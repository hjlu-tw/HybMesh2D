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
from app.views.panels.field_widgets import read_specs, write_specs
from app.views.panels.solver_field_specs import SOLVER_SPECS


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
            from app.services.case_files import RUN_TAGS
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
            # RUN_TAGS in that order, from the one module that declares them.
            for tag in RUN_TAGS:
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
        # `_loading` suppresses the restart auto-fill AND tells the controller's
        # panel->model sync that these widget signals are population, not user edits.
        # try/finally: an exception mid-population used to leave the flag stuck True,
        # which now means the panel would never sync again — silently stale.
        self._loading = True
        try:
            self._set_config_body(cfg)
        finally:
            self._loading = False

    def _set_config_body(self, cfg: SolverConfig):
        # Every declared field in one traversal (SOLVER_SPECS): binaries, grid files,
        # flow conditions, turbulence, numerics + shock, iteration control, output +
        # probes, restart + initial condition, parallel, decomposition and IBM.
        write_specs(self, SOLVER_SPECS, cfg)
        # Linf is read-only while it is derived from the model unit, so the mode has
        # to be re-applied after the value lands.
        self._sync_linf_mode()

        # The BC table is a table of ROWS, not a field: one per mesh segment, with the
        # patch name it was given upstream and the BC type chosen for it.
        self.bc_table.setRowCount(0)
        for bc in cfg.bc_definitions:
            self._add_bc_row(bc.get("segment_no", 0), bc.get("bc_type", 0),
                             str(bc.get("values", "") or ""),
                             str(bc.get("name", "") or ""))

        self._update_ibm_visibility()
        self._update_decompose_visibility()
        self._update_shock_visibility()
        self._update_restart_visibility()

    def get_config(self, cfg: SolverConfig | None = None) -> SolverConfig:
        cfg = cfg or SolverConfig()
        # One traversal back. A gfloat (beta / dissip_ctrl / the shock parameters) that
        # does not parse keeps the value cfg already holds, which is the fallback the
        # hand-written `_parse_float(self.beta.text(), cfg.beta)` calls had.
        read_specs(self, SOLVER_SPECS, cfg)

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
