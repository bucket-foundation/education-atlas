"""Indicator codebook integrity tests."""

from edu import schema
from edu.indicators import (INDICATORS, codebook_rows, worldbank_codes,
                            unesco_codes, pisa_codes)


def test_every_indicator_has_valid_category_and_level():
    for code, m in INDICATORS.items():
        assert m["category"] in schema.CATEGORIES, code
        assert m["level"] in schema.LEVELS, code


def test_every_indicator_has_direction():
    valid = {"higher_better", "lower_better", "target_one"}
    for code, m in INDICATORS.items():
        assert m["direction"] in valid, code


def test_benchmarks_present_or_explicitly_none():
    # benchmark may be None, but the note must always explain why
    for code, m in INDICATORS.items():
        assert m["benchmark_note"], code


def test_codebook_rows_coerce_cleanly():
    for r in codebook_rows("2026-01-01T00:00:00Z"):
        out = schema.coerce("indicator", r)
        assert out["indicator_code"]
        assert out["category"] in schema.CATEGORIES


def test_source_partitions_cover_all_indicators():
    total = set(INDICATORS)
    parts = set(worldbank_codes()) | set(unesco_codes()) | set(pisa_codes())
    owid = {c for c, m in INDICATORS.items() if m["source"] == "owid"}
    assert total == parts | owid


def test_gender_parity_uses_target_one():
    for code in ("SE.ENR.PRIM.FM.ZS", "SE.ENR.SECO.FM.ZS", "SE.ENR.TERT.FM.ZS"):
        assert INDICATORS[code]["direction"] == "target_one"
        assert INDICATORS[code]["benchmark"] == 1.0
