#!/usr/bin/env python3
"""A restarted solve plays back as ONE animation across its legs (#32).

#26 moves a finished run's outputs into ``work/prev_<NNN>/`` so a restart can
continue in the same case dir, and #30 leaves a ``RUN.txt`` in each archive
saying how far that leg got. The consequence for the Results tab is that a
restarted solve's field output is SEVERAL files — ``work/xtecp_sol_allz.dat.gui``
plus one per archive — and the transport could only ever animate one of them.

What is pinned here, in three groups:

 1. **``services/result_legs``** — which files are the legs, and in what ORDER.
    A leg is found by its STEM (#30 renames an archived file's tag to
    ``.prev_NNN``, so one output has two spellings); the order is by iteration
    count from ``RUN.txt``, NOT by filename; a leg that ran later and got no
    further is reported as an overlap rather than spliced; a legacy archive with
    no note is played last; and a file outside a case is one leg with no history.

 2. **``models/result_series`` over several files** — one flat frame numbering,
    one LRU byte budget, one value range per variable. The byte-range parse stays
    identical to a whole-file scan (the property ``test_result_playback`` pins for
    one file, re-pinned here ACROSS files, since a wrong ``(file, zone)`` map is
    exactly the way a fast loader starts returning someone else's data).

 3. **The transport and the canvas** — Play crosses a leg boundary without
    interruption, the read-out names the leg, the colour range spans the series, a
    manual clim still wins (#24's precedence unchanged), the variable list is the
    INTERSECTION of the legs, and the offer to open them together is really asked
    (declining loads exactly the file requested).

Every property here was verified by INJECTION — the rule was broken in the real
module and the named check re-run — and two of those injections paid for
themselves at once. One passed with the variable filter DELETED, because the
frame on screen was the leg with FEWER variables, whose own list is already the
intersection; the check now stands on the leg that has more. Another was inert:
``from_file``'s ``path`` argument is unused when an index is supplied (the index
reads through its own path), so "read the wrong file" changes nothing and the
mutation that bites is "read through the wrong leg's INDEX".

Two blind spots, named rather than papered over:

  * Nothing here runs the solver. The legs are written by hand in the layout
    ``case_archive`` produces, which ``test_restart_archive`` pins against the
    real ``prepare_case_dir``; if that layout moves, this test keeps passing
    against a shape nothing produces. What partly closes that is an acceptance
    run recorded here rather than automated: ``results/solver/case`` in this repo
    is a real twice-restarted solve whose archives predate #30, and listing it
    reports ``prev_001, prev_002, latest`` with one known count, 3 frames over
    3 files, a whole-series ``\`r`` range of (14.82, 18.96) and 12 ms for a
    6384-node frame. That run is what found the ordering defect above.
  * The ORDERING axis is ``RUN.txt``'s ``last_iteration``, and a leg without one
    falls back to the order it RAN in. That fallback is right for every case
    except the one it cannot see — a NOTELESS leg that was itself re-run from an
    earlier point — because the note records no per-leg START iteration, which is
    also why ``result_legs`` reports an overlap instead of claiming to resolve
    one.

Run:  python3 tools/PreProcessor/tests/test_result_legs_playback.py
"""
import os
import shutil
import sys
import tempfile
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >180s", flush=True)
    os._exit(99)


_wd = threading.Timer(180, _watchdog)
_wd.daemon = True
_wd.start()

import numpy as np  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.models.result_series import ResultSeries  # noqa: E402
from app.services.result_legs import (  # noqa: E402
    UNKNOWN_ITERATION, leg_stem, list_result_legs,
)
from app.services.restart_points import ARCHIVE, LATEST, OTHER  # noqa: E402
from app.views import result_canvas_setup_mixin as setup_mod  # noqa: E402
from app.views.result_canvas import ResultCanvasView  # noqa: E402

RESULT = "xtecp_sol_allz.dat"


