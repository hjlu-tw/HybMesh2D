# A Hermite wall-normal term in the multi-block fill — prototyped and measured

**A RESEARCH NOTE, and the answer to issue #157.** Not `.claude/rules/*.md` (what the rule is),
not `docs/design_notes/` (why a shipped rule was chosen). #157 asked a question with a
measurement attached and said in as many words that a NO is a complete outcome; this file is
that measurement. 2026-09-30.

**Nothing shipped changed to write it, and that is measured rather than asserted.** The
prototype lives in `docs/research/hermite-wall-normal-fill/prototype.patch`, is not applied, is
reachable from no `.dat` key, and with its flag off produces **21/21 SAME at exactly
`0.000e+00`** against a binary built from `HEAD` (`tools/scripts/golden_mesh.py`, run
2026-09-30). No default moved, no golden case was recaptured, no pin was edited.

**Reproducing every number here**, from the repo root:

```bash
git apply docs/research/hermite-wall-normal-fill/prototype.patch && ./build.sh
for v in 0 1 2; do
  python3 docs/research/hermite-wall-normal-fill/measure.py --out /tmp/h --variant $v --folds
done
python3 docs/research/hermite-wall-normal-fill/measure.py --report /tmp/h
```

The committed `rows.json` and `folds.json` beside the harness are the run this note is written
from, so `--report docs/research/hermite-wall-normal-fill` prints the tables below without
rebuilding anything.

## How to read the markers

- **[V]** measured by me in this repo, or verified in a primary source I read myself.
- **[I]** my own inference or derivation from a **[V]** fact. Stated as reasoning, not as fact.
- **[2nd]** secondhand only. Treat as unconfirmed.

---

## Lead: the answer, and it is not the one the ticket expected

### A1 — The error it was built to fix needs no fixing, and that half is a clean NO. **[V]**

The offset ring's tilted chord costs **0.070625** unsmoothed on
`config/multiblock_tworing_offset.dat`. The best-faith Hermite fill takes that to **0.000000**.
It does not matter: **the shipped smoother already takes it to `0.000000` at every cap from 1
upward**, and the shipped default is 20. At that default, of the seven shipped configs **five
report the identical `wall_first_cell_worst_rel` under both fills to every digit the line
prints** — `square`, `cavity` and `tworing` at 0.000000, `tworing_offset` at 0.000000, `ogrid`
at 0.000371 — and the two that differ move by 0.000005 (`hgrid`, 0.000806 → 0.000811) and
0.000045 (`cgrid`, 0.000968 → 0.001013), both in the WRONG direction and both four orders under
the error being chased.

`docs/research/arc-length-correspondence-on-an-offset-ring.md` predicted this and #157 quoted
it. The measurement confirms it with nothing left over.

### A2 — The stability hypothesis, which was #157's only argument the smoother does not already answer: also NO. **[V]**

The first cap whose EXPORTED mesh contains an inverted cell, found by a ladder and then a
cap-by-cap linear scan of the bracket (not a bisection — whether the count is monotone in the
cap is a property of the solve, not of arithmetic):

| case | linear | Hermite v1 | Hermite v2 |
|---|---|---|---|
| `square` | never through 1000 | never through 1000 | never through 1000 |
| `cavity` | never through 1000 | never through 1000 | never through 1000 |
| `hgrid` | never through 1000 | never through 1000 | never through 1000 |
| `ogrid` | **202** | **202** | **202** |
| `cgrid` | **333** | **342** | **1** |
| `tworing` | **116** | **116** | **116** |
| `tworing_offset` | **63** | **64** | **64** |

**The fold does not move.** Two of the four folding cases are unchanged to the sweep; one gains
one sweep out of 63; the C-grid gains nine out of 333, which is 2.7%. There are no extra usable
sweeps for a better mesh to live in, so the question "is the mesh better where the extra sweeps
now reach" has no domain to be asked over. #82's warning — that converging this solve is the
*worse* mesh — never had to be invoked.

