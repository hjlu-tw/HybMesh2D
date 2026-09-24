#!/usr/bin/env python3
"""The C-grid template: a wake CUT and a four-way trailing-edge corner (#148).

The H-grid proved the chain from a parameter form to a mesh; the O-grid added the
BINDING and the refusal when one breaks. This family adds no third mechanism — it is
a registry entry, a field-spec table and a function — and what it has to be measured
on is therefore not the machinery but the two STRUCTURES that made
``examples/topology/cgrid_naca0012.json`` the hardest of the five shipped documents to
have typed by hand:

  * the wake is ONE ``cut`` edge that is the WEST of BOTH wake blocks, and
  * the trailing edge is ONE declared corner where all four blocks meet.

WHAT THIS FILE FOUND ABOUT THE SHARED INVARIANT CHECKER, and did not work around.
``topology_doc_invariants.ring_closes`` used to require a block's east, north and west
to be declared in the convention's own direction; the mesher does not, and cannot,
because a shared edge is ONE edge with ONE direction named by two blocks whose frames
need not agree about it. Run against the SHIPPED, WORKING, hand-written C-grid that
check returned one complaint — and no C-grid can ever satisfy it, since the cut is the
west of both wake blocks and the two want it declared opposite ways round. The checker
now mirrors ``resolveBlockFrames`` exactly (and gained the mesher's distinct-corner
refusal with it); the H-grid's own injection A — east and west swapped — still fails it,
and so does a reversed SOUTH edge, which the mesher also refuses because south is what
fixes the frame.

THE FAR FIELD IS GENERATED, NOT DRAWN, WHICH IS THIS FAMILY'S ONE DEPARTURE from the
O-grid's "the template writes no geometry". #148's own demo is "fill in wake length,
far-field radius and target cell edge", so the six far-field corners are FREE
coordinates and their edges are the straight lines between them. Two consequences, both
MEASURED here rather than argued: check 13 shows those six corners landing exactly on
the shipped hand-written document's, and check 14c reports what the hexagon costs
against the shipped curved D — the peak non-orthogonality, at the one corner where they
differ, and nothing at the wall. The third consequence is not a measurement but a
limitation, and it is stated in the family's own docstring and in the read-out: a free
corner belongs to no geometry, so those six sides carry the run's ``BC_GEOM`` and cannot
carry an ``outlet`` of their own.

WHAT THIS FILE DOES NOT CHECK, because another gate owns it: the structural rules
themselves (``topology_doc_invariants.py``, which checks 1-7 call and which both other
family gates call too), the parameters-to-families comparison
(``test_topology_param_specs.py``), what the panel displays (``test_topology_panel.py``),
that the model persists (``test_topology_persistence.py``) and the aerofoil CAD shape
itself (``test_naca_airfoil_parity.py``, #147).

INJECTIONS: run by hand, 2026-09-24, each reverted and the tree compared against its
pre-injection state afterwards. Each line is what the mutation ACTUALLY did, READ FROM
THE EXIT CODE and not from a count of FAIL lines. Where the result differed from the
prediction written first, the correction is the record.

  A. the upper surface is always the one LEAVING the trailing edge (the cross-product
     measurement deleted) -> exit 1, checks 9 and 9b. NOT 9c: the mirrored section's
     rings still wind counter-clockwise, because the far field is laid out in world
     axes and only the surface edges' direction changed — which is the same fact this
     family rests on, seen from the other side.
  B. the wake declared ``interface`` instead of ``cut`` -> exit 1, checks 8 and 8c.
     The document is otherwise LEGAL — an interface bounds two blocks too, so checks
     2, 4, 5 and 7 all stay green and the mesher meshes it; what is lost is the
     declaration that this line is a cut, which #57's own note says is DECLARED here
     rather than inferred from the absence of a binding.
  D. the blunt-trailing-edge refusal removed -> exit 1, check 12 ALONE, and that is
     the useful part: the section is still refused, by the "exactly two surfaces"
     count one line below, so what the injection removes is the SENTENCE and not the
     safety. 12 goes red on the wording, which is what the criterion asks for ("with
     the problem named").
  E. the far field's nose placed ahead of the TRAILING edge rather than the leading
     one -> exit 1, check 13 alone. Nothing else can see it: the document is legal,
     it meshes, and only the comparison against the shipped hand-written corners
     knows where f2 belongs.
  F. ``GROWTH`` 1.2 -> 1.5 -> exit 1, check 11b alone (43 radial nodes became 23,
     against the shipped document's 41). Predicted "11b and 14"; the mesher meshes
     the coarser grid to zero inverted cells, so the real binary cannot see it.
  H. ``ring_closes`` put back to the version that pinned every side's direction ->
     exit 1, check 2 alone, on ``b_wake_up`` of every document in the spread. This is
     the negative control for the relaxation itself: without it this family's own
     output fails the shared checker exactly as the shipped hand-written document did.
  J. the two wake blocks name the cut as their SOUTH instead of their west -> exit 1,
     TWELVE checks (2, 4, 8, 9c, the whole 14 series and 16b/16c). The blast radius is
     the point: naming the same four edges in a different order is not a relabelling,
     it re-frames both blocks, and the real mesher refuses the document.

  THE FIRST RUN OF THIS HARNESS WAS WRONG TWICE, and both corrections are in the tree
  rather than in this comment. (i) Apple's python3 caches bytecode OUTSIDE the tree
  (``~/Library/Caches/com.apple.python``) and validates it by ``(mtime, size)``, so a
  restore at the SAME SIZE — ``x_le`` for ``x_te`` is exactly that — was silently
  ignored: ``git status`` was clean, the source file read correctly, and
  ``far_corners`` still answered with the mutation. Bumping the mtime was not enough;
  the harness now runs with ``PYTHONDONTWRITEBYTECODE=1``. (ii) Two injections CRASHED
  this file part-way (B at check 8c, J inside the winding walk), so they measured as
  2 and 3 checks; both sites were guarded, and J then measured as TWELVE. A crash is
  not a weak bite, it is an unmeasured one.

NAMED BLIND SPOTS:

  * Nothing here drives the GUI. That the panel captures the aerofoil's binding when
    the user names it, shows this derivation and flags a broken one is
    ``test_topology_panel.py``'s and ``test_topology_repair.py``'s. Checks 16-17d go
    one layer further out than the rest of this file — through the real
    ``MeshConfig`` and the real skeleton and detach services, which is what the canvas
    mixin and the panel's buttons are handed — but they still call no Qt.
  * The far field's SIX SIDES carry `BC_GEOM` and nothing here can prove that is the
    right trade — it is a consequence of generating rather than drawing, measured in
    check 14b as "one patch name where the shipped document has two". A user who needs
    an outlet distinct from the far field has no route through this template.
  * The GROWTH constant is this project's own red line for cell expansion rather than a
    derivation. Check 11b measures that it reproduces the shipped document's radial
    count to within two nodes, which is the closest thing to a check on it that exists;
    nothing here says 1.2 is the right number.
  * The `up_first` measurement is exercised on a MIRRORED section, which for a
    symmetric designation is the same shape wound the other way. A cambered section
    drawn clockwise is not in the spread, and the code path is the same one.
  * Check 14c's bound on peak non-orthogonality is a FACTOR against the shipped case's
    own number, so it moves if the shipped case changes. It is a bound on the cost of
    the hexagon, not a quality target.

Run:  python3 tools/PreProcessor/tests/test_topology_cgrid.py
Skips the real-binary half cleanly if ./build/HybMesh2D is not built.
"""
from __future__ import annotations

