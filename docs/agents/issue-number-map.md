# Issue-number map: session-local numbers that collide with the tracker

**A `#N` written in a commit message, a rule file or a design note is not always this
repo's tracker number.** Work done in a session that did not file a ticket first takes the
next number the session believes is free. When the tracker later issues that number to
something else, every reference silently points at the wrong thing.

**Resolve a `#N` against the table below BEFORE following it.** If it is not in the table,
it is a tracker number and `gh issue view <N>` is correct.

## 2026-11-27 — six numbers, every one of them misresolving

The work landed on `main` first and the issues were filed afterwards (`gh issue create`,
then closed with a pointer at the commits). The offset came out at **+2**, which is the
worst available outcome: **every session-local number is also a valid tracker number**, and
four of the six resolve to another ticket *in this same batch*, whose subject matter is
close enough that a reader would not notice they had the wrong one.

| `#N` as written in the tree | the work it means | the real tracker issue | but `gh issue view N` shows |
|---|---|---|---|
| `#195` | a graded block side facing a uniform one | **#197** | Price the wake cut's growth ratio (unrelated) |
| `#196` | the first case whose node count falls going outward | **#198** | A straight interior line cannot declare its shape |
| `#197` | the O-grid's generated far field | **#199** | …the graded-side warning, i.e. local `#195` |
| `#198` | the thin-body ring advisory | **#200** | …the reducing case, i.e. local `#196` |
| `#199` | the two-ring generated far field | **#201** | …the generated far field, i.e. local `#197` |
| `#200` | `MB_SMOOTH_WALL_FREEZE` | **#202** | …the ring advisory, i.e. local `#198` |

Commits: `f96a4a5`, `4defe54`, `07d0798`, `fb0b610`, `342b1cc`, `a0d3b84`, `bd8b8c8`,
`ffdccec`, `bfc6ec3`.

**The tree was NOT rewritten.** 100 references across about 25 files carry the local
numbers, and the six commit subjects carry them too — those cannot be corrected without a
rebase. The map is the correction. A rewrite was weighed and declined: it would fix the
files and leave the commit log stale, which is a half-correction that reads as a whole one.

## Why this keeps happening, and the one habit that stops it

A session that is going to produce a ticket's worth of work **files the issue first** and
uses the number the tracker gives it. The failure is not the collision, it is that a number
invented mid-session looks exactly like a number the tracker issued — there is nothing in
`#198` that says which kind it is.

It has happened before: `#174`/`#175` meant two different things across 27 sites.

**If you are about to write `#N` and you did not get N from `gh issue create` or
`gh issue view`, either file the issue now or do not write a number.** "The ticket that
added the wall-layer freeze" costs five words and never goes stale.
