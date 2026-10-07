"""The case-type picker and its read-out, at the top of the Mesh panel (#169).

Until this section existed the whole case-type workflow was headless:
`case_type.active_case_type()` had exactly one call site in the repo, no
controller, view or worker read `HYBMESH_CASE_TYPE`, and with the variable unset
a Trial printed nothing at all. Everything behind that silence was already built
and gated — the four-state verdict and its advice (#160), the config overlay and
the deviation marking (#162), Trial and Generate (#166), the reference meshes a
threshold rests on (#168) — and the deviation list in particular was COMPUTED on
the GUI path, carried on every `Verdict`, written into the commit sidecar and
shown to nobody.

ABOVE THE UNIT ROW, and not collapsible. The unit row is first because it says
what every number below it means; this is first because it says who is going to
read them. Both are interpretive keys rather than values, and a key you have to
expand a section to find is one an operator never discovers — which is the exact
failure this ticket exists to close.

IT SELECTS WHAT JUDGES, NOT WHAT RUNS. Nothing here writes a case type's fields
into the configuration, scales its sizes or binds its family: that is
`apply_case_type.py`'s job, every part of it needs ROLES, and roles are #170.
The read-out below the combo is therefore a comparison and not a promise — it
names the fields the case type has an opinion about and marks the ones this run
has moved, which is #158's stories 24 and 20.

THE RULES, including why a file that will not load is shown DISABLED rather than
omitted and why a reopened case does not change the choice, are
`.claude/rules/gui-dispositions.md`; what the panel OWNS is only the widgets.
Every sentence the operator reads comes from `services/case_type_picker.py`, the
Qt-free half, for `gui-seams.md`'s reason: a panel that worded the summary itself
would be free to describe a comparison differently from the verdict that acts on
it.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFileDialog, QFormLayout, QWidget

from app.models.mesh_config import MeshConfig
from app.services import case_type_picker
from app.utils import align_form_labels, block_signals


class MeshConfigCaseTypeMixin:
    """Builds the case-type row + summary, and keeps both in step with the model."""

    def _build_case_type_section(self):
        holder = QWidget()
        form = QFormLayout(holder)
        form.setContentsMargins(0, 0, 0, 2)
        # The two rows come from MESH_SPECS like every other field, so the picker
        # gets panel->model sync, undo and dirty detection for free — the choice
        # is a `MeshConfig` field, and `project_state_ctrl._collect_project_state`
        # is `to_dict()`.
        self._spec_rows(form, "casetype")
        align_form_labels(form, 130)
        self._layout.addWidget(holder)

        self._populate_case_types()
        self.case_type_file.currentIndexChanged.connect(self._on_case_type_picked)
        # Against a FRESH config carrying only the picker's own value, because at
        # construction there is no panel to read: this section is built before the
        # unit row, so `get_config()` here would reach a `unit_selector` that does
        # not exist yet. The two agree by construction — nothing else on the panel
        # can have been touched — and the first real `set_config` replaces it.
        seed = MeshConfig()
        seed.case_type_file = case_type_picker.read_choice(self.case_type_file)
        self._refresh_case_type_summary(seed)

    # ── the list ─────────────────────────────────────────────────────────
    def _populate_case_types(self, keep: str | None = None):
        """Rebuild the combo: `(none)`, the catalogue, then `Browse…`.

        `keep` is the stored spelling to end up selected; ``None`` means "the one
        selected now", which is what makes this safe to call after a Browse. A
        value the catalogue does not hold is re-added by `write_choice`, so a
        file chosen through Browse and one whose file has gone both keep their
        place in the list rather than silently reverting to `(none)`.
        """
        w = self.case_type_file
        if keep is None:
            keep = case_type_picker.read_choice(w)
        with block_signals(w):
            w.clear()
            w.addItem(case_type_picker.NONE_LABEL, "")
            for entry in case_type_picker.catalogue(extra=[keep] if keep else []):
                w.addItem(entry.label, entry.stored)
                i = w.count() - 1
                w.setItemData(i, entry.why or entry.stored,
                              Qt.ItemDataRole.ToolTipRole)
                if not entry.loadable:
                    # SHOWN AND UNSELECTABLE, never omitted. "A case type the
                    # operator named and the tool quietly ignored is how a
                    # verdict goes missing" — dropping the row from the list is
                    # that silence, so the file is named and the reason is on it.
                    # `model().item(i)` is QComboBox's own QStandardItemModel.
                    item = w.model().item(i)
                    if item is not None:
                        item.setEnabled(False)
            w.addItem(case_type_picker.BROWSE_LABEL, case_type_picker.BROWSE)
            case_type_picker.write_choice(w, keep)

    # ── the choice ───────────────────────────────────────────────────────
    def _on_case_type_picked(self, *_args):
        """React to a pick: run Browse for the sentinel, else refresh the read-out.

        THE SENTINEL IS NEVER LEFT SELECTED and the previous choice comes back on
        Cancel — `Browse…` is a row the operator selects in order to leave it, and
        a picker sitting on it would be a configuration naming a path no loader
        can resolve. The restore is belt AND braces: `read_choice` answers with
        the last real selection whatever the combo shows, so even a `get_config()`
        landing while the modal dialog is open reports the configuration the
        operator actually has.

        NOTHING IS EMITTED HERE. `undo_ctrl._wire_widget_edits` already connects
        every `QComboBox.currentIndexChanged` on this panel to `on_panel_edited`,
        which syncs the model and schedules the undo snapshot; it is wired AFTER
        this handler, so by the time it runs the Browse has finished and the combo
        holds the final choice. `mesh_config_changed` would be the wrong signal
        besides — its listener reloads every geometry preview and re-reads every
        `.meta`, and picking a case type cannot have changed a geometry file
        (`.claude/rules/gui-topology.md` records the same finding for a template
        keystroke).
        """
        if getattr(self, "_loading", False):
            return
        w = self.case_type_file
        if w.currentData() != case_type_picker.BROWSE:
            self._refresh_case_type_summary()
            return
        previous = getattr(w, "_case_type_stored", "") or ""
        path, _filt = QFileDialog.getOpenFileName(
            self, "Select a case type",
            os.path.dirname(case_type_picker.resolve(previous)) or "",
            "Case types (*%s);;JSON (*.json);;All Files (*)"
            % case_type_picker.SUFFIX)
        chosen = (case_type_picker.stored_spelling(os.path.abspath(path))
                  if path else previous)
        # CHOOSING IT IS WHAT ADDS IT TO THE LIST, so the next pick does not need
        # the dialog again. A cancel rebuilds with the previous choice, which is
        # the same call with nothing new in it.
        self._populate_case_types(keep=chosen)
        self._refresh_case_type_summary()

    def _refresh_case_type_section(self, cfg):
        """Rebuild the list for `cfg` and re-render the read-out under it.

        The ONE call `_set_config_body` makes, so a reopened workspace gets both
        halves: a case type whose file has gone, or one browsed to in another
        session, is back on the list with its own row and its own reason — where
        `write_specs`'s plain insert would show it undecorated and selectable.
        """
        self._populate_case_types(keep=case_type_picker.chosen(cfg))
        self._refresh_case_type_summary(cfg)

    # ── the read-out ─────────────────────────────────────────────────────
    def _refresh_case_type_summary(self, cfg=None):
        """Show what the chosen case type owns and what this run has moved.

        `cfg` is the configuration to compare against; ``None`` means "read the
        panel", which is right everywhere but inside a population — `get_config()`
        from there would describe half-written widgets, so `_set_config_body`
        passes the configuration it is writing, exactly as `_refresh_topology_counts`
        is handed one.
        """
        lbl = getattr(self, "case_type_summary", None)
        if lbl is None:
            return
        if cfg is None:
            if getattr(self, "_loading", False):
                return
            cfg = self.get_config()
        lbl.setText(case_type_picker.summary(cfg))
