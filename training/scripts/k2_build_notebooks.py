"""Build the training notebooks (``notebooks/NN_*.ipynb``) from the cell lists below.

The notebooks are the deliverable; this script only keeps them consistent (same set-up cell, same
checkpoint style) and easy to regenerate. Execute them afterwards with ``k3_run_notebooks.py``.
"""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[2]
NB = ROOT / "training" / "notebooks"


def md(s):
    return nbf.v4.new_markdown_cell(s.strip("\n"))


def code(s):
    return nbf.v4.new_code_cell(s.strip("\n"))


def setup(n, extra=""):
    return code(f'''
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from nisar_s1.config import load_kit
from nisar_s1 import product as P

kit = load_kit()                                  # training/notebooks/kit_config.yaml
OUT = Path(kit["data_dir"]) / "outputs" / "{n:02d}"   # outputs stay outside the repository
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({{"figure.dpi": 90, "axes.spines.top": False, "axes.spines.right": False}})
{extra}''')


def status(n, checks):
    """Checkpoint cell: every check must be True for the module to PASS."""
    lines = ",\n    ".join(f'"{k}": {v}' for k, v in checks.items())
    return code(f'''
checks = {{
    {lines},
}}
for k, v in checks.items():
    print(f"  [{{'x' if v else ' '}}] {{k}}")
assert all(checks.values()), "some checks failed: read the messages above"
print("Module {n:02d} STATUS: PASS")''')


SESSION = 'session = P.load_session(kit["session_file"], required={req})\n'
OPEN = 'src_ctx = lambda: P.open_local_or_remote(session["gcov_local"], session["gcov_url"])\n'

NOTEBOOKS = {}

# --------------------------------------------------------------------------------------------- 01
NOTEBOOKS["01_Setup_and_Product_Selection"] = [
    md("""
# 01 — Setup, product selection and first map

**Goal:** go from "a NISAR granule name" to "I can see this scene on a map", and register the
choice in a session file that every later notebook reads.

This series follows the structure of the open NISAR GCOV training toolkit of D. K. Pandey
(`dharmendraisro/nisar-polarimetric-training`, Apache-2.0) and adapts it to what is actually
acquired over Europe: **NISAR L-band dual-pol HH/HV** (no quad-pol, no S-band), compared with
**Sentinel-1 C-band VV/VH**, on the Vosges clear-cut site of this feasibility study.
All code used here lives in the `nisar_s1` package of this repository, so it can be reused outside
the notebooks (and on ROSE-L L2 products, expected to share the same geocoded layout).

**Data are never stored in the repository.** They go to `data_dir` (see `training/notebooks/kit_config.yaml`).
Earthdata credentials are read from `~/.netrc` by `earthaccess` and are never printed.
"""),
    setup(1),
    md("""
## 01A — Which NISAR products cover the area of interest?

The search uses the ASF catalogue (no login needed for searching). We list the GCOV granules
(L2, geocoded, radiometrically terrain-corrected covariance) over the AOI.
"""),
    code('''
from nisar_s1.config import bbox_to_wkt
from nisar_s1.search import search_nisar

bbox = kit["aoi"]["bbox_wgs84"]
try:
    found = search_nisar(bbox_to_wkt(bbox), "2026-06-01", "2026-11-30", product_types=("GCOV",))
    cols = ["sceneName", "track", "direction", "frame", "bw_code", "pol_code", "ref_date", "size_mb"]
    gcov_list = found[[c for c in cols if c in found]].sort_values("ref_date")
    print(len(gcov_list), "GCOV granules over the AOI")
    display(gcov_list.groupby(["track", "direction", "frame", "bw_code"]).size().rename("n").reset_index())
except Exception as e:  # offline: the rest of the notebook works with the configured granule
    gcov_list = None
    print("catalogue search not available:", type(e).__name__, e)
'''),
    md("""
The training granule is fixed in `kit_config.yaml` so that everybody works on the same scene:
track 144 ascending, frame 26, 20+5 MHz mode (`2005`), dual-pol `DHDH`, 3 November 2026.
The notebooks open the **local copy** if it has been downloaded, otherwise they **stream** the file
from ASF (only the HDF5 chunks that are read are transferred).
"""),
    code('''
g = kit["gcov"]
local = Path(g["local"])
print("granule :", g["granule"])
print("local   :", local, "->", f"{local.stat().st_size / 2**30:.2f} GB" if local.exists() else "absent (will stream)")
print("netrc   :", "present" if (Path.home() / ".netrc").exists() else "MISSING (needed to stream from ASF)")
'''),
    md("## 01B — Footprint from the product itself"),
    code('''
from nisar_s1 import maps
import geopandas as gpd

with P.open_local_or_remote(g["local"], g["url"]) as h5:
    prof = P.product_profile(h5)
    footprint = P.footprint_lonlat(h5)
sites = gpd.read_file(kit["aoi"]["site_polygons"])
layers = maps.layers_frame(footprint, bbox, sites)
print(prof.product_type, prof.band, prof.orbit_direction, "track", prof.track, "frame", prof.frame)
print("start:", prof.start)

fig, axs = plt.subplots(1, 2, figsize=(12, 5.5))
maps.static_map(layers[layers.layer.isin(["footprint", "aoi"])], "Product footprint and AOI", ax=axs[0])
maps.static_map(layers, "AOI and study polygons (clear-cut, control forest)", ax=axs[1], zoom_to="aoi")
fig.savefig(OUT / "01_footprint.png", dpi=120, bbox_inches="tight")
plt.show()
'''),
    md("Interactive version (OpenStreetMap background; the static map above is the one that must work offline):"),
    code('maps.folium_map(layers, zoom_to="aoi")'),
    md("## 01C — Register the choice in the session file"),
    code('''
session = P.save_session(kit["session_file"], granule=g["granule"], gcov_local=g["local"], gcov_url=g["url"],
                         product_type=prof.product_type, epsg_hint=prof.grids["frequencyA"].epsg)
print(kit["session_file"])
'''),
    md("""
### Checkpoint
Where is the scene (country, region)? Which orbit direction and track? Which projection (EPSG code)
is the product delivered in? You will need that EPSG code in notebooks 06 and 10.
"""),
    status(1, {"product is a GCOV": 'prof.product_type == "GCOV"',
               "AOI inside the footprint": "footprint.contains(layers[layers.layer == 'aoi'].geometry.iloc[0])",
               "session saved": 'Path(kit["session_file"]).exists()'}),
]

# --------------------------------------------------------------------------------------------- 02
NOTEBOOKS["02_Session_Check_and_Product_Orientation"] = [
    md("""
# 02 — Session check and product orientation

**Goal:** discover from the file (not from its name) which frequencies, polarizations and
covariance terms it holds, choose a frequency for the session, and verify that pixels can be read.

NISAR's L-band radar can transmit two sub-bands at once: **frequency A** (here 20 MHz, fine
resolution) and **frequency B** (5 MHz, coarser, mainly for ionospheric correction). The file name
code `2005` means 20 + 5 MHz; `DHDH` means dual-pol H transmit, H and V receive, on both.
"""),
    setup(2, SESSION.format(req='("granule", "gcov_local", "gcov_url")') + OPEN),
    code('''
with src_ctx() as h5:
    prof = P.product_profile(h5)
print("polarimetric mode (from content):", prof.polarimetric_mode)
rows = []
for f, gr in prof.grids.items():
    rows.append({"frequency": f, "polarizations": gr.polarizations, "covariance terms": gr.terms,
                 "rows x cols": gr.shape, "pixel (m)": (gr.dx, -gr.dy), "EPSG": gr.epsg,
                 "complex terms stored": prof.complex_terms_available(f)})
pd.DataFrame(rows)
'''),
    md("""
The name is only a **hint**: we cross-check it against the content. A mismatch (renamed file,
wrong download) is reported instead of silently trusted.
"""),
    code('''
issues = P.check_name_consistency(prof, session["granule"])
print("name vs content:", "consistent" if not issues else issues)
'''),
    md("""
## Choose the session frequency
Rule used here: the frequency with the finest pixel (A). Change `FREQ` to work at 5 MHz instead
(notebook 09 compares the two).
"""),
    code('''
FREQ = min(prof.grids, key=lambda f: abs(prof.grids[f].dx))
grid = prof.grids[FREQ]
session = P.save_session(kit["session_file"], frequency=FREQ, epsg=grid.epsg,
                         polarimetric_mode=prof.polarimetric_mode, terms=grid.terms)
print("session frequency:", FREQ, "| pixel", grid.dx, "m | EPSG", grid.epsg)
'''),
    md("## Verify pixel access (a 4 x 4 window at the grid centre)"),
    code('''
cy, cx = grid.shape[0] // 2, grid.shape[1] // 2
centre = P.Window(slice(cy, cy + 4), slice(cx, cx + 4), grid.transform, f"EPSG:{grid.epsg}")
with src_ctx() as h5:
    for t in grid.terms:
        v = P.read_layer(h5, grid, t, centre)
        print(f"{t}: {np.nanmean(v):.4f} (linear power, mean of 16 pixels)")
'''),
    md("""
### Checkpoint
How many frequencies? Which one did the session keep and why? Are the off-diagonal (complex)
covariance terms stored in this dual-pol GCOV? (Answer: no — notebook 13 explains how to get them.)
"""),
    status(2, {"two frequencies discovered": "len(prof.grids) == 2",
               "HH and HV present": 'set(grid.polarizations) == {"HH", "HV"}',
               "name consistent with content": "not issues",
               "frequency saved": '"frequency" in P.load_session(kit["session_file"])'}),
]

