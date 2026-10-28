"""Weight estimation regression (paper Chapter 3, Regression Models).

W = b0 + b1 L + b2 A                                   (linear baseline)
W = b0 + b1 L + b2 A + b3 L^2 + b4 A^2 + b5 L*A          (degree 2 at most)

Terms are chosen by backward elimination, models are compared with grouped
cross-validation, and the degree-2 model is kept only when it lowers the
validation RMSE clearly (by at least 5 %). Before any fit, a provisional
length-weight curve W = a * L^b is used and labeled as such.
"""

import math

import numpy as np

from .thresholds import Thresholds

LINEAR_TERMS = ["L", "A"]
POLY_TERMS = ["L", "A", "L2", "A2", "LA"]
CLEARLY_BETTER = 0.95  # poly kept only if its CV RMSE <= 95 % of the linear one


def provisional_model(t=Thresholds()):
    return {"kind": "power", "a": t.lw_a, "b": t.lw_b, "label": "Provisional length–weight curve (not fitted)"}


def _term(name, L, A):
    return {"L": L, "A": A, "L2": L * L, "A2": A * A, "LA": L * A}[name]


def predict(model, L, A):
    if model is None or L is None or L <= 0:
        return None
    if model["kind"] == "power":
        return float(model["a"]) * float(L) ** float(model["b"])
    if A is None and any("A" in term for term in model["terms"]):
        return None
    w = model["intercept"] + sum(c * _term(n, L, A or 0.0) for n, c in zip(model["terms"], model["coefs"]))
    return max(w, 0.0)


def _design(rows, terms):
    return np.column_stack([np.ones(len(rows))] + [[_term(n, r["L"], r["A"]) for r in rows] for n in terms])


def _ols(X, y):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def _t_values(X, y, beta):
    n, p = X.shape
    resid = y - X @ beta
    dof = max(n - p, 1)
    sigma2 = float(resid @ resid) / dof
    try:
        cov = sigma2 * np.linalg.pinv(X.T @ X)
        se = np.sqrt(np.clip(np.diag(cov), 1e-18, None))
    except np.linalg.LinAlgError:
        return np.zeros(p)
    return np.abs(beta / se)


def backward_eliminate(rows, terms, t_crit=2.0):
    """Drop the weakest term (smallest |t|, i.e. p > ~0.05) one at a time."""
    terms = list(terms)
    y = np.asarray([r["W"] for r in rows], float)
    while len(terms) > 1:
        X = _design(rows, terms)
        tv = _t_values(X, y, _ols(X, y))[1:]
        worst = int(np.argmin(tv))
        if tv[worst] >= t_crit:
            break
        terms.pop(worst)
    return terms


def metrics(y_true, y_pred):
    y, p = np.asarray(y_true, float), np.asarray(y_pred, float)
    err = p - y
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    rel = np.abs(err) / np.where(y == 0, np.nan, y)
    return {"n": int(len(y)),
            "r2": round(1 - float(np.sum(err ** 2)) / ss_tot, 4) if ss_tot > 0 else None,
            "rmse": round(math.sqrt(float(np.mean(err ** 2))), 3),
            "mae": round(float(np.mean(np.abs(err))), 3),
            "mare": round(float(np.nanmean(rel)) * 100, 2),
            "mxae": round(float(np.max(np.abs(err))), 3),
            "mxre": round(float(np.nanmax(rel)) * 100, 2)}


def _fit(rows, terms):
    y = np.asarray([r["W"] for r in rows], float)
    beta = _ols(_design(rows, terms), y)
    return {"kind": "ols", "terms": terms, "intercept": float(beta[0]), "coefs": [float(b) for b in beta[1:]]}


def grouped_cv(rows, terms):
    groups = sorted({r["group"] for r in rows})
    if len(groups) < 2:  # fall back to 5-fold by position
        groups = list(range(5))
        rows = [{**r, "group": i % 5} for i, r in enumerate(rows)]
    y_true, y_pred = [], []
    for g in groups:
        train = [r for r in rows if r["group"] != g]
        test = [r for r in rows if r["group"] == g]
        if not test or len(train) <= len(terms) + 1:
            continue
        m = _fit(train, terms)
        y_true += [r["W"] for r in test]
        y_pred += [predict(m, r["L"], r["A"]) for r in test]
    return metrics(y_true, y_pred)


def fit_models(rows, t=Thresholds()):
    rows = [r for r in rows if r.get("L") and r.get("A") and r.get("W")]
    if len(rows) < t.weight_fit_min_fish:
        raise ValueError(f"Need at least {t.weight_fit_min_fish} fish with scale weight and image length/area "
                         f"(have {len(rows)}).")
    out = {}
    for name, terms in (("linear", LINEAR_TERMS), ("poly", POLY_TERMS)):
        kept = backward_eliminate(rows, terms)
        model = _fit(rows, kept)
        y = [r["W"] for r in rows]
        model.update(label="Linear regression (baseline)" if name == "linear" else "Polynomial regression (degree 2)",
                     train=metrics(y, [predict(model, r["L"], r["A"]) for r in rows]),
                     cv=grouped_cv(rows, kept),
                     range_L=[round(min(r["L"] for r in rows), 2), round(max(r["L"] for r in rows), 2)])
        out[name] = model
    lin, pol = out["linear"]["cv"]["rmse"], out["poly"]["cv"]["rmse"]
    out["selected"] = "poly" if pol <= CLEARLY_BETTER * lin else "linear"
    out["n"] = len(rows)
    out["groups"] = len({r["group"] for r in rows})
    return out
