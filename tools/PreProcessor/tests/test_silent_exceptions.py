#!/usr/bin/env python3
"""Regression tests for finding N7 — silently swallowed exceptions.

The defect: 36 handlers across the GUI were ``except Exception: pass``. The app
already configures a rotating log file and an uncaught-exception hook
(``services/logging_setup.py``), but none of these sites used it, so when a
canvas overlay, a snap callback, a probe overlay or the CAD-to-pipeline-script
sync failed in the field, the log contained *nothing at all* — the behaviour just
quietly degraded. They now log at:

  * ``debug``   — genuinely best-effort (cursor changes, teardown/removeItem);
                  nothing the user asked for is lost.
  * ``warning`` — a failure silently degrades requested behaviour (an unsnapped
                  point, missing iso-lines, a saved pipeline script that does not
                  match the canvas, an export under the wrong name).

Checks:
 1. get_logger() returns a ``hybmesh.gui.<module>`` child, usable before setup.
 2. No new SILENT BROAD HANDLER anywhere under ``tools/PreProcessor/gui/`` —
    only the documented allowlist, which is limited to logging's own write path
    (logging a logging failure recurses) and the escalation thread's terminal
    catch.
 3. A converted warning site really writes a record *with a traceback*.
 4. A converted debug site records at DEBUG and is dropped at INFO.
 5. HYBMESH_LOG_LEVEL raises the level so best-effort diagnostics are reachable.
 6. Log records carry the module name, so a message can be traced to its site.
 7. A geometry file that EXISTS and cannot be read is named, with its
    exception, by all FIVE readers that open one (#117's four, plus the mesh
    panel's auto-sizing hint reader, added by #118 and driven here by #127 --
    which is also when this sentence stopped saying FOUR).
 8. ...while a geometry file that is simply ABSENT still produces no record.

Check 2 is about the HANDLER, not about one keyword (#118). Until then it matched
a body of exactly ``["pass"]``, and #117 is what that cost: a refactor moved what
REACHES one of these handlers, turning a correct skip into a swallowed
diagnostic, and every gate stayed green because the body said ``continue``. What
the standard bans is a broad catch that neither RECORDS the failure nor RE-RAISES
it; ``pass`` is only its most recognisable spelling. ``continue``, ``break``,
``return``, ``return <fallback>`` and a body that is nothing but a string literal
discard exactly as much, and all six now fail.

BROAD, not every handler. ``except ValueError: continue`` inside a line parser is
the correct idiom, and this tree holds over a hundred narrow handlers that
recover deliberately. A gate that flagged them would need an allowlist longer
than the rule, and this repo's own lint policy says a permanently-red gate is
worse than none. The widening triaged 10 sites the tree really held — the project
baseline and its dirty comparison, the transform handle length, the gmsh probe,
the curve preview, two numpy import guards that were dead (numpy is a hard
dependency, so those handlers were deleted rather than logged), two geometry
reads behind the auto-sizing hints and the formula evaluator's two — and added
NO new allowlist entry. The ticket's own figures (28/14/3/0) came from a scan of
EVERY except clause on the pre-#117 tree, its `3 return` counting BARE returns
only; the numbers above are re-derived here and printed by check 2 on every run
rather than restated.

Checks 7-8 are proved non-vacuous by seven injections, the verdict read from the
EXIT CODE and with a negative control on the unmutated tree (this repo has
scored a crashed injection as a bite that never happened):

  * the BC overlay reverted to ``except Exception: continue``   -> check 7 red
  * the selection highlight reverted to ``except Exception: return`` -> 7 red
  * the bbox scan's fallback reverted to ``except OSError: pass``     -> 7 red
  * the loader thread's print replaced by ``pass``                    -> 7 red
  * the hint reader's handler made silent (#127)                      -> 7 red
    -- and red ALONE: its body was written ``pts = None; return pts``, which is
    blind spot (a) below, so the run's only two FAILs are check 7's own and the
    keyword scan contributed nothing. The literal pre-#118 shape
    (``except Exception: return None``) reddens check 7 too, and check 2 with it.
  * the BC overlay made to log the ABSENT case as well               -> 8 red
  * the hint reader made to log the ABSENT case as well (#127)        -> 8 red

Check 2 has injections of its own, in two tiers. In process: each of the six
discarding bodies fires on its own, three at once are all reported in one run, an
allowlisted site does NOT fire while the same site without its comment does, an
allowlist entry whose file no longer holds a silent handler fails as obsolete, an
unparsable file is a failure rather than a skip, and a negative control shows the
real tree passes because its silent sites are exactly the allowlisted ones.
End to end: a probe file written into the real GUI tree, with the verdict read
from a child process's EXIT CODE plus an empty stderr (exit 1 alone does not
separate a bite from a crash) — once per keyword; once with the probe's own path
allowlisted for that child run (`--allow-probe`), which must exit 0, beside the
identical file without the entry, which must not, and the identical file without
its comment, which must not either; once whose only `#` sits inside a STRING, which
must not either (the explanation half reads real `tokenize` COMMENT tokens, so
punctuation cannot satisfy it); and once with the probe removed, to show the
same command exits 0.

Known blind spots, stated rather than pretended away:

 a. It reads CONTROL FLOW, not intent. A broad handler whose body does anything
    else — ``self._x = None``, a UI reset — is not reached, and can discard just
    as completely. Deciding whether a body "records the failure" needs to
    recognise logging by name, which is the fragile version of this gate;
    ``_reset_project_baseline`` was fixed by hand rather than by widening here.
 b. It is scoped to the GUI tree, which is what the standard binds. The mesher's
    Python (``tools/scripts/``) and the test suite itself are outside it.
 c. A broad handler aliased past the name match (``Err = Exception`` then
    ``except Err:``) is not recognised. Nothing in this tree does it, and a name
    match is what keeps the scan readable.

Run:  python3 tools/PreProcessor/tests/test_silent_exceptions.py
      python3 tools/PreProcessor/tests/test_silent_exceptions.py --scan-only
        check 2's walk alone — no injections, no Qt, no AppController. This is
        the mode the end-to-end injections run in a child process, so that
        running the gate cannot recurse into spawning another copy of itself.
"""
import ast
import logging
import os
import shutil
import io
import subprocess
import sys
import tempfile
import threading
import tokenize

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
#: The tree the standard binds, and therefore the tree check 2 walks. It is the
#: GUI package and not `app/`: `gui/main.py` sits outside `app/` and the standard
#: reaches it, which the old scan's root quietly did not.
GUI_REL = "tools/PreProcessor/gui"
_GUI = os.path.join(_REPO, GUI_REL)
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >60s", flush=True)
    os._exit(99)


