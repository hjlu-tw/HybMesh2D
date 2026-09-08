#!/usr/bin/env python3
"""The solver BC table is DERIVED by a service, not by the panel that shows it.

#90. The chain from a meshed patch to the solver's ``.bc.def`` was Qt-free at
every step but one: ``services/bnd_io.read_bnd_segments`` reads the patches,
``services/bnd_io.default_bc_flag_for_name`` mirrors getPGrid's ``getBCType``
name→flag mapping, ``SolverConfig.bc_definitions`` is a plain model field and
``services/solver_case.py`` writes it out for BOTH hosts. But the only thing that
POPULATED ``bc_definitions`` read the Qt table, and the only caller of
``default_bc_flag_for_name`` was a panel VIEW — so the mapping was a service
while the derivation that uses it was a widget.

``services/solver_bc_table.py`` is that derivation, given a home beside the
mapping — the same seam this repo took for the pipeline stage set and the IB
hand-off. **This ticket changes no behaviour**, which is why the panel is driven
here as well as the service: the claim is checkable only if both are measured.

The oracle in check 11 is the pre-#90 inline code, quoted from
``solver_config_bc_mixin.py`` as it stood at ``fca0997``. It is a second copy of
the rule ON PURPOSE and only here: a refactor that says "same answers" needs an
independent statement of what the old answers were, and a test that re-derives
them from the new service would agree with itself.

Checks:
 1. the service is Qt-free — imported AND CALLED in a subprocess that never
    loads PyQt6, with no QApplication anywhere
 2. an explicit ``group_bc`` assignment beats the guess from the patch name
 3. …and with no assignment, the name decides
 4. an unknown name falls back to a wall, by solution type (2 viscous / 0 euler)
 5. an assignment naming an unknown token gets that SAME fallback — the
    assignment is honoured as a name, not silently ignored in favour of the patch
 6. an EMPTY assignment is not an assignment: the name decides again
 7. the rows are ``bc_definitions`` rows — segment id, name preserved as the
    grouping label, empty ``values`` — in the patch order given
 8. the override map is keyed by ROW INDEX and holds ONLY the patches carrying an
    explicit assignment, so a manual tweak on an unassigned row survives
 9. the PANEL produces exactly the service's rows, read back through the real
    ``get_config()`` — same segments, same flags, same names
10. …and ``resync_bc_types_from_group`` applies exactly the service's overrides,
    returning the number of rows that really changed
11. the service agrees with the pre-#90 inline implementation over a matrix of
    patch/assignment/solution-type combinations

Run:  python3 tools/PreProcessor/tests/test_solver_bc_table.py
"""
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


# ── 1. Qt-free, in a subprocess ───────────────────────────────────────────────
# In-process the answer is always "PyQt6 is loaded" once anything else imports it
# (test_qt_free_seam.py measured that), and this file builds a real panel below.
_PROBE = (
    "import sys, json\n"
    "from app.services.solver_bc_table import bc_definitions_for_patches\n"
    "rows = bc_definitions_for_patches([(1, 'inlet'), (2, 'geom')],\n"
    "                                  group_bc={'geom': 'wall'}, euler=False)\n"
    "print(json.dumps({'qt': [m for m in sys.modules if m.startswith('PyQt')],\n"
    "                  'rows': rows}))\n"
)
_proc = subprocess.run([sys.executable, "-c", _PROBE], cwd=_GUI,
                       capture_output=True, text=True)
_out = _proc.stdout.strip().splitlines()[-1] if _proc.stdout.strip() else ""
try:
    import json
    _probe = json.loads(_out)
except ValueError:
    _probe = None
check(_proc.returncode == 0 and _probe is not None
      and _probe["qt"] == []
      and _probe["rows"] == [
          {"segment_no": 1, "bc_type": 5, "values": "", "name": "inlet"},
          {"segment_no": 2, "bc_type": 2, "values": "", "name": "geom"}],
      f"1. the derivation runs with no QApplication and loads no PyQt6 "
      f"(rc={_proc.returncode}, qt={_probe['qt'] if _probe else '?'}, "
      f"stderr={_proc.stderr.strip()[-200:]!r})")

from app.services.solver_bc_table import (                          # noqa: E402
    bc_definitions_for_patches, bc_flag_for_patch, bc_flag_overrides,
)
from app.services.bnd_io import default_bc_flag_for_name            # noqa: E402

