"""Shared helpers: logging, case ids, quarter dates, splits, scaling, weighted quantiles."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import numpy as np
import pandas as pd

PHASES = ("oil", "gas", "water")
UNITS = {"oil": "STB", "gas": "MSCF", "water": "STB"}


def get_logger(name: str, log_dir: Path | None = None) -> logging.Logger:
    logger = logging.getLogger(f"spelunca.{name}")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.propagate = False
    fmt = logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    if log_dir is not None:
        fh = logging.FileHandler(Path(log_dir) / "pipeline.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


def norm_case(label: object) -> str:
    """'Case_7', 'case 7', ' Case 7 ' -> 'CASE 7'. Labels without a case number are upper-cased."""
    s = str(label).strip().replace("_", " ").upper()
    m = re.fullmatch(r"CASE\s*(\d+)", s)
    return f"CASE {int(m.group(1))}" if m else s


def case_number(case_id: str) -> int:
    m = re.search(r"(\d+)", str(case_id))
    if not m:
        raise ValueError(f"No case number in {case_id!r}")
    return int(m.group(1))


def quarter_dates(start: str, end: str) -> pd.DatetimeIndex:
    """Quarter-start dates, inclusive: 1998-01-01, 1998-04-01, ..."""
    return pd.date_range(start=start, end=end, freq="QS-JAN")


def split_of(case_id: str, split_cfg: dict) -> str:
    n = case_number(case_id)
    for name, (lo, hi) in split_cfg.items():
        if lo <= n <= hi:
            return name
    return "unknown"


class ParamScaler:
    """Raw parameters <-> model inputs in [0, 1]: optional log transform, then min-max by the 100-case design.

    The bounds come from the design table (inputs only, no targets), so using all 100 cases is not leakage.
    """

    def __init__(self, names: list[str], log_names: list[str]):
        self.names = list(names)
        self.log = [n in log_names for n in self.names]

    def _t(self, raw: np.ndarray) -> np.ndarray:
        z = np.array(raw, dtype=float, copy=True)
        for j, is_log in enumerate(self.log):
            if is_log:
                z[:, j] = np.log(z[:, j])
        return z

    def fit(self, raw: pd.DataFrame) -> ParamScaler:
        z = self._t(raw[self.names].to_numpy())
        self.lo_, self.hi_ = z.min(axis=0), z.max(axis=0)
        if np.any(self.hi_ <= self.lo_):
            raise ValueError("A parameter has no spread; cannot scale")
        return self

    def transform(self, raw: pd.DataFrame | np.ndarray) -> np.ndarray:
        arr = raw[self.names].to_numpy() if isinstance(raw, pd.DataFrame) else np.atleast_2d(raw)
        return (self._t(arr) - self.lo_) / (self.hi_ - self.lo_)

    def inverse(self, x: np.ndarray) -> np.ndarray:
        z = np.atleast_2d(x) * (self.hi_ - self.lo_) + self.lo_
        for j, is_log in enumerate(self.log):
            if is_log:
                z[:, j] = np.exp(z[:, j])
        return z


def weighted_quantile(values: np.ndarray, quantiles, weights: np.ndarray | None = None) -> np.ndarray:
    """Weighted quantiles along axis 0 (values: n_members x ...), interpolating the weighted CDF."""
    values = np.asarray(values, dtype=float)
    q = np.atleast_1d(np.asarray(quantiles, dtype=float))
    w = np.ones(values.shape[0]) if weights is None else np.asarray(weights, dtype=float)
    if w.shape[0] != values.shape[0] or w.sum() <= 0 or np.any(w < 0):
        raise ValueError("weights must be non-negative, one per member, with a positive sum")
    flat = values.reshape(values.shape[0], -1)
    out = np.empty((q.size, flat.shape[1]))
    pos = w > 0                                  # zero-weight members must not shape the CDF
    for j in range(flat.shape[1]):
        order = np.argsort(flat[pos, j])
        v, ww = flat[pos, j][order], w[pos][order]
        cdf = (np.cumsum(ww) - 0.5 * ww) / ww.sum()
        out[:, j] = np.interp(q, cdf, v)
    return out.reshape((q.size,) + values.shape[1:])
