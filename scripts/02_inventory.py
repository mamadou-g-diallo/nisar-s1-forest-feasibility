"""Step 2 — Inventory of Sentinel-1 and NISAR products over the search AOI.

Orchestration only: all logic is in ``nisar_s1.search``.
Outputs (small, versioned): ``results/tables/inventory_*.csv``.
"""

from __future__ import annotations

import pandas as pd

from nisar_s1.config import PROJECT_ROOT, load_params, search_aoi_wkt
from nisar_s1.search import (NISAR_PRODUCT_TYPES, revisit_summary, search_nisar,
                             search_s1)

OUT = PROJECT_ROOT / "results" / "tables"


def main() -> None:
    params = load_params()
    aoi = search_aoi_wkt(params)
    start, end = str(params["periode"]["debut"]), str(params["periode"]["fin"])
    OUT.mkdir(parents=True, exist_ok=True)

    # --- Sentinel-1 IW SLC -------------------------------------------------
    s1 = search_s1(aoi, start, end)
    s1.drop(columns=["url"]).to_csv(OUT / "inventory_s1_slc.csv", index=False)
    s1_rev = revisit_summary(s1, ["flightDirection", "pathNumber"])
    s1_rev["platforms"] = s1_rev.apply(
        lambda r: "+".join(sorted(s1.loc[(s1.flightDirection == r.flightDirection)
                                         & (s1.pathNumber == r.pathNumber), "platform"].unique())),
        axis=1)
    s1_rev.to_csv(OUT / "inventory_s1_revisit.csv", index=False)

    # --- NISAR: all product types (counts), then GCOV / GUNW in detail -----
    nis = search_nisar(aoi, start, end, product_types=NISAR_PRODUCT_TYPES)
    nis.drop(columns=["url"]).to_csv(OUT / "inventory_nisar_all.csv", index=False)
    counts = (nis.groupby(["product", "bw_code", "pol_code"])
                 .agg(n=("sceneName", "size"), size_mb_median=("size_mb", "median"),
                      first=("startTime", "min"), last=("startTime", "max"))
                 .reset_index())
    counts.to_csv(OUT / "inventory_nisar_counts.csv", index=False)

    gcov = nis[nis["product"] == "GCOV"]
    revisit_summary(gcov, ["direction", "track", "frame"]).to_csv(
        OUT / "inventory_nisar_gcov_revisit.csv", index=False)

    gunw = nis[nis["product"] == "GUNW"]
    if len(gunw):
        pairs = (gunw.groupby(["direction", "track", "frame", "baseline_days"])
                     .agg(n_pairs=("sceneName", "size"),
                          first_ref=("ref_date", "min"), last_sec=("sec_date", "max"),
                          aoi_cover=("aoi_cover", "max"))
                     .reset_index())
        pairs.to_csv(OUT / "inventory_nisar_gunw_pairs.csv", index=False)

    # --- Console summary ----------------------------------------------------
    pd.set_option("display.width", 200)
    print(f"AOI: {aoi}\nPeriod: {start} -> {end}\n")
    print(f"Sentinel-1 IW SLC: {len(s1)} scenes")
    print(s1_rev.to_string(index=False), "\n")
    print(f"NISAR: {len(nis)} products")
    print(counts.to_string(index=False), "\n")
    if len(gunw):
        print(pairs.to_string(index=False))


if __name__ == "__main__":
    main()
