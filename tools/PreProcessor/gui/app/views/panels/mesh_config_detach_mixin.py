"""Detaching the template into a hand-maintained file, from the panel (#139).

The model half is ``services/topology_detach.py`` and everything decided about the
transition lives there. This file is the two things only a view can supply — WHERE
the document goes (a Save dialog) and the user's consent to discard what they edited
— plus the surface the ticket actually asks for: once detached, the template section
is a READ-ONLY SUMMARY that still names the family and the parameters that produced
the file, rather than disappearing or, worse, staying editable while its edits no
longer reach anything.

THE WRITE GOES INTO THE ROWS, exactly as #138's binding repair does. Detaching sets
the ``topo_detached`` checkbox and the ``mesh_topology_file`` line edit; those two
rows are what the panel->model sync reads, so the state is carried to the global
config, into the project file and onto the undo stack by the machinery every other
field uses. Nothing here keeps a private copy of "am I detached" — a second home for
that flag would be free to disagree with the one the projection asks.

THE CHECKBOX IS THE AUTHOR AND THE BUTTONS ARE THE CONTROLS, which is why the box
below declares no ``panel_edited``: a ``QCheckBox`` emits ``toggled`` for a
programmatic write too, and ``undo_ctrl._wire_widget_edits`` connects that signal, so
setting it IS the edit reaching the funnel. (The line edit is written in the same
breath and emits only ``textChanged``, which that traversal deliberately ignores —
one sync reads the whole panel, so the pair lands together.) A plain ``QPushButton``
never emits ``toggled``, so the buttons themselves reach nothing, which is correct:
pressing one is not an edit until the row it writes says so.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.services import topology_detach
from app.services.logging_setup import get_logger
from app.services.topology_field_specs import TOPOLOGY_SPECS, TOPOLOGY_STATE_ROWS
from app.utils import confirm_destructive, make_button, report_error
from app.views.panels.field_widgets import set_spec_row_enabled

_log = get_logger(__name__)

#: The summary's own styling. Deliberately NOT the amber of a broken binding: this is
#: a state the user chose, not a refusal.
_SUMMARY_QSS = "color:#8a93ad; font-size:10px;"

_ATTACHED_HINT = (
    "This document is generated from the parameters above, every run. Detach it to "
    "take it over by hand — the parameters stay visible as a record of where the "
    "file came from.")


class TopologyDetachBox(QWidget):
    """The Detach / Re-attach controls, and the read-only summary when detached."""

    #: "the user asked to detach" / "...to re-attach". The mixin does the work; this
    #: widget knows nothing about models, paths or dialogs.
    detach_requested = pyqtSignal()
    reattach_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 2)
        lay.setSpacing(3)
        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet(_SUMMARY_QSS)
        # Selectable, because the one thing a user copies out of this block is the
        # path to the file they now have to go and edit.
        self._summary.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self._summary)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        self.detach_btn = make_button("Detach to a file…", "#181b2a",
                                      border="#2d3356", hover_border="#5a9ad4")
        self.detach_btn.setToolTip(
            "Write the generated document to a file you maintain by hand, and stop "
            "regenerating it. The family and its parameters stay on screen as a "
            "record of where the file came from.")
        self.detach_btn.clicked.connect(self.detach_requested)
        self.reattach_btn = make_button("Re-attach to the template…", "#181b2a",
                                        border="#2d3356", hover_border="#5a9ad4")
        self.reattach_btn.setToolTip(
            "Generate the document from the parameters again. Edits made to the "
            "detached file are discarded; the file itself is left on disk.")
        self.reattach_btn.clicked.connect(self.reattach_requested)
        row.addWidget(self.detach_btn)
        row.addWidget(self.reattach_btn)
        row.addStretch(1)
        lay.addLayout(row)
        self.setVisible(False)

    def show_state(self, *, has_family: bool, detached: bool, summary: str) -> None:
        """Show the state ``(has_family, detached)`` describes.

        Hidden whole for a configuration with no template: there is nothing to
        detach, and a Detach button that refuses when pressed is worse than none.
        """
        self.setVisible(bool(has_family))
        self.detach_btn.setVisible(bool(has_family) and not detached)
        self.reattach_btn.setVisible(bool(detached))
        self._summary.setText(summary if detached else _ATTACHED_HINT)

    def summary_text(self) -> str:
        """What the summary currently reads — the gate's window onto this panel."""
        return self._summary.text()


