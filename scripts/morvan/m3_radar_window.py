"""Morvan step 3 — choice of the radar processing window inside G23.

The Sentinel-2 guide map covers the whole sylvo-ecoregion (3 000 km2), but Sentinel-1 SLC
processing is done burst by burst (RAM limit: 3 bursts) inside one sub-swath, and NISAR frames
must cover the window entirely. Candidate square windows are scored by the area of reference
clear-cuts they contain. A window is eligible when one ascending and one descending Sentinel-1 orbit
each see it in a single sub-swath with <= 3 bursts, and at least one ascending and one descending
NISAR geometry cover it fully (so that L and C band can be compared at equal geometry in both
directions). Among eligible windows within 15 % of the largest cut area, the one covered by the most
NISAR geometries is kept.

Outputs: ``results/morvan/fenetre_radar.geojson`` and ``results/morvan/tables/radar_window_candidates.csv``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import asf_search as asf
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from nisar_s1.config import load_site
from nisar_s1.search import search_nisar


def s1_bursts(win_ll, orbit: int, start: str, end: str) -> tuple[list[str], int]:
    """Sub-swaths and number of distinct bursts of ``orbit`` intersecting the window."""
    res = asf.search(dataset="SLC-BURST", intersectsWith=win_ll.wkt, relativeOrbit=orbit,
                     start=start, end=end, maxResults=200)
    ids = {(b.properties["burst"]["subswath"], b.properties["burst"]["relativeBurstID"]) for b in res}
    return sorted({i[0] for i in ids}), len(ids)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size-km", type=float, default=20.0)
    ap.add_argument("--step-km", type=float, default=2.0)
    ap.add_argument("--top", type=int, default=12)
    args = ap.parse_args()
    s = load_site("morvan")
    res = Path(s["chemins"]["results"])
    crs = s["site"]["crs"]
    zone = gpd.read_file(res / "zone_g23.geojson").to_crs(crs)
    ref = gpd.read_file(res / "s2_coupes_guide.gpkg", layer="reference")
    x0, y0, x1, y1 = zone.total_bounds
    size, step = args.size_km * 1e3, args.step_km * 1e3
    cand = []
    for x in np.arange(x0, x1 - size, step):
        for y in np.arange(y0, y1 - size, step):
            w = box(x, y, x + size, y + size)
            if zone.geometry.iloc[0].intersection(w).area < 0.8 * w.area:
                continue
            inside = ref[ref.intersects(w)]
            cand.append({"x": x, "y": y, "n_cuts": len(inside), "cut_ha": inside.area_ha.sum(),
                         "geometry": w})
    c = gpd.GeoDataFrame(cand, crs=crs).sort_values("cut_ha", ascending=False)
    # drop near-duplicates (heavily overlapping windows) before the slow catalogue checks
    kept = []
    for _, r in c.iterrows():
        if all(r.geometry.intersection(k.geometry).area < 0.5 * r.geometry.area for k in kept):
            kept.append(r)
        if len(kept) >= args.top:
            break
    start, end = map(str, s["periode"]["recherche"])
    rows = []
    for i, r in enumerate(kept, 1):
        w_ll = gpd.GeoSeries([r.geometry], crs=crs).to_crs(4326).iloc[0]
        row = {"rank": i, "n_cuts": r.n_cuts, "cut_ha": round(r.cut_ha, 1),
               "x": r.x, "y": r.y}
        for orb in s["capteurs"]["sentinel1"]["orbites"]:
            sw, nb = s1_bursts(w_ll, orb, start, end)
            row[f"s1_{orb}"] = f"{'+'.join(sw)}:{nb}"
            row[f"ok_{orb}"] = len(sw) == 1 and 0 < nb <= 3
        nis = search_nisar(w_ll.wkt, start, end, product_types=["GCOV"])
        nis = nis[(nis.bw_code == "2005") & (nis.pol_code == "DHDH")]
        full = nis[nis.aoi_cover >= 0.999]
        geoms = {f"{g['direction']}{g['track']}" for g in s["capteurs"]["nisar"]["geometries"]}
        got = set(full.direction + full.track.astype(str))
        row["nisar_full"] = "+".join(sorted(got & geoms))
        # at least one ascending and one descending NISAR geometry fully covering the window
        row["nisar_ok"] = any(g.startswith("A") for g in got & geoms) and any(
            g.startswith("D") for g in got & geoms)
        row["nisar_n"] = len(got & geoms)
        rows.append(row)
        print(f"[{i}/{len(kept)}] {r.n_cuts} coupes, {r.cut_ha:.0f} ha | "
              + " ".join(f"S1-{o} {row[f's1_{o}']}" for o in s["capteurs"]["sentinel1"]["orbites"])
              + f" | NISAR complet : {row['nisar_full']}", flush=True)
    t = pd.DataFrame(rows)
    (res / "tables").mkdir(parents=True, exist_ok=True)
    t.to_csv(res / "tables" / "radar_window_candidates.csv", index=False)
    asc = [o for o in s["capteurs"]["sentinel1"]["orbites"] if o in (59, 161)]
    desc = [o for o in s["capteurs"]["sentinel1"]["orbites"] if o in (37, 110)]
    best = None
    # prefer windows covered by more NISAR geometries when the cut area is within 15 % of the best
    ok_rows = t[t.nisar_ok]
    if len(ok_rows):
        lim = 0.85 * ok_rows.cut_ha.max()
        t = pd.concat([t[t.nisar_ok & (t.cut_ha >= lim)].sort_values(["nisar_n", "cut_ha"], ascending=False),
                       t[~(t.nisar_ok & (t.cut_ha >= lim))]])
    for _, row in t.iterrows():
        a = [o for o in asc if row[f"ok_{o}"]]
        d = [o for o in desc if row[f"ok_{o}"]]
        if row.nisar_ok and a and d:
            best = (row, a[0], d[0])
            break
    if best is None:
        raise SystemExit("aucune fenêtre ne satisfait toutes les contraintes")
    row, a, d = best
    w = box(row.x, row.y, row.x + size, row.y + size)
    out = gpd.GeoDataFrame([{"nom": "fenetre_radar", "s1_montante": int(a), "s1_descendante": int(d),
                             "nisar": row.nisar_full,
                             "n_coupes_ref": int(row.n_cuts), "surface_coupes_ha": float(row.cut_ha)}],
                           geometry=[w], crs=crs)
    out.to_file(res / "fenetre_radar.geojson", driver="GeoJSON")
    print(f"Fenêtre retenue : rang {int(row['rank'])}, {int(row.n_cuts)} coupes de référence, "
          f"{row.cut_ha:.0f} ha ; Sentinel-1 A{a} et D{d}")


if __name__ == "__main__":
    main()
