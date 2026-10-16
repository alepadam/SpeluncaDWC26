# 05 · References

> [!NOTE]
> **Purpose of this file:** the published sources cited as [R#] in the methodology and formulas, and the primary
> challenge material.

> [!WARNING]
> These references were cited from knowledge, **not** looked up online for this file. Verify volume and page numbers
> before using them in the final report.

**Contents**
- [History matching and data assimilation](#history-matching-and-data-assimilation)
- [Proxy and surrogate modelling, machine learning](#proxy-and-surrogate-modelling-machine-learning)
- [Experimental design and sensitivity analysis](#experimental-design-and-sensitivity-analysis)
- [Reservoir engineering](#reservoir-engineering)
- [Software and standards](#software-and-standards)
- [Challenge material (primary data)](#challenge-material-primary-data)

---

## History matching and data assimilation

| ID | Reference | Used for |
|---|---|---|
| R1 | Oliver, D.S. & Chen, Y. (2011). Recent progress on reservoir history matching: a review. *Computational Geosciences*, 15(1), 185–221. | Research design; non-uniqueness; F25 |
| R2 | Schulze-Riegert, R. & Ghedan, S. (2007). Modern techniques for history matching. *9th International Forum on Reservoir Simulation*, Abu Dhabi. | Background |
| R7 | Oliver, D.S., Reynolds, A.C. & Liu, N. (2008). *Inverse Theory for Petroleum Reservoir Characterization and History Matching*. Cambridge University Press. | F25 |
| R8 | Evensen, G. (1994). Sequential data assimilation with a nonlinear quasi-geostrophic model using Monte Carlo methods to forecast error statistics. *Journal of Geophysical Research*, 99(C5), 10143–10162. | Background (ensemble methods) |
| R9 | Emerick, A.A. & Reynolds, A.C. (2013). Ensemble smoother with multiple data assimilation. *Computers & Geosciences*, 55, 3–15. | F26 |
| R23 | Beven, K. & Binley, A. (1992). The future of distributed models: model calibration and uncertainty prediction. *Hydrological Processes*, 6(3), 279–298. | F24 (GLUE weights) |

## Proxy and surrogate modelling, machine learning

| ID | Reference | Used for |
|---|---|---|
| R28 | Huang, H. et al. (2023). A deep-learning-based graph neural network–long-short-term memory model for reservoir simulation and optimization with varying well controls. SPE. *(Kick Off deck, slide 32)* | ML forecaster motivation |
| R29 | Zhang, Z. et al. (2023). Robust method for reservoir simulation history matching using Bayesian inversion and long-short-term memory network-based proxy. SPE. *(Kick Off deck, slide 32)* | ML forecaster motivation |
| R10 | Zubarev, D.I. (2009). Pros and cons of applying proxy-models as a substitute for full reservoir simulations. SPE-124815-MS. | Background |
| R11 | Mohaghegh, S.D. (2017). *Data-Driven Reservoir Modeling*. Society of Petroleum Engineers. | Background |
| R12 | Rasmussen, C.E. & Williams, C.K.I. (2006). *Gaussian Processes for Machine Learning*. MIT Press. | F30 |
| R14 | Raissi, M., Perdikaris, P. & Karniadakis, G.E. (2019). Physics-informed neural networks. *Journal of Computational Physics*, 378, 686–707. | Background |
| R24 | Kennedy, M.C. & O'Hagan, A. (2001). Bayesian calibration of computer models. *Journal of the Royal Statistical Society B*, 63(3), 425–464. | Proxy-based calibration |
| R25 | Higdon, D., Gattiker, J., Williams, B. & Rightley, M. (2008). Computer model calibration using high-dimensional output. *Journal of the American Statistical Association*, 103(482), 570–583. | PCA + GP proxy (F29) |

## Experimental design and sensitivity analysis

| ID | Reference | Used for |
|---|---|---|
| R5 | McKay, M.D., Beckman, R.J. & Conover, W.J. (1979). A comparison of three methods for selecting values of input variables in the analysis of output from a computer code. *Technometrics*, 21(2), 239–245. | Latin-hypercube sampling |
| R15 | Sobol, I.M. (2001). Global sensitivity indices for nonlinear mathematical models and their Monte Carlo estimates. *Mathematics and Computers in Simulation*, 55, 271–280. | F31, F32 |

## Reservoir engineering

| ID | Reference | Used for |
|---|---|---|
| R13 | Arps, J.J. (1945). Analysis of decline curves. *Transactions of the AIME*, 160, 228–247. | F16, F17 |
| R16 | Ahmed, T. (2019). *Reservoir Engineering Handbook* (5th ed.). Gulf Professional Publishing. | F3, F7, F11 |
| R17 | Dake, L.P. (1978). *Fundamentals of Reservoir Engineering*. Elsevier. | F3 |
| R18 | Aziz, K. & Settari, A. (1979). *Petroleum Reservoir Simulation*. Applied Science Publishers. | F8 |
| R19 | Fetkovich, M.J. (1971). A simplified approach to water influx calculations: finite aquifer systems. *Journal of Petroleum Technology*, 23(7), 814–828. | F12 |
| R20 | Havlena, D. & Odeh, A.S. (1963). The material balance as an equation of a straight line. *Journal of Petroleum Technology*, 15(8), 896–900. | F39 |
| R21 | Buckley, S.E. & Leverett, M.C. (1942). Mechanism of fluid displacement in sands. *Transactions of the AIME*, 146, 107–116. | F43 |
| R22 | Corey, A.T. (1954). The interrelation between gas and oil relative permeabilities. *Producers Monthly*, 19(1), 38–41. | F44 |
| R26 | Ershaghi, I. & Omorigie, O. (1978). A method for extrapolation of cut vs recovery curves. *Journal of Petroleum Technology*, 30(2), 203–204. | F18, F19 |
| R27 | Yousef, A.A., Gentil, P.H., Jensen, J.L. & Lake, L.W. (2006). A capacitance model to infer interwell connectivity from production and injection rate fluctuations. *SPE Reservoir Evaluation & Engineering*, 9(6), 630–646. | F27 |

## Software and standards

| ID | Reference | Used for |
|---|---|---|
| R3 | Schlumberger. *ECLIPSE Reference Manual / Technical Description* (keywords PORV, NTG, MULTFLT, MULTPV, TRANX, AQUNUM). | F1, F9; grid column meanings |
| R4 | OPM (Open Porous Media). *OPM Flow Reference Manual*. | F1 |
| R6 | Canadian Well Logging Society. *LAS Version 2.0 standard* (NULL value −999.25). | Null value in the grid files |

## Challenge material (primary data)

- ExxonMobil EMTech KL IT (2026). *DataWorks Challenge 2026 Kick-Off Ceremony* slides (6 Oct 2026).
- ExxonMobil EMTech KL IT (2026). *DataWorks Challenge 2026 Starter Pack* (`dwc26.zip`): README.md,
  01 Introduction.xlsx, 02 Field Production.xlsx, 03–08 case workbooks, 09 Template Deliverable.xlsx, Kick Off.pptx.
- ExxonMobil DWC26 portal: home, timeline, FAQ and dashboard pages (accessed 14 Oct 2026).
