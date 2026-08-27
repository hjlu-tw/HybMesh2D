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
from app.services.field_spec import by_attr, reads_in_mode
from app.services.mesh_modes import MESH_MODE_HYBRID
from app.utils import keep_on_top, BC_COLORS, DEFAULT_BC_COLOR
from app.views.panels.field_widgets import read_widget, set_spec_row_visible
from app.views.panels.mesh_bl_field_specs import PANEL_BL_SPECS
from app.views.panels.mesh_field_specs import MESH_SPECS


class MeshConfigSizingMixin:
    """Domain-source, sizing, auto-hint and BC-indicator helpers."""

    # ── mesh-mode applicability ─────────────────────────────────────────────
    # One rule over the table's own `modes=` declarations, rather than a list of
    # fields kept here. Every finer visibility helper below ANDs its answer with
    # `_mode_reads`, because those helpers are driven by signals that fire long
    # after this ran (a geometry selection, a checkbox) and would otherwise put a
    # row back that the active mode does not read.

    def _mesh_mode_value(self) -> int:
        """The mode the panel currently shows, read through its own spec.

        By VALUE, never by combo index: the mode numbers are the mesher's
        (include/MeshMode.hpp) and an index only equals a value while the list
        happens to be dense — the same rule `_bl_value` follows for the method
        combos, whose numbers are 0/2 and 1/2/5/6/7/8.
        """
        w = getattr(self, "mesh_mode", None)
        if w is None:
            return MESH_MODE_HYBRID
        spec = by_attr(MESH_SPECS).get("mesh_mode")
        try:
            return int(read_widget(w, spec, MESH_MODE_HYBRID))
        except (TypeError, ValueError):
            return MESH_MODE_HYBRID

    def _mode_reads(self, attr: str) -> bool:
        """Does the active mode read the field declared under ``attr``?

        Looks in BOTH of the panel's tables, so a caller does not have to know which
        one declares a field (no attribute is declared twice — check 1 of
        tests/test_field_spec_tables.py is what makes that safe). True for an attr
        with no spec or no declaration, so this can be ANDed into any existing
        visibility rule without that rule having to know which fields declare one.
        """
        spec = by_attr(MESH_SPECS, PANEL_BL_SPECS).get(attr)
        return spec is None or reads_in_mode(spec, self._mesh_mode_value())

    def _apply_mode_visibility(self, *_args):
        """Hide every row the active mode does not read; restore the rest.

        Restoring is handed straight back to the finer rules rather than being a
        `setVisible(True)`: the far-field outer growth rate is hidden by the
        bidirectional toggle and the seed size/radius by the geometry role, so
        showing them unconditionally would undo two other decisions.
        """
        mode = self._mesh_mode_value()
        # BOTH of the panel's tables. The 21 BL backing widgets sit in sections the
        # panel hides wholesale, so this changes nothing a user sees here — it is
        # the Edit-BL dialog that shows them, and it applies the same declaration
        # from the same table. Walking them anyway keeps "the panel's state matches
        # the declaration" a property that can be asked of the panel.
        for spec in (sp for tbl in (MESH_SPECS, PANEL_BL_SPECS) for sp in tbl):
            if spec.modes is None:
                continue                     # not this rule's business
            set_spec_row_visible(self, spec.attr, reads_in_mode(spec, mode))
        # A section whose every declared row is gone is hidden whole, so the mode
        # does not leave an empty header behind. Asked of the table, not listed.
        if getattr(self, "sec_meshing", None) is not None:
            self.sec_meshing.setVisible(
                any(reads_in_mode(sp, mode) for sp in MESH_SPECS
                    if sp.group == "meshing"))
        # Hand back to the finer rules for the rows this mode does keep.
        self._update_domain_source_visibility()
        self._update_bidirectional_visibility()
        self._update_auto_farfield_hint()
        self._update_role_visibility()
        self._update_transition_visibility()
        self._update_convex_widgets_visibility()

    def _update_domain_source_visibility(self):
        """Show the rectangular box X/Y Min/Max only when Domain Source is
        'Rectangle box'; hide them for 'Custom geometry' (the domain then comes
        from a geometry with a Domain role).

        The domain-box edge patches only apply to the rectangle box, so the button
        that opens their pop-up (#4) is hidden for a custom domain (whose
        outer-boundary patches come from the outline's per-edge CAD names). The
        canvas is told to drop the rectangular box + its patch colours."""
        is_custom = self.domain_source_combo.currentIndex() == 1
        # The four box rows are one container widget, so the mode gates the
        # container rather than each row (they are declared hybrid-only for the
        # mesher's warning, which is the same declaration read here).
        self._domain_box_widget.setVisible(not is_custom
                                           and self._mode_reads("domain_x_min"))
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
            keep_on_top(dlg)   # #2: above the app's main window, not other apps
            from app.utils import offset_popup
            offset_popup(dlg, self.window())   # #3: nudge off centre
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
        on = self.auto_farfield_size.isChecked() and self._mode_reads("auto_farfield_size")
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
        on = (self.farfield_bidirectional.isChecked()
              and self._mode_reads("farfield_growth_rate_outer"))
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
        # A refinement seed only ever drove the far-field size field, which the
        # multi-block path does not have — so the whole seed row block follows the
        # declaration on seed_size (seed_mode has no spec of its own to carry one).
        is_seed = enabled and idx == 2 and self._mode_reads("seed_size")
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

    def _bl_value(self, attr):
        """A BL backing widget's current VALUE, read through its spec.

        Read by value rather than by combo index or item text: the item text is a
        label the table owns and an index is only the value while the choice list
        happens to be dense. `"0: Fan" in currentText()` was both at once.
        """
        specs = by_attr(PANEL_BL_SPECS)
        return read_widget(getattr(self, attr), specs[attr])

    def _update_transition_visibility(self):
        """Hide the manual Transition Layers count when Auto Transition computes it."""
        manual = (self._bl_value("bl_auto_transition_layers") == 0  # 0: OFF
                  and self._mode_reads("bl_transition_layers"))
        self.bl_transition_layers.setVisible(manual)
        lbl = self._trans_form.labelForField(self.bl_transition_layers)
        if lbl:
            lbl.setVisible(manual)

    def _update_convex_widgets_visibility(self):
        is_fan = (self._bl_value("bl_convex_method") == 0       # 0: Fan
                  and self._mode_reads("bl_fan_nodes"))

        self.bl_fan_nodes.setVisible(is_fan)
        self.bl_auto_fan_nodes.setVisible(is_fan)
        self.bl_fan_angle_threshold.setVisible(is_fan)

        label_nodes = self.convex_form.labelForField(self.bl_fan_nodes)
        if label_nodes:
            label_nodes.setVisible(is_fan)

        label_threshold = self.convex_form.labelForField(self.bl_fan_angle_threshold)
        if label_threshold:
            label_threshold.setVisible(is_fan)
