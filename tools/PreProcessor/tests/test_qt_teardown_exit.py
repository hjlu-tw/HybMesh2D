#!/usr/bin/env python3
"""Every script here that builds a QApplication must end in ``os._exit``.

WHY THIS IS A GATE AND NOT A COMMENT. Qt's teardown under ``QT_QPA_PLATFORM=offscreen``
can segfault on a machine with no GPU, AFTER the script's last statement has run. The
checks all print PASS, the exit code is 139, and `run_all.sh` reports
``FAIL <script> (exit 139)`` — a green test read as a failing assertion, which sends
the reader hunting through a body that is correct. Measured on CI run 36506672624:
`test_topology_repair.py` printed `All checks passed.` and then died with
`Segmentation fault (core dumped)`, having been green in CI for days beforehand. It
does not reproduce on macOS, so a developer cannot see it locally.

The cure is `os._exit`, which skips the teardown entirely. `run_all.sh` has carried a
comment saying so since long before that CI failure, and five scripts still did not do
it — a house style nothing enforced. This file enforces it.

WHAT IT CANNOT SEE, stated rather than implied:

  - A script that gets a QApplication some other way than the two spellings in
    ``_BUILDS_APP`` (a helper module, a star import). None does today; a new one would
    be invisible here, which is what check 0's population count is for.
  - Whether ``os._exit`` is on the path actually taken. A file that ends in a branch
    the run never reaches passes. The check reads the last statement, which is where
    the ending belongs, rather than a mention anywhere in the file.
  - A teardown crash in a script that builds no QApplication. Out of scope: there is
    no Qt teardown to crash.
  - Whether a flush reaches stdout in every branch. Check 2 reads the block the final
    ``os._exit`` sits in; a second ``os._exit`` on the failure path a few lines up is
    not looked at. `test_restart_archive.py` and `test_result_clim_per_variable.py`
    have one, and both were given a flush by hand.

INJECTIONS, run by hand 2026-09-29, each against a COPY of this directory so the real
tree was never mutated. All five bit; what is recorded is what each run PRINTED.

  A. revert `test_popup_stacking.py` to ``sys.exit(1 if _FAILS else 0)`` -> check 1 red,
     ``(65/66) — offenders: ['test_popup_stacking.py (line …)']``. The real regression.
  B. keep ``os._exit`` but append a trailing ``print("done")`` after it -> check 1 red,
     the same shape. A mention is not an ending, which is check 1's whole point.
  C. ``_qt_scripts()`` returning ``[]`` -> check 0 red, ``(0 of 127 runnable scripts
     here)``. Without check 0 the other two pass vacuously, which is how a scan that
     has stopped matching anything goes green.
  D. drop the ``sys.stdout.flush()`` from `test_solver_bc_table.py` -> check 2 red,
     ``(65/66) — unflushed: ['test_solver_bc_table.py']``.
  E. delete the one-level indirection from ``_last_statement`` -> check 1 red naming
     `test_bc_preview_coloring.py`, which is CORRECT — its ``os._exit`` is the last
     line of the ``main()`` its module body calls. This injection is the false positive
     the gate would otherwise have shipped, and it is why the resolution is there.

WHAT CHECK 2 IS WORTH, measured rather than argued. ``os._exit`` skips the flush a
normal exit does, and `run_all.sh` redirects each script's stdout to a file — so a
missing flush silently truncates the log it prints under a FAIL line. Seven scripts
here were losing their verdict: `test_solver_bc_table.py`'s redirected output ended at
``PASS 12. …`` with ``all checks passed`` gone, and under `PYTHONUNBUFFERED=1` the same
run ended at ``all checks passed``. On a green run nobody looks, which is how it
survived. All seven were fixed in the same commit as this file.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent

# The two spellings this directory uses. Kept as source text rather than an import so
# the gate never has to build a QApplication of its own to measure one.
_BUILDS_APP = re.compile(r"QApplication\s*\(|QApplication\.instance\s*\(")

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def _qt_scripts():
    """Every runnable script here whose source builds a QApplication."""
    out = []
    for p in sorted(HERE.glob("*.py")):
        if p.name == pathlib.Path(__file__).name:
            continue
        if not (p.name.startswith("test_") or p.name.startswith("smoke_")):
            continue
        if _BUILDS_APP.search(p.read_text(encoding="utf-8")):
            out.append(p)
    return out


def _last_statement(tree):
    """The last statement a module actually RUNS, resolving one level of indirection.

    ``ast`` rather than a tail regex: the ending is frequently the last line of an
    ``if __name__`` block or of an ``if/else``, and a regex over the final lines cannot
    tell that from a comment or a string. The indirection matters too —
    `test_bc_preview_coloring.py` ends in a bare ``main()`` whose own last statement is
    the ``os._exit``, and reading only the module body calls that file an offender when
    it is correct. One level, deliberately: a chain deeper than that is not a shape this
    directory uses, and following it would be guessing at the path taken rather than
    reading it.
    """
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}

    def _walk(body):
        node = body[-1] if body else None
        while node is not None and getattr(node, "body", None):
            node = node.body[-1]
        return node

    node = _walk(tree.body)
    called = (node.value.func.id
              if isinstance(node, ast.Expr)
              and isinstance(node.value, ast.Call)
              and isinstance(node.value.func, ast.Name)
              else None)
    if called in funcs:
        return _walk(funcs[called].body)
    return node


def _is_os_exit(node):
    return (isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "_exit"
            and isinstance(node.value.func.value, ast.Name)
            and node.value.func.value.id == "os")


def _flushes(node):
    """``sys.stdout.flush()``, or a ``print(..., flush=True)``."""
    if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
        return False
    fn = node.value.func
    if isinstance(fn, ast.Attribute) and fn.attr == "flush":
        return True
    if isinstance(fn, ast.Name) and fn.id == "print":
        return any(k.arg == "flush" and getattr(k.value, "value", False) is True
                   for k in node.value.keywords)
    return False


def _flushes_before(tree, target):
    """Does anything flush stdout in the block the final ``os._exit`` sits in?

    The block, not the whole file: a ``flush=True`` five hundred lines up in some check
    helper says nothing about what is still buffered at the exit. Only the siblings
    ahead of it in its own suite count.
    """
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list) or target not in body:
            continue
        return any(_flushes(s) for s in body[: body.index(target)])
    return False


def _print_is_rebound_flushing(tree):
    """``print = functools.partial(<something>.print, flush=True)`` at module level.

    15 scripts here take this route instead of flushing at the exit, and it is just as
    good: every line they print is flushed as it is written, so nothing is left in the
    buffer for `os._exit` to drop. Detected by SHAPE rather than by its source text —
    this directory already spells it two ways (`builtins.print` and
    `__import__("builtins").print`), and a text match on the first one calls the second
    an offender when it is correct.
    """
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t_, ast.Name) and t_.id == "print" for t_ in node.targets):
            continue
        if isinstance(node.value, ast.Call) and any(
                k.arg == "flush" and getattr(k.value, "value", False) is True
                for k in node.value.keywords):
            return True
    return False


scripts = _qt_scripts()
trees = {p: ast.parse(p.read_text(encoding="utf-8"), filename=str(p)) for p in scripts}

check(f"0. the scan finds the QApplication-building scripts at all, so a gate that "
      f"stopped matching anything cannot pass vacuously ({len(scripts)} of "
      f"{len(list(HERE.glob('test_*.py'))) + len(list(HERE.glob('smoke_*.py')))} "
      f"runnable scripts here)",
      len(scripts) >= 50)

offenders = []
for p in scripts:
    node = _last_statement(trees[p])
    if not _is_os_exit(node):
        where = f"line {node.lineno}" if node is not None else "empty file"
        offenders.append(f"{p.name} ({where})")

check(f"1. every one of them ENDS in `os._exit(...)`, so Qt's offscreen teardown "
      f"never runs and a green run cannot exit 139 "
      f"({len(scripts) - len(offenders)}/{len(scripts)})"
      + (f" — offenders: {offenders}" if offenders else ""),
      not offenders)

# The ending is only half of it: `os._exit` skips the flushing a normal exit does, so a
# script that does not flush first can lose the very output `run_all.sh` prints when it
# reports the failure. A green run hides that — the output is discarded either way —
# which is why it is gated rather than left to the reader of a diff.
unflushed = [p.name for p in scripts
             if _is_os_exit(_last_statement(trees[p]))
             and not _flushes_before(trees[p], _last_statement(trees[p]))
             and not _print_is_rebound_flushing(trees[p])]

check(f"2. and each flushes stdout on the way out, `os._exit` being the one exit that "
      f"does not ({len(scripts) - len(unflushed)}/{len(scripts)})"
      + (f" — unflushed: {unflushed}" if unflushed else ""),
      not unflushed)

print()
# This gate builds no QApplication, so it has no teardown to skip — plain sys.exit is
# correct here and `os._exit` would be cargo cult.
sys.exit(1 if failures else 0)
