---
paths:
  - tools/PreProcessor/gui/app/services/case_type_apply*
  - tools/PreProcessor/gui/app/services/case_type_roles*
  - tools/PreProcessor/gui/app/services/case_type_guess*
  - tools/PreProcessor/gui/app/services/case_type_scale*
  - tools/PreProcessor/gui/app/controllers/case_type_apply_ctrl*
  - tools/PreProcessor/gui/app/views/case_type_apply_dialog*
  - tools/PreProcessor/gui/app/views/panels/case_type_roles_table*
---

# Applying a case type to the operator's own drawing

Loaded on demand when the apply service, the roles service, the pre-selection, the
characteristic length, the apply controller, the confirmation dialog or the roles table is
read — **seven globs**, the exact list being this file's own `paths:`. The SIXTEENTH rule file
and the SEVENTH taken because another was FULL: `gui-handoff.md`'s `services/case_type*`
already reaches four of them and was left with 444 characters of slack by #169, so #170's rules
could not go there. This file OVERLAPS rather than partitions — a session editing
`services/case_type_roles.py` loads BOTH, what a case type IS and what it owns being there and
what APPLYING one does being here — and one glob
(`views/panels/case_type_roles_table*`) is also `gui-panels-config.md`'s `views/panels/**`, the
field-spec mechanism being there and this widget's own rules here. **Rules only** — the
rationale (the measurements, the reversals and the named blind spots) is
`docs/design_notes/gui.md`. Read that note before overruling a rule here; when a rule changes,
update BOTH.

**This file rules on TWO modules outside its own globs**: `tools/PreProcessor/apply_case_type.py`,
the headless host, which no glob in any rule file reaches; and
`tools/PreProcessor/gui/app/models/mesh_config.py`, whose `case_type_roles` field is the
assignment and which is `gui-panels-config.md`'s by its `models/mesh_config*` glob. The tripwire
row in `CLAUDE.md` is the only thing that reaches the first one's reader.

## The act

**APPLYING IS ONE ACT WITH ONE INTERRUPT** (`services/case_type_apply.py`; #170, parent #158,
user stories 2-4, 21-24). Fields, roles and the family's own pre-flight are three questions
about ONE decision. `apply` writes everything or nothing; the one thing that interrupts is the
PHYSICAL parameter, and it interrupts by being REFUSED in the service rather than by a dialog a
host remembers to show. Gate: `tests/test_case_type_apply.py`.

- **NOTHING IS WRITTEN UNTIL EVERYTHING PASSES.** The overlay goes onto a DEEP COPY, the roles
  are bound into that copy and the pre-flight is asked of it; the caller gets the copy only if
  all three succeed. `case_type_fields.apply` mutates in place and `RolePlan.bind` mutates
  `config.topology`, so there is no version of this that touches the live object and is still
  all-or-nothing. The refusal is the moment the operator most needs their own numbers back.
- **EVERY PROBLEM AT ONCE, ACROSS THE SERVICES.** An unconfirmed role, a segment that does not
  resolve and an unconfirmed first cell height arrive in ONE refusal.
  `case_type_roles.RolePlan` states that rule WITHIN one service; this is it applied across
  three. The PRE-FLIGHT is the exception and cannot be otherwise — a family can only be asked
  whether it can fill a drawing once the bindings exist — so it is a second round by
  construction, never by choice.
- **A REFUSAL CARRIES THE CURVES, NOT ONLY THE SENTENCE.** `PreflightRefused` holds the
  `topology_preflight.Refusal` rows verbatim, so the window points at the offending curve
  through `mesh_gen_diag_ctrl._draw_preflight_refusal` — the same overlay Generate uses, never a
  second drawing of one refusal. That is what makes stories 25-27 reachable at APPLY time
  rather than only after a generation is attempted.
- **THE OWNED FIELDS ARE OVERWRITTEN, AND SAID FIRST.** The overlay is sparse, so only fields
  the case type has an opinion about move; every one is reported as `was -> now` BEFORE anything
  is written. KEEPING a field the operator had already moved was the rejected alternative: it
  makes a third state the deviation marking has no word for, where some owned fields are the
  case type's and some are not and nothing records which. Story 21 is answered the other way
  round — after applying, any field may be moved again and the read-out marks it MOVED.
- **ONE UNDO STEP**, through the project recorder's own mechanism: capture
  `_project_config_state()` BEFORE the push, push through `push_panel_config` (which suppresses
  recording, or twenty `set_config` signals each look like a user edit), then set
  `_project_undo_before` and call `flush_project_snapshot()`. The order is load bearing —
  `suppress_project_undo` CLEARS a pending burst on the way out, so setting it first makes the
  apply silently un-undoable.