import json
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
from app.services import topology_cgrid as cg  # noqa: E402
from app.services import topology_model as tm  # noqa: E402
from topology_outline_fixture import write_airfoil  # noqa: E402

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


class Cfg:
    """The duck a binding context reads: a geometry list and one length."""

    def __init__(self, geoms, first_cell=1e-3):
        self.geom_files = list(geoms)
        self.bl_initial_thickness = first_cell


def model(geom, **kw):
    return tm.TopologyModel(family=cg.FAMILY, cgrid_body_geom=geom, **kw)


_TMP = tempfile.TemporaryDirectory()
_T = _TMP.name

#: Each fixture is a reason, not a variation.
FIX = {
    # The shipped hand-written C-grid's own section: a sharp NACA 0012 of unit chord
    # at the origin, split at the trailing and leading edges.
    "unit": write_airfoil(os.path.join(_T, "unit"), [0, 1], ["wall", "wall"]),
    # Segment ids that are NOT positions, and two DIFFERENT conditions, so a mesh
    # whose walls came off the wrong segments cannot look right.
    "odd-ids": write_airfoil(os.path.join(_T, "odd"), [7, 3],
                             ["suction", "pressure"]),
    # The same section wound CLOCKWISE: the segment leaving the trailing edge is then
    # the LOWER surface, which the family has to measure rather than assume.
    "mirror": write_airfoil(os.path.join(_T, "mir"), [4, 9], ["suction", "pressure"],
                            mirror_y=True),
    # Cambered, pitched, scaled and moved off the origin, so nothing in the far-field
    # placement can be reading a zero it was handed.
    "cambered": write_airfoil(os.path.join(_T, "cam"), [2, 5], ["wall", "wall"],
                              designation="2412", chord=2.0, x_le=3.0, y_le=-1.0,
                              alpha_deg=5.0),
    # BLUNT: three segments, because that is what the CAD stage draws one as.
    "blunt": write_airfoil(os.path.join(_T, "blunt"), [0, 1, 2],
                           ["wall", "wall", "wall"], sharp_te=False),
}

SPREAD = [
    ("the shipped section, on the model's own defaults", "unit", {}),
    ("segment ids that are not positions", "odd-ids", {}),
    ("a section wound CLOCKWISE", "mirror", {}),
    ("cambered, pitched, twice the chord and off the origin", "cambered",
     dict(cgrid_wake_length=38.0, cgrid_far_radius=20.0, cgrid_cell=0.04,
          cgrid_te_cell=0.01)),
    ("both counts overridden", "unit",
     dict(cgrid_wake_count=30, cgrid_radial_count=25)),
    ("a target cell larger than a whole surface", "unit", dict(cgrid_cell=99.0)),
]


