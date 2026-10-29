"""Single source of truth for every rule cutoff (paper Table 14).

Every value is PROVISIONAL until the administrator records that it was confirmed
with the BFAR technician. The paper leaves them as "[to be set with the BFAR
technician]"; these defaults only let the prototype run. They are editable in
Maintenance and stored in the database with a dated change history.
"""

from dataclasses import asdict, dataclass, fields


@dataclass(frozen=True)
class Thresholds:
    # --- Disease screening / Health status --------------------------------------
    det_conf: float = 0.25  # minimum confidence for a screening result to be accepted
    referral_conf: float = 0.50  # skin erosion / red sores at or above -> Refer to technician
    k_min: float = 0.9  # Flores-Garcia et al. (2022): K below 0.9 usually means emaciation
    k_max: float = 2.0
    pond_watch_share: float = 0.10  # share of fish Watch/Refer -> pond Watch
    pond_refer_share: float = 0.30  # share of fish Watch/Refer -> pond Refer (or any Refer fish)
    min_screened_share: float = 0.70  # below this share of sampled fish screened -> pond health Insufficient data

    # --- Harvest readiness -----------------------------------------------------
    target_weight_g: float = 300.0
    approaching_share: float = 0.50
    ready_share: float = 0.80
    max_cv: float = 0.25  # coefficient of variation of weight (fraction)
    min_sgr: float = 0.5  # % body weight per day
    culture_days_min: float = 120.0  # usual culture period, about 4-6 months
    culture_days_max: float = 180.0
    growth_poly_min_rounds: int = 5

    # --- Weight estimation -----------------------------------------------------
    lw_a: float = 0.0141  # provisional W = a * L^b until a model is fitted
    lw_b: float = 3.0
    weight_fit_min_fish: int = 10

    # --- Sampling board (inner rectangle between the marker corners) ----------
    board_width_cm: float = 32.0  # fits A3 landscape with the markers
    board_height_cm: float = 20.0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        known = {f.name: f.type for f in fields(cls)}
        clean = {}
        for key, value in (data or {}).items():
            if key not in known or value is None or value == "":
                continue
            clean[key] = int(value) if known[key] in (int, "int") else float(value)
        return cls(**clean)


FRACTIONS = ("det_conf", "referral_conf", "pond_watch_share", "pond_refer_share", "min_screened_share",
             "approaching_share", "ready_share", "max_cv")
POSITIVE = ("k_min", "k_max", "target_weight_g", "min_sgr", "culture_days_min", "culture_days_max", "lw_a", "lw_b",
            "board_width_cm", "board_height_cm")
MIN_INT = {"growth_poly_min_rounds": 3, "weight_fit_min_fish": 3}

GROUPS = {
    "health": ["det_conf", "referral_conf", "k_min", "k_max", "pond_watch_share", "pond_refer_share",
               "min_screened_share"],
    "harvest": ["target_weight_g", "approaching_share", "ready_share", "max_cv", "min_sgr",
                "culture_days_min", "culture_days_max", "growth_poly_min_rounds"],
    "weight": ["lw_a", "lw_b", "weight_fit_min_fish"],
    "board": ["board_width_cm", "board_height_cm"],
}

LABELS = {
    "det_conf": "Detection confidence (minimum)",
    "referral_conf": "Referral confidence (skin erosion / red sores)",
    "k_min": "Condition factor K, lower limit",
    "k_max": "Condition factor K, upper limit",
    "pond_watch_share": "Pond Watch: share of fish Watch/Refer",
    "pond_refer_share": "Pond Refer: share of fish Watch/Refer",
    "min_screened_share": "Minimum share of sampled fish screened",
    "target_weight_g": "Target market size (g)",
    "approaching_share": "Share at target for Approaching",
    "ready_share": "Share at target for Ready",
    "max_cv": "Maximum weight CV",
    "min_sgr": "Minimum specific growth rate (%/day)",
    "culture_days_min": "Usual culture period, from (days)",
    "culture_days_max": "Usual culture period, to (days)",
    "growth_poly_min_rounds": "Rounds needed for the growth curve",
    "lw_a": "Provisional length-weight a",
    "lw_b": "Provisional length-weight b",
    "weight_fit_min_fish": "Fish needed to fit the weight model",
    "board_width_cm": "Board inner width (cm)",
    "board_height_cm": "Board inner height (cm)",
}
