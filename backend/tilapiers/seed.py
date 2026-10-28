"""Demo data for panel presentations (TILAPIERS_DEMO=1, or `python -m tilapiers.seed`).

Creates three ponds that show different states, a culture-period temperature
log, caretaker observations, sampling rounds with weighed/measured fish and
technician scores, and probe calibration pairs. Every seeded row is tagged
(source='seed' / analysis_source='seed') so it is never mistaken for field data.
"""

import math
import random
import time
from datetime import datetime

from .rules import health as health_rules
from .rules.environment import PH_TZ, season_for

DAY = 86400.0

SEASON_OFFSET = {"Cool dry": -1.6, "Hot dry": 1.1, "Rainy": -0.4}

PONDS = [
    # name, days since stocking, growth scale, rounds at DOC, base temp, scenario
    dict(name="Pond A", location="BFAR outdoor pond, east row", area_m2=400, stocked_count=1200,
         feeding_regime="Commercial pellets, 2x daily", doc=150, scale=530,
         rounds=[30, 48, 66, 84, 102, 120, 138], base=28.2, scenario="approaching"),
    dict(name="Pond B", location="BFAR outdoor pond, west row", area_m2=350, stocked_count=1000,
         feeding_regime="Commercial pellets, 2x daily", doc=96, scale=560,
         rounds=[28, 46, 64, 86], base=27.6, scenario="watch"),
    dict(name="Pond C", location="BFAR outdoor pond, north row", area_m2=420, stocked_count=1100,
         feeding_regime="Pellets + natural feed", doc=176, scale=560,
         rounds=[40, 70, 100, 130, 160, 172], base=28.4, scenario="ready"),
]


def _weight(doc, scale):
    return scale / (1 + math.exp(-0.03 * (doc - 140))) + 2


def _temp_series(rng, start, end, base, step=900, spikes=()):
    out = []
    t = start
    noise = 0.0
    excursion = 0
    while t <= end:
        local = datetime.fromtimestamp(t, PH_TZ)
        hour = local.hour + local.minute / 60
        diurnal = 1.3 * math.sin((hour - 9) / 24 * 2 * math.pi)
        noise = 0.85 * noise + rng.gauss(0, 0.12)
        if excursion == 0 and rng.random() < 0.0012:
            excursion = rng.randint(8, 30)
        temp = base + SEASON_OFFSET[season_for(t)] + diurnal + noise
        if excursion:
            excursion -= 1
            temp = max(temp, 31.4 + rng.uniform(0, 0.4))
        for s0, s1, v in spikes:
            if s0 <= t <= s1:
                temp = v + rng.gauss(0, 0.15)
        out.append((t, round(temp, 2)))
        t += step
    return out


def _indicators(rng, poor=False):
    if poor:
        return dict(gill_color_index=rng.uniform(0.18, 0.38), skin_color_index=rng.uniform(0.35, 0.5),
                    fin_integrity=rng.uniform(0.45, 0.62), eye_clarity=rng.uniform(0.2, 0.4),
                    body_shape=rng.gauss(0.34, 0.015))
    return dict(gill_color_index=min(rng.gauss(0.68, 0.08), 0.98), skin_color_index=min(rng.gauss(0.7, 0.06), 0.98),
                fin_integrity=min(rng.gauss(0.88, 0.05), 1.0), eye_clarity=min(rng.gauss(0.65, 0.08), 0.98),
                body_shape=rng.gauss(0.38, 0.015))


def _true_score(rng, x):
    s = (-0.6 + 1.0 * x["condition_factor"] + 1.8 * x["gill_color_index"] + 0.8 * x["skin_color_index"]
         + 1.0 * x["fin_integrity"] + 0.6 * x["eye_clarity"] + rng.gauss(0, 0.25))
    return min(5.0, max(1.0, round(s * 2) / 2))


