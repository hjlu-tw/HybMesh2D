# PROTOTYPE — which solution field picks a curve you'd accept as a block boundary?

Throwaway. Nothing imports this; no gate runs it. Kept as a primary source for the
finding below.

    python3 prototypes/sensor_fields/plot_sensors.py <case_name_or_tecplot_path>
    WINDOW=-3,3,-3,3 python3 prototypes/sensor_fields/plot_sensors.py tworing_conv_control

## The question

The proposal: run a coarse mesh, solve it, use the result's DENSITY GRADIENT to
decide where the blocks go. `docs/research/solution-driven-block-decomposition.md`
says a bare `|grad rho|` is the one sensor nobody ships. This measures that claim on
this repo's own solver output.

Four candidate sensors plus a CONTROL:

| sensor | what it is |
|---|---|
| `|grad rho|` | the proposal, raw |
| `h |grad rho|` | the same, scaled by cell size (Fluent-style) |
| `h |grad p| / p` | a pressure switch |
| `|vort|` | straight out of the solver, no derivative taken |
| **`|grad h|`** | **THE MESH ALONE. No flow data whatsoever.** |

The control is the whole method. Every sensor is computed with the same
cell→node→linear-gradient operator, so the operator's own mesh-dependence is
shared by the control and cancels out of the comparison.

## What it measured

Each sensor's iso-curve at its own 97th percentile, scored on how many
DISCONNECTED pieces it breaks into and how long the longest one is. A usable
block boundary is few long pieces; speckle is many short ones.

## The findings

1. **The control beats every flow sensor on the aerofoil case.** On
   `cgrid_hermfill_conv` the mesh alone gives 3 pieces / longest 36.21, better than
   `|grad rho|` (4 / 19.04), the pressure switch (3 / 34.23) and `|vort|` (4 / 34.44).
   The mesh was BUILT with a wake refinement and a trailing-edge block interface, so
   a sensor computed on it partly reads that decision back. Using the result to
   choose blocking is therefore partly a feedback loop, and the loop is invisible
   without a control.

2. **Density carries no signal at these operating points.** Every shipped case is
   `fs_Mach 0.2`, `fs_UnitRe 200`, `fs_flow_angle 0`. On the converged runs the
   density spread is 2.45% (`cgrid_hermfill_conv`), 1.48% (`cgrid_linfill_conv`) and
   **0.24%** (`tworing_conv_control`). No shock exists anywhere to be found.

3. **Raw `|grad rho|` is the one that tracks the mesh.** Spearman rank correlation
   with `|grad h|` on `tworing_conv_control`: raw `|grad rho|` **0.374**, while the
   three scaled sensors sit at −0.008, −0.025, −0.028. The research note's
   "normalisation is mandatory" is visible in one number.

4. **Scaling trades one artefact for another.** `h |grad rho|` and the pressure
   switch both render the O-grid's radial spokes across the whole domain, and
   blocky far-field cell-size patterns on the C-grid. Multiplying by `h` imports the
   mesh's own texture.

5. **`|vort|` is the only one that looks like physics** — and it needs no derivative,
   because the solver already writes it.

6. **An unconverged solve looks like a strong signal.** `multiblock_cgrid_demo`
   stops at 90 iterations with residuals still rising in places, and reports a
   density spread of **28.87%** — an order of magnitude more than the converged run
   of the same geometry. Read as a sensor, that transient is indistinguishable from
   a feature. This matches L6 of the research note: the field always runs this as a
   LOOP with a termination test, never as one coarse pass.

## Caveat

The gradient operator (cell → area-weighted node average → linear-triangle
gradient) is itself mesh-dependent. That is why the control exists; conclusions are
drawn only from sensor-vs-control comparisons, never from a sensor's absolute level.

## Round 2 — the same question asked of an UNBIASED coarse mesh

Round 1's finding was that the control won on a mesh that had already been blocked.
Round 2 builds the mesh a novice would actually produce — the hybrid path,
`prototypes/sensor_fields/hybrid_probe*.json`, 16,796 cells, nothing refined in the
wake — and runs the same flow (M 0.2, Re 200, alpha 0, ns_sol, the settings copied
from `cgrid_hermfill_conv`) on it. Same flow, two very different meshes.

### 7. The control's score is a property of the MESH, and it discriminates sharply

| coarse mesh | control pieces | longest | what it picked out |
|---|---|---|---|
| C-grid, structured, wake refined | 3 | **36.21** | the wake line and the TE block interface |
| two-ring O-grid, structured | 4 | 0.85 | a RING round the body — where its blocking is |
| hybrid, unstructured, wake not refined | **41** | **0.35** | speckle; no wake line at all |

So the coarse mesh must have no opinion, or the sensor reads its blocking back. This
is a usable PRE-FLIGHT check for the proposed subprogram: compute the control first,
and refuse if the mesh's own `|grad h|` yields a long coherent curve.

**Confound, stated rather than hidden.** The control is coherent on structured meshes
and speckled on unstructured ones, so it may be measuring "structured vs not" rather
than "already blocked". On a structured mesh `|grad h|` peaks where the grading
changes, and that is where the blocking is — the two readings are the same statement.
The design consequence is unchanged; the causal claim is not stronger than this.

### 8. On the unbiased mesh, NO sensor finds the wake either

