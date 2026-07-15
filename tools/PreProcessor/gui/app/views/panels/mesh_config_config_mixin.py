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
        # Suppress the BL change handler while bulk-populating, and reset the BL
        # edit scope to global; the selection sync at the end re-points it.
        self._bl_updating = True
        self._bl_target_item = None
        # 1. Domain
        self.domain_x_min.setValue(cfg.domain_x_min)
        self.domain_x_max.setValue(cfg.domain_x_max)
        self.domain_y_min.setValue(cfg.domain_y_min)
        self.domain_y_max.setValue(cfg.domain_y_max)
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
        self.domain_source_combo.blockSignals(True)
        self.domain_source_combo.setCurrentIndex(dsrc)
        self.domain_source_combo.blockSignals(False)
        self._update_domain_source_visibility()

        # Geometries (with per-file role carried as item data). Block selection
        # signals during the rebuild, then resync the role editor once.
        self.geom_list_widget.blockSignals(True)
        self.geom_list_widget.clear()
        for f in cfg.geom_files:
            item = QListWidgetItem(os.path.basename(f))
            item.setData(Qt.ItemDataRole.UserRole, f)
            rinfo = cfg.geom_roles.get(f)
            if rinfo:
                item.setData(self._ROLE_DATA, dict(rinfo))
            self.geom_list_widget.addItem(item)
        self.geom_list_widget.blockSignals(False)

        # #4: per-group BC-type assignments carried on the config.
        self._group_bc = dict(cfg.group_bc or {})

        # 2. Sizing
        self.surface_mesh_size.setValue(cfg.surface_mesh_size)
        self.auto_surface_size.setChecked(cfg.auto_surface_size)
        self.farfield_mesh_size.setValue(cfg.farfield_mesh_size)
        self.auto_farfield_size.setChecked(cfg.auto_farfield_size)
        self.farfield_growth_rate.setValue(cfg.farfield_growth_rate)
        # #7: bidirectional far-field grading
        self.farfield_bidirectional.setChecked(cfg.farfield_bidirectional)
        self.farfield_growth_rate_outer.setValue(cfg.farfield_growth_rate_outer)
        self._update_bidirectional_visibility()

        # 3. BL Core
        self.bl_initial_thickness.setValue(cfg.bl_initial_thickness)
        self.bl_growth_rate.setValue(cfg.bl_growth_rate)
        self.bl_layers.setValue(cfg.bl_layers)

        # 4. Convex
        convex_methods = [0, 2]
        if cfg.bl_convex_method in convex_methods:
            self.bl_convex_method.setCurrentIndex(convex_methods.index(cfg.bl_convex_method))
        else:
            self.bl_convex_method.setCurrentIndex(1)
        self.bl_fan_nodes.setValue(cfg.bl_fan_nodes)
        self.bl_auto_fan_nodes.setChecked(cfg.bl_auto_fan_nodes)
        self.bl_fan_angle_threshold.setValue(cfg.bl_fan_angle_threshold)
        self.bl_convex_angle_threshold.setValue(cfg.bl_convex_angle_threshold)
        self.bl_para_fallback_angle.setValue(cfg.bl_para_fallback_angle)

        # 5. Concave
        concave_methods = [5]
        if cfg.bl_concave_method in concave_methods:
            self.bl_concave_method.setCurrentIndex(concave_methods.index(cfg.bl_concave_method))
        else:
            self.bl_concave_method.setCurrentIndex(0)
        self.bl_concave_angle_threshold.setValue(cfg.bl_concave_angle_threshold)
        self.bl_concave_influence_multiplier.setValue(cfg.bl_concave_influence_multiplier)
        self.bl_merge_concave.setChecked(cfg.bl_merge_concave)
        self.bl_smoothing_iters.setValue(cfg.bl_smoothing_iters)

        # 6. Transition
        self.bl_transition_layers.setValue(cfg.bl_transition_layers)
        self.bl_auto_transition_layers.setCurrentIndex(cfg.bl_auto_transition_layers)
        self.bl_transition_growth_rate.setValue(cfg.bl_transition_growth_rate)
        self.bl_transition_buffer.setValue(cfg.bl_transition_buffer)

        gmsh_algos = [1, 2, 5, 6, 7, 8]
        if cfg.gmsh_algorithm in gmsh_algos:
            self.gmsh_algorithm.setCurrentIndex(gmsh_algos.index(cfg.gmsh_algorithm))
        else:
            self.gmsh_algorithm.setCurrentIndex(3)  # default: 6
        self.gmsh_optimize.setChecked(cfg.gmsh_optimize != 0)
        self.bl_use_analytic_geom.setChecked(bool(cfg.bl_use_analytic_geom))

        # 7. Domain boundary patches (rectangle-box edges) + output
        self.bc_xmin.setText(cfg.bc_xmin)
        self.bc_xmax.setText(cfg.bc_xmax)
        self.bc_ymin.setText(cfg.bc_ymin)
        self.bc_ymax.setText(cfg.bc_ymax)
        # bc_geom is no longer a panel field; the model default (a geometry's wall
        # patch) is set per-geometry (Wall BC) / per-segment instead.

        # Suggested name from BOUNDARY geometries only (seeds share geom_files
        # but shouldn't drive the name).
        boundaries = cfg.boundary_files
        if not cfg.geom_files or len(boundaries) == 0:
            default_name = "results/meshes/mesh_cartesian.*"
        elif len(boundaries) == 1:
            stem = os.path.splitext(os.path.basename(boundaries[0]))[0]
            default_name = f"results/meshes/mesh_{stem}.*"
        else:
            # Multiple boundaries: name after all their stems so different
            # geometry sets still export to distinct files.
            stems = "_".join(os.path.splitext(os.path.basename(b))[0]
                             for b in boundaries)
            default_name = f"results/meshes/mesh_{stems}.*"
        # An auto-generated name (empty, or the "results/meshes/mesh_*" pattern
        # we produce) is refreshed to match the current geometry so switching
        # geometries changes the export name; a name the user typed is kept.
        def _is_auto(name: str) -> bool:
            return (not name) or name.startswith("results/meshes/mesh_")

        incoming = (cfg.output_filename or "").strip()
        widget_text = self.output_filename.text().strip()
        if incoming and not _is_auto(incoming):
            # Explicit custom name carried in the config (e.g. a loaded file).
            self.output_filename.setText(incoming)
            self._output_name_user_set = True
        elif self._output_name_user_set and widget_text and not _is_auto(widget_text):
            # Keep the custom name the user already typed into the field.
            pass
        else:
            self.output_filename.setText(default_name)
            self._output_name_user_set = False

        self.export_vtk.setChecked(cfg.export_vtk)
        self.export_starcd.setChecked(cfg.export_starcd)
        self.export_cgns.setChecked(cfg.export_cgns)
        self.enable_collision_detection.setChecked(cfg.enable_collision_detection)

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

        # 1. Domain
        cfg.domain_x_min = self.domain_x_min.value()
        cfg.domain_x_max = self.domain_x_max.value()
        cfg.domain_y_min = self.domain_y_min.value()
        cfg.domain_y_max = self.domain_y_max.value()

        # Geometries (+ per-file role read back from item data)
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

        # 2. Sizing
        cfg.surface_mesh_size = self.surface_mesh_size.value()
        cfg.auto_surface_size = self.auto_surface_size.isChecked()
        cfg.farfield_mesh_size = self.farfield_mesh_size.value()
        cfg.auto_farfield_size = self.auto_farfield_size.isChecked()
        cfg.farfield_growth_rate = self.farfield_growth_rate.value()
        # #7: bidirectional far-field grading
        cfg.farfield_bidirectional = self.farfield_bidirectional.isChecked()
        cfg.farfield_growth_rate_outer = self.farfield_growth_rate_outer.value()

        # 3-6. Boundary layer: the override-able fields come from the
        # authoritative global-BL store (so a per-geometry override currently
        # shown in the widgets is not mistaken for the global value).
        self._apply_global_bl_to_cfg(cfg)

        # Non-override BL / meshing fields are always global — read from widgets.
        cfg.bl_merge_concave = self.bl_merge_concave.isChecked()
        cfg.bl_smoothing_iters = self.bl_smoothing_iters.value()
        gmsh_algos = [1, 2, 5, 6, 7, 8]
        cfg.gmsh_algorithm = gmsh_algos[self.gmsh_algorithm.currentIndex()]
        cfg.gmsh_optimize = 1 if self.gmsh_optimize.isChecked() else 0

        # 7. Domain boundary patches (rectangle-box edges) + output.
        # cfg.bc_geom keeps its model default (geometry wall patch) — it is no
        # longer a panel field; per-geometry / per-segment names override it.
        cfg.bc_xmin = self.bc_xmin.text().strip()
        cfg.bc_xmax = self.bc_xmax.text().strip()
        cfg.bc_ymin = self.bc_ymin.text().strip()
        cfg.bc_ymax = self.bc_ymax.text().strip()
        cfg.output_filename = self.output_filename.text().strip()

        cfg.export_vtk = self.export_vtk.isChecked()
        cfg.export_starcd = self.export_starcd.isChecked()
        cfg.export_cgns = self.export_cgns.isChecked()
        cfg.enable_collision_detection = self.enable_collision_detection.isChecked()

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