def seed_demo(services, rng_seed=7):
    rng = random.Random(rng_seed)
    db = services.db
    now = time.time()
    model = services.fci_model()
    t = services.thresholds()

    db.set_setting("contact", {"name": "Pond caretaker", "email": "", "phone": ""})

    for spec in PONDS:
        stocked = now - spec["doc"] * DAY
        pond_id = services.create_pond({
            "name": spec["name"], "location": spec["location"], "area_m2": spec["area_m2"],
            "stocked_at": stocked, "stocked_count": spec["stocked_count"],
            "feeding_regime": spec["feeding_regime"], "notes": "Demo pond (seeded data)",
        })

        spikes = []
        if spec["scenario"] == "watch":
            last = stocked + spec["rounds"][-1] * DAY
            spikes = [(last - 6 * DAY, last - 6 * DAY + 5 * 3600, 32.6), (last - 3 * DAY, last - 3 * DAY + 3 * 3600, 32.4)]
        readings = _temp_series(rng, stocked, now - 60, spec["base"], spikes=spikes)
        readings.append((now - 5, readings[-1][1]))  # so the pond is not shown as probe-offline at startup
        db.executemany(
            "INSERT INTO temperature_readings (pond_id, ts, temperature_c, source) VALUES (?,?,?,?)",
            [(pond_id, ts, c, "seed") for ts, c in readings])

        # weekly caretaker observations
        obs_t = stocked + 3 * DAY
        while obs_t < now:
            algae = rng.random() < (0.3 if spec["scenario"] == "watch" else 0.12)
            db.insert("observations", {
                "pond_id": pond_id, "ts": obs_t, "algae_seen": 1 if algae else 0,
                "do_ppm": round(rng.uniform(4.2, 7.5), 1) if rng.random() < 0.4 else None,
                "ph": round(rng.uniform(6.8, 8.2), 1) if rng.random() < 0.3 else None,
                "ammonia_ppm": None, "nitrate_ppm": None,
                "notes": "Green tint near inlet" if algae else None, "recorded_by": "caretaker (seed)",
            })
            obs_t += 7 * DAY
        if spec["scenario"] == "watch":
            db.insert("observations", {"pond_id": pond_id, "ts": now - 0.5 * DAY, "algae_seen": 1, "do_ppm": 4.6,
                                       "notes": "Visible algae along the north edge", "recorded_by": "caretaker (seed)"})

        for i, doc in enumerate(spec["rounds"]):
            ts = stocked + doc * DAY + rng.uniform(8, 10) * 3600
            conditions = ["open sunlight", "shade", "overcast"]
            round_id = services.create_round(pond_id, {
                "sampled_at": ts, "capture_condition": conditions[i % 3],
                "weather": rng.choice(["Sunny", "Cloudy", "Light rain"]),
                "phone_model": rng.choice(["Samsung Galaxy A15", "Redmi Note 13", "iPhone 12"]),
                "notes": "Seeded sampling round",
            })
            mean_w = _weight(doc, spec["scale"])
            last_round = i == len(spec["rounds"]) - 1
            n = 12
            for seq in range(1, n + 1):
                cv = 0.11 if spec["scenario"] == "ready" else 0.16
                w = max(5.0, rng.lognormvariate(math.log(mean_w), cv))
                poor = spec["scenario"] == "watch" and last_round and seq <= 2
                k_true = rng.gauss(1.42 if poor else 1.72, 0.07)
                length = round((100 * w / k_true) ** (1 / 3), 1)
                k = health_rules.condition_factor(w, length)
                x = {"condition_factor": k, **_indicators(rng, poor)}
                fci = health_rules.predict_fci(model, x)
                score = _true_score(rng, x) if rng.random() < 0.7 else None
                db.insert("fish", {
                    "round_id": round_id, "seq": seq, "weight_g": round(w, 1), "length_cm": length,
                    "condition_factor": round(k, 4), **{key: round(v, 4) for key, v in x.items() if key != "condition_factor"},
                    "fci": fci, "flagged": 1 if fci is not None and fci < t.fci_flag_below else 0,
                    "technician_score": score, "analysis_source": "seed", "created_at": ts,
                })

            before = db.scalar("SELECT COALESCE(MAX(id), 0) FROM notifications")
            detail = services.complete_round(round_id)
            a = detail["assessment"]
            # technician's independent assessment: mostly agrees, sometimes not
            tech_h = a["health"]["status"]
            if rng.random() < 0.15:
                tech_h = rng.choice(["Normal", "Watch", "Refer to technician"])
            sys_r = a["readiness"]["status"]
            tech_r = "Approaching" if sys_r.startswith("Size reached") else sys_r
            if rng.random() < 0.15:
                tech_r = rng.choice(["Not Ready", "Approaching", "Ready"])
            db.execute("UPDATE sampling_rounds SET technician_health=?, technician_readiness=?, completed_at=? "
                       "WHERE id=?", (tech_h, tech_r, ts + 3600, round_id))
            db.execute("UPDATE notifications SET ts=? WHERE id>?", (ts + 3600, before))

    for _ in range(12):
        ref = round(rng.uniform(24.5, 31.5), 1)
        db.insert("probe_calibrations", {"pond_id": 1, "ts": now - rng.uniform(1, 30) * DAY,
                                         "probe_c": round(ref + rng.gauss(0.12, 0.1), 2), "reference_c": ref,
                                         "notes": "Seeded calibration pair"})


if __name__ == "__main__":
    from .config import Settings
    from .db import Database
    from .notify import Notifier
    from .services import Services
    from .vision.detector import load_detector

    settings = Settings.from_env()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    database = Database(settings.db_path)
    svc = Services(database, settings, Notifier(database, settings), load_detector())
    if svc.list_ponds():
        print("Database already has ponds; delete backend/data/tilapiers.db to reseed.")
    else:
        seed_demo(svc)
        print("Seeded demo data into", settings.db_path)