# ── 2-6. the precedence rule, one function ───────────────────────────────────
check(bc_flag_for_patch("wall", {"wall": "inlet"}) == 5
      and default_bc_flag_for_name("wall") == 2,
      "2. an explicit group_bc assignment beats the patch name "
      f"(wall+{{wall:inlet}} -> {bc_flag_for_patch('wall', {'wall': 'inlet'})}, "
      f"name alone -> {default_bc_flag_for_name('wall')})")
check(bc_flag_for_patch("outlet", {"other": "inlet"}) == 1,
      "3. with no assignment for THIS patch, the name decides "
      f"({bc_flag_for_patch('outlet', {'other': 'inlet'})})")
check(bc_flag_for_patch("mystery") == 2
      and bc_flag_for_patch("mystery", euler=True) == 0,
      "4. an unknown name falls back to a wall by solution type "
      f"(viscous {bc_flag_for_patch('mystery')}, euler "
      f"{bc_flag_for_patch('mystery', euler=True)})")
check(bc_flag_for_patch("inlet", {"inlet": "mystery"}) == 2
      and bc_flag_for_patch("inlet", {"inlet": "mystery"}, euler=True) == 0,
      "5. an assignment naming an unknown token takes the SAME fallback — it is "
      f"honoured as a name, not dropped back to the patch's own "
      f"({bc_flag_for_patch('inlet', {'inlet': 'mystery'})}, not "
      f"{default_bc_flag_for_name('inlet')})")
check(bc_flag_for_patch("inlet", {"inlet": ""}) == 5
      and bc_flag_for_patch("inlet", {"inlet": None}) == 5,
      "6. an empty assignment is not an assignment: the name decides "
      f"({bc_flag_for_patch('inlet', {'inlet': ''})})")

# ── 7. the rows ──────────────────────────────────────────────────────────────
_PATCHES = [(3, "geom"), (1, "XMin"), (2, "outlet"), (7, "")]
_GROUP = {"geom": "isothermal", "XMin": "farfield"}
_rows = bc_definitions_for_patches(_PATCHES, group_bc=_GROUP, euler=False)
check([r["segment_no"] for r in _rows] == [3, 1, 2, 7]
      and [r["name"] for r in _rows] == ["geom", "XMin", "outlet", ""]
      and [r["bc_type"] for r in _rows] == [3, 1, 1, 2]
      and {r["values"] for r in _rows} == {""},
      f"7. one bc_definitions row per patch, in the order given, the name kept "
      f"as the grouping label and no extra value invented ({_rows})")

# ── 8. the overrides ─────────────────────────────────────────────────────────
_names = ["geom", "outlet", "XMin", "geom"]
check(bc_flag_overrides(_names, _GROUP, euler=False) == {0: 3, 2: 1, 3: 3},
      f"8. only the rows whose patch NAME carries an explicit assignment are "
      f"offered a new flag, keyed by row index "
      f"({bc_flag_overrides(_names, _GROUP, euler=False)})")
check(bc_flag_overrides(_names, {}, euler=False) == {}
      and bc_flag_overrides(_names, None) == {}
      and bc_flag_overrides([], _GROUP) == {},
      "8. …and nothing assigned means nothing offered, so a manual tweak on an "
      "unassigned row stands")
check(bc_flag_overrides(["geom", None, "XMin"], {**_GROUP, "": "inlet"}) == {0: 3, 2: 1},
      "8. …and a row with no name CELL is skipped without a lookup, which `\"\"` "
      "as a stand-in would not be — the panel passes None for exactly that row "
      f"({bc_flag_overrides(['geom', None, 'XMin'], {**_GROUP, '': 'inlet'})})")

# ── the pre-#90 inline implementation, the oracle for checks 10 and 11 ───────
def _pre90_flag(name, group_bc, euler):
    """`solver_config_bc_mixin.populate_bc_from_segments` as of fca0997."""
    assigned = (group_bc or {}).get(name)
    return (default_bc_flag_for_name(assigned, euler) if assigned
            else default_bc_flag_for_name(name, euler))


# ── 9-10. the PANEL agrees, through the real widgets ─────────────────────────
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication                            # noqa: E402
from app.views.panels.solver_config_panel import SolverConfigPanel  # noqa: E402

