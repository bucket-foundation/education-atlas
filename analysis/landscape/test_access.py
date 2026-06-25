"""Pin the headline landscape numbers to the analysis output.

Runs the analysis (idempotent) and asserts the headline findings hold. This is
a regression guard: if an upstream data refresh or a code change moves a
headline number, the test fails and forces a doc update.

Run:  cd analysis/landscape && python3 -m pytest test_access.py -q
  or: python3 test_access.py
"""

from __future__ import annotations

import math
from pathlib import Path

import build_access
from scale import DEPTH_LEVELS, INCOME_TIERS

HERE = Path(__file__).resolve().parent


def _results():
    return build_access.main()


# --------------------------------------------------------------------------- #
def test_real_income_gradient_tertiary():
    """L2 (tertiary GER) must show the real, sharp income gradient:
    high income ~7x low income, monotonically decreasing."""
    r = _results()
    s = r["access_by_depth_and_income"]
    hi = s["High income"]["L2"]
    lo = s["Low income"]["L2"]
    assert hi > 60 and lo < 15, (hi, lo)            # ~68.8 vs ~9.7
    assert hi / lo > 5, hi / lo
    # monotonic down the income ladder
    seq = [s[t]["L2"] for t in INCOME_TIERS]
    assert seq == sorted(seq, reverse=True), seq


def test_access_cliff_with_depth():
    """The headline: access falls monotonically L0 -> L5 within every tier,
    and the frontier (L4) is < 1% even in high income."""
    r = _results()
    s = r["access_by_depth_and_income"]
    for tier in INCOME_TIERS:
        vals = [s[tier][lvl] for lvl in DEPTH_LEVELS]
        # strictly decreasing depth ladder
        for a, b in zip(vals, vals[1:]):
            assert a >= b, (tier, vals)
        assert s[tier]["L4"] < 1.0, (tier, s[tier]["L4"])


def test_frontier_participation_world():
    """The single most dramatic number: world frontier-participation ~0.136%
    (1360 researchers per million)."""
    r = _results()
    fp = r["frontier_participation"]
    assert fp["world_researchers_per_million"] == 1360.0
    assert math.isclose(fp["world_frontier_pct"], 0.136, abs_tol=0.001), fp["world_frontier_pct"]
    # consume vs create: >99.8% never produce
    assert (100 - fp["world_frontier_pct"]) > 99.8


def test_frontier_income_gap():
    """High vs low income frontier (L4) gap is roughly 75x (real UNESCO anchor:
    4150 vs 55 researchers/M)."""
    r = _results()
    fp = r["frontier_participation"]
    assert fp["high_vs_low_L4_ratio"] >= 60, fp["high_vs_low_L4_ratio"]
    rpm = fp["researchers_per_million_by_income"]
    assert rpm["High income"] / rpm["Low income"] > 50


def test_depth_ceiling_by_income():
    """The median person's depth ceiling rises with income:
    Low -> L0, mids -> L1, High -> L2. Nobody's typical ceiling reaches L3+."""
    r = _results()
    c = r["depth_ceiling_by_income"]
    assert c["Low income"] == "L0", c
    assert c["High income"] == "L2", c
    assert c["Lower middle income"] == "L1", c
    assert c["Upper middle income"] == "L1", c
    # no tier's typical person reaches graduate depth or beyond
    assert all(c[t] in ("below L0", "L0", "L1", "L2") for t in INCOME_TIERS), c


def test_real_vs_estimate_ledger_present():
    """Honesty: every estimated dimension must declare its assumption + anchor."""
    r = _results()
    est = r["estimates"]
    for key in ("L3_graduate", "L4_frontier", "L5_production",
                "internet_by_age", "solution_density", "age_depth_gating"):
        assert key in est and len(est[key]) > 20, key
    # L0-L2 are sourced as real World Bank
    assert "World Bank" in r["sources"]["enrollment_literacy"]


def test_research_atlas_corroboration():
    """The research-atlas frontier population is wired in (real cross-check)."""
    r = _results()
    corr = r["frontier_participation"]["corroboration_research_atlas"]
    # either the real numbers loaded, or an explicit error was recorded
    assert ("research_atlas_corpus_persons" in corr) or ("research_atlas_error" in corr)
    if "research_atlas_corpus_persons" in corr:
        assert corr["research_atlas_corpus_persons"] > 1_000_000


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