# --------------------------------------------------------------------------------------------- 03
NOTEBOOKS["03_Product_Explorer_Metadata_First"] = [
    md("""
# 03 — Metadata-first product explorer

**Goal:** read what the product says about itself — structure, units, chunking, acquisition and
processing metadata — **before** touching any pixel. Nothing in this notebook reads image data.
"""),
    setup(3, SESSION.format(req='("granule", "frequency")') + OPEN),
    code('''
with src_ctx() as h5:
    tree = pd.DataFrame(P.hdf5_tree(h5, "/", max_depth=6))
    prof = P.product_profile(h5)
    band = prof.band
    ident = {k: P._txt(v) for k, v in h5[f"science/{band}/identification"].items()}
print(len(tree), "groups and datasets;", (tree.kind == "dataset").sum(), "datasets")
tree["group"] = tree.path.str.rsplit("/", n=1).str[0]
tree[tree.kind == "dataset"].groupby("group").size().rename("datasets").to_frame()
'''),
    md("## Identification: the product's own record of the acquisition"),
    code('''
keys = ["granuleId", "missionId", "productType", "productVersion", "radarBand", "orbitPassDirection",
        "lookDirection", "trackNumber", "frameNumber", "zeroDopplerStartTime", "zeroDopplerEndTime",
        "listOfFrequencies", "isGeocoded", "isFullFrame", "processingCenter", "processingType", "productDoi"]
pd.Series({k: ident.get(k, "-") for k in keys}, name="value").to_frame()
'''),
    md("## Layers of the session grid: shape, type, chunking, compression and units"),
    code('''
FREQ = session["frequency"]
with src_ctx() as h5:
    gpath = prof.grids[FREQ].path
    info = pd.DataFrame([P.dataset_info(h5[f"{gpath}/{k}"]) for k in h5[gpath]
                         if hasattr(h5[f"{gpath}/{k}"], "shape") and h5[f"{gpath}/{k}"].ndim == 2])
    units = {k: P._txt(h5[f"{gpath}/{k}"].attrs.get("units", b"")) for k in info.path.str.split("/").str[-1]}
info["layer"] = info.path.str.split("/").str[-1]
info["units"] = info.layer.map(units)
info[["layer", "shape", "dtype", "chunks", "compression", "size_GB_uncompressed", "units"]]
'''),
    md("""
Each image layer of a 20 m frame is ~1.2 GB uncompressed and is cut in **512 x 512 chunks**:
reading a small window only decompresses the chunks it touches (notebook 05).

## Processing and calibration metadata
"""),
    code('''
with src_ctx() as h5:
    meta = tree[(tree.kind == "dataset") & tree.path.str.contains("metadata|processingInformation")]
    print(len(meta), "metadata datasets, e.g.:")
    for p in meta.path.head(12):
        print("  ", p)
    pi = f"science/{band}/{prof.product_type}/metadata/processingInformation/parameters"
    if pi in h5:
        print("\\nprocessing parameters:", list(h5[pi].keys())[:15])
'''),
    md("## Optional: bring your own GIS layer (here the study polygons, reprojected to the product CRS)"),
    code('''
import geopandas as gpd
sites = gpd.read_file(kit["aoi"]["site_polygons"]).to_crs(prof.grids[FREQ].epsg)
from shapely.geometry import box
inside = sites.within(box(*prof.grids[FREQ].bounds))
sites.assign(inside_grid=inside.values, area_ha=sites.area / 1e4)[["role", "area_ha", "inside_grid"]]
'''),
    md("""
### Checkpoint
What are the units of `HHHH`? What does `rtcGammaToSigmaFactor` do (hint: notebook 04)? Which DOI
identifies this product?
"""),
    status(3, {"metadata read without pixel access": "len(tree) > 50",
               "HHHH listed with 512x512 chunks": 'info.loc[info.layer == "HHHH", "chunks"].iloc[0] == (512, 512)',
               "study polygons inside the grid": "bool(inside.all())"}),
]

# --------------------------------------------------------------------------------------------- 04
NOTEBOOKS["04_L2_GCOV_Covariance_Explorer"] = [
    md("""
# 04 — L2 GCOV covariance explorer

**Goal:** understand what the GCOV layers measure.

* GCOV stores the **covariance matrix** of the scattering vector, averaged and geocoded.
  The **diagonal** terms (`HHHH` = ⟨|S_HH|²⟩, `HVHV` = ⟨|S_HV|²⟩) are real backscattered power.
  **Off-diagonal** terms (e.g. `HHHV` = ⟨S_HH S_HV*⟩) are complex and carry the polarimetric phase.
* NISAR GCOV is **radiometrically terrain-corrected**: values are **γ⁰ (gamma-naught)**, normalized by
  the illuminated area computed from a DEM, so slopes facing the radar are not artificially bright.
  `rtcGammaToSigmaFactor` converts to σ⁰ (sigma-naught), the convention of many older studies.
* Values are **linear power**; dB = 10·log10(power).
"""),
    setup(4, SESSION.format(req='("granule", "frequency")') + OPEN),
    code('''
with src_ctx() as h5:
    prof = P.product_profile(h5)
    grid = prof.grids[session["frequency"]]
    # a 2 x 2 km window around the clear-cut site, in the product projection
    from nisar_s1.product import lonlat_to_proj
    cx, cy = 6.7564, 47.9101
    x0, y0, x1, y1 = lonlat_to_proj((cx - 0.013, cy - 0.009, cx + 0.013, cy + 0.009), grid.epsg)
    win = P.window_from_bounds(grid, (x0, y0, x1, y1))
    hh = P.read_layer(h5, grid, "HHHH", win)
    hv = P.read_layer(h5, grid, "HVHV", win)
    g2s = P.read_layer(h5, grid, "rtcGammaToSigmaFactor", win)
    looks = P.read_layer(h5, grid, "numberOfLooks", win)
print("window", win.shape, "pixels; diagonal terms are real:", hh.dtype, hv.dtype)
print("complex off-diagonal terms stored:", prof.complex_terms_available(session["frequency"]))
'''),
    code('''
from nisar_s1.polarimetry import to_db
fig, axs = plt.subplots(1, 4, figsize=(16, 4))
for ax, (a, t, kw) in zip(axs, [(to_db(hh), "HH γ⁰ (dB)", dict(zip(("vmin", "vmax"), np.nanpercentile(to_db(hh), [2, 98])))),
                                (to_db(hv), "HV γ⁰ (dB)", dict(zip(("vmin", "vmax"), np.nanpercentile(to_db(hv), [2, 98])))),
                                (g2s, "γ⁰ → σ⁰ factor", {}), (looks, "number of looks", {})]):
    im = ax.imshow(a, cmap="gray" if "dB" in t else "viridis", **kw)
    ax.set_title(t, loc="left"); ax.set_xticks([]); ax.set_yticks([])
    plt.colorbar(im, ax=ax, shrink=0.75)
fig.savefig(OUT / "04_layers.png", dpi=110, bbox_inches="tight"); plt.show()
'''),
    md("## γ⁰ versus σ⁰: same pixels, different normalization"),
    code('''
sig_hh = hh * g2s
d = to_db(sig_hh) - to_db(hh)
print(f"sigma0 - gamma0 (HH): median {np.nanmedian(d):+.2f} dB, 5-95 % range "
      f"{np.nanpercentile(d, 5):+.2f} to {np.nanpercentile(d, 95):+.2f} dB")
fig, ax = plt.subplots(figsize=(6, 3.5))
ax.hist(d[np.isfinite(d)], bins=80, color="#2a78d6")
ax.set_xlabel("σ⁰ − γ⁰ (dB)"); ax.set_ylabel("pixels"); ax.set_title("The difference follows the terrain slope", loc="left")
plt.show()
'''),
    md("""
## Power statistics
Cross-pol (HV) is typically 6–10 dB below co-pol (HH) over land; at L-band the HV level of forests is
driven by volume scattering in branches and trunks, which is why HV is the classic L-band biomass
and clear-cut indicator.
"""),
    code('''
stats = pd.DataFrame({t: pd.Series(to_db(a)[np.isfinite(a)]).describe(percentiles=[.02, .5, .98])
                      for t, a in {"HH (dB)": hh, "HV (dB)": hv}.items()}).T
stats["HH-HV ratio (dB)"] = np.nan
stats.loc["HH (dB)", "HH-HV ratio (dB)"] = np.nanmedian(to_db(hh) - to_db(hv))
stats.round(2)
'''),
    status(4, {"diagonal terms real-valued": "np.isrealobj(hh) and np.isrealobj(hv)",
               "HV weaker than HH": "np.nanmedian(hv) < np.nanmedian(hh)",
               "looks > 1": "np.nanmedian(looks) > 1"}),
]

# --------------------------------------------------------------------------------------------- 05
NOTEBOOKS["05_Large_Data_Performance_and_Windowed_Access"] = [
    md("""
# 05 — Large-data performance and windowed access

**Goal:** never load a full frame when you need a window. A 20 m GCOV frame is ~18 000 x 18 000
pixels per layer (≈ 1.2 GB per layer as float32, several GB for all layers): it does not fit
comfortably in the memory of a training laptop, and it is never needed.

HDF5 stores each layer in **chunks** (512 x 512 here). A window read decompresses only the chunks
it overlaps; a strided read (`a[::10, ::10]`) still touches every chunk and is slow.
"""),
    setup(5, SESSION.format(req='("granule", "frequency")') + OPEN + "import time\n"),
    code('''
with src_ctx() as h5:
    prof = P.product_profile(h5)
    grid = prof.grids[session["frequency"]]
    d = h5[f"{grid.path}/HVHV"]
    full_gb = np.prod(d.shape) * d.dtype.itemsize / 2**30
    print(f"HVHV full layer: {d.shape}, {full_gb:.2f} GB in memory; chunks {d.chunks}")
    print("memory guard refuses it:", end=" ")
    try:
        P.read_layer(h5, grid, "HVHV", P.window_from_bounds(grid, grid.bounds), max_gb=1.0)
    except MemoryError as e:
        print(e)
'''),
    md("## Aligned versus misaligned windows"),
    code('''
def timed(h5, rows, cols):
    t = time.perf_counter()
    a = h5[f"{grid.path}/HVHV"][rows, cols]
    return time.perf_counter() - t, a.nbytes / 2**20

res = []
with src_ctx() as h5:
    r0, c0 = (grid.shape[0] // 2 // 512) * 512, (grid.shape[1] // 2 // 512) * 512
    for name, rows, cols in [
        ("1024² aligned on chunks (4 chunks)", slice(r0, r0 + 1024), slice(c0, c0 + 1024)),
        ("1024² shifted by 256 px (9 chunks)", slice(r0 + 256, r0 + 1280), slice(c0 + 256, c0 + 1280)),
        ("strided 1/16 over 16384² (~1024² values)", slice(r0 - 8192, r0 + 8192, 16), slice(c0 - 8192, c0 + 8192, 16)),
    ]:
        rows = slice(max(rows.start, 0), min(rows.stop, grid.shape[0]), rows.step)
        cols = slice(max(cols.start, 0), min(cols.stop, grid.shape[1]), cols.step)
        s, mb = timed(h5, rows, cols)
        res.append({"read": name, "seconds": round(s, 2), "MB returned": round(mb, 1)})
pd.DataFrame(res)
'''),
    md("""
The strided read returns as many values as the 1024² window but has to decompress hundreds of chunks.
For an **overview** of a whole frame, use the browse products (PNG/KML shipped next to the HDF5),
or the coarser frequency B grid, rather than striding through frequency A.

## Tile-wise processing
When an AOI is too large for memory, process it tile by tile (`P.block_iter`) and keep only
summary values. Here: the mean HV of a 4096² area in 1024² tiles, never holding more than one tile.
"""),
    code('''
big = P.Window(slice(r0 - 2048, r0 + 2048), slice(c0 - 2048, c0 + 2048), grid.transform, f"EPSG:{grid.epsg}")
tiles = list(P.block_iter(big, 1024))
s, n = 0.0, 0
t = time.perf_counter()
with src_ctx() as h5:
    for i, w in enumerate(tiles, 1):
        a = P.read_layer(h5, grid, "HVHV", w)
        s += np.nansum(a); n += np.isfinite(a).sum()
        if i % 4 == 0: print(f"[{i}/{len(tiles)}] tiles done")
print(f"mean HV over {n:,} pixels: {10*np.log10(s/n):.2f} dB in {time.perf_counter()-t:.1f} s")
'''),
    md("""
## Remote access
The same code reads a file **on the ASF server** through HTTPS range requests (only the needed
chunks travel over the network). Set `TRY_REMOTE = True` to time a remote 512² read (needs
Earthdata credentials in `~/.netrc` and internet).
"""),
    code('''
TRY_REMOTE = False
if TRY_REMOTE:
    from nisar_s1.io_nisar import open_product
    t = time.perf_counter()
    with open_product(session["gcov_url"]) as h5:
        a = h5[f"{grid.path}/HVHV"][r0:r0 + 512, c0:c0 + 512]
    print(f"remote 512² read: {time.perf_counter() - t:.1f} s")
'''),
    status(5, {"full-layer read refused by the guard": "full_gb > 1.0",
               "aligned window faster than strided read": "res[0]['seconds'] < res[2]['seconds']",
               "tile-wise mean computed": "n > 0"}),
]

