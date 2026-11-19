"""Clear-cut mapping method of the IRSTEA/TETIS methodological guide (Ose & Deshayes, 2015,
"Détection et cartographie des coupes rases par télédétection satellitaire", v5.0), written so that
it applies to any per-pixel change image: Sentinel-2 dNDVI (as in the guide) or radar change
features (NISAR, Sentinel-1, ROSE-L).

Guide steps reproduced here:
  * section 2.2.3 / 3.6.1-3.6.2: statistical thresholds on the change image, mean m and standard
    deviation s computed inside the forest mask; a pixel is a candidate cut if
    change < m - s, with three certainty degrees (1: [m-2s, m-s), 2: [m-3s, m-2s), 3: < m-3s);
  * section 3.6.3: GDAL "sieve" filter to remove objects below the minimum mapping unit (1 ha);
  * section 2.3.2: vector export with the certainty degree and the area;
  * section 2.4 / 3.9: confusion matrix by area, producer / user accuracy, omission / commission,
    overall accuracy, plus Cohen's kappa.
For a radar feature where clear-cuts produce *larger* values (e.g. a coherence drop) the same rule
is applied to the negated feature (``direction=+1``).
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
from rasterio.features import shapes, sieve
from scipy import ndimage
from shapely.geometry import shape

from .optical import Raster


def guide_stats(change: np.ndarray, valid: np.ndarray) -> tuple[float, float]:
    """Mean and standard deviation of ``change`` inside ``valid`` (the forest mask)."""
    v = change[valid & np.isfinite(change)]
    return float(v.mean()), float(v.std(ddof=1))


def certainty_degrees(change: np.ndarray, valid: np.ndarray, direction: int = -1,
                      k: tuple[float, float, float] = (1, 2, 3),
                      stats: tuple[float, float] | None = None) -> np.ndarray:
    """Guide "requête 2": uint8 image, 0 = no detection / outside forest, 1-3 = certainty degree.

    ``direction`` = -1 when cuts decrease the feature (dNDVI, d_gamma0), +1 when they increase it
    (coherence drop). ``stats`` = (m, s) may be imposed (e.g. computed on another image)."""
    # clear-cuts are always on the low side of ``y``
    y = change if direction == -1 else -change
    m, s = stats if stats is not None else guide_stats(y, valid)
    out = np.zeros(change.shape, "uint8")
    ok = valid & np.isfinite(y)
    out[ok & (y < m - k[0] * s)] = 1
    out[ok & (y < m - k[1] * s)] = 2
    out[ok & (y < m - k[2] * s)] = 3
    return out


def sieve_degrees(degrees: np.ndarray, min_pixels: int, connectivity: int = 8,
                  min_degree: int = 1) -> np.ndarray:
    """Guide "Tamiser": remove detected objects (degree >= ``min_degree``) smaller than ``min_pixels``.

    The sieve is applied to the binary detection, so an object made of several degrees is kept or
    removed as a whole; the degrees of kept pixels are unchanged."""
    det = (degrees >= min_degree).astype("uint8")
    kept = sieve(det, size=min_pixels, connectivity=connectivity)
    # sieve merges small objects into their surroundings: keep only pixels still detected
    return np.where((kept == 1) & (det == 1), degrees, 0).astype("uint8")


def vectorize(degrees: np.ndarray, grid: Raster, min_degree: int = 1,
              extra: dict[str, np.ndarray] | None = None) -> gpd.GeoDataFrame:
    """Connected objects (8-connectivity) of ``degrees >= min_degree`` as polygons, with the area,
    the maximum and majority certainty degree, and the mean of every array of ``extra``."""
    det = degrees >= min_degree
    labels, n = ndimage.label(det, structure=np.ones((3, 3)))
    if n == 0:
        return gpd.GeoDataFrame(columns=["geometry", "area_ha", "degre_max", "degre_maj"],
                                geometry="geometry", crs=grid.crs)
    rows = []
    objs = ndimage.find_objects(labels)
    for lab, sl in enumerate(objs, start=1):
        m = labels[sl] == lab
        tr = grid.transform @ grid.transform.translation(sl[1].start, sl[0].start)
        geoms = [shape(g) for g, v in shapes(m.astype("uint8"), mask=m, transform=tr) if v]
        geom = geoms[0] if len(geoms) == 1 else gpd.GeoSeries(geoms).union_all()
        d = degrees[sl][m]
        row = {"geometry": geom, "area_ha": m.sum() * grid.pixel_area_m2 / 1e4,
               "degre_max": int(d.max()), "degre_maj": int(np.bincount(d).argmax())}
        for name, arr in (extra or {}).items():
            row[name] = float(np.nanmean(arr[sl][m]))
        rows.append(row)
    return gpd.GeoDataFrame(rows, crs=grid.crs)


def confusion_area(pred: np.ndarray, ref: np.ndarray, valid: np.ndarray,
                   pixel_area_m2: float) -> dict:
    """Guide table 4: 2x2 confusion matrix by area (ha) between a predicted and a reference
    clear-cut mask inside ``valid``, with producer / user accuracy, omission / commission (%),
    overall accuracy (%) and Cohen's kappa."""
    p, r = pred[valid].astype(bool), ref[valid].astype(bool)
    ha = pixel_area_m2 / 1e4
    tp, fn = (p & r).sum() * ha, (~p & r).sum() * ha
    fp, tn = (p & ~r).sum() * ha, (~p & ~r).sum() * ha
    n = tp + fn + fp + tn
    prod = tp / (tp + fn) if tp + fn else np.nan
    user = tp / (tp + fp) if tp + fp else np.nan
    po = (tp + tn) / n
    pe = ((tp + fn) * (tp + fp) + (tn + fp) * (tn + fn)) / n**2
    return {"ref_ha": tp + fn, "pred_ha": tp + fp, "tp_ha": tp, "fn_ha": fn, "fp_ha": fp,
            "tn_ha": tn, "producer_pct": 100 * prod, "user_pct": 100 * user,
            "omission_pct": 100 * (1 - prod), "commission_pct": 100 * (1 - user),
            "overall_pct": 100 * po, "kappa": (po - pe) / (1 - pe) if pe < 1 else np.nan,
            "f1": 2 * tp / (2 * tp + fp + fn) if tp else 0.0}


def object_hits(pred: np.ndarray, ref_labels: np.ndarray, min_frac: float = 0.25) -> np.ndarray:
    """For every reference object (labels 1..n in ``ref_labels``), the fraction of its pixels that
    are detected; an object counts as found when that fraction is >= ``min_frac``."""
    n = int(ref_labels.max())
    if n == 0:
        return np.zeros(0)
    idx = np.arange(1, n + 1)
    return ndimage.mean(pred.astype("float32"), ref_labels, idx)
