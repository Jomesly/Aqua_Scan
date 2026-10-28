"""Harvest Readiness rules: Not Ready / Approaching / Ready per pond per round.

The status describes the pond as it is at the sampling round. Growth regression
is fitted only over the observed days of culture and never extrapolated to
forecast a harvest date. The system supports the harvest decision; it does not
make it.
"""

import math

import numpy as np

from .thresholds import Thresholds

READY = "Ready"
SIZE_REVIEW = "Size reached - health review needed"
APPROACHING = "Approaching"
NOT_READY = "Not Ready"
INSUFFICIENT = "Insufficient data"


def specific_growth_rate(w1, w2, days):
    """SGR (% body weight per day) = 100 * (ln W2 - ln W1) / days."""
    if not w1 or not w2 or not days or days <= 0 or w1 <= 0 or w2 <= 0:
        return None
    return 100.0 * (math.log(w2) - math.log(w1)) / days


def round_size_stats(weights_g, thresholds=Thresholds()):
    w = [float(x) for x in weights_g if x is not None]
    if not w:
        return {"n": 0, "mean_weight_g": None, "share_at_target": None, "weight_cv": None}
    arr = np.asarray(w)
    mean = float(arr.mean())
    cv = float(arr.std(ddof=1) / mean) if len(arr) > 1 and mean > 0 else 0.0
    return {
        "n": len(w),
        "mean_weight_g": round(mean, 2),
        "share_at_target": round(float(np.mean(arr >= thresholds.target_weight_g)), 4),
        "weight_cv": round(cv, 4),
    }


def growth_trend(points, thresholds=Thresholds()):
    """``points`` = [(days_of_culture, mean_weight_g)] sorted by day.

    Degree-2 polynomial of mean weight on days of culture when at least
    ``growth_poly_min_rounds`` rounds exist; otherwise specific growth rate only.
    """
    pts = sorted((float(d), float(w)) for d, w in points if d is not None and w)
    sgrs = []
    for (d0, w0), (d1, w1) in zip(pts, pts[1:]):
        sgrs.append({"from_day": d0, "to_day": d1, "sgr": specific_growth_rate(w0, w1, d1 - d0)})
    latest = sgrs[-1]["sgr"] if sgrs else None

    poly = None
    if len(pts) >= thresholds.growth_poly_min_rounds:
        x = np.asarray([p[0] for p in pts])
        y = np.asarray([p[1] for p in pts])
        coef = np.polyfit(x, y, 2)
        fit = np.polyval(coef, x)
        ss_res = float(np.sum((y - fit) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        grid = np.linspace(x.min(), x.max(), 25)
        poly = {
            "degree": 2,
            "coefficients": [round(float(c), 6) for c in coef],  # a*d^2 + b*d + c
            "r2": round(1 - ss_res / ss_tot, 4) if ss_tot > 0 else None,
            "curve": [[round(float(d), 2), round(float(np.polyval(coef, d)), 2)] for d in grid],
        }

    return {
        "method": "polynomial" if poly else "sgr",
        "latest_sgr": round(latest, 4) if latest is not None else None,
        "sgr_by_interval": [{**s, "sgr": round(s["sgr"], 4) if s["sgr"] is not None else None} for s in sgrs],
        "poly": poly,
        "n_rounds": len(pts),
    }


def harvest_readiness(weights_g, mean_k, days_of_culture, health, recent_critical, growth,
                      thresholds=Thresholds()):
    t = thresholds
    size = round_size_stats(weights_g, t)
    if size["n"] == 0:
        return {"status": INSUFFICIENT, "criteria": [], "size": size, "notes": ["No weighed fish in this round."]}

    share = size["share_at_target"]
    cv = size["weight_cv"]
    size_ok = share >= t.ready_share_at_target
    uniform_ok = cv <= t.max_weight_cv
    health_ok = health == "Normal" and not recent_critical
    k_ok = mean_k is not None and mean_k >= t.condition_factor_low
    doc = days_of_culture
    doc_ok = doc is not None and doc >= t.culture_days_min
    sgr = growth.get("latest_sgr") if growth else None

    criteria = [
        {"key": "size", "label": f"Fish at or above {t.target_weight_g:g} g",
         "value": f"{share:.0%}", "target": f">= {t.ready_share_at_target:.0%}", "passed": size_ok},
        {"key": "uniformity", "label": "Weight uniformity (CV)",
         "value": f"{cv:.2f}", "target": f"<= {t.max_weight_cv:.2f}", "passed": uniform_ok},
        {"key": "condition", "label": "Mean condition factor (K)",
         "value": f"{mean_k:.2f}" if mean_k is not None else "-", "target": f">= {t.condition_factor_low:g}", "passed": k_ok},
        {"key": "doc", "label": "Days of culture",
         "value": f"{doc:.0f}" if doc is not None else "-",
         "target": f"{t.culture_days_min:.0f}-{t.culture_days_max:.0f} usual", "passed": doc_ok},
        {"key": "growth", "label": "Specific growth rate",
         "value": f"{sgr:.2f} %/day" if sgr is not None else "needs 2 rounds", "target": "descriptive", "passed": None},
        {"key": "health", "label": "Health clearance",
         "value": health + ("; Critical temperature in last %g days" % t.recent_critical_days if recent_critical else ""),
         "target": "Normal, no recent Critical", "passed": health_ok},
    ]

    if size_ok and uniform_ok:
        status = READY if health_ok else SIZE_REVIEW
    elif share >= t.approaching_share_at_target or doc_ok:
        status = APPROACHING
    else:
        status = NOT_READY

    notes = []
    if size["n"] < t.min_fish_per_round:
        notes.append(f"Only {size['n']} fish sampled (recommended at least {t.min_fish_per_round}); readiness is noisy.")
    if doc is not None and doc > t.culture_days_max:
        notes.append("Days of culture exceed the usual culture period.")
    notes.append("Status describes the pond at this round; it is not a harvest-date forecast.")

    return {"status": status, "criteria": criteria, "size": size, "notes": notes}