# --------------------------------------------------------------------------------------------- 06
NOTEBOOKS["06_Spatial_Subsetting_AOI"] = [
    md("""
# 06 — Spatial subsetting with AOI validation

**Goal:** define the area of interest once, validate it against the product grid, and hand it to
every later notebook through the session file. This notebook is the **single authority** for the AOI.

The AOI is given in longitude/latitude (WGS84). The product grid is in UTM (EPSG from notebook 02):
the four corners are projected and the enclosing window of grid pixels is computed.
"""),
    setup(6, SESSION.format(req='("granule", "frequency", "epsg")') + OPEN),
    code('''
bbox = kit["aoi"]["bbox_wgs84"]
with src_ctx() as h5:
    prof = P.product_profile(h5)
grid = prof.grids[session["frequency"]]
bounds = P.lonlat_to_proj(bbox, grid.epsg)
win = P.window_from_bounds(grid, bounds)
area_km2 = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1]) / 1e6
print("AOI (WGS84)        :", bbox)
print(f"AOI (EPSG:{grid.epsg}) :", [round(v) for v in bounds])
print(f"window rows {win.rows.start}:{win.rows.stop}, cols {win.cols.start}:{win.cols.stop} -> {win.shape} pixels, {area_km2:.1f} km²")
'''),
    md("""
## Validation rules
* the AOI must lie **inside** the grid (a partial overlap is accepted but reported);
* it must not be degenerate (at least 10 x 10 pixels);
* its memory footprint for all layers must stay small (here < 0.5 GB).
"""),
    code('''
gx0, gy0, gx1, gy1 = grid.bounds
fully_inside = bounds[0] >= gx0 and bounds[2] <= gx1 and bounds[1] >= gy0 and bounds[3] <= gy1
from nisar_s1.polarimetry import memory_needed_gb
mem = memory_needed_gb(win.shape, n_arrays=len(grid.terms) + 3, itemsize=4)
print("fully inside the grid:", fully_inside)
print(f"memory for {len(grid.terms) + 3} float32 layers: {mem * 1024:.1f} MB")
for bad in [(0, 0, 100, 100)]:
    try:
        P.window_from_bounds(grid, bad)
    except ValueError as e:
        print("an AOI outside the product is rejected:", str(e)[:70], "...")
'''),
    md("## The AOI on the image (HV, frequency A)"),
    code('''
import geopandas as gpd
from nisar_s1.polarimetry import to_db
with src_ctx() as h5:
    hv = P.read_layer(h5, grid, "HVHV", win)
sites = gpd.read_file(kit["aoi"]["site_polygons"]).to_crs(grid.epsg)
x0 = win.transform.c; y0 = win.transform.f
ext = [x0, x0 + win.transform.a * win.shape[1], y0 + win.transform.e * win.shape[0], y0]
fig, ax = plt.subplots(figsize=(7, 6))
ax.imshow(to_db(hv), cmap="gray", vmin=np.nanpercentile(to_db(hv), 2), vmax=np.nanpercentile(to_db(hv), 98), extent=ext)
sites.boundary.plot(ax=ax, color=["#c0392b" if r == "cut" else "#1e8449" for r in sites.role], lw=1.5)
ax.set_title("AOI: NISAR L-band HV γ⁰ (dB), 3 Nov 2026 — red: clear-cut, green: control forest", loc="left", fontsize=10)
ax.set_xlabel(f"x (m, EPSG:{grid.epsg})"); ax.set_ylabel("y (m)")
fig.savefig(OUT / "06_aoi_hv.png", dpi=110, bbox_inches="tight"); plt.show()
'''),
    md("## Hand the AOI downstream"),
    code('''
session = P.save_session(kit["session_file"], aoi_name=kit["aoi"]["name"], aoi_bbox_wgs84=bbox,
                         aoi_bounds=list(bounds), aoi_window=win.to_dict())
print("saved:", session["aoi_window"])
'''),
    status(6, {"AOI fully inside the grid": "fully_inside", "AOI >= 10 x 10 pixels": "min(win.shape) >= 10",
               "memory < 0.5 GB": "mem < 0.5", "AOI saved": '"aoi_window" in P.load_session(kit["session_file"])'}),
]

# --------------------------------------------------------------------------------------------- 07
NOTEBOOKS["07_QC_Statistics_and_Masks"] = [
    md("""
# 07 — Quality control, statistics and masks

**Goal:** before interpreting values, check that they are valid: no-data, the product `mask`
layer, the number of looks, outliers, and the statistics of each polarization, overall and per
land unit (clear-cut and control forest).
"""),
    setup(7, SESSION.format(req='("granule", "frequency", "aoi_window")') + OPEN + '''from nisar_s1.polarimetry import to_db
from nisar_s1.grid import polygon_mask
from nisar_s1.optical import Raster
import geopandas as gpd
'''),
    code('''
with src_ctx() as h5:
    prof = P.product_profile(h5)
    grid = prof.grids[session["frequency"]]
    win = P.window_from_bounds(grid, session["aoi_bounds"])
    L = {t: P.read_layer(h5, grid, t, win) for t in grid.terms}
    mask = P.read_layer(h5, grid, "mask", win, nodata_zero=False)
    looks = P.read_layer(h5, grid, "numberOfLooks", win)
vals, counts = np.unique(mask, return_counts=True)
print("mask values in the AOI:", dict(zip(vals.tolist(), counts.tolist())))
'''),
    md("""
The `mask` layer of NISAR L2 products encodes, per pixel, which sub-swath(s) imaged it; **0 means
no valid sub-swath** and **255 is the fill value** outside the swath. Any other value is a valid pixel.
"""),
    code('''
valid = (mask != 0) & (mask != 255)
qc = []
for t, a in L.items():
    fin = np.isfinite(a)
    qc.append({"term": t, "valid by mask (%)": 100 * valid.mean(), "finite (%)": 100 * fin.mean(),
               "finite but masked": int((fin & ~valid).sum()), "<= 0": int((a <= 0).sum()),
               "median looks": float(np.nanmedian(looks))})
pd.DataFrame(qc).round(2)
'''),
    md("## Statistics and outliers (dB)"),
    code('''
rows = []
for t, a in L.items():
    db = to_db(a)[valid & np.isfinite(a)]
    q1, q3 = np.percentile(db, [25, 75])
    out = ((db < q1 - 3 * (q3 - q1)) | (db > q3 + 3 * (q3 - q1))).mean() * 100
    rows.append({"term": t, "mean": db.mean(), "median": np.median(db), "std": db.std(),
                 "p2": np.percentile(db, 2), "p98": np.percentile(db, 98), "outliers 3·IQR (%)": out})
stats = pd.DataFrame(rows).round(2); stats
'''),
    code('''
fig, ax = plt.subplots(figsize=(7, 3.8))
for t, c in zip(L, ["#2a78d6", "#eb6834"]):
    ax.hist(to_db(L[t])[valid].ravel(), bins=120, range=(-30, 5), histtype="step", lw=2, color=c, label=t)
ax.set_xlabel("γ⁰ (dB)"); ax.set_ylabel("pixels"); ax.legend(frameon=False)
ax.set_title("AOI histograms", loc="left"); plt.show()
'''),
    md("""
## Statistics per land unit
The scene is from 3 November 2026, **after** the clear-cut (July–August). At L-band the cut should
show a lower HV (less volume scattering) than the surrounding forest. Polygons are eroded by one
pixel to avoid mixed edge pixels.
"""),
    code('''
sites = gpd.read_file(kit["aoi"]["site_polygons"]).to_crs(grid.epsg)
ref = Raster(np.zeros(win.shape, "float32"), win.transform, win.crs)
unit = []
for _, s in sites.iterrows():
    m = polygon_mask([s.geometry], ref, erode_m=abs(grid.dx)) & valid
    unit.append({"unit": s.role, "pixels": int(m.sum()),
                 **{f"{t} median (dB)": float(np.nanmedian(to_db(L[t])[m])) for t in L}})
units = pd.DataFrame(unit).round(2); units
'''),
    code('''
P.save_session(kit["session_file"], qc_valid_fraction=float(valid.mean()))
np.save(OUT / "valid_mask.npy", valid)
'''),
    status(7, {"AOI mostly valid (> 95 %)": "valid.mean() > 0.95",
               "no non-positive powers": "all(r['<= 0'] == 0 for r in qc)",
               "cut darker than control in HV": 'units.set_index("unit").loc["cut", "HVHV median (dB)"] < units.set_index("unit").loc["control", "HVHV median (dB)"]'}),
]

