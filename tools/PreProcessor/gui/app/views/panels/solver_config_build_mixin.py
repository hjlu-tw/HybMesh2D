"""Section builders for SolverConfigPanel, part A: pipeline / grid / flow /
turbulence / numerics / iteration.

Every widget comes from ``SOLVER_SPECS`` (``views/panels/solver_field_specs.py``): a
builder names the GROUP of rows it lays out and, where a row is composite, how to wrap
that one field's widget. The 51 ``self.<attr> = _spin(…)`` lines this file used to hold
were a second description of fields the sync half named again — see the module docstring
of ``app/services/field_spec.py`` for what that cost.
"""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QFormLayout, QPushButton, QLineEdit,
)

from app.models.solver_config import SolverConfig
from app.utils import align_form_labels
from app.views.collapsible import CollapsibleSection
from app.views.panels.field_widgets import SpecRowsMixin, browse_row
from app.views.panels.solver_config_widgets import _check
from app.views.panels.solver_field_specs import SOLVER_SPECS


class SolverConfigBuildMixin(SpecRowsMixin):
    """Collapsible-section builders + browse/dll row helpers.

    ``_spec_rows`` / ``_spec_widgets`` come from SpecRowsMixin.
    """

    _SPEC_TABLE = SOLVER_SPECS
    _SPEC_MODEL = SolverConfig

    # ------------------------------------------------------------------ #
    # Row helpers
    # ------------------------------------------------------------------ #
    def _browse_row(self, edit: QLineEdit, caption: str, filt: str = "All Files (*)"):
        """A line edit + Browse button row (shared with every other config panel)."""
        return browse_row(self, edit, caption, filt)

    def _dll_row(self, edit: QLineEdit, caption: str, build_btn: QPushButton):
        """A DLL path row: line edit + Browse + a 'Build…' button."""
        w = browse_row(self, edit, caption, "C++ (*.cc *.cpp *.so);;All Files (*)")
        w.layout().addWidget(build_btn)
        return w

    # ------------------------------------------------------------------ #
    # Section plumbing
    # ------------------------------------------------------------------ #
    def _section(self, title: str) -> CollapsibleSection:
        sec = CollapsibleSection(title, start_collapsed=True)
        self._layout.addWidget(sec)
        return sec

    @staticmethod
    def _grow(form: QFormLayout, width: int) -> None:
        align_form_labels(form, width)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

    # ------------------------------------------------------------------ #
    # Section builders
    # ------------------------------------------------------------------ #
    def _build_pipeline_section(self):
        sec = self._section("Pipeline Binaries")
        form = QFormLayout()
        self._spec_rows(form, "pipeline")
        self._grow(form, 100)
        sec.add_layout(form)

    def _build_grid_section(self):
        sec = self._section("Grid Conversion (getPGrid)")
        # Not a SolverConfig field: it chooses where the .vrt/.cel/.bnd come from
        # rather than editing a value, and solver_ctrl reads it directly.
        self.auto_link_mesh = _check(
            "Auto-link from Mesh Generator output",
            "Use the .vrt/.cel/.bnd produced by HybMesh2D as getPGrid input")
        self.auto_link_mesh.setChecked(True)
        sec.add_widget(self.auto_link_mesh)

        form = QFormLayout()
        self._spec_rows(form, "grid")
        self._grow(form, 100)
        sec.add_layout(form)

    def _build_flow_section(self):
        sec = self._section("Flow Conditions")
        form = QFormLayout()
        self._spec_rows(form, "flow")
        align_form_labels(form, 110)
        sec.add_layout(form)

    def _build_turbulence_section(self):
        sec = self._section("Turbulence")
        form = QFormLayout()
        self._spec_rows(form, "turbulence")
        align_form_labels(form, 110)
        sec.add_layout(form)

    def _build_numerics_section(self):
        sec = self._section("Numerics")
        form = QFormLayout()
        self._spec_rows(form, "numerics")
        self._grow(form, 110)
        sec.add_layout(form)

        # ── Shock capturing: a bare toggle gating its own sub-form ──
        self._spec_widgets("shock_enable")
        sec.add_widget(self.enable_shock)
        shock_form = QFormLayout()
        self._spec_rows(shock_form, "shock")
        self._grow(shock_form, 110)
        sec.add_layout(shock_form)
        self._shock_form = shock_form

    def _build_iteration_section(self):
        sec = self._section("Iteration Control")
        form = QFormLayout()
        self._spec_rows(form, "iteration")
        align_form_labels(form, 110)
        sec.add_layout(form)


# --- output/restart/parallel/decompose/ibm/bc builders live in
# solver_config_build_mixin_b.SolverConfigBuildMixinB (kept on the same panel
# instance via MRO) to keep each file small. ---
