"""Morvan step 4a — NISAR GCOV (gamma0 HH, HV) and GUNW (coherence) over the radar window.

Same remote chunk reading as the Vosges study (``nisar_s1.io_nisar``): only the HDF5 chunks that
cover the window are read over HTTPS. The window (``morvan/results/fenetre_radar.geojson``, chosen
at step 3) is reprojected into each product's own projection before reading.

Outputs: ``<data_root>/nisar/<geom>/<product>/<granule>__<layer>.tif`` and
``morvan/results/tables/nisar_extracted.csv``.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio.warp import transform_bounds

from nisar_s1.config import load_site
from nisar_s1.io_nisar import _grid, open_product, read_window
from nisar_s1.optical import load_raster, save_raster
from nisar_s1.search import search_nisar

LAYERS = {"GUNW": ["coh20", "coh80"], "GCOV": ["HHHH", "HVHV"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--products", nargs="+", default=["GCOV", "GUNW"])
    ap.add_argument("--margin", type=float, default=300.0)
    args = ap.parse_args()
    s = load_site("morvan")
    res, data = Path(s["chemins"]["results"]), Path(s["chemins"]["data_root"])
    win = gpd.read_file(res / "fenetre_radar.geojson").to_crs(s["site"]["crs"])
    x0, y0, x1, y1 = win.total_bounds
    m = args.margin
    b_l93 = (x0 - m, y0 - m, x1 + m, y1 + m)
    wkt = win.to_crs(4326).iloc[0].geometry.wkt
    df = search_nisar(wkt, *map(str, s["periode"]["recherche"]), product_types=args.products)
    df = df[((df["product"] == "GUNW") & (df.bw_code == "2000")) |
            ((df["product"] == "GCOV") & (df.bw_code == "2005") & (df.pol_code == "DHDH"))]
    wanted = {f"{g['direction']}{g['track']}" for g in s["capteurs"]["nisar"]["geometries"]}
    df["geom"] = df.direction + df.track.astype(str) + "F" + df.frame.astype(str)
    df = df[(df.direction + df.track.astype(str)).isin(wanted) & (df.aoi_cover >= 0.999)]
    df = df.drop_duplicates("sceneName").sort_values(["geom", "product", "startTime"]).reset_index(drop=True)
    print(df.groupby(["geom", "product"]).size().to_string(), flush=True)

    import earthaccess
    earthaccess.login(strategy="netrc")
    fs = earthaccess.get_fsspec_https_session()
    rows, t0 = [], time.time()
    for i, r in df.iterrows():
        tag = f"[{i + 1}/{len(df)}]"
        out_dir = data / "nisar" / r.geom / r["product"]
        name = Path(r.sceneName).stem
        row = {k: r[k] for k in ("sceneName", "product", "geom", "direction", "track", "frame",
                                 "ref_date", "sec_date", "baseline_days", "startTime")}
        todo = [lay for lay in LAYERS[r["product"]] if not (out_dir / f"{name}__{lay}.tif").exists()]
        try:
            for attempt in range(3):   # signed URLs expire: retry with a fresh session
                try:
                    if todo:
                        with open_product(r.url, fs=fs) as h5:
                            grp = "" if r["product"] == "GCOV" else "wrappedInterferogram"
                            g = _grid(h5, r["product"], grp)
                            epsg = int(g["projection"][()])
                            b = transform_bounds(s["site"]["crs"], f"EPSG:{epsg}", *b_l93, densify_pts=21)
                            for lay in todo:
                                save_raster(read_window(h5, r["product"], lay, b),
                                            out_dir / f"{name}__{lay}.tif")
                    break
                except Exception as e:
                    if attempt == 2:
                        raise
                    print(f"{tag} nouvel essai après {type(e).__name__}: {e}"[:160], flush=True)
                    earthaccess.login(strategy="netrc")
                    fs = earthaccess.get_fsspec_https_session()
                    todo = [lay for lay in todo if not (out_dir / f"{name}__{lay}.tif").exists()]
            a = load_raster(out_dir / f"{name}__{LAYERS[r['product']][0]}.tif").data
            row["valid_frac"] = float(np.isfinite(a).mean())
            row["status"] = "ok"
        except Exception as e:
            row["status"] = f"error: {type(e).__name__}: {e}"[:200]
        rows.append(row)
        print(f"{tag} {r['product']} {r.geom} {r.ref_date}"
              f"{' -> ' + str(r.sec_date) if r['product'] == 'GUNW' else ''} : {row['status']}"
              f" ({(time.time() - t0) / 60:.1f} min)", flush=True)
    out = pd.DataFrame(rows)
    (res / "tables").mkdir(parents=True, exist_ok=True)
    out.to_csv(res / "tables" / "nisar_extracted.csv", index=False)
    print(out.groupby(["geom", "product", "status"]).size().to_string())


if __name__ == "__main__":
    main()
