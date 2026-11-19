# Replication in the Morvan (sylvo-ecoregion G23): IRSTEA guide method and NISAR / Sentinel-1 comparison

*Version française : [replication_morvan_fr.md](replication_morvan_fr.md)*

## 1. Why this replication

The Vosges test (frozen as `v1.0-vosges`) covered **one clear-cut** (C11, 2.36 ha) and **one
Sentinel-1 orbit** (descending). Its two main limitations were therefore generalisation (n = 1)
and comparison at equal geometry (a single common geometry).

The replication uses the **study area of the IRSTEA methodological guide**:

> K. Ose, M. Deshayes (2015). *Détection et cartographie des coupes rases par télédétection
> satellitaire. Guide méthodologique*, v5.0, UMR TETIS – Irstea.

The guide was written for the French Ministry of Agriculture over two IFN sylvo-ecoregions,
including **G23 "Morvan et Autunois"**. It defines an operational method and specifications:
- 1 ha minimum mapping unit;
- omission and commission errors ≤ 10 % by area;
- Lambert 93 projection.

The replication uses the guide in two ways:

1. as the **optical reference** (Sentinel-2), replacing the ad hoc threshold used in the Vosges;
2. as a **detection method transposed to radar**, so that NISAR and Sentinel-1 are evaluated
   against a French operational standard, not only by an AUC.

## 2. The guide method in short

The guide proceeds in six steps:

1. Two summer optical images, one year apart, converted to reflectance.
2. NDVI on each date, then the difference dNDVI = NDVI(n+1) − NDVI(n).
3. Masks: study area (sylvo-ecoregion) and forest (BD Topo or BD Forêt).
4. Statistical thresholds inside the forest, from the mean m and standard deviation σ of dNDVI.
   A pixel is a candidate cut if dNDVI < m − σ, with three certainty degrees:

   | Degree | dNDVI interval |
   |---|---|
   | 1 (low) | [m − 2σ, m − σ) |
   | 2 (medium) | [m − 3σ, m − 2σ) |
   | 3 (high) | < m − 3σ |

   The guide notes that degree 1 mostly holds false detections (shadows, atmospheric effects).
5. Sieve (GDAL *Sieve*) at 1 ha, then vector export with area and degree.
6. Evaluation with an area-based confusion matrix:
   - producer and user accuracy;
   - omission and commission;
   - overall accuracy;
   - kappa.

The reusable module [`src/nisar_s1/guide_cr.py`](../../src/nisar_s1/guide_cr.py) implements these
steps for **any change image**: dNDVI, Δγ⁰ or coherence drop. The direction of change is a
parameter, and the module is covered by tests.

## 3. Organisation

| Item | Location |
|---|---|
| Site configuration | [`config/sites/morvan.yaml`](../../config/sites/morvan.yaml) (Lambert 93, 20 m grid, time windows, guide parameters) |
| Scripts | [`scripts/morvan/`](../../scripts/morvan) (`m1` to `m6`) |
| Versioned results | `results/morvan/` (tables, figures, vectors) |
| Large data | external disk, `nisar_data/morvan/` (not versioned) |

## 4. IGN data (step m1)

