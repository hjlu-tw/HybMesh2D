"""The Qt half of a :class:`~app.services.field_spec.FieldSpec`: one widget class per
kind, and one way to read and write each.

Three traversals live here and nothing else does them: build (:func:`add_spec_rows`),
write (:func:`write_specs`, model → widgets) and read (:func:`read_specs`, widgets →
model). Before this module each panel spelled all three out by hand — the solver's two
halves alone were 88 widget constructions against 75 reads and 77 writes — and the BL
dialog kept a third, quietly divergent copy of the kind→widget mapping.

Rules that are not cosmetic:

* **Numeric and combo fields are added to the form DIRECTLY, never wrapped.**
  ``QFormLayout.labelForField(w)`` only finds a label for a widget that is the field
  cell itself, and four visibility helpers use it to hide a row's label along with its
  field. Wrapping a spin box in a help container silently orphans its label.
* **A checkbox carries its own text**, so its row is ``addRow("", help_widget(cb))`` —
  the label column stays empty, exactly as the hand-written forms had it.
* **Seeding comes from the model, not from literals in build code.** A panel is built
  with whatever Qt leaves in an un-set widget (0, or the range floor), and the sync
  that made the panel authoritative reads every panel back at startup — which is how
  the GUI's real defaults silently became BL layers 0, growth 1.001, Gmsh MeshAdapt
  and all-inlet outer BCs. Seeding from the dataclass makes the documented defaults
  the panel's defaults by construction.
* **A choice is matched by VALUE in Python, never by ``findData``.** ``findData``
  compares QVariants, so a bool ``False`` against an int ``0`` datum is a coin toss;
  the sparse method combos (convex 0/2, Gmsh 1/2/5/6/7/8) are exactly where that
  would bite. Matching here also lets a value the combo does not offer fall back to a
  declared one instead of silently landing on index 0.
"""
from __future__ import annotations

from typing import Any, Callable, Iterable, Mapping

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QWidget,
)

from app.services.field_spec import FieldSpec, NUMERIC_KINDS
from app.utils import COMBO_STYLE, LINEEDIT_STYLE, SPIN_STYLE, help_label, help_widget
from app.views.clean_double_spin_box import (
    CleanDoubleSpinBox, NarrowDoubleSpinBox, SciDoubleSpinBox,
)

__all__ = [
    "make_widget", "read_widget", "write_widget", "edit_signal",
    "build_spec_widgets", "add_spec_rows", "read_specs", "write_specs",
    "wire_specs", "spec_widgets", "set_spec_row_visible", "browse_row",
    "SpecRowsMixin",
]

_BROWSE_QSS = (
    "QPushButton{background:#1d2a3a;color:#dde2ff;border:1px solid #2d3356;"
    "border-radius:4px;padding:2px;} QPushButton:hover{border-color:#5a9ad4;}")


# ── construction ────────────────────────────────────────────────────────────

