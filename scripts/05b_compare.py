"""Step 5b — NISAR (L-band) vs Sentinel-1 (C-band): separability of the clear-cut from intact forest.

Every layer is put on the same 20 m UTM 32N grid (site window). Then:

1. per-date statistics (clear-cut vs control forest) for each sensor / geometry / variable;
2. change features per pixel, with the cut dates taken from the Sentinel-2 series:
   - backscatter: d_gamma0 = mean dB after the cut - mean dB before (temporal means in linear power);
   - coherence: d_coh = mean coherence of pairs after the cut - mean of pairs before;
     and coh_span = coherence of the pairs overlapping the cut window - mean coherence before;
3. separability of each feature (Cohen's d, AUC with block-bootstrap 95 % interval, Jeffries-Matusita)
   and pixel-wise detection over the window against the Sentinel-2 reference (dNDVI <= -0.3 in forest).

Logic in ``nisar_s1.io_nisar``, ``nisar_s1.grid``, ``nisar_s1.stats``, ``nisar_s1.plots``.
Outputs: ``results/tables/comparison_*.csv``, ``results/figures/comparison_*.png``.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from nisar_s1 import plots
from nisar_s1.config import PROJECT_ROOT, load_params
from nisar_s1.grid import make_grid, polygon_mask, read_geotiff, to_grid
from nisar_s1.io_nisar import info_from_name
from nisar_s1.optical import Raster, forest_mask_like, load_raster, save_raster
from nisar_s1.snap import dimap_band
from nisar_s1.detect import detection_scores
from nisar_s1.stats import block_bootstrap_auc, separability

PRE = ["2026-06-24", "2026-06-25", "2026-07-04", "2026-07-10"]
POST = ["2026-09-23", "2026-09-25", "2026-10-05", "2026-10-12"]
TAB, FIG = PROJECT_ROOT / "results" / "tables", PROJECT_ROOT / "results" / "figures"


def db(lin: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10 * np.log10(np.where(lin > 0, lin, np.nan))


def _snap(path, pattern: str) -> Raster:
    """SNAP band (ENVI) with 0 treated as no data (SNAP writes 0 outside the valid swath)."""
    r = read_geotiff(dimap_band(path, pattern))
    r.data[r.data == 0] = np.nan
    return r


def collect_layers(p: dict, grid: Raster) -> list[dict]:
    """All NISAR and Sentinel-1 layers resampled on ``grid`` (backscatter kept in linear power)."""
    layers = []
    nroot = Path(p["chemins"]["processed"]) / "nisar"
    for f in sorted(nroot.glob("*/*/*.tif")):
        gran, layer = f.stem.split("__")
        info = info_from_name(gran)
        geom = f.parent.parent.name
        if info.product == "GCOV" and layer in ("HHHH", "HVHV"):
            r = to_grid(load_raster(f), grid, "average")
            layers.append(dict(sensor="NISAR-L", geom=geom, kind="g0", pol=layer[:2],
                               d1=pd.Timestamp(info.ref_date), d2=None, data=r.data))
        elif info.product == "GUNW" and layer in ("coh20", "coh80"):
            r = to_grid(load_raster(f), grid, "average" if layer == "coh20" else "bilinear")
            layers.append(dict(sensor="NISAR-L", geom=geom, kind="coh" if layer == "coh20" else "coh80",
                               pol="HH", d1=pd.Timestamp(info.ref_date), d2=pd.Timestamp(info.sec_date),
                               data=r.data))
    sroot = Path(p["chemins"]["processed"]) / "sentinel1"
    for f in sorted(sroot.glob("t*/g0_*.dim")):
        d = pd.Timestamp(re.search(r"g0_(\d{4}-\d{2}-\d{2})", f.name).group(1))
        for pol in ("VV", "VH"):
            r = to_grid(_snap(f, f"Gamma0*_{pol}"), grid, "bilinear")
            layers.append(dict(sensor="S1-C", geom=f.parent.name.upper(), kind="g0", pol=pol, d1=d, d2=None,
                               data=r.data))
    for f in sorted(sroot.glob("t*/coh_*.dim")):
        a, b = re.findall(r"\d{4}-\d{2}-\d{2}", f.name)[:2]
        for pol in ("VV", "VH"):
            r = to_grid(_snap(f, f"coh*_{pol}"), grid, "bilinear")
            layers.append(dict(sensor="S1-C", geom=f.parent.name.upper(), kind="coh", pol=pol,
                               d1=pd.Timestamp(a), d2=pd.Timestamp(b), data=r.data))
    return layers


def phase(l: dict, cut_after: pd.Timestamp, cut_before: pd.Timestamp) -> str:
    """pre / post / span / during, relative to the cut interval [cut_after, cut_before]."""
    if l["d2"] is None:
        return "pre" if l["d1"] <= cut_after else "post" if l["d1"] >= cut_before else "during"
    if l["d2"] <= cut_after:
        return "pre"
    if l["d1"] >= cut_before:
        return "post"
    if l["d1"] <= cut_after and l["d2"] >= cut_before:
        return "span"
    return "during"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--margin", type=float, default=1500.0)
    ap.add_argument("--erode", type=float, default=0.0,
                    help="polygon erosion (m); 0 = all pixels of the S2-derived polygons (aligned grid)")
    ap.add_argument("--tag", default="", help="suffix of output tables/figures (sensitivity runs)")
    ap.add_argument("--bootstrap", type=int, default=300)
    args = ap.parse_args()

    p = load_params()
    crs, res = p["projet"]["crs_travail"], p["comparaison"]["grille_m"]
    erode = args.erode
    site = gpd.read_file(PROJECT_ROOT / "config" / "site.geojson").to_crs(crs)
    cut_after, cut_before = pd.Timestamp(site.cut_after.iloc[0]), pd.Timestamp(site.cut_before.iloc[0])
    xmin, ymin, xmax, ymax = site.total_bounds
    m = args.margin
    grid = make_grid((xmin - m, ymin - m, xmax + m, ymax + m), res, crs)
    cut_m = polygon_mask(site[site.role == "cut"].geometry, grid, erode_m=erode)
    ctl_m = polygon_mask(site[site.role == "control"].geometry, grid, erode_m=erode)
    print(f"grid {grid.data.shape}, cut {cut_m.sum()} px, control {ctl_m.sum()} px (erosion {erode} m); "
          f"cut between {cut_after.date()} and {cut_before.date()}", flush=True)

    # --- Sentinel-2 reference on the grid ------------------------------------------------
    tile = site.tile.iloc[0]
    cache = Path(p["chemins"]["processed"]) / "sentinel2" / "composites"
    pre = to_grid(load_raster(cache / f"ndvi_pre_{tile}_20m_{'_'.join(PRE)}.tif"), grid)
    post = to_grid(load_raster(cache / f"ndvi_post_{tile}_20m_{'_'.join(POST)}.tif"), grid)
    forest = forest_mask_like(grid, p["aoi_recherche"]["bbox_wgs84"])
    dndvi = post.data - pre.data
    truth = (dndvi <= p["comparaison"].get("seuil_coupe_dndvi", -0.3)) & (pre.data >= 0.7)
    # evaluation pixels: forest before; ambiguous partial changes (-0.3 < dNDVI < -0.1) excluded
    valid = forest & (pre.data >= 0.7) & np.isfinite(dndvi) & ~((dndvi > -0.3) & (dndvi < -0.1))
    print(f"reference: {truth[valid].sum()} cut px / {valid.sum()} evaluated forest px "
          f"({100 * truth[valid].mean():.1f} %)", flush=True)
    proc = Path(p["chemins"]["processed"]) / "comparaison"
    save_raster(Raster(np.where(valid, truth, np.nan).astype("float32"), grid.transform, grid.crs),
                proc / "reference_cut_mask.tif")

    # --- 1. per-date statistics ------------------------------------------------------------
    layers = collect_layers(p, grid)
    print(f"{len(layers)} layers on the grid", flush=True)
    rows = []
    for l in layers:
        v = db(l["data"]) if l["kind"] == "g0" else l["data"]
        s = separability(v[cut_m], v[ctl_m])
        rows.append({"sensor": l["sensor"], "geom": l["geom"], "kind": l["kind"], "pol": l["pol"],
                     "date": l["d1"].date(), "date2": None if l["d2"] is None else l["d2"].date(),
                     "baseline_d": None if l["d2"] is None else (l["d2"] - l["d1"]).days,
                     "phase": phase(l, cut_after, cut_before),
                     "valid_cut": float(np.isfinite(v[cut_m]).mean()), **s})
    ts = pd.DataFrame(rows).sort_values(["sensor", "geom", "kind", "pol", "date"])
    ts.to_csv(TAB / f"comparison_timeseries{args.tag}.csv", index=False)

    # --- 2-3. change features, separability, detection --------------------------------------
    feats, out = {}, []
    groups = {}
    for l in layers:
        groups.setdefault((l["sensor"], l["geom"], l["kind"], l["pol"]), []).append(l)
    for (sensor, geom, kind, pol), ls in groups.items():
        ph = {k: [l for l in ls if phase(l, cut_after, cut_before) == k] for k in ("pre", "post", "span", "during")}
        ph["span"] = ph["span"] + ph["during"]  # pairs overlapping the cut window (12-day pairs < 15-day window)
        if kind in ("coh", "coh80"):
            # before / after: 12-day pairs only; change pairs: <= 25 days (for NISAR the pair over the
            # cut is a 24-day pair, an acquisition is missing at the end of July)
            ph = {k: [l for l in v if (l["d2"] - l["d1"]).days <= (25 if k == "span" else 13)]
                  for k, v in ph.items()}
        if not ph["pre"] or not ph["post"]:
            print(f"skip {sensor} {geom} {kind} {pol}: pre {len(ph['pre'])}, post {len(ph['post'])}")
            continue
        mean = lambda L: np.nanmean(np.stack([l["data"] for l in L]), axis=0)  # noqa: E731
        name = f"{sensor} {geom} {pol}"
        if kind == "g0":
            f = {f"d_gamma0_{pol}": (db(mean(ph["post"])) - db(mean(ph["pre"])), -1),
                 f"gamma0_post_{pol}": (db(mean(ph["post"])), -1)}
        else:
            k = "coh" if kind == "coh" else "coh80"
            f = {f"d_{k}_{pol}": (mean(ph["post"]) - mean(ph["pre"]), +1),
                 f"{k}_post_{pol}": (mean(ph["post"]), +1)}
            if ph["span"]:
                f[f"{k}_change_{pol}"] = (mean(ph["span"]), -1)  # coherence of the pair(s) over the cut
                f[f"{k}_drop_{pol}"] = (mean(ph["span"]) - mean(ph["pre"]), -1)
        for var, (img, _) in f.items():
            s = separability(img[cut_m], img[ctl_m])
            if "auc" not in s:
                continue
            direction = 1 if s["auc"] >= 0.5 else -1  # direction learned on the site polygons
            # blocks larger than the effective resolution: 60 m for 20 m layers, 100 m for 80 m layers
            # (at 80 m the 2.4 ha cut holds only ~4 independent pixels: indicative only)
            coarse = "coh80" in var
            lo, hi = block_bootstrap_auc(img, cut_m, ctl_m, block=5 if coarse else 3, n=args.bootstrap)
            det = detection_scores(img, truth, valid, direction)
            feats[f"{name} {var}"] = img
            out.append({"sensor": sensor, "geom": geom, "pol": pol, "variable": var, "res_m": 80 if coarse else 20,
                        "label": f"{sensor} {geom} {var}", "n_pre": len(ph["pre"]), "n_post": len(ph["post"]),
                        "n_span": len(ph.get("span", [])), **s, "ci_lo": lo, "ci_hi": hi, **det})
            save_raster(Raster(img.astype("float32"), grid.transform, grid.crs),
                        proc / f"{sensor}_{geom}_{var}.tif".replace(" ", "_"))
    res_df = pd.DataFrame(out).sort_values("auc_sep", ascending=False)
    res_df.to_csv(TAB / f"comparison_change{args.tag}.csv", index=False)
    pd.set_option("display.width", 220)
    cols = ["label", "n_pre", "n_post", "delta", "cohen_d", "auc_sep", "ci_lo", "ci_hi", "jm",
            "auc_window", "f1_otsu", "f1_best"]
    print(res_df[[c for c in cols if c in res_df]].round(3).to_string(index=False))

    # --- figures ------------------------------------------------------------------------------
    plots.separability_bars(res_df, FIG / f"comparison_auc{args.tag}.png", "auc_sep",
                            "Clear-cut vs intact forest: separability of change features (AUC, 95 % CI)")
    for (sensor, geom), g in ts[ts.kind.isin(["g0", "coh"])].groupby(["sensor", "geom"]):
        g = g.copy()
        g["variable"] = g.kind.map({"g0": "gamma0 (dB)", "coh": "coherence"}) + " " + g.pol + \
            np.where(g.baseline_d.fillna(0) > 13, " (24 d)", "")
        g = g[~g.variable.str.endswith("(24 d)")]
        mid = pd.to_datetime(g.date) + (pd.to_datetime(g.date2) - pd.to_datetime(g.date)) / 2
        g["date"] = np.where(g.kind == "coh", mid, pd.to_datetime(g.date))  # pairs at their mid-date
        plots.sensor_timeseries(g, FIG / f"comparison_ts_{sensor}_{geom}{args.tag}.png", (cut_after, cut_before))


if __name__ == "__main__":
    main()
