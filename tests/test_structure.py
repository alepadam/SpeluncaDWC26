"""Structural checks that run in CI before any pipeline code exists.

They guard the project set-up: config is valid and consistent with the known facts,
dependencies are pinned, and private / competition files are protected from git.
"""

from pathlib import Path

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def cfg() -> dict:
    with open(ROOT / "config.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def test_config_has_required_sections(cfg):
    required = {"project", "paths", "files", "sheets", "observed_columns", "grid", "parameters", "split",
                "history", "matching", "proxy", "optimization", "forecast", "best10", "sensitivity", "gas",
                "deliverable"}
    assert required <= set(cfg), f"missing sections: {required - set(cfg)}"


def test_split_covers_cases_1_to_100_exactly_once(cfg):
    seen = []
    for lo, hi in cfg["split"].values():
        assert lo <= hi
        seen += list(range(lo, hi + 1))
    assert sorted(seen) == list(range(1, 101))


def test_history_has_41_quarters(cfg):
    dates = pd.date_range(cfg["history"]["start"], cfg["history"]["end"], freq="QS-JAN")
    assert len(dates) == 41


def test_forecast_has_80_quarters(cfg):
    dates = pd.date_range(cfg["forecast"]["start"], cfg["forecast"]["end"], freq="QS-JAN")
    assert len(dates) == 80


def test_backtest_window_is_inside_history(cfg):
    h0, h1 = pd.Timestamp(cfg["history"]["start"]), pd.Timestamp(cfg["history"]["end"])
    fit0 = pd.Timestamp(cfg["forecast"]["backtest_fit_start"])
    cut = pd.Timestamp(cfg["forecast"]["backtest_cut"])
    assert h0 <= fit0 < cut < h1


def test_four_parameters_and_log_subset(cfg):
    names = cfg["parameters"]["names"]
    assert len(names) == 4
    assert set(cfg["parameters"]["log_transform"]) <= set(names)


def test_matching_settings_are_valid(cfg):
    m = cfg["matching"]
    assert 0 < m["sigma_rel"] < 1
    assert 0 < m["accept_top_fraction"] <= 1
    assert set(m["phase_weights"]) == {"oil", "gas", "water"}


def test_project_folders_exist(cfg):
    for rel in cfg["paths"].values():
        assert (ROOT / rel).is_dir(), f"missing folder: {rel}"


def test_requirements_are_pinned():
    for name in ("requirements.txt", "requirements-dev.txt"):
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-r"):
                continue
            assert "==" in line, f"{name}: unpinned dependency {line!r}"


def test_gitignore_protects_private_and_competition_files():
    rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for rule in (".env", "data/raw/*", "data/processed/*", "Dataset/", "*.xlsx", "*.pptx"):
        assert rule in rules, f".gitignore is missing {rule!r}"
    assert "!.env.example" in rules


def test_notebooks_have_no_saved_outputs():
    """Executed notebooks contain competition results; commit them cleared (Kernel > Restart & Clear Output)."""
    import json

    for nb_path in (ROOT / "notebooks").glob("*.ipynb"):
        nb = json.loads(nb_path.read_text(encoding="utf-8"))
        dirty = [i for i, c in enumerate(nb.get("cells", [])) if c.get("cell_type") == "code" and c.get("outputs")]
        assert not dirty, f"{nb_path.name}: clear outputs before committing (cells {dirty[:5]})"


def test_python_files_only_define_functions():
    """Team rule: work lives in notebooks; .py files only hold definitions (no top-level script logic)."""
    import ast

    allowed = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef, ast.Assign, ast.AnnAssign, ast.Expr)
    for py in (ROOT / "src").glob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        bad = [type(n).__name__ for n in tree.body if not isinstance(n, allowed)]
        assert not bad, f"{py.name}: top-level statements not allowed: {bad}"