# --------------------------------------------------------------------------- #
# A unit square split into two triangles, written as N zones. ``base`` shifts
# every value so each leg occupies its own value band — which is how a frame
# served from the wrong leg is caught, and how a range that spans only one leg
# is distinguishable from one that spans the series.
# --------------------------------------------------------------------------- #
def write_transient(path, n_zones=3, base=0.0, variables=("p", "u")):
    head = ", ".join(f'"{v}"' for v in ("x", "y") + tuple(variables))
    L = ['Title = "test"', f'variables = {head}']
    nv = len(variables)
    for k in range(n_zones):
        loc = f"[3-{2 + nv}]" if nv > 1 else "[3]"
        L += ['zone t = "time 0" N=4 E=2 ZONETYPE=FETRIANGLE',
              ' DATAPACKING = BLOCK VARLOCATION = ( [1-2] = NODAL, '
              f'{loc} = CELLCENTERED )',
              '0 1 1 0', '0 0 1 1']
        for j in range(nv):
            v0 = base + k + 1.0 + 10.0 * j
            L += [f'{v0} {v0 + 1.0}']
        L += ['1 2 3', '1 3 4']
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")
    return path


def whole_file_parse(path, zone):
    """Reference parse: find the zone by scanning every line, as before."""
    with open(path) as f:
        lines = f.readlines()
    starts = [i for i, ln in enumerate(lines)
              if ln.lstrip().lower().startswith("zone")]
    if zone < 0:
        zone += len(starts)
    end = starts[zone + 1] if zone + 1 < len(starts) else len(lines)
    return np.fromstring("".join(lines[starts[zone] + 2:end]), sep=" ")


def write_note(archive, suffix, iteration, interval=10, stamp="2026-08-20 10:00:00",
               resumed=""):
    """A ``RUN.txt`` in the format ``case_run_note.write_run_note`` writes.

    Written through the REAL writer where possible — but the writer derives the
    iteration count from the archive's own convergence history, and this test
    needs to choose that number, so the note is composed here and read back with
    the real ``read_run_note``. The round trip is what ``test_restart_archive``
    pins; here the point is which number the ordering uses.
    """
    lines = [
        "# HybMesh solver run archive",
        f"archive: {suffix}",
        f"archived_at: {stamp}",
        "run_tag: .gui",
        f"resumed_from: {resumed or 'cold start'}",
        f"zone_dump: binDumpZ.dat.{suffix}",
        f"convergence_file: unicones.enorm.{suffix}",
        f"last_iteration: {iteration}",
        "convergence_rows: 3",
        f"convergence_interval: {interval}",
        "total_bytes: 0",
        "",
        "files: 1",
        f"  unicones.enorm.{suffix}   1 KB",
    ]
    with open(os.path.join(archive, "RUN.txt"), "w") as f:
        f.write("\n".join(lines) + "\n")


def build_case(root, legs, live=(3, 0.0), live_iters=None, live_tag=".gui"):
    """A case dir shaped like ``case_archive`` leaves one.

    ``legs`` is ``[(suffix, n_zones, base, iteration or None), …]`` oldest first;
    ``live`` is ``(n_zones, base)`` for the un-archived leg in ``work/``, whose
    iteration comes from a convergence history rather than from a note (it has
    not been archived, so it has none).
    """
    work = os.path.join(root, "work")
    os.makedirs(work, exist_ok=True)
    for suffix, n, base, iters in legs:
        d = os.path.join(work, suffix)
        os.makedirs(d, exist_ok=True)
        write_transient(os.path.join(d, f"{RESULT}.{suffix}"), n_zones=n,
                        base=base)
        if iters is not None:
            write_note(d, suffix, iters)
    if live is not None:
        n, base = live
        write_transient(os.path.join(work, f"{RESULT}{live_tag}"), n_zones=n,
                        base=base)
        if live_iters is not None:
            with open(os.path.join(work, f"unicones.enorm{live_tag}"), "w") as f:
                f.write(f"1 0.5\n{live_iters} 0.1\n")
        with open(os.path.join(work, "input.in"), "w") as f:
            f.write('print_convg_per_niter 10\nzdump_fn_restart "binDumpZ.dat"\n')
    return work


