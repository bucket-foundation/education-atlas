"""Build the GEOGRAPHIC + DEMOGRAPHIC dimension of the knowledge-access gradient.

A per-country world map of who reaches the frontier (L4/L5 on the scale.py depth
ladder). Extends results.json / results_expansion.json with the spatial and
demographic cut the income-tier surface could not show: *which countries* hold
the world's frontier capacity, and *who within them* is shut out.

Reuses, verbatim:
  - the L0-L5 depth ladder + income tiers from scale.py
  - the World Bank cache directory data/raw/worldbank/ that build_access uses
  - the research-atlas slim DB for the corpus cross-check
and adds three per-country World Bank series the base map only had as group
means (researchers/M was a documented anchor there; here it is per-country real):

  SP.POP.SCIE.RD.P6  Researchers in R&D (per million people)  -- the L4/L5 anchor
  SE.TER.ENRR        School enrollment, tertiary (% gross)     -- L2/L3 (cached)
  IT.NET.USER.ZS     Individuals using the Internet (%)        -- access channel
  SE.TER.CMPL.ZS     Tertiary first-degree graduation ratio    -- completion
  SE.TER.ENRR.FE/.MA tertiary GER by sex                       -- gender cut

Composite per-country frontier-access index (0-100): a transparent weighted mean
of the four normalized components. Coverage is honest: many low-income countries
have NO researcher datapoint at all -- that missingness is itself a headline.

Idempotent: re-running re-fetches only un-cached series and overwrites
results_geographic.json deterministically.
"""

from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path

import pandas as pd

from scale import INCOME_TIERS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]                       # education-atlas/
WB_CACHE = ROOT / "data" / "raw" / "worldbank"
EDU_DATA = ROOT / "data" / "processed"
RESEARCH_DB = ROOT.parent / "research-atlas" / "research_atlas_slim.duckdb"
OUT = HERE / "results_geographic.json"

WB_API = "https://api.worldbank.org/v2"
START, END = 2000, 2024

# The per-country series. Codes already in the build_access cache are reused;
# the new ones are fetched into the SAME cache dir with the SAME key format.
SERIES = {
    "researchers_per_million": "SP.POP.SCIE.RD.P6",
    "tertiary_ger":            "SE.TER.ENRR",
    "internet_users_pct":      "IT.NET.USER.ZS",
    "tertiary_completion":     "SE.TER.CMPL.ZS",
    "tertiary_ger_female":     "SE.TER.ENRR.FE",
    "tertiary_ger_male":       "SE.TER.ENRR.MA",
}


# --------------------------------------------------------------------------- #
# World Bank cache loader (same key format as edu/connectors/worldbank.py)
# --------------------------------------------------------------------------- #
def _cache_path(code: str) -> Path:
    return WB_CACHE / f"{code}_{START}_{END}.json"


def _fetch_series(code: str) -> list[dict]:
    """Return cached records for an indicator, fetching+caching if absent.

    Mirrors WorldBankConnector.fetch: paginated /country/all/indicator/<code>,
    cached as <code>_<start>_<end>.json in data/raw/worldbank/.
    """
    path = _cache_path(code)
    if path.exists():
        return json.loads(path.read_text())
    WB_CACHE.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    page, pages = 1, 1
    while page <= pages:
        url = (f"{WB_API}/country/all/indicator/{code}"
               f"?format=json&date={START}:{END}&per_page=20000&page={page}")
        with urllib.request.urlopen(url, timeout=60) as r:
            payload = json.loads(r.read().decode())
        if not isinstance(payload, list) or len(payload) < 2:
            break
        pages = int((payload[0] or {}).get("pages", 1) or 1)
        records.extend(payload[1] or [])
        page += 1
    path.write_text(json.dumps(records))
    print(f"  fetched worldbank {code}: {len(records)} records -> {path.name}")
    return records


def _latest_per_country(code: str) -> dict[str, dict]:
    """Latest non-null value per ISO3 country (drops regional aggregates)."""
    recs = _fetch_series(code)
    best: dict[str, dict] = {}
    for rec in recs:
        iso3 = rec.get("countryiso3code") or ""
        if len(iso3) != 3 or rec.get("value") is None:
            continue
        year = int(rec.get("date"))
        cur = best.get(iso3)
        if cur is None or year > cur["year"]:
            best[iso3] = {"value": float(rec["value"]), "year": year}
    return best