_app = QApplication.instance() or QApplication([])
_panel = SolverConfigPanel()
_n = _panel.populate_bc_from_segments(_PATCHES, euler=False, group_bc=_GROUP)
_panel_rows = _panel.get_config().bc_definitions
check(_n == len(_PATCHES) and _panel_rows == _rows,
      f"9. the panel's table holds exactly the service's rows "
      f"(n={_n}, {_panel_rows})")

_e_rows = bc_definitions_for_patches(_PATCHES, group_bc=_GROUP, euler=True)
_panel.populate_bc_from_segments(_PATCHES, euler=True, group_bc=_GROUP)
check(_panel.get_config().bc_definitions == _e_rows,
      f"9. …and under euler_sol too, where the unnamed patch turns to slip "
      f"({[r['bc_type'] for r in _e_rows]})")

# Seed the table with the NAME-only guess, then resync from the assignments:
# rows 0 and 1 carry one, row 2 does not and must keep whatever is shown.
_panel.populate_bc_from_segments(_PATCHES, euler=False, group_bc={})
_seeded = [r["bc_type"] for r in _panel.get_config().bc_definitions]
_changed = _panel.resync_bc_types_from_group(_GROUP, euler=False)
_after = [r["bc_type"] for r in _panel.get_config().bc_definitions]
_over = bc_flag_overrides([nm for _s, nm in _PATCHES], _GROUP, euler=False)
_want = [_over.get(i, f) for i, f in enumerate(_seeded)]
# ...and the same expectation reached WITHOUT the service: pre-#90, resync moved
# a row iff its name carried an assignment, to that assignment's own flag.
_want_pre90 = [(_pre90_flag(nm, _GROUP, False) if _GROUP.get(nm) else f)
               for (_s, nm), f in zip(_PATCHES, _seeded)]
check(_after == _want == _want_pre90
      and _changed == sum(1 for i, f in enumerate(_seeded) if _over.get(i, f) != f),
      f"10. resync applies exactly the service's overrides — and the pre-#90 "
      f"rule's — counting the rows that really moved (seeded {_seeded} -> "
      f"{_after}, want {_want_pre90}, changed={_changed})")
check(_panel.resync_bc_types_from_group(_GROUP, euler=False) == 0,
      "10. …and a second resync changes nothing, so the count is rows moved "
      "rather than rows visited")

_MATRIX = []
for _nm in ("inlet", "outlet", "wall", "symp", "s2d", "", "Mystery", "GEOM"):
    for _asg in (None, "", "wall", "inlet", "isothermal", "nonsense"):
        for _eu in (False, True):
            _MATRIX.append((_nm, {_nm: _asg} if _asg is not None else {}, _eu))
# ── 11. against the pre-#90 inline implementation ────────────────────────────
_bad = [(nm, g, eu, bc_flag_for_patch(nm, g, eu), _pre90_flag(nm, g, eu))
        for nm, g, eu in _MATRIX
        if bc_flag_for_patch(nm, g, eu) != _pre90_flag(nm, g, eu)]
check(not _bad and len(_MATRIX) == 96,
      f"11. the service answers the pre-#90 inline rule exactly, over "
      f"{len(_MATRIX)} name/assignment/solution-type combinations ({_bad[:3]})")

# ── 12. ONE caller-facing answer for the mapping ─────────────────────────────
# The rule can be stated twice without either copy being wrong TODAY, which is how
# a precedence rule drifts apart. So: the name→flag mapping is reached from the
# derivation service and from nowhere else in the GUI tree, and no VIEW reaches it
# at all. Read from source, since a runtime check cannot see a copy nobody ran.
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
        if "default_bc_flag_for_name" in _txt:
            _callers.append(_rel)
            if _rel.startswith("views/"):
                _views.append(_rel)
check(_callers == ["services/solver_bc_table.py"] and not _views,
      f"12. the name→flag mapping has ONE caller — the derivation service — and "
      f"no view calls it (callers={_callers})")
check("default_bc_flag_for_name" not in
      open(os.path.join(_gui_app, "views/panels/solver_config_bc_mixin.py"),
           encoding="utf-8").read(),
      "12. …the panel mixin in particular, which is where the precedence rule "
      "used to live")

print()
if _FAILS:
    print(f"{len(_FAILS)} FAILED:")
    for m in _FAILS:
        print("  - " + m)
print(f"{len(_FAILS)} failure(s)" if _FAILS else "all checks passed")
os._exit(1 if _FAILS else 0)
