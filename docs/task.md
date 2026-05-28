# Task Checklist - PreProcessor GUI Improvements and HybMesh2D Integration

> Reference: [implementation_plan.md](file:///Users/hjlu_nchc/.gemini/antigravity-cli/brain/5d64ddd6-1ed4-44fe-b278-a6ab7959412a/implementation_plan.md)

---

# Plan A: PreProcessor GUI Bug Fixes & Refactoring

## Phase 1: Critical Bugs (8 tasks)

> All tasks are independent and can be executed separately.

- [x] **1.1** Fix `CreateSegmentsFromIndicesCmd._execute_curve_segment` overwriting split indices
  - File: `gui/app/commands/segment_cmds.py` L398-400
  - Change `self.session.split_indices = new_split_indices` to `.extend()` + `sorted(set(...))`

- [x] **1.2** Fix `RemoveSegmentCmd` index adjustment `>= del_start` to `> del_end`
  - File: `gui/app/commands/segment_cmds.py` L124-130
  - Align with `DuplicateTransformCmd` L612-617 using `> del_end`

- [x] **1.3** Fix Controller curve segment list index lookup error (global idx used as list row index)
  - File: `gui/app/controller.py` L1460-1463
  - Iterate over curve_segment_list to find the item matching UserRole (like L1082-1087)

- [x] **1.4** Fix `_record_segment_state_change` bypassing CommandHistory API
  - File: `gui/app/commands/base.py` - Add `record()` method
  - File: `gui/app/controller.py` L1273-1275 - Use `command_history.record(cmd)`

- [x] **1.5** Fix `BakeCurveToGeometryCmd` middle range index mapping error
  - File: `gui/app/commands/segment_cmds.py` L491-498
  - Separate `== s` (no change) vs `s < idx <= e` (map to end) logic

- [x] **1.6** Initialize `_active_session_id = None` in `CanvasView.__init__`
  - File: `gui/app/views/canvas.py` L29-49 - Add `self._active_session_id = None`
  - Same file L253, L278, L440 - Remove hasattr/getattr guards

- [x] **1.7** Move `_param_snapshot` and `_segment_state_snapshot` into GeometrySession
  - File: `gui/app/models/session.py` - Add snapshots
  - File: `gui/app/controller.py` - Use session.param_snapshot and session.segment_state_snapshot

- [x] **1.8** Fix closed geometry endpoint check
  - File: `gui/app/controller.py` L927-929
  - No endpoints in closed geometry, `is_endpoint` should be `False` if `is_closed` is `True`

---

## Phase 2: Major Bugs & Thread Safety (7 tasks)

> Starts after 1.1-1.8 are completed. 2.1-2.7 are independent.

- [x] **2.1** Add `is_geometry_modified` to missing commands
  - File: `gui/app/commands/split_cmds.py` - `AddSplitCmd`
  - File: `gui/app/commands/segment_cmds.py` - `UpdateStrategyCmd`, `UpdateParamsCmd`, `ToggleIsClosedCmd`, `ToggleGlobalSplineCmd`, `ToggleMatchPreviousCmd`, `UpdateSegmentStateCmd`

- [x] **2.2** Fix `RemoveSplitCmd.undo()` - Call `update_file_segments_from_indices()`
  - File: `gui/app/commands/split_cmds.py` L66-71

- [x] **2.3** Add Backend Worker concurrency check
  - File: `gui/app/controller.py` `_run_backend` method - Add `if self._worker.isRunning(): return`

- [x] **2.4** Add cancel/timeout to BackendWorker
  - File: `gui/app/workers/backend_run.py`

- [x] **2.5** Fix serialization: save formula for non-custom curves
  - File: `gui/app/models/segment.py` L94-100

- [x] **2.6** Improve `update_file_segments_from_indices` to inherit segment strategy and params
  - File: `gui/app/models/project.py` L23-44

- [x] **2.7** Add pixel distance threshold (30px) for Canvas click selection
  - File: `gui/app/views/canvas.py` L468-478

---

## Phase 3: Architecture Refactoring (5 tasks)

> Suggest order: 3.5 -> 3.4 -> 3.2 -> 3.1 -> 3.3.

- [ ] **3.5** Create `app/utils.py` and `block_signals` context manager
- [ ] **3.4** Extract index adjustment logic to helper functions
- [ ] **3.2** Eliminate Command <-> Controller circular dependencies (extract GeometryService)
- [ ] **3.1** Split Controller God Class into sub-controllers
- [ ] **3.3** Split Sidebar God Class into panels

---

## Phase 4: Code Quality & DRY (9 tasks)

- [ ] **4.1** Extract duplicate transform logic in `controller.py`
- [ ] **4.2** Extract curve type label mappings to utility dict
- [ ] **4.3** Fix `self.layout` masking `QWidget.layout()` in `log_panel.py` and `sidebar.py`
- [ ] **4.4** Update `commands/__init__.py` to export all commands
- [ ] **4.5** Clean up dead code (dead widgets, unused snapshots, redundant imports)
- [ ] **4.6** Fix PEP 8 semicolon multi-line statements in `sidebar.py`
- [ ] **4.7** Add `maxlen=MAX_DEPTH` to `_redo_stack` in `base.py`
- [ ] **4.8** Fix mouse button enum check in `canvas.py`
- [ ] **4.9** Extract duplicate "get segment points" logic in `controller.py`

---

## Phase 5: Enhancements (Recorded only, deferred)

- [ ] ~~5.1 Vectorize formula evaluation~~
- [ ] ~~5.2 MainWindow.closeEvent prompt and cleanup~~
- [ ] ~~5.3 LogPanel improvements~~
- [ ] ~~5.4 Fix versions in requirements.txt~~
- [ ] ~~5.5 Improve backend executable detection~~
- [ ] ~~5.6 Move pyqtgraph config to main.py~~
- [ ] ~~5.7 Unified stylesheet management~~
- [ ] ~~5.8 Session color counter reset~~

---

# Plan B: HybMesh2D Mesh Generator GUI Integration

## Phase B1: VTK Parser & Mesh Visualization (4 tasks)

- [ ] **B1.1** Create VTK Legacy ASCII Parser (`gui/app/models/vtk_mesh.py`)
- [ ] **B1.2** Create Mesh Canvas View (`gui/app/views/mesh_canvas.py`)
- [ ] **B1.3** Create Mesh Statistics Widget (`gui/app/views/panels/mesh_stats_panel.py`)
- [ ] **B1.4** Test: Parse and render existing VTK mesh files

## Phase B2: Background_para.dat Config Editor (4 tasks)

- [ ] **B2.1** Create MeshConfig Model (`gui/app/models/mesh_config.py`)
- [ ] **B2.2** Create Config Editor Panel (`gui/app/views/panels/mesh_config_panel.py`)
- [ ] **B2.3** Create Geometry File Selector in Config Panel
- [ ] **B2.4** Test: Load, edit, and save Background_para.dat configuration

## Phase B3: Mesh Generation Workflow (5 tasks)

- [ ] **B3.1** Create MeshGenWorker to execute HybMesh2D binary
- [ ] **B3.2** Create MeshGenController for workflow orchestration
- [ ] **B3.3** Integrate into MainWindow with Mesh Generation Mode
- [ ] **B3.4** Connect PreProcessor resampling output directly to MeshGen inputs
- [ ] **B3.5** Test: End-to-end resampling and mesh generation flow

## Phase B4: Results Management (5 tasks)

- [ ] **B4.1** Create Results Panel for output management
- [ ] **B4.2** Implement element quality visualization (aspect ratio / skewness) on Canvas
- [ ] **B4.3** Draw domain bounding box preview on Canvas
- [ ] **B4.4** Visualize boundary conditions (BC) with distinct colors
- [ ] **B4.5** Test: All visualization modes and exporting options (VTK, STAR-CD)
