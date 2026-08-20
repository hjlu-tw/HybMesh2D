"""What the Results surface plot is allowed to use as "the surface".

The extraction maths lives in ``services/surface_source.py``; this mixin answers
the question that comes first — which sources this session can actually offer
right now, and why the others are greyed out. Two rules:

* **Availability is decided here, not in the dialog**, so the reason a source is
  unavailable is one sentence written once ("run STL3d first", "no closed CAD
  shape"), instead of a disabled radio button with no explanation.
* **Nothing is extracted while the user is still choosing** (USER-REQUESTED). Every
  option carries only cheap metadata — a variable list, a grid size, a shape
  description. Contouring a field or chaining an interface point cloud happens in
  ``build_surface`` after the user commits, because on a large result those are
  seconds of work and the user may be picking a different source entirely.
"""
from __future__ import annotations

import os

import numpy as np

from app.services import surface_source as ss
from app.services.analytic_shape import describe, shape_dict, solid_shapes
from app.services.logging_setup import get_logger

_log = get_logger(__name__)


class SurfaceSourceControllerMixin:
    # ------------------------------------------------------------------ #
    # Data providers
    # ------------------------------------------------------------------ #
    def surface_stl3d_phi(self) -> dict | None:
        """The STL3d φ field held by the IB stage, or None.

        Returns the field with its grid dimensions, because a φ array on its own
        cannot be contoured — the structured shape is what makes it a field
        rather than a list of numbers, and a mismatch between the two means the
        panel's Nx/Ny/Nz was edited after the run.
        """
        pts = getattr(self, "_stl3d_phi_pts", None)
        phi = getattr(self, "_stl3d_phi_val", None)
        if pts is None or phi is None or len(np.asarray(phi)) == 0:
            return None
        cfg = getattr(self, "global_stl3d_config", None)
        if cfg is None:
            return None
        nx, ny, nz = int(cfg.nx), int(cfg.ny), int(cfg.nz)
        dx, dy, dz = cfg.spacings()
        out = {"pts": np.asarray(pts), "phi": np.asarray(phi),
               "nx": nx, "ny": ny, "nz": nz, "dx": dx, "dy": dy, "dz": dz,
               "match": nx * ny * nz == len(np.asarray(phi))}
        return out

    def surface_analytic_shapes(self) -> list:
        """Analytic solid shapes from the active CAD session, newest info first.

        ``in_use`` marks the shape the solver config is actually running (an
        analytic-φ init DLL with no phi.dat), so the dialog can say which of
        several CAD bodies is the one being solved.
        """
        session = self.active_session() if hasattr(self, "active_session") else None
        sc = getattr(self, "global_solver_config", None)
        dll = os.path.basename(getattr(sc, "init_cond_dll", "") or "")
        analytic_run = bool(dll.startswith("ibm_phi_shape_edge")
                            and not (getattr(sc, "ibm_phi_file", "") or ""))
        out: list = []
        for seg in solid_shapes(session):
            sh = shape_dict(session, seg)
            if sh is None:
                continue
            sid = sh.get("seg_id")
            sh["label"] = f"Edge {sid}: {describe(sh)}"
            sh["in_use"] = bool(analytic_run and f"edge{sid}." in dll)
            out.append(sh)
        return out

    # ------------------------------------------------------------------ #
    # The option list the dialog renders
    # ------------------------------------------------------------------ #
    def surface_source_options(self, result=None) -> list:
        """One entry per source: kind, label, whether it is usable, and why not.

        ``detail`` is a short line the dialog shows under the label; it must stay
        cheap to produce (see the module docstring) — no contouring, no loop
        tracing.
        """
        opts: list = []

        has_mesh = result is not None and len(getattr(result, "elements", [])) > 0
        opts.append({
            "kind": ss.KIND_MESH, "enabled": has_mesh,
            "reason": "" if has_mesh else "no result loaded",
            "detail": "Inner boundary loops of the solved grid — the points are "
                      "mesh nodes, so values are exact (no interpolation).",
        })

        scalars = list(result.scalar_variables()) if result is not None else []
        has_phi = "phi" in scalars
        opts.append({
            "kind": ss.KIND_FIELD_ISO, "enabled": bool(scalars),
            "reason": "" if scalars else "no result loaded",
            "vars": scalars, "default_var": "phi" if has_phi else (
                scalars[0] if scalars else ""),
            "detail": ("φ = 0.5 is the immersed solid's surface on the SOLVED "
                       "mesh." if has_phi else
                       "This result carries no φ — an iso-line of another "
                       "variable is not a body surface."),
        })

        g = self.surface_stl3d_phi()
        grid_ok = bool(g and g["match"])
        if g and not g["match"]:
            why = (f"the panel's grid {g['nx']}×{g['ny']}×{g['nz']} no longer "
                   f"matches the loaded φ field ({len(g['phi'])} points) — "
                   "re-run STL3d")
        else:
            why = "" if grid_ok else "no STL3d φ field loaded (run the IB stage)"
        detail = (f"{g['nx']}×{g['ny']}×{g['nz']} structured φ from the IB stage"
                  if g else "Needs the IB (STL3d) stage to have produced φ.")
        opts.append({"kind": ss.KIND_GRID_ISO, "enabled": grid_ok, "reason": why,
                     "detail": detail + (
                         "  — a different grid from the CFD mesh, so values are "
                         "interpolated onto it." if grid_ok else "")})
        opts.append({"kind": ss.KIND_INTERFACE_CELLS, "enabled": grid_ok,
                     "reason": why,
                     "detail": "Exactly the points the Fit Δ heatmap measures "
                               "(solid cells touching fluid). Cell CENTRES, so "
                               "the curve is a staircase and is ordered by "
                               "nearest neighbour."})

        shapes = self.surface_analytic_shapes()
        opts.append({
            "kind": ss.KIND_ANALYTIC, "enabled": bool(shapes),
            "reason": "" if shapes else ("no closed CAD shape (circle / polygon / "
                                         "triangle / quad) in the active session"),
            "shapes": shapes,
            "detail": "The analytic solid itself — exact, no grid error." + (
                "  (★ = the shape this run's φ DLL was built from.)"
                if any(s.get("in_use") for s in shapes) else ""),
        })

        sessions = (self.cad_overlay_sessions()
                    if hasattr(self, "cad_overlay_sessions") else [])
        usable = [s for s in sessions if s[3]]
        opts.append({
            "kind": ss.KIND_CAD, "enabled": bool(usable),
            "reason": "" if usable else "no open CAD session carries geometry",
            "sessions": sessions,
            "detail": "The CAD outline as drawn / imported (resampled points when "
                      "the project has been saved).",
        })
        for o in opts:
            o.setdefault("label", ss.KIND_LABELS.get(o["kind"], o["kind"]))
        return opts

    # ------------------------------------------------------------------ #
    # Extraction (called only after the user commits)
    # ------------------------------------------------------------------ #
    def build_surface(self, spec, result=None) -> dict:
        """Extract the curves ``spec`` describes.

        Returns ``{"curves": [...], "error": str, "notes": [str]}``. Errors are
        returned rather than raised: the dialog stays open on a bad pick so the
        user can change one field, and every note (a staircase chain that jumped,
        a piece dropped for being too short) is surfaced instead of swallowed.
        """
        out: dict = {"curves": [], "error": "", "notes": []}
        try:
            curves = self._extract_surface_curves(spec, result, out)
        except Exception as e:                      # bad grid / unusable field
            # Allowed to fail: the message goes back to the caller, which shows it
            # in the dialog and in the canvas's surface status. The traceback is
            # debug-tier detail for HYBMESH_LOG_LEVEL=DEBUG.
            _log.debug("surface extraction failed for kind=%s", spec.kind,
                       exc_info=True)
            out["error"] = str(e)
            return out
        curves = [c for c in curves if len(c) >= 2]
        if not curves:
            out["error"] = out["error"] or (
                f"{ss.KIND_LABELS.get(spec.kind, spec.kind)} produced no curve "
                "— check the iso level / the selected shape.")
        out["curves"] = curves
        out["notes"] += [c.note for c in curves if c.note]
        return out

    def _extract_surface_curves(self, spec, result, out: dict) -> list:
        kind = spec.kind
        if kind == ss.KIND_MESH:
            if result is None:
                raise ValueError("no result loaded")
            return ss.mesh_boundary_curves(result)
        if kind == ss.KIND_FIELD_ISO:
            if result is None:
                raise ValueError("no result loaded")
            if spec.var not in result.scalar_variables():
                raise ValueError(
                    f"this result carries no {spec.var!r} variable — it has "
                    f"{', '.join(result.scalar_variables()) or 'none'}")
            vals = result.cell_to_node(spec.var)
            return ss.iso_curves(result.nodes, result.elements, vals, spec.level)
        if kind in (ss.KIND_GRID_ISO, ss.KIND_INTERFACE_CELLS):
            g = self.surface_stl3d_phi()
            if not g:
                raise ValueError("no STL3d φ field is loaded")
            if not g["match"]:
                raise ValueError(
                    f"grid {g['nx']}×{g['ny']}×{g['nz']} does not match the φ "
                    f"field ({len(g['phi'])} points)")
            if kind == ss.KIND_GRID_ISO:
                return ss.grid_iso_curves(g["pts"], g["phi"], g["nx"], g["ny"],
                                          g["nz"], spec.level, spec.grid_slice)
            from app.services.phi_quality import interface_points
            xy, vals = ss.grid_slice_xy(g["pts"], g["phi"], g["nx"], g["ny"],
                                        g["nz"], spec.grid_slice)
            # One k-layer only: the Fit Δ heatmap is 3D, but an arc length has to
            # live in a plane, and the immersed-solid case is quasi-2D by design.
            pts3 = np.column_stack([xy, np.zeros(len(xy))])
            ipts = interface_points(vals > spec.level, g["nx"], g["ny"], 1, pts3)
            out["notes"].append(
                f"{len(ipts)} interface cells in the plotted layer "
                f"(k={'middle' if spec.grid_slice < 0 else spec.grid_slice}).")
            return [ss.chain_points_nn(ipts)]
        if kind == ss.KIND_ANALYTIC:
            if not spec.shape:
                raise ValueError("no analytic shape selected")
            return [ss.analytic_curve(spec.shape)]
        if kind == ss.KIND_CAD:
            ids = set(spec.session_ids) if spec.session_ids else None
            return ss.cad_curves(self.cad_overlay_polylines(ids))
        raise ValueError(f"unknown surface source {kind!r}")
