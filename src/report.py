"""Helpers for the written findings in the notebooks: number formatting, tables and display.

Findings are generated from the results at run time, so the text always matches the numbers, and it is removed
together with the other outputs when notebook outputs are cleared before a commit (no competition numbers in git).

Tables are rendered by `show_table` as self-contained HTML (inline styles only, no extra dependency such as jinja2),
so they look the same in VS Code and Jupyter, in light and dark themes, and still print as plain text elsewhere.
"""

from __future__ import annotations

import datetime as dt
import html
import logging
from collections.abc import Callable, Iterable

import numpy as np
import pandas as pd

from .utils import get_logger


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


# ------------------------------------------------------------------ tables
# Colours match src/plotting.py (INK, INK_2, GRID) so tables and figures read as one system.
_INK, _INK_2, _GRID = "#0b0b0b", "#52514e", "#e4e3df"
_HEAD_BG, _ZEBRA, _HIGHLIGHT, _GROUP_RULE = "#f4f3ef", "#fafaf8", "#eaf2fc", "#b9b8b3"
_FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
_WRAP_AT = 60   # text cells longer than this wrap; shorter ones stay on one line

Format = str | Callable[[object], str]


def _is_missing(v) -> bool:
    try:
        return bool(pd.isna(v))
    except (TypeError, ValueError):   # lists, tuples, arrays: not a missing scalar
        return False


def _is_number(v) -> bool:
    return isinstance(v, (int, float, np.integer, np.floating)) and not isinstance(v, (bool, np.bool_))


def fmt_value(v, spec: Format | None = None) -> str:
    """One cell as text. `spec` is a format string ('{:.1%}') or a function; otherwise a readable default:
    missing -> 'n/a', bool -> Yes/No, dates -> YYYY-MM-DD, integers with thousands separators, floats by size,
    tuples (a, b) -> 'a–b'."""
    if _is_missing(v):
        return "n/a"
    if spec is not None:
        return str(spec(v)) if callable(spec) else spec.format(v)
    if isinstance(v, (bool, np.bool_)):
        return "Yes" if v else "No"
    if isinstance(v, (pd.Timestamp, dt.datetime)):
        return v.strftime("%Y-%m-%d") if (v.hour, v.minute, v.second) == (0, 0, 0) else v.strftime("%Y-%m-%d %H:%M")
    if isinstance(v, dt.date):
        return v.strftime("%Y-%m-%d")
    if isinstance(v, (int, np.integer)):
        return f"{int(v):,}"
    if isinstance(v, (float, np.floating)):
        a = abs(float(v))
        if a == 0:
            return "0"
        if float(v).is_integer() and a < 1e15:
            return f"{float(v):,.0f}"
        if a >= 1e4:
            return f"{float(v):,.0f}"
        if a >= 100:
            return f"{float(v):,.1f}"
        if a >= 1:
            return f"{float(v):.3f}"
        if a >= 0.01:
            return f"{float(v):.4f}"
        return f"{float(v):.2e}"
    if isinstance(v, tuple) and len(v) == 2:
        return f"{fmt_value(v[0])}–{fmt_value(v[1])}"
    return str(v)


def sci(digits: int = 1) -> Callable[[object], str]:
    """Format for very small numbers: 2.5e-08; an exact zero is shown as 0 rather than 0.0e+00."""
    return lambda v: "0" if float(v) == 0 else f"{float(v):.{digits}e}"


def _label(c) -> str:
    """Column label; MultiIndex columns are joined with ' · '."""
    return " · ".join(str(x) for x in c) if isinstance(c, tuple) else str(c)


def _cell_style(*, right: bool, head: bool = False, bold: bool = False, bg: str | None = None,
                top: str | None = None, last: bool = False, wrap: bool = False) -> str:
    s = [f"padding:{'7px' if head else '6px'} 12px", f"text-align:{'right' if right else 'left'}",
         "vertical-align:top", f"color:{_INK}"]
    if head:
        s += [f"background:{_HEAD_BG}", "font-weight:600", f"border-bottom:1px solid {_INK}", "white-space:nowrap"]
    else:
        s += [f"background:{bg or '#ffffff'}", f"border-bottom:{'none' if last else f'1px solid {_GRID}'}"]
        if bold:
            s.append("font-weight:600")
        if top:
            s.append(f"border-top:1px solid {top}")
    if right:
        s.append("font-variant-numeric:tabular-nums")
    if not head:
        s.append("white-space:normal;min-width:180px;max-width:520px" if wrap else "white-space:nowrap")
    return ";".join(s)


class Table:
    """A rendered table: HTML for notebooks, plain text for anything else (logs, text-only viewers)."""

    def __init__(self, html_text: str, plain_text: str):
        self.html, self.text = html_text, plain_text

    def _repr_html_(self) -> str:
        return self.html

    def __repr__(self) -> str:
        return self.text


