"""World Bank connector normalize() tests -- the backbone source."""

from edu.connectors.worldbank import WorldBankConnector, _num


WB_PAGE = {
    "code": "SE.LPV.PRIM",
    "records": [
        {"countryiso3code": "IND", "date": "2020", "value": 46.9,
         "indicator": {"id": "SE.LPV.PRIM"}},
        {"countryiso3code": "NGA", "date": "2018", "value": 70.0,
         "indicator": {"id": "SE.LPV.PRIM"}},
        # 3-letter aggregate (SSF = Sub-Saharan Africa) -> KEPT (powers
        # regional comparison; filtered later in problem scoring by income_group)
        {"countryiso3code": "SSF", "date": "2020", "value": 86.0},
        # 2-letter code -> dropped (not a valid iso3)
        {"countryiso3code": "ZG", "date": "2020", "value": 80.0},
        # null value -> dropped (never coerced to 0)
        {"countryiso3code": "USA", "date": "2020", "value": None},
    ],
}


def test_normalize_keeps_iso3_drops_nonconforming(tmp_path):
    wb = WorldBankConnector(raw_dir=tmp_path / "raw",
                            processed_dir=tmp_path / "proc")
    rows = list(wb.normalize([WB_PAGE]))
    iso = {r.data["country_code"] for r in rows}
    assert iso == {"IND", "NGA", "SSF"}   # 2-letter + null dropped
    assert "ZG" not in iso and "USA" not in iso


def test_normalize_stamps_provenance_and_metadata(tmp_path):
    wb = WorldBankConnector(raw_dir=tmp_path / "raw",
                            processed_dir=tmp_path / "proc")
    r = next(iter(wb.normalize([WB_PAGE]))).data
    assert r["source"] == "worldbank"
    assert r["source_url"].startswith("https://data.worldbank.org/indicator/")
    assert r["as_of"]
    assert r["category"] == "learning"
    assert r["level"] == "primary"
    assert r["unit"] == "percent"


def test_normalize_skips_unknown_indicator(tmp_path):
    wb = WorldBankConnector(raw_dir=tmp_path / "raw",
                            processed_dir=tmp_path / "proc")
    rows = list(wb.normalize([{"code": "NOT.A.CODE", "records": WB_PAGE["records"]}]))
    assert rows == []


def test_num_helper():
    assert _num("3.14") == 3.14
    assert _num(None) is None
    assert _num("") is None


def test_emit_dedups_on_obs_id(tmp_path):
    wb = WorldBankConnector(raw_dir=tmp_path / "raw",
                            processed_dir=tmp_path / "proc")
    rows = list(wb.normalize([WB_PAGE]))
    wb.emit(rows)
    counts = wb.emit(rows)  # re-emit same rows -> converge, not duplicate
    assert counts["observation"] == 3
