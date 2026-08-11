from __future__ import annotations
import os


class SolverBcControllerMixin:
    """Bridge mesh boundary patches -> solver BC table (D).

    Reads the STAR-CD .bnd patch names/segment numbers and keeps the solver BC
    rows in sync with the Mesh-Generator per-patch assignments; also the type-11
    BC DLL builder. Mixed into the AppController alongside SolverControllerMixin.
    """

    # ------------------------------------------------------------------ #
    # Bridge mesh boundary patches -> solver BC table (D)
    # ------------------------------------------------------------------ #
    def _locate_mesh_bnd(self) -> str:
        """Find the STAR-CD .bnd of the mesh to assign BCs to.

        It must be the file the RUN will use, or the table describes one grid
        while the solver reads another. So auto-link wins when it is on (the run
        overwrites the panel's paths from the last generated mesh anyway, and
        the field can still be showing an earlier 'Send to Solver' export);
        otherwise the explicitly set .bnd in Grid Conversion, else the last
        generated mesh's .bnd."""
        from app.services.bnd_io import bnd_path_for
        panel = self.main_window.solver_config_panel
        auto = getattr(panel, "auto_link_mesh", None)
        vtk = getattr(self, "global_vtk_path", "")
        if auto is not None and auto.isChecked() and vtk:
            b = bnd_path_for(vtk)
            if os.path.exists(b):
                return b
        p = panel.input_bnd_file.text().strip()
        if p and os.path.exists(p):
            return p
        if vtk:
            b = bnd_path_for(vtk)
            if os.path.exists(b):
                return b
        return ""

    def detect_bc_from_mesh(self):
        """Read the actual boundary patches (segment number + name) from the last
        generated mesh's .bnd and fill the solver BC table, pre-selecting a BC
        type per patch name. This is what carries the per-segment patch names set
        in CAD / 'Edit segment BCs…' through to the solver with the CORRECT
        segment numbers (the mesher numbers segments per patch, not 1-4=box/5=geom)."""
        from app.services.bnd_io import read_bnd_segments
        log = self.main_window.log_panel.log
        bnd = self._locate_mesh_bnd()
        if not bnd:
            log("[ERROR] No mesh .bnd found. Generate a mesh with 'Write STAR-CD' "
                "enabled first, or set the .bnd path in Grid Conversion.")
            return
        segs = read_bnd_segments(bnd)
        if not segs:
            log(f"[WARNING] No boundary patches found in {os.path.basename(bnd)}.")
            return
        panel = self.main_window.solver_config_panel
        euler = panel.flow_solu_type.currentText() == "euler_sol"
        # #4: honour BC types assigned per group/patch NAME in the Mesh Generator
        # (they win over the name-based guess; the name stays as the display label).
        group_bc = getattr(getattr(self, "global_mesh_config", None), "group_bc", {}) or {}
        n = panel.populate_bc_from_segments(segs, euler=euler, group_bc=group_bc)
        listing = ", ".join(f"{sid}={nm or '(unnamed)'}" for sid, nm in segs)
        log(f"[Solver] Detected {n} boundary patch(es) from "
            f"{os.path.basename(bnd)}: {listing}. Review the BC types, then Run.")

    def resync_solver_bc_from_group(self):
        """#2/#7: make the solver BC rows reflect the CURRENT mesh + the latest
        Mesh-Generator per-patch BC assignments, on entering Solver mode / before
        a run — WITHOUT the user having to click 'Detect from Mesh'.

        The earlier version only patched EXISTING rows by matching the patch NAME
        against ``group_bc``. That silently did nothing when the table was empty,
        default (XMin…/geom), or stale from an older mesh — the patch names didn't
        match, so a BC set in the Mesh Generator reached the solver as the WRONG
        BC (the reported bug). Now: if a mesh .bnd exists and its patch NAMES no
        longer match the table, RE-DETECT from that .bnd (real names + segment
        ids + group_bc). When the table already matches the mesh, only refresh
        the BC types (preserving a manual tweak on an unassigned patch). Finally
        it audits the mesh against the assigned BCs, since only a regenerate can
        carry an assignment the mesh predates into the solver."""
        panel = self.main_window.solver_config_panel
        log = self.main_window.log_panel.log
        group_bc = getattr(getattr(self, "global_mesh_config", None), "group_bc", {}) or {}
        euler = panel.flow_solu_type.currentText() == "euler_sol"

        from app.services.bnd_io import read_bnd_segments
        bnd = self._locate_mesh_bnd()
        if bnd:
            segs = read_bnd_segments(bnd)
            mesh_names = [nm for _sid, nm in segs]
            table_names = [panel.bc_table.item(r, 1).text().strip()
                           for r in range(panel.bc_table.rowCount())
                           if panel.bc_table.item(r, 1) is not None]
            if segs and mesh_names != table_names:
                # Table is stale vs the mesh — seed it fresh (this applies
                # group_bc too, via detect_bc_from_mesh -> populate_bc_from_segments).
                self.detect_bc_from_mesh()
            elif group_bc and panel.bc_table.rowCount():
                n = panel.resync_bc_types_from_group(group_bc, euler=euler)
                if n:
                    log(f"[Solver] Updated {n} BC row(s) from the current "
                        f"Mesh-Generator patch assignments.")
        elif group_bc and panel.bc_table.rowCount():
            n = panel.resync_bc_types_from_group(group_bc, euler=euler)
            if n:
                log(f"[Solver] Updated {n} BC row(s) from the current "
                    f"Mesh-Generator patch assignments.")

        # Warn about assignments the current mesh can't carry (it predates them).
        # NOT by comparing group_bc's keys with the patch names: a key is a
        # segment LABEL while a patch name is the BC TYPE the mesher resolved
        # that label to, so every key looked "missing" and the warning fired on
        # every single run — including for meshes that were perfectly correct,
        # and telling the user to regenerate a mesh that already had their BCs.
        # The audit compares like with like (assigned type vs patch name, plus
        # the mesh's age against the .meta the labels live in).
        if bnd:
            self.warn_if_mesh_bc_stale(bnd)

    def open_bc_dll_builder(self):
        """Open the DLL builder for a BC type-11 getQ_inst_dll source (#12) and
        drop the saved path into the selected BC row's Extra values (column 3).
        Falls back to logging the path when no row is selected."""
        from PyQt6.QtWidgets import QTableWidgetItem
        from app.views.dll_builder_dialog import DllBuilderDialog
        from app.services.dll_templates import BC_INFLOW
        sp = self.main_window.solver_config_panel
        row = sp.bc_table.currentRow()
        seed = ""
        if row >= 0 and sp.bc_table.item(row, 3) is not None:
            seed = sp.bc_table.item(row, 3).text().strip()
        dlg = DllBuilderDialog(self.main_window, BC_INFLOW, seed)
        from app.utils import offset_popup
        offset_popup(dlg, self.main_window)
        if dlg.exec() and dlg.result_path:
            if row >= 0:
                item = sp.bc_table.item(row, 3) or QTableWidgetItem()
                item.setText(dlg.result_path)
                sp.bc_table.setItem(row, 3, item)
                self.main_window.log_panel.log(
                    f"[BC] type-11 DLL source set on row {row}: {dlg.result_path}")
            else:
                self.main_window.log_panel.log(
                    f"[BC] type-11 DLL source saved (select a BC row to attach): "
                    f"{dlg.result_path}")