def make_widget(spec: FieldSpec) -> QWidget:
    """The widget for one spec, styled, ranged and tooltipped. No value set."""
    o: Mapping[str, Any] = spec.opts
    kind = spec.kind

    if kind in ("sci", "float", "narrow", "int"):
        if kind == "sci":
            w = SciDoubleSpinBox()
        elif kind == "narrow":
            w = NarrowDoubleSpinBox()
        elif kind == "float":
            w = CleanDoubleSpinBox()
        else:
            w = QSpinBox()
        w.setRange(o["lo"], o["hi"])
        if kind in ("float", "narrow"):
            w.setDecimals(o["dec"])
            w.setSingleStep(o.get("step", 0.1))
        if "suffix" in o:
            w.setSuffix(o["suffix"])
        if "special" in o:
            # e.g. 0 displays as "auto" for the refinement-seed size/radius.
            w.setSpecialValueText(o["special"])
        if o.get("width"):
            w.setMaximumWidth(o["width"])
            if hasattr(w, "setWidthCap"):
                # A wide range + 6 decimals reports a ~140px minimumSizeHint, so the
                # requested width would not take effect on a multi-spin row.
                w.setWidthCap(o["width"])
        w.setStyleSheet(SPIN_STYLE)

    elif kind in ("text", "gfloat", "path"):
        w = QLineEdit()
        w.setStyleSheet(LINEEDIT_STYLE)
        if o.get("readonly"):
            w.setReadOnly(True)
        if o.get("placeholder"):
            w.setPlaceholderText(o["placeholder"])
            # LINEEDIT_STYLE pins an explicit text colour, so the placeholder would
            # otherwise render like a real value; dim it via the palette.
            from PyQt6.QtGui import QColor, QPalette
            pal = w.palette()
            pal.setColor(QPalette.ColorRole.PlaceholderText, QColor("#5a6480"))
            w.setPalette(pal)

    elif kind == "bool":
        w = QCheckBox(o.get("text", spec.label))
        w.setStyleSheet("color:#a0a8c0;")

    elif kind == "bcname":
        from app.views.bc_widget import BCWidget
        w = BCWidget()

    elif kind == "toggle":
        # A write-format switch: a checkable button that highlights green when on,
        # so "which files will Generate write?" is legible at a glance.
        from app.utils import make_button
        w = make_button(o.get("text", spec.label), "#181b2a", border="#2d3356",
                        hover_border="#5a9ad4", checked_bg="#1e4620")
        w.setCheckable(True)

    elif kind == "choice":
        w = QComboBox()
        for _val, lbl in _choices(spec):
            w.addItem(lbl)
        w.setStyleSheet(COMBO_STYLE)

    else:                                    # "label" — a derived read-out
        w = QLabel(o.get("text", ""))
        w.setWordWrap(True)
        w.setStyleSheet(o.get("style", "color:#8a93ad; font-size:11px;"))
        if o.get("hidden"):
            w.setVisible(False)

    if spec.tip:
        w.setToolTip(spec.tip)
    return w


def _choices(spec: FieldSpec) -> list[tuple[Any, str]]:
    """The (value, label) pairs this widget offers.

    Always ``opts["choices"]``: a host that offers a narrowed set asks
    :func:`app.services.field_spec.panel_table` for that view of the table, so no
    function here needs to know which host it is serving.
    """
    return list(spec.opts["choices"])


# ── read / write one widget ─────────────────────────────────────────────────

def _as_number(v) -> float:
    return float(v)


def _as_bool(v) -> bool:
    try:
        return bool(float(v))
    except (TypeError, ValueError):
        return bool(v)


def _choice_key(v):
    """A comparable form of a choice value: numbers (and bools) as ints, else str."""
    if isinstance(v, (bool, int, float)):
        return int(round(float(v)))
    return str(v)


def write_widget(w: QWidget, spec: FieldSpec, value) -> None:
    """Set ``w`` from a model value. ``None`` leaves the widget alone."""
    if spec.write is not None:
        spec.write(w, value)
        return
    if value is None or spec.kind == "label":
        return
    kind = spec.kind
    if kind == "int":
        w.setValue(int(round(_as_number(value))))
    elif kind in ("sci", "float", "narrow"):
        w.setValue(_as_number(value))
    elif kind in ("text", "path", "bcname"):
        w.setText("" if value is None else str(value))
    elif kind == "gfloat":
        w.setText(f"{_as_number(value):g}")
    elif kind in ("bool", "toggle"):
        w.setChecked(_as_bool(value))
    elif kind == "choice":
        choices = _choices(spec)
        want = _choice_key(value)
        idx = next((i for i, (val, _l) in enumerate(choices)
                    if _choice_key(val) == want), -1)
        if idx < 0 and "fallback" in spec.opts:
            fb = _choice_key(spec.opts["fallback"])
            idx = next((i for i, (val, _l) in enumerate(choices)
                        if _choice_key(val) == fb), -1)
        w.setCurrentIndex(idx if idx >= 0 else 0)


def read_widget(w: QWidget, spec: FieldSpec, fallback=None):
    """The model value ``w`` currently holds, or None when the spec authors nothing."""
    if spec.read is not None:
        return spec.read(w)
    kind = spec.kind
    if kind == "int":
        return int(w.value())
    if kind in ("sci", "float", "narrow"):
        return float(w.value())
    if kind in ("text", "path", "bcname"):
        return w.text().strip() or spec.opts.get("fallback", "")
    if kind == "gfloat":
        try:
            return float(w.text().strip())
        except (AttributeError, ValueError):
            return fallback
    if kind in ("bool", "toggle"):
        checked = w.isChecked()
        return int(checked) if spec.opts.get("as_int") else checked
    if kind == "choice":
        choices = _choices(spec)
        i = w.currentIndex()
        if 0 <= i < len(choices):
            return choices[i][0]
        return spec.opts.get("fallback", choices[0][0] if choices else None)
    return None                                       # "label"


