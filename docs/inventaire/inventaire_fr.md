# Étape 2 — Inventaire des produits (Sentinel-1, NISAR, BIOMASS)

*🇬🇧 English version: [inventaire_en.md](inventaire_en.md)*

*Emprise de recherche : Vosges / Alsace, bbox `[6.70, 47.70, 7.70, 48.80]` (WGS84). Période : 2026-06-01 → 2026-11-30.
Catalogue interrogé le 2026-11-18 via ASF (`asf_search` 14.1). Reproduction : `python scripts/02_inventory.py` ;
tableaux dans `results/tables/inventory_*.csv`.*

## 1. Résultats principaux

1. **Des données NISAR existent sur la zone et la période** : 546 produits, tous niveaux confondus, dont **93 GCOV** et
   **67 GUNW** (du 18 juin au 10 novembre 2026). La comparaison bande L / bande C est faisable.
2. **Deux géométries NISAR couvrent toute la zone de recherche** : ascendante **trace 144 / cadre 26** et descendante
   **trace 138 / cadre 64** (100 % de l'emprise), plus l'ascendante **trace 72 / cadre 26** (97 %).
   Les trois acquièrent en mode **20+5 MHz, double polarisation HH/HV**.
3. **La résolution est compatible avec la taille des coupes** : GCOV est à **20 m** (bande principale de 20 MHz) ou à
   10 m (40 MHz), et GUNW fournit une **cohérence à 20 m** (et à 80 m). Une coupe de 5 ha couvre environ 125 pixels à 20 m.
4. **GUNW n'existe qu'en co-polarisation (HH)** et entre acquisitions successives (**12 jours**, 24 jours quand une
   acquisition manque). L'information HV ne vient donc que de la **rétrodiffusion GCOV**, pas de la cohérence.
5. **Les GUNW s'arrêtent au 2026-10-26** (dernière date secondaire) à cause du délai de traitement, alors que GCOV va
   jusqu'au 10 novembre. Pour la cohérence, la coupe doit avoir eu lieu **entre fin juin et mi-octobre 2026**.
6. **La plupart des GUNW sont « provisional »** (`NISAR_L2_GUNW_PROVISIONAL_V1` : 64 sur 67). C'est une limite à signaler.
7. **Sentinel-1 est dense** : 263 IW SLC (VV+VH), 5 orbites relatives, revisite médiane de **6 jours** avec S1A, S1C et S1D.
   On peut donc former une cohérence S1 à **12 jours**, exactement comme NISAR.
8. **BIOMASS (bande P) est inutilisable ici** : les acquisitions sur l'Europe et l'Amérique du Nord sont bloquées par la
   zone d'exclusion du radar américain de surveillance spatiale (SOTR).

## 2. Sentinel-1 (bande C, λ ≈ 5,6 cm)

| Direction | Orbite relative | Acquisitions | Revisite médiane | Couverture max. de l'emprise | Satellites |
|-----------|-----------------|--------------|------------------|------------------------------|------------|
| Ascendante | 15 | 29 | 6 j | 70 % | S1A + S1C + S1D |
| Ascendante | 88 | 27 | 6 j | 92 % | S1A + S1C + S1D |
| Descendante | 37 | 29 | 6 j | 4 % | S1A + S1C + S1D |
| Descendante | 66 | 28 | 6 j | 48 % | S1A + S1C + S1D |
| Descendante | 139 | 31 | 6 j | **100 %** | S1A + S1C + S1D |

- Produit : IW SLC, VV+VH, environ **4,7 Go** par scène (médiane). Le traitement restera limité à 2–3 bursts (TOPSAR-Split).
- Répartition : S1D 125, S1C 116, S1A 22 scènes.
- « Acquisitions » compte des jours distincts ; un même jour peut contenir 2 scènes consécutives.

## 3. NISAR (bande L, λ ≈ 24 cm)

### 3.1 Produits disponibles sur la zone (tous niveaux)

| Niveau | Produit | Contenu | Mode (nombre) | Taille médiane |
|--------|---------|---------|---------------|----------------|
| L1 | RSLC | SLC en géométrie radar | 20+5 DH (55), 40+5 DH (35), SH (3) | 15–26 Go |
| L1 | RIFG / RUNW / ROFF | Interférogramme enroulé / déroulé, décalages (géométrie radar) | 20 ou 40 MHz, HH | 0,3–1,4 Go |
| L2 | GSLC | SLC géocodé | comme RSLC | 13–23 Go |
| L2 | **GCOV** | **Matrice de covariance γ⁰** géocodée et corrigée du relief (HHHH, HVHV) | 20+5 DH (55), 40+5 DH (35), SH (3) | **2,1 Go** (20+5), 7,2 Go (40+5) |
| L2 | **GUNW** | **Interférogramme déroulé + cohérence** géocodés | 20 MHz HH (44), 40 MHz HH (23) | **2,4 Go** |
| L2 | GOFF | Décalages de pixels géocodés | 20 ou 40 MHz HH | 1,2 Go |

Codes de mode dans les noms de fichiers : `2005` = bande principale de 20 MHz + bande secondaire de 5 MHz ;
`DHDH` = double polarisation HH/HV sur les deux bandes ; `SH` = HH seul.

### 3.2 GCOV — revisite par géométrie

| Direction | Trace | Cadre | Acquisitions | Revisite | Couverture | Mode |
|-----------|-------|-------|--------------|----------|------------|------|
| Ascendante | **144** | **26** | 11 | 12 j | **100 %** | 20+5 DH |
| Ascendante | 72 | 26 | 12 | 12 j | 97 % | 20+5 DH |
| Ascendante | 72 | 25 | 12 | 12 j | ~15 % | 40+5 DH |
| Descendante | **138** | **64** | 10 | 12 j | **100 %** | 20+5 DH |
| Descendante | 66 | 64 | 12 | 12 j | ~22 % | 20+5 DH |
| Descendante | 37 | 64 | 11 | 12 j | ~15–30 % | 20+5 / 40+5 DH |
| Descendante | 37 | 65 | 11 | 12 j | ~10 % | 40+5 DH |

GCOV est déjà **corrigé radiométriquement du relief (γ⁰, RTC par surface avec le MNT Copernicus)**. Une couche
`rtcGammaToSigmaFactor` permet de passer en σ⁰. Les produits double polarisation ne contiennent que les termes
diagonaux. Les termes hors diagonale (par exemple HH·HV*) devraient être recalculés à partir des GSLC, ce qui sort
du périmètre de ce test.

### 3.3 GUNW — paires interférométriques par géométrie

| Direction | Trace | Cadre | Paires à 12 j | Paires à 24 j | Première référence → dernière secondaire | Couverture |
|-----------|-------|-------|---------------|---------------|------------------------------------------|------------|
| Ascendante | **144** | **26** | 9 | 1 | 2026-06-24 → 2026-10-22 | **100 %** |
| Ascendante | 72 | 26 | 8 | 1 | 2026-06-19 → 2026-10-17 | 97 % |
| Descendante | **138** | **64** | 7 | 1 | 2026-07-05 → 2026-10-21 | **100 %** |
| Descendante | 37 | 64 | 16 | 2 | 2026-06-28 → 2026-10-26 | 30 % |
| Descendante | 66 | 64 | 8 | 1 | 2026-06-18 → 2026-10-16 | 23 % |
| Ascendante | 72 | 25 | 4 | 1 | 2026-06-19 → 2026-10-17 | 17 % |
| Descendante | 37 | 65 | 7 | 1 | 2026-06-28 → 2026-10-14 | 17 % |

Couches GUNW : phase déroulée à 80 m, interférogramme enroulé et **amplitude de cohérence à 20 m** (aussi à 80 m), et
un écran de phase ionosphérique (fourni, **non appliqué** par défaut). L'ionosphère compte pour la phase
(glissements de terrain), mais pas pour l'amplitude de cohérence.

## 4. BIOMASS (bande P, λ ≈ 70 cm)

- Les données sont ouvertes depuis la fin de la recette en orbite (janvier 2026).
- **Aucune acquisition sur l'Europe et l'Amérique du Nord** : le masque d'observation exclut la zone couverte par le
  radar américain de surveillance spatiale (SOTR). Cela confirme ce qu'indique la fiche de stage.
- Conséquence : BIOMASS **n'est pas utilisable sur ce site**. La bande P reste une perspective pour le stage, par
  exemple sur des sites de forêt tropicale, où elle apporterait la sensibilité à la biomasse (troncs, grosses branches).

## 5. Conséquences pour les étapes suivantes

| Point | Décision / contrainte |
|-------|-----------------------|
| Géométrie NISAR | Priorité à **A144/F26** et **D138/F64** (couverture totale, 20 m, double polarisation) ; A72/F26 en troisième |
| Géométrie Sentinel-1 | **D139** (100 %) et **A88** (92 %) ; même direction que NISAR quand c'est possible |
| Fenêtre de date de la coupe | **Fin juin → mi-octobre 2026** (disponibilité GUNW, paires avant *et* après la coupe) |
| Grille commune | **20 m**, UTM 32N (GCOV et cohérence GUNW à 20 m ; S1 moyenné à environ 20 m) |
| Intervalle temporel | **12 jours** pour les deux capteurs (la revisite S1 de 6 jours le permet) |
| Polarisations | Cohérence : NISAR HH vs S1 VV/VH. Rétrodiffusion : NISAR HH/HV/HV÷HH vs S1 VV/VH/VH÷VV |
| Volume à télécharger (étape 4) | GCOV ~2 Go, GUNW ~2,4 Go, S1 SLC ~4,7 Go chacun → quelques dizaines de Go sur le disque externe |
| Limites à signaler | GUNW provisoires ; GUNW en HH seul ; pas de BIOMASS ; heures d'acquisition différentes entre S1 et NISAR (passages du matin et du soir) |

## 6. Outils pour la chaîne de traitement

| Outil | Usage dans ce projet | Intérêt pour le SERTIT / ROSE-L |
|-------|----------------------|---------------------------------|
| `asf_search`, `earthaccess` | recherche dans le catalogue, téléchargement authentifié (`nisar_s1.search`) | même API pour toute mission hébergée par l'ASF |
| `h5py` / `xarray` | lecture des HDF5 GCOV/GUNW par fenêtre, pour limiter la mémoire | base de `nisar_s1.io_nisar` |
| SNAP 14 (`gpt`) | cohérence et γ⁰ S1 (TOPSAR-Split, Back-Geocoding, Coherence, Terrain-Flattening) | chaîne bande C existante du SERTIT |
| ISCE3 | processeur officiel de NISAR (produit GCOV, GUNW…) ; permettrait de former des paires sur mesure ou les termes hors diagonale à partir des RSLC/GSLC | voie probable pour traiter ROSE-L |
| ASF HyP3 | cohérence S1 calculée à la demande (solution de repli si la RAM limite) | — |

## Sources

- Documentation NISAR de l'ASF — GCOV : <https://nisar-docs.asf.alaska.edu/gcov/>
- Documentation NISAR de l'ASF — GUNW : <https://nisar-docs.asf.alaska.edu/gunw/>
- Catalogue NASA Earthdata, NISAR L2 GUNW (provisional) : <https://www.earthdata.nasa.gov/data/catalog/asf-nisar-l2-gunw-provisional-v1-1>
- JPL D-102272, spécification du produit NISAR L2 GUNW : <https://nisar.asf.earthdatacloud.nasa.gov/NISAR-SAMPLE-DATA/DOCS/NISAR_D-102272_L2_GUNW_Product_Spec_R3.4_231109_clean_w-sigs.pdf>
- K. Scipal, *Biomass Mission Overview* (ESA, 2026) : <https://eo-college.org/wp-content/uploads/2026/03/02_Biomass_Mission_Overview-Klaus-Scipal.pdf>
- ESA Earth Online — description de la mission Biomass : <https://earth.esa.int/eogateway/missions/biomass/description>
- BELSPO — « ESA's Biomass data now available » : <https://eo.belspo.be/en/news/esas-biomass-data-now-available>
