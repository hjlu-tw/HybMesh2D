#!/usr/bin/env python3
"""Do the MESH-stage per-segment edits survive re-saving the geometry?

USER-REPORTED (2026-08-12): "I set the boundaries in Mesh ▸ Edit Seg BC — why do I
get `This mesh has no boundary patch named inlet, outlet`?" The log said exactly
what happened: a CAD edit, Save (which re-runs the resampler), then Generate, and
the mesher's own warning in between —

    NO boundary segment carries any of the 4 GROUP_BC label(s) mapped in this run
    (..._s1, ..._s2, ..._s3, ..._s4) ... Every patch will therefore export as the
    wall default (wall), whatever the config says.

A per-segment BC is TWO halves living in two places in the ``.meta``: the LABEL in
the NSEGMENTS bc column, the label->type map in the trailer. The resampler rewrites
the sidecar from the CAD config on every save: the trailer is carried through
verbatim, the bc column comes back ``-``, and the v3 grow column comes back 1 (No
BL cleared). So the map outlived its labels, resolved to nothing, and every patch
silently exported as ``wall`` — while the GUI still showed the BCs it held in
memory. The No-BL flags went the same way.

WHERE THE FIX WENT, and why not either of the two obvious places. Not the
resampler: it stopped preserving the prior sidecar on purpose, because a NEW
geometry written over an existing output name then inherited the old geometry's
flags (tools/PreProcessor/src/main.cpp says so in a comment). And not a wrapper
around the subprocess either, which is what shipped first — three call sites
snapshotting the sidecar before the run and re-applying after, each having to
REFUSE itself whenever the segment id set had changed, since re-applying by id
after a subprocess rewrote the file would move the inlet onto another piece of
wall. That refusal was correct where it sat and still a silent loss of the user's
edit.

Both facts are now SegmentModel FIELDS (``bc`` already was one; ``grow_bl`` is
new), so they travel in the config the GUI writes for the resampler — which has
always read ``sj["bc"]`` and ``sj["grow_bl"]`` — and the sidecar is written
correctly the FIRST time. The fact moved UP, not back down: the model knows which
geometry it is describing and the resampler does not, which is why the reverted
failure mode cannot return. The sidecar is now a PROJECTION of the model,
rewritten after every edit, undo and redo.

Pinned here, against the real ``surface_resampler`` rather than a stub:
  1. The wipe is real. A config that does NOT carry the facts still clears both
     columns — so if the resampler ever starts preserving them, this says so
     rather than letting a redundant mechanism look load-bearing.
  2. A config that DOES carry them (i.e. SegmentModel.to_dict()) comes back with
     both columns intact, through the binary.
  3. The reverted failure mode stays dead: a new geometry written over an existing
     output name inherits nothing from the file it overwrites.
  4. The real controller handler puts the edit on the model, undoably, and the
     sidecar follows the model on execute AND on undo.
  5. The id-set-changed refusal is gone as a concept: a label rides the segment
     object, so adding an edge cannot move it onto another one.
  6. Both facts reach the workspace and the pipeline script, because all three
     writers go through the same to_dict().
  7. The removed compensation has no callers and no definitions left.

Run:  python3 tools/PreProcessor/tests/test_seg_edit_carryover.py
"""
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >120s", flush=True)
    os._exit(99)


_wd = threading.Timer(120, _watchdog)
_wd.daemon = True
_wd.start()

from app.services import meta_io  # noqa: E402

tmp = tempfile.mkdtemp(prefix="hybmesh_segedit_")


# --------------------------------------------------------------------------- #
def write_square(path, n=13):
    """A closed square polyline: 4 sides, so 4 file segments to assign BCs to."""
    pts = []
    for x in range(n):
        pts.append((x / (n - 1.0), 0.0))
    for y in range(1, n):
        pts.append((1.0, y / (n - 1.0)))
    for x in range(1, n):
        pts.append((1.0 - x / (n - 1.0), 1.0))
    for y in range(1, n):
        pts.append((0.0, 1.0 - y / (n - 1.0)))
    with open(path, "w") as f:
        for x, y in pts:
            f.write(f"{x:.10f} {y:.10f}\n")
    return len(pts)


