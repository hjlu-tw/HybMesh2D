#!/usr/bin/env python3
"""End-spacing distribution for tanh / geometric edges (Phase-1 residual).

The C++ resampler has always accepted ``spacing_start`` / ``spacing_end`` for the
non-uniform strategies, but the GUI exposed no way to reach them: a wall's first
cell size could only be approximated by guessing an abstract "intensity" or growth
ratio. Both strategies now have a **By End Spacing** mode.

Two things had to be corrected on the way, and they are the reason this test exists:

* **tanh's spacing support did not work.** ``main.cpp`` mapped the request to a
  clustering parameter with the heuristic ``log(L / min(s0,s1)) * 0.5``, which does
  not reproduce the requested spacing (measured ~40x off on a chord-scale edge) and
  required BOTH ends to be set — a one-sided request silently fell back to
  ``intensity``. Replaced by ``Spacing::solveTanhDelta``, a bisection solve.
* **tanh is SYMMETRIC**, so it cannot honour different first/last spacings. The UI
  therefore has ONE "Δs at ends" field, not two; only ``geometric`` (genuinely
  asymmetric, and already a real solve) gets separate start/end fields.

Checks:
 1. Both strategies expose a mode combo, and the spacing fields are
    SciDoubleSpinBox with no floor (a wall spacing is 1e-5 or smaller).
 2. tanh has exactly ONE end-spacing field (symmetry), geometric has two.
 3. Writing: the chosen mode's keys are written and the other mode's are NOT —
    two sources for one quantity is how they drift apart.
 4. An "unset" (zero) end is OMITTED, not written as 0.0: that is how the
    resampler distinguishes one-sided from two-sided.
 5. Reading: the presence of a spacing key restores By-End-Spacing mode, so a
    hand-written or older config round-trips without a separate mode flag.
 6. (needs the built binary) the resampler REPRODUCES the requested spacing —
    tanh symmetric to within 1%, geometric one-sided likewise.

Run:  python3 tools/PreProcessor/tests/test_end_spacing_distribution.py
"""
import os
import subprocess
import sys
import tempfile
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
    print("FAIL watchdog: blocked >120s", flush=True)
    os._exit(99)


_wd = threading.Timer(120, _watchdog)
_wd.daemon = True
_wd.start()

import numpy as np  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.models.segment import SegmentModel  # noqa: E402
from app.views.clean_double_spin_box import SciDoubleSpinBox  # noqa: E402
from app.views.panels.edge_props_panel import EdgePropsPanel  # noqa: E402

panel = EdgePropsPanel(None)

# ── 1/2. the fields exist, are unbounded-below, and match each strategy's symmetry
check(panel.tanh_type_combo.count() == 2 and panel.geo_type_combo.count() == 2,
      "1. both strategies expose a mode combo")
for name in ("tanh_spacing_ends", "geo_spacing_start", "geo_spacing_end"):
    w = getattr(panel, name, None)
    check(isinstance(w, SciDoubleSpinBox), f"1. {name} is a SciDoubleSpinBox")
    if isinstance(w, SciDoubleSpinBox):
        w.setValue(3.5e-7)
        check(abs(w.value() - 3.5e-7) < 1e-18,
              f"1. {name} holds 3.5e-7 unclamped (a wall spacing)")
        w.setValue(0.0)
        check(w.text() == "unset", f"1. {name} shows 0 as 'unset'")

check(not hasattr(panel, "tanh_spacing_end"),
      "2. tanh has ONE end-spacing field — it is symmetric, so two would be a "
      "promise the distribution cannot keep")
check(hasattr(panel, "geo_spacing_start") and hasattr(panel, "geo_spacing_end"),
      "2. geometric has separate start/end fields (it IS asymmetric)")

# ── 3/4/5. the model<->form bridge ────────────────────────────────────────
from app.controllers.segment_distribution_ctrl import (  # noqa: E402
    SegmentDistributionControllerMixin as Dist,
)


class _Stub(Dist):
    """Just the parameter bridge; the rest of AppController is not needed."""

    class _MW:
        pass

    def __init__(self, panel):
        self.main_window = _Stub._MW()
        self.main_window.sidebar_view = panel


stub = _Stub(panel)


def write(strategy, mode, **vals):
    seg = SegmentModel(1, 0, 10)
    seg.strategy = strategy
    combo = panel.tanh_type_combo if strategy == "tanh" else panel.geo_type_combo
    combo.setCurrentText(mode)
    for attr, v in vals.items():
        getattr(panel, attr).setValue(v)
    stub._read_params_into_segment(seg)
    return dict(seg.parameters)


p = write("tanh", "By End Spacing", tanh_spacing_ends=2.5e-5)
check(p.get("spacing_start") == 2.5e-5 and "intensity" not in p,
      f"3. tanh By-End-Spacing writes spacing_start and NOT intensity ({p})")
check("spacing_end" not in p,
      "3. ...and never a second spacing key (symmetry)")

p = write("tanh", "By Intensity", tanh_intensity=3.5)
check(p.get("intensity") == 3.5 and "spacing_start" not in p,
      f"3. tanh By-Intensity writes intensity and NOT a spacing ({p})")