_wd = threading.Timer(60, _watchdog)
_wd.daemon = True
_wd.start()

# ── 1. get_logger ─────────────────────────────────────────────────────────
from app.services.logging_setup import LOGGER_NAME, get_logger  # noqa: E402

lg = get_logger("app.controllers.demo_ctrl")
check(lg.name == f"{LOGGER_NAME}.controllers.demo_ctrl",
      f"1. get_logger names the child after the module (got {lg.name!r})")
check(get_logger(None).name == LOGGER_NAME,
      "1. get_logger(None) returns the root GUI logger")
# Usable at import time, before configure_logging() has run.
lg.debug("harmless")
check(True, "1. logging before configure_logging() does not raise")

# ── 2. no new SILENT BROAD HANDLER ────────────────────────────────────────
# #118 widened this from one keyword to the HANDLER. What the standard bans is a
# broad catch that neither RECORDS the failure nor RE-RAISES it; `pass` is only
# its most recognisable spelling. `continue`, `break` and `return` discard
# exactly as much, and #117 is what the gap cost: a refactor moved what REACHES
# one of those handlers, turning a correct skip into a swallowed diagnostic, and
# every gate stayed green because the body said `continue` rather than `pass`.
#
# Read with `ast`, not with a regex plus an indentation walk over the next seven
# lines. The old scan could be walked around three ways that are not defects at
# all -- a comment above the keyword, an `except` clause spilling over two lines,
# a docstring in the handler -- and it could only ever see the ONE spelling it
# was written against. The AST sees the handler.
#
# BROAD, not every handler. `except ValueError: continue` inside a line parser is
# the correct idiom, and this tree holds over a hundred narrow handlers that
# recover deliberately; a gate that flagged them would need an allowlist longer
# than the rule, and this repo's own lint policy says a gate people work around
# is worse than none. The line is drawn where the standard draws it: a catch wide
# enough to swallow an error nobody predicted.
BROAD_NAMES = {"Exception", "BaseException"}

#: The single-statement handler bodies that discard. `raise` is absent on
#: purpose: re-raising is the other correct answer, not a violation.
_SILENT_STMTS = ((ast.Pass, "pass"), (ast.Continue, "continue"),
                 (ast.Break, "break"))

