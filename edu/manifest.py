"""The atlas manifest -- the authoritative record of what is published.

``data/MANIFEST.json`` lists every published table (parquet path, schema
version, row count, as_of, contributing sources). It is the CANON_INDEX of the
atlas: if a parquet is not in the manifest, treat it as not-published.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from edu import schema
from edu.connectors.base import DATA_PROCESSED, REPO_ROOT
from edu.schema import now_iso

MANIFEST_PATH = REPO_ROOT / "data" / "MANIFEST.json"


def build_manifest(processed_dir: Path | None = None,
                   manifest_path: Path | None = None) -> dict:
    processed_dir = processed_dir or DATA_PROCESSED
    manifest_path = manifest_path or MANIFEST_PATH

    datasets = []
    for table in schema.all_tables():
        path = processed_dir / f"{table}.parquet"
        if not path.exists():
            continue
        df = pd.read_parquet(path)
        sources = sorted(df["source"].dropna().unique().tolist()) \
            if "source" in df.columns else []
        as_of = max(df["as_of"].dropna()) if "as_of" in df.columns and len(df) \
            else None
        datasets.append({
            "table": table,
            "path": str(path.relative_to(REPO_ROOT)),
            "schema_version": schema.SCHEMA_VERSION,
            "row_count": int(len(df)),
            "columns": list(df.columns),
            "sources": sources,
            "as_of": as_of,
        })

    manifest = {
        "name": "education-atlas",
        "description": "A data-grounded map of educational problems by country "
                       "and level, measured against SDG 4 benchmarks.",
        "schema_version": schema.SCHEMA_VERSION,
        "generated_at": now_iso(),
        "license": "MIT (code) / CC-BY-4.0 (data)",
        "publisher": "bucket-foundation",
        "framework": "UN SDG 4 (Quality Education)",
        "datasets": datasets,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    m = build_manifest()
    print(f"manifest: {len(m['datasets'])} datasets")
    for d in m["datasets"]:
        print(f"  {d['table']:14s} {d['row_count']:>9,} rows  {d['sources']}")
