#!/usr/bin/env python3
"""The multi-block smoothing pass, end to end through the real binary (#81-#84).

The kernel, the control functions and the freeze rule are pinned next door in
``tests/cpp/test_multiblock.cpp`` checks 40-56, which link the pure layer alone
and drive ``buildMultiBlock`` with a topology STRING: which nodes move and which
are frozen (41), that the kernel is the WINSLOW update of a node's nine logical
neighbours with its two source terms (against hand-worked numbers, checks 48 and
52), that a grid whose answer is known comes back unmoved (47), that the wall gate
is the DECLARED KIND and the target is the ruler's own blend (51), that a grid
already holding what the declaration asks for is asked for nothing (53), that the
solve reaches all three of its endings (49), and — since #84 — that a shared node
is moved ONCE by IDENTITY, that the ghost layer IS the neighbour's own first
interior line, that either block would compute the same position from it, and that
the four-way corner does not move (56). What can only be checked out here is the
half that reaches a user: that ``MB_SMOOTH_ITERS`` travels from a ``.dat`` into the
seam at all, that the run REPORTS what smoothing bought, which nodes it was free to
move and whether its solve finished, that the reporting is unchanged when nothing
was smoothed, and #83's and #84's acceptance figures on the shipped files.

Driven on the SHIPPED C-grid (``config/multiblock_cgrid.dat``) and the SHIPPED
O-grid (``config/multiblock_ogrid.dat``), read from disk through the gates that
own them rather than composed here — the same rule the golden comparator follows:
these files are documentation a user runs, and an edit to one has to be visible
from a gate.

SINCE #114 GROUP 13 ALSO DRIVES THE OTHER THREE — ``multiblock_square``,
``multiblock_cavity`` and ``multiblock_hgrid``, so all FIVE shipped multi-block
configs are exercised for the wall warning's floor. Those three have no gate of
their own to import from (nothing else in the tree runs them), so they enter
through ``shipped_config`` below, which retargets by KEY rather than by the needle
list ``base_config`` can afford. What each of the three can and cannot see is in
the blind spots, per config: the floor-revert injection reaches NONE of them, and
saying so is half of what this widening bought. (That group number is a GATED figure
since #116: this line said 12 while the code, the numbered list below, the section
banner and the rule file all said 13, and `test_instruction_budget.py` check 7 now
derives it from the checks that follow the three ``shipped_config`` retargets. Renumber
the group and run that gate with ``--sync`` rather than editing this sentence.)

What this pins down:

  1. At the default (no ``MB_SMOOTH_ITERS`` line at all) the output is what it was
     before this parameter existed: ONE quality block, ONE machine-readable
     ``HYBMESH_MB_QUALITY`` line, and NO ``_BEFORE`` line anywhere.
  2. With sweeps on, the run reports the mesh BEFORE and AFTER — two banners and
     two machine-readable lines — and the BEFORE line is bit-identical to the
     figures the same case prints at the default. So the pair really is one mesh
     measured twice, not two runs that happened to agree.
  3. THE UNSUFFIXED LINE ALWAYS DESCRIBES THE MESH AS EXPORTED. A gate grepping
     ``HYBMESH_MB_QUALITY`` keeps getting the answer about the file on disk,
     smoothed or not, and never has to know which run it is reading.
  4. THE WALL FIRST CELL IS HELD, and #82's own check here asserted the opposite
     because it had no control functions to hold it with. All three of #80's
     figures now move the right way at once.
  5. EVERY COLUMN BEATS THE KERNEL #81 SHIPPED, on both shipped cases and at every
     sweep count either ticket measured.
  6. A NEGATIVE sweep count is refused BY NAME with the CONFIG code and exports
     nothing — never clamped to 0, which would run no smoothing for someone who
     asked for some.
  7. THE SOLVE IS BOUNDED AND SAYS WHICH ENDING IT REACHED, and #84 moved which
     endings the shipped files reach: the C-grid DIVERGES again (at sweep 1111,
     returning that best iterate) where under #83 its residual merely plateaued,
     and its stability limit moved OUT — 0 folded cells at a cap of 100 and 150
     where #83 folded 4 at 100, first folds at 400.
  8. #80's O-GRID NEGATIVE CONTROL: still not met, and now by 1.2% instead of 5.3x.
  9. THE INTERFACES ARE NO LONGER THE KINK, measured on the mid-block radial band's
     own cells and on where the whole mesh's worst corner sits.
 10. #83's ACCEPTANCE on the shipped C-grid, including the near-leading-edge cells
     that ticket asks for specifically.
 11. #84's OWN DELIVERABLES: the freeze rule reported rather than inferred, node
     and cell counts unchanged, the mesh still CONFORMAL by #53's measure, and the
     wake cut measured on its own terms.
 12. THE WALL WARNING'S BAR SITS ABOVE ITS OWN ARITHMETIC (#107). The additive
     term under that bar was 1e-12, BELOW the noise of the quantity it bounds, so
     the shipped C-grid's two outlet-side walls warned on a relative deviation of
     2.3e-12 and printed `0.000000%` against `0.000000%`. Both directions are
     asserted on real files: the two noise warnings are gone, the two walls whose
     deviation is real still warn in the SAME run, and the two that went quiet are
     back at a cap where their own deviation rises above the floor.
 13. AND THE SAME CRITERION ON ALL FIVE SHIPPED CONFIGS (#114), which was checked
     on two of them until that ticket. The H-grid's eight declared wall edges give
     seven warnings whose smallest, 5.90e-6 relative, is now the TIGHTEST upper
     bound this floor has — under the C-grid's `e_ff` pair at 9.499e-6 — and its
     eighth starts 0.15% off its declaration, is IMPROVED to 0.08% and is
     correctly silent, so it pins the bar's BASELINE. That is not unique to it:
     the C-grid's `af_up`/`af_lo` do the same at 0.44% -> 0.05%, nothing asserted
     either before this ticket, and both are asserted now — group 12 for the
     C-grid's pair, group 13 for `v00`. Square and cavity are rectangles the solve
     leaves where it found them, so their walls are at an exact zero before and
     after and the silence is the MESH's rather than the bar's: no floor can reach
     them, and what they gate is a comparison that starts warning about a wall
     nothing happened to.

MEASURED 2026-09-10 on the five shipped multi-block configs, before and after
(counts of `could not hold ... first cell height` warnings, from two builds of this
tree differing only in that constant):

    case      1e-12   1e-9   which edges went quiet
    square        0      0   --
    cavity        0      0   --
    hgrid         7      7   none
    ogrid         4      4   none
    cgrid         4      2   e_out_up, e_out_lo (2.3e-12 relative)

  ONLY THE TWO NOISE WARNINGS MOVED, which is acceptance criterion 2 and is
  measured rather than reasoned about. #107's own text predicted "the hgrid's five
  and the ogrid's two"; the tree says SEVEN and FOUR. The prediction that mattered
  — that none of them would move — holds, and the counts beside it did not, so they
  are corrected here rather than quoted.

  THE FOUR C-GRID EDGES, in full, with the format temporarily widened to read them:

    e_out_up (south of block 0)   2.334e-10 %   was 4.662e-13 %   -> now silent
    e_out_lo (north of block 3)   2.334e-10 %   was 2.260e-13 %   -> now silent
    e_ff_up  (east of block 0)    9.499e-04 %   was 1.686e-13 %   -> still warns
    e_ff_lo  (east of block 3)    9.499e-04 %   was 0.000e+00 %   -> still warns

INJECTIONS, dated 2026-09-10, EXIT CODE READ BEFORE THE FAIL COUNT. Hand runs on
this tree, in the shape the C++ test next door established — a gate cannot mutate
the binary it drove, and rebuilding one from inside a check is not something this
repo ships. Both bite:

  A. the floor restored to 1e-12 (the defect itself). Rebuilt, exit 1, TWO checks
     red and both name `e_out_up`: the absence half and the identical-figures half.
     The negative controls stayed GREEN throughout, which is what says they are not
     riding on the fix.
  B. the floor raised absurdly to 1e-3. Rebuilt, exit 1: `e_ff_up` and `e_ff_lo`
     silenced at the default, their margin check with them, and the two outlet
     walls no longer coming back at a cap of 400. So a bar raised too far is
     caught here and not only a bar left too low.
     **AND THE CHECK LABELLED "THE NEGATIVE CONTROL, gross end" STAYS GREEN under
     it, which the first draft of this log got wrong by saying "the NEGATIVE
     control goes red".** `af_up`'s 27.37% against 0.4368% before clears a bar of
     0.0054 without noticing, and no floor below **0.269** relative can silence
     it. What actually bounds this constant from ABOVE is the `e_ff` pair at
     9.499e-6 — the tightest bound in the tree as of this run; #114's H-grid
     superseded it at 5.90e-6, see the blind spot below. The gross-end control earns its place by
     proving a real loss is never mutable at all, not by bounding the floor.
  B'. B RE-RUN AFTER REVIEW, and this is why it was re-run rather than quoted: on
     the first pass B turned TWO checks red, and the margin check between them
     stayed GREEN because its `all(...)` was vacuously true once both edges
     vanished. With each edge's presence asserted in its own clause it turns red
     too — 3 red, not 2. An injection's own bite count is evidence about the
     CHECKS, so a check repaired after an injection has to face it again.
  Restored to 1e-9 and rebuilt: ALL PASS, and ctest 6/6.

INJECTIONS FOR #114's THREE ADDED CONFIGS, dated 2026-09-11, EXIT CODE READ FIRST.
Same shape: edit `src/MultiBlock.cpp`, `./build.sh`, run this file, `git checkout`
the source and rebuild. The three partition cleanly, and the first one is the
answer to #114's own criterion 2 rather than a confirmation of it:

  A. THE FLOOR BACK TO 1e-12, which is what #114's criterion 2 calls reverting
     the warning guard. **EXIT 1, THREE CHECKS RED, AND ONE OF THEM IS #114's
     OWN** — the H-grid's upper-bound relation, because at 1e-12 the C-grid's
     noise pair returns at 2.3e-10% and is then the lowest warning in the tree.
     So the criterion's literal reading IS met on the H-grid. It took three
     attempts to find that out, and the two that failed are worth more than the
     one that worked: the first draft of that check compared the H-grid against
     ONE C-grid edge and stayed green here, and widening it to every warning the
     other four produce — a review finding about the check's WORDING, not about
     this injection — is what made it bite. **An earlier draft of this paragraph
     said the criterion was unsatisfiable.** It is not: read as the floor's VALUE
     it reaches the C-grid and, through that relation, the H-grid; read as the
     `heightLost` BAR it reaches all three (B, C, D below). What stays true and
     narrow is that SQUARE AND CAVITY cannot see this constant in either
     direction, and no injection to it will make them.
     Square 0 warnings, cavity 0, hgrid 7 — counts unchanged, as the table above
     says. ELEVEN checks are added by this ticket (ten in group 13 — six on the
     H-grid, one enumerating the five configs, one on the three exit codes, and
     one loop body printing twice — plus the C-grid baseline check in group 12;
     94 checks before, 105 after, counted by running both). The criterion was written from its own shape; the table above,
     dated the day before the ticket, already said only the C-grid's two edges
     move. So the three are scored against the injections that DO reach them:
  B. the floor raised absurdly to 1e-3. Exit 1, EIGHT checks red where the same
     injection bit THREE before this work — four of the SEVEN H-grid checks go with
     it (its seven warnings, the eighth's silence, the two-order margin and the
     upper-bound relation). The H-grid is therefore non-vacuous against a floor
     raised too far, which is the direction the blind spots call the wide one.
     THE THREE THAT STAY GREEN ARE NAMED because one of them is green for a bad
     reason: "eight edges measured" is still true (the targets exist, they simply
     stop warning) and so is the exit code, but "none shows a before and an after
     identical to every digit" is VACUOUS on an empty warning set — the same vacuity #107's own
     review found in the margin check, surviving here in the half that cannot be
     repaired by a presence clause, because the claim IS about survivors.
     **AND IT CRASHED THE FIRST DRAFT OF GROUP 13 rather than failing it**: with
     every warning silenced, `max(v[0] for v in w_hg.values())` raised on the empty
     set, the run stopped there and the square and cavity checks never executed —
     read off the output it looked like a bite of five. Both readings now fall back
     to a number (`default=0.0`, and `-inf` for the log) so every check can be
     scored. Re-run after the fix: 8 red, not 5.
  C. the comparison's own direction, `> was * 1.01 + floor` becoming
     `>= was * 1.01 - floor` — a guard that warns about a wall the sweeps did not
     make worse, which IS #107's symptom reached by the other route. Exit 1, FIVE
     red: the C-grid's two, the H-grid's bound relation, and the SQUARE and CAVITY
     pair. Those two are the only
     shipped cases where that flip invents a warning, because they are the only
     ones whose every wall has `now` exactly equal to `was` — the H-grid stays
     green under it, since `v00` improved by more than the 1% slack.
     (Deleting the guard outright is not the injection: `-Werror` rejects the build
     for an unused `kHeightNoiseFloor`, so the floor is kept and neutralised.)
  D. THE BAR REWRITTEN AS AN ABSOLUTE TOLERANCE ON THE DECLARATION, `> 1e-4`
     instead of `> was * 1.01 + floor` — the change the blind spots say nothing
     used to catch. Exit 1, SEVEN red, and the two that matter are the airfoil
     pair's silence on the C-grid and `v00`'s on the H-grid: both are walls that
     go IN off their declaration and come out closer to it, so a bar that forgot
     the baseline warns about the very walls the control functions rescued. That
     check did not exist when this injection was first run; writing it is what
     this injection bought.
  ALL FOUR RE-RUN AFTER EVERY REPAIR, twice over, because each round of review
  changed a check and a changed check has to face the injections again: A 3 red,
  B 8, C 5, D 7. The first round, before the review's fixes, read A 2, B 8, C 4,
  D 7 — A and C moved because the bound check was widened. Restored and rebuilt:
  ALL PASS, 105 checks, ctest 7/7.

WHAT THE REVIEW OF THIS WORK CHANGED, since two of its findings were in figures
this docstring states: **"six orders" was 2.6.** The floor is 2.6 orders above the
2.334e-12 that fired and 4.0 below `e_ff_up`'s 9.499e-6; six is the distance to the
~1e-15 PRE-SMOOTHING residual, a different quantity, and #107's own text made that
substitution — carried in here from the ticket and corrected in all four places
that stated it. And the margin check **claimed five orders while asserting two**,
the shape #95 recorded: it now asserts two, says two, and DERIVES the measured
margin from the same reading rather than printing a number typed beside it.

MEASURED 2026-09-07 by this file's own runs, #84's FREED SHARED EDGES beside #83's
frozen ones (re-measured the same day, from the commit before this one), #82's
plain Winslow and #81's Laplacian (both quoted from their tickets):

  shipped C-grid, 11520 cells, unsmoothed 0 inverted / 32.044 deg max /
  4.562 deg mean / 0.4368% wall:

    cap    kernel              inverted  max      mean    wall      clipped
    1      Laplacian (#81)            0  89.399   6.230   36.61%      --
    1      Winslow   (#82)            0  31.438   4.778   11.65%      --
    1      +control  (#83)            0  31.861   4.527    0.1222%    36
    1      +seams    (#84)            0  31.861   4.516    0.1222%    40
    5      Laplacian (#81)            4  89.786  10.004  126.45%      --
    5      Winslow   (#82)            0  29.844   5.627   39.15%      --
    5      +control  (#83)            0  31.382   4.454    0.0805%     8
    5      +seams    (#84)            0  31.382   4.340    0.0846%     8
    20     Laplacian (#81)           26  89.864  16.288  372.84%      --
    20     Winslow   (#82)            0  33.759   8.517  130.77%      --
    20     +control  (#83)            0  29.895   4.301    0.0893%     0
    20     +seams    (#84)            0  29.895   3.821    0.0968%     0
    40     +control  (#83)            0  34.784   4.214    0.0980%     0
    40     +seams    (#84)            0  28.551   3.388    0.1111%     0
    100    +control  (#83)            4  86.606   4.710   19.06%       4
    100    +seams    (#84)            0  26.493   3.381    0.1289%     0
    150    +seams    (#84)            0  28.890   4.316    0.1338%     0
    300    +seams    (#84)            0  47.765   8.218    0.1555%     0
    400    +seams    (#84)          184  80.872  10.854   27.37%     156
    500    +control  (#83)          288  84.927  10.860   99.99%     212
    500    +seams    (#84)          620  89.900  13.087   37.38%     428
    20000  +seams    (#84)         2262  89.944  17.854   99.99%     942
           (#84 DIVERGES at 1111 and returns that iterate; #83's residual
            plateaued there instead and #82's diverged at ~4900)

  THE ANGLE NO LONGER TURNS AT THIRTY, which is the clearest single reading of what
  this ticket bought: #83's max went 29.90 -> 31.55 -> 34.78 over caps 20, 30, 40
  because the interior was shearing against a frozen seam. #84's falls monotonically
  to 26.49 at a cap of 100 and turns only past 150.

  shipped O-grid, 9216 cells, unsmoothed 0 inverted / 2.250 / 1.875 / 0.0812%.
  THIS WHOLE TABLE IS ON THE 80-FACET FAR FIELD and is left as the dated record it
  is; the shipped far field is 320 facets since #95, on which every `max` column
  below reads 2.025 at every cap and the smoother's excess is exactly zero. What
  the table still measures is the four KERNELS against each other on one geometry,
  which is what it was written for:

    1      Laplacian (#81)            0   4.344   1.882   53.36%      --
    1      Winslow   (#82)            0   3.312   1.875    9.13%      --
    1      +control  (#83)            0   3.632   1.875    0.0390%     0
    1      +seams    (#84)            0   2.276   1.875    0.0390%     0
    5      Laplacian (#81)          184  17.443   2.111   87.36%      --
    5      Winslow   (#82)            0   8.061   1.978   29.13%      --
    5      +control  (#83)            0   6.418   1.980    0.0412%     0
    5      +seams    (#84)            0   2.276   1.875    0.0412%     0
    20     +control  (#83)            0  12.036   2.571    0.0442%     0
    20     +seams    (#84)            0   2.276   1.875    0.0442%     0
    40     +seams    (#84)            0   2.276   1.875    0.0475%     0
    150    +seams    (#84)            0   2.274   1.875    0.0566%     0
    300    +seams    (#84)          192   2.274   1.875    0.0598%   200

  THE MEAN OF EXACTLY 1.875 IS STRUCTURAL, not a coincidence and not a strong
  result: a 96-gon's every quad corner deviates by half the sector angle whatever
  the radial distribution is, so this column measures the faceting and nothing
  else. (It said "48-gon" until #95, whose review found the third copy of a slip
  #93 had already corrected in the design note. 360/48/2 is 3.75, not 1.875 — the
  arithmetic never produced the number the sentence explains; the ring is 96 nodes,
  4704 vertices over 49 radial stations.) What it DOES say is that the grid is polar again — #83's 2.571 at a cap of
  20 was the interior pulled off the polar structure by the frozen radials.

  the mid-block radial band of the shipped O-grid — the 48 interface nodes with
  2 < r < 8 and the 416 cell corners touching them, indexed on the unsmoothed mesh
  because a freed interface MOVES:

    cap 0    max 2.2477   mean 1.8752
    cap 1    max 1.9475   mean 1.8755
    cap 20   max 1.8794   mean 1.8757

  the near-leading-edge region of the shipped C-grid — the ten quad cells touching
  the airfoil between x = 0.005 and 0.030, which is where #57 localised the corner
  that drove the solver to NaN, at (0.0134, 0.0196):

    cap 0   max 32.044 deg   mean 26.895 deg
    cap 1   max 31.861       mean 26.734
    cap 5   max 31.382       mean 26.308
    cap 20  max 29.895       mean 24.915

  the wake cut of the shipped C-grid, over the 192 corners of the 48 cells touching
  it, at a cap of 20:

    unsmoothed   max 0.0000 deg   mean 0.0000 deg
    smoothed     max 0.6173       mean 0.0178

#80'S ACCEPTANCE IS MET ON THE C-GRID AND STILL NOT ON THE O-GRID, and both are
asserted rather than summarised:

  * C-grid: max, mean AND wall all better than #57's baseline at the same time,
    inverted still 0, and the near-LE region improving on its own figures rather
    than only through the mesh-wide maximum. Group 10.
  * O-grid: the wall first cell is BETTER than #55's 0.0812% (0.0390%) and max
    non-orthogonality is still WORSE (2.250 -> 2.276). Recorded as unmet — but the
    gap is 1.2% and no longer grows with the cap, so #83's "no single cap meets
    both of #80's bullets" is GONE. The residue is the FACETED OUTER WALL's rather
    than the interface's: the unsmoothed mesh's own worst corner is 2.250 ON that
    wall and the smoothed one's is 2.276 one grid line in from it. Groups 8 and 9.
    CORRECTED by #93 (2026-09-08): what that wall is faceted BY is a polyline
    coarser than the mesh reading it — 80 facets under 96 nodes — so the cause is
    the sampling ratio and NOT #83's frozen wall, whose decision this leaves
    untouched.
    AND MET BY #95 (2026-09-08), which stored that far field at 320 facets instead
    of 80. The shipped case now reads 2.024972 unsmoothed AND 2.024972 at every cap
    measured, so the smoother's excess is not 1.2% but exactly zero, and all three
    of #80's figures are met — the worst angle and the wall with margin, the mean
    exactly and structurally. The paragraph above is kept because it is what those
    figures were, and because the two facts it got right survive: the residue was
    the faceted wall's, and it was never the kernel's. Groups 8 and 9 assert the
    met form; the bars are the quality gate's.

WHAT #84's OWN CRITERION ASKED FOR AND THIS FILE COULD NOT DELIVER, said plainly:
the ticket asks that the wake cut's "own cells improve rather than staying at their
unsmoothed values". They cannot. The wake is a straight line on the symmetry axis
and the algebraic fill already leaves all 48 cells against it EXACTLY orthogonal,
so the criterion's premise — that the wake was one of the worst lines — is false on
this geometry. The worst lines were the RADIAL interfaces, and those improve (group
9). Group 11 measures the wake on the terms that are true: one line both blocks
read, no boundary face, its 23 interior nodes moving, staying on the axis to 1.4e-18 (the check's
own bar is 1e-15), and a cost of 0.0178 deg mean where the mesh-wide mean gains 0.74.

BLIND SPOTS, named rather than papered over:

  * Nothing here runs the solver or the grid converter on a smoothed mesh. That is
    #80's own acceptance rather than this ticket's, and the unsmoothed C-grid's
    dated run is in test_multiblock_cgrid_surface.py. A smoothed mesh would now be
    a reasonable thing to hand a viscous solver — 0.10% off the requested wall
    height at twenty sweeps — so this is a gap rather than a non-question, and it
    belongs to #85.
  * The figures in the tables above are a record of one dated run, not something
    this file re-measures. What it asserts is the DIRECTION and a floor, so a
    kernel that quietly stopped moving anything would be caught while a kernel
    that moves things differently is free to.
  * NOTHING MEASURES THE FREED INTERFACES ON THE C-GRID's OWN TERMS. Group 9's
    band selection is polar and works because the O-grid's radials lie at four
    known angles; the C-grid's three radials and its wake have no such handle from
    outside, so what is read there is the wake (group 11) and the whole-mesh
    figures. The C++ test reaches those lines by node id and pins the mechanism,
    not the quality.
  * A FOLD FROM SMOOTHING IS STILL REACHABLE ON THESE FILES, at a cap of 400 on
    the C-grid and 300 on the O-grid rather than #83's 100 and (unmeasured). Group
    7 asserts exit 9 on the real file. THE O-GRID's FOLD IS INVISIBLE TO
    NON-ORTHOGONALITY, which is worth recording as a limit of the ruler rather
    than of this ticket: at a cap of 300 it folds 192 cells while max
    non-orthogonality reads 2.274 deg, because two adjacent radial lines have
    swapped order and the folded cells are still very nearly rectangular. The
    inverted-cell count is what sees it.
  * NO SYNTHETIC FIXTURE REACHES THE SATURATING-AND-DESCENDING regime that the
    stability limit lives in; the shipped C-grid at a cap of 400 is the only case
    that does, which is why that check is here and not next door.
  * THE WALL WARNING'S NOISE FLOOR IS CALIBRATED, SO IT CAN GO STALE. 1e-9 is
    2.6 orders above the deviation the shipped C-grid's 5920 nodes produced and
    3.8 orders below the smallest deviation anyone would act on — the H-grid's
    `v21`, since #114; 4.0 is the distance to the C-grid's `e_ff` pair, which is
    the figure this bullet carried before that — but it is a
    fixed number and
    nothing re-derives it from the mesh it is applied to. A mesh an order denser
    has a higher noise floor, and the first symptom would be the same false
    warning on a case nobody has run yet. Groups 12 and 13 pin BOTH ends on the
    five shipped configs — they cannot speak for a mesh that is not in the tree.
  * AND THE UPPER END IS PINNED AT 5.90e-6, NOT AT 1e-9. What catches a floor set
    too HIGH is a real warning going silent, so the whole band between the chosen
    1e-9 and the lowest real warning in the tree — 3.77 orders — is a raise nothing
    here would notice. #114 narrowed that figure from the C-grid `e_ff` pair's
    9.499e-6 to the H-grid `v21`'s 5.90e-6, a factor of 1.6 and 0.2 of an order:
    real, and small. The gross-end control does not narrow it at all: `af_up`'s
    27.37% survives any floor under 0.269. Named because injection B's first
    write-up read as though the gross-end control bounded the constant, and it
    does not.
  * ALL FIVE SHIPPED CONFIGS CARRY THE CRITERION NOW, AND WHICH OF THEM SEES THE
    FLOOR DEPENDS ON THE DIRECTION IT MOVES (#114, which replaces "gated on two of
    the five"). Lowered, only the C-grid's WARNINGS change — though that shows up
    in the H-grid's upper-bound check too, since the noise pair returning at
    2.3e-10% makes the H-grid no longer the lowest. RAISED, three of the
    five change — the C-grid, the O-grid and the H-grid. Two cannot see this
    constant in either direction: square and cavity. **This bullet said "three of
    them cannot see the floor at all" and its own list below contradicted it**,
    which is the count-against-its-own-enumeration shape #111 recorded. What each
    one is worth against a change to `kHeightNoiseFloor` was measured, not
    assumed:
      - cgrid: the only case whose warnings MOVE when the floor does. Both ends.
      - ogrid: four warnings at 3.7e-4 relative; catches a floor raised past that.
      - hgrid: seven warnings, the lowest at 5.90e-6, which is the tree's tightest
        upper bound — and an eighth edge that is one of the two places the bar's
        BASELINE is now pinned (see below).
      - square, cavity: NOTHING a floor at or above zero can reach. Both are
        rectangles the solve leaves as it found them (cavity bit for bit), so every
        wall has `now` exactly equal to `was` and the comparison is false for any
        floor. They gate the COMPARISON instead — injection C, a `>` flipped to a
        `>=`, reddens exactly this pair and nothing else new.
    So a floor moved DOWN is still seen by one config only, and widening the gate
    did not change that. What widening bought is the H-grid's tighter upper bound,
    the baseline checks below, and two cases that see the other guard.
  * THE BAR'S BASELINE WAS NOT ASSERTED AT ALL UNTIL #114, and looking for it is
    what found that. "Worse than the mesh the solve started from" is the whole
    sentence, and it has two instances in the tree: the C-grid's `af_up`/`af_lo`
    go in 0.44% off the declared height and come out at 0.05%, and the H-grid's
    `v00` goes in at 0.15% (a declared geometric spacing the algebraic fill cannot
    land on exactly) and comes out at 0.08%. Both are their mesh's worst-held wall
    and both are correctly silent; neither was named by any check before this
    ticket, so a bar rewritten as an absolute tolerance on the DECLARATION would
    have passed the whole gate. Both are asserted now — the C-grid's in group 12,
    the H-grid's in group 13 — and injection D is the evidence (7 red). **THIS
    BULLET CLAIMED `v00` WAS THE ONLY SUCH WALL**, which is what the ticket's own
    framing suggested and what measuring the C-grid's banner disproved. The
    O-grid's `o*` edges are the near miss: their `was` is a real 3.6e-5 rather
    than a rounding, but the sweeps make them WORSE, so they warn.
  * The banner is checked for its headings and the numbers are read out of the
    machine-readable lines, exactly as the quality gate next door does it: the two
    are built from one report object, and the C++ test pins the report. The
    exceptions are groups 9, 10 and 11's own quad reader, and group 10 validates it
    against the C++ ruler's whole-mesh line before it is trusted anywhere the
    ruler does not look.

Run:  python3 tools/PreProcessor/tests/test_multiblock_smooth_surface.py
Skips cleanly if ./build/HybMesh2D has not been built.

COST, measured 2026-09-11 on this machine: **the attributable figure is 0.71 s**,
the three mesher runs group 13 adds, timed on their own (square 0.42, cavity 0.20,
hgrid 0.09). The whole-run wall clock is NOT evidence here and is deliberately not
quoted as a before/after: across measurements either side of the change it ranged
8.6-11.2 s, and a review run of the CHANGED file came back at 9.73 s — inside the
range an earlier draft of this paragraph had given as the "after". The spread is
wider than the addition, so only the 0.71 s is stated.

THE `run_all.sh` RANKING THAT STOOD HERE IS DELETED, NOT CORRECTED (#116). Three
homes called this the FOURTH-slowest file in `run_all.sh` and named three files with
absolute timings behind it; the ranking was wrong a second time and the absolutes
re-timed 1.5x to 3.5x under what they said. Re-deriving either means timing every
test file in the suite, which is why nobody does and why both readings decayed
unseen, and by
`docs/agents/rule-file-style.md` rule 6 — keep a measurement that CONSTRAINS a
decision, drop one that only justifies it — it decided nothing. What did decide the
widening survives: this file makes 20-odd mesher invocations, the C-grid at a cap of
20000 among them, so a C-grid or O-grid run costs ~1 s here and the three cheapest
configs in the repo were the affordable way to widen it. The rationale, and why the
true rank is not stated in its place, is in `docs/design_notes/mesher.md`.
"""
import glob
import math
import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
sys.path.insert(0, _HERE)
# Imported, not copied: each shipped config is retargeted by the gate that owns
# it, which also fails loudly if the file stops containing what it rewrites.
from test_multiblock_cgrid_surface import base_config  # noqa: E402
from test_multiblock_ogrid_surface import base_config as ogrid_config  # noqa: E402
# The ONE parser for the machine-readable quality line, in the gate that owns it.
# The token is matched WITH its trailing space, which is what keeps the unsuffixed
# line and the `_BEFORE` one apart — the whole reason the before line wears a
# suffix rather than an extra field on the existing one.
from test_multiblock_quality_surface import qlines  # noqa: E402
# #53's CONFORMITY MEASURE, imported and not re-invented: #84's acceptance names it
# as the property to reuse. `edge_use` counts how many cells each undirected cell
# edge belongs to, `components` counts connected components by SHARED NODE IDENTITY,
# and the three readers give the STAR-CD files the grid converter actually consumes.
from test_multiblock_weld_surface import (  # noqa: E402
    bnd_faces, cel_cells, components, edge_use, vrt_nodes)
