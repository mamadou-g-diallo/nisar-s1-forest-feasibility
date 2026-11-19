"""Offline tests for nisar_s1.sites (synthetic data)."""
import numpy as np
import pandas as pd
import rasterio

from nisar_s1.optical import Raster
from nisar_s1.sites import classify_timeseries, detect_clearcuts

WIN = ("2026-07-11", "2026-09-22")


def _ts(values, dates):
    return pd.DataFrame({"date": pd.to_datetime(dates), "ndvi": values})


DATES = ["2026-06-20", "2026-07-04", "2026-07-10", "2026-08-13", "2026-09-23", "2026-10-05", "2026-10-12"]


def test_persistent_drop_is_clearcut_with_dates():
    r = classify_timeseries(_ts([0.88, 0.87, 0.89, 0.40, 0.35, 0.37, 0.36], DATES), WIN)
    assert r["label"] == "clearcut"
    assert (r["cut_after"], r["cut_before"]) == ("2026-07-10", "2026-08-13")


def test_single_date_drop_is_transient():
    r = classify_timeseries(_ts([0.88, 0.87, 0.89, 0.86, 0.22, 0.85, 0.86], DATES), WIN)
    assert r["label"] == "transient"


def test_detect_clearcuts_with_forest_mask():
    pre = np.full((50, 50), 0.88, dtype="float32")
    post = pre.copy()
    post[10:25, 10:25] = 0.35                  # 225 px * 400 m2 = 9 ha at 20 m
    post[40:48, 40:48] = 0.30                  # crop field outside the forest mask
    forest = np.ones_like(pre, dtype=bool)
    forest[38:, 38:] = False
    tr = rasterio.transform.from_origin(400000, 5300000, 20, 20)
    g = detect_clearcuts(Raster(pre, tr, "EPSG:32632"), Raster(post, tr, "EPSG:32632"),
                         min_area_ha=2, forest=forest)
    assert len(g) == 1 and abs(g.area_ha[0] - 9.0) < 0.5
