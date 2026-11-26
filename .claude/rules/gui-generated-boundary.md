---
paths:
  - services/topology_genfar*
  - services/topology_ogrid.py
  - services/topology_tworing.py
  - services/topology_cgrid_section.py
---

# GUI rules — WHAT A TOPOLOGY FAMILY MAY GENERATE FOR ITSELF

Loaded on demand when the generated-boundary module, or one of the three families that
generate something, is read. **The NINETEENTH rule file, and the TENTH taken because
another was FULL**: `.claude/rules/gui-topology.md` says in its own second line that it
is full and that *"the next block here is a new rule file, not a squeeze"*, and it had
eight characters of slack when #197 arrived. Three of the four globs are that file's as
well, the intended overlap — what a family BUILDS is there, **what it may build for the
user rather than read off their drawing is here**.

Rules only: the rationale — the measurements, the injections and the named blind spots —
is `docs/design_notes/gui.md`, the same note the other `gui-*` rule files point at. Read
it before overruling a rule here, and when a rule changes update BOTH.

**THE LINE IS NOT "A FAMILY WRITES NO GEOMETRY". IT IS "A GENERATED THING CANNOT BE A
STORED POLYLINE."** `.claude/rules/gui-topology.md` states the two-ring family's refusal
— it will not offset the body for you — and the reason it gives is exact and narrower
than the slogan it reads as: a `follows` or a `binding` edge resolves to a stretch of a
stored polyline, so a generated one would have to be a written FILE with no stable-id
scheme, no sidecar and no place in the project round trip. **An outer boundary is not
that.** Since #175 an edge may declare the CURVE IT IS, with no file anywhere, and its
nodes are placed on that curve at exact arc length.
- **SO: a family MAY generate an edge that is analytic (`curve`) or straight; it MAY NOT
  generate one that must FOLLOW a shape the user drew.** An intermediate ring of a
  multi-ring O-grid is the second kind and stays the user's, made with
  **CAD ▸ Offset Geometry…**. A far field is the first.
- **The C-grid was already on this side of the line** (#149, `cgrid_far_geom` blank ⇒ six
  free corners) and the O-grid joined it at #197. Neither is a precedent for generating a
  seam.

**THE O-GRID'S FAR FIELD IS OPTIONALLY DRAWN, AND GENERATED AS ONE ELLIPSE WHEN IT IS
NOT** (#197; `services/topology_genfar.py` + the generated branch of
`services/topology_ogrid.py`)

- **BLANK IS THE DEFAULT AND NOT A DEGRADED STATE**, the C-grid's own wording. The two
  paths are told apart by the stored NAME and never by whether the lookup found
  anything: a name that resolves to nothing is a REFUSAL, because silently generating a
  far field there would hide a geometry the user deleted.
- **ONE ELLIPSE, NEVER A RECTANGLE.** A ring's outer corners are placed one per block, so
  on a rectangle some block side would cut across a corner unless the block count happened
  to put one at each of the four. An ellipse has no corners, so any count lands on it
  exactly. It is also the better mesh — `docs/research/gridpro-blocking-method.md` §12b
  measured a ring taken straight to a rectangle at **89.2°** of worst non-orthogonality
  against a circle's **48.1°** — and the rectangular far field a reader may be picturing
  wants an **H between the ring and the box**, which is a different family and is not this
  one.
- **THE SIZE IS AN EQUIVALENT RADIUS MULTIPLE, SO IT MEANS THE SAME THING AT EVERY
  ASPECT.** `sqrt(a*b)` is pinned to `ratio * body_R`; the derived radial count reads that
  figure, so a user who stretches the far field and saw the count move would be watching an
  accident. Gate: `tests/test_topology_ogrid.py` 18b.
- **A GENERATED SIDE CARRIES THE RUN'S `BC_GEOM`**, because a free corner and a declared
  curve belong to no geometry. Said in the field-spec row that offers the choice, not
  discovered: a mesh wanting an inlet and an outlet on different parts of its outer
  boundary still has to draw one. The mesher also warns (a `wall` declaring a `curve`
  names `binding`), which is correct and expected here.
