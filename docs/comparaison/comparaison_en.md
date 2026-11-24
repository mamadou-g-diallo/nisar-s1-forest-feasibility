# Step 5 — Processing and comparison of NISAR (L band) and Sentinel-1 (C band)

*Version française : [comparaison_fr.md](comparaison_fr.md)*

## 1. Processing chain

| | NISAR (L band, 1.26 GHz) | Sentinel-1 (C band, 5.4 GHz) |
|---|---|---|
| Products | GCOV (γ⁰ HH, HV, RTC) and GUNW (HH coherence), L2 level produced by **ISCE3** | IW SLC, processed with **SNAP 14** (`gpt`) |
| Geometries | A144 F26 and A72 F26 (ascending), D138 F64 (descending) | D139 (descending), sub-swath IW2 |
| γ⁰ | provided by the product (radiometric terrain flattening) | thermal noise → β⁰ calibration → deburst → 4 × 1 multilook → Terrain-Flattening → 20 m geocoding |
| Coherence | `wrappedInterferogram/HH/coherenceMagnitude` (20 m) and `unwrappedInterferogram` (80 m) | Back-Geocoding (Copernicus 30 m DEM) → 10 × 3 coherence (flat-earth and topographic phase removed) → 20 m geocoding. No ESD: a single burst covers the site |
| Pairs | 12 days; **the pair over the cut is a 24-day pair** (an acquisition is missing at the end of July) | 12 days (13 days at the S1A → S1C transition) |

The SNAP graphs are in `graphs/` of the [nisar_s1 package](https://github.com/mamadou-g-diallo/nisar-s1/blob/v0.4.0/src/nisar_s1/graphs). `scripts/05a_process_s1.py` runs the processing (25 products,
≈ 1 h). All layers are then resampled onto **a common 20 m grid in UTM 32N** (`nisar_s1.grid`): average in
linear power for NISAR γ⁰, bilinear for Sentinel-1.

## 2. Evaluation method (`scripts/05b_compare.py`, modules `stats` and `detect`)

- **Samples**: the C11 clear-cut (59 pixels of 20 m, 2.36 ha) and a ring of intact forest 100–275 m around the cut
  (548 pixels, 21.8 ha), both delineated from Sentinel-2 NDVI (step 3).
- **Phases**: before the cut (images, and coherence pairs, entirely before 27/07), after (entirely after 11/08),
  and pairs spanning the cut.
- **Change variables** per sensor and geometry:
  - `d_gamma0` = mean γ⁰ after − mean γ⁰ before (dB); `gamma0_post` = mean γ⁰ after;
  - `coh_change` = coherence of the pair spanning the cut; `coh_drop` = `coh_change` − coherence before;
    `d_coh` = coherence after − coherence before; `coh_post` = coherence after.
- **Separability metrics** cut / control: mean difference Δ, Cohen's d, **AUC** (Mann-Whitney,
  max(AUC, 1 − AUC)), Jeffries-Matusita distance (0–2). Neighbouring pixels are not independent, so no p-value
  is computed. Instead, a **95 % confidence interval is obtained by block bootstrap** with 3 × 3 pixel blocks
  (5 × 5 for the 80 m layers).
- **Detection prototype** over the whole window (188 × 187 pixels, 3.7 × 3.7 km). The reference is S2
  dNDVI ≤ −0.3 over forest (NDVI before ≥ 0.7), with ambiguous partial changes excluded: 95 cut pixels out of
  25,723 (0.4 %). Scores: AUC over the window, F1 at the Otsu threshold, and maximum F1.
- **Check**: before the cut, the cut and the control are **indistinguishable** (AUC 0.51–0.62 depending on the
  sensor), which validates the choice of control.
- **Sensitivity**: same computation with polygons eroded by 20 m (25 pure cut pixels), suffix `_erode20`.

## 3. Results

### 3.1 Comparable variables (20 m grid, no erosion)

