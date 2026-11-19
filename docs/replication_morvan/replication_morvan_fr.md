# Réplication sur le Morvan (sylvo-écorégion G23) — méthode du guide IRSTEA et comparaison NISAR / Sentinel-1

*English version: [replication_morvan_en.md](replication_morvan_en.md)*

## 1. Pourquoi cette réplication

Le test des Vosges (version figée `v1.0-vosges`) portait sur **une seule coupe** (C11, 2,36 ha) et
une **seule orbite Sentinel-1** (descendante). Ses deux principales limites étaient donc la
généralisation (n = 1) et la comparaison à géométrie égale (une seule géométrie commune).

La réplication reprend la **zone d'étude du guide méthodologique de l'IRSTEA** :

> K. Ose, M. Deshayes (2015). *Détection et cartographie des coupes rases par télédétection
> satellitaire. Guide méthodologique*, v5.0, UMR TETIS – Irstea.

Ce guide a été établi pour le ministère de l'Agriculture et les DRAAF Rhône-Alpes et Bourgogne sur
deux sylvo-écorégions de l'IFN, dont **G23 « Morvan et Autunois »**. Il fixe une méthode
opérationnelle et des spécifications :
- unité minimale de 1 ha ;
- erreurs d'omission et de commission ≤ 10 % en surface ;
- projection Lambert 93.

La réplication s'en sert de deux façons :

1. comme **référence optique** (Sentinel-2), à la place du seuil ad hoc utilisé dans les Vosges ;
2. comme **méthode de détection transposée au radar**, ce qui permet d'évaluer NISAR et
   Sentinel-1 selon une norme opérationnelle française, et pas seulement par une AUC.

## 2. La méthode du guide en bref

Le guide procède en six étapes :

