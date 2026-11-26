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

The reusable module [`nisar_s1/guide_cr.py`](https://github.com/mamadou-g-diallo/nisar-s1/blob/v0.4.0/src/nisar_s1/guide_cr.py) implements these
steps for **any change image**: dNDVI, Δγ⁰ or coherence drop. The direction of change is a
parameter, and the module is covered by tests.

## 3. Organisation

| Item | Location |
|---|---|
| Site configuration | [`config/sites/morvan.yaml`](../../config/sites/morvan.yaml) (Lambert 93, 20 m grid, time windows, guide parameters) |
| Scripts | [`morvan/scripts/`](../scripts) (`m1` to `m6`) |
| Versioned results | `morvan/results/` (tables, figures, vectors) |
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
([figure](../results/figures/s2_photo_check_reference.png),
[verdicts](../results/tables/s2_photo_check.csv)):
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

**Selected window** ([candidates](../results/tables/radar_window_candidates.csv),
[figure](../results/figures/s2_reference_window.png)): north-east of G23, **60 reference
cuts (112 ha)**, i.e. 34 in broadleaves, 20 in conifers and 6 in mixed forest.

| | Ascending | Descending |
|---|---|---|
| NISAR (L band) | A173 F25 | D66 F65 |
| Sentinel-1 (C band) | A59 (IW3, 3 bursts) | D37 (IW2, 3 bursts) |

Unlike the Vosges, this window allows a comparison **at equal geometry in both directions**.

**Photo-interpretation of the 60 cuts of the window** (step m2b,
[figures](../results/figures/s2_photo_check_window_1.png),
[verdicts](../results/tables/s2_photo_check_window.csv)). Every reference cut of the window
was examined in true colour (July, September) and in September SWIR / NIR / red false colour, where
bare soil and logging residues appear pink-magenta:

| Verdict | Broadleaves | Conifers | Mixed | Total |
|---|---|---|---|---|
| Certain cut (visible bare soil) | 1 | 6 | 3 | **10** (22.8 ha) |
| Probable cut | 6 | 2 | 1 | 9 |
| No bare soil (senescence, shadow, thinning) | 27 | 12 | 2 | 41 |

Only 10 of the 60 "qualified" cuts are certain clear-cuts, almost all in conifers or mixed forest:
in broadleaves the September NDVI drop is mostly senescence. This confirms and strengthens finding 2.

**"Forest before" test** (step m2c, [table](../results/tables/s2_forest_before.csv)). A
clear-cut in the guide's sense is a change from a closed stand to bare soil. For every certain cut,
the July SWIR reflectance (B11) inside the object is compared with a 100–400 m ring of BD Forêt
forest: the object was a closed stand if its B11 does not exceed the ring's 90th percentile. Three
certain cuts (R019, R139, R225) were already open in July (earlier cut, regeneration, timber
storage): they became bare between July and September, but this is not the loss of a stand.

**References used for the radar.** Four nested references are evaluated (option `--ref` of
`m6_compare.py`):

| Reference | Content | Objects | Role |
|---|---|---|---|
| `auto` | 60 cuts qualified by thresholds | 60 | sensitivity (noisy) |
| `verifie_probable` | certain + probable cuts | 19 | sensitivity |
| `verifie` | certain cuts | 10 | sensitivity |
| **`peuplement`** | certain cuts **and** closed forest before | **7** (15.4 ha) | **main reference** |

Discarded (ambiguous) objects are excluded both from the cut class and from intact forest (buffer
zone), so that a cut missed by the reference is not counted as "intact forest".

> **Finding 3.** The main reference is small (7 cuts, 15.4 ha) but reliable: every cut is visually
> checked and was a closed stand in July. Confidence intervals are wide and computed by resampling
> the cuts (cluster bootstrap).

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

## 8. Radar results (steps m6 and m7)

Main reference: 7 closed-stand clear-cuts (15.4 ha, 385 pixels of 20 m), against 10,149 ha of intact
forest. Comparison **at equal geometry**: L A173 with C A59 (ascending), L D66 with C D37 (descending).
95 % confidence intervals (CI) from a cluster bootstrap (cuts and 5 × 5-pixel forest blocks).

### 8.1 Cut / intact forest separability (AUC)

[Summary figure](../results/figures/m8_summary_L_vs_C.png).

| Indicator | L A173 | C A59 | L D66 | C D37 |
|---|---|---|---|---|
| Δγ⁰ cross-pol | 0.80 [0.61–0.93] | 0.73 [0.65–0.86] | 0.83 [0.66–0.93] | 0.83 [0.78–0.91] |
| Δγ⁰ co-pol | 0.70 | 0.63 | 0.71 | 0.74 |
| γ⁰ after, cross-pol | 0.89 | 0.76 | 0.85 | 0.82 |
| minimum coherence (co-pol) | 0.60 [0.53–0.66] | 0.51 | **0.81** [0.75–0.86] | 0.52 |
| coherence after (co-pol) | 0.66 | 0.68 | 0.54 | 0.74 |

- **Cross-pol backscatter drop** (cut / forest): −2.5 / −0.2 dB (L A173), −1.8 / −0.4 dB (C A59),
  −2.7 / −0.3 dB (L D66), −2.6 / −0.6 dB (C D37). The L-band drop is larger, and its Cohen's d is larger
  in both directions (1.89 and 2.13 against 1.03 and 1.63).
- **At equal geometry**, L ≥ C in ascending (0.80 vs 0.73) and L = C in descending (0.83). The CIs
  overlap: with 7 cuts, no backscatter AUC difference is significant.
- **Pre-cut check**: *change* variables stay close to chance (AUC 0.50 to 0.57). Pre-cut *level*
  variables reach 0.54–0.64 (0.70–0.75 with the "verified" reference): the cut stands are special
  (mature conifers). The post-cut γ⁰ (0.85–0.89) is therefore partly inflated by stand type. **The main
  indicator remains the change Δγ⁰**, which does not depend on the starting level.
- **20 m erosion** (edge pixels removed): every AUC rises by 0.03 to 0.07; the L / C order is unchanged.

### 8.2 Coherence: the forest stays coherent in L band, not in C band

Median coherence of intact forest, pair by pair (`m6_coherence_pairs.csv`):

| Geometry | Intact forest, 12-day pairs | Cuts after the cut |
|---|---|---|
| L A173 | 0.35 to 0.70 | 0.41 to 0.74 |
| L D66 | 0.48 to 0.71 | 0.59 to 0.71 |
| C D37 | 0.25 to 0.27 | 0.27 to 0.38 |
| C A59 | 0.30 to 0.36 | 0.34 to 0.53 |

- **H1 is confirmed**: the forest keeps a coherence of 0.5 to 0.7 in L band, against 0.25 to 0.36 in
  C band, i.e. the floor of the estimator (10 × 3 window): in C band the forest is fully decorrelated
  after 12 days, as in the Vosges.
- **H2 is confirmed in descending**: in D66, the minimum coherence of the cuts drops to 0.34 against
  0.48 for the forest (AUC 0.81, against 0.52 in C D37). The 29/08 → 10/09 pair, which brackets three
  cuts, gives 0.45 on the cuts against 0.63 in the forest.
- **In ascending (A173), the advantage is small** (AUC 0.60). Two pairs of the cut window (13/08 →
  25/08 and 25/08 → 06/09) decorrelate the **whole** forest (0.35): the minimum coherence no longer
  singles out the cut. Probable cause: a late-summer rain or wind episode (not verified).
- **In C band, the cut only shows in coherence *afterwards***: bare soil becomes slightly coherent in
  October–November (0.33 to 0.53) while the forest stays at the floor. Hence the post-cut coherence AUC
  is higher in C (0.68–0.74) than in L (0.54–0.66). This is a late signal (4 to 8 weeks), useless for
  alerts.

### 8.3 The guide transposed to radar

[Degree maps](../results/figures/m6_guide_maps.png), audits: [NISAR D66](../results/figures/m6b_commission_NISAR_D66F65_d_g0_HV.png), [Sentinel-1 D37](../results/figures/m6b_commission_S1_T037_d_g0_VH.png).

m − kσ thresholds on cross-pol Δγ⁰ in the forest, then 1 ha sieve (best combination per geometry):

| Geometry | Degree | Omission | Commission | Kappa | Cuts found | False alarms (% forest) |
|---|---|---|---|---|---|---|
| L A173 | ≥ 2 | 55 % | 62 % | **0.41** | **5/7** | 0.09 |
| C A59 | ≥ 2 | 83 % | 94 % | 0.08 | 3/7 | 0.32 |
| L D66 | ≥ 2 | 51 % | 64 % | **0.41** | **5/7** | 0.10 |
| C D37 | ≥ 3 | 84 % | 83 % | 0.16 | 2/7 | 0.10 |

- **L band transposes the guide's method much better** (kappa 0.41 against 0.08 to 0.16), although the
  AUC is equal in descending. Reason: the guide cuts the **tail** of the distribution (m − 2σ, m − 3σ),
  where the gap in standard-deviation units matters (Cohen's d 2.13 in L against 1.63 in C), not the
  average ranking measured by the AUC.
- This **holds for every reference**: L / C kappa = 0.34 / 0.08–0.19 (verified), 0.27 / 0.07–0.15
  (verified + probable), 0.13 / 0.04–0.09 (automatic).
- **We remain far from the guide's target** (≤ 10 % omission and commission). Commission is inflated
  by the small reference: 11 to 13 ha of false alarms in L against 15 ha of cuts, over 12,800 ha
  evaluated, i.e. 0.1 % of the forest. At the same degree (≥ 2), C band produces 41 to 52 ha, four
  times more.
- **Audit of the NISAR D66 false alarms** (15 largest objects, photo-interpretation): 2 probable late
  cuts (F01, 2.5 ha; F04, 1.6 ha); the other 13 are senescence, edges, larch yellowing or hedgerows.
  The same audit on Sentinel-1 D37 (VH Δγ⁰, degree 3, 15 largest objects) finds **no late cut**: 8 of 15 objects (22 of 36 ha) are plots **already open in June** (old cuts, heathland, meadows still mapped as closed forest by BD Forêt), where the low vegetation changes (senescence, soil work); the other 7 are intact forest, edges or senescence. C band reacts to low vegetation, as on cuts R019, R139 and R225, which were open before July; L band does not.

### 8.4 Radar dating

[Time series](../results/figures/m7_cut_timeseries.png).

First lasting cross-pol drop of more than 2 dB (`m7_cut_dates.csv`):

- In **L band**, the series are smooth (a few tenths of a dB of noise from one date to the next), and
  both geometries agree: R013 and R060 late August–early September, R161 early September, R198 and
  R246 late July–mid-August.
- In **C band**, the descending orbit D37 shows synchronous ±3 dB jumps over the whole forest
  (probably moisture): it dates 5 of the 7 cuts to the same pair (25/08–06/09), which is not credible.
  The ascending orbit A59 is more stable and narrows the date of R198 (21/07–02/08).
- **R100** is only detected in C band (September, in both orbits), like R225 (outside the main
  reference); in L band the drop stays below 2 dB (−1.3 to −2.0 dB). Hypothesis: thinning or late
  skidding, to which C band, sensitive to small elements, reacts more than L band.

### 8.5 Hypotheses

| H | Morvan finding | Verdict |
|---|---|---|
| H1 | Forest: 0.5–0.7 in L against 0.25–0.36 in C (floor) | **confirmed** |
| H2 | D66: AUC 0.81 against 0.52; A173: 0.60 (forest-wide decorrelation in late August) | **confirmed in descending, partial** |
| H3 | Larger L drop (Cohen's d 1.9–2.1 against 1.0–1.6); AUC L ≥ C, difference not significant | **partial** |
| H4 | Cross-pol > co-pol in both bands and all four geometries | **confirmed** |

> **Finding 4.** As in the Vosges, the clear L-band advantage is **interferometric**: the forest stays
> coherent and a cut becomes an event. In backscatter the AUCs are close, but L band gives a stronger
> contrast, and that is what matters for a threshold method like the guide's: 5 of 7 cuts found in L,
> 2 to 3 in C.

> **Finding 5.** Reference quality dominates everything else: the AUC rises from 0.51–0.56 (automatic
> reference, 60 objects) to 0.73–0.83 (7 verified closed-stand cuts). Without photo-interpretation, we
> would have wrongly concluded that neither L nor C band sees the cuts.

### 8.6 Limits

- **7 cuts, 15 ha**: wide CIs, no backscatter AUC difference is significant.
- A single season (June–November 2026), a single landscape (Morvan, dominated by conifer cuts).
- Imperfect optical reference: cuts without bare soil, partial cuts and late cuts (after 20/10) are
  misclassified.
- Different coherence estimators (NISAR GUNW vs SNAP 10 × 3); NISAR products are provisional.
- Weather not checked (rain, frost) to explain forest-wide decorrelation.
