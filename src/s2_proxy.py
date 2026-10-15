"""Step 2 — ML proxy training and prediction (SRQ4: can a proxy reproduce the simulator on unseen cases?).

Model (deck slide 27, "design an architecture"): a linear autoencoder (PCA) compresses each case's
3 x 41 cumulative curves to K scores; one Gaussian process per score maps the 4 scaled parameters to it
(Higdon et al. 2008). Predictions are decoded back to curves and forced to be non-negative and
non-decreasing. GP variances are propagated to give a per-point uncertainty.

Protocol: fit on train (1-70), compare models on validation (71-85), report test (86-100) once.
The final proxy used for history matching is then refitted on all 100 cases.
Baselines: linear regression, gradient boosting on PCA scores, nearest case.

Outputs: outputs/tables/srq4_proxy_scores.csv, data/processed/proxy.joblib
"""

from __future__ import annotations

import warnings

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, Matern, WhiteKernel
from sklearn.linear_model import LinearRegression
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neighbors import KNeighborsRegressor

from .metrics import endpoint_rel_error, mape, r2, rmse
from .s1_prepare import x_cols
from .utils import PHASES, get_logger


def stack_curves(sim_cum: dict, cases: list[str]) -> np.ndarray:
    """N cases x (3*T): [oil(T) | gas(T) | water(T)]."""
    return np.hstack([sim_cum[k][cases].to_numpy().T for k in PHASES])


def unstack(Y: np.ndarray, n_dates: int) -> dict:
    return {k: Y[:, i * n_dates:(i + 1) * n_dates] for i, k in enumerate(PHASES)}


def enforce_monotone(Y: np.ndarray, n_dates: int) -> np.ndarray:
    """Cumulatives cannot be negative or decrease: clip at 0, then running maximum per phase."""
    out = np.array(Y, dtype=float, copy=True)
    for i in range(len(PHASES)):
        sl = slice(i * n_dates, (i + 1) * n_dates)
        out[:, sl] = np.maximum.accumulate(np.clip(out[:, sl], 0.0, None), axis=1)
    return out


