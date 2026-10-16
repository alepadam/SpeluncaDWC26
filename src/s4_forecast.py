"""Step 4: Forecast production 20 years ahead (SRQ5: can we extrapolate reliably beyond 2008?).

The provided simulation curves end at 2008-01-01 (deck slide 31), so the forecast must extrapolate.
Physics-constrained forecaster, applied to any set of 1998-2008 cumulative curves
(a simulated case, or a proxy prediction for an optimized parameter set):
  * Oil:   hyperbolic Arps decline fitted on late history (F16), 0 <= b <= 1, continued
            analytically from 2008 with the decline rate it has reached by then (F17).
  * Water: ln(WOR) = a + c·Np trend fitted on late history (F18), anchored to the last WOR, c >= 0,
            WOR capped; water volume per quarter = WOR × oil volume.
  * Gas:   solution gas, Rs = ΔGp/ΔNp over the fit window; gas volume = Rs × oil volume (F13).
  Cumulatives are accumulated quarter by quarter with real day counts (F15), so they never decrease.

Validation (temporal backtest): repeat with data up to 2004-01-01 only, forecast 2004–2008, compare
against the simulator, for validation and test cases. The water trend is selected on validation cases
only. Second method: an autoregressive gradient-boosting model of next-quarter ratios. The method used for the final
forecast (decline or ML) is chosen by backtest on validation cases; the other is kept as model-form uncertainty.
Benchmark: naive (hold last rate).
The full pipeline (match -> best 10 -> forecast) is backtested against the observed field in step 5.

Outputs (outputs/tables/): srq5_backtest_cases.csv, srq5_backtest_summary.csv, srq5_all_cases_2028.csv
         (outputs/figures/): srq5_backtest.png
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from scipy.optimize import OptimizeWarning, curve_fit
from sklearn.ensemble import GradientBoostingRegressor

from .plotting import plt
from .s1_prepare import x_cols
from .utils import PHASES, UNITS, get_logger, quarter_dates

B_EPS = 1e-4


# --------------------------------------------------------------------------- Arps (F16, F17)
def arps_rate(t, qi, di, b):
    t = np.asarray(t, float)
    if b < B_EPS:
        return qi * np.exp(-di * t)
    return qi / np.power(1.0 + b * di * t, 1.0 / b)


def arps_cum(t, qi, di, b):
    """Volume produced from 0 to t (days), all b in [0, 1], including the limits b=0 and b=1."""
    t = np.asarray(t, float)
    if di <= 1e-15:
        return qi * t
    if b < B_EPS:
        return qi / di * (1.0 - np.exp(-di * t))
    if abs(b - 1.0) < B_EPS:
        return qi / di * np.log1p(di * t)
    return qi / ((1.0 - b) * di) * (1.0 - np.power(1.0 + b * di * t, (b - 1.0) / b))


def fit_arps(t, q, b_bounds=(0.0, 1.0)):
    """Least-squares fit of q(t) with relative weighting; falls back to a log-linear exponential."""
    t, q = np.asarray(t, float), np.asarray(q, float)
    ok = q > 0
    t, q = t[ok], q[ok]
    if q.size < 3:
        return (float(q[-1]) if q.size else 0.0), 0.0, 0.0
    slope = np.polyfit(t, np.log(q), 1)[0]
    d0 = max(-slope, 1e-9)
    p0 = [float(q[0]), d0, float(np.clip(0.5, *b_bounds))]
    lower, upper = [1e-9, 1e-12, b_bounds[0]], [10.0 * q.max(), 1.0, b_bounds[1]]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", OptimizeWarning)
            popt, _ = curve_fit(lambda tt, qi, di, b: arps_rate(tt, qi, di, b), t, q, p0=p0,
                                bounds=(lower, upper), sigma=q, maxfev=20000)
        return float(popt[0]), float(popt[1]), float(popt[2])
    except (RuntimeError, ValueError):
        intercept = np.polyfit(t, np.log(q), 1)[1]
        return float(np.exp(intercept)), d0, 0.0


# --------------------------------------------------------------------------- forecaster
def period_table(cum: dict[str, pd.Series]) -> pd.DataFrame:
    """Per-period volumes and average rates; period k = (t_k-1, t_k]."""
    idx = cum["oil"].index
    days = idx.to_series().diff().dt.days.to_numpy(float)
    df = pd.DataFrame(index=idx)
    for k in PHASES:
        df[f"d{k}"] = cum[k].diff().to_numpy()
        df[f"q{k}"] = df[f"d{k}"] / days
        df[f"cum_{k}"] = cum[k].to_numpy()
    df["days"] = days
    df["t_mid"] = (idx - pd.to_timedelta(days / 2.0, unit="D")) if len(idx) else idx
    return df.iloc[1:]


WATER_MODELS = ("wor_vs_np", "wor_vs_time")


def fit_forecaster(cum: dict[str, pd.Series], fit_start, cfg_f: dict, rs_default: float,
                   wor_fallback: dict | None = None) -> dict:
    """Fit oil decline, two WOR trends and Rs on the window of periods ending after `fit_start`.

    WOR trends (both standard empirical forms, chosen later by backtest on validation cases):
      wor_vs_np   : ln(WOR) = a + c * Np        (F18)
      wor_vs_time : ln(WOR) = a + c * t
    Each is anchored to the last observed WOR (at the last period's midpoint) and has c >= 0.
    """
    per = period_table(cum)
    win = per[per.index > pd.Timestamp(fit_start)]
    if len(win) < cfg_f["min_points"]:
        raise ValueError(f"Only {len(win)} periods in the fit window (need {cfg_f['min_points']})")
    t_end = cum["oil"].index[-1]
    t0 = win["t_mid"].iloc[0]
    tt = (win["t_mid"] - t0).dt.days.to_numpy(float)
    qi, di, b = fit_arps(tt, win["qoil"].to_numpy(), tuple(cfg_f["b_bounds"]))
    t_end_rel = float((t_end - t0).days)
    q_fit_last = float(arps_rate(tt[-1], qi, di, b))
    scale = float(win["qoil"].iloc[-1]) / q_fit_last if q_fit_last > 0 else 1.0
    q_end = float(arps_rate(t_end_rel, qi, di, b)) * scale          # anchored to the last actual rate
    d_end = di / (1.0 + b * di * t_end_rel) if b >= B_EPS else di    # decline rate reached at t_end

    doil = win["doil"].sum()
    rs = float(win["dgas"].sum() / doil) if doil > 0 else rs_default

    wor = (win["qwater"] / win["qoil"].where(win["qoil"] > 0)).to_numpy(float)
    np_mid = (win["cum_oil"] - win["doil"] / 2.0).to_numpy(float)
    ok = np.isfinite(wor) & (wor > cfg_f["wor_min"])
    wor_last = float(wor[-1]) if np.isfinite(wor[-1]) else 0.0
    water = {}
    if ok.sum() >= max(3, cfg_f["min_points"] // 2):
        source = "fit"
        for name, xv in (("wor_vs_np", np_mid), ("wor_vs_time", tt)):
            c, a = np.polyfit(xv[ok], np.log(wor[ok]), 1)
            water[name] = [float(a), max(float(c), 0.0)]
    elif wor_fallback is not None:
        source = "population_fallback"
        water = {k: list(v) for k, v in wor_fallback.items()}
    else:
        source = "no_water"
        water = {k: [-np.inf, 0.0] for k in WATER_MODELS}
    if wor_last > cfg_f["wor_min"]:                                  # continuity with the last WOR
        water["wor_vs_np"][0] = np.log(wor_last) - water["wor_vs_np"][1] * np_mid[-1]
        water["wor_vs_time"][0] = np.log(wor_last) - water["wor_vs_time"][1] * tt[-1]
    return {"qi": qi, "di": di, "b": b, "q_end": q_end, "d_end": d_end, "rs": rs, "water": water,
            "water_source": source, "t_end": t_end, "t_end_rel": t_end_rel,
            "cum_end": {k: float(cum[k].iloc[-1]) for k in PHASES}}


def forecast_from_fit(fit: dict, dates: pd.DatetimeIndex, wor_max: float,
                      water_model: str = "wor_vs_np") -> dict[str, np.ndarray]:
    """Cumulative oil, gas, water on `dates` (all after t_end), continuing from the history values."""
    if water_model not in WATER_MODELS:
        raise ValueError(f"water_model must be one of {WATER_MODELS}")
    tau = np.asarray((dates - fit["t_end"]).days, float)
    if np.any(tau <= 0) or np.any(np.diff(tau) <= 0):
        raise ValueError("Forecast dates must be increasing and after the end of history")
    edges = np.concatenate([[0.0], tau])
    d_oil = np.diff(arps_cum(edges, fit["q_end"], fit["d_end"], fit["b"]))
    np_mid = fit["cum_end"]["oil"] + np.concatenate([[0.0], np.cumsum(d_oil)[:-1]]) + d_oil / 2.0
    a, c = fit["water"][water_model]
    if np.isfinite(a):
        x = np_mid if water_model == "wor_vs_np" else fit["t_end_rel"] + (edges[:-1] + edges[1:]) / 2.0
        wor = np.minimum(np.exp(a + c * x), wor_max)
    else:
        wor = np.zeros_like(np_mid)
    return {"oil": fit["cum_end"]["oil"] + np.cumsum(d_oil),
            "gas": fit["cum_end"]["gas"] + np.cumsum(fit["rs"] * d_oil),
            "water": fit["cum_end"]["water"] + np.cumsum(wor * d_oil)}


def naive_forecast(cum: dict[str, pd.Series], dates: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    """Benchmark: hold the last period's rates constant."""
    per = period_table(cum)
    tau = np.asarray((dates - cum["oil"].index[-1]).days, float)
    return {k: float(cum[k].iloc[-1]) + float(per[f"q{k}"].iloc[-1]) * tau for k in PHASES}


def case_curves(sim_cum: dict, case: str, until=None) -> dict[str, pd.Series]:
    out = {k: sim_cum[k][case] for k in PHASES}
    return {k: (v[v.index <= pd.Timestamp(until)] if until is not None else v) for k, v in out.items()}


def population_wor(sim_cum: dict, cases: list[str], fit_start, cfg_f: dict, rs_default: float) -> dict | None:
    """Median (a, c) of each WOR trend over cases with enough water; used as a fallback for water-free curves."""
    fits = {k: [] for k in WATER_MODELS}
    for c in cases:
        try:
            f = fit_forecaster(case_curves(sim_cum, c), fit_start, cfg_f, rs_default)
        except ValueError:
            continue
        if f["water_source"] == "fit":
            for k in WATER_MODELS:
                fits[k].append(f["water"][k])
    if not fits["wor_vs_np"]:
        return None
    return {k: tuple(np.median(np.array(v), axis=0)) for k, v in fits.items()}


# --------------------------------------------------------------------------- ML forecaster (autoregressive)
METHODS = ("decline", "ml_autoregressive")


def _ar_state(cum: dict[str, pd.Series], fit_start, rs_default: float) -> dict:
    """Last-quarter state of a history: oil rate, WOR, Rs over the fit window, cumulatives, quarter index."""
    per = period_table(cum)
    win = per[per.index > pd.Timestamp(fit_start)]
    doil = win["doil"].sum()
    qo = float(per["qoil"].iloc[-1])
    return {"qo": qo, "wor": float(per["qwater"].iloc[-1] / qo) if qo > 0 else 0.0,
            "rs": float(win["dgas"].sum() / doil) if doil > 0 else rs_default,
            "cum": np.array([float(cum[k].iloc[-1]) for k in PHASES]), "k": len(per) - 1,
            "t_end": cum["oil"].index[-1]}


def _ar_rows(cum: dict[str, pd.Series], x: np.ndarray):
    per = period_table(cum)
    qo = per["qoil"].to_numpy()
    wor = (per["qwater"] / per["qoil"].where(per["qoil"] > 0)).fillna(0).to_numpy()
    feats, targets = [], []
    for k in range(len(per) - 1):
        if qo[k] <= 0 or qo[k + 1] <= 0:
            continue
        feats.append([*x, np.log(qo[k]), np.log1p(wor[k]), k])
        targets.append([np.log(qo[k + 1] / qo[k]), np.log1p(wor[k + 1]) - np.log1p(wor[k])])
    return feats, targets


def fit_ar(histories: list[dict], X: np.ndarray, seed: int) -> list:
    """Gradient boosting on next-quarter ratios: ln(q_o[k+1]/q_o[k]) and Δln(1+WOR), given parameters and state."""
    Xf, Yt = [], []
    for cum, x in zip(histories, X):
        f, t = _ar_rows(cum, x)
        Xf += f
        Yt += t
    Xf, Yt = np.array(Xf), np.array(Yt)
    return [GradientBoostingRegressor(random_state=seed).fit(Xf, Yt[:, j]) for j in range(2)]


def roll_ar(models: list, states: list[dict], X: np.ndarray, dates: pd.DatetimeIndex) -> dict[str, np.ndarray]:
    """Roll many histories forward together (vectorised over cases). Returns phase -> (N x len(dates))."""
    n = len(states)
    qo = np.array([s["qo"] for s in states], float)
    wor = np.array([s["wor"] for s in states], float)
    rs = np.array([s["rs"] for s in states], float)
    cum = np.vstack([s["cum"] for s in states]).astype(float)
    k = np.array([s["k"] for s in states], float)
    prev = np.array([s["t_end"] for s in states], dtype="datetime64[ns]")
    out = {p: np.empty((n, len(dates))) for p in PHASES}
    for j, d in enumerate(dates):
        rows = np.column_stack([X, np.log(np.maximum(qo, 1e-9)), np.log1p(wor), k])
        qo = qo * np.exp(models[0].predict(rows))
        wor = np.maximum(np.expm1(np.log1p(wor) + models[1].predict(rows)), 0.0)
        dt = (np.datetime64(d, "ns") - prev).astype("timedelta64[D]").astype(float)
        cum = cum + np.column_stack([qo * dt, rs * qo * dt, wor * qo * dt])
        for i, p in enumerate(PHASES):
            out[p][:, j] = cum[:, i]
        prev = np.full(n, np.datetime64(d, "ns"))
        k = k + 1
    return out


def ml_benchmark(sim_cum: dict, feats: pd.DataFrame, train: list[str], test: list[str], cut, fit_start,
                 dates: pd.DatetimeIndex, rs_default: float, seed: int) -> dict:
    """Train on `train` cases (history up to `cut`), roll `test` cases forward over `dates`."""
    xc = x_cols(feats)
    models = fit_ar([case_curves(sim_cum, c, cut) for c in train], feats.loc[train, xc].to_numpy(), seed)
    states = [_ar_state(case_curves(sim_cum, c, cut), fit_start, rs_default) for c in test]
    pred = roll_ar(models, states, feats.loc[test, xc].to_numpy(), dates)
    return {c: {p: pred[p][i] for p in PHASES} for i, c in enumerate(test)}


# --------------------------------------------------------------------------- run
def run(cfg: dict, state: dict) -> dict:
    log = get_logger("s4_forecast", cfg["paths"]["logs"])
    T, F = cfg["paths"]["tables"], cfg["paths"]["figures"]
    cf, seed, rs0 = cfg["forecast"], cfg["project"]["random_seed"], cfg["gas"]["rs_expected"]
    feats, sim_cum, obs_cum = state["features"], state["sim_cum"], state["obs_cum"]
    cases = feats.index.tolist()
    hist_dates = obs_cum.index
    cut = pd.Timestamp(cf["backtest_cut"])
    test_dates = hist_dates[hist_dates > cut]

    # ---- 1. case-level backtest (decline x 2 water models vs naive vs ML), fit 2001-2004 -> 2004-2008
    wor_fb_bt = population_wor({k: v[v.index <= cut] for k, v in sim_cum.items()}, cases,
                               cf["backtest_fit_start"], cf, rs0)
    eval_cases = [c for c in cases if feats.loc[c, "split"] in ("validation", "test")]
    ml = ml_benchmark(sim_cum, feats, [c for c in cases if feats.loc[c, "split"] == "train"], eval_cases,
                      cut, cf["backtest_fit_start"], test_dates, rs0, seed)
    rows = []
    for c in eval_cases:
        hist = case_curves(sim_cum, c, cut)
        truth = {k: sim_cum[k][c].loc[test_dates].to_numpy() for k in PHASES}
        fit = fit_forecaster(hist, cf["backtest_fit_start"], cf, rs0, wor_fb_bt)
        preds = {f"decline_{w}": forecast_from_fit(fit, test_dates, cf["wor_max"], w) for w in WATER_MODELS}
        preds.update({"naive": naive_forecast(hist, test_dates), "ml_autoregressive": ml[c]})
        for method, p in preds.items():
            for k in PHASES:
                base = float(hist[k].iloc[-1])
                inc_true, inc_pred = truth[k][-1] - base, p[k][-1] - base
                rows.append({"case": c, "split": feats.loc[c, "split"], "method": method, "phase": k,
                             "cum_2008_rel_err": abs(p[k][-1] - truth[k][-1]) / max(truth[k][-1], 1e-9),
                             "increment_rel_err": abs(inc_pred - inc_true) / inc_true if inc_true > 0 else np.nan})
    bt = pd.DataFrame(rows)
    bt.to_csv(T / "srq5_backtest_cases.csv", index=False)
    summary = bt.groupby(["split", "method", "phase"])[["cum_2008_rel_err", "increment_rel_err"]].agg(["mean", "max"])
    summary.to_csv(T / "srq5_backtest_summary.csv")
    log.info("Backtest (2004 -> 2008):\n%s", summary.round(4).to_string())

    # water model: chosen on VALIDATION cases only (test cases stay untouched for reporting)
    if cf["water_model"] == "auto":
        val = bt[(bt.split == "validation") & (bt.phase == "water") & bt.method.str.startswith("decline_")]
        err = val.groupby("method")["increment_rel_err"].mean()
        water_model = err.idxmin().removeprefix("decline_") if err.notna().any() else WATER_MODELS[0]
    else:
        water_model = cf["water_model"]
    log.info("Water model used for forecasting: %s", water_model)

    # forecasting method: decline (with the chosen water trend) vs ML autoregressive, chosen on VALIDATION cases
    # by the mean oil + water increment error; the other method is kept to report model-form uncertainty
    val = bt[(bt.split == "validation") & bt.phase.isin(["oil", "water"])]
    method_err = {"decline": val[val.method == f"decline_{water_model}"]["increment_rel_err"].mean(),
                  "ml_autoregressive": val[val.method == "ml_autoregressive"]["increment_rel_err"].mean()}
    method = min(method_err, key=method_err.get) if cf["method"] == "auto" else cf["method"]
    pd.DataFrame([{"method": k, "validation_mean_increment_rel_err_oil_water": v, "selected": k == method}
                  for k, v in method_err.items()]).to_csv(T / "srq5_method_selection.csv", index=False)
    log.info("Forecast method: %s (validation errors %s)", method, {k: round(v, 4) for k, v in method_err.items()})

    xc = x_cols(feats)
    ar_models = fit_ar([case_curves(sim_cum, c) for c in cases], feats[xc].to_numpy(), seed)
    ar_models_bt = fit_ar([case_curves(sim_cum, c, cut) for c in cases], feats[xc].to_numpy(), seed)

    # ---- 2. forecast every simulated case to 2028 (the spread "before matching", for SRQ6)
    f_dates = quarter_dates(cf["start"], cf["end"])
    wor_fb = population_wor(sim_cum, cases, cf["fit_window_start"], cf, rs0)
    rows = []
    ml_all = roll_ar(ar_models, [_ar_state(case_curves(sim_cum, c), cf["fit_window_start"], rs0) for c in cases],
                     feats[xc].to_numpy(), f_dates)
    for i, c in enumerate(cases):
        fit = fit_forecaster(case_curves(sim_cum, c), cf["fit_window_start"], cf, rs0, wor_fb)
        p = forecast_from_fit(fit, f_dates, cf["wor_max"], water_model)
        chosen = p if method == "decline" else {k: ml_all[k][i] for k in PHASES}
        rows.append({"case": c, **{f"cum_{k}_2028": chosen[k][-1] for k in PHASES},
                     **{f"cum_{k}_2028_decline": p[k][-1] for k in PHASES},
                     **{f"cum_{k}_2028_ml": ml_all[k][i][-1] for k in PHASES},
                     "b": fit["b"], "d_end_per_year": fit["d_end"] * 365.25, "rs": fit["rs"],
                     "water_source": fit["water_source"]})
    all_2028 = pd.DataFrame(rows).set_index("case")
    all_2028.to_csv(T / "srq5_all_cases_2028.csv")

    # figure: decline vs naive vs ML on the first evaluation case + truth
    c0 = eval_cases[0]
    hist = case_curves(sim_cum, c0, cut)
    fit = fit_forecaster(hist, cf["backtest_fit_start"], cf, rs0, wor_fb_bt)
    dec = forecast_from_fit(fit, test_dates, cf["wor_max"], water_model)
    nav = naive_forecast(hist, test_dates)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    for ax, k in zip(axes, PHASES):
        ax.plot(hist_dates, sim_cum[k][c0], "k-", lw=1.5, label="simulator (truth)")
        ax.plot(test_dates, dec[k], "r--", label="decline forecast")
        ax.plot(test_dates, nav[k], ":", color="0.4", label="naive")
        ax.plot(test_dates, ml[c0][k], "-.", color="tab:green", label="ML autoregressive")
        ax.axvline(cut, color="0.6", lw=0.8)
        ax.set_title(f"{c0} cumulative {k} [{UNITS[k]}]")
        ax.legend(fontsize=8)
    fig.suptitle("Temporal backtest: fitted up to 2004-01-01, forecast to 2008-01-01")
    fig.tight_layout()
    fig.savefig(F / "srq5_backtest.png", dpi=150)
    plt.close(fig)

    return {"backtest": bt, "backtest_summary": summary, "all_cases_2028": all_2028, "wor_fallback": wor_fb,
            "wor_fallback_backtest": wor_fb_bt, "forecast_dates": f_dates, "water_model": water_model,
            "forecast_method": method, "ar_models": ar_models, "ar_models_backtest": ar_models_bt}
