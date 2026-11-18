"""Step 3a — Detect clear-cut candidates from a Sentinel-2 NDVI pair over the Vosges tiles.

Orchestration only: logic in ``nisar_s1.optical`` and ``nisar_s1.sites``.
Outputs: ``results/site_candidates.geojson`` and ``results/tables/site_candidates.csv``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd

from nisar_s1.config import PROJECT_ROOT, load_params
from nisar_s1.optical import cached_composite, forest_mask_like, search_s2
from nisar_s1.sites import detect_clearcuts


def main() -> None:
    ap = argparse.ArgumentParser()
    # Median composites of clear dates (both tiles < 6 % cloud). Single dates are not robust:
    # 2026-09-22 has unmasked clouds that look like clear-cuts.
    ap.add_argument("--pre", nargs="+", default=["2026-06-24", "2026-06-25", "2026-07-04", "2026-07-10"])
    ap.add_argument("--post", nargs="+", default=["2026-09-23", "2026-09-25", "2026-10-05", "2026-10-12"])
    ap.add_argument("--drop", type=float, default=-0.3, help="dNDVI threshold")
    ap.add_argument("--min-ha", type=float, default=None, help="default: params surface_coupe_min_ha")
    ap.add_argument("--tiles", nargs="+", default=["32ULU", "32ULV"])
    ap.add_argument("--res", type=float, default=40.0)  # screening resolution
    args = ap.parse_args()

    p = load_params()
    bbox = p["aoi_recherche"]["bbox_wgs84"]
    c = p["comparaison"]
    s2 = search_s2(bbox, min(args.pre), max(args.post), max_cloud=30, tiles=args.tiles)

    out = []
    for tile in args.tiles:
        t = s2[s2.tile == tile]
        t = t.drop_duplicates("date")  # one item per date (lowest cloud first)
        pre = t[t.date.astype(str).isin(args.pre)]
        post = t[t.date.astype(str).isin(args.post)]
        print(f"{tile}: pre {list(pre.date.astype(str))}, post {list(post.date.astype(str))}")
        cache = Path(p["chemins"]["processed"]) / "sentinel2" / "composites"
        tag = f"{tile}_{int(args.res)}m"
        a = cached_composite(cache / f"ndvi_pre_{tag}_{'_'.join(args.pre)}.tif",
                             list(pre["item"]), args.res, bbox)
        b = cached_composite(cache / f"ndvi_post_{tag}_{'_'.join(args.post)}.tif",
                             list(post["item"]), args.res, bbox)
        forest = forest_mask_like(a, bbox)
        print(f"  forest (WorldCover tree cover): {forest.mean():.1%} of the window")
        min_ha = args.min_ha or c["surface_coupe_min_ha"]
        cand = detect_clearcuts(a, b, forest_min=0.7, drop_max=args.drop,
                                min_area_ha=min_ha, forest=forest)
        cand["tile"] = tile
        out.append(cand.to_crs(p["projet"]["crs_travail"]))
        print(f"  {len(cand)} candidates >= {min_ha} ha (dNDVI <= {args.drop})")

    gdf = gpd.GeoDataFrame(pd.concat(out, ignore_index=True), crs=p["projet"]["crs_travail"])
    gdf = gdf.sort_values("area_ha", ascending=False).reset_index(drop=True)
    gdf["cand_id"] = [f"C{i + 1:02d}" for i in range(len(gdf))]
    ll = gdf.to_crs("EPSG:4326").geometry.centroid
    gdf["lon"], gdf["lat"] = ll.x.round(5), ll.y.round(5)
    gdf.to_file(PROJECT_ROOT / "results" / "site_candidates.geojson", driver="GeoJSON")
    gdf.drop(columns="geometry").to_csv(PROJECT_ROOT / "results" / "tables" / "site_candidates.csv",
                                        index=False)
    print(gdf.drop(columns="geometry").head(20).to_string(index=False))


if __name__ == "__main__":
    main()
