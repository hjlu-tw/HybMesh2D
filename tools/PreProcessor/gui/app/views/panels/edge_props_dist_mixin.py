from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel, QComboBox, QSpinBox
from app.utils import (COMBO_STYLE, SPIN_STYLE, align_form_labels, block_signals,
                       help_label)
from app.models.distribution_spec import DistributionSpec
from app.views.clean_double_spin_box import CleanDoubleSpinBox, SciDoubleSpinBox


class EdgePropsDistMixin:
    def _setup_param_forms(self):
        spin_style = SPIN_STYLE
        combo_style = COMBO_STYLE
        def mk_spin(lo=2, hi=100000, val=50):
            s = QSpinBox()
            s.setRange(lo, hi)
            s.setValue(val)
            s.setStyleSheet(spin_style)
            return s

        def mk_dspin(lo=0.0, hi=1e4, val=1.0, dec=5, step=0.1):
            s = CleanDoubleSpinBox()
            s.setRange(lo, hi)
            s.setValue(val)
            s.setDecimals(dec)
            s.setSingleStep(step)
            s.setStyleSheet(spin_style)
            return s

        def mk_sci_spin(tip: str):
            """A physical-length field (see the SciDoubleSpinBox rule in
            CLAUDE.md): scientific notation, no floor. 0 means "not set", which is
            how the resampler distinguishes a one-sided from a two-sided spec."""
            s = SciDoubleSpinBox()
            s.setRange(0.0, 1e6)
            s.setSpecialValueText("unset")     # 0 reads as "unset", not "0 metres"
            s.setStyleSheet(spin_style)
            s.setToolTip(tip)
            return s

        def _rows(form: QFormLayout, **widgets) -> dict:
            """Map name -> (label, field) so a mode toggle can hide whole rows.

            Hiding the field alone leaves its label behind, which is what made the
            earlier uniform toggle need a hand-kept ``_uniform_spacing_label``.
            """
            return {name: (form.labelForField(w), w) for name, w in widgets.items()}

        # 0 — Uniform
        uw = QWidget()
        ul = QFormLayout(uw)
        self.uniform_type_combo = QComboBox()
        self.uniform_type_combo.addItems(["By Node Count", "By Spacing"])
        self.uniform_type_combo.setStyleSheet(combo_style)
        self.uniform_type_combo.setToolTip("Choose between specifying node count or spacing distance")
        ul.addRow(help_label("Mode:", "Choose between specifying node count or spacing distance"), self.uniform_type_combo)
        self.uniform_n = mk_spin(2, 100000, 50)
        self.uniform_n.setToolTip("Number of evenly-spaced nodes along this edge")
        ul.addRow(help_label("Node Count:", "Number of evenly-spaced nodes along this edge"), self.uniform_n)
        # A physical length, so it needs the same scientific-notation treatment as
        # the mesh sizes: a mm-scale edge resampled at Δs=2e-5 was unreachable
        # behind the old 1e-6 floor / 5-decimal display.
        self.uniform_spacing = SciDoubleSpinBox()
        self.uniform_spacing.setRange(0.0, 1e6)
        self.uniform_spacing.setValue(0.1)
        self.uniform_spacing.setStyleSheet(spin_style)
        self.uniform_spacing.setToolTip(
            "Fixed distance between adjacent nodes. "
            "Accepts scientific notation (e.g. 2e-5).")
        self.uniform_spacing.setVisible(False)
        ul.addRow(help_label("Spacing (Δs):", "Fixed distance between adjacent nodes"), self.uniform_spacing)
        self._uniform_spacing_label = ul.labelForField(self.uniform_spacing)
        if self._uniform_spacing_label:
            self._uniform_spacing_label.setVisible(False)
        self.uniform_type_combo.currentTextChanged.connect(
            lambda t: self._toggle_uniform_mode(t == "By Spacing"))
        self.param_stack.addWidget(uw)

        # 1 — Tanh
        tw = QWidget()
        tl = QFormLayout(tw)
        self.tanh_n = mk_spin()
        self.tanh_n.setToolTip("Number of nodes with hyperbolic tangent clustering at both ends")
        self.tanh_intensity = mk_dspin(0.1, 10.0, 2.0, 2, 0.1)
        self.tanh_intensity.setToolTip("Clustering intensity (higher = more nodes at endpoints)")
        # End-spacing mode. A y+-driven end cell size could previously only be
        # approximated by guessing an intensity. The resampler now SOLVES the
        # clustering for a requested end spacing (Spacing::solveTanhDelta); the old
        # log(L/min(s0,s1))*0.5 heuristic it replaced was ~40x off and needed both
        # ends set to do anything at all.
        self.tanh_type_combo = QComboBox()
        self.tanh_type_combo.addItems(["By Intensity", "By End Spacing"])
        self.tanh_type_combo.setStyleSheet(combo_style)
        self.tanh_type_combo.setToolTip(
            "Choose between an abstract clustering intensity and an explicit "
            "end-node spacing")
        # ONE field, not two: tanh clustering is symmetric, so it physically
        # cannot produce different first/last spacings. Offering two would be a
        # promise the distribution cannot keep.
        self.tanh_spacing_ends = mk_sci_spin(
            "Node spacing at BOTH ends of the edge (tanh clustering is symmetric)")
        tl.addRow(help_label("Mode:", "Intensity or explicit end spacings"),
                  self.tanh_type_combo)
        tl.addRow(help_label("Node Count:", "Number of nodes with hyperbolic tangent clustering at both ends"), self.tanh_n)
        tl.addRow(help_label("Intensity:", "Clustering intensity (higher = more nodes at endpoints)"), self.tanh_intensity)
        tl.addRow(help_label("Δs at ends:",
                             "Node spacing at BOTH ends (tanh is symmetric)"),
                  self.tanh_spacing_ends)
        _t_hint = QLabel("tanh is symmetric → one spacing governs both ends")
        _t_hint.setStyleSheet("color:#556688; font-size:10px;")
        tl.addRow("", _t_hint)
        self._tanh_rows = _rows(tl, intensity=self.tanh_intensity,
                                ends=self.tanh_spacing_ends)
        self.tanh_type_combo.currentTextChanged.connect(
            lambda t: self._toggle_tanh_mode(t == "By End Spacing"))
        self._toggle_tanh_mode(False)
        self.param_stack.addWidget(tw)

        # 2 — Cosine
        cw = QWidget()
        cfl = QFormLayout(cw)
        self.cosine_n = mk_spin()
        self.cosine_n.setToolTip("Number of nodes with cosine-based clustering (denser at both ends)")
        cfl.addRow(help_label("Node Count:", "Number of nodes with cosine-based clustering (denser at both ends)"), self.cosine_n)
        self.param_stack.addWidget(cw)

        # 3 — Curvature
        kw = QWidget()
        kl = QFormLayout(kw)
        self.curv_n = mk_spin()
        self.curv_n.setToolTip("Number of nodes distributed based on local curvature")
        self.curv_sens = mk_dspin(0.1, 10.0, 1.5, 2, 0.1)
        self.curv_sens.setToolTip("Sensitivity to curvature (higher = more nodes in curved regions)")
        kl.addRow(help_label("Node Count:", "Number of nodes distributed based on local curvature"), self.curv_n)
        kl.addRow(help_label("Sensitivity:", "Sensitivity to curvature (higher = more nodes in curved regions)"), self.curv_sens)
        self.param_stack.addWidget(kw)

        # 4 — Geometric
        gw = QWidget()
        gl2 = QFormLayout(gw)
        self.geo_n = mk_spin()
        self.geo_n.setToolTip("Number of nodes with geometric (exponential) spacing")
        self.geo_ratio = mk_dspin(1.0, 5.0, 1.2, 3, 0.05)
        self.geo_ratio.setToolTip("Growth ratio at the start of the edge (>1 means expanding)")
        self.geo_ratio_end = mk_dspin(1.0, 5.0, 1.0, 3, 0.05)
        self.geo_ratio_end.setToolTip("Growth ratio at the end of the edge (1.0 = uniform at end)")
        # Same reasoning as tanh: the resampler accepts spacing_start /
        # spacing_end for geometric (one-sided from either end, or a two-sided
        # blend) and derives the growth from them. That is how a boundary-layer-
        # like distribution is actually specified, so it needs to be reachable.
        self.geo_type_combo = QComboBox()
        self.geo_type_combo.addItems(["By Growth Ratio", "By End Spacing"])
        self.geo_type_combo.setStyleSheet(combo_style)
        self.geo_type_combo.setToolTip(
            "Choose between growth ratios and explicit first/last node spacings")
        self.geo_spacing_start = mk_sci_spin(
            "First-node spacing at the START of the edge (0 = not set)")
        self.geo_spacing_end = mk_sci_spin(
            "Last-node spacing at the END of the edge (0 = not set)")
        gl2.addRow(help_label("Mode:", "Growth ratios or explicit end spacings"),
                   self.geo_type_combo)
        gl2.addRow(help_label("Node Count:", "Number of nodes with geometric (exponential) spacing"), self.geo_n)
        gl2.addRow(help_label("Growth Ratio (start):", "Growth ratio at the start of the edge (>1 means expanding)"), self.geo_ratio)
        gl2.addRow(help_label("Growth Ratio (end):", "Growth ratio at the end of the edge (1.0 = uniform at end)"), self.geo_ratio_end)
        gl2.addRow(help_label("Δs start:", "First-node spacing at the START of the edge (0 = not set)"),
                   self.geo_spacing_start)
        gl2.addRow(help_label("Δs end:", "Last-node spacing at the END of the edge (0 = not set)"),
                   self.geo_spacing_end)
        _hint = QLabel("Growth ratio = 1.0 → uniform at end;  Δs = 0 → that end unset")
        _hint.setStyleSheet("color:#556688; font-size:10px;")
        gl2.addRow("", _hint)
        self._geo_rows = _rows(gl2, ratio=self.geo_ratio,
                               ratio_end=self.geo_ratio_end,
                               s0=self.geo_spacing_start,
                               s1=self.geo_spacing_end)
        self.geo_type_combo.currentTextChanged.connect(
            lambda t: self._toggle_geo_mode(t == "By End Spacing"))
        self._toggle_geo_mode(False)
        self.param_stack.addWidget(gw)

        # Align form layouts
        for layout in [ul, tl, cfl, kl, gl2]:
            align_form_labels(layout)

    # ── The distribution form's interface ────────────────────────────────
    # Controllers used to read and write these thirteen widgets by name. They
    # now say what they mean and the form answers in DistributionSpec, which is
    # Qt-free and carries the resampler contract (see models/distribution_spec).
    #
    # The mode combos already drive their own toggles at build time (see the
    # currentTextChanged connections above), so only POPULATION has to apply a
    # toggle by hand — with signals blocked, or filling the form would read back
    # as a user edit and record an undo step per field.

    _DIST_VALUE_WIDGETS = (
        "uniform_n", "uniform_spacing", "tanh_n", "tanh_intensity",
        "tanh_spacing_ends", "cosine_n", "curv_n", "curv_sens", "geo_n",
        "geo_ratio", "geo_ratio_end", "geo_spacing_start", "geo_spacing_end",
    )
    _DIST_MODE_COMBOS = ("uniform_type_combo", "tanh_type_combo", "geo_type_combo")

    def _wire_distribution_edits(self):
        """Collapse every distribution widget into ONE `distribution_edited`.

        The controller used to list ten spin boxes and a combo at the wiring
        site, so a field added here silently did nothing until that list was
        edited too. Introspecting our own widgets means the form cannot grow a
        field the signal misses.
        """
        for name in self._DIST_VALUE_WIDGETS:
            getattr(self, name).valueChanged.connect(
                lambda *_: self.distribution_edited.emit())
        for name in self._DIST_MODE_COMBOS:
            getattr(self, name).currentTextChanged.connect(
                lambda *_: self.distribution_edited.emit())

    #: Distribution fields holding a PHYSICAL LENGTH, so they carry the model's
    #: unit as a suffix (see the SciDoubleSpinBox / units rules in CLAUDE.md).
    #: Growth ratios, intensities and node counts are dimensionless and must not.
    _LENGTH_FIELDS = ("uniform_spacing", "tanh_spacing_ends",
                      "geo_spacing_start", "geo_spacing_end")

    def set_length_suffix(self, symbol: str):
        for name in self._LENGTH_FIELDS:
            getattr(self, name).setSuffix(f" {symbol}")

    def distribution_spec(self, strategy: str) -> DistributionSpec:
        """What the form currently says, for `strategy`."""
        return DistributionSpec(
            strategy=strategy,
            n_points={
                "uniform": self.uniform_n, "tanh": self.tanh_n,
                "cosine": self.cosine_n, "curvature": self.curv_n,
                "geometric": self.geo_n,
            }.get(strategy, self.uniform_n).value(),
            by_spacing=(
                self.uniform_type_combo.currentText() == "By Spacing"
                if strategy == "uniform" else
                self.tanh_type_combo.currentText() == "By End Spacing"
                if strategy == "tanh" else
                self.geo_type_combo.currentText() == "By End Spacing"
                if strategy == "geometric" else False),
            spacing=self.uniform_spacing.value(),
            intensity=self.tanh_intensity.value(),
            spacing_ends=self.tanh_spacing_ends.value(),
            sensitivity=self.curv_sens.value(),
            ratio=self.geo_ratio.value(),
            ratio_end=self.geo_ratio_end.value(),
            spacing_start=self.geo_spacing_start.value(),
            spacing_end=self.geo_spacing_end.value(),
        )

    def show_distribution_spec(self, spec: DistributionSpec):
        """Put `spec` on the form without it reading back as a user edit."""
        widgets = [getattr(self, n) for n in self._DIST_VALUE_WIDGETS]
        combos = [getattr(self, n) for n in self._DIST_MODE_COMBOS]
        with block_signals(*widgets, *combos):
            if spec.strategy == "uniform":
                self.uniform_type_combo.setCurrentText(
                    "By Spacing" if spec.by_spacing else "By Node Count")
                # Only the ACTIVE mode's field is written. The other one holds no
                # value in `parameters` (mode is key presence, so exactly one is
                # stored), and writing the spec's default into it would silently
                # reset whatever the user last typed in the hidden field.
                if spec.by_spacing:
                    self.uniform_spacing.setValue(spec.spacing)
                else:
                    self.uniform_n.setValue(spec.n_points)
                self._toggle_uniform_mode(spec.by_spacing)
            elif spec.strategy == "tanh":
                self.tanh_type_combo.setCurrentText(
                    "By End Spacing" if spec.by_spacing else "By Intensity")
                self.tanh_n.setValue(spec.n_points)
                self.tanh_intensity.setValue(spec.intensity)
                self.tanh_spacing_ends.setValue(spec.spacing_ends)
                self._toggle_tanh_mode(spec.by_spacing)
            elif spec.strategy == "cosine":
                self.cosine_n.setValue(spec.n_points)
            elif spec.strategy == "curvature":
                self.curv_n.setValue(spec.n_points)
                self.curv_sens.setValue(spec.sensitivity)
            elif spec.strategy == "geometric":
                self.geo_type_combo.setCurrentText(
                    "By End Spacing" if spec.by_spacing else "By Growth Ratio")
                self.geo_n.setValue(spec.n_points)
                self.geo_ratio.setValue(spec.ratio)
                self.geo_ratio_end.setValue(spec.ratio_end)
                self.geo_spacing_start.setValue(spec.spacing_start)
                self.geo_spacing_end.setValue(spec.spacing_end)
                self._toggle_geo_mode(spec.by_spacing)

    def switch_param_form(self, strategy_name: str):
        m = {"uniform": 0, "tanh": 1, "cosine": 2, "curvature": 3, "geometric": 4}
        if strategy_name in m:
            self.param_stack.setCurrentIndex(m[strategy_name])

    def _toggle_uniform_mode(self, is_spacing: bool):
        self.uniform_n.setVisible(not is_spacing)
        lbl = self.uniform_n.parentWidget().layout().labelForField(self.uniform_n)
        if lbl:
            lbl.setVisible(not is_spacing)
        self.uniform_spacing.setVisible(is_spacing)
        if self._uniform_spacing_label:
            self._uniform_spacing_label.setVisible(is_spacing)

    @staticmethod
    def _set_rows_visible(rows: dict, names, visible: bool):
        """Show/hide whole label+field rows by name (see the ``_rows`` helper)."""
        for name in names:
            lbl, field = rows.get(name, (None, None))
            if field is not None:
                field.setVisible(visible)
            if lbl is not None:
                lbl.setVisible(visible)

    def _toggle_tanh_mode(self, by_spacing: bool):
        """Intensity <-> explicit end spacings. Node count applies to both."""
        self._set_rows_visible(self._tanh_rows, ("intensity",), not by_spacing)
        self._set_rows_visible(self._tanh_rows, ("ends",), by_spacing)

    def _toggle_geo_mode(self, by_spacing: bool):
        """Growth ratios <-> explicit end spacings. Node count applies to both."""
        self._set_rows_visible(self._geo_rows, ("ratio", "ratio_end"), not by_spacing)
        self._set_rows_visible(self._geo_rows, ("s0", "s1"), by_spacing)

    def _on_curve_mode_toggled(self, is_parametric: bool):
        self._param_widget.setVisible(is_parametric)
        self._explicit_widget.setVisible(not is_parametric)
