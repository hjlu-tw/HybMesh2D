"""Section builders for SolverConfigPanel, split out as a mixin (behaviour
unchanged). Holds the `_build_*` collapsible-section constructors plus the
`_browse_row` / `_dll_row` helpers. Every method references widgets/attributes
created on the host panel (`self.*`) and resolves via MRO; each `_build_*`
creates the widgets it owns and appends its section to `self._layout`."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QFormLayout, QLabel, QPushButton, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
)

from app.views.collapsible import CollapsibleSection
from app.utils import make_button, align_form_labels, help_label, help_widget
from app.views.panels.solver_config_widgets import _spin, _ispin, _edit, _check, _combo


class SolverConfigBuildMixin:
    """Collapsible-section builders + browse/dll row helpers."""

    # ------------------------------------------------------------------ #
    # Section builders
    # ------------------------------------------------------------------ #
    def _browse_row(self, edit: QLineEdit, caption: str, filt: str = "All Files (*)"):
        """A line edit + Browse button row."""
        btn = QPushButton("…")
        btn.setFixedWidth(32)
        btn.setStyleSheet(
            "QPushButton{background:#1d2a3a;color:#dde2ff;border:1px solid #2d3356;"
            "border-radius:4px;padding:2px;} QPushButton:hover{border-color:#5a9ad4;}")

        def _do():
            f, _ = QFileDialog.getOpenFileName(self, caption, "", filt)
            if f:
                edit.setText(f)
        btn.clicked.connect(_do)
        row = QHBoxLayout()
        row.setSpacing(4)
        row.addWidget(edit, 1)
        row.addWidget(btn)
        w = QWidget()
        w.setLayout(row)
        return w

    def _dll_row(self, edit: QLineEdit, caption: str, build_btn: QPushButton):
        """A DLL path row: line edit + Browse + a 'Build…' button."""
        browse = QPushButton("…")
        browse.setFixedWidth(32)
        browse.setStyleSheet(
            "QPushButton{background:#1d2a3a;color:#dde2ff;border:1px solid #2d3356;"
            "border-radius:4px;padding:2px;} QPushButton:hover{border-color:#5a9ad4;}")

        def _do():
            f, _ = QFileDialog.getOpenFileName(
                self, caption, "", "C++ (*.cc *.cpp *.so);;All Files (*)")
            if f:
                edit.setText(f)
        browse.clicked.connect(_do)
        row = QHBoxLayout()
        row.setSpacing(4)
        row.addWidget(edit, 1)
        row.addWidget(browse)
        row.addWidget(build_btn)
        w = QWidget()
        w.setLayout(row)
        return w

    def _build_pipeline_section(self):
        sec = CollapsibleSection("Pipeline Binaries", start_collapsed=True)
        self._layout.addWidget(sec)
        form = QFormLayout()
        self.getpgrid_binary = _edit("Path to the getPGrid binary")
        self.bdecompose_binary = _edit("Path to the bDecompose binary (optional)")
        self.solver_binary = _edit("Path to the unicones solver binary")
        form.addRow(help_label("getPGrid:", "Path to the getPGrid binary"),
                    self._browse_row(self.getpgrid_binary, "Select getPGrid binary"))
        form.addRow(help_label("bDecompose:", "Path to the bDecompose binary (optional)"),
                    self._browse_row(self.bdecompose_binary, "Select bDecompose binary"))
        form.addRow(help_label("Solver:", "Path to the unicones solver binary"),
                    self._browse_row(self.solver_binary, "Select solver binary"))
        align_form_labels(form, 100)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(form)

    def _build_grid_section(self):
        sec = CollapsibleSection("Grid Conversion (getPGrid)", start_collapsed=True)
        self._layout.addWidget(sec)
        self.auto_link_mesh = _check(
            "Auto-link from Mesh Generator output",
            "Use the .vrt/.cel/.bnd produced by HybMesh2D as getPGrid input")
        self.auto_link_mesh.setChecked(True)
        sec.add_widget(self.auto_link_mesh)

        form = QFormLayout()
        self.input_vrt_file = _edit("STAR-CD vertex file (.vrt)")
        self.input_cel_file = _edit("STAR-CD cell file (.cel)")
        self.input_bnd_file = _edit("STAR-CD boundary file (.bnd)")
        self.is_3d = _check("3D grid", "Treat the input as a 3D grid")
        self.mixed_mesh = _check(
            "Mixed mesh (keep quads+tris)",
            "Preserve the hybrid quad+tri mesh instead of slicing to triangles. "
            "Forces use_incenter off (undefined for quad cells).")
        self.axisymmetric_2d = _check(
            "Axisymmetric 2D", "Treat the 2D domain as axisymmetric (nozzles, cones)")
        self.output_grid_file = _edit("Output grid filename (.grid)")
        self.output_bc_file = _edit("Output bc filename (.bc)")
        form.addRow(help_label(".vrt:", "STAR-CD vertex file"),
                    self._browse_row(self.input_vrt_file, "Select .vrt", "Vertex (*.vrt);;All Files (*)"))
        form.addRow(help_label(".cel:", "STAR-CD cell file"),
                    self._browse_row(self.input_cel_file, "Select .cel", "Cell (*.cel);;All Files (*)"))
        form.addRow(help_label(".bnd:", "STAR-CD boundary file"),
                    self._browse_row(self.input_bnd_file, "Select .bnd", "Boundary (*.bnd);;All Files (*)"))
        form.addRow("", help_widget(self.is_3d, "Treat the input as a 3D grid"))
        form.addRow("", help_widget(self.mixed_mesh, "Preserve hybrid quad+tri mesh"))
        form.addRow("", help_widget(self.axisymmetric_2d, "Treat the 2D domain as axisymmetric"))
        form.addRow(help_label("Out grid:", "Output grid filename"), self.output_grid_file)
        form.addRow(help_label("Out bc:", "Output bc filename"), self.output_bc_file)
        align_form_labels(form, 100)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(form)

    def _build_flow_section(self):
        sec = CollapsibleSection("Flow Conditions", start_collapsed=True)
        self._layout.addWidget(sec)
        form = QFormLayout()
        self.flow_solu_type = _combo(
            ["ns_sol", "euler_sol"],
            "Solution type: ns_sol = viscous Navier-Stokes, euler_sol = inviscid.\n"
            "Also drives the default geometry wall BC (no-slip vs slip).")
        self.transp_prop_option = _combo(
            ["CONST_PRANDTL", "CONST_PROP", "VAR_PRANDTL"],
            "Transport-property model under the perfect-gas assumption.")
        self.fs_mach = _spin(4, 0.0, 100.0, "Free-stream Mach number")
        self.fs_tinf = _spin(2, 0.0, 1e5, "Free-stream temperature (K)")
        self.fs_unit_re = _spin(2, 0.0, 1e9, "Free-stream unit Reynolds number per meter")
        self.fs_flow_angle = _spin(3, -180.0, 180.0,
                                   "Free-stream flow angle / angle of attack (degrees)")
        self.linf = _spin(6, 1e-6, 1e6, "Reference length scale (m); 1 if mesh already in metres")
        self.gamma = _spin(4, 1.0, 2.0, "Ratio of specific heats Cp/Cv (1.4 for air)")
        self.rgas = _spin(3, 0.0, 1e4, "Perfect-gas constant R (≈287 for air, SI)")
        self.stokes = _spin(4, -10.0, 10.0, "Stokes coefficient for the second viscosity")
        self.prandtl = _spin(4, 0.0, 10.0, "Prandtl number")
        form.addRow(help_label("Solver type:", "ns_sol (viscous) / euler_sol (inviscid)"),
                    self.flow_solu_type)
        form.addRow(help_label("Transport:", "Transport-property model"), self.transp_prop_option)
        form.addRow(help_label("Mach:", "Free-stream Mach number"), self.fs_mach)
        form.addRow(help_label("AoA (deg):", "Free-stream flow angle / angle of attack"),
                    self.fs_flow_angle)
        form.addRow(help_label("T_inf (K):", "Free-stream temperature"), self.fs_tinf)
        form.addRow(help_label("Unit Re:", "Free-stream unit Reynolds number"), self.fs_unit_re)
        form.addRow(help_label("L_inf (m):", "Reference length scale"), self.linf)
        form.addRow(help_label("gamma:", "Ratio of specific heats"), self.gamma)
        form.addRow(help_label("Rgas:", "Perfect-gas constant"), self.rgas)
        form.addRow(help_label("Stokes:", "Second-viscosity Stokes coefficient"), self.stokes)
        form.addRow(help_label("Prandtl:", "Prandtl number"), self.prandtl)
        align_form_labels(form, 110)
        sec.add_layout(form)

    def _build_turbulence_section(self):
        sec = CollapsibleSection("Turbulence", start_collapsed=True)
        self._layout.addWidget(sec)
        form = QFormLayout()
        self.turb_model_option = _combo(
            ["laminar", "sa_model", "komega_wilcox", "komega_sst",
             "k-epsilon", "smagorinsky", "dsm_model"],
            "Turbulence model. laminar = none. RANS models need near-wall y+~1 mesh;\n"
            "LES (smagorinsky/dsm) is only meaningful for time-accurate runs.")
        self.construct_wall_dist_db = _check(
            "Construct wall-distance DB",
            "Generate Wall_dist_db.dat (RANS pre-processing step; run once with "
            "num_half_iter = 0, then switch to 'Read in').")
        self.read_in_wall_dist_db = _check(
            "Read in wall-distance DB",
            "Read the previously generated Wall_dist_db.dat instead of rebuilding it.")
        form.addRow(help_label("Model:", "Turbulence model option"), self.turb_model_option)
        form.addRow("", help_widget(self.construct_wall_dist_db, "Build wall-distance database"))
        form.addRow("", help_widget(self.read_in_wall_dist_db, "Read wall-distance database"))
        align_form_labels(form, 110)
        sec.add_layout(form)

    def _build_numerics_section(self):
        sec = CollapsibleSection("Numerics", start_collapsed=True)
        self._layout.addWidget(sec)
        form = QFormLayout()
        self.cfl = _spin(4, 0.0, 1e4, "CFL number")
        self.constant_cfl = _check("Constant CFL", "Hold CFL constant across iterations")
        self.alpha = _spin(4, -1e6, 1e6, "Numerical parameter alpha")
        # Scientific-notation values use a free-text edit (spin box can't show 1e-12).
        self.beta = _edit("Numerical parameter beta (e.g. -200000)")
        self.dissip_ctrl = _edit("Dissipation control (e.g. 1.0e-12)")
        self.epsilon = _spin(4, -1e6, 1e6, "Numerical parameter epsilon")
        self.use_incenter = _check("Use incenter", "Use triangle incenter for reconstruction")
        self.dissip_per_cfl = _check("Dissipation per CFL", "Scale dissipation per CFL")
        self.unsteady_lstep = _check("Unsteady local stepping", "Enable unsteady local time stepping")
        self.dt_const = _edit("Constant time step (used when 'Constant CFL' is off). Leave blank to use CFL.")
        self.cfl_schedule_fn = _edit("Optional iteration→(cfl,dt,dissip) schedule table filename")
        self.convg_norm_type = _combo(
            ["L2NORM", "L1NORM"], "Error-norm type used for the convergence residual.")
        form.addRow(help_label("CFL:", "CFL number"), self.cfl)
        form.addRow("", help_widget(self.constant_cfl, "Hold CFL constant (steady state)"))
        form.addRow(help_label("dt_const:", "Constant time step (when Constant CFL is off)"), self.dt_const)
        form.addRow(help_label("CFL schedule:", "Iteration-vs-parameter schedule file"), self.cfl_schedule_fn)
        form.addRow(help_label("alpha:", "Numerical parameter alpha (larger = more dissipation)"), self.alpha)
        form.addRow(help_label("beta:", "Numerical parameter beta"), self.beta)
        form.addRow(help_label("dissip_ctrl:", "Dissipation control"), self.dissip_ctrl)
        form.addRow(help_label("epsilon:", "Numerical parameter epsilon (sigma bound)"), self.epsilon)
        form.addRow(help_label("Norm:", "Convergence error-norm type"), self.convg_norm_type)
        form.addRow("", help_widget(self.use_incenter, "Use triangle incenter"))
        form.addRow("", help_widget(self.dissip_per_cfl, "Scale dissipation per CFL"))
        form.addRow("", help_widget(self.unsteady_lstep, "Unsteady local time stepping (TALTS)"))
        align_form_labels(form, 110)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(form)

        # ── Shock capturing (collapsible toggle) ──
        self.enable_shock = _check(
            "Enable shock capturing",
            "Pressure-gradient based shock capturing for supersonic flows.\n"
            "Tip: run once and plot the 'vort' variable (2nd pressure derivative) "
            "to pick shock_gradp_value.")
        sec.add_widget(self.enable_shock)
        shock_form = QFormLayout()
        self.shock_gradp_value = _edit("Shock detection cut-off (e.g. -2000)")
        self.shockf_gradp_beta = _edit("Shock beta (e.g. -2000)")
        self.shockf_gradp_eps = _spin(4, -1e6, 1e6, "Shock epsilon (e.g. 3)")
        self.shockf_gradp_dissip_ctrl = _edit("Shock dissipation control (e.g. 1.0e-14)")
        shock_form.addRow(help_label("gradp value:", "Shock detection cut-off"), self.shock_gradp_value)
        shock_form.addRow(help_label("gradp beta:", "Shock beta"), self.shockf_gradp_beta)
        shock_form.addRow(help_label("gradp eps:", "Shock epsilon"), self.shockf_gradp_eps)
        shock_form.addRow(help_label("gradp dissip:", "Shock dissipation control"), self.shockf_gradp_dissip_ctrl)
        align_form_labels(shock_form, 110)
        shock_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(shock_form)
        self._shock_form = shock_form

    def _build_iteration_section(self):
        sec = CollapsibleSection("Iteration Control", start_collapsed=True)
        self._layout.addWidget(sec)
        form = QFormLayout()
        self.num_half_iter = _ispin(1, 100_000_000, "Total number of half-iterations to run")
        # R9: keep print intervals small enough that the live residual monitor
        # actually receives data (the stock 100000 leaves it blank for a long time).
        self.print_convg_per_niter = _ispin(
            1, 100_000_000,
            "Iterations between convergence prints. Keep small (e.g. 100) so the "
            "live residual monitor updates (R9).")
        self.print_sol_per_niter = _ispin(
            1, 100_000_000,
            "Iterations between Tecplot solution dumps. Controls when Results has a file.")
        self.dump_zone_per_niter = _ispin(
            1, 100_000_000,
            "Iterations between zone-dump (restart) writes.")
        self.write_wall_force = _check(
            "Write wall force", "Compute viscous wall force and write WallForce.dat (lift/drag history).")
        form.addRow(help_label("Half iters:", "Total number of half-iterations"), self.num_half_iter)
        form.addRow(help_label("Print convg /n:", "Iterations between convergence prints (keep small for live monitor)"), self.print_convg_per_niter)
        form.addRow(help_label("Print sol /n:", "Iterations between Tecplot solution dumps"), self.print_sol_per_niter)
        form.addRow(help_label("Dump zone /n:", "Iterations between restart zone dumps"), self.dump_zone_per_niter)
        form.addRow("", help_widget(self.write_wall_force, "Write WallForce.dat"))
        align_form_labels(form, 110)
        sec.add_layout(form)

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
        form.addRow(help_label("Probe file:", "Probe-point coordinate definition file"),
                    self._browse_row(self.probe_points_def_fn, "Select probe-point file"))
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
            "Leave blank for freestream init. Ignored on restart / IBM.")
        ic_form.addRow(help_label("init Q:", "Explicit initial dependent-variable array"),
                       self.init_cond_depQ)
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
        self.init_cond_dll = _edit("Path to init-condition DLL source (.cc; compiled per-case)")
        self.motion_dll = _edit("Path to motion DLL source (.cc; compiled per-case)")
        # "Build…" opens the IBM DLL builder (templates + editor + g++); the
        # controller wires these and writes the resulting .cc path back here.
        self.build_init_cond_btn = make_button("Build…", "#1d2a3a")
        self.build_motion_btn = make_button("Build…", "#1d2a3a")
        for b in (self.build_init_cond_btn, self.build_motion_btn):
            b.setFixedWidth(64)
            b.setToolTip("Generate / edit / compile this DLL with the IBM DLL Builder")
        form.addRow(help_label("phi_min:", "Minimum solid-phase phi"), self.solid_phase_phi_min)
        form.addRow(help_label("solid alpha:", "Solid-phase alpha"), self.solid_phase_alpha)
        form.addRow(help_label("solid eps:", "Solid-phase epsilon"), self.solid_phase_epsilon)
        form.addRow("", help_widget(self.stationary_solid, "Solid does not move"))
        form.addRow("", help_widget(self.rigid_moving_body, "Solid is a rigid moving body"))
        form.addRow(help_label("init DLL:", "Init-condition DLL source (.cc)"),
                    self._dll_row(self.init_cond_dll, "Select init DLL source", self.build_init_cond_btn))
        form.addRow(help_label("motion DLL:", "Motion DLL source (.cc)"),
                    self._dll_row(self.motion_dll, "Select motion DLL source", self.build_motion_btn))
        self.ibm_phi_file = _edit("phi field data (STL3d output), staged into the work dir as phi.dat")
        form.addRow(help_label("phi field:", "Solid phi field data from STL3d (staged as work/phi.dat)"),
                    self._browse_row(self.ibm_phi_file, "Select phi field data",
                                     "phi data (*.dat);;All Files (*)"))
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
        # bc_detect_btn is wired by the controller (it knows the mesh .bnd path).
