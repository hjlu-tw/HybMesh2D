"""Which STAR-CD grid does this case actually run on? (Qt-free.)

The solver reads a ``(.vrt, .cel, .bnd)`` triple, and three different places can
supply it. Picking between them is not a detail: the answer decides both what
getPGrid converts and which ``.bnd`` the BC table is built from, so the run and
the table have to ask the same question and get the same answer.
"""
from __future__ import annotations
import os

_EXTS = (".vrt", ".cel", ".bnd")


def trio_for(base: str) -> tuple[str, str, str]:
    """The ``(.vrt, .cel, .bnd)`` beside an extension-less ``base``."""
    return (base + _EXTS[0], base + _EXTS[1], base + _EXTS[2])


def trio_for_mesh(path: str) -> tuple[str, str, str]:
    """The STAR-CD triple that belongs to a mesh output path (usually a ``.vtk``)."""
    return trio_for(os.path.splitext(path)[0])


def resolve_case_grid(session_mesh: str, wired, exported_mesh: str):
    """``(trio, note, tried)`` — the grid a case will use.

    ``trio`` is the first candidate whose three files all exist, ``note`` says
    where it came from (for the log), and ``tried`` describes each candidate that
    fell short so a failure can name what was looked for. ``trio`` is None when
    the case has no complete grid anywhere.

    Candidates, freshest first:

    1. ``session_mesh`` — the mesh this GUI session generated. Only reachable
       INSIDE that session: Generate Mesh writes its output into the GUI's temp
       dir on purpose (``<temp>/global_mesh.*``, so generating does not litter the
       repo — the stable per-case files appear on Export / Send to Solver) and
       that directory is removed on exit.
    2. ``wired`` — the triple the case already carries. A reopened workspace
       restores these, which is why they must be tried before any guess: the
       workspace records what the user last actually sent to the solver.
    3. ``exported_mesh`` — the per-case mesh path derived from the mesh config,
       i.e. where Export / Send to Solver writes it.

    Without (2) and (3) a reopened workspace always arrived with an empty
    ``session_mesh`` and auto-link answered "No mesh generated yet" for a case
    whose grid was sitting on disk. USER-REPORTED (2026-08-13).
    """
    cands = []
    if session_mesh:
        cands.append((trio_for_mesh(session_mesh), "this session's generated mesh"))
    wired = tuple(p or "" for p in (wired or ("", "", "")))
    if len(wired) == 3 and all(wired):
        cands.append((wired, "the grid this case is already wired to"))
    if exported_mesh:
        cands.append((trio_for_mesh(exported_mesh), "the mesh exported for this case"))

    tried, seen = [], set()
    for trio, note in cands:
        if trio in seen:
            continue
        seen.add(trio)
        missing = [p for p in trio if not os.path.exists(p)]
        if not missing:
            return trio, note, tried
        stem = os.path.splitext(trio[0])[0]
        tried.append(f"{stem}.{{vrt,cel,bnd}} (missing "
                     + ", ".join(os.path.splitext(m)[1] for m in missing) + ")")
    return None, "", tried
