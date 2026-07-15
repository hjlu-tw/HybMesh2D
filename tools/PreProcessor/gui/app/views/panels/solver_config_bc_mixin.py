"""BC-table handling for SolverConfigPanel, split out as a mixin (behaviour
unchanged). Owns the boundary-condition table row helpers, the default/detected
fill methods, and `_on_flow_solu_changed` (which refreshes the geometry wall row
when the solver type flips). Expects the host to provide `self.bc_table` and
`self.flow_solu_type`, both built in `_build_bc_section` / `_build_flow_section`."""
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QTableWidgetItem

from app.utils import COMBO_STYLE
from app.models.solver_config import BC_TYPES


class SolverConfigBCMixin:
    """Boundary-condition table CRUD + type-combo + flow-solu wall refresh."""

    def _fill_default_bc(self):
        """Populate the standard HybMesh2D group mapping (1-4 domain non-reflect,
        5 geometry wall) using the wall flag appropriate for the solution type."""
        wall = 0 if self.flow_solu_type.currentText() == "euler_sol" else 2
        self.bc_table.setRowCount(0)
        for seg, bc, name in [(1, 1, "XMin"), (2, 1, "XMax"), (3, 1, "YMin"),
                              (4, 1, "YMax"), (5, wall, "geom")]:
            self._add_bc_row(seg, bc, "", name)

    def populate_bc_from_segments(self, segments, euler: bool = False,
                                  group_bc: dict | None = None) -> int:
        """Fill the BC table from a list of ``(seg_id, patch_name)`` pairs read
        from the generated mesh, pre-selecting a sensible BC type per patch. #4:
        when a patch NAME has an explicit BC type assigned in the Mesh Generator
        (``group_bc[name]``), that assignment wins over guessing from the name;
        the name is still shown (read-only) so the grouping label is preserved.
        Returns the number of rows added."""
        from app.services.bnd_io import default_bc_flag_for_name
        group_bc = group_bc or {}
        self.bc_table.setRowCount(0)
        for sid, name in segments:
            assigned = group_bc.get(name)
            flag = (default_bc_flag_for_name(assigned, euler) if assigned
                    else default_bc_flag_for_name(name, euler))
            self._add_bc_row(sid, flag, "", name)
        return len(segments)

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
            if self.bc_table.cellWidget(r, 2) is combo:
                flag = combo.currentData()
                item = self.bc_table.item(r, 3)
                if item is None:
                    item = QTableWidgetItem("")
                    self.bc_table.setItem(r, 3, item)
                hints = {3: "non-dimensional wall temperature, e.g. 2.5",
                         50: "rho u v et (2D) or rho u v w et (3D)",
                         11: "./bc.so (path to the DLL)"}
                item.setToolTip(hints.get(flag, "(no extra value needed)"))
                break

    def _add_bc_row(self, seg: int, bc: int, values: str = "", name: str = ""):
        r = self.bc_table.rowCount()
        self.bc_table.insertRow(r)
        self.bc_table.setItem(r, 0, QTableWidgetItem(str(seg)))
        # Patch name is a read-only display label (set upstream in CAD / mesh).
        name_item = QTableWidgetItem(name or "")
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        name_item.setToolTip("Patch name from the mesh (grouping label). The BC "
                             "type you pick here is applied to this segment.")
        self.bc_table.setItem(r, 1, name_item)
        self.bc_table.setCellWidget(r, 2, self._make_bc_type_combo(bc))
        self.bc_table.setItem(r, 3, QTableWidgetItem(values))
        self._sync_bc_extra_hint(self.bc_table.cellWidget(r, 2))

    def _remove_bc_row(self):
        rows = sorted({i.row() for i in self.bc_table.selectedItems()}, reverse=True)
        # selectedItems() misses combo-only selections; fall back to current row.
        if not rows and self.bc_table.currentRow() >= 0:
            rows = [self.bc_table.currentRow()]
        for r in rows:
            self.bc_table.removeRow(r)

    def _on_flow_solu_changed(self, _text: str):
        """When the solver type flips, refresh the geometry wall row (seg 5) if it
        still holds the other type's default wall flag, so the BC stays sensible."""
        wall = 0 if self.flow_solu_type.currentText() == "euler_sol" else 2
        other = 2 if wall == 0 else 0
        for r in range(self.bc_table.rowCount()):
            seg_item = self.bc_table.item(r, 0)
            combo = self.bc_table.cellWidget(r, 2)
            if not seg_item or combo is None:
                continue
            if seg_item.text().strip() == "5" and combo.currentData() == other:
                idx = combo.findData(wall)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
