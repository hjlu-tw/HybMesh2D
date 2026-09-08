"""Derive the solver BC table from the mesh's own boundary patches (#91).

Qt-free, and its own module for two reasons rather than one: `pipeline_runner`
was at the GUI tree's ~500-line limit, and this is a separate question from
sequencing subprocesses — the runner owns WHEN stages run, this owns WHAT
boundary conditions the solve is given when the script does not say.

The defect it closes: `services/solver_case.py` writes `<case>.bc.def` from
`SolverConfig.bc_definitions` when it has any, and otherwise copies the table
getPGrid wrote for itself. getPGrid's `getBCType` does not know the name
`farfield` and falls back to a NO-SLIP ADIABATIC WALL — deliberately, so a
free-form GUI patch label cannot crash the conversion, on the stated assumption
that "the physical BC type is assigned per segment in the solver BC table, which
overrides this default". Nothing headless ever assigned it, so that assumption
was false on exactly the path it was written for, and the shipped C-grid demo
solved a body in a CLOSED VISCOUS BOX: exit 0, 100 iterations, no NaN, a
plausible contour plot, and not one word said.

A GUI-authored `.hws` was never affected — it carries `project.solver_config`
wholesale — so the blast radius was the HAND-WRITTEN script: every file in
`config/pipeline/`, the documented headless entry points.

Rules and rationale: `.claude/rules/pipeline-case.md` and
`docs/design_notes/pipeline.md`. Gated by `tests/test_pipeline_bc_from_mesh.py`.
"""
from __future__ import annotations
import os

from app.services.bnd_io import read_bnd_segments
from app.services.solver_bc_table import bc_definitions_for_patches


def derive_bc_definitions(sc, group_bc: dict | None = None, log=print) -> int:
    """Fill an EMPTY solver BC table from the mesh's own boundary patches (#91).

    Returns the number of rows derived, 0 when it declines. It declines in
    exactly two cases, and both leave the pre-#91 behaviour untouched:

    * **The script states the table.** A declaration always wins — deriving fills
      a gap, it never overwrites an answer someone gave. This is what keeps a
      GUI-authored `.hws` (which carries `project.solver_config` wholesale, its
      `bc_definitions` included) behaving exactly as it did.
    * **There is nothing to derive FROM** — no `.bnd`, or one with no patches.
      `solver_case.stage_bc_def_companion` then copies getPGrid's own table, as
      it always has.

    Why this exists: `solver_case` writes `<case>.bc.def` from `bc_definitions`
    when it has any and otherwise copies the table getPGrid wrote for itself.
    getPGrid does not know the name `farfield` and defaults those patches to a
    NO-SLIP ADIABATIC WALL, so a hand-written script — every script in
    `config/pipeline/`, the documented headless entry points — solved a body in a
    closed viscous box while exiting 0 with a plausible contour plot. The GUI has
    always derived this; it did so inside a Qt panel until #90 gave the rule a
    home both hosts can call.
    """
    if sc.bc_definitions:
        return 0
    # Plain attribute access, not getattr with a default: both fields are
    # declared on SolverConfig, and a default would turn a rename into this
    # function silently returning 0 — the closed viscous box back, with not even
    # the log line below to show for it.
    patches = read_bnd_segments(sc.input_bnd_file or "")
    if not patches:
        return 0
    euler = sc.flow_solu_type == "euler_sol"
    sc.bc_definitions = bc_definitions_for_patches(patches, group_bc, euler)
    listing = ", ".join(f"{r['segment_no']}={r['name'] or '(unnamed)'}:{r['bc_type']}"
                        for r in sc.bc_definitions)
    log(f"[Solver] BC table derived from {os.path.basename(sc.input_bnd_file)} "
        f"({len(patches)} patch(es)): {listing}. The script stated none, and "
        "getPGrid's own table would call every name it does not know a wall.")
    return len(sc.bc_definitions)
