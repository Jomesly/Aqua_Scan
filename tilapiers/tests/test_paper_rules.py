"""Unit tests for the paper's rules as implemented in paper_config / telemetry.

Run from the repository root or the tilapiers folder:
    tilapiers/venv/Scripts/python -m pytest tilapiers/tests -q
"""

import threading

import pytest

import paper_config as pc
import telemetry as tele


# --------------------------------------------------------------------- data


class FakeCamera:
    """Deterministic pellet source.

    ``plan`` holds one target depletion rate per observation window; each Pt
    read consumes the next entry.
    """

    def __init__(self, plan=(), p0=16, confidence=0.9, alive=True):
        self.plan = list(plan)
        self.p0 = p0
        self.confidence = confidence
        self.alive = alive
        self.windows = 0

    def pellet(self, kind, p0=None):
        if not self.alive:
            return None
        if kind == "health":
            return {"count": self.p0, "confidence": self.confidence}
        if kind == "p0":
            return {"count": self.p0, "confidence": self.confidence}
        self.windows += 1
        target = self.plan.pop(0) if self.plan else 0.5
        remaining = p0 if p0 else self.p0
        return {"count": int(round(remaining * (1 - target))),
                "confidence": self.confidence}

    @staticmethod
    def evidence():
        return b"\xff\xd8\xff\xd9"


def wire(camera):
    tele._providers["pellet"] = camera.pellet
    tele._providers["evidence"] = camera.evidence


def safe_gate():
    tele._record_reading(27.5, 5.8, True)


def unsafe_gate(temp=33.0, oxygen=4.0):
    tele._record_reading(temp, oxygen, True)


def run_session(source="test"):
    session_id, error = tele.start_session(source)
    assert session_id, error
    tele._active["thread"].join(timeout=60)
    session = tele._one("SELECT * FROM feeding_sessions WHERE id = ?", (session_id,))
    increments = tele._query(
        "SELECT * FROM increments WHERE session_id = ? ORDER BY id", (session_id,)
    )
    return session, increments


@pytest.fixture
def backend(tmp_path, monkeypatch):
    # Test-only acceleration. The production window is guarded separately by
    # test_observation_window_is_strictly_300_seconds.
    monkeypatch.setattr(pc, "OBSERVATION_WINDOW_S", 0.15)

    if tele._conn is not None:
        try:
            tele._conn.close()
        except Exception:  # pragma: no cover - defensive
            pass
        tele._conn = None
    tele._stop.clear()
    tele._active.update({"session_id": None, "thread": None, "stop": threading.Event()})
    tele._schedule_state["last_ran"].clear()
    tele._last_gate["state"] = None
    tele._sim = tele._SimState()
    tele._providers.update({"pellet": None, "evidence": None})

    tele.init(db_path=str(tmp_path / "tilapiers.db"), seed=False, with_workers=False)
    tele.set_config(simulate_pellets=False)

    yield tele

    tele._active["stop"].set()
    thread = tele._active.get("thread")
    if thread is not None and thread.is_alive():
        thread.join(timeout=10)


# ------------------------------------------------------------ Table 2 gate


def test_table2_gate_boundaries():
    assert pc.gate_state(25, 5) == "Safe"
    assert pc.gate_state(31, 5) == "Safe"
    assert pc.gate_state(27, 5) == "Safe"
    assert pc.gate_state(27, 4.999) == "Unsafe"
    assert pc.gate_state(24.9, 5) == "Unsafe"
    assert pc.gate_state(31.1, 5) == "Unsafe"

    # exact values called out by the acceptance check
    assert pc.gate_state(24, 5.0) == "Unsafe"
    assert pc.gate_state(32, 5.0) == "Unsafe"
    assert pc.gate_state(27, 4.9) == "Unsafe"
    assert pc.gate_state(25, 5.0) == "Safe"
    assert pc.gate_state(31, 5.0) == "Safe"


def test_gate_has_no_upper_dissolved_oxygen_bound():
    # The paper bounds DO from below only.
    assert pc.gate_state(27, 12) == "Safe"
    assert pc.gate_state(27, 20) == "Safe"


def test_gate_is_strictly_binary():
    results = {
        pc.gate_state(temp, oxygen)
        for temp in (20, 24.9, 25, 28, 31, 31.1, 40)
        for oxygen in (0, 3, 4.9, 5, 6, 9)
    }
    assert results <= {"Safe", "Unsafe"}
    assert results == {"Safe", "Unsafe"}


