---
paths:
  - services/topology_genfar*
  - services/topology_ogrid*
  - services/topology_tworing*
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
- **WHERE AN OUTER CORNER GOES IS ARC LENGTH, PAIRED WITH THE BODY's OWN — NOT A RAY FAN
  FROM THE CENTROID.** It is the rule the DRAWN path has always used (equal-arc splits
  pairing one to one), said about a curve instead of about a polyline, and the ring is
  anchored by the ray through body corner 0 so the fan still starts where the body does.
  **#197 SHIPPED THE RAY FAN FIRST AND IT WAS WRONG ON A THIN BODY**: on a NACA 0012 at 24
  blocks the first SEVEN outer corners landed in the first 10% of the ellipse while their
  body partners were evenly spaced 4.2% apart, for a mean non-orthogonality of **33.58°**
  against a drawn far field's **14.76** on the same circle at the same counts. By arc
  length it is **14.84**, which is that drawn figure to the drawn circle's own faceting.
  **The two rules AGREE on a round body**, which is why the first evidence could not see
  it. Gate: 18h, with the ray fan as its injection.
- **THAT CHANGE RETIRED A REFUSAL RATHER THAN NEEDING ONE.** A ray fan can cross itself on
  a body that is not star-shaped about its centroid, which cost a check and a sentence the
  user could not act on ("your body is not star-shaped"). Two monotone orderings around two
  nested closed curves cannot cross, so there is nothing left to refuse. **Do not
  reintroduce a fan check**: if one is ever needed again, the placement rule has changed
  and that is the thing to argue about.
- **TWO REFUSALS THE DRAWN PATH NEVER NEEDS, each naming what the user can change:**
  1. **a size under `MIN_RATIO`** (1.5 body radii) — below it the ring is a sliver the
     mesher fills with folded cells rather than refusing;
  2. **CONTAINMENT, walked over the body's OWN POINTS** and never compared against an
     equivalent radius. That is #165's ruler mistake, and the 4.0 × 0.2 body it was
     measured on is this gate's fixture too: its equivalent radius is 0.505, so a far
     field at 1.5 "radii" is an ellipse of radius 0.76 and the body reaches x = ±2
     straight through it.
- **NAMING A FAR FIELD PUTS THE FAMILY BACK ON THE DRAWN PATH, DOCUMENT FOR DOCUMENT**,
  and the two generated rows go INERT through `Plan.inert_rows` — the C-grid's mechanism
  and its direction: a row is inert because of what the user CONFIGURED, never because of
  what they typed into it. Gate: 18f, which is what makes the rest of group 18
  non-vacuous.
