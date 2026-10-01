# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

**Layout: single-context.** One `CONTEXT.md` + one `docs/adr/` at the repo root. (HybMesh2D is a single C++ mesher plus one PyQt6 pre-processor GUI — there is no workspace/monorepo split, so there is no `CONTEXT-MAP.md` and no per-context ADR directory.)

## Before exploring, read these

- **`CONTEXT.md`** at the repo root — the glossary of domain terms.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in.
- **`CLAUDE.md`** at the repo root, plus the on-demand rule files its tripwire table names (`.claude/rules/*.md`) — this repo keeps an unusually dense body of hard-won invariants across the two — the BL/no-BL junction rules, the panel↔model data-flow contract, the length-unit/`Linf` relationship, the pop-up stacking rules, and much else. Which rule file holds which is moving ticket by ticket under #59, so read the tripwire table for the area you are about to touch rather than a list here, which would go stale on the next one. Treat them as required reading alongside `CONTEXT.md`, not as an alternative to it.

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The `/domain-modeling` skill (reached via `/grill-with-docs` and `/improve-codebase-architecture`) creates them lazily when terms or decisions actually get resolved.

Measured 2026-10-01: `CONTEXT.md` and `docs/adr/` now **both exist** — the glossary and ADRs `0001`/`0002` landed in `f9e3974`. That does not change the rule above: the next term or decision is still added lazily, by `/domain-modeling`, when it is actually resolved — never by going and filling the directory out upfront.

## File structure

```
/
├── CLAUDE.md                  ← existing invariants + build/run reference
├── CONTEXT.md                 ← glossary (added to lazily)
├── docs/
│   ├── adr/                   ← decision records (added to lazily)
│   │   ├── 0001-families-compute-positions-no-dbc.md
│   │   └── 0002-thresholds-live-in-case-types.md
│   └── agents/                ← this directory: skill configuration
├── include/                   ← C++ headers (Config.hpp, GeomUtils.hpp)
├── src/                       ← C++ mesher (main.cpp, BoundaryLayer.cpp, Mesh.cpp)
├── solver/                    ← UNICONES solver + STL3d pre-processor
└── tools/PreProcessor/        ← JSON-driven resampler CLI + PyQt6 GUI
```

`docs/` already holds long-form design documents (`custom_domain_bc_plan.md`, `pipeline_refactor_plan.md`, `solver_integration_plan.md`, `ui_framework_migration_plan.md`) and the UNICONES user manual. Those are **plans and vendor docs, not ADRs** — an ADR records a decision that has been taken and its consequences. Don't retrofit them into `docs/adr/`; cite them from an ADR when one is written.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/domain-modeling`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders) — but worth reopening because…_
