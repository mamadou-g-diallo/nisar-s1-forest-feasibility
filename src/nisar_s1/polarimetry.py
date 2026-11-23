"""Dual-polarization SAR polarimetry (2x2 covariance matrix C2), for NISAR L-band HH/HV and
Sentinel-1 C-band VV/VH.

Over Europe NISAR acquires in dual-pol (DHDH: HH and HV), and its GCOV product stores only the
diagonal power terms (HHHH, HVHV). The complex cross term <HH.HV*> needed for polarimetric
decompositions is rebuilt here from the complex GSLC images (:func:`c2_from_slc`); for Sentinel-1
the same matrix comes from SNAP (``Polarimetric-Matrices`` C2) via :func:`c2_from_elements`.

Conventions: C2 = [[C11, C12], [C12*, C22]] with C11 = <|S_co|^2>, C22 = <|S_cross|^2>,
C12 = <S_co S_cross*> (co = HH or VV, cross = HV or VH), <.> = spatial multilook average.

References
- Cloude, S.R. (2007). The dual polarization entropy/alpha decomposition: a PALSAR case study.
  Proc. POLinSAR 2007, ESA SP-644.
- Cloude, S.R. & Pottier, E. (1997). An entropy based classification scheme for land applications
  of polarimetric SAR. IEEE TGRS 35(1), 68-78.
- Mandal, D. et al. (2020). Dual polarimetric radar vegetation index for crop growth monitoring
  using Sentinel-1 SAR data. Remote Sens. Environ. 247, 111954.
- Trudel, M., Charbonneau, F. & Leconte, R. (2012). Using RADARSAT-2 polarimetric and
  ENVISAT-ASAR dual-polarization data for estimating soil moisture over agricultural fields.
  Can. J. Remote Sens. 38(4), 514-527 (dual-pol RVI).
- Raney, R.K. (2007). Hybrid-polarity SAR architecture. IEEE TGRS 45(11), 3397-3404 (Stokes
  parameters of the received wave).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class C2:
    """Dual-pol covariance matrix, element-wise arrays (same shape)."""
    c11: np.ndarray
    c22: np.ndarray
    c12: np.ndarray  # complex

    @property
    def trace(self) -> np.ndarray:
        return self.c11 + self.c22

    @property
    def det(self) -> np.ndarray:
        return self.c11 * self.c22 - np.abs(self.c12) ** 2

    @property
    def coherence(self) -> np.ndarray:
        """Complex co/cross correlation coefficient rho = C12 / sqrt(C11 C22)."""
        with np.errstate(divide="ignore", invalid="ignore"):
            return self.c12 / np.sqrt(self.c11 * self.c22)

    @property
    def nbytes(self) -> int:
        return self.c11.nbytes + self.c22.nbytes + self.c12.nbytes


def _block_mean(a: np.ndarray, ly: int, lx: int, min_valid: float) -> np.ndarray:
    ny, nx = (a.shape[0] // ly) * ly, (a.shape[1] // lx) * lx
    b = a[:ny, :nx].reshape(ny // ly, ly, nx // lx, lx)
    valid = np.isfinite(b).sum(axis=(1, 3))
    with np.errstate(invalid="ignore"):
        m = np.nanmean(b, axis=(1, 3)) if np.isnan(b).any() else b.mean(axis=(1, 3))
    m = np.asarray(m)
    m[valid < min_valid * ly * lx] = np.nan
    return m


def c2_from_slc(s_co: np.ndarray, s_cross: np.ndarray, looks: tuple[int, int] = (4, 2),
                min_valid: float = 0.5) -> C2:
    """Multilooked C2 from two co-registered complex images (e.g. NISAR GSLC HH and HV).

    ``looks`` = (rows, cols) averaging box; the output is decimated by the same factors (one value
    per box), which keeps memory low. Boxes with less than ``min_valid`` finite pixels are NaN."""
    ly, lx = looks
    c11 = _block_mean((np.abs(s_co) ** 2).astype("float32"), ly, lx, min_valid)
    c22 = _block_mean((np.abs(s_cross) ** 2).astype("float32"), ly, lx, min_valid)
    prod = s_co * np.conj(s_cross)
    c12 = _block_mean(prod.real.astype("float32"), ly, lx, min_valid) + \
        1j * _block_mean(prod.imag.astype("float32"), ly, lx, min_valid)
    return C2(c11.astype("float32"), c22.astype("float32"), c12.astype("complex64"))


def c2_from_elements(c11, c22, c12_real, c12_imag) -> C2:
    """C2 from its four real elements (e.g. SNAP ``C11``, ``C22``, ``C12_real``, ``C12_imag``)."""
    return C2(np.asarray(c11, "float32"), np.asarray(c22, "float32"),
              (np.asarray(c12_real) + 1j * np.asarray(c12_imag)).astype("complex64"))


def validate_c2(c: C2, tol: float = 1e-4) -> dict:
    """Physical checks of a covariance matrix: non-negative powers, |rho| <= 1, det >= 0.

    Returns fractions of violating pixels (should all be ~0) and summary values."""
    ok = np.isfinite(c.c11) & np.isfinite(c.c22) & np.isfinite(c.c12)
    rho = np.abs(c.coherence[ok])
    tr = c.trace[ok]
    det = c.det[ok]
    lam1, lam2 = eigenvalues(C2(c.c11[ok], c.c22[ok], c.c12[ok]))
    return {
        "n_valid": int(ok.sum()),
        "frac_invalid": float(1 - ok.mean()),
        "frac_negative_power": float(((c.c11[ok] < 0) | (c.c22[ok] < 0)).mean()),
        "frac_rho_above_1": float((rho > 1 + tol).mean()),
        "frac_negative_det": float((det < -tol * tr ** 2).mean()),
        "max_trace_error": float(np.nanmax(np.abs(lam1 + lam2 - tr) / tr)) if tr.size else np.nan,
        "median_abs_rho": float(np.median(rho)) if rho.size else np.nan,
    }


def eigenvalues(c: C2) -> tuple[np.ndarray, np.ndarray]:
    """Closed-form eigenvalues of the 2x2 Hermitian C2, lambda1 >= lambda2 >= 0."""
    half = (c.c11 + c.c22) / 2
    root = np.sqrt(((c.c11 - c.c22) / 2) ** 2 + np.abs(c.c12) ** 2)
    return half + root, np.maximum(half - root, 0)


def h_alpha_dual(c: C2) -> dict[str, np.ndarray]:
    """Dual-pol entropy / anisotropy / mean alpha (Cloude 2007).

    alpha_i = arccos |first component of eigenvector i| (degrees, 0-90); in dual pol the two
    eigenvectors are orthogonal so alpha_1 + alpha_2 = 90. H uses log base 2 (0-1).
    A = (lambda1 - lambda2) / (lambda1 + lambda2)."""
    l1, l2 = eigenvalues(c)
    s = l1 + l2
    with np.errstate(divide="ignore", invalid="ignore"):
        p1, p2 = l1 / s, l2 / s
        ent = -(np.where(p1 > 0, p1 * np.log2(p1), 0) + np.where(p2 > 0, p2 * np.log2(p2), 0))
        mag_c12 = np.abs(c.c12)
        d = l1 - c.c11
        v1 = np.where(mag_c12 > 0, mag_c12 / np.sqrt(mag_c12 ** 2 + d ** 2),
                      np.where(c.c11 >= c.c22, 1.0, 0.0))
    alpha1 = np.degrees(np.arccos(np.clip(v1, 0, 1)))
    alpha2 = 90.0 - alpha1
    alpha = p1 * alpha1 + p2 * alpha2
    nan = ~np.isfinite(s) | (s <= 0)
    out = {"H": ent, "A": (l1 - l2) / s, "alpha": alpha, "alpha1": alpha1, "lambda1": l1, "lambda2": l2}
    for k in out:
        out[k] = np.where(nan, np.nan, out[k]).astype("float32")
    return out


def degree_of_polarization(c: C2) -> np.ndarray:
    """m = sqrt(1 - 4 det(C2) / tr(C2)^2), 0 (fully depolarized) to 1 (fully polarized)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.sqrt(np.clip(1 - 4 * c.det / c.trace ** 2, 0, 1)).astype("float32")


