from __future__ import annotations
import os
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QListWidgetItem
from app.utils import block_signals, report_info
from app.commands.segment_cmds_core import UpdateMultipleSegmentsStateCmd
from app.services import meta_io
from app.services.geom_path_identity import canonical_geom_path

class MeshLayersControllerMixin:
    """Mixin managing the Geometry Layers list of the mesh generator — syncing
    sessions/external files into the panel and adding/removing geometry from the
    global mesh config."""

    def add_active_preprocessor_geometry(self):
        """Auto-add the resampled output file of the active PreProcessor session into the mesh generator input list."""
        session = self.active_session()
        if not session:
            self.log("No active session. Please create or import geometry first.")
            return

        if not session.project_model.output_file:
            self.log(
                "No resampled output file specified. Run 'Save & Export' in PreProcessor mode first."
            )
            return

        path = session.project_model.output_file
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            self.log(
                f"Resampled file does not exist at '{abs_path}'. Run 'Save & Export' first."
            )
            return

        cfg = self.config_from_panel("mesh_config_panel")
        if cfg.add_geom_file(abs_path):
            self.push_panel_config(self.main_window.mesh_config_panel, cfg)
            self.log(f"Added resampled geometry to configuration: {abs_path}")
            self.sync_mesh_layers_panel()
        else:
            self.log("Geometry file is already in the list.")

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
        # By IDENTITY, never os.path.abspath: that is cwd-relative, so this prune
        # missed a repo-relative entry whenever the GUI was launched from anywhere
        # but the repo root, and the deleted geometry stayed in the mesh.
        if not cfg.remove_geom_file(out_file):
            return  # this geometry was not part of the mesh
        cfg.prune_roles()  # drop the removed geometry's seed role, if any

        # Keep the panel (the authority at generate time) and the canvas
        # previews in sync with the pruned list — preserving live numeric edits.
        self._sync_global_scalars_from_panel()
        self.push_panel_config(self.main_window.mesh_config_panel, cfg)
        self.sync_mesh_layers_panel()
        self.log(
            f"Removed deleted geometry '{os.path.basename(out_file)}' from the "
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
                    abs_out_file = canonical_geom_path(out_file)
                    if not os.path.exists(abs_out_file):
                        display_text += " (not exported)"
                else:
                    display_text += " (no output file)"

                item = QListWidgetItem(display_text)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

                if self.global_mesh_config.has_geom_file(abs_out_file):
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
            # Both sides through the SAME resolver. With os.path.abspath a
            # repo-relative geom_files entry did not match the session that
            # exported it whenever the GUI ran from another cwd, so the geometry
            # was listed as its own layer AND again as an "external file" — the
            # reported "listed every geometry twice".
            session_outs = set()
            for session in self.sessions:
                out_file = session.project_model.output_file
                if out_file:
                    session_outs.add(canonical_geom_path(out_file))

            for gf in self.global_mesh_config.geom_files:
                abs_gf = canonical_geom_path(gf)
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
                self.global_mesh_config.remove_geom_file(abs_out_file)
                self.global_mesh_config.prune_roles()
                self._sync_global_scalars_from_panel()
                self.push_panel_config(self.main_window.mesh_config_panel, self.global_mesh_config)
                self.sync_mesh_layers_panel()
                self.log(
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

            self.global_mesh_config.add_geom_file(abs_out_file)
        else:
            # The partner of the add above, and it has to match it: adding by
            # identity while removing by STRING meant a config holding the
            # repo-relative spelling (what a loaded workspace or case package
            # carries) could not be unchecked at all — the box cleared and the
            # geometry stayed in the mesh.
            if self.global_mesh_config.remove_geom_file(abs_out_file):
                self.global_mesh_config.prune_roles()

        self._sync_global_scalars_from_panel()
        self.push_panel_config(self.main_window.mesh_config_panel, self.global_mesh_config)

    # ── Mesh-stage per-segment edits (No-BL toggle, BC label) ──────────────
    #
    # These two facts are per-SEGMENT but edited at the MESH stage, and their
    # only home used to be the ``.meta`` sidecar next to the resampled ``.dat``.
    # The resampler rewrites that sidecar from the CAD config on every save, so
    # each fact came back as its default (bc ``-``, grow ``1``) and three call
    # sites wrapped the subprocess in snapshot/restore to put them back — a
    # compensation that had to refuse itself whenever the segment id set changed,
    # since it re-applied by id after a subprocess had rewritten the file.
    #
    # Routing the edit through the SegmentModel removes the need for any of that:
    # ``to_dict()`` feeds the resampler's own config (which has always read
    # ``sj["bc"]`` and ``sj["grow_bl"]``), so the sidecar is written correctly the
    # FIRST time, and the fact reaches undo, the workspace and the pipeline
    # script for free. It also cannot resurrect the failure mode that got sidecar
    # preservation reverted from the resampler — a new geometry written over an
    # existing output name inheriting the old geometry's flags — because the model
    # knows which geometry it describes and the resampler does not.
    def _session_for_geom_path(self, path: str):
        """The CAD session whose export IS this mesh-stage geometry file, if any.

        Matched on the session's own ``output_file``, which is exactly what
        ``sync_mesh_layers_panel`` lists. A geometry with no session behind it is
        legitimate and common (an external ``.dat`` browsed in, or one left by a
        closed tab), which is why the caller must handle None rather than treat
        it as an error.
        """
        target = canonical_geom_path(path or "")
        if not target:
            return None
        for session in self.sessions:
            out = (session.project_model.output_file or "").strip()
            if out and canonical_geom_path(out) == target:
                return session
        return None

    def _adopt_sidecar_facts(self, session, path: str) -> list[str]:
        """Take into the model any per-segment fact only the sidecar knows.

        THE MODEL CAN ONLY BE THE TRUTH ABOUT A FACT IT WAS TOLD, and nothing
        ever seeded these two from a ``.meta``. Without this, the projection
        below overwrote labels and flags it had never read: on any geometry whose
        labels live only in its sidecar — i.e. every case predating the model
        field — one Mesh-stage BC edit reset every OTHER segment's label to
        ``-`` and re-enabled a No-BL wall, because the BC dialog only reports
        NEWLY MINTED names while the projection writes every segment. Measured
        before the fix: four labels and one No-BL flag became one label and none.
        That is the same all-``wall`` export the model field exists to prevent.

        Fill-in only, never overwrite — the same rule ``ib_handoff`` applies to a
        scripted phi path: a fact the model holds wins, a fact only the file
        holds is adopted. For ``grow_bl`` that means a sidecar ``0`` is taken
        when the model is still at its ``True`` default; the reverse (model off,
        file on) is left alone, since the file is a projection and can only be
        ahead of the model when the resampler has just rewritten it.

        Runs BEFORE the undo snapshot on purpose, so undo returns to the adopted
        state rather than to the empty one — otherwise undoing the first edit
        would re-wipe the sidecar it was meant to protect. Adoption is a
        migration of the user's existing setup, not an edit of theirs, so it is
        deliberately not undoable; it is reported instead, because a silent
        migration of somebody's boundary conditions is worse than a loud one.
        """
        adopted = []
        if not os.path.exists(meta_io.meta_path_for(path)):
            return adopted
        file_bc = {sid: (bc or "").strip()
                   for sid, bc, _kind in meta_io.read_meta_segments(path)}
        file_grow = meta_io.read_meta_seg_growbl(path)
        for seg in session.project_model.segments:
            if not seg.bc and file_bc.get(seg.id):
                seg.bc = file_bc[seg.id]
                adopted.append(f"{seg.id}->{seg.bc}")
            if seg.grow_bl and file_grow.get(seg.id) is False:
                seg.grow_bl = False
                adopted.append(f"{seg.id}->No BL")
        return adopted

    def _write_sidecar_from_model(self, session, path: str) -> None:
        """Project the segment models' per-segment facts onto the ``.meta``.

        The sidecar is a PROJECTION here, never a second home: it is rewritten
        from the model after every edit, undo and redo. That is what makes undo
        actually effective — reverting the model while the file kept the old
        column would leave the mesher reading the un-undone value — and it is
        why the readers (the BL dialog's seeding, the mesher itself) need no
        change: the file still says what it always said, it just no longer
        decides it.

        Total by design: every segment the model holds is written. That is only
        safe because :meth:`_adopt_sidecar_facts` ran first — see the measured
        failure in its docstring. Segment ids the model does NOT hold keep their
        existing column (both writers in ``meta_io`` leave an id they were not
        given alone), so an extra row in the sidecar is never clobbered.
        """
        segs = session.project_model.segments
        meta_io.write_meta_seg_growbl(path, {seg.id: seg.grow_bl for seg in segs})
        meta_io.write_meta_segbc(path, {seg.id: seg.bc for seg in segs})

    def _apply_mesh_stage_seg_edit(self, path: str, values: dict, apply,
                                   describe) -> bool:
        """Put a {seg_id: value} edit on the segment models, undoably.

        ``apply(seg, value)`` performs the field write and ``describe(segs)``
        names the result for the log — callables rather than a field-name string,
        so neither the attribute nor the log wording is stringly typed.

        Returns True when a live model took the edit. False means no session is
        behind this geometry, and the caller writes the sidecar directly — the
        fact then lives only in that file, which is correct for a geometry this
        app does not resample.
        """
        session = self._session_for_geom_path(path)
        if session is None:
            return False
        pm = session.project_model
        adopted = self._adopt_sidecar_facts(session, path)
        if adopted:
            self.log("Adopted per-segment settings already in the geometry's "
                     ".meta into the model: " + ", ".join(adopted))
        old_states, states = {}, {}
        for idx, seg in enumerate(pm.segments):
            if seg.id not in values:
                continue
            old_states[idx] = seg.to_dict()
            apply(seg, values[seg.id])
        for idx in old_states:
            states[idx] = (old_states[idx], pm.segments[idx].to_dict())
        changed = [i for i, (o, n) in states.items() if o != n]
        if changed:
            session.command_history.execute(UpdateMultipleSegmentsStateCmd(
                session, states,
                refresh_cb=lambda: self._write_sidecar_from_model(session, path)))
            self.log(describe([pm.segments[i] for i in changed]))
        else:
            # Nothing moved, but the file may still predate the model (e.g. the
            # geometry was just re-resampled, or adoption just ran). Keep the
            # projection honest.
            self._write_sidecar_from_model(session, path)
        return True

    def handle_seg_grow_bl_changed(self, path: str, seg_grow: dict):
        """A Mesh-stage 'grow BL?' toggle."""
        values = {int(k): bool(v) for k, v in (seg_grow or {}).items()}
        if self._apply_mesh_stage_seg_edit(
                path, values,
                lambda seg, v: setattr(seg, "grow_bl", v),
                lambda segs: "No-BL: boundary layer now " + ", ".join(
                    f"{'off' if not x.grow_bl else 'on'} on segment {x.id}"
                    for x in segs)):
            return
        meta_io.write_meta_seg_growbl(path, values)

    def handle_seg_bc_labels_changed(self, path: str, seg_bc: dict):
        """A Mesh-stage per-segment BC label edit. Same rule, same reason."""
        values = {int(k): (v or "").strip() for k, v in (seg_bc or {}).items()}
        if self._apply_mesh_stage_seg_edit(
                path, values,
                lambda seg, v: setattr(seg, "bc", v),
                lambda segs: "Segment BC: " + ", ".join(
                    f"{x.id}->{x.bc or '(inherit)'}" for x in segs)):
            return
        meta_io.write_meta_segbc(path, values)

    def add_all_sessions_to_mesh(self):
        """Add all sessions that have valid exported output files to the global mesh config."""
        added_any = False
        missing_exports = []
        for session in self.sessions:
            out_file = session.project_model.output_file
            if out_file:
                abs_out = canonical_geom_path(out_file)
                if os.path.exists(abs_out):
                    if self.global_mesh_config.add_geom_file(abs_out):
                        added_any = True
                else:
                    missing_exports.append(session.display_name)
            else:
                missing_exports.append(session.display_name)

        if missing_exports:
            names = ", ".join(missing_exports)
            self.log(
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
            self.log("All exported sessions added to mesh configuration.")