Converged to 49,750 iterations, residual 8.4e-8 (better than any shipped case). Every
sensor returns 2 pieces, longest 0.21–0.45, clustered on the leading edge. The wake is
visibly present in the `|vort|` field and never reaches the 97th percentile, because
the wall's vorticity is orders of magnitude larger. Masking the body plus 0.15 and
re-thresholding (`MASK_WALL=0.15`) does not rescue it: all four then trace a ragged
ring just outside the mask, 5–15 pieces. The mask only moved the wall outward.

This measures, for all four sensors rather than just density, what the research note
could only infer **[I]** — the near-wall field dominates any global threshold.

### 9. CFL 0.6 NaNs on this mesh at iteration ~1000

`Average norm is a nan, exiting....`, on a mesh whose BL holds triangles of edge ratio
35.6. The same CFL runs 50,000 iterations on the structured C-grid. CFL 0.3 converges
further than any reference case.

### 10. `bl_layers` is inert below 13 — SIDE FINDING, not chased

`bl_layers` of 0, 2 and 8 all print "Generating 13 boundary layers" and produce
byte-identical mesh statistics (8594 vertices, 16796 elements, max edge ratio
35.608); 20 is honoured. Whether this is `BL_AUTO_TRANSITION_LAYERS` LOCAL adding to
a floor, or a floor elsewhere, was not investigated — it is outside this prototype's
question and may warrant its own ticket.

## Round 3 — the negative result was about the FLOW, not the sensor

Rounds 1–2 ran at the only operating point this repo ships: M 0.2, Re 200, alpha 0.
That flow is laminar, symmetric and has no sharp feature, so "no sensor found
anything" could not be told apart from "there was nothing to find". Round 3 runs the
SAME coarse hybrid mesh at M 0.8, alpha 1.25, Euler — the classic transonic NACA 0012,
which has an upper-surface shock. Converged to 49,750 iterations, residual 3.5e-8.
It reaches M 1.28 and a density spread of 95.66%, so the supersonic pocket is there.

### 11. Every sensor is reported RELATIVE to its own mesh's control

The absolute length is meaningless across meshes (a wake cut is 19 long, a ring round
a cylinder is 0.85). The ratio to what the bare mesh yields is the same question
everywhere.

| case | mesh | `|grad rho|` | `h|grad rho|` | pressure switch | `|vort|` |
|---|---|---|---|---|---|
| C-grid, M 0.2 | structured, wake refined | 0.53x | 0.96x | 0.95x | 0.95x |
| two-ring, M 0.03 | structured | 0.51x | 6.15x* | 1.65x | 1.00x |
| hybrid, M 0.2 | unbiased | 0.61x | 1.31x | 0.89x | 0.75x |
| **hybrid, M 0.8 (shock)** | **unbiased** | **2.48x** | 3.73x* | 9.98x* | 1.14x |

`*` = inflated by far-field junk, confirmed in the figures; see finding 13.

On both structured meshes every honest sensor is at or BELOW 1.0 — the bare grid
yields a longer curve than the flow does. On the unbiased mesh in a featureless flow,
the same. Only with a shock present does a sensor clearly beat its mesh, and the one
that does it honestly is `|grad rho|` at **2.48x**.

### 12. So the proposal is right in a regime, and wrong outside it

"Coarse solve -> density gradient -> block boundary" needs a SHARP COMPRESSIBLE
feature to work on. With one, raw `|grad rho|` finds it on an unbiased coarse mesh and
the control confirms it is not the grid. Without one — which is every case this repo
currently ships — there is nothing above the mesh's own noise, and on a structured
coarse mesh the blocking you already have wins outright.

### 13. For CURVE EXTRACTION, the h-scaling backfires — the opposite of the orthodoxy

`docs/research/solution-driven-block-decomposition.md` L2 records that every shipped
sensor mandates scaling or normalisation. Measured here, the `h` factor lights up the
COARSE FAR FIELD, and that is where the pressure switch's 9.98x and `h|grad rho|`'s
6.15x and 3.73x come from — long wandering curves in empty space, visible in the
figures. The orthodox sensors are built to WEIGHT REFINEMENT, where rewarding a big
cell with a gradient is the point. Extracting a curve is a different job, and there the
raw gradient was the better-behaved one. The ratio in finding 11 is therefore
necessary but NOT sufficient: it can be gamed by any sensor that blows up where the
mesh is coarse, and it has to be read next to the picture.

## The figures kept, and what each one is for

`results/` is gitignored, so the solves themselves are not in the repo and these
cannot be regenerated from a clean clone without re-running them — the configs beside
them do that, about 12 minutes each.

| figure | the row of finding 11 it is the evidence for |
|---|---|
| `sensors_cgrid_hermfill_conv.png` | C-grid, M 0.2 — the control WINS, 36.21 against 19.04–34.87 |
| `sensors_tworing_conv_control.png` | two-ring, M 0.03 — the control picks out a RING on the blocking; `h|grad rho|`'s 6.15x is the two spoke-aligned lobes |
| `sensors_hybrid_probe_cfl03.png` | hybrid, M 0.2 — the control collapses to speckle, and so does every sensor |
| `sensors_hybrid_probe_transonic.png` | hybrid, M 0.8 — `|grad rho|` finds the shock at 2.48x while the control is unchanged |

Dropped as redundant: the second C-grid fill variant, the unconverged
`multiblock_cgrid_demo` (its finding is a number, not a picture), the 500-iteration
hybrid superseded by the converged one, and the pipeline's own contour PNGs.
