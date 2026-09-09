#!/usr/bin/env python3
"""The GUI file-length standard's measurement, in ONE place.

Two gates read this, for two different jobs, and the whole reason it is a module
rather than a copied walk is that they must not be able to disagree:

  * `test_file_length.py` ENFORCES the standard — every `.py` file under
    `tools/PreProcessor/gui/` is within `LIMIT` or pinned at the size it had when
    that gate landed;
  * `test_instruction_budget.py` check 7 DERIVES the status figure the instruction
    files state about that standard — how many files exceed it, out of how many,
    the worst one's size, and in `.claude/rules/gui-seams.md` every offender by
    name — from the same walk, so `--sync` rewrites it from disk and a stale one
    goes red. THREE files state it (the root, that rule file and
    `docs/design_notes/gui.md`) and all three are registered; #101 registered only
    the root, which is why this docstring used to name only `CLAUDE.md`. Those
    numbers are deliberately not repeated here: a figure stated in a file no
    `--sync` reaches is the defect #101 set out to remove.

A second copy of `LIMIT` is the failure this split exists to make unreachable: a
standard changed to 400 in the enforcing gate while the documented status was
still derived at 500 would leave `CLAUDE.md` stating a true-looking number that
measured the wrong thing — the decay class #101 removes, arriving from inside the
machinery that removes it.

This module holds no checks and prints nothing, so importing it has no side
effects; both gates run their own checks at import time and a shared file that
did the same would run them twice.

Needs no Qt, no build tree and no network.
"""
import os

# The standard, verbatim from CLAUDE.md: "Keep each file under
# `tools/PreProcessor/gui/` at ~500 lines; split it when it grows past."
LIMIT = 500

# Repo-relative, and joined with `os.sep` rather than written with `/` because it
# is used to BUILD paths as well as to name them in failures.
GUI_REL = os.path.join("tools", "PreProcessor", "gui")

# Directories that hold no source of ours.
SKIP_DIRS = {"__pycache__", ".ruff_cache", ".git", ".mypy_cache", ".pytest_cache"}


def gui_dir(repo):
    """The GUI package inside `repo`."""
    return os.path.join(repo, GUI_REL)


def measure(root):
    """{relative path: line count} for every .py file under `root`.

    Lines are counted with `splitlines()` rather than by counting newlines, so a
    file with no trailing newline is not silently one line short of its real size.
    """
    lengths = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            lengths[rel] = len(text.splitlines())
    return lengths
