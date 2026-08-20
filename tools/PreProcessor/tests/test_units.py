#!/usr/bin/env python3
"""Length units, and the Linf/Reynolds coupling they exist for.

There was no unit system, and that was not cosmetic. From the UNICONES manual:
``fs_UnitRe`` is "per meter" and ``Linf`` is "Length scale used to normalize grid
coordinates (in meter), input 1 if dimensional in meters" — its own sample reads
``Linf 0.0254 //to convert mesh to meter`` for an inch grid. So ``Re = fs_UnitRe ×
Linf``, and a millimetre mesh left at ``Linf = 1`` runs at 1000× the intended Reynolds
number while every mesh picture looks perfect.

What this pins down:
 1. The unit table and parsing: exact factors, alias tolerance, no wild guessing.
 2. Linf IS metres-per-unit, and unit_for_linf reads a legacy Linf back as a unit.
 3. Conversion, including the identity short-circuit (no float drift on a no-op).
 4. A legacy solver config (hand-set linf, no length_unit) does NOT get silently
    re-derived — that would change Re on a case that used to run correctly.
 5. unit_check names the discrepancy in concrete terms (which unit, what factor).
 6. The panel: suffixes land on exactly the physical-length fields and nothing else,
    the value round-trips through the suffix, and the model unit reaches MeshConfig.
 7. The live reference-Reynolds read-out reproduces the manual's double-cone case.
 8. A unit change does NOT rescale numbers, and does NOT clobber the user's other
    Solver fields (a bug this feature introduced once and must not again).
 9. Import conversion scales coordinates once, and headless never prompts.
10. Cross-stage checks in a pipeline script.
11. GUI→C++ parity: the mesher parses LENGTH_UNIT and reports the same factor.

Run:  python3 tools/PreProcessor/tests/test_units.py
"""
import os
import subprocess
import sys
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >180s", flush=True)
    os._exit(99)


_wd = threading.Timer(180, _watchdog)
_wd.daemon = True
_wd.start()

import numpy as np  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.services import units  # noqa: E402

# ── 1. the table ──────────────────────────────────────────────────────────
check(units.metres_per_unit("m") == 1.0
      and units.metres_per_unit("mm") == 1.0e-3
      and units.metres_per_unit("in") == 0.0254
      and units.metres_per_unit("ft") == 0.3048,
      "1. unit factors are the exact definitions")
check(units.unit_codes() == ["m", "ft", "in", "cm", "mm", "um", units.CUSTOM],
      f"1. units are ordered coarsest-first with custom last, so the dropdown reads "
      f"like a ruler ({units.unit_codes()})")
check(units.plural("in") == "inches" and units.plural("ft") == "feet",
      "1. irregular plurals are stored, not formed by adding 's' — a warning reading "
      '"a grid in inchs" undermines itself')
check(units.parse("Millimetres") == "mm" and units.parse("inches") == "in"
      and units.parse("μm") == "um",
      "1. spelling variants and the micro sign parse")
check(units.parse("furlong") == "m" and units.parse("") == "m",
      "1. an unknown unit falls back rather than being guessed at — a wrong unit is "
      "worse than an unset one")
check(units.parse("u", default="mm") == "mm",
      '1. a bare "u" is NOT accepted as micro: one stray letter must not become a '
      "1e-6 factor")
check(units.metres_per_unit("custom", 0.0254) == 0.0254
      and units.metres_per_unit("custom", 0) == 1.0
      and units.metres_per_unit("custom", "junk") == 1.0,
      "1. a custom factor is used, and a bad one degrades to 1.0")

# ── 2. Linf is metres-per-unit ─────────────────────────────────────────────
check(units.linf_for("in") == 0.0254,
      "2. linf_for is metres-per-unit — the manual's inch grid is 0.0254")
check(units.unit_for_linf(0.0254) == "in" and units.unit_for_linf(1.0e-3) == "mm",
      "2. a legacy Linf reads back as the unit it means")
