#!/usr/bin/env python3
"""Drawing a NACA aerofoil in the CAD stage, through the real controller.

#147's demo sentence, driven rather than described: "draw a NACA 0012 of chord 1
in the CAD stage, see it previewed and segmented". `test_naca_airfoil_parity.py`
proves the LAW and the seam it crosses, and is deliberately Qt-free so it runs
with no display; this file is the other half — that the shape is reachable from
the UI the user actually has, and arrives as the edges a topology template binds
to rather than as one edge someone still has to split.

What is checked:

  1. The shape tool: two clicks (leading edge, then trailing edge) become a
     pending aerofoil whose chord and angle of attack come out of the span
     between them — so the tool means something geometric, not just "open a
     dialog".
  2. Committing it adds the PARTS, in ONE undoable step. Undo takes the whole
     aerofoil back; three presses leaving a lower surface behind would be a
     geometry nobody authored.
  3. It previews like any other analytic shape: the canvas gets points for every
     part, through the same `GeometryService` call the other shapes use.
  4. The sidebar round-trips it: selecting an aerofoil edge shows its own page,
     the widgets hold its values, and reading them back gives the same
     parameters — including the two that are not spin boxes (the designation and
     the sharp-TE flag), which is the half a numeric-only form would drop.
  5. A blunt section arrives as THREE edges, the third being its trailing-edge
     base.

NAMED BLIND SPOTS.

  * **No mouse events are synthesised.** The tool is driven at
    `on_shape_drawn(tool, pts)`, which is where the canvas hands the placed
    points over; that the canvas emits it after two clicks is
    `_DRAW_NPTS['naca']`'s and is asserted as data here, not by clicking.
  * **The modeless dialog is opened and closed by the controller**, so what is
    proved about it is that the commit path runs — not that its fields look
    right. The fields are covered through `shape_spec`'s tables in check 4.
  * **Editing one part of an existing aerofoil is not covered, because nothing
    joins the parts after they are created.** Changing the chord on the upper
    surface alone leaves a geometry whose two halves disagree, and the user can
    see it in the preview; there is no model-level link that would stop it. A
    named limitation of #147, not an oversight — see `docs/design_notes/gui.md`.

Run: python3 tools/PreProcessor/tests/test_naca_airfoil_gui.py
"""
import functools
import math
import os
import sys
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

import builtins                                                    # noqa: E402
print = functools.partial(builtins.print, flush=True)
_FAILS = []
_RUN = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    _RUN.append(msg)
    if not cond:
        _FAILS.append(msg)


threading.Timer(90, lambda: (print("FAIL watchdog >90s"), os._exit(99))).start()

from PyQt6.QtWidgets import QApplication                           # noqa: E402
app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController                           # noqa: E402
from app.models import shape_spec                                  # noqa: E402
from app.models.curve_edit_spec import CURVE_TYPES                 # noqa: E402
from app.services import naca_airfoil as na                        # noqa: E402
from app.services.canvas_tools import DRAW_NPTS, draw_hint         # noqa: E402
from app.services.geometry_service import GeometryService          # noqa: E402

import numpy as np                                                 # noqa: E402


def draw_airfoil(ctrl, le, te, **params):
    """Drive the tool the way the canvas does: place two points, then commit."""
    ctrl.on_shape_drawn("naca", [le, te])
    app.processEvents()
    seg = ctrl.edge_edit.segment
    if seg is not None and params:
        seg.parameters.update(params)
    ctrl._commit_pending_edge()
    app.processEvents()
    return seg


# ── 1. the tool ───────────────────────────────────────────────────────────── #

check(DRAW_NPTS.get("naca") == 2,
      "1. the aerofoil tool collects exactly two points (%r)"
      % DRAW_NPTS.get("naca"))
check("LEADING" in draw_hint("naca", 0) and "TRAILING" in draw_hint("naca", 1),
      "1. ...and asks for the leading edge first, then the trailing edge (%r / "
      "%r)" % (draw_hint("naca", 0), draw_hint("naca", 1)))

c = AppController()
sess = c.active_session()
sess.original_points = np.empty((0, 2), dtype=float)
sess.project_model.closed_mode = "open"

c.on_shape_drawn("naca", [(1.0, 0.0), (1.0, -2.0)])
app.processEvents()
pending = c.edge_edit.segment
check(pending is not None and pending.curve_type == "naca4",
      "1. two clicks open a pending aerofoil edge (%r)"
      % (pending and pending.curve_type))
check(pending is not None and abs(pending.parameters["chord"] - 2.0) < 1e-9,
      "1. ...whose chord is the span the user drew (%.6f)"
      % (pending.parameters["chord"] if pending else -1))
check(pending is not None and abs(pending.parameters["alpha_deg"] - 90.0) < 1e-9,
      "1. ...and whose angle of attack is that span's own direction (%.4f)"
      % (pending.parameters["alpha_deg"] if pending else -1))
check(pending is not None
      and (pending.parameters["x_le"], pending.parameters["y_le"]) == (1.0, 0.0),
      "1. ...placed at the FIRST click, which is the leading edge")

