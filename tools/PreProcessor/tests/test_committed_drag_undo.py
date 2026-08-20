#!/usr/bin/env python3
"""One canvas gesture on a committed edge is one undo step — and only ever its own.

Architecture backlog candidate 7, ticket 3 (issue #17). Dragging a control-point
handle of an ALREADY-COMMITTED edge fires many move events; the whole gesture
must collapse into a single undoable edit. That was held by
``AppController._drag_orig_state``: a nullable attribute the drag handler filled
on the first move event, and which the *selection/refresh chokepoint* cleared as
a side effect, in an unrelated method, with a comment explaining why the clearing
had to be remembered.

It is now a transition on ``EdgeEditSession`` — ``begin_drag`` / ``finish_drag``
— and the rule the clearing enforced became a PROPERTY: a drag belongs to the
segment it began on and cannot be finished against another.

This test drives the real ``AppController`` on the offscreen Qt platform, so the
gesture goes through the actual handler, sidebar widgets and command history.
The owner's verbs are additionally pinned Qt-free in ``test_edge_edit_owner.py``;
here the point is the wiring, which is where the old bug lived.

What it pins:

1. ONE GESTURE, ONE UNDO STEP. Several move events plus the finished one leave
   exactly one entry, and undoing it restores the pre-drag parameters — not the
   state one move event ago, which is what a per-event snapshot would give.

2. A GESTURE THAT CHANGES SELECTION MID-DRAG RECORDS NOTHING, ON EITHER SEGMENT.
   This is the case the clearing call existed for. Note what is being prevented:
   not merely a wrong-sized undo step, but recording segment A's pre-drag shape
   as the "before" state of segment B — undo would then write A's shape onto B.
   The old code narrowly avoided that by clearing, and still recorded a
   one-event edit on B; the owner's identity rule records nothing at all.

3. AN UNCHANGED GESTURE RECORDS NOTHING, so a click that nudges a handle and
   returns it does not fill the undo stack with steps that undo nothing.

4. THE SELECTION/REFRESH CHOKEPOINT NO LONGER CLEARS ANYTHING. Checked by AST
   rather than by behaviour: the guarantee is meant to hold because of where the
   state lives, so a clearing call quietly reintroduced there would make this
   suite pass for the old reason.

macOS has no ``timeout``; a watchdog hard-exits rather than hanging CI.

Run:  python3 tools/PreProcessor/tests/test_committed_drag_undo.py
"""
import ast
import functools
import os
import sys
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

import builtins  # noqa: E402
print = functools.partial(builtins.print, flush=True)
_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: the drag test blocked >60s")
    os._exit(99)


_wd = threading.Timer(60, _watchdog)
_wd.daemon = True
_wd.start()

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.controller import AppController  # noqa: E402
from app.models.segment import SegmentModel  # noqa: E402

c = AppController()
sess = c.active_session()


def _add_circle(seg_id, cx, cy, r):
    seg = SegmentModel(seg_id, -1, -1)
    seg.type = "curve"
    seg.curve_type = "circle"
    seg.curve_mode = "parametric"
    seg.parameters = {"n_points": 50, "cx": cx, "cy": cy, "r": r}
    sess.project_model.segments.append(seg)
    return seg


seg_a = _add_circle(1, 0.0, 0.0, 1.0)
seg_b = _add_circle(2, 10.0, 10.0, 2.0)
c._refresh_segment_list()


def _select(idx):
    """Select a segment the way the app does — through the controller, so the
    sidebar widgets really hold that segment's parameters."""
    sess.current_segment_idx = idx
    c._select_segment_by_index(idx)
    app.processEvents()


def _undo_depth():
    return len(sess.command_history._undo_stack)


def _drag(handle, moves, finish_at):
    """Deliver a gesture: several move events, then the finished one."""
    for x, y in moves:
        c._on_edge_handle_dragged(handle, x, y, False)
    c._on_edge_handle_dragged(handle, finish_at[0], finish_at[1], True)


# ══ 1: one gesture, one undo step ═══════════════════════════════════════════
_select(0)
before = dict(seg_a.parameters)
depth0 = _undo_depth()
_drag("c", [(0.3, 0.0), (0.6, 0.0), (0.9, 0.0)], (1.2, 0.0))
app.processEvents()
after = dict(seg_a.parameters)

