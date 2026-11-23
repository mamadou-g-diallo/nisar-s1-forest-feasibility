"""Run ESA SNAP ``gpt`` graphs (Sentinel-1 SLC -> coherence / terrain-flattened gamma0).

Graphs live in ``nisar_s1/graphs`` and use ``${name}`` variables that are substituted here, so the
same processing is applied to every date / pair. The gpt console output (progress percentages)
is streamed to the caller's log with a prefix, and written in full to ``<out>.gpt.log``.
"""

from __future__ import annotations

import os
import re
import string
import subprocess
import time
from pathlib import Path

GRAPHS = Path(__file__).parent / "graphs"


def render_graph(name: str, out_xml: Path, **variables) -> Path:
    """Write graph ``name`` (``s1_coherence``, ``s1_gamma0``, ``s1_interferogram`` or ``s1_c2``) with variables substituted."""
    tpl = string.Template((GRAPHS / f"{name}.xml").read_text())
    xml = tpl.substitute({k: str(v) for k, v in variables.items()})
    out_xml.parent.mkdir(parents=True, exist_ok=True)
    out_xml.write_text(xml)
    return out_xml


def run_gpt(graph_xml: Path, gpt: str | Path, log: Path, label: str = "",
            cache_gb: int = int(os.environ.get("SNAP_CACHE_GB", 2)),
            threads: int = 2, timeout_s: int = 4 * 3600) -> None:
    """Run ``gpt graph.xml``; print gpt progress lines with ``label``; raise on failure."""
    cmd = [str(Path(gpt).expanduser()), str(graph_xml), "-c", f"{cache_gb}G", "-q", str(threads)]
    t0 = time.time()
    with open(log, "w") as lf:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             env={**os.environ, "LC_ALL": "C"})
        last = ""
        for line in p.stdout:
            lf.write(line)
            s = line.strip()
            # gpt prints progress like "....10%....20%...." ; keep the last percentage
            pct = re.findall(r"(\d+)%", s)
            if pct and pct[-1] != last:
                last = pct[-1]
                print(f"{label} gpt {last}% ({(time.time() - t0) / 60:.1f} min)", flush=True)
            elif "Error" in s or "Exception" in s:
                print(f"{label} gpt: {s[:200]}", flush=True)
        rc = p.wait(timeout=timeout_s)
    if rc != 0:
        raise RuntimeError(f"gpt failed (code {rc}), see {log}")
    print(f"{label} gpt done in {(time.time() - t0) / 60:.1f} min", flush=True)


def s1_coherence(ref_safe: Path, sec_safe: Path, out_dim: Path, swath: str, aoi_wkt: str,
                 region_wkt: str, gpt: str, pixel_m: float = 20.0, crs: str = "EPSG:32632",
                 coh_win: tuple[int, int] = (10, 3), label: str = "") -> Path:
    """12-day (or any) coherence of a Sentinel-1 SLC pair, VV and VH, on a UTM grid."""
    if out_dim.exists():
        print(f"{label} {out_dim.name}: already present", flush=True)
        return out_dim
    tmp = out_dim.with_name(out_dim.stem + "_part.dim")
    xml = render_graph("s1_coherence", out_dim.with_suffix(".xml"), ref=_manifest(ref_safe),
                       sec=_manifest(sec_safe), swath=swath.upper(), aoi=aoi_wkt, cohWinRg=coh_win[0],
                       cohWinAz=coh_win[1], pixel=pixel_m, crs=crs, region=region_wkt, out=tmp)
    run_gpt(xml, gpt, out_dim.with_suffix(".gpt.log"), label)
    _rename_dimap(tmp, out_dim)
    return out_dim


def s1_gamma0(safe: Path, out_dim: Path, swath: str, aoi_wkt: str, region_wkt: str, gpt: str,
              pixel_m: float = 20.0, crs: str = "EPSG:32632", looks: tuple[int, int] = (4, 1),
              label: str = "") -> Path:
    """Terrain-flattened gamma0 (VV, VH, linear power) of one Sentinel-1 SLC date on a UTM grid."""
    if out_dim.exists():
        print(f"{label} {out_dim.name}: already present", flush=True)
        return out_dim
    tmp = out_dim.with_name(out_dim.stem + "_part.dim")
    xml = render_graph("s1_gamma0", out_dim.with_suffix(".xml"), ref=_manifest(safe), swath=swath.upper(),
                       aoi=aoi_wkt, rgLooks=looks[0], azLooks=looks[1], pixel=pixel_m, crs=crs,
                       region=region_wkt, out=tmp)
    run_gpt(xml, gpt, out_dim.with_suffix(".gpt.log"), label)
    _rename_dimap(tmp, out_dim)
    return out_dim


