"""Clear-cut candidate detection from an NDVI pair, and selection of an intact control forest."""

from __future__ import annotations

import geopandas as gpd
import numpy as np
from rasterio.features import shapes
from scipy import ndimage
from shapely.geometry import shape

from .optical import Raster


def detect_clearcuts(pre: Raster, post: Raster, forest_min: float = 0.7,
                     drop_max: float = -0.3, min_area_ha: float = 5.0,
                     max_area_ha: float | None = 200.0,
                     forest: np.ndarray | None = None) -> gpd.GeoDataFrame:
    """Polygons where forest (NDVI_pre >= ``forest_min``) lost NDVI (dNDVI <= ``drop_max``).

    ``pre`` and ``post`` must share the same grid. ``forest`` is an optional boolean mask on that
    grid (e.g. WorldCover tree cover), needed to exclude harvested crops. Connected groups
    (8-connectivity) outside [``min_area_ha``, ``max_area_ha``] are discarded. Returns polygons with area and mean values.
    """
    d = post.data - pre.data
    mask = (pre.data >= forest_min) & (d <= drop_max)
    if forest is not None:
        mask &= forest
    mask = ndimage.binary_opening(mask, structure=np.ones((2, 2)))  # remove isolated pixels
    labels, n = ndimage.label(mask, structure=np.ones((3, 3)))
    if n == 0:
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=pre.crs)
    idx = np.arange(1, n + 1)
    counts = ndimage.sum(mask, labels, idx)
    area = counts * pre.pixel_area_m2 / 1e4
    keep = idx[(area >= min_area_ha) & (area <= (max_area_ha or np.inf))]
    rows = []
    for lab in keep:
        m = labels == lab
        geoms = [shape(g) for g, v in shapes(m.astype("uint8"), mask=m, transform=pre.transform) if v]
        geom = max(geoms, key=lambda g: g.area) if len(geoms) > 1 else geoms[0]
        rows.append({"geometry": geom,
                     "area_ha": round(m.sum() * pre.pixel_area_m2 / 1e4, 2),
                     "ndvi_pre": float(np.nanmean(pre.data[m])),
                     "ndvi_post": float(np.nanmean(post.data[m])),
                     "dndvi": float(np.nanmean(d[m]))})
    if not rows:
        return gpd.GeoDataFrame(columns=["geometry", "area_ha", "ndvi_pre", "ndvi_post", "dndvi"],
                                geometry="geometry", crs=pre.crs)
    gdf = gpd.GeoDataFrame(rows, crs=pre.crs)
    return gdf.sort_values("area_ha", ascending=False).reset_index(drop=True)


def control_forest(cut: gpd.GeoSeries | gpd.GeoDataFrame, pre: Raster, post: Raster,
                   ring_m: tuple[float, float] = (100, 1000), forest_min: float = 0.7,
                   stable_max: float = 0.05, target_ha: float | None = None,
                   forest: np.ndarray | None = None) -> gpd.GeoDataFrame:
    """Intact forest near a clear-cut: stable NDVI (|dNDVI| <= ``stable_max``) and NDVI_pre >= ``forest_min``,
    inside a ring between ``ring_m[0]`` and ``ring_m[1]`` metres around the cut.

    Returns the largest compact component, clipped to about ``target_ha`` (default: the cut area).
    """
    geom = cut.geometry.iloc[0] if hasattr(cut, "geometry") else cut.iloc[0]
    ring = geom.buffer(ring_m[1]).difference(geom.buffer(ring_m[0]))
    from rasterio.features import geometry_mask
    in_ring = ~geometry_mask([ring], out_shape=pre.data.shape, transform=pre.transform)
    d = post.data - pre.data
    ok = in_ring & (pre.data >= forest_min) & (np.abs(d) <= stable_max)
    if forest is not None:
        ok &= forest
    ok = ndimage.binary_opening(ok, structure=np.ones((3, 3)))
    labels, n = ndimage.label(ok)
    if n == 0:
        return gpd.GeoDataFrame(columns=["geometry"], geometry="geometry", crs=pre.crs)
    sizes = ndimage.sum(ok, labels, np.arange(1, n + 1))
    m = labels == (int(np.argmax(sizes)) + 1)
    poly = max((shape(g) for g, v in shapes(m.astype("uint8"), mask=m, transform=pre.transform) if v),
               key=lambda g: g.area)
    target = (target_ha or geom.area / 1e4) * 1e4
    if poly.area > target:
        # keep the part closest to the cut, about the same area as the cut
        c = poly.centroid
        r = (target / np.pi) ** 0.5
        near = poly.intersection(geom.buffer(ring_m[0] + 2 * r))
        poly = near if near.area >= 0.5 * target else poly.intersection(c.buffer(r * 1.2))
    return gpd.GeoDataFrame({"area_ha": [round(poly.area / 1e4, 2)],
                             "ndvi_pre": [float(np.nanmean(pre.data[m]))],
                             "dndvi": [float(np.nanmean(d[m]))]},
                            geometry=[poly], crs=pre.crs)


def classify_timeseries(ts, cut_window: tuple[str, str], forest_min: float = 0.7,
                        drop_min: float = 0.25, min_post: int = 2) -> dict:
    """Label a candidate from its NDVI time series (output of ``optical.ndvi_timeseries``).

    - ``clearcut``: forest before ``cut_window[0]`` (median NDVI >= ``forest_min``) and a
      persistent drop of at least ``drop_min`` on >= ``min_post`` clear dates after ``cut_window[1]``;
    - ``transient``: the drop is not persistent (unmasked cloud, haze, shadow);
    - ``not_forest`` or ``no_data`` otherwise.
    The cut date is estimated between the last high-NDVI date and the first low-NDVI date.
    """
    import pandas as pd
    ts = ts.dropna(subset=["ndvi"]).copy()
    ts["date"] = pd.to_datetime(ts["date"])
    pre = ts[ts.date < cut_window[0]]
    post = ts[ts.date > cut_window[1]]
    if len(pre) < 2 or len(post) < min_post:
        return {"label": "no_data"}
    ref = pre.ndvi.median()
    if ref < forest_min:
        return {"label": "not_forest", "ndvi_pre": ref}
    low = post.ndvi <= ref - drop_min
    out = {"ndvi_pre": round(ref, 3), "ndvi_post": round(post.ndvi.median(), 3),
           "n_post": int(len(post)), "n_post_low": int(low.sum())}
    if low.sum() >= min_post and low.mean() >= 0.75:
        thr = ref - drop_min
        first_low = ts[(ts.ndvi <= thr)].date.min()
        last_high = ts[(ts.date < first_low) & (ts.ndvi > thr)].date.max()
        out.update(label="clearcut", cut_after=str(last_high.date()), cut_before=str(first_low.date()))
    else:
        out["label"] = "transient"
    return out
