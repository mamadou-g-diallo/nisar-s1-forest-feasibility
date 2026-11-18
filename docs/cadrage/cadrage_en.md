# Step 1 — Scoping

*🇫🇷 Version française : [cadrage_fr.md](cadrage_fr.md)*

*Feasibility test prepared for the SERTIT/ICube internship "Exploring L and P bands (NISAR, BIOMASS) for the detection of deforestation and landslides".*

## 1. Question and hypotheses

**Question.** On a recent clear-cut in the Vosges / Alsace (June–November 2026), do **NISAR (L-band, λ ≈ 24 cm)**
interferometric coherence and backscatter separate the clear-cut from intact forest better than
**Sentinel-1 (C-band, λ ≈ 5.6 cm)**?

**Hypotheses to test.**

| # | Hypothesis | Physical rationale |
|---|------------|--------------------|
| H1 | Over intact forest, coherence is higher in L-band than in C-band at the same temporal baseline (12 days). | L-band penetrates the canopy and scatters mainly from trunks and large branches, which are stable. C-band is dominated by moving foliage (temporal decorrelation). |
| H2 | The "clear-cut − forest" coherence contrast is therefore larger in L-band. | In C-band the forest is already poorly coherent, so the contrast with the clear-cut (bare soil, often more coherent) is small. |
| H3 | The backscatter drop after cutting is stronger in L-band, especially in HV. | Removing trunks suppresses volume scattering and trunk-ground double bounce. C-band saturates over dense forest. |
| H4 | Cross-polarisation (HV, and the HV/HH ratio) is the radar indicator most sensitive to clear-cutting. | HV is linked to volume scattering, hence to biomass. |

## 2. Scope

**Included:**
- one clear-cut confirmed by Sentinel-2, with a nearby intact reference forest;
- Sentinel-1 IW SLC → coherence and γ⁰ (SNAP, small area: TOPSAR-Split, 2–3 bursts);
- NISAR L2 **GUNW** (coherence) and **GCOV** (γ⁰ HH, HV);
- validation with the Sentinel-2 NDVI difference.

**Inventoried but not processed on this site:**
- **BIOMASS (P-band)**: according to the internship description it does not acquire over Western Europe. The inventory
  (step 2) will document this with the coverage map, and P-band will remain an outlook (e.g. tropical forest).

**Out of scope, discussed as outlook in the report:**
- NISAR vs S1 interferograms over forested slopes affected by landslides (unwrapped phase, displacement);
- storm damage; full polarimetry (decompositions); biomass quantification;
- ROSE-L (Copernicus, launch planned for 2028): the L-band chain developed here must be transferable to it.

## 3. Data (details to be confirmed in step 2)

| Sensor | Product | Variables used | To be checked in the inventory |
|--------|---------|----------------|--------------------------------|
| Sentinel-1 (C) | IW SLC (ASF) | VV/VH coherence; VV/VH γ⁰ (terrain-flattened) | relative orbits covering the site; 6/12-day repeat depending on active satellites (S1A, S1C, S1D) |
| NISAR (L) | L2 GUNW | coherence | actual availability over the area; resolution of the coherence layer; available 12-day pairs |
| NISAR (L) | L2 GCOV | γ⁰ HH, HV (RTC), HV/HH ratio | acquisition mode and polarisations over Europe; resolution; dates |
| BIOMASS (P) | L1/L2 | — | coverage (expected to be none over the area) |
| Sentinel-2 | L2A | NDVI before / after, NDVI difference | cloud-free dates (cloudy autumn in the Vosges) |
| Optional | ASF HyP3 (on-demand S1 coherence) | control S1 coherence | useful if SNAP runs out of RAM |

## 4. Method

1. **Site** (step 3): a clear-cut of **≥ 5 ha if possible**. The GUNW coherence layer may have a coarse
   resolution (to be confirmed), and a small clear-cut would contain only a few pixels.
   The cutting date must also be bracketed by clear S2 images, with a nearby intact control forest of the same
   stand type, slope and aspect.
2. **Polygons**: clear-cut (`dNDVI` < threshold, to be calibrated, about −0.2) and intact forest. Both are shrunk
   inwards by one radar pixel to avoid edge effects.
3. **S1 / NISAR comparability**
   - same **temporal baseline** (12 days) for coherence, comparing pairs acquired before and after the cut;
   - **terrain-flattened γ⁰** on both sides: GCOV is already RTC, S1 goes through Terrain-Flattening in SNAP;
   - resampling to a **common grid** (UTM 32N) at the coarser resolution of the two sensors;
   - geometry (ascending or descending orbit, incidence angle) and weather (rain, snow in November) are taken into account.
