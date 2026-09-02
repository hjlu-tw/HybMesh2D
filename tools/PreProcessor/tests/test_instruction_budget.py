#!/usr/bin/env python3
"""The instruction files have a per-file budget, and no rule file can go missing.

There is no production code behind this gate: the thing under test is the
instruction set itself. `CLAUDE.md` is loaded in full on every session before a
line of source is read, so its size is a per-session cost paid by everyone; the
`.claude/rules/*.md` files are loaded on demand when a file matching their
`paths:` globs is READ (measured on Claude Code 2.1.250, #61 — not at launch,
and not at all for a non-matching file). Three properties keep that arrangement
from decaying, and each is external behaviour rather than wording: how many
characters each file costs, whether every rule file is reachable from the root
file's tripwire table, and whether every gate a rule names still exists.

Nothing here asserts on prose. The relocation tickets (#59) rewrite all of it on
purpose, and a gate that pinned sentences would have to be edited by the very
change it exists to guard.

Checks:
 1. Per-file size. The root file and each rule file are measured against their
    OWN budget — never a total, so moving text from one rule file into another is
    not a legal evasion. The failure names the file, its size, its budget and the
    design note the detail belongs in.
 2. The tripwire table against the rule files, BOTH directions. A rule file that
    no row names fails (it looks perfectly healthy from inside itself), and a row
    naming a rule file that does not exist fails too.
 3. Every gate-test filename named inside a rule file — or in the root file, which
    still carries the rules for every area the move has not reached yet — exists on
    disk. This
    is the check that makes compression honest: dropping a gate name severs a rule
    from its only means of verification and changes nothing a reader would notice.
 4. Every rule file declares a `paths:` list that is present, non-empty, and not
    only `**`. Measured in #61: the loader DISCARDS such a list and the file then
    loads at `session_start` with no globs at all — silently becoming an
    always-loaded file, which is the exact inversion of the point of the split,
    one character away from a legitimate glob.
 5-9. Each of the four is verified by an in-test injection over a mutated COPY of
    the inputs, asserting the check then fails, that the mutated input is still
    well-formed, and that it really differs from the original.

Sizes are measured in CHARACTERS, which is the unit #59 states the budgets in — not
bytes, which the root file has 297 more of today because this repo's own prose
contains CJK. That figure moves with every relocation ticket — it was 389 before
#66 — and is re-derived here, never carried. The tooling's own per-file limit (4 MiB, observed in #61) is in bytes,
and a character budget is conservative against it either way, since a character is
never fewer than one byte.

Known remaining blind spots, stated rather than pretended away:

 a. Check 3 matches a gate test by BASENAME. `tests/cpp/test_multiblock.cpp` and
    `test_multiblock.cpp` name the same gate, and pinning the spelling would fail a
    rule file that is correct — but the consequence is that a rule file naming the
    WRONG DIRECTORY for a real gate passes.
 b. It can prove a rule file is reachable IN THE TABLE. It cannot prove a session
    ever received it: that is the tooling's behaviour, not this repo's, and it is
    covered by #61's manual probe instead. A version bump can invalidate that probe
    without anything here going red.
 c. Nothing checks that a pointer INTO a rule file still resolves. FOUR went stale
    in #62's own move and this gate saw none of them — `models/mesh_config.py:106`
    and `services/mesh_bl_field_specs.py:213` (both GUI files, so no mesher glob
    hands their reader the moved text), `src/MultiBlock.cpp:69`, and
    `docs/design_notes/mesher.md:8`. They were repointed by hand afterwards, which
    is the point rather than the remedy: nothing here caught them and nothing here
    will catch the next one. A check would have to resolve prose section titles
    across files, which is the kind of substring matching this repo has twice
    measured blind. #63's move was swept by hand the same way and found two —
    `CLAUDE.md`'s own "See the 'Full Pipeline' section under Architecture" and
    `docs/design_notes/pipeline.md:8` — both repointed in the same commit. #64's
    sweep found six: `edge_props_dist_mixin.py:31` and `:217`,
    `pipeline_io_ctrl.py:47`, `docs/design_notes/gui.md:8`,
    `docs/agents/domain.md:11` — and, review found, `CLAUDE.md:235`, where "the
    derived key map" was left with its defining block one screen below it and that
    block gone. The last one matters most: it is in the always-loaded file, the one
    place a sweep is cheap, and the first version of this entry claimed all five
    were "outside this gate's reach". #65's sweep found two, and both are files
    #64 already repointed once — `docs/design_notes/gui.md:8` and
    `docs/agents/domain.md:11`, each of which ENUMERATES which rules have moved and so
    goes stale on every one of these tickets. Nothing here noticed either time.
    #66's sweep found `docs/design_notes/gui.md:8` a THIRD time, for the same reason,
    and nothing else: the six results gate tests carry no pointer at `CLAUDE.md` at
    all, and `docs/agents/domain.md:11` survived because #65 replaced its enumeration
    with a pointer at the tripwire table — which is the only fix that has held. What
    #66 also found is a defect this entry cannot see from either end: the moved rules
    discuss `services/phi_quality.py`, which NO glob in ANY rule file reaches, so the
    pointer resolved while the file it points at was unreachable. It is named in
    `gui-results.md`'s header instead. Reachability of a NAMED file is a third thing
    nothing here checks.
 d. `RULE_BUDGET` is a flat 60,000 with no ratchet, because #59 fixes the number.
    The five rule files that exist are 35,615 / 36,615 / 15,483 / 11,799 / 12,847
    characters, so "moving text into another rule file is not a legal evasion" only bites
    for a move larger than the 24,385 / 23,385 of headroom the two large ones have left,
    and not at all for a move into any of the other three, which have 44,517 / 48,201 / 47,153.
    It tightens on its own as the last area lands. Exact figures rather than
    rounded ones, because rounding is what went wrong twice: that 36,615 read "36.1k"
    here from #63 until #64's review measured it, and #65 first wrote its own new file as
    "12.0k" when it was 12,611 — measured before a later edit to the same file and never
    re-derived. This blind-spot list is not exempt from the rule the root file states two
    screens up, that a number carried in from a neighbouring document is not evidence; nor
    from the stronger one #65's review supplies, that a number re-derived BEFORE the last
    edit is a carried-in number too. #66 broke that rule on its first attempt and BOTH
    review axes caught it independently: the two figures for the files #66 itself edits
    were this list's own HEAD values, stale the moment the ticket touched them, sitting
    beside a freshly added sentence claiming every figure was re-derived. The claim is
    kept, because it is the right rule; what it now describes is a measurement taken after
    the last content edit of the ticket rather than during it.

Needs no Qt, no build tree and no network.

Run:  python3 tools/PreProcessor/tests/test_instruction_budget.py
"""
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_ROOT_NAME = "CLAUDE.md"
_RULES_DIR = os.path.join(".claude", "rules")

