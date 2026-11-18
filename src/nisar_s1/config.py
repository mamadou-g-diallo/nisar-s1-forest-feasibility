"""Project configuration: load ``config/params.yaml`` and expose paths and the search footprint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PARAMS = PROJECT_ROOT / "config" / "params.yaml"


def load_params(path: str | Path = DEFAULT_PARAMS) -> dict[str, Any]:
    """Read the YAML parameter file and expand ``~`` in the ``chemins`` section."""
    with open(path, encoding="utf-8") as f:
        params = yaml.safe_load(f)
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
