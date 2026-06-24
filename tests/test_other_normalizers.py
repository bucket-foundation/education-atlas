"""OWID, UNESCO, and OECD PISA connector normalize() tests."""

from edu.connectors.owid import OWIDConnector
from edu.connectors.unesco import UNESCOConnector
from edu.connectors.oecd_pisa import OECDPISAConnector


# ---- OWID ---- #
OWID_PAGE = {
    "code": "OWID.MYS", "col": 0,
    "rows": [
        ["Entity", "Code", "Year", "Average years of schooling"],
        ["Nigeria", "NGA", "2020", "7.2"],
        ["World", "OWID_WRL", "2020", "8.7"],   # non-iso3 -> dropped
        ["Mali", "MLI", "1990", "0.9"],
        ["Bad", "MLI", "abc", "x"],             # unparseable -> dropped
    ],
}


def test_owid_normalize_drops_nonconforming(tmp_path):
    o = OWIDConnector(raw_dir=tmp_path / "raw", processed_dir=tmp_path / "proc")
    rows = list(o.normalize([OWID_PAGE]))
    iso = sorted(r.data["country_code"] for r in rows)
    assert iso == ["MLI", "NGA"]
    for r in rows:
        assert r.data["source"] == "owid"
        assert r.data["unit"] == "years"
        assert r.data["category"] == "completion"


# ---- UNESCO ---- #
UIS_PAGE = {
    "code": "SCHBSP.1.WELEC",
    "records": [
        {"geoUnit": "KEN", "year": 2019, "value": 65.0},
        {"geoUnit": "IND", "year": 2016, "value": 47.4},
        {"geoUnit": "XYZ2", "year": 2019, "value": 1.0},  # bad iso -> dropped
        {"geoUnit": "USA", "year": 2019, "value": None},  # null -> dropped
    ],
}


def test_unesco_normalize(tmp_path):
    u = UNESCOConnector(raw_dir=tmp_path / "raw", processed_dir=tmp_path / "proc")
    rows = list(u.normalize([UIS_PAGE]))
    assert len(rows) == 2
    r = rows[0].data
    assert r["source"] == "unesco"
    assert r["category"] == "infrastructure"
    assert r["level"] == "primary"


# ---- OECD PISA ---- #
def test_pisa_emits_three_domains_per_country():
    p = OECDPISAConnector()
    rows = list(p.normalize(p.fetch()))
    # Singapore should appear with 3 rows (math, read, science)
    sgp = [r for r in rows if r.data["country_code"] == "SGP"]
    assert len(sgp) == 3
    codes = {r.data["indicator_code"] for r in sgp}
    assert codes == {"PISA.MATH", "PISA.READ", "PISA.SCIE"}
    for r in sgp:
        assert r.data["source"] == "oecd_pisa"
        assert r.data["unit"] == "score"
        assert r.data["level"] == "secondary"
        assert r.data["year"] == 2022


def test_pisa_skips_nonparticipants():
    p = OECDPISAConnector()
    rows = list(p.normalize(p.fetch()))
    assert not any(r.data["country_code"] == "IND" for r in rows)  # India n/a 2022
