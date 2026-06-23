from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QPushButton, QDialogButtonBox, QSpinBox, QRadioButton,
    QButtonGroup, QWidget
)
from app.utils import COMBO_STYLE, SPIN_STYLE
from app.views.clean_double_spin_box import CleanDoubleSpinBox
from app.views.polygon_editor import PolygonEditor

# Field layout and per-type defaults are owned by app.models.shape_spec so the
# dialog, the sidebar editor, and the curve controller never drift apart.
from app.models.shape_spec import DEFAULTS as _DEFAULTS, FIELDS as _FIELDS


class ShapeParamDialog(QDialog):
    """Compact modal numeric editor for one analytic-shape edge.

    Mirrors the sidebar fields so a shape can be entered / corrected precisely,
    complementing the interactive canvas drag-handles.  ``result_params``
    returns the edited ``{param_key: value}`` plus ``n_points``.
    """

    def __init__(self, seg, parent=None, changed_cb=None, confirm_text="Create Edge"):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Edge {seg.id}")
        self._confirm_text = confirm_text
        self.setStyleSheet("background:#121422; color:#cdd6f4;")
        self._curve_type = getattr(seg, "curve_type", "custom")
        self._spins: dict[str, CleanDoubleSpinBox] = {}
        self._poly_edit: PolygonEditor | None = None
        self._changed_cb = changed_cb

        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        title = QLabel(f"{self._curve_type.replace('_', ' ').title()}")
        title.setStyleSheet("font-weight:bold; color:#89b4fa;")
        lay.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(form.labelAlignment())
        p = dict(_DEFAULTS.get(self._curve_type, {}))
        p.update({k: v for k, v in seg.parameters.items()})

        if self._curve_type == "polygon":
            self._poly_edit = PolygonEditor(
                seg.parameters.get("vertices_str", "0,0; 1,0; 1,1; 0,1"))
            form.addRow(QLabel("Vertices:"), self._poly_edit)
        else:
            for key, label in _FIELDS.get(self._curve_type, []):
                spin = CleanDoubleSpinBox()
                spin.setRange(-1e6, 1e6)
                spin.setDecimals(4)
                spin.setStyleSheet(SPIN_STYLE)
                spin.setValue(float(p.get(key, 0.0)))
                self._spins[key] = spin
                form.addRow(QLabel(label + ":"), spin)

        # Node count (applied immediately on accept).
        self._node_spin = QSpinBox()
        self._node_spin.setRange(2, 100000)
        self._node_spin.setValue(int(seg.parameters.get("n_points", 50)))
        self._node_spin.setStyleSheet(SPIN_STYLE)
        form.addRow(QLabel("Node Count:"), self._node_spin)
        lay.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        ok_btn = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_btn.setText(self._confirm_text)
        ok_btn.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        # Live two-way binding: edits here drive the canvas preview / handles.
        for spin in self._spins.values():
            spin.valueChanged.connect(self._emit_changed)
        if self._poly_edit is not None:
            self._poly_edit.textChanged.connect(self._emit_changed)
        self._node_spin.valueChanged.connect(self._emit_changed)

    def _emit_changed(self, *args):
        if self._changed_cb is not None:
            params, n = self.result_params()
            self._changed_cb(params, n)

    def set_values(self, params: dict, n_points: int | None = None):
        """Silently push values into the fields (used when the canvas control
        points are dragged) without re-emitting the change signal."""
        widgets = list(self._spins.values()) + [self._node_spin]
        if self._poly_edit is not None:
            widgets.append(self._poly_edit)
        for w in widgets:
            w.blockSignals(True)
        try:
            if self._curve_type == "polygon" and self._poly_edit is not None:
                if "vertices_str" in params:
                    self._poly_edit.setText(params["vertices_str"])
            else:
                for key, spin in self._spins.items():
                    if key in params:
                        spin.setValue(float(params[key]))
            if n_points is not None:
                self._node_spin.setValue(int(n_points))
        finally:
            for w in widgets:
                w.blockSignals(False)

    def result_params(self) -> tuple[dict, int]:
        out: dict = {}
        if self._curve_type == "polygon" and self._poly_edit is not None:
            out["vertices_str"] = self._poly_edit.text()
        else:
            for key, spin in self._spins.items():
                out[key] = spin.value()
        return out, self._node_spin.value()


