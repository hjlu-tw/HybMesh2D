from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QSplitter, QLabel, QComboBox, QPushButton
)
from PyQt6.QtCore import Qt

from app.views.panels import (
    FilePanel, GeometryPanel, VertexPanel,
    EdgeListPanel, EdgePropsPanel, AdvancedPanel, ActionsPanel
)
from app.views.settings_dialog import SettingsDialog
from app.styles import COMBO_STYLE

_SCROLLBAR_QSS = """
    QScrollBar:vertical {
        border: none; background: #0c0d16; width: 10px; margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #2c2e43; min-height: 20px; border-radius: 5px;
    }
    QScrollBar::handle:vertical:hover { background: #3e415e; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
"""

_SECTION_LABEL_QSS = (
    "color:#7c86b8; font-size:11px; font-weight:bold;"
    " text-transform:uppercase; padding:4px 2px 2px 2px;"
)


class SidebarView(QWidget):
    """Left control panel — industrial 'tree + details' layout.

    A vertical splitter holds the model tree (geometry layers + their edges,
    with a selection-mode filter) on top and a context-sensitive Details area
    (edge or vertex properties, driven by selection) below. A persistent footer
    carries Export / Save and opens the geometry-settings dialog.

    All sub-panels are kept as attributes (even when not placed directly in a
    layout) so SidebarView's __getattr__ delegation keeps resolving every widget
    the controllers reference, and existing signal wiring stays intact."""

    def __init__(self, parent=None):
        super().__init__(parent)

        # ── Panels (created first so __getattr__ delegation is always safe) ──
        self.file_panel = FilePanel(self)
        self.geometry_panel = GeometryPanel(self)
        self.edge_list_panel = EdgeListPanel(self)
        self.edge_props_panel = EdgePropsPanel(self)
        self.vertex_panel = VertexPanel(self)
        self.advanced_panel = AdvancedPanel(self)
        self.actions_panel = ActionsPanel(self)

        self._edit_mode = "edge"
        self._edge_props_visible = False

        # ── Selection-mode filter (relocated from the canvas toolbar) ────────
        self.select_mode_label = QLabel("Edit:")
        self.select_mode_label.setStyleSheet(
            "color:#a0a8c0; font-size:11px; font-weight:bold;")
        self.select_mode_combo = QComboBox()
        self.select_mode_combo.addItems(["Vertex (Point)", "Edge (Segment)"])
        self.select_mode_combo.setCurrentIndex(1)  # default to Edge mode
        self.select_mode_combo.setStyleSheet(COMBO_STYLE)
        self.select_mode_combo.setToolTip(
            "Selection Mode: choose whether clicking/selecting affects Vertices "
            "or Edges.\nIn Edge mode, Shift+drag box-selects edges (Ctrl/Cmd+drag "
            "adds to the selection); plain drag still pans.")

        # ── Settings dialog hosts the geometry-settings panel ────────────────
        self.settings_dialog = SettingsDialog(self.advanced_panel, self)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setStyleSheet(
            "QSplitter::handle { background:#1c1e36; height:4px; }"
            "QSplitter::handle:hover { background:#3e415e; }")
        splitter.setChildrenCollapsible(False)
        outer.addWidget(splitter, stretch=1)

        splitter.addWidget(self._build_top_pane())
        splitter.addWidget(self._build_details_pane())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        outer.addWidget(self._build_footer())

        self._update_details()

    # ── Pane builders ───────────────────────────────────────────────────────

    def _make_scroll(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background:#121422;")
        scroll.verticalScrollBar().setStyleSheet(_SCROLLBAR_QSS)
        return scroll

    def _build_top_pane(self) -> QWidget:
        scroll = self._make_scroll()
        content = QWidget()
        content.setStyleSheet("background:#121422; color:#a0a8c0;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        # Import / File (collapsed — used once per session)
        lay.addWidget(self.file_panel)

        # Selection-mode filter, sitting beside the tree it filters
        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(2, 0, 2, 0)
        mode_row.addWidget(self.select_mode_label)
        mode_row.addWidget(self.select_mode_combo, stretch=1)
        lay.addLayout(mode_row)

        tree_lbl = QLabel("Model Tree")
        tree_lbl.setStyleSheet(_SECTION_LABEL_QSS)
        lay.addWidget(tree_lbl)

        # The tree itself (lifted out of geometry_panel; geometry_panel stays
        # alive only as the delegation/signal holder for `geometry_tree`).
        lay.addWidget(self.geometry_panel.geometry_tree, stretch=1)

        # Edge actions act on the tree's current selection
        self.edge_list_panel.expand()
        lay.addWidget(self.edge_list_panel)

        scroll.setWidget(content)
        return scroll

    def _build_details_pane(self) -> QWidget:
        scroll = self._make_scroll()
        content = QWidget()
        content.setStyleSheet("background:#121422; color:#a0a8c0;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        self._details_header = QLabel("Details")
        self._details_header.setStyleSheet(_SECTION_LABEL_QSS)
        lay.addWidget(self._details_header)

        self._details_placeholder = QLabel(
            "Select an edge in the tree to edit its properties,\n"
            "or switch to Vertex mode to edit break points.")
        self._details_placeholder.setWordWrap(True)
        self._details_placeholder.setStyleSheet(
            "color:#6a7aaa; font-style:italic; padding:8px 4px;")
        lay.addWidget(self._details_placeholder)

        # Properties live here, always expanded (no hunting through accordions).
        self.edge_props_panel.expand()
        lay.addWidget(self.edge_props_panel)

        self.vertex_panel.expand()
        lay.addWidget(self.vertex_panel)

        lay.addStretch()
        scroll.setWidget(content)
        return scroll

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setStyleSheet("background:#0c0d16; border-top:1px solid #1c1e36;")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(6, 5, 6, 5)
        fl.setSpacing(6)
        fl.addWidget(self.save_btn, stretch=1)
        fl.addWidget(self.generate_btn, stretch=1)

        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedWidth(34)
        self.settings_btn.setToolTip("Geometry settings (spline smoothing, output transform)")
        self.settings_btn.setStyleSheet(
            "QPushButton { background:#181b30; color:#dde2ff; border:1px solid #2d3356;"
            "  border-radius:4px; padding:5px 4px; font-weight:bold; }"
            "QPushButton:hover { background:#2c3258; border-color:#5a9ad4; color:#fff; }")
        self.settings_btn.clicked.connect(self._open_settings)
        fl.addWidget(self.settings_btn)
        return footer

    # ── Details visibility (selection-driven) ───────────────────────────────

    def _update_details(self):
        """Show the right Details content for the current edit mode/selection."""
        if self._edit_mode == "vertex":
            self.vertex_panel.setVisible(True)
            self.edge_props_panel.setVisible(False)
            self._details_placeholder.setVisible(False)
            self._details_header.setText("Vertex")
        else:
            self.vertex_panel.setVisible(False)
            show = self._edge_props_visible
            self.edge_props_panel.setVisible(show)
            self._details_placeholder.setVisible(not show)
            self._details_header.setText("Edge Properties" if show else "Details")

    def show_details_for_mode(self, mode: str):
        self._edit_mode = "vertex" if mode == "vertex" else "edge"
        self._update_details()

    def _open_settings(self):
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    # ── Public API used by the controllers (unchanged contract) ─────────────

    @property
    def preview_btn(self):
        win = self.window()
        return win.cad_preview_btn if (win and hasattr(win, "cad_preview_btn")) else None

    @property
    def curve_preview_btn(self):
        win = self.window()
        return win.cad_curve_preview_btn if (win and hasattr(win, "cad_curve_preview_btn")) else None

    @property
    def file_preview_btn(self):
        win = self.window()
        return win.cad_file_preview_btn if (win and hasattr(win, "cad_file_preview_btn")) else None

    def switch_param_form(self, strategy_name: str):
        self.edge_props_panel.switch_param_form(strategy_name)

    def show_file_segment(self, start: int, end: int):
        self.edge_props_panel.show_file_segment(start, end)

    def show_curve_segment(self, seg):
        self.edge_props_panel.show_curve_segment(seg)

    def show_segment_props(self, visible: bool):
        self._edge_props_visible = visible
        self.edge_props_panel.show_segment_props(visible)
        self._update_details()

    def get_transform_dict(self) -> dict | None:
        if not self.apply_transform_cb.isChecked():
            return None
        return {
            "scale": self.transform_scale.value(),
            "rotate": self.transform_rotate.value(),
            "translate": [self.transform_tx.value(), self.transform_ty.value()],
        }

    def set_transform_from_dict(self, d: dict | None):
        if d:
            self.apply_transform_cb.setChecked(True)
            self.transform_scale.setValue(d.get("scale", 1.0))
            self.transform_rotate.setValue(d.get("rotate", 0.0))
            tr = d.get("translate", [0.0, 0.0])
            self.transform_tx.setValue(tr[0])
            self.transform_ty.setValue(tr[1])
        else:
            self.apply_transform_cb.setChecked(False)

    def __getattr__(self, name):
        # Delegate unknown attribute lookups to the sub-panels. Guard against
        # recursion before the panels exist (e.g. during super().__init__).
        if name.startswith("__") or "file_panel" not in self.__dict__:
            raise AttributeError(name)
        for panel in [
            self.file_panel,
            self.geometry_panel,
            self.vertex_panel,
            self.edge_list_panel,
            self.edge_props_panel,
            self.advanced_panel,
            self.actions_panel,
        ]:
            if hasattr(panel, name):
                return getattr(panel, name)
            # Transform sub-widgets live inside EdgePropsPanel's TransformPanel.
            if panel is self.edge_props_panel and hasattr(panel, "_transform_dup_group"):
                dup = panel._transform_dup_group
                if hasattr(dup, name):
                    return getattr(dup, name)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
