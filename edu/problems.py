"""Problem identification -- the analytical heart of education-atlas.

For each ``(country, indicator)`` it derives a data-grounded problem profile by
comparing the country's latest value against three reference frames and a trend:

1. **Benchmark gap** -- vs the SDG 4 / global-standard benchmark from the
   codebook (e.g. 100% completion, GPI = 1.0, learning poverty = 0).
2. **Peer gap** -- vs the median of the country's World Bank income-group peers
   in the same year (controls for "rich countries look good on everything").
3. **Trend** -- the per-year slope over the trend window; a worsening trend on a
   lower-better indicator (or declining higher-better indicator) is flagged.

Each profile gets a 0-100 ``severity`` score (benchmark gap dominates, peer gap
and adverse trend add on) and a set of human-readable ``flags``. Severities
roll up to a per-country, per-category problem ranking.

Everything is derived from the published ``observation`` + ``country`` tables;
nothing here invents numbers. Every problem row traces back to the observations
that produced it (same ``indicator_code`` + ``latest_year``).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from edu.connectors.base import DATA_PROCESSED
from edu.indicators import INDICATORS
from edu.schema import make_problem_id, now_iso

TREND_WINDOW = 10  # years back from latest for trend slope


def _latest_per_country(obs: pd.DataFrame) -> pd.DataFrame:
    """For each (country, indicator) take the most recent non-null observation."""
    obs = obs.dropna(subset=["value"])
    idx = obs.groupby(["country_code", "indicator_code"])["year"].idxmax()
    return obs.loc[idx].copy()


def _benchmark_gap(value: float, meta: dict):
    """Signed gap where positive = worse than benchmark. None if no benchmark."""
    bench = meta["benchmark"]
    if bench is None:
        return None, None
    direction = meta["direction"]
    if direction == "higher_better":
        gap = bench - value              # short of target => positive
    elif direction == "lower_better":
        gap = value - bench              # above target => positive
    elif direction == "target_one":     # GPI: distance from parity, either way
        gap = abs(value - bench)
    else:
        return None, None
    gap_pct = (gap / bench * 100.0) if bench not in (0, None) else None
    return float(gap), (float(gap_pct) if gap_pct is not None else None)


def _severity(gap, gap_pct, peer_gap, trend_adverse, meta) -> float:
    """Composite 0-100 severity. Benchmark gap dominates; peer gap + trend add."""
    score = 0.0
    bench = meta["benchmark"]
    direction = meta["direction"]

    # benchmark component (0-70)
    if gap is not None and gap > 0:
        if direction == "target_one":
            # GPI: gap of 0.2 from parity is severe
            score += min(70.0, (gap / 0.5) * 70.0)
        elif bench and bench > 0 and meta["unit"] in ("percent", "score", "years",
                                                       "ratio", "index"):
            score += min(70.0, abs(gap_pct or 0.0) * 0.9)
        else:  # counts (out-of-school): scale by magnitude, capped
            score += min(70.0, 35.0)  # any nonzero out-of-school is a real problem

    # peer component (0-20): worse than income-group peers
    if peer_gap is not None and peer_gap > 0:
        score += min(20.0, peer_gap * 0.4)

    # trend component (0-10): moving the wrong way
    if trend_adverse:
        score += 10.0

    return round(min(100.0, score), 1)


def build_problems(processed_dir: Path | None = None) -> pd.DataFrame:
    processed_dir = processed_dir or DATA_PROCESSED
    obs = pd.read_parquet(processed_dir / "observation.parquet")
    countries = pd.read_parquet(processed_dir / "country.parquet")[
        ["country_code", "income_group", "region"]]

    latest = _latest_per_country(obs)
    latest = latest.merge(countries, on="country_code", how="left")
    # exclude World Bank regional/income aggregates from per-country profiles
    latest = latest[latest["income_group"] != "Aggregate"]
    latest = latest[latest["country_code"].notna()]

    # peer medians: median latest value per (indicator, income_group)
    peer = (latest.groupby(["indicator_code", "income_group"])["value"]
            .median().rename("peer_median").reset_index())
    latest = latest.merge(peer, on=["indicator_code", "income_group"], how="left")

    as_of = now_iso()
    rows = []
    # pre-group observations for trend slope
    obs_sorted = obs.dropna(subset=["value"]).sort_values("year")
    grp = obs_sorted.groupby(["country_code", "indicator_code"])

    for _, r in latest.iterrows():
        code = r["indicator_code"]
        meta = INDICATORS.get(code)
        if not meta:
            continue
        value = r["value"]
        gap, gap_pct = _benchmark_gap(value, meta)

        # peer gap (signed; positive = worse than peer median)
        peer_med = r.get("peer_median")
        peer_gap = None
        if peer_med is not None and not pd.isna(peer_med):
            if meta["direction"] == "higher_better":
                peer_gap = float(peer_med - value)
            elif meta["direction"] == "lower_better":
                peer_gap = float(value - peer_med)
            elif meta["direction"] == "target_one":
                peer_gap = float(abs(value - 1.0) - abs(peer_med - 1.0))

        # trend slope over window
        slope = None
        trend_adverse = False
        try:
            sub = grp.get_group((r["country_code"], code))
            sub = sub[sub["year"] >= r["year"] - TREND_WINDOW]
            if len(sub) >= 2:
                x = sub["year"].astype(float).values
                y = sub["value"].astype(float).values
                slope = float(((x - x.mean()) * (y - y.mean())).sum() /
                              ((x - x.mean()) ** 2).sum())
                if meta["direction"] == "higher_better" and slope < -0.05:
                    trend_adverse = True
                elif meta["direction"] == "lower_better" and slope > 0.05:
                    trend_adverse = True
        except (KeyError, ZeroDivisionError):
            pass

        severity = _severity(gap, gap_pct, peer_gap, trend_adverse, meta)

        flags = []
        if gap is not None and gap > 0:
            flags.append("below_benchmark")
        if peer_gap is not None and peer_gap > 0:
            flags.append("below_peers")
        if trend_adverse:
            flags.append("worsening")
        if meta["direction"] == "target_one" and gap is not None and gap > 0.03:
            flags.append("gender_disparity")

        rows.append(dict(
            problem_id=make_problem_id(r["country_code"], meta["category"],
                                       meta["level"], code),
            country_code=r["country_code"],
            category=meta["category"],
            level=meta["level"],
            indicator_code=code,
            latest_year=int(r["year"]),
            latest_value=float(value),
            benchmark=meta["benchmark"],
            gap=gap,
            gap_pct=gap_pct,
            peer_median=(float(peer_med) if peer_med is not None
                         and not pd.isna(peer_med) else None),
            peer_gap=peer_gap,
            trend_slope=slope,
            severity=severity,
            flags="|".join(flags),
            as_of=as_of,
        ))

    df = pd.DataFrame(rows)
    out = processed_dir / "problem.parquet"
    df.to_parquet(out, index=False)
    return df


if __name__ == "__main__":
    df = build_problems()
    print(f"problems: {len(df):,} profiles across "
          f"{df['country_code'].nunique()} countries")
    print(df.groupby("category")["severity"].mean().round(1).sort_values(
        ascending=False))