tmp = tempfile.mkdtemp(prefix="hybmesh_legs_")

# ── 1. the legs: found by stem, ordered by iteration ──────────────────────
check(leg_stem(f"{RESULT}.gui") == RESULT
      and leg_stem(f"{RESULT}.prev_001") == RESULT
      and leg_stem("/a/b/" + RESULT) == RESULT,
      "1. one solver output has two spellings — a run tag while it is live and "
      "#30's archive suffix once it is filed — and both reduce to the same stem")

case = os.path.join(tmp, "case")
work = build_case(case, [("prev_001", 2, 0.0, 500),
                         ("prev_002", 3, 100.0, 1990)],
                  live=(3, 200.0), live_iters=3000)
live_path = os.path.join(work, f"{RESULT}.gui")
found = list_result_legs(live_path)
check(len(found) == 3 and list(found.labels) == ["prev_001", "prev_002", LATEST],
      f"1. every leg of the solve is found — the two archives and the live one — "
      f"oldest solution first ({list(found.labels)})")
check([leg.kind for leg in found.legs] == [ARCHIVE, ARCHIVE, LATEST]
      and [leg.iteration for leg in found.legs] == [500, 1990, 3000],
      f"1. each leg reports how far it got: the archives from their own RUN.txt, "
      f"the live one from the convergence history beside it (it has no note yet) "
      f"({[leg.iteration for leg in found.legs]})")
check(found.warnings == (),
      f"1. a clean chain says nothing — a warning is for a real anomaly, not for "
      f"every restart ({found.warnings})")
check(found.index_of(live_path) == 2 and found.index_of("/nope") == -1,
      "1. the caller can ask which leg it opened without re-deriving the match")

# Order is by ITERATION, not by name: prev_002 re-ran the same leg from an
# earlier point (#31 makes that a click), so it got LESS far than prev_001.
rerun = os.path.join(tmp, "rerun")
rework = build_case(rerun, [("prev_001", 2, 0.0, 1990),
                            ("prev_002", 3, 100.0, 900)],
                    live=(2, 200.0), live_iters=3000)
r = list_result_legs(os.path.join(rework, f"{RESULT}.gui"))
check(list(r.labels) == ["prev_002", "prev_001", LATEST],
      f"1. the legs are ordered by ITERATION COUNT, so a leg re-run from an "
      f"earlier point plays where it belongs in the solve rather than where its "
      f"directory name falls ({list(r.labels)})")
check(any("prev_002" in w and "prev_001" in w and "same part" in w
          for w in r.warnings),
      f"1. ...and the overlap is SAID, naming both legs — the note records no "
      f"start iteration, so it is reported rather than resolved ({r.warnings})")

# A legacy archive (no RUN.txt) has no place on the iteration axis.
legacy = os.path.join(tmp, "legacy")
lwork = build_case(legacy, [("prev_001", 2, 0.0, None),
                            ("prev_002", 2, 100.0, 1990)],
                   live=(2, 200.0), live_iters=3000)
lg = list_result_legs(os.path.join(lwork, f"{RESULT}.gui"))
check(list(lg.labels) == ["prev_001", "prev_002", LATEST]
      and lg.legs[0].iteration == UNKNOWN_ITERATION,
      f"1. a leg with no RUN.txt is played WHERE IT RAN, not last: it is a real "
      f"part of the solve and creation order is the fact that is always there "
      f"({list(lg.labels)})")
check(any("prev_001" in w and "RUN.txt" in w for w in lg.warnings),
      f"1. ...and that it was placed that way is said ({lg.warnings})")

# The case that measures WHY: an archive from before #30 has no note, so a
# "played last" rule sends the NEWEST leg to the front and runs the solve
# backwards. This is the layout of this repo's own results/solver/case.
allold = os.path.join(tmp, "allold")
awork = build_case(allold, [("prev_001", 1, 0.0, None),
                            ("prev_002", 1, 100.0, None)],
                   live=(1, 200.0), live_iters=1990)
