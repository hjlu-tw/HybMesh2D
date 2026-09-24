# PreProcessor GUI design notes

Long-form rationale extracted verbatim from `CLAUDE.md` on 2026-08-28, when that
file was condensed to its rules. (The reason this line used to give — a 150k-char
context limit — is false; `CLAUDE.md`'s header block carries the measured behaviour
and keeps the superseded claim as a specimen. #60.) Nothing here was rewritten:
this is the original prose, with its measurements, dated
acceptance runs, injections and named blind spots. `CLAUDE.md` carries the rule —
except where #59 has moved an area's rules out to an on-demand `.claude/rules/*.md`
file, loaded when a matching file is READ. **Which rules live where is `CLAUDE.md`'s
tripwire table, and only that table.** This paragraph used to enumerate the areas and
their tickets, and it went stale on #64, #65, #66 and #67 in turn — once per ticket,
every time for the same reason: it was a second copy of a list that already exists.
Replaced by the pointer, which is the only version of this that has held (the same fix
#65 applied to `docs/agents/domain.md`). This file carries why it is the rule.

### PreProcessor GUI (`tools/PreProcessor/gui/app/`)
Layered PyQt6 application:

- **`controller.py`**: Top-level orchestrator; command pattern for undo/redo, delegates to specialized controllers
- **`controllers/`**: Business logic split by concern — `segment_ctrl.py` (CRUD, properties), `session_ctrl.py` (save/load), `session_io_ctrl.py` (`.hws` workspace read/write + `WORKSPACE_FORMAT_VERSION` migration), `project_state_ctrl.py` (the workspace's `project` section: Mesh/Solver/IB config + baseline-snapshot dirty detection), `backend_ctrl.py` (runs `surface_resampler` in QThread), `mesh_gen_ctrl.py` (runs `HybMesh2D` in QThread), `mesh_config_io_ctrl.py` (the mesher's own `.dat`, read and written through a file dialog), `lifecycle_ctrl.py` (autosave, crash recovery, bounded worker shutdown), `curve_ctrl.py`, `transform_ctrl.py`
- **`models/`**: `segment.py` (`type`, `strategy`, `parameters` incl. `spacing` for distance-based resampling, curve fields, plus the two per-segment facts the MESH stage edits — `bc` and `grow_bl`, see "A re-save of the geometry" below; serialized via `to_dict()`/`from_dict()`, which is the ONE serialiser behind the resample config, the workspace and the pipeline script), `project.py`, `mesh_config.py` (+ `mesh_config_keys.py`, `mesh_config_io.py`, `mesh_output_names.py` — see "The Output field's `.*`"), `session.py`, `vtk_mesh.py`, `result_data.py` / `tecplot_index.py` / `result_series.py` (see "Transient results" below). Note: auto-split is computed in the GUI (producing explicit `split_indices`); the per-segment `auto_split`/`split_threshold` keys are read by the C++ backend (`src/cli.cpp`) for hand-written/CLI configs but are not emitted by the GUI. Exported JSON carries a `format_version` field (`CONFIG_FORMAT_VERSION`).
- **`views/`**: `canvas.py` (pyqtgraph interactive geometry canvas, dark theme), `mesh_canvas.py` (mesh visualization), `main_window.py` (tab layout), `sidebar.py` (segment property editor), `panels/` (tab panels per workflow)
- **`commands/`**: `segment_cmds.py` (`UpdateSegmentStateCmd` snapshots full state dict), `split_cmds.py`, `vertex_cmds.py`, `config_cmds.py` (`UpdateProjectStateCmd` — snapshot of the Mesh/Solver/IB configuration)

**Stage config data flow is one-directional** (`controllers/panel_sync_ctrl.py`): the
**model is the truth, the panel is a view**.
- **panel → model**: `sync_panel_to_model(panel_attr)` runs on *every* user edit (the
  widget-introspection traversal in `undo_ctrl._wire_widget_edits` calls
  `on_panel_edited`, which syncs first and then schedules the undo snapshot). So
  `global_mesh_config` / `global_solver_config` / `global_stl3d_config` are never stale;
  nothing should read a panel widget to get a config value.
- **model → panel**: `push_panel_config(panel, cfg)` (undo-suppressed), as before.
- `PRESERVED_FIELDS` lists what each panel does **not** author and must never overwrite
  (e.g. the solver panel has no widget for `length_unit`, so a wholesale copy would wipe
  it and take `Linf` with it). `tests/test_panel_model_sync.py` proves each set equals
  what that panel's `get_config` actually assigns, **by AST** — so a model field added
  without a widget fails the build instead of silently going stale or being wiped.
- A model may define `normalize()` to restore its own invariants after a sync (SolverConfig
  re-derives `linf` from the preserved unit).
- **`set_config` sets the panel's own `_loading` flag under try/finally**, and the sync
  checks *that*, not the caller's discipline: a direct `set_config` that forgets
  `push_panel_config` must cost at most a spurious undo step, never a corrupted model.
  New panels must follow the same `set_config` / `_set_config_body` split.

**A config field is declared ONCE, in its panel's field-spec table**
(`app/services/field_spec.py` is the Qt-free record + the pure questions asked of a
table; `views/panels/field_widgets.py` is the one kind→widget mapping and the three
traversals; the tables are `services/mesh_field_specs.py` +
`services/mesh_bl_field_specs.py` and `views/panels/solver_field_specs.py`,
`views/panels/stl3d_field_specs.py` — the two MESH tables live in `services/` because
the `.dat` key map derives from them, see "The GUI's `.dat` key map is derived" below;
their old `views/panels/` paths survive as re-export shims so the ~11 Qt-side call
sites are unchanged). Each panel used to be cut in half —
one half BUILT widgets, the other read and wrote them against a model — with the whole
widget set as the implicit interface: **176 attributes across five build mixins, named
back by hand in 246 read/write lines**, agreeing only because both halves spelled the
same name. One BL knob (`BL_TRANSITION_BUFFER`) was named 16 times across 7 GUI files,
four of which were parallel lists over the same 21 fields. A spec carries `attr` ·
`kind` · `label` · `tip` · `model` · `key` · `group` · `opts`; the table is walked once
to build (`add_spec_rows`), once to write (`write_specs`) and once to read
(`read_specs`). Rules that are load bearing:
- **`get_config` / `set_config` / `_set_config_body` were NOT touched as verbs**, nor
  was `panel_sync_ctrl` — the frozen review lists both under *"Genuinely deep — leave
  these alone"*. The table sits BEHIND those three, and the panel-owned `_loading` flag
  and its `try/finally` are unchanged.
- **`PRESERVED_FIELDS` is a subtraction, not a list**: model fields − table − the
  residue each panel declares beside its table (`*_EXTRA_AUTHORED`, for facts one
  widget holds for many things — the geometry list, the BC-definition table). What is
  left to prove is that the declared residue equals the code still written by hand.
- **The ownership scan reads SYNTAX, so a field written only through a model VERB reads
  as unauthored** — and "unauthored" means the sync *preserves* it, i.e. discards what
  the panel just built. `config_ownership.MODEL_WRITER_METHODS` declares the method →
  field map, and #99 is what made that real rather than theoretical: making `geom_files`
  verb-only outside the model removed the mesh panel's bare `cfg.geom_files = []`, and
  the panel's own `cfg.add_geom_file(p)` beside it had ALWAYS been invisible to the scan
  — the assignment was the only thing keeping the answer right. Declared rather than
  guessed from the name, because `add_geom_file` does not spell its plural field.
  `tests/test_field_spec_tables.py` check 2 fails on an entry naming a method or a field
  that no ONE model class carries together, and asserts at least one field is
  verb-authored with no assignment in that panel's own `get_config`, so the map cannot be
  deleted wholesale and pass. An entry may be INERT and that is legal:
  `remove_geom_file`'s callers are in `controllers/mesh_layers_ctrl.py`, outside every
  `PANEL_SOURCES` glob. The recorded blind spot is the direction it cannot fail in — a
  STALE entry fails, a MISSING one does not, and a new model verb that writes a field and
  is never listed has the silent symptom above.
- **`LENGTH_FIELDS` is derived from `kind == "sci"`**, which IS the physical-length rule
  (`SciDoubleSpinBox`, no floor, decade steps), so the list and the widgets cannot
  disagree.
- **Widgets are seeded from the model's defaults**, not from literals repeated in build
  code. Measured: a fresh panel used to report BL layers 0, growth 1.001, Gmsh
  MeshAdapt, CFL 0, all-`inlet` outer BCs and a 0..0 STL3d domain; it now reports the
  dataclass values. That is the `_STARTUP_OK` bug class closed at its source.
- **A choice is matched by VALUE in Python, never `findData`** (QVariant comparison
  makes a bool `False` against an int `0` datum a coin toss), and a value the combo does
  not offer falls back to a *declared* one instead of landing on index 0.
- **Numeric and combo rows go into the form DIRECTLY, never wrapped**:
  `QFormLayout.labelForField` only finds a label for the widget that IS the field cell,
  and four visibility helpers use it to hide a row's label with its field.
- Three escape hatches exist and each is used by exactly one field, named with its
  reason in the gate: `read`/`write` on a spec (`ascii_combo` — three items behind a
  bool), `panel_choices` (`bl_concave_method` — the panel's backing combo offers only
  method 5 because method 0 is CLI-side), `host_writes` (`output_filename` — population
  is a heuristic that reads the widget's own text).
- **One spec means one tooltip**, so a form label's '?' now shows the field's full
  explanation rather than a shorter summary (~40 rows). The alternative — a second
  `label_tip` on every spec — is the duplication the candidate removes. The Edit-BL
  dialog's '?' shows that prose **plus the `.dat`/`Config.hpp` KEY**: the KEY used to be
  the ONLY help 20 of the 21 fields had, and giving every spec a tip silently killed the
  `spec.tip or key` fallback (found in review, now gate check 12).
- **`services/field_spec.py` is Qt-free and gated; `config_ownership` is Qt-free at
  IMPORT only.** The MESH tables are now genuinely reachable headlessly (they had to
  be — see below), but the SOLVER and IB tables still live under `views/panels/`,
  whose package `__init__` eagerly imports eight Qt panels, so a `preserved_fields()`
  call naming those two still loads PyQt6. Do not read the deferral as "answerable
  headlessly" for every panel; it keeps the `services/` sweep honest, and for the
  mesh panel it is now more than that.
Gated by `tests/test_field_spec_tables.py` (twelve properties, every static one verified
by injection, each injection asserting the mutated source still PARSES and really
changed).
Behaviour preservation was measured against `f97213a` via `git archive`: the solver and
IB panels' form structure is row-for-row identical (70/70 and 7/7), all 25 differing mesh
rows are inside the four `setVisible(False)` BL backing sections, and every panel's
`set_config` → `get_config` round-trip is byte-identical. `test_panel_model_sync.py`
stayed green throughout and lost only its check 1, which became a tautology once both
sides of that equality were the same declaration.

**The GUI's `.dat` key map is DERIVED from the field-spec tables**
(`models/mesh_config_keys.py`): 45 of its 49 `KEY -> (attribute, converter)` entries
come from the tables (`spec.key` + `spec.model`), the converter comes from the model
field's own dataclass type via `field_spec.model_types()`, and the 4-entry residue is
declared with a reason each. It used to be 49 hand-written entries restating both
facts, in a file with no way of knowing when a table changed.
- **The two mesh tables MOVED to `services/` for this, and the reason is the seam.**
  They are intrinsically Qt-free (they import only `dataclasses`, `MeshConfig` and
  `field_spec`), but any module under `views/panels/` drags in that package's
  `__init__` and its eight Qt panels — measured: importing either table with PyQt6
  blocked raised ImportError — while `mesh_config_keys` is on the HEADLESS path
  (`mesh_config_io.config_to_text` ← `run_pipeline.sh` / `run_batch.sh`). A spec
  import without the move would have made PyQt6 a requirement of a compute node that
  never draws a window.
- **The cost is recorded rather than hidden**: ~250 lines of UI text (labels,
  tooltips, one `_HINT_STYLE` CSS string) now sit in `services/`, which weakens the
  "the tables carry UI text so they live under `views/`" reasoning this file used to
  give for their location. The Qt-free RULE is unaffected and still gated; what
  changed is the rationale, and the trade was taken deliberately — deriving the map
  is worth more than the tidiness of where UI copy lives. The solver and IB tables
  did NOT move: nothing headless derives from them.
- **`_KEY_MAP` is anchored to the WRITER, not just to the tables** (gate check 13f,
  both directions, with the four structural keys — `GEOM_FILE` / `DOMAIN_FILE` /
  `SEED_FILE` / `GROUP_BC` — declared). Checking only "map agrees with tables" was
  measured BLIND: removing a spec's `key=` left both sides agreeing with the
  parameter gone from each, while the writer kept emitting the line and the reader
  could no longer read it back. `test_gui_cpp_config_parity.py` cannot see that
  either, since the writer's f-strings are independent of the map.
- Deriving the map made `mesh_config_keys` depend on `MeshConfig`, i.e. the cycle the
  module was split out to avoid, pointing the other way. `mesh_config.py` therefore
  imports the map inside the two methods that use it.

**The edge being edited has an OWNER, and there are TWO edit kinds in it**
(`services/edge_edit.py`, Qt-free — `EdgeEditSession` + `EditOutcome` +
`ShapeOutcome`). Drawing a new **analytic** edge or double-clicking an existing one,
and double-clicking an **imported (discrete)** edge to reshape its whole outline by
the corner vertices, both open a *modeless* session: a numeric dialog and draggable
canvas handles bound live to one segment, committed by **Create Edge** / **Apply**
and reverted by **Cancel**. Between them that was **twelve attributes on
`AppController`** — declared in `controller.py`, begun in `curve_draw_ctrl` /
`file_edit_ctrl`, committed or cancelled in `pending_edit_ctrl` / `file_edit_ctrl` —
with "an edit is live" enforced only by every reader remembering to test for `None`,
and the whole lifecycle unreachable without a canvas, a dialog and a QApplication.
**Both kinds live in one owner because they are alternatives**: at most one may be
live, so `_edit_in_progress()` is now one question with one answer instead of an
`or` repeated at every call site. Three rules:
- **The dialog is held OPAQUELY.** The owner stores it and hands it back; it never
  calls a method on it. What has to be *asked* of the dialog — a polygon's
  open/closed toggle, which is not part of the form's `params` — is read by the
  caller and passed into `update()` as a value. That is what keeps the module free
  of Qt without a wrapper interface.
- **`commit()` / `cancel()` end the session and return an `EditOutcome`; they do not
  decide what it becomes.** Whether that is an `AddCurveSegmentCmd` or a recorded
  `UpdateSegmentStateCmd` stays with the controller, which owns the undo stack. The
  *revert* does live in the owner, because it is the other half of the snapshot it
  took.
- **An edit BELONGS to the CAD session it began in, and leaving that session is a
  transition.** This is the half that was a *defect*, not a shape: nothing cancelled
  a live edit when a tab was switched or closed, while the commit path resolved its
  target through `active_session()` — the tab in front *now*. So committing an edit
  looked the segment up in the wrong session, failed, and fell back to matching by
  segment **id** (the fallback that exists to survive an intervening undo) — and ids
  are per-session, so it landed on **another tab's edge**, recording an undo entry
  whose before-state came from one geometry and whose after-state came from another;
  committing a *new* edge added it to whichever tab was in front. Measured, the id
  collision is worse than "possible": `ProjectModel.renumber_segments` assigns
  contiguous 1..N across both edge kinds, so every tab's Nth edge has id N. Every
  outcome now carries its session and the caller acts on **that** one, and the list /
  selection / window title — which describe the tab in FRONT — are only touched when
  the edit's session *is* that tab. Switching or closing away from a live edit
  **asks**, defaulting to cancelling it (`headless_default=True`, so a batch run
  never blocks and never comes out with an edit pointing at a tab that is gone); on
  close the edit question comes **first**, and declining it aborts the close so the
  unsaved-changes question is never reached. Declining a switch has to **put the tab
  bar back** — Qt moves it and then tells us. And **at most one edit is live** stopped
  being convention: `begin`/`begin_shape` REFUSE while another is live, so the Qt side
  must ask and end the first one deliberately. Refusing is the backstop, not the
  interaction — a module with no Qt cannot put up a prompt and should not decide to.
  `commit`/`cancel` with nothing live is a silent no-op (a dialog signal arriving
  after the state was cleared is a timing artefact, not something the user did):
  `get_logger(__name__).debug`, never a pop-up or a user-log line.
- **An ending the DIALOG did not initiate must close the dialog.** It tears itself
  down through `finished → deleteLater`, which fires only when it closes *itself*;
  a cancel driven by a tab switch, a tab close or a second edit beginning used to
  leave the window on screen with its Apply and Cancel pointing at an owner that had
  forgotten the edit. The dialog therefore travels back on the outcome (the owner
  holds it opaquely and may not call a method on it) and the caller closes it. That
  `close()` **re-emits `rejected`**, so the cancel handler runs again against an idle
  owner — which is exactly the silent-no-op case above, and is why the two rules have
  to land together. And **the canvas clear takes the EDIT's session**: the live
  preview is a canvas item keyed by `session_id`, so aiming it at the front tab
  leaves the preview drawn on the tab the edit belonged to.
- **Not every route out of a session is a prompt.** Switching and closing a tab ask,
  because both are cleanly abortable. Opening a new tab, `reset_all_state` and
  loading a workspace **end the edit unconditionally and say so in the log**: the
  first moves focus as an unavoidable consequence of an action already taken (making
  it abortable would mean `_new_session` — which four call sites dereference straight
  away — growing a failure mode), and the last two have already asked their own
  whole-session question. What the requirement actually demands is that no live edit
  survives pointing at a background or discarded session, which is what these
  guarantee.
- **The committed-edge DRAG is a transition, not a nullable field.** Dragging a
  handle of an already-committed edge (no dialog open — a third modality the other
  two deliberately route drags away from) must collapse one gesture into one undo
  step. That used to be `AppController._drag_orig_state`, filled by the drag handler
  and retired by the *selection/refresh chokepoint* as a side effect, because a
  snapshot left over from a gesture that ended abnormally would otherwise be recorded
  against whichever segment was selected next — and undoing THAT writes one edge's
  shape onto another. It is now `begin_drag` / `finish_drag`, and the rule is a
  property: **a drag belongs to the segment it began on and cannot be finished
  against another**. Two consequences worth knowing: the handler must not
  `begin_drag` on the `finished` event (a gesture cannot begin and end in one event;
  letting it would make a stray finish snapshot the *new* segment and record a
  one-event edit on it — the old code did exactly that), and **a drag is NOT
  `is_active()`**, because the callers that guard on that predicate must keep working
  during one.
- **A corner drag is a value in, an outline out.** The shape session holds the
  pristine points plus the corner POSITIONS, and `move_corner` returns a freshly
  re-fitted array instead of mutating the live one — so every re-fit recomputes from
  the same basis, dragging never accumulates transform onto transform, and Cancel
  restores the points *byte-for-byte* rather than to within a tolerance.
  Its one departure from symmetry is deliberate: the shape side has **`end_shape()`,
  not a commit/cancel pair**, because both endings need the same thing from the owner
  (the snapshot) and differ only in what the caller does with it.
The SHAPE of all this is gated by `tests/test_edge_edit_owner_seam.py` — five
properties, each a function over source so the nine in-test injections run the real
check against mutated text, and each injection asserting the mutation still PARSES
and really differed (a mutation that breaks the parse looks exactly like the check
working). It watches: no modal-edit attribute back on `AppController`; nobody
reaching past the verbs (resolving `self.edge_edit` **and** one-line aliases of it);
the owner Qt-free, proved by DRIVING the whole lifecycle in a **subprocess** with
PyQt6 blocked — in-process the answer is always "Qt is loaded" once another test
imported it — plus an AST read for a *deferred* import at any nesting depth; one
predicate; and both commit paths resolving their session from the outcome. Its blind
spots are named in its own docstring, the sharpest being that check 1 matches
attribute NAMES, so state smuggled back as `self._live` is invisible: it defends
against the cheap regression, not a determined one.

The BEHAVIOUR is gated by `tests/test_edge_edit_owner.py` (the owner's verbs, Qt-free),
`tests/test_committed_drag_undo.py` (the drag wiring) and
`tests/test_edit_session_binding.py` (the cross-tab defect and both prompts) — the
last two on the offscreen Qt platform with the real `AppController`, which is where
the old bugs lived. The session-binding test reaches the wrong-tab state by moving
`active_idx` **directly** rather than through `switch_tab`, on purpose: `switch_tab`
now ends the edit, so going through it would test the prompt instead of the binding,
and the binding is the half that must still hold when some other route changes the
front tab. The first refuses PyQt6 through a meta-path hook (so a *deferred* `import PyQt6` fails too) and then drives the REAL
`PendingEditControllerMixin` / `FileEditControllerMixin` — re-implementing the commit
branch in the test would prove only that a test can add a segment. (It loads both by
file path: `app/controllers/__init__.py` eagerly re-exports eight Qt mixins, the same
hazard `test_qt_free_seam.py` records for `models/` and `views/panels/`, and that is a
property of the package rather than of the module under test.) Every check is verified
by injection. One claim is deliberately narrowed rather than overstated: the params
snapshot is a deep copy, but **no shipped caller mutates a nested parameter in place**
(a polygon carries `vertices_str`, a *string*), so a shallow copy would pass every
live path — the test mutates one directly and says so, pinning the contract rather
than a reproducible bug.

**The outline re-fit is pure arithmetic and has its own module**
(`services/shape_refit.py`, Qt-free — `build_edge_specs` + `refit_shape`). Each edge
of an imported outline re-fits between its own two corners by the similarity transform
carrying its ORIGINAL corner pair onto the current one, so dragging a corner two edges
share redistributes both. It lived inside `FileEditControllerMixin._refit_geom`, read
three `self.` attributes and **had no test at all**; extracting it first is what made
moving the state around it small. Two behaviours it is careful about and which are now
pinned: a **zero-length edge** falls back to a pure translation (the transform's
divisor is the squared length, so without it the interior points divide by ~zero and
leave the canvas), and the **closing edge wraps to index 0** rather than being read as
out-of-range and skipped — a gap that only opens on a *closed* outline, which is most
of them. The extraction was measured, not asserted: 2000 randomised outlines through
both the new function and the pre-change in-place body recovered from git came out
**byte-identical, worst |Δ| = 0**. Gated by `tests/test_shape_refit.py`, whose sort-
order check needed searching for: a CPython set of small corner indices iterates
sorted anyway, *and* the order depends on insertion history rather than the values, so
neither a small outline nor a set literal is a usable oracle — the check uses a layout
found by search over 200k random cuts where the builder's own set really is unsorted.

**Undo is global, across every CAD session AND project settings** (`controllers/undo_ctrl.py`). Histories stay per-`GeometrySession` (plus `controller.project_history`) so closing a tab drops exactly its own commands; ordering across them is by the monotonic `seq` that `CommandHistory._push` stamps — undo takes the highest, redo the lowest waiting on a redo stack. Undo raises the tab owning the command before applying it. Mesh/Solver/IB edits are recorded by debounced snapshot diffing, so a burst of typing is one step. **Any code pushing config into those panels must go through `controller.push_panel_config(panel, cfg)`** (or `suppress_project_undo()`), or the push is recorded as a user edit.
- **`workers/`**: `backend_run.py`, `mesh_gen_run.py` (QThread wrappers for CLI subprocesses), `proc_util.py` (shared `popen_kwargs()` with `start_new_session`, plus `stop_process`/`stop_process_async` SIGTERM→SIGKILL escalation over the child's process group — every worker `cancel()` must route through these, never a bare `terminate()`)

**Subprocess environment**: `services/env_setup.py::mesher_env()` resolves the libgmsh directory (override: `HYBMESH_GMSH_LIB_DIR`) and must be passed as `env=` when launching `HybMesh2D`/`surface_resampler`. Inheriting it from a shell wrapper does **not** work — macOS SIP strips every `DYLD_*` variable when a protected `python3` starts, so `run.sh`'s export never reaches a Python-launched child. `tools/scripts/gmsh_lib_dir.sh` is the shell-side equivalent, sourced by `run.sh`/`run_pipeline.sh`. **Where Gmsh actually is has ONE answer: `tools/scripts/gmsh_sdk_dirs.py`** — the shell helper and `CMakeLists.txt` (which also needs `gmsh.h` at configure time) both resolve through it by asking the installed wheel. The CMake side used to carry a fixed HINTS list naming one developer's macOS pip prefix, and a pip prefix is per-machine: **CI installed gmsh and then failed at configure with "Gmsh SDK not found", and because the test job is `needs: build` the entire regression suite was SKIPPED rather than run — the workflow had never once been green.** A hardcoded absolute path in a discovery hint is worth treating as a defect on sight. The second half of the same bug was the LIBRARY name: the Linux wheel ships `lib/libgmsh.so.4.15` with no unversioned `libgmsh.so` symlink, so `find_library`'s `NAMES gmsh gmsh.4.15` (which become `libgmsh.so` / `libgmsh.4.15.so`) match nothing, while macOS's `libgmsh.4.15.dylib` matches — the build worked on the developer's machine and nowhere else. The resolver therefore reports `LIBFILE=` (the file it globbed) and CMake falls back to it, rather than teaching NAMES another platform's spelling and baking the version into a second place. The workflow first went green on 2026-08-17 (`4254c5d`), and what that covers is worth knowing: **69 Python tests + `ctest` 2/2 in the build job + the end-to-end `run_pipeline.sh`, none of which had ever executed in CI before**. Getting there took four unrelated environment defects and one flaky runner, and not one of them was a defect in the code under test — the lesson is that a workflow's *history* is the only evidence it gates anything.

**`app/utils.py` is the Qt side of a seam, and the pure helpers now live on the
other side** (`services/paths.py`, Qt-free — `repo_root`, `find_binary_executable`,
`find_solver_executables`, `find_stl3d_binary`, `find_mpi_launcher`, `is_mpi_binary`).
`app/utils.py` was a namespace rather than a module: message boxes, signal guards,
pop-up stacking and form builders, then a third of pure `os`/`shutil` path resolution,
one name, and that name sits on the Qt side. So **every headless module that needed a
path imported the whole GUI toolkit** — `import app.services.pipeline_runner` loaded five
`PyQt6` modules four lines below its own comment reading "no PyQt import, so this module
stays headless-safe", and `run_pipeline.sh` / `run_batch.sh` required PyQt6 on a compute
node that will never draw a window. `app/utils.py` **re-exports** the moved names, so the
~16 Qt-side call sites are untouched; only the Qt-free layers were migrated.
`is_headless` deliberately **stayed** with the Qt helpers — it asks which Qt platform
plugin is running, so it belongs there even though its own `QApplication` import is
deferred into the function body. Two things the gate
(`tests/test_qt_free_seam.py`) had to learn the hard way:
- **The check must be a subprocess.** In-process the answer is always "yes, PyQt6 is
  loaded" once any other test has imported it, so the assertion would pass for the wrong
  reason exactly when it matters.
- **A deferred import is still a dependency, and an import-time sweep cannot see it.**
  With the sweep green, `run_pipeline.sh` on a PyQt6-less machine still died in stage 2:
  `mesh_config_io.config_to_text` did `from app.utils import repo_root` *inside a function
  body*, loading no Qt at import time and needing the toolkit the moment a mesh config was
  written. Three such sites existed (`models/mesh_config_io.py` ×2,
  `models/solver_config.py`, `workers/solver_run.py`). The gate therefore reads the AST for
  a moved name imported from `app.utils` at **any** nesting depth, and separately refuses
  PyQt6 outright in a subprocess and drives the writers that failed.
The `services/` sweep is a **deny**-list (`QT_SERVICES`, each entry carrying its reason —
`i18n` wraps QTranslator, `ui_state` wraps QSettings): a new service is assumed Qt-free and
making one Qt-dependent costs an entry, since an allow-list would silently exempt whatever
nobody remembered to enrol. Stale entries fail too. One incidental correction: the moved
block held a **second, disagreeing depth count** — `find_binary_executable` walked five
levels from `gui/app` and so resolved to `<repo>/../build`, outside the repo, which is the
off-by-one `repo_root`'s own docstring warns about; it now goes through `repo_root()`, and
the gate pins the **resolved path** rather than the number of `..` segments. A separate
pre-existing defect the sweep surfaced and did *not* fix is recorded in the gate's
`CANNOT_IMPORT_STANDALONE`: `services/index_helpers.py` cannot be imported first
(`index_helpers` → `models/__init__` → `models.session` → `commands/__init__` →
`commands.segment_structure_cmds` → back), enabled by the eager re-exports in those two
`__init__.py` files.

Scroll-wheel on QSpinBox/QDoubleSpinBox is intentionally disabled (overridden in `main.py`).

**Numeric fields**: any field holding a *physical length* (BL initial thickness, mesh sizes, domain coordinates, resampling spacing, seed size/radius) must use `views/clean_double_spin_box.py::SciDoubleSpinBox`, not `CleanDoubleSpinBox`. It accepts/displays scientific notation, steps by decade, and has no hardcoded floor — a fixed-notation box silently clamps the 1e-7..1e-8 first-cell heights real CFD needs. Range lower bounds stay at 0 and invalid values are rejected by `MeshConfig.validate()` with a message, never by UI clamping.

**Length units** (`app/services/units.py`, Qt-free): the model declares ONE length unit
(Mesh panel, top row). It is **not cosmetic** — the solver is dimensional. Per the UNICONES
manual `fs_UnitRe` is *per metre* and `Linf` is *metres per grid unit* ("input 1 if
dimensional in meters"; its own sample uses `Linf 0.0254` for an inch grid), so
**Re = fs_UnitRe × Linf**. A mm mesh left at `Linf = 1` runs at 1000× the intended Reynolds
number with a mesh that looks perfect.

Rules:
- **`Linf` is derived from the declared unit**, not typed. `SolverConfig.linf_from_unit`
  is True for anything new; `load_from_dict` turns it **off** for a config that has a
  hand-set `linf` and no `length_unit`, so a pre-units case keeps its Reynolds number.
  `unit_check()` then reports the discrepancy naming the unit that `linf` implies.
- **Changing the unit relabels; it never rescales.** Only two things convert numbers:
  `Linf`, and coordinates at *import* (`views/import_unit_dialog.py`, asked once per
  import action, defaulting to no conversion, silent + no-op when headless).
- **Units are shown as the spin box's own `setSuffix`**, never baked into label text —
  the suffix rides on the widget owning the number and cannot be forgotten. Only
  physical lengths get one; growth rates, angles and counts must not.
  `views/panels/mesh_units_mixin.py::LENGTH_FIELDS` must equal the panel's
  `SciDoubleSpinBox` set — `tests/test_units.py` fails the build otherwise, which is how
  a field added later cannot silently lose its unit.
- The visible defence against a *plausible* wrong unit is the **reference Reynolds
  number** read-out on the Solver panel (`views/panels/solver_units_mixin.py`) and the
  `[INFO] reference Reynolds number` line in `run_pipeline.py`. The size-plausibility
  check only catches gross errors and says so.
- The mesher **records but never converts** `LENGTH_UNIT` (it only compares lengths with
  each other); it prints it in the banner, so it also lands in the provenance sidecar.

**The user-facing log is a service, not a widget**: say things with `AppController.log()` (controllers) or `app/services/user_log.py` (views) — never `main_window.log_panel.log(...)`, which is how 255 reach-throughs accumulated. `LogPanel` is a registered sink; sinks get the RAW message and classify for themselves, and the durable file mirror happens in the service ONLY (a second one in the panel writes every line twice). `user_log.log()` attaches the file handler itself, so a process that never ran the GUI's `main()` still leaves its log on disk. Gated by `tests/test_user_log_seam.py`, which fails the build on a new reach-through. This is a different log from `get_logger(__name__)`, which is developer diagnostics.

**The solver BC table is DERIVED by a service, not by the panel that shows it** (`services/solver_bc_table.py`, Qt-free, #90). The chain from a meshed patch to the solver's `.bc.def` was Qt-free at every step but one, which is what made this a prefactor rather than a feature: `bnd_io.read_bnd_segments` reads the `(segment id, patch name)` pairs out of the generated `.bnd`, `bnd_io.default_bc_flag_for_name` mirrors getPGrid's `getBCType` name→flag mapping, `SolverConfig.bc_definitions` is a plain model field, and `services/solver_case.py` — whose own docstring says it is shared by the GUI solver worker and the headless pipeline runner — writes it out. But the only thing that POPULATED `bc_definitions` read the Qt table (`solver_config_sync_mixin.get_config`), and the only caller of `default_bc_flag_for_name` was a panel VIEW (`solver_config_bc_mixin.populate_bc_from_segments`). So the mapping was a service while the derivation that uses it was a widget — the same shape as the pipeline stage set and the IB hand-off before those moved.

The ticket's whole claim is **no behaviour change**, so the gate holds it against something other than the new code. `tests/test_solver_bc_table.py` carries the pre-#90 inline rule verbatim as an ORACLE (quoted from `fca0997`) and agrees with it over 96 name/assignment/solution-type combinations, and it drives the REAL `SolverConfigPanel` on the offscreen platform, reading the rows back through `get_config()` — the rows the model actually ends up with, not the widgets. A test that re-derived the expectation from the service would agree with itself. Five injections were run and all five bit with a non-zero exit: dropping the precedence (7 FAILs), inventing an extra `values` (4), offering an override to unassigned rows (1), looking up a row that has no name cell (1), and — the one behaviour cannot see — leaving a second copy of the rule in the panel, caught only by the static check 12.

Three decisions inside it:
- **The precedence rule is stated once.** `bc_flag_for_patch` resolves an explicit assignment OR the patch name through `default_bc_flag_for_name`. The old inline code called that function twice on two branches, and the branch structure is what a second copy drifts on: an assignment naming a token getPGrid does not know must take the same wall fallback (2 viscous / 0 euler) as an unknown patch name, not fall back to the patch's own name.
- **`bc_flag_overrides` is a different question, not the same one twice.** `populate` builds a table; the resync (#7) patches one that already exists, and must leave a row nobody assigned alone so a manual solver-table tweak survives. Returning `{row index: flag}` keeps the widget-poking — `findData`, `setCurrentIndex`, the changed count — in the panel where it belongs, and lets the service be tested on lists. Its `None` name means "this row has no name CELL", which the old code skipped before it ever looked anything up; `""` means the patch really is unnamed. Collapsing the two would make `group_bc[""]` reachable.
- **`default_bc_flag_for_name` having ONE caller is checked STATICALLY**, by reading every GUI source file. A duplicated precedence rule is not wrong on the day it is written, so no runtime check can see it; injection E is exactly that case — behaviour identical, both behavioural checks green, check 12 red.

**#92 made the fallback AUDIBLE, and changed nothing else.** `default_bc_flag_for_name` documented its own fallback honestly — an unknown name is a slip wall for inviscid Euler and a no-slip wall for viscous NS, "matching getPGrid's tolerant fallback" — and the fallback is right: refusing to mesh, or refusing to solve, because a patch is named something unexpected would be worse than a wall. What was wrong is that it was SILENT. A user who typed `far-feild`, or who used a name this repo has not enumerated, got a solid wall where they meant an outflow, and the only symptom was a solution that was quietly wrong. getPGrid does warn on its own stdout when it does not know a name — that is how #57 and #85 measured this at all, **288 warnings on one C-grid run** — but that warning is about getPGrid's table, and after #91 getPGrid's table is no longer what decides. The place that knows both the token and the flag the run will really use is this service, so that is where it speaks from.

Five decisions in it:
- **A separate question, not a sentinel.** `bnd_io.is_known_bc_name` answers "was this looked up?"; `default_bc_flag_for_name` keeps answering "what flag?" with exactly the value it always returned. Folding the two into one return would have made every caller handle a shape it does not need, and would have put the fallback's own behaviour at risk in a ticket whose whole claim is that it does not move. Check 5 pins the flags against the pre-#92 `bc_flag_for_patch` over the same 96 combinations #90's oracle uses.
- **The token choice moved into `bc_token_for_patch`.** Asking "was it resolved?" and "what flag?" must be about the SAME token, and `assigned if assigned else name` written twice is how that stops being true. This is the precedence rule above, unchanged, given a name so it can be reused instead of retyped — which is also what lets the warning distinguish an unrecognised ASSIGNMENT (`inlet` assigned `far-feild`) from an unrecognised patch NAME.
- **The message is built ONCE, in the service, and logged by each host.** The GUI's `detect_bc_from_mesh` and `resync_solver_bc_from_group` log it through `AppController.log()`; `pipeline_bc_derive` logs it through its `log=` callback. Check 7 asserts the two hosts' lines are byte-identical, which a message built at each call site could not survive. The wording avoids the words "error" and "failed" on purpose, and the reason is a regex worth knowing before writing any new log line: `user_log._LEVEL_PREFIX` is anchored `^\s*`, so a `[Component] [LEVEL]` line — this repo's dominant shape, ~20 of them, `[IB] [WARNING]` in `pipeline_runner` among them — never matches it and falls through to the KEYWORD heuristic. The `[WARNING]` tag is therefore for the READER; the word "warning" is what grades the line, and "error"/"failed" anywhere in it would grade it ERROR. A first draft of this note and of the rule file both said the tag was what graded it — an unchecked tree fact, caught in review and re-measured through the real classifier, which is now what check 2 asserts.
- **Silence is load-bearing.** A mesh whose names all resolve says nothing, so the warning means something when it appears. That is the half an implementation gets wrong by warning per lookup rather than per unresolved patch, and it is the injection that produced 9 FAILs.
- **GROUPED BY NAME, not one line per segment.** The first draft warned once per patch and the acceptance run below caught it: the shipped C-grid names four segments `farfield`, so a typo there produced FOUR identical lines. That is the burial this ticket exists to undo — getPGrid already prints 288 of them on that same run, which is precisely why nobody reads them. One line per distinct NAME, carrying the segment ids (`(segments 5, 6, 7, 8)`), says strictly more in a quarter of the space. Found by looking at real output, not by a check; check 1 and check 2 hold it now.

**Two findings from the review, both real, both about the resync route.** Widening it past its `if n:` gate was right — a patch that resolves to nothing is just as wrong on the second entry into Solver mode, and that method also runs BEFORE A RUN, the last moment the warning can reach anyone. But the widened version then named a flag the table did not carry: `resync_bc_types_from_group` deliberately preserves a hand-picked flag on an unassigned row, while `unresolved_patches` re-derived its answer from name + `group_bc` and never read the table. So the message said "falls back to flag 2" while the run used the 1 the user had set, and doing the fix the message recommends did not stop it repeating — worse than noise. `in_force` (`{segment id: the flag really in force}`) closes it: an answered segment is dropped, and a patch all of whose segments were answered is not reported. The GUI passes it; the headless route has none to pass, because nothing there can override the derivation. Check 8 now drives exactly the reviewer's probe — set the combo by hand, resync, assert silence.

**And a check that could not bite, kept rather than strengthened.** Check 5's oracle calls the LIVE `default_bc_flag_for_name`, so both sides move together: mutating the fallback's own return leaves it PASS (checks 1, 2, 4, 6 and 8 catch that instead). It pins what #92 touched — the token choice moving into `bc_token_for_patch` — and nothing more. A hand-copied `_NAME_TO_FLAG` oracle here would rot into a second source of truth; the mapping is pinned where it should be, by `test_pipeline_bc_from_mesh.py` check 10 against getPGrid's own C++. #90's check 11 has the identical shape and the identical limit, and neither said so until now.

**Named blind spot.** A headless run with no `.bnd`, or one with no patches, derives nothing and therefore warns nothing, while `stage_bc_def_companion` copies getPGrid's own table — carrying the same silent unknown-name fallback #92 exists to end. There are no patch names to inspect on that path, so there is nothing to name; recorded rather than fixed.

Eleven injections, every one with a non-zero exit: dropping the headless emission (2 FAILs, one of them the cross-host equality), dropping the GUI's (2), dropping the RESYNC path's (1), reporting nothing unresolved (6), reporting everything as unresolved (9), dropping the fix sentence (1), dropping the flag number (1), dropping the segment list (3), un-grouping back to one entry per segment (4), breaking the precedence so the token and the flag disagree (4, one of them the pre-#92 oracle), and making `is_known_bc_name` say yes to everything (6). Five more after the review, all biting: gating the resync warning back behind `if n:` (3), putting the word "failed" into the wording so `classify` grades it ERROR (1), ignoring `in_force` (1), not passing it from the controller (1), and dropping a patch as soon as ANY of its segments was answered rather than all (5).

Two harness lessons, both already in this repo's memory and both re-earned here. The RESYNC injection bit only after check 8 was added for it: the first draft gated `detect_bc_from_mesh` and left its sibling — the path the GUI takes on entering Solver mode, where an assignment changed after the table was seeded lands its flag without anyone clicking Detect — unguarded, which is "injections cannot reach an untouched path" again. And when the grouping rewrite changed three of the injected source lines, those three injections silently became NO-OPS and reported green, indistinguishable from an inert probe; the harness now asserts the file actually changed before scoring.

Known blind spot, PRESERVED rather than fixed: the lookup is `group_bc[patch_name]`, but a `group_bc` key is the per-segment grouping LABEL while a `.bnd` patch name is the physical BC TYPE the mesher resolved that label to (`src/Mesh.cpp`, `Config::resolveGroupBc` — the same two namespaces the mesh-BC audit confused once, and had to stop comparing directly). The precedence rule therefore only fires where a label happens to be named after its own type, which is the common case and not the general one. #90 is a prefactor and changes no behaviour; the asymmetry is recorded here and in the service's own docstring so that whoever picks up #91/#92 meets it before rediscovering it. Both have since landed and neither touched it.

**User messages**: use `app/utils.py`'s graded helpers, never a raw `QMessageBox` call — with **two recorded exemptions, and no third without a helper**: `views/case_dir_dialog.py` (the case-dir question, now **four** mutually exclusive dispositions — #33 restored `CASE_ARCHIVE`, see below) and `controllers/curve_join_ctrl.py` (keep / merge). The graded set is `report_*`, a two-way `confirm`, and `confirm_destructive`; none of the two exempted prompts is a yes/no, and both still make the headless early-return themselves, which is the part the helpers exist to centralise. A third multi-way prompt is the point at which `app/utils.py` grows a `choose()` rather than the list growing again — `report_error` (failed write, data at risk → Critical), `report_warning` (failed read → Warning), `report_info` (a precondition, nothing broke → Information), `confirm(..., headless_default=)` (Yes/No), `confirm_destructive(..., action_label=, option_label=)` (an irreversible action: a **named** button, Cancel as the default, an optional extra tick, and **no `headless_default` at all** — a destructive prompt has no safe default to proceed with, and making it an argument would let a caller opt an unattended path into deleting files; it returns `None` when declined and the tick's state otherwise). **`confirm_destructive` is the rule working rather than an exception to it**: #33's clean confirmation IS a yes/no, so the file exemption above did not cover it — what it needed beyond `confirm` was a details pane and one checkbox, i.e. a helper, and it was caught in review arguing from the wrong half of this paragraph. All of them no-op or return the default on a headless platform, which is what keeps tests, CI and the headless pipeline from hanging on a modal. Any new dock widget needs `setObjectName()`, or `QMainWindow.restoreState()` silently skips it.

**Pop-up stacking** (`app/popup_stack.py`, re-exported from `app/utils.py`): every
modeless pop-up goes through `keep_on_top(w)` **before** `show()`, which re-parents it to
the **top-level** window, leaves it an ordinary normal-level `Qt.Dialog`, and installs the
three filters that put it back on top — `_PopupRaiser` (on the main window, for every
activation), `_ClickRaiser` (on the **QApplication**, for every mouse RELEASE) and
`_ShowRaiser` (on the pop-up, so a call site that only `show()`s is covered).
Activation alone is not enough and that is not a detail: it fires on the FIRST click of
the main window only, so every click after it reorders the window in front of the pop-up
with no Qt event to hear, and a raise deferred into the middle of a canvas *drag* is
undone when the drag ends. Releasing is the moment the platform has finished reordering.
The app-wide filter returns on its first line for anything that is not a release, and
`raise_later` keeps at most one raise in flight per widget. Both shortcuts on the window LEVEL are wrong and were each shipped once:
`WindowStaysOnTopHint` floats the pop-up above **every** application (intrusive), and
`Qt.Tool` — an NSPanel with `hidesOnDeactivate` — makes the pop-up **disappear** the
moment the user clicks another app while the main window stays visible (measured on
Qt 6.10: `isExposed()` → False). Disabling the auto-hide is not an escape: Qt6 ignores
`WA_MacAlwaysShowToolWindow` (the cocoa plugin reads the `_q_macAlwaysShowToolWindow`
*window property*) and a Tool window sits at NSFloatingWindowLevel, i.e. back to floating
over the other app. **Every raise goes through `raise_later()`** — a raise issued from
inside the event that reorders the windows is undone when the platform finishes that
event, which is why the arc/line editor (shown from the canvas press that completes the
shape) opened *underneath* the main window once the Tool level was gone. Re-parenting is
load bearing twice over — the raiser finds pop-ups in the top-level's direct child list,
and a pop-up parented to a panel is hidden with that panel. Gated by
`tests/test_popup_stacking.py`. `BatchDialog` opts out on purpose (it runs for minutes and
must be free to sit behind the main window).

**Duplicate/transform closure**: `transform_apply_ctrl` is type-preserving (a line stays a
line, an **arc stays an arc**…), and the copy inherits the source's `closed` flag — except
in the polygon-bake fallback (formula curves, discrete file edges, and a circle/arc under
a NON-uniform scale, which is an ellipse the model cannot hold), where the flag is
*re-derived from the points* by `_baked_edge_is_closed`. The arc's image is read off three
TRANSFORMED POINTS — centre, arc start, quarter-sweep point — so one code path serves
every similarity transform and a mirror's reversed sweep (`theta1 < theta0`, which both
samplers walk) comes out of the geometry rather than a per-transform sign rule; the
quarter point rather than the midpoint, because `sin(sweep/2)` vanishes at exactly
|sweep| = 2π. Whatever still bakes is NAMED in the log with the reason. `SegmentModel.closed` defaults True and is only
ever read for `curve_type == "polygon"`, so every other kind of edge carries True while
drawing open; copying that flag onto a baked polygon is what silently closed a duplicated
arc. Discrete edges must not take the PROJECT's closure either — one segment of a closed
imported outline is itself an open polyline. Gated by `tests/test_transform_closure.py`.

**The discrete geometry is ONE polyline, and both ends of that have to be handled.**
A session stores every discrete point in `original_points`, indexed by `split_indices`
into file segments, and the canvas draws it as a single pyqtgraph item.
- **Baking order matters.** `BakeCurveToGeometryCmd` welds a converted edge onto
  whichever END of the polyline it touches, so an edge touching neither lands as a
  separate piece. `bake_selected_curve` therefore chains a multi-edge selection with
  `_chain_edges` (the same one Join uses) and bakes head-to-tail as ONE undo step
  (`BakeCurvesToGeometryCmd`) — the selection is index-sorted, so the DRAWING order,
  which the user cannot fix by clicking differently, was deciding the result.
- **Where the polyline must NOT join comes from the model.** `_geometry_connect`
  (in `segment_canvas_ctrl`) breaks it at any index interval covered by no file
  segment — `update_file_segments_from_indices` already drops the bridging pair —
  and passes that as pyqtgraph's `connect` array. Without it two disjoint pieces are
  drawn joined: a "diagonal" that belongs to no edge and cannot be selected away.
  Deliberately not a spacing heuristic, which would also break a long straight edge
  beside a finely sampled arc.
- **An empty model still has to be drawn.** `_apply_geometry_update` returns early
  when `original_points is None`, so `_clear_geometry_canvas` does the wiping —
  layer, hit-test points, split markers, closing edge, stats — but never the
  analytic (curve) items, which a session can legitimately have on their own.

**A PARAMETRIC AEROFOIL, AND A LAW WRITTEN TWICE ON PURPOSE** (#147, parent #146;
`app/services/naca_airfoil.py` + `tools/PreProcessor/include/NacaAirfoil.hpp`,
`app/models/shape_spec.py`'s `naca4` rows, `app/models/project.py::add_airfoil_parts`).
#133 deferred this in as many words — *"an airfoil shape arrives with the C-grid
template that actually needs it"* — and the gap it left is upstream of the whole
template library: the CAD stage offered `line`, `circle`, `arc`, `triangle`,
`quadrilateral`, `polygon` and `custom`, so the only way to get an aerofoil into a case
was to bring a `.dat` from outside and bind a template to whatever segmentation that
file happened to carry.

**Why it is a `curve_type` and not a new kind of object.** It joins `circle` and
`polygon` in the machinery that already exists: declared in `shape_spec` (defaults,
dialog fields, sidebar widget names, control points, drag, the drawing tool), generated
in `GeometryService.compute_curve_preview_pts`, handled in the resampler's `curve_type`
dispatch, serialised by the one `SegmentModel.to_dict()` that the project file, the
workspace and the pipeline script all go through. The round trip therefore needed no
code at all, which is asserted by driving it rather than by saying so
(`test_naca_airfoil_parity.py` check 5).

**THE LAW HAS ONE OWNER PER HOST, AND THAT IS NOT A PREFERENCE.** #146 asked for ONE
Qt-free owner both the GUI preview and the resampler read. A Python module cannot be
read by a C++ binary; the converse is worse, because the canvas preview runs on every
drag of a control point and must work in a checkout with no build tree — every
mesher gate in this repo self-skips when `build/` is empty, and a preview that needed
`surface_resampler` would make drawing a shape depend on having compiled one. So the
camber/thickness law is written twice, each host having exactly one copy, and
**`tests/test_naca_airfoil_parity.py` is what makes the pair behave as one**: it drives
the preview through the real `GeometryService` and the law through the real
`surface_resampler`, on a config built from a real `SegmentModel.to_dict()`, and
compares coordinates. Measured 2026-09-24 over seven parameter sets: **worst deviation
6.9e-11**, which is the `.dat`'s own `setprecision(10)` quantum and not a property of
the law — so the tolerance is 1e-9 and deliberately not tighter, a tolerance below the
file's resolution being a measurement of the writer. A source scan was refused for
#135's reason: a claim about a shared funnel was true in the source while the edit
never reached it.

Both files are written to be mirrored literally — powers as repeated multiplication
rather than `**`, the same evaluation order, the two exact endpoints ASSIGNED rather
than computed — because the thing being protected is a numerical agreement and every
avoidable difference in spelling is a place for one to appear.

**THE PREVIEW APPLIES THE UNIFORM RE-FIT BECAUSE THE RESAMPLER DOES.** The generator
samples cosine in x, crowding the points where the surface turns; the resampler then
hands that polyline to the segment's `uniform` strategy, which redistributes it by arc
length. The preview therefore ends with `_resample_polyline_uniform` — not decoration,
and not a choice: `circle` and `line` already do exactly this, for exactly this reason,
and removing it is one of the injections that bites (M, 1.2e-01 apart). What the cosine
spacing buys is the FACETING the redistribution interpolates on, which is what keeps
the nodes near the leading edge on the real surface.

**THE SHAPE ARRIVES SEGMENTED, AND THE SPLIT IS DECIDED IN ONE PLACE.**
`naca_airfoil.segment_parts` returns `("upper", "lower")` for a sharp section and
`("upper", "lower", "te")` for a blunt one; `ProjectModel.add_airfoil_parts` turns a
drawn aerofoil into exactly those `SegmentModel`s, each carrying the same parameters
and its own `part`, and `AddAirfoilSegmentsCmd` adds them as ONE undo step — three
presses leaving a lower surface and a trailing edge behind is a geometry nobody
authored. The ids are the ordinary CAD segment ids, so the C-grid's bindings are the
stable-id lookups #137 already built and there is no new resolution rule. The node
budget splits between the two surfaces; the trailing-edge base takes `TE_PART_POINTS`
of its own rather than a proportional share, which on a base a few thousandths of a
chord long would be one point.

**A BLUNT TRAILING EDGE IS PRODUCED HERE, AND REFUSED BY THE TEMPLATE.** #147 asked for
this to be decided and stated rather than left to chance, and the two halves land in
different tickets. The classic 4-digit thickness law (`-0.1015`) leaves the section OPEN
at x = 1 by `0.0021*t` of chord; that is a real aerofoil, so it is produced, and its
base is a real third segment whose span is the law's own `y(1)` doubled (measured
0.00252 at 12% thickness, gated). The closed variant (`-0.1036`) makes the five
coefficients sum to zero and is the DEFAULT, because a sharp trailing edge is the one a
C-grid's four blocks can meet at. What is REFUSED is the shape that does not exist: a
`te` part on a SHARP section, which would be a zero-length segment, comes back as a
`NacaError` in Python and an empty point list with a named reason in C++. The C-grid
family's own refusal of a blunt section belongs to #148 and is a different refusal, for
a different reason — its four blocks sit on one declared corner a blunt edge has not
got.

**AN ELEMENT THAT PRODUCED NOTHING NOW SAYS SO.** The resampler used to print
`Successfully processed element to ... (0 points)` and write an empty `.dat`, which on a
refused aerofoil appeared one line under the refusal's own reason. A named refusal
contradicted by the next line reads as noise, so the empty case is reported as the
failure it is and nothing is written. Reported by the ONE writer, so it cannot be true
of one shape and not another.

**What the injections found, and one that cannot be fixed by writing a check.** 17
mutations, 16 bite, recorded in the gate's own docstring. Two lessons are worth more
than the list. **A parameter the gate does not MOVE is a parameter the gate does not
check**: every `full` case originally asked for an EVEN node count, and under an even
count the two ways of rounding the per-side split agree exactly — so a host rounding
the other way was invisible until an odd-count case existed, and the same injection
then bit in both hosts. **And six C++ injections came back INERT on the first run for a
reason that was not the gate's**: make compares timestamps at one-second granularity,
and an inject-build-restore-build cycle finishes inside one second, so the mutated
header was never compiled and a real bite looked exactly like a check that does not
bite. The same shape as this repo's `__pycache__` restore trap, in another language.

**And the per-tool drawing tables left the canvas for `services/canvas_tools.py`.** How
many points a tool collects (`DRAW_NPTS`) and what it asks for next (`DRAW_HINTS` /
`draw_hint`) were a class constant and a nine-branch if-chain inside
`views/canvas_draw_mixin.py`. They are one tool's two facts, and a tool that gains one
without the other is a tool that never completes or never prompts — so they are now
declared side by side, in the Qt-free module that already exists for canvas logic
"away from Qt, so it is testable without a display". What forced the move rather than
merely justifying it was the 500-line standard: adding the aerofoil tool took that mixin
to 502, and the table version — being better prose — took it to 507. Moving both tables
out left it at 472 and `canvas_tools.py` at 244, which is the shape the standard exists
to produce: a file gets smaller because something belonged elsewhere, not because
comments were cut to fit a number.

**Named blind spots.**
- **Nothing joins the parts after they are created.** Changing the chord on the upper
  surface alone leaves a geometry whose two halves disagree. The preview shows it
  immediately and no export is silently wrong, but there is no model-level link that
  would prevent it — the parts are ordinary segments, which is exactly what makes the
  binding mechanism free. A linked edit is a feature, not a fix, and is not in #147.
- **The parity gate proves the two hosts AGREE, never that either is RIGHT.** Both
  could carry the same wrong coefficient. Standing between that and a shipped aerofoil
  is check 1 alone — a handful of published figures (6% half-thickness at 12%, maximum
  thickness at x = 0.3, the closed-TE coefficients summing to zero) — not an
  independent implementation.
- **One injection stays INERT, measured**: dropping the C++ end-snap leaves the
  computed value in place, ~1.7e-17 from the assigned one, three orders BELOW the
  `.dat`'s own quantum, so no comparison against that file can see it. Exactness at the
  two points where the surfaces meet is checked on the Python owner, where it can be
  compared with 0.0 itself; the C++ half of it is unguarded and the gate says so.
- **The single-edge `full` form under-resolves a BLUNT base**, measured rather than
  fixed: uniform arc-length distribution gives a base 0.25% of chord long no interior
  node of its own, so the loop cuts that corner. The SEGMENTED form is what a template
  binds to; `full` is a convenience, and check 4d states the number.
- **A transform of an aerofoil BAKES it to a polygon**, through
  `transform_apply_ctrl`'s documented fallback, and the log names it. A similarity
  transform could stay analytic; a mirror could not (it is a different camber sign),
  and half a rule is worse than the fallback that already tells the truth.


**Window layout** is persisted by `app/services/ui_state.py` — **window geometry and
dock state, and nothing else** — namespaced by `LAYOUT_VERSION` (now 2; bump it when
the layout changes so stale state is ignored rather than restored). It never touches
`QSettings` when headless. **The active stage and the sidebar sections are
deliberately NOT persisted, and that is a reversal, not an omission** (issue #27,
USER-REQUESTED): both used to be saved and restored here on the same
resume-where-you-stopped argument, and the user weighed that against landing
somewhere unpredictable — with no way to reset it — and chose predictability. Every
launch therefore starts on **CAD** with **every** sidebar section collapsed, and both
defaults come from code that was already there rather than from a new constant:
`mode_combo`'s own index 0 (`main_window.py`) and
`CollapsibleSection`'s own `start_collapsed=True` default — measured: of the 39
`start_collapsed` mentions under `app/`, **zero** pass `False`, so the default is the
guarantee and no call site overrides it. **The `LAYOUT_VERSION` bump orphans more than the keys this removed**, and
that is worth stating rather than discovering: `_section_key` is built from `_PREFIX`,
so moving to `ui/v2` drops every existing user's saved geometry, dock state and
*dialog*-accordion flags along with the stage and section keys. The bump was requested
in the issue and the one-time loss accepted there; what it buys is that no v1 key can
ever come back as a live value. `restore_active_stage` and the private `_sections` walker are **gone** —
the save half went with the restore half, because a value written and never read
reads as a working feature. The convenience removed was real; do not reinstate it as
a bug fix. `tests/test_ui_state_and_dialogs.py` checks 1/2/4 are the **inverted**
versions of the checks that used to pin the old behaviour (seeded with a previous
version's `ui/v1` stage + section keys, rebuilt in the old key format from the live
sidebar so the stale state is really the kind the deleted restore consumed), so
bringing either restore back fails the gate. A **dialog's** accordion is a separate,
still-wanted feature and its *code path* is untouched: it persists itself through
`save_section_states(scope, sections)` / `restore_section_states(...)` with an
explicit scope string, which never walked `sidebar_stack` — the Edit-BL dialog still
opens all-closed and reopens the groups the user left open. Its *stored* flags are
not exempt from the version bump, per the paragraph above.

**"⟳ Restart" closes THIS window first and spawns only if the close happened**
(`services/gui_restart.py`, Qt-free — `restart_command` / `preflight` / `launch`;
`lifecycle_ctrl.restart_gui`; the button sits beside `Run All` in the persistent tab
row, so it is present in every stage). USER-REQUESTED (2026-08-20, issue #28):
`Clear All` resets the model but leaves the process — its view state, temp dir, log
and worker threads — in place, so a truly fresh instance meant quitting and
relaunching by hand. Four rules:
- **The order IS the feature.** Spawning first and *then* asking "discard unsaved
  changes?" leaves **two** GUIs running when the answer is No, which is the opposite
  of the request. So `main_window.close()` goes first and the child is launched only
  if it returned True.
- **The outcome comes from `close()`'s return value, not from `isVisible()`.**
  Measured under the offscreen platform: a *cancelled* close on a window that was
  never shown reports `isVisible() == False` and `isHidden() == True` — identical to
  a successful one — while `close()` returns False exactly when the close event was
  ignored, shown or not. The issue's own text suggests `isVisible()`; it would have
  made the gate pass for the wrong reason.
- **There is no second copy of the unsaved-work prompt.** The close routes through
  `MainWindow.closeEvent` → `handle_close_event`, which already covers modified
  geometry sessions *and* a dirty Mesh/Solver/IB configuration, saves the layout
  before teardown, joins every worker within its bounded budget, and removes the
  autosave file — so the new instance does not offer to recover the session the user
  just chose to leave. A second prompt would be a second place to forget a
  dirty-state source.
- **`proc_util.popen_kwargs()` must NOT be reused here.** It sets `stdout=PIPE`
  (with `stderr` folded in) for the streaming workers; with the parent gone nobody
  drains that pipe and the child stalls once the buffer fills. The restart builds its
  own kwargs — `start_new_session=True` repeated deliberately rather than inherited,
  `stdin`/`stdout`/`stderr` all `DEVNULL` — and passes **no arguments**, because the
  request is a brand-new session and carrying the case over would be a different
  feature. The entry point resolves through `paths.repo_root()`, never by counting
  `..` segments.
`preflight()` exists because of that ordering: a bad interpreter or a missing
`main.py` has to be caught while there is still a window to report it in. The
residue is named rather than hidden — a `Popen` that fails *after* the window is
gone can only reach `user_log`'s file mirror, since there is no parent window left
to put a modal on and the app is already quitting; the gate pins that it is at
least *said*. The button's **caption is a measurement, and the measurement lives in
the gate rather than in a comment**: at the 900px minimum window the tab row is
540px, "⟳ Restart" (88px) leaves 31px of slack in the tightest stage and
"⟳ New Session" (119px) leaves 0 — but those numbers are re-derived per run by
`tests/test_gui_restart.py`, which sums what each visible widget asked for across
**every** stage, because a tab bar is visible in some stages and hidden in others
(measuring in the IB stage reports 171px of slack where CAD has 31). The two
tab-row buttons also share one QSS builder (`_tab_row_btn_qss`) for exactly that
reason: the fit is measured against padding and font size, so two copies of them
could drift apart. Gated by `tests/test_gui_restart.py` — 9 properties, the
source-reading ones AST-based and injection-verified, with a negative control on
`popen_kwargs` and its blind spots named in its own docstring — plus a one-off
acceptance run: the real spawn was reparented to init in its own session and
outlived the parent.

**Edit Boundary Layer dialog** (`views/panels/mesh_dialogs_bl.py`, tables in
`mesh_bl_field_specs.py`, accordion + window fitting in `mesh_bl_dialog_layout.py`):
the 21 BL parameters are collapsible groups (`_BL_FIELD_GROUPS`, mirroring the `.dat`
parameter groups), **all closed to start** (USER-REQUESTED — the dialog opens as a list
of headers and the window is only as tall as what was opened), plus Expand all /
Collapse all. Only two things open a group and neither is a default: the state the user
left it in (`ui_state.save/restore_section_states`), and an override (below).
**`_BL_FIELD_GROUPS` must partition
`_BL_FIELD_SPECS` exactly** — a key in no group is a parameter the user cannot reach
that is still written back on OK — gated by `tests/test_bl_dialog_sections.py`, with
stray keys falling into a trailing "Other" group as a backstop. A group holding a value
that differs from the global default expands itself, so a per-geometry override never
hides behind a collapsed header. The window follows the open groups
(`_relayout` → `_autofit_height`), bounded by the screen and never below a height the
user set by dragging. Two Qt facts that fit depends on, both learned the hard way:
`QScrollArea::sizeHint()` is **clamped to 24 font heights**, so the dialog's own
`sizeHint()` stops growing after a group or two (the fit measures the scroll's shortfall
against its cap and the leftover slack instead); and hiding a widget only *posts* the
layout request, so `CollapsibleSection._on_toggle` invalidates its own layout — without
that, every reader (including the sidebar) sizes itself from the state the section just
left. The leftover-space absorber (trailing spacer / per-segment list) is
**stretch 0 + Expanding**, never a stretched item, which would compete proportionally
with the capped scroll area and leave the groups short of their own cap.

**A greyed field says WHY, and where the reason RIDES was measured** (#23,
USER-REPORTED). `BL_JUNCTION_ANGLE_C1` is dead under the default junction method,
which bins its slide by a hard-coded 95 deg, so disabling it is correct — the SILENCE
was the defect: on screen a greyed box with no reason is indistinguishable from one
greyed for another reason, or from a bug, which is what it was reported as. Three
placement facts, none of them stylistic. A tooltip on the box is impossible: MEASURED
on this Qt, hovering an ENABLED spin box delivers `Enter` to it while hovering the
disabled one delivers nothing to it OR to its parent, because Qt picks the mouse
receiver by walking PAST disabled widgets. Suffixing the label was the first choice and
costs the whole form: the label column is one shared width measured from the labels
actually built, and the suffixed composite measures 240 against the plain 171 on the
metric these numbers were taken on, which shoves every label in the dialog 69 px right
and onto `LABEL_COL_MAX`, where the next parameter added clips instead. So the reason
rides in a composite FIELD cell — the one in the GUI — which feeds no measurement at
all: 171 + 86 (spin box) + 4 + 73 (note) = 334 px, inside the dialog's own 380 px
minimum.

**A pixel literal is a metric of one machine, and the gate had one** (#98).
`test_bl_dialog_sections.py` check 14 carried the argument in its own comment — "a
macOS font metric asserted on an Ubuntu CI runner — a gate that goes red for the
platform rather than for the code" — and then asserted `suffixed >= 240`, the ceiling
written out as a number, which measured EXACTLY 240 here. MEASURED: the same assertion
fails at 224 (`QT_FONT_DPI=84`) and 191 (72) with the code correct. The first fix was
also wrong and in the same class, mirrored: comparing two CLAMPED widths collapses past
a ~1.8x metric, where the plain labels alone reach the ceiling and "the column grows"
is false while the code is still right — found by BOTH review axes independently. What
survives a font change is not a width but the CONSEQUENCE, and there are exactly two:
the shared column grows, or it is already on `LABEL_COL_MAX` and the suffixed label
clips inside the cell it is right-aligned in. The gate asserts that cost
(`suffix_cost`), plus the growth as a RATIO for the magnitude the ceiling comparison
used to carry — 1.40 today, and inside 1.39..1.41 across a 0.7..2.0 sweep over which
the pixel itself moved 191..385. The band it clamps against is DECLARED as
`LABEL_COL_MIN`/`LABEL_COL_MAX` with `clamp_label_col` in `mesh_bl_dialog_layout.py`,
so the gate reads the bound instead of restating it. The TEETH are an injection, not a
comparison: `by_key` is patched to hand the build a C1 spec whose label already carries
the reason, and the column check must go red on the real dialog.

**An unreadable method value leaves the field LIVE** — `_sync`'s
`except (TypeError, ValueError)` sets `reads_c1 = True`, never stuck off, and shows no
marker, an editable field having nothing to explain. Both halves were intended rather
than verified for two tickets: check 14 toggles between the two shipped methods and
both parse fine, so nothing ever entered the branch. Check 15 raises from
`_widget_value` for the junction combo and asserts the state at all THREE arrivals —
the constructor's own `_sync` and a real `currentIndexChanged` in each direction. The
first version of it asserted off `_set_widget_value(..., 1)` alone, which is inert: the
seed is already method 1 (`include/BLParams.hpp`'s default), so no signal is emitted
and an unexercised signal path looks identical to an exercised one. The branch also
logs at `debug(..., exc_info=True)` now — permissive by decision, but not invisible,
since its only other trace would be a field that quietly stopped greying out.

**Transient results (Results tab playback)**: a transient run appends one Tecplot
zone per dumped step, so the Results view is a movie. `models/tecplot_index.py`
scans the file ONCE for the byte offset of every `zone` header and caches that
index by (path, mtime, size); `TecplotResult.from_file` then seeks to one zone's
byte range instead of `readlines()`-ing the whole file and rescanning it — 0.35 s
→ 0.07 s per frame on a 113 MB / 10-zone run, which is what makes playback
affordable at all. `models/result_series.py` adds the bounded (by BYTES, not
frame count) LRU frame cache and the per-variable global range.
`views/result_playback_mixin.py` owns the transport (First, Prev, Play/Pause,
Next, Last, speed, Loop, Lock scale). **Looping is opt-in**: by default a run plays
through once and stops on the last frame (the converged solution), and the same
checkbox governs the step buttons, which clamp at the ends — and grey themselves
out there — instead of wrapping to the far end of the run. Play at the end of a
finished non-looping run rewinds first. First/Last are jumps rather than steps, so
Loop does not apply to them; they grey out only on the frame they lead to. Two
further rules decide whether the animation is readable:
- **The colour scale can be pinned across the whole run** ("Lock scale", shown only
  for a multi-zone result), because auto-scaling each frame to its own min/max
  repaints the same colours onto a changing range — a vorticity field decaying
  0.089 → 0.019 looks *identical* frame to frame. Ticking it scans all frames for
  the current variable (cached, so it is paid once) and pins that range.
  **It is OFF by default (USER-REQUESTED)**: "Auto (fit to data)" has to mean the
  data on screen, i.e. the frame being shown. A **manual** clim always wins over
  both: the lock fixes auto-scaling, it does not overrule an explicit choice, and
  it is dropped when the displayed variable changes.
- **A colour range — pinned OR typed — belongs to ONE variable.** The lock always
  carried `_range_lock_var` beside `_range_lock`; the manual clim was one unkeyed
  tuple, so Auto off → Min/Max → Apply coloured *every* variable, and a pressure
  range rendered vorticity as one flat colour or one saturated blob with the
  Min/Max boxes still showing the old numbers as if they belonged to it —
  USER-REPORTED (2026-08-20, issue #24). It is now `_clim_by_var`
  (`dict[str, tuple]`), written by `set_clim` under the displayed variable and
  read by `render` for the variable it is about to draw; the same fact got the
  same shape rather than a second pattern. Four rules: **the MODE stays global**
  (one Auto/Custom checkbox with one meaning — making it per-variable would be a
  second hidden mode), so switching to Auto does not forget the numbers; **a
  variable with no remembered pair is SEEDED from its own data range on first
  render and remembered**, which is both what stops it inheriting another
  variable's numbers and what stops playback re-seeding (and so drifting) every
  frame; **precedence is untouched** — manual > lock > auto data range, enforced
  where it always was, in `playback_clim` returning None unless `_clim_auto`;
  and **the store is view state for the loaded result**, cleared by
  `load_result_path` / `clear` (a new run must not wear the old one's numbers)
  but deliberately kept across frames of one run. It is written ONLY through
  `remember_clim` / `set_clim` and read through `manual_clim`, `render`'s seed
  path included — the same reason `recordBoundaryEdge` is the only way to write
  a boundary edge's BC.
  The panel's Min/Max boxes follow the range in force through the existing
  `result_rendered` signal — never by reading canvas privates — and in Custom
  mode they are refreshed on exactly two events, because there they are an input
  the user may be halfway through typing: the variable MOVED, or the canvas
  reports `clim_seeded`, i.e. the range on screen is not one the user typed.
  **The seed flag is why the refresh is not keyed on the variable NAME**: a
  newly loaded run clears the store and re-seeds under the *same* variable name,
  so a name-keyed refresh left the boxes showing the previous run's numbers —
  verbatim the reported symptom, found in review of the first version of this
  fix and now its own check.
  And **the Auto checkbox IS the mode, in both directions**: unticking it used to
  tell the canvas nothing until Apply, so the panel showed the Custom box while
  the canvas kept auto-scaling every frame to its own min/max and the Min/Max
  boxes — no longer refreshed by the Auto branch — froze on the frame the untick
  happened on. That is the same "the boxes describe a range that is not on
  screen" symptom reached by the other route, and it needs a multi-frame run to
  see, which is why it is its own section in the gate. Unticking now seeds from
  the frame on screen, so nothing jumps at that moment.
  Gated by `tests/test_result_clim_per_variable.py` (8 properties, every one
  verified by injection — including both wrong versions found in review — with
  the one blind spot named in its docstring).
- **`set_result` reuses the triangulation when the incoming frame has the same
  nodes**, which also keeps probes/line/extrema alive across a step (they mark
  geometry, and the geometry did not move). Field caches are always dropped.
Frames are labelled by POSITION (`Frame 4 / 10`): the solver writes `t = "time 0"`
for *every* zone, so the file carries no real timestamp to show. Gated by
`tests/test_result_playback.py`, which pins the byte-range parse to be identical
to a whole-file scan, and `tests/test_result_clim_per_variable.py` for the
per-variable colour range.

**A restarted solve is ONE run split across several files, and it plays as one
animation** (`services/result_legs.py`, Qt-free — `list_result_legs` → a
`LegSeries` of `ResultLeg`s in playback order plus its warnings as data;
`ResultSeries` takes a LIST of paths). #32, USER-REQUESTED (2026-08-21), blocked
by #30 because it reads the `RUN.txt` #30 writes. #26 moves a finished run's
outputs into `work/prev_<NNN>/`, so the field output of a twice-restarted solve
is three files and the transport could only ever animate one of them — watching
the solve evolve meant opening each leg by hand and losing the animation at every
boundary. Rules that are load bearing:
- **A list, never a concatenated temp file.** The byte-offset index exists so a
  frame costs 0.07 s instead of 0.35 s; merging hundreds of MB would throw that
  away. So the per-file `tecplot_index` is untouched and a FLAT frame index sits
  above it — global frame *k* → `(file, zone)`. Three things become global with
  it: the numbering, the LRU **byte** budget (a solve restarted ten times must
  not hold ten caches) and every range `global_range` reports. A change in ANY
  file therefore drops EVERY cached frame and range, because the numbering shifts
  and a frame kept under its old global number would serve another leg's zone.
- **A leg is found by its STEM.** #30 renames an archived file's run tag to
  `.prev_<NNN>`, so one solver output is `xtecp_sol_allz.dat.gui` live and
  `xtecp_sol_allz.dat.prev_001` archived; `strip_archive_suffix` +
  `strip_run_tag` (the inverse of `archive_name`, and the reason `strip_run_tag`
  now exists in `case_files`) recovers the one name both carry. That also makes
  it work on **pre-#30 archives**, which kept `.gui` — measured on this repo's
  own `results/solver/case`.
- **Order by ITERATION COUNT; lineage answers a different question.** The first
  version of this said lineage was NOT recoverable and that was simply FALSE —
  found by the Spec axis. `case_archive.bare_link_for_archived_dump` links an
  archived dump into `work/` under its ARCHIVED name, so a `resumed_from` reading
  `binDumpZ.dat.prev_001` names that leg exactly, and #31's own
  `_last_resumed_basename` already relies on it. What lineage really gives is a
  PREDECESSOR relation, never a position: it says where a leg started, not how
  far it went, and two legs resumed from the same point are indistinguishable by
  it — which is exactly the re-run case. So the corrected `end` orders (creation
  order breaking ties) and lineage DETECTS the overlap where a span cannot.
- **How far a leg got is NOT computed here** (#43): every leg's span comes from
  `case_run_note.iteration_span`, which the restart chooser reads too, so the two
  windows cannot describe one archive differently. #32 shipped the note as the
  only source, so an archive predating #30 played with no count while `_live_leg`
  eight lines below computed its own from a convergence history with that same
  reader — on `results/solver/case` that was every archive it has. Ordering is by
  the CORRECTED `end`, not the raw last row: two legs printing at different
  intervals sort correctly only after the correction.
- **A leg that can be measured NEITHER way is played WHERE IT RAN, not last** — a
  deliberate departure from the issue's "offered last", because that phrasing is
  right for a chooser LIST and wrong for a playback ORDER. Not academic: the
  FIRST version shipped the literal rule and the acceptance run against
  `results/solver/case` played the solve **backwards** — newest leg first, the
  two oldest after it. Such a leg inherits the last count recorded before it,
  which is creation order except where a measured count says otherwise. #43
  demotes this from the first line of defence to the **third**: it was written
  when a `RUN.txt` was the only source, and it now only applies once both the
  record and the convergence history have failed.
- **An overlap is a MEASUREMENT** (#43), reported and never interleaved. A leg
  reports a half-open **span** `(start, end]`, so the test is interval
  intersection and the message names the iterations that repeat. Half-open is
  load bearing: consecutive legs of a restart chain MEET at a boundary iteration,
  and a closed range would report every ordinary restart as an overlap.
  **Lineage** stays as the fallback for a pair whose spans cannot both be
  measured — two legs whose notes record the same start really did re-run one
  segment, and that holds when neither reports a count; a blank start is
  deliberately not a key, since "cold start" and "we have no record" must not
  match each other. **Non-monotonicity is gone**: "ran later, got no higher a
  count" false-positives on a later leg covering an earlier, DISJOINT range, and
  intersection strictly dominates it wherever both spans are known. Measured on
  `results/solver/case`: `prev_001` and `prev_002` both ran 0-1000, an overlap
  that was silent under #32 and is now named.
- **The legs are the legs of ONE run.** A case run by both hosts holds
  `…dat.gui` and `…dat.cli` side by side and those are two solves; the live
  lookup always picked the file the user opened, and #43 extends the rule to the
  archives. The anchor is the opened file's run tag — from its name, or from its
  own `RUN.txt` when #30's rename took the tag off it — a leg whose tag differs
  is excluded and NAMED, and a leg whose tag cannot be determined is included
  rather than dropped. Note the direction that is evidence: opening the `.gui`
  leg passes with or without the filter, so only the headless-leg direction
  proves anything.
- **Opening any leg opens the SOLVE. #43 asked nothing; since 2026-08-27 an
  INTERACTIVE load asks, and a headless one still does not** (USER-REQUESTED —
  see "Which legs play" below, which reverses half of this bullet and keeps the
  other half exactly). What follows is #43's reasoning, unedited, because the
  half that survives is the half it was really protecting: an unattended run must
  not behave differently from what CI records.
  #32 shipped "ask, do not assume": a `confirm` with `headless_default=False` on
  every result load, plus `load_result_path(..., ask_legs=False)` for a caller
  that must not open a modal (`postprocess_ctrl`, reaching into `pipeline_ctrl`'s
  private `_pipeline_running`). That made the common case cost a click and made an
  unattended run behave differently from an interactive one, so a CI screenshot
  showed something the user never sees. The modal is gone, the permission flag is
  gone with it, and so is that reach. **The residue is named rather than claimed
  away**: `postprocess_ctrl` still reads `_pipeline_running` once, guarding the
  load-FAILED modal — a *different* modal, predating #32, and one an unattended
  run genuinely must not stop on. #43's story 45 asks for "no controller left
  reaching into another mixin's private state"; what landed is the reach #32
  added, not every reach. **`This leg only`** is the escape and it follows
  `Lock scale`'s rules: shown only when the solve HAS more than one leg, never
  persisted, unticked on every load. Restricting yields a ONE-leg series rather
  than a second code path, so the cache, the labels and the ranges behave
  identically either way. **Its visibility asks how many LEGS the solve has and
  nothing else** — not the `multi` (frame-count) flag the rest of the transport
  row uses. One zone per leg is an ordinary restarted solve, so ticking the box
  can leave a single-frame series, and keying on `multi` hid the whole row
  *including the box that had just been ticked*: the escape closed behind the
  user. Found in review, measured at 3 legs x 1 zone.
- **Which legs play is a CHOICE, and it is the user's** (`views/result_leg_picker.py`
  + `views/result_leg_select_mixin.py`, gated by `tests/test_result_leg_picker.py`).
  USER-REQUESTED 2026-08-27. The choice used to be binary — every leg, or `This
  leg only` — with no way to say "these three, not that one", which is what
  comparing a re-run leg against the one it replaced needs; #43's own measurement
  of `results/solver/case` found `prev_001` and `prev_002` both running iterations
  0-1000, one segment solved twice, played in sequence with no way to drop either.
  A tick-list is offered on load and reopenable from `Legs…` in the transport row.
  **`ask_legs` returns `None` — "every leg" — when headless, and `None` is also
  what a CANCEL and an empty tick-list return**: one meaning, the state the view
  already has for "no restriction", so batch and CI are byte-for-byte #43 and a
  cancel leaves the animation as it would have been. **Precedence is stated, not
  raced** (the rule `Lock scale`/manual-clim already follows): `This leg only`
  wins while ticked, then the subset, then every leg — and unticking restores the
  SUBSET, so the override does not destroy the answer it overrode. A subset is an
  ordinary `LegSeries`, never a second code path. **Both controls key on the LEG
  count and never on the frame count**, for the reason recorded above: restricting
  to one one-frame leg leaves a one-frame series, so a control keyed on frames
  hides itself the moment it is used. Asking that of a fixture with three frames
  proves nothing — measured, the injection came back green — and two of the gate's
  other three checks were weak in the same way on the first attempt (the reset
  check could not see its own mechanism, since a multi-leg load reassigns the
  selection regardless; the handler check surfaces as a CRASH, which an injection
  harness that counts FAIL lines scores as zero). Blind spot named in the test:
  offscreen the dialog is never shown, so what is gated is its verbs, the filter
  its answer drives and the controls' visibility.
- **The landing frame is the last frame of the leg that was OPENED**, not of the
  series (`ResultSeries.last_frame_of`). The two differ only when an archived leg
  was named deliberately, and then the file the user asked for is the one they
  should be looking at. A `This leg only` toggle lands there too, so the control
  moves the animation around the picture instead of moving the picture.
- **`load_result_path`'s second argument is a `frame`, not a `zone`.** It was a
  zone index within one file until #32 made a load cover several, and the
  single-file fallback (no readable series at all) no longer reuses that value as
  a file-local zone — a series index has no meaning there.
- **The variable selector is the INTERSECTION**, and the subtraction is logged
  naming the short leg. The derived quantities are recomputed from that
  intersection through the new `TecplotResult.derived_from_names` — a pure
  function of the variable NAMES, which is all the old availability test ever was
  — so a derived field cannot outlive its inputs either. Asking this from the leg
  with FEWER variables proves nothing (its own list is already the intersection),
  which is a hole the gate's own injections found.
- **The leg name prefixes a label only when the series has more than one file**
  (`prev_002 · Frame 3 / 10`), so a case that was never restarted reads exactly as
  it did. The transport's own read-out appends the SERIES position on top
  (`… (7 / 30)`) because every button here moves through the series; that is
  added in `_read_out`, not in `frame_label`, since the zone selector uses the
  label as a list entry where a second pair of numbers on every row is noise.
- **The per-variable seeded range is COMPUTED over the series, not just carried
  across it.** #24 seeds an untouched variable from the frame on screen so
  nothing jumps when Auto is unticked; across legs that basis is wrong — one
  leg's band saturates every other leg and the Min/Max boxes then describe a
  range that is not on screen, #24's own symptom one level up. So a MULTI-leg
  series seeds from the series and a single file keeps #24 exactly. The scan is
  the one "Lock scale" already pays (`scan_series_range`, now shared). **It no
  longer runs inside a paint** (#43): #32 called it from `render`, which is a
  place that cannot pump the event loop — it would re-enter the paint in progress
  — so switching variables in Custom mode froze the application for as long as
  reading every frame takes, with no way to say why. It now runs in
  `seed_range_from_series()`, called by the handler that unticks Auto, where the
  "this will take a moment" line is painted first; switching variables afterwards
  seeds from the frame on screen, and where the whole-series range is available is
  stated in the Min/Max tooltip (`series_range_hint`) rather than logged on every
  change. **A failed scan is not remembered** — `_series_seeded` records the
  variables whose range came from a scan that actually SUCCEEDED, so a transient
  read error does not pin a variable to one frame's numbers for the session. **A
  range the user TYPED is tracked separately (`_clim_typed`, written only by
  `set_clim`) and is never scanned away.** "Already scanned" does not imply it,
  and assuming it did was a real defect: the first version guarded on the scan
  set alone, so typing numbers for a variable that had never been scanned and
  then toggling Auto off and on replaced them with the series band (found in
  review, measured -999..999 -> 1.0..134.33). #24's manual-over-lock-over-auto
  precedence is out of scope for #43 and this is what keeps it that way. The
  whole colour-scale concern (lock, seed, precedence) moved into
  `views/result_scale_lock_mixin.py` when `result_playback_mixin.py` passed the
  GUI length budget; the two only ever shared a toolbar row.
- **Each leg's iteration count is where the leg is NAMED** — the tooltips of the
  frame read-out and the frame selector, which already say which leg a frame
  belongs to — rather than in a log line the user scrolls back to. It carries
  the SAME two caveats the restart chooser's tooltip does (recorded vs
  recomputed, and that an interrupted run makes the figure an upper bound):
  unifying the arithmetic so the two windows cannot disagree about a number, and
  then reporting that number with different confidence in each, would put the
  disagreement back one level up. A load emits ONE summary line naming the legs
  opened; each warning (overlap, tag exclusion, a variable gap) stays a full line
  of its own, because each changes how the picture should be read.
- `set_result`'s triangulation reuse and #24's clim precedence
  (manual > lock > auto) are unchanged and both are pinned across a leg boundary.
- **A leg's timestamp is when its run FINISHED, never its `archived_at`**
  (`case_run_note.finished_stamp`; USER-REPORTED 2026-08-27). An archive is made
  by the NEXT run at the moment it starts, so `archived_at` answers "when was this
  folder made?" while a live leg's stamp answers "when did this run finish?" —
  and both were rendered as a bare parenthesised time in one list, which is what
  invited them to be compared. On this repo's own `results/solver/case` the
  restart chooser read `Latest result (09:35:11)` beside `prev_005 (09:35:01)`:
  ten seconds apart, and they are two runs three minutes apart — the ten seconds
  are merely how long the latest run took. `prev_003` displayed a date **six days**
  out, and the two pre-#30 archives displayed nothing at all. The run's own
  outputs still carry the answer (`shutil.move` preserves mtime, and #30's hard
  link shares the inode), so the stamp is recovered from them, preferring the
  ZONE DUMP because it is written at the end of a run and `RUN.txt` because it is
  written at archive time. **`restart_points` and `result_legs` had the defect
  independently** — `stamp=note.get("archived_at", "")` in each — so the answer has
  ONE owner, the same rule #43 applied to the iteration count; `archived_at` is
  kept as its own labelled tooltip line rather than discarded. The gate's checks 3,
  4 and 8 are the INVERTED versions of the ones that pinned the old behaviour, and
  check 4's blank stamp for a pre-#30 archive was not a refusal to fabricate but a
  refusal to look.

Three duplications this created were pushed to their owners rather than left:
`case_files.strip_run_tag` / `newest_first` and `case_run_note.mtime_stamp` /
`iteration_span` are each now read by both `restart_points` and `result_legs`.
Gated by `tests/test_result_legs_playback.py` — injection-verified properties over
3 groups, with its two blind spots and the acceptance run in its own docstring.
**Two of those injections are PERMANENT**, because the obvious construction of
each passes with the code removed: the convergence fallback is injected on legs
that HAVE a note (their ends still come from those notes, so what is removed is
the START, and with it the overlap), and the run-tag filter in the direction that
FAILS (an older headless leg opened in a case whose archives are interactive) —
opening the `.gui` leg gets the `.gui` archive either way. Both carry a negative
control so they cannot pass because the patch was inert. Acceptance, on
`results/solver/case`: `prev_001 (0, 1000]`, `prev_002 (0, 1000]`,
`latest (1000, 2000]`, all recomputed, and the overlap on iterations 1-1000 —
silent under #32 — is named; the restart chooser reports the same three numbers
for the same folders, which is the point of there being one `iteration_span`.

**"The surface" of a surface plot is a CHOICE, and so is where s = 0 is**
(`services/surface_source.py` + `services/surface_sample.py`, both Qt-free;
`controllers/surface_source_ctrl.py` decides availability; `views/surface_source_dialog.py`
+ `views/result_canvas_surface_mixin.py` are the UI). Results ▸ **Surface…** used to
mean exactly one curve — the inner boundary loops of the solved triangulation —
which is the only honest answer for a body-fitted mesh and **no answer at all for
an immersed-boundary run**, where the solid never touches a mesh boundary. Six
sources are now offered, all listed even when unusable, each with the reason on the
row ("no STL3d φ field loaded (run the IB stage)"): `mesh` (unchanged, and the only
one whose points ARE mesh nodes, so it keeps `node_ids` and reads **exact** nodal
values), `field_iso` (φ = 0.5 on the solved mesh), `grid_iso` (the same on the
STL3d structured φ), `interface_cells` (**the Fit Δ points**, i.e.
`phi_quality.interface_points` — now public precisely so the plotted surface is the
one the fit report measured), `analytic` (the analytic φ shape itself, read through
`services/analytic_shape.py`, which the φ-DLL generator now shares so the plotted
body cannot drift from the solved one) and `cad`. Rules that are not cosmetic:
- **Iso-lines are chained by mesh EDGE identity, never by welding coordinates**:
  one crossing point per crossed edge, computed from the canonically sorted node
  pair so both owning triangles get the identical coordinate, then a walk
  triangle→triangle through shared edge keys. There is no distance tolerance
  anywhere — a tolerance on a fine mesh either fragments one contour or fuses two
  that merely pass close. Every crossing triangle has degree exactly 2, so a
  component is a cycle (closed) or a path (the iso-line left through the boundary),
  and `closed` is reported from *arriving back at the entry edge*, not guessed.
- **s = 0 is required, not defaulted (USER-REQUESTED)**: the old path inherited the
  origin from `next(iter(set))` inside the boundary tracer — reproducible for one
  file, but two runs of the same body could start their arc length in different
  places, which is exactly when you want to overlay the curves. Show/Plot stay
  disabled until a rule (x min / x max / y min / y max) is picked, traversal
  handedness is forced from the polygon's signed area, and the canvas marks the
  origin + direction while the plot's axis label repeats the coordinate.
- **Arc length of a closed curve now reaches the full perimeter.** The removed
  `TecplotResult.perimeter_series` computed the closing chord and then sliced it
  off, so its last sample was one chord short of where it started.
- **Off-node samples are interpolated, and δ = 0 by default.** For an immersed
  solid the interface holds the SOLID state, so an outward-normal offset δ (one
  cell is typical) is offered — but nothing is moved silently, and the title states
  `exact nodal` vs `interpolated, δ=…`. Outward comes from the polygon's own signed
  area, not from the requested handedness, or the offset would point *into* the
  body on exactly the curves that were reversed. Samples outside the mesh come back
  NaN (a visible gap), never a fabricated value.
- **The Fit Δ cloud is cell CENTRES with no connectivity**, so it is ordered by a
  greedy nearest-neighbour walk that can jump a thin waist or take the wrong
  branch; when a hop is >5× the typical one the curve says so in `note` instead of
  returning a plausible-looking arc length. Prefer the iso-line for measurement.
Nothing is extracted while the dialog is being edited — the widgets only build a
`SurfaceSpec`. Gated by `tests/test_surface_source.py` (geometry) and
`tests/test_surface_source_gui.py` (the dialog, the overlay and both result kinds).

**The grid must carry the BCs before it leaves the Mesh stage**
(`services/mesh_bc_audit.py`, Qt-free): a mesh generated BEFORE the per-segment
BCs were applied exports **every** patch as the wall default, and the solve then
looks exactly like a converged, unchanged answer — the reported "I updated the
STAR-CD boundary conditions and got the same result". The mesher's own
`NO boundary segment carries any of the GROUP_BC label(s)` warning fires at MESH
time, several clicks before the grid is exported, sent and run, so
`audit_mesh_bc()` re-checks the actual file at each of those three points
(`mesh_export_ctrl.mesh_bc_problems` / `warn_if_mesh_bc_stale`, and
`controllers/solver_ctrl.py`'s `_confirm_mesh_bc_state`, which *asks* rather than
deciding — `headless_default=True` so batch/CI, which regenerate in the same pass, are not
blocked). Two independent signals: an assigned BC **type** with no patch of that
name in the `.bnd`, and a geometry `.meta` **newer** than the mesh (the per-segment
BC and No-BL flags are projected there from the model on every edit, so its mtime
still moves when one changes — and changing one segment from inlet to outlet
leaves both names in the file, so content alone cannot see it). Note the two
namespaces this replaced a bug in: a `group_bc` key is a segment **label**, a
`.bnd` patch name is the **BC type** the mesher resolved it to — comparing them
directly (the old warning) marks every assignment missing on every run. Also:
BC detection resolves the .bnd the RUN will use (auto-link wins in
`_locate_mesh_bnd`, and `resync_solver_bc_from_group` runs *after* the auto-link),
or the table describes one grid while the solver reads another. Gated by
`tests/test_mesh_bc_audit.py`.

**A path is not a kind: project files are recognised by CONTENT**
(`services/project_file_kind.py`, Qt-free — `classify_project_file` → `"workspace"` /
`"pipeline"` / `""`; `PipelineConfig.classify_file` / `is_workspace_file` delegate to
it, so the extension never has to be right). `main.py` handed every positional
argument to the geometry loader, so `main.py case.hws` ran `np.loadtxt` over JSON and
reported `could not convert string '{' to float64` — a message naming neither the file
nor the problem. USER-REPORTED (2026-08-13). Every "open this path" entry point now
dispatches through the one classifier: the CLI's positional args,
`_load_geometry_file` (which the recent-files menu and the STL stager also reach), and
Pipeline ▸ Load, whose dialog accepts `*.hws` too. Rules: a **workspace opened in the
GUI goes to the workspace loader**, never through `PipelineConfig.from_workspace_dict`
— that conversion exists so the headless runner can *run* a `.hws` and deliberately
drops working state (cached resampled points, generated mesh/result paths, the active
tab); the CLI loads the **project first and geometry after**, because either project
load resets all state and closes every tab (geometry used to load at 100 ms and the
pipeline at 200 ms, so `--pipeline x.json geom.dat` silently discarded the geometry);
and only ONE project file is accepted per launch, the rest named and refused. The
"this will close all current tabs" prompt is gated on `has_unsaved_work()` — the GUI
always opens with one pristine blank session, so otherwise opening a workspace from
the command line put a modal in front of an empty canvas.

**The same failure had a SECOND instance, outside the GUI, for three weeks (#58).**
`tools/scripts/visualize_dat.py` still handed every path it was given to
`np.loadtxt`, so `visualize_dat.py mesh_multiblock_square.vtk` ended in an unhandled
traceback reading `could not convert string 'HybMesh2D' to float64 at row 0,
column 1` — `HybMesh2D` being the provenance banner on line 2 of a legacy-VTK header.
Same shape as the `'{'` message above, and found the same way: by pointing the tool
at a file this repo had just produced. The rule had been applied to the GUI's "open
this path" entry points and to nothing else, which is what makes a *fixed* bug class
worth a second ticket even when the instance is cheap. Three decisions, and two of
them are refusals. **It does NOT import `project_file_kind`**: that module is Qt-free
but lives inside the GUI package, and this script's whole dependency set is numpy and
matplotlib — so the ONE kind this tool is actually handed (legacy VTK, identifiable
from its first line) is recognised locally, in a `looks_like_legacy_vtk` that reads
256 bytes and carries the reasoning and the cross-reference in a comment. Note what
is and is not shared here, because the first draft of this note got it wrong and the
#58 review caught it: `project_file_kind` classifies JSON PROJECT files and has no VTK
notion at all, so this is not a second spelling of an existing check but a second
instance of the same RULE. What would belong beside the classifier is a SECOND caller
of the VTK question; there is one caller, and user story 3 pre-authorised keeping it
local ("a five-line local check that carries its reasoning is also an acceptable
answer for a tool this size, and is the cheaper one"). **It does
not delegate the drawing** either: naming `tools/scripts/view_mesh_vtk.py` in the
message is smaller than importing it and cannot be wrong, and the suggested command
was run rather than assumed. And numpy's own `at row R, column C` is kept verbatim
for a genuinely malformed geometry — it is the one useful thing the old message
carried, so a fix that dropped it would trade a blind error for another blind error.
`plot_element`'s two loads got the same treatment: both were bare `except:` bodies,
so a mesh named as an element's `output_file` or `input_file` drew an empty figure
and said nothing at all. Gated by `tests/test_visualize_dat_kind.py`, whose group 1
meshes `examples/topology/square_block.json` with the real binary rather than writing
a fixture (no `.vtk` is tracked — `results/` is ignored) and then checks the SAME
bytes under a `.dat` name, because that is the half an `endswith(".vtk")` would fake.
Its six injections are recorded in the file, and two of them earned their keep — one
showed that `"mesh" in out.lower()` was satisfied by the banner `HybMesh2D` inside
numpy's own message, so a check passed while the feature was deleted; the other that a
group-4 check did not name the field it was about, and passed on the other element's
warning. **What no injection could find, and the review did**: the first fix guarded the
PARSE and not the SHAPE. `np.loadtxt` collapses a one-column file AND a one-point
geometry to the same 1-D array, so `visualize_dat.py one_column.dat` parsed fine and
then died in `ax.plot` with an `IndexError` naming no file — this ticket's own
complaint, moved three lines later. Every injection mutates the new code, so none of
them reaches a path the new code never touched; that is the standing limit of injection
as evidence. `load_geometry` now returns an `(N, >=2)` array or raises, `ndmin=2` being
what makes the one-column file and the one-point geometry distinguishable at all.
**Blind spot**:
only legacy VTK is recognised. A `.vrt`/`.cel`/`.bnd` handed to this tool is columns
of numbers, so it parses, and the failure is a wrong picture rather than a wrong
message. #58 scopes every other kind out.

**The Output field's `.*` is a placeholder, and only one module may read it**
(`models/mesh_output_names.py`, Qt-free — `output_base` / `output_path_for` /
`FORMAT_PLACEHOLDER`, re-exported as `MeshConfig.*` so every existing call site is
unchanged; that module also owns `auto_case_name` / `auto_output_name` /
`is_auto_output_name`, whose `<case>` naming is mirrored in `src/cli.cpp`). The Mesh
panel's Output field holds ONE name for however many formats are enabled, so it is
filled in as `results/meshes/<case>/mesh_<case>.*` — and because the panel→model sync
runs on every edit, that string IS the model value and travels verbatim into the
workspace, the pipeline script and the mesher's config. Only the export dialog
understood it, in a private `endswith(".*")` branch, so: the **mesher** wrote a VTK
into a file literally named `mesh_<case>.*` (see `cli.cpp` above), and
**`pipeline_runner`** handed that name straight through and then `os.path.exists`-ed
it — which the glob-named file satisfied, so the run reported success and passed a
glob to the contour stage. Note the coupling: a C++-only fix turns that silent pass
into a hard failure, so both halves move together, and `_mesh_output_path` is split
out of `_run_mesh` to be testable without a mesh run. `tests/test_output_format_placeholder.py`
gates the resolver, the end-to-end `-out_name <dir>/probe.*` run (no file with a `*`
in its name, banner reports the resolved basename), and **statically fails the build
if any other GUI file grows its own `endswith(".*")`** — a second private copy is how
this diverged in the first place.

**The last generated mesh is not where a reopened case left it**
(`services/mesh_grid_lookup.py::resolve_case_grid`, Qt-free): Generate Mesh writes its
output into the GUI's **temp dir** on purpose (`<temp>/global_mesh.*`, so generating
does not litter the repo — the stable per-case files appear on Export / Send to
Solver), and that directory is removed on exit, so `global_vtk_path` is **always**
empty or dangling in a reopened workspace. Auto-link read only that and answered
`No mesh generated yet` for a case whose grid was on disk and whose own Grid
Conversion fields still pointed at it — USER-REPORTED (2026-08-13) together with the
`.hws` failure above. The resolver tries this session's mesh, then the triple the case
is **already wired to** (what the workspace restored, i.e. what the user last actually
sent to the solver — trusted over any guess), then the per-case exported mesh, and
takes the first whose `.vrt` + `.cel` + `.bnd` all exist; it names which one and why in
the log, and names every candidate when none works. `_locate_mesh_bnd` asks the SAME
resolver, or the BC table describes one grid while the run reads another. Whether that
grid is STALE stays the mesh-BC audit's job (`_confirm_mesh_bc_state`), not a refusal
to run. Both blocks gated by `tests/test_open_project_by_path.py`.

**A re-save of the geometry must not throw the Mesh-stage edits away, and the fix
is a MODEL FIELD rather than a wrapper around the subprocess.** Both halves of a
per-segment BC live in the `.meta` — the **label** in the NSEGMENTS bc column, the
label→type map in the trailer — and the resampler REWRITES that sidecar from the CAD
config on every save. It carries the trailer through verbatim but the bc column comes
back `-` and the v3 grow column comes back 1, so a CAD tweak + Save left the map
pointing at labels nothing carries: the mesher warns
(`NO boundary segment carries any of the … GROUP_BC label(s)`), every patch
exports as `wall`, and the GUI still shows the BCs it holds in memory. USER-REPORTED
(2026-08-12) as "I set the BCs in Edit Seg BC, why `no boundary patch named inlet,
outlet`?".

The fix is **not** in the resampler, which stopped preserving the prior sidecar
itself on purpose, because a NEW geometry written over an existing output name then
inherited the old geometry's flags (`tools/PreProcessor/src/main.cpp` says so in a
comment). It is also **no longer a caller-side snapshot/restore around the
subprocess** — that shipped first (`meta_io.snapshot_seg_edits` /
`restore_seg_edits`, three call sites) and is now **gone**, along with its
`describe_seg_edit_restore`. Both facts are `SegmentModel` **fields** instead: `bc`
already was one, and **`grow_bl` is new** (default True; `to_dict()` emits it only
when False, so every pre-existing config, workspace and script stays
byte-identical). The resampler has always read `sj["bc"]` and `sj["grow_bl"]` from
its own config, so `to_dict()` — the single serialiser behind the resample config
(`models/project.py`), the `.hws` workspace (`session_io_ctrl`) and the pipeline
script (`pipeline_config.cad_section`) — makes the sidecar come back **correct the
first time**. Measured against the real binary: `grow_bl: False` + `bc: "inlet"` in
the config survive a resample; the same config without them still comes back wiped
(so the mechanism is not redundant); and a *different* geometry over the same output
name inherits nothing, which is the reverted failure mode staying dead. The fact
moved **up**, not back down: the model knows which geometry it describes and the
resampler does not.

Three consequences worth knowing. **The `.meta` is now a PROJECTION of the model,
not a second home** — `mesh_layers_ctrl._write_sidecar_from_model` rewrites both
columns after every edit, and it is the command's `refresh_cb`, so an **undo rewrites
the file too**; reverting the model while the file kept the old column would leave the
mesher reading the un-undone value. Every existing reader (the BL dialog's seeding,
the mesher) therefore needs no change — the file still says what it always said, it
just no longer decides it.

**But a projection must be SEEDED first, and forgetting that broke the very thing
this work exists to fix.** The projection is total (every segment the model holds),
nothing ever seeded `SegmentModel.bc`/`grow_bl` from an existing `.meta`, and the BC
dialog reports only NEWLY MINTED labels — so on any geometry whose setup lived only in
its sidecar (i.e. every case predating the model field) one Mesh-stage BC edit reset
every *other* segment's label to `-` **and** re-enabled a No-BL wall it had never read.
Measured: four labels and one flag became one label and none — the same all-`wall`
export the model field exists to prevent. `_adopt_sidecar_facts` now takes the
sidecar's values into the model first, **fill-in only** (a fact the model holds wins; a
fact only the file holds is adopted — the same rule `ib_handoff` applies to a scripted
phi path), and it runs **BEFORE the undo snapshot**: adopting after it still fixes the
wipe but makes undo restore the *empty* value, re-wiping the sidecar it just protected.
Both the presence and the ordering are pinned separately in the gate, each verified by
injection. Adoption is a migration of the user's existing setup rather than an edit of
theirs, so it is not undoable and is **named in the log** instead — it also means
legacy labels start travelling in the workspace and the pipeline script, which is the
point of the candidate. A caveat that follows: the fill-in rule cannot distinguish
"the model holds `grow_bl = True`" from "the model is at its default", so a sidecar
`grow=0` is always adopted; that is right for the migration and would be wrong if the
file were ever allowed to lag the model, which the projection is what prevents. And **the id-set-changed refusal disappeared as a
concept**: the old restore had to drop everything when the segment id set moved,
because it re-applied by id after a subprocess had rewritten the file, and a label
bound to a segment object cannot be shifted onto its neighbour by inserting an edge.
The Mesh-stage dialogs consequently **emit** (`seg_grow_bl_changed` /
`seg_bc_labels_changed`) instead of writing the sidecar themselves — a view writing
that file is how the fact came to live only there. A geometry with **no CAD session
behind it** (an external `.dat` browsed in, or one left by a closed tab) has no model
to hold the fact, so the handler falls back to writing the sidecar directly; that is
correct for a geometry this app does not resample, and
`_session_for_geom_path` returning None is a normal outcome rather than an error. The
label→BC-**type** map (`GROUP_BC`) deliberately did **not** move: it is keyed by label
rather than by segment (one label covers many segments), so there is no segment field
for it to be a field of, and the resampler carries the trailer through verbatim, so it
never needed the rescue the label column did. Two knock-on effects of reusing
`UpdateMultipleSegmentsStateCmd`: a Mesh-stage No-BL toggle now sets
`is_geometry_modified`, so the CAD tab shows `*` and prompts on close — defensible,
since the flag is genuinely model state that must be saved to persist, and reverting it
would stop undo restoring the dirty flag.
Gated by `tests/test_seg_edit_carryover.py`, which drives the real
`surface_resampler` (so the wipe cannot quietly stop happening) and the real
controller handler (so undo, redo and the projection are proven, not asserted).

**Signal guards**: never write a raw `blockSignals(True)`/`blockSignals(False)` pair — an exception between them leaves the widget permanently unable to emit. Use `with block_signals(w1, w2, ...)` (`app/utils.py`). Likewise, never assign `_is_populating`: use `with controller.populating():`, which is a re-entrant depth counter (a bare bool let a nested populate clear the outer guard). `tests/test_signal_guards.py` statically fails the build on either.

**Error handling**: never a BROAD `except` that discards. Use `services/logging_setup.py::get_logger(__name__)` and log at `debug(..., exc_info=True)` for a step allowed to fail, or `warning` when the failure silently degrades what the user asked for. `HYBMESH_LOG_LEVEL=DEBUG` surfaces the debug tier. `tests/test_silent_exceptions.py` fails the build if a new undocumented silent handler appears. The rule is `.claude/rules/gui-seams.md`'s; why it is about the handler rather than about `pass`, and what the widening found, is "A standard that bans one KEYWORD" below.

**File length — why the number got a gate, and why its pins are a ceiling.** The rule is
`.claude/rules/gui-seams.md`'s ("keep each file under `tools/PreProcessor/gui/` at ~500 lines");
this is what was measured. Of the four standards that bind before any file is opened, this was the
only one nothing enforced, and the cost is measurable rather than arguable. One walk of each GUI
`.py` file's own history on 2026-09-09, comparing every blob with its predecessor: **44 commits
across 35 files** took a GUI file past 500 lines. **Four of those landed in the six days after #67
wrote the standard into `CLAUDE.md`** (2026-09-02) — `98003f1` (#85) `models/mesh_config.py`
499→505, `306d6a1` (#91) `services/pipeline_runner.py` 490→537, and the #47 merge `8bdc36a` twice
in one commit (`controllers/mesh_gen_ctrl.py` 490→512, `services/pipeline_runner.py` 498→506). A
review caught three of the four, always after the fact; nothing caught `98003f1` at all. The same
merge split `mesh_config` 505→426 for exactly this budget while breaking two other files, so the
failure was never ignorance of the rule — it was inconsistency, which is the signature of a rule
whose only enforcement is whether somebody happens to look. #97 replaced that with
`tests/test_file_length.py`.

Three decisions inside that gate were bought rather than assumed:

- **The seven files already over the limit when the gate landed are PINNED, not exempted, and the
  pin fails in BOTH directions** — growing further fails (already over is not a licence), dropping
  back under fails as an obsolete pin. #102 collected the first of those failures on purpose:
  splitting `controllers/mesh_gen_ctrl.py` turned its own pin red as obsolete, and clearing the
  entry is what closed the ticket. That is `test_instruction_budget.py`'s `KNOWN_RESIDUE` shape, reused because
  it had already been proved here: those pins failed the moment #76 stopped them being violations,
  rather than quietly outliving the defect the way a skip list does.
- **A pin is a CEILING, not an exact measurement.** An exact-match pin is the stricter rule and was
  rejected: #102 and #103 split two of these very files rather than living inside their pins, and
  an exact match would go red on every intermediate commit of the work the gate exists to provoke — `ruff.toml`'s "a permanently-red
  gate is worse than none" arriving through a different door. The cost is a real hole (a pinned
  file may shrink and grow back to its pin unseen), bounded by a pin that never rises, and it is
  recorded as a named blind spot rather than left implicit.
- **The end-to-end injection reads a child process's EXIT CODE, and exit 1 alone is not enough.**
  An unhandled exception in the child also exits 1, which is the exact confusion the exit-code rule
  was written against — this repo has previously scored a crashed injection as a bite that never
  happened (a FAIL-line count reports a crash as zero bites). So the verdict is exit 1 AND an empty
  stderr AND the offender named in stdout, with a negative control asserting the same command exits
  0 once the probe is removed. The probe is written at the GUI ROOT rather than inside `app/`, so a
  run killed between the write and its `finally` cannot leave an importable module behind, and the
  name is in `.gitignore` so such a leftover cannot be committed.

The status figure the instruction files print about this standard (5 of 277, worst 524) is DERIVED
from the same walk that ENFORCES it, in all three files that state it — this one, the root and
`.claude/rules/gui-seams.md`, which lists every offender by name (#101). The 44/35 history
count deliberately is NOT gated —
`test_instruction_budget.py` blind spot (g) states the reason: a git-history figure decays on every
commit rather than on every edit to the file, so gating one would make each commit re-measure
`git log`, and there is no fixed point to converge on.

**A standard that bans one KEYWORD has three other spellings of the same silence.** The rule is
`.claude/rules/gui-seams.md`'s ("never a BROAD `except` that discards"); this is what #118
measured and decided. The standard has always been ABOUT the handler — a catch that neither
records the failure nor re-raises it — and its gate implemented that by matching a body of exactly
`["pass"]`. #117 is the evidence that the gap is a defect and not untidiness: a refactor moved
what REACHES one of these handlers, a correct skip became a swallowed diagnostic, nothing in the
handler changed, and every gate stayed green because the body said `continue`. No review would
have caught it either; nothing about it looks like a regression in a diff.

Four decisions inside the widening:

- **BROAD, not every handler — and this is the whole of why the gate can be green.** The ticket's
  figures (28 `pass`, 14 `continue`, 3 `return`, 0 `break`) reproduce EXACTLY when the scan is run
  over every `except` clause in `app/` on the pre-#117 tree — its `3 return` counting BARE returns,
  with 65 more spelled `return <value>` under the same scan, which is worth stating because the
  widening shipped here treats those 65 as the same silence. That is the scan that would need an
  allowlist of a hundred-odd sites: `except ValueError: continue` inside a line parser is the
  correct idiom and this tree is full of deliberate narrow fallbacks (`except OSError: return []`
  in `services/meta_io.py`, `except (TypeError, ValueError): return 1.0` in `services/units.py`).
  A gate that red-lights correct sites to find one real one gets worked around rather than obeyed
  — `ruff.toml`'s "a permanently-red gate is worse than none", the same door #97 came through. So
  the line is drawn where the STANDARD draws it, at a catch wide enough to swallow an error nobody
  predicted: `except Exception:`, `except BaseException:`, a bare `except:`, or a tuple holding
  either. Re-derived on the tree the widening actually landed on (#118's own criterion says to),
  that reaches **10** sites rather than 17, and check 2 prints the count on every run rather than
  any file restating it.
- **Every one of the 10 was FIXED; the allowlist did not grow.** The project baseline and its
  dirty comparison (`warning` — "conservative" means the close prompt that protects unsaved work
  never appears again), the curve preview (`warning` — the edge does not draw), the two geometry
  reads behind the auto-sizing hints (GRADED, below), the transform handle length, the gmsh probe
  and the formula evaluator's two (`debug`). Two of the ten were deleted outright rather than
  logged: `views/panels/mesh_sizing_mixin.py` guarded two deferred `import numpy` calls with
  `except Exception: return None`, and numpy is a hard dependency of this GUI, so those handlers
  were unreachable defensive code. Deleting a handler is the better half of "fix it or allowlist
  it", and `test_qt_free_seam.py` check 6 already says a deferred import is still a dependency.
- **Where one failure can mean two things, RESOLVE first and the question answers itself — and the
  first version of this got it wrong in a way worth keeping.** #117's distinction is that a
  geometry the user has not produced yet is not an error while one that is there and will not read
  is, and the two auto-sizing hint scans reach both. The version that shipped in `77c2561` computed
  the grade with `os.path.exists(p)` on the entry the list widget carries. Review caught it against
  `.claude/rules/gui-panels-config.md`'s "a reader RESOLVES an entry before opening it": that entry
  is the stored `MeshConfig.geom_files` spelling, repo-relative for a file inside the repo, so from
  any other cwd BOTH the grade and the `np.loadtxt` beside it answer about the wrong directory — a
  geometry that is really there reads as one the user has not made yet, which is #117's
  distinction inverted by the helper written to make it. The fix is the verb, not a better
  predicate: `mesh_sizing_mixin._hint_points` calls `readable_geom_path`, whose `""` IS the
  "nothing to record" answer, and everything that reaches the open is a genuine read failure it
  `warning`s. That makes it the seventh caller of that verb and the fifth that opens — a count
  restated in four places, now stale for the second time in two tickets, and updated in all four.
  The raw `np.loadtxt(p)` it replaced was PRE-EXISTING and outside this ticket's scan; `check 12`
  of `test_geom_files_identity.py` does not reach it, because these paths come from the widget's
  item data rather than from `cfg.geom_files`, which is the blind spot that let it live there.
- **`ast`, not a regex plus an indentation walk.** The old scan reconstructed the body from the
  next seven lines by indentation, so a comment above the keyword, an `except` clause spilling
  over two lines or a docstring inside the handler each walked around it, and it could only ever
  see the one spelling it was written against. The AST sees the handler, which also made a fifth
  and sixth silence free: `return <fallback>` (the caller cannot tell it from success) and a body
  that is nothing but a string literal (the loudest-looking silence there is, since the text
  usually reads as an explanation). The same parse widened the ROOT from `app/` to the GUI tree
  the standard actually binds, which is how `gui/main.py` came inside it.

Check 2's injections are in two tiers, because the in-process ones cannot prove the walk. In
process, against the scan's output as a value: each of the six discarding bodies fires alone,
three at once are all reported in one run, an allowlisted site does NOT fire while the same site
without its comment does, an allowlist entry whose file stops holding one fails as obsolete, an
unparsable file is a failure rather than a skip, and a negative control shows the real tree passes
because its silent sites are exactly the allowlisted ones. End to end, a probe file is written
into the real GUI tree and the gate run as a child in `--scan-only` mode, once per keyword — the
verdict exit 1 AND an empty stderr AND the probe named in stdout, with the probe removed for a
final run that must exit 0. The allowlist gets the same treatment rather than only the in-process
one: `--allow-probe` adds the probe's own path to the allowlist for one child run, which must exit
0, against the identical file without the entry (exit 1), the identical file without its
comment (exit 1), and one whose only `#` sits inside a STRING (exit 1 — the explanation half reads
real `tokenize` COMMENT tokens, so it cannot be satisfied by punctuation, and the same probe proves
a handler whose body is a string statement plus `continue` still reads as `continue`). The lever can only ever reach a filename this gate writes and deletes itself, so
it exempts nothing real — the alternative was editing one of the three genuinely allowlisted source
files, which a killed run would leave modified, and this repo has already lost a fix to a stale
injection backup once. That is `test_file_length.py`'s shape reused rather than reinvented,
including the GUI-root probe location and its `.gitignore` line.

**A GEOMETRY IS THE FILE IT NAMES.** `services/geom_path_identity.py`, the rules in
`.claude/rules/gui-panels-config.md`. USER-REPORTED 2026-08-20, reopening an exported case
package: the Mesh Generator listed every geometry twice and Run All died with
`HYBMESH_ERROR 3 GEOMETRY_LOAD results/resampled/Untitled`. Every dedup guard in the tree was a
`not in` string compare over `MeshConfig.geom_files`, so `results/x.dat` and `/repo/results/x.dat`
were two entries for one file — measured as two identical `GEOM_FILE` lines, i.e. a doubled
boundary handed to the mesher, not an untidy list. The resolution base was `os.path.abspath`, so
the same entry named `<repo>/results/…` launched from the repo root and `/private/tmp/results/…`
launched from `/tmp`, and `repo_root()` was already imported in that same function for relativising
OUTPUT only. Canonical is `realpath` and NOT `(st_dev, st_ino)` — `case_workspace`'s inode rule is
the stronger test but needs the file to exist, and the entries this reasons about are exactly the
ones that may not (a reopened package carries no CAD).

**The verbs did not stay on the config class, and the reason was the 500-line standard.** They live
in `models/mesh_config_geoms.py::GeomListMixin`, split off when `mesh_config.py` crossed it; the
merge that landed this took that file 505 -> 426 lines, so the split is what put it back under the
standard rather than a tidy-up done beside the fix. That split is also what makes the AST gate's
allow-list derivable at all: it is keyed to where the verbs LIVE (`inspect.getsourcefile`), so
`models/mesh_config.py` — the config class itself — is provably not exempt, which the mixin's
own docstring had claimed it was.

**Shipping only the ADD sites was worse than not starting**, which is the durable lesson here:
the first round converted the six additions and left the removals and the `in` tests comparing
strings, so `mesh_layers_ctrl` added a layer by identity and un-added it by string — on a config
holding the relative spelling the checkbox drew **Unchecked for a geometry that was in the
mesh**, and unchecking it cleared the box and left the geometry to be meshed. `remove_geom_file` existed and
was called from nowhere. A review found that; nothing in the tree could, which is why the verbs are
now ONE set the rule file names in full — `add_geom_file` / `remove_geom_file` / `has_geom_file` /
`set_geom_files` / `role_of` / `prune_roles` / `dedupe_geom_paths` — and why the rule is an AST
gate over every raw construct rather than a convention (#99, and its own widening was still
incomplete until review found the constructor keyword). The verb set is also why the ownership map
above exists: verb-only is exactly the shape the syntax scan cannot see.

**#104: three residues, all of the same shape — a rule stated in more places than it is enforced.**
(i) One canonicalisation loop was hand-written three times, the add path re-deriving the canonical
key that the membership verb beside it already answers. Three copies of one rule is how the
string-compare defect got in, so the loop is now `keyed_geom_paths` and the verbs read it — all
but two of those that ask an identity question, and #110 made those two say why at the code rather
than only in the rule file:
`remove_geom_file` asks about one file and compares through `same_geom_file` (the keyer drops a
falsy entry, which is a dedupe's job and would make a removal delete the empty entries beside the
one it was asked about — now gated, check 7), and `role_of` walks the roles dict against the key
it already has. The same ticket found the third hand-written copy the first sweep left behind, in
`geom_files_not_on_disk`, which is the keyer's exact shape and now reads it. (ii) The identity
import was function-local in `mesh_config_io` where no cycle required it. Measured rather than
assumed: that module imports first in a fresh interpreter and drags in no Qt, which matters because
it is on the headless path. The check that proves it immediately caught a *fresh* deferred import
the same change had just added to `mesh_canvas_loader` — the gate paying for itself inside its own
ticket. (iii) Callers still STORED what `os.path.abspath` returned: the exact cwd-relative
spelling rule (i) of the module condemns. Nothing was broken by it, because every comparison
canonicalises, which is precisely why it survived — a rule contradicted by its own callers and no
symptom to point at.

**Routing the restore through the verb changed three things nobody had declared (#110).**
`load_from_dict`'s rebind became `set_geom_files`, and with it a duplicate identity collapses, a
falsy entry is dropped and the restored list stops being an alias of the `dict`'s own. All three
are right for a stale workspace — a saved file is exactly where one geometry appears under two
spellings — but they were carried by a comment, which is the same shape as a rule stated at a
constant and enforced nowhere. Check 10 asserts them through the public restore API and shows each
non-vacuous by re-running the rebind they replaced on the real model, so the comment is now a
description of something a gate holds. It asserts the fourth consequence beside them — a JSON null
for the list lands as `[]` — with NO injection, because the rebind's own `or []` got that one
right: a non-vacuity claim is per assertion, and three of the four are the verb's doing.

**Two MORE of #110's changes were undeclared, and one was taken against a stated Implementation
Decision (#121).** #108's decisions read *"The only new module-level surface is one read-side verb
in the Qt-free geometry-identity service"*; #111 added that verb, `readable_geom_path`, and #110
had already promoted `_keyed` to `keyed_geom_paths` beside it — two new surfaces, not one.
Promoting it was still right: "the canonical-key loop is written ONCE" is a claim only checkable
against a list of readers, and a private helper cannot carry that list where a reader of the
model's verbs would look for it. The cost was real and landed with check 12, which shipped
recognising ONE canonicalising name — so the banned shape written through the second verb was
invisible, with an instance of it already sitting in the tree, until #119 measured the set off the
module. The second change is
`remove_geom_file("")`: it used to canonicalise both sides, so a falsy argument canonicalised to
`""`, matched every falsy entry and stripped them all, reporting True. It now removes nothing and
returns False — the answer the delegation reason itself demands, since a removal that deletes the
empty entries beside the one it was asked about is exactly what refusing the keyer avoids — but no
ticket asked for the flip, and a behaviour that is merely GATED is not a behaviour that was
DECLARED. Neither is reversed; both are recorded in `.claude/rules/gui-panels-config.md`, where the
rule lives. What should have caught them is #108's own closing audit, which recorded 23 of 24
stories met and was more generous than the gates it read in three of those rows; it is corrected by
a new comment there rather than edited, so the original stands beside the correction.

**Storing the repo-relative spelling forced the READ side into the open, and the first sweep of it
was WRONG.** With the entry stored as `results/resampled/x.dat` rather than absolute, every call
site that opened the raw string answers against the process cwd. They already would have, for the
repo-relative entries a loaded workspace or a saved script has always carried; the change only
makes the common case common. The first pass converted five readers — the Run-All pre-flight, the
mesh bbox scan, the BC canvas overlay, the preview loader thread, the `.bnd` audit — and the two
review axes found **five more it had missed**, four from Standards: `read_meta_group_bc` in the mesh panel,
`read_meta_segments` and `write_meta_group_bc` in the BL mixin, and `mesh_layers_ctrl`'s
`write_meta_*`. Two lessons, and the second is the one worth keeping. First, the WRITE sites were
the dangerous half: `write_meta_group_bc` against the cwd drops a stray sidecar in a tree beside
wherever the GUI was launched, leaving the real one holding the old BCs — the all-`wall` grid of
2026-08-11, reached by a new route. Second, nine hand-converted call sites is the shotgun-surgery
shape of one rule, and the fix was not to convert the last four: every one of the nine reaches its
sidecar through `meta_io.meta_path_for`, so the rule went THERE — a `.meta` belongs to the FILE,
not to the spelling. The fifth, from the Spec axis, had no sidecar in it at all — the canvas
SELECTION HIGHLIGHT, reading the list item's own data, which is the stored entry verbatim; its
symptom is the same silence, a highlight that stops drawing. What is left at the call sites is the
five readers that open the geometry itself, which have no such choke point.

**One thing `os.path.abspath` is still right for, and the same review found it being taken away.**
A path the USER gave — a CLI argument, a dialog result — really is cwd-relative, and
`session_load_ctrl` loads the points from it that way. Storing `stored_geom_path(input_file)` from
the RAW spelling therefore resolved against the repo while the load beside it resolved against the
cwd, so the session could load one file and list another — a defect the abspath the change was
removing had been preventing. The rule is not "abspath is wrong"; it is "the base for an ENTRY is
the repo". Resolve the user's path with `abspath` first, derive the entry from that.

**The read side got its verb last, and the argument for it is the one the sidecar side already
made (#111).** After #104 the asymmetry was the recorded blind spot: the STORE side had an AST
gate, the sidecar side had `meta_path_for`, and the five call sites that open the geometry itself
had neither — each answering "canonicalise the entry, then find out whether there is anything to
open" for itself, which is two steps of one rule copied five times across three layers. FOUR of the
five spelled the second step `os.path.exists` on the canonical path; the BC overlay spelled it by
letting `np.loadtxt` fail into its own `continue`, which is the same question with no separate call
to name — worth stating exactly, because "all five wrote the same two steps" is the kind of round
number this repo keeps having to walk back, and both review axes walked this one back independently.
Two review axes that cannot
see each other converged on it from opposite directions, the Standards axis as duplicated code and
the Spec axis as a rule #104 said would be expressed once and is not; and the reach was known
rather than assumed, since #99 and #104 each paid for a full-tree sweep and each had a review find
sites it had missed. So the third sweep bought a seam instead: `readable_geom_path`, entry in, the
canonical path or `""` out, the existence question answered inside. The shape of the verb is
decided by what the five callers asked, not by what a path helper could offer — existence is
`os.path.exists` and not `isfile`/`os.access`, because a file that exists and still cannot be read
is the OPEN's failure and the layer that opens it is the one holding the filename and the
exception; and it stays at the PATH layer, absorbing neither the loader thread's NaN/`(N,2)`
validation nor anything else that has a home.

**That last clause was written as "every caller already has a handler holding the filename and the
exception", and it was FALSE of two of them on the day it was written — which is the argument this
seam rests on being an assertion rather than evidence (#117).** Counted rather than asserted, the
callers are SIX and only FOUR open a file: the mesh bbox scan, the preview loader thread, the BC
overlay and the selection highlight. The Run-All readiness check and `add_all_sessions_to_mesh`
never open one, so there is no open failure there to pre-empt — which also corrects the rule file's
"five of them OPEN", a count that included the readiness check — and `test_geom_files_identity.py`'s
check 11 comment, a FOURTH home of it that the first pass of this very fix missed. (#118 moved both
numbers again, to SEVEN and FIVE, by converting the auto-sizing hint reader; see "a standard that
bans one KEYWORD" above. A count restated in four places is a count that goes stale in four places,
and this one now has done so twice — but the alternative, deriving it in a gate, would pin the
CALLERS of a verb rather than its contract, and check 12 already holds the reach. #127 is where
the three statements that still said FOUR were corrected: "Five, not four", below.) Of the four, the
loader thread
named both halves (`[preview] skipping malformed geometry '<f>': <e>`) and the bbox scan named the
file only on the branch where its fallback `open` SUCCEEDED — when the file is genuinely unreadable
that fallback raises too, into `except OSError: pass`. The BC overlay's handler was
`except Exception: continue` and the selection highlight's `except Exception: return`: the file,
the exception, everything, gone.

**A refactor that changes what REACHES a handler can turn a correct silence into a swallowed
diagnostic, with every gate green and not one character of the handler edited.** That is the
mechanism, and it is worth naming because nothing about it looks like a regression in a diff.
Before #112 those two handlers WERE the existence answer — the missing file raised inside
`np.loadtxt` and the skip was correct, because a geometry the user has not made yet is not an
error. #112 moved the existence question OUT, in front of the open. From that commit on,
everything arriving at the unchanged handler is a genuine read failure on a file that exists. The
standard's own gate could not see it either: it matched a handler body of exactly `["pass"]`, and
these two spell it `continue` and `return` — the back door #118 then closed, below.

#117 fixed the three rather than softening the claim, all at `warning`: the standard's grade for a
failure that silently degrades what the user asked for, which is what an overlay that does not
draw, a highlight that does not appear and a geometry silently absent from the bbox each are. The
proof is what all five RECORD, not what they return — `tests/test_silent_exceptions.py` 7–8 drive
the real `AppController` against a real unreadable file (chmod-000, falling back to a directory
where a file should be for a user who can read anything) and read `results/logs/gui.log` — plus the
loader thread's stdout, captured rather than read off the source, since "we looked and it names the
file" is the evidence this ticket exists to replace. Check 8
is the other half and the reason this is a fix rather than a noise increase: an ABSENT geometry
must still produce NO record, so the two cases stay distinguishable. SEVEN injections, verdict from
the EXIT CODE with a negative control on the unmutated tree: reverting each of the three handlers
bites its own check, the loader thread's print replaced by `pass` bites the fourth, making the
BC overlay log the absent case too reddens check 8, and #127's two below — the hint reader
silenced, and the hint reader made to log the absent case — bite 7 and 8 respectively.

**Five, not four — and the sentence above said FOUR from #118 until #127.** #118 added the
fifth opener, `mesh_sizing_mixin._hint_points`, and left every statement of the count behind
INSIDE the commit that made it wrong: this paragraph, check 7's own summary and check 8's message
all still read FOUR, while the rule file and the verb's docstring read FIVE — two numbers for one
set, with the gate holding the wrong one. Worse than the figure, the fifth reader was driven by
NOTHING: run before this fix, `grep -rn '_hint_points' tools/PreProcessor/tests/` matched
nothing at all, so its
handler was correct only by READING — which is the state the BC overlay's handler was in before
#112 moved what reaches it, i.e. the exact argument this whole section exists to make. #127 drove
it the way the other four are driven (it is a module-level function, so the check calls it
directly — no panel, no widget tree) and corrected the three sentences. Of its own two injections
the sharper is the one that reddens check 7: the silent handler was written
`pts = None; return pts`, which check 2 cannot see (blind spot (a)), so the run's ONLY two FAILs
were check 7's — proving that what holds this reader is check 7 itself and not the keyword scan
that happens to sit beside it. The count stays PROSE rather than joining the `--sync` ledger:
deriving it would mean resolving five call sites of one verb through an AST, which pins a verb's
CALLERS rather than its contract and is past the "derivable in one walk" test #101 set; a third
staleness is when that trade changes.

No plural form was added, because only one of the SEVEN would have written the comprehension — the
Run-All readiness check, the one that opens nothing (the count here read "five" until #117
recounted the callers): the bbox scan and the BC overlay need the stored spelling for their log
line and their role test as well as the path. The conversion is
behaviour-preserving by construction — a missing file still reaches each caller's existing skip,
with no new refusal and no new log line — so it is held by the GUI gates that already run rather
than by tests written to prove a conversion correct, and check 11 holds the VERB's own contract,
driven from a foreign cwd with the raw `os.path.exists(gf)` measured beside it as the negative
half. The check is FOUR assertions and only three of them are the verb's: the fourth measures the
FIXTURE — that `os.path.exists` on the same entry from the same cwd really does answer differently
— and it is labelled a fixture control rather than an injection, because no mutation of the verb
can turn it red. What makes check 11 non-vacuous about the verb is the mutation run beside it:
rewriting the body back to `os.path.abspath` exits 1 with the first assertion the first FAIL.
Calling a fixture control an injection is the shape #110's review had already named — a
check that only argues.

**What the seam does NOT cover, measured for #112 rather than left for it to find — and the count
was wrong the first time it was written down here, which is the ticket's own lesson recurring one
paragraph later.** The line numbers below are as measured AT #111 (`e1f98fc`) and have already
moved; the method names beside them in the next section are what to grep for. Walking the AST for a filesystem call whose argument is a canonicalising call or
a variable bound from one finds FIVE in `mesh_layers_ctrl` alone, and they are not one thing.
THREE cannot use the verb, because they need the canonical path precisely WHEN the file is absent:
it goes into the refusal message `Resampled file does not exist at '<path>'` (`:33`), onto the
`(not exported)` label beside the membership test and the item data (`:118`), and onto the
`external file` / `missing file` label BY BASENAME (`:155`). `""` is the one answer that destroys
what those three need. ONE is a real unconverted reader of the "use it only if it is there" kind
and should delegate — `:403` canonicalises, tests existence and adds. One is a near-shape rather
than this shape (`:207` re-tests a path taken from the widget's item data, already canonical, with
no canonicalising call feeding it), and `geom_files_not_on_disk` asks the whole-list inverse
through `keyed_geom_paths`. So the rule is "the side that OPENS a file has a seam", not "every
filesystem call about an entry goes through one verb": a shape ban with no exemption red-lights
four correct call sites to find one real one, and the exemption cannot be a list of FILES — it has
to be the question the site is asking, since three of `mesh_layers_ctrl`'s five are correct and
one is not. The
verb is also the THIRD identity verb that deliberately does not read `keyed_geom_paths` — it asks
about one entry, like `remove_geom_file` — so the helper's own census of its readers names it,
which is the census #110 had just paid to make true.

**#112 made that exemption a property of the CODE rather than a list of files, and converted the
one real reader.** The gate's check 12 walks the same tree for two shapes, both of them exactly
what the converted readers used to be: a filesystem call whose argument is a canonicalising call
(or a local bound from one), and a filesystem call on a value taken straight from a `geom_files`
iteration. The second is the reader the rule file's blind spot named — `for gf in cfg.geom_files:
np.loadtxt(gf)` — which resolves a repo-relative entry against the process cwd and makes a preview
silently not draw.

The discriminator is what keeps the first shape from red-lighting the three correct sites: **an
existence call on a canonicalised entry is a violation only when that entry is used NOWHERE but the
branch where the file turned out to be there.** That is "use it only if it is there", which is
`readable_geom_path`'s question and nothing else's; the three correct sites all use the path where
the file is ABSENT, so they fall out by the question they ask rather than by their filename. Three
details make that hold on the real tree rather than on a fixture:

- **Uses inside the guard's own test do not count.** `canon and os.path.exists(canon)` is one
  question, not a use of the answer — and that is what makes `readable_geom_path`'s own body the
  banned shape, so its module's exemption is LOAD BEARING rather than decoration, the same bar
  check 7's derived allow-list is held to.
- **The guard-clause spelling counts as the indented one.** When `if not os.path.exists(q):` ends
  its branch with a `return`/`raise`/`continue`/`break`, the rest of the enclosing block IS the
  file-is-there branch. Without that, `q = canonical(p); if not exists(q): return; use(q)` would
  be invisible while the identical logic one indent deeper failed — and the reach-around would
  have a spelling.
- **The name analysis is FUNCTION-scoped, not file-scoped**, because a file-wide read over-reaches
  measurably here: `sync_mesh_layers_panel` binds `abs_out_file` from the canonicalising call, and
  `handle_mesh_layer_toggled` unpacks a same-named local from the widget's item data and re-tests
  it. A file-wide scan reports that second re-test as though the first fed it. It does not; the
  ticket's own write-up had already said an AST scan keyed on the canonicalising call would not
  fire there, so a scan that did would have contradicted the measurement it was built from. **That
  is also where the ticket's "four correct sites" becomes THREE**: the near-shape is one of the
  four only under the file-scoped walk that produced the figure, and the scan that shipped never
  reaches it. Both numbers are right about different scans, and the one in the gate is the gate's.

A call that READS (`open`, `np.loadtxt`, `os.stat`) needs no discrimination at all: it presupposes
the answer, so canonicalise-then-read is always the reach-around.

The one real reader was converted rather than pinned: `add_all_sessions_to_mesh` now asks
`readable_geom_path(session.project_model.output_file)`, which collapses its two missing cases —
no output file at all, and an export that is gone — into the one branch that already handled both
the same way, so `missing_exports` gets the same names it did before. #111 had correctly left it,
because it does not OPEN the file; it asks the same question about it, which is what makes it the
same verb's. With that landed, check 12 against the tree reports exactly ONE site, in
`geom_path_identity.py` itself, and nothing is pinned or exempted by name.

**Shape 2 has zero sites in this tree, and saying so is the point.** It is prophylactic — the
defect the blind spot predicted rather than one that is there — so the only thing standing behind
it is the injection: a module dropped into a tree the gate scans handing a raw `geom_files` entry
to `os.path.exists`, with the verdict read from the child's EXIT CODE and not from a FAIL-line
count, which reports a crash as zero failures. Both new doors sit beside the four already there,
each shown to move exactly one verdict, against a negative control on the untouched tree. Reaching
a raw entry by SUBSCRIPT (`open(cfg.geom_files[0])`) is covered alongside the loop and the
comprehension, because it is the same entry by another route and costs one branch.

What the check still cannot see is enumerated in the rule file's blind-spot list rather than
summarised, and two of the three entries there were found by REVIEW rather than by writing the
scan: the existence ANSWER bound to a name (`ok = os.path.exists(q); if ok: use(q)` is silent,
while the `if` and ternary spellings of the same guard fail — a spelling gap, not the "an AST
cannot follow a value" one), and a closure reading its enclosing function's binding, which falls
out of the function scoping above. One limit is DELIBERATE rather than residual: a site that uses
the canonical path where the file is absent is silent BY CONSTRUCTION, which is the same property
that keeps the three correct sites green. Each of those was verified against the shipped scan, not
reasoned about — the gap list is the part of a gate most likely to be written from intent.

**#119: "canonicalise" was ONE name in a module that had already exported a SECOND
canonicalising verb.** `keyed_geom_paths` went public in #110; check 12 shipped in #112 reading
`canonical_geom_path.__name__` and nothing else, so a reader that canonicalised through the newer
verb and then asked the filesystem passed — and the tree already held one, written correctly, in
the model's `geom_files_not_on_disk`. Both review axes found it independently, from opposite
directions, which is the same signal the three-entry gap list above is there to produce.

The fix is a MEASUREMENT, not a second name: call every verb in `geom_path_identity.__all__` with
one relative spelling whose canonical form is known, and keep the verbs whose answer CONTAINS it.
That answers on behaviour rather than on a naming convention, and it discriminates — `same_geom_file`
answers a bool, `dedupe_geom_paths` and `stored_geom_path` answer SPELLINGS, and the gate proves
each of those three is silent by scanning the same reader written through it. `readable_geom_path`
measures as canonicalising and is subtracted again off the same function object `_READ_OK` is
derived from: it is the sanctioned route TO the filesystem, and five of its seven callers open what
it hands back, so banning a read on its result would red-light every one of them. A third verb is
covered with no edit to the check, at the scan level AND at the build level, because the per-verb
probes and the injection doors are both generated from the derived set.

Two shapes follow from what those verbs ANSWER, and the same measurement settles both. They hand
back a SEQUENCE rather than a path, so the binding the code reaches them through is a
`for`/comprehension target rather than an assignment — and when the element is a PAIR its two
halves are not one question: `keyed_geom_paths` yields `(key, the spelling it came from)`, the key
an identity and the spelling a stored entry. So the probe records WHERE the canonical path sits as
well as which verbs produce one, and the scan binds by that position: the key is canonical, and
everything else in the target is the raw entry it is, failing on `os.path.exists(spelling)` exactly
as the same entry taken off the list directly does. Hard-coding "the key is first" would have put
the module's contract in the gate; the first cut of this change did neither, gave the spelling half
the key's discrimination, and review measured the asymmetry it produced.

And the guard is then a comprehension's `if` rather than a statement, whose file-is-there branch is
the element expression — or NOTHING when the test is negated, because then the element is produced
precisely where the file is absent. **A negated guard with an empty file-is-there branch is the one
thing this change subtracts from the check**, and it is the deliberate limit above rather than a
new exemption: it is the absent question and nothing else, which is what keeps
`geom_files_not_on_disk` green without a pin. Every other shape is judged exactly as it was before,
by whether the entry is used anywhere but the branch where the file turned out to be there — the
first cut required a use IN that branch instead, which silently stopped `q = canonical_geom_path(…);
if os.path.exists(q): return True` from failing. Both regressions were review findings on this
change's own first cut, and both are now injected: one probe per PAIR-answering verb (one today)
asserts the key half fails where the branch uses only the ANSWER and the spelling half fails as a
raw entry. Every fixture and every door is generated from the measured shape rather than written
key-first, so a verb answering `(spelling, key)` would be covered by them instead of turning them
red — which is what the "no edit for a third verb" claim has to mean.

**The probe was inside the package it was measuring.** The doors were written to
`gui/app/services/_geom_ident_inj_probe.py` and removed in a `finally` — which a SIGKILL never
reaches, so a cancelled or crashed run left a module in the live package for the next run to
measure. This repo has paid for that shape once already (a stale harness backup silently reverting
a fix that had landed, #113), and the lesson recorded then was to leave nothing rather than to
sweep afterwards. The doors now go into a temporary directory put on `sys.path` and added to the
gate's scan roots, so they are still opened in a tree the real scans walk, with the same per-file
AST check; a child run is handed the parent's sandbox through the environment, so the probe lands
in a directory the surviving parent owns. Check 7c demonstrates it rather than asserting it:
snapshot `gui/app`, start the gate again with a pause that stops it with a probe written and
nothing removed, SIGKILL the process group, and compare — with two checks first that the killed run
really had a probe on disk and that the probe was outside the package, so the third cannot pass for
the wrong reason. **The killed child still makes a temp directory of its own**, and its `rmtree`
is in the same `finally` a SIGKILL never reaches: that leaked one ~48K directory per gate run until
review measured 17 of them. The criterion is about the package tree and held either way, but
"leave nothing rather than sweep afterwards" has to be true of the whole run — so the child prints
that directory beside the probe path and the KILLER removes it, checked both ways (still there
before, gone after). What the doors used to prove as a side effect — that the package is the tree
these scans read — is asserted directly now, against the one walk both roots go through.

**THE MESH SUMMARY HAD TWO IMPLEMENTATIONS, AND THEY DID NOT MEASURE THE SAME THING (#131,
parent #128).** The rule is `.claude/rules/gui-handoff.md`'s, and the reader it turns on is
`services/mesh_shape_stats.py` (Qt-free: the sidecar read is the half a headless test can
exercise, so the panel is left with formatting only). The panel
(`views/panels/mesh_stats_panel.py`) computed its own per-cell aspect ratio from the loaded
`VTKMesh` and showed min / max / mean; the mesher, since #129 and #130, measures cell shape itself
and publishes median / p95 / max on three surfaces — the run banner, a `HYBMESH_*` machine line and
the `mesh.quality` object of the `.provenance.json` sidecar. Two producers describing one file is
the defect; that the two used different DEFINITIONS is what made it unfixable by agreeing on a
format. Measured 2026-09-17, `./run.sh -conf config/multiblock_ogrid.dat` at the shipped defaults
(`8eb5451`): the sidecar says `quad_midline_ratio`, median 1.846, p95 23.662, max 32.768 over
**4608 structured quads**, while the file on disk holds **9216 triangles** and nothing in the GUI
can see a structured quad at all. Those five figures are a DATED reading of one run, not a gated
one — `test_instruction_budget.py` blind spot (g) is the entry that says why a figure of this kind
stays out of `--sync`, and the gate re-derives the live ones from the binary instead. The panel's own number for that mesh was
not a worse estimate of the mesher's; it was an answer to a different question. `#128`'s own
headline is the other half — min / max / mean has no percentile, so one boundary-layer cell hides
the shape of the other 99%.

**The blank is the feature, and it is an accepted regression stated as one.** A mesh with no
sidecar — produced before this work, or by another tool — shows `—` for all four rows. A fallback
computation was refused in the ticket and again here: it is the second implementation coming back,
and it would be the MORE dangerous version of it, because a fallback is invisible at the point of
reading. The gate holds that against a NEGATIVE CONTROL rather than by assertion — the blank case
is a mesh whose client-side per-cell array is non-empty (2 cells, max 1.414), so a fallback would
have had numbers to show and the check would go green on them.

**`metric` travels with the figures, and that is why the panel has a fourth row.** `1.85` means
nothing without knowing it is a quad midline ratio over structured cells rather than a triangle
edge ratio over exported ones, and #128's user story 6 asks for exactly this. The row shows the
metric KEY as the sidecar spells it, not a prettified label: the banner, the machine line and the
sidecar all spell it the same way, and a fourth spelling in the GUI would be the one a user cannot
grep for. The gloss lives in the tooltip (`METRIC_MEANING`), where a wrong one costs nothing.

**Three states, not two.** `None` from `read_shape_summary` is "no sidecar" and blanks the rows; a
sidecar carrying `cells: 0` with negative figures is "the tool looked and could not measure", and
says `not measured`. Collapsing them would lose the distinction the mesher deliberately writes into
the file — negative and never 0.0, because the metric's floor is 1.0 and a 0.0 would read as a
perfect mesh (`include/Provenance.hpp`, and the same rule `MbQualityReport` follows).

**The read is synchronous while skewness is still threaded, and the asymmetry is the point.** The
sidecar is one small JSON file, read once per `update_stats`, so the `STATS_ASYNC_CELL_LIMIT`
machinery buys nothing for it — and unlike the skewness array it does not depend on the loaded
cells at all, it depends on the FILE. `workers/mesh_stats_run.py` stopped computing aspect ratio at
the same time: nothing displayed it any more, and the canvas colour map
(`views/mesh_canvas_fills_mixin.py`) builds its own array where it draws.

**Injections, run by hand 2026-09-17 against `tests/test_mesh_shape_panel.py`** (the harness lives
in a scratchpad, not in the tree, and each mutation was scored by EXIT CODE first — a crash reports
zero FAIL lines and would otherwise read as inert). Eleven, all of which bit, none inert; the list
and its dating live in that file's own docstring, and are not counted twice here. **The four added
last are the interesting ones**, because they exist because of a review round rather than because
of the implementation: two checks were found weaker than their own labels (see the blind spots
below), and the mutations that would have walked through them are now what proves they do not.
One of the original eight, "drop the shape labels from the panel's clear list", stopped COMPILING
when the tooltip fix landed — the clear routes through one verb now — so it is recorded in its
current shape rather than in the one that found the defect.

**Named blind spots.**
- **The sidecar is trusted because it is BESIDE the file, and nothing checks that it describes
  it.** Overwrite a `.vtk` with another mesh and the old run's sidecar still reads, so the panel
  quotes figures for a mesh that is gone. A staleness check is buildable and was left out of #131
  as scope rather than as impossible: measured on both shipped cases, the sidecar's `mesh.elements`
  equals the loaded mesh's total cell count exactly (naca 11400 = 11396 triangles + 4 two-node
  entries the parser bins as polygons; O-grid 9216 = 9216 triangles), so a future ticket has its
  premise already measured. What it does NOT have is evidence that the equality holds for every
  export this tool can write, which is what a guard would need before it may call a mesh stale.
- **Only a path ending in a mesh the GUI loaded reaches this at all.** `update_stats` is called
  with `global_vtk_path` or the expected VTK path; a case wired to a STAR-CD triplet with no `.vtk`
  hands it `""` and blanks — correctly, but for the trivial reason rather than the measured one.
- **The gate's colour-map leg proves the fills are still the SAME, not that they are RIGHT.** It
  compares brush colours with and without a sidecar over a fixture holding one cell in each of the
  four quality buckets, so a mutation that recoloured every cell identically wrong in both cases
  would still pass. The per-cell arithmetic has never had a gate here and #131 did not add one — it
  is the rendering input the ticket explicitly leaves alone. **Its first form was weaker than that
  and its label said more than it checked**: two `len(filled_items)` counts over the SAME
  two-triangle fixture, so the equality it called "identically" was `1 == 1` on one bucket. A
  review axis found it; the fixture and the comparison both changed, which is the second time in
  this ticket that a check's words outran its assert (the other is the next bullet).
- **Check 7 was scoped to `views/panels/`, under a criterion about the whole GUI.** A fallback
  computation added in a controller, a service or a canvas mixin would have passed it — the label
  was honest ("no panel module") and narrower than the thing it was placed under. It is now an
  allow-list over the whole package: `get_element_aspect_ratios` has exactly two homes, the model
  that defines it and the colour map that consumes it, and a third fails wherever it is written.

**THE RUN NOBODY WATCHES HAD NO QUALITY SIGNAL AT ALL (#132, parent #128).** #131 made the GUI
panel a reader; this made the two HEADLESS hosts readers as well —
`services/pipeline_runner.py`'s mesh stage logs the figures when it finishes, and the batch
queue's table carries them per case. The rules are `.claude/rules/gui-handoff.md`'s (the reader
and the report string) and `.claude/rules/pipeline-case.md`'s (the stage that logs it). Before
this, someone running `./run_batch.sh` over forty cases could find out how good the meshes were
in exactly one way: open each one in the GUI afterwards. That is the gap #128 opens with, and it
is why the parent ticket exists at all.

**ONE STRING, TWO HOSTS — and the formatter is shared for the same reason the reader is.** Sharing
`read_shape_summary` alone would have left each host free to round differently, drop the metric
name, or render an unmeasured run as numbers, so `format_shape_report` is where the report's shape
is decided and `shape_report` is the one call both hosts make. The batch dialog does not even call
it: `batch_runner` reads once, off the GUI thread and Qt-free, and stores the string on the job, so
the view reformats nothing. The gate compares the queue's row against the runner's own log line for
the SAME case in the SAME run — string equality, not two numbers that agree today.

**A CASE WITH NO MESH CARRIES NO FIGURES, WHICH IS A THIRD THING AGAIN.** The reader already had
two absences — `None` for no sidecar, and `cells: 0` with negative figures for "looked and could
not measure". A batch adds a third that is not the reader's at all: a case that failed before its
mesh stage, or has not run yet. Asking for a sidecar beside nothing would come back `not
published`, which is a statement ABOUT A MESH, so `batch_runner._shape_of` returns `""` when there
is no `vtk` artifact and the row shows a dash whose tooltip points at the Status column.
`batch_ctrl` clears it on a re-run for the same reason — the previous run's numbers standing beside
a FAILED status is the same lie by another route.

**Measured 2026-09-17 on the two scripts the ticket names as its demo** (`8eb5451` plus this
work), `./run_pipeline.sh <script> --no-solver`: `naca_demo.json` reports
`tri_edge_ratio: median 1.585, p95 9.901, max 35.608 (11396 cells)` and
`multiblock_cgrid_demo.json` reports
`quad_midline_ratio: median 4.832, p95 148.006, max 3147.958 (5760 cells)`. Dated, not gated —
`test_instruction_budget.py` blind spot (g) is the entry that says why. **No cause is offered here
for the C-grid's 3147** — which block or which cell it is has not been localised, and #93's lesson
is that a plausible localisation written down as a cause outlives the measurement it never had.
What #128 already settles is that a figure of that size is not by itself a defect: it rules out a
threshold and a colour precisely so one does not train anyone to ignore the column.

**The runner reports BELOW its own guards, and that ordering is gated rather than argued.**
`_run_mesh` already refused a non-zero exit and a missing VTK; the report sits after both, so there
is no path on which it describes a mesh that was never written. The gate checks the two source
positions rather than trusting the reading, because "it is obviously after it" is exactly the claim
a later refactor invalidates silently.

**Injections, run by hand 2026-09-17 against `tests/test_headless_shape_report.py`** (the harness
lived in a scratchpad and is not in the tree; each was scored by EXIT CODE first). Eight, all of
which bit; the list and its dating live in that file's own docstring and are not counted twice
here. **Two of them corrected the claims written for them before they ran**, which is the reason
for running them at all: returning `""` for a missing sidecar was predicted to leave the batch
dialog's dash check unreached and in fact left it GREEN — the dash is fed by `_shape_of`'s own
empty string, so the blank has to be refused where the report is made and not only where it is
shown; and a view that reformats the report was predicted to redden the row-equals-log check and
did not, because that check compares the job's string against the log line and never reads the
table. A third bit somewhere unplanned: the runner reading the sidecar itself also reddened the
ORDERING check, whose anchor is the report's exact spelling, so that check now says when an anchor
has gone missing instead of reporting a rewording as an ordering defect. The eighth was added
after review, for the panel-versus-report check the review asked for, and is NOT the isolated
probe of it that it was meant to be — formatting at `.2f` reddens four checks across three
sections, because two of them rebuild the expected string from the sidecar and carry the precision
with it. Recorded as it ran. **Two harness hazards cost real work in this round and are worth more
than the injections**: restoring by `git checkout` reverted UNCOMMITTED edits in the same files, in
the middle of acting on a review (the rule since #131 is commit first, and it was not followed);
and a same-SIZE, same-second restore of `mesh_shape_stats.py` was ignored by this platform's
bytecode cache, so the file on disk was correct while the gate went on failing until it was
`touch`ed — the trap this repo has recorded before and hit again.

**Named blind spots.**
- **The batch column inherits #131's staleness hole and widens the window.** The sidecar is trusted
  because it sits beside the file; a case whose output name collides with another's would show the
  LAST writer's figures against both rows. Collisions are already warned about before the run, by
  source file, which is the mitigation that exists — not a check that these figures describe this
  mesh.
- **The panel and the report are two renderings of one `ShapeSummary`, and they are pinned rather
  than merged.** A four-row layout and a one-line string are different renderings, so
  `format_shape_report` does not serve the panel; what a review found was that nothing then held
  them together — the `.3f`, the metric name and the `not measured` wording were each written
  twice. Check 7 of `tests/test_headless_shape_report.py` now asserts the panel's three figures
  appear verbatim in the report, under the same metric name, with the same unmeasured wording, so
  changing one side has to be a deliberate change to both. What it still does NOT hold is the
  LAYOUT: the panel's cell-count parenthesis and the report's are written separately and may
  diverge in position without the check speaking.
- **A case that meshed and then FAILED at a later stage shows the dash, not its mesh's
  figures.** `run_batch` reads `job.artifacts`, and `run_pipeline` builds that dict locally and
  raises without returning it, so a solver failure loses the `vtk` key the mesh stage had already
  filled — the mesh is on disk with its sidecar beside it and the row says nothing about it. The
  figures ARE still in the log, from the mesh stage's own line, so the batch is not blind; only the
  column is. Fixing it means carrying partial artifacts out of `run_pipeline`, which changes a
  return shape two hosts read, and #132 does not ask for it. Recorded rather than left for
  rediscovery.

- **`run_batch.py`'s end-of-batch summary does not carry the figures**, only the per-case `[Mesh]`
  lines interleaved in the log — which is precisely the "forty interleaved logs" problem the
  summary exists to solve, solved for status and not for quality. Left out as scope: the summary
  dict is a published shape that three callers read, and #132 asks for the GUI queue.

**THE SPLIT ARRIVED WITHOUT EITHER HEADLESS HOST CHANGING, WHICH IS WHAT #128's SEAM BOUGHT (#145,
parent #128).** #143 and #144 made the two generation paths publish `layer` and `bulk` beside the
whole-mesh set; this is the reader half, and the measure of the seam #131/#132 left behind is how
little it needed. `services/pipeline_runner.py` and `services/batch_runner.py` are UNTOUCHED by
this ticket — one `shape_report` call each, as before — and the split reaches both of them inside
the string they already print. `views/batch_dialog.py` gained five lines of TOOLTIP prose and nothing else:
it displays what the job carries, and what changed is one module, one panel and one hover text.
It is stated that precisely because the first draft of this paragraph said "untouched" while the
same commit edited the file — a false claim inside the record that argues for the work, which is
this repo's named recurring failure. The rule is `.claude/rules/gui-handoff.md`'s.

**One rendering of a HALF, and this time it IS shared with the panel.** #132's blind spot recorded
that the panel and the report are two renderings pinned rather than merged, because a four-row
layout and a one-line string are different shapes. That argument does not reach a HALF: both
surfaces show one half as one string, so `format_figures` renders it and both call it — the panel's
two rows are its output verbatim, the report's two clauses are the same call. The pin (check 7)
still holds the whole-mesh set; check 9 holds the halves harder, by asserting the panel makes
exactly two `format_figures` calls. Measured 2026-09-21 on the shipped cases: the hybrid NACA case
reports `tri_edge_ratio: median 1.158, p95 52.186, max 78.703 (15233 cells); layer median 35.282,
p95 70.542, max 78.703 (3215 cells); bulk median 1.112, p95 1.412, max 11.902 (12018 cells)`, and
the O-grid `quad_midline_ratio: median 1.846, p95 23.662, max 32.768 (4608 cells); layer median
5.184, p95 28.508, max 32.768 (2304 cells); bulk median 1.693, p95 1.878, max 1.882 (2304 cells)`.
Dated, not gated — `test_instruction_budget.py` blind spot (g) says why; the gates re-derive the
live figures from the binary instead. **The whole-mesh p95 is the boundary layer's on both**, which
is #143's and #144's whole argument, now visible on every surface rather than in the banner alone.

**A FOURTH state, and the old sidecar is the acceptance.** The reader had three — `None` (no
sidecar), `cells: 0` with negative figures (looked and could not measure), and `""` from
`batch_runner._shape_of` (no mesh at all). `not split` is the fourth and belongs to a HALF, not to
a summary: the sidecar carries no `layer`/`bulk` keys because the run that wrote it predates the
producers. It must not collapse into any of the other three — a dash reads as "no figures", `not
measured` reads as "this mesh has no boundary layer", and a number is a lie. The state #128 bought
is that such a sidecar still shows everything it always did, so the gate holds the headless line
as a STRING EQUALITY against the exact line it produced before #145, not as a substring.

**Both halves or neither, and the split is never inferred from a zero.** The writer emits the pair
under one flag, so the reader collapses half a split to none: one band with nothing to compare it
against is worse than no split, and it is a sidecar this tool did not write. The opposite mistake
is the more tempting one — reading `layer.cells == 0` as "no split" would be wrong on the ordinary
case #143 names, a geometry meshed with no boundary layer, whose layer really is empty and whose
bulk is the whole mesh. Present-and-empty says `not measured`; absent says `not split`.

**Injections, run by hand 2026-09-21** (five against `tests/test_mesh_shape_panel.py`, four against
`tests/test_headless_shape_report.py`; the harness lived in a scratchpad and is not in the tree).
All nine bit; the lists and their dating live in those files' own docstrings and are not counted
twice here. **One of them found a defect in a check rather than in the code, and it is the one
worth keeping**: dropping the split clause entirely — the mutation that removes the whole feature —
printed ONE FAIL line, because the ordering check used `str.index`, which RAISES on a line with no
split. The gate crashed and ten FAIL lines never printed. Scoring by exit code, this repo's own
rule for exactly this hazard, does not separate the two here: an unhandled exception and a failed
assertion both exit 1. What separated them was that the count was implausible for a mutation that
size. The check now uses `find` and asserts both positions are real, and the harness prints stderr
on every run rather than only on an unexpected exit code.

**Five review findings, and the two that were defects in the RECORD rather than in the code.**
The Spec axis found a fixture mixing two meshes: the `SPLIT` sidecar carried the shipped
naca0012's whole-mesh count (11396) with halves taken from a different run of a different case
(3215 + 12018 = 15233), so the two halves overran the whole mesh by 34% while the comment called
them "the shipped NACA case's own shape". Nothing caught it, and nothing could: the blind spot
below says in as many words that the reader never checks the halves partition anything, and the
fixture was the first thing to demonstrate it. **It had a SECOND home the review did not reach** —
`test_headless_shape_report.py`'s `split_q`, the same numbers with the same mismatch — which is the
pattern this repo keeps paying for: a figure found in one place is found in one of its homes. Both
now carry counts that sum to their own whole, with the shipped case's MAGNITUDES kept, and the
comment says which half of the fixture is real. The Standards axis found the #145 section inserted
INSIDE #132's blind-spot list, orphaning #132's last bullet under #145's heading, and this
paragraph's own neighbour claiming `views/batch_dialog.py` was untouched while the commit edited
it. Both fixed above; neither was visible from the diff of the code.

**Two gate additions the review bought, and one thing kept as written.** #145's first criterion has
two halves — "no host parses the sidecar itself and no host computes a figure of its own" — and
only the second was gated; `test_headless_shape_report.py` check 10 now holds the first over the
whole GUI package. Its scope was chosen by MEASUREMENT, not by banning what looks alike: a bare
`["quality"]` subscript is also how `services/geometry_stats.py` keys its own unrelated dict,
twice, so the check bans the `["mesh"]["quality"]` CHAIN and any read of `layer` or `bulk` by
name, and proves itself non-vacuous against the shape it bans. Check 7 gained a pin on the state
where the two surfaces genuinely differ: both producers set the split flag unconditionally, so an
unmeasured run publishes two EMPTY halves, and there the line drops the clause while the panel
keeps two `not measured` rows. Neither invents a zero, so the difference is layout and not
disagreement — pinned rather than resolved, so that changing either becomes deliberate. **Kept as
written**: `LAYER_MEANING`, which the Spec axis correctly named as the only net-new concept in the
diff and one no criterion asks for. A row labelled `Layer` on a tool whose two banners call that
band two different words is a row a user cannot connect to the output they just read; the gloss is
a tooltip, is shown only when the sidecar HAS a split, and the sidecar's own key stays neutral.

**Named blind spots.**
- **The split is trusted exactly as far as the sidecar is**, so it inherits #131's staleness hole
  whole: nothing checks that the file beside the mesh describes the mesh. A stale sidecar now
  misreports three sets instead of one.
- **Nothing here checks that `layer` and `bulk` PARTITION the mesh.** The reader does not compare
  `layer.cells + bulk.cells` against `cells`, and on the hybrid path they do not have to be equal —
  the whole-mesh set counts exported triangles while the two halves are what each producer chose to
  offer the metric. A producer that double-counted, or dropped a band, would display as
  cheerfully as a correct one. Asserting the sum belongs to the PRODUCERS' gates (#143, #144),
  where what the counts mean is known; asserting it here would encode a relationship this module
  cannot know is true.
- **A half that is present and MALFORMED loses the whole summary, not just the split.**
  `_half_from_json` tolerates absence and nothing else, so a corrupt `layer.median` raises into
  `read_shape_summary`'s handler and the mesh reads as having no sidecar at all. Deliberate — a
  corrupt sidecar is one state — and no producer writes it, but it is the one input on which the
  old-sidecar guarantee does NOT hold.
- **The panel's two rows are one line each, which is a layout choice this ticket made and no gate
  holds.** Six rows (three figures per half) would have been the symmetric shape; the comparison a
  reader actually makes is layer-against-bulk across all three at once, and six more rows push the
  whole-mesh set off the top of the section. Nothing here would notice the choice being reversed
  except the exact-text checks, which would simply be rewritten with it.
#### THE TOPOLOGY TEMPLATE LIBRARY (#134, parent #133)

Three modules, named here because the rule file's pointer resolves to this note for each of them:
`services/topology_model.py` (the model, the family registry, the projection to JSON),
`services/topology_hgrid.py` (the H-grid family as a pure function, and the ONE owner of the count
derivation), and `services/topology_field_specs.py` (one row per parameter, no `.dat` key). The
panel half lives in `views/panels/mesh_config_build_mixin.py` and
`views/panels/mesh_config_config_mixin.py`; the projection hooks into
`models/mesh_config_io.py`.


**The problem it was built for, measured rather than asserted.** To mesh anything with
`MESH_MODE 1` a user had to hand-write a JSON block topology document. All five shipped topology
documents were typed by hand; the only parametric writer in the tree lived inside a test file and
wrote a single rectangular block for the golden comparator. Writing one by hand means knowing —
before a single node exists — the `[south, east, north, west]` edge order, that the corner ring
must close counter-clockwise, that a `count` is a SEED that propagates across opposite sides and
through shared edges, that an interior line is declared once and named by both blocks, that ids
are unique across three namespaces, and that an unknown key is refused rather than ignored. The
GUI offered a single file-path field. The multi-block path was therefore effectively unavailable
to anyone who had not read `.claude/rules/mesher-multiblock.md`.

**Why a family is a FUNCTION and not a data-driven template file.** Seeding exactly one count per
equivalence class, closing the ring counter-clockwise and deciding which lines are interior are
logic, not fill-in-the-blanks. A data format expressing them needs an interpreter, and the
interpreter is the module anyway — so the "data" would be a second language with one implementation
and no users. Users extend the library by adding a function and a registry row; the bidirectional
parameter gate then requires a field-spec row for every parameter that function reads.

**BY CONSTRUCTION, not by a check afterwards.** Every structural rule the mesher refuses a document
for is made unreachable by how the document is built rather than validated once it exists: the four
sides of every block come from ONE index expression, so they cannot disagree; the id families carry
different prefixes; the `nx + ny` count classes are seeded on the bottom row and the left column,
which is one seed per class and never two. The alternative — build freely, then validate — leaves
the user a refusal, which is the thing the template exists to spare them.

**The count classes, derived.** Opposite sides of a block carry equal counts and a shared edge is
one edge named by two blocks, so on an `nx x ny` H-grid the horizontal edges of column `i` are ONE
class and the vertical edges of row `j` are another: `nx + ny` classes for `nx*ny` blocks. The
shipped hand-written `examples/topology/hgrid_blocks.json` is a 2x2 and seeds exactly four counts
(`h00`, `h10`, `v00`, `v01`), which is the same partition reached independently.

**"Is the bottom a wall" is a SPACING, and the tree decided that, not taste.** A boundary edge MUST
be `kind: "wall"` — the mesher requires a wall to bound exactly one block side and an
interface/cut exactly two — so the toggle cannot be a choice of kind; there is nothing for it to
choose. What it chooses is whether the bottom row's vertical edges cluster toward `y_min`, which is
what a flat plate or a duct floor wants: `spacing: {"wall_ends": "start"}`, "start" naming the
bottom because those edges are declared upward. It declares NO `ds_start`, so the first cell height
is the run's `BL_INITIAL_THICKNESS` — #133's decision that a template uses the existing
boundary-layer parameter names rather than an alias, the physical quantity being identical.
**Spacing does not propagate, only counts do** (the shipped document says so in its own header),
which is why the clustering is written onto EVERY vertical edge of the bottom row rather than onto
the seeded one and left to spread.

**Measured on the defaults, 2026-09-22.** `TopologyModel()` — a 2x2 grid over x 0..2, y 0..1 at a
0.1 target cell, floor clustered — runs the real binary to exit 0 with **0 of 400 cells inverted**.
Its bulk measures **exactly 1.000** on the quad midline ratio (the 0.1 target divides both spans
evenly: 11 nodes per column, 6 per row) and its wall band **50.000**, which is arithmetic rather
than a defect: 0.1 azimuthal over the 0.002 `BL_INITIAL_THICKNESS` asked for. The figures come from
the sidecar the mesher already writes and the one reader #131 built — **this work adds no quality
code at all**, which `test_topology_templates.py` check 15 holds by asking that reader rather than
by parsing the run again.

**Where the projection hooks, and what it cost.** `models/mesh_config_io.py::save_config_to_file`
is the ONE call both hosts converge on immediately before launching the mesher
(`controllers/mesh_gen_ctrl.py:191` writes a temp config, `services/pipeline_runner.py:234` writes
the case's). Hooking there makes "the file `MESH_TOPOLOGY_FILE` names exists" structurally true
rather than something two call sites must remember — the alternative, an explicit prepare step each
host calls, is the shape this repo was already bitten by when four pipeline stages implemented
twice let an artefact be produced for nobody. The cost is stated at the function: it is no longer a
pure text transformation. `config_to_text` STAYS pure and takes the projected path as an OVERRIDE
argument, because its other two callers (the solver case staging its runnable parameters, and the
source listing) want content and are not about to run anything — a projection fired from there
would write a document for nobody. The override is also why `cfg` is not mutated: a text builder
that edited the model it describes would leave the projected path on a model the user is still
editing, and the next Save would write it out as if the user had typed it.

**THE FINDING THAT ONLY THE EXISTING GATES COULD HAVE MADE.** `get_config` first read the template
parameters into the fresh config's default model IN PLACE (`read_specs(self, TOPOLOGY_SPECS,
cfg.topology)`). Every check in `test_topology_panel.py` passed — because they all talk to the
panel directly. What they could not see is that `config_ownership` derives what the panel->model
sync may overwrite from what the panel's sources are seen to ASSIGN, and an in-place mutation is
not an assignment: `topology` landed in `PRESERVED_FIELDS`, which is the set
`sync_panel_to_model` refuses to overwrite. Every template edit the user made would have been
silently dropped on its way to the global config. `test_field_spec_tables.py` check 2 found it as
"written-but-undeclared". The fix is to build the model and ASSIGN it, and check 9 of the panel
gate now pins `topology` OUT of `PRESERVED_FIELDS` so the property is held rather than remembered.

**Two more the existing gates caught, both correct.** `test_units.py` check 6: the domain range and
the target cell size are PHYSICAL LENGTHS and must carry the model's unit suffix, so `LENGTH_FIELDS`
had to include the third table — a mm-scale template left labelled in metres is the same defect a mm
mesh left at `Linf` 1 is, one panel section further in. And check 14d: eleven mode-restricted rows
with no `.dat` key needed their reasons written down, which is what keeps "no key" from meaning
"unchecked". Check 8's own injection then asserted LOUDLY that its anchor no longer matched the
shipped `LENGTH_FIELDS` line, rather than passing as a no-op — the failure mode #101 is about.

**A silent degradation caught by its own round-trip, not by a gate.** `TopologyModel`'s converter
map was first derived with `f.type is int`. `from __future__ import annotations` is in force in
that module, so `dataclasses.fields()` reports `f.type` as the STRING `"int"` and every field fell
through to `str`: `hgrid_nx` restored as `'7'` and the round-trip looked like it worked. The map now
matches on the annotation TEXT and RAISES at import on an annotation it does not know, rather than
defaulting to anything — the same rule the schema derivation in `test_topology_templates.py` check
6a follows, and the same failure family as every "derivation that answers on bad input" in this
tree.

**Injections: FOURTEEN recorded across the three gate files, 2026-09-22 — thirteen run deliberately
by hand and one that fired on its own.** Counted from the files rather than remembered: six in
`test_topology_templates.py`, three in `test_topology_param_specs.py`, five in
`test_topology_panel.py`. FIVE corrected the prediction written beside them, and the corrections are
kept rather than tidied away:

- a spread that had grown to EIGHT parameter sets was written up as "six" — remembered, not counted,
  which is this batch's own instance of the mistake this paragraph is now correcting;
- seeding every horizontal edge bites even a 1x1. The prediction reasoned about interior lines; the
  count class is about OPPOSITE SIDES, which every block has, so there was no case where it stayed
  green;
- swapping east/west is refused by the REAL BINARY too (exit 8), not only by the ring walk, so
  three more checks went red than the note expected;
- removing the derived-count read-out reddens SIX checks, not three: every claim the panel gate
  makes about the read-out rests on the read-out existing;
- an inline copy of the count derivation in the panel silently drops the OVERRIDE, because
  overriding is part of the derivation and not a step after it — and the check comparing the
  displayed number against the family's stayed GREEN throughout, which is why a source scan sits
  beside it.

And the `ast` walk in the parameter gate cannot see a read of a NON-model attribute, so a typo'd
read shows up only as an unread ROW — kept as a named blind spot rather than as a fix. The
FOURTEENTH fired UNPLANNED: the first draft of the schema check selected each key set by the
`where` argument of its `rejectUnknownKeys` call, which is a runtime-built variable at four of the
five call sites, so it reported `None` and the check beside it passed VACUOUSLY.

**Named blind spot, CLOSED by #135 and kept as the record.** The solver case staging its runnable
mesh parameters into `grid/cad/` and the pipeline source listing called `config_to_text` directly,
so they read `cfg.mesh_topology_file` — empty for a template case, because that path only exists
once `save_config_to_file` has projected one. A staged config for a template case carried no
`MESH_TOPOLOGY_FILE` line. It was named rather than half-fixed because doing it right means staging
the DOCUMENT, which is the portable-reproduction work #135 owns; the alternative considered and
rejected was having `config_to_text` fall back to projecting into a temp directory, which trades a
missing line for a file nobody deletes. What #135 actually did is neither: a third caller,
`case_sources.mesh_config_generated`, produces the parameter file and the document TOGETHER as the
two `(name, text)` pairs the staging service already writes, so `config_to_text` stayed pure and
still fires no projection. The rationale is in `docs/design_notes/pipeline.md`, beside the rest of
what a case carries.

#### THE TOPOLOGY MODEL SURVIVES THE SESSION (#135, parent #133)

**Most of this ticket was already true, and saying so is the honest report.** #134 carried
`MeshConfig.topology` through `to_dict`/`load_from_dict` by name and hooked the projection into the
one call both hosts make, so save -> reload -> project already reproduced a byte-identical document
and the two hosts already agreed. The four acceptance criteria about round-tripping passed on the
first run of the gate written for them. What was NOT true is everything that only appears once the
section is allowed to be ABSENT, which is the criterion the ticket leads with.

**Optional, and its inverse, are ONE decision.** `to_dict` now omits `topology` unless
`TopologyModel.is_configured()`, following the `stl3d` precedent in `pipeline_config`. That single
line silently breaks undo unless the other direction moves with it: the project-undo snapshot IS
`to_dict()`, so the snapshot taken *before* the first template edit carries no section at all, and
a `load_from_dict` that treats an absent section as a no-op would restore that snapshot and leave
the edit in place. Every other field on this model is restored by being PRESENT; this one has to be
restored by being ABSENT. The rule is therefore stated as one sentence — *absent means the default
model* — and `load_from_dict` rebinds a fresh `TopologyModel` before reading the key. **Measured,
not reasoned**: under the injection that reverts `load_from_dict` to its #134 form,
`test_undo_redo.py` and `test_topology_panel.py` both stay GREEN. Nothing else in the tree stands
between the user and a first template edit that Ctrl+Z cannot walk back.

**`is_configured()` asks about every parameter, never about `family`.** A user who types a domain
range and a block count and only then opens the family combo has configured something, and a writer
that asked `bool(self.family)` would drop every number they typed. It compares against a freshly
built model rather than against a remembered snapshot of the defaults, so a new parameter is covered
with no edit. Injection E is that mistake, and it reddens the check written for it.

**A round-trip claim is measured on a FILE, and both hosts are DRIVEN.** The gate saves a real
project file, reopens it through a real `AppController`, reads the same file through the pipeline
bridge, and compares the two documents byte for byte — then runs both configs through the real
mesher and compares the meshes node for node. Two reasons, both measured rather than argued. A dict
round-trip cannot see a parameter the writer never emitted. And a two-host comparison agrees with
itself about a parameter BOTH hosts lost: injection H, which drops one field from
`TopologyModel.load_from_dict`, reddens checks 5, 5b, 7, 8b and 13 while check 8 — the two hosts
against each other — stays green throughout. That is why check 5 compares BEFORE against AFTER and
why check 13 is deliberately asymmetric, the live model's mesh against the round-tripped one.

**The legacy case is a SHIPPED file, and its being legacy is checked first.**
`config/pipeline/multiblock_cgrid_demo.json` is the strong version of "a project file written
before this feature": `MESH_MODE 1` with a hand-written topology path and no template anywhere. The
gate asserts it really has no `topology` section before using it as evidence, because a legacy check
against a file that quietly grew one proves nothing.

**Two injections changed the gate rather than the code, and both are kept.** One removed the
document from the staged pair and CRASHED the file at an unguarded index instead of printing four
red lines — the failure mode this repo has already recorded, where a reader scoring by FAIL count
reads a total removal as no bite at all. The other named the staged document by its ABSOLUTE
projection path and was INERT: the check compared the parameter file's line against the staged NAME,
and both came from the same variable, so it agreed with itself about a name that is not a filename.
It asserts the name has no directory part now, which is a real defect — `stage_case_sources` writes
a generated entry with `os.path.join(dest_dir, name)`, and an absolute name lands outside the case
folder entirely.

**What the review found, and it was not in the round-trip.** Both axes passed the persistence half
outright; all four surviving findings were in the case STAGING, which is the part of this ticket no
acceptance criterion asked for. The sharpest was a defect the cross-reference itself created: the
staged parameter file names the document beside it, `grid/cad/` is never cleared
(`solver_case.prepare_case_dir` has no `rmtree`), and the staging renames a colliding entry — so a
second run of the same case wrote `Background_para_<case>_2.dat` quoting the FIRST run's document.
A case folder stating in writing that a grid was cut from a topology it was not, which is precisely
the confident wrong record `grid/cad/` exists to prevent, and it was reachable from the ordinary
"tweak a parameter, Send to Solver again" flow rather than theoretically. It was reproduced before
it was fixed. The fix narrows `_unique_name` for GENERATED entries only: they step aside from a name
this run has taken, never from a file a previous run left, because a generated file is a
reconstruction of the configuration as it stands now and last run's is stale — the rule
`_write_index` already follows by rewriting itself in full.

Three more, all taken: two docstring sentences in `mesh_config_io` that the change made FALSE (the
"ONLY `save_config_to_file` passes it" and "its other two callers" lines — this repo's own recorded
"a reader list goes stale" failure); the "does a template drive this config?" predicate spelled
twice and INVERTED at the two sites, now `TopologyModel.names_a_family()` with a source-scan gate,
because two spellings that agree today are how a projection and a staging drift apart; and the
self-declared regression that a family function raising cost the case its parameter file as well,
now a fallback to the pre-template file with no `MESH_TOPOLOGY_FILE` line.

**Two of the review's own gate checks were wrong on the first try, in the same way as the ticket's
originals.** The re-stage check asked only whether each quoted document RESOLVES, and stayed GREEN
on the injection that restores the bug — with two parameter files both quoting the first run's
document, every name still resolved; it measures a BIJECTION now. And the fallback check was inert
twice: once crashing the file, and then, with the `except` added to stop that, letting the raised
placeholder satisfy the very condition being tested (one entry, no `MESH_TOPOLOGY_FILE` line). It
pins the entry's NAME now, so "it raised" cannot read as "it fell back".

**Named blind spot: a GENERATED staged entry can overwrite a previous run's file of the same name.**
The narrowing above is what keeps the pair together; the cost is that a file left in `grid/cad/` by
an earlier run whose name collides with a generated one is replaced rather than kept. Reachable only
for a copied input named exactly `Background_para_<case>.dat` or `..._topology.json` that is no
longer a source this run — already an unrecorded leftover, since `SOURCES.txt` is rewritten in full.
Nothing gates it.

**Named blind spot, stated here as well as in the rule file:** only `TopologyModel()`'s DEFAULTS are
run through the real binary. The other seven parameter sets in the spread are checked structurally,
because eight mesher runs in a gate is a cost nobody asked for — so a parameter set that is
structurally legal and geometrically degenerate is not reached.

#### THE BLOCK SKELETON ON THE CANVAS (#136, parent #133)

Two modules, named here because the rule file's pointer resolves to this note for each of them:
`services/topology_skeleton.py` (Qt-free — the count propagation, the corner placement and the ONE
owner of "is there a skeleton to draw") and `views/mesh_canvas_skeleton_mixin.py` (pens, symbols and
z-order, and nothing else). The hook and the third `auto_range` source are in
`views/mesh_canvas.py`, whose one-shot fit token is shared with
`views/mesh_canvas_geom_mixin.py` — the other half of the fit rule, and named here because that
file is otherwise reached by no area glob. The emit that makes a typed parameter reach the canvas
is `_on_topology_edited` in `views/panels/mesh_config_build_mixin.py`, routed through
`controller.handle_topology_changed`. Gate: `tests/test_topology_skeleton.py`.

**What the ticket is actually about is the NUMBER, not the outline.** A `count` in a topology
document is a SEED. Opposite sides of a block carry equal counts and a shared edge is ONE edge two
blocks name, so on the shipped four-block H-grid FOUR declarations decide TWELVE edges — measured,
not asserted: the mesher's own banner on `examples/topology/hgrid_blocks.json` reads
`Point counts : 4 declared, 8 propagated ('h02' = 7, 'h12' = 5, 'v20' = 4, 'v21' = 6, 'h01' = 7,
'h11' = 5, 'v10' = 4, 'v11' = 6)`. An overlay drawing the block boundaries alone would show the half
a user can already predict from the parameters they typed and hide the half they cannot.

**The propagation is a SECOND HOME for `resolveEdgeCounts`, and the alternative was measured to be
unaffordable rather than merely inelegant.** Asking the authority means writing a document to disk,
launching a process and parsing its report — for every keystroke in a parameter box. So the rule is
restated in Python: union each block's OPPOSITE sides, which for `[south, east, north, west]` are
the index pairs (0, 2) and (1, 3), then one seed per class. What keeps the two together is two
checks rather than discipline. Check 2 reads the pairing literal out of `src/MultiBlock.cpp` AND out
of `services/topology_skeleton.py` and compares them — and FAILS, never skips, when either is
unfindable, because a check that cannot see its subject must not report success about it. Check 12
runs the REAL mesher and compares its `Point counts` row edge by edge, on the shipped document and
on one the H-grid family produced: `5 declared, 12 propagated` against the same 5/12 and the same
twelve values.

**A refusal resolves to no number.** A class with no seed and a class with two seeds that disagree
are the two documents `resolveEdgeCounts` exits over; both label `?` here. Picking one of two
conflicting seeds would label a mesh no run will produce, and going blank would hide the one state
that stops the run. The negative control is in the same check: the two-block fixture with a single
seed resolves `w` = 3 through the shared edge `m` and on to `ee`, which is the chain the C++ gate
uses for the same reason.

**Read-only is a decision about two interactions.** Dragging a BOUND corner means editing a
normalized arc-length position; dragging a FREE one means moving a coordinate — two interactions
behind two identical-looking dots, which is why #133 deferred dragging rather than shipping half of
it. Check 9 holds it by walking the mixin's AST for `TargetItem`, a `movable=` keyword and the mouse
signals. **Its first draft was a substring scan, and it went red on the shipped file**: the mixin's
own header names `movable=True` to explain the rule, and the scan read that prose as the defect it
rules out. A check whose subject's documentation can fail it is measuring the wrong thing.

**The emit, and why no other mesh field has one.** `mesh_config_changed` fires for STRUCTURAL
edits — the geometry list, a role, a BC — and not for a plain spin box; that is the same gap
`undo_ctrl._wire_widget_edits` exists to cover for the undo recorder, and the canvas has no
equivalent generic traversal. Before this, the overlay tracked a programmatic `set_config` and
nothing a user typed. `_on_topology_edited` is SCOPED to the template table (widening it to every
mesh field would change what the canvas does on every other panel edit, which is not this ticket's
to change) and to the MODE combo, which is the other half of `skeleton_for_config`'s question —
without that one line the canvas kept drawing a topology while `_apply_mode_visibility` had hidden
the section that owns it, which is how check 10d found it.

**`auto_range` gained a third source because a template case can have nothing else.** An empty
`cads` is legal in `MESH_MODE 1`, so a skeleton is sometimes the only thing on the canvas with an
extent; it is UNIONED with the mesh and geometry-preview bounds rather than preferred, so a bound
topology still fits its geometry too.

**The FIT, as opposed to the union, shipped wrong, and both review axes found it independently.**
`auto_range` sets `_did_initial_fit`, the one-shot token the ASYNCHRONOUS geometry-preview load
spends (`mesh_canvas_geom_mixin._on_geometry_previews_loaded` fits only `if not
self._did_initial_fit`). The skeleton is built at the TOP of `update_mesh_config`, before those
previews are even requested — so fitting there unconditionally spent the token on content that had
not arrived, and the geometry was then never fitted at all. Measured by the Spec axis on a
`MESH_MODE 1` config naming `naca0012.dat` (x 0..1): the view came out at **x 0.026..0.174**, most
of the aerofoil off screen, while the same config in hybrid mode fitted it correctly. The rule text
shipped in the same commit — "unioned rather than preferred, so a bound topology still fits its
geometry as well" — was refuted by the code beside it, because the union branch ran before the
geometry existed. The skeleton now fits only when there is no mesh AND no `geom_files`; with
geometry, the preview load spends the token and `auto_range` unions the skeleton in.

**Its first gate check could not see the defect either, and an injection is what said so.** Check
11e put the geometry INSIDE the skeleton's extent, so a skeleton-only fit covered both and the
check passed; injection M (fitting unconditionally again) reddened 11d alone. The fixture now puts
the naca around y 0 and the skeleton at y 5..6, neither containing the other, and M reddens both.

**A keystroke reached the disk, and dropped something visible on the way.** The first version
emitted `mesh_config_changed`, whose handler reloads every geometry preview and re-reads every
`.meta` — the Spec axis measured **12 preview reloads for five characters typed**. The cost itself
is small (0.27 s for 40 keystroke-equivalents with three geometries loaded, measured here), and it
is not why this changed. `update_geometry_previews` OPENS by calling `highlight_geometry_file(None)`
to drop a stale selection highlight, so typing in a template row cleared the yellow outline of the
geometry selected in the config list, and nothing put it back until the user clicked again. A
template row cannot have changed a geometry file, so the panel now emits a narrow
`topology_changed` and the controller calls `update_mesh_config(cfg, reload_geometry=False)`. A
FLAG on the one function rather than a second entry point: the skeleton, the domain box and the BC
preview keep one route and cannot drift apart. The narrow handler deliberately syncs no model —
`undo_ctrl._wire_widget_edits` already routes every widget edit through `on_panel_edited`, and a
second traversal would be free to cover a different widget set, which is the defect that traversal
exists instead of.

**An invalid `count` read as an absent one, which is a number over a refused run.** The mesher
refuses a `count` that is present and not an integer >= 2 (`src/MultiBlock.cpp`, `count >= 2`);
`resolve_counts` treated it as "no declaration here", so a VALID sibling seed in the same class
resolved every edge to a number for a document that never meshes. It now unresolves the class.
Narrower than the mesher, which refuses the whole document — here the `?` lands on the edges the
user has to fix. Unreachable from the shipped family (`topology_hgrid._override` clamps to >= 2),
and `resolve_counts` is public and #138 will feed it hand-authored documents. **Its first fixture
made the injection INERT**: with only the invalid seed in the class, removing the fix left a
seedless class and both readings answered `None`. The fixture carries a valid sibling now, and
injection P reddens 4e.

**Named blind spot: the overlay draws the MODEL and never a hand-named topology FILE.** #136's own
criterion — "does not survive switching to a case with no topology model" — read literally. The cost
is that every shipped document declaring an `on_geometry` corner (`cavity_block.json`, the O-grid,
the C-grid) is a hand-named file, so the BOUND-corner marker the ticket asks for is exercised only
by handing `update_topology_skeleton` a skeleton built in the gate, not by any shipped path, until
#137 ships a family that declares one. Drawing a named file needs binding resolution, which is
#137's.

**Named blind spot: the mesher can only be compared on a document it ACCEPTS.** The banner check 12
reads is never printed by a refused run, so the two refusals are held at opposite ends and never
compared — `test_multiblock_weld_surface.py` check 6 proves the mesher refuses them, check 4 here
proves this module answers `?`, and nothing asserts the two refuse the SAME documents. A module
that saw a conflict where the mesher sees none would draw `?` over a mesh that runs; the reverse
would draw a number over a run that is refused. Only a human would notice either.

**This entry's first draft was wider, and one injection refuted it.** It claimed that a defect
mis-partitioning the count classes was invisible to the cross-check as well. Injection A — unioning
each block's ADJACENT sides instead of its opposite ones — reddened `12c` on BOTH documents, so the
cross-check sees a mis-partition perfectly well. What it also showed is a real weakness one level
down, which the entry now carries instead: `12b`, the declared/propagated SPLIT, stayed GREEN
through injections A and B both, because mis-partitioning the classes does not change how many
counts the document declares. The edge-by-edge half is what earns check 12 its place; the split
half would have passed two mutations that destroy the feature.


#### THE O-GRID BINDS TO THE CAD, AND A BROKEN BINDING REFUSES (#137, parent #133)

Two modules, named here because the rule file's pointer resolves to this note for each:
`services/topology_ogrid.py` (the family, and `plan()` — the ONE owner of every number the
read-out displays) and `services/topology_binding.py` (what a binding resolves against, and the
refusal when it cannot). The panel half is the two rows wired in
`views/panels/mesh_config_build_mixin.py`; the projection and the case staging pass the context
from `models/mesh_config_io.py` and `services/case_sources.py`.

**Why a positional binding is the thing being designed out.** A segment index is positional, so
inserting, deleting or reordering a segment shifts every binding after it and each then names a
DIFFERENT segment, with no error at all: the mesh runs, exports and looks right while carrying the
wrong conditions. That is the same failure class that once exported an entire mesh as `wall`
(`docs/design_notes/` on the orphaned `GROUP_BC`). The refusal is not defensive programming; it is
the only signal available, because nothing downstream of a wrong-but-valid binding can tell.

**The id is already there — this ticket did not invent one.** `SegmentModel.id` is stamped into
the `.meta` sidecar by the resampler (`tools/PreProcessor/src/main.cpp`,
`const int segId = sj.value("id", segIndex)`) into both the `NSEGMENTS` rows and the per-point
`POINTS` column, and the mesher matches on that number (`src/MultiBlock.cpp`,
`if (g.segId[k] != seg) continue`). So the sidecar's column IS the stable id and "resolving a
binding to a sidecar segment" is a LOOKUP that proves the id is still on disk, not index
arithmetic. Recorded because the ticket's wording implies a conversion that does not exist, and a
reader looking for one would go and build it.

**Blank adopts; captured binds.** A stored list of ids is what makes a later deletion a refusal
rather than a shorter ring — a family that re-derived the list at projection time would simply
mesh three blocks where it used to mesh four. So `ogrid_body_segs` is blank only until something
captures it, and the panel captures it the moment the user names the geometry, which is both the
one moment they have said which shape they mean and the only one at which overwriting the row
cannot destroy an answer they typed. It leaves an existing binding alone unless the geometry it
names no longer answers for it: re-picking the same file must not silently re-adopt segments the
user has edited, and repairing a binding a CAD edit broke is #138's, not this handler's.

**Two things the gate found that the design did not.**

* **A two-block ring is not meshable at all.** The family's first floor was two — the smallest
  ring that closes. Measured 2026-09-23 on a real run: the mesher refuses it with
  `block 'q1': its corners 'b1', 'f1', 'f0', 'b0' wind clockwise (signed area -0.000000)` and the
  topology exit code 8. Its block-orientation test takes the signed area of the corner CHORD ring,
  and with two corners on each outline all four corners of every block are collinear. `MIN_BLOCKS`
  is 3, and the family refuses below it with a sentence naming the fix — the mesher's own refusal
  moved forward to where the user can act on it. The winding check that caught it places the
  corners rather than reading the declaration order, which is also why injection C (deleting the
  clockwise mirror) reddens it while the ring-closure check stays green: the ring still closes as
  a declaration, it just closes the wrong way round on the page.
* **A derived count moved when the geometry was re-sampled.** Two separate causes, both found by
  the same byte-for-byte check. The radius was a mean over the sampled points, which falls as a
  square outline gains points; it is now AREA-EQUIVALENT (`sqrt(|A| / 2π)`), exact at any sampling
  of a straight-sided outline and 0.4999971 against a true 0.5 on the shipped 160-point circle.
  And a wall count derived from a polyline's SUMMED arc length sat on an exact tie —
  2.4999999999999996 against 2.5000000000000004 for one fixture — where Python's half-to-EVEN
  `round` lands on different integers. It now rounds half up with a 1e-9 tolerance. Either alone
  made changing point density a topology edit, which is precisely the acceptance criterion.

**The far field is DRAWN, never generated, and that is a narrowing of the ticket's own wording.**
#137 says the user "fills in the far-field size"; #133 decides that the template writes no
geometry. Both cannot hold: a far field synthesised from a radius has no geometry to bind to, so
its edges would be straight chords between block corners — a SQUARE far field on the four-block
case, which is not a far field anyone wants, and no boundary conditions of its own. The ticket's
own demo draws one ("draw a circle and a far-field circle"), so the drawn reading is the one that
survives and the radius parameter does not exist. Stated here rather than silently dropped — and
it does cost #133's user story 2 its "far-field radius", which is a TICKET amendment rather than
code, since no amount of code can both synthesise a far field and write no geometry.

**The segments pair ONE TO ONE, and a mismatch is refused by name.** The alternative — a common
refinement of both outlines' segment boundaries — is general but produces wildly uneven blocks,
and every block boundary it invents is one the user never asked for. Pairing is what the shipped
hand-written `examples/topology/ogrid_circle.json` does, and "segment the far field the same way
you segmented the body" is an instruction a user can follow. A wall edge must lie within ONE
source segment because a `binding` declares one `seg`; that is why the block ring REFINES the
segment partition rather than cutting across it, and why `ogrid_splits` is per segment.

**The derivation is the panel's most useful output, so it shows the working.** `q = 1 + 2π/N_theta`
is the radial law that gives unit aspect ratio on a circular O-grid, because a circumferential cell
at radius r is `2πr/N_theta` long and a radial step equal to it is `dr = r · 2π/N_theta`. The
default radial count is where a geometric law STARTING at the run's `BL_INITIAL_THICKNESS` and
growing at `q` reaches the far field, which is the ticket's "how many radial points would close the
gap". On the shipped circles at a 0.0327 target cell that is 96 circumferential cells, q = 1.06545,
a 1:1 first cell of 3.27e-02 against the 1e-3 asked for — 32.7x flatter — and 103 radial nodes,
against the 49 the hand-written document declares. Every one of those numbers is in the read-out,
not just the 103. No `ds_start` is declared anywhere: the first cell keeps its one home under the
name it already has, and `plan()` READS it so the read-out can say what the choice costs.

**The context is not configuration and is never persisted.** It is what the user's CAD looks like
right now, rebuilt from `MeshConfig` at projection time and cached by each file's `(mtime, size)`
so the overlay and the read-out can ask on every keystroke without re-parsing a `.dat` per
character. A copy inside the project file would be a stale geometry list that the next run
believed. The H-grid accepts and ignores it, so `fam.build` stays a call rather than a dispatch.

**The structural invariants moved into one checker.** `tests/topology_doc_invariants.py` holds
what the mesher refuses a document for, and BOTH family gates call it. The check numbers and
messages in `test_topology_templates.py` are unchanged; what moved is where each rule is written
down. A second copy is one that can come to disagree, and the family it disagreed about would be
the one that shipped a refusal.

**The review found that "reordering is unreachable" was FALSE, and it was this note that said it.**
The first version argued that #137's "deleting **or reordering** a bound segment causes the
projection to be refused" was half-satisfied by construction, "because there is no position
anywhere in the chain". That is wrong, and measurably: the stored binding list is ORDERED, and
`_ring` walks it in that order, so swapping two ids leaves every one of them resolvable while
sending a wall edge backwards along the body. Measured on the gate's own fixtures before the fix:
`0,2,1,3` PROJECTED a document, and the C++ mesher then refused it at exit 8 — the right outcome
reached by the wrong owner, after the panel's read-out had said nothing; and `3,2,1,0` was refused
with a FALSE diagnosis, "the body and the far field are wound in opposite directions", naming no
edge. `order_problem` now refuses both, naming the edge, and the rule it enforces is that the
positions of the bound ids in the geometry's own list must be CYCLICALLY INCREASING — so a
rotation is fine (a ring has no first segment) and a subset is fine (a binding need not use every
segment), while a walk that goes backwards at more than one joint is not. **The subset half of
that sentence was SUPERSEDED by #138** and is kept as written because the shape is the same one
this paragraph is about: a subset really does walk the geometry's order, so `order_problem` really
does not fire — and the four-block ring it projected was then refused by the C++ mesher at exit 8,
for the edge that would have to span two source segments. The claim was true of the FUNCTION and
false of the DOCUMENT, and nothing was asking the second question until a dropdown repair produced
exactly that state. `cover_problem` asks it now; see "THE BROKEN BINDING IS REPAIRED FROM THE
PANEL" below. A two-entry list cannot
tell a reversal from a rotation and is not refused; with two positions there is no third to break
the tie. The wrong claim is kept above the checks rather than deleted, because an argument that an
acceptance criterion is unreachable is exactly the kind that needs a measurement and did not get
one.

**Three more the review found, all in the parser and the panel.** `parse_binding` (then `_ids`)
SKIPPED a token it could not read and fell all the way back to adopting the whole geometry when
none of them parsed — so `"0,x,2"` bound two segments where three were written, which is the
silently-shorter-ring this design exists to make unreachable, reintroduced inside the parser meant
to prevent it. It now refuses, and refuses a duplicate id for the same reason (one segment at two
ring positions is two walls on one stretch of geometry). The panel had its OWN reading of the same
string and the two disagreed on exactly that input; it now asks `parse_binding`. And the capture
was keyed on "do the held ids still resolve?" rather than on WHICH FILE they were captured for:
both shipped circles carry segments 0-3, so switching the body from one to the other kept a
binding chosen for the other shape — this ticket's failure class reached by another route.

**Two smaller ones, recorded because both were invisible until named.** The far-field-inside-body
refusal sat AFTER the radial derivation, which therefore answered on a negative span before the
refusal fired; it is now before it. And `MAX_RADIAL` clamped a count the panel presents as the
derivation's answer, silently; the read-out now says when it fires.

**What the two binding rows are, after the review.** They are READ-ONLY, because #133 decides that
which edges bind is the template's decision and not the user's, and a hand-typed segment id is a
more internal control than the normalized arc-length position that decision was protecting users
from. They exist as rows at all because a binding must be STORED to be a binding, and a field-spec
row is how this package stores and gates a parameter. Re-pointing one is #138's dropdown. The
pairing of geometry row to binding row is declared in `topology_field_specs.BINDING_ROWS` rather
than spelled in the panel, so a second binding family needs no view edit and the bidirectional
gate can see both halves.

**Named blind spots.** The fixtures in `test_topology_ogrid.py` are written by the gate rather
than by the real `surface_resampler`, so a change to the sidecar FORMAT is caught next door in
`test_multiblock_binding_surface.py` and not here. Reordering segments without renumbering them is
now refused by `order_problem` rather than argued away; what remains unreachable is a two-entry
list, where a reversal and a rotation are the same sequence. The 1:1 law
is an idealisation for a circle, so on a shape that is not one the equivalent radius is an
approximation and nothing measures how good it is; the count it produces is a default the user may
override, which is what makes that acceptable.


#### THE BROKEN BINDING IS REPAIRED FROM THE PANEL (#138, parent #133)

Three modules, named here because the rule file's pointer resolves to this note for each:
`services/topology_ogrid_binding.py` (the stored list's one reader, one writer, order rule,
coverage rule and repair — split out of `topology_ogrid.py`, which this ticket took past the
repo's ~500-line standard), `views/panels/mesh_config_repair_mixin.py` (the flag, the dropdown and
the write) and the `BrokenBinding` row in `services/topology_binding.py`. The registry's dispatch
is `topology_model.broken_bindings`; the gate is `tests/test_topology_repair.py`, with the fixture
writer and the CAD edit that breaks a binding in `tests/topology_outline_fixture.py`.

**Why the refusal alone was not enough, in the ticket's own words.** #137's refusal is correct and
leaves the user holding an error message and a JSON document they were never meant to open — at
the one moment they already know the answer, because they are the one who just went back to the
CAD stage and cut the segment. So the repair belongs where the knowledge is.

**The thing the ticket asks for could not be built as asked, and the measurement is why.** A
dropdown that REPLACES the broken id at its ring position is the obvious reading of "choosing one
repairs the binding", and it was the first version. It produces a document the mesher refuses at
exit 8: `edge 'w2' binds to segment 8 ... so both of its corners must lie on that segment — but
corner 'b3' is attached to segment 3`. The reason is structural rather than incidental. Each wall
edge runs from its own segment's start to the NEXT bound segment's start, so the next bound segment
has to be the geometry's next segment — all the way round. **A valid O-grid binding is therefore a
ROTATION of the geometry's whole segment list and nothing else**, and the only information a stored
list carries is where the ring starts. Once that is seen, the repair writes itself: naming the
segment one flagged edge should lie on picks the rotation, so `repair_binding(order, pos, seg)`
returns the geometry's current ids rotated to honour that choice and does not read the broken text
at all. It is also why the dropdown offers the geometry's WHOLE current list rather than a filtered
one — every entry names a legal ring.

**Two consequences, both deliberate.** Repairing a binding a SPLIT broke makes the ring one block
BIGGER, because the user really did cut one more segment into the outline; and the far field then
has to be cut too, or the one-to-one pairing refuses by name. That second refusal is #137's and is
not repairable by a dropdown — no choice of segment can make four pair with five — so it is left
saying what it says.

**The resolve moved in FRONT of the pairing check.** With one list repaired and the other still
broken, the two lists differ in length BECAUSE of the binding still broken in the other, and
answering "the body binds 5 source segment(s) and the far field 4" there names no edge and sends
the user to look at the wrong geometry. `plan` now resolves each list against its own ring first,
so a broken binding is reported as one. That change cost `test_topology_ogrid.py` check 14 its
fixture — the case had bound a far field `"9,7"` on a geometry carrying only segment 9, which is a
missing segment rather than a count mismatch — and it now reaches the pairing refusal the only way
that remains: two geometries cut into different numbers of segments.

**The flag is a POOL of rows that is never destroyed.** A repair is made from inside a combo's own
`currentIndexChanged`, and the refresh it triggers arrives while that signal is still on the stack,
so rebuilding by deleting and recreating the rows deletes the widget mid-emit — the gate CRASHES
rather than failing a check. Reusing a pool (grown as needed, the surplus hidden, every repopulate
inside `block_signals`) keeps the whole path synchronous, which is also what lets a headless gate
drive it with no event loop. The alternative, deferring the rebuild with a zero-timer, would have
made every gate that touches this section pump events.

**`panel_edited` is what puts the repair inside the funnel.** `undo_ctrl._wire_widget_edits`
traverses the panel's widgets ONCE, when it is constructed, so a combo created or re-purposed later
is invisible to it — the same gap the restart chooser (#31) declared that signal for. Without it
the write still lands in the widget and reaches neither the global model nor the undo stack, which
is the injection that reddens the persistence and undo checks while the repair check stays green.

**The refresh hangs off `_refresh_topology_counts`.** That is the one place already holding both a
template model read back from the widgets and the binding context for this case, and it runs on
every template keystroke AND on every `set_config`. So the flag clears when the cause is removed by
other means with nothing in the panel knowing why: undoing the CAD edit rewrites the sidecar, the
binding cache is keyed by its `(mtime, size)`, and the ids resolve again on the next refresh. A
second traversal for the flag would have been a second chance to cover a different trigger set.

**What the gate measures, and one thing it had to stop measuring.** The break is the real one — the
fixture cuts a bound segment in the SIDECAR ONLY, which is what a CAD split does: the `.dat` is
untouched and every coordinate the binding was chosen against is still where it was. The run-
proceeds half runs the real mesher with `MB_SMOOTH_ITERS 0`, and the reason is measured rather than
stylistic: this fixture's own UNBROKEN four-block ring comes back at exit 9 with 32 of 704 cells
inverted AFTER the smoother and 0 before it, on a 0.5 body inside a 4.0 far field at a 0.2
circumferential cell. That is the smoother's business and `test_multiblock_smooth_surface.py`
holds it; a binding gate failing for it would be failing for a reason that has nothing to do with
a binding. The control run — the same fixture, no CAD edit — is what makes the repaired run's exit
code a claim about the repair.

**Three of the seven injections bit differently from the prediction, and two of them changed the
gate.** Removing `cover_problem` reddened ONE check and would have reddened NONE as the file was
first written: every repair this gate makes produces a full cover, so nothing reached the refusal,
and the rule #138 discovered was gated only next door in `test_topology_ogrid.py`. Check 5d was
added for it, and it asserts exactly the string the naive repair writes. Making `repair_binding`
adopt the geometry's list outright left check 4 GREEN, because segment 8 at position 2 IS the
identity rotation of this fixture's list — so the one check that drives the real controller now
asks for segment 9 instead. And deleting the `panel_edited` emit left the PERSISTENCE check green
while the undo checks went red: `_collect_project_state` refreshes each model from its panel before
serialising, so a repair that never reached the funnel is still saved, and only Ctrl+Z can tell.
Two more are recorded for their shape rather than their content: the injection that removes the
whole feature prints ONE `FAIL` line and then crashes, and the one that destroys and recreates the
rows prints ZERO — with no event loop the deleted widgets are not collected, so the gate limps on
against stale rows and dies late. Both are exit 1, which is the only signal that means anything
here.

**The review found two things, and one of them is the ticket's own demo.** #138 says "split one of
the bound segments ... generate successfully", and under #137's one-to-one pairing that cannot end
in a mesh: cutting only the body gives it five source segments against the far field's four, so
repairing the body's own binding leaves nothing flagged and the run still refused. No dropdown can
fix it — no choice of segment makes four pair with five — so what the gate pins is that the state
is reached honestly: no flag the user cannot act on, and a refusal naming the CAD action rather
than an edge. It is a TICKET-level conflict with #137's pairing design, of the same kind as #137's
own far-field-radius amendment, and it is recorded rather than papered over. The second finding was
a plain defect: `_refresh_topology_counts` returned early for a family that is not the O-grid,
BEFORE asking what was broken, so switching the family combo left the amber flags and their
dropdowns on screen naming edges of a template no longer selected — and picking from one still
wrote the `ogrid_*` row. The family's own answer was already empty; it was simply never asked.

**And three smells worth the edit.** `plan` recovered the broken edge from the refusal it had just
written (`why.split("edge '")[1]`), in the package whose own rule is that `BindingError` carries
the edge as a FIELD precisely so nothing parses prose for it; both order and coverage refusals now
answer `(edge, problem)`. The two-list pairing was retyped twice in `plan` and a third time as
`BINDING_LISTS`, under a comment claiming it was named once so a third reader could not spell it
differently — the third reader was `plan`, and it spelled "far-field" where the table says "far
field", so two refusals about one list hyphenated it two ways; both loops now read the table. And
the repair's write returned silently when no panel row authored the field the family named, which
is the one outcome a repair panel must not produce without a word; it logs at `warning`.

**Named blind spots.**

* **A repair that names a segment far from where the broken one lay is legal and makes a bad
  mesh.** The choice decides the ring's rotation, so pairing body corner k with a far corner most
  of a turn away is a document nothing refuses — measured at exit 9 with 67 of 704 cells inverted
  when the gate first picked "whatever is offered first". Nothing can do better from inside the
  panel: the deleted segment is gone from the sidecar, so there is no record of where it lay, and
  the stored list's neighbours are the only hint. Cutting the two outlines at DIFFERENT arc
  positions has the same effect through a different route (22 of 704 on the gate's first aligned
  attempt) and is #137's pairing design rather than this ticket's.
* **`broken_bindings` reports only what a dropdown can repair.** A geometry the mesh does not
  load, an unparseable list, a body that is not closed, a far field inside the body — none is a
  wrong SEGMENT, so none is flagged, and all of them keep the read-out's sentence as their only
  voice. A user whose read-out says something the flag area does not is looking at one of those.
* **Nothing gates the FAMILY dispatch's empty half.** `Family.broken` is `None` for the H-grid and
  the gate asserts the O-grid's answer; a third family that forgot to declare one would report
  nothing broken and be invisible here, exactly as the H-grid correctly is.


#### THE TOPOLOGY DETACHES INTO A FILE (#139, parent #133)

Two modules, named here because the rule file's pointer resolves to this note for each:
`services/topology_detach.py` (the transition, the suggested path, the provenance summary and the
one wording of what re-attaching costs) and `views/panels/mesh_config_detach_mixin.py` (the box,
the Save dialog, the consent and the greying). The state is one field on `TopologyModel`; the gate
is `tests/test_topology_detach.py`; the enabled mirror of `set_spec_row_visible` is
`views/panels/field_widgets.py::set_spec_row_enabled`.

**What the escape hatch is for, in the ticket's own words.** Without it the first case outside the
template library's coverage locks the user out of the very path the library exists to open. What
it must NOT become is the other failure the ticket names in the same breath: an editable panel
whose edits no longer take effect, which is a control that does nothing.

**One flag, and it turns off the one predicate.** The whole feature is `detached: bool` making
`names_a_family()` False while `family` stays named. That predicate already had three readers from
#134/#135 — the funnel that projects, the case staging that generates, the canvas that draws a
skeleton — and #139 adds a fourth by asking it inside `broken_bindings`. Nothing at any of the four
was edited. The measurement is injection A: restoring `names_a_family` to `bool(self.family)`
reddens checks 3, 3c, 5, 5b, 6c and 14, i.e. the projection, the staging, the re-attach and the
real mesher all at once. That is the argument for stating it as ONE owner rather than as an
`if` at each site, made in the form of a blast radius rather than as a preference.

**Why the parameters are kept rather than cleared.** They are the provenance, which the ticket
calls the only useful thing left three months later. Keeping them costs one thing — the panel now
shows values that decide nothing — and that cost is paid by greying every row rather than by
deleting them, so the section reads as a record. The summary is DERIVED from `TOPOLOGY_SPECS` by
the family's declared prefix, which is the same bidirectional property the parameter gate holds
for the panel: a parameter added to a family and its table appears in the summary with no edit
here. Injection G (a hand-listed H-grid summary) leaves check 12 green and only 12b red, which is
why 12b compares against the table rather than against a literal.

**Why re-attach clears `mesh_topology_file`, which is the one decision that is not obvious.** With
a family attached the funnel passes the projected path as an override, so a path left in that row
changes nothing about the run — and yet it is on screen, in an editable row with a Browse button,
and it becomes live the moment the family combo is set back to "(none)". Injection C restores the
old behaviour and check 6 stays GREEN: every behavioural claim about the re-attached run still
holds, and only 6b — which asks what the row now says — sees it. A defect that no behavioural
check can reach is exactly the shape this repo keeps finding in "a control that does nothing".

**Why the state is a field-spec row and not a flag the panel keeps.** `get_config()` builds a
FRESH `TopologyModel` and fills it with `read_specs(self, TOPOLOGY_SPECS, topo)`, so a model field
with no row is silently reset to its default on EVERY panel edit — the detached state would have
survived exactly until the user touched a spin box. Making it a row buys the persistence, the
sync, the projection and undo for nothing, and it is the shape #138 already used for the binding
repair: the action writes into the row, and the row is what everything downstream reads. It costs
a `readonly` option on the `bool` kind, spelled `setEnabled(False)` because `QCheckBox` has no
`setReadOnly` — with the consequence the Edit-BL dialog's greyed-field rule already recorded, that
Qt walks the mouse past a disabled widget, so the row's tip lives on its `?` helper.

**The write order is load bearing and was nearly wrong.** `undo_ctrl._wire_widget_edits` connects
`QLineEdit.textEdited` — user typing only — and `QAbstractButton.toggled`, which Qt emits for a
programmatic `setChecked` too. So writing the path row reaches nothing and writing the checkbox
reaches `on_panel_edited`, which reads the WHOLE panel back: the pair lands together, as one undo
step, if and only if the path is written first. That is also why the detach box declares no
`panel_edited` of its own, unlike `TopologyRepairBox` — its children are two plain `QPushButton`s,
which never emit `toggled`, and the row they write into is already inside the funnel.

**A defect this ticket found in #134/#135 and fixed.** `mesh_modes.missing_mesh_input` refused
every ATTACHED template case: `mesh_topology_file` is an output while a family drives the run, so
it is empty until `save_config_to_file` projects the document — which is AFTER the precondition
runs. The GUI showed `MESH_TOPOLOGY_FILE names none` on a fully configured case, and
`pipeline_runner` raised it as a `PipelineError` before writing anything, so no template case
could run through the pipeline at all. #135's own gate could not see it: it drives the mesher
binary directly on the projected config and never goes through either host's precondition. It is
#139's business because "re-attach returns to generating" would otherwise hand the user back a
case the pipeline refuses. Check 15 now asks all four multi-block cases — template, detached,
hand-written, and neither — in one line.

**What the gate measures rather than describes.** "Nothing overwrites it" is not a claim about a
branch not taken: the detached document is edited to a node count no derivation would produce, the
real funnel is run over it twice, and the real mesher is then asked to cut it — 117 nodes against
the template's 275. The two-host half does the same on its own file (70 against 275), because a
detached document that is byte-identical to the template's cannot tell a host that read the file
from one that quietly re-projected.

**What the review round changed, and the one finding that mattered.** The Spec axis measured the
provenance summary against the criterion's own words — *"still naming the originating family and
its parameters"* — and found it PARTIAL for the O-grid. The summary derives its rows from the
field-spec table by the family's prefix, and #133 deliberately gives a template no alias for a
physical quantity the run already carries, so `BL_INITIAL_THICKNESS` — the number that sets the
radial count — has no `ogrid_` prefix and was silently absent. Every check was green on it,
including the one that walks the table, because the H-grid's prefix happens to cover everything it
reads. `Family.reads_context` now declares `(BindingContext field, label, MeshConfig attribute)`
per such quantity and `test_topology_param_specs.py` checks 11/11b pair it against an `ast` walk
in both directions; check 12d asks it of EVERY family rather than of the one in front of it.

The same axis found the re-attach direction gated only at the panel, where the criterion says
*"detach and re-attach are persisted with the project"* — check 13e drives it through the real
controller's snapshot, with 13e-pre making it non-vacuous. Two cosmetics went with them: a
`default_path` that produced `topology_topology.json`, and a summary printing `Override Radial
Nodes: 0` where 0 MEANS "derived" (the row now declares `special`, which the spin box shows too).

The Standards axis found the new row's tooltip written as developer rationale with a ticket number
in it, in a table whose every other row speaks to the user; `set_spec_row_enabled` duplicating
`set_spec_row_visible` verbatim (one `_apply_to_spec_row` now); `detach` returning a second
spelling of the path its caller reads off the config; the clearing rule spelled in both `reattach`
and its caller; a `makedirs` in the Save dialog that created `config/topology/` even when the user
cancelled, contradicting `default_path`'s own docstring; a `_log_detach` that only forwarded; and
`mesh_modes.topology_file`'s docstring still claiming to be the one place that asks both halves of
a question `missing_mesh_input` now asks differently. All fixed. The three-state predicate set
(`has_family` / `names_a_family` / `is_detached`) came out of that axis too, and it closed the
blind spot this note had listed one paragraph later — the list was written before the fix existed,
and review took it at its word.

One thing the injection round measured about the GATE rather than the code: check 16b compared the
two hosts' VTK text byte for byte and FLAKED on its second run. This mesher wobbles at ~1e-13 and
its node numbering varies run to run, which `tools/scripts/golden_mesh.py` exists to say; the
check snaps to 1e-10 and sorts, snapping BEFORE sorting.

**Named blind spots.**

* **The suggested path is a suggestion, and nothing checks where the user actually puts it.** A
  detached document saved under `results/` is inside `clean_results.sh`'s reach; `default_path`
  steers to `config/topology/` for exactly that reason, and the Save dialog is free to go
  anywhere. Nothing warns.
* **Detach writes a file that undo cannot take back.** Ctrl+Z walks back the STATE — the flag and
  the path — and the document stays on disk, which is the right half to be irreversible (deleting
  a file on undo would be worse) but means an undone detach leaves a stray document behind. The
  same is true of re-attach, which by design never deletes.
* **A detached case whose file is deleted is refused by the MESHER, not by the panel.** Nothing
  here checks that the path still resolves; `missing_mesh_input` asks only whether one is named.
  That is the same standing behaviour as a hand-written topology and is not made worse by
  detaching, but a user who moves their file gets the mesher's message rather than the panel's.
* **The greying is asserted over `TOPOLOGY_SPECS` only.** A control added to the template section
  that is NOT a row of that table — the repair box's dropdowns, say — would stay live when
  detached. The repair box is hidden in that state because `broken_bindings` returns nothing for a
  detached model, so it is covered by consequence rather than by the loop; a third such widget
  would need its own line.
* **CLOSED in review, kept as the shape:** the three states were told apart by two predicates plus
  an inline `bool(model.family)` at three sites, so a caller wanting "a template is configured
  here" and reaching for `names_a_family()` would have got False for a detached case. All three
  now live on the model (`has_family` / `names_a_family` / `is_detached`) and the summary's own
  "is there provenance to show" question asks the first. What is still ungated is the CHOICE
  between them: nothing notices a new caller picking the wrong one of the three.
* **`Family.reads_context` is declared, so a family that forgets one is caught only where the
  `ast` walk can see it.** Checks 11/11b compare the declaration against `<name>.<attr>` reads
  whose attr is a `BindingContext` field — the same scoping blind spot the parameter walk already
  records. A family reading a run quantity through a helper that takes it as a plain float, rather
  than off the context, is invisible to both.


### PreProcessor CLI (`tools/PreProcessor/src/main.cpp`)
- Reads JSON config via `nlohmann/json.hpp` (header-only, bundled)
- `detectFeaturePoints()` → `splitPolyline()` → `alignEndpoints()` → `distributePointsProportionally()`
- Spacing strategies: `uniform`, `curvature`, `cosine` (double-end dense), `geometric` (exponential), `tanh`
- Supporting headers in `tools/PreProcessor/include/`: `Spline.hpp` (cubic spline), `Spacing.hpp`, `Quality.hpp`

