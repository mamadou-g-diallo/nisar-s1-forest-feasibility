"""Morvan step 1 — IGN layers: outline of the sylvo-ecoregion G23 and BD Forêt V2 inside it.

Outputs: ``results/morvan/zone_g23.geojson`` (outline, versioned) and
``<data_root>/ign/bdforet_g23.gpkg`` (forest polygons with a feuillus / résineux group).
"""

from __future__ import annotations

from pathlib import Path

from nisar_s1.config import load_site
from nisar_s1.ign import forest_classes, ser_outline, wfs_bbox


def main() -> None:
    s = load_site("morvan")
    res, data = Path(s["chemins"]["results"]), Path(s["chemins"]["data_root"])
    (data / "ign").mkdir(parents=True, exist_ok=True)
    res.mkdir(parents=True, exist_ok=True)
    zone = ser_outline(s["site"]["ser_archive"], s["site"]["ser_code"]).to_crs(s["site"]["crs"])
    zone.to_file(res / "zone_g23.geojson", driver="GeoJSON")
    print(f"G23 : {zone.area.iloc[0] / 1e6:.0f} km2, emprise {zone.total_bounds.round(0)}")

    out = data / "ign" / "bdforet_g23.gpkg"
    if not out.exists():
        bdf = wfs_bbox(s["bdforet"]["wfs"], s["bdforet"]["couche"], tuple(zone.total_bounds))
        bdf = bdf.clip(zone.geometry.iloc[0])
        bdf.to_file(out, layer="bdforet_v2", driver="GPKG")
    import geopandas as gpd
    bdf = gpd.read_file(out)
    print(f"BD Forêt V2 : {len(bdf)} polygones dans G23")
    print((bdf.assign(ha=bdf.area / 1e4).groupby("tfv").ha.sum().sort_values(ascending=False)
           .head(15).round(0)).to_string())
    f = forest_classes(bdf, s["bdforet"]["prefixes_foret"])
    print("\nForêt retenue par groupe (ha) :")
    print(f.assign(ha=f.area / 1e4).groupby("groupe").ha.sum().round(0).to_string())


if __name__ == "__main__":
    main()
