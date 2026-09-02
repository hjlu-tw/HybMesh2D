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
   is what stops an agent "improving" a decision the user made deliberately. **A marker WRAPS the
   same way an anchor does**: #70 found `USER-REQUESTED` and its `2026-08-21` on two different
   lines, so count marker-with-date, not the bare word, or a preserved marker reads as a lost one
   and a lost date as a preserved marker.
4. **Reversal narrative → one line plus an anchored pointer.** `SUPERSEDED by #NN:`,
   `SUPERSEDES #NN:` or `REVERSES #NN:`, the new answer in one clause, then
   `Why: docs/design_notes/<area>.md, "<anchor>"`. The ACTIVE forms exist because rule 1 forces
   them: when the surviving claim is the NEW answer, the old one cannot be the sentence's subject
   (#70). **The marker itself must not wrap either** — `grep -c -F "REVERSES #31"` printed 0 on
   #70's first pass, with `REVERSES` and `#31` on different lines.
   **Grep-verify every anchor** (`grep -c -F "<anchor>" <target>` must print exactly `1`) and keep
   **the anchor AND its `Why:` pointer on ONE LINE** — an extractor keyed on the whole construct
   breaks when the prefix wraps, which #69's first pass did in 2 of 4. Four ways an anchor fails,
   one found per ticket: it wraps in the TARGET (#73); it appears twice there (#68); it wraps in the
   RULE FILE (#69); or shortening it to fit makes it ambiguous (#69 review — "All four sides are
   reported" matches twice, "…, because v0" once). Budget about 55 characters for the anchor.
5. **Named blind spots move to one `## Named blind spots` list per rule file**, not trailing the
   rule they belong to. Their purpose is to stop a coverage claim, and one readable list serves that
   better than eight scattered asides. **Move only a COVERAGE LIMIT** — what a gate does not check.
   Two things that look like blind spots and are not: a *directive* ("prefer the iso-line for
   measurement"), and a **capability refusal** ("nothing welds along a BOUND edge") — the second is
   what the implementation deliberately does not support, so it belongs with its rule. Both were got
   wrong once each (#73, #69) and caught in review.
6. **Keep a measurement that constrains a decision; drop one that only justifies it.**
   `0.35 s → 0.07 s per frame` and `21- and 41-point resamplings` constrain. *"Four unrelated
   environment defects stood in the way"* justifies — design note.
7. **One bolded lead sentence per rule, bullets under it.** The FILE's existing section structure
   (`##` / `###`) is not part of this style and is not restructured — `mesher.md` keeps its
   `## Configuration` / `### Core C++` split and states its rules as bolded lead paragraphs. What is
   fixed is `## Named blind spots` (rule 5), the one section a compression adds.
8. **Do not touch the rule.** A compression that changes what a rule says is a behaviour change
   hidden in a docs diff. If a rule looks wrong, report it on the ticket.

## The ruler: build it before compressing, not after

A relocation can be proven complete by concatenation equivalence. **A compression cannot** — which
is why rule 2 is the only mechanical evidence available:

```python
import re
norm = lambda x: re.sub(r"\s+", " ", x).strip()          # a token WRAPS; #69 added this
tok = lambda s: {norm(x) for x in re.findall(r"`([^`]+)`", s)}
lost = tok(open("before.md").read()) - tok(open("after.md").read())
```

Run it per block and require `lost == set()`. On #73 it caught two real losses whose rules had
survived as prose with the identifier gone (`scan_series_range`, and the named wrong key `multi`).
**`norm` is not cosmetic**: without it #69 got two false positives and #70's review re-derived
295 → 296 with `(overwrite, no-archive)` "invented", because that token wrapped across two lines
in the BEFORE file. Same trap as rules 3 and 4 — it costs the ruler its only claim to be
mechanical, since a false positive and a real loss look identical. It does **not** catch a dropped
*constraint* whose identifier appears elsewhere — read the diff too.

## What the reference block measured

| | |
|---|---|
| block, before → after | **5,065 → 4,470 chars (−12%)** |
| identifiers lost | **none** |
| gate filenames preserved | `tests/cpp/test_multiblock.cpp`, `tests/test_multiblock_binding_surface.py` |
| reversal | `SUPERSEDED by #53` + a grep-verified anchor (count 1) |
| blind spot | moved to `mesher.md`'s new `## Named blind spots` |

**−12% is the honest expectation, not −50%**, and where a file's blind spots consolidate into a
list that did not exist before, the headline is smaller still: #73's whole-file pass was −7.7%,
while #69 (−1.6%) and #70 (−0.7%) each spent a ~5% fall in rule text on a new list and its
anchors. **A compression ticket pays for the structure it adds**, so the headline is the wrong
number to optimise — report the decomposition and let the two numbers disagree in public. These
files are
already dense; the style's value is structural — claim first, identifiers intact, reversals
pointing rather than retelling, blind spots in one list — and **not** byte savings. No rule file is
anywhere near its 60,000 budget, so a ticket that trades an identifier for characters has the
trade backwards.

Gate: `python3 tools/PreProcessor/tests/test_instruction_budget.py` (check 3 fails the build if a
gate filename is dropped, which is the red line most likely to be lost in transit).
