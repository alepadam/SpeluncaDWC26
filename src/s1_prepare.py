"""Step 1 — Data preparation and analysis (SRQ1: how should simulated and observed data be aligned?).

What it does
  1. Loads the 4 uncertainty parameters, the observed field rates and the 3 simulated cumulative sheets.
  2. Aligns every case's irregular cumulative curve onto the 41 observed quarterly dates
     (combined index -> time interpolation -> keep target dates; cumulatives, not rates).
  3. Tests the two date conventions for the observed rates and keeps the one that fits better.
  4. Runs data-quality checks (monotonic cumulatives, no negatives, gas/oil ratio).
  5. Builds scaled model inputs and the train / validation / test split.

Outputs
  data/processed/: sim_cum_{oil,gas,water}.csv, history_cum_{phase}.csv (RAMP_History),
                   obs_cum_{start,end}.csv, obs_cum.csv (chosen), obs_rates.csv, features.csv
  outputs/tables/: srq1_convention_test.csv, qc_report.csv, field_sheets.csv
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import io_load
from .metrics import misfit, sigma_matrix
from .utils import PHASES, ParamScaler, get_logger, quarter_dates, split_of

CUM_KEYS = {"oil": "oil_cum", "gas": "gas_cum", "water": "water_cum"}


def align_cumulative(raw: pd.DataFrame, target: pd.DatetimeIndex) -> pd.DataFrame:
    """Interpolate irregular cumulative curves onto target dates (formula F20).

    Correct order: union of each column's own timestamps and the target dates -> linear-in-time
    interpolation -> keep target dates. Points outside a column's own data range stay NaN and raise.
    """
    idx = raw.index.union(target)
    full = raw.reindex(idx).interpolate(method="time", limit_area="inside")
    out = full.loc[target]
    if out.isna().any().any():
        bad = out.columns[out.isna().any()].tolist()
        raise ValueError(f"Missing values after alignment for {len(bad)} columns, e.g. {bad[:5]}")
    return out


def observed_cumulative(obs: pd.DataFrame, convention: str) -> pd.DataFrame:
    """Integrate observed daily rates into cumulatives on the observed dates (formula F22).

    'start': rate stamped t_k applies to [t_k, t_k+1)  ->  Q(t_n) = sum_{k<n}  q_k (t_k+1 - t_k)
    'end'  : rate stamped t_k applies to (t_k-1, t_k]  ->  Q(t_n) = sum_{k<=n} q_k (t_k - t_k-1), Q(t_0) = 0
    """
    days = obs.index.to_series().diff().dt.days.fillna(0).to_numpy(float)  # days[k] = t_k - t_{k-1}
    out = {}
    for k in PHASES:
        q = obs[k].to_numpy(float)
        vol = np.zeros_like(q)
        if convention == "start":
            vol[1:] = q[:-1] * days[1:]
        elif convention == "end":
            vol = q * days
        else:
            raise ValueError(f"Unknown convention {convention!r}")
        out[k] = np.cumsum(vol)
    return pd.DataFrame(out, index=obs.index)


def quality_checks(sim_cum: dict, rs_expected: float, rs_tol: float) -> pd.DataFrame:
    rows = []
    for k, df in sim_cum.items():
        dec = (df.diff().iloc[1:] < -1e-6).sum()
        rows.append({"check": f"{k}: cumulative never decreases", "cases_failing": int((dec > 0).sum()),
                     "detail": ", ".join(dec[dec > 0].index[:10])})
        neg = (df < 0).any()
        rows.append({"check": f"{k}: no negative values", "cases_failing": int(neg.sum()),
                     "detail": ", ".join(neg[neg].index[:10])})
    d_oil = sim_cum["oil"].iloc[-1] - sim_cum["oil"].iloc[0]
    d_gas = sim_cum["gas"].iloc[-1] - sim_cum["gas"].iloc[0]
    rs = (d_gas / d_oil.replace(0, np.nan)).dropna()
    off = rs[(rs - rs_expected).abs() / rs_expected > rs_tol]
    rows.append({"check": f"gas/oil ratio within {rs_tol:.0%} of {rs_expected} MSCF/STB",
                 "cases_failing": int(off.size),
                 "detail": f"min={rs.min():.4f} median={rs.median():.4f} max={rs.max():.4f}"})
    return pd.DataFrame(rows)


def build_features(params: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, ParamScaler]:
    names = cfg["parameters"]["names"]
    scaler = ParamScaler(names, cfg["parameters"]["log_transform"]).fit(params)
    x = scaler.transform(params)
    feats = params.copy()
    for j, n in enumerate(names):
        feats[f"x{j}"] = x[:, j]
    feats["split"] = [split_of(c, cfg["split"]) for c in feats.index]
    return feats, scaler


def x_cols(feats: pd.DataFrame) -> list[str]:
    return sorted([c for c in feats.columns if c.startswith("x") and c[1:].isdigit()], key=lambda c: int(c[1:]))


def run(cfg: dict) -> dict:
    log = get_logger("s1_prepare", cfg["paths"]["logs"])
    P, T = cfg["paths"]["processed"], cfg["paths"]["tables"]

    sheets = io_load.list_field_sheets(cfg)
    known = {cfg["sheets"]["field"], *cfg["sheets"]["curves"].values()}
    pd.DataFrame({"sheet": sheets, "used": [s in known for s in sheets]}).to_csv(T / "field_sheets.csv", index=False)
    extra = [s for s in sheets if s not in known]
    if extra:
        log.info("Sheets in 02 Field Production not used yet (check for pressure data): %s", extra)

    params = io_load.load_uncertainty(cfg)
    obs = io_load.load_observed(cfg)
    obs.to_csv(P / "obs_rates.csv")
    expected = quarter_dates(cfg["history"]["start"], cfg["history"]["end"])
    if not obs.index.equals(expected):
        log.warning("Observed dates differ from the expected 41 quarters; using the observed dates")
    target = obs.index

    sim_cum, hist_cum = {}, {}
    for phase, key in CUM_KEYS.items():
        cases, hist = io_load.load_curve_sheet(cfg, cfg["sheets"]["curves"][key])
        sim_cum[phase] = align_cumulative(cases, target)
        sim_cum[phase].to_csv(P / f"sim_cum_{phase}.csv")
        if hist is not None and hist.notna().sum() > 1:
            hist_cum[phase] = align_cumulative(hist.to_frame("RAMP_History"), target)["RAMP_History"]
            hist_cum[phase].to_csv(P / f"history_cum_{phase}.csv")
        log.info("Aligned %s cumulative: %d dates x %d cases", phase, *sim_cum[phase].shape)

    common = sorted(set(params.index) & set(sim_cum["oil"].columns), key=lambda c: int(c.split()[1]))
    if len(common) < len(params):
        log.warning("Cases with parameters but no curves: %s", sorted(set(params.index) - set(common))[:10])
    params = params.loc[common]
    sim_cum = {k: v[common] for k, v in sim_cum.items()}

    # SRQ1 — which observed-rate convention matches the simulator's cumulatives?
    m = cfg["matching"]
    rows, obs_by_conv = [], {}
    sim_stack = {k: sim_cum[k].to_numpy().T for k in PHASES}  # N x T
    for conv in m["date_conventions"]:
        oc = observed_cumulative(obs, conv)
        obs_by_conv[conv] = oc
        oc.to_csv(P / f"obs_cum_{conv}.csv")
        o = {k: oc[k].to_numpy() for k in PHASES}
        scores = pd.Series(misfit(o, sim_stack, sigma_matrix(o, m["sigma_rel"], m["sigma_floor_frac"]),
                                  m["phase_weights"]), index=common)
        row = {"convention": conv, "median_misfit_best10": scores.nsmallest(10).median(),
               "min_misfit": scores.min(), "best_case": scores.idxmin()}
        if len(hist_cum) == 3:  # RAMP_History vs observed under this convention
            row["ramp_history_rel_diff_end"] = float(np.mean(
                [abs(hist_cum[k].iloc[-1] - oc[k].iloc[-1]) / max(oc[k].iloc[-1], 1e-9) for k in PHASES]))
        rows.append(row)
    conv_test = pd.DataFrame(rows).sort_values("median_misfit_best10")
    conv_test.to_csv(T / "srq1_convention_test.csv", index=False)
    chosen = str(conv_test.iloc[0]["convention"])
    obs_cum = obs_by_conv[chosen]
    obs_cum.to_csv(P / "obs_cum.csv")
    log.info("SRQ1 convention test:\n%s\n-> using '%s'", conv_test.to_string(index=False), chosen)

    qc = quality_checks(sim_cum, cfg["gas"]["rs_expected"], cfg["gas"]["rs_tolerance"])
    qc.to_csv(T / "qc_report.csv", index=False)
    log.info("Quality checks:\n%s", qc.to_string(index=False))

    feats, scaler = build_features(params, cfg)
    feats.to_csv(P / "features.csv")
    return {"sim_cum": sim_cum, "obs_cum": obs_cum, "obs_rates": obs, "features": feats,
            "scaler": scaler, "convention": chosen, "history_cum": hist_cum}
