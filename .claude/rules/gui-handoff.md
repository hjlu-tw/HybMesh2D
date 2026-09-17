---
paths:
  - tools/PreProcessor/gui/app/services/mesh_bc_audit*
  - tools/PreProcessor/gui/app/services/project_file_kind*
  - tools/PreProcessor/gui/app/services/mesh_grid_lookup*
  - tools/PreProcessor/gui/app/services/mesh_shape_stats*
  - tools/PreProcessor/gui/app/views/panels/mesh_stats_panel*
  - tools/PreProcessor/gui/app/models/mesh_output_names*
  - tools/PreProcessor/gui/app/controllers/mesh_export_ctrl*
  - tools/PreProcessor/gui/app/controllers/mesh_layers_ctrl*
  - tools/PreProcessor/gui/app/controllers/solver_ctrl*
  - tools/PreProcessor/gui/app/models/segment.py
---

# GUI file hand-off rules

Loaded on demand when the mesh-BC audit, the project-file classifier, the case-grid lookup,
the shape-summary reader, the Mesh Statistics panel, the mesh output-name resolver, the
mesh-export / Mesh-layers / solver controller, or the segment model is read — **10 files**,
verified to match. **Rules only** — the rationale (the
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
Gated by `tests/test_mesh_shape_panel.py`: a negative control that HAS computable per-cell shape
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

