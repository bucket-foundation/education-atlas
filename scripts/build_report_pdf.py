#!/usr/bin/env python3
"""Render docs/EDUCATION_PROBLEMS.md to a styled PDF via weasyprint.

Pure-Python markdown -> HTML -> PDF (no headless browser). The PDF is a
gitignored build artifact -- the markdown is the source of truth.

Usage:
    python scripts/build_report_pdf.py
    python scripts/build_report_pdf.py --out /tmp/education-problems.pdf
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edu.connectors.base import REPO_ROOT  # noqa: E402

SRC = REPO_ROOT / "docs" / "EDUCATION_PROBLEMS.md"
OUT = REPO_ROOT / "docs" / "EDUCATION_PROBLEMS.pdf"

CSS = """
@page { size: A4; margin: 2cm 2.2cm; @bottom-center {
  content: "education-atlas v0.1.0  ·  Bucket Foundation  ·  page " counter(page);
  font-size: 8pt; color: #888; } }
body { font-family: 'DejaVu Serif', Georgia, serif; font-size: 10.5pt;
  line-height: 1.5; color: #1a1a1a; }
h1 { font-size: 20pt; color: #0b3d2e; border-bottom: 3px solid #0b3d2e;
  padding-bottom: 6px; }
h2 { font-size: 14pt; color: #0b3d2e; margin-top: 1.4em;
  border-bottom: 1px solid #cdd; padding-bottom: 3px; }
h3 { font-size: 11.5pt; color: #14573f; }
table { border-collapse: collapse; width: 100%; margin: 0.8em 0; font-size: 9.5pt; }
th, td { border: 1px solid #ccc; padding: 4px 8px; text-align: left; }
th { background: #eef3f1; }
strong { color: #0b3d2e; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.5pt;
  background: #f3f5f4; padding: 1px 3px; }
em { color: #555; }
hr { border: none; border-top: 1px solid #ddd; margin: 1.5em 0; }
"""


def md_to_html(md: str) -> str:
    """Minimal but correct markdown subset: headings, tables, lists, bold,
    italic, code, hr. Sufficient for this report (no external dep)."""
    try:
        import markdown  # noqa
        body = markdown.markdown(md, extensions=["tables"])
        return body
    except ImportError:
        pass

    lines = md.split("\n")
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if re.match(r"^\|.*\|$", ln) and i + 1 < len(lines) and \
                re.match(r"^\|[\s:|-]+\|$", lines[i + 1]):
            header = [c.strip() for c in ln.strip("|").split("|")]
            out.append("<table><thead><tr>" +
                       "".join(f"<th>{_inline(h)}</th>" for h in header) +
                       "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and re.match(r"^\|.*\|$", lines[i]):
                cells = [c.strip() for c in lines[i].strip("|").split("|")]
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>"
                                             for c in cells) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue
        if ln.startswith("### "):
            out.append(f"<h3>{_inline(ln[4:])}</h3>")
        elif ln.startswith("## "):
            out.append(f"<h2>{_inline(ln[3:])}</h2>")
        elif ln.startswith("# "):
            out.append(f"<h1>{_inline(ln[2:])}</h1>")
        elif ln.strip() == "---":
            out.append("<hr/>")
        elif ln.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(f"<li>{_inline(lines[i][2:])}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        elif ln.strip() == "":
            out.append("")
        else:
            out.append(f"<p>{_inline(ln)}</p>")
        i += 1
    return "\n".join(out)


def _inline(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", s)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()
    from weasyprint import HTML, CSS as WCSS
    html = f"<html><head><meta charset='utf-8'></head><body>" \
           f"{md_to_html(SRC.read_text(encoding='utf-8'))}</body></html>"
    HTML(string=html).write_pdf(args.out, stylesheets=[WCSS(string=CSS)])
    size = Path(args.out).stat().st_size
    print(f"pdf -> {args.out} ({size//1024} KB)")


if __name__ == "__main__":
    main()
