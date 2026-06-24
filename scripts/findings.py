#!/usr/bin/env python3
"""Compute the headline findings used by the synthesis report.

Emits a JSON blob of the global education-problem numbers so the report (and the
final summary) cite the same traceable values. Pure DuckDB over the published
parquet -- no invented numbers.

Usage:
    python scripts/findings.py            # pretty-print
    python scripts/findings.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edu.connectors.base import DATA_PROCESSED, REPO_ROOT  # noqa: E402

OUT = REPO_ROOT / "docs" / "findings.json"


def compute():
    import duckdb
    con = duckdb.connect()
    o = f"read_parquet('{DATA_PROCESSED/'observation.parquet'}')"
    c = f"read_parquet('{DATA_PROCESSED/'country.parquet'}')"
    p = f"read_parquet('{DATA_PROCESSED/'problem.parquet'}')"

    def one(sql):
        r = con.execute(sql).fetchone()
        return r[0] if r else None

    def rows(sql):
        return con.execute(sql).fetchall()

    f = {}

    # --- out-of-school (primary + lower-secondary), latest WORLD aggregate --- #
    # World Bank ships the world aggregate under iso3 'WLD'; use it for headline
    # counts (the authoritative global total). Fall back to summing countries.
    # The World Bank EdStats does not publish a WLD aggregate for primary
    # out-of-school (that headline is a UIS modeled estimate). We report the
    # SUM of the latest available country values instead -- honest, traceable,
    # and a known lower bound (countries with no recent data are missing).
    f["oos_primary_world"] = one(f"""
        SELECT sum(value) FROM (
          SELECT o.value, row_number() OVER (PARTITION BY o.country_code
                 ORDER BY o.year DESC) rn
          FROM {o} o JOIN {c} cc USING(country_code)
          WHERE o.indicator_code='SE.PRM.UNER' AND o.value IS NOT NULL
                AND cc.income_group <> 'Aggregate'
        ) WHERE rn=1""")
    f["oos_primary_world_method"] = "sum of latest available country values (lower bound)"
    f["oos_lsec_world"] = one(
        f"SELECT value FROM {o} WHERE country_code='WLD' "
        f"AND indicator_code='UIS.OFST.2' AND value IS NOT NULL "
        f"ORDER BY year DESC LIMIT 1")
    f["oos_lsec_world_year"] = one(
        f"SELECT year FROM {o} WHERE country_code='WLD' "
        f"AND indicator_code='UIS.OFST.2' AND value IS NOT NULL "
        f"ORDER BY year DESC LIMIT 1")

    # --- learning poverty (world) --- #
    f["learning_poverty_world"] = one(
        f"SELECT value FROM {o} WHERE country_code='WLD' "
        f"AND indicator_code='SE.LPV.PRIM' AND value IS NOT NULL "
        f"ORDER BY year DESC LIMIT 1")
    f["learning_poverty_lic"] = one(  # low-income aggregate
        f"SELECT value FROM {o} WHERE country_code='LIC' "
        f"AND indicator_code='SE.LPV.PRIM' AND value IS NOT NULL "
        f"ORDER BY year DESC LIMIT 1")
    f["learning_poverty_ssa"] = one(  # Sub-Saharan Africa aggregate
        f"SELECT value FROM {o} WHERE country_code='SSF' "
        f"AND indicator_code='SE.LPV.PRIM' AND value IS NOT NULL "
        f"ORDER BY year DESC LIMIT 1")

    # --- financing (world) --- #
    f["edu_spend_gdp_world"] = one(
        f"SELECT value FROM {o} WHERE country_code='WLD' "
        f"AND indicator_code='SE.XPD.TOTL.GD.ZS' AND value IS NOT NULL "
        f"ORDER BY year DESC LIMIT 1")
    # countries below the 4% GDP financing floor (latest per country, non-agg)
    f["countries_below_4pct_gdp"] = one(f"""
        SELECT count(*) FROM (
          SELECT o.country_code, o.value,
                 row_number() OVER (PARTITION BY o.country_code
                                    ORDER BY o.year DESC) rn
          FROM {o} o JOIN {c} cc USING(country_code)
          WHERE o.indicator_code='SE.XPD.TOTL.GD.ZS' AND o.value IS NOT NULL
                AND cc.income_group <> 'Aggregate'
        ) WHERE rn=1 AND value < 4.0""")
    f["countries_with_spend_data"] = one(f"""
        SELECT count(DISTINCT o.country_code) FROM {o} o JOIN {c} cc
        USING(country_code) WHERE o.indicator_code='SE.XPD.TOTL.GD.ZS'
        AND o.value IS NOT NULL AND cc.income_group <> 'Aggregate'""")

    # --- adult literacy (world) --- #
    f["adult_literacy_world"] = one(
        f"SELECT value FROM {o} WHERE country_code='WLD' "
        f"AND indicator_code='SE.ADT.LITR.ZS' AND value IS NOT NULL "
        f"ORDER BY year DESC LIMIT 1")

    # --- problem severity by category (mean over countries) --- #
    f["severity_by_category"] = {r[0]: round(r[1], 1) for r in rows(
        f"SELECT category, avg(severity) s FROM {p} "
        f"GROUP BY category ORDER BY s DESC")}

    # --- problem severity by level --- #
    f["severity_by_level"] = {r[0]: round(r[1], 1) for r in rows(
        f"SELECT level, avg(severity) s FROM {p} "
        f"GROUP BY level ORDER BY s DESC")}

    # --- dominant (highest-severity) problem indicator per level --- #
    f["dominant_problem_per_level"] = {}
    for level, ind_code, sev in rows(f"""
        SELECT level, indicator_code, avg(severity) s FROM {p}
        GROUP BY level, indicator_code
        QUALIFY row_number() OVER (PARTITION BY level ORDER BY s DESC)=1
        ORDER BY s DESC"""):
        f["dominant_problem_per_level"][level] = {
            "indicator_code": ind_code, "mean_severity": round(sev, 1)}

    # --- worst countries per category (top mean severity) --- #
    f["worst_countries_per_category"] = {}
    for cat in ["access", "completion", "learning", "equity", "financing",
                "teachers", "literacy", "infrastructure", "digital", "skills"]:
        f["worst_countries_per_category"][cat] = [
            {"country": r[0], "name": r[1], "severity": round(r[2], 1)}
            for r in rows(f"""
                SELECT pr.country_code, cc.name, avg(pr.severity) s
                FROM {p} pr JOIN {c} cc USING(country_code)
                WHERE pr.category='{cat}' AND cc.income_group <> 'Aggregate'
                GROUP BY pr.country_code, cc.name
                ORDER BY s DESC LIMIT 5""")]

    # --- regional learning poverty (latest per WB region aggregate) --- #
    region_aggs = {"SSF": "Sub-Saharan Africa", "SAS": "South Asia",
                   "LCN": "Latin America & Caribbean", "MEA": "Middle East & N. Africa",
                   "EAS": "East Asia & Pacific", "ECS": "Europe & Central Asia"}
    f["learning_poverty_by_region"] = {}
    for code, name in region_aggs.items():
        v = one(f"SELECT value FROM {o} WHERE country_code='{code}' "
                f"AND indicator_code='SE.LPV.PRIM' AND value IS NOT NULL "
                f"ORDER BY year DESC LIMIT 1")
        if v is not None:
            f["learning_poverty_by_region"][name] = round(v, 1)

    # --- gender parity: countries far from GPI=1 at secondary --- #
    f["countries_gender_gap_secondary"] = one(f"""
        SELECT count(*) FROM (
          SELECT o.country_code, o.value,
                 row_number() OVER (PARTITION BY o.country_code
                                    ORDER BY o.year DESC) rn
          FROM {o} o JOIN {c} cc USING(country_code)
          WHERE o.indicator_code='SE.ENR.SECO.FM.ZS' AND o.value IS NOT NULL
                AND cc.income_group <> 'Aggregate'
        ) WHERE rn=1 AND abs(value - 1.0) >= 0.10""")

    # --- coverage / honesty --- #
    f["n_observations"] = one(f"SELECT count(*) FROM {o}")
    f["n_countries"] = one(f"SELECT count(*) FROM {c} WHERE income_group <> 'Aggregate'")
    f["n_indicators"] = one(f"SELECT count(DISTINCT indicator_code) FROM {o}")
    f["year_min"] = one(f"SELECT min(year) FROM {o}")
    f["year_max"] = one(f"SELECT max(year) FROM {o}")
    f["sources"] = [r[0] for r in rows(f"SELECT DISTINCT source FROM {o} ORDER BY 1")]
    # data sparsity: low-income countries with learning-poverty data
    f["lic_with_lp_data"] = one(f"""
        SELECT count(DISTINCT o.country_code) FROM {o} o JOIN {c} cc
        USING(country_code) WHERE o.indicator_code='SE.LPV.PRIM'
        AND cc.income_group='Low income' AND o.value IS NOT NULL""")
    f["n_lic"] = one(f"SELECT count(*) FROM {c} WHERE income_group='Low income'")
    # PISA coverage
    f["pisa_countries"] = one(
        f"SELECT count(DISTINCT country_code) FROM {o} WHERE source='oecd_pisa'")

    con.close()
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    f = compute()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(f, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(f, indent=2))
    else:
        print(f"findings -> {OUT.relative_to(REPO_ROOT)}\n")
        for k, v in f.items():
            print(f"{k}: {json.dumps(v) if isinstance(v,(dict,list)) else v}")


if __name__ == "__main__":
    main()
