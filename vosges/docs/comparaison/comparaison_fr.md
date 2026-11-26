# Étape 5 — Traitement et comparaison NISAR (bande L) / Sentinel-1 (bande C)

*English version: [comparaison_en.md](comparaison_en.md)*

## 1. Chaîne de traitement

| | NISAR (bande L, 1,26 GHz) | Sentinel-1 (bande C, 5,4 GHz) |
|---|---|---|
| Produits | GCOV (γ⁰ HH, HV, RTC) et GUNW (cohérence HH), niveau L2 produit par **ISCE3** | SLC IW, traités avec **SNAP 14** (`gpt`) |
| Géométries | A144 F26 et A72 F26 (montantes), D138 F64 (descendante) | D139 (descendante), sous-fauchée IW2 |
| γ⁰ | fourni par le produit (aplanissement radiométrique) | bruit thermique → calibration β⁰ → déburst → multivue 4 × 1 → Terrain-Flattening → géocodage 20 m |
| Cohérence | `wrappedInterferogram/HH/coherenceMagnitude` (20 m) et `unwrappedInterferogram` (80 m) | Back-Geocoding (DEM Copernicus 30 m) → cohérence 10 × 3 (phase plate et topographique retirées) → géocodage 20 m. Pas d'ESD : un seul burst couvre le site |
| Paires | 12 jours ; **la paire sur la coupe fait 24 jours** (acquisition manquante fin juillet) | 12 jours (13 jours à la transition S1A → S1C) |

