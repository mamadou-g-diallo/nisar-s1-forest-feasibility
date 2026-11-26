"""Figures of the French poster (labels in French), read from the result tables of the three studies.

f0_localisation.png  France, the three sites and the Morvan sylvo-ecoregion G23
f1_vosges.png        clear-cut C11: separation AUC per indicator and geometry
f2_morvan.png        7 verified clear-cuts: AUC with 95 % cluster-bootstrap CI, equal geometry
f3_sechilienne.png   forested slope: coherence and phase consistency of the 17 pairs

Run from the repository root: python poster/poster_figures.py
"""
import json
import sys
import urllib.request
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import geopandas as gpd  # noqa: E402
import matplotlib.dates as mdates  # noqa: E402,F401
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "morvan" / "scripts"))
from m8_make_tables import GEO_LABEL, INDICATORS, PAIRS, get  # noqa: E402

OUT = ROOT / "poster" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
NE = ROOT / "data" / "naturalearth" / "ne_50m_admin_0_countries.zip"

L1, L2, L3, C = "#1f5fae", "#6fa3e0", "#0d3b73", "#d4541f"
INK, MUTED, GRID = "#1d1d1d", "#6b6b6b", "#e6e6e6"
W = 15.3   # column width of the A0 poster, inches: fonts below are close to their printed size
plt.rcParams.update({"font.size": 23, "axes.titlesize": 23, "axes.labelsize": 23, "xtick.labelsize": 21,
                     "ytick.labelsize": 21, "legend.fontsize": 20, "font.family": "DejaVu Sans"})
VIRG = mticker.FuncFormatter(lambda v, _: f"{v:g}".replace(".", ",").replace("-", "−"))


def dec(x, nd=2):
    nd = 3 if nd == 2 and 0.99 < x < 1 else nd     # 0.995 stays 0,995 instead of rounding to 1,00
    return f"{x:.{nd}f}".replace(".", ",")


def tidy(ax):
    ax.grid(axis="y", color=GRID, lw=0.9); ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#aaaaaa")
    ax.tick_params(colors="#444444")


# 0. Location -------------------------------------------------------------------------------------
print("[1/4] localisation", flush=True)
if not NE.exists():
    NE.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request("https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip",
                                 headers={"User-Agent": "nisar-s1-forest-france/1.0"})
    NE.write_bytes(urllib.request.urlopen(req, timeout=300).read())
world = gpd.read_file(f"zip://{NE}")
fr = world[world.ADMIN == "France"].explode(index_parts=False)
fr = fr[fr.geometry.centroid.x.between(-6, 10) & fr.geometry.centroid.y.between(41, 52)]   # metropolitan France
cut = json.load(open(ROOT / "config" / "site.geojson"))["features"][0]["properties"]
g23 = gpd.read_file(ROOT / "morvan" / "results" / "zone_g23.geojson").to_crs(4326)
win = gpd.read_file(ROOT / "morvan" / "results" / "fenetre_radar.geojson").to_crs(4326)
sites = [(cut["lon"], cut["lat"], "Vosges\ncoupe rase C11", (-1.2, 1.15)),
         (*win.geometry.iloc[0].centroid.coords[0], "Morvan\n7 coupes rases", (-4.9, 0.55)),
         (5.835, 45.057, "Séchilienne\nglissement\nsous forêt", (-4.6, -2.3))]
fig, ax = plt.subplots(figsize=(W * 0.5, W * 0.52), constrained_layout=True)
world.plot(ax=ax, color="#eeeeee", edgecolor="white", lw=0.8)
fr.plot(ax=ax, color="#f3ead3", edgecolor="#4a4a4a", lw=1.4)
g23.plot(ax=ax, color="#a5d6a7", edgecolor="#2e7d32", lw=1.0, alpha=0.9)
for lon, lat, lab, (dx, dy) in sites:
    ax.plot(lon, lat, "o", ms=17, color="#7b2cbf", mec="white", mew=2.2, zorder=5)
    ax.annotate(lab, (lon, lat), xytext=(lon + dx, lat + dy), fontsize=19, fontweight="bold", color="#5a189a",
                zorder=6, arrowprops=dict(arrowstyle="-", color="#7b2cbf", lw=1.5))
