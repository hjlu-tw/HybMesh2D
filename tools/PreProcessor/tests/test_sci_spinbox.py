#!/usr/bin/env python3
"""Regression tests for finding N4 — scientific-notation numeric input.

The defect: every length/size field was a fixed-notation ``QDoubleSpinBox`` with a
hardcoded floor and decimal count, e.g. BL initial thickness as
``setRange(1e-6, 1.0)`` + ``setDecimals(6)``. A y+~1 first boundary-layer cell on
a chord-normalised geometry is routinely 1e-7..1e-8, so the value an engineer
needed was **silently clamped to 1e-6** — a different mesh than the one asked
for, with no warning. ``CleanDoubleSpinBox`` also never overrode
``valueFromText``, so Qt's validator rejected the ``e`` in ``1.2e-7`` outright.
Millimetre-scale geometry hit the same wall on mesh sizes, coordinates and
resampling spacing.

Checks:
 1. SciDoubleSpinBox holds and displays values the old field could not.
 2. Scientific notation is accepted as input; garbage still is not.
 3. Every prefix on the way to "1e-7" stays typable (not rejected mid-entry).
 4. Stepping is decade-relative, not Qt's blunt 1.0.
 5. Out-of-range input is clamped by fixup(), not silently accepted.
 6. specialValueText ("auto") survives the validate/interpret overrides.
 7. The fields that block CFD work actually use the new widget, with no floor.
 8. An un-populated panel still reports the MeshConfig defaults (the old field's
    minimum was doing that implicitly via clamping).
 9. A small value round-trips GUI -> panel -> .dat -> reload without loss, in the
    C-locale scientific form the C++ reader (`ss >> double`) accepts.
10. apply_smart_spin_steps skips these fields (its one fixed step, chosen at
    startup, cannot follow a value that moves orders of magnitude).

Run:  python3 tools/PreProcessor/tests/test_sci_spinbox.py
"""
import os
import sys
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >60s", flush=True)
    os._exit(99)


_wd = threading.Timer(60, _watchdog)
_wd.daemon = True
_wd.start()

from PyQt6.QtGui import QValidator  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.models.mesh_config import MeshConfig  # noqa: E402
from app.views.clean_double_spin_box import SciDoubleSpinBox  # noqa: E402

ACCEPT = QValidator.State.Acceptable
INTERM = QValidator.State.Intermediate
INVALID = QValidator.State.Invalid


def state(box, text):
    return box.validate(text, len(text))[0]


# ── 1. values the old field could not represent ────────────────────────────
box = SciDoubleSpinBox()
box.setRange(0.0, 1e4)
held = []
for v in (2.5e-7, 1e-8, 3.5e-6, 1234.5):
    box.setValue(v)
    held.append(abs(box.value() - v) <= abs(v) * 1e-9)
check(all(held), "1. holds 2.5e-7 / 1e-8 / 3.5e-6 / 1234.5 without clamping")
box.setValue(2.5e-7)
check(box.text() == "2.5e-07", f"1. displays it in exponent form (got {box.text()!r})")
box.setValue(0.25)
check(box.text() == "0.25", f"1. no exponent when none is needed (got {box.text()!r})")

# ── 2. scientific input accepted, garbage rejected ────────────────────────
good = {"1.2e-7": 1.2e-7, "3E+3": 3000.0, "0.00025": 2.5e-4, "5e-9": 5e-9, "7": 7.0}
bad_typed = [t for t, want in good.items()
             if state(box, t) != ACCEPT or abs(box.valueFromText(t) - want) > abs(want) * 1e-12]
check(not bad_typed,
      "2. accepts scientific + plain input" + (f" (failed: {bad_typed})" if bad_typed else ""))
check(state(box, "abc") == INVALID and state(box, "1e-7x") == INVALID,
      "2. still rejects non-numeric text")

# ── 3. partial entries must not be rejected mid-typing ────────────────────
partials = ["", "-", "+", "1e", "1e-", "1E+", "."]
rejected = [p for p in partials if state(box, p) == INVALID]
check(not rejected,
      "3. every prefix of a scientific number stays typable"
      + (f" (rejected: {rejected})" if rejected else ""))

# ── 4. decade-relative stepping ───────────────────────────────────────────
steps = []
for start, want in ((1e-6, 1.1e-6), (2.5e-3, 2.6e-3), (10.0, 11.0)):
    box.setValue(start)
    box.stepBy(1)
    steps.append(abs(box.value() - want) <= abs(want) * 1e-9)
check(all(steps), "4. one step moves the value by one decade below its own scale")
box.setValue(0.0)
box.stepBy(1)
check(0 < box.value() < 1e-3, f"4. stepping up from 0 does something small (got {box.value():g})")

# ── 5. out-of-range is clamped, not accepted ──────────────────────────────
check(state(box, "9e9") == INTERM,
      "5. an out-of-range entry is Intermediate (may still be on its way)")
check(abs(float(box.fixup("9e9")) - 1e4) < 1e-6,
      f"5. fixup() clamps it to the maximum (got {box.fixup('9e9')})")
