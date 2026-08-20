#!/usr/bin/env python3
"""The modeless edge-edit lifecycle, driven with no Qt at all.

Architecture backlog candidate 7, ticket 1 (issue #15). Creating or re-opening an
analytic edge used to be five attributes on ``AppController`` — the segment, the
dialog, the create/edit flag, a params snapshot and a state snapshot — declared
in ``controller.py``, begun in ``curve_draw_ctrl`` and committed or cancelled in
``pending_edit_ctrl``. Nothing owned them, so "an edit is live" was a ``None``
check every reader had to remember, and the lifecycle could not be run at all
without a canvas, a dialog and a QApplication.

``services/edge_edit.EdgeEditSession`` owns them now. What this test pins:

1. THE OWNER IS QT-FREE, AND SO IS THE COMMIT PATH. The test refuses PyQt6 at
   import (a meta-path hook, so a deferred ``import PyQt6`` inside a function
   body fails too) and then drives ``PendingEditControllerMixin`` itself — the
   real ``_commit_pending_edge`` / ``_cancel_pending_edit`` / dialog-changed
   handler — against a stub host. Re-implementing the commit branch here would
   prove only that the test can add a segment.

2. CANCELLING AN EDIT REVERTS THE SHAPE, AND THE SNAPSHOT SURVIVES AN IN-PLACE
   MUTATION. ``begin()`` deep-copies, so a nested value edited in place still
   reverts. Named honestly: no shipped caller mutates a nested parameter in
   place today — a polygon carries ``vertices_str``, a string, so a shallow copy
   would pass every live path — which is why 2b mutates one directly. It pins
   the owner's CONTRACT (the snapshot is independent of the live params), not a
   failure reproducible through the GUI as it stands; a shape that ever stores a
   list would otherwise revert to the edited value with no test noticing.

3. CANCELLING AN EDIT REVERTS THE OPEN/CLOSED FLAG. It is not part of the
   dialog's ``params``, so it travels separately in both directions: read off
   the dialog by the caller and passed INTO ``update()`` (the owner never calls
   a method on the dialog), and restored from the ``to_dict()`` snapshot on
   cancel. ``to_dict()`` emits ``closed`` only when False, hence the default.

4. CANCELLING A CREATION REVERTS NOTHING. There is no earlier shape; the
   outcome must say so (``reverted`` False) or the log line is wrong and a
   caller could try to restore ``None``.

5. COMMIT ROUTES ON is_new. Creating executes an ``AddCurveSegmentCmd`` (the
   edge appears, undoably); editing records an ``UpdateSegmentStateCmd`` against
   the pre-edit snapshot, and undo puts the old shape back.

6. A NO-OP EDIT RECORDS NOTHING, so pressing Apply without changing anything
   does not push an undo step that undoes nothing.

6b. A POLYGON BACK ON *By Node Count* LOSES ITS ``spacing`` KEY. The dialog
   simply stops sending it, so a stale key left in the parameters puts the edge
   back into By-Spacing mode on the next round-trip and the backend resamples by
   distance while the form says node count.

7. THE SESSION IS ONE-AT-A-TIME AND SELF-CLEARING. After commit or cancel
   ``is_active()`` is False and the segment/dialog references are dropped — a
   held reference would keep a deleted dialog alive and make the next
   ``_edit_in_progress()`` answer for the previous edit.

Run:  python3 tools/PreProcessor/tests/test_edge_edit_owner.py
"""
import os
import sys

# ── Check 1a: refuse PyQt6 for the whole run, at any nesting depth ───────────
class _NoQt:
    def find_module(self, name, path=None):   # py2-era API, still consulted
        return self.find_spec(name, path)

    def find_spec(self, name, path=None, target=None):
        if name == "PyQt6" or name.startswith("PyQt6."):
            raise ImportError(
                f"PyQt6 import refused: {name} — the edge-edit lifecycle must "
                f"run headless")
        return None


sys.meta_path.insert(0, _NoQt())

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "gui"))

