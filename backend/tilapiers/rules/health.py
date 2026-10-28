"""Fish Health Monitoring rules (paper Figure 11, steps 1-3).

Screening finds visible signs consistent with Aeromonas or TiLV; it is not a
diagnosis. A flagged fish is referred to the technician.
"""

from .thresholds import Thresholds

NORMAL = "Normal"
WATCH = "Watch"
REFER = "Refer to technician"
UNSCREENED = "Not screened"
INSUFFICIENT = "Insufficient data"
DISEASE_CLASSES = ("Aeromonas", "TiLV")


def condition_factor(weight_g, length_cm):
    """Fulton's condition factor K = 100 * W(g) / L(cm)^3."""
    if weight_g is None or not length_cm or length_cm <= 0:
        return None
    return 100.0 * float(weight_g) / float(length_cm) ** 3


def fish_status(cls, conf, k, t=Thresholds()):
    if cls is None:
        return {"status": UNSCREENED, "reasons": ["No fish detected above the confidence threshold."]}
    reasons = []
    if cls in DISEASE_CLASSES:
        if conf is not None and conf >= t.referral_conf:
            status = REFER
            reasons.append(f"Signs consistent with {cls} at {conf:.0%} confidence (referral cutoff "
                           f"{t.referral_conf:.0%}). Set the fish apart until the technician checks it.")
        else:
            status = WATCH
            reasons.append(f"Possible signs consistent with {cls}, below the referral cutoff.")
    else:
        status = NORMAL
        reasons.append("No visible signs screened.")
    if k is None:
        reasons.append("K not measured (no scale or no weight).")
    elif k < t.k_min or k > t.k_max:
        if status == NORMAL:
            status = WATCH
        reasons.append(f"Condition factor K {k:.2f} outside the accepted range {t.k_min:g} to {t.k_max:g}.")
    return {"status": status, "reasons": reasons}


def pond_status(statuses, t=Thresholds()):
    screened = [s for s in statuses if s in (NORMAL, WATCH, REFER)]
    n = len(screened)
    if n == 0:
        return {"status": INSUFFICIENT, "n": 0, "watch_share": None, "refer_count": 0}
    refer = sum(1 for s in screened if s == REFER)
    flagged = sum(1 for s in screened if s in (WATCH, REFER))
    share = flagged / n
    if refer >= 1 or share >= t.pond_refer_share:
        status = REFER
    elif share >= t.pond_watch_share:
        status = WATCH
    else:
        status = NORMAL
    return {"status": status, "n": n, "watch_share": round(share, 4), "refer_count": refer}
