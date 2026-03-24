import base64
from io import BytesIO

import matplotlib.pyplot as plt

_LAST_AX = None
_PLOT_STYLE = "fivethirtyeight"
_DISPLAY_DPI = 150
_DISPLAY_HEIGHT_PX = 280
_DEFAULT_FIGSIZE = (28, 4)


class PlotResult:
    def __init__(self, figure):
        self.figure = figure

    def _responsive_png_html(self):
        png_buffer = BytesIO()
        self.figure.savefig(
            png_buffer,
            format="png",
            dpi=_DISPLAY_DPI,
            bbox_inches="tight",
        )
        encoded = base64.b64encode(png_buffer.getvalue()).decode("ascii")
        return (
            '<img alt="plot" '
            f'style="width:100%;max-width:100%;height:{_DISPLAY_HEIGHT_PX}px;object-fit:contain;display:block;" '
            f'src="data:image/png;base64,{encoded}" />'
        )

    def show(self):
        # Notebook-safe responsive display.
        try:
            from IPython.display import HTML, display

            display(HTML(self._responsive_png_html()))
        except Exception:
            plt.show()
        finally:
            # Prevent duplicate notebook inline rendering of the same figure.
            plt.close(self.figure)
        return None

    def __getattr__(self, name):
        return getattr(self.figure, name)


def _get_axis(new_figure, title=None, figsize=None):
    global _LAST_AX
    if new_figure or _LAST_AX is None:
        _, ax = plt.subplots(figsize=figsize or _DEFAULT_FIGSIZE, layout="constrained")
        _LAST_AX = ax
    ax = _LAST_AX
    if title is not None:
        ax.set_title(title)
    return ax


def fast_bar(data, figsize=None, title="", alpha=1, label="", new_figure=True):
    with plt.style.context(_PLOT_STYLE):
        ax = _get_axis(new_figure=new_figure, title=title or None, figsize=figsize)
        ax.bar(data.index, data.values, alpha=alpha, label=label or "value")
    return PlotResult(ax.figure)


def fast_hist(data, n=30, ax=None, figsize=None, title="", alpha=1, label="", new_figure=True):
    with plt.style.context(_PLOT_STYLE):
        if ax is None:
            ax = _get_axis(new_figure=new_figure, title=title or None, figsize=figsize)
        elif title:
            ax.set_title(title)
        ax.hist(data, bins=n, alpha=alpha, label=label or "value")
    return PlotResult(ax.figure)


def fast_plot(data, rolling=1, alpha=0.5, figsize=None, new_figure=True, title=None, label=None):
    smoothed = data.rolling(rolling).mean()
    with plt.style.context(_PLOT_STYLE):
        ax = _get_axis(new_figure=new_figure, title=title, figsize=figsize)
        ax.plot(
            smoothed.index,
            smoothed.values,
            marker="o",
            linewidth=2,
            alpha=alpha,
            label=label or (data.name if getattr(data, "name", None) else "series"),
        )
    return PlotResult(ax.figure)


def fast_scatter(x, y, rolling=1, alpha=0.5, figsize=None, new_figure=True, title=None, label=None):
    x_smoothed = x.rolling(rolling).mean()
    y_smoothed = y.rolling(rolling).mean()
    with plt.style.context(_PLOT_STYLE):
        ax = _get_axis(new_figure=new_figure, title=title, figsize=figsize)
        ax.scatter(x_smoothed, y_smoothed, alpha=alpha, label=label or "scatter")
    return PlotResult(ax.figure)


def fast_legend(ncol=3, pos=(0.5, -0.15), fontsize=16):
    with plt.style.context(_PLOT_STYLE):
        ax = _get_axis(new_figure=False, title=None, figsize=None)
        ax.legend(
            loc="upper center",
            bbox_to_anchor=pos,
            ncol=ncol,
            fontsize=fontsize,
        )
    return PlotResult(ax.figure)
