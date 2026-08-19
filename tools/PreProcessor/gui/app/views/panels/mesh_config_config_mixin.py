"""Geometry-list / role handlers and the get_config / set_config round-trip for
MeshConfigPanel, split out as a mixin (behaviour unchanged). These methods read
and write the widgets, geom_list_widget item data (_ROLE_DATA / UserRole),
_group_bc, _global_bl and the BL edit scope created in the panel's __init__, and
emit geom_files_changed / mesh_config_changed / geom_selection_changed. They
resolve widgets and the BL / visibility helpers (_read_bl_widgets,
_apply_global_bl_to_cfg, _sync_bl_scope, _update_role_visibility,
_update_domain_source_visibility, _update_bidirectional_visibility,
_update_auto_*_hint) via the host class MRO."""
from __future__ import annotations
import os
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QListWidgetItem, QFileDialog
from app.models.mesh_config import MeshConfig
from app.utils import block_signals
from app.views.panels.field_widgets import read_specs, write_specs
from app.views.panels.mesh_bl_field_specs import PANEL_BL_SPECS
from app.views.panels.mesh_field_specs import MESH_SPECS


class MeshConfigConfigMixin:
    """Geometry/role handlers plus get_config / set_config for MeshConfigPanel."""

    # ── Per-geometry boundary layer (inline) ──────────────────────────────
    def _on_browse_geom(self):
        """Prompt file dialog to select external geometry files."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Geometry File", "", "Geometry Files (*.dat);;All Files (*)"
        )
        for f in files:
            # We want to display the relative path or absolute path
            # For simplicity, store absolute path but list basename
            item = QListWidgetItem(os.path.basename(f))
            item.setData(Qt.ItemDataRole.UserRole, f)
            self.geom_list_widget.addItem(item)

        geom_files = []
        for row in range(self.geom_list_widget.count()):
            geom_files.append(self.geom_list_widget.item(row).data(Qt.ItemDataRole.UserRole))
        self.geom_files_changed.emit(geom_files)

    def _on_remove_geom(self):
        """Remove selected geometry file from the list."""
        for item in self.geom_list_widget.selectedItems():
            self.geom_list_widget.takeItem(self.geom_list_widget.row(item))

        geom_files = []
        for row in range(self.geom_list_widget.count()):
            geom_files.append(self.geom_list_widget.item(row).data(Qt.ItemDataRole.UserRole))
        self.geom_files_changed.emit(geom_files)

    def _on_geom_selection_changed(self, current, previous=None):
        """Populate the role editor from the geometry selected in the list."""
        self._role_updating = True
        try:
            if current is None:
                self.geom_role_combo.setEnabled(False)
                self.geom_role_combo.setCurrentIndex(0)
                self.seed_size.setValue(0.0)
                self.seed_radius.setValue(0.0)
                self.seed_mode.setCurrentIndex(0)
                self.geom_bc_combo.setCurrentText("")
            else:
                self.geom_role_combo.setEnabled(True)
                rinfo = current.data(self._ROLE_DATA)
                role_name = rinfo.get("role") if rinfo else None
                self.geom_bc_combo.setCurrentText(rinfo.get("bc", "") if rinfo else "")
                # "bl" is a boundary that grows a BL with per-geometry overrides,
                # so it maps to the same combo entry as a plain boundary.
                role_to_index = {None: 0, "bl": 0, "nobl": 1, "seed": 2,
                                 "farfield": 3, "wall": 4}
                self.geom_role_combo.setCurrentIndex(role_to_index.get(role_name, 0))
                if role_name == "seed":
                    self.seed_size.setValue(float(rinfo.get("size") or 0.0))
                    self.seed_radius.setValue(float(rinfo.get("radius") or 0.0))
                    self.seed_mode.setCurrentIndex(1 if rinfo.get("mode") == "embed" else 0)
                else:
                    self.seed_size.setValue(0.0)
                    self.seed_radius.setValue(0.0)
                    self.seed_mode.setCurrentIndex(0)
        finally:
            self._role_updating = False
        self._update_role_visibility()
        # Point the BL sections at this geometry's override (or the global default).
        self._sync_bl_scope()
        # Tell the canvas which geometry is selected so it can highlight it.
        path = current.data(Qt.ItemDataRole.UserRole) if current is not None else ""
        self.geom_selection_changed.emit(path or "")

    def _on_role_edited(self, *args):
        """Commit the role editor state onto the selected geometry item and
        re-emit the config so previews re-style boundary vs seed."""
        if self._role_updating:
            return
        item = self.geom_list_widget.currentItem()
        if item is None:
            return
        # Carry any existing per-geometry BL override + wall BC across role
        # changes (BL only survives between the BL-growing roles).
        prev = item.data(self._ROLE_DATA) or {}
        bl_params = prev.get("bl_params")
        bc = prev.get("bc")
        idx = self.geom_role_combo.currentIndex()
        if idx == 2:  # Seed (no wall BC / BL)
            size = self.seed_size.value()
            radius = self.seed_radius.value()
            item.setData(self._ROLE_DATA, {
                "role": "seed",
                "size": size if size > 0 else None,
                # radius is independent of size (an explicit radius is kept even
                # when the size is auto).
                "radius": radius if radius > 0 else None,
                "mode": "embed" if self.seed_mode.currentIndex() == 1 else "source",
            })
        elif idx == 1:   # No-BL obstacle (conform at far-field size)
            rinfo = {"role": "nobl"}
            if bc:
                rinfo["bc"] = bc
            item.setData(self._ROLE_DATA, rinfo)
        elif idx == 3:   # Domain: far-field outline (external, no BL)
            rinfo = {"role": "farfield"}
            if bc:
                rinfo["bc"] = bc
            item.setData(self._ROLE_DATA, rinfo)
        elif idx == 4:   # Domain: wall (internal flow, BL grows inward)
            rinfo = {"role": "wall"}
            if bl_params:
                rinfo["bl_params"] = bl_params
            if bc:
                rinfo["bc"] = bc
            item.setData(self._ROLE_DATA, rinfo)
        else:            # Boundary obstacle (grows BL)
            if bl_params or bc:
                rinfo = {"role": "bl"}
                if bl_params:
                    rinfo["bl_params"] = bl_params
                if bc:
                    rinfo["bc"] = bc
                item.setData(self._ROLE_DATA, rinfo)
            else:
                item.setData(self._ROLE_DATA, None)
        self._update_role_visibility()
        # A role change may enable/disable overriding; re-point the BL sections.
        self._sync_bl_scope()
        self.mesh_config_changed.emit(self.get_config())

    def _on_geom_bc_edited(self, *args):
        """Commit the per-geometry wall BC / patch name onto the selected item."""
        if self._role_updating:
            return
        item = self.geom_list_widget.currentItem()
        if item is None:
            return
        bc = self.geom_bc_combo.currentText().strip()
        rinfo = dict(item.data(self._ROLE_DATA) or {})
        if bc:
            if not rinfo.get("role"):
                rinfo["role"] = "bl"   # a plain boundary needs a dict to carry bc
            rinfo["bc"] = bc
            item.setData(self._ROLE_DATA, rinfo)
        else:
            rinfo.pop("bc", None)
            # Drop the role entry if nothing meaningful is left on it.
            if rinfo.get("role") == "bl" and not rinfo.get("bl_params"):
                item.setData(self._ROLE_DATA, None)
            else:
                item.setData(self._ROLE_DATA, rinfo or None)
        self.mesh_config_changed.emit(self.get_config())

    def set_config(self, cfg: MeshConfig):
        """Populate widget values from a MeshConfig model instance."""
        # `_loading` tells the controller's panel->model sync that the widgets are
        # mid-population, so a valueChanged fired here is NOT a user edit and must not
        # be read back into the model. Deliberately a fact the PANEL knows rather than
        # something the caller must remember: a direct set_config that forgets
        # push_panel_config should cost a spurious undo step, never a corrupted model.
        self._loading = True
        try:
            self._set_config_body(cfg)
        finally:
            self._loading = False

    def _set_config_body(self, cfg: MeshConfig):
        # Suppress the BL change handler while bulk-populating, and reset the BL
        # edit scope to global; the selection sync at the end re-points it.
        self._bl_updating = True
        self._bl_target_item = None
        # 0. Units — applied before the length fields so their suffixes are already
        # right when the values land, rather than flickering from the old unit.
        self._units_from_config(cfg)

        # 1. Every declared field, in one traversal: the domain box, mesh sizing, all
        # 21 BL parameters, the meshing algorithm, the four domain patch names and the
        # write formats. Output File is skipped here (host_writes) — its population is
        # the heuristic below, which reads the widget's own current text.
        write_specs(self, MESH_SPECS, cfg)
        write_specs(self, PANEL_BL_SPECS, cfg)

        # Domain source: a geometry acting as the outer domain → Custom; an
        # external-flow config with geometries but no domain outline → Rectangle
        # box; a fresh/empty config → default to Custom geometry (#1: entering the
        # mesh generator defaults to Custom).
        if cfg.domain_file:
            dsrc = 1
        elif cfg.geom_files:
            dsrc = 0
        else:
            dsrc = 1
        with block_signals(self.domain_source_combo):
            self.domain_source_combo.setCurrentIndex(dsrc)
        self._update_domain_source_visibility()
        self._update_bidirectional_visibility()   # #7: outer growth rate follows it

        # Geometries (with per-file role carried as item data). Block selection
        # signals during the rebuild, then resync the role editor once.
        with block_signals(self.geom_list_widget):
            self.geom_list_widget.clear()
            for f in cfg.geom_files:
                item = QListWidgetItem(os.path.basename(f))
                item.setData(Qt.ItemDataRole.UserRole, f)
                rinfo = cfg.geom_roles.get(f)
                if rinfo:
                    item.setData(self._ROLE_DATA, dict(rinfo))
                self.geom_list_widget.addItem(item)

        # #4: per-group BC-type assignments carried on the config.
        self._group_bc = dict(cfg.group_bc or {})
        # Self-heal the label->BC-type map from each geometry's .meta trailer, so
        # a session reset / config reload that dropped group_bc still resolves the
        # labels in the .meta (otherwise every boundary falls back to the wall
        # default at mesh time). An explicit GROUP_BC from the config stays
        # authoritative (setdefault only fills gaps).
        from app.services.meta_io import read_meta_group_bc
        for gf in (cfg.geom_files or []):
            for label, bc in read_meta_group_bc(gf).items():
                self._group_bc.setdefault(label, bc)

        # #3: adopt the config's configured-state (the patch names above are written
        # under _bl_updating, so _mark_bc_configured did not see them as user edits).
        self._bc_configured = getattr(cfg, "bc_configured", True)
        # bc_geom is no longer a panel field; the model default (a geometry's wall
        # patch) is set per-geometry (Wall BC) / per-segment instead.

        # Suggested name from BOUNDARY geometries only (seeds share geom_files
        # but shouldn't drive the name).
        # Suggested name is per-case (results/meshes/<case>/mesh_<case>.*) so
        # each geometry set exports into its own subfolder. FORMAT_PLACEHOLDER is
        # not an extension — this field is where it enters the model, and every
        # consumer resolves it through MeshConfig.output_base / output_path_for.
        boundaries = cfg.boundary_files
        default_name = MeshConfig.auto_output_name(
            [] if (not cfg.geom_files or len(boundaries) == 0) else boundaries,
            ext=MeshConfig.FORMAT_PLACEHOLDER,
        )
        # An auto-generated name is refreshed to match the current geometry so
        # switching geometries changes the export name; a name the user typed
        # is kept.
        incoming = (cfg.output_filename or "").strip()
        widget_text = self.output_filename.text().strip()
        if incoming and not MeshConfig.is_auto_output_name(incoming):
            # Explicit custom name carried in the config (e.g. a loaded file).
            self.output_filename.setText(incoming)
            self._output_name_user_set = True
        elif (self._output_name_user_set and widget_text
                and not MeshConfig.is_auto_output_name(widget_text)):
            # Keep the custom name the user already typed into the field.
            pass
        else:
            self.output_filename.setText(default_name)
            self._output_name_user_set = False

        # The BL widgets now hold cfg's global defaults — snapshot them as the
        # authoritative global BL, then release the population guard.
        self._global_bl = self._read_bl_widgets()
        self._bl_updating = False

        # Sync the role editor + BL override scope + canvas highlight to the
        # current selection (may re-point the BL sections to a geometry override).
        self._on_geom_selection_changed(self.geom_list_widget.currentItem())

        # #6: refresh the auto size hints now the checkboxes + domain/geoms are set.
        self._update_auto_farfield_hint()
        self._update_auto_surface_hint()

        # Update canvas preview geometries and config
        self.mesh_config_changed.emit(cfg)

    def get_config(self) -> MeshConfig:
        """Collect widget values and return a MeshConfig model instance."""
        cfg = MeshConfig()

        # 0. Units — read first so anything below that wants to reason about
        # magnitude has the unit available on cfg.
        self._units_to_config(cfg)

        # 1. Every declared field the panel's own widgets author, in one traversal.
        read_specs(self, MESH_SPECS, cfg)

        # 2. The 21 BL fields come from the authoritative global-BL store, NOT from
        # the widgets — so a per-geometry override that happened to be shown cannot
        # be mistaken for the global value. That is why PANEL_BL_SPECS is written to
        # the widgets above but read from _global_bl here.
        self._apply_global_bl_to_cfg(cfg)

        # 3. Facts one widget holds for many things (see MESH_EXTRA_AUTHORED).
        cfg.geom_files = []
        cfg.geom_roles = {}
        for row in range(self.geom_list_widget.count()):
            item = self.geom_list_widget.item(row)
            p = item.data(Qt.ItemDataRole.UserRole)
            cfg.geom_files.append(p)
            rinfo = item.data(self._ROLE_DATA)
            if rinfo and rinfo.get("role") in ("seed", "nobl", "farfield", "wall", "bl"):
                cfg.geom_roles[p] = dict(rinfo)

        # #4: per-group BC-type assignments (kept separate from the group names).
        cfg.group_bc = dict(self._group_bc)
        cfg.bc_configured = getattr(self, "_bc_configured", False)  # #3
        # cfg.bc_geom keeps its model default (geometry wall patch) — it is not a
        # panel field; per-geometry / per-segment names override it.

        return cfg

    def current_geom_roles(self) -> dict:
        """Return {path: role_dict} for the seed geometries currently listed,
        read straight from item data — no full MeshConfig rebuild. Used by the
        live preview path so a geom-file change doesn't re-parse every widget."""
        roles = {}
        for row in range(self.geom_list_widget.count()):
            item = self.geom_list_widget.item(row)
            rinfo = item.data(self._ROLE_DATA)
            if rinfo and rinfo.get("role") == "seed":
                roles[item.data(Qt.ItemDataRole.UserRole)] = rinfo
        return roles
