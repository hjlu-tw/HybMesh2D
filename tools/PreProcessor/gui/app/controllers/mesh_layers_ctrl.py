from __future__ import annotations
import os
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QListWidgetItem
from app.utils import block_signals, report_info

class MeshLayersControllerMixin:
    """Mixin managing the Geometry Layers list of the mesh generator — syncing
    sessions/external files into the panel and adding/removing geometry from the
    global mesh config."""

    def add_active_preprocessor_geometry(self):
        """Auto-add the resampled output file of the active PreProcessor session into the mesh generator input list."""
        session = self.active_session()
        if not session:
            self.main_window.log_panel.log("No active session. Please create or import geometry first.")
            return

        if not session.project_model.output_file:
            self.main_window.log_panel.log(
                "No resampled output file specified. Run 'Save & Export' in PreProcessor mode first."
            )
            return

        path = session.project_model.output_file
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            self.main_window.log_panel.log(
                f"Resampled file does not exist at '{abs_path}'. Run 'Save & Export' first."
            )
            return

        cfg = self.main_window.mesh_config_panel.get_config()
        if abs_path not in cfg.geom_files:
            cfg.geom_files.append(abs_path)
            self.global_mesh_config = cfg
            self.push_panel_config(self.main_window.mesh_config_panel, cfg)
            self.main_window.log_panel.log(f"Added resampled geometry to configuration: {abs_path}")
            self.sync_mesh_layers_panel()
        else:
            self.main_window.log_panel.log("Geometry file is already in the list.")

    def _sync_global_scalars_from_panel(self):
        """Merge the mesh panel's CURRENT numeric/scalar edits into
        global_mesh_config before a set_config re-apply, so a value the user just
        typed (domain bounds, mesh sizes, growth rate, BL params, output name, …)
        is not clobbered by the stale stored config. The geometry list, per-file
        roles and per-group BC are OWNED by the layer ops here and left untouched.

        Fix: numeric spinbox edits were never written back to global_mesh_config
        (only role/BC edits were), so add/remove/toggle-geometry — which re-apply
        global_mesh_config via set_config — snapped those values back to their old
        stored value."""
        # Delegates to the single panel->model sync (N8: one data-flow direction).
        # The extra-preserve set is what makes THIS call site different: the geometry
        # list, per-file roles and per-group BC are mid-mutation by the layer operation
        # running right now, so the stored value must win over the panel for those
        # three. Fields the panel simply cannot author (bc_geom, missing_geom_files)
        # are preserved by panel_sync_ctrl itself and are no longer duplicated here —
        # keeping two copies of that list is how they drifted apart in the first place.
        self.sync_panel_to_model(
            "mesh_config_panel",
            extra_preserve=("geom_files", "geom_roles", "group_bc"))

    def remove_session_from_mesh_config(self, session) -> None:
        """Drop a deleted CAD session's exported geometry from the mesh
        generator input list.

        CAD layers and the mesh geometry list are otherwise decoupled (closing
        a tab keeps its geometry in the mesh), but an explicit *delete* should
        also remove it from the mesh — and only that one file, so the remaining
        geometries of a multi-geometry mesh are preserved. No-op when the
        deleted geometry was never added to the mesh."""
        pm = getattr(session, "project_model", None)
        out_file = pm.output_file if pm else ""
        cfg = self.global_mesh_config
        if not cfg or not out_file:
            return
        abs_out = os.path.abspath(out_file)
        before = len(cfg.geom_files)
        cfg.geom_files = [p for p in cfg.geom_files if os.path.abspath(p) != abs_out]
        if len(cfg.geom_files) == before:
            return  # this geometry was not part of the mesh
        cfg.prune_roles()  # drop the removed geometry's seed role, if any

        # Keep the panel (the authority at generate time) and the canvas
        # previews in sync with the pruned list — preserving live numeric edits.
        self._sync_global_scalars_from_panel()
        self.push_panel_config(self.main_window.mesh_config_panel, cfg)
        self.sync_mesh_layers_panel()
        self.main_window.log_panel.log(
            f"Removed deleted geometry '{os.path.basename(abs_out)}' from the "
            "mesh generator input list."
        )

    def sync_mesh_layers_panel(self):
        """Update the Geometry Layers QListWidget in the MeshConfigPanel based on current sessions."""
        panel = self.main_window.mesh_config_panel
        if not hasattr(panel, 'layers_list_widget'):
            return

        with block_signals(panel.layers_list_widget):
            panel.layers_list_widget.clear()

            for session in self.sessions:
                name = session.display_name
                out_file = session.project_model.output_file
                display_text = name

                abs_out_file = ""
                if out_file:
                    abs_out_file = os.path.abspath(out_file)
                    if not os.path.exists(abs_out_file):
                        display_text += " (not exported)"
                else:
                    display_text += " (no output file)"

                item = QListWidgetItem(display_text)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

                if abs_out_file and abs_out_file in self.global_mesh_config.geom_files:
                    item.setCheckState(Qt.CheckState.Checked)
                else:
                    item.setCheckState(Qt.CheckState.Unchecked)

                item.setData(Qt.ItemDataRole.UserRole, (session.session_id, abs_out_file))
                if hasattr(session, "color") and session.color:
                    item.setForeground(QColor(session.color))

                panel.layers_list_widget.addItem(item)

            # Surface any geometry files that WILL be meshed but are not backed by a
            # live CAD layer (e.g. loaded from a saved mesh config, browsed in, or
            # left over from a closed tab). They would otherwise be invisible here
            # yet still meshed — so list them explicitly, checked, with uncheck =
            # remove, giving one complete view of what the mesh will contain.
            session_outs = set()
            for session in self.sessions:
                out_file = session.project_model.output_file
                if out_file:
                    session_outs.add(os.path.abspath(out_file))

            for gf in self.global_mesh_config.geom_files:
                abs_gf = os.path.abspath(gf)
                if abs_gf in session_outs:
                    continue
                tag = "external file" if os.path.exists(abs_gf) else "missing file"
                item = QListWidgetItem(f"{os.path.basename(abs_gf)}  ({tag})")
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked)
                # session_id None marks an external/orphan entry: uncheck to remove.
                item.setData(Qt.ItemDataRole.UserRole, (None, abs_gf))
                item.setForeground(QColor("#8a93ad"))
                item.setToolTip(
                    "Geometry file included in the mesh but not tied to a CAD "
                    "layer.\nUncheck to remove it from the mesh."
                )
                panel.layers_list_widget.addItem(item)


    def handle_mesh_layer_toggled(self, item: QListWidgetItem):
        """Called when a geometry layer checkbox is checked or unchecked in the Mesh Generator panel."""
        data = item.data(Qt.ItemDataRole.UserRole)
        if not data:
            return
        session_id, abs_out_file = data

        # session_id None => an external/orphan geometry file (in the mesh but
        # not tied to a live CAD layer). The only meaningful action is to drop
        # it from the mesh; unchecking removes it from the geometry list.
        if session_id is None:
            if item.checkState() != Qt.CheckState.Checked and abs_out_file:
                self.global_mesh_config.geom_files = [
                    p for p in self.global_mesh_config.geom_files
                    if os.path.abspath(p) != os.path.abspath(abs_out_file)
                ]
                self.global_mesh_config.prune_roles()
                self._sync_global_scalars_from_panel()
                self.push_panel_config(self.main_window.mesh_config_panel, self.global_mesh_config)
                self.sync_mesh_layers_panel()
                self.main_window.log_panel.log(
                    f"Removed external geometry '{os.path.basename(abs_out_file)}' "
                    "from the mesh geometry list."
                )
            return

        session = None
        for s in self.sessions:
            if s.session_id == session_id:
                session = s
                break

        if not session:
            return

        is_checked = item.checkState() == Qt.CheckState.Checked

        if is_checked:
            if not abs_out_file or not os.path.exists(abs_out_file):
                report_info(
                    self.main_window,
                    "Geometry Not Exported",
                    f"The geometry '{session.display_name}' has not been saved/exported yet.\n"
                    "Please switch to CAD mode and run 'Save & Export' first."
                )
                panel = self.main_window.mesh_config_panel
                with block_signals(panel.layers_list_widget):
                    item.setCheckState(Qt.CheckState.Unchecked)
                return

            if abs_out_file not in self.global_mesh_config.geom_files:
                self.global_mesh_config.geom_files.append(abs_out_file)
        else:
            if abs_out_file in self.global_mesh_config.geom_files:
                self.global_mesh_config.geom_files.remove(abs_out_file)
                self.global_mesh_config.prune_roles()

        self._sync_global_scalars_from_panel()
        self.push_panel_config(self.main_window.mesh_config_panel, self.global_mesh_config)

    def add_all_sessions_to_mesh(self):
        """Add all sessions that have valid exported output files to the global mesh config."""
        added_any = False
        missing_exports = []
        for session in self.sessions:
            out_file = session.project_model.output_file
            if out_file:
                abs_out = os.path.abspath(out_file)
                if os.path.exists(abs_out):
                    if abs_out not in self.global_mesh_config.geom_files:
                        self.global_mesh_config.geom_files.append(abs_out)
                        added_any = True
                else:
                    missing_exports.append(session.display_name)
            else:
                missing_exports.append(session.display_name)

        if missing_exports:
            names = ", ".join(missing_exports)
            self.main_window.log_panel.log(
                f"[WARNING] The following sessions cannot be added because they have not been exported yet: {names}"
            )

        if added_any or not missing_exports:
            panel = self.main_window.mesh_config_panel
            # Preserve the user's Domain Source choice — set_config derives it
            # from the roles, which would otherwise snap it back to "Rectangle
            # box" after Add All even if the user had picked Custom geometry.
            prev_src = panel.domain_source_combo.currentIndex()
            self._sync_global_scalars_from_panel()
            panel.set_config(self.global_mesh_config)
            if panel.domain_source_combo.currentIndex() != prev_src:
                panel.domain_source_combo.setCurrentIndex(prev_src)
            self.sync_mesh_layers_panel()
            self.main_window.log_panel.log("All exported sessions added to mesh configuration.")
