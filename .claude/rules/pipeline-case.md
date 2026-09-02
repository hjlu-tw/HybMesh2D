---
paths:
  - tools/PreProcessor/gui/app/services/case_*
  - tools/PreProcessor/gui/app/services/solver_case*
  - tools/PreProcessor/gui/app/services/restart_points*
  - tools/PreProcessor/gui/app/services/pipeline*
  - tools/PreProcessor/gui/app/services/stl3d*
  - tools/PreProcessor/gui/app/services/ib_handoff*
  - tools/PreProcessor/gui/app/services/contour_render*
  - tools/PreProcessor/gui/app/models/pipeline_config*
  - tools/PreProcessor/run_pipeline.py
  - run_pipeline.sh
---

# Pipeline and solver-case rules

Loaded on demand when a case / solver-case / pipeline / STL3d service, the pipeline schema, or
the headless pipeline entry point is read. Rules only: the rationale — the dated acceptance runs
against the real `unicones` binary, the measurements, the injections, the reversals and the named
residues — is `docs/design_notes/pipeline.md`. Read that note before overruling a rule here, and
when a rule changes update BOTH.

These rules also govern files OUTSIDE the globs above, which cannot hand a reader the text:
`controllers/pipeline_ctrl.py`, `controllers/pipeline_io_ctrl.py`,
`controllers/case_disposition_ctrl.py`, `workers/solver_run.py`, `views/case_dir_dialog.py` and
`views/panels/restart_chooser.py`. The tripwire table in `CLAUDE.md` is what makes them reachable;
the globs are the convenience.

### Full Pipeline (CAD → mesh → solver → results, one action)

**One unified JSON script drives the whole chain**, and the GUI and the headless CLI share both
the schema and the stage logic.

- **`models/pipeline_config.py`** (`PipelineConfig`, Qt-free) is the unified schema
  (`cads`/`mesh`/`solver`/`stl3d`/`results`, each mapping 1:1 onto
  `ProjectModel`/`MeshConfig`/`SolverConfig`/`Stl3dConfig`) plus converters, at
  `PIPELINE_FORMAT_VERSION` (v2). **`cads` is a LIST** — one entry per geometry, so a multi-body
  case round-trips; the singular `cad` key is still read and exposed as a property for pre-v2
  scripts. `from_workspace_dict()` turns a `.hws` into a runnable script, so `run_pipeline.sh`
  accepts either. Examples: `config/pipeline/naca_demo.json`, `multi_element_demo.json`.
- **The stage set is declared ONCE and the two hosts are adapters**
  (`services/pipeline_stages.py`, Qt-free, stdlib only). The four stages — resample · immersed
  solid · mesh · solver — are implemented twice (`pipeline_runner` blocking, `pipeline_ctrl`
  chained on QThread `finished_signal`), and both build their plan and their `Stage i/N` labels
  from `plan()` / `label()`. Deliberately **data, not a base class**: the one thing that
  legitimately differs is how the hosts WAIT. `PipelineConfig.stl3d_skip()` joins
  `cad_skip`/`solver_skip`, so "will this stage run?" has one shape for all four. Until this
  module nothing knew the SET (candidate 6a): `Stage 1/3`…`3/3` was hand-written at 8 sites while
  four stages existed. Gated by `tests/test_pipeline_stages.py` (ten failure modes, all
  injection-verified in-test), which carries two rules for gates in this area: **both directions
  or it is not a gate**, and **order is recovered, not assumed** — the GUI's chain is read as a
  reachability graph over
  `self._pipe*` **references**, since a continuation handed over as an attribute is invisible to
  a call-only walk. Two smaller ones: an injection that makes the source **fail to parse** looks
  exactly like the check working, and a check with an **exemption marker** is an escape hatch for
  whoever next trips it.
- **`services/pipeline_runner.py`** (Qt-free, blocking) runs the 3 CLI stages via subprocess
  (surface_resampler → HybMesh2D → getPGrid→unicones); `run_pipeline()` returns the artifact paths.