def test_gate_treats_missing_reading_as_unsafe():
    assert pc.gate_state(None, 5) == "Unsafe"
    assert pc.gate_state(27, None) == "Unsafe"
    assert pc.gate_state(None, None) == "Unsafe"


def test_failing_parameter_is_named_and_never_ph():
    assert pc.failing_parameters(27, 4.0) == ["dissolved oxygen"]
    assert pc.failing_parameters(33, 6.0) == ["temperature"]
    assert pc.failing_parameters(33, 4.0) == ["temperature", "dissolved oxygen"]
    assert pc.failing_parameters(27, 6.0) == []
    assert pc.failing_parameters(None, None) == ["temperature", "dissolved oxygen"]
    for named in pc.failing_parameters(33, 4.0):
        assert named in {"temperature", "dissolved oxygen"}


# ------------------------------------------------- Table 1 stages and D_ref


def test_stage_classification_from_abw():
    assert pc.classify_stage(36)[0].key == "starter"
    assert pc.classify_stage(99)[0].key == "starter"
    assert pc.classify_stage(127)[0].key == "grower"
    assert pc.classify_stage(221.5)[0].key == "grower"
    assert pc.classify_stage(256.5)[0].key == "finisher"
    assert pc.classify_stage(361.5)[0].key == "finisher"


def test_abw_outside_every_band_is_flagged():
    # Between and beyond the three Table 1 bands.
    for abw in (0, 10, 100, 110, 240, 400):
        stage, out_of_band = pc.classify_stage(abw)
        assert stage is None, abw
        assert out_of_band is True, abw


def test_d_ref_divisor_is_100_not_the_papers_1000():
    # Flagged deviation #1: the paper's 1000 divisor gives 1.25 g, 10x low.
    stage, _ = pc.classify_stage(50)
    paper_value = (50 * stage.rate_pct * 20) / (1000 * stage.freq)
    assert paper_value == 1.25
    assert pc.d_ref_g(stage, 50, 20) == 12.5


def test_d_ref_unit_test_from_the_plan():
    # 20 fish, ABW 50 g, 5%, 4x/day -> 12.5 g
    stage, _ = pc.classify_stage(50)
    assert stage.rate_pct == 5.0
    assert stage.freq == 4
    assert pc.d_ref_g(stage, 50, 20) == 12.5
    assert pc.increment_g(stage, 50, 20) == 3.125


def test_d_ref_for_every_stage():
    grower, _ = pc.classify_stage(150)
    assert pc.d_ref_g(grower, 150, 20) == (150 * 3 * 20) / (100 * 3)

    finisher, _ = pc.classify_stage(300)
    assert pc.d_ref_g(finisher, 300, 20) == (300 * 2 * 20) / (100 * 2)


def test_increment_is_always_a_quarter_of_d_ref():
    for abw in (40, 50, 150, 300):
        stage, _ = pc.classify_stage(abw)
        assert pc.increment_g(stage, abw, 25) == pc.d_ref_g(stage, abw, 25) * 0.25


# ------------------------------------------------------------ Table 3 tiers


def test_table3_boundaries():
    assert pc.classify_depletion(0.80) == ("High", "continue", False)
    assert pc.classify_depletion(1.00) == ("High", "continue", False)
    assert pc.classify_depletion(0.79999) == ("Moderate", "reduce", True)
    assert pc.classify_depletion(0.79) == ("Moderate", "reduce", True)
    assert pc.classify_depletion(0.40) == ("Moderate", "reduce", True)
    assert pc.classify_depletion(0.39999) == ("Low", "stop", False)
    assert pc.classify_depletion(0.39) == ("Low", "stop", False)
    assert pc.classify_depletion(0.0) == ("Low", "stop", False)
    assert pc.classify_depletion(None) == (None, None, False)


def test_depletion_rate_formula():
    assert pc.depletion_rate(10, 2) == pytest.approx(0.8)
    assert pc.depletion_rate(10, 10) == 0.0
    assert pc.depletion_rate(10, 0) == 1.0
    # P0 == 0 cannot produce a rate - the algorithm must not classify it.
    assert pc.depletion_rate(0, 0) is None
    assert pc.depletion_rate(0, 5) is None


