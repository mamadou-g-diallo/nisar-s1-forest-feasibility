"""Step 3d — Visual check of clear-cut candidates: true-colour chips before / during / after the
cut window and a SWIR-NIR-red false-colour chip (bare soil and slash appear pink/orange, while
bark-beetle dieback appears as a gradual red-brown browning of standing crowns).

Output: ``results/figures/candidates_rgb_quicklooks.png``.
"""

from __future__ import annotations

import argparse

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from nisar_s1.config import PROJECT_ROOT, load_params  # noqa: E402
from nisar_s1.optical import rgb_chip, search_s2  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="+", default=["C05", "C13", "C08", "C11", "C15", "C16", "C07",
                                                 "C10", "C09", "C06", "C14"])
    ap.add_argument("--dates", nargs=3, default=["2026-07-04", "2026-08-13", "2026-10-05"])
    ap.add_argument("--tile", default="32ULU")
    ap.add_argument("--half", type=float, default=600.0, help="chip half-size (m)")
    args = ap.parse_args()

    p = load_params()
    c = gpd.read_file(PROJECT_ROOT / "results" / "site_candidates.geojson")
    s2 = search_s2(p["aoi_recherche"]["bbox_wgs84"], min(args.dates), max(args.dates), 30,
                   tiles=[args.tile]).drop_duplicates(["tile", "date"])
    items = {d: s2[s2.date.astype(str) == d]["item"].iloc[0] for d in args.dates}
    h, res = args.half, 10.0
    fig, axs = plt.subplots(len(args.ids), 4, figsize=(12, 3 * len(args.ids)), squeeze=False)
    for i, cid in enumerate(args.ids):
        g = c[c.cand_id == cid].to_crs(32632).geometry.iloc[0]
        ctr = (g.centroid.x, g.centroid.y)
        chips = [(rgb_chip(items[d], ctr, h, res), f"{cid} {d}") for d in args.dates]
        chips.append((rgb_chip(items[args.dates[-1]], ctr, h, res, swir=True), f"{cid} SWIR {args.dates[-1]}"))
        x, y = g.exterior.xy
        px = [(xx - ctr[0] + h) / res for xx in x]
        py = [(h - (yy - ctr[1])) / res for yy in y]
        for ax, (im, ttl) in zip(axs[i], chips):
            ax.imshow(im)
            ax.plot(px, py, "y-", lw=0.8)
            ax.set_title(ttl, fontsize=8)
            ax.axis("off")
        print(f"[{i + 1}/{len(args.ids)}] {cid}", flush=True)
    fig.tight_layout()
    fig.savefig(PROJECT_ROOT / "results" / "figures" / "candidates_rgb_quicklooks.png", dpi=80)


if __name__ == "__main__":
    main()
