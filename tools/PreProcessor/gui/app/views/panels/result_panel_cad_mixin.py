from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QListWidgetItem,
)

from app.utils import (
    block_signals,
)

_TABLE_QSS = (
    "QTableWidget{background:#181b2a;color:#a0a8c0;border:1px solid #333852;"
    "gridline-color:#2c2e43;} QHeaderView::section{background:#1e2235;"
    "color:#a0a8c0;border:none;padding:3px;}")
_SCROLLBAR_QSS = """
    QScrollBar:vertical { border: none; background: #0c0d16; width: 10px; margin: 0px; }
    QScrollBar::handle:vertical { background: #2c2e43; min-height: 20px; border-radius: 5px; }
    QScrollBar::handle:vertical:hover { background: #3e415e; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
"""
_COLORMAPS = ["turbo", "viridis", "inferno", "plasma", "coolwarm", "jet", "RdBu_r"]


class ResultPanelCadMixin:
    def _cad_checked_ids(self) -> set:
        ids = set()
        for i in range(self.cad_list.count()):
            it = self.cad_list.item(i)
            if ((it.flags() & Qt.ItemFlag.ItemIsUserCheckable)
                    and it.checkState() == Qt.CheckState.Checked):
                ids.add(it.data(Qt.ItemDataRole.UserRole))
        return ids

    def _populate_cad_list(self):
        """(Re)build the geometry checklist from the controller, preserving the
        prior tick state; a fresh list defaults every geometry to ticked."""
        if self._controller is None:
            return
        prev = self._cad_checked_ids()
        fresh = self.cad_list.count() == 0
        with block_signals(self.cad_list):
            self.cad_list.clear()
            for sid, name, color, has_geom in self._controller.cad_overlay_sessions():
                item = QListWidgetItem(name if has_geom else f"{name}  (no geometry)")
                if has_geom:
                    item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    checked = (sid in prev) if not fresh else True
                    item.setCheckState(Qt.CheckState.Checked if checked
                                       else Qt.CheckState.Unchecked)
                    if color:
                        item.setForeground(QColor(color))
                else:
                    item.setFlags(Qt.ItemFlag.NoItemFlags)
                item.setData(Qt.ItemDataRole.UserRole, sid)
                self.cad_list.addItem(item)

    def _apply_cad(self, *_):
        if self._canvas is None:
            return
        if self.cad_cb.isChecked() and self._controller is not None:
            polys = self._controller.cad_overlay_polylines(self._cad_checked_ids())
            self._canvas.set_cad_geometry(polys, True)
        else:
            self._canvas.set_cad_geometry([], False)

    def _on_cad_toggled(self, on: bool):
        if on and self.cad_list.count() == 0:
            self._populate_cad_list()
        self._apply_cad()

    def _on_cad_item_changed(self, *_):
        if self.cad_cb.isChecked():
            self._apply_cad()

    def _on_cad_color_changed(self, *_):
        if self._canvas is not None:
            self._canvas.set_cad_color(self.cad_color.currentData())

    def _reload_cad(self):
        self._populate_cad_list()
        self.cad_cb.setChecked(True)   # showing implies loading (may fire _apply_cad)
        self._apply_cad()              # ensure a (re)apply even if already checked
