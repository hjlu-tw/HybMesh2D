#!/usr/bin/env python3
"""The GUI file-length standard, gated.

CLAUDE.md names four standards that bind before any file is opened. Three of them
already fail the build when they are crossed — a silent `except`, a raw
`blockSignals` pair, a mesh key that disagrees across the GUI/C++ seam. The
fourth, *keep each file under `tools/PreProcessor/gui/` at ~500 lines*, had no
gate at all, and was crossed four times: #91 once, and #47's merge twice more
(`mesh_gen_ctrl` 490 → 512, `pipeline_runner` 498 → 506) while worsening a third
(`pipeline_config` 523 → 524). Every one of those was caught by a human reading a
diff, which is to say the standard was enforced whenever somebody happened to
look. That merge demonstrably KNEW the rule — it split `mesh_config` 505 → 426
for exactly this budget in the same change — so the failure is inconsistency, not
ignorance, and inconsistency is the signature of a rule nothing enforces.

There is no production code behind this gate: the thing under test is a line
count off disk. It imports no application module and constructs no widget, so it
needs neither Qt nor a build tree, and it runs in CI's **lint** job as well as in
`run_all.sh`.

Checks:
 1. Every `.py` file under `tools/PreProcessor/gui/` is within the standard, or is
    pinned in `PINS` at the size it was when this gate landed. The failure names
    the file, its current length and its overage, and EVERY offender is reported
    in one run — one run tells a developer the whole job rather than its first
    item.

`PINS` is self-invalidating in BOTH directions, which is what separates it from a
skip list:

  * a pinned file that grows FURTHER fails — already being over the limit is not a
    licence, and the pin is a ceiling rather than an exemption;
  * a pinned file that drops back under the limit fails as an obsolete pin — the
    allowance cannot outlive its reason.

That is deliberately the same shape as `test_instruction_budget.py`'s
`KNOWN_RESIDUE`, whose entries fail the moment they stop being violations. The
mechanism is established in this repo and is reused here rather than reinvented.

Injections. Every behaviour above is proved non-vacuous by constructing the
condition, asserting the mutation really differs from the real tree, and then
asserting the check reports it — plus a negative control on the real, unmutated
tree, so a green run cannot be the checker being inert. The two END-TO-END
injections read the verdict from a child process's **exit code**, never from a
count of FAIL lines in its output: a crashed injection prints no FAIL lines at
all, and this repo has previously scored exactly that as a bite that never
happened. The in-process injections cannot be mis-scored the same way, because a
crash inside one propagates and takes this process's exit status with it.

Known blind spots, stated rather than pretended away:

 a. A pin is a CEILING, not a fixed measurement. A pinned file that shrinks while
    staying over the limit passes, and may then grow back to its pin without the
    gate speaking. That is deliberate: #102 and #103 split two of these files, and
    an exact-match pin would go red on every intermediate commit of the very work
    it exists to provoke. The hole is bounded by the pin, which never rises.
 b. It counts LINES, which is a proxy. A 400-line file can be far worse than a
    510-line one, and nothing here can tell. The standard is a splitting
    instruction with a number attached, and this gate enforces the number.
 c. It reaches `.py` files only. The GUI directory also holds `.json`, `.md` and
    Qt translation sources; the standard is about the code.

Run:  python3 tools/PreProcessor/tests/test_file_length.py
      python3 tools/PreProcessor/tests/test_file_length.py --scan-only
        the disk scan alone, no injections — the mode the end-to-end injections
        below run in a child process, so that running the gate cannot recurse
        into spawning another copy of itself.
"""
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI_REL = os.path.join("tools", "PreProcessor", "gui")
_GUI = os.path.join(_REPO, _GUI_REL)

# The standard, verbatim from CLAUDE.md: "Keep each file under
# `tools/PreProcessor/gui/` at ~500 lines; split it when it grows past."
LIMIT = 500

