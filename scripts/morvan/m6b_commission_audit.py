"""Morvan step 6b — audit of radar "commission" errors by photo-interpretation.

The Sentinel-2 reference can miss clear-cuts (cut after the "after" optical window, cloud, NDVI
drop too small, or a parcel that was not closed forest). Radar detections (guide transposition,
degree >= 2, >= 1 ha) that fall outside every reference object and its 40 m buffer are therefore
counted as commission although some may be real cuts. The largest ones are shown in true colour and
SWIR false colour before (July) and late (October-November) to classify them by hand.

Output: ``results/morvan/figures/m6b_commission_<geom>_<var>.png`` and
``results/morvan/tables/m6b_commission_<geom>_<var>.csv`` (verdicts recorded by hand).
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
from shapely.geometry import shape  # noqa: E402

from nisar_s1.config import load_site  # noqa: E402
from nisar_s1.grid import polygon_mask  # noqa: E402
from nisar_s1.guide_cr import vectorize  # noqa: E402
from nisar_s1.optical import Raster, load_raster, search_s2  # noqa: E402

import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).parent))
from m2b_photo_check import HALF, clean_chip  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--geom", required=True, help="e.g. NISAR_D66F65 or S1_T037")
    ap.add_argument("--var", required=True, help="e.g. d_g0_HV")
    ap.add_argument("--n", type=int, default=15)
    ap.add_argument("--degree", type=int, default=2)
    args = ap.parse_args()
    s = load_site("morvan")
    res, data = Path(s["chemins"]["results"]), Path(s["chemins"]["data_root"])
    crs = s["site"]["crs"]
    deg = load_raster(data / "analysis" / f"degres_{args.geom}_{args.var}.tif")
    grid = Raster(np.zeros(deg.data.shape, "float32"), deg.transform, deg.crs)
    # guide objects: sieved degree map (>= 1 ha) vectorised at degree >= 1, kept if they reach ``degree``
    objs = vectorize(np.nan_to_num(deg.data).astype("uint8"), grid, min_degree=1)
    objs = objs[objs.degre_max >= args.degree]
    allg = gpd.read_file(res / "s2_coupes_guide.gpkg", layer="coupes")
    ref = gpd.read_file(res / "s2_coupes_guide.gpkg", layer="reference")
    known = pd.concat([allg.geometry, ref.geometry]).buffer(40).union_all()
    fp = objs[~objs.intersects(known)].sort_values("area_ha", ascending=False).head(args.n).reset_index(drop=True)
    fp["id"] = [f"F{i + 1:02d}" for i in range(len(fp))]
    print(f"{len(objs)} détections radar, {int((~objs.intersects(known)).sum())} hors référence ; "
          f"audit des {len(fp)} plus grandes", flush=True)
    ll = fp.to_crs(4326)
    bb = list(ll.total_bounds)
    pre = search_s2(bb, *map(str, s["periode"]["s2_avant"]), max_cloud=30)
    late = search_s2(bb, "2026-10-15", "2026-11-19", max_cloud=40)
    tiles = sorted(set(pre.tile) & set(late.tile))
    feet = {t: shape(pre[pre.tile == t].iloc[0]["item"].geometry) for t in tiles}
    panels = (("avant", pre, "2026-07-05", False), ("tard", late, "2026-10-25", False),
              ("tard SWIR", late, "2026-10-25", True))
    nrow = int(np.ceil(len(fp) / 3))
    fig, axs = plt.subplots(nrow, 9, figsize=(15.5, 1.95 * nrow))
    axs = np.atleast_2d(axs)
    for k, r in fp.iterrows():
        c = ll.geometry.iloc[k].centroid
        tile = next((t for t in tiles if feet[t].contains(c)), None)
        row, col = divmod(k, 3)
        for j, (name, items, near, swir) in enumerate(panels):
            ax = axs[row, 3 * col + j]
            ax.set_xticks([])
            ax.set_yticks([])
            if tile is None:
                continue
            _, img, g, (cx, cy), date = clean_chip(items, tile, near, r.geometry, crs, swir)
            ax.imshow(img, extent=(cx - HALF, cx + HALF, cy - HALF, cy + HALF))
            g.boundary.plot(ax=ax, color="cyan", lw=0.7)
            ax.set_xlim(cx - HALF, cx + HALF)
            ax.set_ylim(cy - HALF, cy + HALF)
            ax.set_xlabel("")
            ax.set_ylabel("")
            ax.set_title((f"{r.id} {r.area_ha:.1f}ha " if j == 0 else "") + f"{name} {date[5:]}", fontsize=6)
        print(f"[{k + 1}/{len(fp)}] {r.id}", flush=True)
    for ax in axs.ravel()[3 * len(fp):]:
        ax.set_visible(False)
    fig.suptitle(f"Radar detections outside the optical reference — {args.geom} {args.var} (degree >= {args.degree})",
                 fontsize=8)
    fig.tight_layout()
    tag = f"{args.geom}_{args.var}"
    fig.savefig(res / "figures" / f"m6b_commission_{tag}.png", dpi=105)
    fp.drop(columns="geometry").to_csv(res / "tables" / f"m6b_commission_{tag}.csv", index=False)
    fp.to_file(res / "m6b_commission.gpkg", layer=tag, driver="GPKG")


if __name__ == "__main__":
    main()
