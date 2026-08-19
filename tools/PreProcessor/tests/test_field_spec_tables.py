#!/usr/bin/env python3
"""One field-spec table per config panel (architecture candidate 5).

A stage-configuration panel was cut in half. One half BUILT widgets, the other read and
wrote them against a model, and the interface between the halves was the whole set of
widgets passed implicitly through ``self`` — 176 widget attributes across five build
mixins, named back by hand in 246 read/write lines. Nothing declared the set, so the
halves agreed only because both spelled the same name, and both failure directions were
silent: a model field with no widget went stale, a widget with no ``get_config`` line was
a control that did nothing.

Each panel now has one table (``MESH_SPECS`` + ``PANEL_BL_SPECS``, ``SOLVER_SPECS``,
``STL3D_SPECS``) walked once to build, once to read and once to write. What this gate
pins down is that it STAYS one:

 1. No field is declared twice — not two specs for one model field, and not two specs
    for one panel attribute.
 2. Each panel's declared residue (``*_EXTRA_AUTHORED``) equals what its remaining
    hand-written ``get_config`` code actually assigns, checked against the AST. That is
    the content left in the old ``PRESERVED_FIELDS`` equality once both sides became
    the same declaration.
 3. A table field's widget is not ALSO hand-built (``self.fs_mach = _spin(...)``) — the
    exact shape the table replaced, and the cheapest way to reintroduce it.
 4. A table field is not ALSO hand-read or hand-written inside the read/write halves
    (``get_config`` / ``_read_bl_widgets``, ``set_config`` / ``_set_config_body`` /
    ``_write_bl_widgets``). Scoped to those bodies on purpose: a ``setText`` in a restart
    auto-fill or a ``setVisible`` in a feature toggle is behaviour, not a second copy of
    the write half.
 5. Every declared group is walked by a builder, and every group a builder walks is
    declared. One direction alone has an obvious hole in each direction: an unwalked
    group is a field that is written back to the model and has no reachable widget; an
    undeclared group is a builder call that lays out nothing.
 6. Every kind in ``KINDS`` builds a widget, and an unknown kind is refused at
    construction rather than producing nothing.
 7. Every kind's read/write pair round-trips, on the LIVE panels' widgets.
 8. ``PRESERVED_FIELDS`` and ``LENGTH_FIELDS`` are derived, not listed.
 9. Every model field the panel does not author is named here with a reason, so a field
    added without a widget fails the build instead of silently becoming unreachable.
10. The three escape hatches (``read``/``write`` on a spec, ``panel_choices``,
    ``host_writes``) are used only by the fields listed here.
12. The Edit-BL dialog's '?' help still names each parameter's ``.dat`` KEY. Giving
    every spec a ``tip`` silently killed the ``spec.tip or key`` fallback that was the
    ONLY help 20 of the 21 fields had, so the dialog stopped showing the name a user
    reading a config file matches against. Found in review; pinned here.
11. The BL coercion sets are derived from ``MeshConfig``'s DECLARED field types and
    cover every BL parameter. That derivation reads ``dataclasses.fields(...).type``,
    which is a STRING under ``from __future__ import annotations``; a switch to
    ``bool | None``, or dropping that import, would silently empty the sets and put an
    int back in a bool field — the exact bug the derivation exists to prevent.

Every static check is verified BY INJECTION: the source is mutated in memory, the
mutation is asserted to have changed the text AND to still parse (a mutation that breaks
the syntax looks exactly like the check working), and the checker must then report the
defect.

Run:  python3 tools/PreProcessor/tests/test_field_spec_tables.py
"""
import ast
import dataclasses
import glob
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

