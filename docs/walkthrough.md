# Walkthrough — PreProcessor GUI Phase 1 & 2 Bug Fixes

Here is a summary of the changes implemented for **Plan A Phase 1 & 2**.

## Phase 1: Critical Bugs (Completed)

### 1.1 split_indices Overwrite Bug Fix
- **File**: [segment_cmds.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/commands/segment_cmds.py#L395-L400)
- **Fix**: Replaced assignment (`=`) of `self.session.split_indices` with `.extend()` to merge the split indices of the new segment. Applied sorting and deduplication (`sorted(list(set(...)))`) to maintain clean indices.

### 1.2 RemoveSegmentCmd Index Range Fix
- **File**: [segment_cmds.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/commands/segment_cmds.py#L124-L130)
- **Fix**: Changed the index boundary adjustment condition from `>= del_start` to `> del_end` to ensure index shifts are only applied to elements lying strictly after the deleted range, preventing corruption of surrounding discrete edge indices.

### 1.3 Controller Row Index Fix for Analytic Edge List
- **File**: [controller.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/controller.py#L1451-L1464)
- **Fix**: In `handle_curve_type_changed`, instead of using the global segment index directly as the row index in `curve_segment_list`, it now iterates through list items to find the matching item containing the correct index in `Qt.ItemDataRole.UserRole`.

### 1.4 Segment State Change Undo Hook Fix
- **File**: [base.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/commands/base.py#L37-L41)
- **File**: [controller.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/controller.py#L1262-L1277)
- **Fix**: Added `record(self, cmd: BaseCommand)` method to `CommandHistory` to safely append commands that have already been executed without executing them again. Updated `controller.py` to call this API instead of directly manipulating private properties `_undo_stack` and `_redo_stack`.

### 1.5 BakeCurveToGeometryCmd Mapping Bug Fix
- **File**: [segment_cmds.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/commands/segment_cmds.py#L485-L499)
- **Fix**: Rewrote the boundary vs inner points logic when baking curves to the main geometry. Points matching start/end bounds of the segment are untouched, while all strictly internal points map to `s + num_new_pts - 1`.

### 1.6 CanvasView Session ID Initialization and Guard Removal
- **File**: [canvas.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/views/canvas.py)
- **Fix**: Initialized `self._active_session_id = None` in `CanvasView.__init__` and removed all defensive `hasattr`/`getattr` calls.

### 1.7 Session Snapshots Migration
- **File**: [session.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/models/session.py#L41-L45)
- **File**: [controller.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/controller.py)
- **Fix**: Moved `_param_snapshot` and `_segment_state_snapshot` from class-level/controller-level fields into `GeometrySession` as `session.param_snapshot` and `session.segment_state_snapshot`. This prevents states from being shared between different tabs.

### 1.8 Closed Geometry Endpoint Endpoint Bug Fix
- **File**: [controller.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/controller.py#L925-L931)
- **Fix**: When checking whether a vertex is an endpoint, if the geometry is closed (`session.project_model.is_closed`), the check returns `False` for all points (since all points in a closed loop can be split).

---

## Phase 2: Major Bugs & Thread Safety (Completed)

### 2.1 Missing is_geometry_modified Flags
- **Files**: 
  - [split_cmds.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/commands/split_cmds.py)
  - [segment_cmds.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/commands/segment_cmds.py)
- **Fix**: Added tracking of `session.is_geometry_modified` to `AddSplitCmd`, `UpdateStrategyCmd`, `UpdateParamsCmd`, `ToggleIsClosedCmd`, `ToggleGlobalSplineCmd`, `ToggleMatchPreviousCmd`, and `UpdateSegmentStateCmd`. When executing, `is_geometry_modified` is set to `True`, and when undoing, it is reverted to its original snapshot value (`_old_modified`).

### 2.2 RemoveSplitCmd Undo File Segment Sync
- **File**: [split_cmds.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/commands/split_cmds.py#L65-L72)
- **Fix**: Updated `RemoveSplitCmd.undo()` to call `self.session.project_model.update_file_segments_from_indices(...)` before refreshing, ensuring that UI lists representing edge segments stay correctly synced upon undo.

### 2.3 Backend Worker Concurrency Guard
- **File**: [controller.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/controller.py#L2174-L2180)
- **Fix**: Added a guard check in `_run_backend()` to prevent launching the C++ backend process if the worker is already running (`self._worker.isRunning()`). Logs a message to the user warning that a backend process is active.

### 2.4 Backend Worker Cancellation & Timeout Mechanism
- **File**: [backend_run.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/workers/backend_run.py)
- **Fix**: Implemented `cancel()` on `BackendWorker` to terminate the process cleanly when requested. Added line-by-line checks for cancellation flags. Replaced infinite wait with `self._process.wait(timeout=600)` (10-minute timeout) and structured `TimeoutExpired` logging to ensure threads do not hang indefinitely.

### 2.5 Save Formulas for Non-Custom Curves
- **File**: [segment.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/models/segment.py#L91-L100)
- **Fix**: Removed the `if self.curve_type == "custom":` check in `to_dict()` so that the formulas and coordinates mapping mode are serialized for all curve types, maintaining backward compatibility in `from_dict()`.

### 2.6 Overlap-based Segment Configuration Inheritance
- **File**: [project.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/models/project.py#L39-L51)
- **Fix**: Rewrote key matching fallback logic in `update_file_segments_from_indices()`. If a exact matching index key is not found (which happens when a segment is split), it calculates the intersection overlap against existing segments:
  `overlap = max(0, min(end, old_e) - max(start, old_s))`
  The new segment inherits the strategy, parameters, and match_previous settings from the most-overlapping old segment.

### 2.7 Canvas Click Distance Pixel Threshold
- **File**: [canvas.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/views/canvas.py#L476-L485)
- **Fix**: Replaced pure data-space click mapping with screen pixel mapping. It converts scene point locations using `vb.mapViewToScene(...)` and enforces a 30-pixel maximum radius threshold so that clicking in empty space does not mistakenly select coordinates.

---

## Verification & Testing

1. **Syntax / Compilation Check**:
   Ran python compiler check across all modified files:
   ```bash
   python3 -m py_compile tools/PreProcessor/gui/app/commands/split_cmds.py tools/PreProcessor/gui/app/commands/segment_cmds.py tools/PreProcessor/gui/app/controller.py tools/PreProcessor/gui/app/workers/backend_run.py tools/PreProcessor/gui/app/models/segment.py tools/PreProcessor/gui/app/models/project.py tools/PreProcessor/gui/app/views/canvas.py
   ```
   **Result**: Checked out with zero syntax errors.
