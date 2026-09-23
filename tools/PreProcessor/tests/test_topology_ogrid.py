#!/usr/bin/env python3
"""The O-grid template: bound to the CAD, and REFUSED when a binding breaks (#137).

The H-grid proved the chain from a parameter form to a mesh without touching the
user's geometry. This is the half it left out. What the O-grid adds is a BINDING, and
a binding is only worth having if the failure of one is loud:

  * the walls FOLLOW the geometry, so their boundary conditions are read off that
    geometry's own segments and reach the exported ``.bnd``;
  * a binding is stored as the CAD segment's STABLE ID, so re-sampling a geometry to
    a different point count leaves the topology working with no edit;
  * and an id the geometry no longer has REFUSES the projection and names the edge —
    never a fallback to the configured default condition, which would be a mesh that
    runs, exports and looks right while carrying the wrong conditions.

WHY A POSITIONAL BINDING IS THE THING BEING DESIGNED OUT, restated where the checks
are: an index shifts when a segment is inserted, deleted or reordered, and every
binding after it then names a different segment WITH NO ERROR AT ALL. That is the
same failure class that once exported an entire mesh as ``wall``. Check 9 is written
against a fixture whose segment ids are deliberately NOT 0..n-1, so an implementation
that had quietly used positions cannot pass it by coincidence.

THE FIXTURES ARE STRAIGHT-SIDED WHERE EXACTNESS IS CLAIMED. A square body inside a
square far field has segment arc lengths that are EXACT under resampling, so check 10
can compare two resamplings' projected documents byte for byte instead of allowing a
tolerance — the same argument ``test_multiblock_binding_surface.py`` already makes for
its own corner positions. The curved half is measured where it can be stated exactly:
check 8 runs the derivation against the SHIPPED circles, whose radii are 0.5 and 10,
and check 17 runs the real mesher on them.

WHAT THIS FILE DOES NOT CHECK, because another gate owns it: the structural rules
themselves (``topology_doc_invariants.py``, which checks 1-7 call and which the
H-grid gate calls too), the parameters-to-families comparison
(``test_topology_param_specs.py``, in both directions), what the panel displays
(``test_topology_panel.py``) and that the model persists (
``test_topology_persistence.py``).

INJECTIONS: run by hand, 2026-09-23, each reverted and the tree compared against its
pre-injection state afterwards. Recorded here rather than automated because the
harness lived in a scratchpad. Each line is what the mutation ACTUALLY did, READ FROM
THE EXIT CODE and not from a count of FAIL lines — two of the six CRASH this file
rather than failing a check, and a crash prints no FAIL line at all. Where the result
differed from the prediction written first, the correction is the record.

  A. ``topology_binding.resolve`` stops testing ``seg not in g.spans`` -> exit 1, but
     by CRASHING at check 11's projection with a ``KeyError`` on the missing span
     rather than by failing a check. Predicted "11b, 11c and 11d red". The gate is
     still red, and the shape is worth knowing: with the resolver disabled, the
     missing segment is not detected at all until something indexes it, which is
     precisely the "no error at all" this rule exists to prevent — the crash is an
     artefact of the fixture being the first thing to index, not a diagnostic a user
     would get. Check 17's ``.bnd`` is UNCHANGED either way: downstream of a
     wrong-but-valid binding there is nothing that can tell.
  B. ``_ids`` ignores the stored text and always adopts ``g.seg_ids`` -> exit 1 with
     SIX red: 9c, 11c, 11d, 11f, 11g and 14. Checks 9 and 9b STAYED GREEN, which was
     half the prediction ("check 9 still green") and is the useful half: adoption
     produces the right ids for a geometry that still has them, so the two directional
     checks cannot see it and only 9c — which binds a SUBSET — and the refusal checks
     can. A stored binding is observable through its failure, not through its success.
  C. the clockwise mirror deleted from the block tuple (always the CCW one) -> exit 1,
     check 13 alone. Check 2 STAYED GREEN, because the ring still closes as a
     declaration and only closes the wrong way round in real coordinates. That is why
     13 places the corners instead of reading the declaration order.
  D. the radial seed written onto every radial edge instead of the first -> exit 1,
     check 4 alone: the radials are ONE class that wraps around and closes, so seeding
     four of them is four seeds in one class.
  E. ``radial_count`` returns ``ceil(n)`` instead of ``ceil(n) + 1`` -> exit 1, checks
     8c AND 8e red (103 became 102). Predicted "8c and nothing else"; 8e reddens too
     because it states the derived count beside the override, which is what makes an
     override check also a derivation check.
  F. ``_close_loop`` stops dropping the trailing duplicate -> exit 1, reddening 8,
     8b, 8c, 8d, 8e, 9 and 9b and then CRASHING at check 10. Predicted "15b and 9".
     15b never runs — the crash comes first — so the mutation is caught by the
     derivation and the ids rather than by the check written for it. Segment 0 of a
     closed loop looks non-contiguous with the duplicate left in and is dropped
     entirely, so the body comes back with THREE segments where the mesher sees four.

NAMED BLIND SPOTS:

  * Nothing here drives the GUI. That the panel captures a binding when the user
    names a geometry, and that the read-out shows this derivation, is
    ``test_topology_panel.py``'s.
  * The three-block floor is enforced HERE, against the mesher's refusal measured
    once (2026-09-23: a two-block ring comes back as "block 'q1': its corners ...
    wind clockwise (signed area -0.000000)", topology exit code 8). Nothing in this
    file re-runs that measurement on every pass, so a mesher that later accepted two
    would leave the floor as a conservatism rather than as a rule.
  * Reordering segments WITHOUT renumbering them is not a refusal and is not checked
    as one: with ids, a reorder that keeps the ids keeps the bindings, which is the
    point of storing ids. #137's criterion is about the INDEX SHIFT, and the shift is
    unreachable here — there is no position anywhere in the chain. A reorder that
    RENUMBERS is a delete plus a create, and that is check 11.
  * The 1:1 radial law is stated for a CIRCULAR O-grid, so on the square fixtures the
    radius it uses is the AREA-EQUIVALENT one and the derived count is an
    approximation. Check 8 therefore measures the derivation on circles, where that
    reduction is exact to 6 digits; nothing here measures how good the approximation
    is on a shape that is not a circle, and nothing downstream depends on it — the
    count it produces is a default the user may override.
  * The fixtures are written by this file rather than by the real
    ``surface_resampler``, so a change to the sidecar FORMAT would not be caught
    here. It is caught next door: ``test_multiblock_binding_surface.py`` drives the
    real resampler and feeds its sidecar to the real mesher.

Run:  python3 tools/PreProcessor/tests/test_topology_ogrid.py
Skips the real-binary half cleanly if ./build/HybMesh2D is not built.
"""
from __future__ import annotations

