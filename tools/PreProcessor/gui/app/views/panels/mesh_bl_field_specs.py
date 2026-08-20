"""Re-export of the boundary-layer field-spec tables, which now live Qt-free.

See ``app/views/panels/mesh_field_specs.py`` for why they moved: the ``.dat`` key
map derives from them and must not pull PyQt6 onto the headless pipeline's path.
The tables themselves are unchanged and their new home is
``app/services/mesh_bl_field_specs.py``.
"""
from app.services.mesh_bl_field_specs import (
    BL_SPECS,
    PANEL_BL_SPECS,
    _BL_BOOL_ATTRS,
    _BL_FIELD_GROUPS,
    _BL_FIELD_SPECS,
    _BL_INT_ATTRS,
    _BL_MODEL_TYPES,
    _BL_OVERRIDE_KEYS,
    _value_differs,
)

#: Every name any caller reaches through this path — enumerated by parsing the
#: importers rather than guessed, and `__all__` is mandatory here: ruff's F401 would
#: otherwise read a re-export as an unused import and `--fix` would gut the shim.
__all__ = ["BL_SPECS", "PANEL_BL_SPECS", "_BL_FIELD_SPECS", "_BL_FIELD_GROUPS",
           "_BL_OVERRIDE_KEYS", "_BL_MODEL_TYPES", "_BL_INT_ATTRS",
           "_BL_BOOL_ATTRS", "_value_differs"]