check(units.unit_for_linf(0.7) is None and units.unit_for_linf(-1) is None
      and units.unit_for_linf("x") is None,
      "2. an arbitrary/invalid Linf maps to no unit rather than the nearest one")

# ── 3. conversion ─────────────────────────────────────────────────────────
check(abs(units.convert(4500, "mm", "m") - 4.5) < 1e-12,
      "3. 4500 mm -> 4.5 m")
check(units.convert(1.234567890123, "m", "m") == 1.234567890123,
      "3. an identity conversion returns the value bit-for-bit (no float drift on a "
      "no-op the user did not ask for)")
pts = np.array([[0.0, 0.0], [4500.0, 1800.0]])
same = units.convert_points(pts, "m", "m")
check(same is pts, "3. convert_points returns the SAME object when the factor is 1, so "
                   "a caller can rely on identity to know nothing happened")
conv = units.convert_points(pts, "mm", "m")
check(abs(conv[1, 0] - 4.5) < 1e-12 and abs(conv[1, 1] - 1.8) < 1e-12,
      "3. convert_points scales coordinates")

# ── 4/5. legacy solver configs ────────────────────────────────────────────
from app.models.solver_config import SolverConfig  # noqa: E402

fresh = SolverConfig()
check(fresh.linf_from_unit and fresh.linf == 1.0 and fresh.length_unit == "m",
      "4. a fresh config derives Linf and starts in metres (== the old default, so "
      "adopting units changes no existing result)")

legacy = SolverConfig()
legacy.load_from_dict({"linf": 0.0254, "fs_unit_re": 2.2853e5})
check(not legacy.linf_from_unit and legacy.linf == 0.0254,
      "4. a config with a hand-set linf and NO length_unit keeps its linf and stops "
      "deriving — re-deriving would silently change Re on a case that used to run")

explicit = SolverConfig()
explicit.load_from_dict({"linf": 0.0254, "linf_from_unit": True})
check(explicit.linf_from_unit,
      "4. an explicit linf_from_unit in the file wins over that inference")

msgs = legacy.unit_check("m", 1.0)
check(any("inch" in m for m in msgs) and any("39" in m for m in msgs),
      f"5. the mismatch names the unit linf means and the Re factor ({msgs})")
check(any("Re = fs_UnitRe" in m for m in msgs),
      "5. the message says WHY it matters (Re = fs_UnitRe x Linf)")

derived = SolverConfig()
changed = derived.set_length_unit("mm")
check(changed and derived.linf == 1.0e-3 and derived.unit_check("mm", 1.0e-3) == [],
      "5. set_length_unit derives Linf and the result is self-consistent")
held = SolverConfig()
held.linf_from_unit = False
held.linf = 0.0254
check(not held.set_length_unit("mm") and held.linf == 0.0254,
      "5. set_length_unit does NOT touch a held linf")
bad = SolverConfig()
bad.linf = 0.0
check(any("must be positive" in m for m in bad.unit_check()),
      "5. a non-positive Linf is reported (it would zero the Reynolds number)")

mixed = SolverConfig()
mixed.set_length_unit("mm")
check(any("must agree" in m for m in mixed.unit_check("in", 0.0254)),
      "5. a solver/mesh unit disagreement is reported — the grid comes from that stage")

# ── 6/7/8. the panels ─────────────────────────────────────────────────────
from app.controller import AppController  # noqa: E402
from app.views.panels.mesh_units_mixin import LENGTH_FIELDS  # noqa: E402
from app.views.clean_double_spin_box import SciDoubleSpinBox  # noqa: E402

ctl = AppController()
mp = ctl.main_window.mesh_config_panel
sp = ctl.main_window.solver_config_panel

# Every physical-length field is a SciDoubleSpinBox (the N4 rule), so the panel's
# SciDoubleSpinBox set IS the set that must carry a unit. If they diverge, a field
# added later has silently lost its unit.
sci_on_panel = {name for name in dir(mp)
                if not name.startswith("__")
                and isinstance(getattr(mp, name, None), SciDoubleSpinBox)}
