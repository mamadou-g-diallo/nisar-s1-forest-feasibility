"""Morvan step 2b — photo-interpretation check of the Sentinel-2 reference (guide section 3.9.1).

A random sample of reference clear-cuts, and of guide detections rejected by the "bare soil"
criterion, is shown before / after in true colour (10 m) with the object outline. The verdict of
the visual check is recorded by hand in ``results/morvan/tables/s2_photo_check.csv``.

Output: ``results/morvan/figures/s2_photo_check_<set>.png``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from nisar_s1.config import load_site  # noqa: E402
from nisar_s1.optical import rgb_chip, search_s2  # noqa: E402

HALF = 400.0     # chip half-size (m)


def candidates(items, tile, near):
    """Items of ``tile`` ordered by cloud cover then distance to ``near`` (the chip is taken from the
    first one that has data at the object: items at the edge of an orbit are partly empty)."""
    sub = items[items.tile == tile].copy()
    sub["gap"] = [abs((pd.Timestamp(d) - near).days) for d in sub.date]
    return list(sub.sort_values(["cloud", "gap"])["item"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--set", choices=["reference", "rejected"], default="reference")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    s = load_site("morvan")
    res = Path(s["chemins"]["results"])
    if args.set == "reference":
        objs = gpd.read_file(res / "s2_coupes_guide.gpkg", layer="reference")
    else:
        allo = gpd.read_file(res / "s2_coupes_guide.gpkg", layer="coupes")
        ref = gpd.read_file(res / "s2_coupes_guide.gpkg", layer="reference")
        objs = allo[(allo.degre_max >= 2) & ~allo.intersects(ref.union_all())]
    sample = objs.sample(min(args.n, len(objs)), random_state=args.seed).reset_index(drop=True)
    ll = sample.to_crs(4326)
    bb = list(ll.total_bounds)
    import pandas as pd
    pre = search_s2(bb, *map(str, s["periode"]["s2_avant"]), max_cloud=5)
    post = search_s2(bb, *map(str, s["periode"]["s2_apres"]), max_cloud=5)
    tiles = sorted(set(pre.tile) & set(post.tile))
    ncol = 6
    nrow = int(np.ceil(len(sample) / (ncol // 2)))
    fig, axs = plt.subplots(nrow, ncol, figsize=(2.3 * ncol, 2.4 * nrow))
    axs = np.atleast_2d(axs)
    for k, (i, r) in enumerate(sample.iterrows()):
        c = ll.geometry.iloc[i].centroid
        # tile whose footprint contains the centroid
        tile = None
        for t in tiles:
            it = pre[pre.tile == t].iloc[0]["item"]
            from shapely.geometry import shape
            if shape(it.geometry).contains(c):
                tile = t
                break
        row, col = divmod(k, ncol // 2)
        for j, (items, near) in enumerate(((pre, pd.Timestamp("2026-07-05")),
                                           (post, pd.Timestamp("2026-09-23")))):
            ax = axs[row, 2 * col + j]
            ax.set_xticks([])
            ax.set_yticks([])
            if tile is None:
                continue
            for item in candidates(items, tile, near)[:4]:
                epsg = item.properties.get("proj:epsg") or int(item.properties["proj:code"].split(":")[1])
                g = gpd.GeoSeries([r.geometry], crs=s["site"]["crs"]).to_crs(epsg)
                cx, cy = g.iloc[0].centroid.x, g.iloc[0].centroid.y
                img = rgb_chip(item, (cx, cy), HALF, 10.0)
                if (img.sum(axis=2) > 0).mean() > 0.95:
                    break
            ax.imshow(img, extent=(cx - HALF, cx + HALF, cy - HALF, cy + HALF))
            g.boundary.plot(ax=ax, color="yellow", lw=0.8)
            ax.set_xlim(cx - HALF, cx + HALF)
            ax.set_ylim(cy - HALF, cy + HALF)
            if j == 0:
                ax.set_title(f"{k + 1}. {r.get('id', '')} {r.area_ha:.1f} ha {r.groupe[:4]} {item.properties['datetime'][5:10]}", fontsize=7)
            else:
                ax.set_title(f"{item.properties['datetime'][:10]}  dNDVI {r.dndvi:.2f}", fontsize=7)
        print(f"[{k + 1}/{len(sample)}] {r.get('id', '')}", flush=True)
    for ax in axs.ravel()[2 * len(sample):]:
        ax.set_visible(False)
    fig.suptitle(f"{args.set}: true colour before (July) / after (September), outline in yellow", fontsize=9)
    fig.tight_layout()
    out = res / "figures" / f"s2_photo_check_{args.set}.png"
    fig.savefig(out, dpi=110)
    sample.drop(columns="geometry").assign(n=range(1, len(sample) + 1)).to_csv(
        res / "tables" / f"s2_photo_sample_{args.set}.csv", index=False)
    print(out)


if __name__ == "__main__":
    main()
