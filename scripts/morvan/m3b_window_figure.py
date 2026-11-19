"""Morvan step 3b — figure: qualified reference clear-cuts over G23 and the radar window.

Output: ``results/morvan/figures/s2_reference_window.png``.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from nisar_s1.config import load_site  # noqa: E402


def main() -> None:
    s = load_site("morvan")
    res = Path(s["chemins"]["results"])
    zone = gpd.read_file(res / "zone_g23.geojson")
    ref = gpd.read_file(res / "s2_coupes_guide.gpkg", layer="reference")
    win = gpd.read_file(res / "fenetre_radar.geojson")
    cols = {"feuillus": "#e08214", "resineux": "#542788", "mixte": "#1b9e77", "autre": "0.4",
            "peupleraie": "0.4"}
    fig, ax = plt.subplots(figsize=(7.2, 6.6), constrained_layout=True)
    zone.plot(ax=ax, color="#eef5e9", edgecolor="k", lw=0.6)
    for g, c in cols.items():
        sub = ref[ref.groupe == g]
        if len(sub):
            sub.centroid.plot(ax=ax, color=c, markersize=6 + 3 * sub.area_ha,
                              label=f"{g} ({len(sub)})")
    win.boundary.plot(ax=ax, color="#c0392b", lw=1.6)
    ax.annotate("radar window 20 x 20 km", xy=win.total_bounds[[0, 3]], xytext=(5, 6),
                textcoords="offset points", color="#c0392b", fontsize=9)
    ax.legend(title="Reference clear-cuts (size ~ area)", fontsize=8, loc="lower left")
    ax.set_title(f"G23 Morvan et Autunois: {len(ref)} clear-cuts >= 1 ha, July -> September 2026",
                 fontsize=10)
    ax.set_xticks([])
    ax.set_yticks([])
    out = res / "figures" / "s2_reference_window.png"
    fig.savefig(out, dpi=140)
    print(out)


if __name__ == "__main__":
    main()