import math
import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
sys.path.insert(0, _GUI)
sys.path.insert(0, _HERE)

import topology_doc_invariants as inv  # noqa: E402
from app.services import topology_binding as tb  # noqa: E402
from app.services import topology_model as tm  # noqa: E402
from app.services import topology_ogrid as og  # noqa: E402

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


# ── fixtures: a closed outline whose segment ids are ours to choose ─────────

def write_outline(stem, r, seg_ids, per_seg, bc, cw=False, square=False):
    """A closed outline as a ``.dat`` plus its ``.meta`` sidecar.

    ``seg_ids`` are written into BOTH the sidecar's ``NSEGMENTS`` rows and its
    per-point ``POINTS`` column, which is where the PreProcessor puts a
    ``SegmentModel.id`` and where the mesher reads one. They are deliberately free to
    be anything, because a binding that is an id must not care what they are.

    ``square=True`` walks the perimeter of a square rather than a circle, so a
    segment's arc length is EXACT under resampling — which is what lets check 10
    compare byte for byte rather than within a tolerance.
    """
    n_seg = len(seg_ids)
    pts, ids = [], []
    for i in range(n_seg):
        for j in range(per_seg):
            f = (i * per_seg + j) / float(n_seg * per_seg)
            if square:
                u = ((4.0 - f * 4.0) if cw else (f * 4.0)) % 4.0
                side, t = int(u), u - int(u)
                x, y = [(r, -r + 2 * r * t), (r - 2 * r * t, r),
                        (-r, r - 2 * r * t), (-r + 2 * r * t, -r)][side]
            else:
                a = 2.0 * math.pi * (-f if cw else f)
                x, y = r * math.cos(a), r * math.sin(a)
            pts.append((x, y))
            ids.append(seg_ids[i])
    pts.append(pts[0])           # the trailing duplicate a closed loop carries
    ids.append(seg_ids[0])
    with open(stem + ".dat", "w", encoding="utf-8") as f:
        for x, y in pts:
            f.write(f"{x:.12f} {y:.12f}\n")
    with open(stem + ".dat.meta", "w", encoding="utf-8") as f:
        f.write("HYBMESH_META 2\n")
        f.write(f"COUNT {len(pts)}\n")
        f.write("NPIECES 0\n")
        f.write(f"NSEGMENTS {n_seg}\n")
        for s in seg_ids:
            f.write(f"{s} {bc} line\n")
        f.write(f"POINTS {len(pts)}\n")
        for k, s in enumerate(ids):
            f.write(f"{s} {1 if k % per_seg == 0 else 0}\n")
    return stem + ".dat"


