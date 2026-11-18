# Étape 1 — Cadrage

*🇬🇧 English version: [cadrage_en.md](cadrage_en.md)*

*Test de faisabilité préparatoire au stage SERTIT/ICube « Exploration des bandes L et P (NISAR, BIOMASS) pour la détection de la déforestation et des glissements de terrain ».*

## 1. Question et hypothèses

**Question.** Sur une coupe rase récente des Vosges / d'Alsace (juin–novembre 2026), la cohérence
interférométrique et la rétrodiffusion **NISAR (bande L, λ ≈ 24 cm)** distinguent-elles mieux la coupe
de la forêt intacte que **Sentinel-1 (bande C, λ ≈ 5,6 cm)** ?

**Hypothèses à tester.**

| # | Hypothèse | Justification physique |
|---|-----------|------------------------|
| H1 | La cohérence en forêt intacte est plus élevée en bande L qu'en bande C, à même intervalle temporel (12 j). | La bande L pénètre le couvert et rétrodiffuse surtout sur les troncs et les grosses branches, qui sont stables. La bande C est dominée par le feuillage, qui bouge (décorrélation temporelle). |
| H2 | L'écart de cohérence « coupe − forêt » est donc plus marqué en bande L. | En bande C, la forêt est déjà peu cohérente : le contraste avec la coupe (sol nu, souvent plus cohérent) est faible. |
| H3 | La baisse de rétrodiffusion après la coupe est plus forte en bande L, surtout en HV. | La disparition des troncs supprime la diffusion de volume et la double réflexion tronc-sol. La bande C sature sur forêt dense. |
| H4 | La polarisation croisée (HV, et le rapport HV/HH) est l'indicateur radar le plus sensible à la coupe. | HV est lié à la diffusion de volume, c'est-à-dire à la biomasse. |

## 2. Périmètre

**Inclus :**
- un site de coupe rase confirmé par Sentinel-2, avec une forêt intacte de référence voisine ;
- Sentinel-1 IW SLC → cohérence et γ⁰ (SNAP, petite zone : TOPSAR-Split, 2–3 bursts) ;
- NISAR L2 **GUNW** (cohérence) et **GCOV** (γ⁰ HH, HV) ;
- validation par différence de NDVI Sentinel-2.

**Inventorié mais non traité sur ce site :**
- **BIOMASS (bande P)** : d'après la fiche de stage, il n'acquiert pas sur l'Europe de l'Ouest. L'inventaire
  (étape 2) le documentera avec la carte de couverture, et la bande P restera une perspective (forêt tropicale par exemple).

**Hors périmètre, en perspective dans le rapport :**
- interférogrammes NISAR vs S1 sur versant boisé touché par un glissement de terrain (phase déroulée, déplacement) ;
- dégâts de tempête ; polarimétrie complète (décompositions) ; quantification de la biomasse ;
- ROSE-L (Copernicus, lancement prévu en 2028) : la chaîne bande L développée ici doit lui être transposable.

## 3. Données (détails à confirmer à l'étape 2)

| Capteur | Produit | Grandeurs utilisées | Points à vérifier à l'inventaire |
|---------|---------|---------------------|-----------------------------------|
| Sentinel-1 (C) | IW SLC (ASF) | cohérence VV/VH ; γ⁰ VV/VH (aplanissement topographique) | orbites relatives couvrant le site ; répétitivité 6/12 j selon les satellites actifs (S1A, S1C, S1D) |
| NISAR (L) | L2 GUNW | cohérence | disponibilité réelle sur la zone ; résolution de la couche de cohérence ; intervalles 12 j disponibles |
| NISAR (L) | L2 GCOV | γ⁰ HH, HV (RTC), rapport HV/HH | mode et polarisations acquis sur l'Europe ; résolution ; dates |
| BIOMASS (P) | L1/L2 | — | couverture (attendue nulle sur la zone) |
| Sentinel-2 | L2A | NDVI avant / après, différence de NDVI | dates sans nuages (automne vosgien nuageux) |
| Optionnel | ASF HyP3 (cohérence S1 calculée à la demande) | cohérence S1 de contrôle | utile si SNAP sature la RAM |

