#!/usr/bin/env python3
"""A patch name nothing can resolve must SAY so, not fall silently onto a wall.

#92, blocked by #90. ``services/bnd_io.default_bc_flag_for_name`` documents its
fallback honestly — an unknown name becomes a slip wall for inviscid Euler and a
no-slip wall for viscous NS, "matching getPGrid's tolerant fallback". The
fallback is right: refusing to mesh, or refusing to solve, because a patch is
named something unexpected would be worse. What was wrong is that it was SILENT.
A user who typed ``far-feild``, or who used a name this repo has not enumerated,
got a solid wall where they meant an outflow, and the only symptom was a solution
that was quietly wrong.

getPGrid does warn on its own stdout when it does not know a name — that is how
#57 and #85 measured this at all, 288 warnings on one C-grid run — but that
warning is about getPGrid's table, not about the flag the run ends up using, and
it is buried in the converter's output rather than raised where the decision is
made. #91 then made the decision this repo's own: the derivation fills the table
the solver reads, so getPGrid's table (and its warning) is no longer what
decides. The one place that knows both facts is
``services/solver_bc_table.py``, and that is where this speaks from.

**The fallback itself is unchanged.** Check 5 pins the RESTRUCTURING against the
pre-#92 `bc_flag_for_patch`, over the same 96 name/assignment/solution-type
combinations ``test_solver_bc_table.py`` check 11 uses: #92 makes the fallback
audible, it does not make it a refusal.

**What check 5 does NOT pin, said plainly.** Its oracle calls the LIVE
``default_bc_flag_for_name``, so both sides move together and a change to the
name→flag MAPPING itself passes it. That is deliberate — a hand-copied
`_NAME_TO_FLAG` here would rot into a second source of truth — and the mapping is
pinned elsewhere, by ``test_pipeline_bc_from_mesh.py`` check 10, which reads
getPGrid's own ``getBCType`` C++ and compares all 25 tokens. What check 5 catches
is what #92 actually touched: the token choice moving into ``bc_token_for_patch``.
Measured: breaking the precedence fails it; mutating the fallback's own return
does not (checks 1, 2, 4, 6 and 8 catch that instead). #90's check 11 has the same
shape and the same limit.

Checks:
 1. the seam: ``unresolved_patches`` names the patch, the token really looked up,
    the flag really used and the segments carrying it — an unrecognised
    ASSIGNMENT is distinguishable from an unrecognised patch NAME, and a name
    several segments share is ONE entry rather than one per segment
 2. the message names the PATCH, the FLAG (number and label) and the FIX, and
    grades as WARNING through the real ``user_log.classify``
 3. a mesh whose names ALL resolve produces nothing, so the warning means
    something when it appears
 4. HEADLESS: ``derive_bc_definitions`` on a `.bnd` carrying an unrecognised
    name warns; the same `.bnd` with the name corrected says only what #91 said
 5. the fallback FLAGS are bit-identical to pre-#92, over 96 combinations
 6. GUI: the real AppController + solver panel, driven through
    ``detect_bc_from_mesh``, puts the same line into the user-log SERVICE — and
    says nothing for a mesh that resolves
 7. both hosts emit the SAME text, built once in the service; and the mapping's
    ``is_known_bc_name`` keeps ONE caller, like ``default_bc_flag_for_name``
 8. the OTHER GUI route — the resync that runs on entering Solver mode AND
    before a run — warns too, on EVERY entry rather than only the one where a
    row moved, and for an unresolvable patch name as well as an assignment

Run:  python3 tools/PreProcessor/tests/test_bc_name_unresolved.py
"""
import os
import sys
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


from app.models.solver_config import BC_FLAG_TO_LABEL                # noqa: E402
from app.services import user_log                                    # noqa: E402
from app.services.bnd_io import (default_bc_flag_for_name,           # noqa: E402
                                 is_known_bc_name)
from app.services.solver_bc_table import (bc_flag_for_patch,         # noqa: E402
                                          unresolved_patch_warnings,
                                          unresolved_patches)

tmp = tempfile.mkdtemp(prefix="hybmesh_bc_unresolved_")


def write_bnd(path, patches):
    """A STAR-CD `.bnd`: segment id is column 6, patch name column 8."""
    with open(path, "w", encoding="utf-8") as f:
        for i, (sid, name) in enumerate(patches, start=1):
            f.write(f"{i:>6}{i:>8}{i + 1:>8}{0:>8}{0:>8}{sid:>8}{0:>8}  {name}\n")
    return path


