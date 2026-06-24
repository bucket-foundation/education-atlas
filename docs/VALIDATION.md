# education-atlas -- validation report

_Generated 2026-06-24T23:11:21Z_

Invariants asserted on the published parquet. Hard checks gate publishing; soft checks are advisory coverage signals.

| check | type | result | detail |
|---|---|---|---|
| provenance present on every observation | hard | PASS | 0 rows missing provenance |
| country referential integrity | hard | PASS | 0 observations with unknown country_code |
| indicator referential integrity | hard | PASS | 0 observations with unknown indicator_code |
| percent in [0,100] (gross/completion <=300) | hard | PASS | 0 percent values out of range |
| counts non-negative | hard | PASS | 0 negative counts |
| pupil-teacher ratios in (0,200] | hard | PASS | 0 implausible ratios |
| obs_id unique | hard | PASS | 0 duplicate obs_id |
| country_code unique | hard | PASS | 0 duplicate countries |
| category in domain | hard | PASS | 0 bad categories |
| level in domain | hard | PASS | 0 bad levels |
| year plausible (1820-2030) | hard | PASS | 0 implausible years |
| multiple sources contribute | soft | PASS | 4 distinct sources |
| dataset non-empty | soft | PASS | 78,326 obs / 298 countries / 30 indicators / 5,036 problems |
| indicator country-coverage >= 30 (soft) | soft | PASS | 0 indicators cover <30 countries |

**14/14 checks passed; 0 hard failure(s).**
