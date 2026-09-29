#!/usr/bin/env python3
"""A derived offset geometry, driven through the real controller (#152).

`test_geometry_offset.py` proves the LAW on the points it returns. This is the
other half: that the law is reachable from the UI the user has, that what it
produces is an ORDINARY geometry carrying its source's segmentation, that the
record of where it came from survives save and reopen, and that every refusal a
user can meet says which geometry it is about.

The demo sentence of the ticket, driven rather than described: draw a shape,
offset it, see both, save, reopen, edit the source, regenerate, and watch the
offset follow.

What is checked:

  1. THE OFFSET IS AN ORDINARY GEOMETRY. A new session with one point array of
     the source's length, the source's split indices as a LIST (not a count, which
     is equal for two different segmentations), and the source's FILE segments —
     ids, boundaries and per-segment facts — while NO new curve type appears
     anywhere. Its points are the ones the service returns, so the canvas preview
     and the thing that writes the geometry are the same owner.
  2. IT RECORDS WHERE IT CAME FROM, VISIBLY. The record carries the source's name
     and the signed distance, and the tab the user reopens says so without
     opening anything.
  3. THE PROJECT ROUND TRIP CARRIES THE RECORD. Through the `.hws` workspace —
     written and read back by the real controller — and through the pipeline
     script's `cads` section and the resampler's own JSON config, which are the
     other two files a project is saved as.
  4. REGENERATION FOLLOWS AN EDITED SOURCE, END TO END. The source is edited and
     the offset re-derived; what is measured is the OFFSET's points against the
     edited source, not a claim that the call was made. It is ONE undo step.
  5. REGENERATION WITHOUT ITS SOURCE IS REFUSED BY NAME. The source tab is closed;
     the refusal names the missing geometry, the offset is untouched, and no other
     open geometry is silently used instead — checked by leaving a DECOY tab whose
     points would be visible in the result if it had been.
  6. THE OTHER TWO REFUSALS SAY WHICH GEOMETRY. A geometry that was never derived,
     and a session with no discrete points at all.
  7. A FOLD REFUSED IN THE CONTROLLER CHANGES NOTHING. No tab is added, and the
     number the refusal names creates one when fed back through the same action.

NAMED BLIND SPOTS.

  * **No dialog is driven.** `OffsetGeometryDialog` is constructed and its
    `signed_distance()` checked as arithmetic (check 1e); the creation path is
    entered at `create_offset_geometry`, which is where the dialog hands over.
    What the widgets look like is not covered here.
  * **The source's ANALYTIC edges are not offset**, by design, and nothing here
    drives a source that has both kinds. A mixed source yields an offset of its
    discrete half; that is the documented behaviour, not a tested one.
  * **Nothing meshes the result.** That an offset geometry reaches the mesher like
    any other is the claim "it is an ordinary geometry" makes; this gate checks
    the shape of the object, not a run.

INJECTIONS, run by hand 2026-09-29 against a copy of the tree, reading the EXIT
CODE as well as the FAIL lines. One per REFUSAL this ticket adds — the fold (K),
the missing source (F), the source with no discrete points (I) and the geometry
that was never derived (L) — plus the record and the segmentation — a mutation that crashes the gate prints no FAIL
line at all and would otherwise score as silence.

  A  `_offset_segmentation` returns no segments          -> 1e, 1f, exit 1
  B  the segments are aliased instead of deep-copied    -> 1f, exit 1
  C  `derived_from` leaves `ProjectModel.to_state_dict` -> 3a, 3b (x2), exit 1
  D  `cad_section` stops going through `to_state_dict`  -> 3b (x2), exit 1
  E  `DerivedOffset.from_dict` ignores `kind`           -> 3d, exit 1
  F  `find_offset_source` falls back to the first open session
                                                       -> 5b, 5c, exit 1
  G  regeneration re-derives from the recorded distance's MAGNITUDE
                                                       -> 4g, exit 1
  H  `RegenerateOffsetCmd.undo` restores only the points -> 4f, exit 1
  I  the no-discrete-points refusal is a silent return   -> 6b (x2), exit 1
  K  the controller opens the tab even when the law refused
                                                       -> 7a, 7d, exit 1
  L  the not-a-derived-geometry refusal is a silent return
                                                       -> 6a, exit 1
  J  NEGATIVE CONTROL: a comment-only edit               -> inert, rightly

G AND H WERE INERT ON THE FIRST RUN, and the ledger above names where they bite
only because the gate was changed to reach them. Both were unfalsifiable as
written: every recorded distance in the file was POSITIVE, so reading its magnitude
changed nothing; and the only undo checked was of a regeneration that had not moved
the segmentation, so an undo restoring nothing left it equal anyway. C and F bit by
CRASHING — the watchdog thread was not a daemon, so an uncaught exception hung the
run for the full 120 s and then exited 99 with no traceback. All three are fixed
here rather than recorded as blind spots.

Run: python3 tools/PreProcessor/tests/test_offset_geometry_gui.py
"""
import functools
import json
import math
import os
import re
import sys
import tempfile
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


