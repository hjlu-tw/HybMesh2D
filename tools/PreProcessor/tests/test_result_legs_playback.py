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
    ``.prev_NNN``, so one output has two spellings); every leg's SPAN comes from
    ``case_run_note.iteration_span``, so an archive predating ``RUN.txt`` reports
    a real count from its own convergence history instead of "unknown"; the order
    is by that corrected count, NOT by filename; an overlap is a measurement —
    interval intersection over the half-open ``(start, end]`` — reported and
    never spliced, with lineage as the fallback where a span cannot be computed;
    a leg measurable NEITHER way is played WHERE IT RAN; the legs are filtered to
    the RUN the opened file belongs to; and a file outside a case is one leg with
    no history.

 2. **``models/result_series`` over several files** — one flat frame numbering,
    one LRU byte budget, one value range per variable. The byte-range parse stays
    identical to a whole-file scan (the property ``test_result_playback`` pins for
    one file, re-pinned here ACROSS files, since a wrong ``(file, zone)`` map is
    exactly the way a fast loader starts returning someone else's data).

 3. **The transport and the canvas** — Play crosses a leg boundary without
    interruption, the read-out names the leg, the colour range spans the series, a
    manual clim still wins (#24's precedence unchanged), the variable list is the
    INTERSECTION of the legs, and opening a leg opens the SOLVE without asking
    (#43 removed #32's per-load modal and its permission flag). ``This leg only``
    is the escape: shown only when the solve HAS more than one leg, unticked on
    every load, landing on the same frame. The whole-series colour scan runs when
    Auto is unticked rather than inside ``render``, and a FAILED scan is not
    remembered.

Every property here was verified by INJECTION — the rule was broken in the real
module and the named check re-run — and four of those injections paid for
themselves. One passed with the variable filter DELETED, because the frame on
screen was the leg with FEWER variables, whose own list is already the
intersection; the check now stands on the leg that has more. Another was inert:
``from_file``'s ``path`` argument is unused when an index is supplied (the index
reads through its own path), so "read the wrong file" changes nothing and the
mutation that bites is "read through the wrong leg's INDEX". Two more found
missing checks rather than a defect: the suite stayed GREEN with the
``This leg only`` reset deleted and with a failed range scan recorded as the
answer, so both now have properties of their own.

**Two injections are PERMANENT here, because the obvious construction of each
passes with the code removed.**

  * *The convergence fallback* is injected on the legs that HAVE a run note
    (``case_run_note._iteration_rows`` patched to read nothing). Their ends still
    come from those notes, so what the injection removes is the START — and with
    it the overlap the check above reports. Injected on a note-LESS leg it would
    prove only that a count appears at all; this direction pins the rule that is
    cheapest to delete unnoticed, that the file is read even when a note has
    already answered "how far". The note-less direction is checked too, one
    property later, where the count itself is what is at stake.
  * *The run-tag filter* is injected in the direction that FAILS: an older
    headless leg opened in a case whose archives belong to the interactive run.
    Opening the ``.gui`` leg gets the ``.gui`` archive with or without the filter,
    so a check built that way certifies a filter that is not there — the
    assertion therefore covers both directions and says which one is evidence.

Both injections have a negative control: making the patch call the real function
turns the checks red, so they cannot pass because the injection was inert.

Two blind spots, named rather than papered over:

  * Nothing here runs the solver. The legs are written by hand in the layout
    ``case_archive`` produces, which ``test_restart_archive`` pins against the
    real ``prepare_case_dir``; if that layout moves, this test keeps passing
    against a shape nothing produces. The corrected endpoint arithmetic is
    likewise pinned against the two figures this repo already measured against
    the real binary (#26's 990 -> 1000, #30's 1990 -> 2000), not against a fresh
    run. What partly closes both is an acceptance run recorded here rather than
    automated: ``results/solver/case`` is a real twice-restarted solve whose two
    archives predate #30, and under #43 it reports

      prev_001  (0, 1000]   prev_002  (0, 1000]   latest  (1000, 2000]

    all three recomputed from their own convergence histories, interval 10 —
    where #32 reported "iteration unknown" for both archives. The overlap that
    follows, ``prev_001`` and ``prev_002`` both covering iterations 1-1000, was
    SILENT before this and is now named. The restart chooser reports the same
    three numbers for the same folders, which is the point of there being one
    ``iteration_span``. 3 frames over 3 files, 11 ms for a 6384-node frame,
    ``last_frame_of`` landing on frame 0 for ``prev_001`` and 2 for the live leg.
    An earlier version of that same run is what found the backwards-ordering
    defect this file's group 1 exists for.
  * The ordering axis is the corrected ``end``, and a leg measurable NEITHER by a
    note nor by a convergence history still falls back to the order it RAN in.
    That fallback is right for every case except the one it cannot see — such a
    leg re-run from an earlier point — which is also why ``result_legs`` reports
    an overlap instead of claiming to resolve one. #43 demoted it from the first
    line of defence to the third, so the set of legs it applies to is now much
    smaller: a pre-#30 archive that still holds its history is no longer in it.

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
from app.services import case_run_note, result_legs  # noqa: E402
from app.services.case_files import RUN_NOTE_NAME as RUN_NOTE  # noqa: E402
from app.services.result_legs import (  # noqa: E402
    leg_stem, list_result_legs,
)
from app.services.restart_points import ARCHIVE, LATEST, OTHER  # noqa: E402
from app import utils as utils_mod  # noqa: E402
from app.views.result_canvas import ResultCanvasView  # noqa: E402

RESULT = "xtecp_sol_allz.dat"
#: "we could not tell how far that run got" — case_run_note's, one spelling.
UNKNOWN = case_run_note.UNKNOWN_ITERATION


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


def write_convg(path, rows, interval=10):
    """A convergence history: one row every ``interval`` iterations.

    ``rows`` is ``(first, last)``. A real archive holds one of these, and #43 is
    what makes the playback side read it — a leg's SPAN, where it took over as
    well as where it got to, is recovered from the file's own first row, last row
    and spacing. A fixture with notes but no histories can only ever exercise the
    note, which is the state this gate was in.
    """
    first, last = rows
    with open(path, "w") as f:
        f.write("".join(f"{n}   1.5e-16  5.5e-03\n"
                        for n in range(first, last + 1, interval)))


def build_case(root, legs, live=(3, 0.0), live_rows=None, live_tag=".gui"):
    """A case dir shaped like ``case_archive`` leaves one.

    ``legs`` is ``[(suffix, n_zones, base, note iteration or None[, convg rows]),
    …]`` oldest first: the 4th item writes a ``RUN.txt`` recording that last row,
    the optional 5th writes the convergence history that leg archived. The two are
    independent on purpose — a pre-#30 archive has only the history, and a fixture
    with only the note is what proves ``start`` is read from the file even when
    ``end`` is recorded.

    ``live`` is ``(n_zones, base)`` for the un-archived leg in ``work/``, whose
    span comes from ``live_rows`` (it has not been archived, so it has no note).
    """
    work = os.path.join(root, "work")
    os.makedirs(work, exist_ok=True)
    for leg in legs:
        suffix, n, base, iters = leg[:4]
        d = os.path.join(work, suffix)
        os.makedirs(d, exist_ok=True)
        write_transient(os.path.join(d, f"{RESULT}.{suffix}"), n_zones=n,
                        base=base)
        if iters is not None:
            write_note(d, suffix, iters)
        if len(leg) > 4 and leg[4] is not None:
            write_convg(os.path.join(d, f"unicones.enorm.{suffix}"), leg[4])
    if live is not None:
        n, base = live
        write_transient(os.path.join(work, f"{RESULT}{live_tag}"), n_zones=n,
                        base=base)
        if live_rows is not None:
            write_convg(os.path.join(work, f"unicones.enorm{live_tag}"),
                        live_rows)
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

# A clean restart chain: each leg takes over exactly where the last stopped.
# 490/1990 are LAST ROWS, so the counts the solver printed are 500/2000/3000.
case = os.path.join(tmp, "case")
work = build_case(case, [("prev_001", 2, 0.0, 490, (10, 490)),
                         ("prev_002", 3, 100.0, 1990, (510, 1990))],
                  live=(3, 200.0), live_rows=(2010, 2990))
live_path = os.path.join(work, f"{RESULT}.gui")
found = list_result_legs(live_path)
check(len(found) == 3 and list(found.labels) == ["prev_001", "prev_002", LATEST],
      f"1. every leg of the solve is found — the two archives and the live one — "
      f"oldest solution first ({list(found.labels)})")
check([leg.kind for leg in found.legs] == [ARCHIVE, ARCHIVE, LATEST]
      and [leg.span.end for leg in found.legs] == [500, 2000, 3000],
      f"1. each leg reports the count the SOLVER PRINTED, not the last row it "
      f"wrote: a history ending at 490 with one row every 10 means 500. #30/#31 "
      f"showed the raw row and called the correction a fabrication; #43 reverses "
      f"that ({[leg.span.end for leg in found.legs]})")
check([leg.span.start for leg in found.legs] == [0, 500, 2000],
      f"1. ...and where it took OVER, from its own history's first row — which is "
      f"what turns 'how far did it get' into a range that can be intersected, and "
      f"0 for the leg that cold-started ({[leg.span.start for leg in found.legs]})")
check([leg.span.recorded for leg in found.legs] == [True, True, False],
      f"1. ...saying which figures were RECORDED in a RUN.txt and which were "
      f"recomputed, since a reader is entitled to know how much to trust one "
      f"({[leg.span.recorded for leg in found.legs]})")
check(found.warnings == (),
      f"1. a clean chain says nothing — consecutive legs MEET at a boundary "
      f"iteration and a half-open span gives it to the earlier leg alone, so an "
      f"ordinary restart is not reported as an overlap ({found.warnings})")
check(found.index_of(live_path) == 2 and found.index_of("/nope") == -1,
      "1. the caller can ask which leg it opened without re-deriving the match")

# Order is by ITERATION, not by name: prev_002 re-ran 1000-1900 after prev_001
# had already reached 2000 (#31 makes that a click), so it got LESS far.
rerun = os.path.join(tmp, "rerun")
rework = build_case(rerun, [("prev_001", 2, 0.0, 1990, (1010, 1990)),
                            ("prev_002", 3, 100.0, 1890, (1010, 1890))],
                    live=(2, 200.0), live_rows=(2010, 2990))
r = list_result_legs(os.path.join(rework, f"{RESULT}.gui"))
check(list(r.labels) == ["prev_002", "prev_001", LATEST],
      f"1. the legs are ordered by ITERATION COUNT, so a leg re-run from an "
      f"earlier point plays where it belongs in the solve rather than where its "
      f"directory name falls ({list(r.labels)})")
check(any("prev_002" in w and "prev_001" in w and "same part" in w
          and "1001-1900" in w for w in r.warnings),
      f"1. ...and the overlap is a MEASUREMENT, naming both legs AND the "
      f"iterations that repeat: two spans that intersect really did cover one "
      f"stretch twice, where 'ran later, got no further' was a heuristic that "
      f"could not say which part ({r.warnings})")
# The case non-monotonicity got wrong: a later leg over an EARLIER, disjoint
# range. prev_002 re-ran 0-900 from scratch, which repeats nothing prev_001 did.
disj = os.path.join(tmp, "disjoint")
dwork = build_case(disj, [("prev_001", 2, 0.0, 1990, (1010, 1990)),
                          ("prev_002", 2, 100.0, 890, (10, 890))], live=None)
d = list_result_legs(os.path.join(dwork, "prev_001", f"{RESULT}.prev_001"))
check(not any("same part" in w for w in d.warnings),
      f"1. ...and a leg that ran LATER over an earlier, DISJOINT range is not "
      f"reported: 'ran later but got no further' called that an overlap, which "
      f"is exactly the false positive interval intersection removes ({d.warnings})")

# INJECTION — stop iteration_span reading any convergence history, i.e. put
# back #32's "the note IS the record". Done on the RE-RUN case, whose legs BOTH
# carry a RUN.txt: their ends still come from those notes, so what is lost is
# the START, and with it the overlap. Injected on a note-LESS leg this proves
# only the easy half (a count appearing at all); this direction proves the rule
# that is cheapest to delete unnoticed — that the file is read even when a note
# has already answered "how far".
_real_rows = case_run_note._iteration_rows
case_run_note._iteration_rows = lambda _p: ((), 0)
try:
    blind = list_result_legs(os.path.join(rework, f"{RESULT}.gui"))
finally:
    case_run_note._iteration_rows = _real_rows
blind_arch = [leg for leg in blind.legs if leg.kind == ARCHIVE]
check(any("same part" in w for w in r.warnings)
      and not any("same part" in w for w in blind.warnings)
      and all(leg.span.known and not leg.span.measurable
              for leg in blind_arch),
      f"1. INJECTED: with the convergence history unreadable the two legs keep "
      f"the ends their notes record ({[leg.span.end for leg in blind_arch]}) and "
      f"lose their STARTS, so the re-run above goes silent — `start` is read "
      f"from the file even for a noted archive, or the best-documented legs are "
      f"the only ones nothing can intersect ({blind.warnings})")

# Lineage is the direct evidence of a re-run and needs no counts at all: two
# legs whose notes record the same start really did cover the same stretch.
# `bare_link_for_archived_dump` links an archived dump into work/ under its
# ARCHIVED name, so `binDumpZ.dat.prev_001` in a note names one leg exactly.
lin = os.path.join(tmp, "lineage")
lwk = build_case(lin, [("prev_001", 2, 0.0, None),
                       ("prev_002", 2, 100.0, None)], live=None)
write_note(os.path.join(lwk, "prev_001"), "prev_001", -1,
           resumed="binDumpZ.dat.prev_000")
write_note(os.path.join(lwk, "prev_002"), "prev_002", -1,
           resumed="binDumpZ.dat.prev_000")
li = list_result_legs(os.path.join(lwk, "prev_001", f"{RESULT}.prev_001"))
check(any("prev_002" in w and "prev_001" in w and "both resumed from" in w
          for w in li.warnings),
      f"1. two legs that RESUMED FROM THE SAME DUMP are reported as covering "
      f"one stretch even though neither records an iteration count — lineage is "
      f"direct evidence where non-monotonicity needs two numbers ({li.warnings})")

# ...but a blank start is not a shared start: "we have no record" must not be
# matched against another "we have no record" and reported as a re-run.
quiet = os.path.join(tmp, "quiet")
qwk = build_case(quiet, [("prev_001", 2, 0.0, 500),
                         ("prev_002", 2, 100.0, 900)], live=None)
qi = list_result_legs(os.path.join(qwk, "prev_001", f"{RESULT}.prev_001"))
check(not any("both resumed from" in w for w in qi.warnings),
      f"1. ...and two legs whose notes record NO start are not reported as "
      f"sharing one ({qi.warnings})")

# THE case #43 is about, and the layout of this repo's own results/solver/case:
# two archives predating RUN.txt, each holding a perfectly readable convergence
# history. #32 read the note ONLY, so both played with no count at all.
old = os.path.join(tmp, "preNote")
owork = build_case(old, [("prev_001", 2, 0.0, None, (10, 990)),
                         ("prev_002", 2, 100.0, None, (10, 990))],
                   live=(2, 200.0), live_rows=(1010, 1990))
pn = list_result_legs(os.path.join(owork, f"{RESULT}.gui"))
check([leg.span.end for leg in pn.legs] == [1000, 1000, 2000]
      and not any(leg.span.recorded for leg in pn.legs),
      f"1. an archive written before RUN.txt existed reports a REAL count, "
      f"recomputed from the convergence history inside it — the live leg two "
      f"functions away always did exactly this, with this reader, so refusing it "
      f"to the archives made them second-class for no reason their own folder "
      f"supports ({[leg.span.end for leg in pn.legs]})")
check(any("prev_002" in w and "prev_001" in w and "1-1000" in w
          for w in pn.warnings),
      f"1. ...and that makes a real overlap VISIBLE that was silent: both legs "
      f"ran 0-1000, so a stretch of the animation repeats and the user is told "
      f"which stretch ({pn.warnings})")

# INJECTION — the other half of the same rule, where the COUNT is what is at
# stake rather than the start. Same mutation, a case with no notes at all.
case_run_note._iteration_rows = lambda _p: ((), 0)
try:
    blind_pre = list_result_legs(os.path.join(owork, f"{RESULT}.gui"))
finally:
    case_run_note._iteration_rows = _real_rows
check([leg.span.end for leg in blind_pre.legs] == [UNKNOWN] * 3
      and not any("1-1000" in w for w in blind_pre.warnings),
      f"1. INJECTED: with no history read, a case whose archives predate RUN.txt "
      f"loses every count and its overlap with them — which is precisely the "
      f"state #32 shipped and #43 measured on this repo's own "
      f"results/solver/case ({[leg.span.end for leg in blind_pre.legs]})")

# A leg that can be measured NEITHER way still has to be played somewhere.
legacy = os.path.join(tmp, "legacy")
lwork = build_case(legacy, [("prev_001", 2, 0.0, None),
                            ("prev_002", 2, 100.0, 1990, (510, 1990))],
                   live=(2, 200.0), live_rows=(2010, 2990))
lg = list_result_legs(os.path.join(lwork, f"{RESULT}.gui"))
check(list(lg.labels) == ["prev_001", "prev_002", LATEST]
      and not lg.legs[0].known,
      f"1. a leg with neither a record nor a history is played WHERE IT RAN, not "
      f"last: it is a real part of the solve and creation order is the fact that "
      f"is always there ({list(lg.labels)})")
check(any("prev_001" in w and RUN_NOTE in w and "convergence history" in w
          for w in lg.warnings),
      f"1. ...and that it was placed that way is said, naming BOTH sources that "
      f"failed rather than only the record ({lg.warnings})")

# The case that measures WHY: with nothing measurable anywhere, a "played last"
# rule sends the NEWEST leg to the front and runs the solve backwards.
allold = os.path.join(tmp, "allold")
awork = build_case(allold, [("prev_001", 1, 0.0, None),
                            ("prev_002", 1, 100.0, None)],
                   live=(1, 200.0), live_rows=(10, 1990))
ao = list_result_legs(os.path.join(awork, f"{RESULT}.gui"))
check(list(ao.labels) == ["prev_001", "prev_002", LATEST],
      f"1. ...and when only the LIVE leg can be measured, the solve still plays "
      f"oldest first instead of newest first ({list(ao.labels)})")

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
# write_note stamps run_tag .gui, so prev_001 belongs to the interactive run.
both = os.path.join(tmp, "both")
bwork = build_case(both, [("prev_001", 2, 0.0, 490, (10, 490))],
                   live=(2, 100.0), live_rows=(510, 990), live_tag=".gui")
write_transient(os.path.join(bwork, f"{RESULT}.cli"), n_zones=4, base=900.0)
b_gui = list_result_legs(os.path.join(bwork, f"{RESULT}.gui"))
b_cli = list_result_legs(os.path.join(bwork, f"{RESULT}.cli"))
check(os.path.basename(b_gui.legs[-1].path) == f"{RESULT}.gui"
      and os.path.basename(b_cli.legs[-1].path) == f"{RESULT}.cli",
      "1. a case run by both hosts holds two live outputs, and the one the user "
      "OPENED is the live leg — they are two solves, not two halves of one")
check(list(b_gui.labels) == ["prev_001", LATEST]
      and list(b_cli.labels) == [LATEST],
      f"1. ...and the ARCHIVES follow the same rule: opening the headless leg "
      f"plays only the headless run, where #32 spliced the interactive run's "
      f"archive into it. Note the direction — opening .gui passes with or "
      f"without the filter, so only this one is evidence "
      f"({list(b_cli.labels)} vs {list(b_gui.labels)})")
check(any("prev_001" in w and "gui" in w and "cli" in w for w in b_cli.warnings),
      f"1. ...and the excluded leg is NAMED, with both tags, so a leg missing "
      f"from the animation is never silent ({b_cli.warnings})")

# INJECTION — remove the filter and re-list BOTH directions. Only the headless
# one changes: opening .gui was always going to get the .gui archive, so a check
# built that way certifies a filter that is not there.
_real_same_run = result_legs._same_run
result_legs._same_run = lambda legs, anchor: (legs, [])
try:
    nf_cli = list_result_legs(os.path.join(bwork, f"{RESULT}.cli"))
    nf_gui = list_result_legs(os.path.join(bwork, f"{RESULT}.gui"))
finally:
    result_legs._same_run = _real_same_run
check(list(nf_cli.labels) == ["prev_001", LATEST]
      and list(nf_gui.labels) == list(b_gui.labels),
      f"1. INJECTED: without the filter the interactive run's archive is spliced "
      f"into the headless one's animation — two solves shown as one, and the "
      f"discontinuity between them reads as physics. The .gui direction is "
      f"UNCHANGED by the injection, which is why it is not the evidence "
      f"({list(nf_cli.labels)} vs {list(nf_gui.labels)})")
# An archived leg whose OWN name cannot carry a tag anchors on its note (#30's
# rename replaced the tag), and it must not drag work/'s newest file in with it.
b_arch = list_result_legs(
    os.path.join(bwork, "prev_001", f"{RESULT}.prev_001"))
check(list(b_arch.labels) == ["prev_001", LATEST]
      and os.path.basename(b_arch.legs[-1].path) == f"{RESULT}.gui",
      f"1. ...and opening an ARCHIVED leg anchors on its RUN.txt tag, which is "
      f"the only place the tag survives the rename — so the live leg it is "
      f"played with is its own run's, not whichever file in work/ is newest "
      f"({[os.path.basename(p) for p in b_arch.paths]})")

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
# The expected (file, zone) for every global frame, counted off the FILES rather
# than asked of the series: a reference parse that routes through `locate` agrees
# with a broken map by construction — measured, a map collapsing every frame onto
# zone 0 passed this check while failing eight others.
def zone_count(path):
    with open(path) as f:
        return sum(1 for ln in f if ln.lstrip().lower().startswith("zone"))


expected = [(fi, zi) for fi, p_ in enumerate(paths)
            for zi in range(zone_count(p_))]
check(len(expected) == s.n_frames and [s.locate(k) for k in range(s.n_frames)]
      == expected,
      f"2. the flat map is exactly the legs' zones in order, counted off the "
      f"files themselves ({len(expected)} vs {s.n_frames})")

same = True
for k, (fi, zi) in enumerate(expected):
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
# Nothing here may put up a modal. #32 asked one on every load and gave the
# entry point a flag to suppress it; #43 deleted both, so a confirm() reaching
# the canvas at all is now the failure — hence a fake that RECORDS rather than
# one that answers.
_asked = []
_real_confirm = utils_mod.confirm


def fake_confirm(*a, **k):
    _asked.append((a, k))
    return False


utils_mod.confirm = fake_confirm

v = ResultCanvasView()
v.load_result_path(live_path)
check(_asked == [],
      f"3. opening a leg of a restarted solve asks NOTHING — the common case "
      f"costs no clicks, and an unattended run takes the same path an "
      f"interactive one does, so a CI screenshot shows what the user sees "
      f"({_asked})")
check(v._series is not None and v._series.n_files == 3
      and v._frame_count() == 8,
      f"3. ...and it plays the whole solve by default: 8 frames over 3 legs "
      f"({v._frame_count()})")
check(v._frame == 7,
      f"3. ...opening on the LAST frame of the leg that was opened — here the "
      f"live one, which is also the most-converged solution ({v._frame})")
# isHidden(), not isVisible(): under the offscreen platform a child of a
# top-level that was never shown reports isVisible() False either way.
check(not v.one_leg_cb.isHidden() and not v.one_leg_cb.isChecked(),
      f"3. ...with 'This leg only' offered and unticked: the escape is a control "
      f"the user can see and reverse, not a question they must answer before the "
      f"picture appears ({v.one_leg_cb.isHidden()}, {v.one_leg_cb.isChecked()})")
tip = v.frame_label.toolTip()
check("prev_001" in tip and "500" in tip and "3000" in tip
      and tip == v.zone_combo.toolTip(),
      f"3. ...and each leg's count is where the leg is NAMED — the frame "
      f"read-out and the frame selector — rather than in a log line to scroll "
      f"back to ({tip!r})")
check(v.zone_combo.count() == 8
      and v.zone_combo.itemText(0).startswith("prev_001")
      and v.zone_combo.currentIndex() == 7,
      f"3. the zone selector lists every frame of the series and names the leg, "
      f"so the selector and the read-out say the same thing "
      f"({v.zone_combo.itemText(0)!r})")
check(v.frame_label.text() == "latest · Frame 3 / 3 (8 / 8)",
      f"3. the frame read-out names the leg AND says where that is in the whole "
      f"series — every transport button moves through the series, so the "
      f"read-out has to describe the same thing ({v.frame_label.text()!r})")

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

# The per-variable seeded range is COMPUTED over every leg, not over the frame
# that happened to be on screen when Auto was unticked. Standing on frame 0 —
# whose own band is 1..2 — the seed must still be the series' 1..204, or one
# leg's numbers colour the whole solve and the Min/Max boxes describe a range
# that is not on screen (#24's symptom, one level up).
v.show_frame(0)
v.reset_clim_store()          # the manual range above was this variable's
frame_band = (float(v._result.get_cell_field("p").min()),
              float(v._result.get_cell_field("p").max()))
v.set_clim_auto(False)
v.render()
seeded = v.manual_clim("p")
check(seeded == (1.0, 204.0) and frame_band == (1.0, 2.0),
      f"3. unticking Auto over a restarted solve seeds from the WHOLE SERIES, "
      f"not from the frame on screen (whose own band is {frame_band}) — one "
      f"leg's numbers would saturate every other leg ({seeded})")
v.show_frame(7)
check(v.manual_clim("p") == seeded,
      f"3. ...and it is remembered, so a leg boundary cannot re-seed (and so "
      f"drift) it ({v.manual_clim('p')})")
solo_v = ResultCanvasView()
solo_v.load_result_path(paths[2])
solo_v.one_leg_cb.setChecked(True)
solo_v.select_variable("p")
solo_v.show_frame(0)
solo_v.set_clim_auto(False)
solo_v.render()
# A scan that FAILS must not be recorded as the answer, or one transient read
# error pins the variable to a single frame's numbers for the rest of the session.
fv = ResultCanvasView()
fv.load_result_path(live_path)
fv.select_variable("u")
_real_gr = ResultSeries.global_range


def _boom(self, var, progress=None):
    raise OSError("simulated transient read failure")


ResultSeries.global_range = _boom
try:
    fv.set_clim_auto(False)
    fv.render()
finally:
    ResultSeries.global_range = _real_gr
after_fail = fv.manual_clim("u")
fv.set_clim_auto(True)
fv.set_clim_auto(False)
fv.render()
check("u" in fv._series_seeded and fv.manual_clim("u") != after_fail,
      f"3. a FAILED whole-series scan is NOT remembered, so the next untick "
      f"retries and the real range still takes effect — the alternative pins a "
      f"variable to one frame's numbers for the session on a transient read "
      f"error ({after_fail} -> {fv.manual_clim('u')})")

# A range the user TYPED is never scanned away. #24's manual-over-lock-over-auto
# precedence is explicitly out of scope for #43, and "already scanned" does not
# imply it: the first version of seed_range_from_series guarded on the scan set
# alone, so typing numbers for a variable that had never been scanned and then
# toggling Auto off and on replaced them with the series band (found in review,
# measured -999..999 -> 1.0..134.33).
tv = ResultCanvasView()
tv.load_result_path(live_path)
tv.select_variable("u")
tv.set_clim_auto(False)          # scans 'u'
tv.render()
tv.select_variable("p")
tv.render()
tv.set_clim(-999.0, 999.0)
tv.set_clim_auto(True)
tv.set_clim_auto(False)
tv.render()
check(tv.manual_clim("p") == (-999.0, 999.0),
      f"3. a range the user TYPED survives unticking Auto again — the "
      f"whole-series scan is a fix for auto-scaling, never an override of an "
      f"explicit choice, and it must not reach a variable that was never "
      f"scanned merely because it was never scanned ({tv.manual_clim('p')})")
tv.select_variable("v" if "v" in tv._series.variables else "u")
tv.render()
check(tv.manual_clim("u") == (11.0, 214.0),
      f"3. ...while a variable nobody typed still gets the whole-series band, so "
      f"the guard is not simply 'never scan once anything is remembered' "
      f"({tv.manual_clim('u')})")

check(solo_v.manual_clim("p") == (201.0, 202.0),
      f"3. ...while a SINGLE file still seeds from the frame on screen, so #24's "
      f"'nothing jumps when you untick' is untouched where it was decided "
      f"({solo_v.manual_clim('p')})")
v.set_clim_auto(True)

# "This leg only" restricts the series to exactly the file that was opened.
_asked.clear()
v2 = ResultCanvasView()
v2.load_result_path(live_path)
v2.one_leg_cb.setChecked(True)
check(v2._series.n_files == 1 and v2._series.paths == [live_path]
      and v2._frame_count() == 3,
      f"3. 'This leg only' plays ONLY the file that was opened — inspecting one "
      f"leg stays a normal thing to do ({v2._series.paths})")
check(v2.frame_label.text() == "Frame 3 / 3",
      f"3. ...and that one file is labelled the way it always was, with no leg "
      f"name and no series position to distinguish it from "
      f"({v2.frame_label.text()!r})")
check(not v2.one_leg_cb.isHidden(),
      "3. ...and the box stays visible while it is ticked, or there would be no "
      "way back: it follows how many legs the SOLVE has, not how many are loaded")
v2.one_leg_cb.setChecked(False)
check(v2._series.n_files == 3 and v2._frame_count() == 8 and v2._frame == 7,
      f"3. ...unticking rebuilds the whole series and lands on the same leg's "
      f"last frame, so the control moves the animation around the picture "
      f"rather than moving the picture ({v2._series.n_files}, {v2._frame})")

# The box is view state for the result in front of you, never a preference.
v2.one_leg_cb.setChecked(True)
v2.load_result_path(live_path)
check(not v2.one_leg_cb.isChecked() and v2._series.n_files == 3,
      f"3. ...and a fresh load unticks it: it is an escape the user asks for on "
      f"one result, not a preference the view carries to the next one "
      f"({v2.one_leg_cb.isChecked()}, {v2._series.n_files})")

# Opening an ARCHIVED leg lands on THAT leg's last frame, not the solve's.
v3 = ResultCanvasView()
v3.load_result_path(paths[0])
check(v3._series.n_files == 3 and v3._frame == 1
      and v3._series.path_of(v3._frame) == paths[0],
      f"3. opening an archived leg plays the whole solve but LANDS on that "
      f"leg's last frame — the file the user named is the one they should be "
      f"looking at ({v3._frame})")
v3.one_leg_cb.setChecked(True)
check(v3._series.n_files == 1 and v3._frame == 1,
      f"3. ...and toggling 'This leg only' keeps them on it ({v3._frame})")

# One zone per leg is an ordinary restarted solve, and ticking the box then
# leaves a SINGLE-frame series — which hides the transport row. The box must not
# go with it, or the escape closes behind the user (found in review of #43;
# measured 3 legs x 1 zone: tick -> frames=1, the box hidden).
one_zone = os.path.join(tmp, "onezone")
ozwork = build_case(one_zone, [("prev_001", 1, 0.0, 490, (10, 490)),
                               ("prev_002", 1, 100.0, 1990, (510, 1990))],
                    live=(1, 200.0), live_rows=(2010, 2990))
vz = ResultCanvasView()
vz.load_result_path(os.path.join(ozwork, f"{RESULT}.gui"))
check(vz._frame_count() == 3 and not vz.one_leg_cb.isHidden(),
      f"3. a solve of three one-zone legs is three frames, and the box is offered "
      f"({vz._frame_count()}, hidden={vz.one_leg_cb.isHidden()})")
vz.one_leg_cb.setChecked(True)
check(vz._frame_count() == 1 and not vz.one_leg_cb.isHidden(),
      f"3. ...and ticking it leaves ONE frame without hiding the box: its "
      f"visibility is a fact about how many LEGS the solve has, never about how "
      f"many frames are loaded, or the escape closes behind the user "
      f"({vz._frame_count()}, hidden={vz.one_leg_cb.isHidden()})")
vz.one_leg_cb.setChecked(False)
check(vz._series.n_files == 3,
      f"3. ...so there is a way back ({vz._series.n_files})")

# A single-leg case is not a restarted solve: nothing is offered.
_asked.clear()
solo_case = os.path.join(tmp, "solo")
swork = build_case(solo_case, [], live=(3, 0.0), live_rows=(10, 100))
v4 = ResultCanvasView()
v4.load_result_path(os.path.join(swork, f"{RESULT}.gui"))
check(v4._frame_count() == 3 and v4.frame_label.text() == "Frame 3 / 3"
      and v4.one_leg_cb.isHidden(),
      f"3. a case that was never restarted has one leg, so there is nothing to "
      f"rename and no 'This leg only' to offer ({v4.frame_label.text()!r}, "
      f"{v4.one_leg_cb.isHidden()})")

# The variable list is the intersection, and the subtraction is logged.
_asked.clear()
vcase = os.path.join(tmp, "vcase")
vwork = build_case(vcase, [("prev_001", 2, 0.0, 490, (10, 490))],
                   live=(2, 100.0), live_rows=(510, 990))
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

utils_mod.confirm = _real_confirm
shutil.rmtree(tmp, ignore_errors=True)

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