import importlib.util  # noqa: E402

from app.commands.segment_cmds import UpdateSegmentStateCmd  # noqa: E402
from app.models.segment import SegmentModel  # noqa: E402
from app.models.session import GeometrySession  # noqa: E402
from app.services.edge_edit import EdgeEditSession  # noqa: E402


def _load_by_path(name, *parts):
    """Import a module from its FILE, bypassing its package ``__init__``.

    ``app/controllers/__init__.py`` eagerly re-exports every mixin, eight of
    which import PyQt6 — the same pre-existing eager-re-export hazard
    ``test_qt_free_seam.py`` records for ``models/`` and ``views/panels/``. That
    is a property of the package, not of the module under test: this file's own
    imports are ``app.commands.segment_cmds`` and nothing else. Loading it by
    path is what stops the package's ``__init__`` from deciding the answer.
    """
    path = os.path.join(_HERE, "..", "gui", *parts)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PendingEditControllerMixin = _load_by_path(
    "_pending_edit_ctrl_standalone",
    "app", "controllers", "pending_edit_ctrl.py").PendingEditControllerMixin

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


# ── Stubs: everything the commit/cancel path touches that is NOT the state ───
class _Dialog:
    """The modeless dialog, as far as the owner is concerned: opaque. Only the
    caller asks it anything, and only the polygon open/closed toggle."""

    def __init__(self, closed=True):
        self._closed = closed

    def is_closed(self):
        return self._closed


class _Window:
    def __init__(self):
        self.titles = []

    def update_title(self, name, dirty):
        self.titles.append((name, dirty))


class _Host(PendingEditControllerMixin):
    """The mixin's collaborators, stubbed to what it actually calls."""

    def __init__(self, session):
        self.edge_edit = EdgeEditSession()
        self._session = session
        self.main_window = _Window()
        self.logs = []
        self.canvas_cleared = 0
        self.refreshes = 0
        self.selected = []
        self.handles_shown = 0
        self.previews = 0

    def active_session(self):
        return self._session

    def log(self, msg):
        self.logs.append(msg)

    def _clear_pending_canvas(self):
        self.canvas_cleared += 1

    def _refresh_segment_list(self):
        self.refreshes += 1

    def _select_segment_by_index(self, idx):
        self.selected.append(idx)

    def _show_pending_handles(self):
        self.handles_shown += 1

    def _preview_pending(self):
        self.previews += 1


def _polygon(seg_id=1, verts=None, closed=True):
    seg = SegmentModel(seg_id, -1, -1)
    seg.type = "curve"
    seg.curve_type = "polygon"
    seg.curve_mode = "parametric"
    seg.parameters = {"n_points": 50,
                      "vertices": list(verts or [[0.0, 0.0], [1.0, 0.0],
                                                 [1.0, 1.0]])}
    seg.closed = closed
    return seg


def _new_host():
    return _Host(GeometrySession())


# ══ 2 + 3: cancelling an EDIT reverts params (deeply) and the closed flag ════
sess = GeometrySession()
seg = _polygon(verts=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]], closed=True)
sess.project_model.segments.append(seg)
host = _Host(sess)
host.edge_edit.begin(seg, is_new=False)
host.edge_edit.attach_dialog(_Dialog(closed=False))
host._on_pending_dialog_changed({"vertices_str": "0,0; 9,9; 1,1"}, 80)
# An in-place edit of a nested value — what the deep copy in ``begin`` is for.
seg.parameters["vertices"][1][0] = 9.0

check("2a live update reaches the segment",
      seg.parameters["vertices_str"] == "0,0; 9,9; 1,1"
      and seg.parameters["n_points"] == 80)
check("3a the dialog's open/closed toggle is mirrored onto the polygon",
      seg.closed is False)
check("1b the dialog-changed handler refreshed handles + preview",
      host.handles_shown == 1 and host.previews == 1)

