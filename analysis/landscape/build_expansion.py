"""Expand the knowledge-access map with the five dimensions not in build_access.

Reuses the SAME L0-L5 depth ladder and age bins from scale.py and the SAME
access surface from build_access.py (so the expansion is consistent with the
base map, not a parallel re-derivation). Adds five new evaluable dimensions:

  1. cost_to_access   -- $ to reach each depth level, an age x depth cost surface
  2. depth_by_field   -- the 3rd axis: a depth x discipline coverage matrix
  3. temporal_trend   -- has frontier access risen over time? OA%, internet, tools
  4. continuity       -- the survival/funnel down the depth ladder (of 100 at L0)
  5. latency_gates    -- gatekeeper count between a learner and L4/L5

Idempotent: re-running overwrites results_expansion.json deterministically.

Real anchors (traceable to source):
  - access surface (L0-L5)          : build_access.py (World Bank + UNESCO UIS)
  - field sizes (researchers/field) : research-atlas research_atlas_slim.duckdb
  - corpus OA share by year         : research-atlas work_slim.is_oa (biased; corr.)
  - global OA share by year         : published bibliometrics (cited, anchors)
  - internet penetration by year    : ITU / World Bank IT.NET.USER.ZS (anchors)
  - tuition / APC / subscription $   : cited 2024-2026 figures (anchors)
Estimate flags: every modeled value carries an assumption + the anchor it is
derived from, under results["estimates"].
"""

from __future__ import annotations

import json
from pathlib import Path

import build_access
from scale import AGE_BINS, DEPTH_LEVELS, AGE_DEPTH_OPEN, INCOME_TIERS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESEARCH_DB = ROOT.parent / "research-atlas" / "research_atlas_slim.duckdb"
OUT = HERE / "results_expansion.json"


# --------------------------------------------------------------------------- #
# DIMENSION 1 -- Cost-to-access per depth level (a cost surface over age x depth)
# --------------------------------------------------------------------------- #
# Per-depth cost to *reach and operate at* that level for one person-year, in USD.
# Anchored on real, cited figures (US/OECD-leaning; the cliff is qualitative
# globally). low = the cheapest legitimate path, high = a typical paid path.
#   L0  public primary literacy / free apps / library        -> ~$0
#   L1  public secondary / free OER (Khan, OpenStax)          -> ~$0 public; private K-12 high
#   L2  undergraduate tuition / yr                            -> $0 (free-tuition countries / OCW) .. ~$11k public in-state (US) .. ~$40k private
#   L3  graduate / professional tuition / yr                  -> ~$12k public .. ~$60k professional
#   L4  reading primary research: paywall per article ~$35-50; or APC to publish
#       in an OA venue ~$2k-12.85k (Nature 2026 = $12,850); institutional sub ~$0 if affiliated
#   L5  the cost of *doing* research for a person-year: stipend+bench+overhead,
#       proxied by typical direct cost of one funded researcher-year
COST_PER_DEPTH = {
    #        low_usd   high_usd   note
    "L0": (0,        0,        "Public primary + free apps/library; ~$0 cash cost"),
    "L1": (0,        15000,    "Free OER/public secondary ($0) vs US private K-12 ~$15k/yr"),
    "L2": (0,        40000,    "Free-tuition systems / OCW ($0) vs US private undergrad ~$40k/yr; public in-state ~$11k"),
    "L3": (12000,    60000,    "Public grad ~$12k/yr vs US professional (law/med/MBA) ~$60k/yr"),
    "L4": (35,       12850,    "Per-paywalled-article ~$35-50; OA APC ~$2k avg, Nature 2026 APC = $12,850"),
    "L5": (50000,    150000,   "Cost of doing research: ~one funded researcher-year direct cost (stipend+bench+overhead)"),
}

