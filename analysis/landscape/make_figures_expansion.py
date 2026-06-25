"""Render the five EXPANSION figures from results_expansion.json.

Idempotent: re-running overwrites the PNGs. Runs build_expansion.py first if
results_expansion.json is missing.

Figures (analysis/landscape/figures/):
  (1) fig_cost_surface.png    -- cost-to-access surface over age x depth (USD, log)
  (2) fig_depth_field.png     -- depth x field served-score heatmap (the 3rd axis)
  (3) fig_temporal_trend.png  -- OA% + internet penetration over time + tool arrivals
  (4) fig_continuity_funnel.png -- survival funnel down the depth ladder
  (5) fig_gatekeepers.png     -- cumulative gatekeeper count to each depth
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm

from scale import AGE_BINS, AGE_LABELS, DEPTH_LEVELS, DEPTH_LABELS

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)
RES = HERE / "results_expansion.json"

DEPTH_COLORS = {
    "L0": "#1a9850", "L1": "#66bd63", "L2": "#fee08b",
    "L3": "#fdae61", "L4": "#f46d43", "L5": "#a50026",
}


def load():
    if not RES.exists():
        import build_expansion
        build_expansion.main()
    return json.loads(RES.read_text())


# --------------------------------------------------------------------------- #
def fig_cost_surface(r):
    """(1) Cost-to-access surface over age x depth (USD midpoint, log color).
    Structurally-closed cells hatched grey; a free-path badge on free rungs."""
    surf = r["cost_to_access"]["cost_surface_age_depth_usd_midpoint"]
    free = r["cost_to_access"]["free_path_exists"]
    depths = list(reversed(DEPTH_LEVELS))            # L5 top
    C = np.full((len(depths), len(AGE_BINS)), np.nan)
    for i, lvl in enumerate(depths):
        for j, age in enumerate(AGE_BINS):
            v = surf[lvl][age]
            C[i, j] = v if v is not None else np.nan

    fig, ax = plt.subplots(figsize=(10.5, 6.4))
    Cplot = np.where((~np.isnan(C)) & (C <= 0), 1.0, C)   # 0 -> 1 so log works ($0 floor)
    masked = np.ma.masked_invalid(Cplot)
    im = ax.imshow(masked, aspect="auto", cmap="YlOrRd",
                   norm=LogNorm(vmin=1, vmax=200000), origin="upper")
    for i, lvl in enumerate(depths):
        for j, age in enumerate(AGE_BINS):
            v = C[i, j]
            if np.isnan(v):
                ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1,
                             facecolor="#dddddd", edgecolor="white", hatch="//"))
            else:
                label = "$0" if v <= 0 else (f"${v/1000:.0f}k" if v >= 1000 else f"${v:.0f}")
                ax.text(j, i, label, ha="center", va="center", fontsize=8.5,
                        color="black" if v < 30000 else "white")
        if free[lvl]:
            ax.text(-0.72, i, "free\npath", ha="center", va="center", fontsize=7,
                    color="#1a9850", fontweight="bold")
    ax.set_xticks(range(len(AGE_BINS)))
    ax.set_xticklabels([AGE_LABELS[a] for a in AGE_BINS], fontsize=8)
    ax.set_yticks(range(len(depths)))
    ax.set_yticklabels([DEPTH_LABELS[l] for l in depths], fontsize=8)
    ax.set_xlabel("Life-stage (age)")
    ax.set_title("DIM 1 -- Cost to access each knowledge depth (USD/yr, midpoint, log color)\n"
                 "$0 at literacy; a free-to-READ path exists at the frontier (L4) but NOT a "
                 "free path to PRODUCE (L3/L5)", fontsize=11)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="USD (log)")
    fig.tight_layout()
    fig.savefig(FIG / "fig_cost_surface.png", dpi=140)
    plt.close(fig)


def fig_depth_field(r):
    """(2) The 3rd axis: depth x field served-score heatmap. Rows = fields
    (sorted by size), cols = depth. Shows STEM richly served, humanities thin,
    frontier (L4/L5) thin in EVERY field."""
    df = r["depth_by_field"]
    fields = df["fields"]
    matrix = df["served_score_field_x_depth"]
    order = sorted(fields, key=lambda s: -fields[s]["researchers"])
    M = np.array([[matrix[s][lvl] for lvl in DEPTH_LEVELS] for s in order])

    fig, ax = plt.subplots(figsize=(10.5, 7))
    im = ax.imshow(M, aspect="auto", cmap="viridis", origin="upper", vmin=0, vmax=1)
    for i, s in enumerate(order):
        for j, lvl in enumerate(DEPTH_LEVELS):
            v = M[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7.5,
                    color="white" if v < 0.55 else "black")
    ylabels = []
    for s in order:
        n = fields[s]["researchers"]
        tag = "" if fields[s]["real"] else "*"
        ylabels.append(f"{fields[s]['label']}{tag}  (n={n:,})")
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(ylabels, fontsize=8)
    ax.set_xticks(range(len(DEPTH_LEVELS)))
    ax.set_xticklabels([DEPTH_LABELS[l] for l in DEPTH_LEVELS], rotation=20, ha="right", fontsize=8)
    ax.set_title("DIM 2 -- The 3rd axis: depth x FIELD coverage (served score 0-1)\n"
                 "Field size = REAL researcher counts (research-atlas); * = placeholder "
                 "(corpus is STEM-built). Frontier thins in every field.", fontsize=11)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="served score (0-1)")
    fig.text(0.01, 0.01, "* humanities/arts/law sizes are documented placeholders -- their "
             "near-absence from the STEM-built corpus is the finding.", fontsize=7, color="#555")
    fig.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(FIG / "fig_depth_field.png", dpi=140)
    plt.close(fig)


def fig_temporal_trend(r):
    """(3) Temporal trend: global OA share + internet penetration over time,
    with frontier-tool milestones, plus the (biased) local corpus OA series."""
    t = r["temporal_trend"]
    oa = {int(k): v for k, v in t["global_oa_share_by_year_pct"].items()}
    net = {int(k): v for k, v in t["internet_penetration_by_year_pct"].items()}
    corpus = {int(k): v for k, v in t["corpus_oa_share_by_year_pct"].items() if str(k).isdigit()}
    oa_x = sorted(oa)
    net_x = sorted(net)

    fig, ax = plt.subplots(figsize=(11, 6.4))
    ax.plot(oa_x, [oa[k] for k in oa_x], "-o", color="#2c7fb8", lw=2.6, ms=6,
            label="Global open-access share of new papers (real anchor)")
    ax.plot(net_x, [net[k] for k in net_x], "-s", color="#31a354", lw=2.2, ms=5,
            label="Global internet penetration (World Bank/ITU)")
    if corpus:
        cx = sorted(corpus)
        ax.plot(cx, [corpus[k] for k in cx], "--^", color="#c51b8a", lw=1.6, ms=5, alpha=0.8,
                label="Local research corpus OA% (real but OA-selected -- corroboration)")
    ax.axhline(50, color="#999", ls=":", lw=1)
    ax.text(2001, 51.5, "50% line: OA crossed half of new papers in the early 2020s",
            fontsize=8, color="#555")
    # milestones
    for yr_k, lbl in t["frontier_tool_milestones"].items():
        yr = int(yr_k)
        if yr >= 2000:
            ax.axvline(yr, color="#bbb", ls="-", lw=0.7, alpha=0.7)
            ax.text(yr, 4, lbl, rotation=90, fontsize=6.6, va="bottom", ha="right", color="#777")
    ax.set_xlim(1999, 2025.5)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Year")
    ax.set_ylabel("% share")
    ax.set_title("DIM 3 -- Is frontier access democratizing over time?\n"
                 f"OA share x{t['oa_multiple_2000_2024']} (12->54%) and internet "
                 f"x{t['internet_multiple_2000_2024']} (6.7->68%) since 2000 -- READING the "
                 "frontier is getting easier", fontsize=11)
    ax.legend(loc="center right", fontsize=8.5)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIG / "fig_temporal_trend.png", dpi=140)
    plt.close(fig)


def fig_continuity_funnel(r):
    """(4) Survival funnel down the depth ladder: of 100 entering L0, how many
    remain at each rung. Annotate the biggest drop-off."""
    c = r["continuity_funnel"]
    surv = c["survivors_per_100_at_L0"]
    drops = c["adjacent_dropoff_per_100"]
    biggest = c["biggest_dropoff"]["transition"]
    vals = [surv[l] for l in DEPTH_LEVELS]

    fig, ax = plt.subplots(figsize=(10.5, 6.4))
    y = np.arange(len(DEPTH_LEVELS))[::-1]            # L0 at top
    bars = ax.barh(y, vals, color=[DEPTH_COLORS[l] for l in DEPTH_LEVELS],
                   edgecolor="#333", height=0.62)
    ax.set_xscale("symlog", linthresh=0.05)
    ax.set_xticks([0.05, 0.1, 1, 10, 50, 100])
    ax.set_xticklabels(["0.05", "0.1", "1", "10", "50", "100"])
    ax.set_yticks(y)
    ax.set_yticklabels([DEPTH_LABELS[l] for l in DEPTH_LEVELS], fontsize=8)
    ax.set_xlabel("Survivors per 100 who entered L0 (log scale)")
    for yi, l in zip(y, DEPTH_LEVELS):
        v = surv[l]
        ax.text(v * 1.15, yi, f"{v:.2f}" if v < 10 else f"{v:.0f}", va="center", fontsize=9)
    # annotate drop-offs between rungs
    for k in range(len(DEPTH_LEVELS) - 1):
        a, b = DEPTH_LEVELS[k], DEPTH_LEVELS[k + 1]
        key = f"{a}->{b}"
        ymid = (y[k] + y[k + 1]) / 2
        hot = (key == biggest)
        ax.text(105, ymid, f"-{drops[key]:.1f}" + ("  <- biggest leak" if hot else ""),
                va="center", fontsize=8.5, color="#a50026" if hot else "#777",
                fontweight="bold" if hot else "normal")
    ax.set_title("DIM 4 -- The pipeline leak: survival down the depth ladder\n"
                 f"Of 100 entering L0, ~0.17 reach the frontier. Biggest single leak: "
                 f"{biggest} (-{r['continuity_funnel']['biggest_dropoff']['people_lost_per_100']:.0f}/100)",
                 fontsize=11)
    ax.set_xlim(0, 220)
    ax.grid(True, axis="x", which="both", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIG / "fig_continuity_funnel.png", dpi=140)
    plt.close(fig)


def fig_gatekeepers(r):
    """(5) Cumulative gatekeeper count to reach each depth (stacked by level),
    with the structural-gate count called out at the frontier."""
    g = r["latency_gates"]
    per = g["gates_per_level"]
    cum = g["cumulative_gate_count"]
    vals = [cum[l] for l in DEPTH_LEVELS]

    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    x = np.arange(len(DEPTH_LEVELS))
    bars = ax.bar(x, vals, color=[DEPTH_COLORS[l] for l in DEPTH_LEVELS],
                  edgecolor="#333")
    for xi, l in zip(x, DEPTH_LEVELS):
        ax.text(xi, cum[l] + 0.3, f"{cum[l]} gates", ha="center", fontsize=9, fontweight="bold")
        ax.text(xi, cum[l] / 2, f"+{per[l]}", ha="center", fontsize=8, color="white")
    ax.set_xticks(x)
    ax.set_xticklabels([DEPTH_LABELS[l] for l in DEPTH_LEVELS], rotation=20, ha="right", fontsize=8)
    ax.set_ylabel("Cumulative gates from a standing start")
    ax.set_ylim(0, max(vals) + 3)
    ax.set_title("DIM 5 -- Latency to the frontier: gatekeepers between a learner and each depth\n"
                 f"{g['gates_to_reach_L4']} gates to READ the frontier (L4), {g['gates_to_reach_L5']} "
                 f"to PRODUCE (L5); {g['structural_gates_to_L5']} are structural "
                 "(effort alone can't pass)", fontsize=11)
    ax.annotate("enrollment, tuition, prereqs,\naffiliation, paywalls/APC,\npeer review",
                xy=(5, cum["L5"]), xytext=(3.1, cum["L5"] - 1.5), fontsize=8, color="#a50026",
                arrowprops=dict(arrowstyle="->", color="#a50026"))
    ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(FIG / "fig_gatekeepers.png", dpi=140)
    plt.close(fig)


def main():
    r = load()
    fig_cost_surface(r)
    fig_depth_field(r)
    fig_temporal_trend(r)
    fig_continuity_funnel(r)
    fig_gatekeepers(r)
    new = ["fig_cost_surface.png", "fig_depth_field.png", "fig_temporal_trend.png",
           "fig_continuity_funnel.png", "fig_gatekeepers.png"]
    print("wrote 5 expansion figures to", FIG)
    for p in new:
        print(" -", FIG / p)


if __name__ == "__main__":
    main()
