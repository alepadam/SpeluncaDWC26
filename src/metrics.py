"""Evaluation metrics (methodology §5) and the history-match loss (SRQ2)."""

from __future__ import annotations

import numpy as np

from .utils import PHASES


def rmse(y, yhat) -> float:
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    return float(np.sqrt(np.mean((y - yhat) ** 2)))


def mape(y, yhat, min_abs: float = 1e-9) -> float:
    """Percent error, skipping points where |y| <= min_abs (e.g. water before breakthrough)."""
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    m = np.abs(y) > min_abs
    return float(100.0 * np.mean(np.abs((y[m] - yhat[m]) / y[m]))) if m.any() else float("nan")


def r2(y, yhat) -> float:
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    ss_tot = np.sum((y - y.mean()) ** 2)
    return float(1.0 - np.sum((y - yhat) ** 2) / ss_tot) if ss_tot > 0 else float("nan")


def endpoint_rel_error(y, yhat) -> float:
    """Relative error of the last value (e.g. cumulative at the end of the horizon)."""
    y, yhat = np.asarray(y, float), np.asarray(yhat, float)
    return float(abs(y[-1] - yhat[-1]) / abs(y[-1])) if y[-1] != 0 else float("nan")


def coverage(y, lo, hi) -> float:
    """Share of actual values inside [lo, hi] (target ~0.8 for a P10–P90 band)."""
    y, lo, hi = (np.asarray(a, float) for a in (y, lo, hi))
    return float(np.mean((y >= lo) & (y <= hi)))


def sigma_matrix(obs: dict, sigma_rel: float, floor_frac: float) -> dict:
    """sigma[t,k] = max(sigma_rel * |obs|, floor_frac * max|obs_k|) per phase k."""
    out = {}
    for k in PHASES:
        o = np.asarray(obs[k], float)
        floor = floor_frac * max(float(np.max(np.abs(o))), 1e-9)
        out[k] = np.maximum(sigma_rel * np.abs(o), floor)
    return out


def misfit(obs: dict, sim: dict, sigma: dict, weights: dict, sim_sd: dict | None = None) -> np.ndarray:
    """Weighted least-squares misfit, averaged over dates and summed over phases (formula F23).

        O = (1/T) * sum_k w_k * sum_t (obs[t,k] - sim[t,k])^2 / (sigma[t,k]^2 + sd[t,k]^2)

    sim may hold one curve per phase (shape T) or many (shape N x T) -> returns a scalar or N values.
    sim_sd (optional, same shape as sim) adds proxy uncertainty to the error, so the optimiser does not
    trust the proxy more than it deserves.
    """
    total, T = 0.0, None
    for k in PHASES:
        o = np.asarray(obs[k], float)
        s = np.asarray(sim[k], float)
        T = o.size
        var = sigma[k] ** 2 + (np.asarray(sim_sd[k], float) ** 2 if sim_sd is not None else 0.0)
        total = total + weights.get(k, 1.0) * np.sum((o - s) ** 2 / var, axis=-1)
    return np.asarray(total / T)


def glue_weights(scores) -> np.ndarray:
    """Tempered likelihood weights w ∝ exp(-O/2) (formula F24), computed stably."""
    s = np.asarray(scores, float)
    w = np.exp(-(s - np.nanmin(s)) / 2.0)
    w[~np.isfinite(w)] = 0.0
    return w / w.sum()
