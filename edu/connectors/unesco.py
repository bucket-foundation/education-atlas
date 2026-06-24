"""UNESCO UIS connector -- the authoritative SDG 4 source (best-effort).

The UNESCO Institute for Statistics (UIS) is the official custodian of the
SDG 4 education indicators. Its public API
(``https://api.uis.unesco.org/api/public/data/indicators``) returns clean JSON
records ``{indicatorId, geoUnit, year, value}`` for a list of indicators across
a list of countries.

We use UIS for **school-infrastructure** indicators (SDG 4.a) that the World
Bank does not expose cleanly: % of primary schools with electricity, internet
(for pedagogy), and basic drinking water. These are the only sourced data on the
infrastructure / digital-divide problem categories.

Best-effort: UIS occasionally rate-limits or changes its query surface. The
connector queries countries in batches and tolerates an empty/failed batch
(logs + continues) so the build never hard-fails on UIS. World Bank remains the
backbone; UIS is additive coverage.

Provenance: ``source="unesco"``, ``source_id=<UIS indicator id>``,
``source_url`` = the UIS data browser.
"""

from __future__ import annotations

from typing import Iterable, Iterator

from edu.connectors.base import Connector
from edu.indicators import INDICATORS, unesco_codes
from edu.schema import Row, make_obs_id, now_iso

API = "https://api.uis.unesco.org/api/public/data/indicators"


class UNESCOConnector(Connector):
    source = "unesco"
    delay = 0.3  # gentler on the UIS API

    def fetch(self, country_codes: Iterable[str] | None = None,
              start: int = 2010, end: int = 2024, batch: int = 60, **_):
        """Yield cached raw pages per indicator (all requested countries)."""
        codes = unesco_codes()
        countries = list(country_codes) if country_codes else None
        for code in codes:
            key = f"{code}_{start}_{end}"
            if self.has_raw(key):
                yield {"code": code, "records": self.load_raw(key)}
                continue
            records: list[dict] = []
            # If no country list given, a single bare query returns all geoUnits.
            if not countries:
                resp = self.http.get(API, params=[
                    ("indicator", code), ("start", start), ("end", end)])
                if resp and resp.status_code == 200:
                    records = resp.json().get("records", [])
            else:
                for i in range(0, len(countries), batch):
                    chunk = countries[i:i + batch]
                    params = [("indicator", code), ("start", start), ("end", end)]
                    params += [("geoUnit", c) for c in chunk]
                    resp = self.http.get(API, params=params)
                    if resp and resp.status_code == 200:
                        records.extend(resp.json().get("records", []))
                    else:
                        print(f"  unesco {code}: batch {i//batch} failed (skip)")
            self.cache_raw(key, records)
            print(f"  unesco {code}: {len(records)} records")
            yield {"code": code, "records": records}

    def normalize(self, raw_pages: Iterable[dict]) -> Iterator[Row]:
        as_of = now_iso()
        for page in raw_pages:
            code = page["code"]
            meta = INDICATORS.get(code)
            if not meta:
                continue
            url = f"https://databrowser.uis.unesco.org/browser/EDUCATION/{code}"
            for rec in page["records"]:
                iso3 = rec.get("geoUnit") or ""
                if len(iso3) != 3 or rec.get("value") is None:
                    continue
                year = rec.get("year")
                yield Row("observation", dict(
                    obs_id=make_obs_id("unesco", iso3, code, meta["level"], year),
                    country_code=iso3,
                    indicator_code=code,
                    category=meta["category"],
                    level=meta["level"],
                    year=year,
                    value=rec.get("value"),
                    unit=meta["unit"],
                    source="unesco",
                    source_id=code,
                    source_url=url,
                    as_of=as_of,
                ))