# Each entry is silent ON PURPOSE; the reason must be in a comment at the site.
# Self-invalidating in both directions, the shape `test_file_length.py`'s PINS
# and `test_instruction_budget.py`'s KNOWN_RESIDUE already use here: a file whose
# last silent handler is fixed or deleted FAILS as an obsolete entry, so an
# allowance cannot outlive its reason.
ALLOWED_SILENT = {
    # Moved out of app/views/log_panel.py when the user-facing log grew a seam:
    # the file mirror belongs to the service, so the widget no longer writes it.
    ("app/services/user_log.py", "this IS the write-to-log-file path"),
    ("app/services/logging_setup.py", "logging setup / excepthook"),
    ("app/workers/proc_util.py", "escalation thread terminal catch"),
}
ALLOWED_FILES = {f for f, _ in ALLOWED_SILENT}

#: INJECTION LEVER, and nothing else. `--allow-probe` adds the end-to-end probe's
#: own path to the allowlist for one child run, so that "an allowlisted site does
#: NOT fire" can be proved the same way the bites are — from a real file in the
#: real tree and a real exit code — without mutating a source file that a killed
#: run would leave modified. It can only ever reach `zz_silent_handler_probe.py`,
#: a name this gate writes and deletes itself, so it cannot exempt anything real.
if "--allow-probe" in sys.argv[1:]:
    ALLOWED_FILES.add("zz_silent_handler_probe.py")


def _is_broad(handler) -> bool:
    """True for a catch wide enough to swallow an error nobody predicted."""
    t = handler.type
    if t is None:
        return True                 # a bare `except:` is the widest of them all
    for node in (t.elts if isinstance(t, ast.Tuple) else [t]):
        # Matched by NAME so `Exception`, `builtins.Exception` and a tuple
        # holding either are one rule.
        name = node.attr if isinstance(node, ast.Attribute) else getattr(
            node, "id", "")
        if name in BROAD_NAMES:
            return True
    return False


def _silent_stmt(handler):
    """The lone discarding statement in ``handler``, or None if it does work.

    A leading string expression is dropped first: a handler may carry a
    docstring-shaped comment and still be a silent handler.
    """
    def _is_str(st):
        return (isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant)
                and isinstance(st.value.value, str))

    body = [st for st in handler.body if not _is_str(st)]
    if not body:
        # A handler whose ENTIRE body is a string literal runs nothing at all —
        # the loudest-looking silence there is, since the text usually reads as
        # an explanation. Reported at the string, which is the whole handler.
        return handler.body[0], "a string literal"
    if len(body) != 1:
        return None, None
    st = body[0]
    for cls, kw in _SILENT_STMTS:
        if isinstance(st, cls):
            return st, kw
    if isinstance(st, ast.Return):
        # `return` and `return <fallback>` are the same silence: the caller is
        # handed an answer that cannot be told apart from a successful one.
        return st, ("return" if st.value is None else "return <expr>")
    return None, None


def scan_gui(gui_dir):
    """Every silent broad handler under ``gui_dir``, plus the file count.

    A file that will not PARSE is reported rather than skipped: a scan that
    quietly drops what it cannot read is a scan that can be switched off by a
    syntax error.
    """
    sites, unparsed, n_files = [], [], 0
    for root, _dirs, files in os.walk(gui_dir):
        for fn in sorted(files):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, gui_dir)
            n_files += 1
            src = open(path, encoding="utf-8").read()
            try:
                tree = ast.parse(src)
            except SyntaxError as exc:
                unparsed.append(f"{rel}: {exc}")
                continue
            # Real COMMENT tokens, not `"#" in line`: a `#` inside a string on
            # the same line would otherwise read as an explanation, which is the
            # allowlist half of this check quietly satisfied by punctuation. Not
            # wrapped in a handler — the parse above already succeeded, so a
            # tokenize failure here is a bug that should take the gate down
            # loudly rather than downgrade every site to "explains nothing".
            comment_lines = {tok.start[0] for tok
                             in tokenize.generate_tokens(io.StringIO(src).readline)
                             if tok.type == tokenize.COMMENT}
            for node in ast.walk(tree):
                if not isinstance(node, ast.ExceptHandler) or not _is_broad(node):
                    continue
                st, kind = _silent_stmt(node)
                if st is None:
                    continue
                # "Explains itself" = a real comment after the `except` clause
                # and no later than the discarding statement's own line.
                commented = any(ln in comment_lines
                                for ln in range(node.lineno + 1, st.lineno + 1))
                sites.append({"rel": rel, "line": node.lineno, "kind": kind,
                              "commented": commented})
    return {"sites": sites, "unparsed": unparsed, "n_files": n_files,
            "allowed": set(ALLOWED_FILES)}


