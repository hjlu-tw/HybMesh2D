"""Model-unit row for MeshConfigPanel, and the suffix broadcast for its length fields.

Deliberately **not** a collapsible section, and placed above everything else: it is the
one control that tells you what every other number on the panel means. Collapsing it by
default (as the other sections are) would hide the interpretive key to the whole panel,
and a unit you cannot see is how a millimetre model gets meshed as metres.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QFormLayout, QWidget

from app.services import units
from app.services.field_spec import length_attrs
from app.utils import align_form_labels, help_label
from app.views.panels.mesh_bl_field_specs import PANEL_BL_SPECS
from app.views.panels.mesh_field_specs import MESH_SPECS
from app.views.units_ui import UnitSelector, apply_unit_suffix

#: Panel attributes holding a *physical length*, and therefore the exact set that
#: carries a unit suffix. Everything else on the panel is dimensionless — growth
#: rates, angles, layer counts — and must not be labelled with one.
#:
#: DERIVED from the field-spec tables rather than listed: the ``sci`` kind IS the
#: physical-length rule (a SciDoubleSpinBox, no floor, decade steps), so the list and
#: the widgets cannot disagree. tests/test_units.py asserts this equals the panel's
#: SciDoubleSpinBox set, which is now a statement about the derivation — and that is
#: what stops a field added later from quietly losing its unit.
LENGTH_FIELDS = length_attrs(MESH_SPECS, PANEL_BL_SPECS)


class MeshConfigUnitsMixin:
    """Builds the model-unit row and keeps the panel's length suffixes in step."""

    def _build_units_section(self):
        holder = QWidget()
        form = QFormLayout(holder)
        form.setContentsMargins(0, 0, 0, 2)
        self.unit_selector = UnitSelector()
        form.addRow(
            help_label("Model Unit:",
                       "The unit every length in this project is written in; reaches "
                       "the solver as Linf (metres per grid unit)"),
            self.unit_selector)
        align_form_labels(form, 130)
        self._layout.addWidget(holder)

        self.unit_selector.unit_changed.connect(self._on_unit_changed)
        self._apply_unit_suffixes()

    # ── suffixes ─────────────────────────────────────────────────────────
    def _length_widgets(self):
        return [getattr(self, n, None) for n in LENGTH_FIELDS]

    def _apply_unit_suffixes(self):
        apply_unit_suffix(self._length_widgets(),
                          self.unit_selector.unit(),
                          self.unit_selector.custom_name())

    def _on_unit_changed(self, unit: str, metres: float, custom_name: str):
        """A user unit change: relabel, then let the controller propagate.

        Nothing is rescaled here. The panel's numbers stay exactly as typed, which is
        the documented contract — a unit change is a statement about what the existing
        numbers mean, not an instruction to convert them.
        """
        self._apply_unit_suffixes()
        # Reuse the panel's normal change path so the value lands in MeshConfig and
        # the controller's undo snapshot sees it like any other edit.
        if hasattr(self, "_emit_config_changed"):
            self._emit_config_changed()
        elif hasattr(self, "mesh_config_changed"):
            self.mesh_config_changed.emit(self.get_config())

    # ── config plumbing ──────────────────────────────────────────────────
    def _units_to_config(self, cfg):
        cfg.length_unit = self.unit_selector.unit()
        cfg.length_unit_metres = self.unit_selector.custom_metres()
        cfg.length_unit_name = self.unit_selector.custom_name()

    def _units_from_config(self, cfg):
        self.unit_selector.set_unit(
            units.parse(getattr(cfg, "length_unit", "m"), "m"),
            getattr(cfg, "length_unit_metres", 1.0) or 1.0,
            getattr(cfg, "length_unit_name", "") or "")
        self._apply_unit_suffixes()
