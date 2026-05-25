# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important: Git and Commit Policy

**NEVER execute git commands or commit changes automatically.** Always wait for explicit user instructions before performing git operations (git status, git add, git commit, git push, etc.).

## Project Overview

HybMesh2D is a C++ tool for generating 2D hybrid meshes (boundary layer quads + far-field triangles) for CFD. It includes a Python GUI for pre-processing geometry via resampling and segmentation.

## Recent Refactoring (Completed)

The following features were recently implemented in the PreProcessor GUI & C++ Backend:

1. **Predefined Shape Vertex Snap Preservation**: Triangle, Quadrilateral, Polygon shapes snap coordinates precisely to vertex parameters, splitting into linear edges and distributing point count budget proportionally by length.
2. **Auto-detect Curve Splitting**: Automatically splits custom curves into sub-polylines at sharp corners (direction change angle > threshold).
3. **Persisted Sidebar Selection during Undo**: Fixed bug where undoing parameter changes would reset segment index to `-1` and collapse property editor.
4. **GUI Fixes**: Scroll wheel on numerical spin boxes ignored, non-selected segments drawn in muted gray, "Duplicate with Transform" enabled for all segment types.

## Build & Run

**Compile:**
```bash
./build.sh
```

**Run main mesh generator:**
```bash
./run.sh -conf config/Background_para.dat -geom examples/geometries/naca0012.dat
```

**Run preprocessor GUI:**
```bash
python3 tools/PreProcessor/gui/main.py
```

**Run preprocessor GUI with geometry file loaded:**
```bash
python3 tools/PreProcessor/gui/main.py <geometry_file>
```

**Run preprocessor CLI (after GUI creates config):**
```bash
./run_preprocessor.sh config/your_config.json
```

**Visualize .dat files:**
```bash
python3 tools/scripts/visualize_dat.py <path_to_dat_file> [--config <json_config>] [--quality]
```

The `--quality` flag enables a heatmap visualization of expansion ratio (green < 1.05, orange 1.05-1.2, red > 1.2).

## Architecture

### Core C++ (`src/`, `include/`)
- **`main.cpp`**: Entry point, parses config, loads geometries, handles collision detection, orchestrates mesh generation pipeline
- **`Mesh.cpp`**: Mesh data structure (Nodes, Elements, Edges), Cartesian mesh generation, Gmsh far-field generation, VTK/STAR-CD export
- **`BoundaryLayer.cpp`**: Boundary layer generator advancing from wall toward far-field
- **`Config.hpp`**: Single-header config loading from `.dat` files with ~50 parameters for BL thickness, growth rate, corner handling, Gmsh settings
- **`GeomUtils.hpp`**: Basic 2D geometry utilities (Vector2D/Point2D, segment intersection, cross/dot products, normal vectors)

### PreProcessor GUI (`tools/PreProcessor/gui/app/`)
- **`controller.py`**: Main controller (~85KB) using command pattern for undo/redo; manages sessions, canvas rendering, and backend worker communication. Key fix: `_record_segment_state_change()` uses `setCurrentRow(seg_idx)` in refresh callback to prevent selection collapse.
- **`views/canvas.py`**: pyqtgraph-based interactive canvas with dark theme; displays multiple geometries simultaneously, overlays for active segments, split points, quality indicators
- **`models/segment.py`**: Segment model with properties `auto_split` (bool) and `split_threshold` (float); stored in `to_dict()`/`from_dict()`
- **`views/sidebar.py`**: Segment property editor with `auto_split_cb` and `split_threshold_sb` controls
- **`workers/backend_run.py`**: QThread for running `surface_resampler` CLI asynchronously
- **`commands/`**: Command classes for undo/redo (split management, segment updates, vertex insertion)
- **`commands/segment_cmds.py`**: `UpdateSegmentStateCmd` handles undo/redo by capturing complete segment state dict

### PreProcessor CLI (`tools/PreProcessor/src/main.cpp`)
- Parses JSON configs with `nlohmann/json.hpp`
- **`struct ResampleTask`**: Represents a chunk of polyline points to be resampled with allocated point count or spacing method
- **`detectFeaturePoints`**: Computes direction change angles; flags split when angle > threshold
- **`splitPolyline`**: Splits polylines at specified indices
- **`alignEndpoints`**: Snaps boundary points to exact anchor coordinates
- **`distributePointsProportionally`**: Allocates point budget among sub-tasks relative to length
- Supports file segments and curve segments (line, circle, polygon, custom formulas with x_formula/y_formula)
- **Vertex-pinned resampling**: guarantees all original vertices are preserved in output
- Implements spacing strategies: uniform, curvature-based, cosine (double-end dense), geometric (exponential), tanh
- Quality analysis for expansion ratio monitoring

### Visualization (`tools/scripts/`)
- **`visualize_dat.py`**: Matplotlib-based visualization for .dat files with quality heatmap mode
- **`generate_letters.py`**: Utility for generating letter geometries

## Testing & Verification

### Build C++ backend
```bash
./build.sh
```
Output binary: `./build/surface_resampler`

### Run Backend Resampler manually
```bash
./build/surface_resampler <config_json_path>
```
Example configs:
- `tools/PreProcessor/config/test_triangle_backend.json` (vertex snap verification)
- `tools/PreProcessor/config/test_auto_split.json` (feature split verification)

### Run Python Headless GUI Unit Tests
```bash
python3 /Users/hjlu_nchc/.gemini/antigravity-cli/brain/123d466b-4c02-4217-8852-2f9a4c4a1277/scratch/test_gui_logic.py
```

## Common Tasks

- **Add a new spacing strategy**: Edit `Spacing.hpp/cpp` in PreProcessor/include
- **Modify boundary layer generation**: Edit `BoundaryLayer.cpp`
- **Change canvas appearance**: Update color constants in `views/canvas.py` (lines 9-18)
- **Add new geometry type**: Add curve_type handler in `tools/PreProcessor/src/main.cpp`
- **Modify visualization colors**: Edit `tools/scripts/visualize_dat.py` lines 184-185
