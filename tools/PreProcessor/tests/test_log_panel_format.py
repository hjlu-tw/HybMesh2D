#!/usr/bin/env python3
"""Regression test: mesher output must render readably in the OUTPUT CONSOLE.

Reported symptom (user, on the size-field read-out):

    [14:29:06] [INFO]   - Growth reaches : 0.0585717 (size field max before the cap)
    [14:29:06] [INFO] [2026-08-10T06:29:06Z] [INFO] The far-field size cap ...

Two independent defects, both in LogPanel.log():

1. DOUBLE STAMP. include/Logger.hpp prefixes every C++ log line with
   "[<ISO UTC>] [LEVEL] ", and proc_util folds stderr into stdout, so all of them
   land here. The panel renders its own clock + level label, and its old strip
   only matched a level tag at the START of the line -- the ISO timestamp sat in
   front of it, so nothing was stripped. This affected every [WARN]/[ERROR] the
   mesher has ever emitted, not just the new INFO line.

2. COLLAPSED ALIGNMENT. append() parses its argument as rich text, and HTML folds
   runs of spaces to one, so every column-aligned block the mesher prints (the
   parameter banner, "[ Mesh Size Field ]") arrived as ragged one-space soup.

Also pinned: the level tag is now authoritative, so an INFO line that merely
contains the word "error" stays INFO instead of being keyword-guessed to ERROR.

Run:  python3 tools/PreProcessor/tests/test_log_panel_format.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "gui"))

from PyQt6.QtWidgets import QApplication            # noqa: E402
from app.views.log_panel import LogPanel            # noqa: E402

# Module scope, as the other GUI tests do: the QApplication has to outlive every
# widget created below.
app = QApplication.instance() or QApplication(sys.argv)

WARN_COLOR = "#ffb74d"
ERROR_COLOR = "#f44336"
failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def main():
    panel = LogPanel()

    # --- 1. the mesher's own stamp must not double up --------------------
    panel.log("[2026-08-10T06:29:06Z] [INFO] The far-field size cap (1) is "
              "never reached: growth only takes the size field to 0.0585717.")
    txt = panel.get_log_text()
    check("the mesher's ISO timestamp is stripped", "2026-08-10T06:29:06Z" not in txt)
    check("only one [INFO] label remains", txt.count("[INFO]") == 1)
    check("the message body survives", "far-field size cap" in txt)

    # A bare level tag (GUI-side callers) must still be stripped.
    panel.clear_log()
    panel.log("[ERROR] Failed to save log: disk full")
    txt = panel.get_log_text()
    check("a bare [ERROR] tag is stripped", txt.count("[ERROR]") == 1)
    check("a bare [ERROR] tag still colours the line ERROR",
          ERROR_COLOR in panel.text_edit.toHtml())

    # --- 2. the declared level wins over keyword guessing ----------------
    panel.clear_log()
    panel.log("[2026-08-10T06:29:06Z] [WARN] Very sharp BL/no-BL wedge at (1, 2)")
    check("a mesher [WARN] renders as WARNING",
          WARN_COLOR in panel.text_edit.toHtml())
    check("the [WARN] line is not double-stamped",
          "2026-08-10T06:29:06Z" not in panel.get_log_text())

    panel.clear_log()
    # Keyword heuristics would call this ERROR; the declared level must win.
    panel.log("[2026-08-10T06:29:06Z] [INFO] collision error norm check passed")
    html = panel.text_edit.toHtml()
    check("a declared INFO containing 'error' is NOT promoted to ERROR",
          ERROR_COLOR not in html)

    # An untagged line must still fall back to the keyword heuristics.
    panel.clear_log()
    panel.log("Segmentation fault: 11")
    check("an untagged crash line is still classified ERROR",
          ERROR_COLOR in panel.text_edit.toHtml())
    panel.clear_log()
    panel.log("eL2 error norm 1.2e-6")
    check("the solver's 'eL2 error norm' stays INFO",
          ERROR_COLOR not in panel.text_edit.toHtml())

    # --- 3. column alignment must survive the HTML round-trip ------------
    panel.clear_log()
    panel.log("  - Growth reaches          : 0.0585717  (size field max)")
    panel.log("  - Effective ceiling       : 0.0585717")
    txt = panel.get_log_text()
    check("padded columns are preserved (spaces not folded)",
          "Growth reaches          :" in txt)
    check("leading indentation is preserved",
          any(ln.endswith("  - Effective ceiling       : 0.0585717")
              for ln in txt.splitlines()))

    # The banner uses the same padding, so it is covered by the same fix.
    panel.clear_log()
    panel.log("  - BL Layers            : 5")
    check("the parameter banner keeps its alignment too",
          "BL Layers            :" in panel.get_log_text())

    print("-------------------------------------------")
    if failures:
        print(f"FAILED {len(failures)} check(s):")
        for f in failures:
            print("  - " + f)
        return 1
    print("All log panel format checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
