"""The window's half of APPLYING a case type (#170, parent #158).

#169 gave the operator a case type to PICK and a verdict to read, and said in as
many words that picking selects what JUDGES and applies nothing — because every
part of applying needs ROLES. This controller is the other half: the action
behind the Mesh panel's "Apply Case Type…" button.

NOTHING HERE DECIDES ANYTHING. The whole act — fitting the overlay to this
drawing's scale, refusing an unconfirmed role or first cell height, binding the
family to the operator's own segments and asking it whether it can fill the
drawing — is `services/case_type_apply.py`, Qt-free and gated headlessly. What is
here is the three things a window can do and a service cannot: ask the
confirmation, point at the offending curve, and put the result on the undo stack.

ONE UNDO STEP. The service returns a fitted configuration and this pushes it
whole, so Ctrl+Z after an apply restores every field the case type moved at once
— which is what makes #158's story 21 ("a starting point, not a cage") true in
the direction that matters: an operator who applies one and dislikes it is one
keystroke from their own numbers, not twenty edits.

THE REFUSAL POINTS AT THE CURVE. `case_type_apply.PreflightRefused` carries the
family's own `Refusal` rows, and `_draw_preflight_refusal` — the mesh stage's
diagnostics mixin, which already draws exactly these at Generate time — is what
draws them. That is #158's stories 25-27 reached BEFORE anything is pressed
rather than after a generation is attempted, and it is deliberately the same
overlay: two ways of drawing one refusal would be two things to keep in step.
"""
from __future__ import annotations

from app.services import case_type_apply
from app.services.case_type_reference import CaseTypeError
from app.services.logging_setup import get_logger
from app.utils import report_info, report_warning
from app.views.case_type_apply_dialog import CaseTypeApplyDialog

_log = get_logger(__name__)


class CaseTypeApplyControllerMixin:
    """Apply the chosen case type to this project's own configuration."""

    def apply_case_type(self):
        """The "Apply Case Type…" action, start to finish.

        Reads the panel rather than ``global_mesh_config`` so an edit made in
        the same breath as the apply is included: the panel is what the operator
        is looking at, and the sync that copies it into the model is scheduled
        rather than immediate.
        """
        panel = self.main_window.mesh_config_panel
        cfg = panel.get_config()
        try:
            plan = case_type_apply.plan(cfg)
        except (CaseTypeError, OSError) as exc:
            # A failed READ: the file is missing, malformed, or nothing is
            # picked. A WARNING by `gui-seams.md`'s grading, never the
            # Critical tier -- NOTHING on any path of this action is ever at
            # risk, which is what Critical is for.
            report_warning(self.main_window, "Apply Case Type",
                           "This case type cannot be applied.",
                           detail=str(exc))
            return
        # THE ROLES ARE ANSWERED BEFORE THE DIALOG OPENS, not inside it. They are
        # a persistent assignment the operator makes in the panel — the table is
        # right there, under the picker — so a refusal about one sends them back
        # to a control they can see, where a role combo buried in a modal would
        # be a second place to assign the same thing.
        if not plan.ready():
            # A PRECONDITION, and nothing broke: `report_info`'s definition.
            report_info(
                self.main_window, "Apply Case Type",
                "Assign the roles this case type needs before applying it.",
                detail="\n".join(
                    [g.describe() for g in plan.unconfirmed_roles()]
                    + list(plan.problems())))
            return
        dlg = CaseTypeApplyDialog(self.main_window, plan, cfg)
        if not dlg.exec():
            self.log("Apply case type: cancelled, nothing was changed.")
            return
        try:
            applied = case_type_apply.apply(plan, cfg, dlg.confirmed())
        except case_type_apply.PreflightRefused as exc:
            # The family cannot fill this drawing with the curves it was given.
            # Shown, pointed at, and NOTHING written — the configuration the
            # operator had is exactly as it was.
            self.log_report("[ERROR] " + str(exc))
            self._draw_preflight_refusal(cfg, exc.refusals)
            # Graded `[ERROR]` in the LOG, the way `mesh_gen_diag_ctrl` grades
            # the same refusal at Generate time, and shown as INFORMATION: it
            # is a precondition of the drawing, and nothing was written.
            report_info(self.main_window, "Apply Case Type",
                        "This case type's topology cannot work with the "
                        "curves you assigned. Nothing was changed.",
                        detail=str(exc))
            return
        except (CaseTypeError, OSError) as exc:
            report_warning(self.main_window, "Apply Case Type",
                           "This case type was refused. Nothing was changed.",
                           detail=str(exc))
            return
        self._commit_applied_case_type(plan, applied)

    def _commit_applied_case_type(self, plan, applied):
        """Put the fitted configuration into the panel, undoably, and say what moved.

        ONE UNDO STEP, through the project recorder's own mechanism rather than
        a second one beside it: the state is captured BEFORE the push, the push
        itself goes through `push_panel_config` (which suppresses recording, or
        the twenty `set_config` signals would each look like a user edit), and
        the captured state is then handed back to `flush_project_snapshot` as
        the burst to measure against. Writing a command by hand here would be a
        second author of `UpdateProjectStateCmd` and a second place for its
        label to drift.
        """
        panel = self.main_window.mesh_config_panel
        # THE REFUSAL OVERLAY GOES WITH THE REFUSAL. A previous attempt may have
        # drawn one; leaving it up after a successful apply points at a curve
        # that is now fine, which `mesh_gen_diag_ctrl` names as worse than no
        # overlay. That mixin owns the flag, so this clears OUR OWN mark only
        # and cannot wipe a selection somebody else made.
        self._clear_preflight_highlight()
        before = self._project_config_state()
        self.global_mesh_config = applied.config
        self.push_panel_config(panel, applied.config)
        self.sync_mesh_layers_panel()
        # AFTER the push, because `suppress_project_undo` clears a pending burst
        # on the way out — setting it first would have it dropped and the apply
        # would silently not be undoable, which is this method's whole subject.
        self._project_undo_before = before
        self.flush_project_snapshot()
        self.log("Applied case type '%s':" % plan.case_type.name)
        for line in applied.describe():
            self.log("    " + line)
        if not applied.changes:
            # Said rather than passed over in silence: a case type with an empty
            # overlay is a legitimate document (it may carry only thresholds),
            # and an action that logs nothing reads as an action that failed.
            self.log("    it has an opinion about no configuration field.")
        _log.debug("case type %r applied: %d change(s), %d binding(s)",
                   plan.case_type.name, len(applied.changes),
                   len(applied.bindings))
        # NO SUCCESS DIALOG. The modal the operator just accepted listed every
        # `was -> now` row and every binding, so a second one saying the same
        # thing is a box to dismiss rather than information — `load_mesh_config`
        # beside it logs and shows nothing, which is the house pattern for a
        # completed action. The REFUSALS above all show one, because those are
        # the paths where nothing the operator asked for happened.
