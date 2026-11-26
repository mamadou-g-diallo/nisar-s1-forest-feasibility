# Step 4 — NISAR and Sentinel-1 data acquisition

*Version française : [acquisition_fr.md](acquisition_fr.md)*

## Constraint: network throughput

Measured Earthdata throughput: **≈ 1.8 MB/s per connection**. A NISAR GUNW is 2.4 GB and a GCOV 2.1 GB
(≈ 20 min each); a Sentinel-1 SLC is 4.6 GB (≈ 45 min). Downloading everything (≈ 60 NISAR products and
13 SLCs) would have taken about 30 h. Two techniques reduce the volume with no information loss for the site.

## NISAR: remote window reads (`vosges/scripts/04_fetch_nisar.py`, module `io_nisar`)

NISAR L2 products (HDF5, produced by ISCE3) are **chunked in 512 × 512 pixel blocks** on a 20 m UTM 32N grid.
`io_nisar` opens the file directly on the Earthdata HTTPS URL (`earthaccess` + `fsspec` + `h5py`) and reads
only the chunks covering the site window (site + 1.5 km, ≈ 3.7 × 3.7 km): **≈ 15 s per layer instead of
≈ 20 min per file**. Sub-scenes are saved as GeoTIFF on the external disk, with provenance (granule name) in
`vosges/results/tables/nisar_extracted.csv`.

Extracted layers:

| Product | Layer (frequency A, 20 MHz) | Resolution |
|---|---|---|
| GCOV | γ⁰ HH (`HHHH`), γ⁰ HV (`HVHV`), radiometrically terrain-corrected (RTC) | 20 m |
| GUNW | coherence `wrappedInterferogram/HH/coherenceMagnitude` | 20 m |
| GUNW | coherence, unwrapped phase, connected components (`unwrappedInterferogram`) | 80 m |

Every geometry whose footprint fully contains the window is used:

| Geometry | GCOV (dates) | 12-day GUNW | 24-day GUNW (pair over the cut) |
|---|---|---|---|
| A144 F26 (ascending) | 11 (24/06 → 03/11) | 8 | 18/07 → 11/08 |
| A72 F26 (ascending) | 10 (19/06 → 10/11) | 8 | 25/07 → 18/08 |
| D138 F64 (descending) | 11 (05/07 → 02/11) | 7 | 17/07 → 10/08 |

Notes:
- in all three geometries **the pair bracketing the cut is a 24-day pair** (an acquisition is missing at the
  end of July); there is no 12-day pair over the cut;
- D66 F64 has a single GCOV in another projection: not used;
- signed CloudFront URLs expire: the script retries with a fresh session.

## Sentinel-1: reduced SAFE (`vosges/scripts/04_fetch_s1.py`, module `download`)

- Orbit **D139** (descending, 05:42 UTC), sub-swath **IW2** (found with the ASF burst catalogue), VV + VH.
- Chain of **13 dates 12 days apart** (14/06 → 06/11/2026), the same interval as NISAR: S1A until 26/06 (transition pair 26/06 → 09/07: 13 days),
  then S1C.
- The remote zip is read with HTTP range requests (`HttpRangeFile`): only the manifest, annotation,
  calibration, noise and IW2 measurement files are extracted. **1.58 GB instead of 4.6 GB per date**.
  Three parallel streams (`--shard`), ≈ 1.1 MB/s each.
- SNAP reads these reduced SAFE products in single-swath mode (`enableSingleSwathMode` of TOPSAR-Split).

## Reproduce

```bash
python vosges/scripts/04_fetch_nisar.py
python vosges/scripts/04_fetch_s1.py --start 2026-06-14 --end 2026-11-07 --shard 0/3   # same with 1/3 and 2/3
```

Data stay on the external disk (`/media/dell/Transcend1/nisar_data`), never in Git.