# Directories that hold no source of ours.
_SKIP_DIRS = {"__pycache__", ".ruff_cache", ".git", ".mypy_cache", ".pytest_cache"}

# The files that were already over the limit when this gate landed (2026-09-09),
# pinned at their measured lengths so the gate can be green today without
# pretending they comply. Each carries the ticket that owns getting it back under,
# where one exists. This is a grandfather list, not a pressure valve: a file that
# is NOT here has to be split, and an entry that stops being a violation FAILS
# rather than quietly outliving the defect.
PINS = {
    "app/models/pipeline_config.py": 524,        # worst of the seven
    "app/controllers/mesh_gen_ctrl.py": 512,     # #102 splits it
    "app/services/case_run_note.py": 508,
    "app/controllers/session_io_ctrl.py": 508,
    "app/services/pipeline_runner.py": 506,      # #103 splits it
    "app/services/result_legs.py": 501,
    "app/models/solver_config.py": 501,
}

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


# --- the inputs, as one value -------------------------------------------------
# The check is a pure function of this dict, which is what makes the injections
# below cheap: mutate a copy, ask the same function.
def measure(root):
    """{relative path: line count} for every .py file under `root`.

    Lines are counted with `splitlines()` rather than by counting newlines, so a
    file with no trailing newline is not silently one line short of its real size.
    """
    lengths = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            lengths[rel] = len(text.splitlines())
    return lengths


def read_world():
    return {"lengths": measure(_GUI), "pins": dict(PINS)}


def check_lengths(world):
    """Every failure, never just the first — one run tells the whole job."""
    lengths = world["lengths"]
    pins = world["pins"]
    fails = []
    for rel in sorted(lengths):
        length = lengths[rel]
        if rel in pins:
            continue
        if length > LIMIT:
            fails.append(
                "%s/%s is %d lines, %d over the ~%d-line standard. Split it. `PINS` "
                "grandfathers only the files that predate this gate and is not a place "
                "to put a new one."
                % (_GUI_REL, rel, length, length - LIMIT, LIMIT))
    for rel in sorted(pins):
        pinned = pins[rel]
        if rel not in lengths:
            fails.append(
                "PINS pins `%s` at %d lines, but there is no such file under %s/. "
                "Delete the entry, or fix its path — a pin nothing measures is a pin "
                "that cannot fail."
                % (rel, pinned, _GUI_REL))
            continue
        length = lengths[rel]
        if length > pinned:
            fails.append(
                "%s/%s is pinned at %d lines and is now %d — %d MORE. Already being "
                "over the limit is not a licence to grow: the pin is a ceiling, not an "
                "exemption."
                % (_GUI_REL, rel, pinned, length, length - pinned))
        elif length <= LIMIT:
            fails.append(
                "PINS pins `%s` at %d lines, but it is now %d — inside the ~%d-line "
                "standard. Delete the entry; an allowance that outlives its reason is "
                "the skip list this list was written instead of."
                % (rel, pinned, length, LIMIT))
    return fails


def run(fn, world, msg):
    """Evaluate the check ONCE, print each failure, then record the verdict."""
    fails = fn(world)
    for fail in fails:
        print("     -> " + fail, flush=True)
    check(not fails, msg)


world = read_world()

# --- --scan-only: the disk scan alone -----------------------------------------
# The end-to-end injections below run the gate in a child process to read its
# EXIT CODE. Without this mode that child would run the injections too, and would
# spawn a child of its own, forever.
if "--scan-only" in sys.argv[1:]:
    run(check_lengths, world,
        "check 1. every GUI .py file is inside the ~%d-line standard or pinned at the "
        "size it had when this gate landed (%d files scanned, %d pinned)"
        % (LIMIT, len(world["lengths"]), len(world["pins"])))
    sys.exit(1 if _FAILS else 0)

run(check_lengths, world,
    "check 1. every GUI .py file is inside the ~%d-line standard or pinned at the size "
    "it had when this gate landed (%d files scanned, %d pinned)"
    % (LIMIT, len(world["lengths"]), len(world["pins"])))

