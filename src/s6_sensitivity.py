"""Step 6: Parameter influence (SRQ3: which of the 4 parameters control production, and how?).

  * Spearman rank correlation, parameter vs outcome, over the 100 simulated cases
    (2008 cumulatives, water breakthrough date, history misfit, forecast 2028 cumulatives).
  * Water breakthrough date per case (deck slide 29: aquifer size / porosity drive water).
  * Sobol first-order and total indices (F31, F32) on the proxy for 2008 cumulatives and on the
    proxy + decline forecaster for 2028 cumulatives (SALib, Saltelli scheme).

Outputs (outputs/tables/): srq3_spearman.csv, srq3_breakthrough.csv, srq3_sobol.csv
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from SALib.analyze import sobol as sobol_analyze
from SALib.sample import sobol as sobol_sample
from scipy.stats import spearmanr

from .s1_prepare import x_cols
from .s2_proxy import unstack
from .s5_best10 import forecast_param_sets
from .utils import PHASES, get_logger


def breakthrough_dates(water_cum: pd.DataFrame, threshold: float) -> pd.Series:
    """First date at which cumulative water exceeds `threshold` STB (NaT if never)."""
    out = {}
    for c in water_cum.columns:
        hit = water_cum.index[water_cum[c] > threshold]
        out[c] = hit[0] if len(hit) else pd.NaT
    return pd.Series(out, name="breakthrough")


def run(cfg: dict, state: dict) -> dict:
    log = get_logger("s6_sensitivity", cfg["paths"]["logs"])
    T = cfg["paths"]["tables"]
    feats, sim_cum, names = state["features"], state["sim_cum"], cfg["parameters"]["names"]
    cases = feats.index.tolist()

    outcomes = pd.DataFrame({f"cum_{k}_2008": sim_cum[k][cases].iloc[-1] for k in PHASES})
    bt = breakthrough_dates(sim_cum["water"][cases], cfg["sensitivity"]["breakthrough_threshold_stb"])
    outcomes["breakthrough_days"] = (bt - sim_cum["water"].index[0]).dt.days
    outcomes["misfit"] = state["case_misfit"]["misfit"].reindex(cases)
    for k in PHASES:
        outcomes[f"cum_{k}_2028"] = state["all_cases_2028"][f"cum_{k}_2028"].reindex(cases)

    rows = []
    for p in names:
        for o in outcomes.columns:
            ok = outcomes[o].notna()
            if ok.sum() < 3 or outcomes.loc[ok, o].nunique() < 2:
                continue
            rho, pval = spearmanr(feats.loc[ok[ok].index, p], outcomes.loc[ok, o])
            rows.append({"parameter": p, "outcome": o, "spearman_rho": rho, "p_value": pval})
    spear = pd.DataFrame(rows)
    spear.to_csv(T / "srq3_spearman.csv", index=False)
    bt.to_frame().join(feats[names]).to_csv(T / "srq3_breakthrough.csv")

    xc = x_cols(feats)
    problem = {"num_vars": len(xc), "names": names, "bounds": [[0.0, 1.0]] * len(xc)}
    Xs = sobol_sample.sample(problem, cfg["sensitivity"]["sobol_n"], calc_second_order=False,
                             seed=cfg["project"]["random_seed"])
    n_hist = sim_cum["oil"].shape[0]
    y2008 = unstack(state["proxy"].predict(Xs), n_hist)
    y2028 = forecast_param_sets(Xs, state["proxy"], sim_cum["oil"].index, state["forecast_dates"], cfg,
                                state["wor_fallback"], state["water_model"], anchor=None,
                                method=state["forecast_method"], ar_models=state["ar_models"])
    srows = []
    for label, Y in (("2008", y2008), ("2028", y2028)):
        for k in PHASES:
            y = Y[k][:, -1]
            if np.std(y) == 0:
                continue
            res = sobol_analyze.analyze(problem, y, calc_second_order=False, print_to_console=False,
                                        seed=cfg["project"]["random_seed"])
            for j, name in enumerate(names):
                srows.append({"outcome": f"cum_{k}_{label}", "parameter": name, "S1": res["S1"][j],
                              "S1_conf": res["S1_conf"][j], "ST": res["ST"][j], "ST_conf": res["ST_conf"][j]})
    sob = pd.DataFrame(srows)
    sob.to_csv(T / "srq3_sobol.csv", index=False)
    if not sob.empty:
        log.info("Sobol total indices (ST):\n%s",
                 sob.pivot(index="parameter", columns="outcome", values="ST").round(3).to_string())
    return {"spearman": spear, "sobol": sob, "breakthrough": bt}
