"""Step 4a — Extract NISAR GUNW and GCOV sub-scenes over the study site.

NISAR L2 HDF5 files are chunked (512 x 512), so only the chunks covering the site window are read
from the Earthdata HTTPS URL (about 15 s per layer instead of ~20 min to download a 2-2.5 GB file
at the measured ~1.8 MB/s). Every acquisition geometry whose footprint fully contains the window
is used. Logic in ``nisar_s1.search`` and ``nisar_s1.io_nisar``.

Outputs: ``<processed>/nisar/<A144F26>/<product>/<granule>__<layer>.tif`` and the provenance table
``vosges/results/tables/nisar_extracted.csv`` (one row per granule, with dates and valid fraction).
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box, shape

from nisar_s1.config import PROJECT_ROOT, load_params
from nisar_s1.io_nisar import open_product, read_window
from nisar_s1.optical import save_raster
from nisar_s1.search import search_nisar

LAYERS = {"GUNW": ["coh20", "coh80", "unw", "conncomp"], "GCOV": ["HHHH", "HVHV"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=str(PROJECT_ROOT / "config" / "site.geojson"))
    ap.add_argument("--margin", type=float, default=1500.0, help="window margin around the site (m)")
    ap.add_argument("--products", nargs="+", default=["GUNW", "GCOV"])
    args = ap.parse_args()

    p = load_params()
    crs = p["projet"]["crs_travail"]
    site = gpd.read_file(args.site).to_crs(crs)
    xmin, ymin, xmax, ymax = site.total_bounds
    m = args.margin
    bounds = (xmin - m, ymin - m, xmax + m, ymax + m)
    win_ll = gpd.GeoSeries([box(*bounds)], crs=crs).to_crs("EPSG:4326").iloc[0]
    print(f"window {bounds} ({(bounds[2] - bounds[0]) / 1e3:.1f} x {(bounds[3] - bounds[1]) / 1e3:.1f} km)")

    df = search_nisar(win_ll.wkt, str(p["periode"]["debut"]), str(p["periode"]["fin"]),
                      product_types=args.products)
    # only main-band modes of interest, and full coverage of the window
    df = df[((df["product"] == "GUNW") & (df.bw_code == "2000")) |
            ((df["product"] == "GCOV") & (df.bw_code == "2005") & (df.pol_code == "DHDH"))]
    df = df[df.aoi_cover >= 0.999].drop_duplicates("sceneName").reset_index(drop=True)
    df["geom"] = df.direction + df.track.astype(str) + "F" + df.frame.astype(str)
    print(df.groupby(["product", "geom"]).size().to_string(), flush=True)

    import earthaccess
    earthaccess.login(strategy="netrc")
    fs = earthaccess.get_fsspec_https_session()
    root = Path(p["chemins"]["processed"]) / "nisar"
    rows, t0 = [], time.time()
    for i, r in df.iterrows():
        tag = f"[{i + 1}/{len(df)}]"
        out_dir = root / r.geom / r["product"]
        name = Path(r.sceneName).stem
        row = {k: r[k] for k in ("sceneName", "product", "geom", "direction", "track", "frame",
                                 "ref_date", "sec_date", "baseline_days", "startTime")}
        todo = [l for l in LAYERS[r["product"]] if not (out_dir / f"{name}__{l}.tif").exists()]
        try:
            for attempt in range(3):  # signed CloudFront URLs expire: retry with a fresh session
                try:
                    if todo:
                        with open_product(r.url, fs=fs) as h5:
                            for layer in todo:
                                ras = read_window(h5, r["product"], layer, bounds)
                                save_raster(ras, out_dir / f"{name}__{layer}.tif")
                    break
                except Exception as e:
                    if attempt == 2:
                        raise
                    print(f"{tag} retry after {type(e).__name__}", flush=True)
                    earthaccess.login(strategy="netrc")
                    fs = earthaccess.get_fsspec_https_session()
                    todo = [l for l in todo if not (out_dir / f"{name}__{l}.tif").exists()]
            first = LAYERS[r["product"]][0]
            from nisar_s1.optical import load_raster
            a = load_raster(out_dir / f"{name}__{first}.tif").data
            row["valid_frac"] = float(np.isfinite(a).mean() if a.dtype.kind == "f" else 1.0)
            row["status"] = "ok"
        except Exception as e:  # keep going, record the failure
            row["status"] = f"error: {type(e).__name__}: {e}"[:200]
        rows.append(row)
        print(f"{tag} {r['product']} {r.geom} {r.ref_date}"
              f"{' -> ' + str(r.sec_date) if r['product'] == 'GUNW' else ''}: {row['status']}"
              f" (elapsed {(time.time() - t0) / 60:.1f} min)", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(PROJECT_ROOT / "vosges" / "results" / "tables" / "nisar_extracted.csv", index=False)
    print(out.groupby(["product", "geom", "status"]).size().to_string())


if __name__ == "__main__":
    main()