ao = list_result_legs(os.path.join(awork, f"{RESULT}.gui"))
check(list(ao.labels) == ["prev_001", "prev_002", LATEST],
      f"1. ...and when only the LIVE leg has a count — every archive predating "
      f"#30 — the solve still plays oldest first instead of newest first "
      f"({list(ao.labels)})")

# An archive that produced no field output is not a leg at all.
noout = os.path.join(tmp, "noout")
nwork = build_case(noout, [("prev_001", 2, 0.0, 500)], live=(2, 100.0))
os.remove(os.path.join(nwork, "prev_001", f"{RESULT}.prev_001"))
n1 = list_result_legs(os.path.join(nwork, f"{RESULT}.gui"))
check(len(n1) == 1 and n1.labels == (LATEST,),
      f"1. an archive holding no field output is skipped, not offered as an "
      f"empty leg ({list(n1.labels)})")

# A file that is not a case's own output has no history, and is still one leg.
loose = write_transient(os.path.join(tmp, "loose.dat"), n_zones=2)
lo = list_result_legs(loose)
check(len(lo) == 1 and lo.legs[0].kind == OTHER and lo.warnings == ()
      and lo.legs[0].path == os.path.abspath(loose),
      "1. a Tecplot file outside a case is ONE leg with no history — so every "
      "caller builds a series the same way instead of branching on None")

# Two hosts in one work dir are two different solves; the file OPENED decides.
both = os.path.join(tmp, "both")
bwork = build_case(both, [("prev_001", 2, 0.0, 500)], live=(2, 100.0),
                   live_tag=".gui")
write_transient(os.path.join(bwork, f"{RESULT}.cli"), n_zones=4, base=900.0)
b_gui = list_result_legs(os.path.join(bwork, f"{RESULT}.gui"))
b_cli = list_result_legs(os.path.join(bwork, f"{RESULT}.cli"))
check(os.path.basename(b_gui.legs[-1].path) == f"{RESULT}.gui"
      and os.path.basename(b_cli.legs[-1].path) == f"{RESULT}.cli",
      "1. a case run by both hosts holds two live outputs, and the one the user "
      "OPENED is the live leg — they are two solves, not two halves of one")

# ── 2. the series over several files ──────────────────────────────────────
paths = list(found.paths)
labels = list(found.labels)
s = ResultSeries(paths, labels=labels)
check(s.n_frames == 8 and s.n_files == 3,
      f"2. the series reports ONE flat frame count over every leg "
      f"(2+3+3={s.n_frames})")
check([s.locate(k) for k in (0, 1, 2, 4, 5, 7)]
      == [(0, 0), (0, 1), (1, 0), (1, 2), (2, 0), (2, 2)],
      "2. a global frame number resolves to (file, zone) — the flat index sits "
      "ABOVE the per-file byte-offset ones rather than replacing them")
check(s.path_of(0) == paths[0] and s.path_of(7) == paths[2],
      "2. ...and the caller can ask which file a frame came from")

# Record and continue rather than abort on the first bad frame: a wrong
# (file, zone) map raises out of ``from_file`` as easily as it returns the wrong
# array, and a raise here would take every check below it with it — the same
# reason the C++ side's check.hpp records instead of aborting.
same = True
for k in range(s.n_frames):
    fi, zi = s.locate(k)
    try:
        r = s.frame(k)
        ref = whole_file_parse(paths[fi], zi)
        got = np.concatenate([r.node_data["x"], r.node_data["y"],
                              r.cell_data["p"], r.cell_data["u"],
                              (r.elements[:2] + 1).astype(float).ravel()])
        same = same and np.array_equal(got, ref)
    except (OSError, ValueError, IndexError) as e:
        print(f"     frame {k} -> {fi},{zi}: {e}", flush=True)
        same = False
check(same,
      "2. a byte-range parse reproduces the whole-file parse EXACTLY for every "
      "frame of every leg — a wrong (file, zone) map is how a fast loader starts "
      "returning another leg's data and still looks like physics")