def test_observation_window_is_strictly_300_seconds():
    assert pc.OBSERVATION_WINDOW_S == 300


# --------------------------------------------------------- session behaviour


def test_all_high_reaches_the_d_ref_ceiling(backend):
    camera = FakeCamera(plan=[0.87] * 8)
    wire(camera)
    safe_gate()

    session, increments = run_session()

    assert session["status"] == pc.SESSION_CAP_REACHED
    assert session["total_dispensed_g"] == pytest.approx(12.5)
    assert session["total_dispensed_g"] <= session["d_ref_g"] + 1e-9
    assert session["increments_dispensed"] == 4
    assert [row["size_g"] for row in increments] == pytest.approx([3.125] * 4)
    assert {row["classification"] for row in increments} == {"High"}


def test_moderate_halves_then_restores_full(backend):
    camera = FakeCamera(plan=[0.5, 0.87, 0.5, 0.2])
    wire(camera)
    safe_gate()

    session, increments = run_session()

    assert session["status"] == pc.SESSION_LOW_DEPLETION_STOP
    assert [round(row["size_g"], 4) for row in increments] == pytest.approx(
        [3.125, 1.5625, 3.125, 1.5625]
    )
    assert [row["classification"] for row in increments] == [
        "Moderate", "High", "Moderate", "Low",
    ]
    assert [row["action"] for row in increments] == [
        "reduce", "continue", "reduce", "stop",
    ]


def test_consecutive_moderate_continues_at_half(backend):
    camera = FakeCamera(plan=[0.5, 0.5, 0.87, 0.2])
    wire(camera)
    safe_gate()

    session, increments = run_session()

    assert session["status"] == pc.SESSION_LOW_DEPLETION_STOP
    assert [round(row["size_g"], 4) for row in increments] == pytest.approx(
        [3.125, 1.5625, 1.5625, 3.125]
    )


def test_low_depletion_stops_and_logs_uneaten_feed(backend):
    camera = FakeCamera(plan=[0.2])
    wire(camera)
    safe_gate()

    session, increments = run_session()

    assert session["status"] == pc.SESSION_LOW_DEPLETION_STOP
    assert len(increments) == 1
    assert increments[0]["classification"] == "Low"
    assert increments[0]["action"] == "stop"

    alert = tele._one(
        "SELECT * FROM alerts WHERE kind = ? ORDER BY id DESC", (pc.ALERT_UNEATEN_FEED,)
    )
    assert alert is not None
    assert alert["sms_status"] is not None


def test_p0_zero_takes_no_further_feeding_action(backend):
    camera = FakeCamera(plan=[0.5], p0=0)
    wire(camera)
    safe_gate()

    session, increments = run_session()

    assert session["status"] == pc.SESSION_FAIL_SAFE
    assert session["increments_dispensed"] == 1
    assert increments[0]["flag"] == pc.FLAG_P0_ZERO
    assert increments[0]["classification"] is None
    assert increments[0]["p_start"] == 0

    flag = tele._one(
        "SELECT * FROM alerts WHERE kind = ? ORDER BY id DESC", (pc.ALERT_FAIL_SAFE,)
    )
    assert flag is not None and "p0_zero" in flag["message"]


def test_low_confidence_holds_the_previous_state(backend):
    camera = FakeCamera(plan=[0.5, 0.87, 0.2])
    wire(camera)
    safe_gate()
    # Second window reads below the confidence threshold.
    original = camera.pellet

    def low_confidence(kind, p0=None):
        if kind == "pt" and camera.windows == 1:
            camera.confidence = 0.3
        elif kind == "p0":
            camera.confidence = 0.9
        return original(kind, p0)

    tele._providers["pellet"] = low_confidence

    session, increments = run_session()

    assert increments[1]["flag"] == pc.FLAG_LOW_CONFIDENCE
    assert increments[1]["classification"] is None
    # Held: the window after the low-confidence read is still a half increment.
    assert round(increments[1]["size_g"], 4) == 1.5625
    assert round(increments[2]["size_g"], 4) == 1.5625
    alert = tele._one(
        "SELECT * FROM alerts WHERE kind = ? ORDER BY id DESC", (pc.ALERT_LOW_CONFIDENCE,)
    )
    assert alert is not None


