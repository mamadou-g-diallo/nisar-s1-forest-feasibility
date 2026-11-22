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


def contrast_persistence(ts: pd.DataFrame, out: Path, cut_window=None) -> None:
    """Per-date separation AUC (cut vs control) of the backscatter, one line per sensor/geometry/pol:
    shows whether the contrast created by the cut persists or fades with time."""
    fig, axs = plt.subplots(1, 2, figsize=(13, 4), sharey=True, constrained_layout=True)
    styles = {"HV": "-", "VH": "-", "HH": "--", "VV": "--"}
    for (sensor, geom, pol), s in ts.groupby(["sensor", "geom", "pol"]):
        s = s.sort_values("date")
        color = {"A144F26": "#2ca02c", "A72F26": "#17becf", "D138F64": "#8c564b"}.get(geom, "#9467bd")
        ax = axs[0] if pol in ("HV", "VH") else axs[1]
        ax.plot(pd.to_datetime(s.date), s.auc_sep, "o" + styles[pol], color=color, ms=4,
                label=f"{'NISAR L' if sensor.startswith('NISAR') else 'S1 C'} {geom} {pol}")
    for ax, ttl in zip(axs, ("cross-polarisation (HV / VH)", "co-polarisation (HH / VV)")):
        if cut_window:
            ax.axvspan(pd.Timestamp(cut_window[0]), pd.Timestamp(cut_window[1]), color="0.85")
        ax.axhline(0.5, color="0.5", lw=1, ls=":")
        ax.set_title(ttl)
        ax.set_ylim(0.45, 1.0)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8, loc="lower left")
        ax.tick_params(axis="x", labelrotation=30)
    axs[0].set_ylabel("separation AUC, cut vs control (per date)")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def change_maps(feats: dict, truth: Raster, cut, control, out: Path) -> None:
    """Maps of change variables (one panel each) next to the Sentinel-2 reference, with the cut
    (red) and control (blue) outlines."""
    n = len(feats) + 1
    fig, axs = plt.subplots(1, n, figsize=(4.2 * n, 4.4), constrained_layout=True)
    im = axs[0].imshow(truth.data, extent=_extent(truth), cmap="Greys", vmin=0, vmax=1, interpolation="nearest")
    axs[0].set_title("S2 reference (dNDVI <= -0.3)", fontsize=9)
    for ax, (name, r) in zip(axs[1:], feats.items()):
        v = r.data[np.isfinite(r.data)]
        lo, hi = np.percentile(v, [2, 98])
        if "coh" in name:
            lo, hi = 0, 1
        im = ax.imshow(r.data, extent=_extent(r), cmap="RdBu" if "gamma0" in name else "viridis",
                       vmin=-max(abs(lo), abs(hi)) if "d_gamma0" in name else lo,
                       vmax=max(abs(lo), abs(hi)) if "d_gamma0" in name else hi, interpolation="nearest")
        fig.colorbar(im, ax=ax, shrink=0.7)
        ax.set_title(name, fontsize=9)
    for ax in axs:
        _outline(ax, cut, CUT_COLOR, "clear-cut")
        _outline(ax, control, CTRL_COLOR, "control")
        b = control.total_bounds
        pad = 400
        ax.set_xlim(b[0] - pad, b[2] + pad)
        ax.set_ylim(b[1] - pad, b[3] + pad)
        ax.set_xticks([]); ax.set_yticks([])
    axs[0].legend(fontsize=7, loc="lower left")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)


# single-hue sequential ramp (light -> dark blue) for magnitude matrices
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def value_matrix(values: pd.DataFrame, out: Path, vmin: float = 0.5, vmax: float = 1.0,
                 groups: list[tuple[str, int]] | None = None, cbar_label: str = "",
                 fmt: str = "{:.2f}", decimal: str = ".", figsize: tuple[float, float] = (11, 6),
                 fontsize: float = 11) -> None:
    """Annotated matrix of one metric (rows: variables, columns: sensors / geometries).

    ``values`` holds the numbers (NaN = not applicable, drawn as a light grey cell with a dash).
    ``decimal`` sets the decimal separator of the cell labels (',' for French figures).
    ``groups`` = [(title, n_rows), ...] draws a separator and a group title every ``n_rows`` rows.
    Colours follow a single-hue sequential ramp; values are always written in the cell, so the
    figure does not rely on colour alone.
    """
    from matplotlib.colors import LinearSegmentedColormap

    cmap = LinearSegmentedColormap.from_list("seq_blue", SEQ_BLUE)
    cmap.set_bad("#f2f2f2")
    v = values.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=figsize, constrained_layout=True)
    im = ax.imshow(np.ma.masked_invalid(v), cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")
    for i in range(v.shape[0]):
        for j in range(v.shape[1]):
            x = v[i, j]
            if np.isnan(x):
                ax.text(j, i, "–", ha="center", va="center", color="#9a9a9a", fontsize=fontsize)
            else:
                dark = (x - vmin) / (vmax - vmin) > 0.55
                ax.text(j, i, fmt.format(x).replace(".", decimal), ha="center", va="center", fontsize=fontsize,
                        color="white" if dark else "#1a1a1a", fontweight="bold" if x >= 0.9 else None)
    ax.set_xticks(range(v.shape[1]), values.columns, fontsize=fontsize)
    ax.xaxis.tick_top()
    ax.set_yticks(range(v.shape[0]), values.index, fontsize=fontsize * 0.95)
    ax.tick_params(which="both", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(-0.5, v.shape[1]), minor=True)
    ax.set_yticks(np.arange(-0.5, v.shape[0]), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    if groups:
        start = 0
        for title, n in groups:
            if start:
                ax.axhline(start - 0.5, color="#333333", linewidth=1.2)
            ax.text(-0.42, (start + start + n - 1) / 2, title, transform=ax.get_yaxis_transform(),
                    ha="center", va="center", rotation=90, fontsize=fontsize * 0.95, fontweight="bold",
                    color="#333333")
            start += n
    cb = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.01)
    cb.set_label(cbar_label, fontsize=fontsize * 0.95)
    cb.ax.tick_params(labelsize=fontsize * 0.9)
    cb.ax.yaxis.set_major_formatter(lambda t, _: f"{t:.1f}".replace(".", decimal))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=200)
    plt.close(fig)
