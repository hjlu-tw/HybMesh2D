"""Re-export shim for the segment commands.

The former monolithic ``segment_cmds`` module was split into three focused
modules to keep every file under the GUI file-length limit:

- ``segment_cmds_core``      — shared state helpers + lightweight/metadata cmds
- ``segment_structure_cmds`` — add/remove/duplicate/clear segment cmds
- ``segment_geometry_cmds``  — point-array-mutating split/bake cmds

This module preserves the original public import surface so existing
``from app.commands.segment_cmds import <Cmd>`` (and the ``_..._state``
helpers, imported by some consumers) keep working unchanged.
"""

from app.commands.segment_cmds_core import (
    _snapshot_full_state,
    _restore_full_state,
    _apply_segment_state,
    UpdateStrategyCmd,
    UpdateParamsCmd,
    SetClosedModeCmd,
    ToggleGlobalSplineCmd,
    ToggleMatchPreviousCmd,
    UpdateSegmentStateCmd,
    UpdateMultipleSegmentsStateCmd,
)
from app.commands.segment_structure_cmds import (
    RemoveSegmentCmd,
    AddCurveSegmentCmd,
    DuplicateTransformCmd,
    DuplicateMultipleTransformCmd,
    ClearGeometryCmd,
)
from app.commands.segment_geometry_cmds import (
    CreateSegmentsFromIndicesCmd,
    BakeCurveToGeometryCmd,
)

__all__ = [
    "_snapshot_full_state",
    "_restore_full_state",
    "_apply_segment_state",
    "UpdateStrategyCmd",
    "UpdateParamsCmd",
    "RemoveSegmentCmd",
    "AddCurveSegmentCmd",
    "SetClosedModeCmd",
    "ToggleGlobalSplineCmd",
    "ToggleMatchPreviousCmd",
    "UpdateSegmentStateCmd",
    "UpdateMultipleSegmentsStateCmd",
    "CreateSegmentsFromIndicesCmd",
    "BakeCurveToGeometryCmd",
    "DuplicateTransformCmd",
    "DuplicateMultipleTransformCmd",
    "ClearGeometryCmd",
]
