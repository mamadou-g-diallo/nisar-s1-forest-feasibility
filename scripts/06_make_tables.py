"""Step 6a — LaTeX tables (French and English) generated from the result CSV files, so that the
numbers in the two reports come directly from the computation (no manual copy).

Outputs: ``reports/latex/tables/*_{fr,en}.tex``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from nisar_s1.config import PROJECT_ROOT

TAB = PROJECT_ROOT / "results" / "tables"
OUT = PROJECT_ROOT / "reports" / "latex" / "tables"

VAR = {  # variable -> (fr, en)
    "d_gamma0": ("$\\Delta\\gamma^0$ après $-$ avant (dB)", "$\\Delta\\gamma^0$ after $-$ before (dB)"),
    "gamma0_post": ("$\\gamma^0$ après (dB)", "$\\gamma^0$ after (dB)"),
    "d_coh": ("$\\Delta$ cohérence après $-$ avant", "$\\Delta$ coherence after $-$ before"),
    "coh_post": ("cohérence après", "coherence after"),
    "coh_change": ("cohérence de la paire sur la coupe", "coherence of the pair over the cut"),
    "coh_drop": ("chute de cohérence (paire sur la coupe $-$ avant)", "coherence drop (pair over the cut $-$ before)"),
    "d_coh80": ("$\\Delta$ cohérence 80 m", "$\\Delta$ coherence 80 m"),
    "coh80_post": ("cohérence 80 m après", "coherence 80 m after"),
    "coh80_change": ("cohérence 80 m, paire sur la coupe", "coherence 80 m, pair over the cut"),
    "coh80_drop": ("chute de cohérence 80 m", "coherence drop 80 m"),
}


def _var(v: str, lang: int) -> str:
    base, pol = v.rsplit("_", 1)
    return f"{VAR.get(base, (base, base))[lang]} {pol}"


def _num(x, fmt="{:.2f}", lang=0):
    if pd.isna(x):
        return "--"
    s = fmt.format(x)
    s = s.replace(".", "{,}") if lang == 0 else s
    return s.replace("-", "$-$", 1) if s.startswith("-") else s


def sensor_label(r) -> str:
    band = "L" if r.sensor.startswith("NISAR") else "C"
    name = "NISAR" if band == "L" else "Sentinel-1"
    return f"{name} {r.geom}"


def change_table(df: pd.DataFrame, lang: int, path, caption: tuple[str, str], label: str) -> None:
    hdr = (["Capteur", "Variable", "$n_{av}/n_{ap}$", "$\\Delta$", "$d$", "AUC [IC 95\\,\\%]", "JM",
            "AUC fen.", "F1$_{max}$"],
           ["Sensor", "Variable", "$n_{bef}/n_{aft}$", "$\\Delta$", "$d$", "AUC [95\\,\\% CI]", "JM",
            "win. AUC", "F1$_{max}$"])[lang]
    lines = ["\\begin{table}[htbp]", "\\centering", "\\scriptsize",
             f"\\caption{{{caption[lang]}}}", f"\\label{{{label}}}",
             "\\begin{tabular}{llcrrlrrr}", "\\toprule", " & ".join(hdr) + " \\\\", "\\midrule"]
    prev = None
    for _, r in df.iterrows():
        sl = sensor_label(r)
        if prev is not None and sl != prev:
            lines.append("\\addlinespace")
        prev = sl
        auc = f"{_num(r.auc_sep, lang=lang)} [{_num(r.ci_lo, lang=lang)}--{_num(r.ci_hi, lang=lang)}]"
        aw = max(r.auc_window, 1 - r.auc_window) if pd.notna(r.get("auc_window")) else np.nan
        lines.append(" & ".join([sl, _var(r.variable, lang), f"{int(r.n_pre)}/{int(r.n_post)}",
                                 _num(r.delta, lang=lang), _num(r.cohen_d, "{:.1f}", lang),
                                 auc, _num(r.jm, lang=lang), _num(aw, lang=lang),
                                 _num(r.get("f1_best"), lang=lang)]) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
    path.write_text("\n".join(lines) + "\n")


CORE = ["d_gamma0_HV", "d_gamma0_VH", "d_gamma0_HH", "d_gamma0_VV", "coh_change_HH", "coh_change_VV",
        "coh_change_VH", "d_coh_HH", "d_coh_VV", "d_coh_VH"]


def persistence_table(ts: pd.DataFrame, lang: int, path) -> None:
    """Per-date separation AUC of the backscatter after the cut, averaged over two periods: it
    shows whether the contrast persists (L band) or fades in autumn (C band)."""
    g = ts[(ts.kind == "g0") & (ts.phase == "post")].copy()
    g["date"] = pd.to_datetime(g.date)
    g["per"] = np.where(g.date < "2026-10-01", "a", "b")
    rows = g.groupby(["sensor", "geom", "pol", "per"]).agg(auc=("auc_sep", "mean"), delta=("delta", "mean"),
                                                         n=("auc_sep", "size")).unstack("per")
    hdr = (["Capteur", "Pol.", "AUC août--sept.", "$\\Delta$ (dB)", "AUC oct.--nov.", "$\\Delta$ (dB)"],
           ["Sensor", "Pol.", "AUC Aug--Sep", "$\\Delta$ (dB)", "AUC Oct--Nov", "$\\Delta$ (dB)"])[lang]
    cap = ("Persistance du contraste de rétrodiffusion après la coupe : AUC de séparation et écart "
           "coupe $-$ témoin, moyennés par date sur deux périodes.",
           "Persistence of the backscatter contrast after the cut: separation AUC and cut $-$ control "
           "difference, averaged per date over two periods.")[lang]
    lines = ["\\begin{table}[htbp]", "\\centering", "\\small", f"\\caption{{{cap}}}",
             "\\label{tab-persistence}", "\\begin{tabular}{llrrrr}", "\\toprule", " & ".join(hdr) + " \\\\",
             "\\midrule"]
    for (sensor, geom, pol), r in rows.iterrows():
        name = ("NISAR " if sensor.startswith("NISAR") else "Sentinel-1 ") + geom
        lines.append(" & ".join([name, pol, _num(r[("auc", "a")], lang=lang), _num(r[("delta", "a")], "{:.1f}", lang),
                                 _num(r[("auc", "b")], lang=lang), _num(r[("delta", "b")], "{:.1f}", lang)]) + " \\\\")
    lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ch = pd.read_csv(TAB / "comparison_change.csv")
    ch["band"] = np.where(ch.sensor.str.startswith("NISAR"), 0, 1)
    ch = ch.sort_values(["band", "geom", "auc_sep"], ascending=[True, True, False])
    for lang, suf in ((0, "fr"), (1, "en")):
        change_table(ch, lang, OUT / f"separability_{suf}.tex",
                     ("Séparabilité coupe rase / forêt témoin des variables de changement "
                      "($\\Delta$ : moyenne coupe $-$ moyenne témoin ; $d$ : d de Cohen ; AUC : max(AUC, 1$-$AUC) "
                      "avec IC par bootstrap par blocs ; JM : Jeffries-Matusita ; AUC fen. et F1$_{max}$ : "
                      "détection pixel à pixel sur toute la fenêtre, référence dNDVI S2).",
                      "Clear-cut / control forest separability of the change variables ($\\Delta$: cut mean "
                      "$-$ control mean; $d$: Cohen's d; AUC: max(AUC, 1$-$AUC) with block-bootstrap CI; "
                      "JM: Jeffries-Matusita; win.\\ AUC and F1$_{max}$: pixel-wise detection over the whole "
                      "window, S2 dNDVI reference)."),
                     "tab-separability")
        # best variable per sensor family (summary)
        fine = ch[ch.res_m == 20] if "res_m" in ch else ch[~ch.variable.str.contains("coh80")]
        best = fine.loc[fine.groupby(["band", "geom"]).auc_sep.idxmax()].sort_values(["band", "auc_sep"],
                                                                                  ascending=[True, False])
        change_table(best, lang, OUT / f"best_{suf}.tex",
                     ("Meilleure variable à 20 m par capteur et géométrie.", "Best 20 m variable per sensor and geometry."),
                     "tab-best")
        core = ch[ch.variable.isin(CORE)]
        change_table(core, lang, OUT / f"core_{suf}.tex",
                     ("Variables comparables entre capteurs (20 m) : variation de $\\gamma^0$, cohérence de la "
                      "paire qui encadre la coupe et variation de cohérence (après $-$ avant).",
                      "Variables comparable across sensors (20 m): $\\gamma^0$ change, coherence of the pair "
                      "spanning the cut and coherence change (after $-$ before)."), "tab-core")
        ts = pd.read_csv(TAB / "comparison_timeseries.csv")
        persistence_table(ts, lang, OUT / f"persistence_{suf}.tex")
    print(f"tables written to {OUT}")


if __name__ == "__main__":
    main()
