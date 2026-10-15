"""Helpers for the written findings in the notebooks: number formatting, Markdown tables and display.

Findings are generated from the results at run time, so the text always matches the numbers, and it is removed
together with the other outputs when notebook outputs are cleared before a commit (no competition numbers in git).
"""

from __future__ import annotations

import pandas as pd


def pct(x: float, digits: int = 1) -> str:
    """0.0523 -> '5.2%'."""
    return f"{100.0 * float(x):.{digits}f}%"


def millions(x: float, digits: int = 1) -> str:
    """58_907_930 -> '58.9 M'."""
    return f"{float(x) / 1e6:,.{digits}f} M"


def verdict(ok: bool, partly: bool = False) -> str:
    """Bold verdict for a hypothesis check."""
    if partly:
        return "**Partly supported**"
    return "**Supported**" if ok else "**Not supported**"


def md_table(df: pd.DataFrame, index: bool = False) -> str:
    """DataFrame -> GitHub Markdown table (no extra dependency). Cells are converted with str()."""
    d = df.reset_index() if index else df
    head = "| " + " | ".join(str(c) for c in d.columns) + " |"
    sep = "|" + "|".join("---" for _ in d.columns) + "|"
    rows = ["| " + " | ".join(str(v).replace("|", "/") for v in r) + " |" for r in d.itertuples(index=False)]
    return "\n".join([head, sep, *rows])


def show_md(text: str) -> None:
    """Render Markdown in a notebook output cell."""
    from IPython.display import Markdown, display

    display(Markdown(text))