from app.controllers.panel_sync_ctrl import PRESERVED_FIELDS  # noqa: E402
from app.models.mesh_config import MeshConfig  # noqa: E402
from app.models.solver_config import SolverConfig  # noqa: E402
from app.models.stl3d_config import Stl3dConfig  # noqa: E402
from app.services import field_spec as fs  # noqa: E402
from app.services.config_ownership import (  # noqa: E402
    PANEL_SOURCES, extra_authored, hand_authored, preserved_fields, spec_tables,
    unauthored_fields,
)
from app.views.panels import field_widgets as fw  # noqa: E402

PANELS = {
    "mesh_config_panel": MeshConfig,
    "solver_config_panel": SolverConfig,
    "stl3d_config_panel": Stl3dConfig,
}

#: Model fields no panel widget authors, each with the reason it has none. This is the
#: DELIBERATE half of PRESERVED_FIELDS: that set is now derived (fields minus table
#: minus residue), so nothing would otherwise notice a field added without a widget —
#: it would simply be preserved for ever, silently unreachable. Adding one costs an
#: entry here, which is a sentence of justification rather than a build break.
NO_WIDGET = {
    "mesh_config_panel": {
        "bc_geom": "the geometry wall patch: owned by the per-geometry / per-segment BC "
                   "dialogs and group_bc resolution, not by a panel field",
        "missing_geom_files": "a load diagnostic populated by load_from_file",
    },
    "solver_config_panel": {
        "length_unit": "declared on the MESH panel; this panel only shows derived Linf",
        "length_unit_metres": "ditto — wiping it would take Linf, i.e. the Reynolds "
                              "number, with it",
        "grid_type": "fixed for this workflow (unstructured)",
        "grid_data_format": "fixed for this workflow (c_binary)",
        "bc_file_use_table": "fixed for this workflow",
        "reorient_mesh": "fixed for this workflow",
        "slice_to_simplex": "fixed for this workflow",
        "solve_gcl": "fixed for this workflow",
        "work_dir": "staged per run by services/solver_case, not typed by the user",
    },
    # The IB panel authors every field of its model, which is also the only reason
    # stl3d_ctrl may assign that model wholesale (test_panel_model_sync check 10).
    "stl3d_config_panel": {},
}

#: The three escape hatches, and every field allowed to use one. Listed rather than
#: counted: an escape hatch nobody has to justify is how the irregular case becomes the
#: normal one again.
ESCAPE_HATCHES = {
    "read/write on the spec": {
        "ascii_combo": "a THREE-item combo (Auto-detect / ASCII / Binary) behind a "
                       "bool: Auto-detect and ASCII both mean True, so the mapping is "
                       "not one-to-one and no choice list can express it",
    },
    "panel_choices": {
        "bl_concave_method": "the panel's hidden backing combo offers method 5 alone "
                             "because method 0 (Merge) is CLI-side and the GUI has "
                             "never emitted it; the Edit-BL dialog offers both",
    },
    "host_writes": {
        "output_filename": "population is a heuristic (refresh an auto-generated name "
                           "from the current geometry, keep one the user typed) that "
                           "reads the widget's own text, so a plain copy would destroy "
                           "the state it branches on",
    },
}

#: Value setters. setEnabled / setVisible / setStyleSheet are behaviour, not a write of
#: the field's value, and several legitimately appear in the panels.
VALUE_SETTERS = {"setValue", "setText", "setChecked", "setCurrentIndex",
                 "setCurrentText"}


# ── source helpers (every checker takes a {path: text} map, so injection is text) ──

def panel_sources(panel: str) -> dict:
    out = {}
    for pattern in PANEL_SOURCES.get(panel, ()):
        for path in sorted(glob.glob(os.path.join(_GUI, pattern))):
            with open(path, encoding="utf-8") as f:
                out[path] = f.read()
    return out


def _funcs(tree, names):
    return [n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]


def hand_built(sources: dict, attrs: set) -> list:
    """``self.<table attr> = …`` anywhere in the panel's sources."""
    out = []
    for path, src in sources.items():
        tree = ast.parse(src, filename=path)
        for n in ast.walk(tree):
            if not isinstance(n, ast.Assign):
                continue
            for t in n.targets:
                if (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                        and t.value.id == "self" and t.attr in attrs):
                    out.append(f"{os.path.basename(path)}:{n.lineno} self.{t.attr} = …")
    return out


