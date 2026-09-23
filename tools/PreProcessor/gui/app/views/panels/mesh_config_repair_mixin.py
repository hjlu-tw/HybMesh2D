"""Repairing a broken template binding FROM THE PANEL, not from the file (#138).

#137 made a binding that no longer resolves a REFUSAL with the edge named, which is
correct and is not enough: it leaves the user holding an error message and a JSON
document they were never meant to open. And the moment a binding breaks is precisely
the moment they know the answer — they are the one who just went back to the CAD stage
and cut one more segment into the geometry the topology is bound to.

So this mixin turns each :class:`~app.services.topology_binding.BrokenBinding` the
family reports into ONE ROW: a sentence naming the edges, the geometry and the segment
they were bound to, and a dropdown of the segments that geometry carries now. Choosing
one writes the repaired list into the binding row the family named, which is a normal
model edit from there on — persisted with the project, carried to the global config by
the panel->model sync, and undoable through the same funnel as every other panel edit.

THE ROWS ARE A POOL AND ARE NEVER DESTROYED. A repair is made from inside a combo's own
signal, and the refresh it triggers arrives while that signal is still on the stack —
so rebuilding by deleting and recreating the rows would delete the widget that is
mid-emit. Reusing a fixed pool (grown as needed, the surplus hidden) makes the whole
path synchronous, which is also what lets a headless gate drive it without an event
loop. The alternative, deferring the rebuild with a zero-timer, would have made every
gate that touches this section pump events.

WHICH ROWS EXIST IS THE FAMILY'S ANSWER, ASKED THROUGH THE REGISTRY
(``topology_model.broken_bindings``). The panel decides nothing about which edges bind
or which segments may replace one — that is #133's decision and it stays in the family,
for the same reason the projection is a pure function of the model.
"""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

from app.utils import COMBO_STYLE, block_signals
from app.services.topology_field_specs import TOPOLOGY_SPECS

#: The flag's own styling. Amber rather than red: the run is refused, but the state is
#: repairable in place and the panel is offering the repair in the next line down.
_FLAG_QSS = "color:#e8b45a; font-size:10px;"

_INTRO = ("This topology binds to segments the geometry no longer carries, so the run "
          "is refused. Re-point each one:")


