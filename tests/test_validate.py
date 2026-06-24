"""Validation-suite tests -- builds a tiny dataset and asserts checks behave."""

import pandas as pd

import scripts.validate as V


def _write(proc, obs, ctry, ind, prob):
    pd.DataFrame(obs).to_parquet(proc / "observation.parquet", index=False)
    pd.DataFrame(ctry).to_parquet(proc / "country.parquet", index=False)
    pd.DataFrame(ind).to_parquet(proc / "indicator.parquet", index=False)
    pd.DataFrame(prob).to_parquet(proc / "problem.parquet", index=False)


def _good_obs(**over):
    base = dict(obs_id="o1", country_code="IND", indicator_code="SE.LPV.PRIM",
                category="learning", level="primary", year=2020, value=47.0,
                unit="percent", source="worldbank", source_id="SE.LPV.PRIM",
                source_url="u", as_of="2026")
    base.update(over)
    return base


def _ctry():
    return [dict(country_code="IND", iso2="IN", name="India",
                 region="South Asia", income_group="Lower middle income",
                 capital="New Delhi", longitude=77.0, latitude=28.0,
                 source="worldbank", source_id="IND", source_url="u",
                 as_of="2026")]


def _ind():
    return [dict(indicator_code="SE.LPV.PRIM", name="Learning poverty",
                 category="learning", level="primary", unit="percent",
                 direction="lower_better", benchmark=0.0,
                 benchmark_note="n", description="d", source="worldbank")]


def _prob():
    return [dict(problem_id="p1", country_code="IND", category="learning",
                 level="primary", indicator_code="SE.LPV.PRIM",
                 latest_year=2020, latest_value=47.0, benchmark=0.0, gap=47.0,
                 gap_pct=None, peer_median=40.0, peer_gap=7.0, trend_slope=0.1,
                 severity=50.0, flags="below_benchmark", as_of="2026")]


def test_clean_dataset_passes_all_hard(tmp_path):
    _write(tmp_path, [_good_obs(), _good_obs(obs_id="o2", source="unesco",
           indicator_code="SCHBSP.1.WELEC", category="infrastructure",
           value=60.0, source_id="SCHBSP.1.WELEC")],
           _ctry(),
           _ind() + [dict(indicator_code="SCHBSP.1.WELEC", name="elec",
                          category="infrastructure", level="primary",
                          unit="percent", direction="higher_better",
                          benchmark=100.0, benchmark_note="n", description="d",
                          source="unesco")],
           _prob())
    s = V.run(tmp_path)
    assert not s.hard_failures


def test_missing_provenance_fails(tmp_path):
    _write(tmp_path, [_good_obs(source=None)], _ctry(), _ind(), _prob())
    s = V.run(tmp_path)
    names = [r.name for r in s.hard_failures]
    assert any("provenance" in n for n in names)


def test_orphan_country_fails(tmp_path):
    _write(tmp_path, [_good_obs(country_code="ZZZ")], _ctry(), _ind(), _prob())
    s = V.run(tmp_path)
    assert any("country referential" in r.name for r in s.hard_failures)


def test_percent_out_of_range_fails(tmp_path):
    # net rate > 100 is impossible
    _write(tmp_path, [_good_obs(value=150.0)], _ctry(), _ind(), _prob())
    s = V.run(tmp_path)
    assert any("percent" in r.name for r in s.hard_failures)


def test_gross_ratio_over_100_allowed(tmp_path):
    ind = _ind() + [dict(indicator_code="SE.PRE.ENRR", name="pre enr",
                         category="access", level="pre_primary", unit="percent",
                         direction="higher_better", benchmark=100.0,
                         benchmark_note="n", description="d", source="worldbank")]
    obs = [_good_obs(obs_id="g", indicator_code="SE.PRE.ENRR", category="access",
                     level="pre_primary", value=145.0, source_id="SE.PRE.ENRR")]
    _write(tmp_path, obs, _ctry(), ind, _prob())
    s = V.run(tmp_path)
    assert not any("percent" in r.name for r in s.hard_failures)


def test_duplicate_obs_id_fails(tmp_path):
    _write(tmp_path, [_good_obs(), _good_obs(value=50.0)], _ctry(), _ind(), _prob())
    s = V.run(tmp_path)
    assert any("obs_id unique" in r.name for r in s.hard_failures)
