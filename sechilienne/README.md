# Séchilienne — phase under forest on an unstable slope

On the forested, unstable slope of Séchilienne (Isère), 17 paired 12/24-day interferograms (26 June – 24 October
2026) compare **NISAR GUNW (ISCE3)** with **Sentinel-1** (SNAP, same pairs).

| Median over pairs | L A173 | C A161 | L D138 | C D139 |
|---|---|---|---|---|
| Coherence, forested slope | **0.58** | 0.28 | 0.32 | 0.29 |
| Phase consistency, forested slope | **0.92** | 0.11 | **0.88** | 0.09 |

- **C band is decorrelated under forest at 12 days**: its 0.27–0.30 forest coherence is the estimator bias floor.
  The chain itself is fine, with 0.97–0.99 on built-up areas.
- **L band keeps a consistent phase** through the canopy. This is the necessary condition for displacement InSAR
  under forest, and an argument for NISAR, then ROSE-L.
- **No displacement is detected above noise** in 4 months. The cumulative change ranges from −4 to +5 mm, against a
  per-pair control spread of 3–10 mm. The expected velocity of 1–5 cm/yr is too slow for single pairs, so a
  ≥ 1-year SBAS series is the next step.

**Note:** [EN](docs/glissement_sechilienne_en.md) · [FR](docs/glissement_sechilienne_fr.md)

Site configuration: [config/sites/sechilienne.yaml](../config/sites/sechilienne.yaml). Scripts
`sechilienne/scripts/g0_*.py` to `g4_*.py`; resumable run:
`bash sechilienne/scripts/run_pipeline.sh --install` (systemd user service, capped memory, automatic restart).