def test_rapid_depletion_is_flagged_not_classified_high(backend):
    camera = FakeCamera(plan=[0.5, 1.0, 0.2])
    wire(camera)
    safe_gate()

    session, increments = run_session()

    assert increments[1]["flag"] == pc.FLAG_RAPID_DEPLETION
    assert increments[1]["classification"] is None
    assert increments[1]["depletion_rate"] >= pc.RAPID_DEPLETION
    # Not auto-classified High, so the previous (half) state is held.
    assert round(increments[2]["size_g"], 4) == 1.5625
    alert = tele._one(
        "SELECT * FROM alerts WHERE kind = ? ORDER BY id DESC",
        (pc.ALERT_RAPID_DEPLETION,),
    )
    assert alert is not None


def test_camera_dropout_takes_no_feeding_action(backend):
    tele._providers["pellet"] = lambda kind, p0=None: None
    tele._providers["evidence"] = FakeCamera.evidence
    safe_gate()

    session, increments = run_session()

    assert session["status"] == pc.SESSION_FAIL_SAFE
    assert session["increments_dispensed"] == 0
    assert increments == []


def test_missing_sensor_reading_takes_no_feeding_action(backend):
    wire(FakeCamera(plan=[0.87] * 8))
    # No sensor reading has ever been recorded.
    session, increments = run_session()

    assert session["status"] == pc.SESSION_FAIL_SAFE
    assert session["increments_dispensed"] == 0
    assert increments == []


def test_invalid_sensor_reading_takes_no_feeding_action(backend):
    wire(FakeCamera(plan=[0.87] * 8))
    tele._record_reading(None, None, False)

    session, increments = run_session()

    assert session["status"] == pc.SESSION_FAIL_SAFE
    assert session["increments_dispensed"] == 0
    assert increments == []


def test_unsafe_gate_halts_before_the_first_increment(backend):
    wire(FakeCamera(plan=[0.87] * 8))
    unsafe_gate()

    session, increments = run_session()

    assert session["status"] == pc.SESSION_GATE_HALT
    assert session["increments_dispensed"] == 0
    assert increments == []

    alert = tele._one(
        "SELECT * FROM alerts WHERE kind = ? ORDER BY id DESC", (pc.ALERT_UNSAFE_ENV,)
    )
    assert alert is not None
    assert alert["sms_status"] is not None


def test_unsafe_sensor_write_logs_sms_with_status_and_times(backend):
    tele._last_gate["state"] = "Safe"
    tele._record_reading(33.0, 4.1, True)

    alerts = tele.get_alerts()
    unsafe = [a for a in alerts if a["kind"] == pc.ALERT_UNSAFE_ENV]
    assert unsafe
    row = unsafe[0]
    assert row["sms_status"] == "delivered"
    assert row["sms_sent_at"] and row["sms_delivered_at"]
    assert "dissolved oxygen" in row["message"] and "temperature" in row["message"]


def test_gate_flips_unsafe_below_five_mg_per_litre(backend):
    tele._record_reading(27.0, 4.9, True)
    assert tele.get_environment()["gate_state"] == "Unsafe"
    tele._record_reading(27.0, 5.0, True)
    assert tele.get_environment()["gate_state"] == "Safe"
    tele._record_reading(24.9, 6.0, True)
    assert tele.get_environment()["gate_state"] == "Unsafe"
    tele._record_reading(31.1, 6.0, True)
    assert tele.get_environment()["gate_state"] == "Unsafe"


def test_simulation_switch_fills_in_when_camera_sees_no_pellets(backend):
    tele.set_config(simulate_pellets=True)
    tele._providers["pellet"] = lambda kind, p0=None: {"count": 0, "confidence": 0.9}
    tele._providers["evidence"] = FakeCamera.evidence
    safe_gate()

    session, increments = run_session()

    # The real zero would have fired p0_zero; simulation filled the window in,
    # so at least one increment was classified from a simulated reading.
    assert session["increments_dispensed"] >= 1
    assert increments[0]["classification"] in {"High", "Moderate", "Low"}
    assert increments[0]["p0_simulated"] == 1
    assert increments[0]["pt_simulated"] == 1


def test_simulation_off_keeps_the_real_zero(backend):
    tele.set_config(simulate_pellets=False)
    tele._providers["pellet"] = lambda kind, p0=None: {"count": 0, "confidence": 0.9}
    tele._providers["evidence"] = FakeCamera.evidence
    safe_gate()

    session, increments = run_session()

    assert session["status"] == pc.SESSION_FAIL_SAFE
    assert increments[0]["flag"] == pc.FLAG_P0_ZERO
    assert increments[0]["p0_simulated"] == 0