def context(fixname, first_cell=1e-3):
    path = FIX[fixname]
    return path, tb.context_for_config(Cfg([path], first_cell))


_DOCS = []
for _why, _fx, _kw in SPREAD:
    _p, _c = context(_fx)
    _DOCS.append((_why, tm.build_document(model(_p, **_kw), _c)))

# ── 1-7. the structural rules, from the ONE checker all three family gates call ──
bad = [c for why, d in _DOCS for c in inv.unique_ids(why, d)]
check("1. every corner, edge and block id is unique, across the spread: "
      + (", ".join(bad) if bad else "none duplicated"), not bad)

bad = [c for why, d in _DOCS for c in inv.ring_closes(why, d)]
check("2. every block's four edges close a ring by the MESHER'S own rule — the south "
      "edge fixes the frame and the other three may be declared either way, which is "
      "what a cut shared as the west of two blocks forces: "
      + (", ".join(bad) if bad else "all closed"), not bad)

bad = [c for why, d in _DOCS for c in inv.legal_counts(why, d)]
check("3. every declared count is an integer >= 2: "
      + (", ".join(bad) if bad else "all legal"), not bad)

bad = [c for why, d in _DOCS for c in inv.one_seed_per_class(why, d)]
check("4. exactly one count seed per equivalence class — the five radials are ONE "
      "class and the wake and the two far-field side edges are another, so four seeds "
      "decide twelve edges: "
      + ("; ".join(bad) if bad else "one seed in every class"), not bad)
_classes = {}
for _why, _d in _DOCS[:1]:
    _seeds = [e["id"] for e in _d["edges"] if "count" in e]
check(f"4b. ...and there are exactly FOUR of them, which is what the shipped "
      f"hand-written document declares by hand ({_seeds})", len(_seeds) == 4)