# The C-grid demo's eight patches with ONE typo'd — the reported shape of this
# bug: a name one letter away from a far field, silently solved as a wall.
_TYPO = [(1, "wall"), (2, "wall"), (3, "outlet"), (4, "outlet"),
         (5, "far-feild"), (6, "farfield"), (7, "farfield"), (8, "farfield")]
_CLEAN = [(sid, "farfield" if nm == "far-feild" else nm) for sid, nm in _TYPO]

# ── 1. the seam ──────────────────────────────────────────────────────────────
check(unresolved_patches(_TYPO) == [("far-feild", "far-feild", 2, [5])],
      f"1. the one patch that resolved to nothing is named, with the token "
      f"looked up, the flag the run really uses and the segment carrying it "
      f"({unresolved_patches(_TYPO)})")
check(unresolved_patches(_CLEAN) == [],
      f"1. …and the corrected mesh reports nothing ({unresolved_patches(_CLEAN)})")
check(unresolved_patches(_TYPO, euler=True) == [("far-feild", "far-feild", 0, [5])],
      f"1. …the flag follows the solution type, as the fallback does "
      f"({unresolved_patches(_TYPO, euler=True)})")
_asg = unresolved_patches([(1, "inlet")], {"inlet": "far-feild"})
check(_asg == [("inlet", "far-feild", 2, [1])],
      f"1. …and a patch whose MESH-GENERATOR ASSIGNMENT is the unknown token is "
      f"reported with both, since the patch name alone resolves fine ({_asg})")
check(unresolved_patches([(1, "inlet")], {"inlet": ""}) == []
      and unresolved_patches([(1, "inlet")], {"other": "far-feild"}) == [],
      "1. …an empty assignment is not an assignment, and an assignment for "
      "ANOTHER patch does not implicate this one")

_ALL_TYPO = [(sid, "far-feild") for sid, _ in _TYPO]
_grp = unresolved_patches(_ALL_TYPO)
check(_grp == [("far-feild", "far-feild", 2, [1, 2, 3, 4, 5, 6, 7, 8])],
      f"1. …and a name several segments share is ONE entry carrying them all, "
      f"not eight — four identical lines is the burial #92 exists to undo, and "
      f"the shipped C-grid really does name four patches `farfield` ({_grp})")

# ── 2. the message ───────────────────────────────────────────────────────────
_msgs = unresolved_patch_warnings(_TYPO)
check(len(_msgs) == 1 and len(unresolved_patch_warnings(_ALL_TYPO)) == 1,
      f"2. one line per unresolved patch NAME ({len(_msgs)})")
_m = _msgs[0] if _msgs else ""
check("far-feild" in _m and "segment 5" in _m,
      f"2. …it names the PATCH and the segment carrying it ({_m!r})")
check("segments 1, 2, 3, 4, 5, 6, 7, 8"
      in unresolved_patch_warnings(_ALL_TYPO)[0],
      f"2. …every segment when a name is shared, in one line "
      f"({unresolved_patch_warnings(_ALL_TYPO)})")
check("flag 2" in _m and BC_FLAG_TO_LABEL[2] in _m,
      f"2. …it names the FLAG it fell back to, by number and by label ({_m!r})")
check("Mesh Generator" in _m and "Boundary Conditions" in _m,
      f"2. …and it says what to do about it, naming both places the type can be "
      f"set ({_m!r})")
_lvl, _clean = user_log.classify(_m)
check(_lvl == "WARNING",
      f"2. …and the real user-log classifier grades it WARNING, not a muted INFO "
      f"and not an ERROR the run did not have ({_lvl}: {_clean[:60]!r})")

# ── 3. silence when everything resolves ──────────────────────────────────────
check(unresolved_patch_warnings(_CLEAN) == []
      and unresolved_patch_warnings([]) == []
      and unresolved_patch_warnings(_CLEAN, {"wall": "isothermal"}) == [],
      "3. a mesh whose names all resolve says nothing — including one whose "
      "Mesh-Generator assignments all resolve too")

# ── 4. the HEADLESS path ─────────────────────────────────────────────────────
from app.models.pipeline_config import PipelineConfig                # noqa: E402
from app.services.pipeline_bc_derive import derive_bc_definitions    # noqa: E402

_SCRIPT = os.path.join(_REPO, "config", "pipeline", "multiblock_cgrid_demo.json")
_pcfg = PipelineConfig.load_from_file(_SCRIPT)


