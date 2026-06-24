"""The indicator codebook -- education-atlas's domain knowledge.

Maps each authoritative source indicator to its canonical metadata: the SDG4
problem ``category``, the education ``level`` it measures, its ``unit``,
``direction`` (whether higher or lower is better -- needed for problem scoring),
and a ``benchmark`` (the global standard / SDG 4 target) with a sourced note.

This is the single place that encodes "what good looks like" so problem
identification is data-grounded and explainable, not arbitrary.

Benchmark provenance
--------------------
- Universal access / completion targets (100%) come from SDG 4.1/4.2 (universal
  primary & secondary completion, universal pre-primary by 2030).
- Gender parity benchmark (GPI = 1.0) is SDG 4.5.
- Learning poverty benchmark (0%) and the "halve by 2030" framing come from the
  World Bank / UNESCO Learning Poverty definition (2019).
- Financing benchmarks (4-6% of GDP AND 15-20% of public expenditure) come from
  the Education 2030 Framework for Action (Incheon Declaration).
- PISA benchmark (OECD mean ~ 489 in math, 2022) and the low-performer share
  come from OECD PISA 2022.
- Pupil-teacher ratio benchmarks reflect UIS guidance (primary <= 40 flagged).
"""

from __future__ import annotations

# Each entry: code -> dict(name, category, level, unit, direction, benchmark,
#                          benchmark_note, source)
INDICATORS: dict[str, dict] = {

    # ---- ACCESS / ENROLLMENT (SDG 4.1, 4.2, 4.3) ------------------------- #
    "SE.PRE.ENRR": dict(
        name="Pre-primary gross enrollment ratio",
        category="access", level="pre_primary", unit="percent",
        direction="higher_better", benchmark=100.0,
        benchmark_note="SDG 4.2: universal access to quality pre-primary by 2030",
        source="worldbank"),
    "SE.PRM.NENR": dict(
        name="Primary net enrollment rate",
        category="access", level="primary", unit="percent",
        direction="higher_better", benchmark=100.0,
        benchmark_note="SDG 4.1: universal primary education",
        source="worldbank"),
    "SE.SEC.NENR": dict(
        name="Secondary net enrollment rate",
        category="access", level="secondary", unit="percent",
        direction="higher_better", benchmark=100.0,
        benchmark_note="SDG 4.1: universal secondary education",
        source="worldbank"),
    "SE.TER.ENRR": dict(
        name="Tertiary gross enrollment ratio",
        category="access", level="tertiary", unit="percent",
        direction="higher_better", benchmark=None,
        benchmark_note="SDG 4.3: equal access; no universal target (compared to peers)",
        source="worldbank"),
    "SE.PRM.UNER": dict(
        name="Children out of school, primary",
        category="access", level="primary", unit="count",
        direction="lower_better", benchmark=0.0,
        benchmark_note="SDG 4.1: zero out-of-school children",
        source="worldbank"),
    "UIS.OFST.2": dict(
        name="Adolescents out of school, lower secondary",
        category="access", level="lower_secondary", unit="count",
        direction="lower_better", benchmark=0.0,
        benchmark_note="SDG 4.1: zero out-of-school adolescents",
        source="worldbank"),

    # ---- COMPLETION / DROPOUT (SDG 4.1) ---------------------------------- #
    "SE.PRM.CMPT.ZS": dict(
        name="Primary completion rate",
        category="completion", level="primary", unit="percent",
        direction="higher_better", benchmark=100.0,
        benchmark_note="SDG 4.1: universal primary completion",
        source="worldbank"),
    "SE.SEC.CMPT.LO.ZS": dict(
        name="Lower-secondary completion rate",
        category="completion", level="lower_secondary", unit="percent",
        direction="higher_better", benchmark=100.0,
        benchmark_note="SDG 4.1: universal lower-secondary completion",
        source="worldbank"),
    "SE.PRM.PRSL.ZS": dict(
        name="Persistence to last grade of primary",
        category="completion", level="primary", unit="percent",
        direction="higher_better", benchmark=100.0,
        benchmark_note="SDG 4.1: all children reach the last primary grade",
        source="worldbank"),
    "SE.SEC.PROG.ZS": dict(
        name="Progression to secondary school",
        category="completion", level="secondary", unit="percent",
        direction="higher_better", benchmark=100.0,
        benchmark_note="universal transition primary -> secondary",
        source="worldbank"),

    # ---- LEARNING OUTCOMES / QUALITY (SDG 4.1.1) ------------------------- #
    "SE.LPV.PRIM": dict(
        name="Learning poverty (share unable to read by age 10)",
        category="learning", level="primary", unit="percent",
        direction="lower_better", benchmark=0.0,
        benchmark_note="World Bank/UNESCO 2019: target halve global LP by 2030; ideal 0",
        source="worldbank"),
    "HD.HCI.HLOS": dict(
        name="Harmonized test scores (Human Capital Index)",
        category="learning", level="all", unit="score",
        direction="higher_better", benchmark=625.0,
        benchmark_note="World Bank HCI: 625 = advanced attainment benchmark",
        source="worldbank"),
    "PISA.MATH": dict(
        name="PISA mathematics mean score (15-year-olds)",
        category="learning", level="secondary", unit="score",
        direction="higher_better", benchmark=489.0,
        benchmark_note="OECD PISA 2022 average (math) = 472; reference 489 (pre-COVID OECD mean)",
        source="oecd_pisa"),
    "PISA.READ": dict(
        name="PISA reading mean score (15-year-olds)",
        category="learning", level="secondary", unit="score",
        direction="higher_better", benchmark=476.0,
        benchmark_note="OECD PISA 2022 average (reading) = 476",
        source="oecd_pisa"),
    "PISA.SCIE": dict(
        name="PISA science mean score (15-year-olds)",
        category="learning", level="secondary", unit="score",
        direction="higher_better", benchmark=485.0,
        benchmark_note="OECD PISA 2022 average (science) = 485",
        source="oecd_pisa"),

    # ---- EQUITY (SDG 4.5) ------------------------------------------------ #
    "SE.ENR.PRIM.FM.ZS": dict(
        name="Gender parity index, primary enrollment",
        category="equity", level="primary", unit="index",
        direction="target_one", benchmark=1.0,
        benchmark_note="SDG 4.5: gender parity (GPI = 1.0)",
        source="worldbank"),
    "SE.ENR.SECO.FM.ZS": dict(
        name="Gender parity index, secondary enrollment",
        category="equity", level="secondary", unit="index",
        direction="target_one", benchmark=1.0,
        benchmark_note="SDG 4.5: gender parity (GPI = 1.0)",
        source="worldbank"),
    "SE.ENR.TERT.FM.ZS": dict(
        name="Gender parity index, tertiary enrollment",
        category="equity", level="tertiary", unit="index",
        direction="target_one", benchmark=1.0,
        benchmark_note="SDG 4.5: gender parity (GPI = 1.0)",
        source="worldbank"),

    # ---- FINANCING (SDG 4, means of implementation) --------------------- #
    "SE.XPD.TOTL.GD.ZS": dict(
        name="Government expenditure on education (% of GDP)",
        category="financing", level="all", unit="percent",
        direction="higher_better", benchmark=4.0,
        benchmark_note="Education 2030 / Incheon: 4-6% of GDP (4% = floor)",
        source="worldbank"),
    "SE.XPD.TOTL.GB.ZS": dict(
        name="Government expenditure on education (% of public spending)",
        category="financing", level="all", unit="percent",
        direction="higher_better", benchmark=15.0,
        benchmark_note="Education 2030 / Incheon: 15-20% of public expenditure (15% = floor)",
        source="worldbank"),

    # ---- TEACHERS (SDG 4.c) --------------------------------------------- #
    "SE.PRM.ENRL.TC.ZS": dict(
        name="Pupil-teacher ratio, primary",
        category="teachers", level="primary", unit="ratio",
        direction="lower_better", benchmark=40.0,
        benchmark_note="UIS: primary PTR > 40 flags teacher shortage; lower is better",
        source="worldbank"),
    "SE.SEC.ENRL.TC.ZS": dict(
        name="Pupil-teacher ratio, secondary",
        category="teachers", level="secondary", unit="ratio",
        direction="lower_better", benchmark=30.0,
        benchmark_note="UIS guidance: secondary PTR target ~30 or below",
        source="worldbank"),
    "SE.PRM.TCAQ.ZS": dict(
        name="Trained teachers in primary education (% of total)",
        category="teachers", level="primary", unit="percent",
        direction="higher_better", benchmark=100.0,
        benchmark_note="SDG 4.c: all teachers trained/qualified",
        source="worldbank"),

    # ---- SKILLS / NEET (SDG 4.4) ---------------------------------------- #
    "SL.UEM.NEET.ZS": dict(
        name="Youth not in education, employment or training (NEET)",
        category="skills", level="all", unit="percent",
        direction="lower_better", benchmark=0.0,
        benchmark_note="SDG 8.6 / 4.4: reduce youth NEET; lower is better",
        source="worldbank"),

    # ---- LITERACY (SDG 4.6) --------------------------------------------- #
    "SE.ADT.LITR.ZS": dict(
        name="Adult literacy rate (15+)",
        category="literacy", level="adult", unit="percent",
        direction="higher_better", benchmark=100.0,
        benchmark_note="SDG 4.6: universal youth & adult literacy by 2030",
        source="worldbank"),
    "SE.ADT.1524.LT.ZS": dict(
        name="Youth literacy rate (15-24)",
        category="literacy", level="adult", unit="percent",
        direction="higher_better", benchmark=100.0,
        benchmark_note="SDG 4.6: universal youth literacy by 2030",
        source="worldbank"),

    # ---- ATTAINMENT (Our World in Data, long-run) ----------------------- #
    "OWID.MYS": dict(
        name="Mean years of schooling (population 15+)",
        category="completion", level="all", unit="years",
        direction="higher_better", benchmark=12.0,
        benchmark_note="12 years = universal completion of basic+secondary education",
        source="owid"),

    # ---- INFRASTRUCTURE / DIGITAL (SDG 4.a) -- UNESCO UIS --------------- #
    "SCHBSP.1.WELEC": dict(
        name="Primary schools with access to electricity (%)",
        category="infrastructure", level="primary", unit="percent",
        direction="higher_better", benchmark=100.0,
        benchmark_note="SDG 4.a: all schools have basic services (electricity)",
        source="unesco"),
    "SCHBSP.1.WINTERN": dict(
        name="Primary schools with internet for pedagogy (%)",
        category="digital", level="primary", unit="percent",
        direction="higher_better", benchmark=100.0,
        benchmark_note="SDG 4.a: all schools have internet for pedagogical purposes",
        source="unesco"),
    "SCHBSP.1.WWATA": dict(
        name="Primary schools with basic drinking water (%)",
        category="infrastructure", level="primary", unit="percent",
        direction="higher_better", benchmark=100.0,
        benchmark_note="SDG 4.a: all schools have basic drinking water",
        source="unesco"),
}


def unesco_codes() -> list[str]:
    return [c for c, m in INDICATORS.items() if m["source"] == "unesco"]


def pisa_codes() -> list[str]:
    return [c for c, m in INDICATORS.items() if m["source"] == "oecd_pisa"]


def codebook_rows(as_of: str) -> list[dict]:
    """Materialize the codebook as indicator-table rows."""
    rows = []
    for code, m in INDICATORS.items():
        rows.append(dict(
            indicator_code=code,
            name=m["name"],
            category=m["category"],
            level=m["level"],
            unit=m["unit"],
            direction=m["direction"],
            benchmark=m["benchmark"],
            benchmark_note=m["benchmark_note"],
            description=m["name"],
            source=m["source"],
        ))
    return rows


def worldbank_codes() -> list[str]:
    return [c for c, m in INDICATORS.items() if m["source"] == "worldbank"]
