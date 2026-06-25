"""Render the geographic + demographic figures from results_geographic.json.

Idempotent: re-running overwrites the PNGs. Runs build_geographic.py first if
results_geographic.json is missing.

Figures (analysis/landscape/figures/):
  (a) fig_geo_choropleth.png   -- world map of the frontier-access index.
        Uses geopandas Natural Earth if available; otherwise degrades to a
        per-country longitude/latitude BUBBLE map (real geography, no geopandas)
        and a regional bar panel -- never fails on a missing dependency.
  (b) fig_geo_country_rank.png -- top-15 vs bottom-15 countries by index, plus
        the "no researcher data at all" tally (the shut-out countries).
  (c) fig_geo_gender.png       -- women researchers by region (UNESCO) +
        female/male tertiary GER by income tier (World Bank) + field gap.
  (d) fig_geo_concentration.png-- top-N cumulative share of frontier capacity +
        the researchers/M Lorenz curve (Gini).
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)
RES = HERE / "results_geographic.json"

# diverging green->red ramp, matching the rest of the landscape figures
def _idx_color(v, vmin=20, vmax=95):
    from matplotlib.colors import Normalize
    norm = Normalize(vmin, vmax)
    return matplotlib.colormaps["RdYlGn"](norm(v))


def load() -> dict:
    if not RES.exists():
        import build_geographic
        build_geographic.main()
    return json.loads(RES.read_text())


# --------------------------------------------------------------------------- #
def fig_choropleth(r: dict):
    """World map shaded by the frontier-access index. geopandas if present,
    else a lon/lat bubble map + regional bar fallback."""
    pc = r["frontier_access_index"]["per_country"]
    no_data = set(r["frontier_access_index"]["without_anchor_iso"])

    try:
        import geopandas as gpd  # noqa
        _choropleth_geopandas(r, pc, no_data)
        return
    except Exception:
        pass
    _choropleth_bubble(r, pc, no_data)


def _choropleth_geopandas(r, pc, no_data):
    import geopandas as gpd
    world = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
    world["idx"] = world["iso_a3"].map(lambda i: pc.get(i, {}).get("index"))
    fig, ax = plt.subplots(figsize=(15, 7.5))
    world.plot(column="idx", cmap="RdYlGn", linewidth=0.3, edgecolor="#666",
               ax=ax, legend=True, missing_kwds={"color": "#dddddd",
               "label": "no researcher data"})
    ax.set_title("Frontier-access index by country (0-100) — green = reaches the "
                 "frontier, grey = no researcher data", fontsize=13)
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(FIG / "fig_geo_choropleth.png", dpi=130)
    plt.close(fig)


def _choropleth_bubble(r, pc, no_data):
    """A real geographic world map without geopandas: country bubbles placed at
    their (lon, lat), sized by absolute frontier capacity, colored by the index.
    A second panel ranks regions (the explicit fallback requested)."""
    import pandas as pd
    ctry = pd.read_parquet(HERE.parents[1] / "data" / "processed" / "country.parquet")
    ctry = ctry[~ctry.income_group.isin(["Aggregate", "Not classified"])]
    lon = dict(zip(ctry.country_code, ctry.longitude))
    lat = dict(zip(ctry.country_code, ctry.latitude))

    cap = {c["iso"]: c["researchers_est"] for c in r["concentration"]["top10_countries"]}

    fig = plt.figure(figsize=(15, 9))
    gs = fig.add_gridspec(2, 1, height_ratios=[2.1, 1.0], hspace=0.28)
    ax = fig.add_subplot(gs[0])

    # faint world frame
    ax.set_xlim(-180, 180); ax.set_ylim(-60, 85)
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#cccccc")
    ax.set_facecolor("#f4f7fa")

    xs_n, ys_n = [], []
    for iso in no_data:
        if iso in lon and lon[iso] is not None and not np.isnan(lon[iso]):
            xs_n.append(lon[iso]); ys_n.append(lat[iso])
    ax.scatter(xs_n, ys_n, s=18, c="#bbbbbb", marker="x", linewidths=1.0,
               label=f"no researcher data ({len(no_data)} countries)", zorder=2)

    xs, ys, cs, sz = [], [], [], []
    for iso, info in pc.items():
        if iso in lon and lon[iso] is not None and not np.isnan(lon[iso]):
            xs.append(lon[iso]); ys.append(lat[iso])
            cs.append(info["index"])
            sz.append(30 + 6 * np.sqrt(max(info["researchers_per_million_raw"], 1)))
    sc = ax.scatter(xs, ys, c=cs, s=sz, cmap="RdYlGn", vmin=20, vmax=95,
                    edgecolors="#333", linewidths=0.4, alpha=0.9, zorder=3)
    cb = fig.colorbar(sc, ax=ax, fraction=0.025, pad=0.01)
    cb.set_label("frontier-access index (0-100)")

    # label the heaviest-capacity countries
    iso_name = {iso: info["name"] for iso, info in pc.items()}
    for iso in list(cap)[:10]:
        if iso in lon and lon[iso] is not None and not np.isnan(lon[iso]):
            ax.annotate(iso_name.get(iso, iso), (lon[iso], lat[iso]),
                        fontsize=7, ha="center", va="bottom",
                        xytext=(0, 5), textcoords="offset points", zorder=4)

    h = r["headline"]
    ax.set_title(f"Who reaches the frontier — {h['n_with_researcher_data']} countries "
                 f"with researcher data, {h['n_without_researcher_data']} with NONE "
                 f"({int(h['pct_countries_without_researcher_data'])}%).  "
                 f"Bubble size ~ researchers/million; grey × = no data.",
                 fontsize=12)
    ax.legend(loc="lower left", fontsize=8, framealpha=0.9)

    # ---- regional bar fallback panel ----
    ax2 = fig.add_subplot(gs[1])
    reg = {k: v for k, v in r["regional"].items() if v["mean_frontier_index"] is not None}
    order = sorted(reg, key=lambda k: reg[k]["mean_frontier_index"])
    vals = [reg[k]["mean_frontier_index"] for k in order]
    cov = [reg[k]["coverage_pct"] for k in order]
    colors = [_idx_color(v) for v in vals]
    y = np.arange(len(order))
    ax2.barh(y, vals, color=colors, edgecolor="#333", linewidth=0.4)
    ax2.set_yticks(y)
    ax2.set_yticklabels([k if len(k) < 30 else k[:27] + "…" for k in order], fontsize=8)
    ax2.set_xlabel("mean frontier-access index (real-data countries only)")
    ax2.set_title("Regional fallback: mean index + researcher-data coverage", fontsize=11)
    for i, (v, c) in enumerate(zip(vals, cov)):
        ax2.text(v + 0.5, i, f"{v:.0f}  ({c:.0f}% covered)", va="center", fontsize=7.5)
    ax2.set_xlim(0, 100)

    fig.suptitle("Geographic concentration of frontier capacity", fontsize=15, y=0.98)
    fig.savefig(FIG / "fig_geo_choropleth.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


# --------------------------------------------------------------------------- #
def fig_country_rank(r: dict):
    top = r["ranked_top15"]
    bottom = r["ranked_bottom15"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 7))

    def _bar(ax, rows, title, reverse=False):
        rows = rows[::-1] if reverse else rows
        names = [f"{x['name']}" for x in rows]
        vals = [x["index"] for x in rows]
        colors = [_idx_color(v) for v in vals]
        y = np.arange(len(rows))
        ax.barh(y, vals, color=colors, edgecolor="#333", linewidth=0.4)
        ax.set_yticks(y); ax.set_yticklabels(names, fontsize=9)
        ax.set_xlim(0, 100); ax.set_xlabel("frontier-access index (0-100)")
        ax.set_title(title, fontsize=12)
        for i, x in enumerate(rows):
            ax.text(x["index"] + 1, i,
                    f"{x['index']:.0f}  ({x['researchers_per_million_raw']:.0f}/M)",
                    va="center", fontsize=7.5)

    _bar(a1, top, "Top 15 — who holds the frontier", reverse=True)
    _bar(a2, bottom, "Bottom 15 with data — the shut-out (have a datapoint)")

    h = r["headline"]
    fig.suptitle(f"The brutal gradient: index {top[0]['index']:.0f} "
                 f"({top[0]['name']}) → {bottom[0]['index']:.0f} ({bottom[0]['name']}). "
                 f"And {h['n_without_researcher_data']} countries have NO researcher "
                 f"datapoint at all — not even on this chart.",
                 fontsize=12.5, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(FIG / "fig_geo_country_rank.png", dpi=130)
    plt.close(fig)


# --------------------------------------------------------------------------- #
def fig_gender(r: dict):
    g = r["gender"]
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(17, 6))

    # (1) women researchers by region
    wr = g["women_researchers_pct"]["by_region"]
    regs = [k for k in wr if k != "World"]
    regs.sort(key=lambda k: wr[k])
    vals = [wr[k] for k in regs]
    colors = ["#c2185b" if v >= 45 else "#7b1fa2" if v >= 33 else "#455a64" for v in vals]
    y = np.arange(len(regs))
    a1.barh(y, vals, color=colors, edgecolor="#333", linewidth=0.4)
    a1.axvline(wr["World"], color="black", ls="--", lw=1.2)
    a1.text(wr["World"] + 0.4, 0.2, f"world {wr['World']}%", fontsize=8, rotation=90, va="bottom")
    a1.axvline(50, color="#888", ls=":", lw=1.0)
    a1.set_yticks(y); a1.set_yticklabels([k.replace(" & ", " &\n") for k in regs], fontsize=8)
    a1.set_xlim(0, 60); a1.set_xlabel("% of researchers who are women")
    a1.set_title("Women in research by region\n(UNESCO UIS — anchors)", fontsize=11)
    for i, v in enumerate(vals):
        a1.text(v + 0.4, i, f"{v}%", va="center", fontsize=7.5)

    # (2) female vs male tertiary GER by income (REAL World Bank)
    bi = g["tertiary_ger_by_sex_real"]["by_income"]
    tiers = [t for t in ["High income", "Upper middle income",
                         "Lower middle income", "Low income"] if t in bi]
    fem = [bi[t]["female_tertiary_ger"] for t in tiers]
    mal = [bi[t]["male_tertiary_ger"] for t in tiers]
    x = np.arange(len(tiers)); w = 0.38
    a2.bar(x - w/2, fem, w, label="female", color="#c2185b", edgecolor="#333", linewidth=0.4)
    a2.bar(x + w/2, mal, w, label="male", color="#1976d2", edgecolor="#333", linewidth=0.4)
    a2.set_xticks(x)
    a2.set_xticklabels([t.replace(" income", "").replace(" middle", "-mid") for t in tiers],
                       rotation=20, fontsize=8)
    a2.set_ylabel("tertiary GER (% gross)")
    a2.set_title("Tertiary enrollment by sex & income\n(World Bank — REAL)", fontsize=11)
    a2.legend(fontsize=8)
    for i, (f, m) in enumerate(zip(fem, mal)):
        a2.text(i - w/2, f + 1, f"{f:.0f}", ha="center", fontsize=7)
        a2.text(i + w/2, m + 1, f"{m:.0f}", ha="center", fontsize=7)

    # (3) women graduate share by field (the horizontal segregation)
    wf = g["women_graduate_share_by_field"]["by_field"]
    fields = sorted(wf, key=lambda k: wf[k])
    fvals = [wf[k] for k in fields]
    fcolors = ["#c2185b" if v >= 50 else "#455a64" for v in fvals]
    yy = np.arange(len(fields))
    a3.barh(yy, fvals, color=fcolors, edgecolor="#333", linewidth=0.4)
    a3.axvline(50, color="#888", ls=":", lw=1.0)
    a3.set_yticks(yy); a3.set_yticklabels(fields, fontsize=8)
    a3.set_xlim(0, 80); a3.set_xlabel("% of graduates who are women")
    a3.set_title("Field segregation: women's graduate share\n(UNESCO — anchors)", fontsize=11)
    for i, v in enumerate(fvals):
        a3.text(v + 0.6, i, f"{v:.0f}%", va="center", fontsize=7.5)

    fig.suptitle("The gender cut: women out-enroll in tertiary, yet hold ~1/3 of "
                 "research posts — and as few as 21% in computing", fontsize=13, y=1.0)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(FIG / "fig_geo_gender.png", dpi=130)
    plt.close(fig)


# --------------------------------------------------------------------------- #
def fig_concentration(r: dict):
    conc = r["concentration"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(15, 6.5))

    # (1) cumulative top-N share
    ns = ["top1", "top5", "top10", "top25"]
    labels = ["Top 1\n(China)", "Top 5", "Top 10", "Top 25"]
    vals = [conc["top1_share_pct"], conc["top5_share_pct"],
            conc["top10_share_pct"], conc["top25_share_pct"]]
    x = np.arange(len(ns))
    bars = a1.bar(x, vals, color=["#a50026", "#d73027", "#f46d43", "#fdae61"],
                  edgecolor="#333", linewidth=0.5)
    a1.set_xticks(x); a1.set_xticklabels(labels, fontsize=9)
    a1.set_ylabel("% of world's estimated researcher capacity")
    a1.set_ylim(0, 100)
    a1.set_title("Frontier capacity is hoarded by a handful of countries", fontsize=12)
    for b, v in zip(bars, vals):
        a1.text(b.get_x() + b.get_width()/2, v + 1.5, f"{v:.0f}%", ha="center", fontsize=10, fontweight="bold")

    # (2) Lorenz curve of researchers/M
    pc = r["frontier_access_index"]["per_country"]
    rpm = sorted(info["researchers_per_million_raw"] for info in pc.values())
    cum = np.cumsum(rpm)
    cum = np.insert(cum, 0, 0) / cum[-1]
    xx = np.linspace(0, 1, len(cum))
    a2.plot([0, 1], [0, 1], "--", color="#888", lw=1.2, label="perfect equality")
    a2.plot(xx, cum, color="#a50026", lw=2.2,
            label=f"actual (Gini = {conc['gini_researchers_per_million']})")
    a2.fill_between(xx, cum, xx, color="#a50026", alpha=0.12)
    a2.set_xlabel("cumulative share of countries (poorest → richest in researchers/M)")
    a2.set_ylabel("cumulative share of researchers/M")
    a2.set_title(f"Inequality of research intensity across {len(rpm)} countries\n"
                 f"max {conc['max_researchers_per_million']:.0f}/M vs "
                 f"min {conc['min_researchers_per_million']:.0f}/M  "
                 f"(median {conc['median_researchers_per_million']:.0f})",
                 fontsize=11)
    a2.legend(fontsize=9, loc="upper left")
    a2.set_xlim(0, 1); a2.set_ylim(0, 1)

    h = r["headline"]
    fig.suptitle(f"Concentration: top-10 countries hold {conc['top10_share_pct']:.0f}% "
                 f"of estimated global researcher capacity; top-25 hold "
                 f"{conc['top25_share_pct']:.0f}%. "
                 f"(research-atlas: all top-25 funded orgs are US/elite.)",
                 fontsize=12, y=1.0)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(FIG / "fig_geo_concentration.png", dpi=130)
    plt.close(fig)


# --------------------------------------------------------------------------- #
def main():
    r = load()
    fig_choropleth(r)
    fig_country_rank(r)
    fig_gender(r)
    fig_concentration(r)
    print("wrote figures:")
    for f in ["fig_geo_choropleth.png", "fig_geo_country_rank.png",
              "fig_geo_gender.png", "fig_geo_concentration.png"]:
        print(f"  {FIG / f}")


if __name__ == "__main__":
    main()