Les graphes SNAP sont dans `graphs/` du [paquet nisar_s1](https://github.com/mamadou-g-diallo/nisar-s1/blob/v0.4.0/src/nisar_s1/graphs) ; les traitements sont lancés par `vosges/scripts/05a_process_s1.py`
(25 produits, ≈ 1 h). Toutes les couches sont ensuite rééchantillonnées sur **une grille commune de 20 m en
UTM 32N** (`nisar_s1.grid`) : moyenne en puissance linéaire pour les γ⁰ NISAR, bilinéaire pour Sentinel-1.

## 2. Méthode d'évaluation (`vosges/scripts/05b_compare.py`, modules `stats` et `detect`)

- **Échantillons** : la coupe C11 (59 pixels de 20 m, 2,36 ha) et un anneau de forêt intacte situé à
  100–275 m de la coupe (548 pixels, 21,8 ha), délimités à partir du NDVI Sentinel-2 (étape 3).
- **Phases** : avant la coupe (images, et paires de cohérence, entièrement avant le 27/07), après
  (entièrement après le 11/08), et paires qui encadrent la coupe.
- **Variables de changement** par capteur et géométrie :
  - `d_gamma0` = γ⁰ moyen après − γ⁰ moyen avant (dB) ; `gamma0_post` = γ⁰ moyen après ;
  - `coh_change` = cohérence de la paire qui encadre la coupe ; `coh_drop` = `coh_change` − cohérence avant ;
    `d_coh` = cohérence après − cohérence avant ; `coh_post` = cohérence après.
- **Métriques de séparabilité** coupe / témoin : écart des moyennes Δ, d de Cohen, **AUC** (Mann-Whitney,
  max(AUC, 1 − AUC)), distance de Jeffries-Matusita (0–2). Les pixels voisins ne sont pas indépendants : on
  ne calcule pas de p-valeur, mais un **intervalle de confiance à 95 % par bootstrap par blocs** de 3 × 3 pixels
  (5 × 5 pour les couches à 80 m).
- **Prototype de détection** sur toute la fenêtre (188 × 187 pixels, 3,7 × 3,7 km) : référence = dNDVI S2 ≤ −0,3
  sur forêt (NDVI avant ≥ 0,7), changements partiels ambigus exclus ; 95 pixels coupés sur 25 723 (0,4 %).
  Scores : AUC sur la fenêtre, F1 au seuil d'Otsu et F1 maximal.
- **Contrôle** : avant la coupe, la coupe et le témoin sont **indiscernables** (AUC 0,51–0,62 selon le
  capteur), ce qui valide le choix du témoin.
- **Sensibilité** : même calcul avec les polygones érodés de 20 m (25 pixels de coupe purs), suffixe `_erode20`.

## 3. Résultats

### 3.1 Variables comparables (grille 20 m, sans érosion)

| Variable | NISAR A144 | NISAR A72 | NISAR D138 | Sentinel-1 D139 |
|---|---|---|---|---|
| Δγ⁰ polarisation croisée (HV / VH) | −4,3 dB, AUC **0,97** [0,93–0,99] | −3,7 dB, 0,94 | −2,3 dB, 0,84 | −2,2 dB, **0,91** [0,85–0,94] |
| Δγ⁰ copolarisation (HH / VV) | −4,2 dB, 0,96 | −3,0 dB, 0,92 | −1,7 dB, 0,72 | −2,5 dB, 0,90 |
| Cohérence de la paire sur la coupe | −0,40, AUC **0,995** | −0,25, 0,92 | −0,31, **0,995** | −0,06, **0,71–0,74** |
| Δ cohérence après − avant | −0,09, 0,77 | −0,05, 0,65 | −0,01, 0,55 | +0,03 à +0,06, 0,65–0,70 |

(Δ = moyenne coupe − moyenne témoin ; tableaux complets : `vosges/results/tables/comparison_change.csv`,
figure `vosges/results/figures/comparison_auc.png`.)

### 3.2 Constats

1. **Cohérence interférométrique : avantage net de la bande L.** Sur la paire qui encadre la coupe, la cohérence
   NISAR de la coupe chute à ≈ 0,26–0,33 alors que la forêt témoin reste à 0,50–0,69 (AUC 0,995 en A144 et D138,
   **malgré une paire de 24 jours**). En bande C, la forêt est déjà décorrélée en 12 jours (cohérence ≈ 0,25–0,30) :
   la coupe n'ajoute presque rien (−0,06, AUC ≈ 0,72). C'est le résultat attendu physiquement : la bande L pénètre
   le houppier et reste cohérente sur la forêt ; la bande C est dominée par les feuilles et rameaux, qui bougent.
2. **Rétrodiffusion : les deux bandes voient la coupe, la bande L plus fortement.** La chute en polarisation
   croisée est de −4 à −5 dB en L (perte de la diffusion de volume des troncs et branches) contre ≈ −2 à −3 dB en C.
3. **Persistance : avantage décisif de la bande L** (`comparison_persistence.png`, table de persistance). En HV, le
   contraste NISAR reste stable d'août à novembre (AUC 0,91–0,95 en A144). En bande C il est instable et
   **disparaît en octobre** (AUC VH 0,88 → 0,74 ; VV 0,86 → 0,66 ; 0,52 le 25/10) : à l'automne, le sol nu
   humide et les rémanents de la coupe rediffusent fortement en bande C, et rattrapent la forêt.
4. **Géométrie** : les deux orbites montantes (A144, A72) séparent mieux que la descendante D138. Sur ce
   versant, l'effet d'ombre et de bord de la coupe dépend de la direction de visée (cf. Bouvet et al., 2018).
5. **Date de la coupe** : le 02/08, Sentinel-1 ne voit encore aucun changement (AUC VH 0,57) ; le 14/08, il est
   net. Combiné aux dates NISAR, cela place l'essentiel de la coupe **entre le 2 et le 11 août 2026**.
6. **Sensibilité** : avec les polygones érodés de 20 m, toutes les AUC augmentent (HV A144 0,97 → 0,996 ;
   VH S1 0,91 → 0,98 en `gamma0_post`) : les résultats ne sont pas un artefact des pixels de bordure.
7. **Détection sur la fenêtre** : AUC 0,82–0,93 pour les meilleures variables NISAR, 0,86–0,87 pour S1. Le F1
   reste faible (≤ 0,29) car la coupe ne représente que 0,4 % des pixels : un seuil sur une seule variable produit
   de nombreuses fausses alarmes. Une détection opérationnelle demande une combinaison de variables, un filtrage
   spatial (taille minimale d'objet) et une confirmation temporelle (plusieurs dates).

## 4. Limites

- **Un seul site de 2,4 ha** : les intervalles de confiance traduisent la variabilité des pixels, pas celle des sites.
  La généralisation exige plusieurs coupes (le candidat C09 est une réplication possible).
- **Paire NISAR de 24 jours** contre 12 jours en C : cela défavorise la bande L, ce qui renforce la conclusion.
- Produits NISAR **provisoires** (`PR`, 2026) ; nombre réduit de dates avant la coupe (1 à 3 paires).
- Les variables de cohérence à 80 m (AUC = 1) ne contiennent que ≈ 4 pixels indépendants dans la coupe :
  elles sont indicatives et exclues de la table des meilleures variables.

## 5. Reproduire

```bash
python vosges/scripts/05a_process_s1.py
python vosges/scripts/05b_compare.py
python vosges/scripts/05b_compare.py --erode 20 --tag _erode20
python vosges/scripts/06_make_tables.py
```

Figures : `vosges/results/figures/comparison_*.png` ; tables : `vosges/results/tables/comparison_*.csv` et
`vosges/report/tables/`.
