#!/usr/bin/env python3
"""One data-flow direction for stage configuration (finding N8, architectural half).

Each stage's settings existed twice — widgets on a panel, and a model the controller
holds — and the model was only refreshed when the stage RAN. In between it lagged, and
every workaround for the lag was a different partial copy: one call site copied all but a
hand-kept exclusion set, another copied a different three fields, the solver model was
never refreshed at all. One quantity, several sources of truth.

What this pins down:
 1. PRESERVED_FIELDS equals what the panel's own get_config does NOT assign — proved by
    parsing the panel sources with ast, so a model field added later without a widget
    fails the build instead of silently going stale or silently being wiped.
 2. A user edit reaches the model immediately (the staleness class is closed), including
    the exact case that motivated this: typing Unit Re on the Solver panel.
 3. Preserved fields SURVIVE a sync — notably the solver's length_unit, which has no
    widget, so a wholesale copy would reset it and take Linf (and the Reynolds number)
    with it.
 4. Population does NOT sync, and the guard is the PANEL's own flag: a direct
    set_config that forgets push_panel_config must cost at most a spurious undo step,
    never a corrupted model. Verified by calling set_config directly.
 5. The population flag is exception-safe — a stuck flag would silently stop syncing
    forever, which is worse than the staleness this replaces.
 6. extra_preserve still lets a mid-mutation caller win (the geometry-list operations).
 7. The old duplicated exclusion lists are gone from the call sites.

Run:  python3 tools/PreProcessor/tests/test_panel_model_sync.py
"""
import dataclasses
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
    print("FAIL watchdog: blocked >180s", flush=True)
    os._exit(99)


_wd = threading.Timer(180, _watchdog)
_wd.daemon = True
_wd.start()

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.controllers.panel_sync_ctrl import (  # noqa: E402
    PANEL_MODELS, PRESERVED_FIELDS,
)
from app.models.mesh_config import MeshConfig  # noqa: E402
from app.models.solver_config import SolverConfig  # noqa: E402
from app.models.stl3d_config import Stl3dConfig  # noqa: E402
from app.services.config_ownership import unauthored_fields  # noqa: E402

_MODELS = {
    "mesh_config_panel": MeshConfig,
    "solver_config_panel": SolverConfig,
    "stl3d_config_panel": Stl3dConfig,
}

# ── 1. the declared ownership matches the code ────────────────────────────
for panel_attr, model_cls in _MODELS.items():
    derived = unauthored_fields(panel_attr, model_cls)
    declared = set(PRESERVED_FIELDS.get(panel_attr, frozenset()))
    check(derived == declared,
          f"1. {panel_attr}: PRESERVED_FIELDS equals what get_config does not assign "
          f"(would be wiped: {sorted(derived - declared)}; "
          f"needlessly preserved: {sorted(declared - derived)})")

# A sanity check on the extractor itself: if it found nothing, every field would look
# unauthored and the gate above would pass while proving nothing. That failure mode
# already happened once (a wrong source root made every glob match zero files).
from app.services.config_ownership import authored_fields  # noqa: E402

for panel_attr, model_cls in _MODELS.items():
    n = len(authored_fields(panel_attr)
            & {f.name for f in dataclasses.fields(model_cls)})
    check(n > 8,
          f"1. the ast extractor actually finds {panel_attr}'s assignments ({n}) — a "
          f"silent zero would make the gate above vacuous")

# ── 2/3. edits reach the model; preserved fields survive ──────────────────
from app.controller import AppController  # noqa: E402

ctl = AppController()
mw = ctl.main_window

# Both names in every PANEL_MODELS pair must actually resolve. A renamed panel or model
# attribute would make sync_panel_to_model return False for ever — no error, no log, the
# model simply never updates again.
for panel_attr, model_attr in PANEL_MODELS:
    check(getattr(mw, panel_attr, None) is not None
          and getattr(ctl, model_attr, None) is not None,
          f"2. PANEL_MODELS pair resolves: {panel_attr} / {model_attr}")

sp = mw.solver_config_panel
mp = mw.mesh_config_panel

# ── 9. startup: the models' defaults survive being read back ──────────────
# Must run before any edit below. Making the panel authoritative gave the pair a
# starting-point problem: a panel is built holding Qt's un-set widget values (0, or
# the spin box floor), and every push_panel_config ends by re-reading ALL panels, so
# the first push (init_solver's) read the untouched Mesh panel into the mesh model.
# The GUI's real defaults silently became BL layers 0 (no boundary layer grown at
# all), growth rate 1.001, Gmsh MeshAdapt, and the outer BCs all inlet. The fix is
# push_models_to_panels() before anything reads the other way; this pins it.
from app.models.mesh_config import MeshConfig as _MC  # noqa: E402
from app.models.solver_config import SolverConfig as _SC  # noqa: E402
from app.models.stl3d_config import Stl3dConfig as _S3  # noqa: E402