# A real, single canonical "free vs paid floor" per depth: is the *cheapest
# legitimate* path to this depth free? 1 = a $0 path exists, 0 = no free path.
FREE_PATH_EXISTS = {
    "L0": 1,   # public school, Wikipedia, free apps
    "L1": 1,   # public secondary, OER
    "L2": 1,   # MIT OCW, OpenStax, free-tuition countries -- content free, credential not
    "L3": 0,   # no free graduate credential anywhere at scale
    "L4": 1,   # arXiv/PMC/PLOS/Unpaywall -- a large, growing free-to-READ slice exists
    "L5": 0,   # producing+publishing carries APC and/or research cost; no free path at scale
}


def cost_surface() -> dict:
    """An age x depth cost surface (USD, midpoint of low/high), gated by the
    same AGE_DEPTH_OPEN reachability mask as the access surface."""
    midpoint = {lvl: round((lo + hi) / 2, 0) for lvl, (lo, hi, _) in COST_PER_DEPTH.items()}
    matrix = {}
    for lvl in DEPTH_LEVELS:
        row = {}
        for i, age in enumerate(AGE_BINS):
            row[age] = midpoint[lvl] if AGE_DEPTH_OPEN[lvl][i] else None
        matrix[lvl] = row
    return {
        "cost_per_depth_usd": {lvl: {"low": lo, "high": hi, "midpoint": midpoint[lvl], "note": note}
                               for lvl, (lo, hi, note) in COST_PER_DEPTH.items()},
        "free_path_exists": FREE_PATH_EXISTS,
        "cost_surface_age_depth_usd_midpoint": matrix,
    }


# --------------------------------------------------------------------------- #
# DIMENSION 2 -- The 3rd axis: depth x FIELD coverage matrix
# --------------------------------------------------------------------------- #
# Map research-atlas field_slugs to readable discipline labels. The 9 slugs are
# the real, measured field sizes (researchers per field) in the corpus. We add a
# small set of humanities/under-served fields that are STRUCTURALLY ABSENT from
# the corpus (the corpus is STEM/biomed-built) -- their absence IS the finding,
# so we represent them explicitly with a documented near-zero size.
FIELD_LABELS = {
    "biomed-bio":     "Biomedicine / Biology",
    "earth-climate":  "Earth / Climate",
    "physics-astro":  "Physics / Astronomy",
    "engineering":    "Engineering",
    "cs-ml":          "Computer Science / ML",
    "materials":      "Materials Science",
    "econ-social":    "Economics / Social Sci",
    "chemistry":      "Chemistry",
    "math":           "Mathematics",
}
# Disciplines essentially absent from the (STEM-built) research corpus and thin
# in the solution catalog. Sizes are documented placeholders (corpus ~ 0), used
# to show the breadth gap honestly, NOT a measured count -- flagged as estimated.
ABSENT_FIELDS = {
    "humanities":     ("Humanities (history/philosophy/literature)", 1500),
    "arts":           ("Arts / Performing arts", 500),
    "law-civics":     ("Law / Civics", 1200),
}