# daemon=True: a non-daemon Timer keeps the interpreter alive after the main thread
# has died of an uncaught exception, so a crashing INJECTION hung for the whole
# watchdog period and then exited 99 instead of failing at once with its traceback.
# Measured on injections C and F.
_wd = threading.Timer(120, lambda: (print("FAIL watchdog >120s"), os._exit(99)))
_wd.daemon = True
_wd.start()

import numpy as np                                                 # noqa: E402
from PyQt6.QtWidgets import QApplication                           # noqa: E402
app = QApplication.instance() or QApplication(sys.argv)

from app.controller import AppController                           # noqa: E402
from app.models.derived_geometry import DerivedOffset              # noqa: E402
from app.models.pipeline_config import PipelineConfig              # noqa: E402
from app.services import user_log                                  # noqa: E402
from app.services.geometry_offset import offset_points             # noqa: E402
from app.views.offset_dialog import OffsetGeometryDialog           # noqa: E402

_seen: list = []
user_log.add_sink(_seen.append)


def said(*words) -> bool:
    return any(all(w in line for w in words) for line in _seen)


N = 240
TH = np.linspace(0.0, 2.0 * math.pi, N, endpoint=False)


def circle(r):
    return np.column_stack((r * np.cos(TH), r * np.sin(TH)))


def seed(ctrl, session, r=1.0, name="body"):
    session.original_points = circle(r)
    session.split_indices = [0, 60, 120, 180, N - 1]
    session.project_model.update_file_segments_from_indices(
        session.split_indices, session.original_points)
    session.project_model.closed_mode = "closed"
    session.project_model.resolve_closure(session.original_points)
    session.display_name = name
    for s in session.project_model.segments:
        s.parameters["n_points"] = 33
    session.project_model.segments[1].bc = "inlet"
    return session


def radius(pts):
    return float(np.hypot(pts[:, 0], pts[:, 1]).mean())


c = AppController()
body = seed(c, c.active_session())
D = 0.2
off = c.create_offset_geometry(body, D)


# ── 1. the offset is an ordinary geometry ─────────────────────────────────── #

check(off is not None and off is not body and off in c.sessions,
      "1a. offsetting the active geometry opens a new geometry of its own")
check(off is not None and off.original_points is not None
      and len(off.original_points) == len(body.original_points),
      "1b. ...ONE point array, of the source's length (%d vs %d)"
      % (len(off.original_points) if off is not None else -1,
         len(body.original_points)))
check(off.split_indices == body.split_indices,
      "1c. ...with the source's split indices, as a LIST (%r vs %r)"
      % (off.split_indices, body.split_indices))
check([(s.id, s.start_index, s.end_index) for s in off.project_model.segments]
      == [(s.id, s.start_index, s.end_index)
          for s in body.project_model.segments],
      "1d. ...and the source's segment ids and boundaries, edge for edge")
check([s.bc for s in off.project_model.segments]
      == [s.bc for s in body.project_model.segments]
      and off.project_model.segments[1].bc == "inlet",
      "1e. ...carrying its per-segment facts too, so nothing is re-declared")
body.project_model.segments[1].bc = "outlet"
check(off.project_model.segments[1].bc == "inlet",
      "1f. ...as a COPY: editing the source's segment does not reach the offset")
body.project_model.segments[1].bc = "inlet"
check(all(s.type == "file" for s in off.project_model.segments)
      and all(getattr(s, "curve_type", "") in ("", "line")
              for s in off.project_model.segments),
      "1g. the offset needs NO new curve type — it is discrete throughout")
want = offset_points(body.original_points, D, True)
check(float(np.abs(off.original_points - want).max()) == 0.0,
      "1h. its points are the offset service's own, bit for bit — one owner")
check(abs(radius(off.original_points) - (1.0 + D / math.cos(math.pi / N))) < 1e-9,
      "1i. ...a circle of r + d (%.9f)" % radius(off.original_points))
dlg = OffsetGeometryDialog("body", True, suggested=0.5)
dlg.distance.setValue(0.25)
dlg.side.setCurrentIndex(1)
check(abs(dlg.signed_distance() + 0.25) < 1e-15,
      "1j. the dialog's magnitude and side combine into ONE signed distance "
      "(%.4f)" % dlg.signed_distance())
dlg.deleteLater()


# ── 2. it records where it came from, visibly ─────────────────────────────── #

rec = off.project_model.derived_from
check(isinstance(rec, DerivedOffset) and rec.source_name == "body"
      and abs(rec.distance - D) < 1e-15,
      "2a. the geometry records its source and its SIGNED distance (%r)" % (rec,))
