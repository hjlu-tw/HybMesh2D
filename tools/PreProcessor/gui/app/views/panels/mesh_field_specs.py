"""Re-export of the mesh panel's field-spec table, which now lives Qt-free.

The table moved to ``app/services/mesh_field_specs.py`` so the ``.dat`` key map can
DERIVE from it. It could not before, and the reason is worth stating: the table
itself imports only ``dataclasses`` and two Qt-free modules, but any module under
``app/views/panels/`` drags in that package's ``__init__``, which eagerly imports
eight Qt panels. Measured — importing this table with PyQt6 blocked raised
ImportError — and ``models/mesh_config_keys.py`` is on the HEADLESS path
(``mesh_config_io`` → ``run_pipeline.sh`` / ``run_batch.sh``), the exact seam
``tests/test_qt_free_seam.py`` exists to keep clean.

This shim exists so the Qt-side call sites keep their import path, the same way
``app/utils.py`` re-exports the path helpers that moved to ``services/paths.py``.
"""
from app.services.mesh_field_specs import MESH_EXTRA_AUTHORED, MESH_SPECS

__all__ = ["MESH_SPECS", "MESH_EXTRA_AUTHORED"]
