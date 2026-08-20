#!/usr/bin/env python3
"""Item 3 regression: a degenerate (coincident-endpoint) split pair must NOT
become a phantom zero-length file segment, and must not survive a rebuild.

Guards the "extra edge5 (Idx 100 -> 101) I can't remove, and convert-to-discrete
brings back" bug: split_indices held two boundaries at a collapsed point, so
update_file_segments_from_indices kept spawning a ~zero-length edge whose shared
endpoints defeated Remove.

Run: python3 tools/PreProcessor/tests/test_degenerate_split_prune.py
"""
import os
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

from app.models.project import ProjectModel  # noqa: E402

fails = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        fails.append(msg)


# Points with a coincident pair at indices 3,4 (a collapsed edge). A split placed
# at both 3 and 4 makes the interval [3,4] a zero-length phantom.
pts = np.array([[0, 0], [1, 0], [2, 0], [3, 0], [3, 0], [4, 0], [5, 0]], float)

# ── prune_degenerate_splits drops the collapsed interior boundary ─────────────
pruned = ProjectModel.prune_degenerate_splits([0, 3, 4, 6], pts)
check(f"prune merges the collapsed [3,4] interval (got {pruned})",
      pruned == [0, 3, 6])
check("prune keeps a healthy chain unchanged",
      ProjectModel.prune_degenerate_splits([0, 3, 6], pts) == [0, 3, 6])
check("prune is a no-op without points",
      ProjectModel.prune_degenerate_splits([0, 3, 4, 6], None) == [0, 3, 4, 6])

# Degenerate FINAL interval: points 5,6 coincident, split at both.
pts2 = np.array([[0, 0], [1, 0], [2, 0], [3, 0], [4, 0], [5, 0], [5, 0]], float)
check("prune collapses a degenerate final interval, keeping the endpoint",
      ProjectModel.prune_degenerate_splits([0, 3, 5, 6], pts2) == [0, 3, 6])

# ── update_file_segments_from_indices never builds the phantom edge ───────────
pm = ProjectModel()
pm.segments = []
pm.update_file_segments_from_indices([0, 3, 4, 6], points=pts)
file_segs = [s for s in pm.segments if s.type == "file"]
spans = {(s.start_index, s.end_index) for s in file_segs}
check(f"rebuild yields 2 real file segments, no phantom (spans={spans})",
      len(file_segs) == 2 and (3, 4) not in spans)
check("the two real spans are [0,3] and [3,6]",
      spans == {(0, 3), (3, 6)})

# Rebuilding again (idempotent) still has no phantom — the convert-to-discrete /
# remove resurrection path.
pm.update_file_segments_from_indices([0, 3, 4, 6], points=pts)
spans2 = {(s.start_index, s.end_index) for s in pm.segments if s.type == "file"}
check("second rebuild is stable, still no phantom", (3, 4) not in spans2)

print()
print("RESULT:", "ALL PASS" if not fails else f"{len(fails)} FAILED", flush=True)
sys.exit(1 if fails else 0)
