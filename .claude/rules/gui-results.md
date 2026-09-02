---
paths:
  - tools/PreProcessor/gui/app/views/result*
  - tools/PreProcessor/gui/app/views/surface_source_dialog.py
  - tools/PreProcessor/gui/app/views/panels/result_panel*
  - tools/PreProcessor/gui/app/models/result*
  - tools/PreProcessor/gui/app/models/tecplot*
  - tools/PreProcessor/gui/app/services/result*
  - tools/PreProcessor/gui/app/services/surface*
  - tools/PreProcessor/gui/app/services/analytic_shape*
---

# GUI results rules

Loaded on demand when a result view or one of its mixins, the surface-source dialog, a
Results panel mixin, the result / Tecplot models, or the result-legs, surface-source,
surface-sample or analytic-shape service is read. **Rules only** — the rationale (the
timings, the measurements, the injections, the reversals and the named blind spots) is
`docs/design_notes/gui.md`.
Read that note before overruling a rule here; when a rule changes, update BOTH.

**Also governed from OUTSIDE these globs**, which cannot hand a reader the text:
`controllers/postprocess_ctrl.py` (loads a result path, asks `ask_legs`),
`controllers/surface_source_ctrl.py` (decides which of the six surface sources are
usable), and `services/phi_quality.py`, whose `interface_points` the `interface_cells`
source reads and which NO glob in ANY rule file reaches. The tripwire table in `CLAUDE.md`
is what makes all three reachable; the globs are the convenience.

**Globs: three go BEYOND #59's list, nothing is narrowed.** #59's five — `views/result*`,
`models/result*`, `models/tecplot*`, `services/result*`, `services/surface*` — are carried
verbatim. Added: `views/surface_source_dialog.py` and `services/analytic_shape*`, because
the surface source is one of this file's rule blocks and #59's list reaches neither file;
and `views/panels/result_panel*`, a deliberate overlap with
`.claude/rules/gui-panels-config.md`, which carries no results rule — so a Results-panel
reader is handed both files.

**Boundaries run BOTH ways.**
- **Outward.** TWO facts, neither owner under a glob here: a leg's span
  (`iteration_span`, `finished_stamp`) is owned by `services/case_run_note.py`, a leg's
  stem (`strip_run_tag`, `newest_first`) by `services/case_files.py` — both matched by
  `.claude/rules/pipeline-case.md`'s `services/case_*`, as is
  `views/panels/restart_chooser.py`, the OTHER window that must not describe one archive
  differently. Read that file when changing what a span or a
  stem means.
- **Inward.** Three files these globs reach show modeless pop-ups through `keep_on_top` —
  `views/result_canvas_interaction_mixin.py`, `result_canvas_plots_mixin.py`,
  `result_canvas_surface_mixin.py` — while the pop-up stacking rule is
  `.claude/rules/gui-canvas-edit.md`'s. Nothing here restates it and nothing here counts
  those calls: that file's header is the one place the count lives.

## Transient playback (Results tab)

A transient run appends one Tecplot zone per dumped step, so the Results view is a movie.

- **The zone index is BYTE OFFSETS, scanned once** (`models/tecplot_index.py`, cached by
  (path, mtime, size)); `TecplotResult.from_file` seeks to one zone's byte range instead
  of reading the whole file — 0.35 s → 0.07 s per frame on a 113 MB / 10-zone run.
- **`models/result_series.py`** owns the LRU frame cache — bounded by BYTES, not frame
  count — and the per-variable global range. `views/result_playback_mixin.py` owns the
  transport.
- **Looping is opt-in**: a run plays through once and stops on the last frame (the
  converged solution). The same checkbox governs the step buttons, which clamp at the ends
  — greying out there — instead of wrapping. Play at the end of a finished non-looping run
  rewinds first; First/Last are jumps, so Loop does not apply.
- **"Lock scale" pins the colour scale across the whole run** (shown only for a multi-zone
  result), because auto-scaling each frame to its own min/max repaints the same colours
  onto a changing range. **OFF by default (USER-REQUESTED)**: "Auto (fit to data)" has to
  mean the frame on screen. A **manual** clim always wins, and the lock is dropped when
  the displayed variable changes.
- **A colour range — pinned OR typed — belongs to ONE variable** (`_clim_by_var`; #24,
  USER-REPORTED). Four rules: the MODE stays global (one Auto/Custom checkbox with one
  meaning), so switching to Auto does not forget the numbers; a variable with no
  remembered pair is SEEDED from its own data range on first render and remembered;
  precedence is **manual > lock > auto**, enforced in `playback_clim` returning None
  unless `_clim_auto`; and the store is view state for the loaded result, cleared by
  `load_result_path` / `clear` but kept across frames. Written ONLY through
  `remember_clim` / `set_clim`, read through `manual_clim` / `render`'s seed path.
- **The panel's Min/Max boxes follow the range in force through the `result_rendered`
  signal**, never by reading canvas privates, and in Custom mode refresh on exactly two
  events: the variable MOVED, or the canvas reports `clim_seeded`. **Never keyed on the
  variable NAME** — a newly loaded run re-seeds under the *same* name. **The Auto checkbox
  IS the mode, in both directions**: unticking seeds from the frame on screen.
