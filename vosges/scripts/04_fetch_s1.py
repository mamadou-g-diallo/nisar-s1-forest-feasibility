"""Step 4b — Sentinel-1 IW SLC acquisition over the study site (reduced SAFE: one sub-swath).

A chain of acquisitions spaced by ``--step`` days (12 by default, as NISAR) is selected on one
relative orbit. Only the sub-swath covering the site (found with the ASF burst catalogue) is
extracted from each remote SLC zip, with VV and VH: about 1/3 of the full 4.5 GB download.
Logic in ``nisar_s1.search`` and ``nisar_s1.download``.

Outputs: ``<raw>/sentinel1/<track>/<SAFE>`` and ``vosges/results/tables/s1_selected.csv``.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import asf_search as asf
import geopandas as gpd
import pandas as pd

from nisar_s1.config import PROJECT_ROOT, load_params
from nisar_s1.download import earthdata_session, extract_safe_subset
from nisar_s1.search import search_s1


def select_chain(df: pd.DataFrame, start: str, step: int) -> pd.DataFrame:
    """Greedy chain of acquisitions as close as possible to ``start + k * step`` days."""
    df = df.copy()
    df["day"] = df.startTime.dt.tz_convert(None).dt.normalize()
    days = sorted(df.day.unique())
    t, chain = pd.Timestamp(start), []
    while t <= days[-1]:
        near = min(days, key=lambda d: abs((d - t).days))
        if abs((near - t).days) <= 3 and near not in chain:
            chain.append(near)
            t = near + pd.Timedelta(days=step)
        else:
            t += pd.Timedelta(days=1)
    return (df[df.day.isin(chain)].sort_values(["day", "frameCoverage"] if "frameCoverage" in df else "day")
              .drop_duplicates("day").reset_index(drop=True))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default=str(PROJECT_ROOT / "config" / "site.geojson"))
    ap.add_argument("--track", type=int, default=None, help="relative orbit (default: first priority)")
    ap.add_argument("--step", type=int, default=12)
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--shard", default="0/1", help="i/n: process dates i, i+n, ... (parallel streams)")
    args = ap.parse_args()

    p = load_params()
    track = args.track or p["capteurs"]["sentinel1"]["orbites_prioritaires"][0]
    start, end = args.start or str(p["periode"]["debut"]), args.end or str(p["periode"]["fin"])
    site = gpd.read_file(args.site).to_crs("EPSG:4326")
    centre = site.union_all().centroid
    hull = site.union_all().envelope

    bursts = asf.search(dataset="SLC-BURST", intersectsWith=centre.wkt, relativeOrbit=track,
                        start=start, end=end, maxResults=50)
    swaths = sorted({b.properties["burst"]["subswath"] for b in bursts})
    if not swaths:
        raise SystemExit(f"no burst of track {track} over the site")
    swath = swaths[0].lower()
    print(f"track {track}: site in sub-swath(s) {swaths}, using {swath}")

    s1 = search_s1(hull.wkt, start, end)
    s1 = s1[s1.pathNumber == track]
    chain = select_chain(s1, start, args.step)
    chain["swath"] = swath
    out_csv = PROJECT_ROOT / "vosges" / "results" / "tables" / f"s1_selected_t{track}.csv"
    chain.drop(columns=["url"]).to_csv(out_csv, index=False)
    print(chain[["sceneName", "day", "platform"]].to_string(index=False), flush=True)
    if args.dry_run:
        return

    si, sn = map(int, args.shard.split("/"))
    chain = chain.iloc[si::sn]
    sess = earthdata_session()
    out = Path(p["chemins"]["raw"]) / "sentinel1" / f"t{track:03d}"
    t0 = time.time()
    for k, (_, r) in enumerate(chain.iterrows(), 1):
        tag = f"[shard {si}: {k}/{len(chain)}]"
        try:
            extract_safe_subset(r.url, out, swath, session=sess, label=tag)
        except Exception as e:
            print(f"{tag} {r.sceneName}: FAILED {type(e).__name__}: {e}", flush=True)
        print(f"{tag} elapsed {(time.time() - t0) / 60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
