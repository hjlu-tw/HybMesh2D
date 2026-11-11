#!/usr/bin/env python3
"""The TEN-BLOCK CHAIN C-GRID, end to end through the real binary (#191).

The demonstrator for #190's chain: a second shipped C-grid whose aerofoil carries
97 nodes per surface against ``config/multiblock_cgrid.dat``'s 49, while every one
of its far-field edges still declares a number that case already declares. It is a
SECOND case beside that one, never a replacement — the comparison needs both
sides, and the four-block case keeps its own pins, its own golden baseline and its
own acceptance run.

WHAT IS NEW IN THIS TOPOLOGY, and therefore what this file measures:

  * THE ONLY TWO CHAIN SIDES IN ANY SHIPPED DOCUMENT. ``i_upper``'s east is
    ``["m1", "m2"]`` and ``i_lower``'s is ``["m3", "m4"]``. Their members are
    resolved to 49 apiece by the outer block beneath each, their SUM
    (49 + 49 - 1 = 97) decides the side facing them, and that side is the
    aerofoil. Counts go OUT of a chain and never into it.
  * A BLOCK BOUNDARY THAT TERMINATES. ``r_mid_up`` and ``r_mid_lo`` separate the
    two outer nose blocks and STOP at the chain's junction instead of running on
    into the inner band. That is the whole of what a chain buys structurally, and
    it is why ``ff1``..``ff4`` can each carry 49 while the aerofoil carries 97.
  * A SECOND RADIAL EQUIVALENCE CLASS, 29 stations from the wall to the seam and
    13 from the seam to the far field. 29 + 13 - 1 = 41, which is exactly what the
    four-block case spends on one class over the same span.
  * AN INTERIOR LINE THAT IS A DECLARED CURVE AND NOT A DRAWN ONE. The seam is
    four arcs of ONE ellipse (centre (1, 0), a = 2, b = 1), so this case adds no
    geometry file at all and reads the four-block case's two unchanged.

WHAT A CHAIN DOES **NOT** BUY, stated first because the easy reading is wrong and
#191's own acceptance criteria can be read that way. **The far field over the nose
carries 97 NODES, not 49.** A block's two opposite sides hold the same number, a
chain's side holds the sum of its members, and nothing in this model gives an
interior node a valence other than four — so the node count along the body and the
node count along the far field are EQUAL at every radius, in this document exactly
as in the one beside it. What a chain changes is which EDGES carry that total and
where the block boundaries between them may stop. Every criterion below is stated
in those terms, and check 5 is the one that holds the distinction.

WHERE THE ADDED CELLS GO — the measurement #188 asks for, taken by this file
rather than quoted (check 9, measured 2026-11-11):

    against config/multiblock_cgrid.dat (5760 quads), binned by the distance from
    the cell centroid to the aerofoil polyline, in chords

                              added   < 1 chord   1-5 chords   > 5 chords
      the CONTROL               3840    2480 64.6%   880 22.9%   480 12.5%
        (the four-block case
         with af_up/af_lo
         raised to 97 and
         nothing else changed)
      THIS CASE                 3840    3042 79.2%   772 20.1%    26  0.7%

    Both add the same 3840 quads, because both put 97 nodes on the aerofoil and
    the node count is conserved out to the far field. What moves is WHERE they
    land: the share beyond one chord falls from 35.4% to 20.8%.

    AND THE LEVER IS NOT THE CHAIN. It is the second radial class: 28 intervals
    inside one chord and 12 over the nine beyond it, against the control's single
    tanh that spends 22 and 18 on the same span. The chain is what lets that split
    be DECLARED with every far-field edge's count unchanged — without it the inner
    band's outer side would have to be one edge, the outer region one block per
    quadrant, and ``e_ff_nose_up`` a 97-node edge. Both halves are necessary and
    the gate holds them separately: check 5 the counts, check 9 the distribution.

GATE 1 — ZERO INVERTED CELLS — is check 2, and it passed on the first run of the
shipped declaration at every cap tried.

GATE 2 — THE SOLVER RUNS — is the dated acceptance run quoted below, in the
convention #55, #57 and #85 established. It is quoted and not re-run: CI has no
solver binary.

THE ACCEPTANCE RUN, measured 2026-11-11 through
``config/pipeline/multiblock_cgrid_chain_demo.json`` and its four-block CONTROL
through ``config/pipeline/multiblock_cgrid_demo.json``, both on the same day,
through the same headless chain, at the SAME operating point — M 0.2, Re 200,
zero incidence, cfl 0.6 constant, num_half_iter 100, print_convg_per_niter 10,
laminar NS. The operating point is stated because #57 measured that it matters:
lowering cfl to 0.3 makes a BAD mesh run too, so a recorded run that does not say
which one it used proves less than it appears to.

    ./run_pipeline.sh config/pipeline/multiblock_cgrid_chain_demo.json

    THIS CASE (ten blocks, 29 + 13 radial, 97 per aerofoil surface)
        mesher    EXIT 0   HYBMESH_MB_QUALITY cells=19200 inverted=0
                           nonortho_max_deg=42.230458 nonortho_mean_deg=5.300418
                           wall_first_cell_worst_rel=0.000666
                           9856 vertices, 19200 triangles, 512 boundary edges
        getPGrid  EXIT 0   "Read in 9856 vertices coordinates"
                           "Read in 19200 elements"
                           "number of boundary elements = 512"
                           "Read in 512 boundary condition flags"
                           480 warnings that it does not know the name
                           'farfield' — its own token list, two per face over the
                           240 far-field faces, exactly the four-block case's 288
                           over its 144. The `.bc.def` the runner DERIVES from the
                           mesh gives segments 1-2 flag 2 (wall, the two aerofoil
                           surfaces) and segments 3-8 flag 1 (non-reflect far
                           field), which is this operating point.
        unicones  EXIT 0   at cfl 0.6, last printed "Global Iteration count 90"
                           at print_convg_per_niter 10 with num_half_iter 100 —
                           i.e. 100 iterations, by the 90 + 10 arithmetic
                           services/case_run_note.iteration_span uses.
                           No NaN anywhere in the log. Residuals finite and
                           O(1e-4) at iteration 90. Wrote binDumpZ,
                           xtecp_sol_allz, unicones.enorm, tWall_values,
                           vsurface_qty — the same five files the control wrote.

    THE CONTROL (the shipped four-block C-grid), re-run the same day so the
    record is a comparison this file measured rather than a quotation against
    #57's and #85's
        mesher    EXIT 0   5920 vertices, 11520 triangles, 320 boundary edges
        getPGrid  EXIT 0   same four counts at its own sizes, 288 'farfield'
                           warnings
        unicones  EXIT 0   at cfl 0.6, last printed "Global Iteration count 90",
                           100 iterations, no NaN

WHAT THIS RUN DOES **NOT** EXERCISE, so it is not read as more than it is:

  * It is ONE operating point and the claim is "the solver runs on this mesh". It
    is not convergence and not accuracy, and no pressure distribution is compared
    with anything — not even against the control. The four-block gate next door
    records WHY that question cannot be answered at this operating point
    (measured 2026-10-01, #157): no shipped case in this repo reaches a settled
    force here, so a force difference read between two meshes drifts with the
    iteration count rather than settling.
  * Nothing here re-runs the solver. The figures above are a record of one dated
    run.
  * NO OUTPUT IS ON DISK, following #55: no para.in, no bc.def, no solver output
    is committed, so these figures are a quotation and not a reproduction. The
    case itself is reproducible — the pipeline script is shipped.

BLIND SPOTS, named rather than papered over:

  * THE THREE CONTINUATION SPACINGS IN THE DOCUMENT ARE DERIVED AND NOTHING
    ENFORCES THE RELATION. ``0.11082851`` is the inner band's own final radial
    interval, ``0.01537496`` is ``m1``'s final interval and ``0.03757995`` is
    ``ff1``'s, each read off an unsmoothed run and written into the edge beside
    it. Change a count, a span or ``BL_INITIAL_THICKNESS`` and all three are
    wrong — and what would say so is the size jump ACROSS SEAMS, which this file
    prints but does not bar. It is the same shape as the four-block case's blind
    spot about its two 0.005s and is recorded in the same words.
  * THE SEAM'S SIZE JUMP IS THE SMOOTHER'S, not the declaration's, and it is
    worse than the four-block case's: 1.357 across seams BEFORE the sweeps and
    2.460 after, against that case's 1.055. The seam is a declared curve, so the
    smoother freezes it and compresses the row beside it. That is the shape
    ``test_multiblock_tworing_offset_surface.py`` already records at 2.733, so
    this case is in family rather than an outlier — but nothing bars it, and
    #183's split figure is what makes it visible at all.
  * NOTHING HERE MEASURES THE SMOOTHER'S BRANCH. This case reaches the cap AT its
    own best residual (best_sweep 20, residual == best), where all five cases in
    ``test_multiblock_smooth_surface.py`` group 14's ``curved`` list reach it
    PAST their best. It is therefore a sixth curved case taking a DIFFERENT
    branch, and it is deliberately not added to that group: doing so would need
    its own dated table in three homes and would assert the opposite of what that
    group asserts.
  * THE BAND'S DISTANCE FROM THE BODY IS NOT UNIFORM. The seam stands between
    0.82 and 1.00 chords off the aerofoil, so "inside the inner band" and "within
    one chord" are nearly but not exactly the same statement, and check 9's bins
    are the DISTANCE and not the band. That is deliberate — the bins are #188's,
    and a bin drawn at the band would be the case grading itself.
  * CHECK 7 MEASURES CONFORMITY ON THE EXPORTED FILES, so it cannot distinguish a
    chain that welded correctly from one that was welded correctly and then
    exported correctly. Same boundary ``test_multiblock_weld_surface.py`` works
    at.

Run:  python3 tools/PreProcessor/tests/test_multiblock_cgrid_chain_surface.py
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
_TOPO = os.path.join(_REPO, "examples", "topology", "cgrid_chain_naca0012.json")
_TOPO4 = os.path.join(_REPO, "examples", "topology", "cgrid_naca0012.json")
sys.path.insert(0, _HERE)
from mesher_bin import mesher_env as _mesher_env            # noqa: E402
# THE ONE shipped-config retargeter (#126). Imported, never re-implemented.
from mb_shipped_config import shipped_config                # noqa: E402
from test_multiblock_weld_surface import (                  # noqa: E402
    bnd_faces, cel_cells, components, edge_use, vrt_nodes)
from test_multiblock_quality_surface import qlines as _qlines   # noqa: E402

# The distance bins #188 states its measurement in, in chords.
BINS = (1.0, 5.0)

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def base_config(topo=None):
    """The shipped chain C-grid config, retargeted at a temp output stem.

    Read from disk rather than rebuilt, for the reason ``mb_shipped_config``
    states: ``config/multiblock_cgrid_chain.dat`` is documentation a user runs.
    ``topo`` defaults to NOTHING rather than to ``_TOPO`` so that the seam
    resolves whatever the config says — the blindness #126's review found in the
    four-block gate's first draft.
    """
    return shipped_config(
        "multiblock_cgrid_chain",
        paths=({"MESH_TOPOLOGY_FILE": topo} if topo is not None else None))


def topology(path=_TOPO):
    """A shipped topology document, PARSED.

    Its ``//`` line comments are the mesher's own extension to JSON, so they are
    stripped here. Line-oriented, like the four-block gate's: no string value in
    this schema contains ``//``.
    """
    with open(path, encoding="utf-8") as f:
        text = "".join("" if s.lstrip().startswith("//") else s
                       for s in f.readlines())
    return json.loads(text)


def run(tmp, name, config_text):
    """Run one config text, returning (exit code, stdout+stderr, output stem)."""
    stem = os.path.join(tmp, name)
    conf = os.path.join(tmp, name + ".dat")
    with open(conf, "w", encoding="utf-8") as f:
        f.write(config_text.replace("@STEM@", stem))
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=600)
    return p.returncode, p.stdout + p.stderr, stem


def _vtk_cells(path):
    """(points, cells) out of a legacy VTK, as coordinate pairs and id tuples."""
    txt = open(path, encoding="utf-8").read().split("\n")
    i, pts, cells = 0, [], []
    while i < len(txt):
        t = txt[i].split()
        if t and t[0] == "POINTS":
            n, vals = int(t[1]), []
            i += 1
            while len(vals) < 3 * n:
                vals += [float(x) for x in txt[i].split()]
                i += 1
            pts = [(vals[3 * k], vals[3 * k + 1]) for k in range(n)]
            continue
        if t and t[0] == "CELLS":
            n = int(t[1])
            i += 1
            for _ in range(n):
                a = [int(x) for x in txt[i].split()]
                i += 1
                cells.append(tuple(a[1:]))
            continue
        i += 1
    return pts, cells


def _body_polyline():
    """The shipped aerofoil, as the polyline both cases bind their walls to."""
    out = []
    with open(os.path.join(_GEOM, "naca0012_cgrid.dat"), encoding="utf-8") as f:
        for ln in f:
            s = ln.split()
            if len(s) >= 2:
                try:
                    out.append((float(s[0]), float(s[1])))
                except ValueError:
                    pass
    return out


def _bin_cells(vtk, body):
    """How many of a mesh's cells fall in each distance-from-the-body bin.

    THE DISTANCE IS TO THE POLYLINE, not to a centre or a chord: #188's bins are
    "within one chord OF THE BODY", and on a 12%-thick aerofoil the two differ by
    the thickness. Segment distance rather than nearest VERTEX, so the answer does
    not depend on how finely the shipped geometry happens to be sampled.
    """
    pts, cells = _vtk_cells(vtk)
    out = [0] * (len(BINS) + 1)
    for c in cells:
        cx = sum(pts[i][0] for i in c) / len(c)
        cy = sum(pts[i][1] for i in c) / len(c)
        best = float("inf")
        for k in range(len(body) - 1):
            ax, ay = body[k]
            bx, by = body[k + 1]
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            if L2 == 0.0:
                d = math.hypot(cx - ax, cy - ay)
            else:
                t = ((cx - ax) * dx + (cy - ay) * dy) / L2
                t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
                d = math.hypot(cx - (ax + t * dx), cy - (ay + t * dy))
            if d < best:
                best = d
        for k, edge in enumerate(BINS):
            if best < edge:
                out[k] += 1
                break
        else:
            out[-1] += 1
    return out


def main():
    if not os.path.exists(_BIN):
        print("SKIP: ./build/HybMesh2D not built")
        return 0

    doc = topology()
    doc4 = topology(_TOPO4)
    edges = {e["id"]: e for e in doc["edges"]}
    edges4 = {e["id"]: e for e in doc4["edges"]}
    blocks = {b["id"]: b["edges"] for b in doc["blocks"]}

    # ── 1. THE CHAIN IS DECLARED, and it is the only one in the tree ──────
    #
    # Read off the SHIPPED document rather than described: an entry of a block's
    # `edges` array that is a LIST is a chain, and a bare id is an ordinary side.
    # Both halves are asserted, because "this document has a chain" and "this
    # document has no accidental chains" are different claims and only the pair
    # says what the schema addition costs an existing reader.
    chains = {bid: [e for e in es if isinstance(e, list)]
              for bid, es in blocks.items()}
    with_chain = sorted(b for b, c in chains.items() if c)
    check(f"1. exactly two of this document's ten blocks carry a chain, and they "
          f"are the two whose body side is an aerofoil surface ({with_chain})",
          with_chain == ["i_lower", "i_upper"])
    check(f"1. ...each being ONE chain of exactly TWO members, in order "
          f"({ {b: c for b, c in sorted(chains.items()) if c} })",
          chains["i_upper"] == [["m1", "m2"]]
          and chains["i_lower"] == [["m3", "m4"]])
    check("1. ...and the chain is this block's EAST, the side facing its "
          "aerofoil, so the sum decides the wall and not a radial",
          blocks["i_upper"][1] == ["m1", "m2"]
          and blocks["i_lower"][1] == ["m3", "m4"])
    check("1. ...while the four-block C-grid beside it has no chain at all, so "
          "that case is reading the schema exactly as it did before #190",
          not any(isinstance(e, list) for es in
                  (b["edges"] for b in doc4["blocks"]) for e in es))

    # ── 2. GATE 1: THE SHIPPED CASE MESHES WITH ZERO INVERTED CELLS ───────
    tmp = tempfile.mkdtemp(prefix="cgrid_chain_")
    rc, out, stem = run(tmp, "chain", base_config())
    q = _qlines(out)
    check(f"2. the shipped config exits 0 (rc {rc})", rc == 0)
    check(f"2. ...and reports ZERO inverted cells, which is gate 1 "
          f"({q[0].get('inverted') if q else 'no quality line'} of "
          f"{q[0].get('cells') if q else '?'})",
          bool(q) and q[0].get("inverted") == 0 and q[0].get("cells") == 19200)
    # THE THREE FIGURES ARE PRINTED AND NOT BARRED, following #57's rule and
    # #128's: what is asserted is that all three were MEASURED, so a silent
    # regression to "not measured" cannot read as "it came out perfect". The bars
    # live in `test_multiblock_quality_gate.py` for the two cases that have a
    # recorded baseline, and this case does not invent one here.
    fig = {k: q[0].get(k) for k in
           ("nonortho_max_deg", "nonortho_mean_deg",
            "wall_first_cell_worst_rel")} if q else {}
    check(f"2. ...and all three quality figures were MEASURED rather than coming "
          f"back negative ({fig})",
          bool(fig) and all(v is not None and v >= 0.0 for v in fig.values()))

    # ── 3. THE AEROFOIL CARRIES DOUBLE, read off both shipped documents ───
    check(f"3. this case's two aerofoil edges each declare 97 against the "
          f"four-block case's 49 — double, read off both shipped documents "
          f"(af_up {edges['af_up'].get('count')}/{edges4['af_up'].get('count')}, "
          f"af_lo {edges['af_lo'].get('count')}/{edges4['af_lo'].get('count')})",
          edges["af_up"]["count"] == edges["af_lo"]["count"] == 97
          and edges4["af_up"]["count"] == edges4["af_lo"]["count"] == 49
          and edges["af_up"]["count"] == 2 * edges4["af_up"]["count"] - 1)
    # AND THE MESH AGREES WITH THE DOCUMENT. A count is a seed, so a declaration
    # saying 97 and a block coming out 49 wide is exactly the failure a document
    # check alone cannot see.
    sizes = dict(re.findall(r"Block '([^']+)'\s*: (\d+ x \d+) nodes", out))
    check(f"3. ...and the two blocks that carry those walls come out 97 wide in "
          f"the RUN, so the count reached the fill ({sizes})",
          sizes.get("i_upper") == "29 x 97"
          and sizes.get("i_lower") == "29 x 97")

    # ── 4. THE CHAIN'S SUM IS WHAT DECIDES IT, and the direction is one-way ─
    #
    # 49 + 49 - 1 = 97 with the junction counted once. The members are NOT seeded
    # here — they are resolved from the outer blocks' far-field edges — so the
    # arithmetic is asserted against the run's own propagation report rather than
    # against two numbers in the document.
    prop = dict((m, int(n)) for m, n in
                re.findall(r"'([^']+)' = (\d+)", out))
    members = ("m1", "m2", "m3", "m4")
    check(f"4. none of the four chain members declares a count — each is resolved "
          f"by the outer block beneath it, which is the one-way propagation this "
          f"case exists to exercise ({ {m: edges[m].get('count') for m in members} })",
          all("count" not in edges[m] for m in members))
    check(f"4. ...and all four come back at 49, the number their own far-field "
          f"edge declares ({ {m: prop.get(m) for m in members} })",
          all(prop.get(m) == 49 for m in members))
    check(f"4. ...so the chain's total is 49 + 49 - 1 = 97 and that is the "
          f"aerofoil's declared count, the junction being ONE declared corner "
          f"counted once (sum {prop.get('m1', 0) + prop.get('m2', 0) - 1})",
          prop.get("m1", 0) + prop.get("m2", 0) - 1 == edges["af_up"]["count"]
          and prop.get("m3", 0) + prop.get("m4", 0) - 1 == edges["af_lo"]["count"])

    # ── 5. EVERY FAR-FIELD EDGE'S COUNT IS ONE THE FOUR-BLOCK CASE ALREADY
    #       DECLARES — and the honest consequence, stated as a number ─────
    #
    # THE CRITERION IS ABOUT EDGES, AND THE TOTAL IS NOT. Both are asserted here
    # together on purpose: the first is what the chain buys, the second is what
    # conservation costs, and either alone is a half-truth a reader would finish
    # in the wrong direction.
    ff = ("e_ff_up", "ff1", "ff2", "ff3", "ff4", "e_ff_lo")
    ff4 = ("e_ff_up", "e_ff_nose_up", "e_ff_nose_lo", "e_ff_lo")

    def count_of(eid, parsed, propagated):
        return parsed[eid].get("count") or propagated.get(eid)

    rc4, out4, _ = run(tmp, "four", shipped_config("multiblock_cgrid"))
    prop4 = dict((m, int(n)) for m, n in re.findall(r"'([^']+)' = (\d+)", out4))
    check(f"5. the four-block case still exits 0, so the numbers compared below "
          f"come from a run and not from a document alone (rc {rc4})", rc4 == 0)
    mine = {e: count_of(e, edges, prop) for e in ff}
    theirs = {e: count_of(e, edges4, prop4) for e in ff4}
    check(f"5. every far-field edge of this case carries a count the four-block "
          f"case already carries on a far-field edge — {sorted(set(mine.values()))} "
          f"against {sorted(set(theirs.values()))} — so refining the aerofoil "
          f"moved no far-field edge's number (mine {mine}, theirs {theirs})",
          set(mine.values()) == set(theirs.values()) == {25, 49})
    check("5. ...and the two that face the aerofoil pair are FOUR edges of 49 "
          "where that case has TWO, which is the chain's doing: the block "
          "boundary between each pair terminates at the chain's junction",
          [mine[e] for e in ("ff1", "ff2", "ff3", "ff4")] == [49, 49, 49, 49]
          and [theirs[e] for e in ("e_ff_nose_up", "e_ff_nose_lo")] == [49, 49])
    # THE HONEST HALF. 49 + 49 - 1 = 97 nodes over the stretch the four-block
    # case covers with 49, because the node count is conserved from the body to
    # the far field. Asserted so that check 5's first clause can never be read as
    # "the far field was not refined".
    check(f"5. ...while the far field over each nose nevertheless carries "
          f"{mine['ff1'] + mine['ff2'] - 1} nodes against that case's "
          f"{theirs['e_ff_nose_up']}, which is the aerofoil's own total: a chain "
          f"moves which EDGES carry a count, never the total",
          mine["ff1"] + mine["ff2"] - 1 == edges["af_up"]["count"]
          > theirs["e_ff_nose_up"])

    # ── 6. THE RADIAL BUDGET IS THE FOUR-BLOCK CASE's, SPLIT IN TWO ───────
    check(f"6. the two radial classes are 29 and 13 and spend 29 + 13 - 1 = 41 "
          f"stations on the span the four-block case spends 41 on, so this case "
          f"buys its near-field resolution out of its own budget rather than by "
          f"growing it (r_te_up_in {edges['r_te_up_in'].get('count')}, "
          f"r_te_up_out {edges['r_te_up_out'].get('count')}, "
          f"four-block r_te_up {edges4['r_te_up'].get('count')})",
          edges["r_te_up_in"]["count"] + edges["r_te_up_out"]["count"] - 1
          == edges4["r_te_up"]["count"] == 41)
    check("6. ...and no block has one of each as its two i-sides, which is what "
          "makes them two classes rather than one — the inner band's 28 "
          "intervals answer to the wall and the outer region's 12 to the far "
          "field",
          all(not ({es[0], es[2]} & {"r_te_up_in", "r_le_in", "r_te_lo_in",
                                     "e_out_up_in", "e_out_lo_in"}
                   and {es[0], es[2]} & {"r_te_up_out", "r_mid_up", "r_le_out",
                                         "r_mid_lo", "r_te_lo_out",
                                         "e_out_up_out", "e_out_lo_out"})
              for es in blocks.values()))

    # ── 7. THE EXPORTED MESH IS ONE CONFORMAL BODY ───────────────────────
    #
    # Measured on the files, which is where a hanging node introduced by a chain
    # would actually show: every interior edge belongs to exactly two cells, the
    # whole mesh is one component by NODE IDENTITY, and the boundary edges are
    # exactly the ones used once.
    nodes = vrt_nodes(stem)
    cells = cel_cells(stem)
    use = edge_use(cells)
    once = {k for k, v in use.items() if v == 1}
    check(f"7. every edge of the exported `.cel` belongs to one or two cells, so "
          f"a chain introduced no hanging node ({sorted(set(use.values()))})",
          set(use.values()) <= {1, 2})
    check(f"7. ...and the whole mesh is ONE component by node identity, across "
          f"the chain junctions and the terminating block boundaries alike "
          f"({components(cells, len(nodes))} component(s), {len(nodes)} nodes)",
          components(cells, len(nodes)) == 1 and len(nodes) == 9856)
    faces = bnd_faces(stem)
    check(f"7. ...and the `.bnd` names exactly the edges used once — no face from "
          f"an interior line, no interior line exported as a boundary "
          f"({len(faces)} faces, {len(once)} used once)",
          len(faces) == len(once) == 512
          and {f[0] for f in faces} == once)

    # ── 8. THE `.bnd` IS THE FOUR-BLOCK CASE'S SHAPE ─────────────────────
    #
    # Splitting a far-field segment into two EDGES must not split it into two
    # PATCHES: the patch key is the source segment, so `ff1` and `ff2` merge. If
    # they did not, a solver BC table derived from the mesh would gain two rows
    # that no geometry declares.
    patches = {}
    for key, name in faces:
        patches[name] = patches.get(name, 0) + 1
    rows = re.findall(r"Boundary '([^']+)'\s*: (\d+) edge\(s\), from segment "
                      r"(\d+) of '([^']+)'", out)
    check(f"8. the run reports EIGHT boundary patches — one per source segment of "
          f"the two geometries, exactly the four-block case's eight — so the two "
          f"edges on each nose segment merged into one patch ({len(rows)})",
          len(rows) == 8)
    seg2 = [r for r in rows if r[2] == "2" and r[3].endswith("cgrid_farfield.dat")]
    check(f"8. ...and far-field segment 2, which `ff1` and `ff2` cover between "
          f"them, is ONE patch of 96 faces rather than two of 48 ({seg2})",
          len(seg2) == 1 and seg2[0][1] == "96")
    check(f"8. ...and the patch NAMES are the three the sidecars declare, with "
          f"nothing on the config's `wall` fallback that the aerofoil did not put "
          f"there ({sorted(patches)})",
          sorted(patches) == ["farfield", "outlet", "wall"])

    # ── 9. WHERE THE ADDED CELLS LAND, against the control #188 states ───
    #
    # THE CONTROL IS BUILT HERE, not quoted: the shipped four-block topology with
    # af_up and af_lo raised to 97 and NOTHING else touched. That is #188's own
    # "doubling the aerofoil's count and changing nothing else", and building it
    # in the gate is what stops its figures being a number someone remembered.
    with open(_TOPO4, encoding="utf-8") as f:
        ctrl_text = f.read().replace('"kind": "wall", "count": 49',
                                     '"kind": "wall", "count": 97')
    check("9. the control is the shipped four-block document with exactly the two "
          "aerofoil counts raised, so it differs from the shipped case in nothing "
          "else",
          ctrl_text.count('"count": 97') == 2)
    ctrl_topo = os.path.join(tmp, "ctrl.json")
    with open(ctrl_topo, "w", encoding="utf-8") as f:
        f.write(ctrl_text)
    rc_c, out_c, stem_c = run(tmp, "ctrl", shipped_config(
        "multiblock_cgrid", paths={"MESH_TOPOLOGY_FILE": ctrl_topo}))
    q_c = _qlines(out_c)
    check(f"9. ...and it meshes (rc {rc_c}, inverted "
          f"{q_c[0].get('inverted') if q_c else '?'})",
          rc_c == 0 and bool(q_c) and q_c[0].get("inverted") == 0)

    body = _body_polyline()
    # MEASURED AS QUADS, so the comparison is between structured cells and not
    # between a split count: `MB_SPLIT_QUADS 0` on all three runs below.
    unsplit = "\nMB_SPLIT_QUADS 0\n"
    rc_b, _, stem_b = run(tmp, "base",
                          shipped_config("multiblock_cgrid") + unsplit)
    rc_c2, _, stem_c2 = run(tmp, "ctrl2", shipped_config(
        "multiblock_cgrid", paths={"MESH_TOPOLOGY_FILE": ctrl_topo}) + unsplit)
    rc_n, _, stem_n = run(tmp, "new", base_config() + unsplit)
    check(f"9. all three unsplit runs exit 0, so the three histograms below "
          f"describe meshes that were exported (base {rc_b}, control {rc_c2}, "
          f"this case {rc_n})", (rc_b, rc_c2, rc_n) == (0, 0, 0))
    h_b = _bin_cells(stem_b + ".vtk", body)
    h_c = _bin_cells(stem_c2 + ".vtk", body)
    h_n = _bin_cells(stem_n + ".vtk", body)
    add_c = [h_c[k] - h_b[k] for k in range(3)]
    add_n = [h_n[k] - h_b[k] for k in range(3)]
    tot_c, tot_n = sum(add_c), sum(add_n)
    check(f"9. both add the SAME number of quads to the base mesh, because both "
          f"put 97 nodes on the aerofoil and the node count is conserved out to "
          f"the far field — the premise the rest of this check rests on "
          f"(control {tot_c}, this case {tot_n})",
          tot_c == tot_n == 3840)
    beyond_c = (add_c[1] + add_c[2]) / float(tot_c)
    beyond_n = (add_n[1] + add_n[2]) / float(tot_n)
    check(f"9. and this case puts a MATERIALLY smaller share of them beyond one "
          f"chord of the body: {100 * beyond_n:.1f}% against the control's "
          f"{100 * beyond_c:.1f}% (added < 1 / 1-5 / > 5 chords — control "
          f"{add_c}, this case {add_n})",
          beyond_n < 0.75 * beyond_c)
    check(f"9. ...and the far bin is where it shows most: "
          f"{100.0 * add_n[2] / tot_n:.1f}% of the added cells land beyond FIVE "
          f"chords against the control's {100.0 * add_c[2] / tot_c:.1f}%, which "
          f"is #188's 'where nobody asked for anything'",
          add_n[2] < 0.25 * add_c[2])
    # THE LEVER, ISOLATED — which is what stops check 9 being read as "the chain
    # moved the cells". Both meshes spend 40 radial intervals on the same span;
    # what differs is how many of them land inside one chord, and that is the
    # second radial class.
    #
    # IT IS 3.8 AND NOT 6, AND THE GAP IS NOT SLACK. The inner band holds 28 of
    # this case's 40 intervals, but the band also runs downstream along the wake
    # to the outlet plane, where it is nineteen chords from the body — so a fifth
    # of its cells are counted in the far bins and the effective figure is 25.9
    # against the base's 22.1. The bar is set below the measurement rather than at
    # it, because this is a RATIO of two histograms and not a count.
    r_b, r_n = h_b[0] / 144.0, h_n[0] / 240.0
    check(f"9. ...and the mechanism is the second radial class, not the chain: "
          f"the base mesh lands {r_b:.1f} of its 40 radial intervals inside one "
          f"chord where this case lands {r_n:.1f} of its own 40 — the inner "
          f"band's own 28, less the stretch of it that runs down the wake "
          f"({h_b} / {h_n})",
          r_n > r_b + 2.0)

    # ── 10. THE FOUR-BLOCK CASE IS UNTOUCHED ──────────────────────────────
    #
    # Asserted here as the two counts a shared-geometry change would move first.
    # The full claim — every pre-existing case byte-for-byte — is
    # `tools/scripts/golden_mesh.py`'s, and this is the cheap daily version of it.
    check(f"10. the shipped four-block C-grid still meshes to its own 5920 "
          f"vertices and 11520 triangles, so adding this case beside it moved "
          f"neither geometry nor mesher "
          f"({len(vrt_nodes(stem_b))} nodes unsplit)",
          len(vrt_nodes(stem_b)) == 5920)

    print()
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for m in failures:
            print("  " + m)
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
