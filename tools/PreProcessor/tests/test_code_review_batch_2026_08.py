#!/usr/bin/env python3
"""Regression tests for the 2026-08 code-review batch.

One check per defect the review found, so none of them can quietly come back:

1. `cad_cancel_btn` / `progress_bar` are actually POSITIONED in the CAD toolbar
   grid (they were visible-but-unplaced, painting over Undo at (0,0)).
2. Every `_run_backend` caller gets the running-state UI cleared — the pipeline
   path used to leave Preview/Apply/Save disabled for the rest of the session.
3. The shared progress bar is owner-guarded, so a finishing run cannot hide or
   reset a bar another (concurrent) stage is driving.
4. `is_auto_output_name` only matches names this app would have generated, so a
   user's own path under results/meshes/ survives set_config.
5. `clamp_case_name` keeps the auto case name inside NAME_MAX.
6. `_resolve_export_path` never defaults into the session temp dir (rmtree'd
   at exit) when no output filename is set.
7. `load_result` does not open a blocking modal during a batch pipeline run.
8. Saving a workspace preserves the file's permissions (mkstemp forces 0600).

Run:  python3 tools/PreProcessor/tests/test_code_review_batch_2026_08.py
(the script forces the offscreen platform itself, so the env var is optional).
"""
import os
import sys
import threading
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >60s (modal-dialog regression?)", flush=True)
    os._exit(99)


_wd = threading.Timer(60, _watchdog)
_wd.daemon = True
_wd.start()

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.models.mesh_config import MeshConfig  # noqa: E402

# ── 4. is_auto_output_name is a narrow match ───────────────────────────────
AUTO_CASES = [
    ("", True),
    ("results/meshes/mesh_naca0012.vtk", True),          # legacy flat
    ("results/meshes/naca0012/mesh_naca0012.vtk", True),  # per-case
    ("results/meshes/naca0012/mesh_naca0012.*", True),   # panel's ".*" form
    ("results\\meshes\\naca0012\\mesh_naca0012.vtk", True),
    ("results/meshes/run_alpha5/mesh_fine.vtk", False),  # USER name (regression)
    ("results/meshes/naca0012/fine.vtk", False),
    ("results/meshes/a/b/mesh_b.vtk", False),
    ("my_meshes/mesh_x.vtk", False),
]
bad = [n for n, want in AUTO_CASES if MeshConfig.is_auto_output_name(n) != want]
check(not bad, f"is_auto_output_name classifies {len(AUTO_CASES)} names correctly"
               + (f" (wrong: {bad})" if bad else ""))
check(all(MeshConfig.is_auto_output_name(MeshConfig.auto_output_name(b))
          for b in ([], ["a/x.dat"], ["a/x.dat", "b/y.dat"])),
      "auto_output_name round-trips as auto")

# ── 5. clamp_case_name keeps the path component writable ───────────────────
many = [f"a/30p30n_jaxa_element{i}_resampled.dat" for i in range(12)]
case = MeshConfig.auto_case_name(many)
check(len(case) <= MeshConfig.CASE_NAME_MAX_LEN,
      f"many-body case name clamped to {len(case)} chars")
auto_path = MeshConfig.auto_output_name(many)
longest = max(len(c.encode()) for c in auto_path.split("/"))
check(longest < 255, f"longest path component is {longest} bytes (< NAME_MAX)")
check(MeshConfig.auto_case_name(many) == MeshConfig.auto_case_name(many),
      "clamping is deterministic")
check(MeshConfig.auto_case_name(many[:6]) != case,
      "different boundary sets clamp to different case names")

from app.controller import AppController  # noqa: E402

c = AppController()
mw = c.main_window

# ── 1. CAD toolbar places Cancel and the progress bar ──────────────────────
# adjust_toolbar_layout() only places widgets that report isVisible(), which is
# False for every child while the window itself is hidden — so the window must be
# shown (cheap on the offscreen platform) for this to test anything at all.
mw.show()
mw.mode_combo.setCurrentIndex(0)          # CAD mode
app.processEvents()


