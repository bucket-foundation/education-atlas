"""Render the four landscape figures from results.json.

Idempotent: re-running overwrites the PNGs. Requires build_access.py to have
produced results.json first (it is run automatically if missing).

Figures (analysis/landscape/figures/):
  (a) fig_access_vs_age.png   -- knowledge-access vs age, curve per depth level
  (b) fig_income_surface.png  -- access x income tier surface (grouped bars, log)
  (c) fig_coverage_heatmap.png-- age x depth, shaded by access & solution density
  (d) fig_frontier_bar.png    -- consume-vs-create / frontier-participation
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm

from scale import (
    AGE_BINS, AGE_LABELS, DEPTH_LEVELS, DEPTH_LABELS,
    AGE_DEPTH_OPEN, INCOME_TIERS, INCOME_SHORT,
)

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)
RES = HERE / "results.json"

DEPTH_COLORS = {
    "L0": "#1a9850", "L1": "#66bd63", "L2": "#fee08b",
    "L3": "#fdae61", "L4": "#f46d43", "L5": "#a50026",
}


def load():
    if not RES.exists():
        import build_access
        build_access.main()
    return json.loads(RES.read_text())


# --------------------------------------------------------------------------- #
def fig_access_vs_age(r):
    """(a) Access vs age, one line per depth level. World-average access,
    placed at the age band where each depth is first reachable, showing the
    cliff DOWN the depth axis at every life-stage."""
    matrix = r["age_depth_matrix"]
    x = np.arange(len(AGE_BINS))
    fig, ax = plt.subplots(figsize=(10, 6.2))
    for lvl in DEPTH_LEVELS:
        ys = [matrix[lvl][age] for age in AGE_BINS]   # None where structurally closed
        xs = [i for i, y in enumerate(ys) if y is not None]
        yy = [y for y in ys if y is not None]
        ax.plot(xs, yy, "-o", color=DEPTH_COLORS[lvl], lw=2.4, ms=7,
                label=DEPTH_LABELS[lvl])
    ax.set_yscale("symlog", linthresh=0.1)
    ax.set_yticks([0.001, 0.01, 0.1, 1, 10, 50, 100])
    ax.set_yticklabels(["0.001%", "0.01%", "0.1%", "1%", "10%", "50%", "100%"])
    ax.set_ylim(-0.0005, 130)
    ax.set_xticks(x)
    ax.set_xticklabels([AGE_LABELS[a] for a in AGE_BINS], fontsize=9)
    ax.set_xlabel("Life-stage (age)")
    ax.set_ylabel("Share of people who can reach this depth (log scale)")
    ax.set_title("The access cliff: who can reach each knowledge depth, by life-stage\n"
                 "World-average access. Note the log axis — frontier (L4/L5) is "
                 "~1000x below undergrad.", fontsize=12)
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=9,
              title="Knowledge depth")
    ax.annotate("frontier floor\n~0.1% at any age",
                xy=(3, r["world_access_by_depth"]["L4"]),
                xytext=(2.0, 0.004), fontsize=9, color="#a50026",
                arrowprops=dict(arrowstyle="->", color="#a50026"))
    fig.tight_layout()
    fig.savefig(FIG / "fig_access_vs_age.png", dpi=140)
    plt.close(fig)


def fig_income_surface(r):
    """(b) Access x income tier, grouped bars per depth level, log y. The
    equity gradient: HIC vs LIC at every depth."""
    surface = r["access_by_depth_and_income"]
    fig, ax = plt.subplots(figsize=(11, 6.2))
    n_tier = len(INCOME_TIERS)
    x = np.arange(len(DEPTH_LEVELS))
    w = 0.2
    tier_colors = ["#08519c", "#3182bd", "#9ecae1", "#deebf7"]
    for j, tier in enumerate(INCOME_TIERS):
        vals = [max(surface[tier][lvl], 0.001) for lvl in DEPTH_LEVELS]
        ax.bar(x + (j - (n_tier - 1) / 2) * w, vals, w,
               label=INCOME_SHORT[tier], color=tier_colors[j], edgecolor="#333", lw=0.4)
    ax.set_yscale("log")
    ax.set_ylim(0.001, 200)
    ax.set_xticks(x)
    ax.set_xticklabels([DEPTH_LABELS[l] for l in DEPTH_LEVELS], rotation=20,
                       ha="right", fontsize=9)
    ax.set_ylabel("Share of people who reach this depth, % (log scale)")
    ax.set_title("The equity gradient: knowledge access by depth and World Bank income tier\n"
                 "L0-L2 real (World Bank); L3-L5 real anchor x documented multiplier.",
                 fontsize=12)
    ax.grid(True, axis="y", which="both", alpha=0.25)
    ax.legend(title="Income tier", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "fig_income_surface.png", dpi=140)
    plt.close(fig)


def fig_coverage_heatmap(r):
    """(c) Age x depth heatmap. Two panels: access (world-average) and solution
    density. Structurally-closed cells hatched grey; the empty top-right is the
    white space."""
    matrix = r["age_depth_matrix"]
    soln = r["solution_density"]["grid"]
    depths = list(reversed(DEPTH_LEVELS))   # L5 at top

    fig, axes = plt.subplots(1, 2, figsize=(14, 6.4))

    # --- panel 1: access ---
    A = np.full((len(depths), len(AGE_BINS)), np.nan)
    for i, lvl in enumerate(depths):
        for j, age in enumerate(AGE_BINS):
            v = matrix[lvl][age]
            A[i, j] = v if v is not None else np.nan
    ax = axes[0]
    Amask = np.ma.masked_invalid(np.where(A > 0, A, 1e-3))
    im = ax.imshow(Amask, aspect="auto", cmap="YlOrRd_r",
                   norm=LogNorm(vmin=1e-2, vmax=100), origin="upper")
    ax.set_title("(c1) Access — % who reach each cell\n(world-average; grey = structurally N/A)")
    _grid_labels(ax, depths)
    for i in range(len(depths)):
        for j in range(len(AGE_BINS)):
            if np.isnan(A[i, j]):
                ax.add_patch(plt.Rectangle((j - .5, i - .5), 1, 1,
                             facecolor="#dddddd", edgecolor="white", hatch="//"))
            else:
                v = A[i, j]
                txt = f"{v:.0f}%" if v >= 1 else f"{v:.2f}%"
                ax.text(j, i, txt, ha="center", va="center", fontsize=8,
                        color="black")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="% access (log)")

    # --- panel 2: solution density ---
    S = np.zeros((len(depths), len(AGE_BINS)))
    for i, lvl in enumerate(depths):
        for j, age in enumerate(AGE_BINS):
            S[i, j] = soln[lvl][age]
    ax2 = axes[1]
    im2 = ax2.imshow(S, aspect="auto", cmap="Greens", origin="upper")
    est = " (ESTIMATED prior)" if r["solution_density"]["estimated"] else ""
    ax2.set_title(f"(c2) Solution density — # of solutions{est}\nThe empty top-right "
                  "= frontier white space")
    _grid_labels(ax2, depths)
    for i in range(len(depths)):
        for j in range(len(AGE_BINS)):
            ax2.text(j, i, int(S[i, j]), ha="center", va="center", fontsize=8,
                     color="black" if S[i, j] < S.max() * 0.6 else "white")
    fig.colorbar(im2, ax=ax2, fraction=0.046, pad=0.04, label="# solutions")

    fig.suptitle("Coverage / white-space: Age x Knowledge-depth grid", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(FIG / "fig_coverage_heatmap.png", dpi=140)
    plt.close(fig)


def _grid_labels(ax, depths):
    ax.set_xticks(range(len(AGE_BINS)))
    ax.set_xticklabels([AGE_LABELS[a] for a in AGE_BINS], fontsize=8)
    ax.set_yticks(range(len(depths)))
    ax.set_yticklabels([DEPTH_LABELS[l] for l in depths], fontsize=8)
    ax.set_xlabel("Life-stage (age)")


def fig_frontier_bar(r):
    """(d) Consume-vs-create: the tiny frontier-participation slice. Left:
    L4 (reach frontier) vs L5 (produce) by income, log. Right: the single
    dramatic 'who ever produces new knowledge' number vs everyone else."""
    fp = r["frontier_participation"]
    surface = r["access_by_depth_and_income"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5.8),
                                   gridspec_kw={"width_ratios": [1.4, 1]})

    # left: L4 vs L5 by income
    x = np.arange(len(INCOME_TIERS))
    l4 = [surface[t]["L4"] for t in INCOME_TIERS]
    l5 = [surface[t]["L5"] for t in INCOME_TIERS]
    ax1.bar(x - 0.2, l4, 0.4, label="L4 reach frontier (researcher)", color="#f46d43")
    ax1.bar(x + 0.2, l5, 0.4, label="L5 produce new knowledge (publish)", color="#a50026")
    ax1.set_yscale("log")
    ax1.set_xticks(x)
    ax1.set_xticklabels([INCOME_SHORT[t] for t in INCOME_TIERS])
    ax1.set_ylabel("% of population (log scale)")
    ax1.set_title("Frontier participation by income tier\n"
                  f"{fp['high_vs_low_L4_ratio']:.0f}x gap, high vs low income")
    ax1.legend(fontsize=9)
    ax1.grid(True, axis="y", which="both", alpha=0.25)
    for xi, (a, b) in enumerate(zip(l4, l5)):
        ax1.text(xi - 0.2, a, f"{a:.3f}%", ha="center", va="bottom", fontsize=7.5)

    # right: consume vs create, world
    world_pct = fp["world_frontier_pct"]
    ax2.bar(["Consume\n(everyone else)", "Create\n(researchers, world)"],
            [100 - world_pct, world_pct],
            color=["#9ecae1", "#a50026"])
    ax2.set_ylabel("% of world population")
    ax2.set_ylim(0, 100)
    ax2.set_title("Consume vs. create new knowledge (world)")
    ax2.text(1, world_pct + 2, f"{world_pct:.3f}%\n({fp['world_researchers_per_million']:.0f}/M)",
             ha="center", fontsize=11, color="#a50026", fontweight="bold")
    ax2.text(0, 50, f"{100 - world_pct:.2f}%", ha="center", fontsize=12, color="#08519c")

    fig.suptitle("The most dramatic number: ~0.1% of humanity ever produces new knowledge",
                 fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(FIG / "fig_frontier_bar.png", dpi=140)
    plt.close(fig)


def main():
    r = load()
    fig_access_vs_age(r)
    fig_income_surface(r)
    fig_coverage_heatmap(r)
    fig_frontier_bar(r)
    print("wrote 4 figures to", FIG)
    for p in sorted(FIG.glob("*.png")):
        print(" -", p)


if __name__ == "__main__":
    main()
