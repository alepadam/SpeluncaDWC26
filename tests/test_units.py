"""Unit tests for the formulas and helpers the pipeline relies on."""

import numpy as np
import pandas as pd
import pytest

from src.metrics import glue_weights, misfit, sigma_matrix
from src.s1_prepare import align_cumulative, observed_cumulative
from src.s4_forecast import arps_cum, arps_rate, fit_arps, fit_forecaster, forecast_from_fit
from src.s5_best10 import pick_diverse
from src.utils import ParamScaler, norm_case, weighted_quantile


@pytest.mark.parametrize("b", [0.0, 0.3, 0.5, 1.0])
def test_arps_cumulative_matches_numerical_integral(b):
    qi, di = 15000.0, 0.0008
    t = np.linspace(0, 7300, 200001)
    rate = arps_rate(t, qi, di, b)
    numeric = np.concatenate([[0.0], np.cumsum((rate[1:] + rate[:-1]) / 2 * np.diff(t))])
    assert arps_cum(t[-1], qi, di, b) == pytest.approx(numeric[-1], rel=1e-6)


def test_fit_arps_recovers_known_parameters():
    t = np.linspace(0, 1500, 17)
    q = arps_rate(t, 9000.0, 0.0012, 0.6)
    qi, di, b = fit_arps(t, q)
    assert (qi, di, b) == pytest.approx((9000.0, 0.0012, 0.6), rel=1e-3)


def test_observed_cumulative_conventions():
    idx = pd.to_datetime(["2000-01-01", "2000-04-01", "2000-07-01"])
    obs = pd.DataFrame({"oil": [1.0, 1.0, 1.0], "gas": [0.0] * 3, "water": [0.0] * 3, "winj": [0.0] * 3}, index=idx)
    start = observed_cumulative(obs, "start")["oil"].to_numpy()
    end = observed_cumulative(obs, "end")["oil"].to_numpy()
    assert start.tolist() == [0.0, 91.0, 182.0]   # 2000: Jan-Mar = 91 days (leap), Apr-Jun = 91
    assert end.tolist() == [0.0, 91.0, 182.0]
    obs.loc[idx[0], "oil"] = 5.0                    # only 'start' uses the first rate
    assert observed_cumulative(obs, "start")["oil"].iloc[1] == 455.0
    assert observed_cumulative(obs, "end")["oil"].iloc[1] == 91.0


def test_align_cumulative_interpolates_each_column_on_its_own_points():
    stamps = pd.to_datetime(["2000-01-01", "2000-02-15", "2000-03-10", "2000-04-01"])
    raw = pd.DataFrame({"A": [0.0, 45.0, np.nan, 91.0], "B": [0.0, np.nan, 69.0, 182.0]}, index=stamps)
    out = align_cumulative(raw, pd.to_datetime(["2000-01-01", "2000-04-01"]))
    assert out["A"].tolist() == [0.0, 91.0]
    assert out["B"].tolist() == [0.0, 182.0]
    mid = align_cumulative(raw, pd.to_datetime(["2000-03-01"]))
    assert mid["A"].iloc[0] == pytest.approx(45.0 + (91 - 45) * 15 / 46)


def test_align_cumulative_rejects_dates_outside_the_data():
    raw = pd.DataFrame({"A": [1.0, 2.0]}, index=pd.to_datetime(["2000-02-01", "2000-03-01"]))
    with pytest.raises(ValueError):
        align_cumulative(raw, pd.to_datetime(["2000-01-01"]))


def test_misfit_is_zero_for_a_perfect_match_and_weights_sum_to_one():
    obs = {k: np.array([0.0, 10.0, 20.0]) for k in ("oil", "gas", "water")}
    sig = sigma_matrix(obs, 0.05, 0.01)
    assert float(misfit(obs, obs, sig, {})) == 0.0
    sims = {k: np.vstack([v, v * 1.1]) for k, v in obs.items()}
    s = misfit(obs, sims, sig, {})
    assert s[0] == 0.0 and s[1] > 0
    assert glue_weights(s).sum() == pytest.approx(1.0)