- **A ROLE THIS CASE TYPE DOES NOT NEED IS KEPT, NOT USED, AND NAMED** (`ApplyPlan.ignored`).
  Switching case types changes which roles exist; dropping the others would lose the operator's
  work the moment they looked at a second case type, and passing them to `RolePlan.resolve`
  would make having looked at one an error.
- **`plan` READS THE CHOICE THROUGH `case_type_picker.for_config`**, so the precedence rule (the
  document in hand beats `HYBMESH_CASE_TYPE`) is reached and never re-spelled. "No case type is
  chosen" and "the one you picked will not load" are different refusals the operator is owed
  separately.
- **A RULER THAT CANNOT BE READ REFUSES, so `plan` calls `case_type_scale.plan` and NEVER `fit`.**
  The two differ in exactly the way that matters here: `fit` CATCHES the ruler's refusal and falls
  back to the authored numbers, which is right for a read-out comparing fields and wrong for an act
  that writes them — a case type authored on a 1 m body would put its 0.02 surface size on a 10 mm
  one. `apply_case_type.py` lets the same refusal through. The first cut called BOTH, and `fit`'s
  reason was dead on arrival (it is non-empty only when it catches what the line above had already
  let escape) while doubling the per-keystroke cost, `fit` re-running `plan` internally.
- **THE APPLY BUTTON IS LIVE WHENEVER A CASE TYPE IS CHOSEN, not when a plan was built.** Every
  reason a plan fails is one the operator can act on and is owed in words — the file will not load,
  the ruler cannot be measured on this drawing — and a button that greys itself out says none of
  them. Pressing it produces the refusal, naming which.

## The assignment

