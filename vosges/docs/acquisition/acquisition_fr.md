# Étape 4 — Acquisition des données NISAR et Sentinel-1

*English version: [acquisition_en.md](acquisition_en.md)*

## Contrainte : débit réseau

Débit mesuré depuis Earthdata : **≈ 1,8 Mo/s par connexion**. Un GUNW NISAR fait 2,4 Go et un GCOV 2,1 Go
(≈ 20 min chacun) ; un SLC Sentinel-1 fait 4,6 Go (≈ 45 min). Tout télécharger (≈ 60 produits NISAR et
13 SLC) aurait pris environ 30 h. Deux techniques réduisent ce volume sans perte d'information pour le site.

## NISAR : lecture de fenêtres à distance (`vosges/scripts/04_fetch_nisar.py`, module `io_nisar`)

Les produits NISAR L2 (HDF5, produits par ISCE3) sont **découpés en blocs (chunks) de 512 × 512 pixels**,
sur une grille UTM 32N à 20 m. Le module `io_nisar` ouvre le fichier directement sur l'URL HTTPS Earthdata
(`earthaccess` + `fsspec` + `h5py`) et ne lit que les blocs qui couvrent la fenêtre du site
(site + 1,5 km, ≈ 3,7 × 3,7 km) : **≈ 15 s par couche au lieu de ≈ 20 min par fichier**. Les sous-scènes
sont enregistrées en GeoTIFF sur le disque externe, avec la provenance (nom du granule) dans
`vosges/results/tables/nisar_extracted.csv`.

Couches extraites :

| Produit | Couche (fréquence A, 20 MHz) | Résolution |
|---|---|---|
| GCOV | γ⁰ HH (`HHHH`), γ⁰ HV (`HVHV`), corrigés du relief (RTC) | 20 m |
| GUNW | cohérence `wrappedInterferogram/HH/coherenceMagnitude` | 20 m |
| GUNW | cohérence, phase déroulée, composantes connexes (`unwrappedInterferogram`) | 80 m |

Toutes les géométries dont l'emprise contient entièrement la fenêtre sont utilisées :

| Géométrie | GCOV (dates) | GUNW 12 j | GUNW 24 j (paire sur la coupe) |
|---|---|---|---|
| A144 F26 (montante) | 11 (24/06 → 03/11) | 8 | 18/07 → 11/08 |
| A72 F26 (montante) | 10 (19/06 → 10/11) | 8 | 25/07 → 18/08 |
| D138 F64 (descendante) | 11 (05/07 → 02/11) | 7 | 17/07 → 10/08 |

Remarques :
- dans les trois géométries, **la paire qui encadre la coupe est une paire de 24 jours** (une acquisition
  manque fin juillet) ; il n'existe pas de paire de 12 jours sur la coupe ;
- D66 F64 n'a qu'un GCOV, dans une autre projection : non utilisé ;
- les URL CloudFront signées expirent : le script relance la lecture avec une nouvelle session.

## Sentinel-1 : SAFE réduits (`vosges/scripts/04_fetch_s1.py`, module `download`)

- Orbite **D139** (descendante, 05:42 UTC), sous-fauchée **IW2** (trouvée par le catalogue de bursts ASF),
  VV + VH.
- Chaîne de **13 dates espacées de 12 jours** (14/06 → 06/11/2026), même intervalle que NISAR :
  S1A jusqu’au 26/06, puis S1C (paire de transition 26/06 → 09/07 : 13 jours).
- Le zip distant est lu par requêtes HTTP partielles (`HttpRangeFile`) : seuls le manifeste, les annotations,
  la calibration, le bruit et les mesures de IW2 sont extraits. **1,58 Go au lieu de 4,6 Go par date**.
  Trois flux en parallèle (`--shard`), ≈ 1,1 Mo/s chacun.
- SNAP lit ces SAFE réduits en mode une sous-fauchée (`enableSingleSwathMode` de TOPSAR-Split).

## Reproduire

```bash
python vosges/scripts/04_fetch_nisar.py
python vosges/scripts/04_fetch_s1.py --start 2026-06-14 --end 2026-11-07 --shard 0/3   # idem 1/3 et 2/3
```

Les données restent sur le disque externe (`/media/dell/Transcend1/nisar_data`), jamais dans Git.