from mesher_bin import NO_SMOOTH, mesher_env as _mesher_env  # noqa: E402

# "UNSMOOTHED" IS NO LONGER THE DEFAULT, and since #85 every run that means it has
# to say so. `MB_SMOOTH_ITERS` ships at 20, so a bare run is a SMOOTHED run — the
# five places below that need the algebraic fill's own mesh (group 1's silence, the
# O-grid's and the C-grid's before-figures, and group 11's control) pass
# `NO_SMOOTH` explicitly. It is imported rather than spelled here: `mesher_bin`
# owns the one spelling, because this file called it `OFF` while the gate next door
# called it `NO_SMOOTH` and three more used a raw literal. What the DEFAULT produces
# is gated in test_multiblock_quality_gate.py.

# The #81 LAPLACIAN figures, quoted from that ticket rather than re-measured: the
# kernel is deleted, so there is nothing left to measure them on. Keyed by
# (case, cap) -> (inverted, nonortho max, nonortho mean, wall first cell fraction).
LAPLACIAN_2026_09_04 = {
    ("cgrid", 1):  (0, 89.399, 6.230, 0.3661),
    ("cgrid", 5):  (4, 89.786, 10.004, 1.2645),
    ("cgrid", 20): (26, 89.864, 16.288, 3.7284),
    ("ogrid", 1):  (0, 4.344, 1.882, 0.5336),
    ("ogrid", 5):  (184, 17.443, 2.111, 0.8736),
}

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(tmp, name, extra="", config=None):
    stem = os.path.join(tmp, name)
    conf = os.path.join(tmp, name + ".dat")
    text = (config or base_config)()
    with open(conf, "w", encoding="utf-8") as f:
        f.write(text.replace("@STEM@", stem) + extra)
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=900)
    return p.returncode, (p.stdout or "") + (p.stderr or ""), stem


