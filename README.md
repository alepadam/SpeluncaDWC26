# SpeluncaDWC26

**ExxonMobil DataWorks Challenge 2026 (DWC26)**

**Topic:** Machine Learning-Assisted History Matching and the Challenge of Production Forecasting

## Team SPELUNCA

| Member |
|---|
| Muhammad Aliff Adam bin Sultan |
| Qistina Aqilah binti Abdul Razak Tuah |
| Muhammad Adam Harith bin Ahmad Zaki |

## What we are researching

An oil field has been producing since 1998. We have its observed production up to 2008, plus 100 reservoir
simulations. Each simulation uses different values for four uncertain parameters: fault transmissibility, porosity
multiplier, permeability multiplier and aquifer pore volume. Our job is to find the parameter values that reproduce
the field's history, then use them to forecast oil, gas and water production for the next 20 years (2008 → 2028).

> **Main research question**
>
> **Can a machine-learning proxy, trained on the 100 simulated cases, identify the parameter values that match the
> observed 1998–2008 production, and use them to forecast cumulative oil, gas and water production to 2028 with an
> honest uncertainty range?**

| Sub-question | About | Detail |
|---|---|---|
| SRQ1 | Time alignment | How should simulated and observed production be lined up in time? |
| SRQ2 | History matching | Which parameter values best match the observed history, and is the answer unique? |
| SRQ3 | Parameter influence | Which of the four parameters control production? |
| SRQ4 | Proxy accuracy | How accurately can an ML proxy reproduce the simulator for unseen cases? |
| SRQ5 | Extrapolation | Can we forecast reliably 20 years beyond the data, and which method does it best? |
| SRQ6 | Best 10 forecasts and uncertainty | What are the 10 best forecasts to 2028, and how uncertain are they? |

The full questions and hypotheses are in [`research/01_research_questions.md`](research/01_research_questions.md).

## Methodology

1. **Prepare the data:** line up the simulated and observed production on the same 41 quarterly dates and check the
   data quality.
2. **Train an ML proxy:** learn how the 4 parameters shape the production curves (principal component analysis +
   Gaussian process). This lets us test new parameter values almost instantly instead of running the simulator.
   It is trained on cases 1–70, tuned on 71–85 and tested once on 86–100.
3. **History matching:** search the parameter space for the values whose predicted production best matches the
   observed field (weighted least-squares loss, differential evolution), and keep every set that fits well.
4. **Forecast to 2028:** forecast production after 2008 with two methods (decline curves and an ML time-series
   model). We use whichever has the lower error when tested on 2004 → 2008.
5. **Best 10 forecasts:** pick the 10 best-matching parameter sets that are clearly different from each other,
   forecast each one to 2028, report P90 / P50 / P10 and fill in the competition template.
6. **Explain:** measure how much each parameter drives the results (Sobol sensitivity analysis).

More detail:

| Document | What it covers |
|---|---|
| [`research/03_methodology.md`](research/03_methodology.md) | Full method |
| [`research/04_formulas.md`](research/04_formulas.md) | Formulas |
| [`research/05_references.md`](research/05_references.md) | References |

## Running the project

Installation, notebooks, tests and CI/CD are covered in [SETUP.md](SETUP.md).

## Licence

All rights reserved. See [LICENSE](LICENSE). The DWC26 competition data is not part of this repository and must
not be published.
