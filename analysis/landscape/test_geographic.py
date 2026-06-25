"""Pin the headline GEOGRAPHIC + DEMOGRAPHIC numbers to the analysis output.

Runs build_geographic.main() (idempotent; reuses the cached World Bank series)
and asserts the headline findings hold. Regression guard: if a data refresh or a
code change moves a headline number, the test fails and forces a doc update.

Run:  cd analysis/landscape && python3 -m pytest test_geographic.py -q
  or: python3 test_geographic.py
"""

from __future__ import annotations

from pathlib import Path

import build_geographic

HERE = Path(__file__).resolve().parent


def _results():
    return build_geographic.main()


# --------------------------------------------------------------------------- #
def test_coverage_many_countries_have_no_researcher_data():
    """The coverage finding: a large minority of countries have NO researcher
    datapoint at all -- the frontier anchor is simply missing for them."""
    r = _results()
    idx = r["frontier_access_index"]
    assert idx["n_with_anchor"] + idx["n_without_anchor"] == r["meta"]["n_real_countries"]
    # at least ~60 countries with no researcher data (currently 75 of 217 ~ 35%)
    assert idx["n_without_anchor"] >= 60, idx["n_without_anchor"]
    pct = r["headline"]["pct_countries_without_researcher_data"]
    assert 25 <= pct <= 50, pct


def test_frontier_capacity_is_concentrated():
    """Top-10 countries hold the large majority of estimated global researcher
    capacity; top-25 hold the overwhelming majority. China + US lead."""
    r = _results()
    c = r["concentration"]
    assert c["top10_share_pct"] >= 60, c["top10_share_pct"]      # ~69%
    assert c["top25_share_pct"] >= 80, c["top25_share_pct"]      # ~87%
    # monotonic cumulative shares
    assert c["top1_share_pct"] <= c["top5_share_pct"] <= c["top10_share_pct"] <= c["top25_share_pct"]
    # the top-2 are China then the US
    names = [x["name"] for x in c["top10_countries"][:2]]
    assert "China" in names[0], names
    assert "United States" in names[1], names


def test_research_intensity_is_highly_unequal():
    """Gini of researchers/M across countries is high (>0.5); the max/min ratio
    spans orders of magnitude."""
    r = _results()
    c = r["concentration"]
    assert c["gini_researchers_per_million"] > 0.5, c["gini_researchers_per_million"]
    ratio = r["headline"]["max_vs_min_researchers_per_million_ratio"]
    assert ratio > 1000, ratio                                   # thousands-fold span


def test_index_gradient_top_vs_bottom():
    """The composite index spans a brutal gradient: top countries ~90, the
    lowest data-carrying countries ~<30, and the ordering is monotonic."""
    r = _results()
    top = r["ranked_top15"]
    bottom = r["ranked_bottom15"]
    assert top[0]["index"] >= 85, top[0]
    assert bottom[0]["index"] <= 35, bottom[0]
    # top is high income; the deepest-shut-out are low / lower-middle income
    assert top[0]["income_group"] == "High income", top[0]
    assert bottom[0]["income_group"] in ("Low income", "Lower middle income"), bottom[0]


def test_gender_gap_real_and_anchored():
    """Women hold ~1/3 of research posts globally (UNESCO anchor), yet women
    now out-enroll men in tertiary in the real World Bank series -- the leak is
    post-degree. Field segregation: computing is far below parity."""
    r = _results()
    g = r["gender"]
    assert g["women_researchers_pct"]["world"] == 33.3
    # the lowest region is well below the world third
    by_region = {k: v for k, v in g["women_researchers_pct"]["by_region"].items() if k != "World"}
    assert min(by_region.values()) < 20, by_region        # South & West Asia ~18.5
    # real WB: female tertiary GER mean >= male tertiary GER mean (the reversal)
    s = g["tertiary_ger_by_sex_real"]
    assert s["world_female_mean"] >= s["world_male_mean"], s
    # computing is the most male-skewed field in the anchors
    fields = g["women_graduate_share_by_field"]["by_field"]
    assert fields["ICT (computing)"] < 30, fields


def test_idempotent_index_size():
    """Re-running converges: same country count in the index."""
    a = build_geographic.main()
    b = build_geographic.main()
    assert (a["frontier_access_index"]["n_with_anchor"]
            == b["frontier_access_index"]["n_with_anchor"])


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all geographic tests passed")