c._commit_pending_edge()
app.processEvents()


# ── 2. it lands as its parts, in one undo step ────────────────────────────── #

segs = sess.project_model.segments
check([s.parameters.get("part") for s in segs] == ["upper", "lower"],
      "2. committing adds the aerofoil's two surfaces (%r)"
      % [s.parameters.get("part") for s in segs])
check(len({s.id for s in segs}) == 2,
      "2. ...as two ordinary CAD edges with their own ids (%r)"
      % [s.id for s in segs])
c.undo()
app.processEvents()
check(not sess.project_model.segments,
      "2. ONE undo takes the whole aerofoil back (%d edge(s) left)"
      % len(sess.project_model.segments))
c.redo()
app.processEvents()
check([s.parameters.get("part") for s in sess.project_model.segments]
      == ["upper", "lower"],
      "2. ...and redo brings all of it back (%r)"
      % [s.parameters.get("part") for s in sess.project_model.segments])


# ── 3. it previews like any other analytic shape ──────────────────────────── #

drawn = []
for s in sess.project_model.segments:
    pts = GeometryService.get_segment_points(sess, s)
    drawn.append(0 if pts is None else len(pts[0]))
check(all(n >= 2 for n in drawn),
      "3. every part draws through the same verb the canvas uses (%r points)"
      % drawn)

up = GeometryService.get_segment_points(sess, sess.project_model.segments[0])
lo = GeometryService.get_segment_points(sess, sess.project_model.segments[1])
seam = math.hypot(up[0][-1] - lo[0][0], up[1][-1] - lo[1][0])
check(seam < 1e-12,
      "3. ...and the upper surface ends exactly where the lower one starts — "
      "the leading edge (%.3e apart)" % seam)


# ── 4. the sidebar round-trips it ─────────────────────────────────────────── #

ep = c.main_window.sidebar_view.edge_props_panel
check(ep.curve_type_combo.count() == ep.shape_stack.count() == len(CURVE_TYPES),
      "4. the combo, the widget stack and the type list still agree "
      "(%d / %d / %d)" % (ep.curve_type_combo.count(), ep.shape_stack.count(),
                          len(CURVE_TYPES)))

target = sess.project_model.segments[0]
target.parameters.update({"designation": "4415", "chord": 0.75, "x_le": 2.0,
                          "y_le": -0.5, "alpha_deg": -3.5, "sharp_te": False})
# Through the controller's own selection, not `sidebar_view.show_curve_segment`
# directly: populating the form emits every widget's change signal, and the
# guard that stops those being written back over the model half-filled is the
# controller's `populating()`. Driving the view alone would be testing a path
# the application does not take — and it clobbers the edge, measured.
c._select_segment_by_index(sess.project_model.segments.index(target))
app.processEvents()
idx = CURVE_TYPES.index("naca4")
check(ep.curve_type_combo.currentIndex() == idx
      and ep.shape_stack.currentIndex() == idx,
      "4. selecting an aerofoil edge shows the aerofoil page (%d / %d, want %d)"
      % (ep.curve_type_combo.currentIndex(), ep.shape_stack.currentIndex(), idx))

back = shape_spec.read_widget_params(ep, "naca4")
want = {k: target.parameters[k] for k in shape_spec.DEFAULTS["naca4"]
        if k != "part"}
wrong = {k: (v, back.get(k)) for k, v in want.items()
         if not (abs(v - back[k]) < 1e-9 if isinstance(v, float) else v == back[k])}
check(not wrong,
      "4. ...and the widgets hold exactly what the edge says (mismatched: %r)"
      % wrong)
check(ep.naca_designation.text() == "4415"
      and ep.naca_sharp_te.isChecked() is False,
      "4. ...including the two that are NOT spin boxes: the designation (%r) "
      "and the sharp-TE flag (%r)"
      % (ep.naca_designation.text(), ep.naca_sharp_te.isChecked()))


# ── 5. a blunt section arrives as three edges ─────────────────────────────── #

c2 = AppController()
sess2 = c2.active_session()
sess2.original_points = np.empty((0, 2), dtype=float)
sess2.project_model.closed_mode = "open"
draw_airfoil(c2, (0.0, 0.0), (1.0, 0.0), sharp_te=False)
parts = [s.parameters.get("part") for s in sess2.project_model.segments]
check(parts == list(na.segment_parts(False)),
      "5. a BLUNT section arrives as three edges, its base among them (%r)"
      % parts)
base = GeometryService.get_segment_points(
    sess2, sess2.project_model.segments[2])
span = math.hypot(base[0][-1] - base[0][0], base[1][-1] - base[1][0])
check(abs(span - 2.0 * na.half_thickness(1.0, 0.12, False)) < 1e-9,
      "5. ...and that base really spans the open trailing edge (%.8f)" % span)


print("\n%d checks, %d failed" % (len(_RUN), len(_FAILS)))
if _FAILS:
    print("FAILED:")
    for f in _FAILS:
        print("  - " + f)
os._exit(1 if _FAILS else 0)