# ── The three shipped configs no other gate drives (#114) ────────────────────
#
# The C-grid and the O-grid arrive above through `base_config`, each imported
# from the gate that owns it. `multiblock_square`, `multiblock_cavity` and
# `multiblock_hgrid` have no such gate: nothing else in the tree RUNS them, so
# there is no owner to import from and this is where they enter.
#
# RETARGETED BY KEY, NOT BY A LIST OF NEEDLES, which is the one deliberate
# difference from `base_config`. That list is honest there because the gate that
# holds it reads the same file for a dozen other claims, so a path it stopped
# naming would be noticed. Here the only reader is this block, and a needle list
# it owned alone would rot into a run that quietly wrote into the repo's own
# `results/` while this file, seeing a mesh, reported PASS.
#
# A KEY LIST IS STILL A LIST, AND THE SWEEP BELOW IS WHAT MAKES THE PARAGRAPH
# ABOVE TRUE. `_MB_PATH_KEYS` is as capable of going stale as a needle list: a
# path added to one of these configs under a key NOT in it would be left relative
# and the run would write into the repo. So after the rewrite every remaining
# value is checked for resolving to a file in this checkout, and one that does is
# a KEY THIS FUNCTION DOES NOT KNOW — raised by name, never retargeted silently.
# That, not the keying, is the part a reviewer should trust; the review of #114
# is what asked for it, having read the paragraph above as a guarantee.
#
# ALL FOUR GUARDS PROBED BY HAND, 2026-09-11, each by mutating the shipped square
# config and reading the raise: an unknown key carrying a resolving path
# (`BC_GEOM_FILE`), a missing `OUTPUT_FILENAME`, `MESH_MODE` no longer 1, and a
# known path key whose value stopped resolving. All four fired and named the file,
# the key and the value; the config was restored and `git diff` came back clean.
# They are not gate checks — a check that edits a shipped config under the gate
# that reads it is a hazard this repo does not ship — so the probe is the record.
#
# AND THIS IS A THIRD "READ THE SHIPPED `.dat`, RETARGET, FAIL LOUDLY", named
# because the two it sits beside are imported under a comment that says "Imported,
# not copied". The key-driven form here could subsume both `base_config`s and
# leave one implementation — `qlines`'s own note next door records what four
# copies of a parser cost when #81 had to make the identical one-character fix in
# two of them. It is NOT done here: those two functions are owned by the gates
# that hold them, each does something extra (the C-grid's `bc_geom` override, the
# O-grid's topology argument), and collapsing three into one across three files is
# a refactor rather than #114. Recorded as the residue it is.
_MB_PATH_KEYS = ("MESH_TOPOLOGY_FILE", "GEOM_FILE", "DOMAIN_FILE")


def shipped_config(name):
    """``config/<name>.dat``, retargeted at ``@STEM@`` and at this checkout.

    Read from disk for the reason the C-grid's own `base_config` gives: these
    files are documentation a user runs, and a test that composed an equivalent
    one would leave an edit to the shipped file invisible from here.
    """
    path = os.path.join(_REPO, "config", name + ".dat")
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    out_, hit = [], {"MESH_MODE": False, "OUTPUT_FILENAME": False}
    for ln in lines:
        key = ln.split()[0] if ln.split() else ""
        val = ln[len(key):].strip()
        if key in _MB_PATH_KEYS:
            rel = os.path.join(_REPO, val)
            if not os.path.exists(rel):
                raise AssertionError(
                    "%s: %s %r does not resolve under %s, so this test cannot "
                    "retarget it. Update shipped_config()." % (path, key, val, _REPO))
            ln = key + " " + rel
        elif key == "OUTPUT_FILENAME":
            hit[key] = True
            ln = key + " @STEM@.vtk"
        elif key == "MESH_MODE":
            hit[key] = (val == "1")
        elif key and not key.startswith("#") and val and os.path.isfile(
                os.path.join(_REPO, val)):
            # A PATH UNDER A KEY THIS FUNCTION DOES NOT KNOW. Left alone it would
            # stay repo-relative, the mesher would read the repo's own file and,
            # for an output, write into the repo's `results/`. Caught by what the
            # value IS rather than by what the key is called, so the list above
            # cannot go stale in silence.
            raise AssertionError(
                "%s: %s %r resolves to a file in this checkout but %s is not in "
                "_MB_PATH_KEYS, so the run would read (or write) the repo's own "
                "tree. Add it there." % (path, key, val, key))
        out_.append(ln)
    if not hit["MESH_MODE"]:
        raise AssertionError(
            "%s is no longer a MESH_MODE 1 config, so this test cannot drive it "
            "as one. Update shipped_config()." % path)
    if not hit["OUTPUT_FILENAME"]:
        raise AssertionError(
            "%s no longer declares OUTPUT_FILENAME, so this test cannot retarget "
            "its output away from the repo. Update shipped_config()." % path)
    return "\n".join(out_) + "\n"


_WALL_BANNER = re.compile(
    r"^\s+\w+ '([^']+)'\s+: asked .* got .* \(([-\d.]+)%\)\s*$")


def wall_banner(out, before=False):
    """One quality banner's per-edge wall lines: edge id -> deviation in %.

    THE READER OF LAST RESORT, for the one thing the machine-readable line cannot
    answer: `wall_first_cell_worst_rel` carries only the WORST edge, so counting
    how many edges were MEASURED at all needs the per-edge lines.

    TWO DECIMAL PLACES IS ALL IT PRINTS, AND NO ASSERT MAY COMPARE MAGNITUDES OFF
    IT. #114's first draft did — `v00`'s rounded 0.08 against another edge's
    6-digit 0.075166, where the rounding interval straddles the competitor — so
    what survives is COUNTING edges and printing the reader-facing figure in a
    message. Every threshold and every ordering in groups 12 and 13 is read from
    the warning text or from `qlines` instead.

    `before` picks the pre-smoothing banner. The two are told apart by the
    machine-readable line that TERMINATES each, not by the heading above it: the
    heading carries a sweep count and the terminator does not, so a run at a
    different cap parses the same way.
    """
    sections, cur = {}, []
    for ln in out.splitlines():
        if ln.startswith("HYBMESH_MB_QUALITY_BEFORE "):
            sections["before"], cur = cur, []
        elif ln.startswith("HYBMESH_MB_QUALITY "):
            sections["after"], cur = cur, []
        else:
            cur.append(ln)
    got = sections.get("before" if before else "after")
    if got is None:
        return {}
    return {m.group(1): float(m.group(2))
            for m in (_WALL_BANNER.match(l) for l in got) if m}


def wrote(stem):
    return [e for e in (".vtk", ".vrt", ".cel", ".bnd")
            if os.path.exists(stem + e)]