- **Producing a phi field is not the same as wiring one up** (`services/ib_handoff.py`, Qt-free):
  `link_phi_to_solver()` is the one owner and all three hosts call it. STL3d writes a *Tecplot*
  field while the init DLL reads a *headerless* `phi.dat` with the STL3d grid spec compiled into
  it, and that conversion lived in a Qt method no headless runner could call: the runner
  collected the phi into `out["phi"]` and passed it **nowhere**, Run All had no IB stage at all,
  and both fell back to whatever `work/phi.dat` the reused case dir held — the previous geometry's
  solid, converging to a believable answer for the wrong shape. Three rules:
  **`PHI_HEADER_LINES` is checked against the `skiprows=` its own reader uses** (one number, not
  two guesses); **the phi field and the init DLL are ONE fact, so it takes over both or neither**
  (the DLL can only read the field this stage traced, so a mixed pair is a wrong answer rather
  than an error — only when both are blank does the stage supply both, and naming one keeps both
  and warns); **`replace` is the difference between the callers** (the GUI overwrites a field
  computed *now*; the headless runner fills blanks only, as `_run_solver` already does for
  `.vrt`/`.cel`/`.bnd`). It deliberately does **not** decide whether the solve has an immersed
  solid: `immersed_solid` is the CALLER's declaration and a stage may not overrule it —
  `send_stl3d_to_solver` turns it on because a button is allowed an opinion a stage is not. Gated
  by `tests/test_pipeline_ib_handoff.py`, which drives the real conversion, proves the chain by
  AST, and **compiles the generated DLL** (`stage_dll` returns `""` with a mere WARNING on a
  compile failure, so a source that does not build degrades silently to "no init DLL").