# The standard binds the GUI package, so a gate that scanned an empty tree would
# pass every mutation below by finding nothing at all.
check(len(world["lengths"]) > 200,
      "check 1. ...and the scan really reached the GUI package (%d .py files; an empty "
      "walk would pass everything below)" % len(world["lengths"]))


# --- injections ---------------------------------------------------------------
# Each mutates a COPY of the inputs, asserts the mutation is well-formed and
# really differs, then asserts the check reports it. A crash inside one of these
# propagates and takes this process's exit status with it, so an injection that
# died cannot be read as an injection that bit.
def copy_world(w):
    return {"lengths": dict(w["lengths"]), "pins": dict(w["pins"])}


NEW = "app/controllers/injected_ctrl.py"

# 1. a new file taken past the limit
inj = copy_world(world)
inj["lengths"][NEW] = LIMIT + 37
check(NEW not in world["lengths"] and inj["lengths"][NEW] > LIMIT
      and inj["lengths"] != world["lengths"],
      "injection 1. injection is well-formed: the file is not in the real tree, really "
      "is over the limit, and the world really differs")
f = check_lengths(inj)
check(len(f) == 1 and NEW in f[0] and str(LIMIT + 37) in f[0] and " 37 over" in f[0],
      "injection 1. check 1 fails on it, naming the FILE, its LENGTH and its OVERAGE — "
      "the three things that make the fix obvious without re-measuring anything")

# 1b. exactly at the limit is inside the standard; one past it is not.
inj = copy_world(world)
inj["lengths"][NEW] = LIMIT
check(not check_lengths(inj),
      "injection 1b. a file of exactly %d lines passes — the boundary is `> %d`, not "
      "`>= %d`" % (LIMIT, LIMIT, LIMIT))
inj["lengths"][NEW] = LIMIT + 1
check(len(check_lengths(inj)) == 1,
      "injection 1b. ...and one line past it fails, so the boundary is where the "
      "standard puts it")

# 2. EVERY offender in one run, not just the first
inj = copy_world(world)
extra = {"app/views/injected_a.py": LIMIT + 1,
         "app/services/injected_b.py": LIMIT + 200,
         "app/models/injected_c.py": LIMIT + 4}
inj["lengths"].update(extra)
check(all(k not in world["lengths"] for k in extra) and len(inj["lengths"])
      == len(world["lengths"]) + 3,
      "injection 2. injection is well-formed: three files that are not in the real tree "
      "were really added")
f = check_lengths(inj)
check(len(f) == 3 and all(any(k in line for line in f) for k in extra),
      "injection 2. all THREE are reported in one run — stopping at the first would "
      "make a developer re-run the gate once per offender")

# 3. a pinned file that grows FURTHER
victim = "app/models/pipeline_config.py"
inj = copy_world(world)
check(victim in world["pins"] and world["lengths"].get(victim) == world["pins"][victim],
      "injection 3. injection is well-formed: `%s` really is pinned, at the size it "
      "really has on disk" % victim)
inj["lengths"][victim] = world["pins"][victim] + 9
f = check_lengths(inj)
check(len(f) == 1 and victim in f[0] and "9 MORE" in f[0] and "licence" in f[0],
      "injection 3. check 1 fails on a pinned file that GREW — already over the limit "
      "is not a licence, and the pin is a ceiling")

# 4. a pinned file that drops back under the limit — an obsolete pin
inj = copy_world(world)
inj["lengths"][victim] = LIMIT - 60
check(inj["lengths"][victim] <= LIMIT
      and world["lengths"][victim] > LIMIT,
      "injection 4. injection is well-formed: the pinned file really was over the limit "
      "and really is under it now")
f = check_lengths(inj)
check(len(f) == 1 and victim in f[0] and "Delete the entry" in f[0],
      "injection 4. check 1 fails on the now-obsolete PIN, not on the file — the "
      "allowance cannot outlive its reason (the residue gate's shape, reused)")