def hand_written(sources: dict, attrs: set, exempt: set) -> list:
    """A per-field value setter inside ``set_config`` / ``_set_config_body``."""
    out = []
    for path, src in sources.items():
        tree = ast.parse(src, filename=path)
        # Scope: the WRITE half. `_write_bl_widgets` is part of it — the BL store's
        # own traversal — and was the hole a reviewer found in the first version:
        # a `self.bl_layers.setValue(...)` reintroduced there passed the check.
        for fn in _funcs(tree, {"set_config", "_set_config_body", "_write_bl_widgets"}):
            for n in ast.walk(fn):
                if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                        and n.func.attr in VALUE_SETTERS
                        and isinstance(n.func.value, ast.Attribute)
                        and isinstance(n.func.value.value, ast.Name)
                        and n.func.value.value.id == "self"):
                    continue
                attr = n.func.value.attr
                if attr in attrs and attr not in exempt:
                    out.append(f"{os.path.basename(path)}:{n.lineno} "
                               f"self.{attr}.{n.func.attr}(…)")
    return out


def hand_read(sources: dict, authored: set) -> list:
    """``cfg.<table field> = …`` inside ``get_config``."""
    out = []
    for path, src in sources.items():
        tree = ast.parse(src, filename=path)
        for fn in _funcs(tree, {"get_config", "_read_bl_widgets"}):
            for n in ast.walk(fn):
                if not isinstance(n, ast.Assign):
                    continue
                for t in n.targets:
                    if (isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                            and t.value.id == "cfg" and t.attr in authored):
                        out.append(f"{os.path.basename(path)}:{n.lineno} "
                                   f"cfg.{t.attr} = …")
    return out


def groups_walked(sources: dict) -> set:
    """Group names passed to ``_spec_rows`` / ``_spec_widgets`` in the panel's sources."""
    out = set()
    for path, src in sources.items():
        tree = ast.parse(src, filename=path)
        for n in ast.walk(tree):
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr in ("_spec_rows", "_spec_widgets")):
                for a in n.args:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        out.add(a.value)
    return out


def inject(sources: dict, path_frag: str, old: str, new: str) -> dict:
    """A copy of ``sources`` with one replacement, proving the mutation is real.

    Both guards matter. A replacement that matched nothing leaves the sources intact
    and the check passes for the wrong reason; a replacement that breaks the syntax
    makes every AST walk raise, which looks exactly like the check working.
    """
    hit = [p for p in sources if path_frag in os.path.basename(p)]
    assert len(hit) == 1, f"injection target {path_frag!r} matched {hit}"
    out = dict(sources)
    mutated = out[hit[0]].replace(old, new, 1)
    assert mutated != out[hit[0]], f"injection into {path_frag} changed nothing"
    ast.parse(mutated, filename=hit[0])          # must still be valid Python
    out[hit[0]] = mutated
    return out


# ── 1. nothing is declared twice ──────────────────────────────────────────
for panel in PANELS:
    tables = spec_tables(panel)
    check(bool(tables), f"1. {panel} has at least one field-spec table")
    dm = fs.duplicate_models(*tables)
    da = fs.duplicate_attrs(*tables)
    check(not dm, f"1. {panel}: no model field is authored by two specs ({dm})")
    check(not da, f"1. {panel}: no panel attribute is declared by two specs ({da})")

_dupe = fs.duplicate_models(spec_tables("solver_config_panel")[0]
                            + (fs.FieldSpec("fs_mach_again", "float", "M", "",
                                            model="fs_mach",
                                            opts=dict(lo=0.0, hi=1.0, dec=2)),))
