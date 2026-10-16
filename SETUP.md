# Setup and running

For the team, research topic and a short summary of the method, see [README.md](README.md).
The full method is in [`research/03_methodology.md`](research/03_methodology.md).

## Install

You need **Python 3.12 or newer**.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                   # Windows: copy .env.example .env
```

## Run

All the work happens in the notebooks. The files in `src/*.py` only hold the functions the notebooks call.

| Notebook | What it does |
|---|---|
| `notebooks/01_eda.ipynb` | Checks every input file against the known facts (sheets, dates, RAMP_History, gas–oil ratio, drivers). Section 9 checks the grid files (if any of 03–08 is present) and recomputes HCPV |
| `notebooks/02_pipeline.ipynb` | Runs the full method step by step and shows every result table and figure |
| `notebooks/03_results_figures.ipynb` | Builds slide-ready figures from the saved tables (nothing is recomputed) |

Open them in VS Code or Jupyter with the `.venv` kernel, from the `notebooks/` folder.

> [!IMPORTANT]
> **Clear all outputs before committing.** The outputs contain competition results, and a test checks for this.

```bash
pytest                                 # unit tests + end-to-end test on synthetic data
ruff check .                           # lint
```

Every setting (file and sheet names, split, dates, error model, optimiser and forecast options) lives in
`config.yaml`. The log is written to `outputs/logs/pipeline.log`.

## Pipeline

| Step | Module | Research question | Main outputs (`outputs/`) |
|---|---|---|---|
| 1. Data preparation | `src/s1_prepare.py` | SRQ1 time alignment | `tables/srq1_convention_test.csv`, `qc_report.csv` |
| 2. ML proxy | `src/s2_proxy.py` | SRQ4 proxy accuracy | `tables/srq4_proxy_scores.csv`, `srq4_proxy_uncertainty.csv` |
| 3. Optimization (history matching) | `src/s3_history_match.py` | SRQ2 | `tables/srq2_optimum.csv`, `figures/srq2_history_match.png` |
| 4. Forecast | `src/s4_forecast.py` | SRQ5 extrapolation | `tables/srq5_backtest_summary.csv`, `figures/srq5_backtest.png` |
| 5. Best 10 | `src/s5_best10.py` | SRQ6 uncertainty | `tables/srq6_best10.csv`, `srq6_pipeline_backtest.csv`, `figures/srq6_forecast_fan.png` |
| Deliverable | `src/deliverable.py` | Not a research question (submission file) | `deliverable/SPELUNCA_Template_Deliverable.xlsx` (Power BI source) |
| 6. Parameter influence | `src/s6_sensitivity.py` | SRQ3 | `tables/srq3_sobol.csv`, `srq3_spearman.csv` |

## Folder structure

```
speluncaDWC26/
├── README.md  SETUP.md  LICENSE
├── config.yaml  requirements.txt  requirements-dev.txt  pyproject.toml
├── .env (private, ignored)  .env.example  .gitignore  .gitattributes
├── .github/workflows/ci.yml      CI/CD
├── research/                     written research: questions, data facts, methodology, formulas, references, findings
├── src/                          pipeline modules (table above) + config, io_load, grid, metrics, utils, plotting, report, pipeline
├── tests/                        test_units.py, test_pipeline.py (synthetic data), test_structure.py, synthetic.py
├── notebooks/                    01_eda.ipynb, 02_pipeline.ipynb, 03_results_figures.ipynb
├── data/{raw,processed}/         contents ignored by git
└── outputs/{figures,tables,deliverable,logs}/  contents ignored by git
```

## How private files are protected

- `.env` and everything inside `data/` and `outputs/` are ignored by git. Only the `.gitkeep` placeholders are tracked.
- **Keep the GitHub repository private.** The result tables and figures come from competition data.
- Tests and CI run on a **synthetic** dataset with the same file structure (`tests/synthetic.py`), so the real data
  never leaves your machine.
- The CI **guard** job fails if a `.env` or any data file is ever committed by mistake.

## CI/CD (`.github/workflows/ci.yml`)

| Job | When | What it does |
|---|---|---|
| guard | every push to `main`, every PR | Fails if `.env` or competition data is tracked, or if a file is over 50 MB |
| lint | same | `ruff check .` |
| test | same | `pytest` on Python 3.12 and 3.13 (unit + synthetic end-to-end) |
| package (CD) | tag `v*` or manual run | Builds `SPELUNCA.zip` from tracked files, checks it is ≤ 100 MB with no secrets or data, then uploads it |

```bash
git tag v1.0 && git push origin v1.0      # or GitHub → Actions → CI/CD → Run workflow
```