def smooth_line(out):
    """The one HYBMESH_MB_SMOOTH line, as a dict, or {} when no sweep ran.

    Parsed here rather than beside `qlines` because it is a different line with a
    different owner: `qlines` reports the MESH and this reports the SOLVE, and a
    run can have the first without the second.
    """
    hit = [l for l in out.splitlines() if l.startswith("HYBMESH_MB_SMOOTH ")]
    if len(hit) != 1:
        return {}
    out_ = {}
    for tok in hit[0].split()[1:]:
        k, _, v = tok.partition("=")
        out_[k] = float(v) if ("." in v or "e" in v) else int(v)
    return out_


_WALL_HEIGHT_WARN = re.compile(
    r"wall edge '([^']+)' \([^)]*\): the control function could not hold "
    r"the first cell height the declaration asks for "
    r"\(worst ([-\d.eE+]+)% off it, against ([-\d.eE+]+)% before the sweeps\)")


def wall_height_warns(out):
    """The HEIGHT half of every wall-control warning: edge id -> (now, was), in %.

    THE HALF IS NAMED IN THE PATTERN and not filtered for afterwards, because the
    message is one sentence with two optional halves — a wall can be warned about
    for its 90 degrees alone, and such a line carries no height figures to read.
    Matching the height clause is what keeps "no height warning" and "no warning"
    apart, which is exactly the distinction group 12 turns on.

    THE FIGURES COME BACK AS THE MESSAGE PRINTS THEM, not re-measured: what #107 is
    about is what a reader is shown, and a check that re-derived the deviation from
    the mesh could pass while the sentence beside it stayed nonsense.
    """
    return {m.group(1): (float(m.group(2)), float(m.group(3)))
            for m in (_WALL_HEIGHT_WARN.search(l) for l in out.splitlines())
            if m}


def quad_corners(vtk_path):
    """Every corner-angle deviation from 90 degrees in a legacy-VTK QUAD mesh.

    THE METRIC IS THE RULER'S, not a new one. `MbQuality` measures
    non-orthogonality as the deviation of a STRUCTURED cell's corner angle from
    90 degrees, and with ``MB_SPLIT_QUADS 0`` the exported cells ARE those cells,
    so this computes the same quantity over the same corners. What it adds is a
    SELECTION — which corners to report — and #80's "no new metric is invented"
    rule is about the metric, not about the filter.

    It lives out here rather than in `MbQuality` because the question it answers
    is about a shipped FILE: "the first cell off the wall around x = 0.017 on the
    NACA 0012". `measureMbQuality` is a pure function of any `MbResult` and has no
    business knowing an airfoil's leading edge. What keeps this from becoming a
    second answer to the same question is that group 10 first checks the
    WHOLE-MESH figures out of this reader against the C++ ruler's own line: an
    instrument that agrees with the ruler everywhere can be trusted where the
    ruler does not look.
    """
    lines = open(vtk_path, encoding="utf-8").read().split("\n")
    i, pts, cells = 0, [], []
    while i < len(lines):
        if lines[i].startswith("POINTS"):
            n = int(lines[i].split()[1])
            i += 1
            vals = []
            while len(vals) < 3 * n:
                vals += lines[i].split()
                i += 1
            pts = [(float(vals[3 * k]), float(vals[3 * k + 1])) for k in range(n)]
            continue
        if lines[i].startswith("CELLS"):
            n = int(lines[i].split()[1])
            i += 1
            for _ in range(n):
                cells.append([int(x) for x in lines[i].split()][1:])
                i += 1
            break
        i += 1
    return pts, [c for c in cells if len(c) == 4]


def devs_of(pts, cells, keep=None):
    """The deviations of the corners of `cells`, optionally only cells touching `keep`."""
    out = []
    for c in cells:
        if keep is not None and not (set(c) & keep):
            continue
        for a in range(4):
            p, q, r = pts[c[a]], pts[c[(a + 1) % 4]], pts[c[(a - 1) % 4]]
            u = (q[0] - p[0], q[1] - p[1])
            v = (r[0] - p[0], r[1] - p[1])
            lu = math.hypot(*u)
            lv = math.hypot(*v)
            if lu == 0 or lv == 0:
                continue
            cs = max(-1.0, min(1.0, (u[0] * v[0] + u[1] * v[1]) / (lu * lv)))
            out.append(abs(90.0 - math.degrees(math.acos(cs))))
    return out


def on_polyline(pts, poly, tol=1e-9):
    """Which of `pts` lie ON `poly` — a wall node, by distance and not by identity.

    Distance to the SEGMENTS and not to the vertices, because a wall node is
    placed by arc length along the bound polyline and is generally not one of its
    points. Matching vertices instead found 0 of them, which is how this was
    written the first time.
    """
    hit = set()
    for k, p in enumerate(pts):
        best = 1e30
        for a, b in zip(poly, poly[1:]):
            vx, vy = b[0] - a[0], b[1] - a[1]
            l2 = vx * vx + vy * vy
            t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * vx
                                                       + (p[1] - a[1]) * vy) / l2))
            best = min(best, math.hypot(p[0] - (a[0] + t * vx), p[1] - (a[1] + t * vy)))
            if best < tol:
                break
        if best < tol:
            hit.add(k)
    return hit


def read_poly(path):
    poly = []
    for ln in open(path, encoding="utf-8"):
        f = ln.split()
        if len(f) >= 2:
            try:
                poly.append((float(f[0]), float(f[1])))
            except ValueError:
                pass
    return poly


def beats_laplacian(case, cap, a):
    """Every column of `a` at least as good as #81's Laplacian on the same run."""
    inv, mx, mean, wall = LAPLACIAN_2026_09_04[(case, cap)]
    return (a["inverted"] <= inv and a["nonortho_max_deg"] < mx
            and a["nonortho_mean_deg"] < mean
            and a["wall_first_cell_worst_rel"] < wall)


