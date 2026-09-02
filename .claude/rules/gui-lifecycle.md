---
paths:
  - tools/PreProcessor/gui/app/services/env_setup*
  - tools/PreProcessor/gui/app/services/ui_state*
  - tools/PreProcessor/gui/app/services/gui_restart*
  - tools/PreProcessor/gui/app/controllers/lifecycle_ctrl*
  - tools/PreProcessor/gui/app/views/main_window*
  - tools/PreProcessor/gui/main.py
  - tools/PreProcessor/gui/app/workers/**
  - tools/scripts/gmsh_*
---

# GUI lifecycle rules

Loaded on demand when the GUI's entry point, its main window or a main-window mixin, the
lifecycle controller, a worker, or the environment / UI-state / restart service is read —
**24 files**, verified to match. **Rules only** — the rationale (the measurements, the dated
user reports, the injections, the reversals and the named blind spots) is
`docs/design_notes/gui.md`. Read that note before overruling a rule here; when a rule
changes, update BOTH.

The concern is **the app as a process**: how it starts, what environment its subprocesses
inherit, what state survives a launch, and how it restarts. It is not the GUI's *contents* —
what a panel, a canvas or a results view does belongs to the four other GUI rule files.

**Two globs go BEYOND #77's list, and nothing is narrowed.** `tools/scripts/gmsh_*` is the
first glob pointing into `tools/scripts/`, and the first in a **GUI** rule file that leaves the
GUI tree — not, as this sentence first claimed, the first outside `tools/PreProcessor/` at all:
enumerated, `mesher.md` carries `src/**`, `include/**`, `config/**` and `tests/cpp/**`, and
`pipeline-case.md` carries `run_pipeline.sh`. The glob exists because the subprocess-environment
rule has TWO halves and the shell-side one (`gmsh_lib_dir.sh`, `gmsh_sdk_dirs.py`) is where the
"hardcoded absolute path in a discovery hint is a defect on sight" rule actually bites. And
`workers/**` is widened from #77's per-file spelling, because the SIGTERM→SIGKILL routing
rule applies to every worker's `cancel()`, not to the two the prose names.

**Also governed from OUTSIDE these globs**, which cannot hand a reader the text:
`CMakeLists.txt`, which the subprocess-environment rule rules on directly (its HINTS list is
the defect that kept CI red) and which **no glob in any rule file reaches** — the third
instance of that gap, after `services/phi_quality.py` (#66) and `tools/PreProcessor/run_batch.py`
(#67). `.github/workflows/gui-tests.yml` is the same shape; the root file's `## Build & Run`
carries what CI does. The tripwire table in `CLAUDE.md` is the only thing that reaches either.

**Boundaries run BOTH ways.**
- **Outward.** The restart rule turns on `proc_util.popen_kwargs()` being the WRONG helper
  here (it sets `stdout=PIPE`, and with the parent gone nobody drains it). `proc_util.py` is
  under `workers/**` and so is reached, but the rule that every worker `cancel()` MUST route
  through `stop_process`/`stop_process_async` is stated in the GUI module map, which lives in
  `.claude/rules/gui-seams.md`. A `proc_util.py` reader is handed both files, so both arrive —
  by the widest glob rather than by this one.
- **Inward.** `views/main_window*` matches five files, and what a main-window mixin builds —
  the toolbar's measured width, the menu bar's per-stage actions, the status bar — is not ruled
  on here. `main.py`'s scroll-wheel rule is in `gui-seams.md` for the same reason: this file
  owns the process, not the widgets.

---

**Subprocess environment**: `services/env_setup.py::mesher_env()` resolves the libgmsh
directory (override: `HYBMESH_GMSH_LIB_DIR`) and must be passed as `env=` when launching
`HybMesh2D`/`surface_resampler`. Inheriting it from a shell wrapper does **not** work —
macOS SIP strips every `DYLD_*` variable when a protected `python3` starts.
`tools/scripts/gmsh_lib_dir.sh` is the shell-side equivalent. **Where Gmsh actually is has
ONE answer: `tools/scripts/gmsh_sdk_dirs.py`** — the shell helper and `CMakeLists.txt` both
resolve through it by asking the installed wheel. The CMake side used to carry a fixed HINTS
list naming one developer's macOS pip prefix: **CI installed gmsh, failed at configure with
"Gmsh SDK not found", and because the test job is `needs: build` the entire regression suite
was SKIPPED rather than run — the workflow had never once been green.** A hardcoded absolute
path in a discovery hint is worth treating as a defect on sight. The second half was the
LIBRARY name: the Linux wheel ships `lib/libgmsh.so.4.15` with no unversioned symlink, so
`find_library`'s NAMES matched nothing there while macOS's `libgmsh.4.15.dylib` matched. The
resolver therefore reports `LIBFILE=` (the file it globbed) and CMake falls back to it. The
workflow first went green 2026-08-17 (`4254c5d`), covering **69 Python tests + `ctest` 2/2 +
the end-to-end `run_pipeline.sh`, none of which had ever executed in CI before**; four
unrelated environment defects and one flaky runner stood in the way, and not one was a defect
in the code under test. **A workflow's *history* is the only evidence it gates anything.**

**Window layout** is persisted by `app/services/ui_state.py` — **window geometry and dock state,
and nothing else** — namespaced by `LAYOUT_VERSION` (now 2; bump it when the layout changes so
stale state is ignored rather than restored). It never touches `QSettings` when headless. **The
active stage and the sidebar sections are deliberately NOT persisted, and that is a reversal, not
an omission** (#27, USER-REQUESTED): the user weighed resume-where-you-stopped against landing
somewhere unpredictable with no way to reset it, and chose predictability. Every launch starts on
**CAD** with **every** sidebar section collapsed, both from defaults already in the code
(`mode_combo` index 0; `CollapsibleSection`'s `start_collapsed=True`, which no call site
overrides). The version bump also orphans saved geometry, dock state and *dialog* accordion flags,
accepted in the issue; what it buys is that no v1 key can come back as a live value.
`restore_active_stage` and the private `_sections` walker are **gone**, save half with restore half.
**Do not reinstate the convenience as a bug fix** — `tests/test_ui_state_and_dialogs.py` checks
1/2/4 are the **inverted** versions of the ones that pinned the old behaviour. A **dialog's**
accordion is a separate, still-wanted feature with an untouched code path
(`save/restore_section_states(scope, sections)`, which never walked `sidebar_stack`).

**"⟳ Restart" closes THIS window first and spawns only if the close happened**
(`services/gui_restart.py`, Qt-free — `restart_command` / `preflight` / `launch`;
`lifecycle_ctrl.restart_gui`; the button sits beside `Run All` in the persistent tab row). #28,
USER-REQUESTED. Four rules:
- **The order IS the feature** — spawning first and *then* asking "discard unsaved changes?" leaves
  **two** GUIs running when the answer is No.
- **The outcome comes from `close()`'s return value, not from `isVisible()`.** Measured offscreen:
  a *cancelled* close on a never-shown window reports `isVisible() == False` / `isHidden() == True`,
  identical to a successful one, while `close()` returns False exactly when the event was ignored.
  The issue's own text suggests `isVisible()`; it would have made the gate pass for the wrong reason.
- **There is no second copy of the unsaved-work prompt** — the close routes through
  `MainWindow.closeEvent` → `handle_close_event`, which already covers modified sessions *and* a
  dirty Mesh/Solver/IB config, saves the layout, joins every worker, and removes the autosave file.
- **`proc_util.popen_kwargs()` must NOT be reused here** — it sets `stdout=PIPE`, and with the
  parent gone nobody drains that pipe, so the child stalls once the buffer fills. The restart builds
  its own kwargs (`start_new_session=True`, all three streams `DEVNULL`) and passes **no arguments**.
  The entry point resolves through `paths.repo_root()`, never by counting `..` segments.
`preflight()` exists because of that ordering: a bad interpreter or missing `main.py` must be caught
while there is still a window to report it in (a `Popen` failing after that can only reach
`user_log`'s file mirror). The button's **caption is a measurement living in the gate rather than a
comment** — at the 900px minimum "⟳ Restart" leaves 31px of slack in the tightest stage and
"⟳ New Session" leaves 0 — re-derived per run across **every** stage, because a tab bar is visible
in some and hidden in others. The two tab-row buttons share one QSS builder (`_tab_row_btn_qss`) for
that reason. Gated by `tests/test_gui_restart.py` (9 properties, AST-based, injection-verified).

