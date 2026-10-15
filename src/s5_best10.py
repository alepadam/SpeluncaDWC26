"""Step 5 — Pick the best 10 forecast cases (SRQ6) — deck slide 31: "Pick the best 10 forecast cases".

  1. Candidates = proxy-optimized parameter sets from step 3, ranked by history misfit.
  2. Greedy pick of 10, best misfit first, at least `min_distance` apart in scaled parameter space,
     so the 10 cases are distinct history-matched realizations rather than near-copies of one point.
  3. Each pick: proxy history curves -> (optionally anchored to observed 2008 cumulatives) ->
     physics-constrained forecast to 2028 (step 4).
  4. Uncertainty: P90 / P50 / P10 (low / mid / high) across the 10 and across the weighted posterior;
     spread compared with all 100 unmatched cases (did matching narrow the forecast?), and the same 10 cases
     forecast with the other method (model-form uncertainty).
  5. Business view (deck: "evaluate if the field will make money"): remaining oil 2008-2028, end rates,
     water cut — per realization.
  6. Whole-pipeline backtest against the observed field (match <= 2004, forecast 2004-2008).

Outputs (outputs/tables/): srq6_best10.csv, srq6_best10_forecasts.csv (long format),
                           srq6_spread_2028.csv, srq6_business.csv, srq6_pipeline_backtest.csv
         (outputs/figures/): srq6_forecast_fan.png
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import qmc

from .metrics import coverage, glue_weights, misfit, sigma_matrix
from .plotting import plt
from .s1_prepare import x_cols
from .s2_proxy import unstack
from .s4_forecast import METHODS, _ar_state, fit_forecaster, forecast_from_fit, roll_ar
from .utils import PHASES, UNITS, get_logger, weighted_quantile


def pick_diverse(X: np.ndarray, scores: np.ndarray, n: int, min_dist: float) -> list[int]:
    """Indices of n candidates: best score first, each at least min_dist from those already picked.
    If fewer than n satisfy the distance, the remaining slots take the next best scores."""
    order = list(np.argsort(scores))
    chosen: list[int] = []
    for i in order:
        if all(np.linalg.norm(X[i] - X[j]) >= min_dist for j in chosen):
            chosen.append(i)
        if len(chosen) == n:
            return chosen
    for i in order:
        if i not in chosen:
            chosen.append(i)
        if len(chosen) == n:
            break
    return chosen


def forecast_param_sets(X: np.ndarray, proxy, hist_index: pd.DatetimeIndex, f_dates: pd.DatetimeIndex,
                        cfg: dict, wor_fallback, water_model: str, anchor: dict | None = None,
                        fit_start=None, until=None, method: str = "decline", ar_models=None) -> dict[str, np.ndarray]:
    """Proxy history + forecast for each row of X. Returns phase -> (N x len(f_dates)) cumulatives.

    anchor (phase -> observed cumulative at the end of history): shifts each history curve by a constant
    so it ends on the observed value; rates (and therefore every fitted trend) are unchanged.
    fit_start / until: fit window and end of usable history (used by the backtest).
    method: "decline" (physics-constrained) or "ml_autoregressive" (needs ar_models).
    """
    cf, rs0 = cfg["forecast"], cfg["gas"]["rs_expected"]
    fit_start = cf["fit_window_start"] if fit_start is None else fit_start
    X = np.atleast_2d(X)
    Y = unstack(proxy.predict(X), len(hist_index))
    keep = hist_index <= pd.Timestamp(until) if until is not None else np.ones(len(hist_index), bool)
    histories = []
    for i in range(len(X)):
        curves = {k: pd.Series(Y[k][i][keep], index=hist_index[keep]) for k in PHASES}
        if anchor is not None:
            curves = {k: v + (anchor[k] - v.iloc[-1]) for k, v in curves.items()}
        histories.append(curves)
    if method == "ml_autoregressive":
        if ar_models is None:
            raise ValueError("method 'ml_autoregressive' needs ar_models")
        return roll_ar(ar_models, [_ar_state(h, fit_start, rs0) for h in histories], X, f_dates)
    if method != "decline":
        raise ValueError(f"Unknown forecast method {method!r}")
    out = {k: np.empty((len(X), len(f_dates))) for k in PHASES}
    for i, curves in enumerate(histories):
        fit = fit_forecaster(curves, fit_start, cf, rs0, wor_fallback)
        p = forecast_from_fit(fit, f_dates, cf["wor_max"], water_model)
        for k in PHASES:
            out[k][i] = p[k]
    return out


def end_rates(cum_row: dict, f_dates: pd.DatetimeIndex) -> dict:
    days = (f_dates[-1] - f_dates[-2]).days
    q = {k: (cum_row[k][-1] - cum_row[k][-2]) / days for k in PHASES}
    wc = q["water"] / (q["water"] + q["oil"]) if (q["water"] + q["oil"]) > 0 else np.nan
    return {"oil_rate_2028_stb_d": q["oil"], "gas_rate_2028_mscf_d": q["gas"],
            "water_rate_2028_stb_d": q["water"], "water_cut_2028": wc}


def pipeline_backtest(cfg: dict, state: dict) -> pd.DataFrame:
    """Backtest of the WHOLE method against the observed field: match on observed data up to the cut
    (2004-01-01) only, pick the best 10, forecast from the cut, compare with the observed 2004-2008 values.
    The proxy is reused (it was trained on simulator runs, never on observed data after the cut)."""
    cf, opt, m, b10 = cfg["forecast"], cfg["optimization"], cfg["matching"], cfg["best10"]
    obs_cum, proxy = state["obs_cum"], state["proxy"]
    idx, cut = obs_cum.index, pd.Timestamp(cf["backtest_cut"])
    pre, post_dates = idx <= cut, idx[idx > cut]
    o_pre = {k: obs_cum[k].to_numpy()[pre] for k in PHASES}
    sigma = sigma_matrix(o_pre, m["sigma_rel"], m["sigma_floor_frac"])
    d = len(x_cols(state["features"]))
    X = qmc.LatinHypercube(d=d, seed=cfg["project"]["random_seed"] + 1).random(opt["lhs_samples"])
    scores = []
    for i in range(0, len(X), 2000):
        Y, S = proxy.predict(X[i:i + 2000], return_std=True)
        Yd, Sd = unstack(Y, len(idx)), unstack(S, len(idx))
        scores.append(misfit(o_pre, {k: v[:, pre] for k, v in Yd.items()}, sigma, m["phase_weights"],
                             {k: v[:, pre] for k, v in Sd.items()}))
    scores = np.concatenate(scores)
    anchor = ({k: float(obs_cum[k].loc[:cut].iloc[-1]) for k in PHASES}
              if cf["anchor"] == "observed" else None)
    kw = {"fit_start": cf["backtest_fit_start"], "until": cut, "method": state["forecast_method"],
          "ar_models": state["ar_models_backtest"]}
    wfb, wm = state["wor_fallback_backtest"], state["water_model"]
    picks = pick_diverse(X, scores, b10["n_cases"], b10["min_distance"])
    best = forecast_param_sets(X[picks], proxy, idx, post_dates, cfg, wfb, wm, anchor, **kw)
    keep = np.argsort(scores)[: opt["posterior_keep"]]
    post = forecast_param_sets(X[keep], proxy, idx, post_dates, cfg, wfb, wm, anchor, **kw)
    w = glue_weights(scores[keep])
    rows, qs = [], sorted(b10["percentiles"])
    for k in PHASES:
        actual = obs_cum[k].loc[post_dates].to_numpy()
        base = float(obs_cum[k].loc[:cut].iloc[-1])
        for label, arr, ww in (("best_10", best[k], None), ("posterior", post[k], w)):
            lo, mid, hi = weighted_quantile(arr, qs, ww)
            rows.append({"phase": k, "set": label, "coverage_p10_p90": coverage(actual, lo, hi),
                         "p50_rel_err_2008": abs(mid[-1] - actual[-1]) / max(actual[-1], 1e-9),
                         "p50_increment_rel_err": abs(mid[-1] - actual[-1]) / max(actual[-1] - base, 1e-9)})
    return pd.DataFrame(rows)


def run(cfg: dict, state: dict) -> dict:
    log = get_logger("s5_best10", cfg["paths"]["logs"])
    T, F = cfg["paths"]["tables"], cfg["paths"]["figures"]
    b10, names = cfg["best10"], cfg["parameters"]["names"]
    obs_cum, proxy, post = state["obs_cum"], state["proxy"], state["posterior"]
    xc = [c for c in post.columns if c.startswith("x") and c[1:].isdigit()]
    f_dates, wor_fb, wm = state["forecast_dates"], state["wor_fallback"], state["water_model"]
    hist_index = obs_cum.index
    anchor = ({k: float(obs_cum[k].iloc[-1]) for k in PHASES}
              if cfg["forecast"]["anchor"] == "observed" else None)

    Xc, sc = post[xc].to_numpy(), post["misfit_proxy"].to_numpy()
    picks = pick_diverse(Xc, sc, b10["n_cases"], b10["min_distance"])
    best = post.iloc[picks].reset_index(drop=True)
    method = state["forecast_method"]
    other = [m for m in METHODS if m != method][0]
    mk = {"method": method, "ar_models": state["ar_models"]}
    fc = forecast_param_sets(best[xc].to_numpy(), proxy, hist_index, f_dates, cfg, wor_fb, wm, anchor, **mk)
    fc_other = forecast_param_sets(best[xc].to_numpy(), proxy, hist_index, f_dates, cfg, wor_fb, wm, anchor,
                                   method=other, ar_models=state["ar_models"])

    rows, long_rows = [], []
    for i in range(len(best)):
        name = f"Case {i + 1}"
        row_cum = {k: fc[k][i] for k in PHASES}
        rows.append({"template_sheet": name, **best.loc[i, names].to_dict(),
                     "misfit_proxy": best.loc[i, "misfit_proxy"],
                     **{f"cum_{k}_2028": row_cum[k][-1] for k in PHASES},
                     **{f"cum_{k}_2028_{other}": fc_other[k][i][-1] for k in PHASES},
                     "oil_2008_2028_stb": row_cum["oil"][-1] - (anchor["oil"] if anchor else np.nan),
                     **end_rates(row_cum, f_dates)})
        for j, d in enumerate(f_dates):
            long_rows.append({"template_sheet": name, "date": d, **{k: row_cum[k][j] for k in PHASES}})
    table = pd.DataFrame(rows)
    # initial hydrocarbon pore volume (from the grid files: scales exactly with the porosity multiplier)
    table["hcpv_rb"] = cfg["grid"]["hcpv_base_rb"] * table["Porosity Multiplier"]
    # recovery to 2028 per reservoir barrel of initial oil; recovery factor = this x Bo (Bo not provided)
    table["np_2028_per_hcpv_stb_per_rb"] = table["cum_oil_2028"] / table["hcpv_rb"]
    pd.DataFrame(long_rows).to_csv(T / "srq6_best10_forecasts.csv", index=False)
    wc_cap = cfg["forecast"]["wor_max"] / (1.0 + cfg["forecast"]["wor_max"])
    table["wor_cap_reached"] = table["water_cut_2028"] >= wc_cap - 1e-9
    if table["wor_cap_reached"].any():
        log.warning("%d of %d forecasts hit the WOR cap (%.0f) — water after the cap is a ceiling, not a trend",
                    int(table["wor_cap_reached"].sum()), len(table), cfg["forecast"]["wor_max"])
    table.to_csv(T / "srq6_best10.csv", index=False)
    table[["template_sheet", "oil_2008_2028_stb", "cum_oil_2028", "hcpv_rb", "np_2028_per_hcpv_stb_per_rb",
           "oil_rate_2028_stb_d", "water_cut_2028", "wor_cap_reached"]].to_csv(T / "srq6_business.csv", index=False)

    bt = pipeline_backtest(cfg, state)
    bt.to_csv(T / "srq6_pipeline_backtest.csv", index=False)
    log.info("Whole-pipeline backtest vs observed field (match <= %s, forecast to %s):\n%s",
             cfg["forecast"]["backtest_cut"], obs_cum.index[-1].date(), bt.round(4).to_string(index=False))

    # uncertainty: best 10 (equal weights) vs weighted posterior vs all 100 unmatched cases
    post_fc = forecast_param_sets(Xc, proxy, hist_index, f_dates, cfg, wor_fb, wm, anchor, **mk)
    w = post["weight"].to_numpy()
    qs = sorted(b10["percentiles"])
    spread = []
    all100 = state["all_cases_2028"]
    for k in PHASES:
        for label, vals, ww in (("all_100_cases", all100[f"cum_{k}_2028"].to_numpy(), None),
                                ("posterior", post_fc[k][:, -1], w),
                                ("best_10", fc[k][:, -1], None),
                                (f"best_10_{other}", fc_other[k][:, -1], None)):
            lo, mid, hi = weighted_quantile(vals, qs, ww)
            spread.append({"phase": k, "set": label, "P90_low": lo, "P50": mid, "P10_high": hi,
                           "P10_P90_width": hi - lo})
    spread = pd.DataFrame(spread)
    spread.to_csv(T / "srq6_spread_2028.csv", index=False)
    log.info("Forecast method %s; 2028 cumulative spread (best_10_%s = model-form uncertainty):\n%s",
             method, other, spread.round(1).to_string(index=False))

    band = {k: weighted_quantile(post_fc[k], qs, w) for k in PHASES}
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    for ax, k in zip(axes, PHASES):
        ax.fill_between(f_dates, band[k][0], band[k][2], color="tab:orange", alpha=0.25,
                        label="P90-P10 (parameter uncertainty only)")
        ax.plot(f_dates, fc[k].T, color="tab:red", lw=0.8)
        ax.plot(hist_index, obs_cum[k], "k.", ms=3, label="observed history")
        ax.set_title(f"Cumulative {k} [{UNITS[k]}]")
        ax.legend(loc="upper left", fontsize=8)
    fig.suptitle(f"Best 10 history-matched forecasts to 2028 (red, {method}) — band excludes method error")
    fig.tight_layout()
    fig.savefig(F / "srq6_forecast_fan.png", dpi=150)
    plt.close(fig)
    return {"best10": table, "best10_forecasts": fc, "spread": spread, "pipeline_backtest": bt}