def seg_dicts(nseg, npts, edits=None):
    """The per-segment config the GUI writes, built from real SegmentModels.

    Deliberately not hand-authored JSON: the whole property under test is that
    ``SegmentModel.to_dict()`` is what carries the two facts to the resampler, so
    a literal dict here would prove something the GUI does not do.
    """
    from app.models.segment import SegmentModel
    step = (npts - 1) // nseg
    out = []
    for i in range(nseg):
        s0 = i * step
        e0 = (npts - 1) if i == nseg - 1 else (i + 1) * step
        seg = SegmentModel(i + 1, s0, e0)
        seg.strategy = "uniform"
        seg.parameters = {"n_points": 12}
        for field, val in (edits or {}).get(i + 1, {}).items():
            setattr(seg, field, val)
        out.append(seg.to_dict())
    return out


def resample(src, out, nseg=4, npts=169, edits=None, name="sq"):
    """Run the real surface_resampler over `src` -> `out` with `nseg` segments."""
    exe = os.path.join(_ROOT, "build", "surface_resampler")
    if not os.path.exists(exe):
        return None
    cfg = {"elements": [{"name": name, "input_file": src, "output_file": out,
                         "is_closed": True,
                         "segments": seg_dicts(nseg, npts, edits)}]}
    cfg_path = os.path.join(tmp, "cfg.json")
    with open(cfg_path, "w") as f:
        json.dump(cfg, f)
    return subprocess.run([exe, cfg_path], cwd=_ROOT, capture_output=True,
                          text=True, timeout=60)


def columns(path):
    """(bc labels, grow flags) as the sidecar currently holds them."""
    return ({sid: bc for sid, bc, _k in meta_io.read_meta_segments(path)},
            meta_io.read_meta_seg_growbl(path))


src = os.path.join(tmp, "square.dat")
npts = write_square(src)
out = os.path.join(tmp, "square_resampled.dat")

r = resample(src, out, npts=npts)
if r is None:
    print("SKIP surface_resampler not built — run ./build.sh", flush=True)
    _wd.cancel()
    shutil.rmtree(tmp, ignore_errors=True)
    os._exit(0)
check(r.returncode == 0 and os.path.exists(out + ".meta"),
      f"0. (precondition) the resampler produced a .meta ({r.returncode})")
segs = meta_io.read_meta_segments(out)
check(len(segs) == 4,
      f"0. (precondition) it lists the 4 segments the config declared ({segs})")

LABELS = {1: "sq_s1", 2: "sq_s2", 3: "sq_s3", 4: "sq_s4"}
GROUP_BC = {"sq_s1": "wall", "sq_s2": "inlet", "sq_s3": "wall", "sq_s4": "outlet"}

# ── 1. the wipe is real ───────────────────────────────────────────────────────
# Write the two facts straight onto the sidecar (as the dialogs used to), then
# re-resample from a config that does NOT carry them.
meta_io.write_meta_segbc(out, LABELS)
meta_io.write_meta_group_bc(out, GROUP_BC)
meta_io.write_meta_seg_growbl(out, {3: False})
r = resample(src, out, npts=npts)
bc_after, grow_after = columns(out)
check(all(not v for v in bc_after.values()),
      f"1. the real resampler still clears the bc column ({bc_after})")
check(grow_after.get(3) is True,
      f"1. and still resets the v3 grow column ({grow_after})")
check(meta_io.read_meta_group_bc(out) == GROUP_BC,
      "1. while carrying the GROUP_BC trailer through verbatim")

# ── 2. the model carries them THROUGH the binary ──────────────────────────────
EDITS = {1: {"bc": "sq_s1"}, 2: {"bc": "sq_s2"}, 3: {"bc": "sq_s3", "grow_bl": False},
         4: {"bc": "sq_s4"}}