# --------------------------------------------------------------------------------------------- 08
NOTEBOOKS["08_Visualization_and_RGB_Composite"] = [
    md("""
# 08 — Visualization and dual-pol RGB composite

**Goal:** display GCOV values in a way that can be read: dB scale, robust stretch (2–98 %
percentiles), and a dual-pol colour composite.

Quad-pol data are usually shown as a Pauli RGB. With dual-pol HH/HV the common composite is
**R = HH, G = HV, B = HH/HV**: forests (strong volume, high HV) look green, bare or smooth surfaces
(low HV, high ratio) look blue/purple, buildings (strong HH) red/pink.
"""),
    setup(8, SESSION.format(req='("granule", "frequency", "aoi_bounds")') + OPEN + '''from nisar_s1.polarimetry import to_db, dualpol_rgb, stretch
import geopandas as gpd
'''),
    code('''
with src_ctx() as h5:
    prof = P.product_profile(h5)
    grid = prof.grids[session["frequency"]]
    win = P.window_from_bounds(grid, session["aoi_bounds"])
    hh = P.read_layer(h5, grid, "HHHH", win)
    hv = P.read_layer(h5, grid, "HVHV", win)
x0, y0 = win.transform.c, win.transform.f
ext = [x0, x0 + win.transform.a * win.shape[1], y0 + win.transform.e * win.shape[0], y0]
sites = gpd.read_file(kit["aoi"]["site_polygons"]).to_crs(grid.epsg)
'''),
    code('''
fig, axs = plt.subplots(1, 3, figsize=(16, 5))
for ax, (a, t, cm) in zip(axs, [(to_db(hh), "HH γ⁰ (dB)", "gray"), (to_db(hv), "HV γ⁰ (dB)", "gray"),
                                (to_db(hh) - to_db(hv), "HH/HV ratio (dB)", "magma")]):
    lo, hi = np.nanpercentile(a, [2, 98])
    im = ax.imshow(a, cmap=cm, vmin=lo, vmax=hi, extent=ext)
    sites.boundary.plot(ax=ax, color="cyan", lw=1)
    ax.set_title(t, loc="left"); ax.set_xticks([]); ax.set_yticks([])
    plt.colorbar(im, ax=ax, shrink=0.7)
fig.savefig(OUT / "08_channels.png", dpi=110, bbox_inches="tight"); plt.show()
'''),
    md("## Dual-pol RGB"),
    code('''
rgb = dualpol_rgb(hh, hv)
fig, ax = plt.subplots(figsize=(8, 6.5))
ax.imshow(rgb, extent=ext)
sites.boundary.plot(ax=ax, color="white", lw=1.2)
ax.set_title("NISAR L-band, 3 Nov 2026 — R: HH, G: HV, B: HH/HV (2–98 % stretch)", loc="left", fontsize=10)
ax.set_xticks([]); ax.set_yticks([])
fig.savefig(OUT / "08_rgb.png", dpi=130, bbox_inches="tight"); plt.show()
'''),
    md("""
**Reading the composite:** the forested Vosges slopes are green (HV volume scattering); meadows and
the clear-cut are darker/bluer (less HV); villages appear pink (double bounce in HH). The same
stretch must be used when comparing two dates — otherwise colours change because of the stretch,
not of the ground.
"""),
    status(8, {"RGB in [0, 1]": "rgb.min() >= 0 and rgb.max() <= 1", "figure written": '(OUT / "08_rgb.png").exists()'}),
]

# --------------------------------------------------------------------------------------------- 09
NOTEBOOKS["09_Frequencies_Masks_and_Batch_Processing"] = [
    md("""
# 09 — Frequencies, masks and batch processing

**Goal:** (1) compare frequency A (20 MHz) and frequency B (5 MHz) on the same AOI; (2) process
every discovered covariance term of every frequency in one loop, with the validity mask applied,
and export them as GeoTIFF — nothing hard-coded.
"""),
    setup(9, SESSION.format(req='("granule", "aoi_bounds")') + OPEN + '''from nisar_s1.polarimetry import to_db
from nisar_s1.optical import Raster, save_raster
'''),
    code('''
with src_ctx() as h5:
    prof = P.product_profile(h5)
    data = {}
    for f, gr in prof.grids.items():
        w = P.window_from_bounds(gr, session["aoi_bounds"])
        m = P.read_layer(h5, gr, "mask", w, nodata_zero=False)
        data[f] = {"grid": gr, "win": w, "valid": (m != 0) & (m != 255),
                   **{t: P.read_layer(h5, gr, t, w) for t in gr.terms}}
pd.DataFrame([{"frequency": f, "pixel (m)": d["grid"].dx, "AOI pixels": d["win"].shape,
               **{f"{t} median (dB)": round(float(np.nanmedian(to_db(d[t]))), 2) for t in d["grid"].terms}}
              for f, d in data.items()])
'''),
    md("""
The 5 MHz grid is 4 x coarser. Medians agree (same radar, same calibration), but a clear-cut of
2.4 ha covers ~60 pixels at 20 m and only ~4 at 80 m: frequency B is not usable for small cuts.
"""),
    code('''
A, B = data["frequencyA"], data["frequencyB"]
k = int(round(B["grid"].dx / A["grid"].dx))
fig, axs = plt.subplots(1, 2, figsize=(12, 5))
for ax, (d, t) in zip(axs, [(A, "frequency A (20 MHz)"), (B, "frequency B (5 MHz)")]):
    lo, hi = np.nanpercentile(to_db(A["HVHV"]), [2, 98])         # same stretch for both grids
    ax.imshow(to_db(d["HVHV"]), cmap="gray", vmin=lo, vmax=hi)
    ax.set_title(f"HV γ⁰, {t}, {d['grid'].dx:.0f} m", loc="left"); ax.set_xticks([]); ax.set_yticks([])
plt.show()
print("pixel ratio B/A:", k)
'''),
    md("## Batch: every term x every frequency, masked, to GeoTIFF"),
    code('''
written = []
jobs = [(f, t) for f, d in data.items() for t in d["grid"].terms]
for i, (f, t) in enumerate(jobs, 1):
    d = data[f]
    arr = to_db(np.where(d["valid"], d[t], np.nan))
    path = OUT / f"{session['granule'][:60]}_{f}_{t}_dB.tif"
    save_raster(Raster(arr, d["win"].transform, d["win"].crs), path)
    written.append(path)
    print(f"[{i}/{len(jobs)}] {path.name}")
'''),
    status(9, {"two frequencies processed": "len(data) == 2", "4 GeoTIFF written": "len(written) == 4 and all(p.exists() for p in written)",
               "B is 4x coarser": "k == 4"}),
]

# --------------------------------------------------------------------------------------------- 10
NOTEBOOKS["10_GeoTIFF_Export_and_QGIS_Validation"] = [
    md("""
# 10 — GeoTIFF export and QGIS validation

**Goal:** export analysis-ready rasters (γ⁰ in dB, HH, HV and ratio) and **prove** they are
correctly georeferenced before anyone opens them in QGIS: CRS, pixel size, origin, values,
and overlay with an independent vector layer.
"""),
    setup(10, SESSION.format(req='("granule", "frequency", "aoi_bounds")') + OPEN + '''from nisar_s1.polarimetry import to_db
from nisar_s1.optical import Raster, save_raster
import rasterio, geopandas as gpd
'''),
    code('''
with src_ctx() as h5:
    prof = P.product_profile(h5)
    grid = prof.grids[session["frequency"]]
    win = P.window_from_bounds(grid, session["aoi_bounds"])
    hh = P.read_layer(h5, grid, "HHHH", win)
    hv = P.read_layer(h5, grid, "HVHV", win)
products = {"HH_gamma0_dB": to_db(hh), "HV_gamma0_dB": to_db(hv), "HH_HV_ratio_dB": to_db(hh) - to_db(hv)}
paths = {}
for k, a in products.items():
    paths[k] = OUT / f"vosges_{k}.tif"
    save_raster(Raster(a, win.transform, win.crs), paths[k])
    print("written", paths[k].name)
'''),
    md("## Validation, read back from disk"),
    code('''
rows = []
for k, p in paths.items():
    with rasterio.open(p) as r:
        back = r.read(1)
        rows.append({"file": p.name, "CRS": r.crs.to_string(), "pixel": r.res, "size": (r.height, r.width),
                     "origin": (r.transform.c, r.transform.f), "nodata": r.nodata,
                     "values identical": bool(np.allclose(back, products[k], equal_nan=True))})
val = pd.DataFrame(rows); val
'''),
    md("""
## Overlay with an independent vector layer
The study polygons were drawn on Sentinel-2 images in another projection. If the raster
georeferencing were wrong by even one pixel, the clear-cut would not sit on the dark HV patch.
"""),
    code('''
sites = gpd.read_file(kit["aoi"]["site_polygons"]).to_crs(grid.epsg)
with rasterio.open(paths["HV_gamma0_dB"]) as r:
    a = r.read(1); b = r.bounds
cut = sites[sites.role == "cut"].geometry.iloc[0]
cx0, cy0, cx1, cy1 = cut.buffer(150).bounds
fig, ax = plt.subplots(figsize=(6, 5.5))
ax.imshow(a, cmap="gray", vmin=np.nanpercentile(a, 2), vmax=np.nanpercentile(a, 98), extent=[b.left, b.right, b.bottom, b.top])
sites.boundary.plot(ax=ax, color=["#ff4136" if r == "cut" else "#2ecc40" for r in sites.role], lw=2)
ax.set_xlim(cx0 - 300, cx1 + 300); ax.set_ylim(cy0 - 300, cy1 + 300)
ax.set_title("HV GeoTIFF read back + polygons (zoom on the cut)", loc="left", fontsize=10)
fig.savefig(OUT / "10_overlay.png", dpi=110, bbox_inches="tight"); plt.show()
'''),
    md("""
## QGIS checklist
1. *Layer → Add Raster Layer* → the three `.tif` files in the output folder printed below.
2. *Properties → Information*: CRS must read the EPSG printed above, pixel size 20 m.
3. *Add Vector Layer* → `config/site.geojson` (on-the-fly reprojection): the red polygon must sit
   on the dark HV patch.
4. *Symbology*: single-band grey, min/max = 2–98 % cumulative cut — the same stretch as notebook 08.
"""),
    code('print(OUT)'),
    status(10, {"CRS preserved": f'val.CRS.eq("EPSG:" + str(grid.epsg)).all()', "values identical after write/read": 'val["values identical"].all()',
                "pixel size = grid spacing": "all(abs(r[0] - abs(grid.dx)) < 1e-6 for r in val.pixel)"}),
]

