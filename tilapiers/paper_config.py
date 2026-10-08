"""Single source of truth for every constant taken from FINAL PAPER TILAPIERS!.

If code and paper disagree, this module follows the paper, except where
DEVIATIONS below says otherwise.
"""

from dataclasses import dataclass

PAPER_TITLE = (
    "Tilapiers: A YOLOv8-Based Intelligent Behavior Analysis and "
    "Automated Feeding System for Tilapia"
)

DEVIATIONS = {
    "d_ref_divisor": (
        "Paper's D_ref divisor (1000) yields a dose 10x too small; this build "
        "uses 100 so that D_ref = daily ration / feedings per day. Paper to be corrected."
    ),
    "tilapia_class": (
        "Paper trains a 'tilapia' class yet states the system does not detect "
        "fish; the UI reports it as 'detected, not counted'."
    ),
    "stage_derivation": (
        "Paper classifies culture stage from ABW and also states stage is never "
        "auto-detected; this build derives stage from ABW at entry only."
    ),
}

# --- Table 2: binary environmental classification --------------------------
TEMP_MIN_C = 25.0
TEMP_MAX_C = 31.0
DO_MIN_MG = 5.0
# No upper dissolved-oxygen bound in the paper. No pH.

# --- Table 1: culture stages -----------------------------------------------
@dataclass(frozen=True)
class Stage:
    key: str
    label: str
    month: int
    abw_min_g: float
    abw_max_g: float
    rate_pct: float
    freq: int
    feed: str
    sessions_per_day: int


STAGES = (
    Stage("starter", "Starter", 2, 36.0, 99.0, 5.0, 4, "Starter floater", 4),
    Stage("grower", "Grower", 3, 127.0, 221.5, 3.0, 3, "Grower floater", 3),
    Stage("finisher", "Finisher", 4, 256.5, 361.5, 2.0, 2, "Finisher floater", 2),
)

STAGE_BY_KEY = {s.key: s for s in STAGES}
DEFAULT_STAGE_KEY = "starter"

# --- Feeding decision algorithm --------------------------------------------
D_REF_DIVISOR = 100  # DEVIATIONS["d_ref_divisor"]
INCREMENT_FRACTION = 0.25
OBSERVATION_WINDOW_S = 300  # strict; no demo override

HIGH_DEPLETION = 0.80
MODERATE_DEPLETION = 0.40

HALF_INCREMENT_FRACTION = 0.5  # Reduce Feed Module

# Detection-confidence threshold: readings below this are suppressed
# (hold previous state, flag low_confidence) per the fail-safe rules.
MIN_CONFIDENCE = 0.40

# Pellet depletion above this within one window is not physically plausible
# for a single increment and is flagged for review instead of auto-classified.
RAPID_DEPLETION = 0.98


def classify_stage(abw_g):
    """Return (stage, out_of_band) per the paper's stage pseudocode."""
    for stage in STAGES:
        if stage.abw_min_g <= abw_g <= stage.abw_max_g:
            return stage, False
    return None, True


def d_ref_g(stage, abw_g, num_stocks):
    """D_ref = (ABW x rate_pct x N) / (D_REF_DIVISOR x freq)."""
    if stage is None or num_stocks <= 0:
        return 0.0
    return (abw_g * stage.rate_pct * num_stocks) / (D_REF_DIVISOR * stage.freq)


def increment_g(stage, abw_g, num_stocks):
    return d_ref_g(stage, abw_g, num_stocks) * INCREMENT_FRACTION


def gate_state(temperature_c, dissolved_oxygen_mg):
    """Table 2: Safe iff 25 <= T <= 31 AND DO >= 5. Any failure is Unsafe."""
    if temperature_c is None or dissolved_oxygen_mg is None:
        return "Unsafe"
    if not (TEMP_MIN_C <= temperature_c <= TEMP_MAX_C):
        return "Unsafe"
    if dissolved_oxygen_mg < DO_MIN_MG:
        return "Unsafe"
    return "Safe"


def failing_parameters(temperature_c, dissolved_oxygen_mg):
    """Names the parameter(s) that failed the Table 2 gate."""
    failing = []
    if temperature_c is None:
        failing.append("temperature")
    elif not (TEMP_MIN_C <= temperature_c <= TEMP_MAX_C):
        failing.append("temperature")
    if dissolved_oxygen_mg is None:
        failing.append("dissolved oxygen")
    elif dissolved_oxygen_mg < DO_MIN_MG:
        failing.append("dissolved oxygen")
    return failing


def depletion_rate(p0, pt):
    """R = (P0 - Pt) / P0. Returns None when P0 == 0."""
    if p0 is None or p0 == 0:
        return None
    return (p0 - pt) / p0


def classify_depletion(rate):
    """Table 3. Returns (classification, action, next_is_half)."""
    if rate is None:
        return None, None, False
    if rate >= HIGH_DEPLETION:
        return "High", "continue", False
    if rate >= MODERATE_DEPLETION:
        return "Moderate", "reduce", True
    return "Low", "stop", False


# --- Scheduler -------------------------------------------------------------
# The paper gives session counts (4/3/2 per day) but no clock times, so times
# are config-driven with these defaults. Pre-feed evaluation is 1 h before each.
DEFAULT_SESSION_TIMES = {
    "starter": ("06:00", "10:00", "14:00", "18:00"),
    "grower": ("06:00", "12:00", "18:00"),
    "finisher": ("06:00", "16:00"),
}
PREFEED_OFFSET_MIN = 60
MAINTENANCE_DAY = 5  # Saturday (paper: SMS every Saturday); no time given
MAINTENANCE_TIME = "08:00"
WEEKLY_RECALIBRATION_DAY = 0  # Monday

# --- Alert kinds / severities ----------------------------------------------
ALERT_UNSAFE_ENV = "unsafe_env"
ALERT_UNEATEN_FEED = "uneaten_feed"
ALERT_FAIL_SAFE = "fail_safe"
ALERT_LOW_CONFIDENCE = "low_confidence"
ALERT_RAPID_DEPLETION = "rapid_depletion"
ALERT_MAINTENANCE = "maintenance"

# --- Session / increment statuses ------------------------------------------
SESSION_COMPLETED = "completed"
SESSION_LOW_DEPLETION_STOP = "low_depletion_stop"
SESSION_CAP_REACHED = "session_cap_reached"
SESSION_GATE_HALT = "gate_halt"
SESSION_FAIL_SAFE = "fail_safe"

FLAG_P0_ZERO = "p0_zero"
FLAG_LOW_CONFIDENCE = "low_confidence"
FLAG_RAPID_DEPLETION = "rapid_depletion"

SOURCE_LIVE = "live"
SOURCE_SEED = "seed"
SOURCE_TEST = "test"

SEED_SESSION_COUNT = 10
