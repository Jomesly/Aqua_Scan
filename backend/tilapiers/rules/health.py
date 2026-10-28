"""Fish Health Monitoring rules: condition factor, the Fish Condition Index (FCI)
regression, and the rule-based pond health status.

The FCI estimates the technician's fish condition score (1 = poor, 5 = excellent)
from image-derived indicators and condition factor using multiple linear
regression, with degree-2 terms at most. It screens visible indicators only and
never diagnoses disease.
"""

import numpy as np

from .thresholds import Thresholds

FEATURES = [
    "condition_factor",
    "gill_color_index",
    "skin_color_index",
    "fin_integrity",
    "eye_clarity",
    "body_shape",
]

FEATURE_LABELS = {
    "condition_factor": "Condition factor (K)",
    "gill_color_index": "Gill color index",
    "skin_color_index": "Skin color index",
    "fin_integrity": "Fin integrity ratio",
    "eye_clarity": "Eye clarity index",
    "body_shape": "Body shape ratio",
}

# Indicator groups compared in the study (objective 2b).
FEATURE_GROUPS = {
    "k_only": ["condition_factor"],
    "k_color": ["condition_factor", "gill_color_index", "skin_color_index"],
    "full": FEATURES,
}

GROUP_LABELS = {
    "k_only": "Condition factor only",
    "k_color": "+ color indicators",
    "full": "+ fin, eye and shape indicators",
}

SCORE_MIN, SCORE_MAX = 1.0, 5.0
MIN_FIT_ROWS = 8

# Hand-set starting coefficients so the prototype produces plausible values
# before any technician-scored data exists. Replaced by a fitted model as soon as
# enough scored fish are recorded (Evaluation page -> Fit model).
DEFAULT_FCI_MODEL = {
    "name": "default",
    "source": "uncalibrated starting coefficients (no technician data yet)",
    "features": FEATURES,
    "poly_features": [],
    "intercept": -1.0,
    "coefs": {
        "condition_factor": 1.2,
        "gill_color_index": 1.5,
        "skin_color_index": 1.0,
        "fin_integrity": 1.2,
        "eye_clarity": 0.8,
        "body_shape": 0.0,
    },
    "means": {
        "condition_factor": 1.6, "gill_color_index": 0.6, "skin_color_index": 0.65,
        "fin_integrity": 0.85, "eye_clarity": 0.6, "body_shape": 0.37,
    },
    "n": 0,
    "metrics": None,
}


def condition_factor(weight_g, length_cm):
    """Fulton's condition factor K = 100 * W(g) / L(cm)^3."""
    if weight_g is None or not length_cm or length_cm <= 0:
        return None
    return 100.0 * float(weight_g) / float(length_cm) ** 3


def _terms(model):
    return list(model["features"]) + [f"{f}^2" for f in model.get("poly_features", [])]


def _row_vector(model, indicators):
    values = {}
    for f in model["features"]:
        v = indicators.get(f)
        if v is None:
            if f == "condition_factor":
                return None  # K comes from scale + ruler; never imputed
            v = model.get("means", {}).get(f)
            if v is None:
                return None
        values[f] = float(v)
    vec = [values[f] for f in model["features"]]
    vec += [values[f] ** 2 for f in model.get("poly_features", [])]
    return vec


def predict_fci(model, indicators):
    vec = _row_vector(model, indicators)
    if vec is None:
        return None
    coefs = [model["coefs"][t] for t in _terms(model)]
    raw = model["intercept"] + float(np.dot(coefs, vec))
    return round(float(np.clip(raw, SCORE_MIN, SCORE_MAX)), 2)


