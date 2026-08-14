from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QSplitter, QLabel, QComboBox, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal

from app.views.panels import (
    FilePanel, GeometryPanel, VertexPanel, GeomStatsPanel,
    EdgeListPanel, EdgePropsPanel, AdvancedPanel, ActionsPanel
)
from app.views.settings_dialog import SettingsDialog
from app.styles import COMBO_STYLE
from app.views.sidebar_actions_mixin import SidebarActionsMixin
from app.views.sidebar_display_mixin import SidebarDisplayMixin

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


class SidebarView(SidebarActionsMixin, SidebarDisplayMixin, QWidget):
    """Left control panel — industrial 'tree + details' layout.

    A vertical splitter holds the model tree (geometry layers + their edges,
    with a selection-mode filter) on top and a context-sensitive Details area
    (edge or vertex properties, driven by selection) below. A persistent footer
    carries Export / Save and opens the geometry-settings dialog.

    All sub-panels are kept as attributes (even when not placed directly in a
    layout) because this class composes them; they are NOT a lookup path for
    callers.

    There is no __getattr__ here any more. It forwarded any unknown attribute to
    whichever sub-panel owned it, which is how 214 widget names ended up being
    read and written from ten controllers — none of them visible to a rename, a
    deletion, or a reviewer. Callers now use the verbs and signals below, and
    tests/test_sidebar_seam.py fails the build if a new reach-through appears OR
    if the forwarder comes back."""

    # ── What happened, not which widget it happened on ───────────────────
    # Re-emitted from the panel that owns the widgets, so callers connect to the
    # sidebar and never learn the panel tree. `distribution_edited` replaces a
    # controller-side list of ten spin boxes and a combo; a field added to the
    # form now reaches the controller without that list being edited.
    distribution_edited = pyqtSignal()
    distribution_open_requested = pyqtSignal()
    distribution_apply_requested = pyqtSignal()
    distribution_closed = pyqtSignal()
    # Duplicate & Transform. `duplicate_edited` replaces a list of seventeen
    # spin boxes; type and base-mode changes stay separate signals because
    # choosing a transform is not the same event as tuning its parameters.
    duplicate_edited = pyqtSignal()
    duplicate_type_changed = pyqtSignal()
    duplicate_base_mode_changed = pyqtSignal()
    duplicate_requested = pyqtSignal()
    transform_open_requested = pyqtSignal()
    transform_closed = pyqtSignal()
    # Analytic edges. `curve_edited` replaces a hand-listed 38 shape
    # spin boxes plus the formula fields; the shape widgets are found
    # from shape_spec's own parameter table, so a shape that gains a
    # field is wired by the same edit that gives it a parameter.
    curve_edited = pyqtSignal()
    curve_type_changed = pyqtSignal()

    # ── Actions: what the user asked for, never which button they pressed ──
    # Declared here and bound by _ACTIONS below, so a controller connects to an
    # intent. These replace 23 widget names in signal_wiring_ctrl; the line
    # count barely moves, because the win is the seam, not brevity — a renamed
    # or relocated button now breaks in ONE table instead of silently resolving
    # through __getattr__ to nothing.
    load_requested = pyqtSignal()
    load_stl_requested = pyqtSignal()
    load_json_requested = pyqtSignal()
    save_requested = pyqtSignal()
    generate_requested = pyqtSignal()
    extrude_stl_requested = pyqtSignal()
    new_tab_requested = pyqtSignal()
    split_requested = pyqtSignal()
    remove_split_requested = pyqtSignal()
    insert_point_requested = pyqtSignal()
    move_vertex_requested = pyqtSignal()
    remove_edge_requested = pyqtSignal()
    join_edges_requested = pyqtSignal()
    bake_curve_requested = pyqtSignal()
    patch_name_requested = pyqtSignal()
    auto_detect_requested = pyqtSignal()
    auto_split_requested = pyqtSignal()
    strategy_changed = pyqtSignal(str)
    closure_mode_changed = pyqtSignal(str)
    selection_mode_changed = pyqtSignal(int)
    match_previous_toggled = pyqtSignal(bool)
    global_spline_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        # ── Panels (created first so __getattr__ delegation is always safe) ──
        self.file_panel = FilePanel(self)
        self.geometry_panel = GeometryPanel(self)
        self.edge_list_panel = EdgeListPanel(self)
        self.edge_props_panel = EdgePropsPanel(self)
        # Signal-to-signal: the sidebar IS the seam, so its callers must not
        # have to know which sub-panel raised the edit, which button was pressed,
        # or that the distribution tool is a QDialog at all.
        _ep = self.edge_props_panel
        _ep.distribution_edited.connect(self.distribution_edited)
        _ep.distribution_btn.clicked.connect(self.distribution_open_requested)
        _ep.distribution_apply_btn.clicked.connect(self.distribution_apply_requested)
        _ep.wire_distribution_dialog_closed(self.distribution_closed.emit)
        _ep.connect_transform_signals(self.duplicate_edited,
                                      self.duplicate_type_changed,
                                      self.duplicate_base_mode_changed)
        _ep.wire_duplicate_requested(self.duplicate_requested.emit)
        _ep.transform_btn.clicked.connect(self.transform_open_requested)
        _ep.wire_curve_edits(self.curve_edited.emit,
                             self.curve_type_changed.emit)
        _ep.wire_transform_dialog_closed(self.transform_closed.emit)
        self.vertex_panel = VertexPanel(self)
        self.geom_stats_panel = GeomStatsPanel(self)
        # Named, not left to __getattr__: the tree is part of this sidebar's
        # interface (Q8 — it owns its own interface, so it is exposed rather
        # than wrapped), and every other name resolving through the forwarder
        # is a leak scheduled for removal along with the forwarder itself.
        self.geometry_tree = self.geometry_panel.geometry_tree
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

        # FilePanel is kept alive purely as the delegation/wiring holder for its
        # buttons (load_btn/load_stl_btn/…, now driven from the File menu) and
        # file_name_label; it is never placed in a layout, so hide it to keep the
        # un-managed widget from floating over the sidebar.
        self.file_panel.setVisible(False)

        self._wire_actions()
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

        # Import / File actions now live in the menu bar (File menu). Only the
        # geometry-level "Closed Loop" property stays here, beside the tree.
        # Reuse the (now hidden) FilePanel's combo so all controller wiring and
        # SidebarView.__getattr__ delegation keep resolving `is_closed_combo`.
        closed_row = QHBoxLayout()
        closed_row.setContentsMargins(2, 0, 2, 0)
        closed_lbl = QLabel("Closed Loop:")
        closed_lbl.setStyleSheet(
            "color:#a0a8c0; font-size:11px; font-weight:bold;")
        closed_row.addWidget(closed_lbl)
        closed_row.addWidget(self.file_panel.is_closed_combo, stretch=1)
        # Resolved-state hint (e.g. "→ Closed") shown when the mode is Auto.
        closed_row.addWidget(self.file_panel.closed_mode_status)
        lay.addLayout(closed_row)

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

        # Properties stay collapsed by default; selecting an edge expands them
        # (see EdgePropertiesPanel.show_segment_props).
        lay.addWidget(self.edge_props_panel)

        lay.addWidget(self.vertex_panel)

        # Read-out, so it sits below the editable panels; collapsed by default
        # because the sidebar is a fixed 360 px and edge properties come first.
        lay.addWidget(self.geom_stats_panel)

        lay.addStretch()
        scroll.setWidget(content)
        return scroll

    def _build_footer(self) -> QWidget:
        footer = QWidget()
        footer.setStyleSheet("background:#0c0d16; border-top:1px solid #1c1e36;")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(6, 5, 6, 5)
        fl.setSpacing(6)
        ap = self.actions_panel
        fl.addWidget(ap.save_btn, stretch=1)
        fl.addWidget(ap.generate_btn, stretch=1)
        fl.addWidget(ap.extrude_stl_btn, stretch=1)

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
        from app.utils import offset_popup
        offset_popup(self.settings_dialog, self.window())
        self.settings_dialog.show()
        self.settings_dialog.raise_()
        self.settings_dialog.activateWindow()

    # ── Public API used by the controllers (unchanged contract) ─────────────

    def switch_param_form(self, strategy_name: str):
        self.edge_props_panel.switch_param_form(strategy_name)

    # Both dialogs are opened by controllers, so both are part of the sidebar's
    # interface and are declared here rather than left to __getattr__ — which is
    # being removed, and which makes an undeclared verb indistinguishable from a
    # widget reach-through to any reader (and to the seam gate).
    def open_distribution_dialog(self):
        return self.edge_props_panel.open_distribution_dialog()

    def open_transform_dialog(self):
        return self.edge_props_panel.open_transform_dialog()

    def set_save_enabled(self, enabled: bool):
        """Enable/disable the footer's Save button.

        The sidebar used to also hand out the three CAD toolbar buttons via
        properties that reached back into self.window() — a view asking the
        window for widgets it does not own, which is the same leak as a
        controller reaching in here, only pointing outward. Those buttons are
        the main window's and are addressed there; this one is ours."""
        self.actions_panel.save_btn.setEnabled(enabled)

    def set_length_suffix(self, symbol: str):
        """Show `symbol` on every sidebar field holding a physical length.

        The unit controller used to hold the list of field NAMES and fetch each
        one with getattr(sb, name) — invisible to the seam gate (a string is not
        an attribute access) and, worse, silent: once __getattr__ goes, getattr
        returns None and the suffixes simply stop appearing with nothing raised.
        The list belongs to the panel that owns the widgets anyway.
        """
        self.edge_props_panel.set_length_suffix(symbol)

    def selection_mode(self) -> int:
        """The active edit mode as the combo's row (0 = vertex, 1 = edge)."""
        return self.select_mode_combo.currentIndex()

    def set_shape_tool_menu(self, menu):
        """Attach the Add-Analytic-Edge shape menu. A menu is handed over, not
        connected to, so it is a verb rather than one of the signals above."""
        self.edge_list_panel.add_curve_seg_btn.setMenu(menu)

    def curve_spec(self):
        """What the analytic-edge form currently says."""
        return self.edge_props_panel.curve_spec()

    # ── Point distribution ──────────────────────────────────────────────
    def distribution_spec(self, strategy: str):
        """What the distribution form currently says, as a DistributionSpec."""
        return self.edge_props_panel.distribution_spec(strategy)

    def show_distribution_spec(self, spec):
        """Put a DistributionSpec on the form, without it reading back as an edit."""
        self.edge_props_panel.show_distribution_spec(spec)

    def distribution_tool_visible(self) -> bool:
        """Whether the distribution tool window is open (its live preview runs
        only while it is). The caller asks a question; that the tool is a QDialog
        is ours."""
        return self.edge_props_panel.distribution_tool_visible()

    # ── Duplicate & Transform ───────────────────────────────────────────
    def transform_spec(self):
        """What the Duplicate & Transform form currently says."""
        return self.edge_props_panel.transform_spec()

    def set_transform_reference_editable(self, editable: bool):
        """Whether the user owns the pivot fields, or the base mode drives them."""
        self.edge_props_panel.set_transform_reference_editable(
            editable)

    def set_transform_reference(self, point):
        """Display the computed pivot every transform turns about."""
        self.edge_props_panel.set_transform_reference(point)

    def set_transform_reference_applicable(self, applicable: bool):
        self.edge_props_panel.set_transform_reference_applicable(
            applicable)

    def use_custom_transform_reference(self):
        self.edge_props_panel.use_custom_transform_reference()

    def set_transform_handle(self, handle: str, x: float, y: float):
        """Place the canvas handle the user dragged."""
        self.edge_props_panel.set_transform_handle(
            handle, x, y)

    def show_transform_panel(self, visible: bool):
        self.edge_props_panel.show_transform_panel(visible)

    def show_file_segment(self, start: int, end: int):
        self.edge_props_panel.show_file_segment(start, end)

    def show_curve_segment(self, seg):
        self.edge_props_panel.show_curve_segment(seg)

    def show_segment_props(self, visible: bool):
        self._edge_props_visible = visible
        self.edge_props_panel.show_segment_props(visible)
        self._update_details()

    def get_transform_dict(self) -> dict | None:
        if not self.advanced_panel.apply_transform_cb.isChecked():
            return None
        ap = self.advanced_panel
        return {
            "scale": ap.transform_scale.value(),
            "rotate": ap.transform_rotate.value(),
            "translate": [ap.transform_tx.value(), ap.transform_ty.value()],
        }

    def set_transform_from_dict(self, d: dict | None):
        ap = self.advanced_panel
        if d:
            ap.apply_transform_cb.setChecked(True)
            ap.transform_scale.setValue(d.get("scale", 1.0))
            ap.transform_rotate.setValue(d.get("rotate", 0.0))
            tr = d.get("translate", [0.0, 0.0])
            ap.transform_tx.setValue(tr[0])
            ap.transform_ty.setValue(tr[1])
        else:
            ap.apply_transform_cb.setChecked(False)
