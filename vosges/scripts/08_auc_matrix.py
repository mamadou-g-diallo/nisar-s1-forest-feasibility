"""Annex figure for the Vosges slides: separation AUC of every change variable, as a matrix
(rows: variables, columns: sensor / geometry), readable on a 16:9 slide.

Input: ``vosges/results/tables/comparison_change.csv`` (step 5b). Output:
``vosges/results/figures/comparison_auc_matrix_fr.png``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from nisar_s1.config import PROJECT_ROOT
from nisar_s1.plots import value_matrix

TAB = PROJECT_ROOT / "vosges" / "results" / "tables"
FIG = PROJECT_ROOT / "vosges" / "results" / "figures"

COLS = {  # column label -> (sensor, geometry)
    "L A144\n(montante)": ("NISAR-L", "A144F26"),
    "L A72\n(montante)": ("NISAR-L", "A72F26"),
    "L D138\n(descendante)": ("NISAR-L", "D138F64"),
    "C D139\n(descendante)": ("S1-C", "T139"),
}
# rows: (label, NISAR variable, Sentinel-1 variable)
ROWS = [
    ("Paire à cheval sur la coupe", "coh_change_HH", "coh_change_VV"),
    ("Chute : à cheval − avant", "coh_drop_HH", "coh_drop_VV"),
    ("Δ : après − avant", "d_coh_HH", "d_coh_VV"),
    ("Cohérence après", "coh_post_HH", "coh_post_VV"),
    ("Paire à cheval (VH)", None, "coh_change_VH"),
    ("Chute (VH)", None, "coh_drop_VH"),
    ("Δ après − avant (VH)", None, "d_coh_VH"),
    ("Cohérence après (VH)", None, "coh_post_VH"),
    ("Paire à cheval (80 m)", "coh80_change_HH", None),
    ("Chute (80 m)", "coh80_drop_HH", None),
    ("Δ après − avant (80 m)", "d_coh80_HH", None),
    ("Cohérence après (80 m)", "coh80_post_HH", None),
    ("Δγ⁰ croisée (HV | VH)", "d_gamma0_HV", "d_gamma0_VH"),
    ("γ⁰ après, croisée", "gamma0_post_HV", "gamma0_post_VH"),
    ("Δγ⁰ co-pol. (HH | VV)", "d_gamma0_HH", "d_gamma0_VV"),
    ("γ⁰ après, co-pol.", "gamma0_post_HH", "gamma0_post_VV"),
]
GROUPS = [("Cohérence\nHH | VV", 4), ("Cohérence\nVH (C)", 4), ("Cohérence\n80 m (L)", 4),
          ("Rétro-\ndiffusion", 4)]


def main() -> None:
    df = pd.read_csv(TAB / "comparison_change.csv")
    auc = {(r.sensor, r.geom, r.variable): r.auc_sep for r in df.itertuples()}
    mat = pd.DataFrame(np.nan, index=[r[0] for r in ROWS], columns=list(COLS))
    for label, var_l, var_c in ROWS:
        for col, (sensor, geom) in COLS.items():
            var = var_l if sensor == "NISAR-L" else var_c
            if var is not None:
                mat.loc[label, col] = auc.get((sensor, geom, var), np.nan)
    assert mat.notna().sum().sum() == len(df), "every variable of the table must appear once"
    value_matrix(mat, FIG / "comparison_auc_matrix_fr.png", groups=GROUPS,
                 cbar_label="AUC de séparation coupe / forêt\n(0,5 = hasard ; 1 = parfait)",
                 decimal=",", figsize=(13, 6.4), fontsize=14)
    print("écrit :", FIG / "comparison_auc_matrix_fr.png", f"({int(mat.notna().sum().sum())} valeurs)")


if __name__ == "__main__":
    main()
