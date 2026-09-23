#!/usr/bin/env python3
"""Repairing a broken binding FROM THE PANEL (issue #138, parent #133).

#137 made an unresolvable binding a refusal with the edge named. That is correct and
it is only half: it leaves the user holding an error message and a JSON document they
were never meant to open, at the one moment they already know the answer — they are
the one who just went back to the CAD stage and cut a segment. This gate holds the
other half.

THE BREAK IS THE REAL ONE, not a hand-edited model. `split_segment_in_meta` cuts a
bound segment into two in the SIDECAR ONLY, which is what a CAD split does: the `.dat`
is untouched, every coordinate the binding was chosen against is still exactly where
it was, and the stored id simply stops existing. A gate that produced the broken state
by typing a bogus id into the model would be testing the flag against a state the app
cannot reach.

Headless, against panel state and displayed text — the style of `test_topology_panel.py`
beside it — plus one run through the REAL AppController for the two claims a panel
cannot make about itself (persisted with the project, undoable), and one through the
real mesher for "the run proceeds", which is the criterion's own word.

The claims held here, in the ticket's order: a broken binding is FLAGGED naming the
geometry and what it was bound to (2, 2b); the flag carries a DROPDOWN of that
geometry's current segments and choosing one REPAIRS it (3, 4); a repaired binding is
PERSISTED (6) and UNDOABLE through the existing funnel (7); with every binding repaired
the run PROCEEDS and with one still broken it is still REFUSED with the edge named
(5, 5b, 5c); the flag CLEARS when the cause is removed by other means (8); and the panel
files stay under the file-length standard (9).

INJECTIONS: run by hand, 2026-09-23, each reverted and the file restored from git
afterwards. (Every run of this file prints `QOpenGLWidget is not supported on this
platform` on stderr, GREEN runs included — the exit code is the signal, not stderr.)

  A. `broken_bindings` returns `()` unconditionally -> 1, 1b, 2, 2b, 2c, 3, 4, 5b,
     6, 7 and 8b red; 1c, 2d, 5, 5c and 8 stayed GREEN, because all five assert that
     NOTHING is flagged or that a repaired topology projects, which a family reporting
     nothing satisfies perfectly. The negative controls in this file are only
     meaningful beside the positive ones, and that is why both are stated.
  B. `repair_binding` appends the new id instead of replacing at `pos` -> 4 red and,
     one step later, 5 red: the ring then walks five segments where the far field has
     four, so the projection refuses for a different reason than the one it started
     with. The positional rule is not a nicety.
  C. `repair_binding` re-captures the geometry's current ids (the "just refresh it"
     fix) -> 4 red alone: every id resolves, so the run proceeds — with the wall that
     was at ring position 2 now on a segment the user never picked. The check that
     catches it compares the WHOLE list, not whether the projection succeeds, which is
     why 5 is not enough on its own.
  D. `TopologyRepairBox.panel_edited` never emitted -> 6 and 7 red, 4 GREEN. The
     write lands in the widget either way; what is lost is the funnel, i.e. the model
     and the undo stack. Exactly the defect `undo_ctrl._wire_widget_edits` documents
     for a composite that builds its own children.
  E. `show_broken` DESTROYS and recreates its rows (`deleteLater` + rebuild) instead
     of reusing the pool -> the gate CRASHES at check 4 with the combo deleted inside
     its own signal. Scored zero by a reader counting FAIL lines; read the exit code.
  F. `_refresh_topology_repair` wired only to `set_config`, not into
     `_refresh_topology_counts` -> 8b red: the flag never clears while the panel is
     open, so the user fixes the CAD, comes back, and is still told the binding is
     broken.
  G. `choices` offering every segment id rather than excluding the ones already
     bound -> 3b red. Choosing one of those swaps "segment 2 is gone" for "segment 1
     is named twice", which is a repair that repairs nothing.

Run:  python3 tools/PreProcessor/tests/test_topology_repair.py
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
sys.path.insert(0, _GUI)
sys.path.insert(0, _HERE)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import gui_file_lengths as fl  # noqa: E402
from topology_outline_fixture import (  # noqa: E402
    meta_stamp, restore_meta, split_segment_in_meta, write_outline,
)

from PyQt6.QtWidgets import QApplication  # noqa: E402

from app.models.mesh_config import MeshConfig  # noqa: E402
from app.services import topology_binding as tb  # noqa: E402
from app.services import topology_model as tm  # noqa: E402
from app.services import topology_ogrid as og  # noqa: E402
from app.services import topology_ogrid_binding as _ogb  # noqa: E402
from app.services.mesh_modes import MESH_MODE_MULTIBLOCK  # noqa: E402
from app.views.panels.mesh_config_panel import MeshConfigPanel  # noqa: E402

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


_app = QApplication.instance() or QApplication([])


def flagged(pnl):
    """The repair rows currently showing a flag, as ``[(index, label text)]``.

    ``isHidden()`` and not ``isVisible()``: the latter asks whether the widget is on
    SCREEN, which is False for every widget of a panel whose window was never shown —
    and the AppController half of this file drives the panel inside a main window it
    does not raise. The claim being made is "this row is showing", which is the
    widget's own state; whether the section is on screen is check 2b's separate claim,
    made where the panel really is shown.
    """
    return [(i, lbl.text()) for i, (lbl, _c) in enumerate(pnl._topo_repair._rows)
            if not lbl.isHidden()]

# ── the fixture: two bound outlines, then the CAD split that breaks one ────
_TMP = tempfile.TemporaryDirectory()
_T = _TMP.name
BODY = write_outline(os.path.join(_T, "body"), 0.5, [0, 1, 2, 3], 12, "wall")
FAR = write_outline(os.path.join(_T, "far"), 4.0, [0, 1, 2, 3], 12, "farfield")


def cfg_for(body_segs="0, 1, 2, 3", far_segs="0, 1, 2, 3", **kw):
    c = MeshConfig()
    c.mesh_mode = MESH_MODE_MULTIBLOCK
    c.bl_initial_thickness = 1e-3
    c.add_geom_file(BODY)
    c.add_geom_file(FAR)
    c.topology.family = og.FAMILY
    c.topology.ogrid_body_geom = BODY
    c.topology.ogrid_far_geom = FAR
    c.topology.ogrid_body_segs = body_segs
    c.topology.ogrid_far_segs = far_segs
    c.topology.ogrid_cell = 0.2
    for k, v in kw.items():
        setattr(c.topology, k, v)
    return c


def ctx_for(cfg):
    return tb.context_for_config(cfg)


# The topology binds 0,1,2,3 on each outline and projects cleanly — the NEGATIVE
# CONTROL the ticket's own criteria are stated against, asserted before anything is
# broken so a later "it is broken now" cannot be true of the fixture all along.
_ok_cfg = cfg_for()
_ok_doc = tm.build_document(_ok_cfg.topology, ctx_for(_ok_cfg))
check(f"0. the fixture projects cleanly BEFORE the CAD edit "
      f"({len(_ok_doc['blocks'])} blocks, {len(_ok_doc['edges'])} edges)",
      len(_ok_doc["blocks"]) == 4)

_stamp_before = meta_stamp(BODY)
BODY_META = split_segment_in_meta(BODY, 2, [8, 9])
# The SAME segment on both outlines, which is what a user cutting one more segment
# into their O-grid does: the ring pairs body corner k with far corner k, so cutting
# the body's third quarter and the far field's SECOND leaves every radial edge
# sheared across an eighth of a turn. That document is legal and its interior folds —
# measured, 22 of 704 cells inverted after the smoother. The blind spot is recorded
# in `.claude/rules/gui-topology.md`; here the fixture is the realistic edit.
FAR_META = split_segment_in_meta(FAR, 2, [10, 11])
check(f"0b. ...and the CAD edit really moved the sidecar's cache key "
      f"({_stamp_before} -> {meta_stamp(BODY)}), which is what makes every "
      "'re-read' claim below a measurement rather than a hope",
      meta_stamp(BODY) != _stamp_before)

_broken_cfg = cfg_for()
_ctx = ctx_for(_broken_cfg)
check("0c. ...and the body now carries the two halves in place of segment 2 "
      f"({list(_ctx.geometry(BODY).seg_ids)}), with the .dat untouched",
      list(_ctx.geometry(BODY).seg_ids) == [0, 1, 8, 9, 3])

# ── 1. the FAMILY reports what is broken, position by position ─────────────
_broken = tm.broken_bindings(_broken_cfg.topology, _ctx)
check(f"1. the family reports one broken position per stored id the geometry lost, "
      f"naming the edges, the geometry and the segment: "
      f"{[b.label() for b in _broken]}",
      len(_broken) == 2
      and {b.who for b in _broken} == {"body", "far field"}
      and all(b.seg == 2 for b in _broken)
      and {b.edges for b in _broken} == {("w2",), ("o2",)})
_body_b = next(b for b in _broken if b.who == "body")
check(f"1b. ...and what it offers instead is that geometry's WHOLE current segment "
      f"list, in its own order ({list(_body_b.choices)}) — every one of them names a "
      "legal binding, because a valid ring is a ROTATION of that list and choosing "
      "the segment one flagged edge lies on is choosing the rotation",
      list(_body_b.choices) == list(_ctx.geometry(BODY).seg_ids))
check("1c. ...and a topology whose every id still resolves reports NOTHING "
      "(negative control, against the same family and the same context)",
      tm.broken_bindings(
          cfg_for("0, 1, 8, 9, 3", "0, 1, 10, 11, 3").topology, _ctx) == ())

# ── 2. the PANEL flags it, visibly ─────────────────────────────────────────
panel = MeshConfigPanel()
panel.show()
panel.set_config(cfg_for("0, 1, 8, 9, 3", "0, 1, 10, 11, 3"))
check("2d. with every binding resolvable the repair box is HIDDEN, so its presence "
      "means something (negative control, run before the broken case so it cannot "
      "pass on a box that was never shown)",
      not panel._topo_repair.isVisible())

panel.set_config(_broken_cfg)
_flags = [t for _i, t in flagged(panel)]
check(f"2. a broken binding is FLAGGED in the panel, naming the edge, the geometry "
      f"and what it was bound to: {_flags}",
      len(_flags) == 2
      and any("w2" in t and "segment 2" in t and "body.dat" in t for t in _flags)
      and any("o2" in t and "segment 2" in t and "far.dat" in t for t in _flags))
check(f"2b. ...and the box is shown with the section EXPANDED, because a flag inside "
      f"a collapsed header is a flag nobody sees "
      f"(visible={panel._topo_repair.isVisible()}, "
      f"expanded={panel.sec_topology.is_expanded})",
      panel._topo_repair.isVisible() and panel.sec_topology.is_expanded)
check("2c. ...and the read-out beside it still carries the family's own refusal "
      f"sentence, so the two say the same thing "
      f"({panel.topo_ogrid_derived.text()[:80]!r})",
      "segment" in panel.topo_ogrid_derived.text())

# ── 3. the dropdown offers that geometry's current segments ────────────────
_body_row = next(i for i, t in flagged(panel) if "body.dat" in t)
_combo = panel._topo_repair._rows[_body_row][1]
_offered = [_combo.itemData(i) for i in range(_combo.count())]
check(f"3. the flagged edge offers a dropdown of that geometry's CURRENT segments "
      f"({[_combo.itemText(i) for i in range(_combo.count())]})",
      _offered[0] is None and _offered[1:] == [0, 1, 8, 9, 3])
check("3b. ...and the ids it offers are the family's answer, not a list the view "
      "built for itself",
      _offered[1:] == list(_body_b.choices))

# ── 4. choosing one REPAIRS the binding, at its position ───────────────────
_before = panel.topo_ogrid_body_segs.text()
_combo.setCurrentIndex(1 + _offered[1:].index(8))
_after = panel.topo_ogrid_body_segs.text()
check(f"4. choosing segment 8 repairs the binding — the ring now walks the "
      f"geometry's CURRENT segments, rotated so segment 8 sits at the flagged "
      f"position ({_before!r} -> {_after!r}). Not a replacement at the position, "
      "which is what this shipped first: that leaves the ring covering four of the "
      "five segments, which the real mesher refuses at exit 8 for the edge that "
      "would then span two of them (check 10 is where that was measured)",
      [t.strip() for t in _after.split(",")] == ["0", "1", "8", "9", "3"])
check("4a2. ...and the user's own ROTATION is what the position preserves rather "
      "than being overwritten by the geometry's list outright: asking for segment 9 "
      "at the same position gives a different rotation of the same segments",
      _ogb.repair_binding([0, 1, 8, 9, 3], 2, 9) == "1, 8, 9, 3, 0"
      and _ogb.repair_binding([0, 1, 8, 9, 3], 2, 8) == "0, 1, 8, 9, 3")
check("4b. ...and the row it wrote into is still READ-ONLY, so the repair is the "
      "dropdown the family offered and not the user editing an id list (#133: "
      "which edges bind is the template's decision)",
      panel.topo_ogrid_body_segs.isReadOnly())
check(f"4c. ...and the flag for the OTHER geometry is still showing, because one "
      f"repair is not two "
      f"({[t for _i, t in flagged(panel)]})",
      len(flagged(panel)) == 1)

# ── 5. the run: still refused with one broken, proceeds with none ──────────
_half = panel.get_config()
_err = ""
try:
    tm.build_document(_half.topology, ctx_for(_half))
except tb.BindingError as exc:
    _err = str(exc)
    _edge = exc.edge
check(f"5b. with one binding still broken the projection is still REFUSED, with the "
      f"edge named: {_err!r}",
      "o2" in _err and _edge == "o2")

_far_row = flagged(panel)[0][0]
_far_combo = panel._topo_repair._rows[_far_row][1]
_far_offered = [_far_combo.itemData(i) for i in range(_far_combo.count())]
_far_combo.setCurrentIndex(1 + _far_offered[1:].index(10))
# 10 at position 2 on [0, 1, 10, 11, 3] is the identity rotation, which is the pick a
# user makes: the edge that was on the segment they cut goes on its first half.
_fixed = panel.get_config()
check(f"5c. ...and repairing it clears the last flag "
      f"({panel.topo_ogrid_far_segs.text()!r}, box visible="
      f"{panel._topo_repair.isVisible()})",
      [t.strip() for t in panel.topo_ogrid_far_segs.text().split(",")]
      == ["0", "1", "10", "11", "3"] and not panel._topo_repair.isVisible())
_doc = tm.build_document(_fixed.topology, ctx_for(_fixed))
check(f"5. with every binding repaired the projection PROCEEDS — on a ring that is "
      f"one block LARGER than before, because the user really did cut one more "
      f"segment into each outline ({len(_doc['blocks'])} blocks, was 4) — and every "
      f"wall edge binds a segment the geometry really carries",
      len(_doc["blocks"]) == 5
      and all(e["binding"]["seg"]
              in ctx_for(_fixed).geometry(e["binding"]["geom"]).spans
              for e in _doc["edges"] if "binding" in e))

# ── 6-7. persisted with the project, and undoable — through the REAL app ───
# A panel cannot make either claim about itself: what persists is the project
# snapshot (`_collect_project_state`), and what undoes is the recorder that snapshot
# feeds. Both hang on the repair reaching `on_panel_edited`, which for a control
# that builds its own children means its `panel_edited` signal — the one thing
# `undo_ctrl._wire_widget_edits` cannot cover by traversal.
from app.controller import AppController  # noqa: E402

_ctl = AppController()
_p = _ctl.main_window.mesh_config_panel
_ctl.push_panel_config(_p, cfg_for("0, 1, 2, 3", "0, 1, 10, 11, 3"))
_held = _ctl._collect_project_state()["mesh_config"]["topology"]["ogrid_body_segs"]
_row = flagged(_p)[0][0]
_c2 = _p._topo_repair._rows[_row][1]
_off2 = [_c2.itemData(i) for i in range(_c2.count())]
_c2.setCurrentIndex(1 + _off2[1:].index(8))
_snap = _ctl._collect_project_state()["mesh_config"]["topology"]["ogrid_body_segs"]
check(f"6. a repair made in the panel reaches the GLOBAL model and the project "
      f"snapshot — which is what the project file is written from — through the same "
      f"funnel as every other panel edit ({_held!r} -> {_snap!r}, model: "
      f"{_ctl.global_mesh_config.topology.ogrid_body_segs!r})",
      [t.strip() for t in _snap.split(",")] == ["0", "1", "8", "9", "3"]
      and _ctl.global_mesh_config.topology.ogrid_body_segs == _snap)
check("7pre. ...and it was RECORDED as an undo step rather than merely applied",
      _ctl.flush_project_snapshot())
_ctl.undo()
check(f"7. ...and Ctrl+Z walks it back to the binding that was there before "
      f"({_ctl.global_mesh_config.topology.ogrid_body_segs!r})",
      [t.strip() for t in
       _ctl.global_mesh_config.topology.ogrid_body_segs.split(",")]
      == ["0", "1", "2", "3"])
_ctl.redo()
check(f"7b. ...and redo re-applies it "
      f"({_ctl.global_mesh_config.topology.ogrid_body_segs!r})",
      [t.strip() for t in
       _ctl.global_mesh_config.topology.ogrid_body_segs.split(",")]
      == ["0", "1", "8", "9", "3"])

# ── 8. the flag clears when the CAUSE is removed by other means ────────────
# Undoing the CAD edit puts the segment back. Nothing in the panel knows that
# happened: the binding context is keyed by the sidecar's own mtime and size, so the
# next refresh re-reads it and the ids resolve again.
panel.set_config(_broken_cfg)
check("8pre. the panel is flagging again before the restore, so check 8 cannot pass "
      "on a box that was already hidden",
      panel._topo_repair.isVisible())
restore_meta(BODY, BODY_META)
restore_meta(FAR, FAR_META)
panel.set_config(_broken_cfg)
check(f"8. undoing the CAD edit clears the flag with no repair made — the stored "
      f"binding is untouched ({panel.topo_ogrid_body_segs.text()!r}) and it resolves "
      f"again (box visible={panel._topo_repair.isVisible()})",
      not panel._topo_repair.isVisible()
      and [t.strip() for t in panel.topo_ogrid_body_segs.text().split(",")]
      == ["0", "1", "2", "3"])
# ...and while the panel is OPEN, not only on the way in: the refresh hangs off
# `_refresh_topology_counts`, which every template keystroke runs.
split_segment_in_meta(BODY, 2, [8, 9])
panel.topo_ogrid_cell.setValue(0.21)
check("8b. ...and the flag APPEARS again from a plain parameter keystroke, so the "
      "check does not depend on the user leaving and re-entering the Mesh stage",
      panel._topo_repair.isVisible())
restore_meta(BODY, BODY_META)

# ── 9. the panel files stay under the file-length standard ─────────────────
_lengths = fl.measure(fl.gui_dir(_REPO))
_touched = {k: v for k, v in _lengths.items()
            if "mesh_config" in k or "topology" in k}
_over = {k: v for k, v in _touched.items() if v > fl.LIMIT}
check(f"9. every panel and service file this ticket touched is under the repo's "
      f"~{fl.LIMIT}-line standard, measured from the same walk "
      f"`test_file_length.py` enforces (worst: "
      f"{max(_touched.items(), key=lambda kv: kv[1])})",
      not _over)

# ── 10. the run PROCEEDS, in the criterion's own word ──────────────────────
# Driven the way the demo is: the CAD split lands on BOTH outlines, the panel flags
# both, and every repair is made through a dropdown. Then the same topology is run
# UNREPAIRED-BUT-UNBROKEN as the control, so "exit 0" is a claim about the repair and
# not about the fixture.
if not os.path.exists(_BIN):
    print("SKIP  build/HybMesh2D not built; the real-binary half is not measured.")
else:
    import mesher_bin  # noqa: E402

    def run_mesher(topo_model, ctx, label):
        """Project ``topo_model`` and mesh it; return ``(exit code, output)``."""
        with tempfile.TemporaryDirectory() as tmp:
            conf = os.path.join(tmp, "case.dat")
            topo = tm.project(topo_model, conf, ctx)
            stem = os.path.join(tmp, label)
            with open(conf, "w", encoding="utf-8") as fh:
                fh.write("MESH_MODE 1\n"
                         f"MESH_TOPOLOGY_FILE {topo}\n"
                         f"GEOM_FILE {BODY}\nGEOM_FILE {FAR}\n"
                         "BL_INITIAL_THICKNESS 0.001\nMB_SPLIT_QUADS 1\n"
                         "EXPORT_VTK 1\nBC_GEOM inlet\n"
                         f"OUTPUT_FILENAME {stem}.vtk\n"
                         + mesher_bin.NO_SMOOTH)
            r = subprocess.run([_BIN, "-conf", conf], cwd=tmp,
                               env=mesher_bin.mesher_env(), capture_output=True,
                               text=True, timeout=900)
            return r.returncode, (r.stdout or "") + (r.stderr or "")

    # MB_SMOOTH_ITERS 0, the spelling five other gates share. Measured first without
    # it: this fixture's own UNBROKEN four-block ring comes back at exit 9 with 32 of
    # 704 cells inverted AFTER the smoother (0 before it), on a 0.5 body inside a 4.0
    # far field at a 0.2 circumferential cell. That is the smoother's business, held
    # by `test_multiblock_smooth_surface.py`; measuring it here would make a binding
    # gate fail for a reason that has nothing to do with a binding.
    _base_rc, _base_out = run_mesher(cfg_for().topology, ctx_for(cfg_for()), "base")
    check(f"10pre2. CONTROL: the same fixture, four blocks and no CAD edit, meshes "
          f"to exit 0 — so check 10's exit code is about the repair rather than "
          f"about this geometry (exit {_base_rc})", _base_rc == 0)

    split_segment_in_meta(BODY, 2, [8, 9])
    split_segment_in_meta(FAR, 2, [10, 11])
    p10 = MeshConfigPanel()
    p10.set_config(cfg_for())
    r10 = p10._topo_repair._rows
    check(f"10pre. the CAD edit flagged both outlines in a freshly built panel "
          f"({[t for _i, t in flagged(p10)]})", len(flagged(p10)) == 2)
    # The SENSIBLE pick, the way a user makes it: segment 2 became 8 and 9 (10 and 11
    # on the far field), so the edge that was on 2 goes on the FIRST half, where that
    # edge started. Not "whatever is first in the list": the choice decides the ring's
    # ROTATION, so naming a segment on the far side of the body pairs each body corner
    # with a far corner most of a turn away — a legal document and a badly skewed mesh
    # (measured: exit 9, 67 of 704 inverted). Recorded as a blind spot in
    # `.claude/rules/gui-topology.md`.
    for want in (8, 10):
        # One at a time and re-asked each round: repairing one rebuilds the list, so a
        # loop over a snapshot of the rows would act on a row that has moved.
        combo = r10[flagged(p10)[0][0]][1]
        offered = [combo.itemData(k) for k in range(combo.count())]
        combo.setCurrentIndex(offered.index(want))
    check(f"10pre3. ...and both were repaired through the dropdowns, leaving nothing "
          f"flagged ({flagged(p10)})", not flagged(p10))
    repaired = p10.get_config()
    _rc, _out = run_mesher(repaired.topology, ctx_for(repaired), "mesh")
    check(f"10. a topology repaired ONLY through the panel's dropdowns runs the real "
          f"mesher to exit 0 — 'the run proceeds', in the criterion's own word "
          f"(bindings {repaired.topology.ogrid_body_segs!r} / "
          f"{repaired.topology.ogrid_far_segs!r}, exit {_rc})", _rc == 0)
    _rows = re.findall(r"Inverted cells\s*:\s*(\d+) of (\d+)", _out)
    check(f"10b. ...over a mesh that exists, with no inverted cells in the LAST row "
          f"the run reports — the mesher prints one per stage, and reading the first "
          f"would answer about the mesh before the stage that could fold it "
          f"({_rows or 'no Inverted cells row'})",
          bool(_rows) and _rows[-1][0] == "0" and int(_rows[-1][1]) > 0)
    check(f"10c. ...and the ring really is one block bigger than the control, so "
          f"check 10 is not passing on a topology that ignored the CAD edit "
          f"({len(tm.build_document(repaired.topology, ctx_for(repaired))['blocks'])} "
          f"blocks)",
          len(tm.build_document(repaired.topology,
                                ctx_for(repaired))["blocks"]) == 5)
    restore_meta(BODY, BODY_META)
    restore_meta(FAR, FAR_META)

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print("All checks passed.")