bad = [c for why, d in _DOCS for c in inv.kind_usage(why, d)]
check("5. every 'wall' bounds exactly one block side and every interior line — "
      "'interface' AND 'cut' — exactly two: "
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

# ── 8. the two structures this family exists for ───────────────────────────
bad = []
for why, d in _DOCS:
    cuts = [e for e in d["edges"] if e["kind"] == "cut"]
    if len(cuts) != 1:
        bad.append(f"{why}: {len(cuts)} cut edge(s)")
        continue
    cid = cuts[0]["id"]
    wests = [b["id"] for b in d["blocks"] if b["edges"][3] == cid]
    if len(wests) != 2:
        bad.append(f"{why}: the cut is the west of {wests}")
check("8. EXACTLY ONE 'cut' edge, and it is the WEST (index 3 of [south, east, "
      "north, west]) of BOTH wake blocks — not merely an edge two blocks share, "
      "which any interface is: " + ("; ".join(bad) if bad else "one cut, two wests"),
      not bad)
bad = []
for why, d in _DOCS:
    by_e = {e["id"]: e for e in d["edges"]}
    on = {}
    for b in d["blocks"]:
        for cid in {c for eid in b["edges"] for c in by_e[eid]["corners"]}:
            on.setdefault(cid, set()).add(b["id"])
    four = [c for c, bs in on.items() if len(bs) == 4]
    if len(four) != 1:
        bad.append(f"{why}: {len(four)} corner(s) on four blocks")
        continue
    ends = [e["id"] for e in d["edges"] if four[0] in e["corners"]]
    if len(ends) != 5:
        bad.append(f"{why}: {len(ends)} edge(s) end on {four[0]}")
check("8b. ONE declared corner is shared by all FOUR blocks, and FIVE edges end on "
      "it — the cut, the two trailing-edge radials and the two surfaces — so the "
      "highest-risk point in the grid is welded by identity and needs no tolerance: "
      + ("; ".join(bad) if bad else "one four-way corner, five edges"), not bad)
# GUARDED, because a mutation that removes the cut altogether must leave the rest of
# this file RUNNING: an injection that crashes the gate at its third check is measured
# on three checks, and what the other thirty would have said is then unknown.
_cuts = [e for e in _DOCS[0][1]["edges"] if e["kind"] == "cut"]
check(f"8c. ...and the cut carries NO binding, so no face of it reaches the .bnd and "
      f"the two blocks share its nodes by identity rather than coinciding "
      f"({sorted(_cuts[0]) if _cuts else 'there is no cut edge'})",
      bool(_cuts) and "binding" not in _cuts[0])

# ── 9. the section is READ, not assumed ────────────────────────────────────
_up, _cu = context("unit")
_mi, _cm = context("mirror")
_pu, _pm = cg.plan(model(_up), _cu), cg.plan(model(_mi), _cm)
check(f"9. the trailing edge is the joint further DOWNSTREAM and the upper surface is "
      f"the one on the +y side of the chord, both measured: the anticlockwise section "
      f"leaves its trailing edge on segment {_pu.section.up_seg} (upper) and the "
      f"CLOCKWISE one on segment {_pm.section.lo_seg} (lower), so `up_first` is "
      f"{_pu.section.up_first} against {_pm.section.up_first}",
      not _pu.problem and not _pm.problem
      and _pu.section.up_first and not _pm.section.up_first
      and _pu.section.te_seg == 0 and _pm.section.te_seg == 4)
_du = tm.build_document(model(_up), _cu)
_dm = tm.build_document(model(_mi), _cm)


def _edge(doc, eid):
    return [e for e in doc["edges"] if e["id"] == eid][0]


check(f"9b. ...and the ONLY thing that changes is the direction the two surface edges "
      f"are declared in — no mirrored block tuple, because a block's west may be "
      f"declared either way (af_up runs {_edge(_du, 'af_up')['corners']} against "
      f"{_edge(_dm, 'af_up')['corners']})",
      _edge(_du, "af_up")["corners"] == ["te", "le"]
      and _edge(_dm, "af_up")["corners"] == ["le", "te"]
      and [b["edges"] for b in _du["blocks"]] == [b["edges"] for b in _dm["blocks"]])


def ring_area(doc, ctx, block):
    """Twice the signed area of ``block``'s corner ring, from PLACED corners.

    Positive is counter-clockwise, which the mesher's block-orientation rule
    requires. Placed rather than declared: a block whose edges close a ring in the
    declaration can still wind the wrong way round on the page. Walked by the
    MESHER's frame rule, since this family declares edges in either direction.
    """
    by_e = {e["id"]: e for e in doc["edges"]}
    by_c = {c["id"]: c for c in doc["corners"]}
    place = tb.locator(ctx)

    def at(cid):
        c = by_c[cid]
        return place(c) if c["kind"] == "on_geometry" else tuple(c["xy"])

    s, e, n, w = (by_e[i]["corners"] for i in block["edges"])
    a, b = s
    d = inv._other_end(w, a)
    c = inv._other_end(e, b)
    # A ring that does not close has no area rather than a KeyError: check 2 is what
    # reports that, and a crash here would stop this file before it got there.
    if c is None or d is None:
        return 0.0
    pts = [at(x) for x in (a, b, c, d)]
    if any(p is None for p in pts):
        return 0.0
    return sum(pts[k][0] * pts[(k + 1) % 4][1] - pts[(k + 1) % 4][0] * pts[k][1]
               for k in range(4))


bad = []
for why, fixname, kw in SPREAD:
    path, ctx = context(fixname)
    d = tm.build_document(model(path, **kw), ctx)
    for blk in d["blocks"]:
        if ring_area(d, ctx, blk) <= 0.0:
            bad.append(f"{why}/{blk['id']}")
check("9c. every block's corner ring winds COUNTER-CLOCKWISE in real coordinates, on "
      "a clockwise section as well as an anticlockwise one — measured from where the "
      "binding and the generated corners put them, not read off the declaration: "
      + (", ".join(bad) if bad else "all counter-clockwise"), not bad)

# ── 10. a binding is a stable ID, and a broken one refuses ─────────────────
_od, _co = context("odd-ids")
_do = tm.build_document(model(_od), _co)
_binds = {e["id"]: e["binding"]["seg"] for e in _do["edges"] if "binding" in e}
_corner_segs = {c["id"]: c["seg"] for c in _do["corners"] if c["kind"] == "on_geometry"}
check(f"10. the two surface edges bind to the geometry's OWN segment ids and the two "
      f"section corners are declared on them ({_binds}, corners {_corner_segs}) — a "
      f"positional implementation would say 0 and 1 here",
      _binds == {"af_up": 7, "af_lo": 3} and _corner_segs == {"te": 7, "le": 3})
check(f"10b. ...and EVERY edge that is not the section's is a free-cornered far-field "
      f"side with no binding, which is what generating the far field means: "
      f"{sorted(e['id'] for e in _do['edges'] if 'binding' not in e)}",
      {e["id"] for e in _do["edges"] if "binding" in e} == {"af_up", "af_lo"}
      and sum(1 for c in _do["corners"] if c["kind"] == "free") == 6)
_broken = model(_od, cgrid_body_segs="7,99")
_pb = cg.plan(_broken, _co)
_rows = tm.broken_bindings(_broken, _co)
check(f"10c. a stored id the section no longer carries REFUSES and names the edge, "
      f"rather than falling back to the configured default condition: "
      f"{_pb.problem[:90]!r}",
      "no longer has" in _pb.problem and _pb.broken_edge == "af_lo")
check(f"10d. ...and the family reports it as a repairable row naming BOTH surface "
      f"edges, because with one span missing it cannot say which is the upper "
      f"({[(r.field, r.pos, r.seg, r.edges, r.choices) for r in _rows]})",
      len(_rows) == 1 and _rows[0].pos == 1 and _rows[0].seg == 99
      and _rows[0].edges == ("af_up", "af_lo")
      and _rows[0].choices == (7, 3) and _rows[0].field == "cgrid_body_segs")
try:
    tm.build_document(_broken, _co)
    _raised = False
except ValueError:
    _raised = True
check("10e. ...and build_document RAISES rather than returning a document the mesher "
      "would then reject with a message about the document", _raised)

# ── 11. the counts are DERIVED, DISPLAYED and OVERRIDABLE ─────────────────
_p = cg.plan(model(_up), _cu)
_d = tm.build_document(model(_up), _cu)
_seeded = {e["id"]: e["count"] for e in _d["edges"] if "count" in e}
check(f"11. the counts the DOCUMENT seeds are the ones the plan reports, so the panel "
      f"cannot display a figure the mesh does not use ({_seeded} against surfaces "
      f"{_p.up_nodes}/{_p.lo_nodes}, wake {_p.wake_nodes}, radial {_p.radial_nodes})",
      _seeded == {"wake": _p.wake_nodes, "r_te_up": _p.radial_nodes,
                  "af_up": _p.up_nodes, "af_lo": _p.lo_nodes})
_ship_doc = json.loads(re.sub(r"//.*", "", open(
    os.path.join(_REPO, "examples", "topology", "cgrid_naca0012.json"),
    encoding="utf-8").read()))
_ship_rad = [e["count"] for e in _ship_doc["edges"] if e["id"] == "r_te_up"][0]
check(f"11b. the radial derivation — a law starting at the run's "
      f"BL_INITIAL_THICKNESS and never growing faster than {cg.GROWTH}, which is this "
      f"project's own red line for cell expansion — lands within two nodes of the "
      f"count the shipped hand-written document declares by hand "
      f"({_p.radial_derived} against {_ship_rad})",
      abs(_p.radial_derived - _ship_rad) <= 2)
_ov = cg.plan(model(_up, cgrid_wake_count=30, cgrid_radial_count=25), _cu)
check(f"11c. the derivation is a DEFAULT and not a cage: overrides of 30 and 25 are "
      f"taken and reported as overrides, with the derived counts still stated "
      f"(got {_ov.wake_nodes}/{_ov.radial_nodes}, derived "
      f"{_ov.wake_derived}/{_ov.radial_derived})",
      _ov.wake_nodes == 30 and _ov.radial_nodes == 25 and _ov.wake_overridden
      and _ov.radial_overridden and _ov.wake_derived == _p.wake_derived
      and _ov.radial_derived == _p.radial_derived)
_no_run = cg.plan(model(_up), tb.context_for_config(Cfg([_up], first_cell=0.0)))
check(f"11e. a run that declares no BL_INITIAL_THICKNESS still derives a radial "
      f"count, from the trailing-edge cell — and the read-out NAMES that source "
      f"rather than printing one parameter under another's name "
      f"({_no_run.lines()[3]!r})",
      not _no_run.problem and not _no_run.first_cell_from_run
      and "BL_INITIAL_THICKNESS" not in _no_run.lines()[3].split("—")[0]
      and "trailing-edge cell" in _no_run.lines()[3]
      and _p.first_cell_from_run)
_lines = _p.lines()
check(f"11d. ...and the read-out shows the WORKING rather than only the result — the "
      f"section as it was read, the spacing and the growth each count came from, and "
      f"the far field's own limitation: {_lines!r}",
      len(_lines) == 5
      and any("chord" in ln and "trailing edge at" in ln for ln in _lines)
      and any("BL_INITIAL_THICKNESS" in ln for ln in _lines)
      and any(str(cg.GROWTH) in ln for ln in _lines)
      and any("BC_GEOM" in ln for ln in _lines))

# ── 12. a blunt trailing edge is refused, with a sharp one as the control ──
_bl, _cb = context("blunt")
_pbl = cg.plan(model(_bl), _cb)
check(f"12. a BLUNT trailing edge is refused with the problem NAMED — the section has "
      f"a base segment of its own and its two surfaces never meet, so there is no "
      f"single corner for the four blocks to share: {_pbl.problem[:140]!r}",
      bool(_pbl.problem) and "BLUNT" in _pbl.problem
      and "Sharp trailing edge" in _pbl.problem)
check("12b. ...with the SHARP section of the same designation as the negative "
      "control, which is refused for nothing", not cg.plan(model(_up), _cu).problem)
_cases = [
    ("no geometry named at all", model(""), _cu, "name the aerofoil geometry"),
    ("a geometry this mesh does not load",
     model(os.path.join(_T, "never_drawn.dat")), _cu,
     "not one of this mesh's geometries"),
    ("a far field that does not contain the section",
     model(_up, cgrid_far_radius=0.02), _cu, "outside the far field"),
    ("a wake length of zero", model(_up, cgrid_wake_length=0.0), _cu,
     "wake length must be greater than zero"),
    ("a target cell edge of zero", model(_up, cgrid_cell=0.0), _cu,
     "target cell edge must be greater than zero"),
    ("a binding token that is not a segment id",
     model(_up, cgrid_body_segs="0,x"), _cu, "is not a segment id"),
    ("a binding naming one segment twice", model(_up, cgrid_body_segs="0,0"), _cu,
     "twice"),
    ("no context at all", model(_up), None,
     "it needs the mesh's geometry list"),
]
bad = []
for why, mm, cc, want in _cases:
    got = cg.plan(mm, cc).problem or ""
    if want not in got:
        bad.append(f"{why}: got {got[:80]!r}")
check("12c. each refusable configuration is refused with a sentence naming the fix "
      "rather than with a bare failure: "
      + ("; ".join(bad) if bad else f"all {len(_cases)} named"), not bad)

# ── 13. the generated far field lands on the shipped document's own corners ─
_SHIP_AF = os.path.join(_REPO, "examples", "geometries", "naca0012_cgrid.dat")
_SHIP_FF = os.path.join(_REPO, "examples", "geometries", "cgrid_farfield.dat")
_ship_ctx = tb.context_for_config(Cfg([_SHIP_AF, _SHIP_FF]))
_place = tb.locator(_ship_ctx)
_ship_far = {c["id"]: _place(c) for c in _ship_doc["corners"]
             if c["geom"].endswith("cgrid_farfield.dat")}
_tpl = cg.plan(model(_SHIP_AF), tb.context_for_config(Cfg([_SHIP_AF])))
_off = {k: max(abs(_tpl.far[k][0] - _ship_far[k][0]),
               abs(_tpl.far[k][1] - _ship_far[k][1])) for k in _ship_far}
check(f"13. on the model's UNTOUCHED defaults the six generated far-field corners "
      f"land EXACTLY where the shipped hand-written document's own six are, so "
      f"'reproduces the target' is a comparison rather than a resemblance "
      f"(worst offset {max(_off.values()):.3e}; {_off})",
      set(_off) == {"wk", "fu", "f1", "f2", "f3", "fl"}
      and max(_off.values()) < 1e-9)
_def = tm.TopologyModel()
check(f"13b. ...and those really are the untouched defaults (wake "
      f"{_def.cgrid_wake_length}, radius {_def.cgrid_far_radius}, cell "
      f"{_def.cgrid_cell}, te cell {_def.cgrid_te_cell}, overrides "
      f"{_def.cgrid_wake_count}/{_def.cgrid_radial_count})",
      (_def.cgrid_wake_length, _def.cgrid_far_radius, _def.cgrid_cell,
       _def.cgrid_te_cell, _def.cgrid_wake_count, _def.cgrid_radial_count)
      == (19.0, 10.0, 0.02, 0.005, 0, 0))

# ── 14. the REAL mesher, and the comparison with the shipped document ──────


def run_mesher(tmp, topo_path, geoms, tag, bc="farfield"):
    conf = os.path.join(tmp, tag + ".dat")
    stem = os.path.join(tmp, tag)
    with open(conf, "w", encoding="utf-8") as fh:
        fh.write("MESH_MODE 1\n"
                 f"MESH_TOPOLOGY_FILE {topo_path}\n"
                 + "".join(f"GEOM_FILE {g}\n" for g in geoms)
                 + "BL_INITIAL_THICKNESS 0.001\nMB_SPLIT_QUADS 1\n"
                   "EXPORT_VTK 1\nEXPORT_STARCD 1\n"
                 f"BC_GEOM {bc}\nOUTPUT_FILENAME {stem}.vtk\n")
    env = dict(os.environ)
    lib = subprocess.run(["bash", os.path.join(_REPO, "tools", "scripts",
                                               "gmsh_lib_dir.sh")],
                         capture_output=True, text=True)
    if lib.returncode == 0 and lib.stdout.strip():
        env["DYLD_LIBRARY_PATH"] = lib.stdout.strip()
    r = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=env, capture_output=True,
                       text=True, timeout=900)
    out = (r.stdout or "") + (r.stderr or "")
    rows = [ln for ln in out.splitlines() if ln.startswith("HYBMESH_MB_QUALITY ")]
    q = dict(kv.split("=") for kv in rows[-1].split()[1:]) if rows else {}
    names = []
    if os.path.exists(stem + ".bnd"):
        with open(stem + ".bnd", encoding="utf-8") as fh:
            names = sorted({ln.split()[-1] for ln in fh if ln.split()})
    return r.returncode, q, names, out


