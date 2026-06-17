from __future__ import annotations
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QAbstractItemView
from PyQt6.QtCore import Qt, pyqtSignal

from app.styles import TREE_STYLE

ROLE = Qt.ItemDataRole.UserRole


class GeometryTreeView(QTreeWidget):
    """Single model tree replacing the old geometry-layer list + edge list.

    Top-level rows are geometry sessions (layers) with a checkbox that doubles
    as a visibility "eye". Each session's edges appear as child rows. To keep the
    selection/index plumbing simple, edges are only ever materialised under the
    *active* session node (edges are addressed by per-session index, which is
    only meaningful for the active session).

    Item payload (``data(0, ROLE)``):
      - session row : ``("session", session_id)``
      - edge row    : ``("edge", session_id, segment_index)``
    """

    # (global_pos, item|None) — emitted on right-click so the controller can
    # build a context menu appropriate to the clicked row kind.
    context_menu_requested = pyqtSignal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setRootIsDecorated(True)
        self.setIndentation(14)
        self.setUniformRowHeights(True)
        self.setExpandsOnDoubleClick(False)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.setStyleSheet(TREE_STYLE)
        self.setMinimumHeight(140)

    def _on_context_menu(self, pos):
        item = self.itemAt(pos)
        self.context_menu_requested.emit(self.viewport().mapToGlobal(pos), item)

    # ── Payload helpers ────────────────────────────────────────────────────

    @staticmethod
    def kind(item) -> str | None:
        if item is None:
            return None
        data = item.data(0, ROLE)
        return data[0] if data else None

    @staticmethod
    def session_id_of(item) -> int | None:
        if item is None:
            return None
        data = item.data(0, ROLE)
        return data[1] if data else None

    @staticmethod
    def edge_index(item) -> int | None:
        data = item.data(0, ROLE) if item is not None else None
        if data and data[0] == "edge":
            return data[2]
        return None

    # ── Session (top-level) accessors ──────────────────────────────────────

    def session_items(self) -> list[QTreeWidgetItem]:
        return [self.topLevelItem(i) for i in range(self.topLevelItemCount())]

    def session_item(self, session_id) -> QTreeWidgetItem | None:
        for it in self.session_items():
            if self.session_id_of(it) == session_id:
                return it
        return None

    # ── Edge (child) accessors ─────────────────────────────────────────────

    def edge_items(self, session_id) -> list[QTreeWidgetItem]:
        node = self.session_item(session_id)
        if node is None:
            return []
        return [node.child(i) for i in range(node.childCount())]

    def edge_item_by_index(self, session_id, seg_idx) -> QTreeWidgetItem | None:
        for it in self.edge_items(session_id):
            if self.edge_index(it) == seg_idx:
                return it
        return None

    def selected_edge_items(self) -> list[QTreeWidgetItem]:
        return [it for it in self.selectedItems() if self.kind(it) == "edge"]

    def selected_edge_indices(self) -> list[int]:
        out = []
        for it in self.selected_edge_items():
            idx = self.edge_index(it)
            if idx is not None:
                out.append(idx)
        return out

    def clear_all_edges(self):
        """Remove every edge child from every session node."""
        for node in self.session_items():
            while node.childCount() > 0:
                node.removeChild(node.child(node.childCount() - 1))

    def clear_edge_selection(self):
        """Deselect any edge rows without touching session-row selection."""
        for it in self.selected_edge_items():
            it.setSelected(False)
