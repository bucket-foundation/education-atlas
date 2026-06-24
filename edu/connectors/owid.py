"""Our World in Data (OWID) connector -- clean long-run education series.

OWID publishes every grapher chart as a tidy CSV at
``https://ourworldindata.org/grapher/<slug>.csv?csvType=full`` with the columns
``Entity, Code, Year, <value...>``. We use it for series the World Bank doesn't
expose as cleanly -- notably long-run **mean years of schooling**, an attainment
measure that complements the WB enrollment/completion flow.

OWID slugs are not perfectly stable; a 404 is handled gracefully (the connector
logs and skips, rather than failing the build). This keeps OWID an additive,
best-effort source on top of the World Bank backbone.

Provenance: ``source="owid"``, ``source_id=<slug>``, ``source_url`` = the OWID
grapher page (citeable; OWID republishes underlying sources, themselves cited
on the page).
"""

from __future__ import annotations

import csv
import io
from typing import Iterable, Iterator

from edu.connectors.base import Connector
from edu.indicators import INDICATORS
from edu.schema import Row, make_obs_id, now_iso

GRAPHER = "https://ourworldindata.org/grapher"

# canonical indicator code -> (OWID slug, value-column index 0-based after Year)
SLUGS = {
    "OWID.MYS": ("mean-years-of-schooling-long-run", 0),
}


class OWIDConnector(Connector):
    source = "owid"

    def fetch(self, **_) -> Iterable[dict]:
        for code, (slug, col) in SLUGS.items():
            key = slug
            if self.has_raw(key):
                yield {"code": code, "col": col, "rows": self.load_raw(key)}
                continue
            resp = self.http.get(f"{GRAPHER}/{slug}.csv",
                                 params={"csvType": "full"})
            if not resp or resp.status_code != 200:
                print(f"  owid {slug}: unavailable (skipping, best-effort source)")
                self.cache_raw(key, [])
                yield {"code": code, "col": col, "rows": []}
                continue
            reader = csv.reader(io.StringIO(resp.text))
            rows = list(reader)
            self.cache_raw(key, rows)
            print(f"  owid {slug}: {len(rows)-1} rows")
            yield {"code": code, "col": col, "rows": rows}

    def normalize(self, raw_pages: Iterable[dict]) -> Iterator[Row]:
        as_of = now_iso()
        for page in raw_pages:
            code, col, rows = page["code"], page["col"], page["rows"]
            meta = INDICATORS.get(code)
            if not meta or not rows:
                continue
            slug = SLUGS[code][0]
            url = f"{GRAPHER}/{slug}"
            for r in rows[1:]:  # skip header
                if len(r) < 4:
                    continue
                iso3 = r[1].strip()
                if len(iso3) != 3:  # skip continents/world/regions w/o iso3
                    continue
                try:
                    year = int(r[2])
                    value = float(r[3 + col])
                except (ValueError, IndexError):
                    continue
                yield Row("observation", dict(
                    obs_id=make_obs_id("owid", iso3, code, meta["level"], year),
                    country_code=iso3,
                    indicator_code=code,
                    category=meta["category"],
                    level=meta["level"],
                    year=year,
                    value=value,
                    unit=meta["unit"],
                    source="owid",
                    source_id=slug,
                    source_url=url,
                    as_of=as_of,
                ))