check("body" in rec.describe() and "0.2" in rec.describe(),
      "2b. ...and describes itself in one line: %r" % rec.describe())
check("body" in off.display_name and "0p2" in off.display_name
      and os.path.splitext(off.display_name)[1] == "",
      "2c. ...which the tab says without opening anything, with a decimal point "
      "that survives being splitext-ed into a file stem (%r)"
      % off.display_name)
check(said("[Offset]", "Created", "body"),
      "2d. ...and the log says what was made, from what, at what distance")


# ── 3. the project round trip carries the record ──────────────────────────── #

tmp = tempfile.mkdtemp(prefix="hybmesh-offset-")
ws_path = os.path.join(tmp, "case.hws")
c._write_workspace_file(ws_path)
raw = json.loads(open(ws_path).read())
stored = [s["project_config"].get("derived_from")
          for s in raw["sessions"]]
check(stored[1] and stored[1].get("source_name") == "body"
      and abs(float(stored[1]["distance"]) - D) < 1e-15,
      "3a. the .hws workspace writes the record down (%r)" % (stored[1],))
check(stored[0] is None,
      "3a. ...and only for the geometry that has one (%r)" % (stored[0],))

script = PipelineConfig.from_configs(
    "offset", [s.project_model for s in c.sessions], None, None)
check(script.cads[1].get("derived_from", {}).get("source_name") == "body",
      "3b. the pipeline script's cads section carries it too (%r)"
      % (script.cads[1].get("derived_from"),))
rebuilt = script.build_project_model(tmp, "out.dat", index=1)
check(rebuilt.derived_from is not None
      and rebuilt.derived_from.source_name == "body",
      "3b. ...and reading that section back restores it")

cfg_path = os.path.join(tmp, "offset.json")
off.project_model.export_config(cfg_path)
from app.models.project import ProjectModel                        # noqa: E402
round_pm = ProjectModel()
round_pm.load_from_config(json.loads(open(cfg_path).read()))
check(round_pm.derived_from is not None
      and round_pm.derived_from.source_name == "body"
      and abs(round_pm.derived_from.distance - D) < 1e-15,
      "3c. the resampler's own JSON config round-trips it as well")

check(DerivedOffset.from_dict({"kind": "sweep", "source_name": "x",
                               "distance": 1.0}) is None
      and DerivedOffset.from_dict({"source_name": "", "distance": 1.0}) is None,
      "3d. a record of another KIND, or with no source, is not read as an "
      "offset — a later derivation is never guessed at")

c._read_workspace_file(ws_path)
app.processEvents()
reopened = [s for s in c.sessions
            if s.project_model.derived_from is not None]
check(len(reopened) == 1
      and reopened[0].project_model.derived_from.source_name == "body"
      and abs(reopened[0].project_model.derived_from.distance - D) < 1e-15,
      "3e. REOPENING the workspace brings the record back, on exactly the one "
      "geometry that had it (%d of %d sessions)"
      % (len(reopened), len(c.sessions)))


# ── 4. regeneration follows an edited source, end to end ──────────────────── #

body = [s for s in c.sessions if s.display_name.lstrip("*") == "body"][0]
off = reopened[0]
body.original_points = circle(2.0)               # the user edits the source
c.active_idx = c.sessions.index(off)
del _seen[:]
c.regenerate_offset_geometry()
check(abs(radius(off.original_points) - (2.0 + D / math.cos(math.pi / N))) < 1e-9,
      "4a. regenerating produces an offset of the EDITED source, measured on "
      "its points (%.9f)" % radius(off.original_points))
check(abs(radius(off.original_points) - 2.0) < 0.2001
      and radius(off.original_points) > 2.0,
      "4b. ...still OUTWARD and still at the recorded distance, not its "
      "magnitude reinterpreted")
check(said("[Offset]", "Regenerated", "body"),
      "4c. ...and says so, naming both geometries")
c.undo()
check(abs(radius(off.original_points) - (1.0 + D / math.cos(math.pi / N))) < 1e-9
      and off.split_indices == body.split_indices,
      "4d. it is ONE undo step, and undo puts the segmentation back too "
      "(%.9f)" % radius(off.original_points))
c.redo()

# The source gains points: the offset re-mirrors rather than keeping stale splits.
body.original_points = circle(2.0)[:120]
body.split_indices = [0, 40, 119]
body.project_model.closed_mode = "open"
body.project_model.update_file_segments_from_indices(
    body.split_indices, body.original_points)
c.regenerate_offset_geometry()
check(len(off.original_points) == 120 and off.split_indices == [0, 40, 119]
      and len(off.project_model.segments) == 2,
      "4e. a source that changed SHAPE re-mirrors its segmentation, never "
      "keeping the old one (%d points, %r)"
      % (len(off.original_points), off.split_indices))
