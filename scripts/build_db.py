#!/usr/bin/env python3
"""Build a DuckDB database from the published parquet tables.

The DuckDB file is a rebuildable analysis artifact (gitignored) -- a convenient
single-file query surface over the four published tables, plus two views that
join problems to country/indicator metadata for ad-hoc analysis.

Usage:
    python scripts/build_db.py            # -> education_atlas.duckdb
    python scripts/build_db.py --db /tmp/edu.duckdb
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edu import schema                                # noqa: E402
from edu.connectors.base import DATA_PROCESSED, REPO_ROOT  # noqa: E402


def main():
    import duckdb
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(REPO_ROOT / "education_atlas.duckdb"))
    args = ap.parse_args()

    db = Path(args.db)
    if db.exists():
        db.unlink()
    con = duckdb.connect(str(db))
    for t in schema.all_tables():
        p = DATA_PROCESSED / f"{t}.parquet"
        if p.exists():
            con.execute(f"CREATE TABLE {t} AS SELECT * FROM read_parquet('{p}')")
            n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            print(f"  {t:12s} {n:>9,} rows")

    # convenience views
    con.execute("""
        CREATE VIEW problem_full AS
        SELECT p.*, c.name AS country_name, c.region, c.income_group,
               i.name AS indicator_name, i.direction, i.unit AS indicator_unit
        FROM problem p
        LEFT JOIN country c USING(country_code)
        LEFT JOIN indicator i USING(indicator_code)
    """)
    con.execute("""
        CREATE VIEW observation_full AS
        SELECT o.*, c.name AS country_name, c.region, c.income_group,
               i.name AS indicator_name, i.direction, i.benchmark
        FROM observation o
        LEFT JOIN country c USING(country_code)
        LEFT JOIN indicator i USING(indicator_code)
    """)
    con.close()
    print(f"db -> {db}")


if __name__ == "__main__":
    main()