class Cfg:
    """The duck a binding context reads: a geometry list and one length.

    Deliberately NOT a ``MeshConfig``: ``context_for_config`` is documented as
    duck-typed, and a gate that built the real class would be unable to tell the
    difference between reading those two attributes and reading the class.
    """

    def __init__(self, geoms, first_cell=1e-3):
        self.geom_files = list(geoms)
        self.bl_initial_thickness = first_cell


def model(body, far, **kw):
    kw.setdefault("ogrid_cell", 0.2)
    return tm.TopologyModel(family=og.FAMILY, ogrid_body_geom=body,
                            ogrid_far_geom=far, **kw)


_TMP = tempfile.TemporaryDirectory()
_T = _TMP.name

#: Each fixture pair is a reason, not a variation.
FIX = {
    # Four segments each, ids 0..3: the shape of the shipped hand-written O-grid.
    "4seg": (write_outline(os.path.join(_T, "b4"), 0.5, [0, 1, 2, 3], 10, "wall"),
             write_outline(os.path.join(_T, "f4"), 4.0, [0, 1, 2, 3], 10, "farfield")),
    # ONE segment each: the ticket's own demo (draw a circle and a far-field circle),
    # which only meshes because Splits Per Segment cuts the ring.
    "1seg": (write_outline(os.path.join(_T, "b1"), 0.5, [7], 24, "wall"),
             write_outline(os.path.join(_T, "f1"), 4.0, [9], 24, "farfield")),
    # Segment ids that are NOT positions, and that differ between the two geometries,
    # so an implementation using indices cannot agree with one using ids by accident.
    "odd-ids": (write_outline(os.path.join(_T, "bo"), 0.5, [5, 11, 2, 40], 10, "wall"),
                write_outline(os.path.join(_T, "fo"), 4.0, [3, 1, 8, 0], 10,
                              "farfield")),
    # Both outlines wound CLOCKWISE: the block tuple has to mirror, or every ring
    # closes the wrong way round in real coordinates.
    "cw": (write_outline(os.path.join(_T, "bc"), 0.5, [0, 1, 2, 3], 10, "wall",
                         cw=True),
           write_outline(os.path.join(_T, "fc"), 4.0, [0, 1, 2, 3], 10, "farfield",
                         cw=True)),
    # Straight-sided, so arc length is exact under resampling.
    "square": (write_outline(os.path.join(_T, "bs"), 0.5, [2, 4, 6, 8], 12, "wall",
                            square=True),
               write_outline(os.path.join(_T, "fs"), 4.0, [1, 3, 5, 7], 12,
                             "farfield", square=True)),
}

SPREAD = [
    ("4 body segments, one block each — the shipped O-grid's shape", "4seg",
     dict(ogrid_splits=1)),
    ("4 body segments split 3 ways — 12 blocks around the ring", "4seg",
     dict(ogrid_splits=3)),
    ("a single-segment body split 4 ways — the ticket's own demo", "1seg",
     dict(ogrid_splits=4)),
    ("a single-segment body split 3 ways — the smallest ring the mesher's own "
     "block-orientation test accepts", "1seg", dict(ogrid_splits=3)),
    ("segment ids that are not positions", "odd-ids", dict(ogrid_splits=2)),
    ("a clockwise body and far field", "cw", dict(ogrid_splits=1)),
    ("a clockwise body, split 3 ways", "cw", dict(ogrid_splits=3)),
    ("straight-sided outlines, and the radial count overridden", "square",
     dict(ogrid_splits=1, ogrid_radial_count=9)),
    ("a target cell larger than a whole wall edge", "square",
     dict(ogrid_splits=1, ogrid_cell=99.0)),
]


