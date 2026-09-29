#!/usr/bin/env python3
"""The TWO-RING O-GRID, end to end through the real binary (issue #153).

#151 shipped the key (``follows``) and a two-block fixture that proves it works;
this is the case a user runs. Eight blocks around the same circular body the
four-block O-grid uses, split by a curved seam into a wall ring and a far-field
ring, from ``examples/topology/tworing_ogrid.json`` +
``config/multiblock_tworing.dat`` — and it needed no C++ change at all, which is
the strongest thing this gate says about #151's design.

THE ARGUMENT IS A MEASUREMENT, NOT A DESCRIPTION, and the measurement does not
come out the way the batch's problem statement predicted. The comparison against
the shipped single ring is checks 8 and 9 here and is written up in
``docs/design_notes/mesher.md`` under "A TWO-RING O-GRID, MEASURED AGAINST THE
SINGLE RING". The headline: at an IDENTICAL budget — 4704 vertices, 9216
triangles, 192 boundary edges, because 96 x (25 + 25 - 1) is 96 x 49 — the two
rings buy a better-held wall spacing and a better cell shape, buy NOTHING at all
on non-orthogonality, and COST wall-normal expansion ratio. That last one is the
number #150 expected to win on.

What this pins down:

  1. The shipped middle ring IS what the one circle generator produces. Same
     property check 1 of the O-grid gate makes about the body and the far field,
     and for the same reason: a hand-edited ``.dat`` whose ``.meta`` still
     describes the old point set is a mesh with corners on the wrong segments and
     no error at all. The generator is imported from that gate, never copied.
  2. The shipped case meshes: exit 0, zero inverted cells, eight blocks of
     25 x 25, and the machine-readable ``HYBMESH_MB_QUALITY`` line.
  3. The run NAMES all four seam edges as interfaces FOLLOWING their own segment
     of ``circle_seam.dat``, and names the eight radials straight chords — the
     shared-edge report's path-source half, which is how a user sees that the seam
     they declared is the seam they got.
  4. The seam's 96 nodes lie ON the middle ring, and the negative control is the
     same document with its four ``follows`` removed, where they lie on the four
     quarter CHORDS instead. The tolerance is derived from the polyline's own
     sagitta: one 120-per-quarter facet departs from the circle by 2.142e-05, and
     the quarter chord departs from it by 0.2929 — four orders apart, so this
     check cannot pass by the two being close.
  5. The seam is NOT a boundary. No ``.bnd`` face has both ends on the middle
     ring, and no patch carries its sidecar's label ``seam`` — which is unmapped
     on purpose, so a condition that leaked would arrive under its own name rather
     than hiding inside ``wall``. The ``.bnd`` is exactly the single ring's 192
     faces in two patches.
  6. The two rings are CONTINUOUS across the seam, and that is declared rather
     than tuned. The last cell into the seam and the first cell out of it agree to
     nine decimal places on the unsmoothed mesh, because the topology's
     ``ds_start`` IS the inner ring's own last interval. The negative control is
     the same document with that key removed: the outer ring goes uniform and the
     first cell out of the seam is 6.45 times the last cell into it.
  7. The grid is CONFORMING, on the exported files rather than argued: every
     interior edge of the triangulation belongs to exactly two cells, the boundary
     edge set is exactly the ``.bnd``, and it is one connected component. Eight
     blocks, two rings welded along a curve and each ring closed back on itself,
     is the most welding any shipped document does.
  8. THE BUDGET IS THE SINGLE RING'S, EXACTLY — vertices, cells and boundary
     edges all equal, read off BOTH runs rather than asserted of one. Without that
     the comparison below would be an impression.
  9. THE COMPARISON, on the three quantities #153 names plus the one that moved.
     Measured here rather than quoted, at the shipped default of 20 sweeps AND with the
     smoother off — both tables of the design note's write-up, so no direction of the
     comparison is gated only at the cap that flatters it.
 10. The seam SURVIVES the default sweeps: the smoother reports it frozen, and the
     96 nodes are still on the middle ring in the exported file. #151's check 3
     made this claim about a two-block fixture; this is it on eight blocks.
 11. #94's sample-rate advice does NOT fire on the seam — 120 facets to 24
     intervals is five whole facets to a node — while it still fires on the body's
     four edges at 1.667, and its count advice there still reads 41. That last
     clause is what the middle ring's faceting was CHOSEN for, and it is the thing
     a later edit to that geometry would silently break: the advice is the GCD over
     the equivalence class, and the seam joined that class, so a 96- or 192-facet
     middle ring pulls it from 40 down to 8 and tells the user to coarsen the body
     to 9 nodes.

THE ACCEPTANCE RUN, dated and quoted rather than replaced by a shape check. CI has
no solver binary, so this is recorded here in the convention this repo adopted
after a change shipped broken behind 85 green tests that pinned strings and never
executed the solver — and #150 asked for it by name, because this path has already
produced a grid with zero inverted cells that then drove the solver to NaN.

Measured 2026-09-29 on ``examples/topology/tworing_ogrid.json`` +
``config/multiblock_tworing.dat`` at the shipped defaults (eight blocks, 25 x 25
nodes each, r = 0.5 body and r = 1.0 seam in an r = 10 far field,
BL_INITIAL_THICKNESS 0.001, MB_SMOOTH_ITERS 20):

    ./run.sh -conf config/multiblock_tworing.dat
        -> EXIT 0
           4704 vertices, 9216 triangles, 192 boundary edges
           HYBMESH_MB_QUALITY cells=9216 inverted=0
               nonortho_max_deg=2.024972 nonortho_mean_deg=1.875000
               wall_first_cell_worst_rel=0.000000

    solver/preprocess/getPGrid/work/getPGrid < para.in        # the grid converter
        -> EXIT 0
           "Read in 4704 vertices coordinates"
           "Read in 9216 elements"
           "number of boundary elements = 192"
           "Read in 192 boundary condition flags"
           It warns 96 times that it does not know the name 'farfield' and
           defaults those patches to a no-slip wall — its own token list, not this
           path's. Segments 5-8 were given flag 1 (non-reflect far field) in
           ``tworing.bc.def`` by hand for the run below, which is what the GUI's
           solver Boundary Conditions table writes through
           services/bnd_io._NAME_TO_FLAG.

    solver/execute/unicones.eqn6.mac -t tworing input.in      # the solver
        -> EXIT 0
           THE OPERATING POINT, stated because a run without one is not an
           acceptance run: Mach 0.2, T 288 K, unit Re 200, flow angle 0, Linf 1,
           CFL 0.6 constant, ns_sol with CONST_PRANDTL, 100 half-iterations.
           last printed "Global Iteration count 90", at print_convg_per_niter 10
           with num_half_iter 100 -- i.e. 100 iterations, by the 90 + 10
           arithmetic services/case_run_note.iteration_span uses.
           Wrote binDumpZtworing.dat, xtecp_sol_allztworing.dat,
           uniconestworing.enorm, tWall_valuestworing.dat, vsurface_qtytworing.dat.
           NO NaN anywhere in the log; the final boundary-region eL2 norms are
           1.1e-07 / 1.7e-17 / 1.6e-03 / 1.3e-03.

    THE SEAM REACHES THE SOLVER AS NOTHING AT ALL, which is the point of `follows`
    and is visible here: getPGrid read 192 boundary flags over 8 segments, the same
    8 the single ring has. A seam exported as a patch would have arrived as a
    no-slip wall across the middle of the fluid and the run would have converged to
    the wrong answer rather than failing.

BLIND SPOTS, named rather than papered away:

  * Nothing here re-runs the solver. The block above is a record of one dated run,
    not something this file measures.
  * The comparison in checks 8 and 9 is ONE body at ONE budget. A circle is the
    case where a single tanh law has the least trouble spanning wall to far field,
    which is the honest reason the split does not win on expansion ratio here; it
    says nothing about a body where the wall-normal extent varies around it. #150's
    out-of-scope list keeps the two-ring C-grid out of this batch, so there is no
    second case to say it on, and this gate does not pretend otherwise.
  * The expansion ratio in check 9 is measured along ONE ray, the +x axis, which
    every one of the three circles has a node on. The mesh is four-fold symmetric
    by construction so the ray is representative, but it is a sample and not a
    maximum over the mesh.
  * Check 4 measures the seam against the CIRCLE the middle ring discretises,
    recomputed here from its declared radius rather than read out of the file.
    That is a check against the POLYLINE only because the polyline's vertices are
    on that circle by construction, which check 1 is what establishes; a geometry
    whose facets were not would need a point-to-segment distance instead.

Run:  python3 tools/PreProcessor/tests/test_multiblock_tworing_surface.py
      python3 tools/PreProcessor/tests/test_multiblock_tworing_surface.py --write
          rewrites the shipped middle ring from the generator.
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
_GEOM = os.path.join(_REPO, "examples", "geometries")
_TOPO = os.path.join(_REPO, "examples", "topology", "tworing_ogrid.json")
sys.path.insert(0, _HERE)
from mesher_bin import NO_SMOOTH, mesher_env as _mesher_env   # noqa: E402
# THE ONE shipped-config retargeter (#126), imported and never re-implemented.
from mb_shipped_config import shipped_config                  # noqa: E402
# The ONE generator of this repo's circle geometries, in the gate that owns the
# other two (#55). A second copy is guaranteed divergence, and what would diverge
# is the `.meta` convention whose failure mode is a mesh with corners on the wrong
# segments and no error at all.
from test_multiblock_ogrid_surface import write_circle        # noqa: E402
# The ONE set of exported-file readers, in the gate that owns welding.
from test_multiblock_weld_surface import (                    # noqa: E402
    bnd_faces, cel_cells, components, edge_use, vrt_nodes)
# The ONE parser for the machine-readable quality line, in the gate that owns it.
from test_multiblock_quality_surface import qlines as _qlines  # noqa: E402

# The shipped middle ring, as (basename, radius, points per quarter, BC label).
#
# 120 PER QUARTER IS TWO DIVISIBILITY RULES, not a taste for round numbers, and
# check 11 is where both are asserted. It is a multiple of the 24 intervals a seam
# edge carries, so the seam is sampled a whole number of facets to a node and #94's
# advice does not fire on it; and it is a multiple of the body's own 40, so the
# count advice #94 gives on the BODY's four edges still reads 41 rather than the 9
# a 96- or 192-facet ring would drag it down to.
SEAM = ("circle_seam", 1.0, 120, "seam")

# The single ring this case is measured against, and the one thing about it that
# has to be true for the comparison to mean anything.
SINGLE = "multiblock_ogrid"

# Body and far-field radii, for the ray check 9 walks. Declared here rather than
# read off the geometries: a change to either is a change to the case, and this
# gate should say so rather than follow it.
_R_BODY, _R_FAR = 0.5, 10.0

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def base_config(topo=None, geom_dir=None):
    """The shipped two-ring config, retargeted at a temp output stem.

    Read from disk rather than rebuilt, for the reason `mb_shipped_config` gives:
    ``config/multiblock_tworing.dat`` is documentation a user runs, and a test that
    composed an equivalent one would leave an edit to the shipped file invisible
    from the gate that is supposed to be covering it.

    The name is ``base_config`` because ``tools/scripts/golden_mesh.py`` reaches
    every shipped multi-block case through ``mod.base_config()``.

    BOTH ARGUMENTS DEFAULT TO NOTHING rather than to this file's ``_TOPO`` and
    ``_GEOM``: a default that names the shipped value asks for it BY NAME, so the
    gate would go on driving the same topology after the shipped config was
    repointed at another file. Unset, the seam resolves whatever the config says.
    """
    return shipped_config(
        "multiblock_tworing",
        paths=({"MESH_TOPOLOGY_FILE": topo} if topo is not None else None),
        dirs=({"GEOM_FILE": geom_dir} if geom_dir is not None else None))


def fixture():
    """The checked-in topology as data, so a variant differs from it by one key.

    Read from disk for the same reason ``base_config`` is. The shipped documents
    carry ``//`` comments, which the mesher's parser accepts and Python's does
    not."""
    text = "\n".join(ln for ln in open(_TOPO, encoding="utf-8").read().splitlines()
                     if not ln.lstrip().startswith("//"))
    return json.loads(text)


def edge(doc, eid):
    for e in doc["edges"]:
        if e["id"] == eid:
            return e
    raise AssertionError("no edge %r in the shipped topology" % eid)


def run(tmp, name, conf_text, extra=""):
    stem = os.path.join(tmp, name)
    conf = os.path.join(tmp, name + ".dat")
    with open(conf, "w", encoding="utf-8") as f:
        f.write(conf_text.replace("@STEM@", stem) + extra)
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=600)
    return p, stem, (p.stdout or "") + (p.stderr or "")


def quality(out):
    """The quality line for the mesh AS EXPORTED, or ``{}`` when there is none."""
    q = _qlines(out)
    return q[0] if q else {}


def ray_nodes(stem):
    """The exported nodes on the +x axis, in order, which is one whole radial line.

    Every one of the three circles has a vertex at angle 0 and the two corner rings
    are declared at the t = 0 of their segment 0, so this ray carries a node of
    every radial station and of both seam ends."""
    return sorted(x for (x, y) in vrt_nodes(stem) if abs(y) < 1e-12 and x > 0.0)


def intervals(xs):
    return [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]


def ratios(iv):
    return [iv[i + 1] / iv[i] for i in range(len(iv) - 1)]


def off_ring(p, radius):
    """How far a point is from the circle the middle ring discretises."""
    return abs(math.hypot(p[0], p[1]) - radius)


def off_chords(p, radius):
    """How far a point is from the four QUARTER CHORDS between the seam's corners.

    The inscribed square, which is what the seam would be with `follows` gone and
    is therefore the negative control's own measure. Point-to-SEGMENT, not
    point-to-line: the four chords meet at the corners and a point beyond one
    segment's end belongs to its neighbour."""
    best = float("inf")
    for k in range(4):
        a = (radius * math.cos(math.pi * k / 2.0), radius * math.sin(math.pi * k / 2.0))
        b = (radius * math.cos(math.pi * (k + 1) / 2.0),
             radius * math.sin(math.pi * (k + 1) / 2.0))
        vx, vy = b[0] - a[0], b[1] - a[1]
        t = ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / (vx * vx + vy * vy)
        t = min(1.0, max(0.0, t))
        best = min(best, math.hypot(p[0] - (a[0] + t * vx), p[1] - (a[1] + t * vy)))
    return best


