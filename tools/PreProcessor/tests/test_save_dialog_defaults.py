#!/usr/bin/env python3
"""No save dialog proposes writing over the repo's own tracked inputs.

Issue #5. The Export 2D Profile STL dialog built its default path inside
`examples/geometries/`, from the session's own stem — so a session opened from
`examples/geometries/I_coarse.dat` proposed `I_coarse_2d.stl`, and accepting the
default OVERWROTE a committed sibling in place. Measured once: a tracked binary
STL replaced by a 4.6x larger ascii re-export of the same body, spotted only
because a reviewer noticed an unrelated binary diff in a review of something
else.

Two properties, and they are different questions:

1. **NO SAVE DIALOG DEFAULTS INTO A DIRECTORY THAT HOLDS TRACKED FILES.** This
   is the user-facing half: a test that never accepts a default would fix CI and
   leave the trap armed for everyone else.

   The question is put to GIT, not to a list of folder names, and that is the
   whole design. The first version of this gate carried
   `FORBIDDEN = ("examples", "docs", "src", "include", ".github")` — and omitted
   `config`, while this very docstring named `config/pipeline/` as source. Under
   that list `pipeline_io_ctrl.py` defaulted to `config/pipeline/{session}.json`
   with the blank session named "Untitled 1" — and `config/pipeline/Untitled 1.json`
   was TRACKED (committed in c2a90c5, untracked again once the default moved), so
   the folder held the proof that the default had already been accepted once. The
   same defect as issue #5, in a folder the list forgot, found by a review rather
   than by the gate written to prevent it. A
   hand-maintained list of what is source cannot help going stale; `git ls-files`
   cannot. `examples/`, `docs/`, `src/`, `include/`, `.github/` and
   `config/pipeline/` are all covered now without being named, and a folder that
   BECOMES source later is covered the moment something in it is committed.

   Generated artifacts belong under `results/` (gitignored, nothing tracked), and
   GUI-written working configs under `config/local/`, which is ignored as a whole
   directory so it holds nothing tracked by construction.

2. **`results/` IS ACTUALLY IGNORED, ON A CASE-SENSITIVE FILESYSTEM.** The
   ignore rule read `Results/` while the directory the repo writes is
   `results/`. That matched anyway on macOS and matched NOTHING on Linux, so
   every case-sensitive checkout — CI included — carried `results/` and
   `tools/results/` as untracked noise while the rule looked correct to whoever
   wrote it. Directing output at `results/` is only safe BECAUSE it is ignored,
   so the two checks are one fix and are pinned together.

   The question has to be asked in a form that does not depend on the DISK.
   ``results/`` matches directories only, and for a path's last component git
   decides directory-ness by stat-ing it — so ``check-ignore tools/results``
   answered "ignored" on a developer machine that had run the tool and "not
   ignored" in a fresh checkout, where the ignored directory has never existed.
   That is what turned CI red on 2026-08-20 while every local run was green.
   Every row now carries a trailing slash and check 2a pins the property, so
   losing it fails on the machine that writes it rather than one push later.

Blind spots, named:
  - Check 1 reads the literal path segments in each default expression. A
    default assembled at run time from a variable (`os.path.join(base, name)`
    where `base` came from a config) is invisible to it — including
    `os.path.join(out_dir, f"{stem}.stl")`, where the folder was resolved a line
    earlier. The two live save defaults keep their folder as literal segments in
    the same join FOR THIS REASON, and moving one into a helper would hide it.
  - The count is over the whole SUBTREE, so a folder is refused when something
    below it is tracked even though a file written directly into it could not
    collide with that. Deliberately the strict direction: a directory whose
    subtree holds committed files is not a scratch folder.
  - "Tracked" is a property of the index, so `git add -f` on one file inside an
    output directory turns that whole directory into an offender. That is the
    right answer — a default that can overwrite a committed file is the defect,
    whatever the folder is called — but it means this gate can go red for a
    reason that is nothing to do with the code under it.
  - It scans `getSaveFileName` call sites. A dialog opened some other way, or a
    file written with no dialog at all, is not covered.
  - Check 2 asks git, so it verifies the RULE. It does not prove any particular
    run writes only there.

Run:  python3 tools/PreProcessor/tests/test_save_dialog_defaults.py
"""
import ast
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_APP = os.path.join(_REPO, "tools", "PreProcessor", "gui", "app")

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