c.undo()
check(len(off.original_points) == N and off.split_indices == [0, 60, 120, 180, N - 1]
      and len(off.project_model.segments) == 4,
      "4f. ...and undoing THAT restores the points AND the segmentation it "
      "replaced, which is the whole reason it is one command (%d points, %r, "
      "%d segments)" % (len(off.original_points), off.split_indices,
                        len(off.project_model.segments)))
c.redo()

# A NEGATIVE recorded distance, on its own controller: with a positive one the
# side is unfalsifiable, and an injection reading the magnitude passed.
c3 = AppController()
inner_src = seed(c3, c3.active_session(), r=1.0, name="duct")
inner = c3.create_offset_geometry(inner_src, -0.3)
check(inner is not None
      and abs(radius(inner.original_points) - (1.0 - 0.3 / math.cos(math.pi / N))) < 1e-9,
      "4g. an INWARD offset is created inward (%.9f)"
      % (radius(inner.original_points) if inner else -1))
inner_src.original_points = circle(1.5)
c3.active_idx = c3.sessions.index(inner)
c3.regenerate_offset_geometry()
check(abs(radius(inner.original_points) - (1.5 - 0.3 / math.cos(math.pi / N))) < 1e-9,
      "4g. ...and regenerating keeps it INWARD — the recorded distance is signed, "
      "not a magnitude re-decided at regeneration time (%.9f)"
      % radius(inner.original_points))


# ── 5. regeneration without its source is refused BY NAME ─────────────────── #

decoy = c._new_session("")
decoy.display_name = "decoy"
decoy.original_points = circle(50.0)
decoy.split_indices = [0, N - 1]
decoy.project_model.update_file_segments_from_indices(
    decoy.split_indices, decoy.original_points)
before = off.original_points.copy()
c.close_tab(c.sessions.index(body))
app.processEvents()
c.active_idx = c.sessions.index(off)
del _seen[:]
c.regenerate_offset_geometry()
check(said("[Offset]", "body"),
      "5a. a regeneration whose source is gone is refused NAMING it: %r"
      % ([ln for ln in _seen if "[Offset]" in ln][:1],))
check(off.original_points.shape == before.shape
      and float(np.abs(off.original_points - before).max()) == 0.0,
      "5b. ...and nothing was changed (%r vs %r)"
      % (off.original_points.shape, before.shape))
check(radius(off.original_points) < 10.0,
      "5c. ...and the one other open geometry was NOT used instead (%.3f)"
      % radius(off.original_points))


# ── 6. the other two refusals say which geometry ──────────────────────────── #

c.active_idx = c.sessions.index(decoy)
del _seen[:]
c.regenerate_offset_geometry()
check(said("[Offset]", "decoy", "not a derived geometry"),
      "6a. regenerating a geometry that was never derived says so, by name: %r"
      % ([ln for ln in _seen if "[Offset]" in ln][:1],))

blank = c._new_session("")
blank.display_name = "blank"
c.active_idx = c.sessions.index(blank)
del _seen[:]
c.offset_active_geometry()
check(said("[Offset]", "blank", "no discrete geometry"),
      "6b. offsetting a geometry with no discrete points is refused by name "
      "and points at Convert to Discrete: %r"
      % ([ln for ln in _seen if "[Offset]" in ln][:1],))
check(said("Convert to Discrete"),
      "6b. ...naming the action that fixes it")


# ── 7. a fold refused in the controller changes nothing ───────────────────── #

c2 = AppController()
src = seed(c2, c2.active_session(), r=1.0, name="ring")
tabs = len(c2.sessions)
del _seen[:]
refused = c2.create_offset_geometry(src, -1.5)
check(refused is None and len(c2.sessions) == tabs,
      "7a. an offset that would fold is refused and opens NO tab (%d)"
      % len(c2.sessions))
line = [ln for ln in _seen if "[Offset]" in ln]
check(bool(line) and "ring" in line[0] and "largest" in line[0],
      "7b. ...and the refusal names the geometry and the largest distance that "
      "works: %r" % (line[:1],))
# Read the number out of the sentence the way a user would, rather than from the
# exception object — the claim is that the MESSAGE carries usable advice.
nums = [float(t) for t in re.findall(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", line[0])]
negatives = [v for v in nums if v < 0.0]
named = negatives[-1] if negatives else None
check(named is not None,
      "7c. ...as a number that can be read out of the sentence (%r)" % (named,))
again = c2.create_offset_geometry(src, named) if named is not None else None
check(again is not None and len(c2.sessions) == tabs + 1,
      "7d. THAT NUMBER, fed back through the same action, succeeds")


print("\n%d checks, %d failed" % (len(_RUN), len(_FAILS)))
if _FAILS:
    print("FAILED:")
    for f in _FAILS:
        print("  - " + f)
os._exit(1 if _FAILS else 0)