- **THE TWO GENERATED-PATH ROWS ARE `float` AND NOT `sci`, AND THAT IS A RULE RATHER THAN
  A WIDGET CHOICE.** The standing rule is that a PHYSICAL LENGTH is a `SciDoubleSpinBox`;
  these two are DIMENSIONLESS. The widget is also what `case_type_scale.LENGTH_KIND` is
  keyed on, so calling a dimensionless number a length there would ask a case type to
  rescale a ratio into another drawing. Gate: `tests/test_case_type_scale.py` check 7,
  both directions.
- **THREE REFUSALS THE DRAWN PATH NEVER NEEDS, each naming what the user can change:**
  1. **a size under `MIN_RATIO`** (1.5 body radii) — below it the ring is a sliver the
     mesher fills with folded cells rather than refusing;
  2. **CONTAINMENT, walked over the body's OWN POINTS** and never compared against an
     equivalent radius. That is #165's ruler mistake, and the 4.0 × 0.2 body it was
     measured on is this gate's fixture too: its equivalent radius is 0.505, so a far
     field at 1.5 "radii" is an ellipse of radius 0.76 and the body reaches x = ±2
     straight through it;
  3. **THE FAN** — every outer corner is placed along the ray from the body's centroid
     through its own corner, so the radials cannot cross exactly when the body is
     STAR-SHAPED about that centroid **at the corners it is cut at**. Measured at the
     corners and not over the whole outline, deliberately: a cambered section's lower
     surface is not star-shaped everywhere while its block corners are, and over-refusing
     would turn a working aerofoil into an error. The sentence names the two ring
     positions that are out of order, because "your body is not star-shaped" is a property
     the user cannot see.
- **NAMING A FAR FIELD PUTS THE FAMILY BACK ON THE DRAWN PATH, DOCUMENT FOR DOCUMENT**,
  and the two generated rows go INERT through `Plan.inert_rows` — the C-grid's mechanism
  and its direction: a row is inert because of what the user CONFIGURED, never because of
  what they typed into it. Gate: 18f, which is what makes the rest of group 18
  non-vacuous.
- **THE COST IS MEASURED AGAINST THE DRAWN PATH AND NOT AGAINST A CONSTANT.** Gate 18g
  runs both on the SAME body: a constant there would measure the FIXTURE, whose ten points
  per segment are worth 15° of non-orthogonality on their own (#93's residue). Measured,
  the two are **equal to six decimals** — the worst cell is on the body in both, and a
  generated side is an exact ellipse where a drawn one is a stored polyline, so it has no
  faceting of its own to contribute.
- Gated by `tests/test_topology_ogrid.py` group 18 (18, 18b, 18c, 18d, 18f, 18g), with the
  drawn path's own checks unchanged beside it.
  Why: `docs/design_notes/gui.md`, "A FAR FIELD NOBODY DREW".

## Named blind spots

- **NOTHING CHECKS THAT A `RATIO` FIELD REALLY IS DIMENSIONLESS.** `test_case_type_scale.py`
  check 7 holds that every `sci` field has a judgement and that each KIND does what it
  says; classifying a dimensionless field as `SIZE` instead passes everything, because
  whether a number carries a dimension is a judgement about the quantity and not a fact
  the field-spec row records. Measured as an injection in #197's own round: it came back
  GREEN. What #197 did instead was move the two rows OFF `sci` entirely, so the question
  is not asked of them — which fixes these two and not the shape.
- **THE FAN TEST IS AT THE CORNERS, SO A BODY THAT DIPS BACK BETWEEN TWO OF THEM PASSES.**
  Deliberate (see the rule), and the failure it leaves reachable is the mesher's own: a
  fold, reported as an inverted-cell count. No shipped case reaches it, and nothing
  measures how deep a dip would have to be.
- **NO SHIPPED `config/multiblock_*.dat` USES THE GENERATED PATH.** Every shipped
  document was hand-written before this family existed, so the only coverage is the gate's
  own run through the real mesher. A shipped case would also be the first to exercise the
  mesher's `curve`-on-a-`wall` warning in anger.