declared = set(LENGTH_FIELDS)
check(sci_on_panel == declared,
      f"6. LENGTH_FIELDS matches the panel's physical-length fields exactly "
      f"(missing a unit: {sorted(sci_on_panel - declared)}; "
      f"stale: {sorted(declared - sci_on_panel)})")

mp.unit_selector.set_unit("mm")
mp._apply_unit_suffixes()
check(mp.domain_x_min.suffix().strip() == "mm"
      and mp.bl_initial_thickness.suffix().strip() == "mm",
      "6. length fields carry the unit")
check(mp.bl_growth_rate.suffix().strip() == ""
      and mp.bl_fan_angle_threshold.suffix().strip() == "",
      "6. dimensionless fields (growth rate, angle) carry NO unit — labelling them "
      "would be a confident lie")
mp.bl_initial_thickness.setValue(1.2e-7)
check(mp.bl_initial_thickness.text() == "1.2e-07 mm"
      and mp.bl_initial_thickness.valueFromText("1.2e-07 mm") == 1.2e-07,
      f"6. a value round-trips THROUGH the suffix, in scientific notation "
      f"({mp.bl_initial_thickness.text()!r})")
check(mp.seed_radius.text() == "auto",
      f"6. specialValueText is not corrupted by the suffix "
      f"({mp.seed_radius.text()!r})")

cfg = mp.get_config()
check(cfg.length_unit == "mm", "6. the model unit reaches MeshConfig")

# The manual's double-cone case: fs_UnitRe 2.2853e5 /m, Linf 0.0254 m -> Re 5805.
sp.fs_unit_re.setValue(2.2853e5)
sp.linf_from_unit.setChecked(False)
sp.linf.setValue(0.0254)
check(sp.ref_reynolds.text() == "5805",
      f"7. the reference-Re read-out reproduces the manual's double-cone case "
      f"({sp.ref_reynolds.text()!r})")
check(not sp.linf.isReadOnly(), "7. a held Linf is editable")
sp.linf.setValue(1.0e-3)
check(sp.ref_reynolds.text() == "228.5",
      f"7. the same mesh declared in mm shows Re 1000x lower — the whole point of "
      f"the read-out ({sp.ref_reynolds.text()!r})")
sp.linf.setValue(0.0)
check(sp.ref_reynolds.text() == "—",
      "7. an unfilled form reads as unknown, not as a red error")

sp.linf_from_unit.setChecked(True)
check(sp.linf.isReadOnly(), "7. a derived Linf is read-only")

# A unit change relabels; it must not rescale, and must not take the user's other
# Solver fields with it (push_panel_config would have — that bug shipped once here).
sp.fs_unit_re.setValue(2.2853e5)
sp.fs_mach.setValue(12.65)
mp.domain_x_max.setValue(10.0)
mp.unit_selector.set_unit("in")
mp._on_unit_changed("in", 0.0254, "")
check(mp.domain_x_max.value() == 10.0,
      "8. changing the unit does NOT rescale a number the user typed")
check(ctl.global_solver_config.linf == 0.0254 and sp.linf.value() == 0.0254,
      f"8. Linf follows the model unit ({ctl.global_solver_config.linf})")
check(sp.fs_unit_re.value() == 2.2853e5 and sp.fs_mach.value() == 12.65,
      "8. the user's OTHER Solver fields survive — a derived field must not drag its "
      "neighbours back to the model's values")
check(sp.ref_reynolds.text() == "5805",
      f"8. and Re is right again ({sp.ref_reynolds.text()!r})")
check(ctl.length_unit_warnings() == [],
      f"8. a consistent project reports nothing ({ctl.length_unit_warnings()})")

# ── 9. import conversion ──────────────────────────────────────────────────
import tempfile  # noqa: E402

