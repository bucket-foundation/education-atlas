"""Render the MODALITY-dimension figure for doc 07-modality.md.

The MODALITY axis is orthogonal to the depth ladder (scale.py): it asks, for
each *channel* through which knowledge is acquired, (a) how far up the L0-L5
depth ladder it can realistically carry a motivated learner, and (b) how large
its reach is. The single figure maps each modality as a bubble on a
reach (x, log) x depth-ceiling (y) plane, colored by whether it can reach
PRODUCTION (L5).

Idempotent: re-running overwrites the PNG. No network, no GPU. stdlib + the
matplotlib/numpy already used by the sibling make_figures_*.py scripts.

The numbers encoded here (reach headcounts, depth ceilings) are the real cited
anchors from doc 07; the depth-ceiling y-values are this project's constructed
L0-L5 ladder (scale.py), so they are an analytical mapping, flagged as such in
the figure footnote and the doc.

Figure (analysis/landscape/figures/):
  fig_modality_reach.png  -- modality reach (x) vs depth-ceiling (y), bubble =
                             relative cost/credential, color = reaches L5?
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)

# --------------------------------------------------------------------------- #
# Modality table. Each row:
#   name, reach (people who can plausibly USE the channel, order-of-magnitude),
#   depth_floor, depth_ceiling (on the L0-L5 ladder; fractional = "edge of"),
#   reaches_L5 (bool), note
# reach values are cited order-of-magnitude anchors (see doc 07); the depth
# range is the constructed L0-L5 ladder. Both are documented in the doc.
MODALITIES = [
    # name,                 reach,        floor, ceil, reachesL5, label_dy
    ("Informal / open\n(MOOC, YouTube,\nWikipedia, OER)", 3.0e9, 0.0, 3.0, False, -0.42),
    ("Self-directed /\nautodidact\n(books, open web)",    6.0e8, 0.0, 4.5, False, 0.20),
    ("Formal\n(school -> university\n-> grad school)",     1.4e9, 1.0, 5.0, True,  0.20),
    ("Apprenticeship /\nmentorship\n(advisor, the lab)",   3.2e5, 3.0, 5.0, True,  0.20),
    ("AI-mediated\n(tutors, research\nagents)",            1.5e9, 0.0, 4.5, False, -0.55),
]


def fig_modality_reach():
    fig, ax = plt.subplots(figsize=(12.5, 7.2))

    for name, reach, floor, ceil, l5, dy in MODALITIES:
        color = "#a50026" if l5 else "#2c7fb8"
        # vertical "carry range" bar from floor to ceiling
        ax.plot([reach, reach], [floor, ceil], color=color, lw=2.4, alpha=0.45,
                zorder=1, solid_capstyle="round")
        # ceiling marker (the load-bearing point: how high it carries you)
        ax.scatter([reach], [ceil], s=360, color=color, edgecolor="#222",
                   linewidth=1.2, zorder=3,
                   marker="^" if l5 else "o")
        # floor marker
        ax.scatter([reach], [floor], s=70, color=color, alpha=0.6, zorder=2)
        ax.annotate(name, xy=(reach, ceil), xytext=(reach, ceil + dy),
                    ha="center", fontsize=8.6, fontweight="bold", color="#222",
                    va="bottom" if dy > 0 else "top")

    # the L4 "frontier read" line and the L5 "production" line
    ax.axhline(4.0, color="#888", ls="--", lw=1.0, alpha=0.8)
    ax.text(1.3e9, 4.04, "L4  the frontier  (read primary research)  -- "
            "only ~0.14% of humanity is here", fontsize=8, color="#555")
    ax.axhline(5.0, color="#a50026", ls="--", lw=1.0, alpha=0.6)
    ax.text(1.3e9, 5.04, "L5  PRODUCTION  (add to the frontier)  -- "
            "the gated ceiling; ~0.06% of humanity", fontsize=8, color="#a50026")

    # the "scalability cliff": shade the high-reach region
    ax.axvspan(2e7, 1e10, color="#2c7fb8", alpha=0.04, zorder=0)
    ax.text(2.2e9, 0.15, "high-reach\n(scalable) modalities", fontsize=8,
            color="#2c7fb8", ha="center", style="italic")
    ax.text(3.2e5, 0.15, "the modality that reaches\nL5 (apprenticeship)\n"
            "does NOT scale", fontsize=8, color="#a50026", ha="center",
            style="italic")

    ax.set_xscale("log")
    ax.set_xlim(5e4, 1e10)
    ax.set_ylim(-0.3, 5.7)
    ax.set_yticks(range(6))
    ax.set_yticklabels([
        "L0 literacy", "L1 secondary", "L2 undergrad", "L3 grad/prof",
        "L4 frontier (read)", "L5 PRODUCE",
    ], fontsize=8.5)
    ax.set_xlabel("REACH -- people who can plausibly use the channel "
                  "(log scale, order-of-magnitude cited anchors)")
    ax.set_ylabel("DEPTH CEILING on the L0-L5 ladder")
    ax.set_title("MODALITY x DEPTH-REACH: the channels that scale ceiling out before "
                 "production;\nthe channel that reaches production does not scale  "
                 "(triangle = reaches L5; circle = stalls below it)", fontsize=11.5)
    ax.grid(True, alpha=0.22)

    # legend proxies
    from matplotlib.lines import Line2D
    handles = [
        Line2D([0], [0], marker="^", color="w", markerfacecolor="#a50026",
               markeredgecolor="#222", markersize=13,
               label="Reaches L5 / production"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#2c7fb8",
               markeredgecolor="#222", markersize=12,
               label="Ceilings out below production"),
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=9, framealpha=0.95)

    fig.text(0.01, 0.005,
             "Reach = order-of-magnitude cited anchors (Coursera 168M regd / "
             "~220M MOOC enrollments, YouTube ~2.5B users w/ ~51% learning, ~1.4B "
             "in formal education, ~320k active publishing researchers via the "
             "advisor pipeline). Depth ceiling = this project's constructed L0-L5 "
             "ladder (scale.py); the self-directed/AI ceilings are drawn to the "
             "L4-L5 EDGE to encode 'possible in principle, rare in practice'. "
             "Interpretive mapping -- see doc 07 for the per-cell citations.",
             fontsize=6.6, color="#666")
    fig.tight_layout(rect=[0, 0.03, 1, 1])
    out = FIG / "fig_modality_reach.png"
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def main():
    out = fig_modality_reach()
    print("wrote modality figure to", out)


if __name__ == "__main__":
    main()
