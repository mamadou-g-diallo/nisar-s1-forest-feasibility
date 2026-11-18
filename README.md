# NISAR vs Sentinel-1 — faisabilité détection de coupes rases (Vosges / Alsace)

*🇬🇧 English version: [README_en.md](README_en.md)*

Test de faisabilité préparatoire au stage SERTIT/ICube (bandes L et P : NISAR, BIOMASS).

## Question
Sur une coupe rase récente (Vosges/Alsace, juin–nov. 2026), la cohérence et la rétrodiffusion
**NISAR (bande L, produits GUNW / GCOV)** distinguent-elles mieux la coupe de la forêt intacte
que **Sentinel-1 (bande C)** ? Validation par différence de NDVI **Sentinel-2**.

## Étapes
| # | Étape | État |
|---|-------|------|
| 0 | Environnement, structure, dépôt, SNAP 14, accès Earthdata | ✅ |
| 1 | Cadrage — [FR](docs/cadrage/cadrage_fr.md) · [EN](docs/cadrage/cadrage_en.md) | ✅ |
| 2 | Inventaire S1 / NISAR / BIOMASS (niveaux, polarisations, couverture, répétitivité) | ⏳ |
| 3 | Choix du site (coupe ≥ 5 ha + forêt témoin) et référence NDVI S2 | ⏳ |
| 4 | Téléchargement (`asf_search`) | ⏳ |
| 5 | Traitement et comparaison (cohérence, γ⁰ HH/HV, AUC, JM, prototype de détection) | ⏳ |
| 6 | Rapport LaTeX en deux versions complètes, française et anglaise (ROSE-L et ISCE3 cités) | ⏳ |

Paramètres : [config/params.yaml](config/params.yaml).

## Chaîne réutilisable
La logique de traitement est dans le paquet importable `src/nisar_s1/` (lecture GUNW/GCOV, grille commune,
statistiques, détection), pensé pour être réutilisé sur d'autres sites et transposé à **ROSE-L**.
Les scripts de `scripts/` ne font qu'appeler ces modules. Détails : § 9 du cadrage.

```bash
conda activate nisar_s1
pip install -e .          # rend « import nisar_s1 » disponible partout
```

## Organisation
```
config/        paramètres (emprise, dates, seuils) — pas de secrets
docs/          documents d'étape, en FR et en EN
notebooks/     exploration
scripts/       orchestration des étapes (appellent nisar_s1)
snap_graphs/   graphes SNAP (.xml)
src/nisar_s1/  modules réutilisables
tests/         tests sur données synthétiques
results/       tables et petites sorties
reports/       figures + rapports LaTeX (FR et EN)
data/raw, data/processed -> liens vers /media/dell/Transcend1/nisar_data (non versionné)
```

## Environnement
```bash
conda env create -f environment.yml
conda activate nisar_s1
```
Identifiants : `~/.netrc` (Earthdata, `chmod 600`, script `scripts/setup/create_netrc.sh`), `.env` (tokens ESA/GEE) — exclus de Git.
SNAP 14 (`~/esa-snap`, `-Xmx5G`) ; test : `bash scripts/setup/test_gpt.sh`.
Contraintes machine : ~8 Go de RAM → SNAP sur petite zone (TOPSAR-Split, 2–3 bursts).