def main() -> int:
    if not os.path.exists(_BIN):
        print("SKIP: build/HybMesh2D not found (run ./build.sh first)")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        # ── 1. ZERO SWEEPS is silence, and the DEFAULT is not zero ──────────
        #
        # #81 wrote this group as "the default is silence" and #85 took that half
        # away: the shipped default is 20 sweeps, so what still has to hold is the
        # narrower and more useful claim — a run that asks for NO smoothing gets
        # byte for byte the report this path printed before the parameter existed.
        # The second half is new and is the other direction: the default really
        # does smooth, so this group cannot pass on a build where the flip was lost.
        rc0, out0, _ = run(tmp, "plain", NO_SMOOTH)
        check("1. the shipped C-grid meshes at MB_SMOOTH_ITERS 0 (rc=0)", rc0 == 0)
        check("1. ...printing exactly ONE machine-readable quality line",
              len(qlines(out0)) == 1)
        check("1. ...and NO before/after pair, because nothing was smoothed",
              "_BEFORE" not in out0)
        check("1. ...nor a line about a solve that never ran", smooth_line(out0) == {})
        check("1. ...under the heading a gate written before this ticket greps for",
              "[ Multi-block Mesh Quality ]" in out0)
        check("1. ...while the run's provenance record still names the parameter, so "
              "'we ran no sweeps' is recorded rather than assumed",
              "Smoothing Sweeps" in out0 and "(none)" in out0)
        base = qlines(out0)[0] if qlines(out0) else {}
        rcd, outd, _ = run(tmp, "dflt")
        sd = smooth_line(outd)
        check(f"1. ...while the DEFAULT is 20 sweeps and not 0 (#85), so none of "
              f"the above is a property of a bare run any more (rc={rcd}, "
              f"cap={sd.get('cap')})",
              rcd == 0 and sd.get("cap") == 20 and "_BEFORE" in outd)

        # ── 2/3/4. one sweep: the pair, and what it cost ────────────────────
        rc1, out1, stem1 = run(tmp, "smooth1", "\nMB_SMOOTH_ITERS 1\n")
        check("2. the same case with one sweep meshes (rc=0)", rc1 == 0)
        before, after = qlines(out1, "_BEFORE"), qlines(out1)
        check("2. ...reporting the mesh BEFORE smoothing", len(before) == 1)
        check("2. ...and the mesh AFTER it", len(after) == 1)
        check("2. ...as two banners a reader can tell apart",
              "[ Multi-block Mesh Quality — before smoothing ]" in out1
              and "— after 1 Winslow sweep(s) ]" in out1)
        check("2. ...and the BEFORE figures ARE the default run's, number for "
              "number — so the pair is one mesh measured twice, not two runs that "
              f"happen to agree ({before[0] if before else None})",
              bool(before) and before[0] == base)
        if before and after:
            b, a = before[0], after[0]
            check("3. the UNSUFFIXED line describes the mesh AS EXPORTED, so it is "
                  "the one that moved", a != b)
            check(f"3. ...over the same cells ({a.get('cells')})",
                  a.get("cells") == b.get("cells") == 11520)
            check(f"4. THE WALL FIRST CELL IS HELD, and #82's miss is REVERSED — "
                  f"its own text called the control functions ticket 3's job "
                  f"({100 * b['wall_first_cell_worst_rel']:.2f}%"
                  f" -> {100 * a['wall_first_cell_worst_rel']:.2f}%)",
                  a["wall_first_cell_worst_rel"] < b["wall_first_cell_worst_rel"])
            check(f"4. ...while MAX NON-ORTHOGONALITY, the metric #80 exists for, "
                  f"still comes out BELOW the unsmoothed fill's "
                  f"({b['nonortho_max_deg']:.3f} deg -> {a['nonortho_max_deg']:.3f} deg)",
                  a["nonortho_max_deg"] < b["nonortho_max_deg"])
            check(f"4. ...and so does the MEAN, which #82 recorded as the one figure "
                  f"that got worse "
                  f"({b['nonortho_mean_deg']:.3f} -> {a['nonortho_mean_deg']:.3f})",
                  a["nonortho_mean_deg"] < b["nonortho_mean_deg"])
            check("4. ...while one sweep folds NOTHING", a["inverted"] == 0)
        check(f"4. ...and the mesh is exported ({wrote(stem1)})",
              wrote(stem1) == [".vtk", ".vrt", ".cel", ".bnd"])
        check("4. ...with the sweep count in the run's provenance record, naming the "
              "kernel and saying the number is a CAP",
              "Smoothing Sweeps     : 1" in out1 and "Winslow elliptic" in out1)

        # ── 5. every column beats the kernel #81 shipped ────────────────────
        for cap in (1, 5, 20):
            rcw, outw, stemw = run(tmp, "c%d" % cap, "\nMB_SMOOTH_ITERS %d\n" % cap)
            a = qlines(outw)
            lap = LAPLACIAN_2026_09_04[("cgrid", cap)]
            check(f"5. the shipped C-grid at {cap} sweep(s) meshes and exports "
                  f"(rc={rcw})", rcw == 0 and wrote(stemw) == [".vtk", ".vrt",
                                                              ".cel", ".bnd"])
            check(f"5. ...and beats #81's Laplacian on EVERY column at the same cap "
                  f"— Laplacian {lap}, Winslow "
                  f"({a[0]['inverted'] if a else None}, "
                  f"{a[0]['nonortho_max_deg'] if a else None}, "
                  f"{a[0]['nonortho_mean_deg'] if a else None}, "
                  f"{a[0]['wall_first_cell_worst_rel'] if a else None})",
                  bool(a) and beats_laplacian("cgrid", cap, a[0]))
            check(f"5. ...folding NOTHING where that kernel folded {lap[0]} — the "
                  f"reason group 5 no longer asserts exit 9 (got "
                  f"{a[0]['inverted'] if a else None})",
                  bool(a) and a[0]["inverted"] == 0)

        # ── 6. a negative count is refused BY NAME ──────────────────────────
        rcn, outn, stemn = run(tmp, "smoothneg", "\nMB_SMOOTH_ITERS -1\n")
        check(f"6. a negative sweep count is REFUSED, not clamped to 0, got {rcn}",
              rcn != 0)
        check("6. ...naming the key the user has to fix",
              "MB_SMOOTH_ITERS" in outn)
        check(f"6. ...and exporting nothing ({wrote(stemn)})", wrote(stemn) == [])
        check("6. ...as a CONFIG refusal, not a topology one — the .dat is what is "
              "wrong", "HYBMESH_ERROR 2 CONFIG" in outn)

        # ── 7. the solve is bounded, and says which ending it reached ───────
        s1 = smooth_line(out1)
        check(f"7. a solve reports its sweeps, its cap and its residual ({s1})",
              s1.get("sweeps") == 1 and s1.get("cap") == 1
              and s1.get("residual", 0) > 0)
        check("7. ...and a cap of one has NOT converged, in the line and in a "
              "warning naming the key — and the ADVICE is #83's, not #82's: the "
              "declared wall height is held while the cap rises, so the sentence "
              "about a converged solve relaxing to the harmonic map is gone",
              s1.get("converged") == 0 and s1.get("diverged") == 0
              and "MB_SMOOTH_ITERS" in out1
              and "the declared wall height is held" in out1
              and "a CONVERGED solve is not the goal at this kernel" not in out1)
        check("7. ...bounded by STABILITY rather than by the kernel's limit, which "
              "is what replaced that sentence: raise it only while the "
              "inverted-cell count stays 0",
              "inverted-cell count stays 0" in out1)
        check(f"7. ...and it names the BEST iterate beside the exported one, which "
              f"at a small cap is the same sweep ({s1.get('best_sweep')})",
              s1.get("best_sweep") == s1.get("sweeps")
              and s1.get("best_residual") == s1.get("residual"))
        # THE CLIP COUNT IS A DIRECTION, NOT A THRESHOLD, and this file is where
        # that was found. The obvious reading — clipping means trouble — is wrong on
        # this very case: at a cap of one the control is clipped at 36 nodes and the
        # mesh is sound, because the algebraic fill starts far from the wall
        # condition and the count FALLS as the solve catches up (36, 28, 8, 0 over
        # the first ten sweeps, measured 2026-09-07). It is the climb back off zero
        # that goes with the folds. So what is asserted is the DIRECTION and the
        # sentence that tells the reader which way to read it.
        s5 = smooth_line(run(tmp, "c5b", "\nMB_SMOOTH_ITERS 5\n")[1])
        s10 = smooth_line(run(tmp, "c10b", "\nMB_SMOOTH_ITERS 10\n")[1])
        check(f"7. ...and the SATURATION COUNT falls as the solve catches up with "
              f"the wall it was told to hold, from a mesh that is sound at every "
              f"step ({s1.get('clipped')} -> {s5.get('clipped')} -> "
              f"{s10.get('clipped')})",
              s1.get("clipped", -1) > s5.get("clipped", -1) > s10.get("clipped", -1)
              == 0)
        check("7. ...which is why the advice gives it as a direction rather than as "
              "a threshold to clear",
              "a direction rather than a threshold" in out1)
        check("7. ...with the banner saying so in words, not only in the token",
              "[ Multi-block Elliptic Smoothing ]" in out1
              and re.search(r"Converged\s+: NO", out1) is not None)
        # A CAP REACHED PAST THE TURN is a different answer from a cap reached on
        # the way down, and #82's review is the reason it is told apart: the flags
        # alone cannot distinguish them — both are `converged=0 diverged=0`. The
        # cap moved with #84: the C-grid is still descending at 100 and 150 and
        # turns by 300 (best 281), where #83's turned by 30.
        _, outt, _ = run(tmp, "turned", "\nMB_SMOOTH_ITERS 300\n")
        st = smooth_line(outt)
        check(f"7. a cap reached PAST the solve's best iterate is reported as such, "
              f"not as a solve with more to give ({st})",
              st.get("converged") == 0 and st.get("diverged") == 0
              and st.get("best_sweep", 0) < st.get("sweeps", 0)
              and st.get("best_residual", 1) < st.get("residual", 0))
        check("7. ...and the advice turns over with it: the iteration has TURNED, so "
              "raising the cap makes the mesh worse rather than more converged",
              "the iteration has turned" in outt
              and "PAST ITS BEST" in outt)
        check("7. ...while the mesh returned is still the LAST iterate, because N "
              "sweeps has to mean N sweeps outside the diverged path",
              st.get("sweeps") == 300)

        # THE STABILITY LIMIT, and #84 MOVED IT — which is one of the two ways this
        # ticket shows up in this group. The control functions hold the wall and the
        # lagged-coefficient iteration is only conditionally stable, but with the
        # shared edges free the grid has somewhere to go instead of shearing against
        # a frozen seam. Measured 2026-09-07 on this file, against #83's own figures
        # from the same runs:
        #
        #   cap    #83 inverted   #84 inverted
        #   40               0              0
        #   100              4              0
        #   150             --              0
        #   300             --              0
        #   400             --            184
        #   500            288            620
        #
        # So the fold is now reachable at 400 and not at 100, and the run still
        # reports it through the machinery that already exists — the inverted-cell
        # count and exit 9 — which is why the capped warning points at that rather
        # than at a second signal.
        rcok, outok, _ = run(tmp, "stable100", "\nMB_SMOOTH_ITERS 100\n")
        aok = qlines(outok)
        check(f"7. the shipped C-grid at a cap of 100 folds NOTHING and exits 0, "
              f"where #83's kernel folded 4 cells there — freeing the seams moved "
              f"the stability limit out (inverted "
              f"{aok[0]['inverted'] if aok else None}, rc={rcok})",
              bool(aok) and aok[0]["inverted"] == 0 and rcok == 0)
        rcs, outs, _ = run(tmp, "satur", "\nMB_SMOOTH_ITERS 400\n")
        ss = smooth_line(outs)
        aq = qlines(outs)
        check(f"7. ...and at 400 it HAS folded while still descending — the "
              f"stability limit, not a turn ({ss})",
              ss.get("converged") == 0 and ss.get("diverged") == 0)
        check(f"7. ...reported by the machinery that already exists: the inverted "
              f"count and exit 9 (inverted {aq[0]['inverted'] if aq else None}, "
              f"rc={rcs})",
              bool(aq) and aq[0]["inverted"] > 0 and rcs == 9)
        check(f"7. ...with the clip count climbing back off the zero it reached by "
              f"sweep 10, which is the direction the warning tells the reader to "
              f"watch ({s10.get('clipped')} at 10 -> {ss.get('clipped')} at 400)",
              ss.get("clipped", 0) > 0)

        # THE DIVERGED ENDING IS BACK ON A SHIPPED FILE, which is the other way #84
        # shows up here and is a reversal of #83's own record. Under that kernel
        # neither shipped case reached either of the two non-cap endings — the
        # residual PLATEAUED, at 6.8e-05 on the C-grid at a cap of 50000 — and both
        # endings had moved to fixtures next door (tests/cpp/test_multiblock.cpp
        # check 49, a notched box whose depth picks the ending). With the seams free
        # the C-grid's residual falls further and then GROWS: it diverges at sweep
        # 1111 and the solve hands back that best iterate rather than the last.
        # Measured 2026-09-07. The C++ fixtures stay — they run in milliseconds and
        # cover the CONVERGED ending, which no shipped case reaches.
        _, outd, _ = run(tmp, "diverge", "\nMB_SMOOTH_ITERS 20000\n")
        sd = smooth_line(outd)
        check(f"7. the shipped C-grid DIVERGES at a cap of 20000 and stops early, "
              f"which #83's kernel could not do on this file ({sd})",
              sd.get("diverged") == 1 and sd.get("converged") == 0
              and 0 < sd.get("sweeps", 0) < 20000)
        check("7. ...returning the BEST iterate rather than the last, and saying so",
              sd.get("best_sweep") == sd.get("sweeps")
              and "DIVERGED" in outd
              and "the BEST iterate" in outd)

        # ── 8. the O-grid: #80's negative control, and it IS met ───────────
        rco0, outo0, _ = run(tmp, "o0", NO_SMOOTH, config=ogrid_config)
        rco1, outo1, _ = run(tmp, "o1", "\nMB_SMOOTH_ITERS 1\n", config=ogrid_config)
        bo, ao = qlines(outo1, "_BEFORE"), qlines(outo1)
        check(f"8. the shipped O-grid meshes with and without smoothing "
              f"(rc={rco0}/{rco1})", rco0 == 0 and rco1 == 0)
        # NOT #55's 2.250 SINCE #95: that figure was the 80-facet far field's
        # sampling artefact (#93), and the shipped far field is 320 facets. The
        # unsmoothed mesh reads 2.025, which is the BODY's own 1.667 facets per
        # mesh interval and the residue everything below is measured against.
        # 2.025 IS A SPECIMEN HERE, NOT A BAR. Every threshold with an owner lives
        # in test_multiblock_quality_gate.py; this file's job is the four KERNELS
        # against each other, and the literal it compares against is the geometry's
        # figure on the day — like the 3.632 / 12.036 / 2.276 rows below it.
        check(f"8. ...over 9216 cells, unsmoothed at 2.025 deg — the body's "
              f"sampling residue, #55's 2.250 having been the far field's until "
              f"#95 resolved it ({bo[0]['nonortho_max_deg'] if bo else None})",
              bool(bo) and bo[0]["cells"] == 9216
              and abs(bo[0]["nonortho_max_deg"] - 2.025) < 0.01)
        check(f"8. ...and every column beats #81's Laplacian at the same cap "
              f"(Laplacian {LAPLACIAN_2026_09_04[('ogrid', 1)]})",
              bool(ao) and beats_laplacian("ogrid", 1, ao[0]))
        # #80's NEGATIVE CONTROL: MET AS OF #95, AND BY EXACT EQUALITY. The check
        # below read "STILL NOT MET" for four tickets and said in as many words that
        # when it started passing it should be turned round and #80 told. It is
        # turned round here rather than loosened, and the history it held is kept:
        #
        #   cap    #83 max    #84 max    #95 max    (#55's bar 2.250)
        #   1        3.632      2.276      2.025
        #   5        6.418      2.276      2.025
        #   20      12.036      2.276      2.025
        #   40      16.787      2.276      2.025
        #
        # WHAT CHANGED IS THE GEOMETRY, NOT THE KERNEL. #93 measured the +0.026 to be
        # the SAMPLING RATIO of an 80-facet far field under a 96-node ring rather
        # than the frozen wall it had been attributed to; #95 stored that circle at
        # 320 facets, and the excess went not to something small but to ZERO, at
        # every cap. #83's decision is untouched — wall nodes still do not slide, and
        # group 9's wall-row check still holds it. See docs/design_notes/mesher.md,
        # "THE O-GRID's RESIDUE IS A SAMPLING RATIO, NOT A FROZEN WALL".
        check(f"8. #80's NEGATIVE CONTROL IS MET: a case the fill already leaves at "
              f"{bo[0]['nonortho_max_deg'] if bo else -1:.6f} deg comes out at "
              f"{ao[0]['nonortho_max_deg'] if ao else -1:.6f} — the smoother adds "
              f"EXACTLY nothing, which is what the shipped geometry could not "
              f"demonstrate until #95 resolved its far field",
              bool(ao) and bool(bo)
              and ao[0]["nonortho_max_deg"] == bo[0]["nonortho_max_deg"])
        _, outo20, _ = run(tmp, "o20", "\nMB_SMOOTH_ITERS 20\n", config=ogrid_config)
        ao20, bo20 = qlines(outo20), qlines(outo20, "_BEFORE")
        check(f"8. ...at a cap of TWENTY too, where #83 was at 12.036 deg and #84 at "
              f"2.276 — so the excess does not merely start at zero, it stays there "
              f"as the solve runs ({ao20[0]['nonortho_max_deg'] if ao20 else -1:.6f} "
              f"deg)",
              bool(ao20) and bool(bo20)
              and ao20[0]["nonortho_max_deg"] == bo20[0]["nonortho_max_deg"]
              and ao20[0]["nonortho_mean_deg"] <= 1.876
              and ao20[0]["inverted"] == 0)
        check(f"8. ...and the wall first cell is BETTER than #55's 0.0812%, which "
              f"#83 already delivered and #84 must not give back "
              f"({100 * ao20[0]['wall_first_cell_worst_rel'] if ao20 else -1:.4f}%)",
              bool(ao20) and ao20[0]["wall_first_cell_worst_rel"] < 0.000812)

        # ── 9. WHERE the kink went: the interfaces are no longer it ────────
        #
        # #82 localised this regression through the run's own wall table; #83 held
        # the wall row all the way round, so the table could no longer find it, and
        # measured the corners directly instead: the smoothed O-grid's worst sat at
        # r = 3.43, MID-BLOCK on the four DECLARED RADIAL INTERFACES, while the
        # unsmoothed mesh's worst sat at r = 10 on the faceted outer circle. That
        # was the kink along a frozen shared edge, and #84 is the ticket that
        # unfroze them.
        #
        # WHAT THIS GROUP NOW ASSERTS, in two halves that answer different
        # questions. First, the mid-block radial band's OWN cells, selected on the
        # unsmoothed mesh and read on both — because the freed interfaces bend
        # slightly and a theta filter re-applied to the smoothed mesh silently
        # loses four of the 84 nodes. Measured 2026-09-07 over the 48 radial-
        # interface nodes with 2 < r < 8 and the 416 cell corners touching them:
        #
        #   cap 0    max 2.2477   mean 1.8752
        #   cap 1    max 1.9475   mean 1.8755
        #   cap 20   max 1.8794   mean 1.8757
        #
        # So the cells against a shared edge are now BETTER than the algebraic
        # fill left them, which is #80's user story 3 and #84's own acceptance
        # criterion about a shared edge's own cells improving.
        #
        # Second, the whole mesh's worst corner has MOVED: off the mid-block
        # interface and onto a FACETED WALL, at that faceting's own magnitude. Both
        # halves are needed — the first alone would pass on a mesh whose worst had
        # merely moved somewhere else worse, and the second alone would not show
        # that the interface improved rather than being left alone.
        #
        # WHICH wall is a fact about the shipped geometry and has changed once. Until
        # #95 it was the OUTER circle's, one grid line in at r = 9.19, because an
        # 80-facet polyline under 96 mesh nodes was the coarsest thing in the case.
        # With that circle stored at 320 facets the far field no longer binds and the
        # worst sits on the BODY at r = 0.500, whose 160 facets under the same ring
        # are 1.667 per interval — the residue #94's warning names on those four
        # edges and the whole of this mesh's 2.025.
        #
        # SO THE ASSERTION IS THE BODY, NOT "a wall". A first draft of this accepted
        # either circle, on the reasoning that the PROPERTY under test is
        # wall-rather-than-interface; a review pointed out that this accepts the
        # pre-#95 state, so a reverted geometry would pass a check whose own comment
        # says the far field no longer binds. The far field binding again IS a
        # regression here, and this is the check that should say so.
        oq = "\nMB_SPLIT_QUADS 0\n"
        _, _, oqs0 = run(tmp, "oq0", oq + NO_SMOOTH, config=ogrid_config)
        _, _, oqs1 = run(tmp, "oq1", oq + "\nMB_SMOOTH_ITERS 20\n",
                         config=ogrid_config)
        wall_tab = [l for l in outo1.splitlines() if "west 'w0'" in l]
        check(f"9. the O-grid's wall row is still held at its declared height ALL "
              f"the way round, which is #83's and must survive this ticket "
              f"({wall_tab[-1].strip() if wall_tab else None})",
              len(wall_tab) == 2 and "(0.0" in wall_tab[-1])
        pts0, cells0 = quad_corners(oqs0 + ".vtk")
        pts1, cells1 = quad_corners(oqs1 + ".vtk")
        # THE MID-BLOCK RADIAL BAND, indexed on the UNSMOOTHED mesh and reused.
        # Node ids are what welding rests on and no sweep allocates one, so the same
        # index is the same node in both files — which is the only selection that
        # can compare a line that MOVED.
        mid = set()
        for k, (x, y) in enumerate(pts0):
            rad = math.hypot(x, y)
            if not (2.0 < rad < 8.0):
                continue
            ang = math.degrees(math.atan2(y, x))
            if min(abs(ang - t) for t in (-180, -90, 0, 90, 180)) < 1e-9:
                mid.add(k)
        b0, b1 = devs_of(pts0, cells0, mid), devs_of(pts1, cells1, mid)
        check(f"9. the four mid-block radial interfaces are found on both meshes "
              f"({len(mid)} nodes, {len(b0)} corners) and the same set is read on "
              f"each, because a freed interface MOVES",
              len(mid) > 0 and len(b0) == len(b1) > 0)
        if b0 and b1:
            check(f"9. ...and THEIR OWN CELLS IMPROVE rather than staying at the "
                  f"unsmoothed values: max {max(b0):.4f} -> {max(b1):.4f} deg",
                  max(b1) < max(b0))
            check("9. ...which is what #83 could not do at all — its whole-mesh "
                  "worst was 12.036 deg, localised on exactly these lines at "
                  "r = 3.43 (this band is now under 2.0 deg)",
                  max(b1) < 2.0)
        worst, at = 0.0, None
        for c in cells1:
            for k in range(4):
                p, q, r = pts1[c[k]], pts1[c[(k + 1) % 4]], pts1[c[(k - 1) % 4]]
                u = (q[0] - p[0], q[1] - p[1])
                v = (r[0] - p[0], r[1] - p[1])
                lu, lv = math.hypot(*u), math.hypot(*v)
                if lu == 0 or lv == 0:
                    continue
                cs = max(-1.0, min(1.0, (u[0] * v[0] + u[1] * v[1]) / (lu * lv)))
                d = abs(90.0 - math.degrees(math.acos(cs)))
                if d > worst:
                    worst, at = d, p
        rad = math.hypot(*at) if at else -1.0
        check(f"9. ...and the smoothed mesh's WORST corner is on the BODY's faceted "
              f"wall — not on a mid-block interface, which is what #84 moved it off, "
              f"and not back on the far field, which is what #95 moved it off "
              f"({worst:.4f} deg at r={rad:.3f}; the body is r=0.5, the far field "
              f"r=10, and the freed interfaces run between them)",
              rad < 0.55)

        # ── 10. #83's OWN ACCEPTANCE, on the shipped C-grid ─────────────────
        #
        # #80's criterion for this ticket: max and mean non-orthogonality BETTER
        # than #57's recorded 32.04 / 4.56, wall first-cell accuracy NO WORSE than
        # its 0.44%, inverted still 0 — "both improving at once is the whole claim;
        # one at the cost of the other is not". Measured at the cap where the
        # combination is best.
        #
        # AND THE NEAR-LEADING-EDGE CELLS SPECIFICALLY, which the ticket asks for in
        # as many words: "the first cell off the wall around x = 0.017 on the
        # shipped C-grid are measured specifically, not only through the whole-mesh
        # maximum. That is the region the solver diverged in, and a mesh-wide
        # average can improve while it does not." So the region's own max AND mean
        # are read, over the ten quad cells that touch the airfoil between x = 0.005
        # and x = 0.030 — #57's worst corner is at (0.0134, 0.0196), inside it.
        #
        # THE INSTRUMENT IS VALIDATED FIRST. The whole-mesh figures out of this
        # reader are compared against the C++ ruler's own machine-readable line, so
        # the region figure is trusted because the same code agrees with the ruler
        # where the ruler looks.
        CAP83 = 20
        base_q, outq0, qs0 = run(tmp, "q0", "\nMB_SPLIT_QUADS 0\n" + NO_SMOOTH)
        _, out83, qs1 = run(tmp, "q83",
                            "\nMB_SPLIT_QUADS 0\nMB_SMOOTH_ITERS %d\n" % CAP83)
        u83 = qlines(out83, "_BEFORE")
        a83 = qlines(out83)
        check(f"10. the shipped C-grid at a cap of {CAP83} meshes as quads "
              f"(rc={base_q})", base_q == 0 and bool(a83))
        if u83 and a83:
            check(f"10. MAX non-orthogonality is BETTER than #57's baseline "
                  f"({u83[0]['nonortho_max_deg']:.3f} -> "
                  f"{a83[0]['nonortho_max_deg']:.3f} deg)",
                  a83[0]["nonortho_max_deg"] < u83[0]["nonortho_max_deg"] < 32.05)
            check(f"10. ...the MEAN is better AT THE SAME TIME, which is the whole "
                  f"claim ({u83[0]['nonortho_mean_deg']:.3f} -> "
                  f"{a83[0]['nonortho_mean_deg']:.3f} deg)",
                  a83[0]["nonortho_mean_deg"] < u83[0]["nonortho_mean_deg"] < 4.57)
            check(f"10. ...the wall first cell is NO WORSE than its 0.44%, and is in "
                  f"fact better ({100 * u83[0]['wall_first_cell_worst_rel']:.4f}% -> "
                  f"{100 * a83[0]['wall_first_cell_worst_rel']:.4f}%)",
                  a83[0]["wall_first_cell_worst_rel"]
                  <= u83[0]["wall_first_cell_worst_rel"])
            check(f"10. ...and inverted cells are still 0 "
                  f"({a83[0]['inverted']})", a83[0]["inverted"] == 0)
        pts0, cells0 = quad_corners(qs0 + ".vtk")
        pts1, cells1 = quad_corners(qs1 + ".vtk")
        all0, all1 = devs_of(pts0, cells0), devs_of(pts1, cells1)
        # ON BOTH MESHES, because the regional comparison below reads both and an
        # instrument validated on one of them is validated on neither. It also pins
        # the claim MB_SPLIT_QUADS rests on: non-orthogonality is measured on the
        # STRUCTURED cells either way, so the quad run must report the figure the
        # triangle run does.
        q0line = qlines(outq0)
        for label, devs, line in (("unsmoothed", all0, q0line[0] if q0line else {}),
                                  ("smoothed", all1, a83[0] if a83 else {})):
            check(f"10. THE INSTRUMENT AGREES WITH THE RULER on the whole "
                  f"{label} mesh, which is what makes its regional figure worth "
                  f"reading (reader max {max(devs) if devs else -1:.6f} deg vs line "
                  f"{line.get('nonortho_max_deg', -1):.6f})",
                  bool(devs) and bool(line)
                  and abs(max(devs) - line["nonortho_max_deg"]) < 1e-4
                  and abs(sum(devs) / len(devs) - line["nonortho_mean_deg"]) < 1e-4)
        check(f"10. ...and the QUAD run reports the same non-orthogonality as the "
              f"triangle run, so measuring on quads is not a different question "
              f"({q0line[0]['nonortho_max_deg'] if q0line else None} vs "
              f"{base.get('nonortho_max_deg')})",
              bool(q0line) and bool(base)
              and q0line[0]["nonortho_max_deg"] == base["nonortho_max_deg"]
              and q0line[0]["nonortho_mean_deg"] == base["nonortho_mean_deg"])
        poly = read_poly(os.path.join(_REPO, "examples", "geometries",
                                      "naca0012_cgrid.dat"))
        le0 = on_polyline(pts0, poly)
        le1 = on_polyline(pts1, poly)
        le0 = {k for k in le0 if 0.005 <= pts0[k][0] <= 0.030}
        le1 = {k for k in le1 if 0.005 <= pts1[k][0] <= 0.030}
        r0, r1 = devs_of(pts0, cells0, le0), devs_of(pts1, cells1, le1)
        check(f"10. the near-leading-edge region is found on both meshes and is the "
              f"same region ({len(le0)} wall nodes, {len(r0)} corners)",
              len(le0) == len(le1) > 0 and len(r0) == len(r1) > 0)
        if r0 and r1:
            check(f"10. ...and #57's OWN REGION improves, not just the mesh-wide "
                  f"maximum: max {max(r0):.3f} -> {max(r1):.3f} deg",
                  max(r1) < max(r0))
            check(f"10. ...including its MEAN, which a whole-mesh average could have "
                  f"hidden: {sum(r0)/len(r0):.3f} -> {sum(r1)/len(r1):.3f} deg",
                  sum(r1) / len(r1) < sum(r0) / len(r0))

        # ── 11. #84's OWN DELIVERABLES on the shipped C-grid ───────────────
        #
        # THE FREEZE RULE IS REPORTED, not inferred from a loop: a run says how many
        # nodes it was free to move and how many of those were on a shared edge, and
        # the second figure is checked against the run's OWN shared-edge report
        # rather than against a number typed here — an edge of n shared nodes frees
        # n - 2 of them, its two ends being declared corners.
        #
        # THE MESH STAYS CONFORMAL, measured with #53's own instrument on the
        # EXPORTED files: every interior edge in exactly two cells, the boundary
        # edge set exactly the `.bnd`, one connected component by node identity.
        # That is the property a per-block smoother would break — it is what tearing
        # a shared node into two looks like from outside — and it is the reason the
        # ticket asks for that measure rather than a new one.
        #
        # AND THE WAKE CUT SPECIFICALLY, where the ticket's own premise turned out
        # not to hold and the honest answer is the measurement. It asks that the
        # cut's "own cells improve rather than staying at their unsmoothed values".
        # On this geometry they CANNOT: the wake is a straight line on the symmetry
        # axis and the algebraic fill already leaves the cells against it EXACTLY
        # orthogonal — 0.0000 deg over all 48 of them — so there is nothing to
        # improve. What is asserted instead is what is true and what the criterion
        # was reaching for: the cut is one line both blocks read, it exports no
        # boundary face, its 23 interior nodes MOVE rather than being frozen, they
        # stay on the axis to 1.4e-18 by symmetry, and the cost of freeing them is
        # 0.0178 deg mean / 0.617 deg max at a cap of 20 against a mesh-wide gain of
        # 32.044 -> 29.895 max and 4.562 -> 3.821 mean. The lines that WERE the
        # worst ones — the radial interfaces — are group 9's, and they improve.
        rc84, out84, s84 = run(tmp, "m84", "\nMB_SMOOTH_ITERS 20\n")
        _, outu84, su84 = run(tmp, "m84u", NO_SMOOTH)
        a84 = qlines(out84)
        sm84 = smooth_line(out84)
        check(f"11. the shipped C-grid smooths and exports every file (rc={rc84}, "
              f"wrote {wrote(s84)})", rc84 == 0 and len(wrote(s84)) == 4)
        shared_nodes = [int(m) for m in re.findall(r"(\d+) shared nodes", out84)]
        want_shared = sum(n - 2 for n in shared_nodes)
        check(f"11. the run REPORTS which nodes it was free to move, and the shared "
              f"half is exactly the interior of the edges its own shared-edge report "
              f"names ({sm84.get('moved_shared')} vs {want_shared} from "
              f"{shared_nodes})",
              len(shared_nodes) == 4
              and sm84.get("moved_shared") == want_shared > 0)
        check("11. ...in the banner as well as in the token, saying which nodes are "
              "frozen and why",
              re.search(r"Movable nodes\s+: \d+ of \d+, of which \d+ on a shared "
                        r"edge \(walls and declared corners are frozen\)",
                        out84) is not None)
        check("11. ...and a run that smoothed NOTHING reports neither figure, "
              "because 0 movable nodes is a real answer and must not stand in for "
              "not having looked", "Movable nodes" not in outu84)
        # NODE COUNTS DO NOT CHANGE. Smoothing moves nodes; it never adds, removes
        # or re-identifies one — which is what "welding is by allocation" means on
        # the way out, and it is read off the exported files rather than the seam.
        nu, ns = vrt_nodes(su84), vrt_nodes(s84)
        cu, cs = cel_cells(su84), cel_cells(s84)
        check(f"11. node and cell counts are UNCHANGED by smoothing "
              f"({len(nu)}/{len(cu)} vs {len(ns)}/{len(cs)})",
              len(nu) == len(ns) > 0 and len(cu) == len(cs) > 0)
        check("11. ...and so is the CONNECTIVITY, id for id: the smoother writes "
              "coordinates and allocates nothing", cu == cs)
        # CONFORMITY, on the SMOOTHED files, with #53's measure.
        use = edge_use(cs)
        interior = [k for k, v in use.items() if v == 2]
        boundary = [k for k, v in use.items() if v == 1]
        overused = [k for k, v in use.items() if v > 2]
        bnd = bnd_faces(s84)
        check(f"11. the SMOOTHED mesh is still CONFORMING: every interior edge "
              f"belongs to exactly two cells ({len(interior)} interior, "
              f"{len(overused)} with more than two)", not overused)
        check(f"11. ...and its boundary edge set is EXACTLY the '.bnd' "
              f"({len(boundary)} vs {len(bnd)})",
              len(boundary) == len(bnd)
              and {f for f, _ in bnd} == set(boundary))
        check("11. ...and the whole mesh is ONE connected component, by node "
              "identity", components(cs, len(ns)) == 1)
        # THE WAKE CUT. Identified on the exported vertices: the segment of the
        # symmetry axis downstream of the trailing edge at x = 1.
        #
        # THE MOVEMENT IS READ OFF THE `.vtk` AND NOT THE `.vrt`, which cost this
        # check a false failure first: the STAR-CD vertex writer rounds, and the
        # wake's own displacement at a cap of 20 is 4.6e-06 at its finest station —
        # so 21 of the 24 nodes came back "unmoved" from a file that had simply not
        # written the digits. The `.bnd` half below stays on the STAR-CD files,
        # because there the question is about the patch list the converter reads.
        #
        # EACH SET IS INDEXED IN ITS OWN FILE'S NUMBERING. A `.vrt` id and a `.vtk`
        # id are the two numbers CLAUDE.md's `golden_mesh.py` note calls "precisely
        # the numbers free to move", so the first draft — a `.vrt`-indexed wake set
        # applied to the `.vtk` arrays — passed only by today's coincidence. There
        # are two sets now and they are checked against each other by SIZE.
        vp_u, _ = quad_corners(su84 + ".vtk")
        vp_s, _ = quad_corners(s84 + ".vtk")
        wake_vtk = [k for k, (x, y) in enumerate(vp_u) if y == 0.0 and x > 1.0]
        wake_u = [k for k, (x, y) in enumerate(nu) if y == 0.0 and x > 1.0]
        check(f"11. the wake cut is found on the exported mesh, in BOTH numberings "
              f"({len(wake_u)} '.vrt' nodes and {len(wake_vtk)} '.vtk' nodes on the "
              f"axis downstream of the trailing edge)",
              len(wake_u) > 2 and len(wake_vtk) == len(wake_u))
        on_axis = [f for f, _ in bnd
                   if all(ns[v - 1][1] == 0.0 and ns[v - 1][0] > 1.0 for v in f)]
        check(f"11. ...and it STILL exports no boundary face, smoothed: it is an "
              f"interior line with cells on both sides ({len(on_axis)} faces on it)",
              not on_axis)
        movedw = sum(1 for k in wake_vtk if vp_u[k] != vp_s[k])
        check(f"11. ...its interior nodes MOVE rather than staying frozen, which is "
              f"this ticket on the line #57 made the highest-risk one in the grid "
              f"({movedw} of {len(wake_vtk)} moved; the one that does not is the "
              f"declared corner at the outlet)",
              movedw == len(wake_vtk) - 1)
        check(f"11. ...and stays ONE line on the symmetry axis, to 1e-15 — the two "
              f"wake blocks are mirror images and the node is moved ONCE, so there "
              f"is no second answer to be pulled toward (worst |y| "
              f"{max(abs(vp_s[k][1]) for k in wake_vtk):.2e})",
              max(abs(vp_s[k][1]) for k in wake_vtk) < 1e-15)
        # AND WHAT FREEING IT COST, measured rather than claimed: the unsmoothed
        # cells against the wake are EXACTLY orthogonal, so the ticket's "its own
        # cells improve" is unreachable on this geometry and the honest figure is
        # the small price. Read on the quad runs group 10 already made, over the
        # cells touching the wake.
        # Group 10's own quad runs, named again rather than inherited: `pts0` is
        # rebound twice above (group 9's O-grid, then group 10's C-grid) and a
        # measurement that depends on which assignment ran last is one nobody can
        # check by reading it.
        cq0, cc0 = quad_corners(qs0 + ".vtk")
        cq1, cc1 = quad_corners(qs1 + ".vtk")
        wq = {k for k, (x, y) in enumerate(cq0) if y == 0.0 and x > 1.0}
        wd0, wd1 = devs_of(cq0, cc0, wq), devs_of(cq1, cc1, wq)
        check(f"11. the unsmoothed cells against the wake are EXACTLY orthogonal, "
              f"so 'its own cells improve' is unreachable here and the criterion's "
              f"premise does not hold on this geometry (max {max(wd0):.6f} deg over "
              f"{len(wd0)} corners)",
              bool(wd0) and max(wd0) < 1e-9)
        check(f"11. ...and freeing it costs {max(wd1):.4f} deg max / "
              f"{sum(wd1)/len(wd1):.4f} deg mean there, against a mesh-wide gain of "
              f"32.044 -> {a84[0]['nonortho_max_deg']:.3f} max and 4.562 -> "
              f"{a84[0]['nonortho_mean_deg']:.3f} mean — recorded, not hidden",
              bool(wd1) and max(wd1) < 1.0 and bool(a84)
              and a84[0]["nonortho_max_deg"] < 32.044
              and a84[0]["nonortho_mean_deg"] < 4.562)

        # ── 12. THE WALL WARNING'S BAR SITS ABOVE ITS OWN ARITHMETIC (#107) ─
        #
        # THE COMPARISON IS STILL "WORSE THAN THE MESH THE SOLVE STARTED FROM" and
        # this ticket does not touch that. What it moves is the ADDITIVE term under
        # it, which existed so that a wall whose pre-smoothing residual is exactly 0
        # would not get a bar of exactly 0 — and which sat at 1e-12, BELOW this
        # quantity's own arithmetic noise on a 5920-node mesh. So the term written
        # to protect near-zero walls was the one that fired on them: the shipped
        # C-grid's two outlet-side walls warned on a relative deviation of 2.3e-12,
        # printing `0.000000%` against `0.000000%` — a reader told a control
        # function failed, shown a before and an after identical to every digit, and
        # handed two remedies for nothing.
        #
        # BOTH HALVES, BECAUSE ABSENCE ALONE IS NOT THE CLAIM. A check that only
        # asserted the two noise warnings had gone would pass just as well on a
        # warning deleted outright, which is the failure a bar-raising fix invites.
        # So the two edges whose deviation is REAL are asserted present in the same
        # run, and the two that went quiet are asserted BACK at a cap where their
        # own deviation rises above the floor — the mute is on the quantity, never
        # on the edge.
        #
        # THE FLOOR IS 1e-9 RELATIVE, AND THE ORDERS ARE WRITTEN OUT BECAUSE #107's
        # OWN TEXT GOT THEM WRONG: it claims "six orders above what was measured
        # here (2.3e-12)", which is 2.6 (1e-9 / 2.334e-12 = 428). Six is true of the
        # ~1e-15 PRE-SMOOTHING residual, a different quantity from the one the bar
        # compares. Below, it is 4.0 orders under `e_ff_up`'s 9.499e-6, not five.
        # The margins are wide either side; the round numbers were not measured.
        # The angle bar on the line below it is unchanged and needs no change — it is
        # already absolute and in degrees, and 0.5 deg is nowhere near the noise.
        #
        # BLIND SPOT, and it is the reason this group exists rather than a comment:
        # the floor is calibrated against THIS repo's shipped cases at THEIR shipped
        # node counts. A mesh an order denser has a higher noise floor, and nothing
        # re-derives this constant from the mesh it is applied to. It is a threshold
        # that can go stale, and only these checks would notice.
        w20 = wall_height_warns(out84)
        check(f"12. the shipped C-grid at the default cap no longer warns about the "
              f"two outlet-side walls whose deviation is arithmetic noise — 2.3e-12 "
              f"relative, eight orders under this mesh's own worst wall (warned "
              f"about: {sorted(w20)})",
              "e_out_up" not in w20 and "e_out_lo" not in w20)
        check(f"12. ...while the two walls whose deviation is REAL still warn, so "
              f"this is a bar that was raised and not a warning that was deleted "
              f"({ {k: v[0] for k, v in w20.items()} })",
              "e_ff_up" in w20 and "e_ff_lo" in w20)
        # THE ASSERT AND THE SENTENCE ARE THE SAME CLAIM. This check said "five
        # orders" while asserting two, so a regression to a hundredth of the
        # measured value would have printed a false sentence and passed — #95's own
        # recorded lesson, caught by review here rather than by a run. What is
        # asserted is TWO orders (the bar), what is measured is four, and both are
        # printed. AND EACH EDGE IS REQUIRED TO BE PRESENT: the same line without
        # `e in w20` was vacuously true if both vanished, which is the absence this
        # group's own comment says is not the claim.
        # The margin in the message is DERIVED from the same reading the assert
        # uses, never a figure typed beside it: an injection that silenced these
        # edges left a hardcoded "4.0 orders up" standing next to a live 0.000000%,
        # which is a stale label on a live number.
        floor_pct = 1e-9 * 100.0
        worst_pct = w20.get("e_ff_up", (0.0, 0.0))[0]
        up = (math.log10(worst_pct / floor_pct) if worst_pct > 0.0 else float("-inf"))
        check(f"12. ...at least two orders above the new floor of {floor_pct:.0e}% "
              f"rather than beside it, which is what makes the gap between the two "
              f"pairs a decision and not a coin toss (worst {worst_pct:.6f}%, "
              f"{up:.1f} orders up)",
              all(e in w20 and w20[e][0] > 100.0 * floor_pct
                  for e in ("e_ff_up", "e_ff_lo")))
        # WHAT THE READER IS SHOWN, on this case and stated as this case's own
        # measurement rather than as a property the floor guarantees: at 1e-9
        # relative a legal warning CAN still print two figures that round together
        # at six decimal places, and nothing here stops it. What is asserted is that
        # the shipped C-grid no longer does.
        same = {e: v for e, v in w20.items() if v[0] == v[1]}
        check(f"12. ...and no surviving warning on this case shows a before and an "
              f"after that are the same number to every digit it prints, which is "
              f"the shape the reader could not act on ({same})", not same)
        # THE NEGATIVE CONTROL, in the shape #95 established: a wall the smoother
        # GENUINELY pulls off its declared height must still warn, or this fix has
        # bought silence rather than accuracy. Two of them, at the two ends of the
        # range, because one alone leaves the other end untested.
        #
        # THE `e_ff` PAIR ABOVE IS THE OTHER ONE, and it does double duty rather
        # than belonging to the positive half alone: 1.7e-13 -> 9.5e-6 is a wall
        # genuinely pulled off, which is the spec's own words for a negative
        # control, AND it is the check that stops the absence half passing on a
        # deleted warning. It is also the ONLY thing bounding this floor from
        # above — the gross-end pair below survives any floor under 0.269 — so the
        # two are not interchangeable and the docstring's blind spots say which
        # does what.
        #
        # Group 7's own cap-400 run, bound once above and named here rather than
        # inherited silently — the habit group 11 records after a measurement that
        # depended on which assignment had run last.
        w400 = wall_height_warns(outs)
        check(f"12. THE NEGATIVE CONTROL, gross end: at a cap of 400 the smoother "
              f"destroys the airfoil walls and is still told to say so — 27.37% off "
              f"a declaration it was handed exactly (af_up "
              f"{w400.get('af_up', (0, 0))[0]:.4f}%, af_lo "
              f"{w400.get('af_lo', (0, 0))[0]:.4f}%)",
              w400.get("af_up", (0, 0))[0] > 1.0
              and w400.get("af_lo", (0, 0))[0] > 1.0)
        check(f"12. ...and the two edges the default run stopped warning about are "
              f"BACK at that cap, where their own deviation has risen above the "
              f"floor: the bar mutes a QUANTITY, never an edge (e_out_up "
              f"{w400.get('e_out_up', (0, 0))[0]:.6f}%, e_out_lo "
              f"{w400.get('e_out_lo', (0, 0))[0]:.6f}%)",
              "e_out_up" in w400 and "e_out_lo" in w400)
        check("12. ...while a run that smoothed NOTHING warns about no wall at all, "
              "because there is no pair of coordinate sets to compare and a bar "
              "applied to one mesh would be a tolerance somebody picked",
              not wall_height_warns(outu84))
        # THE OTHER SHIPPED CASE THIS FILE ALREADY DRIVES, which is acceptance
        # criterion 2's only half reachable from here for free: group 8's own
        # default-cap O-grid run, bound once above. All four of its wall warnings
        # sit at 1e-3% or above and none of them may move — if one does, the floor
        # was set too high, and that is the criterion stated as an assert instead of
        # as prose. THE OTHER THREE SHIPPED CONFIGS ARE GROUP 13's, since #114 —
        # this sentence used to say they were measured-not-gated, which was this
        # file's own blind spot and is no longer true of any of the five.
        # THE BAR'S BASELINE, NAMED ON THIS CASE AT LAST (#114). "Worse than the
        # mesh the solve started from" is the whole sentence, and the C-grid's
        # airfoil pair is where it bites hardest: `af_up` and `af_lo` go in at
        # 0.44% off the declared height — the fill cannot hold a wall spacing that
        # fine around the leading edge — and come out at 0.05%, so they are the
        # worst-held walls in the BEFORE mesh and are correctly silent. Nothing
        # asserted that before this ticket: group 12's absence half named only the
        # two noise edges, and a bar rewritten as an absolute tolerance on the
        # DECLARATION would have passed every check here while warning about these
        # two. Found while widening the gate to the H-grid, whose `v00` is the
        # other instance of the same property and which this file first claimed
        # was the only one.
        cg_b, cg_a = wall_banner(out84, before=True), wall_banner(out84)
        check(f"12. ...and the airfoil pair, the WORST-held walls of the before "
              f"mesh, are silent because the sweeps IMPROVED them — the bar is the "
              f"mesh the solve started from and not the declaration (af_up "
              f"{cg_b.get('af_up')}% -> {cg_a.get('af_up')}%, af_lo "
              f"{cg_b.get('af_lo')}% -> {cg_a.get('af_lo')}%)",
              "af_up" not in w20 and "af_lo" not in w20
              and all(cg_b.get(e, 0.0) > cg_a.get(e, 0.0) > 0.0
                      for e in ("af_up", "af_lo"))
              and min(cg_b.get(e, 0.0) for e in ("af_up", "af_lo"))
                  >= max(cg_b.values()))
        wo20 = wall_height_warns(outo20)
        check(f"12. the shipped O-GRID keeps all four of its wall warnings at the "
              f"default, none of them being anywhere near the floor — the second "
              f"of the five shipped configs to carry acceptance criterion 2 "
              f"({ {k: round(v[0], 6) for k, v in wo20.items()} })",
              len(wo20) == 4
              and all(v[0] > 100.0 * floor_pct for v in wo20.values()))

        # ── 13. THE SAME CRITERION ON THE OTHER THREE SHIPPED CONFIGS (#114) ─
        #
        # The criterion group 12 asserts is true of the FIVE shipped multi-block
        # configs; until #114 it was checked on the two this file happened to
        # already drive. The remaining three go through the same warning path with
        # the same floor, and this group is the removal of that blind spot.
        #
        # THE FLOOR'S VALUE IS VISIBLE TO THE C-GRID ALONE, measured rather than
        # predicted. #114's criterion 2 asks that each added config report the
        # failure "with the warning guard reverted", and which guard that means
        # decides whether it is met: reverting the floor's VALUE reaches none of
        # the three, while reverting the BAR reaches all three (injections B, C
        # and D). An earlier draft of this comment called the criterion
        # unsatisfiable, which was wider than the measurement. With
        # `kHeightNoiseFloor` put back to 1e-12 and the tree rebuilt (2026-09-11),
        # square stays at 0 warnings, cavity at 0 and the H-grid at 7 — the same
        # counts as at 1e-9, edge for edge and figure for figure. That is not a
        # surprise this work uncovered; it is the table THIS DOCSTRING ALREADY
        # HELD, dated 2026-09-10, which says in as many words that only the two
        # C-grid warnings moved. So what each of the three is worth is stated here
        # per config, against the guard it can actually see.
        # THE FIVE ARE ENUMERATED FROM DISK, not from this list, because a sixth
        # shipped config would otherwise ship un-gated and nothing would say so —
        # the very shape this group exists to remove, and #114's review is what
        # noticed it surviving inside the fix for it. The three names below are
        # then the five minus the two group 12 drives.
        shipped = sorted(os.path.basename(f)[:-4] for f in
                         glob.glob(os.path.join(_REPO, "config", "multiblock_*.dat")))
        driven = ["multiblock_cavity", "multiblock_cgrid", "multiblock_hgrid",
                  "multiblock_ogrid", "multiblock_square"]
        check(f"13. the five shipped multi-block configs are exactly the five this "
              f"file drives, read off `config/` rather than from a list here — so a "
              f"SIXTH one cannot ship without a gate ({shipped})",
              shipped == driven)
        # THE EXIT CODE IS READ, as it is for every other run in this file: a case
        # that folded and exited 9 still prints its banners, so a group that only
        # parsed them would report ALL PASS on a broken mesh. #114's review.
        rc_sq, sq, _ = run(tmp, "sq114",
                           config=lambda: shipped_config("multiblock_square"))
        rc_cv, cv, _ = run(tmp, "cv114",
                           config=lambda: shipped_config("multiblock_cavity"))
        rc_hg, hg, _ = run(tmp, "hg114",
                           config=lambda: shipped_config("multiblock_hgrid"))
        check(f"13. all three added configs EXIT 0 at the default cap, so the "
              f"banners the checks below parse describe a mesh that was actually "
              f"exported (square {rc_sq}, cavity {rc_cv}, hgrid {rc_hg})",
              (rc_sq, rc_cv, rc_hg) == (0, 0, 0))
        w_hg = wall_height_warns(hg)
        hg_before, hg_after = wall_banner(hg, before=True), wall_banner(hg)
        check(f"13. the shipped H-GRID's eight declared wall edges are all MEASURED "
              f"at the default cap, so this case reaches the warning path rather "
              f"than being silent for lack of a target ({sorted(hg_after)})",
              len(hg_after) == 8 and len(hg_before) == 8)
        check(f"13. ...and SEVEN of the eight warn, every one of them a real "
              f"deviation the sweeps introduced from a fill that had been exact "
              f"({ {k: v[0] for k, v in sorted(w_hg.items())} })",
              len(w_hg) == 7 and all(v[1] == 0.0 for v in w_hg.values()))
        # THE EIGHTH IS THE BAR'S BASELINE ON THIS CASE. `v00` declares a geometric
        # spacing the algebraic fill cannot land on exactly, so it goes in 0.15%
        # off the declared height, and the sweeps make it BETTER, 0.08%. It is
        # therefore at once the worst-held wall in this mesh and correctly not
        # warned about — the bar's own sentence ("worse than the mesh the solve
        # started from") stated as a run rather than as a comment.
        #
        # **IT IS NOT THE ONLY ONE, WHICH THIS COMMENT CLAIMED UNTIL IT WAS
        # MEASURED.** The C-grid's `af_up`/`af_lo` do the same thing and larger:
        # 0.44% in, 0.05% out. So the property has two instances rather than one,
        # and the honest consequence is that BOTH are now asserted — the C-grid's
        # pair in group 12 above, added by this ticket because looking for a claim
        # of uniqueness is what found that nothing asserted the property at all.
        # The O-grid's `o*` edges are the near miss: their `was` is a real
        # 3.6e-5, not a rounding, but the sweeps make them WORSE, so they warn.
        #
        # THE SEVEN ARE RE-ASSERTED IN THIS CHECK'S OWN CLAUSE rather than
        # inherited from the one above, which is the habit this group already
        # records: `"v00" not in w_hg` is vacuously true on a build that warns
        # about nothing, and injection B is a build that warns about nothing.
        # READ OFF THE MACHINE-READABLE LINE, NOT THE BANNER, and #114's review is
        # why: `wall_first_cell_worst_rel` carries the worst wall at full precision
        # while the banner prints two decimals, and at two decimals `h10` ALSO
        # reads 0.08. The first draft compared `v00`'s ROUNDED 0.08 against
        # `h10`'s 6-digit 0.075166 — a true claim resting on a rounding interval
        # that straddles its own competitor, so it could have passed while false.
        # What is asserted instead needs no per-edge figure at all: the mesh's
        # worst wall (8.06e-4) is strictly ABOVE the worst of the seven warned
        # ones (7.5166e-4), so the worst-held wall is not among them — and the
        # eighth edge is the only one left. The banner figures stay in the message
        # as the reader-facing two decimals they are.
        q_hg = qlines(hg)
        qb_hg = qlines(hg, "_BEFORE")
        worst_hg = q_hg[0]["wall_first_cell_worst_rel"] * 100.0 if q_hg else 0.0
        worstb_hg = qb_hg[0]["wall_first_cell_worst_rel"] * 100.0 if qb_hg else 0.0
        check(f"13. ...while the EIGHTH, `v00`, is this mesh's WORST-held wall and "
              f"is still not warned about, because the sweeps IMPROVED it "
              f"(worst wall {worstb_hg:.6f}% -> {worst_hg:.6f}%, above the worst "
              f"of the seven at {max((v[0] for v in w_hg.values()), default=0.0):.6f}%; "
              f"banner {hg_before.get('v00')}% -> {hg_after.get('v00')}%): the bar "
              f"is the mesh the solve started from, the H-grid's instance of the "
              f"property the C-grid's airfoil pair carries above",
              len(w_hg) == 7 and "v00" not in w_hg
              and worst_hg > max((v[0] for v in w_hg.values()), default=0.0)
              and worstb_hg > worst_hg > 0.0)
        # `hg_min` FALLS BACK TO A NUMBER AND THE LOG TO -inf rather than either
        # raising: injection B silenced all seven, and the first draft of this
        # block CRASHED on the empty set instead of failing — which took the two
        # checks after it out of the run and would have read as a bite of five
        # where it was really a bite of seven. A check that cannot fail cannot be
        # scored, so nothing here may raise on a mesh the injection emptied.
        hg_min = min((v[0] for v in w_hg.values()), default=0.0)
        hg_up = (math.log10(hg_min / floor_pct) if hg_min > 0.0
                 else float("-inf"))
        check(f"13. ...and every one of the seven sits at least two orders above "
              f"the floor, the smallest {hg_min:.6f}% being "
              f"{hg_up:.1f} orders up — so a floor raised "
              f"to swallow this case has to be raised a long way",
              bool(w_hg) and hg_min > 100.0 * floor_pct)
        # AND IT TIGHTENS THE ONLY BOUND THIS CONSTANT HAS FROM ABOVE, which the
        # docstring's blind spot names as the wide half: what catches a floor set
        # too HIGH is a real warning going silent, and the lowest real warning in
        # the tree was the C-grid's `e_ff` pair at 9.499e-6 relative. The H-grid's
        # `v21` is 5.90e-6, so the band a raise could hide in narrows by a factor
        # of 1.6 — 3.98 orders to 3.77. That is a real tightening and a small one,
        # and it is asserted as the RELATION rather than as either figure, so the
        # claim stays true when a mesh moves.
        # AGAINST EVERY WARNING THE OTHER CONFIGS PRODUCE, not against one C-grid
        # edge. "The tightest upper bound this floor has" is a claim about all of
        # them, and the O-grid's four were in scope and excluded — #114's review.
        # They do not change the answer at the committed floor (0.037% each, two
        # orders above), which is exactly why leaving them out was a claim wider
        # than its assert.
        #
        # EVERY WARNING, NOT EVERY *REAL* ONE, and that word is load bearing:
        # "real" is not something a run can decide, and comparing against all of
        # them is what makes this the ONE added check the floor's own VALUE can
        # move in BOTH directions. Lowered to 1e-12 the C-grid's noise pair comes
        # back at 2.3e-10%, under the H-grid's 5.90e-4%, and this check goes red —
        # which is #114's criterion 2 met literally on the H-grid, found only by
        # re-running the injections after the review widened the comparison.
        # Square and cavity still cannot see the value at all.
        others = ([v[0] for v in w20.values()] + [v[0] for v in wo20.values()])
        check(f"13. ...and the smallest of them is BELOW every warning the other "
              f"four configs produce, so the H-grid carries the tightest upper "
              f"bound this floor has — and a floor LOWERED until noise reappears "
              f"under it reddens this too ({hg_min:.6f}% against a minimum of "
              f"{min(others, default=0.0):.6f}% over {len(others)} of them)",
              bool(others) and 0.0 < hg_min < min(others))
        same_hg = {e: v for e, v in w_hg.items() if v[0] == v[1]}
        check(f"13. ...and none of the seven shows a before and an after identical "
              f"to every digit it prints — #107's own symptom, asserted on the case "
              f"where seven warnings could carry it ({same_hg})", not same_hg)
        # SQUARE AND CAVITY ARE THE SILENT PAIR, AND THE SILENCE IS THE MESH'S, NOT
        # THE BAR'S. Both are rectangles, which the elliptic solve leaves where it
        # found them (the design note's "A RECTANGLE IS A FIXED POINT"): cavity
        # comes back bit for bit, square to 3.5e-16. Their walls are therefore at
        # an EXACT zero deviation before and after, and `now > was * 1.01 + floor`
        # is false for every floor at or above zero — which is why the 1e-12 build
        # above leaves them at 0 and why no floor injection can ever reach them.
        #
        # WHAT THEY DO GATE is the other direction, and it is the one #107 was
        # actually about: a wall the smoother did not move must not be warned
        # about. The guard that delivers that is the comparison itself, not the
        # floor — and these two are the only shipped cases where a `>` quietly
        # becoming a `>=` produces warnings out of nothing, because they are the
        # only ones where `now` equals `was` exactly on every wall. The count of
        # moved nodes is asserted beside it so the silence can never be a run that
        # smoothed nothing.
        for nm, out_ in (("SQUARE", sq), ("CAVITY", cv)):
            bef, aft = wall_banner(out_, before=True), wall_banner(out_)
            ws, sl = wall_height_warns(out_), smooth_line(out_)
            check(f"13. the shipped {nm} measures four wall edges at the default "
                  f"cap and warns about NONE of them, on a run that was free to "
                  f"move {sl.get('moved')} nodes and left every wall at the exact "
                  f"height the declaration asked for (before {bef}, after {aft})",
                  len(bef) == 4 and len(aft) == 4 and not ws
                  and sl.get("cap") == 20 and sl.get("moved", 0) > 0
                  and all(v == 0.0 for v in bef.values())
                  and all(v == 0.0 for v in aft.values()))

    print()
    if failures:
        print("%d check(s) failed:" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
