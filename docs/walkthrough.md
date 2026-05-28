# Walkthrough — PreProcessor GUI Phase 1 Critical Bug Fixes

Here is a summary of the changes implemented for **Plan A Phase 1: Critical Bugs**.

## Changes Made

### 1.1 split_indices Overwrite Bug Fix
- **File**: [segment_cmds.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/commands/segment_cmds.py#L397-L401)
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
- **File**: [controller.py](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/controller.py#L927-L931)
- **Fix**: When checking whether a vertex is an endpoint, if the geometry is closed (`session.project_model.is_closed`), the check returns `False` for all points (since all points in a closed loop can be split).

---

## Verification & Testing

1. **Syntax / Compilation Check**:
   Ran python compiler check across all modified files:
   ```bash
   python3 -m py_compile tools/PreProcessor/gui/app/commands/segment_cmds.py tools/PreProcessor/gui/app/commands/base.py tools/PreProcessor/gui/app/controller.py tools/PreProcessor/gui/app/views/canvas.py tools/PreProcessor/gui/app/models/session.py
   ```
   **Result**: Checked out with zero syntax errors.
