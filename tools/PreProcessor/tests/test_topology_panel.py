#!/usr/bin/env python3
"""The template panel: what it SHOWS, and that it shows the family's own numbers
(issue #134, parent #133).

Headless, against displayed text and panel state — the style of the other GUI gates
here, and the only form in which "the derived counts are visible as the user types"
is a checkable claim rather than a description of some code.

The two gates beside this one hold the halves it deliberately does not: the
document's structure and the real-binary run (``test_topology_templates.py``), and
parameters <-> families in both directions (``test_topology_param_specs.py``).

WHAT MATTERS MOST HERE is check 4. The panel could satisfy every other check in this
file with its own copy of the count arithmetic, and it would then be free to display
a number the generated mesh does not use — the two-homes-for-one-fact failure this
whole feature is shaped to avoid. So the display is compared against
``topology_hgrid.hgrid_counts`` AND the panel's source is read for a second
derivation.

INJECTIONS: run by hand, 2026-09-22, each reverted and the file's checksum compared
against its pre-injection copy afterwards. Five, all of which bit; three of the five
bit differently from the prediction written beside them, and the measurements are
what is recorded.

  A. ``_refresh_topology_counts`` returns before setting the label -> SIX checks
     red (2, 2b, 3, 3b, 3c, 4a), not the three predicted. Every claim this file
     makes about the read-out rests on the read-out existing, so the blast radius
     of removing it is the whole set rather than a subset.
  B. the refresh wired only to the family combo, not to every parameter -> checks
     3, 3b and 3c red while 2 stays GREEN: the label is populated once and then
     frozen. Exactly why "it displays something" and "it displays THIS, now" are
     separate checks.
  C. the panel recomputing the counts inline (``round(span / nx / cell)``) instead
     of calling the family -> check 4b red on the source scan as predicted, and
     check 3c red as well, which was NOT predicted: the inline copy silently
     dropped the OVERRIDE, because overriding is part of the derivation and not a
     step after it. Check 4a stayed GREEN throughout — an inline copy that agrees
     on the default parameters displays the right number on the default
     parameters, which is the whole reason 4b exists beside 4a.
  D. drop ``d["topology"]`` from ``MeshConfig.to_dict`` -> check 6 red. Without it
     the project-undo snapshot cannot see a template edit, so Ctrl+Z would silently
     do nothing in this section.
  E. make the restore unconditional (drop the ``isinstance(dict)`` guard) -> the
     gate CRASHES with ``KeyError: 'topology'`` at check 7's setup rather than
     printing a red check 7. Recorded as it happened: the bite is real and is the
     one check 7 is for (a project file written before templates must load exactly
     as it did), but a reader scoring this file by counting FAIL lines would score
     this injection ZERO. Read the exit code, not the FAIL count.

INJECTIONS for the O-grid half (#137), run by hand 2026-09-23, each reverted. All
six bit. (Every run of this file prints `QOpenGLWidget is not supported on this
platform` on stderr, GREEN runs included, so stderr is not the crash signal here —
the exit code is.)

  G. `_refresh_topology_counts` returns before setting `topo_ogrid_derived` -> 11,
     11c and 12a red. **11b stayed GREEN**, and that is the finding: it asserts the
     ABSENCE of the O-grid's numbers when another family is selected, which an empty
     read-out satisfies just as well. A negative check cannot notice a missing
     read-out, which is why 11 and 12a are stated positively beside it.
  H. `_capture_topology_binding` returns immediately -> 13 and 13c red; 13b and 13d
     GREEN, because both assert that a binding is LEFT ALONE and a handler that does
     nothing leaves everything alone. The same asymmetry as G, recorded rather than
     tidied: the two "leave it alone" checks are only meaningful beside the two that
     require a capture to have happened.
  I. the read-out's context forced to `None`, so the panel stops resolving against
     the case's geometries -> the same three as G. The read-out then shows the
     family's "needs the geometry list" sentence, which is right for a panel that
     genuinely has no config and wrong for this one.
  J. the capture keyed on "do the held ids still resolve?" instead of on WHICH FILE
     the binding was captured for -> 13d red alone. That was the shipped behaviour
     until the Spec review measured it: both shipped circles carry segments 0-3, so
     switching the body from one to the other kept a binding chosen for the other
     shape, and no other check here can see it.
  N. `BINDING_ROWS` naming a segment row that does not exist -> `test_topology_
     param_specs.py` check 9 red AND 13, 13c, 13d, 13e red here. The pairing being
     DECLARED rather than spelled in the view is what lets a gate see it at all.
  O. the `readonly=True` dropped from the body binding row -> check 13f red here and
     `test_topology_param_specs.py` check 10 red. Two gates on one rule because the
     table is where it is declared and the widget is where it is felt.

CHECKS 15-15d, and the audit that added them (2026-09-23, closing #133). #133's user
story 22 — "parameter edits are undoable like every other panel's, so that the
topology panel is not the one place Ctrl+Z does nothing" — was the one story of the
twenty-eight that no sub-ticket's gate carried, found by auditing the parent
literally at the end of the batch rather than by anything going red. It WORKS; what
was missing was anything that would notice if it stopped. The two undo checks that
existed are about ACTIONS reaching a widget through a handler (`test_topology_repair`
7, `test_topology_detach` 13d); this is the ordinary route, a user typing into a spin
box, which reaches the recorder through `undo_ctrl._wire_widget_edits`' traversal.

  P. `MeshConfig.to_dict` dropping the topology key -> FIVE red (6, 10, 10b, 15b,
     15c), and TWO things had to be fixed before it could say so. The first run
     printed ONE red and a `KeyError: 'topology'` at check 10's setup, ending the
     file — checks 10 to 15d never ran, so the injection that removes undo entirely
     scored a one. Section 10's snapshot reads are `.get(...)` now, in the f-strings
     as well as in the conditions, which is where the second crash hid. The second
     was in check 15 itself: its fixture started `hgrid_nx` at the model's DEFAULT,
     and an absent section RESTORES THE DEFAULT MODEL (#135's rule), so "undo put my
     value back" and "undo reset everything" were the same number and 15c passed on
     the injection. It starts at 3 now and says why.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
sys.path.insert(0, _GUI)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from app.models.mesh_config import MeshConfig  # noqa: E402
from app.services import topology_hgrid  # noqa: E402
from app.services.topology_model import TopologyModel  # noqa: E402
from app.services.mesh_modes import MESH_MODE_HYBRID, MESH_MODE_MULTIBLOCK  # noqa: E402
from app.views.panels.mesh_config_panel import MeshConfigPanel  # noqa: E402

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


_app = QApplication.instance() or QApplication([])
panel = MeshConfigPanel()
panel.show()


def cfg_for(mode, family="hgrid", **kw):
    c = MeshConfig()
    c.mesh_mode = mode
    c.topology.family = family
    for k, v in kw.items():
        setattr(c.topology, k, v)
    return c


# ── 1. the section follows the mode, whole ─────────────────────────────────
panel.set_config(cfg_for(MESH_MODE_HYBRID))
hybrid_vis = panel.sec_topology.isVisible()
panel.set_config(cfg_for(MESH_MODE_MULTIBLOCK))
mb_vis = panel.sec_topology.isVisible()
check(f"1. the Block Topology section is hidden in the hybrid mode and shown in "
      f"multi-block (hybrid={hybrid_vis}, multi-block={mb_vis}) — every row in it "
      "declares modes=(MULTIBLOCK,), so in hybrid it would be an empty header "
      "offering a template that path cannot use",
      hybrid_vis is False and mb_vis is True)

# ── 2. the derived counts are displayed, and are not a blank ──────────────
panel.set_config(cfg_for(MESH_MODE_MULTIBLOCK))
shown = panel.topo_hgrid_counts_derived.text()
check(f"2. the derived node counts are displayed: {shown!r}",
      bool(shown.strip()) and "X:" in shown and "Y:" in shown)

panel.set_config(cfg_for(MESH_MODE_MULTIBLOCK, family=""))
none_text = panel.topo_hgrid_counts_derived.text()
check(f"2b. with no template selected the read-out SAYS so rather than going "
      f"blank ({none_text!r}) — a blank cell in a row of numbers reads as a zero",
      bool(none_text.strip()) and "X:" not in none_text)

# ── 3. ...and they follow the parameters as they are typed ───────────────
panel.set_config(cfg_for(MESH_MODE_MULTIBLOCK))
before = panel.topo_hgrid_counts_derived.text()
panel.topo_hgrid_nx.setValue(4)
after_nx = panel.topo_hgrid_counts_derived.text()
panel.topo_hgrid_cell.setValue(0.25)
after_cell = panel.topo_hgrid_counts_derived.text()
panel.topo_hgrid_counts_x.setText("3,,9,")
after_override = panel.topo_hgrid_counts_derived.text()
check(f"3. the read-out changes when the block count changes ({before!r} -> "
      f"{after_nx!r})", before != after_nx and "4x2" in after_nx)
check(f"3b. ...when the target cell size changes ({after_cell!r})",
      after_cell != after_nx)
check(f"3c. ...and when an override is typed, at the position it names "
      f"({after_override!r})",
      after_override != after_cell and "9" in after_override)

# ── 4. the number shown is the FAMILY's, and the panel has no second copy ─
panel.set_config(cfg_for(MESH_MODE_MULTIBLOCK, hgrid_nx=3, hgrid_cell=0.07,
                         hgrid_x_min=0.0, hgrid_x_max=1.5))
model = panel.get_config().topology
xc, yc = topology_hgrid.hgrid_counts(model)
shown = panel.topo_hgrid_counts_derived.text()
check(f"4a. every count the family derives appears in the read-out (family says "
      f"x={xc} y={yc}; panel shows {shown!r})",
      all(str(v) in shown for v in xc + yc))

_src = ""
for name in ("mesh_config_build_mixin.py", "mesh_config_config_mixin.py",
             "mesh_config_panel.py"):
    _src += open(os.path.join(_GUI, "app", "views", "panels", name),
                 encoding="utf-8").read()
check("4b. ...and the panel's own sources call hgrid_counts rather than deriving a "
      "count themselves — an inline copy that agrees today is still a second home "
      "for the derivation, and check 4a cannot see one",
      "hgrid_counts" in _src and "/ float(cell)" not in _src
      and "intervals" not in _src)

# ── 5. the round trip is exact ───────────────────────────────────────────
c = cfg_for(MESH_MODE_MULTIBLOCK, hgrid_nx=3, hgrid_ny=4, hgrid_cell=0.02,
            hgrid_x_min=-2.0, hgrid_x_max=6.5, hgrid_wall_bottom=False,
            hgrid_counts_x="5,6,7")
panel.set_config(c)
back = panel.get_config().topology
check(f"5. set_config -> get_config round-trips every template parameter exactly "
      f"({back})", back == c.topology)

# ── 6. the undo snapshot can SEE a template edit ─────────────────────────
# `project_state_ctrl._collect_project_state` IS `cfg.to_dict()`, so a field it
# does not carry is a field Ctrl+Z cannot restore. `topology` has no `.dat` key for
# `_key_map()` to find it by, which is why it has to be named there explicitly.
a = MeshConfig()
a.topology.family = "hgrid"
a.topology.hgrid_nx = 5
d = a.to_dict()
b = MeshConfig()
b.load_from_dict(d)
check("6. MeshConfig.to_dict carries the topology model, so the project-undo "
      f"snapshot sees a template edit, and load_from_dict restores it exactly "
      f"({b.topology.family!r}, nx={b.topology.hgrid_nx})",
      "topology" in d and b.topology == a.topology)

# ── 7. a project file written before templates loads unchanged ──────────
legacy = {k: v for k, v in d.items() if k != "topology"}
fresh = MeshConfig()
fresh.load_from_dict(legacy)
check("7. a config dict with NO topology key loads without raising and keeps the "
      f"defaults, whose family is '' and so names no template "
      f"({fresh.topology.family!r}, nx={fresh.topology.hgrid_nx})",
      fresh.topology.family == "" and fresh.topology.hgrid_nx == 2)

# ── 8. a restore coerces, rather than trusting the file ────────────────
n = MeshConfig()
n.load_from_dict({"topology": {"family": "hgrid", "hgrid_nx": "7",
                               "hgrid_cell": "0.05"}})
check("8. a hand-written project file that QUOTES a number restores as the number, "
      f"not as a str that the family function would then concatenate "
      f"({n.topology.hgrid_nx!r}, {n.topology.hgrid_cell!r})",
      n.topology.hgrid_nx == 7 and n.topology.hgrid_cell == 0.05)

# ── 9. the sync is allowed to carry a template edit to the global model ──
# `PRESERVED_FIELDS` is what `sync_panel_to_model` refuses to overwrite, derived from
# what the panel's sources are seen to author. If `topology` landed in it, the global
# model would keep its OLD topology and every parameter the user typed would be
# dropped on the way out of the panel — green everywhere else in this file, because
# every other check here talks to the panel directly.
from app.services.config_ownership import preserved_fields  # noqa: E402

_pres = set(preserved_fields("mesh_config_panel", MeshConfig))
check("9. `topology` is NOT in the mesh panel's PRESERVED_FIELDS, so the "
      "panel->model sync is allowed to carry a template edit to the global config "
      f"(preserved: {sorted(_pres)})", "topology" not in _pres)

# ── 10. ...and through the REAL controller, it actually does ────────────
# Check 9 proves the sync is ALLOWED to carry a template edit. This proves it does,
# through the same AppController the app runs: a programmatic push populates, a
# widget edit reaches the global model, and the project snapshot — which IS the undo
# baseline (`_collect_project_state`) — sees both. Slower than every other check
# here by an order of magnitude, and worth it: the defect this batch actually shipped
# and had to fix was invisible to every panel-only check in this file.
from app.controller import AppController  # noqa: E402

_c = AppController()
_panel = _c.main_window.mesh_config_panel
_cfg = MeshConfig()
_cfg.mesh_mode = MESH_MODE_MULTIBLOCK
_cfg.topology.family = "hgrid"
_cfg.topology.hgrid_nx = 3
_c.push_panel_config(_panel, _cfg)
# `.get(..., {})`, not `[...]`: an injection that drops the topology key from
# `to_dict` (the defect check 6 above is FOR) made this line raise `KeyError` and end
# the file, so checks 10 to 15 never ran and the injection scored one red instead of
# several. Read the exit code, not the FAIL count — and index defensively so the
# count means something.
_snap = _c._collect_project_state()["mesh_config"].get("topology", {})
check(f"10. a programmatic push through push_panel_config reaches the project "
      f"snapshot ({_snap.get('family')!r}, nx={_snap.get('hgrid_nx')})",
      _snap.get("family") == "hgrid" and _snap.get("hgrid_nx") == 3)
_panel.topo_hgrid_nx.setValue(6)
_c.sync_panel_to_model("mesh_config_panel")
_after = _c._collect_project_state()["mesh_config"].get("topology", {})
check(f"10b. ...and a WIDGET edit reaches the global model through "
      f"sync_panel_to_model, and the snapshot with it "
      f"(model nx={_c.global_mesh_config.topology.hgrid_nx}, "
      f"snapshot nx={_after.get('hgrid_nx')})",
      _c.global_mesh_config.topology.hgrid_nx == 6
      and _after.get("hgrid_nx") == 6)

# ── 11. the O-grid read-out shows the DERIVATION, not just its result ───
# #137's claim is that displaying the derivation is the single most useful thing the
# panel does, so this checks the WORKING is on screen — the ratio's own expression
# and both first cells — and not only the count it ends at.
_B = os.path.join(_REPO, "examples", "geometries", "circle_body.dat")
_F = os.path.join(_REPO, "examples", "geometries", "circle_farfield.dat")
og_cfg = cfg_for(MESH_MODE_MULTIBLOCK, family="ogrid", ogrid_body_geom=_B,
                 ogrid_far_geom=_F, ogrid_splits=1, ogrid_cell=0.0327)
og_cfg.bl_initial_thickness = 1e-3
og_cfg.add_geom_file(_B)
og_cfg.add_geom_file(_F)
panel.set_config(og_cfg)
og_shown = panel.topo_ogrid_derived.text()
check(f"11. the O-grid read-out shows its derivation with the working — the ratio's "
      f"own expression, the 1:1 first cell, the one asked for and the factor between "
      f"them — and not only the radial count it ends at: {og_shown!r}",
      "2\u03c0/96" in og_shown and "BL_INITIAL_THICKNESS" in og_shown
      and "32.7" in og_shown and "103" in og_shown)
panel.set_config(cfg_for(MESH_MODE_MULTIBLOCK))
check("11b. ...and with the H-grid selected it says so rather than showing the "
      f"O-grid's numbers ({panel.topo_ogrid_derived.text()!r})",
      "2\u03c0" not in panel.topo_ogrid_derived.text())
panel.set_config(og_cfg)
panel.topo_ogrid_cell.setValue(0.0654)
og_after = panel.topo_ogrid_derived.text()
check(f"11c. ...and it follows the parameters as they are typed, through a signal "
      f"that reaches a context the panel read back for itself ({og_after!r})",
      og_after != og_shown and "2\u03c0/48" in og_after)

# ── 12. that number is the FAMILY's, and the panel holds no second copy ──
_og_model = panel.get_config().topology
from app.services import topology_binding as _tb  # noqa: E402
from app.services import topology_ogrid as _og  # noqa: E402

_plan = _og.plan(_og_model, _tb.context_for_config(panel.get_config()))
check(f"12a. every line the panel shows is a line topology_ogrid.plan produced "
      f"({_plan.lines()!r})",
      og_after == "\n".join(_plan.lines()))
check("12b. ...and the panel's own sources call plan() rather than deriving a "
      "radial count themselves — an inline copy that agrees today is still a second "
      "home for the derivation, and 12a cannot see one",
      "topology_ogrid.plan" in _src.replace("\n", " ")
      or ".plan(model, ctx)" in _src, )
check("12c. ...checked against sources that really were read, so 12b cannot pass "
      f"on an empty string ({len(_src)} chars)", len(_src) > 5000)

# ── 13. naming a geometry CAPTURES its segment ids as the binding ───────
# What makes a later deletion a refusal rather than a silently shorter ring: with the
# row blank the family adopts whatever the geometry has at projection time.
# EVERY setText BELOW REALLY CHANGES THE TEXT. Qt emits no `textChanged` for a write
# of the value already held, so re-setting the same absolute path would leave the
# handler unwired and the check would pass on a capture that never ran — which is how
# 13b first passed vacuously. The "same file again" case is therefore spelled
# REPO-RELATIVE, which is a real text change naming the same file and exercises the
# identity match at the same time.
_B_REL = os.path.relpath(_B, _REPO)
panel.set_config(cfg_for(MESH_MODE_MULTIBLOCK, family="ogrid"))
panel.topo_ogrid_body_geom.setText(_B)
captured = panel.topo_ogrid_body_segs.text()
check(f"13. naming the body geometry captures its CURRENT segment ids into the "
      f"binding row ({captured!r}), so the stored binding is an id list rather than "
      f"a blank that re-adopts whatever is there at run time",
      [t.strip() for t in captured.split(",")] == ["0", "1", "2", "3"])
panel.topo_ogrid_body_segs.setText("2, 1")
panel.topo_ogrid_body_geom.setText(_B_REL)
check("13b. ...and re-naming the SAME geometry (here by its repo-relative spelling, "
      "so the widget really emits) leaves a hand-edited binding alone, "
      "because re-picking a file must not silently re-adopt segments the user has "
      f"since chosen ({panel.topo_ogrid_body_segs.text()!r})",
      panel.topo_ogrid_body_segs.text() == "2, 1")
panel.topo_ogrid_body_segs.setText("2, 9")
panel.topo_ogrid_body_geom.setText(_B)
check("13c. ...while a held binding the named geometry cannot answer for IS "
      "re-captured, because a binding that resolves to nothing is not an answer to "
      f"protect ({panel.topo_ogrid_body_segs.text()!r})",
      [t.strip() for t in panel.topo_ogrid_body_segs.text().split(",")]
      == ["0", "1", "2", "3"])
panel.topo_ogrid_body_segs.setText("2, 1")
panel.topo_ogrid_body_geom.setText(_F)
check("13d. ...and swapping to a DIFFERENT geometry ALWAYS re-captures, even when "
      "the held ids happen to resolve on the new one — both shipped circles carry "
      "segments 0-3, so a rule keyed on 'does it still resolve' kept a binding "
      "chosen for the other shape, which is this ticket's failure class by another "
      f"route ({panel.topo_ogrid_body_segs.text()!r})",
      [t.strip() for t in panel.topo_ogrid_body_segs.text().split(",")]
      == ["0", "1", "2", "3"])
panel.topo_ogrid_body_segs.setText("nonsense")
panel.topo_ogrid_body_geom.setText(_B)
check("13e. ...and a binding the family's OWN parser refuses is re-captured rather "
      "than protected, which is what keeps the panel's reading of this string and "
      f"the projection's the same one ({panel.topo_ogrid_body_segs.text()!r})",
      [t.strip() for t in panel.topo_ogrid_body_segs.text().split(",")]
      == ["0", "1", "2", "3"])
check("13f. the two binding rows are READ-ONLY, because #133 decides which edges "
      "bind is the template's decision and not the user's — a hand-typed id list is "
      "a more internal control than the arc length the decision was protecting them "
      "from",
      panel.topo_ogrid_body_segs.isReadOnly()
      and panel.topo_ogrid_far_segs.isReadOnly())

# ── 14. the O-grid parameters round-trip too ───────────────────────────
c14 = cfg_for(MESH_MODE_MULTIBLOCK, family="ogrid", ogrid_body_geom=_B,
              ogrid_far_geom=_F, ogrid_body_segs="5, 11", ogrid_far_segs="3,1",
              ogrid_splits=3, ogrid_cell=0.031, ogrid_radial_count=42)
panel.set_config(c14)
check(f"14. set_config -> get_config round-trips every O-grid parameter exactly, "
      f"including the two binding lists ({panel.get_config().topology})",
      panel.get_config().topology == c14.topology)

# ── 15. a plain PARAMETER edit is undoable, through the REAL controller ────
# #133's user story 22 — "parameter edits are undoable like every other panel's, so
# that the topology panel is not the one place Ctrl+Z does nothing" — was the one
# story of the twenty-eight that no sub-ticket's gate carried, found by auditing the
# parent literally at the end of the batch (#139). It WORKS; what was missing was
# anything that would notice if it stopped.
#
# The two undo checks that already existed are about actions, not parameters:
# `test_topology_repair.py` check 7 undoes a binding REPAIR and
# `test_topology_detach.py` check 13d undoes a DETACH. Both go through a widget
# written programmatically by a handler. This one is the ordinary case — a user
# typing into a spin box — which reaches the recorder by a different route
# (`undo_ctrl._wire_widget_edits`' traversal of QAbstractSpinBox) and is the route
# every other template parameter uses.
from app.controller import AppController  # noqa: E402

_ctl = AppController()
_up = _ctl.main_window.mesh_config_panel
# nx=3, deliberately NOT the model's default of 2. Injection N — `to_dict` dropping
# the topology key — left check 15c GREEN with a fixture that started at the
# default: an absent section RESTORES THE DEFAULT MODEL (#135's rule), so "undo put
# my value back" and "undo reset everything" were the same number. A fixture that
# cannot tell the two apart is not measuring undo.
_ctl.push_panel_config(_up, cfg_for(MESH_MODE_MULTIBLOCK, hgrid_nx=3))
_before_nx = _ctl.global_mesh_config.topology.hgrid_nx
_up.topo_hgrid_nx.setValue(5)
_after_nx = _ctl.global_mesh_config.topology.hgrid_nx
check(f"15. typing a template parameter reaches the GLOBAL model through the panel "
      f"-> model sync, like every other panel field ({_before_nx} -> {_after_nx})",
      _before_nx == 3 and _after_nx == 5)
check("15b. ...and it was RECORDED as an undo step rather than merely applied",
      _ctl.flush_project_snapshot())
_ctl.undo()
check(f"15c. ...so Ctrl+Z walks it back TO THE VALUE THAT WAS THERE, which is a "
      f"different claim from resetting to the default "
      f"(nx={_ctl.global_mesh_config.topology.hgrid_nx}, want 3, default "
      f"{TopologyModel().hgrid_nx})",
      _ctl.global_mesh_config.topology.hgrid_nx == 3
      and TopologyModel().hgrid_nx != 3)
_ctl.redo()
check(f"15d. ...and redo re-applies it, in the model AND in the widget the user is "
      f"looking at (model={_ctl.global_mesh_config.topology.hgrid_nx}, "
      f"widget={_up.topo_hgrid_nx.value()})",
      _ctl.global_mesh_config.topology.hgrid_nx == 5
      and _up.topo_hgrid_nx.value() == 5)

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print("All checks passed.")
