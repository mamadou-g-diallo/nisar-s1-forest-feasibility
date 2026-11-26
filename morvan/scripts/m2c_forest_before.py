"""Morvan step 2c — was the parcel a standing forest before the cut? (independent of the radar)

NDVI cannot tell a closed canopy from a young plantation, regrowth or herbaceous cover (all have
NDVI >= 0.7 in summer). The short-wave infrared (Sentinel-2 B11, 1.6 um) can: a closed canopy is
dark (shadowing, high water content), low vegetation is brighter. For each photo-interpreted
reference object of the radar window, the median "before" B11 reflectance inside the object is
compared with the BD Forêt forest ring around it (100-400 m, stable NDVI). An object is
"standing forest before" if its B11 is not above the 90th percentile of its ring.

Output: ``morvan/results/tables/s2_forest_before.csv`` (merged into the photo-check verdicts).
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio.enums import Resampling
from shapely.geometry import shape

from nisar_s1.config import load_site
from nisar_s1.grid import polygon_mask
from nisar_s1.ign import forest_classes
from nisar_s1.optical import Raster, _read, search_s2


def main() -> None:
    s = load_site("morvan")
    res, data = Path(s["chemins"]["results"]), Path(s["chemins"]["data_root"])
    crs = s["site"]["crs"]
    ref = gpd.read_file(res / "s2_coupes_guide.gpkg", layer="reference")
    verdict = pd.read_csv(res / "tables" / "s2_photo_check_window.csv")
    objs = ref.merge(verdict[["id", "verdict"]], on="id")
    objs = objs[objs.verdict != "sans_sol_nu"].reset_index(drop=True)
    forest = forest_classes(gpd.read_file(data / "ign" / "bdforet_g23.gpkg"), s["bdforet"]["prefixes_foret"])
    ll = objs.to_crs(4326)
    items = search_s2(list(ll.total_bounds), *map(str, s["periode"]["s2_avant"]), max_cloud=5)
    rows = []
    for i, r in objs.iterrows():
        c = ll.geometry.iloc[i].centroid
        cand = items[[shape(it.geometry).contains(c) for it in items["item"]]].sort_values("cloud")
        best = None
        for it in cand["item"][:4]:
            epsg = it.properties.get("proj:epsg") or int(it.properties["proj:code"].split(":")[1])
            g = gpd.GeoSeries([r.geometry], crs=crs).to_crs(epsg).iloc[0]
            x0, y0, x1, y1 = g.buffer(450).bounds
            x0, y0 = np.floor(x0 / 20) * 20, np.floor(y0 / 20) * 20
            x1, y1 = np.ceil(x1 / 20) * 20, np.ceil(y1 / 20) * 20
            shp = (int((y1 - y0) / 20), int((x1 - x0) / 20))
            off = 0 if it.properties.get("earthsearch:boa_offset_applied", True) else 1000
            b11 = _read(it.assets["swir16"].href, (x0, y0, x1, y1), shp, Resampling.average)
            scl = _read(it.assets["scl"].href, (x0, y0, x1, y1), shp, Resampling.nearest)
            grid = Raster(b11.data.astype("float32"), b11.transform, b11.crs)
            inside = polygon_mask([g], grid)
            ring = polygon_mask([g.buffer(400)], grid) & ~polygon_mask([g.buffer(100)], grid)
            fr = forest.to_crs(epsg).clip(g.buffer(450))
            ring &= polygon_mask(list(fr.geometry), grid) if len(fr) else ring
            ok = np.isin(scl.data, (4, 5))
            v_in = (b11.data[inside & ok] - off) / 1e4
            v_ring = (b11.data[ring & ok] - off) / 1e4
            if v_in.size > 5 and v_ring.size > 30:
                best = (it.properties["datetime"][:10], np.median(v_in), np.median(v_ring),
                        np.percentile(v_ring, 90))
                break
        if best is None:
            rows.append({"id": r.id, "verdict": r.verdict, "groupe": r.groupe})
            continue
        d, m_in, m_ring, p90 = best
        rows.append({"id": r.id, "verdict": r.verdict, "groupe": r.groupe, "area_ha": r.area_ha,
                     "date_avant": d, "b11_objet": round(m_in, 4), "b11_anneau_med": round(m_ring, 4),
                     "b11_anneau_p90": round(p90, 4), "foret_avant": bool(m_in <= p90)})
        print(f"[{i + 1}/{len(objs)}] {r.id} {r.verdict} : B11 {m_in:.3f} (anneau {m_ring:.3f}, p90 {p90:.3f})"
              f" -> {'forêt' if m_in <= p90 else 'NON forêt fermée'}", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(res / "tables" / "s2_forest_before.csv", index=False)
    print(out.groupby(["verdict", "foret_avant"]).size().to_string())


if __name__ == "__main__":
    main()