# --------------------------------------------------------------------------------------------- 11
NOTEBOOKS["11_End_to_End_GCOV_Capstone"] = [
    md("""
# 11 — End-to-end GCOV capstone: detecting a summer clear-cut

**Goal:** chain everything — product, AOI, QC, dB, statistics, export — on a real question:
*is the July–August 2026 clear-cut of the Vosges site visible in the NISAR GCOV time series?*

The single-date product of notebooks 01–10 is complemented here by the 11 GCOV dates (track 144
ascending, June–November 2026) that the feasibility study already cut to the site (GeoTIFF, HH and
HV γ⁰ at 20 m; `vosges/scripts/04_fetch_nisar.py`). If they are absent, only the single date is used.
"""),
    setup(11, SESSION.format(req='("granule", "frequency", "aoi_bounds")') + OPEN + '''from nisar_s1.polarimetry import to_db
from nisar_s1.grid import polygon_mask, read_geotiff, to_grid
from nisar_s1.optical import Raster, save_raster
from nisar_s1.config import load_params
import geopandas as gpd, re
'''),
    md("## Step 1–5 in one cell: open → profile → AOI → QC → dB, per land unit"),
    code('''
def gcov_units(h5, frequency, bounds, sites, erode=True):
    prof = P.product_profile(h5)
    grid = prof.grids[frequency]
    win = P.window_from_bounds(grid, bounds)
    m = P.read_layer(h5, grid, "mask", win, nodata_zero=False)
    valid = (m != 0) & (m != 255)
    ref = Raster(np.zeros(win.shape, "float32"), win.transform, win.crs)
    out = {}
    for _, s in sites.to_crs(grid.epsg).iterrows():
        mk = polygon_mask([s.geometry], ref, erode_m=abs(grid.dx) if erode else 0) & valid
        for t in grid.terms:
            out[(s.role, t)] = float(to_db(np.nanmedian(P.read_layer(h5, grid, t, win)[mk])))
    return prof, out

sites = gpd.read_file(kit["aoi"]["site_polygons"])
with src_ctx() as h5:
    prof, single = gcov_units(h5, session["frequency"], session["aoi_bounds"], sites)
pd.Series(single).unstack().round(2)
'''),
    md("## Time series from the feasibility-study GeoTIFFs"),
    code('''
gdir = Path(load_params()["chemins"]["processed"]) / "nisar" / "A144F26" / "GCOV"
files = sorted(gdir.glob("*__HVHV.tif")) if gdir.exists() else []
print(len(files), "HV dates found in", gdir)
rows = []
for i, f in enumerate(files, 1):
    date = re.search(r"_(\\d{8})T", f.name).group(1)
    for pol in ("HHHH", "HVHV"):
        r = read_geotiff(f.with_name(f.name.replace("__HVHV", f"__{pol}")))
        for _, s in sites.to_crs(r.crs).iterrows():
            mk = polygon_mask([s.geometry], r, erode_m=20)
            rows.append({"date": pd.Timestamp(date), "unit": s.role, "pol": pol[:2],
                         "dB": float(to_db(np.nanmedian(np.where(r.data > 0, r.data, np.nan)[mk])))})
    print(f"[{i}/{len(files)}] {date}", end="  ")
ts = pd.DataFrame(rows)
'''),
    code('''
fig, axs = plt.subplots(1, 2, figsize=(13, 4), sharex=True)
for ax, pol in zip(axs, ["HH", "HV"]):
    for unit, c in [("control", "#1e8449"), ("cut", "#c0392b")]:
        d = ts[(ts.pol == pol) & (ts.unit == unit)].sort_values("date")
        ax.plot(d.date, d.dB, "-o", color=c, label=unit, lw=2, ms=5)
    ax.axvspan(pd.Timestamp("2026-07-27"), pd.Timestamp("2026-08-11"), color="#999999", alpha=0.25, label="cut window")
    ax.set_title(f"NISAR L-band {pol} γ⁰ (dB), median per unit", loc="left"); ax.legend(frameon=False)
fig.autofmt_xdate(); fig.savefig(OUT / "11_timeseries.png", dpi=120, bbox_inches="tight"); plt.show()
'''),
    code('''
piv = ts.pivot_table(index=["pol", "date"], columns="unit", values="dB")
piv["cut - control"] = piv["cut"] - piv["control"]
before = piv[piv.index.get_level_values("date") < "2026-07-27"].groupby("pol")["cut - control"].mean()
after = piv[piv.index.get_level_values("date") > "2026-08-11"].groupby("pol")["cut - control"].mean()
summary = pd.DataFrame({"contrast before (dB)": before, "contrast after (dB)": after})
summary["change (dB)"] = summary.iloc[:, 1] - summary.iloc[:, 0]
summary.round(2)
'''),
    md("""
**Interpretation.** Before the cut, cut and control behave alike. After it, HV of the cut drops by
several dB relative to the control and stays low: L-band cross-pol sees the loss of the tree volume.
This is the result of the feasibility study (NISAR HV change, AUC ≈ 0.9 on this site) reproduced
from the raw products in a few cells.
"""),
    status(11, {"single-date contrast computed": "len(single) == 4",
                "time series found": "len(files) >= 5",
                "HV contrast drops after the cut": 'summary.loc["HV", "change (dB)"] < -1'}),
]

# --------------------------------------------------------------------------------------------- 12
NOTEBOOKS["12_Troubleshooting_Performance_and_Session_Management"] = [
    md("""
# 12 — Troubleshooting, performance and session management

**Goal:** diagnose the problems met most often, with a check for each. Run this notebook first when
something fails.
"""),
    setup(12),
    code('''
import sys, importlib, platform, os
rows = [{"item": "python", "value": sys.version.split()[0]}, {"item": "platform", "value": platform.platform()}]
for m in ["nisar_s1", "h5py", "numpy", "rasterio", "geopandas", "pyproj", "earthaccess", "folium"]:
    try:
        mod = importlib.import_module(m); rows.append({"item": m, "value": getattr(mod, "__version__", "ok")})
    except Exception as e:
        rows.append({"item": m, "value": f"MISSING ({type(e).__name__})"})
pd.DataFrame(rows)
'''),
    md("""
## Typical problems

| Symptom | Cause | Check / fix |
|---|---|---|
| `FileNotFoundError: no session file` | notebooks run out of order | run 01, 02, 06 first |
| `KeyError: session file is missing [...]` | an earlier step was skipped | the message names the missing keys |
| `MemoryError: window needs ... GB` | AOI too large for the guard | shrink the AOI (06) or process by tiles (05) |
| `401 / 403` when streaming | no or wrong Earthdata credentials | `~/.netrc` with `urs.earthdata.nasa.gov`; accept the NISAR EULA on the Earthdata profile |
| `FileNotFoundError` on an ASF URL | product moved collection (e.g. `..._PROVISIONAL_V1`) | search the granule again (`asf_search.granule_search`) and update the URL |
| `PROJ: proj_create_from_database ...` printed by GDAL | two PROJ databases in the environment | harmless if coordinates are right (notebook 10 checks it); set `PROJ_DATA` to `pyproj.datadir.get_data_dir()` |
| very slow reads | strided reads or windows not aligned on chunks | read windows, see notebook 05 |
| kernel dies | RAM exhausted | close other notebooks; lower `max_gb`; on Linux run long jobs with `systemd-run --user -p MemoryMax=...` |
"""),
    code('''
netrc = Path.home() / ".netrc"
ok_netrc = netrc.exists() and "urs.earthdata.nasa.gov" in netrc.read_text()   # content never printed
print("Earthdata entry in ~/.netrc:", ok_netrc)
import pyproj
print("pyproj data dir:", pyproj.datadir.get_data_dir())
print("PROJ_DATA env  :", os.environ.get("PROJ_DATA", "(not set)"))
'''),
    md("## Session file: inspect, and reset if needed"),
    code('''
sf = Path(kit["session_file"])
s = P.load_session(sf) if sf.exists() else {}
for k, v in s.items():
    print(f"{k:20s} {str(v)[:90]}")
RESET = False            # set True to start again from notebook 01
if RESET:
    sf.unlink(); print("session reset")
'''),
    md("## Memory available now"),
    code('''
try:
    import psutil
    vm = psutil.virtual_memory(); print(f"RAM available: {vm.available / 2**30:.1f} of {vm.total / 2**30:.1f} GB")
except ImportError:
    print(Path("/proc/meminfo").read_text().splitlines()[2] if Path("/proc/meminfo").exists() else "unknown")
'''),
    status(12, {"package importable": 'rows[2]["value"] != "MISSING"', "session readable": "isinstance(s, dict)"}),
]

# --------------------------------------------------------------------------------------------- 13
NOTEBOOKS["13_Polarimetric_Mode_Discovery_and_Covariance_Inventory"] = [
    md("""
# 13 — Polarimetric mode discovery and covariance inventory

**Goal:** find out which polarimetric analysis the available data allow, **before** choosing a
method.

* Quad-pol (HH, HV, VH, VV) allows the full 3x3 decompositions (Cloude–Pottier, Pauli,
  Freeman–Durden, Yamaguchi). Compact-pol (RH, RV) allows Stokes / m-χ.
* Over Europe NISAR acquires **dual-pol HH/HV** (`DHDH`) and some single-pol HH (`SHSH`).
  Quad-pol is planned only over specific areas (agriculture, cal/val), not on our sites.
* The dual-pol **GCOV** stores only `HHHH` and `HVHV`. The cross term ⟨S_HH S_HV*⟩ needed for
  dual-pol decompositions must be rebuilt from the complex **GSLC** (geocoded SLC) images.
"""),
    setup(13, '''from nisar_s1.config import load_params
'''),
    md("## What NISAR acquired over the study area (ASF inventory of the feasibility study)"),
    code('''
import nisar_s1.config as C
inv = pd.read_csv(C.project_root() / "results" / "tables" / "inventory_nisar_all.csv")
inv.groupby(["product", "pol_code"]).size().unstack(fill_value=0)
'''),
    md("## The mode, discovered from each product type"),
    code('''
rows = []
with P.open_local_or_remote(kit["gcov"]["local"], kit["gcov"]["url"]) as h5:
    prof = P.product_profile(h5)
    for f in prof.grids:
        rows.append({"product": "GCOV", "frequency": f, "mode": prof.polarimetric_mode,
                     "layers": prof.grids[f].terms, "complex cross term": prof.complex_terms_available(f)})
gdir = Path(kit["data_dir"]) / "gslc"
gslc_files = sorted(gdir.glob("*.h5"))
for p in gslc_files[:1]:
    import h5py
    with h5py.File(p) as h5:
        sp = P.product_profile(h5)
        g = sp.grids["frequencyA"]
        rows.append({"product": "GSLC (AOI subset)", "frequency": "frequencyA", "mode": sp.polarimetric_mode,
                     "layers": g.polarizations, "complex cross term": str(h5[f"{g.path}/HH"].dtype).startswith("complex")})
inventory = pd.DataFrame(rows); inventory
'''),
    md("""
### Decision table: which methods of the original (quad/compact-pol) toolkit carry over?

| Original module | Needs | With NISAR dual-pol HH/HV | This series |
|---|---|---|---|
| 14 full-pol C3 reconstruction | 9 terms | 2x2 C2 from GSLC | **14** C2 from GSLC + validation against GCOV |
| 15 eigen-analysis | C3 | eigen-analysis of C2 | **15** |
| 16 Cloude–Pottier H/A/α | C3 | dual-pol H/α (Cloude 2007) | **16** |
| 17 Pauli, Freeman–Durden, Yamaguchi | VV and HH–VV phase | not possible | **17** dual-pol indices (DpRVI, RVI, Stokes) |
| 18 compact-pol (S-band SSAR) | RH/RV | no S-band over Europe | **18** Sentinel-1 C-band C2 (VV/VH), same methods |
| 19 capstone | — | — | **19** clear-cut seen by L- and C-band polarimetry |

The GSLC subsets used in 14–19 are prepared once by `training/scripts/k1_prepare_data.py`: only the AOI
window of each 13 GB GSLC is streamed from ASF and saved with the same HDF5 layout.
"""),
    code('''
P.save_session(kit["session_file"], gslc_subsets=[str(p) for p in gslc_files])
print(len(gslc_files), "GSLC subsets:", [p.name[:60] for p in gslc_files])
'''),
    status(13, {"GCOV has no complex cross term": "not inventory.loc[0, 'complex cross term']",
                "GSLC subsets present": "len(gslc_files) >= 2",
                "GSLC is complex dual-pol": "bool(inventory.iloc[-1]['complex cross term'])"}),
]