# --- budgets -----------------------------------------------------------------
# ROOT_BUDGET is a RATCHET, set to the root file's actual size after each
# relocation ticket in #59 and lowered by the next one; the final value is locked
# by the last ticket. It is exact rather than rounded up on purpose — the point is
# that the next feature which tries to add 3k to the always-loaded budget trips
# the gate on its first attempt, which is what the previous split (93k moved out,
# 5,752 chars back within two feature commits) had no way to do.
ROOT_BUDGET = 52_453
# Per rule file, and flat rather than ratcheted because #59 fixes the number. Well
# inside the tooling's own limit — 4 MiB, confirmed on this build in #61 — so this is
# repo policy, not a loader constraint, which is the right way round. Note the units
# differ and the comparison survives it: the loader counts BYTES, these budgets count
# CHARACTERS, and a character is never fewer than one byte.
RULE_BUDGET = 60_000

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


# --- the inputs, as one value -------------------------------------------------
# Every check is a pure function of this dict, which is what makes the injections
# below cheap: mutate a copy, ask the same function.
def read_world():
    root_path = os.path.join(_REPO, _ROOT_NAME)
    with open(root_path, encoding="utf-8") as fh:
        root_text = fh.read()
    rules = {}
    rules_dir = os.path.join(_REPO, _RULES_DIR)
    if os.path.isdir(rules_dir):
        for name in sorted(os.listdir(rules_dir)):
            if name.endswith(".md"):
                with open(os.path.join(rules_dir, name), encoding="utf-8") as fh:
                    rules[name] = fh.read()
    return {"root": root_text, "rules": rules, "tests": collect_test_files()}