def check_silent(world):
    """Every failure, never just the first — one run tells the whole job."""
    fails = list(world["unparsed"])
    allowed = world["allowed"]
    for site in world["sites"]:
        where = f"{GUI_REL}/{site['rel']}:{site['line']}"
        if site["rel"] not in allowed:
            fails.append(
                f"{where} is a broad handler whose whole body is `{site['kind']}` — "
                f"it neither records the failure nor re-raises it. Log it through "
                f"get_logger(__name__) at debug(..., exc_info=True), or at warning "
                f"if the failure silently degrades what the user asked for. "
                f"ALLOWED_SILENT is for the handful of sites that must stay quiet, "
                f"and every entry states why.")
        elif not site["commented"]:
            fails.append(
                f"{where} is allowlisted as intentionally silent and explains "
                f"nothing. Put the reason in a comment at the site: the allowlist "
                f"says WHICH file may be quiet, the comment says why THIS handler "
                f"is.")
    for rel in sorted(allowed):
        if not any(site["rel"] == rel for site in world["sites"]):
            fails.append(
                f"ALLOWED_SILENT allows `{rel}` to hold a silent broad handler and it "
                f"holds none. Delete the entry — an allowance that outlives its reason "
                f"is the skip list this list was written instead of.")
    return fails


def run(fn, world, msg):
    """Evaluate the check ONCE, print each failure, then record the verdict."""
    fails = fn(world)
    for fail in fails:
        print("     -> " + fail, flush=True)
    check(not fails, msg)


world = scan_gui(_GUI)
run(check_silent, world,
    "2. no undocumented silent broad handler under %s/ (%d .py files, %d silent "
    "sites, all in the %d allowlisted files)"
    % (GUI_REL, world["n_files"], len(world["sites"]), len(world["allowed"])))
check(world["n_files"] > 200,
      "2. ...and the walk really reached the GUI package (%d .py files; an empty "
      "walk would pass every injection below)" % world["n_files"])

# --- --scan-only: the walk alone, no injections, no Qt --------------------
# The end-to-end injections below run this gate in a CHILD process so the verdict
# can be read from an EXIT CODE. Without this mode that child would run the
# injections too, and would spawn a child of its own, forever.
if "--scan-only" in sys.argv[1:]:
    _wd.cancel()
    os._exit(1 if _FAILS else 0)


# --- injections on check 2 -------------------------------------------------
# Each mutates a COPY of the scan's output, asserts the mutation really differs,
# then asserts the check reports it. A crash inside one propagates and takes this
# process's exit status with it, so an injection that DIED cannot be misread as
# an injection that bit — the mistake this repo has made before, scoring a
# crashed injection by counting FAIL lines it never printed.
def copy_world(w):
    return {"sites": [dict(x) for x in w["sites"]], "unparsed": list(w["unparsed"]),
            "n_files": w["n_files"], "allowed": set(w["allowed"])}


VICTIM = "app/controllers/injected_ctrl.py"


def with_site(kind, rel=VICTIM, line=42, commented=False):
    inj = copy_world(world)
    inj["sites"].append({"rel": rel, "line": line, "kind": kind,
                         "commented": commented})
    return inj


# i1. every discarding body, one at a time. `pass` was the only one the gate saw
# before #118; the other four are the back door it closes.
for _kind in ("pass", "continue", "break", "return", "return <expr>",
              "a string literal"):
    _inj = with_site(_kind)
    _f = check_silent(_inj)
    check(len(_f) == 1 and VICTIM in _f[0] and ":42" in _f[0] and _kind in _f[0]
          and "neither records" in _f[0],
          "injection 1. a broad handler whose body is `%s` FAILS check 2, named by "
          "file:line and by what its body says" % _kind)

# i1b. a handler that does WORK is not silent, whatever it catches. Without this
# the gate could be satisfied by flagging every broad handler in the tree, which
# would be a different rule and a redder one.
check(not check_silent(copy_world(world)),
      "injection 1b. the same world with no injected site passes — i1 bit on the "
      "site, not on the shape of the check")

# i2. EVERY offender in one run. Stopping at the first makes a developer re-run
# the gate once per site, and this widening added several at once.
inj = copy_world(world)
for i, kind in enumerate(("continue", "return", "break")):
    inj["sites"].append({"rel": f"app/views/injected_{i}.py", "line": 7 + i,
                         "kind": kind, "commented": False})
