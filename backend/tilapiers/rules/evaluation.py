"""Evaluation metrics reported to the thesis panel. Descriptive only: no claims of
statistical significance are made anywhere."""

from collections import Counter

import numpy as np


def calibration_metrics(pairs):
    """``pairs`` = [(probe_c, reference_c)]. Probe error against a reference thermometer."""
    pairs = [(float(p), float(r)) for p, r in pairs if p is not None and r is not None]
    if not pairs:
        return {"n": 0, "mae": None, "bias": None, "rmse": None, "max_abs": None}
    err = np.asarray([p - r for p, r in pairs])
    return {
        "n": len(pairs),
        "mae": round(float(np.mean(np.abs(err))), 3),
        "bias": round(float(np.mean(err)), 3),
        "rmse": round(float(np.sqrt(np.mean(err**2))), 3),
        "max_abs": round(float(np.max(np.abs(err))), 3),
    }


def agreement(pairs, labels):
    """``pairs`` = [(system_label, technician_label)]. Accuracy, Cohen's kappa, confusion."""
    pairs = [(s, t) for s, t in pairs if s and t]
    n = len(pairs)
    confusion = {t: {s: 0 for s in labels} for t in labels}
    for s, t in pairs:
        if t in confusion and s in confusion[t]:
            confusion[t][s] += 1
    if n == 0:
        return {"n": 0, "accuracy": None, "kappa": None, "labels": labels, "confusion": confusion}
    po = sum(1 for s, t in pairs if s == t) / n
    cs = Counter(s for s, _ in pairs)
    ct = Counter(t for _, t in pairs)
    pe = sum(cs[k] * ct[k] for k in set(cs) | set(ct)) / (n * n)
    kappa = (po - pe) / (1 - pe) if pe < 1 else None
    return {"n": n, "accuracy": round(po, 4), "kappa": round(kappa, 4) if kappa is not None else None,
            "labels": labels, "confusion": confusion}


def stress_association(rows):
    """OLS of round mean FCI on hours outside the band in the preceding interval,
    sampling rounds pooled across ponds with pond as a fixed-effect grouping factor.

    ``rows`` = [{"pond_id", "x", "y"}].
    """
    rows = [r for r in rows if r.get("x") is not None and r.get("y") is not None]
    n = len(rows)
    ponds = sorted({r["pond_id"] for r in rows})
    if n < len(ponds) + 2:
        return {"n": n, "n_ponds": len(ponds), "slope": None, "r2": None,
                "note": "Not enough sampling rounds with both stress exposure and condition index."}
    X = []
    for r in rows:
        dummies = [1.0 if r["pond_id"] == p else 0.0 for p in ponds[1:]]
        X.append([1.0, float(r["x"])] + dummies)
    X = np.asarray(X)
    y = np.asarray([float(r["y"]) for r in rows])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    fit = X @ beta
    ss_res = float(np.sum((y - fit) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return {
        "n": n, "n_ponds": len(ponds),
        "slope": round(float(beta[1]), 5),
        "r2": round(1 - ss_res / ss_tot, 4) if ss_tot > 0 else None,
        "note": "Descriptive association only; handling, stocking density and feed are not controlled.",
        "points": [{"pond_id": r["pond_id"], "x": r["x"], "y": r["y"]} for r in rows],
    }
