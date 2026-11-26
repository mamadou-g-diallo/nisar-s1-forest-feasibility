"""Step 7 — Summary figure for the presentation: L band (each NISAR geometry) vs C band (Sentinel-1) on
the three key indicators, read from the result tables (no number typed by hand).

Indicators (20 m grid):
  1. coherence of the pair spanning the cut (separation AUC);
  2. cross-pol backscatter change after - before (HV / VH, separation AUC);
  3. persistence: mean per-date cross-pol AUC in October-November.

The descending NISAR geometry (D138) is highlighted because it is the like-for-like comparison with the
descending Sentinel-1 orbit 139.

Output: ``vosges/results/figures/summary_L_vs_C.png``.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from nisar_s1.config import PROJECT_ROOT  # noqa: E402

TAB = PROJECT_ROOT / "vosges" / "results" / "tables"
FIG = PROJECT_ROOT / "vosges" / "results" / "figures"

SERIES = [("NISAR-L", "A144F26", "L  A144 (asc.)", "#2ca02c"),
          ("NISAR-L", "A72F26", "L  A72 (asc.)", "#98df8a"),
          ("NISAR-L", "D138F64", "L  D138 (desc.)", "#1b7a1b"),
          ("S1-C", "T139", "C  D139 (desc.)", "#9467bd")]


def main() -> None:
    ch = pd.read_csv(TAB / "comparison_change.csv")
    ts = pd.read_csv(TAB / "comparison_timeseries.csv")
    post = ts[(ts.kind == "g0") & (ts.phase == "post") & ts.pol.isin(["HV", "VH"])].copy()
    post["date"] = pd.to_datetime(post.date)
    late = post[post.date >= "2026-10-01"].groupby(["sensor", "geom"]).auc_sep.mean()

    def val(sensor, geom, variables):
        x = ch[(ch.sensor == sensor) & (ch.geom == geom) & ch.variable.isin(variables)]
        return x.auc_sep.max() if len(x) else np.nan

    ind = ["Coherence of the pair\nspanning the cut", "Cross-pol backscatter\nchange (HV / VH)",
           "Persistence:\ncross-pol AUC Oct.-Nov."]
    vals = {lab: [val(s, g, ["coh_change_HH", "coh_change_VV", "coh_change_VH"]),
                  val(s, g, ["d_gamma0_HV", "d_gamma0_VH"]), late.get((s, g), np.nan)]
            for s, g, lab, _ in SERIES}

    fig, ax = plt.subplots(figsize=(10, 4.6), constrained_layout=True)
    w = 0.2
    x = np.arange(len(ind))
    for k, (s, g, lab, col) in enumerate(SERIES):
        v = vals[lab]
        bars = ax.bar(x + (k - 1.5) * w, v, w, label=lab, color=col,
                      edgecolor="k" if "desc" in lab else "none", linewidth=1.2 if "desc" in lab else 0)
        for b, y in zip(bars, v):
            ax.text(b.get_x() + b.get_width() / 2, y + 0.008, f"{y:.2f}", ha="center", va="bottom", fontsize=8)
    ax.axhline(0.5, color="0.5", ls=":", lw=1)
    ax.set_xticks(x, ind)
    ax.set_ylim(0.45, 1.05)
    ax.set_ylabel("separation AUC (clear-cut vs intact forest)")
    ax.set_title("black outline: descending geometries, the like-for-like L vs C comparison", fontsize=9, color="0.3", y=-0.22)
    ax.legend(ncol=4, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, 1.13), frameon=False)
    ax.grid(axis="y", alpha=0.3)
    FIG.mkdir(parents=True, exist_ok=True)
    out = FIG / "summary_L_vs_C.png"
    fig.savefig(out, dpi=200)
    print(f"figure written: {out}")
    for lab, v in vals.items():
        print(f"  {lab:18s} " + "  ".join(f"{y:.3f}" for y in v))


if __name__ == "__main__":
    main()