if not os.path.exists(_BIN):
    print("SKIP  build/HybMesh2D not built; the real-binary half is not measured.")
else:
    with tempfile.TemporaryDirectory() as tmp:
        # THE MODEL'S OWN DEFAULTS on a shipped-style section, which is what
        # "generating from defaults" means; only the geometry is named.
        _m = tm.TopologyModel(family=cg.FAMILY, cgrid_body_geom=_SHIP_AF)
        _topo = tm.project(_m, os.path.join(tmp, "tpl.dat"),
                           tb.context_for_config(Cfg([_SHIP_AF])))
        rc, q, names, out = run_mesher(tmp, _topo, [_SHIP_AF], "tpl")
        check(f"14. the C-grid's DEFAULTS on a drawn aerofoil run the real mesher to "
              f"exit 0 (got {rc})", rc == 0)
        check(f"14a. ...with zero inverted cells, over a mesh that exists "
              f"(inverted {q.get('inverted')} of {q.get('cells')})",
              q.get("inverted") == "0" and int(q.get("cells", 0)) > 0)
        # THE EXPORTED MESH'S BLOCK, not the run's first: the mesher prints the
        # quality twice, before and after the elliptic sweeps, and the two answer
        # different questions here. Everything after the BEFORE block's own machine
        # row is the mesh that was written.
        pre, _, post = out.partition("HYBMESH_MB_QUALITY_BEFORE")
        pat = r"west 'af_(?:up|lo)'\s*:.*?\(([0-9.]+)%\)"
        wf = re.findall(pat, post or pre)
        raw = re.findall(pat, pre) if post else []
        check(f"14b. ...and the first cell at the SECTION's own wall, in the mesh that "
              f"was EXPORTED, is the run's BL_INITIAL_THICKNESS to the percentages "
              f"the mesher itself reports ({wf}) — where the algebraic grid before "
              f"the elliptic sweeps was {raw} off it, because the generated hexagon "
              f"is nearer the section at mid-chord than at the nose and the first "
              f"cell scales with the local i-line. The wall control functions are "
              f"what recover it",
              len(wf) == 2 and all(float(v) < 1.0 for v in wf)
              and len(raw) == 2 and all(float(v) > 1.0 for v in raw))
        check(f"14b2. ...while the six GENERATED far-field sides carry the config's "
              f"BC_GEOM, because a free corner belongs to no geometry — the .bnd "
              f"names {names}, one name where the shipped document has two",
              names == ["farfield", "wall"])

        # THE SHIPPED HAND-WRITTEN DOCUMENT, through the same binary, so the
        # comparison is measured rather than asserted.
        srcs = os.path.join(_REPO, "examples", "topology", "cgrid_naca0012.json")
        rc2, q2, names2, _ship_out = run_mesher(tmp, srcs, [_SHIP_AF, _SHIP_FF],
                                                "ship")
        ratio = (float(q["nonortho_max_deg"]) / float(q2["nonortho_max_deg"])
                 if q.get("nonortho_max_deg") and q2.get("nonortho_max_deg") else 0.0)
        cells = (int(q["cells"]) / int(q2["cells"])
                 if q.get("cells") and q2.get("cells") else 0.0)
        check(f"14c. the mesh the template produces is COMPARED with the shipped "
              f"hand-written C-grid's, not merely declared to reproduce it: template "
              f"{q.get('cells')} cells / {q.get('nonortho_max_deg')} deg peak "
              f"non-orthogonality against shipped {q2.get('cells')} / "
              f"{q2.get('nonortho_max_deg')}, i.e. {cells:.2f}x the cells at "
              f"{ratio:.2f}x the peak. The difference is the far field: a generated "
              f"hexagon where the drawn one curves, which costs at that one corner "
              f"and nothing at the wall",
              rc2 == 0 and q2.get("inverted") == "0" and 0.0 < ratio < 2.0
              and 0.5 < cells < 2.0)

        # THE COMPARISON WHERE IT MATTERS. Peak non-orthogonality and a cell count
        # are whole-mesh figures, and both are dominated by the far field — which is
        # the half these two documents deliberately disagree about. What "reproduces
        # the target" has to mean is the grid AROUND THE SECTION, so this compares the
        # two runs' per-block cell-shape medians for the two body blocks, which the
        # mesher reports itself. Added by #148's Spec review, which read 14c's assert
        # against its own label and found the discretisation ungated.
        def by_block(text):
            tail = text.partition("HYBMESH_MB_QUALITY_BEFORE")[2] or text
            return {m[0]: float(m[1]) for m in re.findall(
                r"block '(\w+)'\s*:\s*median ([0-9.]+)", tail)}

        _t, _s2 = by_block(out), by_block(_ship_out)
        _body = {b: (_t.get(b), _s2.get(b)) for b in ("b_upper", "b_lower")}
        _worst = max((max(a, b) / min(a, b)) for a, b in _body.values()
                     if a and b) if all(all(v) for v in _body.values()) else 0.0
        check(f"14c2. ...and AT THE SECTION the two grids are the same grid: the "
              f"mesher's own per-block cell-shape medians for the two body blocks "
              f"agree to {_worst:.3f}x ({_body}). The whole-mesh figures above are "
              f"dominated by the far field, which is the half the two documents "
              f"deliberately disagree about",
              bool(_worst) and _worst < 1.2)
        check(f"14d. ...and the shipped document's own far field is what carries the "
              f"second boundary name the template cannot ({names2} against {names})",
              names2 == ["farfield", "outlet", "wall"])

        # The section's own conditions really do come off its segments.
        rc3, q3, names3, _ = run_mesher(
            tmp, tm.project(model(FIX["odd-ids"]), os.path.join(tmp, "odd.dat"),
                            tb.context_for_config(Cfg([FIX["odd-ids"]]))),
            [FIX["odd-ids"]], "odd", bc="farfield")
        check(f"14e. a section whose two surfaces carry DIFFERENT conditions exports "
              f"them both, read off its own CAD segments rather than from the config "
              f"default ({names3}); BC_GEOM said 'farfield', which is only the "
              f"generated far field's",
              rc3 == 0 and names3 == ["farfield", "pressure", "suction"])

