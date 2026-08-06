#!/usr/bin/env python3
"""Regression tests for finding N6 — undo scope.

Two defects:

1. **Undo was per-CAD-tab.** The stack lived on ``GeometrySession``, so switching
   tabs silently switched history and Ctrl+Z could not reach the edit the user had
   just made elsewhere. Histories stay per-session (so closing a tab drops exactly
   its own commands), but every command now carries a global sequence number and
   undo/redo pick the genuinely most recent action across all of them — raising the
   owning tab first, because undoing something invisible is worse than not undoing.

2. **Mesh / Solver / IB edits were not undoable at all**, even though the user's
   mental model is one global Ctrl+Z. They are now recorded by snapshot diffing on
   a debounce, so a burst of typing is ONE undo step.

Checks:
 1. CommandHistory stamps a strictly increasing seq and can peek both ends.
 2. Entering a stage / loading config (a programmatic push) records nothing.
 3. A Mesh edit is undoable and redoable, returning to the value that was visible.
 4. Solver and IB edits likewise, each labelled by section.
 5. A burst of edits coalesces into one undo step.
 6. Undo/redo run in true chronological order across tabs AND project settings.
 7. Undo raises the tab that owns the command.
 8. Redo mirrors undo exactly (last undone is first redone).
 9. Closing a tab drops only that tab's history; the rest still undo.
10. The toolbar buttons reflect every history, not just the active session's.
11. Undo flushes a pending (still-debouncing) edit first, so Ctrl+Z right after
    typing does not skip past it.
12. Applying an undo does not re-record itself as a new edit.

Run:  python3 tools/PreProcessor/tests/test_global_undo.py
"""
import os
import sys
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >120s (modal dialog?)", flush=True)
    os._exit(99)


_wd = threading.Timer(120, _watchdog)
_wd.daemon = True
_wd.start()

# ── 1. sequence stamping ──────────────────────────────────────────────────
from app.commands.base import BaseCommand, CommandHistory  # noqa: E402


class _Noop(BaseCommand):
    def __init__(self, tag):
        self.tag = tag

    def execute(self):
        pass

    def undo(self):
        pass

    def description(self):
        return self.tag


h1, h2 = CommandHistory(), CommandHistory()
check(h1.peek_undo_seq() is None and h1.peek_redo_seq() is None,
      "1. an empty history peeks as None at both ends")
h1.execute(_Noop("a"))
h2.execute(_Noop("b"))
h1.execute(_Noop("c"))
s_a, s_b, s_c = (h1._undo_stack[0].seq, h2._undo_stack[0].seq, h1._undo_stack[1].seq)
check(s_a < s_b < s_c,
      f"1. seq increases across separate histories ({s_a} < {s_b} < {s_c})")
check(h1.peek_undo_seq() == s_c, "1. peek_undo_seq is the top of the undo stack")
h1.undo()
check(h1.peek_redo_seq() == s_c and h1.peek_undo_seq() == s_a,
      "1. after undo, the command is peekable on the redo side")

# ── GUI-scope checks ──────────────────────────────────────────────────────
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from app.commands.segment_cmds_core import UpdateParamsCmd  # noqa: E402
from app.controller import AppController  # noqa: E402

ctl = AppController()
mesh_panel = ctl.main_window.mesh_config_panel


def steps():
    return len(ctl.project_history._undo_stack)


# ── 2. a programmatic push records nothing ────────────────────────────────
before_steps = steps()
ctl.main_window.mode_combo.setCurrentIndex(1)      # enters the Mesh stage
ctl.flush_project_snapshot()
check(steps() == before_steps,
      f"2. entering the Mesh stage records no undo step ({steps() - before_steps})")
ctl.push_panel_config(mesh_panel, ctl.global_mesh_config)
ctl.flush_project_snapshot()
check(steps() == before_steps,
      "2. push_panel_config records no undo step either")

