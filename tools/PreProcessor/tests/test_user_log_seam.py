#!/usr/bin/env python3
"""The user-facing log is a service with sinks, not a widget reached through the view tree.

What this pins, and why each one is a defect that shipped:

1. CLASSIFICATION IS QT-FREE. The level heuristics (ANSI colour, the mesher's own
   "[<ISO>] [LEVEL]" stamp, the "eL2 error norm" false positive, native-crash
   tokens) used to live inside LogPanel.log, so none of them could be exercised
   without a QApplication. They are now app.services.user_log.classify.

2. NO SINK IS NOT NO LOG. Every call site used to hard-require a main_window,
   so each windowless entry point grew its own private answer instead
   (run_pipeline.py defines `log = print`; result_playback_mixin hand-rolled an
   "is there a console?" walk up the widget tree). With no sink registered the
   message must still reach the "hybmesh.gui" logger.

3. NO REACH-THROUGH REGRESSION. Statically fail the build if a controller grows
   a new `log_panel.log` reach-through: that is exactly how the 255 call sites
   accumulated, and one private copy is how they stay.

4. A FAILING SINK IS NOT FATAL. Sinks are called from subprocess-output slots; a
   dead C++ widget must not take the worker down, and the other sinks still run.

5. A WRAPPED FAILURE IS ONE FAILURE. Sinks classify for themselves, so a caller
   that tagged every line of a multi-line refusal `[ERROR]` made the user read
   one failure as several — which the mesh stage's missing-geometry refusal did
   until #102 moved the head/tail split next to the classifier it exists for.
   `log_report` grades the FIRST line only.

Run:  python3 tools/PreProcessor/tests/test_user_log_seam.py
"""
import ast
import logging
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.join(_HERE, "..", "gui")
sys.path.insert(0, _GUI)

from app.services import user_log  # noqa: E402

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


# ── 1. classification, with no Qt imported at all ─────────────────────────
check("1. Qt is not imported by the user-log service",
      "PyQt6" not in sys.modules)

cases = [
    # (raw, expected level, expected clean text)
    ("[2026-08-10T06:29:06Z] [INFO] The far-field size cap is never reached.",
     "INFO", "The far-field size cap is never reached."),
    ("[2026-08-10T06:29:06Z] [WARN] Very sharp BL/no-BL wedge at (1, 2)",
     "WARNING", "Very sharp BL/no-BL wedge at (1, 2)"),
    ("[ERROR] Failed to save log: disk full",
     "ERROR", "Failed to save log: disk full"),
    # the level tag is authoritative: "error" in the text must not win over it
    ("[2026-08-10T06:29:06Z] [INFO] collision error norm check passed",
     "INFO", "collision error norm check passed"),
    # the solver's residual line is not a failure
    ("eL2 error norm 1.2e-6", "INFO", "eL2 error norm 1.2e-6"),
    # a native crash carries none of the words "error"/"failed"
    ("Segmentation fault: 11", "ERROR", "Segmentation fault: 11"),
    # a component tag is NOT a level tag and must survive
    ("[Pipeline] stage 2 of 4", "INFO", "[Pipeline] stage 2 of 4"),
    # ANSI colour outranks the keywords
    ("\x1b[1;31mmesh written\x1b[0m", "ERROR", "mesh written"),
]
for raw, want_lvl, want_txt in cases:
    lvl, txt = user_log.classify(raw)
    check(f"1. {raw[:44]!r} -> {want_lvl}", lvl == want_lvl)
    check(f"1. {raw[:44]!r} cleaned", txt == want_txt)

# An explicit level is taken as given, so re-classifying is stable.
lvl, txt = user_log.classify("plain progress line", "ERROR")
check("1. an explicit level is not second-guessed", lvl == "ERROR")
lvl2, txt2 = user_log.classify(txt, lvl)
check("1. re-classifying an already-clean line is stable",
      (lvl2, txt2) == (lvl, txt))

# ── 2. headless: no sink, but the message still reaches the log file ──────
check("2. no sinks are registered outside the GUI", user_log.sinks() == ())

recorded = []


class _Capture(logging.Handler):
    def emit(self, record):
        recorded.append((record.levelno, record.getMessage()))


_lg = logging.getLogger("hybmesh.gui")
_lg.setLevel(logging.INFO)
_lg.addHandler(_Capture())

user_log.log("[WARN] headless runs keep their log")
check("2. a sink-less log still reaches the durable logger", len(recorded) == 1)
check("2. ... at the classified level", recorded and recorded[0][0] == logging.WARNING)
check("2. ... with the emitter stamp stripped",
      recorded and recorded[0][1] == "headless runs keep their log")

# ── 3. sinks get the RAW message, in registration order ──────────────────
seen_a, seen_b = [], []
user_log.add_sink(seen_a.append)
user_log.add_sink(seen_b.append)
user_log.add_sink(seen_a.append)          # re-registering is a no-op
check("3. a sink is registered once", len(user_log.sinks()) == 2)

user_log.log("[ERROR] \x1b[31mboom\x1b[0m")
check("3. every sink is called", len(seen_a) == 1 and len(seen_b) == 1)
check("3. sinks receive the RAW text, so each classifies for itself",
      seen_a[0] == "[ERROR] \x1b[31mboom\x1b[0m")

user_log.log("")
check("3. an empty message is dropped before the sinks", len(seen_a) == 1)

# ── 4. a failing sink does not take the caller down ──────────────────────
def _broken(_m):
    raise RuntimeError("wrapped C/C++ object of type LogPanel has been deleted")


user_log.add_sink(_broken)
try:
    user_log.log("after a dead sink, the live ones still render")
    survived = True
except Exception:
    survived = False
