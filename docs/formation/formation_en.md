# NISAR / Sentinel-1 training kit: 19 executed notebooks

The full description (modules, data, running, references) is in
[`notebooks/README.md`](../../notebooks/README.md). This page summarises what running the kit on the
Vosges clear-cut showed.

* **Consistency checks.** The C2 matrix rebuilt from the GSLC meets every physical constraint
  (no |ρ| > 1, no negative determinant). It correlates with the same-date GCOV at r = 0.79, with a
  clear peak at zero shift: the georeferencing is correct to within one 40 m pixel. The exported
  GeoTIFFs read back identical to the arrays in memory.
* **GCOV time series (11 dates).** After the cut, the cut − control contrast drops by 5.1 dB in HV
  and 4.5 dB in HH, and stays low.
* **Polarimetry (40 m, 32 looks).** The powers carry the signal. The power drop separates the cut
  from the control forest almost perfectly:
  - L-band: AUC 0.985 in HH and 0.975 in HV;
  - C-band: AUC 0.90 in VV and 0.97 in VH.

  The drop is larger at L-band (−4.3 dB in cross-pol, against −2.2 dB at C-band). The normalized
  parameters H, ᾱ, DpRVI and m, however, change by only a few hundredths (AUC 0.52–0.59). A fresh
  cut (stumps, slash, rough soil) still depolarizes, so HH and HV fall together. For clear-cut
  detection, the complex GSLC (13 GB per date) therefore adds nothing over the GCOV powers.
* **Limits.** One 2.4 ha cut (16 pixels at 40 m), one site, one season. The method transfers; the
  numbers have to be re-established elsewhere.

Structure adapted from D. K. Pandey's NISAR GCOV training toolkit (Apache-2.0,
doi:10.5281/zenodo.24458160) to the dual-pol HH/HV mode acquired over Europe; code in the `nisar_s1`
package, intended for reuse on ESA ROSE-L L2 products. NISAR L2 products are generated with ISCE3.
