# 04 · Formulas

> [!NOTE]
> **Purpose of this file:** every formula the project uses or refers to, numbered (F#) so the methodology, notebooks
> and report can cite them. Formulas marked **used** are computed by the code (the function is named); the rest are
> reference material explaining the physics or methods we did not choose.
> Units: STB = stock-tank barrel, MSCF = 1,000 standard cubic feet, rb = reservoir barrel, 1 bbl = 5.615 ft³,
> rates per day, Δt in days. References [R#] are in [`05_references.md`](05_references.md).

**Contents**
- [Quick index](#quick-index)
- [A. Volumes and saturations](#a-volumes-and-saturations)
- [B. Flow](#b-flow)
- [C. Aquifer support](#c-aquifer-support)
- [D. Production volumes and conventions](#d-production-volumes-and-conventions)
- [E. Forecasting](#e-forecasting)
- [F. Data alignment (SRQ1)](#f-data-alignment-srq1)
- [G. History matching (SRQ2)](#g-history-matching-srq2)
- [H. Machine learning (SRQ3, SRQ4)](#h-machine-learning-srq3-srq4)
- [I. Evaluation and uncertainty](#i-evaluation-and-uncertainty)
- [J. Supporting reservoir-engineering formulas](#j-supporting-reservoir-engineering-formulas)
- [K. Pipeline rules](#k-pipeline-rules)

---

## Quick index

<details>
<summary><b>All 52 formulas and where each is used</b> (click to expand)</summary>

| F# | Name | Section | Used by the code |
|---|---|---|---|
| F1 | Pore volume of a cell | A | ✅ grid check |
| F2 | Porosity multiplier effect | A | ✅ grid check |
| F3 | Oil in place from the grid | A | Reference (needs Bo) |
| F3a | Initial hydrocarbon pore volume | A | ✅ `grid.hcpv`, business table |
| F4 | Oil in place, field form | A | Reference |
| F5 | Saturation closure | A | Reference |
| F6 | Darcy's law | B | Reference |
| F7 | Darcy, field units | B | Reference |
| F8 | Transmissibility (harmonic average) | B | Reference |
| F9 | Permeability and fault multipliers | B | ✅ grid check |
| F10 | Flow between cells | B | Reference |
| F11 | Pot aquifer | C | Reference |
| F12 | Fetkovich aquifer | C | Reference |
| F13 | Solution gas | D | ✅ QC, both forecasters |
| F14 | Observed cumulative | D | ✅ Step 1 |
| F15 | Quarterly accumulation | D | ✅ forecasts, template |
| F16 | Arps decline rate | E | ✅ decline forecaster |
| F16a | Decline anchored to the end of history | E | ✅ decline forecaster |
| F17 | Arps cumulative | E | ✅ decline forecaster |
| F18 | Water–oil ratio trends | E | ✅ decline forecaster |
| F19 | Ershaghi X-plot | E | Reference |
| F20 | Linear interpolation of a cumulative | F | ✅ Step 1 |
| F21 | Average rate from cumulatives | F | ✅ forecasters, end rates |
| F22 | Date conventions | F | ✅ Step 1 |
| F23 | Weighted least-squares misfit (loss) | G | ✅ Steps 1, 3, 5 |
| F24 | GLUE weight | G | ✅ Steps 3, 5 |
| F25 | Bayesian objective | G | Reference |
| F26 | ES-MDA update | G | Reference |
| F27 | Capacitance–resistance model | G | Reference |
| F28 | Min–max scaling | H | ✅ Step 1 |
| F29 | PCA curve compression | H | ✅ Step 2 |
| F30 | Gaussian-process kernels | H | ✅ Step 2 |
| F31 | Sobol first-order index | H | ✅ Step 6 |
| F32 | Sobol total index | H | ✅ Step 6 |
| F33 | RMSE | I | ✅ Step 2 |
| F34 | MAE | I | Reference |
| F35 | MAPE | I | ✅ Step 2 |
| F36 | R² | I | ✅ Step 2 |
| F37 | End-point relative error | I | ✅ Steps 2, 5 |
| F38 | P10–P90 coverage | I | ✅ Steps 2, 5 |
| F39 | Material balance | J | Reference |
| F40 | Water cut | J | ✅ business table |
| F41 | Voidage replacement ratio | J | Reference (needs Bo) |
| F42 | Recovery factor | J | ✅ as N_p / HCPV |
| F43 | Buckley–Leverett fractional flow | J | Reference |
| F44 | Corey relative permeability | J | Reference |
| F45 | Weighted percentile | I | ✅ Steps 3, 5 |
| F46 | Monotone cumulative | I | ✅ proxy, forecasters, template |
| F47 | Proxy uncertainty and calibration | H | ✅ Steps 2, 3 |
| F48 | Autoregressive ML forecaster | E | ✅ Steps 4, 5, 6 |
| F49 | Best-10 diversity rule | K | ✅ Step 5 |
| F50 | Backtest increment error | K | ✅ Steps 4, 5 |

</details>

---

## A. Volumes and saturations

**F1: Pore volume of a cell** [R3][R4] · *used: grid check*
$$\text{PORV}_i = V_{b,i}\,\phi_i\,\text{NTG}_i$$

**F2: Effect of the porosity multiplier** · *used: `grid.check_case`*
$$\phi_i^{case} = M_\phi\,\phi_i \;\Rightarrow\; \text{PORV}_i^{case} = M_\phi\,\text{PORV}_i$$

**F3: Oil in place from the grid** [R16][R17]
$$N = \sum_i \frac{\text{PORV}_i\,S_{o,i}}{B_{o,i}}$$

**F3a: Initial hydrocarbon pore volume** · *used: `grid.hcpv`, business table*
$$\text{HCPV} = \sum_{i\,\in\,\text{active}} \text{PORV}_i\,S_{o,i} = M_\phi\,\text{HCPV}_{base}, \qquad N = \text{HCPV}/B_o$$
HCPV_base = 129,421,914.67 rb. Bo is not given in the data, so the pipeline reports N_p / HCPV.

**F4: Oil in place, classic field form**
$$N\,[\text{STB}] = \frac{7758\,A\,h\,\phi\,(1-S_{wi})}{B_{oi}}$$

**F5: Saturation closure** (holds in the data)
$$S_w + S_o + S_g = 1$$

---

## B. Flow

**F6: Darcy's law**
$$q = -\frac{kA}{\mu}\frac{dp}{dx}$$

**F7: Darcy, field units** (q in bbl/d, k in mD, A in ft², Δp in psi, μ in cP, L in ft) [R16]
$$q = \frac{0.001127\,k\,A\,\Delta p}{\mu\,L}$$

**F8: Transmissibility between neighbouring cells (harmonic average)** [R18]
$$T_{ij} = \frac{C}{\dfrac{\Delta x_i}{2k_iA_i} + \dfrac{\Delta x_j}{2k_jA_j}}$$

**F9: Effect of the permeability and fault multipliers** [R3] · *used: `grid.check_case`*
$$k^{case} = M_k\,k \qquad T^{case}_{fault} = M_{flt}\,T_{fault}$$
In the grid files only the permeability part is visible; the fault multiplier acts on fault faces and is not exported.

**F10: Flow between cells**
$$q_{ij} = T_{ij}\,\lambda\,(p_i - p_j), \qquad \lambda = \frac{k_r}{\mu B}$$

---

## C. Aquifer support

**F11: Pot aquifer** [R16]
$$W_e = (c_w + c_f)\,W_i\,(p_i - p)$$

**F12: Fetkovich finite aquifer** [R19]
$$W_{ei} = c_t\,W_i\,p_i, \qquad \Delta W_{e,n} = \frac{W_{ei}}{p_i}\left(\bar p_{a,n-1} - \bar p_n\right)\left(1 - e^{-J p_i \Delta t / W_{ei}}\right)$$

---

## D. Production volumes and conventions

**F13: Solution gas (undersaturated oil)** · *used: QC, both forecasters*
$$q_g = R_s\,q_o, \qquad G_p = R_s\,N_p, \qquad R_s \approx 0.3633\ \text{MSCF/STB}$$

**F14: Observed cumulative from quarterly rates** · *used: `s1_prepare.observed_cumulative`*
$$N_p(t_n) = \sum_{k} q_{o,k}\,\Delta t_k \quad (\Delta t_k = 90, 91 \text{ or } 92 \text{ days})$$

**F15: Quarterly accumulation (forecast and template)** · *used: both forecasters*
$$Q_n = Q_{n-1} + \bar q_n\,\Delta t_n, \qquad n = 1,\dots,80$$

---

## E. Forecasting

**F16: Arps decline: hyperbolic, exponential (b = 0), harmonic (b = 1)** [R13] · *used: `s4_forecast.arps_rate`, `fit_arps`*
$$q(t) = \frac{q_i}{(1+bD_it)^{1/b}} \qquad q = q_i e^{-D t} \qquad q = \frac{q_i}{1 + D_i t}$$

**F16a: Anchoring the decline to the end of history** · *used: `s4_forecast.fit_forecaster`*
$$q_{end} = q_{fit}(t_{end})\cdot\frac{q_{obs,last}}{q_{fit}(t_{last})}, \qquad D_{end} = \frac{D_i}{1 + b\,D_i\,t_{end}}\ (b>0), \quad D_{end} = D_i\ (b = 0)$$
The forecast restarts the Arps curve at 2008 with rate q_end and decline D_end (same b), so it continues the last
actual rate and the decline rate reached by then. Fitted on period mid-points, 0 ≤ b ≤ 1.

**F17: Arps cumulative** · *used: `s4_forecast.arps_cum`*
$$N_p = \frac{q_i}{(1-b)D_i}\left[1 - (1+bD_it)^{\frac{b-1}{b}}\right] \;(0<b<1) \qquad N_p = \frac{q_i - q}{D} \;(b=0) \qquad N_p = \frac{q_i}{D_i}\ln(1+D_it) \;(b=1)$$

**F18: Water–oil ratio trends** (two forms, chosen by backtest on validation cases) · *used: `s4_forecast.fit_forecaster`*
$$\ln(\text{WOR}) = a + c\,N_p \quad\text{or}\quad \ln(\text{WOR}) = a + c\,t, \qquad \text{WOR} = \frac{q_w}{q_o}, \qquad c \ge 0$$
Fitted by least squares on the fit window (only points with WOR > 10⁻⁴); the intercept is then reset so the line
passes through the last observed WOR (continuity); forecast WOR = min(exp(a + c·x), 100); water volume per quarter =
WOR × oil volume. If a case has too little water to fit, the median (a, c) of the cases that do is used.

**F19: Ershaghi X-plot** [R26]
$$X = \ln\!\left(\frac{1}{f_w} - 1\right) - \frac{1}{f_w}, \qquad N_p = \alpha + \beta X$$

**F48: Autoregressive ML forecaster** · *used: `s4_forecast.fit_ar`, `roll_ar`*
$$\ln\frac{q_{o,k+1}}{q_{o,k}} = g_1(\mathbf x, \ln q_{o,k}, \ln(1+\text{WOR}_k), k), \qquad \ln(1+\text{WOR}_{k+1}) - \ln(1+\text{WOR}_k) = g_2(\cdot)$$
g₁, g₂ = gradient-boosted trees trained on every consecutive quarter pair of the training histories; rolled forward
one quarter at a time. Volumes per quarter: oil q_o·Δt, gas R_s·q_o·Δt (F13), water WOR·q_o·Δt.

---

## F. Data alignment (SRQ1)

**F20: Linear interpolation of a cumulative at a target date** (t_a ≤ t* ≤ t_b) · *used: `s1_prepare.align_cumulative`*
$$Q(t^*) = Q(t_a) + \frac{t^* - t_a}{t_b - t_a}\,\big(Q(t_b) - Q(t_a)\big)$$

**F21: Average rate from cumulatives** · *used: `s4_forecast.period_table`, `s5_best10.end_rates`*
$$\bar q_k = \frac{Q(t_k) - Q(t_{k-1})}{t_k - t_{k-1}}$$

**F22: Two date conventions for observed rates** · *used: `s1_prepare.observed_cumulative`*
$$\text{start: } Q(t_n) = \sum_{k<n} q_k\,(t_{k+1}-t_k) \qquad \text{end: } Q(t_n) = \sum_{k\le n} q_k\,(t_k - t_{k-1})$$

---

## G. History matching (SRQ2)

> [!IMPORTANT]
> **F23 is the loss function** that drives the method: it scores how badly a parameter set's production disagrees
> with the observed field. It is used to choose the date convention (Step 1), to rank cases, run the optimiser and
> weight the posterior (Step 3), and in the whole-pipeline backtest (Step 5).

**F23: Weighted least-squares misfit of case j** · *used: `metrics.misfit`, `metrics.sigma_matrix`*
$$O_j = \frac{1}{T}\sum_{k\in\{o,g,w\}} w_k\sum_{t=1}^{T}\frac{\left(Q^{obs}_{t,k} - Q^{(j)}_{t,k}\right)^2}{\sigma_{t,k}^2 + s_{t,k}^2}, \qquad \sigma_{t,k} = \max\!\left(0.05\,|Q^{obs}_{t,k}|,\ 0.01\max_t|Q^{obs}_{t,k}|\right)$$

| Symbol | Meaning | Value |
|---|---|---|
| T | Number of observed dates | 41 |
| w_k | Phase weight | 1 for oil, gas and water |
| σ | Observation error; the floor stops near-zero early volumes dividing by ~0 | 5% of the observed value, floor 1% of the phase maximum (sensitivity: 3%, 10%) |
| s | Proxy predictive sd (F47) | From the GP when the candidate comes from the proxy; 0 when a simulated case is scored directly |

Reading the number: a prediction 2% off at every date in every phase gives O = 3 × (2/5)² = 0.48; a perfect match
gives 0.

**F24: GLUE likelihood weight** [R23] · *used: `metrics.glue_weights`*
$$w_j = \frac{\exp(-O_j/2)}{\sum_i \exp(-O_i/2)} = \frac{\exp\!\big(-(O_j - O_{min})/2\big)}{\sum_i \exp\!\big(-(O_i - O_{min})/2\big)}$$
The second form is what the code computes: identical result, no numerical underflow.

**F25: Bayesian objective** [R1][R7]
$$O(\mathbf m) = \tfrac12(\mathbf m - \mathbf m_{pr})^{T}C_M^{-1}(\mathbf m - \mathbf m_{pr}) + \tfrac12\big(g(\mathbf m) - \mathbf d_{obs}\big)^{T}C_D^{-1}\big(g(\mathbf m) - \mathbf d_{obs}\big)$$

**F26: ES-MDA update** (Σ 1/α_i = 1) [R9]
$$\mathbf m_j^{a} = \mathbf m_j^{f} + C_{MD}\left(C_{DD} + \alpha C_D\right)^{-1}\left(\mathbf d_{obs} + \sqrt{\alpha}\,\mathbf e_j - \mathbf d_j\right)$$

**F27: Capacitance–Resistance Model** [R27]
$$q(t_n) = q(t_{n-1})\,e^{-\Delta t/\tau} + \left(1 - e^{-\Delta t/\tau}\right) f\,I(t_n)$$

---

## H. Machine learning (SRQ3, SRQ4)

**F28: Min–max scaling** · *used: `utils.ParamScaler`*
$$\tilde x = \frac{x - x_{min}}{x_{max} - x_{min}}$$
The permeability multiplier is replaced by ln(multiplier) first (its range spans ~19×); x_min and x_max are the
minimum and maximum over the 100 cases' input parameters (inputs only, no outputs).

**F29: PCA curve compression (one PCA per phase)** · *used: `s2_proxy.CurveProxy`*
$$\mathbf y_p(\mathbf x) \approx c_p\Big[\bar{\mathbf y}_p + \sum_{k=1}^{K_p} z_{p,k}(\mathbf x)\,\boldsymbol\phi_{p,k}\Big], \qquad p \in \{oil, gas, water\}$$
y_p = the phase's 41-date cumulative curve divided by c_p (its maximum over the cases the proxy is fitted on).
K_p = the smallest number of components explaining ≥ 99.999% of that phase's variance, but at least 3. Decoded curves
are clipped at 0 and made non-decreasing (running maximum).

**F30: Gaussian-process kernels** [R12] · *used: `s2_proxy.CurveProxy._kernel`*
$$k_{RBF}(\mathbf x,\mathbf x') = \sigma_f^2\exp\!\left(-\tfrac{r^2}{2\ell^2}\right) \qquad k_{M5/2}(r) = \sigma_f^2\left(1 + \tfrac{\sqrt5 r}{\ell} + \tfrac{5r^2}{3\ell^2}\right)\exp\!\left(-\tfrac{\sqrt5 r}{\ell}\right), \quad r = \lVert\mathbf x - \mathbf x'\rVert$$
Used: constant × Matérn 5/2 with one length scale per input (ARD) + white noise; hyper-parameters by maximum
marginal likelihood (3 restarts); one GP per PCA score z_{p,k}.

**F47: Proxy predictive uncertainty and its calibration** · *used: `CurveProxy.predict`, `CurveProxy.calibrate`*
$$s_{t,p} = \lambda_p\,c_p\sqrt{\sum_{k} \mathrm{sd}_{p,k}^2\,\phi_{p,k,t}^2 + v^{trunc}_{p,t}}, \qquad \lambda_p = \max\!\left(1,\ \frac{q_{0.80}\big(|y - \hat y|/s\big)}{1.2816}\right)$$
sd_{p,k} = GP standard deviation of score k; v^trunc = mean squared PCA reconstruction error on the training curves.
λ_p is computed on validation cases only, so that ~80% of held-out points fall inside ±1.2816 s (the 80% band); it
can only widen the band. Checked once on test cases.

**F31: Sobol first-order index** [R15] · *used: `s6_sensitivity.run` (SALib)*
$$S_i = \frac{\operatorname{Var}\big(\mathbb E[Y\mid X_i]\big)}{\operatorname{Var}(Y)}$$

**F32: Sobol total index** · *used: `s6_sensitivity.run` (SALib)*
$$S_{T_i} = 1 - \frac{\operatorname{Var}\big(\mathbb E[Y\mid X_{\sim i}]\big)}{\operatorname{Var}(Y)}$$

---

## I. Evaluation and uncertainty

**F33: RMSE** · *used: `metrics.rmse`*
$$\text{RMSE} = \sqrt{\tfrac1n\textstyle\sum (y - \hat y)^2}$$

**F34: MAE** (reference only; we report MAPE because the three phases differ in scale)
$$\text{MAE} = \tfrac1n\textstyle\sum |y - \hat y|$$

**F35: MAPE** (points where y ≈ 0 are excluded) · *used: `metrics.mape`*
$$\text{MAPE} = \tfrac{100}{n}\textstyle\sum \left|\frac{y - \hat y}{y}\right|$$

**F36: Coefficient of determination** · *used: `metrics.r2`*
$$R^2 = 1 - \frac{\sum (y - \hat y)^2}{\sum (y - \bar y)^2}$$

**F37: End-point relative error** · *used: `metrics.endpoint_rel_error`, `s5_best10.pipeline_backtest`*
$$\varepsilon_{end} = \frac{|Q(t_{end}) - \hat Q(t_{end})|}{Q(t_{end})}$$
t_end = the last date with known truth: 2008-01-01 for the proxy and for the 2004 → 2008 backtests.

**F38: Coverage of the P10–P90 band** (target ≈ 0.8) · *used: `metrics.coverage`*
$$\text{Cov} = \frac1n\textstyle\sum \mathbb 1\left[P_{90} \le y \le P_{10}\right]$$

**F45: Weighted percentile (P90 / P50 / P10), interpolated** · *used: `utils.weighted_quantile`*
$$F_m = \frac{\sum_{i\le m} w_{(i)} - \tfrac12 w_{(m)}}{\sum_i w_{(i)}}, \qquad P_p = \text{linear interpolation of } y_{(m)} \text{ at } F = p$$
y sorted ascending; members with zero weight are dropped first; equal weights for the best 10, F24 weights for the
posterior. Petroleum convention: P90 = low case = the 10th percentile of the distribution.

**F46: Monotone cumulative via non-negative increments** · *used: `s2_proxy.enforce_monotone`, forecasters, `deliverable.run` (check)*
$$Q_{t} = Q_{t-1} + \Delta Q_t, \qquad \Delta Q_t \ge 0$$
Guaranteed three ways: proxy curves are clipped at 0 and replaced by their running maximum (F29); decline forecasts
add Arps volumes, which are positive (F17); ML forecasts add q_o·Δt with q_o = q_o·e^{(·)} > 0 and WOR ≥ 0 (F48). The
template step checks it again before writing.

---

## J. Supporting reservoir-engineering formulas

**F39: Material balance (Havlena–Odeh)** [R20]
$$F = N\,(E_o + mE_g + E_{f,w}) + W_e + W_{inj}B_w, \qquad F = N_p\big[B_o + (R_p - R_s)B_g\big] + W_pB_w$$

**F40: Water cut** · *used: `s5_best10.end_rates`*
$$f_w = \frac{q_w}{q_o + q_w}$$

**F41: Voidage replacement ratio**
$$\text{VRR} = \frac{W_{inj}B_w}{N_pB_o + W_pB_w + (G_p - N_pR_s)B_g}$$

**F42: Recovery factor** · *used as N_p / HCPV: `s5_best10.run`*
$$RF = \frac{N_p}{N} = \frac{N_p\,B_o}{\text{HCPV}}$$
Reported as N_p / HCPV in STB/rb because Bo is unknown.

**F43: Buckley–Leverett fractional flow** (no gravity, no capillarity) [R21]
$$f_w = \frac{1}{1 + \dfrac{k_{ro}\,\mu_w}{k_{rw}\,\mu_o}}$$

**F44: Corey relative permeability** (S_wc = 0.2 in the data) [R22]
$$k_{rw} = k_{rw}^{max}\left(\frac{S_w - S_{wc}}{1 - S_{wc} - S_{orw}}\right)^{n_w}$$

---

## K. Pipeline rules

**F49: Diversity rule for the best 10** · *used: `s5_best10.pick_diverse`*
Take candidates in order of increasing misfit; accept one only if its Euclidean distance to every accepted one, in the
scaled 4-parameter space (F28), is ≥ 0.05; stop at 10 (if fewer qualify, fill with the next-best misfits).

**F50: Backtest increment error** (chooses the water trend and the forecast method) · *used: `s4_forecast.run`, `s5_best10.pipeline_backtest`*
$$e = \frac{\big|\Delta\hat Q - \Delta Q\big|}{\Delta Q} = \frac{\big|\hat Q(2008) - Q(2008)\big|}{Q(2008) - Q(2004)}, \qquad \Delta Q = Q(2008) - Q(2004)$$
Q = the simulator's truth for case backtests, the observed field for the whole-pipeline backtest; both forecasts start
from the same Q(2004), so the two forms are equal. Mean over validation cases: water only for the water trend, oil +
water for the method. Reported (not used to choose) on test cases.
