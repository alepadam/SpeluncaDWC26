"""Runs the steps in the deck's suggested order (slide 30):
data preparation -> ML proxy training -> ML prediction + optimization (history matching)
-> forecast production -> best 10 forecasts -> deliverable; parameter influence last.
"""

from __future__ import annotations

import time

from . import deliverable, s1_prepare, s2_proxy, s3_history_match, s4_forecast, s5_best10, s6_sensitivity
from .utils import get_logger

STEPS = [
    ("prepare", s1_prepare.run),           # SRQ1
    ("proxy", s2_proxy.run),               # SRQ4
    ("history_match", s3_history_match.run),  # SRQ2
    ("forecast", s4_forecast.run),         # SRQ5
    ("best10", s5_best10.run),             # SRQ6
    ("deliverable", deliverable.run),      # template
    ("sensitivity", s6_sensitivity.run),   # SRQ3
]
STEP_NAMES = [name for name, _ in STEPS]


def run_pipeline(cfg: dict, until: str | None = None) -> dict:
    if until is not None and until not in STEP_NAMES:
        raise ValueError(f"Unknown step {until!r}; choose from {STEP_NAMES}")
    log = get_logger("pipeline", cfg["paths"]["logs"])
    state: dict = {}
    for name, func in STEPS:
        t0 = time.perf_counter()
        log.info("=== step: %s", name)
        out = func(cfg) if name == "prepare" else func(cfg, state)
        state.update(out)
        log.info("=== step %s done in %.1f s", name, time.perf_counter() - t0)
        if name == until:
            break
    return state
