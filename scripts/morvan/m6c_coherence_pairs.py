"""Per-pair median coherence of the verified closed-stand cuts and of intact forest (all geometries).

Output: results/morvan/tables/m6_coherence_pairs.csv. Run from the repository root."""
import sys, numpy as np, pandas as pd, geopandas as gpd
from pathlib import Path
sys.path.insert(0, "scripts/morvan")
import m6_compare as M
s = M.load_site("morvan"); res, data = Path(s["chemins"]["results"]), Path(s["chemins"]["data_root"])
win = gpd.read_file(res/"fenetre_radar.geojson").to_crs(s["site"]["crs"])
grid = M.make_grid(tuple(win.total_bounds), s["site"]["grille_m"], s["site"]["crs"])
group = np.nan_to_num(M.to_grid(M.load_raster(data/"s2"/"forest_group_l93.tif"), grid, "nearest").data).astype(int)
dndvi = M.to_grid(M.load_raster(data/"s2"/"dndvi_l93.tif"), grid, "nearest").data
thr = pd.read_csv(res/"tables"/"s2_guide_thresholds.csv").iloc[0]
deg = np.nan_to_num(M.to_grid(M.load_raster(data/"s2"/"degres_s2_l93.tif"), grid, "nearest").data).astype(int)
ref = gpd.read_file(res/"s2_coupes_guide.gpkg", layer="reference")
v = pd.read_csv(res/"tables"/"s2_photo_check_window.csv").set_index("id").verdict
fb = pd.read_csv(res/"tables"/"s2_forest_before.csv").set_index("id").foret_avant
ref = ref[(ref.id.map(v) == "coupe") & ref.id.map(fb).fillna(False).astype(bool)]
forest = (group > 0) & np.isfinite(dndvi)
cut = M.polygon_mask(list(ref.geometry), grid) & forest
intact = forest & (deg == 0) & (np.abs(dndvi - thr.m) <= thr.sigma) & ~cut
g = {}; g.update(M.nisar_layers(data/"nisar", grid)); g.update(M.s1_layers(data/"processed"/"sentinel1", grid))
rows = []
for geom, L in g.items():
    for l in L:
        if l["kind"] != "coh" or l["pol"] not in ("HH", "VV"): continue
        rows.append(dict(geom=geom, d1=l["d1"].date(), d2=l["d2"].date(), jours=(l["d2"]-l["d1"]).days,
                         foret=np.nanmedian(l["data"][intact]), coupe=np.nanmedian(l["data"][cut])))
df = pd.DataFrame(rows).sort_values(["geom", "d1"]); print(df.round(2).to_string(index=False))
df.to_csv(res/"tables"/"m6_coherence_pairs.csv", index=False)
