"""Pop-up dialog widgets and boundary-layer field specs for the mesh config
panel. This module is now a thin re-export shim: the implementations live in
``mesh_dialogs_bl.py`` (boundary-layer field specs + BL dialogs) and
``mesh_dialogs_bc.py`` (BC-type / patch dialogs). Existing import paths
(``from .mesh_dialogs import ...`` and ``mesh_dialogs._BL_FIELD_SPECS``) keep
working via the re-exports below."""
from __future__ import annotations
from .mesh_dialogs_bl import (
    _BL_OVERRIDE_KEYS, _BL_INT_ATTRS, _BL_BOOL_ATTRS, _BL_FIELD_SPECS,
    SegmentBLSection, PerGeomBLDialog,
)
from .mesh_dialogs_bc import SegmentBCDialog, AssignPatchDialog

__all__ = [
    "_BL_OVERRIDE_KEYS", "_BL_INT_ATTRS", "_BL_BOOL_ATTRS", "_BL_FIELD_SPECS",
    "SegmentBLSection", "PerGeomBLDialog", "SegmentBCDialog", "AssignPatchDialog",
]