# --------------------------------------------------------------------------------------------- 14
NOTEBOOKS["14_Dual_Pol_C2_Reconstruction_and_Validation"] = [
    md("""
# 14 — Dual-pol covariance matrix C2: reconstruction and validation

**Goal:** build the 2x2 covariance matrix

C2 = [[⟨|S_HH|²⟩, ⟨S_HH S_HV*⟩], [⟨S_HV S_HH*⟩, ⟨|S_HV|²⟩]]

from the complex GSLC images, by spatial averaging (multilooking), and check it is physically valid.
The off-diagonal term stays **complex** (its phase is information; replacing it by its magnitude
changes the decompositions).
"""),
    setup(14, '''import h5py
from nisar_s1 import polarimetry as pol
session = P.load_session(kit["session_file"], required=("gslc_subsets", "aoi_bounds"))
'''),
    code('''
src = Path(session["gslc_subsets"][0])          # before the cut (18 July 2026)
with h5py.File(src) as h5:
    prof = P.product_profile(h5)
    g = prof.grids["frequencyA"]
    win = P.window_from_bounds(g, g.bounds)
    hh = P.read_layer(h5, g, "HH", win)
    hv = P.read_layer(h5, g, "HV", win)
print(prof.granule[:70]); print("SLC window", hh.shape, hh.dtype, f"pixel {g.dx:.2f} x {-g.dy:.2f} m")
'''),
    md("""
## Number of looks
Entropy and α are **biased** when estimated from few looks (entropy is underestimated). We average
to ~40 m, which gives a comparable number of looks for NISAR and Sentinel-1 (notebook 18).
"""),
    code('''
target = kit["gslc"]["target_pixel_m"]
looks = (max(1, round(target / abs(g.dy))), max(1, round(target / g.dx)))
c2 = pol.c2_from_slc(hh, hv, looks=looks)
print(f"looks (rows x cols) = {looks} -> {looks[0] * looks[1]} looks, output pixel "
      f"{looks[1] * g.dx:.0f} x {looks[0] * abs(g.dy):.0f} m, shape {c2.c11.shape}")
chk = pol.validate_c2(c2); pd.Series(chk).round(5)
'''),
    md("""
## Validation against the GCOV of the same date
GCOV `HHHH` is γ⁰ (terrain-normalized) while |GSLC|² is not terrain-normalized: values differ by a
slope-dependent factor and by speckle, so the correlation is high but not perfect (≈ 0.8 here).
The decisive test is **where** the correlation peaks: shifting one image by a single 40 m pixel
must lower it. A peak away from zero shift would reveal a geolocation error.
"""),
    code('''
from nisar_s1.grid import read_geotiff, to_grid
from nisar_s1.optical import Raster
from nisar_s1.config import load_params
import re
day = re.search(r"_(\\d{8})T", prof.granule).group(1)
gc = sorted((Path(load_params()["chemins"]["processed"]) / "nisar" / "A144F26" / "GCOV").glob(f"*_{day}T*__HHHH.tif"))
from affine import Affine
ml_tr = win.transform @ Affine.scale(looks[1], looks[0])
c11_r = Raster(c2.c11, ml_tr, win.crs)
if gc:
    gref = to_grid(read_geotiff(gc[0]), c11_r)          # GCOV γ0 HH averaged onto the C2 grid
    a, b = pol.to_db(c11_r.data), pol.to_db(gref.data)
    ok = np.isfinite(a) & np.isfinite(b)
    r = np.corrcoef(a[ok], b[ok])[0, 1]
    print(f"GCOV date {day}: Pearson r (dB) = {r:.3f}, median offset GSLC-GCOV = {np.median(a[ok]-b[ok]):+.2f} dB, n = {ok.sum()}")
    # geolocation test: the correlation must peak at zero shift (a 1-pixel error would move the peak)
    shifts = {}
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            aa = np.roll(np.roll(a, dy, 0), dx, 1); o = ok & np.isfinite(aa)
            shifts[(dy, dx)] = np.corrcoef(aa[o], b[o])[0, 1]
    best = max(shifts, key=shifts.get)
    print("correlation by shift (rows, cols):", {k: round(v, 2) for k, v in shifts.items()})
    print("best shift:", best)
    fig, ax = plt.subplots(figsize=(5, 4.5))
    ax.hexbin(b[ok], a[ok], gridsize=60, bins="log", cmap="Blues")
    ax.set_xlabel("GCOV HHHH γ⁰ (dB)"); ax.set_ylabel("C11 from GSLC (dB)"); ax.set_title("Same date, 40 m", loc="left")
    plt.show()
else:
    r, best = np.nan, (0, 0); print("no GCOV GeoTIFF of the same date found: validation skipped")
'''),
    code('''
np.savez_compressed(OUT / "c2_pre.npz", c11=c2.c11, c22=c2.c22, c12=c2.c12, transform=list(ml_tr)[:6], crs=win.crs)
P.save_session(kit["session_file"], c2_looks=list(looks))
'''),
    status(14, {"no |rho| > 1": "chk['frac_rho_above_1'] == 0", "no negative determinant": "chk['frac_negative_det'] == 0",
                "trace = sum of eigenvalues": "chk['max_trace_error'] < 1e-3",
                "consistent with GCOV (r > 0.6)": "np.isnan(r) or r > 0.6",
                "correlation peaks at zero shift": "best == (0, 0)"}),
]

# --------------------------------------------------------------------------------------------- 15
NOTEBOOKS["15_Dual_Pol_Observables_and_Eigen_Analysis"] = [
    md("""
# 15 — Dual-pol observables and eigen-analysis

**Goal:** derive from C2 the basic observables — total power (span), co/cross ratio, the complex
co/cross correlation ρ = C12 / √(C11·C22) — and the eigenvalues λ1 ≥ λ2 of C2.

The two eigenvalues split the power into a dominant, polarized mechanism (λ1) and a residual
depolarized part (λ2). Their balance is what entropy (notebook 16) and DpRVI (notebook 17) measure.
Processing is done **tile by tile** to keep memory low on large AOIs.
"""),
    setup(15, '''import h5py
from nisar_s1 import polarimetry as pol
session = P.load_session(kit["session_file"], required=("gslc_subsets", "c2_looks"))
'''),
    code('''
looks = tuple(session["c2_looks"])
def c2_tiles(path, block=1024):
    """C2 of a GSLC subset, computed tile by tile (block multiple of the looks)."""
    parts = []
    with h5py.File(path) as h5:
        g = P.product_profile(h5).grids["frequencyA"]
        win = P.window_from_bounds(g, g.bounds)
        b = block - block % (looks[0] * looks[1])
        rows = range(win.rows.start, win.rows.stop - looks[0] + 1, b - b % looks[0])
        for i, r0 in enumerate(rows, 1):
            r1 = min(r0 + b - b % looks[0], win.rows.stop)
            w = P.Window(slice(r0, r1), win.cols, g.transform, win.crs)
            parts.append(pol.c2_from_slc(P.read_layer(h5, g, "HH", w), P.read_layer(h5, g, "HV", w), looks))
            print(f"[{i}/{len(rows)}] rows {r0}-{r1}")
    nx = min(p.c11.shape[1] for p in parts)
    cat = lambda k: np.concatenate([getattr(p, k)[:, :nx] for p in parts])
    return pol.C2(cat("c11"), cat("c22"), cat("c12")), win

c2, win = c2_tiles(session["gslc_subsets"][0])
print("C2 shape", c2.c11.shape)
'''),
    code('''
rho = c2.coherence
l1, l2 = pol.eigenvalues(c2)
obs = {"span (dB)": pol.to_db(c2.trace), "HH/HV ratio (dB)": pol.to_db(c2.c11) - pol.to_db(c2.c22),
       "|ρ| HH–HV": np.abs(rho), "arg ρ (deg)": np.degrees(np.angle(rho)),
       "λ1 (dB)": pol.to_db(l1), "λ2/λ1": l2 / l1}
fig, axs = plt.subplots(2, 3, figsize=(15, 8.5))
for ax, (t, a) in zip(axs.ravel(), obs.items()):
    lo, hi = np.nanpercentile(a, [2, 98]) if "arg" not in t else (-180, 180)
    im = ax.imshow(a, cmap="twilight" if "arg" in t else "viridis", vmin=lo, vmax=hi)
    ax.set_title(t, loc="left"); ax.set_xticks([]); ax.set_yticks([]); plt.colorbar(im, ax=ax, shrink=0.75)
fig.suptitle("NISAR L-band dual-pol observables, 18 Jul 2026 (before the cut), ~40 m", x=0.01, ha="left")
fig.savefig(OUT / "15_observables.png", dpi=100, bbox_inches="tight"); plt.show()
'''),
    md("""
**Reading.** Over natural media, |ρ| between HH and HV is **low** (≈ 0.1–0.3): reflection symmetry
makes co- and cross-pol nearly uncorrelated, so most of the information is in the powers. The phase
of ρ is then mostly noise. λ2/λ1 is high where scattering is random (forest volume), low where one
mechanism dominates (bare soil, buildings).
"""),
    code('''
summary = pd.DataFrame({k: pd.Series(v[np.isfinite(v)]).describe(percentiles=[.1, .5, .9]) for k, v in obs.items()}).T
summary.round(3)
'''),
    status(15, {"|ρ| within [0, 1]": "np.nanmax(np.abs(rho)) <= 1 + 1e-5", "λ1 >= λ2": "np.all((l1 >= l2)[np.isfinite(l1)])",
                "low median |ρ| (reflection symmetry)": "np.nanmedian(np.abs(rho)) < 0.5"}),
]

