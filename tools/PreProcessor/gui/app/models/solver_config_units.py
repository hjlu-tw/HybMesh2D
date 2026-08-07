"""Length-unit behaviour for :class:`SolverConfig`, split out to keep that file under
the GUI's 500-line limit.

These methods are what make the unit system a correctness feature rather than a label.
Per the UNICONES manual ``fs_UnitRe`` is per metre and ``Linf`` is metres per grid unit,
so ``Re = fs_UnitRe x Linf`` — meaning ``Linf`` is not an independent input at all, it is
the declared model unit expressed in the solver's vocabulary. See app/services/units.py.
"""
from __future__ import annotations


class SolverConfigUnitsMixin:
    """Unit derivation and consistency checks for SolverConfig."""

    # ------------------------------------------------------------------ #
    # Units (see app/services/units.py)
    # ------------------------------------------------------------------ #
    def set_length_unit(self, unit: str, custom_metres: float = 1.0,
                        adopt: bool = True) -> bool:
        """Declare the grid's length unit; returns True if ``linf`` changed.

        ``adopt=False`` records the unit without touching ``linf`` — used when the
        unit is being *read* from somewhere else (a workspace, a mesh config) and the
        solver's own hand-set value must win until the user says otherwise.
        """
        from app.services import units
        self.length_unit = units.parse(unit, self.length_unit)
        if self.length_unit == units.CUSTOM:
            try:
                m = float(custom_metres)
            except (TypeError, ValueError):
                m = 1.0
            self.length_unit_metres = m if m > 0 else 1.0
        if not (adopt and self.linf_from_unit):
            return False
        new_linf = units.linf_for(self.length_unit, self.length_unit_metres)
        changed = new_linf != self.linf
        self.linf = new_linf
        return changed

    def derived_linf(self) -> float:
        """What ``linf`` would be for the declared unit."""
        from app.services import units
        return units.linf_for(self.length_unit, self.length_unit_metres)

    def unit_check(self, model_unit: str = "", model_metres: float = 1.0) -> list:
        """Advisory messages about unit consistency. Never mutates anything.

        Three things can be wrong, and each is reported in the terms the user can
        act on rather than as "check your units":

        * ``linf`` disagrees with the declared unit (a legacy config, or a hand edit).
          The message names the unit ``linf`` actually corresponds to, because
          ``0.0254`` *is* a statement that the grid is in inches.
        * the solver's unit disagrees with the mesh/CAD stage's unit — the grid came
          from there, so the two must match.
        * ``linf <= 0``, which makes Re zero or negative.
        """
        from app.services import units
        out = []
        if not (self.linf > 0):
            out.append(f"Linf is {self.linf:g}; it is metres per grid unit and must be "
                       f"positive (Re = fs_UnitRe x Linf).")
            return out

        derived = self.derived_linf()
        if abs(self.linf - derived) > 1e-12 * max(1.0, derived):
            implied = units.unit_for_linf(self.linf)
            implied_txt = (f"a grid in {units.plural(implied)}"
                           if implied else f"1 grid unit = {self.linf:g} m")
            out.append(
                f"Linf = {self.linf:g} means {implied_txt}, but the declared unit is "
                f"{units.describe(self.length_unit, self.length_unit_metres)}. "
                f"Re = fs_UnitRe x Linf, so one of the two is scaling the Reynolds "
                f"number by {max(self.linf, derived) / min(self.linf, derived):g}x.")

        if model_unit:
            mu = units.parse(model_unit, "")
            if mu and mu != self.length_unit:
                out.append(
                    f"The geometry/mesh stage is in {units.plural(mu)} but the "
                    f"solver stage says {units.plural(self.length_unit)}. The grid comes from "
                    f"that stage, so these must agree.")
            elif mu == units.CUSTOM and abs(
                    float(model_metres) - self.length_unit_metres) > 0:
                out.append(
                    f"Both stages use a custom unit but with different factors "
                    f"({model_metres:g} m vs {self.length_unit_metres:g} m).")
        return out