r = resample(src, out, npts=npts, edits=EDITS)
bc_after, grow_after = columns(out)
check(r.returncode == 0, f"2. resample with the fields present succeeds ({r.returncode})")
check(bc_after == LABELS,
      f"2. every bc label comes back from the config alone ({bc_after})")
check(grow_after == {1: True, 2: True, 3: False, 4: True},
      f"2. and so does the No-BL flag ({grow_after})")

# The mesher is the consumer, so prove the column it version-gates is really v3.
with open(out + ".meta") as f:
    first = f.readline().split()
check(first[:1] == ["HYBMESH_META"] and int(first[1]) >= 3,
      f"2. the sidecar is v3+, so the mesher reads the grow column ({first})")

# ── 3. the reverted failure mode stays dead ───────────────────────────────────
# A DIFFERENT geometry written over the same output name must inherit nothing —
# this is exactly why sidecar preservation was reverted from the resampler.
src2 = os.path.join(tmp, "square2.dat")
npts2 = write_square(src2, n=9)
r = resample(src2, out, npts=npts2, name="other")
bc_after, grow_after = columns(out)
check(all(not v for v in bc_after.values()) and all(grow_after.values()),
      f"3. a new geometry over an existing output name inherits nothing "
      f"({bc_after}, {grow_after})")

# ── 4. the real controller handler: model first, sidecar as a projection ──────
resample(src, out, npts=npts, edits=EDITS)   # back to the edited geometry
from app.controllers.mesh_layers_ctrl import MeshLayersControllerMixin  # noqa: E402
from app.models.session import GeometrySession  # noqa: E402
from app.models.segment import SegmentModel  # noqa: E402


class _Host(MeshLayersControllerMixin):
    """Just enough controller to drive the real handler: sessions + a log sink."""

    def __init__(self, session):
        self.sessions = [session]
        self.lines = []

    def log(self, msg):
        self.lines.append(msg)


sess = GeometrySession()
sess.project_model.output_file = out
sess.project_model.segments = [SegmentModel(i, 0, 1) for i in (1, 2, 3, 4)]
for seg in sess.project_model.segments:
    seg.bc = LABELS[seg.id]
sess.project_model.segments[2].grow_bl = False
host = _Host(sess)

check(host._session_for_geom_path(out) is sess,
      "4. the handler finds the session whose output_file IS this geometry")
check(host._session_for_geom_path(os.path.join(tmp, "nobody.dat")) is None,
      "4. and returns None for a geometry no session owns")

host.handle_seg_grow_bl_changed(out, {1: True, 2: False, 3: False, 4: True})
check(sess.project_model.segments[1].grow_bl is False,
      "4. the No-BL edit landed on the SegmentModel")
_, grow_after = columns(out)
check(grow_after == {1: True, 2: False, 3: False, 4: True},
      f"4. and the sidecar was rewritten from the model ({grow_after})")
check(any("segment 2" in ln for ln in host.lines),
      f"4. the edit is named in the user log ({host.lines})")

check(sess.command_history.can_undo,
      "4. the edit is on the undo stack (it was pushed as a command)")
sess.command_history.undo()
check(sess.project_model.segments[1].grow_bl is True,
      "4. undo reverses the No-BL edit on the model")
_, grow_after = columns(out)
check(grow_after == {1: True, 2: True, 3: False, 4: True},
      f"4. and the sidecar follows the undo, not just the model ({grow_after})")
sess.command_history.redo()
_, grow_after = columns(out)
check(grow_after.get(2) is False,
      f"4. redo re-applies to both ({grow_after})")

# The BC half goes through the identical path.
host.handle_seg_bc_labels_changed(out, {2: "inlet"})
check(sess.project_model.segments[1].bc == "inlet",
      "4. a Mesh-stage BC label lands on the model too")
bc_after, _ = columns(out)
check(bc_after.get(2) == "inlet",
      f"4. and reaches the sidecar ({bc_after})")