# -------------------------------------------------------------- presentation


class _Box:
    def __init__(self, class_id, confidence):
        self.cls = [class_id]
        self.conf = [confidence]
        self.xyxy = [[0, 0, 10, 10]]


class _Result:
    def __init__(self, class_ids, names):
        self.names = names
        self.boxes = [_Box(class_id, 0.9) for class_id in class_ids]
        self.obb = None
        self.tilapiers_suppressed_people = 0


def test_pellet_count_counts_only_the_pellets_class():
    from detection_core import result_metrics

    names = {0: "Bubbles", 1: "Pellets", 2: "Tilapia", 3: "Waste"}
    result = _Result([0, 1, 1, 1, 2, 3], names)
    metrics = result_metrics(result)

    assert metrics["pellet_count"] == 3
    assert metrics["count"] == 6
    assert metrics["class_counts"]["Tilapia"] == 1


def test_no_pellets_means_zero_not_the_total():
    from detection_core import result_metrics

    names = {0: "Bubbles", 1: "Pellets", 2: "Tilapia", 3: "Waste"}
    metrics = result_metrics(_Result([2, 2, 3], names))
    assert metrics["pellet_count"] == 0
    assert metrics["count"] == 3


# ------------------------------------------------------------------- storage


def test_seed_rows_are_marked_seed(backend):
    tele.seed_data()
    rows = tele._query("SELECT DISTINCT source FROM feeding_sessions")
    assert {row["source"] for row in rows} == {pc.SOURCE_SEED}
    assert tele._one("SELECT COUNT(*) c FROM feeding_sessions")["c"] == pc.SEED_SESSION_COUNT

    history = tele.get_feeding_history()
    assert history["sessions"]
    assert all(session["seed"] for session in history["sessions"])


def test_seed_evidence_frames_are_present(backend):
    tele.seed_data()
    row = tele._one(
        "SELECT COUNT(*) c FROM increments WHERE evidence_p0_jpeg IS NOT NULL"
        " AND evidence_pt_jpeg IS NOT NULL"
    )
    assert row["c"] > 0

    detail = tele.get_feeding_history(session_id=1)
    assert detail["increments"]
    for increment in detail["increments"]:
        assert increment["evidence_p0"].startswith("data:image/jpeg;base64,")
        assert increment["evidence_pt"].startswith("data:image/jpeg;base64,")


def test_csv_export_covers_the_three_documented_tables(backend):
    tele.seed_data()
    for table, expected in (
        ("increments", "depletion_rate"),
        ("sensor_readings", "dissolved_oxygen_mg"),
        ("alerts", "sms_status"),
    ):
        csv_text = tele.export_csv(table)
        lines = csv_text.splitlines()
        assert lines, table
        assert expected in lines[0]
    # The seed writes sessions, increments and alerts; sensor readings only start
    # once the live sensor worker ticks, so only those two carry rows here.
    assert len(tele.export_csv("increments").splitlines()) > 1
    assert len(tele.export_csv("alerts").splitlines()) > 1


def test_config_round_trip_derives_stage_and_d_ref(backend):
    cfg = tele.set_config(abw_g=150, num_stocks=30, mobile_number="+639990001111")
    assert cfg["derived_stage"] == "grower"
    assert cfg["session_times"] == ["06:00", "12:00", "18:00"]
    assert cfg["d_ref_g"] == pytest.approx((150 * 3 * 30) / (100 * 3))

    cfg = tele.set_config(abw_g=10)
    assert cfg["out_of_band"] is True
    assert cfg["derived_stage"] == "grower"  # held last valid stage

    cfg = tele.set_config(abw_g=50, num_stocks=20, mobile_number="+639170000000")
    assert cfg["derived_stage"] == "starter"
    assert cfg["d_ref_g"] == pytest.approx(12.5)


def test_schedule_reports_pre_feed_offset_of_one_hour(backend):
    tele.set_config(abw_g=50, num_stocks=20)
    schedule = tele.get_schedule()
    assert schedule["prefeed_offset_min"] == 60
    assert schedule["sessions_per_day"] == 4
    assert len(schedule["times"]) == 4
    assert schedule["maintenance"]["day"] == "Saturday"
