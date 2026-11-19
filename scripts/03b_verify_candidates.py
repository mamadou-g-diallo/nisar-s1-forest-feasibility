"""Step 3b — Verify clear-cut candidates with an NDVI time series (June -> mid-November 2026).

Orchestration only: logic in ``nisar_s1.optical.ndvi_timeseries`` and ``nisar_s1.sites.classify_timeseries``.
Output: ``results/tables/site_candidates_verified.csv`` and per-candidate time series.
"""

from __future__ import annotations

import argparse

import geopandas as gpd
import pandas as pd

from nisar_s1.config import PROJECT_ROOT, load_params
from nisar_s1.optical import ndvi_timeseries, search_s2
from nisar_s1.sites import classify_timeseries


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=15, help="number of candidates (largest first)")
    ap.add_argument("--start", default="2026-06-01")
    ap.add_argument("--end", default="2026-11-18")
    ap.add_argument("--max-cloud", type=float, default=50)
    ap.add_argument("--cut-window", nargs=2, default=["2026-07-11", "2026-09-22"])
    args = ap.parse_args()

    p = load_params()
    cand = gpd.read_file(PROJECT_ROOT / "results" / "site_candidates.geojson").head(args.top)
    s2 = search_s2(p["aoi_recherche"]["bbox_wgs84"], args.start, args.end, args.max_cloud,
                   tiles=sorted(cand.tile.unique()))
    s2 = s2.drop_duplicates(["tile", "date"])
    rows, series = [], []
    for _, c in cand.iterrows():
        ts = ndvi_timeseries(s2[s2.tile == c.tile], c.geometry, cand.crs)
        ts.insert(0, "cand_id", c.cand_id)
        series.append(ts)
        res = classify_timeseries(ts, tuple(args.cut_window))
        rows.append({"cand_id": c.cand_id, "area_ha": c.area_ha, "lon": c.lon, "lat": c.lat, **res})
        print(rows[-1], flush=True)
    out = PROJECT_ROOT / "results" / "tables"
    pd.DataFrame(rows).to_csv(out / "site_candidates_verified.csv", index=False)
    pd.concat(series).to_csv(out / "site_candidates_timeseries.csv", index=False)


if __name__ == "__main__":
    main()
