---
paths:
  - tools/PreProcessor/gui/app/services/mesh_bc_audit*
  - tools/PreProcessor/gui/app/services/project_file_kind*
  - tools/PreProcessor/gui/app/services/mesh_grid_lookup*
  - tools/PreProcessor/gui/app/services/mesh_shape_stats*
  - tools/PreProcessor/gui/app/services/case_type*
  - tools/PreProcessor/gui/app/views/panels/mesh_stats_panel*
  - tools/PreProcessor/gui/app/models/mesh_output_names*
  - tools/PreProcessor/gui/app/controllers/mesh_export_ctrl*
  - tools/PreProcessor/gui/app/controllers/mesh_layers_ctrl*
  - tools/PreProcessor/gui/app/controllers/solver_ctrl*
  - tools/PreProcessor/gui/app/models/segment.py
---

# GUI file hand-off rules

Loaded on demand when the mesh-BC audit, the project-file classifier, the case-grid lookup,
the shape-summary reader, the CASE TYPE and its verdict, the Mesh Statistics panel, the mesh
output-name resolver, the mesh-export / Mesh-layers / solver controller, or the segment model
is read — **18 files**, verified to match. The `services/case_type*` glob is #160's: a case
type GRADES the same `.provenance.json` this file's sixth concern already reads inward, so
the reader and the judge sit together rather than one area's rule being split in two. It
reaches EIGHT files since #164 — the document, the figures and provenance it holds, the
config overlay, the characteristic length that fits that overlay to another drawing, the
verdict, the authoring step, the ROLES that bind one to the operator's own CAD and the
pre-selection split off them — all eight being the ~500-line standard's cuts through one
artefact rather than eight seams. **Rules only** — the rationale (the
measurements, the dated USER-REPORTED failures, the reversals and the named blind spots) is
`docs/design_notes/gui.md`. Read that note before overruling a rule here; when a rule changes,
update BOTH.

