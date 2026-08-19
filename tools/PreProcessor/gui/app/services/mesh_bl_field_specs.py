"""The boundary-layer parameter TABLE — one declaration for all 21 BL parameters.

There are two hosts for these parameters and they used to be described five times over.
The Edit-BL dialog (per-geometry and global) built its fields from ``_BL_FIELD_SPECS``;
the mesh panel hand-built the same 21 widgets 30 lines apart as hidden backing widgets;
``_BL_OVERRIDE_KEYS`` paired each KEY with its ``MeshConfig`` attribute;
``_BL_INT_ATTRS``/``_BL_BOOL_ATTRS`` carried the coercion; and
``mesh_bl_mixin._read_bl_widgets`` / ``_write_bl_widgets`` / ``_wire_bl_widgets`` walked
the same 21 by hand three more times. One knob, e.g. ``BL_TRANSITION_BUFFER``, was named
16 times across 7 files.

:data:`BL_SPECS` is now the single declaration: the ``.dat``/``Config.hpp`` KEY, the
``MeshConfig`` attribute, the label, the widget kind and its range/choices. Everything
below it is DERIVED and keeps its old name, so the dialog, the panel, the layout mixin,
``services/config_ownership.py`` and two tests are unchanged callers:

* ``_BL_OVERRIDE_KEYS`` — (KEY, attr) pairs.
* ``_BL_INT_ATTRS`` / ``_BL_BOOL_ATTRS`` — read off ``MeshConfig``'s own declared field
  types rather than off the widget kind. That is the right source and it matters:
  ``bl_auto_fan_nodes`` is edited by a THREE-value combo (OFF/GLOBAL/LOCAL) while the
  model field is a bool, so deriving the coercion from the widget would put an int in a
  bool field and make the model disagree with its own dataclass default.
* ``_BL_FIELD_SPECS`` — the legacy ``(KEY, label, kind, opts)`` tuples, kept for
  ``tests/test_sci_spinbox.py`` and ``tests/test_bl_dialog_sections.py``, which read
  ``kind == "float"`` plus ``opts["sci"]`` for the physical-length rule.

``_BL_FIELD_GROUPS`` stays hand-written on purpose: it is a layout decision (which
collapsible section a parameter appears in), not a per-field fact, and it has its own
gate. Pure data plus one float comparison — no Qt widgets; the kind→widget mapping lives
in ``field_widgets.py`` and is shared with every other config panel.
"""
from __future__ import annotations

from app.models.mesh_config import MeshConfig
from app.services.field_spec import FieldSpec, model_types, panel_table

_ANGLE = dict(lo=0.0, hi=360.0, dec=2, step=1.0)
_RATE = dict(lo=1.001, hi=5.0, dec=4, step=0.05)

_C1_TIP = ("Only used by Junction Method 0 (Taper-to-zero). Method 1's slide bound "
           "is geometric (95 deg) and not adjustable, so this value has no effect "
           "there — it is kept for method 0 and for config round-trip.")
# The wording the mesh panel's (hidden) backing spinboxes already carried for C2/C3;
# reusing it puts the explanation where the parameter is actually edited.
_JUNCTION_TIP = ("Flow-facing angle thresholds (deg) that bin the BL/no-BL "
                 "junction scheme: C2/C3 pick the cap direction "
                 "(perpendicular / along the reversed neighbour edge). "
                 "Below 95 deg the corner is too narrow for any cap — the "
                 "column slides along the neighbour edge instead; that bound "
                 "is geometric and not adjustable, so C1 is kept for "
                 "Taper-to-zero and config round-trip only. "
                 "Only used when Junction Method = 4-case.")
_AUTO_CHOICES = [(0, "OFF"), (1, "GLOBAL"), (2, "LOCAL")]

