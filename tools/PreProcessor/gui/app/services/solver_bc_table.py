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

**A name nothing can resolve is AUDIBLE, not refused** (#92). ``unresolved_patches``
answers which patches took ``default_bc_flag_for_name``'s tolerant wall fallback
instead of a real lookup, and ``unresolved_patch_warnings`` turns that into the
line both hosts log. The fallback itself is unchanged — refusing to solve because
a patch is named something unexpected would be worse — but it no longer happens
in silence, which is how a typo'd ``far-feild`` became a solid wall where the user
meant an outflow with nothing to show for it.

One asymmetry worth knowing before extending this: ``group_bc`` is keyed by the
per-segment grouping LABEL, while a ``.bnd`` patch name is the physical BC TYPE
the mesher resolved that label to (``src/Mesh.cpp``, ``Config::resolveGroupBc``).
The lookup here is by patch name, so it only ever fires where a label happens to
be named after its own type. That is the behaviour as it shipped and #90 keeps
it; it is not an endorsement of it.
"""
from __future__ import annotations

from app.models.solver_config import BC_FLAG_TO_LABEL
from app.services.bnd_io import default_bc_flag_for_name, is_known_bc_name


def bc_token_for_patch(name: str, group_bc: dict | None = None) -> str:
    """THE precedence rule, one copy: the token whose meaning decides this
    patch's BC — an explicit ``group_bc`` assignment for the patch name, else the
    patch name itself. An empty or missing assignment is not an assignment.

    Split out of ``bc_flag_for_patch`` by #92 so that asking "was it resolved?"
    and asking "what flag?" cannot answer about different tokens. Nothing else
    may re-derive it."""
    assigned = (group_bc or {}).get(name)
    return assigned if assigned else name


def bc_flag_for_patch(name: str, group_bc: dict | None = None,
                      euler: bool = False) -> int:
    """The solver BC flag for one boundary patch: ``bc_token_for_patch`` decides
    WHICH token is asked about, and ``default_bc_flag_for_name`` resolves it — so
    an assignment naming a token getPGrid does not know takes the same wall
    fallback as an unknown patch name, rather than reverting to the patch's own
    name."""
    return default_bc_flag_for_name(bc_token_for_patch(name, group_bc), euler)


def bc_definitions_for_patches(patches, group_bc: dict | None = None,
                               euler: bool = False) -> list[dict]:
    """``bc_definitions`` rows for ``[(seg_id, patch_name), ...]`` — one row per
    patch, in the order given, each with the flag ``bc_flag_for_patch`` decides
    and no extra value (only a handful of BC types take one, and none of them can
    be guessed from a patch).

    ``patches`` is not defaulted away: ``None`` raises here as it did inline,
    rather than being read as "no patches" — the one caller guards for that
    already, and a silent empty table is the wrong answer to a bug upstream. The
    one deliberate difference from the inline code it replaces: the rows are
    built BEFORE the panel clears its table, so a malformed patch list leaves the
    table as it was instead of half-filled."""
    return [{"segment_no": sid,
             "bc_type": bc_flag_for_patch(name, group_bc, euler),
             "values": "",
             "name": name}
            for sid, name in patches]


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
    out: dict[int, int] = {}
    for i, name in enumerate(names):
        if name is None:
            continue
        key = name.strip()
        if group_bc.get(key):
            out[i] = bc_flag_for_patch(key, group_bc, euler)
    return out


# The fix the warning below names. Both halves are real places in this GUI: the
# Mesh Generator's per-patch assignment (which travels into the mesh) and the
# solver panel's Boundary Conditions table (which does not, but overrides the
# guess for this run).
_UNRESOLVED_FIX = ("assign its type in the Mesh Generator (Edit segment BCs…), "
                   "or set it in the solver's Boundary Conditions table")


def unresolved_patches(patches, group_bc: dict | None = None,
                       euler: bool = False) -> list[tuple[str, str, int, list]]:
    """``[(patch_name, token, flag, [segment ids]), ...]`` for the patches whose
    BC could NOT be resolved — the ones that took the tolerant wall fallback
    (#92). One entry per distinct NAME, in first-appearance order.

    ``token`` is what was actually looked up (``bc_token_for_patch``), so a patch
    that failed because of an unrecognised Mesh-Generator ASSIGNMENT is
    distinguishable from one that failed on its own name. ``flag`` is the flag
    the run will really use, asked of ``bc_flag_for_patch`` rather than
    re-derived, so this can never name a flag the table does not carry.

    **Grouped by name rather than one entry per segment**, because a mesh names
    several segments the same on purpose — the shipped C-grid has four
    ``farfield`` patches — and four identical lines is the burial this ticket
    exists to undo. getPGrid already prints 288 of them on that run. The segment
    ids are kept so the line still says WHERE.

    Empty for a mesh whose names all resolve, which is what makes the warning
    mean something when it appears."""
    order: list[str] = []
    seen: dict[str, tuple[str, str, int, list]] = {}
    for sid, name in patches:
        token = bc_token_for_patch(name, group_bc)
        if is_known_bc_name(token):
            continue
        if name not in seen:
            order.append(name)
            seen[name] = (name, token, bc_flag_for_patch(name, group_bc, euler), [])
        seen[name][3].append(sid)
    return [seen[n] for n in order]


def unresolved_patch_warnings(patches, group_bc: dict | None = None,
                              euler: bool = False) -> list[str]:
    """One user-log line per unresolved patch NAME, naming the PATCH, the
    segments carrying it, the FLAG it fell back to and the fix — ready to hand
    to ``AppController.log`` or to a headless ``log=`` callback, so both hosts
    say the same words (#92).

    Empty when every patch resolved. The ``[WARNING]`` tag is what
    ``services/user_log.classify`` grades on; the wording deliberately avoids the
    words "error" and "failed", which that classifier would read as ERROR — this
    is a fallback the run survives, not a failure."""
    out = []
    for name, token, flag, sids in unresolved_patches(patches, group_bc, euler):
        shown = name or "(unnamed)"
        via = "" if token == name else f", assigned '{token}',"
        label = "segment" if len(sids) == 1 else "segments"
        where = f"{label} " + ", ".join(str(s) for s in sids)
        out.append(
            f"[Solver] [WARNING] Boundary patch '{shown}' ({where}){via} matches "
            f"no boundary condition this repo or getPGrid knows, so it falls "
            f"back to a solid wall — flag {flag}: "
            f"{BC_FLAG_TO_LABEL.get(flag, 'unknown')}. If that is not what you "
            f"meant, {_UNRESOLVED_FIX}.")
    return out