check(_dupe == ("fs_mach",),
      f"1. (injection) a second spec for one model field is reported ({_dupe})")
_dupe_a = fs.duplicate_attrs(spec_tables("solver_config_panel")[0]
                             + (fs.FieldSpec("fs_mach", "float", "M", "", model=None,
                                             opts=dict(lo=0.0, hi=1.0, dec=2)),))
check(_dupe_a == ("fs_mach",),
      f"1. (injection) a second spec for one panel attribute is reported ({_dupe_a})")

# ── 2. the declared residue is honest ─────────────────────────────────────
for panel, cls in PANELS.items():
    derived = preserved_fields(panel, cls)
    from_source = unauthored_fields(panel, cls)
    check(derived == from_source,
          f"2. {panel}: the declared residue matches the code — table + "
          f"*_EXTRA_AUTHORED covers exactly what get_config assigns "
          f"(claimed-but-unwritten: {sorted(derived - from_source)}; "
          f"written-but-undeclared: {sorted(from_source - derived)})")
    # A sanity check on the extractor: a silent zero would make the above vacuous.
    model_names = {f.name for f in dataclasses.fields(cls)}
    found = hand_authored(panel) & model_names
    check(len(found) >= len(extra_authored(panel)),
          f"2. the ast extractor still finds {panel}'s hand-written assignments "
          f"({len(found)} found, {len(extra_authored(panel))} declared)")

# Injection: claim a residue field the panel does not actually write.
_extra = set(extra_authored("solver_config_panel")) | {"work_dir"}
_bad = fs.preserved(SolverConfig, spec_tables("solver_config_panel"), _extra)
check(_bad != unauthored_fields("solver_config_panel", SolverConfig),
      "2. (injection) a residue entry no code writes makes the two answers disagree")
# Injection: drop a real residue field.
_extra2 = set(extra_authored("solver_config_panel")) - {"bc_definitions"}
_bad2 = fs.preserved(SolverConfig, spec_tables("solver_config_panel"), _extra2)
check(_bad2 != unauthored_fields("solver_config_panel", SolverConfig),
      "2. (injection) ...and so does dropping one the code does write")

# ── 3. a table field's widget is not also hand-built ──────────────────────
for panel in PANELS:
    src = panel_sources(panel)
    attrs = set(fs.by_attr(*spec_tables(panel)))
    offenders = hand_built(src, attrs)
    check(not offenders,
          f"3. {panel}: no table field's widget is hand-built as well ({offenders})")

_src = panel_sources("solver_config_panel")
_mut = inject(_src, "solver_config_build_mixin.py",
              "    def _build_pipeline_section(self):\n",
              "    def _build_pipeline_section(self):\n"
              "        self.fs_mach = _check('x', 'y')\n")
check(hand_built(_mut, set(fs.by_attr(*spec_tables("solver_config_panel")))),
      "3. (injection) a hand-built widget shadowing a table row is reported")

# ── 4. a table field is not also hand-read / hand-written ─────────────────
_exempt = set(ESCAPE_HATCHES["host_writes"])
for panel in PANELS:
    src = panel_sources(panel)
    attrs = set(fs.by_attr(*spec_tables(panel)))
    authored = set(fs.authored(*spec_tables(panel)))
    w = hand_written(src, attrs, _exempt)
    r = hand_read(src, authored)
    check(not w, f"4. {panel}: set_config writes no field by hand ({w})")
    check(not r, f"4. {panel}: get_config reads no field by hand ({r})")

_mut = inject(_src, "solver_config_sync_mixin.py",
              "        write_specs(self, SOLVER_SPECS, cfg)\n",
              "        write_specs(self, SOLVER_SPECS, cfg)\n"
              "        self.fs_mach.setValue(cfg.fs_mach)\n")
check(hand_written(_mut, set(fs.by_attr(*spec_tables("solver_config_panel"))), _exempt),
      "4. (injection) a per-field setValue back inside _set_config_body is reported")
