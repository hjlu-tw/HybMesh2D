"""Section builders for SolverConfigPanel, part B: output / restart / parallel /
decompose / IBM / boundary conditions.

Same shape as part A — each builder names the ``SOLVER_SPECS`` group it lays out, and
the row helpers (``_browse_row`` / ``_dll_row``) plus ``_spec_rows`` / ``_section`` live
on ``SolverConfigBuildMixin`` and are reached through ``self.`` on the shared instance.
The BC table is the one thing here that is not a field: it is a table of rows (segment ·
patch name · BC type · extra value), so it stays hand-built and is declared in
``SOLVER_EXTRA_AUTHORED``.
"""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QTableWidget, QHeaderView,
)

from app.utils import make_button, align_form_labels, help_label
from app.views.panels.restart_chooser import RestartChooser


class SolverConfigBuildMixinB:
    """Collapsible-section builders (output/restart/parallel/decompose/ibm/bc)."""

    def _build_output_section(self):
        sec = self._section("Output & Probes")
        self._spec_widgets("output_flags")
        sec.add_widget(self.tecplot_write_vtx_output)
        sec.add_widget(self.calc_time_mean_values)

        # Browse to an existing file, OR enter coordinates in the GUI and let it
        # auto-generate + link the probe file (#10). The controller owns the coords
        # dialog + file write, so the button is only created here.
        self.probe_coords_btn = QPushButton("Coords…")
        self.probe_coords_btn.setFixedWidth(64)
        self.probe_coords_btn.setToolTip(
            "Enter probe-point coordinates in the GUI; the probe file is generated "
            "and linked automatically.")
        self.probe_coords_btn.setStyleSheet(
            "QPushButton{background:#1d2a3a;color:#dde2ff;border:1px solid #2d3356;"
            "border-radius:4px;padding:2px;} QPushButton:hover{border-color:#5a9ad4;}")

        def _probe_row(host, edit):
            row = host._browse_row(edit, "Select probe-point file")
            row.layout().addWidget(host.probe_coords_btn)
            return row

        form = QFormLayout()
        self._spec_rows(form, "output", wrap={"probe_points_def_fn": _probe_row})
        self._grow(form, 110)
        sec.add_layout(form)

    def _build_restart_section(self):
        sec = self._section("Restart / Initial Condition")
        # ONE control for "what does this run start from?" — the case's own
        # history as a list, cold start included (#31). It replaced a `Restart`
        # tick plus two path fields: three widgets for one decision, and the
        # tick sat in a different place from the thing it restarted FROM.
        self.restart_chooser = RestartChooser()
        sec.add_widget(self.restart_chooser)

        # 'Build…' opens the DLL builder (freestream / normal-shock templates, IBM and
        # non-IBM); the controller writes the resulting .cc path into the field. The
        # DLL takes precedence over the explicit 'init Q' array above when set.
        self.build_init_cond_btn = make_button("Build…", "#1d2a3a")
        self.build_init_cond_btn.setFixedWidth(64)
        self.build_init_cond_btn.setToolTip(
            "Generate / edit / compile an initial-condition DLL from a template "
            "(freestream or normal shock; IBM and non-IBM variants)")
        ic_form = QFormLayout()
        self._spec_rows(ic_form, "ic", wrap={
            "init_cond_dll": lambda host, edit: host._dll_row(
                edit, "Select init DLL source", host.build_init_cond_btn)})
        self._grow(ic_form, 110)
        sec.add_layout(ic_form)

    def _build_parallel_section(self):
        sec = self._section("Parallel (pthread)")
        form = QFormLayout()
        self._spec_rows(form, "parallel")
        align_form_labels(form, 110)
        sec.add_layout(form)

    def _build_decompose_section(self):
        sec = self._section("Domain Decomposition (bDecompose)")
        self._spec_widgets("decompose_enable")
        sec.add_widget(self.enable_decompose)
        note = QLabel(
            "Needs mpirun on PATH + an MPI build of unicones; otherwise the run is "
            "refused before launch (the bundled binary is pthread-only).")
        note.setStyleSheet("color:#7a82a0; font-size: 10px;")
        note.setWordWrap(True)
        sec.add_widget(note)

        form = QFormLayout()
        self._spec_rows(form, "decompose")
        self._grow(form, 110)
        sec.add_layout(form)
        self._decompose_form = form

    def _build_ibm_section(self):
        sec = self._section("Immersed Boundary (IBM)")
        self._spec_widgets("ibm_enable")
        sec.add_widget(self.immersed_solid)

        self.build_motion_btn = make_button("Build…", "#1d2a3a")
        self.build_motion_btn.setFixedWidth(64)
        self.build_motion_btn.setToolTip(
            "Generate / edit / compile this DLL with the IBM DLL Builder")
        form = QFormLayout()
        self._spec_rows(form, "ibm", wrap={
            "motion_dll": lambda host, edit: host._dll_row(
                edit, "Select motion DLL source", host.build_motion_btn)})

        # Analytic alternative to the STL3d phi.dat: auto-generate a phi init DLL
        # from a CAD circle/polygon (no data file needed). An action, not a field.
        self.build_phi_shape_btn = make_button("φ from CAD shape…", "#1d2a3a")
        self.build_phi_shape_btn.setToolTip(
            "Auto-generate an analytic phi init DLL from a CAD circle/polygon — "
            "immersed solid without an STL3d phi.dat file")
        form.addRow(help_label("analytic φ:",
                               "Generate phi analytically from a CAD shape (no phi.dat)"),
                    self.build_phi_shape_btn)
        self._grow(form, 110)
        sec.add_layout(form)
        self._ibm_form = form

    def _build_bc_section(self):
        sec = self._section("Boundary Conditions")
        hint = QLabel(
            "Assign the physical BC TYPE to each boundary patch here (Fluent-style): "
            "each row is a mesh segment (with the patch NAME it was given upstream in "
            "CAD / the mesh generator) → pick its type.\n"
            "Click 'Detect from Mesh' to load the ACTUAL segment numbers + patch "
            "names from the generated mesh (recommended — the mesher numbers "
            "segments by patch, not a fixed convention).\n"
            "Leave the table empty to keep getPGrid's own flags; add/detect rows to "
            "override.\nTypes marked (+) take an extra value: isothermal wall → wall "
            "T; fixed dep-vars → 'rho u v et'; user DLL → './bc.so'.")
        hint.setStyleSheet("color:#7a82a0; font-size: 10px;")
        hint.setWordWrap(True)
        sec.add_widget(hint)

        self.bc_table = QTableWidget(0, 4)
        self.bc_table.setHorizontalHeaderLabels(["Seg", "Patch", "BC Type", "Extra values"])
        self.bc_table.setFixedHeight(170)
        self.bc_table.setStyleSheet(
            "QTableWidget{background:#181b2a;color:#a0a8c0;border:1px solid #333852;"
            "gridline-color:#2c2e43;} QHeaderView::section{background:#1e2235;"
            "color:#a0a8c0;border:none;padding:3px;}")
        hdr = self.bc_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.bc_table.verticalHeader().setVisible(False)
        sec.add_widget(self.bc_table)

        # Detect from Mesh is the recommended, primary action (own row).
        self.bc_detect_btn = make_button("Detect from Mesh", "#1a3a2a")
        self.bc_detect_btn.setToolTip(
            "Read the ACTUAL boundary patches (segment number + name) from the last "
            "generated mesh's .bnd and fill the table, pre-selecting a sensible BC "
            "type per patch name. This is what makes the patch names you set in "
            "CAD / 'Edit segment BCs…' reach the solver with the correct segment "
            "numbers.")
        sec.add_widget(self.bc_detect_btn)

        bc_btns = QHBoxLayout()
        bc_btns.setSpacing(4)
        self.bc_add_btn = make_button("Add Row", "#1a2a3a")
        self.bc_remove_btn = make_button("Remove Row", "#301a1a")
        self.bc_default_btn = make_button("Box Default", "#1a2a3a")
        self.bc_default_btn.setToolTip(
            "Rectangle-box fallback (no per-patch names): fill segments 1-5 — "
            "domain 1-4 → non-reflect, geometry 5 → wall (no-slip for NS, reflect "
            "for Euler). Prefer 'Detect from Mesh' when patches are named.")
        bc_btns.addWidget(self.bc_add_btn)
        bc_btns.addWidget(self.bc_remove_btn)
        bc_btns.addWidget(self.bc_default_btn)
        sec.add_layout(bc_btns)
        self.bc_add_btn.clicked.connect(lambda: self._add_bc_row(0, 1, ""))
        self.bc_remove_btn.clicked.connect(self._remove_bc_row)
        self.bc_default_btn.clicked.connect(self._fill_default_bc)

        # BC type 11 (user DLL) needs a getQ_inst_dll source; offer a template
        # builder that writes the source path into the selected row's Extra
        # values, mirroring the IBM init/motion builders (#12). Wired by the
        # controller (it owns the dialog + row write-back).
        self.bc_dll_btn = make_button("BC DLL Builder (type 11)…", "#1d2a3a")
        self.bc_dll_btn.setToolTip(
            "Generate / edit / compile a BC type-11 getQ_inst_dll source from a "
            "parameter template (angled inflow, uniform inflow, or a blank "
            "skeleton) and drop its path into the selected BC row's Extra values.")
        sec.add_widget(self.bc_dll_btn)
        # bc_detect_btn is wired by the controller (it knows the mesh .bnd path).