ax.text(0.4, 45.6, "FRANCE", fontsize=26, color="#7a6a3a", fontweight="bold", alpha=0.7, ha="center")
ax.set_xlim(-5.2, 9.8); ax.set_ylim(41.2, 51.3); ax.set_aspect(1 / np.cos(np.radians(46.5)))
ax.set_xticks([]); ax.set_yticks([]); ax.set_xlabel(""); ax.set_ylabel("")
for sp in ax.spines.values():
    sp.set_color("#bbbbbb")
fig.savefig(OUT / "f0_localisation.png", dpi=200); plt.close(fig)

# 1. Vosges ---------------------------------------------------------------------------------------
print("[2/4] Vosges", flush=True)
TAB = ROOT / "vosges" / "results" / "tables"
ch = pd.read_csv(TAB / "comparison_change.csv")
ts = pd.read_csv(TAB / "comparison_timeseries.csv")
post = ts[(ts.kind == "g0") & (ts.phase == "post") & ts.pol.isin(["HV", "VH"])].copy()
post["date"] = pd.to_datetime(post.date)
late = post[post.date >= "2026-10-01"].groupby(["sensor", "geom"]).auc_sep.mean()


def val(sensor, geom, variables):
    x = ch[(ch.sensor == sensor) & (ch.geom == geom) & ch.variable.isin(variables)]
    return x.auc_sep.max() if len(x) else np.nan


SERIES = [("NISAR-L", "A144F26", "L A144 (mont.)", L2, "none"), ("NISAR-L", "A72F26", "L A72 (mont.)", "#a9c8ee", "none"),
          ("NISAR-L", "D138F64", "L D138 (desc.)", L1, "k"), ("S1-C", "T139", "C D139 (desc.)", C, "k")]
IND = ["Cohérence de la paire\nencadrant la coupe", "Variation de γ⁰\ncroisée (HV / VH)", "Persistance :\nAUC oct.–nov."]
fig, ax = plt.subplots(figsize=(W, 4.9), constrained_layout=True)
x = np.arange(len(IND)); w = 0.2
rows = []
for k, (s, g, lab, col, ec) in enumerate(SERIES):
    v = [val(s, g, ["coh_change_HH", "coh_change_VV", "coh_change_VH"]), val(s, g, ["d_gamma0_HV", "d_gamma0_VH"]),
         late.get((s, g), np.nan)]
    rows.append(dict(serie=lab, coherence=v[0], d_gamma0_cross=v[1], persistence=v[2]))
    bars = ax.bar(x + (k - 1.5) * w, v, w, label=lab, color=col, edgecolor=ec, linewidth=2 if ec == "k" else 0)
    for b, y in zip(bars, v, strict=True):
        ax.text(b.get_x() + b.get_width() / 2, y + 0.01, dec(y), ha="center", va="bottom", fontsize=17)
ax.axhline(0.5, color="#999999", ls=":", lw=1.4)
ax.set_xticks(x, IND); ax.set_ylim(0.45, 1.08); ax.set_ylabel("AUC coupe / forêt")
ax.yaxis.set_major_formatter(VIRG)
ax.legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.17), frameon=False, handletextpad=0.3, columnspacing=1.0)
tidy(ax)
fig.savefig(OUT / "f1_vosges.png", dpi=200); plt.close(fig)
pd.DataFrame(rows).round(3).to_csv(OUT / "f1_vosges.csv", index=False)

