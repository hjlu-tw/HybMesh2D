"""Domain-source / mesh-sizing / auto-hint helpers for MeshConfigPanel, split
out as a mixin (behaviour unchanged): domain-source visibility, the domain patch
pop-up, domain-extent + surface-spacing estimates, the auto far-field / surface
size hints, bidirectional-grading visibility and the BC indicator colours.
Expects the host to provide the matching widgets, geom_list_widget, _ROLE_DATA,
_domain_patch_dialog/_domain_patch_body, _sizing_form and domain_source_changed. Also holds the remaining widget-visibility
toggles (role / transition / convex) and the _mesh_sublabel section-label
factory relocated from the panel body."""
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox, QLabel
from app.utils import keep_on_top, BC_COLORS, DEFAULT_BC_COLOR


class MeshConfigSizingMixin:
    """Domain-source, sizing, auto-hint and BC-indicator helpers."""

    def _update_domain_source_visibility(self):
        """Show the rectangular box X/Y Min/Max only when Domain Source is
        'Rectangle box'; hide them for 'Custom geometry' (the domain then comes
        from a geometry with a Domain role).

        The domain-box edge patches only apply to the rectangle box, so the button
        that opens their pop-up (#4) is hidden for a custom domain (whose
        outer-boundary patches come from the outline's per-edge CAD names). The
        canvas is told to drop the rectangular box + its patch colours."""
        is_custom = self.domain_source_combo.currentIndex() == 1
        self._domain_box_widget.setVisible(not is_custom)
        self.domain_patch_btn.setVisible(not is_custom)
        if is_custom and self._domain_patch_dialog is not None:
            self._domain_patch_dialog.hide()   # not applicable to a custom domain

        # #6: the auto far-field size estimate depends on the domain source.
        self._update_auto_farfield_hint()

        self.domain_source_changed.emit(is_custom)

    def _open_domain_patch_dialog(self):
        """#4: pop-up to name the four rectangle-box edges (built lazily). The
        BCWidget edits commit live (read back by get_config at generate time), so
        the dialog only needs a Close button — no explicit Apply."""
        if self._domain_patch_dialog is None:
            dlg = QDialog(self)
            dlg.setWindowTitle("Domain boundary patches")
            dlg.setStyleSheet("background:#121422; color:#cdd6f4;")
            dlg.setMinimumWidth(360)
            lay = QVBoxLayout(dlg)
            lay.setContentsMargins(10, 10, 10, 10)
            lay.setSpacing(6)
            lay.addWidget(self._domain_patch_body)
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(dlg.reject)
            buttons.accepted.connect(dlg.accept)
            lay.addWidget(buttons)
            keep_on_top(dlg)   # #2: never sink below the main window
            self._domain_patch_dialog = dlg
        self._domain_patch_dialog.show()
        self._domain_patch_dialog.raise_()
        self._domain_patch_dialog.activateWindow()

    def _domain_extent(self) -> float | None:
        """Largest side of the computational domain, matching the C++ far-field
        heuristic (max(xMax-xMin, yMax-yMin)). Rectangle box → the box; custom →
        the bounds of the Domain-role geometry, else the union of all listed
        geometries. Returns None when it can't be determined."""
        is_custom = self.domain_source_combo.currentIndex() == 1
        if not is_custom:
            dx = self.domain_x_max.value() - self.domain_x_min.value()
            dy = self.domain_y_max.value() - self.domain_y_min.value()
            ext = max(dx, dy)
            return ext if ext > 0 else None
        # Custom domain: read geometry bounds (prefer a Domain-role geometry).
        try:
            import numpy as np
        except Exception:
            return None
        domain_paths, other_paths = [], []
        for row in range(self.geom_list_widget.count()):
            it = self.geom_list_widget.item(row)
            p = it.data(Qt.ItemDataRole.UserRole)
            if not p:
                continue
            rinfo = it.data(self._ROLE_DATA) or {}
            (domain_paths if rinfo.get("role") in ("farfield", "wall")
             else other_paths).append(p)
        xmin = ymin = float("inf")
        xmax = ymax = float("-inf")
        for p in (domain_paths or other_paths):
            try:
                pts = np.atleast_2d(np.loadtxt(p))
                if pts.size == 0 or pts.shape[1] < 2:
                    continue
                xmin = min(xmin, float(np.nanmin(pts[:, 0])))
                xmax = max(xmax, float(np.nanmax(pts[:, 0])))
                ymin = min(ymin, float(np.nanmin(pts[:, 1])))
                ymax = max(ymax, float(np.nanmax(pts[:, 1])))
            except Exception:
                continue
        if xmax > xmin or ymax > ymin:
            return max(xmax - xmin, ymax - ymin)
        return None

    def _update_auto_farfield_hint(self, *args):
        """#6: when Auto Far-field Sizing is on, show the far-field size the mesher
        will derive from the domain extent (5% of the larger side). The mesher also
        clamps it to be >= the last BL thickness, which isn't known in the GUI."""
        on = self.auto_farfield_size.isChecked()
        self.auto_farfield_hint.setVisible(on)
        if not on:
            return
        extent = self._domain_extent()
        if extent and extent > 0:
            size = extent * 0.05
            self.auto_farfield_hint.setText(
                f"Auto far-field ≈ {size:.4g}  (5% of domain extent {extent:.4g}; "
                "the mesher clamps it to ≥ the last BL thickness)")
        else:
            self.auto_farfield_hint.setText(
                "Auto far-field: computed from the domain extent at mesh time.")

    def _surface_spacing_estimate(self) -> float | None:
        """Average adjacent-point spacing across the boundary geometries — the
        value the mesher's Auto Surface size resolves to (it averages the BL-front
        edge lengths, which equal the surface point spacing). None if it can't be
        determined (no boundary geometry / unreadable files)."""
        try:
            import numpy as np
        except Exception:
            return None
        total = 0.0
        count = 0
        for row in range(self.geom_list_widget.count()):
            it = self.geom_list_widget.item(row)
            p = it.data(Qt.ItemDataRole.UserRole)
            if not p:
                continue
            role = (it.data(self._ROLE_DATA) or {}).get("role")
            if role in ("seed", "farfield"):   # not body-fitted surfaces
                continue
            try:
                pts = np.atleast_2d(np.loadtxt(p))
                if pts.shape[0] < 2 or pts.shape[1] < 2:
                    continue
                d = np.diff(pts[:, :2], axis=0)
                seg = np.sqrt((d * d).sum(axis=1))
                seg = seg[np.isfinite(seg) & (seg > 0)]   # skip NaN piece-breaks
                if seg.size:
                    total += float(seg.sum())
                    count += int(seg.size)
            except Exception:
                continue
        return (total / count) if count else None

    def _update_auto_surface_hint(self, *args):
        """#6: when Auto Surface Sizing is on, show the size the mesher will
        derive (average boundary point spacing)."""
        on = self.auto_surface_size.isChecked()
        self.auto_surface_hint.setVisible(on)
        if not on:
            return
        size = self._surface_spacing_estimate()
        if size and size > 0:
            self.auto_surface_hint.setText(
                f"Auto surface ≈ {size:.4g}  (average boundary point spacing)")
        else:
            self.auto_surface_hint.setText(
                "Auto surface: computed from the boundary point spacing at mesh time.")

    def _update_bidirectional_visibility(self, *args):
        """#7: show the Outer Growth Rate only when bidirectional grading is on."""
        on = self.farfield_bidirectional.isChecked()
        self.farfield_growth_rate_outer.setVisible(on)
        lbl = self._sizing_form.labelForField(self.farfield_growth_rate_outer)
        if lbl:
            lbl.setVisible(on)

    def _update_bc_indicators(self):
        """Parse boundary condition texts and update indicator backgrounds accordingly."""
        for edit, indicator in [
            (self.bc_xmin, self.bc_xmin_indicator),
            (self.bc_xmax, self.bc_xmax_indicator),
            (self.bc_ymin, self.bc_ymin_indicator),
            (self.bc_ymax, self.bc_ymax_indicator),
        ]:
            val = edit.text().strip().lower()
            color = BC_COLORS.get(val, DEFAULT_BC_COLOR)
            indicator.setStyleSheet(
                f"background-color: {color}; border-radius: 4px; border: 1px solid #333852;"
            )

    def _mark_bc_configured(self, *_):
        """#3: a domain BC was edited — flip the config out of its neutral
        untouched state so the BC Preview paints real colours. Ignored while
        set_config is bulk-populating the widgets (that isn't a user edit)."""
        if getattr(self, "_bl_updating", False):
            return
        self._bc_configured = True

    def _update_role_visibility(self):
        """Show seed params only for a selected seed geometry. Size and radius are
        independent, so radius stays editable even when the size is auto. (#2: the
        per-geometry Wall BC field was removed from this editor.)"""
        enabled = self.geom_role_combo.isEnabled()
        idx = self.geom_role_combo.currentIndex()
        is_seed = enabled and idx == 2
        for w in (self.seed_size, self.seed_radius, self.seed_mode):
            w.setVisible(is_seed)
            w.setEnabled(is_seed)
            lbl = self._role_form.labelForField(w)
            if lbl:
                lbl.setVisible(is_seed)

    def _mesh_sublabel(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#6b7390; font-size:10px; font-weight:bold;")
        return lbl

    def _update_transition_visibility(self):
        """Hide the manual Transition Layers count when Auto Transition computes it."""
        manual = self.bl_auto_transition_layers.currentIndex() == 0  # 0: OFF
        self.bl_transition_layers.setVisible(manual)
        lbl = self._trans_form.labelForField(self.bl_transition_layers)
        if lbl:
            lbl.setVisible(manual)

    def _update_convex_widgets_visibility(self):
        method_str = self.bl_convex_method.currentText()
        is_fan = "0: Fan" in method_str

        self.bl_fan_nodes.setVisible(is_fan)
        self.bl_auto_fan_nodes.setVisible(is_fan)
        self.bl_fan_angle_threshold.setVisible(is_fan)

        label_nodes = self.convex_form.labelForField(self.bl_fan_nodes)
        if label_nodes:
            label_nodes.setVisible(is_fan)

        label_threshold = self.convex_form.labelForField(self.bl_fan_angle_threshold)
        if label_threshold:
            label_threshold.setVisible(is_fan)
