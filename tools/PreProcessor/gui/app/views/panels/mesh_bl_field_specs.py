"""Boundary-layer parameter TABLES for the mesh config panel and its Edit-BL
dialog: which parameters can be overridden per geometry, how each one is edited
(widget kind + range), and how the dialog groups them into collapsible sections.

Pure data (plus one float comparison) with no Qt widgets, split out of
mesh_dialogs_bl.py so the dialog file stays inside the project's ~500-line
per-GUI-file limit. Re-exported by mesh_dialogs_bl / mesh_dialogs, so the
existing import paths keep working."""
from __future__ import annotations


# Boundary-layer parameters that can be overridden per geometry: the .dat/C++
# KEY (include/Config.hpp BLParams) paired with the MeshConfig attribute. These
# are the fields the panel's BL sections edit; when a geometry override is
# active the same widgets edit that geometry's values instead of the global ones.
_BL_OVERRIDE_KEYS = [
    ("BL_INITIAL_THICKNESS", "bl_initial_thickness"),
    ("BL_GROWTH_RATE", "bl_growth_rate"),
    ("BL_LAYERS", "bl_layers"),
    ("BL_CONVEX_METHOD", "bl_convex_method"),
    ("BL_FAN_NODES", "bl_fan_nodes"),
    ("BL_AUTO_FAN_NODES", "bl_auto_fan_nodes"),
    ("BL_FAN_ANGLE_THRESHOLD", "bl_fan_angle_threshold"),
    ("BL_CONVEX_ANGLE_THRESHOLD", "bl_convex_angle_threshold"),
    ("BL_PARA_FALLBACK_ANGLE", "bl_para_fallback_angle"),
    ("BL_CONCAVE_METHOD", "bl_concave_method"),
    ("BL_CONCAVE_ANGLE_THRESHOLD", "bl_concave_angle_threshold"),
    ("BL_CONCAVE_INFLUENCE_MULTIPLIER", "bl_concave_influence_multiplier"),
    ("BL_JUNCTION_METHOD", "bl_junction_method"),
    ("BL_JUNCTION_ANGLE_C1", "bl_junction_angle_c1"),
    ("BL_JUNCTION_ANGLE_C2", "bl_junction_angle_c2"),
    ("BL_JUNCTION_ANGLE_C3", "bl_junction_angle_c3"),
    ("BL_TRANSITION_LAYERS", "bl_transition_layers"),
    ("BL_AUTO_TRANSITION_LAYERS", "bl_auto_transition_layers"),
    ("BL_TRANSITION_GROWTH_RATE", "bl_transition_growth_rate"),
    ("BL_TRANSITION_BUFFER", "bl_transition_buffer"),
    ("BL_USE_ANALYTIC_GEOM", "bl_use_analytic_geom"),
]
# Coercion for _apply_global_bl_to_cfg (all other BL attrs are floats).
_BL_INT_ATTRS = {"bl_layers", "bl_convex_method", "bl_fan_nodes", "bl_concave_method",
                 "bl_junction_method",
                 "bl_transition_layers", "bl_auto_transition_layers"}
_BL_BOOL_ATTRS = {"bl_auto_fan_nodes", "bl_use_analytic_geom"}

