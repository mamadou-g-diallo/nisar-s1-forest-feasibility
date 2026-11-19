"""Prototype change detection by thresholding a per-pixel change feature, scored against a reference
mask (Sentinel-2 dNDVI). Sensor-agnostic: the same function scores NISAR, Sentinel-1 or ROSE-L features."""

from __future__ import annotations

import numpy as np


def detection_scores(feature: np.ndarray, truth: np.ndarray, valid: np.ndarray,
                     direction: int) -> dict:
    """Pixel-wise detection of ``truth`` (clear-cut = True) from ``feature`` inside ``valid``.

    ``direction`` = +1 if clear-cuts have larger values, -1 if smaller. Two thresholds:
    Otsu (unsupervised, realistic) and the best-F1 threshold (oracle, upper bound).
    """
    from skimage.filters import threshold_otsu
    ok = valid & np.isfinite(feature)
    f, t = direction * feature[ok], truth[ok].astype(bool)
    if t.sum() < 5 or (~t).sum() < 5:
        return {}

    def f1_at(th):
        p = f >= th
        tp, fp, fn = (p & t).sum(), (p & ~t).sum(), (~p & t).sum()
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        return (2 * prec * rec / (prec + rec) if prec + rec else 0.0), prec, rec

    otsu = threshold_otsu(f)
    f1o, po, ro = f1_at(otsu)
    cands = np.unique(np.percentile(f, np.linspace(1, 99, 99)))
    best = max(((f1_at(c)[0], c) for c in cands), key=lambda x: x[0])
    from scipy.stats import mannwhitneyu
    u = mannwhitneyu(f[t], f[~t], alternative="two-sided").statistic / (t.sum() * (~t).sum())
    return {"auc_window": float(u), "f1_otsu": f1o, "precision_otsu": po, "recall_otsu": ro,
            "threshold_otsu": direction * otsu, "f1_best": best[0], "threshold_best": direction * best[1],
            "prevalence": t.mean()}
