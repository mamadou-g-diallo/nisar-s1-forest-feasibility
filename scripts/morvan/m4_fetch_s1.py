"""Morvan step 4b — Sentinel-1 IW SLC over the radar window: one ascending and one descending orbit
(chosen at step 3), 12-day chains as NISAR, reduced SAFE (only the sub-swath of the window, VV+VH).

Outputs: ``<data_root>/sentinel1/t<orbit>/<SAFE>`` and ``results/morvan/tables/s1_selected_t<orbit>.csv``.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import asf_search as asf
import geopandas as gpd

from nisar_s1.config import load_site
from nisar_s1.download import earthdata_session, extract_safe_subset
from nisar_s1.search import search_s1, select_chain


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orbit", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--shard", default="0/1", help="i/n: dates i, i+n, ... (parallel streams)")
    args = ap.parse_args()
    s = load_site("morvan")
    res, data = Path(s["chemins"]["results"]), Path(s["chemins"]["data_root"])
    win = gpd.read_file(res / "fenetre_radar.geojson").to_crs(4326).iloc[0].geometry
    start, end = map(str, s["periode"]["recherche"])
    bursts = asf.search(dataset="SLC-BURST", intersectsWith=win.wkt, relativeOrbit=args.orbit,
                        start=start, end=end, maxResults=200)
    swaths = sorted({b.properties["burst"]["subswath"] for b in bursts})
    if len(swaths) != 1:
        raise SystemExit(f"orbite {args.orbit} : sous-fauchées {swaths} (une seule attendue)")
    swath = swaths[0].lower()
    s1 = search_s1(win.wkt, start, end)
    s1 = s1[s1.pathNumber == args.orbit]
    chain = select_chain(s1, start, 12)
    chain["swath"] = swath
    (res / "tables").mkdir(parents=True, exist_ok=True)
    chain.drop(columns=["url"]).to_csv(res / "tables" / f"s1_selected_t{args.orbit}.csv", index=False)
    print(f"orbite {args.orbit}, sous-fauchée {swath}, {len(chain)} dates :")
    print(chain[["sceneName", "day", "platform"]].to_string(index=False), flush=True)
    if args.dry_run:
        return
    si, sn = map(int, args.shard.split("/"))
    chain = chain.iloc[si::sn]
    sess = earthdata_session()
    out = data / "sentinel1" / f"t{args.orbit:03d}"
    t0 = time.time()
    for k, (_, r) in enumerate(chain.iterrows(), 1):
        tag = f"[t{args.orbit} lot {si} : {k}/{len(chain)}]"
        try:
            extract_safe_subset(r.url, out, swath, session=sess, label=tag)
        except Exception as e:
            print(f"{tag} {r.sceneName} : ÉCHEC {type(e).__name__}: {e}", flush=True)
        print(f"{tag} {(time.time() - t0) / 60:.1f} min écoulées", flush=True)


if __name__ == "__main__":
    main()
