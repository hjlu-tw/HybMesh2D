---
paths:
  - tools/PreProcessor/gui/app/views/panels/**
  - tools/PreProcessor/gui/app/views/clean_double_spin_box.py
  - tools/PreProcessor/gui/app/views/import_unit_dialog.py
  - tools/PreProcessor/gui/app/views/units_ui.py
  - tools/PreProcessor/gui/app/services/*field_spec*
  - tools/PreProcessor/gui/app/services/config_ownership.py
  - tools/PreProcessor/gui/app/services/units.py
  - tools/PreProcessor/gui/app/models/mesh_config*
---

# GUI panel-configuration rules

Loaded on demand when a panel view, the physical-length spin box, a field-spec service, the unit
service or a mesh-config model is read. Rules only — the rationale (the counted attributes, the
measurements, the injections, the reversals) is `docs/design_notes/gui.md`. Read that note before
overruling a rule here, and when a rule changes update BOTH.

**These rules also govern files OUTSIDE the globs above, which cannot hand a reader the text**:
`controllers/panel_sync_ctrl.py` (the module the one-directional flow is named after),
`controllers/undo_ctrl.py` (`_wire_widget_edits`, the traversal that makes the panel→model sync run
on every edit), `controllers/pipeline_io_ctrl.py`, `controllers/project_state_ctrl.py`, and
`tools/PreProcessor/run_pipeline.py`, whose `[INFO] reference Reynolds number` line the length-unit
rules name as one of the two visible defences against a plausible wrong unit. That last one is
matched by `.claude/rules/pipeline-case.md`'s globs instead, and that file carries no unit rule, so
the tripwire table is its only route here. The table in `CLAUDE.md` is what makes every one of
these reachable; the globs are the convenience.

**Two of the globs reach files whose rules are NOT here — read that file as well.**
`views/panels/**` is the glob #59 assigns to this area and is wider than the area: the results
panels and mixins are governed by `.claude/rules/gui-results.md` (whose own globs name
`views/panels/result_panel*`, so a reader of one is handed both files), and
`views/panels/restart_chooser.py` by `.claude/rules/pipeline-case.md`. And `models/mesh_config*`
reaches `MeshConfig.output_base` / `output_path_for`, whose rule — the Output field's `.*`
placeholder and the one module allowed to read it — is in `.claude/rules/gui-handoff.md` with
`models/mesh_output_names.py`, where #77 moved it.

**Stage config data flow is one-directional** (`controllers/panel_sync_ctrl.py`): the **model is
the truth, the panel is a view**.
- **panel → model**: `sync_panel_to_model(panel_attr)` runs on *every* user edit (the
  widget-introspection traversal in `undo_ctrl._wire_widget_edits` calls `on_panel_edited`, which
  syncs first and then schedules the undo snapshot). So `global_mesh_config` /
  `global_solver_config` / `global_stl3d_config` are never stale; nothing should read a panel widget
  to get a config value.
- **model → panel**: `push_panel_config(panel, cfg)` (undo-suppressed).
- **`PRESERVED_FIELDS` lists what each panel does NOT author and must never overwrite** (the solver
  panel has no widget for `length_unit`, so a wholesale copy would wipe it and take `Linf` with it).
  `tests/test_panel_model_sync.py` proves each set equals what that panel's `get_config` actually
  assigns, **by AST**, so a model field added without a widget fails the build instead of silently
  going stale.
- A model may define `normalize()` to restore its own invariants after a sync.
- **`set_config` sets the panel's own `_loading` flag under try/finally**, and the sync checks
  *that*, not the caller's discipline: a direct `set_config` that forgets `push_panel_config` must
  cost at most a spurious undo step, never a corrupted model. New panels must follow the same
  `set_config` / `_set_config_body` split.

**A config field is declared ONCE, in its panel's field-spec table.** `app/services/field_spec.py`
is the Qt-free record plus the pure questions asked of a table; `views/panels/field_widgets.py` is
the one kind→widget mapping and the three traversals; the tables are `services/mesh_field_specs.py`
+ `services/mesh_bl_field_specs.py` and `views/panels/solver_field_specs.py`,
`views/panels/stl3d_field_specs.py` — the two MESH tables live in `services/` because the `.dat`
key map derives from them, and their old `views/panels/` paths survive as re-export shims. A spec
carries `attr` · `kind` · `label` · `tip` · `model` · `key` · `group` · `opts`; the table is walked
once to build (`add_spec_rows`), once to write (`write_specs`) and once to read (`read_specs`).
Load-bearing rules:
- **`get_config` / `set_config` / `_set_config_body` were NOT touched as verbs**, nor was
  `panel_sync_ctrl` — the frozen review lists both under *"genuinely deep — leave alone"*. The
  table sits BEHIND those three; the panel-owned `_loading` flag is unchanged.
- **`PRESERVED_FIELDS` is a subtraction, not a list**: model fields − table − the residue each
  panel declares beside its table (`*_EXTRA_AUTHORED`, for facts one widget holds for many things).
- **`LENGTH_FIELDS` is derived from `kind == "sci"`**, which IS the physical-length rule, so the
  list and the widgets cannot disagree.
- **Widgets are seeded from the model's defaults**, not literals repeated in build code.
- **A choice is matched by VALUE in Python, never `findData`** (QVariant comparison makes a bool
  `False` against an int `0` a coin toss), and an unavailable value falls back to a *declared* one
  instead of index 0.
- **Numeric and combo rows go into the form DIRECTLY, never wrapped**: `QFormLayout.labelForField`
  only finds a label for the widget that IS the field cell.
- **Three escape hatches, each used by exactly one field and named with its reason in the gate**:
  `read`/`write` on a spec (`ascii_combo`), `panel_choices` (`bl_concave_method`), `host_writes`
  (`output_filename`).
- **One spec means one tooltip**; the Edit-BL dialog's '?' shows that prose **plus the
  `.dat`/`Config.hpp` KEY** (the KEY used to be the only help 20 of 21 fields had, and giving every
  spec a tip silently killed the `spec.tip or key` fallback — gate check 12).
- **`services/field_spec.py` is Qt-free and gated.**
Gated by `tests/test_field_spec_tables.py` (twelve properties, every static one verified by
injection, each injection asserting the mutated source still PARSES and really changed).

**The GUI's `.dat` key map is DERIVED from the field-spec tables**
(`models/mesh_config_keys.py`): 45 of its 49 `KEY -> (attribute, converter)` entries come from the
tables (`spec.key` + `spec.model`), the converter from the model field's own dataclass type via
`field_spec.model_types()`, and the 4-entry residue is declared with a reason each.
- **The two mesh tables live in `services/` for this, and the reason is the seam.** Any module
  under `views/panels/` drags in that package's eight Qt panels, while `mesh_config_keys` is on the
  HEADLESS path (`mesh_config_io.config_to_text` ← `run_pipeline.sh` / `run_batch.sh`). The cost is
  recorded rather than hidden: ~250 lines of UI text now sit in `services/`. The solver and IB
  tables did NOT move — nothing headless derives from them.
- **`_KEY_MAP` is anchored to the WRITER, not just to the tables** (gate check 13f, both
  directions, with `GEOM_FILE` / `DOMAIN_FILE` / `SEED_FILE` / `GROUP_BC` declared). Checking only
  "map agrees with tables" was measured BLIND: removing a spec's `key=` left both sides agreeing
  while the writer kept emitting the line.
- `mesh_config.py` imports the map inside the two methods that use it, since deriving it made
  `mesh_config_keys` depend on `MeshConfig`.

**A field holding a physical length uses `views/clean_double_spin_box.py::SciDoubleSpinBox`, never
`CleanDoubleSpinBox`** — BL initial thickness, mesh sizes, domain coordinates, resampling spacing,
seed size/radius. It accepts/displays scientific notation, steps by decade, and has no hardcoded
floor: a fixed-notation box silently clamps the 1e-7..1e-8 first-cell heights real CFD needs. Range
lower bounds stay at 0, and invalid values are rejected by `MeshConfig.validate()` with a message,
never by UI clamping.

**The model declares ONE length unit, and it is not cosmetic — the solver is dimensional**
(`app/services/units.py`, Qt-free; Mesh panel, top row). Per the UNICONES manual
`fs_UnitRe` is *per metre* and `Linf` is *metres per grid unit*, so **Re = fs_UnitRe × Linf**: a mm
mesh left at `Linf = 1` runs at 1000× the intended Reynolds number with a mesh that looks perfect.
- **`Linf` is derived from the declared unit**, not typed. `SolverConfig.linf_from_unit` is True
  for anything new; `load_from_dict` turns it **off** for a config with a hand-set `linf` and no
  `length_unit`, so a pre-units case keeps its Reynolds number. `unit_check()` reports the
  discrepancy naming the unit that `linf` implies.
- **Changing the unit relabels; it never rescales.** Only two things convert numbers: `Linf`, and
  coordinates at *import* (`views/import_unit_dialog.py`, asked once per import action, defaulting
  to no conversion, silent + no-op when headless).
- **Units are shown as the spin box's own `setSuffix`**, never baked into label text. Only physical
  lengths get one; growth rates, angles and counts must not.
  `views/panels/mesh_units_mixin.py::LENGTH_FIELDS` must equal the panel's `SciDoubleSpinBox` set —
  `tests/test_units.py` fails the build otherwise.
- **The visible defence against a *plausible* wrong unit is the reference Reynolds number**
  read-out on the Solver panel (`views/panels/solver_units_mixin.py`) and the
  `[INFO] reference Reynolds number` line in `run_pipeline.py`.
- **The mesher records but never converts `LENGTH_UNIT`**; it prints it in the banner, so it lands
  in the provenance sidecar.

**The Edit Boundary Layer dialog's 21 BL parameters are collapsible groups, all closed to start
(USER-REQUESTED)**, plus Expand all / Collapse all — `views/panels/mesh_dialogs_bl.py`, tables in
`mesh_bl_field_specs.py`, accordion + fitting in `mesh_bl_dialog_layout.py`, the groups themselves
`_BL_FIELD_GROUPS` mirroring the `.dat` groups. Only two things open a group and neither is a
default: the state the user left it in (`ui_state`), and a group holding a value differing from the
global default, so a per-geometry override never hides behind a collapsed header.
- **`_BL_FIELD_GROUPS` must partition `_BL_FIELD_SPECS` exactly** — a key in no group is a
  parameter the user cannot reach that is still written back on OK. Gated by
  `tests/test_bl_dialog_sections.py`, with stray keys falling into a trailing "Other" group as a
  backstop.
- **The window follows the open groups** (`_relayout` → `_autofit_height`), bounded by the screen
  and never below a height the user set by dragging.
- Two Qt facts the fit depends on: `QScrollArea::sizeHint()` is **clamped to 24 font heights**, so
  the dialog's own `sizeHint()` stops growing after a group or two (the fit measures the scroll's
  shortfall against its cap instead); and hiding a widget only *posts* the layout request, so
  `CollapsibleSection._on_toggle` invalidates its own layout.
- **The leftover-space absorber is stretch 0 + Expanding**, never a stretched item, which would
  compete proportionally with the capped scroll area.

## Named blind spots

Consolidated here rather than trailing the rules they belong to, so a coverage claim can be checked
against one list. #71 moved both.

- **`config_ownership` is Qt-free at IMPORT only.** The SOLVER and IB tables still live under
  `views/panels/`, whose package `__init__` eagerly imports eight Qt panels, so a
  `preserved_fields()` call naming those two still loads PyQt6 — the Qt-free gate reaches
  `services/field_spec.py` only.
- **The unit size-plausibility check only catches gross errors, and says so.** A *plausible* wrong
  unit is left to the two visible defences above, which do nothing but print the number.
