"""Visibility toggles + model sync for SolverConfigPanel, split out as a mixin
(behaviour unchanged). Holds the feature-gated form show/hide helpers, the
restart auto-fill, the preset apply, and the `set_config` / `get_config`
read/write bridge between the panel widgets and a SolverConfig. Every method
references widgets created in the panel's `__init__` / `_build_*` and resolves
via MRO."""
from __future__ import annotations
import os
from PyQt6.QtWidgets import QFormLayout

from app.models.solver_config import SolverConfig, PRESETS, BC_FLAGS_NEEDING_EXTRA
from app.views.panels.solver_config_widgets import _parse_float


class SolverConfigSyncMixin:
    """Visibility toggles, restart auto-fill, preset apply, get/set_config."""

    # ------------------------------------------------------------------ #
    # Visibility toggles
    # ------------------------------------------------------------------ #
    def _set_form_visible(self, form: QFormLayout, visible: bool):
        """Show/hide every row of a form (label + field) so the gated controls
        appear only when their feature is enabled (collapsing the empty space)."""
        for i in range(form.rowCount()):
            for role in (QFormLayout.ItemRole.LabelRole, QFormLayout.ItemRole.FieldRole):
                it = form.itemAt(i, role)
                if it and it.widget():
                    it.widget().setVisible(visible)

    def _update_ibm_visibility(self):
        self._set_form_visible(self._ibm_form, self.immersed_solid.isChecked())

    def _update_decompose_visibility(self):
        self._set_form_visible(self._decompose_form, self.enable_decompose.isChecked())

    def _update_shock_visibility(self):
        self._set_form_visible(self._shock_form, self.enable_shock.isChecked())

    def _update_restart_visibility(self):
        self._set_form_visible(self._restart_form, self.restart.isChecked())

    def _autofill_restart_from_last_run(self):
        """When the user turns Restart on with empty fields, pre-fill them from
        this case's last run. The solver writes the zone-dump/convergence files
        into results/solver/<case>/work/ with a tag suffix (.gui for GUI runs,
        .cli for headless), which is easy to miss — so point the fields at the
        actual filenames instead of leaving the user to hunt for them."""
        if self._loading or not self.restart.isChecked():
            return
        try:
            from app.services.solver_case import sanitize_case_name
            from app.utils import repo_root
        except Exception:
            return
        case = sanitize_case_name(self.case_name.text().strip() or "case")
        work = os.path.join(repo_root(), "results", "solver", case, "work")
        if not os.path.isdir(work):
            return

        def _pick(stem: str) -> str:
            # GUI solves tag outputs ".gui"; prefer that, fall back to ".cli".
            for tag in (".gui", ".cli"):
                p = os.path.join(work, stem + tag)
                if os.path.exists(p):
                    return p
            return ""

        if not self.zdump_fn_restart.text().strip():
            z = _pick("binDumpZ.dat")
            if z:
                self.zdump_fn_restart.setText(z)
        if not self.convg_fn_restart.text().strip():
            c = _pick("unicones.enorm")
            if c:
                self.convg_fn_restart.setText(c)

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
        self._loading = True   # suppress restart auto-fill during programmatic load
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
        self.linf_from_unit.setChecked(bool(getattr(cfg, "linf_from_unit", True)))
        self._sync_linf_mode()
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
        self.ibm_phi_file.setText(cfg.ibm_phi_file)

        self.bc_table.setRowCount(0)
        for bc in cfg.bc_definitions:
            self._add_bc_row(bc.get("segment_no", 0), bc.get("bc_type", 0),
                             str(bc.get("values", "") or ""),
                             str(bc.get("name", "") or ""))

        self._update_ibm_visibility()
        self._update_decompose_visibility()
        self._update_shock_visibility()
        self._update_restart_visibility()
        self._loading = False

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
        cfg.linf_from_unit = self.linf_from_unit.isChecked()
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
        cfg.ibm_phi_file = self.ibm_phi_file.text().strip()

        cfg.bc_definitions = []
        for r in range(self.bc_table.rowCount()):
            seg_item = self.bc_table.item(r, 0)
            name_item = self.bc_table.item(r, 1)
            combo = self.bc_table.cellWidget(r, 2)
            val_item = self.bc_table.item(r, 3)
            try:
                seg = int(seg_item.text()) if seg_item else 0
            except (ValueError, AttributeError):
                continue
            bc = int(combo.currentData()) if combo is not None else 0
            values = val_item.text().strip() if val_item else ""
            name = name_item.text().strip() if name_item else ""
            # Only keep the extra value for types that actually use one.
            if bc not in BC_FLAGS_NEEDING_EXTRA:
                values = ""
            cfg.bc_definitions.append(
                {"segment_no": seg, "bc_type": bc, "values": values, "name": name})

        return cfg
