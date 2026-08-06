from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel, QComboBox, QSpinBox
from app.utils import COMBO_STYLE, SPIN_STYLE, align_form_labels, help_label
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
        tl.addRow(help_label("Node Count:", "Number of nodes with hyperbolic tangent clustering at both ends"), self.tanh_n)
        tl.addRow(help_label("Intensity:", "Clustering intensity (higher = more nodes at endpoints)"), self.tanh_intensity)
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
        gl2.addRow(help_label("Node Count:", "Number of nodes with geometric (exponential) spacing"), self.geo_n)
        gl2.addRow(help_label("Growth Ratio (start):", "Growth ratio at the start of the edge (>1 means expanding)"), self.geo_ratio)
        gl2.addRow(help_label("Growth Ratio (end):", "Growth ratio at the end of the edge (1.0 = uniform at end)"), self.geo_ratio_end)
        _hint = QLabel("Growth ratio = 1.0 → uniform at end")
        _hint.setStyleSheet("color:#556688; font-size:10px;")
        gl2.addRow("", _hint)
        self.param_stack.addWidget(gw)

        # Align form layouts
        for layout in [ul, tl, cfl, kl, gl2]:
            align_form_labels(layout)

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

    def _on_curve_mode_toggled(self, is_parametric: bool):
        self._param_widget.setVisible(is_parametric)
        self._explicit_widget.setVisible(not is_parametric)