- **G23 outline**: IGN forest inventory file `ser_l93.zip`, i.e. **3,011 km²**.
- **BD Forêt V2**: retrieved from the Géoplateforme WFS, i.e. 13,494 polygons in G23.
- **Forest kept**: closed and open forest with tree cover, and poplar stands. Class FF0 ("closed
  forest without tree cover", i.e. old cuts) and heathland are excluded. This gives about
  **157,800 ha**:
  - 89,750 ha broadleaves;
  - 49,400 ha conifers, mostly Douglas fir;
  - 18,600 ha mixed forest.

## 5. The guide applied to Sentinel-2 over the whole of G23 (step m2)

**NDVI composites.** For each tile (31TEM, 31TEN, 31TFM, 31TFN), we take the median of the 3
clearest dates of each window:
- "before": 15/06 → 08/07/2026;
- "after": 15/09 → 16/10/2026.

The composites are mosaicked on a 20 m Lambert 93 grid. dNDVI is valid over 92 % of the forest.

**Guide thresholds**, computed in the G23 forest: m = −0.040 and σ = 0.058, hence:
- m − σ = −0.098;
- m − 2σ = −0.157;
- m − 3σ = −0.215.

**Raw guide result.** We get 3,349 objects of 1 ha or more (13,600 ha), 3,089 of them of degree 2
or higher. That is **8.7 % of the forest in two and a half months**, which is not plausible: the
clear-cut rate is around 1 % per year. The detections are mostly broadleaves (2,269 of 3,089
objects), which yellow from September (early senescence, drought stress).

This is the limit of the guide transposed as is to an **intra-season** pair. Its m − kσ thresholds
assume that uncut forest has a narrow, centred dNDVI, which holds for two summer images one year
apart but not between July and September.

> **Finding 1.** The guide's statistical thresholds cannot be transferred unchanged to
> sub-annual monitoring: phenology widens the tail of the dNDVI distribution and the "high" degree
> no longer isolates clear-cuts.

**Qualified reference.** The guide asks to keep only plots that "went from a wooded state to bare
soil" (section 2.2). The reference is therefore:
- guide degree 3;
- and NDVI before ≥ 0.70;
- and NDVI after ≤ 0.65;
- then a 1 ha sieve.

This gives **281 clear-cuts (613 ha)**: 193 in broadleaves, 67 in conifers, 21 in mixed forest.
The median area is 1.6 ha.

**Photo-interpretation check** (guide section 3.9.1). On a random sample of 30 reference cuts,
compared in true colour in July and September
([figure](../../results/morvan/figures/s2_photo_check_reference.png),
[verdicts](../../results/morvan/tables/s2_photo_check.csv)):
- 13 certain cuts (brown bare soil);
- 6 probable;
- 3 with no visible change;
- 8 not interpretable (cloud on the "after" image).

**Reference precision is therefore 59 % (certain only) to 86 % (with probable)**, on n = 22.

All 3 errors are **broadleaves**, whereas the certain cuts are mostly conifers and mixed stands.
dNDVI does not separate true cuts from errors (−0.24 to −0.51 in both groups).

> **Finding 2.** The optical reference is imperfect, mainly in broadleaves. Radar scores measured
> against it are therefore **lower bounds**: part of the radar "commission" is actually a
> reference error. The analysis is also split by forest group (broadleaves / conifers).

## 6. Choice of the radar window (step m3)

Sentinel-1 processing is done per burst (at most 3, because of RAM) inside one sub-swath. Candidate
20 × 20 km windows were ranked by the area of reference cuts they contain, then checked in the ASF
catalogues: Sentinel-1 bursts and full coverage by NISAR frames.

Rule applied: one ascending and one descending Sentinel-1 orbit, each in a single sub-swath, and at
least one ascending and one descending NISAR geometry. The windows richest in cuts straddle the
IW2 / IW3 boundary of descending orbit D37 and were discarded.

**Selected window** ([candidates](../../results/morvan/tables/radar_window_candidates.csv),
[figure](../../results/morvan/figures/s2_reference_window.png)): north-east of G23, **60 reference
cuts (112 ha)**, i.e. 34 in broadleaves, 20 in conifers and 6 in mixed forest.

| | Ascending | Descending |
|---|---|---|
| NISAR (L band) | A173 F25 | D66 F64 |
| Sentinel-1 (C band) | A59 (IW3, 3 bursts) | D37 (IW2, 3 bursts) |

Unlike the Vosges, this window allows a comparison **at equal geometry in both directions**.

## 7. Radar acquisition and processing (steps m4 and m5)

- **NISAR**: GCOV (γ⁰ HH, HV) and GUNW (HH coherence at 20 m), read remotely by chunks
  (`m4_fetch_nisar.py`). The window is reprojected into each product's projection (UTM 31N).
- **Sentinel-1**: 12-day chains from 01/06 to 18/11/2026, i.e. 15 dates per orbit, almost all from
  S1D. Only the first pair (S1C → S1D) spans 13 days. The SAFE files are reduced to the useful
  sub-swath (`m4_fetch_s1.py`).
- **SNAP processing**: same graphs as in the Vosges (`m5_process_s1.py`), output on the 20 m
  Lambert 93 grid.
  - γ⁰: Terrain-Flattening;
  - coherence: 10 × 3 window, flat-earth and topographic phases removed;
  - the 3 bursts are joined by TOPSAR-Deburst, without ESD.

*(Radar results are added in section 8 once processing is complete.)*
