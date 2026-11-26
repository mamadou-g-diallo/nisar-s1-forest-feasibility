"""Crée un petit GeoTIFF synthétique (200x200, UTM 32N) pour tester SNAP gpt."""
import sys
import numpy as np
import rasterio
from rasterio.transform import from_origin

a = np.random.default_rng(0).gamma(2, 0.05, (200, 200)).astype("float32")
with rasterio.open(sys.argv[1], "w", driver="GTiff", width=200, height=200, count=1,
                   dtype="float32", crs="EPSG:32632",
                   transform=from_origin(370000, 5370000, 10, 10)) as d:
    d.write(a, 1)
print("== GeoTIFF d'entrée créé :", sys.argv[1])