### A3 — But the prototype does something nobody asked it to, and it is the largest effect in the table. **[V]**

At the shipped default of 20 sweeps, with **0 inverted cells** and the wall figure unmoved,
variant 1 takes the maximum non-orthogonality of the two worst-angled shipped cases down hard:

| case (cap 20) | non-orth max | non-orth mean |
|---|---|---|
| `cgrid` | 29.895° → **10.946°** | 3.821° → **2.739°** |
| `tworing_offset` | 28.796° → **25.989°** | 9.482° → **7.229°** |

Everything else at that cap is small: `square` and `cavity` are **bit-identical** (the
correction is algebraically zero wherever the linear blend already delivers the declared spacing
in the declared direction, which is every rectangle, graded or not), and `hgrid`, `ogrid` and
`tworing` move the *wrong* way by **+0.001°, +0.187° and +0.171°** of maximum non-orthogonality
with their wall figures unchanged to six decimals. Cell shape moves by under 3.3% in either
direction on every case.

The C-grid's win is not a scoring artefact. Its mesh is visibly better round the nose, its
inverted count is 0, and its `.cel` is still conforming — measured on both exports with
`test_multiblock_weld_surface.py`'s own helpers: **no edge used by more than two cells, the 320
free edges exactly the 320 `.bnd` rows' node pairs as a SET and not merely as a count, one
connected component**, identical under both fills. Its cell-shape p95 falls from 148.006 to
145.447 while the median rises 4.832 → 4.991.

**So the honest recommendation is neither the ticket's expected flat NO nor a YES.** It is that
the quantity worth a feature ticket is not the one #157 named: the wall height needs nothing,
the stability budget does not move, and the angle — which nobody was asking the fill about —
does. That is a different ticket with a different argument, and §5 says what it would have to
answer before it is one.

---

## 1. What was built

Two variants, behind `HYBMESH_MB_FILL_HERMITE`, set by the adapter in `src/cli.cpp` into a new
`MbParams::fillHermite`. **An environment variable and not a `.dat` key, deliberately**: a key
would have to reach `Config`, the GUI↔C++ parity table, the field-spec tables and
`inertParamsSet`, and #157's acceptance says nothing shipped changes.

Both are written as an **additive correction** to the existing `coons()` result rather than as a
second fill, and that shape is load bearing three ways. **[V]** With both boundary tangents set
to the linear-equivalent `T = E − W`, the cubic Hermite blend collapses *algebraically* to
`W + u(E − W)` — `H10 + H11 = 2u³ − 3u² + u` cancels `H00`/`H01`'s cubic part exactly — so the
whole change is carried by how far each end's tangent DEPARTS from that, and the correction is
identically zero where nothing departs. It vanishes on all four sides, so the boundary is still
the edge's own discretisation and the welding is untouched. And the two directions' corrections
simply add, each being the boolean sum's own Hermite-minus-linear difference including the
tensor term.

**Variant 1 is Thompson, Warsi & Mastin Ch. VIII §1.B taken literally**: `T = (req/gap)·n̂`, so
the first interior node sits at `wall + req·n̂` to first order in `gap`, where `gap` is the
first interior grid line's own blending coordinate and `req` is the declared off-wall spacing.

**Variant 2 is the same cubic correction calibrated against the fill's own first interior
line**: `δ = (req·n̂ − actual first step) / H(gap)`, forced to zero at the side's two end
stations. It exists so that a NO cannot be blamed on variant 1's truncation error.

Both read the request the way `src/MbQuality.cpp` measures it — the two corner declarations
blended **linearly in the logical coordinate** — because driving the fill at one measure while
the ruler reads another is the defect `.claude/rules/mesher-smoothing.md` names by name.

## 2. Where the prototype's own arithmetic bit, and how it was found

Recorded because two of the three are interesting, and because the first one produced a
confident wrong answer that survived a whole measurement round.