def collect_test_files():
    """Basenames of every test_*.py / test_*.cpp in the tree.

    Matched by BASENAME rather than by the path a rule file happens to spell:
    `tests/cpp/test_multiblock.cpp` and `test_multiblock.cpp` name the same gate,
    and pinning the spelling would fail on a rule file that is correct.
    """
    skip = {".git", "build", "__pycache__", "results", ".venv", "node_modules"}
    found = set()
    for dirpath, dirnames, filenames in os.walk(_REPO):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for fn in filenames:
            if fn.startswith("test_") and fn.endswith((".py", ".cpp")):
                found.add(fn)
    return found


# --- shared parsing -----------------------------------------------------------
_RULE_REF = re.compile(r"\.claude/rules/([A-Za-z0-9_.-]+\.md)")
# A machine-readable anchor, not a section title. The first version accepted a
# rule-file mention in ANY markdown table row of the root file, which is looser than
# the criterion's "a tripwire row" — a mention in the design-note table would have
# satisfied "every rule file is named". Prose is deliberately not pinned (the
# compression ticket rewrites all of it), so the anchor is a comment the compression
# pass carries rather than a heading it may retitle. Its ABSENCE is a failure in its
# own right: silently falling back to scanning every table is exactly the loosening
# this replaced.
TRIPWIRE_ANCHOR = "<!-- TRIPWIRE TABLE"


def tripwire_rows(root_text):
    """Rule-file names named by a row of the tripwire table.

    Returns None when the anchor is missing — distinct from "the table names
    nothing", so the caller can report the two differently.
    """
    lines = root_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith(TRIPWIRE_ANCHOR):
            start = i
            break
    if start is None:
        return None
    named, seen_table = [], False
    for line in lines[start + 1:]:
        if line.lstrip().startswith("|"):
            seen_table = True
            for m in _RULE_REF.finditer(line):
                named.append(m.group(1))
            continue
        # The table ends at the first non-row line AFTER it has begun; the anchor's
        # own remaining comment lines and the blank line between are skipped.
        if seen_table:
            break
    return named


def frontmatter_paths(text):
    """The `paths:` list of a rule file, or None when there is no frontmatter.

    Returns [] for a `paths:` key that is present but empty, so "absent" and
    "empty" stay distinguishable — the loader treats them the same, but the
    failure message should not.
    """
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    body = text[4:end + 1]
    paths = None
    in_list = False
    for line in body.splitlines():
        if re.match(r"^paths:\s*\[", line):
            inline = line.split("[", 1)[1].rsplit("]", 1)[0]
            return [p.strip().strip("'\"") for p in inline.split(",") if p.strip()]
        if re.match(r"^paths:\s*$", line):
            paths, in_list = [], True
            continue
        if in_list:
            m = re.match(r"^\s+-\s*(.+?)\s*$", line)
            if m:
                paths.append(m.group(1).strip().strip("'\""))
                continue
            if line.strip() and not line.startswith(" "):
                in_list = False
    return paths


# The three design notes that exist, keyed by the AREA prefix of a rule file's name
# (`mesher.md`, `gui-results.md`, `pipeline-case.md`, ...). A set rather than a
# mapping: the note is named after the area, and an identity dict would only hide
# that.
_DESIGN_NOTE_AREAS = frozenset(("mesher", "gui", "pipeline"))


