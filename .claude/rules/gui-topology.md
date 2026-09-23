---
paths:
  - tools/PreProcessor/gui/app/services/topology_*
  - tools/PreProcessor/gui/app/views/mesh_canvas*
  - tools/PreProcessor/gui/app/views/panels/mesh_config_*
  - tools/PreProcessor/gui/app/models/mesh_config_io*
---

# GUI topology-template rules

Loaded on demand when a topology service, the mesh canvas or its two mixins, a mesh-config panel
mixin, or the mesher-config writer is read. Rules only — the rationale (the measurements, the
injections, the reversals and the named blind spots) is `docs/design_notes/gui.md`, sections "THE
TOPOLOGY TEMPLATE LIBRARY", "THE TOPOLOGY MODEL SURVIVES THE SESSION", "THE BLOCK SKELETON ON THE
CANVAS", "THE O-GRID BINDS TO THE CAD" and "THE BROKEN BINDING IS REPAIRED FROM THE PANEL". Read
the matching section before overruling a rule here; when a rule changes, update BOTH.

**THE ELEVENTH RULE FILE, AND THE SECOND TAKEN BECAUSE ONE WAS FULL.** These four blocks (#134,
#135, #136, #137) lived in `.claude/rules/gui-panels-config.md` until #137's review, which left
that file at **59,927 of its 60,000 characters — 73 of slack**, so #138 could not have written a
sentence there. #85's precedent is the one followed: when a rule file is full the answer is a new
file, not a squeeze, because compressing rules to fit a budget is how a rule quietly loses the
clause that made it a rule. The area is coherent on its own terms as well as by size — a family
registry, a projection, a binding, and the overlay that draws what they produce — and it had two
tickets still to land when it was taken, of which #138's binding repair has since landed here and
#139's detach has not.

**THIS FILE OVERLAPS `gui-panels-config.md` RATHER THAN PARTITIONING IT**, the same shape #89 and
#85 took, and the overlap is the intended one: the template's parameters are field-spec rows and
its panel is the mesh-config panel, so a session under `views/panels/mesh_config_build_mixin.py` or
`models/mesh_config_io.py` loads BOTH files and needs both — the field-spec mechanism from there,
the template's own rules from here. What is NOT duplicated is the rule text: every topology rule is
here and none is there.

**These rules also govern files OUTSIDE the globs above, which cannot hand a reader the text**:
`controllers/solver_ctrl.py` and `services/pipeline_case_sources.py` (both call
`case_sources.mesh_config_generated`, whose own staging rules are in
`.claude/rules/pipeline-case.md`), `controllers/undo_ctrl.py` (`_wire_widget_edits`, the traversal
that makes a template keystroke reach the undo recorder), and `controllers/project_state_ctrl.py`
(`_collect_project_state` IS `MeshConfig.to_dict()`, which is why the `topology` section has to be
named there by hand). The table in `CLAUDE.md` is what makes each of those reachable.

**One glob is WIDER than the area.** `views/panels/mesh_config_*` and `models/mesh_config_io*`
reach far more than the template: the field-spec tables, the `.dat` key map, the length units, the
Edit-BL dialog and the geometry list are all `gui-panels-config.md`'s, and this file says nothing
about them. `views/mesh_canvas*` is the reverse — it is entirely this file's, and it is NOT the CAD
canvas, whose edit-ownership rules are `.claude/rules/gui-canvas-edit.md` (`views/canvas*`, which
does not match `mesh_canvas*`).

**A TOPOLOGY TEMPLATE IS A MODEL; THE JSON IS A PROJECTION** (#134, parent #133;
`services/topology_model.py`, `services/topology_hgrid.py`, `services/topology_field_specs.py`)

- **One family = one PURE FUNCTION** from `TopologyModel` to a document `dict`, registered in
  `FAMILIES` with its own parameter PREFIX. Qt-free, mesher-free, canvas-free. A family is a
  function and never a data-driven template file: seeding one count per equivalence class, closing
  the ring counter-clockwise and deciding which lines are interior are LOGIC, and expressing them
  as data means inventing a second language whose interpreter is the module anyway.
- **The document satisfies the mesher's structural rules BY CONSTRUCTION, never by a check
  afterwards** — the ring closes `[south, east, north, west]` from ONE index expression, ids are
  unique by prefix, `nx + ny` count classes seeded on the bottom row and the left column, each
  interior line declared once and named by both blocks, no key outside the schema, nothing
  declared that reaches nothing. A template that can produce a refusal has handed the user back
  the JSON they came to avoid. Gate: `tests/test_topology_templates.py` (checks 1-9, over a spread
  of EIGHT parameter sets, classes derived there from the propagation rules rather than from the
  builder; check 6a reads all five key sets out of `src/MultiBlock.cpp` by a MARKER key and fails
  rather than answering when it cannot).
- **`MeshConfig.mesh_topology_file` is an OUTPUT when a family is named, an input when none is.**
  The projection is hooked into `models/mesh_config_io.py::save_config_to_file` — the ONE call both
  hosts converge on before launching the mesher (`controllers/mesh_gen_ctrl.py`,
  `services/pipeline_runner.py`) — so the file that line names exists because of WHERE the hook is,
  not because two hosts each remembered a prepare step. That function's docstring states the cost:
  it is no longer a pure text transformation. `config_to_text` STAYS pure and takes the projected
  path as an OVERRIDE argument, because its other two callers want content, not a run.
- **Template rows are their own field-spec table with NO `.dat` key.** A template parameter has no
  C++ counterpart — the mesher never sees a block count, it sees the document one produced — so
  these rows cannot ride in `MESH_SPECS`, whose key is compared against `Config.hpp` in both
  directions. What they are compared against instead is the FAMILY FUNCTIONS, in both directions,
  with the reads DERIVED by `ast` rather than hand-listed. Gate:
  `tests/test_topology_param_specs.py`.
- **The derived counts have ONE owner, shared with the panel** (`topology_hgrid.hgrid_counts`,
  which is also what the document seeds). The panel displays that function's answer and computes
  nothing; a second copy would be free to show a number the generated mesh does not use. Gate:
  `tests/test_topology_panel.py` check 4, whose 4b reads the panel's own sources for a second
  derivation because 4a cannot see one that happens to agree today.
- **`to_dict` carries `topology` BY NAME**, because `_key_map()` finds fields by their `.dat` key
  and this one has none — and the project-undo snapshot IS `to_dict()`, so without that line Ctrl+Z
  would be the one thing that did nothing in this section. `load_from_dict` restores it only when
  the key is a dict, so a project file written before templates loads exactly as it did.
- **`_spec_rows(..., model=)` seeds a table from a class other than `_SPEC_MODEL`**, for the one
  table whose rows author something other than the panel's own config. Without it every topology
  row would be seeded from whatever Qt leaves in an un-set widget, which the panel->model sync then
  makes the session's default.
- **The `topology` section is OPTIONAL, and ABSENT MEANS THE DEFAULT MODEL — in BOTH directions**
  (#135). `to_dict` omits it unless `TopologyModel.is_configured()`, following the `stl3d`
  precedent in `pipeline_config`; `load_from_dict` REBINDS a fresh model when the key is absent,
  null or not an object. The second half is not tidiness: the project-undo snapshot IS `to_dict()`,
  so the snapshot taken before the first template edit now carries no section at all, and an absent
  section that did nothing would make that edit the one thing Ctrl+Z cannot walk back — measured,
  with `test_undo_redo.py` and `test_topology_panel.py` both staying GREEN on the injection.
  `is_configured()` compares against a freshly built model and so asks about EVERY parameter, never
  about `family` alone: a number typed before the combo is touched is still something configured.
  Gate: `tests/test_topology_persistence.py` checks 1-3b.
- **What a template case STAGES is ruled on in `.claude/rules/pipeline-case.md`**, whose globs own
  `services/case_*`: the document is generated into `grid/cad/` beside the parameter file that
  names it (`case_sources.mesh_config_generated`, #135, closing #134's blind spot below). Named
  here only so a reader of the projection is not left believing `save_config_to_file` is the only
  place a document is written.
- **A round-trip claim is measured on a FILE and by DRIVING both hosts, never on a dict and never
  from a source scan.** The gate saves a real project file, reopens it through a real
  `AppController`, reads the same file through the pipeline bridge, and compares the two documents
  byte for byte — then runs both configs through the real mesher and compares the meshes node for
  node. Two reasons, both measured: a dict round-trip cannot see a parameter the writer never
  emitted, and a two-host comparison agrees with itself about a parameter BOTH hosts lost (injection
  H reddened 5, 5b, 7, 8b and 13 while 8 stayed green). The live-model-against-round-tripped
  asymmetry in check 13 is deliberate for exactly that.

Why, and every measurement: `docs/design_notes/gui.md`, "THE TOPOLOGY TEMPLATE LIBRARY".

**THE O-GRID BINDS TO THE CAD, AND A BROKEN BINDING REFUSES** (#137, parent #133;
`services/topology_ogrid.py`, `services/topology_binding.py`)

- **A binding is the CAD segment's STABLE ID, never a position** — the sidecar's `segId` column
  already IS that id, so resolving is a LOOKUP proving it is still on disk. A missing id raises
  `BindingError` naming the EDGE, writes nothing, and NEVER falls back to `BC_GEOM`; so does a list
  that walks the geometry's order BACKWARDS (a rotation is fine, a reorder is not — every id in a
  swapped list still resolves), one holding a token that is not an id, and one naming a segment
  twice. Blank adopts the geometry's segments; the panel CAPTURES them when the user names a
  geometry, keyed by WHICH FILE, and the rows are **read-only** with their pairing declared in
  `BINDING_ROWS` — which edges bind is the template's decision (#133). `parse_binding` is the one
  parser of that format, asked by the panel too. Gate: `tests/test_topology_ogrid.py` 9-11m, whose
  11 and 11h are the negative controls.
- **A family is pure over `(model, ctx)`**; the context is built from `MeshConfig` at projection
  time and NEVER persisted. The H-grid ignores it, so `fam.build` stays a call, not a dispatch.
- **The far field is DRAWN, never generated**, and its segments pair ONE TO ONE with the body's. A
  wall edge lies within ONE source segment, so the ring REFINES the segment partition and
  `ogrid_splits` is per segment.
- **The winding is MEASURED**: a clockwise body gets the mirrored tuple `[w, r_next, o, r]`, which
  pairs the same edges as opposite sides, so classes and seeding are unchanged. **`MIN_BLOCKS` is
  3, measured**, the mesher refusing a two-block ring on collinear corners. Gate: check 13.
- **The radial count is DERIVED AND ITS DERIVATION DISPLAYED**: `q = 1 + 2π/N_theta`, the default
  being where a law starting at the run's `BL_INITIAL_THICKNESS` and growing at `q` reaches the far
  field, and the clamp saying so when it fires. No `ds_start` is declared, so the first cell keeps
  its one home under the existing name. `topology_ogrid.plan` is the ONE owner. Gate: check 8.
- **A radius is AREA-EQUIVALENT and a wall count rounds half UP with a tolerance**, or re-sampling
  a geometry moves a derived count and so becomes a topology edit. Gate: check 10.
- **The invariants every family's document must satisfy live in ONE checker**,
  `tests/topology_doc_invariants.py`, called by both family gates.

Why, and every measurement: `docs/design_notes/gui.md`, "THE O-GRID BINDS TO THE CAD".

**A BROKEN BINDING IS REPAIRED FROM THE PANEL, AND A RING MUST COVER ITS OUTLINE** (#138, parent
#133; `services/topology_ogrid_binding.py`, `views/panels/mesh_config_repair_mixin.py`)

- **A VALID O-GRID BINDING IS A ROTATION OF THE GEOMETRY'S WHOLE SEGMENT LIST, and nothing else.**
  Each wall edge runs from its own segment's start to the NEXT bound segment's start, so the
  mesher's rule that a bound edge's corners lie on the segment it binds forces the next bound
  segment to be the geometry's next segment, all the way round. `cover_problem` refuses a gap
  NAMING THE EDGE that would have to span two source segments — the mesher's own exit-8 refusal
  moved forward. **SUPERSEDES #137's "a subset is fine"**, which was true of `order_problem` (a
  subset walks the right way) and false of the document it let through; measured, `2, 40` of
  `[5, 11, 2, 40]` projected a four-block ring the mesher then refused.
- **THE REPAIR IS THEREFORE A ROTATION, NOT A REPLACEMENT AT THE POSITION.** `repair_binding(order,
  pos, seg)` returns the geometry's CURRENT ids rotated so `seg` sits at `pos`, and does not read
  the broken text at all: the only information a valid list carries is where the ring starts, so
  naming the segment one flagged edge should lie on picks the whole list. A replacement at the
  position — the obvious reading of the ticket, and what shipped first — leaves the hole above the
  moment a CAD split has turned one bound segment into two. Repairing a split therefore makes the
  ring one block BIGGER, and the far field must be cut to match or #137's one-to-one pairing
  refuses; that refusal is not repairable by a dropdown and is left as it is.
- **`plan` RESOLVES EVERY BINDING BEFORE IT ASKS ANY QUESTION ABOUT COUNTS.** With one list
  repaired and the other still broken the two differ in length BECAUSE of the broken one, and
  "the body binds 5 and the far field 4" names no edge and points at the wrong geometry. Each
  list is walked against its own ring, so neither depends on the other's length.
- **WHAT IS BROKEN IS THE FAMILY'S ANSWER, ASKED THROUGH THE REGISTRY** (`Family.broken`,
  `topology_model.broken_bindings`). It reports EVERY broken position at once where `plan` stops
  at the first — one answers "can this run?", the other "what must the user fix?" — and it is
  SCOPED to what a dropdown can repair: a geometry the mesh does not load, an unparseable list, an
  unclosed body and a far field inside the body are not wrong SEGMENTS and keep the read-out's
  sentence as their only voice. `choices` is the geometry's whole current list, because every
  entry names a legal rotation.
- **The flag REFRESHES from `_refresh_topology_counts`, the one place already holding both the
  model and the context**, which runs on every template keystroke AND every `set_config`. That is
  what clears the flag when the cause is removed by other means — undoing the CAD edit rewrites
  the sidecar, whose `(mtime, size)` is the binding cache's key. The rows are a POOL that is never
  destroyed and are repopulated inside `block_signals`: a repair arrives from inside a combo's own
  signal, so deleting and recreating them deletes the widget mid-emit. `TopologyRepairBox` declares
  `panel_edited`, the convention `undo_ctrl._wire_widget_edits` documents for a composite that
  builds its own children — without it the write lands in the widget and reaches neither the
  global model nor the undo stack.
- **The write goes into the binding ROW, which stays READ-ONLY.** That row is the field-spec row
  the panel->model sync already reads, so a repair is persisted, undone and projected by the
  machinery every other template parameter uses; the panel supplies only the position and the
  chosen segment, and what the rest of the list becomes is the family's answer. Gate:
  `tests/test_topology_repair.py`, whose fixture and the sidecar-only CAD split live in
  `tests/topology_outline_fixture.py` (shared with `test_topology_ogrid.py`, so one `.meta` writer
  serves both), and whose real-mesher half runs with `MB_SMOOTH_ITERS 0` beside a no-CAD-edit
  CONTROL.

Why, and every measurement: `docs/design_notes/gui.md`, "THE BROKEN BINDING IS REPAIRED FROM THE
PANEL".


**THE SKELETON IS THE TOPOLOGY MODEL DRAWN, AND THE NODE COUNT IS THE POINT** (#136, parent #133;
`services/topology_skeleton.py`, `views/mesh_canvas_skeleton_mixin.py`, `views/mesh_canvas.py`)

- **Every edge's count is RESOLVED by propagation, never read off the edge.** A `count` in the
  document is a SEED: opposite sides of a block carry equal counts and a shared edge is one edge two
  blocks name, so four declarations decide twelve edges on the shipped H-grid. An overlay drawing the
  outline alone would show the easy half and hide the half a user cannot predict.
  `resolve_counts` mirrors `resolveEdgeCounts` (`src/MultiBlock.cpp`) — union a block's OPPOSITE
  sides, which for `[south, east, north, west]` are the pairs (0, 2) and (1, 3), then one seed per
  class. **It is a SECOND HOME for one rule and says so**; the alternative is writing a document to
  disk and launching the mesher for every keystroke, which a live overlay cannot pay. What keeps the
  two together is a gate, not discipline: `tests/test_topology_skeleton.py` check 2 reads the
  pairing literal out of BOTH sources and FAILS rather than skips when either is unfindable, and
  check 12 compares the REAL mesher's own `Point counts` banner row — the declared/propagated split
  and every propagated edge by name — against this module, on the shipped `hgrid_blocks.json` AND on
  a document the family produced.
- **A document the mesher would REFUSE resolves to NO number, never to a guess.** A class with no
  seed, and a class with two seeds that disagree, both label `?` — the two refusals `resolveEdgeCounts`
  exits with. Picking one of two conflicting seeds would label a mesh no run will produce, and a
  blank would hide the one state that stops the run. Negative control in check 4: the same two-block
  topology with a single seed resolves the whole chain across the shared edge.
- **ONE owner for "is there a skeleton to draw" — `skeleton_for_config`** — which asks BOTH halves,
  the multi-block mode and a family named, for the reason `mesh_modes.topology_file` asks both of
  its own. The canvas holds no predicate, so it cannot come to a different answer than the panel
  about what a template case is. `None` for a case with no topology model is also what CLEARS the
  overlay on the way in, rather than leaving the last case's skeleton on screen.
- **READ-ONLY in v1, and that is a decision about two interactions rather than a deferral.**
  Dragging a BOUND corner edits a normalized arc-length position; dragging a FREE one moves a
  coordinate — two interactions behind two identical-looking dots. Gate: check 9 walks the mixin's
  **AST** for `TargetItem`, a `movable=` keyword and the mouse signals. Over the PARSE and not the
  text, because the file's own header names `movable=True` to explain the rule and the first draft's
  substring scan read that prose as the defect it rules out.
- **A bound corner differs by SYMBOL as well as colour, and one nothing can place is drawn nowhere.**
  Two dots that differ only in hue are two dots. `skeleton()` takes a `locate` callback —
  `topology_binding.locator` since #137, nothing before it — and reports an unplaced corner as
  bound-with-no-position, an invented coordinate being a topology the user did not declare.
- **The hook is `update_mesh_config`, OUTSIDE its `if self.mesh_config:` branch.** That is the one
  place this canvas learns the configuration changed, so a parameter edit and a case switch reach the
  overlay by the same route and neither is the one that forgets; outside the branch because `cfg is
  None` is exactly the case whose skeleton must not survive the one before it.
- **The template rows AND the mode combo emit `mesh_config_changed`; no other mesh field does.**
  `_on_topology_edited` in `views/panels/mesh_config_build_mixin.py`. That signal fires for
  STRUCTURAL edits — the geometry list, a role, a BC — and not for a plain spin box, the same gap
  `undo_ctrl._wire_widget_edits` covers for the recorder; the canvas has no such generic traversal.
  The mode is wired because it is the other half of `skeleton_for_config`'s question, and without it
  the canvas keeps drawing a topology while `_apply_mode_visibility` has hidden the section that owns
  it. SCOPED to this table rather than fixed for every mesh field, which is not this ticket's to
  change, and suppressed while `_loading` — the `text` rows report `textChanged`, which Qt emits for a
  programmatic write too, and `set_config` ends with its own emit.
- **`auto_range` gained a THIRD source and UNIONS it — but the skeleton FITS only when nothing
  else will.** An empty `cads` is legal in `MESH_MODE 1`, where a topology declaring its own corners
  is the whole input, so a template case can have no mesh and no geometry preview and still need
  fitting. The union is what makes a case that HAS geometry fit both. The guard on the fit is the
  half that is easy to get wrong and was: `auto_range` spends `_did_initial_fit`, the ONE-SHOT token
  `mesh_canvas_geom_mixin._on_geometry_previews_loaded` needs, and the skeleton is built at the TOP
  of `update_mesh_config`, before those previews are even requested — so fitting unconditionally
  spent the token on content that had not arrived and the geometry was never fitted at all (a
  `MESH_MODE 1` config naming `naca0012.dat`, x 0..1, came out at x 0.026..0.174). So the skeleton
  fits only with no mesh and no `geom_files`. Gate: check 11b (no skeleton, nothing moves), 11c (no
  geometry, the skeleton is fitted), 11d/11e (with geometry, the token is left for the preview load,
  which then covers BOTH — the fixture puts the two apart on purpose, because one enclosing the
  other cannot tell a union from a fit that never saw the geometry).
- **A template keystroke emits `topology_changed`, NOT `mesh_config_changed`, and reaches
  `update_mesh_config(cfg, reload_geometry=False)`.** The wide signal's handler
  (`controller.handle_mesh_config_changed`) reloads every geometry preview and re-reads every
  `.meta` — 12 preview reloads for five characters typed — and `update_geometry_previews` OPENS by
  clearing the selection highlight, so typing in a template row dropped the outline of the geometry
  picked in the config list and nothing put it back. A flag on the one function rather than a second
  entry point, so the skeleton, the domain box and the BC preview cannot drift out of step. The
  narrow handler syncs no model: `undo_ctrl._wire_widget_edits` already routes every widget edit
  through `on_panel_edited`, and a second traversal is free to cover a different widget set. Gate:
  check 13, with 13c as the negative control that the wide handler still reloads.
- **A `count` that is PRESENT but not an integer >= 2 unresolves its whole CLASS.** The mesher
  refuses such a document by name (`src/MultiBlock.cpp`, `count >= 2`), so reading it as "no
  declaration here" would let a valid sibling seed label a number for a run that never happens.
  Narrower than the mesher, which refuses the whole document: here the `?` lands on the edges the
  user has to go and fix. Gate: check 4e, whose fixture carries a VALID sibling seed — without one
  the class is seedless and both readings answer `None`, which is how its first version made the
  injection inert — and 4e2, the negative control.
- **The overlay draws the MODEL and never a hand-named topology FILE**, which is #136's own
  criterion ("does not survive switching to a case with no topology model") read literally. Since
  #137 the O-grid's bound corners ARE placed, from the same context the projection uses — and
  `skeleton_for_config` returns `None` when that family refuses, because an overlay of a topology
  the run will not produce is worse than no overlay. A hand-named file still draws nothing.
- **An edge with an unplaceable end is drawn NOWHERE, and carries no `?`.** The asymmetry against
  the unresolved-count rule above is deliberate and is a consequence rather than a choice: `?` is a
  label, and a label needs a midpoint. Stated because the two unresolvable cases otherwise look like
  they should behave the same.

Why, and every measurement: `docs/design_notes/gui.md`, "THE BLOCK SKELETON ON THE CANVAS".

## Named blind spots

Consolidated here rather than trailing the rules they belong to, so a coverage claim can be checked
against one list — the shape `gui-panels-config.md` uses, and these six came from it with #137.

- **The template parameter gate's `ast` walk is SCOPED to fields `TopologyModel` declares**, so a
  read of an attribute that is NOT a model field is invisible to it: a typo'd `model.hgrid_cellsize`
  is not reported as an undeclared parameter, it simply vanishes from the reads. It is still
  caught, but only from the other direction — the row whose field is no longer read goes red.
  Measured by injection C in that file, which corrected the prediction written beside it.
- **CLOSED by #135, kept as the shape:** `config_to_text`'s two other callers saw no topology for a
  template case, because both read `cfg.mesh_topology_file` — empty when a family is named, since
  that path exists only once `save_config_to_file` has projected one — so a staged config carried no
  `MESH_TOPOLOGY_FILE` line at all. Both now go through `case_sources.mesh_config_generated`, which
  GENERATES the document beside the parameter file; `config_to_text` stayed pure and neither caller
  fires a projection. What is left is one asymmetry, deliberate and stated at that function: the
  STAGED line quotes a bare filename while the line the run itself wrote is absolute, so the staged
  config is runnable in place only from the staged folder. It is a record, not a rerun, and an
  absolute path in it would be a record of one machine.
- **A GENERATED staged entry can overwrite a previous run's file of the same name.** #135
  narrowed `_unique_name` for generated entries so the parameter file and its document stay a
  PAIR across re-runs (`grid/cad/` is never cleared, and the old rule made the second run's
  parameter file quote the FIRST run's document). The cost is that a file left there by an
  earlier run whose name collides with a generated one is replaced rather than kept. Reachable
  only for a COPIED input named exactly `Background_para_<case>.dat` or `..._topology.json`
  that is no longer a source this run — already an unrecorded leftover, since `SOURCES.txt` is
  rewritten in full. Nothing gates it. The earlier blind spot this replaces — a template case
  that could not build its document losing its PARAMETER FILE too — was CLOSED in review: the
  fallback is the pre-template parameter file with no `MESH_TOPOLOGY_FILE` line.
- **The bound-corner MARKER is gated on a fixture, not on a real path.** #137 made the O-grid
  produce bound corners, but check 8 still hands `update_topology_skeleton` a skeleton the gate
  built; nothing drives the canvas from a template that binds.
- **The mesher can only be compared on a document it ACCEPTS.** Check 12's cross-check reads the
  `Point counts` banner, which a refused run never prints — so the two refusals are held at
  opposite ends and never compared: `test_multiblock_weld_surface.py` check 6 proves the MESHER
  refuses them, check 4 here proves this module answers `?`, and nothing asserts the two refuse the
  SAME documents. A module that saw a conflict where the mesher sees none would draw `?` over a
  mesh that runs, and the reverse would draw a number over a run that is refused; only a human
  would notice either. SUPERSEDES #136's own first draft: the weak half is check 12's
  declared/propagated SPLIT, not the cross-check.
  Why: docs/design_notes/gui.md, "This entry's first draft was wider"
- **A repair that names a segment far from where the broken one lay is LEGAL and meshes badly.**
  The choice decides the ring's rotation, so pairing a body corner with a far corner most of a
  turn away is a document nothing refuses — measured at exit 9 with 67 of 704 cells inverted.
  Nothing can do better from the panel: the deleted segment is gone from the sidecar, so there is
  no record of where it lay. Cutting the two outlines at DIFFERENT arc positions has the same
  effect by another route and is #137's pairing design rather than #138's.
- **`Family.broken` being unset is indistinguishable from "nothing is broken".** It is `None` for
  the H-grid, correctly; a third family that forgot to declare one would report nothing and no
  gate would notice.
- **Nothing gates that a family's document MESHES except for the DEFAULTS.** The spread of eight
  parameter sets is checked structurally; only `TopologyModel()`'s defaults are run through the
  real binary, because eight mesher runs in a gate is a cost nobody asked for. A parameter set that
  is structurally legal and geometrically degenerate (a zero-width domain, say) is not reached.