rng = s.global_range("p")
check(rng == (1.0, 204.0),
      f"2. a value range spans the WHOLE series, not the leg on screen (p runs "
      f"1..204 across the three legs) ({rng})")
one_leg = ResultSeries(paths[2:], labels=labels[2:]).global_range("p")
check(one_leg == (201.0, 204.0) and rng != one_leg,
      f"2. ...and it genuinely differs from the newest leg's own range, which is "
      f"the flat-colour artefact #24 fixed inside one file ({one_leg})")

check(s.frame_label(0) == "prev_001 · Frame 1 / 2"
      and s.frame_label(5) == "latest · Frame 1 / 3",
      f"2. a frame is labelled by LEG and its position within that leg — "
      f"'Frame 4 / 8' alone says nothing across a restarted solve "
      f"({s.frame_label(5)!r})")
solo = ResultSeries(paths[0], labels=["prev_001"])
check(solo.frame_label(0) == "Frame 1 / 2",
      f"2. a ONE-file series is labelled exactly as it was, even when handed a "
      f"leg name: there is nothing to distinguish it from ({solo.frame_label(0)!r})")

tiny = ResultSeries(paths, labels=labels, max_bytes=1)
for k in range(tiny.n_frames):
    tiny.frame(k)
check(tiny.cached_frames() == 1,
      f"2. the BYTE cap is one budget over the whole series, not one per leg — "
      f"a solve restarted ten times must not hold ten caches "
      f"({tiny.cached_frames()})")

# A leg rewritten under an open Results tab renumbers every frame after it, so
# the frames AND the ranges have to go, not just that file's.
churn_dir = os.path.join(tmp, "churn")
os.makedirs(churn_dir, exist_ok=True)
c1 = write_transient(os.path.join(churn_dir, "a.dat"), n_zones=2, base=0.0)
c2 = write_transient(os.path.join(churn_dir, "b.dat"), n_zones=2, base=100.0)
cs = ResultSeries([c1, c2], labels=["a", "b"])
cs.frame(0)
cs.frame(3)
cs.global_range("p")
write_transient(c1, n_zones=4, base=0.0)
os.utime(c1, (0, 0))                     # force a distinct stamp
check(cs.n_frames == 6 and cs.cached_frames() == 0
      and not cs.has_global_range("p"),
      f"2. a leg that gained zones renumbers the series, so EVERY cached frame "
      f"and range is dropped — one kept under its old global number would serve "
      f"another leg's zone ({cs.n_frames}, {cs.cached_frames()})")
check(cs.locate(4) == (1, 0),
      f"2. ...and the flat map really moved with it ({cs.locate(4)})")

gone = ResultSeries([c1, os.path.join(churn_dir, "not-there.dat"), c2],
                    labels=["a", "x", "b"])
check(gone.n_files == 2 and gone.labels == ["a", "b"] and gone.n_frames == 6,
      f"2. an unreadable leg is dropped WITH its label, before anything is "
      f"numbered — a deleted archive must not cost the whole animation "
      f"({gone.labels})")

# Legs may disagree about variables: the selector gets the intersection.
vdir = os.path.join(tmp, "vars")
os.makedirs(vdir, exist_ok=True)
v_full = write_transient(os.path.join(vdir, "full.dat"), n_zones=2,
                         variables=("p", "u", "M"))
v_thin = write_transient(os.path.join(vdir, "thin.dat"), n_zones=2,
                         variables=("p", "u"))
vs = ResultSeries([v_full, v_thin], labels=["prev_001", "latest"])
check(vs.variables == ["x", "y", "p", "u"],
      f"2. the series' variables are the INTERSECTION of its legs — a variable "
      f"only some frames carry would blank out at every boundary that lacks it "
      f"({vs.variables})")
check(vs.variable_gaps() == [("latest", ("M",))],
      f"2. ...and which leg is short of what is answerable, so the subtraction "
      f"can be said out loud instead of a variable quietly leaving the list "
      f"({vs.variable_gaps()})")

