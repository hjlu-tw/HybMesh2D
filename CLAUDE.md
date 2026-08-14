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
python3 tools/PreProcessor/gui/main.py [geometry.dat | case.hws | pipeline.json | @list.txt ...]
```
Positional arguments are recognised by **content**, not extension — see "A path is not
a kind" under Architecture. One project file (`.hws` / pipeline script) per launch,
plus any number of geometry files; `--run` then executes Run All.

**Run preprocessor CLI (after GUI exports a JSON config):**
```bash
./run_preprocessor.sh config/your_config.json
# or directly:
./build/surface_resampler config/your_config.json
```

**Run a batch of pipeline scripts (headless):**
```bash
./run_batch.sh case_a.json case_b.hws --no-solver     # or @manifest.txt (one path per line)
```
In the GUI the same queue is **Pipeline ▸ Batch Queue…** — a modeless dialog with per-case
status. Its **Cancel stops the case already running**, not just the queue: `run_batch`'s
`should_stop()` only fires between cases, so `pipeline_runner` threads an `on_process`
callback down to every stage subprocess and the worker kills the live one via
`proc_util.stop_process_async`. Case-name collisions (which would make two cases overwrite
each other's mesh) are shown as soon as scripts are queued, not at run time.

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
- **`main.cpp`**: Entry point; parses config, loads geometries, runs collision checks, orchestrates BL + Gmsh pipeline. **`OUTPUT_FILENAME` may end in the GUI's `.*` all-formats placeholder, which is a wildcard and not an extension** — stripped once, before `validate()`/`print()`, so the banner, the provenance sidecar and every writer share one basename. Taking it literally wrote the VTK into a file *named* `mesh_<case>.*` (the export block's `extPos()` finds that dot, so `.vtk` was never appended), and before `stripExt` it did the same to STAR-CD — which is where the `results/meshes/cartesian/mesh_cartesian.*.vrt` files on disk came from. See "The Output field's `.*`" below.
- **`BoundaryLayer.cpp`**: Quad layer growth — normals, fan/parallel corner handling, concave merging, transition layers, smoothing. BL/no-BL junctions (a BL edge meeting a `grow=0` neighbour) use the angle-driven cap scheme (`BL_JUNCTION_METHOD=1`, default): the flow-facing angle θ picks case 1 (slide along the neighbour edge + absorb the no-BL nodes it covers, θ ≤ 95°), case 2/4 (perpendicular cap, 95° < θ ≤ C2 or θ > C3) or case 3 (neighbour-edge extension cap, C2 < θ ≤ C3); every cap leaves a free full-height lateral column whose edges are emitted as far-field constraints so the wedge is triangulated, and the step is scaled by 1/cos(tilt) so the *perpendicular* height is what stays fixed. **The 95° slide bound is geometric, not a knob**: a cap must point into the fluid wedge (which spans θ) while the perpendicular sits at 90°, so at θ ≤ 90° it provably exits through the no-BL wall — θ < 90° self-intersects the front (exit 5) and θ = 90° (a rectangular duct with one wall No-BL) hands Gmsh a doubled-back hole (exit 6). `C1` used to be that bound at 135°, wide enough to slide where an honest cap fit; it now only bins method 0 and round-trips through config. A slide at a **very sharp wedge** (`tan θ × BL_CONCAVE_INFLUENCE_MULTIPLIER < 1`, i.e. the corner squeezes more wall than the concave blend can lean over — 21.8° at the default 2.5, measured break between 22° and 21°) still fails downstream, so it emits `[WARN] Very sharp BL/no-BL wedge at (x, y)` naming the corner; advisory only, nothing is auto-corrected. **A case-1 slide REPLACES a stretch of the no-BL wall, so its own edges must carry that wall's BC by construction** (`slideColumns`/`slideWallRun` → `Mesh::boundaryEdgeBc`), matched to the wall edge each replacing edge covers by arc length: the column is a straight ray along the first neighbour chord, so on a *curved* no-BL wall it drifts off the wall polyline by ~a chord sagitta while `classifyBoundaryBc`'s `pointOnSegment` accepts 1e-6 of a chord (measured 6e-8..1.8e-6 vs a 2.0e-8 tolerance) — every column edge past the first fell through to `BC_GEOM`, so a No-BL inlet/outlet exported a `wall` band exactly D_total long at each BL junction and the solver ran a wall across part of the inlet. A straight no-BL wall has no drift, which is why straight-duct coverage missed it. Gated by `tests/test_nobl_junction_acute.py` (`write_curved_duct` — the curvature is the point). `=0` restores the legacy taper-to-zero (~12% floor ramping back over arc length).
- **`Mesh.cpp`**: Mesh data structure (Nodes/Elements/Edges), Gmsh far-field integration, VTK and STAR-CD export. **`FARFIELD_MESH_SIZE` is a `Min()` cap on the size field, not a target**: the field is grown from the wall (`FARFIELD_GROWTH_RATE`, from the BL front or — no BL — the geometry surface) and/or inward from the domain bounding box (`FARFIELD_GROWTH_RATE_OUTER`), so in a domain that is small relative to the growth rate it tops out below the cap and *every* larger cap gives a byte-identical mesh. Every run therefore prints a `[ Mesh Size Field ]` block reporting how high growth actually reaches, the effective ceiling, and whether the cap is dead / marginal / active — computed by re-evaluating the field expressions at the generated mesh nodes, **not** by measuring cell edges (those run ~15% long on stretched triangles and would report a dead cap as live). Gated by `tests/test_size_field_ceiling.py`. Caveat: a custom domain outline is added with `geomId = -1`, so for a pure internal-flow case (`DOMAIN_FILE … nobl`, no `GEOM_FILE`) the wall-distance field is never built and `FARFIELD_GROWTH_RATE` is inert — only `FARFIELD_GROWTH_RATE_OUTER` (distance to the *bounding box*) grades the mesh.
- **`Config.hpp`**: Single-header; parses `.dat` files into ~50 typed parameters
- **`GeomUtils.hpp`**: `Vector2D`/`Point2D`, segment intersection, normals, dot/cross products

### PreProcessor GUI (`tools/PreProcessor/gui/app/`)
Layered PyQt6 application:

- **`controller.py`**: Top-level orchestrator; command pattern for undo/redo, delegates to specialized controllers
- **`controllers/`**: Business logic split by concern — `segment_ctrl.py` (CRUD, properties), `session_ctrl.py` (save/load), `session_io_ctrl.py` (`.hws` workspace read/write + `WORKSPACE_FORMAT_VERSION` migration), `project_state_ctrl.py` (the workspace's `project` section: Mesh/Solver/IB config + baseline-snapshot dirty detection), `backend_ctrl.py` (runs `surface_resampler` in QThread), `mesh_gen_ctrl.py` (runs `HybMesh2D` in QThread), `lifecycle_ctrl.py` (autosave, crash recovery, bounded worker shutdown), `curve_ctrl.py`, `transform_ctrl.py`
- **`models/`**: `segment.py` (`type`, `strategy`, `parameters` incl. `spacing` for distance-based resampling, curve fields; serialized via `to_dict()`/`from_dict()`), `project.py`, `mesh_config.py` (+ `mesh_config_keys.py`, `mesh_config_io.py`, `mesh_output_names.py` — see "The Output field's `.*`"), `session.py`, `vtk_mesh.py`, `result_data.py` / `tecplot_index.py` / `result_series.py` (see "Transient results" below). Note: auto-split is computed in the GUI (producing explicit `split_indices`); the per-segment `auto_split`/`split_threshold` keys are read by the C++ backend (`src/main.cpp`) for hand-written/CLI configs but are not emitted by the GUI. Exported JSON carries a `format_version` field (`CONFIG_FORMAT_VERSION`).
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

**Window layout** is persisted by `app/services/ui_state.py` (geometry, dock state, active stage, collapsible sections), namespaced by `LAYOUT_VERSION` — bump it when the layout changes so stale state is ignored rather than restored. It never touches `QSettings` when headless. `restore_ui_state` only walks `sidebar_stack`, so a **dialog's** accordion persists itself through `save_section_states(scope, sections)` / `restore_section_states(...)` with an explicit scope string.

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
- **`set_result` reuses the triangulation when the incoming frame has the same
  nodes**, which also keeps probes/line/extrema alive across a step (they mark
  geometry, and the geometry did not move). Field caches are always dropped.
Frames are labelled by POSITION (`Frame 4 / 10`): the solver writes `t = "time 0"`
for *every* zone, so the file carries no real timestamp to show. Gated by
`tests/test_result_playback.py`, which pins the byte-range parse to be identical
to a whole-file scan.

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
name in the `.bnd`, and a geometry `.meta` **newer** than the mesh (per-segment
BC and No-BL flags live there, and changing one segment from inlet to outlet
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
`is_auto_output_name`, whose `<case>` naming is mirrored in `src/main.cpp`). The Mesh
panel's Output field holds ONE name for however many formats are enabled, so it is
filled in as `results/meshes/<case>/mesh_<case>.*` — and because the panel→model sync
runs on every edit, that string IS the model value and travels verbatim into the
workspace, the pipeline script and the mesher's config. Only the export dialog
understood it, in a private `endswith(".*")` branch, so: the **mesher** wrote a VTK
into a file literally named `mesh_<case>.*` (see `main.cpp` above), and
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

**A re-save of the geometry must not throw the Mesh-stage edits away**
(`meta_io.snapshot_seg_edits` / `restore_seg_edits`): both halves of a per-segment
BC live in the `.meta` — the **label** in the NSEGMENTS bc column, the label→type
map in the trailer — and the resampler REWRITES that sidecar from the CAD config
on every save. It carries the trailer through verbatim but the bc column comes
back `-` and the v3 grow column comes back 1, so a CAD tweak + Save leaves the map
pointing at labels nothing carries: the mesher warns
(`NO boundary segment carries any of the … GROUP_BC label(s)`), every patch
exports as `wall`, and the GUI still shows the BCs it holds in memory. USER-REPORTED
(2026-08-12) as "I set the BCs in Edit Seg BC, why `no boundary patch named inlet,
outlet`?". The fix is in the CALLER, not the resampler — which stopped preserving
the prior sidecar itself on purpose, because a NEW geometry written over an existing
output name then inherited the old geometry's flags (`src/main.cpp`). Only the
caller knows the file it is overwriting is the same geometry: `save_output`
snapshots **only when `project_model.output_file` already is that path**,
`_pipe_resample` / `_run_resample` because the path is the session's / script's own.
Two rules keep the restore honest: it is **refused when the segment id set changed**
(a label is bound to a segment by id, so after an edge is added or removed
re-applying by id would move the inlet onto another piece of wall) and reported as
dropped instead; and every restore is **named in the log** by BC type, since a
silent restore of the wrong thing beats nothing at all. Gated by
`tests/test_seg_edit_carryover.py`, which drives the real `surface_resampler` so
the wipe it compensates for cannot quietly stop happening.

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

### Full Pipeline (CAD → mesh → solver → results, one action)
A single unified JSON script drives the whole chain; the GUI and the headless CLI share the same schema and stage logic.
- **`models/pipeline_config.py`** (`PipelineConfig`, Qt-free): the unified schema (`cads`/`mesh`/`solver`/`stl3d`/`results`, each mapping 1:1 onto `ProjectModel`/`MeshConfig`/`SolverConfig`/`Stl3dConfig`) + converters. `PIPELINE_FORMAT_VERSION` (v2). `cads` is a **list** — one entry per geometry, so a multi-body case round-trips; the singular `cad` key is still read and exposed as a property (first entry) for pre-v2 scripts. `from_workspace_dict()` turns a `.hws` workspace into a runnable script, so `run_pipeline.sh` accepts either. Examples: `config/pipeline/naca_demo.json` (single), `multi_element_demo.json` (multi-body).
- **`services/pipeline_runner.py`** (Qt-free, blocking): runs the 3 CLI stages via subprocess (surface_resampler → HybMesh2D → getPGrid→unicones); `run_pipeline()` returns the produced artifact paths.
- **`services/solver_case.py`** (Qt-free): case-dir orchestration (`results/solver/<name>/{work,grid,dll}`), extracted so `solver_ctrl._prepare_case_dir` and the headless runner share one source of truth. **The grid stem is the RESOLVED case name, not the requested one**: auto-versioning renames the *directory* (`case` → `case_002`), and a stem left on the pre-version name writes `case.grid` into `case_002/`. That runs — `input.in` names the file it just wrote — so it stays invisible until the user later types the versioned name by hand and the same directory ends up holding `case.grid` *and* `case_002.grid`, two 1.3 MB grids distinguishable only by which one `input.in` references. USER-REPORTED (2026-08-13).
- **`services/case_sources.py`** (Qt-free): copies the CAD/STL a case was cut from into **`grid/cad/`**, so the case describes its own geometry instead of only the mesh (the source otherwise lives in `examples/geometries/` or a Desktop, free to be edited or deleted while the case looks complete). Fed by `solver_ctrl._case_source_files` / `_case_generated_files` and `pipeline_runner._case_sources` — the imported source, the resampled `.dat` the mesher read, the immersed STL, the mesh `.provenance.json`, and the **mesh parameter file**, which is *generated* rather than copied because the GUI only ever materialises one in `temp_dir` and deletes it on exit (`mesh_config_io.config_to_text`, split out of `save_config_to_file` so the staged config is byte-identical to a hand-saved one; it takes the destination path because a geometry outside the repo is emitted relative to the config file). Rules: **copy, never move** (the mesher, the GUI session and other cases still point at the original — and a *move* is unimplementable anyway, since one resampled `.dat` legitimately feeds several cases and the pipeline is not one-directional); **a hard link is not the cheap version of a copy** — one inode means editing the CAD afterwards silently rewrites what the case holds, which is the property the copy exists to deny; **sidecars follow their file** (`<name>.dat.meta` carries the per-segment BC labels and No-BL flags, so the `.dat` without it is a different geometry); **collisions are renamed, not overwritten** (two bodies can both be `profile.dat`); generated files are staged **last** and marked `(generated)` in the index, because a reconstruction must not read as evidence. `SOURCES.txt` maps every staged name back to its absolute origin, rewritten in full each run so a body no longer in the case leaves no line — and it is the *only* index there is, so **`tools/scripts/case_sources_index.py`** reads them back to answer the question the case dir cannot ("if I change this CAD, which cases go stale?"), matching by `(st_dev, st_ino)` then path then substring, exit 1 on no match. `case_export` descends into `grid/cad/` with its own allow-list — a nested folder the exporter cannot see is neither shipped *nor named as skipped*.
- **`services/stl3d_case.py`** (Qt-free): the same for the immersed-solid stage — `validate()`, `work_dir_for()`, `prepare_case_dir()` (stages the STL under a whitespace-safe name + writes `para.in`). Both `stl3d_ctrl.run_stl3d` and the headless runner's IB stage go through it. **`Stl3dConfig.para_in_text()` must match `solver/preprocess/STL3d/src/stl3d.cpp`'s `cin >>` sequence line for line** — there are five reads and deliberately no ascii y/n line (the binary auto-detects); an extra line is consumed as the case name and the run silently produces an empty phi field with exit code 0. `tests/test_stl3d_case_parity.py` parses the C++ and gates this. **Inside `stl3d.cpp`, `STLobject` carries two different x extents and they must not be confused**: `xloc_db` (the candidate index `trace_ray` looks rays up in) is keyed by element **centre** x, while `xmin`/`xmax` (the ray culling window) come from the **vertices** — and have to, since a centroid sits strictly inside the surface and a centre-based box clips whole regions off a coarse or fan-shaped tessellation. Every ray in the strip between the last centre and `xmax` therefore passes the culling check with nothing at or after it in the index, so `lower_bound()` returns `end()`; dereferencing that (`->second->second`) is what killed a GUI IB run with `[STL3d] exited with code -11`. A **flat 2D profile is the worst case** — an ear-clipped/fan triangulation drags every centroid toward the apex, leaving the far ~20-30% of the x extent centroid-free (measured 5.856 vs 6.070, i.e. the last 41 of 128 slices). `ctr_strip_at_or_after()` clamps instead: a range *start* falls back to the last strip, a range *end* to `ctr_db_.end()`, so the far strip is really traced rather than silently clipped. Gated by `tests/test_stl3d_flat_profile_trace.py`, which compiles `stl3d.cpp` itself (CI does not build STL3d, and a stale binary must not be able to pass it).
- **`services/contour_render.py`** (Qt-free): renders a Tecplot result to a contour PNG (matplotlib Agg) for headless runs.
- **`controllers/pipeline_ctrl.py`** (`PipelineControllerMixin`): GUI **Run All** — chains the existing per-stage QThread workers on their `finished_signal` (batch mode: no per-stage dialogs), ending on the auto-loaded Results contour. Also Save/Load pipeline script.
- **`tools/PreProcessor/run_pipeline.py`** + **`run_pipeline.sh`**: headless entry point (`--no-solver`, `--no-contour`, `--png`).

### Visualization (`tools/scripts/`)
- **`visualize_dat.py`**: Matplotlib visualization for `.dat` files; `--quality` flag adds expansion-ratio heatmap
- **`generate_letters.py`**: Generates letter-shaped geometry files
- **`case_sources_index.py`**: which solver cases were built from which geometry (reads every `results/solver/*/grid/cad/SOURCES.txt`). No argument lists every case; an argument (path or partial name) answers "if I change this CAD, which cases go stale?" and exits 1 when nothing matches.

## Common Tasks

- **Add a spacing strategy**: Edit `tools/PreProcessor/include/Spacing.hpp`
- **Modify BL generation**: Edit `src/BoundaryLayer.cpp`
- **Add a geometry/curve type**: Add `curve_type` handler in `tools/PreProcessor/src/main.cpp`
- **Change canvas colors**: Update color constants near the top of `tools/PreProcessor/gui/app/views/canvas.py`
- **Add a config parameter**: Add field to `include/Config.hpp` and parse it in the `loadConfig()` block
- **Add a GUI undo-able action**: Create a new `Command` subclass in `tools/PreProcessor/gui/app/commands/` and dispatch it through `controller.py`