def context(fixname):
    body, far = FIX[fixname]
    return body, far, tb.context_for_config(Cfg([body, far]))


def docs():
    out = []
    for why, fixname, kw in SPREAD:
        body, far, ctx = context(fixname)
        out.append((why, tm.build_document(model(body, far, **kw), ctx)))
    return out


_DOCS = docs()

# ── 1-7. the structural rules, from the ONE checker both family gates call ──
# The invariants live in ``topology_doc_invariants.py``, which the H-grid gate calls
# too, so "what must every family's output satisfy" is one statement rather than one
# copy per family. A second copy is one that can come to disagree, and the family it
# disagreed about would be the one that shipped a refusal.
bad = [c for why, d in _DOCS for c in inv.unique_ids(why, d)]
check("1. every corner, edge and block id is unique, across the spread: "
      + (", ".join(bad) if bad else "none duplicated"), not bad)

bad = [c for why, d in _DOCS for c in inv.ring_closes(why, d)]
check("2. every block's four edges close a ring in [south, east, north, west], "
      "walked by DIRECTION so a swapped pair cannot pass as the same set: "
      + (", ".join(bad) if bad else "all closed"), not bad)

bad = [c for why, d in _DOCS for c in inv.legal_counts(why, d)]
check("3. every declared count is an integer >= 2: "
      + (", ".join(bad) if bad else "all legal"), not bad)

bad = [c for why, d in _DOCS for c in inv.one_seed_per_class(why, d)]
check("4. exactly one count seed per equivalence class — the radials are ONE class "
      "that wraps around and closes, so only the first of them may declare one: "
      + ("; ".join(bad) if bad else "one seed in every class"), not bad)

bad = [c for why, d in _DOCS for c in inv.kind_usage(why, d)]
check("5. every 'wall' bounds exactly one block side and every 'interface' two: "
      + (", ".join(bad) if bad else "all as declared"), not bad)

check("6a. all five schema key sets were READ from src/MultiBlock.cpp by a marker "
      f"key rather than assumed ({sorted(inv.SCHEMA)}), so 6b cannot pass vacuously",
      inv.schema_readable())
bad = [c for why, d in _DOCS for c in inv.no_unknown_keys(why, d)]
check("6b. every emitted key is one the mesher's schema accepts: "
      + (", ".join(bad) if bad else "no unknown key"), not bad)

bad = [c for why, d in _DOCS for c in inv.nothing_orphaned(why, d)]
check("7. no corner lies on no edge and no edge lies in no block: "
      + ("; ".join(bad) if bad else "everything reaches something"), not bad)

# ── 8. the derivation, on the SHIPPED circles, with its working ─────────────
# The one place this ticket's central claim is measurable against numbers written
# before the code existed: 0.0327 at 1:1, a 1e-3 ask, "about 33 times", and the count
# that closes the gap.
_SHIP_B = os.path.join(_REPO, "examples", "geometries", "circle_body.dat")
_SHIP_F = os.path.join(_REPO, "examples", "geometries", "circle_farfield.dat")
_ship_ctx = tb.context_for_config(Cfg([_SHIP_B, _SHIP_F], first_cell=1e-3))
_ship_m = model(_SHIP_B, _SHIP_F, ogrid_splits=1, ogrid_cell=0.0327)
P = og.plan(_ship_m, _ship_ctx)
check(f"8. the shipped circles give a four-block ring of 96 circumferential cells "
      f"(got {P.blocks} blocks, {P.n_theta} cells, wall counts {P.wall_counts}) — "
      f"which is also what the hand-written examples/topology/ogrid_circle.json "
      f"declares by hand",
      not P.problem and P.blocks == 4 and P.n_theta == 96
      and P.wall_counts == (25, 25, 25, 25))
