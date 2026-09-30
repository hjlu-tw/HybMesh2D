#!/usr/bin/env python3
"""The two-ring O-grid template: the family IS the two shipped documents (#155).

The capability shipped twice as a hand-written document — #153's circle with a drawn
concentric seam, #154's ellipse with a computed offset — and zero times as something a
user can produce. What both documents warn about in their own comments is ONE NUMBER:
the outer ring's ``ds_start`` is the inner ring's last interval, read off a run, and
"change the inner ring's count, its span or BL_INITIAL_THICKNESS and this number is
wrong and the seam shows". A stale number nothing errors on is the same failure class
as every binding-by-index defect this repo has tickets about, and a family that DERIVES
it is the fix.

SO THE CENTRAL CLAIM HERE IS A REPRODUCTION, NOT A DESCRIPTION. Checks 20 and 21
configure the family to each shipped document's own parameters, project it, run the
REAL mesher on the projection and compare the exported nodes against the shipped case's
own, node for node. A document-level text diff is deliberately NOT the check: the
family is free to order edges differently, and pinning that would be pinning the wrong
thing.

AND ``ds_start`` IS MEASURED ON A MESH, NEVER AGAINST A SECOND COPY OF THE FORMULA.
``topology_spacing`` is a second home for the mesher's own one-sided tanh law, so a
gate comparing the two implementations would only prove they were typed the same way.
Check 22 runs the family's output through the mesher UNSMOOTHED at a radial count
NEITHER shipped document uses and requires the first cell out of the seam to equal the
last cell into it, with the same document minus the key as the negative control.

WHAT THIS FILE DOES NOT CHECK, because another gate owns it: the structural rules
themselves (``topology_doc_invariants.py``, which checks 1-7 call), the
parameters-to-families comparison (``test_topology_param_specs.py``), what the panel
displays for the other three families (``test_topology_panel.py``), and the shipped
documents' own meshes (``test_multiblock_tworing_surface.py`` and
``test_multiblock_tworing_offset_surface.py``, which are what checks 20 and 21 measure
against).

INJECTIONS: run by hand, 2026-09-30, each against a symlink MIRROR of the repo whose
python tree alone is a copy, so the real tree was never mutated. Each line is what the
mutation ACTUALLY did, read from the harness's EXIT CODE and not from a count of FAIL
lines. Where the result differed from the prediction written first, the CORRECTION is
what is recorded — three of them did.

  A. ``last_interval`` returns the UNIFORM interval (``span / (count - 1)``) instead of
     solving the tanh -> exit 1, checks 19, 20, 21 and 22 red. Check 10 STAYS GREEN,
     which was not the prediction and is the useful half: it reads the same function
     the family reads, so a wrong LAW agrees with itself there. Check 19 — the derived
     number against the literal a real run put in each shipped document — is what sees
     it, and is the reason this file has a check that needs no binary at all.
  B. ``ds_start`` solved from ``seam_radius - radius`` (the area-equivalent span)
     instead of from the ``ri0`` CHORD -> exit 1, checks 19, 19b, 20, 21, 21b and 22
     red. Predicted "check 21 alone, the circle being blind by construction"; the
     circle is NOT blind — its equivalent radii are 0.49994 and 0.99999, not 0.5 and
     1.0, so its own ``ds_start`` moved too (0.05814123 against 0.05813418). The two
     shapes are still both run, because the ellipse's error is 20x larger.
  C. the seam's pairing check deleted -> exit 1, check 13b ALONE. Check 13 stays green
     and should: it is the BLANK-seam refusal, which is a different sentence reached
     one step earlier.
  D. ``ds_start`` written on ``ro0`` only rather than on every outer radial -> exit 1,
     checks 9, 10, 20 and 21 red. CHECK 22 STAYS GREEN, and that is a named weakness of
     it rather than a detail: the +x ray it walks runs along ``ro0``, the one radial
     the mutation spared, so the continuity measurement cannot see three of the four
     going uniform. What catches it is the node-for-node reproduction.
  E. the outer radials given no count seed (so their class has none) -> exit 1, checks
     4, 20, 21, 22, 22b, 23 and 23b red; the mesher refuses the document outright, and
     every reader below returns empty rather than raising. CHECK 8 STAYS GREEN, which
     was not the prediction: the class PARTITION is unchanged by removing a seed, so
     the shared ``one_seed_per_class`` invariant is what sees it — the two checks ask
     different questions and only look alike.
  F. ``broken_bindings`` walking only the body and the far field -> exit 1, checks 15,
     16, 16b and 16c red: the seam's broken position is reported nowhere, the panel
     offers no dropdown for it, and the repaired configuration still refuses.

THE FIRST RUN OF D, E AND F CRASHED THIS FILE rather than failing its checks — a
``KeyError`` on a missing ``spacing``, a ``FileNotFoundError`` on a ``.vrt`` no refused
run wrote, and a ``BindingError`` out of ``build_document``. That is #154's own trap:
an injected-away step must not take the checks below it with it, or a mutation turns
two dozen owed checks into one red one. Every reader in the mesher half now answers
empty instead of raising, and the results above are the re-run.

NAMED BLIND SPOTS:

  * ONE ``ds_start`` SERVES THE WHOLE RING, taken at ring position 0. The inner radials
    of a body that is not a circle are not all the same length — 0.2500008 to 0.2500509
    on the shipped ellipse, 0.02% apart — so a PER-EDGE ``ds_start``, each outer radial
    continuing its own inner one, would be strictly more continuous at the three
    positions this one is not taken from. It is not taken, because it would stop the
    family reproducing the two documents it exists to replace, which is this ticket's
    own strongest claim. Check 21b states the spread so the trade is on the record.
  * CHECK 22 WALKS ONE RADIAL LINE, measured by injection D above. A mutation that
    spoils the seam spacing on some outer radials but not on ``ro0`` is invisible to
    it; the node-for-node reproduction is what covers the rest, and only on the two
    shipped parameter sets.
  * THE ARC-LENGTH CORRESPONDENCE IS INHERITED, NOT FIXED. ``follows`` places a node by
    arc length, and equal arc on a body corresponds to equal arc on its constant-
    distance offset only where ``1 + d*kappa`` is constant — i.e. on a circle. The
    family emits the same declarations the shipped documents do and so reproduces that
    behaviour exactly; the read-out says what ``splits`` buys against it (check 12b) and
    nothing here tries to remove it. Thompson, Warsi & Mastin Ch. VI §2F frames the
    algebraic grid as the INITIAL GUESS for an elliptic solve, which this repo already
    runs (``MbControl``), so the unsmoothed number is a property of an initial guess.
  * The reproduction is to a TOLERANCE, not to bytes. The shipped documents quote
    ``ds_start`` to 8 decimals where the family computes it in full, and this mesher is
    not byte-reproducible anyway (``docs/design_notes/mesher.md``, "THE GOLDEN
    COMPARATOR"). Checks 20 and 21 report the worst deviation they measured — 5.0e-08
    and 8.0e-08 — rather than asserting an equality that would be a fiction.
  * Only the DEFAULTS and the two shipped parameter sets reach the real binary. The
    nine-entry spread is checked structurally, which is the O-grid gate's own limit and
    for its reason: nine mesher runs in a gate is a cost nobody asked for.
  * Nothing here drives the family from the GUI's own panel except the repair rows
    (checks 16-16c). That the read-out updates as the user types is
    ``test_topology_panel.py``'s shape for the other three families, not re-run here.
  * The fixtures are written by this file rather than by the real ``surface_resampler``,
    so a change to the sidecar FORMAT would not be caught here. It is caught next door,
    by ``test_multiblock_binding_surface.py``.

Run:  python3 tools/PreProcessor/tests/test_topology_tworing.py
Skips the real-binary half cleanly if ./build/HybMesh2D is not built.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
_GEOM = os.path.join(_REPO, "examples", "geometries")
sys.path.insert(0, _GUI)
sys.path.insert(0, _HERE)

import topology_doc_invariants as inv                            # noqa: E402
from app.services import topology_binding as tb                  # noqa: E402
from app.services import topology_model as tm                    # noqa: E402
from app.services import topology_spacing as ts                  # noqa: E402
from app.services import topology_tworing as tw                  # noqa: E402
from topology_outline_fixture import (                           # noqa: E402
    meta_stamp, split_segment_in_meta, write_outline,
)

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


class Cfg:
    """The duck a binding context reads: a geometry list and one length.

    Deliberately NOT a ``MeshConfig``, for the reason ``test_topology_ogrid.py``
    gives: ``context_for_config`` is documented as duck-typed.
    """

    def __init__(self, geoms, first_cell=1e-3):
        self.geom_files = list(geoms)
        self.bl_initial_thickness = first_cell


def model(body, seam, far, **kw):
    kw.setdefault("tworing_cell", 0.2)
    return tm.TopologyModel(family=tw.FAMILY, tworing_body_geom=body,
                            tworing_seam_geom=seam, tworing_far_geom=far, **kw)


# ── fixtures: three closed outlines whose segment ids are ours to choose ────
_TMP = tempfile.TemporaryDirectory()
_T = _TMP.name


def _triple(tag, ids_b, ids_m, ids_f, per, **kw):
    return (write_outline(os.path.join(_T, tag + "b"), 0.5, ids_b, per, "wall", **kw),
            write_outline(os.path.join(_T, tag + "m"), 1.0, ids_m, per, "seam", **kw),
            write_outline(os.path.join(_T, tag + "f"), 4.0, ids_f, per, "farfield",
                          **kw))


FIX = {
    # Four segments each: the shape of both shipped hand-written documents.
    "4seg": _triple("s4", [0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3], 10),
    # Segment ids that are NOT positions, and that differ between the three
    # geometries, so an implementation using indices cannot agree with one using ids
    # by accident — and the SEAM's differ too, which the O-grid's fixtures cannot say.
    "odd-ids": _triple("so", [5, 11, 2, 40], [7, 3, 9, 1], [3, 1, 8, 0], 10),
    # ONE segment each: only meshes because Splits Per Segment cuts the rings.
    "1seg": _triple("s1", [7], [9], [11], 24),
    # All three wound CLOCKWISE: the block tuples have to mirror, or every ring closes
    # the wrong way round in real coordinates.
    "cw": _triple("sc", [0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3], 10, cw=True),
    # Straight-sided, so a segment's arc length is exact under resampling.
    "square": _triple("ss", [2, 4, 6, 8], [1, 3, 5, 7], [0, 2, 4, 6], 12, square=True),
}

SPREAD = [
    ("4 segments each, one block per segment — both shipped documents' shape",
     "4seg", dict(tworing_splits=1)),
    ("4 segments split 3 ways — 12 blocks per ring, 24 in all", "4seg",
     dict(tworing_splits=3)),
    ("a single-segment body split 4 ways", "1seg", dict(tworing_splits=4)),
    ("a single-segment body split 3 ways — the smallest ring the mesher accepts",
     "1seg", dict(tworing_splits=3)),
    ("segment ids that are not positions, and differ between all three outlines",
     "odd-ids", dict(tworing_splits=2)),
    ("three clockwise outlines", "cw", dict(tworing_splits=1)),
    ("three clockwise outlines, split 3 ways", "cw", dict(tworing_splits=3)),
    ("straight-sided outlines with BOTH radial counts overridden", "square",
     dict(tworing_splits=1, tworing_radial_inner=9, tworing_radial_outer=7)),
    ("a target cell larger than a whole wall edge", "square",
     dict(tworing_splits=1, tworing_cell=99.0)),
]


def context(fixname, first_cell=1e-3):
    b, m, f = FIX[fixname]
    return b, m, f, tb.context_for_config(Cfg([b, m, f], first_cell))


def docs():
    out = []
    for why, fixname, kw in SPREAD:
        b, m, f, ctx = context(fixname)
        out.append((why, tm.build_document(model(b, m, f, **kw), ctx)))
    return out


_DOCS = docs()

# ── 1-7. the shared structural invariants, over the whole spread ───────────
for fn, label in ((inv.unique_ids, "1. ids are unique within corners/edges/blocks"),
                  (inv.ring_closes, "2. every block's four edges close a ring"),
                  (inv.legal_counts, "3. every declared count is an int >= 2"),
                  (inv.one_seed_per_class, "4. exactly one count seed per class"),
                  (inv.kind_usage, "5. a wall bounds one block side, an interior two"),
                  (inv.nothing_orphaned, "6. no orphan corner and no orphan edge"),
                  (inv.no_unknown_keys, "7. every emitted key is in the mesher's "
                                        "schema")):
    bad = [c for why, doc in _DOCS for c in fn(why, doc)]
    check(f"{label}, over {len(_DOCS)} parameter sets: "
          + ("; ".join(bad) if bad else "all hold"), not bad)
check("7b. ...and the schema really was read out of src/MultiBlock.cpp, so check 7 "
      "is a comparison rather than a vacuous pass", inv.schema_readable())

# ── 8. TWO radial classes, and no block holds one of each ──────────────────
# The whole point of splitting the ring: the law that holds the wall's first cell
# answers to the wall and the one that reaches the far field answers to the far field.
_bad = []
for why, doc in _DOCS:
    classes = inv.count_classes(doc)
    ri = {e["id"] for e in doc["edges"] if e["id"].startswith("ri")}
    ro = {e["id"] for e in doc["edges"] if e["id"].startswith("ro")}
    if not any(set(c) == ri for c in classes):
        _bad.append(f"{why}: the inner radials are not one whole class")
    if not any(set(c) == ro for c in classes):
        _bad.append(f"{why}: the outer radials are not one whole class")
    for b in doc["blocks"]:
        if (set(b["edges"]) & ri) and (set(b["edges"]) & ro):
            _bad.append(f"{why}/{b['id']}: holds an inner AND an outer radial")
check("8. the inner radials are ONE equivalence class, the outer radials are "
      "ANOTHER, and no block has one of each as its two i-sides — which is the whole "
      "point of splitting the ring: " + ("; ".join(_bad) if _bad else "all hold"),
      not _bad)

# ── 9. what each radial class DECLARES ─────────────────────────────────────
_bad = []
for why, doc in _DOCS:
    for e in doc["edges"]:
        sp = e.get("spacing", {})
        if e["id"].startswith("ri") and sp != {"wall_ends": "start"}:
            _bad.append(f"{why}/{e['id']}: {sp}")
        if e["id"].startswith("ro") and list(sp) != ["ds_start"]:
            _bad.append(f"{why}/{e['id']}: {sp}")
check("9. every INNER radial declares its body end a wall end (so the mesher's tanh "
      "law solves for BL_INITIAL_THICKNESS there) and every OUTER radial declares a "
      "`ds_start` — every one of them, because spacing does not propagate along a "
      "count class, only counts do: " + ("; ".join(_bad) if _bad else "all hold"),
      not _bad)

# ── 10. ds_start IS the inner ring's own last interval ─────────────────────
_bad = []
for why, fixname, kw in SPREAD:
    b, m, f, ctx = context(fixname)
    mdl = model(b, m, f, **kw)
    p = tw.plan(mdl, ctx)
    doc = tm.build_document(mdl, ctx)
    want = ts.last_interval(p.inner_chord, p.inner, p.first_cell)
    got = {(e.get("spacing") or {}).get("ds_start") for e in doc["edges"]
           if e["id"].startswith("ro")}
    if got != {want} or want <= 0.0:
        _bad.append(f"{why}: declared {got}, derived {want}")
check("10. the declared `ds_start` IS the last interval of the inner ring's own "
      "first radial, at that radial's chord, its count and the run's first cell — "
      "one number, on every outer radial. It asks WHICH ARGUMENTS the law is given "
      "and where the answer is written, NOT whether the law is right: it reads the "
      "same function the family does, so a wrong law agrees with itself here and is "
      "check 19's to catch (measured, injection A): "
      + ("; ".join(_bad) if _bad else "all hold"), not _bad)

# ── 10b. ...and it MOVES with each of the three things it is derived from ──
_b, _m, _f, _ctx = context("4seg")
_base = tw.plan(model(_b, _m, _f, tworing_splits=1), _ctx).ds_start
_moved = {
    "the inner radial count": tw.plan(
        model(_b, _m, _f, tworing_splits=1, tworing_radial_inner=31), _ctx).ds_start,
    "BL_INITIAL_THICKNESS": tw.plan(
        model(_b, _m, _f, tworing_splits=1),
        context("4seg", first_cell=5e-3)[3]).ds_start,
    "the seam's position": tw.plan(
        model(_b, write_outline(os.path.join(_T, "m2"), 2.0, [0, 1, 2, 3], 10, "seam"),
              _f, tworing_splits=1),
        tb.context_for_config(Cfg([_b, os.path.join(_T, "m2.dat"), _f]))).ds_start,
}
check(f"10b. ...and it MOVES when any of the three moves, which is the whole of this "
      f"ticket: base {_base:.8f}, then "
      + ", ".join(f"{k} -> {v:.8f}" for k, v in _moved.items()),
      all(v > 0.0 and abs(v - _base) > 1e-9 for v in _moved.values()))

# ── 11. the seam FOLLOWS and carries no condition ─────────────────────────
_bad = []
for why, doc in _DOCS:
    seam = [e for e in doc["edges"] if e["id"].startswith("s")]
    n = len([e for e in doc["edges"] if e["id"].startswith("w")])
    if len(seam) != n:
        _bad.append(f"{why}: {len(seam)} seam edges for {n} walls")
    for e in seam:
        if e["kind"] != "interface" or "binding" in e or "follows" not in e:
            _bad.append(f"{why}/{e['id']}: {sorted(e)} kind={e['kind']}")
check("11. every seam edge is an `interface` that FOLLOWS its own segment and "
      "declares NO `binding`, because an interior line is not a boundary — so "
      "whatever the user labelled those segments reaches nothing: "
      + ("; ".join(_bad) if _bad else "all hold"), not _bad)

# ── 12. the read-out says what the derivation IS and what splits BUY ───────
_p = tw.plan(model(*FIX["4seg"], tworing_splits=1), context("4seg")[3])
_lines = _p.lines()
_text = "\n".join(_lines)
check(f"12. the derivation read-out shows RESULT AND WORKING — both counts with what "
      f"each was derived from, the seam spacing marked DERIVED, and the span each "
      f"ring crosses ({len(_lines)} lines)",
      not _p.problem and "DERIVED" in _text and "BL_INITIAL_THICKNESS" in _text
      and "ds_start" in _text and "inner:" in _text and "outer:" in _text)
check("12b. ...and it says what MORE CORNERS costs and buys, which is this family's "
      "own property and not the O-grid's — arc-length correspondence, and that the "
      "default smoothing repairs it — naming BOTH ways of adding them, because they "
      "are not equally good and check 24 measures the difference",
      "arc" in _text.lower() and "smoothing" in _text.lower()
      and "SOURCE segments" in _text and "Splits Per Segment" in _text)
check("12c. ...and it says the seam's label reaches NOTHING, rather than leaving the "
      "user to go and read the .bnd (user story 8)",
      "reaches" in _text and "no face" in _text)

# ── 13. the three refusals, each BY NAME ──────────────────────────────────
_b, _m, _f, _ctx = context("4seg")


def why_of(**kw):
    return tw.plan(model(kw.pop("body", _b), kw.pop("seam", _m), kw.pop("far", _f),
                         **kw), _ctx).problem


_no_seam = why_of(seam="")
check(f"13. a MISSING seam geometry is refused by name and the refusal names the CAD "
      f"action that makes one, because this family writes no geometry (#133, #150): "
      f"{_no_seam!r}",
      "seam" in _no_seam and tw.OFFSET_ACTION in _no_seam)
_short = write_outline(os.path.join(_T, "m3"), 1.0, [0, 1, 2], 10, "seam")
_ctx3 = tb.context_for_config(Cfg([_b, _short, _f]))
_pair = tw.plan(model(_b, _short, _f), _ctx3).problem
check(f"13b. a seam whose segments do not PAIR with the body's is refused by name — "
      f"never resolved by guessing which segment goes with which — and that refusal "
      f"names the same action: {_pair!r}",
      "seam" in _pair and "4" in _pair and "3" in _pair
      and tw.OFFSET_ACTION in _pair)
_farshort = write_outline(os.path.join(_T, "f3"), 4.0, [0, 1, 2], 10, "farfield")
_pf = tw.plan(model(_b, _m, _farshort),
              tb.context_for_config(Cfg([_b, _m, _farshort]))).problem
check(f"13c. ...and so is a FAR FIELD that does not pair, naming the far field and "
      f"not the seam: {_pf!r}", "far field" in _pf and tw.OFFSET_ACTION not in _pf)

_inside = write_outline(os.path.join(_T, "mi"), 0.25, [0, 1, 2, 3], 10, "seam")
_pi = tw.plan(model(_b, _inside, _f),
              tb.context_for_config(Cfg([_b, _inside, _f]))).problem
check(f"13d. a seam that is not strictly BETWEEN the body and the far field is "
      f"refused before either derivation, so no count is answered on a negative "
      f"span: {_pi!r}", "seam" in _pi and "between" in _pi)
_cwseam = write_outline(os.path.join(_T, "mw"), 1.0, [0, 1, 2, 3], 10, "seam", cw=True)
_pw = tw.plan(model(_b, _cwseam, _f),
              tb.context_for_config(Cfg([_b, _cwseam, _f]))).problem
check(f"13e. a seam wound AGAINST the body is refused, which the O-grid's two-way "
      f"test could not see because it had only two rings: {_pw!r}", "wound" in _pw)
check("13f. an unparseable stored list is refused as a whole string, naming the ROLE "
      "so the user knows which of the three to look at",
      "seam" in why_of(tworing_seam_segs="0,x,2"))
check("13g. no context at all is a refusal and not a crash, because the panel asks "
      "this before a configuration exists", bool(tw.plan(model(_b, _m, _f), None).problem))
check("13h. THE NEGATIVE CONTROL: the same three outlines with nothing wrong build a "
      "document and report no problem", not tw.plan(model(_b, _m, _f), _ctx).problem)

# ── 14. build() REFUSES rather than falling back, and names the edge ───────
_broken_model = model(_b, _m, _f, tworing_seam_segs="0, 1, 99, 3")
try:
    tm.build_document(_broken_model, _ctx)
    _raised = None
except tb.BindingError as exc:
    _raised = exc
check(f"14. an id the seam no longer carries REFUSES the projection and names the "
      f"EDGE as a field, never falling back to the configured default condition "
      f"({_raised and _raised.edge!r}): {str(_raised)[:110]!r}",
      _raised is not None and _raised.edge == "s2")

# ── 15. broken_bindings covers all THREE lists and says which ─────────────
_bb, _bm, _bf = _triple("brk", [0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3], 12)
_stamp = meta_stamp(_bm)
split_segment_in_meta(_bb, 2, [8, 9])
split_segment_in_meta(_bm, 2, [10, 11])
split_segment_in_meta(_bf, 2, [12, 13])
check(f"15pre. the CAD edit really moved the seam sidecar's cache key "
      f"({_stamp} -> {meta_stamp(_bm)})", meta_stamp(_bm) != _stamp)
_bctx = tb.context_for_config(Cfg([_bb, _bm, _bf]))
_bmodel = model(_bb, _bm, _bf, tworing_body_segs="0, 1, 2, 3",
                tworing_seam_segs="0, 1, 2, 3", tworing_far_segs="0, 1, 2, 3")
_broken = tm.broken_bindings(_bmodel, _bctx)
check(f"15. the family reports a broken position for EACH of the three geometries, "
      f"each row NAMING which — a user with two broken rings cannot tell two "
      f"unlabelled rows apart: {[b.label() for b in _broken]}",
      len(_broken) == 3
      and {b.who for b in _broken} == {"body", "seam", "far field"}
      and {b.edges for b in _broken} == {("w2",), ("s2",), ("o2",)})
check("15b. ...and each offers that geometry's WHOLE current segment list, which is "
      "the set of legal rotations",
      all(list(b.choices) == list(_bctx.geometry(g).seg_ids)
          for b, g in zip(sorted(_broken, key=lambda x: x.field), (_bb, _bf, _bm))))
check("15c. THE NEGATIVE CONTROL: the same context with the repaired lists reports "
      "NOTHING",
      tm.broken_bindings(model(_bb, _bm, _bf, tworing_body_segs="0, 1, 8, 9, 3",
                               tworing_seam_segs="0, 1, 10, 11, 3",
                               tworing_far_segs="0, 1, 12, 13, 3"), _bctx) == ())

# ── 16. the three repairs, through the REAL panel ─────────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication                          # noqa: E402

from app.models.mesh_config import MeshConfig                     # noqa: E402
from app.services.mesh_modes import MESH_MODE_MULTIBLOCK          # noqa: E402
from app.views.panels.mesh_config_panel import MeshConfigPanel    # noqa: E402

_app = QApplication.instance() or QApplication([])


def panel_cfg(**kw):
    c = MeshConfig()
    c.mesh_mode = MESH_MODE_MULTIBLOCK
    c.bl_initial_thickness = 1e-3
    for g in (_bb, _bm, _bf):
        c.add_geom_file(g)
    c.topology.family = tw.FAMILY
    c.topology.tworing_body_geom = _bb
    c.topology.tworing_seam_geom = _bm
    c.topology.tworing_far_geom = _bf
    c.topology.tworing_cell = 0.2
    c.topology.tworing_body_segs = "0, 1, 2, 3"
    c.topology.tworing_seam_segs = "0, 1, 2, 3"
    c.topology.tworing_far_segs = "0, 1, 2, 3"
    for k, v in kw.items():
        setattr(c.topology, k, v)
    return c


_panel = MeshConfigPanel()
_panel.set_config(panel_cfg(tworing_body_segs="0, 1, 8, 9, 3",
                            tworing_seam_segs="0, 1, 10, 11, 3",
                            tworing_far_segs="0, 1, 12, 13, 3"))
check("16pre. with every binding resolvable the repair box is HIDDEN, so its "
      "presence below means something", not _panel._topo_repair.isVisible())
_panel.set_config(panel_cfg())
_flags = [lbl.text() for lbl, _c in _panel._topo_repair._rows if not lbl.isHidden()]
check(f"16. all three broken bindings are FLAGGED in the panel, each naming its own "
      f"geometry and edge: {_flags}",
      len(_flags) == 3
      and any("w2" in t and "body" in t for t in _flags)
      and any("s2" in t and "seam" in t for t in _flags)
      and any("o2" in t and "far field" in t for t in _flags))
# Repair them through the dropdowns the panel offers, ALWAYS TAKING THE TOP ROW and
# re-reading the list afterwards. Not a loop over the rows as they stand: a repair
# arrives from inside a combo's own signal and the refresh it triggers rebuilds the
# rows, so row 1 after the first repair is a DIFFERENT broken binding from row 1
# before it — which is exactly what a user sees, and what a positional loop silently
# skipped in this gate's first draft (the seam was never repaired and 16c said so).
_WANT = {"tworing_body_segs": 8, "tworing_seam_segs": 10, "tworing_far_segs": 12}
for _ in range(len(_WANT)):
    _live = [i for i, (lbl, _c) in enumerate(_panel._topo_repair._rows)
             if not lbl.isHidden()]
    if not _live:
        break
    _i = _live[0]
    _b_row = _panel._topo_repair._broken[_i]
    _panel._topo_repair._rows[_i][1].setCurrentIndex(
        1 + list(_b_row.choices).index(_WANT[_b_row.field]))
_after = {a: getattr(_panel, a).text() for a in
          ("topo_tworing_body_segs", "topo_tworing_seam_segs",
           "topo_tworing_far_segs")}
check(f"16b. ...and repairing each from its dropdown writes the geometry's own ids "
      f"ROTATED so the chosen segment lands at the flagged position, into the row "
      f"that holds it — the ring here grows from four blocks to FIVE, because a CAD "
      f"split is what broke it: {_after}",
      _after == {"topo_tworing_body_segs": "0, 1, 8, 9, 3",
                 "topo_tworing_seam_segs": "0, 1, 10, 11, 3",
                 "topo_tworing_far_segs": "0, 1, 12, 13, 3"})
_repaired = panel_cfg(**{k.replace("topo_", ""): v for k, v in _after.items()})
try:
    _nblocks = len(tm.build_document(_repaired.topology, _bctx)["blocks"])
except tb.BindingError as exc:
    # A refusal here is the FAILURE this check is about, not a reason to stop the
    # thirteen checks below it — #154's own trap, and injection F walked into it.
    _nblocks, _why16c = -1, str(exc)[:100]
else:
    _why16c = "no refusal"
check(f"16c. ...and the repaired configuration projects a document again, with "
      f"nothing left flagged ({_nblocks} blocks, {_why16c})",
      tm.broken_bindings(_repaired.topology, _bctx) == () and _nblocks == 10)

# ── 17. the family is registered and reachable from the panel ─────────────
check(f"17. the registry carries a FOURTH family, with a label the combo shows "
      f"({[f.name for f in tm.FAMILIES]})",
      [f.name for f in tm.FAMILIES][-1] == tw.FAMILY
      and any(v == tw.FAMILY for v, _l in tm.FAMILY_CHOICES)
      and tm.family_for(tw.FAMILY).binds)

# ── 17b. it DETACHES like every other family, with no edit in #139 ────────
# The ticket's user story 10: "a starting point and not a cage". Nothing in
# `topology_detach` knows a family by name — it writes the document the registry
# builds and derives the provenance summary from the field-spec table by PREFIX — so
# what is checked here is that this family's ten parameters and the one quantity it
# reads from the RUN all reach that summary, which is the half a new family can break
# (#139's review found the O-grid's first cell missing from a summary that looked
# complete).
from app.services import topology_detach as td                    # noqa: E402
from app.services.topology_field_specs import TOPOLOGY_SPECS      # noqa: E402

_dcfg = panel_cfg(tworing_body_segs="0, 1, 8, 9, 3",
                  tworing_seam_segs="0, 1, 10, 11, 3",
                  tworing_far_segs="0, 1, 12, 13, 3")
_dpath = os.path.join(_T, "detached_topology.json")
_written = td.detach(_dcfg.topology, _dcfg, _dpath, _bctx)
_summary = td.summary(_dcfg.topology, _dcfg)
_prefixed = [sp.label for sp in TOPOLOGY_SPECS
             if (sp.model_name or "").startswith("tworing_")]
check(f"17b. detaching writes the family's document to a file the run then reads by "
      f"hand, turns the projection off, and leaves the parameters as PROVENANCE — "
      f"every one of this family's {len(_prefixed)} rows named in the summary, plus "
      f"the first cell it reads from the run",
      os.path.exists(_written) and _dcfg.topology.is_detached()
      and not _dcfg.topology.names_a_family()
      and all(lbl in _summary for lbl in _prefixed)
      and "BL_INITIAL_THICKNESS" in _summary)
check("17c. ...and the file it wrote IS the document the family builds, so detaching "
      "is a starting point and not a second builder",
      json.load(open(_written, encoding="utf-8"))
      == tm.build_document(panel_cfg(
          tworing_body_segs="0, 1, 8, 9, 3", tworing_seam_segs="0, 1, 10, 11, 3",
          tworing_far_segs="0, 1, 12, 13, 3").topology, _bctx))

# ── 18. Qt-free ───────────────────────────────────────────────────────────
_p = subprocess.run(
    [sys.executable, "-c",
     "import sys; sys.path.insert(0, %r);"
     "import app.services.topology_tworing, app.services.topology_spacing;"
     "print('PyQt6' in sys.modules)" % _GUI],
    capture_output=True, text=True, cwd=_REPO)
check(f"18. importing the two-ring family and the spacing law leaves PyQt6 "
      f"unimported (subprocess said {_p.stdout.strip()!r})",
      _p.stdout.strip() == "False")

# ── 19-22. the REAL mesher ────────────────────────────────────────────────
from mesher_bin import NO_SMOOTH, mesher_env                      # noqa: E402

#: Each shipped document, as (case, geometries, the cell that reproduces its wall
#: counts, its declared radial counts, its declared `ds_start`). The cell is stated
#: rather than solved for, so a fixture that stopped reproducing the document fails
#: here instead of being followed.
SHIPPED = {
    "circle": dict(case="multiblock_tworing",
                   geoms=("circle_body.dat", "circle_seam.dat",
                          "circle_farfield.dat"),
                   cell=0.0327, inner=25, outer=25, ds=0.05813418),
    "ellipse": dict(case="multiblock_tworing_offset",
                    geoms=("ellipse_body.dat", "ellipse_offset.dat",
                           "ellipse_farfield.dat"),
                    cell=0.0252, inner=25, outer=25, ds=0.02474095),
}


def shipped_plan(spec, **kw):
    geoms = [os.path.join(_GEOM, g) for g in spec["geoms"]]
    ctx = tb.context_for_config(Cfg(geoms))
    mdl = model(*geoms, tworing_cell=spec["cell"],
                tworing_radial_inner=kw.pop("inner", spec["inner"]),
                tworing_radial_outer=kw.pop("outer", spec["outer"]), **kw)
    return geoms, ctx, mdl, tw.plan(mdl, ctx)


# ── 19. the derived ds_start IS the literal each document had to be told ──
# Measured with no binary, because both literals were themselves read off real runs:
# this is a comparison against the MESHER's own arithmetic, not against a formula.
_bad = []
for name, spec in SHIPPED.items():
    _g, _c, _m, _p = shipped_plan(spec)
    if _p.problem or list(_p.wall_counts) != [25] * 4:
        _bad.append(f"{name}: {_p.problem or list(_p.wall_counts)}")
    elif abs(_p.ds_start - spec["ds"]) > 5e-9:
        _bad.append(f"{name}: derived {_p.ds_start:.10f} vs declared {spec['ds']}")
check("19. the family DERIVES the very number each shipped document had to be told, "
      "to the digits that document quotes — circle "
      f"{shipped_plan(SHIPPED['circle'])[3].ds_start:.8f} against 0.05813418, ellipse "
      f"{shipped_plan(SHIPPED['ellipse'])[3].ds_start:.8f} against 0.02474095 — and "
      "at the same wall counts: " + ("; ".join(_bad) if _bad else "both hold"),
      not _bad)
_e = shipped_plan(SHIPPED["ellipse"])[3]
check(f"19b. ...and on the ellipse it is taken from the ri0 CHORD "
      f"({_e.inner_chord:.7f}) and not from the area-equivalent span "
      f"({_e.seam_radius - _e.radius:.7f}), which is the 0.1% that would show as a "
      f"seam", abs(_e.inner_chord - 0.2500509) < 1e-6
      and abs(_e.inner_chord - (_e.seam_radius - _e.radius)) > 1e-4)

if not os.path.exists(_BIN):
    print("SKIP  build/HybMesh2D not built; the real-binary half is not measured.")
else:
    from mb_shipped_config import shipped_config                  # noqa: E402
    from test_multiblock_weld_surface import vrt_nodes            # noqa: E402

    def run(tmp, name, conf_text, extra=""):
        stem = os.path.join(tmp, name)
        conf = os.path.join(tmp, name + ".dat")
        with open(conf, "w", encoding="utf-8") as fh:
            fh.write(conf_text.replace("@STEM@", stem) + extra)
        p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=mesher_env(),
                           capture_output=True, text=True, timeout=900)
        return p, stem, (p.stdout or "") + (p.stderr or "")

    def nodes(stem):
        """The exported nodes, or ``[]`` when the run wrote none.

        NOT ``vrt_nodes`` directly: a mutation that makes the mesher REFUSE leaves no
        ``.vrt``, and a reader that raises there turns the one check the mutation was
        supposed to redden into a crash that takes every check below it with it —
        #154's trap, and injection E walked into it.
        """
        return vrt_nodes(stem) if os.path.exists(stem + ".vrt") else []

    def ray(stem):
        """The exported nodes on the +x axis, in order — one whole radial line.

        Every one of the three circles has a vertex at angle 0 and the two corner
        rings are declared at the t = 0 of their first segment, so this ray carries a
        node of every radial station and of both seam ends.
        """
        return sorted(x for (x, y) in nodes(stem) if abs(y) < 1e-12 and x > 0.0)

    def worst_node_gap(a, b):
        """The worst distance between two meshes' nodes, matched by COORDINATE.

        Node NUMBERING varies run to run (``tools/scripts/golden_mesh.py``), so the
        comparison is over the sorted coordinate lists — which is a real claim only
        because the counts are asserted equal first.
        """
        xa, xb = sorted(a), sorted(b)
        return max(max(abs(p[0] - q[0]), abs(p[1] - q[1]))
                   for p, q in zip(xa, xb))

    with tempfile.TemporaryDirectory() as tmp:
        for _n, (name, spec) in enumerate(SHIPPED.items()):
            geoms, ctx, mdl, plan_ = shipped_plan(spec)
            conf = os.path.join(tmp, f"{name}.conf.dat")
            topo = tm.project(mdl, conf, ctx)
            text = shipped_config(spec["case"], paths={"MESH_TOPOLOGY_FILE": topo})
            pf, stemf, outf = run(tmp, f"{name}_family", text)
            ps, stems, _outs = run(
                tmp, f"{name}_shipped",
                shipped_config(spec["case"]))
            nf, ns = nodes(stemf), nodes(stems)
            gap = worst_node_gap(nf, ns) if nf and len(nf) == len(ns) else float("inf")
            check(f"{20 + _n}. the family REPRODUCES the shipped "
                  f"{name} document's mesh: both runs exit 0, both export "
                  f"{len(nf)} / {len(ns)} nodes, and the worst coordinate difference "
                  f"between them is {gap:.3e} — the shipped file quotes `ds_start` to "
                  f"8 decimals where the family computes it in full, so this is a "
                  f"tolerance and not a byte comparison",
                  pf.returncode == 0 and ps.returncode == 0
                  and len(nf) == len(ns) and len(nf) > 0 and gap < 1e-6)

        # ── 21b. the spread ONE ds_start covers, stated rather than assumed ──
        _g, _c, _m, _p = shipped_plan(SHIPPED["ellipse"])
        _seam = _c.geometry(_g[1])
        _body = _c.geometry(_g[0])
        _chords = [((_body.spans[b].points[0][0] - _seam.spans[s].points[0][0]) ** 2
                    + (_body.spans[b].points[0][1] - _seam.spans[s].points[0][1]) ** 2)
                   ** 0.5 for b, s in zip(_p.body_segs, _p.seam_segs)]
        check(f"21b. ONE `ds_start` serves the whole ring, taken at position 0, and "
              f"the ellipse's four inner radials are {min(_chords):.7f}..."
              f"{max(_chords):.7f} — so a per-edge value would be strictly more "
              f"continuous at the other three and would stop this family reproducing "
              f"the document above. The blind spot is stated, not discovered",
              max(_chords) - min(_chords) > 1e-6
              and abs(_chords[0] - _p.inner_chord) < 1e-12)

        # ── 22. the seam is continuous AT A COUNT NEITHER DOCUMENT USES ──────
        spec = SHIPPED["circle"]
        geoms, ctx, mdl, plan_ = shipped_plan(spec, inner=17, outer=31)
        conf = os.path.join(tmp, "novel.conf.dat")
        topo = tm.project(mdl, conf, ctx)
        text = shipped_config(spec["case"], paths={"MESH_TOPOLOGY_FILE": topo})
        pn, stemn, _ = run(tmp, "novel", text, NO_SMOOTH)
        xs = ray(stemn)
        iv = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
        k = min(range(len(xs)), key=lambda i: abs(xs[i] - 1.0)) if xs else -1
        # EVERY quantity below survives a run that produced no mesh, because a
        # mutation that makes the mesher REFUSE must redden this check rather than
        # crash the four below it (#154's trap; injection E walked into it twice).
        ok = 0 < k < len(iv)
        into, out = (iv[k - 1], iv[k]) if ok else (0.0, 0.0)
        ratio = out / into if ok and into > 0.0 else float("inf")
        check(f"22. at inner 17 / outer 31 — a count NEITHER shipped document uses — "
              f"the last cell INTO the seam is {into:.9e} and the first cell OUT "
              f"of it is {out:.9e}, a ratio of {ratio:.9f} on the UNSMOOTHED mesh, "
              f"so the seam the family derived is not visible as a jump in cell size",
              pn.returncode == 0 and k == 16 and abs(ratio - 1.0) < 1e-6)
        doc2 = json.load(open(topo, encoding="utf-8"))
        for e in doc2["edges"]:
            if e["id"].startswith("ro"):
                e.pop("spacing", None)
        jump = os.path.join(tmp, "jump.json")
        with open(jump, "w", encoding="utf-8") as fh:
            json.dump(doc2, fh, indent=2)
        pj, stemj, _ = run(tmp, "jump", shipped_config(
            spec["case"], paths={"MESH_TOPOLOGY_FILE": jump}), NO_SMOOTH)
        xj = ray(stemj)
        ivj = [xj[i + 1] - xj[i] for i in range(len(xj) - 1)]
        jok = 0 < k < len(ivj)
        jinto, jout = (ivj[k - 1], ivj[k]) if jok else (0.0, 0.0)
        jump_ratio = jout / jinto if jok and jinto > 0.0 else 0.0
        check(f"22b. THE NEGATIVE CONTROL: drop that one derived key and the outer "
              f"ring goes uniform — the first cell out of the seam becomes "
              f"{jout:.6e} against {jinto:.6e} into it, a jump of "
              f"{jump_ratio:.2f}x that the same mesh otherwise hides "
              f"(measured 3.15x; the bound is 2, and it is lower than the shipped "
              f"gates' 6.45 because 31 uniform nodes over the outer ring is a "
              f"coarser jump than 25)",
              pj.returncode == 0 and jump_ratio > 2.0)

        # ── 23. the DEFAULTS mesh, and the seam's label reaches nothing ──────
        geoms = [os.path.join(_GEOM, g) for g in SHIPPED["circle"]["geoms"]]
        ctx = tb.context_for_config(Cfg(geoms))
        _def = tm.TopologyModel(family=tw.FAMILY, tworing_body_geom=geoms[0],
                                tworing_seam_geom=geoms[1], tworing_far_geom=geoms[2])
        check(f"23pre. the run below is on the UNTOUCHED defaults "
              f"(splits={_def.tworing_splits}, cell={_def.tworing_cell}, "
              f"inner={_def.tworing_radial_inner}, outer={_def.tworing_radial_outer})",
              (_def.tworing_splits, _def.tworing_cell, _def.tworing_radial_inner,
               _def.tworing_radial_outer)
              == (tm.TopologyModel().tworing_splits, tm.TopologyModel().tworing_cell,
                  tm.TopologyModel().tworing_radial_inner,
                  tm.TopologyModel().tworing_radial_outer))
        conf = os.path.join(tmp, "defaults.conf.dat")
        topo = tm.project(_def, conf, ctx)
        pd, stemd, outd = run(tmp, "defaults", shipped_config(
            SHIPPED["circle"]["case"], paths={"MESH_TOPOLOGY_FILE": topo}))
        mm = re.search(r"Inverted cells\s*:\s*(\d+) of (\d+)", outd)
        check(f"23. the two-ring family's DEFAULTS on a shipped geometry run the real "
              f"mesher to exit 0 with zero inverted cells "
              f"({mm.group(0) if mm else 'no Inverted cells row'})",
              pd.returncode == 0 and bool(mm) and mm.group(1) == "0"
              and int(mm.group(2)) > 0)
        names = []
        if os.path.exists(stemd + ".bnd"):
            with open(stemd + ".bnd", encoding="utf-8") as fh:
                names = sorted({ln.split()[-1] for ln in fh if ln.split()})
        check(f"23b. ...and the exported .bnd names the BODY's and the FAR FIELD's "
              f"conditions and NOT the seam's, whose sidecar labels those segments "
              f"'seam' — an interior line is not a boundary, and this is where a user "
              f"would otherwise have to go and check ({names})",
              names == ["farfield", "wall"])

        # ── 24. the read-out's own QUALITY claim, RE-MEASURED ────────────────
        # #155's research note measured one ladder and this family's first draft
        # quoted it for the other. The Spec review measured `splits` itself and the
        # two are different, so the panel promised 0.21% where it delivers 1.03%.
        # Both ladders are now re-measured HERE, on the shipped ellipse at a fixed 96
        # nodes around, so the sentence the panel shows cannot go stale: a cell of
        # `quarter / 24` gives n_theta = 96 at EVERY splits, which is what makes the
        # two ladders comparable at all.
        _ELL = SHIPPED["ellipse"]
        _CELL96 = 0.605521 / 24.0

        def wall_worst(geom_dir, geoms, splits, tag):
            """The worst wall first-cell error the real mesher reports, unsmoothed."""
            ctx2 = tb.context_for_config(Cfg(geoms))
            mdl2 = model(*geoms, tworing_cell=_CELL96, tworing_splits=splits,
                         tworing_radial_inner=25, tworing_radial_outer=25)
            pl = tw.plan(mdl2, ctx2)
            if pl.problem:
                return None, 0, pl.problem
            topo2 = tm.project(mdl2, os.path.join(geom_dir, tag + ".conf.dat"), ctx2)
            pr, st, out2 = run(geom_dir, tag, shipped_config(
                _ELL["case"], paths={"MESH_TOPOLOGY_FILE": topo2},
                dirs={"GEOM_FILE": geom_dir}), NO_SMOOTH)
            m2 = re.search(r"Wall first cell\s*:\s*worst ([0-9.]+)% off", out2)
            return (float(m2.group(1)) if m2 and pr.returncode == 0 else None,
                    pl.blocks, pl.n_theta)

        def resegmented(pieces):
            """The three shipped ellipse outlines, each source segment cut `pieces`
            ways AT THE SAME POINT INDICES on all three — what a user re-segmenting
            in the CAD stage does, and the reason those corners pair point for point.
            """
            d = tempfile.mkdtemp(dir=tmp)
            out2 = []
            for n in _ELL["geoms"]:
                for ext in ("", ".meta"):
                    shutil.copy(os.path.join(_GEOM, n + ext),
                                os.path.join(d, n + ext))
                out2.append(os.path.join(d, n))
            if pieces > 1:
                for g in out2:
                    for old in (4, 3, 2, 1):
                        split_segment_in_meta(
                            g, old, [old * 10 + j for j in range(pieces)])
            return d, out2

        _ship = [os.path.join(_GEOM, g) for g in _ELL["geoms"]]
        _by_splits, _by_segments = {}, {}
        for _k, _sp in ((4, 1), (8, 2), (16, 4)):
            _d = tempfile.mkdtemp(dir=tmp)
            for _n in _ELL["geoms"]:
                for _e in ("", ".meta"):
                    shutil.copy(os.path.join(_GEOM, _n + _e),
                                os.path.join(_d, _n + _e))
            _by_splits[_k] = wall_worst(
                _d, [os.path.join(_d, n) for n in _ELL["geoms"]], _sp, "sp%d" % _k)[0]
            _dd, _gg = resegmented(_sp)
            _by_segments[_k] = wall_worst(_dd, _gg, 1, "sg%d" % _k)[0]
        check(f"24. RE-SEGMENTING beats SPLITTING, which is what the read-out says and "
              f"what the first draft got backwards. Worst unsmoothed wall first cell "
              f"on the shipped ellipse at 96 nodes around, by edges per ring — more "
              f"SOURCE segments: {_by_segments}; more SPLITS: {_by_splits}. Both start "
              f"at the same 4-edge number, because at one split per segment they ARE "
              f"the same document",
              all(v is not None for v in
                  list(_by_splits.values()) + list(_by_segments.values()))
              and abs(_by_splits[4] - _by_segments[4]) < 1e-9
              and _by_segments[8] < _by_splits[8]
              and _by_segments[16] < _by_splits[16])
        check("24b. ...and the read-out quotes the numbers this check just measured, "
              "to 2 decimals, in both ladders — so the sentence the panel shows "
              "cannot go stale while the gate stays green",
              all(f"{v:.2f}%" in _text
                  for v in list(_by_segments.values()) + list(_by_splits.values())))
        def chord_spread(geoms, splits):
            """How much the ring's inner radials differ in length, as a ratio.

            The MECHANISM, measured rather than argued: a corner at a source-segment
            boundary sits at the same POINT INDEX on the body and on its offset, so
            every radial is the ring's thickness; a corner a `splits` put in the
            middle sits at equal arc FRACTION of each, which on a body of varying
            curvature is a different point — and the fill scales the first cell with
            the radial it grows along.
            """
            ctx2 = tb.context_for_config(Cfg(geoms))
            pl = tw.plan(model(*geoms, tworing_cell=_CELL96, tworing_splits=splits,
                               tworing_radial_inner=25, tworing_radial_outer=25), ctx2)
            gb, gm = ctx2.geometry(geoms[0]), ctx2.geometry(geoms[1])
            ch = []
            for (bs, bt), (ms, mt) in zip(tw._ring(pl.body_segs, splits),
                                          tw._ring(pl.seam_segs, splits)):
                a2, b2 = gb.spans[bs].point_at(bt), gm.spans[ms].point_at(mt)
                ch.append(((a2[0] - b2[0]) ** 2 + (a2[1] - b2[1]) ** 2) ** 0.5)
            return max(ch) / min(ch) - 1.0

        _sp_spread = chord_spread(_ship, 4)
        _sg_spread = chord_spread(resegmented(4)[1], 1)
        check(f"24c. ...and the MECHANISM is the corner chords, measured rather than "
              f"argued: at 16 edges per ring the inner radials differ by "
              f"{_sp_spread * 100:.3f}% when the corners come from SPLITS and "
              f"{_sg_spread * 100:.3f}% when they come from SOURCE SEGMENTS, because "
              f"a segment boundary sits at the same POINT INDEX on the body and its "
              f"offset while a split sits at equal arc FRACTION of each",
              _sg_spread < 0.001 < _sp_spread)

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
# `os._exit` because Qt's teardown under the offscreen platform crashes on a machine
# with no GPU, AFTER every check has printed PASS — the house ending for every script
# here that builds a QApplication, gated by `test_qt_teardown_exit.py`. It skips
# stdout flushing, hence the explicit flush.
print("All checks passed." if not failures else "", flush=True)
sys.stdout.flush()
os._exit(1 if failures else 0)
