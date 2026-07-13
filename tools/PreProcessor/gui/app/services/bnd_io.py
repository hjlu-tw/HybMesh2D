"""Read the STAR-CD ``.bnd`` boundary file produced by HybMesh2D and recover the
per-patch (segment-number, patch-name) list, so the solver Boundary-Conditions
table can be populated with the REAL segment numbers the mesher assigned.

Why this exists: the mesher assigns each distinct boundary patch NAME its own
integer segment id in first-appearance order (not a fixed "1-4 = box, 5 = geom"
convention). getPGrid then keys its ``segm_no bc_flag`` table off those ids. So
the only reliable way to know which segment number corresponds to which patch is
to read the generated ``.bnd``:

    <bndId> <v1> <v2> 0 0 <segId> 0 <patchName>      # 8 columns (2D)

The segment id is column 6 (1-based) and the patch name is column 8.

``default_bc_flag_for_name`` mirrors getPGrid's ``getBCType`` name→flag mapping
(plus a few friendly aliases) so the table pre-selects a sensible physical BC
type per patch; the user can override it. The integer flags match both
getPGrid's BCType enum and ``solver_config.BC_TYPES``.
"""
from __future__ import annotations
import os


def bnd_path_for(base_or_vtk: str) -> str:
    """Return the ``.bnd`` path for a mesh output base name or a .vtk path."""
    base = os.path.splitext(base_or_vtk)[0] if base_or_vtk else ""
    return base + ".bnd"


def read_bnd_segments(bnd_path: str) -> list[tuple[int, str]]:
    """Return the ordered, de-duplicated ``[(seg_id, patch_name), ...]`` from a
    STAR-CD ``.bnd`` file (segment id = column 6, name = column 8). Empty list if
    the file is missing/unreadable. Ordered by segment id."""
    if not bnd_path or not os.path.exists(bnd_path):
        return []
    seen: dict[int, str] = {}
    try:
        with open(bnd_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                parts = line.split()
                if len(parts) < 6:
                    continue
                try:
                    sid = int(parts[5])          # column 6 (0-based index 5)
                except ValueError:
                    continue
                name = parts[7] if len(parts) >= 8 else ""
                # First name wins for a given segment id (they're all equal).
                seen.setdefault(sid, name)
    except OSError:
        return []
    return sorted(seen.items(), key=lambda kv: kv[0])


# Name → solver BC flag, mirroring getPGrid getBCType() (see
# solver/preprocess/getPGrid/src/getPGrid.cpp). Flags line up with
# solver_config.BC_TYPES: 0 reflect/slip, 1 non-reflect far-field,
# 2 no-slip adiabatic wall, 3 no-slip isothermal wall, 5 fixed freestream,
# 6 supersonic-2D. Keyed case-insensitively; a few friendly GUI aliases
# (symmetry / farfield / movingwall) are added on top of getPGrid's tokens.
_NAME_TO_FLAG = {
    # reflect / slip / symmetry
    "symp": 0, "symp2": 0, "symmetry": 0, "slip": 0,
    # non-reflect far-field / outflow
    "outl": 1, "outflow": 1, "excp": 1, "outlet": 1,
    "farfield": 1, "far-field": 1, "far_field": 1,
    # no-slip adiabatic walls
    "wall": 2, "nozzle": 2, "sting": 2, "cyl": 2, "cylwall": 2,
    "cav": 2, "cav_wall": 2, "movingwall": 2, "moving_wall": 2,
    # no-slip isothermal wall
    "isothermal": 3,
    # fixed freestream / inflow
    "free": 5, "splbc": 5, "prof_far": 5, "tran": 5,
    "inle": 5, "inflow": 5, "inlet": 5,
    # supersonic 2D
    "s2d": 6,
}


def default_bc_flag_for_name(name: str, euler: bool = False) -> int:
    """Suggested solver BC flag for a patch name. Unknown names default to a
    solid wall (slip/reflect 0 for inviscid Euler, no-slip 2 for viscous NS),
    matching getPGrid's tolerant fallback."""
    key = (name or "").strip().lower()
    if key in _NAME_TO_FLAG:
        return _NAME_TO_FLAG[key]
    return 0 if euler else 2