def depth_by_field() -> dict:
    """The depth x field matrix. For each field we report:
      - researcher headcount in the corpus (real for the 9 STEM fields)
      - a per-depth 'served' score 0-1: how richly each depth is served in that
        field, derived from field size (real) x a per-depth attenuation that
        encodes the universal frontier-thinness (every field thins at L4/L5).
    The matrix is field (row) x depth (col)."""
    sizes = {}
    real = True
    try:
        import duckdb
        con = duckdb.connect(str(RESEARCH_DB), read_only=True)
        rows = con.execute(
            "SELECT field_slug, SUM(researchers) FROM researcher_segment GROUP BY field_slug"
        ).fetchall()
        con.close()
        for slug, n in rows:
            sizes[slug] = int(n)
    except Exception as e:
        real = False
        sizes = {"_error": str(e)}

    # combine real STEM sizes + documented absent fields
    all_fields = {}
    for slug, label in FIELD_LABELS.items():
        all_fields[slug] = {"label": label, "researchers": sizes.get(slug, 0), "real": True}
    for slug, (label, n) in ABSENT_FIELDS.items():
        all_fields[slug] = {"label": label, "researchers": n, "real": False}

    max_n = max(v["researchers"] for v in all_fields.values()) or 1
    # per-depth attenuation: established knowledge (L0-L3) is broadly served if
    # the field is large; frontier (L4/L5) thins everywhere (the base-map cliff).
    # Multipliers anchored on the world_access_by_depth shape (L4/L5 ~ <<1%).
    DEPTH_ATTEN = {"L0": 1.00, "L1": 1.00, "L2": 0.95, "L3": 0.55, "L4": 0.18, "L5": 0.08}

    matrix = {}
    for slug, info in all_fields.items():
        base = info["researchers"] / max_n            # 0..1 field richness (log-fair below)
        # use sqrt to avoid biomed swamping everything; keeps small fields visible
        base = base ** 0.5
        row = {}
        for lvl in DEPTH_LEVELS:
            row[lvl] = round(base * DEPTH_ATTEN[lvl], 4)
        matrix[slug] = row

    return {
        "fields": all_fields,
        "depth_attenuation": DEPTH_ATTEN,
        "served_score_field_x_depth": matrix,
        "field_sizes_real": real,
        "richest_field": max(FIELD_LABELS, key=lambda s: sizes.get(s, 0)) if real else None,
        "thinnest_real_field": min(FIELD_LABELS, key=lambda s: sizes.get(s, 1e9)) if real else None,
    }


# --------------------------------------------------------------------------- #
# DIMENSION 3 -- Temporal trend: has frontier access risen over time?
# --------------------------------------------------------------------------- #
# Global open-access share of the scholarly literature, by publication year.
# REAL anchors from published bibliometrics (OpenAlex/Unpaywall/Curtin Open
# Knowledge Initiative; the widely-cited result that OA crossed ~50% of new
# articles in the early 2020s). Values are the OA share of articles published
# THAT year. Coarse, documented anchors.
GLOBAL_OA_SHARE_BY_YEAR = {
    2000: 12.0, 2005: 18.0, 2010: 24.0, 2013: 30.0, 2015: 34.0,
    2017: 38.0, 2019: 43.0, 2021: 48.0, 2023: 52.0, 2024: 54.0,
}
# Global internet penetration (% of population using the internet), World Bank /
# ITU IT.NET.USER.ZS. REAL anchors.
INTERNET_PENETRATION_BY_YEAR = {
    2000: 6.7, 2005: 15.7, 2010: 28.7, 2013: 35.5, 2015: 41.1,
    2017: 47.1, 2019: 53.7, 2021: 63.0, 2023: 67.0, 2024: 68.0,
}
# Arrival of frontier-access tooling (year first broadly available) -- the
# "frontier got more reachable" milestones. REAL dates.
FRONTIER_TOOL_MILESTONES = {
    1991: "arXiv launched (free preprints, physics)",
    2004: "Google Scholar",
    2008: "PMC public-access mandate (NIH)",
    2013: "bioRxiv (biology preprints)",
    2015: "Unpaywall / Semantic Scholar era begins",
    2022: "OpenAlex (474M works, CC0) + LLM research tools (Elicit/Consensus scale)",
    2024: "Autonomous science agents (FutureHouse PaperQA2 beats PhDs on lit review)",
}


