"""The constructed Age x Knowledge-depth grid -- the single source of truth.

Two constructed axes used across every script in this landscape analysis. They
are NOT measured by any authoritative source; they are an analytical frame this
project defines, and they are documented here so the construction is explicit.

AGE / LIFE-STAGE (X) -- 5 bins keyed to the schooling system:
    0-5    early childhood (pre-primary, ISCED 0)
    5-18   K-12 school age (primary + secondary, ISCED 1-3)
    18-22  traditional tertiary age (undergraduate, ISCED 6)
    22-65  working-age adult (graduate/professional + lifelong, ISCED 7-8)
    65+    later life

KNOWLEDGE DEPTH (Y) -- 6 levels, a constructed ladder of how deep into a body
of knowledge a person can go. Mapped, where possible, to ISCED and to a
real, measurable access proxy:
    L0 basic literacy/numeracy        -> adult literacy           (real)
    L1 K-12 / secondary               -> secondary net enrollment (real)
    L2 undergraduate                  -> tertiary gross enrollment(real)
    L3 graduate / professional        -> tertiary * grad-share    (real * est)
    L4 frontier / primary research    -> researchers-per-million  (real, UNESCO)
    L5 producing new knowledge        -> active publishing share  (real * est)

L4 and L5 are deliberately split: L4 = *reaching* the frontier (being a
researcher / reading primary literature); L5 = *adding to it* (publishing,
producing new knowledge). The data shows them as nearly the same tiny sliver.
"""

from __future__ import annotations

# --- X axis: age / life-stage bins ----------------------------------------- #
AGE_BINS = ["0-5", "5-18", "18-22", "22-65", "65+"]
AGE_LABELS = {
    "0-5":   "0-5\nearly childhood",
    "5-18":  "5-18\nK-12 age",
    "18-22": "18-22\nundergrad age",
    "22-65": "22-65\nworking adult",
    "65+":   "65+\nlater life",
}

# --- Y axis: knowledge-depth ladder ---------------------------------------- #
DEPTH_LEVELS = ["L0", "L1", "L2", "L3", "L4", "L5"]
DEPTH_LABELS = {
    "L0": "L0 basic literacy",
    "L1": "L1 K-12 / secondary",
    "L2": "L2 undergraduate",
    "L3": "L3 graduate / prof",
    "L4": "L4 frontier (read primary research)",
    "L5": "L5 producing new knowledge",
}

# Which life-stage(s) a depth level is normally *reached during*. Used to gate
# the age x depth surface: you cannot be at undergrad depth at age 3. A cell
# outside a level's reachable age window is structurally N/A (greyed out), not
# zero-access. 1 = age-appropriate / open, 0 = structurally not-yet/closed.
# (65+ kept open for L0-L4: lifelong access; L5 production tapers in retirement.)
AGE_DEPTH_OPEN = {
    #          0-5  5-18 18-22 22-65 65+
    "L0":     [1,   1,   1,    1,    1],
    "L1":     [0,   1,   1,    1,    1],
    "L2":     [0,   0,   1,    1,    1],
    "L3":     [0,   0,   0,    1,    1],
    "L4":     [0,   0,   1,    1,    1],
    "L5":     [0,   0,   0,    1,    1],
}

INCOME_TIERS = [
    "High income",
    "Upper middle income",
    "Lower middle income",
    "Low income",
]
INCOME_SHORT = {
    "High income": "High",
    "Upper middle income": "Upper-mid",
    "Lower middle income": "Lower-mid",
    "Low income": "Low",
}