- **`set_result` reuses the triangulation when the incoming frame has the same nodes**,
  keeping probes/line/extrema alive across a step. Field caches are always dropped.
- **Frames are labelled by POSITION** (`Frame 4 / 10`): the solver writes `t = "time 0"`
  for *every* zone.

Gated by `tests/test_result_playback.py` (which pins the byte-range parse against a
whole-file scan) and `tests/test_result_clim_per_variable.py` (8 properties, all
injection-verified).

## A restarted solve is ONE run, and it plays as one animation

`services/result_legs.py`, Qt-free — `list_result_legs` → a `LegSeries` of `ResultLeg`s in
playback order plus warnings as data; `ResultSeries` takes a LIST of paths. #32, blocked
by #30 because it reads the `RUN.txt` #30 writes.

- **A list, never a concatenated temp file** — the byte-offset index exists so a frame
  costs 0.07 s. A FLAT frame index sits above the per-file `tecplot_index`: global frame
  *k* → (file, zone). Three things become global with it — the numbering, the LRU **byte**
  budget and every range `global_range` reports — so a change in ANY file drops EVERY
  cached frame and range.
- **A leg is found by its STEM** (`strip_archive_suffix` + `strip_run_tag`, the inverse of
  `archive_name`), which also works on **pre-#30 archives** that kept `.gui`.
- **Order by ITERATION COUNT**: by the CORRECTED `end`, creation order breaking ties.
  Lineage answers a different question — a PREDECESSOR relation, never a position, and two
  legs resumed from the same point are indistinguishable by it — but it DETECTS the
  overlap a span cannot.
