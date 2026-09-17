#!/usr/bin/env python3
"""The multi-block CELL SHAPE figures, through the real binary on ALL FIVE shipped
cases, with every figure PINNED (issue #129, then #140; parent #128).

The arithmetic is pinned next door in ``tests/cpp/test_cell_shape.cpp`` (a square
is 1.0, a degenerate cell does not divide by zero, how p95 is ranked) and which
cells feed it in ``tests/cpp/test_mb_quality.cpp`` check 9. What can only be
checked out here is the half that IS the ticket: that THREE SURFACES agree about
one mesh — the banner a user reads, the machine-readable line a script greps, and
the ``.provenance.json`` sidecar every later reader consumes — and that the figure
does not move when ``MB_SPLIT_QUADS`` does.

Run on the SHIPPED configs, read from disk through the one retargeter, because
the demo in the ticket is ``./run.sh -conf config/multiblock_ogrid.dat`` and a
composed equivalent would leave an edit to that file invisible from here.

#140 CHANGED THIS FILE'S SUBJECT, and the change is worth stating rather than
inferring from the table below. #129 shipped it against TWO of the five shipped
multi-block configs — the O-grid and the H-grid — and asserted STRUCTURAL bars
only (ordering, agreement, independence), keeping its measured figures as a dated
record explicitly "not a threshold in disguise". A per-story audit of #128 then
found what that cost: the token ``quad_midline_ratio`` appeared in no other
surface gate, so the case with by far the worst figures — the shipped C-grid, at
median 4.832, p95 148.006, max 3147.958, two orders past the O-grid's 32.8 that
motivated #128 — was measured by the batch's own instrument and looked at by
nobody. All five run here now, and the record became a PIN.

A PIN IS NOT A THRESHOLD, and #128's refusal of one still stands. A threshold says
a number is BAD; a pin says it MOVED. Check 11 has no opinion about 3147.958 — it
fails when today's run disagrees with the day it was measured, and its fix is
either "re-measure and update the pin" or "this is the regression the pin was for".
That is the same instrument ``tools/scripts/golden_mesh.py`` is for the meshes
themselves, and it is what gives the ticket that splits this report by wall band a
baseline to be visible against.

What this pins down:

  1. The banner gains a ``Cell shape`` row carrying median, p95 and max, and says
     over how many STRUCTURED quads — a different count from the ``Inverted
     cells`` row's, which counts what was exported.
  2. One row PER BLOCK under it, named with the id the topology document gave the
     block, the way each wall gets a row under the wall headline. The H-grid is
     what makes that worth having: its four blocks report four different medians,
     and the C-grid's wake blocks report a median 2.7x its own airfoil blocks'.
  3. The machine-readable line carries the four figures as ``key=value`` in the
     existing shape, so an acceptance check stays a grep. It is read with the ONE
     parser the quality gate owns, which floats every token — so a string-valued
     token on that line would fail here rather than silently breaking five gates.
  4. The METRIC'S NAME IS IN THE KEY (``quad_midline_ratio_*``). The hybrid path's
     figure is a different quantity under a different name, and a grep must not be
     able to confuse them.
  5. The sidecar's ``mesh.quality`` object holds the same numbers, under a
     ``metric`` that names the quantity. Parsed as JSON out of a file a real run
     produced, never asserted against a writer.
  6. THE SAME NUMBERS, to the digit, in all three places. This is what "one owner"
     means operationally.
  7. INDEPENDENT OF ``MB_SPLIT_QUADS``: the same shipped case at 0 exports half as
     many cells and reports the four figures BITWISE unchanged. On all five now,
     which is acceptance criterion 4 of #140 for the C-grid specifically.
  8. Every figure is at or above 1.0 and ordered median <= p95 <= max, on all five
     cases. 1.0 is the metric's floor, so this is what stops an absent measurement
     reaching a user as a number.
  9. NO THRESHOLD AND NO FAILURE: the shipped O-grid's max is ~32.8 and the
     C-grid's ~3148, and both runs exit 0 with nothing on those rows coloured or
     graded. Both numbers are what the user asked for (see 13), and a tool that
     coloured them red would be training them to ignore colour.
 10. Shape is not inversion: the deliberately folded dart exits 9 with inverted
     cells AND still reports shape figures, so neither figure is the other wearing
     a different name.
 11. EVERY SHIPPED CASE'S THREE FIGURES ARE PINNED, in ``PINS`` below, and a wrong
     figure reddens a check whose label names the case. The band is DERIVED from
     the pin rather than declared per case: a case pinned at the metric's floor
     (all three exactly 1.0) is held to exact equality, since a band below 1.0 is
     unreachable and one above it would be slack for nothing; every other case is
     held to ``PIN_TOL`` relative. The toleranced cases carry their own NEGATIVE
     CONTROL — the same case at ``MB_SMOOTH_ITERS 0`` must miss the pin by more
     than ``PIN_TOL`` — so the band is measured to be narrower than a real change
     to the mesh rather than assumed to be.
 12. AN INDEPENDENT RECOMPUTATION AGREES. Every exported quad's opposite-edge
     midline ratio is recomputed here, in Python, off the file on disk, and
     reduced by the two rules ``reduceCellShapes`` states (median = middle or mean
     of two middles; p95 = nearest rank, ``ceil(0.95n)`` from 1). All four figures
     must match the binary's. Three surfaces agreeing proves one owner; a fourth
     implementation agreeing is what makes the owner's answer right.
 13. WHAT THE C-GRID'S 3147.958 IS, measured rather than asserted — #140's whole
     question. The worst cell is LOCATED (it touches the outlet plane and lies on
     the wake cut) and its two midlines are named: the wake cut's last streamwise
     interval over the first radial height off the cut. See the entry below.

WHY THE C-GRID'S MAX IS ARITHMETIC AND NOT A DEFECT, which is #140's acceptance
criterion 3 in the form a gate can hold. Measured 2026-09-17 on the shipped case:

    worst cell  corners (16.8564, ~0) (16.8564, -0.000999)
                        (20.0000, -0.000999) (20.0000, ~0)
    long midline   3.143570   the LAST of the wake cut's 24 intervals: `wake`
                              declares `count` 25 and `ds_start` 0.005 over a
                              19-chord span (trailing edge x = 1 to outlet x = 20),
                              so the stretching law ends at 3.14
    short midline  0.000999   the first radial interval off the cut, which
                              `e_out_up`/`e_out_lo` declare as a wall end and the
                              run's `BL_INITIAL_THICKNESS 0.001` sizes
    ratio          3147.96    = 3.143570 / 0.000998606

That is the O-grid's 32.77 = 0.0327 / 0.001 in the same shape, two orders larger
because the wake is 19 chords long where the O-grid's ring is 2*pi*0.5 around. BOTH
numbers are the quotient of two spacings the DOCUMENT declares, so neither is a
defect in the radial law: a C-grid whose wake reached the outlet in 24 intervals
without stretching would need the wake cut's own `count`, not a different law. What
a fix would change is therefore the topology, not the mesher — and #128's decision
that these figures carry no threshold is what keeps that a user's choice.

THE ARITHMETIC HAS ITS OWN NEGATIVE CONTROL, and it is injection D below: giving the
shipped wake cut a 26th node — one more interval over the same 19 chords, nothing
else touched — moves the max to 3003.344 and moves NO other case. A number that
tracks the wake's own count that way is the quotient claimed above; a defect in the
radial law would not have cared.

INJECTIONS, run by hand 2026-09-17 against this file and the shipped topology, each
restored by CONTENT from a copy taken first (#131's lesson: a `git checkout` on a
mixed tree is not a restore). All four bit:

  A  the C-grid's pinned `max` moved 0.01%           -> 1 check: `cgrid: 11. the
     (3147.957636 -> 3148.272432)                       pinned max`, and nothing
                                                        else in the file
  B  `reduce_ratios` interpolates p95 instead of     -> 2 checks: `hgrid: 12` and
     taking the nearest rank                            `cgrid: 12`. NOT the
                                                        O-grid's: its four blocks
                                                        are congruent, so the two
                                                        ranks either side of p95
                                                        hold the same value and an
                                                        interpolation between them
                                                        is the same number. An
                                                        injection that bites on two
                                                        of three is recorded with
                                                        the reason the third is
                                                        immune rather than rounded
                                                        up to "it bit"
  C  check 13 takes the LEAST-stretched cell         -> 5 checks, all of 13: the
     instead of the worst                               ratio, both locators and
                                                        both midline sentences
  D  the shipped topology's wake cut declares        -> 4 checks, all `cgrid: 11`
     `count` 26 instead of 25                           (the cell count and all
                                                        three figures), and no
                                                        other case moved

MEASURED 2026-09-17, at the shipped defaults (``MB_SMOOTH_ITERS`` 20). These are
the values ``PINS`` carries, and they are a PIN rather than a record now:

    shipped square   400 structured quads,  800 exported triangles
                     median 1.000000, p95 1.000000, max 1.000000
    shipped cavity   256 structured quads,  512 exported triangles
                     median 1.000000, p95 1.000000, max 1.000000
    shipped H-grid    80 structured quads,  160 exported triangles
                     median 1.164421, p95 1.391410, max 1.504321
                     per block: bl 1.156, br 1.249, tl 1.080, tr 1.389 (medians)
    shipped O-grid  4608 structured quads, 9216 exported triangles
                     median 1.845977, p95 23.662285, max 32.767868
    shipped C-grid  5760 structured quads, 11520 exported triangles
                     median 4.832007, p95 148.005672, max 3147.957636
                     per block: b_wake_up 10.107, b_upper 3.692,
                                b_lower 3.692, b_wake_lo 10.107 (medians)

The O-grid's spread is #128's own headline number and its arithmetic is there:
0.0327 azimuthal spacing / 0.001 requested first-cell height = 32.7. The C-grid's
is the entry above. ``test_multiblock_quality_gate.py`` owns the numeric QUALITY
bars for this path and deliberately gains none here: #128 rules out a pass/fail
threshold on the shape figures, and a pin is not one.

CHECK 6 IS KNOWN TO BITE, by accident and on the day it was written: its first
draft read the FIRST ``Cell shape`` row out of the output, which on a smoothed run
(the shipped default since #85) is the report for the mesh BEFORE the sweeps — a
mesh that was never exported. It compared that against the after-smoothing machine
line and went red on both cases, naming the disagreement. The fix is in
``last_report`` and is the same trailing-space rule ``qlines`` carries for its own
prefix.

BLIND SPOTS, named rather than papered over:

  * ``not measured`` IS NOT REACHED HERE, and not for want of trying: every
    declaration this path ACCEPTS produces at least one structured quad — an edge
    with ``count`` 1 is refused by name ("an edge needs at least 2 nodes"), so
    there is no valid document that fills no measurable cell. The row-level and
    headline-level halves of that rule are therefore pinned where a mesh can be
    built by hand, in ``tests/cpp/test_mb_quality.cpp`` checks 8 and 9d; what is
    NOT covered anywhere is the banner STRING for that state, in ``src/cli.cpp``.
  * A PIN IS NOT A BAR, and the cost #129 named is only half paid. A regression
    that made every mesh twice as stretched now reddens check 11 on every case
    that moved — but it reddens it as "this moved", and an author who re-measures
    the pin without reading the number has banked the regression. Nothing here
    says 3147.958 is worse than 32.768, because #128 declined to create that
    gate; what #140 bought is that the movement cannot happen in SILENCE.
  * THE TWO CASES AT THE METRIC'S FLOOR HAVE NO NEGATIVE CONTROL, by construction
    rather than by omission. The square and the cavity are uniform rectangles, so
    the smoother moves nothing on them and their pin's band has no width to
    demonstrate — check 11 holds them to exact equality instead, and says so. What
    is NOT demonstrated there is that a real change to those two cases would be
    caught; the exactness is the argument, and it is an argument rather than a
    measurement.
  * The sidecar is parsed for the ``mesh.quality`` object only. Whether every
    other key in it is still right is ``test_provenance_sidecar``'s subject, not
    this file's.
  * The per-block rows are checked for presence, naming, count and ordering — not
    against the per-block cells, which no machine-readable line carries, and NOT
    pinned. A row that reported the WRONG block's figures would pass here;
    ``tests/cpp/test_mb_quality.cpp`` check 9d is where a row is tied to its block.
  * Check 13 locates the C-grid's worst cell and names its two midlines; it does
    NOT re-derive the wake cut's stretching law, so "3.1436 is the last of 24
    intervals from ds_start 0.005 over 19 chords" is read off the topology by a
    human and stated above rather than computed here.

Run:  python3 tools/PreProcessor/tests/test_multiblock_shape_surface.py
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import json
import math
import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
sys.path.insert(0, _HERE)
# The ONE shipped-config retargeter (#126), called directly for all five cases.
# `test_shipped_config_seam.py` derives the set of retargeters from the tree and
# fails on a second, so this file defines none — and it calls the seam rather than
# the O-grid's and the C-grid's `base_config` wrappers, which exist to carry a
# per-gate ARGUMENT (a mutated topology, a wall thickness, a BC fallback) and this
# gate passes none: `base_config()` with no arguments is `shipped_config(<name>)`.
# #129 imported the O-grid's wrapper for its one case; five cases in one table is
# what makes calling the seam directly the simpler of the two.
from mb_shipped_config import shipped_config  # noqa: E402
# The ONE parser for the quality line, imported from the gate that owns it rather
# than written again here — `.claude/rules/mesher-smoothing.md` forbids the fourth
# near-copy in as many words. It floats EVERY token, which is check 3's point.
from test_multiblock_quality_surface import qlines  # noqa: E402
from test_multiblock_quality_surface import DART  # noqa: E402
from test_multiblock_surface import run as run_conf, write_config, write_topology  # noqa: E402
# The legacy-VTK quad reader, and the ONE spelling of "no smoothing" (#85, #126).
# `quad_corners` is the smoothing gate's, imported for the same reason `qlines` is:
# a second reader for the same file format is the copy this repo keeps paying for.
from test_multiblock_smooth_surface import quad_corners  # noqa: E402
from mesher_bin import NO_SMOOTH, mesher_env as _mesher_env  # noqa: E402

# The four keys the figure travels under on the machine-readable line. Spelled
# once: every check below builds its token names from these, so a rename shows up
# as one edit here rather than as a gate that quietly stopped looking.
METRIC = "quad_midline_ratio"
FIELDS = ("cells", "median", "p95", "max")
FIGURES = ("median", "p95", "max")

# The banner's headline row and its per-block rows.
_HEAD = re.compile(
    r"^  - Cell shape\s+: median ([\d.]+), p95 ([\d.]+), max ([\d.]+) "
    r"\(quad midline ratio over (\d+) structured quads")
_ROW = re.compile(r"^      block '([^']+)'\s+: (.+)$")
_ROWNUM = re.compile(r"^median ([\d.]+), p95 ([\d.]+), max ([\d.]+)$")

# THE PIN'S BAND, and why it is this wide. The machine line prints six decimals,
# so on the C-grid's max the print resolution alone is 3e-10 relative; the six runs
# this pin was measured over reproduced every figure to the last printed digit on
# one machine, and CI builds with a different compiler and libm, where a tanh a
# few ulp away is expected and a changed mesh is not. 1e-6 relative is wider than
# the first and, as check 11's own negative control MEASURES rather than assumes,
# narrower than the second — but the MARGIN is thinner than the obvious example
# suggests, so it is stated with the number that is thinnest. The nine movements
# that control measures between 0 and 20 smoothing sweeps run from 2.1e-2 (the
# H-grid's median) down to 7.60e-6: the O-GRID'S MAX, only 7.6x this band. The
# C-grid's max at 1.4e-3 is the comfortable one and is not the one to quote. A
# looser band would stop catching the O-grid's max at all.
PIN_TOL = 1e-6

# THE MACHINE LINE'S OWN RESOLUTION, which is what check 12 can compare against.
# Both the `HYBMESH_MB_QUALITY` line and the sidecar carry six DECIMALS, so a
# figure read back off either is the true value rounded to within half of the last
# one. Check 12's independent recomputation reads the SAME node coordinates the
# binary reduced, so the only difference it can legitimately show is that rounding
# plus double-precision noise around 1e-15 relative — which is why this is an
# ABSOLUTE bound and not a relative one, and why it is not PIN_TOL. The first draft
# compared at 1e-9 relative and went red on the three cases whose figures are not
# exactly 1.0, naming a disagreement that was the printf.
PRINT_EPS = 5e-7

# The five shipped multi-block configs: the name this gate prints, the shipped
# `config/<name>.dat` it drives, and the block ids the topology document gives.
# #129 ran the first two rows of this table; #140 added the other three, and the
# C-grid is the reason it exists — see the entry above.
CASES = (
    ("square", "multiblock_square", ("block0",)),
    ("cavity", "multiblock_cavity", ("cavity",)),
    ("hgrid", "multiblock_hgrid", ("bl", "br", "tl", "tr")),
    ("ogrid", "multiblock_ogrid", ("q0", "q1", "q2", "q3")),
    ("cgrid", "multiblock_cgrid",
     ("b_wake_up", "b_upper", "b_lower", "b_wake_lo")),
)

# WHAT EACH SHIPPED CASE MEASURES, measured 2026-09-17 at the shipped defaults and
# PINNED. `cells` is exact (a count cannot drift by a rounding); the three figures
# are held to `PIN_TOL`, or to exact equality where all three are the metric's
# floor — see check 11, which derives which rule applies from the pin itself.
PINS = {
    "square": {"cells": 400, "median": 1.0, "p95": 1.0, "max": 1.0},
    "cavity": {"cells": 256, "median": 1.0, "p95": 1.0, "max": 1.0},
    "hgrid": {"cells": 80, "median": 1.164421, "p95": 1.391410, "max": 1.504321},
    "ogrid": {"cells": 4608, "median": 1.845977, "p95": 23.662285,
              "max": 32.767868},
    "cgrid": {"cells": 5760, "median": 4.832007, "p95": 148.005672,
              "max": 3147.957636},
}

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(tmp, name, config_text):
    """Run one config, returning (exit code, output, output stem)."""
    stem = os.path.join(tmp, name)
    conf = os.path.join(tmp, name + ".dat")
    with open(conf, "w", encoding="utf-8") as f:
        f.write(config_text.replace("@STEM@", stem))
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=900)
    return p.returncode, (p.stdout or "") + (p.stderr or ""), stem


def last_report(out):
    """The LAST ``Cell shape`` block: ``(headline numbers or None, {block: text})``.

    ONE WALK, because both halves need the same answer to the same question — which
    of the report's two copies describes the mesh on disk — and two walks is two
    places for that answer to drift. THE LAST ONE, and the trailing-space rule
    ``qlines`` follows is why this has to be said: a smoothed run prints the whole
    quality block TWICE, and the first is the mesh BEFORE the sweeps, a mesh that
    was never exported. The first draft took the first match and compared the
    before-banner against the after-machine-line, which reddened check 6 on both
    cases — which is how this gate is known to bite.

    The headline is None when the row said ``not measured`` (or is absent); the rows
    are whatever text each block carried, parsed by the caller.
    """
    head, rows = None, {}
    seen = False
    for line in out.splitlines():
        if line.startswith("  - Cell shape"):
            m = _HEAD.match(line)
            head = ({"median": float(m.group(1)), "p95": float(m.group(2)),
                     "max": float(m.group(3)), "cells": float(m.group(4))}
                    if m else None)
            rows, seen = {}, True
            continue
        if not seen:
            continue
        m = _ROW.match(line)
        if m:
            rows[m.group(1)] = m.group(2).strip()
        elif line.strip() and not line.startswith("      "):
            seen = False
    return head, rows


def sidecar(stem):
    """The ``mesh.quality`` object beside a run's output, or None.

    Imported by ``test_hybrid_shape_surface.py``, which asks the same question of
    the other generation path's sidecar.
    """
    path = stem + ".provenance.json"
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("mesh", {}).get("quality")


def quality(out):
    got = qlines(out)
    return got[0] if got else None


def shape_of(q):
    """The four shape figures off a parsed machine line, or None if absent."""
    if q is None or any(METRIC + "_" + f not in q for f in FIELDS):
        return None
    return {f: q[METRIC + "_" + f] for f in FIELDS}


def midlines(pts, quad):
    """``(shorter, longer)`` distance between the midpoints of a quad's opposite
    edges — the metric ``cellShapeRatio`` takes the ratio of, written again on
    purpose.

    THIS IS A SECOND IMPLEMENTATION AND THAT IS THE POINT, which is the opposite of
    why ``qlines`` is imported rather than copied. A parser copied four times is
    four places one format change has to land; an independently written METRIC that
    agrees with the C++ everywhere is evidence the C++ computes what its header
    says. Check 12 is that agreement, over every exported quad of all five shipped
    cases.
    """
    p = [pts[i] for i in quad]

    def mid(a, b):
        return ((p[a][0] + p[b][0]) / 2.0, (p[a][1] + p[b][1]) / 2.0)

    def dist(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    d1 = dist(mid(0, 1), mid(2, 3))
    d2 = dist(mid(1, 2), mid(3, 0))
    return (min(d1, d2), max(d1, d2))


def reduce_ratios(ratios):
    """``reduceCellShapes``'s two rules, restated here so check 12 can apply them.

    Median is the middle value, or the MEAN of the two middle ones on an even
    count; p95 is NEAREST RANK, ``ceil(0.95n)`` counting from 1, no interpolation.
    Both over the ascending order. Stated in ``include/CellShape.hpp``, because a
    percentile with no stated rule is a number nobody can reproduce — and a check
    that could not reproduce it would be measuring its own guess.
    """
    v = sorted(ratios)
    n = len(v)
    med = v[n // 2] if n % 2 else 0.5 * (v[n // 2 - 1] + v[n // 2])
    return {"cells": float(n), "median": med,
            "p95": v[math.ceil(0.95 * n) - 1], "max": v[-1]}


def close(a, b, tol=PIN_TOL):
    """``a`` within ``tol`` RELATIVE of ``b``, with ``b`` never 0 here (1.0 floors
    the metric and a cell count is at least one)."""
    return abs(a - b) <= tol * abs(b)


def pin_check(name, got, pin):
    """Check 11 for one case, plus the rule that decides how wide its band is."""
    exact = all(pin[f] == 1.0 for f in FIGURES)
    check(f"{name}: 11. the pinned cell count is what ran ({got['cells']:.0f} "
          f"structured quads against the pinned {pin['cells']})",
          got["cells"] == float(pin["cells"]))
    for f in FIGURES:
        if exact:
            check(f"{name}: 11. the pinned {f} is EXACT, because this case sits at "
                  f"the metric's floor and a band below 1.0 is unreachable "
                  f"(got {got[f]!r}, pinned {pin[f]!r})", got[f] == pin[f])
        else:
            check(f"{name}: 11. the pinned {f} is held to {PIN_TOL:g} relative "
                  f"(got {got[f]:.6f}, pinned {pin[f]:.6f}, "
                  f"off by {abs(got[f] - pin[f]) / pin[f]:.2e}) — re-measure the "
                  f"pin only after reading WHY the number moved",
                  close(got[f], pin[f]))
    return exact


def one_case(tmp, name, config_name, blocks):
    """Checks 1-8 and 11-12 for one shipped case. Returns the default run's output
    and the stem of its ``MB_SPLIT_QUADS 0`` twin, or ``(None, None)``."""
    config_text = shipped_config(config_name)
    pin = PINS[name]
    rc, out, stem = run(tmp, name, config_text)
    check(f"{name}: the shipped case runs and exits 0 (got {rc})", rc == 0)

    # --- 1. the banner row ---------------------------------------------------
    head, rows = last_report(out)
    check(f"{name}: 1. the banner carries a Cell shape row with median, p95, max "
          f"and the count of structured quads", head is not None)
    if head is None:
        return None, None
    line = quality(out)
    check(f"{name}: 1. ...and the machine line is present", line is not None)
    if line is None:
        return None, None
    check(f"{name}: 1. ...over FEWER cells than were exported ({head['cells']:.0f} "
          f"structured quads against {line['cells']:.0f} exported cells), because "
          f"the figure is measured on the cell the DOCUMENT declares",
          head["cells"] < line["cells"])

    # --- 2. one row per block ------------------------------------------------
    check(f"{name}: 2. one row per block, named by the document's own block ids "
          f"({sorted(rows)})", sorted(rows) == sorted(blocks))
    parsed = {b: _ROWNUM.match(t) for b, t in rows.items()}
    check(f"{name}: 2. ...each carrying its own three figures",
          all(m is not None for m in parsed.values()))

    # --- 3/4. the machine line -----------------------------------------------
    got = shape_of(line)
    check(f"{name}: 3. the machine line carries every {METRIC}_* field as a "
          f"key=value float", got is not None)
    if got is None:
        return None, None
    check(f"{name}: 4. ...and the metric's name is IN THE KEY, so a grep for the "
          f"hybrid path's tri_edge_ratio cannot match this line",
          not any(k.startswith("tri_edge_ratio") for k in line))

    # --- 5/6. the sidecar, and all three agreeing ----------------------------
    side = sidecar(stem)
    check(f"{name}: 5. the sidecar beside the mesh carries mesh.quality",
          side is not None)
    if side is not None:
        check(f"{name}: 5. ...naming the metric ({side.get('metric')!r})",
              side.get("metric") == METRIC)
        check(f"{name}: 6. ...with the SAME four numbers as the machine line",
              all(float(side.get(f, -99)) == got[f] for f in FIELDS))
    check(f"{name}: 6. ...and the banner prints those same numbers to the three "
          f"decimals it shows",
          all(abs(head[f] - got[f]) < 5e-4 for f in FIGURES)
          and head["cells"] == got["cells"])

    # --- 8. the figures are orderly, and above the metric's floor ------------
    check(f"{name}: 8. median <= p95 <= max "
          f"({got['median']:.3f} <= {got['p95']:.3f} <= {got['max']:.3f})",
          got["median"] <= got["p95"] <= got["max"])
    check(f"{name}: 8. ...and the median is at or above 1.0, the metric's floor, "
          f"so an absent measurement cannot reach a user as a number",
          got["median"] >= 1.0)
    for b, m in parsed.items():
        if m is None:
            continue
        lo, mid, hi = float(m.group(1)), float(m.group(2)), float(m.group(3))
        check(f"{name}: 8. ...and block {b!r}'s own row is ordered and above 1.0",
              1.0 <= lo <= mid <= hi)

    # --- 11. the figures are PINNED -----------------------------------------
    exact = pin_check(name, got, pin)

    # --- 7. independent of MB_SPLIT_QUADS ------------------------------------
    off = config_text.replace("MB_SPLIT_QUADS 1", "MB_SPLIT_QUADS 0")
    check(f"{name}: 7. the shipped config really declares MB_SPLIT_QUADS 1, so "
          f"turning it off is a change", off != config_text)
    rc2, out2, stem2 = run(tmp, name + "_quads", off)
    check(f"{name}: 7. ...and the run with quads exits 0 (got {rc2})", rc2 == 0)
    line2 = quality(out2)
    got2 = shape_of(line2)
    check(f"{name}: 7. ...reporting its figures too", got2 is not None)
    if got2 is None or line2 is None:
        return out, None
    # NEGATIVE CONTROL, computed rather than claimed: the split really did change
    # what was exported, so "unchanged" below is a measurement and not two runs of
    # the same thing.
    check(f"{name}: 7. ...off EXACTLY HALF the exported cells ({line2['cells']:.0f} "
          f"quads against {line['cells']:.0f} triangles), so the two runs really "
          f"did export different meshes", line["cells"] == 2 * line2["cells"])
    check(f"{name}: 7. ...and the four shape figures are BITWISE identical, so "
          f"turning the split off to diagnose a mesh does not change the number "
          f"being diagnosed", got == got2)

    # --- 12. an INDEPENDENT recomputation off the file on disk ---------------
    pts, quads = quad_corners(stem2 + ".vtk")
    pairs = [midlines(pts, q) for q in quads]
    check(f"{name}: 12. every exported quad is measurable (no collapsed midline), "
          f"so the recomputation below drops none of them",
          pairs and all(lo > 0.0 for lo, _ in pairs))
    if not pairs or not all(lo > 0.0 for lo, _ in pairs):
        return out, stem2
    mine = reduce_ratios([hi / lo for lo, hi in pairs])
    check(f"{name}: 12. ...and an INDEPENDENT midline measurement of all "
          f"{mine['cells']:.0f} of them, reduced by the two rules "
          f"reduceCellShapes states, reproduces the binary's four figures "
          f"(median {mine['median']:.6f}, p95 {mine['p95']:.6f}, "
          f"max {mine['max']:.6f})",
          mine["cells"] == got["cells"]
          and all(abs(mine[f] - got[f]) <= PRINT_EPS for f in FIGURES))

    # --- 11. THE PIN'S OWN NEGATIVE CONTROL ----------------------------------
    # The band has to be narrower than a real change to the mesh, and the cheapest
    # real change this path has is the smoother. A case pinned at the metric's
    # floor is a uniform rectangle the smoother does not move, so it gets exact
    # equality above and no control here — said out loud rather than skipped.
    if exact:
        check(f"{name}: 11. no negative control is offered, because this case is "
              f"pinned at the metric's floor by EXACT equality and its band has "
              f"no width to demonstrate", all(pin[f] == 1.0 for f in FIGURES))
        return out, stem2
    rc3, out3, _ = run(tmp, name + "_nosmooth", config_text + NO_SMOOTH)
    got3 = shape_of(quality(out3))
    check(f"{name}: 11. the same case at MB_SMOOTH_ITERS 0 runs (rc {rc3})",
          rc3 == 0 and got3 is not None)
    if got3 is None:
        return out, stem2
    moved = {f: abs(got3[f] - pin[f]) / pin[f] for f in FIGURES}
    check(f"{name}: 11. ...and MISSES the pin by more than {PIN_TOL:g} relative "
          "(" + ", ".join(f"{f} {moved[f]:.2e}" for f in FIGURES) + "), so the "
          "band is measured to be narrower than a real change to this mesh "
          "rather than assumed to be",
          all(m > PIN_TOL for m in moved.values()))
    return out, stem2


def cgrid_arithmetic(stem2, config_text, reported_max):
    """Check 13: WHAT the C-grid's max IS, located and named.

    #140's question in the form a gate can hold. The worst cell is found by the
    independent measurement check 12 already trusts, then LOCATED — it must touch
    the outlet plane (the mesh's own largest x) and lie on the wake cut (every
    corner within one first-cell height of it) — and its two midlines are compared
    against the one number the config declares, `BL_INITIAL_THICKNESS`.

    What this settles is the ticket's either/or: the figure is the quotient of two
    spacings the DOCUMENT asks for, not a defect in the radial law. What it does
    NOT do is re-derive the wake cut's stretching law; that arithmetic is in this
    file's header, read off the topology by a person.
    """
    pts, quads = quad_corners(stem2 + ".vtk")
    worst, lo, hi = None, 0.0, 0.0
    for q in quads:
        a, b = midlines(pts, q)
        if a > 0.0 and (worst is None or b / a > hi / lo):
            worst, lo, hi = q, a, b
    check("13. the C-grid's worst quad is found by the independent measurement, "
          f"and its ratio IS the reported max ({hi / lo:.6f} against "
          f"{reported_max:.6f})", worst is not None and close(hi / lo, reported_max, 1e-9))
    if worst is None:
        return
    corners = [pts[i] for i in worst]
    out_x = max(p[0] for p in pts)
    want = [float(ln.split()[1]) for ln in config_text.splitlines()
            if ln.split()[:1] == ["BL_INITIAL_THICKNESS"]]
    check("13. ...the shipped config declares BL_INITIAL_THICKNESS exactly once, "
          f"so there is one number to compare the cell against ({want})",
          len(want) == 1)
    if len(want) != 1:
        return
    check(f"13. ...and that cell TOUCHES THE OUTLET PLANE (x = {out_x:g}, the "
          f"mesh's own largest x), so it is the last cell on the wake",
          any(abs(p[0] - out_x) <= 1e-9 * out_x for p in corners))
    # THE BOUND IS THE DECLARED HEIGHT, not the cell's own short midline: the
    # corner ON the outlet sits at exactly the declared 0.001 while the one 3.14
    # upstream has been pulled to 0.000997 by the smoother, so the midline is the
    # MEAN of the two and is smaller than the larger corner. Measuring the corners
    # against the mean is what reddened this check in its first draft.
    check(f"13. ...and LIES ON THE WAKE CUT: every corner is within the declared "
          f"first-cell height of y = 0 (worst |y| = "
          f"{max(abs(p[1]) for p in corners):.9f} against {want[0]:g})",
          max(abs(p[1]) for p in corners) <= want[0] * 1.001)
    check(f"13. ...its SHORT midline is that requested first-cell height "
          f"({lo:.6f} against {want[0]:g}, {abs(lo - want[0]) / want[0]:.2%} off "
          f"it), so the denominator is what the user asked for",
          close(lo, want[0], 0.01))
    check(f"13. ...so the max is ARITHMETIC and not a defect: {hi:.6f}, the wake "
          f"cut's last streamwise interval at the outlet, over {lo:.6f}, the "
          f"requested wall spacing = {hi / lo:.3f}. The O-grid's 32.77 is the same "
          f"quotient (0.0327 / 0.001); this one is larger because the wake is 19 "
          f"chords long. A fix would change the TOPOLOGY's wake count, not the "
          f"mesher", hi > 1.0 and lo > 0.0 and close(hi / lo, reported_max, 1e-9))


def main() -> int:
    if not os.path.exists(_BIN):
        print("SKIP  build/HybMesh2D not built; nothing to measure.")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        # ALL FIVE shipped multi-block cases, each read from disk (#140). #129 ran
        # the O-grid and the H-grid; the case it did not run was the one with the
        # worst figures by two orders, which is the whole reason for the table.
        outs, stems = {}, {}
        for name, config_name, blocks in CASES:
            outs[name], stems[name] = one_case(tmp, name, config_name, blocks)

        # --- 9. a correct large number is not a failure ----------------------
        # Both extremes, off the runs already made rather than a third run of the
        # same case: #128's own headline 32.8 and the C-grid's 3148, which no line
        # of #128 mentions because its Further Notes never measured this case.
        for name, lo, hi in (("ogrid", 30.0, 35.0), ("cgrid", 3000.0, 3300.0)):
            got = shape_of(quality(outs[name] or ""))
            check(f"9. the shipped {name}'s max is in [{lo:g}, {hi:g}] — what the "
                  f"document asks for, not a defect — and the run still exits 0 "
                  f"(max {got['max'] if got else '?'})",
                  got is not None and lo < got["max"] < hi)
        # EVERY WORD IN THE MESSAGE IS IN THE TUPLE, and that is not pedantry: a
        # check whose prose is wider than its assert is inert in exactly the gap
        # between them, which is the shape #114 recorded. The first draft named
        # PASS in the sentence and left it out of the tuple.
        _GRADED = ("PASS", "WARN", "FAIL", "too ", "threshold", "exceeds")
        for name in outs:
            check(f"9. ...and nothing in {name}'s report colours or grades it: "
                  "none of " + ", ".join(repr(w) for w in _GRADED)
                  + " sits on the Cell shape rows",
                  not any(w in ln for ln in (outs[name] or "").splitlines()
                          if "Cell shape" in ln or _ROW.match(ln)
                          for w in _GRADED))

        # --- 13. what the C-grid's 3147.958 IS -------------------------------
        if stems["cgrid"]:
            cgrid_arithmetic(stems["cgrid"], shipped_config("multiblock_cgrid"),
                             shape_of(quality(outs["cgrid"]))["max"])

        # --- 10. shape is not inversion --------------------------------------
        # The deliberately folded dart the quality gate owns. It exits 9 with
        # inverted cells and IS still measured for shape, so neither figure is the
        # other wearing a different name.
        topo = write_topology(os.path.join(tmp, "dart.json"), ni=5, nj=5,
                              corners=DART)
        stem = os.path.join(tmp, "dartout")
        conf = write_config(os.path.join(tmp, "dart.dat"), topo, stem)
        rc, out = run_conf(tmp, conf)
        line = quality(out)
        got = shape_of(line)
        check(f"10. the folded dart still exits 9 with inverted cells (rc {rc})",
              rc == 9 and line is not None and line["inverted"] > 0)
        check("10. ...and its shape figures are reported anyway, so a mesh can be "
              "folded and ordinarily shaped at the same time and the report says "
              "both", got is not None and got["cells"] > 0)
        side = sidecar(stem)
        check("10. ...and the sidecar beside the EXPORTED folded mesh carries them "
              "too, so a mesh that failed is still described",
              side is not None and side.get("metric") == METRIC)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for f in failures:
            print("  - " + f)
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