_mut = inject(_src, "solver_config_sync_mixin.py",
              "        read_specs(self, SOLVER_SPECS, cfg)\n",
              "        read_specs(self, SOLVER_SPECS, cfg)\n"
              "        cfg.fs_mach = self.fs_mach.value()\n")
check(hand_read(_mut, set(fs.authored(*spec_tables("solver_config_panel")))),
      "4. (injection) a per-field cfg assignment back inside get_config is reported")
# ...and the exemption is not a blanket one: output_filename is allowed, a second
# field is not.
_msrc = panel_sources("mesh_config_panel")
_mut = inject(_msrc, "mesh_config_config_mixin.py",
              "        write_specs(self, MESH_SPECS, cfg)\n",
              "        write_specs(self, MESH_SPECS, cfg)\n"
              "        self.surface_mesh_size.setValue(cfg.surface_mesh_size)\n")
check(hand_written(_mut, set(fs.by_attr(*spec_tables("mesh_config_panel"))), _exempt),
      "4. (injection) the host_writes exemption covers one named field, not the rest")

# ── 5. groups and builders match, in both directions ──────────────────────
for panel in PANELS:
    src = panel_sources(panel)
    declared = set()
    for table in spec_tables(panel):
        declared |= set(fs.group_names(table))
    walked = groups_walked(src)
    check(declared == walked,
          f"5. {panel}: every declared group is walked by a builder and vice versa "
          f"(declared-not-walked: {sorted(declared - walked)}; "
          f"walked-not-declared: {sorted(walked - declared)})")

_mut = inject(_src, "solver_config_build_mixin.py",
              'self._spec_rows(form, "grid")', 'pass')
check("grid" not in groups_walked(_mut),
      "5. (injection) dropping a builder call leaves its group unreachable — a field "
      "still written to the model with no widget to reach it")
_mut = inject(_src, "solver_config_build_mixin.py",
              'self._spec_rows(form, "grid")',
              'self._spec_rows(form, "grid"); self._spec_rows(form, "gird")')
check("gird" in groups_walked(_mut),
      "5. (injection) ...and a builder walking a group nothing declares is reported")

# ── 6. every kind builds a widget; an unknown kind is refused ─────────────
_KIND_CLASS = {
    "sci": "SciDoubleSpinBox", "float": "CleanDoubleSpinBox",
    "narrow": "NarrowDoubleSpinBox", "int": "QSpinBox", "text": "QLineEdit",
    "gfloat": "QLineEdit", "bool": "QCheckBox", "choice": "QComboBox",
    "path": "QLineEdit", "bcname": "BCWidget", "toggle": "QPushButton",
    "label": "QLabel",
}
check(set(_KIND_CLASS) == set(fs.KINDS),
      f"6. every declared kind is covered here "
      f"(missing: {sorted(set(fs.KINDS) - set(_KIND_CLASS))})")
# lo/hi are INTS: they have to serve the int kind too, whose QSpinBox.setRange
# refuses a float on a current sip (and took a DeprecationWarning before that).
# The double spin boxes accept an int bound unchanged.
_probe_opts = dict(lo=0, hi=10, dec=2, choices=[(1, "one"), (2, "two")])
for kind, cls_name in _KIND_CLASS.items():
    w = fw.make_widget(fs.FieldSpec("probe", kind, "Probe", "tip", model=None,
                                    opts=dict(_probe_opts)))
    check(type(w).__name__ == cls_name,
          f"6. kind {kind!r} builds a {cls_name} (got {type(w).__name__})")

try:
    fs.FieldSpec("probe", "flaot", "Probe", "tip")
    _refused = False
except ValueError:
    _refused = True
check(_refused,
      "6. (injection) a typo'd kind is refused at construction — it would otherwise "
      "build no widget and be found as a missing control")

try:
    fs.FieldSpec("probe", "int", "Probe", "tip", opts=dict(lo=0, hi=1e6))
    _refused = False
