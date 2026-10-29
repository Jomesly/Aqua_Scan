"""Fish Health Monitoring rules (paper Figure 11, steps 1-3).

Screening flags visible skin defects (skin erosion, red sores); it does not name
a disease and is not a diagnosis. A flagged fish is referred to the technician.
"""

from .thresholds import Thresholds

NORMAL = "Normal"
WATCH = "Watch"
REFER = "Refer to technician"
UNSCREENED = "Not screened"
INSUFFICIENT = "Insufficient data"
HEALTHY = "Healthy"
EROSION = "Skin erosion"
RED_SORES = "Red sores"
DEFECT_CLASSES = (EROSION, RED_SORES)
CLASSES = (HEALTHY, *DEFECT_CLASSES)
# What each flag looks like on the fish, for reasons and help text.
DEFECT_DESCRIPTIONS = {
    EROSION: "worn or eroded skin, missing scales or pale patches",
    RED_SORES: "red, bleeding sores, ulcers or reddened fins",
}


def condition_factor(weight_g, length_cm):
    """Fulton's condition factor K = 100 * W(g) / L(cm)^3."""
    if weight_g is None or not length_cm or length_cm <= 0:
        return None
    return 100.0 * float(weight_g) / float(length_cm) ** 3


def fish_status(cls, conf, k, t=Thresholds()):
    if cls is None:
        return {"status": UNSCREENED, "reasons": ["No fish detected above the confidence threshold."]}
    reasons = []
    if cls in DEFECT_CLASSES:
        seen = f"{cls} ({DEFECT_DESCRIPTIONS[cls]})"
        if conf is not None and conf >= t.referral_conf:
            status = REFER
            reasons.append(f"{seen} flagged at {conf:.0%} confidence (referral cutoff "
                           f"{t.referral_conf:.0%}). Set the fish apart until the technician checks it.")
        else:
            status = WATCH
            reasons.append(f"Possible {seen}, below the referral cutoff.")
    else:
        status = NORMAL
        reasons.append("No visible defect flagged.")
    if k is None:
        reasons.append("K not measured (no scale or no weight).")
    elif k < t.k_min or k > t.k_max:
        if status == NORMAL:
            status = WATCH
        reasons.append(f"Condition factor K {k:.2f} outside the accepted range {t.k_min:g} to {t.k_max:g}.")
    return {"status": status, "reasons": reasons}


def pond_status(statuses, t=Thresholds()):
    total = len(statuses)
    screened = [s for s in statuses if s in (NORMAL, WATCH, REFER)]
    n = len(screened)
    share_screened = round(n / total, 4) if total else 0.0
    if n == 0 or share_screened < t.min_screened_share:
        return {"status": INSUFFICIENT, "n": n, "watch_share": None, "refer_count": 0,
                "screened_share": share_screened}
    refer = sum(1 for s in screened if s == REFER)
    flagged = sum(1 for s in screened if s in (WATCH, REFER))
    share = flagged / n
    if refer >= 1 or share >= t.pond_refer_share:
        status = REFER
    elif share >= t.pond_watch_share:
        status = WATCH
    else:
        status = NORMAL
    return {"status": status, "n": n, "watch_share": round(share, 4), "refer_count": refer,
            "screened_share": share_screened}