host._cancel_pending_edit()
check("2b cancel reverts a nested value edited IN PLACE (deep copy)",
      seg.parameters["vertices"] == [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]])
check("2b' cancel reverts the replaced key too",
      "vertices_str" not in seg.parameters)
check("2c cancel reverts n_points", seg.parameters["n_points"] == 50)
check("3b cancel restores the closed flag the dialog toggled",
      seg.closed is True)
check("3c a reverted cancel says so in the log",
      any("reverted" in m for m in host.logs))
check("7a cancel ends the session",
      host.edge_edit.is_active() is False
      and host.edge_edit.segment is None
      and host.edge_edit.dialog is None)
check("7b cancel dropped the canvas decoration", host.canvas_cleared == 1)
check("2d cancelling an edit records nothing on the undo stack",
      len(sess.command_history._undo_stack) == 0)

# ══ 4: cancelling a CREATION reverts nothing ════════════════════════════════
host = _new_host()
fresh = _polygon(seg_id=7)
host.edge_edit.begin(fresh, is_new=True)
outcome = host.edge_edit.cancel()
check("4a cancelling a creation reports nothing reverted",
      outcome is not None and outcome.reverted is False
      and outcome.is_new is True)

host = _new_host()
host.edge_edit.begin(_polygon(seg_id=7), is_new=True)
host._cancel_pending_edit()
check("4b the creation-cancel log line is the add one, not the revert one",
      any("Add edge cancelled" in m for m in host.logs)
      and not any("reverted" in m for m in host.logs))
check("4c a cancelled creation adds nothing to the model",
      len(host.active_session().project_model.segments) == 0)

# ══ 5a: committing a CREATION adds the edge, undoably ═══════════════════════
host = _new_host()
sess = host.active_session()
made = _polygon(seg_id=3)
host.edge_edit.begin(made, is_new=True)
host.edge_edit.attach_dialog(_Dialog(closed=True))
host._on_pending_dialog_changed({"vertices": [[0, 0], [2, 0], [2, 2]]}, 40)
host._commit_pending_edge()
segs = sess.project_model.segments
check("5a committing a creation adds the edited edge itself",
      len(segs) == 1 and segs[0] is made
      and segs[0].parameters["n_points"] == 40)
check("5b the creation is one undoable step",
      len(sess.command_history._undo_stack) == 1)
check("5d commit marks the session dirty and retitles",
      sess.is_geometry_modified is True and host.main_window.titles == [
          (sess.display_name, True)])
sess.command_history.undo()
check("5c undo removes it again",
      len(sess.project_model.segments) == 0)
check("7c commit ends the session",
      host.edge_edit.is_active() is False and host.edge_edit.dialog is None)

# ══ 5e: committing an EDIT records the change against the snapshot ══════════
sess = GeometrySession()
seg = _polygon(seg_id=4, verts=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]])
sess.project_model.segments.append(seg)
host = _Host(sess)
host.edge_edit.begin(seg, is_new=False)
host.edge_edit.attach_dialog(_Dialog(closed=True))
host._on_pending_dialog_changed(
    {"vertices": [[0.0, 0.0], [5.0, 0.0], [1.0, 1.0]]}, 50)
host._commit_pending_edge()
hist = sess.command_history
check("5e committing an edit records exactly one command",
      len(hist._undo_stack) == 1)
check("5f …an UpdateSegmentStateCmd, not an add",
      isinstance(hist._undo_stack[-1], UpdateSegmentStateCmd)
      and len(sess.project_model.segments) == 1)
check("5g the edited edge is reselected", host.selected == [0])
hist.undo()
check("5h undo restores the pre-edit shape",
      sess.project_model.segments[0].parameters["vertices"]
      == [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]])

# ══ 6: a no-op edit records nothing ═════════════════════════════════════════
sess = GeometrySession()
seg = _polygon(seg_id=5)
sess.project_model.segments.append(seg)
host = _Host(sess)
host.edge_edit.begin(seg, is_new=False)
host.edge_edit.attach_dialog(_Dialog(closed=True))
host._commit_pending_edge()
check("6 an unchanged edit pushes no undo step",
      len(sess.command_history._undo_stack) == 0)

