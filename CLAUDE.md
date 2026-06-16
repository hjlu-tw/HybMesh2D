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

**Visualize .dat files:**
```bash
python3 tools/scripts/visualize_dat.py <path_to_dat_file> [--config <json_config>] [--quality]
```
`--quality` renders a heatmap of expansion ratio: green < 1.05, orange 1.05–1.2, red > 1.2.

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
| Transition | `BL_TRANSITION_LAYERS`, `BL_TRANSITION_GROWTH_RATE`, `BL_TRANSITION_BUFFER` |
| Gmsh | `GMSH_ALGORITHM` (6=Frontal-Delaunay), `GMSH_OPTIMIZE`, `FARFIELD_GROWTH_RATE`, `FARFIELD_MESH_SIZE` |
| Output | `EXPORT_VTK`, `EXPORT_STARCD`, `BC_XMIN/XMAX/YMIN/YMAX/GEOM` |

### PreProcessor JSON Config
JSON format; supports multi-element definitions with transforms (scale/rotate/translate), per-segment spacing strategy, and auto-split threshold. See `tools/PreProcessor/config/` for examples.

## Architecture

### Core C++ (`src/`, `include/`)
- **`main.cpp`**: Entry point; parses config, loads geometries, runs collision checks, orchestrates BL + Gmsh pipeline
- **`BoundaryLayer.cpp`**: Quad layer growth — normals, fan/parallel corner handling, concave merging, transition layers, smoothing
- **`Mesh.cpp`**: Mesh data structure (Nodes/Elements/Edges), Gmsh far-field integration, VTK and STAR-CD export
- **`Config.hpp`**: Single-header; parses `.dat` files into ~50 typed parameters
- **`GeomUtils.hpp`**: `Vector2D`/`Point2D`, segment intersection, normals, dot/cross products

### PreProcessor GUI (`tools/PreProcessor/gui/app/`)
Layered PyQt6 application:

- **`controller.py`**: Top-level orchestrator; command pattern for undo/redo, delegates to specialized controllers
- **`controllers/`**: Business logic split by concern — `segment_ctrl.py` (CRUD, properties), `session_ctrl.py` (save/load), `backend_ctrl.py` (runs `surface_resampler` in QThread), `mesh_gen_ctrl.py` (runs `HybMesh2D` in QThread), `curve_ctrl.py`, `transform_ctrl.py`
- **`models/`**: `segment.py` (`type`, `strategy`, `parameters` incl. `spacing` for distance-based resampling, curve fields; serialized via `to_dict()`/`from_dict()`), `project.py`, `mesh_config.py`, `session.py`, `vtk_mesh.py`. Note: auto-split is computed in the GUI (producing explicit `split_indices`); the per-segment `auto_split`/`split_threshold` keys are read by the C++ backend (`src/main.cpp`) for hand-written/CLI configs but are not emitted by the GUI. Exported JSON carries a `format_version` field (`CONFIG_FORMAT_VERSION`).
- **`views/`**: `canvas.py` (pyqtgraph interactive geometry canvas, dark theme), `mesh_canvas.py` (mesh visualization), `main_window.py` (tab layout), `sidebar.py` (segment property editor), `panels/` (tab panels per workflow)
- **`commands/`**: `segment_cmds.py` (`UpdateSegmentStateCmd` snapshots full state dict), `split_cmds.py`, `vertex_cmds.py`
- **`workers/`**: `backend_run.py`, `mesh_gen_run.py` (QThread wrappers for CLI subprocesses)

Scroll-wheel on QSpinBox/QDoubleSpinBox is intentionally disabled (overridden in `main.py`).

### PreProcessor CLI (`tools/PreProcessor/src/main.cpp`)
- Reads JSON config via `nlohmann/json.hpp` (header-only, bundled)
- `detectFeaturePoints()` → `splitPolyline()` → `alignEndpoints()` → `distributePointsProportionally()`
- Spacing strategies: `uniform`, `curvature`, `cosine` (double-end dense), `geometric` (exponential), `tanh`
- Supporting headers in `tools/PreProcessor/include/`: `Spline.hpp` (cubic spline), `Spacing.hpp`, `Quality.hpp`

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
