# Kit de formation NISAR / Sentinel-1 : 19 notebooks exécutés

## Objet

Une progression pas à pas, sur données réelles, d'un produit NISAR L2 jusqu'à la polarimétrie en
double polarisation, sur la coupe rase du site des Vosges étudiée dans ce projet. Chaque notebook se
termine par un point de contrôle qui doit afficher `Module NN STATUS: PASS`.

La structure reprend celle du kit de formation NISAR GCOV de D. K. Pandey
(`dharmendraisro/nisar-polarimetric-training`, licence Apache-2.0, DOI 10.5281/zenodo.24458160),
réécrite pour ce qui est réellement acquis au-dessus de l'Europe. Aucun code n'est repris : tout
le traitement est dans le paquet `nisar_s1` (modules `product`, `polarimetry`, `maps`), réutilisable
hors des notebooks et, à terme, sur les produits L2 de la mission L de l'ESA **ROSE-L**, dont la
structure géocodée devrait être proche. Les produits NISAR L2 sont générés par le JPL avec
**ISCE3**.

## Ce qui change par rapport au kit d'origine

| | Kit d'origine | Ce kit |
|---|---|---|
| Mode NISAR | bande L quad-pol, bande S compact-pol | **bande L double polarisation HH/HV** (`DHDH`), le mode acquis en Europe |
| Matrice polarimétrique | C3/T3 3x3 lue dans le GCOV | **C2 2x2 reconstruite depuis le GSLC complexe** (le GCOV double polarisation ne stocke pas le terme croisé) |
| Décompositions | Cloude–Pottier, Pauli, Freeman–Durden, Yamaguchi, m-χ | **H/A/α double polarisation** (Cloude 2007), **DpRVI** (Mandal et al. 2020), RVI, paramètres de Stokes |
| Second capteur | NISAR bande S | **Sentinel-1 bande C VV/VH**, mêmes méthodes (graphe SNAP `s1_c2`) |
| Application | générique | **détection de coupe rase**, bande L contre bande C |

Pauli, Freeman–Durden et Yamaguchi ne sont pas transposés : ces modèles ont besoin de VV et de la
phase HH–VV, que l'acquisition HH/HV ne mesure pas. Les appliquer serait faux, pas seulement
approché (notebook 17).

## Les 19 notebooks

* **01–12, le produit GCOV** : recherche ASF, ouverture locale ou à distance (seuls les blocs lus
  sont transférés), découverte du contenu depuis le fichier (fréquences A 20 MHz et B 5 MHz,
  polarisations, termes), métadonnées sans lecture de pixel, γ⁰ et σ⁰, accès par fenêtre et
  garde-fou mémoire, zone d'étude validée et transmise par un fichier de session, contrôle qualité
  et masques, composition colorée HH/HV/rapport, export GeoTIFF vérifié par relecture et
  superposition, série temporelle de 11 dates, dépannage.
* **13–19, la polarimétrie** : inventaire des modes et tableau de décision, C2 reconstruite depuis
  deux extraits GSLC (avant et après la coupe) et validée contre le GCOV de la même date,
  observables et valeurs propres, H/A/α, DpRVI/RVI/Stokes, C2 de Sentinel-1 par SNAP, et synthèse
  bande L contre bande C (AUC du changement coupe contre forêt témoin).

## Résultats obtenus en exécutant le kit

* **Contrôles de cohérence.** La matrice C2 reconstruite depuis le GSLC respecte toutes les
  contraintes physiques (aucun |ρ| > 1, aucun déterminant négatif). Elle est corrélée à 0,79 avec le
  GCOV de la même date, avec un maximum net à décalage nul : le géoréférencement est juste au pixel
  de 40 m près. Le GeoTIFF exporté relu est identique au tableau en mémoire.
* **Série temporelle GCOV (11 dates).** Après la coupe, le contraste coupe − forêt témoin baisse
  de 5,1 dB en HV et de 4,5 dB en HH, puis reste bas.
* **Polarimétrie (40 m, 32 vues).** Ce sont les puissances qui portent le signal. La baisse de
  puissance sépare la coupe de la forêt témoin presque parfaitement :
  - bande L : AUC 0,985 en HH et 0,975 en HV ;
  - bande C : AUC 0,90 en VV et 0,97 en VH.

  La baisse est plus forte en bande L (−4,3 dB en polarisation croisée, contre −2,2 dB en bande C).
  En revanche, les paramètres normalisés H, ᾱ, DpRVI et m ne bougent que de quelques centièmes
  (AUC de 0,52 à 0,59). Une coupe fraîche (souches, rémanents, sol rugueux) dépolarise encore, si
  bien que HH et HV chutent ensemble. Pour détecter une coupe rase, le GSLC complexe (13 Go par
  date) n'apporte donc rien de plus que les puissances du GCOV.
* **Limites.** Une seule coupe de 2,4 ha (16 pixels à 40 m), un site, une saison. La méthode se
  transpose ; les chiffres sont à rétablir ailleurs.

## Données et exécution

Rien n'est stocké dans le dépôt. `notebooks/kit_config.yaml` fixe les granules et la zone ; les
données vont dans `<data_root>/kit`. Un GCOV complet (2 Go) pour 01–12 ; pour 13–19, deux fenêtres
de 6 km extraites à distance de GSLC de 13 Go (7 Mo chacune) et deux matrices C2 Sentinel-1
(`scripts/kit/k1_prepare_data.py`). Exécution sans interface :
`python scripts/kit/k3_run_notebooks.py 1 19`. Les cellules sont générées par
`scripts/kit/k2_build_notebooks.py`.
