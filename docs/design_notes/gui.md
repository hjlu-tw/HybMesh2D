# PreProcessor GUI design notes

Long-form rationale extracted verbatim from `CLAUDE.md` on 2026-08-28, when that
file passed the 150k-char context limit and was condensed to its rules. Nothing
here was rewritten: this is the original prose, with its measurements, dated
acceptance runs, injections and named blind spots. `CLAUDE.md` carries the rule;
this file carries why it is the rule.

### PreProcessor GUI (`tools/PreProcessor/gui/app/`)
Layered PyQt6 application:

- **`controller.py`**: Top-level orchestrator; command pattern for undo/redo, delegates to specialized controllers
- **`controllers/`**: Business logic split by concern — `segment_ctrl.py` (CRUD, properties), `session_ctrl.py` (save/load), `session_io_ctrl.py` (`.hws` workspace read/write + `WORKSPACE_FORMAT_VERSION` migration), `project_state_ctrl.py` (the workspace's `project` section: Mesh/Solver/IB config + baseline-snapshot dirty detection), `backend_ctrl.py` (runs `surface_resampler` in QThread), `mesh_gen_ctrl.py` (runs `HybMesh2D` in QThread), `lifecycle_ctrl.py` (autosave, crash recovery, bounded worker shutdown), `curve_ctrl.py`, `transform_ctrl.py`
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
`solver_ctrl._confirm_mesh_bc_state`, which *asks* rather than deciding —
`headless_default=True` so batch/CI, which regenerate in the same pass, are not
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

**Portable case export** (`services/case_export.py` + `case_export_docs.py`, both
Qt-free; Solver toolbar "Export Case ⇪" + Solver menu): copies a case's INPUTS into
a folder that reruns on another machine — `grid/` (mesh + `.def` + the getPGrid
sources, whose `para.in` travels as **`getPGrid.in`**: `_RENAMES` owns that mapping
so `run_case.sh --regrid` and the manifest cannot disagree), `work/` (`input.in`,
`.def`, `phi.dat`, and the restart dump **only when `input.in` restarts from it** —
`include_restart="auto"`, since `binDump*` is an output that only a restart run
reads back and is the largest file in the case), `dll/` (`.so` **and** the `.cc` it
was compiled from, pulled from `results/solver/dll_src` by basename), plus
`run_case.sh` and `MANIFEST.txt`. `run_case.sh` **suggests** a compiler rather than
choosing one (`CXX=${CXX:-g++}`, `CXXFLAGS`) — the package is for someone else's
machine, which may build with icpc. Selection is an **allow-list**, so a new output
file can never sneak in, and everything rejected is NAMED in the manifest (split
into known-output, not-used-by-this-run and unrecognised) — a skipped input is a
visible line, not a surprise on the far machine. **The allow-list matches on NAME,
so `work/phi.dat` and `dll/*` also have to ask whether the RUN uses them**
(`_unused_reason`): `prepare_case_dir` reuses a case directory in place, so a case
that once ran an immersed solid still holds both after being re-run without one —
USER-REPORTED (2026-08-12) as "I didn't configure IBM, why is there a phi.dat and a
dll/?". `input.in` decides, being the file the far machine actually runs: it
declares `immersed_solid` and it names every DLL it dlopens by quoted path (plus a
type-11 BC row in `work/*.def`, which is the one DLL `input.in` never mentions).
A `.so` that no longer travels also stops pulling its `.cc` out of `dll_src`.
`solver_case.report_stale_ibm_artifacts` names the same leftover at case-prep time
and never deletes it — with immersed solid ON but no phi field chosen, the init DLL
reads `phi.dat` by that fixed name, so the previous geometry's solid would converge
to a believable answer for the wrong shape. **Every quoted value in `input.in` is a file path**
(see `SolverConfig.generate_input_in`), and the GUI writes absolute ones for any
file the user browsed to; those are staged into `work/` and rewritten to
`./<name>`, which is the other half of portability. The solver binary is
deliberately excluded. Gated by `tests/test_case_export.py`; verified end-to-end
by regenerating the grid with getPGrid from the exported folder and running
unicones on it. Everything the export *writes* rather than copies lives in
`case_export_docs.py` (`run_case.sh`, `MANIFEST.txt`, the rewritten `input.in`,
and `write_extras`); the "is this file an input of THIS run or a fossil of the
last one?" reading of `input.in` lives in `case_export_usage.py`. Both splits
are the file-size budget, not new concepts.

**The package also reopens in the GUI, not just in a shell**
(`services/case_workspace.py`, Qt-free). `run_case.sh` reruns the SOLVER; there
is no importer for an exported case, so "load the case I exported" had no answer
— USER-REQUESTED (2026-08-13). Export Case now *asks* (a third prompt, after the
restart dump and the tarball) and writes `<folder>.hws` into the package via
`export_case(..., extra_files=...)`, so the manifest names it under its own
heading like everything else. Three rules decide whether the workspace is worth
shipping: **(1) re-point by file IDENTITY, never by string** — the map is keyed
by `(st_dev, st_ino)`, so `results/` vs `Results/` on a case-insensitive volume
or a symlinked scratch dir is still the same file, and a path the package does
NOT carry (the CAD `.dat`, the mesh, a declined restart dump) is left alone and
REPORTED in the log rather than rewritten to a name that resolves to nothing;
**(2) the caller's plan is the authority** — `export_case` now accepts `plan=`
because the workspace is derived from the plan, and a second plan built with
different arguments would describe a different package than the one on disk
(decline the restart dump and its path must stay put); **(3) the stamp survives
a move** — a package exists to be copied elsewhere, which strands absolute paths
a second time, so the exported workspace records `exported_case_root` and
`rebase_case_workspace` (called from `_read_workspace_file` on **every** load)
swaps that prefix for wherever the `.hws` is actually being opened from. Note
what does NOT travel: CAD/mesh sources are no part of a solver case, so the
geometry rides *inside* the `.hws` (`original_points` are stored verbatim) and
still draws, but re-resampling or re-meshing needs those files — the export log
and the manifest both say so. `Save Workspace` and the export share one builder
(`session_io_ctrl.workspace_dict()`), so an exported workspace can never
describe less than a saved one. Gated by `tests/test_case_workspace_export.py`,
which drives the real Export Case slot, moves the folder, and loads it back.

**Signal guards**: never write a raw `blockSignals(True)`/`blockSignals(False)` pair — an exception between them leaves the widget permanently unable to emit. Use `with block_signals(w1, w2, ...)` (`app/utils.py`). Likewise, never assign `_is_populating`: use `with controller.populating():`, which is a re-entrant depth counter (a bare bool let a nested populate clear the outer guard). `tests/test_signal_guards.py` statically fails the build on either.

**Error handling**: never `except Exception: pass`. Use `services/logging_setup.py::get_logger(__name__)` and log at `debug(..., exc_info=True)` for a step allowed to fail, or `warning` when the failure silently degrades what the user asked for. `HYBMESH_LOG_LEVEL=DEBUG` surfaces the debug tier. `tests/test_silent_exceptions.py` fails the build if a new undocumented silent handler appears.

### PreProcessor CLI (`tools/PreProcessor/src/main.cpp`)
- Reads JSON config via `nlohmann/json.hpp` (header-only, bundled)
- `detectFeaturePoints()` → `splitPolyline()` → `alignEndpoints()` → `distributePointsProportionally()`
- Spacing strategies: `uniform`, `curvature`, `cosine` (double-end dense), `geometric` (exponential), `tanh`
- Supporting headers in `tools/PreProcessor/include/`: `Spline.hpp` (cubic spline), `Spacing.hpp`, `Quality.hpp`

