"""Section builders for SolverConfigPanel, split out as a mixin (behaviour
unchanged). Holds the `_build_*` collapsible-section constructors plus the
`_browse_row` / `_dll_row` helpers. Every method references widgets/attributes
created on the host panel (`self.*`) and resolves via MRO; each `_build_*`
creates the widgets it owns and appends its section to `self._layout`."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QFormLayout, QLabel, QPushButton, QFileDialog,
    QTableWidget, QHeaderView, QLineEdit,
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
        form.addRow(help_label("Out grid:", "Output grid filename"), self.output_grid_file)
        form.addRow(help_label("Out bc:", "Output bc filename"), self.output_bc_file)
        align_form_labels(form, 100)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(form)

    def _build_flow_section(self):
        sec = CollapsibleSection("Flow Conditions", start_collapsed=True)
        self._layout.addWidget(sec)
        form = QFormLayout()
        # Axisymmetric is a property of the solved domain (nozzles, cones), not of
        # the getPGrid file conversion — it belongs with the flow/domain settings.
        self.axisymmetric_2d = _check(
            "Axisymmetric 2D", "Treat the 2D domain as axisymmetric (nozzles, cones)")
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
        form.addRow("", help_widget(self.axisymmetric_2d, "Treat the 2D domain as axisymmetric"))
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
        self.dissip_per_cfl = _check(
            "Dissipation per CFL",
            "Scale the artificial dissipation by the local CFL number so the "
            "dissipation stays consistent when the CFL / time-step varies "
            "(local time stepping, ramped CFL). It is a stabilisation toggle "
            "only — the dissipation magnitude is still set by alpha / beta / "
            "dissip_ctrl, so no extra input is required.")
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
        form.addRow("", help_widget(self.dissip_per_cfl,
            "Scale dissipation by local CFL for stability — no extra input needed"))
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


# --- output/restart/parallel/decompose/ibm/bc builders moved to
# solver_config_build_mixin_b.SolverConfigBuildMixinB (kept on the same panel
# instance via MRO) to keep each file small. ---

