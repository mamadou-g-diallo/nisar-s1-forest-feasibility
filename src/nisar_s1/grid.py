"""Common analysis grid: reprojection of any sensor raster onto it, and polygon masks.

All sensors (NISAR GCOV/GUNW, Sentinel-1 from SNAP, Sentinel-2 NDVI) are compared on the same
grid (default 20 m, UTM 32N), so per-pixel statistics use exactly the same ground samples.
"""

from __future__ import annotations

import numpy as np
import rasterio
from affine import Affine
from rasterio.features import geometry_mask
from rasterio.warp import Resampling, reproject

from .optical import Raster


def make_grid(bounds: tuple[float, float, float, float], res: float, crs: str) -> Raster:
    """Empty (NaN) raster covering ``bounds`` (snapped outward to multiples of ``res``)."""
    xmin, ymin = np.floor(bounds[0] / res) * res, np.floor(bounds[1] / res) * res
    xmax, ymax = np.ceil(bounds[2] / res) * res, np.ceil(bounds[3] / res) * res
    w, h = int(round((xmax - xmin) / res)), int(round((ymax - ymin) / res))
    return Raster(np.full((h, w), np.nan, "float32"), Affine(res, 0, xmin, 0, -res, ymax),
                  rasterio.crs.CRS.from_user_input(crs))


def to_grid(src: Raster, grid: Raster, resampling: str = "average") -> Raster:
    """Reproject ``src`` onto ``grid`` (NaN = no data). ``average`` for continuous variables
    sampled at the same or a finer resolution, ``bilinear`` for coarser inputs, ``nearest`` for classes."""
    out = np.full(grid.data.shape, np.nan, "float32")
    reproject(src.data.astype("float32"), out, src_transform=src.transform, src_crs=src.crs,
              dst_transform=grid.transform, dst_crs=grid.crs, src_nodata=np.nan, dst_nodata=np.nan,
              resampling=Resampling[resampling])
    return Raster(out, grid.transform, grid.crs)


def polygon_mask(geoms, grid: Raster, erode_m: float = 0.0, all_touched: bool = False) -> np.ndarray:
    """Boolean mask of pixels whose centre lies in the (optionally eroded) polygons."""
    geoms = [g.buffer(-erode_m) if erode_m else g for g in geoms]
    geoms = [g for g in geoms if not g.is_empty]
    if not geoms:
        return np.zeros(grid.data.shape, bool)
    return ~geometry_mask(geoms, out_shape=grid.data.shape, transform=grid.transform,
                          all_touched=all_touched)


def read_geotiff(path, band: int | str = 1) -> Raster:
    """Read one band (index or band description, e.g. ``coh_VV``) of a GeoTIFF as a Raster."""
    with rasterio.open(path) as ds:
        if isinstance(band, str):
            names = [d or "" for d in ds.descriptions]
            match = [i + 1 for i, d in enumerate(names) if band.lower() in d.lower()]
            if not match:
                raise KeyError(f"band {band!r} not in {names}")
            band = match[0]
        a = ds.read(band).astype("float32")
        if ds.nodata is not None and not np.isnan(ds.nodata):
            a[a == ds.nodata] = np.nan
        return Raster(a, ds.transform, ds.crs)
