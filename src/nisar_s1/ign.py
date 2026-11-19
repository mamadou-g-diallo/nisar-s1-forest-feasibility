"""IGN reference layers for French study areas: sylvo-ecoregion outlines (IFN "SER") and the
BD Forêt V2 forest map (WFS of the Géoplateforme). Both are open data (Etalab licence)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests


def ser_outline(archive: str | Path, code: str) -> gpd.GeoDataFrame:
    """Dissolved outline of sylvo-ecoregion ``code`` (e.g. ``G23``) from the IFN ``ser_l93.zip``."""
    with zipfile.ZipFile(archive) as z:
        shp = [n for n in z.namelist() if n.endswith(".shp")][0]
    ser = gpd.read_file(f"zip://{archive}!{shp}")
    out = ser[ser["codeser"] == code].dissolve(by="codeser", as_index=False)
    return out[["codeser", "NomSER", "geometry"]]


def wfs_bbox(url: str, layer: str, bbox: tuple[float, float, float, float], crs: str = "EPSG:2154",
             page: int = 5000, timeout: int = 180, progress: bool = True) -> gpd.GeoDataFrame:
    """All features of ``layer`` intersecting ``bbox`` (in ``crs``), fetched page by page."""
    frames, start = [], 0
    while True:
        params = {"SERVICE": "WFS", "VERSION": "2.0.0", "REQUEST": "GetFeature", "TYPENAMES": layer,
                  "SRSNAME": crs, "BBOX": ",".join(map(str, bbox)) + f",{crs}",
                  "COUNT": page, "STARTINDEX": start, "OUTPUTFORMAT": "application/json"}
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        feats = r.json().get("features", [])
        if not feats:
            break
        frames.append(gpd.GeoDataFrame.from_features(feats, crs=crs))
        start += len(feats)
        if progress:
            print(f"  WFS {layer.split(':')[-1]} : {start} entités", flush=True)
        if len(feats) < page:
            break
    if not frames:
        return gpd.GeoDataFrame(geometry=[], crs=crs)
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=crs)


def forest_classes(bdf: gpd.GeoDataFrame, prefixes: list[str]) -> gpd.GeoDataFrame:
    """BD Forêt polygons whose ``code_tfv`` starts with one of ``prefixes``, with a simplified
    ``groupe`` column: feuillus / resineux / mixte / peupleraie / autre (from the TFV code)."""
    keep = bdf[bdf["code_tfv"].str.startswith(tuple(prefixes))].copy()
    tfv = keep["tfv"].str.lower()
    keep["groupe"] = "autre"
    feuillus = "feuillu|chêne|hêtre|châtaignier|robinier|frêne|charme|bouleau|aulne|peuplier"
    resineux = "conif|douglas|sapin|épicéa|pin|mélèze"
    keep.loc[tfv.str.contains(feuillus), "groupe"] = "feuillus"
    keep.loc[tfv.str.contains(resineux), "groupe"] = "resineux"
    keep.loc[tfv.str.contains("prépondérants"), "groupe"] = "mixte"
    keep.loc[keep["code_tfv"].str.startswith("FP"), "groupe"] = "peupleraie"
    return keep
