# NISAR vs Sentinel-1 — clear-cut detection feasibility (Vosges / Alsace)

Feasibility test prepared for the SERTIT/ICube internship (L and P bands: NISAR, BIOMASS).

## Question
On a recent clear-cut (Vosges/Alsace, June–Nov. 2026), do **NISAR (L-band, GUNW / GCOV products)**
coherence and backscatter separate the clear-cut from intact forest better than **Sentinel-1 (C-band)**?
Validation with the **Sentinel-2** NDVI difference.

## Main result
On a 2.36 ha clear-cut (early August 2026, near Le Thillot), **yes**:

| | NISAR (L band) | Sentinel-1 (C band) |
|---|---|---|
| Coherence of the pair spanning the cut (cut vs forest) | 0.29 vs 0.69, **AUC 0.995** (even over 24 days) | 0.23 vs 0.29, AUC 0.71–0.74 |
| 12-day coherence of intact forest | 0.64–0.70 | 0.28 |
| Cross-pol backscatter drop (HV / VH) | −4.3 dB, **AUC 0.97** | −2.2 dB, AUC 0.91 |
| Contrast in Oct.–Nov. (cross-pol AUC) | 0.91 (persists) | 0.74 (fades; 0.52 on 25/10) |

![Per-date separability](results/figures/comparison_persistence.png)

Single site: to be replicated before designing an operational detector (see the report).

## Steps
| # | Step | Status |
|---|------|--------|
| 0 | Environment, structure, repository, SNAP 14, Earthdata access | ✅ |
| 1 | Scoping — [EN](docs/cadrage/cadrage_en.md) · [FR](docs/cadrage/cadrage_fr.md) | ✅ |
| 2 | S1 / NISAR / BIOMASS inventory — [EN](docs/inventaire/inventaire_en.md) · [FR](docs/inventaire/inventaire_fr.md) | ✅ |
| 3 | Site selection: clear-cut C11 (2.4 ha, July–August 2026) + control forest, S2 NDVI reference — [EN](docs/site/site_en.md) · [FR](docs/site/site_fr.md) | ✅ |
| 4 | Download: NISAR remote window reads, reduced Sentinel-1 SAFE — [EN](docs/acquisition/acquisition_en.md) · [FR](docs/acquisition/acquisition_fr.md) | ✅ |
| 5 | Processing and comparison: L-band coherence and HV γ⁰ separate the cut best (AUC 0.97–0.995) and the L-band contrast persists into autumn, unlike C band — [EN](docs/comparaison/comparaison_en.md) · [FR](docs/comparaison/comparaison_fr.md) | ✅ |
| 6 | LaTeX report in two complete versions (ROSE-L and ISCE3 cited) — [EN PDF](reports/latex/report_en.pdf) · [FR PDF](reports/latex/rapport_fr.pdf) | ✅ |

Parameters: [config/params.yaml](config/params.yaml).

## Reusable chain
Processing logic lives in the importable package `src/nisar_s1/` (GUNW/GCOV readers, common grid,
statistics, detection), designed for reuse on other sites and for transfer to **ROSE-L**.
Scripts in `scripts/` only call these modules. Details: § 9 of the scoping document.

```bash
conda activate nisar_s1
pip install -e .          # makes "import nisar_s1" available everywhere
```

## Layout
```
config/        parameters (footprint, dates, thresholds) — no secrets
docs/          step documents, in FR and EN
notebooks/     exploration
scripts/       step orchestration (calls nisar_s1)
snap_graphs/   SNAP graphs (.xml)
src/nisar_s1/  reusable modules
tests/         tests on synthetic data
results/       tables and small outputs
reports/       figures + LaTeX reports (FR and EN)
data/raw, data/processed -> links to /media/dell/Transcend1/nisar_data (not versioned)
```

## Environment
```bash
conda env create -f environment.yml
conda activate nisar_s1
```
Credentials: `~/.netrc` (Earthdata, `chmod 600`, script `scripts/setup/create_netrc.sh`), `.env` (ESA/GEE tokens) — excluded from Git.
SNAP 14 (`~/esa-snap`, `-Xmx5G`); test: `bash scripts/setup/test_gpt.sh`.
Machine constraints: ~8 GB RAM → SNAP on a small area (TOPSAR-Split, 2–3 bursts).
