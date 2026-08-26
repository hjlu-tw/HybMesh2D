---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
---

Implement the work described by the user in the spec or tickets.

First establish that the work is not already done. A closed issue can still be
unbuilt on the branch you are standing on: read the issue's state and its
closing comment, then check the tree and `git branch --contains` for whatever
commit that comment names. Report what you find rather than rebuilding it.

Use /tdd where possible, at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Once done, use /code-review to review the work.

Commit your work to the current branch.