# --------------------------------------------------------------------------- #
# Country dimension (region, income, lon/lat) from the processed parquet
# --------------------------------------------------------------------------- #
def _country_dim() -> pd.DataFrame:
    c = pd.read_parquet(EDU_DATA / "country.parquet")
    # real countries only: drop WB aggregates / unclassified
    c = c[~c.income_group.isin(["Aggregate", "Not classified"])]
    c = c[c.region != "Aggregates"]
    # World Bank region labels carry inconsistent trailing whitespace
    # ("Sub-Saharan Africa " vs "Sub-Saharan Africa"); strip so the rollup merges.
    c = c.copy()
    c["region"] = c["region"].astype(str).str.strip()
    return c[["country_code", "name", "region", "income_group",
              "longitude", "latitude"]].dropna(subset=["country_code"])


# --------------------------------------------------------------------------- #
# Composite frontier-access index
# --------------------------------------------------------------------------- #
# Component weights. Researchers/M is the L4/L5 anchor and gets the most weight;
# tertiary + completion are the L2/L3 pipeline; internet is the access channel.
# Documented, transparent -- NOT tuned to any target.
INDEX_WEIGHTS = {
    "researchers_per_million": 0.40,   # the frontier anchor (L4/L5)
    "tertiary_ger":            0.25,   # L2 pipeline into the frontier
    "tertiary_completion":     0.15,   # L3 completion, who finishes
    "internet_users_pct":      0.20,   # the digital access channel
}
# Researchers/M is heavy-tailed (Israel/Korea ~8000+, SSA single digits). We log-
# compress it before normalizing so the index isn't a one-country spike. The
# others are already 0-100ish percentages.
RPM_LOG_CAP = 9000.0   # ~ the world max (Israel/Korea band); documented cap


def _normalize_component(values: dict[str, float], code_key: str) -> dict[str, float]:
    """Map a raw series to 0-100. Researchers/M is log-scaled; %s are clipped."""
    if code_key == "researchers_per_million":
        out = {}
        denom = math.log10(RPM_LOG_CAP + 1.0)
        for iso, v in values.items():
            out[iso] = round(min(math.log10(v + 1.0) / denom, 1.0) * 100, 2)
        return out
    return {iso: round(min(max(v, 0.0), 100.0), 2) for iso, v in values.items()}


def build_index(comp_latest: dict[str, dict[str, dict]],
                countries: pd.DataFrame) -> dict:
    """Per-country composite 0-100 index over the four real components.

    A country gets an index iff it has the frontier anchor (researchers/M);
    countries with no researcher datapoint are tracked separately -- their
    absence from the index is the coverage finding. Missing non-anchor
    components are mean-imputed within the country's income group (flagged).
    """
    norm = {k: _normalize_component({iso: d["value"] for iso, d in comp_latest[c].items()}, k)
            for k, c in [(k, k) for k in INDEX_WEIGHTS]}

    iso_income = dict(zip(countries.country_code, countries.income_group))
    iso_name = dict(zip(countries.country_code, countries.name))
    iso_region = dict(zip(countries.country_code, countries.region))

    # income-group means per component (for imputation of non-anchor gaps)
    grp_means: dict[str, dict[str, float]] = {}
    for k in INDEX_WEIGHTS:
        by_grp: dict[str, list[float]] = {}
        for iso, val in norm[k].items():
            g = iso_income.get(iso)
            if g:
                by_grp.setdefault(g, []).append(val)
        grp_means[k] = {g: sum(v) / len(v) for g, v in by_grp.items()}

    per_country = {}
    imputed_counts = {k: 0 for k in INDEX_WEIGHTS}
    has_anchor, no_anchor = [], []

    for iso in sorted(set(iso_income)):
        anchor = norm["researchers_per_million"].get(iso)
        if anchor is None:
            no_anchor.append(iso)
            continue
        has_anchor.append(iso)
        parts, imputed_flags = {}, {}
        for k in INDEX_WEIGHTS:
            v = norm[k].get(iso)
            if v is None:
                v = round(grp_means[k].get(iso_income.get(iso), 0.0), 2)
                imputed_counts[k] += 1
                imputed_flags[k] = True
            parts[k] = v
        idx = round(sum(parts[k] * w for k, w in INDEX_WEIGHTS.items()), 2)
        per_country[iso] = {
            "name": iso_name.get(iso, iso),
            "region": iso_region.get(iso),
            "income_group": iso_income.get(iso),
            "index": idx,
            "components": parts,
            "imputed": imputed_flags,
            "researchers_per_million_raw":
                round(comp_latest["researchers_per_million"][iso]["value"], 1),
            "researchers_year":
                comp_latest["researchers_per_million"][iso]["year"],
        }
    return {
        "per_country": per_country,
        "n_with_anchor": len(has_anchor),
        "n_without_anchor": len(no_anchor),
        "without_anchor_iso": sorted(no_anchor),
        "imputed_component_counts": imputed_counts,
        "weights": INDEX_WEIGHTS,
        "rpm_log_cap": RPM_LOG_CAP,
    }


