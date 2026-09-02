---
paths:
  - tools/PreProcessor/gui/**
---

# GUI seam rules, and the four repo-wide standards in full

Loaded on demand when **any** file under `tools/PreProcessor/gui/` is read — deliberately the
widest glob of #59's six, because these rules bind every GUI file rather than one area's, so
there is no narrower glob that would not lose most of their reach. **Rules only** — the
rationale (the measurements, the dated user reports, the injections and the named blind spots)
is `docs/design_notes/gui.md`. Read that note before overruling a rule here; when a rule
changes, update BOTH.

**Four of these rules are ALSO pinned in `CLAUDE.md`, one line each, and that duplication is
the point.** The GUI↔C++ config parity gate, the GUI file-length limit, `never except
Exception: pass` and `never a raw blockSignals pair` belong to no area, and a glob cannot bind
an edit that happens outside every glob — measured in #61, a rule file does not arrive for an
`Edit` without a prior `Read`, nor for a `Write` creating a new file. The root carries the rule
and its gate; this file carries the whole of it. When one changes, both change.

**Two of the four reach files no glob here covers**, which is the other half of why they are
pinned in the root:
- **Parity** rules on `include/BLParams.hpp` and `include/Config.hpp` as much as on the GUI
  key map. Those two are matched by `.claude/rules/mesher.md`'s `include/**`, and that file
  carries no parity rule — it only mentions the gate in passing (its `MESH_MODE` initialiser
  note). An agent editing the C++ half is reached by the root one-liner, not by this file.
- **`except Exception: pass` and the signal guards** are repo-wide by intent; their gates
  (`tests/test_silent_exceptions.py`, `tests/test_signal_guards.py`) sweep the GUI tree, so
  the glob covers what is gated, and the root line covers what is not.

**The Qt-free seam also governs two files OUTSIDE this glob**, which cannot hand a reader the
text: `tools/PreProcessor/run_pipeline.py` and `run_batch.py` — the headless entry points, and
the ones the deferred-import defect actually killed. The two are NOT equally reachable, and the
difference is measured rather than assumed: `run_pipeline.py` is matched by
`.claude/rules/pipeline-case.md` (which carries the stage rules and not this one), while
`run_batch.py` is matched by **no glob in any rule file** — the same reachability gap #66
recorded for `services/phi_quality.py`. For that one file the tripwire table in `CLAUDE.md` is
not a convenience on top of a glob; it is the only thing that reaches its reader.

**One block travels here that #59 does not assign to any area**: the one-line scroll-wheel rule
(`main.py` disables the wheel on every spin box). Its only file is `main.py`, which no other
rule file's globs reach, and this file's glob is the whole GUI subtree — so this is the only
rule file that can hand a `main.py` reader anything. Recorded rather than left as silent
precedent, per #66.

**One rule's rationale is NOT in the design note, and the header pointer above is therefore
true only in part.** The parity block came out of the root file's `## Build & Run` section,
which the 2026-08-28 extraction (`3a2e096`) never touched — so these 25 lines ARE its whole
story, and `docs/design_notes/gui.md:143` records only the one thing the parity gate *cannot*
see (a spec's `key=` removed leaves both sides agreeing while the writer keeps emitting).
Stated here rather than fixed by moving text into a note, which #59 puts out of scope.

**The GUI file-length limit is an ADDITION, not a relocation, and it has no gate.** #59 and #67
both name it among the four repo-wide standards, and it is a standing instruction from the
user — but it has never appeared in `CLAUDE.md` in this repo's git history (measured with
`git log -S`, all the way back past `854f53e`). `docs/architecture_overview.md:928` asserted
that it did, which is how the belief survived unmeasured — and as of #67 that sentence is true,
which is the fix, not the evidence. It is the only one of the four with no gate,
so the number is a habit rather than a check: **measured 2026-09-02, 258 GUI `.py` files, of
which 5 exceed 500 lines** — `models/pipeline_config.py` 523, `services/case_run_note.py` 508,
`controllers/session_io_ctrl.py` 508, `services/result_legs.py` 501, `models/solver_config.py`
501. The `~` is doing real work; treat it as "split it when it grows past ~500", not as a
threshold something enforces.

---

**GUI↔C++ config parity** is gated by `tests/test_gui_cpp_config_parity.py`, and it
compares **key, TYPE and DEFAULT, in both directions** — not just key presence, which
is blind to the two divergences that produce a wrong mesh instead of an error. Both
sides are read as declarations: the C++ from `include/BLParams.hpp`'s rows plus
`Config.hpp`'s `key == "..."` branch → member → struct initialiser (a key that stops
resolving fails check 0, so a blind extractor cannot turn the comparison into a no-op),
the GUI from the derived key map + `field_spec.model_types` + `MeshConfig()` — whose own
rules moved to `.claude/rules/gui-panels-config.md` in #64. New
C++-only keys must be justified in `KNOWN_CPP_ONLY`; structural multi-token lines in
`_STRUCTURAL`. Two things about the divergence lists are load bearing:
- **`PINNED_TYPE_DIVERGENCE` is empty and must stay empty.** A type mismatch means one
  side cannot represent what the other stores, so there is no intended version of it.
  The gate found one — `BL_AUTO_FAN_NODES` — and it was FIXED, not pinned.
- **`PINNED_DEFAULT_DIVERGENCE` pins BOTH values and a reason**, because the two
  defaults answer *different questions*: the C++ one is what an unspecified key in a
  hand-written `.dat` means (neutral and safe), the GUI one is what a fresh editing
  session suggests before the user changes it. Forcing them equal would be wrong in
  both directions — it would make a new GUI case default to an all-`wall` box with no
  inlet, or make the mesher stop writing a VTK for a CLI user who asked for nothing.
  Measured: 8 of the 49 shared keys diverge, and all 8 are correct. Pinning both values
  means a *change* to either side fails the gate again, so an entry cannot absorb a new
  drift. And check 6 makes the pinning honest by machine-checking its precondition —
  the GUI must write that key **unconditionally**, so the mesher's differing default is
  never the one in force for a GUI run. That is not a formality: 7 of the writer's keys
  really are conditional.

**`app/utils.py` is the Qt side of a seam, and the pure helpers live on the other side**
(`services/paths.py`, Qt-free — `repo_root`, `find_binary_executable`,
`find_solver_executables`, `find_stl3d_binary`, `find_mpi_launcher`, `is_mpi_binary`).
`app/utils.py` re-exports the moved names, so the ~16 Qt-side call sites are untouched.
`is_headless` deliberately **stayed** with the Qt helpers. Two things the gate
(`tests/test_qt_free_seam.py`) had to learn the hard way:
- **The check must be a subprocess** — in-process the answer is always "PyQt6 is loaded"
  once any other test imported it.
- **A deferred import is still a dependency.** With the import-time sweep green,
  `run_pipeline.sh` on a PyQt6-less machine still died in stage 2: three call sites did
  `from app.utils import repo_root` *inside a function body*. The gate reads the AST for a
  moved name at **any** nesting depth, and separately refuses PyQt6 in a subprocess and
  drives the writers that failed.
The `services/` sweep is a **deny**-list (`QT_SERVICES`, each entry carrying its reason);
stale entries fail too. One pre-existing defect the sweep surfaced and did *not* fix is
recorded in `CANNOT_IMPORT_STANDALONE`: `services/index_helpers.py` cannot be imported first
(a cycle enabled by eager re-exports in two `__init__.py` files).

Scroll-wheel on QSpinBox/QDoubleSpinBox is intentionally disabled (overridden in `main.py`).

**The user-facing log is a service, not a widget**: say things with `AppController.log()`
(controllers) or `app/services/user_log.py` (views) — never `main_window.log_panel.log(...)`,
which is how 255 reach-throughs accumulated. `LogPanel` is a registered sink; sinks get the
RAW message and classify for themselves, and the durable file mirror happens in the service
ONLY (a second one in the panel writes every line twice). `user_log.log()` attaches the file
handler itself, so a process that never ran the GUI's `main()` still leaves its log on disk.
Gated by `tests/test_user_log_seam.py`. This is a different log from `get_logger(__name__)`,
which is developer diagnostics.

**User messages**: use `app/utils.py`'s graded helpers, never a raw `QMessageBox` — with
**two recorded exemptions, and no third without a helper**: `views/case_dir_dialog.py` (the
case-dir question, four mutually exclusive dispositions) and `controllers/curve_join_ctrl.py`
(keep / merge). Neither is a yes/no, and both make the headless early-return themselves. The
graded set is `report_error` (failed write, data at risk → Critical), `report_warning`
(failed read → Warning), `report_info` (a precondition, nothing broke → Information),
`confirm(..., headless_default=)` (Yes/No), and `confirm_destructive(..., action_label=,
option_label=)` (an irreversible action: a **named** button, Cancel as the default, an
optional extra tick, and **no `headless_default` at all** — a destructive prompt has no safe
default, and making it an argument would let an unattended path opt into deleting files; it
returns `None` when declined and the tick's state otherwise). A third multi-way prompt is the
point at which `app/utils.py` grows a `choose()` rather than the exemption list growing again.
All of them no-op or return the default on a headless platform. Any new dock widget needs
`setObjectName()`, or `QMainWindow.restoreState()` silently skips it.

**Signal guards**: never write a raw `blockSignals(True)`/`blockSignals(False)` pair — an exception
between them leaves the widget permanently unable to emit. Use `with block_signals(w1, w2, ...)`
(`app/utils.py`). Likewise, never assign `_is_populating`: use `with controller.populating():`, a
re-entrant depth counter (a bare bool let a nested populate clear the outer guard).
`tests/test_signal_guards.py` statically fails the build on either.

**Error handling**: never `except Exception: pass`. Use
`services/logging_setup.py::get_logger(__name__)` and log at `debug(..., exc_info=True)` for a step
allowed to fail, or `warning` when the failure silently degrades what the user asked for.
`HYBMESH_LOG_LEVEL=DEBUG` surfaces the debug tier. `tests/test_silent_exceptions.py` fails the build
if a new undocumented silent handler appears.

---

**The GUI module map** (#77). It lives behind the widest glob because it is a map rather than
a rule: every GUI reader is served by it, and the one hard rule inside it — every worker
`cancel()` routes through `stop_process` / `stop_process_async`, never a bare `terminate()` —
binds every worker. Layered PyQt6 application, `tools/PreProcessor/gui/app/`:

- **`controller.py`**: top-level orchestrator; command pattern for undo/redo, delegates to specialized controllers
- **`controllers/`**: business logic split by concern — `segment_ctrl.py` (CRUD, properties), `session_ctrl.py` (save/load), `session_io_ctrl.py` (`.hws` workspace read/write + `WORKSPACE_FORMAT_VERSION` migration), `project_state_ctrl.py` (the workspace's `project` section: Mesh/Solver/IB config + baseline-snapshot dirty detection), `backend_ctrl.py` (runs `surface_resampler` in QThread), `mesh_gen_ctrl.py` (runs `HybMesh2D` in QThread), `lifecycle_ctrl.py` (autosave, crash recovery, bounded worker shutdown), `curve_ctrl.py`, `transform_ctrl.py`
- **`models/`**: `segment.py` (`type`, `strategy`, `parameters` incl. `spacing`, curve fields, plus the two per-segment facts the MESH stage edits — `bc` and `grow_bl`; serialized via `to_dict()`/`from_dict()`, the ONE serialiser behind the resample config, the workspace and the pipeline script), `project.py`, `mesh_config.py` (+ `mesh_config_keys.py`, `mesh_config_io.py`, `mesh_output_names.py`), `session.py`, `vtk_mesh.py`, `result_data.py` / `tecplot_index.py` / `result_series.py`. Auto-split is computed in the GUI (producing explicit `split_indices`); the per-segment `auto_split`/`split_threshold` keys are read by `src/cli.cpp` for hand-written configs but are not emitted by the GUI. Exported JSON carries `format_version` (`CONFIG_FORMAT_VERSION`).
- **`views/`**: `canvas.py` (pyqtgraph interactive geometry canvas, dark theme), `mesh_canvas.py`, `main_window.py` (tab layout), `sidebar.py` (segment property editor), `panels/` (tab panels per workflow)
- **`commands/`**: `segment_cmds.py` (`UpdateSegmentStateCmd` snapshots full state dict), `split_cmds.py`, `vertex_cmds.py`, `config_cmds.py` (`UpdateProjectStateCmd`)
- **`workers/`**: `backend_run.py`, `mesh_gen_run.py` (QThread wrappers for CLI
  subprocesses), `proc_util.py` (shared `popen_kwargs()` with `start_new_session`, plus
  `stop_process`/`stop_process_async` SIGTERM→SIGKILL escalation over the child's process
  group — every worker `cancel()` must route through these, never a bare `terminate()`)

