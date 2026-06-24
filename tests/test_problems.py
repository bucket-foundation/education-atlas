"""Problem-scoring engine tests."""

import pandas as pd

from edu.problems import _benchmark_gap, _severity, build_problems
from edu.indicators import INDICATORS


def test_benchmark_gap_higher_better():
    meta = INDICATORS["SE.PRM.CMPT.ZS"]  # benchmark 100, higher better
    gap, pct = _benchmark_gap(80.0, meta)
    assert gap == 20.0          # 20 points short of universal completion
    assert pct == 20.0


def test_benchmark_gap_lower_better():
    meta = INDICATORS["SE.LPV.PRIM"]  # benchmark 0, lower better
    gap, pct = _benchmark_gap(48.0, meta)
    assert gap == 48.0          # 48 points above the ideal of zero
    assert pct is None          # benchmark 0 -> pct undefined, not div-by-zero


def test_benchmark_gap_gender_parity_either_direction():
    meta = INDICATORS["SE.ENR.SECO.FM.ZS"]  # target 1.0
    gap_low, _ = _benchmark_gap(0.85, meta)   # boys favored
    gap_high, _ = _benchmark_gap(1.15, meta)  # girls favored
    assert round(gap_low, 2) == 0.15 and round(gap_high, 2) == 0.15


def test_severity_monotonic_in_gap():
    meta = INDICATORS["SE.PRM.CMPT.ZS"]
    s_small = _severity(10, 10, None, False, meta)
    s_big = _severity(40, 40, None, False, meta)
    assert s_big > s_small


def test_severity_bounded_0_100():
    meta = INDICATORS["SE.PRM.CMPT.ZS"]
    s = _severity(100, 100, 50, True, meta)
    assert 0 <= s <= 100


def test_no_gap_no_severity():
    meta = INDICATORS["SE.PRM.CMPT.ZS"]
    assert _severity(0, 0, None, False, meta) == 0.0


def test_build_problems_end_to_end(tmp_path):
    proc = tmp_path
    obs = pd.DataFrame([
        # Nigeria learning poverty, two years -> latest 2020, worsening
        dict(obs_id="a", country_code="NGA", indicator_code="SE.LPV.PRIM",
             category="learning", level="primary", year=2018, value=68.0,
             unit="percent", source="worldbank", source_id="x",
             source_url="u", as_of="2026"),
        dict(obs_id="b", country_code="NGA", indicator_code="SE.LPV.PRIM",
             category="learning", level="primary", year=2020, value=72.0,
             unit="percent", source="worldbank", source_id="x",
             source_url="u", as_of="2026"),
        # Finland, low LP (small problem)
        dict(obs_id="c", country_code="FIN", indicator_code="SE.LPV.PRIM",
             category="learning", level="primary", year=2020, value=2.0,
             unit="percent", source="worldbank", source_id="x",
             source_url="u", as_of="2026"),
    ])
    ctry = pd.DataFrame([
        dict(country_code="NGA", iso2="NG", name="Nigeria",
             region="Sub-Saharan Africa", income_group="Lower middle income",
             capital="Abuja", longitude=7.0, latitude=9.0, source="worldbank",
             source_id="NGA", source_url="u", as_of="2026"),
        dict(country_code="FIN", iso2="FI", name="Finland",
             region="Europe & Central Asia", income_group="High income",
             capital="Helsinki", longitude=25.0, latitude=60.0,
             source="worldbank", source_id="FIN", source_url="u", as_of="2026"),
    ])
    obs.to_parquet(proc / "observation.parquet", index=False)
    ctry.to_parquet(proc / "country.parquet", index=False)

    df = build_problems(processed_dir=proc)
    nga = df[df.country_code == "NGA"].iloc[0]
    fin = df[df.country_code == "FIN"].iloc[0]
    assert nga["latest_year"] == 2020 and nga["latest_value"] == 72.0
    assert nga["severity"] > fin["severity"]    # Nigeria worse than Finland
    assert "below_benchmark" in nga["flags"]
    assert "worsening" in nga["flags"]          # LP rose -> adverse trend


def test_build_problems_excludes_aggregates(tmp_path):
    proc = tmp_path
    obs = pd.DataFrame([
        dict(obs_id="a", country_code="SSF", indicator_code="SE.LPV.PRIM",
             category="learning", level="primary", year=2020, value=86.0,
             unit="percent", source="worldbank", source_id="x",
             source_url="u", as_of="2026"),
    ])
    ctry = pd.DataFrame([
        dict(country_code="SSF", iso2="ZG", name="Sub-Saharan Africa",
             region="Aggregates", income_group="Aggregate", capital=None,
             longitude=None, latitude=None, source="worldbank",
             source_id="SSF", source_url="u", as_of="2026"),
    ])
    obs.to_parquet(proc / "observation.parquet", index=False)
    ctry.to_parquet(proc / "country.parquet", index=False)
    df = build_problems(processed_dir=proc)
    assert df.empty  # aggregate excluded from per-country profiles