def edit_signal(w: QWidget, spec: FieldSpec):
    """The signal that means "the user changed this field", or None."""
    kind = spec.kind
    if kind in NUMERIC_KINDS:
        return w.valueChanged
    if kind in ("text", "gfloat", "path", "bcname"):
        return w.textChanged
    if kind in ("bool", "toggle"):
        return w.toggled
    if kind == "choice":
        return w.currentIndexChanged
    return None


# ── table traversals ────────────────────────────────────────────────────────

def build_spec_widgets(host, specs: Iterable[FieldSpec], defaults=None) -> list:
    """Create each spec's widget, store it on ``host`` and seed it from ``defaults``.

    ``defaults`` is a model instance; a spec whose field it does not carry (or that
    authors nothing) is left at the widget's own initial state.
    """
    built = []
    for spec in specs:
        w = make_widget(spec)
        setattr(host, spec.attr, w)
        name = spec.model_name
        if defaults is not None and name is not None and hasattr(defaults, name):
            write_widget(w, spec, getattr(defaults, name))
        built.append(w)
    return built


def add_spec_rows(host, form, specs: Iterable[FieldSpec], defaults=None,
                  wrap: Mapping[str, Callable[[Any, QWidget], QWidget]] | None = None
                  ) -> list:
    """Build ``specs`` onto ``host`` and append one form row each, in table order.

    ``wrap`` lets a section give one field a composite field cell (a Browse button, a
    'Build…' button) while the WIDGET still comes from the table — the point being
    that an irregular row must not cost the field a second declaration.
    """
    wrap = wrap or {}
    built = []
    # Which form each row landed in, and which widget IS its field cell. Recorded
    # because hiding a ROW means hiding three things — the widget, the cell it may
    # be wrapped in (a Browse row) and the label QFormLayout paired with that cell —
    # and `labelForField` only answers for the cell. Every helper that hid a row used
    # to carry its own `self._some_form` for exactly this, which is fine for one field
    # and wrong for a rule (mode applicability) that spans several sections.
    cells: dict = getattr(host, "_spec_cells", None)
    if cells is None:
        cells = {}
        host._spec_cells = cells
    for spec in specs:
        w = build_spec_widgets(host, [spec], defaults)[0]
        built.append(w)
        cell: QWidget = w
        if spec.attr in wrap:
            cell = wrap[spec.attr](host, w)
        elif spec.kind == "path":
            cell = browse_row(host, w, spec.opts.get("caption", "Select file"),
                              spec.opts.get("filter", "All Files (*)"))
        cells[spec.attr] = (form, cell)
        if spec.kind == "bool":
            # The text is on the checkbox; an empty label column keeps the row's
            # shape identical to the hand-written forms.
            form.addRow("", help_widget(cell, spec.tip))
        elif spec.opts.get("bare") or not spec.label:
            form.addRow("", cell)
        else:
            form.addRow(help_label(spec.label + spec.opts.get("colon", ":"),
                                   spec.tip), cell)
    return built


def set_spec_row_visible(host, attr: str, visible: bool) -> None:
    """Show/hide one table-built row: its widget, its field cell and its label.

    A no-op for an attr the host never built through :func:`add_spec_rows` (the BL
    tables are also built without rows, and a caller should not have to know which).
    """
    w = getattr(host, attr, None)
    form, cell = getattr(host, "_spec_cells", {}).get(attr, (None, None))
    if w is not None:
        w.setVisible(visible)
    if cell is not None and cell is not w:
        cell.setVisible(visible)
    if form is not None:
        lbl = form.labelForField(cell if cell is not None else w)
        if lbl is not None:
            lbl.setVisible(visible)


def spec_widgets(host, specs: Iterable[FieldSpec]) -> list:
    """The live widgets for ``specs`` (skipping any the host does not have yet)."""
    out = []
    for spec in specs:
        w = getattr(host, spec.attr, None)
        if w is not None:
            out.append(w)
    return out