_solver_dflt = _SC()
_solver_dflt.ensure_default_binaries()
#: Fields whose startup value is deliberately not the dataclass default.
_STARTUP_OK = {
    # The concave combo offers method 5 only (the merge default is CLI-side), and the
    # export name is derived from the loaded geometry, not a fixed string.
    "global_mesh_config": {"bl_concave_method", "output_filename"},
    "global_solver_config": set(),
    "global_stl3d_config": set(),
}
for _model_attr, _dflt in (("global_mesh_config", _MC()),
                           ("global_solver_config", _solver_dflt),
                           ("global_stl3d_config", _S3())):
    _live = getattr(ctl, _model_attr)
    _lost = {k: (v, getattr(_live, k)) for k, v in vars(_dflt).items()
             if k not in _STARTUP_OK[_model_attr] and getattr(_live, k) != v}
    check(not _lost, f"9. {_model_attr} still holds its defaults after startup "
                     f"(clobbered: {sorted(_lost)[:6]})")

_gm = ctl.global_mesh_config
check((_gm.bl_layers, _gm.bl_growth_rate, _gm.bl_transition_layers) == (5, 1.2, 3),
      f"9. ...naming the ones that were lost: BL layers/growth/transition = "
      f"{_gm.bl_layers}/{_gm.bl_growth_rate}/{_gm.bl_transition_layers}, not 0/1.001/0")
check((_gm.gmsh_algorithm, _gm.gmsh_optimize, _gm.bc_ymax) == (6, 1, "outlet"),
      f"9. ...and Gmsh Frontal-Delaunay + optimize + outlet BCs survive "
      f"({_gm.gmsh_algorithm}, {_gm.gmsh_optimize}, {_gm.bc_ymax})")
check(not ctl.project_is_dirty(),
      "9. and a freshly started app is not already 'modified' (the baseline is taken "
      "from panels that agree with their models)")

check(ctl.global_solver_config.fs_unit_re != 2.2853e5,
      "2. (precondition) the model does not already hold the probe value")
sp.fs_unit_re.setValue(2.2853e5)
check(ctl.global_solver_config.fs_unit_re == 2.2853e5,
      f"2. typing Unit Re reaches global_solver_config immediately — this exact field "
      f"was read stale while the panel showed the real value "
      f"({ctl.global_solver_config.fs_unit_re})")

mp.domain_x_min.setValue(-7.25)
check(ctl.global_mesh_config.domain_x_min == -7.25,
      f"2. a mesh spin-box edit reaches global_mesh_config "
      f"({ctl.global_mesh_config.domain_x_min})")

sp.num_half_iter.setValue(4321)
check(ctl.global_solver_config.num_half_iter == 4321,
      "2. so does a solver iteration count (the panel has no change signal of its own; "
      "widget introspection is what covers it)")

ctl.global_solver_config.length_unit = "mm"
ctl.global_solver_config.length_unit_metres = 1.0e-3
ctl.global_solver_config.linf = 1.0e-3
sp.fs_mach.setValue(0.42)
check(ctl.global_solver_config.length_unit == "mm",
      f"3. the solver's length_unit SURVIVES a sync — the panel has no widget for it, "
      f"so a wholesale copy would reset it and take Linf with it "
      f"({ctl.global_solver_config.length_unit})")
check(ctl.global_solver_config.linf == 1.0e-3,
      f"3. and Linf is RE-DERIVED from that preserved unit rather than taken from the "
      f"widget: linf has a widget, the unit does not, so a plain copy would leave "
      f"length_unit=mm beside linf=1 — an inconsistency the sync itself created "
      f"({ctl.global_solver_config.linf})")
ctl.global_solver_config.linf_from_unit = False
ctl.global_solver_config.linf = 0.0254
sp.linf_from_unit.setChecked(False)
sp.linf.setValue(0.0254)
sp.fs_mach.setValue(0.43)
check(ctl.global_solver_config.linf == 0.0254,
      f"3. with linf_from_unit OFF the widget IS the authority and is not re-derived — "
      f"that is the whole point of the manual mode ({ctl.global_solver_config.linf})")
ctl.global_solver_config.linf_from_unit = True
sp.linf_from_unit.setChecked(True)

ctl.global_mesh_config.bc_geom = "symmetry"
mp.domain_x_max.setValue(9.5)
check(ctl.global_mesh_config.bc_geom == "symmetry",
      f"3. bc_geom survives (owned by the BC dialogs, not by a panel field) "
      f"({ctl.global_mesh_config.bc_geom})")

