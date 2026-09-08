"""Derive the solver's boundary-condition table from a mesh's boundary patches.

Qt-free, so both hosts can ask the question: the GUI's solver panel, which shows
the answer as a table of widgets, and anything headless that needs the same rows
without one. The rows are ``SolverConfig.bc_definitions`` rows exactly —
``{"segment_no", "bc_type", "values", "name"}`` — which ``services/solver_case.py``
writes into the solver's ``.bc.def`` for the GUI worker and the pipeline runner
alike.

This is the derivation that used to live inside ``views/panels/solver_config_bc_mixin.py``
(#90). Everything else in the chain was already a service: ``bnd_io.read_bnd_segments``
reads the ``(segment id, patch name)`` pairs out of the generated ``.bnd``, and
``bnd_io.default_bc_flag_for_name`` mirrors getPGrid's ``getBCType`` name→flag
mapping. Only the rule that USES them was a widget.

**The precedence rule is stated once, in ``bc_flag_for_patch``**: an explicit
per-patch assignment made in the Mesh Generator (``group_bc[name]``) beats the
guess from the patch name, and either way the answer goes through
``default_bc_flag_for_name`` — so an assignment naming a token getPGrid does not
know falls back the same way an unknown patch name does, rather than quietly
reverting to the patch's own name. An empty or missing assignment is not an
assignment. The patch name is preserved on the row regardless, because it is the
grouping LABEL the user set upstream.

One asymmetry worth knowing before extending this: ``group_bc`` is keyed by the
per-segment grouping LABEL, while a ``.bnd`` patch name is the physical BC TYPE
the mesher resolved that label to (``src/Mesh.cpp``, ``Config::resolveGroupBc``).
The lookup here is by patch name, so it only ever fires where a label happens to
be named after its own type. That is the behaviour as it shipped and #90 keeps
it; it is not an endorsement of it.
"""
from __future__ import annotations

from app.services.bnd_io import default_bc_flag_for_name


def bc_flag_for_patch(name: str, group_bc: dict | None = None,
                      euler: bool = False) -> int:
    """The solver BC flag for one boundary patch. THE precedence rule, one copy:
    an explicit ``group_bc`` assignment for this patch name wins over guessing
    from the name itself; both are resolved by ``default_bc_flag_for_name``."""
    assigned = (group_bc or {}).get(name)
    return default_bc_flag_for_name(assigned if assigned else name, euler)


def bc_definitions_for_patches(patches, group_bc: dict | None = None,
                               euler: bool = False) -> list[dict]:
    """``bc_definitions`` rows for ``[(seg_id, patch_name), ...]`` — one row per
    patch, in the order given, each with the flag ``bc_flag_for_patch`` decides
    and no extra value (only a handful of BC types take one, and none of them can
    be guessed from a patch)."""
    return [{"segment_no": sid,
             "bc_type": bc_flag_for_patch(name, group_bc, euler),
             "values": "",
             "name": name}
            for sid, name in patches or []]


def bc_flag_overrides(names, group_bc: dict | None = None,
                      euler: bool = False) -> dict[int, int]:
    """``{row index: flag}`` for the rows an already-built table should adopt from
    the CURRENT Mesh-Generator assignments.

    Only patches carrying an explicit assignment appear, which is the whole point:
    a row for a patch nobody assigned keeps whatever it is showing, so a manual
    tweak in the solver table is not overwritten by a guess from the name.

    ``None`` in ``names`` is a row with no name CELL at all (the caller found no
    item there), and is skipped without a lookup — distinct from ``""``, a row
    whose patch really is unnamed."""
    group_bc = group_bc or {}
    if not group_bc:
        return {}
    out: dict[int, int] = {}
    for i, name in enumerate(names or []):
        if name is None:
            continue
        key = name.strip()
        if group_bc.get(key):
            out[i] = bc_flag_for_patch(key, group_bc, euler)
    return out
