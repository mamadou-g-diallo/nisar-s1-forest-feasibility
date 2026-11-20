"""Landslide step 1b — reference zones, built WITHOUT radar data (avoids circular reasoning).

From the literature (Séchilienne, right bank of the Romanche, south-east facing flank of Mont Sec,
deformation between ~450 and 1140 m, very active "frontal zone" of bare gneiss scree around
700-1000 m) and from the independent layers of step 0 (Copernicus DEM, WorldCover, Sentinel-2):

* ``frontale``  : sparsely vegetated scree (Sentinel-2 NDVI < 0.55) on the right-bank slope,
                  600-1100 m, inside the search box of the visible scar (photo-interpretation);
* ``versant``   : the forested part of the moving slope: right bank, 450-1140 m, downslope azimuth
                  90-200 deg, slope >= 15 deg, within 1.2 km of the frontal zone, tree cover;
* ``temoin``    : stable control forest with the same terrain classes (azimuth 90-200 deg, slope
                  30-50 deg, as steep as the moving slope, 450-1300 m) more than 2.5 km away.

Output: ``results/sechilienne/grid/zones.tif`` (0 none, 1 frontale, 2 versant, 3 temoin) and
``results/sechilienne/tables/g1b_zones.csv``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

from nisar_s1.config import load_site
from nisar_s1.optical import Raster, load_raster, save_raster

SCAR_BOX = (924300, 6444500, 925700, 6446300)   # L93, photo-interpreted from g0_site.png
ZONES = {1: "frontale", 2: "versant", 3: "temoin"}


def main() -> None:
    s = load_site("sechilienne")
    res = Path(s["chemins"]["results"])
    g = {k: load_raster(res / "grid" / f"{k}.tif") for k in ("dem", "slope", "aspect", "forest", "ndvi")}
    T = g["dem"].transform
    h, w = g["dem"].data.shape
    cols, rows = np.meshgrid(np.arange(w), np.arange(h))
    x, y = T * (cols + 0.5, rows + 0.5)
    dem, slope, asp = g["dem"].data, g["slope"].data, g["aspect"].data
    forest, ndvi = g["forest"].data > 0, g["ndvi"].data
    # right bank of the Romanche = north-west of the valley floor; valley floor = lowest cells.
    # Simple, explicit criterion: downslope azimuth towards the south-east (the river).
    facing = (asp >= 90) & (asp <= 200)
    inbox = (x >= SCAR_BOX[0]) & (x <= SCAR_BOX[2]) & (y >= SCAR_BOX[1]) & (y <= SCAR_BOX[3])
    front = inbox & facing & (dem >= 600) & (dem <= 1100) & (ndvi < 0.55)
    front = ndimage.binary_opening(front, iterations=1)
    lab, n = ndimage.label(front)
    if n:
        sizes = ndimage.sum(front, lab, range(1, n + 1))
        front = np.isin(lab, 1 + np.flatnonzero(sizes >= 10))       # >= 0.4 ha patches
    dist = ndimage.distance_transform_edt(~front) * abs(T.a)
    slope_ok = (slope >= 15) & (slope <= 50)
    versant = (~front) & forest & facing & slope_ok & (dem >= 450) & (dem <= 1140) & (dist <= 1200)
    # control slopes as steep as the moving slope (coherence depends strongly on slope)
    temoin = forest & facing & (slope >= 30) & (slope <= 50) & (dem >= 450) & (dem <= 1300) & (dist > 2500)
    z = np.zeros((h, w), "float32")
    z[temoin], z[versant], z[front] = 3, 2, 1
    save_raster(Raster(z, T, g["dem"].crs), res / "grid" / "zones.tif")
    pa = abs(T.a * T.e) / 1e4
    rows_ = []
    for k, name in ZONES.items():
        m = z == k
        rows_.append({"zone": name, "pixels": int(m.sum()), "ha": round(m.sum() * pa, 1),
                      "alt_med": round(float(np.median(dem[m])), 0), "pente_med": round(float(np.median(slope[m])), 1),
                      "azimut_med": round(float(np.median(asp[m])), 0), "ndvi_med": round(float(np.nanmedian(ndvi[m])), 2),
                      "foret_pct": round(100 * float(forest[m].mean()), 0)})
    df = pd.DataFrame(rows_)
    (res / "tables").mkdir(parents=True, exist_ok=True)
    df.to_csv(res / "tables" / "g1b_zones.csv", index=False)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
