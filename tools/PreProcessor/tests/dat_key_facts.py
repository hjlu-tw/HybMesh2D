"""Facts about the mesh ``.dat``'s key vocabulary that more than one gate needs.

Two gates ask the same question — ``test_field_spec_tables.py`` (is every key the
writer emits readable back?) and ``test_gui_cpp_config_parity.py`` (does every key the
GUI writes resolve to a C++ type and default?) — and both have to except the same four
keys for the same reason. That reason was written out twice and had already drifted
apart in wording within a day, with nothing comparing the copies. It is the duplication
this repo removes by deletion rather than by a rule, so it lives here once.
"""
from __future__ import annotations

#: Keys the GUI writes as STRUCTURAL lines: several tokens with their own parser, not
#: one value with a type and a default. Each carries the reason it cannot be compared
#: as a scalar, and both gates fail on a stale entry (one no longer written).
STRUCTURAL_KEYS = {
    "GEOM_FILE": "`GEOM_FILE <path> [bl|nobl] [KEY=VALUE ...]` — a list entry carrying "
                 "a role and per-geometry BL overrides, not one value",
    "DOMAIN_FILE": "the same shape for the custom domain outline",
    "SEED_FILE": "`SEED_FILE <path> [size|auto] [radius] <mode>` — positional tokens "
                 "parsed into one SeedSpec each",
    "GROUP_BC": "`GROUP_BC <label> <bc-type>` — one line per label, so it is a MAP "
                "rather than a field",
}
