import numpy as np
import rasterio
from affine import Affine

from nisar_s1.guide_cr import (certainty_degrees, confusion_area, guide_stats, object_hits,
                               sieve_degrees, vectorize)
from nisar_s1.optical import Raster


def _scene(seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(0.0, 0.05, (100, 100)).astype("float32")
    x[20:40, 20:40] = -0.6          # 400 px cut (16 ha at 20 m)
    x[70, 70] = -0.6                # isolated pixel
    return x


def test_degrees_follow_m_minus_k_sigma():
    x = _scene()
    valid = np.ones_like(x, bool)
    m, s = guide_stats(x, valid)
    d = certainty_degrees(x, valid, direction=-1)
    assert d[30, 30] == 3 and d[70, 70] == 3
    assert (d[x > m - s] == 0).all()


def test_direction_plus_one_is_symmetric():
    x = _scene()
    valid = np.ones_like(x, bool)
    assert (certainty_degrees(-x, valid, direction=+1) == certainty_degrees(x, valid)).all()


def test_sieve_removes_small_objects_only():
    d = certainty_degrees(_scene(), np.ones((100, 100), bool))
    s = sieve_degrees(d, min_pixels=25)
    assert s[70, 70] == 0 and s[30, 30] == 3


def test_vectorize_and_confusion():
    grid = Raster(np.zeros((100, 100), "float32"), Affine(20, 0, 0, 0, -20, 2000),
                  rasterio.crs.CRS.from_epsg(2154))
    d = sieve_degrees(certainty_degrees(_scene(), np.ones((100, 100), bool)), 25)
    g = vectorize(d, grid)
    assert len(g) == 1 and abs(g.area_ha.iloc[0] - 16.0) < 1e-6
    ref = np.zeros((100, 100), bool)
    ref[20:40, 20:40] = True
    c = confusion_area(d > 0, ref, np.ones_like(ref), 400.0)
    assert c["omission_pct"] == 0 and c["commission_pct"] == 0 and c["kappa"] == 1
    lab = ref.astype(int)
    assert object_hits(d > 0, lab)[0] == 1.0