def seam_nodes(stem, radius, tol, measure=off_ring):
    """Exported nodes within ``tol`` of the curve ``measure`` is the distance to.

    The seam is IDENTIFIED by where it is, in both directions: on the shipped
    document its 96 nodes are the ones on the middle ring, and on the control with
    `follows` removed they are the ones on the inscribed square. Selecting by
    radius alone would have caught 2976 nodes on the first draft of this gate —
    every node of the whole mesh inside a band as wide as the sagitta being
    measured — and reported the worst of THOSE as the seam's error."""
    return [p for p in vrt_nodes(stem) if measure(p, radius) <= tol]


def shared_edges(out):
    """``{edge id: path-source phrase}`` from the shared-edge report."""
    got = {}
    for m in re.finditer(r"- Interface '(\w+)'\s*:.*?, (a straight chord|following "
                         r"segment \d+ of '[^']+')", out):
        got[m.group(1)] = m.group(2)
    return got


def sample_rate_warns(out):
    """``{edge id: (facets per interval, the count the advice names)}``."""
    got = {}
    for m in re.finditer(r"edge '(\w+)': its \d+ nodes \((\d+) intervals\) sample .*?"
                         r"stored as (\d+) polyline facets", out):
        eid, iv, fac = m.group(1), int(m.group(2)), int(m.group(3))
        got[eid] = (fac / iv, None)
    for m in re.finditer(r"edge '(\w+)':.*?declare count (\d+) on this edge's", out):
        if m.group(1) in got:
            got[m.group(1)] = (got[m.group(1)][0], int(m.group(2)))
    return got