def temporal_trend() -> dict:
    """Stitch the real series together and add the LOCAL corpus OA-by-year as a
    biased corroboration (the corpus is OA-selected, so it sits high)."""
    corpus_oa = {}
    try:
        import duckdb
        con = duckdb.connect(str(RESEARCH_DB), read_only=True)
        rows = con.execute(
            "SELECT publication_year, ROUND(100.0*AVG(CASE WHEN is_oa THEN 1 ELSE 0 END),1) "
            "FROM work_slim WHERE publication_year BETWEEN 2013 AND 2024 GROUP BY publication_year "
            "ORDER BY publication_year"
        ).fetchall()
        con.close()
        corpus_oa = {int(y): float(v) for y, v in rows}
    except Exception as e:
        corpus_oa = {"_error": str(e)}

    oa_2000 = GLOBAL_OA_SHARE_BY_YEAR[2000]
    oa_2024 = GLOBAL_OA_SHARE_BY_YEAR[2024]
    net_2000 = INTERNET_PENETRATION_BY_YEAR[2000]
    net_2024 = INTERNET_PENETRATION_BY_YEAR[2024]
    return {
        "global_oa_share_by_year_pct": GLOBAL_OA_SHARE_BY_YEAR,
        "internet_penetration_by_year_pct": INTERNET_PENETRATION_BY_YEAR,
        "frontier_tool_milestones": FRONTIER_TOOL_MILESTONES,
        "corpus_oa_share_by_year_pct": corpus_oa,           # biased local corroboration
        "oa_growth_2000_2024": round(oa_2024 - oa_2000, 1),
        "oa_multiple_2000_2024": round(oa_2024 / oa_2000, 1),
        "internet_growth_2000_2024": round(net_2024 - net_2000, 1),
        "internet_multiple_2000_2024": round(net_2024 / net_2000, 1),
    }


# --------------------------------------------------------------------------- #
# DIMENSION 4 -- Continuity / pipeline-leak (the survival funnel)
# --------------------------------------------------------------------------- #
def continuity_funnel(world_access: dict) -> dict:
    """Of 100 people at L0, how many SURVIVE to each deeper rung.

    We treat the world-average access %s as the share of the L0 cohort still
    present at each rung (a cohort survival curve, not conditional transition).
    The biggest drop-off = the largest absolute fall between adjacent rungs.
    All inputs are the base-map world_access (real L0-L2, anchored L3-L5)."""
    base_l0 = world_access["L0"]                      # normalize so L0 cohort = 100
    survivors = {}
    for lvl in DEPTH_LEVELS:
        survivors[lvl] = round(world_access[lvl] / base_l0 * 100, 4)
    # adjacent drop-offs (people lost per 100 of the L0 cohort, between rungs)
    drops = {}
    for a, b in zip(DEPTH_LEVELS, DEPTH_LEVELS[1:]):
        drops[f"{a}->{b}"] = round(survivors[a] - survivors[b], 4)
    biggest = max(drops, key=drops.get)
    # conditional transition rate (share of those AT a rung who reach the next)
    cond = {}
    for a, b in zip(DEPTH_LEVELS, DEPTH_LEVELS[1:]):
        cond[f"{a}->{b}"] = round(world_access[b] / world_access[a] * 100, 2) if world_access[a] else None
    worst_cond = min(cond, key=lambda k: cond[k] if cond[k] is not None else 1e9)
    return {
        "survivors_per_100_at_L0": survivors,
        "adjacent_dropoff_per_100": drops,
        "biggest_dropoff": {"transition": biggest, "people_lost_per_100": drops[biggest]},
        "conditional_transition_pct": cond,
        "worst_conditional_transition": {"transition": worst_cond, "pct_who_advance": cond[worst_cond]},
    }


# --------------------------------------------------------------------------- #
# DIMENSION 5 -- Latency-to-frontier / gatekeeper count
# --------------------------------------------------------------------------- #
# The discrete gates between a motivated learner and each depth level. Each gate
# is a real, named barrier. Count is cumulative (gates passed to REACH the level).
GATES_TO_DEPTH = {
    "L0": ["literacy instruction / a teacher or app"],
    "L1": ["school enrollment", "years of attendance (compulsory schooling)"],
    "L2": ["secondary completion / diploma", "admission (grades/exams)", "tuition or funding"],
    "L3": ["bachelor's degree (prerequisite)", "graduate admission (GRE/portfolio/refs)",
           "graduate tuition or funded slot"],
    "L4": ["graduate-level training (to read primary literature)",
           "institutional affiliation (for subscription access)",
           "paywall / APC (to read or publish closed venues)",
           "domain fluency (jargon, methods, statistics)"],
    "L5": ["a research position / PI or advisor", "funding / grant", "ethics & institutional approval",
           "peer-review acceptance", "publication cost (APC up to $12,850)"],
}


