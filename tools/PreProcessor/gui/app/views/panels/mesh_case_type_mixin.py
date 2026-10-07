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
from PyQt6.QtWidgets import QFileDialog, QFormLayout, QHBoxLayout, QWidget

from app.models.mesh_config import MeshConfig
from app.services import case_type_apply, case_type_picker
from app.services.case_type_reference import CaseTypeError
from app.services.logging_setup import get_logger
from app.utils import align_form_labels, block_signals, make_button
from app.views.panels.case_type_roles_table import CaseTypeRolesTable

logger = get_logger(__name__)


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

        # What the MODEL holds for roles the table below is not showing — a case
        # type the operator looked at and moved away from. Kept so switching
        # case types does not lose the assignment made for the other one.
        self._case_type_roles_held = {}
        # The roles the chosen case type needs on THIS drawing, and the one
        # action that applies it (#170). Below the read-out because the read-out
        # says what the case type has an opinion about and this says what it
        # needs from the operator before it may act on one.
        self.case_type_roles_table = CaseTypeRolesTable()
        self._layout.addWidget(self.case_type_roles_table)
        row = QWidget()
        hb = QHBoxLayout(row)
        hb.setContentsMargins(0, 0, 0, 4)
        hb.addStretch()
        self.apply_case_type_btn = make_button("Apply Case Type…", "#1e3346")
        self.apply_case_type_btn.setToolTip(
            "Write this case type's settings into the configuration, fitted to "
            "your geometry's own scale, and bind its topology family to the "
            "curves you assigned above. The boundary-layer first cell height is "
            "physical rather than geometric, so it is never applied without "
            "being confirmed. One undo step; nothing is written if anything is "
            "refused.")
        hb.addWidget(self.apply_case_type_btn)
        self._layout.addWidget(row)
        self.apply_case_type_btn.clicked.connect(self.apply_case_type_requested)

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
            # The moment a pick lands on a real row is the moment the value to
            # fall back to from `Browse…` changes, and it is the ONE place that
            # is true outside a programmatic write.
            case_type_picker.remember_choice(w)
            self._refresh_case_type_summary()
            return
        previous = case_type_picker.read_choice(w)
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

    def _wire_case_type_refresh(self):
        """Refresh the read-out on EVERY field edit, not only on a `set_config`.

        THE DEVIATION HALF IS LIVE OR IT IS A LIE. Without this the read-out was
        rendered at construction, at `set_config` and on a pick — so an operator
        who moved an owned field went on reading "None of them has been moved on
        this run", which is the exact silence #169 exists to close, one layer in.
        Measured on the live panel before the fix: with the case type owning
        `bl_initial_thickness = 0.001`, typing 0.05 moved the model and left the
        read-out word for word unchanged.

        WIRED LAST, from the panel's `__init__`, because this traverses widgets
        every section builder has to have created first — the same position
        `_apply_unit_suffixes` holds, and for the same reason. The BL rows are
        wired HERE too and the ORDER is load bearing: `_wire_bl_widgets` ran
        earlier, so its handler has already written `_global_bl` by the time this
        slot reads the configuration back.

        The picker's own two rows are skipped: `_on_case_type_picked` already
        refreshes, and a second call would be the Browse dialog's own emit coming
        round twice.

        PER KEYSTROKE, which is affordable and is MEASURED rather than assumed
        — and the figure moved with #170, so the old sentence here ("a small
        JSON load plus `case_type_scale.fit`") is now wrong and is corrected
        rather than left standing. With no case type chosen `summary` returns a
        constant. With one, this slot now costs the summary AND a whole
        `case_type_apply.plan`: a second case-type load, `case_type_scale.plan`
        and a binding context with `guess_roles`' area ranking over it.
        Measured on a drawing of two 2,000-point outlines: **1.3 ms** for the
        plan, 0.7 ms for the context alone, 0.2 ms for the summary. That is the
        same cost class — and the same house pattern — as
        `_refresh_topology_counts`, which already builds a binding context per
        keystroke behind `Family.binds`.
        """
        from app.views.panels.field_widgets import wire_specs
        from app.views.panels.mesh_bl_field_specs import PANEL_BL_SPECS
        from app.views.panels.mesh_field_specs import MESH_SPECS
        from app.services.topology_field_specs import TOPOLOGY_SPECS
        mine = {"case_type_file", "case_type_summary"}
        for table in (MESH_SPECS, PANEL_BL_SPECS, TOPOLOGY_SPECS):
            wire_specs(self, [sp for sp in table if sp.attr not in mine],
                       self._on_field_edited)

    def _on_field_edited(self, *_args):
        """A field changed: re-render the read-out. A NAMED slot, not a lambda.

        Named for two reasons. Qt hands an edit signal its own payload — a float
        from a spin box, an index from a combo — which `_refresh_case_type_summary`
        would read as its `cfg` argument and then describe a configuration nobody
        has; and a lambda cannot be DISCONNECTED by a gate, so injection D in
        `tests/test_case_type_picker.py` could not restore the defect this wiring
        closes.
        """
        self._refresh_case_type_summary()

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
        self._refresh_case_type_roles(cfg)

    # ── the roles ────────────────────────────────────────────────────────
    def _refresh_case_type_roles(self, cfg):
        """Show the roles the chosen case type needs on `cfg`'s own drawing.

        ONE PLAN, built here and read by the table — the same shape
        `_refresh_topology_counts` has, and the same per-keystroke cost class:
        it builds a binding context, which that one already does behind
        `Family.binds`. The table itself rebuilds only when the SHAPE changes,
        so the keystroke cost is this plan and not a widget teardown.

        A case type that will not load leaves the table saying there is nothing
        to assign rather than raising into a keystroke handler: the picker's
        read-out above has already said WHY in the loader's own words, and a
        second copy of that sentence here would be a second wording of it.
        """
        table = getattr(self, "case_type_roles_table", None)
        if table is None:
            return
        try:
            plan = case_type_apply.plan(cfg)
        except (CaseTypeError, OSError) as exc:
            logger.debug("no role plan for this configuration: %s", exc,
                         exc_info=True)
            plan = None
        self._case_type_roles_held = dict(
            getattr(cfg, "case_type_roles", None) or {})
        table.set_plan(plan, self._case_type_roles_held)
        # ENABLED WHENEVER A CASE TYPE IS CHOSEN, not when a plan was built. A
        # plan fails for reasons the operator can act on and is owed in words —
        # the file will not load, or its characteristic length cannot be
        # measured on this drawing — and a button that silently greys out says
        # none of them. Pressing it produces the refusal, naming which.
        self.apply_case_type_btn.setEnabled(bool(case_type_picker.chosen(cfg)))

    def _read_case_type_roles(self, cfg):
        """Author `cfg.case_type_roles` from the table. The panel's own residue.

        A role the table does not SHOW keeps whatever the model already held —
        switching case types must not lose an assignment made for the other one,
        which is `case_type_apply.ApplyPlan.ignored`'s rule on the reading side.
        `_loading` is not consulted: `get_config` is never called mid-population
        (`_refresh_case_type_summary` passes the configuration being written
        instead), and the table's own values are whatever was last selected
        either way.
        """
        table = getattr(self, "case_type_roles_table", None)
        if table is None:
            return
        shown = table.shown_roles()
        kept = {r: v for r, v in (self._case_type_roles_held or {}).items()
                if r not in shown}
        kept.update(table.read())
        cfg.case_type_roles = kept
