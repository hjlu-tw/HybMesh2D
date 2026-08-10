#!/usr/bin/env python3
"""Pre-flight validation must judge the domain the run will actually use.

**The bug this locks out.** A case with a BL body plus a *custom* far-field
outline ("Domain Source: Custom geometry") could not be generated at all:

    [WARN]  Geometry bounds ([2.886, 3.086] x [0.2, 0.8]) extend outside the
            domain box; the mesh may be clipped or the run may fail.
    [ERROR] Domain X Min must be strictly less than X Max.
    [ERROR] Domain Y Min must be strictly less than Y Max.

Nothing was wrong with the geometry, and nothing on the canvas was outside
anything. ``MeshConfig.validate()`` was checking the *rectangular box* — which a
custom domain hides, never uses, and which the mesher overwrites from the
outline geometry. Worse, the four spin boxes were built without ever being
seeded from the model defaults, so an untouched panel reported a degenerate
0..0 box: the run was blocked on numbers the user had not set and, with the
fields hidden, could not even see.

``Config.hpp::validate()`` already gates its own domain-span check on
``domainFile.empty()``. The GUI now agrees, which is the parity this test pins:
a check the backend deliberately skips must not be a GUI-side blocker.

Checks:
 1. A custom domain does NOT error on a degenerate rectangular box...
 2. ...while a rectangle-box domain still does (the check is skipped, not lost).
 3. Containment is measured against the custom outline's bounds, not the box —
    inside the outline is silent, outside still warns.
 4. The C++ gates the same check on the same condition (source parity).
 5. A freshly built mesh panel reports the model's default box, not 0..0.
 6. A global BL_LAYERS of 0 with a per-geometry BL_LAYERS override does not
    claim "no boundary layer will be grown" (the mesher honours the override).
 7. mesh_gen_ctrl feeds validate() the domain bbox it now scans for.

Run:  python3 tools/PreProcessor/tests/test_custom_domain_validation.py
"""
import inspect
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


from app.models.mesh_config import MeshConfig  # noqa: E402

# The reported case: a BL body plus a custom far-field outline, and a domain box
# nobody ever set (all four spin boxes at Qt's default 0).
BODY = "I_coarse_resampled.dat"
OUTLINE = "Untitled_1_resampled.dat"
BODY_BBOX = (2.886, 0.2, 3.086, 0.8)      # (xmin, ymin, xmax, ymax)
OUTLINE_BBOX = (0.0, 0.0, 10.0, 1.0)      # the body sits inside this


def custom_domain_cfg() -> MeshConfig:
    cfg = MeshConfig()
    cfg.geom_files = [BODY, OUTLINE]
    cfg.geom_roles = {BODY: {"role": "bl"}, OUTLINE: {"role": "farfield"}}
    cfg.domain_x_min = cfg.domain_x_max = 0.0
    cfg.domain_y_min = cfg.domain_y_max = 0.0
    return cfg


# ── 1. a custom domain does not error on the unused box ───────────────────
cfg = custom_domain_cfg()
check(cfg.domain_file == OUTLINE, "0. the far-field outline is recognised as the domain")

errors, warnings = cfg.validate(geom_bbox=BODY_BBOX, domain_bbox=OUTLINE_BBOX)
check(not any("Domain X Min" in e or "Domain Y Min" in e for e in errors),
      "1. a custom domain does not error on the degenerate rectangular box")
check(errors == [], f"1. ...and the run is not blocked at all (errors={errors})")

# ── 2. the rectangle box is still checked when it IS the domain ───────────
box = MeshConfig()
box.geom_files = [BODY]
box.geom_roles = {BODY: {"role": "bl"}}
box.domain_x_min = box.domain_x_max = 0.0
box.domain_y_min = box.domain_y_max = 0.0
box_errors, _ = box.validate(geom_bbox=BODY_BBOX)
check(any("Domain X Min" in e for e in box_errors)
      and any("Domain Y Min" in e for e in box_errors),
      "2. a rectangle-box domain still errors on min >= max (check skipped, not deleted)")