def write_specs(host, specs: Iterable[FieldSpec], cfg) -> None:
    """Model → widgets, for every spec that authors a field ``cfg`` carries."""
    for spec in specs:
        name = spec.model_name
        w = getattr(host, spec.attr, None)
        if w is None or name is None or not hasattr(cfg, name):
            continue
        if spec.opts.get("host_writes"):
            # The panel decides this one itself. Exactly one field does: the mesh
            # Output name, whose population is a HEURISTIC (refresh an
            # auto-generated name from the current geometry, keep a name the user
            # typed) that reads the widget's current text — so a plain copy here
            # would destroy the very state the heuristic branches on.
            continue
        write_widget(w, spec, getattr(cfg, name))


def read_specs(host, specs: Iterable[FieldSpec], cfg) -> None:
    """Widgets → model, for every spec that authors a field.

    The model's current value is passed as the fallback, which is what a ``gfloat``
    needs: an unparseable line edit must keep the value the model already holds
    rather than substituting a zero.
    """
    for spec in specs:
        name = spec.model_name
        w = getattr(host, spec.attr, None)
        if w is None or name is None:
            continue
        val = read_widget(w, spec, getattr(cfg, name, None))
        if val is not None or spec.read is not None:
            setattr(cfg, name, val)


def wire_specs(host, specs: Iterable[FieldSpec], slot) -> None:
    """Connect every spec's edit signal to ``slot``."""
    for spec in specs:
        w = getattr(host, spec.attr, None)
        if w is None:
            continue
        sig = edit_signal(w, spec)
        if sig is not None:
            sig.connect(slot)


# ── shared composite rows ───────────────────────────────────────────────────

def browse_row(parent, edit: QLineEdit, caption: str,
               filt: str = "All Files (*)") -> QWidget:
    """A line edit + '…' Browse button, as one form-field cell."""
    btn = QPushButton("…")
    btn.setFixedWidth(32)
    btn.setStyleSheet(_BROWSE_QSS)

    def _do():
        f, _ = QFileDialog.getOpenFileName(parent, caption, "", filt)
        if f:
            edit.setText(f)
    btn.clicked.connect(_do)
    row = QHBoxLayout()
    row.setSpacing(4)
    row.addWidget(edit, 1)
    row.addWidget(btn)
    w = QWidget()
    w.setLayout(row)
    return w


class SpecRowsMixin:
    """``_spec_rows`` / ``_spec_widgets`` for a panel built from a field-spec table.

    All three config panels want the same two calls — lay out one declared GROUP of
    rows, or build one group's widgets without rows because several share a line — and
    all three had their own copy differing only in which table and which model class to
    seed from. Those two facts are now class attributes.

    ``_SPEC_TABLE`` is the panel's default table; a panel with more than one (the mesh
    panel, which shares the 21 BL parameters with the Edit-BL dialog) passes the other
    explicitly. ``_SPEC_MODEL`` is the dataclass each widget is seeded from: a panel is
    otherwise built with whatever Qt leaves in an un-set widget, and since the
    panel->model sync reads every panel back at startup, that value BECOMES the
    session's default.

    Not a Qt virtual, so this mixin's position in the bases is free — unlike the
    layout mixins, which override ``showEvent``/``resizeEvent`` and must precede
    QDialog (see mesh_bl_dialog_layout).
    """

    #: The panel's own table (a tuple of FieldSpec) and the model class to seed from.
    _SPEC_TABLE: tuple = ()
    _SPEC_MODEL = None

    def _spec_rows(self, form, group: str, table=None, wrap=None):
        """Lay out one declared GROUP of fields into ``form``, in table order."""
        from app.services.field_spec import in_group
        return add_spec_rows(self, form, in_group(table or self._SPEC_TABLE, group),
                             self._SPEC_MODEL() if self._SPEC_MODEL else None, wrap)

    def _spec_widgets(self, group: str, table=None):
        """Build one declared GROUP's widgets without adding form rows.

        For a group whose members share a line rather than taking a row each: the three
        mesh write-format toggles under one "Formats:" label, the solver feature toggles
        that gate a sub-form, the STL3d domain bounds two per row and Nx/Ny/Nz in one.
        Same traversal and same seeding; only the layout differs.
        """
        from app.services.field_spec import in_group
        return build_spec_widgets(self, in_group(table or self._SPEC_TABLE, group),
                                  self._SPEC_MODEL() if self._SPEC_MODEL else None)