class TopologyRepairBox(QWidget):
    """The flagged-binding rows, and the dropdown that repairs one.

    ``panel_edited`` is the convention ``undo_ctrl._wire_widget_edits`` documents for a
    COMPOSITE control that builds its own children: that traversal runs once, when the
    panel is constructed, so a combo created (or re-purposed) later is invisible to it
    and an edit made through one would reach neither the global model nor the undo
    recorder. Declaring the signal is what brings this widget back inside the funnel.
    """

    #: "the user changed something in me" — read by `undo_ctrl._wire_widget_edits`.
    panel_edited = pyqtSignal()
    #: ``(BrokenBinding, chosen segment id)``. Emitted BEFORE ``panel_edited`` in the
    #: same handler, because the funnel reads the panel back: the model has to already
    #: hold the repair by the time the sync runs.
    repair_requested = pyqtSignal(object, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(3)
        self._intro = QLabel(_INTRO)
        self._intro.setWordWrap(True)
        self._intro.setStyleSheet(_FLAG_QSS)
        lay.addWidget(self._intro)
        self._layout = lay
        self._rows: list[tuple[QLabel, QComboBox]] = []
        self._broken: tuple = ()
        self._populating = False
        self.setVisible(False)

    def show_broken(self, broken) -> None:
        """Show one row per broken binding; hide the box when there are none."""
        self._broken = tuple(broken)
        self._populating = True
        try:
            while len(self._rows) < len(self._broken):
                self._add_row()
            for i, (lbl, combo) in enumerate(self._rows):
                if i >= len(self._broken):
                    lbl.setVisible(False)
                    combo.setVisible(False)
                    continue
                b = self._broken[i]
                lbl.setText("⚠  " + b.label())
                lbl.setToolTip(f"{b.geom}  (stored list: {b.field}, position "
                               f"{b.pos})")
                lbl.setVisible(True)
                with block_signals(combo):
                    combo.clear()
                    combo.addItem("re-point to…", None)
                    for sid in b.choices:
                        combo.addItem(f"segment {sid}", int(sid))
                    combo.setCurrentIndex(0)
                combo.setEnabled(bool(b.choices))
                combo.setVisible(True)
            self.setVisible(bool(self._broken))
        finally:
            self._populating = False

    def _add_row(self) -> None:
        lbl = QLabel()
        lbl.setWordWrap(True)
        lbl.setStyleSheet(_FLAG_QSS)
        combo = QComboBox()
        combo.setStyleSheet(COMBO_STYLE)
        # The tooltip says what the choice DOES, not just what it names: a ring
        # covers the whole outline, so picking a segment for the flagged edge decides
        # where the ring starts and the rest follows. A user who expected only this
        # one edge to move would otherwise read the new list as a bug.
        combo.setToolTip(
            "The segments this geometry carries now. Choosing one puts the flagged "
            "edge on it and walks the ring on from there, so the binding becomes "
            "this geometry's own segments in its own order, started where you say. "
            "They are still stored as stable ids, never as positions.")
        idx = len(self._rows)
        combo.currentIndexChanged.connect(lambda i, r=idx: self._on_pick(r, i))
        self._layout.addWidget(lbl)
        self._layout.addWidget(combo)
        self._rows.append((lbl, combo))

    def _on_pick(self, row: int, index: int) -> None:
        # Index 0 is the prompt, not a segment: a combo has to have a current item,
        # and the first real choice must be a change the user can see themselves make.
        if self._populating or index <= 0 or row >= len(self._broken):
            return
        seg = self._rows[row][1].itemData(index)
        if seg is None:
            return
        self.repair_requested.emit(self._broken[row], int(seg))
        self.panel_edited.emit()


class MeshConfigRepairMixin:
    """The binding-repair box, its refresh and the write it makes.

    Composed into ``MeshConfigPanel``; ``self.sec_topology`` and the binding row
    widgets come from ``MeshConfigBuildMixin``, which builds the section this box is
    appended to.
    """

    def _build_topology_repair(self):
        """Append the repair box under the template rows. Called by the section."""
        self._topo_repair = TopologyRepairBox()
        self._topo_repair.repair_requested.connect(self._on_topology_repair)
        self.sec_topology.add_widget(self._topo_repair)
        # Only a transition from "nothing broken" to "something broken" expands the
        # section, and only once: re-expanding on every refresh would fight a user who
        # collapsed it while working through a list of repairs.
        self._topo_repair_flagged = False

    def _refresh_topology_repair(self, model, ctx):
        """Ask the family what is broken and show it.

        Called from ``_refresh_topology_counts``, which is the ONE place that already
        holds both a template model read back from the widgets and the binding context
        for this case — and which runs on every template keystroke AND on every
        ``set_config``. That is what makes the flag clear when the cause is removed by
        other means: undoing the CAD edit puts the segment back, re-entering the Mesh
        stage pushes the configuration, and the ids resolve again with nothing here
        knowing why. The binding cache is keyed by the file's own mtime and size, so a
        geometry rewritten in between is re-read rather than remembered.
        """
        box = getattr(self, "_topo_repair", None)
        if box is None:
            return
        from app.services import topology_model
        broken = topology_model.broken_bindings(model, ctx)
        box.show_broken(broken)
        if broken and not self._topo_repair_flagged:
            self.sec_topology.expand()
        self._topo_repair_flagged = bool(broken)

    def _on_topology_repair(self, b, seg: int):
        """Re-point ``b``'s position at segment ``seg`` in the row that holds it.

        THE WRITE GOES THROUGH THE FAMILY'S OWN WRITER and lands in the binding row's
        widget, not in a private store: that row is the field-spec row the panel->model
        sync already reads, so a repair is persisted, undone and projected by exactly
        the machinery every other template parameter uses. Nothing here is a second
        home for a binding.

        The panel supplies the POSITION and the CHOSEN SEGMENT and nothing else; what
        the rest of the list becomes is `repair_binding`'s answer, and it is the
        geometry's own segments rotated to honour that choice — because a valid
        binding is a rotation of that list and nothing else is. A view that wrote the
        replacement itself would be deciding a topology rule.

        The row stays READ-ONLY (#133: which edges bind is the template's decision),
        which is why the repair is a dropdown of that geometry's own segments rather
        than the user editing the list.
        """
        from app.services import topology_ogrid_binding
        attr = self._topology_attr_for(b.field)
        w = getattr(self, attr, None) if attr else None
        if w is None:
            return
        text = topology_ogrid_binding.repair_binding(b.choices, b.pos, seg)
        if text:
            w.setText(text)

    @staticmethod
    def _topology_attr_for(field: str) -> str:
        """The panel attribute of the row authoring ``field``, from the TABLE.

        Not a hand-written map: the pairing of a model field to its widget is what the
        field-spec table already declares, so reading it here keeps the repair pointed
        at whatever row currently authors that field.
        """
        for sp in TOPOLOGY_SPECS:
            if sp.model_name == field:
                return sp.attr
        return ""
