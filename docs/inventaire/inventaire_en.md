# Step 2 — Product inventory (Sentinel-1, NISAR, BIOMASS)

*🇫🇷 Version française : [inventaire_fr.md](inventaire_fr.md)*

*Search footprint: Vosges / Alsace, bbox `[6.70, 47.70, 7.70, 48.80]` (WGS84). Period: 2026-06-01 → 2026-11-30.
Catalogue queried on 2026-11-18 via ASF (`asf_search` 14.1). Reproduce with `python scripts/02_inventory.py`;
tables in `results/tables/inventory_*.csv`.*

## 1. Key findings

1. **NISAR data exist over the area and period**: 546 products of all levels, including **93 GCOV** and **67 GUNW**
   (June 18 → Nov 10, 2026). The L-band vs C-band comparison is feasible.
2. **Two NISAR geometries fully cover the search area**: ascending **track 144 / frame 26** and descending
   **track 138 / frame 64** (100 % AOI cover), plus ascending **track 72 / frame 26** (97 %).
   All three acquire in **20+5 MHz, dual-pol HH/HV** mode.
3. **Resolution is compatible with clear-cut sizes**: GCOV is at **20 m** (20 MHz main band) or 10 m (40 MHz),
   and GUNW provides **coherence at 20 m** (and 80 m). A 5 ha clear-cut covers about 125 pixels at 20 m.
4. **GUNW is co-polarised only (HH)** and nearest-neighbour (**12-day**, 24 days when an acquisition is missing).
   HV information therefore comes only from **GCOV backscatter**, not from coherence.
5. **GUNW stops at 2026-10-26** (latest secondary date) because of processing latency, while GCOV goes to Nov 10.
   For coherence, the clear-cut must happen **between late June and mid-October 2026**.
6. **Most GUNW are "provisional"** (`NISAR_L2_GUNW_PROVISIONAL_V1`: 64 of 67). This must be stated as a limitation.
7. **Sentinel-1 is dense**: 263 IW SLC (VV+VH), 5 relative orbits, **6-day** median revisit with S1A, S1C and S1D.
   This means a **12-day** S1 coherence can be formed to match NISAR exactly.
8. **BIOMASS (P-band) cannot be used here**: acquisitions over Europe and North America are blocked by the US
   Space Objects Tracking Radar (SOTR) exclusion zone.

## 2. Sentinel-1 (C-band, λ ≈ 5.6 cm)

| Direction | Relative orbit | Acquisitions | Median revisit | Max AOI cover | Satellites |
|-----------|----------------|--------------|----------------|---------------|------------|
| Ascending | 15 | 29 | 6 d | 70 % | S1A + S1C + S1D |
| Ascending | 88 | 27 | 6 d | 92 % | S1A + S1C + S1D |
| Descending | 37 | 29 | 6 d | 4 % | S1A + S1C + S1D |
| Descending | 66 | 28 | 6 d | 48 % | S1A + S1C + S1D |
| Descending | 139 | 31 | 6 d | **100 %** | S1A + S1C + S1D |

- Product: IW SLC, VV+VH, about **4.7 GB** per scene (median). Processing will stay on 2–3 bursts (TOPSAR-Split).
- Platform split: S1D 125, S1C 116, S1A 22 scenes.
- "Acquisitions" counts distinct days; a day can contain 2 consecutive slices.

## 3. NISAR (L-band, λ ≈ 24 cm)

### 3.1 Products available over the area (all levels)

| Level | Product | Content | Mode (count) | Median size |
|-------|---------|---------|--------------|-------------|
| L1 | RSLC | Range-Doppler SLC | 20+5 DH (55), 40+5 DH (35), SH (3) | 15–26 GB |
| L1 | RIFG / RUNW / ROFF | Wrapped / unwrapped interferogram, offsets (radar geometry) | 20 or 40 MHz, HH | 0.3–1.4 GB |
| L2 | GSLC | Geocoded SLC | as RSLC | 13–23 GB |
| L2 | **GCOV** | Geocoded, RTC **γ⁰ covariance** (HHHH, HVHV) | 20+5 DH (55), 40+5 DH (35), SH (3) | **2.1 GB** (20+5), 7.2 GB (40+5) |
| L2 | **GUNW** | Geocoded **unwrapped interferogram + coherence** | 20 MHz HH (44), 40 MHz HH (23) | **2.4 GB** |
| L2 | GOFF | Geocoded pixel offsets | 20 or 40 MHz HH | 1.2 GB |

Mode codes in file names: `2005` = 20 MHz main band + 5 MHz side band; `DHDH` = dual-pol HH/HV on both bands;
`SH` = single HH.

### 3.2 GCOV — revisit per geometry

| Direction | Track | Frame | Acquisitions | Revisit | AOI cover | Mode |
|-----------|-------|-------|--------------|---------|-----------|------|
| Ascending | **144** | **26** | 11 | 12 d | **100 %** | 20+5 DH |
| Ascending | 72 | 26 | 12 | 12 d | 97 % | 20+5 DH |
| Ascending | 72 | 25 | 12 | 12 d | ~15 % | 40+5 DH |
| Descending | **138** | **64** | 10 | 12 d | **100 %** | 20+5 DH |
| Descending | 66 | 64 | 12 | 12 d | ~22 % | 20+5 DH |
| Descending | 37 | 64 | 11 | 12 d | ~15–30 % | 20+5 / 40+5 DH |
| Descending | 37 | 65 | 11 | 12 d | ~10 % | 40+5 DH |

