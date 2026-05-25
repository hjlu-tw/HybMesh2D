# Agent Handover Documentation

This document is designed to help another AI agent quickly and accurately resume/take over the development work on the HybMesh PreProcessor.

---

## ⚠️ Critical Agent Rules (from `GEMINI.md`)

- **Do NOT perform git operations (status, add, commit, etc.) automatically.** Only execute them when explicitly requested by the user.

---

## 📌 Project Overview & Current State

We have completed the refactoring and feature enhancement for the **PreProcessor GUI & C++ Resampling Backend**. The main goals achieved are:
1. **Predefined Shape Vertex snap preservation**: Snaps coordinates of shapes (Triangle, Quadrilateral, Polygon) precisely to vertex parameters, splitting them into linear edges, and distributing the point count budget proportionally by length.
2. **Auto-detect Curve Splitting**: Automatically splits custom curves into sub-polylines at sharp corners (where change of direction angle > threshold), resampling each piece independently to preserve sharp features.
3. **Persisted Sidebar Selection during Undo**: Fixed a UI bug where undoing parameter changes would reset current segment index to `-1` and collapse the property editor.
4. **General GUI Fixes**: Scroll wheel changes on numerical spin boxes are ignored (preventing accidental parameter adjustment), non-selected curve segments are drawn in muted gray, and "Duplicate with Transform" is enabled for all segment types.

---

## 🛠️ Architecture & Code Layout

### 1. C++ Backend (`tools/PreProcessor/src/main.cpp`)
- Built output executable: `build/surface_resampler`
- Key Logic:
  - **`struct ResampleTask`**: Represents a chunk of polyline points to be resampled with its allocated point count or spacing method.
  - **`splitPolyline`**: Evaluates and splits polylines at indices (used for shapes and auto-splitting).
  - **`detectFeaturePoints`**: Computes direction change angles between consecutive segments of a curve. If $\theta > \text{threshold}$, it flags a split.
  - **`alignEndpoints`**: Snaps boundary points of sub-segments to exact anchor coordinates.
  - **`distributePointsProportionally`**: Allocates the unique output point budget among the sub-tasks relative to the length of each sub-segment.

### 2. Python GUI (`tools/PreProcessor/gui/`)
- **Model (`app/models/segment.py`)**:
  - Properties `auto_split` (bool) and `split_threshold` (float) are stored and serialized in `to_dict()` and `from_dict()`.
- **Command (`app/commands/segment_cmds.py`)**:
  - `UpdateSegmentStateCmd` handles undo/redo by capturing the complete state dict of a segment and restoring it on undo/redo.
- **View (`app/views/sidebar.py`)**:
  - Adds `auto_split_cb` ("Auto Detect Segments") and `split_threshold_sb` ("Threshold") spin box inside the segment properties layout.
- **Controller (`app/controller.py`)**:
  - Synchronizes states between model and UI.
  - Fixes selection collapse: inside `_record_segment_state_change()`, the `refresh` callback restores row focus using `setCurrentRow(seg_idx)`, which prevents deselection.

---

## 🧪 Build and Verification Steps

### Build C++ backend
From the repository root `/Users/hjlu_nchc/home/NCHC/CESE/HybMesh`:
```bash
./build.sh
```
This compiles the C++ codebase, writing the output binary to `./build/surface_resampler`.

### Run Backend Resampler manually
```bash
./build/surface_resampler <config_json_path>
```
Example config files:
- `tools/PreProcessor/config/test_triangle_backend.json` (triangle verification)
- `tools/PreProcessor/config/test_auto_split.json` (L-shape feature split verification)

### Run Python Headless GUI Unit Tests
Runs the offscreen PyQt6 unit tests checking tab management, curve types, duplicates, and undo/redo operations:
```bash
python3 /Users/hjlu_nchc/.gemini/antigravity-cli/brain/123d466b-4c02-4217-8852-2f9a4c4a1277/scratch/test_gui_logic.py
```

---

## 🚀 Next Steps for Taking Over
1. Validate any new geometry models or user-requested files in the GUI.
2. If requested to perform git commits, execute `git add` and `git commit` as explicitly detailed by the user.
3. Handle any additional shape modifications or formula evaluations as requested.
