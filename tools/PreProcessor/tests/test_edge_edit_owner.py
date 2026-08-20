#!/usr/bin/env python3
"""The modeless edge-edit lifecycle — BOTH kinds — driven with no Qt at all.

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

Ticket 2 (issue #16) moved the SECOND edit kind — the imported outline reshaped
by its corner vertices, seven more attributes — into the same owner, so
``_edit_in_progress()`` has exactly one thing to ask. Checks 9-12 cover it:

9.  ``is_active()`` ANSWERS FOR EITHER KIND, and ``active_segment`` returns
    whichever edge is live. That is the single question; two owners would put
    an ``or`` back at every call site, which is where this started.

10. A CORNER DRAG IS A VALUE IN, AN OUTLINE OUT. ``move_corner`` returns the
    re-fitted points instead of mutating a live array, so a re-fit cannot
    accumulate onto the previous frame and the pristine snapshot stays a valid
    basis for the whole session. Cancel therefore restores the points
    BYTE-FOR-BYTE, not to within a tolerance.

11. COMMIT IS ONE ``ReplaceGeometryPointsCmd``, and undo puts the original
    layout back. An unchanged shape records nothing.

12. THE HANDLE-ID FORMAT LIVES IN ONE PLACE. ``handle_points`` emits the ids and
    ``move_corner`` parses them, so the canvas cannot be handed a spelling the
    owner will not accept; a stray or unknown id is refused rather than raising,
    because ids arrive from the canvas.

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
FileEditControllerMixin = _load_by_path(
    "_file_edit_ctrl_standalone",
    "app", "controllers", "file_edit_ctrl.py").FileEditControllerMixin

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
        self.closes = 0

    def is_closed(self):
        return self._closed

    def close(self):
        # The one thing the CALLER does to it. An ending the dialog did not
        # initiate has to take the window down, or it sits there with its Apply
        # and Cancel pointing at an owner that has forgotten the edit.
        self.closes += 1


class _Canvas:
    """Only what the edit mixins call on it — the handles they draw."""

    def __init__(self):
        self.handles = None
        self.cleared = 0

    def show_edge_handles(self, items):
        self.handles = list(items)

    def clear_edge_handles(self):
        self.cleared += 1
        self.handles = None


class _Window:
    def __init__(self):
        self.titles = []
        self.canvas_view = _Canvas()

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
        self.canvas_cleared_for = []
        self.refreshes = 0
        self.selected = []
        self.handles_shown = 0
        self.previews = 0

    def active_session(self):
        return self._session

    def log(self, msg):
        self.logs.append(msg)

    def _clear_pending_canvas(self, session=None):
        # Records WHICH session the canvas clear was aimed at: the preview is a
        # canvas item keyed by session id, so aiming it at the front tab leaves
        # the preview drawn on the tab the edit belonged to.
        self.canvas_cleared += 1
        self.canvas_cleared_for.append(session)

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
host.edge_edit.begin(seg, is_new=False, session=sess)
dlg = _Dialog(closed=False)
host.edge_edit.attach_dialog(dlg)
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
check("7b' …aimed at the EDIT's session, not whatever is in front",
      host.canvas_cleared_for == [sess])
check("7b'' …and closed the dialog, which this ending did not come from",
      dlg.closes == 1)
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

# ══ 9-12: the SHAPE (imported outline) edit, in the same owner ══════════════
import numpy as np  # noqa: E402


class _EndpointDialog:
    """The endpoint dialog, opaque to the owner: only the caller talks to it."""

    def __init__(self):
        self.points = []
        self.closes = 0

    def set_points(self, p0, p1):
        self.points.append((tuple(p0), tuple(p1)))

    def close(self):
        self.closes += 1


class _FileSeg:
    def __init__(self, start_index, end_index, seg_id=1):
        self.type = "file"
        self.id = seg_id
        self.start_index = start_index
        self.end_index = end_index


class _ShapeHost(FileEditControllerMixin, PendingEditControllerMixin):
    """The mixin's collaborators, stubbed to what it actually calls.

    BOTH mixins, matching the real ``AppController``: the shape edit reaches the
    cross-kind policy that lives on ``PendingEditControllerMixin``
    (``_make_way_for_edit``, ``_close_orphan_dialog``). That coupling is real and
    is named in the review as a Divergent Change on that module's name; stubbing
    around it here would hide it instead."""

    def __init__(self, session):
        self.edge_edit = EdgeEditSession()
        self._session = session
        self.main_window = _Window()
        self.logs = []
        self.redraws = 0
        self.geometry_updates = 0

    def active_session(self):
        return self._session

    def log(self, msg):
        self.logs.append(msg)

    def _redraw_file_geometry(self, session):
        self.redraws += 1

    def _apply_geometry_update(self, session):
        self.geometry_updates += 1

    def _clear_file_edit_canvas(self):
        pass


def _outline_session():
    """A closed 6-point outline cut into three file edges (the last wrapping)."""
    sess = GeometrySession()
    sess.original_points = np.array([[0.0, 0.0], [0.5, 0.5],
                                     [1.0, 0.0], [1.5, -0.5],
                                     [2.0, 0.0], [1.0, -1.0]])
    sess.project_model.segments.extend(
        [_FileSeg(0, 2, 1), _FileSeg(2, 4, 2), _FileSeg(4, 6, 3)])
    return sess


# ── 9: one question, either kind ────────────────────────────────────────────
owner = EdgeEditSession()
sess = _outline_session()
edge = sess.project_model.segments[1]
check("9a a fresh owner is idle for both kinds",
      owner.is_active() is False and owner.is_shape_active() is False
      and owner.active_segment is None)
check("9b begin_shape opens the outline",
      owner.begin_shape(edge, sess.original_points,
                        sess.project_model.segments) is True)
check("9c is_active() answers for the SHAPE kind too — the one question",
      owner.is_active() is True and owner.is_shape_active() is True)
check("9d active_segment returns the shape's edge",
      owner.active_segment is edge)
check("9e the dialog's two corners are the double-clicked edge's",
      owner.edge_corners == (2, 4))
check("9f one handle per corner, in stable sorted order",
      [h for h, _p in owner.handle_points()] == ["c0", "c2", "c4"])
owner.end_shape()
check("9g end_shape puts it back to idle",
      owner.is_active() is False and owner.edge_corners is None
      and owner.handle_points() == [])

# A geometry with no usable file edge is refused rather than opened empty.
empty = GeometrySession()
empty.original_points = np.array([[0.0, 0.0], [1.0, 0.0]])
check("9h a geometry with no file edge is refused",
      EdgeEditSession().begin_shape(_FileSeg(0, 1), empty.original_points,
                                    []) is False)
check("9i …and so is an empty point array",
      EdgeEditSession().begin_shape(_FileSeg(0, 1), np.empty((0, 2)),
                                    [_FileSeg(0, 1)]) is False)

# The closing edge is the one whose end_index is past the end.
owner = EdgeEditSession()
closing = _FileSeg(4, 6, 3)
owner.begin_shape(closing, sess.original_points, sess.project_model.segments)
check("9j the closing edge's second corner wraps to index 0",
      owner.edge_corners == (4, 0))
owner.end_shape()

# ── 10: a drag is a value in, an outline out; cancel is byte-for-byte ────────
sess = _outline_session()
pristine = sess.original_points.copy()
host = _ShapeHost(sess)
host.edge_edit.begin_shape(sess.project_model.segments[1],
                           sess.original_points, sess.project_model.segments,
                           session=sess)
host.edge_edit.attach_shape_dialog(_EndpointDialog())
host._on_file_handle_dragged("c2", 1.0, 1.0, False)
check("10a a corner drag re-fits and rebinds the session's points",
      not np.array_equal(sess.original_points, pristine)
      and sess.original_points is not pristine)
check("10b …and the neighbouring edges both moved (the shared corner)",
      not np.allclose(sess.original_points[1], pristine[1])
      and not np.allclose(sess.original_points[3], pristine[3]))
check("10c the dragged corner is mirrored into the dialog",
      host.edge_edit.shape_dialog.points[-1][0] == (1.0, 1.0))
host._on_file_handle_dragged("c0", 9.0, -9.0, False)
check("10d dragging a corner the dialog does NOT show leaves it alone",
      len(host.edge_edit.shape_dialog.points) == 1)
host._on_file_handle_dragged("c2", 1.0, 0.0, True)
host._on_file_handle_dragged("c0", 0.0, 0.0, True)
check("10e re-fits do not accumulate: back at the original corners the "
      "outline is EXACTLY the original",
      np.array_equal(sess.original_points, pristine))

sess = _outline_session()
pristine = sess.original_points.copy()
host = _ShapeHost(sess)
host.edge_edit.begin_shape(sess.project_model.segments[1],
                           sess.original_points, sess.project_model.segments,
                           session=sess)
shape_dlg = _EndpointDialog()
host.edge_edit.attach_shape_dialog(shape_dlg)
host._on_file_handle_dragged("c2", 4.0, 7.0, True)
host._cancel_file_edit()
check("10f cancel restores the points byte-for-byte",
      np.array_equal(sess.original_points, pristine))
check("10g …ends the session and says so",
      host.edge_edit.is_active() is False
      and any("cancelled" in m for m in host.logs))
check("10h cancel records nothing on the undo stack",
      len(sess.command_history._undo_stack) == 0)
check("10i …and closes the shape dialog this ending did not come from",
      shape_dlg.closes == 1)

# ── 11: commit is one undoable geometry replacement ─────────────────────────
sess = _outline_session()
pristine = sess.original_points.copy()
host = _ShapeHost(sess)
host.edge_edit.begin_shape(sess.project_model.segments[1],
                           sess.original_points, sess.project_model.segments)
host._on_file_handle_dragged("c2", 1.0, 1.0, True)
moved = sess.original_points.copy()
host._commit_file_edit()
hist = sess.command_history
check("11a commit records exactly one command",
      len(hist._undo_stack) == 1)
check("11b …a ReplaceGeometryPointsCmd",
      type(hist._undo_stack[-1]).__name__ == "ReplaceGeometryPointsCmd")
check("11c the committed layout is the edited one",
      np.array_equal(sess.original_points, moved))
check("11d commit marks the session dirty and retitles",
      sess.is_geometry_modified is True
      and host.main_window.titles == [(sess.display_name, True)])
hist.undo()
check("11e undo restores the original layout",
      np.array_equal(sess.original_points, pristine))
hist.redo()
check("11f redo re-applies the edit",
      np.array_equal(sess.original_points, moved))
check("11g commit ends the session", host.edge_edit.is_active() is False)

sess = _outline_session()
host = _ShapeHost(sess)
host.edge_edit.begin_shape(sess.project_model.segments[1],
                           sess.original_points, sess.project_model.segments)
host._commit_file_edit()
check("11h an unchanged shape records nothing",
      len(sess.command_history._undo_stack) == 0)

# ── 12: the handle-id format has one owner ──────────────────────────────────
sess = _outline_session()
owner = EdgeEditSession()
owner.begin_shape(sess.project_model.segments[1], sess.original_points,
                  sess.project_model.segments)
ids = [h for h, _p in owner.handle_points()]
check("12a every id the owner EMITS is one it accepts back",
      all(owner.move_corner(h, 0.0, 0.0) is not None for h in ids))
check("12b an unparseable or unknown id is refused, not raised",
      owner.move_corner("x9", 1.0, 1.0) is None
      and owner.move_corner("c", 1.0, 1.0) is None
      and owner.move_corner("c999", 1.0, 1.0) is None
      and owner.move_corner(None, 1.0, 1.0) is None)
check("12c corner_key round-trips the ids it emits",
      [owner.corner_key(h) for h in ids] == [0, 2, 4])
owner.end_shape()
check("12d an idle owner refuses every shape verb",
      owner.move_corner("c0", 1.0, 1.0) is None
      and owner.set_edge_corners((0, 0), (1, 1)) is None
      and owner.end_shape() is None
      and owner.edge_corner_points() is None)

# Each kind resets only its own state.
owner = EdgeEditSession()
owner.begin_shape(sess.project_model.segments[1], sess.original_points,
                  sess.project_model.segments)
owner.commit()   # the ANALYTIC verb, with only a shape edit live
check("12e ending the analytic edit leaves a live shape edit alone",
      owner.is_shape_active() is True)
owner.end_shape()
owner.begin(_polygon(seg_id=11), is_new=True)
owner.end_shape()   # the SHAPE verb, with only an analytic edit live
check("12f …and vice versa", owner.is_active() is True)
owner.cancel()

# ══ 14: the committed-edge DRAG is a transition, not a nullable field ═══════
owner = EdgeEditSession()
a = _polygon(seg_id=20, verts=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0]])
b = _polygon(seg_id=21, verts=[[5.0, 5.0], [6.0, 5.0], [6.0, 6.0]])
check("14a a fresh owner is not dragging",
      owner.is_dragging() is False and owner.drag_segment is None)
check("14b the first move event starts the drag", owner.begin_drag(a) is True)
check("14c …and it is on that segment",
      owner.is_dragging() is True and owner.drag_segment is a)
a.parameters["vertices_str"] = "moved"
check("14d later move events do NOT re-snapshot (one gesture, one step)",
      owner.begin_drag(a) is False and owner.begin_drag(a) is False)
snap = owner.finish_drag(a)
check("14e finishing on the segment it began on returns the PRE-gesture state",
      snap is not None and snap.get("parameters", {}).get("vertices_str")
      != "moved")
check("14f …and the drag is over", owner.is_dragging() is False)

# The rule the old clearing call enforced, now a property.
owner.begin_drag(a)
check("14g finishing against a DIFFERENT segment returns nothing",
      owner.finish_drag(b) is None)
check("14h …and still ends the drag, so nothing is left to leak",
      owner.is_dragging() is False)
check("14i finishing with no drag in progress returns nothing",
      owner.finish_drag(a) is None)
check("14j begin_drag(None) starts nothing",
      owner.begin_drag(None) is False and owner.is_dragging() is False)

# A gesture that never finished cannot be adopted by the next one.
owner.begin_drag(a)
check("14k a drag on another segment re-snapshots rather than continuing",
      owner.begin_drag(b) is True and owner.drag_segment is b)
owner.finish_drag(b)

# The drag must NOT count as a modal edit session: the callers that guard on
# is_active() (double-click editors, canvas selection) run during a drag.
owner.begin_drag(a)
check("14l a drag is not an 'edit in progress' — is_active() stays False",
      owner.is_active() is False)
owner.finish_drag(a)

# ══ 15: an edit BELONGS to the session it began in ══════════════════════════
sA, sB = GeometrySession(), GeometrySession()
owner = EdgeEditSession()
pa = _polygon(seg_id=30)
check("15a a fresh owner owns nothing",
      owner.owning_session is None and owner.belongs_to(sA) is False)
owner.begin(pa, is_new=False, session=sA)
check("15b the edit reports the session it began in",
      owner.owning_session is sA and owner.belongs_to(sA) is True
      and owner.belongs_to(sB) is False)
check("15c belongs_to(None) is False, not a match on a missing session",
      owner.belongs_to(None) is False)

# The invariant: a second begin is REFUSED, and the live edit is untouched.
pb = _polygon(seg_id=31)
check("15d begin while active is refused",
      owner.begin(pb, is_new=True, session=sB) is False)
check("15e …and the live edit is exactly as it was",
      owner.segment is pa and owner.owning_session is sA)
check("15f begin_shape while an analytic edit is live is refused too",
      owner.begin_shape(_FileSeg(0, 2), _outline_session().original_points,
                        _outline_session().project_model.segments,
                        session=sB) is False)
out = owner.cancel()
check("15g the outcome carries the session the edit began in",
      out is not None and out.session is sA)

# …and the same in the other direction.
osess = _outline_session()
owner = EdgeEditSession()
owner.begin_shape(osess.project_model.segments[1], osess.original_points,
                  osess.project_model.segments, session=sA)
check("15h a shape edit reports its session too",
      owner.owning_session is sA and owner.belongs_to(sA) is True)
check("15i begin while a SHAPE edit is live is refused",
      owner.begin(pb, is_new=True, session=sB) is False
      and owner.is_shape_active() is True)
sout = owner.end_shape()
check("15j the shape outcome carries its session",
      sout is not None and sout.session is sA)

# A commit outcome carries it as well — that is the one the cross-tab bug used.
owner = EdgeEditSession()
owner.begin(_polygon(seg_id=32), is_new=True, session=sB)
cout = owner.commit()
check("15k a commit outcome carries the session too",
      cout is not None and cout.session is sB)

# A DRAG belongs to a session but is not a modal edit: leaving drops it silently.
owner = EdgeEditSession()
owner.begin_drag(pa, session=sA)
check("15l a live drag does not make the owner 'belong' to the session",
      owner.belongs_to(sA) is False and owner.owning_session is None)
check("15m release_drag_for ignores another session's drag",
      owner.release_drag_for(sB) is False and owner.is_dragging() is True)
check("15n …and drops its own",
      owner.release_drag_for(sA) is True and owner.is_dragging() is False)
check("15o …so the gesture records nothing when it finishes",
      owner.finish_drag(pa) is None)
check("15p release_drag_for with no drag live is False, not an error",
      owner.release_drag_for(sA) is False)

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

# ══ 13: _edit_in_progress() asks EXACTLY ONE thing ══════════════════════════
_draw_src = open(os.path.join(_HERE, "..", "gui", "app", "controllers",
                              "curve_draw_ctrl.py")).read()
_pred = ast.parse(_draw_src)
_body = next(n for n in ast.walk(_pred)
             if isinstance(n, ast.FunctionDef) and n.name == "_edit_in_progress")
_calls = [n for n in ast.walk(_body) if isinstance(n, ast.Call)]
_bools = [n for n in ast.walk(_body) if isinstance(n, ast.BoolOp)]
check("13 _edit_in_progress() asks exactly one thing, with no 'or': "
      + ast.unparse(_body.body[-1]),
      len(_calls) == 1 and not _bools
      and "edge_edit.is_active" in ast.unparse(_body))

# ══ 8: the five attributes are gone from AppController.__init__ ═════════════
ctrl_src = open(os.path.join(_HERE, "..", "gui", "app", "controller.py")).read()
gone = ["_drag_orig_state",
        "_pending_seg", "_pending_dialog", "_pending_is_new",
        "_pending_orig", "_pending_orig_state",
        "_pending_file", "_pending_file_seg", "_pending_file_dialog",
        "_pending_geom_orig", "_pending_geom_specs", "_pending_geom_cur",
        "_pending_geom_corners"]
check("8a all thirteen edit attributes are gone from AppController",
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
check("8c no caller reads a _pending_* edit attribute directly: "
      + ("; ".join(leaks) if leaks else "none"), not leaks)

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for f in failures:
        print("  - " + f)
    sys.exit(1)
print("All edge-edit owner checks passed.")
