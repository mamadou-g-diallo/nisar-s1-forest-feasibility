"""Configuration lookup: explicit path, NISAR_S1_ROOT, missing files (no network)."""
from pathlib import Path

import pytest

from nisar_s1 import config

SITE_YAML = """nom: test
chemins:
  results: results/test
  data: ~/donnees_test
"""
PARAMS_YAML = """aoi_recherche:
  bbox_wgs84: [-16.4, 12.5, -16.2, 12.7]
chemins:
  data: ~/donnees
"""


def _make_root(tmp_path: Path) -> Path:
    (tmp_path / "config" / "sites").mkdir(parents=True)
    (tmp_path / "config" / "sites" / "test.yaml").write_text(SITE_YAML)
    (tmp_path / "config" / "params.yaml").write_text(PARAMS_YAML)
    return tmp_path


def test_load_site_from_explicit_yaml_path(tmp_path):
    root = _make_root(tmp_path)
    site = config.load_site(root / "config" / "sites" / "test.yaml", root=root)
    assert site["chemins"]["results"] == str(root / "results" / "test")
    assert site["chemins"]["data"] == str(Path("~/donnees_test").expanduser())


def test_root_from_environment_variable(tmp_path, monkeypatch):
    root = _make_root(tmp_path)
    monkeypatch.setenv("NISAR_S1_ROOT", str(root))
    assert config.project_root() == root.resolve()
    assert config.load_site("test")["chemins"]["results"] == str(root.resolve() / "results" / "test")
    params = config.load_params()
    assert config.search_aoi_wkt(params).startswith("POLYGON((-16.4 12.5")


def test_missing_file_gives_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv("NISAR_S1_ROOT", str(tmp_path))
    with pytest.raises(FileNotFoundError, match="NISAR_S1_ROOT"):
        config.load_site("absent")


def test_bbox_to_wkt_is_closed():
    wkt = config.bbox_to_wkt([0, 1, 2, 3])
    assert wkt == "POLYGON((0 1,2 1,2 3,0 3,0 1))"
