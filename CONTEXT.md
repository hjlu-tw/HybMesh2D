# HybMesh2D

A 2D mesh generator for CFD, plus the PreProcessor GUI that drives it. This glossary
fixes the words used when discussing the tool's workflow and its users. It is a
glossary only: rules live in `.claude/rules/`, rationale in `docs/design_notes/`.

## The two generation paths

**Multi-block**:
The structured path (`MESH_MODE 1`): a declared block topology filled with structured
quads, using Gmsh nowhere. The project's target path.
_Avoid_: structured mode, block mode, MB

**Hybrid**:
The unstructured path (`MESH_MODE 0`): boundary-layer quads grown from every geometry,
far field filled with Gmsh triangles. Every case shipped before 2026-10 uses it.
_Avoid_: Gmsh mode, triangle mode

## The three senses of "boundary"

Three distinct things that Chinese "邊界" and English "boundary" both reach. Never use
the bare word; pick one of these.

**Far-field box** (遠場框):
The rectangle the mesh fills out to, set by `domain_x_min` / `x_max` / `y_min` / `y_max`.
_Avoid_: domain, boundary, outer boundary

**BC** (邊界條件):
The physical condition on a patch — inlet, outlet, wall — written to the `.bnd` file.
_Avoid_: boundary, patch type, BC type

**BL** (邊界層):
The band of structured quads grown against a wall, governed by 21 `BL_*` parameters.
_Avoid_: boundary, prism layer, inflation layer

## The workflow

**CAD**:
The input geometry: a `.dat` polyline, a shape drawn on the canvas, or a parametric
shape from the library. Never a STEP/IGES/NURBS file — this project has no such importer
and its data model is polyline-based throughout.
_Avoid_: geometry file, model, part

**Topology**:
The declared arrangement of blocks — their corners, edges and how they share them — that
the multi-block path fills. Authored separately from the CAD and bound to it.
_Avoid_: block structure, grid structure, layout

**One-click generation**:
The single action that takes a bound CAD and topology to a finished mesh and stops
there. It does not run the solver; that remains `Run All`.
_Avoid_: auto-mesh, generate, Run All

**Verdict**:
The tool's own graded judgement on a finished mesh — usable / needs attention /
unusable / **not determinable** — issued above the mesher from measured quality
metrics, so an operator need not read raw numbers to know whether to proceed. The
fourth state is not optional: a metric that could not be measured must never read as
one that came out well.
_Avoid_: quality report, mesh stats, score, grade

## The people

**Operator**:
Someone who runs the tool to get a mesh for their own CFD work and is not expected to
know meshing theory. The audience one-click generation and the verdict exist for.
_Avoid_: user, student, end user

**Maintainer**:
The single person who knows the tool internally, authors what operators choose from,
and is the only one expected to reach the full parameter set.
_Avoid_: developer, admin, expert user

## The multi-block vocabulary

**Family**:
One of the four parameterised topology generators — `hgrid`, `ogrid`, `cgrid`,
`tworing` — each a pure function from typed parameters to a topology document. A shape
outside all four has no family.
_Avoid_: template, generator, type

**Binding**:
The attachment of a topology edge to a CAD segment, held as that segment's stable id
and, along it, a normalised arc length. Re-resampling the CAD does not move a binding;
deleting the segment breaks it.
_Avoid_: link, reference, mapping

**Case type**:
A named bundle the maintainer authors once and an operator applies: a family, its
parameter values, the verdict's thresholds, and the remedial advice shown when a
threshold is missed. The unit in which meshing expertise is stored and reused.
_Avoid_: template, preset, profile, config

**Pin**:
A recorded figure asserting only that a number has not MOVED, carrying no claim that it
is good. Distinct from a threshold, which asserts a number is BAD. The mesher holds
pins and refuses thresholds; thresholds live in case types.
_Avoid_: baseline, golden value, benchmark

**Reference mesh**:
A mesh the maintainer judged good, whose measured metrics become a case type's
thresholds after a tolerance factor is applied. It makes authoring a case type a
demonstration rather than a specification, and gives every threshold a traceable origin.
_Avoid_: golden mesh, baseline mesh, benchmark

**Role**:
The job a CAD segment plays in a topology — body, far field, seam — named by the
operator when applying a case type, since the case type's own bindings point at the
maintainer's geometry and cannot carry over. The unit in which an operator attaches
their own drawing to borrowed expertise.
_Avoid_: tag, label, group

**Deviation**:
An operator's edit to a field the applied case type had an opinion about. It does not
invalidate the verdict but downgrades its standing: the thresholds were measured on a
reference mesh whose premises the edit has changed, and the verdict must say so.
Distinct from "not determinable", which is a metric that could not be measured at all.
_Avoid_: override, drift, customisation

**Pre-flight refusal**:
A family's own judgement, made before any mesh is generated, that a given geometry and
role assignment cannot work — a closed loop that is not closed, a C-grid with no
trailing edge. It belongs to the family, because each family's preconditions are its own,
and it must speak in the operator's terms rather than in exit codes.
_Avoid_: validation, precondition check, sanity check

**Fallback mesh**:
The hybrid mesh offered, never silently substituted, when no family covers the
operator's geometry. It is a usable mesh but not a structured one, so a case type's
thresholds do not apply to it and no verdict is issued from them.
_Avoid_: degraded mesh, backup mesh, default mesh

**Characteristic length**:
The geometric length a case type expresses its geometry-driven sizes relative to — a
chord, a body diameter — so that one case type fits a 1 m body and a 10 mm one. Named
by the case type, derived from the segments the operator assigned roles to.
_Avoid_: reference length, scale, base size

**Physical parameter**:
A case-type value fixed by physics rather than by geometry — the boundary-layer first
cell height, set by Reynolds number and target y+. It is never scaled with the
characteristic length, and is the one thing a case type asks the operator to confirm on
every application rather than applying silently.
_Avoid_: absolute parameter, fixed parameter

**Preview**:
A mesh generated for the operator to look at and decide whether to adjust. It is the
inspect-and-tweak loop: the operator may run it as many times as they like, and nothing
downstream consumes what it produces.
_Avoid_: draft, test mesh, quick mesh

**Generate**:
The action that produces the mesh the solver will read, and commits it to the case along
with the case type it came from. The end of the operator's meshing work.
_Avoid_: export, build, run, finalise
