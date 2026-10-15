"""Single place that selects the non-interactive matplotlib backend (works headless in CI) and holds the slide style.

In notebooks, show a figure with ``display(Image(data=png_bytes(fig)))`` - ``plt.show()`` and ``display(fig)`` draw
nothing under the Agg backend.
"""

import io

import matplotlib

matplotlib.use("Agg")

from matplotlib import pyplot as plt  # noqa: E402

# Phase colours = slots 1-3 of the validated reference categorical palette (light surface #ffffff).
# All three pairs pass the colour-blind check; water (#1baf7a) is below 3:1 contrast, so every chart that uses
# these colours also labels its values directly.
PHASE_COLORS = {"oil": "#2a78d6", "gas": "#eb6834", "water": "#1baf7a"}
INK = "#0b0b0b"          # titles and values
INK_2 = "#52514e"        # axis labels, tick labels, notes
GRID = "#e4e3df"         # recessive grid / axis lines

SLIDE_RC = {
    "figure.facecolor": "white", "axes.facecolor": "white", "savefig.facecolor": "white",
    "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "axes.titlecolor": INK, "axes.titlesize": 12,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": INK_2, "ytick.color": INK_2, "xtick.labelsize": 9, "ytick.labelsize": 10,
    "font.size": 10, "legend.frameon": False, "legend.fontsize": 9,
}


def clean_axes(ax, grid_axis: str = "x") -> None:
    """Recessive axes: light grid behind the data on one axis only, no tick marks on the category axis."""
    ax.set_axisbelow(True)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.tick_params(axis="y" if grid_axis == "x" else "x", length=0)
    ax.tick_params(axis=grid_axis, length=3, color=GRID)


def png_bytes(fig, dpi: int = 110) -> bytes:
    """Render a figure to PNG bytes (for IPython ``Image(data=...)``); works with the Agg backend."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    return buf.getvalue()


__all__ = ["plt", "PHASE_COLORS", "INK", "INK_2", "GRID", "SLIDE_RC", "clean_axes", "png_bytes"]