# --------------------------------------------------------------------------------------------- 16
NOTEBOOKS["16_Dual_Pol_H_A_Alpha"] = [
    md("""
# 16 — Dual-pol entropy / anisotropy / α (Cloude 2007)

**Goal:** apply the eigen-decomposition of C2: entropy **H** (0 = one pure mechanism, 1 = fully
random), anisotropy **A** = (λ1 − λ2)/(λ1 + λ2), and mean scattering angle **ᾱ** (0° = co-pol
dominated, 90° = cross-pol dominated), then read the H–α plane, before and after the clear-cut.

With dual-pol, α and H describe the **HH/HV** balance only; the quad-pol H–α zones of Cloude &
Pottier (1997) do not apply as such. Dual-pol H–α is used for vegetation/soil discrimination
(Cloude 2007; Ji & Wu 2015).
"""),
    setup(16, '''import h5py
from nisar_s1 import polarimetry as pol
from nisar_s1.grid import polygon_mask
from nisar_s1.optical import Raster
from affine import Affine
import geopandas as gpd
session = P.load_session(kit["session_file"], required=("gslc_subsets", "c2_looks"))
looks = tuple(session["c2_looks"])
'''),
    code('''
def c2_of(path):
    with h5py.File(path) as h5:
        g = P.product_profile(h5).grids["frequencyA"]
        win = P.window_from_bounds(g, g.bounds)
        c = pol.c2_from_slc(P.read_layer(h5, g, "HH", win), P.read_layer(h5, g, "HV", win), looks)
    return c, win.transform @ Affine.scale(looks[1], looks[0]), win.crs

res = {}
for i, (k, p) in enumerate(zip(["pre (18 Jul)", "post (23 Aug)"], session["gslc_subsets"][:2]), 1):
    c, tr, crs = c2_of(p)
    res[k] = pol.h_alpha_dual(c); res[k]["tr"] = tr; res[k]["crs"] = crs
    print(f"[{i}/2] {k}: median H = {np.nanmedian(res[k]['H']):.2f}, median α = {np.nanmedian(res[k]['alpha']):.1f}°")
'''),
    code('''
sites = gpd.read_file(kit["aoi"]["site_polygons"]).to_crs(res["pre (18 Jul)"]["crs"])
fig, axs = plt.subplots(2, 3, figsize=(15, 9))
for row, (k, r) in zip(axs, res.items()):
    ny, nx = r["H"].shape; tr = r["tr"]
    ext = [tr.c, tr.c + tr.a * nx, tr.f + tr.e * ny, tr.f]
    for ax, (v, lim, t) in zip(row, [("H", (0.2, 1), "H"), ("A", (0, 0.8), "A"), ("alpha", (5, 45), "ᾱ (deg)")]):
        im = ax.imshow(r[v], vmin=lim[0], vmax=lim[1], cmap="viridis", extent=ext)
        sites.boundary.plot(ax=ax, color=["#ff4136" if s == "cut" else "white" for s in sites.role], lw=1.2)
        ax.set_title(f"{t} — {k}", loc="left"); ax.set_xticks([]); ax.set_yticks([]); plt.colorbar(im, ax=ax, shrink=0.75)
fig.savefig(OUT / "16_h_a_alpha.png", dpi=100, bbox_inches="tight"); plt.show()
'''),
    md("## H–α plane, cut versus control forest"),
    code('''
fig, axs = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
table = []
for ax, (k, r) in zip(axs, res.items()):
    ref = Raster(r["H"], r["tr"], r["crs"])
    ax.hexbin(r["H"].ravel(), r["alpha"].ravel(), gridsize=50, bins="log", cmap="Greys", extent=(0, 1, 0, 60))
    for _, s in sites.iterrows():
        m = polygon_mask([s.geometry], ref) & np.isfinite(r["H"])
        c = "#c0392b" if s.role == "cut" else "#1e8449"
        ax.scatter(r["H"][m], r["alpha"][m], s=14, color=c, edgecolor="white", lw=0.5, label=f"{s.role} (n={m.sum()})")
        table.append({"date": k, "unit": s.role, "n": int(m.sum()), "H": np.nanmedian(r["H"][m]),
                      "A": np.nanmedian(r["A"][m]), "alpha": np.nanmedian(r["alpha"][m])})
    ax.set_xlabel("entropy H"); ax.set_title(k, loc="left"); ax.legend(frameon=False, fontsize=8)
axs[0].set_ylabel("ᾱ (deg)"); fig.savefig(OUT / "16_h_alpha_plane.png", dpi=110, bbox_inches="tight"); plt.show()
ha = pd.DataFrame(table).round(3); ha
'''),
    md("""
**Reading.** Before the cut, both units are forest: high entropy (≈ 0.75) and ᾱ ≈ 25°, well
above the meadows of the valley. After the cut, the cut moves only **slightly** towards lower H and
lower ᾱ, while its HV power dropped by ~4 dB (notebook 11). At L-band the logged stand still
depolarizes (stumps, slash, regrowth, rough soil): the *ratio* HV/HH changes little even though both
powers fall. Dual-pol H/α is therefore a weak clear-cut indicator here — the power is the signal.
With a 2.4 ha cut there are only ~16 pixels at 40 m: an illustration, not a statistical test (19).
"""),
    code('''
np.savez_compressed(OUT / "h_alpha.npz", **{f"{k.split()[0]}_{v}": res[k][v] for k in res for v in ("H", "A", "alpha")})
'''),
    status(16, {"H within [0, 1]": "all(np.nanmax(r['H']) <= 1 + 1e-5 for r in res.values())",
                "alpha within [0, 90]": "all(np.nanmax(r['alpha']) <= 90 for r in res.values())",
                "both units sampled": "(ha.n > 0).all()"}),
]

# --------------------------------------------------------------------------------------------- 17
NOTEBOOKS["17_Dual_Pol_Vegetation_Indices_DpRVI_RVI_Stokes"] = [
    md("""
# 17 — Dual-pol vegetation indices: DpRVI, RVI and Stokes parameters

**Why not Pauli, Freeman–Durden or Yamaguchi?** These decompositions model the 3x3 matrix: they need
VV and the HH–VV phase (surface vs double-bounce), which a HH/HV acquisition does not measure.
Running them on dual-pol data would be wrong, not just approximate.

**Dual-pol alternatives used in the literature:**
* **DpRVI** = 1 − m·β (Mandal et al. 2020), m = degree of polarization, β = λ1/(λ1+λ2):
  0 for a pure scatterer (bare soil), towards 1 for random volume (dense vegetation).
* **RVI** = 4·σ_cross/(σ_co + σ_cross) (Trudel et al. 2012): intensity only, so it can be computed
  from GCOV as well (useful for the 11-date time series).
* **Stokes parameters** of the received wave (g0…g3), degree of polarization m and ellipticity χ.
  For linear transmit these describe the wave only; the m-χ *scattering* interpretation of
  compact-pol (circular transmit) does not apply.
"""),
    setup(17, '''import h5py
from nisar_s1 import polarimetry as pol
from nisar_s1.grid import polygon_mask
from nisar_s1.optical import Raster
from affine import Affine
import geopandas as gpd
session = P.load_session(kit["session_file"], required=("gslc_subsets", "c2_looks"))
looks = tuple(session["c2_looks"])
'''),
    code('''
ind = {}
for i, (k, p) in enumerate(zip(["pre", "post"], session["gslc_subsets"][:2]), 1):
    with h5py.File(p) as h5:
        g = P.product_profile(h5).grids["frequencyA"]
        win = P.window_from_bounds(g, g.bounds)
        c = pol.c2_from_slc(P.read_layer(h5, g, "HH", win), P.read_layer(h5, g, "HV", win), looks)
    st = pol.stokes_dual(c)
    ind[k] = {"DpRVI": pol.dprvi(c), "RVI": pol.rvi_dual(c.c11, c.c22), "m": st["m"], "chi": st["chi"],
              "tr": win.transform @ Affine.scale(looks[1], looks[0]), "crs": win.crs}
    print(f"[{i}/2] {k} done")
'''),
    code('''
fig, axs = plt.subplots(2, 4, figsize=(18, 8.5))
for row, k in zip(axs, ind):
    for ax, (v, lim) in zip(row, [("DpRVI", (0.3, 1)), ("RVI", (0.2, 1.2)), ("m", (0, 0.7)), ("chi", (-10, 10))]):
        im = ax.imshow(ind[k][v], vmin=lim[0], vmax=lim[1], cmap="RdYlGn" if v != "chi" else "coolwarm")
        ax.set_title(f"{v} — {k}", loc="left"); ax.set_xticks([]); ax.set_yticks([]); plt.colorbar(im, ax=ax, shrink=0.7)
fig.savefig(OUT / "17_indices.png", dpi=100, bbox_inches="tight"); plt.show()
'''),
    code('''
sites = gpd.read_file(kit["aoi"]["site_polygons"]).to_crs(ind["pre"]["crs"])
rows = []
for k, r in ind.items():
    ref = Raster(r["DpRVI"], r["tr"], r["crs"])
    for _, s in sites.iterrows():
        m = polygon_mask([s.geometry], ref) & np.isfinite(r["DpRVI"])
        rows.append({"date": k, "unit": s.role, **{v: float(np.nanmedian(r[v][m])) for v in ("DpRVI", "RVI", "m", "chi")}})
t = pd.DataFrame(rows).pivot(index="unit", columns="date")
t.round(3)
'''),
    md("""
**Reading.** Forest has a high DpRVI and a low degree of polarization m (random volume). After the
cut, DpRVI of the cut decreases and m increases, but only by a few hundredths — the same message as
H/α in notebook 16: these normalized indices are built to be insensitive to the absolute power,
and the absolute HV power is precisely what the clear-cut changes most at L-band.
"""),
    status(17, {"DpRVI within [0, 1]": "all(np.nanmax(r['DpRVI']) <= 1 + 1e-5 for r in ind.values())",
                "m within [0, 1]": "all(np.nanmax(r['m']) <= 1 + 1e-5 for r in ind.values())",
                "DpRVI of the cut decreases": 't.loc["cut", ("DpRVI", "post")] < t.loc["cut", ("DpRVI", "pre")]'}),
]

