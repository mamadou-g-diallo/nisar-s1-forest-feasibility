"""Step 5a — Sentinel-1 processing with SNAP gpt over the site window.

For every reduced SAFE of the selected chain: terrain-flattened gamma0 (VV, VH); for every pair of
consecutive dates (12 days): coherence (VV, VH). Output on the 20 m UTM 32N grid, cropped to the
site window. Logic in ``nisar_s1.snap`` (graphs in ``nisar_s1/graphs``).

Outputs: ``<processed>/sentinel1/t<track>/{g0_<date>.dim, coh_<ref>_<sec>.dim} (BEAM-DIMAP)``.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from nisar_s1.config import PROJECT_ROOT, load_params
from nisar_s1.snap import s1_coherence, s1_gamma0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", type=int, default=None)
    ap.add_argument("--margin", type=float, default=1500.0)
    ap.add_argument("--only", choices=["gamma0", "coherence"], default=None)
    args = ap.parse_args()

    p = load_params()
    track = args.track or p["capteurs"]["sentinel1"]["orbites_prioritaires"][0]
    crs = p["projet"]["crs_travail"]
    res = p["comparaison"]["grille_m"]
    site = gpd.read_file(PROJECT_ROOT / "config" / "site.geojson").to_crs(crs)
    xmin, ymin, xmax, ymax = site.total_bounds
    m = args.margin + 500  # a bit wider than the analysis window (cropping happens later)
    region = gpd.GeoSeries([box(xmin - m, ymin - m, xmax + m, ymax + m)], crs=crs).to_crs("EPSG:4326").iloc[0]
    aoi = site.to_crs("EPSG:4326").union_all().envelope.buffer(0.01)

    sel = pd.read_csv(PROJECT_ROOT / "results" / "tables" / f"s1_selected_t{track}.csv")
    raw = Path(p["chemins"]["raw"]) / "sentinel1" / f"t{track:03d}"
    out = Path(p["chemins"]["processed"]) / "sentinel1" / f"t{track:03d}"
    out.mkdir(parents=True, exist_ok=True)
    safes = []
    for _, r in sel.iterrows():
        s = raw / f"{r.sceneName}.SAFE"
        if s.exists():
            safes.append((str(r.day)[:10], s, r.swath))
        else:
            safes.append(None)  # keeps chain positions: no pair across a missing date
            print(f"missing {s.name} (not downloaded yet), skipped", flush=True)
    gpt = p["chemins"]["gpt"]
    t0 = time.time()
    jobs = []
    if args.only in (None, "gamma0"):
        jobs += [("g0", d, s, None, sw) for d, s, sw in filter(None, safes)]
    if args.only in (None, "coherence"):
        jobs += [("coh", a[0], a[1], b, a[2]) for a, b in zip(safes[:-1], safes[1:]) if a and b]
    for i, (kind, d, s, b, sw) in enumerate(jobs, 1):
        tag = f"[{i}/{len(jobs)}]"
        try:
            if kind == "g0":
                s1_gamma0(s, out / f"g0_{d}.dim", sw, aoi.wkt, region.wkt, gpt, pixel_m=res, crs=crs, label=tag)
            else:
                s1_coherence(s, b[1], out / f"coh_{d}_{b[0]}.dim", sw, aoi.wkt, region.wkt, gpt,
                             pixel_m=res, crs=crs, label=tag)
        except Exception as e:
            print(f"{tag} {kind} {d}: FAILED {e}", flush=True)
        print(f"{tag} {kind} {d} elapsed {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