# ── 3. a Mesh edit is undoable ────────────────────────────────────────────
base_layers = mesh_panel.get_config().bl_layers
mesh_panel.bl_layers.setValue(base_layers + 12)
check(ctl.flush_project_snapshot(), "3. a Mesh edit is recorded")
ctl.undo()
check(mesh_panel.get_config().bl_layers == base_layers,
      f"3. undo restores the previously VISIBLE value ({mesh_panel.get_config().bl_layers})")
ctl.redo()
check(mesh_panel.get_config().bl_layers == base_layers + 12,
      "3. redo re-applies it")
check(ctl.project_history._undo_stack[-1].description() == "Mesh settings",
      "3. the step is labelled by section")

# A scientific-notation field (domain box) must be covered too — those are the
# ones the panel's own mesh_config_changed signal does not fire for.
ctl.flush_project_snapshot()
base_x = mesh_panel.get_config().domain_x_min
mesh_panel.domain_x_min.setValue(-2.5e-3)
check(ctl.flush_project_snapshot(), "3. a domain-box edit is recorded")
ctl.undo()
check(abs(mesh_panel.get_config().domain_x_min - base_x) < 1e-12,
      "3. ...and undoes to the prior coordinate")

# ── 4. Solver and IB edits ────────────────────────────────────────────────
ctl.flush_project_snapshot()
solver_panel = ctl.main_window.solver_config_panel
base_iter = solver_panel.get_config().num_half_iter
solver_panel.num_half_iter.setValue(base_iter + 321)
check(ctl.flush_project_snapshot(), "4. a Solver edit is recorded")
check(ctl.project_history._undo_stack[-1].description() == "Solver settings",
      "4. ...labelled 'Solver settings'")
ctl.undo()
check(solver_panel.get_config().num_half_iter == base_iter,
      "4. ...and undoes")

ctl.flush_project_snapshot()
ib_panel = ctl.main_window.stl3d_config_panel
base_nx = ib_panel.get_config().nx
ib_panel.nx.setValue(base_nx + 7)
check(ctl.flush_project_snapshot(), "4. an Immersed-Solid edit is recorded")
check(ctl.project_history._undo_stack[-1].description()
      == "Immersed-solid settings", "4. ...labelled 'Immersed-solid settings'")
ctl.undo()
check(ib_panel.get_config().nx == base_nx, "4. ...and undoes")

# ── 5. burst coalescing ───────────────────────────────────────────────────
ctl.flush_project_snapshot()
start_layers = mesh_panel.get_config().bl_layers
n0 = steps()
for v in (3, 4, 5, 6):
    mesh_panel.bl_layers.setValue(v)
ctl.flush_project_snapshot()
check(steps() - n0 == 1,
      f"5. four rapid edits become ONE undo step ({steps() - n0})")
ctl.undo()
check(mesh_panel.get_config().bl_layers == start_layers,
      "5. one undo returns to before the whole burst")

# ── 6-9. cross-scope chronology ───────────────────────────────────────────
GEOMS = [os.path.join(_REPO, "examples", "geometries", n)
         for n in ("naca0012.dat", "circle.dat")]
if not all(os.path.exists(g) for g in GEOMS):
    print("SKIP example geometries missing — cross-tab checks skipped", flush=True)