except ValueError:
    _refused = True
check(_refused,
      "6. (injection) a float bound on an int field is refused at construction — "
      "QSpinBox.setRange takes ints, so `hi=1e6` builds the panel on one sip and "
      "raises TypeError on another")

# ── 7. every kind's read/write pair round-trips on the LIVE panels ────────
from app.views.panels.mesh_config_panel import MeshConfigPanel  # noqa: E402
from app.views.panels.solver_config_panel import SolverConfigPanel  # noqa: E402
from app.views.panels.stl3d_panel import Stl3dConfigPanel  # noqa: E402

_PANEL_OBJS = {
    "mesh_config_panel": MeshConfigPanel(None),
    "solver_config_panel": SolverConfigPanel(None),
    "stl3d_config_panel": Stl3dConfigPanel(None),
}


def probe_value(spec, current):
    """A value in range that is not what the widget already holds."""
    o = spec.opts
    if spec.kind == "choice":
        vals = [v for v, _l in o["choices"]]
        return next((v for v in vals if v != current), vals[0])
    if spec.kind in ("bool", "toggle"):
        return not bool(current)
    if spec.kind == "int":
        lo, hi = o["lo"], o["hi"]
        return lo + 3 if lo + 3 <= hi else hi
    if spec.kind == "sci":
        return 2.5e-7 if o["lo"] <= 2.5e-7 <= o["hi"] else o["hi"] / 3.0
    if spec.kind in ("float", "narrow"):
        lo, hi = o["lo"], o["hi"]
        return round(lo + (hi - lo) * 0.123456, o["dec"])
    if spec.kind == "gfloat":
        return -1.25e-11
    if spec.kind == "bcname":
        return "SYMP"
    return "probe/value.txt"


def roundtrip_failures(panel_obj, specs):
    bad = []
    for spec in specs:
        if spec.kind == "label" or spec.model_name is None:
            continue
        w = getattr(panel_obj, spec.attr, None)
        if w is None:
            bad.append(f"{spec.attr}: no widget on the panel")
            continue
        want = probe_value(spec, fw.read_widget(w, spec))
        fw.write_widget(w, spec, want)
        got = fw.read_widget(w, spec)
        ok = (abs(got - want) <= max(1e-12, abs(want) * 1e-9)
              if isinstance(want, float) and isinstance(got, (int, float))
              else got == want)
        if not ok:
            bad.append(f"{spec.attr} ({spec.kind}): wrote {want!r}, read {got!r}")
    return bad


for panel, obj in _PANEL_OBJS.items():
    specs = [s for table in spec_tables(panel) for s in table]
    bad = roundtrip_failures(obj, specs)
    check(not bad, f"7. {panel}: every field round-trips through its widget ({bad})")

_broken = fs.FieldSpec("fs_mach", "float", "M", "", opts=dict(lo=0.0, hi=100.0, dec=4),
                       read=lambda w: w.value() + 1.0)
check(roundtrip_failures(_PANEL_OBJS["solver_config_panel"], [_broken]),
      "7. (injection) a read/write pair that disagrees is reported")

# ── 8. the derived lists are derived ──────────────────────────────────────
_ALL_MODEL_FIELDS = {f.name for cls in PANELS.values() for f in dataclasses.fields(cls)}


def listed_field_names(src: str, name: str, known: set) -> list:
    """Model field names appearing as STRING LITERALS in ``name``'s value expression.

    An AST walk of the assignment, not a substring search for ``frozenset({"``: the
    first version of this check was that substring, and CLAUDE.md already records a
    substring check broken in one line — ``frozenset([...])`` or single quotes would
    have slipped straight through, and a literal dict identical to the derivation would
    have passed while nothing was derived at all.
    """
    tree = ast.parse(src)
    out = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)):
            continue
        for c in ast.walk(n.value):
            if isinstance(c, ast.Constant) and isinstance(c.value, str) \
                    and c.value in known:
                out.append(c.value)
    return sorted(out)