# ── 16. the skeleton, the cut included — and detach/re-attach ─────────────
# Through the REAL MeshConfig and the real services, because #136's own criterion is
# about what the canvas is handed rather than about a document: the mixin asks
# `skeleton_for_config(self.mesh_config)` and nothing else.
from app.models.mesh_config import MeshConfig  # noqa: E402
from app.services import topology_detach, topology_skeleton  # noqa: E402
from app.services.mesh_modes import MESH_MODE_MULTIBLOCK  # noqa: E402

_mc = MeshConfig()
_mc.mesh_mode = MESH_MODE_MULTIBLOCK
_mc.add_geom_file(FIX["unit"])
_mc.bl_initial_thickness = 1e-3
_mc.topology = model(FIX["unit"])
_skel = topology_skeleton.skeleton_for_config(_mc)
_unplaced = [c.id for c in (_skel.corners if _skel else ()) if c.xy is None]
_bound = sorted(c.id for c in (_skel.corners if _skel else ()) if c.bound)
check(f"16. the canvas is handed a skeleton for a C-grid case, with every corner "
      f"PLACED — the two on the section by its binding and the six generated ones by "
      f"their own coordinates (bound {_bound}, unplaced {_unplaced})",
      _skel is not None and len(_skel.corners) == 8 and not _unplaced
      and _bound == ["le", "te"])
