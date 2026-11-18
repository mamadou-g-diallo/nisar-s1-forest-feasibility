#!/usr/bin/env bash
# Test fonctionnel de SNAP gpt sans données SAR :
# 1) crée un petit GeoTIFF synthétique (200x200, UTM 32N ~ Vosges) avec l'env conda nisar_s1
# 2) applique un graphe gpt Read > BandMaths > Write (snap_graphs/test_bandmaths.xml) (sigma0 dB fictif) et écrit un GeoTIFF
# 3) vérifie la sortie avec gdalinfo
set -euo pipefail
GPT="${GPT:-$(command -v gpt || echo "$HOME/esa-snap/bin/gpt")}"
WORK="$(mktemp -d -t gpt_test_XXXX)"
echo "== gpt     : $GPT"
echo "== dossier : $WORK"

conda run --no-capture-output -n nisar_s1 python "$(dirname "$0")/make_test_raster.py" "$WORK/in.tif"
test -s "$WORK/in.tif" || { echo "ERREUR : GeoTIFF d'entrée non créé"; exit 1; }

echo "== Lancement de gpt BandMaths..."
GRAPH="$(dirname "$0")/../../snap_graphs/test_bandmaths.xml"
time "$GPT" "$GRAPH" -q 2 -Pinput="$WORK/in.tif" -Poutput="$WORK/out.tif"

echo "== Vérification de la sortie"
conda run -n nisar_s1 gdalinfo -stats "$WORK/out.tif" | grep -E "Size is|EPSG\",32632|STATISTICS_(MINIMUM|MAXIMUM|MEAN)" | head -6
echo "== TEST GPT OK"