**(a) One-sided end tangents, and the error does not stay at the end.** **[V]** The first
version took the wall tangent at station 0 as the chord `wall[1] − wall[0]`, which on a curved
wall is tilted from the true tangent by half the turn across that interval — **1.9° on the
shipped O-grid's body arc**. That would be a corner-only error except that the boolean sum's
tensor term subtracts a blend of the two END deltas from *every* station, so a wrong end tangent
pollutes the whole side. Measured: the O-grid's unsmoothed wall first-cell error went
**0.000036 → 0.024536** — 680× worse on a case whose fill is otherwise exact. The ends now
extrapolate the two adjacent facet directions (`1.5·d01 − 0.5·d12`), which is exact on a circle
to the order the interior's central difference is, and the same figure becomes 0.002814.

**The lesson is not "use better tangents".** It is that a first measurement round had already
been taken, tabulated and half-interpreted against the buggy version, and every number in it was
wrong in the same direction. What caught it was not a test — nothing here has one — but the
O-grid's 0.000036, a figure the design notes say is *the faceting and nothing else*, moving by
three orders. A case whose shipped answer is known to be exact is the instrument.

**(b) Variant 1's residual is a factor, and the factor is not always small.** **[I]**, derived
and then **[V]** against the table. Writing out the boolean sum at the first interior line, with
`T_far` left at the linear equivalent:

```
r(gap) − wall  =  req·n̂·(1 − gap)²  +  gap²(2 − gap)·chord
                =  req·n̂  −  gap(2 − gap)·[ gap·chord − req·n̂ ]
```

so **the Hermite fill's first-cell error is `gap(2 − gap)` times the linear fill's own error
vector.** On a strongly clustered wall `gap` is ~1e-4 and the error all but vanishes; on a
coarse one it barely shrinks. This is #157's own "exact only to first order in the first
interval", with the factor named.

**(c) The calibration target was the wrong vector, and the H-grid is where that shows.** **[V]**
Variant 1 measures its departure against the pure `u`-term `gap·chord`, which is NOT what the
transfinite fill puts on the first interior line when the two facing perpendicular edges carry
different laws — the Coons `u`-terms contribute there too. On `hgrid`'s `h00`, which asks for
**1.504e-01** at one end and **2.000e-01** at the other, the linear fill delivers **0.00%** and
variant 1 delivers **4.40%**: a correction applied to a row that needed none. Variant 2 was
written for this and is worse still on that wall (**6.34%**), for the reason in (d).

**(d) Variant 2 hits the target exactly and folds the C-grid, and the reason is the basis
function.** **[V]** Unsmoothed, variant 2 takes `tworing_offset` from 0.070625 to **0.000000**
and `ogrid` from 0.000036 to **0.000003** — the prescription, achieved. It also puts **116
inverted cells** in the unsmoothed C-grid and keeps between 140 and 320 of them at every cap
through 60. **[I]** The arithmetic is the finding: `H10` peaks at **4/27 ≈ 0.148** at `u = 1/3`
while its value at the first interior line is `H10(gap) ≈ gap`. Calibrating the tangent to fix
the first row therefore multiplies the *mid-block* displacement by `0.148/gap`, which on the
C-grid's `gap ≈ 1e-4` is **≈ 1.4e3**. A cubic Hermite correction cannot be both exact at the
wall and small in the interior when the wall clustering is strong. Anything that could would not
be a cubic — it would be a blend that decays over the first few layers, which is a different
construction and is not what TWM Ch. VIII §1.B describes.

That is the sharpest thing this spike learned, and it was not visible from the literature.

## 3. The measurement tables

Seven shipped configs × three fills × ten caps, every figure off the run's own
`HYBMESH_MB_QUALITY` line. The full ten-cap tables are in `rows.json`; the two caps that decide
anything are here. `wall` is `wall_first_cell_worst_rel`; `shp` is the quad midline ratio.

### Cap 0 — the fill alone