def test_weighted_quantile():
    vals = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert weighted_quantile(vals, [0.5])[0] == pytest.approx(3.0)
    w = np.array([0, 0, 0, 0, 1.0])
    assert weighted_quantile(vals, [0.1, 0.9], w).tolist() == [5.0, 5.0]


def test_pick_diverse_keeps_distance_and_order():
    X = np.array([[0.0, 0.0], [0.01, 0.0], [0.5, 0.5], [0.9, 0.9]])
    scores = np.array([0.1, 0.2, 0.3, 0.4])
    assert pick_diverse(X, scores, 3, 0.05) == [0, 2, 3]
    assert pick_diverse(X, scores, 4, 0.05) == [0, 2, 3, 1]   # falls back to next best when short


def test_param_scaler_round_trip():
    raw = pd.DataFrame({"a": [1.0, 2.0, 3.0], "p": [0.5, 2.0, 9.0]})
    sc = ParamScaler(["a", "p"], ["p"]).fit(raw)
    x = sc.transform(raw)
    assert x.min() == 0.0 and x.max() == 1.0
    assert sc.inverse(x) == pytest.approx(raw.to_numpy())


def test_norm_case():
    assert norm_case("Case_7") == "CASE 7"
    assert norm_case(" case 12 ") == "CASE 12"
    assert norm_case("RAMP_History") == "RAMP HISTORY"


def test_forecast_continues_history_and_never_decreases():
    idx = pd.date_range("2000-01-01", "2008-01-01", freq="QS-JAN")
    t = (idx - idx[0]).days.to_numpy(float)
    oil = arps_cum(t, 10000.0, 0.0005, 0.5)
    curves = {"oil": pd.Series(oil, index=idx), "gas": pd.Series(0.3633 * oil, index=idx),
              "water": pd.Series(0.02 * oil * (t / t[-1]) ** 2, index=idx)}
    cfg_f = {"min_points": 6, "b_bounds": [0.0, 1.0], "wor_min": 1e-4}
    fit = fit_forecaster(curves, "2004-01-01", cfg_f, 0.3633)
    dates = pd.date_range("2008-04-01", "2028-01-01", freq="QS-JAN")
    for model in ("wor_vs_np", "wor_vs_time"):
        p = forecast_from_fit(fit, dates, 100.0, model)
        for k in p:
            assert np.all(np.diff(np.concatenate([[curves[k].iloc[-1]], p[k]])) >= 0)
        assert p["gas"][-1] - curves["gas"].iloc[-1] == pytest.approx(
            0.3633 * (p["oil"][-1] - curves["oil"].iloc[-1]), rel=1e-6)
    # oil: hyperbolic continuation matches the exact analytic future volume
    exact = arps_cum((dates[-1] - idx[0]).days, 10000.0, 0.0005, 0.5)
    assert p["oil"][-1] == pytest.approx(exact, rel=2e-3)


