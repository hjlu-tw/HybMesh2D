#!/usr/bin/env python3
"""#191's three-row table, with a row for #192's reducing C-grid in it.

Section 16e of ``docs/research/nesting-blocks-at-a-complicated-leading-edge.md``
states a four-row table of where the cells a refinement ADDS actually land, and
a reader has to be able to re-derive it. The ruler is NOT re-implemented here:
``_bin_cells`` and ``_body_polyline`` are imported from
``tools/PreProcessor/tests/test_multiblock_cgrid_chain_surface.py``, the gate
that #191 measured its own rows with, so the rows here and the rows there are
the same measurement by construction rather than by agreement.

THE BASELINE IS THE SHIPPED FOUR-BLOCK C-GRID AS SHIPPED, at MB_SMOOTH_ITERS 20,
while the two #192 documents are at 0 — because at 20 the reducing one has 120
inverted cells. The ADDED TOTALS are unaffected by that (a mesh has the cell
count its counts give it, smoothed or not); which BIN a cell near a boundary
lands in can be, and nothing here corrects for it.

    ./run.sh -conf <a config with MB_SPLIT_QUADS 0> -out_name /tmp/<name>
    python3 docs/research/gridpro-blocking-method/bin_added_cells.py \
        /tmp/four_block.vtk  "the shipped chain case"=/tmp/chain.vtk ...
"""

import importlib
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", ".."))


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    sys.path.insert(0, os.path.join(ROOT, "tools", "PreProcessor", "tests"))
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    gate = importlib.import_module("test_multiblock_cgrid_chain_surface")
    body = gate._body_polyline()
    base = gate._bin_cells(sys.argv[1], body)
    print("baseline %s: %s, total %d" % (sys.argv[1], base, sum(base)))
    # ABSOLUTE counts as well as the share of what was added. #191's table is
    # "added, split by bin", and that framing assumes every row ADDS in every
    # bin: a document that REDISTRIBUTES -- the #192 stacks put fewer cells
    # beyond one chord than the baseline does -- gives a negative numerator and
    # a share past 100%, which is arithmetic and not a measurement. The absolute
    # row is always meaningful; the share is printed beside it and goes blank
    # when its own denominator cannot carry it.
    print("%-34s %6s %6s %15s %15s %14s"
          % ("", "cells", "added", "< 1 chord", "1-5 chords", "> 5 chords"))
    print("%-34s %6d %6s %7d %7s %7d %7s %6d %7s"
          % ("the BASELINE itself", sum(base), "-", base[0], "", base[1], "",
             base[2], ""))
    for arg in sys.argv[2:]:
        label, _, path = arg.rpartition("=")
        got = gate._bin_cells(path or label, body)
        add = [x - y for x, y in zip(got, base)]
        tot = sum(add)
        def share(v):
            return "(%5.1f%%)" % (100.0 * v / tot) if tot > 0 and min(add) >= 0 \
                else "        "
        print("%-34s %6d %6d %7d %7s %7d %7s %6d %7s"
              % (label or path, sum(got), tot, got[0], share(add[0]),
                 got[1], share(add[1]), got[2], share(add[2])))


if __name__ == "__main__":
    main()
