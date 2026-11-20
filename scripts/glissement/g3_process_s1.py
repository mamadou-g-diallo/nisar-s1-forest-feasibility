"""Landslide step 3 — Sentinel-1 interferograms with SNAP gpt (graph ``s1_interferogram``):
consecutive pairs of the dates selected at step 2 (the same pairs as NISAR), VV, ESD, flat-earth and
topographic phase removed (Copernicus DEM 30 m), 4 x 1 looks, coherence window 10 x 3, 20 m
Lambert 93 grid. Pairs are processed as soon as both SAFEs are downloaded (one gpt at a time: 8 GB RAM).

Outputs: ``<data_root>/processed/sentinel1/t<orbit>/ifg_<ref>_<sec>.dim``.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from nisar_s1.config import bbox_to_wkt, load_site
from nisar_s1.snap import s1_interferogram


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orbits", type=int, nargs="+", default=[161, 139])
    ap.add_argument("--wait-h", type=float, default=4.0, help="max wait for a missing SAFE")
    args = ap.parse_args()
    s = load_site("sechilienne")
    res, data = Path(s["chemins"]["results"]), Path(s["chemins"]["data_root"])
    x0, x1, y0, y1 = s["site"]["bbox_wgs84"]
    aoi = bbox_to_wkt([x0, y0, x1, y1])
    region = bbox_to_wkt([x0 - 0.01, y0 - 0.01, x1 + 0.01, y1 + 0.01])
    jobs = []
    for o in args.orbits:
        sel = pd.read_csv(res / "tables" / f"s1_selected_t{o}.csv")
        raw = data / "sentinel1" / f"t{o:03d}"
        items = [(str(r.day)[:10], raw / f"{r.sceneName}.SAFE", r.swath) for _, r in sel.iterrows()]
        jobs += [(o, a, b) for a, b in zip(items[:-1], items[1:])]
    t0 = time.time()
    for i, (o, a, b) in enumerate(jobs, 1):
        tag = f"[t{o} {i}/{len(jobs)}]"
        out = data / "processed" / "sentinel1" / f"t{o:03d}" / f"ifg_{a[0]}_{b[0]}.dim"
        out.parent.mkdir(parents=True, exist_ok=True)
        tw = time.time()
        while not (a[1].exists() and b[1].exists()):
            if time.time() - tw > args.wait_h * 3600:
                break
            time.sleep(60)
        if not (a[1].exists() and b[1].exists()):
            print(f"{tag} {a[0]} -> {b[0]} : SAFE absent, paire ignorée", flush=True)
            continue
        try:
            s1_interferogram(a[1], b[1], out, a[2], aoi, region, s["chemins"]["gpt"],
                             pixel_m=s["site"]["grille_m"], crs=s["site"]["crs"], label=tag)
        except Exception as e:
            print(f"{tag} {a[0]} -> {b[0]} : ÉCHEC {e}", flush=True)
        print(f"{tag} {a[0]} -> {b[0]} : {(time.time() - t0) / 60:.1f} min écoulées", flush=True)


if __name__ == "__main__":
    main()
