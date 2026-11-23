"""Maps for the training notebooks: product footprint, AOI and site polygons, static (matplotlib)
and interactive (folium, OpenStreetMap tiles; needs internet for the background only)."""

from __future__ import annotations

import math

import geopandas as gpd
import matplotlib.pyplot as plt
import pandas as pd
from shapely.geometry import box

COLORS = {"footprint": "#2a78d6", "aoi": "#eb6834", "cut": "#c0392b", "control": "#1e8449"}


def layers_frame(footprint=None, aoi_bbox=None, sites: gpd.GeoDataFrame | None = None) -> gpd.GeoDataFrame:
    """One GeoDataFrame (WGS84) with a ``layer`` column: footprint, aoi, and site roles."""
    rows = []
    if footprint is not None:
        rows.append({"layer": "footprint", "geometry": footprint})
    if aoi_bbox is not None:
        rows.append({"layer": "aoi", "geometry": box(*aoi_bbox)})
    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    if sites is not None:
        s = sites.to_crs(4326)
        s = gpd.GeoDataFrame({"layer": s.get("role", "site"), "geometry": s.geometry}, crs="EPSG:4326")
        gdf = gpd.GeoDataFrame(pd.concat([gdf, s], ignore_index=True), geometry="geometry", crs="EPSG:4326")
    return gdf


def static_map(gdf: gpd.GeoDataFrame, title: str = "", ax=None, zoom_to: str | None = None):
    """Outline map of the layers (works offline). ``zoom_to``: layer name to frame the view on."""
    if ax is None:
        _, ax = plt.subplots(figsize=(6.5, 6))
    for layer, sub in gdf.groupby("layer"):
        sub.boundary.plot(ax=ax, color=COLORS.get(layer, "#555555"), lw=2 if layer != "footprint" else 1.5,
                          label=layer)
    if zoom_to is not None:
        x0, y0, x1, y1 = gdf[gdf.layer == zoom_to].total_bounds
        mx, my = (x1 - x0) * 0.15, (y1 - y0) * 0.15
        ax.set_xlim(x0 - mx, x1 + mx)
        ax.set_ylim(y0 - my, y1 + my)
    ax.set_xlabel("longitude (deg)")
    ax.set_ylabel("latitude (deg)")
    ax.set_aspect(1 / max(0.2, math.cos(math.radians(ax.get_ylim()[0]))))
    ax.legend(frameon=False, loc="best")
    ax.set_title(title, loc="left")
    ax.grid(color="#eeeeee")
    return ax


def folium_map(gdf: gpd.GeoDataFrame, zoom_to: str | None = None):
    """Interactive map (OpenStreetMap background) with one toggleable layer per ``layer`` value."""
    import folium
    sel = gdf[gdf.layer == zoom_to] if zoom_to else gdf
    x0, y0, x1, y1 = sel.total_bounds
    m = folium.Map(tiles="OpenStreetMap", control_scale=True)
    for layer, sub in gdf.groupby("layer"):
        c = COLORS.get(layer, "#555555")
        folium.GeoJson(sub[["layer", "geometry"]].to_json(), name=layer,
                       style_function=lambda _f, c=c: {"color": c, "weight": 2, "fillOpacity": 0.05},
                       tooltip=folium.GeoJsonTooltip(["layer"])).add_to(m)
    folium.LayerControl().add_to(m)
    m.fit_bounds([[y0, x0], [y1, x1]])
    return m
