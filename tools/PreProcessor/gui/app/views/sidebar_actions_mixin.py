"""Which widget raises which of the sidebar's intents.

Split from sidebar.py because it is a different concern from the layout — and a
growing one: every group that leaves the reach-through baseline adds a row here.

The SIGNALS themselves stay declared on SidebarView. PyQt only collects signals
from a class built by the Qt metaclass, which a plain mixin is not; this holds
the binding, not the declaration.
"""
from __future__ import annotations


class SidebarActionsMixin:
    #: intent -> (panel attribute, widget attribute, the widget's own signal).
    #: A panel of None means the widget is the sidebar's own.
    _ACTIONS = (
        ("load_requested",          "file_panel",       "load_btn",          "clicked"),
        ("load_stl_requested",      "file_panel",       "load_stl_btn",      "clicked"),
        ("load_json_requested",     "file_panel",       "load_json_btn",     "clicked"),
        ("new_tab_requested",       "file_panel",       "new_tab_btn",       "clicked"),
        ("closure_mode_changed",    "file_panel",       "is_closed_combo",   "currentTextChanged"),
        ("save_requested",          "actions_panel",    "save_btn",          "clicked"),
        ("generate_requested",      "actions_panel",    "generate_btn",      "clicked"),
        ("extrude_stl_requested",   "actions_panel",    "extrude_stl_btn",   "clicked"),
        ("split_requested",         "vertex_panel",     "split_btn",         "clicked"),
        ("remove_split_requested",  "vertex_panel",     "remove_split_btn",  "clicked"),
        ("insert_point_requested",  "vertex_panel",     "insert_btn",        "clicked"),
        ("move_vertex_requested",   "vertex_panel",     "move_btn",          "clicked"),
        ("auto_detect_requested",   "vertex_panel",     "auto_detect_btn",   "clicked"),
        ("remove_edge_requested",   "edge_list_panel",  "remove_seg_btn",    "clicked"),
        ("join_edges_requested",    "edge_list_panel",  "join_edges_btn",    "clicked"),
        ("bake_curve_requested",    "edge_list_panel",  "curve_bake_btn",    "clicked"),
        ("patch_name_requested",    "edge_list_panel",  "group_btn",         "clicked"),
        ("auto_split_requested",    "edge_props_panel", "auto_split_btn",    "clicked"),
        ("strategy_changed",        "edge_props_panel", "strategy_combo",    "currentTextChanged"),
        ("match_previous_toggled",  "edge_props_panel", "match_previous_cb", "toggled"),
        ("global_spline_toggled",   "advanced_panel",   "global_spline_cb",  "toggled"),
        ("selection_mode_changed",  None,               "select_mode_combo", "currentIndexChanged"),
    )

    def _wire_actions(self):
        for intent, panel_attr, widget_attr, qt_signal in self._ACTIONS:
            owner = getattr(self, panel_attr) if panel_attr else self
            getattr(getattr(owner, widget_attr), qt_signal).connect(
                getattr(self, intent))