_tracked_count: dict[str, int] = {}


def holds_tracked(rel_dir: str) -> int:
    """How many files git tracks under ``rel_dir``. 0 makes it a safe target.

    Asked of the index rather than the disk, so the answer does not depend on
    whether a gitignored output directory happens to exist on this machine —
    the state-dependence that turned CI red on 2026-08-20 for check 2.
    """
    if rel_dir not in _tracked_count:
        p = subprocess.run(["git", "ls-files", "--", rel_dir],
                           cwd=_REPO, capture_output=True, text=True)
        _tracked_count[rel_dir] = len([ln for ln in p.stdout.splitlines() if ln])
    return _tracked_count[rel_dir]


def bad_defaults(src: str) -> list[str]:
    """Path-building expressions in this module that write into tracked territory.

    Deliberately looks at every ``os.path.join`` that ends in a filename, not
    only the one handed to ``getSaveFileName``: the default is routinely built a
    few lines above the call and assigned to a local, which is exactly how the
    original was written.

    The literal segments minus the filename are the folder, and the folder is
    then looked up in git. A join with no literal segment at all (the folder came
    from a variable) is skipped rather than guessed about — see the blind spots.
    """
    tree = ast.parse(src)
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "join"):
            continue
        last = node.args[-1] if node.args else None
        if not _ends_in_a_filename(last):
            continue
        lits = [a.value for a in node.args
                if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if lits and isinstance(last, ast.Constant) and isinstance(last.value, str):
            lits = lits[:-1]          # the trailing filename is not the folder
        if not lits:
            continue
        rel = "/".join(lits)
        n = holds_tracked(rel)
        if n:
            hits.append(f"line {node.lineno}: {rel}/{_describe(last)} "
                        f"({n} tracked file(s) under {rel}/)")
    return hits


def _ends_in_a_filename(last) -> bool:
    """Whether this join's final part names a FILE rather than a directory.

    The distinction is the whole check: ``os.path.join(repo, "examples",
    "geometries")`` is where demo geometry is LOADED from and must not fail,
    while the same join with a filename appended is a write target.

    An f-string is the case that matters and the one the first attempt missed —
    the original defect ended in ``f"{stem}_2d.stl"``, an ``ast.JoinedStr`` and
    not an ``ast.Constant``, so a constants-only scan walked straight past the
    exact expression this issue was filed about. Anything that is not a plain
    extension-less constant counts as a filename, because a gate that guesses
    "directory" is the one that lets this back in.
    """
    if last is None:
        return False
    if isinstance(last, ast.Constant) and isinstance(last.value, str):
        return "." in last.value
    return True


def _describe(node) -> str:
    try:
        return ast.unparse(node)
    except Exception:  # pragma: no cover - display only
        return "<expr>"


# ── 1. every save-dialog module ─────────────────────────────────────────────
scanned, offenders = [], []
for root, _dirs, files in os.walk(_APP):
    for fn in sorted(files):
        if not fn.endswith(".py"):
            continue
        path = os.path.join(root, fn)
        with open(path) as fh:
            src = fh.read()
        if "getSaveFileName" not in src:
            continue
        rel = os.path.relpath(path, _REPO)
        scanned.append(os.path.basename(path))
        offenders += [f"{rel} {h}" for h in bad_defaults(src)]

# 15 modules open a save dialog today. The floor sits just under that rather
# than at half of it: its job is to catch the WALK breaking (a bad root, an
# extension filter that stops matching), and a floor of 8 would have let more
# than half the app fall out of scope while still reporting a pass.
check(f"1. {len(scanned)} save-dialog modules scanned (anti-vacuity)",
      len(scanned) >= 13)
check("1b. no save dialog defaults into a folder holding tracked files: "
      + ("; ".join(offenders) if offenders else "none"), not offenders)
check("1c. the extrude export — the one that overwrote a committed STL — is "
      "among the modules scanned", "extrude_ctrl.py" in scanned)

# ── 2. results/ is really ignored, case and all ─────────────────────────────
def _ignored(rel: str) -> bool:
    """Ask git, with case-folding OFF so the answer is the Linux answer.

    A directory MUST be asked about with a trailing slash, and that is not
    cosmetic. The rule is ``results/``, which git matches against directories
    only — and for the LAST component of the path it is given, git decides
    directory-ness by looking at the DISK. So ``check-ignore tools/results``
    answers "ignored" on a machine that has run the tool once and "not ignored"
    in a fresh checkout, because the directory is gitignored and therefore was
    never committed. Measured 2026-08-20 by cloning this repo: ``tools/results``
    NOT ignored, ``tools/results/`` ignored, same commit and same .gitignore.
    That is exactly how this test passed for everyone locally and turned CI red
    — the answer depended on state the test does not control. The slash tells
    git the thing it would otherwise guess.

    ``results/stl3d`` never had the problem: there ``results`` is a LEADING
    component, so git knows it is a directory without asking the disk. Relying
    on that would leave the question fragile per-row, so every row carries it.
    """
    p = subprocess.run(
        ["git", "-c", "core.ignorecase=false", "check-ignore", "-q", rel],
        cwd=_REPO, capture_output=True)
    return p.returncode == 0


for rel in ("results/stl3d/", "results/meshes/", "tools/results/"):
    check(f"2. '{rel}' is ignored on a CASE-SENSITIVE filesystem (Linux/CI)",
          _ignored(rel))

# The guard that makes the row above honest on the machine that writes it. A
# path matching the rule but ABSENT from disk is ignored only if the question was
# asked in the disk-independent form, so dropping the trailing slash fails HERE,
# locally, instead of passing and failing in CI a push later.
_absent = "src/results/"
check(f"2a. …and the question does not depend on the disk: '{_absent}' is "
      "ignored though nothing of that name exists",
      not os.path.exists(os.path.join(_REPO, _absent)) and _ignored(_absent))

check("2b. …and nothing under results/ is tracked",
      subprocess.run(["git", "ls-files", "results/"], cwd=_REPO,
                     capture_output=True, text=True).stdout.strip() == "")

# ── 3. the injection: the check must fire on the original defect ────────────
print()
print("── injection ──")
_original = ('default_path = os.path.join(\n'
             '    repo_root(), "examples", "geometries",\n'
             '    f"{stem}_2d.stl")\n'
             'QFileDialog.getSaveFileName(w, "t", default_path, "")\n')
ast.parse(_original)
check("3. the exact expression this issue was filed about is caught",
      bool(bad_defaults(_original)))
_ok = ('out = os.path.join(repo_root(), "results", "stl3d", f"{stem}_2d.stl")\n'
       'QFileDialog.getSaveFileName(w, "t", out, "")\n')
ast.parse(_ok)
check("3b. …and the replacement is not", not bad_defaults(_ok))
_read = 'p = os.path.join(repo_root(), "examples", "geometries")\n'
ast.parse(_read)
check("3c. …nor is a bare directory, which is how demo geometry is LOADED",
      not bad_defaults(_read))
_missed = ('default = os.path.join(repo_root(), "config", "pipeline", f"{n}.json")\n'
           'QFileDialog.getSaveFileName(w, "t", default, "")\n')
ast.parse(_missed)
check("3d. …and the one the hand-written FORBIDDEN list walked past is caught: "
      "config/pipeline/, which holds the curated scripts four tests read",
      bool(bad_defaults(_missed)))
_local = ('default = os.path.join(repo_root(), "config", "local", f"{n}.json")\n'
          'QFileDialog.getSaveFileName(w, "t", default, "")\n')
ast.parse(_local)
check("3e. …while its SIBLING config/local/ is allowed — same parent, opposite "
      "answer, which is the rule resolving rather than matching folder names",
      not bad_defaults(_local))

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for f in failures:
        print("  - " + f)
    sys.exit(1)
print("All save-dialog default checks passed.")
