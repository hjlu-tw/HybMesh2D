#!/usr/bin/env python3
"""Do the MESH-stage per-segment edits survive re-saving the geometry?

USER-REPORTED (2026-08-12): "I set the boundaries in Mesh ▸ Edit Seg BC — why do I
get `This mesh has no boundary patch named inlet, outlet`?" The log says exactly
what happened: a CAD edit, Save (which re-runs the resampler), then Generate, and
the mesher's own warning in between —

    NO boundary segment carries any of the 4 GROUP_BC label(s) mapped in this run
    (..._s1, ..._s2, ..._s3, ..._s4) ... Every patch will therefore export as the
    wall default (wall), whatever the config says.

A per-segment BC is TWO halves and they live in two places in the ``.meta``: the
LABEL in the NSEGMENTS bc column, the label→type map in the trailer. The resampler
rewrites the sidecar from the CAD config on every save: the trailer is carried
through verbatim, the bc column comes back ``-``, and the v3 grow column comes back
1 (No BL cleared). So the map outlives its labels, resolves to nothing, and every
patch silently exports as ``wall`` — while the GUI still shows the BCs it holds in
memory. The No-BL flags go the same way.

The fix is not in the resampler: it stopped preserving the prior sidecar on purpose
(a NEW geometry written over an existing output name inherited the old geometry's
flags — see tools/PreProcessor/src/main.cpp). It is the CALLER that knows the file
it is about to overwrite is the same geometry, so the caller snapshots and restores
(``meta_io.snapshot_seg_edits`` / ``restore_seg_edits``).

Pinned here:
  1. The real ``surface_resampler`` really does clear both columns (if it ever
     preserves them, the restore is dead code and this test says so).
  2. snapshot → resample → restore puts labels + No BL back, trailer intact.
  3. A changed segment set is NOT re-applied by id (that would move the inlet onto
     another edge) and is reported as dropped instead.
  4. No snapshot (a new geometry over an existing name) inherits nothing.
  5. All three call sites really snapshot before the run and restore after it:
     interactive Save, GUI Run All, and the headless pipeline runner.

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


def resample(src, out, nseg=4, npts=169):
    """Run the real surface_resampler over `src` -> `out` with `nseg` segments.

    Mirrors what the GUI writes for a file geometry split into edges: one segment
    per side, addressed by start/end index into the source point list.
    """
    exe = os.path.join(_ROOT, "build", "surface_resampler")
    if not os.path.exists(exe):
        return None
    step = (npts - 1) // nseg
    segs = []
    for i in range(nseg):
        s = i * step
        e = (npts - 1) if i == nseg - 1 else (i + 1) * step
        segs.append({"id": i + 1, "type": "file", "start_index": s,
                     "end_index": e, "strategy": "uniform",
                     "parameters": {"n_points": 12}})
    cfg = {"elements": [{"name": "sq", "input_file": src, "output_file": out,
                         "is_closed": True, "segments": segs}]}
    cfg_path = os.path.join(tmp, "cfg.json")
    with open(cfg_path, "w") as f:
        json.dump(cfg, f)
    r = subprocess.run([exe, cfg_path], cwd=_ROOT, capture_output=True, text=True,
                       timeout=60)
    return r


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

# The Mesh stage's own two edits, written exactly as the BC / BL dialogs write them.
LABELS = {1: "sq_s1", 2: "sq_s2", 3: "sq_s3", 4: "sq_s4"}
GROUP_BC = {"sq_s1": "wall", "sq_s2": "inlet", "sq_s3": "wall", "sq_s4": "outlet"}
meta_io.write_meta_segbc(out, LABELS)
meta_io.write_meta_group_bc(out, GROUP_BC)
meta_io.write_meta_seg_growbl(out, {3: False})

# ── 1. the resampler really does clear them ───────────────────────────────
snap = meta_io.snapshot_seg_edits(out)
check(snap["labels"] == LABELS and snap["nobl"] == [3]
      and snap["group_bc"] == GROUP_BC,
      f"1. the snapshot sees both halves plus the No-BL flag ({snap})")

r = resample(src, out, npts=npts)
after = {sid: bc for sid, bc, _k in meta_io.read_meta_segments(out)}
grow_after = meta_io.read_meta_seg_growbl(out)
check(all(not bc for bc in after.values()),
      f"1. re-resampling really does wipe the bc column — the labels the map "
      f"points at are gone ({after})")
check(all(grow_after.values()),
      f"1. ...and clears No BL back to grow-everywhere ({grow_after})")
check(meta_io.read_meta_group_bc(out) == GROUP_BC,
      "1. ...while the trailer survives, which is what leaves the map pointing "
      "at labels that no longer exist (all patches then export as wall)")

# ── 2. the restore puts them back ─────────────────────────────────────────
res = meta_io.restore_seg_edits(out, snap)
check(res["labels"] == LABELS and res["nobl"] == [3] and not res["dropped"],
      f"2. the restore reports exactly what it re-applied ({res})")
back = {sid: bc for sid, bc, _k in meta_io.read_meta_segments(out)}
check(back == LABELS,
      f"2. every label is on its own segment again ({back})")
check(meta_io.read_meta_seg_growbl(out) == {1: True, 2: True, 3: False, 4: True},
      f"2. ...and No BL is back on segment 3 only "
      f"({meta_io.read_meta_seg_growbl(out)})")
check(meta_io.read_meta_group_bc(out) == GROUP_BC,
      "2. ...with the label→type map untouched, so inlet/outlet resolve again")
lines = meta_io.describe_seg_edit_restore(res, GROUP_BC)
check(len(lines) == 1 and "inlet" in lines[0] and "No BL on segment 3" in lines[0],
      f"2. the log line names the BC TYPES, not the internal labels ({lines})")

# Idempotent: the second save of an unchanged geometry says the same thing.
snap2 = meta_io.snapshot_seg_edits(out)
resample(src, out, npts=npts)
check(meta_io.restore_seg_edits(out, snap2)["labels"] == LABELS,
      "2. it survives an arbitrary number of re-saves, not just the first")

# ── 3. a changed segment set is reported, never guessed at ────────────────
# The user removed an edge: ids shift, so re-applying by id would put the inlet on
# a different piece of wall. Refuse and say so.
snap3 = meta_io.snapshot_seg_edits(out)
resample(src, out, nseg=3, npts=npts)
res3 = meta_io.restore_seg_edits(out, snap3)
check(not res3["labels"] and not res3["nobl"] and res3["dropped"] == LABELS,
      f"3. a different segment set is NOT re-applied by id ({res3})")
check(all(not bc for _s, bc, _k in meta_io.read_meta_segments(out)),
      "3. ...and the file is left as the resampler wrote it")
lines3 = meta_io.describe_seg_edit_restore(res3, GROUP_BC)
check(len(lines3) == 1 and lines3[0].startswith("WARNING")
      and "re-apply" in lines3[0],
      f"3. the loss is NAMED with what to do about it — the whole failure mode "
      f"here is that it used to be silent ({lines3})")

# ── 4. no snapshot inherits nothing ───────────────────────────────────────
# A NEW geometry saved over an existing output name must not pick up the previous
# geometry's BCs: that is the bug the resampler's own preservation was reverted
# for, so the caller passing None has to be a hard no-op.
resample(src, out, npts=npts)
check(meta_io.restore_seg_edits(out, None) == {"labels": {}, "nobl": [],
                                              "dropped": {}}
      and all(not bc for _s, bc, _k in meta_io.read_meta_segments(out)),
      "4. restore_seg_edits(None) writes nothing at all")
check(meta_io.describe_seg_edit_restore({"labels": {}, "nobl": [],
                                         "dropped": {}}) == [],
      "4. ...and says nothing, so an ordinary first save stays quiet")
empty = meta_io.snapshot_seg_edits(os.path.join(tmp, "nope.dat"))
check(empty["labels"] == {} and empty["seg_ids"] == [],
      "4. snapshotting a geometry with no sidecar is empty, not an error")

# ── 5. all three call sites are wired the same way ────────────────────────
# The service is only half of it: a save path that forgets to snapshot BEFORE the
# resampler runs reads back the wiped file and restores nothing.
SITES = [("controllers/backend_ctrl.py", "save_output", "_on_save_finished"),
         ("controllers/pipeline_ctrl.py", "_pipe_resample", "_pipe_after_resample"),
         ("services/pipeline_runner.py", "_run_resample", "_run_resample")]
for rel, before_fn, after_fn in SITES:
    src_txt = open(os.path.join(_GUI, "app", rel), encoding="utf-8").read()
    tree = ast.parse(src_txt)
    fns = {n.name: n for n in ast.walk(tree)
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    snap_fn = fns.get(before_fn)
    rest_fn = fns.get(after_fn)
    snap_src = ast.unparse(snap_fn) if snap_fn else ""
    rest_src = ast.unparse(rest_fn) if rest_fn else ""
    check("snapshot_seg_edits" in snap_src,
          f"5. {rel}:{before_fn} snapshots the .meta BEFORE the resampler runs")
    check("restore_seg_edits" in rest_src
          and "describe_seg_edit_restore" in rest_src,
          f"5. {rel}:{after_fn} restores it afterwards AND logs the outcome")

shutil.rmtree(tmp, ignore_errors=True)

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
