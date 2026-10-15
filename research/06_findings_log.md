# 06 · Findings Log

> [!NOTE]
> **Purpose of this file:** every result from running the notebooks on the real dataset, with the file that holds the
> evidence (`outputs/tables/`, `outputs/figures/`). Hypotheses are in
> [`01_research_questions.md`](01_research_questions.md).
> First full run: 14 Oct 2026. Grid study (files 03 and 08) and full re-run: 15 Oct 2026.

> [!WARNING]
> The numbers below are derived from competition data. Keep this repository **private**.

**Contents**
1. [Headline results](#1-headline-results)
2. [Data facts (EDA)](#2-data-facts-eda)
3. [SRQ1: Time alignment](#3-srq1-time-alignment)
4. [SRQ4: Proxy accuracy](#4-srq4-proxy-accuracy)
5. [SRQ2: History matching](#5-srq2-history-matching)
6. [SRQ5: Forecasting](#6-srq5-forecasting)
7. [SRQ6: Best 10 and uncertainty](#7-srq6-best-10-and-uncertainty)
8. [SRQ3: Parameter influence](#8-srq3-parameter-influence)
9. [Grid files](#9-grid-files)
10. [Open questions](#10-open-questions)

---

## 1. Headline results

> [!IMPORTANT]
> - The ML proxy reproduces the simulator to **0.038% (oil) and 0.094% (water)** on unseen test cases.
> - History matching pins down **porosity**; fault, permeability and aquifer stay uncertain (non-unique).
> - Tested against the **real field** (match to 2004, forecast to 2008), the method's P50 is within **0.8% for oil**
>   and **5.7% for water**.
> - Best-10 P50 cumulative oil by 2028: **59.0 M STB**; remaining oil 2008–2028: **20.4–21.1 M STB**.
> - After matching, the largest uncertainty is **which forecasting method** is used, not the parameters.

| Metric | Oil | Gas | Water | Source |
|---|---|---|---|---|
| Proxy test MAPE at 2008 | 0.038% | 0.038% | 0.094% | `srq4_proxy_scores.csv` |
| Forecast backtest error, ML (test cases) | 3.9% | 3.9% | 6.9% | `srq5_backtest_summary.csv` |
| Whole-pipeline P50 error vs the field | 0.8% | 0.8% | 5.7% | `srq6_pipeline_backtest.csv` |
| Best-10 P50 at 2028 | 59.0 M STB | 21.4 M MSCF | 79.8 M STB | `srq6_spread_2028.csv` |

---

## 2. Data facts (EDA)

From `01_eda.ipynb`.

| Finding | Evidence |
|---|---|
| `02 Field Production` has 8 sheets: Plots, Field Production, and cumulative + rate sheets for gas, oil, water. **No pressure sheet** | `field_sheets.csv` |
| Curve sheets: 11,096 irregular timestamps × 100 cases, 98.45% blank, 1998-01-01 → 2008-01-01; no data after 2008 | 01_eda §4 |
| Inputs varied independently (largest correlation between parameters 0.17); permeability spans 19× | 01_eda §2 |
| A few validation/test cases lie slightly outside the training range (validation permeability by 3.2%, fault by 0.7%; test permeability by 1.7% of the range) | 01_eda §2 |
| Observed field: oil peaks at 15,508 STB/d (1998), falls 67% by 2008; water from 1999, exceeds oil from 2006-04-01, water cut 61% by 2008 | 01_eda §3 |
| `RAMP_History` equals the observed history (relative difference ≤ 3e-8 at 2008 under the "start" convention) | `srq1_convention_test.csv` |
| Gas–oil ratio is 0.3632–0.3633 MSCF/STB in all 100 cases (observed 0.3630–0.3636) → produced gas is solution gas | `qc_report.csv` |
| Over 1998–2008 the porosity multiplier dominates every phase (Spearman ρ = +0.993 oil, −0.995 water); the other parameters have |ρ| ≤ 0.15 | 01_eda §7 |
| All 100 cases produce identical volumes until 1999-04-01; the field lies inside the cases' range on every date | 01_eda §8 |

---

## 3. SRQ1: Time alignment

**Verdict:** ✅ the "start" convention.

| Finding | Evidence |
|---|---|
| "Start" convention (rate stamped at the start of its quarter) fits **85× better**: median misfit of the 10 best cases 0.082 vs 6.900 | `srq1_convention_test.csv` |
| `RAMP_History` difference: 1.7e-8 ("start") vs 2.6e-2 ("end") | `srq1_convention_test.csv` |
| No data-quality failures (0 of 7 checks): cumulatives never decrease, no negatives, gas–oil ratio within 2% | `qc_report.csv` |

---

## 4. SRQ4: Proxy accuracy

**Verdict:** ✅ accuracy and ✅ calibrated uncertainty.

| Finding | Evidence |
|---|---|
| Per-phase PCA keeps 5 components per phase (99.9995% of variance) | 02_pipeline Step 2 |
| Validation MAPE at 2008: oil 0.023%, gas 0.020%, water 0.104%; best baseline (gradient boosting) 0.51–0.66% → **6–26× better** | `srq4_proxy_scores.csv` |
| Test MAPE at 2008: oil 0.038%, gas 0.038%, water 0.094%; worst single test case 0.56% | `srq4_proxy_scores.csv` |
| 80% band coverage: 80.8% on validation, **78.2% on test** (scale factors 1.0000 / 1.0000 / 1.0012) | `srq4_proxy_uncertainty.csv` |
| A single shared PCA (first attempt) kept 1 component and lost the minor parameters — fixed by per-phase PCA | Method note |

---

## 5. SRQ2: History matching

**Verdict:** ✅ optimum beats every case · ✅ non-unique · ✅ stable to the error assumption.

| Finding | Evidence |
|---|---|
| Best simulated case: **CASE 40** (misfit 0.0619). Proxy optimum: misfit **0.0569**, 8.1% lower | `srq2_optimum.csv` |
| The 15 accepted cases: 9 train, 3 validation, 3 test; water contributes a median 91% of their misfit — the hardest phase to match | `srq2_case_misfit.csv` |
| Changing the observation error to 3% or 10% keeps 15 of 15 accepted cases | `srq2_sigma_sensitivity.csv` |
| The optimum sits at the edge of the design range for fault, permeability and aquifer — the poorly identified parameters, where the misfit is nearly flat | `srq2_optimum.csv` |
| Posterior weights vary only 1.016× across the 500 kept samples (misfit averaged over dates) → in effect the best 500 of 20,000, almost equally weighted | `srq2_posterior_samples.csv` |

**Identifiability** (weighted P10–P90 of the posterior as a share of the design range):

| Parameter | Posterior P10–P90 | Share of range | Identified? |
|---|---|---|---|
| Porosity Multiplier | 1.334–1.379 | **7%** | ✅ Yes |
| Fault Transmissibility | 0.0588–0.137 | 78% | ❌ No |
| Permeability Multiplier | 0.820–7.92 | 77% | ❌ No |
| Aquifer Pore Volume | 76.9–187.8 | 76% | ❌ No |

---

## 6. SRQ5: Forecasting

**Verdict:** ⚠️ Arps fits sit at b ≈ 1 · ✅ WOR vs cumulative oil · ✅ gas = Rs × oil · ❌ physics decline is not the
best extrapolator.

| Finding | Evidence |
|---|---|
| Water trend chosen on validation: ln(WOR) vs cumulative oil, increment error **19.9%** vs 103.6% for the time trend | `srq5_backtest_summary.csv` |
| **ML autoregressive beats decline** on validation (oil + water increment error 5.5% vs 13.2%; naive 33.1%) → selected | `srq5_method_selection.csv` |
| Same winner on test cases (not used for the choice): ML 5.4%, decline 12.2% | `srq5_backtest_cases.csv` |
| Arps exponent b: median 0.994; all 100 cases have b > 0.95 (decline flattening toward harmonic) | `srq5_all_cases_2028.csv` |
| Decline gives more 2028 oil than ML in 100% of cases — the method choice shifts the forecast systematically | `srq5_all_cases_2028.csv` |

---

## 7. SRQ6: Best 10 and uncertainty

**Verdict:** ✅ narrower after matching · ⚠️ small parameter range remains · ❌ band coverage (excludes method error).

| Finding | Evidence |
|---|---|
| Best 10: porosity 1.302–1.341 (tight); permeability 4.60–9.78, aquifer 54–157, fault 0.059–0.150 (wide) | `srq6_best10.csv` |
| Matching narrows the 2028 P10–P90 range **9–18×** (oil: 18.9 M → 1.05 M STB) | `srq6_spread_2028.csv` |
| Posterior P10–P90 range is only 1.8% (oil), 1.8% (gas), 3.1% (water) of its P50 | `srq6_spread_2028.csv` |
| **Model-form uncertainty exceeds parameter uncertainty:** best-10 P50 at 2028 — oil 59.0 M (ML) vs 61.3 M (decline) STB; water 79.8 M vs 94.2 M STB (gap 5.8× the posterior range) | `srq6_spread_2028.csv` |
| Whole-pipeline backtest vs the real field: P50 error oil 0.8%, gas 0.8%, water 5.7%; band coverage oil 0%, gas 0%, water 6% → the band covers parameter uncertainty only | `srq6_pipeline_backtest.csv` |
| Remaining oil 2008–2028: 20.39–21.06 M STB; 2028 oil rate 1,076–1,164 STB/d; water cut 89.8–90.2%; WOR cap reached in 0 of 10 | `srq6_business.csv` |
| HCPV 168.5–173.5 M rb; N_p(2028) / HCPV = 0.339–0.350 STB/rb | `srq6_business.csv` |

---

## 8. SRQ3: Parameter influence

**Verdict:** ❌ breakthrough is driven by porosity · ✅ porosity drives long-term oil · ✅ fault has the smallest effect.

| Finding | Evidence |
|---|---|
| Porosity's Sobol total index is **0.96–0.99** for every output | `srq3_sobol.csv` |
| For 2028 water: porosity 0.959 > aquifer 0.040 > permeability 0.016 > fault 0.000; the aquifer's share grows 6× from 2008 (0.007) to 2028 | `srq3_sobol.csv` |
| Interactions are small (largest S_T − S₁ = 0.026) | `srq3_sobol.csv` |
| Water-breakthrough date correlates most with porosity (ρ = +0.854); permeability −0.189, aquifer −0.055 | `srq3_spearman.csv` |

---

## 9. Grid files

From `01_eda.ipynb` §9 and `src/grid.check_case`; details in [`02_data_facts.md` §6](02_data_facts.md#6-grid-workbooks-0308).

| Finding | Evidence |
|---|---|
| **No information beyond the 4 parameters (35 cases, cell by cell):** every case = Case 1 × its porosity, permeability and aquifer ratios (largest error 2.7e-5 = export rounding); 23 of 29 columns identical; TRANX/TRANY follow permeability in 100% of cells; HCPV within 2e-9 | 01_eda §9 |
| **Fault multiplier absent from the grid files:** 0 cells change by the fault ratio in the 19 cases where it is distinguishable | 01_eda §9 |
| **Layout:** aquifer = 2,286 edge cells below the oil holding 83.5% of the pore volume; oil zone 4.2%; permeability region in lower layers K 13–31, mostly below the oil — explains why aquifer and permeability matter more for 2028 water | 01_eda §9 |
| First two-case check: Case 2 vs Case 1 — PORO ratio 1.135898 (expected 1.135899), PERMX/Y ratio 2.085115 in 11,575 cells (expected 2.085115), aquifer PORV ratio 1.994053 in 2,286 cells (expected 1.994053) | 01_eda §9 |

---

## 10. Open questions

| Question | Status | Answer / source |
|---|---|---|
| Template Case 1–10 meaning | ✅ Resolved | Our best 10 forecasts (Kick Off slide 31) |
| Simulation data after 2008? | ✅ Resolved: no | Curves end 2008-01-01 |
| Pressure sheet in `02`? | ✅ Resolved: no | `field_sheets.csv` |
| Meaning of `RAMP_History` | ✅ Resolved | = observed history |
| One-quarter offset | ✅ Resolved | "Start" convention |
| Grid columns / snapshot date | ✅ Resolved | 29 columns; initial state, identical in every case |
| Do grids add information beyond the 4 parameters? | ✅ Resolved: no | 35 of 100 cases checked; run `01_eda` §9 with `GRID_SCOPE = "all"` for files 04–07 |
| Oil formation volume factor Bo | Not in the data | Recovery reported as N_p / HCPV |
| Exact accuracy metric used for judging | ⏳ **Open** | Slide 35 only says "accuracy of model output" — ask the organisers |