_sync_path = os.path.join(_GUI, "app", "controllers", "panel_sync_ctrl.py")
_sync_src = open(_sync_path, encoding="utf-8").read()
_listed = listed_field_names(_sync_src, "PRESERVED_FIELDS", _ALL_MODEL_FIELDS)
check("preserved_fields(" in _sync_src and not _listed,
      f"8. PRESERVED_FIELDS is derived from the tables, with no field named as a "
      f"literal ({_listed})")
_mut = _sync_src.replace(
    "PRESERVED_FIELDS = {\n    panel: preserved_fields(panel, cls)\n"
    "    for panel, cls in PANEL_MODEL_CLASSES.items()\n}",
    'PRESERVED_FIELDS = {"mesh_config_panel": frozenset(["bc_geom"])}', 1)
assert _mut != _sync_src, "check-8 injection changed nothing"
ast.parse(_mut)
check(listed_field_names(_mut, "PRESERVED_FIELDS", _ALL_MODEL_FIELDS) == ["bc_geom"],
      "8. (injection) a hand-listed field name is reported — including in a spelling "
      "the old substring check would have missed (frozenset([...]))")
for panel, cls in PANELS.items():
    check(PRESERVED_FIELDS[panel] == preserved_fields(panel, cls),
          f"8. ...and {panel}'s entry IS that derivation")

_units_src = open(os.path.join(_GUI, "app", "views", "panels", "mesh_units_mixin.py"),
                  encoding="utf-8").read()
check("length_attrs(" in _units_src,
      "8. LENGTH_FIELDS is derived from the table's sci kind, not a hand-written tuple")
from app.views.panels.mesh_units_mixin import LENGTH_FIELDS  # noqa: E402

check(set(LENGTH_FIELDS) == set(fs.length_attrs(*spec_tables("mesh_config_panel"))),
      "8. ...and equals the sci-kind fields of the mesh panel's tables")
_mut = _units_src.replace("LENGTH_FIELDS = length_attrs(MESH_SPECS, PANEL_BL_SPECS)",
                          'LENGTH_FIELDS = ("domain_x_min",)', 1)
assert _mut != _units_src, "LENGTH_FIELDS injection changed nothing"
ast.parse(_mut)
check(listed_field_names(_mut, "LENGTH_FIELDS", {"domain_x_min"}) == ["domain_x_min"]
      and not listed_field_names(_units_src, "LENGTH_FIELDS", _ALL_MODEL_FIELDS),
      "8. (injection) replacing the derivation with a literal tuple is reported by the "
      "same checker, and the shipped source names nothing")

# ── 9. a field with no widget is named, with its reason ───────────────────
for panel, cls in PANELS.items():
    declared = set(NO_WIDGET[panel])
    derived = set(preserved_fields(panel, cls))
    check(declared == derived,
          f"9. {panel}: every field no widget authors is named here with a reason "
          f"(undeclared: {sorted(derived - declared)}; stale: {sorted(declared - derived)})")
    check(all(len(r) > 20 for r in NO_WIDGET[panel].values()),
          f"9. ...and each reason is a sentence, not a placeholder ({panel})")

# ── 10. the escape hatches are used only where justified ──────────────────
_all_specs = [s for panel in PANELS for table in spec_tables(panel) for s in table]
_used = {
    "read/write on the spec": {s.attr for s in _all_specs
                               if s.read is not None or s.write is not None},
    # panel_variant() strips the key, so ask the un-narrowed tables.
    "panel_choices": {s.attr for s in _all_specs if s.opts.get("panel_choices")}
    | {s.attr for s in
       __import__("app.views.panels.mesh_bl_field_specs", fromlist=["BL_SPECS"]).BL_SPECS
       if s.opts.get("panel_choices")},
    "host_writes": {s.attr for s in _all_specs if s.opts.get("host_writes")},
}
for hatch, allowed in ESCAPE_HATCHES.items():
    check(_used[hatch] == set(allowed),
          f"10. {hatch}: used only by the fields justified here "
          f"(unjustified: {sorted(_used[hatch] - set(allowed))}; "
          f"stale: {sorted(set(allowed) - _used[hatch])})")