# ── 5. the id-set-changed refusal is gone as a concept ────────────────────────
# The old restore had to drop everything when the id set moved. A field rides the
# object, so inserting an edge cannot shift a label onto its neighbour.
before = {s.id: (s.bc, s.grow_bl) for s in sess.project_model.segments}
newseg = SegmentModel(99, 0, 1)
sess.project_model.segments.insert(1, newseg)
after = {s.id: (s.bc, s.grow_bl) for s in sess.project_model.segments if s.id != 99}
check(after == before,
      f"5. inserting a segment moves no label or flag ({before} -> {after})")
check(newseg.grow_bl is True and newseg.bc == "",
      "5. and the new segment starts at the defaults (grow, inherit)")

# ── 6. both facts reach the workspace and the pipeline script ─────────────────
off = SegmentModel(7, 0, 1)
off.grow_bl = False
off.bc = "outlet"
rt = SegmentModel.from_dict(7, off.to_dict())
check(rt.grow_bl is False and rt.bc == "outlet",
      "6. to_dict/from_dict round-trips both facts")
check("grow_bl" not in SegmentModel(8, 0, 1).to_dict(),
      "6. and emits nothing when the flag is at its default, so old files are byte-identical")

# Not just "the writer calls to_dict" — read the flag back out of a real script
# and a real workspace payload, since those are the two files the acceptance
# criterion names.
from app.models.pipeline_config import PipelineConfig  # noqa: E402

pm = sess.project_model
pm.input_file = src
pm.output_file = out
sec = PipelineConfig.cad_section(pm)
scripted = {sd["id"]: sd for sd in sec["segments"]}
check(scripted.get(2, {}).get("grow_bl") is False
      and scripted.get(2, {}).get("bc") == "inlet",
      f"6. the pipeline script's cads section carries both facts ({scripted.get(2)})")

# The workspace writer is the same to_dict, so round-trip through a real file to
# prove the flag comes back on load rather than only going out on save.
ws = os.path.join(tmp, "case.hws")
with open(ws, "w") as f:
    json.dump({"segments": [sg.to_dict() for sg in pm.segments]}, f)
loaded = [SegmentModel.from_dict(i, sd)
          for i, sd in enumerate(json.load(open(ws))["segments"])]
by_id = {sg.id: sg for sg in loaded}
check(by_id[2].grow_bl is False and by_id[2].bc == "inlet",
      "6. a saved-then-reloaded workspace payload still carries both facts")

_writers = {
    "app/models/project.py": "the resampler config",
    "app/controllers/session_io_ctrl.py": "the .hws workspace",
    "app/models/pipeline_config.py": "the pipeline script",
}
for rel, what in _writers.items():
    txt = open(os.path.join(_GUI, rel), encoding="utf-8").read()
    check("to_dict() for s" in txt or "seg.to_dict() for seg" in txt
          or "s.to_dict() for s" in txt,
          f"6. {what} serialises segments through to_dict() ({rel})")

# ── 7. the removed compensation is really gone ────────────────────────────────
_GONE = ("snapshot_seg_edits", "restore_seg_edits", "describe_seg_edit_restore")
offenders = []
for dirpath, _dirs, files in os.walk(os.path.join(_GUI, "app")):
    for fn in sorted(f for f in files if f.endswith(".py")):
        full = os.path.join(dirpath, fn)
        rel = os.path.relpath(full, _GUI)
        tree = ast.parse(open(full, encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in _GONE:
                offenders.append(f"{rel}:{node.lineno} defines {node.name}")
            elif isinstance(node, ast.Attribute) and node.attr in _GONE:
                offenders.append(f"{rel}:{node.lineno} calls .{node.attr}")
            elif isinstance(node, ast.Name) and node.id in _GONE:
                offenders.append(f"{rel}:{node.lineno} references {node.id}")
check(not offenders,
      "7. the snapshot/restore compensation has no definitions or callers left"
      + (f": {offenders[:4]}" if offenders else ""))

_wd.cancel()
shutil.rmtree(tmp, ignore_errors=True)
print()
if _FAILS:
    print(f"{len(_FAILS)} FAILURE(S)")
    for f in _FAILS:
        print("  - " + f)
    os._exit(1)
print("All per-segment carry-over checks passed.")
os._exit(0)
