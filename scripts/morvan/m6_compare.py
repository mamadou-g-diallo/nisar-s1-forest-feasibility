"""Morvan step 6 — NISAR (L band) vs Sentinel-1 (C band) on many clear-cuts, and transposition of the
IRSTEA guide method to radar change images.

Reference (Sentinel-2, step 2): objects of the guide map with certainty degree >= 2 inside the radar
window ("cut" class). Intact forest: BD Forêt forest with dNDVI inside m +/- sigma, at more than 40 m
from any detection (degree >= 1). Pixels of degree-1 objects and of the 40 m buffer are excluded
from both classes (uncertain).

Radar change variables per sensor / geometry (all on the 20 m Lambert 93 grid):
  * d_g0_<pol>   : mean gamma0 "after" - mean gamma0 "before" (dB; means in linear power);
  * g0_post_<pol>: mean gamma0 "after" (dB);
  * coh_min      : minimum coherence over the pairs between the two windows (the pair spanning a cut
                   is among them, whatever the cut date);
  * coh_drop     : mean coherence of the "before" pairs - coh_min;
  * coh_post     : mean coherence of the "after" pairs.
Pre-cut sanity check: the same separability computed on a "before only" change (two pre dates / first
pre pair) must be close to AUC 0.5.

Evaluation:
  1. separability cut vs intact forest (AUC, Cohen's d, JM), 95 % interval by a cluster bootstrap that
     resamples whole cut objects and 5 x 5 pixel blocks of forest;
  2. guide transposition: certainty degrees m - k.sigma on each radar variable inside the forest,
     1 ha sieve, then the guide's confusion matrix by area against the Sentinel-2 reference, and the
     share of reference cuts found (>= 25 % of their pixels detected);
  3. by forest group (feuillus / résineux), and persistence (per-date AUC up to November).

Outputs: ``results/morvan/tables/m6_*.csv`` and ``results/morvan/figures/m6_*.png``.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import ndimage  # noqa: E402

from nisar_s1.config import load_site  # noqa: E402
from nisar_s1.grid import make_grid, polygon_mask, read_geotiff, to_grid  # noqa: E402
from nisar_s1.guide_cr import (certainty_degrees, confusion_area, object_hits,  # noqa: E402
                               sieve_degrees)
from nisar_s1.io_nisar import info_from_name  # noqa: E402
from nisar_s1.optical import Raster, load_raster  # noqa: E402
from nisar_s1.snap import dimap_band  # noqa: E402
from nisar_s1.stats import auc, separability  # noqa: E402

# direction of the change for a clear-cut: -1 = values decrease, +1 = values increase
DIRECTION = {"d_g0": -1, "g0_post": -1, "coh_min": -1, "coh_drop": +1, "coh_post": +1}
GROUPS = {1: "feuillus", 2: "resineux", 3: "mixte"}


def db(lin):
    with np.errstate(divide="ignore", invalid="ignore"):
        return 10 * np.log10(np.where(lin > 0, lin, np.nan))


def mean_lin(arrs):
    with np.errstate(all="ignore"):
        return np.nanmean(np.stack(arrs), axis=0) if arrs else None


def _snap(path, pattern: str) -> Raster:
    r = read_geotiff(dimap_band(path, pattern))
    r.data[r.data == 0] = np.nan
    return r


def nisar_layers(root: Path, grid: Raster) -> dict[str, list[dict]]:
    """Per geometry: list of layers (kind g0/coh, pol, d1, d2, data), latest processing only."""
    latest = {}
    for f in sorted(root.glob("*/*/*.tif")):
        gran, layer = f.stem.split("__")
        i = info_from_name(gran)
        latest[(f.parent.parent.name, i.product, i.ref_date, i.sec_date, layer)] = f
    out: dict[str, list[dict]] = {}
    for (geom, prod, d1, d2, layer), f in latest.items():
        if prod == "GCOV" and layer in ("HHHH", "HVHV"):
            item = dict(kind="g0", pol=layer[:2], d1=pd.Timestamp(d1), d2=None)
            item["data"] = to_grid(load_raster(f), grid, "average").data
        elif prod == "GUNW" and layer == "coh20":
            item = dict(kind="coh", pol="HH", d1=pd.Timestamp(d1), d2=pd.Timestamp(d2))
            item["data"] = to_grid(load_raster(f), grid, "average").data
        else:
            continue
        out.setdefault(f"NISAR {geom}", []).append(item)
    return out


def s1_layers(root: Path, grid: Raster) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for f in sorted(root.glob("t*/g0_*.dim")):
        d = pd.Timestamp(re.search(r"g0_(\d{4}-\d{2}-\d{2})", f.name).group(1))
        for pol in ("VV", "VH"):
            out.setdefault(f"S1 {f.parent.name.upper()}", []).append(
                dict(kind="g0", pol=pol, d1=d, d2=None,
                     data=to_grid(_snap(f, f"Gamma0*_{pol}"), grid, "bilinear").data))
    for f in sorted(root.glob("t*/coh_*.dim")):
        a, b = re.findall(r"\d{4}-\d{2}-\d{2}", f.name)[:2]
        for pol in ("VV", "VH"):
            out.setdefault(f"S1 {f.parent.name.upper()}", []).append(
                dict(kind="coh", pol=pol, d1=pd.Timestamp(a), d2=pd.Timestamp(b),
                     data=to_grid(_snap(f, f"coh*_{pol}"), grid, "bilinear").data))
    return out


def features(layers: list[dict], per: dict) -> tuple[dict[str, np.ndarray], dict]:
    """Change variables of one geometry, plus the pre-cut sanity variables and the date bookkeeping."""
    a0, a1 = map(pd.Timestamp, per["radar_avant"])
    p0, p1 = map(pd.Timestamp, per["radar_apres"])
    feats, info = {}, {}
    for pol in sorted({l["pol"] for l in layers if l["kind"] == "g0"}):
        g = [l for l in layers if l["kind"] == "g0" and l["pol"] == pol]
        pre = sorted([l for l in g if a0 <= l["d1"] <= a1], key=lambda l: l["d1"])
        post = [l for l in g if p0 <= l["d1"] <= p1]
        info[f"g0_{pol}"] = f"{len(pre)} avant / {len(post)} après"
        if pre and post:
            mpre, mpost = mean_lin([l["data"] for l in pre]), mean_lin([l["data"] for l in post])
            feats[f"d_g0_{pol}"] = db(mpost) - db(mpre)
            feats[f"g0_post_{pol}"] = db(mpost)
        if len(pre) >= 2:                                       # sanity: change between two pre dates
            feats[f"precheck_d_g0_{pol}"] = db(pre[-1]["data"]) - db(pre[0]["data"])
    for pol in sorted({l["pol"] for l in layers if l["kind"] == "coh"}):
        c = [l for l in layers if l["kind"] == "coh" and l["pol"] == pol]
        pre = [l for l in c if l["d1"] >= a0 and l["d2"] <= a1]
        mid = [l for l in c if l["d2"] > a1 and l["d1"] < p0]   # pairs between the windows
        post = [l for l in c if l["d1"] >= p0 and l["d2"] <= p1 + pd.Timedelta(days=13)]
        info[f"coh_{pol}"] = f"{len(pre)} avant / {len(mid)} entre / {len(post)} après"
        if mid:
            with np.errstate(all="ignore"):
                cmin = np.nanmin(np.stack([l["data"] for l in mid]), axis=0)
            feats[f"coh_min_{pol}"] = cmin
            if pre:
                feats[f"coh_drop_{pol}"] = mean_lin([l["data"] for l in pre]) - cmin
                feats[f"precheck_coh_{pol}"] = pre[0]["data"]
        if post:
            feats[f"coh_post_{pol}"] = mean_lin([l["data"] for l in post])
    return feats, info


def cluster_bootstrap_auc(x, cut_lab, forest, n=300, block=5, seed=0):
    """95 % interval of the separation AUC: resample cut objects and forest blocks with replacement."""
    rng = np.random.default_rng(seed)
    ok = np.isfinite(x)
    lab = cut_lab[ok & (cut_lab > 0)]
    vc = x[ok & (cut_lab > 0)]
    order = np.argsort(lab)
    lab, vc = lab[order], vc[order]
    _, st = np.unique(lab, return_index=True)
    gc = np.split(vc, st[1:])
    bi = (np.arange(x.shape[0])[:, None] // block) * 10**6 + np.arange(x.shape[1])[None, :] // block
    m = ok & forest
    ids, vf = bi[m], x[m]
    order = np.argsort(ids)
    ids, vf = ids[order], vf[order]
    _, st = np.unique(ids, return_index=True)
    gf = np.split(vf, st[1:])
    if len(gc) < 3 or len(gf) < 3:
        return (np.nan, np.nan)
    sub = min(len(gf), 3000)          # forest blocks subsampled for speed
    res = []
    for _ in range(n):
        a = np.concatenate([gc[i] for i in rng.integers(0, len(gc), len(gc))])
        b = np.concatenate([gf[i] for i in rng.integers(0, len(gf), sub)])
        u = auc(a, b)
        res.append(max(u, 1 - u))
    return tuple(np.percentile(res, [2.5, 97.5]).round(3))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bootstrap", type=int, default=200)
    ap.add_argument("--erode", type=float, default=0.0, help="erosion of reference objects (m)")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    s = load_site("morvan")
    res, data = Path(s["chemins"]["results"]), Path(s["chemins"]["data_root"])
    tab, fig = res / "tables", res / "figures"
    tab.mkdir(parents=True, exist_ok=True)
    fig.mkdir(parents=True, exist_ok=True)
    win = gpd.read_file(res / "fenetre_radar.geojson").to_crs(s["site"]["crs"])
    grid = make_grid(tuple(win.total_bounds), s["site"]["grille_m"], s["site"]["crs"])
    px_ha = grid.pixel_area_m2 / 1e4

    # --- reference on the window grid ------------------------------------------------------------
    deg = np.nan_to_num(to_grid(load_raster(data / "s2" / "degres_s2_l93.tif"), grid, "nearest").data).astype(int)
    dndvi = to_grid(load_raster(data / "s2" / "dndvi_l93.tif"), grid, "nearest").data
    group = np.nan_to_num(to_grid(load_raster(data / "s2" / "forest_group_l93.tif"), grid, "nearest").data).astype(int)
    thr = pd.read_csv(tab / "s2_guide_thresholds.csv").iloc[0]
    cuts = gpd.read_file(res / "s2_coupes_guide.gpkg")
    cuts = cuts[cuts.intersects(win.geometry.iloc[0])]
    ref_objs = cuts[cuts.degre_max >= s["guide"]["degre_reference_min"]].reset_index(drop=True)
    forest = (group > 0) & np.isfinite(dndvi)
    cut_lab = np.zeros(grid.data.shape, "int32")
    for i, g in enumerate(ref_objs.geometry, 1):
        m = polygon_mask([g], grid, erode_m=args.erode)
        cut_lab[m & forest] = i
    ref = cut_lab > 0
    any_det = polygon_mask(list(cuts.geometry), grid) if len(cuts) else np.zeros_like(ref)
    buf = ndimage.binary_dilation(any_det | (deg > 0), iterations=2)          # 40 m
    uncertain = buf & ~ref
    intact = forest & ~buf & (np.abs(dndvi - thr.m) <= thr.sigma)
    evalmask = forest & ~uncertain
    print(f"Fenêtre {grid.data.shape[1]} x {grid.data.shape[0]} px : {len(ref_objs)} coupes de référence "
          f"({ref.sum() * px_ha:.0f} ha), forêt intacte {intact.sum() * px_ha:.0f} ha, "
          f"incertain exclu {uncertain.sum() * px_ha:.0f} ha", flush=True)
    ref_objs.assign(n_px=[(cut_lab == i).sum() for i in range(1, len(ref_objs) + 1)]).drop(
        columns="geometry").to_csv(tab / f"m6_reference_objects{args.tag}.csv", index=False)

    # --- radar layers -----------------------------------------------------------------------------
    geoms = {}
    geoms.update(nisar_layers(data / "nisar", grid))
    geoms.update(s1_layers(data / "processed" / "sentinel1", grid))
    print("Géométries :", ", ".join(f"{k} ({len(v)} couches)" for k, v in geoms.items()), flush=True)

    sep_rows, guide_rows, grp_rows, pers_rows, info_rows = [], [], [], [], []
    keep_maps = {}
    for gi, (gname, layers) in enumerate(sorted(geoms.items()), 1):
        sensor = "NISAR-L" if gname.startswith("NISAR") else "S1-C"
        feats, info = features(layers, s["periode"])
        info_rows.append({"geometrie": gname, **info})
        for var, x in feats.items():
            base = re.sub(r"_(HH|HV|VV|VH)$", "", var)
            sp = separability(x[ref], x[intact])
            if not sp or "auc" not in sp:
                continue
            ci = cluster_bootstrap_auc(x, cut_lab, intact, n=args.bootstrap) if not var.startswith("precheck") else (np.nan, np.nan)
            sep_rows.append({"sensor": sensor, "geom": gname, "variable": var, **sp,
                             "auc_lo": ci[0], "auc_hi": ci[1]})
            if var.startswith("precheck"):
                continue
            # guide transposition
            dirn = DIRECTION[base]
            valid = forest & np.isfinite(x)
            degs = certainty_degrees(x, valid, direction=dirn, k=tuple(s["guide"]["k_sigma"]))
            degs = sieve_degrees(degs, int(round(s["guide"]["surface_min_ha"] / px_ha)))
            for kmin in (1, 2, 3):
                pred = degs >= kmin
                c = confusion_area(pred, ref, evalmask & valid, grid.pixel_area_m2)
                hits = object_hits(pred, cut_lab)
                guide_rows.append({"sensor": sensor, "geom": gname, "variable": var, "degre_min": kmin,
                                   **c, "objets_trouves_pct": 100 * float((hits >= 0.25).mean()) if len(hits) else np.nan,
                                   "objets_n": len(hits)})
            keep_maps[(gname, var)] = (x, degs)
            for gc, gl in GROUPS.items():
                mref, mint = ref & (group == gc), intact & (group == gc)
                if mref.sum() >= 25 and mint.sum() >= 25:
                    u = auc(x[mref], x[mint])
                    grp_rows.append({"sensor": sensor, "geom": gname, "variable": var, "groupe": gl,
                                     "n_coupe_px": int(mref.sum()), "auc_sep": max(u, 1 - u)})
        # persistence: per-date AUC of gamma0 after the cut window
        for l in layers:
            if l["kind"] == "g0" and l["d1"] >= pd.Timestamp(s["periode"]["radar_avant"][0]):
                u = auc(l["data"][ref], l["data"][intact])
                pers_rows.append({"sensor": sensor, "geom": gname, "pol": l["pol"], "date": l["d1"],
                                  "auc_sep": max(u, 1 - u)})
        print(f"[{gi}/{len(geoms)}] {gname} : {len(feats)} variables ({'; '.join(f'{k} {v}' for k, v in info.items())})", flush=True)
        del layers

    sep = pd.DataFrame(sep_rows)
    sep.to_csv(tab / f"m6_separability{args.tag}.csv", index=False)
    gd = pd.DataFrame(guide_rows)
    gd.to_csv(tab / f"m6_guide_confusion{args.tag}.csv", index=False)
    pd.DataFrame(grp_rows).to_csv(tab / f"m6_by_group{args.tag}.csv", index=False)
    pd.DataFrame(pers_rows).to_csv(tab / f"m6_persistence{args.tag}.csv", index=False)
    pd.DataFrame(info_rows).to_csv(tab / f"m6_dates{args.tag}.csv", index=False)

    best = (sep[~sep.variable.str.startswith("precheck")].sort_values("auc_sep", ascending=False)
            .groupby("geom").head(3))
    print("\nMeilleures variables par géométrie :")
    print(best[["geom", "variable", "mean_a", "mean_b", "auc_sep", "auc_lo", "auc_hi"]].round(3).to_string(index=False))
    print("\nContrôle avant coupe (AUC attendue ~0,5) :")
    print(sep[sep.variable.str.startswith("precheck")][["geom", "variable", "auc_sep"]].round(3).to_string(index=False))
    gbest = gd.sort_values("f1", ascending=False).groupby("geom").head(1)
    print("\nMéthode du guide, meilleure variable par géométrie (F1) :")
    print(gbest[["geom", "variable", "degre_min", "omission_pct", "commission_pct", "kappa", "f1",
                 "objets_trouves_pct"]].round(2).to_string(index=False))

    # --- figures -----------------------------------------------------------------------------------
    if args.tag:
        return
    ext = (grid.transform.c, grid.transform.c + grid.data.shape[1] * 20,
           grid.transform.f - grid.data.shape[0] * 20, grid.transform.f)
    picks = []
    for gname in sorted(geoms):
        sub = gd[(gd.geom == gname) & (gd.degre_min == 2)].sort_values("f1", ascending=False)
        if len(sub):
            picks.append((gname, sub.iloc[0].variable))
    n = len(picks) + 1
    ncol = min(n, 4)
    nrow = int(np.ceil(n / ncol))
    f, axs = plt.subplots(nrow, ncol, figsize=(4.2 * ncol, 4.2 * nrow), constrained_layout=True)
    axs = np.atleast_1d(axs).ravel()
    cmap = matplotlib.colors.ListedColormap(["#e8f0e3", "#f2c14e", "#f08a3c", "#c0392b"])
    s2show = np.where(forest, np.clip(deg, 0, 3), np.nan)
    axs[0].imshow(s2show, cmap=cmap, vmin=-0.5, vmax=3.5, extent=ext, interpolation="nearest")
    axs[0].set_title("Sentinel-2 reference (guide)", fontsize=9)
    for ax, (gname, var) in zip(axs[1:], picks):
        x, degs = keep_maps[(gname, var)]
        ax.imshow(np.where(forest, degs, np.nan), cmap=cmap, vmin=-0.5, vmax=3.5, extent=ext,
                  interpolation="nearest")
        ax.set_title(f"{gname} — {var}", fontsize=9)
    for ax in axs:
        ax.set_xticks([])
        ax.set_yticks([])
        ref_objs.boundary.plot(ax=ax, color="k", lw=0.3) if ax.has_data() else None
    for ax in axs[n:]:
        ax.set_visible(False)
    f.suptitle("Guide certainty degrees (yellow 1, orange 2, red 3); black: reference cuts", fontsize=10)
    f.savefig(fig / "m6_guide_maps.png", dpi=120)


if __name__ == "__main__":
    main()