| case | fill | inv | non-orth max | non-orth mean | wall | shp median | shp p95 |
|---|---|---|---|---|---|---|---|
| square | linear | 0 | 0.0000 | 0.0000 | 0.000000 | 1.0000 | 1.0000 |
| square | hermite1 | 0 | 0.0000 | 0.0000 | 0.000000 | 1.0000 | 1.0000 |
| square | hermite2 | 0 | 0.0000 | 0.0000 | 0.000000 | 1.0000 | 1.0000 |
| cavity | linear | 0 | 0.0000 | 0.0000 | 0.000000 | 1.0000 | 1.0000 |
| cavity | hermite1 | 0 | 0.0000 | 0.0000 | 0.000000 | 1.0000 | 1.0000 |
| cavity | hermite2 | 0 | 0.0000 | 0.0000 | 0.000000 | 1.0000 | 1.0000 |
| hgrid | linear | 0 | 3.0987 | 0.4455 | 0.001464 | 1.1894 | 1.3889 |
| hgrid | hermite1 | 0 | 4.0428 | 0.4453 | 0.044044 | 1.1863 | 1.3889 |
| hgrid | hermite2 | 0 | 4.4575 | 0.4452 | 0.063423 | 1.1848 | 1.3889 |
| ogrid | linear | 0 | 2.0250 | 1.8750 | 0.000036 | 1.8417 | 23.4330 |
| ogrid | hermite1 | 0 | 2.2157 | 1.8750 | 0.002814 | 1.8368 | 23.4873 |
| ogrid | hermite2 | 0 | 2.0250 | 1.8750 | 0.000003 | 1.8381 | 23.4358 |
| cgrid | linear | 0 | 32.0441 | 4.5619 | 0.004368 | 4.7739 | 148.1963 |
| cgrid | hermite1 | 0 | **18.3101** | 3.6077 | 0.010971 | 4.9661 | 147.6699 |
| cgrid | hermite2 | **116** | 36.0077 | 1.7979 | 0.012599 | 4.7806 | 139.5096 |
| tworing | linear | 0 | 2.0250 | 1.8750 | 0.000171 | 1.6268 | 20.8202 |
| tworing | hermite1 | 0 | 2.2150 | 1.8750 | 0.002803 | 1.6261 | 20.8696 |
| tworing | hermite2 | 0 | 2.0250 | 1.8750 | **0.000000** | 1.6259 | 20.8249 |
| tworing_offset | linear | 0 | 29.3518 | 9.9107 | 0.070625 | 2.1548 | 16.9733 |
| tworing_offset | hermite1 | 0 | 30.0893 | 7.2188 | 0.003793 | 2.1513 | 17.4455 |
| tworing_offset | hermite2 | 0 | 30.2232 | 7.1999 | **0.000000** | 2.1514 | 17.3882 |

### Cap 20 — the mesh a user actually gets

