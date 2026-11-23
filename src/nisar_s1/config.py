"""Configuration: locate and load the parameter file and the per-site study files.

The package does not depend on the layout of this repository. Configuration files are looked up,
in this order:

1. an explicit path passed to :func:`load_params` / :func:`load_site`;
2. the environment variable ``NISAR_S1_ROOT`` (a folder containing ``config/params.yaml`` and
   ``config/sites/*.yaml``);
3. the repository the package was installed from in editable mode (``pip install -e .``);
4. the current working directory.

Relative paths in a site file (``chemins``) are resolved against that same root folder.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]


def project_root() -> Path:
    """Root folder holding ``config/`` (see the module docstring for the lookup order)."""
    env = os.environ.get("NISAR_S1_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    if (_REPO_ROOT / "config").is_dir():
        return _REPO_ROOT
    return Path.cwd()


# Kept for the project scripts, which run from a clone of the repository.
PROJECT_ROOT = project_root()
DEFAULT_PARAMS = PROJECT_ROOT / "config" / "params.yaml"
SITES_DIR = PROJECT_ROOT / "config" / "sites"


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} not found. Pass an explicit path, or set NISAR_S1_ROOT to a folder "
            "containing config/params.yaml and config/sites/.")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_params(path: str | Path | None = None) -> dict[str, Any]:
    """Read the YAML parameter file (default ``<root>/config/params.yaml``) and expand ``~`` in
    the ``chemins`` section."""
    params = _read_yaml(Path(path) if path else project_root() / "config" / "params.yaml")
    for key, value in params.get("chemins", {}).items():
        params["chemins"][key] = str(Path(value).expanduser())
    return params


def bbox_to_wkt(bbox: list[float] | tuple[float, float, float, float]) -> str:
    """Convert ``[lon_min, lat_min, lon_max, lat_max]`` (WGS84) to a closed WKT polygon."""
    x0, y0, x1, y1 = bbox
    return f"POLYGON(({x0} {y0},{x1} {y0},{x1} {y1},{x0} {y1},{x0} {y0}))"


def search_aoi_wkt(params: dict[str, Any] | None = None) -> str:
    """WKT of the search footprint defined in ``aoi_recherche.bbox_wgs84``."""
    params = params or load_params()
    return bbox_to_wkt(params["aoi_recherche"]["bbox_wgs84"])


def load_site(name: str | Path, root: str | Path | None = None) -> dict[str, Any]:
    """Read a site study file (AOI, CRS, periods, sensors).

    ``name`` is either a site name, read from ``<root>/config/sites/<name>.yaml``, or a path to a
    YAML file. Relative paths in ``chemins`` are made absolute against ``root`` (default:
    :func:`project_root`) and ``~`` is expanded, so every script of the site writes to its own
    results and data folders.
    """
    base = Path(root).expanduser().resolve() if root else project_root()
    candidate = Path(name)
    if candidate.suffix in (".yaml", ".yml"):
        path = candidate.expanduser()
    else:
        path = base / "config" / "sites" / f"{name}.yaml"
    site = _read_yaml(path)
    paths = site.setdefault("chemins", {})
    for key, value in paths.items():
        p = Path(str(value)).expanduser()
        paths[key] = str(p if p.is_absolute() else base / p)
    return site


def load_kit(path: str | Path | None = None, root: str | Path | None = None) -> dict[str, Any]:
    """Read the training-notebook configuration (default ``<root>/notebooks/kit_config.yaml``).

    Adds resolved paths: ``data_dir`` (default ``<chemins.data_root>/kit``, created if needed),
    ``session_file``, ``gcov.local`` and ``gcov.url`` (granule substituted), and
    ``aoi.site_polygons`` made absolute. Data never go into the repository."""
    base = Path(root).expanduser().resolve() if root else project_root()
    kit = _read_yaml(Path(path) if path else base / "notebooks" / "kit_config.yaml")
    data = kit.get("data_dir") or Path(load_params(base / "config" / "params.yaml")["chemins"]["data_root"]) / "kit"
    data = Path(data).expanduser()
    data.mkdir(parents=True, exist_ok=True)
    kit["data_dir"] = str(data)
    kit["session_file"] = str(data / "session.json")
    g = kit["gcov"]
    g["local"] = str(data / "gcov" / f"{g['granule']}.h5")
    g["url"] = g["url"].format(granule=g["granule"])
    poly = Path(kit["aoi"]["site_polygons"]).expanduser()
    kit["aoi"]["site_polygons"] = str(poly if poly.is_absolute() else base / poly)
    return kit