- **`services/solver_case.py`** (Qt-free) owns the case dir
  (`results/solver/<name>/{work,grid,dll}`) for both the GUI worker and the headless runner, and
  answers **where a case lives** (`case_root_for` / `work_dir_of`). **The grid stem is the
  RESOLVED case name, not the requested one** — auto-versioning renames the *directory*, and a
  stem left on the old name writes `case.grid` into `case_002/`, which runs, so it stays
  invisible until one directory holds two 1.3 MB grids distinguishable only by what `input.in`
  references (USER-REPORTED 2026-08-13). **`prepare_case_dir` is the ONE place that makes a path
  in `input.in` relative to the work dir**: grid/bc as `../grid/<case>.*`, IBM DLLs as
  `../dll/*.so`, a BC type-11 DLL as `./x.so`, the phi field staged under a fixed name.
  - **Restart references are rewritten, not passed through** (#25, USER-REPORTED 2026-08-20):
    they were the only paths nothing touched, so the deliberately absolute autofilled path
    reached the solver verbatim and a GUI restart errored out while an *exported* case ran.
    `restart_refs_for_work_dir` rewrites an **absolute path to an existing file** (inside `work/`
    → bare basename; elsewhere → out and back) and passes a blank, an already-relative or a
    non-resolving value **straight through** — a wrong path must surface as the solver's own
    error. Three load-bearing details: the dump is **referenced, never copied** (largest file in
    a case); the relative form is **out and back**, because the panel computes it from the case
    *name* before auto-versioning may rename the directory; and the result is **returned into
    `generate_input_in` (`zdump_rel`/`convg_rel`), never written back onto `cfg`**, since `cfg`
    is what the `.hws` and pipeline script are saved from and a work-dir-relative value there
    resolves to nothing from the next work dir. Gated by `test_restart_paths_relative.py`.
  - **The last three of the nine quoted paths got the OPPOSITE answer, and the difference is
    SIZE** (#29): `mpi_comm_map_fn`, `cfl_schedule_fn`, `probe_points_def_fn`.
    `table_refs_for_work_dir` **copies** the file into `work/` and quotes the bare name — a table
    is small, and a case that does not hold its own inputs is the problem. Three shapes: a **bare
    name** is emitted unchanged but still **reserves its basename** (or a later field's absolute
    path with the same basename lands on the file it quotes); an **existing file** is staged under
    a collision-safe basename; anything that does **not** resolve is emitted unchanged. Copy,
    never move, never hard-link. **The claim is exactly this narrow: every quoted path that
    RESOLVES is work-dir relative.** A value naming nothing stays absolute deliberately, as does
    a table named like a run output (`^binDump`, `.plt`); do not upgrade this to "every quoted
    path" without re-reading `_stage_table`. Two neighbours keep up: `case_export` no longer
    reports a file `input.in` REFERENCES as an unrecognised skip (the allow-list is deliberately
    **not** widened — a reference is a fact about this run, a suffix a glob over every future
    one), and `case_archive` reads the previous `input.in` for names no list can hold. What a
    work dir already means lives in `case_files` (`WORK_STAGED`, `staged_bare_names`), never
    restated. The reservation asks whether the file EXISTS, which
    is both more precise and what makes the counter TERMINATE (`input.in` excepted, being written
    *after* staging). Resolvers live in `services/case_input_paths.py`; gated by
    `test_input_in_staged_paths.py` (10 properties, 42 assertions, all injection-verified).
- **A restart continues in the SAME case dir, and must not write over what it resumed from**
  (`services/case_archive.py`, Qt-free; #26, USER-REPORTED 2026-08-20).
  `archive_previous_outputs()` moves the previous run's outputs into a fresh `work/prev_<NNN>/`
  before this run writes anything. **Two facts about the solver decide the shape, both measured
  on the real binary.** (1) The restart reference must be a **BARE name in the work dir**, or the
  solver derives a per-zone path into a directory that does not exist and dies with
  `Can't open file`. (2) It must **DIFFER from the solver's own output dump name**
  (`binDumpZ.dat` + the `-t` tag), which is exactly the file a GUI restart resumes from — so
  *every* same-folder restart used to rewrite its own restart point in place.
  - **The zone dump moves too, and `work/` keeps a bare-named HARD LINK to it.**
    SUPERSEDES #26: the dump used to stay out in `work/`, so the archive was never complete (#30).
    One inode satisfies both halves at ~0 bytes (measured 24352 → 24356 KB across a 1597 KB dump).
    **This is the ONE place this repo's "a hard link is not the cheap version of a copy" rule
    flips, and for that rule's own reason** — a zone dump is never edited.
    Why: `docs/design_notes/pipeline.md`, "flips, and for that rule's own reason".
    A stale link is retired **by INODE** (`_archived_inodes`) — unlinked, never moved. A file
    already named `.prev_NNN` that is *not* a link is filed into the archive it is named for, which
    is how a pre-#30 case upgrades.
  - **Every archived file ends in `.prev_<NNN>`** (`case_files.archive_name`): a trailing run tag
    is replaced, a name without one is appended to, a name already carrying a suffix is left
    alone. The tag is what the rename discards, so **`RUN.txt` is where it survives**.
    `is_run_output` **strips the suffix before matching**, because two patterns anchor on the END
    of the name (`\.plt$`, `^fort\.\d+$`); widening them would loosen them for every future name,
    seeing through our own suffix does not.
  - **An allow-list decides, not a glob**; that list and `ARCHIVE_DIR_PREFIX` live in
    `services/case_files.py`, which `case_archive` and `case_export` import **as peers** (facts
    about a case, not about an export). The inputs `prepare_case_dir` stages **stay**, or the
    resumed run restarts into nothing; a file **neither** list recognises stays put and is
    **named in the log**; **move, never copy**; **nothing is created when nothing moves**; and an
    exhausted counter archives **nothing** and says so, because giving up the other way is the
    exact destruction the archive exists to prevent.
  - **That refusal has a second instance, and the archiver used to commit the destruction it
    names** (#42): `…dat.cli` and `…dat.gui` — one output of one case run by the two hosts — both
    want `….prev_001`, and the second `shutil.move` landed on the first silently, reachable
    without misuse (headless, then a GUI run answering *Overwrite*, then a restart).
    `case_files.archive_name_collisions` asks it ONCE over the set about to move, in the module
    that owns the mapping, and **before the retire loop** — before ANY move — so a refusal is a
    no-op the user can retry. Refused wholesale, naming both files, the name they both wanted and
    the *reason* (that archiving drops the run tag, which the file names alone do not show). It
    does **not** claim the run continues "beside" the files it declined to move: the refusing run
    carries one of the two tags itself, so it overwrites the half of every pair sharing it — out
    of scope in #42, said out loud.
  - **The restart reference follows the file**: `restart_refs_for_work_dir(..., moved=)` consults
    the move map *before* the existence check, and it is the **one** thing that rewrites an
    already-*relative* reference. That is why #26 was blocked by #25.
  - **The disposition is one value, not a pair of booleans**: `solver_case.CASE_ARCHIVE` /
    `CASE_IN_PLACE` / `CASE_NEW_VERSION`, mapped to the two mechanical flags in one place
    (`case_dir_flags`), which **raises on an unknown value** — `(False, False)` is a real
    disposition, so a typo would otherwise run silently in a directory nobody chose.
  - **`case_export` had to learn to see the archive**: `plan_export` skipped every non-file entry
    silently. Each archive is walked as its own subdirectory with **nothing** allow-listed (every
    file in it is an output by construction), except the dump `input.in` quotes — which forced
    the reference match from BASENAME to the resolved path.
  - **Each archive carries a `RUN.txt`** (`services/case_run_note.py`, Qt-free — writer *and*
    reader, so the format round-trips): timestamp, run tag, what that run resumed from, the
    dump's archived name, and how far it got. Two must be RECOVERED rather than remembered — the
    tag is read off the file names *before* the rename, and the iteration count from the LAST ROW
    of the convergence history (the solver prints `Global Iteration count` to stdout, gone by
    archive time). Stored as `last_iteration` + `convergence_interval`, and **the two together
    recover the printed count** (`1990 + 10` = the 2000 the acceptance run measured).
    REVERSES #30/#31 (#43): both printed the bound `1990+`, stated in the gate as
    `[1990, 2000)` — a half-open interval excluding the value it claims to contain. What
    survives is that an *interrupted* run makes the sum an **upper** bound, which belongs in a
    tooltip rather than in a refusal to name the number; one home,
    `case_run_note.iteration_span`.
    Why: `docs/design_notes/pipeline.md`, "That arithmetic is a REVERSAL of what #30 and #31".
    **Keep the specimen** — a considered argument that survived two issues because its own
    evidence was never checked against it.
    An unreadable history reports **-1, never 0** (0 is a real cold-start answer), and
    `resumed_from` has three states for a sharper version of the same reason: `""` = cold start,
    **None** = "we could not tell", because rendering that as "cold start" would be a positive
    false claim. `RUN.txt` is the one archived file not ending in `.prev_<NNN>` (the archive's own
    record, not something a run produced); `case_export` names it as a skipped OUTPUT and does not
    ship it.
  - **The run tags are declared once**, in `case_files.RUN_TAGS` — a rename rule stripping a tag
    nobody writes silently does nothing.
  Gated by `tests/test_restart_archive.py` (10 properties against the real `prepare_case_dir`,
  export planner and dialog; #42's guard has its absence INJECTED with a negative control) **and
  by `test_case_export.py` check 16**, because the archive's behaviour proven in the archive's
  test says nothing about a planner nobody re-pointed at it. Acceptance: the real
  `prepare_case_dir` over the reported case, then the real `unicones` — **exit 0,
  `Global Iteration count 1000`** (a cold start reports 0), restart source byte-identical, archive
  intact. Residue named: #25's cross-case reference resumes correctly but leaves an empty
  `binDumpZ.dat.0` in the work dir.
- **bDecompose runs IN THE CASE**, in `grid/` (`workers/solver_run.py::_run_bdecompose`;
  classification in `services/case_files.py`; #37). It ran in the binary's own install dir, three
  ways worse than "the output lands outside the case": the stage **could not find its inputs by
  construction** (the para file names the grid and bc as BARE BASENAMES, which getPGrid writes
  into the case's `grid/`); the install dir made that **silent**, holding a `mesh_cartesian.grid`
  from one hand run, so a case NAMED `mesh_cartesian` decomposed the STALE one and ran MPI on
  another mesh's decomposition; and the answer file landed in a **shared, possibly read-only**
  location two runs would race on. Three rules:
  - **The answer file is NOT `para.in`** — a deliberate departure from the issue's proposed scope,
    because getPGrid owns `grid/para.in`, `case_export` ships it as `grid/getPGrid.in` and
    `run_case.sh --regrid` feeds it back, so sharing the name would silently replace getPGrid's
    answers. It is fed on **stdin**, so the name is ours: `case_files.BDECOMPOSE_INPUT`.
  - **`is_run_output` must NOT learn `mpi_*`, and this is measured rather than argued**: for the
    comm map the file bDecompose PRODUCES and the file the solver READS are the *same name*, and
    `case_input_paths._stage_table` asks `is_run_output` whether to stage a user-named table — so
    widening it silently undoes #29 for exactly the field #37 is about. The question is asked
    **per DIRECTORY**: `is_decompose_output` for `grid/`, `is_run_output` for `work/`. (An earlier
    write-up claimed the classifier reads `COMM_MAP_NAME`; it does **not**, it matches by pattern
    — the same every/all/only overclaim habit recorded against #25 and #29.)
  - **Filling `mpi_comm_map_fn` in is still the caller's**: the produced path is named in the log
    and nothing more, and #29's staging carries it. **`case_export` keeps shipping the comm map —
    and the first version of #37 BROKE exactly that**: the new `grid/` branch `continue`d *ahead
    of* `plan_export`'s `elif rel in referenced`, the branch whose own comment states the rule it
    was jumping. One condition fixed it (`rel not in referenced`), leaving `_is_output`'s
    precedence untouched. **The gate did not pin the wrong side, it never covered this side** —
    which decides the remedy: a check was ADDED, not corrected.
  **`_validate_solver_config` validates the binary too**: it never checked `bdecompose_binary` at
  all, and now refuses a blank, a missing file, and a **wrong executable format**
  (`services/paths.wrong_executable_format`; the shipped binary is x86-64 **ELF**, this dev
  machine arm64 macOS). That test is narrow on purpose: an unrecognised format answers False,
  because "we cannot judge this" must not be reported as broken, and the MACHINE word is not
  compared (Rosetta). Gated by `tests/test_bdecompose_in_case.py` (14 properties). **A shared
  decomposition needs nothing**: because the stage only NAMES what it produced, pointing
  `mpi_comm_map_fn` at one gets precisely #29's behaviour. Residues: the comm map is staged into
  `work/` only on the NEXT run (it still resolves, being relative); bDecompose's other outputs get
  no home in `work/`, because whether the solver wants them there is not knowable here; and a
  stale `grid/bDecompose.in` still ships as an input, the same fossil class as getPGrid's own
  `para.in`, recorded rather than fixed.
- **"Overwrite" and "empty this folder first" are two different answers, and the destructive one
  shows its work** (`services/case_clean.py`, Qt-free, plus the second half of
  `views/case_dir_dialog.py`; #33, DECIDED 2026-08-21). Reuse-in-place leaves a case a mixture of
  this run's output and the last one's — a defect class with **two defences and no fix**
  (`report_stale_ibm_artifacts`, `case_export_usage.unused_reason`). Rules:
  - **A separate button, never a redefinition.** The non-restart prompt is `Overwrite in Place` /
    `Clean and Run…` / `Archive Previous` / `New Versioned Dir` + Cancel — **four plus Cancel,
    #33's stated ceiling**, so the next answer to want a button is where this stops being a
    message box. The restart path reaches none of it (#31).
  - **`Archive Previous` is a REVERSAL of #31, on a ground #31 did not rule on.** #31 removed it
    because a restart stopped reaching the prompt, **not** because archiving is wrong for a
    non-resuming run; once `Clean and Run` exists the alternative is needed, or keeping previous
    results *in this folder* has no answer but splitting the case across two directories.
    Why: `docs/design_notes/pipeline.md`, "`Archive Previous` is a REVERSAL of #31".
  - **Measure, show, then delete — three steps, and the deletion is not one of them.**
    `plan_case_clean(work_dir)` builds a `CleanPlan` and touches nothing; the prompt renders THAT
    plan; `apply_case_clean` acts on the approved list and never re-reads the directory. This repo
    has the scar the separation is for (an `ls` and an `rm -rf` in one command destroyed ~40
    gitignored artifacts), and it puts a possibly huge deletion on the worker thread.
  - **Reuse the classification, do not glob.** A file neither `is_run_output` nor `WORK_STAGED`
    recognises is **kept and named in the log**, and so is a directory that is not an archive (an
    `isfile` guard that silently passes over a folder is the bug `plan_export` had). Scope is the
    TOP LEVEL of `work/`.
  - **But the classification alone KEEPS the file #33 exists to remove**: `phi.dat` is in
    `WORK_STAGED`. The fix is **not** to delete that entry (a config whose `ibm_phi_file`
    resolves to `work/phi.dat` itself has no second copy, and the literal reading destroys it).
    The question asked is **"is it stale?"** — `solver_case.stale_phi_name` returns the name only
    when this run stages no phi at all, which is exactly what `report_stale_ibm_artifacts` warns
    about, so the warning and the deletion have ONE owner. `plan_case_clean(work_dir, stale=…)`
    takes those names from the caller, because whether a staged input is a leftover is a question
    about the *config*. `dll/` is out of scope, named rather than implied.
  - **`work/prev_*/` is NOT deleted by default**, and the tick that includes it is off every time
    the dialog opens (a fresh `QCheckBox` per call, never read back from `ui_state`).
  - **Two guards in `apply_case_clean`, and only one stops a deletion**: the plan's `work_dir` vs
    the run's, refused wholesale with one message naming both; then every entry re-checked to be
    `is_inside` that dir. Measured — remove the first and every entry is still refused
    individually; what is lost is the single legible refusal.
  - **A restart is refused even if handed a plan — and the guard CORRECTS the flags it
    invalidates.** Merely *skipping* the deletion shipped first and was wrong: a clean's flags are
    `(overwrite, no-archive)`, so declining left the run overwriting the previous outputs as it
    produced its own — #26's hazard, worse than either answer the user could have picked. It now
    sets `archive_prev`.
    Why: `docs/design_notes/pipeline.md`, "and the guard CORRECTS the flags it invalidates".
  - **Never unattended**: Run All / batch answers `CASE_NEW_VERSION` before any prompt;
    `confirm_case_clean` returns cancel when headless; an **empty** work dir degrades to
    `CASE_IN_PLACE` with a log line rather than prompting about nothing.
  - **One approved value, not a pair**: `ApprovedClean(plan, include_archives)`, exposed as
    `pending_clean()` — a verb, because a `getattr(self, "_case_clean_plan", None)` reach would
    make an uncomposed mixin degrade silently instead of failing.
  - **`_resolve_case_disposition` lives in `controllers/case_disposition_ctrl.py`** — moved there
    when the question grew its second step; a concept split, not just a line count.
  Gated by `tests/test_case_clean.py` (12 properties + 6 injections), which imports **no Qt at
  all** — the acceptance list asks for that in as many words, and the first version built a
  `QApplication` so `is_headless()` would answer True, making the deliverable literally false.
- **The restart point is PICKED from the case's own history, not typed as a path**
  (`services/restart_points.py`, Qt-free, plus `views/panels/restart_chooser.py`; #31,
  USER-REQUESTED 2026-08-21). The retired autofill looked for a fixed name **in `work/` only**,
  knowing nothing about #26's archives, while what is being decided is an **iteration count**.
  `list_restart_points(case_root)` returns cold start, the newest un-archived dump, then each
  archived leg newest-first with its count, timestamp and run tag; the chooser is one column of
  radio buttons plus an "Other file…" escape.
  - **The MODEL still holds a path**, absolute (#25), so `.hws`, pipeline scripts, `case_export`
    and `prepare_case_dir` are untouched — but **one control authors all three** fields; the three
    `FieldSpec` rows are gone and the names are declared in `SOLVER_EXTRA_AUTHORED` with a reason.
  - **Radio buttons, not a list widget, and the control reports its own edits.**
    `undo_ctrl._wire_widget_edits` is the ONE traversal that knows "the user touched this panel",
    and it connects spin boxes, combos, line edits and *checkable buttons* — a `QListWidget`
    selection is none of those — and the rows are **rebuilt whenever the case changes**, long
    after that one-shot traversal ran, so a composite control declares **`panel_edited`**.
  - **The list is derived on every call and cached nowhere** — the case dir is the truth. The cost
    is stated rather than optimised away; a cache is the thing this rule forbids.
  - **The marker is matched by BASENAME**: for an archived dump the reference names a hard link
    (#30) that the *next* archive retires, so matching by path or inode would lose the mark on
    exactly the row #31 exists to highlight.
  - **Every leg's count comes from one function, `case_run_note.iteration_span`** (#43).
    REVERSES #31, which gave an archive with no note the count "unknown" and *deliberately did
    not re-read* its history — costing exactly the legs it meant to protect, while
    `_latest_point` two functions below computed the live row's count from that same kind of file
    with that same reader. A leg whose span cannot be computed still gets a row, unlabelled:
    hiding a restart point that exists is worse.
    Why: `docs/design_notes/pipeline.md`, "#31 shipped the opposite rule".
  - **A restart source inside an archive gets a bare-named hard link in `work/` on demand**
    (`case_archive.bare_link_for_archived_dump`, called by `prepare_case_dir` *before* the archive
    step and independently of `archive_prev`). Without it the chooser's headline click produces
    the exact reference #26 measured the solver dying on. It refuses rather than guesses twice: a
    name taken by a different file is not overwritten, and a filesystem that cannot link warns
    instead of silently copying the largest file in the case.
  - **A restart whose source is not there is refused in the GUI**, both references resolved (a
    relative one against this case's work dir) and named with their missing path.
  - **The case-dir modal is dropped on the restart path** (CONFIRMED 2026-08-21); Run All
    untouched. One confirmation fewer means the archive step must be legible in the log on its own.
  - **`case_root_for` / `work_dir_of` live in `solver_case`**; `restart_points` re-exports them.
    The claim is exactly that narrow: the first write-up said "one spelling" and it was
    **false** — 11 `results/solver` joins exist.
  - **One departure from the issue's text, and one REVERSED**: the rows first showed the count as
    a bound (`1990+`); #43 reverses that to `iteration 2000` with both surviving caveats in the
    tooltip. The departure is recorded rather than deleted, so it is not left standing as a
    validated precedent. The remaining one: the issue says this
    keeps "`prepare_case_dir` untouched", which it does not.
    Why: `docs/design_notes/pipeline.md`, "One departure from the issue's own text, and one".
  - Residue, named rather than fixed: **a case-name change keeps the previously picked absolute
    path**, so it can land on "Other file…" as a cross-case restart — visible in the row's own
    field, refused by `_validate` if the file is gone, and no worse than the retired autofill.
  - **A row has to FIT, and that is structural rather than cosmetic** (USER-REPORTED 2026-08-27).
    `SolverConfigPanel` caps content at 430px with `ScrollBarAlwaysOff` +
    `setWidgetResizable(True)`, so a row wider than the viewport is CLIPPED with no window size
    that rescues it (measured: 494px wanted against ~380px usable). The timestamp drops its year
    and seconds, the marker became `← last run` (321px), and `_Row` elides what a narrower
    sidebar cannot fit — an ellipsis says there is more, a clip pretends the row ended. Two
    consequences: `minimumSizeHint` must stop advertising the full width, or the row forces the
    content wider than the viewport again; and **the marker is BOLD as well as worded**, because
    the words sit at the END and are elided first. A check asked of a row built from the CURRENT
    (short) text proves nothing — measured, it passed with the mechanism deleted — so the gate
    uses a deliberately over-long row. **The panel itself now scrolls sideways**
    (`ScrollBarAsNeeded`, USER-REQUESTED 2026-08-27; the setting `mesh_config_panel` has had
    since 2026-07-28) — a safety net for the PANEL, deliberately not the mechanism for the rows.
    `stl3d_panel`, `result_panel` and `sidebar` still carry `AlwaysOff` and have the same latent
    gap, recorded rather than fixed.
  Gated by `tests/test_restart_chooser.py` (12 properties against the real `prepare_case_dir`,
  the real widget offscreen, the real `SolverControllerMixin` and the real `AppController`; checks
  2-4 and 8 are **inverted** versions of ones that asserted the raw last row, a blank count, a
  blank TIMESTAMP and the old marker wording), and `test_restart_archive.py` check 7 is the
  **inverted** version of the one that pinned the dialog's restart branch.
- **A case describes its own geometry, not only its mesh** (`services/case_sources.py`, Qt-free):
  the CAD/STL a case was cut from is copied into **`grid/cad/`**. Fed by
  `solver_ctrl._case_source_files` / `_case_generated_files` and `pipeline_runner._case_sources` —
  the imported source, the resampled `.dat` the mesher read, the immersed STL, the mesh
  `.provenance.json`, and the **mesh parameter file**, which is *generated* rather than copied
  because the GUI only materialises one in `temp_dir` and deletes it on exit
  (`mesh_config_io.config_to_text`, split out of `save_config_to_file` so the staged config is
  byte-identical to a hand-saved one; it takes the destination path because a geometry outside the
  repo is emitted relative to the config file). Rules: **copy, never move** (a *move* is
  unimplementable anyway — one resampled `.dat` legitimately feeds several cases); **a hard link
  is not the cheap version of a copy**, since one inode means editing the CAD afterwards silently
  rewrites what the case holds; **sidecars follow their file** (`<name>.dat.meta` carries the
  per-segment BC labels and No-BL flags); **collisions are renamed, not overwritten**; generated
  files are staged **last** and marked `(generated)`, because a reconstruction must not read as
  evidence. `SOURCES.txt` maps every staged name back to its absolute origin, rewritten in full
  each run — and it is the *only* index there is, so **`tools/scripts/case_sources_index.py`**
  reads them back to answer "if I change this CAD, which cases go stale?" (matching by
  `(st_dev, st_ino)`, then path, then substring; exit 1 on no match). `case_export` descends into
  `grid/cad/` with its own allow-list.
- **`services/stl3d_case.py`** (Qt-free) is the same for the immersed-solid stage — `validate()`,
  `work_dir_for()`, `prepare_case_dir()` — and both `stl3d_ctrl.run_stl3d` and the headless IB
  stage go through it. **`Stl3dConfig.para_in_text()` must match
  `solver/preprocess/STL3d/src/stl3d.cpp`'s `cin >>` sequence line for line** — five reads and
  deliberately no ascii y/n line (the binary auto-detects); an extra line is consumed as the case
  name and the run silently produces an empty phi field with exit code 0. `cin >>` parsed from the
  C++ and gated by `tests/test_stl3d_case_parity.py`.
  **Inside `stl3d.cpp`, `STLobject` carries two different x extents and they must not be
  confused**: `xloc_db` (the index `trace_ray` looks rays up in) is keyed by element **centre** x,
  while the ray culling window `xmin`/`xmax` comes from the **vertices** — and has to, since a
  centroid sits strictly inside the surface. Every ray in the strip between the last centre and
  `xmax` passes the culling check with nothing at or after it in the index, so `lower_bound()`
  returns `end()` and dereferencing it killed a GUI IB run with `[STL3d] exited with code -11`. A
  **flat 2D profile is the worst case** — a fan triangulation drags every centroid toward the
  apex, leaving the far ~20-30% of the x extent centroid-free (measured 5.856 vs 6.070, the last
  41 of 128 slices). `ctr_strip_at_or_after()` clamps instead. Gated by
  `tests/test_stl3d_flat_profile_trace.py`, which compiles `stl3d.cpp` itself (CI does not build
  STL3d, and a stale binary must not pass it).
- **`services/contour_render.py`** (Qt-free) renders a Tecplot result to a contour PNG
  (matplotlib Agg) for headless runs.
- **`controllers/pipeline_ctrl.py`** (`PipelineControllerMixin`) is GUI **Run All** — it chains
  the per-stage QThread workers on their `finished_signal` (batch mode: no per-stage dialogs),
  ending on the auto-loaded Results contour. The **immersed-solid stage sits where the headless
  runner puts it, before the mesh**, so a script and the button build the same case; it is
  optional and skipped *out loud*. Save/Load of the script is
  **`controllers/pipeline_io_ctrl.py`** — the two share nothing but the config classes, and the
  split kept the file inside the GUI length budget.
- **`tools/PreProcessor/run_pipeline.py`** + **`run_pipeline.sh`** are the headless entry point
  (`--no-solver`, `--no-contour`, `--png`).

### The case as a package (`services/case_export*`, `services/case_workspace.py`)

**A portable case export copies a case's INPUTS into a folder that reruns on another machine**
(`services/case_export.py` + `case_export_docs.py`, both Qt-free; Solver toolbar "Export Case ⇪" +
Solver menu): `grid/` (mesh + `.def` + the getPGrid sources, whose `para.in` travels as
**`getPGrid.in`** — `_RENAMES` owns that mapping so `run_case.sh --regrid` and the manifest cannot
disagree), `work/` (`input.in`, `.def`, `phi.dat`, and the restart dump **only when `input.in`
restarts from it** — `include_restart="auto"`), `dll/` (`.so` **and** the `.cc` it was compiled
from, pulled from `results/solver/dll_src` by basename), plus `run_case.sh` and `MANIFEST.txt`.
`run_case.sh` **suggests** a compiler rather than choosing one (`CXX=${CXX:-g++}`) — the package
is for someone else's machine. Selection is an **allow-list**, so a new output file can never sneak
in, and everything rejected is NAMED in the manifest (known-output / not-used-by-this-run /
unrecognised). **The allow-list matches on NAME, so `work/phi.dat` and `dll/*` also have to ask
whether the RUN uses them** (`_unused_reason`): `prepare_case_dir` reuses a case directory in
place, so a case that once ran an immersed solid still holds both — USER-REPORTED as "I didn't
configure IBM, why is there a phi.dat and a dll/?". `input.in` decides, being the file the far
machine runs: it declares `immersed_solid` and names every DLL it dlopens by quoted path (plus a
type-11 BC row in `work/*.def`, the one DLL `input.in` never mentions). A `.so` that no longer
travels also stops pulling its `.cc` out of `dll_src`. `solver_case.report_stale_ibm_artifacts`
names the same leftover at case-prep time and never deletes it. **Every quoted value in `input.in`
is a file path**, and the GUI writes absolute ones for browsed files; those are staged into
`work/` and rewritten to `./<name>`. The solver binary is deliberately excluded. What the export
*writes* rather than copies lives in `case_export_docs.py`; the "is this file an input of THIS run
or a fossil of the last one?" reading of `input.in` lives in `case_export_usage.py`. Gated by
`tests/test_case_export.py`; verified end-to-end by regenerating the grid with getPGrid from the
exported folder and running unicones on it.

**The package also reopens in the GUI, not just in a shell** (`services/case_workspace.py`,
Qt-free). `run_case.sh` reruns only the SOLVER and there was no importer for an exported case
(USER-REQUESTED 2026-08-13), so Export Case *asks* (a third prompt, after the restart dump and the
tarball) and writes `<folder>.hws` into the package via `export_case(..., extra_files=...)`.
Three rules: **(1) re-point by file IDENTITY, never by string** — keyed by `(st_dev, st_ino)`, so
`results/` vs `Results/` on a case-insensitive volume or a symlinked scratch dir is still the same
file, and a path the package does NOT carry is left alone and REPORTED rather than rewritten to a
name that resolves to nothing; **(2) the caller's plan is the authority** — `export_case` accepts
`plan=`, because a second plan built with different arguments would describe a different package
than the one on disk; **(3) the stamp survives a move** — the workspace records
`exported_case_root`, and `rebase_case_workspace` (called from `_read_workspace_file` on **every**
load) swaps that prefix for wherever the `.hws` is being opened from. What does NOT travel:
CAD/mesh sources are no part of a solver case, so the geometry rides *inside* the `.hws`
(`original_points` verbatim) and still draws, but re-resampling or re-meshing needs those files —
the export log and the manifest both say so. `Save Workspace` and the export share one builder
(`session_io_ctrl.workspace_dict()`), so an exported workspace can never describe less than a
saved one. Gated by `tests/test_case_workspace_export.py`, which drives the real slot, moves the
folder, and loads it back.

## Named blind spots

Consolidated here rather than trailing each rule, so a coverage claim can be checked against one
list. #70 moved all four.

- **Nothing was measured on the solver for the three staged tables** — no case in this repo sets
  `mpi_comm_map_fn`, `cfl_schedule_fn` or `probe_points_def_fn`, so the justification for
  `table_refs_for_work_dir` is self-containment, not evidence.
- **bDecompose's acceptance run is OUTSTANDING and the gate says so**: the prebuilt binary cannot
  execute here, so `tests/test_bdecompose_in_case.py` pins the SHAPE of the run, not the binary's
  acceptance of it. #26 is why that distinction is written down.
- **`tests/test_bdecompose_in_case.py`'s checks 1-11 are BEHAVIOURAL but their injections were
  HAND runs**, which is not an in-test injection; exactly ONE injection is permanent (check 13
  mutates `_OUTPUT_PATTERNS` live and asserts the CONSEQUENCE).
- **Nothing in `tests/test_restart_chooser.py` runs `unicones`**, so the bare-name restart
  reference is pinned against the SHAPE #30's acceptance run measured.