def design_note_for(fname):
    """Which design note a detail trimmed out of this file belongs in.

    The pressure has to push rationale DOWN a layer rather than out of the repo, so
    the failure message names a destination instead of just a number. For the ROOT
    file there is no single note — it is cross-cutting by construction — so it gets
    every concrete destination it could mean. The first version returned a GLOB
    there, which is not a place anything can be put, and injection 5's substring
    assertion was satisfied by it.
    """
    stem = fname[:-3] if fname.endswith(".md") else fname
    area = stem.split("-", 1)[0].lower()
    if area in _DESIGN_NOTE_AREAS:
        return "docs/design_notes/%s.md" % area
    return ("the rule file for the detail's own area (see the tripwire table), or "
            "one of docs/design_notes/mesher.md, gui.md, pipeline.md")


# --- check 1 ------------------------------------------------------------------
def check_sizes(world):
    fails = []
    root_size = len(world["root"])
    if root_size > ROOT_BUDGET:
        fails.append(
            "%s is %d chars, over its %d budget by %d. It is loaded in FULL on "
            "every session, so this is a per-session context cost. Move the "
            "detail into %s, or into the rule file for its area, rather than "
            "trimming it out of the repo."
            % (_ROOT_NAME, root_size, ROOT_BUDGET, root_size - ROOT_BUDGET,
               design_note_for(_ROOT_NAME)))
    for name, text in sorted(world["rules"].items()):
        size = len(text)
        if size > RULE_BUDGET:
            fails.append(
                "%s/%s is %d chars, over its %d budget by %d. Move the detail "
                "into %s — not into another rule file, which the per-file budget "
                "exists to refuse."
                % (_RULES_DIR, name, size, RULE_BUDGET, size - RULE_BUDGET,
                   design_note_for(name)))
    return fails


# --- check 2 ------------------------------------------------------------------
def check_tripwire(world):
    fails = []
    rows = tripwire_rows(world["root"])
    if rows is None:
        return ["%s has no %s ... --> anchor above its tripwire table, so this check "
                "cannot tell which table is the tripwire table. Restore the anchor "
                "rather than relying on a heading, which the compression pass is "
                "free to retitle." % (_ROOT_NAME, TRIPWIRE_ANCHOR)]
    named = set(rows)
    on_disk = set(world["rules"])
    for name in sorted(on_disk - named):
        fails.append(
            "%s/%s exists but NO tripwire row in %s names it. A rule file no row "
            "names is invisible: an agent that creates or edits a matching file "
            "without READING one first is never handed it (measured, #61), so the "
            "table is what makes 'I did not know there was a rule' unreachable."
            % (_RULES_DIR, name, _ROOT_NAME))
    for name in sorted(named - on_disk):
        fails.append(
            "a tripwire row in %s names %s/%s, which does not exist. Either the "
            "rule file was renamed and the row was not, or the row was written "
            "for a move that never landed."
            % (_ROOT_NAME, _RULES_DIR, name))
    return fails


# --- check 3 ------------------------------------------------------------------
_GATE_REF = re.compile(r"\btest_[A-Za-z0-9_]+\.(?:py|cpp)\b")


def check_gate_names(world):
    """Applied to the ROOT file as well as the rule files.

    The acceptance criterion asks only for the rule files, but the root still
    carries most of the rules while the move is staged, and the relocation tickets
    are precisely when a gate name can be dropped in transit. Same property, one
    superset — and it is measured, not assumed: all 17 gates the root names today
    resolve. That count falls with each relocation (44 before #63 moved the pipeline
    rules out) and is re-derived here rather than carried; it stood at 44 through three
    tickets that each lowered it, which is the failure this whole file is about.
    """
    fails = []
    sources = [(_ROOT_NAME, world["root"])]
    sources += [("%s/%s" % (_RULES_DIR, n), tx)
                for n, tx in sorted(world["rules"].items())]
    for where, text in sources:
        for gate in sorted(set(_GATE_REF.findall(text))):
            if gate not in world["tests"]:
                fails.append(
                    "%s names the gate test %s, which is on no path in this tree. "
                    "A rule whose gate cannot be found is a rule nobody can verify "
                    "they have not broken."
                    % (where, gate))
    return fails


