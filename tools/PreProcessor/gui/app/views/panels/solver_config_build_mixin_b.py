"""Section builders for SolverConfigPanel, part B (behaviour unchanged).
Holds the output/restart/parallel/decompose/ibm/bc `_build_*` collapsible-
section constructors, split out of `solver_config_build_mixin.py` to keep each
file small. Every method references widgets/attributes created on the host panel
(`self.*`) and resolves via MRO; the `_browse_row` / `_dll_row` helpers live on
`SolverConfigBuildMixin` and are reached through `self.` on the shared instance.
"""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QTableWidget, QHeaderView,
)

from app.views.collapsible import CollapsibleSection
from app.utils import make_button, align_form_labels, help_label, help_widget
from app.views.panels.solver_config_widgets import _spin, _ispin, _edit, _check


class SolverConfigBuildMixinB:
    """Collapsible-section builders (output/restart/parallel/decompose/ibm/bc)."""

    def _build_output_section(self):
        sec = CollapsibleSection("Output & Probes", start_collapsed=True)
        self._layout.addWidget(sec)
        self.tecplot_write_vtx_output = _check(
            "Write nodal Tecplot output",
            "Write solutions on cell vertices instead of cell centers. "
            "Cell-centered is more reliable for the CESE scheme (esp. MPI).")
        self.calc_time_mean_values = _check(
            "Compute time-mean values",
            "Accumulate and write time averages (MeanValue_tec.dat).")
        sec.add_widget(self.tecplot_write_vtx_output)
        sec.add_widget(self.calc_time_mean_values)
        form = QFormLayout()
        self.probe_points_def_fn = _edit(
            "Probe-point coordinate file (one 'x y' per line for 2D); blank = no probes")
        self.probe_output_skip_niter = _ispin(
            1, 100_000_000, "Iterations between probe outputs")
        # Browse to an existing file, OR enter coordinates in the GUI and let it
        # auto-generate + link the probe file (#10). The controller owns the
        # coords dialog + file write.
        self.probe_coords_btn = QPushButton("Coords…")
        self.probe_coords_btn.setFixedWidth(64)
        self.probe_coords_btn.setToolTip(
            "Enter probe-point coordinates in the GUI; the probe file is generated "
            "and linked automatically.")
        self.probe_coords_btn.setStyleSheet(
            "QPushButton{background:#1d2a3a;color:#dde2ff;border:1px solid #2d3356;"
            "border-radius:4px;padding:2px;} QPushButton:hover{border-color:#5a9ad4;}")
        probe_row = self._browse_row(self.probe_points_def_fn, "Select probe-point file")
        probe_row.layout().addWidget(self.probe_coords_btn)
        form.addRow(help_label("Probe file:", "Probe-point coordinate definition file"),
                    probe_row)
        form.addRow(help_label("Probe /n:", "Iterations between probe outputs"),
                    self.probe_output_skip_niter)
        align_form_labels(form, 110)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(form)

    def _build_restart_section(self):
        sec = CollapsibleSection("Restart / Initial Condition", start_collapsed=True)
        self._layout.addWidget(sec)
        self.restart = _check(
            "Restart from previous run",
            "Continue from a previous run's zone-dump and convergence files.")
        sec.add_widget(self.restart)
        form = QFormLayout()
        self.convg_fn_restart = _edit(
            "Previous-run convergence file — the solver writes it into the case "
            "work dir as unicones.enorm.gui (GUI) / .cli (headless)")
        self.zdump_fn_restart = _edit(
            "Previous-run zone-dump file — the solver writes it into the case "
            "work dir as binDumpZ.dat.gui (GUI) / .cli (headless)")
        form.addRow(help_label("Convg file:", "Restart convergence file"),
                    self._browse_row(self.convg_fn_restart, "Select convergence file"))
        form.addRow(help_label("Zone dump:", "Restart zone-dump file"),
                    self._browse_row(self.zdump_fn_restart, "Select zone-dump file"))
        align_form_labels(form, 110)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(form)
        self._restart_form = form

        ic_form = QFormLayout()
        self.init_cond_depQ = _edit(
            "Explicit initial dep-var array, e.g. '1 1 0 0 0.524' (rho u v [w] et). "
            "Leave blank for freestream init. Ignored on restart, or when an init "
            "DLL is set.",
            placeholder="rho u v [w] et   e.g. 1 1 0 0 0.524")
        ic_form.addRow(help_label("init Q:", "Explicit initial dependent-variable array"),
                       self.init_cond_depQ)
        # Initial-condition DLL (works with OR without IBM, #4): a getQ-style
        # source the solver dlopens to set the initial field. 'Build…' opens the
        # DLL builder (freestream / normal-shock templates, IBM and non-IBM), and
        # the controller writes the resulting .cc path here. Takes precedence over
        # the explicit array above when set.
        self.init_cond_dll = _edit(
            "Path to an initial-condition DLL source (.cc; compiled per-case). "
            "Set it to drive the initial field from code instead of the explicit "
            "'init Q' array. Works with or without IBM.")
        self.build_init_cond_btn = make_button("Build…", "#1d2a3a")
        self.build_init_cond_btn.setFixedWidth(64)
        self.build_init_cond_btn.setToolTip(
            "Generate / edit / compile an initial-condition DLL from a template "
            "(freestream or normal shock; IBM and non-IBM variants)")
        ic_form.addRow(help_label("init DLL:", "Initial-condition DLL source (.cc)"),
                       self._dll_row(self.init_cond_dll, "Select init DLL source",
                                     self.build_init_cond_btn))
        align_form_labels(ic_form, 110)
        ic_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(ic_form)

    def _build_parallel_section(self):
        sec = CollapsibleSection("Parallel (pthread)", start_collapsed=True)
        self._layout.addWidget(sec)
        form = QFormLayout()
        self.apply_pthread = _check("Apply pthread", "Enable pthread parallelism")
        self.max_nthread = _ispin(1, 1024, "Maximum number of threads")
        self.num_zones_per_block = _ispin(1, 100000, "Number of zones per block")
        form.addRow("", help_widget(self.apply_pthread, "Enable pthread parallelism"))
        form.addRow(help_label("Max threads:", "Maximum number of threads"), self.max_nthread)
        form.addRow(help_label("Zones/block:", "Number of zones per block"), self.num_zones_per_block)
        align_form_labels(form, 110)
        sec.add_layout(form)

    def _build_decompose_section(self):
        sec = CollapsibleSection("Domain Decomposition (bDecompose)", start_collapsed=True)
        self._layout.addWidget(sec)
        self.enable_decompose = _check(
            "Enable domain decomposition (MPI)",
            "Run bDecompose to partition the grid and launch the solver under "
            "mpirun. Off by default (D4): the bundled unicones is a pthread build, "
            "not MPI. Requires mpirun on PATH and an MPI-capable solver binary.")
        sec.add_widget(self.enable_decompose)
        note = QLabel(
            "Needs mpirun on PATH + an MPI build of unicones; otherwise the run is "
            "refused before launch (the bundled binary is pthread-only).")
        note.setStyleSheet("color:#7a82a0; font-size: 10px;")
        note.setWordWrap(True)
        sec.add_widget(note)
        form = QFormLayout()
        self.num_partitions = _ispin(1, 4096, "Number of MPI partitions (mpirun -np)")
        self.readin_iface_info = _check(
            "Read in interface info",
            "Off for the first MPI run (the code generates interface info and writes "
            "it to file); on for later runs reusing it.")
        self.mpi_comm_map_fn = _edit("Communication-map file produced by bDecompose (optional)")
        form.addRow(help_label("Partitions:", "Number of MPI partitions"), self.num_partitions)
        form.addRow("", help_widget(self.readin_iface_info, "Reuse generated interface info"))
        form.addRow(help_label("Comm map:", "MPI communication-map file"),
                    self._browse_row(self.mpi_comm_map_fn, "Select comm-map file"))
        align_form_labels(form, 110)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(form)
        self._decompose_form = form

    def _build_ibm_section(self):
        sec = CollapsibleSection("Immersed Boundary (IBM)", start_collapsed=True)
        self._layout.addWidget(sec)
        self.immersed_solid = _check(
            "Immersed solid", "Enable the immersed-boundary solid phase (D7)")
        sec.add_widget(self.immersed_solid)
        form = QFormLayout()
        self.solid_phase_phi_min = _spin(6, 0.0, 1.0, "Minimum solid-phase phi")
        self.solid_phase_alpha = _spin(6, 0.0, 100.0, "Solid-phase alpha")
        self.solid_phase_epsilon = _spin(6, 0.0, 100.0, "Solid-phase epsilon")
        self.stationary_solid = _check("Stationary solid", "Solid does not move")
        self.rigid_moving_body = _check("Rigid moving body", "Solid is a rigid moving body")
        # The initial-condition DLL lives in the Restart / Initial Condition
        # section now (#4 — it works without IBM too); only the motion DLL is
        # IBM-specific and stays here.
        self.motion_dll = _edit("Path to motion DLL source (.cc; compiled per-case)")
        self.build_motion_btn = make_button("Build…", "#1d2a3a")
        self.build_motion_btn.setFixedWidth(64)
        self.build_motion_btn.setToolTip(
            "Generate / edit / compile this DLL with the IBM DLL Builder")
        form.addRow(help_label("phi_min:", "Minimum solid-phase phi"), self.solid_phase_phi_min)
        form.addRow(help_label("solid alpha:", "Solid-phase alpha"), self.solid_phase_alpha)
        form.addRow(help_label("solid eps:", "Solid-phase epsilon"), self.solid_phase_epsilon)
        form.addRow("", help_widget(self.stationary_solid, "Solid does not move"))
        form.addRow("", help_widget(self.rigid_moving_body, "Solid is a rigid moving body"))
        form.addRow(help_label("motion DLL:", "Motion DLL source (.cc)"),
                    self._dll_row(self.motion_dll, "Select motion DLL source", self.build_motion_btn))
        self.ibm_phi_file = _edit("phi field data (STL3d output), staged into the work dir as phi.dat")
        form.addRow(help_label("phi field:", "Solid phi field data from STL3d (staged as work/phi.dat)"),
                    self._browse_row(self.ibm_phi_file, "Select phi field data",
                                     "phi data (*.dat);;All Files (*)"))
        # Analytic alternative to the STL3d phi.dat: auto-generate a phi init DLL
        # from a CAD circle/polygon (no data file needed).
        self.build_phi_shape_btn = make_button("φ from CAD shape…", "#1d2a3a")
        self.build_phi_shape_btn.setToolTip(
            "Auto-generate an analytic phi init DLL from a CAD circle/polygon — "
            "immersed solid without an STL3d phi.dat file")
        form.addRow(help_label("analytic φ:", "Generate phi analytically from a CAD shape (no phi.dat)"),
                    self.build_phi_shape_btn)
        align_form_labels(form, 110)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(form)
        self._ibm_form = form

    def _build_bc_section(self):
        sec = CollapsibleSection("Boundary Conditions", start_collapsed=True)
        self._layout.addWidget(sec)
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