def test_grid_column_codes_and_case_comparison():
    from src.grid import column_codes, compare_cases, hcpv

    header = ["I", "Pore Volume (PORV)", "Porosity (PORO)", " Connateg  Gas Saturation (SGL)", "Perm X (PERMX)",
              "Pressure (PRESSURE)", "Water Sat (SWAT)", "Oil Sat (SOIL)", "Rs (RS)"]
    cols = column_codes(header)
    assert cols["PORV"] == 1 and cols["SGL"] == 3 and cols["I"] == 0
    cols = {"I": 0, "J": 1, "K": 2, **{k: v + 2 for k, v in cols.items() if k != "I"}}

    rng = np.random.default_rng(0)
    n = 40
    a = np.column_stack([np.arange(n), np.zeros(n), np.zeros(n),
                         rng.uniform(1, 2, n), rng.uniform(0.1, 0.3, n), np.full(n, 0.2),
                         rng.uniform(10, 100, n), np.full(n, 3000.0), np.full(n, 0.3), np.full(n, 0.7),
                         np.full(n, 0.36)])
    a[0, 3] = 0.0                                                   # one inactive cell
    b = a.copy()
    b[:, [3, 4]] *= 1.1                                             # porosity x1.1
    b[:10, 6] *= 2.0                                                # perm region x2
    b[30:, 3] *= 3.0                                                # aquifer cells x3 (on top of porosity)
    pa = {"Porosity Multiplier": 1.0, "Permeability Multiplier": 1.0, "Aquifer Pore Volume": 1.0}
    pb = {"Porosity Multiplier": 1.1, "Permeability Multiplier": 2.0, "Aquifer Pore Volume": 3.0}
    out = compare_cases((cols, a), (cols, b), pa, pb)
    assert out["same_cells"] and out["same_active_set"] and out["initial_state_identical"]
    assert out["poro_ratio"] == pytest.approx(out["poro_ratio_expected"])
    assert out["perm_region_cells"] == 9 and out["perm_ratio"] == pytest.approx(2.0)   # cell 0 inactive
    assert out["aquifer_cells"] == 10 and out["aquifer_ratio"] == pytest.approx(out["aquifer_ratio_expected"])
    assert hcpv(cols, a) == pytest.approx(float(np.sum(a[1:, 3] * 0.7)))


def test_grid_check_case_detects_multipliers_and_absent_fault():
    from src.grid import check_case, layout_summary, ratios, region_masks

    names = ["I Index", "J Index", "K Index", "Z Coordinate", "PORV", "PORO", "PERMX", "PERMY", "PERMZ",
             "TRANX", "TRANY", "SOIL", "PRESSURE"]
    cols = {n: i for i, n in enumerate(names)}
    rng = np.random.default_rng(1)
    n = 60
    a = np.column_stack([np.arange(n), np.zeros(n), np.arange(n) % 3, -np.linspace(7500, 9000, n),
                         rng.uniform(1, 2, n), rng.uniform(0.1, 0.3, n), rng.uniform(10, 100, n),
                         rng.uniform(10, 100, n), rng.uniform(1, 10, n), rng.uniform(1, 5, n), rng.uniform(1, 5, n),
                         np.r_[np.full(20, 0.7), np.zeros(40)], np.full(n, 3000.0)])
    p0 = {"Porosity Multiplier": 1.0, "Permeability Multiplier": 1.0, "Aquifer Pore Volume": 1.0,
          "Fault Transmissibility": 1.0}
    p1 = {"Porosity Multiplier": 1.2, "Permeability Multiplier": 2.0, "Aquifer Pore Volume": 3.0,
          "Fault Transmissibility": 5.0}
    b = a.copy()
    b[:, [4, 5]] *= 1.2
    b[10:30, [6, 7, 9, 10]] *= 2.0                     # permeability region (and its transmissibilities)
    b[50:, 4] *= 3.0                                     # aquifer cells
    m = region_masks((cols, a), (cols, b), 1.2)
    assert m["perm_region"].sum() == 20 and m["aquifer"].sum() == 10 and m["oil_zone"].sum() == 20
    out = check_case((cols, a), (cols, b), m, ratios(p0, p1))
    assert out["same_active_cells"] and out["PORO_max_rel_err"] < 1e-12 and out["PORV_max_rel_err"] < 1e-12
    assert out["unchanged_cols_max_abs_diff"] == 0 and out["tran_cells_unexplained"] == 0
    assert out["fault_testable"] and out["fault_scaled_cells"] == 0          # fault ratio 5 is outside [1, 2]
    c = b.copy()
    c[0, 9] *= 5.0                                       # a cell scaled by the fault ratio is detected
    assert check_case((cols, a), (cols, c), m, ratios(p0, p1))["fault_scaled_cells"] == 1
    lay = layout_summary((cols, a), m)
    assert lay["aquifer"]["cells"] == 10 and lay["aquifer"]["in_oil_zone"] == 0
    assert lay["perm_region"]["in_oil_zone"] == 10 and lay["oil_zone"]["i_range"] == (0, 19)
