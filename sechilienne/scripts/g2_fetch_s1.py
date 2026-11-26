"""Landslide step 2 — Sentinel-1 IW SLC (reduced SAFE: one sub-swath, VV only) on the dates closest
to the NISAR acquisitions of the paired geometry (A161 <-> NISAR A173, D139 <-> NISAR D138).

Only VV is needed for interferometry (best coherence of the two channels). Outputs:
``<data_root>/sentinel1/t<orbit>/<SAFE>`` and ``sechilienne/results/tables/s1_selected_t<orbit>.csv``.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import asf_search as asf
import pandas as pd

from nisar_s1.config import bbox_to_wkt, load_site
from nisar_s1.download import earthdata_session, extract_safe_subset
from nisar_s1.search import search_nisar, search_s1

PAIRING = {161: "A173", 139: "D138"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orbit", type=int, required=True, choices=list(PAIRING))
    ap.add_argument("--max-gap", type=int, default=6, help="max |S1 - NISAR| in days")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--shard", default="0/1")
    args = ap.parse_args()
    s = load_site("sechilienne")
    res, data = Path(s["chemins"]["results"]), Path(s["chemins"]["data_root"])
    x0, x1, y0, y1 = s["site"]["bbox_wgs84"]
    wkt = bbox_to_wkt([x0, y0, x1, y1])
    start, end = map(str, s["periode"]["recherche"])
    nis = search_nisar(wkt, start, end, product_types=["GUNW"])
    nis = nis[(nis.direction + nis.track.astype(str)) == PAIRING[args.orbit]]
    nis = nis[nis.bw_code == s["capteurs"]["nisar"]["bw_code"]]
    ndates = sorted(set(pd.to_datetime(nis.ref_date)) | set(pd.to_datetime(nis.sec_date)))
    bursts = asf.search(dataset="SLC-BURST", intersectsWith=wkt, relativeOrbit=args.orbit,
                        start=start, end=end, maxResults=200)
    swaths = sorted({b.properties["burst"]["subswath"] for b in bursts})
    if len(swaths) != 1:
        raise SystemExit(f"orbite {args.orbit} : sous-fauchées {swaths} (une seule attendue)")
    swath = swaths[0].lower()
    s1 = search_s1(wkt, start, end)
    s1 = s1[s1.pathNumber == args.orbit].copy()
    s1["day"] = s1.startTime.dt.tz_convert(None).dt.normalize()
    s1 = s1.drop_duplicates("day")
    rows = []
    for d in ndates:
        gap = (s1.day - d).abs().dt.days
        k = gap.idxmin()
        if gap[k] <= args.max_gap:
            rows.append({**s1.loc[k].to_dict(), "nisar_date": d.date(), "gap_days": int(gap[k])})
    chain = pd.DataFrame(rows).drop_duplicates("day").sort_values("day").reset_index(drop=True)
    chain["swath"] = swath
    (res / "tables").mkdir(parents=True, exist_ok=True)
    chain.drop(columns=["url"]).to_csv(res / "tables" / f"s1_selected_t{args.orbit}.csv", index=False)
    print(f"orbite {args.orbit} ({PAIRING[args.orbit]}), sous-fauchée {swath}, {len(chain)} dates :")
    print(chain[["sceneName", "day", "nisar_date", "gap_days", "platform"]].to_string(index=False),
          flush=True)
    if args.dry_run:
        return
    si, sn = map(int, args.shard.split("/"))
    chain = chain.iloc[si::sn]
    sess = earthdata_session()
    out = data / "sentinel1" / f"t{args.orbit:03d}"
    t0 = time.time()
    for k, (_, r) in enumerate(chain.iterrows(), 1):
        tag = f"[t{args.orbit} lot {si} : {k}/{len(chain)}]"
        for attempt in range(3):
            try:
                extract_safe_subset(r.url, out, swath, pols=("vv",), session=sess, label=tag)
                break
            except Exception as e:
                print(f"{tag} {r.sceneName} : essai {attempt + 1} ÉCHEC {type(e).__name__}: {e}"[:200],
                      flush=True)
                sess = earthdata_session()
        print(f"{tag} {(time.time() - t0) / 60:.1f} min écoulées", flush=True)


if __name__ == "__main__":
    main()
