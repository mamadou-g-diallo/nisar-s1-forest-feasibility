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

Le module réutilisable [`nisar_s1/guide_cr.py`](https://github.com/mamadou-g-diallo/nisar-s1/blob/v0.4.0/src/nisar_s1/guide_cr.py) implémente
ces étapes pour **n'importe quelle image de changement** : ΔNDVI, Δγ⁰ ou baisse de cohérence. Le
sens du changement est un paramètre, et le module est couvert par des tests.

## 3. Organisation

| Élément | Emplacement |
|---|---|
| Configuration du site | [`config/sites/morvan.yaml`](../../config/sites/morvan.yaml) (Lambert 93, grille 20 m, fenêtres temporelles, paramètres du guide) |
| Scripts | [`morvan/scripts/`](../scripts) (`m1` à `m6`) |
| Résultats versionnés | `morvan/results/` (tables, figures, vecteurs) |
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
([figure](../results/figures/s2_photo_check_reference.png),
[verdicts](../results/tables/s2_photo_check.csv)) :
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

**Fenêtre retenue** ([table des candidates](../results/tables/radar_window_candidates.csv),
[figure](../results/figures/s2_reference_window.png)) : nord-est de G23, **60 coupes de
référence (112 ha)**, soit 34 en feuillus, 20 en résineux et 6 en forêts mixtes.

| | Montante | Descendante |
|---|---|---|
| NISAR (bande L) | A173 F25 | D66 F65 |
| Sentinel-1 (bande C) | A59 (IW3, 3 bursts) | D37 (IW2, 3 bursts) |

Cette fenêtre permet, contrairement aux Vosges, de comparer **à géométrie égale dans les deux
directions**.

**Photo-interprétation des 60 coupes de la fenêtre** (étape m2b,
[figures](../results/figures/s2_photo_check_window_1.png),
[verdicts](../results/tables/s2_photo_check_window.csv)). Toutes les coupes de référence
de la fenêtre ont été examinées en couleurs vraies (juillet, septembre) et en fausses couleurs
SWIR / PIR / rouge de septembre, où le sol nu et les rémanents apparaissent rose-magenta :

| Verdict | Feuillus | Résineux | Mixtes | Total |
|---|---|---|---|---|
| Coupe certaine (sol nu visible) | 1 | 6 | 3 | **10** (22,8 ha) |
| Coupe probable | 6 | 2 | 1 | 9 |
| Pas de sol nu (sénescence, ombre, éclaircie) | 27 | 12 | 2 | 41 |

Seules 10 des 60 coupes « qualifiées » sont donc des coupes rases certaines, et presque toutes en
résineux ou en forêt mixte : en feuillus, la baisse de NDVI de septembre est surtout de la
sénescence. Cela confirme et aggrave le constat 2.

**Test « forêt avant »** (étape m2c, [table](../results/tables/s2_forest_before.csv)).
Une coupe rase au sens du guide est le passage d'un peuplement fermé au sol nu. Pour chaque coupe
certaine, la réflectance SWIR (B11) de juillet dans l'objet est comparée à celle d'un anneau de
forêt BD Forêt de 100 à 400 m autour : l'objet était un peuplement fermé si sa B11 ne dépasse pas
le 90ᵉ centile de l'anneau. Trois coupes certaines (R019, R139, R225) étaient déjà ouvertes en
juillet (coupe antérieure, régénération, dépôt de bois) : elles ont été mises à nu entre juillet et
septembre, mais ce n'est pas la perte d'un peuplement.

**Références utilisées pour le radar.** Quatre références emboîtées sont évaluées
(option `--ref` de `m6_compare.py`) :

| Référence | Contenu | Objets | Rôle |
|---|---|---|---|
| `auto` | 60 coupes qualifiées par les seuils | 60 | sensibilité (bruitée) |
| `verifie_probable` | coupes certaines + probables | 19 | sensibilité |
| `verifie` | coupes certaines | 10 | sensibilité |
| **`peuplement`** | coupes certaines **et** forêt fermée avant | **7** (15,4 ha) | **référence principale** |

Les objets écartés (ambigus) sont exclus de l'apprentissage comme de la forêt intacte (zone
tampon), pour ne pas compter comme « forêt intacte » une coupe que la référence a ratée.

> **Constat 3.** La référence principale est petite (7 coupes, 15,4 ha) mais fiable : chaque coupe
> est vérifiée visuellement et était un peuplement fermé en juillet. Les intervalles de confiance
> sont larges et calculés par rééchantillonnage des coupes (bootstrap en grappes).

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

## 8. Résultats radar (étapes m6 et m7)

Référence principale : 7 coupes de peuplement (15,4 ha, 385 pixels de 20 m), contre 10 149 ha de
forêt intacte. Comparaison **à géométrie égale** : L A173 avec C A59 (montantes), L D66 avec C D37
(descendantes). Intervalles de confiance (IC) à 95 % par bootstrap par grappes (coupes et blocs de
forêt de 5 × 5 pixels).

### 8.1 Séparabilité coupe / forêt intacte (AUC)

[Figure de synthèse](../results/figures/m8_summary_L_vs_C.png).

