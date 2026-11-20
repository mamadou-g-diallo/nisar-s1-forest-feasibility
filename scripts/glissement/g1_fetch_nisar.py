"""Landslide step 1 — NISAR GUNW over the Séchilienne window: coherence (20 m wrapped grid and 80 m
unwrapped grid), unwrapped phase, connected components and ionosphere phase screen.

Remote chunk reading as for the Vosges and Morvan (``nisar_s1.io_nisar``).
Outputs: ``<data_root>/nisar/<geom>/GUNW/<granule>__<layer>.tif`` and
``results/sechilienne/tables/nisar_gunw.csv``.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd
from rasterio.warp import transform_bounds

from nisar_s1.config import bbox_to_wkt, load_site
from nisar_s1.io_nisar import _grid, open_product, read_window
from nisar_s1.optical import load_raster, save_raster
from nisar_s1.search import search_nisar

LAYERS = ["coh20", "coh80", "unw", "conncomp", "iono"]


def main() -> None:
    s = load_site("sechilienne")
    res, data = Path(s["chemins"]["results"]), Path(s["chemins"]["data_root"])
    x0, x1, y0, y1 = s["site"]["bbox_wgs84"]
    wkt = bbox_to_wkt([x0, y0, x1, y1])
    nis = s["capteurs"]["nisar"]
    df = search_nisar(wkt, *map(str, s["periode"]["recherche"]), product_types=["GUNW"])
    wanted = {f"{g['direction']}{g['track']}" for g in nis["geometries"]}
    df["geom"] = df.direction + df.track.astype(str)
    df = df[df.geom.isin(wanted) & (df.bw_code == nis["bw_code"]) & (df.aoi_cover >= 0.999)]
    df = df.drop_duplicates("sceneName").sort_values(["geom", "ref_date", "sec_date"]).reset_index(drop=True)
    print(df.groupby("geom").size().to_string(), flush=True)

    import earthaccess
    earthaccess.login(strategy="netrc")
    fs = earthaccess.get_fsspec_https_session()
    rows, t0 = [], time.time()
    for i, r in df.iterrows():
        tag = f"[{i + 1}/{len(df)}]"
        out_dir = data / "nisar" / r.geom / "GUNW"
        name = Path(r.sceneName).stem
        row = {k: r[k] for k in ("sceneName", "geom", "direction", "track", "frame",
                                 "ref_date", "sec_date", "baseline_days")}
        todo = [lay for lay in LAYERS if not (out_dir / f"{name}__{lay}.tif").exists()]
        try:
            for attempt in range(3):
                try:
                    if todo:
                        with open_product(r.url, fs=fs) as h5:
                            g = _grid(h5, "GUNW", "unwrappedInterferogram")
                            epsg = int(g["projection"][()])
                            b = transform_bounds("EPSG:4326", f"EPSG:{epsg}", x0, y0, x1, y1,
                                                 densify_pts=21)
                            for lay in todo:
                                try:
                                    save_raster(read_window(h5, "GUNW", lay, b),
                                                out_dir / f"{name}__{lay}.tif")
                                except KeyError as e:   # e.g. no ionosphere layer
                                    print(f"{tag} {lay} absent : {e}", flush=True)
                    break
                except Exception as e:
                    if attempt == 2:
                        raise
                    print(f"{tag} nouvel essai après {type(e).__name__}: {e}"[:160], flush=True)
                    earthaccess.login(strategy="netrc")
                    fs = earthaccess.get_fsspec_https_session()
                    todo = [lay for lay in todo if not (out_dir / f"{name}__{lay}.tif").exists()]
            a = load_raster(out_dir / f"{name}__coh80.tif").data
            row["coh80_median"] = float(np.nanmedian(a))
            row["status"] = "ok"
        except Exception as e:
            row["status"] = f"error: {type(e).__name__}: {e}"[:200]
        rows.append(row)
        print(f"{tag} {r.geom} {r.ref_date} -> {r.sec_date} ({r.baseline_days} j) : {row['status']}"
              f" ({(time.time() - t0) / 60:.1f} min)", flush=True)
    out = pd.DataFrame(rows)
    (res / "tables").mkdir(parents=True, exist_ok=True)
    out.to_csv(res / "tables" / "nisar_gunw.csv", index=False)
    print(out.groupby(["geom", "status"]).size().to_string())


if __name__ == "__main__":
    main()