p = write("geometric", "By End Spacing", geo_spacing_start=4e-4, geo_spacing_end=2e-3)
check(p.get("spacing_start") == 4e-4 and p.get("spacing_end") == 2e-3
      and "ratio" not in p,
      f"3. geometric By-End-Spacing writes both spacings and NOT ratio ({p})")

p = write("geometric", "By Growth Ratio", geo_ratio=1.3, geo_ratio_end=1.0)
check(p.get("ratio") == 1.3 and "spacing_start" not in p,
      f"3. geometric By-Growth-Ratio writes ratio and NOT a spacing ({p})")

p = write("geometric", "By End Spacing", geo_spacing_start=0.0, geo_spacing_end=7e-4)
check("spacing_start" not in p and p.get("spacing_end") == 7e-4,
      f"4. an 'unset' end is OMITTED, not written as 0.0 ({p})")
p = write("tanh", "By End Spacing", tanh_spacing_ends=0.0)
check("spacing_start" not in p and "intensity" in p,
      f"4. tanh with an unset spacing falls back to intensity rather than "
      f"writing 0.0 ({p})")

for strategy, key, combo_attr, want_mode in (
        ("tanh", "spacing_start", "tanh_type_combo", "By End Spacing"),
        ("tanh", "spacing_end", "tanh_type_combo", "By End Spacing"),
        ("geometric", "spacing_end", "geo_type_combo", "By End Spacing"),
        ("tanh", "intensity", "tanh_type_combo", "By Intensity"),
        ("geometric", "ratio", "geo_type_combo", "By Growth Ratio")):
    seg = SegmentModel(1, 0, 10)
    seg.strategy = strategy
    seg.parameters = {"n_points": 60, key: 1.5e-4 if "spacing" in key else 2.0}
    stub._populate_form_from_segment(seg)
    got = getattr(panel, combo_attr).currentText()
    check(got == want_mode,
          f"5. a {strategy} config carrying '{key}' restores {want_mode!r} (got {got!r})")

# tanh restores the single field from EITHER key (older / hand-written configs).
seg = SegmentModel(1, 0, 10)
seg.strategy = "tanh"
seg.parameters = {"n_points": 60, "spacing_end": 8e-5}
stub._populate_form_from_segment(seg)
check(abs(panel.tanh_spacing_ends.value() - 8e-5) < 1e-15,
      "5. tanh restores its single field from spacing_end too")

# ── 6. the resampler actually reproduces the requested spacing ────────────
from app.models.project import ProjectModel  # noqa: E402
from app.services.env_setup import mesher_env  # noqa: E402
from app.utils import find_binary_executable  # noqa: E402

exe = find_binary_executable("surface_resampler")
geom = os.path.join(_REPO, "examples", "geometries", "naca0012.dat")
if not exe or not os.path.exists(geom):
    print("SKIP surface_resampler or naca0012.dat missing — solve accuracy "
          "not measured", flush=True)
else:
    n_src = len(np.loadtxt(geom))

    def resample(strategy, params):
        out = tempfile.mktemp(suffix="_endsp.dat")
        cfg = tempfile.mktemp(suffix="_endsp.json")
        try:
            pm = ProjectModel()
            pm.load_from_config({
                "input_file": geom, "output_file": out, "is_closed": True,
                "segments": [{"id": 1, "type": "file", "strategy": strategy,
                              "start_index": 0, "end_index": n_src - 1,
                              "parameters": params}]})
            pm.export_config(cfg)
            subprocess.run([exe, cfg], capture_output=True, text=True,
                           env=mesher_env(), timeout=120)
            if not os.path.exists(out):
                return None
            a = np.atleast_2d(np.loadtxt(out))
            if a.shape[0] < 3:
                return None
            d = np.linalg.norm(np.diff(a, axis=0), axis=1)
            return d
        finally:
            for f in (out, cfg):
                if os.path.exists(f):
                    os.remove(f)

    for want in (1e-3, 2e-4, 5e-5):
        d = resample("tanh", {"n_points": 200, "spacing_start": want})
        if d is None:
            check(False, f"6. tanh @ {want:g}: the resampler produced no usable output")
            continue
        err = abs(d[0] - want) / want
        check(err < 0.01,
              f"6. tanh reproduces a {want:.0e} end spacing (got {d[0]:.3e}, "
              f"err {err * 100:.2f}%)")
        check(abs(d[0] - d[-1]) / d[0] < 0.02,
              f"6. ...and both ends match, as symmetry requires "
              f"({d[0]:.3e} vs {d[-1]:.3e})")

    d = resample("geometric", {"n_points": 200, "spacing_start": 5e-4})
    if d is None:
        check(False, "6. geometric: the resampler produced no usable output")
    else:
        err = abs(d[0] - 5e-4) / 5e-4
        check(err < 0.01,
              f"6. geometric reproduces a one-sided 5e-4 start spacing "
              f"(got {d[0]:.3e}, err {err * 100:.2f}%)")

    # A request coarser than uniform must degenerate safely, not emit NaN.
    d = resample("tanh", {"n_points": 200, "spacing_start": 10.0})
    check(d is None or np.all(np.isfinite(d)),
          "6. an absurdly coarse request degenerates without producing NaN")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
