from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, QLabel, QCheckBox,
)

from app.views.collapsible import CollapsibleSection
from app.utils import make_button, SPIN_STYLE, align_form_labels
from app.views.clean_double_spin_box import CleanDoubleSpinBox


class ResultControlPanel(QWidget):
    """Results-mode sidebar: color-scale (clim) control + field statistics.

    The result canvas's toolbar already covers variable / zone / colormap /
    overlays; this panel adds the color range (the one thing missing) and shows
    the current field's min/max/mean so a "single colour" plot is easy to
    diagnose (flat field vs. a range squashed by outliers).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #121422; color: #a0a8c0;")
        self._canvas = None
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # ── Color scale ────────────────────────────────────────────────────
        sec = CollapsibleSection("Color Scale", start_collapsed=False)
        root.addWidget(sec)

        self.auto_cb = QCheckBox("Auto (fit to data range)")
        self.auto_cb.setChecked(True)
        self.auto_cb.setStyleSheet("color:#a0a8c0;")
        sec.add_widget(self.auto_cb)

        form = QFormLayout()
        self.vmin = CleanDoubleSpinBox()
        self.vmax = CleanDoubleSpinBox()
        for s in (self.vmin, self.vmax):
            s.setRange(-1e12, 1e12)
            s.setDecimals(6)
            s.setStyleSheet(SPIN_STYLE)
            s.setEnabled(False)
        form.addRow("Min:", self.vmin)
        form.addRow("Max:", self.vmax)
        align_form_labels(form, 60)
        sec.add_layout(form)

        btns = QHBoxLayout()
        btns.setSpacing(4)
        self.apply_btn = make_button("Apply", "#1e2a38")
        self.reset_btn = make_button("Reset to data", "#1a2a3a")
        self.apply_btn.setEnabled(False)
        btns.addWidget(self.apply_btn)
        btns.addWidget(self.reset_btn)
        sec.add_layout(btns)

        # ── Field info ─────────────────────────────────────────────────────
        info = CollapsibleSection("Field Info", start_collapsed=False)
        root.addWidget(info)
        self.lbl_var = self._info_row(info, "Variable:")
        self.lbl_min = self._info_row(info, "Data min:")
        self.lbl_max = self._info_row(info, "Data max:")
        self.lbl_mean = self._info_row(info, "Mean:")

        root.addStretch()

        self.auto_cb.toggled.connect(self._on_auto_toggled)
        self.apply_btn.clicked.connect(self._on_apply)
        self.reset_btn.clicked.connect(self._on_reset)

    def _info_row(self, sec: CollapsibleSection, label: str) -> QLabel:
        row = QHBoxLayout()
        row.setSpacing(6)
        k = QLabel(label)
        k.setStyleSheet("color:#7a82a0;")
        k.setFixedWidth(80)
        v = QLabel("—")
        v.setStyleSheet("color:#dde2ff;")
        row.addWidget(k)
        row.addWidget(v, 1)
        sec.add_layout(row)
        return v

    # ------------------------------------------------------------------ #
    def bind(self, canvas):
        """Connect to the result canvas (called by the controller)."""
        self._canvas = canvas
        canvas.result_rendered.connect(self._on_rendered)

    def _on_auto_toggled(self, checked: bool):
        self.vmin.setEnabled(not checked)
        self.vmax.setEnabled(not checked)
        self.apply_btn.setEnabled(not checked)
        if self._canvas is not None and checked:
            self._canvas.set_clim_auto(True)

    def _on_apply(self):
        if self._canvas is not None:
            self._canvas.set_clim(self.vmin.value(), self.vmax.value())

    def _on_reset(self):
        # Reset the inputs to the current data range; re-enable auto.
        self.auto_cb.setChecked(True)

    def _on_rendered(self, info: dict):
        self.lbl_var.setText(str(info.get("var", "—")))
        self.lbl_min.setText(f"{info.get('dmin', 0.0):.6g}")
        self.lbl_max.setText(f"{info.get('dmax', 0.0):.6g}")
        self.lbl_mean.setText(f"{info.get('mean', 0.0):.6g}")
        # When auto, mirror the applied range into the (disabled) inputs so the
        # user can switch to manual starting from sensible values.
        if self.auto_cb.isChecked():
            self.vmin.blockSignals(True)
            self.vmax.blockSignals(True)
            self.vmin.setValue(info.get("vmin", 0.0))
            self.vmax.setValue(info.get("vmax", 1.0))
            self.vmin.blockSignals(False)
            self.vmax.blockSignals(False)
