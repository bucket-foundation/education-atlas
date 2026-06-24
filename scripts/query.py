#!/usr/bin/env python3
"""Ad-hoc query helper over the education-atlas parquet (DuckDB).

Examples:
    python scripts/query.py "SELECT count(*) FROM observation"
    python scripts/query.py --problems NGA        # problem profile for Nigeria
    python scripts/query.py --worst learning 10   # 10 worst countries on learning
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edu.connectors.base import DATA_PROCESSED  # noqa: E402


def _con():
    import duckdb
    con = duckdb.connect()
    for t in ("observation", "country", "indicator", "problem"):
        p = DATA_PROCESSED / f"{t}.parquet"
        if p.exists():
            con.execute(f"CREATE VIEW {t} AS SELECT * FROM read_parquet('{p}')")
    return con


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sql", nargs="?")
    ap.add_argument("--problems", metavar="ISO3")
    ap.add_argument("--worst", nargs=2, metavar=("CATEGORY", "N"))
    args = ap.parse_args()
    con = _con()

    if args.problems:
        sql = f"""SELECT category, level, indicator_code, latest_year,
                 round(latest_value,1) value, round(severity,1) severity, flags
                 FROM problem WHERE country_code='{args.problems}'
                 ORDER BY severity DESC"""
    elif args.worst:
        cat, n = args.worst
        sql = f"""SELECT p.country_code, c.name, round(avg(p.severity),1) sev
                 FROM problem p JOIN country c USING(country_code)
                 WHERE p.category='{cat}' AND c.income_group<>'Aggregate'
                 GROUP BY 1,2 ORDER BY sev DESC LIMIT {int(n)}"""
    elif args.sql:
        sql = args.sql
    else:
        ap.error("provide SQL, --problems ISO3, or --worst CATEGORY N")

    df = con.execute(sql).fetchdf()
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
