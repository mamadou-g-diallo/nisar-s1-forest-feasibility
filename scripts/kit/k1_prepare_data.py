"""Prepare the local data of the training notebooks (run once; resumable).

1. NISAR GSLC (complex HH/HV, ~13 GB each): only the AOI window is streamed from ASF and saved as a
   small HDF5 subset with the NISAR layout (``product.write_subset``), before and after the cut.
2. Sentinel-1 IW SLC (already downloaded for the feasibility study): dual-pol C2 matrix (VV/VH) with
   SNAP, ~40 m, same dates window (graph ``s1_c2``).

The GCOV of notebooks 01-12 is downloaded separately (full file, 2 GB) or streamed by the notebooks.
Usage: python scripts/kit/k1_prepare_data.py [--only gslc|s1]
"""
import argparse
import time
from pathlib import Path

from shapely.geometry import box

from nisar_s1 import product as P
from nisar_s1.config import load_kit, load_params
from nisar_s1.io_nisar import open_product
from nisar_s1.snap import s1_c2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["gslc", "s1"])
    args = ap.parse_args()
    kit, prm = load_kit(), load_params()
    data = Path(kit["data_dir"])
    bbox = kit["aoi"]["bbox_wgs84"]
    t0 = time.time()
    if args.only in (None, "gslc"):
        out = data / "gslc"
        out.mkdir(exist_ok=True)
        names = [kit["gslc"]["pre"], kit["gslc"]["post"]]
        for i, name in enumerate(names, 1):
            dst = out / f"{name}_{kit['aoi']['name']}.h5"
            if dst.exists():
                print(f"[{i}/{len(names)}] {dst.name}: already present", flush=True)
                continue
            url = kit["gslc"]["url"].format(granule=name, collection=kit["gslc"]["collection"])
            print(f"[{i}/{len(names)}] streaming AOI window of {name}", flush=True)
            with open_product(url, block_size=2**22) as h5:
                prof = P.product_profile(h5)
                g = prof.grids["frequencyA"]
                win = P.window_from_bounds(g, P.lonlat_to_proj(bbox, g.epsg))
                P.write_subset(h5, prof, win, dst)
            print(f"[{i}/{len(names)}] done ({dst.stat().st_size / 2**20:.0f} MB, "
                  f"{(time.time() - t0) / 60:.1f} min)", flush=True)
    if args.only in (None, "s1"):
        s1 = kit["sentinel1"]
        raw = Path(prm["chemins"]["raw"]) / "sentinel1" / f"t{s1['track']:03d}"
        out = data / "s1"
        out.mkdir(exist_ok=True)
        aoi = box(*bbox)
        region = aoi.buffer(0.005)
        names = [s1["pre"], s1["post"]]
        for i, name in enumerate(names, 1):
            day = name.split("_")[5][:8]
            s1_c2(raw / f"{name}.SAFE", out / f"c2_{day}.dim", s1["swath"], aoi.buffer(0.01).wkt,
                  region.wkt, prm["chemins"]["gpt"], pixel_m=s1["pixel_m"],
                  crs=prm["projet"]["crs_travail"], looks=tuple(s1["looks"]), label=f"[{i}/{len(names)}]")
            print(f"[{i}/{len(names)}] elapsed {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