class CurveProxy:
    """Per-phase PCA (linear autoencoder) + one Gaussian process per retained component.

    Each phase (oil, gas, water) gets its own PCA so a small but real effect in one phase (e.g. the aquifer on
    water) is not swamped by the dominant shared mode. Components are kept until `var_target` of each phase's
    variance is explained (and at least `min_components`, data permitting).
    """

    def __init__(self, n_dates: int, var_target: float = 0.99999, kernel: str = "matern52",
                 restarts: int = 3, random_state: int = 42, min_components: int = 3):
        self.n_dates, self.var_target, self.kernel = n_dates, var_target, kernel
        self.restarts, self.random_state, self.min_components = restarts, random_state, min_components
        self.sd_scale_ = np.ones(len(PHASES))  # per-phase calibration of the predictive sd (from validation)

    def _kernel(self, d: int):
        base = (Matern(length_scale=np.ones(d), length_scale_bounds=(1e-2, 1e3), nu=2.5)
                if self.kernel == "matern52" else RBF(length_scale=np.ones(d), length_scale_bounds=(1e-2, 1e3)))
        return ConstantKernel(1.0, (1e-3, 1e5)) * base + WhiteKernel(1e-5, (1e-12, 1e-1))

    def _sl(self, i: int) -> slice:
        return slice(i * self.n_dates, (i + 1) * self.n_dates)

    def encode(self, Y: np.ndarray) -> list[np.ndarray]:
        """Physical curves -> list of per-phase PCA scores."""
        return [self.pcas_[i].transform(Y[:, self._sl(i)] / self.scale_[i]) for i in range(len(PHASES))]

    def decode(self, Z: list[np.ndarray]) -> np.ndarray:
        """Per-phase PCA scores -> physical curves (monotone, non-negative)."""
        Y = np.hstack([self.pcas_[i].inverse_transform(Z[i]) * self.scale_[i] for i in range(len(PHASES))])
        return enforce_monotone(Y, self.n_dates)

    def fit(self, X: np.ndarray, Y: np.ndarray) -> CurveProxy:
        self.scale_ = np.array([max(float(Y[:, self._sl(i)].max()), 1e-9) for i in range(len(PHASES))])
        self.pcas_, self.gps_, self.trunc_var_, self.k_, self.explained_ = [], [], [], [], []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ConvergenceWarning)
            for i in range(len(PHASES)):
                Ys = Y[:, self._sl(i)] / self.scale_[i]
                evr = PCA().fit(Ys).explained_variance_ratio_
                k = int(np.searchsorted(np.cumsum(evr), self.var_target) + 1)
                k = max(min(self.min_components, len(evr)), k)
                k = max(1, min(k, X.shape[0] - 1, Ys.shape[1]))
                pca = PCA(n_components=k).fit(Ys)
                Z = pca.transform(Ys)
                self.trunc_var_.append(np.mean((Ys - pca.inverse_transform(Z)) ** 2, axis=0))
                gps = []
                for j in range(k):
                    gp = GaussianProcessRegressor(kernel=self._kernel(X.shape[1]), normalize_y=True,
                                                  n_restarts_optimizer=self.restarts, random_state=self.random_state)
                    gps.append(gp.fit(X, Z[:, j]))
                self.pcas_.append(pca)
                self.gps_.append(gps)
                self.k_.append(k)
                self.explained_.append(float(np.sum(pca.explained_variance_ratio_)))
        return self

    def predict(self, X: np.ndarray, return_std: bool = False):
        X = np.atleast_2d(X)
        Z, SD = [], []
        for i in range(len(PHASES)):
            mus, sds = zip(*(gp.predict(X, return_std=True) for gp in self.gps_[i]))
            Z.append(np.column_stack(mus))
            SD.append(np.column_stack(sds))
        Y = self.decode(Z)
        if not return_std:
            return Y
        # independent component errors: var(y) = sum_k sd_k^2 * phi_k^2 + truncation variance (per phase)
        sd = np.hstack([self.sd_scale_[i] * self.scale_[i] *
                        np.sqrt((SD[i] ** 2) @ (self.pcas_[i].components_ ** 2) + self.trunc_var_[i])
                        for i in range(len(PHASES))])
        return Y, sd

    def calibrate(self, X: np.ndarray, Y: np.ndarray, target: float = 0.80) -> np.ndarray:
        """Per phase, scale the sd so `target` of held-out points fall inside the central band
        (z = 1.2816 for 80%). Only widens, never narrows. Uses validation data only."""
        self.sd_scale_ = np.ones(len(PHASES))
        mu, sd = self.predict(X, return_std=True)
        ratio = np.abs(Y - mu) / np.maximum(sd, 1e-12)
        self.sd_scale_ = np.array([max(float(np.quantile(ratio[:, self._sl(i)], target)) / 1.2816, 1.0)
                                   for i in range(len(PHASES))])
        return self.sd_scale_


def score_block(model: str, split: str, Y: np.ndarray, Yhat: np.ndarray, n: int) -> list[dict]:
    rows, Yd, Hd = [], unstack(Y, n), unstack(Yhat, n)
    for k in PHASES:
        end_true, end_pred = Yd[k][:, -1], Hd[k][:, -1]
        rows.append({"model": model, "split": split, "phase": k,
                     "rmse_curve": rmse(Yd[k], Hd[k]), "r2_curve": r2(Yd[k].ravel(), Hd[k].ravel()),
                     "mape_end_2008": mape(end_true, end_pred), "r2_end_2008": r2(end_true, end_pred),
                     "worst_case_rel_err_end": max(endpoint_rel_error([t], [p]) for t, p in zip(end_true, end_pred))
                     if np.all(end_true != 0) else float("nan")})
    return rows