- **How far a leg got is NOT computed here** (#43): every span comes from
  `case_run_note.iteration_span`, which the restart chooser reads too, so the two windows
  cannot describe one archive differently.
- **A leg measurable NEITHER way is played WHERE IT RAN, not last**, inheriting the last
  count recorded before it. REVERSES #32's "offered last", which is right for a chooser
  LIST and wrong for a playback ORDER — see `docs/design_notes/gui.md`, "A leg that can be
  measured NEITHER way is played WHERE IT RAN, not last".
- **An overlap is a MEASUREMENT** (#43), reported and never interleaved: a half-open span
  `(start, end]`, so the test is interval intersection and the message names the repeating
  iterations. Half-open is load bearing — consecutive legs MEET at a boundary iteration,
  and a closed range would report every ordinary restart as an overlap. **Lineage** is the
  fallback when both spans cannot be measured; a blank start is deliberately not a key,
  since "cold start" and "no record" must not match.
- **The legs are the legs of ONE run**: `…dat.gui` and `…dat.cli` side by side are two
  solves. The anchor is the opened file's run tag — from its name, or from its own
  `RUN.txt` — a differing leg is excluded and NAMED, an undeterminable one included.
- **Opening any leg opens the SOLVE. An INTERACTIVE load asks; a headless one does not**
  (USER-REQUESTED 2026-08-27). REVERSES #32's modal on every load — see
  `docs/design_notes/gui.md`, "Opening any leg opens the SOLVE". **`This leg only`** is
  the escape: shown only when the solve HAS more than one leg, never persisted, unticked
  on every load, and yielding a ONE-leg series rather than a second code path. **Its
  visibility asks how many LEGS the solve has and nothing else** — never the `multi`
  frame-count flag.
- **Which legs play is a CHOICE, and it is the user's** (`views/result_leg_picker.py` +
  `views/result_leg_select_mixin.py`): a tick-list offered on load and reopenable from
  `Legs…`. **`ask_legs` returns `None` — "every leg" — when headless, and `None` is also
  what a CANCEL and an empty tick-list return**, so batch and CI are byte-for-byte #43.
  **Precedence is stated, not raced**: `This leg only` wins while ticked, then the subset,
  then every leg — and unticking restores the SUBSET. **Both controls key on the LEG
  count, never the frame count.**
- **The landing frame is the last frame of the leg that was OPENED** (`last_frame_of`),
  not of the series. **`load_result_path`'s second argument is a `frame`, not a `zone`.**
- **The variable selector is the INTERSECTION**, the subtraction logged naming the short
  leg, with derived quantities recomputed from that intersection through
  `TecplotResult.derived_from_names`, so a derived field cannot outlive its inputs.
- **The leg name prefixes a label only when the series has more than one file**
  (`prev_002 · Frame 3 / 10`); the transport's read-out appends the SERIES position in
  `_read_out`, not in `frame_label`, since the zone selector uses the label as a list
  entry.
- **The per-variable seeded range is COMPUTED over the series, not just carried across
  it** —
  one leg's band saturates every other. A MULTI-leg series seeds from the series; a single
  file keeps #24 exactly. **It runs in `seed_range_from_series()`, never inside a paint**
  (#43; REVERSES the original `scan_series_range` call from `render`, which cannot pump
  the event loop — see `docs/design_notes/gui.md`, "A restarted solve is ONE run split
  across several files"),
  called by the handler that unticks Auto, where the "this will take a moment" line is
  painted first; `series_range_hint` states in the Min/Max tooltip where the whole-series
  range is available. **A failed scan is not remembered**
  (`_series_seeded` records only successful scans). **A range the user TYPED is tracked
  separately (`_clim_typed`, written only by `set_clim`) and is never scanned away.** The
  colour-scale concern lives in `views/result_scale_lock_mixin.py`.
- **Each leg's iteration count is where the leg is NAMED** — the tooltips of the frame
  read-out and frame selector — carrying the SAME two caveats the restart chooser's
  tooltip does (recorded vs recomputed; an interrupted run makes it an upper bound). A
  load emits ONE summary line naming the legs opened; each warning stays a full line of
  its own.
- **A leg's timestamp is when its run FINISHED, never its `archived_at`**
  (`case_run_note.finished_stamp`; USER-REPORTED 2026-08-27) — an archive is made by the
  NEXT run at the moment it starts, so the two answer different questions. Recovered from
  the run's own outputs (`shutil.move` preserves mtime; #30's hard link shares the inode),
  preferring the ZONE DUMP then `RUN.txt`. **`restart_points` and `result_legs` had the
  defect independently**, so the answer has ONE owner; `archived_at` is kept as its own
  tooltip line.

Three duplications this created were pushed to their owners: `case_files.strip_run_tag` /
`newest_first` and `case_run_note.mtime_stamp` / `iteration_span`, read by both
`restart_points` and `result_legs`. Gated by `tests/test_result_legs_playback.py` and
`tests/test_result_leg_picker.py`.

## "The surface" of a surface plot is a CHOICE, and so is where s = 0 is

`services/surface_source.py` + `services/surface_sample.py`, both Qt-free;
`controllers/surface_source_ctrl.py` decides availability; `views/surface_source_dialog.py`
+ `views/result_canvas_surface_mixin.py` are the UI. REVERSES the older single meaning —
the inner boundary loops of the solved triangulation, which is no answer at all for an
immersed-boundary run — see the block of the same name in `docs/design_notes/gui.md`.

Six sources are offered, all listed even when unusable with the reason on the row: `mesh`
(the only one whose points ARE mesh nodes, so it keeps `node_ids` and reads **exact**
nodal values), `field_iso` (φ = 0.5 on the solved mesh), `grid_iso` (the same on the STL3d
structured φ), `interface_cells` (the Fit Δ points, i.e. `phi_quality.interface_points` —
public precisely so the plotted surface is the one the fit report measured), `analytic`
(through `services/analytic_shape.py`, shared with the φ-DLL generator so the plotted body
cannot drift from the solved one) and `cad`.

- **Iso-lines are chained by mesh EDGE identity, never by welding coordinates**: one
  crossing point per crossed edge, computed from the canonically sorted node pair so both
  owning triangles get the identical coordinate, then a walk triangle→triangle through
  shared edge keys. **No distance tolerance anywhere.** Every crossing triangle has degree
  exactly 2, so a component is a cycle or a path, and `closed` is reported from *arriving
  back at the entry edge*, not guessed.
- **s = 0 is required, not defaulted (USER-REQUESTED)**: Show/Plot stay disabled until a
  rule (x min / x max / y min / y max) is picked, traversal handedness is forced from the
  polygon's signed area, and the canvas marks the origin + direction. REVERSES the old
  origin inherited from `next(iter(set))` inside the boundary tracer — see
  `docs/design_notes/gui.md`, the surface block.
- **Arc length of a closed curve reaches the full perimeter** (the removed
  `perimeter_series` computed the closing chord and then sliced it off).
- **Off-node samples are interpolated, and δ = 0 by default.** For an immersed solid the
  interface holds the SOLID state, so an outward-normal offset δ is offered — but nothing
  is moved silently, and the title states `exact nodal` vs `interpolated, δ=…`. Outward
  comes from the polygon's own signed area, not the requested handedness. Samples outside
  the mesh come back NaN, never a fabricated value.
- **The Fit Δ cloud is cell CENTRES with no connectivity**, so it is ordered by a greedy
  nearest-neighbour walk; a hop >5× the typical one is reported in `note` instead of
  returning a plausible-looking arc length.
- **Nothing is extracted while the dialog is being edited** — the widgets only build a
  `SurfaceSpec`.

Gated by `tests/test_surface_source.py` and `tests/test_surface_source_gui.py`.

## Named blind spots

- **The leg picker is gated offscreen, where the dialog is never shown.** What
  `tests/test_result_leg_picker.py` covers is its verbs, the filter and the controls'
  visibility — not the dialog itself.
- **Two of `tests/test_result_legs_playback.py`'s injections are PERMANENT**, because the
  obvious construction of each passes with the code removed: the convergence fallback
  injected on legs that HAVE a note, and the run-tag filter in the direction that FAILS.
  Each carries a negative control.
- **`controllers/postprocess_ctrl.py` still reads `_pipeline_running` once**, guarding the
  load-FAILED modal — residue predating #32's interactive/headless split.
- **The Fit Δ walk can jump a thin waist.** The >5× hop is reported, not repaired; prefer
  the iso-line for measurement.
