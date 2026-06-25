"""Pin the EXPANSION headline numbers (cost, field, temporal, continuity, latency).

Regression guard for build_expansion.py: if an upstream data refresh or a code
change moves a headline number, the test fails and forces a doc update. Runs
the analysis idempotently.

Run:  cd analysis/landscape && python3 -m pytest test_expansion.py -q
  or: python3 test_expansion.py
"""

from __future__ import annotations

from pathlib import Path

import build_expansion
from scale import DEPTH_LEVELS

HERE = Path(__file__).resolve().parent


def _results():
    return build_expansion.main()


# --- DIM 1: cost-to-access ---------------------------------------------------- #
def test_cost_free_at_floor_paid_at_frontier():
    """A $0 path exists at L0-L2 and (to READ) at L4, but NOT to PRODUCE (L3/L5)."""
    r = _results()
    free = r["cost_to_access"]["free_path_exists"]
    assert free["L0"] == 1 and free["L1"] == 1 and free["L2"] == 1
    assert free["L4"] == 1                       # free-to-READ (arXiv/PMC/PLOS)
    assert free["L3"] == 0 and free["L5"] == 0   # no free path to produce
    # the Nature 2026 APC anchor is pinned
    assert r["cost_to_access"]["cost_per_depth_usd"]["L4"]["high"] == 12850
    # L5 (doing research) is the most expensive rung
    highs = {l: r["cost_to_access"]["cost_per_depth_usd"][l]["high"] for l in DEPTH_LEVELS}
    assert highs["L5"] == max(highs.values())


# --- DIM 2: depth x field ---------------------------------------------------- #
def test_field_breadth_gap_stem_dominates():
    """Biomedicine is the richest field; mathematics is the thinnest REAL field;
    humanities/arts/law are placeholders (near-absent from the STEM-built corpus)."""
    r = _results()
    df = r["depth_by_field"]
    assert df["field_sizes_real"] is True
    assert df["richest_field"] == "biomed-bio"
    assert df["thinnest_real_field"] == "math"
    f = df["fields"]
    assert f["biomed-bio"]["researchers"] > 500_000          # real, big
    assert f["math"]["researchers"] < 10_000                 # real, small
    # biomed dwarfs math by >100x
    assert f["biomed-bio"]["researchers"] / f["math"]["researchers"] > 100
    # humanities flagged as not-real (placeholder)
    assert f["humanities"]["real"] is False
    # frontier thins in EVERY field: L4 served score < L2 served score everywhere
    for slug, row in df["served_score_field_x_depth"].items():
        assert row["L4"] < row["L2"], slug


# --- DIM 3: temporal trend --------------------------------------------------- #
def test_oa_and_internet_rose():
    """OA share roughly quadrupled and crossed ~50% by the 2020s; internet
    penetration grew ~10x since 2000 -- reading the frontier got easier."""
    r = _results()
    t = r["temporal_trend"]
    assert t["oa_multiple_2000_2024"] >= 4.0
    assert t["global_oa_share_by_year_pct"][2024] >= 50
    assert t["global_oa_share_by_year_pct"][2000] <= 15
    assert t["internet_multiple_2000_2024"] >= 8.0
    # local corpus corroboration is present (real but biased high)
    c = t["corpus_oa_share_by_year_pct"]
    assert ("_error" in c) or (max(v for v in c.values()) > 80)


# --- DIM 4: continuity funnel ------------------------------------------------ #
def test_funnel_monotone_and_biggest_leak():
    """The funnel is monotone non-increasing L0->L5, ~0.17 reach the frontier
    of 100 starting at L0, and the biggest single leak is L2->L3."""
    r = _results()
    c = r["continuity_funnel"]
    surv = [c["survivors_per_100_at_L0"][l] for l in DEPTH_LEVELS]
    assert surv[0] == 100.0
    for a, b in zip(surv, surv[1:]):
        assert a >= b, surv
    assert surv[4] < 1.0                      # <1 of 100 reach L4
    assert 0.1 < surv[4] < 0.3               # ~0.17
    assert c["biggest_dropoff"]["transition"] == "L2->L3"


# --- DIM 5: latency / gatekeepers -------------------------------------------- #
def test_gate_count_grows_with_depth():
    """Cumulative gates grow monotonically; reaching the frontier (L4) takes
    more gates than undergrad, and producing (L5) takes the most."""
    r = _results()
    g = r["latency_gates"]
    cum = [g["cumulative_gate_count"][l] for l in DEPTH_LEVELS]
    for a, b in zip(cum, cum[1:]):
        assert b > a, cum
    assert g["gates_to_reach_L4"] >= 10
    assert g["gates_to_reach_L5"] > g["gates_to_reach_L4"]
    assert g["structural_gates_to_L5"] >= 8     # most frontier gates are structural


# --- honesty ledger present -------------------------------------------------- #
def test_honesty_ledger_and_sources():
    r = _results()
    for key in ("cost_to_access", "depth_by_field", "temporal_trend",
                "continuity_funnel", "latency_gates"):
        assert key in r["estimates"] and len(r["estimates"][key]) > 20, key
    assert "research-atlas" in r["sources"]["field_sizes"]


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
