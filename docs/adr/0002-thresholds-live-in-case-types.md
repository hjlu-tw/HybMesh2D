# The mesher measures and never grades; thresholds live in case types

`.claude/rules/mesher-quality.md` states that the quality report carries "**NO COLOUR AND NO
THRESHOLD, anywhere, by decision**", and the product code holds none — only per-case **pins**,
on the stated distinction that "a threshold says a number is **BAD**; a pin says it **MOVED**".
Our operators nevertheless need a **verdict** (usable / needs attention / unusable / not
determinable) rather than raw numbers. **We are keeping the mesher's refusal to grade exactly
as it stands, and putting thresholds one layer up, inside case types**, which consume the
numbers the mesher already writes to `.provenance.json`.

A future reader finding thresholds in this system will assume someone violated that rule.
They did not. The rule's subject is **universality**: whether 30° of non-orthogonality is bad
depends on whether this is an aerofoil or a cavity, so the mesher has no standing to say. A
case type's threshold is explicitly *not* universal — it is scoped to one class of problem and
authored by someone who knows that class. The two coexist because they claim different things.

## Consequences

- **Thresholds carry their origin.** A case type's thresholds are measured from a
  **reference mesh** the maintainer judged good, times a tolerance factor — so a threshold is
  a demonstration, not an invented number, and six months later it is traceable to the mesh
  it came from. A misjudged verdict is corrected by adding a reference mesh, not by hand-
  editing the number (which would throw the traceability away).
- **The negative-measurement rule forces a fourth verdict state.** The mesher returns
  negative, never 0.0, for anything unmeasurable, and prints `not measured`, precisely so
  that "we did not measure" never reads as "it came out perfect". The verdict layer must
  preserve that: `not measured` becomes **not determinable**, never "usable".
- **`EXIT_ERR_INVERTED` (9) must be a hard "unusable" at this layer.** The mesher exports a
  folded mesh under its ordinary filename, by design, so that a developer can *see* the fold.
  That is right for the mesher and dangerous for an operator, whose finished case would carry
  a folded mesh that looks entirely normal. The verdict layer, not the mesher, is what
  refuses to let it through.
- **An operator's deviation downgrades the verdict's standing rather than voiding it.** The
  thresholds were measured under premises the edit has changed, so the verdict must say so —
  but withholding it entirely would just teach operators not to touch anything.
