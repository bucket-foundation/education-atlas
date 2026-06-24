#!/usr/bin/env python3
"""Data-quality validation suite for the education-atlas.

Runs after a build and ASSERTS the invariants a trustworthy dataset must hold.
Reads ``data/processed/*.parquet`` via DuckDB, runs each check, prints a
pass/fail table, writes ``docs/VALIDATION.md``, and exits non-zero if any HARD
check fails so it can gate CI / a publish step.

Hard checks (failure => non-zero exit):
- provenance present: every observation has non-null source + source_url + as_of;
- referential integrity: every observation.country_code resolves to a country;
- every observation.indicator_code resolves to an indicator (codebook);
- value sanity: percent indicators in [0, 100] (GPI/index/ratio/score/count/years
  allowed their own ranges); no negative counts;
- primary-key uniqueness: one row per obs_id / country_code / indicator_code;
- category/level domain: every observation uses a known category + level.

Soft checks (reported, never fail):
- source coverage; country coverage per indicator; problem-table coverage.

Usage:
    python scripts/validate.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from edu import schema                                # noqa: E402
from edu.connectors.base import DATA_PROCESSED, REPO_ROOT  # noqa: E402
from edu.schema import now_iso                        # noqa: E402

REPORT = REPO_ROOT / "docs" / "VALIDATION.md"


@dataclass
class Result:
    name: str
    hard: bool
    passed: bool
    detail: str = ""


@dataclass
class Suite:
    results: list = field(default_factory=list)

    def check(self, name, hard, passed, detail=""):
        self.results.append(Result(name, hard, bool(passed), detail))

    @property
    def hard_failures(self):
        return [r for r in self.results if r.hard and not r.passed]


def _rp(p, t):
    return f"read_parquet('{p / (t + '.parquet')}')"


def run(processed: Path) -> Suite:
    import duckdb
    s = Suite()
    con = duckdb.connect()
    obs, ctry, ind, prob = (_rp(processed, t) for t in
                            ("observation", "country", "indicator", "problem"))

    def q1(sql):
        return con.execute(sql).fetchone()[0]

    # ---- HARD ---- #
    miss_prov = q1(f"SELECT count(*) FROM {obs} WHERE source IS NULL "
                   f"OR source_url IS NULL OR as_of IS NULL")
    s.check("provenance present on every observation", True, miss_prov == 0,
            f"{miss_prov} rows missing provenance")

    orphan_c = q1(f"SELECT count(*) FROM {obs} o LEFT JOIN {ctry} c "
                  f"USING(country_code) WHERE c.country_code IS NULL")
    s.check("country referential integrity", True, orphan_c == 0,
            f"{orphan_c} observations with unknown country_code")

    orphan_i = q1(f"SELECT count(*) FROM {obs} o LEFT JOIN {ind} i "
                  f"USING(indicator_code) WHERE i.indicator_code IS NULL")
    s.check("indicator referential integrity", True, orphan_i == 0,
            f"{orphan_i} observations with unknown indicator_code")

    # Gross enrollment ratios and completion rates are unbounded above by
    # construction (they count all enrollees -- over-age, repeating, and in
    # micro-states cross-border students -- against the official-age
    # population), so genuine World Bank values can exceed 200%. They are
    # bounded at a sane 300 ceiling. Net rates and shares must stay in
    # [0,100]. No percent may be negative.
    GROSS = ("SE.PRE.ENRR", "SE.TER.ENRR", "SE.PRM.CMPT.ZS",
             "SE.SEC.CMPT.LO.ZS", "SE.SEC.PROG.ZS", "SE.PRM.PRSL.ZS")
    gross_in = "','".join(GROSS)
    bad_pct = q1(
        f"SELECT count(*) FROM {obs} WHERE unit='percent' AND value IS NOT NULL "
        f"AND ( value < 0 "
        f"      OR (indicator_code NOT IN ('{gross_in}') AND value > 100) "
        f"      OR (indicator_code IN ('{gross_in}') AND value > 300) )")
    s.check("percent in [0,100] (gross/completion <=300)", True, bad_pct == 0,
            f"{bad_pct} percent values out of range")

    neg_count = q1(f"SELECT count(*) FROM {obs} WHERE unit='count' "
                   f"AND value IS NOT NULL AND value < 0")
    s.check("counts non-negative", True, neg_count == 0,
            f"{neg_count} negative counts")

    bad_ratio = q1(f"SELECT count(*) FROM {obs} WHERE unit='ratio' "
                   f"AND value IS NOT NULL AND (value <= 0 OR value > 200)")
    s.check("pupil-teacher ratios in (0,200]", True, bad_ratio == 0,
            f"{bad_ratio} implausible ratios")

    dup_obs = q1(f"SELECT count(*) FROM (SELECT obs_id FROM {obs} "
                 f"GROUP BY obs_id HAVING count(*) > 1)")
    s.check("obs_id unique", True, dup_obs == 0, f"{dup_obs} duplicate obs_id")

    dup_c = q1(f"SELECT count(*) FROM (SELECT country_code FROM {ctry} "
               f"GROUP BY country_code HAVING count(*) > 1)")
    s.check("country_code unique", True, dup_c == 0, f"{dup_c} duplicate countries")

    cats = "','".join(schema.CATEGORIES)
    bad_cat = q1(f"SELECT count(*) FROM {obs} WHERE category NOT IN ('{cats}')")
    s.check("category in domain", True, bad_cat == 0, f"{bad_cat} bad categories")

    levs = "','".join(schema.LEVELS)
    bad_lev = q1(f"SELECT count(*) FROM {obs} WHERE level NOT IN ('{levs}')")
    s.check("level in domain", True, bad_lev == 0, f"{bad_lev} bad levels")

    # OWID's mean-years-of-schooling is a long-run series (back to ~1870),
    # which is legitimate; floor at 1820, ceiling at the current year + 1.
    bad_year = q1(f"SELECT count(*) FROM {obs} WHERE year < 1820 OR year > 2030")
    s.check("year plausible (1820-2030)", True, bad_year == 0,
            f"{bad_year} implausible years")

    # ---- SOFT ---- #
    n_src = q1(f"SELECT count(DISTINCT source) FROM {obs}")
    s.check("multiple sources contribute", False, n_src >= 2,
            f"{n_src} distinct sources")

    n_obs = q1(f"SELECT count(*) FROM {obs}")
    n_ctry = q1(f"SELECT count(*) FROM {ctry}")
    n_ind = q1(f"SELECT count(*) FROM {ind}")
    n_prob = q1(f"SELECT count(*) FROM {prob}")
    s.check("dataset non-empty", False, n_obs > 0,
            f"{n_obs:,} obs / {n_ctry} countries / {n_ind} indicators / "
            f"{n_prob:,} problems")

    spar = q1(f"SELECT count(*) FROM (SELECT indicator_code FROM {obs} "
              f"GROUP BY indicator_code HAVING count(DISTINCT country_code) < 30)")
    s.check("indicator country-coverage >= 30 (soft)", False, spar == 0,
            f"{spar} indicators cover <30 countries")

    con.close()
    return s


def write_report(s: Suite, processed: Path):
    lines = ["# education-atlas -- validation report", "",
             f"_Generated {now_iso()}_", "",
             "Invariants asserted on the published parquet. Hard checks gate "
             "publishing; soft checks are advisory coverage signals.", "",
             "| check | type | result | detail |", "|---|---|---|---|"]
    for r in s.results:
        lines.append(f"| {r.name} | {'hard' if r.hard else 'soft'} | "
                     f"{'PASS' if r.passed else 'FAIL'} | {r.detail} |")
    hard = len(s.hard_failures)
    lines += ["", f"**{len([r for r in s.results if r.passed])}/"
              f"{len(s.results)} checks passed; {hard} hard failure(s).**"]
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    s = run(DATA_PROCESSED)
    print(f"\n{'check':52s} {'type':5s} result")
    print("-" * 72)
    for r in s.results:
        print(f"{r.name:52s} {'hard' if r.hard else 'soft':5s} "
              f"{'PASS' if r.passed else 'FAIL':4s}  {r.detail}")
    write_report(s, DATA_PROCESSED)
    hard = len(s.hard_failures)
    print(f"\n{sum(r.passed for r in s.results)}/{len(s.results)} passed; "
          f"{hard} hard failure(s). report -> {REPORT.relative_to(REPO_ROOT)}")
    sys.exit(1 if hard else 0)


if __name__ == "__main__":
    main()
