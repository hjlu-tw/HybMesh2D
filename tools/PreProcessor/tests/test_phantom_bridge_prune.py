#!/usr/bin/env python3
"""Model-level guard for the phantom-bridge fix (Remove Edge resurrection +
arc Convert-to-Discrete '99>100' ghost).

update_file_segments_from_indices builds a segment for every consecutive
split-index pair. After removing a MIDDLE file segment the two survivors become
index-adjacent across the hole they used to fill, and appending a disjoint piece
(a converted free-standing arc) leaves the base end index-adjacent to the new
range's start. Either way a spurious 1-edge segment bridges a discontinuity —
non-coincident, so prune_degenerate_splits can't see it. The rebuild must DROP
such adjacent, no-overlap NEW pairs on a real rebuild, while never dropping a
genuine split sub-segment nor breaking a fresh build.

Run: python3 tools/PreProcessor/tests/test_phantom_bridge_prune.py
"""
import os
import sys
import functools

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

import builtins
print = functools.partial(builtins.print, flush=True)
_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        _FAILS.append(msg)


from app.models.project import ProjectModel
from app.models.segment import SegmentModel


def file_seg(sid, s, e):
    seg = SegmentModel(sid, s, e)
    seg.type = "file"
    return seg


def rebuild(existing, splits, npts):
    pm = ProjectModel()
    pm.segments = list(existing)
    pts = np.column_stack([np.arange(npts, dtype=float), np.zeros(npts)])
    # spread y a little so nothing is coincident (prune must not be what fires)
    pts[:, 1] = np.arange(npts) * 0.01
    pm.update_file_segments_from_indices(splits, points=pts)
    return [(s.start_index, s.end_index) for s in pm.segments if s.type == "file"]


# 1. Fresh build (empty existing map) — every pair becomes a segment.
r = rebuild([], [0, 5, 10], 11)
check(r == [(0, 5), (5, 10)], f"fresh build keeps all pairs (got {r})")

# 2. Genuine split — parent (0,10) in map; sub-pairs overlap it, both kept.
r = rebuild([file_seg(1, 0, 10)], [0, 5, 10], 11)
check(r == [(0, 5), (5, 10)], f"split keeps both sub-segments (got {r})")

# 3. Remove MIDDLE segment — survivors (0,5) & (6,15) index-adjacent at 5→6.
#    split_indices gains the bridge pair (5,6); it must be dropped.
r = rebuild([file_seg(1, 0, 5), file_seg(2, 6, 15)], [0, 5, 6, 15], 16)
check(r == [(0, 5), (6, 15)],
      f"remove-middle drops the (5,6) phantom bridge (got {r})")

# 4. Arc Convert-to-Discrete append — base (0,99) + arc (100,120); the base end
#    99 sits index-adjacent to the arc start 100. Bridge (99,100) must be dropped
#    while the arc segment survives.
r = rebuild([file_seg(1, 0, 99), file_seg(2, 100, 120)],
            [0, 99, 100, 120], 121)
check(r == [(0, 99), (100, 120)],
      f"arc append drops the (99,100) phantom, keeps the arc (got {r})")

# 5. A legitimate short 1-edge segment already in the map is NEVER dropped
#    (only NEW no-overlap adjacent pairs are).
r = rebuild([file_seg(1, 0, 1), file_seg(2, 1, 10)], [0, 1, 10], 11)
check(r == [(0, 1), (1, 10)], f"existing short edge (0,1) kept (got {r})")

# 6. Idempotence — rebuilding the item-3 survivors again introduces no phantom.
pm = ProjectModel()
pm.segments = [file_seg(1, 0, 5), file_seg(2, 6, 15)]
pts = np.column_stack([np.arange(16, dtype=float), np.arange(16) * 0.01])
pm.update_file_segments_from_indices([0, 5, 6, 15], points=pts)
pm.update_file_segments_from_indices(
    pm.get_split_indices_from_file_segments(), points=pts)
r = [(s.start_index, s.end_index) for s in pm.segments if s.type == "file"]
check(r == [(0, 5), (6, 15)], f"second rebuild stays phantom-free (got {r})")

print()
if _FAILS:
    print(f"RESULT: {len(_FAILS)} FAILED")
    sys.exit(1)
print("RESULT: ALL PASS")
sys.exit(0)