# 4b. a pin whose file is gone is obsolete too: a pin nothing measures is a pin
# that can never fail, which is the same hole from the other side.
inj = copy_world(world)
del inj["lengths"][victim]
f = check_lengths(inj)
check(len(f) == 1 and victim in f[0] and "no such file" in f[0],
      "injection 4b. check 1 fails on a pin whose file no longer exists")

# 5. NEGATIVE CONTROL — the real, unmutated tree passes, so every bite above is
# the mutation and not a limit set below the tree's own sizes.
check(not check_lengths(world),
      "injection 5. negative control: the real, unmutated tree passes")
over = sorted(r for r, n in world["lengths"].items() if n > LIMIT)
check(over and set(over) == set(world["pins"]),
      "injection 5. ...and it passes because the %d over-limit files are exactly the "
      "pinned ones (%d pins), not because nothing is over the limit" % (len(over),
                                                                        len(world["pins"])))

# 6. END TO END, read from the EXIT CODE. A real file, really written into the
# real GUI tree, and the gate run as a real child process. The verdict is
# `returncode`, never a count of FAIL lines in the output: an injection that
# CRASHED prints no FAIL line at all, and scoring that as a bite is a mistake this
# repo has already made once.
probe = os.path.join(_GUI, "app", "controllers", "zz_file_length_probe.py")
if os.path.exists(probe):
    # An earlier run was interrupted between writing the probe and its `finally`.
    # Check 1 has already failed on it by name; remove it so the run below is not
    # measuring the leftover, and say so rather than dying in a traceback.
    os.remove(probe)
    check(False, "injection 6. a probe file left behind by an interrupted earlier "
                 "run was removed — re-run the gate")
CMD = [sys.executable, os.path.abspath(__file__), "--scan-only"]
try:
    with open(probe, "w", encoding="utf-8") as fh:
        fh.write("# a probe file, deleted by the test that wrote it\n" * (LIMIT + 11))
    grew = subprocess.run(CMD, capture_output=True, text=True, cwd=_REPO)
    check(len(open(probe, encoding="utf-8").read().splitlines()) == LIMIT + 11,
          "injection 6. injection is well-formed: the probe file really is %d lines on "
          "disk, inside the tree the gate scans" % (LIMIT + 11))
    check(grew.returncode == 1,
          "injection 6. the gate EXITS 1 on it (exit %d) — read from the exit code, "
          "never from a FAIL-line count, which a crashed injection would not print at "
          "all" % grew.returncode)
    check("zz_file_length_probe.py" in grew.stdout and "11 over" in grew.stdout,
          "injection 6. ...and the failure it printed names the file and its overage")
finally:
    if os.path.exists(probe):
        os.remove(probe)

# 6b. the other half of the same end-to-end proof: with the probe gone, the same
# command on the same tree exits 0. Without this, injection 6 would be satisfied
# by a gate that fails always.
clean = subprocess.run(CMD, capture_output=True, text=True, cwd=_REPO)
check(not os.path.exists(probe) and clean.returncode == 0,
      "injection 6b. negative control, end to end: with the probe removed the same "
      "child command exits 0 (exit %d)" % clean.returncode)

# 7. the gate needs neither Qt nor a build tree — which is why it can run in CI's
# lint job. Asserted from this process's own import table rather than from the
# source text, so a deferred import inside a function body would still show up.
loaded = sorted(m for m in sys.modules
                if m == "PyQt6" or m.startswith(("PyQt6.", "app.")) or m == "app")
check(not loaded,
      "injection 7. the gate imported no Qt and no application module (%s), so it needs "
      "neither a display nor a build tree" % (loaded or "none loaded"))

if _FAILS:
    print("\nRESULT: %d FAILED" % len(_FAILS), flush=True)
    sys.exit(1)
print("\nRESULT: ALL PASS", flush=True)
sys.exit(0)
