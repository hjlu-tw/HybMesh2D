"""Output section builder for MeshConfigPanel, split out as a mixin (behaviour
unchanged): the output-filename field, the collision-detection toggle, the
checkable per-format write buttons (VTK / STAR-CD / CGNS) and the "Export mesh…"
button.

The section-building code was relocated verbatim from MeshConfigPanel.__init__.
The Export button is wired to export_mesh_requested and other output widgets are
read/written by get_config/set_config in MeshConfigConfigMixin — they resolve on
self via the shared MRO."""
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFormLayout, QVBoxLayout, QCheckBox, QLineEdit,
)
from app.views.collapsible import CollapsibleSection
from app.utils import (
    make_button, align_form_labels, help_label, help_widget, LINEEDIT_STYLE,
)


class MeshConfigOutputMixin:
    """Builds the "Output" panel section (widgets + wiring)."""

    def _build_output_section(self):
        # ── 8. Output ─────────────────────────────────────────────────────
        self.sec_output = CollapsibleSection("Output", start_collapsed=True)
        self._layout.addWidget(self.sec_output)

        self.output_filename = QLineEdit()
        self.output_filename.setStyleSheet(LINEEDIT_STYLE)
        self.output_filename.setToolTip("Base filename for mesh output files (extension .* means all formats)")
        # Track whether the user typed a custom output name. While it's still an
        # auto-generated name, set_config refreshes it from the current geometry
        # so different geometries export to different mesh files.
        self._output_name_user_set = False
        self.output_filename.textEdited.connect(
            lambda _t: setattr(self, "_output_name_user_set", True))

        # #5: each write-format is a checkable toggle BUTTON (highlighted green
        # when on) instead of a checkbox — a click selects whether that format is
        # written on Generate. isChecked()/setChecked() keep working, so set_config
        # / get_config are unchanged.
        def _fmt_btn(text):
            b = make_button(text, "#181b2a", border="#2d3356",
                            hover_border="#5a9ad4", checked_bg="#1e4620")
            b.setCheckable(True)
            return b

        self.export_vtk = _fmt_btn("VTK")
        self.export_vtk.setToolTip("Write a .vtk file when the mesh is generated/saved.")
        self.export_starcd = _fmt_btn("STAR-CD")
        self.export_starcd.setToolTip(
            "Write STAR-CD files (.vrt/.cel/.bnd) when the mesh is generated/saved "
            "(required for the solver).")
        self.export_cgns = _fmt_btn("CGNS")
        self.export_cgns.setToolTip(
            "Write a CGNS file (.cgns; unstructured zone + per-BC patches) when the "
            "mesh is generated. Ignored if HybMesh2D was built without the CGNS library.")
        self.enable_collision_detection = QCheckBox("Collision Detection")
        self.enable_collision_detection.setStyleSheet("color:#a0a8c0;")
        self.enable_collision_detection.setToolTip("Enable self-intersection detection during boundary layer generation")

        # #5: an explicit Export button (write the generated mesh in the enabled
        # formats to a chosen location) — the per-format action buttons removed in
        # batch 6 left no output action in this panel. Emits export_mesh_requested,
        # wired by the controller to the same save flow as the Results panel.
        self.export_mesh_btn = make_button("Export mesh…", "#243a52")
        self.export_mesh_btn.setToolTip(
            "Save the generated mesh (in the enabled write formats above) to a "
            "chosen location. Generates first if no mesh exists yet.")

        out_form = QFormLayout()
        out_form.addRow(help_label("Output File:", "Base filename for mesh output files (extension .* means all formats)"), self.output_filename)
        out_form.addRow("", help_widget(self.enable_collision_detection, "Enable self-intersection detection during boundary layer generation"))

        # #5/#8: unified output — each write-format is a checkable toggle button
        # (which files to write on generate). #8-2: one per row (the single row was
        # too wide for the sidebar). Export-to-a-chosen-path uses the Export button
        # below (and the Results panel's Save VTK… / Save STAR-CD…).
        export_layout = QVBoxLayout()
        export_layout.setSpacing(4)
        export_layout.addWidget(help_widget(self.export_vtk, "Write a .vtk file when the mesh is generated"))
        export_layout.addWidget(help_widget(self.export_starcd, "Write STAR-CD files (.vrt/.cel/.bnd) when the mesh is generated (required for the solver)"))
        export_layout.addWidget(help_widget(self.export_cgns, "Write a CGNS file when the mesh is generated"))
        out_form.addRow(help_label("Write formats:", "Which mesh files to write when you generate. Use Export mesh… to save them to a specific path."), export_layout)
        out_form.addRow("", help_widget(self.export_mesh_btn, "Save the generated mesh in the enabled formats to a chosen location"))
        align_form_labels(out_form, 90)
        out_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        out_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.sec_output.add_layout(out_form)
