"""Canonical schema for education-atlas.

The atlas is a tidy/long **observation** table: one row per
``(country, level, indicator, year)`` measurement, each carrying provenance and
an ``as_of`` timestamp. Alongside it sit small dimension tables (``country``,
``indicator``) and a derived ``problem`` table (the scored problem profile).

Design principles
-----------------
- **One fact per row.** No wide year columns; long form is the source of truth.
  A measurement is ``value`` (numeric), tagged with its ``unit`` and the
  ``category`` (SDG4-aligned problem domain) it informs.
- **Provenance on every row.** ``source`` + ``source_url`` + ``as_of`` make
  every number traceable back to its origin. A value with no provenance is a bug.
- **Deterministic ids.** ``obs_id = hash(source, country_code, indicator_code,
  level, year)`` -- re-ingesting the same record converges (idempotent merge),
  never duplicates.
- **Never silently zero.** Unknown values are ``None``/null, not 0.

The schema is the single contract every connector conforms to. Connectors emit
``Row`` objects; :func:`coerce` validates and fills the canonical column set in
canonical order so emitted parquet is always stable.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

SCHEMA_VERSION = "0.1.0"


# --------------------------------------------------------------------------- #
# Education levels (ISCED-aligned) -- the LEVEL axis. Every observation is
# tagged with exactly one level (``all`` for level-agnostic / system-wide).
# --------------------------------------------------------------------------- #
LEVELS = [
    "pre_primary",      # ISCED 0
    "primary",          # ISCED 1
    "lower_secondary",  # ISCED 2
    "upper_secondary",  # ISCED 3
    "secondary",        # ISCED 2-3 combined (where the source doesn't split)
    "tertiary",         # ISCED 5-8
    "tvet",             # technical & vocational (ISCED-aligned vocational)
    "adult",            # adult / lifelong literacy
    "all",              # system-wide / level-agnostic (e.g. % GDP on education)
]

# --------------------------------------------------------------------------- #
# Problem categories -- the SDG 4 + standard-taxonomy axis. Every indicator is
# mapped to exactly one category so problems aggregate cleanly.
# --------------------------------------------------------------------------- #
CATEGORIES = [
    "access",          # (1) enrollment / out-of-school  -- SDG 4.1, 4.2, 4.3
    "completion",      # (2) completion / dropout         -- SDG 4.1
    "learning",        # (3) learning outcomes / quality  -- SDG 4.1.1 (PISA, LP)
    "equity",          # (4) gender / income / rural-urban / disability -- SDG 4.5
    "financing",       # (5) education spending           -- SDG 4 means of impl.
    "teachers",        # (6) teacher supply & quality     -- SDG 4.c
    "infrastructure",  # (7) electricity/water/internet in schools -- SDG 4.a
    "skills",          # (8) skills mismatch / youth NEET  -- SDG 4.4
    "digital",         # (9) digital divide               -- SDG 4.4 / 4.a
    "literacy",        # adult & youth literacy           -- SDG 4.6
]


# --------------------------------------------------------------------------- #
# Provenance: every observation carries these.
# --------------------------------------------------------------------------- #
PROVENANCE_COLUMNS = [
    "source",      # short source key: "worldbank", "owid", "unesco", "oecd_pisa"
    "source_id",   # the record id in the source's own namespace (indicator code)
    "source_url",  # canonical, citeable URL to the record at the source
    "as_of",       # ISO-8601 UTC timestamp the record was fetched/normalized
]


# --------------------------------------------------------------------------- #
# Tables.
# --------------------------------------------------------------------------- #

# The fact table -- one row per measurement.
OBSERVATION_COLUMNS = [
    "obs_id",          # surrogate key = hash(source, country, indicator, level, year)
    "country_code",    # ISO-3166 alpha-3 (e.g. "IND", "NGA")
    "indicator_code",  # canonical indicator id (e.g. "SE.PRM.UNER")
    "category",        # one of CATEGORIES
    "level",           # one of LEVELS
    "year",            # integer year of the observation
    "value",           # numeric measurement (None if unknown)
    "unit",            # "percent" | "count" | "ratio" | "index" | "score" | "years"
    *PROVENANCE_COLUMNS,
]

# Country dimension.
COUNTRY_COLUMNS = [
    "country_code",    # ISO-3166 alpha-3 (primary key)
    "iso2",            # ISO-3166 alpha-2
    "name",            # display name
    "region",          # World Bank region
    "income_group",    # World Bank income classification
    "capital",
    "longitude",
    "latitude",
    *PROVENANCE_COLUMNS,
]

# Indicator dimension -- the codebook.
INDICATOR_COLUMNS = [
    "indicator_code",  # canonical id (primary key)
    "name",            # human-readable name
    "category",        # one of CATEGORIES
    "level",           # the LEVEL this indicator measures (or "all")
    "unit",
    "direction",       # "higher_better" | "lower_better" -- for problem scoring
    "benchmark",       # the global standard / target value (None if N/A)
    "benchmark_note",  # source/rationale for the benchmark (e.g. "SDG 4 target")
    "description",
    "source",          # which connector populates it
]

# Derived problem table -- the scored problem profile per (country, category, level).
PROBLEM_COLUMNS = [
    "problem_id",      # hash(country, category, level, indicator)
    "country_code",
    "category",
    "level",
    "indicator_code",
    "latest_year",     # year of the latest observation used
    "latest_value",    # the latest value
    "benchmark",       # benchmark compared against
    "gap",             # signed gap vs benchmark (positive = worse than benchmark)
    "gap_pct",         # gap as % of benchmark (where meaningful)
    "peer_median",     # median of income-group peers (latest year)
    "peer_gap",        # signed gap vs peer median
    "trend_slope",     # per-year change over the trend window (None if <2 points)
    "severity",        # 0-100 composite problem severity score
    "flags",           # pipe-joined problem flags (e.g. "below_benchmark|worsening")
    "as_of",
]


ENTITY_TABLES = {
    "observation": OBSERVATION_COLUMNS,
    "country": COUNTRY_COLUMNS,
    "indicator": INDICATOR_COLUMNS,
    "problem": PROBLEM_COLUMNS,
}


def all_tables() -> list[str]:
    return list(ENTITY_TABLES.keys())


# --------------------------------------------------------------------------- #
# Row + helpers.
# --------------------------------------------------------------------------- #

@dataclass
class Row:
    """A single row destined for ``table``. ``data`` keys are a subset of the
    canonical columns for that table."""

    table: str
    data: dict


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_obs_id(source: str, country_code: str, indicator_code: str,
                level: str, year) -> str:
    """Deterministic surrogate key for an observation."""
    raw = f"{source}|{country_code}|{indicator_code}|{level}|{year}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def make_problem_id(country_code: str, category: str, level: str,
                    indicator_code: str) -> str:
    raw = f"{country_code}|{category}|{level}|{indicator_code}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def coerce(table: str, data: dict) -> dict:
    """Validate + fill a row to the canonical column set for ``table``.

    Unknown columns raise (typo guard); missing canonical columns become None.
    """
    if table not in ENTITY_TABLES:
        raise ValueError(f"unknown table: {table!r}")
    cols = ENTITY_TABLES[table]
    extra = set(data) - set(cols)
    if extra:
        raise ValueError(f"row for {table!r} has unknown columns: {sorted(extra)}")
    out = {c: data.get(c) for c in cols}

    # light type/value validation on the fact table
    if table == "observation":
        if out["level"] is not None and out["level"] not in LEVELS:
            raise ValueError(f"invalid level: {out['level']!r}")
        if out["category"] is not None and out["category"] not in CATEGORIES:
            raise ValueError(f"invalid category: {out['category']!r}")
        if out["year"] is not None:
            out["year"] = int(out["year"])
        if out["value"] is not None:
            out["value"] = float(out["value"])
    return out
