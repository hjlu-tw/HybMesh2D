# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important: Git and Commit Policy

**NEVER execute git commands or commit changes automatically.** Always wait for explicit user instructions before performing git operations (git status, git add, git commit, git push, etc.).

## Project Overview

HybMesh2D is a C++ tool for generating 2D hybrid meshes (boundary layer quads + far-field triangles) for CFD. It includes a Python GUI for pre-processing geometry via resampling and segmentation.

## Build & Run

**Compile both binaries:**
```bash
./build.sh
```
Outputs: `./build/HybMesh2D` and `./build/surface_resampler`

**Run main mesh generator:**
```bash
./run.sh -conf config/Background_para.dat -geom examples/geometries/naca0012.dat
```
`run.sh` sets the Gmsh dylib path (`DYLD_LIBRARY_PATH`) before invoking `./build/HybMesh2D`.

**Run preprocessor GUI:**
```bash
python3 tools/PreProcessor/gui/main.py [optional_geometry_file]
```

**Run preprocessor CLI (after GUI exports a JSON config):**
```bash
./run_preprocessor.sh config/your_config.json
# or directly:
./build/surface_resampler config/your_config.json
```

**Run full pipeline (CAD → mesh → solver → contour) headless from one JSON script:**
```bash
./run_pipeline.sh config/pipeline/naca_demo.json           # -> results/pipeline/*.png
./run_pipeline.sh config/pipeline/naca_demo.json --no-solver   # stop after meshing
```
`run_pipeline.sh` sets `DYLD_LIBRARY_PATH` (like `run.sh`) and calls `tools/PreProcessor/run_pipeline.py`. In the GUI, the same end-to-end run is the **Run All** button (top-right, all modes) / **Pipeline** menu (Run / Load / Save script). See the "Full Pipeline" section under Architecture.

**Visualize .dat files:**
```bash
python3 tools/scripts/visualize_dat.py <path_to_dat_file> [--config <json_config>] [--quality]
```
`--quality` renders a heatmap of expansion ratio: green < 1.05, orange 1.05–1.2, red > 1.2.

**Lint (what CI enforces):**
```bash
cd tools/PreProcessor/gui && ruff check .            # config: ruff.toml
cd tools/PreProcessor/gui && ruff check --config ruff.toml ../tests
```
`ruff.toml` enforces only real-defect rules (`E9`, `F`); style rules are off with the reason stated in the file. Fix violations before adding a rule to `select` — a permanently-red gate is worse than none. CI (`.github/workflows/gui-tests.yml`) has three jobs: **lint**, **build C++ with `-Werror`**, and **test** (which `needs: build`, so the binary-dependent tests actually run instead of self-skipping, plus an end-to-end `run_pipeline.sh`).

**GUI↔C++ config parity** is gated by `tests/test_gui_cpp_config_parity.py`: it statically compares the keys `models/mesh_config_io.py` writes against the `key == "..."` branches in `include/Config.hpp`. A key the GUI writes but the C++ ignores means the user's setting silently does nothing. New C++-only keys must be justified in that test's `KNOWN_CPP_ONLY`.

**Example backend test configs:**
- `tools/PreProcessor/config/test_triangle_backend.json` — vertex snap verification
- `tools/PreProcessor/config/test_auto_split.json` — feature split verification

## Mesh Generation Pipeline

```
Input: .dat geometry file (space-separated x y coordinates per line)
  ↓
[Optional] PreProcessor (GUI or CLI)
  - Resamples surface points with chosen spacing strategy
  - Preserves predefined shape vertices (Triangle/Quad/Polygon vertex snap)
  - Auto-splits at sharp corners (direction change > threshold)
  - Output: resampled .dat geometry
  ↓
BoundaryLayer.cpp — grows structured quad layers outward from geometry
  - Computes outward normals per node
  - Fans at convex corners (angle > BL_FAN_ANGLE_THRESHOLD)
  - Merges or blends at concave corners (configurable method)
  - Transition layers with separate growth rate
  ↓
Mesh.cpp / Gmsh SDK — fills far-field with unstructured triangles
  - BL outer edge becomes inner boundary of Gmsh domain
  - Starting mesh size derived from last BL layer thickness
  ↓
Collision detection → Laplacian smoothing (BFS region around frozen nodes)
  ↓
Export: VTK (.vtk) and/or STAR-CD (.vrt / .cel / .bnd)
```

