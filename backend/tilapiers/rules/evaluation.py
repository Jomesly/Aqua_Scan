"""Evaluation metrics: status agreement with the technician and measurement error."""

import math

import numpy as np


def agreement(pairs, labels):
    """``pairs`` = [(system, technician)]. Linear-weighted Cohen's kappa for ordered statuses."""
    pairs = [(s, t) for s, t in pairs if s in labels and t in labels]
    k = len(labels)
    idx = {lab: i for i, lab in enumerate(labels)}
    m = np.zeros((k, k))
    for s, t in pairs:
        m[idx[s], idx[t]] += 1
    n = int(m.sum())
    if n == 0:
        return {"n": 0, "accuracy": None, "kappa_w": None, "matrix": m.astype(int).tolist(), "labels": labels}
    o = m / n
    e = np.outer(o.sum(axis=1), o.sum(axis=0))
    w = np.abs(np.subtract.outer(np.arange(k), np.arange(k))) / max(k - 1, 1)
    denom = float((w * e).sum())
    kappa = 1.0 - float((w * o).sum()) / denom if denom > 0 else 1.0
    return {"n": n, "accuracy": round(float(np.trace(m)) / n, 4), "kappa_w": round(kappa, 4),
            "matrix": m.astype(int).tolist(), "labels": labels}


def refer_recall(pairs, refer="Refer to technician"):
    tech_refer = [(s, t) for s, t in pairs if t == refer]
    if not tech_refer:
        return None
    return round(sum(1 for s, _ in tech_refer if s == refer) / len(tech_refer), 4)


def error_stats(pairs):
    """``pairs`` = [(estimate, reference)]."""
    pairs = [(float(a), float(b)) for a, b in pairs if a is not None and b is not None]
    if not pairs:
        return {"n": 0, "mae": None, "rmse": None, "mare": None}
    err = [a - b for a, b in pairs]
    rel = [abs(a - b) / b for a, b in pairs if b]
    return {"n": len(pairs), "mae": round(sum(abs(x) for x in err) / len(err), 3),
            "rmse": round(math.sqrt(sum(x * x for x in err) / len(err)), 3),
            "mare": round(100 * sum(rel) / len(rel), 2) if rel else None}