| case | fill | inv | non-orth max | non-orth mean | wall | shp median | shp p95 |
|---|---|---|---|---|---|---|---|
| square | linear | 0 | 0.0000 | 0.0000 | 0.000000 | 1.0000 | 1.0000 |
| square | hermite1 | 0 | 0.0000 | 0.0000 | 0.000000 | 1.0000 | 1.0000 |
| square | hermite2 | 0 | 0.0000 | 0.0000 | 0.000000 | 1.0000 | 1.0000 |
| cavity | linear | 0 | 0.0000 | 0.0000 | 0.000000 | 1.0000 | 1.0000 |
| cavity | hermite1 | 0 | 0.0000 | 0.0000 | 0.000000 | 1.0000 | 1.0000 |
| cavity | hermite2 | 0 | 0.0000 | 0.0000 | 0.000000 | 1.0000 | 1.0000 |
| hgrid | linear | 0 | 2.8590 | 0.4354 | 0.000806 | 1.1644 | 1.3914 |
| hgrid | hermite1 | 0 | 2.8600 | 0.4315 | 0.000811 | 1.1617 | 1.3907 |
| hgrid | hermite2 | 0 | 2.8604 | 0.4304 | 0.000813 | 1.1605 | 1.3904 |
| ogrid | linear | 0 | 2.0250 | 1.8750 | 0.000371 | 1.8460 | 23.6623 |
| ogrid | hermite1 | 0 | 2.2122 | 1.8750 | 0.000371 | 1.8457 | 23.7108 |
| ogrid | hermite2 | 0 | 2.0250 | 1.8750 | 0.000371 | 1.8460 | 23.6644 |
| cgrid | linear | 0 | 29.8951 | 3.8212 | 0.000968 | 4.8320 | 148.0057 |
| cgrid | hermite1 | 0 | **10.9456** | **2.7390** | 0.001013 | 4.9907 | 145.4466 |
| cgrid | hermite2 | **316** | 79.1993 | 1.9524 | 0.001017 | 5.0045 | 179.1041 |
| tworing | linear | 0 | 2.0250 | 1.8750 | 0.000000 | 1.6854 | 21.1287 |
| tworing | hermite1 | 0 | 2.1955 | 1.8750 | 0.000000 | 1.6856 | 21.1726 |
| tworing | hermite2 | 0 | 2.0250 | 1.8750 | 0.000000 | 1.6854 | 21.1323 |
| tworing_offset | linear | 0 | 28.7957 | 9.4818 | 0.000000 | 2.2264 | 17.1814 |
| tworing_offset | hermite1 | 0 | **25.9888** | **7.2289** | 0.000000 | 2.2227 | 17.6675 |
| tworing_offset | hermite2 | 0 | 26.0629 | 7.2008 | 0.000000 | 2.2240 | 17.6098 |

### The angle across the whole cap range, on the two cases that move

`cgrid` maximum non-orthogonality, linear → hermite1: 0 sweeps **32.044 → 18.310**, 1 **31.861 →
17.231**, 2 **31.736 → 16.168**, 5 **31.382 → 13.532**, 10 **30.848 → 10.122**, 20 **29.895 →
10.946**, 40 **28.551 → 13.129**, 60 **27.774 → 15.419**, 100 **26.493 → 21.653**, 200 **35.276
→ 34.946**. **[V]** The linear fill's max falls monotonically to sweep 100 and then turns; the
Hermite fill starts far lower, reaches its own minimum around sweep 10 and climbs back toward
the same place. **The two converge**, which is exactly what should happen — they are two initial
guesses for one elliptic solve, and TWM says so — but the shipped cap of 20 is nowhere near
there, so at the shipped default the difference is 19 degrees.

`tworing_offset` maximum, linear → hermite1: 0 **29.352 → 30.089**, 2 **29.280 → 29.422**, 5
**29.198 → 28.528**, 10 **29.071 → 27.361**, 20 **28.796 → 25.989**, 40 **28.173 → 25.014**, 60
**27.588 → 24.616**. Worse unsmoothed, better from sweep 5 to 60. Its **mean** is better at
every cap measured, by 2.2 to 2.7 degrees.

### The circles are the negative control, and they fail it by 0.19° **[V]**

`ogrid` and `tworing` are the cases where `coons()` already reproduces a polar annulus
*exactly*, so **any** change to the fill is a regression there by construction. Variant 1 costs
them **+0.187°** and **+0.171°** of maximum non-orthogonality at the default and nothing else;
variant 2, which is exact at the wall, costs them nothing at all (2.0250 to four decimals at
every cap). That is the cleanest statement of what variant 1's truncation is worth: about a
fifth of a degree on a case that was already right.

### The hypothesis' own mechanism IS real, and it still does not move the fold **[V]**

#157's argument was "if a Hermite fill lets the control functions do less work, it might buy
stability", quoting TWM: *"The optimum acceleration parameters and the convergence rate decrease
as the control functions increase in magnitude."* That quantity is published — `clipped=` on
`HYBMESH_MB_SMOOTH`, the count of source terms that hit `MB_CONTROL_CLIP` — and on the C-grid
it moves exactly the way the hypothesis says it should:

