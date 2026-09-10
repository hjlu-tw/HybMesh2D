---
paths:
  - tools/PreProcessor/gui/app/views/panels/**
  - tools/PreProcessor/gui/app/views/clean_double_spin_box.py
  - tools/PreProcessor/gui/app/views/import_unit_dialog.py
  - tools/PreProcessor/gui/app/views/units_ui.py
  - tools/PreProcessor/gui/app/services/*field_spec*
  - tools/PreProcessor/gui/app/services/config_ownership.py
  - tools/PreProcessor/gui/app/services/geom_path_identity.py
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
- **Filling a field through the MODEL'S OWN VERB counts as authoring it**, declared in
  `config_ownership.MODEL_WRITER_METHODS` (method → field): the ownership scan reads syntax, so a
  field a panel can only write through a verb otherwise reads as unauthored and the sync
  *preserves* — i.e. discards — what the panel just built. Declared rather than guessed from the
  name, since `add_geom_file` does not spell its plural field. Gated by
  `tests/test_field_spec_tables.py` check 2, which fails on an entry naming a method or a field
  that no ONE model class carries together, and asserts at least one field is verb-authored with no
  assignment in that panel's own `get_config`, so deleting the map cannot pass. #99 is what made
  that real: `geom_files` became verb-only outside the model, and the mesh panel's own
  `cfg.add_geom_file(p)` had always been invisible to the scan — only the bare `cfg.geom_files = []`
  beside it was keeping the answer right. **An entry may be inert**: `remove_geom_file`'s callers
  are in `controllers/mesh_layers_ctrl.py`, outside every `PANEL_SOURCES` glob.
- **`LENGTH_FIELDS` is derived from `kind == "sci"`**, which IS the physical-length rule, so the
  list and the widgets cannot disagree.
- **Widgets are seeded from the model's defaults**, not literals repeated in build code.
- **A choice is matched by VALUE in Python, never `findData`** (QVariant comparison makes a bool
  `False` against an int `0` a coin toss), and an unavailable value falls back to a *declared* one
  instead of index 0.
- **Numeric and combo rows go into the form DIRECTLY, never wrapped**: `QFormLayout.labelForField`
  only finds a label for the widget that IS the field cell, and four visibility helpers use it to
  hide a row's label with its field. **ONE exemption exists in the whole GUI and it is recorded
  here**: the Edit-BL dialog's C1 note cell (measured in the greyed-field rule below), legal only
  because nothing in that dialog's OWN mixins calls `labelForField` —
  `tests/test_bl_dialog_sections.py` check 14 pins that precondition by AST over the dialog's own
  MRO, so a visibility helper added there fails the build instead of silently finding no label.
  Anywhere else a wrapped cell orphans its label.
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
- **A field the selected scheme cannot read is greyed out AND says WHY, in the visible row**
  (#23, USER-REPORTED). `BL_JUNCTION_ANGLE_C1` is dead under the default junction method and
  disabling it is correct — the SILENCE was the defect, because on screen a greyed box with no
  reason is indistinguishable from one greyed for another reason, or from a bug. The same `_sync`
  that calls `setEnabled` sets or clears the row's marker, so the lock and its explanation cannot
  disagree; `_FIELD_NOTES` is the ONE declaration of the short text and the long prose stays the
  spec's own `_C1_TIP`, not a copy. Three placement facts are MEASURED, not stylistic: the note
  rides beside the FIELD because the label column is one shared width measured from the labels
  actually built and clamped to `LABEL_COL_MIN`..`LABEL_COL_MAX` (120..240, declared with
  `clamp_label_col` in `mesh_bl_dialog_layout`), which a suffixed C1 label either widens or clips
  inside; the note cell is the ONE composite field cell in the GUI, which is the exemption to
  **"Numeric and combo rows go into the form DIRECTLY, never wrapped"** — what makes it legal, and
  the gate that pins that, are stated with THAT rule above and only there; and a tooltip on the
  disabled widget is impossible, since Qt picks the mouse receiver by walking past disabled
  widgets, so the box gets no `Enter` — nor does its parent.
  **The gate asserts that COST, never a pixel.** SUPERSEDES #23: `suffix_cost` asserts the
  consequence a suffixed label would impose — the shared column grows, or it is already on
  `LABEL_COL_MAX` and the label clips — plus the growth as a RATIO for the magnitude, since a
  width scales with the font and the clamp does not.
  Why: docs/design_notes/gui.md, "A pixel literal is a metric of one machine"
  **An unreadable method value leaves the field LIVE and SILENT**: `_sync`'s
  `except (TypeError, ValueError)` sets `reads_c1 = True` — never stuck off — and an editable field
  has nothing to explain, so no marker is shown; it logs at `debug(..., exc_info=True)`, its only
  other trace being a field that quietly stopped greying out. Gated by
  `tests/test_bl_dialog_sections.py` check 14, which binds "disabled ⇔ a non-empty reason showing"
  in BOTH directions, proves itself non-vacuous by re-running the real pre-fix wiring, and patches
  `by_key` to hand the build a C1 spec whose label already carries the reason, so the column check
  is shown going red; plus check 15, which raises from `_widget_value` for the junction combo at
  all THREE arrivals (the build, and a real index change each way) — the fallback path both
  shipped methods never take.
  **The composite cell is what mode-hiding must hide**: `mesh_bl_dialog_layout` hides `cell`, not
  `w`, or a row the active `MESH_MODE` does not read leaves its note showing beside nothing.

**A geometry in the mesh config is the FILE it names, not the string that names it**
(`services/geom_path_identity.py`, Qt-free — `canonical_geom_path` / `same_geom_file` /
`canonical_geom_keys` / `dedupe_geom_paths` / `stored_geom_path`; the model's verbs are
`models/mesh_config_geoms.py::GeomListMixin`, split off
when `mesh_config.py` went over the file-size budget). Every dedup guard in the tree used to be a
`not in` string compare over `MeshConfig.geom_files`, so the repo-relative and absolute spellings
of one file were two entries: the Mesh Generator listed the geometry twice and the mesher was
handed a doubled boundary — USER-REPORTED (2026-08-20), reopening an exported case package, which
is exactly the case that mixes spellings (the workspace stores relative, the panel computes
absolute). Two rules:

- **The base is the repo, never the process cwd.** `os.path.abspath` is cwd-relative, so one
  stored entry named a different file depending on where the GUI was launched from (measured:
  `<repo>/results/...` from the repo root, `/private/tmp/results/...` from `/tmp`). Every relative
  path this app stores is repo-relative — that is what `mesh_config_io` writes.
- **Canonical means realpath**, so a symlinked scratch dir or a case-insensitive volume cannot
  reintroduce two-strings-one-file. Identity by inode (`case_workspace`'s rule) is stronger but
  needs the file to EXIST, and the whole point here is entries that may not.

Both of those are about COMPARING two spellings. Four more say how one is WRITTEN DOWN and READ
BACK — the three residues #104 closed, plus the read-side rule that closing them exposed:

- **What goes INTO the list is `stored_geom_path`, never `os.path.abspath`** — repo-relative for a
  file inside the repo (the spelling `mesh_config_io` emits and a workspace carries, so the model,
  the config and the script agree and a case package stays portable), canonical absolute for one
  outside it. The callers used to store what `abspath` returned, i.e. the exact cwd-relative
  spelling the first rule condemns; nothing was broken by it because every comparison
  canonicalises, but a stored `<cwd>/results/…` stops naming the same file the moment the GUI is
  launched from elsewhere. Gated by `tests/test_geom_files_identity.py` check 9, by AST over
  `add_geom_file` / `set_geom_files`.
- **A reader RESOLVES an entry before opening it**: `os.path.exists(gf)` / `np.loadtxt(gf)` on the
  raw string answers about the process cwd. This is what makes the repo-relative store above safe
  rather than a silent "the preview vanished", and it is TWO rules, not one, because the readers
  are two kinds:
  - The five that open the geometry itself resolve at the call site with `canonical_geom_path` —
    the Run-All pre-flight, the mesh bbox scan, the BC canvas overlay, the preview loader thread
    and the selection highlight.
  - **A path the USER gave is the one thing `os.path.abspath` is still right for**: a CLI argument
    or a dialog result really is cwd-relative, and the load beside it reads it that way. Resolve
    it with `abspath` FIRST and derive the entry from THAT (`stored_geom_path(abs_path)`) —
    resolving the raw spelling against the repo instead makes the session load one file and list
    another. `session_load_ctrl` is both such sites.
  - **A `.meta` sidecar belongs to the FILE, and `meta_io.meta_path_for` is where that is
    decided** — not at its callers. Nine sites across the panels, `mesh_layers_ctrl` and the
    `.bnd` audit reach a sidecar; converting them one by one is the shotgun-surgery version of
    one rule, and the WRITE half is the dangerous one — `write_meta_group_bc` on a raw
    repo-relative entry drops a stray sidecar under the cwd while the real one keeps the old BCs,
    i.e. the all-`wall` grid this repo has already shipped once. Driven end to end from a foreign
    cwd by check 9, which also asserts nothing was written under it.
- **The canonical-key loop is written ONCE**, in the service's `_keyed`; `dedupe_geom_paths` and
  `canonical_geom_keys` read it, and the model's `add_geom_file` asks `has_geom_file` rather than
  re-deriving the key. Three hand-written copies of one canonicalisation rule is how the
  string-compare defect got in. That is the MEMBERSHIP shape only: `remove_geom_file` and
  `role_of` still compare per entry, deliberately — `_keyed` drops a falsy entry, which is right
  for a dedupe and would silently make `remove_geom_file` delete empty entries as a side effect of
  removing something else.
- **The identity import is at MODULE level everywhere**, and the absence of a cycle is MEASURED —
  `mesh_config_io` (the module that carried the deferred form, and is on the headless path)
  imports first in a fresh interpreter, dragging in no Qt. A deferred import hides a real
  dependency: that is `test_qt_free_seam`'s own lesson, where an import-time sweep was green while
  `run_pipeline.sh` still died on three function-body imports. Gated by check 8, at any nesting
  depth.

**Addition, removal and membership are ONE verb set, and no caller outside the mixin may reach
`geom_files` by any other route** — they move together, because half of them converted is a config
that adds a layer by identity and un-adds it by string. The set is `add_geom_file` /
`remove_geom_file` / `has_geom_file` / `set_geom_files` / `role_of` / `prune_roles` /
`dedupe_geom_paths`, and **`tests/test_geom_files_identity.py` check 7 fails the build on EVERY
raw way in over `geom_files` outside the mixin**: the eight list mutators (`append` / `remove` /
`extend` / `insert` / `pop` / `clear` / `sort` / `reverse`), `in` / `not in`, a wholesale
`cfg.geom_files = [...]` rebind, a slice rebind, a `del`, a literal
`setattr(cfg, "geom_files", …)` and a `geom_files=` keyword to `MeshConfig(…)` or
`dataclasses.replace(…)` — by AST, because the prose
recording the rule names every construct it forbids and a substring scan fires on that. Its
allow-list is DERIVED from where the verbs live (`inspect.getsourcefile`), which is how it noticed
them moving into the mixin and is why `models/mesh_config.py` — the config class itself — is **not**
exempt. **Each new door must be shown to fail the BUILD, by injection into a real GUI package with
the verdict read from the child's exit code** and a negative control on the untouched tree; the
first widening proved only the rebind, and the constructor keyword — which reaches the dataclass
field with no assignment and no method call anywhere — was then found by review, not by the scan.

- **Replacing the whole list is `set_geom_files`, and only the mixin may rebind** (#99). It
  dedupes by identity and keeps the caller's spelling, so a list rebuilt from widgets or from a
  restored workspace cannot put back the state `add_geom_file` removed; a falsy entry is dropped,
  as the mesher-config writer already did. It also drops the alias a rebind left — the restored
  `dict`'s own list is no longer the config's. Five callers outside the mixin were rebinding when
  the scan gained the construct (`mesh_config.load_from_dict`,
  `mesh_config_io.load_config_from_file`, `pipeline_config.build_mesh_config`, `pipeline_io_ctrl`
  and the mesh panel's config mixin), one of them a `[os.path.abspath(out)]` of the kind
  `geom_path_identity` exists to replace. A sixth site matched the NAME without being this list —
  see the next rule.
- **A class outside the model may not name an attribute `geom_files`.** The scan matches by
  attribute NAME, since an AST cannot resolve the type of `self`; `mesh_canvas_loader`'s thread
  therefore holds `self.paths`. Renaming the neighbour is the fix, never an allow-list entry — one
  exemption keyed to the verbs is checkable, a growing filename list is not.

Why: docs/design_notes/gui.md, "Shipping only the ADD sites was worse than not starting"

Two things the fix deliberately does NOT do: `dedupe_geom_paths` keeps the FIRST spelling rather
than rewriting entries to canonical form (that would churn a saved config on load, and
`pipeline_config` regressed a test by trying it — `/tmp` became `/private/tmp`), and `validate()`
stays PURE, so "is this file on disk?" is `geom_files_not_on_disk()` and not a validation error.
That method is **not** `missing_geom_files`, the field one word away on the same class: the field
holds `GEOM_FILE` tokens a `.dat` read could not resolve at all.

## Named blind spots

Consolidated here rather than trailing the rules they belong to, so a coverage claim can be checked
against one list; #71 moved the first two here.

- **`config_ownership` is Qt-free at IMPORT only.** The SOLVER and IB tables still live under
  `views/panels/`, whose package `__init__` eagerly imports eight Qt panels, so a
  `preserved_fields()` call naming those two still loads PyQt6 — the Qt-free gate reaches
  `services/field_spec.py` only.
- **The unit size-plausibility check only catches gross errors, and says so.** A *plausible* wrong
  unit is left to the two visible defences above, which do nothing but print the number.
- **`MODEL_WRITER_METHODS` fails on a STALE entry, never on a MISSING one.** The gate proves every
  declared verb resolves; nothing notices a *new* model verb that writes a field and is not listed,
  and the symptom is silent — the field reads as unauthored, so the sync preserves it and the
  panel's edit is dropped. The gate's check that at least one field is verb-authored keeps the map
  from being deleted wholesale, not from being incomplete.
- **The geometry-identity scan is NAME-based and TREE-scoped**, so five things stay outside it.
  (i) It cannot tell `MeshConfig.geom_files` from any other object's attribute of that name — it
  over-reaches (hence `mesh_canvas_loader.paths`) and would under-reach an ALIAS,
  `lst = cfg.geom_files; lst.append(p)`. Nothing in the tree aliases the list, and nothing here
  would notice if something started. (ii) A name it cannot read as a literal: a computed
  `setattr(cfg, name, …)` or `getattr(cfg, name).append(…)` passes, where the literal
  `setattr(cfg, "geom_files", …)` fails. (iii) A DUNDER called directly —
  `cfg.geom_files.__setitem__(0, p)`, `__iadd__` — is not in the mutator list; the subscript and
  `+=` FORMS those spell are caught as syntax, and nobody writes the method call. (iv) The
  `geom_files=` keyword is scoped to `MeshConfig(…)` and `dataclasses.replace(…)`, so a
  differently-named factory building the config, or a `**kwargs` splat, passes — the alternative
  was firing on the NINE functions here that take an ordinary `geom_files` parameter, and a gate
  that red-lights `audit_mesh_bc(bnd, geom_files=…)` gets worked around rather than obeyed.
  (v) It walks
  `.py` files under `gui/app/` only, so a caller in `tools/PreProcessor/`, `tools/scripts/` or the
  tests is unreached — the tests deliberately rebind, to build the stale state under test. Beside
  those, one thing it deliberately does not watch: the per-geometry `geom_roles` dict has no such
  gate, and a role keyed under a dropped spelling is `prune_roles`' job rather than a scan's.
- **The cwd-relative STORE scan (check 9) reads the ARGUMENT, so an indirection passes.**
  `add_geom_file(os.path.abspath(p))` and the same inside a list literal fail; `q =
  os.path.abspath(p); add_geom_file(q)` does not, for the reason blind spot (i) gives — an AST
  cannot follow a value. Two things bound it: the scan is scoped to the model's own store verbs, so
  an `os.path.abspath` for anything else (the recent-files list keeps one, deliberately) is not
  swept up, and check 9's behavioural half asserts what `stored_geom_path` RETURNS from any cwd,
  which no caller can re-implement correctly by accident. **The READ side has no scan at all**, and
  is held by a seam for sidecars (`meta_path_for`) and by nothing at all for the four call sites
  that open the geometry directly: a new `np.loadtxt(gf)` fails no gate, and its symptom is silent
  — a preview that does not draw. The first attempt at #104 converted five readers and left four,
  which is how that reach is known rather than assumed.