- **THE COST IS MEASURED AGAINST THE DRAWN PATH, NOT AGAINST A CONSTANT, AND ON TWO BODIES
  BECAUSE ONE OF THEM CANNOT FAIL.** Gate 18g runs both paths on the same ROUND body — a
  constant there would measure the FIXTURE, whose ten points per segment are worth 15° on
  their own (#93's residue) — and they come back **equal to six decimals**. That is true
  and it is not evidence: the two corner-placement rules coincide on a circle. **18h is the
  check that can fail**, the same comparison on a NACA 0012 with a drawn far field of the
  same two segments: **14.85° against 14.76**, where the rule that shipped first read
  33.58. Quote 18h, never 18g alone.
- Gated by `tests/test_topology_ogrid.py` group 18 (18, 18b, 18c, 18d, 18f, 18g, 18h), with
  the drawn path's own checks unchanged beside it.
  Why: `docs/design_notes/gui.md`, "A FAR FIELD NOBODY DREW".

**AND THE TWO-RING FAMILY TOOK THE SAME PATH, WITH ONE DECISION OF ITS OWN** (#199; the
generated branch of `services/topology_tworing.py`)

- **THE FAR FIELD IS OPTIONAL AND THE SEAM IS NOT**, in the same family, which is the
  clearest statement of where the line actually runs. The outer boundary is analytic and
  may be generated; the seam is an interior line a `follows` edge attaches to, so it has
  to be a stored polyline the user drew. The refusal for a blank seam is unchanged and
  still names **CAD ▸ Offset Geometry…**. Gate: `tests/test_topology_tworing.py` 25b,
  both halves — the blank seam refuses, and the generated document's seam edges still
  `follow` a real geometry while the far-field edges beside them declare a curve.
- **A GENERATED OUTER RING PAIRS WITH THE SEAM's CORNERS, NEVER WITH THE BODY's.** The
  outer blocks run from the seam outward, so the seam is the ring they have to stay
  normal to; pairing with the body hands them the INNER ring's arc-length distribution,
  which the seam has already departed from. Measured on a body whose four segments carry
  unequal shares of its perimeter against an equal-segmented seam: mean non-orthogonality
  **21.613°** seam-paired against **24.688** body-paired, worst **53.70** against
  **64.31**. Gate: 25h, with the body pairing as its injection.
- **THE SIZE IS A MULTIPLE OF THE BODY's EQUIVALENT RADIUS AND CONTAINMENT IS WALKED OVER
  THE SEAM's POINTS.** Two different outlines on purpose: the row means what it means on
  the O-grid and moving the seam does not move the far field, while the thing that must
  be INSIDE the generated ellipse is the seam, because it is the outer ring's inner side.
  `genfar.outside_body` takes the noun as an argument so the refusal names the curve the
  user has to look at. Gate: 25f, **on a seam that can actually poke out** — an elongated
  one whose equivalent radius is 0.894 while it reaches x = ±4. **A ROUND SEAM CANNOT**,
  and the first draft of that check was written on one: the ellipse-radius ordering fired
  first, so two injections against the containment rule came back silent while the check
  passed on a different refusal.
- **THE GENERATED PATH COSTS NOTHING AGAINST A DRAWN FAR FIELD AT THE SAME RADIUS** —
  **21.613° mean, 53.70 worst, both paths, to six decimals** on that same unequal-segment
  fixture. The fixture is one where the paths CAN differ (the body pairing proves it), so
  unlike #197's first evidence this comparison is not measuring a symmetry. 25g is the
  coincident case and is kept for what it rules out, never quoted alone.
- Gated by `tests/test_topology_tworing.py` group 25 (25, 25b–25i), eleven hand
  injections. Ten reddened a check; the eleventh — dropping the SEAM from the required
  list — makes `plan` die on a short list instead, which is detected but takes the checks
  below it with it.
  Why: `docs/design_notes/gui.md`, "THE SAME DOOR, ONE FAMILY ALONG".

## Named blind spots

- **NOTHING CHECKS THAT A `RATIO` FIELD REALLY IS DIMENSIONLESS.** `test_case_type_scale.py`
  check 7 holds that every `sci` field has a judgement and that each KIND does what it
  says; classifying a dimensionless field as `SIZE` instead passes everything, because
  whether a number carries a dimension is a judgement about the quantity and not a fact
  the field-spec row records. Measured as an injection in #197's own round: it came back
  GREEN. What #197 did instead was move the two rows OFF `sci` entirely, so the question
  is not asked of them — which fixes these two and not the shape.
- **THE ARC-LENGTH RULE IGNORES THE BODY's SHAPE, AND NOTHING MEASURES WHERE THAT IS
  WRONG.** It pairs fractions and nothing else, so a body with one long flat and one tiny
  nose gives most of the ellipse to the flat. That is what the drawn path does too, and
  what the two shipped bodies want; a body for which it is the wrong answer would show up
  as a poor mesh and no message. The knob that would answer it is the far field's
  `aspect`, and that one is MEASURED NOT TO HELP: stretching the ellipse on an aerofoil
  takes the mean from 33.58° to 57.97 and the wall from 0.12% to 14.69 (ratio 62, aspect
  1.00 → 0.12), so it is for a body that is itself elongated and not a repair for a ring.
- **NOTHING MEASURES THE PAIRING ON A SEAM THAT IS NOT AN OFFSET OF THE BODY.** 25h's
  fixture is a hand-built body with deliberately unequal segment shares, which is the
  situation the rule has content in — but every seam this repo SHIPS is either a circle
  or an offset, and on those the body and seam pairings coincide to 5.8e-12 degrees. So
  the rule is right and no shipped case exercises it.
- **NO SHIPPED `config/multiblock_*.dat` USES THE GENERATED PATH.** Every shipped
  document was hand-written before this family existed, so the only coverage is the gate's
  own run through the real mesher. A shipped case would also be the first to exercise the
  mesher's `curve`-on-a-`wall` warning in anger.