check(f"8b. ...whose 1:1 ratio is exactly 1 + 2π/96 and whose implied wall first "
      f"cell is 3.27e-02 at r = 0.5 (got q = {P.ratio:.5f}, "
      f"ds = {P.first_cell_11:.4e}, r = {P.radius:.4f})",
      abs(P.ratio - (1 + 2 * math.pi / 96)) < 1e-12
      and abs(P.first_cell_11 - 0.0327) < 5e-5 and abs(P.radius - 0.5) < 1e-3)
check(f"8c. ...so a 1e-3 first cell is about 33x flatter than 1:1, and 103 radial "
      f"nodes close the gap (got {P.aspect:.1f}x, {P.radial_derived} nodes)",
      32.0 < P.aspect < 34.0 and P.radial_derived == 103)
check(f"8d. ...and the read-out SHOWS that working rather than only its result — "
      f"the ratio's own expression, the two first cells and the factor between "
      f"them: {P.lines()!r}",
      len(P.lines()) == 4
      and any("2π/96" in ln for ln in P.lines())
      and any("32.7" in ln for ln in P.lines())
      and any("BL_INITIAL_THICKNESS" in ln for ln in P.lines()))
_over = og.plan(model(_SHIP_B, _SHIP_F, ogrid_splits=1, ogrid_cell=0.0327,
                      ogrid_radial_count=17), _ship_ctx)
check(f"8e. the derivation is a DEFAULT and not a cage: an override of 17 is taken "
      f"and reported as one, with the derived count still stated "
      f"(got {_over.radial}, overridden={_over.overridden}, "
      f"derived {_over.radial_derived})",
      _over.radial == 17 and _over.overridden and _over.radial_derived == 103)
_seeded = [e["count"] for e in tm.build_document(_ship_m, _ship_ctx)["edges"]
           if e["id"] == "r0"]
check(f"8f. the radial count the DOCUMENT seeds is the one the plan reports, so the "
      f"panel cannot display a number the mesh does not use ({_seeded} vs "
      f"{P.radial})", _seeded == [P.radial])

# ── 9. a binding is a stable ID, never a position ──────────────────────────
_b, _f, _ctx = context("odd-ids")
_d = tm.build_document(model(_b, _f, ogrid_splits=1), _ctx)
wall_segs = [e["binding"]["seg"] for e in _d["edges"] if e["id"].startswith("w")]
far_segs = [e["binding"]["seg"] for e in _d["edges"] if e["id"].startswith("o")]
corner_segs = [c["seg"] for c in _d["corners"] if c["id"].startswith("b")]
check(f"9. every wall edge binds to the geometry's OWN segment ids, in ring order "
      f"({wall_segs}), and every body corner is declared on one — a positional "
      f"implementation would have written [0, 1, 2, 3]",
      wall_segs == [5, 11, 2, 40] and corner_segs == [5, 11, 2, 40])
check(f"9b. ...and so does the far field, whose ids differ from the body's "
      f"({far_segs}), so the two cannot be one coincidence", far_segs == [3, 1, 8, 0])
check("9c. ...and the STORED binding is what is used, not the geometry's current "
      "list: binding only segments 2 and 40, split twice, builds a four-block ring "
      "on those two alone while the geometry still carries four",
      [e["binding"]["seg"] for e in
       tm.build_document(model(_b, _f, ogrid_splits=2, ogrid_body_segs="2, 40",
                               ogrid_far_segs="8,0"), _ctx)["edges"]
       if e["id"].startswith("w")] == [2, 2, 40, 40])

# ── 10. re-sampling to a different point count changes nothing ─────────────
b1 = write_outline(os.path.join(_T, "r_b"), 0.5, [2, 4, 6, 8], 12, "wall",
                   square=True)
f1 = write_outline(os.path.join(_T, "r_f"), 4.0, [1, 3, 5, 7], 12, "farfield",
                   square=True)
m_rs = model(b1, f1, ogrid_splits=2, ogrid_body_segs="2,4,6,8",
             ogrid_far_segs="1,3,5,7")
