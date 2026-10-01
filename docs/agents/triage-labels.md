# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use.

Re-checked against `gh label list` on 2026-10-01: **four of the five already exist** — `wontfix` (one of GitHub's own defaults, described there as "This will not be worked on"), plus `needs-triage`, `ready-for-agent` and `ready-for-human`, created by earlier `/triage` runs. Apply all four; never create a second label with the same role. Only **`needs-info` does not exist yet** — the first `/triage` run that needs it creates it (`gh label create needs-info`). The repo's other defaults (`bug`, `enhancement`, `documentation`, `question`, …) are orthogonal to triage state and are left alone.
