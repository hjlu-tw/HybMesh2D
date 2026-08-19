"""Checkbox factory shared by SolverConfigPanel and its mixins.

This module used to hold a full set of widget constructors — ``_spin`` / ``_ispin`` /
``_edit`` / ``_combo`` / ``_parse_float`` — which was a SECOND kind->widget mapping
beside the one in ``field_widgets.py`` and the one the Edit-BL dialog kept. Now that
every solver field is built from ``solver_field_specs.SOLVER_SPECS`` they have no
callers, and a dead mapping is exactly how the halves diverged in the first place, so
they are deleted rather than left available.

``_check`` survives because one solver control is NOT a config field: the Grid section's
"Auto-link from Mesh Generator output" toggle chooses where the .vrt/.cel/.bnd come
from rather than editing a value, so it has no spec.
"""
from __future__ import annotations
from PyQt6.QtWidgets import QCheckBox


def _check(text: str, tip: str) -> QCheckBox:
    c = QCheckBox(text)
    c.setStyleSheet("color:#a0a8c0;")
    c.setToolTip(tip)
    return c