class MeshConfigDetachMixin:
    """Build the detach box, keep it in step, and run the two transitions.

    Composed into ``MeshConfigPanel``; ``self.sec_topology`` and every template row
    come from ``MeshConfigBuildMixin``, which builds the section this is appended to.
    """

    def _build_topology_detach(self):
        """Append the detach box at the foot of the template section."""
        self._topo_detach = TopologyDetachBox()
        self._topo_detach.detach_requested.connect(self._on_topology_detach)
        self._topo_detach.reattach_requested.connect(self._on_topology_reattach)
        self.sec_topology.add_widget(self._topo_detach)

    def _refresh_topology_detach(self, model, cfg=None):
        """Show the state, and make the template rows read-only when detached.

        Called from ``_refresh_topology_counts``, the one place that already holds a
        template model read back from the widgets and runs on every template
        keystroke AND every ``set_config`` — the same hook #138's repair flag uses,
        and for the same reason: a second traversal is a second chance to cover a
        different set of rows.

        GREYING THE ROWS IS THE TICKET'S OWN REQUIREMENT, not decoration. An
        editable panel whose edits no longer take effect is a control that does
        nothing; the parameters are kept on screen to say where the file came from,
        so they must look like a record and not like an input.
        """
        box = getattr(self, "_topo_detach", None)
        if box is None:
            return
        detached = topology_detach.is_detached(model)
        for spec in TOPOLOGY_SPECS:
            # The state row itself is never re-enabled: it is a read-out, and
            # `set_spec_row_enabled` would happily undo what the builder declared.
            if spec.attr in TOPOLOGY_STATE_ROWS and spec.attr != "topo_family":
                continue
            set_spec_row_enabled(self, spec.attr, not detached)
        box.show_state(has_family=bool(getattr(model, "family", "")),
                       detached=detached,
                       summary=topology_detach.summary(model, cfg))

    # ── the two transitions ────────────────────────────────────────────────

    def _on_topology_detach(self):
        """Write the document where the user says, and stop generating it."""
        from app.services import topology_binding
        cfg = self.get_config()
        model = cfg.topology
        if not model.names_a_family():
            # Unreachable from the button, which is hidden without a family; kept
            # because the handler is also the gate's entry point.
            return
        path = self._ask_detach_path(topology_detach.default_path(cfg))
        if not path:
            return
        try:
            written = topology_detach.detach(
                model, cfg, path, topology_binding.context_for_config(cfg))
        except (OSError, ValueError) as exc:
            # A family that cannot BUILD (a binding the geometry no longer carries)
            # and a file that cannot be WRITTEN are one outcome for the user: the
            # topology was not detached and the configuration is untouched, which is
            # what `detach` guarantees by building before it writes.
            _log.warning("detach refused: %s", exc, exc_info=True)
            report_error(self, "Could not detach the topology",
                         f"{exc}\n\nThe topology is still generated from the "
                         f"template, and nothing was written.")
            return
        self._write_detached_state(cfg.mesh_topology_file, True)
        self._log_detach(f"[INFO] topology detached to {written} — it is no longer "
                         f"generated from the template.")

    def _on_topology_reattach(self):
        """Discard the file's edits and go back to generating, having said so."""
        cfg = self.get_config()
        if not topology_detach.is_detached(cfg.topology):
            return
        if not self._confirm_reattach():
            return
        topology_detach.reattach(cfg.topology, cfg)
        self._write_detached_state("", False)
        self._log_detach("[INFO] topology re-attached to its template — the "
                         "document is generated again on every run.")

    def _write_detached_state(self, topology_file: str, detached: bool):
        """Push the two changed values into the rows that author them.

        ORDER IS LOAD BEARING. The line edit is written first and the checkbox
        second, because the checkbox's ``toggled`` is what reaches
        ``undo_ctrl._wire_widget_edits``' slot — one ``on_panel_edited``, which reads
        the WHOLE panel back, so both values land in the global config together and
        as ONE undo step. Writing the checkbox first would sync a state whose path
        row still held the previous run's answer.
        """
        w = getattr(self, "mesh_topology_file", None)
        if w is not None:
            w.setText(topology_file)
        box = getattr(self, "topo_detached", None)
        if box is not None:
            box.setChecked(bool(detached))
        # The read-out, the greying and the canvas overlay all hang off the template
        # handler, which a programmatic write does not otherwise reach.
        self._on_topology_edited()

    # ── the two things only a view can answer ──────────────────────────────

    def _ask_detach_path(self, default: str) -> str:
        """Where the detached document goes. Overridden headlessly by the gate."""
        from PyQt6.QtWidgets import QFileDialog
        os.makedirs(os.path.dirname(default), exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "Detach topology to a file", default,
            "Topology (*.json);;All Files (*)")
        return path or ""

    def _confirm_reattach(self) -> bool:
        """Consent to discard the file's edits, stated plainly before anything runs.

        ``confirm_destructive`` rather than ``confirm``: the edits cannot be
        recovered, so the button is NAMED, Cancel is the default, and there is no
        ``headless_default`` to let an unattended path consent on the user's behalf.
        """
        return confirm_destructive(
            self, "Re-attach topology", topology_detach.REATTACH_QUESTION,
            action_label="Re-attach and regenerate",
            informative=topology_detach.REATTACH_WARNING) is not None

    def _log_detach(self, message: str):
        """Say what happened, through the user-log service if this panel has one."""
        from app.services import user_log
        user_log.log(message)
