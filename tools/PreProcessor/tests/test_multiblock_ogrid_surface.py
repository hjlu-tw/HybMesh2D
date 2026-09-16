#!/usr/bin/env python3
"""The circular O-GRID, end to end through the real binary (issue #55).

The DECISIONS are pinned next door in ``tests/cpp/test_multiblock.cpp`` checks
30-35, which link the pure layer alone and assert on blocks, node positions, wall
specs and refusals as data. What can only be checked out here is the chain on the
SHIPPED files: two circle geometries with their sidecars, one topology document,
one config, through the real exporters onto disk.

What this pins down:

  1. The two shipped circle geometries are exactly what ``write_circle`` below
     produces. There is ONE generator, and the committed files are checked
     against it rather than trusted -- a hand-edited ``.dat`` whose ``.meta``
     still describes the old point set is a mesh with corners on the wrong
     segments and no error at all.
  2. The shipped O-grid meshes: exit 0, zero inverted cells, and the machine
     readable ``HYBMESH_MB_QUALITY`` line the acceptance gate greps.
  3. Every wall node sits ON the circle. The negative control is the CHORD the
     same edge would cut without its binding, which on a quarter circle is 0.293 r
     off the body at its midpoint -- three orders larger than what is measured, so
     this check cannot pass by the two being close.
  4. The two geometries' own conditions reach the ``.bnd``: the body as ``wall``
     and the far field as ``farfield``, four patches each.
  5. The wall first-cell height TRACKS ``BL_INITIAL_THICKNESS``. Three values two
     orders apart, each reproduced to 0.04%. That residue was the polyline
     FACETING of the stored circles until #95 resolved the far field; the
     UNSMOOTHED mesh now reproduces the asked-for height to 0.0036%, so what is
     left at the default is the SMOOTHER's own contribution rather than the
     geometry's. Both are far under #55's recorded 0.0812%.
  6. A per-edge ``ds_start`` beats the global, measured on the same document with
     one key added.
  7. Changing the ring's ONE seeded count does not move the wall spacing. This is
     the property the tanh default exists to protect: the count is decided for
     three of the four radials by propagation, so the law has to absorb a count it
     did not choose.
  8. The ring is CONFORMAL where it closes: every interior edge belongs to exactly
     two cells, the boundary edge set is exactly the ``.bnd``, and the whole mesh
     is ONE connected component by node identity. A last block that failed to weld
     back to the first would leave two components and a doubled seam.

THE ACCEPTANCE RUN, dated and quoted rather than replaced by a shape check. CI has
no solver binary, so this is recorded here in the convention this repo adopted
after a change shipped broken behind 85 green tests that pinned strings and never
executed the solver.

Measured 2026-09-04 on ``examples/topology/ogrid_circle.json`` +
``config/multiblock_ogrid.dat`` (four blocks, 49 x 25 nodes each, r = 0.5 body in
an r = 10 far field, BL_INITIAL_THICKNESS 0.001):

    ./run.sh -conf config/multiblock_ogrid.dat        # see the note below: this
                                                     # command no longer produces
                                                     # these figures
        -> EXIT 0
           4704 vertices, 9216 triangles, 192 boundary edges
           HYBMESH_MB_QUALITY cells=9216 inverted=0
               nonortho_max_deg=2.250000 nonortho_mean_deg=1.875000
               wall_first_cell_worst_rel=0.000812

    THE COMMAND ABOVE IS #55's AND IS NOW SHORT ONE LINE. Since #85 the shipped
    default is `MB_SMOOTH_ITERS 20`, so that invocation produces the SMOOTHED mesh
    (2.276042 / 1.875000 / 0.000442) and reproducing the record above needs
    `MB_SMOOTH_ITERS 0` appended. The figures are not restated here: a dated
    quotation is a record of what ran on the day and is not edited afterwards
    (#43's rule), so what is added is the missing line rather than new numbers.
    #85's own runs on this case, at both 0 and 20 sweeps, are in
    test_multiblock_cgrid_surface.py's docstring with the rest of that gate-2 set.

    AND SINCE #95 IT IS SHORT A GEOMETRY AS WELL AS A LINE. The far field above is
    the 80-facet circle; the shipped one is 320 facets, so no invocation of the
    command reproduces the record — the numbers moved because the GEOMETRY did.
    What the shipped case measures today is 2.024972 / 1.875000 / 0.000036
    unsmoothed and 2.024972 / 1.875000 / 0.000371 at the default cap of 20, which
    meets every figure #80 asked of this case. Those are gated in
    test_multiblock_quality_gate.py rather than restated as a run here: this block
    is a record of what ran on 2026-09-04 and is annotated rather than edited
    (#43's rule).

    solver/preprocess/getPGrid/work/getPGrid < para.in        # the grid converter
        -> EXIT 0
           "Read in 4704 vertices coordinates"
           "Read in 9216 elements"
           "number of boundary elements = 192"
           "Read in 192 boundary condition flags"
           It warns 8 times that it does not know the name 'farfield' and
           defaults those patches to a no-slip wall. That is getPGrid's own
           token list, not this path's: the four far-field patches were given
           flag 1 (non-reflect far field) in ``ogrid.bc.def`` for the run below,
           which is exactly what the GUI's solver Boundary Conditions table
           writes. The GUI maps the name (services/bnd_io._NAME_TO_FLAG), so a
           GUI-driven run never sees the warning.

    solver/execute/unicones.eqn6.mac -t ogrid input.in        # the solver
        -> EXIT 0
           last printed "Global Iteration count 90", at print_convg_per_niter 10
           with num_half_iter 100 -- i.e. 100 iterations, by the 90 + 10
           arithmetic services/case_run_note.iteration_span uses.
           Wrote binDumpZogrid.dat, xtecp_sol_allzogrid.dat, uniconesogrid.enorm,
           tWall_valuesogrid.dat, vsurface_qtyogrid.dat.

THIS IS THE FIRST MULTI-BLOCK GRID OF MORE THAN ONE BLOCK TO GO THROUGH EITHER
BINARY. ``.claude/rules/mesher-multiblock.md`` recorded that as outstanding for #53
on the grounds that "this checkout has no solver tree"; it has one, and the run
above is it.

BLIND SPOTS, named rather than papered over:

  * Nothing here re-runs the solver. The figures above are a record of one dated
    run, not something this file measures.
  * The circles are stored as POLYLINES, so "follows the circle" is measured
    against the polyline's own vertices, and how finely each is stored is a
    property of the geometry file rather than of anything this path enforces. #95
    chose the far field's 320 facets so the mesh no longer reads a curve coarser
    than itself; NOTHING GATES THAT CHOICE against a later change to the topology's
    declared counts, which is the coupling #95 refused to create. What names the
    cost when it goes wrong is #94's warning, group 9 below.
    Nothing on this path projects onto an analytic curve --
    BL_USE_ANALYTIC_GEOM survives into this mode and is still not read.
  * Check 8 measures conformity on the EXPORTED files, so it cannot distinguish a
    ring that welded correctly from one that was welded correctly and then
    exported correctly. That is the same boundary test_multiblock_weld_surface.py
    works at, and the node-identity half is check 33 next door.

Run:  python3 tools/PreProcessor/tests/test_multiblock_ogrid_surface.py
      python3 tools/PreProcessor/tests/test_multiblock_ogrid_surface.py --write
          rewrites the two shipped geometries from the generator below.
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import math
import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_GEOM = os.path.join(_REPO, "examples", "geometries")
_TOPO = os.path.join(_REPO, "examples", "topology", "ogrid_circle.json")
sys.path.insert(0, _HERE)
from mesher_bin import NO_SMOOTH, mesher_env as _mesher_env
# THE ONE shipped-config retargeter (#126). Imported, never re-implemented:
# `test_shipped_config_seam.py` derives the set of them from the tree and fails
# on a second, because three copies of this rule is what #124 had to record.
from mb_shipped_config import shipped_config   # noqa: E402

# #55's OWN RECORDED BASELINE for this case, on the same terms as the C-grid's:
# declared once, in the gate that owns the case, and read by
# test_multiblock_quality_gate.py rather than retyped there.
OGRID_BASELINE = {
    "nonortho_max_deg": 2.250,
    "nonortho_mean_deg": 1.875000,
    "wall_first_cell_worst_rel": 0.000812,
}          # noqa: E402
from test_multiblock_weld_surface import (                # noqa: E402
    bnd_faces, cel_cells, components, edge_use, vrt_nodes)
# The ONE writer of this repo's `.meta` sidecar convention. It lives next door
# because #57 needed it for a two- and a six-segment body; there is no second copy.
from test_multiblock_cgrid_surface import closed_polyline_meta   # noqa: E402
# The ONE parser for the machine-readable quality line, in the gate that owns
# that line. Imported rather than copied: this file and the O-grid's each held a
# byte-identical copy until #81, which had to fix the same character in both.
from test_multiblock_quality_surface import qlines as _qlines   # noqa: E402

# The two shipped circles, as (basename, radius, points per quarter, BC label).
#
# THE FAR FIELD IS 320 FACETS SINCE #95, and the number is the density past which
# the far field STOPS BINDING rather than a convergence point. At the shipped 20
# per quarter (80 facets) it was COARSER than the 96-node ring reading it — 0.833
# facets per mesh interval — so the ring meshed an irregular polygon and #55's
# 2.250 deg baseline was that sampling artefact rather than a floor (#93). At 80
# per quarter the worst corner moves off the far field onto the BODY and reads
# 2.025, which is the body's own 1.667 ratio; 160 and 640 per quarter read the
# same 2.025 because the far field is no longer what binds.
#
# NOT MADE COMMENSURATE, deliberately. Matching the ring's own 96 nodes — or any
# integer multiple of them — reaches the 1.875 floor, but that couples a geometry
# file to node counts the topology PROPAGATES, so a later change to one declared
# count would silently take the quality back to ~2.2 with nothing to say so. #95
# took the robust 2.025 over the fragile 1.875. The coupling is not enforced
# anywhere; what names the cost when it is wrong is #94's per-edge warning, which
# still fires on the body's four edges and is asserted in check 9.
SHIPPED = (("circle_body", 0.5, 40, "wall"),
           ("circle_farfield", 10.0, 80, "farfield"))

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def write_circle(radius, per_quarter, bc):
    """``(dat_text, meta_text)`` for a CLOSED circle in four quarter segments.

    THE ONE generator for the shipped circles, so check 1 can compare the
    committed files against it instead of trusting them.

    The `.meta` conventions it has to reproduce -- the closing duplicate the
    loader drops, and a joint belonging to the LATER segment -- are not written
    out here: they live in ``closed_polyline_meta``, which is the ONE writer of
    them, and this function is one call to it. Two copies of that convention is
    how the two come to disagree, and the failure mode is a mesh with corners on
    the wrong segments and no error at all.
    """
    n = 4 * per_quarter

    def at(k):
        a = 2.0 * math.pi * k / n
        return (radius * math.cos(a), radius * math.sin(a))

    # Segments overlap by one point, which is what closed_polyline_meta expects:
    # quarter `s` runs from its own first sample to the NEXT quarter's, and that
    # shared joint belongs to the later of the two.
    segs = [[at(k) for k in range(s * per_quarter, (s + 1) * per_quarter + 1)]
            for s in range(4)]
    return closed_polyline_meta(segs, [bc] * 4)


def _write_shipped():
    for name, radius, per_quarter, bc in SHIPPED:
        dat, meta = write_circle(radius, per_quarter, bc)
        with open(os.path.join(_GEOM, name + ".dat"), "w", encoding="utf-8") as f:
            f.write(dat)
        with open(os.path.join(_GEOM, name + ".dat.meta"), "w", encoding="utf-8") as f:
            f.write(meta)
        print("wrote " + name)


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


def base_config(topo=_TOPO, thickness=None, geom_dir=_GEOM):
    """The shipped O-grid config, retargeted at a temp output stem.

    Read from disk rather than rebuilt, for the reason the cavity golden case
    gives: config/multiblock_ogrid.dat is documentation a user runs, and a test
    that composed an equivalent one would leave an edit to the shipped file
    invisible here.

    THE RETARGETING RULE ITSELF IS `mb_shipped_config.shipped_config`; what stays
    here is the O-grid's share of it — which topology, which directory the two
    circles come from, and the wall spacing checks 6 and 7 drive. That rule was
    written out in full here, in the C-grid gate and in the smoothing gate until
    #126 collapsed the three; the name survives because four other files import
    it.
    """
    return shipped_config(
        "multiblock_ogrid",
        paths={"MESH_TOPOLOGY_FILE": topo},
        dirs={"GEOM_FILE": geom_dir},
        overrides=({"BL_INITIAL_THICKNESS": thickness}
                   if thickness is not None else None))


def main() -> int:
    if "--write" in sys.argv:
        _write_shipped()
        return 0
    if not os.path.exists(_BIN):
        print("SKIP: build/HybMesh2D not found (run ./build.sh first)")
        return 0

    # ── 1. the shipped geometries ARE what the generator produces ───────────
    for name, radius, per_quarter, bc in SHIPPED:
        dat, meta = write_circle(radius, per_quarter, bc)
        for ext, want in ((".dat", dat), (".dat.meta", meta)):
            path = os.path.join(_GEOM, name + ext)
            got = open(path, encoding="utf-8").read() if os.path.exists(path) else None
            check(f"1. {name}{ext} is exactly what write_circle() produces",
                  got == want)

    with tempfile.TemporaryDirectory() as tmp:
        # ── 2. the shipped O-grid meshes, with zero inverted cells ──────────
        p, stem = run_case(tmp, "ogrid", base_config())
        check("2. the shipped O-grid config exits 0 (rc=%d)" % p.returncode,
              p.returncode == 0)
        q = quality(p.stdout)
        check("2. it prints the machine-readable quality line", bool(q))
        check("2. ZERO inverted cells (got %s)" % q.get("inverted"),
              q.get("inverted") == 0.0)
        check("2. ...over a mesh that is actually there (%s cells)" % q.get("cells"),
              (q.get("cells") or 0) > 1000)

        nodes = vrt_nodes(stem)
        cells = cel_cells(stem)
        faces = bnd_faces(stem)

        # ── 3. the wall FOLLOWS the circle, and the chord is the control ────
        by_patch = {}
        for key, name in faces:
            by_patch.setdefault(name, set()).update(key)
        wall_ids = by_patch.get("wall", set())
        radii = [math.hypot(*nodes[i - 1]) for i in sorted(wall_ids)]
        worst = max(abs(r - 0.5) for r in radii) if radii else 1.0
        # A 25-node quarter-circle CHORD would put its midpoint at
        # 0.5*cos(45 deg) = 0.354, i.e. 0.146 off the body. The measured figure
        # must be orders below that, not merely below it.
        check("3. every wall node is ON the circle (worst radial deviation %.3e, "
              "against the 1.46e-01 a chord would give)" % worst,
              worst < 1.0e-3)
        # 4 arcs x 25 nodes, the four block corners shared: 96 distinct wall
        # nodes. Named exactly rather than as "enough of them", so a binding that
        # silently stopped covering one arc could not pass this by being close.
        check("3. ...over all 96 distinct wall nodes, not a lucky few (%d)"
              % len(radii),
              len(radii) == 96)

        # ── 4. each geometry's own condition reaches the .bnd ───────────────
        counts = {}
        for _key, name in faces:
            counts[name] = counts.get(name, 0) + 1
        check("4. the .bnd carries BOTH conditions, from the two geometries (%r)"
              % counts,
              set(counts) == {"wall", "farfield"})
        check("4. ...in equal halves, four patches each (%r)" % counts,
              counts.get("wall") == counts.get("farfield") ==
              len(faces) // 2 > 0)

        # ── 8. the ring is CONFORMAL where it closes ────────────────────────
        use = edge_use(cells)
        boundary = {k for k, n in use.items() if n == 1}
        check("8. every interior edge belongs to exactly two cells",
              all(n in (1, 2) for n in use.values()))
        check("8. the boundary edge set is exactly the .bnd (%d vs %d)"
              % (len(boundary), len(faces)),
              boundary == {k for k, _ in faces})
        check("8. the whole ring is ONE connected component by node identity",
              components(cells, len(nodes)) == 1)

        # ── 5. the wall height TRACKS BL_INITIAL_THICKNESS ──────────────────
        for thickness in ("1e-3", "1e-5", "1e-7"):
            p2, _ = run_case(tmp, "t" + thickness.replace("-", "_"),
                             base_config(thickness=thickness))
            q2 = quality(p2.stdout)
            check("5. BL_INITIAL_THICKNESS %s: exit 0, zero inverted" % thickness,
                  p2.returncode == 0 and q2.get("inverted") == 0.0)
            check("5. ...and the wall first cell is within 0.1%% of it (%.4f%%)"
                  % (100.0 * (q2.get("wall_first_cell_worst_rel") or 1.0)),
                  (q2.get("wall_first_cell_worst_rel") or 1.0) < 1.0e-3)

        # ── 6. a per-edge ds_start beats the global ─────────────────────────
        topo = open(_TOPO, encoding="utf-8").read()
        over = os.path.join(tmp, "ogrid_override.json")
        with open(over, "w", encoding="utf-8") as f:
            f.write(topo.replace('"spacing": {"wall_ends": "start"}',
                                 '"spacing": {"ds_start": 2.5e-06}'))
        p3, stem3 = run_case(tmp, "ov", base_config(topo=over, thickness="1e-3"))
        check("6. a per-edge ds_start is accepted (rc=%d)" % p3.returncode,
              p3.returncode == 0)
        # Measured on the exported grid, not on the banner: the shortest edge
        # touching a wall node IS the first cell off the wall.
        n3 = vrt_nodes(stem3)
        shortest = min(
            math.dist(n3[a - 1], n3[b - 1])
            for a, b in (tuple(k) for k in edge_use(cel_cells(stem3)))
        )
        check("6. ...and the EDGE's 2.5e-06 is what the mesh has, not the "
              "config's 1e-3 (shortest cell edge %.3e)" % shortest,
              abs(shortest - 2.5e-6) < 0.1 * 2.5e-6)

        # ── 7. the ring's seeded count does not move the wall spacing ───────
        #
        # PINNED AT ZERO SWEEPS SINCE #85, when the shipped default became 20. The
        # property under test belongs to the SPACING LAW — a radial count this
        # equivalence class propagated rather than chose still lands the first cell
        # where `BL_INITIAL_THICKNESS` asks — and the elliptic solve's own
        # convergence depends on how many lines it has, so at the default the three
        # counts come out at 0.049% / 0.044% / 0.022% and the law's invariance is no
        # longer what the check would be reading. The default's own figures are
        # gated in test_multiblock_quality_gate.py.
        heights = {}
        for count in (25, 49, 97):
            path = os.path.join(tmp, "c%d.json" % count)
            with open(path, "w", encoding="utf-8") as f:
                f.write(topo.replace('"count": 49', '"count": %d' % count))
            p4, _ = run_case(tmp, "c%d" % count,
                             base_config(topo=path) + NO_SMOOTH)
            q4 = quality(p4.stdout)
            check("7. the ring at radial count %d: exit 0, zero inverted" % count,
                  p4.returncode == 0 and q4.get("inverted") == 0.0)
            heights[count] = q4.get("wall_first_cell_worst_rel")
        check("7. ...and the wall first-cell accuracy is UNCHANGED across all "
              "three (%r) — the count is propagated to three of the four radials, "
              "so the law absorbs one it did not choose" % heights,
              len(set(heights.values())) == 1 and None not in heights.values())


        # ── 9. THE SAMPLE RATE IS SAID, AND ITS NUMBER IS THE MESH's GAP ────
        #
        # #94. SINCE #95 THE FAR FIELD IS 320 FACETS and costs less than the
        # warning's own tolerance, so its four edges say nothing; the BODY is still
        # 160 facets under the same 96-node ring — 1.667 facets per interval, which
        # does not divide — and its four edges still warn. Four, not eight, and the
        # four that remain are the ones that still cost something.
        #
        # AND THE CHECK IS NOT THAT IT WARNED. Anyone can print a warning; what
        # makes this one worth reading is that its figure ACCOUNTS FOR the gap
        # between this mesh's worst corner and its mean. Unsmoothed, this case is
        # max 2.250000 / mean 1.875000, and the worst warned excess is 0.750 deg of
        # boundary TURN — half of which is 0.375, the gap exactly. The mean is the
        # floor here because a regular 96-gon's every quad corner deviates by half
        # the sector angle (360/96/2), which is #93's finding; so the whole of this
        # case's unmet #80 bullet is in that one number.
        #
        # IT SURVIVED #95, WHICH IS THE POINT OF WRITING IT AS A RELATION. #95 left
        # a residue rather than removing one — the far field stopped binding and the
        # BODY's 1.667 ratio became the whole of it — and the relation reads the new
        # residue as exactly as it read the old: max 2.024972 - mean 1.875000 =
        # 0.149972 against half the body's warned 0.300 deg of turn = 0.150000, four
        # digits, on a mesh neither figure was written against. Only the count below
        # is a fact about TODAY's geometry. The permanent home of the weakness itself
        # is the C++ gate's check 57, whose fixture is non-commensurate by
        # declaration rather than by accident.
        p5, _ = run_case(tmp, "rate", base_config() + NO_SMOOTH)
        q5 = quality(p5.stdout)
        said = [ln for ln in (p5.stdout + p5.stderr).splitlines()
                if "sample a bound stretch" in ln]
        # WHICH FOUR, NOT HOW MANY. A count cannot tell the four body arcs from the
        # four far-field ones, so four far-field warnings with the body silent would
        # read the same — and that is the state #95 was supposed to leave behind.
        # The edge names are in the message; the topology calls the body's arcs
        # w0..w3 and the far field's o0..o3 (f0..f3 are that circle's CORNERS).
        named = sorted(set(re.findall(r"edge '([^']+)'", "\n".join(said))))
        check("9. every bound edge whose sample rate costs something is named, and "
              "ONLY those (%d warnings on %r; the shipped ring is 96 nodes over a "
              "320-facet far field and a 160-facet body, so the four BODY arcs fire "
              "and the four far-field arcs no longer do)" % (len(said), named),
              len(said) == 4 and named == ["w0", "w1", "w2", "w3"])
        worst = 0.0
        for ln in said:
            m = re.search(r"so ([0-9.]+) deg of that corner is the SAMPLE RATE", ln)
            if m:
                worst = max(worst, float(m.group(1)))
        gap = (q5.get("nonortho_max_deg", -1.0)
               - q5.get("nonortho_mean_deg", -1.0))
        # A boundary turn of t puts about t/2 into the quad corners either side of
        # it, so half the worst excess is what reaches the metric. The slack is the
        # bar's own half: an edge whose cost sits under MB_SAMPLE_RATE_TOL_DEG says
        # nothing and may still contribute that much to the gap.
        check("9. ...and the worst of those figures ACCOUNTS FOR this mesh's whole "
              "corner gap: max %.6f - mean %.6f = %.6f deg, against half the worst "
              "warned excess of %.3f deg of turn = %.6f"
              % (q5.get("nonortho_max_deg", -1.0), q5.get("nonortho_mean_deg", -1.0),
                 gap, worst, worst / 2.0),
              p5.returncode == 0 and gap >= worst / 2.0 - 1e-3
              and gap <= worst / 2.0 + 0.05 + 1e-3)

    print()
    if failures:
        print("%d check(s) failed:" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("PASS test_multiblock_ogrid_surface")
    return 0


if __name__ == "__main__":
    sys.exit(main())
