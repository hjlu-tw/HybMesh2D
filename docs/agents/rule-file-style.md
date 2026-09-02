# Entry style for `.claude/rules/*.md`

The style #59's compression tickets (#69–#72, #74) rewrite the rule files into, fixed on one
block by **#68** so that a wrong style cost one block rather than 106k characters. The reference
block is *"Boundary conditions are DECLARED; geometry attaches by ARC LENGTH"* in
`.claude/rules/mesher.md` (#52), chosen because it carries all three hard cases at once: reversal
narrative, a gate filename, and a named blind spot.

**What licenses this style**: the audience of these files is declared to be agents. Humans read
`README.md`, `docs/architecture_overview.md` and `docs/design_notes/`. So a sentence whose work is
*persuading a reader the rule is right* belongs in the design note, and the rule file keeps what
*constrains a decision*.

## The eight rules

1. **Lead with the claim.** Bold claim → owning module or identifier → the constraint → the gate.
   Never open with the story that produced the rule.
2. **Every identifier stays.** A rule whose subject is unnamed is not a preserved rule: the reader
   cannot check it and the next agent cannot find it. This is the one thing a compression can be
   *measured* against — see the ruler below.
3. **Two red lines, verbatim** (#59): a **gate test filename**, and every **`USER-REQUESTED` /
   `USER-REPORTED`** marker. The first is the reader's only route to verifying the rule; the second
   is what stops an agent "improving" a decision the user made deliberately.
4. **Reversal narrative → one line plus an anchored pointer.** `SUPERSEDED by #NN:` or
   `REVERSES #NN:`, the new answer in one clause, then `Why: docs/design_notes/<area>.md, "<anchor>"`.
   **Grep-verify every anchor** (`grep -c -F "<anchor>" <target>` must print exactly `1`) — a phrase
   that wraps in the TARGET does not resolve, and one that appears twice is not a pointer.
5. **Named blind spots move to one `## Named blind spots` list per rule file**, not trailing the
   rule they belong to. Their purpose is to stop a coverage claim, and one readable list serves that
   better than eight scattered asides. Known cost, reported on #73 and not fixed: a blind spot that
   is really a *directive* ("prefer the iso-line for measurement") ends up away from the rule an
   agent is reading. Leave the directive with the rule and move only the coverage limit.
6. **Keep a measurement that constrains a decision; drop one that only justifies it.**
   `0.35 s → 0.07 s per frame` and `21- and 41-point resamplings` constrain. *"Four unrelated
   environment defects stood in the way"* justifies — design note.
7. **A `##` heading per rule cluster, bullets inside.** One bolded lead sentence per bullet.
8. **Do not touch the rule.** A compression that changes what a rule says is a behaviour change
   hidden in a docs diff. If a rule looks wrong, report it on the ticket.

## The ruler: build it before compressing, not after

A relocation can be proven complete by concatenation equivalence. **A compression cannot** — which
is why rule 2 is the only mechanical evidence available:

```python
import re
tok = lambda s: set(re.findall(r"`([^`]+)`", s))
lost = tok(open("before.md").read()) - tok(open("after.md").read())
```

Run it per block and require `lost == set()`. On #73 it caught two real losses whose rules had
survived as prose with the identifier gone (`scan_series_range`, and the named wrong key `multi`).
It does **not** catch a dropped *constraint* whose identifier appears elsewhere — read the diff too.

## What the reference block measured

| | |
|---|---|
| block, before → after | **5,065 → 4,470 chars (−12%)** |
| identifiers lost | **none** |
| gate filenames preserved | `tests/cpp/test_multiblock.cpp`, `tests/test_multiblock_binding_surface.py` |
| reversal | `SUPERSEDED by #53` + a grep-verified anchor (count 1) |
| blind spot | moved to `mesher.md`'s new `## Named blind spots` |

**−12% is the honest expectation, not −50%.** #73's whole-file pass was −7.7%. These files are
already dense; the style's value is structural — claim first, identifiers intact, reversals
pointing rather than retelling, blind spots in one list — and **not** byte savings. No rule file is
anywhere near its 60,000 budget, so a ticket that trades an identifier for characters has the
trade backwards.

Gate: `python3 tools/PreProcessor/tests/test_instruction_budget.py` (check 3 fails the build if a
gate filename is dropped, which is the red line most likely to be lost in transit).
