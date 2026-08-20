"""Unit-aware behaviour for SolverConfigPanel: the Linf mode and the Re read-out.

Two things live here, and both exist because the unit error this guards against is
otherwise invisible.

``Linf`` is metres per grid unit, so it is not an independent input — it is the model
unit written in the solver's vocabulary. While "from model unit" is ticked the field is
read-only and follows the Mesh panel. Unticking it is the escape hatch a config written
before units existed needs: that config carries a hand-set ``Linf`` and no unit, and
silently replacing it with 1.0 would change the Reynolds number of a case that used to
run correctly.

The **reference Reynolds number** ``fs_UnitRe × Linf`` is shown live. This is the actual
defence: a mesh authored in millimetres and declared as metres produces a perfectly
normal-looking ``Linf`` of 1 and a perfectly normal-looking mesh, and the only visible
symptom is a Reynolds number 1000x off. Nobody reads that off two spin boxes by
multiplying in their head; everybody recognises it when it is written down.
"""
from __future__ import annotations


class SolverUnitsMixin:
    def _wire_unit_widgets(self):
        """Connect the Linf/Re widgets. Call once, after the sections are built."""
        self.linf_from_unit.toggled.connect(self._on_linf_mode_toggled)
        for w in (self.fs_unit_re, self.linf):
            w.valueChanged.connect(self._update_ref_reynolds)
        self._sync_linf_mode()

    # ── Linf mode ────────────────────────────────────────────────────────
    def _sync_linf_mode(self):
        """Make Linf read-only while it is derived, and refresh the read-out.

        Read-only rather than disabled: the value still has to be legible (it is the
        unit factor the solver will use), and a greyed-out box invites people to
        wonder whether it is even being applied.
        """
        derived = self.linf_from_unit.isChecked()
        self.linf.setReadOnly(derived)
        self.linf.setButtonSymbols(
            self.linf.ButtonSymbols.NoButtons if derived
            else self.linf.ButtonSymbols.UpDownArrows)
        self._update_ref_reynolds()

    def _on_linf_mode_toggled(self, _checked: bool):
        self._sync_linf_mode()
        # Re-deriving is the controller's job (it owns the model unit); asking for it
        # here would duplicate the source of truth.
        if hasattr(self, "solver_config_changed"):
            self.solver_config_changed.emit()

    # ── derived read-out ─────────────────────────────────────────────────
    def _update_ref_reynolds(self, *_a):
        """Show Re = fs_UnitRe × Linf, or why it cannot be computed.

        fs_UnitRe is per metre and Linf is metres per grid unit, so the product is
        dimensionless — which is the whole point: it is comparable against the
        textbook value for the case regardless of what unit the grid is in.
        """
        lbl = getattr(self, "ref_reynolds", None)
        if lbl is None:
            return
        unit_re = self.fs_unit_re.value()
        linf = self.linf.value()
        if unit_re <= 0 or linf <= 0:
            # Not an error worth colouring red — an unfilled form is the normal
            # starting state, and a fresh panel screaming at the user is noise.
            lbl.setText("—")
            lbl.setToolTip("Needs a positive Unit Re and L_inf.")
            return
        re = unit_re * linf
        lbl.setText(f"{re:.4g}")
        lbl.setToolTip(
            f"Re = fs_UnitRe x Linf = {unit_re:.6g} /m x {linf:.6g} m = {re:.6g}\n"
            f"Sanity-check this against the case you intend to run: a wrong model "
            f"unit shifts it by a factor of 1000 while leaving the mesh looking "
            f"perfectly correct.")
