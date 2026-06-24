#!/usr/bin/env python3
"""Write small, committable sample parquet under data/processed/sample/.

The full observation/problem parquet are gitignored (heavy, rebuildable). This
ships a representative, fully-provenanced slice so the repo is explorable without
a build: a fixed set of diverse countries across all income groups + regions,
the full codebook, and their problem profiles.

Usage:
    python scripts/build_sample.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd                                   # noqa: E402

from edu.connectors.base import DATA_PROCESSED        # noqa: E402

SAMPLE = DATA_PROCESSED / "sample"

# diverse, recognizable spread across regions + income groups
SAMPLE_COUNTRIES = [
    "USA", "GBR", "DEU", "FIN", "JPN", "KOR", "SGP",   # high income
    "BRA", "MEX", "ZAF", "CHN", "IDN", "IND", "VNM",   # middle income
    "NGA", "ETH", "PAK", "BGD", "KEN", "AFG", "TCD",   # low / lower-mid
    "COD", "NER", "MLI", "YEM",                          # fragile / low
]


def main():
    SAMPLE.mkdir(parents=True, exist_ok=True)

    obs = pd.read_parquet(DATA_PROCESSED / "observation.parquet")
    ctry = pd.read_parquet(DATA_PROCESSED / "country.parquet")
    ind = pd.read_parquet(DATA_PROCESSED / "indicator.parquet")
    prob = pd.read_parquet(DATA_PROCESSED / "problem.parquet")

    obs_s = obs[obs["country_code"].isin(SAMPLE_COUNTRIES)
                & (obs["year"] >= 2010)]
    ctry_s = ctry[ctry["country_code"].isin(SAMPLE_COUNTRIES)]
    prob_s = prob[prob["country_code"].isin(SAMPLE_COUNTRIES)]

    obs_s.to_parquet(SAMPLE / "observation.parquet", index=False)
    ctry_s.to_parquet(SAMPLE / "country.parquet", index=False)
    ind.to_parquet(SAMPLE / "indicator.parquet", index=False)        # full codebook
    prob_s.to_parquet(SAMPLE / "problem.parquet", index=False)

    print(f"sample -> {SAMPLE}")
    print(f"  observation {len(obs_s):>7,} rows ({len(SAMPLE_COUNTRIES)} countries)")
    print(f"  country     {len(ctry_s):>7,} rows")
    print(f"  indicator   {len(ind):>7,} rows (full codebook)")
    print(f"  problem     {len(prob_s):>7,} rows")


if __name__ == "__main__":
    main()