| Variable | NISAR A144 | NISAR A72 | NISAR D138 | Sentinel-1 D139 |
|---|---|---|---|---|
| Cross-pol Δγ⁰ (HV / VH) | −4.3 dB, AUC **0.97** [0.93–0.99] | −3.7 dB, 0.94 | −2.3 dB, 0.84 | −2.2 dB, **0.91** [0.85–0.94] |
| Co-pol Δγ⁰ (HH / VV) | −4.2 dB, 0.96 | −3.0 dB, 0.92 | −1.7 dB, 0.72 | −2.5 dB, 0.90 |
| Coherence of the pair over the cut | −0.40, AUC **0.995** | −0.25, 0.92 | −0.31, **0.995** | −0.06, **0.71–0.74** |
| Δ coherence after − before | −0.09, 0.77 | −0.05, 0.65 | −0.01, 0.55 | +0.03 to +0.06, 0.65–0.70 |

(Δ = cut mean − control mean. Full tables: `results/tables/comparison_change.csv`; figure:
`results/figures/comparison_auc.png`.)

### 3.2 Findings

1. **Interferometric coherence: a clear L-band advantage.** On the pair spanning the cut, NISAR coherence of the
   cut drops to ≈ 0.26–0.33 while the control forest stays at 0.50–0.69 (AUC 0.995 for A144 and D138, **despite
   a 24-day pair**). At C band, the forest is already decorrelated after 12 days (coherence ≈ 0.25–0.30), so the
   cut adds almost nothing (−0.06, AUC ≈ 0.72). This is the physically expected result. L band penetrates the
   crown and stays coherent over forest. C band is dominated by leaves and twigs, which move.
2. **Backscatter: both bands see the cut, L band more strongly.** The cross-pol drop is −4 to −5 dB at L band,
   from the loss of volume scattering by trunks and branches. At C band it is ≈ −2 to −3 dB.
3. **Persistence: a decisive L-band advantage** (`comparison_persistence.png`, persistence table).
   - At HV, the NISAR contrast stays stable from August to November (AUC 0.91–0.95 for A144).
   - At C band it is unstable and **vanishes in October**: VH AUC 0.88 → 0.74; VV 0.86 → 0.66; 0.52 on 25/10.
   - In autumn, the wet bare soil and logging residues of the cut scatter strongly at C band and catch up with
     the forest.
4. **Geometry**: the two ascending orbits (A144, A72) separate better than the descending D138. On this slope, the
   shadow and edge effect of the cut depends on the look direction (cf. Bouvet et al., 2018).
5. **Cut date**: on 02/08, Sentinel-1 still sees no change (VH AUC 0.57); on 14/08 the change is clear. Combined
   with the NISAR dates, this places most of the cut **between 2 and 11 August 2026**.
6. **Sensitivity**: with polygons eroded by 20 m, every AUC increases (A144 HV 0.97 → 0.996; S1 VH 0.91 → 0.98
   for `gamma0_post`). The results are not an artefact of edge pixels.
7. **Detection over the window**:
   - The window AUC is 0.82–0.93 for the best NISAR variables and 0.86–0.87 for S1.
   - F1 stays low (≤ 0.29) because the cut covers only 0.4 % of the pixels: a threshold on a single variable
     produces many false alarms.
   - Operational detection requires a combination of variables, spatial filtering (minimum object size) and
     temporal confirmation (several dates).

## 4. Limitations

- **A single 2.4 ha site**: confidence intervals reflect pixel variability, not between-site variability.
  Generalisation requires several cuts (candidate C09 is a possible replication).
- **24-day NISAR pair** vs 12 days at C band: this penalises L band, which strengthens the conclusion.
- NISAR products are **provisional** (`PR`, 2026). Few dates are available before the cut (1 to 3 pairs).
- The 80 m coherence variables (AUC = 1) contain only ≈ 4 independent pixels inside the cut. They are
  indicative only and are excluded from the best-variable table.

## 5. Reproduce

```bash
python scripts/05a_process_s1.py
python scripts/05b_compare.py
python scripts/05b_compare.py --erode 20 --tag _erode20
python scripts/06_make_tables.py
```

Figures: `results/figures/comparison_*.png`. Tables: `results/tables/comparison_*.csv` and
`reports/latex/tables/`.
