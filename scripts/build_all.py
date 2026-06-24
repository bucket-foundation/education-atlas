#!/usr/bin/env python3
"""End-to-end build: ingest every source -> codebook -> problems -> manifest.

Idempotent + resumable: each connector caches raw under ``data/raw`` and merges
into parquet by primary key, so re-running converges (never duplicates). Sources
that fail (e.g. UNESCO rate-limit) are logged and skipped -- World Bank is the
backbone and must succeed.

Usage:
    python scripts/build_all.py
    python scripts/build_all.py --start 2000 --end 2024
    python scripts/build_all.py --skip unesco oecd_pisa
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edu import schema                                    # noqa: E402
from edu.connectors.base import DATA_PROCESSED            # noqa: E402
from edu.connectors.oecd_pisa import OECDPISAConnector    # noqa: E402
from edu.connectors.owid import OWIDConnector             # noqa: E402
from edu.connectors.unesco import UNESCOConnector         # noqa: E402
from edu.connectors.worldbank import WorldBankConnector   # noqa: E402
from edu.indicators import codebook_rows                  # noqa: E402
from edu.manifest import build_manifest                   # noqa: E402
from edu.problems import build_problems                   # noqa: E402
from edu.schema import Row, now_iso                       # noqa: E402


def emit_supplemental_countries():
    """Countries with education data but absent from the World Bank country list
    (e.g. Taiwan). Kept minimal + provenanced so OWID/PISA rows resolve."""
    import pandas as pd
    from edu.connectors.base import Connector
    rows = [
        Row("country", dict(
            country_code="TWN", iso2="TW", name="Taiwan",
            region="East Asia & Pacific", income_group="High income",
            capital="Taipei", longitude=121.5, latitude=25.0,
            source="atlas", source_id="TWN",
            source_url="https://en.wikipedia.org/wiki/Taiwan", as_of=now_iso())),
        Row("country", dict(
            country_code="REU", iso2="RE", name="Reunion",
            region="Sub-Saharan Africa", income_group="High income",
            capital="Saint-Denis", longitude=55.5, latitude=-21.1,
            source="atlas", source_id="REU",
            source_url="https://en.wikipedia.org/wiki/R%C3%A9union",
            as_of=now_iso())),
    ]

    class _Sup(Connector):
        source = "atlas"
        def fetch(self, **_): return []
        def normalize(self, _): return []
    return _Sup().emit(rows)


def emit_codebook():
    """Write the indicator dimension from the codebook."""
    import pandas as pd
    rows = codebook_rows(now_iso())
    df = pd.DataFrame([schema.coerce("indicator", r) for r in rows])
    df.to_parquet(DATA_PROCESSED / "indicator.parquet", index=False)
    return len(df)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2000)
    ap.add_argument("--end", type=int, default=2024)
    ap.add_argument("--skip", nargs="*", default=[])
    args = ap.parse_args()

    print("=== education-atlas build ===")
    print("[indicator] writing codebook")
    print(f"  indicator: {emit_codebook()} indicators")

    print("[worldbank] ingesting (backbone)")
    wb = WorldBankConnector()
    c = wb.run(start=args.start, end=args.end)
    print(f"  -> {c}")

    print("[country] supplemental countries (Taiwan, Reunion)")
    print(f"  -> {emit_supplemental_countries()}")

    if "owid" not in args.skip:
        print("[owid] ingesting (best-effort)")
        try:
            c = OWIDConnector().run()
            print(f"  -> {c}")
        except Exception as exc:  # noqa: BLE001
            print(f"  owid failed (skipping): {exc}")

    if "unesco" not in args.skip:
        print("[unesco] ingesting (best-effort, SDG4 custodian)")
        try:
            # country list seeds the geoUnit batches
            import pandas as pd
            cc = pd.read_parquet(DATA_PROCESSED / "country.parquet")[
                "country_code"].dropna().tolist()
            c = UNESCOConnector().run(country_codes=cc,
                                      start=args.start, end=args.end)
            print(f"  -> {c}")
        except Exception as exc:  # noqa: BLE001
            print(f"  unesco failed (skipping): {exc}")

    if "oecd_pisa" not in args.skip:
        print("[oecd_pisa] emitting curated PISA 2022 means")
        try:
            c = OECDPISAConnector().run()
            print(f"  -> {c}")
        except Exception as exc:  # noqa: BLE001
            print(f"  oecd_pisa failed (skipping): {exc}")

    print("[problems] scoring problem profiles")
    df = build_problems()
    print(f"  problem: {len(df):,} profiles")

    print("[manifest] rebuilding")
    m = build_manifest()
    for d in m["datasets"]:
        print(f"  {d['table']:12s} {d['row_count']:>9,} rows  {d['sources']}")

    print("=== build complete ===")


if __name__ == "__main__":
    main()