doc_a = tm.document_for(m_rs, tb.context_for_config(Cfg([b1, f1])))
pts_a = len(tb.geometry_binding(b1).spans[2].points)
# The SAME files, re-sampled to 5x the points with the segment structure unchanged.
write_outline(os.path.join(_T, "r_b"), 0.5, [2, 4, 6, 8], 60, "wall", square=True)
write_outline(os.path.join(_T, "r_f"), 4.0, [1, 3, 5, 7], 60, "farfield", square=True)
doc_b = tm.document_for(m_rs, tb.context_for_config(Cfg([b1, f1])))
pts_b = len(tb.geometry_binding(b1).spans[2].points)
check(f"10. re-sampling both geometries to 5x the point count, with the segment "
      f"structure unchanged, leaves the projected document BYTE FOR BYTE the same "
      f"— changing point density is not a topology edit ({len(doc_a)} chars). The "
      f"0.2 cell against a 0.5 wall edge is deliberately an exact 2.5 tie, which is "
      f"where an arc length summed over a polyline moves its last bits",
      doc_a == doc_b and len(doc_a) > 100)
check(f"10b. ...and that is a measurement rather than a tautology: the context was "
      f"re-read and really did change ({pts_a} -> {pts_b} points on segment 2), so "
      f"a stale cache could not have produced the agreement", pts_b > pts_a)

# ── 11. a removed segment REFUSES, and names the edge ──────────────────────
b2 = write_outline(os.path.join(_T, "del_b"), 0.5, [2, 4, 6, 8], 12, "wall",
                   square=True)
f2 = write_outline(os.path.join(_T, "del_f"), 4.0, [1, 3, 5, 7], 12, "farfield",
                   square=True)
m_del = model(b2, f2, ogrid_splits=1, ogrid_body_segs="2,4,6,8",
              ogrid_far_segs="1,3,5,7")
out_path = os.path.join(_T, "refuse", "case.dat")
before = tm.project(m_del, out_path, tb.context_for_config(Cfg([b2, f2])))
check("11. NEGATIVE CONTROL: the same topology projects cleanly BEFORE the segment "
      f"is removed ({os.path.basename(before)} written)", os.path.exists(before))
os.remove(before)
# Segment 6 deleted in the CAD stage; the other three keep their ids, which is what
# an id-based binding is for — and what a positional one would silently survive by
# re-pointing the rest of the ring at its neighbours.
write_outline(os.path.join(_T, "del_b"), 0.5, [2, 4, 8], 12, "wall", square=True)
_err = None
_edge = None
try:
    tm.project(m_del, out_path, tb.context_for_config(Cfg([b2, f2])))
except ValueError as exc:
    _err = str(exc)
    _edge = getattr(exc, "edge", None)
check(f"11b. deleting a bound segment REFUSES the projection rather than meshing a "
      f"shorter ring: {(_err or 'it projected anyway')[:90]!r}", bool(_err))
check(f"11c. ...and the refusal NAMES THE EDGE ('{_edge}'), the segment and the "
      f"geometry, and says that a binding is a stable id",
      bool(_err) and _edge == "w2" and "'w2'" in _err and "segment 6" in _err
      and os.path.basename(b2) in _err and "stable id" in _err)
check("11d. ...and the refusal is REACHABLE as a typed BindingError carrying that "
      "edge, so the repair panel (#138) flags an edge rather than parsing prose",
      isinstance(_edge, str) and _edge != "")
check("11e. ...and NOTHING was written, so a run cannot pick up the previous "
      "document and mesh a topology the configuration no longer describes",
      not os.path.exists(before))
check("11f. ...and the default boundary condition is not what happened: the word "
      "'default' appears only as the thing the refusal exists instead of",
      bool(_err) and "fall back to the default" in _err)
_plan_del = og.plan(m_del, tb.context_for_config(Cfg([b2, f2])))
check("11g. ...and the panel read-out carries that same sentence while the user "
      "types, rather than the user meeting it only after pressing Generate",
      _plan_del.problem and _plan_del.problem in _err
      and _plan_del.broken_edge == "w2")

# ── 12. the first-cell height keeps ONE home ────────────────────────────────
_ds = [e for why, d in _DOCS for e in d["edges"] if "spacing" in e]
check(f"12. every radial edge marks its BODY end a wall end and declares NO "
      f"ds_start, so the height is the run's BL_INITIAL_THICKNESS under the name it "
      f"already has rather than an alias ({len(_ds)} spacings across the spread)",
      bool(_ds) and all(e["spacing"] == {"wall_ends": "start"} for e in _ds)
      and all(e["id"].startswith("r") for e in _ds))
