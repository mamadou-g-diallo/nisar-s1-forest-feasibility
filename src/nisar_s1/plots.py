"""Figures for the site selection and the sensor comparison (matplotlib, no display needed)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .optical import Raster  # noqa: E402

CUT_COLOR, CTRL_COLOR = "#d62728", "#1f77b4"


def _extent(r: Raster):
    h, w = r.data.shape
    t = r.transform
    return (t.c, t.c + w * t.a, t.f + h * t.e, t.f)


def _outline(ax, gdf, color, label):
    for g in gdf.geometry:
        polys = getattr(g, "geoms", [g])
        for k, pg in enumerate(polys):
            x, y = pg.exterior.xy
            ax.plot(x, y, color=color, lw=1.5, label=label if k == 0 else None)


def site_maps(pre: Raster, post: Raster, cut, control, out: Path, title: str = "") -> None:
    """NDVI before / after and dNDVI with the clear-cut (red) and control forest (blue)."""
    fig, axs = plt.subplots(1, 3, figsize=(15, 5), constrained_layout=True)
    d = Raster(post.data - pre.data, pre.transform, pre.crs)
    for ax, r, ttl, cmap, lim in ((axs[0], pre, "NDVI before", "YlGn", (0, 1)),
                                  (axs[1], post, "NDVI after", "YlGn", (0, 1)),
                                  (axs[2], d, "dNDVI (after - before)", "RdBu", (-0.6, 0.6))):
        im = ax.imshow(r.data, extent=_extent(r), cmap=cmap, vmin=lim[0], vmax=lim[1])
        _outline(ax, cut, CUT_COLOR, "clear-cut")
        _outline(ax, control, CTRL_COLOR, "control forest")
        ax.set_title(ttl)
        ax.set_xlabel("UTM 32N x (m)")
        fig.colorbar(im, ax=ax, shrink=0.8)
    axs[0].set_ylabel("UTM 32N y (m)")
    axs[0].legend(loc="lower left", fontsize=8)
    if title:
        fig.suptitle(title)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def ndvi_series(ts: pd.DataFrame, out: Path, cut_window=None, title: str = "") -> None:
    """NDVI time series per polygon role (``role`` column: cut / control)."""
    fig, ax = plt.subplots(figsize=(9, 4), constrained_layout=True)
    for role, color in (("cut", CUT_COLOR), ("control", CTRL_COLOR)):
        s = ts[(ts.role == role)].dropna(subset=["ndvi"])
        ax.plot(pd.to_datetime(s.date), s.ndvi, "o-", color=color, ms=4, label=role)
    if cut_window:
        ax.axvspan(pd.Timestamp(cut_window[0]), pd.Timestamp(cut_window[1]), color="0.85", label="cut window")
    ax.set_ylabel("median NDVI (Sentinel-2)")
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.3)
    ax.legend()
    if title:
        ax.set_title(title)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def sensor_timeseries(df: pd.DataFrame, out: Path, cut_window=None, ylabel_map: dict | None = None) -> None:
    """One panel per variable: cut vs control mean (+/- std) over time.

    ``df`` columns: variable, date, mean_a (cut), std_a, mean_b (control), std_b.
    """
    vars_ = list(dict.fromkeys(df.variable))
    n = len(vars_)
    ncol = 2 if n > 1 else 1
    nrow = int(np.ceil(n / ncol))
    fig, axs = plt.subplots(nrow, ncol, figsize=(6.5 * ncol, 3.2 * nrow), squeeze=False,
                            constrained_layout=True)
    for ax, v in zip(axs.ravel(), vars_):
        s = df[df.variable == v].sort_values("date")
        x = pd.to_datetime(s.date)
        for col, std, color, lab in (("mean_a", "std_a", CUT_COLOR, "clear-cut"),
                                     ("mean_b", "std_b", CTRL_COLOR, "control forest")):
            ax.plot(x, s[col], "o-", color=color, ms=4, label=lab)
            ax.fill_between(x, s[col] - s[std], s[col] + s[std], color=color, alpha=0.15)
        if cut_window:
            ax.axvspan(pd.Timestamp(cut_window[0]), pd.Timestamp(cut_window[1]), color="0.85")
        ax.set_title(v)
        ax.set_ylabel((ylabel_map or {}).get(v, ""))
        ax.grid(alpha=0.3)
        ax.tick_params(axis="x", labelrotation=30)
    for ax in axs.ravel()[n:]:
        ax.axis("off")
    axs[0, 0].legend(fontsize=8)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def separability_bars(df: pd.DataFrame, out: Path, metric: str = "auc_sep", title: str = "") -> None:
    """Horizontal bars of a separability metric per (sensor, variable), sorted."""
    s = df.sort_values(metric)
    fig, ax = plt.subplots(figsize=(8, 0.35 * len(s) + 1.2), constrained_layout=True)
    colors = ["#2ca02c" if str(x).startswith("NISAR") else "#9467bd" for x in s.sensor]
    ax.barh(s.label, s[metric], color=colors)
    if "ci_lo" in s and metric == "auc_sep":
        ax.errorbar(s[metric], s.label, xerr=[s[metric] - s.ci_lo, s.ci_hi - s[metric]], fmt="none",
                    ecolor="k", capsize=2)
        ax.axvline(0.5, color="0.5", ls="--", lw=1)
        ax.set_xlim(0.4, 1.0)
    ax.set_xlabel(metric)
    if title:
        ax.set_title(title)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