else:
    ctl2 = AppController()
    for g in GEOMS:
        ctl2.load_geometry_from_path(g)
    ctl2.main_window.mode_combo.setCurrentIndex(1)
    ctl2.flush_project_snapshot()
    panel2 = ctl2.main_window.mesh_config_panel
    tab_a, tab_b = ctl2.sessions[0], ctl2.sessions[1]

    def cad_edit(session, n):
        seg = session.project_model.segments[0]
        session.command_history.execute(
            UpdateParamsCmd(session, 0, dict(seg.parameters), {"n": n}))

    def cad_n(session):
        return session.project_model.segments[0].parameters.get("n")

    orig_a, orig_b = cad_n(tab_a), cad_n(tab_b)
    cad_edit(tab_a, 111)                      # 1st
    layers_before = panel2.get_config().bl_layers
    panel2.bl_layers.setValue(layers_before + 5)   # 2nd
    ctl2.flush_project_snapshot()
    cad_edit(tab_b, 222)                      # 3rd

    # Park the user on tab A, so a correct undo has to raise tab B itself.
    ctl2.main_window.tab_widget.setCurrentIndex(0)
    ctl2.switch_tab(0)
    check(ctl2.active_session() is tab_a, "7. user is on tab A before undoing")

    ctl2.undo()
    check(cad_n(tab_b) == orig_b,
          "6. undo 1 reverts the newest action (a CAD edit in the OTHER tab)")
    check(ctl2.active_session() is tab_b,
          "7. ...and raises the tab that owns it")

    ctl2.undo()
    check(panel2.get_config().bl_layers == layers_before,
          "6. undo 2 reverts the project-settings edit")

    ctl2.undo()
    check(cad_n(tab_a) == orig_a, "6. undo 3 reverts the oldest CAD edit")
    check(ctl2.active_session() is tab_a, "7. ...raising tab A back")

    ctl2.redo()
    check(cad_n(tab_a) == 111, "8. redo 1 mirrors: oldest-undone comes back first")
    ctl2.redo()
    check(panel2.get_config().bl_layers == layers_before + 5,
          "8. redo 2 restores the project edit")
    ctl2.redo()
    check(cad_n(tab_b) == 222, "8. redo 3 restores the newest CAD edit")

    # 9. Closing a tab drops only its own commands.
    proj_depth = len(ctl2.project_history._undo_stack)
    ctl2.close_tab(1)
    check(len(ctl2.sessions) == 1, "9. the tab closed")
    check(len(ctl2.project_history._undo_stack) == proj_depth,
          "9. the project history is untouched by closing a tab")
    check(ctl2.main_window.undo_btn.isEnabled(),
          "10. undo is still offered from the surviving histories")
    ctl2.undo()
    check(panel2.get_config().bl_layers == layers_before,
          "9. ...and undo still reaches the project edit after the close")

# ── 10. buttons reflect every history ─────────────────────────────────────
fresh = AppController()
check(not fresh.main_window.undo_btn.isEnabled(),
      "10. a brand-new app offers no undo")
fresh.main_window.mode_combo.setCurrentIndex(1)
fresh.flush_project_snapshot()
fresh.main_window.mesh_config_panel.bl_layers.setValue(9)
fresh.flush_project_snapshot()
check(fresh.main_window.undo_btn.isEnabled(),
      "10. a project-only edit enables the undo button")
fresh.undo()
check(fresh.main_window.redo_btn.isEnabled(),
      "10. ...and undoing enables redo")

# ── 11. a pending (debouncing) edit is flushed by undo ────────────────────
pend = AppController()
pend.main_window.mode_combo.setCurrentIndex(1)
pend.flush_project_snapshot()
pp = pend.main_window.mesh_config_panel
pend_base = pp.get_config().bl_layers
pp.bl_layers.setValue(pend_base + 4)
# NOTE: no flush here — the debounce timer is still pending, exactly as it would
# be if the user hit Ctrl+Z immediately after typing.
pend.undo()
check(pp.get_config().bl_layers == pend_base,
      f"11. undo flushes the pending edit and reverts it "
      f"({pp.get_config().bl_layers} vs {pend_base})")

# ── 12. applying an undo must not re-record itself ────────────────────────
depth_before = len(pend.project_history._undo_stack)
redo_before = len(pend.project_history._redo_stack)
pend.flush_project_snapshot()
check(len(pend.project_history._undo_stack) == depth_before
      and len(pend.project_history._redo_stack) == redo_before,
      "12. flushing right after an undo records nothing (no self-retrigger)")
pend.redo()
pend.flush_project_snapshot()
check(pp.get_config().bl_layers == pend_base + 4,
      "12. redo still works after that flush")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
