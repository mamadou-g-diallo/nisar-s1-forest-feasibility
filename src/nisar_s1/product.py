"""Discovery-driven access to NISAR L2 geocoded products (GCOV, GSLC, GUNW).

Nothing about the product is hard-coded: frequencies, polarizations, covariance terms, grid,
projection and acquisition metadata are read from the HDF5 file itself, and the file name is only
used as a cross-check. The same functions work on a local file or on a remote file opened with
:func:`nisar_s1.io_nisar.open_product` (only the chunks that are read are transferred).

These helpers back the training notebooks in ``notebooks/`` and are meant to carry over to ROSE-L
L2 products, which are expected to follow the same layout (geocoded grids, coordinate vectors,
``projection`` EPSG code).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import h5py
import numpy as np
from affine import Affine

from .optical import Raster

PRODUCT_TYPES = ("GCOV", "GSLC", "GUNW", "GOFF")


def _txt(v) -> str:
    v = v[()] if isinstance(v, h5py.Dataset) else v
    if isinstance(v, bytes):
        return v.decode()
    if isinstance(v, np.ndarray):
        return ",".join(_txt(x) for x in v.ravel())
    return str(v)


def _list(v) -> list[str]:
    a = v[()]
    return [x.decode() if isinstance(x, bytes) else str(x) for x in np.atleast_1d(a)]


def find_science_root(h5: h5py.File) -> tuple[str, str, str]:
    """Return ``(band, product_type, root)``, e.g. ``("LSAR", "GCOV", "science/LSAR/GCOV")``,
    found by walking ``/science`` rather than assuming a band or a product type."""
    for band in h5["science"]:
        for ptype in h5[f"science/{band}"]:
            if ptype in PRODUCT_TYPES:
                return band, ptype, f"science/{band}/{ptype}"
    raise ValueError("no NISAR L2 geocoded product group found under /science")


@dataclass
class GridInfo:
    """One frequency grid of a geocoded product."""
    frequency: str
    path: str
    polarizations: list[str]
    terms: list[str]
    shape: tuple[int, int]
    epsg: int
    dx: float
    dy: float
    x0: float  # centre of the first column
    y0: float  # centre of the first row

    @property
    def transform(self) -> Affine:
        return Affine(self.dx, 0, self.x0 - self.dx / 2, 0, self.dy, self.y0 - self.dy / 2)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        ny, nx = self.shape
        xs = (self.x0 - self.dx / 2, self.x0 + self.dx * (nx - 0.5))
        ys = (self.y0 - self.dy / 2, self.y0 + self.dy * (ny - 0.5))
        return min(xs), min(ys), max(xs), max(ys)


@dataclass
class ProductProfile:
    """What a NISAR L2 file contains, read from the file itself."""
    granule: str
    band: str
    product_type: str
    root: str
    start: str
    stop: str
    orbit_direction: str
    look_direction: str
    track: int
    frame: int
    frequencies: list[str]
    grids: dict[str, GridInfo] = field(default_factory=dict)

    @property
    def polarimetric_mode(self) -> str:
        """Human-readable mode inferred from the polarizations (not from the file name)."""
        pols = set().union(*(set(g.polarizations) for g in self.grids.values())) if self.grids else set()
        if {"HH", "HV", "VH", "VV"} <= pols:
            return "quad-pol (full polarimetry)"
        if {"RH", "RV"} <= pols:
            return "compact-pol (circular transmit)"
        if len(pols) == 2:
            return f"dual-pol linear ({'/'.join(sorted(pols))})"
        if len(pols) == 1:
            return f"single-pol ({next(iter(pols))})"
        return "unknown"

    def complex_terms_available(self, frequency: str) -> bool:
        """True if the off-diagonal (complex) covariance terms are stored, e.g. ``HHHV``."""
        g = self.grids[frequency]
        return any(t[:2] != t[2:] for t in g.terms)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["polarimetric_mode"] = self.polarimetric_mode
        return d


def _grid_info(h5: h5py.File, path: str, frequency: str, ptype: str) -> GridInfo:
    g = h5[path]
    pols = _list(g["listOfPolarizations"]) if "listOfPolarizations" in g else \
        [k for k in g if len(k) == 2 and k.isupper()]
    if "listOfCovarianceTerms" in g:
        terms = _list(g["listOfCovarianceTerms"])
    elif ptype == "GSLC":
        terms = []  # complex images, the covariance is built by the user (see polarimetry.c2_from_slc)
    else:
        terms = [k for k in g if len(k) == 4 and k.isupper()]
    x, y = g["xCoordinates"], g["yCoordinates"]
    nx, ny = x.shape[0], y.shape[0]
    x0, x1 = float(x[0]), float(x[1])
    y0, y1 = float(y[0]), float(y[1])
    epsg = int(g["projection"][()]) if "projection" in g else int(h5[path.rsplit("/", 1)[0]]["projection"][()])
    return GridInfo(frequency, path, pols, terms, (ny, nx), epsg, x1 - x0, y1 - y0, x0, y0)


def _grid_path(h5: h5py.File, root: str, ptype: str, frequency: str) -> str:
    if ptype == "GUNW":
        return f"{root}/grids/{frequency}/wrappedInterferogram"
    return f"{root}/grids/{frequency}"


def product_profile(h5: h5py.File) -> ProductProfile:
    """Read the structure of a NISAR L2 product (see :class:`ProductProfile`)."""
    band, ptype, root = find_science_root(h5)
    ident = h5[f"science/{band}/identification"]
    get = lambda k, d="": _txt(ident[k]) if k in ident else d  # noqa: E731
    freqs = [f if f.startswith("frequency") else f"frequency{f}" for f in _list(ident["listOfFrequencies"])] \
        if "listOfFrequencies" in ident else sorted(k for k in h5[f"{root}/grids"] if k.startswith("frequency"))
    prof = ProductProfile(
        granule=get("granuleId"), band=band, product_type=ptype, root=root,
        start=get("zeroDopplerStartTime"), stop=get("zeroDopplerEndTime"),
        orbit_direction=get("orbitPassDirection"), look_direction=get("lookDirection"),
        track=int(get("trackNumber", "0") or 0), frame=int(get("frameNumber", "0") or 0),
        frequencies=freqs)
    for f in freqs:
        p = _grid_path(h5, root, ptype, f)
        if p in h5:
            prof.grids[f] = _grid_info(h5, p, f, ptype)
    return prof


def check_name_consistency(prof: ProductProfile, name: str) -> list[str]:
    """Compare the file name with the file content; return a list of mismatches (empty = OK)."""
    from .search import parse_nisar_name
    p = parse_nisar_name(Path(name).name)
    issues = []
    if p["product"] != prof.product_type:
        issues.append(f"product type: name {p['product']} vs file {prof.product_type}")
    if p["track"] != prof.track:
        issues.append(f"track: name {p['track']} vs file {prof.track}")
    if p["frame"] != prof.frame:
        issues.append(f"frame: name {p['frame']} vs file {prof.frame}")
    if p["direction"] != prof.orbit_direction[:1].upper():
        issues.append(f"direction: name {p['direction']} vs file {prof.orbit_direction}")
    return issues


def hdf5_tree(h5: h5py.File | h5py.Group, root: str = "/", max_depth: int = 4) -> list[dict]:
    """Flat listing of groups and datasets below ``root`` (metadata only, no pixel is read)."""
    rows = []
    base = h5[root]
    d0 = base.name.count("/") if base.name != "/" else 0

    def visit(name, obj):
        depth = obj.name.count("/") - d0
        if depth > max_depth:
            return
        if isinstance(obj, h5py.Dataset):
            rows.append({"path": obj.name, "kind": "dataset", "shape": obj.shape, "dtype": str(obj.dtype),
                         "chunks": obj.chunks, "units": _txt(obj.attrs.get("units", b""))})
        else:
            rows.append({"path": obj.name, "kind": "group", "shape": None, "dtype": "", "chunks": None,
                         "units": ""})
    base.visititems(visit)
    return rows


def dataset_info(dset: h5py.Dataset) -> dict:
    """Size, chunking, compression and attributes of a dataset, without reading its pixels."""
    nbytes = int(np.prod(dset.shape)) * dset.dtype.itemsize
    return {"path": dset.name, "shape": dset.shape, "dtype": str(dset.dtype), "chunks": dset.chunks,
            "compression": dset.compression, "size_GB_uncompressed": nbytes / 2**30,
            "attrs": {k: _txt(v) for k, v in dset.attrs.items() if k not in ("DIMENSION_LIST",)}}


def footprint_lonlat(h5: h5py.File):
    """Product footprint (shapely polygon, lon/lat) from ``identification/boundingPolygon``."""
    from shapely import wkt
    band, _, _ = find_science_root(h5)
    return wkt.loads(_txt(h5[f"science/{band}/identification/boundingPolygon"]).replace("POLYGON Z", "POLYGON"))


def lonlat_to_proj(bbox_wgs84, epsg: int) -> tuple[float, float, float, float]:
    """(lon_min, lat_min, lon_max, lat_max) -> bounds in the product projection (all 4 corners)."""
    from pyproj import Transformer
    t = Transformer.from_crs(4326, epsg, always_xy=True)
    lo0, la0, lo1, la1 = bbox_wgs84
    xs, ys = t.transform([lo0, lo1, lo0, lo1], [la0, la0, la1, la1])
    return min(xs), min(ys), max(xs), max(ys)


@dataclass
class Window:
    """Row/column window of a grid, with its georeferencing."""
    rows: slice
    cols: slice
    transform: Affine
    crs: str

    @property
    def shape(self) -> tuple[int, int]:
        return self.rows.stop - self.rows.start, self.cols.stop - self.cols.start

    def to_dict(self) -> dict:
        return {"rows": [self.rows.start, self.rows.stop], "cols": [self.cols.start, self.cols.stop],
                "transform": list(self.transform)[:6], "crs": self.crs}


def window_from_bounds(grid: GridInfo, bounds) -> Window:
    """Window of ``grid`` covering ``bounds`` (xmin, ymin, xmax, ymax) in the grid projection.
    Raises ``ValueError`` if the AOI does not overlap the grid."""
    xmin, ymin, xmax, ymax = bounds
    gx0, gy0, gx1, gy1 = grid.bounds
    if xmax <= gx0 or xmin >= gx1 or ymax <= gy0 or ymin >= gy1:
        raise ValueError(f"AOI {bounds} does not overlap the product grid {grid.bounds}")
    j0 = max(int(np.floor((xmin - grid.x0) / grid.dx + 0.5)), 0)
    j1 = min(int(np.ceil((xmax - grid.x0) / grid.dx + 0.5)), grid.shape[1])
    i0 = max(int(np.floor((ymax - grid.y0) / grid.dy + 0.5)), 0)
    i1 = min(int(np.ceil((ymin - grid.y0) / grid.dy + 0.5)), grid.shape[0])
    tr = Affine(grid.dx, 0, grid.x0 + grid.dx * (j0 - 0.5), 0, grid.dy, grid.y0 + grid.dy * (i0 - 0.5))
    return Window(slice(i0, i1), slice(j0, j1), tr, f"EPSG:{grid.epsg}")


def read_layer(h5: h5py.File, grid: GridInfo, layer: str, win: Window, nodata_zero: bool = True,
               max_gb: float = 1.0) -> np.ndarray:
    """Read ``layer`` (e.g. ``HHHH``, ``HV``, ``mask``) of ``grid`` inside ``win``.

    ``max_gb`` is a memory guard: the read is refused if the window would exceed it. Float layers
    are returned with 0 replaced by NaN (0 = no data in NISAR float layers)."""
    d = h5[f"{grid.path}/{layer}"]
    need = win.shape[0] * win.shape[1] * d.dtype.itemsize / 2**30
    if need > max_gb:
        raise MemoryError(f"window needs {need:.2f} GB > max_gb={max_gb}; shrink the AOI or raise max_gb")
    a = d[win.rows, win.cols]
    if nodata_zero and np.issubdtype(a.dtype, np.floating):
        a = a.astype("float32")
        a[a == 0] = np.nan
    elif nodata_zero and np.issubdtype(a.dtype, np.complexfloating):
        a = a.astype("complex64")
        a[a == 0] = np.nan
    return a


def read_raster(h5: h5py.File, grid: GridInfo, layer: str, win: Window, **kw) -> Raster:
    """:func:`read_layer` wrapped in a :class:`~nisar_s1.optical.Raster` (ready for GeoTIFF export)."""
    return Raster(read_layer(h5, grid, layer, win, **kw), win.transform, win.crs)


def block_iter(win: Window, block: int = 1024):
    """Yield sub-windows of ``win`` of at most ``block`` x ``block`` pixels (tile-wise processing)."""
    for i in range(win.rows.start, win.rows.stop, block):
        for j in range(win.cols.start, win.cols.stop, block):
            rs, cs = slice(i, min(i + block, win.rows.stop)), slice(j, min(j + block, win.cols.stop))
            yield Window(rs, cs, win.transform @ Affine.translation(j - win.cols.start, i - win.rows.start), win.crs)


# --- persistent session -------------------------------------------------------------------------

def save_session(path, **values) -> dict:
    """Merge ``values`` into the JSON session file ``path`` (created if needed) and return it."""
    path = Path(path)
    s = load_session(path) if path.exists() else {}
    s.update(values)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(s, indent=2, default=str))
    return s


def load_session(path, required: tuple[str, ...] = ()) -> dict:
    """Read the session file; raise a clear error naming the notebook to run if a key is missing."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"no session file {path}: run notebook 01 first")
    s = json.loads(path.read_text())
    missing = [k for k in required if k not in s]
    if missing:
        raise KeyError(f"session file is missing {missing}: run the earlier notebooks first")
    return s