def _derive(patches, name, group_bc=None):
    sc = _pcfg.build_solver_config(_REPO)
    sc.input_bnd_file = write_bnd(os.path.join(tmp, name), patches)
    lines = []
    n = derive_bc_definitions(sc, group_bc or {}, log=lines.append)
    return n, lines, sc


_n, _lines, _sc = _derive(_TYPO, "typo.bnd")
_warn = [x for x in _lines if "far-feild" in x and "WARNING" in x]
check(_n == 8 and len(_warn) == 1,
      f"4. the headless derivation warns about the patch it could not resolve — "
      f"the path where nobody is watching a table ({_lines})")
check({r["segment_no"]: r["bc_type"] for r in _sc.bc_definitions}[5] == 2,
      "4. …while still writing the wall it always wrote: audible, not refused")
_n2, _lines2, _ = _derive(_CLEAN, "clean.bnd")
check(_n2 == 8 and not [x for x in _lines2 if "WARNING" in x],
      f"4. …and the corrected mesh derives the same eight rows with no warning "
      f"at all ({_lines2})")

# ── 5. the fallback is UNCHANGED ─────────────────────────────────────────────
def _pre92_flag(name, group_bc, euler):
    """`solver_bc_table.bc_flag_for_patch` as of 566b8d0, before #92 split the
    token choice out of it. It calls the LIVE `default_bc_flag_for_name` on
    purpose, so this pins the PRECEDENCE and not the mapping — see the header."""
    assigned = (group_bc or {}).get(name)
    return default_bc_flag_for_name(assigned if assigned else name, euler)


_MATRIX = []
for _nm in ("inlet", "outlet", "wall", "symp", "s2d", "", "Mystery", "GEOM"):
    for _asg in (None, "", "wall", "inlet", "isothermal", "nonsense"):
        for _eu in (False, True):
            _MATRIX.append((_nm, {_nm: _asg} if _asg is not None else {}, _eu))
_bad = [(nm, g, eu, bc_flag_for_patch(nm, g, eu), _pre92_flag(nm, g, eu))
        for nm, g, eu in _MATRIX
        if bc_flag_for_patch(nm, g, eu) != _pre92_flag(nm, g, eu)]
check(not _bad and len(_MATRIX) == 96,
      f"5. the RESTRUCTURING is bit-identical to pre-#92 over {len(_MATRIX)} "
      f"name/assignment/solution-type combinations — the mapping itself is "
      f"pinned by test_pipeline_bc_from_mesh.py check 10, not here ({_bad[:3]})")

# ── 6. the GUI host, through the real controller ─────────────────────────────
import threading                                                     # noqa: E402


def _watchdog():
    print("FAIL watchdog: AppController blocked >60s", flush=True)
    os._exit(99)


_wd = threading.Timer(60, _watchdog)
_wd.daemon = True
_wd.start()

from PyQt6.QtWidgets import QApplication                             # noqa: E402
from app.controller import AppController                             # noqa: E402

_app = QApplication.instance() or QApplication([])
_c = AppController()
_panel = _c.main_window.solver_config_panel
_panel.auto_link_mesh.setChecked(False)      # use the .bnd path we set, not a run's

_seen: list[str] = []
_sink = _seen.append
user_log.add_sink(_sink)


def _detect(patches, name):
    _panel.input_bnd_file.setText(write_bnd(os.path.join(tmp, name), patches))
    del _seen[:]
    _c.detect_bc_from_mesh()
    return list(_seen)


_gui_typo = _detect(_TYPO, "gui_typo.bnd")
_gui_warn = [x for x in _gui_typo if "far-feild" in x and "WARNING" in x]
check(len(_gui_warn) == 1,
      f"6. the GUI's Detect-from-Mesh puts the warning into the user-log SERVICE "
      f"({[x[:70] for x in _gui_typo]})")
check(_panel.get_config().bc_definitions[4]["bc_type"] == 2,
      "6. …and the table still shows the wall it always showed")
_gui_clean = _detect(_CLEAN, "gui_clean.bnd")
check(not [x for x in _gui_clean if "WARNING" in x],
      f"6. …and a mesh whose names all resolve is silent in the GUI too "
      f"({[x[:70] for x in _gui_clean]})")

# ── 7. one text, one caller ──────────────────────────────────────────────────
check(_gui_warn and _warn and _gui_warn[0] == _warn[0],
      f"7. both hosts say the SAME words, because the service builds them "
      f"({_gui_warn[:1]} vs {_warn[:1]})")