def s1_c2(safe: Path, out_dim: Path, swath: str, aoi_wkt: str, region_wkt: str, gpt: str,
          pixel_m: float = 40.0, crs: str = "EPSG:32632", looks: tuple[int, int] = (12, 3),
          label: str = "") -> Path:
    """Dual-pol covariance matrix C2 (VV/VH, complex cross term kept) of one Sentinel-1 SLC date,
    multilooked (``looks`` = range, azimuth) and terrain-corrected on a UTM grid (graph ``s1_c2``).
    Read the bands with :func:`dimap_band` (``C11``, ``C12_real``, ``C12_imag``, ``C22``)."""
    if out_dim.exists():
        print(f"{label} {out_dim.name}: already present", flush=True)
        return out_dim
    tmp = out_dim.with_name(out_dim.stem + "_part.dim")
    _remove_partial(tmp)
    xml = render_graph("s1_c2", out_dim.with_suffix(".xml"), ref=_manifest(safe), swath=swath.upper(),
                       aoi=aoi_wkt, rgLooks=looks[0], azLooks=looks[1], pixel=pixel_m, crs=crs,
                       region=region_wkt, out=tmp)
    run_gpt(xml, gpt, out_dim.with_suffix(".gpt.log"), label)
    _rename_dimap(tmp, out_dim)
    return out_dim


def s1_interferogram(ref_safe: Path, sec_safe: Path, out_dim: Path, swath: str, aoi_wkt: str,
                     region_wkt: str, gpt: str, pixel_m: float = 20.0, crs: str = "EPSG:2154",
                     coh_win: tuple[int, int] = (10, 3), looks: tuple[int, int] = (4, 1),
                     label: str = "") -> Path:
    """Flattened, topography-free VV interferogram (i/q bands) and coherence of a Sentinel-1 SLC
    pair, multilooked and terrain-corrected (graph ``s1_interferogram``)."""
    if out_dim.exists():
        print(f"{label} {out_dim.name}: already present", flush=True)
        return out_dim
    tmp = out_dim.with_name(out_dim.stem + "_part.dim")
    _remove_partial(tmp)   # left over by an interrupted run (crash, OOM, reboot)
    xml = render_graph("s1_interferogram", out_dim.with_suffix(".xml"), ref=_manifest(ref_safe),
                       sec=_manifest(sec_safe), swath=swath.upper(), aoi=aoi_wkt, cohWinRg=coh_win[0],
                       cohWinAz=coh_win[1], rgLooks=looks[0], azLooks=looks[1], pixel=pixel_m, crs=crs,
                       region=region_wkt, out=tmp)
    run_gpt(xml, gpt, out_dim.with_suffix(".gpt.log"), label)
    _rename_dimap(tmp, out_dim)
    return out_dim


def _remove_partial(tmp: Path) -> None:
    """Delete an incomplete BEAM-DIMAP output (``*_part.dim`` + ``.data``) so a rerun starts clean."""
    import shutil
    if tmp.with_suffix(".data").exists():
        shutil.rmtree(tmp.with_suffix(".data"))
    tmp.unlink(missing_ok=True)


def _manifest(safe: Path) -> Path:
    safe = Path(safe)
    return safe / "manifest.safe" if safe.is_dir() else safe


def _rename_dimap(src: Path, dst: Path) -> None:
    """Rename a BEAM-DIMAP product (``.dim`` header + ``.data`` folder) atomically enough."""
    src.with_suffix(".data").rename(dst.with_suffix(".data"))
    txt = src.read_text().replace(src.with_suffix(".data").name, dst.with_suffix(".data").name)
    dst.write_text(txt)
    src.unlink()


def dimap_band(dim: Path, pattern: str) -> Path:
    """Path of the ENVI ``.img`` of the band whose name contains ``pattern`` (case-insensitive),
    e.g. ``Gamma0_VV`` or ``coh_`` + ``_VV``. Raises if zero or several bands match."""
    imgs = sorted(Path(dim).with_suffix(".data").glob("*.img"))
    parts = [s.lower() for s in pattern.split("*")]
    hit = [i for i in imgs if all(s in i.stem.lower() for s in parts)]
    if len(hit) != 1:
        raise KeyError(f"{pattern!r} matches {[h.stem for h in hit]} in {[i.stem for i in imgs]}")
    return hit[0]