def main() -> int:
    if "--write" in sys.argv:
        name, radius, per_quarter, bc = SEAM
        dat, meta = write_circle(radius, per_quarter, bc)
        with open(os.path.join(_GEOM, name + ".dat"), "w", encoding="utf-8") as f:
            f.write(dat)
        with open(os.path.join(_GEOM, name + ".dat.meta"), "w", encoding="utf-8") as f:
            f.write(meta)
        print("wrote " + name)
        return 0
    if not os.path.exists(_BIN):
        print("SKIP: build/HybMesh2D not found (run ./build.sh first)")
        return 0

    # ── 1. the shipped middle ring IS what the generator produces ───────────
    name, seam_r, per_quarter, bc = SEAM
    dat, meta = write_circle(seam_r, per_quarter, bc)
    for ext, want in ((".dat", dat), (".dat.meta", meta)):
        path = os.path.join(_GEOM, name + ext)
        got = open(path, encoding="utf-8").read() if os.path.exists(path) else None
        check(f"1. {name}{ext} is exactly what write_circle({seam_r}, {per_quarter}, "
              f"'{bc}') produces — the ONE generator, imported from the O-grid gate "
              f"rather than copied", got == want)

    # The two tolerances check 4 lives between, both derived rather than chosen.
    # A facet's own sagitta is how far this polyline can be from the circle it
    # discretises; a quarter's chord sagitta is how far the seam would be from it
    # with `follows` gone.
    facet_sagitta = seam_r * (1.0 - math.cos(math.pi / (4.0 * per_quarter)))
    chord_sagitta = seam_r * (1.0 - math.cos(math.pi / 4.0))

    with tempfile.TemporaryDirectory() as tmp:
        p20, stem20, out20 = run(tmp, "tr20", base_config())
        p00, stem00, out00 = run(tmp, "tr00", base_config(), NO_SMOOTH)

        # ── 2. the shipped case meshes ──────────────────────────────────────
        q20, q00 = quality(out20), quality(out00)
        blocks = re.findall(r"- Block '(\w+)'\s*: (\d+) x (\d+) nodes", out20)
        check(f"2. the shipped two-ring O-grid meshes at the default cap: exit "
              f"{p20.returncode}, {q20.get('cells')} cells, "
              f"{q20.get('inverted')} inverted",
              p20.returncode == 0 and q20.get("cells") == 9216
              and q20.get("inverted") == 0)
        check(f"2. ...and again with the smoother off, which is the mesh checks 4, "
              f"6 and 7 measure (exit {p00.returncode}, {q00.get('inverted')} "
              f"inverted)",
              p00.returncode == 0 and q00.get("inverted") == 0)
        check(f"2. ...over EIGHT blocks of 25 x 25 nodes, four inner and four outer "
              f"({blocks})",
              len(blocks) == 8 and all(b[1] == "25" and b[2] == "25" for b in blocks)
              and [b[0] for b in blocks] == ["q0", "q1", "q2", "q3",
                                             "p0", "p1", "p2", "p3"])

        # ── 3. the shared-edge report NAMES the path source ─────────────────
        se = shared_edges(out20)
        follow = {e: v for e, v in se.items() if v.startswith("following")}
        chord = {e: v for e, v in se.items() if v == "a straight chord"}
        check(f"3. the run names all four seam edges as interfaces FOLLOWING their "
              f"own segment of the middle ring, which is how a user sees that the "
              f"seam they declared is the seam they got ({follow})",
              follow == {"s%d" % k: "following segment %d of 'circle_seam.dat'" % k
                         for k in range(4)})
        check(f"3. ...and the eight radials as straight chords, so the report "
              f"distinguishes the two rather than saying 'interface' twelve times "
              f"({sorted(chord)})",
              sorted(chord) == ["ri0", "ri1", "ri2", "ri3",
                                "ro0", "ro1", "ro2", "ro3"])

        # ── 4. the seam's nodes are ON the middle ring, not on its chords ───
        on = seam_nodes(stem00, seam_r, facet_sagitta)
        worst = max(off_ring(p, seam_r) for p in on)
        far = max(off_chords(p, seam_r) for p in on)
        check(f"4. the seam's {len(on)} nodes lie ON the middle ring to "
              f"{worst:.3e}, inside the {facet_sagitta:.3e} one 120-per-quarter "
              f"facet itself departs from the circle",
              len(on) == 96 and worst <= facet_sagitta)
        check(f"4. ...and those same 96 nodes reach {far:.4f} OFF the chords "
              f"between the seam's corners, which is the {chord_sagitta:.4f} "
              f"sagitta of a quarter — four orders above the tolerance above, so "
              f"this pair cannot pass by the two curves being close",
              abs(far - chord_sagitta) < 1e-6)
        # THE NEGATIVE CONTROL. The same document with its four `follows` removed
        # is the mesh the five earlier documents could only declare: four straight
        # chords, the seam 0.293 inside the ring it is supposed to be.
        doc = fixture()
        for k in range(4):
            del edge(doc, "s%d" % k)["follows"]
        flat = os.path.join(tmp, "flat.json")
        with open(flat, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
        pf, stemf, outf = run(tmp, "flat", base_config(topo=flat), NO_SMOOTH)
        onf = seam_nodes(stemf, seam_r, 1e-9, measure=off_chords)
        worstf = max(off_ring(p, seam_r) for p in onf)
        check(f"4. THE NEGATIVE CONTROL: with the four `follows` removed the same "
              f"document meshes (exit {pf.returncode}) and its {len(onf)} seam "
              f"nodes fall ONTO the four quarter chords — {worstf:.4f} off the ring "
              f"they are meant to lie on, against the {worst:.3e} above",
              pf.returncode == 0 and len(onf) == 96
              and abs(worstf - chord_sagitta) < 1e-6
              and worstf > 1000.0 * max(worst, 1e-12))
        check("4. ...and that run says so in its own report, calling all twelve "
              "interfaces straight chords",
              not [v for v in shared_edges(outf).values()
                   if v.startswith("following")])

        # ── 5. the seam is NOT a boundary ───────────────────────────────────
        faces20 = bnd_faces(stem20)
        pts20 = vrt_nodes(stem20)
        names = sorted(set(n for _, n in faces20))
        on_ring = [f for f, _ in faces20
                   if all(abs(math.hypot(*pts20[v - 1]) - seam_r) <= facet_sagitta
                          for v in f)]
        check(f"5. the .bnd carries {len(faces20)} faces in exactly two patches, "
              f"{names} — the middle ring's own sidecar label 'seam' reaches "
              f"NOTHING, which is what `follows` means and is why that label was "
              f"left unmapped",
              len(faces20) == 192 and names == ["farfield", "wall"])
        check(f"5. ...and no exported boundary face has both ends on the middle "
              f"ring ({len(on_ring)} of them), so the seam is not a band of wall "
              f"through the middle of the fluid", not on_ring)

        # ── 6. the two rings are CONTINUOUS across the seam ─────────────────
        xs = ray_nodes(stem00)
        iv = intervals(xs)
        k = min(range(len(xs)), key=lambda i: abs(xs[i] - seam_r))
        declared = edge(fixture(), "ro0")["spacing"]["ds_start"]
        check(f"6. the +x ray carries {len(xs)} nodes with the seam's at exactly "
              f"x = {xs[k]:.12f}, node {k} of {len(xs) - 1} — 24 intervals in each "
              f"ring, which is the single ring's 48",
              len(xs) == 49 and k == 24 and abs(xs[k] - seam_r) < 1e-12)
        check(f"6. the last cell INTO the seam is {iv[k - 1]:.9e} and the first cell "
              f"OUT of it is {iv[k]:.9e} — a ratio of {iv[k] / iv[k - 1]:.9f}, so "
              f"the seam is not visible as a jump in cell size",
              abs(iv[k] / iv[k - 1] - 1.0) < 1e-6)
        check(f"6. ...and that is DECLARED, not tuned: the topology's `ds_start` on "
              f"the outer radials is {declared:g}, which IS the inner ring's own "
              f"last interval ({iv[k - 1]:.9e}) to {abs(declared / iv[k - 1] - 1.0):.2e} "
              f"relative — the number is the inner ring's arithmetic read off",
              abs(declared / iv[k - 1] - 1.0) < 1e-6)
        # THE NEGATIVE CONTROL for the continuity, in the same shape as check 4's.
        doc2 = fixture()
        for k2 in range(4):
            del edge(doc2, "ro%d" % k2)["spacing"]
        jump = os.path.join(tmp, "jump.json")
        with open(jump, "w", encoding="utf-8") as f:
            json.dump(doc2, f, indent=2)
        pj, stemj, _ = run(tmp, "jump", base_config(topo=jump), NO_SMOOTH)
        ivj = intervals(ray_nodes(stemj))
        check(f"6. THE NEGATIVE CONTROL: drop that one key and the outer ring goes "
              f"uniform — the first cell out of the seam becomes {ivj[k]:.6e} "
              f"against {ivj[k - 1]:.6e} into it, a jump of "
              f"{ivj[k] / ivj[k - 1]:.2f}x that the same mesh otherwise hides",
              pj.returncode == 0 and ivj[k] / ivj[k - 1] > 6.0)

        # ── 7. the grid is CONFORMING ───────────────────────────────────────
        cells = cel_cells(stem20)
        use = edge_use(cells)
        boundary = {f for f, n in use.items() if n == 1}
        interior_bad = [f for f, n in use.items() if n > 2]
        check(f"7. every interior edge of the {len(cells)} exported cells belongs to "
              f"exactly two of them ({len(interior_bad)} do not) — eight blocks, two "
              f"rings welded along a curve and each ring closed back on itself",
              not interior_bad and len(cells) == 9216)
        check("7. ...and the edges used ONCE are exactly the .bnd, face for face, "
              "so the boundary the exporter wrote is the boundary the mesh has",
              boundary == {f for f, _ in faces20})
        check(f"7. ...and it is ONE connected component by node identity, which a "
              f"ring that failed to weld back to itself would not be "
              f"({components(cells, len(pts20))})",
              components(cells, len(pts20)) == 1)

        # ── 8. the budget IS the single ring's, read off BOTH runs ──────────
        ps20, sstem20, sout20 = run(tmp, "sr20", shipped_config(SINGLE))
        ps00, sstem00, sout00 = run(tmp, "sr00", shipped_config(SINGLE), NO_SMOOTH)
        sq20, sq00 = quality(sout20), quality(sout00)
        mine = (len(pts20), len(cells), len(faces20))
        theirs = (len(vrt_nodes(sstem20)), len(cel_cells(sstem20)),
                  len(bnd_faces(sstem20)))
        check(f"8. the two-ring case and the shipped single ring export the SAME "
              f"budget — vertices, cells and boundary faces, {mine} against "
              f"{theirs} — because 96 x (25 + 25 - 1) is 96 x 49. Read off both "
              f"runs, so check 9 is a comparison and not an impression",
              ps20.returncode == 0 and mine == theirs == (4704, 9216, 192))

        # ── 9. THE COMPARISON #153 asks for, measured here ──────────────────
        sxs = ray_nodes(sstem00)
        check(f"9. NON-ORTHOGONALITY does not move: {q20.get('nonortho_max_deg')} / "
              f"{q20.get('nonortho_mean_deg')} deg against the single ring's "
              f"{sq20.get('nonortho_max_deg')} / {sq20.get('nonortho_mean_deg')}. "
              f"Both are set by the 96 nodes AROUND, which the split does not "
              f"touch, and the seam buys exactly nothing here",
              q20.get("nonortho_max_deg") == sq20.get("nonortho_max_deg")
              and q20.get("nonortho_mean_deg") == sq20.get("nonortho_mean_deg"))
        check(f"9. the WALL SPACING is held BETTER through the sweeps: "
              f"{q20.get('wall_first_cell_worst_rel'):.6f} against the single "
              f"ring's {sq20.get('wall_first_cell_worst_rel'):.6f}, both against "
              f"the same 1e-3 declaration — the far-field arcs' first cell is "
              f"declared here and merely inherited there",
              q20.get("wall_first_cell_worst_rel")
              < sq20.get("wall_first_cell_worst_rel"))
        check(f"9. the CELL SHAPE is better at the median and at p95 and the same at "
              f"the max: {q20.get('quad_midline_ratio_median'):.4f} / "
              f"{q20.get('quad_midline_ratio_p95'):.4f} against "
              f"{sq20.get('quad_midline_ratio_median'):.4f} / "
              f"{sq20.get('quad_midline_ratio_p95'):.4f}. The max is the first cell "
              f"off the wall, which both declare identically",
              q20.get("quad_midline_ratio_median")
              < sq20.get("quad_midline_ratio_median")
              and q20.get("quad_midline_ratio_p95")
              < sq20.get("quad_midline_ratio_p95")
              and abs(q20.get("quad_midline_ratio_max")
                      - sq20.get("quad_midline_ratio_max")) < 0.01)
        rr, sr = ratios(intervals(xs)), ratios(intervals(sxs))
        check(f"9. AND THE ONE #150 EXPECTED TO WIN ON GOES THE OTHER WAY. The "
              f"worst wall-normal expansion ratio is {max(rr):.4f} here against "
              f"{max(sr):.4f} on the single ring, unsmoothed: two laws each "
              f"spanning their own range of scales in 24 intervals is a HARDER "
              f"problem than one law spanning the whole of it in 48. Recorded as "
              f"the deliverable rather than tuned away — #153's own criterion",
              max(rr) > max(sr))
        check(f"9. ...and the same three quantities UNSMOOTHED, so the design note's "
              f"second table is gated and not only quoted: wall spacing "
              f"{q00.get('wall_first_cell_worst_rel'):.6f} against "
              f"{sq00.get('wall_first_cell_worst_rel'):.6f} (the fill's own faceting, "
              f"where the single ring is the better of the two), cell shape "
              f"{q00.get('quad_midline_ratio_median'):.4f} against "
              f"{sq00.get('quad_midline_ratio_median'):.4f}, and the SEAM at a "
              f"cell-size ratio of {iv[k] / iv[k - 1]:.9f} — so every direction in the "
              f"comparison is measured at both caps rather than at the flattering one",
              q00.get("wall_first_cell_worst_rel")
              > sq00.get("wall_first_cell_worst_rel")
              and q00.get("quad_midline_ratio_median")
              < sq00.get("quad_midline_ratio_median")
              and abs(iv[k] / iv[k - 1] - 1.0) < 1e-6)

        # ── 10. the seam survives the default sweeps ────────────────────────
        sm = re.search(r"HYBMESH_MB_SMOOTH .*?moved=(\d+) moved_shared=(\d+)", out20)
        after = seam_nodes(stem20, seam_r, facet_sagitta)
        worst_after = max(off_ring(p, seam_r) for p in after)
        check(f"10. the 96 seam nodes are still on the middle ring after the "
              f"default 20 Winslow sweeps ({worst_after:.3e}), because a following "
              f"edge is frozen — the freeze #151 had to widen after those sweeps "
              f"pulled a declared curve off itself",
              len(after) == 96 and worst_after <= facet_sagitta)
        check(f"10. ...and the run says so: {sm.group(1)} movable nodes of 4704, of "
              f"which {sm.group(2)} on a shared edge — the eight radials, and none "
              f"of the four seams",
              sm is not None and int(sm.group(1)) == 4416
              and int(sm.group(2)) == 184)

        # ── 11. #94's advice reaches the body and NOT the seam ──────────────
        warns = sample_rate_warns(out20)
        check(f"11. the sample-rate advice does not fire on ANY seam edge — 120 "
              f"facets to 24 intervals is five whole facets to a node, and a "
              f"stretch carrying a whole number of them costs exactly nothing "
              f"({sorted(warns)})",
              not [e for e in warns if e.startswith("s")])
        body = {e: v for e, v in warns.items() if e.startswith("w")}
        check(f"11. ...while it still fires on the body's four edges at 1.667 "
              f"facets per interval, exactly as it does on the single ring ({ {k: round(v[0], 3) for k, v in body.items()} })",
              sorted(body) == ["w0", "w1", "w2", "w3"]
              and all(abs(v[0] - 40.0 / 24.0) < 1e-9 for v in body.values()))
        check(f"11. ...AND ITS COUNT ADVICE THERE STILL READS 41, which is what the "
              f"middle ring's 120 facets were chosen for: that number is the GCD "
              f"over the equivalence class and the seam JOINED that class, so a "
              f"96- or 192-facet ring would pull it to 8 and tell the user to "
              f"coarsen the body to 9 nodes ({ {k: v[1] for k, v in body.items()} })",
              all(v[1] == 41 for v in body.values())
              and sample_rate_warns(sout20).get("w0", (0, 0))[1] == 41)

    print()
    if failures:
        print("%d check(s) failed:" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
