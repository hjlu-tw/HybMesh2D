"""Output section builder for MeshConfigPanel: the output-filename field, the
collision-detection toggle, the checkable per-format write buttons (VTK / STAR-CD /
CGNS) and the "Export mesh…" button.

The four config fields come from ``MESH_SPECS`` (groups ``output`` and ``formats``);
this file owns only the LAYOUT, which is the one thing about them that is not a
per-field fact — the three write formats stack under a single "Formats:" label instead
of taking a form row each.
"""
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFormLayout, QVBoxLayout
from app.views.collapsible import CollapsibleSection
from app.services.field_spec import in_group
from app.utils import make_button, align_form_labels, help_label, help_widget
from app.views.panels.mesh_field_specs import MESH_SPECS


class MeshConfigOutputMixin:
    """Builds the "Output" panel section (widgets + wiring)."""

    def _build_output_section(self):
        # ── 8. Output ─────────────────────────────────────────────────────
        self.sec_output = CollapsibleSection("Output", start_collapsed=True)
        self._layout.addWidget(self.sec_output)

        out_form = QFormLayout()
        self._spec_rows(out_form, "output")

        # Track whether the user typed a custom output name. While it's still an
        # auto-generated name, set_config refreshes it from the current geometry
        # so different geometries export to different mesh files. (This is why the
        # field is declared host_writes: the rule reads the widget's own text.)
        self._output_name_user_set = False
        self.output_filename.textEdited.connect(
            lambda _t: setattr(self, "_output_name_user_set", True))

        # #5/#8: each write-format is a checkable toggle BUTTON (highlighted green
        # when on) — which files to write on generate. #8-2: one per row (a single
        # row was too wide for the sidebar). Export-to-a-chosen-path uses the Export
        # button below (and the Results panel's Save VTK… / Save STAR-CD…).
        self._spec_widgets("formats")
        export_layout = QVBoxLayout()
        export_layout.setSpacing(4)
        for spec in in_group(MESH_SPECS, "formats"):
            export_layout.addWidget(help_widget(getattr(self, spec.attr), spec.tip))
        out_form.addRow(help_label(
            "Formats:", "Which mesh files to write when you generate. Use Export "
            "mesh… to save them to a specific path."), export_layout)

        # #5: an explicit Export button (write the generated mesh in the enabled
        # formats to a chosen location) — the per-format action buttons removed in
        # batch 6 left no output action in this panel. Emits export_mesh_requested,
        # wired by the controller to the same save flow as the Results panel.
        self.export_mesh_btn = make_button("Export mesh…", "#243a52")
        self.export_mesh_btn.setToolTip(
            "Save the generated mesh (in the enabled write formats above) to a "
            "chosen location. Generates first if no mesh exists yet.")
        out_form.addRow("", help_widget(
            self.export_mesh_btn,
            "Save the generated mesh in the enabled formats to a chosen location"))

        align_form_labels(out_form, 90)
        out_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        out_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.sec_output.add_layout(out_form)
