from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QFrame
from PyQt6.QtCore import Qt

from app.views.collapsible import CollapsibleSection
from app.views.panels import (
    FilePanel, GeometryPanel, VertexPanel,
    EdgeListPanel, EdgePropsPanel, AdvancedPanel, ActionsPanel
)

class SidebarView(QWidget):
    """
    Left-hand control panel — scrollable, grouped into collapsible sections.
    No emoji icons on buttons; muted/dark colour palette.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: #0c0d16;")
        scroll.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                border: none;
                background: #0c0d16;
                width: 10px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #2c2e43;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3e415e;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        content = QWidget()
        content.setStyleSheet("background: #121422; color: #a0a8c0;")
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(6, 6, 6, 6)
        self._layout.setSpacing(6)

        # 1. Project Panel (File)
        self.file_panel = FilePanel(self)
        self._layout.addWidget(self.file_panel)
        # Expose widgets
        self.load_btn = self.file_panel.load_btn
        self.load_json_btn = self.file_panel.load_json_btn
        self.new_tab_btn = self.file_panel.new_tab_btn
        self.file_name_label = self.file_panel.file_name_label
        self.is_closed_combo = self.file_panel.is_closed_combo

        # 2. Geometry Panel
        self.geometry_panel = GeometryPanel(self)
        self._layout.addWidget(self.geometry_panel)
        # Expose widgets
        self.geom_list = self.geometry_panel.geom_list
        self.toggle_visibility_btn = self.geometry_panel.toggle_visibility_btn

        # 3. Vertex Panel
        self.vertex_panel = VertexPanel(self)
        self._layout.addWidget(self.vertex_panel)
        # Expose widgets
        self.selected_info = self.vertex_panel.selected_info
        self.split_btn = self.vertex_panel.split_btn
        self.remove_split_btn = self.vertex_panel.remove_split_btn
        self.keep_vertex_cb = self.vertex_panel.keep_vertex_cb
        self.auto_detect_btn = self.vertex_panel.auto_detect_btn
        self.insert_x = self.vertex_panel.insert_x
        self.insert_y = self.vertex_panel.insert_y
        self.insert_btn = self.vertex_panel.insert_btn

        # 4. Edge Panel (List and Properties)
        self.sec_edge_parent = CollapsibleSection("Edge", start_collapsed=True)
        self._layout.addWidget(self.sec_edge_parent)

        self.edge_list_panel = EdgeListPanel(self)
        self.sec_edge_parent.add_widget(self.edge_list_panel)
        # Expose widgets
        self.file_segment_list = self.edge_list_panel.file_segment_list
        self.curve_segment_list = self.edge_list_panel.curve_segment_list
        self.add_curve_seg_btn = self.edge_list_panel.add_curve_seg_btn
        self.remove_seg_btn = self.edge_list_panel.remove_seg_btn
        self.curve_bake_btn = self.edge_list_panel.curve_bake_btn

        self.edge_props_panel = EdgePropsPanel(self)
        self.sec_edge_parent.add_widget(self.edge_props_panel)
        # Expose widgets
        self.segment_type_label = self.edge_props_panel.segment_type_label
        self._file_seg_label = self.edge_props_panel._file_seg_label
        self._curve_group = self.edge_props_panel._curve_group
        self.curve_type_combo = self.edge_props_panel.curve_type_combo
        self.shape_stack = self.edge_props_panel.shape_stack
        self.curve_mode_param = self.edge_props_panel.curve_mode_param
        self.curve_mode_explicit = self.edge_props_panel.curve_mode_explicit
        self._curve_mode_group = self.edge_props_panel._curve_mode_group
        self.curve_x_formula = self.edge_props_panel.curve_x_formula
        self.curve_y_formula = self.edge_props_panel.curve_y_formula
        self.curve_formula = self.edge_props_panel.curve_formula
        self.curve_t_min = self.edge_props_panel.curve_t_min
        self.curve_t_max = self.edge_props_panel.curve_t_max
        self.curve_n = self.edge_props_panel.curve_n
        self.curve_start_node = self.edge_props_panel.curve_start_node
        self.curve_end_node = self.edge_props_panel.curve_end_node
        self.curve_preview_btn = self.edge_props_panel.curve_preview_btn
        self.strategy_combo = self.edge_props_panel.strategy_combo
        self.match_previous_cb = self.edge_props_panel.match_previous_cb
        self.auto_split_angle_sb = self.edge_props_panel.auto_split_angle_sb
        self.auto_split_form = self.edge_props_panel.auto_split_form
        self.auto_split_btn = self.edge_props_panel.auto_split_btn
        self.param_stack = self.edge_props_panel.param_stack
        self.file_preview_btn = self.edge_props_panel.file_preview_btn

        # Transform sub-widgets (from TransformPanel inside EdgePropsPanel)
        self._transform_dup_group = self.edge_props_panel._transform_dup_group
        self.dup_type_combo = self._transform_dup_group.dup_type_combo
        self.dup_base_form = self._transform_dup_group.dup_base_form
        self.dup_base_mode_combo = self._transform_dup_group.dup_base_mode_combo
        self._dup_stack = self._transform_dup_group._dup_stack
        self.dup_rot_angle = self._transform_dup_group.dup_rot_angle
        self.dup_rot_px = self._transform_dup_group.dup_rot_px
        self.dup_rot_py = self._transform_dup_group.dup_rot_py
        self.dup_mh_py = self._transform_dup_group.dup_mh_py
        self.dup_mv_px = self._transform_dup_group.dup_mv_px
        self.dup_ma_px = self._transform_dup_group.dup_ma_px
        self.dup_ma_py = self._transform_dup_group.dup_ma_py
        self.dup_ma_dx = self._transform_dup_group.dup_ma_dx
        self.dup_ma_dy = self._transform_dup_group.dup_ma_dy
        self.dup_ps_px = self._transform_dup_group.dup_ps_px
        self.dup_ps_py = self._transform_dup_group.dup_ps_py
        self.dup_trans_dx = self._transform_dup_group.dup_trans_dx
        self.dup_trans_dy = self._transform_dup_group.dup_trans_dy
        self.dup_scale_factor = self._transform_dup_group.dup_scale_factor
        self.dup_scale_px = self._transform_dup_group.dup_scale_px
        self.dup_scale_py = self._transform_dup_group.dup_scale_py
        self.dup_delete_orig_cb = self._transform_dup_group.dup_delete_orig_cb
        self.dup_btn = self._transform_dup_group.dup_btn

        # 5. Advanced Panel
        self.advanced_panel = AdvancedPanel(self)
        self._layout.addWidget(self.advanced_panel)
        # Expose widgets
        self.global_spline_cb = self.advanced_panel.global_spline_cb
        self.quality_check_cb = self.advanced_panel.quality_check_cb
        self.show_vertices_cb = self.advanced_panel.show_vertices_cb
        self.transform_scale = self.advanced_panel.transform_scale
        self.transform_rotate = self.advanced_panel.transform_rotate
        self.transform_tx = self.advanced_panel.transform_tx
        self.transform_ty = self.advanced_panel.transform_ty
        self.apply_transform_cb = self.advanced_panel.apply_transform_cb
        self._transform_box = self.advanced_panel._transform_box

        # 6. Actions Panel
        self.actions_panel = ActionsPanel(self)
        self._layout.addWidget(self.actions_panel)
        # Expose widgets
        self.preview_btn = self.actions_panel.preview_btn
        self.save_btn = self.actions_panel.save_btn
        self.generate_btn = self.actions_panel.generate_btn

        self._layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)

    def switch_param_form(self, strategy_name: str):
        self.edge_props_panel.switch_param_form(strategy_name)

    def show_file_segment(self, start: int, end: int):
        self.edge_props_panel.show_file_segment(start, end)

    def show_curve_segment(self, seg):
        self.edge_props_panel.show_curve_segment(seg)

    def show_segment_props(self, visible: bool):
        self.edge_props_panel.show_segment_props(visible)

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
