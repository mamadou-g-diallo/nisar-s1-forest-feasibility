import numpy as np
import pytest

from nisar_s1 import polarimetry as pol


def _random_c2(n=500, seed=0):
    rng = np.random.default_rng(seed)
    # random Hermitian positive semi-definite matrices from complex Gaussian samples
    k = rng.normal(size=(n, 16, 2)) + 1j * rng.normal(size=(n, 16, 2))
    k[..., 1] *= rng.uniform(0.05, 1.0, size=(n, 1))
    c11 = np.mean(np.abs(k[..., 0]) ** 2, axis=1)
    c22 = np.mean(np.abs(k[..., 1]) ** 2, axis=1)
    c12 = np.mean(k[..., 0] * np.conj(k[..., 1]), axis=1)
    return pol.C2(c11.astype("float32"), c22.astype("float32"), c12.astype("complex64"))


def test_eigenvalues_match_numpy():
    c = _random_c2()
    l1, l2 = pol.eigenvalues(c)
    m = np.stack([np.stack([c.c11, c.c12], -1), np.stack([np.conj(c.c12), c.c22], -1)], -2)
    ref = np.linalg.eigvalsh(m.astype("complex128"))
    np.testing.assert_allclose(l1, ref[:, 1], rtol=1e-4)
    np.testing.assert_allclose(l2, ref[:, 0], rtol=1e-3, atol=1e-5)


def test_alpha_matches_numpy_eigenvectors():
    c = _random_c2(200, seed=3)
    out = pol.h_alpha_dual(c)
    m = np.stack([np.stack([c.c11, c.c12], -1), np.stack([np.conj(c.c12), c.c22], -1)], -2)
    w, v = np.linalg.eigh(m.astype("complex128"))
    alpha1 = np.degrees(np.arccos(np.abs(v[:, 0, 1])))  # eigenvector of the largest eigenvalue
    np.testing.assert_allclose(out["alpha1"], alpha1, atol=1e-2)
    p = w[:, ::-1] / w.sum(1, keepdims=True)
    ent = -(p * np.log2(p)).sum(1)
    np.testing.assert_allclose(out["H"], ent, atol=1e-4)
    assert np.all((out["alpha"] >= 0) & (out["alpha"] <= 90))


def test_pure_targets():
    one = np.ones(1, "float32")
    zero = np.zeros(1, "complex64")
    # pure co-pol scatterer: H = 0, alpha = 0, m = 1, DpRVI = 0
    surf = pol.h_alpha_dual(pol.C2(one, one * 0, zero))
    assert surf["H"][0] == pytest.approx(0) and surf["alpha"][0] == pytest.approx(0)
    assert pol.dprvi(pol.C2(one, one * 0, zero))[0] == pytest.approx(0)
    # fully random (equal uncorrelated powers): H = 1, m = 0, DpRVI = 1
    rnd = pol.C2(one, one, zero)
    assert pol.h_alpha_dual(rnd)["H"][0] == pytest.approx(1)
    assert pol.degree_of_polarization(rnd)[0] == pytest.approx(0)
    assert pol.dprvi(rnd)[0] == pytest.approx(1)


def test_c2_from_slc_multilook_and_validation():
    rng = np.random.default_rng(1)
    co = (rng.normal(size=(40, 20)) + 1j * rng.normal(size=(40, 20))).astype("complex64")
    cr = (0.3 * co + 0.2 * (rng.normal(size=(40, 20)) + 1j * rng.normal(size=(40, 20)))).astype("complex64")
    co[0, 0] = np.nan
    c = pol.c2_from_slc(co, cr, looks=(4, 2))
    assert c.c11.shape == (10, 10)
    np.testing.assert_allclose(c.c22[1, 1], np.mean(np.abs(cr[4:8, 2:4]) ** 2), rtol=1e-5)
    np.testing.assert_allclose(c.c12[1, 1], np.mean(co[4:8, 2:4] * np.conj(cr[4:8, 2:4])), rtol=1e-5)
    chk = pol.validate_c2(c)
    assert chk["frac_rho_above_1"] == 0 and chk["frac_negative_det"] == 0
    assert chk["max_trace_error"] < 1e-4
    # strongly correlated co/cross -> high |rho|
    assert chk["median_abs_rho"] > 0.7


def test_stokes_degree_of_polarization_consistent():
    c = _random_c2(300, seed=5)
    s = pol.stokes_dual(c)
    np.testing.assert_allclose(s["m"], pol.degree_of_polarization(c), atol=1e-4)
    np.testing.assert_allclose(s["g0"] ** 2 * (1 - s["m"] ** 2), 4 * c.det, rtol=1e-3, atol=1e-4)


def test_rvi_and_rgb():
    assert pol.rvi_dual(np.array([1.0]), np.array([1.0]))[0] == pytest.approx(2.0)
    rgb = pol.dualpol_rgb(np.full((4, 4), 0.1), np.linspace(0.01, 0.02, 16).reshape(4, 4))
    assert rgb.shape == (4, 4, 3) and np.nanmax(rgb) <= 1