#: Every boundary-layer parameter a geometry can override, in the order both hosts lay
#: them out. ``group`` names the panel's (hidden) backing form that builds the widget.
BL_SPECS: tuple[FieldSpec, ...] = (
    # sci: a physical length that routinely needs 1e-7..1e-8 (y+~1 on a
    # chord-normalised geometry), which a fixed-notation box cannot express.
    FieldSpec("bl_initial_thickness", "sci", "Initial Thickness",
              "Height of the first boundary layer cell adjacent to the wall. "
              "Accepts scientific notation (e.g. 2.5e-7).",
              key="BL_INITIAL_THICKNESS", group="bl_core",
              opts=dict(lo=0.0, hi=1e4)),
    FieldSpec("bl_growth_rate", "float", "Growth Rate",
              "Multiplicative growth factor between successive BL layers "
              "(e.g. 1.2 = 20% increase per layer)",
              key="BL_GROWTH_RATE", group="bl_core", opts=dict(_RATE)),
    FieldSpec("bl_layers", "int", "Layers",
              "Total number of structured boundary layer rows to generate",
              key="BL_LAYERS", group="bl_core", opts=dict(lo=0, hi=100)),

    FieldSpec("bl_convex_method", "choice", "Convex Method",
              "Method for handling convex (outward-pointing) corners in the "
              "boundary layer",
              key="BL_CONVEX_METHOD", group="convex",
              opts=dict(choices=[(0, "Fan"), (2, "Parallelogram")], fallback=2)),
    FieldSpec("bl_fan_nodes", "int", "Fan Nodes",
              "Number of fan elements inserted at convex corners (Fan method only)",
              key="BL_FAN_NODES", group="convex", opts=dict(lo=1, hi=100)),
    FieldSpec("bl_auto_fan_nodes", "choice", "Auto Fan Nodes",
              "Automatically determine fan node count based on corner angle",
              key="BL_AUTO_FAN_NODES", group="convex",
              opts=dict(choices=list(_AUTO_CHOICES), fallback=0)),
    FieldSpec("bl_fan_angle_threshold", "float", "Fan Threshold (deg)",
              "Minimum corner angle (degrees) to trigger fan insertion",
              key="BL_FAN_ANGLE_THRESHOLD", group="convex", opts=dict(_ANGLE)),
    FieldSpec("bl_convex_angle_threshold", "float", "Convex Threshold (deg)",
              "Angle threshold to classify a corner as convex",
              key="BL_CONVEX_ANGLE_THRESHOLD", group="convex", opts=dict(_ANGLE)),
    FieldSpec("bl_para_fallback_angle", "float", "Para Fallback (deg)",
              "When corner angle exceeds this, fall back to parallelogram method",
              key="BL_PARA_FALLBACK_ANGLE", group="convex", opts=dict(_ANGLE)),

    # panel_choices: the mesh panel's backing combo offers method 5 ONLY, because
    # method 0 (Merge) is CLI-side and the GUI has never emitted it. The dialog still
    # offers both. One documented asymmetry on one spec, rather than a second list.
    FieldSpec("bl_concave_method", "choice", "Concave Method",
              "Method for handling concave (inward-pointing) corners in the "
              "boundary layer",
              key="BL_CONCAVE_METHOD", group="concave",
              opts=dict(choices=[(0, "Merge"), (5, "Thickness Blending")],
                        panel_choices=[(5, "5: Thickness Blending")])),
    FieldSpec("bl_concave_angle_threshold", "float", "Concave Threshold (deg)",
              "Angle threshold to classify a corner as concave",
              key="BL_CONCAVE_ANGLE_THRESHOLD", group="concave", opts=dict(_ANGLE)),
    FieldSpec("bl_concave_influence_multiplier", "float", "Concave Influence",
              "Controls how far the concave corner correction propagates along the wall",
              key="BL_CONCAVE_INFLUENCE_MULTIPLIER", group="concave",
              opts=dict(lo=0.0, hi=100.0, dec=2, step=0.5)),

    FieldSpec("bl_junction_method", "choice", "Junction Method",
              "How a BL edge meeting a no-BL neighbour is capped "
              "(1: angle-driven, default)",
              key="BL_JUNCTION_METHOD", group="concave",
              opts=dict(choices=[(0, "Taper-to-zero"), (1, "4-case angle-driven")],
                        fallback=1)),
    # C1 binned the old scheme's concave slide. Method 1 does not read it: its slide
    # bound is geometric (a cap must point into the fluid wedge, so below ~90 deg it
    # provably leaves the domain) and therefore hard-coded in BoundaryLayer.cpp. The
    # field stays for method 0 and for config round-trip, and says so — a knob that
    # cannot do anything must not look adjustable.
    FieldSpec("bl_junction_angle_c1", "float", "Junction θ C1 (deg)", _C1_TIP,
              key="BL_JUNCTION_ANGLE_C1", group="concave", opts=dict(_ANGLE)),
    FieldSpec("bl_junction_angle_c2", "float", "Junction θ C2 (deg)", _JUNCTION_TIP,
              key="BL_JUNCTION_ANGLE_C2", group="concave", opts=dict(_ANGLE)),
    FieldSpec("bl_junction_angle_c3", "float", "Junction θ C3 (deg)", _JUNCTION_TIP,
              key="BL_JUNCTION_ANGLE_C3", group="concave", opts=dict(_ANGLE)),

    FieldSpec("bl_transition_layers", "int", "Transition Layers",
              "Number of transitional element rows blending BL quads into "
              "far-field triangles",
              key="BL_TRANSITION_LAYERS", group="transition", opts=dict(lo=0, hi=100)),
    FieldSpec("bl_auto_transition_layers", "choice", "Auto Transition",
              "Automatically compute transition layer count (OFF / GLOBAL / LOCAL)",
              key="BL_AUTO_TRANSITION_LAYERS", group="transition",
              opts=dict(choices=list(_AUTO_CHOICES), fallback=0)),
    FieldSpec("bl_transition_growth_rate", "float", "Transition Growth",
              "Growth rate applied within the transition zone between BL and far-field",
              key="BL_TRANSITION_GROWTH_RATE", group="transition", opts=dict(_RATE)),
    FieldSpec("bl_transition_buffer", "float", "Transition Buffer",
              "Buffer distance multiplier around geometry for transition smoothing",
              key="BL_TRANSITION_BUFFER", group="transition",
              opts=dict(lo=0.0, hi=100.0, dec=4, step=0.5)),

    # text="": the checkbox itself stays unlabelled so the dialog's form label is the
    # only place the name appears (the panel's row for it is in a hidden section).
    FieldSpec("bl_use_analytic_geom", "bool", "Analytic BL Normals",
              "Grow the boundary layer along exact analytic normals on line/circle "
              "surface segments (instead of finite differences). No effect on "
              "smooth/polyline bodies. Uses the curve kind carried in the geometry's "
              ".meta sidecar.",
              key="BL_USE_ANALYTIC_GEOM", group="transition",
              opts=dict(text="", as_int=True)),
)


