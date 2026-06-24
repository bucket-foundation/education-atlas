"""Schema contract tests."""

import pytest

from edu import schema
from edu.schema import (coerce, make_obs_id, make_problem_id, Row)


def test_canonical_columns_have_provenance():
    # The fact + dimension tables carry full provenance. The indicator codebook
    # carries a `source` attribution (it is authored, not fetched per-row); the
    # derived problem table carries `as_of`.
    for table in ("observation", "country"):
        for p in ("source", "source_url", "as_of"):
            assert p in schema.ENTITY_TABLES[table], f"{table} missing {p}"
    assert "source" in schema.INDICATOR_COLUMNS
    assert "as_of" in schema.PROBLEM_COLUMNS


def test_coerce_fills_missing_columns_with_none():
    row = coerce("observation", {"country_code": "IND",
                                 "indicator_code": "SE.LPV.PRIM",
                                 "category": "learning", "level": "primary",
                                 "year": 2020, "value": 47.0, "unit": "percent",
                                 "source": "worldbank"})
    assert set(row) == set(schema.OBSERVATION_COLUMNS)
    assert row["source_url"] is None
    assert row["value"] == 47.0


def test_coerce_rejects_unknown_columns():
    with pytest.raises(ValueError):
        coerce("observation", {"bogus": 1})


def test_coerce_rejects_bad_level_and_category():
    with pytest.raises(ValueError):
        coerce("observation", {"level": "kindergarten"})
    with pytest.raises(ValueError):
        coerce("observation", {"category": "happiness"})


def test_coerce_casts_year_and_value():
    row = coerce("observation", {"year": "2019", "value": "12.5",
                                 "level": "all", "category": "financing"})
    assert row["year"] == 2019 and isinstance(row["year"], int)
    assert row["value"] == 12.5 and isinstance(row["value"], float)


def test_obs_id_is_deterministic_and_unique():
    a = make_obs_id("worldbank", "IND", "SE.LPV.PRIM", "primary", 2020)
    b = make_obs_id("worldbank", "IND", "SE.LPV.PRIM", "primary", 2020)
    c = make_obs_id("worldbank", "IND", "SE.LPV.PRIM", "primary", 2021)
    assert a == b and a != c and len(a) == 20


def test_problem_id_deterministic():
    a = make_problem_id("NGA", "learning", "primary", "SE.LPV.PRIM")
    b = make_problem_id("NGA", "learning", "primary", "SE.LPV.PRIM")
    assert a == b


def test_unknown_table_raises():
    with pytest.raises(ValueError):
        coerce("nope", {})
