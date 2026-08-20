from __future__ import annotations
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QVBoxLayout, QFormLayout,
    QLabel, QComboBox, QSpinBox,
    QCheckBox, QDialog
)
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, COMBO_STYLE, SPIN_STYLE, align_form_labels, help_label, help_widget, block_signals
from app.views.panels.transform_panel import TransformPanel
from app.views.clean_double_spin_box import CleanDoubleSpinBox
from app.views.adjusting_stacked_widget import AdjustingStackedWidget
from app.models import shape_spec
from app.models.curve_edit_spec import CURVE_TYPES
from app.views.panels.edge_props_shapes_mixin import EdgePropsShapesMixin
from app.views.panels.edge_props_dist_mixin import EdgePropsDistMixin
from app.views.panels.edge_props_dialogs_mixin import EdgePropsDialogsMixin
from app.views.panels.edge_props_shape_build_mixin import EdgePropsShapeBuildMixin

class EdgePropsPanel(CollapsibleSection, EdgePropsShapesMixin, EdgePropsDistMixin,
                     EdgePropsDialogsMixin, EdgePropsShapeBuildMixin):
    # The panel says WHAT happened, never which widget it happened on. Declared
    # here rather than on EdgePropsDistMixin because PyQt only collects signals
    # from a class built by the Qt metaclass, which a plain mixin is not.
    distribution_edited = pyqtSignal()
    curve_edited = pyqtSignal()
    #: '' | 'file' | 'curve' — which CAD toolbar preview button applies
    #: to what is being shown. Emitted instead of reaching up through
    #: self.window() for buttons this panel does not own; the window
    #: connects it and shows its own widgets.
    preview_kind_changed = pyqtSignal(str)
    curve_type_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Edge Properties", start_collapsed=True, parent=parent)

        self.segment_type_label = QLabel("—")
        self.segment_type_label.setStyleSheet("font-weight: bold; color: #64B5F6;")

        # ── File segment info ─────────────────────────────────────────────
        self._file_seg_label = QLabel("Start: —   End: —")
        self._file_seg_label.setStyleSheet("color:#6a7aaa; font-size:11px;")
        self._file_seg_label.setVisible(False)

        # ── Curve / Shape Properties group (collapsible) ──────────────────
        self._curve_group = CollapsibleSection("Shape", start_collapsed=True)

        # Curve Type Selection
        self.curve_type_combo = QComboBox()
        self.curve_type_combo.addItems([
            "Custom Formula",
            "Horizontal Line",
            "Vertical Line",
            "Line",
            "Circle",
            "Triangle",
            "Quadrilateral",
            "Polygon",
            "Arc"
        ])
        self.curve_type_combo.setStyleSheet(COMBO_STYLE)
        self.curve_type_combo.setToolTip("Select the geometric shape type for this curve edge")
        self._curve_group.add_widget(self.curve_type_combo)

        # Stacked widget for switching parameters based on curve type.
        # Sizes to the current page so a short shape (e.g. Circle) leaves no
        # dead space below it.
        self.shape_stack = AdjustingStackedWidget()
        self._curve_group.add_widget(self.shape_stack)

        _shape_forms = self._build_shape_stack()
        self.curve_type_combo.currentIndexChanged.connect(self.shape_stack.setCurrentIndex)

        # General curve properties (applicable to all shapes)
        rf = QFormLayout()
        # #2: a polygon may be distributed by a fixed node count OR by a target
        # edge spacing (node count then derived from the polygon perimeter). The
        # Mode row is shown only for polygon; other analytic curves stay node-count.
        self.curve_dist_mode = QComboBox()
        self.curve_dist_mode.addItems(["By Node Count", "By Spacing"])
        self.curve_dist_mode.setStyleSheet(COMBO_STYLE)
        self.curve_dist_mode.setToolTip("Distribute the polygon by a fixed node count or by a target edge spacing")
        self.curve_n = QSpinBox()
        self.curve_n.setRange(2, 100000)
        self.curve_n.setValue(100)
        self.curve_n.setStyleSheet(SPIN_STYLE)
        self.curve_n.setToolTip("Total number of points to distribute along this edge")
        self.curve_spacing = CleanDoubleSpinBox()
        self.curve_spacing.setRange(1e-6, 1e4)
        self.curve_spacing.setValue(0.1)
        self.curve_spacing.setDecimals(5)
        self.curve_spacing.setSingleStep(0.01)
        self.curve_spacing.setStyleSheet(SPIN_STYLE)
        self.curve_spacing.setToolTip("Target distance between adjacent nodes along the polygon perimeter")
        self.curve_spacing.setVisible(False)
        self.curve_start_node = QSpinBox()
        self.curve_start_node.setRange(-1, 1000000)
        self.curve_start_node.setValue(-1)
        self.curve_start_node.setSpecialValueText("None")
        self.curve_start_node.setStyleSheet(SPIN_STYLE)
        self.curve_start_node.setToolTip("Index of the anchor node at the start (or None for auto)")
        self.curve_end_node = QSpinBox()
        self.curve_end_node.setRange(-1, 1000000)
        self.curve_end_node.setValue(-1)
        self.curve_end_node.setSpecialValueText("None")
        self.curve_end_node.setStyleSheet(SPIN_STYLE)
        self.curve_end_node.setToolTip("Index of the anchor node at the end (or None for auto)")
        rf.addRow(help_label("Mode:", "Distribute by a fixed node count or by a target edge spacing (polygon)"), self.curve_dist_mode)
        rf.addRow(help_label("Node Count:", "Total number of points to distribute along this edge"), self.curve_n)
        rf.addRow(help_label("Spacing (Δs):", "Target distance between adjacent nodes along the polygon perimeter"), self.curve_spacing)
        rf.addRow(help_label("Start Anchor:", "Index of the anchor node at the start (or None for auto)"), self.curve_start_node)
        rf.addRow(help_label("End Anchor:", "Index of the anchor node at the end (or None for auto)"), self.curve_end_node)
        self._curve_mode_label = rf.labelForField(self.curve_dist_mode)
        self._curve_n_label = rf.labelForField(self.curve_n)
        self._curve_spacing_label = rf.labelForField(self.curve_spacing)
        if self._curve_spacing_label:
            self._curve_spacing_label.setVisible(False)
        self.curve_dist_mode.currentTextChanged.connect(
            lambda t: self._toggle_curve_dist_mode(t == "By Spacing"))

        self._curve_group.add_layout(rf)

        self._curve_group.setVisible(False)

        # ── Strategy ─────────────────────────────────────────────────────
        sf = QFormLayout()
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems(["uniform", "tanh", "cosine", "curvature", "geometric"])
        self.strategy_combo.setStyleSheet(COMBO_STYLE)
        self.strategy_combo.setToolTip("Point distribution strategy along this edge")
        sf.addRow(help_label("Distribution:", "Point distribution strategy along this edge"), self.strategy_combo)

        self.match_previous_cb = QCheckBox("Match spacing with previous edge")
        self.match_previous_cb.setStyleSheet("color:#a0b0d0; font-size:11px;")
        self.match_previous_cb.setToolTip("Match the end spacing of the previous edge for smooth transitions")

        self.auto_split_angle_sb = CleanDoubleSpinBox()
        self.auto_split_angle_sb.setRange(0.0, 180.0)
        self.auto_split_angle_sb.setValue(30.0)
        self.auto_split_angle_sb.setDecimals(1)
        self.auto_split_angle_sb.setSuffix("°")
        self.auto_split_angle_sb.setStyleSheet(SPIN_STYLE)
        self.auto_split_angle_sb.setToolTip("Angle threshold (degrees) for detecting sharp corners in auto-split")

        self.auto_split_form = QFormLayout()
        self.auto_split_form.addRow(help_label("Detection Angle:", "Angle threshold (degrees) for detecting sharp corners in auto-split"), self.auto_split_angle_sb)

        self.auto_split_btn = make_button("Split at Corners", '#1b2a4a')
        self.auto_split_btn.setToolTip("Split selected edge at sharp corners based on threshold")

        self.param_stack = AdjustingStackedWidget()
        self._setup_param_forms()
        self._wire_distribution_edits()

        # ── Slim inspector: definition inline, tools in standalone windows ──
        # Header already names the edge & type, so the geometry definition is
        # shown directly beneath it (no collapsible). Distribution / Split /
        # Transform open as separate tool windows to keep the panel compact.
        self.add_widget(self.segment_type_label)
        self.add_widget(self._file_seg_label)
        self.add_widget(self._curve_group)

        # NOTE: "Assign patch / group…" was moved out of this per-edge inspector
        # into the always-visible Edge Actions panel (#1), so grouping acts on the
        # whole selection at once instead of one edge at a time. See
        # app/views/panels/edge_list_panel.py (group_btn).

        # Tool buttons (open standalone windows).
        self.distribution_btn = make_button("Distribution…", '#1b2a4a')
        self.distribution_btn.setToolTip("Set the point distribution for this edge — live preview on the canvas")
        self.split_corner_btn = make_button("Split at Corners…", '#1b2a4a')
        self.split_corner_btn.setToolTip("Split this edge at sharp corners")
        self.transform_btn = make_button("Duplicate & Transform…", '#243a52')
        self.transform_btn.setToolTip("Open the duplicate / transform tools in a separate window")
        self.add_widget(help_widget(self.distribution_btn, "Set the point distribution for this edge — live preview on the canvas"))
        self.add_widget(help_widget(self.split_corner_btn, "Split this edge at sharp corners"))
        self.add_widget(help_widget(self.transform_btn, "Open the duplicate / transform tools in a separate window"))

        def _tool_dialog(title):
            # Parented to this panel → the dialog floats above the MAIN window
            # but not above other applications (no global stay-on-top), and
            # follows the app when you switch away.
            dlg = QDialog(self)
            dlg.setWindowTitle(title)
            dlg.setStyleSheet("background:#121422; color:#cdd6f4;")
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(8, 8, 8, 8)
            lay.setSpacing(4)
            dlg.hide()
            return dlg, lay

        # Distribution window — strategy + params + match-previous + Apply.
        self._distribution_dialog, _qv = _tool_dialog("Edge Distribution")
        _qv.addLayout(sf)
        _qv.addWidget(help_widget(self.match_previous_cb, "Match the end spacing of the previous edge for smooth transitions"))
        _qv.addWidget(self.param_stack)
        self.distribution_apply_btn = make_button("Apply", '#1e4620')
        self.distribution_apply_btn.setToolTip("Apply the distribution and show the resampled result on the canvas")
        _qv.addWidget(help_widget(self.distribution_apply_btn, "Apply the distribution and show the resampled result on the canvas"))

        # Split-at-corners window — detection angle + action.
        self._split_dialog, _sv = _tool_dialog("Split at Corners")
        _sv.addLayout(self.auto_split_form)
        _sv.addWidget(help_widget(self.auto_split_btn, "Split selected edge at sharp corners based on threshold"))

        # Duplicate & Transform window.
        self._transform_dup_group = TransformPanel()
        self._transform_dialog, _tl = _tool_dialog("Duplicate & Transform")
        _tl.addWidget(self._transform_dup_group)

        self.split_corner_btn.clicked.connect(self._open_split_dialog)
        # distribution_btn and transform_btn are wired by the controller (they
        # also start the live canvas preview / transform gizmo).

        # Align form layouts (per-shape forms returned by _build_shape_stack,
        # plus this panel's own strategy / split forms).
        for layout in _shape_forms + [rf, sf, self.auto_split_form]:
            align_form_labels(layout)

        # Slightly smaller fonts throughout the inspector for a denser, more
        # industrial feel.
        self.setStyleSheet(
            "QLabel{font-size:11px;} QCheckBox{font-size:11px;}"
            " QGroupBox{font-size:11px;} QGroupBox::title{font-size:11px;}"
            " QSpinBox,QDoubleSpinBox,QLineEdit{font-size:11px;}")

        self.curve_mode_param.toggled.connect(self._on_curve_mode_toggled)

    def show_file_segment(self, start: int, end: int):
        self._file_seg_label.setVisible(True)
        self._curve_group.setVisible(False)
        # Discrete edges are resampled → offer the Distribution tool.
        self.distribution_btn.setVisible(True)
        # The toolbar "Apply" duplicated "Preview" (both run the full resampler),
        # so it is no longer shown — use the toolbar "Preview" for a full preview
        # and the Distribution window's Apply for a single edge.
        self.preview_kind_changed.emit("")
        self._file_seg_label.setText(f"Start Index: {start}    End Index: {end}")

    def show_curve_segment(self, seg):
        self._file_seg_label.setVisible(False)
        self._curve_group.setVisible(True)
        # Analytic edges set their point count in Definition (Node Count); the
        # resampling-strategy Distribution does not apply to analytic edges.
        self.distribution_btn.setVisible(False)
        self._distribution_dialog.hide()
        self.preview_kind_changed.emit("curve")

        curve_type = getattr(seg, "curve_type", "custom")
        if curve_type in CURVE_TYPES:
            idx = CURVE_TYPES.index(curve_type)
            with block_signals(self.curve_type_combo):
                self.curve_type_combo.setCurrentIndex(idx)
            self.shape_stack.setCurrentIndex(idx)
        else:
            with block_signals(self.curve_type_combo):
                self.curve_type_combo.setCurrentIndex(0)
            self.shape_stack.setCurrentIndex(0)

        # Populate shape-specific inputs from the shared param↔widget mapping.
        shape_spec.write_widget_params(self, curve_type, seg.parameters)

        is_p = (seg.curve_mode == "parametric")
        self.curve_mode_param.setChecked(is_p)
        self.curve_mode_explicit.setChecked(not is_p)
        self._param_widget.setVisible(is_p)
        self._explicit_widget.setVisible(not is_p)
        self.curve_x_formula.setText(seg.x_formula)
        self.curve_y_formula.setText(seg.y_formula)
        self.curve_formula.setText(seg.formula)
        self.curve_t_min.setValue(seg.t_min)
        self.curve_t_max.setValue(seg.t_max)
        self.curve_n.setValue(seg.parameters.get("n_points", 100))
        self.curve_start_node.setValue(seg.start_index)
        self.curve_end_node.setValue(seg.end_index)

        # #2: the By-Node/By-Spacing mode row applies to polygon only; a stored
        # 'spacing' key means the polygon is distributed by spacing.
        is_poly = (curve_type == "polygon")
        self.curve_dist_mode.setVisible(is_poly)
        if self._curve_mode_label:
            self._curve_mode_label.setVisible(is_poly)
        spacing_mode = is_poly and ("spacing" in seg.parameters)
        with block_signals(self.curve_dist_mode):
            self.curve_dist_mode.setCurrentIndex(1 if spacing_mode else 0)
        if spacing_mode:
            self.curve_spacing.setValue(seg.parameters.get("spacing", 0.1))
        self._toggle_curve_dist_mode(spacing_mode)

    def _toggle_curve_dist_mode(self, spacing_on: bool):
        """Swap the Node-Count row for the Spacing (Δs) row (#2)."""
        self.curve_n.setVisible(not spacing_on)
        if self._curve_n_label:
            self._curve_n_label.setVisible(not spacing_on)
        self.curve_spacing.setVisible(spacing_on)
        if self._curve_spacing_label:
            self._curve_spacing_label.setVisible(spacing_on)

    def show_segment_props(self, visible: bool):
        self.setVisible(visible)
        if visible:
            # Selecting an edge should surface its properties immediately rather
            # than leaving them behind a collapsed header the user must hunt for.
            self.expand()
        if not visible:
            self.preview_kind_changed.emit("")

    # ── What this panel's tool windows answer ────────────────────────────
    # The sidebar used to reach _transform_dup_group and _distribution_dialog
    # directly. They are this panel's internals: it composes them, so it is the
    # one that may name them, and the sidebar asks the panel instead.

    def distribution_tool_visible(self) -> bool:
        return self._distribution_dialog.isVisible()

    def wire_distribution_dialog_closed(self, slot):
        self._distribution_dialog.finished.connect(lambda _result: slot())

    def wire_transform_dialog_closed(self, slot):
        self._transform_dialog.finished.connect(lambda _result: slot())

    def transform_spec(self):
        return self._transform_dup_group.transform_spec()

    def set_transform_reference_editable(self, editable: bool):
        self._transform_dup_group.set_transform_reference_editable(editable)

    def set_transform_reference(self, point):
        self._transform_dup_group.set_transform_reference(point)

    def set_transform_reference_applicable(self, applicable: bool):
        self._transform_dup_group.set_transform_reference_applicable(applicable)

    def use_custom_transform_reference(self):
        self._transform_dup_group.use_custom_transform_reference()

    def set_transform_handle(self, handle: str, x: float, y: float):
        self._transform_dup_group.set_transform_handle(handle, x, y)

    def show_transform_panel(self, visible: bool):
        self._transform_dup_group.setVisible(visible)

    def connect_transform_signals(self, on_edited, on_type_changed,
                                  on_base_mode_changed):
        tp = self._transform_dup_group
        tp.transform_edited.connect(on_edited)
        tp.transform_type_changed.connect(on_type_changed)
        tp.transform_base_mode_changed.connect(on_base_mode_changed)

    def wire_duplicate_requested(self, slot):
        self._transform_dup_group.dup_btn.clicked.connect(slot)
