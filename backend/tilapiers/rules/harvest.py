"""Harvest Readiness rules (paper Figure 11, steps 4-6).

The status describes the pond at the sampling round. The growth curve is only
fitted over the observed days and never used as a harvest-date forecast. The
harvest decision stays with the caretaker and the technician.
"""

import math

import numpy as np

from .thresholds import Thresholds

READY = "Ready"
SIZE_REVIEW = "Size reached - health review needed"
APPROACHING = "Approaching"
NOT_READY = "Not Ready"
INSUFFICIENT = "Insufficient data"


def sgr(w1, w2, days):
    """Specific growth rate (%/day) = 100 * (ln W2 - ln W1) / days."""
    if not w1 or not w2 or not days or days <= 0 or w1 <= 0 or w2 <= 0:
        return None
    return 100.0 * (math.log(w2) - math.log(w1)) / days


def size_stats(weights_g, t=Thresholds()):
    w = [float(x) for x in weights_g if x is not None]
    if not w:
        return {"n": 0, "mean_weight_g": None, "share_at_target": None, "cv": None}
    arr = np.asarray(w)
    mean = float(arr.mean())
    cv = float(arr.std(ddof=1) / mean) if len(arr) > 1 and mean > 0 else 0.0
    return {"n": len(w), "mean_weight_g": round(mean, 2),
            "share_at_target": round(float(np.mean(arr >= t.target_weight_g)), 4), "cv": round(cv, 4)}


def growth_trend(points, t=Thresholds()):
    """``points`` = [(days_of_culture, mean_weight_g)]. Degree-2 curve from N rounds, else SGR."""
    pts = sorted((float(d), float(w)) for d, w in points if d is not None and w)
    intervals = [{"from_day": d0, "to_day": d1, "sgr": sgr(w0, w1, d1 - d0)}
                 for (d0, w0), (d1, w1) in zip(pts, pts[1:])]
    overall = sgr(pts[0][1], pts[-1][1], pts[-1][0] - pts[0][0]) if len(pts) >= 2 else None
    poly = None
    if len(pts) >= t.growth_poly_min_rounds:
        x = np.asarray([p[0] for p in pts])
        y = np.asarray([p[1] for p in pts])
        coef = np.polyfit(x, y, 2)
        fit = np.polyval(coef, x)
        ss_res = float(np.sum((y - fit) ** 2))
        ss_tot = float(np.sum((y - y.mean()) ** 2))
        slope_end = float(2 * coef[0] * x.max() + coef[1])
        grid = np.linspace(x.min(), x.max(), 25)
        poly = {"degree": 2, "coefficients": [round(float(c), 6) for c in coef],
                "r2": round(1 - ss_res / ss_tot, 4) if ss_tot > 0 else None,
                "slope_g_per_day": round(slope_end, 3),
                "curve": [[round(float(d), 1), round(float(np.polyval(coef, d)), 2)] for d in grid]}
    return {"method": "polynomial" if poly else "sgr",
            "latest_sgr": round(overall, 4) if overall is not None else None,
            "intervals": intervals, "poly": poly, "n_rounds": len(pts), "points": pts}


def readiness(weights_g, mean_k, days_of_culture, growth, pond_health, t=Thresholds()):
    size = size_stats(weights_g, t)
    if size["n"] == 0:
        return {"status": INSUFFICIENT, "criteria": [], "met": 0, "size": size,
                "notes": ["No fish with an estimated weight in this round."]}
    share, cv, doc = size["share_at_target"], size["cv"], days_of_culture
    g_sgr = growth.get("latest_sgr") if growth else None
    poly = growth.get("poly") if growth else None
    if poly:
        growth_ok, growth_val = poly["slope_g_per_day"] > 0, f"curve slope {poly['slope_g_per_day']:.2f} g/day"
    elif g_sgr is not None:
        growth_ok, growth_val = g_sgr >= t.min_sgr, f"{g_sgr:.2f} %/day"
    else:
        growth_ok, growth_val = False, "needs 2 rounds"
    criteria = [
        {"key": "share", "label": f"Fish at or above {t.target_weight_g:g} g", "value": f"{share:.0%}",
         "target": f">= {t.ready_share:.0%}", "passed": share >= t.ready_share},
        {"key": "cv", "label": "Weight uniformity (CV)", "value": f"{cv:.0%}",
         "target": f"<= {t.max_cv:.0%}", "passed": cv <= t.max_cv},
        {"key": "growth", "label": "Growth", "value": growth_val,
         "target": "curve rising" if poly else f"SGR >= {t.min_sgr:g} %/day", "passed": growth_ok},
        {"key": "k", "label": "Mean condition factor K",
         "value": f"{mean_k:.2f}" if mean_k is not None else "not measured",
         "target": f"{t.k_min:g} to {t.k_max:g}", "passed": mean_k is not None and t.k_min <= mean_k <= t.k_max},
        {"key": "doc", "label": "Days of culture", "value": f"{doc:.0f}" if doc is not None else "-",
         "target": f">= {t.culture_days_min:.0f} (usual {t.culture_days_min:.0f}-{t.culture_days_max:.0f})",
         "passed": doc is not None and doc >= t.culture_days_min},
    ]
    met = sum(1 for c in criteria if c["passed"])
    if met == len(criteria):
        status = READY if pond_health == "Normal" else SIZE_REVIEW
    elif share >= t.approaching_share and met >= 3:
        status = APPROACHING
    else:
        status = NOT_READY
    notes = []
    if status == SIZE_REVIEW:
        notes.append(f"Readiness cutoffs met, but pond health is {pond_health}: health review needed before harvest.")
    if doc is not None and doc > t.culture_days_max:
        notes.append("Days of culture exceed the usual culture period.")
    notes.append("The status describes the pond at this round. It is not a harvest-date forecast; "
                 "the harvest decision stays with the caretaker and the technician.")
    return {"status": status, "criteria": criteria, "met": met, "size": size, "notes": notes}
