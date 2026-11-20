"""Morvan step 7 — radar time series and dating of the photo-interpreted clear-cuts.

For every confirmed clear-cut of the radar window (step 2b) and every geometry (NISAR A173 / D66,
Sentinel-1 A59 / D37): median cross-polarised gamma0 (HV / VH) per acquisition date, compared with
the median of intact forest of the same date. The radar cut date is the first acquisition where
gamma0 falls more than ``--drop`` dB below the mean of the acquisitions before July and stays below
on the next acquisition (a single low date is not enough). The cut is then dated between the
previous acquisition and that one.

Outputs: ``results/morvan/figures/m7_cut_timeseries.png`` and ``results/morvan/tables/m7_cut_dates.csv``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from m6_compare import db, nisar_layers, s1_layers  # noqa: E402

from nisar_s1.config import load_site  # noqa: E402
from nisar_s1.grid import make_grid, polygon_mask, to_grid  # noqa: E402
from nisar_s1.optical import load_raster  # noqa: E402

CROSS = {"NISAR": "HV", "S1": "VH"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", type=float, default=2.0)
    args = ap.parse_args()
    s = load_site("morvan")
    res, data = Path(s["chemins"]["results"]), Path(s["chemins"]["data_root"])
    win = gpd.read_file(res / "fenetre_radar.geojson")
    grid = make_grid(tuple(win.total_bounds), s["site"]["grille_m"], s["site"]["crs"])
    ref = gpd.read_file(res / "s2_coupes_guide.gpkg", layer="reference")
    ver = pd.read_csv(res / "tables" / "s2_photo_check_window.csv").set_index("id").verdict
    fb = pd.read_csv(res / "tables" / "s2_forest_before.csv").set_index("id").foret_avant
    cuts = ref[ref.id.map(ver) == "coupe"].copy()
    cuts["foret_avant"] = cuts.id.map(fb).fillna(False).astype(bool)
    cuts = cuts.sort_values("id").reset_index(drop=True)
    dndvi = to_grid(load_raster(data / "s2" / "dndvi_l93.tif"), grid, "nearest").data
    grp = to_grid(load_raster(data / "s2" / "forest_group_l93.tif"), grid, "nearest").data
    thr = pd.read_csv(res / "tables" / "s2_guide_thresholds.csv").iloc[0]
    intact = (grp > 0) & (np.abs(dndvi - thr.m) <= thr.sigma)
    masks = {r.id: polygon_mask([r.geometry], grid) for r in cuts.itertuples()}

    geoms = {}
    geoms.update(nisar_layers(data / "nisar", grid))
    geoms.update(s1_layers(data / "processed" / "sentinel1", grid))
    pre_end = pd.Timestamp(s["periode"]["radar_avant"][1])
    rows, series = [], {}
    for gname, layers in sorted(geoms.items()):
        pol = CROSS[gname.split()[0]]
        lay = sorted([l for l in layers if l["kind"] == "g0" and l["pol"] == pol], key=lambda l: l["d1"])
        dates = [l["d1"] for l in lay]
        forest = [np.nanmedian(db(l["data"])[intact]) for l in lay]
        series[gname] = {"dates": dates, "forest": forest, "cuts": {}}
        for cid, m in masks.items():
            v = np.array([np.nanmedian(db(l["data"])[m]) for l in lay])
            series[gname]["cuts"][cid] = v
            pre = v[[d <= pre_end for d in dates]]
            base = np.nanmean(pre) if pre.size else np.nan
            low = v < base - args.drop
            k = next((i for i in range(len(v) - 1) if dates[i] > pre_end and low[i] and low[i + 1]), None)
            rows.append({"id": cid, "geom": gname, "niveau_avant_db": round(float(base), 2),
                         "chute_max_db": round(float(np.nanmin(v[[d > pre_end for d in dates]]) - base), 2)
                         if pre.size else np.nan,
                         "coupe_apres": dates[k - 1].date() if k else None,
                         "coupe_avant": dates[k].date() if k is not None else None})
    out = pd.DataFrame(rows)
    out = out.merge(cuts[["id", "groupe", "area_ha", "foret_avant"]], on="id")
    out.to_csv(res / "tables" / "m7_cut_dates.csv", index=False)
    piv = out.assign(f=lambda d: d.coupe_apres.astype(str) + " -> " + d.coupe_avant.astype(str))
    print(piv.pivot(index="id", columns="geom", values="f").to_string())

    names = sorted(series)
    fig, axs = plt.subplots(2, 2, figsize=(12, 7.5), sharex=True, constrained_layout=True)
    colors = plt.cm.tab10(np.arange(len(cuts)))
    for ax, gname in zip(axs.ravel(), names):
        sr = series[gname]
        for c, r in zip(colors, cuts.itertuples()):
            ax.plot(sr["dates"], sr["cuts"][r.id], "-o" if r.foret_avant else "--", ms=3, color=c,
                    lw=1.3 if r.foret_avant else 0.9, label=f"{r.id} ({r.groupe[:4]})")
        ax.plot(sr["dates"], sr["forest"], "k-", lw=2.4, label="intact forest (median)")
        ax.axvspan(pd.Timestamp(s["periode"]["radar_avant"][1]), pd.Timestamp(s["periode"]["radar_apres"][0]),
                   color="0.9", zorder=0)
        ax.set_title(f"{gname} — gamma0 {CROSS[gname.split()[0]]} (dB)", fontsize=10)
        ax.grid(alpha=0.3)
    axs[0, 0].legend(fontsize=7, ncol=2, loc="lower left")
    fig.suptitle("Confirmed clear-cuts (solid: standing forest before, Sentinel-2 SWIR; dashed: not closed "
                 "forest before). Grey band: between the two reference windows.", fontsize=9)
    fig.savefig(res / "figures" / "m7_cut_timeseries.png", dpi=130)


if __name__ == "__main__":
    main()