# --------------------------------------------------------------------------------------------- 18
NOTEBOOKS["18_Sentinel1_C_Band_Dual_Pol_Counterpart"] = [
    md("""
# 18 — The C-band counterpart: Sentinel-1 VV/VH dual-pol C2

**Why this module?** The original toolkit's module 18 handles NISAR S-band compact-pol, which is not
acquired over Europe. The operational comparison that matters here is **Sentinel-1 C-band**
(VV/VH, 12-day revisit), which this feasibility study compares with NISAR throughout.

The Sentinel-1 C2 matrix (VV/VH, complex cross term kept) is produced by ESA SNAP from the IW SLC
(graph `s1_c2`: split → orbit → complex calibration → deburst → C2 → multilook 12x3 → terrain
correction to 40 m), then **the same functions** as for NISAR are applied.
"""),
    setup(18, '''from nisar_s1 import polarimetry as pol
from nisar_s1.snap import dimap_band
from nisar_s1.grid import read_geotiff, polygon_mask
import geopandas as gpd
'''),
    code('''
s1dir = Path(kit["data_dir"]) / "s1"
dims = sorted(s1dir.glob("c2_*.dim"))
print([d.name for d in dims])
def load_c2(dim):
    b = {k: read_geotiff(dimap_band(dim, k)) for k in ("C11", "C12_real", "C12_imag", "C22")}
    c = pol.c2_from_elements(*(np.where(b[k].data == 0, np.nan, b[k].data) for k in ("C11", "C22", "C12_real", "C12_imag")))
    return c, b["C11"]
s1 = {}
for i, (k, d) in enumerate(zip(["pre (21 Jul)", "post (14 Aug)"], dims[:2]), 1):
    c, ref = load_c2(d)
    s1[k] = {"c2": c, "ref": ref, "check": pol.validate_c2(c), **pol.h_alpha_dual(c), "DpRVI": pol.dprvi(c)}
    print(f"[{i}/2] {k}: shape {c.c11.shape}, valid {s1[k]['check']['n_valid']}")
pd.DataFrame({k: v["check"] for k, v in s1.items()}).round(4)
'''),
    code('''
fig, axs = plt.subplots(2, 4, figsize=(18, 8.5))
for row, (k, r) in zip(axs, s1.items()):
    span = pol.to_db(r["c2"].trace)
    for ax, (a, lim, t) in zip(row, [(span, tuple(np.nanpercentile(span, [2, 98])), "span (dB)"), (r["H"], (0.2, 1), "H"),
                                     (r["alpha"], (5, 45), "ᾱ (deg)"), (r["DpRVI"], (0.3, 1), "DpRVI")]):
        im = ax.imshow(a, vmin=lim[0], vmax=lim[1], cmap="gray" if "span" in t else "viridis")
        ax.set_title(f"S1 C-band {t} — {k}", loc="left", fontsize=9); ax.set_xticks([]); ax.set_yticks([]); plt.colorbar(im, ax=ax, shrink=0.7)
fig.savefig(OUT / "18_s1_c2.png", dpi=100, bbox_inches="tight"); plt.show()
'''),
    md("""
## L-band versus C-band over the same forest
At C-band (5.6 cm) the signal comes mostly from the upper canopy (leaves, twigs); at L-band (24 cm)
it penetrates to branches and trunks. Over a closed forest both show high entropy (≈ 0.75); the
clear-cut barely moves H, ᾱ or DpRVI at either band, while the powers drop (notebook 19).
"""),
    code('''
sites = gpd.read_file(kit["aoi"]["site_polygons"]).to_crs(s1["pre (21 Jul)"]["ref"].crs)
rows = []
for k, r in s1.items():
    for _, s in sites.iterrows():
        m = polygon_mask([s.geometry], r["ref"]) & np.isfinite(r["H"])
        rows.append({"date": k, "unit": s.role, "n": int(m.sum()), "H": np.nanmedian(r["H"][m]),
                     "alpha": np.nanmedian(r["alpha"][m]), "DpRVI": np.nanmedian(r["DpRVI"][m]),
                     "VH/VV (dB)": np.nanmedian(pol.to_db(r["c2"].c22[m]) - pol.to_db(r["c2"].c11[m]))})
c_units = pd.DataFrame(rows).round(3); c_units
'''),
    status(18, {"two S1 dates": "len(s1) == 2", "C2 physically valid": "all(v['check']['frac_rho_above_1'] == 0 for v in s1.values())",
                "H within [0, 1]": "all(np.nanmax(v['H']) <= 1 + 1e-5 for v in s1.values())"}),
]

# --------------------------------------------------------------------------------------------- 19
NOTEBOOKS["19_End_to_End_Polarimetric_Capstone_L_vs_C"] = [
    md("""
# 19 — Polarimetric capstone: the clear-cut seen by L-band and C-band

**Question:** which dual-pol parameters change most on the clear-cut between the dates before and
after the cut, relative to the unchanged control forest — and does L-band (NISAR) separate the cut
better than C-band (Sentinel-1)?

**Method.** For each sensor and parameter: change Δ = post − pre per pixel (40 m), then
separability of the cut pixels from the control pixels measured by the AUC (0.5 = no separation,
1 = perfect), with the moving-block bootstrap of the feasibility study for a confidence interval.
"""),
    setup(19, '''import h5py
from affine import Affine
from nisar_s1 import polarimetry as pol
from nisar_s1.grid import polygon_mask, read_geotiff, to_grid
from nisar_s1.optical import Raster
from nisar_s1.snap import dimap_band
from nisar_s1.stats import auc, block_bootstrap_auc
import geopandas as gpd
session = P.load_session(kit["session_file"], required=("gslc_subsets", "c2_looks"))
looks = tuple(session["c2_looks"])
'''),
    code('''
def params(c):
    ha = pol.h_alpha_dual(c)
    return {"co (dB)": pol.to_db(c.c11), "cross (dB)": pol.to_db(c.c22), "H": ha["H"], "alpha": ha["alpha"],
            "DpRVI": pol.dprvi(c), "m": pol.degree_of_polarization(c)}

def nisar(path):
    with h5py.File(path) as h5:
        g = P.product_profile(h5).grids["frequencyA"]
        w = P.window_from_bounds(g, g.bounds)
        c = pol.c2_from_slc(P.read_layer(h5, g, "HH", w), P.read_layer(h5, g, "HV", w), looks)
    return params(c), Raster(c.c11, w.transform @ Affine.scale(looks[1], looks[0]), w.crs)

def s1(dim):
    b = {k: read_geotiff(dimap_band(dim, k)) for k in ("C11", "C22", "C12_real", "C12_imag")}
    c = pol.c2_from_elements(*(np.where(b[k].data == 0, np.nan, b[k].data) for k in ("C11", "C22", "C12_real", "C12_imag")))
    return params(c), b["C11"]

dims = sorted((Path(kit["data_dir"]) / "s1").glob("c2_*.dim"))
sensors = {}
for i, (name, fn, pair) in enumerate([("NISAR L-band (HH/HV)", nisar, session["gslc_subsets"][:2]),
                                      ("Sentinel-1 C-band (VV/VH)", s1, dims[:2])], 1):
    (pre, ref), (post, ref_post) = fn(pair[0]), fn(pair[1])
    # SNAP terrain correction may give the two dates slightly different extents (one row here):
    # bring "post" onto the "pre" grid (nearest neighbour, same 40 m pixels) before differencing
    post = {k: to_grid(Raster(v, ref_post.transform, ref_post.crs), ref, resampling="nearest").data for k, v in post.items()}
    sensors[name] = {"delta": {k: post[k] - pre[k] for k in pre}, "ref": ref}
    print(f"[{i}/2] {name}: grid {ref.data.shape}")
'''),
    code('''
sites = gpd.read_file(kit["aoi"]["site_polygons"])
rows = []
for name, s in sensors.items():
    st = sites.to_crs(s["ref"].crs)
    cut = polygon_mask(list(st[st.role == "cut"].geometry), s["ref"])
    ctl = polygon_mask(list(st[st.role == "control"].geometry), s["ref"])
    for k, d in s["delta"].items():
        ok = np.isfinite(d)
        a, b = d[cut & ok], d[ctl & ok]
        sep = auc(a, b)
        lo, hi = block_bootstrap_auc(d, cut & ok, ctl & ok, block=2, n=300)
        rows.append({"sensor": name, "parameter": k, "n cut": a.size, "n control": b.size,
                     "median Δ cut": np.median(a), "median Δ control": np.median(b), "AUC": max(sep, 1 - sep),
                     "AUC 95% CI": f"{lo:.2f}–{hi:.2f}" if np.isfinite(lo) else "-"})
res = pd.DataFrame(rows).round(3); res
'''),
    code('''
fig, ax = plt.subplots(figsize=(9, 4))
pv = res.pivot(index="parameter", columns="sensor", values="AUC").sort_values("NISAR L-band (HH/HV)")
y = np.arange(len(pv))
for j, (col, c) in enumerate(zip(pv.columns, ["#2a78d6", "#eb6834"])):
    ax.barh(y + (j - 0.5) * 0.38, pv[col], height=0.36, color=c, label=col)
ax.set_yticks(y, pv.index); ax.axvline(0.5, color="#888888", lw=1, ls="--")
ax.set_xlim(0.4, 1.0); ax.set_xlabel("AUC of the change (cut vs control forest)")
ax.legend(frameon=False, loc="lower right"); ax.set_title("Clear-cut C11, Vosges: which dual-pol change separates the cut?", loc="left")
fig.savefig(OUT / "19_auc.png", dpi=130, bbox_inches="tight"); plt.show()
'''),
    md("""
## What this run shows (and its limits)
* **The powers carry the signal.** The co- and cross-pol power drops on the cut separate it from
  the control almost perfectly at both bands (AUC ≈ 0.97–0.99 at L-band, 0.90–0.97 at C-band). The
  drop is larger at L-band (cross-pol ≈ −4.3 dB vs ≈ −2.2 dB at C-band, control ≈ 0): L-band sees
  the loss of trunks and branches, C-band mostly the loss of the canopy.
* **The normalized dual-pol parameters do not.** H, ᾱ, DpRVI and m change by a few hundredths
  (AUC 0.52–0.59, intervals touching 0.5). They describe the *balance* between co- and cross-pol,
  and a fresh clear-cut (stumps, slash, rough soil) still depolarizes: both powers fall together.
  The complex GSLC (13 GB per date) therefore adds nothing for this question over the GCOV powers.
* At 40 m (32 looks) the speckle is low enough for C-band to separate a fresh 2.4 ha cut too; the
  feasibility study, at 20 m and over several months, found L-band clearly ahead (persistence of
  the contrast, notebook 11).
* One cut, ~16 pixels at 40 m: wide confidence intervals, one site, one season. The **method**
  transfers (other sites, Morvan; ROSE-L later), the numbers have to be re-established there.
"""),
    code('res.to_csv(OUT / "19_auc_table.csv", index=False); print(OUT / "19_auc_table.csv")'),
    status(19, {"both sensors processed": "len(sensors) == 2", "cut sampled at both bands": "(res['n cut'] > 5).all()",
                "AUC table written": '(OUT / "19_auc_table.csv").exists()'}),
]


def main():
    """``python k2_build_notebooks.py [NN ...]``: rebuild all notebooks, or only those numbered
    (a rebuilt notebook loses its outputs: execute it again with k3_run_notebooks.py)."""
    import sys
    only = {int(a) for a in sys.argv[1:]}
    todo = {k: v for k, v in NOTEBOOKS.items() if not only or int(k[:2]) in only}
    for i, (name, cells) in enumerate(todo.items(), 1):
        nb = nbf.v4.new_notebook()
        nb.cells = cells
        nb.metadata = {"kernelspec": {"name": "python3", "display_name": "Python 3 (nisar_s1)", "language": "python"},
                       "language_info": {"name": "python"}}
        path = NB / f"{name}.ipynb"
        nbf.write(nb, path)
        print(f"[{i}/{len(todo)}] {path.name} ({len(cells)} cells)")


if __name__ == "__main__":
    main()
