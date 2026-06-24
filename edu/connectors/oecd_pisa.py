"""OECD PISA connector -- learning-outcome scores (15-year-olds).

PISA (Programme for International Student Assessment) is the gold-standard
international learning-outcome measure. The OECD distributes the full
micro-data and an SDMX API, but both are heavy and the SDMX surface is unstable
for an automated build. For a reproducible, citeable backbone we ship the
**published PISA 2022 country mean scores** (mathematics, reading, science) as a
curated in-repo table sourced from the OECD PISA 2022 Results (Volume I,
Annex B1, Tables I.B1.2.1-3). This is the same approach the OECD itself uses for
its headline league tables.

Each score is a country mean for the 2022 cycle. Direction is higher-better;
the codebook benchmark is the OECD average per domain.

Provenance: ``source="oecd_pisa"``, ``source_id=PISA2022``, ``source_url`` =
the OECD PISA 2022 results page.

To refresh with a future cycle, add a new dict to ``PISA_SCORES`` keyed by the
cycle year; the connector is otherwise unchanged.
"""

from __future__ import annotations

from typing import Iterable, Iterator

from edu.schema import Row, make_obs_id, now_iso

PISA_URL = "https://www.oecd.org/en/about/programmes/pisa/pisa-2022-results.html"
CYCLE = 2022

# country_iso3 -> (math, reading, science) PISA 2022 mean scores.
# Source: OECD, "PISA 2022 Results (Volume I)", Annex B1. Values are published
# country means. Selected coverage of major + diverse systems (80 economies
# participated in 2022; this is a representative, fully-sourced subset).
PISA_SCORES = {
    "SGP": (575, 543, 561), "JPN": (536, 516, 547), "KOR": (527, 515, 528),
    "EST": (510, 511, 526), "CHE": (508, 483, 503), "CAN": (497, 507, 515),
    "NLD": (493, 459, 488), "IRL": (492, 516, 504), "BEL": (489, 479, 491),
    "DNK": (489, 489, 494), "GBR": (489, 494, 500), "POL": (489, 489, 499),
    "AUS": (487, 498, 507), "FIN": (484, 490, 511), "DEU": (475, 480, 492),
    "FRA": (474, 474, 487), "PRT": (472, 477, 484), "AUT": (487, 480, 491),
    "NZL": (479, 501, 504), "SWE": (482, 487, 494), "CZE": (487, 489, 498),
    "NOR": (468, 477, 478), "USA": (465, 504, 499), "ITA": (471, 482, 477),
    "ESP": (473, 474, 485), "HUN": (473, 476, 486), "ISR": (458, 474, 465),
    "GRC": (430, 438, 441), "CHL": (412, 448, 444), "URY": (409, 430, 435),
    "MEX": (395, 415, 410), "CRI": (385, 415, 411), "COL": (383, 409, 411),
    "BRA": (379, 410, 403), "PER": (391, 408, 408), "ARG": (378, 401, 406),
    "IDN": (366, 359, 383), "MAR": (365, 339, 365), "PHL": (355, 347, 356),
    "DOM": (339, 351, 360), "KHM": (336, 329, 347), "JOR": (361, 342, 375),
    "QAT": (414, 419, 432), "ARE": (431, 417, 432), "SAU": (389, 383, 390),
    "THA": (394, 379, 409), "VNM": (469, 462, 472), "TUR": (453, 456, 476),
    "MYS": (409, 388, 416), "KAZ": (425, 386, 423), "GEO": (390, 374, 384),
    "ALB": (368, 358, 376), "MNG": (425, 378, 412), "ROU": (428, 428, 438),
    "BGR": (417, 404, 421), "SRB": (440, 440, 447), "HRV": (463, 475, 483),
    "SVK": (464, 447, 462), "SVN": (485, 469, 500), "LTU": (475, 472, 484),
    "LVA": (483, 472, 494), "ISL": (459, 436, 447), "LUX": (470, 470, 477),
    "MLT": (466, 445, 466), "CYP": (418, 424, 411), "MDA": (414, 411, 417),
    "UKR": (441, 428, 450), "IND": None,  # India did not participate in 2022
}


class OECDPISAConnector:
    """Not an HTTP connector -- emits the curated, sourced PISA table.

    Kept structurally parallel to the other connectors (``run`` -> per-table
    counts) so the orchestrator treats every source uniformly.
    """

    source = "oecd_pisa"

    def __init__(self, processed_dir=None):
        from edu.connectors.base import DATA_PROCESSED
        self.processed_dir = processed_dir or DATA_PROCESSED

    def fetch(self, **_) -> Iterable[dict]:
        yield {"cycle": CYCLE, "scores": PISA_SCORES}

    def normalize(self, raw_pages: Iterable[dict]) -> Iterator[Row]:
        as_of = now_iso()
        domains = [("PISA.MATH", 0), ("PISA.READ", 1), ("PISA.SCIE", 2)]
        for page in raw_pages:
            for iso3, scores in page["scores"].items():
                if scores is None:
                    continue
                for code, idx in domains:
                    yield Row("observation", dict(
                        obs_id=make_obs_id("oecd_pisa", iso3, code,
                                           "secondary", page["cycle"]),
                        country_code=iso3,
                        indicator_code=code,
                        category="learning",
                        level="secondary",
                        year=page["cycle"],
                        value=float(scores[idx]),
                        unit="score",
                        source="oecd_pisa",
                        source_id="PISA2022",
                        source_url=PISA_URL,
                        as_of=as_of,
                    ))

    def emit(self, rows):
        from edu.connectors.base import Connector
        return Connector.emit(self, rows)  # reuse the merge logic

    def run(self, **_) -> dict[str, int]:
        return self.emit(self.normalize(self.fetch()))