_walls = [e for why, d in _DOCS for e in d["edges"] if e["kind"] == "wall"]
check(f"12b. ...and EVERY boundary edge is bound, so no patch anywhere in the spread "
      f"falls back to the configured default condition ({len(_walls)} of them)",
      bool(_walls) and all("binding" in e for e in _walls))

# ── 13. the winding is measured in real coordinates ────────────────────────
def ring_area(doc, ctx, block):
    """Twice the signed area of ``block``'s corner ring, from PLACED corners.

    Positive is counter-clockwise, which is what the mesher's block-orientation rule
    requires. Placed rather than declared: a block whose edges close a ring in the
    declaration can still wind the wrong way round on the page, and that is exactly
    what a clockwise body does to the unmirrored tuple (injection C).
    """
    by_e = {e["id"]: e for e in doc["edges"]}
    by_c = {c["id"]: c for c in doc["corners"]}
    place = tb.locator(ctx)
    s, e, n, w = (by_e[i]["corners"] for i in block["edges"])
    pts = [place(by_c[cid]) for cid in (s[0], s[1], e[1], n[0])]
    if any(p is None for p in pts):
        return 0.0
    return sum(pts[k][0] * pts[(k + 1) % 4][1] - pts[(k + 1) % 4][0] * pts[k][1]
               for k in range(4))


bad = []
for why, fixname, kw in SPREAD:
    b, f, c = context(fixname)
    d = tm.build_document(model(b, f, **kw), c)
    for blk in d["blocks"]:
        if ring_area(d, c, blk) <= 0.0:
            bad.append(f"{why}/{blk['id']}")
check("13. every block's corner ring winds COUNTER-CLOCKWISE in real coordinates, "
      "for a clockwise body as well as an anticlockwise one — measured from the "
      "corners the binding places, not read off the declaration order: "
      + (", ".join(bad) if bad else "all counter-clockwise"), not bad)
check("13b. ...and the locator that placed them is the same one the canvas overlay "
      "draws bound corners with, so the two cannot disagree about where a corner is",
      tb.locator is not None
      and tb.locator(_ctx)({"geom": _b, "seg": 5, "t": 0.0}) is not None)

# ── 14. what it refuses to build, and why ──────────────────────────────────
_b1, _f1, _ctx1 = context("1seg")
cases = [
    ("a ring below the mesher's own orientation floor", dict(ogrid_splits=2),
     "at least 3"),
    ("a far field segmented differently from the body",
     dict(ogrid_splits=1, ogrid_body_segs="7", ogrid_far_segs="9,9"), "one to one"),
    ("a body geometry this mesh does not load", dict(ogrid_splits=2),
     "not one of this mesh's geometries"),
    ("no geometry named at all", dict(ogrid_splits=2), "name the body geometry"),
]
bad = []
for why, kw, want in cases:
    mm = model(_b1, _f1, **kw)
    if want.startswith("not one"):
        mm.ogrid_body_geom = os.path.join(_T, "never_drawn.dat")
    elif want.startswith("name the"):
        mm.ogrid_body_geom = ""
    got = og.plan(mm, _ctx1).problem or ""
    if want not in got:
        bad.append(f"{why}: got {got!r}")
check("14. each refusable configuration is refused with a sentence naming the fix "
      "rather than with a bare failure — including the three-block floor, which is "
      "the mesher's own refusal moved forward to where the user can act on it: "
      + ("; ".join(bad) if bad else "all four named"), not bad)
try:
    tm.build_document(model(_b1, _f1, ogrid_splits=2), _ctx1)
    _raised = False
except ValueError:
    _raised = True
check("14b. ...and build_document RAISES on one rather than returning a document "
      "the mesher would then reject with a message about the document", _raised)

# ── 15. the closure rule is the mesher's own number ────────────────────────
_hdr = open(os.path.join(_REPO, "include", "PointTolerance.hpp"),
            encoding="utf-8").read()