## Configuration

### .dat Config Format (`config/Background_para.dat`)
Key-value text file, command-line args override file values. Parameters grouped by function:

| Group | Key examples |
|-------|-------------|
| Domain | `DOMAIN_X_MIN/MAX`, `DOMAIN_Y_MIN/MAX` |
| Surface | `SURFACE_MESH_SIZE`, `AUTO_SURFACE_SIZE` |
| BL Core | `BL_INITIAL_THICKNESS`, `BL_GROWTH_RATE`, `BL_LAYERS` |
| Corners | `BL_FAN_NODES`, `BL_AUTO_FAN_NODES`, `BL_FAN_ANGLE_THRESHOLD`, `BL_CONVEX_METHOD` |
| Concave | `BL_CONCAVE_METHOD`, `BL_CONCAVE_ANGLE_THRESHOLD`, `BL_SMOOTHING_ITERS` |
| BL/no-BL Junction | `BL_JUNCTION_METHOD` (0=taper-to-zero legacy, 1=4-case angle-driven, default), `BL_JUNCTION_ANGLE_C1/C2/C3` (°) |
| Transition | `BL_TRANSITION_LAYERS`, `BL_TRANSITION_GROWTH_RATE`, `BL_TRANSITION_BUFFER` |
| Gmsh | `GMSH_ALGORITHM` (6=Frontal-Delaunay), `GMSH_OPTIMIZE`, `FARFIELD_GROWTH_RATE`, `FARFIELD_MESH_SIZE` |
| Output | `EXPORT_VTK`, `EXPORT_STARCD`, `BC_XMIN/XMAX/YMIN/YMAX/GEOM` |
| Units | `LENGTH_UNIT` (m/cm/mm/um/in/ft/custom), `LENGTH_UNIT_METRES`, `LENGTH_UNIT_NAME` |

### PreProcessor JSON Config
JSON format; supports multi-element definitions with transforms (scale/rotate/translate), per-segment spacing strategy, and auto-split threshold. See `tools/PreProcessor/config/` for examples.

## Architecture

### Core C++ (`src/`, `include/`)
- **`main.cpp`**: Entry point; parses config, loads geometries, runs collision checks, orchestrates BL + Gmsh pipeline
- **`BoundaryLayer.cpp`**: Quad layer growth — normals, fan/parallel corner handling, concave merging, transition layers, smoothing. BL/no-BL junctions (a BL edge meeting a `grow=0` neighbour) use the 4-case angle-driven scheme (`BL_JUNCTION_METHOD=1`, default): the flow-facing angle θ picks case 1 (concave slide along the neighbour edge + concave blend + absorb), 2/4 (perpendicular cap), or 3 (neighbour-edge extension cap); cases 2/3/4 leave a free full-height lateral cap column whose edges are emitted as far-field constraints so the wedge is triangulated. `=0` restores the legacy taper-to-zero.
- **`Mesh.cpp`**: Mesh data structure (Nodes/Elements/Edges), Gmsh far-field integration, VTK and STAR-CD export
- **`Config.hpp`**: Single-header; parses `.dat` files into ~50 typed parameters
- **`GeomUtils.hpp`**: `Vector2D`/`Point2D`, segment intersection, normals, dot/cross products

### PreProcessor GUI (`tools/PreProcessor/gui/app/`)
Layered PyQt6 application:

