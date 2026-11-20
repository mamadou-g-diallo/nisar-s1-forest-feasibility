"""Morvan step 8 — LaTeX tables (FR and EN) and synthesis figure from the step 6 / 6b / 7 results.

No number is copied by hand into the reports: every table is generated here from the CSV outputs.

Tables (``reports/morvan/latex/tables/<name>_<lang>.tex``):
- ``core``: AUC [95 % CI] of the main change indicators, L band vs C band at equal geometry;
- ``refs``: sensitivity of the AUC to the reference (automatic, verified, verified + probable, stand);
- ``guide``: guide method transposed to radar (area confusion matrix, objects found, false alarm rate);
- ``groups``: AUC by forest group (all reference cuts);
- ``dating``: radar cut dates of the reference cuts;
- ``separability``: full separability table (appendix).

Figure: ``results/morvan/figures/m8_summary_L_vs_C.png``.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from nisar_s1.config import PROJECT_ROOT, load_site  # noqa: E402

# geometry pairs at equal look direction: (direction, L-band geometry, C-band geometry)
PAIRS = [("asc", "NISAR A173F25", "S1 T059"), ("desc", "NISAR D66F65", "S1 T037")]
# indicator: (L-band variable, C-band variable, FR label, EN label)
INDICATORS = [
    ("d_g0_HV", "d_g0_VH", r"$\Delta\gamma^0$ pol. croisée", r"$\Delta\gamma^0$ cross-pol"),
    ("d_g0_HH", "d_g0_VV", r"$\Delta\gamma^0$ co-pol.", r"$\Delta\gamma^0$ co-pol"),
    ("g0_post_HV", "g0_post_VH", r"$\gamma^0$ après, pol. croisée", r"$\gamma^0$ after, cross-pol"),
    ("coh_min_HH", "coh_min_VV", "cohérence minimale (co-pol.)", "minimum coherence (co-pol)"),
    ("coh_post_HH", "coh_post_VV", "cohérence après (co-pol.)", "coherence after (co-pol)"),
]
REFS = [("_auto", "auto (60)", "automatic (60)"), ("_verifprob", "vérifiées + probables (19)",
                                                     "verified + probable (19)"),
        ("_verifie", "vérifiées (10)", "verified (10)"), ("", "peuplement (7)", "stand (7)")]
GEO_LABEL = {"NISAR A173F25": "L A173", "S1 T059": "C A59", "NISAR D66F65": "L D66", "S1 T037": "C D37"}


def fmt(x, nd=2, lang="fr"):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "--"
    s = f"{x:.{nd}f}"
    return s.replace(".", "{,}") if lang == "fr" else s


def auc_cell(row, lang, ci=True):
    if row is None:
        return "--"
    s = fmt(row.auc_sep, 2, lang)
    if ci:
        s += r" {\scriptsize [" + fmt(row.auc_lo, 2, lang) + "--" + fmt(row.auc_hi, 2, lang) + "]}"
    return s


def get(sep, geom, var):
    r = sep[(sep.geom == geom) & (sep.variable == var)]
    return None if r.empty else r.iloc[0]


def write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    print(path)


def table(cols: str, header: str, rows: list[str]) -> str:
    return ("\\begin{tabular}{" + cols + "}\n\\toprule\n" + header + r" \\" + "\n\\midrule\n"
            + "\n".join(r + r" \\" for r in rows) + "\n\\bottomrule\n\\end{tabular}\n")


def main() -> None:
    s = load_site("morvan")
    res = Path(s["chemins"]["results"])
    tab, figd = res / "tables", res / "figures"
    out = PROJECT_ROOT / "reports" / "morvan" / "latex" / "tables"
    sep = pd.read_csv(tab / "m6_separability.csv")
    gd = pd.read_csv(tab / "m6_guide_confusion.csv")

    for lang in ("fr", "en"):
        lab = 2 if lang == "fr" else 3
        # --- core table -----------------------------------------------------------------------
        hdr = ("Indicateur" if lang == "fr" else "Indicator") + " & " + " & ".join(
            GEO_LABEL[g] for _, l_, c_ in PAIRS for g in (l_, c_))
        rows = []
        for ind in INDICATORS:
            cells = []
            for _, gl, gc in PAIRS:
                cells += [auc_cell(get(sep, gl, ind[0]), lang), auc_cell(get(sep, gc, ind[1]), lang)]
            rows.append(ind[lab] + " & " + " & ".join(cells))
        write(out / f"core_{lang}.tex", table("lcccc", hdr, rows))

        # --- mean change (dB) of the cross-pol indicator ---------------------------------------
        rows = []
        for var_l, var_c, unit in (("d_g0_HV", "d_g0_VH", "dB"), ("coh_min_HH", "coh_min_VV", "")):
            cells = []
            for _, gl, gc in PAIRS:
                for g, v in ((gl, var_l), (gc, var_c)):
                    r = get(sep, g, v)
                    cells.append("--" if r is None else fmt(r.mean_a, 2, lang) + " / " + fmt(r.mean_b, 2, lang))
            name = {("d_g0_HV", "fr"): r"$\Delta\gamma^0$ croisée (dB)", ("d_g0_HV", "en"): r"cross-pol $\Delta\gamma^0$ (dB)",
                    ("coh_min_HH", "fr"): "cohérence min.", ("coh_min_HH", "en"): "min. coherence"}[(var_l, lang)]
            rows.append(name + " & " + " & ".join(cells))
        hdr2 = ("Coupe / forêt intacte" if lang == "fr" else "Cut / intact forest") + " & " + " & ".join(
            GEO_LABEL[g] for _, l_, c_ in PAIRS for g in (l_, c_))
        write(out / f"means_{lang}.tex", table("lcccc", hdr2, rows))

        # --- reference sensitivity --------------------------------------------------------------
        hdr = ("Référence (objets)" if lang == "fr" else "Reference (objects)") + " & " + " & ".join(
            GEO_LABEL[g] for _, l_, c_ in PAIRS for g in (l_, c_))
        rows = []
        for tag, fr_, en_ in REFS:
            f = tab / f"m6_separability{tag}.csv"
            if not f.exists():
                continue
            sp = pd.read_csv(f)
            cells = []
            for _, gl, gc in PAIRS:
                cells += [auc_cell(get(sp, gl, "d_g0_HV"), lang, ci=False),
                          auc_cell(get(sp, gc, "d_g0_VH"), lang, ci=False)]
            rows.append((fr_ if lang == "fr" else en_) + " & " + " & ".join(cells))
        write(out / f"refs_{lang}.tex", table("lcccc", hdr, rows))

        # --- guide transposition ----------------------------------------------------------------
        hdr = " & ".join(["Géométrie" if lang == "fr" else "Geometry", "Variable", "Degré" if lang == "fr" else "Degree",
                          "Omission (\\%)", "Commission (\\%)", "Kappa",
                          "Objets trouvés" if lang == "fr" else "Objects found",
                          "Fausses alertes (\\% forêt)" if lang == "fr" else "False alarms (\\% forest)"])
        rows = []
        for _, gl, gc in PAIRS:
            for g in (gl, gc):
                sub = gd[gd.geom == g].copy()
                best = sub.sort_values("f1", ascending=False).iloc[0]
                fa = 100 * best.fp_ha / (best.fp_ha + best.tn_ha)
                found = f"{round(best.objets_trouves_pct * best.objets_n / 100):.0f}/{best.objets_n:.0f}"
                rows.append(" & ".join([GEO_LABEL[g], best.variable.replace("_", r"\_"), f"$\\geq${best.degre_min:.0f}",
                                        fmt(best.omission_pct, 0, lang), fmt(best.commission_pct, 0, lang),
                                        fmt(best.kappa, 2, lang), found, fmt(fa, 2, lang)]))
        write(out / f"guide_{lang}.tex", table("lllrrrcr", hdr, rows))

        # --- by forest group (automatic reference, all 60 cuts) ---------------------------------
        f = tab / "m6_by_group_auto.csv"
        if f.exists():
            bg = pd.read_csv(f)
            grp_lab = {"feuillus": ("feuillus", "broadleaves"), "resineux": ("résineux", "conifers"),
                       "mixte": ("mixtes", "mixed")}
            hdr = ("Groupe (pixels coupe)" if lang == "fr" else "Group (cut pixels)") + " & " + " & ".join(
                GEO_LABEL[g] for _, l_, c_ in PAIRS for g in (l_, c_))
            rows = []
            for gk, names in grp_lab.items():
                cells, npx = [], None
                for _, gl, gc in PAIRS:
                    for g, v in ((gl, "d_g0_HV"), (gc, "d_g0_VH")):
                        r = bg[(bg.geom == g) & (bg.variable == v) & (bg.groupe == gk)]
                        cells.append("--" if r.empty else fmt(r.iloc[0].auc_sep, 2, lang))
                        npx = npx or (None if r.empty else int(r.iloc[0].n_coupe_px))
                rows.append(f"{names[0 if lang == 'fr' else 1]} ({npx}) & " + " & ".join(cells))
            write(out / f"groups_{lang}.tex", table("lcccc", hdr, rows))

        # --- dating -----------------------------------------------------------------------------
        f = tab / "m7_cut_dates.csv"
        if f.exists():
            dt = pd.read_csv(f)
            dt = dt[dt.foret_avant]
            geoms = [g for _, l_, c_ in PAIRS for g in (l_, c_)]
            hdr = ("Coupe" if lang == "fr" else "Cut") + " & " + " & ".join(GEO_LABEL[g] for g in geoms)
            rows = []
            for cid, d in dt.groupby("id"):
                cells = []
                for g in geoms:
                    r = d[d.geom == g]
                    if r.empty or pd.isna(r.iloc[0].coupe_avant):
                        cells.append("--")
                    else:
                        a, b = str(r.iloc[0].coupe_apres)[5:], str(r.iloc[0].coupe_avant)[5:]
                        cells.append(f"{a.replace('-', '/')[3:]}/{a[:2]}--{b[3:]}/{b[:2]}"
                                     if a != "None" and a != "nan" else f"$\\leq$ {b[3:]}/{b[:2]}")
                gr = {"feuillus": "F", "resineux": "R", "mixte": "M"}[d.iloc[0].groupe]
                rows.append(f"{cid} ({gr}, {fmt(d.iloc[0].area_ha, 1, lang)} ha) & " + " & ".join(cells))
            write(out / f"dating_{lang}.tex", table("lcccc", hdr, rows))

        # --- full separability (appendix) -------------------------------------------------------
        full = sep[~sep.variable.str.startswith("precheck")]
        hdr = " & ".join(["Géométrie" if lang == "fr" else "Geometry", "Variable", "Coupe" if lang == "fr" else "Cut",
                          "Forêt" if lang == "fr" else "Forest", "d", "AUC", "IC 95 \\%" if lang == "fr" else "95 \\% CI",
                          "JM"])
        rows = [" & ".join([GEO_LABEL[r.geom], r.variable.replace("_", r"\_"), fmt(r.mean_a, 2, lang),
                            fmt(r.mean_b, 2, lang), fmt(r.cohen_d, 2, lang), fmt(r.auc_sep, 2, lang),
                            fmt(r.auc_lo, 2, lang) + "--" + fmt(r.auc_hi, 2, lang), fmt(r.jm, 2, lang)])
                for r in full.itertuples()]
        write(out / f"separability_{lang}.tex", table("llrrrrcr", hdr, rows))

    # --- synthesis figure ---------------------------------------------------------------------------
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True, constrained_layout=True)
    for ax, (dname, gl, gc) in zip(axs, PAIRS):
        x = np.arange(len(INDICATORS))
        for k, (g, col, idx) in enumerate(((gl, "#2E7D32", 0), (gc, "#7B4FA8", 1))):
            vals, lo, hi = [], [], []
            for ind in INDICATORS:
                r = get(sep, g, ind[idx])
                vals.append(np.nan if r is None else r.auc_sep)
                lo.append(np.nan if r is None else r.auc_sep - r.auc_lo)
                hi.append(np.nan if r is None else r.auc_hi - r.auc_sep)
            ax.bar(x + (k - 0.5) * 0.38, vals, 0.38, yerr=[lo, hi], capsize=3, color=col,
                   label=("L band (NISAR) " if k == 0 else "C band (Sentinel-1) ") + GEO_LABEL[g].split()[1])
        ax.axhline(0.5, color="0.4", lw=0.8, ls=":")
        ax.set_xticks(x, [i[3].replace("$\\Delta\\gamma^0$", "Δγ⁰").replace("$\\gamma^0$", "γ⁰") for i in INDICATORS],
                      rotation=20, ha="right", fontsize=8)
        ax.set_ylim(0.4, 1.0)
        ax.set_title(("Ascending" if dname == "asc" else "Descending") + " geometry", fontsize=10)
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(axis="y", alpha=0.3)
    axs[0].set_ylabel("AUC (cut vs intact forest), 95 % cluster-bootstrap CI")
    fig.suptitle("Morvan — 7 verified clear-cuts of closed stands: L band vs C band at equal geometry", fontsize=10)
    p = figd / "m8_summary_L_vs_C.png"
    fig.savefig(p, dpi=140)
    print(p)


if __name__ == "__main__":
    main()
