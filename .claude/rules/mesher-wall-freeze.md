---
paths:
  - include/MbShared.hpp
  - src/MbShared.cpp
  - include/Config.hpp
  - src/cli.cpp
  - include/MultiBlock.hpp
  - tests/cpp/test_multiblock.cpp
  - tools/PreProcessor/tests/test_mb_wall_freeze.py
  - tools/PreProcessor/gui/app/services/mesh_field_specs.py
---

# Mesher rules — WHICH NODES THE SMOOTHER MAY NOT MOVE (`MB_SMOOTH_WALL_FREEZE`)

Loaded on demand when the plan that decides who moves, the key's two doors, the GUI row that
mirrors it or either of its two gates is read. **THE TWENTIETH RULE FILE, AND THE TENTH TAKEN
BECAUSE ANOTHER WAS FULL**: `.claude/rules/mesher-smoothing.md` had 3,198 characters of slack
when #200 arrived and these rules are 2,900 more than that. #85, #137, #153, #165, #170, #177
and #189 are the precedent — a rule file at its budget takes a new file rather than a squeeze,
because compressing rules to fit a number is how a rule quietly loses the clause that made it
a rule, and `docs/agents/rule-file-style.md` refuses that compression outright.

**THIS FILE IS ONE FREEZE OUT OF FOUR, AND THE OTHER THREE ARE NEXT DOOR.** The smoother holds
a node for four different reasons and only the newest is here: a node ON a wall (#83), a
DECLARED CORNER (#84), a shared line with a DECLARED SHAPE (#151, relaxed by #176's
`MB_SMOOTH_SLIDE`), and the wall BAND below. **Read `.claude/rules/mesher-smoothing.md` as
well** — every glob here but the last two is that file's, so a session touching
`src/MbShared.cpp` loads both, which is the intended overlap. What that file answers is what
the smoother DOES; what this one answers is which nodes it is not allowed to do it to.

Rules only: the rationale — the measurements, the injections and the named blind spots — is
`docs/design_notes/mesher.md`, the same note `mesher-smoothing.md` points at. Read it before
overruling a rule here, and when a rule changes update BOTH.

**THE WALL-LAYER FREEZE IS A CHOICE OF WHICH HEIGHT, NOT AN IMPROVEMENT**
(`MB_SMOOTH_WALL_FREEZE`, #200; the band in `src/MbShared.cpp::mbSmoothPlan`)

- **IT HOLDS N INTERIOR ROWS BESIDE EACH WALL, ON TOP OF THE WALL ROW, WHICH IS ALREADY
  FROZEN FOR A DIFFERENT REASON.** #83 froze the wall row because a node on a wall may
  not leave the DOMAIN — that is geometry and is not negotiable. The row one step in is a
  DISCRETISATION: its distance from the wall IS the first-cell height the fill solved
  for, the control functions only TARGET it, and on a body with a corner the Winslow
  operator wins. **Do not restate either freeze in terms of the other.**
- **WHAT IT ACTUALLY DOES IS REPLACE THE SMOOTHED WALL HEIGHT WITH THE UNSMOOTHED ONE**,
  exactly — not approach it, which is what a stronger control function would buy. Which
  of the two is better is **a property of the case, and it goes both ways**:
  - **on the SHIPPED set it is mostly a LOSS, and that was measured only after review
    asked for it.** Seven `config/multiblock_*.dat` cases declare a wall height; SIX are
    worse frozen and one is better. The first draft of this rule generalised from the
    single case the gate then measured and called the loss "small", which `cgrid_chain`
    falsifies by a factor of 263:

    | shipped case | freeze 0 | freeze 1 | |
    |---|---|---|---|
    | `multiblock_cgrid.dat` | 0.000968 | 0.004368 | LOSS |
    | `multiblock_cgrid_chain.dat` | 0.000666 | **0.175201** | LOSS |
    | `multiblock_ogrid.dat` | 0.000371 | **0.000036** | win |
    | `multiblock_reducing.dat` | 0.000045 | 0.044834 | LOSS |
    | `multiblock_tworing.dat` | 0.000000 | 0.000171 | LOSS |
    | `multiblock_tworing_curve.dat` | 0.000000 | 0.037367 | LOSS |
    | `multiblock_tworing_offset.dat` | 0.000000 | 0.070625 | LOSS |

    These are the cases the smoother's default was TUNED on, so this is the expected
    direction rather than a surprise — but it means **the key is for a drawing the
    smoother is failing, and the shipped set is not that drawing.**
  - on the research cases (a 163° trailing-edge corner, `docs/research/
    allampalli-2010-reproductions.md` §5.3) the smoother was SPENDING the height:
    **92.38% becomes 12.58%** on a NACA 0012, a factor of 7.3; the flat plate is
    60.61% → 6.99% and the 64A010 93.18% → 14.10%.
  Gate: `tests/test_mb_wall_freeze.py` check 2, which runs **every shipped case that
  declares a wall height**, prints the table above, and asserts the direction is NOT
  uniform (at least one loss and at least one win) rather than asserting a direction.
  Check 6 is the research case, where it reverses. **A check saying "it improves" would
  be red on six of seven shipped cases**, and the honest reading of that red is not
  "the feature broke".
- **THE INTERIOR STILL RELAXES, SO IT IS NOT A SECOND SPELLING OF `MB_SMOOTH_ITERS 0`.**
  Mean non-orthogonality on the 0012 is **4.792° against 4.799** — within a hundredth of
  a degree. Gates: check 68e (the interior moves while the wall row moves exactly zero)
  and `test_mb_wall_freeze.py` 5 and 6.
- **THE COST IS FOLDED CELLS AND IT IS NAMED RATHER THAN OMITTED**: holding a row stops
  the solve relieving the cells beside it, and on both aerofoils that is **two more**
  (0012 4 → 6, 64A010 2 → 4). The flat plate folds nothing either way and its WORST cell
  angle improves as well, 56.07° → 52.91. Gate: `test_mb_wall_freeze.py` 6, third check.
- **A COUNT AND NOT A BOOL**, which is the one way it differs from `MB_SMOOTH_SLIDE`: a
  boundary layer several cells deep is as declared as its first cell. Nothing measured
  says where it stops being useful, so it is not capped — but **2 is already the same
  wall height as 1** (the first row sets it) at a slightly worse mean, so 1 is the value
  the measurements support.
- **THE DISTANCE IS COUNTED IN THE BLOCK'S OWN INDEX FRAME FROM ITS OWN `wallSpecs`
  SIDES**, asked of EVERY node and asked BEFORE the shared-side rules — a node one row
  off a wall can also sit on a seam, and "whose block moves this seam node" does not stop
  it being the node that carries the height. Gate: check 68d, which holds that the rule
  is keyed on a side being a **WALL** and not on it being an edge of the block.
- **DEFAULT 0, AND THAT IS THE SHIPPED PLAN NODE FOR NODE AND IN ORDER** — not merely a
  similar one. That is the property #81–#84 and #176 each kept and what makes a smoother
  change attributable; `golden_mesh.py compare` is unchanged by this ticket. Gates: check
  68c and `test_mb_wall_freeze.py` 3.
- Gated by `tests/cpp/test_multiblock.cpp` check 68 (68–68e) for the PLAN and
  `tools/PreProcessor/tests/test_mb_wall_freeze.py` for the `.dat` KEY. **Both are
  needed and neither is redundant**: `test_multiblock` links the pure layer, so it
  compiles neither `include/Config.hpp` nor `src/cli.cpp`, and #200's injection round
  found that breaking the parse AND breaking the wiring both left that binary byte for
  byte identical. Four plan injections and five config-path injections.
  Why: `docs/design_notes/mesher.md`, "A ROW THAT CARRIES A DECLARATION".

## Named blind spots

This list is this file's OWN and is short because the arc is one ticket old. The smoother's
other blind spots — the cap's advice wording, what group 14 compares, and the rest — stay in
`.claude/rules/mesher-smoothing.md`, which is where the rules they are about live. A reader
checking "what is NOT covered about smoothing" has to read both lists, and that is the cost of
the split rather than an omission.


- **NOTHING SAYS WHICH CASES WANT THE FREEZE, AND THE TWO SHIPPED ANSWERS DISAGREE.**
  Four measurements exist: three bodies with a corner want it badly and the one smooth
  aerofoil this repo ships does not. What separates them is not isolated — density,
  first-cell aggressiveness and corner angle all differ at once — so the key is offered
  with its two directions measured and no advice about which you are in. The run's own
  before/after quality report is the thing to read.
- **NO SHIPPED `config/multiblock_*.dat` SETS IT**, so the only coverage of a non-zero
  value is the two gates' own runs. That is deliberate — a shipped case changing its
  mesh would have to re-baseline the golden family — but it means the key has no
  worked example a reader can run.
