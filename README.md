# NISAR vs Sentinel-1 — faisabilité détection de coupes rases (Vosges / Alsace)

Test de faisabilité préparatoire au stage SERTIT (bandes L et P : NISAR, BIOMASS).

## Question
Sur une coupe rase récente (Vosges/Alsace, juin–nov. 2026), la cohérence et la rétrodiffusion
**NISAR (bande L, produits GUNW / GCOV)** distinguent-elles mieux la coupe de la forêt intacte
que **Sentinel-1 (bande C)** ? Validation par différence de NDVI **Sentinel-2**.

## Étapes
| # | Étape | État |
|---|-------|------|
| 0 | Environnement, structure, dépôt, SNAP 14, accès Earthdata | ✅ |
| 1 | Cadrage — [docs/cadrage/cadrage.md](docs/cadrage/cadrage.md) | ✅ |
| 2 | Inventaire S1 / NISAR / BIOMASS (niveaux, polarisations, couverture, répétitivité) | ⏳ |
| 3 | Choix du site (coupe ≥ 5 ha + forêt témoin) et référence NDVI S2 | ⏳ |
| 4 | Téléchargement (`asf_search`) | ⏳ |
| 5 | Traitement et comparaison (cohérence, γ⁰ HH/HV, AUC, JM, prototype de détection) | ⏳ |
| 6 | Mini-rapport LaTeX (FR + résumé EN ; perspectives : glissements, bande P, ROSE-L) | ⏳ |

Paramètres : [config/params.yaml](config/params.yaml).

## Organisation
```
config/        paramètres (AOI, dates, emprises) — pas de secrets
docs/cadrage/  notes de cadrage
notebooks/     exploration
scripts/       scripts d'étape (inventaire, téléchargement, traitement)
snap_graphs/   graphes SNAP (.xml) : TOPSAR-Split 2–3 bursts, cohérence, calibration
src/nisar_s1/  code Python réutilisable
results/       tables et petites sorties
reports/       figures + rapport LaTeX
data/raw, data/processed -> liens vers /media/dell/Transcend1/nisar_data (non versionné)
```

## Environnement
```bash
conda env create -f environment.yml
conda activate nisar_s1
```
Identifiants : `~/.netrc` (Earthdata, `chmod 600`), `.env` (tokens ESA/GEE) — tous exclus de Git.

Contraintes machine : ~8 Go de RAM → traitements SNAP limités à une petite zone (TOPSAR-Split, 2–3 bursts).