def write_subset(h5: h5py.File, prof: ProductProfile, win: Window, dst, frequency: str = "frequencyA",
                 layers: tuple[str, ...] | None = None) -> Path:
    """Save the ``win`` window of ``frequency`` to a small HDF5 file with the same NISAR layout
    (identification group copied, grid group with cropped coordinates), so that every function of
    this module works on the subset exactly as on the full product. Used to keep a local AOI
    extract of large remote products (a full GSLC is ~13 GB, a 6 km AOI is a few tens of MB).

    ``layers`` defaults to the polarizations (GSLC) or covariance terms (GCOV) plus ``mask``."""
    dst = Path(dst)
    g = prof.grids[frequency]
    layers = layers or tuple((g.terms or g.polarizations) + ["mask"])
    tmp = dst.with_suffix(".part")
    with h5py.File(tmp, "w") as out:
        ident = f"science/{prof.band}/identification"
        h5.copy(h5[ident], out.require_group(f"science/{prof.band}"), name="identification")
        del out[ident]["listOfFrequencies"]
        out[ident]["listOfFrequencies"] = np.array([frequency.replace("frequency", "").encode()])
        og = out.create_group(g.path)
        src = h5[g.path]
        for k in ("listOfPolarizations", "listOfCovarianceTerms", "projection"):
            if k in src:
                og[k] = src[k][()]
        if "projection" not in og:
            og["projection"] = np.uint32(g.epsg)
        og["xCoordinates"] = src["xCoordinates"][win.cols]
        og["yCoordinates"] = src["yCoordinates"][win.rows]
        for i, lay in enumerate(layers, 1):
            print(f"[{i}/{len(layers)}] {lay} {win.shape}", flush=True)
            a = src[lay][win.rows, win.cols]
            og.create_dataset(lay, data=a, chunks=True, compression="gzip", compression_opts=4)
        og.attrs["subset_of"] = prof.granule
        og.attrs["subset_rows"] = [win.rows.start, win.rows.stop]
        og.attrs["subset_cols"] = [win.cols.start, win.cols.stop]
    tmp.rename(dst)
    return dst


def open_local_or_remote(local, url, fs=None):
    """Open ``local`` if it exists, otherwise stream ``url`` from ASF (Earthdata login via
    ``~/.netrc``). Returns the context manager of :func:`nisar_s1.io_nisar.open_product`."""
    from .io_nisar import open_product
    src = local if local and Path(local).exists() else url
    print(f"opening {'local file' if src == local else 'remote file (HTTPS range requests)'}: {Path(str(src)).name}")
    return open_product(src, fs=fs)