def table(df: pd.DataFrame | pd.Series, title: str | None = None, note: str | None = None,
          formats: Format | dict[object, Format] | None = None, index: bool | None = None,
          highlight: Iterable | None = None, align: dict[object, str] | None = None) -> Table:
    """Build a clean, professional table from a DataFrame.

    - `formats`: one format for every column, or {column: format}; a format is '{:.3f}'-style or a function.
    - `index`: show the index as the first column(s); default = show it unless it is a plain 0, 1, 2 ... index.
      A MultiIndex is shown as grouped columns: repeated labels are left blank and each group starts with a rule.
    - `highlight`: index labels to emphasise, or a boolean list/array/Series with one value per row.
    - `align`: {column: 'left' | 'right'} to override the automatic alignment (numbers right, text left).
    """
    if isinstance(df, pd.Series):
        df = df.to_frame()
    if index is None:
        index = not isinstance(df.index, pd.RangeIndex)
    cols = list(df.columns)
    if isinstance(formats, dict):
        fmt = {c: formats.get(c) for c in cols}
    else:
        fmt = {c: formats for c in cols}
    align = align or {}
    right = {c: align[c] == "right" if c in align else
             all(_is_number(v) or _is_missing(v) for v in df[c].tolist()) and df[c].notna().any() for c in cols}

    n = len(df)
    if highlight is None:
        hl = np.zeros(n, bool)
    else:
        h = list(highlight)
        if len(h) == n and all(isinstance(x, (bool, np.bool_)) for x in h):
            hl = np.array(h, bool)
        else:
            keys = set(h)
            hl = np.array([lab in keys for lab in df.index], bool)

    idx_names = [str(x) if x is not None else "" for x in df.index.names] if index else []
    idx_rows = [lab if isinstance(lab, tuple) else (lab,) for lab in df.index] if index else [()] * n
    depth = len(idx_names)

    # header
    head = [f'<th style="{_cell_style(right=False, head=True)}">{html.escape(nm)}</th>' for nm in idx_names]
    head += [f'<th style="{_cell_style(right=right[c], head=True)}">{html.escape(_label(c))}</th>' for c in cols]

    # body
    body, text_rows, prev = [], [], None
    values = df.to_numpy(dtype=object)
    for r in range(n):
        lab = idx_rows[r]
        group_start = depth > 1 and prev is not None and lab[0] != prev[0]
        bg = _HIGHLIGHT if hl[r] else (_ZEBRA if r % 2 else "#ffffff")
        last = r == n - 1
        top = _GROUP_RULE if group_start else None
        tds, trow = [], []
        for j in range(depth):
            show = prev is None or any(lab[i] != prev[i] for i in range(j + 1))
            txt = fmt_value(lab[j]) if show else ""
            tds.append(f'<td style="{_cell_style(right=False, bold=True, bg=bg, top=top, last=last)}">'
                       f"{html.escape(txt)}</td>")
            trow.append(txt)
        for j, c in enumerate(cols):
            txt = fmt_value(values[r, j], fmt[c])
            style = _cell_style(right=right[c], bold=bool(hl[r]), bg=bg, top=top, last=last,
                                wrap=not right[c] and len(txt) > _WRAP_AT)
            tds.append(f'<td style="{style}">{html.escape(txt)}</td>')
            trow.append(txt)
        body.append("<tr>" + "".join(tds) + "</tr>")
        text_rows.append(trow)
        prev = lab

    parts = [f'<div style="display:inline-block;max-width:100%;overflow-x:auto;box-sizing:border-box;'
             f'margin:6px 0 12px 0;padding:12px 14px;background:#ffffff;border:1px solid {_GRID};border-radius:6px;'
             f'font-family:{_FONT};">']
    if title:
        parts.append(f'<div style="font-size:14px;font-weight:600;color:{_INK};margin:0 0 8px 0;">'
                     f"{html.escape(title)}</div>")
    parts.append(f'<table style="border-collapse:collapse;font-size:13px;line-height:1.35;color:{_INK};'
                 f'background:#ffffff;border-top:1.5px solid {_INK};border-bottom:1.5px solid {_INK};margin:0;">'
                 f"<thead><tr>{''.join(head)}</tr></thead><tbody>{''.join(body)}</tbody></table>")
    if note:
        parts.append(f'<div style="font-size:12px;color:{_INK_2};margin:8px 0 0 0;max-width:900px;">'
                     f"{html.escape(note)}</div>")
    parts.append("</div>")

    header_text = idx_names + [_label(c) for c in cols]
    plain = pd.DataFrame(text_rows, columns=header_text).to_string(index=False) if n else "(empty table)"
    plain = "\n".join(x for x in (title, plain, note) if x)
    return Table("".join(parts), plain)


def show_table(df: pd.DataFrame | pd.Series, title: str | None = None, note: str | None = None,
               formats: Format | dict[object, Format] | None = None, index: bool | None = None,
               highlight: Iterable | None = None, align: dict[object, str] | None = None) -> None:
    """Display `table(...)` in a notebook output cell (same arguments)."""
    from IPython.display import display

    display(table(df, title, note, formats, index, highlight, align))


# ------------------------------------------------------------------ console logging in notebooks
PIPELINE_LOGGERS = ("s1_prepare", "s2_proxy", "s3_history_match", "s4_forecast", "s5_best10",
                    "s6_sensitivity", "deliverable", "pipeline")


def log_to_file_only(cfg: dict, level: int = logging.WARNING) -> None:
    """Keep step-by-step INFO logs in outputs/logs/pipeline.log but out of the notebook, which shows the same
    results as formatted tables. Warnings and errors still appear in the notebook."""
    for name in PIPELINE_LOGGERS:
        for h in get_logger(name, cfg["paths"]["logs"]).handlers:
            if type(h) is logging.StreamHandler:          # the console handler (FileHandler is a subclass: kept)
                h.setLevel(level)
