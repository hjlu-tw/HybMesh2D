from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
)

from app.utils import make_button


class ExtrudeSourceDialog(QDialog):
    """Pick which CAD layers become the flat-sheet STL for the immersed boundary.

    Layers with usable geometry are checkable and pre-checked when currently
    visible; layers without points are shown disabled so the picture is complete.
    Returns the chosen session ids via :meth:`selected_ids`.
    """

    def __init__(self, sessions, has_geom, parent=None):
        """`sessions` is the session list; `has_geom` is a callable
        ``session -> bool`` telling whether a session has usable points."""
        super().__init__(parent)
        self.setWindowTitle("Extrude to STL — Source Layers")
        self.setStyleSheet("QDialog{background:#141826;}")
        self.setMinimumWidth(340)

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)
        hint = QLabel("Choose the CAD layer(s) to include in the immersed-boundary "
                      "STL. Only these are triangulated into the flat sheet.")
        hint.setStyleSheet("color:#a0a8c0; font-size:11px;")
        hint.setWordWrap(True)
        v.addWidget(hint)

        self._list = QListWidget()
        self._list.setStyleSheet(
            "background:#181b2a; color:#a0a8c0; border:1px solid #333852; "
            "border-radius:3px;")
        for s in sessions:
            ok = bool(has_geom(s))
            label = s.display_name if ok else f"{s.display_name}  (no geometry)"
            item = QListWidgetItem(label)
            if ok:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    Qt.CheckState.Checked if getattr(s, "is_visible", True)
                    else Qt.CheckState.Unchecked)
                if getattr(s, "color", ""):
                    item.setForeground(QColor(s.color))
            else:
                item.setFlags(Qt.ItemFlag.NoItemFlags)   # present but not choosable
            item.setData(Qt.ItemDataRole.UserRole, s.session_id)
            self._list.addItem(item)
        v.addWidget(self._list)

        row = QHBoxLayout(); row.setSpacing(4)
        all_btn = make_button("All", "#1e2a38")
        none_btn = make_button("None", "#301a1a")
        row.addWidget(all_btn); row.addWidget(none_btn); row.addStretch()
        cancel_btn = make_button("Cancel", "#26293c")
        ok_btn = make_button("Extrude", "#15303a")
        row.addWidget(cancel_btn); row.addWidget(ok_btn)
        v.addLayout(row)

        all_btn.clicked.connect(lambda: self._set_all(True))
        none_btn.clicked.connect(lambda: self._set_all(False))
        cancel_btn.clicked.connect(self.reject)
        ok_btn.clicked.connect(self.accept)

    def _set_all(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self._list.count()):
            it = self._list.item(i)
            if it.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                it.setCheckState(state)

    def selected_ids(self) -> set:
        ids = set()
        for i in range(self._list.count()):
            it = self._list.item(i)
            if ((it.flags() & Qt.ItemFlag.ItemIsUserCheckable)
                    and it.checkState() == Qt.CheckState.Checked):
                ids.add(it.data(Qt.ItemDataRole.UserRole))
        return ids