_m = re.search(r"POINT_COINCIDENCE_FRACTION\s*=\s*([0-9.eE+-]+)", _hdr)
check(f"15. the seam tolerance this context welds a closed loop with is READ from "
      f"include/PointTolerance.hpp and agrees "
      f"({_m.group(1) if _m else 'unreadable'} vs {tb.POINT_COINCIDENCE_FRACTION}), "
      f"so it cannot disagree with the loader about whether a body closes",
      bool(_m) and abs(float(_m.group(1)) - tb.POINT_COINCIDENCE_FRACTION) < 1e-15)
_g = tb.geometry_binding(_SHIP_B)
check(f"15b. ...and the trailing duplicate is dropped with it, so the shipped closed "
      f"circle reports the FOUR segments the mesher sees rather than the three a "
      f"kept duplicate leaves contiguous ({list(_g.seg_ids)})",
      list(_g.seg_ids) == [0, 1, 2, 3] and _g.closed)

# ── 16. Qt-free, in a subprocess ───────────────────────────────────────────
_probe = ("import sys; sys.path.insert(0, %r);"
          "import app.services.topology_ogrid, app.services.topology_binding;"
          "print('PyQt6' in sys.modules)" % _GUI)
_p = subprocess.run([sys.executable, "-c", _probe], capture_output=True, text=True,
                    cwd=_REPO)
check("16. importing the O-grid family and the binding context leaves PyQt6 "
      f"unimported (subprocess said {_p.stdout.strip()!r}; in-process this check "
      "could only ever say 'loaded')", _p.stdout.strip() == "False")

# ── 17. the REAL mesher, on a shipped-style geometry ───────────────────────
if not os.path.exists(_BIN):
    print("SKIP  build/HybMesh2D not built; the real-binary half is not measured.")
else:
    with tempfile.TemporaryDirectory() as tmp:
        conf = os.path.join(tmp, "case.dat")
        topo = tm.project(_ship_m, conf, _ship_ctx)
        stem = os.path.join(tmp, "mesh")
        with open(conf, "w", encoding="utf-8") as fh:
            fh.write("MESH_MODE 1\n"
                     f"MESH_TOPOLOGY_FILE {topo}\n"
                     f"GEOM_FILE {_SHIP_B}\nGEOM_FILE {_SHIP_F}\n"
                     "BL_INITIAL_THICKNESS 0.001\nMB_SPLIT_QUADS 1\n"
                     "EXPORT_VTK 1\nEXPORT_STARCD 1\nBC_GEOM inlet\n"
                     f"OUTPUT_FILENAME {stem}.vtk\n")
        env = dict(os.environ)
        lib = subprocess.run(["bash", os.path.join(_REPO, "tools", "scripts",
                                                   "gmsh_lib_dir.sh")],
                             capture_output=True, text=True)
        if lib.returncode == 0 and lib.stdout.strip():
            env["DYLD_LIBRARY_PATH"] = lib.stdout.strip()
        r = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=env,
                           capture_output=True, text=True, timeout=900)
        out = (r.stdout or "") + (r.stderr or "")
        check(f"17. the O-grid's projection on a shipped geometry runs the real "
              f"mesher to exit 0 (got {r.returncode})", r.returncode == 0)
        mm = re.search(r"Inverted cells\s*:\s*(\d+) of (\d+)", out)
        check("17b. ...with zero inverted cells, over a mesh that exists "
              f"({mm.group(0) if mm else 'no Inverted cells row'})",
              bool(mm) and mm.group(1) == "0" and int(mm.group(2)) > 0)
        names = []
        if os.path.exists(stem + ".bnd"):
            with open(stem + ".bnd", encoding="utf-8") as fh:
                names = sorted({ln.split()[-1] for ln in fh if ln.split()})
        check(f"17c. ...and every wall patch carries the condition read off the "
              f"GEOMETRY'S OWN segments rather than the config default: the .bnd "
              f"names {names} while BC_GEOM said 'inlet', which appears nowhere",
              names == ["farfield", "wall"])
        wf = re.search(r"Wall first cell\s*:\s*worst ([0-9.]+)% off", out)
        check("17d. ...and the first cell the run delivers is the run's own "
              "BL_INITIAL_THICKNESS, to the percentage the mesher itself reports "
              f"({wf.group(0) if wf else 'no row'})",
              bool(wf) and float(wf.group(1)) < 1.0)

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print("All checks passed.")
