"""Step 3: Optimization / history matching (SRQ2: which parameters reproduce the observed history?).

Deck objective 2: "identify the optimal set of reservoir parameters that minimize the mismatch".
  A. Baseline: score the 100 simulated cases directly against the observed cumulatives.
  B. Main method: search the continuous parameter space with the proxy.
       - loss = weighted least-squares misfit (F23), proxy uncertainty added to the error variance
       - global optimum by differential evolution (deterministic seed, polished)
       - posterior sample: Latin-hypercube points weighted by w ∝ exp(-O/2) (F24)
  C. Sensitivity of the accepted set to the assumed observation error sigma.

Outputs (outputs/tables/): srq2_case_misfit.csv, srq2_sigma_sensitivity.csv, srq2_optimum.csv,
                           srq2_posterior_samples.csv
         (outputs/figures/): srq2_history_match.png
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution
from scipy.stats import qmc

from .metrics import glue_weights, misfit, sigma_matrix
from .plotting import plt
from .s1_prepare import x_cols
from .s2_proxy import unstack
from .utils import PHASES, UNITS, get_logger


def proxy_objective(proxy, obs: dict, sigma: dict, weights: dict, n_dates: int):
    """Return f(X) -> misfit for a batch of scaled parameter vectors, using the proxy."""
    def f(X):
        Y, S = proxy.predict(np.atleast_2d(X), return_std=True)
        return misfit(obs, unstack(Y, n_dates), sigma, weights, unstack(S, n_dates))
    return f


def run(cfg: dict, state: dict) -> dict:
    log = get_logger("s3_history_match", cfg["paths"]["logs"])
    T, F = cfg["paths"]["tables"], cfg["paths"]["figures"]
    m, opt, seed = cfg["matching"], cfg["optimization"], cfg["project"]["random_seed"]
    feats, sim_cum, obs_cum, proxy = state["features"], state["sim_cum"], state["obs_cum"], state["proxy"]
    scaler, names, xc = state["scaler"], cfg["parameters"]["names"], x_cols(state["features"])
    n = obs_cum.shape[0]
    obs = {k: obs_cum[k].to_numpy() for k in PHASES}
    sigma = sigma_matrix(obs, m["sigma_rel"], m["sigma_floor_frac"])
    cases = feats.index.tolist()
    sim = {k: sim_cum[k][cases].to_numpy().T for k in PHASES}

    # A. baseline: the 100 simulated cases
    table = pd.DataFrame(index=cases)
    table["misfit"] = misfit(obs, sim, sigma, m["phase_weights"])
    for k in PHASES:
        only = {p: float(p == k) for p in PHASES}
        table[f"misfit_{k}"] = misfit(obs, sim, sigma, only)
    table["weight"] = glue_weights(table["misfit"].to_numpy())
    table["rank"] = table["misfit"].rank(method="first").astype(int)
    n_accept = max(1, int(round(m["accept_top_fraction"] * len(table))))
    table["accepted"] = table["rank"] <= n_accept
    table = table.join(feats[[*names, "split"]]).sort_values("rank")
    table.to_csv(T / "srq2_case_misfit.csv")

    sens, base = [], set(table.index[table["accepted"]])
    for s in [m["sigma_rel"], *m["sigma_rel_sensitivity"]]:
        sc = pd.Series(misfit(obs, sim, sigma_matrix(obs, s, m["sigma_floor_frac"]), m["phase_weights"]), index=cases)
        acc = set(sc.nsmallest(n_accept).index)
        sens.append({"sigma_rel": s, "n_accepted": n_accept, "overlap_with_base": len(acc & base),
                     "best_case": sc.idxmin(), "best_misfit": float(sc.min())})
    pd.DataFrame(sens).to_csv(T / "srq2_sigma_sensitivity.csv", index=False)

    # B. proxy optimization
    f = proxy_objective(proxy, obs, sigma, m["phase_weights"], n)
    d = len(xc)
    de = differential_evolution(lambda x: float(f(x)[0]), bounds=[(0.0, 1.0)] * d, seed=seed,
                                maxiter=opt["de_maxiter"], popsize=opt["de_popsize"], tol=1e-8, polish=True)
    x_opt = np.clip(de.x, 0.0, 1.0)
    optimum = pd.DataFrame([dict(zip(names, scaler.inverse(x_opt)[0]))])
    optimum["misfit_proxy"] = float(de.fun)
    optimum["best_case_misfit_sim"] = float(table["misfit"].iloc[0])
    optimum["de_converged"] = bool(de.success)
    optimum.to_csv(T / "srq2_optimum.csv", index=False)

    lhs = qmc.LatinHypercube(d=d, seed=seed).random(opt["lhs_samples"])
    X_all = np.vstack([lhs, x_opt[None, :]])
    scores = np.concatenate([f(X_all[i:i + 2000]) for i in range(0, len(X_all), 2000)])
    keep = np.argsort(scores)[: opt["posterior_keep"]]
    post = pd.DataFrame(X_all[keep], columns=xc)
    post[names] = scaler.inverse(X_all[keep])
    post["misfit_proxy"] = scores[keep]
    post["weight"] = glue_weights(scores[keep])
    post.to_csv(T / "srq2_posterior_samples.csv", index=False)

    log.info("Best simulated case %s misfit=%.4f | proxy optimum misfit=%.4f (converged=%s)",
             table.index[0], table["misfit"].iloc[0], de.fun, de.success)
    log.info("Optimum parameters: %s", optimum[names].round(4).to_dict("records")[0])

    # figure: observed vs all cases vs accepted vs proxy optimum
    y_opt = unstack(proxy.predict(x_opt[None, :]), n)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    acc_cases = table.index[table["accepted"]]
    for ax, k in zip(axes, PHASES):
        ax.plot(obs_cum.index, sim_cum[k][cases].to_numpy(), color="0.85", lw=0.6)
        ax.plot(obs_cum.index, sim_cum[k][acc_cases].to_numpy(), color="tab:blue", lw=0.9, alpha=0.8)
        ax.plot(obs_cum.index, y_opt[k][0], color="tab:red", lw=2.0, label="proxy optimum")
        ax.plot(obs_cum.index, obs[k], "k.", label="observed")
        ax.set_title(f"Cumulative {k} [{UNITS[k]}]")
        ax.legend(loc="upper left", fontsize=8)
    fig.suptitle(f"History match. Grey: 100 cases, blue: best {n_accept}, red: proxy optimum, black: observed")
    fig.tight_layout()
    fig.savefig(F / "srq2_history_match.png", dpi=150)
    plt.close(fig)
    return {"case_misfit": table, "optimum": optimum, "x_opt": x_opt, "posterior": post}
