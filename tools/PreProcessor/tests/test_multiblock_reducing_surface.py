#!/usr/bin/env python3
"""THE FIRST SHIPPED CASE WHOSE NODE COUNT FALLS GOING OUTWARD (issue #196).

The DEVICE is pinned next door in ``tests/cpp/test_multiblock.cpp`` check 66,
which links the pure layer alone and asserts that a corner shared by THREE blocks
is accepted, that its node has valence 3, and that N blocks at a corner make N
count classes. What can only be checked out here is the chain on the SHIPPED
files: the two circle geometries, one topology document, one config, through the
real exporters onto disk -- and above all **that the reduction is real in the
mesh**, not just in the declaration.

#192 built this arrangement and measured it, and then decided that nothing would
leave ``docs/research/``. ``.claude/rules/mesher-block-side.md`` recorded that
decision as a rule with its own blind spot: *"Do not read 'the device exists' as
'the capability is available.'"* This file is that blind spot being closed, and
what it must therefore hold is the part a research document could not: that the
committed declaration still meshes, still reduces, and still costs what it was
measured to cost.

What this pins down:

  1. The committed document is exactly what the ONE generator produces. It is
     GENERATED, so a hand edit to ``examples/topology/reducing_ogrid.json`` is a
     document nothing can reproduce -- the same rule the shipped circles are held
     to by ``test_multiblock_ogrid_surface.py`` check 1.
  2. The shipped case meshes: exit 0, zero inverted cells, and the machine
     readable ``HYBMESH_MB_QUALITY`` line.
  3. **THE COUNT REALLY FALLS**, counted off the exported ``.vrt``: 192 distinct
     nodes on the body circle against 96 on the far field. Every other shipped
     document carries the same number on both, and the negative control is in
     this file -- the plain four-block O-grid on the SAME two circles, counted
     the same way, comes back 96 and 96.
  4. The price, measured in this run rather than quoted: the worst
     non-orthogonality against that same O-grid's. A capability is not a quality
     and the two do not trade evenly; a reader who sees only check 3 would not
     know that.
  5. The off-valence nodes are INTERIOR and there are eight of them -- four of
     valence 3 at the folds and four of valence 5 at the apexes. On the boundary
     a fold node's single cell would have to span 180 degrees, which the mesher
     reports as inverted; ``--embed`` is what moves them inside.
  6. The mesh is CONFORMAL: every interior edge belongs to exactly two cells,
     the boundary edge set is exactly the ``.bnd``, and it is ONE connected
     component. A reduction that silently left a hanging node would pass checks
     2 and 3 and fail this one.
  7. K corner blocks make K RADIAL COUNT CLASSES, so a document that seeds one of
     the four is REFUSED by name. That is the one thing about this arrangement an
     author has to learn, and it is asserted on the SHIPPED document with three
     of its four seeds removed rather than on a fixture.
  8. The two geometries' own conditions still reach the ``.bnd``.

Run:  python3 tools/PreProcessor/tests/test_multiblock_reducing_surface.py
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
_TOPO = os.path.join(_REPO, "examples", "topology", "reducing_ogrid.json")
sys.path.insert(0, _HERE)
# The generator lives under `docs/research/`, with #192's own copy of this
# document beside it, and it is IMPORTED rather than copied for the reason
# `golden_mesh.py` imports the topology writer out of a surface test: a second
# generator is guaranteed divergence, and what would diverge here is the
# arithmetic that decides where a corner block's apex goes.
sys.path.insert(0, os.path.join(_REPO, "docs", "research", "gridpro-blocking-method"))
from mesher_bin import mesher_env as _mesher_env               # noqa: E402
from mb_shipped_config import shipped_config                   # noqa: E402
from test_multiblock_weld_surface import (                     # noqa: E402
    bnd_faces, cel_cells, components, edge_use, vrt_nodes)
from test_multiblock_quality_surface import qlines as _qlines  # noqa: E402

# THE SHIPPED PARAMETERS, in one place and matching the command in the topology
# file's own header. A change here that is not made there leaves a document
# nothing reproduces, which is what check 1 fails on.
SHIPPED_ARGS = dict(folds=4, per_unit=2, depth=13, ordinary=13, notch=0.2,
                    embed=True, smooth_iters=20, r_out=1.8)

# #196's OWN RECORDED BASELINE, declared once, in the gate that owns the case.
REDUCING_BASELINE = {
    "nonortho_max_deg": 53.576,
    "nonortho_mean_deg": 4.702,
    "wall_first_cell_worst_rel": 0.000045,
}

R_BODY, R_FAR = 0.5, 10.0

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def base_config(topo=None):
    """The shipped reducing config, retargeted at a temp output stem.

    Read from disk rather than rebuilt, for the reason ``mb_shipped_config``
    states: ``config/multiblock_reducing.dat`` is documentation a user runs.
    ``topo`` defaults to NOTHING so the seam resolves whatever the config says.
    Named like the other shipped gates' because ``tools/scripts/golden_mesh.py``
    reaches it as ``mod.base_config()``.
    """
    return shipped_config(
        "multiblock_reducing",
        paths=({"MESH_TOPOLOGY_FILE": topo} if topo is not None else None))


def run_case(tmp, name, conf_text):
    stem = os.path.join(tmp, name)
    conf = os.path.join(tmp, name + ".dat")
    with open(conf, "w", encoding="utf-8") as f:
        f.write(conf_text.replace("@STEM@", stem))
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=900)
    return p, stem


def quality(out):
    rows = _qlines(out)
    return rows[-1] if rows else {}


def doc_body(path):
    """The JSON of a topology document, with its `//` header stripped."""
    text = open(path, encoding="utf-8").read()
    return json.loads("\n".join(l for l in text.split("\n")
                                if not l.strip().startswith("//")))


def on_circle(stem, radius, rel=1e-3):
    """How many exported nodes sit on the circle of this radius.

    A BAND, not an equality, and the width is the reason: a wall node is placed
    by ARC LENGTH along the STORED polyline, so it sits on a facet and is inside
    the true circle by that facet's sagitta — 9.6e-5 on the body's 160 facets.
    Counting |p| == r exactly returns only the nodes that happen to land on a
    facet VERTEX, which is 32 of the body's 192. The band is still three times
    narrower than the gap to the next ring out (the first radial cell is 1e-3),
    so it cannot pick up a second ring by accident."""
    return sum(1 for x, y in vrt_nodes(stem)
               if abs(math.hypot(x, y) - radius) < rel * radius)


def valences(stem):
    """node id -> how many cells use it, and the set of boundary node ids.

    READ OFF THE UNSPLIT (quad) EXPORT, which is why the caller runs the case a
    second time with ``MB_SPLIT_QUADS 0``. The shipped default splits every quad
    into two triangles, and a regular interior node then sits in six cells rather
    than four — so a valence counted on the split mesh measures the diagonal rule
    and not the blocking."""
    cells = cel_cells(stem)
    use = {}
    for c in cells:
        for n in set(c):
            use[n] = use.get(n, 0) + 1
    edge = edge_use(cells)
    boundary = set()
    for (a, b), n in edge.items():
        if n == 1:
            boundary.add(a)
            boundary.add(b)
    return use, boundary


def main():
    if not os.path.exists(_BIN):
        print("SKIP test_multiblock_reducing_surface: %s not built" % _BIN)
        return 0

    # ── 1. the committed document is what the generator produces ──────────
    try:
        import make_reducing_annulus as gen
        _, built, _, inner_n, outer_n = gen.build(**SHIPPED_ARGS)
    except Exception as exc:                       # noqa: BLE001 - reported, not hidden
        print("FAIL 1. the generator could not be imported or run: %r" % exc)
        return 1
    committed = doc_body(_TOPO)
    check("1. the committed topology document is EXACTLY what the generator "
          "writes, so a hand edit to it is caught here rather than shipping a "
          "document nothing reproduces", committed == built)
    check("1. ...and the generator's own arithmetic says the ring reduces: inner "
          "%d intervals, outer %d, reduction %d = 2*K*a = 2*%d*%d"
          % (inner_n, outer_n, inner_n - outer_n, SHIPPED_ARGS["folds"],
             SHIPPED_ARGS["depth"] - 1),
          inner_n - outer_n == 2 * SHIPPED_ARGS["folds"] * (SHIPPED_ARGS["depth"] - 1))

    tmp = tempfile.mkdtemp(prefix="mbreduce_")
    p, stem = run_case(tmp, "reducing", shipped_config("multiblock_reducing"))

    # ── 2. it meshes ──────────────────────────────────────────────────────
    check("2. the shipped reducing case exits 0 (rc %d)" % p.returncode,
          p.returncode == 0)
    q = quality(p.stdout + p.stderr)
    check("2. ...and prints the machine-readable quality line", bool(q))
    if not q:
        print("no quality line; the rest cannot be read")
        return 1
    check("2. ...with ZERO inverted cells (%g of %g)"
          % (q.get("inverted", -1), q.get("cells", -1)), q.get("inverted") == 0)

    # ── 3. THE COUNT REALLY FALLS, counted off the exported nodes ─────────
    body_n = on_circle(stem, R_BODY)
    far_n = on_circle(stem, R_FAR)
    check("3. the BODY circle carries %d exported nodes and the FAR FIELD %d, so "
          "the count falls by %d across the mesh and not only in the declaration"
          % (body_n, far_n, body_n - far_n),
          body_n == inner_n and far_n == outer_n)

    # THE NEGATIVE CONTROL, and it is the whole value of check 3: the plain
    # four-block O-grid on the SAME two circles, counted the same way, must come
    # back EQUAL. Without it, a node counter that was simply wrong about one of
    # the two circles would pass above.
    po, so = run_case(tmp, "ogrid", shipped_config("multiblock_ogrid"))
    check("3. the control run (the plain O-grid, same circles) exits 0 (rc %d)"
          % po.returncode, po.returncode == 0)
    ob, of_ = on_circle(so, R_BODY), on_circle(so, R_FAR)
    check("3. ...and IT carries the same number on both circles, %d and %d — "
          "which is what every other shipped document does and what this case is "
          "shipped to be the exception to" % (ob, of_), ob == of_ and ob > 0)

    # ── 4. THE PRICE, measured here rather than quoted ────────────────────
    qo = quality(po.stdout + po.stderr)
    mine = q.get("nonortho_max_deg", -1)
    theirs = qo.get("nonortho_max_deg", -1)
    check("4. the reduction costs ANGLE and this run says how much: worst "
          "non-orthogonality %.3f deg against the plain O-grid's %.3f on the same "
          "two circles — a capability, not a quality" % (mine, theirs),
          mine > 10.0 * theirs > 0.0)
    for key, want in REDUCING_BASELINE.items():
        got = q.get(key, -1)
        tol = max(0.01, abs(want) * 0.02)
        check("4. ...and it still measures what #192 recorded: %s %.6f against "
              "%.6f" % (key, got, want), abs(got - want) <= tol)

    # ── 5. the off-valence nodes are INTERIOR, and there are eight ────────
    #
    # On the UNSPLIT export: a valence is a statement about the blocking, and on
    # the split mesh it would be a statement about the diagonal rule.
    quad_conf = shipped_config("multiblock_reducing")
    check("5. the quads variant really differs from the shipped config",
          "MB_SPLIT_QUADS 1" in quad_conf)
    quad_conf = quad_conf.replace("MB_SPLIT_QUADS 1", "MB_SPLIT_QUADS 0")
    pq, sq = run_case(tmp, "reducing_quads", quad_conf)
    check("5. the unsplit run exits 0 (rc %d)" % pq.returncode, pq.returncode == 0)
    use, boundary = valences(sq)
    interior = {n: v for n, v in use.items() if n not in boundary}
    folds = sorted(n for n, v in interior.items() if v == 3)
    apexes = sorted(n for n, v in interior.items() if v == 5)
    odd = sorted(n for n, v in interior.items() if v not in (3, 4, 5))
    check("5. exactly %d interior nodes have valence 3 (the folds) and %d have "
          "valence 5 (the apexes), one of each per corner block"
          % (len(folds), len(apexes)),
          len(folds) == SHIPPED_ARGS["folds"] and len(apexes) == SHIPPED_ARGS["folds"])
    check("5. ...and NO interior node has any other off-valence (%s) — so the "
          "irregularity is the device and not damage" % odd, not odd)

    # ── 6. conformity ─────────────────────────────────────────────────────
    cells = cel_cells(stem)
    use_e = edge_use(cells)
    hanging = [e for e, n in use_e.items() if n > 2]
    check("6. no edge is used by more than two cells (%d)" % len(hanging),
          not hanging)
    bnd = set(f for f, _ in bnd_faces(stem))
    only_one = set(frozenset(e) for e, n in use_e.items() if n == 1)
    check("6. ...the once-used edges are exactly the .bnd faces (%d vs %d)"
          % (len(only_one), len(bnd)), only_one == bnd)
    comps = components(cells, len(vrt_nodes(stem)))
    check("6. ...and the mesh is ONE connected component (%d)" % comps,
          comps == 1)

    # ── 7. K corner blocks make K count classes ───────────────────────────
    #
    # On the SHIPPED document with three of its four radial seeds removed, so the
    # refusal is asserted about the thing that ships rather than about a fixture
    # written to produce it.
    starved = json.loads(json.dumps(committed))
    dropped = []
    for e in starved["edges"]:
        if e["id"].startswith("rA") and e["id"] != "rA0" and "count" in e:
            del e["count"]
            dropped.append(e["id"])
    sp = os.path.join(tmp, "starved.json")
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(starved, f)
    conf = shipped_config("multiblock_reducing").replace(
        os.path.join(_REPO, "examples", "topology", "reducing_ogrid.json"), sp)
    check("7. the starved document really differs (dropped %s)" % dropped,
          len(dropped) == SHIPPED_ARGS["folds"] - 1 and sp in conf)
    ps, _ = run_case(tmp, "starved", conf)
    said = (ps.stdout + ps.stderr)
    check("7. seeding ONE of the %d radial classes is REFUSED (rc %d)"
          % (SHIPPED_ARGS["folds"], ps.returncode), ps.returncode != 0)
    check("7. ...naming the group that has no count, so the author is told what "
          "to seed rather than that something is wrong",
          "declares a 'count'" in said and "structurally linked" in said)

    # ── 8. the conditions still reach the .bnd ────────────────────────────
    names = set(name for _, name in bnd_faces(stem))
    check("8. the body's 'wall' and the far field's 'farfield' both reach the "
          ".bnd (%s)" % sorted(names),
          "wall" in names and "farfield" in names)

    print()
    if failures:
        print("%d check(s) failed:" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("PASS test_multiblock_reducing_surface")
    return 0


if __name__ == "__main__":
    sys.exit(main())