def dprvi(c: C2) -> np.ndarray:
    """Dual-pol radar vegetation index (Mandal et al. 2020): DpRVI = 1 - m * beta,
    beta = lambda1 / (lambda1 + lambda2). 0 = pure (bare) scatterer, towards 1 = random volume."""
    l1, l2 = eigenvalues(c)
    with np.errstate(divide="ignore", invalid="ignore"):
        beta = l1 / (l1 + l2)
    return (1 - degree_of_polarization(c) * beta).astype("float32")


def rvi_dual(co_power, cross_power) -> np.ndarray:
    """Intensity-only dual-pol RVI = 4 cross / (co + cross) (Trudel et al. 2012). Needs no phase,
    so it also works on GCOV / RTC products that store only the diagonal terms."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return (4 * np.asarray(cross_power) / (np.asarray(co_power) + np.asarray(cross_power))).astype("float32")


def stokes_dual(c: C2) -> dict[str, np.ndarray]:
    """Stokes vector of the received wave for a linear dual-pol system (Raney 2007 convention
    g3 = -2 Im C12), with degree of polarization m and ellipticity chi (degrees).

    For linear transmit (NISAR HH/HV, Sentinel-1 VV/VH) these describe the received wave only; the
    m-chi / m-delta scattering interpretation of compact-pol (circular transmit) does not apply."""
    g0 = c.c11 + c.c22
    g1 = c.c11 - c.c22
    g2 = 2 * c.c12.real
    g3 = -2 * c.c12.imag
    with np.errstate(divide="ignore", invalid="ignore"):
        m = np.sqrt(g1 ** 2 + g2 ** 2 + g3 ** 2) / g0
        chi = 0.5 * np.degrees(np.arcsin(np.clip(-g3 / (m * g0), -1, 1)))
    return {k: np.asarray(v, "float32") for k, v in
            {"g0": g0, "g1": g1, "g2": g2, "g3": g3, "m": m, "chi": chi}.items()}


def to_db(p) -> np.ndarray:
    """Power to dB (NaN for non-positive values)."""
    p = np.asarray(p, dtype="float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(p > 0, 10 * np.log10(p), np.nan).astype("float32")


def stretch(a: np.ndarray, pct: tuple[float, float] = (2, 98)) -> np.ndarray:
    """Percentile stretch to 0-1 (NaN kept)."""
    lo, hi = np.nanpercentile(a, pct)
    return np.clip((a - lo) / (hi - lo if hi > lo else 1), 0, 1)


def dualpol_rgb(co_power, cross_power, pct=(2, 98)) -> np.ndarray:
    """Dual-pol RGB: R = co (dB), G = cross (dB), B = co/cross ratio (dB); NaN -> black."""
    co, cr = to_db(co_power), to_db(cross_power)
    rgb = np.dstack([stretch(co, pct), stretch(cr, pct), stretch(co - cr, pct)])
    return np.nan_to_num(rgb, nan=0.0)


def memory_needed_gb(shape: tuple[int, int], n_arrays: int, itemsize: int = 8) -> float:
    """Rough memory needed to hold ``n_arrays`` arrays of ``shape`` (used as a guard)."""
    return shape[0] * shape[1] * n_arrays * itemsize / 2**30