- **`controller.py`**: Top-level orchestrator; command pattern for undo/redo, delegates to specialized controllers
- **`controllers/`**: Business logic split by concern — `segment_ctrl.py` (CRUD, properties), `session_ctrl.py` (save/load), `session_io_ctrl.py` (`.hws` workspace read/write + `WORKSPACE_FORMAT_VERSION` migration), `project_state_ctrl.py` (the workspace's `project` section: Mesh/Solver/IB config + baseline-snapshot dirty detection), `backend_ctrl.py` (runs `surface_resampler` in QThread), `mesh_gen_ctrl.py` (runs `HybMesh2D` in QThread), `lifecycle_ctrl.py` (autosave, crash recovery, bounded worker shutdown), `curve_ctrl.py`, `transform_ctrl.py`
- **`models/`**: `segment.py` (`type`, `strategy`, `parameters` incl. `spacing` for distance-based resampling, curve fields; serialized via `to_dict()`/`from_dict()`), `project.py`, `mesh_config.py`, `session.py`, `vtk_mesh.py`. Note: auto-split is computed in the GUI (producing explicit `split_indices`); the per-segment `auto_split`/`split_threshold` keys are read by the C++ backend (`src/main.cpp`) for hand-written/CLI configs but are not emitted by the GUI. Exported JSON carries a `format_version` field (`CONFIG_FORMAT_VERSION`).
- **`views/`**: `canvas.py` (pyqtgraph interactive geometry canvas, dark theme), `mesh_canvas.py` (mesh visualization), `main_window.py` (tab layout), `sidebar.py` (segment property editor), `panels/` (tab panels per workflow)
- **`commands/`**: `segment_cmds.py` (`UpdateSegmentStateCmd` snapshots full state dict), `split_cmds.py`, `vertex_cmds.py`, `config_cmds.py` (`UpdateProjectStateCmd` — snapshot of the Mesh/Solver/IB configuration)

**Undo is global, across every CAD session AND project settings** (`controllers/undo_ctrl.py`). Histories stay per-`GeometrySession` (plus `controller.project_history`) so closing a tab drops exactly its own commands; ordering across them is by the monotonic `seq` that `CommandHistory._push` stamps — undo takes the highest, redo the lowest waiting on a redo stack. Undo raises the tab owning the command before applying it. Mesh/Solver/IB edits are recorded by debounced snapshot diffing, so a burst of typing is one step. **Any code pushing config into those panels must go through `controller.push_panel_config(panel, cfg)`** (or `suppress_project_undo()`), or the push is recorded as a user edit.
- **`workers/`**: `backend_run.py`, `mesh_gen_run.py` (QThread wrappers for CLI subprocesses), `proc_util.py` (shared `popen_kwargs()` with `start_new_session`, plus `stop_process`/`stop_process_async` SIGTERM→SIGKILL escalation over the child's process group — every worker `cancel()` must route through these, never a bare `terminate()`)

**Subprocess environment**: `services/env_setup.py::mesher_env()` resolves the libgmsh directory (override: `HYBMESH_GMSH_LIB_DIR`) and must be passed as `env=` when launching `HybMesh2D`/`surface_resampler`. Inheriting it from a shell wrapper does **not** work — macOS SIP strips every `DYLD_*` variable when a protected `python3` starts, so `run.sh`'s export never reaches a Python-launched child. `tools/scripts/gmsh_lib_dir.sh` is the shell-side equivalent, sourced by `run.sh`/`run_pipeline.sh`.

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

**User messages**: use `app/utils.py`'s graded helpers, never a raw `QMessageBox` call — `report_error` (failed write, data at risk → Critical), `report_warning` (failed read → Warning), `report_info` (a precondition, nothing broke → Information), `confirm(..., headless_default=)` (Yes/No). All of them no-op or return the default on a headless platform, which is what keeps tests, CI and the headless pipeline from hanging on a modal. Any new dock widget needs `setObjectName()`, or `QMainWindow.restoreState()` silently skips it.

**Window layout** is persisted by `app/services/ui_state.py` (geometry, dock state, active stage, collapsible sections), namespaced by `LAYOUT_VERSION` — bump it when the layout changes so stale state is ignored rather than restored. It never touches `QSettings` when headless.

**Signal guards**: never write a raw `blockSignals(True)`/`blockSignals(False)` pair — an exception between them leaves the widget permanently unable to emit. Use `with block_signals(w1, w2, ...)` (`app/utils.py`). Likewise, never assign `_is_populating`: use `with controller.populating():`, which is a re-entrant depth counter (a bare bool let a nested populate clear the outer guard). `tests/test_signal_guards.py` statically fails the build on either.

**Error handling**: never `except Exception: pass`. Use `services/logging_setup.py::get_logger(__name__)` and log at `debug(..., exc_info=True)` for a step allowed to fail, or `warning` when the failure silently degrades what the user asked for. `HYBMESH_LOG_LEVEL=DEBUG` surfaces the debug tier. `tests/test_silent_exceptions.py` fails the build if a new undocumented silent handler appears.

### PreProcessor CLI (`tools/PreProcessor/src/main.cpp`)
- Reads JSON config via `nlohmann/json.hpp` (header-only, bundled)
- `detectFeaturePoints()` → `splitPolyline()` → `alignEndpoints()` → `distributePointsProportionally()`
- Spacing strategies: `uniform`, `curvature`, `cosine` (double-end dense), `geometric` (exponential), `tanh`
- Supporting headers in `tools/PreProcessor/include/`: `Spline.hpp` (cubic spline), `Spacing.hpp`, `Quality.hpp`

### Full Pipeline (CAD → mesh → solver → results, one action)
A single unified JSON script drives the whole chain; the GUI and the headless CLI share the same schema and stage logic.
- **`models/pipeline_config.py`** (`PipelineConfig`, Qt-free): the unified schema (`cads`/`mesh`/`solver`/`stl3d`/`results`, each mapping 1:1 onto `ProjectModel`/`MeshConfig`/`SolverConfig`/`Stl3dConfig`) + converters. `PIPELINE_FORMAT_VERSION` (v2). `cads` is a **list** — one entry per geometry, so a multi-body case round-trips; the singular `cad` key is still read and exposed as a property (first entry) for pre-v2 scripts. `from_workspace_dict()` turns a `.hws` workspace into a runnable script, so `run_pipeline.sh` accepts either. Examples: `config/pipeline/naca_demo.json` (single), `multi_element_demo.json` (multi-body).
- **`services/pipeline_runner.py`** (Qt-free, blocking): runs the 3 CLI stages via subprocess (surface_resampler → HybMesh2D → getPGrid→unicones); `run_pipeline()` returns the produced artifact paths.
- **`services/solver_case.py`** (Qt-free): case-dir orchestration (`results/solver/<name>/{work,grid,dll}`), extracted so `solver_ctrl._prepare_case_dir` and the headless runner share one source of truth.
- **`services/stl3d_case.py`** (Qt-free): the same for the immersed-solid stage — `validate()`, `work_dir_for()`, `prepare_case_dir()` (stages the STL under a whitespace-safe name + writes `para.in`). Both `stl3d_ctrl.run_stl3d` and the headless runner's IB stage go through it. **`Stl3dConfig.para_in_text()` must match `solver/preprocess/STL3d/src/stl3d.cpp`'s `cin >>` sequence line for line** — there are five reads and deliberately no ascii y/n line (the binary auto-detects); an extra line is consumed as the case name and the run silently produces an empty phi field with exit code 0. `tests/test_stl3d_case_parity.py` parses the C++ and gates this.
- **`services/contour_render.py`** (Qt-free): renders a Tecplot result to a contour PNG (matplotlib Agg) for headless runs.
- **`controllers/pipeline_ctrl.py`** (`PipelineControllerMixin`): GUI **Run All** — chains the existing per-stage QThread workers on their `finished_signal` (batch mode: no per-stage dialogs), ending on the auto-loaded Results contour. Also Save/Load pipeline script.
- **`tools/PreProcessor/run_pipeline.py`** + **`run_pipeline.sh`**: headless entry point (`--no-solver`, `--no-contour`, `--png`).

### Visualization (`tools/scripts/`)
- **`visualize_dat.py`**: Matplotlib visualization for `.dat` files; `--quality` flag adds expansion-ratio heatmap
- **`generate_letters.py`**: Generates letter-shaped geometry files

## Common Tasks

- **Add a spacing strategy**: Edit `tools/PreProcessor/include/Spacing.hpp`
- **Modify BL generation**: Edit `src/BoundaryLayer.cpp`
- **Add a geometry/curve type**: Add `curve_type` handler in `tools/PreProcessor/src/main.cpp`
- **Change canvas colors**: Update color constants near the top of `tools/PreProcessor/gui/app/views/canvas.py`
- **Add a config parameter**: Add field to `include/Config.hpp` and parse it in the `loadConfig()` block
- **Add a GUI undo-able action**: Create a new `Command` subclass in `tools/PreProcessor/gui/app/commands/` and dispatch it through `controller.py`
