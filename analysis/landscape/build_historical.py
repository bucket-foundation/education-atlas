"""Build the HISTORICAL access-arc dataset: the long-run series behind
docs/landscape/06-historical-access-arc.md.

This is the *time* axis of the knowledge-access gradient pushed back across
eras -- complementing docs/landscape/03 (which only ran 2000->2024). It holds
three real long-run series and one era-by-era qualitative ledger, and computes
a few derived trend numbers (CAGR, multiples, doubling times).

Idempotent + deterministic: re-running reproduces results_historical.json
byte-for-byte. No network, no GPU. All anchors are cited inline and in the
companion doc; every estimate is flagged `est`/`approx`.

Anchors (see doc 06 for full citations):
 - Global adult literacy, World entity, 1820->2024: Our World in Data
   (cross-country-literacy-rates), built on Buringh & van Zanden (2009) +
   UNESCO. REAL.
 - Book prices after Gutenberg: Dittmar (2011 QJE) / van Zanden -- real prices
   fell ~2/3 in the Low Countries 1450-1500 and ~75% in England 1450-1530;
   raw price ~-2.4%/yr, content-adjusted ~-1.7%/yr for a century. REAL anchors.
 - European book output: Buringh & van Zanden (2009) -- a few hundred thousand
   MS books in the whole 14th c.; ~12.6M printed books by 1500; the 16th c.
   alone produced on the order of 10^8. Order-of-magnitude REAL.
 - Internet penetration + OA share 2000->2024: reused from build_expansion
   (World Bank/ITU; OpenAlex/Unpaywall/COKI). REAL anchors.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "results_historical.json"


# --------------------------------------------------------------------------- #
# 1. REAL long-run global literacy series (Our World in Data, World entity).
#    Source: ourworldindata.org/grapher/cross-country-literacy-rates (OWID_WRL),
#    built on Buringh & van Zanden 2009 historical estimates + UNESCO modern.
#    Values are % of adults (15+) able to read & write. REAL.
LITERACY_WORLD_PCT = {
    1820: 12.05,
    1870: 18.74,
    1900: 21.40,
    1910: 26.45,
    1920: 31.62,
    1930: 32.53,
    1940: 41.88,
    1950: 35.96,   # post-WWII; decolonization re-baselined the denominator
    1960: 41.62,
    1975: 65.42,
    1990: 74.63,
    2000: 81.12,
    2010: 84.37,
    2020: 86.98,
    2024: 87.74,
}

# 2. Book price collapse after the printing press (~1440). REAL anchors,
#    multiple independent estimates -- recorded as a range, not a point.
BOOK_PRICE_COLLAPSE = {
    "era": "printing press, ~1440-1530",
    "low_countries_real_price_fall_1450_1500_pct": 67,   # ~2/3, van Zanden/Dittmar
    "england_real_price_fall_1450_1530_pct": 75,          # Dittmar 2011
    "raw_price_cagr_pct_per_yr_century": -2.4,            # ~-2.4%/yr for ~100 yrs
    "content_adjusted_cagr_pct_per_yr_century": -1.7,     # quality-adjusted
    "note": "Real price of a book fell by roughly two-thirds to three-quarters "
            "in the first 50-80 years of print; the single largest one-shot "
            "collapse in the cost of a unit of recorded knowledge before the "
            "internet.",
    "status": "real (multiple independent economic-history estimates)",
}

# 3. European book OUTPUT, order-of-magnitude (Buringh & van Zanden 2009 +
#    incunabula counts). Production as a proxy for access-to-read supply.
BOOK_OUTPUT_ORDERS = {
    "manuscript_books_whole_14th_century_approx": 2_700_000,  # B&vZ ~2.7M in 14th c.
    "printed_books_by_1500_approx": 12_600_000,               # incunabula era total
    "printed_books_16th_century_order": 100_000_000,          # ~10^8, order of mag
    "scribe_pages_per_day": 3,                                # hand-copy throughput
    "press_pages_per_day_order": 250,                         # early press throughput
    "throughput_step_change_x": 80,                           # ~250/3, order ~80-100x
    "status": "real order-of-magnitude (B&vZ 2009; incunabula short-title counts)",
}

# 4. Modern reading-access series 2000->2024 (reused anchors; the SHORT arc that
#    doc 03 already plotted -- carried here so the historical figure can show the
#    whole sweep on one timeline).
INTERNET_PENETRATION_PCT = {1990: 0.05, 1995: 0.4, 2000: 6.7, 2005: 16.0,
                            2010: 29.0, 2015: 43.0, 2020: 60.0, 2024: 68.0}
OA_SHARE_PCT = {2000: 12, 2005: 18, 2010: 27, 2015: 39, 2020: 50, 2024: 54}
WIKIPEDIA_EN_ARTICLES = {2001: 0, 2005: 750_000, 2010: 3_400_000,
                         2015: 4_900_000, 2024: 6_900_000, 2026: 7_000_000}

# 5. The era-by-era ledger: what changed, who GAINED access, and -- the thesis --
#    whether each era widened CONSUME (read) access, PRODUCE (make) access, or both.
ERA_LEDGER = [
    {
        "era": "Oral tradition",
        "span": "pre-~3200 BCE (and persisting)",
        "storage": "human memory; elders, bards, ritual",
        "who_gained_access": "everyone in the group, but only to what living "
                             "memory could hold; nothing survived a generation it "
                             "was not retold to",
        "consume_access_change": "n/a (no external store to read)",
        "produce_access_change": "everyone could add to the tradition, but it "
                                 "decayed; no cumulative frontier",
        "verdict": "neither consume nor produce *scaled* -- knowledge was bounded "
                   "by memory and mortality",
    },
    {
        "era": "Writing / manuscript",
        "span": "~3200 BCE - ~1450 CE",
        "storage": "clay, papyrus, parchment; hand-copied codices",
        "who_gained_access": "a tiny literate elite -- scribes, clergy, "
                             "aristocracy; medieval literacy ~<10%",
        "consume_access_change": "WIDENED slightly: knowledge could now outlive its "
                                 "author and travel -- but a book cost up to a "
                                 "house / a craftsman's annual income; reading was "
                                 "gated to those who could afford copies and tutors",
        "produce_access_change": "narrowed to scribes/scholars in monastic & court "
                                 "institutions; producing a copy = years of labor",
        "verdict": "first external store of knowledge, but access (read AND write) "
                   "gated to a literate elite",
    },
    {
        "era": "Printing press",
        "span": "~1440 -",
        "storage": "movable type; mass-printed books",
        "who_gained_access": "the literate middle classes, then the vernacular "
                             "reading public -- the first great democratization of "
                             "READING",
        "consume_access_change": "WIDENED massively: real book prices fell ~2/3 in "
                                 "50 yrs; output went from ~10^5/century (MS) to "
                                 "~10^7 by 1500 to ~10^8 in the 16th c.; press cut "
                                 "the cost of copying ~1000x and lit the "
                                 "Reformation + Scientific Revolution",
        "produce_access_change": "barely moved: an author still needed a press, "
                                 "patron/capital, and literacy; printing amplified "
                                 "who could be *read*, not who could *originate*",
        "verdict": "the canonical case -- a giant CONSUME-access jump, a tiny "
                   "PRODUCE-access jump",
    },
    {
        "era": "Public libraries + mass schooling",
        "span": "19th c. -",
        "storage": "tax-funded libraries; compulsory state schooling",
        "who_gained_access": "the general population -- literacy crossed from elite "
                             "minority to majority (world ~12% 1820 -> ~88% today)",
        "consume_access_change": "WIDENED to near-universal at the BASE: free public "
                                 "access to books + the skill to read them; the "
                                 "single largest expansion of consume-access in "
                                 "history by headcount",
        "produce_access_change": "expanded the *pool* (more literate people => more "
                                 "potential researchers) but the credential/research "
                                 "gate hardened: the modern university + PhD system "
                                 "professionalized and *enclosed* knowledge "
                                 "production",
        "verdict": "near-universal consume-access at the floor; production became a "
                   "credentialed profession",
    },
    {
        "era": "Internet + Wikipedia",
        "span": "1990s -",
        "storage": "the web; crowd-sourced reference; search",
        "who_gained_access": "~5.5 billion people online (68%, 2024); anyone "
                             "connected can read a free encyclopedia of ~7M "
                             "articles (en) + most of recorded reference knowledge",
        "consume_access_change": "WIDENED to information abundance: marginal cost of "
                                 "a copy ~$0; internet 0->68%; Wikipedia made "
                                 "reference knowledge free and instant",
        "produce_access_change": "still mostly READ: anyone can *publish a webpage*, "
                                 "but originating *validated* knowledge (research) "
                                 "stayed behind the lab/credential/funding gate",
        "verdict": "abundance of consume-access; produce-access at the frontier "
                   "essentially unchanged",
    },
    {
        "era": "Open access + preprints",
        "span": "2000s -",
        "storage": "arXiv, PMC, bioRxiv, OA journals, Unpaywall, OpenAlex",
        "who_gained_access": "anyone (no affiliation) can now READ the research "
                             "frontier: OA share 12% (2000) -> 54% (2024)",
        "consume_access_change": "WIDENED at the very TOP for the first time: "
                                 "reading primary, peer-reviewed/preprint research "
                                 "got a $0 path -- the frontier-reading "
                                 "democratization the rest of the arc never reached",
        "produce_access_change": "did NOT move production: APCs re-created the gate "
                                 "on the author side (Nature 2026 APC $12,850); "
                                 "prestige + affiliation + funding gates untouched",
        "verdict": "extended consume-access all the way to L4 (read the frontier); "
                   "production rate pinned at ~0.14% of humanity",
    },
    {
        "era": "AI (the open question)",
        "span": "2020s -",
        "storage": "LLMs + research agents over the whole corpus",
        "who_gained_access": "anyone with a chat box can summarize, explain, and "
                             "(claimants say) *help do* research -- the first tool "
                             "that plausibly touches the PRODUCE side",
        "consume_access_change": "WIDENS again, and lowers the comprehension barrier: "
                                 "AI can explain a paper, not just deliver it",
        "produce_access_change": "GENUINELY CONTESTED -- the first technology that "
                                 "*could* widen access to producing knowledge "
                                 "(hypothesis generation, autonomous experiments, "
                                 "the L3->L4 comprehension bridge) -- OR just a "
                                 "faster reading-amplifier that leaves the "
                                 "institutional/funding/validation gates fully "
                                 "standing",
        "verdict": "the only era where the consume-vs-produce verdict is not yet "
                   "written; both readings are defensible on current evidence",
    },
]


# --------------------------------------------------------------------------- #
def cagr(v0: float, v1: float, years: float) -> float:
    """Compound annual growth rate (%), guarding v0=0."""
    if v0 <= 0 or v1 <= 0 or years <= 0:
        return float("nan")
    return (math.pow(v1 / v0, 1.0 / years) - 1.0) * 100.0


def doubling_time_yrs(rate_pct_per_yr: float) -> float:
    if rate_pct_per_yr <= 0 or math.isnan(rate_pct_per_yr):
        return float("nan")
    return math.log(2) / math.log(1 + rate_pct_per_yr / 100.0)


def main() -> dict:
    lit_years = sorted(LITERACY_WORLD_PCT)
    y0, y1 = lit_years[0], lit_years[-1]
    lit0, lit1 = LITERACY_WORLD_PCT[y0], LITERACY_WORLD_PCT[y1]

    derived = {
        "literacy_1820_pct": lit0,
        "literacy_2024_pct": lit1,
        "literacy_multiple_1820_2024": round(lit1 / lit0, 2),
        "literacy_cagr_1820_2024_pct": round(cagr(lit0, lit1, y1 - y0), 3),
        "literacy_people_who_could_read_1820_approx": "under 100 million",
        "literacy_people_who_could_read_2024_approx": "over 5 billion",
        "internet_multiple_2000_2024": round(
            INTERNET_PENETRATION_PCT[2024] / INTERNET_PENETRATION_PCT[2000], 1),
        "oa_multiple_2000_2024": round(OA_SHARE_PCT[2024] / OA_SHARE_PCT[2000], 1),
        "book_price_real_fall_pct_range": [
            BOOK_PRICE_COLLAPSE["low_countries_real_price_fall_1450_1500_pct"],
            BOOK_PRICE_COLLAPSE["england_real_price_fall_1450_1530_pct"],
        ],
        "book_output_step_century_15th_to_16th_x": round(
            BOOK_OUTPUT_ORDERS["printed_books_16th_century_order"]
            / BOOK_OUTPUT_ORDERS["manuscript_books_whole_14th_century_approx"], 0),
        "copy_throughput_step_x_approx": BOOK_OUTPUT_ORDERS["throughput_step_change_x"],
    }

    result = {
        "meta": {
            "title": "Historical access arc -- the long-run time axis of the "
                     "knowledge-access gradient",
            "axis": "TIME (eras), complementing docs/landscape/03 which ran only "
                    "2000->2024",
            "thesis": "Every prior technology widened access to CONSUME knowledge; "
                      "none widened access to PRODUCE it. AI is the first open "
                      "question.",
            "note": "All series real anchors; era verdicts are interpretive; "
                    "estimates flagged. No network at runtime; values pinned from "
                    "cited sources (see doc 06).",
        },
        "literacy_world_pct": LITERACY_WORLD_PCT,
        "internet_penetration_pct": INTERNET_PENETRATION_PCT,
        "oa_share_pct": OA_SHARE_PCT,
        "wikipedia_en_articles": WIKIPEDIA_EN_ARTICLES,
        "book_price_collapse": BOOK_PRICE_COLLAPSE,
        "book_output_orders": BOOK_OUTPUT_ORDERS,
        "era_ledger": ERA_LEDGER,
        "derived": derived,
    }
    OUT.write_text(json.dumps(result, indent=2, sort_keys=False))
    print("wrote", OUT)
    print(f"  literacy {y0}->{y1}: {lit0}% -> {lit1}%  "
          f"(x{derived['literacy_multiple_1820_2024']}, "
          f"CAGR {derived['literacy_cagr_1820_2024_pct']}%/yr)")
    print(f"  book real-price fall (print era): "
          f"{derived['book_price_real_fall_pct_range'][0]}-"
          f"{derived['book_price_real_fall_pct_range'][1]}%")
    return result


if __name__ == "__main__":
    main()
