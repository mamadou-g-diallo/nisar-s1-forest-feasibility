"""Readers for NISAR L2 geocoded products (GCOV backscatter, GUNW interferometry).

Products are HDF5 files on a projected grid (UTM for Europe) with 512x512 chunks, so a small
window can be read from a local file or directly from the Earthdata HTTPS URL (only the needed
chunks are transferred). The same API is meant to be reused for ROSE-L L2 products, which are
expected to follow a similar layout (geocoded grids + coordinate vectors + projection EPSG).

Layers (frequency A, 20 MHz mode, 20 m posting):

- GCOV  ``/science/LSAR/GCOV/grids/frequencyA/{HHHH,HVHV}``: RTC gamma0 (linear power);
  ``rtcGammaToSigmaFactor`` converts to sigma0; ``numberOfLooks``, ``mask``.
- GUNW  ``.../wrappedInterferogram/HH/coherenceMagnitude`` (20 m);
  ``.../unwrappedInterferogram/HH/{coherenceMagnitude,unwrappedPhase,connectedComponents,
  ionospherePhaseScreen}`` (80 m).
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np
from affine import Affine

from .optical import Raster
from .search import parse_nisar_name

GCOV_GRID = "science/LSAR/GCOV/grids/frequencyA"
GUNW_GRID = "science/LSAR/GUNW/grids/frequencyA"

# short name -> (group relative to the product grid, dataset)
LAYERS = {
    "GCOV": {
        "HHHH": ("", "HHHH"), "HVHV": ("", "HVHV"),
        "gamma_to_sigma": ("", "rtcGammaToSigmaFactor"),
        "looks": ("", "numberOfLooks"), "mask": ("", "mask"),
    },
    "GUNW": {
        "coh20": ("wrappedInterferogram", "HH/coherenceMagnitude"),
        "coh80": ("unwrappedInterferogram", "HH/coherenceMagnitude"),
        "unw": ("unwrappedInterferogram", "HH/unwrappedPhase"),
        "conncomp": ("unwrappedInterferogram", "HH/connectedComponents"),
        "iono": ("unwrappedInterferogram", "HH/ionospherePhaseScreen"),
        "mask20": ("wrappedInterferogram", "mask"),
    },
}


@dataclass
class NisarInfo:
    """Acquisition metadata parsed from the granule name."""
    name: str
    product: str
    track: int
    direction: str
    frame: int
    ref_date: datetime
    sec_date: datetime | None = None

    @property
    def baseline_days(self) -> int | None:
        return None if self.sec_date is None else (self.sec_date - self.ref_date).days


def info_from_name(name: str) -> NisarInfo:
    p = parse_nisar_name(Path(name).name)
    return NisarInfo(Path(name).stem, p["product"], p["track"], p["direction"], p["frame"],
                     p["ref_date"], p.get("sec_date"))


@contextlib.contextmanager
def open_product(src: str | Path, fs=None, block_size: int = 2**20):
    """Open a NISAR HDF5 product from a local path or an HTTPS URL (``fs``: an authenticated
    fsspec filesystem, e.g. ``earthaccess.get_fsspec_https_session()``)."""
    if str(src).startswith("http"):
        if fs is None:
            import earthaccess
            earthaccess.login(strategy="netrc")
            fs = earthaccess.get_fsspec_https_session()
        fobj = fs.open(str(src), block_size=block_size, cache_type="blockcache")
        h5 = h5py.File(fobj, "r")
        try:
            yield h5
        finally:
            h5.close()
            fobj.close()
    else:
        with h5py.File(src, "r") as h5:
            yield h5


def _grid(h5: h5py.File, product: str, group: str) -> h5py.Group:
    root = GCOV_GRID if product == "GCOV" else GUNW_GRID
    return h5[f"{root}/{group}" if group else root]


def read_window(h5: h5py.File, product: str, layer: str,
                bounds: tuple[float, float, float, float]) -> Raster:
    """Read ``layer`` (key of :data:`LAYERS`) inside ``bounds`` = (xmin, ymin, xmax, ymax) in the
    product projection. Returns a :class:`Raster` (NaN outside valid data for float layers)."""
    group, dset = LAYERS[product][layer]
    g = _grid(h5, product, group)
    x, y = g["xCoordinates"][:], g["yCoordinates"][:]
    dx, dy = float(x[1] - x[0]), float(y[1] - y[0])  # dy < 0
    epsg = int(g["projection"][()])
    xmin, ymin, xmax, ymax = bounds
    j0 = max(int(np.floor((xmin - x[0]) / dx + 0.5)), 0)
    j1 = min(int(np.ceil((xmax - x[0]) / dx + 0.5)), len(x))
    i0 = max(int(np.floor((ymax - y[0]) / dy + 0.5)), 0)
    i1 = min(int(np.ceil((ymin - y[0]) / dy + 0.5)), len(y))
    if j1 <= j0 or i1 <= i0:
        raise ValueError(f"window {bounds} outside product grid")
    data = g[dset][i0:i1, j0:j1]
    if np.issubdtype(data.dtype, np.floating):
        data = data.astype("float32")
        data[data == 0] = np.nan  # 0 = no data in NISAR float layers
    # coordinates are pixel centres
    transform = Affine(dx, 0, x[j0] - dx / 2, 0, dy, y[i0] - dy / 2)
    return Raster(data, transform, f"EPSG:{epsg}")


def gcov_backscatter(h5: h5py.File, bounds, kind: str = "gamma0") -> dict[str, Raster]:
    """HH and HV backscatter in dB (``kind`` = ``gamma0`` RTC, or ``sigma0``)."""
    out = {}
    fac = read_window(h5, "GCOV", "gamma_to_sigma", bounds).data if kind == "sigma0" else 1.0
    for pol, term in (("HH", "HHHH"), ("HV", "HVHV")):
        r = read_window(h5, "GCOV", term, bounds)
        lin = r.data * fac
        with np.errstate(divide="ignore", invalid="ignore"):
            r.data = (10 * np.log10(np.where(lin > 0, lin, np.nan))).astype("float32")
        out[pol] = r
    return out