class FileEndpointDialog(QDialog):
    """Modeless editor for the two endpoints of an imported (discrete) edge.

    Lets the user move the segment's start/end points numerically; combined with
    the canvas drag-handles + snapping it is handy for closing gaps between
    imported pieces.  ``changed_cb(p0, p1)`` fires live on every edit."""

    def __init__(self, seg_id, p0, p1, changed_cb=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Edge {seg_id} (endpoints)")
        self.setStyleSheet("background:#121422; color:#cdd6f4;")
        self._changed_cb = changed_cb

        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        form = QFormLayout()

        def mk(v):
            s = CleanDoubleSpinBox()
            s.setRange(-1e6, 1e6)
            s.setDecimals(4)
            s.setStyleSheet(SPIN_STYLE)
            s.setValue(float(v))
            return s

        self._x0 = mk(p0[0]); self._y0 = mk(p0[1])
        self._x1 = mk(p1[0]); self._y1 = mk(p1[1])
        form.addRow(QLabel("Start X:"), self._x0)
        form.addRow(QLabel("Start Y:"), self._y0)
        form.addRow(QLabel("End X:"), self._x1)
        form.addRow(QLabel("End Y:"), self._y1)
        lay.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Apply")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        for s in (self._x0, self._y0, self._x1, self._y1):
            s.valueChanged.connect(self._emit_changed)

    def _emit_changed(self, *args):
        if self._changed_cb is not None:
            self._changed_cb((self._x0.value(), self._y0.value()),
                             (self._x1.value(), self._y1.value()))

    def set_points(self, p0, p1):
        for s, v in ((self._x0, p0[0]), (self._y0, p0[1]),
                     (self._x1, p1[0]), (self._y1, p1[1])):
            s.blockSignals(True)
            s.setValue(float(v))
            s.blockSignals(False)


class CustomFormulaDialog(QDialog):
    """Dialog for creating a custom-formula analytic edge: parametric x(t),y(t)
    or explicit y=f(x), the t/x range, and node count."""

    def __init__(self, parent=None, seg=None, preview_cb=None):
        super().__init__(parent)
        self.setWindowTitle("Custom Formula Edge")
        self.setStyleSheet("background:#121422; color:#cdd6f4;")
        self.setMinimumWidth(340)
        self._preview_cb = preview_cb

        lay = QVBoxLayout(self)
        lay.setSpacing(8)

        # Mode selector.
        mode_row = QHBoxLayout()
        self._param_rb = QRadioButton("Parametric  x(t), y(t)")
        self._explicit_rb = QRadioButton("Explicit  y = f(x)")
        self._param_rb.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self._param_rb)
        grp.addButton(self._explicit_rb)
        mode_row.addWidget(self._param_rb)
        mode_row.addWidget(self._explicit_rb)
        lay.addLayout(mode_row)

        form = QFormLayout()
        self._x_edit = QLineEdit("cos(t)")
        self._y_edit = QLineEdit("sin(t)")
        self._f_edit = QLineEdit("sin(x)")
        for e in (self._x_edit, self._y_edit, self._f_edit):
            e.setStyleSheet(SPIN_STYLE)
        self._x_row = QLabel("x(t) =")
        self._y_row = QLabel("y(t) =")
        self._f_row = QLabel("y(x) =")
        form.addRow(self._x_row, self._x_edit)
        form.addRow(self._y_row, self._y_edit)
        form.addRow(self._f_row, self._f_edit)

        self._tmin = CleanDoubleSpinBox()
        self._tmin.setRange(-1e6, 1e6); self._tmin.setDecimals(6)
        self._tmin.setValue(0.0); self._tmin.setStyleSheet(SPIN_STYLE)
        self._tmax = CleanDoubleSpinBox()
        self._tmax.setRange(-1e6, 1e6); self._tmax.setDecimals(6)
        self._tmax.setValue(6.283185307); self._tmax.setStyleSheet(SPIN_STYLE)
        form.addRow(QLabel("t / x  min:"), self._tmin)
        form.addRow(QLabel("t / x  max:"), self._tmax)

        self._node_spin = QSpinBox()
        self._node_spin.setRange(2, 100000); self._node_spin.setValue(100)
        self._node_spin.setStyleSheet(SPIN_STYLE)
        form.addRow(QLabel("Node Count:"), self._node_spin)
        lay.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        # Pre-fill from an existing edge when editing.
        if seg is not None:
            self._explicit_rb.setChecked(getattr(seg, "curve_mode", "parametric") != "parametric")
            self._param_rb.setChecked(getattr(seg, "curve_mode", "parametric") == "parametric")
            self._x_edit.setText(getattr(seg, "x_formula", "cos(t)"))
            self._y_edit.setText(getattr(seg, "y_formula", "sin(t)"))
            self._f_edit.setText(getattr(seg, "formula", "sin(x)"))
            self._tmin.setValue(getattr(seg, "t_min", 0.0))
            self._tmax.setValue(getattr(seg, "t_max", 6.283185307))
            self._node_spin.setValue(int(seg.parameters.get("n_points", 100)))

        self._param_rb.toggled.connect(self._update_mode_visibility)
        self._update_mode_visibility()

        # Live preview: notify the controller on every edit so it can redraw the
        # formula on the canvas (and fit the view on first show).
        for e in (self._x_edit, self._y_edit, self._f_edit):
            e.textChanged.connect(self._emit_preview)
        self._tmin.valueChanged.connect(self._emit_preview)
        self._tmax.valueChanged.connect(self._emit_preview)
        self._node_spin.valueChanged.connect(self._emit_preview)
        self._param_rb.toggled.connect(self._emit_preview)
        self._emit_preview()

    def _emit_preview(self, *args):
        if self._preview_cb is not None:
            self._preview_cb(self.result_config())

    def _update_mode_visibility(self):
        is_param = self._param_rb.isChecked()
        self._x_row.setVisible(is_param); self._x_edit.setVisible(is_param)
        self._y_row.setVisible(is_param); self._y_edit.setVisible(is_param)
        self._f_row.setVisible(not is_param); self._f_edit.setVisible(not is_param)

    def result_config(self) -> dict:
        return {
            "mode": "parametric" if self._param_rb.isChecked() else "explicit",
            "x_formula": self._x_edit.text(),
            "y_formula": self._y_edit.text(),
            "formula": self._f_edit.text(),
            "t_min": self._tmin.value(),
            "t_max": self._tmax.value(),
            "n_points": self._node_spin.value(),
        }