# ── 4. population must not sync ───────────────────────────────────────────
cfg = MeshConfig()
cfg.bl_layers = 23
cfg.domain_x_min = -17.5
ctl.global_mesh_config = cfg
# Deliberately NOT through push_panel_config: this is the mistake the guard has to
# tolerate. Before the panel owned the flag, this corrupted the model with a
# half-populated form and broke three existing tests.
mp.set_config(cfg)
check(ctl.global_mesh_config.bl_layers == 23
      and ctl.global_mesh_config.domain_x_min == -17.5,
      f"4. a DIRECT set_config (no push_panel_config) leaves the model intact — the "
      f"guard is the panel's own flag, not the caller's discipline "
      f"({ctl.global_mesh_config.bl_layers}, {ctl.global_mesh_config.domain_x_min})")

cfg2 = SolverConfig()
cfg2.num_half_iter = 999
ctl.global_solver_config = cfg2
sp.set_config(cfg2)
check(ctl.global_solver_config.num_half_iter == 999,
      "4. same for the solver panel")

s3 = Stl3dConfig()
s3.case_name = "guarded_case"
ctl.global_stl3d_config = s3
mw.stl3d_config_panel.set_config(s3)
check(ctl.global_stl3d_config.case_name == "guarded_case",
      "4. same for the IB panel")

# ── 5. the flag is exception-safe ─────────────────────────────────────────
for panel, name in ((mp, "mesh"), (sp, "solver"), (mw.stl3d_config_panel, "IB")):
    check(getattr(panel, "_loading", None) is False,
          f"5. the {name} panel's population flag is cleared after set_config")

boom = MeshConfig()
orig = mp._set_config_body


def _raise(_cfg):
    raise RuntimeError("simulated failure mid-population")


mp._set_config_body = _raise
try:
    mp.set_config(boom)
except RuntimeError:
    pass
finally:
    mp._set_config_body = orig
check(mp._loading is False,
      "5. an exception mid-population still clears the flag — a stuck flag would stop "
      "the panel syncing FOREVER, silently, which is worse than the staleness this "
      "whole change replaces")
mp.domain_y_min.setValue(-3.75)
check(ctl.global_mesh_config.domain_y_min == -3.75,
      "5. ...and syncing still works afterwards")

# ── 6. extra_preserve ─────────────────────────────────────────────────────
ctl.global_mesh_config.geom_files = ["/kept/by/the/layer/op.dat"]
ctl.global_mesh_config.group_bc = {"patch": "inlet"}
changed = ctl.sync_panel_to_model(
    "mesh_config_panel", extra_preserve=("geom_files", "geom_roles", "group_bc"))
check(ctl.global_mesh_config.geom_files == ["/kept/by/the/layer/op.dat"]
      and ctl.global_mesh_config.group_bc == {"patch": "inlet"},
      "6. extra_preserve lets a mid-mutation caller win for its own fields, without "
      "that claim being confused with 'the panel cannot author this'")
check(isinstance(changed, bool), "6. sync reports whether anything changed")

# ── 7. the duplicated exclusion lists are gone ────────────────────────────
layers = open(os.path.join(_GUI, "app", "controllers", "mesh_layers_ctrl.py"),
              encoding="utf-8").read()
check('owned = {"geom_files"' not in layers,
      "7. mesh_layers_ctrl no longer keeps its own copy of the preserved-field list "
      "(two copies is how they drifted apart)")
check("sync_panel_to_model(" in layers,
      "7. ...it delegates to the shared sync instead")
check("except Exception:" not in layers.split("_sync_global_scalars_from_panel")[-1][:900],
      "7. and its silent `except Exception: return` around the panel read is gone")

ctrl_src = open(os.path.join(_GUI, "app", "controller.py"), encoding="utf-8").read()
check("gmc.geom_roles = dict(" not in ctrl_src,
      "7. handle_mesh_config_changed no longer copies a hand-picked field subset")

# ── 8. workspace save no longer loses unauthored fields ───────────────────
# The old code serialized panel.get_config() directly (to avoid stale models), which
# silently reset every field the panel does not author. Real losses, both verified
# before the fix: bc_geom symmetry -> wall, and a millimetre solver config -> metres.
ctl.global_mesh_config.bc_geom = "symmetry"
ctl.global_solver_config.length_unit = "mm"
ctl.global_solver_config.length_unit_metres = 1.0e-3
ctl.global_solver_config.linf_from_unit = True
state = ctl._collect_project_state()
check(state["mesh_config"].get("bc_geom") == "symmetry",
      f"8. a saved workspace keeps bc_geom instead of resetting it to the dataclass "
      f"default ({state['mesh_config'].get('bc_geom')})")
check(state["solver_config"].get("length_unit") == "mm"
      and state["solver_config"].get("linf") == 1.0e-3,
      f"8. ...and keeps the solver's length unit, so Linf still means what it says "
      f"({state['solver_config'].get('length_unit')}, "
      f"{state['solver_config'].get('linf')})")
mp.bl_layers.setValue(31)
check(ctl._collect_project_state()["mesh_config"].get("bl_layers") == 31,
      "8. while STILL capturing an edit made without ever running the stage — the "
      "property the panel-reading workaround existed for")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