4. **Indicators**: for each sensor, each variable (coherence, co- and cross-polarised γ⁰, HV/HH ratio)
   and each date (before or after the cut):
   - mean difference clear-cut − forest (Δγ, Δγ⁰ in dB) and effect size (Cohen's d);
   - separability: **AUC** (ROC curve) and **Jeffries-Matusita distance**;
   - time series over each polygon, to see when the clear-cut becomes visible.
5. **Automatic detection (prototype)**: thresholding (Otsu, or a threshold chosen on the ROC) of a change
   indicator (before/after γ⁰ ratio, coherence drop). The resulting map is compared with the NDVI reference:
   precision, recall, F1. This is a first building block towards "monitoring maps of sensitive areas".

## 5. Success criterion

L-band "separates better" if, with comparable baselines and dates, its **AUC (or JM distance) is clearly
higher** than C-band for at least one variable, and this gain carries over to the F1 score of the detection prototype.
A negative or inconclusive result (NISAR data unavailable, clear-cut too small) is **a valid feasibility result**
and will be documented as such.

## 6. Risks

| Risk | Consequence | Mitigation |
|------|-------------|------------|
| Few or no NISAR GUNW/GCOV products over the area and period | Comparison impossible | Early inventory (step 2); widen the area (Northern Vosges, Black Forest) or the period |
| Coarse NISAR resolution relative to clear-cut size | Mixed pixels | Pick a large clear-cut; pool several clear-cuts |
| Limited RAM (~8 GB) | SNAP blocked | TOPSAR-Split on 2–3 bursts, sub-area, `-Xmx5G`; HyP3 as fallback |
| Clouds and snow in autumn | Degraded S2 reference or coherence | Wider date windows; record the weather |
| Vosges relief (radar layover and shadow) | γ⁰ bias | Terrain flattening; layover/shadow mask; control forest with same slope and aspect |

## 7. Mapping to the internship description

| Internship task | How this test addresses it |
|-----------------|---------------------------|
| Inventory NISAR / BIOMASS products (processing levels, polarisations, coverage, revisit) and tools | Step 2 (+ tools: asf_search, earthaccess, h5py, SNAP, ISCE3 cited) |
| Select sites with clear-cuts observed by S1 and NISAR / BIOMASS | Step 3 |
| Compare deforestation detection S1 / NISAR / BIOMASS | Step 5 (BIOMASS: documented lack of coverage) |
| Test the contribution of polarimetry | HH / HV / HV÷HH (GCOV) |
| Compare interferograms over forested slopes affected by landslides | Outlook (qualitative look at coherence on slopes if time allows) |
| Adapt the processing chain to L-band | Reusable modules in `src/nisar_s1/` (see § 9) |
| Automatic detection method | Thresholding prototype + F1 evaluation |
| Prepare for ROSE-L | Sensor-independent chain (§ 9); ROSE-L (2028) and ISCE3 cited in the report |

## 8. Deliverables and indicative schedule

Deliverables meant to be read (report, step documents, README) exist in **two complete versions, French and English**.

| Step | Deliverable |
|------|-------------|
| 2. Inventory | `docs/inventaire/inventaire_fr.md` + `inventaire_en.md` + `results/tables/inventaire_*.csv` |
| 3. Site | `config/site.geojson` (clear-cut + control) + NDVI figure |
| 4. Download | `scripts/04_download.py` (calls `nisar_s1.download`), file log |
| 5. Processing | SNAP graphs, `src/nisar_s1/` modules, statistics tables, figures |
| 6. Report | `reports/latex/rapport_fr.tex` **and** `reports/latex/report_en.tex` (two complete reports) |

## 9. Reusable chain (preparing for ROSE-L)

The code is **not** a set of throwaway scripts. All logic lives in the importable package `src/nisar_s1/`.
The files in `scripts/` and the notebooks only call these modules with the parameters from `config/params.yaml`.

| Module | Role | Intended reuse |
|--------|------|----------------|
| `config.py` | reads `params.yaml`, paths | whole project |
| `search.py` / `download.py` | ASF search and download (asf_search, earthaccess) by footprint and period | other sites; ROSE-L via ASF or Copernicus |
| `io_nisar.py` | reads NISAR L2 **GUNW** (coherence, phase) and **GCOV** (γ⁰ HH/HV) HDF5 products → georeferenced `xarray` | any NISAR data; template for a ROSE-L reader |
| `io_s1.py` | reads SNAP outputs (BEAM-DIMAP/GeoTIFF) → `xarray` | existing S1 chain |
| `snap.py` | runs parameterised `gpt` graphs (`snap_graphs/*.xml`) | any SNAP chain |
| `grid.py` | reprojection and resampling to a common grid | multi-sensor comparison |
| `stats.py` | per-polygon statistics, Δ, Cohen's d, AUC, Jeffries-Matusita distance | any clear-cut/control comparison |
| `detect.py` | threshold-based change detection + evaluation (precision, recall, F1) | monitoring maps of sensitive areas |
| `plots.py` | standardised figures | report |

**Principles:**
- functions documented in English (docstrings) and typed, with no hard-coded paths;
- one reader per **product format**, not per study, so that a future ROSE-L reader plugs into `grid`, `stats` and `detect` without changing them;
- minimal tests (`tests/`) on synthetic data, like the existing `gpt` test.

The report will position this chain relative to **ISCE3** (NISAR's official processing software, which produces
GUNW and GCOV) and to **ROSE-L** (Copernicus L-band mission, launch planned for 2028), to which it must remain transferable.