| Indicateur | L A173 | C A59 | L D66 | C D37 |
|---|---|---|---|---|
| Δγ⁰ pol. croisée | 0,80 [0,61–0,93] | 0,73 [0,65–0,86] | 0,83 [0,66–0,93] | 0,83 [0,78–0,91] |
| Δγ⁰ co-polarisée | 0,70 | 0,63 | 0,71 | 0,74 |
| γ⁰ après, pol. croisée | 0,89 | 0,76 | 0,85 | 0,82 |
| cohérence minimale (co-pol.) | 0,60 [0,53–0,66] | 0,51 | **0,81** [0,75–0,86] | 0,52 |
| cohérence après (co-pol.) | 0,66 | 0,68 | 0,54 | 0,74 |

- **Baisse de rétrodiffusion croisée** (coupe / forêt) : −2,5 / −0,2 dB (L A173), −1,8 / −0,4 dB
  (C A59), −2,7 / −0,3 dB (L D66), −2,6 / −0,6 dB (C D37). La bande L baisse plus, et son d de Cohen
  est plus grand dans les deux directions (1,89 et 2,13 contre 1,03 et 1,63).
- **À géométrie égale**, L ≥ C en montante (0,80 contre 0,73), L = C en descendante (0,83). Les IC se
  recouvrent : avec 7 coupes, aucune différence d'AUC en rétrodiffusion n'est significative.
- **Contrôle avant coupe** : les variables de *changement* restent près du hasard (AUC 0,50 à 0,57).
  Les variables de *niveau* avant la coupe montent à 0,54–0,64 (0,70–0,75 avec la référence
  « vérifiée ») : les parcelles coupées sont des peuplements particuliers (résineux mûrs). Le γ⁰ après
  coupe (0,85–0,89) est donc en partie gonflé par le type de peuplement. **L'indicateur principal reste
  la variation Δγ⁰**, indépendante du niveau de départ.
- **Érosion de 20 m** (pixels de bord retirés) : toutes les AUC augmentent de 0,03 à 0,07, l'ordre L / C
  ne change pas.

### 8.2 Cohérence : la forêt reste cohérente en bande L, pas en bande C

Médiane de la cohérence de la forêt intacte, paire par paire (`m6_coherence_pairs.csv`) :

| Géométrie | Forêt intacte, paires à 12 j | Coupes après la coupe |
|---|---|---|
| L A173 | 0,35 à 0,70 | 0,41 à 0,74 |
| L D66 | 0,48 à 0,71 | 0,59 à 0,71 |
| C D37 | 0,25 à 0,27 | 0,27 à 0,38 |
| C A59 | 0,30 à 0,36 | 0,34 à 0,53 |

- **H1 est confirmée** : la forêt garde une cohérence de 0,5 à 0,7 en bande L, contre 0,25 à 0,36 en
  bande C, c'est-à-dire le plancher de l'estimateur (fenêtre 10 × 3) : en C, la forêt est complètement
  décorrélée en 12 jours, comme dans les Vosges.
- **H2 est confirmée en descendante** : en D66, la cohérence minimale de la coupe tombe à 0,34 contre
  0,48 pour la forêt (AUC 0,81, contre 0,52 en C D37). La paire du 29/08 au 10/09, qui encadre trois
  coupes, donne 0,45 sur les coupes contre 0,63 en forêt.
- **En montante (A173), l'avantage est faible** (AUC 0,60). Deux paires de la fenêtre de coupe (13/08 →
  25/08 et 25/08 → 06/09) décorrèlent **toute** la forêt (0,35) : la cohérence minimale ne distingue
  plus la coupe. Cause probable : épisode de pluie ou de vent en fin d'été (non vérifié).
- **En bande C, la coupe ne se voit en cohérence qu'*après*** : le sol nu redevient un peu cohérent en
  octobre–novembre (0,33 à 0,53), alors que la forêt reste au plancher. D'où l'AUC de la cohérence après
  coupe, plus élevée en C (0,68–0,74) qu'en L (0,54–0,66). C'est un signal tardif (4 à 8 semaines),
  inutile pour l'alerte.

### 8.3 Le guide transposé au radar

[Cartes des degrés](../results/figures/m6_guide_maps.png), audits : [NISAR D66](../results/figures/m6b_commission_NISAR_D66F65_d_g0_HV.png), [Sentinel-1 D37](../results/figures/m6b_commission_S1_T037_d_g0_VH.png).

Seuillage m − kσ sur Δγ⁰ croisée dans la forêt, puis tamisage à 1 ha (meilleure combinaison par
géométrie) :

| Géométrie | Degré | Omission | Commission | Kappa | Coupes trouvées | Fausses alertes (% forêt) |
|---|---|---|---|---|---|---|
| L A173 | ≥ 2 | 55 % | 62 % | **0,41** | **5/7** | 0,09 |
| C A59 | ≥ 2 | 83 % | 94 % | 0,08 | 3/7 | 0,32 |
| L D66 | ≥ 2 | 51 % | 64 % | **0,41** | **5/7** | 0,10 |
| C D37 | ≥ 3 | 84 % | 83 % | 0,16 | 2/7 | 0,10 |