def _in_layout(widget):
    lay = mw.tb_layout
    return any(lay.itemAt(i).widget() is widget for i in range(lay.count()))


check(_in_layout(mw.cad_cancel_btn),
      "cad_cancel_btn is positioned in the CAD toolbar grid")
mw.claim_progress("cad")                  # bar is only laid out while visible
mw.adjust_toolbar_layout()
check(_in_layout(mw.progress_bar),
      "progress_bar is positioned in the CAD toolbar grid")

# ── 3. progress-bar ownership ──────────────────────────────────────────────
mw.claim_progress("mesh", determinate=True)   # a later run takes over
mw.set_progress("cad", 5)                     # stale stage must not drive it
check(mw.progress_bar.value() != 5, "a non-owner cannot set the progress value")
mw.release_progress("cad")                    # the CAD run finishing
check(mw.progress_bar.isVisible(),
      "a finishing run does not hide another stage's progress bar")
check(mw.progress_bar.maximum() == 100,
      "a finishing run does not reset another stage's progress range")
mw.set_progress("mesh", 42)
check(mw.progress_bar.value() == 42, "the owner can drive the progress value")
mw.release_progress("mesh")
check(not mw.progress_bar.isVisible(), "the owner's release hides the bar")

# ── 2. every _run_backend caller gets the UI restored ──────────────────────
sb = mw.sidebar_view
c._set_backend_running_ui(True)
check(not sb.preview_btn.isEnabled() and mw.cad_cancel_btn.isEnabled(),
      "running state disables Preview and enables Cancel")
# The pipeline's on_finish never restored this; _on_backend_finished_ui does.
c._on_backend_finished_ui()
check(sb.preview_btn.isEnabled() and sb.save_btn.isEnabled()
      and sb.file_preview_btn.isEnabled(),
      "finishing restores Preview / Apply / Save for ANY caller")
check(not mw.cad_cancel_btn.isEnabled(), "finishing disables Cancel")

# ── 6. export path never defaults into the session temp dir ────────────────
temp_vtk = os.path.join(c.temp_dir, "global_mesh.vtk")
c.global_mesh_config = MeshConfig()
c.global_mesh_config.geom_files = [os.path.join(_REPO, "examples", "geometries",
                                                "naca0012.dat")]
c.global_mesh_config.output_filename = ""
try:
    mw.mesh_config_panel.set_config(c.global_mesh_config)
except Exception:
    pass
resolved = c._resolve_export_path(temp_vtk, ".vrt")
check(not c._is_session_temp_path(resolved),
      f"export path escapes the session temp dir ({resolved})")
check(os.path.join("results", "meshes") in resolved,
      "export path lands under results/meshes/")

# ── 7. no blocking modal on the batch pipeline path ────────────────────────
import app.utils as _utils  # noqa: E402

_shown = []
_orig_warn = _utils.report_warning
_utils.report_warning = lambda *a, **k: _shown.append(a)
try:
    bogus = os.path.join(c.temp_dir, "not_a_result.dat")
    with open(bogus, "w") as f:
        f.write("this is not a tecplot file\n")
    c._pipeline_running = True
    c.load_result(bogus)
    check(not _shown, "load_result stays dialog-free during a pipeline run")
    c._pipeline_running = False
    c.load_result(bogus)
    check(True, "load_result outside a pipeline does not crash")
finally:
    _utils.report_warning = _orig_warn

# ── 8. saving a workspace preserves file permissions ───────────────────────
ws = os.path.join(c.temp_dir, "perm_check.hws")
with open(ws, "w") as f:
    f.write("{}")
os.chmod(ws, 0o644)
c._write_workspace_file(ws)
mode = os.stat(ws).st_mode & 0o777
check(mode == 0o644, f"workspace save preserves an existing mode (got {oct(mode)})")

fresh = os.path.join(c.temp_dir, "fresh_check.hws")
c._write_workspace_file(fresh)
umask = os.umask(0)
os.umask(umask)
fresh_mode = os.stat(fresh).st_mode & 0o777
check(fresh_mode == (0o666 & ~umask),
      f"a new workspace gets the umask default, not 0600 (got {oct(fresh_mode)})")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
