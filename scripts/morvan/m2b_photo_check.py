"""Morvan step 2b — photo-interpretation of the Sentinel-2 reference (guide section 3.9.1).

Each object is shown in three 800 m chips: true colour before (July), true colour after
(September), and SWIR / NIR / red false colour after, where fresh bare soil and logging residues are
pink-magenta while green or yellowing vegetation stays green. For every chip, the clearest date with
data and without cloud at the object is used (orbit-edge items are partly empty; scene cloud cover
is not local). The verdict is recorded by hand in ``results/morvan/tables/s2_photo_check*.csv``.

Sets: ``reference`` (random sample over G23), ``rejected`` (guide detections that failed the bare
soil criterion) and ``window`` (every reference object inside the radar window, split in pages).

Output: ``results/morvan/figures/s2_photo_check_<set>[_<page>].png``.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from shapely.geometry import shape  # noqa: E402

from nisar_s1.config import load_site  # noqa: E402
from nisar_s1.optical import rgb_chip, search_s2  # noqa: E402

HALF = 400.0     # chip half-size (m)
PANELS = (("avant", "2026-07-05", False), ("après", "2026-09-23", False), ("après SWIR", "2026-09-23", True))


def candidates(items, tile, near):
    """Items of ``tile`` ordered by cloud cover then distance to ``near``."""
    sub = items[items.tile == tile].copy()
    sub["gap"] = [abs((pd.Timestamp(d) - pd.Timestamp(near)).days) for d in sub.date]
    return list(sub.sort_values(["cloud", "gap"])["item"])


def clean_chip(items, tile, near, geom, crs, swir):
    """First chip with data everywhere and no bright cloud in its central part."""
    best = None
    for item in candidates(items, tile, near)[:6]:
        epsg = item.properties.get("proj:epsg") or int(item.properties["proj:code"].split(":")[1])
        g = gpd.GeoSeries([geom], crs=crs).to_crs(epsg)
        cx, cy = g.iloc[0].centroid.x, g.iloc[0].centroid.y
        tc = rgb_chip(item, (cx, cy), HALF, 10.0)
        n = tc.shape[0]
        centre = tc[n // 4: 3 * n // 4, n // 4: 3 * n // 4]
        empty = (tc.sum(axis=2) == 0).mean()
        cloudy = (centre.mean(axis=2) > 0.75).mean()
        img = rgb_chip(item, (cx, cy), HALF, 10.0, swir=True) if swir else tc
        cand = (empty + cloudy, img, g, (cx, cy), item.properties["datetime"][:10])
        if best is None or cand[0] < best[0]:
            best = cand
        if empty < 0.02 and cloudy < 0.02:
            break
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--set", choices=["reference", "rejected", "window"], default="reference")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--per-page", type=int, default=30)
    args = ap.parse_args()
    s = load_site("morvan")
    res = Path(s["chemins"]["results"])
    crs = s["site"]["crs"]
    ref = gpd.read_file(res / "s2_coupes_guide.gpkg", layer="reference")
    if args.set == "reference":
        objs = ref.sample(min(args.n, len(ref)), random_state=args.seed)
    elif args.set == "rejected":
        allo = gpd.read_file(res / "s2_coupes_guide.gpkg", layer="coupes")
        rej = allo[(allo.degre_max >= 2) & ~allo.intersects(ref.union_all())]
        objs = rej.sample(min(args.n, len(rej)), random_state=args.seed)
    else:
        win = gpd.read_file(res / "fenetre_radar.geojson").to_crs(crs)
        objs = ref[ref.intersects(win.geometry.iloc[0])].sort_values("id")
    objs = objs.reset_index(drop=True)
    ll = objs.to_crs(4326)
    bb = list(ll.total_bounds)
    pre = search_s2(bb, *map(str, s["periode"]["s2_avant"]), max_cloud=30)
    post = search_s2(bb, *map(str, s["periode"]["s2_apres"]), max_cloud=30)
    tiles = sorted(set(pre.tile) & set(post.tile))
    feet = {t: shape(pre[pre.tile == t].iloc[0]["item"].geometry) for t in tiles}

    def one(i):
        r = objs.iloc[i]
        c = ll.geometry.iloc[i].centroid
        tile = next((t for t in tiles if feet[t].contains(c)), None)
        if tile is None:
            return i, None
        out = []
        for name, near, swir in PANELS:
            items = pre if name == "avant" else post
            out.append(clean_chip(items, tile, near, r.geometry, crs, swir))
        return i, out

    with ThreadPoolExecutor(max_workers=4) as ex:
        chips = {}
        for k, (i, out) in enumerate(ex.map(one, range(len(objs))), 1):
            chips[i] = out
            print(f"[{k}/{len(objs)}] {objs.iloc[i].get('id', '')}", flush=True)

    per = args.per_page if args.set == "window" else len(objs)
    pages = [list(range(p, min(p + per, len(objs)))) for p in range(0, len(objs), per)]
    for pi, idx in enumerate(pages, 1):
        ncol = 9                                     # 3 objects per row, 3 panels each
        nrow = int(np.ceil(len(idx) / 3))
        fig, axs = plt.subplots(nrow, ncol, figsize=(1.75 * ncol, 1.95 * nrow))
        axs = np.atleast_2d(axs)
        for k, i in enumerate(idx):
            r = objs.iloc[i]
            row, col = divmod(k, 3)
            for j, (name, _, _) in enumerate(PANELS):
                ax = axs[row, 3 * col + j]
                ax.set_xticks([])
                ax.set_yticks([])
                if chips[i] is None:
                    continue
                _, img, g, (cx, cy), date = chips[i][j]
                ax.imshow(img, extent=(cx - HALF, cx + HALF, cy - HALF, cy + HALF))
                g.boundary.plot(ax=ax, color="yellow", lw=0.7)
                ax.set_xlim(cx - HALF, cx + HALF)
                ax.set_ylim(cy - HALF, cy + HALF)
                ax.set_xlabel("")
                ax.set_ylabel("")
                if j == 0:
                    ax.set_title(f"{r.get('id', '')} {r.area_ha:.1f}ha {str(r.groupe)[:4]} {date[5:]}", fontsize=6)
                else:
                    ax.set_title(f"{name} {date[5:]}" + (f" dNDVI {r.dndvi:.2f}" if j == 1 else ""), fontsize=6)
        for ax in axs.ravel()[3 * len(idx):]:
            ax.set_visible(False)
        fig.suptitle(f"{args.set}: before / after true colour / after SWIR-NIR-red (bare soil = pink)",
                     fontsize=8)
        fig.tight_layout()
        suffix = f"_{pi}" if len(pages) > 1 else ""
        out = res / "figures" / f"s2_photo_check_{args.set}{suffix}.png"
        fig.savefig(out, dpi=105)
        print(out)
    objs.drop(columns="geometry").to_csv(res / "tables" / f"s2_photo_sample_{args.set}.csv", index=False)


if __name__ == "__main__":
    main()
