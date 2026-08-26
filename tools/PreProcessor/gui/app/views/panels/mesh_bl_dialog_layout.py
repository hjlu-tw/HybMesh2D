"""Accordion layout and window fitting for the Edit-Boundary-Layer dialog.

Split out of ``mesh_dialogs_bl.py`` (over the GUI file-size budget); the dialog's own
state, widgets and result accessors stay there, and this mixin owns only how the 21 BL
parameters are grouped on screen and how the window follows the groups the user opens.

Two Qt facts the fit depends on, both learned the hard way:

* ``QScrollArea::sizeHint()`` is clamped to 24 font heights, so the dialog's own
  ``sizeHint()`` stops growing after a group or two — the fit therefore measures the
  scroll area's shortfall against its cap and the slack handed to the absorber, never
  ``self.sizeHint()``.
* Hiding a widget only POSTS the layout request, so a reader that sizes itself from a
  section immediately after a toggle sees the state the section just LEFT
  (``CollapsibleSection._on_toggle`` invalidates its own layout for this reason).

Mixin first in the bases: :meth:`showEvent`, :meth:`resizeEvent` and :meth:`done`
override Qt virtuals and call ``super()``, so QDialog has to come after this class in the
MRO or those calls land on ``object``.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QWidget

from app.utils import align_form_labels, help_label
from app.views.collapsible import CollapsibleSection
from app.services.field_spec import by_key
from app.views.panels.mesh_bl_field_specs import (
    BL_SPECS, _BL_FIELD_GROUPS, _value_differs,
)

__all__ = ["BLDialogLayoutMixin"]

#: A field the selected junction scheme cannot read is greyed out, and its row says
#: WHY -> the short on-screen reason, keyed by parameter. ONE declaration: the row
#: cell is built for these keys and :meth:`_wire_method_dependent_fields` is the only
#: thing that fills or clears the text, so "is C1 live?" is decided in one place and
#: the lock and its explanation cannot disagree. The long form stays in the spec's
#: own tip (``services/mesh_bl_field_specs._C1_TIP``) and is NOT repeated here.
_C1_KEY = "BL_JUNCTION_ANGLE_C1"
_FIELD_NOTES = {_C1_KEY: "method 0 only"}

#: The dialog's secondary-text style, for a group's hint line and a row's note alike.
_HINT_QSS = "color:#8a93ad; font-size:10px;"


class BLDialogLayoutMixin:
    """Grouped field layout + window fitting for :class:`PerGeomBLDialog`."""

    def _build_sections(self, col, seed: dict, defaults: dict):
        """Build one CollapsibleSection per _BL_FIELD_GROUPS entry into ``col``,
        seeding each field from ``seed``. Only groups marked start_expanded open — as
        shipped that is NONE of them, so the dialog opens as a list of headers — with
        two exceptions that both err on the side of showing a value rather than hiding
        it: a group holding a value that DIFFERS from ``defaults`` (i.e. something this
        geometry actually overrides) is expanded, and any spec key missing from the
        table lands in a trailing 'Other' group, which opens so an unreachable
        parameter cannot also be an invisible one."""
        specs = by_key(BL_SPECS)
        listed = {k for _t, _e, _h, keys in _BL_FIELD_GROUPS for k in keys}
        groups = list(_BL_FIELD_GROUPS)
        stray = [s.key for s in BL_SPECS if s.key not in listed]
        if stray:
            groups.append(("Other", True, "Ungrouped parameters.", stray))

        forced: list = []
        forms: list = []
        labels: list = []
        for title, start_expanded, hint, keys in groups:
            sec = CollapsibleSection(title, start_collapsed=not start_expanded)
            if hint:
                h = QLabel(hint)
                h.setWordWrap(True)
                h.setStyleSheet(_HINT_QSS)
                sec.add_widget(h)
            form = QFormLayout()
            form.setContentsMargins(0, 0, 0, 0)
            for key in keys:
                spec = specs[key]
                w = self._make_widget(spec)
                self._set_widget_value(w, spec, seed.get(key))
                # The SPEC travels with the widget, not just its kind: reading a
                # sparse choice back needs the (value, label) pairs, and a caller
                # that only kept the kind would have to look them up again.
                self._widgets[key] = (w, spec)
                # The '?' shows the spec's explanation AND the .dat/Config.hpp KEY.
                # Both, deliberately: the KEY is how someone reading a config file
                # finds this field (the group titles follow the .dat parameter groups
                # for the same reason), and it used to be the ONLY help 20 of the 21
                # fields had — giving every spec a tip would otherwise have replaced
                # it rather than added to it. A field the default scheme ignores has
                # to say so HERE: the wording existed, but on the hidden backing
                # widgets in the mesh panel, which is not where the user edits it.
                lbl = help_label(spec.label + ":",
                                 f"{spec.tip}\n\n({key})" if spec.tip else key)
                labels.append(lbl)
                form.addRow(lbl, self._field_cell(key, w))
            forms.append(form)
            sec.add_layout(form)
            sec.toggle_btn.toggled.connect(lambda _c: self._relayout())
            col.addWidget(sec)
            self._sections.append(sec)
            if any(_value_differs(seed.get(k), defaults.get(k)) for k in keys):
                forced.append(sec)

        # One label column across all groups, MEASURED from the labels actually
        # built rather than a hardcoded width: the widest here ("Concave Threshold
        # (deg)") overflows a guessed 150 and, being right-aligned in a fixed-width
        # cell, loses its first characters — and the next parameter added would go
        # stale again. Bounded so one long label cannot eat the field column.
        col_w = max((lbl.sizeHint().width() for lbl in labels), default=150)
        col_w = min(max(col_w, 120), 240)
        for form in forms:
            align_form_labels(form, col_w)

        self._wire_method_dependent_fields()

        # Reopen whatever the user left open last time, then re-apply the
        # overridden-value rule on top: a saved "collapsed" must not hide a value
        # that differs from the global default.
        from app.services import ui_state
        ui_state.restore_section_states(self._STATE_SCOPE, self._sections)
        for sec in forced:
            if not sec.is_expanded:
                sec.expand()

    def _field_cell(self, key: str, w):
        """The FIELD half of one row: the widget itself, or — for a parameter the
        selected scheme can render dead (:data:`_FIELD_NOTES`) — the widget beside an
        initially empty note label that :meth:`_wire_method_dependent_fields` fills
        with the reason.

        The note rides beside the FIELD rather than being appended to the LABEL, and
        that is measured rather than stylistic. The label column is sized from the
        labels actually built (bounded 120..240) and measures 171 today; the composite
        for ``Junction \u03b8 C1 (deg) \u2014 method 0 only:`` measures 240, so
        suffixing the label would shove every label in the dialog 69 px right and sit
        on the upper bound, where the next parameter added would clip instead. The note
        cell feeds no measurement: 171 + 86 (spin box) + 4 + 73 (note) = 334 px, inside
        the dialog's own 380 px minimum width, so nothing moves and nothing clips.

        This is the ONE row in the GUI whose field cell is a composite, against
        CLAUDE.md's "Numeric and combo rows go into the form DIRECTLY, never wrapped".
        The precondition that rule protects is named there and holds here: a wrapped
        cell hides the row from ``QFormLayout.labelForField``, which the four
        visibility helpers use to hide a label with its field — and NO caller resolves
        a label on this dialog's forms (all twelve live in ``mesh_sizing_mixin`` and
        ``edge_props_*``, over the mesh panel's own forms). ``align_form_labels`` reads
        ``itemAt(i, LabelRole)``, not the field, so it is unaffected. The gate pins
        that precondition, so a visibility helper added here fails the build rather
        than silently finding no label.

        A hint on the disabled widget itself is not an option, which is also measured:
        hovering an ENABLED spin box delivers ``Enter`` to it, and hovering the disabled
        one delivers no event to it OR to its parent — Qt picks the mouse receiver by
        walking past disabled widgets, so the box's own tooltip is never shown. The
        '?' beside the label stays enabled and carries the long prose.
        """
        note_text = _FIELD_NOTES.get(key)
        if note_text is None:
            return w
        cell = QWidget()
        row = QHBoxLayout(cell)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(w)
        note = QLabel("")
        note.setStyleSheet(_HINT_QSS)
        # No trailing stretch: the spin box carries Qt's (Expanding, Fixed) policy, so
        # the surplus goes to IT and the box stays the same width as C2's and C3's beside
        # it. A stretch here would absorb that surplus and leave this one row's box
        # visibly narrower than its neighbours.
        row.addWidget(note)
        self._notes[key] = note
        return cell

    def field_note(self, key: str) -> str:
        """The reason the row beside ``key``'s field is showing, '' when it shows none.
        The dialog's answer to "why can I not edit this?", read from the row itself
        rather than from a tooltip nobody knows to hover.

        ``isHidden()`` is not a visibility test and is not read as one: a widget inside
        a COLLAPSED group reports ``isHidden() == False`` while ``isVisible()`` is
        False, and that is the right answer here — the field is hidden with it, so
        there is nothing to explain. What the guard rejects is a note deliberately
        hidden while its text still says the field is dead, which is the silent lock
        this whole row exists to prevent, coming back through the other door. Nothing
        shipped hides one today.
        """
        note = self._notes.get(key)
        return note.text() if note is not None and not note.isHidden() else ""

    def _wire_method_dependent_fields(self):
        """Grey out C1 unless the junction scheme that reads it is selected.

        Method 1 (the default) bins its slide by a hard-coded 95 deg — the angle below
        which a perpendicular cap provably leaves the domain through the no-BL wall — so
        C1 is dead for it. Left editable, it is a knob that changes a number, is written
        back on OK, round-trips through the config, and never changes a mesh; the only
        way to discover that was to regenerate and diff. Still ENABLED for method 0,
        whose taper-to-zero scheme does read it.

        The lock was correct and its SILENCE was the defect (issue #23): on screen the
        greyed box was indistinguishable from a field greyed for some other reason, or
        from a bug — which is exactly what it was reported as. So the same ``_sync``
        that disables the field also states why, in the row's own note cell, and clears
        it again when method 0 re-enables the field. One decision, one place: a second
        thing deciding "is C1 live?" is how the two would come to disagree.
        """
        m = self._widgets.get("BL_JUNCTION_METHOD")
        c1 = self._widgets.get(_C1_KEY)
        if not m or not c1 or not hasattr(m[0], "currentIndexChanged"):
            return

        def _sync(*_a):
            try:
                reads_c1 = self._widget_value(m[0], m[1]) == 0
            except (TypeError, ValueError):
                reads_c1 = True          # unreadable: leave it editable, never stuck off
            c1[0].setEnabled(reads_c1)
            # ...and say so where the user is already looking. Editable means there is
            # nothing to explain, which is why the unreadable-method fallback shows no
            # marker: it leaves the field live.
            note = self._notes.get(_C1_KEY)
            if note is not None:
                note.setText("" if reads_c1 else _FIELD_NOTES[_C1_KEY])

        m[0].currentIndexChanged.connect(_sync)
        _sync()

    def _set_all_sections(self, expand: bool):
        self._fit_suspended = True
        try:
            for sec in self._sections:
                sec.expand() if expand else sec.collapse()
        finally:
            self._fit_suspended = False
        self._relayout()

    def showEvent(self, e):
        # First layout pass: size the parameter area (and the window) to whatever
        # groups are open. Done here rather than in __init__ because the segment
        # section and the button box are not in the layout yet at that point.
        super().showEvent(e)
        self._relayout()
        self._shown = True        # from here on, a resize is the user's doing

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._shown and not self._autofitting:
            self._user_h = self.height()

    def _relayout(self):
        """Cap the parameter area at its content height, so collapsing groups
        hands the space back instead of leaving a tall empty scroll box. A cap,
        not a fixed height: once the open groups are taller than the dialog the
        layout gives less and the scrollbar takes over."""
        if self._fit_suspended:
            return
        # invalidate() first: hiding a section's content posts the layout request,
        # so the cached sizeHint still describes the PREVIOUS state and the cap
        # would be computed from the group the user just closed.
        inner = self._content.layout()
        if inner is not None:
            inner.invalidate()
            inner.activate()
        h = self._content.sizeHint().height() + 4
        self._scroll.setMaximumHeight(max(self._scroll.minimumHeight(), h))
        self.layout().invalidate()
        self.layout().activate()
        self._autofit_height()

    def _autofit_height(self):
        """Follow the open groups with the window height. A fixed window is wrong
        in both directions for an accordion: too tall leaves a dead grey band
        under the collapsed groups, too short makes 'Expand all' scroll a 3-row
        viewport. Bounded by the screen, so expanding everything can never produce
        a window taller than the display, and never below a height the user set
        themselves by dragging the window.

        Works from what the layout ACTUALLY gave the elastic items — the scroll
        area's shortfall against its cap, and the slack handed to whatever absorbs
        leftover space — rather than from a predicted chrome height, so it is exact
        in both directions and self-corrects. It deliberately does not use
        ``self.sizeHint()``: ``QScrollArea::sizeHint()`` is clamped to 24 font
        heights, so the dialog's own hint stops growing after the first group or
        two and the window would never follow."""
        scr = self.screen()
        cap = int(scr.availableGeometry().height() * 0.85) if scr is not None else 1 << 20
        floor = max(self.minimumSizeHint().height(), self._user_h)
        self._autofitting = True
        try:
            for _ in range(2):      # one corrective pass; the layout runs between
                short = self._scroll.maximumHeight() - self._scroll.height()
                want = max(floor, min(self.height() + short - self._slack(), cap))
                if abs(want - self.height()) <= 2:
                    return
                self.resize(self.width(), want)
                self.layout().activate()
        finally:
            self._autofitting = False

    def _slack(self) -> int:
        """Space the layout has handed to the item that absorbs leftovers — the
        trailing spacer, or the per-segment list above its own sizeHint. Shrinking
        the window by it is what lets the accordion fold back up; without it, one
        'Expand all' would leave the window tall for the rest of the session."""
        if self._spacer is not None:
            return self._spacer.geometry().height()
        if self._seg_section is not None:
            return max(0, self._seg_section.height()
                       - self._seg_section.sizeHint().height())
        return 0

    def done(self, r):
        """Remember which groups were left open (per-user, not per-case), so the
        one group an engineer keeps reopening is open next time."""
        from app.services import ui_state
        ui_state.save_section_states(self._STATE_SCOPE, self._sections)
        super().done(r)

