#!/usr/bin/env python3
"""The four-block NACA 0012 C-GRID, end to end through the real binary (#57).

The v1 target of the multi-block feature: the first mesh from this path that is a
CFD grid rather than a demonstration of one. The DECISIONS it rests on are pinned
next door in ``tests/cpp/test_multiblock.cpp`` -- welding by declared identity
(#53), curved projection and the tanh wall law (#55), the edge KIND as an enum --
and checks 37-39 there add the two this case is the first to need. What can only
be checked out here is the chain on the SHIPPED files: two geometries with their
sidecars, one topology document, one config, through the real exporters onto disk.

WHAT IS NEW IN THIS TOPOLOGY, and therefore what this file measures:

  * A CUT EDGE. ``wake`` is ONE declared edge and the WEST side of BOTH wake
    blocks. Two blocks sharing a line that is not a boundary of anything: it welds
    by node identity like an interface, and NO face of it reaches the ``.bnd``.
  * A FOUR-WAY CORNER. Corner ``te`` is one declaration, so one node, and FIVE
    edges end on it -- the wake cut, the two trailing-edge radials and the two
    airfoil surfaces. All four blocks meet there. This is the highest-risk single
    point in the grid and it needs no tolerance at all, because nothing is welded
    by proximity.
  * A C THAT IS OPEN AT THE OUTLET, whose two open ends are ordinary bound
    boundary edges, so the D-shaped far field is one closed polyline of six
    segments and every one of them is exactly one block side.

GATE 1 -- ZERO INVERTED CELLS -- is check 2 below, and it passed on the first run
of the shipped declaration. NO ESCALATION STEP WAS NEEDED: #57 agreed a ladder
(Laplacian smoothing of block interiors, then shipping the O-grid as the release
geometry, then pulling elliptic smoothing forward) for the case where transfinite
interpolation could not clear it, and none of the three was reached.

GATE 2 -- THE SOLVER RUNS -- is the dated acceptance run quoted below, and it is
the gate that actually bit. The first shipped declaration cleared gate 1 with room
to spare and then drove the solver to NaN in 40 iterations. The fix was in the
DOCUMENT, not in the mesher: not one line of src/ or include/ changed for this
whole ticket, which is the strongest thing #57 has to say about #50-#55 -- a
C-grid was already expressible.

  WHAT WENT WRONG, and where #57's own prediction was wrong about it. The ticket
  expected transfinite interpolation to struggle "near the trailing edge". The
  blow-up was on the UPPER AND LOWER SURFACES from x = 0.01 to x = 0.28 -- just
  aft of the LEADING edge -- reached by dumping the solution at iteration 30 and
  reading off the cells with |rho| = inf. It is the same place the worst angle
  was: the far-field nose sides were left UNIFORM, so the outer point opposite a
  body point sat nowhere near that body point's normal, the first cell off the
  wall came out 59.5 degrees from orthogonal, and the mean over the whole mesh
  was 16.0 degrees.

  THE FIX IS ONE NUMBER, AND IT IS NOT A TUNED ONE. The two far-field nose sides
  now cluster at their trailing-edge end to 0.005 -- the airfoil edges' own
  ds_start. Over the chordwise surface the body's normals are nearly vertical and
  that boundary's top is horizontal, so the outer point belonging opposite a body
  point sits at very nearly the same x and the outer distribution has to track
  the body's own. The whole nose semicircle then belongs to the last few percent
  of the body, where the normals fan through 180 degrees. Measured: max
  non-orthogonality 59.52 -> 32.04 degrees, mean 16.0 -> 4.56, wall first cell
  3.46% -> 0.44%, and the solver runs to completion at the same CFL 0.6 the
  O-grid acceptance run used.

  WHAT WAS TRIED AND REJECTED, so the next reader does not re-run it. Lowering
  CFL to 0.3 or 0.1 also makes the ORIGINAL mesh run to exit 0 -- so a "the
  solver runs" line could have been written without improving the grid at all,
  which is why the run below quotes its CFL. And the wake's 3144:1 worst edge
  ratio, the obvious first suspect, is NOT the cause: cutting it to 211 (a
  coarser first cell on the two outlet radials, since the wake spreads) left the
  solver diverging at the same iteration.

THE BASELINE FOR THE ELLIPTIC-SMOOTHING INCREMENT, recorded and EXPLICITLY NOT A
PASS CONDITION (measured 2026-09-04 on the shipped files):

    cells                     11520 triangles (5760 structured quads)
    inverted                  0
    non-orthogonality         max 32.04 deg, mean 4.56 deg
    wall first cell           worst 0.44% off the declared 1e-3
    vertices / boundary faces 5920 / 320
    worst quad edge ratio     3144:1, in the far wake at (18.43, 0.0005)

  The worst angle is now at (0.017, +-0.022), still on the surface just aft of
  the leading edge and still the quantity elliptic smoothing moves. The wake's
  edge ratio is recorded because it is the largest number in the mesh and it was
  measured NOT to be what the solver minded; the next reader should not spend the
  afternoon on it that this one did.

THE NINE ORIGINAL CASES -- now seventeen -- REMAIN IDENTICAL, and the load-bearing
argument is structural rather than statistical: ``git diff --stat src/ include/``
against 02ed550 is EMPTY, so no code the mesher runs changed. The measurement
agrees: a baseline captured from this same tree before the work and compared after
gives 17/17 SAME at worst coordinate deviation 0.000e+00 (2026-09-04, 18/18 once
mb_cgrid was captured). "SAME" and not "bit-identical" is the claim that survives
repetition -- ``golden_mesh.py``'s own docstring records that ``wedge_45`` returns
a coordinate differing by ~1.2e-13 in roughly 1 run in 12, which is why the
comparator has a 1e-10 tolerance at all.

THE ACCEPTANCE RUN, dated and quoted rather than replaced by a shape check. CI has
no solver binary, so it is recorded here in the convention this repo adopted after
a change shipped broken behind 85 green tests that pinned strings and never
executed the solver.

Measured 2026-09-04 on ``examples/topology/cgrid_naca0012.json`` +
``config/multiblock_cgrid.dat`` (four blocks, 41 nodes radially; 25 along the
wake and 49 along each airfoil surface; a 1-chord NACA 0012 in a D of radius 10
with its outlet at x = 20; BL_INITIAL_THICKNESS 1e-3):

    ./run.sh -conf config/multiblock_cgrid.dat
        -> EXIT 0
           5920 vertices, 11520 triangles, 320 boundary edges
           HYBMESH_MB_QUALITY cells=11520 inverted=0
               nonortho_max_deg=32.044106 nonortho_mean_deg=4.561874
               wall_first_cell_worst_rel=0.004368

    solver/preprocess/getPGrid/work/getPGrid < para.in        # the grid converter
        -> EXIT 0
           "Read in 5920 vertices coordinates"
           "Read in 11520 elements"
           "number of boundary elements = 320"
           "Read in 320 boundary condition flags"
           It warns 288 times that it does not know the name 'farfield' and
           defaults those patches to a no-slip wall. That is getPGrid's own token
           list, not this path's -- it DOES know 'outlet' -- and the four
           far-field patches were given flag 1 (non-reflect far field) in
           cgrid.bc.def for the run below, which is exactly what the GUI's solver
           Boundary Conditions table writes. The GUI maps the name
           (services/bnd_io._NAME_TO_FLAG), so a GUI-driven run never sees it.

    solver/execute/unicones.eqn6.mac -t cgrid input.in        # the solver
        -> EXIT 0, at cfl 0.6 (the O-grid acceptance run's own value)
           last printed "Global Iteration count 90", at print_convg_per_niter 10
           with num_half_iter 100 -- i.e. 100 iterations, by the 90 + 10
           arithmetic services/case_run_note.iteration_span uses.
           No NaN in the log. Wrote binDumpZcgrid.dat, xtecp_sol_allzcgrid.dat,
           uniconescgrid.enorm, tWall_valuescgrid.dat, vsurface_qtycgrid.dat.

#85's ACCEPTANCE RUN, ON A SMOOTHED MESH, measured 2026-09-07 in the SAME
convention and at the SAME operating point, because that is the only thing that
makes the two comparable. #85 asks for it because a smoothed mesh is a different
mesh and #57's gate 2 is the one that actually bit — better non-orthogonality
guarantees nothing about the solver surviving it.

FOUR RUNS, not one: the smoothed mesh is the claim, and the unsmoothed CONTROL was
re-run on the same day through the same hand-built chain so the record is a
comparison this file measured rather than a quotation against #57's. The O-grid was
run too, because #80's negative control ought not to break the solver either.

    the chain, per case (cwd shown, since both binaries read relative paths):

      ./run.sh -conf <case>.dat                                    # the mesher
      cd grid && getPGrid < para.in                                # the converter
      <edit <case>.bc.def: every NON-WALL segment to flag 1>       # see below
      cd work && unicones.eqn6.mac -t G input.in                   # the solver

    C-grid, MB_SMOOTH_ITERS 0 (the control, = #57's run)
        mesher    EXIT 0   32.044106 / 4.561874 / 0.4368%, inverted 0
        getPGrid  EXIT 0   5920 vertices, 11520 elements, 320 boundary elements,
                           320 boundary condition flags; 288 warnings that it does
                           not know the name 'farfield'
        unicones  EXIT 0   at cfl 0.6, last printed "Global Iteration count 90"
                           with print_convg_per_niter 10 and num_half_iter 100 —
                           i.e. 100 iterations. No NaN.

    C-grid, MB_SMOOTH_ITERS 20 (THE DEFAULT since #85 — the claim)
        mesher    EXIT 0   29.895095 / 3.821201 / 0.0968%, inverted 0
        getPGrid  EXIT 0   same four counts, same 288 warnings
        unicones  EXIT 0   at cfl 0.6, last printed "Global Iteration count 90",
                           100 iterations, no NaN. Wrote binDumpZ, xtecp_sol_allz,
                           unicones.enorm, tWall_values, vsurface_qty — the same
                           five files the control wrote. Residuals finite and
                           O(1e-4) at iteration 90.

    O-grid, MB_SMOOTH_ITERS 0 and 20
        both      EXIT 0 / 0 / 0, 100 iterations, no NaN, 192 'farfield' warnings.
        mesher    2.250000 / 1.875000 / 0.0812%  ->  2.276042 / 1.875000 / 0.0442%

        THOSE TWO MESHER ROWS ARE THE 80-FACET FAR FIELD's AND NO LONGER REPRODUCE
        (#95, 2026-09-08). The shipped circle is stored at 320 facets since then and
        the same two invocations read 2.024972 / 1.875000 / 0.0036% -> 2.024972 /
        1.875000 / 0.0371%, which meets every figure #80 asked of this case with the
        smoother's excess exactly zero. The record above is NOT edited — it is what
        ran on 2026-09-07 (#43's rule) — and the solver half of it is untouched by
        #95, which changed a geometry and no code. The live figures are gated in
        test_multiblock_quality_gate.py; the derivation is in
        docs/design_notes/mesher.md, "THE SHIPPED O-GRID's FAR FIELD IS 320 FACETS".

THE CFL IS STATED BECAUSE #57 MEASURED THAT IT MATTERS: lowering cfl to 0.3 makes
a BAD mesh run too, so a recorded run that does not say which one it used proves
less than it appears to. All four above are cfl 0.6, the value #55 used.

WHAT THIS RUN DOES **NOT** EXERCISE, so it is not read as more than it is:

  * It is ONE operating point — M 0.2, Re 200, zero incidence, 100 iterations,
    cfl 0.6, every non-wall patch flag 1. "The solver runs on the smoothed mesh"
    is the whole claim. It is not convergence, not accuracy, and no pressure
    distribution is compared with anything — not even between the smoothed run and
    its own control, which is the obvious next question and is not answered here.
  * THE `.bnd` NAME -> SOLVER FLAG MAPPING WAS NOT EXERCISED HERE, and it still
    is not — but it is no longer UNEXERCISED, which is a different sentence.
    CLOSED BY #91 (2026-09-08), stated here rather than deleted because the runs
    quoted above predate it. #85 had measured why the pipeline route did not
    close it: getPGrid writes the `<case>.bc.def` segment table itself, does not
    know 'farfield', and defaulted those four patches to a NO-SLIP WALL with
    nothing in the Python re-writing it — so driving the same case through
    `config/pipeline/multiblock_cgrid_demo.json` ran a body in a closed viscous
    box (exit 0, 100 iterations, no NaN, but NOT this operating point), and the
    flag-1 above was written into the `.bc.def` by hand, exactly as #55's and
    #57's runs were. #91 made the headless runner derive the table from the
    mesh's own patches, so a pipeline run now REPRODUCES this operating point;
    its own dated run and the token-by-token gate against getPGrid's `getBCType`
    live in `tools/PreProcessor/tests/test_pipeline_bc_from_mesh.py`. What the
    GUI does automatically is `services/bnd_io._NAME_TO_FLAG`; check 6 is where
    the names themselves are measured.
  * NO OUTPUT IS ON DISK, following #55 — no para.in, no bc.def, no solver output
    is committed, so these figures are a quotation and not a reproduction.
  * CI has no solver binary. This checkout does (`solver/execute/unicones.eqn6.mac`
    and `solver/preprocess/getPGrid/work/getPGrid`), which corrects a claim
    `test_multiblock_weld_surface.py` still carries in its own docstring — that
    "this checkout carries no solver tree". It does.

BLIND SPOTS, named rather than papered over:

  * Nothing here re-runs the solver. The figures above are a record of one dated
    run, not something this file measures.
  * The airfoil is stored as a POLYLINE, so "follows the airfoil" is measured
    against the polyline's own facets. Nothing on this path projects onto an
    analytic curve -- BL_USE_ANALYTIC_GEOM survives into this mode and is still
    not read.
  * Check 7 measures conformity on the EXPORTED files, so it cannot distinguish a
    cut that welded correctly from one that was welded correctly and then exported
    correctly. That is the same boundary test_multiblock_weld_surface.py works at.
  * The baseline numbers above are printed by this run but NOT asserted, on
    purpose. What is asserted is that all three were MEASURED -- the report's own
    "a negative means we did not measure" rule -- so a silent regression to "not
    measured" cannot be read as "it came out perfect".
  * The 0.005 on the two far-field nose sides is DERIVED from the airfoil edges'
    own ds_start, and nothing enforces the relation: they are two numbers in one
    document that happen to agree. Change one and the other has to follow by
    hand, and the only thing that would say so is the acceptance run.
  * Gate 2 is a run at ONE operating point (M 0.2, Re 200, zero incidence, 100
    iterations, cfl 0.6, all non-wall patches flag 1). "The solver runs" is what
    #57 asked for and all this claims; it is not a convergence or accuracy result,
    and nothing here compares a pressure distribution against anything.
  * NO OUTPUT FROM THE ACCEPTANCE RUN IS ON DISK -- no para.in, no cgrid.bc.def,
    no solver output is committed, following #55. So the figures above are a
    quotation and not a reproduction. Since #56 the case itself no longer has to
    be rebuilt by hand: `config/pipeline/multiblock_cgrid_demo.json` drives the
    same chain headless at the same operating point (M 0.2, Re 200, zero
    incidence, cfl 0.6, num_half_iter 100), and re-running it on 2026-09-04
    reproduced the record above -- exit 0, last printed "Global Iteration count
    90" at print_convg_per_niter 10, no NaN. What that script does NOT reproduce
    is the hand-built getPGrid/unicones invocation quoted above; it goes through
    the pipeline's own case preparation.
  * THE SOLVER RAN ON THE MESH, NOT ON THE MESH'S OWN DECLARED BC NAMES. getPGrid
    does not know 'farfield' and defaulted those 288 faces to a no-slip wall; the
    flag-1 they actually ran with was written into cgrid.bc.def BY HAND. That is
    what the GUI does automatically and what #55's run did too, but it means the
    .bnd -> solver name mapping is NOT part of what gate 2 exercises. Check 6 is
    where the names themselves are measured.

Run:  python3 tools/PreProcessor/tests/test_multiblock_cgrid_surface.py
      python3 tools/PreProcessor/tests/test_multiblock_cgrid_surface.py --write
          rewrites the two shipped geometries from the generators below.
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import json
import math
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_GEOM = os.path.join(_REPO, "examples", "geometries")
_TOPO = os.path.join(_REPO, "examples", "topology", "cgrid_naca0012.json")
_CONF = os.path.join(_REPO, "config", "multiblock_cgrid.dat")
sys.path.insert(0, _HERE)
from mesher_bin import NO_SMOOTH, mesher_env as _mesher_env

# #57's OWN RECORDED BASELINE for this case, declared ONCE and here rather than in
# the threshold gate, because the dependency has to run this way round: that gate
# already imports `base_config` from this file, so this file importing the numbers
# back would be a cycle. The gate that owns the CASE owns the case's recorded
# figures, and test_multiblock_quality_gate.py states every C-grid bar as one of
# them. Check 3 below re-derives them from a zero-sweep run, so a drift shows up
# here first.
CGRID_BASELINE = {
    "nonortho_max_deg": 32.044106,
    "nonortho_mean_deg": 4.561874,
    "wall_first_cell_worst_rel": 0.004368,
}          # noqa: E402
from test_multiblock_weld_surface import (                # noqa: E402
    bnd_faces, cel_cells, components, edge_use, vrt_nodes)

# The ONE parser for the machine-readable quality line, in the gate that owns
# that line. Imported rather than copied: this file and the O-grid's each held a
# byte-identical copy until #81, which had to fix the same character in both.
from test_multiblock_quality_surface import qlines as _qlines   # noqa: E402

# The D-shaped far field, in one place: the outlet plane at x = OUT_X, the nose
# semicircle of radius FAR_R about the leading edge, and the two block corners on
# it that sit level with the trailing edge at x = TE_X.
TE_X = 1.0
FAR_R = 10.0
OUT_X = 20.0
# Points per side of the airfoil. 96 puts the leading-edge joint on a point and
# leaves the polyline fine enough that its faceting is not what this case
# measures.
NACA_PER_SIDE = 96

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


# ── The ONE generator for each shipped geometry ────────────────────────────
# Committed files are CHECKED against these rather than trusted (check 1): a
# hand-edited `.dat` whose `.meta` still describes the old point set is a mesh
# with corners on the wrong segments and no error at all.

def closed_polyline_meta(segs, bcs):
    """``(dat_text, meta_text)`` for a CLOSED polyline in numbered segments.

    THE ONE writer of this convention in this repo -- #55's ``write_circle`` next
    door is one call to it, and that is deliberate: a second copy of a geometry
    generator is guaranteed divergence (CLAUDE.md says so about ``golden_mesh.py``
    for the same reason), and the thing that would diverge here is the two
    conventions below, whose failure mode is a mesh with corners on the wrong
    segments and no error at all.

    Two conventions of the real chain are reproduced exactly, because getting
    either wrong moves a corner by one sample and produces a slightly wrong mesh
    with no error:

      * the file carries the CLOSING DUPLICATE of its first point, which
        ``loadGeometry`` drops (and ``reconcileMeta`` drops the matching sidecar
        row), so the last segment's end is index 0 rather than one past the end;
      * a joint belongs to the LATER segment, so a segment's own rows stop one
        point short of where it ends and every joint is flagged a corner.

    ``segs`` is one list of points per segment, each INCLUDING both of its
    endpoints; consecutive segments therefore overlap by exactly one point.
    """
    pts, rows = [], []
    for s, seg in enumerate(segs):
        for j, p in enumerate(seg[:-1]):
            pts.append(p)
            rows.append((s, 1 if j == 0 else 0))
    pts.append(pts[0])
    rows.append((0, 1))
    dat = "".join("%.12f %.12f\n" % p for p in pts)
    meta = ["HYBMESH_META 2", "COUNT %d" % len(pts), "NPIECES 0",
            "NSEGMENTS %d" % len(segs)]
    meta += ["%d %s line" % (s, bcs[s]) for s in range(len(segs))]
    meta += ["POINTS %d" % len(pts)]
    meta += ["%d %d" % r for r in rows]
    return dat, "\n".join(meta) + "\n"


def naca0012_half_thickness(x):
    """The NACA 4-digit thickness law at t = 0.12, in the CLOSED-trailing-edge
    variant (-0.1036, not -0.1015), so y(1) is exactly 0 and the trailing edge is
    a single point. An open trailing edge would need a fifth block across it."""
    return 0.6 * (0.2969 * math.sqrt(max(x, 0.0)) - 0.1260 * x - 0.3516 * x * x
                  + 0.2843 * x ** 3 - 0.1036 * x ** 4)


def write_naca0012(per_side=NACA_PER_SIDE):
    """The C-grid's airfoil: TWO segments, upper then lower, split at the leading
    edge because that is where a block corner has to sit.

    A file of its OWN rather than a sidecar beside the shipped
    ``examples/geometries/naca0012.dat``: that one is the hybrid path's airfoil
    and has a golden baseline, and giving it a ``.meta`` would change what that
    path reads for a case this work is required to leave identical.

    Cosine spacing in x, so the stored polyline is dense where the surface turns.
    The bound edges distribute their own nodes by ARC LENGTH along it, so this
    distribution sets the faceting, not the mesh.
    """
    up = [(lambda x: (x, naca0012_half_thickness(x)))(
              0.5 * (1.0 + math.cos(math.pi * k / per_side)))
          for k in range(per_side + 1)]
    up[0] = (1.0, 0.0)          # the trailing edge, exactly
    up[-1] = (0.0, 0.0)         # the leading edge, exactly
    lo = [(x, -y) for x, y in reversed(up)]
    return closed_polyline_meta([up, lo], ["wall", "wall"])


def _line(p, q, n):
    return [(p[0] + (q[0] - p[0]) * k / n, p[1] + (q[1] - p[1]) * k / n)
            for k in range(n + 1)]


def _arc(r, a0, a1, n):
    return [(r * math.cos(a0 + (a1 - a0) * k / n),
             r * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]


def write_farfield():
    """The C-grid's D-shaped far field: SIX segments, one per outer block side.

    Walked counter-clockwise from the wake's own outlet point, so the two outlet
    halves are segments 0 and 5 and the D's own boundary is 1..4. The two
    conditions are declared here -- 'outlet' on the plane the wake leaves through,
    'farfield' on everything else -- and reach the ``.bnd`` off this sidecar.
    """
    wk, fu = (OUT_X, 0.0), (OUT_X, FAR_R)
    f1 = (TE_X, FAR_R)
    f3, fl = (TE_X, -FAR_R), (OUT_X, -FAR_R)
    # The sixth corner, `f2` dead ahead of the nose, is deliberately NOT written
    # as a literal: it is where the two nose arcs meet, and the arc generator
    # already produces it (to within sin(pi)'s own 1.2e-16). A literal would be a
    # second source of truth for one point, and the mesher resolves that corner
    # from the polyline anyway.
    top, bot = (0.0, FAR_R), (0.0, -FAR_R)
    segs = [_line(wk, fu, 20),
            _line(fu, f1, 40),
            _line(f1, top, 4)[:-1] + _arc(FAR_R, math.pi / 2, math.pi, 40),
            _arc(FAR_R, math.pi, 1.5 * math.pi, 40)[:-1] + _line(bot, f3, 4),
            _line(f3, fl, 40),
            _line(fl, wk, 20)]
    return closed_polyline_meta(segs, ["outlet", "farfield", "farfield",
                                   "farfield", "farfield", "outlet"])


SHIPPED = (("naca0012_cgrid", write_naca0012),
           ("cgrid_farfield", write_farfield))


def _write_shipped():
    for name, gen in SHIPPED:
        dat, meta = gen()
        with open(os.path.join(_GEOM, name + ".dat"), "w", encoding="utf-8") as f:
            f.write(dat)
        with open(os.path.join(_GEOM, name + ".dat.meta"), "w", encoding="utf-8") as f:
            f.write(meta)
        print("wrote " + name)


# ── Running the shipped case ───────────────────────────────────────────────

def run_case(tmp, name, conf_text):
    stem = os.path.join(tmp, name)
    conf = os.path.join(tmp, name + ".dat")
    with open(conf, "w", encoding="utf-8") as f:
        f.write(conf_text.replace("@STEM@", stem))
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=600)
    return p, stem


def quality(out):
    """The quality line for the mesh AS EXPORTED, or ``{}`` when there is none.

    Delegates to the ONE parser, in the gate that owns that line
    (``test_multiblock_quality_surface.qlines``). It was a byte-identical copy in
    this file and in the O-grid's until #81, which had to make the same
    one-character fix in both — the trailing space that keeps a smoothed run's
    ``HYBMESH_MB_QUALITY_BEFORE`` from being read as this one.
    """
    return _qlines(out)[0] if _qlines(out) else {}


def base_config(topo=_TOPO, bc_geom=None):
    """The shipped config, retargeted at a temp output stem.

    Read from disk rather than rebuilt: config/multiblock_cgrid.dat is
    documentation a user runs, and a test that composed an equivalent one would
    leave an edit to the shipped file invisible here.
    """
    with open(_CONF, encoding="utf-8") as f:
        text = f.read()
    # EVERY retarget must actually land, or the run writes into the repo's own
    # results/ and the caller, seeing a mesh, reports PASS.
    for needle, repl in (
            ("examples/topology/cgrid_naca0012.json", topo),
            ("examples/geometries/naca0012_cgrid.dat",
             os.path.join(_GEOM, "naca0012_cgrid.dat")),
            ("examples/geometries/cgrid_farfield.dat",
             os.path.join(_GEOM, "cgrid_farfield.dat")),
            ("results/meshes/multiblock_cgrid/mesh_multiblock_cgrid.vtk",
             "@STEM@.vtk")):
        if needle not in text:
            raise AssertionError(
                "%s no longer contains %r, so this test cannot retarget it away "
                "from the repo. Update base_config()." % (_CONF, needle))
        text = text.replace(needle, repl)
    if bc_geom is not None:
        text = "\n".join(("BC_GEOM " + bc_geom if line.startswith("BC_GEOM") else line)
                          for line in text.splitlines()) + "\n"
    return text


def topology(text=None):
    """The shipped topology document, PARSED.

    Its `//` line comments are the mesher's own extension to JSON (nlohmann parses
    them; `json` does not), so they are stripped here. The strip is line-oriented
    and would also cut a `//` inside a string value; nothing in this schema has
    one, and a `raise` beats a silent mis-parse if that ever changes.

    Parsed rather than string-counted, because check 5's claim is about the
    DOCUMENT: a reformat, or the word appearing in a comment, must not be able to
    change the answer.
    """
    if text is None:
        text = open(_TOPO, encoding="utf-8").read()
    lines = []
    for ln in text.splitlines():
        cut = ln.find("//")
        if cut >= 0:
            if ln.count('"', 0, cut) % 2:
                raise AssertionError(
                    "%s has a '//' inside a string; this comment stripper cannot "
                    "handle that. Parse it properly or move the value." % _TOPO)
            ln = ln[:cut]
        lines.append(ln)
    return json.loads("\n".join(lines))


def dist_to_polyline(p, poly):
    """Shortest distance from `p` to the polyline `poly` (a list of points)."""
    best = float("inf")
    px, py = p
    for k in range(len(poly) - 1):
        ax, ay = poly[k]
        bx, by = poly[k + 1]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0.0 else ((px - ax) * dx + (py - ay) * dy) / L2
        t = max(0.0, min(1.0, t))
        best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
    return best


def main() -> int:
    if "--write" in sys.argv:
        _write_shipped()
        return 0
    if not os.path.exists(_BIN):
        print("SKIP: build/HybMesh2D not found (run ./build.sh first)")
        return 0

    # ── 1. the shipped geometries ARE what the generators produce ───────────
    for name, gen in SHIPPED:
        dat, meta = gen()
        for ext, want in ((".dat", dat), (".dat.meta", meta)):
            path = os.path.join(_GEOM, name + ext)
            got = open(path, encoding="utf-8").read() if os.path.exists(path) else None
            check("1. %s%s is exactly what its generator produces" % (name, ext),
                  got == want)

    topo_text = open(_TOPO, encoding="utf-8").read()
    topology(topo_text)          # it parses, so check 9's edit below is on a
                                 # document and not on an unread blob

    with tempfile.TemporaryDirectory() as tmp:
        # ── 2. GATE 1: the shipped C-grid meshes with ZERO inverted cells ───
        p, stem = run_case(tmp, "cgrid", base_config())
        check("2. the shipped C-grid config exits 0 (rc=%d)" % p.returncode,
              p.returncode == 0)
        q = quality(p.stdout)
        check("2. it prints the machine-readable quality line", bool(q))
        check("2. GATE 1: ZERO inverted cells (got %s)" % q.get("inverted"),
              q.get("inverted") == 0.0)
        check("2. ...over a mesh that is actually there (%s cells)" % q.get("cells"),
              (q.get("cells") or 0) > 5000)

        nodes = vrt_nodes(stem)
        cells = cel_cells(stem)
        faces = bnd_faces(stem)
        use = edge_use(cells)

        # ── 3. #57's BASELINE is still reproducible, and the run above is not it ─
        #
        # WHAT #85 CHANGED HERE. The figures printed by the run above used to BE
        # #57's baseline, because the shipped default ran no sweeps; the default is
        # now 20, so that run is a SMOOTHED mesh and labelling it "BASELINE" would
        # have been a stale label on a live number — which it was, until it was read.
        # So the baseline is measured on its own explicit `MB_SMOOTH_ITERS 0` run
        # and ASSERTED against #57's recorded figures, because every threshold in
        # test_multiblock_quality_gate.py is stated relative to them: if this mesh
        # ever stops being 32.044 / 4.562 / 0.4368%, those bars are measuring
        # against something else and say so here first.
        #
        # #57's "a baseline and explicitly not pass conditions" is SUPERSEDED by
        # that gate. What stays asserted here is the report's own rule that a
        # negative means "not measured", so a regression to it cannot read as "it
        # came out perfect".
        pb, _ = run_case(tmp, "cgrid_base", base_config() + NO_SMOOTH)
        qb = quality(pb.stdout)
        print("    #57 BASELINE (MB_SMOOTH_ITERS 0)  cells=%s nonortho_max=%.3f deg "
              "nonortho_mean=%.3f deg wall_first_cell_worst=%.4f%%"
              % (qb.get("cells"), qb.get("nonortho_max_deg", -1.0),
                 qb.get("nonortho_mean_deg", -1.0),
                 100.0 * qb.get("wall_first_cell_worst_rel", -1.0)))
        print("    AT THE DEFAULT (20 sweeps)        cells=%s nonortho_max=%.3f deg "
              "nonortho_mean=%.3f deg wall_first_cell_worst=%.4f%%"
              % (q.get("cells"), q.get("nonortho_max_deg", -1.0),
                 q.get("nonortho_mean_deg", -1.0),
                 100.0 * q.get("wall_first_cell_worst_rel", -1.0)))
        check("3. all three figures were MEASURED at the default (a negative is "
              "the report's 'not measured', never a perfect score)",
              all((q.get(k, -1.0) or 0.0) >= 0.0 for k in
                  ("nonortho_max_deg", "nonortho_mean_deg",
                   "wall_first_cell_worst_rel")))
        check("3. ...and #57's own baseline still reproduces at zero sweeps, "
              "32.044 / 4.562 / 0.4368%% — the figures every threshold in "
              "test_multiblock_quality_gate.py is stated against "
              "(%.3f / %.3f / %.4f%%)"
              % (qb.get("nonortho_max_deg", -1.0), qb.get("nonortho_mean_deg", -1.0),
                 100.0 * qb.get("wall_first_cell_worst_rel", -1.0)),
              all(abs(qb.get(k, -1.0) - v) < (1e-6 if k.endswith("_rel") else 1e-3)
                  for k, v in CGRID_BASELINE.items()))
        check("3. ...and the default really did move it, so this gate's own main "
              "run is the smoothed mesh a user gets",
              q.get("nonortho_max_deg", 0.0) < qb.get("nonortho_max_deg", 0.0))

        # ── 4. the WAKE CUT: shared, welded, and NOT a boundary ─────────────
        wake_nodes = [i for i, (x, y) in enumerate(nodes)
                      if abs(y) < 1e-12 and TE_X - 1e-12 <= x <= OUT_X + 1e-12]
        check("4. the wake cut carries exactly its declared 25 nodes, not 50 "
              "(got %d) — one declared edge, allocated once" % len(wake_nodes),
              len(wake_nodes) == 25)
        on_cut = [k for k, name in faces
                  if all(abs(nodes[i - 1][1]) < 1e-12
                         and nodes[i - 1][0] > TE_X + 1e-9 for i in k)]
        check("4. NO face of the cut reaches the .bnd (%d) — that is the whole "
              "difference between a cut and a wall" % len(on_cut),
              not on_cut)
        # Every edge along the cut is used by two cells, one from each block.
        # Ordered by X, never by node id: the .vrt numbering is an allocation
        # order, and two nodes adjacent on the cut need not be adjacent in it.
        cut_ids = [i + 1 for i in
                   sorted(wake_nodes, key=lambda k: nodes[k][0])]
        cut_edges = [frozenset((a, b)) for a, b in zip(cut_ids, cut_ids[1:])
                     if frozenset((a, b)) in use]
        check("4. ...and every one of its 24 segments is shared by exactly two "
              "cells (%d found)" % len(cut_edges),
              len(cut_edges) == 24 and all(use[e] == 2 for e in cut_edges))

        # ── 5. the FOUR-WAY corner at the trailing edge ─────────────────────
        te_ids = [i + 1 for i, (x, y) in enumerate(nodes)
                  if abs(x - TE_X) < 1e-12 and abs(y) < 1e-12]
        check("5. exactly ONE node sits at the trailing edge (%d) — four blocks, "
              "one declared corner, no tolerance" % len(te_ids),
              len(te_ids) == 1)
        if len(te_ids) == 1:
            touching = [c for c in cells if te_ids[0] in c]
            check("5. ...and 8 cells touch it (%d): four blocks x the two "
                  "triangles its corner quad splits into" % len(touching),
                  len(touching) == 8)
            quad = set()
            for c in touching:
                cx = sum(nodes[i - 1][0] for i in c) / len(c)
                cy = sum(nodes[i - 1][1] for i in c) / len(c)
                quad.add((cx > TE_X, cy > 0.0))
            check("5. ...spread over all FOUR quadrants around it (%d) — the two "
                  "wake blocks downstream, the two airfoil blocks upstream"
                  % len(quad),
                  len(quad) == 4)
        on_te = [e["id"] for e in topology()["edges"] if "te" in e["corners"]]
        check("5. the declaration puts FIVE edges on corner 'te' — the cut, two "
              "radials and two surfaces (%r)" % on_te,
              len(on_te) == 5)

        # ── 6. both geometries' own conditions reach the .bnd ───────────────
        counts = {}
        for _key, name in faces:
            counts[name] = counts.get(name, 0) + 1
        check("6. the .bnd carries all THREE conditions, from the two geometries "
              "(%r)" % counts,
              set(counts) == {"wall", "outlet", "farfield"})
        check("6. the airfoil's 96 wall faces are its two 48-face surfaces (%s)"
              % counts.get("wall"),
              counts.get("wall") == 96)
        check("6. the outlet is the two halves the wake cut splits it into (%s)"
              % counts.get("outlet"),
              counts.get("outlet") == 80)
        # THE NEGATIVE CONTROL, and it is needed: the airfoil's condition is
        # 'wall', which is ALSO what the shipped config's BC_GEOM fallback says,
        # so the patch counts above cannot on their own tell a sidecar read from a
        # fallback. Re-run with a fallback nothing should reach. Every patch must
        # come out unchanged — which is also the shipped config's own claim ("every
        # edge here binds, so nothing should reach it") measured rather than
        # asserted.
        p6, stem6 = run_case(tmp, "fallback", base_config(bc_geom="inlet"))
        check("6. a run with BC_GEOM 'inlet' exits 0 (rc=%d)" % p6.returncode,
              p6.returncode == 0)
        check("6. ...and produces the SAME .bnd, patch names and all — so every "
              "condition came off a sidecar and NOTHING reached the fallback",
              p6.returncode == 0 and set(bnd_faces(stem6)) == set(faces))

        # ── 7. the whole grid is CONFORMAL across cut and four-way corner ───
        boundary = {k for k, n in use.items() if n == 1}
        check("7. every interior edge belongs to exactly two cells",
              all(n in (1, 2) for n in use.values()))
        check("7. the boundary edge set is exactly the .bnd (%d vs %d)"
              % (len(boundary), len(faces)),
              boundary == {k for k, _ in faces})
        check("7. the whole C-grid is ONE connected component by node identity",
              components(cells, len(nodes)) == 1)

        # ── 8. the wall FOLLOWS the airfoil, and the chord is the control ───
        airfoil = [tuple(map(float, ln.split())) for ln in
                   open(os.path.join(_GEOM, "naca0012_cgrid.dat"),
                        encoding="utf-8") if ln.strip()]
        by_patch = {}
        for key, name in faces:
            by_patch.setdefault(name, set()).update(key)
        wall_ids = sorted(by_patch.get("wall", set()))
        worst = max(dist_to_polyline(nodes[i - 1], airfoil) for i in wall_ids)
        # The CHORD the two surface edges would cut without their bindings runs
        # straight from the trailing edge to the leading edge, i.e. along y = 0,
        # so it sits up to the airfoil's own half-thickness (6.0e-02) off the
        # body. The measured figure must be orders below that, not merely below.
        # The floor is the FILE, not the mesh: Mesh.cpp writes .vrt coordinates
        # to 8 decimals, so half an ULP of that file is 5e-09 and nothing read
        # back out of it can measure closer.
        check("8. every wall node is ON the airfoil (worst deviation %.3e — the "
              ".vrt's own 8-decimal quantum — against the 6.0e-02 a chord would "
              "give)" % worst,
              worst < 1.0e-8)
        check("8. ...over all 96 distinct wall nodes, not a lucky few (%d)"
              % len(wall_ids),
              len(wall_ids) == 96)

        # ── 9. the KIND is load bearing: the cut declared 'wall' is REFUSED ──
        # The negative control for check 4. A 'wall' is the outside of the mesh
        # and has exactly one block; this line has two, so the refusal is about
        # the DECLARATION and fires before a node exists.
        bad = os.path.join(tmp, "wake_as_wall.json")
        with open(bad, "w", encoding="utf-8") as f:
            f.write(topo_text.replace(
                '"corners": ["te", "wk"], "kind": "cut"',
                '"corners": ["te", "wk"], "kind": "wall"'))
        p9, stem9 = run_case(tmp, "bad", base_config(topo=bad))
        check("9. declaring the wake a 'wall' is REFUSED with the topology exit "
              "code (rc=%d)" % p9.returncode,
              p9.returncode == 8)
        check("9. ...naming both blocks that share it",
              "b_wake_up" in (p9.stdout + p9.stderr)
              and "b_wake_lo" in (p9.stdout + p9.stderr))
        check("9. ...and exporting NOTHING — an invalid declaration is not a "
              "mesh to look at",
              not os.path.exists(stem9 + ".vtk"))


        # ── 10. THE SAMPLE-RATE WARNING IS SILENT HERE, AND THAT IS MEASURED ──
        #
        # #94, and this case is the reason that warning is keyed on a COST rather
        # than on a ratio. Six of this topology's eight bound edges have a
        # facets-per-interval ratio that does not divide — the two outlet halves at
        # 0.5, the two upper/lower far-field sides at 1.667, the two nose sides at
        # 0.917 — and every one of them lies on a STRAIGHT segment of
        # `cgrid_farfield.dat`, where every facet is collinear and where between
        # two vertices a node lands cannot matter. The remaining two are the airfoil
        # surfaces, 96 facets under 48 intervals, which divide exactly.
        #
        # So a ratio-keyed warning would fire six times on a case it has nothing to
        # say about, and this check is what would catch that: the O-grid gate's
        # group 9 proves the warning APPEARS where it costs something, and this one
        # proves it stays quiet where it does not. Neither half is worth much alone.
        said = [ln for ln in (p.stdout + p.stderr).splitlines()
                if "sample a bound stretch" in ln]
        check("10. the shipped C-grid says NOTHING about its sample rates, though "
              "six of its eight bound edges do not divide — they are straight, so "
              "the cost is nil (%d warnings)" % len(said),
              not said)

    print()
    if failures:
        print("%d check(s) failed:" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("PASS test_multiblock_cgrid_surface")
    return 0


if __name__ == "__main__":
    sys.exit(main())