def _metrics(y, yhat):
    y = np.asarray(y, float)
    yhat = np.asarray(yhat, float)
    resid = y - yhat
    ss_res = float(np.sum(resid**2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return {
        "r2": round(1 - ss_res / ss_tot, 4) if ss_tot > 0 else None,
        "rmse": round(float(np.sqrt(np.mean(resid**2))), 4),
        "mae": round(float(np.mean(np.abs(resid))), 4),
        "n": int(len(y)),
    }


def _design(rows, features, poly_features):
    X = []
    for r in rows:
        vec = [float(r[f]) for f in features] + [float(r[f]) ** 2 for f in poly_features]
        X.append([1.0] + vec)
    return np.asarray(X, float)


def _ols(X, y):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def _usable(rows, features):
    return [r for r in rows if r.get("technician_score") is not None and all(r.get(f) is not None for f in features)]


def fit_fci_model(rows, features, poly_features=()):
    """Fit OLS of technician score on the given indicators.

    Cross-validation is grouped so fish from the same pond (or, with a single
    pond, the same sampling round) never appear in both train and test folds.
    """
    poly_features = [f for f in poly_features if f in features]
    rows = _usable(rows, features)
    if len(rows) < max(MIN_FIT_ROWS, len(features) + len(poly_features) + 2):
        raise ValueError(f"Need at least {MIN_FIT_ROWS} technician-scored fish with all indicators; have {len(rows)}.")

    y = np.asarray([float(r["technician_score"]) for r in rows])
    X = _design(rows, features, poly_features)
    beta = _ols(X, y)
    train_pred = np.clip(X @ beta, SCORE_MIN, SCORE_MAX)

    ponds = sorted({r.get("pond_id") for r in rows})
    if len(ponds) >= 2:
        key, method = "pond_id", "leave-one-pond-out"
    else:
        key, method = "round_id", "leave-one-round-out"
    groups = np.asarray([r.get(key) for r in rows])
    cv_pred = np.full(len(rows), np.nan)
    for g in np.unique(groups):
        test = groups == g
        if test.all() or (~test).sum() < X.shape[1]:
            continue
        b = _ols(X[~test], y[~test])
        cv_pred[test] = np.clip(X[test] @ b, SCORE_MIN, SCORE_MAX)
    ok = ~np.isnan(cv_pred)
    cv = _metrics(y[ok], cv_pred[ok]) if ok.sum() >= 3 else {"r2": None, "rmse": None, "mae": None, "n": int(ok.sum())}
    cv["method"] = method
    cv["groups"] = int(len(np.unique(groups)))

    terms = list(features) + [f"{f}^2" for f in poly_features]
    return {
        "name": "fitted",
        "source": f"OLS fitted on {len(rows)} technician-scored fish",
        "features": list(features),
        "poly_features": list(poly_features),
        "intercept": round(float(beta[0]), 6),
        "coefs": {t: round(float(b), 6) for t, b in zip(terms, beta[1:])},
        "means": {f: round(float(np.mean([r[f] for r in rows])), 6) for f in features},
        "n": len(rows),
        "metrics": {"train": _metrics(y, train_pred), "cv": cv},
    }


def compare_feature_groups(rows):
    """What each group of indicators adds (objective 2b)."""
    out = []
    for name, feats in FEATURE_GROUPS.items():
        try:
            m = fit_fci_model(rows, feats)
            out.append({"group": name, "label": GROUP_LABELS[name], "features": feats,
                        "train": m["metrics"]["train"], "cv": m["metrics"]["cv"], "error": None})
        except ValueError as exc:
            out.append({"group": name, "label": GROUP_LABELS[name], "features": feats,
                        "train": None, "cv": None, "error": str(exc)})
    return out


def health_status(fcis, mean_k, env_critical, thresholds=Thresholds()):
    """Rule-based pond health status at a sampling round.

    Normal / Watch / Refer to technician, from the share of sampled fish whose
    FCI is below the flag threshold, mean condition factor, and whether the
    environment was Critical in the interval before the round.
    """
    t = thresholds
    scored = [f for f in fcis if f is not None]
    if not scored:
        return {"status": "Insufficient data", "share_flagged": None, "n_scored": 0,
                "n_flagged": 0, "reasons": ["No fish with a condition index in this round."]}

    flagged = sum(1 for f in scored if f < t.fci_flag_below)
    share = flagged / len(scored)
    reasons = []
    status = "Normal"

    if share >= t.health_refer_share:
        status = "Refer to technician"
        reasons.append(f"{flagged} of {len(scored)} fish ({share:.0%}) have a condition index below {t.fci_flag_below:g}.")
    else:
        if share >= t.health_watch_share:
            status = "Watch"
            reasons.append(f"{flagged} of {len(scored)} fish ({share:.0%}) have a condition index below {t.fci_flag_below:g}.")
        if mean_k is not None and mean_k < t.condition_factor_low:
            status = "Watch"
            reasons.append(f"Mean condition factor {mean_k:.2f} is below {t.condition_factor_low:g}.")
        if env_critical:
            status = "Watch"
            reasons.append("The environment reached Critical before this sampling round.")

    if status == "Normal":
        reasons.append(f"{flagged} of {len(scored)} fish flagged; condition and environment within limits.")
    if len(scored) < t.min_fish_per_round:
        reasons.append(f"Only {len(scored)} fish with a condition index (recommended at least {t.min_fish_per_round}); "
                       "treat this status with caution.")

    return {"status": status, "share_flagged": round(share, 4), "n_scored": len(scored),
            "n_flagged": flagged, "reasons": reasons}