| `cgrid`, `clipped=` | sweep cap 1 | 2 | 5 | 10 | 20 |
|---|---|---|---|---|---|
| linear | **40** | **28** | **8** | 0 | 0 |
| hermite1 | **20** | **4** | **0** | 0 | 0 |

**The Hermite fill halves the clip count at the first sweep and empties it two caps earlier.**
The control really does have less to do, on the one case where it had anything to do at all —
every other shipped case reports `clipped=0` at every cap through 20 under every fill.

**And it buys nothing.** Up where the folds are, the saturation counts are the same to within a
few cells: `tworing_offset` at cap 100 is **112 / 112 / 112** and at 200 **236 / 240 / 240**
(linear / hermite1 / hermite2); `tworing` at cap 200 is **400 / 400 / 400**. The clip count
falls faster early and lands in the same place late, and the first-inversion cap in A2 moves by
at most nine sweeps. **The mechanism is confirmed and the consequence is not** — which is a
stronger NO than "we could not see the mechanism".

The residuals say nothing either way, and by #156's rule they may not be read as a statement
about the mesh: at cap 20, residual / best / best sweep, linear → hermite1 — `hgrid`
1.774e-04→1.653e-04 (sweep 20 both, still falling); `ogrid` 4.545e-04→4.547e-04 (sweep 2 both);
`cgrid` 9.030e-04→9.909e-04 (sweep 1 → 5); `tworing` 4.489e-04→4.489e-04 (sweep 2 both);
`tworing_offset` 4.847e-04→4.861e-04 (sweep 4 → 6).

## 4. What each of #157's acceptance items got

- **A measurement table over every shipped config, at several caps, for both fills, including
  the first-inversion sweep** — §3 and A2, over three fills rather than two. **[V]**
- **Does the mesh a user gets at the shipped default change, and in which direction, per case?**
  `square` and `cavity` **not at all, bit for bit**. `hgrid` **negligibly worse** (max
  +0.001°, wall +0.6% relative on a 0.08% figure). `ogrid` and `tworing` **slightly worse**
  (max +0.19° and +0.17°, wall unchanged). `cgrid` **much better** (max −18.95°, mean −1.08°,
  wall 0.000968 → 0.001013, shape p95 −1.7%, shape median +3.3%). `tworing_offset` **better**
  (max −2.81°, mean −2.25°, wall unchanged at 0.000000, shape p95 +2.8%). Under variant 2 the
  C-grid is **folded** and everything else is within noise of variant 1. **[V]**
- **Does the fold move, and is the mesh better where the extra sweeps now reach?** The fold does
  **not** move (A2). The second half is therefore unanswerable and did not need answering: at
  most nine extra sweeps out of 333 exist on one case, and none on two others. **[V]**
- **The answer recorded in `docs/research/`, citing what was measured** — this file.
- **Nothing shipped changes** — 21/21 golden SAME against a `HEAD` binary with the flag off; no
  default, no golden capture, no pin touched; the prototype is a patch file and is not applied.
  **[V]**

## 5. What a feature ticket would have to answer, if anyone writes one

It would not be #157's ticket. The height needs nothing and the stability budget does not move;
the only thing on the table is the angle, on two of seven cases. Before that is worth the blast
radius #157's §3 enumerates — 21 golden cases, `PINS` and `BAND_PINS`, the per-case figures in
three instruction files and four gate docstrings — it would have to answer:

1. **Does the angle buy anything downstream?** Nothing here ran the solver. The C-grid's 32° is
   the figure #57's gate-2 diagnosis turned on, and 11° is a large move, but "the solver runs"
   was already true at 32° and no pressure distribution has been compared with anything. **This
   is the load-bearing gap.** One `getPGrid` + `unicones` run at #57's own operating point
   (M 0.2, Re 200, zero incidence, 100 iterations, `cfl 0.6`) on both meshes would settle
   whether the question is worth asking.
