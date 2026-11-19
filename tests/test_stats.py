"""Tests of the separability metrics and of the grid helpers."""

import numpy as np
from shapely.geometry import box

from nisar_s1.grid import make_grid, polygon_mask, to_grid
from nisar_s1.optical import Raster
from nisar_s1.stats import block_bootstrap_auc, detection_scores, jeffries_matusita, separability


def test_separability_identical_and_separated():
    rng = np.random.default_rng(1)
    a, b = rng.normal(0, 1, 2000), rng.normal(0, 1, 2000)
    s = separability(a, b)
    assert abs(s["auc"] - 0.5) < 0.05 and s["jm"] < 0.05 and abs(s["cohen_d"]) < 0.1
    s = separability(a + 4, b)
    assert s["auc"] > 0.99 and s["jm"] > 1.5 and s["cohen_d"] > 3.5
    assert separability(b - 4, a)["auc"] < 0.01  # direction kept in auc
    assert jeffries_matusita(a, a + 100) > 1.99


def test_detection_and_bootstrap():
    rng = np.random.default_rng(2)
    img = rng.normal(0, 1, (60, 60))
    truth = np.zeros((60, 60), bool)
    truth[10:30, 10:30] = True
    img[truth] -= 3  # cuts have lower values
    d = detection_scores(img, truth, np.ones_like(truth), direction=-1)
    assert d["f1_best"] > 0.75 and d["recall_otsu"] > 0.9  # Otsu over-detects at 11 % prevalence
    lo, hi = block_bootstrap_auc(img, truth, ~truth, block=5, n=100)
    assert 0.9 < lo <= hi <= 1.0


def test_grid_roundtrip():
    g = make_grid((300005, 5300005, 300395, 5300395), 20, "EPSG:32632")
    assert g.data.shape == (20, 20) and g.transform.c == 300000
    fine = Raster(np.ones((80, 80), "float32"), g.transform @ g.transform.scale(0.25), g.crs)
    fine.data[:40] = 3
    r = to_grid(fine, g)
    assert np.allclose(r.data[:10], 3) and np.allclose(r.data[10:], 1)
    m = polygon_mask([box(300000, 5300000, 300200, 5300200)], g, erode_m=20)
    assert m.sum() == 8 * 8