**The concern is one question, asked six times: is a file one stage leaves on disk still
correct when the NEXT one reads it?** The `.bnd`'s boundary conditions, the project file's
kind, the mesh's output name, which grid a reopened case is wired to, the `.meta` sidecar's
per-segment facts — and, the sixth and the only one read INWARD rather than written outward,
the `.provenance.json` the mesher leaves beside a mesh, which is where the GUI's quality
summary now comes from (#131). Four of the six were USER-REPORTED failures, and every one of
them produced a **plausible wrong answer rather than an error** — an all-`wall` solve that
looks converged, a float parse error on JSON, a file literally named `mesh_<case>.*` that
`os.path.exists` accepts, `No mesh generated yet` for a case whose grid is on disk, a sidecar
whose labels nothing carries, a quality figure measuring a quantity the mesher never reported.
That is the family resemblance, and it is why they are one file.

**THREE files this rules on are reached by NO glob in ANY rule file**:
`tools/PreProcessor/save_case_type.py`, #161's authoring host,
`tools/PreProcessor/show_case_type.py`, #162's inspecting one, and
`tools/PreProcessor/apply_case_type.py`, #163's applying one and #164's binding one. All three sit outside
`gui-seams.md`'s tree-wide `tools/PreProcessor/gui/**` as well — so the tripwire row in
`CLAUDE.md` is the only thing that reaches their reader, the same gap recorded for `run_batch.py`
and `CMakeLists.txt`. All three are outside `tests/test_silent_exceptions.py`'s swept tree for the
same reason, and all three carry the narrow handler that file's absence argues for.

**Boundaries run BOTH ways.**
- **Outward.** Three owners sit under other rule files' globs. `models/mesh_config.py`
  re-exports the whole output-name resolver and belongs to
  `.claude/rules/gui-panels-config.md`, which carries the panel's side of the Output field.
  `services/pipeline_runner.py` is the module that handed the unresolved `.*` name through
  and then `os.path.exists`-ed it; it belongs to `.claude/rules/pipeline-case.md`, as does the
  rest of what `controllers/solver_ctrl.py` does once the grid is accepted. Read those two
  before changing what an output name or a solver run means. A fourth, `tools/scripts/visualize_dat.py`,
  sits under NO rule file's globs at all — so this file and its own header comment are the only
  things that reach its reader. `views/panels/mesh_stats_panel.py` is matched HERE and by
  `.claude/rules/gui-panels-config.md`'s `views/panels/**`: its summary rows are this file's, and
  everything a panel is otherwise — its field-spec conventions, its data flow — is that one's. The
  per-cell array the same panel's colour mode uses is built in `views/mesh_canvas_fills_mixin.py`,
  which only `.claude/rules/gui-seams.md`'s tree-wide glob reaches; #131 left it alone on purpose
  and the rule below says so, because "unchanged" is a claim a later reader needs stated. **#132
  added three more of that kind**: `services/batch_runner.py`, `views/batch_dialog.py` and
  `controllers/batch_ctrl.py` are the batch queue's half of the same summary and are reached by
  no glob but that tree-wide one, so this row of `CLAUDE.md`'s tripwire table is what reaches
  their reader — named there rather than left as silent precedent, per #66. A fourth,
  `services/pipeline_runner.py`, belongs to `.claude/rules/pipeline-case.md`, which carries the
  mesh STAGE's side of it. Stated HERE and only here: a second home is where a list goes stale.
- **Inward.** `models/segment.py` is matched here for its `bc` / `grow_bl` fields, but the
  rule that `to_dict()` / `from_dict()` is the ONE serialiser behind the resample config, the
  workspace and the pipeline script is stated in the GUI module map, in
  `.claude/rules/gui-seams.md`. A `segment.py` reader is handed both.

---

**The grid must carry the BCs before it leaves the Mesh stage** (`services/mesh_bc_audit.py`,
Qt-free): a mesh generated BEFORE the per-segment BCs were applied exports **every** patch as the
wall default, and the solve then looks exactly like a converged, unchanged answer — the reported "I
updated the STAR-CD boundary conditions and got the same result". The mesher's own warning fires at
MESH time, several clicks before the grid is exported, sent and run, so `audit_mesh_bc()` re-checks
the actual file at each of those three points (`mesh_export_ctrl.mesh_bc_problems` /
`warn_if_mesh_bc_stale`, and `solver_ctrl._confirm_mesh_bc_state`, which *asks* rather than deciding
— `headless_default=True`, since batch/CI regenerate in the same pass). Two independent signals: an
assigned BC **type** with no patch of that name in the `.bnd`, and a geometry `.meta` **newer** than
the mesh (changing one segment from inlet to outlet leaves both names in the file, so content alone
cannot see it). Note the two namespaces this replaced a bug in: a `group_bc` key is a segment
**label**, a `.bnd` patch name is the **BC type** the mesher resolved it to — comparing them
directly (the old warning) marks every assignment missing on every run. BC detection resolves the
`.bnd` the RUN will use (auto-link wins in `_locate_mesh_bnd`, and `resync_solver_bc_from_group`
runs *after* the auto-link), or the table describes one grid while the solver reads another. Gated
by `tests/test_mesh_bc_audit.py`.

**A path is not a kind: project files are recognised by CONTENT**
(`services/project_file_kind.py`, Qt-free — `classify_project_file` → `"workspace"` / `"pipeline"` /
`""`; `PipelineConfig.classify_file` / `is_workspace_file` delegate to it). `main.py` handed every
positional argument to the geometry loader, so `main.py case.hws` ran `np.loadtxt` over JSON and
reported `could not convert string '{' to float64` (USER-REPORTED 2026-08-13). Every "open this
path" entry point dispatches through the one classifier: the CLI's positional args,
`_load_geometry_file` (which the recent-files menu and STL stager reach), and Pipeline ▸ Load, whose
dialog accepts `*.hws` too. Rules: a **workspace opened in the GUI goes to the workspace loader**,
never through `PipelineConfig.from_workspace_dict` (that conversion exists so the headless runner
can *run* a `.hws` and deliberately drops working state); the CLI loads the **project first and
geometry after**, because either project load resets all state and closes every tab; and only ONE
project file is accepted per launch, the rest named and refused. The "this will close all current
tabs" prompt is gated on `has_unsaved_work()`, since the GUI always opens with one blank session.
**The same RULE binds one file outside this package, though not the same classifier**:
`tools/scripts/visualize_dat.py` had the same defect (`np.loadtxt` over a `.vtk`, reported as
`could not convert string 'HybMesh2D' to float64`, #58). It asks a DIFFERENT question —
`project_file_kind` classifies JSON project files and has no VTK notion — so it owns
`looks_like_legacy_vtk`, refuses by name and points at `tools/scripts/view_mesh_vtk.py`. It must
NOT import `project_file_kind` to get there: that script's dependency set is numpy and matplotlib,
and this package is neither. A SECOND caller of the VTK question is what would belong beside the
classifier, in a module both can reach — not on this script's import line. It recognises legacy
VTK and nothing else, deliberately: a `.vrt`/`.cel`/`.bnd` is columns of numbers, so it parses,
and #58 scopes every other kind out. `load_geometry` returns an `(N, >=2)` array or raises, since
guarding the parse alone left the same blind traceback three lines later in `ax.plot`. Gated by
`tests/test_visualize_dat_kind.py`, which proves it still imports with PyQt6 unavailable.

**The Output field's `.*` is a placeholder, and only one module may read it**
(`models/mesh_output_names.py`, Qt-free — `output_base` / `output_path_for` / `FORMAT_PLACEHOLDER`,
re-exported as `MeshConfig.*`; it also owns `auto_case_name` / `auto_output_name` /
`is_auto_output_name`, whose `<case>` naming is mirrored in `src/cli.cpp`). The Mesh panel's Output
field holds ONE name for however many formats are enabled, filled in as
`results/meshes/<case>/mesh_<case>.*` — and because the panel→model sync runs on every edit, that
string IS the model value and travels verbatim into the workspace, the pipeline script and the
mesher's config. Only the export dialog understood it, so the **mesher** wrote a VTK into a file
literally named `mesh_<case>.*` and **`pipeline_runner`** handed that name through and then
`os.path.exists`-ed it — which the glob-named file satisfied, so the run reported success and passed
a glob to the contour stage. A C++-only fix turns that silent pass into a hard failure, so both
halves move together. `tests/test_output_format_placeholder.py` gates the resolver, the end-to-end
`-out_name <dir>/probe.*` run, and **statically fails the build if any other GUI file grows its own
`endswith(".*")`**.

**The last generated mesh is not where a reopened case left it**
(`services/mesh_grid_lookup.py::resolve_case_grid`, Qt-free): Generate Mesh writes into the GUI's
**temp dir** on purpose (`<temp>/global_mesh.*`; the stable per-case files appear on Export / Send
to Solver), and that directory is removed on exit, so `global_vtk_path` is **always** empty or
dangling in a reopened workspace — and auto-link, reading only that, answered `No mesh generated
yet` for a case whose grid was on disk (USER-REPORTED 2026-08-13). The resolver tries this session's
mesh, then the triple the case is **already wired to** (what the user last actually sent to the
solver — trusted over any guess), then the per-case exported mesh, and takes the first whose `.vrt`
+ `.cel` + `.bnd` all exist; it names which one and why in the log, and names every candidate when
none works. `_locate_mesh_bnd` asks the SAME resolver. Whether that grid is STALE stays the mesh-BC
audit's job, not a refusal to run. Gated by `tests/test_open_project_by_path.py`.

**The mesh QUALITY SUMMARY has ONE producer, and the GUI is a reader**
(`services/mesh_shape_stats.py`, Qt-free; displayed by `views/panels/mesh_stats_panel.py`; #131,
parent #128). The mesher measures cell shape and publishes median / p95 / max on three surfaces —
the run banner, a `HYBMESH_*` machine line, and `mesh.quality` in the `.provenance.json` sidecar
beside the mesh (`include/Provenance.hpp::MeshQuality`). The panel displays THAT sidecar. Until
#131 it computed its own per-cell aspect ratio and showed min / max / mean, so one mesh had two
descriptions under two DEFINITIONS — measured 2026-09-17 on the shipped `config/multiblock_ogrid.dat`
at the shipped defaults, its sidecar reports a quad midline ratio over 4608 STRUCTURED quads while
the file on disk holds 9216 triangles.
- **No sidecar is a BLANK, and there is no fallback computation.** A mesh made before this work or
  by another tool shows `—`. Computing one here would be the second implementation returning, in
  its most dangerous form: invisible at the point of reading.
- **A sidecar that says `cells: 0` with negative figures says `not measured`**, never 0.000 — the
  metric's floor is 1.0, so a zero would read as a perfect mesh. That is a THIRD state, distinct
  from the blank: the tool looked and could not measure.
- **`metric` travels with the figures and is displayed beside them**, spelled as the sidecar spells
  it. `quad_midline_ratio` and `tri_edge_ratio` are different quantities and comparing them means
  nothing; a prettified label would be a fourth spelling of a name whose job is to be matched.
- **THE SPLIT IS READ BY THE SAME ONE READER, AND NO HOST PARSES OR COMPUTES IT** (#145; the
  producers are #143 hybrid / #144 multi-block). The sidecar's `quality` object carries `layer` and
  `bulk` as NESTED objects beside the whole-mesh four, which have not moved. `ShapeFigures` is one
  set of the four published figures, `ShapeSummary` IS the whole-mesh set plus the metric and the
  two optional halves, and `summary.split` is the question a host asks — **never inferred from a
  zero**, because a half that is present and EMPTY (a geometry meshed with no boundary layer) is an
  ordinary measured state. **Both halves or neither**: the writer emits the pair under one flag
  (`include/Provenance.hpp`, `MeshQuality::split`), so half a split reads as no split.
  **The word is `layer` on both paths**, matching the sidecar's own key, which names the band of
  cells a mesher clusters against a surface without claiming anything about the BC on it; each
  path's BANNER keeps its own word (`boundary layer`, `wall band`) and those reach the GUI only as
  the per-metric gloss in `LAYER_MEANING`, shown only when this sidecar HAS a split.
- **A SIDECAR WRITTEN BEFORE THE SPLIT STILL SHOWS ITS FIGURES, in all three hosts.** It carries
  neither key, reads as not-split, and its whole-mesh figures display and report exactly as they
  did before #145 — the headless line is byte-identical and the panel's rows are unchanged. The
  split rows then say `not split`, which is a FOURTH state and none of the three that predate it:
  not the dash (no figures at all), not `not measured` (looked and could not), not a number.
- **ONE RENDERING OF A HALF, and this one IS shared with the panel.** `format_figures` renders one
  set of figures, and the panel's two split rows are its output verbatim while the headless line's
  two clauses are the same call — so unlike the whole-mesh set (two renderings, PINNED, see below)
  there is no second place where a half's precision or wording is decided. On the headless line the
  split is **APPENDED, never substituted**: every token the report carried before #145 is still in
  it, in the same order and at the same precision, so the old line is a PREFIX of the new one and a
  script that greps it keeps working.
- **The sidecar is found through `case_sources.mesh_provenance_paths`** — the lookup the case
  export already stages provenance with. No second path convention; the reader spells no sidecar
  name in its own code, and the gate checks that by AST.
- **No colour coding and no threshold on these rows.** That O-grid's `quad_midline_ratio` max of
  32.8 is its wall layer and is a CORRECT number, and a red one would train the user to ignore the
  colour.
- **The client-side per-cell arrays were DEMOTED, not deleted.** `get_element_aspect_ratios()` is
  the Quality (Aspect Ratio) colour map's input and is built where it draws
  (`views/mesh_canvas_fills_mixin.py`, unchanged); `workers/mesh_stats_run.py` stopped computing it
  because nothing displays it any more. **Skewness is untouched** and still client-side.
- **THE HEADLESS HOSTS READ THE SAME THING, THROUGH ONE FORMATTER** (#132). `shape_report(path)`
  = read + format, and `format_shape_report` is where the report's shape is decided —
  `services/pipeline_runner.py`'s mesh stage logs `[Mesh] cell shape — <report>` and
  `services/batch_runner.py` stores the same string on the job for the queue's Cell Shape column.
  Sharing the READER alone was not enough: each host would still have been free to round
  differently, drop the metric name or print an unmeasured run as numbers. **The view calls
  neither** — `batch_runner` reads once, Qt-free and off the GUI thread, and
  `views/batch_dialog.py` displays what the job carries, reformatting nothing. **ONE FORMATTER
  means one among the HEADLESS hosts**: the panel renders the same summary as four rows and keeps
  its own formatting, because a line and a row layout are different renderings — so the two are
  PINNED to each other instead (same precision, same metric name, same `not measured` wording),
  by `tests/test_headless_shape_report.py` check 7.
- **A case with no mesh carries NO figures — a THIRD absence, and not the reader's.**
  `batch_runner._shape_of` returns `""` when there is no `vtk` artifact, because asking for a
  sidecar beside nothing comes back `not published`, which is a statement about a mesh. The row
  shows a dash pointing at the Status column, and `controllers/batch_ctrl.py` clears `job.shape`
  on a re-run so a FAILED row cannot stand beside the previous run's numbers. **The dash's tooltip
  must not say the case made no mesh**: a case that meshed and then failed at a LATER stage shows
  the same dash — `run_pipeline` loses its artifact dict with the exception — and its mesh exists,
  with its figures in the log. The `"vtk"` key itself is spelled once, on `BatchJob.mesh_path`.
- **The reader's own strings never spell the sidecar's filename**, because the module that could
  compose a second path convention is this one; the gate below refuses `provenance` anywhere in its
  code strings, so the "no figures published" message names the concept and not the file. A HOST
  may say so in prose — the batch dialog's tooltip does — and `tests/test_headless_shape_report.py`
  check 2 is correspondingly the composition test (a literal ENDING in the suffix) rather than the
  substring one. Two gates, one rule, two strengths, stated so the difference is not read as drift.
Gated for the SPLIT by `tests/test_mesh_shape_panel.py` checks 12–14 (the parse, the panel's three
states including the old sidecar, and the halves against the REAL binary — where the shipped
O-grid's bulk p95 is below 3 while the whole-mesh p95 is above 20, so the split is proven to do
something rather than to exist) and `tests/test_headless_shape_report.py` checks 8–9 plus section
5's per-half comparison on both generation paths. Gated for the rest by
`tests/test_mesh_shape_panel.py`: a negative control that HAS computable per-cell shape
and still blanks, an allow-list over the whole GUI package for the per-cell array's two permitted
homes, a colour-map comparison by BRUSH COLOUR over a fixture with one cell in each quality bucket,
and a leg that runs the real binary on the shipped O-grid so the reader and the C++ writer cannot
drift — and by `tests/test_headless_shape_report.py` (#132), whose real-binary leg runs the two
SHIPPED demo pipeline scripts through the batch queue and compares each row against the line the
runner logged for that same case, as strings. Both files' hand injections are enumerated and dated
in their own docstrings; no count of them is restated here, because a second home for a count is
where one goes stale.

**A re-save of the geometry must not throw the Mesh-stage edits away, and the fix is a MODEL FIELD
rather than a wrapper around the subprocess.** Both halves of a per-segment BC live in the `.meta` —
the **label** in the NSEGMENTS bc column, the label→type map in the trailer — and the resampler
REWRITES that sidecar from the CAD config on every save, carrying the trailer through verbatim while
the bc column comes back `-` and the v3 grow column comes back 1. So a CAD tweak + Save left the map
pointing at labels nothing carries: the mesher warns, every patch exports as `wall`, and the GUI
still shows the BCs it holds in memory (USER-REPORTED 2026-08-12). The fix is **not** in the
resampler, which stopped preserving the prior sidecar on purpose (a NEW geometry written over an
existing output name inherited the old geometry's flags), and it is **no longer a caller-side
snapshot/restore around the subprocess**. Both facts are `SegmentModel` **fields**: `bc` already was
one, and **`grow_bl` is new** (default True; `to_dict()` emits it only when False, so every
pre-existing config, workspace and script stays byte-identical). The resampler has always read
`sj["bc"]` and `sj["grow_bl"]` from its own config, so `to_dict()` — the single serialiser behind
the resample config, the `.hws` and the pipeline script — makes the sidecar come back **correct the
first time**. The fact moved **up**, not down.
- **The `.meta` is now a PROJECTION of the model, not a second home** —
  `mesh_layers_ctrl._write_sidecar_from_model` rewrites both columns after every edit as the
  command's `refresh_cb`, so an **undo rewrites the file too**.
- **But a projection must be SEEDED first, and forgetting that broke the very thing this work exists
  to fix.** Nothing seeded `bc`/`grow_bl` from an existing `.meta`, and the BC dialog reports only
  NEWLY MINTED labels — so on any geometry whose setup lived only in its sidecar, one Mesh-stage BC
  edit reset every *other* segment's label to `-` and re-enabled a No-BL wall.
  `_adopt_sidecar_facts` takes the sidecar's values into the model first, **fill-in only** (a fact
  the model holds wins), and runs **BEFORE the undo snapshot** — adopting after it still fixes the
  wipe but makes undo restore the *empty* value, re-wiping the sidecar it just protected. Presence
  and ordering are pinned separately. Adoption is a migration rather than the user's edit, so it is
  not undoable and is **named in the log**. Caveat: the rule cannot distinguish "the model holds
  `grow_bl = True`" from "the model is at its default", so a sidecar `grow=0` is always adopted —
  right for the migration, wrong only if the file were allowed to lag the model.
- **The id-set-changed refusal disappeared as a concept**: the old restore re-applied by id after a
  subprocess had rewritten the file, and a label bound to a segment object cannot be shifted onto
  its neighbour.
- The Mesh-stage dialogs **emit** (`seg_grow_bl_changed` / `seg_bc_labels_changed`) instead of
  writing the sidecar — a view writing that file is how the fact came to live only there. A geometry
  with **no CAD session behind it** has no model to hold the fact, so the handler falls back to
  writing the sidecar directly; `_session_for_geom_path` returning None is a normal outcome.
- The label→BC-**type** map (`GROUP_BC`) deliberately did **not** move: it is keyed by label rather
  than by segment, so there is no segment field for it to be a field of.
- Knock-on: a Mesh-stage No-BL toggle now sets `is_geometry_modified`.
Gated by `tests/test_seg_edit_carryover.py`, which drives the real `surface_resampler` (so the wipe
cannot quietly stop happening) and the real controller handler.

**A CASE TYPE HOLDS THE THRESHOLDS THE MESHER REFUSES TO HOLD, AND THE VERDICT HAS FOUR STATES**
(`services/case_type.py` = the artefact, `services/case_type_verdict.py` = the grading, both
Qt-free; `examples/case_types/ogrid_circle.casetype.json`; #160, parent #158). The mesher measures
and never grades, by decision; a case type's threshold is not universal — it is scoped to one
class of problem and authored by someone who knows that class. Read
`docs/adr/0002-thresholds-live-in-case-types.md` before concluding the mesher's rule was violated.
- **The mesher is NOT modified.** The inputs are `mesh.quality` in the `.provenance.json`
  sidecar, read through `mesh_shape_stats.read_shape_summary`, plus the process exit code. No
  second reader and no recomputation.
- **FOUR states, and `not determinable` is not optional.** `usable`, `needs attention`,
  `unusable`, `not determinable`. An unmeasurable figure is the fourth and NEVER the first: the
  mesher returns negative, never 0.0, and prints `not measured` so that "we did not measure"
  cannot read as "it came out perfect". **"Unmeasurable" is asked of the SET**
  (`ShapeFigures.measured`), never of one figure's sign — `include/CellShape.hpp` writes a set's
  count 0 exactly when its three figures are negative.
- **`EXIT_ERR_INVERTED` (9) is `unusable` before any figure is read**, because non-orthogonality
  is blind to a fold that preserves angles and the mesh is exported under its ordinary name. The
  Python mirror of that code is in `case_type_verdict.py` and is held against
  `include/ExitCodes.hpp`'s own enum by check 1 of the gate.
- **Worst wins: unusable > not determinable > needs attention > usable.** One unmeasurable figure
  beside two good ones is NOT the milder answer.
- **A case type NAMES its metric** and a mesh measured with the other path's metric is `not
  determinable` — `quad_midline_ratio` against `tri_edge_ratio` is comparing nothing (#130).
- **ONLY the CELL SHAPE figures can carry a threshold.** Inverted counts, non-orthogonality and
  the wall first-cell error are on the `HYBMESH_MB_QUALITY` stdout line and not in the sidecar, so
  the only route to `unusable` from a fold is the exit code. A capability refusal, not a coverage
  limit: reading them would mean parsing the mesher's stdout, a second contract beside the one
  #131 made the single owner.
- **A threshold is an UPPER bound with two levels** (`attention`, `unusable`; either may be
  omitted), because every published figure is a ratio whose floor is 1.0. **Advice is REQUIRED**
  — "needs attention" with nothing to try is a dead end — and **an unknown key is REFUSED at both
  levels**, document and threshold: a bound misspelled into a key nobody reads is a threshold
  that silently stops biting.
- **ONE call for both hosts: `run_report(mesh_path, exit_code)`**, returning the text AND the log
  grade. `controllers/mesh_gen_ctrl.py` passes both to `log_report` (one graded message, not one
  per line) and `services/pipeline_runner.py` logs the text; **neither host may spell a verdict
  state, a threshold comparison or a grade of its own**, which the gate reads out of their ASTs.
  The headless call sits ABOVE the guard that raises on a non-zero exit, or exit 9's `unusable`
  could never be said. The GUI skips every code `workers/exit_codes.is_reason` claims — all
  THREE of `RC_EXCEPTION`, `RC_CANCELLED`, `RC_TIMEOUT`, read from that module rather than
  listed here — because those are the worker's own sentinels, not mesher exit codes.
- **A verdict NAMES the file that issued it** (`CaseType.source`, printed as the report's last
  line when the case type came from one). It is the only record of which case type a run used,
  the interim channel below leaving none.
- **Which case type is in play is NOT decided here.** `HYBMESH_CASE_TYPE` names it, as the one
  channel every host reads identically, and nothing has replaced it: the forecast named #162,
  then #166, and both landed without a picker. Unset means no
  verdict at all — **there is no default case type**, which would be a universal threshold
  wearing a different hat.
- **ONE SEAM, FIVE FILES** (two at #160, four at #161, five since #162), every cut the
  ~500-line standard and none of them by subject: the thresholds and their advice are declared
  in `case_type.py` and nowhere else, the set of OWNABLE fields in `case_type_fields.py` and
  nowhere else, and both are re-exported from the document so no caller learns a new name. Same
  cut as `mesh_config.py` / `mesh_config_validate.py` (#159), every dependency one way.
Gated by `tests/test_case_type_verdict.py` (14 checks and ten automated injections, each
asserting the mutation is well-formed, that the named check reddens and that no other does; the
counts are that file's own docstring's and are not restated here).
  Why: `docs/design_notes/gui.md`, "A CASE TYPE'S THRESHOLDS, AND THE FOUR-STATE VERDICT".

**A THRESHOLD IS MEASURED FROM A REFERENCE MESH, NOT TYPED** (`services/case_type_author.py` =
the authoring step, `services/case_type_reference.py` = the figures and the provenance a case
type holds, both Qt-free; `tools/PreProcessor/save_case_type.py` is the one action; #161, parent
#158). The maintainer knows which mesh is good and does not necessarily know what its p95 is, so
the tool measures the mesh and applies a TOLERANCE FACTOR. ADR-0002's first consequence is the
rule: a threshold is a demonstration, and a misjudged verdict is corrected by adding evidence
(#168), not by editing a number.
- **A bound IS its reference mesh's own published figure times a stated factor**, and the file
  carries the factor rather than only the product, so the derivation is re-checkable off disk.
  `CaseType._check_references` refuses a document whose bound is not its own derivation within
  `Origin.REL_TOL` — the only scope holding both halves, a `Threshold` knowing its factor and a
  `ReferenceMesh` its figure.
- **A FACTOR BELOW 1.0 IS REFUSED**: the bound would sit under the figure the reference mesh
  published, so the mesh the maintainer judged good would fail the case type authored from it.
  The positive form is gated — the reference mesh is `usable` under its own case type.
- **A MEASURED BOUND AND A HAND-SET ONE ARE TOLD APART BY THE FILE'S SHAPE, never by a flag**:
  `Threshold.origin_of` answers `MEASURED` when a factor sits beside the bound and `MANUAL` when
  one does not. A flag could disagree with the number next to it. **An override of ONE bound keeps
  the `reference`** and drops only that bound's factor, so what it overrode stays on the record;
  a threshold whose bounds are BOTH hand-set records no reference at all, `Origin` refusing to
  exist with no factor.
- **A FIGURE THE REFERENCE MESH COULD NOT MEASURE PRODUCES NO THRESHOLD, and the skip is
  REPORTED** (`AuthorResult.skipped`, printed by the host). `measured_figures` asks
  `ShapeFigures.measured` of the SET, so the mesher's negative sentinel is ABSENT from
  `ReferenceMesh.figures` rather than carried — and a `ReferenceMesh` recording a negative figure,
  or none at all, is refused.
- **ADVICE IS THE SELECTION.** The keys advice was supplied for ARE the thresholds; there is
  deliberately no all-nine-keys default. An override naming a figure with no advice is REFUSED,
  not silently inert.
- **`SCHEMA_VERSION` is 2 and `READABLE_VERSIONS` is `(1, 2)`.** A v1 document is a v2 document
  with no reference meshes and every bound `MANUAL` — which is what a hand-written case type is —
  so the artefact GREW rather than being replaced. Writing is always the current version.
- **Provenance is recorded, not merely consulted**: a `ReferenceMesh` carries its id, the mesh,
  the `.provenance.json` the numbers came out of, the date and the figures themselves, every path
  repo-relative. A reference recorded as a path alone says nothing once that mesh is regenerated.
- **Nothing re-measures a mesh.** `measure_reference` goes through
  `mesh_shape_stats.read_shape_summary`, the same single owner the verdict consumes, so a
  threshold cannot be derived from one reading of a mesh and judged against another.
- **`tools/PreProcessor/save_case_type.py` is a HEADLESS host and that is deliberate**, like
  `HYBMESH_CASE_TYPE` beside it: #162 owns the picker and the apply flow, and a dialog authored
  here would be chrome for that ticket to unpick.
Gated by `tests/test_case_type_author.py` (ten checks and nine automated injections, each
asserting the mutation is well-formed, that the named checks redden and that no other does; the
counts are that file's own docstring's and are not restated here).
  Why: `docs/design_notes/gui.md`, "A THRESHOLD IS MEASURED FROM A REFERENCE MESH".

**A CASE TYPE CARRIES ITS CONFIG FIELDS AS A SPARSE OVERLAY, AND A MOVED FIELD DEVIATES THE
VERDICT** (`services/case_type_fields.py` = the vocabulary, the apply, the deviation and the
diff, Qt-free; `tools/PreProcessor/show_case_type.py` is the inspecting host; #162, parent
#158). #160 and #161 grade a mesh after the fact and neither says how to PRODUCE one, so an
operator still configured 104 fields to mesh a problem class they recognise. A case type now
carries the settings that produced its reference mesh, and the tool notices when the operator
moves away from them.
- **SPARSE IS THE DESIGN, NOT AN OPTIMISATION.** A case type records only the fields it takes
  a position on; a field it does not mention takes the ordinary `MeshConfig` default. A full
  snapshot would make every case type in the tree disagree with the model the day a mesher
  parameter is added, and nobody could tell which disagreement was an opinion (user story 36).
- **THE CAPTURE IS A SUBTRACTION, and that is what makes it sparse without a tick list.** The
  maintainer built a case they are happy with, so the fields they MOVED OFF THE DEFAULT ARE the
  fields they have an opinion about — `capture_differences`, three of 74 for the shipped
  O-grid. `--field` is the one way a field sitting at a default becomes an opinion.
- **WHAT MAY BE OWNED IS DERIVED FROM THE TWO MODELS, never listed**: the SCALAR dataclass
  fields of `MeshConfig` and `TopologyModel`, minus a declared `EXCLUDED` set stating its
  reason per entry. A hand-written vocabulary would be a second declaration of the mesh
  parameters, which is what `models/mesh_config_keys.py` exists to have removed.
- **THREE KINDS ARE NOT OWNABLE, and each is somebody else's subject.** CONTAINERS (the
  geometry list, the roles map, the group BC map) are the operator's own drawing. BINDINGS —
  every `*_geom` / `*_segs` topology parameter, excluded by SUFFIX so a fifth family is covered
  the day it lands — are stable segment ids into the MAINTAINER's geometry and cannot carry
  over; roles are #164. PER-PROJECT STATE (`output_filename`, `mesh_topology_file`,
  `bc_configured`, `topology.detached`) is a fact about one project. A name outside the
  vocabulary is REFUSED on load, and the refusal says WHICH of those it is rather than
  "unknown key" for a field that exists and is deliberately excluded. **`capture` checks the
  names BEFORE reading any of them off a config**, which is the `--field` door: an unchecked
  read raises a bare `AttributeError` no host catches, so the maintainer got a traceback where
  that sentence was written for them.
- **THE FAMILY IS A FIELD LIKE ANY OTHER**, under a `topology.` prefix in the same flat
  overlay, because picking a case type has to answer "which family, with what parameters" as
  well as "what size cells". One vocabulary, one apply, one deviation report.
- **TWO FLOATS ARE THE SAME VALUE WHEN THEY RENDER THE SAME AT THE `.dat` WRITER'S OWN
  FORMAT** (`DAT_PRECISION`, `%.6g`, which is what `models/mesh_config_io.py` writes), NOT
  when they sit inside a tolerance. Both forms of a tolerance were wrong: floored at 1.0 it
  became an absolute 1e-6 and missed `bl_initial_thickness` 0.001 -> 0.0010008; unfloored,
  no single relative value separates `%.6g`'s own rounding error (up to 5e-6) from its
  finest expressible change (1e-5) by more than a factor of two. Rendering answers both
  ends, and the gate asserts both. **It is ONE format again since #163**: `FINER_PRECISION`
  gave `length_unit_metres` the writer's own `%.10g`, because it IS metres-per-grid-unit —
  `Linf`, and so the Reynolds number — and #163 made that field UNOWNABLE, so the map named a
  field no overlay can hold. It left with its subject, and the rule has to come back if a unit
  field ever becomes ownable again.
- **DEVIATION IS A COMPARISON, NOT A HISTORY.** `deviations` asks what the overlay says and
  what the config says NOW, over the owned fields and ONLY those — so a field the case type has
  no opinion about can be changed freely (user story 21), and putting an owned one back removes
  its deviation (user story 20).
- **DEVIATION DOWNGRADES STANDING, NEVER WITHHOLDS.** The STATE is unchanged, the verdict is
  MARKED, the moved fields are NAMED rather than counted, and the only thing that moves is the
  log grade: `DEVIATED_FLOOR` lifts a deviated `usable` from INFO to WARNING, every other state
  being already at least that. Withholding would teach operators not to touch anything.
- **IT IS CARRIED ON EVERY VERDICT PATH**, including the ones settled before a figure is read:
  a folded mesh produced with the settings changed is still a folded mesh, and which settings
  moved is the first thing anybody asks about it.
- **THE HOST SUPPLIES THE CONFIG, because only the host has it.** `run_report(..., config=)`;
  `None` means nobody could say and the deviation list is then EMPTY rather than invented. The
  GUI passes `global_mesh_config` (the model the panel synced before the run) and does NOT
  reach it through a `getattr` default, which would make a rename silence the marking instead
  of failing. **The headless runner passes a COPY taken BEFORE its own overrides**: `_run_mesh`
  forces `export_vtk` (and `export_starcd`) on and both are ownable, so judging the object it
  wrote would report a deviation on every headless run, naming a field the operator never
  touched and cannot put back. Gated by check 11, read off the runner's AST.
- **A PATH IS NOT A KIND, here too**: `read_config` classifies through
  `services/project_file_kind` — a `.dat`, a `.hws` workspace or a pipeline script — so this
  seam cannot disagree with `main.py` about what a file is.
- **`SCHEMA_VERSION` is 3 and `READABLE_VERSIONS` is `(1, 2, 3)`.** A v2 document is a v3
  document that takes a position on no field, which is what every case type authored before
  #162 is; the artefact has been WIDENED twice rather than replaced. A case type owning nothing
  writes NO `fields` section, so a round trip returns the document it was given.
- **`show_case_type.py` is a HEADLESS host**, like `save_case_type.py` beside it and for the
  same reason: the GUI has Trial and Generate (#166) but no picker and no author. It answers the three
  questions an operator may ask of borrowed expertise — which fields does it own, what differs
  between two case types, and how far has my case moved.
Gated by `tests/test_case_type_fields.py` (eleven checks and ten automated injections, each
asserting the mutation is well-formed, that the named checks redden and that no other does; the
counts are that file's own docstring's and are not restated here).
  Why: `docs/design_notes/gui.md`, "A CASE TYPE'S CONFIG FIELDS, AND WHAT A DEVIATION COSTS".

**ONE CASE TYPE FITS A GEOMETRY AT ANY SCALE, AND A PHYSICAL PARAMETER IS CONFIRMED RATHER
THAN APPLIED** (`services/case_type_scale.py`, Qt-free;
`tools/PreProcessor/apply_case_type.py` is the applying host; #163, parent #158). #162's
overlay carries numbers that fit the geometry it was authored on, so a case type built on a
1 m body hands a 10 mm one the same 0.02 surface size and meshes it in two cells (user story
22). The whole ticket turns on a distinction a single number cannot carry: which of a case
type's lengths belong to the SIZE of the body and which to the FLOW over it.
- **THE RULER IS DECLARED BY ROLE AND MEASURE, AND MEASURED — NEVER TYPED.** A case type names
  a ROLE (`MeshConfig.geom_roles`'s own vocabulary, with `body` for the DEFAULT role that model
  spells as the ABSENCE of an entry) and one of four MEASURES (`extent`, `x_extent`, `y_extent`,
  `diagonal`), and `CharacteristicLength.derive` is the ONLY constructor: it reads the length
  and the CENTRE off the role-bearing geometries of whatever drawing it meets — the
  maintainer's at `save_case_type.py --characteristic body.extent`, the operator's at apply.
  Same rule as #161's threshold: a figure somebody typed is a figure nobody can trace. What is
  DECLARED is which curve the sizes are about, which no measurement can decide.
- **FOUR KINDS OF LENGTH, AND WHICH FIELDS ARE LENGTHS IS DERIVED.** A field is a length
  exactly when its `FieldSpec.kind` is `sci` — this repo's existing declaration of a physical
  length, the one that decides the unit suffix (`field_spec.LENGTH_KINDS`). What each one MEANS
  is a judgement nothing records, so `LENGTH_KIND` declares it per field: `SIZE` scales by the
  ratio, `X`/`Y` are POSITIONS and map AFFINELY about the ruler's own centre, `PHYSICAL` never
  scales. **A `sci` field missing from that map FAILS the gate**, in both directions — the
  default would otherwise be "scale it", which is the wrong default for the one field that
  matters most.
- **A COORDINATE IS NOT A SIZE.** `DOMAIN_X_MIN` is a position in the geometry's frame, so
  multiplying it is right only for a body at the origin. The reference centre travels in the
  declaration and the operator's is re-derived, so a case type authored on a body at the origin
  fits a drawing whose body sits at (500, 300).
- **A PHYSICAL PARAMETER IS CARRIED UNSCALED AND CONFIRMED ON EVERY APPLICATION.** The
  boundary-layer first cell height is set by the Reynolds number and the target y+; scaling it
  with the body would claim a bigger aerofoil has a thicker boundary layer. `PHYSICAL_WHY`
  states that reason per field and it is PRINTED, because "confirm this number" with no reason
  is a dialog people learn to dismiss. **`Application.apply` RAISES while any is unanswered** —
  user story 23 made structural rather than left to a dialog a second host could skip — and a
  confirmation may carry the operator's OWN value, so confirming and adjusting are one act.
  Confirming a field that is not one of the asked-about parameters is REFUSED: an edit wearing
  a confirmation's name would be invisible to the deviation report. **A physical parameter the
  case type does not CARRY is not asked about**, and that is the sparse overlay working rather
  than a hole in the question: nothing is inherited, so the operator's own value survives
  untouched. `--field bl_initial_thickness` is how a maintainer who MEANS the default records
  it, and then it is asked about like any other.
- **IT USES THE LENGTH-UNIT SYSTEM RATHER THAN DUPLICATING IT.** The geometric factor is a
  ratio of two lengths each measured in its OWN project's grid units, so the unit cancels and
  nothing converts. The physical parameter is the opposite case: `services/units.py` records
  that `length_unit_metres` IS metres-per-grid-unit, and a first cell height means a height in
  METRES, so carrying one from a metre case into a millimetre drawing multiplies by the ratio
  of the two unit factors — the existing rule applied where it has always applied, not a second
  one. **The three `length_unit*` fields are therefore NOT ownable** (`EXCLUDED`): a case type
  that imposed its author's unit would RELABEL the operator's geometry rather than fit it,
  which is the 1000x error this repo has lost a run to. **That is the ONE place the artefact
  was NARROWED rather than widened**, so a v3 document that OWNED one is REFUSED on load — and
  the refusal carries the remedy (delete that entry from its `fields` section), or an operator
  holding such a file is stuck. Gated as a refusal, so the claim is not wider than the assert.
- **A RULER THAT CANNOT BE READ REFUSES, and never falls back.** No geometry bearing the named
  role (the refusal names the role and the roles that ARE borne), a geometry file that will not
  load, a role-bearing set with no extent, an unknown role or measure, a recorded length of
  zero. A guessed ruler produces a mesh that looks right and is the wrong size, which is the
  failure this exists to remove. The geometry goes through
  `geometry_service.load_points_dat`, the tree's one validated loader, and `measure_role` takes
  the paths AS THE CONFIG HOLDS THEM — `models/mesh_config_io.py` resolves every geometry token
  to an absolute path as it loads, and a second resolution rule here could only disagree.
- **DEVIATION IS MEASURED AGAINST THE FITTED NUMBERS, not the authored ones**
  (`fit`, called by `case_type_verdict.run_report` and by
  `show_case_type.py --config`, which also prints the reason `fit` hands back when the
  ruler cannot be read — a verdict only logs it). The value a case type has an opinion about on THIS drawing is
  the one its ruler scaled to; comparing against the authored number would mark every geometric
  field of every rescaled run as the operator's own edit. A case type with NO ruler, or one
  whose ruler this drawing cannot provide, falls back to the authored overlay — not an error,
  since no ruler means nothing was scaled. **`fit` RETURNS that reason as well as logging it,
  and both readers SAY it**: `run_report` appends a line to the verdict and
  `show_case_type --config` prints one, because a deviation list computed on unfitted numbers
  with nothing said is this file's own failure mode, a plausible wrong answer rather than an
  error.
- **`SCHEMA_VERSION` is 4 and `READABLE_VERSIONS` is `(1, 2, 3, 4)`.** A v3 document is a v4
  that declares no ruler and fits every drawing at 1:1 — which is the behaviour it has always
  had — and still asks for its physical parameters to be confirmed, that question being about
  physics rather than scale. A case type declaring none writes NO `characteristic_length`
  section. The artefact has now been WIDENED three times rather than replaced.
- **ONE SEAM, SIX FILES**, every cut the ~500-line standard: `case_type_scale.py` is
  re-exported from the document (`CharacteristicLength`, `Application`, `plan`) so no caller
  learns a new name, and the dependency still runs one way — scale -> fields -> figures,
  document -> scale, verdict -> scale.
- **`apply_case_type.py` is a HEADLESS host**, like the two beside it and for the same reason:
  the GUI has Trial and Generate (#166) but no picker and no role panel. Without `--confirm` it exits 1, names
  the unconfirmed parameter and writes nothing; `--confirm NAME` accepts the offered value and
  `--confirm NAME=VALUE` supplies the operator's own. **There is deliberately no flag that
  confirms everything**, because a case type's whole risk is that somebody else's Reynolds
  number is not yours.
Gated by `tests/test_case_type_scale.py` (twelve checks and nine automated injections, each
asserting the mutation is well-formed, that the named checks redden and that no other does;
the counts are that file's own docstring's and are not restated here). Its last check runs the
REAL binary three times — the case type at 1x, at 100x, and a CONTROL that scales the first
cell height too — and the control's published figures match the 1x run's to within 1% while
the correctly fitted run's differ by more than 10x. That control is what makes the end-to-end
leg falsifiable without an injection.
  Why: `docs/design_notes/gui.md`, "ONE CASE TYPE FITS A GEOMETRY AT ANY SCALE".

**ROLES BIND A CASE TYPE TO THE OPERATOR'S OWN CAD, AND NO AUTHORING ID SURVIVES**
(`services/case_type_roles.py` = the slots, the plan, the resolution and the refusals;
`services/case_type_guess.py` = the pre-selection; both Qt-free;
`tools/PreProcessor/apply_case_type.py` is the applying host; #164, parent #158). #163's gate
named this gap: an overlay naming a family could not be written to a `.dat` on its own, every
family but the H-grid refusing to build a document with no geometry to bind to.
- **A BINDING IS NEVER COPIED, IT IS DERIVED.** A binding is a stable `SegmentModel.id` into the
  MAINTAINER's geometry and the operator's segments have entirely different ids, which is why
  `case_type_fields.EXCLUDED` rules every `*_geom` / `*_segs` parameter unownable BY SUFFIX. What
  travels is the ROLE; `RolePlan.bind` writes ids read off the operator's own `BindingContext`
  and reads none from the case type, because it carries none.
- **THE ROLE IS PER SEGMENT, which `MeshConfig.geom_roles` is not.** That map is keyed by
  geometry FILE and answers a different question (does this curve grow a BL, is it a seed). An
  assignment here is a set of `(geometry, segment id)` pairs; naming a whole geometry is the
  convenience spelling of "every segment it carries". `geom_roles` is still READ as EVIDENCE for
  the guess, never as the assignment.
- **WHICH ROLES A FAMILY NEEDS IS DERIVED FROM `TopologyModel`**, by the family's prefix and the
  `_segs` suffix, so a fifth family's roles arrive with its parameters. Only two things are
  DECLARED, each with its reason: `SLOT_ROLE` (the role word a slot token means — `body`,
  `farfield`, `seam`, the one vocabulary an operator picks from, #158's own) and `OPTIONAL` (the
  C-grid's far field, which the family GENERATES when left unbound). A slot token nobody
  classified is REFUSED rather than defaulting to itself, and the gate checks both directions.
  **No family module was modified** — `.claude/rules/gui-topology.md` is full, and this mechanism
  belongs to the case-type seam; the families keep their own role words for their own refusal
  prose (`SECTION_ROLE` is "aerofoil").
- **THE TOOL MAY GUESS; THE OPERATOR CONFIRMS, AND THE REFUSAL IS STRUCTURAL.** `bind` raises
  while any pre-selected role is unanswered and names EVERY one — the shape
  `case_type_scale.Application.apply` gives a physical parameter, for the same reason: a prompt
  can be skipped by a second host, a raise cannot. A wrong guess reaching the mesher is a mesh
  that generates, exports and looks right with the far field's conditions on the body.
- **THE GUESS RANKS BY ENCLOSED AREA, NEVER BY DRAWING ORDER** (excluded by decision in #158;
  this repo has a USER-REPORTED defect where drawing order rather than click order decided a
  result). It abandons the RANKING whole when the candidate outlines and the slots do not
  line up — but a role the drawing itself already records (`geom_roles`: `farfield` or
  `wall`) survives that, because EVIDENCE is not a ranking and the count says nothing about
  it; it is confirmed like any other offer. It offers nothing for an OPTIONAL slot — a list
  the family documents as generated is not a question, and guessing one would block a run
  for a curve nobody asked to bind. A refinement SEED and a no-BL obstacle are not outlines
  a topology binds and are kept out of the pool, or every slot shifts by one.
- **EVERY PROBLEM AT ONCE** — every missing required role and every unresolvable position in one
  refusal, which is the DERIVED side of #138's rule for `topology_model.broken_bindings`. A
  family's own `plan` still stops at the first, because it answers "can this run?".
- **THE FOUR QUESTIONS ARE ASKED BY THEIR OWNER.** Whether a named geometry is loaded, carries
  per-segment data and is a closed loop goes through `topology_binding.outline_problem` — the
  helper three families spelled themselves until the third copy silently dropped the one clause
  a user can act on. This module supplies only the clause that is its own (`CLOSED_NOTE`: every
  family that binds to the CAD binds a ring). The closed question arrives WITH the helper and is
  generic; a family's own precondition is still #165's.
- **THE STORED ORDER IS THE GEOMETRY'S OWN**, filtered from `seg_ids` rather than kept as typed:
  a list out of the outline's order binds every wall after the first to a different stretch of
  curve with every id still resolving (`topology_ogrid_binding.order_problem`).
- **ONE SEAM, EIGHT FILES**, every cut the ~500-line standard: the pre-selection split off at
  565 lines and is re-exported from the roles module, so no caller learns a new name. What stayed
  is everything that ACTS on a guess, so the confirmation and the thing confirmed cannot drift.
- **`apply_case_type.py` gains `--role ROLE[=GEOM[:SEGS]]`**, the grammar `--confirm` already
  has: a bare name accepts the pre-selection, `ROLE=GEOM` binds every segment that geometry
  carries, `ROLE=GEOM:1,2,3` binds those. The roles a case type needs are PRINTED before any is
  assigned and before the physical parameters are confirmed, so an operator running it bare sees
  which curves they are being asked for rather than a refusal about a first cell height.
Gated by `tests/test_case_type_roles.py` (twelve checks and eight automated injections, each
asserting the mutation is well-formed, that the named checks redden and that no other does; the
counts are that file's own docstring's and are not restated here). Its last check runs the REAL
binary on a drawing whose segment ids are 17-20 and 31-34, from the config's OWN directory —
the writer spells a geometry outside the repo relative to the config beside it, and the mesher
opens what the line says relative to its own working directory.
  Why: `docs/design_notes/gui.md`, "ROLES BIND A CASE TYPE TO THE OPERATOR'S OWN CAD".

**WHY THIS FILE AND NOT A THIRTEENTH, recorded because the opposite call has precedent.** This
file's thesis is "is a file one stage leaves on disk still correct when the NEXT one reads it",
and grading is a different question — which is the exact argument #153 used to split
`mesher-quality.md` out of `mesher-multiblock.md`. The difference is budget and size: that split
happened because the source file had 197 characters of slack, while this one had 37,484 before
the entry landed (60,000 - 22,516, re-derivable) and the
whole entry is ~3.4k. A rule file taken for a tracer bullet would be the thinnest in the tree, and
`services/case_type*` would still need a glob beside `services/mesh_shape_stats*` because the
judge reads what that reader returns. **#162 was named as the cheap moment and was MEASURED
instead of assumed**: its config overlay, deviation and diff came to ~3k, and the thirteenth file
was not taken then. **#164 is where the budget ran out, and that is now a MEASUREMENT rather than
a forecast**: its roles entry left this file 1,598 characters of slack (2026-10-02, in
CHARACTERS — `wc -c` reports BYTES and the first draft of this sentence quoted those), which
is under one block's worth — #137's own threshold was 73 and #153's 197, and this is the same order. So the
next block here is a NEW RULE FILE, not a squeeze, and #165 and #166 should expect to take it;
`gui-topology.md` carries the identical sentence for the same reason.

## Named blind spots

One list per rule file (`docs/agents/rule-file-style.md` rule 5). These are this file's coverage
limits — what a gate does NOT check — as distinct from the caveats stated with the rules above,
which are capability refusals.

- **Nothing judges whether a TOLERANCE FACTOR is right.** #161 closed the half of this that was
  about the shipped case type — its bounds are now measurements times a factor, with one
  deliberate override — and what is gated is that a bound really IS the product, not that the
  product is a good place for a bound. #168 is what corrects a misjudged one with evidence.
- **The "neither host grades" check reads SOURCE**, so a third host that grew its own grading is
  invisible to it.
- **The GUI leg drives `_on_mesh_gen_finished` with a recording stand-in for the main window.**
  That the verdict is wired to a button and rendered by the log panel is not checked here.
- **A CASE TYPE WITH NO RULER CANNOT CONVERT A PHYSICAL PARAMETER.** `unit_metres` is recorded
  ON the characteristic length, so a case type declaring none — every v3 document, and any v4
  authored without `--characteristic` — has no authoring unit to convert from, and its physical
  parameters cross a unit change UNCONVERTED. The operator is still asked, and the
  confirmation reports the metres value in THEIR units, so an unconverted one shows up as the
  absurd length it is. Pinned by the gate; the remedy is to declare a ruler, not to invent a unit.
- **THE RULER IS PER GEOMETRY EVEN THOUGH THE ROLE IS NOT.** #164 landed the per-SEGMENT role
  and derives a binding from it, but `case_type_scale.measure_role` still measures whole files
  bearing a `MeshConfig.geom_roles` role. The measure is a pure function of a point set either
  way, so narrowing it to the role-bearing segments changes nothing on any shipped case — which
  is why it was not done, and is the reason this stays a named limit rather than a defect.
- **NOTHING JUDGES WHETHER THE DECLARED RULER IS THE RIGHT CURVE.** A case type naming the
  `body` role on a drawing whose far field also bears it (which is what a `MESH_MODE 1` case
  with two plain `GEOM_FILE` lines looks like) measures the pair — consistently at both ends,
  so the ratio still scales, but it is not the chord the maintainer meant. The refusal is for
  a role NOBODY bears, never for one borne by something unintended. The shipped case type
  therefore declares no characteristic length at all.
- **THE LENGTH CLASSIFICATION IS A JUDGEMENT.** That `bl_initial_thickness` is physical and
  `surface_mesh_size` is not is argued in `case_type_scale.py`'s docstring; what the gate
  measures is that every `sci` field HAS a judgement, not that each one is right.
- **NOTHING JUDGES WHETHER A CONFIRMED ROLE IS THE RIGHT CURVE.** #164 closed the gap that an
  overlay naming a family could not be written to a `.dat` — the bindings are derived from roles
  and `test_case_type_roles.py` check 12 meshes one through the real binary — but an operator who
  confirms the far field as the body binds exactly that. Only the family's own pre-flight refusal
  (#165) will notice; #163's gate still carries no family in its round-trip leg, which is now a
  property of that gate rather than of the artefact.
- **THE EXCLUSION LIST IS A JUDGEMENT.** That `output_filename` is per-case and
  `bl_growth_rate` is not is argued in the service's docstring and pinned by the gate; nothing
  measures that the line is in the right place.
