"""Tests of the NISAR HDF5 window reader on a small synthetic GCOV/GUNW file."""

import h5py
import numpy as np

from nisar_s1.io_nisar import GCOV_GRID, GUNW_GRID, gcov_backscatter, info_from_name, open_product, read_window


def _make(path):
    x = 300010.0 + 20 * np.arange(100)      # pixel centres
    y = 5300990.0 - 20 * np.arange(80)
    with h5py.File(path, "w") as h:
        g = h.create_group(GCOV_GRID)
        g["xCoordinates"], g["yCoordinates"], g["projection"] = x, y, np.uint32(32632)
        hh = np.full((80, 100), 0.1, "float32"); hh[:10] = 0  # first rows: no data
        g["HHHH"], g["HVHV"] = hh, hh / 10
        g["rtcGammaToSigmaFactor"] = np.full((80, 100), 2.0, "float32")
        w = h.create_group(GUNW_GRID + "/wrappedInterferogram")
        w["xCoordinates"], w["yCoordinates"], w["projection"] = x, y, np.uint32(32632)
        w["HH/coherenceMagnitude"] = np.tile(np.linspace(0, 1, 100, dtype="float32"), (80, 1))


def test_read_window(tmp_path):
    p = tmp_path / "p.h5"
    _make(p)
    with open_product(p) as h:
        r = read_window(h, "GUNW", "coh20", (300400, 5299800, 300800, 5300200))
        assert r.data.shape == (20, 20)
        assert r.crs == "EPSG:32632" and r.pixel_area_m2 == 400
        # top-left corner of the window = edge of the first selected pixel
        assert r.transform.c == 300400 and r.transform.f == 5300200
        b = gcov_backscatter(h, (300000, 5299400, 302000, 5301000))
        assert np.isnan(b["HH"].data[:10]).all()
        assert np.allclose(b["HH"].data[10:], -10) and np.allclose(b["HV"].data[10:], -20)
        s = gcov_backscatter(h, (300000, 5299400, 302000, 5301000), kind="sigma0")
        assert np.allclose(s["HH"].data[10:], -10 + 10 * np.log10(2))


def test_info_from_name():
    n = ("NISAR_L2_PR_GUNW_025_144_A_026_027_2000_SH_20260718T041939_20260718T042014_"
         "20260811T041938_20260811T042013_P05023_N_F_J_001.h5")
    i = info_from_name(n)
    assert (i.track, i.direction, i.frame, i.baseline_days) == (144, "A", 26, 24)