# --- check 4 ------------------------------------------------------------------
def check_paths_frontmatter(world):
    fails = []
    for name, text in sorted(world["rules"].items()):
        paths = frontmatter_paths(text)
        if paths is None:
            fails.append(
                "%s/%s declares no `paths:` frontmatter list. The loader then "
                "loads it at session_start with no globs — an always-loaded file, "
                "the exact inversion of the split (measured, #61)."
                % (_RULES_DIR, name))
            continue
        if not paths:
            fails.append(
                "%s/%s declares an EMPTY `paths:` list, which the loader discards, "
                "making the file always-loaded (measured, #61)."
                % (_RULES_DIR, name))
            continue
        if all(p.strip() in ("**", "**/*") for p in paths):
            fails.append(
                "%s/%s declares `paths:` of only %r. The loader discards a list "
                "that is entirely `**` and loads the file at session_start with no "
                "globs (measured, #61) — one character away from a legitimate glob "
                "and silent."
                % (_RULES_DIR, name, paths))
    return fails


# =============================================================================
world = read_world()

check(bool(world["rules"]),
      "0. .claude/rules/ holds at least one rule file (nothing below can bite on "
      "an empty rule set)")

def run(fn, msg):
    """Evaluate a check ONCE, print each failure, then record the verdict.

    Calling the function twice — once to print, once inside check() — is how the
    first version read, and it is a real hazard rather than only waste: the two calls
    could disagree if a check ever touched the filesystem.
    """
    fails = fn(world)
    for fail in fails:
        print("     -> " + fail, flush=True)
    check(not fails, msg)


run(check_sizes,
    "1. every instruction file is within its OWN per-file budget (root %d, each rule "
    "file %d, in characters)" % (ROOT_BUDGET, RULE_BUDGET))
run(check_tripwire,
    "2. the tripwire table and the rule files agree in BOTH directions")
run(check_gate_names,
    "3. every gate-test filename named in a rule file — or in the root — exists on disk")
run(check_paths_frontmatter,
    "4. every rule file's `paths:` is present, non-empty and not only `**`")


# --- injections ---------------------------------------------------------------
# Each mutates a COPY of the inputs, asserts the check then fails, and asserts
# the mutation is still well-formed and really differs — an injection that merely
# corrupts its input looks identical to the check working.
def copy_world(w):
    return {"root": w["root"], "rules": dict(w["rules"]), "tests": set(w["tests"])}