# Field specs for the per-geometry BL override dialog. (KEY, label, kind, opts);
# kind: float | int | choice | bool. Keys match _BL_OVERRIDE_KEYS.
_BL_FIELD_SPECS = [
    # sci=True: a physical length that routinely needs 1e-7..1e-8 (y+~1 on a
    # chord-normalised geometry), which a fixed-notation box cannot express.
    ("BL_INITIAL_THICKNESS", "Initial Thickness", "float", dict(lo=0.0, hi=1e4, sci=True)),
    ("BL_GROWTH_RATE", "Growth Rate", "float", dict(lo=1.001, hi=5.0, dec=4, step=0.05)),
    ("BL_LAYERS", "Layers", "int", dict(lo=0, hi=100)),
    ("BL_CONVEX_METHOD", "Convex Method", "choice", dict(choices=[(0, "Fan"), (2, "Parallelogram")])),
    ("BL_FAN_NODES", "Fan Nodes", "int", dict(lo=1, hi=100)),
    ("BL_AUTO_FAN_NODES", "Auto Fan Nodes", "choice", dict(choices=[(0, "OFF"), (1, "GLOBAL"), (2, "LOCAL")])),
    ("BL_FAN_ANGLE_THRESHOLD", "Fan Threshold (deg)", "float", dict(lo=0.0, hi=360.0, dec=2, step=1.0)),
    ("BL_CONVEX_ANGLE_THRESHOLD", "Convex Threshold (deg)", "float", dict(lo=0.0, hi=360.0, dec=2, step=1.0)),
    ("BL_PARA_FALLBACK_ANGLE", "Para Fallback (deg)", "float", dict(lo=0.0, hi=360.0, dec=2, step=1.0)),
    ("BL_CONCAVE_METHOD", "Concave Method", "choice", dict(choices=[(0, "Merge"), (5, "Thickness Blending")])),
    ("BL_CONCAVE_ANGLE_THRESHOLD", "Concave Threshold (deg)", "float", dict(lo=0.0, hi=360.0, dec=2, step=1.0)),
    ("BL_CONCAVE_INFLUENCE_MULTIPLIER", "Concave Influence", "float", dict(lo=0.0, hi=100.0, dec=2, step=0.5)),
    ("BL_JUNCTION_METHOD", "Junction Method", "choice", dict(choices=[(0, "Taper-to-zero"), (1, "4-case angle-driven")])),
    ("BL_JUNCTION_ANGLE_C1", "Junction θ C1 (deg)", "float", dict(lo=0.0, hi=360.0, dec=2, step=1.0)),
    ("BL_JUNCTION_ANGLE_C2", "Junction θ C2 (deg)", "float", dict(lo=0.0, hi=360.0, dec=2, step=1.0)),
    ("BL_JUNCTION_ANGLE_C3", "Junction θ C3 (deg)", "float", dict(lo=0.0, hi=360.0, dec=2, step=1.0)),
    ("BL_TRANSITION_LAYERS", "Transition Layers", "int", dict(lo=0, hi=100)),
    ("BL_AUTO_TRANSITION_LAYERS", "Auto Transition", "choice", dict(choices=[(0, "OFF"), (1, "GLOBAL"), (2, "LOCAL")])),
    ("BL_TRANSITION_GROWTH_RATE", "Transition Growth", "float", dict(lo=1.001, hi=5.0, dec=4, step=0.05)),
    ("BL_TRANSITION_BUFFER", "Transition Buffer", "float", dict(lo=0.0, hi=100.0, dec=4, step=0.5)),
    ("BL_USE_ANALYTIC_GEOM", "Analytic BL Normals", "bool", dict()),
]

# How the dialog LAYS OUT those fields: (title, start_expanded, hint, [keys]).
# 21 fields in one flat form meant scrolling past every corner and junction knob
# to reach the three numbers that actually define the layer stack, so the fields
# are grouped by the job they do and only the first group opens. Groups follow the
# .dat parameter groups (see CLAUDE.md / include/Config.hpp) so a user reading a
# config file finds the same partition here.
# INVARIANT: these keys must partition _BL_FIELD_SPECS exactly — a key listed in
# no group would be an unreachable parameter, i.e. a setting that silently keeps
# whatever value it had. Gated by tests/test_bl_dialog_sections.py, and any
# stray key still gets built into a trailing "Other" group below.
_BL_FIELD_GROUPS = [
    ("Layer Growth", True,
     "The layer stack itself: first-cell height, growth per layer, layer count.",
     ["BL_INITIAL_THICKNESS", "BL_GROWTH_RATE", "BL_LAYERS"]),
    # Second, right under the stack it continues: the transition rows are part of
    # the same "how thick, how many" decision, not a corner-handling detail.
    ("Transition Layers", False,
     "The rows that blend the BL quads into the far-field triangles.",
     ["BL_AUTO_TRANSITION_LAYERS", "BL_TRANSITION_LAYERS",
      "BL_TRANSITION_GROWTH_RATE", "BL_TRANSITION_BUFFER"]),
    ("Convex Corners", False,
     "How the layer turns the outside of a corner (fan vs parallelogram).",
     ["BL_CONVEX_METHOD", "BL_FAN_NODES", "BL_AUTO_FAN_NODES",
      "BL_FAN_ANGLE_THRESHOLD", "BL_CONVEX_ANGLE_THRESHOLD",
      "BL_PARA_FALLBACK_ANGLE"]),
    ("Concave Corners", False,
     "How the layer thins where the wall turns inward, and how far that reaches.",
     ["BL_CONCAVE_METHOD", "BL_CONCAVE_ANGLE_THRESHOLD",
      "BL_CONCAVE_INFLUENCE_MULTIPLIER"]),
    ("BL / No-BL Junction", False,
     "How a BL edge is finished where it meets a no-BL edge (e.g. an inlet face).",
     ["BL_JUNCTION_METHOD", "BL_JUNCTION_ANGLE_C1", "BL_JUNCTION_ANGLE_C2",
      "BL_JUNCTION_ANGLE_C3"]),
    ("Advanced", False,
     "Rarely changed; leave alone unless the mesh asks for it.",
     ["BL_USE_ANALYTIC_GEOM"]),
]


def _value_differs(a, b) -> bool:
    """True when a seeded value is a real change from the default it was seeded
    from. Relative tolerance, because these values span 1e-8 (first-cell height)
    to 360 (angles) and an absolute epsilon would be wrong at one end or the
    other."""
    if a is None or b is None:
        return False
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return a != b
    return abs(fa - fb) > 1e-9 * max(1.0, abs(fb))