# ══ 6b: a polygon back on By Node Count loses its stale spacing key ═════════
owner = EdgeEditSession()
poly = _polygon(seg_id=6)
poly.parameters["spacing"] = 0.05
owner.begin(poly, is_new=False)
owner.update({"vertices_str": "0,0; 1,0; 1,1", "spacing": 0.02}, 50)
check("6b' By-Spacing keeps the key", poly.parameters.get("spacing") == 0.02)
owner.update({"vertices_str": "0,0; 1,0; 1,1"}, 50)
check("6b By-Node-Count drops the stale spacing key",
      "spacing" not in poly.parameters)

line = SegmentModel(9, -1, -1)
line.type, line.curve_type = "curve", "line"
line.parameters = {"n_points": 50, "spacing": 0.05, "x0": 0.0}
line.closed = True
owner = EdgeEditSession()
owner.begin(line, is_new=False)
owner.update({"x0": 1.0}, 50, closed=False)
check("6c the rule is polygon-only: another shape keeps its keys untouched",
      line.parameters.get("spacing") == 0.05)
check("3d …and only a polygon's closed flag is mirrored",
      line.closed is True)

# ══ 7d: the owner refuses to act when no session is live ════════════════════
idle = EdgeEditSession()
check("7d an idle owner is not active and answers None",
      idle.is_active() is False and idle.commit() is None
      and idle.cancel() is None
      and idle.update({"a": 1}, 10) is False)

# ══ 1c: the owner imports no Qt, and the run never loaded any ═══════════════
check("1c no PyQt6 module was loaded anywhere in this run",
      not any(m == "PyQt6" or m.startswith("PyQt6.") for m in sys.modules))

import ast  # noqa: E402

_owner_path = os.path.join(_HERE, "..", "gui", "app", "services",
                           "edge_edit.py")
_imports = set()
for _node in ast.walk(ast.parse(open(_owner_path).read())):
    if isinstance(_node, ast.Import):
        _imports.update(a.name for a in _node.names)
    elif isinstance(_node, ast.ImportFrom):
        _imports.add(_node.module or "")
check("1d services/edge_edit.py imports nothing Qt, at any nesting depth: "
      + ", ".join(sorted(_imports)),
      not any(m.split(".")[0] in ("PyQt6", "PyQt5", "pyqtgraph")
              for m in _imports))
check("1e …and nothing from the app's Qt layers either",
      not any(m.startswith(("app.views", "app.utils")) for m in _imports))

# ══ 8: the five attributes are gone from AppController.__init__ ═════════════
ctrl_src = open(os.path.join(_HERE, "..", "gui", "app", "controller.py")).read()
gone = ["_pending_seg", "_pending_dialog", "_pending_is_new",
        "_pending_orig", "_pending_orig_state"]
check("8a the five analytic-edit attributes are gone from AppController",
      not any(f"self.{a} =" in ctrl_src for a in gone))
check("8b …and the owner is declared there instead",
      "EdgeEditSession()" in ctrl_src)

gui = os.path.join(_HERE, "..", "gui")
leaks = []
for root, _dirs, files in os.walk(os.path.join(gui, "app")):
    for fn in files:
        if not fn.endswith(".py"):
            continue
        path = os.path.join(root, fn)
        text = open(path).read()
        for attr in gone:
            # ``_on_pending_dialog_changed`` is a HANDLER name, not the attribute.
            for line in text.splitlines():
                if f"self.{attr}" in line:
                    leaks.append(f"{os.path.relpath(path, gui)}: {line.strip()}")
check("8c no caller reads a _pending_* analytic attribute directly: "
      + ("; ".join(leaks) if leaks else "none"), not leaks)

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for f in failures:
        print("  - " + f)
    sys.exit(1)
print("All edge-edit owner checks passed.")
