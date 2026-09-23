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

**THE TOPOLOGY TEMPLATE LIBRARY LEFT THIS FILE IN #137**, together with the three mesh-canvas
globs #136 had added for its overlay: four blocks and six blind spots are now
`.claude/rules/gui-topology.md`, which this file's `models/mesh_config*` and `views/panels/**`
globs deliberately OVERLAP, so a session editing the mesh-config panel or the mesher-config writer
loads both. The move was forced by size — 73 characters of slack were left here — and #85's
precedent says a full rule file takes a new file rather than a squeeze. Nothing about the template
is ruled on here any more.

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
`views/panels/result_panel*`, so a reader of one is handed both files),
`views/panels/restart_chooser.py` by `.claude/rules/pipeline-case.md`, and
`views/panels/mesh_stats_panel.py`'s quality-summary rows by `.claude/rules/gui-handoff.md`,
whose own globs name that file too (#131) — what the panel READS from the mesher's provenance
sidecar, and why it shows a blank rather than a number of its own, is a hand-off rule and not a
panel-configuration one. And `models/mesh_config*`
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
`canonical_geom_keys` / `dedupe_geom_paths` / `stored_geom_path` / `readable_geom_path`; the
model's verbs are
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
  - **The SEVEN that need a path only WHEN ONE IS THERE go through `readable_geom_path`** (#111's
    five, #112's sixth, #118's seventh) — entry in, the canonical path when a file is there and `""` when there is
    nothing to open, the existence question answered INSIDE the verb. FIVE of them OPEN the file:
    the mesh bbox scan, the BC canvas overlay, the preview loader thread, the selection
    highlight and the mesh panel's auto-sizing hint reader (`mesh_sizing_mixin._hint_points`, ONE
    reader for both hint scans — until #118 they handed the RAW entry to `np.loadtxt` and
    discarded the failure, breaking this rule and the count in one place). The other TWO open nothing — the Run-All readiness check only asks whether any
    entry is there, and `mesh_layers_ctrl.add_all_sessions_to_mesh` adds an exported geometry to
    the config when its file is there, which is why #111 correctly left it — but they ask the same
    question, so they use the same verb, and converting the second is what lets check 12 below be
    green with nothing pinned. Existence
    is `os.path.exists` and NOT `isfile`/`os.access`: **a file that exists and still cannot be read
    is the OPEN's failure, so each of the five that OPEN must name the FILE and the EXCEPTION when
    it fails** — four at `warning` through `get_logger(__name__)` (the grade for a failure that
    silently degrades what the user asked for: an overlay that does not draw, a highlight that
    does not appear, a geometry missing from the bbox, a hint whose number is computed from fewer
    geometries than the user listed), the loader thread onto stdout beside its
    own malformed-geometry line. SUPERSEDES #112: that clause was an assertion, false of the BC
    overlay and the selection highlight from the day it was written; #117 fixed the readers, not
    the claim. Why: docs/design_notes/gui.md, "can turn a correct silence into a swallowed"
    Gated by `tests/test_silent_exceptions.py` checks 7–8 against a REAL unreadable file, holding
    both halves: an ABSENT geometry must still produce NO record, so the two cases stay
    distinguishable instead of both becoming noisy.
    **The verb stays at the PATH layer** — it does not load, and does not absorb the preview
    loader's NaN/`(N,2)` validation (`geometry_service.load_points_dat`). **No plural form**,
    because only one of the SEVEN would write the comprehension: the bbox scan and the overlay
    need the stored spelling for their log line and their role test as well as the path. A falsy
    entry reads back as `""`, the shared derivation's own answer, so one filter covers both.
    **A site that needs the canonical path even when the file is ABSENT is not one of these** and
    must not use the verb — `mesh_layers_ctrl`'s layer list labels a missing entry by basename,
    and `geom_files_not_on_disk` answers the inverse question over the whole list. Check 11 holds
    the verb's contract, from a FOREIGN cwd; the conversions themselves are behaviour-preserving by
    construction and are held by the GUI gates that already run. **Check 12 holds the REACH**
    (#112), by AST over the same tree: a reader that canonicalises and then asks the filesystem
    itself, or hands a raw `geom_files` entry to it, fails the build. It bans the QUESTION and not
    the shape — an existence call on a canonicalised entry is a violation only when that entry is
    used NOWHERE but the branch where the file turned out to be there, the guard-clause spelling
    (`if not exists(q): return`) counted the same as the indented one — because a flat shape ban
    red-lights the three sites above that need the path when it is ABSENT in order to find the one
    real reader, and the exemption it would then need is the filename list the derived allow-lists
    exist to avoid. A read that PRESUPPOSES existence (`open`, `np.loadtxt`) needs no such
    discrimination and always fails. The allow-list is the module that DEFINES the verb, read off
    the function rather than named, and it is load bearing: `readable_geom_path`'s own body is the
    banned shape.
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
- **The canonical-key loop is written ONCE**, in the service's `keyed_geom_paths`, whose own
  docstring names its THREE readers rather than leaving them to be grepped for —
  `dedupe_geom_paths`, `canonical_geom_keys` and the model's `geom_files_not_on_disk` — and states
  that every other verb reaches the loop through the first two (`has_geom_file` hence
  `add_geom_file`, and `prune_roles`, through the keys; `set_geom_files` hence the workspace
  restore, and `mesh_config_io`'s GEOM_FILE writer, through the dedupe). Three hand-written copies
  of one canonicalisation rule is how the string-compare defect got in. **The THREE verbs that ask
  an identity question and do NOT read it say so AT THE CODE**, and the helper's list says it back:
  `remove_geom_file` compares through `same_geom_file`, because the keyer drops a falsy entry —
  right for a dedupe, and a removal that did it would delete the empty entries BESIDE the one it
  was asked about; `readable_geom_path` asks about ONE entry for that same reason, and its callers
  hold the spelling beside the path, so a list still reaches it per entry; `role_of` walks
  `geom_roles`, a different container, against the key it has already derived. Gated by check 7: a removal leaves a falsy entry alone — shown non-vacuous
  against the keyer-delegation it argues against, not against a state the tree can reach —
  `remove_geom_file("")` removes nothing and returns False, and removing a geometry the list does
  not hold reports that nothing went.
- **TWO behaviours here arrived UNDECLARED, and both are KEPT rather than reversed** (#121):
  - **`keyed_geom_paths` is a public surface this batch did not sanction.** #108's Implementation
    Decision reads *"The only new module-level surface is one read-side verb in the Qt-free
    geometry-identity service"*; that verb is `readable_geom_path`, and #110 had already promoted
    `_keyed` beside it, so the batch added TWO. Kept because "written ONCE" above is only checkable
    against a NAMED list of readers, which a private helper cannot carry where a reader of the
    model's verbs looks for it. The cost is the blind spot below: check 12 shipped recognising ONE
    canonicalising name, so the banned shape written through the second was invisible — with an
    instance of it already in the tree — until #119 MEASURED the verb set off the module.
  - **`remove_geom_file("")` CHANGED its answer, and the bullet above states only the answer it has
    NOW.** Before #110 the verb canonicalised both sides, so a falsy argument canonicalised to `""`,
    matched every falsy entry and stripped them ALL, reporting True. Gated by
    `tests/test_geom_files_identity.py` check 7.
    Why: docs/design_notes/gui.md, "Two MORE of #110's changes were undeclared"
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
  see the next rule. **Routing `load_from_dict` through it has four consequences, and check 10 holds
  all four** rather than the comment beside the call describing them: a workspace listing one file
  under two spellings restores as ONE entry, a null or empty entry is dropped instead of restoring
  a nameless geometry, the restored list is a copy (mutating the dict no longer mutates the
  config), and a JSON null for the list lands as `[]`. The first three arrived as an undeclared
  consequence of the routing and are each shown non-vacuous by re-running the rebind they replaced,
  on the real model, through the public restore API; the fourth is the one that rebind also got
  right, with its `or []`, so no injection is claimed for it.
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
against one list; #71 moved the first two here, and #137 took the template library's six to
`.claude/rules/gui-topology.md` with the rules they belong to.

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
  which no caller can re-implement correctly by accident. **Every side that OPENS a file now has a
  seam AND a scan** — `meta_path_for` for sidecars, `readable_geom_path` for the geometry itself,
  and check 12 for both of that verb's reach-arounds (#112). What that check still cannot see,
  enumerated rather than summarised because "the rest is covered" is the claim this list exists to
  stop being made:
  - **An INDIRECTION**, the same AST limit as (i): a canonical path handed to a helper, returned
    to a caller, or stored on `self`. It follows a plain `v = canonical_geom_path(…)` binding
    inside ONE function scope and nothing further — so a walrus, a tuple unpack and a closure
    reading its enclosing function's binding all pass too.
  - **The existence ANSWER bound to a name**: `q = canonical_geom_path(p); ok = os.path.exists(q);
    if ok: use(q)`. The ternary and `if` spellings of that same guard DO fail, so this is a
    spelling gap rather than the "an AST cannot follow a value" one above — it would take a second
    dataflow layer, over the boolean rather than over the path, and it is not there.
  - **A filesystem call whose NAME is outside the two lists it carries**
    (`pathlib.Path(canon).read_text()`, `shutil.copy`, `os.path.getatime`), and an ALIASED import
    of the canonicalising verb. Both lists name what this tree actually asks about a geometry, not
    every way to touch a file. `cfg.geom_files[0]` handed straight to a call IS covered, alongside
    the loop and the comprehension.
  - **A canonical path reached through the LIST-WIDE verbs by more than ONE step**, which is the
    form that was already in the tree behind the second verb. "Canonicalise" is not one verb:
    `keyed_geom_paths` became public in #110 and check 12 shipped in #112 still recognising the one
    name it was written for, so the banned shape written through the second one passed. Since #119
    the set is MEASURED off `geom_path_identity` — call each exported verb with one spelling whose
    canonical form is known, keep the verbs whose answer contains it, and record WHERE in that
    answer the path sits — so `keyed_geom_paths` and `canonical_geom_keys` are seen wherever
    `canonical_geom_path` is, bound by an assignment OR by the `for`/comprehension target that
    iterates the call, and a THIRD verb needs no edit to the check. The measured POSITION is what
    splits a pair: `keyed_geom_paths` yields `(key, the spelling it came from)`, so the key binds as
    an identity and the spelling as the RAW entry it is — `os.path.exists(spelling)` fails just as
    it does for the same entry taken off the list directly. One step past that is not followed, the same AST limit as (i): `keys =
    canonical_geom_keys(…)` and then a loop over `keys` passes. `readable_geom_path` measures as
    canonicalising too and is removed again — it is the sanctioned route TO the filesystem, and
    five of its seven callers open what it hands back. The verbs that answer with a SPELLING
    (`dedupe_geom_paths`, `stored_geom_path`) or a bool (`same_geom_file`) fall out of the
    measurement, and the gate proves that by scanning the same reader written through each of them.
  One limit is DELIBERATE rather than residual: a site that uses the canonical path where the file
  is ABSENT is silent by construction, so a reader that should delegate but also logs the missing
  path passes. That is the same property keeping the three correct `mesh_layers_ctrl` sites green
  **and the model's own `geom_files_not_on_disk`** — which reads the key through `keyed_geom_paths`
  and asks `os.path.exists` about it, i.e. writes the banned shape, and is green because it asks
  which entries are NOT there rather than because it is pinned. Precisely: a NEGATED guard whose
  file-is-there branch is empty. That is the whole of what #119 subtracted; a non-negated guard is
  judged as before, by whether the entry is used anywhere but the branch where the file turned out
  to be there, so `q = canonical_geom_path(…); if os.path.exists(q): return True` still fails. It was bought knowing the cost —
  the measurement that decided it (five canonicalise-then-exists sites in that one file, of which
  one was the defect) is in `docs/design_notes/gui.md`.
