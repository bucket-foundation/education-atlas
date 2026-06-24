# education-atlas

**A data-grounded map of educational problems in every country, at every level —
measured against the global standard (UN SDG 4).**

Bucket Foundation's mission is to reform education. Reform that is not grounded
in evidence is opinion. `education-atlas` is the evidence: it ingests the world's
authoritative education statistics into one normalized, validated, fully
provenanced dataset, then identifies — country by country, level by level — where
the actual problems are, scored against SDG 4 benchmarks, income-group peers, and
trend. Not LLM opinion: every number is a row traceable to its source.

> **The headline:** nearly half the world's children (48.3%) cannot read by age
> 10; 51M+ primary-age children and 61M adolescents are out of school; and world
> education spending (3.6% of GDP) sits *below* the agreed 4% floor, with 92 of
> 200 countries underfunding education. The deepest crisis is not access — it is
> **learning**. See [`docs/EDUCATION_PROBLEMS.md`](docs/EDUCATION_PROBLEMS.md).

---

## What's in the box

| | |
|---|---|
| **78,326** observations | one row per country × level × indicator × year |
| **219** countries + 79 World Bank aggregates | every UN member + regional/income aggregates |
| **30** indicators | across 9 SDG 4 problem categories + all education levels |
| **4** sources | World Bank EdStats, UNESCO UIS, Our World in Data, OECD PISA 2022 |
| **5,036** problem profiles | scored 0–100 severity per country × level × indicator |
| **1870–2024** | long-run attainment back to 1870; problem signal 2000–2024 |
| **14/14** validation checks | provenance, referential integrity, value sanity, uniqueness |

The published source of truth is `data/processed/*.parquet` + `data/MANIFEST.json`
(the CANON_INDEX). Heavy parquet is gitignored and rebuilt from raw; a small,
diverse [sample](data/processed/sample/) (25 countries across every income group)
ships in the repo so it's explorable without a build.

## Framework: UN SDG 4 (Quality Education)

Problems are organized by the global education-problem framework — the nine
SDG 4 / standard categories — across all ISCED education levels:

**Categories:** access · completion · learning outcomes · equity · financing ·
teachers · infrastructure · skills/NEET · digital divide · literacy
**Levels:** pre-primary · primary · lower-secondary · upper-secondary · tertiary ·
TVET · adult/lifelong literacy

The indicator-to-category-to-benchmark mapping (the domain knowledge — including
the SDG 4 / Incheon benchmarks each problem is scored against, with sourced
notes) lives in [`edu/indicators.py`](edu/indicators.py).

## Quickstart

```bash
pip install -r requirements.txt

python scripts/build_all.py        # ingest all sources -> parquet (idempotent, ~3 min)
python scripts/validate.py         # 14-check data-quality suite (gates publish)
python scripts/findings.py         # compute the headline global numbers
python scripts/build_db.py         # build a DuckDB query surface (optional)
python scripts/build_sample.py     # refresh the committed sample slice
python scripts/build_report_pdf.py # render the synthesis report to PDF

# explore
python scripts/query.py --problems NGA          # Nigeria's full problem profile
python scripts/query.py --worst learning 10     # 10 worst countries on learning
python scripts/query.py "SELECT category, round(avg(severity),1) FROM \
  read_parquet('data/processed/problem.parquet') GROUP BY 1 ORDER BY 2 DESC"
```

Re-running any step **converges** (idempotent): raw responses are cached under
`data/raw/`, and emit merges by primary key. Sources that fail (e.g. UNESCO
rate-limiting) are logged and skipped — World Bank is the backbone and must
succeed.

## Architecture

```
edu/
  schema.py        canonical tidy schema (observation fact + country/indicator
                   dimensions + derived problem table); provenance on every row
  indicators.py    the codebook: indicator -> category, level, unit, direction,
                   SDG 4 benchmark (with sourced note)
  connectors/
    base.py        Connector ABC: polite HTTP, cached raw, idempotent emit
    worldbank.py   World Bank EdStats -- the workhorse (enrollment, completion,
                   out-of-school, learning poverty, financing, teachers, NEET,
                   literacy, gender parity)
    unesco.py      UNESCO UIS -- SDG 4 custodian; school infrastructure & digital
                   (electricity / internet / water in schools); best-effort
    owid.py        Our World in Data -- long-run mean years of schooling
    oecd_pisa.py   OECD PISA 2022 learning-outcome scores (math/reading/science)
  problems.py      problem-scoring engine: gap vs benchmark + income-peer median
                   + trend -> 0-100 severity + flags
  manifest.py      writes data/MANIFEST.json (the published-dataset index)

scripts/           build_all · validate · findings · build_db · build_sample ·
                   build_report_pdf · query
tests/             37 tests: schema, codebook, every normalizer, problem scoring,
                   validation suite
docs/              EDUCATION_PROBLEMS.md (+ .pdf) · VALIDATION.md · findings.json
```

### Provenance & idempotency

Every observation carries `source`, `source_id`, `source_url`, and `as_of`. A row
without provenance is a bug the validator catches. Surrogate keys
(`obs_id = hash(source, country, indicator, level, year)`) are deterministic, so
re-ingesting the same record produces the same id — the basis for idempotent
merges. Unknown values are `null`, never silently `0`.

### Problem severity

For each `(country, indicator)` the engine takes the latest non-null value and
scores it (0–100) on three frames: **benchmark gap** (vs the SDG 4 / global
standard, dominant), **peer gap** (vs the median of World Bank income-group
peers), and **trend** (an adverse multi-year slope). Flags
(`below_benchmark | below_peers | worsening | gender_disparity`) make each score
explainable. World Bank regional/income aggregates are excluded from per-country
rankings.

## Honest limitations

Data sparsity is worst exactly where problems are worst: of 25 low-income
countries, only 11 have any learning-poverty data; conflict states report the
least. PISA covers 67 mostly-rich economies. And no global indicator captures
curriculum relevance, pedagogy (rote learning), credentialism, or corruption —
real problems flagged qualitatively in the report. Full discussion in
[`docs/EDUCATION_PROBLEMS.md` §5](docs/EDUCATION_PROBLEMS.md).

## Sources

- **World Bank EdStats** — `api.worldbank.org/v2` (CC-BY-4.0) — the backbone
- **UNESCO Institute for Statistics (UIS)** — `api.uis.unesco.org` — SDG 4 custodian
- **Our World in Data** — `ourworldindata.org` (CC-BY-4.0)
- **OECD PISA 2022 Results** — Volume I (curated country means, in-repo + cited)

## License

MIT (code) · CC-BY-4.0 (published datasets). See [`LICENSE`](LICENSE) and
[`NOTICE`](NOTICE). Citation metadata for a future Zenodo DOI in
[`.zenodo.json`](.zenodo.json).

---

_Bucket Foundation — grounding education reform in the record, not in conviction._