f = check_silent(inj)
check(len(f) == 3 and all(f"injected_{i}.py" in " ".join(f) for i in range(3)),
      "injection 2. all THREE injected sites are reported in one run")

# i3. an ALLOWLISTED site does NOT fire — the other half of the gate, and the one
# that decides whether it can be green at all.
_allowed_rel = sorted(world["allowed"])[0]
check(not check_silent(with_site("continue", rel=_allowed_rel, commented=True)),
      "injection 3. a `continue` in an ALLOWLISTED file that explains itself does "
      "NOT fire (%s)" % _allowed_rel)
f = check_silent(with_site("continue", rel=_allowed_rel, commented=False))
check(len(f) == 1 and "explains nothing" in f[0],
      "injection 3. ...while the same site with no comment fails — the allowlist "
      "says WHICH file may be quiet, the comment says why THIS handler is")

# i4. an allowlist entry whose file no longer holds one is OBSOLETE. Without this
# the list is a skip list that grows and never shrinks.
inj = copy_world(world)
inj["sites"] = [x for x in inj["sites"] if x["rel"] != _allowed_rel]
check(any(x["rel"] == _allowed_rel for x in world["sites"]),
      "injection 4. injection is well-formed: %s really does hold one today"
      % _allowed_rel)
f = check_silent(inj)
check(len(f) == 1 and _allowed_rel in f[0] and "Delete the entry" in f[0],
      "injection 4. an allowlist entry whose file holds no silent handler fails as "
      "obsolete — an allowance cannot outlive its reason")

# i5. a file that will not PARSE is reported, not skipped. A scan that drops what
# it cannot read can be switched off with a syntax error.
inj = copy_world(world)
inj["unparsed"].append("app/views/broken.py: invalid syntax (line 3)")
f = check_silent(inj)
check(len(f) == 1 and "broken.py" in f[0],
      "injection 5. a file the walk could not parse is a FAILURE, not a silent skip")

# i6. NEGATIVE CONTROL — the real tree passes, and it passes for the right
# reason: the silent sites it found are exactly the allowlisted ones.
check(not check_silent(world),
      "injection 6. negative control: the real, unmutated tree passes check 2")
check(world["sites"] and {x["rel"] for x in world["sites"]} <= world["allowed"],
      "injection 6. ...and it passes because its %d silent site(s) are all in the "
      "%d allowlisted files, not because the walk found nothing"
      % (len(world["sites"]), len(world["allowed"])))

# --- injections END TO END, verdict from the EXIT CODE ---------------------
# A real file, really written into the real GUI tree, and the gate run as a real
# child process. Deliberately at the GUI ROOT rather than inside `app/`: still
# inside the tree the gate walks, but not inside a package, so a run killed
# between the write and the `finally` cannot leave an importable module behind.
# The name is in .gitignore for the same reason.
#
# The GUI root is also the half of the tree the old scan never reached — it
# walked `app/` — so these three prove the widened ROOT as well as the widened
# body.
PROBE = os.path.join(_GUI, "zz_silent_handler_probe.py")
PROBE_SRC = {
    "continue": "def _probe(items):\n    for it in items:\n        try:\n"
                "            it()\n        except Exception:\n            continue\n",
    "return": "def _probe(it):\n    try:\n        return it()\n"
              "    except Exception:\n        return\n",
    "break": "def _probe(items):\n    for it in items:\n        try:\n"
             "            it()\n        except Exception:\n            break\n",
}
CMD = [sys.executable, os.path.abspath(__file__), "--scan-only"]

if os.path.exists(PROBE):
    # An earlier run was interrupted between the write and its `finally`. Check 2
    # has already failed on it by name; remove it and say so, rather than
    # measuring the leftover or dying in a traceback.
    os.remove(PROBE)
    check(False, "injection 7. a probe file left behind by an interrupted earlier "
                 "run was removed — re-run the gate")

for kind, src in PROBE_SRC.items():
    try:
        with open(PROBE, "w", encoding="utf-8") as fh:
            fh.write("# a probe file, deleted by the test that wrote it\n" + src)
        got = subprocess.run(CMD, capture_output=True, text=True, cwd=_REPO)
        check(got.returncode == 1,
              "injection 7. the gate EXITS 1 on a broad handler whose body is `%s` "
              "(exit %d) — read from the exit code, never from a FAIL-line count, "
              "which a CRASHED injection would not print at all" % (kind,
                                                                    got.returncode))
        # Exit 1 alone does not separate a bite from a crash: an unhandled
        # exception exits 1 too, which is the confusion the exit-code rule exists
        # against. The verdict is exit 1 AND a clean stderr AND the named site.
        check(not got.stderr.strip(),
              "injection 7. ...by FAILING, not by CRASHING — stderr is empty (%r)"
              % got.stderr[:120])
        check("zz_silent_handler_probe.py" in got.stdout and kind in got.stdout,
              "injection 7. ...and the failure it printed names the probe and `%s`"
              % kind)
    finally:
        if os.path.exists(PROBE):
            os.remove(PROBE)