_wake = [e for e in _skel.edges if e.id == "wake"][0] if _skel else None
check(f"16b. ...and the WAKE CUT is drawn: it has both endpoints, it is an INTERIOR "
      f"edge rather than a boundary (the two the overlay styles apart), and its count "
      f"is the one the plan derived (xy={_wake.xy is not None}, "
      f"is_boundary={_wake.is_boundary}, label={_wake.label!r})",
      _wake is not None and _wake.xy is not None and not _wake.is_boundary
      and _wake.label == str(_p.wake_nodes) and _wake.declared)
_prop = {e.id: e.count for e in _skel.edges if not e.declared}
check(f"16c. ...and the four seeds PROPAGATE to the other eight edges, so the overlay "
      f"shows the counts the user never typed ({_prop})",
      len(_prop) == 8 and all(v is not None for v in _prop.values())
      and _prop["r_le"] == _p.radial_nodes and _prop["e_out_up"] == _p.radial_nodes
      and _prop["e_ff_up"] == _p.wake_nodes
      and _prop["e_ff_nose_up"] == _p.up_nodes)
with tempfile.TemporaryDirectory() as _dt:
    _out = topology_detach.detach(_mc.topology, _mc, os.path.join(_dt, "hand.json"),
                                  tb.context_for_config(_mc))
    _written = json.load(open(_out, encoding="utf-8"))
    check(f"17. detaching a C-grid writes the document it was projecting and turns "
          f"the family off in one flag — the file has "
          f"{len(_written['blocks'])} blocks and {len(_written['corners'])} corners, "
          f"names_a_family={_mc.topology.names_a_family()}, "
          f"is_detached={_mc.topology.is_detached()}, "
          f"mesh_topology_file={bool(_mc.mesh_topology_file)}",
          len(_written["blocks"]) == 4 and len(_written["corners"]) == 8
          and not _mc.topology.names_a_family() and _mc.topology.is_detached()
          and bool(_mc.mesh_topology_file))
    check("17b. ...so the canvas stops drawing a model the run no longer reads, and "
          "the family reports no broken binding for it",
          topology_skeleton.skeleton_for_config(_mc) is None
          and tm.broken_bindings(_mc.topology,
                                 tb.context_for_config(_mc)) == ())
    _sum = topology_detach.summary(_mc.topology, _mc)
    check(f"17c. ...and the provenance summary names the family AND the quantity the "
          f"family reads from the RUN rather than from the model, which no prefix "
          f"could find: {_sum[:120]!r}",
          "C-grid" in _sum and "BL_INITIAL_THICKNESS" in _sum
          and "Wake Length" in _sum)
    topology_detach.reattach(_mc.topology, _mc)
    check(f"17d. ...and re-attaching puts it back: the family drives the run again "
          f"and the path row is CLEARED, so it cannot decide something while the "
          f"funnel overrides it (file={_mc.mesh_topology_file!r})",
          _mc.topology.names_a_family() and not _mc.mesh_topology_file
          and topology_skeleton.skeleton_for_config(_mc) is not None)

# ── 15. Qt-free, in a subprocess ───────────────────────────────────────────
_probe = ("import sys; sys.path.insert(0, %r);"
          "import app.services.topology_cgrid, app.services.topology_cgrid_section;"
          "print('PyQt6' in sys.modules)" % _GUI)
_p2 = subprocess.run([sys.executable, "-c", _probe], capture_output=True, text=True,
                     cwd=_REPO)
check("15. importing the C-grid family and its section reader leaves PyQt6 "
      f"unimported (subprocess said {_p2.stdout.strip()!r}; in-process this check "
      "could only ever say 'loaded')", _p2.stdout.strip() == "False")

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print("All checks passed.")