# ── 3. containment is measured against the outline, not the box ───────────
check(not any("extend outside" in w for w in warnings),
      "3. a body inside the custom outline raises no containment warning")

outside = cfg.validate(geom_bbox=(20.0, 0.2, 21.0, 0.8), domain_bbox=OUTLINE_BBOX)[1]
check(any("extend outside" in w for w in outside),
      "3. ...and a body outside the outline still does warn")

no_dom = cfg.validate(geom_bbox=BODY_BBOX, domain_bbox=None)[1]
check(any("could not be read" in w for w in no_dom),
      "3. an unreadable outline says the extent checks were skipped, not that the body escaped")
check(not any("extend outside" in w for w in no_dom),
      "3. ...and does not fall back to the meaningless box")

# ── 4. source parity with the C++ pre-flight ──────────────────────────────
CONFIG_HPP = os.path.join(_REPO, "include", "Config.hpp")
if not os.path.exists(CONFIG_HPP):
    print(f"SKIP {CONFIG_HPP} not found", flush=True)
else:
    src = open(CONFIG_HPP, encoding="utf-8", errors="replace").read()
    m = re.search(r"if\s*\(\s*domainFile\.empty\(\)\s*\)\s*\{(.*?)\n        \}", src, re.S)
    check(m is not None and "DOMAIN_X_MIN" in m.group(1) and "DOMAIN_Y_MIN" in m.group(1),
          "4. Config.hpp gates its domain-span check on domainFile.empty()")

    py = inspect.getsource(MeshConfig.validate)
    check("custom_domain" in py and "if not custom_domain:" in py,
          "4. ...and MeshConfig.validate() gates the same check the same way")

# ── 5. a fresh panel reports the model defaults, not 0..0 ─────────────────
try:
    from PyQt6.QtWidgets import QApplication
except ImportError:
    print("SKIP PyQt6 not available", flush=True)
else:
    app = QApplication.instance() or QApplication([])
    from app.views.panels.mesh_config_panel import MeshConfigPanel

    panel = MeshConfigPanel()
    pc = panel.get_config()
    d = MeshConfig()
    check((pc.domain_x_min, pc.domain_x_max, pc.domain_y_min, pc.domain_y_max)
          == (d.domain_x_min, d.domain_x_max, d.domain_y_min, d.domain_y_max),
          f"5. an untouched panel reports the default box, not 0..0 "
          f"(got {pc.domain_x_min}..{pc.domain_x_max} x {pc.domain_y_min}..{pc.domain_y_max})")
    check(pc.validate()[0] == [],
          "5. ...so an untouched panel's config passes validation")

# ── 6. a per-geometry BL_LAYERS override is not "no boundary layer" ───────
zero = MeshConfig()
zero.bl_layers = 0
zero.geom_files = [BODY]
zero.geom_roles = {BODY: {"role": "bl", "bl_params": {"BL_LAYERS": 12}}}
check(not any("no boundary layer" in w for w in zero.validate()[1]),
      "6. a per-geometry BL_LAYERS override suppresses the 'no boundary layer' warning")

zero_none = MeshConfig()
zero_none.bl_layers = 0
check(any("no boundary layer" in w for w in zero_none.validate()[1]),
      "6. ...but a genuinely BL-less config still warns")

# ── 7. the controller actually supplies the domain bbox ───────────────────
import app.controllers.mesh_gen_ctrl as mgc  # noqa: E402

run_src = inspect.getsource(mgc.MeshGenControllerMixin.run_mesh_generator)
check("domain_bbox=domain_bbox" in run_src,
      "7. run_mesh_generator passes the scanned domain bbox to validate()")
scan_src = inspect.getsource(mgc.MeshGenControllerMixin._scan_geometry_files)
check("domain_file" in scan_src,
      "7. _scan_geometry_files scans the custom outline's bounds too")
prev_src = inspect.getsource(mgc.MeshGenControllerMixin.preview_mesh_generator)
check("domain_file is None" in prev_src,
      "7. the canvas preview no longer refuses to draw a custom domain")

if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    sys.exit(1)
print("\nRESULT: ALL PASS", flush=True)
sys.exit(0)