# ── 11. the BL coercion sets are derived AND cover every BL parameter ─────
from app.views.panels.mesh_bl_field_specs import (  # noqa: E402
    _BL_BOOL_ATTRS, _BL_INT_ATTRS,
)

_BL_TABLE = spec_tables("mesh_config_panel")[1]        # PANEL_BL_SPECS
_MESH_TYPES = {f.name: f.type for f in dataclasses.fields(MeshConfig)}


def bl_coercion_gaps(table, types: dict) -> dict:
    """What a BL parameter's model type is, where it is not one of the three handled.

    Returns {attr: type} for anything that would fall through to the float branch of
    ``_apply_global_bl_to_cfg`` by accident rather than by declaration.
    """
    return {s.attr: types.get(s.attr)
            for s in table if types.get(s.attr) not in ("int", "float", "bool")}


_gaps = bl_coercion_gaps(_BL_TABLE, _MESH_TYPES)
check(not _gaps,
      f"11. every BL parameter's MeshConfig type is one the coercion handles ({_gaps})")
check(_BL_INT_ATTRS and _BL_BOOL_ATTRS,
      f"11. the derived coercion sets are non-empty — an empty pair would silently "
      f"coerce every BL parameter to float (int={len(_BL_INT_ATTRS)}, "
      f"bool={len(_BL_BOOL_ATTRS)})")
_float_attrs = {s.attr for s in _BL_TABLE} - _BL_INT_ATTRS - _BL_BOOL_ATTRS
check(_BL_INT_ATTRS | _BL_BOOL_ATTRS | _float_attrs == {s.attr for s in _BL_TABLE}
      and not (_BL_INT_ATTRS & _BL_BOOL_ATTRS),
      "11. ...and int / bool / float partition the 21 parameters exactly")
# The tri-state field is the one this must get right: a three-value combo behind a bool.
check("bl_auto_fan_nodes" in _BL_BOOL_ATTRS,
      "11. bl_auto_fan_nodes coerces as BOOL (its model field is one) even though a "
      "three-value combo edits it — deriving from the WIDGET would put an int in a bool "
      "field and make the model disagree with its own dataclass default")

_stringly = bl_coercion_gaps(_BL_TABLE, {k: "bool | None" if v == "bool" else v
                                         for k, v in _MESH_TYPES.items()})
check(_stringly,
      "11. (injection) an annotation the derivation does not recognise "
      "(`bool | None`) is reported instead of silently coercing to float")

# ── 12. the dialog's '?' keeps the .dat KEY beside the prose ──────────────
from app.utils import HelpButton  # noqa: E402
from app.views.panels.mesh_dialogs_bl import PerGeomBLDialog  # noqa: E402

_dlg = PerGeomBLDialog("gate", {s.key: 1.0 for s in _BL_TABLE}, None)
_help = [b._tooltip_text for b in _dlg.findChildren(HelpButton)]
_keys = {s.key for s in _BL_TABLE}
_missing = sorted(k for k in _keys if not any(k in t for t in _help))
check(not _missing,
      f"12. every BL parameter's '?' help names its .dat KEY, so a user reading a "
      f"config file can still find the field ({_missing})")
# ...and the prose is there too: before this candidate 20 of 21 showed the KEY ALONE.
_prose = [t for t in _help if "\n\n(BL_" in t]
check(len(_prose) == len(_keys),
      f"12. ...alongside the parameter's own explanation, which 20 of the 21 fields "
      f"did not have at all before ({len(_prose)}/{len(_keys)})")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
