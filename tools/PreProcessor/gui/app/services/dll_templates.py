"""Authoritative C++ skeletons + parameter templates for unicones IBM DLLs.

Public facade. The actual renderer bodies live in sibling modules:

  * ``dll_templates_core`` — type-key constants, prototypes, ``ParamSpec`` /
    ``TemplateSpec``. (Its private ``_n`` number formatter is imported straight
    from there by the renderer modules, not re-exported here.)
  * ``dll_render_init`` — init-condition renderers (IBM + non-IBM) and
    ``render_analytic_phi_from_shape``.
  * ``dll_render_bc`` — boundary-condition renderers.
  * ``dll_render_motion`` — solid-motion renderers.
  * ``dll_phi_field`` — ``render_phi_field_init`` (STL3d phi field).

Tier 1 = parameterised templates (no C++ needed); Tier 2 = the user edits the
generated source freely before compiling.

Pure Python, no Qt — importable by both the dialog and tests.
"""
from __future__ import annotations

from app.services.dll_templates_core import (
    INIT_COND, SOLID_MOTION, BC_INFLOW,
    PROTO_INIT, PROTO_MOTION, PROTO_BC,
    ParamSpec, TemplateSpec,
)
from app.services.dll_render_init import (
    _render_init_freestream, _render_init_rotating_disk, _render_init_custom,
    render_analytic_phi_from_shape,
    _render_init_freestream_noibm, _render_init_shock_noibm,
)
from app.services.dll_render_bc import (
    _render_bc_uniform, _render_bc_inflow_angle, _render_bc_custom,
)
from app.services.dll_render_motion import (
    _render_motion_stationary, _render_motion_rotation,
    _render_motion_translation, _render_motion_custom,
)
from app.services.dll_phi_field import render_phi_field_init

# This module is a FACADE: several of the imports above are re-exports for
# callers (``from app.services.dll_templates import render_phi_field_init``, the
# dialog's bulk import, the analytic-phi controller, tests) and are not used in
# this file's own body. ``__all__`` states that explicitly — without it an
# unused-import cleanup strips them and every importer breaks at import time.
__all__ = [
    # constants / specs
    "INIT_COND", "SOLID_MOTION", "BC_INFLOW",
    "PROTO_INIT", "PROTO_MOTION", "PROTO_BC",
    "ParamSpec", "TemplateSpec",
    # renderers re-exported for direct use
    "render_analytic_phi_from_shape", "render_phi_field_init",
    # this module's own API
    "TEMPLATES", "templates_for", "default_basename",
]


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
_MACH = ParamSpec("mach", "Mach", 0.2, 4, "Reference Mach number")
_GAMMA = ParamSpec("gamma", "gamma", 1.4, 4, "Ratio of specific heats")

TEMPLATES: dict[str, list[TemplateSpec]] = {
    INIT_COND: [
        TemplateSpec(
            "freestream", "Uniform freestream", INIT_COND,
            "Uniform flow everywhere; no solid marking (phi = 0).",
            _render_init_freestream,
            [_MACH, _GAMMA,
             ParamSpec("rho", "rho", 1.0), ParamSpec("u", "u", 1.0),
             ParamSpec("v", "v", 0.0), ParamSpec("w", "w", 0.0)]),
        TemplateSpec(
            "rotating_disk", "Rotating solid disk", INIT_COND,
            "Freestream outside; a rotating solid disk (phi = 1) inside the radius.",
            _render_init_rotating_disk,
            [ParamSpec("cx", "center x", 0.0), ParamSpec("cy", "center y", 0.0),
             ParamSpec("radius", "radius", 0.52), ParamSpec("ratio", "edge vel", 1.0),
             _MACH, _GAMMA]),
        TemplateSpec(
            "freestream_noibm", "Uniform freestream (no IBM, 4-var)", INIT_COND,
            "Non-IBM uniform flow; Q has 4 components (no solid-phase phi).",
            _render_init_freestream_noibm,
            [_MACH, _GAMMA, ParamSpec("rho", "rho", 1.0),
             ParamSpec("u", "u", 1.0), ParamSpec("v", "v", 0.0)]),
        TemplateSpec(
            "shock_noibm", "Normal shock (no IBM, 4-var)", INIT_COND,
            "Non-IBM normal shock split at x0; pre/post states from the ratios.",
            _render_init_shock_noibm,
            [_MACH, _GAMMA, ParamSpec("x0", "shock x", 0.0),
             ParamSpec("t2t1", "T2/T1", 0.822, 4),
             ParamSpec("r2r1", "rho2/rho1", 0.631, 4)]),
        TemplateSpec(
            "custom", "Custom (blank skeleton)", INIT_COND,
            "The correct prototype + a freestream default to edit freely.",
            _render_init_custom, []),
    ],
    SOLID_MOTION: [
        TemplateSpec(
            "stationary", "Stationary", SOLID_MOTION,
            "Solid does not move (U = V = W = 0).",
            _render_motion_stationary, []),
        TemplateSpec(
            "rotation", "Rigid rotation (2D)", SOLID_MOTION,
            "Rigid-body rotation about a center; velocity = 1 at the given radius.",
            _render_motion_rotation,
            [ParamSpec("cx", "center x", 0.0), ParamSpec("cy", "center y", 0.0),
             ParamSpec("radius", "radius", 0.52), ParamSpec("ratio", "edge vel", 1.0)]),
        TemplateSpec(
            "translation", "Translation", SOLID_MOTION,
            "Constant translational velocity.",
            _render_motion_translation,
            [ParamSpec("ux", "U", 1.0), ParamSpec("uy", "V", 0.0),
             ParamSpec("uz", "W", 0.0)]),
        TemplateSpec(
            "custom", "Custom (blank skeleton)", SOLID_MOTION,
            "The correct prototype + a zero-velocity default to edit freely.",
            _render_motion_custom, []),
    ],
    BC_INFLOW: [
        TemplateSpec(
            "angle", "Angled inflow (stagnation hold)", BC_INFLOW,
            "Inflow at a fixed angle holding stagnation p0/T0 (from inflow_ang.cc).",
            _render_bc_inflow_angle,
            [_MACH, _GAMMA, ParamSpec("angle_deg", "angle (deg)", 5.5, 3,
                                      "Flow angle from +x, in degrees")]),
        TemplateSpec(
            "uniform", "Fixed uniform inflow", BC_INFLOW,
            "Constant (rho, u, v, p) inflow state.",
            _render_bc_uniform,
            [_GAMMA, ParamSpec("rho", "rho", 1.0), ParamSpec("u", "u", 1.0),
             ParamSpec("v", "v", 0.0), ParamSpec("p", "p", 1.0, 5)]),
        TemplateSpec(
            "custom", "Custom (blank skeleton)", BC_INFLOW,
            "The correct getQ_inst_dll prototype + an editable default.",
            _render_bc_custom, []),
    ],
}


def templates_for(dll_type: str) -> list[TemplateSpec]:
    return TEMPLATES.get(dll_type, [])


def default_basename(dll_type: str, template_key: str) -> str:
    prefix = {INIT_COND: "init_cond", SOLID_MOTION: "motion",
              BC_INFLOW: "bc"}.get(dll_type, dll_type)
    return f"{prefix}_{template_key}"
