---
paths:
  - tools/PreProcessor/gui/app/views/canvas*
  - tools/PreProcessor/gui/app/services/edge_edit*
  - tools/PreProcessor/gui/app/services/shape_refit*
  - tools/PreProcessor/gui/app/commands/**
  - tools/PreProcessor/gui/app/popup_stack.py
---

# GUI canvas and editing rules

Loaded on demand when the geometry canvas or one of its mixins, the edge-edit or shape-refit
service, a command class, or the pop-up stacking module is read. Rules only — the rationale (the
counted attributes, the measurements, the injections, the reversals and the named blind spots) is
`docs/design_notes/gui.md`. Read that note before overruling a rule here, and when a rule changes
update BOTH.

**These rules also govern files OUTSIDE the globs above, which cannot hand a reader the text.** For
the edit itself: `controller.py` — where the twelve attributes the owner replaced used to live, and
where `_edit_in_progress()` still is — plus the four controllers that open, commit and cancel one
(`controllers/curve_draw_ctrl.py`, `curve_edit_ctrl.py`, `file_edit_ctrl.py`,
`pending_edit_ctrl.py`) and the dialogs they hold opaquely. For the other four blocks:
`controllers/undo_ctrl.py` (the module global undo is named after),
`controllers/transform_apply_ctrl.py` (the whole of duplicate/transform closure), and
`controllers/segment_canvas_ctrl.py` (`_geometry_connect`, `_apply_geometry_update`,
`_clear_geometry_canvas` — the one-polyline rules).

**Pop-up stacking reaches furthest of all, and no glob of this file reaches a single call site**:
`app/utils.py` re-exports `keep_on_top`, and **every** modeless pop-up must go through it, so the
rule binds any view or controller that shows one — **11 calls in 9 modules**, re-measured
2026-09-03: the two edit controllers above (1 + 1), `views/settings_dialog.py` (1), FIVE across the
three result-canvas mixins, and THREE under `views/panels/` (`edge_props_dialogs_mixin.py`,
`mesh_bl_mixin.py`, `mesh_sizing_mixin.py`) — 2 + 1 + 5 + 3. `controllers/batch_ctrl.py` is NOT
among them and its absence is not an omission: it carries the comment recording that `BatchDialog`
deliberately opts out, which the rule below states. Three of the nine are under `views/panels/**`,
which is `.claude/rules/gui-panels-config.md`'s glob, and three more under
`.claude/rules/gui-results.md`'s; neither of those files carries a pop-up rule, so a reader of
`views/panels/mesh_bl_mixin.py` or of `views/result_canvas_plots_mixin.py` is handed rules for that
file and NOT this one. The table in `CLAUDE.md` is what makes all of them reachable; the globs are
the convenience.

**And one glob is WIDER than the area.** `commands/**` is the glob #59 assigns here, and
`commands/config_cmds.py`'s `UpdateProjectStateCmd` is the other half of a rule that lives in
`.claude/rules/gui-panels-config.md` — the one-directional panel↔model flow and
`push_panel_config`. Read that file as well.

**The edge being edited has an OWNER, and there are TWO edit kinds in it**
(`services/edge_edit.py`, Qt-free — `EdgeEditSession` + `EditOutcome` + `ShapeOutcome`).
Drawing/double-clicking an **analytic** edge, and double-clicking an **imported (discrete)** edge to
reshape its outline by corner vertices, both open a *modeless* session committed by **Create Edge** /
**Apply** and reverted by **Cancel** — between them **twelve attributes on `AppController`**, with
"an edit is live" enforced only by every reader remembering to test for `None`. **Both kinds live in
one owner because they are alternatives**: at most one may be live, so `_edit_in_progress()` is one
question with one answer.
- **The dialog is held OPAQUELY** — stored and handed back, never called into. What must be *asked*
  of it (a polygon's open/closed toggle) is read by the caller and passed into `update()` as a value.
- **`commit()` / `cancel()` end the session and return an `EditOutcome`; they do not decide what it
  becomes.** The *revert* does live in the owner, being the other half of its snapshot.
- **An edit BELONGS to the CAD session it began in, and leaving that session is a transition.**
  Every outcome carries its session and the caller acts on **that** one; the list / selection /
  window title are touched only when the edit's session *is* the front tab. (The defect: commit
  resolved through `active_session()` — the tab in front *now* — then fell back to matching by
  segment **id**, and ids are per-session, `renumber_segments` assigning contiguous 1..N across both
  edge kinds, so every tab's Nth edge has id N and the commit landed on **another tab's edge**.)
  Switching or closing
  away **asks**, defaulting to cancelling (`headless_default=True`); on close the edit question
  comes **first**, and declining aborts the close. Declining a switch must **put the tab bar back**.
  `begin`/`begin_shape` REFUSE while another edit is live — the backstop, not the interaction, since
  a Qt-free module cannot prompt. `commit`/`cancel` with nothing live is a silent no-op
  (`get_logger(__name__).debug`, never a pop-up).
- **An ending the DIALOG did not initiate must close the dialog** — it tears itself down through
  `finished → deleteLater`, which fires only on a self-close. The dialog travels back on the outcome
  and the caller closes it; that `close()` **re-emits `rejected`**, so the cancel handler runs again
  against an idle owner, which is why the silent-no-op rule and this one had to land together.
  **The canvas clear takes the EDIT's session**, since the preview is keyed by `session_id`.
- **Not every route out is a prompt.** Switching and closing a tab ask (both cleanly abortable).
  Opening a new tab, `reset_all_state` and loading a workspace end the edit unconditionally and say
  so in the log.
- **The committed-edge DRAG is a transition, not a nullable field**: `begin_drag` / `finish_drag`,
  and **a drag belongs to the segment it began on and cannot be finished against another**. The
  handler must not `begin_drag` on the `finished` event, and **a drag is NOT `is_active()`** —
  callers guarding on that predicate must keep working during one.
- **A corner drag is a value in, an outline out**: `move_corner` returns a freshly re-fitted array
  instead of mutating the live one, so dragging never accumulates transform onto transform and
  Cancel restores points *byte-for-byte*. The shape side has **`end_shape()`, not a commit/cancel
  pair**, because both endings need the same thing from the owner.
Gated by `tests/test_edge_edit_owner_seam.py` (five properties, nine in-test injections),
`tests/test_edge_edit_owner.py` (the verbs, Qt-free, PyQt6 refused through a meta-path hook so a
*deferred* import fails too), `tests/test_committed_drag_undo.py` and
`tests/test_edit_session_binding.py` (offscreen Qt with the real `AppController`). The binding test
moves `active_idx` **directly** rather than through `switch_tab`, on purpose: `switch_tab` now ends
the edit, and the binding is the half that must hold when some other route changes the front tab.

**The outline re-fit is pure arithmetic and has its own module** (`services/shape_refit.py`, Qt-free
— `build_edge_specs` + `refit_shape`). Each edge re-fits between its own two corners by the
similarity transform carrying its ORIGINAL corner pair onto the current one, so dragging a shared
corner redistributes both. Two behaviours it is careful about: a **zero-length edge** falls back to
a pure translation (the transform's divisor is the squared length), and the **closing edge wraps to
index 0** rather than being read as out-of-range and skipped. The extraction was measured: 2000
randomised outlines through both the new function and the pre-change in-place body came out
**byte-identical, worst |Δ| = 0**. Gated by `tests/test_shape_refit.py`.

**Undo is global, across every CAD session AND project settings** (`controllers/undo_ctrl.py`).
Histories stay per-`GeometrySession` (plus `controller.project_history`) so closing a tab drops
exactly its own commands; ordering across them is by the monotonic `seq` that `CommandHistory._push`
stamps. Undo raises the tab owning the command before applying it. Mesh/Solver/IB edits are recorded
by debounced snapshot diffing, so a burst of typing is one step. **Any code pushing config into
those panels must go through `controller.push_panel_config(panel, cfg)`** (or
`suppress_project_undo()`), or the push is recorded as a user edit.

**Every modeless pop-up goes through `keep_on_top(w)` BEFORE `show()`** (`app/popup_stack.py`,
re-exported from `app/utils.py`), which re-parents it to the **top-level** window, leaves it an
ordinary normal-level `Qt.Dialog`, and installs three filters — `_PopupRaiser` (on the main window,
per activation), `_ClickRaiser` (on the **QApplication**, per mouse RELEASE) and `_ShowRaiser` (on
the pop-up). Activation alone is not enough: it fires on the FIRST click of the main window only, so
every later click reorders the window in front with no Qt event to hear, and a raise deferred into
the middle of a canvas *drag* is undone when the drag ends. Releasing is when the platform has
finished reordering.
- **Both window-LEVEL shortcuts are wrong and were each shipped once.**
  `WindowStaysOnTopHint` floats above **every** application, and `Qt.Tool` — an NSPanel with
  `hidesOnDeactivate` — makes the pop-up **disappear** when the user clicks another app (measured on
  Qt 6.10: `isExposed()` → False); disabling the auto-hide is not an escape (Qt6 ignores
  `WA_MacAlwaysShowToolWindow`, and a Tool window sits at NSFloatingWindowLevel).
- **Every raise goes through `raise_later()`** — a raise issued from inside the event that reorders
  the windows is undone when the platform finishes that event.
- **Re-parenting is load bearing twice**: the raiser finds pop-ups in the top-level's direct child
  list, and a pop-up parented to a panel is hidden with that panel.
- `BatchDialog` opts out on purpose (it runs for minutes and must be free to sit behind).
Gated by `tests/test_popup_stacking.py`.

**Duplicate/transform closure is type-preserving, and only the polygon-bake fallback re-derives the
`closed` flag** (`transform_apply_ctrl`): a line stays a line, an **arc stays an arc**…, and the copy
inherits the source's `closed` flag — except when the copy bakes (formula curves, discrete file
edges, and a circle/arc under a NON-uniform scale, which is an ellipse the model cannot hold), where
the flag comes from the points via `_baked_edge_is_closed`.
- **The arc's image is read off three TRANSFORMED POINTS** — centre, arc start, quarter-sweep point
  — so one code path serves every similarity transform and a mirror's reversed sweep comes out of
  the geometry rather than a per-transform sign rule; the quarter point rather than the midpoint,
  because `sin(sweep/2)` vanishes at |sweep| = 2π.
- **Whatever still bakes is NAMED in the log with the reason.**
- **`SegmentModel.closed` defaults True and is only ever read for `curve_type == "polygon"`**, so
  every other edge carries True while drawing open — copying that flag onto a baked polygon is what
  silently closed a duplicated arc. Discrete edges must not take the PROJECT's closure either: one
  segment of a closed imported outline is itself an open polyline.
Gated by `tests/test_transform_closure.py`.

**The discrete geometry is ONE polyline, and both ends of that have to be handled.** A session
stores every discrete point in `original_points`, indexed by `split_indices` into file segments,
drawn as a single pyqtgraph item.
- **Baking order matters.** `BakeCurveToGeometryCmd` welds a converted edge onto whichever END of
  the polyline it touches, so an edge touching neither lands as a separate piece.
  `bake_selected_curve` chains a multi-edge selection with `_chain_edges` (the same one Join uses)
  and bakes head-to-tail as ONE undo step, index-sorted — otherwise the DRAWING order, which the
  user cannot fix by clicking differently, decides the result.
- **Where the polyline must NOT join comes from the model.** `_geometry_connect` (in
  `segment_canvas_ctrl`) breaks it at any index interval covered by no file segment and passes that
  as pyqtgraph's `connect` array; without it two disjoint pieces are drawn joined by a "diagonal"
  belonging to no edge that cannot be selected away. Deliberately not a spacing heuristic, which
  would also break a long straight edge beside a finely sampled arc.
- **An empty model still has to be drawn**: `_apply_geometry_update` returns early when
  `original_points is None`, so `_clear_geometry_canvas` wipes layer, hit-test points, split
  markers, closing edge and stats — but never the analytic items, which a session can have alone.