GCOV is already **radiometrically terrain-corrected (γ⁰, area-based RTC with the Copernicus DEM)**. A
`rtcGammaToSigmaFactor` layer converts it to σ⁰. Dual-pol products contain only diagonal terms. Off-diagonal terms
(e.g. HH·HV*) would have to be rebuilt from GSLC, which is out of scope here.

### 3.3 GUNW — interferometric pairs per geometry

| Direction | Track | Frame | 12-day pairs | 24-day pairs | First reference → last secondary | AOI cover |
|-----------|-------|-------|--------------|--------------|----------------------------------|-----------|
| Ascending | **144** | **26** | 9 | 1 | 2026-06-24 → 2026-10-22 | **100 %** |
| Ascending | 72 | 26 | 8 | 1 | 2026-06-19 → 2026-10-17 | 97 % |
| Descending | **138** | **64** | 7 | 1 | 2026-07-05 → 2026-10-21 | **100 %** |
| Descending | 37 | 64 | 16 | 2 | 2026-06-28 → 2026-10-26 | 30 % |
| Descending | 66 | 64 | 8 | 1 | 2026-06-18 → 2026-10-16 | 23 % |
| Ascending | 72 | 25 | 4 | 1 | 2026-06-19 → 2026-10-17 | 17 % |
| Descending | 37 | 65 | 7 | 1 | 2026-06-28 → 2026-10-14 | 17 % |

GUNW layers: unwrapped phase at 80 m, wrapped interferogram and **coherence magnitude at 20 m** (also 80 m), and an
ionospheric phase screen (provided, **not applied** by default). Ionosphere matters for phase (landslides), but not
for coherence magnitude.

## 4. BIOMASS (P-band, λ ≈ 70 cm)

- Data have been open since the end of commissioning (January 2026).
- **No acquisitions over Europe and North America**: the observation mask excludes the zone covered by the US
  Space Objects Tracking Radar (SOTR).
- Consequence: BIOMASS is **not usable for this site**. P-band remains an outlook, for example
  on tropical forest sites, where it would add biomass sensitivity (trunks, large branches).

## 5. Implications for the next steps

| Item | Decision / constraint |
|------|-----------------------|
| NISAR geometry | Prioritise **A144/F26** and **D138/F64** (full cover, 20 m, dual-pol); A72/F26 as a third geometry |
| Sentinel-1 geometry | **D139** (100 % cover) and **A88** (92 %); match direction with NISAR when possible |
| Clear-cut date window | **Late June → mid-October 2026** (GUNW availability, pairs before *and* after the cut) |
| Common grid | **20 m**, UTM 32N (NISAR GCOV/GUNW coherence at 20 m; S1 multilooked to about 20 m) |
| Temporal baseline | **12 days** for both sensors (S1 6-day revisit allows it) |
| Polarisations | Coherence: NISAR HH vs S1 VV/VH. Backscatter: NISAR HH/HV/HV÷HH vs S1 VV/VH/VH÷VV |
| Download volume (step 4) | GCOV about 2 GB, GUNW about 2.4 GB, S1 SLC about 4.7 GB each → a few tens of GB on the external drive |
| Limitations to report | GUNW provisional; GUNW HH only; BIOMASS absent; S1 and NISAR acquisition times differ (morning vs evening passes) |

## 6. Tools for the processing chain

| Tool | Use in this project | Note for ROSE-L |
|------|---------------------|-----------------|
| `asf_search`, `earthaccess` | catalogue search, authenticated download (`nisar_s1.search`) | same API for any ASF-hosted mission |
| `h5py` / `xarray` | read GCOV/GUNW HDF5 by window, so memory use stays low | basis of `nisar_s1.io_nisar` |
| SNAP 14 (`gpt`) | S1 coherence and γ⁰ (TOPSAR-Split, Back-Geocoding, Coherence, Terrain-Flattening) | standard Sentinel-1 C-band chain |
| ISCE3 | official NISAR processor (produces GCOV, GUNW…); could build custom pairs or off-diagonal terms from RSLC/GSLC | likely path for ROSE-L processing |
| ASF HyP3 | on-demand S1 coherence (fallback if RAM is limiting) | — |

## Sources

- ASF NISAR documentation — GCOV: <https://nisar-docs.asf.alaska.edu/gcov/>
- ASF NISAR documentation — GUNW: <https://nisar-docs.asf.alaska.edu/gunw/>
- NASA Earthdata catalogue, NISAR L2 GUNW (provisional): <https://www.earthdata.nasa.gov/data/catalog/asf-nisar-l2-gunw-provisional-v1-1>
- JPL D-102272, NISAR L2 GUNW Product Specification: <https://nisar.asf.earthdatacloud.nasa.gov/NISAR-SAMPLE-DATA/DOCS/NISAR_D-102272_L2_GUNW_Product_Spec_R3.4_231109_clean_w-sigs.pdf>
- K. Scipal, *Biomass Mission Overview* (ESA, 2026): <https://eo-college.org/wp-content/uploads/2026/03/02_Biomass_Mission_Overview-Klaus-Scipal.pdf>
- ESA Earth Online — Biomass mission description: <https://earth.esa.int/eogateway/missions/biomass/description>
- BELSPO — "ESA's Biomass data now available": <https://eo.belspo.be/en/news/esas-biomass-data-now-available>