# ── derived views of the one table ──────────────────────────────────────────
#: The same 21 fields as the mesh panel's own (hidden) backing widgets see them: the
#: only difference is BL_CONCAVE_METHOD's narrowed choice list (see panel_variant).
PANEL_BL_SPECS: tuple[FieldSpec, ...] = panel_table(BL_SPECS)

#: The .dat/C++ KEY paired with its MeshConfig attribute.
_BL_OVERRIDE_KEYS = [(s.key, s.attr) for s in BL_SPECS]

_BL_MODEL_TYPES = model_types(MeshConfig)
#: Coercion for _apply_global_bl_to_cfg, read off the MODEL's declared types.
_BL_BOOL_ATTRS = {s.attr for s in BL_SPECS if _BL_MODEL_TYPES.get(s.attr) == "bool"}
_BL_INT_ATTRS = {s.attr for s in BL_SPECS if _BL_MODEL_TYPES.get(s.attr) == "int"}


def _legacy_spec(s: FieldSpec) -> tuple[str, str, str, dict]:
    """One spec as the historical ``(KEY, label, kind, opts)`` tuple.

    ``sci`` was spelled ``("float", {"sci": True})`` before it became a kind of its
    own; two tests read it that way and the translation keeps them honest callers
    rather than rewritten ones.
    """
    opts = dict(s.opts)
    kind = s.kind
    if kind == "sci":
        kind, opts["sci"] = "float", True
    if s.tip:
        opts["tip"] = s.tip
    return (s.key, s.label, kind, opts)


_BL_FIELD_SPECS = [_legacy_spec(s) for s in BL_SPECS]

# How the dialog LAYS OUT those fields: (title, start_expanded, hint, [keys]).
# 21 fields in one flat form meant scrolling past every corner and junction knob to
# reach the three numbers that actually define the layer stack, so the fields are
# grouped by the job they do. USER-REQUESTED: every group starts CLOSED, so the dialog
# opens as a short list of headers and the window is only as tall as what you asked to
# see. Two things still open a group, and neither is a default: the state the user left
# it in last time (ui_state), and a group holding a per-geometry OVERRIDE — that one is
# a safety property, not a preference, since a value that differs from the global must
# not hide behind a collapsed header. Groups follow the .dat parameter groups (see
# CLAUDE.md / include/Config.hpp) so a user reading a config file finds the same
# partition here.
# INVARIANT: these keys must partition BL_SPECS exactly — a key listed in no group
# would be an unreachable parameter, i.e. a setting that silently keeps whatever value
# it had. Gated by tests/test_bl_dialog_sections.py, and any stray key still gets built
# into a trailing "Other" group by mesh_bl_dialog_layout as a backstop.
_BL_FIELD_GROUPS = [
    ("Layer Growth", False,
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