1. Deux images optiques d'été, à une année d'intervalle, converties en réflectance.
2. NDVI à chaque date, puis différence ΔNDVI = NDVI(n+1) − NDVI(n).
3. Masques : zone d'étude (sylvo-écorégion) et forêt (BD Topo ou BD Forêt).
4. Seuillage statistique dans la forêt, à partir de la moyenne m et de l'écart-type σ de ΔNDVI.
   Un pixel est une coupe candidate si ΔNDVI < m − σ, avec trois degrés de certitude :

   | Degré | Intervalle de ΔNDVI |
   |---|---|
   | 1 (faible) | [m − 2σ, m − σ[ |
   | 2 (moyen) | [m − 3σ, m − 2σ[ |
   | 3 (fort) | < m − 3σ |

   Le guide précise que le degré 1 contient surtout de fausses détections (ombres, effets atmosphériques).
5. Tamisage (filtre GDAL *Sieve*) à 1 ha, puis export vectoriel avec la surface et le degré.
6. Évaluation par matrice de confusion en surface :
   - précisions producteur et utilisateur ;
   - omission et commission ;
   - précision globale ;
   - kappa.

Le module réutilisable [`src/nisar_s1/guide_cr.py`](../../src/nisar_s1/guide_cr.py) implémente
ces étapes pour **n'importe quelle image de changement** : ΔNDVI, Δγ⁰ ou baisse de cohérence. Le
sens du changement est un paramètre, et le module est couvert par des tests.

## 3. Organisation

| Élément | Emplacement |
|---|---|
| Configuration du site | [`config/sites/morvan.yaml`](../../config/sites/morvan.yaml) (Lambert 93, grille 20 m, fenêtres temporelles, paramètres du guide) |
| Scripts | [`scripts/morvan/`](../../scripts/morvan) (`m1` à `m6`) |
| Résultats versionnés | `results/morvan/` (tables, figures, vecteurs) |
| Données volumineuses | disque externe, `nisar_data/morvan/` (non versionnées) |

## 4. Données IGN (étape m1)

- **Contour de G23** : fichier `ser_l93.zip` de l'inventaire forestier IGN, soit **3 011 km²**.
- **BD Forêt V2** : récupérée par le service WFS de la Géoplateforme, soit 13 494 polygones dans
  G23.
- **Forêt retenue** : forêts fermées et ouvertes avec couvert arboré, et peupleraies. La classe FF0
  (« forêt fermée sans couvert arboré », c'est-à-dire des coupes anciennes) et les landes sont
  exclues. On obtient environ **157 800 ha** :
  - 89 750 ha de feuillus ;
  - 49 400 ha de résineux, surtout du douglas ;
  - 18 600 ha de forêts mixtes.

## 5. Le guide appliqué à Sentinel-2 sur toute la G23 (étape m2)

**Composites NDVI.** Pour chaque tuile (31TEM, 31TEN, 31TFM, 31TFN), on prend la médiane des
3 dates les plus claires de chaque fenêtre :
- « avant » : 15/06 → 08/07/2026 ;
- « après » : 15/09 → 16/10/2026.

Les composites sont mosaïqués sur une grille Lambert 93 de 20 m. ΔNDVI est valide sur 92 % de la
forêt.

**Seuils du guide**, calculés dans la forêt de G23 : m = −0,040 et σ = 0,058, d'où :
- m − σ = −0,098 ;
- m − 2σ = −0,157 ;
- m − 3σ = −0,215.

**Résultat brut du guide.** On obtient 3 349 objets de 1 ha ou plus (13 600 ha), dont 3 089 de
degré 2 ou plus. Cela fait **8,7 % de la forêt en deux mois et demi**, une valeur non plausible : le
taux de coupe rase est de l'ordre de 1 % par an. Les détections sont surtout des feuillus (2 269
objets sur 3 089), qui jaunissent dès septembre (sénescence précoce, stress hydrique).

C'est la limite du guide transposé tel quel en **intra-saison**. Ses seuils m − kσ supposent que
la forêt non coupée a un ΔNDVI centré et étroit, ce qui est vrai pour deux images d'été à un an
d'intervalle, mais faux entre juillet et septembre.

> **Constat 1.** Les seuils statistiques du guide ne sont pas transposables sans adaptation à un
> suivi infra-annuel : la phénologie élargit la queue de la distribution de ΔNDVI et le degré
> « fort » ne suffit plus à isoler les coupes.

**Référence qualifiée.** Le guide demande de ne retenir que les parcelles « passées d'un état boisé
à un état sol nu » (section 2.2). La référence est donc :
- degré 3 du guide ;
- et NDVI avant ≥ 0,70 ;
- et NDVI après ≤ 0,65 ;
- puis tamisage à 1 ha.

On obtient **281 coupes (613 ha)** : 193 dans des feuillus, 67 dans des résineux, 21 dans des
forêts mixtes. La surface médiane est de 1,6 ha.

**Contrôle par photo-interprétation** (guide, section 3.9.1). Sur un échantillon aléatoire de
30 coupes de référence, comparées en couleurs vraies en juillet et en septembre
([figure](../../results/morvan/figures/s2_photo_check_reference.png),
[verdicts](../../results/morvan/tables/s2_photo_check.csv)) :
- 13 coupes certaines (sol nu brun) ;
- 6 probables ;
- 3 sans changement visible ;
- 8 non interprétables (nuage sur l'image « après »).

La **précision de la référence est donc de 59 % (certaines seules) à 86 % (avec les probables)**,
sur n = 22.

Les 3 erreurs sont toutes des **feuillus**, alors que les coupes certaines sont surtout des
résineux et des forêts mixtes. ΔNDVI ne sépare pas les vraies coupes des erreurs (entre −0,24 et
−0,51 dans les deux groupes).

> **Constat 2.** La référence optique est imparfaite, surtout en feuillus. Les scores radar
> mesurés contre elle sont donc des **bornes basses** : une partie de la « commission » radar est
> en réalité une erreur de la référence. L'analyse est aussi faite par groupe (feuillus / résineux).

## 6. Choix de la fenêtre radar (étape m3)

Le traitement de Sentinel-1 se fait par bursts (3 au maximum, à cause de la mémoire vive) et dans
une seule sous-fauchée. Les fenêtres candidates de 20 × 20 km ont été classées selon la surface de
coupes de référence qu'elles contiennent, puis contrôlées dans les catalogues ASF : bursts
Sentinel-1 et couverture complète par les trames NISAR.

Contrainte retenue : une orbite Sentinel-1 montante et une descendante, chacune dans une seule
sous-fauchée, et au moins une géométrie NISAR montante et une descendante. Les fenêtres les plus
riches en coupes chevauchent la limite IW2 / IW3 de l'orbite descendante D37 et ont été écartées.

**Fenêtre retenue** ([table des candidates](../../results/morvan/tables/radar_window_candidates.csv),
[figure](../../results/morvan/figures/s2_reference_window.png)) : nord-est de G23, **60 coupes de
référence (112 ha)**, soit 34 en feuillus, 20 en résineux et 6 en forêts mixtes.

| | Montante | Descendante |
|---|---|---|
| NISAR (bande L) | A173 F25 | D66 F64 |
| Sentinel-1 (bande C) | A59 (IW3, 3 bursts) | D37 (IW2, 3 bursts) |

Cette fenêtre permet, contrairement aux Vosges, de comparer **à géométrie égale dans les deux
directions**.

## 7. Acquisition et traitement radar (étapes m4 et m5)

- **NISAR** : GCOV (γ⁰ HH, HV) et GUNW (cohérence HH à 20 m), lus à distance par blocs
  (`m4_fetch_nisar.py`). La fenêtre est reprojetée dans la projection de chaque produit (UTM 31N).
- **Sentinel-1** : chaînes à 12 jours du 01/06 au 18/11/2026, soit 15 dates par orbite, presque
  toutes de S1D. Seule la première paire (S1C → S1D) dure 13 jours. Les SAFE sont réduits à la
  sous-fauchée utile (`m4_fetch_s1.py`).
- **Traitement SNAP** : mêmes graphes que pour les Vosges (`m5_process_s1.py`), produits sur la
  grille Lambert 93 de 20 m.
  - γ⁰ : Terrain-Flattening ;
  - cohérence : fenêtre 10 × 3, phases de terre plate et topographique retirées ;
  - les 3 bursts sont raccordés par TOPSAR-Deburst, sans ESD.

*(Les résultats radar sont ajoutés à la section 8 à la fin du traitement.)*
