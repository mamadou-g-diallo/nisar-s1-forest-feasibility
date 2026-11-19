"""Step 3c — Fix the study site: chosen clear-cut polygon + intact control forest, with figures.

Orchestration only: logic in ``nisar_s1.sites``, ``nisar_s1.optical`` and ``nisar_s1.plots``.
Outputs: ``config/site.geojson`` (role = cut / control), ``results/figures/site_*.png``,
``results/tables/site_timeseries.csv``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import pandas as pd

from nisar_s1 import plots
from nisar_s1.config import PROJECT_ROOT, load_params
from nisar_s1.optical import forest_mask_like, load_raster, ndvi_timeseries, search_s2
from nisar_s1.sites import control_forest

PRE = ["2026-06-24", "2026-06-25", "2026-07-04", "2026-07-10"]
POST = ["2026-09-23", "2026-09-25", "2026-10-05", "2026-10-12"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", required=True, help="candidate id (results/site_candidates.geojson)")
    ap.add_argument("--res", type=int, default=20)
    ap.add_argument("--cut-window", nargs=2, default=None, help="dates bracketing the cut")
    ap.add_argument("--name", default=None, help="site name for titles")
    args = ap.parse_args()

    p = load_params()
    crs = p["projet"]["crs_travail"]
    bbox = p["aoi_recherche"]["bbox_wgs84"]
    cands = gpd.read_file(PROJECT_ROOT / "results" / "site_candidates.geojson")
    cut = cands[cands.cand_id == args.cand].to_crs(crs)
    tile = cut.tile.iloc[0]
    cache = Path(p["chemins"]["processed"]) / "sentinel2" / "composites"
    pre = load_raster(cache / f"ndvi_pre_{tile}_{args.res}m_{'_'.join(PRE)}.tif")
    post = load_raster(cache / f"ndvi_post_{tile}_{args.res}m_{'_'.join(POST)}.tif")
    forest = forest_mask_like(pre, bbox)
    ctrl = control_forest(cut.to_crs(pre.crs), pre, post, forest=forest).to_crs(crs)
    if ctrl.empty:
        raise SystemExit("no control forest found")
    print(f"cut {cut.area_ha.iloc[0]} ha, control {ctrl.area_ha.iloc[0]} ha, "
          f"control dNDVI {ctrl.dndvi.iloc[0]:.3f}")

    site = gpd.GeoDataFrame(
        {"role": ["cut", "control"], "cand_id": [args.cand, args.cand],
         "area_ha": [round(cut.geometry.iloc[0].area / 1e4, 2), round(ctrl.geometry.iloc[0].area / 1e4, 2)],
         "tile": [tile, tile]},
        geometry=[cut.geometry.iloc[0], ctrl.geometry.iloc[0]], crs=crs)

    # NDVI time series of both polygons (cut series reused from the verification step if present)
    s2 = search_s2(bbox, "2026-06-01", "2026-11-18", 50, tiles=[tile]).drop_duplicates(["tile", "date"])
    series = []
    for _, r in site.iterrows():
        ts = ndvi_timeseries(s2, r.geometry, crs)
        ts.insert(0, "role", r.role)
        series.append(ts)
        print(f"  {r.role}: {ts.ndvi.notna().sum()} clear dates", flush=True)
    ts = pd.concat(series)
    ts.to_csv(PROJECT_ROOT / "results" / "tables" / "site_timeseries.csv", index=False)

    ver = PROJECT_ROOT / "results" / "tables" / "site_candidates_verified.csv"
    cw = args.cut_window
    if cw is None and ver.exists():
        v = pd.read_csv(ver).set_index("cand_id")
        if args.cand in v.index and isinstance(v.loc[args.cand].get("cut_after"), str):
            cw = [v.loc[args.cand, "cut_after"], v.loc[args.cand, "cut_before"]]
    site["cut_after"], site["cut_before"] = (cw or [None, None])
    ll = site.to_crs("EPSG:4326").geometry.centroid
    site["lon"], site["lat"] = ll.x.round(5), ll.y.round(5)
    site.to_file(PROJECT_ROOT / "config" / "site.geojson", driver="GeoJSON")
    print(site.drop(columns="geometry").to_string(index=False))

    name = args.name or f"{args.cand} ({site.lat.iloc[0]:.4f} N, {site.lon.iloc[0]:.4f} E)"
    figs = PROJECT_ROOT / "results" / "figures"
    # map zoom: 1.5 km around the site
    from rasterio.windows import from_bounds
    xb = site.to_crs(pre.crs).total_bounds
    win = from_bounds(xb[0] - 1500, xb[1] - 1500, xb[2] + 1500, xb[3] + 1500, pre.transform).round_offsets().round_lengths()
    sl = (slice(max(win.row_off, 0), win.row_off + win.height), slice(max(win.col_off, 0), win.col_off + win.width))
    from nisar_s1.optical import Raster
    tr = pre.transform * pre.transform.translation(sl[1].start, sl[0].start)
    zpre, zpost = Raster(pre.data[sl], tr, pre.crs), Raster(post.data[sl], tr, pre.crs)
    plots.site_maps(zpre, zpost, site[site.role == "cut"].to_crs(pre.crs),
                    site[site.role == "control"].to_crs(pre.crs), figs / "site_ndvi_maps.png",
                    title=f"Sentinel-2 NDVI composites, site {name}")
    plots.ndvi_series(ts, figs / "site_ndvi_timeseries.png", cut_window=cw,
                      title=f"NDVI time series, site {name}")


if __name__ == "__main__":
    main()
