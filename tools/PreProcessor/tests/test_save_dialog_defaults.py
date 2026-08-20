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

1. **NO SAVE DIALOG DEFAULTS INTO A TRACKED SOURCE FOLDER.** `examples/` is
   INPUT — 60 tracked files — and `docs/`, `src/`, `include/`, `config/pipeline/`
   are source. Generated artifacts belong under `results/`, which is gitignored
   and holds nothing tracked. This is the user-facing half: a test that never
   accepts a default would fix CI and leave the trap armed for everyone else.

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
    where `base` came from a config) is invisible to it.
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


#: Folders a save dialog must never propose writing into. Each is either
#: tracked source or committed input; a generated file has no business there.
FORBIDDEN = ("examples", "docs", "src", "include", ".github")


def bad_defaults(src: str) -> list[str]:
    """Path-building expressions in this module that name a forbidden folder.

    Deliberately looks at every ``os.path.join`` whose literal parts include a
    forbidden segment, not only the one handed to ``getSaveFileName``: the
    default is routinely built a few lines above the call and assigned to a
    local, which is exactly how the original was written.
    """
    tree = ast.parse(src)
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "join"):
            continue
        parts = [a.value for a in node.args
                 if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if not any(p in FORBIDDEN for p in parts):
            continue
        if _ends_in_a_filename(node.args[-1] if node.args else None):
            shown = "/".join(parts) + "/" + _describe(node.args[-1])
            hits.append(f"line {node.lineno}: {shown}")
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

check(f"1. {len(scanned)} save-dialog modules scanned (anti-vacuity)",
      len(scanned) >= 8)
check("1b. no save dialog defaults into a tracked source folder: "
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

print()
if failures:
    print(f"{len(failures)} FAILURE(S):")
    for f in failures:
        print("  - " + f)
    sys.exit(1)
print("All save-dialog default checks passed.")
