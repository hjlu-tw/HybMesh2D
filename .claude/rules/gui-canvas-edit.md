---
paths:
  - tools/PreProcessor/gui/app/views/canvas*
  - tools/PreProcessor/gui/app/services/edge_edit*
  - tools/PreProcessor/gui/app/services/shape_refit*
  - tools/PreProcessor/gui/app/services/naca_airfoil*
  - tools/PreProcessor/gui/app/services/geometry_offset*
  - tools/PreProcessor/gui/app/models/derived_geometry*
  - tools/PreProcessor/gui/app/views/offset_dialog*
  - tools/PreProcessor/gui/app/services/canvas_tools*
  - tools/PreProcessor/gui/app/models/shape_spec*
  - tools/PreProcessor/gui/app/commands/**
  - tools/PreProcessor/gui/app/popup_stack.py
  - tools/PreProcessor/gui/app/views/panels/edge_props_naca*
  - tools/PreProcessor/include/NacaAirfoil*
  - tools/PreProcessor/src/main.cpp
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
`_clear_geometry_canvas` — the one-polyline rules). For the aerofoil block (#147):
`services/geometry_service.py` (the preview branch), `models/project.py`
(`add_airfoil_parts`), `views/panels/edge_props_shape_build_mixin.py` and
`views/panels/edge_props_panel.py` (the shape stack's host and the combo row, whose OWN
rules are `.claude/rules/gui-panels-config.md`'s), `views/shape_dialog.py`,
`controllers/signal_wiring_ctrl.py` (the shape-tool menu). For the offset block (#152):
`controllers/offset_geom_ctrl.py`, which is the whole CAD-stage half of it and sits under no
glob here. **The two RESAMPLER files are
reached by this file's own last two globs, deliberately rather than by inheritance**: the
first draft of this paragraph ASSERTED that `.claude/rules/mesher.md`'s `src/**` and
`include/**` match a path nested under `tools/PreProcessor/`, and one observation of that
is not a measurement — so the globs here name the two files outright and the claim is
gone rather than argued. `mesher.md` carries no rule about the resampler's shape dispatch
either way.

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

**A PARAMETRIC NACA 4-DIGIT AEROFOIL IS A `curve_type`, AND ITS LAW HAS ONE OWNER PER
HOST** (`services/naca_airfoil.py`, Qt-free and stdlib-only;
`tools/PreProcessor/include/NacaAirfoil.hpp`; `models/shape_spec.py`'s `naca4` rows;
`models/project.py::add_airfoil_parts`; #147). It joins `circle` and `polygon` in the
machinery that exists — no new kind of object, and the project file / workspace /
pipeline round trip comes free from `SegmentModel.to_dict()`.
- **The law is written TWICE, once per host, and that is deliberate.** A Python module
  cannot be read by a C++ binary, and the canvas preview must run on every drag with no
  build tree. Each host has exactly ONE copy; a third anywhere is the defect.
- **What holds them together is `tests/test_naca_airfoil_parity.py`, which DRIVES BOTH**
  — the preview through `GeometryService`, the law through the real `surface_resampler`
  — and compares coordinates. **A source scan is not a substitute** (#135). Tolerance
  1e-9 and NOT tighter: the `.dat` is written at `setprecision(10)`, so 5e-11 is its own
  quantum and anything below that measures the writer.
- **Mirror it literally**: powers as repeated multiplication, the same evaluation order,
  the two exact endpoints ASSIGNED rather than computed. A change to one file without
  the same change to the other is what that gate catches.
- **The preview ends with `_resample_polyline_uniform` because the resampler's `uniform`
  strategy does the same to the generated polyline** — as `circle` and `line` already
  do. Removing it is an injection that bites.
- **The shape arrives SEGMENTED, and `naca_airfoil.segment_parts` is the only thing that
  decides how**: upper + lower for a sharp section, plus a trailing-edge base for a
  blunt one. The parts are ordinary CAD segments with ordinary ids, so a topology
  template binds through #137's stable-id lookups with no new rule, and
  `AddAirfoilSegmentsCmd` adds them in ONE undo step.
- **A blunt trailing edge is PRODUCED, correctly; a `te` part on a SHARP section is
  REFUSED** with the reason named, in both hosts. The C-grid template's refusal of a
  blunt section (#148) is a different refusal for a different reason.
- **An element that produced NO points is reported as a failure and writes nothing** —
  by the one writer in `tools/PreProcessor/src/main.cpp`, so it is true of every shape.
- **`shape_spec`'s non-numeric shape parameters are TABLES** (`TEXT_ATTRS`,
  `BOOL_ATTRS`), not per-type branches in the widget helpers. The polygon's vertex
  string was the first and was a hand-written special case; the second one made it a
  table. A third must go in the table.
Gated by `tests/test_naca_airfoil_parity.py` (64 checks, 17 recorded injections) and
`tests/test_naca_airfoil_gui.py` (18 checks, through the real `AppController`).
Blind spots: in those two gates' docstrings and in `docs/design_notes/gui.md` — this
file has no `## Named blind spots` section, which is where its header sends every other
rule in it.

**AN OFFSET GEOMETRY IS DERIVED, AND ITS LAW HAS EXACTLY ONE OWNER**
(`services/geometry_offset.py`, Qt-free + numpy; `models/derived_geometry.py`;
`views/offset_dialog.py`; `commands/derived_cmds.py`; `controllers/offset_geom_ctrl.py`;
#152, parent #150). What comes back is an ORDINARY discrete geometry — no new
`curve_type` in the GUI and none in the resampler, so the shape-parity surface does not
grow.
- **`offset_points(points, distance, closed)` is the only place the law lives.** The
  canvas preview and the thing that writes the geometry call it, so they cannot produce
  different curves. Nothing may re-derive a normal, a bisector or a fold bound elsewhere.
- **The result has the SOURCE'S LENGTH and the source's point order**, which is what makes
  the source's split indices index it and mean the same thing. The derived session takes
  the source's `split_indices` and a DEEP COPY of its file segments, so segment ids,
  boundaries and per-segment facts (`bc`, `grow_bl`) are the source's by construction —
  never re-segmented, which would be a second answer to a question the source has already
  answered.
- **The vertex direction is the MITER, which is the bisector**: `(na + nb) / (1 + na·nb)`,
  so a polygon inscribed in `r` comes back inscribed in `r + d/cos(pi/n)`. Moving each
  vertex `d` along the UNIT bisector would give `r + d` exactly and put every offset EDGE
  nearer than `d` to its source edge, which is not what a distance from a wall means.
- **The closure flag is the CALLER'S** (`ProjectModel.is_closed`, already resolved): a
  closed outline wraps and both ends get a bisector, an open one takes the end edge's own
  normal. Never re-derived inside the service.
- **The side is a signed distance, and "outward" comes from the stored WINDING** for a
  closed outline — the shoelace area is measured and the normals flipped — so a body
  imported either way round answers to the same sign. An open polyline has no inside, so
  positive is the RIGHT of travel, stated rather than inferred.
- **A fold is REFUSED, never trimmed, and the refusal carries a number that works.** A
  trimmed offset has fewer points than its source, which breaks the one property this
  object exists for. `OffsetRefused.max_distance` is SIGNED and feasible, so feeding it
  straight back in succeeds; the local (edge-reversal) bound is analytic, the global
  (crossing) bound is bisected, and the bisection keeps the known-good end of its bracket.
- **Only the DISCRETE geometry is offset.** A source with no points is refused by name and
  pointed at Convert to Discrete, rather than silently offsetting nothing.
- **The record is DATA and regeneration is an ACTION.** `ProjectModel.derived_from` is
  carried by `to_state_dict()` — the ONE serialiser both the `.hws` `project_config` and
  the pipeline script's `cads` entry now use, so a field added to the model cannot reach
  one project file and not the other. Never a live recomputation on a source edit, which
  would put an implicit write into every geometry edit path and would have to be reconciled
  with global undo and the outline re-fit first.
- **Regeneration resolves its source among the OPEN sessions, by display name then by
  path**, because the thing being offset is the geometry as it is now. A record whose
  source is not open is refused NAMING it — never skipped, and never resolved to whatever
  is nearest. It re-mirrors the source's segmentation as well as its points, in ONE undo
  step (`RegenerateOffsetCmd`).
Gated by `tests/test_geometry_offset.py` (26 checks, 9 recorded injections) and
`tests/test_offset_geometry_gui.py` (39 checks, 12 recorded injections, through the real
`AppController`). Three of those 21 were INERT or CRASHED on their first run and the
gates were changed to reach them — a recorded injection that was never re-run is a claim,
not a measurement. Blind spots: in those two gates' docstrings and in
`docs/design_notes/gui.md`.

**The per-tool shape-drawing tables are `services/canvas_tools.py`'s, not the canvas
mixin's** (`DRAW_NPTS`, `DRAW_HINTS`, `draw_hint`). How many points a tool collects and
what it asks for next are one tool's two facts; declaring them side by side is what
stops a new tool having one and not the other, and Qt-free is what makes them readable
without a display.

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
