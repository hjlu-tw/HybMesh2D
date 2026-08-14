"""Propagates the model length unit across the stages, and checks it for sense.

The unit is declared once, on the Mesh panel, and three other places need it:

* the CAD sidebar's spacing fields and the canvas grid-snap step — lengths in the
  same model unit, shown in the stage where the geometry is drawn;
* the Solver stage, where the unit stops being cosmetic: ``Linf`` is metres per grid
  unit and ``Re = fs_UnitRe × Linf``;
* each CAD session's ``ProjectModel``, so an exported geometry config records what
  its coordinates mean instead of leaving the next reader to guess.

**Nothing here rescales a number the user typed.** Changing the unit relabels the
fields and updates ``Linf`` — that is all. ``Linf`` is the one exception because it is
not an independent quantity: it *is* the unit, written in the solver's vocabulary, so
leaving it stale would be the bug rather than a conservative choice. Converting
coordinates is a separate, explicit action (import conversion / Transform ▸ Scale).
"""
from __future__ import annotations

from app.services import units
from app.services.logging_setup import get_logger

_log = get_logger(__name__)

class UnitsControllerMixin:
    # ── reading the model unit ───────────────────────────────────────────
    def model_length_unit(self) -> tuple:
        """``(code, metres_per_unit, custom_name)`` for the project."""
        cfg = getattr(self, "global_mesh_config", None)
        if cfg is None:
            return (units.DEFAULT_UNIT, 1.0, "")
        code = units.parse(getattr(cfg, "length_unit", units.DEFAULT_UNIT),
                           units.DEFAULT_UNIT)
        metres = units.metres_per_unit(code, getattr(cfg, "length_unit_metres", 1.0))
        return (code, metres, str(getattr(cfg, "length_unit_name", "") or ""))

    def length_unit_symbol(self) -> str:
        code, _m, nm = self.model_length_unit()
        return units.symbol(code, nm)

    # ── propagation ──────────────────────────────────────────────────────
    def sync_length_unit(self) -> None:
        """Push the model unit out to every stage that shows or consumes a length.

        Idempotent and safe to call on any config change: it only ever sets suffixes
        and derived values, so a redundant call costs nothing and a missed one is the
        failure mode worth guarding against.
        """
        code, metres, nm = self.model_length_unit()
        sym = units.symbol(code, nm)
        mw = getattr(self, "main_window", None)

        # CAD sidebar spacings + the canvas grid-snap step.
        if mw is not None:
            sb = getattr(mw, "sidebar_view", None)
            if sb is not None:
                sb.set_length_suffix(sym)
            snap = getattr(mw, "grid_snap_step", None)
            if snap is not None and hasattr(snap, "setSuffix"):
                snap.setSuffix(f" {sym}")

        # Every CAD session records the unit its coordinates are in. They all match
        # the model unit here by construction: an import in a different unit is
        # converted at import time, so a session never sits in a foreign unit.
        for session in getattr(self, "sessions", []) or []:
            project = getattr(session, "project_model", None)
            if project is not None:
                project.length_unit = code
                project.length_unit_metres = (
                    metres if code == units.CUSTOM else 1.0)
                project.length_unit_name = nm

        self._sync_solver_linf(code, metres, nm)

    def _sync_solver_linf(self, code: str, metres: float, nm: str) -> None:
        """Keep the solver's Linf equal to metres-per-unit, when derived.

        A config that predates units has ``linf_from_unit`` False and is left alone —
        its hand-set Linf is a real physical setting, and overwriting it would change
        the Reynolds number of a case that used to run correctly. The discrepancy is
        reported by :meth:`length_unit_warnings` instead.
        """
        scfg = getattr(self, "global_solver_config", None)
        if scfg is None or not hasattr(scfg, "set_length_unit"):
            return
        before = scfg.linf
        changed = scfg.set_length_unit(code, metres)
        if not scfg.linf_from_unit:
            return
        if changed:
            _log.info("Linf %g -> %g (model unit %s)", before, scfg.linf,
                      units.describe(code, metres, nm))

        # Update ONLY the Linf widget, not the whole panel. push_panel_config(panel,
        # scfg) would be the usual route, but it calls set_config and therefore
        # overwrites every other field with the model's value — silently discarding
        # anything the user has typed into the Solver panel since the last read (a
        # freshly entered Unit Re, for one). A derived field must not take its
        # neighbours with it.
        mw = getattr(self, "main_window", None)
        panel = getattr(mw, "solver_config_panel", None) if mw else None
        if panel is None or not hasattr(panel, "linf"):
            return
        # Still suppressed: this is a derived value following its source, and the
        # debounced snapshot recorder would otherwise log it as a user edit.
        if hasattr(self, "suppress_project_undo"):
            with self.suppress_project_undo():
                panel.linf.setValue(scfg.linf)
        else:
            panel.linf.setValue(scfg.linf)

    def on_linf_mode_changed(self, derived: bool) -> None:
        """The user ticked/unticked "Linf from model unit" on the Solver panel.

        Ticking re-derives immediately. Unticking deliberately leaves the current
        number in place: the point of unticking is to hold a value, so replacing it
        at that moment would defeat the control.
        """
        scfg = getattr(self, "global_solver_config", None)
        mw = getattr(self, "main_window", None)
        panel = getattr(mw, "solver_config_panel", None) if mw else None
        if scfg is None or panel is None:
            return
        scfg.linf_from_unit = bool(derived)
        if derived:
            self.sync_length_unit()

    # ── checks ───────────────────────────────────────────────────────────
    def length_unit_warnings(self, extent: float | None = None) -> list:
        """Advisory messages about the declared unit. Never mutates anything.

        Two independent checks:

        * the solver's own consistency (:meth:`SolverConfig.unit_check`) — exact, not
          heuristic: Linf either matches the declared unit or it does not;
        * a gross-size net (``units.implausible``). Its limits are real and stated in
          units.py: it catches an outright wrong unit (a model 1e7 m across), not the
          common near-miss, because 4500 mm read as 4500 m is a perfectly plausible
          size for a ship. The visible defence against that one is the reference
          Reynolds number shown on the Solver panel, not a threshold here.
        """
        code, metres, nm = self.model_length_unit()
        out = []

        scfg = getattr(self, "global_solver_config", None)
        if scfg is not None and hasattr(scfg, "unit_check"):
            out += scfg.unit_check(code, metres)

        if extent is None:
            extent = self._model_extent()
        if extent and units.implausible(extent, code, metres):
            phys = units.physical_extent(extent, code, metres)
            alts = units.plausible_alternatives(extent, code, metres)
            msg = (f"The model is {extent:.6g} {units.symbol(code, nm)} across, i.e. "
                   f"{phys:.6g} m in the declared unit "
                   f"({units.name(code, nm)}).")
            if alts:
                shown = ", ".join(
                    f"{units.symbol(a)} → {extent * units.metres_per_unit(a):.6g} m"
                    for a in alts[:3])
                msg += f" If the geometry were in another unit: {shown}."
            out.append(msg)
        return out

    def _model_extent(self) -> float:
        """Largest bounding-box span across every loaded geometry, in model units.

        Uses the span rather than the diagonal so the number quoted in a warning is
        one the user can read straight off the domain fields.
        """
        best = 0.0
        for session in getattr(self, "sessions", []) or []:
            # original_points: the geometry as loaded, before resampling — the
            # extent is a property of the model, not of the current node spacing.
            pts = getattr(session, "original_points", None)
            if pts is None or len(pts) < 2:
                continue
            try:
                import numpy as np
                a = np.asarray(pts, dtype=float)
                a = a[np.isfinite(a).all(axis=1)]
                if len(a) < 2:
                    continue
                # np.ptp(...), not a.ptp(): the ndarray method was removed in NumPy 2.
                span = float(max(np.ptp(a[:, 0]), np.ptp(a[:, 1])))
            except (ValueError, TypeError, IndexError):
                _log.debug("could not measure a session's extent", exc_info=True)
                continue
            best = max(best, span)
        return best
