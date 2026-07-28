"""Core shared symbols for the unicones IBM DLL templates.

The solver loads two kinds of user DLL via dlopen, each an ``extern "C"`` function
with a fixed signature (the implicit contract with the solver):

  * init-condition DLL  -> ``initQ_at_p(x,y,z, Q, dQdt, dQdx, dQdy, dQdz)``
        Q = (rho, rho*u, rho*v, energy, phi)   [2D, phi is the solid marker]
  * solid-motion DLL    -> ``get_6dof_vel(time, dt, p, center, force, torque,
                                          U, V, W, rho)``
        writes the solid velocity (U,V,W) and density at point p.

These signatures are kept here as the single source of truth so the GUI's
generated code always matches what the solver expects. If the solver changes a
prototype, update it here.

Pure Python, no Qt — importable by both the dialog and tests.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from collections.abc import Callable

INIT_COND = "init_cond"
SOLID_MOTION = "motion"
BC_INFLOW = "bc_inflow"

# extern "C" prototypes echoed verbatim into every generated source.
PROTO_INIT = (
    'extern "C" void initQ_at_p(double x, double y, double z,\n'
    "                           double* Q, double* dQdt,\n"
    "                           double* dQdx, double* dQdy, double* dQdz);"
)
PROTO_MOTION = (
    'extern "C" void get_6dof_vel(double time, double dt, double* p,\n'
    "                             double* center, double* force, double* torque,\n"
    "                             double* U, double* V, double* W, double* rho);"
)
PROTO_BC = (
    'extern "C" void getQ_inst_dll(double t, double x, double y, double z,\n'
    "                              double* Q, double* dQdt,\n"
    "                              double* dQdx, double* dQdy, double* dQdz);"
)


def _n(v) -> str:
    """Format a parameter as a C++ double literal."""
    return repr(float(v))


@dataclass
class ParamSpec:
    key: str
    label: str
    default: float
    decimals: int = 4
    tip: str = ""


@dataclass
class TemplateSpec:
    key: str
    label: str
    dll_type: str
    description: str
    render: Callable[[dict], str]
    params: list[ParamSpec] = field(default_factory=list)
