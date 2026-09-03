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
 5. Every rule file's design-note pointer resolves, and the note it points at names
    every module that rule file's own globs claim BY FILENAME. A rule file carries one
    rationale pointer in its header, so rules that arrive without their rationale make
    that pointer lie about part of the file — which is what #76 was: the export rules
    moved out of the root while their evidence stayed in `gui.md`. Ownership is read
    from the globs, not from a coverage list: a glob whose last component is `**` or `*`
    claims a directory rather than a file and is deliberately NOT ownership, because
    `views/panels/**` reaches `restart_chooser.py` and `tools/PreProcessor/gui/**`
    reaches everything. It fires only when the module IS named in another note, so the
    check reports a misfiled rationale rather than an undocumented module. Both
    narrowings are measured rather than assumed, and the whole ladder is stated because
    the first version of this entry attached the LAST number to the FIRST rung: as
    shipped 0 failures today; counting a directory glob as ownership too, 3 (all
    legitimate cross-area pointers — `restart_chooser.py` under `views/panels/**`,
    `pipeline_config.py` and `case_run_note.py` under the whole-GUI glob); dropping
    ownership entirely, as #76 specifies the check, 8; and dropping the
    named-in-another-note filter as well, which is that ticket's literal wording, 27.
    #76 measured 20/20 with zero false positives when only two rule files existed, and
    specified that it should land BEFORE #64-#67; it did not, so the six wide-glob GUI
    rule files those tickets and #77 added were already in the tree. The narrowing is a
    consequence of that ordering, not an improvement on the ticket.
 6. No rule in the ROOT names a GUI module that some rule file's globs already
    reach. That state splits one rule across two layers: the glob hands a session a
    rule file which is silent about the file it just opened, and nothing says so. It
    had recurred four times before anything measured it (#63, #76, #67's
    `run_batch.py`, and the 13,894 chars #77 moved). Mentions INSIDE the anchored
    tripwire region are excluded by region rather than by an exemption list — there,
    naming an area's files is the table's job. `KNOWN_RESIDUE` pins the one live
    violation with the ticket that owns it (#76), and a pin that stops being a
    violation FAILS TOO, so it cannot outlive the defect the way a skip list would.
 injections. Every check is verified by an in-test injection over a mutated COPY of
    the inputs, asserting the check then fails, that the mutated input is still
    well-formed, and that it really differs from the original. Printed labels say
    `check N` or `injection N`: the two used to share one integer space, and #77's
    check 6 collided with check 2's injection 6.

Sizes are measured in CHARACTERS, which is the unit #59 states the budgets in — not
bytes, which the root file has 181 more of today because this repo's own prose
contains CJK. That figure moves with every relocation ticket — it was 197 before
#76 — and is re-derived here, never carried. The tooling's own per-file limit (4 MiB, observed in #61) is in bytes,
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
    block gone (that sentence has itself since moved: #67 took it to
    `.claude/rules/gui-seams.md`, so the line number here is history, not a pointer). The last one matters most: it is in the always-loaded file, the one
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
    nothing here checks — and #67 found the second instance, `tools/PreProcessor/run_batch.py`,
    reached by no glob in any rule file while the Qt-free seam rules on it. Its first draft
    of the tripwire row asserted the opposite (that `pipeline-case.md` matched it), which is
    what this repo's own "enumerate before every/only/all" rule exists to stop.
    #67's sweep found `docs/design_notes/gui.md:8` a FOURTH time — so its enumeration was
    finally replaced with a pointer at the tripwire table, the same fix #65 applied to
    `docs/agents/domain.md:11`, which has held ever since. It also claimed, in this very
    paragraph, that #67 had made nothing else stale, and review measured that false in the
    place with the least excuse: the `CLAUDE.md:235` reference SIX LINES UP is a pointer at
    a block #67 itself moved. A sweep that does not sweep its own file is the shape this
    blind spot keeps taking. #76's sweep found NOTHING it had made stale — the export rules were the only block left
    in the root's GUI section, nothing outside `CLAUDE.md` pointed INTO it (the two gate
    tests it names, `test_case_export.py` and `test_case_workspace_export.py`, carry no
    pointer at the root file at all), and `docs/design_notes/gui.md:8` held for the second
    time since #67 replaced its enumeration with a pointer at the tripwire table. What it
    did have to repoint is in the destination rather than the source: `pipeline.md`'s own
    header said its rules were moved by #63, which stopped being the whole story the moment
    a second ticket moved rules in. The first draft of this entry claimed the sweep found
    ZERO, and BOTH review axes measured that false against a pointer #77 left behind and
    #76 was about to contradict: the root's own tripwire row and
    `.claude/rules/gui-panels-config.md` both said `MeshConfig.output_base`'s Output-`.*`
    rule was "still in `CLAUDE.md`" while #77 had moved it to `gui-handoff.md`, one screen
    from this ticket's new sentence that NO residue is left. Both are repointed here rather
    than named, because a file that contradicts itself is worse than a stale pointer to
    another file — which is the same reason #67's review gave for its own `CLAUDE.md:235`.
    Two pointers the sweep found stale from EARLIER tickets are left alone and
    named here instead, because #67 did not make them stale and its ticket forbids
    editing tests: `arch_probes.py:171` and `test_field_spec_tables.py:515` each say
    "CLAUDE.md records ..." about text that #63 and #64 moved into a rule file. That is
    this blind spot's own shape — a pointer at a MOVED section, resolving to a file that
    no longer holds it — surviving three tickets in a test file nobody swept.
    #67 also lands the inverse of the reachability gap: `include/BLParams.hpp` and
    `Config.hpp` are the C++ half of the parity rule, they ARE reached by `mesher.md`'s
    globs, and `mesher.md` does not carry that rule. A glob reaching a file whose rules
    are in ANOTHER rule file is what #76's check 5 exists to catch; until it lands, the
    root file's one-line pinning of the four repo-wide standards is what covers it.
    #77's sweep found the THIRD unreachable named file — `CMakeLists.txt`, which the
    subprocess-environment rule rules on directly (its HINTS list is the defect that kept
    CI red) and which no glob in any rule file matches; `.github/workflows/gui-tests.yml`
    is the same shape. Both are named in `gui-lifecycle.md`'s header and in its tripwire
    row. Three instances now (`phi_quality.py`, `run_batch.py`, `CMakeLists.txt`), and the
    pattern is that the unreachable file is always the one OUTSIDE the package the rule's
    other modules live in. Check 6 is the inverse-direction check and does not see this
    one: it asks whether a glob reaches a file whose rule is elsewhere, never whether a
    named file is reached at all.
    #77's sweep found THREE, all in test files and all REPOINTED rather than named, because
    #77 is what made them stale: `test_sidebar_seam.py:396` ("CI had never been green") and
    `mesher_bin.py:18` and `:31` (the hardcoded-path smell, and `env_setup` as the single
    answer to "where is Gmsh") — every one of them a block that moved to `gui-lifecycle.md`.
    A fourth, `docs/architecture_overview.md:932`, names the GUI layering description this
    ticket moved to `gui-seams.md`; it sits inside that document's §7, whose whole subject is
    where `CLAUDE.md` is stale, so it gained a parenthetical pointer instead of a rewrite.
    `docs/design_notes/gui.md:8` held for the FIRST time in five tickets, because #67
    replaced its enumeration with a pointer at the tripwire table. Review of #77 found this
    ledger entry missing while (d) and (e) had both been updated in the same pass — the
    ledger is the point of the entry, so a ticket skipped is the entry failing at its job.
 e. Check 6 sees a module only in the SHORT backticked form a rule uses about its own
    area — `services/foo.py`, `app/services/foo.py`, `views/panels/foo.py`. Three
    escapes, measured rather than supposed:
      - A **bare basename**. The moved export rules name `case_export_docs.py` and
        `case_export_usage.py` exactly that way, so two of #76's four modules were
        invisible here and were NOT in `KNOWN_RESIDUE` (pinning them would have failed
        the staleness half, since they are not violations this check can see). Check 5
        DOES resolve that form, against the GUI package and only when the basename is
        unique there — which is why its injection bites on all three misfiled modules
        and check 6's could only ever have bitten on one. The two checks read the same
        rule files and disagree about what a module mention is; that asymmetry is
        deliberate and stated rather than harmonised, because check 6 reads the ROOT,
        where a bare basename is far more often prose than a rule.
      - The **full repo-relative path**, which is the form `## Common Tasks` uses for
        wayfinding. That is the distinction the short form buys, and a rule that spells
        the long path escapes.
      - A module that no longer EXISTS on disk: `root_ruled_modules` drops it, so a rule
        left pointing at a renamed module is invisible here (blind spot (c)'s territory,
        and this check does not cover it either).
      - Only the six GUI packages. A rule naming `src/` or `tools/scripts/` is not
        checked, so `gui-lifecycle.md`'s `tools/scripts/gmsh_*` glob is outside it.
    And `_glob_matches` normalises `**` to `*` for `fnmatch`, which is LOOSER than the
    loader for a pattern like `a/*/b`. Every pattern in this repo is a prefix glob or a
    literal, where the two agree — but a future middle-wildcard glob would be matched
    more eagerly here than by the tooling.
 f. Check 5's reach is 45 of the 132 module mentions across the eight rule files
    (measured): 84 are named by a rule file whose globs do not claim them BY FILENAME —
    the cross-area pointers the check must not fail — and 3 more are claimed but named in
    no design note at all (`controllers/solver_ctrl.py`,
    `views/result_canvas_interaction_mixin.py`, `views/result_canvas_plots_mixin.py`), so
    a rule whose rationale was never written is invisible to it. Two further escapes: a
    module named in BOTH notes passes, which is why `case_export.py` — already in
    `pipeline.md` through the `case_archive` and `case_input_paths` rationale — is not
    among the three its own injection fires on; and a rule file naming no Python module
    is vacuously true, which is `mesher.md` (zero, its rules being about C++ and `.dat`
    keys). The check therefore bites on the MAJORITY of a misfiled set, never on every
    member.
 d. `RULE_BUDGET` is a flat 60,000 with no ratchet, because #59 fixes the number.
    Eight rule files now — 39,798 / 35,012 / 15,762 / 13,238 / 12,672 / 11,861 / 11,348 / 8,969  characters (pipeline-case, mesher, gui-results, gui-seams, gui-canvas-edit, gui-panels-config, gui-handoff, gui-lifecycle) — so "moving text into another rule file
    is not a legal evasion" only bites for a move larger than the 20,202 / 24,988 of
    headroom the two large ones have left, and not at all for a move into any of the other
    six, which have 44,238 / 46,762 / 47,328 / 48,139 / 48,652 / 51,031. #76 spent 3,446 of
    pipeline-case's headroom moving the export rules in, and that is the first move in this
    series the flat budget could plausibly have refused: two more of that size would. #70's
    compression of that same file gave 263 of it back, which is the shape of the trade: a
    relocation costs thousands and a compression returns hundreds. The flat budget did
    not tighten as the split finished and never will: #59's own two areas were the biggest,
    every file added since is small, and the mean headroom has gone UP with each ticket.
    Only a per-file ratchet like `ROOT_BUDGET`'s would change that, and #59 fixes the number.
    Exact figures rather than
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
import fnmatch
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_ROOT_NAME = "CLAUDE.md"
_RULES_DIR = os.path.join(".claude", "rules")
_NOTES_DIR = os.path.join("docs", "design_notes")

# --- budgets -----------------------------------------------------------------
# ROOT_BUDGET is a RATCHET, set to the root file's actual size after each
# relocation ticket in #59 and lowered by the next one; the final value is locked
# by the last ticket. It is exact rather than rounded up on purpose — the point is
# that the next feature which tries to add 3k to the always-loaded budget trips
# the gate on its first attempt, which is what the previous split (93k moved out,
# 5,752 chars back within two feature commits) had no way to do.
ROOT_BUDGET = 31_457
# Per rule file, and flat rather than ratcheted because #59 fixes the number. Well
# inside the tooling's own limit — 4 MiB, confirmed on this build in #61 — so this is
# repo policy, not a loader constraint, which is the right way round. Note the units
# differ and the comparison survives it: the loader counts BYTES, these budgets count
# CHARACTERS, and a character is never fewer than one byte.
RULE_BUDGET = 60_000

# Check 6's pins: modules whose rule is in the root while a rule file's globs already
# reach them, spelled with the ticket that owns the residue. EMPTY, and that is the
# point — it held `services/case_export.py` and `services/case_workspace.py` until #76
# moved the export rules into `pipeline-case.md`, and the staleness half of check 6 is
# what made those pins fail the moment they stopped being violations rather than
# quietly outliving the defect. A new entry belongs here only with the ticket that owns
# it, and only until that ticket lands. It enters through `read_world()` rather than
# being read from the check, so a pin is an INPUT like every other and the injection
# mutates a copy of the world instead of passing an argument past it.
KNOWN_RESIDUE = {}

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
    notes = {}
    notes_dir = os.path.join(_REPO, _NOTES_DIR)
    if os.path.isdir(notes_dir):
        for name in sorted(os.listdir(notes_dir)):
            if name.endswith(".md"):
                with open(os.path.join(notes_dir, name), encoding="utf-8") as fh:
                    notes[name] = fh.read()
    return {"root": root_text, "rules": rules, "notes": notes,
            "pins": dict(KNOWN_RESIDUE), "tests": collect_test_files()}


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


def tripwire_span(root_text):
    """(first, last) line indices of the anchored tripwire region, or None.

    One walk, two callers: check 2 reads the rows, check 6 excludes them. The region
    runs from the anchor to the first non-row line AFTER the table has begun, so the
    anchor's own remaining comment lines and the blank line between are inside it.
    """
    lines = root_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith(TRIPWIRE_ANCHOR):
            start = i
            break
    if start is None:
        return None
    seen_table = False
    for j in range(start + 1, len(lines)):
        if lines[j].lstrip().startswith("|"):
            seen_table = True
            continue
        if seen_table:
            return (start, j - 1)
    return (start, len(lines) - 1)


def tripwire_rows(root_text):
    """Rule-file names named by a row of the tripwire table.

    Returns None when the anchor is missing — distinct from "the table names
    nothing", so the caller can report the two differently.
    """
    span = tripwire_span(root_text)
    if span is None:
        return None
    lines = root_text.splitlines()
    named = []
    for line in lines[span[0]:span[1] + 1]:
        if line.lstrip().startswith("|"):
            for m in _RULE_REF.finditer(line):
                named.append(m.group(1))
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


# --- shared by checks 5 and 6 ------------------------------------------------------------------
_GUI_PKG = "(?:services|models|views|controllers|commands|workers)"
# The SHORT form a rule uses when speaking about its own area — `services/foo.py`,
# `app/services/foo.py`, `views/panels/foo.py`. Deliberately NOT the full repo-relative
# path, which is the form `## Common Tasks` uses for wayfinding ("Edit
# tools/PreProcessor/gui/app/views/canvas.py") rather than for ruling on a file.
_GUI_MODULE = re.compile(r"`(?:app/)?(" + _GUI_PKG + r"/[A-Za-z0-9_]+(?:/[A-Za-z0-9_]+)*\.py)`")
_GUI_ROOT = os.path.join("tools", "PreProcessor", "gui", "app")

def _glob_matches(path, pattern):
    """Does one `paths:` entry match a repo-relative path?

    `fnmatch` has no `**`, so `a/**` is normalised to `a/*` and `*` is allowed to cross
    `/`. That is LOOSER than the loader for a pattern like `a/*/b`, and named as a blind
    spot rather than papered over: every pattern in this repo is a prefix glob or a
    literal, where the two agree.
    """
    return fnmatch.fnmatch(path, pattern.replace("**", "*"))


# --- check 5 ------------------------------------------------------------------
# The inverse of check 6, and the defect #76 was: the RULES arrive in a rule file
# while their RATIONALE stays in the design note of the area they came from. The rule
# file carries ONE note pointer in its header, so that pointer then lies about part of
# its own contents, and nothing about either file looks wrong from inside it.
_NOTE_PTR = re.compile(r"docs/design_notes/([A-Za-z0-9_.-]+\.md)")
# A bare backticked basename — the form the export rules use for `case_export_docs.py`
# and `case_export_usage.py`, which is why check 6 cannot see those two (blind spot
# (e)). Resolved against the GUI package and accepted only when the basename is
# UNIQUE there, so `__init__.py` and the two `*field_specs.py` pairs resolve to
# nothing rather than to a guess.
_BARE_MODULE = re.compile(r"`([A-Za-z0-9_]+\.py)`")


_BASENAME_INDEX = None


def _gui_basename_index():
    """basename -> repo-relative-in-package path, for basenames that are unique.

    Walked once and cached: `rule_owned_modules` is called per rule file, and the first
    version re-walked all 258 GUI modules eight times per run for an answer that cannot
    change inside one run.
    """
    global _BASENAME_INDEX
    if _BASENAME_INDEX is not None:
        return _BASENAME_INDEX
    seen = {}
    root = os.path.join(_REPO, _GUI_ROOT)
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn.endswith(".py"):
                rel = os.path.relpath(os.path.join(dirpath, fn), root).replace(os.sep, "/")
                seen.setdefault(fn, []).append(rel)
    _BASENAME_INDEX = {k: v[0] for k, v in seen.items() if len(v) == 1}
    return _BASENAME_INDEX


def note_pointer(text):
    """The design note a rule file's header sends its reader to, or None.

    The FIRST mention rather than a scan of all of them: every rule file here names
    exactly one note (measured), and taking the set would let a passing cross-reference
    to another area's note satisfy the check.
    """
    m = _NOTE_PTR.search(text)
    return m.group(1) if m else None


def rule_owned_modules(world, name, text):
    """Modules a rule file names that its OWN globs claim by filename.

    A glob whose last component is `**` or `*` claims a whole directory rather than a
    file, and rule files use those to reach an area they then hand off — `views/panels/**`
    reaches `restart_chooser.py`, whose rules are in `pipeline-case.md`, and
    `tools/PreProcessor/gui/**` reaches everything. Counting those as ownership fails 3
    legitimate cross-area pointers today, measured, and 8 if ownership is dropped
    altogether (the ladder is in the check list above). A glob that
    constrains the FILENAME (`services/case_*`, `views/canvas*`) is the rule file saying
    the file is its own, and that is what this check reads.
    """
    idx = _gui_basename_index()
    named = set(_GUI_MODULE.findall(text))
    for base in _BARE_MODULE.findall(text):
        if base in idx:
            named.add(idx[base])
    owned = {}
    for rel in sorted(named):
        if not os.path.exists(os.path.join(_REPO, _GUI_ROOT, rel)):
            continue
        full = os.path.join(_GUI_ROOT, rel).replace(os.sep, "/")
        for pat in frontmatter_paths(text) or []:
            last = pat.rstrip("/").split("/")[-1]
            if last in ("**", "**/*", "*"):
                continue
            if _glob_matches(full, pat):
                owned[rel] = pat
                break
    return owned


def check_note_coverage(world):
    fails = []
    for name, text in sorted(world["rules"].items()):
        note = note_pointer(text)
        if note is None:
            continue
        if note not in world["notes"]:
            fails.append(
                "%s/%s points its reader at %s/%s, which does not exist. A rule whose "
                "rationale cannot be found is a rule nobody can overrule with evidence."
                % (_RULES_DIR, name, _NOTES_DIR, note))
            continue
        for rel, pat in sorted(rule_owned_modules(world, name, text).items()):
            base = os.path.basename(rel)
            if base in world["notes"][note]:
                continue
            elsewhere = sorted(n for n, tx in world["notes"].items() if base in tx)
            if not elsewhere:
                continue
            fails.append(
                "%s/%s rules on `%s` (its own glob `%s` claims it) and points its reader at "
                "%s/%s, which never names that module — %s does. Either the rationale belongs "
                "in %s and did not travel with the rule, or the rule is in the wrong rule "
                "file."
                % (_RULES_DIR, name, rel, pat, _NOTES_DIR, note,
                   ", ".join("%s/%s" % (_NOTES_DIR, n) for n in elsewhere), note))
    return fails


# --- check 6 ------------------------------------------------------------------
def rule_files_reaching(world, path):
    hit = []
    for name, text in sorted(world["rules"].items()):
        for pat in frontmatter_paths(text) or []:
            if _glob_matches(path, pat):
                hit.append(name)
                break
    return hit


def root_ruled_modules(world):
    """GUI modules the ROOT names OUTSIDE the anchored tripwire region.

    Inside that region a module path is the table doing its job — telling a reader which
    files a rule file covers — so those are not rules and are excluded by region, not by
    an exemption list.
    """
    span = tripwire_span(world["root"])
    lines = world["root"].splitlines()
    if span is not None:
        lines = lines[:span[0]] + lines[span[1] + 1:]
    found = {}
    for m in _GUI_MODULE.finditer("\n".join(lines)):
        rel = m.group(1)
        if os.path.exists(os.path.join(_REPO, _GUI_ROOT, rel)):
            found.setdefault(rel, os.path.join(_GUI_ROOT, rel).replace(os.sep, "/"))
    return found


def check_root_rule_coverage(world):
    pins = world["pins"]
    fails = []
    found = root_ruled_modules(world)
    live = set()
    for rel, path in sorted(found.items()):
        reaching = rule_files_reaching(world, path)
        if not reaching:
            continue
        live.add(rel)
        if rel in pins:
            continue
        fails.append(
            "%s rules on `%s`, but %s already reach that file by their globs. The rule "
            "and the glob then point at different layers: a session that READS it is "
            "handed a rule file that is silent about it, and nothing says so. Move the "
            "rule into %s, or — if the mention is wayfinding rather than a rule — put it "
            "inside the tripwire table."
            % (_ROOT_NAME, rel, ", ".join("%s/%s" % (_RULES_DIR, r) for r in reaching),
               reaching[0]))
    for rel, ticket in sorted(pins.items()):
        if rel not in live:
            fails.append(
                "KNOWN_RESIDUE pins `%s` (%s), but that is no longer a violation — either "
                "the rule left %s or no rule file's globs reach the module any more. Delete "
                "the entry; a pin that outlives its defect is the skip list this check was "
                "written instead of." % (rel, ticket, _ROOT_NAME))
    return fails


# =============================================================================
world = read_world()

check(bool(world["rules"]),
      "check 0. .claude/rules/ holds at least one rule file (nothing below can bite on "
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
    "check 1. every instruction file is within its OWN per-file budget (root %d, each rule "
    "file %d, in characters)" % (ROOT_BUDGET, RULE_BUDGET))
run(check_tripwire,
    "check 2. the tripwire table and the rule files agree in BOTH directions")
run(check_gate_names,
    "check 3. every gate-test filename named in a rule file — or in the root — exists on disk")
run(check_paths_frontmatter,
    "check 4. every rule file's `paths:` is present, non-empty and not only `**`")
run(check_note_coverage,
    "check 5. every rule file's design-note pointer resolves, and names every module the "
    "rule file's own globs claim by filename that some other design note discusses")

run(check_root_rule_coverage,
    "check 6. no rule in the root names a GUI module some rule file's globs already reach, "
    "and every KNOWN_RESIDUE pin is still a real violation")


# --- injections ---------------------------------------------------------------
# Each mutates a COPY of the inputs, asserts the check then fails, and asserts
# the mutation is still well-formed and really differs — an injection that merely
# corrupts its input looks identical to the check working.
def copy_world(w):
    return {"root": w["root"], "rules": dict(w["rules"]), "notes": dict(w["notes"]),
            "pins": dict(w["pins"]), "tests": set(w["tests"])}


# 5. an oversized file
inj = copy_world(world)
pad = ROOT_BUDGET - len(inj["root"]) + 1
inj["root"] = inj["root"] + "\n" + ("padding. " * ((pad // 9) + 2))
check(inj["root"] != world["root"] and inj["root"].startswith("# " + _ROOT_NAME)
      and len(inj["root"]) > ROOT_BUDGET,
      "injection 5. injection is well-formed: the padded root still opens with its own "
      "heading, really differs, and is genuinely over budget")
sz = check_sizes(inj)
check(len(sz) == 1 and _ROOT_NAME in sz[0] and str(ROOT_BUDGET) in sz[0]
      and str(len(inj["root"])) in sz[0]
      and "docs/design_notes/mesher.md" in sz[0],
      "injection 5. check 1 fails on it, naming the file, its size, its budget and a CONCRETE "
      "destination — a `docs/design_notes/*.md` glob passed this assertion once and "
      "is not a place anything can be put")

# A rule file over budget is the other half of check 1, and it must NOT be
# excusable by the root being small: the budget is per file, never a total.
inj = copy_world(world)
victim = sorted(inj["rules"])[0]
inj["rules"][victim] = inj["rules"][victim] + ("x" * (RULE_BUDGET + 1))
check(frontmatter_paths(inj["rules"][victim]) == frontmatter_paths(world["rules"][victim])
      and len(inj["rules"][victim]) > RULE_BUDGET,
      "injection 5b. injection is well-formed: the padded rule file keeps its frontmatter "
      "and really is over budget")
sz = check_sizes(inj)
check(len(sz) == 1 and victim in sz[0]
      and design_note_for(victim) in sz[0]
      and design_note_for(victim) != design_note_for(_ROOT_NAME),
      "injection 5b. check 1 fails on the RULE file even though the root is inside its own "
      "budget — per-file, never a total — and names that AREA's own design note "
      "rather than the root's fallback")

# 6. a rule file that no tripwire row names
inj = copy_world(world)
phantom = "zz-phantom-area.md"
inj["rules"][phantom] = "---\npaths:\n  - src/Phantom.cpp\n---\n\nA rule.\n"
check(phantom not in tripwire_rows(inj["root"])
      and frontmatter_paths(inj["rules"][phantom]) == ["src/Phantom.cpp"]
      and set(inj["rules"]) != set(world["rules"]),
      "injection 6. injection is well-formed: the phantom rule file has a valid, narrow "
      "`paths:` glob — it looks perfectly healthy from inside itself")
tw = check_tripwire(inj)
check(len(tw) == 1 and phantom in tw[0] and "NO tripwire row" in tw[0],
      "injection 6. check 2 fails in the on-disk-but-unnamed direction")

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
check(len(rows) >= 1, "injection 7. the tripwire table has a row to insert after")
inj["root"] = inj["root"].replace(
    rows[0] + "\n",
    rows[0] + "\n| Nonexistent area | `.claude/rules/nope.md` | `src/**` |\n")
after = tripwire_rows(inj["root"])
check(len(after) == before + 1 and "nope.md" in after
      and inj["root"] != world["root"],
      "injection 7. injection is well-formed: the added line really parses as one more "
      "tripwire row")
tw = check_tripwire(inj)
check(len(tw) == 1 and "nope.md" in tw[0] and "does not exist" in tw[0],
      "injection 7. check 2 fails in the named-but-absent direction too — one direction "
      "alone is blind")

# 8. a renamed gate filename
inj = copy_world(world)
victim = None
for name, text in sorted(inj["rules"].items()):
    hits = sorted(set(_GATE_REF.findall(text)))
    if hits:
        victim, gate = name, hits[0]
        break
check(victim is not None, "injection 8. at least one rule file names a gate test to rename")
if victim is not None:
    renamed = gate.replace("test_", "test_renamed_", 1)
    inj["rules"][victim] = inj["rules"][victim].replace(gate, renamed)
    check(inj["rules"][victim] != world["rules"][victim]
          and renamed not in inj["tests"]
          and frontmatter_paths(inj["rules"][victim]) is not None,
          "injection 8. injection is well-formed: the rule file keeps its frontmatter, "
          "really differs, and the new name is on no path in the tree")
    gn = check_gate_names(inj)
    check(any(renamed in f for f in gn),
          "injection 8. check 3 fails on it — a compression pass that drops or mistypes a "
          "gate name cannot pass silently")

# ...and the same in the ROOT file, which is where most rules still are.
inj = copy_world(world)
root_gates = sorted(set(_GATE_REF.findall(inj["root"])))
check(bool(root_gates), "injection 8b. the root file names at least one gate test")
if root_gates:
    renamed = root_gates[0].replace("test_", "test_renamed_", 1)
    inj["root"] = inj["root"].replace(root_gates[0], renamed)
    check(inj["root"] != world["root"] and renamed not in inj["tests"]
          and inj["root"].startswith("# " + _ROOT_NAME),
          "injection 8b. injection is well-formed: the root really differs, still opens with "
          "its own heading, and the new name is on no path in the tree")
    gn = check_gate_names(inj)
    check(any(renamed in f and _ROOT_NAME in f for f in gn),
          "injection 8b. check 3 covers the root file too, so a gate name cannot be lost in "
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
      "injection 9. the real rule file being mutated has a multi-entry `paths:` list and a "
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
          "injection 9. injection is well-formed: the %r mutation keeps the real rule file's "
          "whole body, really differs from it, and changes only the `paths:` list"
          % label)
    pf = check_paths_frontmatter(inj)
    check(len(pf) == 1 and victim in pf[0],
          "injection 9. check 4 refuses `paths:` %r, which the loader would silently turn "
          "into an always-loaded file" % label)
check(not check_paths_frontmatter(world),
      "injection 9. negative control: the real, unmutated rule set passes check 4, so the "
      "four failures above are the mutation and not the checker")

# 10. the tripwire anchor removed. A missing anchor must FAIL rather than fall back
# to scanning every table in the root file — the fallback is the looseness the
# anchor replaced, and it would be silent.
inj = copy_world(world)
lines = inj["root"].splitlines(keepends=True)
at = [i for i, ln in enumerate(lines) if ln.lstrip().startswith(TRIPWIRE_ANCHOR)]
check(len(at) == 1, "injection 10. the root file carries exactly one tripwire anchor")
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
      "injection 10. injection is well-formed: the whole anchor comment is gone with no "
      "dangling delimiter, the table and every rule-file mention are untouched, and "
      "the rows really stop resolving")
tw = check_tripwire(inj)
check(len(tw) == 1 and TRIPWIRE_ANCHOR in tw[0],
      "injection 10. check 2 fails naming the anchor, instead of quietly accepting a "
      "rule-file mention from any table in the file")

# --- injection 11: check 6, the defect it exists to find -----------------------
# Put one of #77's moved rules back into the root. The module is reached by two rule
# files' globs and neither carries the rule any more, which is precisely the split-layer
# state this check refuses.
inj = copy_world(world)
victim_mod = "services/ui_state.py"
check(victim_mod not in root_ruled_modules(world),
      "injection 11. fixture: the root does not already rule on the module, so the "
      "mutation is what makes check 6 fire")
inj["root"] = inj["root"].replace(
    "## Mesh Generation Pipeline",
    "**Window layout** is persisted by `app/%s` and nothing else.\n\n## Mesh Generation Pipeline"
    % victim_mod, 1)
check(inj["root"] != world["root"]
      and tripwire_rows(inj["root"]) == tripwire_rows(world["root"])
      and tripwire_span(inj["root"]) == tripwire_span(world["root"])
      and victim_mod in root_ruled_modules(inj)
      and victim_mod not in root_ruled_modules(world),
      "injection 11. injection is well-formed: the root really differs, its anchored table is "
      "byte-for-byte where it was, and the module is newly ruled on OUTSIDE it")
cov = check_root_rule_coverage(inj)
check(len(cov) == 1 and victim_mod in cov[0]
      and "gui-lifecycle.md" in cov[0] and _ROOT_NAME in cov[0],
      "injection 11. check 6 fails naming the module and the rule files that reach it — a rule "
      "split across two layers cannot pass silently")

# --- injection 11b: the ANCHORED REGION is what excludes the table -------------
# The mutation #77 specifies: take a module path OUT of a tripwire cell and put the
# identical string in ordinary prose. If the check read the whole file it could not tell
# the two placements apart, and the tripwire table — whose whole job is naming each area's
# files — would be a permanent failure.
inj = copy_world(world)
moved_mod = "models/segment.py"
span = tripwire_span(inj["root"])
lines = inj["root"].splitlines(keepends=True)
inside = "".join(lines[span[0]:span[1] + 1])
check(("`%s`" % moved_mod) in inside and moved_mod not in root_ruled_modules(world),
      "injection 11b. fixture: the path is named INSIDE the anchored region and check 6 "
      "does not see it there — which is the behaviour under test")
lines[span[0]:span[1] + 1] = [ln.replace("`%s`" % moved_mod, "the segment model")
                              for ln in lines[span[0]:span[1] + 1]]
inj["root"] = "".join(lines) + "\nThe hand-off rules on `%s`.\n" % moved_mod
check(inj["root"] != world["root"]
      and ("`%s`" % moved_mod) not in "".join(inj["root"].splitlines(keepends=True)
                                              [span[0]:span[1] + 1])
      and tripwire_rows(inj["root"]) == tripwire_rows(world["root"])
      and tripwire_span(inj["root"]) == span,
      "injection 11b. injection is well-formed: the path really left the region, every row "
      "still names the same rule files, and the region is the same span")
cov = check_root_rule_coverage(inj)
check(len(cov) == 1 and moved_mod in cov[0] and "gui-handoff.md" in cov[0],
      "injection 11b. check 6 reads the ANCHORED REGION, not the whole file: one identical "
      "path passes inside the table and fails outside it")

# --- injection 11c: a pin suppresses, and a stale pin fails ---------------------
# KNOWN_RESIDUE is empty since #76 landed, so the mutation can no longer be "unpin a real
# violation": there is nothing pinned to unpin. The pins arrive in the world instead, so
# this injection adds them to a COPY like every other injection here — a pin that IS a
# real violation must suppress, and a pin that is not one must fail. Without the second
# half a pin would be the skip list this check was written instead of.
inj = copy_world(world)
check(inj["pins"] == {} and world["pins"] == {},
      "injection 11c. fixture: the world carries no pins, so both halves below are this "
      "injection's own doing (#76 moved the two entries' rules into pipeline-case.md)")
pinned_mod = "services/ui_state.py"
inj["root"] = inj["root"].replace(
    "## Mesh Generation Pipeline",
    "**Window layout** is persisted by `app/%s` and nothing else.\n\n## Mesh Generation Pipeline"
    % pinned_mod, 1)
check(pinned_mod in root_ruled_modules(inj)
      and rule_files_reaching(inj, "%s/%s" % (_GUI_ROOT, pinned_mod))
      and len(check_root_rule_coverage(inj)) == 1,
      "injection 11c. injection is well-formed: the module is really ruled on in the root, "
      "really reached by a rule file's globs, and fails check 6 while unpinned")
inj["pins"] = {pinned_mod: "#0000"}
check(not check_root_rule_coverage(inj),
      "injection 11c. a pin on a REAL violation suppresses it, which is what a pin is for")
stale_mod = "services/env_setup.py"
check(stale_mod not in root_ruled_modules(inj),
      "injection 11c. fixture: the second pin names a module the root does NOT rule on")
inj["pins"] = {pinned_mod: "#0000", stale_mod: "#0001"}
cov = check_root_rule_coverage(inj)
check(len(cov) == 1 and stale_mod in cov[0] and "no longer a violation" in cov[0],
      "injection 11c. check 6 fails on the pin that is no longer a violation, so a pin cannot "
      "outlive the defect it records")

# --- injection 11d: negative control -------------------------------------------
check(not check_root_rule_coverage(world),
      "injection 11d. negative control: the real, unmutated world passes check 6, so the three "
      "failures above are the mutation and not the checker")

# --- injection 12: check 5, the defect #76 was ---------------------------------
# Reproduce the state this ticket ended: the export RULES in `pipeline-case.md`, their
# RATIONALE still in `gui.md`. Built by moving the note text back rather than by deleting
# it, so the mutated world is the real pre-#76 document pair and not a damaged one.
inj = copy_world(world)
_ptr = "**Portable case export**"
# The section heading is #76's own addition to the note (the two blocks are contiguous
# prose in `gui.md`), so it is a fixture on this ticket's structure rather than on the
# note's wording — rename it in `pipeline.md` and this string moves with it.
_SECTION = "### The case as a package"
_pipe = inj["notes"]["pipeline.md"]
# From the SECTION HEADING, not from the first paragraph: the heading #76 added names
# `services/case_workspace.py` itself, so leaving it behind would keep that module named
# in pipeline.md and the injection would bite on two of the three modules while looking
# like the check missing one.
_head_i = _pipe.find(_SECTION)
_start_i = _pipe.find(_ptr, _head_i if _head_i >= 0 else 0)
# The section ends at the NEXT heading, not at a sentence: pinning its closing words here
# would make this injection a second place that has to be edited when the note is
# reworded, which is the wording-dependence the whole file refuses.
_end_i = _pipe.find("\n### ", _start_i)
check(_head_i > 0 and _start_i > _head_i and _end_i > _start_i,
      "injection 12. fixture: pipeline.md carries the export rationale as one contiguous "
      "section, heading included, ending at the next heading")
_block = _pipe[_start_i:_end_i]
inj["notes"]["pipeline.md"] = _pipe[:_head_i] + _pipe[_end_i + 1:]
inj["notes"]["gui.md"] = inj["notes"]["gui.md"].rstrip("\n") + "\n\n" + _block + "\n"
_moved = ["case_export_docs.py", "case_export_usage.py", "case_workspace.py"]
check(inj["notes"]["pipeline.md"] != world["notes"]["pipeline.md"]
      and inj["notes"]["gui.md"] != world["notes"]["gui.md"]
      and inj["rules"] == world["rules"]
      and all(m not in inj["notes"]["pipeline.md"] and m in inj["notes"]["gui.md"]
              for m in _moved)
      and (inj["notes"]["pipeline.md"].splitlines()[0]
           == world["notes"]["pipeline.md"].splitlines()[0]),
      "injection 12. injection is well-formed: both notes really differ, the RULE files are "
      "untouched, each moved module is now named in gui.md and in NEITHER of pipeline.md's "
      "remaining text, and the emptied note still opens as itself")
nc = check_note_coverage(inj)
check(len(nc) == 3
      and all(any(m in f for f in nc) for m in _moved)
      and all("pipeline-case.md" in f and "pipeline.md" in f and "gui.md" in f for f in nc),
      "injection 12. check 5 fails on every module whose rationale stayed behind, naming the "
      "rule file, the note it points at and the note the module is actually named in")

# --- injection 12b: the POINTER is what is read, not a hardcoded area ----------
inj = copy_world(world)
victim = "pipeline-case.md"
check(note_pointer(inj["rules"][victim]) == "pipeline.md",
      "injection 12b. fixture: the rule file points at its own area's note")
inj["rules"][victim] = inj["rules"][victim].replace(
    "docs/design_notes/pipeline.md", "docs/design_notes/mesher.md", 1)
check(inj["rules"][victim] != world["rules"][victim]
      and note_pointer(inj["rules"][victim]) == "mesher.md"
      and frontmatter_paths(inj["rules"][victim]) == frontmatter_paths(world["rules"][victim])
      and rule_owned_modules(inj, victim, inj["rules"][victim])
      == rule_owned_modules(world, victim, world["rules"][victim]),
      "injection 12b. injection is well-formed: only the pointer moved — the globs and the "
      "modules the file claims are identical")
nc = check_note_coverage(inj)
check(nc and all("mesher.md" in f for f in nc)
      and any("case_export" in f for f in nc),
      "injection 12b. check 5 follows the rule file's own pointer rather than an area-to-note "
      "mapping baked in here: repointing it at a note that discusses none of its modules fails")

# --- injection 12c: a pointer that resolves to nothing --------------------------
inj = copy_world(world)
inj["rules"][victim] = inj["rules"][victim].replace(
    "docs/design_notes/pipeline.md", "docs/design_notes/nope.md", 1)
check(note_pointer(inj["rules"][victim]) == "nope.md" and "nope.md" not in inj["notes"],
      "injection 12c. injection is well-formed: the pointer names a note that is on no path")
nc = check_note_coverage(inj)
check(len(nc) == 1 and "nope.md" in nc[0] and victim in nc[0],
      "injection 12c. check 5 fails when the rationale pointer resolves to nothing")

# --- injection 12d: negative control -------------------------------------------
check(not check_note_coverage(world),
      "injection 12d. negative control: the real, unmutated world passes check 5, so the five "
      "failures above are the mutation and not the checker")

print(("\nRESULT: " + ("ALL PASS" if not _FAILS else f"{len(_FAILS)} FAIL")), flush=True)
sys.exit(1 if _FAILS else 0)