# 2. Morvan ---------------------------------------------------------------------------------------
print("[3/4] Morvan", flush=True)
sep = pd.read_csv(ROOT / "morvan" / "results" / "tables" / "m6_separability.csv")
LAB = ["Δγ⁰\ncroisée", "Δγ⁰\nco-pol.", "γ⁰ après,\ncroisée", "cohérence\nminimale", "cohérence\naprès"]
fig, axs = plt.subplots(1, 2, figsize=(W, 6.8), sharey=True, constrained_layout=True)
rows = []
for ax, (dname, gl, gc), t in zip(axs, PAIRS, ("a)", "b)"), strict=True):
    x = np.arange(len(INDICATORS))
    for k, (g, col, idx) in enumerate(((gl, L1, 0), (gc, C, 1))):
        vals, lo, hi = [], [], []
        for ind in INDICATORS:
            r = get(sep, g, ind[idx])
            vals.append(np.nan if r is None else r.auc_sep)
            lo.append(np.nan if r is None else r.auc_sep - r.auc_lo)
            hi.append(np.nan if r is None else r.auc_hi - r.auc_sep)
            rows.append(dict(geometry=dname, serie=GEO_LABEL[g], variable=ind[idx], auc=vals[-1],
                             lo=None if r is None else r.auc_lo, hi=None if r is None else r.auc_hi))
        ax.bar(x + (k - 0.5) * 0.38, vals, 0.38, yerr=[lo, hi], capsize=5, color=col,
               error_kw=dict(lw=1.6, ecolor="#333333"), label=("Bande L " if k == 0 else "Bande C ") + GEO_LABEL[g].split()[1])
    ax.axhline(0.5, color="#999999", lw=1.4, ls=":")
    ax.set_xticks(x, LAB, fontsize=17)
    ax.set_ylim(0.4, 1.0); ax.yaxis.set_major_formatter(VIRG)
    ax.set_title(t, loc="left", fontweight="bold")
    ax.legend(loc="upper right", fontsize=17, frameon=False)
    tidy(ax)
axs[0].set_ylabel("AUC coupe / forêt")
fig.savefig(OUT / "f2_morvan.png", dpi=200); plt.close(fig)
pd.DataFrame(rows).round(3).to_csv(OUT / "f2_morvan.csv", index=False)

# 3. Séchilienne ----------------------------------------------------------------------------------
print("[4/4] Séchilienne", flush=True)
p = pd.read_csv(ROOT / "sechilienne" / "results" / "tables" / "g4_pairs.csv")
GEO = [("A173", "L", "L A173\n(mont.)", L2), ("A173", "C", "C A161\n(mont.)", C),
       ("D138", "L", "L D138\n(desc.)", L1), ("D138", "C", "C D139\n(desc.)", "#e8915f")]
fig, axs = plt.subplots(1, 2, figsize=(W, 6.6), sharey=True, constrained_layout=True)
rng = np.random.default_rng(0)
rows = []
for ax, (var, t) in zip(axs, (("coh_versant", "a)"), ("consist_versant", "b)")), strict=True):
    for k, (geom, band, lab, col) in enumerate(GEO):
        v = p[(p.geom == geom) & (p.capteur == band)][var].dropna().values
        ax.scatter(k + rng.uniform(-0.12, 0.12, len(v)), v, s=150, color=col, edgecolor="white", lw=1.2, zorder=3)
        m = np.median(v)
        ax.plot([k - 0.3, k + 0.3], [m, m], color=INK, lw=3.5, zorder=4)
        ax.text(k + 0.33, m, dec(m), va="center", fontsize=18, fontweight="bold")
        rows.append(dict(variable=var, geometry=lab.replace("\n", " "), n=len(v), median=m, min=v.min(), max=v.max()))
    ax.set_xticks(range(len(GEO)), [g[2] for g in GEO], fontsize=18)
    ax.set_xlim(-0.55, len(GEO) - 0.2); ax.set_ylim(0, 1.02); ax.yaxis.set_major_formatter(VIRG)
    ax.set_title(t, loc="left", fontweight="bold")
    tidy(ax)
axs[0].set_ylabel("Valeur par paire")
fig.savefig(OUT / "f3_sechilienne.png", dpi=200); plt.close(fig)
pd.DataFrame(rows).round(3).to_csv(OUT / "f3_sechilienne.csv", index=False)
print(pd.DataFrame(rows).round(2).to_string(index=False))