## 4. Méthode

1. **Site** (étape 3) : coupe rase de **≥ 5 ha si possible**. La couche de cohérence GUNW peut être à
   résolution grossière (à confirmer), et une petite coupe ne contiendrait que quelques pixels.
   Il faut aussi une date de coupe encadrée par des images S2 claires, et une forêt intacte témoin voisine,
   de même type de peuplement, pente et exposition.
2. **Polygones** : coupe (`dNDVI` < seuil, à calibrer, environ −0,2) et forêt intacte. Les deux sont réduits
   vers l'intérieur d'un pixel radar pour éviter les effets de bord.
3. **Comparabilité S1 / NISAR**
   - même **intervalle temporel** (12 j) pour la cohérence, en comparant des paires prises avant et après la coupe ;
   - **γ⁰ à aplanissement topographique** des deux côtés : GCOV est déjà RTC, et S1 passe par Terrain-Flattening dans SNAP ;
   - rééchantillonnage sur une **grille commune** (UTM 32N), à la résolution la plus grossière des deux capteurs ;
   - prise en compte de la géométrie (orbite ascendante ou descendante, angle d'incidence) et de la météo (pluie, neige en novembre).
4. **Indicateurs** : pour chaque capteur, chaque variable (cohérence, γ⁰ co- et cross-polarisé, rapport HV/HH)
   et chaque date (avant ou après la coupe) :
   - écart moyen coupe − forêt (Δγ, Δγ⁰ en dB) et taille d'effet (d de Cohen) ;
   - séparabilité : **AUC** (courbe ROC) et **distance de Jeffries-Matusita** ;
   - série temporelle sur chaque polygone, pour voir à quelle date la coupe apparaît.
5. **Détection automatique (prototype)** : seuillage (Otsu ou seuil choisi sur la ROC) d'un indicateur de
   changement (rapport avant/après de γ⁰, chute de cohérence). La carte obtenue est comparée à la référence
   NDVI : précision, rappel, F1. Il s'agit d'une première brique vers les « cartes de suivi des zones sensibles ».

## 5. Critère de réussite

La bande L « distingue mieux » la coupe si, avec des intervalles et des dates comparables, son **AUC (ou sa
distance JM) est nettement supérieure** à celle de la bande C pour au moins une variable, et si ce gain se
retrouve dans le F1 du prototype de détection. Un résultat négatif ou non concluant (données NISAR
indisponibles, coupe trop petite) est **un résultat de faisabilité valable** et sera documenté comme tel.

## 6. Risques

| Risque | Conséquence | Parade |
|--------|-------------|--------|
| Peu ou pas de produits NISAR GUNW/GCOV sur la zone et la période | Comparaison impossible | Inventaire tôt (étape 2) ; élargir la zone (Vosges du Nord, Forêt-Noire) ou la période |
| Résolution NISAR grossière face à la taille des coupes | Mélange de pixels | Choisir une grande coupe ; regrouper plusieurs coupes |
| RAM limitée (~8 Go) | SNAP bloqué | TOPSAR-Split sur 2–3 bursts, sous-zone, `-Xmx5G` ; HyP3 en secours |
| Nuages et neige en automne | Référence S2 ou cohérence dégradées | Fenêtres de dates élargies ; noter la météo |
| Relief vosgien (zones de recouvrement et d'ombre radar) | Biais de γ⁰ | Aplanissement topographique ; masque des zones de recouvrement et d'ombre ; témoin de même pente et exposition |

## 7. Correspondance avec la fiche de stage

| Mission de la fiche | Traitement dans ce test |
|---------------------|------------------------|
| Recenser les produits NISAR / BIOMASS (niveaux, polarisations, couverture, répétitivité) et les outils | Étape 2 (+ outils : asf_search, earthaccess, h5py, SNAP, ISCE3 cité) |
| Choisir des sites avec coupes rases observés par S1 et NISAR / BIOMASS | Étape 3 |
| Comparer la détection de la déforestation S1 / NISAR / BIOMASS | Étape 5 (BIOMASS : constat de non-couverture) |
| Tester l'apport de la polarimétrie | HH / HV / HV÷HH (GCOV) |
| Comparer les interférogrammes sur versants boisés touchés par des glissements | Perspective (aperçu qualitatif de la cohérence sur versant si le temps le permet) |
| Adapter la chaîne de traitement à la bande L | Modules réutilisables dans `src/nisar_s1/` (voir § 9) |
| Méthode de détection automatique | Prototype par seuillage + évaluation F1 |
| Préparer ROSE-L | Chaîne indépendante du capteur (§ 9) ; ROSE-L (2028) et ISCE3 cités dans le rapport |

## 8. Livrables et calendrier indicatif

Les livrables destinés à être lus (rapport, documents d'étape, README) existent en **deux versions complètes, française et anglaise**.

| Étape | Livrable |
|-------|----------|
| 2. Inventaire | `docs/inventaire/inventaire_fr.md` + `inventaire_en.md` + `results/tables/inventaire_*.csv` |
| 3. Site | `config/site.geojson` (coupe + témoin) + figure NDVI |
| 4. Téléchargement | `scripts/04_download.py` (appelle `nisar_s1.download`), journal des fichiers |
| 5. Traitement | graphes SNAP, modules `src/nisar_s1/`, tables de statistiques, figures |
| 6. Rapport | `reports/latex/rapport_fr.tex` **et** `reports/latex/report_en.tex` (deux rapports complets) |

## 9. Chaîne réutilisable (préparation de ROSE-L)

Le code n'est **pas** un ensemble de scripts jetables. Toute la logique se trouve dans le paquet importable
`src/nisar_s1/`. Les fichiers de `scripts/` et les notebooks ne font qu'appeler ces modules avec les
paramètres de `config/params.yaml`.

| Module | Rôle | Réutilisation visée |
|--------|------|---------------------|
| `config.py` | lecture de `params.yaml`, chemins | tout le projet |
| `search.py` / `download.py` | recherche et téléchargement ASF (asf_search, earthaccess) par emprise et période | autres sites ; ROSE-L via ASF ou Copernicus |
| `io_nisar.py` | lecture des produits NISAR L2 **GUNW** (cohérence, phase) et **GCOV** (γ⁰ HH/HV) en HDF5 → `xarray` géoréférencé | toute donnée NISAR ; modèle pour un lecteur ROSE-L |
| `io_s1.py` | lecture des sorties SNAP (BEAM-DIMAP/GeoTIFF) → `xarray` | chaîne S1 existante |
| `snap.py` | lancement des graphes `gpt` paramétrés (`snap_graphs/*.xml`) | toute chaîne SNAP |
| `grid.py` | reprojection et rééchantillonnage sur une grille commune | comparaison multi-capteurs |
| `stats.py` | statistiques par polygone, Δ, d de Cohen, AUC, distance de Jeffries-Matusita | toute comparaison coupe/témoin |
| `detect.py` | détection de changement par seuillage + évaluation (précision, rappel, F1) | cartes de suivi des zones sensibles |
| `plots.py` | figures standardisées | rapport |

**Principes :**
- fonctions documentées en anglais (docstrings) et typées, sans chemins écrits en dur ;
- un lecteur par **format de produit**, et non par étude, pour qu'un futur lecteur ROSE-L se branche sur `grid`, `stats` et `detect` sans les modifier ;
- tests minimaux (`tests/`) sur données synthétiques, comme le test `gpt` déjà en place.

Le rapport situera cette chaîne par rapport à **ISCE3** (logiciel de traitement officiel de NISAR, qui produit
GUNW et GCOV) et à **ROSE-L** (mission Copernicus en bande L, lancement prévu en 2028), pour laquelle elle doit rester transposable.