check(after.get("cx") != before.get("cx"),
      f"1a the gesture actually moved the edge (cx {before.get('cx')} -> "
      f"{after.get('cx')})")
check(_undo_depth() == depth0 + 1,
      f"1b four move events + finish = ONE undo entry (got "
      f"{_undo_depth() - depth0})")
sess.command_history.undo()
app.processEvents()
check(abs(sess.project_model.segments[0].parameters.get("cx", 99)
          - before.get("cx", 0.0)) < 1e-9,
      "1c undo restores the PRE-GESTURE value, not the last move event's")
sess.command_history.redo()
app.processEvents()

# ══ 2: selection changes mid-drag → nothing recorded, on either segment ═════
_select(0)
depth0 = _undo_depth()
a_before = dict(seg_a.parameters)
b_before = dict(seg_b.parameters)

c._on_edge_handle_dragged("c", 0.5, 0.5, False)   # gesture begins on A
c._on_edge_handle_dragged("c", 0.7, 0.7, False)
_select(1)                                        # …selection moves to B
c._on_edge_handle_dragged("c", 5.0, 5.0, True)    # …and the finish lands on B
app.processEvents()

check(_undo_depth() == depth0,
      f"2a a gesture whose selection changed mid-drag records NOTHING "
      f"(got {_undo_depth() - depth0} entries)")
if _undo_depth() > depth0:
    print(f"     (recorded: {type(list(sess.command_history._undo_stack)[-1]).__name__})")

# The decisive part: B must not carry A's pre-drag shape as its undo baseline.
check(abs(seg_b.parameters.get("r", 0.0) - b_before.get("r", 0.0)) < 1e-9,
      "2b segment B's radius is untouched — A's snapshot was not applied to it")
check(not c.edge_edit.is_dragging(),
      "2c the drag is over either way (the owner does not leak a live drag)")

# And the next gesture is clean: it records its own edit, not a merged one.
_select(0)
seg_a.parameters.update(a_before)
c._select_segment_by_index(0)
app.processEvents()
depth0 = _undo_depth()
_drag("c", [(2.0, 0.0)], (3.0, 0.0))
app.processEvents()
check(_undo_depth() == depth0 + 1,
      f"2d the NEXT gesture records exactly one entry of its own "
      f"(got {_undo_depth() - depth0})")

# ══ 3: an unchanged gesture records nothing ═════════════════════════════════
_select(0)
app.processEvents()
here = (seg_a.parameters.get("cx", 0.0), seg_a.parameters.get("cy", 0.0))
depth0 = _undo_depth()
_drag("c", [(here[0] + 0.4, here[1]), (here[0] + 0.8, here[1])], here)
app.processEvents()
check(_undo_depth() == depth0,
      f"3 a gesture that returns to its starting shape records nothing "
      f"(got {_undo_depth() - depth0})")

# ══ 4: the chokepoint no longer clears the snapshot ═════════════════════════
_src = open(os.path.join(_GUI, "app", "controllers", "curve_edit_ctrl.py")).read()
check("_drag_orig_state" not in _src,
      "4a the nullable attribute is gone from curve_edit_ctrl")
_tree = ast.parse(_src)
_refresh = next((n for n in ast.walk(_tree) if isinstance(n, ast.FunctionDef)
                 and n.name == "_refresh_edge_handles"), None)
_body = ast.unparse(_refresh) if _refresh is not None else ""
check(_refresh is not None
      and "drag" not in _body.lower().split('"""')[-1],
      "4b the selection/refresh chokepoint clears no drag state")
_ctrl = open(os.path.join(_GUI, "app", "controller.py")).read()
check("_drag_orig_state" not in _ctrl,
      "4c …and it is gone from AppController.__init__")

print()
_wd.cancel()
if _FAILS:
    print(f"RESULT: {len(_FAILS)} FAILED")
    for f in _FAILS:
        print("  - " + f)
    os._exit(1)
print("RESULT: ALL PASS")
os._exit(0)