**THE ROLE ASSIGNMENT IS A MESH-CONFIG FIELD**, `MeshConfig.case_type_roles`, as
`{role: spec}` where a spec is `"geom"`, `"geom:1,2,3"` or `""` for "the pre-selection,
confirmed". That is `--role`'s own grammar verbatim, so the window and `apply_case_type.py`
express an assignment identically. Being a model field is what makes the rest fall out rather
than be arranged: it rides the panel->model sync, the undo snapshot, the `.hws` workspace and
the pipeline script's `mesh` section, all four being `MeshConfig.to_dict()`. The precedent is
`case_type_file` (#169).

- **PRESENT IS CONFIRMED; ABSENT IS NOT.** A role the operator has not answered for has NO
  entry, which is what `RolePlan.bind` already refuses on. The confirmation therefore stays a
  property of the service and not of any widget. A table that wrote `""` for an unassigned row
  would silently confirm the tool's own guess, which is the wrong guess reaching the mesher —
  a mesh that generates, exports and looks right with the far field's conditions on the body.
- **NOT `geom_roles`.** That is a different vocabulary (`seed` / `nobl` / `farfield` / `wall`)
  answering a different question and keyed by geometry FILE, while a family binds a LIST of
  segments. `services/case_type_roles.py` carries the argument; the two are not merged.
- **KEY-LESS, and UNOWNABLE for a second reason.** No `.dat` key, so
  `tests/test_gui_cpp_config_parity.py` is structurally blind to it — the mesher is handed the
  BINDINGS this produces, never the roles that produced them. And a case type cannot own it
  without an exclusion entry, because `case_type_fields.ownable_types` admits only scalars and
  this is a container: these are the operator's own curves, the one thing that cannot carry over
  from the authoring drawing.
- **THE PANEL AUTHORS IT BY HAND**, so it is declared in `MESH_EXTRA_AUTHORED` — a field
  `config_ownership` cannot see assigned lands in `PRESERVED_FIELDS`, and the sync would then
  discard every assignment the operator makes. A role the TABLE does not show keeps whatever the
  model held: `_read_case_type_roles` merges rather than replaces, which is `ApplyPlan.ignored`'s
  rule on the reading side.

## The table

**ASSIGNMENT IS A TABLE IN THE MESH PANEL, NEVER THE CANVAS**
(`views/panels/case_type_roles_table.py`). Clicking a curve was the other candidate and was
declined: this repo has a USER-REPORTED defect in which drawing order rather than click order
decided a result, and #158 excludes drawing-order conventions by name.

- **ASSIGNING AND CONFIRMING ARE ONE ACT.** There is no confirm checkbox. The combo's first real
  row IS the pre-selection, carrying `Guess.why` in its own text, and selecting it is the
  confirmation — `--role body`'s meaning exactly. A question whose only answer is "yes" is a
  control people learn to click.
- **THE PER-KEYSTROKE COST IS MEASURED, not assumed.** `_refresh_case_type_roles` builds a whole
  `ApplyPlan` on every field edit — a binding context plus `case_type_scale.plan` — on top of the
  read-out's own `fit` and `_refresh_topology_counts`' context. Measured on a drawing of two
  2,000-point outlines: **1.3 ms** per plan, against 0.7 ms for the context alone and 0.2 ms for
  the summary. That is the same cost class as `_refresh_topology_counts`, which is the house
  pattern it follows.
- **IT REBUILDS ON SHAPE, NEVER ON A KEYSTROKE.** `set_plan` compares a SHAPE KEY — the roles,
  the candidate geometries, the pre-selections — and touches no widget when nothing structural
  moved. The VALUES are deliberately not in that key: they are what the operator is editing.
- **AND A ROW THAT ALREADY SAYS THIS IS LEFT ALONE.** `_select` compares what the row would
  READ against what it is being asked to show and skips an agreeing row, because
  `QLineEdit.setText` resets the caret and the spec is normalised on the way through
  (`17,18` -> `17, 18`) — so without this the caret jumps on every character typed. Comparison
  is by VALUE (`_same_spec`), not by string.
- **THE TABLE REFRESHES ON THE GEOMETRY LIST TOO, and on the LIST'S MODEL rather than on a
  signal.** `#158`'s story 5 is that picking a case type before drawing and drawing before
  picking must come to the same place, and they did not: the role combos were built against an
  empty drawing and nothing rebuilt them when the curves arrived, so pick-then-draw left every
  row on `(not assigned)` with no candidate and no pre-selection while draw-then-pick worked.
  The geometry list is not a field-spec row, so neither table reaches it. `rowsInserted` /
  `rowsRemoved` on `geom_list_widget.model()` is the hook because `geom_files_changed` is
  emitted by the panel's OWN Browse and Remove handlers only — a geometry added by a controller
  would not reach it. Gated as an EQUALITY between the two orders (check 15), the defect being
  an asymmetry rather than a property of one of them, with a DISCONNECT injection because the
  subject is a wire.
- **`panel_edited` IS THE PROTOCOL**, not a traversal of children, and check 12 of the gate
  drives it through a live window rather than through `panel.get_config()`.
  `undo_ctrl._wire_widget_edits` connects that signal for a composite control that rebuilds its
  own rows (the restart chooser's, #31); a one-shot traversal at construction cannot reach a
  combo created after a family change, and such a row would edit the panel and never reach the
  model.
- **A GEOMETRY THE DRAWING NO LONGER CARRIES IS ADDED TO THE COMBO, not reset to unassigned** —
  the picker's own rule for a case type whose file has gone. Turning "your curve has moved" into
  "you never assigned one" is the silence this seam exists against.
- **EVERY SENTENCE THE OPERATOR READS COMES FROM THE QT-FREE SERVICES**
  (`case_type_roles.ROLE_MEANING`, `RoleSlot.describe`, `Guess.describe`), for `gui-seams.md`'s
  reason: a widget that worded a role itself could describe one differently from the service
  that binds it.

## The dialog

**THE CONFIRMATION SHOWS THE WHOLE ACT, NOT ONLY THE QUESTION**
(`views/case_type_apply_dialog.py`). It has to stop the operator anyway, so it is where the
`was -> now` list (story 24), the scale line and the bindings are shown rather than discovered
afterwards.

- **THE BOX IS PRE-FILLED AND EDITABLE** — `--confirm NAME=VALUE`'s grammar, where confirming
  and correcting are one act. `ApplyPlan.changes` folds the confirmations in, so the report
  describes the value that will actually be applied: a dialog that showed the OFFERED value and
  applied the corrected one would describe a different apply from the one it performs.
- **A `SciDoubleSpinBox`, NEVER A PLAIN ONE.** A y+~1 first cell on a chord-normalised body is
  routinely 1e-7, and this repo's standing rule is that a physical length is a sci box. Getting
  it wrong here would silently clamp the number in the one dialog whose whole subject is it.
- **HEADLESS IT ANSWERS CANCEL, AND IT ANSWERS FOR ITSELF.** `gui-seams.md` grants two
  bespoke-dialog exemptions from the graded helpers and records that both make the headless
  early-return themselves; this is the third and follows that rule rather than leaving the guard in
  its caller, where a second caller would have to remember it. Cancel is the only safe default: the
  question is a physical parameter nobody answered, and the service refuses an unanswered one — so
  an unattended path gets a refusal, never somebody else's Reynolds number in silence. Gated on the
  REAL dialog (check 13), because the live-window check swaps the class out and cannot see it.
- **THE THREE REFUSALS ARE GRADED, AND NONE OF THEM IS CRITICAL.** Nothing on any path of this
  action is ever at risk — that is what the deep copy buys — so `report_error` is wrong for all
  three. A case type that will not load is a failed READ (`report_warning`); an unassigned role and
  a pre-flight refusal are PRECONDITIONS with nothing broken (`report_info`), the latter graded
  `[ERROR]` in the LOG the way `mesh_gen_diag_ctrl` grades the same refusal at Generate time.
  **A SUCCESS SHOWS NO DIALOG AT ALL**: the modal the operator just accepted listed every row, and
  a second one saying the same thing is a box to dismiss — `load_mesh_config`'s own pattern.
- **THE ROLES ARE ANSWERED BEFORE THE DIALOG OPENS, not inside it.** They are a persistent
  assignment made in the panel, where the table is; a role combo buried in a modal would be a
  second place to assign the same thing.

## Named blind spots

- **THERE ARE NOW TWO HOSTS THAT APPLY, and only one of them uses this service — SO A FIX TO ONE
  WILL NOT REACH THE OTHER.** `tools/PreProcessor/apply_case_type.py` still orchestrates the three
  steps itself: it reaches its refusals in three separate raises (three runs to clear what the
  window clears in one screen of edits), it writes the overlay into the LIVE config rather than a
  copy, and it has no ignored-role filtering. #170 reused every SERVICE the ticket names
  (`guess_roles`, `plan_for`, `bind`, `case_type_scale`) and added the orchestration the window
  needed around them; re-pointing that host at it is a real change to a gated host and was out of
  scope for "the GUI work is a surface over these". **What has to move with it**:
  `tests/test_case_type_roles.py` asserts the host contains the literal line
  `for binding in roles.bind(fitted, assigned):` and injection G mutates exactly it, so that
  anchor has to be re-expressed against this service before the host can change.
- **`plan` READS PRECEDENCE AND THE READ-OUT ABOVE IT DOES NOT.** `case_type_picker.summary`
  asks `chosen(config)` — the operator's own pick — while `plan` asks `for_config`, which falls
  back to `HYBMESH_CASE_TYPE`. So with nothing picked and that variable set, the read-out says
  "No case type is chosen" and the Apply button is live, acting on the environment's. Left as
  it is on purpose: `for_config` is the ONE place precedence is spelled (#169) and duplicating
  it here would be worse, the confirmation dialog NAMES the case type before anything is
  written, and the variable is the channel the picker exists to replace. It is a divergence all
  the same, and a reader changing either side should move both.
- **THE RULER IS STILL READ OFF WHOLE GEOMETRIES.** `case_type_scale.measure_role` measures the
  geometries bearing a `MeshConfig.geom_roles` role, which is per FILE, while the role assigned
  here is per SEGMENT. A drawing whose body and far field are two files measures the same ruler
  either way, which is every shipped case; narrowing it is still not done. Inherited from #164
  and recorded in `gui-handoff.md` as well.
- **NOTHING JUDGES WHETHER A CONFIRMED ROLE IS THE RIGHT CURVE except the family's own
  pre-flight.** Naming the far field as the body binds exactly that, with every id resolving,
  and only `preflight_for_config` notices. That is by design — the operator confirms, the family
  refuses — but it means a family whose pre-flight is weak (the H-grid binds nothing, so it has
  no containment test to fail) accepts an assignment nothing checks.
- **THE TABLE OFFERS EVERY GEOMETRY, not only the closed outlines a ring can bind.** An open
  polyline is selectable and is refused by `topology_binding.outline_problem` at apply time,
  with that helper's own sentence. Listing only valid candidates was the alternative and was not
  taken: a curve missing from the list with no reason given is the silence this seam exists
  against, and the four-question cascade is where the reason lives.
- **THE OVERLAY IS CLEARED ON SUCCESS AND ON NOTHING ELSE.** A cancelled apply, or one refused
  before the pre-flight is reached, leaves a previous attempt's mark up; only a successful commit
  clears it (gated, check 12). The flag belongs to `mesh_gen_diag_ctrl`, so this cannot wipe a
  selection somebody else made — but it also means a refusal the operator then walks away from
  leaves the canvas marked until the next Generate or apply.
- **`ApplyPlan.ready()` AND THE DIALOG ARE TWO READS OF ONE STATE.** The controller checks
  `ready()` before opening the dialog and `apply` checks it again; they cannot disagree today
  because nothing moves in between, but a future dialog that let the operator change a role
  would make the first read stale.
