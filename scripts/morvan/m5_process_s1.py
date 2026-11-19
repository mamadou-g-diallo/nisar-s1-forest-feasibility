"""Morvan step 5a — Sentinel-1 processing with SNAP gpt (same graphs as the Vosges study).

For every reduced SAFE of the 12-day chain of one orbit: terrain-flattened gamma0 (VV, VH); for
every pair of consecutive dates: coherence (VV, VH, window 10 x 3, flat-earth and topographic phase
removed). Output on the 20 m Lambert 93 grid, cropped to the radar window.
The window may span 2-3 bursts: they are processed together and merged by TOPSAR-Deburst.

Outputs: ``<data_root>/processed/sentinel1/t<orbit>/{g0_<date>.dim, coh_<ref>_<sec>.dim}``.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from nisar_s1.config import load_site
from nisar_s1.snap import s1_coherence, s1_gamma0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orbit", type=int, required=True)
    ap.add_argument("--only", choices=["gamma0", "coherence"], default=None)
    args = ap.parse_args()
    s = load_site("morvan")
    res, data = Path(s["chemins"]["results"]), Path(s["chemins"]["data_root"])
    crs = s["site"]["crs"]
    win = gpd.read_file(res / "fenetre_radar.geojson").to_crs(crs)
    x0, y0, x1, y1 = win.total_bounds
    m = 1000.0
    region = gpd.GeoSeries([box(x0 - m, y0 - m, x1 + m, y1 + m)], crs=crs).to_crs(4326).iloc[0]
    aoi = win.to_crs(4326).union_all().envelope
    sel = pd.read_csv(res / "tables" / f"s1_selected_t{args.orbit}.csv")
    raw = data / "sentinel1" / f"t{args.orbit:03d}"
    out = data / "processed" / "sentinel1" / f"t{args.orbit:03d}"
    out.mkdir(parents=True, exist_ok=True)
    safes = []
    for _, r in sel.iterrows():
        p = raw / f"{r.sceneName}.SAFE"
        safes.append((str(r.day)[:10], p, r.swath) if p.exists() else None)
        if not p.exists():
            print(f"absent : {p.name}, ignoré", flush=True)
    jobs = []
    if args.only in (None, "gamma0"):
        jobs += [("g0", d, p, None, sw) for d, p, sw in filter(None, safes)]
    if args.only in (None, "coherence"):
        jobs += [("coh", a[0], a[1], b, a[2]) for a, b in zip(safes[:-1], safes[1:]) if a and b]
    gpt, t0 = s["chemins"]["gpt"], time.time()
    for i, (kind, d, p, b, sw) in enumerate(jobs, 1):
        tag = f"[t{args.orbit} {i}/{len(jobs)}]"
        try:
            if kind == "g0":
                s1_gamma0(p, out / f"g0_{d}.dim", sw, aoi.wkt, region.wkt, gpt,
                          pixel_m=s["site"]["grille_m"], crs=crs, label=tag)
            else:
                s1_coherence(p, b[1], out / f"coh_{d}_{b[0]}.dim", sw, aoi.wkt, region.wkt, gpt,
                             pixel_m=s["site"]["grille_m"], crs=crs, label=tag)
        except Exception as e:
            print(f"{tag} {kind} {d} : ÉCHEC {e}", flush=True)
        print(f"{tag} {kind} {d} : {(time.time() - t0) / 60:.1f} min écoulées", flush=True)


if __name__ == "__main__":
    main()