# i7c. an ALLOWLISTED site does NOT fire, proved the same way — a real file in
# the real tree and a real exit code. The probe's own path is allowlisted for the
# child run by `--allow-probe`, rather than by mutating one of the three real
# allowlisted files, which a killed run would leave edited.
try:
    with open(PROBE, "w", encoding="utf-8") as fh:
        fh.write("# a probe file, deleted by the test that wrote it\n"
                 "def _probe(items):\n    for it in items:\n        try:\n"
                 "            it()\n        except Exception:\n"
                 "            # the reason this one is allowed to be quiet\n"
                 "            continue\n")
    allowed = subprocess.run(CMD + ["--allow-probe"], capture_output=True,
                             text=True, cwd=_REPO)
    check(allowed.returncode == 0 and not allowed.stderr.strip(),
          "injection 7c. the same probe in an ALLOWLISTED file exits 0 (exit %d) — "
          "the allowlist really is an exemption and not decoration"
          % allowed.returncode)
    # ...and it is the ALLOWLIST doing it, not the comment: the identical file
    # without the entry still fails.
    denied = subprocess.run(CMD, capture_output=True, text=True, cwd=_REPO)
    check(denied.returncode == 1 and "zz_silent_handler_probe.py" in denied.stdout,
          "injection 7c. ...while the identical file WITHOUT the allowlist entry "
          "exits 1 (exit %d), so the exemption is what passed it" % denied.returncode)
    # ...and the comment is load bearing too: allowlisted but silent about why.
    with open(PROBE, "w", encoding="utf-8") as fh:
        fh.write("# a probe file, deleted by the test that wrote it\n"
                 "def _probe(items):\n    for it in items:\n        try:\n"
                 "            it()\n        except Exception:\n"
                 "            continue\n")
    bare = subprocess.run(CMD + ["--allow-probe"], capture_output=True, text=True,
                          cwd=_REPO)
    check(bare.returncode == 1 and "explains nothing" in bare.stdout,
          "injection 7c. ...and an allowlisted site with NO comment still exits 1 "
          "(exit %d) — the entry says which FILE may be quiet, the comment says why "
          "THIS handler is" % bare.returncode)
    # ...and a `#` that is only PUNCTUATION inside a string is not an explanation.
    # The string statement is also the filtered-out "docstring" of the handler, so
    # this probe exercises both halves at once: the body still reads as `continue`.
    with open(PROBE, "w", encoding="utf-8") as fh:
        fh.write("# a probe file, deleted by the test that wrote it\n"
                 "def _probe(items):\n    for it in items:\n        try:\n"
                 "            it()\n        except Exception:\n"
                 "            \"a # inside a string, not a comment\"\n"
                 "            continue\n")
    faked = subprocess.run(CMD + ["--allow-probe"], capture_output=True, text=True,
                           cwd=_REPO)
    check(faked.returncode == 1 and "explains nothing" in faked.stdout
          and "`continue`" not in faked.stdout,
          "injection 7c. ...and a `#` inside a STRING is not a comment (exit %d): the "
          "body still reads as `continue`, and the explanation half is not satisfied "
          "by punctuation" % faked.returncode)
finally:
    if os.path.exists(PROBE):
        os.remove(PROBE)

# i7b. the other half of the same proof: with the probe gone, the same command on
# the same tree exits 0. Without this, injection 7 is satisfied by a gate that
# fails always.
clean = subprocess.run(CMD, capture_output=True, text=True, cwd=_REPO)
check(not os.path.exists(PROBE) and clean.returncode == 0,
      "injection 7b. negative control, end to end: with the probe removed the same "
      "child command exits 0 (exit %d)" % clean.returncode)

# ── 3-6. the handlers really log ──────────────────────────────────────────
import app.services.logging_setup as ls  # noqa: E402

tmpdir = tempfile.mkdtemp(prefix="hybmesh_logtest_")
ls._log_dir = lambda: tmpdir
os.environ["HYBMESH_LOG_LEVEL"] = "DEBUG"
root_logger = ls.configure_logging()
check(root_logger.level == logging.DEBUG,
      "5. HYBMESH_LOG_LEVEL=DEBUG raises the effective level")