def latency_gates() -> dict:
    """Cumulative gate count to REACH each depth, and the count specifically
    sitting between a non-affiliated learner and L4/L5."""
    cumulative = {}
    running = 0
    per_level = {}
    for lvl in DEPTH_LEVELS:
        per_level[lvl] = len(GATES_TO_DEPTH[lvl])
        running += per_level[lvl]
        cumulative[lvl] = running
    gates_to_l4 = cumulative["L4"]
    gates_to_l5 = cumulative["L5"]
    # gates that are specifically institutional/financial (the ones a motivated
    # outsider can't pass by effort alone)
    structural = ["tuition or funding", "graduate tuition or funded slot",
                  "institutional affiliation (for subscription access)",
                  "paywall / APC (to read or publish closed venues)",
                  "a research position / PI or advisor", "funding / grant",
                  "ethics & institutional approval", "peer-review acceptance",
                  "publication cost (APC up to $12,850)", "graduate admission (GRE/portfolio/refs)",
                  "admission (grades/exams)"]
    all_gates = [g for lvl in DEPTH_LEVELS for g in GATES_TO_DEPTH[lvl]]
    structural_count_to_l5 = sum(1 for g in all_gates if g in structural)
    return {
        "gates_per_level": per_level,
        "gates_to_reach": GATES_TO_DEPTH,
        "cumulative_gate_count": cumulative,
        "gates_to_reach_L4": gates_to_l4,
        "gates_to_reach_L5": gates_to_l5,
        "structural_gates_to_L5": structural_count_to_l5,
        "note": "Cumulative gates from a standing start to each depth. L4/L5 gates "
                "include institutional affiliation and paywalls/APCs that effort alone "
                "cannot pass -- the structural latency to the frontier.",
    }


