from __future__ import annotations
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QFormLayout, QComboBox, QSpinBox, QLabel, QCheckBox, QLineEdit,
    QPushButton, QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
)
from PyQt6.QtCore import Qt

from app.views.collapsible import CollapsibleSection
from app.utils import (
    make_button, COMBO_STYLE, SPIN_STYLE, align_form_labels,
    help_label, help_widget, LINEEDIT_STYLE, find_solver_executables,
)
from app.models.solver_config import (
    SolverConfig, BC_TYPES, PRESETS, BC_FLAGS_NEEDING_EXTRA,
)
from app.views.clean_double_spin_box import CleanDoubleSpinBox


_SCROLLBAR_QSS = """
    QScrollBar:vertical { border: none; background: #0c0d16; width: 10px; margin: 0px; }
    QScrollBar::handle:vertical { background: #2c2e43; min-height: 20px; border-radius: 5px; }
    QScrollBar::handle:vertical:hover { background: #3e415e; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
"""


def _spin(decimals: int, lo: float, hi: float, tip: str) -> CleanDoubleSpinBox:
    s = CleanDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(decimals)
    s.setStyleSheet(SPIN_STYLE)
    s.setToolTip(tip)
    return s


def _ispin(lo: int, hi: int, tip: str) -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setStyleSheet(SPIN_STYLE)
    s.setToolTip(tip)
    return s


def _edit(tip: str) -> QLineEdit:
    e = QLineEdit()
    e.setStyleSheet(LINEEDIT_STYLE)
    e.setToolTip(tip)
    return e


def _check(text: str, tip: str) -> QCheckBox:
    c = QCheckBox(text)
    c.setStyleSheet("color:#a0a8c0;")
    c.setToolTip(tip)
    return c


def _combo(items: list[str], tip: str) -> QComboBox:
    c = QComboBox()
    c.addItems(items)
    c.setStyleSheet(COMBO_STYLE)
    c.setToolTip(tip)
    return c


def _parse_float(text: str, fallback: float) -> float:
    try:
        return float(text.strip())
    except (ValueError, AttributeError):
        return fallback