# ── 3. the transport and the canvas ──────────────────────────────────────
_asked = []
_answer = [True]
_real_confirm = setup_mod.confirm


def fake_confirm(*a, **k):
    _asked.append((a, k))
    return _answer[0]


setup_mod.confirm = fake_confirm

v = ResultCanvasView()
v.load_result_path(live_path)
check(len(_asked) == 1 and _asked[0][1].get("headless_default") is False,
      f"3. loading a result in a case with archives ASKS, and the headless "
      f"answer is No — a batch run asked for one file and keeps getting one "
      f"({_asked[0][1].get('headless_default') if _asked else None})")
check(v._series is not None and v._series.n_files == 3
      and v._frame_count() == 8,
      f"3. answering Yes plays the whole solve: 8 frames over 3 legs "
      f"({v._frame_count()})")
check(v._frame == 7,
      f"3. ...and it opens on the LAST frame of the NEWEST leg, which is still "
      f"the most-converged solution ({v._frame})")
check(v.zone_combo.count() == 8
      and v.zone_combo.itemText(0).startswith("prev_001")
      and v.zone_combo.currentIndex() == 7,
      f"3. the zone selector lists every frame of the series and names the leg, "
      f"so the selector and the read-out say the same thing "
      f"({v.zone_combo.itemText(0)!r})")
check(v.frame_label.text() == "latest · Frame 3 / 3",
      f"3. the frame read-out names the leg ({v.frame_label.text()!r})")

# Play crosses every boundary without interruption.
v.go_to_end(-1)
check(v._frame == 0 and v._series.path_of(0) == paths[0],
      "3. First jumps to the first frame of the OLDEST leg")
seen = [v._series.path_of(v._frame)]
v.start_playback()
for _ in range(20):
    v._advance_frame()
    seen.append(v._series.path_of(v._frame))
    if not v._playing:
        break
check(v._frame == 7 and not v._playing
      and [p for i, p in enumerate(seen) if i == 0 or seen[i - 1] != p] == paths,
      f"3. Play runs from the first frame of the oldest leg to the last of the "
      f"newest in one pass, visiting the legs in order and stopping there "
      f"(ended at frame {v._frame}, playing={v._playing})")

v.loop_cb.setChecked(True)
v._advance_frame()
check(v._frame == 0,
      "3. Loop wraps from the last frame of the newest leg to the first of the "
      "oldest — the whole series is the loop, not the last leg")
v.step_frame(-1)
check(v._frame == 7,
      "3. ...and Prev wraps the other way over the whole series")
v.loop_cb.setChecked(False)
v.show_frame(2)
check(v.prev_btn.isEnabled() and v.next_btn.isEnabled(),
      "3. a leg boundary is NOT an end of the run: both step buttons stay live "
      "in the middle of the series")
v.go_to_end(1)
check(v._frame == 7 and not v.next_btn.isEnabled(),
      "3. Last lands on the final frame of the whole series and greys out there")

# The triangulation (and so the probes pinned to it) survives a leg boundary.
v.show_frame(1)
tri = v._triang
v._probes = [(0.5, 0.5)]
v.show_frame(2)                       # prev_001 -> prev_002
check(v._triang is tri and v._probes == [(0.5, 0.5)],
      "3. crossing a leg boundary on the same mesh reuses the triangulation and "
      "keeps the probes — they mark GEOMETRY, and the geometry did not move")

# The colour lock spans the series; a manual range still wins (#24 unchanged).
v.select_variable("p")
v.set_clim_auto(True)
v.lock_scale_cb.setChecked(True)
check(v.playback_clim() == (1.0, 204.0),
      f"3. Lock scale pins the range over EVERY leg, so colours mean the same "
      f"thing across the whole solve ({v.playback_clim()})")
v.set_clim(-1.0, 1.0)
check(v.playback_clim() is None and v.manual_clim("p") == (-1.0, 1.0),
      "3. ...and a range typed by hand still wins over it — #24's precedence is "
      "untouched by there being several legs")
