"""The mesh config's PRE-FLIGHT: what the configuration says about itself.

Split off ``mesh_config.py`` when that file ran out of room for the work coming
to it (#159), along the seam the class already had: the dataclass DECLARES the
parameters, and these four methods JUDGE them. Nothing moved but the text — the
methods are still reached as ``MeshConfig.validate(...)`` and friends, through
the mixin below, so every caller is untouched. The same seam, and the same
reason, as ``mesh_config_geoms.py::GeomListMixin`` one file over.

**``validate()`` stays PURE** — a function of the config and nothing else. "Is
this geometry on disk?" is ``geom_files_not_on_disk()``, over in the geometry
mixin, because a question that asks the filesystem gives a different answer from
a different working directory and the caller must be able to tell the two kinds
of refusal apart.
"""
from __future__ import annotations

import os

__all__ = ["ConfigValidationMixin"]


class ConfigValidationMixin:
    """The pre-flight checks :class:`MeshConfig` answers about itself.

    Mixed into the dataclass rather than written as free functions taking a
    config: ``cfg.validate(...)`` is the call every host already makes (the GUI
    mesh controller, the headless pipeline runner), and a prefactor that
    re-pointed those would be changing behaviour's neighbourhood to save a file.
    """

    def validate(self, geom_bbox: tuple | None = None,
                 domain_bbox: tuple | None = None) -> tuple[list[str], list[str]]:
        """Pre-flight parameter sanity check, returning (errors, warnings).

        Errors are conditions that would make the backend crash or produce
        garbage (invalid domain, non-positive sizes, shrinking BL); the caller
        must block the run on any error. Warnings are advisory (no BL grown,
        BL stack likely to overrun the domain, geometry outside the domain box)
        and let the run proceed. Catching these here — rather than after a
        cryptic C++ crash — is what an industrial pre-processor does.

        ``geom_bbox`` is an optional (xmin, ymin, xmax, ymax) of the boundary
        geometry; when supplied, containment against the domain is checked.
        ``domain_bbox`` is the same for the custom outer-domain outline, and is
        what containment is checked against when one is defined.

        **Every domain check here is about the domain the run will actually
        use.** With a custom outline (`domain_file`) the rectangular box is
        hidden in the panel and overwritten from the geometry by the mesher, so
        validating it would block a perfectly valid run on numbers nobody set
        or can see. Config.hpp::validate() gates its own domain-span check on
        `domainFile.empty()` for exactly this reason — the two must agree.
        """
        errors: list[str] = []
        warnings: list[str] = []
        custom_domain = self.domain_file is not None

        # ── Domain ────────────────────────────────────────────────────────
        errors += self.domain_box_errors()
        if custom_domain and domain_bbox is None:
            warnings.append(
                "Custom domain outline could not be read; its extent-based "
                "checks (BL overrun, geometry containment) were skipped.")

        # What the advisory checks measure against: the outline's bounds, else the box.
        if custom_domain:
            dom = domain_bbox
        elif self.domain_x_min < self.domain_x_max and self.domain_y_min < self.domain_y_max:
            dom = (self.domain_x_min, self.domain_y_min,
                   self.domain_x_max, self.domain_y_max)
        else:
            dom = None

        # ── Mesh sizes ────────────────────────────────────────────────────
        if not self.auto_surface_size and self.surface_mesh_size <= 0:
            errors.append("Surface mesh size must be > 0 (or enable Auto).")
        if not self.auto_farfield_size and self.farfield_mesh_size <= 0:
            errors.append("Far-field mesh size must be > 0 (or enable Auto).")

        # ── Boundary layer (only meaningful when layers are grown) ────────
        # Checked PER FRONT: "the BL parameters" is not one set of numbers. Validating
        # the global ones whenever ANY front grows rejects a run over a parameter no
        # front reads; validating them only when the global count is positive lets a
        # geometry inherit a zero thickness unchecked. See bl_fronts().
        fronts = self.bl_fronts()
        if self.bl_layers < 0:
            errors.append("BL layer count cannot be negative.")
        elif not fronts:
            warnings.append("BL layers = 0: no boundary layer will be grown.")
        else:
            for labels, t0, growth in fronts:
                where = f" (used by {', '.join(labels)})" if labels else ""
                if t0 <= 0:
                    errors.append(f"BL initial thickness must be > 0{where}.")
                if growth < 1.0:
                    errors.append(
                        "BL growth rate must be >= 1.0 (a rate < 1 shrinks each "
                        f"layer){where}.")
            # Total BL stack thickness vs domain size (advisory).
            if (self.bl_layers > 0 and self.bl_initial_thickness > 0
                    and self.bl_growth_rate >= 1.0 and dom):
                g, n, t0 = self.bl_growth_rate, self.bl_layers, self.bl_initial_thickness
                total = (t0 * n if abs(g - 1.0) < 1e-9
                         else t0 * (g ** n - 1.0) / (g - 1.0))
                half = 0.5 * min(dom[2] - dom[0], dom[3] - dom[1])
                if half > 0 and total > half:
                    warnings.append(
                        f"Estimated BL stack thickness (~{total:.4g}) exceeds half "
                        f"the smaller domain extent (~{half:.4g}); the boundary "
                        "layer may overrun the domain.")

        # ── Transition ────────────────────────────────────────────────────
        if self.bl_transition_layers < 0:
            errors.append("Transition layer count cannot be negative.")
        if self.bl_transition_layers > 0 and self.bl_transition_growth_rate < 1.0:
            warnings.append(
                "Transition growth rate < 1.0 shrinks each transition layer.")

        # ── Geometry containment (advisory; needs both bboxes) ────────────
        if geom_bbox is not None and dom:
            gx0, gy0, gx1, gy1 = geom_bbox
            if (gx0 < dom[0] or gx1 > dom[2] or gy0 < dom[1] or gy1 > dom[3]):
                where = ("the custom domain outline's bounds "
                         f"([{dom[0]:.4g}, {dom[2]:.4g}] x [{dom[1]:.4g}, {dom[3]:.4g}])"
                         if custom_domain else "the domain box")
                warnings.append(
                    f"Geometry bounds ([{gx0:.4g}, {gx1:.4g}] x [{gy0:.4g}, "
                    f"{gy1:.4g}]) extend outside {where}; the mesh may be "
                    "clipped or the run may fail.")

        return errors, warnings

    def domain_box_errors(self) -> list[str]:
        """Errors in the rectangular domain box — empty when a custom outline is in use.

        The one definition, shared by :meth:`validate` and the Mesh-Generator preview.
        With a custom outline the box is hidden in the panel and overwritten from the
        geometry by the mesher, so checking it would block a valid run on numbers nobody
        set or can see; ``Config.hpp::validate()`` gates its own span check on
        ``domainFile.empty()`` for the same reason, and the three must agree.
        """
        if self.domain_file is not None:
            return []
        out = []
        if self.domain_x_min >= self.domain_x_max:
            out.append("Domain X Min must be strictly less than X Max.")
        if self.domain_y_min >= self.domain_y_max:
            out.append("Domain Y Min must be strictly less than Y Max.")
        return out

    @staticmethod
    def _as_float(value, fallback: float) -> float:
        """``value`` as a float, else ``fallback``. Override dicts come from a workspace
        or a hand-written config, so a value can be a string or junk; an unreadable
        override falls back to the global rather than failing the whole pre-flight."""
        if value is None:
            return fallback
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    def bl_fronts(self) -> list[tuple]:
        """``(labels, initial_thickness, growth_rate)`` per DISTINCT set of values grown.

        Empty when nothing grows a boundary layer at all. ``labels`` is the geometry
        names using those values, and is EMPTY when the global front uses them — so a
        message built from it points at the global BL fields exactly when those are the
        fields to fix, and names the geometries otherwise.

        A geometry's override is merged ON TOP of the global BLParams by the mesher
        (``Config.hpp::applyBLOverride``), so a geometry overriding only the layer count
        is still grown with the GLOBAL thickness and growth rate: hence resolving the
        effective values per front, and grouping by the values rather than the front.
        """
        global_key = ((self.bl_initial_thickness, self.bl_growth_rate)
                      if self.bl_layers > 0 else None)
        by_values: dict = {}          # (t0, growth) -> [geometry label, ...]
        if global_key is not None:
            by_values[global_key] = []
        for g in self.geom_files:
            p = self.bl_params_of(g)
            if not p:
                continue
            if self._as_float(p.get("BL_LAYERS"), float(self.bl_layers)) <= 0:
                continue
            key = (self._as_float(p.get("BL_INITIAL_THICKNESS"), self.bl_initial_thickness),
                   self._as_float(p.get("BL_GROWTH_RATE"), self.bl_growth_rate))
            labels = by_values.setdefault(key, [])
            # Sharing the global front's numbers => unlabelled: the global fields own them.
            if key != global_key:
                labels.append(os.path.basename(g))
        return [(tuple(labels), t0, growth)
                for (t0, growth), labels in by_values.items()]