mp.unit_selector.set_unit("m")
mp._on_unit_changed("m", 1.0, "")
with tempfile.TemporaryDirectory() as td:
    dat = os.path.join(td, "unit_box.dat")
    np.savetxt(dat, np.array([[0, 0], [4500, 0], [4500, 1800], [0, 1800], [0, 0]],
                             dtype=float), fmt="%.6f")
    ctl._load_geometry_file(dat, record_recent=False, unit_scale=1.0e-3)
    sess = ctl.active_session()
    span = float(np.ptp(sess.original_points[:, 0]))
    check(abs(span - 4.5) < 1e-9,
          f"9. an import declared as mm lands in the model unit ({span})")
    check(sess.project_model.length_unit == "m",
          "9. the session records the model unit after conversion, not the file's")
check(ctl._ask_import_scale(1) == 1.0,
      "9. headless import never prompts and never converts — the CLI and pipeline "
      "paths must not block on a modal")

from app.views.import_unit_dialog import ImportUnitDialog, SAME_AS_MODEL  # noqa: E402

dlg = ImportUnitDialog("m", 2)
check(dlg.chosen() == SAME_AS_MODEL and dlg.scale_factor() == 1.0,
      "9. the dialog DEFAULTS to no conversion, so dismissing it cannot damage data")
idx = dlg.combo.findData("mm")
dlg.combo.setCurrentIndex(idx)
check(abs(dlg.scale_factor() - 1.0e-3) < 1e-15
      and "0.001" in dlg._note.text(),
      f"9. it states the factor in numbers, not as 'units will be converted' "
      f"({dlg._note.text()!r})")

# ── 10. pipeline script ───────────────────────────────────────────────────
from app.models.pipeline_config import PipelineConfig  # noqa: E402

p = PipelineConfig()
p.mesh = {"length_unit": "mm"}
p.solver = {"linf": 1.0, "fs_unit_re": 200.0}
w = p.unit_warnings()
check(any("1000" in m for m in w) and any("inch" not in m for m in w),
      f"10. a pipeline script whose solver.linf contradicts mesh.length_unit is "
      f"reported with the factor ({w})")
p.solver["linf"] = 1.0e-3
check(p.unit_warnings() == [], "10. a consistent script reports nothing")
p.cads = [{"length_unit": "in"}]
check(any("cads[0]" in m for m in p.unit_warnings()),
      "10. a CAD section in a different unit is reported (the mesher does not convert)")
p.cads = []
p.solver["linf"] = "junk"
check(any("not a number" in m for m in p.unit_warnings()),
      "10. a non-numeric linf is reported rather than crashing the run")
p.solver["linf"] = -1
check(any("must be positive" in m for m in p.unit_warnings()),
      "10. a negative linf is reported")

# ── 11. GUI -> C++ parity ─────────────────────────────────────────────────
hdr = open(os.path.join(_REPO, "include", "Config.hpp"), encoding="utf-8").read()
for key in ("LENGTH_UNIT", "LENGTH_UNIT_METRES", "LENGTH_UNIT_NAME"):
    check(f'key == "{key}"' in hdr, f"11. Config.hpp parses {key}")
check('if (lengthUnit == "in") return 0.0254;' in hdr,
      "11. the C++ factor table agrees with services/units.py (inch)")
check('if (lengthUnit == "mm") return 1.0e-3;' in hdr,
      "11. ... and for mm")
check("Model Unit" in hdr,
      "11. the mesher prints the unit in its banner, so it reaches the provenance "
      "sidecar too — a mesh must not travel downstream without saying what its "
      "coordinates mean")

binary = os.path.join(_REPO, "build", "HybMesh2D")
if not os.path.exists(binary):
    print("SKIP 11. build/HybMesh2D missing — run ./build.sh for the live check",
          flush=True)
else:
    with tempfile.TemporaryDirectory() as td:
        conf = os.path.join(td, "u.dat")
        with open(conf, "w") as f:
            f.write("LENGTH_UNIT in\nBL_LAYERS 1\n")
        r = subprocess.run([binary, "-conf", conf], capture_output=True, text=True,
                           timeout=120, cwd=_REPO)
        out = r.stdout + r.stderr
        check("0.0254" in out and "Model Unit" in out,
              "11. the built mesher reads LENGTH_UNIT in and reports Linf = 0.0254")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
