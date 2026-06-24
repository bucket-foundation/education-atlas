"""World Bank EdStats connector -- the education-atlas workhorse.

Pulls education indicators from the World Bank Indicators API
(api.worldbank.org/v2), which serves the EdStats education catalogue as clean,
free, paginated JSON. One fetch per indicator returns all countries x years; we
cache each indicator page, then normalize into long observations tagged with the
canonical category/level/unit from the codebook (:mod:`edu.indicators`).

Also populates the ``country`` dimension (region + income group) from the
World Bank country endpoint -- the basis for regional and income-peer comparison.

API shape
---------
``/v2/country/{codes}/indicator/{code}?format=json&date=Y1:Y2&per_page=N``
returns ``[metadata, [observations...]]`` where each observation has
``{countryiso3code, date, value, indicator:{id,value}, country:{value}}``.

Provenance: ``source="worldbank"``, ``source_id=<indicator code>``,
``source_url`` = the human-readable indicator page at data.worldbank.org.
"""

from __future__ import annotations

from typing import Iterable, Iterator

from edu import schema
from edu.connectors.base import Connector
from edu.indicators import INDICATORS, worldbank_codes
from edu.schema import Row, make_obs_id, now_iso

API = "https://api.worldbank.org/v2"


class WorldBankConnector(Connector):
    source = "worldbank"

    # ----- country dimension --------------------------------------------- #

    def fetch_countries(self) -> list[dict]:
        """Fetch + cache the World Bank country list (region, income group)."""
        key = "countries"
        if self.has_raw(key):
            return self.load_raw(key)
        resp = self.http.get(f"{API}/country",
                             params={"format": "json", "per_page": 400})
        payload = resp.json() if resp else [None, []]
        records = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
        self.cache_raw(key, records)
        return records

    def country_rows(self) -> Iterator[Row]:
        as_of = now_iso()
        for c in self.fetch_countries():
            region = (c.get("region") or {}).get("value")
            # World Bank tags regional/income aggregates with region
            # "Aggregates". We KEEP them in the dimension (they power the
            # regional + income-peer comparisons) but mark income_group so
            # they are excluded from per-country rankings.
            income = (c.get("incomeLevel") or {}).get("value")
            if region == "Aggregates":
                income = "Aggregate"
            yield Row("country", dict(
                country_code=c.get("id"),
                iso2=c.get("iso2Code"),
                name=c.get("name"),
                region=region,
                income_group=income,
                capital=c.get("capitalCity") or None,
                longitude=_num(c.get("longitude")),
                latitude=_num(c.get("latitude")),
                source="worldbank",
                source_id=c.get("id"),
                source_url=f"https://data.worldbank.org/country/{c.get('id')}",
                as_of=as_of,
            ))

    # ----- indicator observations ---------------------------------------- #

    def fetch(self, codes: Iterable[str] | None = None,
              start: int = 2000, end: int = 2024, **_) -> Iterable[dict]:
        """Yield one cached raw page per indicator (all countries x years)."""
        codes = list(codes) if codes else worldbank_codes()
        for code in codes:
            key = f"{code}_{start}_{end}"
            if self.has_raw(key):
                yield {"code": code, "records": self.load_raw(key)}
                continue
            records, page, pages = [], 1, 1
            while page <= pages:
                resp = self.http.get(
                    f"{API}/country/all/indicator/{code}",
                    params={"format": "json", "date": f"{start}:{end}",
                            "per_page": 20000, "page": page})
                if not resp:
                    break
                payload = resp.json()
                if not isinstance(payload, list) or len(payload) < 2:
                    break
                meta = payload[0] or {}
                pages = int(meta.get("pages", 1) or 1)
                records.extend(payload[1] or [])
                page += 1
            self.cache_raw(key, records)
            print(f"  worldbank {code}: {len(records)} records")
            yield {"code": code, "records": records}

    def normalize(self, raw_pages: Iterable[dict]) -> Iterator[Row]:
        as_of = now_iso()
        for page in raw_pages:
            code = page["code"]
            meta = INDICATORS.get(code)
            if not meta:
                continue
            url = f"https://data.worldbank.org/indicator/{code}"
            for rec in page["records"]:
                iso3 = rec.get("countryiso3code") or ""
                # skip aggregates (no 3-letter iso) and null values
                if len(iso3) != 3 or rec.get("value") is None:
                    continue
                year = rec.get("date")
                yield Row("observation", dict(
                    obs_id=make_obs_id("worldbank", iso3, code,
                                       meta["level"], year),
                    country_code=iso3,
                    indicator_code=code,
                    category=meta["category"],
                    level=meta["level"],
                    year=year,
                    value=rec.get("value"),
                    unit=meta["unit"],
                    source="worldbank",
                    source_id=code,
                    source_url=url,
                    as_of=as_of,
                ))

    def run(self, codes=None, start=2000, end=2024, **_) -> dict[str, int]:
        # countries first (dimension), then observations
        counts = self.emit(self.country_rows())
        pages = list(self.fetch(codes=codes, start=start, end=end))
        counts.update(self.emit(self.normalize(pages)))
        return counts


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
