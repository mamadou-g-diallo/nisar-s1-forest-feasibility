"""Separability metrics between two pixel samples (clear-cut vs intact forest) and a simple
threshold-detection score, used identically for every sensor and variable.

Spatial autocorrelation makes neighbouring pixels non-independent, so the report relies on effect
sizes (Cohen's d, AUC, Jeffries-Matusita) rather than p-values; confidence intervals use a block
bootstrap (resampling blocks of pixels) to account for that.
"""

from __future__ import annotations

import numpy as np
from scipy import stats as sps


def _clean(x) -> np.ndarray:
    x = np.asarray(x, dtype="float64").ravel()
    return x[np.isfinite(x)]


def cohen_d(a, b) -> float:
    """(mean(a) - mean(b)) / pooled standard deviation."""
    a, b = _clean(a), _clean(b)
    sp = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    return float((a.mean() - b.mean()) / sp) if sp > 0 else np.nan


def auc(a, b) -> float:
    """Probability that a random pixel of ``a`` is larger than one of ``b`` (Mann-Whitney AUC).
    0.5 = no separation; 0 or 1 = perfect separation (the sign gives the direction)."""
    a, b = _clean(a), _clean(b)
    u = sps.mannwhitneyu(a, b, alternative="two-sided").statistic
    return float(u / (len(a) * len(b)))


def jeffries_matusita(a, b) -> float:
    """Jeffries-Matusita distance under a Gaussian assumption, in [0, 2] (2 = fully separable)."""
    a, b = _clean(a), _clean(b)
    m1, m2, v1, v2 = a.mean(), b.mean(), a.var(ddof=1), b.var(ddof=1)
    if v1 <= 0 or v2 <= 0:
        return np.nan
    bh = (m1 - m2) ** 2 / (4 * (v1 + v2)) + 0.5 * np.log((v1 + v2) / (2 * np.sqrt(v1 * v2)))
    return float(2 * (1 - np.exp(-bh)))


def separability(a, b) -> dict:
    """All metrics for samples ``a`` (e.g. clear-cut) and ``b`` (e.g. control forest)."""
    a, b = _clean(a), _clean(b)
    if len(a) < 5 or len(b) < 5:
        return {"n_a": len(a), "n_b": len(b)}
    au = auc(a, b)
    return {"n_a": len(a), "n_b": len(b), "mean_a": a.mean(), "mean_b": b.mean(),
            "std_a": a.std(ddof=1), "std_b": b.std(ddof=1), "delta": a.mean() - b.mean(),
            "cohen_d": cohen_d(a, b), "auc": au, "auc_sep": max(au, 1 - au),
            "jm": jeffries_matusita(a, b)}


def block_bootstrap_auc(img: np.ndarray, mask_a: np.ndarray, mask_b: np.ndarray, block: int = 5,
                        n: int = 500, seed: int = 0) -> tuple[float, float]:
    """95 % interval of the separation AUC (max(AUC, 1-AUC)) by resampling ``block`` x ``block``
    pixel blocks (with replacement) inside each class."""
    rng = np.random.default_rng(seed)
    bi = (np.arange(img.shape[0])[:, None] // block) * 10**6 + np.arange(img.shape[1])[None, :] // block

    def groups(m):
        ids, vals = bi[m & np.isfinite(img)], img[m & np.isfinite(img)]
        order = np.argsort(ids)
        ids, vals = ids[order], vals[order]
        _, start = np.unique(ids, return_index=True)
        return np.split(vals, start[1:])

    ga, gb = groups(mask_a), groups(mask_b)
    if len(ga) < 3 or len(gb) < 3:
        return (np.nan, np.nan)
    res = []
    for _ in range(n):
        a = np.concatenate([ga[i] for i in rng.integers(0, len(ga), len(ga))])
        b = np.concatenate([gb[i] for i in rng.integers(0, len(gb), len(gb))])
        u = auc(a, b)
        res.append(max(u, 1 - u))
    return tuple(np.percentile(res, [2.5, 97.5]).round(3))


from .detect import detection_scores  # noqa: E402,F401  (kept here for backward compatibility)