class SolverConfigPanel(QScrollArea):
    """Sidebar panel editing every SolverConfig parameter.

    The controller (Phase 3) connects run_solver_btn / cancel_solver_btn and
    reads/writes the model via get_config()/set_config().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background: #0c0d16;")
        self.verticalScrollBar().setStyleSheet(_SCROLLBAR_QSS)

        content = QWidget()
        content.setStyleSheet("background: #121422; color: #a0a8c0;")
        content.setMaximumWidth(430)
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(6, 6, 6, 6)
        self._layout.setSpacing(6)
        self.setWidget(content)

        # ── Run / Cancel buttons ──────────────────────────────────────────
        self.run_solver_btn = make_button("Run Solver", "#1e4620")
        self.cancel_solver_btn = make_button("Cancel", "#4a1c1c")
        self.cancel_solver_btn.setEnabled(False)
        run_row = QHBoxLayout()
        run_row.setSpacing(4)
        run_row.addWidget(self.run_solver_btn)
        run_row.addWidget(self.cancel_solver_btn)
        self._layout.addLayout(run_row)

        # Config save/load
        self.load_cfg_btn = make_button("Load Solver Config", "#1d2a3a")
        self.save_cfg_btn = make_button("Save Solver Config", "#301540")
        cfg_row = QHBoxLayout()
        cfg_row.setSpacing(4)
        cfg_row.addWidget(self.load_cfg_btn)
        cfg_row.addWidget(self.save_cfg_btn)
        self._layout.addLayout(cfg_row)

        # ── Workload preset ───────────────────────────────────────────────
        preset_row = QHBoxLayout()
        preset_row.setSpacing(4)
        preset_lbl = QLabel("Preset:")
        preset_lbl.setStyleSheet("color:#7a82a0;")
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("— choose a starting point —")
        self.preset_combo.addItems(list(PRESETS.keys()))
        self.preset_combo.setStyleSheet(COMBO_STYLE)
        self.preset_combo.setToolTip(
            "Apply a manual-grounded starting point (numerics + dissipation), "
            "then fine-tune. Does not change geometry, BCs or iteration counts.")
        self.apply_preset_btn = make_button("Apply", "#1d2a3a")
        self.apply_preset_btn.setFixedWidth(70)
        preset_row.addWidget(preset_lbl)
        preset_row.addWidget(self.preset_combo, 1)
        preset_row.addWidget(self.apply_preset_btn)
        self._layout.addLayout(preset_row)
        self.apply_preset_btn.clicked.connect(self._apply_preset)

        # Domain type selector (e2d / e3d) at top
        top_form = QFormLayout()
        self.domain_type = QComboBox()
        self.domain_type.addItems(["e2d", "e3d"])
        self.domain_type.setStyleSheet(COMBO_STYLE)
        self.domain_type.setToolTip("Solver domain dimensionality (e2d = 2D, e3d = 3D)")
        self.case_name = _edit("Case name; solver_ctrl builds case/<name>/{work,grid,dll}")
        top_form.addRow(help_label("Domain Type:", "Solver domain dimensionality"), self.domain_type)
        top_form.addRow(help_label("Case Name:", "Case name for the solver working directory"), self.case_name)
        align_form_labels(top_form, 130)
        self._layout.addLayout(top_form)

        self._build_pipeline_section()
        self._build_grid_section()
        self._build_flow_section()
        self._build_turbulence_section()
        self._build_numerics_section()
        self._build_iteration_section()
        self._build_output_section()
        self._build_restart_section()
        self._build_parallel_section()
        self._build_decompose_section()
        self._build_ibm_section()
        self._build_bc_section()

        self._layout.addStretch()

        # Prefill binary paths from the prebuilt binaries under solver/ (D5).
        found = find_solver_executables()
        if found.get("getpgrid"):
            self.getpgrid_binary.setText(found["getpgrid"])
        if found.get("bdecompose"):
            self.bdecompose_binary.setText(found["bdecompose"])
        if found.get("solver"):
            self.solver_binary.setText(found["solver"])

        self.immersed_solid.toggled.connect(self._update_ibm_visibility)
        self.enable_decompose.toggled.connect(self._update_decompose_visibility)
        self.enable_shock.toggled.connect(self._update_shock_visibility)
        self.restart.toggled.connect(self._update_restart_visibility)
        self.flow_solu_type.currentTextChanged.connect(self._on_flow_solu_changed)
        self._update_ibm_visibility()
        self._update_decompose_visibility()
        self._update_shock_visibility()
        self._update_restart_visibility()

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

    def _build_pipeline_section(self):
        sec = CollapsibleSection("1. Pipeline Binaries", start_collapsed=True)
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
        sec = CollapsibleSection("2. Grid Conversion (getPGrid)", start_collapsed=True)
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
        sec = CollapsibleSection("3. Flow Conditions", start_collapsed=True)
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
        sec = CollapsibleSection("3b. Turbulence", start_collapsed=True)
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
        sec = CollapsibleSection("4. Numerics", start_collapsed=True)
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
        sec = CollapsibleSection("5. Iteration Control", start_collapsed=True)
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
        sec = CollapsibleSection("5c. Output & Probes", start_collapsed=True)
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
        sec = CollapsibleSection("5b. Restart / Initial Condition", start_collapsed=True)
        self._layout.addWidget(sec)
        self.restart = _check(
            "Restart from previous run",
            "Continue from a previous run's zone-dump and convergence files.")
        sec.add_widget(self.restart)
        form = QFormLayout()
        self.convg_fn_restart = _edit("Previous-run convergence file (e.g. unicones.enorm.r1)")
        self.zdump_fn_restart = _edit("Previous-run zone-dump file (e.g. binDumpZ.dat.r1)")
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
        sec = CollapsibleSection("6. Parallel (pthread)", start_collapsed=True)
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
        sec = CollapsibleSection("7. Domain Decomposition (bDecompose)", start_collapsed=True)
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
        sec = CollapsibleSection("8. Immersed Boundary (IBM)", start_collapsed=True)
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
        form.addRow(help_label("phi_min:", "Minimum solid-phase phi"), self.solid_phase_phi_min)
        form.addRow(help_label("solid alpha:", "Solid-phase alpha"), self.solid_phase_alpha)
        form.addRow(help_label("solid eps:", "Solid-phase epsilon"), self.solid_phase_epsilon)
        form.addRow("", help_widget(self.stationary_solid, "Solid does not move"))
        form.addRow("", help_widget(self.rigid_moving_body, "Solid is a rigid moving body"))
        form.addRow(help_label("init DLL:", "Init-condition DLL source (.cc)"),
                    self._browse_row(self.init_cond_dll, "Select init DLL source", "C++ (*.cc *.cpp *.so);;All Files (*)"))
        form.addRow(help_label("motion DLL:", "Motion DLL source (.cc)"),
                    self._browse_row(self.motion_dll, "Select motion DLL source", "C++ (*.cc *.cpp *.so);;All Files (*)"))
        align_form_labels(form, 110)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(form)
        self._ibm_form = form

    def _build_bc_section(self):
        sec = CollapsibleSection("9. Boundary Conditions", start_collapsed=True)
        self._layout.addWidget(sec)
        hint = QLabel(
            "Segment → BC type. HybMesh2D groups: 1-4 = domain (XMin/XMax/YMin/YMax), "
            "5 = geometry.\nLeave the table empty to keep getPGrid's own boundary flags; "
            "add rows to override.\nTypes marked (+) take an extra value: isothermal wall "
            "→ wall T; fixed dep-vars → 'rho u v et'; user DLL → './bc.so'.")
        hint.setStyleSheet("color:#7a82a0; font-size: 10px;")
        hint.setWordWrap(True)
        sec.add_widget(hint)

        self.bc_table = QTableWidget(0, 3)
        self.bc_table.setHorizontalHeaderLabels(["Seg", "BC Type", "Extra values"])
        self.bc_table.setFixedHeight(170)
        self.bc_table.setStyleSheet(
            "QTableWidget{background:#181b2a;color:#a0a8c0;border:1px solid #333852;"
            "gridline-color:#2c2e43;} QHeaderView::section{background:#1e2235;"
            "color:#a0a8c0;border:none;padding:3px;}")
        hdr = self.bc_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.bc_table.verticalHeader().setVisible(False)
        sec.add_widget(self.bc_table)

        bc_btns = QHBoxLayout()
        bc_btns.setSpacing(4)
        self.bc_add_btn = make_button("Add Row", "#1a2a3a")
        self.bc_remove_btn = make_button("Remove Row", "#301a1a")
        self.bc_default_btn = make_button("Fill Default", "#1a2a3a")
        self.bc_default_btn.setToolTip(
            "Fill segments 1-5: domain 1-4 → non-reflect, geometry 5 → wall "
            "(no-slip for NS, reflect for Euler).")
        bc_btns.addWidget(self.bc_add_btn)
        bc_btns.addWidget(self.bc_remove_btn)
        bc_btns.addWidget(self.bc_default_btn)
        sec.add_layout(bc_btns)
        self.bc_add_btn.clicked.connect(lambda: self._add_bc_row(0, 1, ""))
        self.bc_remove_btn.clicked.connect(self._remove_bc_row)
        self.bc_default_btn.clicked.connect(self._fill_default_bc)

    def _fill_default_bc(self):
        """Populate the standard HybMesh2D group mapping (1-4 domain non-reflect,
        5 geometry wall) using the wall flag appropriate for the solution type."""
        wall = 0 if self.flow_solu_type.currentText() == "euler_sol" else 2
        self.bc_table.setRowCount(0)
        for seg, bc in [(1, 1), (2, 1), (3, 1), (4, 1), (5, wall)]:
            self._add_bc_row(seg, bc, "")

    # ------------------------------------------------------------------ #
    # BC table helpers
    # ------------------------------------------------------------------ #
    def _make_bc_type_combo(self, flag: int) -> QComboBox:
        """A combo listing every BCType by name; itemData stores the integer flag.
        Types that take an extra value are suffixed with '(+)'."""
        combo = QComboBox()
        combo.setStyleSheet(COMBO_STYLE)
        sel = 0
        for i, (f, label, extra) in enumerate(BC_TYPES):
            combo.addItem(f"{f}: {label}{'  (+)' if extra else ''}", f)
            if f == flag:
                sel = i
        combo.setCurrentIndex(sel)
        combo.currentIndexChanged.connect(
            lambda _=None, c=combo: self._sync_bc_extra_hint(c))
        return combo

    def _sync_bc_extra_hint(self, combo: QComboBox):
        """Tooltip the row's extra cell according to the selected type."""
        for r in range(self.bc_table.rowCount()):
            if self.bc_table.cellWidget(r, 1) is combo:
                flag = combo.currentData()
                item = self.bc_table.item(r, 2)
                if item is None:
                    item = QTableWidgetItem("")
                    self.bc_table.setItem(r, 2, item)
                hints = {3: "non-dimensional wall temperature, e.g. 2.5",
                         50: "rho u v et (2D) or rho u v w et (3D)",
                         11: "./bc.so (path to the DLL)"}
                item.setToolTip(hints.get(flag, "(no extra value needed)"))
                break

    def _add_bc_row(self, seg: int, bc: int, values: str = ""):
        r = self.bc_table.rowCount()
        self.bc_table.insertRow(r)
        self.bc_table.setItem(r, 0, QTableWidgetItem(str(seg)))
        self.bc_table.setCellWidget(r, 1, self._make_bc_type_combo(bc))
        self.bc_table.setItem(r, 2, QTableWidgetItem(values))
        self._sync_bc_extra_hint(self.bc_table.cellWidget(r, 1))

    def _remove_bc_row(self):
        rows = sorted({i.row() for i in self.bc_table.selectedItems()}, reverse=True)
        # selectedItems() misses combo-only selections; fall back to current row.
        if not rows and self.bc_table.currentRow() >= 0:
            rows = [self.bc_table.currentRow()]
        for r in rows:
            self.bc_table.removeRow(r)

    # ------------------------------------------------------------------ #
    # Visibility toggles
    # ------------------------------------------------------------------ #
    def _set_form_enabled(self, form: QFormLayout, enabled: bool):
        for i in range(form.rowCount()):
            for role in (QFormLayout.ItemRole.LabelRole, QFormLayout.ItemRole.FieldRole):
                it = form.itemAt(i, role)
                if it and it.widget():
                    it.widget().setEnabled(enabled)

    def _update_ibm_visibility(self):
        self._set_form_enabled(self._ibm_form, self.immersed_solid.isChecked())

    def _update_decompose_visibility(self):
        self._set_form_enabled(self._decompose_form, self.enable_decompose.isChecked())

    def _update_shock_visibility(self):
        self._set_form_enabled(self._shock_form, self.enable_shock.isChecked())

    def _update_restart_visibility(self):
        self._set_form_enabled(self._restart_form, self.restart.isChecked())

    def _on_flow_solu_changed(self, _text: str):
        """When the solver type flips, refresh the geometry wall row (seg 5) if it
        still holds the other type's default wall flag, so the BC stays sensible."""
        wall = 0 if self.flow_solu_type.currentText() == "euler_sol" else 2
        other = 2 if wall == 0 else 0
        for r in range(self.bc_table.rowCount()):
            seg_item = self.bc_table.item(r, 0)
            combo = self.bc_table.cellWidget(r, 1)
            if not seg_item or combo is None:
                continue
            if seg_item.text().strip() == "5" and combo.currentData() == other:
                idx = combo.findData(wall)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

    def _apply_preset(self):
        """Apply the selected workload preset onto the current config + UI."""
        name = self.preset_combo.currentText()
        if name not in PRESETS:
            return
        cfg = self.get_config()
        cfg.apply_preset(name)
        self.set_config(cfg)

    # ------------------------------------------------------------------ #
    # Model sync
    # ------------------------------------------------------------------ #
    def set_config(self, cfg: SolverConfig):
        self.domain_type.setCurrentText(cfg.domain_type)
        self.case_name.setText(cfg.case_name)
        self.getpgrid_binary.setText(cfg.getpgrid_binary)
        self.bdecompose_binary.setText(cfg.bdecompose_binary)
        self.solver_binary.setText(cfg.solver_binary)

        self.input_vrt_file.setText(cfg.input_vrt_file)
        self.input_cel_file.setText(cfg.input_cel_file)
        self.input_bnd_file.setText(cfg.input_bnd_file)
        self.is_3d.setChecked(cfg.is_3d)
        self.mixed_mesh.setChecked(cfg.mixed_mesh)
        self.axisymmetric_2d.setChecked(cfg.axisymmetric_2d)
        self.output_grid_file.setText(cfg.output_grid_file)
        self.output_bc_file.setText(cfg.output_bc_file)

        self.flow_solu_type.setCurrentText(cfg.flow_solu_type)
        self.transp_prop_option.setCurrentText(cfg.transp_prop_option)
        self.fs_mach.setValue(cfg.fs_mach)
        self.fs_tinf.setValue(cfg.fs_tinf)
        self.fs_unit_re.setValue(cfg.fs_unit_re)
        self.fs_flow_angle.setValue(cfg.fs_flow_angle)
        self.linf.setValue(cfg.linf)
        self.gamma.setValue(cfg.gamma)
        self.rgas.setValue(cfg.rgas)
        self.stokes.setValue(cfg.stokes)
        self.prandtl.setValue(cfg.prandtl)

        self.turb_model_option.setCurrentText(cfg.turb_model_option)
        self.construct_wall_dist_db.setChecked(cfg.construct_wall_dist_db)
        self.read_in_wall_dist_db.setChecked(cfg.read_in_wall_dist_db)

        self.cfl.setValue(cfg.cfl)
        self.constant_cfl.setChecked(cfg.constant_cfl)
        self.dt_const.setText(cfg.dt_const)
        self.cfl_schedule_fn.setText(cfg.cfl_schedule_fn)
        self.alpha.setValue(cfg.alpha)
        self.beta.setText(f"{cfg.beta:g}")
        self.dissip_ctrl.setText(f"{cfg.dissip_ctrl:g}")
        self.epsilon.setValue(cfg.epsilon)
        self.convg_norm_type.setCurrentText(cfg.convg_norm_type)
        self.use_incenter.setChecked(cfg.use_incenter)
        self.dissip_per_cfl.setChecked(cfg.dissip_per_cfl)
        self.unsteady_lstep.setChecked(cfg.unsteady_lstep)

        self.enable_shock.setChecked(cfg.enable_shock_capturing)
        self.shock_gradp_value.setText(f"{cfg.shock_gradp_value:g}")
        self.shockf_gradp_beta.setText(f"{cfg.shockf_gradp_beta:g}")
        self.shockf_gradp_eps.setValue(cfg.shockf_gradp_eps)
        self.shockf_gradp_dissip_ctrl.setText(f"{cfg.shockf_gradp_dissip_ctrl:g}")

        self.num_half_iter.setValue(cfg.num_half_iter)
        self.print_convg_per_niter.setValue(cfg.print_convg_per_niter)
        self.print_sol_per_niter.setValue(cfg.print_sol_per_niter)
        self.dump_zone_per_niter.setValue(cfg.dump_zone_per_niter)
        self.write_wall_force.setChecked(cfg.write_wall_force)

        self.tecplot_write_vtx_output.setChecked(cfg.tecplot_write_vtx_output)
        self.calc_time_mean_values.setChecked(cfg.calc_time_mean_values)
        self.probe_points_def_fn.setText(cfg.probe_points_def_fn)
        self.probe_output_skip_niter.setValue(cfg.probe_output_skip_niter)

        self.restart.setChecked(cfg.restart)
        self.convg_fn_restart.setText(cfg.convg_fn_restart)
        self.zdump_fn_restart.setText(cfg.zdump_fn_restart)
        self.init_cond_depQ.setText(cfg.init_cond_depQ)

        self.apply_pthread.setChecked(cfg.apply_pthread)
        self.max_nthread.setValue(cfg.max_nthread)
        self.num_zones_per_block.setValue(cfg.num_zones_per_block)

        self.enable_decompose.setChecked(cfg.enable_decompose)
        self.num_partitions.setValue(cfg.num_partitions)
        self.readin_iface_info.setChecked(cfg.readin_iface_info)
        self.mpi_comm_map_fn.setText(cfg.mpi_comm_map_fn)

        self.immersed_solid.setChecked(cfg.immersed_solid)
        self.solid_phase_phi_min.setValue(cfg.solid_phase_phi_min)
        self.solid_phase_alpha.setValue(cfg.solid_phase_alpha)
        self.solid_phase_epsilon.setValue(cfg.solid_phase_epsilon)
        self.stationary_solid.setChecked(cfg.stationary_solid)
        self.rigid_moving_body.setChecked(cfg.rigid_moving_body)
        self.init_cond_dll.setText(cfg.init_cond_dll)
        self.motion_dll.setText(cfg.motion_dll)

        self.bc_table.setRowCount(0)
        for bc in cfg.bc_definitions:
            self._add_bc_row(bc.get("segment_no", 0), bc.get("bc_type", 0),
                             str(bc.get("values", "") or ""))

        self._update_ibm_visibility()
        self._update_decompose_visibility()
        self._update_shock_visibility()
        self._update_restart_visibility()

    def get_config(self, cfg: SolverConfig | None = None) -> SolverConfig:
        cfg = cfg or SolverConfig()
        cfg.domain_type = self.domain_type.currentText()
        cfg.case_name = self.case_name.text().strip() or "case"
        cfg.getpgrid_binary = self.getpgrid_binary.text().strip()
        cfg.bdecompose_binary = self.bdecompose_binary.text().strip()
        cfg.solver_binary = self.solver_binary.text().strip()

        cfg.input_vrt_file = self.input_vrt_file.text().strip()
        cfg.input_cel_file = self.input_cel_file.text().strip()
        cfg.input_bnd_file = self.input_bnd_file.text().strip()
        cfg.is_3d = self.is_3d.isChecked()
        cfg.mixed_mesh = self.mixed_mesh.isChecked()
        cfg.axisymmetric_2d = self.axisymmetric_2d.isChecked()
        cfg.output_grid_file = self.output_grid_file.text().strip() or "mesh.grid"
        cfg.output_bc_file = self.output_bc_file.text().strip() or "mesh.bc"

        cfg.flow_solu_type = self.flow_solu_type.currentText()
        cfg.transp_prop_option = self.transp_prop_option.currentText()
        cfg.fs_mach = self.fs_mach.value()
        cfg.fs_tinf = self.fs_tinf.value()
        cfg.fs_unit_re = self.fs_unit_re.value()
        cfg.fs_flow_angle = self.fs_flow_angle.value()
        cfg.linf = self.linf.value()
        cfg.gamma = self.gamma.value()
        cfg.rgas = self.rgas.value()
        cfg.stokes = self.stokes.value()
        cfg.prandtl = self.prandtl.value()

        cfg.turb_model_option = self.turb_model_option.currentText()
        cfg.construct_wall_dist_db = self.construct_wall_dist_db.isChecked()
        cfg.read_in_wall_dist_db = self.read_in_wall_dist_db.isChecked()

        cfg.cfl = self.cfl.value()
        cfg.constant_cfl = self.constant_cfl.isChecked()
        cfg.dt_const = self.dt_const.text().strip()
        cfg.cfl_schedule_fn = self.cfl_schedule_fn.text().strip()
        cfg.alpha = self.alpha.value()
        cfg.beta = _parse_float(self.beta.text(), cfg.beta)
        cfg.dissip_ctrl = _parse_float(self.dissip_ctrl.text(), cfg.dissip_ctrl)
        cfg.epsilon = self.epsilon.value()
        cfg.convg_norm_type = self.convg_norm_type.currentText()
        cfg.use_incenter = self.use_incenter.isChecked()
        cfg.dissip_per_cfl = self.dissip_per_cfl.isChecked()
        cfg.unsteady_lstep = self.unsteady_lstep.isChecked()

        cfg.enable_shock_capturing = self.enable_shock.isChecked()
        cfg.shock_gradp_value = _parse_float(self.shock_gradp_value.text(), cfg.shock_gradp_value)
        cfg.shockf_gradp_beta = _parse_float(self.shockf_gradp_beta.text(), cfg.shockf_gradp_beta)
        cfg.shockf_gradp_eps = self.shockf_gradp_eps.value()
        cfg.shockf_gradp_dissip_ctrl = _parse_float(
            self.shockf_gradp_dissip_ctrl.text(), cfg.shockf_gradp_dissip_ctrl)

        cfg.num_half_iter = self.num_half_iter.value()
        cfg.print_convg_per_niter = self.print_convg_per_niter.value()
        cfg.print_sol_per_niter = self.print_sol_per_niter.value()
        cfg.dump_zone_per_niter = self.dump_zone_per_niter.value()
        cfg.write_wall_force = self.write_wall_force.isChecked()

        cfg.tecplot_write_vtx_output = self.tecplot_write_vtx_output.isChecked()
        cfg.calc_time_mean_values = self.calc_time_mean_values.isChecked()
        cfg.probe_points_def_fn = self.probe_points_def_fn.text().strip()
        cfg.probe_output_skip_niter = self.probe_output_skip_niter.value()

        cfg.restart = self.restart.isChecked()
        cfg.convg_fn_restart = self.convg_fn_restart.text().strip()
        cfg.zdump_fn_restart = self.zdump_fn_restart.text().strip()
        cfg.init_cond_depQ = self.init_cond_depQ.text().strip()

        cfg.apply_pthread = self.apply_pthread.isChecked()
        cfg.max_nthread = self.max_nthread.value()
        cfg.num_zones_per_block = self.num_zones_per_block.value()

        cfg.enable_decompose = self.enable_decompose.isChecked()
        cfg.num_partitions = self.num_partitions.value()
        cfg.readin_iface_info = self.readin_iface_info.isChecked()
        cfg.mpi_comm_map_fn = self.mpi_comm_map_fn.text().strip()

        cfg.immersed_solid = self.immersed_solid.isChecked()
        cfg.solid_phase_phi_min = self.solid_phase_phi_min.value()
        cfg.solid_phase_alpha = self.solid_phase_alpha.value()
        cfg.solid_phase_epsilon = self.solid_phase_epsilon.value()
        cfg.stationary_solid = self.stationary_solid.isChecked()
        cfg.rigid_moving_body = self.rigid_moving_body.isChecked()
        cfg.init_cond_dll = self.init_cond_dll.text().strip()
        cfg.motion_dll = self.motion_dll.text().strip()

        cfg.bc_definitions = []
        for r in range(self.bc_table.rowCount()):
            seg_item = self.bc_table.item(r, 0)
            combo = self.bc_table.cellWidget(r, 1)
            val_item = self.bc_table.item(r, 2)
            try:
                seg = int(seg_item.text()) if seg_item else 0
            except (ValueError, AttributeError):
                continue
            bc = int(combo.currentData()) if combo is not None else 0
            values = val_item.text().strip() if val_item else ""
            # Only keep the extra value for types that actually use one.
            if bc not in BC_FLAGS_NEEDING_EXTRA:
                values = ""
            cfg.bc_definitions.append(
                {"segment_no": seg, "bc_type": bc, "values": values})

        return cfg