_gui_app = os.path.join(_GUI, "app")
_callers, _views = [], []
for _dirpath, _dirs, _files in os.walk(_gui_app):
    for _fn in sorted(_files):
        if not _fn.endswith(".py"):
            continue
        _full = os.path.join(_dirpath, _fn)
        _rel = os.path.relpath(_full, _gui_app).replace(os.sep, "/")
        if _rel == "services/bnd_io.py":
            continue                      # where the mapping is DEFINED
        with open(_full, encoding="utf-8", errors="replace") as _f:
            _txt = _f.read()
        if "is_known_bc_name" in _txt:
            _callers.append(_rel)
            if _rel.startswith("views/"):
                _views.append(_rel)
check(_callers == ["services/solver_bc_table.py"] and not _views,
      f"7. …and `is_known_bc_name` keeps ONE caller — the derivation service — "
      f"exactly like the flag it qualifies (callers={_callers})")
check(is_known_bc_name("FarField") and not is_known_bc_name("far-feild")
      and not is_known_bc_name("") and not is_known_bc_name(None),
      "7. …case-insensitive like the mapping it reads, and an unnamed patch is "
      "not 'known'")

# ── 8. the OTHER GUI route into the same silence ─────────────────────────────
# `resync_solver_bc_from_group` runs on entering Solver mode and before a run, so
# an assignment changed AFTER the table was seeded lands its flag without anyone
# clicking Detect. An assignment naming a token nobody knows lands a wall there
# too, and that is the same silence.
_detect(_CLEAN, "gui_resync.bnd")            # a table that matches the mesh
_c.global_mesh_config.group_bc = {"outlet": "nonsense"}
del _seen[:]
_c.resync_solver_bc_from_group()
_res_warn = [x for x in _seen if "nonsense" in x and "WARNING" in x]
check(len(_res_warn) == 1 and "segments 3, 4" in _res_warn[0],
      f"8. resyncing from a Mesh-Generator assignment nobody can resolve warns "
      f"once, naming both segments it hits ({[x[:80] for x in _seen]})")
check([r["bc_type"] for r in _panel.get_config().bc_definitions][2:4] == [2, 2],
      f"8. …and the wall it lands is the wall it always landed "
      f"({[r['bc_type'] for r in _panel.get_config().bc_definitions]})")
del _seen[:]
_c.resync_solver_bc_from_group()
check([x for x in _seen if "nonsense" in x and "WARNING" in x],
      f"8. …and AGAIN on the next entry into Solver mode, when the table already "
      f"matches and no row moves: a patch that resolves to nothing is just as "
      f"wrong the second time, and this runs before a RUN — the last moment the "
      f"warning can still reach anyone ({[x[:80] for x in _seen]})")
_c.global_mesh_config.group_bc = {"outlet": "farfield"}
_detect(_CLEAN, "gui_resync2.bnd")
del _seen[:]
_c.resync_solver_bc_from_group()
check(not [x for x in _seen if "WARNING" in x],
      f"8. …while assignments that all resolve stay silent on that route too "
      f"({[x[:80] for x in _seen]})")
# The fix the message RECOMMENDS must stop the message. `resync_bc_types_from_group`
# preserves a hand-picked flag on an unassigned row, so the derivation's answer and
# the table's can differ — and it is the table the run uses.
_c.global_mesh_config.group_bc = {}
_detect(_TYPO, "gui_manualfix.bnd")
_combo = _panel.bc_table.cellWidget(4, 2)          # segment 5, the `far-feild` row
_combo.setCurrentIndex(_combo.findData(1))         # set it by hand, as the message says
del _seen[:]
_c.resync_solver_bc_from_group()
check(not [x for x in _seen if "WARNING" in x],
      f"8. …and setting the type by hand in the solver's BC table — the fix the "
      f"message names — stops it: the row no longer carries the fallback, so "
      f"there is nothing left to warn about ({[x[:80] for x in _seen]})")
check([r["bc_type"] for r in _panel.get_config().bc_definitions][4] == 1,
      "8. …and the hand-picked flag survives the resync, as it always has")

_detect(_TYPO, "gui_resync3.bnd")
del _seen[:]
_c.resync_solver_bc_from_group()
check([x for x in _seen if "far-feild" in x and "WARNING" in x],
      f"8. …and with NO assignments at all, an unresolvable PATCH NAME is "
      f"reported on this route too, not only by Detect ({[x[:80] for x in _seen]})")
user_log.remove_sink(_sink)

print()
if _FAILS:
    print(f"{len(_FAILS)} FAILED:")
    for m in _FAILS:
        print("  - " + m)
print(f"{len(_FAILS)} failure(s)" if _FAILS else "all checks passed")
os._exit(1 if _FAILS else 0)