# 5. an oversized file
inj = copy_world(world)
pad = ROOT_BUDGET - len(inj["root"]) + 1
inj["root"] = inj["root"] + "\n" + ("padding. " * ((pad // 9) + 2))
check(inj["root"] != world["root"] and inj["root"].startswith("# " + _ROOT_NAME)
      and len(inj["root"]) > ROOT_BUDGET,
      "5. injection is well-formed: the padded root still opens with its own "
      "heading, really differs, and is genuinely over budget")
sz = check_sizes(inj)
check(len(sz) == 1 and _ROOT_NAME in sz[0] and str(ROOT_BUDGET) in sz[0]
      and str(len(inj["root"])) in sz[0]
      and "docs/design_notes/mesher.md" in sz[0],
      "5. check 1 fails on it, naming the file, its size, its budget and a CONCRETE "
      "destination — a `docs/design_notes/*.md` glob passed this assertion once and "
      "is not a place anything can be put")

# A rule file over budget is the other half of check 1, and it must NOT be
# excusable by the root being small: the budget is per file, never a total.
inj = copy_world(world)
victim = sorted(inj["rules"])[0]
inj["rules"][victim] = inj["rules"][victim] + ("x" * (RULE_BUDGET + 1))
check(frontmatter_paths(inj["rules"][victim]) == frontmatter_paths(world["rules"][victim])
      and len(inj["rules"][victim]) > RULE_BUDGET,
      "5b. injection is well-formed: the padded rule file keeps its frontmatter "
      "and really is over budget")
sz = check_sizes(inj)
check(len(sz) == 1 and victim in sz[0]
      and design_note_for(victim) in sz[0]
      and design_note_for(victim) != design_note_for(_ROOT_NAME),
      "5b. check 1 fails on the RULE file even though the root is inside its own "
      "budget — per-file, never a total — and names that AREA's own design note "
      "rather than the root's fallback")

# 6. a rule file that no tripwire row names
inj = copy_world(world)
phantom = "zz-phantom-area.md"
inj["rules"][phantom] = "---\npaths:\n  - src/Phantom.cpp\n---\n\nA rule.\n"
check(phantom not in tripwire_rows(inj["root"])
      and frontmatter_paths(inj["rules"][phantom]) == ["src/Phantom.cpp"]
      and set(inj["rules"]) != set(world["rules"]),
      "6. injection is well-formed: the phantom rule file has a valid, narrow "
      "`paths:` glob — it looks perfectly healthy from inside itself")
tw = check_tripwire(inj)
check(len(tw) == 1 and phantom in tw[0] and "NO tripwire row" in tw[0],
      "6. check 2 fails in the on-disk-but-unnamed direction")

# 7. a tripwire row naming a rule file that does not exist.
#
# Inserted INTO the anchored table rather than appended to the file: appending is
# what the first version did, and once the table was anchored that row landed
# outside it — an injection that stops biting because the code got stricter looks
# exactly like the code getting weaker.
inj = copy_world(world)
before = len(tripwire_rows(inj["root"]))
rows = [ln for ln in inj["root"].splitlines() if _RULE_REF.search(ln)
        and ln.lstrip().startswith("|")]
check(len(rows) >= 1, "7. the tripwire table has a row to insert after")
inj["root"] = inj["root"].replace(
    rows[0] + "\n",
    rows[0] + "\n| Nonexistent area | `.claude/rules/nope.md` | `src/**` |\n")
after = tripwire_rows(inj["root"])
check(len(after) == before + 1 and "nope.md" in after
      and inj["root"] != world["root"],
      "7. injection is well-formed: the added line really parses as one more "
      "tripwire row")
tw = check_tripwire(inj)
check(len(tw) == 1 and "nope.md" in tw[0] and "does not exist" in tw[0],
      "7. check 2 fails in the named-but-absent direction too — one direction "
      "alone is blind")

# 8. a renamed gate filename
inj = copy_world(world)
victim = None
for name, text in sorted(inj["rules"].items()):
    hits = sorted(set(_GATE_REF.findall(text)))
    if hits:
        victim, gate = name, hits[0]
        break
check(victim is not None, "8. at least one rule file names a gate test to rename")
if victim is not None:
    renamed = gate.replace("test_", "test_renamed_", 1)
    inj["rules"][victim] = inj["rules"][victim].replace(gate, renamed)
    check(inj["rules"][victim] != world["rules"][victim]
          and renamed not in inj["tests"]
          and frontmatter_paths(inj["rules"][victim]) is not None,
          "8. injection is well-formed: the rule file keeps its frontmatter, "
          "really differs, and the new name is on no path in the tree")
    gn = check_gate_names(inj)
    check(any(renamed in f for f in gn),
          "8. check 3 fails on it — a compression pass that drops or mistypes a "
          "gate name cannot pass silently")

# ...and the same in the ROOT file, which is where most rules still are.
inj = copy_world(world)
root_gates = sorted(set(_GATE_REF.findall(inj["root"])))
check(bool(root_gates), "8b. the root file names at least one gate test")
if root_gates:
    renamed = root_gates[0].replace("test_", "test_renamed_", 1)
    inj["root"] = inj["root"].replace(root_gates[0], renamed)
    check(inj["root"] != world["root"] and renamed not in inj["tests"]
          and inj["root"].startswith("# " + _ROOT_NAME),
          "8b. injection is well-formed: the root really differs, still opens with "
          "its own heading, and the new name is on no path in the tree")
    gn = check_gate_names(inj)
    check(any(renamed in f and _ROOT_NAME in f for f in gn),
          "8b. check 3 covers the root file too, so a gate name cannot be lost in "
          "transit while the relocation is staged")

# 9. `paths:` absent, empty, and only `**`
#
# These three probes mutate the frontmatter of a REAL rule file, keeping its body, so
# what is asserted is a property of this repo's own input rather than of a literal
# invented here. The first version replaced the whole rule set with a hand-written
# stub and "proved well-formedness" by comparing two test-local literals, which
# asserts nothing about the injected world.
victim = sorted(world["rules"])[0]
real = world["rules"][victim]
real_paths = frontmatter_paths(real)
body = real[real.find("\n---", 3) + 4:]
check(real_paths and len(real_paths) > 1 and body,
      "9. the real rule file being mutated has a multi-entry `paths:` list and a "
      "body, so the mutations below have something to damage")
for label, head in (
        ("absent", ""),
        ("empty", "---\npaths:\n---\n"),
        ("only **", "---\npaths:\n  - **\n---\n"),
        ("only **/*", "---\npaths:\n  - **/*\n---\n")):
    inj = copy_world(world)
    inj["rules"][victim] = head + body
    got = frontmatter_paths(inj["rules"][victim])
    check(inj["rules"][victim] != real
          and inj["rules"][victim].endswith(body)
          and got != real_paths
          and (head == "" or inj["rules"][victim].startswith("---\npaths:")),
          "9. injection is well-formed: the %r mutation keeps the real rule file's "
          "whole body, really differs from it, and changes only the `paths:` list"
          % label)
    pf = check_paths_frontmatter(inj)
    check(len(pf) == 1 and victim in pf[0],
          "9. check 4 refuses `paths:` %r, which the loader would silently turn "
          "into an always-loaded file" % label)
check(not check_paths_frontmatter(world),
      "9. negative control: the real, unmutated rule set passes check 4, so the "
      "four failures above are the mutation and not the checker")

# 10. the tripwire anchor removed. A missing anchor must FAIL rather than fall back
# to scanning every table in the root file — the fallback is the looseness the
# anchor replaced, and it would be silent.
inj = copy_world(world)
lines = inj["root"].splitlines(keepends=True)
at = [i for i, ln in enumerate(lines) if ln.lstrip().startswith(TRIPWIRE_ANCHOR)]
check(len(at) == 1, "10. the root file carries exactly one tripwire anchor")
# The WHOLE comment block, not just its first line: leaving a dangling `-->` behind
# would make the injection an ill-formed document as well as an unanchored one, and
# then it could not distinguish the two.
end = at[0]
while end < len(lines) and "-->" not in lines[end]:
    end += 1
inj["root"] = "".join(lines[:at[0]] + lines[end + 1:])
check(inj["root"] != world["root"]
      and tripwire_rows(world["root"])
      and tripwire_rows(inj["root"]) is None
      and _RULE_REF.search(inj["root"])
      and "-->" not in inj["root"][:inj["root"].find("| Area")],
      "10. injection is well-formed: the whole anchor comment is gone with no "
      "dangling delimiter, the table and every rule-file mention are untouched, and "
      "the rows really stop resolving")
tw = check_tripwire(inj)
check(len(tw) == 1 and TRIPWIRE_ANCHOR in tw[0],
      "10. check 2 fails naming the anchor, instead of quietly accepting a "
      "rule-file mention from any table in the file")

print(("\nRESULT: " + ("ALL PASS" if not _FAILS else f"{len(_FAILS)} FAIL")), flush=True)
sys.exit(1 if _FAILS else 0)
