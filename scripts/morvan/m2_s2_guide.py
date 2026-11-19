"""Morvan step 2 — the IRSTEA guide method applied to Sentinel-2 over the whole sylvo-ecoregion G23.

Guide chain (sections 2.2-2.3, 3.4-3.7), with Sentinel-2 L2A in place of SPOT / RapidEye:
  1. NDVI "before" and "after" composites (per-pixel median of the clearest dates of each window,
     which removes residual clouds; surface reflectance already corrected, so the guide's TOA
     conversion and relative normalisation are not needed);
  2. dNDVI = after - before, inside the G23 outline and the BD Forêt V2 forest mask;
  3. certainty degrees by m - k.sigma (k = 1, 2, 3), m and sigma computed in the forest mask;
  4. sieve at the 1 ha minimum mapping unit (25 pixels at 20 m);
  5. vector export with area, certainty degree, NDVI before / after and forest group.

Outputs: ``<data_root>/s2/*.tif`` (rasters), ``results/morvan/s2_coupes_guide.gpkg``,
``results/morvan/tables/s2_guide_*.csv``, ``results/morvan/figures/s2_guide_*.png``.
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from rasterio.features import rasterize  # noqa: E402

from nisar_s1.config import load_site  # noqa: E402
from nisar_s1.grid import make_grid, polygon_mask, to_grid  # noqa: E402
from nisar_s1.guide_cr import (certainty_degrees, guide_stats, sieve_degrees,  # noqa: E402
                               vectorize)
from nisar_s1.ign import forest_classes  # noqa: E402
from nisar_s1.optical import (Raster, load_raster, ndvi_composite, save_raster,  # noqa: E402
                              search_s2)

GROUPS = {"feuillus": 1, "resineux": 2, "mixte": 3, "peupleraie": 4, "autre": 5}
N_DATES = 3       # clearest dates per tile and window used in the median composite


def composite(site: dict, window: list[str], tag: str, bb: list[float], grid: Raster) -> Raster:
    """Median NDVI of the ``N_DATES`` clearest scenes of every tile, mosaicked on ``grid``."""
    out = Path(site["chemins"]["data_root"]) / "s2" / f"ndvi_{tag}_l93.tif"
    if out.exists():
        return load_raster(out)
    items = search_s2(bb, str(window[0]), str(window[1]),
                      max_cloud=site["capteurs"]["sentinel2"]["nuages_max_pct"])
    tiles = sorted(items.tile.unique())
    acc = np.zeros(grid.data.shape, "float64")
    cnt = np.zeros(grid.data.shape, "int16")
    meta = {}

    def one_tile(tile):
        sel = items[items.tile == tile].sort_values("cloud").drop_duplicates("date").head(N_DATES)
        meta[tile] = [f"{d} ({c:.0f} %)" for d, c in zip(sel.date, sel.cloud)]
        cache = out.parent / f"ndvi_{tag}_{tile}.tif"
        if not cache.exists():
            save_raster(ndvi_composite(list(sel["item"]), 20.0, bb, min_valid=2), cache)
        return tile

    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=len(tiles)) as ex:   # one remote reader per tile
        futs = [ex.submit(one_tile, t) for t in tiles]
        for i, fu in enumerate(as_completed(futs), 1):
            tile = fu.result()
            print(f"  [{tag}] tuile {i}/{len(tiles)} {tile} terminée : {', '.join(meta[tile])}", flush=True)
    for tile in tiles:
        r = load_raster(out.parent / f"ndvi_{tag}_{tile}.tif")
        g = to_grid(r, grid, "average").data
        ok = np.isfinite(g)
        acc[ok] += g[ok]
        cnt[ok] += 1
    with np.errstate(invalid="ignore"):
        mos = (acc / cnt).astype("float32")
    mos[cnt == 0] = np.nan
    res = Raster(mos, grid.transform, grid.crs)
    save_raster(res, out)
    (out.parent / f"ndvi_{tag}_dates.json").write_text(json.dumps(meta, indent=1))
    return res


def main() -> None:
    s = load_site("morvan")
    data, res = Path(s["chemins"]["data_root"]), Path(s["chemins"]["results"])
    (data / "s2").mkdir(parents=True, exist_ok=True)
    (res / "tables").mkdir(parents=True, exist_ok=True)
    (res / "figures").mkdir(parents=True, exist_ok=True)
    zone = gpd.read_file(res / "zone_g23.geojson")
    grid = make_grid(tuple(zone.total_bounds), s["site"]["grille_m"], s["site"]["crs"])
    bb = list(zone.to_crs(4326).total_bounds)
    print(f"Grille {grid.data.shape[1]} x {grid.data.shape[0]} pixels de 20 m (Lambert 93)")

    # --- masks: G23 outline and BD Forêt forest, with the forest group per pixel ----------------
    in_zone = polygon_mask(list(zone.geometry), grid)
    bdf = forest_classes(gpd.read_file(data / "ign" / "bdforet_g23.gpkg"),
                         s["bdforet"]["prefixes_foret"])
    group = rasterize(((g, GROUPS[k]) for g, k in zip(bdf.geometry, bdf.groupe)),
                      out_shape=grid.data.shape, transform=grid.transform, fill=0, dtype="uint8")
    forest = in_zone & (group > 0)
    save_raster(Raster(group.astype("float32"), grid.transform, grid.crs), data / "s2" / "forest_group_l93.tif")
    print(f"Forêt BD Forêt dans G23 : {forest.sum() * 0.04:.0f} ha")

    # --- NDVI composites and guide classification ---------------------------------------------
    pre = composite(s, s["periode"]["s2_avant"], "avant", bb, grid)
    post = composite(s, s["periode"]["s2_apres"], "apres", bb, grid)
    d = post.data - pre.data
    valid = forest & np.isfinite(d)
    m, sd = guide_stats(d, valid)
    k = s["guide"]["k_sigma"]
    deg = certainty_degrees(d, valid, direction=-1, k=tuple(k))
    min_px = int(round(s["guide"]["surface_min_ha"] * 1e4 / grid.pixel_area_m2))
    deg_s = sieve_degrees(deg, min_px)
    save_raster(Raster(d.astype("float32"), grid.transform, grid.crs), data / "s2" / "dndvi_l93.tif")
    save_raster(Raster(deg_s.astype("float32"), grid.transform, grid.crs), data / "s2" / "degres_s2_l93.tif")
    print(f"dNDVI en forêt : m = {m:.4f}, sigma = {sd:.4f} ; seuils m - k.sigma = "
          + ", ".join(f"{m - kk * sd:.3f}" for kk in k))
    print(f"Couverture valide : {valid.sum() / forest.sum():.1%} de la forêt")

    objs = vectorize(deg_s, grid, extra={"ndvi_avant": pre.data, "ndvi_apres": post.data,
                                         "dndvi": d})
    grp = np.where(group > 0, group, np.nan).astype("float32")
    from scipy import ndimage
    lab, _ = ndimage.label(deg_s > 0, structure=np.ones((3, 3)))
    inv = {v: kk for kk, v in GROUPS.items()}
    objs["groupe"] = [inv.get(int(ndimage.median(grp, lab, i + 1)), "autre") for i in range(len(objs))]
    objs["id"] = [f"M{i + 1:04d}" for i in range(len(objs))]
    objs = objs.sort_values("area_ha", ascending=False).reset_index(drop=True)
    objs.to_file(res / "s2_coupes_guide.gpkg", layer="coupes", driver="GPKG")

    # --- reference clear-cuts: strong degree qualified "forest -> bare soil" ------------------
    g = s["guide"]
    bare = ((deg_s >= g["degre_reference_min"]) & (pre.data >= g["ndvi_avant_min"])
            & (post.data <= g["ndvi_apres_max"]))
    ref_deg = sieve_degrees(np.where(bare, deg_s, 0).astype("uint8"), min_px)
    save_raster(Raster(ref_deg.astype("float32"), grid.transform, grid.crs), data / "s2" / "reference_s2_l93.tif")
    refs = vectorize(ref_deg, grid, extra={"ndvi_avant": pre.data, "ndvi_apres": post.data, "dndvi": d})
    lab2, _ = ndimage.label(ref_deg > 0, structure=np.ones((3, 3)))
    refs["groupe"] = [inv.get(int(ndimage.median(grp, lab2, i + 1)), "autre") for i in range(len(refs))]
    refs = refs.sort_values("area_ha", ascending=False).reset_index(drop=True)
    refs["id"] = [f"R{i + 1:03d}" for i in range(len(refs))]
    refs.to_file(res / "s2_coupes_guide.gpkg", layer="reference", driver="GPKG")
    print(f"Référence (degré >= {g['degre_reference_min']}, NDVI avant >= {g['ndvi_avant_min']}, "
          f"après <= {g['ndvi_apres_max']}, >= 1 ha) : {len(refs)} coupes, {refs.area_ha.sum():.0f} ha")
    print(refs.groupby("groupe").agg(n=("id", "size"), ha=("area_ha", "sum")).round(1).to_string())

    # --- summary tables ------------------------------------------------------------------------
    rows = []
    for dmin in (1, 2, 3):
        o = objs[objs.degre_max >= dmin]
        rows.append({"degre_min": dmin, "n_objets": len(o), "surface_ha": o.area_ha.sum(),
                     "surface_mediane_ha": o.area_ha.median(),
                     "pct_foret": 100 * o.area_ha.sum() / (forest.sum() * grid.pixel_area_m2 / 1e4)})
    summ = pd.DataFrame(rows)
    summ.to_csv(res / "tables" / "s2_guide_summary.csv", index=False)
    print(summ.round(2).to_string(index=False))
    by_g = (objs[objs.degre_max >= 2]
            .groupby("groupe").agg(n=("id", "size"), ha=("area_ha", "sum")).round(1))
    by_g.to_csv(res / "tables" / "s2_guide_by_group.csv")
    print(by_g.to_string())
    pd.DataFrame([{"m": m, "sigma": sd, **{f"seuil_k{kk}": m - kk * sd for kk in k},
                   "min_pixels": min_px, "foret_ha": forest.sum() * 0.04,
                   "valide_pct": 100 * valid.sum() / forest.sum()}]).to_csv(
        res / "tables" / "s2_guide_thresholds.csv", index=False)

    # --- figures ---------------------------------------------------------------------------------
    fig, ax = plt.subplots(1, 2, figsize=(13, 5.6), constrained_layout=True)
    v = d[valid]
    ax[0].hist(v, bins=200, range=(-0.8, 0.4), color="0.55")
    for kk, c in zip(k, ["#f2c14e", "#f08a3c", "#c0392b"]):
        ax[0].axvline(m - kk * sd, color=c, lw=1.5, label=f"m - {kk} sigma = {m - kk * sd:.3f}")
    ax[0].set_yscale("log")
    ax[0].set_xlabel("dNDVI (after - before), forest pixels of G23")
    ax[0].set_ylabel("pixels")
    ax[0].legend(fontsize=8)
    ax[0].set_title("Guide thresholds (section 2.2.3)")
    show = np.where(in_zone, np.where(forest, 1, 0), np.nan)
    ext = (grid.transform.c, grid.transform.c + grid.data.shape[1] * 20,
           grid.transform.f - grid.data.shape[0] * 20, grid.transform.f)
    ax[1].imshow(show, cmap="Greens", vmin=0, vmax=3, extent=ext, interpolation="nearest")
    cols = {1: "#f2c14e", 2: "#f08a3c", 3: "#c0392b"}
    for dg in (1, 2, 3):
        o = objs[objs.degre_max == dg]
        if len(o):
            o.plot(ax=ax[1], color=cols[dg], edgecolor=cols[dg], linewidth=0.8)
    zone.boundary.plot(ax=ax[1], color="k", lw=0.6)
    ax[1].set_title("Clear-cuts >= 1 ha by certainty degree (yellow 1, orange 2, red 3)")
    ax[1].set_xticks([])
    ax[1].set_yticks([])
    fig.savefig(res / "figures" / "s2_guide_overview.png", dpi=130)
    print(f"{len(objs)} objets écrits dans {res / 's2_coupes_guide.gpkg'}")


if __name__ == "__main__":
    main()