from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)
from app.controller import AppController  # noqa: E402

ctl = AppController()
logfile = os.path.join(tmpdir, "gui.log")


def read_log() -> str:
    for h in root_logger.handlers:
        h.flush()
    return open(logfile, encoding="utf-8").read() if os.path.exists(logfile) else ""


# 3. warning site: the live output-name read fails -> export would use a
#    different name than the user typed, so this must never be silent.
def _boom(*_a, **_k):
    raise RuntimeError("panel exploded")


ctl.main_window.mesh_config_panel.get_config = _boom
ctl.global_mesh_config.output_filename = "fallback_name.vtk"
name = ctl._current_output_filename()
log = read_log()
check(name == "fallback_name.vtk", "3. the warning path still falls back correctly")
check("could not read the live output name" in log,
      "3. ...and records a WARNING instead of swallowing it")
check("panel exploded" in log and "Traceback" in log,
      "3. ...with the full traceback (exc_info=True)")

# 4/6. debug site: a teardown removeItem() that raises.
mcv = ctl.main_window.mesh_canvas_view
mcv._error_highlight_items = ["not-an-item"]
mcv.plot_widget.removeItem = lambda _item: (_ for _ in ()).throw(
    RuntimeError("removeItem refused"))
mcv.clear_error_highlights()
log = read_log()
check("could not remove an error-highlight item" in log
      and "removeItem refused" in log,
      "4. a best-effort teardown failure is recorded at DEBUG")
check("hybmesh.gui.views.mesh_canvas_geom_mixin" in log,
      "6. records carry the module name of the failing site")

# 4b. At INFO those DEBUG diagnostics are dropped again (no log spam by default).
root_logger.setLevel(logging.INFO)
before = len(read_log())
mcv._error_highlight_items = ["not-an-item"]
mcv.clear_error_highlights()
check(len(read_log()) == before,
      "4. ...and is dropped at the default INFO level (no routine spam)")

os.environ.pop("HYBMESH_LOG_LEVEL", None)

# ── 7. a geometry that EXISTS and cannot be READ reaches the log ──────────
# #117. Until #112 the broad `except` around np.loadtxt in these readers WAS
# the existence answer, so discarding it was correct: a missing geometry is not
# an error. #112 moved existence out into readable_geom_path, so everything that
# still reaches those handlers is a GENUINE read failure on a file that is
# there -- and both of them discarded it without a word. Driven against a real
# unreadable file rather than by reading the code: the point is what the user
# can find in results/logs/gui.log afterwards.
from app.models.mesh_config import MeshConfig  # noqa: E402

_geo = tempfile.mkdtemp(prefix="hybmesh_geomtest_")
unreadable = os.path.join(_geo, "unreadable.dat")
with open(unreadable, "w", encoding="utf-8") as _f:
    _f.write("0 0\n1 0\n1 1\n")
os.chmod(unreadable, 0o000)
try:
    open(unreadable, encoding="utf-8").close()
    # Running as a user who can read anything (root in a container): fall back to
    # the other failure the ticket names -- a directory where a file should be.
    os.chmod(unreadable, 0o600)
    os.remove(unreadable)
    os.mkdir(unreadable)
    _kind = "a directory where a file should be"
except OSError:
    _kind = "a chmod-000 file"
check(os.path.exists(unreadable),
      f"7. the fixture EXISTS ({_kind}) -- readable_geom_path answers it")

bad_cfg = MeshConfig()
bad_cfg.add_geom_file(unreadable)
check(bool(bad_cfg.geom_files), "7. the fixture is in the mesh config")

mcv.mesh_config = bad_cfg
mcv.show_bc_coloring = True
mcv.geom_bc_items = []          # nothing to remove (removeItem is stubbed above)
mcv._sel_highlight_item = None

before = len(read_log())
mcv._rebuild_geom_bc_preview()
bc_log = read_log()[before:]
check("unreadable.dat" in bc_log and "BC overlay" in bc_log,
      "7. the BC overlay names the unreadable geometry in the log")
check("hybmesh.gui.views.mesh_canvas_bc_mixin" in bc_log
      and "Traceback" in bc_log,
      "7. ...from its own module, with the exception (exc_info=True)")

before = len(read_log())
mcv.highlight_geometry_file(unreadable)
hi_log = read_log()[before:]
check("unreadable.dat" in hi_log and "selection highlight" in hi_log,
      "7. the selection highlight names the unreadable geometry in the log")