def run(cfg: dict, state: dict) -> dict:
    log = get_logger("s2_proxy", cfg["paths"]["logs"])
    feats, sim_cum = state["features"], state["sim_cum"]
    xc, pc, seed = x_cols(feats), cfg["proxy"], cfg["project"]["random_seed"]
    n = sim_cum["oil"].shape[0]
    ids = {s: feats.index[feats["split"] == s].tolist() for s in ("train", "validation", "test")}
    for s, v in ids.items():
        if not v:
            raise ValueError(f"No cases in the {s} split")
    X = {s: feats.loc[ids[s], xc].to_numpy() for s in ids}
    Y = {s: stack_curves(sim_cum, ids[s]) for s in ids}

    def new_proxy():
        return CurveProxy(n, pc["pca_variance"], pc["kernel"], pc["gp_restarts"], seed, pc["min_components"])

    proxy = new_proxy().fit(X["train"], Y["train"])
    log.info("PCA components per phase %s: %s (variance explained %s)", PHASES, proxy.k_,
             [round(e, 6) for e in proxy.explained_])
    lin = LinearRegression().fit(X["train"], Y["train"])
    knn = KNeighborsRegressor(n_neighbors=1).fit(X["train"], Y["train"])
    z_train = proxy.encode(Y["train"])
    sizes = [z.shape[1] for z in z_train]
    gbr = MultiOutputRegressor(GradientBoostingRegressor(random_state=seed)).fit(X["train"], np.hstack(z_train))

    def gbr_decode(x):
        z = gbr.predict(x)
        return proxy.decode(np.split(z, np.cumsum(sizes)[:-1], axis=1))

    models = {
        "pca_gp": lambda x: proxy.predict(x),
        "linear": lambda x: enforce_monotone(lin.predict(x), n),
        "gboost_pca": gbr_decode,
        "nearest_case": lambda x: knn.predict(x),
    }
    rows = []
    for split in ("validation", "test"):          # test is scored once, never used for tuning
        for name, f in models.items():
            rows += score_block(name, split, Y[split], f(X[split]), n)
    scores = pd.DataFrame(rows)

    # uncertainty calibration: raw 80% band coverage on validation, then scale the sd on validation,
    # and check the calibrated band on test (never used to fit anything)
    def band_cov(px, split):
        mu, sd = px.predict(X[split], return_std=True)
        return float(np.mean(np.abs(Y[split] - mu) <= 1.2816 * np.maximum(sd, 1e-12)))

    raw_cov = band_cov(proxy, "validation")
    factor = proxy.calibrate(X["validation"], Y["validation"])
    scale_txt = " / ".join(f"{f:.4f}" for f in factor)
    calib = pd.DataFrame([{"raw_coverage_validation": raw_cov, "sd_scale_oil_gas_water": scale_txt,
                           "calibrated_coverage_validation": band_cov(proxy, "validation"),
                           "calibrated_coverage_test": band_cov(proxy, "test"), "target": 0.80}])
    scores.to_csv(cfg["paths"]["tables"] / "srq4_proxy_scores.csv", index=False)
    calib.to_csv(cfg["paths"]["tables"] / "srq4_proxy_uncertainty.csv", index=False)
    log.info("Validation scores:\n%s", scores[scores.split == "validation"].round(4).to_string(index=False))
    log.info("Proxy 80%% band: %s", calib.round(3).to_dict("records")[0])

    # final proxy for history matching: refit on all 100 cases, keep the validated calibration factor
    final = new_proxy().fit(feats[xc].to_numpy(), stack_curves(sim_cum, feats.index.tolist()))
    final.sd_scale_ = factor.copy()
    joblib.dump({"proxy": final, "x_cols": xc, "scaler": state["scaler"]}, cfg["paths"]["processed"] / "proxy.joblib")
    return {"proxy": final, "proxy_train_only": proxy, "proxy_scores": scores, "proxy_uncertainty": calib,
            "split_ids": ids}
