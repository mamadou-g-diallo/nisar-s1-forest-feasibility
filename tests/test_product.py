import h5py
import numpy as np
import pytest

from nisar_s1 import product as P

NAME = "NISAR_L2_PR_GCOV_034_144_A_026_2005_DHDH_M_20261103T041937_20261103T042013_P05036_N_F_J_001.h5"


@pytest.fixture
def gcov(tmp_path):
    """A tiny synthetic GCOV with the NISAR layout (2 frequencies, HH/HV, UTM 32N)."""
    p = tmp_path / NAME
    with h5py.File(p, "w") as f:
        ident = f.create_group("science/LSAR/identification")
        for k, v in {"granuleId": NAME[:-3], "zeroDopplerStartTime": "2026-11-03T04:19:37",
                     "zeroDopplerEndTime": "2026-11-03T04:20:13", "orbitPassDirection": "Ascending",
                     "lookDirection": "Left", "boundingPolygon":
                     "POLYGON Z ((6.5 47.5 0, 7.5 47.5 0, 7.5 48.5 0, 6.5 48.5 0, 6.5 47.5 0))"}.items():
            ident[k] = np.bytes_(v)
        ident["trackNumber"] = 144
        ident["frameNumber"] = 26
        ident["listOfFrequencies"] = np.array([b"A", b"B"])
        for fr, n, dx in (("A", 50, 20.0), ("B", 50, 80.0)):
            g = f.create_group(f"science/LSAR/GCOV/grids/frequency{fr}")
            g["listOfPolarizations"] = np.array([b"HH", b"HV"])
            g["listOfCovarianceTerms"] = np.array([b"HHHH", b"HVHV"])
            g["xCoordinates"] = 330000 + dx / 2 + dx * np.arange(n)
            g["yCoordinates"] = 5310000 - dx / 2 - dx * np.arange(n)
            g["projection"] = np.uint32(32632)
            hh = np.full((n, n), 0.1, "float32")
            hh[0, 0] = 0
            g.create_dataset("HHHH", data=hh, chunks=(16, 16))
            g.create_dataset("HVHV", data=np.full((n, n), 0.02, "float32"), chunks=(16, 16))
            g["mask"] = np.ones((n, n), "uint8")
    return p


def test_profile_is_discovered_from_content(gcov):
    with h5py.File(gcov) as h5:
        prof = P.product_profile(h5)
        assert prof.product_type == "GCOV" and prof.band == "LSAR"
        assert prof.frequencies == ["frequencyA", "frequencyB"]
        g = prof.grids["frequencyA"]
        assert g.polarizations == ["HH", "HV"] and g.terms == ["HHHH", "HVHV"]
        assert g.epsg == 32632 and g.dx == 20 and g.dy == -20 and g.shape == (50, 50)
        assert g.bounds == (330000, 5309000, 331000, 5310000)
        assert prof.polarimetric_mode == "dual-pol linear (HH/HV)"
        assert not prof.complex_terms_available("frequencyA")
        assert P.check_name_consistency(prof, NAME) == []
        assert P.footprint_lonlat(h5).bounds == (6.5, 47.5, 7.5, 48.5)
        assert any(r["path"].endswith("HHHH") for r in P.hdf5_tree(h5, max_depth=6))
        assert not any(r["path"].endswith("HHHH") for r in P.hdf5_tree(h5, max_depth=4))


def test_window_read_and_guard(gcov):
    with h5py.File(gcov) as h5:
        g = P.product_profile(h5).grids["frequencyA"]
        w = P.window_from_bounds(g, (330000, 5309800, 330100, 5310000))
        assert w.shape == (10, 5) and w.transform.c == 330000 and w.transform.f == 5310000
        a = P.read_layer(h5, g, "HHHH", w)
        assert np.isnan(a[0, 0]) and a[1, 1] == pytest.approx(0.1)
        with pytest.raises(MemoryError):
            P.read_layer(h5, g, "HHHH", w, max_gb=1e-9)
        with pytest.raises(ValueError):
            P.window_from_bounds(g, (0, 0, 10, 10))
        tiles = list(P.block_iter(w, block=4))
        assert sum(t.shape[0] * t.shape[1] for t in tiles) == 50
        assert tiles[1].transform.c == 330000 + 4 * 20


def test_session_roundtrip(tmp_path):
    s = tmp_path / "session.json"
    P.save_session(s, product="x.h5")
    P.save_session(s, frequency="frequencyA")
    assert P.load_session(s, required=("product", "frequency"))["frequency"] == "frequencyA"
    with pytest.raises(KeyError):
        P.load_session(s, required=("aoi",))


def test_write_subset_keeps_layout(gcov, tmp_path):
    with h5py.File(gcov) as h5:
        prof = P.product_profile(h5)
        g = prof.grids["frequencyA"]
        w = P.window_from_bounds(g, (330100, 5309500, 330400, 5309900))
        dst = P.write_subset(h5, prof, w, tmp_path / "sub.h5")
        ref = P.read_layer(h5, g, "HVHV", w)
    with h5py.File(dst) as s:
        sp = P.product_profile(s)
        assert sp.frequencies == ["frequencyA"] and sp.product_type == "GCOV"
        sg = sp.grids["frequencyA"]
        assert sg.shape == w.shape and sg.bounds == (330100, 5309500, 330400, 5309900)
        full = P.window_from_bounds(sg, sg.bounds)
        np.testing.assert_array_equal(P.read_layer(s, sg, "HVHV", full), ref)