# --------------------------------------------------------------------------- #
# Concentration statistics
# --------------------------------------------------------------------------- #
def concentration(comp_latest: dict, countries: pd.DataFrame) -> dict:
    """How concentrated is the world's *absolute* frontier capacity?

    Absolute capacity = researchers/M x population (we approximate population
    from the World Bank total-population series if cached, else weight by the
    raw researcher headcount where available). To stay fully real with the data
    on hand, we compute capacity = researchers/M (a per-capita rate) AND an
    absolute-capacity estimate using population pulled live (SP.POP.TOTL).
    """
    # REAL countries only -- World Bank ISO3 codes also include regional/income
    # AGGREGATES (WLD, OED, EAS, MIC...) in the indicator series. The country
    # dimension parquet already excludes aggregates; restrict to it so the
    # concentration + Gini are over sovereign countries, not WB rollups.
    real_iso = set(countries.country_code)
    rpm = {iso: d["value"] for iso, d in comp_latest["researchers_per_million"].items()
           if iso in real_iso}
    iso_name = dict(zip(countries.country_code, countries.name))

    # population for absolute capacity (real WB series, cached on first run)
    pop_latest = _latest_per_country("SP.POP.TOTL")
    abs_cap = {}
    for iso, r in rpm.items():
        p = pop_latest.get(iso)
        if p:
            abs_cap[iso] = r / 1_000_000 * p["value"]   # estimated researcher count
    total_cap = sum(abs_cap.values()) or 1.0
    ranked = sorted(abs_cap.items(), key=lambda kv: -kv[1])

    def top_share(n):
        return round(sum(v for _, v in ranked[:n]) / total_cap * 100, 1)

    # Gini of the per-capita researchers/M distribution across countries
    vals = sorted(rpm.values())
    n = len(vals)
    cum = sum((i + 1) * v for i, v in enumerate(vals))
    gini = round((2 * cum) / (n * sum(vals)) - (n + 1) / n, 3) if sum(vals) else None

    top10 = [{"iso": iso, "name": iso_name.get(iso, iso),
              "researchers_est": int(v),
              "share_pct": round(v / total_cap * 100, 2)} for iso, v in ranked[:10]]

    return {
        "absolute_capacity_method": "researchers_per_million x SP.POP.TOTL (latest); "
                                    "ESTIMATED researcher headcount per country.",
        "n_countries_in_capacity": len(abs_cap),
        "total_estimated_researchers": int(total_cap),
        "top1_share_pct": top_share(1),
        "top5_share_pct": top_share(5),
        "top10_share_pct": top_share(10),
        "top25_share_pct": top_share(25),
        "top10_countries": top10,
        "gini_researchers_per_million": gini,
        "median_researchers_per_million": round(vals[n // 2], 1) if n else None,
        "max_researchers_per_million": round(max(vals), 1) if vals else None,
        "min_researchers_per_million": round(min(vals), 1) if vals else None,
    }


# --------------------------------------------------------------------------- #
# Demographic cuts: gender + the rural/income access gap
# --------------------------------------------------------------------------- #
# UNESCO UIS "Women in Science" -- share of researchers who are women. The
# global figure sits near a third; the regional spread is the finding. REAL
# documented anchors (UNESCO Institute for Statistics, Fact Sheet "Women in
# Science", latest releases ~2021-2023). Flagged as cited anchors, not pulled.
WOMEN_RESEARCHERS_PCT = {
    "World":                        33.3,
    "Central Asia":                 48.2,
    "Latin America & Caribbean":    45.8,
    "Central & Eastern Europe":     39.6,
    "Arab States":                  41.5,
    "Sub-Saharan Africa":           31.5,
    "North America & Western Eur":  32.9,
    "East Asia & Pacific":          23.9,
    "South & West Asia":            18.5,
}
# Field gap inside research (UNESCO / "Cracking the code"): women's share of
# graduates by broad field -- the horizontal segregation. REAL anchors.
WOMEN_GRADUATE_SHARE_BY_FIELD = {
    "Health & Welfare":                 69.0,
    "Education":                        67.0,
    "Arts & Humanities":                64.0,
    "Social sciences / Business / Law": 58.0,
    "Natural sciences / Math / Stats":  52.0,
    "ICT (computing)":                  21.0,
    "Engineering / Manufacturing":      28.0,
}


def gender_cut(comp_latest: dict, countries: pd.DataFrame) -> dict:
    """Real WB female-vs-male tertiary GER gap + documented UNESCO women-in-
    research anchors. Tertiary GER by sex is fully real per country; the
    researcher-gender share is a UNESCO documented anchor (no clean WB series)."""
    real_iso = set(countries.country_code)
    fe = {iso: d["value"] for iso, d in comp_latest["tertiary_ger_female"].items()
          if iso in real_iso}
    ma = {iso: d["value"] for iso, d in comp_latest["tertiary_ger_male"].items()
          if iso in real_iso}
    iso_income = dict(zip(countries.country_code, countries.income_group))

    by_income = {}
    for tier in INCOME_TIERS:
        f = [fe[i] for i in fe if iso_income.get(i) == tier]
        m = [ma[i] for i in ma if iso_income.get(i) == tier]
        if f and m:
            fmean, mmean = sum(f) / len(f), sum(m) / len(m)
            by_income[tier] = {
                "female_tertiary_ger": round(fmean, 1),
                "male_tertiary_ger": round(mmean, 1),
                "female_minus_male": round(fmean - mmean, 1),
                "n_countries_female": len(f),
            }
    # global means
    gf = round(sum(fe.values()) / len(fe), 1) if fe else None
    gm = round(sum(ma.values()) / len(ma), 1) if ma else None

    return {
        "tertiary_ger_by_sex_real": {
            "source": "World Bank SE.TER.ENRR.FE / .MA (latest per country).",
            "world_female_mean": gf,
            "world_male_mean": gm,
            "world_female_minus_male": round(gf - gm, 1) if gf and gm else None,
            "by_income": by_income,
            "note": "Tertiary GROSS enrollment by sex; in aggregate women now "
                    "out-enroll men in tertiary in most regions, yet hold a "
                    "minority of RESEARCH posts -- the leak is post-degree.",
        },
        "women_researchers_pct": {
            "source": "UNESCO UIS Women in Science fact sheet (documented anchors, "
                      "latest ~2021-2023). NOT a clean World Bank series.",
            "estimated": True,
            "by_region": WOMEN_RESEARCHERS_PCT,
            "world": WOMEN_RESEARCHERS_PCT["World"],
        },
        "women_graduate_share_by_field": {
            "source": "UNESCO 'Cracking the code' / UIS graduate shares by field "
                      "(documented anchors).",
            "estimated": True,
            "by_field": WOMEN_GRADUATE_SHARE_BY_FIELD,
        },
    }


# Rural/urban access gap. The cleanest globally-comparable real anchor is the
# UNESCO/World Bank finding on out-of-school + completion rates by location and
# by wealth quintile (DHS-backed). Documented anchors -- DHS microdata is not in
# this repo's cache, so these are cited.
RURAL_URBAN_AND_WEALTH = {
    "source": "UNESCO GEM Report / World Inequality Database on Education (WIDE), "
              "DHS-backed. Documented anchors (DHS microdata not in cache).",
    "estimated": True,
    "tertiary_completion_richest_vs_poorest_quintile_lic_lmic": {
        "richest_quintile_pct": 9.0,
        "poorest_quintile_pct": 0.5,
        "ratio": "~18x",
        "note": "In low/lower-middle income countries, tertiary completion is "
                "near-universally a top-wealth-quintile phenomenon.",
    },
    "primary_completion_urban_vs_rural_low_income": {
        "urban_pct": 70.0,
        "rural_pct": 45.0,
        "gap_pct_points": 25.0,
        "note": "Rural children in low-income countries complete primary at far "
                "lower rates -- the gap compounds up every depth rung.",
    },
}


# --------------------------------------------------------------------------- #
# Regional rollup (powers the choropleth + the fallback regional bars)
# --------------------------------------------------------------------------- #
def regional_rollup(index: dict, comp_latest: dict, countries: pd.DataFrame) -> dict:
    pc = index["per_country"]
    rpm = {iso: d["value"] for iso, d in comp_latest["researchers_per_million"].items()}
    iso_region = dict(zip(countries.country_code, countries.region))
    iso_income = dict(zip(countries.country_code, countries.income_group))

    regions = {}
    for region in sorted(set(r for r in iso_region.values() if r)):
        isos_all = [i for i in iso_income if iso_region.get(i) == region]
        idx_vals = [pc[i]["index"] for i in isos_all if i in pc]
        rpm_vals = [rpm[i] for i in isos_all if i in rpm]
        regions[region] = {
            "n_countries": len(isos_all),
            "n_with_researcher_data": len(rpm_vals),
            "coverage_pct": round(100 * len(rpm_vals) / len(isos_all), 0) if isos_all else 0,
            "mean_frontier_index": round(sum(idx_vals) / len(idx_vals), 1) if idx_vals else None,
            "mean_researchers_per_million": round(sum(rpm_vals) / len(rpm_vals), 1) if rpm_vals else None,
        }
    return regions


# --------------------------------------------------------------------------- #
def _research_atlas_crosscheck() -> dict:
    out = {}
    try:
        import duckdb
        con = duckdb.connect(str(RESEARCH_DB), read_only=True)
        persons = con.execute("SELECT persons FROM stats").fetchone()[0]
        con.close()
        out["research_atlas_corpus_persons"] = int(persons)
        out["note"] = ("research-atlas finding: all top-25 funded orgs are US/elite "
                       "institutions -- the org-level mirror of this country-level "
                       "concentration.")
    except Exception as e:
        out["error"] = str(e)
    return out


def main() -> dict:
    countries = _country_dim()
    comp_latest = {k: _latest_per_country(code) for k, code in SERIES.items()}

    index = build_index(comp_latest, countries)
    conc = concentration(comp_latest, countries)
    gender = gender_cut(comp_latest, countries)
    regions = regional_rollup(index, comp_latest, countries)

    # ranked countries for the bar figures
    pc = index["per_country"]
    ranked = sorted(pc.items(), key=lambda kv: -kv[1]["index"])
    top = [{"iso": i, **{k: v[k] for k in ("name", "index", "income_group",
            "researchers_per_million_raw")}} for i, v in ranked[:15]]
    bottom = [{"iso": i, **{k: v[k] for k in ("name", "index", "income_group",
              "researchers_per_million_raw")}} for i, v in ranked[-15:]]

    n_real_countries = len(countries)
    n_no_data = index["n_without_anchor"]

    results = {
        "meta": {
            "title": "Geographic + demographic dimension of the knowledge-access gradient",
            "extends": "results.json / results_expansion.json (same scale.py ladder)",
            "frontier_anchor": "SP.POP.SCIE.RD.P6 (researchers per million) = L4/L5 anchor",
            "generated_from": "World Bank cache data/raw/worldbank/ (3 new per-country "
                              "series fetched live + cached) + research-atlas slim DB",
            "n_real_countries": n_real_countries,
        },
        # 1 -- per-country composite index
        "frontier_access_index": index,
        "ranked_top15": top,
        "ranked_bottom15": bottom,
        # 4 -- concentration
        "concentration": conc,
        # 3 -- demographic cuts
        "gender": gender,
        "rural_urban_wealth": RURAL_URBAN_AND_WEALTH,
        # regional rollup (choropleth + fallback)
        "regional": regions,
        # corroboration
        "research_atlas_crosscheck": _research_atlas_crosscheck(),
        # headline
        "headline": {
            "n_real_countries": n_real_countries,
            "n_with_researcher_data": index["n_with_anchor"],
            "n_without_researcher_data": n_no_data,
            "pct_countries_without_researcher_data":
                round(100 * n_no_data / n_real_countries, 0),
            "top10_share_of_frontier_capacity_pct": conc["top10_share_pct"],
            "top25_share_of_frontier_capacity_pct": conc["top25_share_pct"],
            "gini_researchers_per_million": conc["gini_researchers_per_million"],
            "women_researchers_world_pct": WOMEN_RESEARCHERS_PCT["World"],
            "women_researchers_min_region":
                min(WOMEN_RESEARCHERS_PCT.items(), key=lambda kv: kv[1]
                    if kv[0] != "World" else 999),
            "max_vs_min_researchers_per_million_ratio":
                round(conc["max_researchers_per_million"] /
                      conc["min_researchers_per_million"], 0)
                if conc["min_researchers_per_million"] else None,
        },
        "estimates": {
            "frontier_access_index": "Composite 0-100 = weighted mean of REAL World "
                "Bank components (researchers/M log-scaled, tertiary GER, tertiary "
                "completion, internet). Weights are DOCUMENTED (0.40/0.25/0.15/0.20), "
                "not tuned. Non-anchor gaps mean-imputed within income group (flagged "
                "per country under .imputed).",
            "concentration": "Absolute capacity = researchers/M x SP.POP.TOTL = an "
                "ESTIMATED researcher headcount per country (both series REAL). Top-share "
                "and Gini computed on that estimate.",
            "women_researchers_pct": "UNESCO UIS Women in Science -- DOCUMENTED ANCHORS, "
                "not a World Bank series.",
            "tertiary_ger_by_sex": "REAL World Bank SE.TER.ENRR.FE / .MA, latest per country.",
            "rural_urban_wealth": "UNESCO GEM/WIDE + DHS -- DOCUMENTED ANCHORS (DHS "
                "microdata not in cache).",
        },
        "sources": {
            "researchers_per_million": "World Bank / UNESCO UIS SP.POP.SCIE.RD.P6 "
                "(per-country, latest available; cached in data/raw/worldbank/).",
            "tertiary_ger": "World Bank SE.TER.ENRR.",
            "tertiary_completion": "World Bank SE.TER.CMPL.ZS (first-degree graduation ratio).",
            "internet_users": "World Bank IT.NET.USER.ZS (individuals using the internet).",
            "tertiary_ger_by_sex": "World Bank SE.TER.ENRR.FE / SE.TER.ENRR.MA.",
            "population": "World Bank SP.POP.TOTL (for absolute capacity).",
            "women_in_science": "UNESCO Institute for Statistics, Women in Science fact sheet.",
            "rural_urban_wealth": "UNESCO GEM Report / WIDE database (DHS-backed).",
            "research_atlas": "research-atlas research_atlas_slim.duckdb (corpus cross-check).",
        },
    }

    OUT.write_text(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    r = main()
    print(f"\nwrote {OUT}\n")
    h = r["headline"]
    print("=== GEOGRAPHIC HEADLINE ===")
    print(f"  real countries:                  {h['n_real_countries']}")
    print(f"  with researcher data:            {h['n_with_researcher_data']}")
    print(f"  WITHOUT researcher data:         {h['n_without_researcher_data']} "
          f"({h['pct_countries_without_researcher_data']}% of countries)")
    print(f"  top-10 share of frontier cap:    {h['top10_share_of_frontier_capacity_pct']}%")
    print(f"  top-25 share of frontier cap:    {h['top25_share_of_frontier_capacity_pct']}%")
    print(f"  Gini (researchers/M):            {h['gini_researchers_per_million']}")
    print(f"  max/min researchers/M ratio:     {h['max_vs_min_researchers_per_million_ratio']}x")
    print(f"  women researchers (world):       {h['women_researchers_world_pct']}%")
    print(f"  women researchers (min region):  {h['women_researchers_min_region']}")
    print("\n  top-10 countries by absolute frontier capacity:")
    for c in r["concentration"]["top10_countries"]:
        print(f"    {c['name']:<28} {c['researchers_est']:>10,}  ({c['share_pct']}%)")
