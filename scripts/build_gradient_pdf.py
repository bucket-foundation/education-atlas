#!/usr/bin/env python3
"""Render docs/THE-KNOWLEDGE-ACCESS-GRADIENT.md to a styled PDF via weasyprint.

Pure-Python markdown -> HTML -> PDF (no headless browser). Embeds the
analysis/landscape figures referenced in the markdown. The PDF is a build
artifact -- the markdown is the source of truth.

Usage:
    python3 scripts/build_gradient_pdf.py
    python3 scripts/build_gradient_pdf.py --out /tmp/gradient.pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "docs" / "THE-KNOWLEDGE-ACCESS-GRADIENT.md"
OUT = REPO_ROOT / "docs" / "THE-KNOWLEDGE-ACCESS-GRADIENT.pdf"

# The full embedded figure set (relative to docs/, the markdown's base_url).
# All are referenced inline in the markdown and resolved via base_url at render
# time; this list is the authoritative manifest and a build-time existence check.
# v1.1 (2026-06-25) added the last four: the historical arc + literacy long-run,
# the geographic concentration map, and the modality reach chart.
FIGURES = [
    "../analysis/landscape/figures/fig_access_vs_age.png",
    "../analysis/landscape/figures/fig_income_surface.png",
    "../analysis/landscape/figures/fig_frontier_bar.png",
    "../analysis/landscape/figures/fig_cost_surface.png",
    "../analysis/landscape/figures/fig_depth_field.png",
    "../analysis/landscape/figures/fig_temporal_trend.png",
    "../analysis/landscape/figures/fig_continuity_funnel.png",
    "../analysis/landscape/figures/fig_gatekeepers.png",
    # v1.1 additions:
    "../analysis/landscape/figures/fig_access_arc.png",        # §1.1 historical spine
    "../analysis/landscape/figures/fig_geo_concentration.png", # §3.6 geographic
    "../analysis/landscape/figures/fig_modality_reach.png",    # §6.2a modality
]

CSS = """
@page { size: A4; margin: 2cm 2.2cm; @bottom-center {
  content: "The Knowledge-Access Gradient  ·  Bucket Foundation  ·  page " counter(page);
  font-size: 8pt; color: #888; } }
body { font-family: 'DejaVu Serif', Georgia, serif; font-size: 10.5pt;
  line-height: 1.5; color: #1a1a1a; }
h1 { font-size: 21pt; color: #0b3d2e; border-bottom: 3px solid #0b3d2e;
  padding-bottom: 6px; }
h2 { font-size: 14pt; color: #0b3d2e; margin-top: 1.4em;
  border-bottom: 1px solid #cdd; padding-bottom: 3px; }
h3 { font-size: 11.5pt; color: #14573f; }
table { border-collapse: collapse; width: 100%; margin: 0.8em 0; font-size: 9.2pt; }
th, td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; }
th { background: #eef3f1; }
strong { color: #0b3d2e; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.5pt;
  background: #f3f5f4; padding: 1px 3px; }
em { color: #555; }
hr { border: none; border-top: 1px solid #ddd; margin: 1.5em 0; }
img { max-width: 100%; max-height: 9.5cm; display: block; margin: 0.6em auto;
  border: 1px solid #e3e3e3; }
p { text-align: justify; }
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    import markdown  # tables + images via core
    from weasyprint import HTML, CSS as WCSS

    # Existence check on the embedded figure manifest (resolved vs docs/).
    missing = [f for f in FIGURES if not (SRC.parent / f).resolve().exists()]
    if missing:
        sys.exit(f"missing figures: {missing}")

    md = SRC.read_text(encoding="utf-8")
    body = markdown.markdown(md, extensions=["tables", "sane_lists"])
    html = (
        "<html><head><meta charset='utf-8'></head><body>"
        f"{body}</body></html>"
    )
    # base_url = docs/ so the ../analysis/... image paths resolve on disk
    HTML(string=html, base_url=str(SRC.parent)).write_pdf(
        args.out, stylesheets=[WCSS(string=CSS)]
    )
    size = Path(args.out).stat().st_size
    print(f"pdf -> {args.out} ({size//1024} KB)")


if __name__ == "__main__":
    main()