2. **What is done about the H-grid?** Variant 1 costs `h00` 0.15% → 4.40% unsmoothed, and the
   cause is understood (§2c): the correction is calibrated against the pure `u`-term rather than
   against the fill's own first interior line. Variant 2 fixes exactly that and folds the
   C-grid, so the fix is not "use variant 2" — it is a calibration that is right *and* bounded,
   which neither variant is.
3. **What about the twist?** Both variants superpose two one-directional corrections and drop
   the cross derivative at a corner where both directions carry a wall. Every shipped case with
   walls in both directions (`square`, `cavity`, `hgrid`) is straight-sided, so nothing here
   exercises a curved twist at all. **[V]**
4. **Is a cubic the right basis?** §2d says a cubic cannot be both exact at the wall and small
   in the interior under strong clustering. A blend that decays over the first few layers could
   be, and is not what TWM Ch. VIII §1.B describes. That is a different construction and would
   need its own literature pass.

## 6. Gaps I could not close, by name

- **No solver run, on either fill.** §5 item 1. Everything in this note is the mesher's own
  ruler measuring the mesher.
- **`TWM Ch. VIII Eq. (66)–(67)` is still secondhand.** The gap
  `arc-length-correspondence-on-an-offset-ring.md` named is unchanged: the passage exists and
  was read, the equation images did not survive text extraction. Variant 1 is written from the
  prose quoted in that note plus my own derivation, not from the equations. **[2nd]**
- **Only the seven shipped configs.** No sweep over wall spacing, block count, curvature ratio
  or aspect ratio. The two cases that improve are the two with the worst angle, which is
  suggestive and is not a trend over two points.
- **The first-inversion figure is a CAP, not a sweep.** The solve stops early on convergence and
  rolls back to its best iterate on divergence, so what was scanned is "the lowest cap whose
  exported mesh has an inverted cell". Monotonicity in the cap was measured only inside each
  bracket, by a linear scan; outside the bracket the ladder could in principle have stepped over
  a folded island. An earlier bisection, over a COARSER ladder and therefore over different
  brackets, returned the same seven answers for the linear fill — weak evidence that the count
  is monotone in the cap, and not a proof.
- **The wall-band split was recorded and not analysed.** `rows.json` carries
  `quad_midline_ratio_layer_*` and `_bulk_*` for every run; this note reads only the whole-mesh
  triple. A band that moved while the whole-mesh figures did not would be invisible above.
- **The C-grid's improvement is not attributed.** I measured that it happens and that the mesh
  is conforming, sane and visibly better round the nose; I did not localise *which* cells
  stopped being skew, so "the Hermite fill straightens the near-wall lines" is a plausible story
  and not a measurement. **[I]**
- **Nothing here is gated.** The harness is not a test, nothing in CI runs it, and the numbers
  above go stale the moment the fill, the smoother or a shipped geometry changes. That is the
  same status `docs/research/`'s first note carries and is deliberate — but it means a reader in
  six months should re-run the four commands at the top before quoting a figure.

## Sources

- Thompson, Warsi & Mastin, *Numerical Grid Generation: Foundations and Applications* (1985),
  Chapters VI, VII and VIII. Free PostScript at
  https://polyakov.imamod.ru/arc/books/MESH_GEN_1/index.html. Ch. VIII §1.B is the Hermite
  boundary-derivative prescription this note prototypes; Ch. VI §2F is the elliptic control-
  function repair this repo already implements. Quoted at length in
  `docs/research/arc-length-correspondence-on-an-offset-ring.md`.
- `docs/research/arc-length-correspondence-on-an-offset-ring.md` — the note that prompted #157,
  including the offset-curve arc relation and the three sizes of fix.
- In this repo: `src/MultiBlock.cpp` (`coons`, `arcFraction`), `src/MbQuality.cpp` (the ruler),
  `src/MbControl.cpp` (the control functions), `.claude/rules/mesher-smoothing.md`,
  `.claude/rules/mesher-quality.md`, `.claude/rules/mesher-multiblock.md`,
  `tools/scripts/golden_mesh.py`.