- **La bande L transpose bien mieux la méthode du guide** (kappa 0,41 contre 0,08 à 0,16), alors que
  l'AUC est égale en descendante. Raison : le guide coupe la **queue** de la distribution (m − 2σ,
  m − 3σ), où compte l'écart en unités d'écart-type (d de Cohen 2,13 en L contre 1,63 en C), pas le
  classement moyen mesuré par l'AUC.
- Ce résultat **tient pour toutes les références** : kappa L / C = 0,34 / 0,08–0,19 (vérifiées),
  0,27 / 0,07–0,15 (vérifiées + probables), 0,13 / 0,04–0,09 (automatique).
- **On reste loin de l'objectif du guide** (≤ 10 % d'omission et de commission). La commission est
  gonflée par la petite référence : 11 à 13 ha de fausses alertes en L face à 15 ha de coupes, sur
  12 800 ha évalués, soit 0,1 % de la forêt. Au même degré (≥ 2), la bande C en produit 41 à 52 ha,
  quatre fois plus.
- **Audit des fausses alertes NISAR D66** (15 plus grands objets, photo-interprétation) : 2 coupes
  tardives probables (F01, 2,5 ha ; F04, 1,6 ha), les 13 autres sont des sénescences, lisières,
  jaunissements de mélèze ou bocage. Le même audit sur Sentinel-1 D37 (Δγ⁰ VH, degré 3, 15 plus grands objets) ne trouve **aucune coupe tardive** : 8 objets sur 15 (22 ha sur 36) sont des parcelles **déjà ouvertes en juin** (anciennes coupes, landes, prairies encore classées en forêt fermée par la BD Forêt), où la strate basse change (sénescence, travail du sol) ; les 7 autres sont des forêts intactes, des lisières ou des sénescences. La bande C réagit à la végétation basse, comme sur les coupes R019, R139 et R225 ouvertes avant juillet ; la bande L, non.

### 8.4 Datation radar

[Séries temporelles](../results/figures/m7_cut_timeseries.png).

Première baisse durable de la polarisation croisée de plus de 2 dB (`m7_cut_dates.csv`) :

- En **bande L**, les séries sont lisses (bruit de quelques dixièmes de dB d'une date à l'autre), et les
  deux géométries concordent : R013 et R060 fin août–début septembre, R161 début septembre, R198 et
  R246 fin juillet–mi-août.
- En **bande C**, l'orbite descendante D37 subit des sauts synchrones de ±3 dB sur toute la forêt
  (humidité probable) : elle date 5 coupes sur 7 dans la même paire (25/08–06/09), ce qui n'est pas
  crédible. L'orbite montante A59 est plus stable et resserre la date de R198 (21/07–02/08).
- **R100** n’est détectée qu’en bande C (septembre, dans les deux orbites), comme R225 (hors référence principale) ; en L, la baisse
  reste sous 2 dB (−1,3 à −2,0 dB). Hypothèse : éclaircie ou débardage tardif, auxquels la bande C, sensible
  aux petits éléments, réagit plus que la bande L.

### 8.5 Bilan des hypothèses

| H | Constat Morvan | Verdict |
|---|---|---|
| H1 | Forêt : 0,5–0,7 en L contre 0,25–0,36 en C (plancher) | **confirmée** |
| H2 | D66 : AUC 0,81 contre 0,52 ; A173 : 0,60 (décorrélation générale fin août) | **confirmée en descendante, partielle** |
| H3 | Baisse L plus forte (d de Cohen 1,9–2,1 contre 1,0–1,6) ; AUC L ≥ C, différence non significative | **partielle** |
| H4 | Pol. croisée > co-pol. dans les deux bandes et les quatre géométries | **confirmée** |

> **Constat 4.** Comme dans les Vosges, l'avantage clair de la bande L est **interférométrique** : la
> forêt reste cohérente, la coupe devient un événement. En rétrodiffusion, les AUC sont proches, mais la
> bande L donne un contraste plus fort, et c'est ce qui compte pour une méthode à seuils comme celle du
> guide : 5 coupes sur 7 trouvées en L, 2 à 3 en C.

> **Constat 5.** La qualité de la référence domine tout le reste : l'AUC passe de 0,51–0,56 (référence
> automatique, 60 objets) à 0,73–0,83 (7 coupes de peuplement vérifiées). Sans photo-interprétation,
> on aurait conclu à tort que ni la bande L ni la bande C ne voient les coupes.

### 8.6 Limites

- **7 coupes, 15 ha** : IC larges, aucune différence d'AUC en rétrodiffusion n'est significative.
- Une seule saison (juin–novembre 2026), un seul paysage (Morvan, dominé par les résineux coupés).
- Référence optique imparfaite : coupes sans sol nu, coupes partielles et coupes tardives
  (après le 20/10) mal classées.
- Estimateurs de cohérence différents (NISAR GUNW contre SNAP 10 × 3), produits NISAR provisoires.
- Météo non vérifiée (pluie, gel) pour expliquer les décorrélations générales.
