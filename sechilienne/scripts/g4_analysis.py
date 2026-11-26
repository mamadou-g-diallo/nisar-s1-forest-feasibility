"""Landslide step 4 — L band (NISAR GUNW) against C band (Sentinel-1) on the Séchilienne slope.

All layers are brought onto the 20 m Lambert 93 grid of step 0 and compared on the reference zones
of step 1b (frontal scree, forested moving slope, stable control forest of the same steepness):

1. coherence of every pair, per zone;
2. phase: each interferogram is referenced to the control forest (circular mean), then
   * consistency of the phase on the moving slope = |mean phasor| (1 = one coherent signal, 0 = noise),
   * mean phase offset of the slope / frontal zone -> line-of-sight (LOS) range change,
     d = lambda / (4 pi) * phase (positive = range increase, i.e. moving away from the satellite;
     ISCE3 and SNAP both form reference x conj(secondary));
3. NISAR only (phase already unwrapped by ISCE3): range change of the slope relative to the control,
   with a planar ramp and a linear elevation term fitted outside the landslide removed (ionosphere,
   long-wavelength and stratified troposphere),
   and its cumulative sum along each 12-day chain.

Outputs: ``sechilienne/results/tables/g4_pairs.csv``, ``g4_cumul.csv`` and figures ``g4_*.png``.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import warnings

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import Resampling, reproject

from nisar_s1.config import load_site
from nisar_s1.optical import load_raster
from nisar_s1.snap import dimap_band

PAIRING = {"A173": 161, "D138": 139}
ZN = {1: "frontale", 2: "versant", 3: "temoin"}


def to_grid(path, grid, resampling=Resampling.bilinear) -> np.ndarray:
    out = np.full(grid.data.shape, np.nan, "float32")
    with rasterio.open(path) as src:
        a = src.read(1).astype("float32")
        nod = src.nodata
        if nod is not None:
            a[a == nod] = np.nan
        reproject(a, out, src_transform=src.transform, src_crs=src.crs, dst_transform=grid.transform,
                  dst_crs=grid.crs, resampling=resampling, src_nodata=np.nan, dst_nodata=np.nan)
    return out


def circ_ref(phase: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """Phase referenced to the circular mean of ``ref`` pixels, wrapped to (-pi, pi]."""
    z0 = np.nanmean(np.exp(1j * phase[ref]))
    return np.angle(np.exp(1j * phase) * np.conj(z0 / abs(z0)))


def phasor_stats(phase: np.ndarray, m: np.ndarray) -> tuple[float, float]:
    z = np.nanmean(np.exp(1j * phase[m & np.isfinite(phase)]))
    return float(abs(z)), float(np.angle(z))


def ramp_removed(unw: np.ndarray, x, y, hz, fit: np.ndarray) -> np.ndarray:
    """Remove a planar ramp (ionosphere, long-wavelength troposphere) and a linear elevation term
    (stratified troposphere: 450-1300 m of relief here), fitted outside the landslide."""
    m = fit & np.isfinite(unw) & np.isfinite(hz)
    A = np.c_[np.ones(m.sum()), x[m], y[m], hz[m]]
    c, *_ = np.linalg.lstsq(A, unw[m], rcond=None)
    return unw - (c[0] + c[1] * x + c[2] * y + c[3] * hz)


def nisar_pairs(data: Path, geom: str) -> pd.DataFrame:
    rows = []
    for f in sorted((data / "nisar" / geom / "GUNW").glob("*__unw.tif")):
        name = f.name.replace("__unw.tif", "")
        st = name.split("_SH_")[1].split("_")
        rows.append({"name": name, "ref": pd.Timestamp(st[0][:8]), "sec": pd.Timestamp(st[2][:8]),
                     "crid": name.split("_")[-4] + name.split("_")[-1]})
    if not rows:
        return pd.DataFrame(columns=["name", "ref", "sec", "crid"])
    df = pd.DataFrame(rows).sort_values(["ref", "sec", "crid"])
    return df.drop_duplicates(["ref", "sec"], keep="last").reset_index(drop=True)


def main() -> None:
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    s = load_site("sechilienne")
    res, data = Path(s["chemins"]["results"]), Path(s["chemins"]["data_root"])
    grid = load_raster(res / "grid" / "zones.tif")
    Z = grid.data.astype(int)
    T = grid.transform
    h, w = Z.shape
    cols, rows = np.meshgrid(np.arange(w), np.arange(h))
    X, Y = T * (cols + 0.5, rows + 0.5)
    X, Y = (X - X.mean()) / 1e3, (Y - Y.mean()) / 1e3
    dem = load_raster(res / "grid" / "dem.tif").data
    slide = (Z == 1) | (Z == 2)
    lam = {"L": s["capteurs"]["nisar"]["lambda_m"], "C": s["capteurs"]["sentinel1"]["lambda_m"]}
    out, maps = [], {}
    for geom, orbit in PAIRING.items():
        npairs = nisar_pairs(data, geom)
        dproc = data / "processed" / "sentinel1" / f"t{orbit:03d}"
        sel = pd.read_csv(res / "tables" / f"s1_selected_t{orbit}.csv")
        s1_of = {pd.Timestamp(r.nisar_date): pd.Timestamp(r.day) for _, r in sel.iterrows()}
        for i, p in npairs.iterrows():
            tag = f"[{geom} {i + 1}/{len(npairs)}]"
            base = data / "nisar" / geom / "GUNW" / p["name"]
            coh = to_grid(f"{base}__coh20.tif", grid)
            unw = to_grid(f"{base}__unw.tif", grid, Resampling.nearest)
            cc = to_grid(f"{base}__conncomp.tif", grid, Resampling.nearest)
            unw[~(cc > 0)] = np.nan
            fit = (~slide) & (coh > 0.3) & np.isfinite(unw)
            unw_r = ramp_removed(unw, X, Y, (dem - 800) / 1e3, fit)
            unw_r -= np.nanmedian(unw_r[Z == 3])
            row = {"geom": geom, "capteur": "L", "ref": p.ref.date(), "sec": p.sec.date(),
                   "jours": (p.sec - p.ref).days}
            for k, zn in ZN.items():
                row[f"coh_{zn}"] = float(np.nanmedian(coh[Z == k]))
            ph = circ_ref(unw, Z == 3)
            for k in (1, 2):
                c, a = phasor_stats(ph, Z == k)
                row[f"consist_{ZN[k]}"] = c
                row[f"dlos_wrap_mm_{ZN[k]}"] = 1e3 * lam["L"] / (4 * np.pi) * a
                row[f"dlos_unw_mm_{ZN[k]}"] = 1e3 * lam["L"] / (4 * np.pi) * float(np.nanmedian(unw_r[Z == k]))
            row["temoin_disp_mm"] = 1e3 * lam["L"] / (4 * np.pi) * float(
                np.nanpercentile(unw_r[Z == 3], 84) - np.nanpercentile(unw_r[Z == 3], 16)) / 2
            out.append(row)
            maps[("L", geom, p.ref, p.sec)] = (coh, ph, unw_r)
            # Sentinel-1 pair on the matching dates
            a, b = s1_of.get(p.ref), s1_of.get(p.sec)
            dim = dproc / f"ifg_{a.date() if a is not None else 'x'}_{b.date() if b is not None else 'x'}.dim"
            if a is None or b is None or not dim.exists():
                print(f"{tag} {p.ref.date()} -> {p.sec.date()} : L seul (S1 absent)", flush=True)
                continue
            ci = to_grid(dimap_band(dim, "coh_*VV"), grid)
            ii = to_grid(dimap_band(dim, "i_ifg*VV"), grid)
            qq = to_grid(dimap_band(dim, "q_ifg*VV"), grid)
            phc = circ_ref(np.angle(ii + 1j * qq), Z == 3)
            rc = {"geom": geom, "capteur": "C", "ref": a.date(), "sec": b.date(), "jours": (b - a).days}
            for k, zn in ZN.items():
                rc[f"coh_{zn}"] = float(np.nanmedian(ci[Z == k]))
            for k in (1, 2):
                c, ang = phasor_stats(phc, Z == k)
                rc[f"consist_{ZN[k]}"] = c
                rc[f"dlos_wrap_mm_{ZN[k]}"] = 1e3 * lam["C"] / (4 * np.pi) * ang
            out.append(rc)
            maps[("C", geom, p.ref, p.sec)] = (ci, phc, None)
            print(f"{tag} {p.ref.date()} -> {p.sec.date()} : coh versant L {row['coh_versant']:.2f} "
                  f"C {rc['coh_versant']:.2f}", flush=True)
    df = pd.DataFrame(out)
    (res / "tables").mkdir(exist_ok=True)
    df.round(3).to_csv(res / "tables" / "g4_pairs.csv", index=False)

    # cumulative NISAR range change along each chain of consecutive pairs
    cum = []
    for geom in PAIRING:
        d = df[(df.geom == geom) & (df.capteur == "L")].sort_values("ref")
        t, acc = None, {"frontale": 0.0, "versant": 0.0}
        for _, r in d.iterrows():
            if t is not None and pd.Timestamp(r.ref) != t:
                continue                       # keep a single contiguous chain
            if t is None:
                cum.append({"geom": geom, "date": r.ref, "frontale": 0.0, "versant": 0.0})
            for zn in acc:
                acc[zn] += r[f"dlos_unw_mm_{zn}"]
            cum.append({"geom": geom, "date": r.sec, **{k: round(v, 2) for k, v in acc.items()}})
            t = pd.Timestamp(r.sec)
    cdf = pd.DataFrame(cum)
    # cumulative maps (same contiguous chains)
    cmaps = {}
    for geom in PAIRING:
        acc, t, n = None, None, 0
        for k in sorted([k for k in maps if k[0] == "L" and k[1] == geom], key=lambda k: k[2]):
            if t is not None and k[2] != t:
                continue
            u = maps[k][2]
            acc = u.copy() if acc is None else acc + u
            t, n = k[3], n + 1
        if acc is not None:
            cmaps[geom] = (1e3 * lam["L"] / (4 * np.pi) * acc, n)
    cdf.to_csv(res / "tables" / "g4_cumul.csv", index=False)
    print(cdf.to_string(index=False))

    # figures
    figs = res / "figures"
    ext = (T.c, T.c + w * T.a, T.f + h * T.e, T.f)
    for geom in PAIRING:
        keysL = [k for k in maps if k[0] == "L" and k[1] == geom]
        keysC = [k for k in maps if k[0] == "C" and k[1] == geom]
        common = [k for k in keysL if ("C",) + k[1:] in maps]
        if not common:
            continue
        mL = np.nanmedian(np.stack([maps[k][0] for k in common]), axis=0)
        mC = np.nanmedian(np.stack([maps[("C",) + k[1:]][0] for k in common]), axis=0)
        best = max(common, key=lambda k: np.nanmedian(maps[k][0][Z == 2]))
        fig, ax = plt.subplots(2, 2, figsize=(13, 9.5), constrained_layout=True)
        for a_, im_, t_ in ((ax[0, 0], mL, f"Cohérence médiane bande L (NISAR {geom}), {len(common)} paires"),
                            (ax[0, 1], mC, f"Cohérence médiane bande C (S1 {PAIRING[geom]}), mêmes paires")):
            hnd = a_.imshow(im_, extent=ext, vmin=0, vmax=1, cmap="magma")
            a_.set_title(t_, fontsize=10)
        fig.colorbar(hnd, ax=ax[0, :], shrink=0.8, label="cohérence")
        phL, phC = maps[best][1], maps[("C",) + best[1:]][1]
        for a_, ph_, t_ in ((ax[1, 0], phL, "Phase bande L (1 cycle = 11,9 cm de distance)"),
                            (ax[1, 1], phC, "Phase bande C (1 cycle = 2,8 cm de distance)")):
            hnd = a_.imshow(ph_, extent=ext, vmin=-np.pi, vmax=np.pi, cmap="twilight")
            a_.set_title(f"{t_}\n{best[2].date()} -> {best[3].date()}, référencée sur la forêt témoin", fontsize=10)
        fig.colorbar(hnd, ax=ax[1, :], shrink=0.8, label="phase (rad)")
        for a_ in ax.flat:
            a_.contour(np.flipud(Z == 1), [0.5], colors="cyan", linewidths=0.8, extent=ext, origin="lower")
            a_.contour(np.flipud(Z == 2), [0.5], colors="w", linewidths=0.6, extent=ext, origin="lower")
            a_.contour(np.flipud(Z == 3), [0.5], colors="lime", linewidths=0.5, extent=ext, origin="lower")
            a_.tick_params(labelsize=6)
        fig.suptitle("Séchilienne : contour blanc = versant boisé en mouvement, cyan = zone frontale, "
                     "vert = forêt témoin", fontsize=10)
        fig.savefig(figs / f"g4_maps_{geom}.png", dpi=130)
        plt.close(fig)
    # cumulative displacement plot + maps
    if len(cdf):
        fig, ax = plt.subplots(1, 2, figsize=(13, 4.5), constrained_layout=True)
        for i, geom in enumerate(PAIRING):
            c = cdf[cdf.geom == geom]
            for zn, col in (("frontale", "tab:red"), ("versant", "tab:orange")):
                ax[i].plot(pd.to_datetime(c.date), c[zn], "o-", color=col, label=zn)
            ax[i].axhline(0, color="k", lw=0.6)
            ax[i].set_title(f"NISAR {geom} : variation de distance cumulée relative à la forêt témoin")
            ax[i].set_ylabel("mm (positif = éloignement)")
            ax[i].legend()
            ax[i].tick_params(axis="x", rotation=30)
        fig.savefig(figs / "g4_cumul_L.png", dpi=130)
        plt.close(fig)
    if cmaps:
        fig, ax = plt.subplots(1, len(cmaps), figsize=(6.5 * len(cmaps), 5), constrained_layout=True)
        for a_, (geom, (cm, n)) in zip(np.atleast_1d(ax), cmaps.items()):
            hnd = a_.imshow(cm, extent=ext, vmin=-30, vmax=30, cmap="RdBu_r")
            a_.contour(np.flipud(Z == 1), [0.5], colors="k", linewidths=0.9, extent=ext, origin="lower")
            a_.contour(np.flipud(Z == 2), [0.5], colors="0.3", linewidths=0.5, extent=ext, origin="lower")
            a_.contour(np.flipud(Z == 3), [0.5], colors="g", linewidths=0.5, extent=ext, origin="lower")
            a_.set_title(f"NISAR {geom} : variation de distance cumulée ({n} paires), mm", fontsize=10)
            a_.tick_params(labelsize=6)
            fig.colorbar(hnd, ax=a_, shrink=0.8, label="mm (positif = éloignement)")
        fig.savefig(figs / "g4_cumul_maps_L.png", dpi=130)
        plt.close(fig)


if __name__ == "__main__":
    main()