check("4. a raising sink does not propagate", survived)
check("4. ... and the remaining sinks still ran", len(seen_b) == 2)
user_log.remove_sink(_broken)

user_log.remove_sink(seen_a.append)
user_log.remove_sink(seen_b.append)
user_log.remove_sink(seen_b.append)       # removing an unknown sink is a no-op
check("4. sinks unregister cleanly", user_log.sinks() == ())

# ── 5. no new view-tree reach-throughs ───────────────────────────────────
# `AppController.log` / `user_log.log` are the only ways to talk to the user.
# The two exemptions below are the seam itself: MainWindow registers the panel
# as a sink, and LogPanel is that sink.
EXEMPT = {"app/views/main_window.py", "app/views/log_panel.py"}
# Walk the WHOLE gui tree, not a list of subpackages: an earlier version listed
# six of them and so never scanned app/controller.py (the object that owns the
# replacement method), app/utils.py, or main.py — the three files most likely to
# grow a reach-through and the least likely to be noticed.
offenders = []
scanned = set()
for dirpath, _d, files in os.walk(_GUI):
    if os.path.basename(dirpath) == "__pycache__":
        continue
    for fn in sorted(files):
        if fn.endswith(".py"):
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, _GUI)
            scanned.add(rel)
            if rel in EXEMPT:
                continue
            tree = ast.parse(open(path, encoding="utf-8").read())
            for node in ast.walk(tree):
                if (isinstance(node, ast.Attribute) and node.attr == "log"
                        and isinstance(node.value, ast.Attribute)
                        and node.value.attr == "log_panel"):
                    offenders.append(f"{rel}:{node.lineno}")
check("5. nothing reaches through the view tree to log_panel.log "
      f"({len(offenders)} found)" + (f": {offenders[:5]}" if offenders else ""),
      not offenders)

# The gap this closes was invisible: a subpackage list that silently omits a file
# still passes. Assert the walk REACHED the files a reach-through would hide in,
# so shrinking the scan is a failure rather than a quieter pass.
for must in ("app/controller.py", "app/utils.py", "main.py"):
    check(f"5. the reach-through scan actually covers {must}", must in scanned)

# controller.py must expose the replacement, or the rule above has no answer.
_ctl = ast.parse(open(os.path.join(_GUI, "app/controller.py"), encoding="utf-8").read())
_methods = {n.name for cls in _ctl.body if isinstance(cls, ast.ClassDef)
            for n in cls.body if isinstance(n, ast.FunctionDef)}
check("5. AppController.log exists as the controller-side entry point",
      "log" in _methods)
# Both entry points, or the rule "say it through the controller" has no answer for
# the multi-line half and a controller re-grows the head/tail split section 6 pins.
check("5. AppController.log_report exists as the MULTI-LINE entry point",
      "log_report" in _methods)

# ── 6. log_report: a wrapped failure is ONE graded failure ───────────────
# Shaped like the real one — services/mesh_config_geoms.missing_geometry_message
# is a headline, a bulleted path per missing file, and a paragraph of advice.
REFUSAL = ("Geometry file(s) not found:\n"
           "  • results/resampled/gone.dat\n"
           "  • results/resampled/also_gone.dat\n"
           "Remove them from Geometry Files, or re-export the geometry they name.")

shown = []
user_log.add_sink(shown.append)
user_log.log_report(REFUSAL)
user_log.remove_sink(shown.append)

# The display sink classifies the RAW text it was handed, which is the whole
# reason the split has to happen before the sinks see it.
graded = [user_log.classify(m)[0] for m in shown]
check("6. every line of the report reaches the sinks (%d of 4)" % len(shown),
      len(shown) == 4)
check(f"6. exactly ONE of them grades ERROR, not four ({graded})",
      graded.count("ERROR") == 1 and graded[0] == "ERROR")
check("6. ...and the tag is not doubled in the displayed text",
      shown and user_log.classify(shown[0])[1] == "Geometry file(s) not found:")
check("6. the continuation lines are shown verbatim",
      shown[1:] == REFUSAL.split("\n")[1:])

# NEGATIVE CONTROL, for the check above and not for the split: tagging each line
# of THIS message really does grade four, so "exactly one ERROR" is a property of
# `log_report` and not of a message that could never have graded otherwise.
naive = [user_log.classify(f"[ERROR] {ln}")[0] for ln in REFUSAL.split("\n")]
check(f"6. negative control: tagging every line grades FOUR errors ({naive})",
      naive.count("ERROR") == 4)

# An explicit level is honoured, so a multi-line WARNING is not promoted.
shown2 = []
user_log.add_sink(shown2.append)
user_log.log_report("careful:\nsecond line", "WARNING")
user_log.remove_sink(shown2.append)
check("6. an explicit level grades the head line and only the head line",
      [user_log.classify(m)[0] for m in shown2] == ["WARNING", "INFO"])
# A report whose first line carries no text of its own must still arrive GRADED:
# the head would emit nothing and the body is deliberately untagged, so the whole
# refusal would ship as INFO — this function's own defect, from the far side.
for raw, want in (("\nfoo", ["[ERROR] foo"]),
                  ("[ERROR]\nfoo", ["[ERROR] foo"]),
                  ("a\nb", ["[ERROR] a", "b"])):
    edge = []
    user_log.add_sink(edge.append)
    user_log.log_report(raw)
    user_log.remove_sink(edge.append)
    check(f"6. {raw!r} still grades exactly one line ({edge})", edge == want)

check("6. sinks unregister cleanly after section 6", user_log.sinks() == ())

print()
if failures:
    print(f"{len(failures)} FAILURE(S)")
    for f in failures:
        print("  - " + f)
    sys.exit(1)
print("All user-log seam checks passed.")