# --------------------------------------------------------------------------- #
def main() -> dict:
    base = build_access.main()                        # reuse the SAME base surface
    world_access = base["world_access_by_depth"]

    cost = cost_surface()
    field = depth_by_field()
    temporal = temporal_trend()
    continuity = continuity_funnel(world_access)
    latency = latency_gates()

    results = {
        "meta": {
            "title": "Knowledge-access map EXPANSION: cost, field, temporal, continuity, latency",
            "extends": "results.json (same L0-L5 ladder + age bins from scale.py)",
            "axes_are_constructed": True,
            "depth_scale": base["meta"]["depth_scale"],
            "note": "Five new dimensions over the same Age x Knowledge-depth grid. "
                    "Real anchors flagged per dimension; estimates carry assumptions.",
        },
        # 1
        "cost_to_access": cost,
        # 2
        "depth_by_field": field,
        # 3
        "temporal_trend": temporal,
        # 4
        "continuity_funnel": continuity,
        # 5
        "latency_gates": latency,
        # base values reused (for reproducibility / figures)
        "base_world_access_by_depth": world_access,
        # honesty ledger
        "estimates": {
            "cost_to_access": "Per-depth USD low/high are REAL cited 2024-2026 figures "
                              "(US/OECD-leaning): private K-12 ~$15k, US private undergrad ~$40k, "
                              "professional grad ~$60k, per-article paywall ~$35-50, Nature 2026 "
                              "APC = $12,850, researcher-year direct cost ~$50-150k. The age x depth "
                              "MIDPOINT surface is a derived summary (REAL anchors, ESTIMATED midpoint).",
            "depth_by_field": "Field sizes = REAL researcher counts per field from "
                              "research-atlas (researcher_segment). Humanities/arts/law sizes are "
                              "DOCUMENTED PLACEHOLDERS (corpus is STEM-built; their near-absence is "
                              "the finding). served_score = field size (real) ^0.5 x per-depth "
                              "attenuation (ESTIMATED, shaped on the base-map frontier cliff).",
            "temporal_trend": "Global OA share by year and internet penetration by year are REAL "
                              "anchors (published bibliometrics; World Bank/ITU IT.NET.USER.ZS). "
                              "Tool milestones are REAL dates. corpus_oa_share_by_year is the LOCAL "
                              "corpus (REAL but OA-SELECTED, sits high -- corroboration only).",
            "continuity_funnel": "Cohort survival = base-map world_access normalized to the L0 "
                                 "cohort. REAL for L0-L2, anchored for L3-L5. It is a survival/"
                                 "presence curve, NOT a measured longitudinal transition.",
            "latency_gates": "Gate inventory is a STRUCTURED ENUMERATION of real, named barriers "
                             "(enrollment, tuition, prerequisites, affiliation, paywall/APC, peer "
                             "review). Counts are exact for the enumerated list; the list is "
                             "representative, not exhaustive.",
        },
        "sources": {
            "field_sizes": "research-atlas research_atlas_slim.duckdb (researcher_segment).",
            "corpus_oa": "research-atlas research_atlas_slim.duckdb (work_slim.is_oa by year).",
            "global_oa": "Published OA bibliometrics (OpenAlex/Unpaywall/Curtin COKI; OA crossed "
                         "~50% of new articles early 2020s).",
            "internet_penetration": "World Bank / ITU IT.NET.USER.ZS (% individuals using internet).",
            "costs": "Cited 2024-2026 figures: Nature APC ($12,850, STAT 2026), US tuition "
                     "(College Board), per-article paywalls (publisher sites).",
            "base_surface": "build_access.py (World Bank EdStats + UNESCO UIS SP.POP.SCIE.RD.P6).",
        },
    }
    OUT.write_text(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    r = main()
    print(f"wrote {OUT}\n")

    print("DIM 1 cost-to-access (USD low-high per depth):")
    for lvl in DEPTH_LEVELS:
        c = r["cost_to_access"]["cost_per_depth_usd"][lvl]
        free = "FREE path" if r["cost_to_access"]["free_path_exists"][lvl] else "NO free path"
        print(f"  {lvl}: ${c['low']:,}-${c['high']:,}   [{free}]")

    print("\nDIM 2 depth x field -- field sizes (researchers, real for STEM):")
    f = r["depth_by_field"]["fields"]
    for slug, info in sorted(f.items(), key=lambda kv: -kv[1]["researchers"]):
        tag = "real" if info["real"] else "PLACEHOLDER"
        print(f"  {info['label']:<38} {info['researchers']:>8,}  ({tag})")

    print("\nDIM 3 temporal trend:")
    t = r["temporal_trend"]
    print(f"  Global OA share 2000->2024: {t['global_oa_share_by_year_pct'][2000]}% -> "
          f"{t['global_oa_share_by_year_pct'][2024]}%  (x{t['oa_multiple_2000_2024']})")
    print(f"  Internet penetration 2000->2024: {t['internet_penetration_by_year_pct'][2000]}% -> "
          f"{t['internet_penetration_by_year_pct'][2024]}%  (x{t['internet_multiple_2000_2024']})")

    print("\nDIM 4 continuity funnel (survivors per 100 entering L0):")
    s = r["continuity_funnel"]["survivors_per_100_at_L0"]
    for lvl in DEPTH_LEVELS:
        print(f"  {lvl}: {s[lvl]}")
    bd = r["continuity_funnel"]["biggest_dropoff"]
    print(f"  biggest drop-off: {bd['transition']} loses {bd['people_lost_per_100']} per 100")

    print("\nDIM 5 latency / gatekeepers:")
    print(f"  gates to reach L4: {r['latency_gates']['gates_to_reach_L4']}")
    print(f"  gates to reach L5: {r['latency_gates']['gates_to_reach_L5']}")
    print(f"  structural (effort-can't-pass) gates to L5: {r['latency_gates']['structural_gates_to_L5']}")
