"""Does the mesh in hand actually carry the boundary conditions the model asks for?

USER-REPORTED (2026-08-11): "I updated the STAR-CD file's boundary conditions
and the solver still gives the same result." It did — the grid it ran on was
every patch `wall`. The per-segment BCs had been re-applied AFTER that mesh was
generated, and nothing between the edit and the solve looks at whether the two
agree: Export Star-CD copies whatever mesh is in hand, Send to Solver links it,
and the solver runs it. The mesher's own "NO boundary segment carries any of the
GROUP_BC label(s)" warning fires at MESH time, which is one step too early to
stop a stale grid being shipped.

Two independent things go wrong, so both are checked here:

* **Content** — a BC type the model assigns (inlet, outlet, symp, …) has no
  patch of that name in the ``.bnd``. The mesher writes the RESOLVED BC type as
  the patch name, so a type that is asked for and absent means the assignment
  did not reach this mesh at all. This is the loud case: every patch reads
  `wall` and the solver quietly runs a sealed box.
* **Age** — a geometry's ``.meta`` (which is where a per-segment BC or a No-BL
  flag is stored) is newer than the mesh. Then the mesh predates the edit even
  if the type happens to appear elsewhere in it — changing segment 2 from inlet
  to outlet leaves both names in the file, so content alone cannot see it.

Qt-free on purpose: the GUI shows the returned lines in a dialog, and the test
calls the same function with files on disk.
"""
from __future__ import annotations
import os

from app.services.bnd_io import read_bnd_segments
from app.services.meta_io import meta_path_for, read_meta_group_bc, read_meta_segments


def expected_bc_types(geom_files, group_bc: dict | None = None) -> dict[str, list[str]]:
    """``{bc_type: [label, ...]}`` the CURRENT geometry sidecars ask for.

    A per-segment BC is two halves: the LABEL sits in the ``.meta`` NSEGMENTS bc
    column, the label→type map in ``group_bc`` (the live Mesh-Generator state)
    with the ``.meta`` trailer as the persisted fallback. Only labels that are
    actually carried by a segment count — a map entry whose label no longer
    exists resolves to nothing at mesh time and must not be demanded of the mesh.
    """
    live = dict(group_bc or {})
    out: dict[str, list[str]] = {}
    for path in geom_files or []:
        labels = [bc for _sid, bc, _kind in read_meta_segments(path) if bc]
        if not labels:
            continue
        persisted = read_meta_group_bc(path)
        for label in labels:
            bc = live.get(label) or persisted.get(label)
            if not bc:
                continue
            out.setdefault(bc.strip().lower(), []).append(label)
    return out


def mesh_bc_gap(bnd_path: str, geom_files, group_bc: dict | None = None) -> list[str]:
    """BC types the model assigns that NO patch in ``bnd_path`` is named after.

    Empty when the mesh carries them (or when nothing is assigned / the .bnd is
    unreadable — this reports a mismatch it can see, never a guess)."""
    expected = expected_bc_types(geom_files, group_bc)
    if not expected:
        return []
    segs = read_bnd_segments(bnd_path)
    if not segs:
        return []
    present = {(name or "").strip().lower() for _sid, name in segs}
    return sorted(bc for bc in expected if bc not in present)


def stale_meta_files(bnd_path: str, geom_files) -> list[str]:
    """Geometry ``.meta`` sidecars modified AFTER the mesh was written.

    ``.meta`` is where the mesh-stage per-segment edits live (BC label, No-BL
    flag), so a newer sidecar means the mesh in hand predates them."""
    try:
        mesh_mtime = os.path.getmtime(bnd_path)
    except OSError:
        return []
    out = []
    for path in geom_files or []:
        meta = meta_path_for(path)
        try:
            if os.path.getmtime(meta) > mesh_mtime:
                out.append(meta)
        except OSError:
            continue
    return out


def audit_mesh_bc(bnd_path: str, geom_files, group_bc: dict | None = None) -> list[str]:
    """Human-readable reasons this mesh does not match the model's BC state.

    Empty list = the mesh is consistent with what the user assigned. Each line
    is written to be shown verbatim in a log line or a dialog.
    """
    problems: list[str] = []
    missing = mesh_bc_gap(bnd_path, geom_files, group_bc)
    if missing:
        problems.append(
            "This mesh has no boundary patch named "
            + ", ".join(missing)
            + " — the per-segment BC(s) you assigned are NOT in it, so the "
              "solver will treat those boundaries as the wall default.")
    stale = stale_meta_files(bnd_path, geom_files)
    if stale:
        problems.append(
            "The mesh was generated before the latest per-segment edit in "
            + ", ".join(os.path.basename(p) for p in stale)
            + ".")
    if problems:
        problems.append(
            "Regenerate the mesh (Mesh ▸ Generate) so the boundary conditions "
            "reach the grid, then send it to the solver again.")
    return problems
