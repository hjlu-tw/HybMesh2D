from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QFormLayout, QLineEdit, QCheckBox
from app.utils import SPIN_STYLE, help_label, help_widget
from app.views.clean_double_spin_box import CleanDoubleSpinBox
from app.models import shape_spec


class EdgePropsNacaMixin:
    """The parametric NACA aerofoil's page in the edge-props shape stack.

    A file of its own rather than another block in
    ``edge_props_shape_build_mixin``: adding it there took that file past the
    ~500-line standard, and a per-shape page is exactly the unit that file is a
    list of. It runs on the composed panel (uses ``self.shape_stack`` and
    ``self._xy_row``), like every other page builder.
    """

    def _build_naca_page(self):
        """Widget 9: the parametric NACA 4-digit aerofoil.

        The widget NAMES are shape_spec's (``SIDEBAR_ATTRS`` / ``TEXT_ATTRS`` /
        ``BOOL_ATTRS``), so the read/write pair and the edit wiring pick them up
        with no second list. ``part`` has no widget on purpose: which piece of
        the section an edge is, is decided when the aerofoil is CREATED (two
        surfaces, plus a trailing-edge base when it is blunt), and a combo that
        let one edge become the other's part would leave the geometry with two
        uppers and no lower.
        """
        widget_naca = QWidget()
        layout_naca = QFormLayout(widget_naca)
        layout_naca.setContentsMargins(0, 0, 0, 0)

        self.naca_designation = QLineEdit(shape_spec.DEFAULTS["naca4"]["designation"])
        self.naca_designation.setStyleSheet(SPIN_STYLE)
        self.naca_designation.setToolTip(
            "NACA 4-digit designation, e.g. 0012 (symmetric, 12% thick) or\n"
            "2412 (2% camber at 40% chord, 12% thick).")
        self.naca_chord = CleanDoubleSpinBox()
        self.naca_chord.setRange(1e-6, 1e6)
        self.naca_chord.setDecimals(4)
        self.naca_chord.setValue(1.0)
        self.naca_chord.setStyleSheet(SPIN_STYLE)
        self.naca_chord.setToolTip("Chord length, leading edge to trailing edge")
        self.naca_x_le = CleanDoubleSpinBox()
        self.naca_x_le.setRange(-1e6, 1e6)
        self.naca_x_le.setDecimals(4)
        self.naca_x_le.setStyleSheet(SPIN_STYLE)
        self.naca_x_le.setToolTip("X-coordinate of the leading edge")
        self.naca_y_le = CleanDoubleSpinBox()
        self.naca_y_le.setRange(-1e6, 1e6)
        self.naca_y_le.setDecimals(4)
        self.naca_y_le.setStyleSheet(SPIN_STYLE)
        self.naca_y_le.setToolTip("Y-coordinate of the leading edge")
        self.naca_alpha = CleanDoubleSpinBox()
        self.naca_alpha.setRange(-180.0, 180.0)
        self.naca_alpha.setDecimals(2)
        self.naca_alpha.setSuffix("\u00b0")
        self.naca_alpha.setStyleSheet(SPIN_STYLE)
        self.naca_alpha.setToolTip(
            "Angle of attack: the section is pitched by MINUS this angle about\n"
            "its leading edge, so a positive value is nose-up against a flow\n"
            "running along +X.")
        self.naca_sharp_te = QCheckBox(shape_spec.param_label("naca4", "sharp_te"))
        self.naca_sharp_te.setChecked(True)
        self.naca_sharp_te.setStyleSheet("color:#a0a8c0; font-size:11px;")
        self._naca_te_tip = (
            "On: the closed-trailing-edge variant (-0.1036), so the two\n"
            "surfaces meet at one point.\n"
            "Off: the report's open trailing edge (-0.1015), whose base is a\n"
            "segment of its own.")
        self.naca_sharp_te.setToolTip(self._naca_te_tip)
        lbl_desig = shape_spec.param_label("naca4", "designation")
        layout_naca.addRow(help_label(lbl_desig + ":",
                                      "NACA 4-digit designation, e.g. 0012"),
                           self.naca_designation)
        layout_naca.addRow(help_label("Chord:", "Chord length"), self.naca_chord)
        layout_naca.addRow(help_label("Leading edge:", "Leading-edge position (x, y)"),
                           self._xy_row(self.naca_x_le, self.naca_y_le))
        layout_naca.addRow(help_label("Angle of attack:", "Nose-up angle in degrees"),
                           self.naca_alpha)
        layout_naca.addRow(help_widget(self.naca_sharp_te,
                           "Off gives the report's open (blunt) trailing edge"))
        self.shape_stack.addWidget(widget_naca)
        return layout_naca

    def _set_naca_te_editable(self, editable: bool):
        """Enable or disable the sharp-TE flag, saying WHY when it is off.

        The reason is the panel's rule (see `show_curve_segment`); the tooltip
        is swapped rather than left stale, because a greyed control with its
        normal tooltip is a control the user cannot find out about.
        """
        self.naca_sharp_te.setEnabled(editable)
        self.naca_sharp_te.setToolTip(
            self._naca_te_tip if editable else
            "Fixed for one PART of an aerofoil: it decides whether the section "
            "has a\ntrailing-edge segment at all, so changing it here would "
            "leave this edge\nand its sibling describing different sections. "
            "Draw the aerofoil again\nto change it.")
