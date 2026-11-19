"""Sentinel-2 L2A access (Element84 Earth Search, public COGs) and NDVI computation.

Data are read remotely by window / at reduced resolution, so nothing large is stored locally.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import rasterio
from pystac_client import Client
from rasterio.enums import Resampling
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds

EARTH_SEARCH = "https://earth-search.aws.element84.com/v1"
S2_COLLECTION = "sentinel-2-l2a"
# SCL classes considered valid: 4 vegetation, 5 bare soil, 6 water.
# Class 7 ("unclassified") is excluded: over the Vosges it holds many low-probability clouds
# (orographic cumulus), which otherwise appear as false clear-cuts.
SCL_VALID = (4, 5, 6)
# Extra cloud guard: surface reflectance in blue (B02) above this value is treated as cloud/haze.
# Forest is ~0.02-0.04, bare soil after a clear-cut rarely exceeds 0.10.
BLUE_MAX = 0.12


@dataclass
class Raster:
    """A single-band array with its georeferencing."""
    data: np.ndarray
    transform: rasterio.Affine
    crs: rasterio.crs.CRS

    @property
    def pixel_area_m2(self) -> float:
        return abs(self.transform.a * self.transform.e)


def search_s2(bbox: list[float], start: str, end: str, max_cloud: float = 30,
              tiles: list[str] | None = None) -> pd.DataFrame:
    """Search S2 L2A items; returns one row per item (id, date, tile, cloud cover, item)."""
    client = Client.open(EARTH_SEARCH)
    items = client.search(collections=[S2_COLLECTION], bbox=bbox, datetime=f"{start}/{end}",
                          query={"eo:cloud_cover": {"lt": max_cloud}}, max_items=2000).items()
    rows = [{"id": i.id, "date": pd.Timestamp(i.properties["datetime"]).date(),
             "tile": i.properties.get("s2:mgrs_tile") or i.id.split("_")[1],
             "cloud": i.properties["eo:cloud_cover"], "item": i} for i in items]
    df = pd.DataFrame(rows)
    if tiles is not None and len(df):
        df = df[df.tile.isin(tiles)]
    return df.sort_values(["tile", "date", "cloud"]).reset_index(drop=True)


# GDAL settings for fast remote COG access (fewer HTTP requests).
GDAL_ENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MULTIRANGE="YES",
                GDAL_HTTP_MERGE_CONSECUTIVE_RANGES="YES", VSI_CACHE="TRUE",
                CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif", GDAL_CACHEMAX=512)


def target_grid(href: str, res: float, bounds_wgs84: list[float] | None
                ) -> tuple[tuple[float, float, float, float], tuple[int, int], rasterio.crs.CRS]:
    """Bounds (snapped to ``res``, clipped to the image), output shape and CRS of a common grid.

    Every band of the same item read on this grid has exactly the same shape and transform,
    whatever its native resolution (10, 20 or 60 m).
    """
    with rasterio.Env(**GDAL_ENV), rasterio.open(href) as src:
        x0, y0, x1, y1 = src.bounds
        if bounds_wgs84 is not None:
            bx0, by0, bx1, by1 = transform_bounds("EPSG:4326", src.crs, *bounds_wgs84)
            x0, y0, x1, y1 = max(x0, bx0), max(y0, by0), min(x1, bx1), min(y1, by1)
        x0, y0 = np.floor(x0 / res) * res, np.floor(y0 / res) * res
        x1, y1 = np.ceil(x1 / res) * res, np.ceil(y1 / res) * res
        return (x0, y0, x1, y1), (int(round((y1 - y0) / res)), int(round((x1 - x0) / res))), src.crs


def _read(href: str, bounds: tuple[float, float, float, float], shape: tuple[int, int],
          resampling: Resampling) -> Raster:
    """Read band 1 of ``href`` onto the grid defined by ``bounds`` and ``shape``."""
    with rasterio.Env(**GDAL_ENV), rasterio.open(href) as src:
        win = from_bounds(*bounds, transform=src.transform)
        data = src.read(1, window=win, out_shape=shape, resampling=resampling,
                        boundless=True, fill_value=0)
        tr = rasterio.transform.from_bounds(*bounds, shape[1], shape[0])
        return Raster(data, tr, src.crs)


def ndvi(item, res: float = 20.0, bounds_wgs84: list[float] | None = None) -> Raster:
    """NDVI of a Sentinel-2 L2A item at ``res`` metres, NaN where SCL is not clear land.

    Reflectances are read with average resampling; SCL with nearest neighbour.
    The processing-baseline offset (-0.1 since baseline 04.00) is applied when present.
    """
    bounds, shape, _ = target_grid(item.assets["red"].href, res, bounds_wgs84)
    red = _read(item.assets["red"].href, bounds, shape, Resampling.average)
    nir = _read(item.assets["nir"].href, bounds, shape, Resampling.average)
    scl = _read(item.assets["scl"].href, bounds, shape, Resampling.nearest)
    blue = _read(item.assets["blue"].href, bounds, shape, Resampling.average)
    offset = float(item.properties.get("earthsearch:boa_offset_applied") is False and -1000 or 0)
    r = red.data.astype("float32") + offset
    n = nir.data.astype("float32") + offset
    with np.errstate(divide="ignore", invalid="ignore"):
        v = (n - r) / (n + r)
    b = (blue.data.astype("float32") + offset) / 10000.0
    v[~np.isin(scl.data, SCL_VALID) | (red.data == 0) | (b > BLUE_MAX)] = np.nan
    return Raster(v.astype("float32"), red.transform, red.crs)


# ---------------------------------------------------------------------------
# Forest mask: ESA WorldCover 2021 (10 m, public COGs on AWS), class 10 = tree cover.
WORLDCOVER_URL = ("https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
                  "ESA_WorldCover_10m_2021_v200_{tile}_Map.tif")
WORLDCOVER_TREE = 10


def _worldcover_tiles(bounds_wgs84: list[float]) -> list[str]:
    """Names of the 3x3 degree WorldCover tiles intersecting ``bounds_wgs84``."""
    x0, y0, x1, y1 = bounds_wgs84
    names = []
    for lat in range(int(np.floor(y0 / 3) * 3), int(np.floor(y1 / 3) * 3) + 1, 3):
        for lon in range(int(np.floor(x0 / 3) * 3), int(np.floor(x1 / 3) * 3) + 1, 3):
            names.append(f"{'N' if lat >= 0 else 'S'}{abs(lat):02d}{'E' if lon >= 0 else 'W'}{abs(lon):03d}")
    return names


def forest_mask_like(ref: Raster, bounds_wgs84: list[float]) -> np.ndarray:
    """Boolean tree-cover mask (WorldCover 2021) resampled onto the grid of ``ref``.

    A pixel is forest if most of it is tree cover (mode resampling).
    """
    from rasterio.vrt import WarpedVRT
    out = np.zeros(ref.data.shape, dtype=bool)
    h, w = ref.data.shape
    for tile in _worldcover_tiles(bounds_wgs84):
        with rasterio.Env(**GDAL_ENV), rasterio.open(WORLDCOVER_URL.format(tile=tile)) as src, \
                WarpedVRT(src, crs=ref.crs, transform=ref.transform, width=w, height=h,
                          resampling=Resampling.mode, nodata=0) as vrt:
            out |= vrt.read(1) == WORLDCOVER_TREE
    return out


def ndvi_composite(items: list, res: float = 20.0,
                   bounds_wgs84: list[float] | None = None, min_valid: int = 2) -> Raster:
    """Per-pixel median NDVI of several items of the same tile.

    A median of 3+ dates removes clouds or shadows left unmasked by SCL on a single date,
    which otherwise produce false "clear-cuts" (NDVI drop on one date only). Pixels with fewer
    than ``min_valid`` clear dates are set to NaN.
    """
    rasters = [ndvi(it, res, bounds_wgs84) for it in items]
    with np.errstate(all="ignore"):
        stack = np.stack([r.data for r in rasters])
        med = np.nanmedian(stack, axis=0).astype("float32")
        med[np.isfinite(stack).sum(axis=0) < min_valid] = np.nan  # need >= min_valid clear dates
    return Raster(med, rasters[0].transform, rasters[0].crs)


def save_raster(r: Raster, path) -> None:
    """Write a :class:`Raster` as a compressed float32 GeoTIFF."""
    from pathlib import Path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", driver="GTiff", height=r.data.shape[0], width=r.data.shape[1],
                       count=1, dtype="float32", crs=r.crs, transform=r.transform, nodata=np.nan,
                       compress="deflate", predictor=3, tiled=True) as dst:
        dst.write(r.data.astype("float32"), 1)


def load_raster(path) -> Raster:
    """Read a single-band GeoTIFF into a :class:`Raster`."""
    with rasterio.open(path) as src:
        return Raster(src.read(1), src.transform, src.crs)


def cached_composite(path, items: list, res: float, bounds_wgs84: list[float] | None) -> Raster:
    """:func:`ndvi_composite` with an on-disk GeoTIFF cache at ``path``."""
    from pathlib import Path
    if Path(path).exists():
        return load_raster(path)
    r = ndvi_composite(items, res, bounds_wgs84)
    save_raster(r, path)
    return r


def ndvi_timeseries(items: pd.DataFrame, polygon, polygon_crs, res: float = 10.0,
                    margin_m: float = 60.0) -> pd.DataFrame:
    """Median NDVI inside ``polygon`` for every item of ``items`` (one row per date).

    ``items`` is a frame from :func:`search_s2` (one tile). Only a small window around the
    polygon is read, so a full season takes a few seconds per date.
    Returns date, cloud (scene %), ndvi (median), valid (fraction of clear pixels).
    """
    import geopandas as gpd
    from rasterio.features import geometry_mask
    g = gpd.GeoSeries([polygon], crs=polygon_crs)
    bounds_wgs84 = list(g.buffer(margin_m).to_crs("EPSG:4326").total_bounds)
    rows = []
    for _, r in items.iterrows():
        nd = ndvi(r["item"], res, bounds_wgs84)
        inside = ~geometry_mask(list(g.to_crs(nd.crs)), out_shape=nd.data.shape,
                                transform=nd.transform)
        v = nd.data[inside]
        valid = float(np.isfinite(v).mean()) if v.size else 0.0
        rows.append({"date": r["date"], "cloud": r["cloud"], "valid": round(valid, 2),
                     "ndvi": float(np.nanmedian(v)) if valid > 0.5 else np.nan})
    return pd.DataFrame(rows)


def rgb_chip(item, centre_xy: tuple[float, float], half_m: float = 600, res: float = 10.0,
             swir: bool = False) -> np.ndarray:
    """True-colour (or SWIR/NIR/red false-colour if ``swir``) chip around ``centre_xy`` given in the
    item CRS (UTM of the tile), scaled to [0, 1] for display. Used for visual checks of candidates."""
    keys = ("swir16", "nir", "red") if swir else ("red", "green", "blue")
    x, y = centre_xy
    bounds = (x - half_m, y - half_m, x + half_m, y + half_m)
    n = int(round(2 * half_m / res))
    off = 0 if item.properties.get("earthsearch:boa_offset_applied", True) else 1000
    bands = [(_read(item.assets[k].href, bounds, (n, n), Resampling.bilinear).data.astype("float32")
              - off) / 1e4 for k in keys]
    rgb = np.dstack(bands)
    return np.clip(rgb / (0.35 if swir else 0.15), 0, 1)