check("hybmesh.gui.views.mesh_canvas_geom_mixin" in hi_log
      and "Traceback" in hi_log,
      "7. ...from its own module, with the exception (exc_info=True)")

# The third opener of the same entry: the bbox scan's fallback read fails too,
# and its `except OSError: pass` used to end the story there.
before = len(read_log())
ctl._scan_geometry_files(bad_cfg)
bb_log = read_log()[before:]
check("unreadable.dat" in bb_log and "bbox scan" in bb_log
      and "hybmesh.gui.controllers.mesh_gen_ctrl" in bb_log,
      "7. the mesh bbox scan names it too (the third caller that OPENS)")

# The FOURTH opener records to stdout rather than to the log file, beside its
# own malformed-geometry line. Measured here rather than asserted from the
# code, because "we looked and it names the file" is exactly the evidence this
# ticket exists to replace. run() is called directly: it is an ordinary method,
# and the point is what it writes, not which thread wrote it.
import contextlib  # noqa: E402
import io as _io  # noqa: E402

from app.views.mesh_canvas_loader import GeomLoaderThread  # noqa: E402

from app.services.geometry_service import load_points_dat  # noqa: E402

try:
    load_points_dat(unreadable)
    _exc_text = ""
except Exception as _e:               # the exception the thread has to report
    _exc_text = str(_e)

_buf = _io.StringIO()
with contextlib.redirect_stdout(_buf):
    GeomLoaderThread([unreadable]).run()
loader_out = _buf.getvalue()
# The head only: the OS embeds a path in the message, and the thread reports
# the CANONICAL one (/private/var/... on macOS) while our own call used the
# spelling tempfile handed us. What is measured is that the exception reaches
# stdout at all, not that two spellings of one path match.
_exc_head = _exc_text.split(": ")[0]         # e.g. "[Errno 13] Permission denied"
check(bool(_exc_head), "7. the fixture really does fail the loader")
check("unreadable.dat" in loader_out and _exc_head in loader_out,
      f"7. the preview loader thread names it and the exception ({_exc_head}), "
      f"on stdout")

# The FIFTH opener (#118). It is a module-level function, so it is driven
# DIRECTLY -- no panel, no widget tree -- and its two callers (the auto
# far-field hint and the auto surface hint) share it, so one call covers both.
# Its handler was correct by reading from the day it was written; what was
# missing until #127 is the thing #117 exists to insist on, that the proof is
# what the reader WRITES.
from app.views.panels.mesh_sizing_mixin import _hint_points  # noqa: E402

before = len(read_log())
check(_hint_points(unreadable, "auto far-field hint") is None,
      "7. the auto-sizing hint reader still answers None on an unreadable file")
hint_log = read_log()[before:]
check("unreadable.dat" in hint_log and "auto far-field hint" in hint_log
      and "left OUT of the estimate" in hint_log,
      "7. the auto-sizing hint reader names it, and says the geometry is left "
      "out (the fifth caller that OPENS)")
check("hybmesh.gui.views.panels.mesh_sizing_mixin" in hint_log
      and "Traceback" in hint_log,
      "7. ...from its own module, with the exception (exc_info=True)")

# ── 8. a geometry that is simply ABSENT stays silent ──────────────────────
# The change must DISTINGUISH the two cases, not make both noisy: a file the
# user has not made yet is answered by readable_geom_path and never reaches an
# open, so there is nothing to record.
absent = os.path.join(_geo, "not_made_yet.dat")
check(not os.path.exists(absent), "8. the absent fixture really is absent")
gone_cfg = MeshConfig()
gone_cfg.add_geom_file(absent)
mcv.mesh_config = gone_cfg
mcv.geom_bc_items = []
mcv._sel_highlight_item = None

before = len(read_log())
_buf = _io.StringIO()
with contextlib.redirect_stdout(_buf):
    mcv._rebuild_geom_bc_preview()
    mcv.highlight_geometry_file(absent)
    ctl._scan_geometry_files(gone_cfg)
    GeomLoaderThread([absent]).run()
    _hint_points(absent, "auto surface hint")
check(len(read_log()) == before and _buf.getvalue().strip() == "",
      "8. an absent geometry produces no record from any of the five")

# The fixture is chmod-000 (or a directory): leave nothing undeletable behind.
if os.path.isfile(unreadable):
    os.chmod(unreadable, 0o600)
shutil.rmtree(_geo, ignore_errors=True)
check(not os.path.exists(_geo), "8. the fixture directory is cleaned up")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
