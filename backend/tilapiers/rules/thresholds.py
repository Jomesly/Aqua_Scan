"""Single source of truth for every rule cutoff.

Only the temperature band (24-31 °C) is fixed by the study team. Every other
value is PROVISIONAL: the study states that the Moderate/Critical limits, the
health thresholds, the target market size and the readiness cutoffs are to be
set with a BFAR technician (Chapter 3). They are editable from the Settings page
and stored in the database; these are only the starting defaults.
"""

from dataclasses import asdict, dataclass, fields


@dataclass(frozen=True)
class Thresholds:
    # --- Environment ------------------------------------------------------
    temp_min_c: float = 24.0  # fixed by the study team
    temp_max_c: float = 31.0  # fixed by the study team
    temp_moderate_margin_c: float = 1.0  # outside band by <= this -> Moderate, beyond -> Critical
    do_good_min_ppm: float = 5.0  # BFAR-NCR consultation: at least 5 ppm
    do_critical_below_ppm: float = 3.0
    algae_report_valid_days: float = 3.0  # how long a caretaker's algae sighting counts
    sensor_stale_after_s: float = 180.0  # no reading for this long -> probe offline

    # --- Fish health ------------------------------------------------------
    fci_flag_below: float = 3.0  # Fish Condition Index on the 1-5 technician scale
    health_watch_share: float = 0.10  # share of flagged fish -> Watch
    health_refer_share: float = 0.30  # share of flagged fish -> Refer to technician
    condition_factor_low: float = 1.4  # Fulton K below this -> Watch

    # --- Harvest readiness ------------------------------------------------
    target_weight_g: float = 250.0
    ready_share_at_target: float = 0.80
    approaching_share_at_target: float = 0.50
    max_weight_cv: float = 0.25
    culture_days_min: float = 120.0  # usual culture period: 4-6 months
    culture_days_max: float = 180.0
    growth_poly_min_rounds: int = 5
    recent_critical_days: float = 7.0
    min_fish_per_round: int = 10

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        known = {f.name: f.type for f in fields(cls)}
        clean = {}
        for key, value in (data or {}).items():
            if key not in known or value is None:
                continue
            clean[key] = int(value) if known[key] in (int, "int") else float(value)
        return cls(**clean)


FIXED_KEYS = ("temp_min_c", "temp_max_c")

GROUPS = {
    "environment": [
        "temp_min_c", "temp_max_c", "temp_moderate_margin_c", "do_good_min_ppm",
        "do_critical_below_ppm", "algae_report_valid_days", "sensor_stale_after_s",
    ],
    "health": ["fci_flag_below", "health_watch_share", "health_refer_share", "condition_factor_low"],
    "harvest": [
        "target_weight_g", "ready_share_at_target", "approaching_share_at_target", "max_weight_cv",
        "culture_days_min", "culture_days_max", "growth_poly_min_rounds", "recent_critical_days",
        "min_fish_per_round",
    ],
}
