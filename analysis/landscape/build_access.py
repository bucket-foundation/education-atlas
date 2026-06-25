"""Quantify knowledge access on the Age x Knowledge-depth grid.

Reads the published education-atlas dataset (data/processed/*.parquet) plus the
research-atlas slim DB for the frontier-participation population, computes the
five evaluable dimensions, and writes results.json. Idempotent: re-running
overwrites results.json deterministically from the same inputs.

Real anchors (traceable to source):
  - enrollment / literacy by income group : World Bank EdStats (education-atlas)
  - researchers in the corpus             : research-atlas slim DB
  - researchers per million (frontier)    : UNESCO UIS SP.POP.SCIE.RD.P6 (documented)
  - internet access by age (channel)      : ITU 2023 (documented)

Estimate flags: every modeled value carries an assumption + the anchor it is
derived from, recorded under results["estimates"].
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd

from scale import (
    AGE_BINS, DEPTH_LEVELS, AGE_DEPTH_OPEN, INCOME_TIERS,
)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                       # education-atlas/
EDU_DATA = ROOT / "data" / "processed"
RESEARCH_DB = ROOT.parent / "research-atlas" / "research_atlas_slim.duckdb"
OUT = HERE / "results.json"

INCOME_KEEP = set(INCOME_TIERS)


# --------------------------------------------------------------------------- #
# Real-data loaders
# --------------------------------------------------------------------------- #
def _latest_by_income(obs: pd.DataFrame, inc: pd.DataFrame, code: str) -> dict:
    """Mean of the latest-available country value within each income group."""
    d = obs[obs.indicator_code == code].sort_values("year").groupby("country_code").tail(1)
    m = d.merge(inc, on="country_code")
    m = m[m.income_group.isin(INCOME_KEEP)]
    return {g: round(float(v), 1) for g, v in m.groupby("income_group")["value"].mean().items()}


def load_income_surface() -> dict:
    """Dimension 2: access x income tier, from real World Bank indicators.

    Maps each measured indicator to a depth level. L0/L1/L2 are fully real;
    L3/L4/L5 layer documented multipliers/anchors on top of the real series.
    """
    obs = pd.read_parquet(EDU_DATA / "observation.parquet")
    ctry = pd.read_parquet(EDU_DATA / "country.parquet")
    inc = ctry[["country_code", "income_group"]]

    real = {
        "L0_adult_literacy":   _latest_by_income(obs, inc, "SE.ADT.LITR.ZS"),
        "L1_secondary_ner":    _latest_by_income(obs, inc, "SE.SEC.NENR"),
        "L2_tertiary_ger":     _latest_by_income(obs, inc, "SE.TER.ENRR"),
        "learning_poverty":    _latest_by_income(obs, inc, "SE.LPV.PRIM"),
        "pre_primary_ger":     _latest_by_income(obs, inc, "SE.PRE.ENRR"),
        "primary_ner":         _latest_by_income(obs, inc, "SE.PRM.NENR"),
    }
    return real


def load_frontier_population() -> dict:
    """Dimension 4: the frontier-participation rate (L4/L5).

    Real corroboration from research-atlas; canonical rate from UNESCO UIS.
    """
    out = {}
    try:
        import duckdb
        con = duckdb.connect(str(RESEARCH_DB), read_only=True)
        total = con.execute("SELECT SUM(researchers) FROM researcher_segment").fetchone()[0]
        active = con.execute(
            "SELECT SUM(researchers) FROM researcher_segment WHERE activity_tier='active'"
        ).fetchone()[0]
        persons = con.execute("SELECT persons FROM stats").fetchone()[0]
        con.close()
        out["research_atlas_corpus_persons"] = int(persons)
        out["research_atlas_segment_total"] = int(total)
        out["research_atlas_segment_active"] = int(active)
    except Exception as e:  # research-atlas optional
        out["research_atlas_error"] = str(e)
    return out


# --------------------------------------------------------------------------- #
# Documented anchors (NOT in the local cache; cited values, flagged as anchors)
# --------------------------------------------------------------------------- #
# UNESCO UIS "Researchers (FTE) per million inhabitants" (SP.POP.SCIE.RD.P6),
# latest available group means. World mean ~1,360/M. These are the canonical
# frontier-participation anchors. Source: UNESCO Institute for Statistics /
# World Bank SP.POP.SCIE.RD.P6 (latest ~2021-2023).
RESEARCHERS_PER_MILLION = {
    "High income":          4150.0,   # OECD-heavy; e.g. Israel/Korea >8000, EU ~4000
    "Upper middle income":  1150.0,   # China ~1585 pulls this up
    "Lower middle income":   270.0,   # India ~260
    "Low income":             55.0,   # SSA averages double-digits
    "World":                1360.0,
}

# Internet-using share by life-stage (the digital ACCESS CHANNEL to depth),
# global. Source: ITU "Measuring digital development: Facts and Figures 2023".
# Youth (15-24) ~75% globally; gap widens for 65+; under-5 not direct users.
INTERNET_BY_AGE = {
    "0-5":   0.0,    # not direct users; access mediated by caregiver
    "5-18":  60.0,   # school-age, global avg (huge HIC/LIC spread)
    "18-22": 75.0,   # youth band, ITU global youth online share
    "22-65": 65.0,   # working-age global online share
    "65+":   40.0,   # oldest band, largest age digital divide
}

# Share of tertiary-enrolled who go on to graduate/professional level (L3),
# and share of population that ever publishes (L5). Modeled multipliers on the
# real tertiary series. Anchors: OECD EAG (master's+ entry ~ a quarter of a
# tertiary cohort in rich systems, far less elsewhere); L5 ~ researchers/M.
GRAD_SHARE_OF_TERTIARY = {     # L3 = tertiary_GER * this
    "High income":         0.30,
    "Upper middle income": 0.18,
    "Lower middle income": 0.10,
    "Low income":          0.06,
}


# --------------------------------------------------------------------------- #
# Derived surfaces
# --------------------------------------------------------------------------- #
def depth_access_by_income(real: dict) -> dict:
    """Dimension 1+2 backbone: % of people who can REACH each depth level,
    by income tier. L0-L2 real; L3 real*est; L4/L5 from researchers/M (real
    UNESCO anchor) expressed as a % of population."""
    out = {}
    for tier in INCOME_TIERS:
        rpm = RESEARCHERS_PER_MILLION[tier]
        l4 = round(rpm / 1_000_000 * 100, 4)          # researchers per million -> %
        l5 = round(l4 * 0.45, 4)                       # ~45% of researchers actively publish
        out[tier] = {
            "L0": real["L0_adult_literacy"].get(tier),
            "L1": real["L1_secondary_ner"].get(tier),
            "L2": real["L2_tertiary_ger"].get(tier),
            "L3": round(real["L2_tertiary_ger"].get(tier) * GRAD_SHARE_OF_TERTIARY[tier], 1),
            "L4": l4,
            "L5": l5,
        }
    return out


def depth_ceiling_by_income(surface: dict) -> dict:
    """Dimension 5: the median depth level a TYPICAL person in each tier reaches.
    'Reaches' = >=50% of that tier attains it (for L0-L3); L4/L5 are sub-1%
    everywhere so they are never the median ceiling. Returns the highest depth
    whose access >= 50%."""
    out = {}
    for tier, row in surface.items():
        ceiling = "below L0"
        for lvl in ["L0", "L1", "L2", "L3"]:
            v = row[lvl]
            if v is not None and v >= 50.0:
                ceiling = lvl
        out[tier] = ceiling
    return out


def age_depth_surface(surface: dict) -> dict:
    """Dimension 1 (+coverage): an age x depth access matrix, world-average.
    World-average access per depth = population-weighted-ish simple mean across
    tiers (documented as unweighted mean for transparency). Gated by
    AGE_DEPTH_OPEN so structurally-impossible cells are null."""
    # world-average access per depth level (unweighted mean of the 4 tiers)
    world = {}
    for lvl in DEPTH_LEVELS:
        vals = [surface[t][lvl] for t in INCOME_TIERS if surface[t][lvl] is not None]
        world[lvl] = round(sum(vals) / len(vals), 4)
    # build matrix [depth][age]
    matrix = {}
    for lvl in DEPTH_LEVELS:
        row = {}
        for i, age in enumerate(AGE_BINS):
            open_ = AGE_DEPTH_OPEN[lvl][i]
            row[age] = world[lvl] if open_ else None
        matrix[lvl] = row
    return {"world_access_by_depth": world, "age_depth_matrix": matrix}


def solution_density() -> dict:
    """Dimension 3: solution-density layer for the white-space heatmap.

    A sibling solution-landscape CSV (data/landscape/solutions.csv) is the
    intended source. If absent, we synthesize a documented density prior that
    encodes the known shape of the EdTech/education market: dense at K-12 and
    consumer-undergrad, sparse at the frontier. Counts are illustrative density
    weights (0=none, higher=more solutions), NOT a measured census -- flagged.
    """
    csv = ROOT / "data" / "landscape" / "solutions.csv"
    if csv.exists():
        df = pd.read_csv(csv)
        # expect columns: age_bin, depth_level (or aggregate to it)
        grid = {lvl: {age: 0 for age in AGE_BINS} for lvl in DEPTH_LEVELS}
        for _, r in df.iterrows():
            a, d = str(r.get("age_bin")), str(r.get("depth_level"))
            if a in AGE_BINS and d in DEPTH_LEVELS:
                grid[d][a] += 1
        return {"source": "data/landscape/solutions.csv", "estimated": False, "grid": grid}

    # documented prior (estimated)
    prior = {
        #          0-5  5-18 18-22 22-65 65+
        "L0":     [12,  20,  4,    8,    2],
        "L1":     [0,   38,  6,    6,    1],
        "L2":     [0,   2,   30,   14,   1],
        "L3":     [0,   0,   3,    9,    0],
        "L4":     [0,   0,   1,    2,    0],
        "L5":     [0,   0,   0,    1,    0],
    }
    grid = {lvl: {AGE_BINS[i]: prior[lvl][i] for i in range(len(AGE_BINS))}
            for lvl in DEPTH_LEVELS}
    return {"source": "documented prior (no solutions.csv present)",
            "estimated": True, "grid": grid}


# --------------------------------------------------------------------------- #
def main() -> dict:
    real = load_income_surface()
    frontier_pop = load_frontier_population()
    surface = depth_access_by_income(real)
    ceiling = depth_ceiling_by_income(surface)
    age_depth = age_depth_surface(surface)
    soln = solution_density()

    # headline frontier-participation numbers
    world_rpm = RESEARCHERS_PER_MILLION["World"]
    frontier_pct_world = round(world_rpm / 1_000_000 * 100, 4)   # ~0.136%
    hi_l4 = surface["High income"]["L4"]
    low_l4 = surface["Low income"]["L4"]

    results = {
        "meta": {
            "title": "Knowledge access on the Age x Knowledge-depth grid",
            "generated_from": "education-atlas data/processed + research-atlas slim DB",
            "depth_scale": {lvl: None for lvl in DEPTH_LEVELS},
            "axes_are_constructed": True,
            "note": "Depth ladder L0-L5 and age bins are a constructed analytical "
                    "frame defined in scale.py; access proxies are real data.",
        },
        # ---- Dimension 1 & coverage ----
        "world_access_by_depth": age_depth["world_access_by_depth"],
        "age_depth_matrix": age_depth["age_depth_matrix"],
        # ---- Dimension 2 ----
        "access_by_depth_and_income": surface,
        "real_income_indicators": real,
        # ---- Dimension 3 ----
        "solution_density": soln,
        # ---- Dimension 4 ----
        "frontier_participation": {
            "world_researchers_per_million": world_rpm,
            "world_frontier_pct": frontier_pct_world,
            "researchers_per_million_by_income": RESEARCHERS_PER_MILLION,
            "L4_pct_by_income": {t: surface[t]["L4"] for t in INCOME_TIERS},
            "L5_pct_by_income": {t: surface[t]["L5"] for t in INCOME_TIERS},
            "high_vs_low_L4_ratio": round(hi_l4 / low_l4, 1) if low_l4 else None,
            "corroboration_research_atlas": frontier_pop,
        },
        # ---- Dimension 5 ----
        "depth_ceiling_by_income": ceiling,
        # ---- access channel ----
        "internet_by_age": INTERNET_BY_AGE,
        # ---- honesty ledger ----
        "estimates": {
            "L3_graduate": "tertiary GER * GRAD_SHARE_OF_TERTIARY; anchor OECD EAG "
                           "graduate-entry shares (~0.30 HIC -> 0.06 LIC). REAL base "
                           "(tertiary GER) x ESTIMATED multiplier.",
            "L4_frontier": "UNESCO UIS researchers-per-million (SP.POP.SCIE.RD.P6) / "
                           "1e6 * 100. REAL anchor (group means documented in code); "
                           "expressed as % of population.",
            "L5_production": "L4 * 0.45 (share of researchers actively publishing). "
                             "ESTIMATED multiplier on the REAL L4 anchor.",
            "internet_by_age": "ITU Facts & Figures 2023 global online shares by age "
                               "band. REAL anchor, coarse global bins.",
            "solution_density": soln["source"] +
                                ("  ESTIMATED density prior." if soln["estimated"]
                                 else "  REAL count from CSV."),
            "age_depth_gating": "AGE_DEPTH_OPEN in scale.py is a CONSTRUCTED structural "
                                "mask (which life-stage a depth is normally reached in).",
        },
        "sources": {
            "enrollment_literacy": "World Bank EdStats via education-atlas "
                                   "data/processed/observation.parquet (latest per country).",
            "researchers_per_million": "UNESCO Institute for Statistics / World Bank "
                                       "SP.POP.SCIE.RD.P6 (latest ~2021-2023).",
            "research_corpus": "research-atlas research_atlas_slim.duckdb "
                               "(researcher_segment, stats).",
            "internet_by_age": "ITU, Measuring digital development: Facts and Figures 2023.",
            "graduate_share": "OECD Education at a Glance (graduate-entry rates).",
        },
    }
    results["meta"]["depth_scale"] = {
        "L0": "basic literacy/numeracy", "L1": "K-12/secondary",
        "L2": "undergraduate", "L3": "graduate/professional",
        "L4": "frontier / read primary research", "L5": "producing new knowledge",
    }

    OUT.write_text(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    r = main()
    print(f"wrote {OUT}")
    s = r["access_by_depth_and_income"]
    print("\nAccess % by depth and income tier (REAL L0-L2, est L3-L5):")
    hdr = "tier".ljust(20) + "".join(l.ljust(10) for l in DEPTH_LEVELS)
    print(hdr)
    for t in INCOME_TIERS:
        print(t.ljust(20) + "".join(str(s[t][l]).ljust(10) for l in DEPTH_LEVELS))
    fp = r["frontier_participation"]
    print(f"\nWorld frontier-participation (L4): {fp['world_frontier_pct']}% "
          f"({fp['world_researchers_per_million']} researchers/M)")
    print("Depth ceiling by income:", r["depth_ceiling_by_income"])
