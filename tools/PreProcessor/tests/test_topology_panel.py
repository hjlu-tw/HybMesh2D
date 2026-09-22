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
_snap = _c._collect_project_state()["mesh_config"]["topology"]
check(f"10. a programmatic push through push_panel_config reaches the project "
      f"snapshot ({_snap['family']!r}, nx={_snap['hgrid_nx']})",
      _snap["family"] == "hgrid" and _snap["hgrid_nx"] == 3)
_panel.topo_hgrid_nx.setValue(6)
_c.sync_panel_to_model("mesh_config_panel")
_after = _c._collect_project_state()["mesh_config"]["topology"]
check(f"10b. ...and a WIDGET edit reaches the global model through "
      f"sync_panel_to_model, and the snapshot with it "
      f"(model nx={_c.global_mesh_config.topology.hgrid_nx}, "
      f"snapshot nx={_after['hgrid_nx']})",
      _c.global_mesh_config.topology.hgrid_nx == 6 and _after["hgrid_nx"] == 6)

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print("All checks passed.")
