"""Landslide step 0 — study grid and independent site layers for Séchilienne (no radar):
Copernicus DEM GLO-30 (elevation, slope, aspect), ESA WorldCover tree cover and a clear-sky
Sentinel-2 summer image (true colour, NDVI). Used to delineate the moving slope from the literature
(south flank of Mont Sec, 450-1140 m) and to choose stable control slopes.

Outputs (Lambert 93, 20 m): ``results/sechilienne/grid/{dem,slope,aspect,forest,ndvi}.tif`` and the
quicklook ``results/sechilienne/figures/g0_site.png``.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds

from nisar_s1.config import load_site
from nisar_s1.optical import GDAL_ENV, Raster, forest_mask_like, save_raster, search_s2

DEM_URL = ("https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N45_00_E005_00_DEM/"
           "Copernicus_DSM_COG_10_N45_00_E005_00_DEM.tif")


def warp_to(url: str, grid: Raster, resampling=Resampling.bilinear, band: int = 1) -> np.ndarray:
    h, w = grid.data.shape
    with rasterio.Env(**GDAL_ENV), rasterio.open(url) as src, \
            WarpedVRT(src, crs=grid.crs, transform=grid.transform, width=w, height=h,
                      resampling=resampling) as vrt:
        a = vrt.read(band).astype("float32")
        if vrt.nodata is not None:
            a[a == vrt.nodata] = np.nan
    return a


def main() -> None:
    s = load_site("sechilienne")
    res = Path(s["chemins"]["results"])
    gdir = res / "grid"
    x0, x1, y0, y1 = s["site"]["bbox_wgs84"]
    px = float(s["site"]["grille_m"])
    bx0, by0, bx1, by1 = transform_bounds("EPSG:4326", s["site"]["crs"], x0, y0, x1, y1)
    bx0, by1 = np.floor(bx0 / px) * px, np.ceil(by1 / px) * px
    w, h = int(np.ceil((bx1 - bx0) / px)), int(np.ceil((by1 - by0) / px))
    grid = Raster(np.zeros((h, w), "float32"), from_origin(bx0, by1, px, px),
                  rasterio.crs.CRS.from_string(s["site"]["crs"]))
    print(f"grille {w} x {h} pixels de {px:.0f} m", flush=True)

    print("[1/4] MNT Copernicus GLO-30", flush=True)
    dem = warp_to(DEM_URL, grid)
    gy, gx = np.gradient(dem, px)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    aspect = np.degrees(np.arctan2(-gx, gy)) % 360   # downslope azimuth: 0 = north, 90 = east (rows run north to south)
    print("[2/4] WorldCover (couvert arboré)", flush=True)
    forest = forest_mask_like(grid, [x0, y0, x1, y1]).astype("float32")

    print("[3/4] Sentinel-2 d'été le plus clair", flush=True)
    df = search_s2([x0, y0, x1, y1], "2026-07-01", "2026-09-15", max_cloud=5)
    it = df.sort_values("cloud").iloc[0]
    print(f"      {it['id']} ({it['cloud']:.1f} % nuages)", flush=True)
    off = 0 if it["item"].properties.get("earthsearch:boa_offset_applied", True) else 1000
    b = {k: (warp_to(it["item"].assets[k].href, grid) - off) / 1e4 for k in ("red", "green", "blue", "nir")}
    ndvi = (b["nir"] - b["red"]) / (b["nir"] + b["red"])

    print("[4/4] écriture", flush=True)
    for name, a in dict(dem=dem, slope=slope, aspect=aspect, forest=forest, ndvi=ndvi).items():
        save_raster(Raster(a.astype("float32"), grid.transform, grid.crs), gdir / f"{name}.tif")
    rgb = np.clip(np.dstack([b["red"], b["green"], b["blue"]]) / 0.15, 0, 1)
    np.save(gdir / "rgb.npy", rgb.astype("float16"))

    ext = (bx0, bx0 + w * px, by1 - h * px, by1)
    fig, ax = plt.subplots(1, 2, figsize=(15, 6.5), constrained_layout=True)
    ax[0].imshow(rgb, extent=ext)
    cs = ax[0].contour(np.flipud(dem), levels=np.arange(300, 2000, 100), colors="w", linewidths=0.4,
                       extent=ext, origin="lower")
    ax[0].clabel(cs, cs.levels[::2], fontsize=6, fmt="%d")
    ax[0].set_title(f"Sentinel-2 {it['date']} et courbes de niveau (100 m)")
    im = ax[1].imshow(np.where(forest > 0, slope, np.nan), extent=ext, cmap="viridis", vmin=0, vmax=50)
    ax[1].set_title("Pente (°) sous couvert arboré (WorldCover)")
    fig.colorbar(im, ax=ax[1], shrink=0.7)
    for a in ax:
        a.set_xticks(np.arange(np.ceil(ext[0] / 1000) * 1000, ext[1], 1000))
        a.set_yticks(np.arange(np.ceil(ext[2] / 1000) * 1000, ext[3], 1000))
        a.tick_params(labelsize=6, rotation=45)
        a.grid(lw=0.3, alpha=0.5)
    (res / "figures").mkdir(parents=True, exist_ok=True)
    fig.savefig(res / "figures" / "g0_site.png", dpi=150)
    print("fait", flush=True)


if __name__ == "__main__":
    main()