check(abs(float(box.fixup("-5")) - 0.0) < 1e-12,
      f"5. ...and to the minimum below range (got {box.fixup('-5')})")

# ── 6. specialValueText survives the overrides ────────────────────────────
auto = SciDoubleSpinBox()
auto.setRange(0.0, 1e6)
auto.setSpecialValueText("auto")
auto.setValue(0.0)
check(auto.text() == "auto", f"6. the special value still displays as 'auto' (got {auto.text()!r})")
check(state(auto, "auto") == ACCEPT and auto.valueFromText("auto") == 0.0,
      "6. 'auto' can be typed back in")
check(state(auto, "au") == INTERM, "6. ...and is Intermediate while being typed")

# ── 7. the blocking fields actually use it, with no floor ─────────────────
from app.views.panels.mesh_config_panel import MeshConfigPanel  # noqa: E402
from app.views.panels.edge_props_panel import EdgePropsPanel  # noqa: E402

panel = MeshConfigPanel(None)
SCI_FIELDS = [
    ("bl_initial_thickness", 2.5e-7),
    ("surface_mesh_size", 4e-5),
    ("farfield_mesh_size", 1.5e-4),
    ("domain_x_min", -2.5e-3),
    ("domain_y_max", 3.5e-3),
    ("seed_size", 1e-6),
    ("seed_radius", 5e-5),
]
for name, probe in SCI_FIELDS:
    w = getattr(panel, name, None)
    check(isinstance(w, SciDoubleSpinBox), f"7. {name} is a SciDoubleSpinBox")
    if isinstance(w, SciDoubleSpinBox):
        w.setValue(probe)
        check(abs(w.value() - probe) <= abs(probe) * 1e-9,
              f"7. {name} accepts {probe:g} unclamped (got {w.value():g})")

edge = EdgePropsPanel(None)
sp = getattr(edge, "uniform_spacing", None)
check(isinstance(sp, SciDoubleSpinBox), "7. the resampling Spacing field is a SciDoubleSpinBox")
if isinstance(sp, SciDoubleSpinBox):
    sp.setValue(2e-5)
    check(abs(sp.value() - 2e-5) < 1e-15, "7. ...and accepts Δs = 2e-5 unclamped")

# The per-geometry BL override dialog edits the same physical quantity.
from app.views.panels.mesh_dialogs_bl import _BL_FIELD_SPECS  # noqa: E402

_thick_spec = next(o for k, _, _, o in _BL_FIELD_SPECS if k == "BL_INITIAL_THICKNESS")
check(_thick_spec.get("sci") is True and _thick_spec["lo"] == 0.0,
      "7. the per-geometry BL dialog's Initial Thickness is sci with no floor")

# ── 8. an un-populated panel still shows the model defaults ───────────────
fresh = MeshConfigPanel(None).get_config()
check(abs(fresh.bl_initial_thickness - MeshConfig.bl_initial_thickness) < 1e-15
      and abs(fresh.surface_mesh_size - MeshConfig.surface_mesh_size) < 1e-15
      and abs(fresh.farfield_mesh_size - MeshConfig.farfield_mesh_size) < 1e-15,
      "8. a fresh panel reports the MeshConfig defaults, not 0")

# ── 9. round-trip through the .dat the C++ side reads ─────────────────────
import tempfile  # noqa: E402

panel.bl_initial_thickness.setValue(2.5e-7)
panel.surface_mesh_size.setValue(4e-5)
panel.auto_surface_size.setChecked(False)
cfg = panel.get_config()
check(abs(cfg.bl_initial_thickness - 2.5e-7) < 1e-18,
      "9. get_config() carries the small value out of the panel")

with tempfile.NamedTemporaryFile("w", suffix="_sci.dat", delete=False) as tf:
    dat = tf.name
try:
    cfg.save_to_file(dat)
    with open(dat, encoding="utf-8") as f:
        lines = {ln.split()[0]: ln.split()[1] for ln in f
                 if len(ln.split()) == 2 and not ln.startswith("#")}
    check(lines.get("BL_INITIAL_THICKNESS") == "2.5e-07",
          f"9. written C-locale as 2.5e-07 (got {lines.get('BL_INITIAL_THICKNESS')!r})")
    reloaded = MeshConfig()
    reloaded.load_from_file(dat)
    check(abs(reloaded.bl_initial_thickness - 2.5e-7) < 1e-18
          and abs(reloaded.surface_mesh_size - 4e-5) < 1e-15,
          "9. reloading the .dat recovers the exact values")
finally:
    if os.path.exists(dat):
        os.remove(dat)

# ── 10. the fixed-step pass must leave these fields alone ─────────────────
from app.utils import apply_smart_spin_steps  # noqa: E402

probe = MeshConfigPanel(None)
probe.bl_initial_thickness.setValue(2.5e-7)
apply_smart_spin_steps(probe)
probe.bl_initial_thickness.stepBy(1)
check(abs(probe.bl_initial_thickness.value() - 2.6e-7) <= 2.6e-16,
      f"10. stepping still decade-relative after apply_smart_spin_steps "
      f"(got {probe.bl_initial_thickness.value():g})")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