v.set_clim_auto(True)

# The per-variable seeded range is one range for the whole series: it is stored
# per VARIABLE, not per file, so a leg boundary cannot re-seed (and so drift) it.
v.show_frame(0)
v.reset_clim_store()          # the manual range above was this variable's
v.set_clim_auto(False)
v.render()
seeded = v.manual_clim("p")
v.show_frame(7)
check(v.manual_clim("p") == seeded and seeded == (1.0, 2.0),
      f"3. the per-variable seeded range is remembered ACROSS legs, so playback "
      f"does not re-seed itself at every boundary ({v.manual_clim('p')})")
v.set_clim_auto(True)

# Declining loads exactly the file that was asked for.
_answer[0] = False
_asked.clear()
v2 = ResultCanvasView()
v2.load_result_path(live_path)
check(len(_asked) == 1 and v2._series.n_files == 1
      and v2._series.paths == [live_path] and v2._frame_count() == 3,
      f"3. declining loads ONLY the file requested — opening one leg on its own "
      f"stays a normal thing to do ({v2._series.paths})")
check(v2.frame_label.text() == "Frame 3 / 3",
      f"3. ...and that one file is labelled the way it always was "
      f"({v2.frame_label.text()!r})")

_asked.clear()
v3 = ResultCanvasView()
v3.load_result_path(live_path, ask_legs=False)
check(_asked == [] and v3._series.n_files == 1,
      "3. ask_legs=False does not ask at all — a pipeline or batch run reaches "
      "this from the solver's finished handler and must not stop on a modal")

# A single-leg case is not a restarted solve: nothing is offered.
_asked.clear()
solo_case = os.path.join(tmp, "solo")
swork = build_case(solo_case, [], live=(3, 0.0), live_iters=100)
v4 = ResultCanvasView()
v4.load_result_path(os.path.join(swork, f"{RESULT}.gui"))
check(_asked == [] and v4._frame_count() == 3
      and v4.frame_label.text() == "Frame 3 / 3",
      f"3. a case that was never restarted has one leg, so there is nothing to "
      f"offer and nothing to rename ({v4.frame_label.text()!r})")

# The variable list is the intersection, and the subtraction is logged.
_answer[0] = True
_asked.clear()
vcase = os.path.join(tmp, "vcase")
vwork = build_case(vcase, [("prev_001", 2, 0.0, 500)], live=(2, 100.0),
                   live_iters=1000)
# Rewrite the two legs so the archive carries a variable the live one does not.
write_transient(os.path.join(vwork, "prev_001", f"{RESULT}.prev_001"),
                n_zones=2, base=0.0, variables=("p", "u", "M"))
write_transient(os.path.join(vwork, f"{RESULT}.gui"), n_zones=2, base=100.0,
                variables=("p", "u"))
said = []
v5 = ResultCanvasView()
v5._log = lambda m: said.append(m)
v5.load_result_path(os.path.join(vwork, f"{RESULT}.gui"))
# Stand on a frame of the RICH leg. Asking from the thin one proves nothing:
# that frame's own variable list is already the intersection, so the check
# passes with the filter DELETED — measured, and the reason this line exists.
v5.show_frame(0)
offered = [v5.var_combo.itemData(i) for i in range(v5.var_combo.count())]
check(v5._series.n_files == 2 and v5._series.path_of(0).endswith(".prev_001")
      and "M" not in offered and "p" in offered,
      f"3. the variable selector offers only what EVERY leg carries, ASKED FROM "
      f"THE LEG THAT HAS MORE — the animation never changes subject part-way "
      f"through ({offered})")
check(any("does not carry" in m and "M" in m for m in said),
      f"3. ...and the leg that is short of it is named, because a silent "
      f"subtraction reads as a variable that was never there ({said})")

setup_mod.confirm = _real_confirm
shutil.rmtree(tmp, ignore_errors=True)

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
