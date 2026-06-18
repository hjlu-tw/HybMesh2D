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
from app.models.solver_config import SolverConfig
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
        self._build_numerics_section()
        self._build_iteration_section()
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
        self._update_ibm_visibility()
        self._update_decompose_visibility()

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
        self.output_grid_file = _edit("Output grid filename (.grid)")
        self.output_bc_file = _edit("Output bc filename (.bc)")
        form.addRow(help_label(".vrt:", "STAR-CD vertex file"),
                    self._browse_row(self.input_vrt_file, "Select .vrt", "Vertex (*.vrt);;All Files (*)"))
        form.addRow(help_label(".cel:", "STAR-CD cell file"),
                    self._browse_row(self.input_cel_file, "Select .cel", "Cell (*.cel);;All Files (*)"))
        form.addRow(help_label(".bnd:", "STAR-CD boundary file"),
                    self._browse_row(self.input_bnd_file, "Select .bnd", "Boundary (*.bnd);;All Files (*)"))
        form.addRow("", help_widget(self.is_3d, "Treat the input as a 3D grid"))
        form.addRow(help_label("Out grid:", "Output grid filename"), self.output_grid_file)
        form.addRow(help_label("Out bc:", "Output bc filename"), self.output_bc_file)
        align_form_labels(form, 100)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(form)

    def _build_flow_section(self):
        sec = CollapsibleSection("3. Flow Conditions", start_collapsed=True)
        self._layout.addWidget(sec)
        form = QFormLayout()
        self.fs_mach = _spin(4, 0.0, 100.0, "Free-stream Mach number")
        self.fs_tinf = _spin(2, 0.0, 1e5, "Free-stream temperature (K)")
        self.fs_unit_re = _spin(2, 0.0, 1e9, "Free-stream unit Reynolds number")
        self.linf = _spin(4, 1e-6, 1e6, "Reference length scale")
        self.prandtl = _spin(4, 0.0, 10.0, "Prandtl number")
        form.addRow(help_label("Mach:", "Free-stream Mach number"), self.fs_mach)
        form.addRow(help_label("T_inf (K):", "Free-stream temperature"), self.fs_tinf)
        form.addRow(help_label("Unit Re:", "Free-stream unit Reynolds number"), self.fs_unit_re)
        form.addRow(help_label("L_inf:", "Reference length scale"), self.linf)
        form.addRow(help_label("Prandtl:", "Prandtl number"), self.prandtl)
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
        form.addRow(help_label("CFL:", "CFL number"), self.cfl)
        form.addRow("", help_widget(self.constant_cfl, "Hold CFL constant"))
        form.addRow(help_label("alpha:", "Numerical parameter alpha"), self.alpha)
        form.addRow(help_label("beta:", "Numerical parameter beta"), self.beta)
        form.addRow(help_label("dissip_ctrl:", "Dissipation control"), self.dissip_ctrl)
        form.addRow(help_label("epsilon:", "Numerical parameter epsilon"), self.epsilon)
        form.addRow("", help_widget(self.use_incenter, "Use triangle incenter"))
        form.addRow("", help_widget(self.dissip_per_cfl, "Scale dissipation per CFL"))
        form.addRow("", help_widget(self.unsteady_lstep, "Unsteady local time stepping"))
        align_form_labels(form, 110)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        sec.add_layout(form)

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
        form.addRow(help_label("Half iters:", "Total number of half-iterations"), self.num_half_iter)
        form.addRow(help_label("Print convg /n:", "Iterations between convergence prints (keep small for live monitor)"), self.print_convg_per_niter)
        form.addRow(help_label("Print sol /n:", "Iterations between Tecplot solution dumps"), self.print_sol_per_niter)
        align_form_labels(form, 110)
        sec.add_layout(form)

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
            "Run bDecompose to partition the grid for MPI. Off by default (D4): "
            "the unicones reference path is pthread-parallel, not MPI.")
        sec.add_widget(self.enable_decompose)
        form = QFormLayout()
        self.num_partitions = _ispin(1, 4096, "Number of MPI partitions")
        form.addRow(help_label("Partitions:", "Number of MPI partitions"), self.num_partitions)
        align_form_labels(form, 110)
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
            "Segment → BC type  (0: reflect, 1: non-reflect, 5: fixed)\n"
            "HybMesh2D groups: 1-4 = domain (XMin/XMax/YMin/YMax), 5 = geometry.\n"
            "Leave empty to use getPGrid's own boundary flags; fill to override.")
        hint.setStyleSheet("color:#7a82a0; font-size: 10px;")
        hint.setWordWrap(True)
        sec.add_widget(hint)

        self.bc_table = QTableWidget(0, 2)
        self.bc_table.setHorizontalHeaderLabels(["Segment No", "BC Type"])
        self.bc_table.setFixedHeight(150)
        self.bc_table.setStyleSheet(
            "QTableWidget{background:#181b2a;color:#a0a8c0;border:1px solid #333852;"
            "gridline-color:#2c2e43;} QHeaderView::section{background:#1e2235;"
            "color:#a0a8c0;border:none;padding:3px;}")
        self.bc_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.bc_table.verticalHeader().setVisible(False)
        sec.add_widget(self.bc_table)

        bc_btns = QHBoxLayout()
        bc_btns.setSpacing(4)
        self.bc_add_btn = make_button("Add Row", "#1a2a3a")
        self.bc_remove_btn = make_button("Remove Row", "#301a1a")
        self.bc_default_btn = make_button("Fill Default", "#1a2a3a")
        self.bc_default_btn.setToolTip(
            "Fill segments 1-5 (domain 1-4 → non-reflect, geometry 5 → fixed)")
        bc_btns.addWidget(self.bc_add_btn)
        bc_btns.addWidget(self.bc_remove_btn)
        bc_btns.addWidget(self.bc_default_btn)
        sec.add_layout(bc_btns)
        self.bc_add_btn.clicked.connect(lambda: self._add_bc_row(0, 0))
        self.bc_remove_btn.clicked.connect(self._remove_bc_row)
        self.bc_default_btn.clicked.connect(self._fill_default_bc)

    def _fill_default_bc(self):
        """Populate the standard HybMesh2D group mapping (1-4 domain, 5 geometry)."""
        self.bc_table.setRowCount(0)
        for seg, bc in [(1, 1), (2, 1), (3, 1), (4, 1), (5, 5)]:
            self._add_bc_row(seg, bc)

    # ------------------------------------------------------------------ #
    # BC table helpers
    # ------------------------------------------------------------------ #
    def _add_bc_row(self, seg: int, bc: int):
        r = self.bc_table.rowCount()
        self.bc_table.insertRow(r)
        self.bc_table.setItem(r, 0, QTableWidgetItem(str(seg)))
        self.bc_table.setItem(r, 1, QTableWidgetItem(str(bc)))

    def _remove_bc_row(self):
        rows = sorted({i.row() for i in self.bc_table.selectedItems()}, reverse=True)
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
        self.output_grid_file.setText(cfg.output_grid_file)
        self.output_bc_file.setText(cfg.output_bc_file)

        self.fs_mach.setValue(cfg.fs_mach)
        self.fs_tinf.setValue(cfg.fs_tinf)
        self.fs_unit_re.setValue(cfg.fs_unit_re)
        self.linf.setValue(cfg.linf)
        self.prandtl.setValue(cfg.prandtl)

        self.cfl.setValue(cfg.cfl)
        self.constant_cfl.setChecked(cfg.constant_cfl)
        self.alpha.setValue(cfg.alpha)
        self.beta.setText(f"{cfg.beta:g}")
        self.dissip_ctrl.setText(f"{cfg.dissip_ctrl:g}")
        self.epsilon.setValue(cfg.epsilon)
        self.use_incenter.setChecked(cfg.use_incenter)
        self.dissip_per_cfl.setChecked(cfg.dissip_per_cfl)
        self.unsteady_lstep.setChecked(cfg.unsteady_lstep)

        self.num_half_iter.setValue(cfg.num_half_iter)
        self.print_convg_per_niter.setValue(cfg.print_convg_per_niter)
        self.print_sol_per_niter.setValue(cfg.print_sol_per_niter)

        self.apply_pthread.setChecked(cfg.apply_pthread)
        self.max_nthread.setValue(cfg.max_nthread)
        self.num_zones_per_block.setValue(cfg.num_zones_per_block)

        self.enable_decompose.setChecked(cfg.enable_decompose)
        self.num_partitions.setValue(cfg.num_partitions)

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
            self._add_bc_row(bc.get("segment_no", 0), bc.get("bc_type", 0))

        self._update_ibm_visibility()
        self._update_decompose_visibility()

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
        cfg.output_grid_file = self.output_grid_file.text().strip() or "mesh.grid"
        cfg.output_bc_file = self.output_bc_file.text().strip() or "mesh.bc"

        cfg.fs_mach = self.fs_mach.value()
        cfg.fs_tinf = self.fs_tinf.value()
        cfg.fs_unit_re = self.fs_unit_re.value()
        cfg.linf = self.linf.value()
        cfg.prandtl = self.prandtl.value()

        cfg.cfl = self.cfl.value()
        cfg.constant_cfl = self.constant_cfl.isChecked()
        cfg.alpha = self.alpha.value()
        cfg.beta = _parse_float(self.beta.text(), cfg.beta)
        cfg.dissip_ctrl = _parse_float(self.dissip_ctrl.text(), cfg.dissip_ctrl)
        cfg.epsilon = self.epsilon.value()
        cfg.use_incenter = self.use_incenter.isChecked()
        cfg.dissip_per_cfl = self.dissip_per_cfl.isChecked()
        cfg.unsteady_lstep = self.unsteady_lstep.isChecked()

        cfg.num_half_iter = self.num_half_iter.value()
        cfg.print_convg_per_niter = self.print_convg_per_niter.value()
        cfg.print_sol_per_niter = self.print_sol_per_niter.value()

        cfg.apply_pthread = self.apply_pthread.isChecked()
        cfg.max_nthread = self.max_nthread.value()
        cfg.num_zones_per_block = self.num_zones_per_block.value()

        cfg.enable_decompose = self.enable_decompose.isChecked()
        cfg.num_partitions = self.num_partitions.value()

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
            bc_item = self.bc_table.item(r, 1)
            try:
                seg = int(seg_item.text()) if seg_item else 0
                bc = int(bc_item.text()) if bc_item else 0
            except ValueError:
                continue
            cfg.bc_definitions.append({"segment_no": seg, "bc_type": bc})

        return cfg
