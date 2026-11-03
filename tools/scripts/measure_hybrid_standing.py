#!/usr/bin/env python3
"""Measure a hybrid (`MESH_MODE 0`) mesh against the standing table in
`docs/research/jaxa-30p30n-reference-mesh.md`, "Where this repo stands against
them, measured".

This file exists because that table's figures were taken with a script that
lived in a scratchpad and was thrown away, so the only way to check a row was
to trust it. Every row it fills is printed here with the rule that produced it,
and the whole table is re-derivable by:

    ./run.sh -conf config/hybrid_30p30n.dat
    python3 tools/scripts/measure_hybrid_standing.py \\
        results/meshes/hybrid_30p30n/mesh_hybrid_30p30n.vtk \\
        examples/geometries/30p30n_jaxa_slat.dat \\
        examples/geometries/30p30n_jaxa_main.dat \\
        examples/geometries/30p30n_jaxa_flap.dat

Rows it fills: 1 (ribbon depth, as the span the ribbon cells occupy), 4 (near
field), 5 (total cells), 6 (inverted or degenerate), and the triangle-quality
line beneath them.

THE RIBBON CUT IS THE ONE JUDGEMENT CALL, and it is checkable rather than
taken on faith. A hybrid mesh carries no per-cell marker saying which cells the
boundary layer emitted, so this script separates them by distance from the
wall: a cell whose centroid lies within `--ribbon-cut` of any geometry point is
ribbon. Two things keep that honest and both are printed:

  * the mesher publishes its OWN layer-cell count in the `.provenance.json`
    beside the mesh (`quality.layer.cells`), and this script reads it when it
    is there and reports the disagreement. On the shipped case at the default
    cut: 249,703 here against 250,708 there, 0.4% apart.
  * an INDEPENDENT cut, `edge ratio > 2`, is printed beside it — 248,512 on the
    same mesh — so the split does not rest on one ruler.

PASS THE GEOMETRY FILES THE MESH WAS ACTUALLY BUILT FROM. The `.provenance.json`
lists them under `inputs`. A `30p30n_jaxa_*.dat` glob picks up a fourth file,
`..._main_resampled.dat`, which this mesh was not built from, and feeding it in
moves the ribbon count to 249,783 — small, but it is the difference between a
figure and a figure you can repeat.

The mesher is not bit-reproducible (about 0.05% in cell count run to run), so
re-running will not reproduce a figure exactly. `tools/scripts/golden_mesh.py`
is the tool for "did this change anything"; this one is for "where does this
mesh stand".
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

# The near field as the reference's own comparison defines it, in chord units.
WINDOW = (-0.2, 1.4, -0.5, 0.5)
# 60 base layers close-form to 0.0038 chord and 3 transition layers sit on top.
RIBBON_CUT = 0.0041


def read_vtk(path: str):
    """Points and triangles of a legacy-ASCII VTK, plus the cells that are not
    triangles — the domain box's four sides come out as VTK_POLYGON (type 7)
    with two vertices each, and counting those as degenerate cells is how the
    first reading of row 6 went wrong."""
    with open(path) as fh:
        lines = fh.read().split("\n")
    i = next(k for k, l in enumerate(lines) if l.startswith("POINTS"))
    npts = int(lines[i].split()[1])
    pts = np.loadtxt(lines[i + 1:i + 1 + npts])[:, :2]
    j = next(k for k, l in enumerate(lines) if l.startswith("CELLS"))
    ncel = int(lines[j].split()[1])
    raw = lines[j + 1:j + 1 + ncel]
    k = next(q for q, l in enumerate(lines) if l.startswith("CELL_TYPES"))
    ctypes = np.array([int(v) for v in lines[k + 1:k + 1 + ncel]])
    tri_rows = np.where(ctypes == 5)[0]
    tris = np.array([[int(v) for v in raw[q].split()[1:4]] for q in tri_rows])
    others = [(int(ctypes[q]), len(raw[q].split()) - 1) for q in np.where(ctypes != 5)[0]]
    return pts, tris, others


def nearest_wall_distance(centroids: np.ndarray, wall: np.ndarray) -> np.ndarray:
    """Distance from each centroid to the nearest wall POINT, in chunks.

    Chunked brute force rather than a KD-tree so this script needs numpy only,
    like the rest of `tools/scripts/`; scipy appears once in the whole tree.
    """
    out = np.empty(len(centroids))
    step = max(1, int(4e7 // max(1, len(wall))))
    for a in range(0, len(centroids), step):
        b = min(a + step, len(centroids))
        d = centroids[a:b, None, :] - wall[None, :, :]
        out[a:b] = np.sqrt((d * d).sum(axis=2)).min(axis=1)
    return out


def provenance_layer_cells(mesh_path: str):
    """The mesher's own count of the cells its boundary layer emitted, if the
    sidecar is beside the mesh. It is a RUN PRODUCT, not a committed file."""
    side = os.path.splitext(mesh_path)[0] + ".provenance.json"
    if not os.path.exists(side):
        return None, side
    try:
        with open(side) as fh:
            doc = json.load(fh)
        return int(doc["mesh"]["quality"]["layer"]["cells"]), side
    except (KeyError, ValueError, TypeError) as exc:
        print("  (could not read %s: %s)" % (side, exc), file=sys.stderr)
        return None, side


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mesh", help="the .vtk the mesher wrote")
    ap.add_argument("geometry", nargs="+",
                    help="the .dat files the mesh was built from — the ones "
                         "the .provenance.json lists under `inputs`")
    ap.add_argument("--ribbon-cut", type=float, default=RIBBON_CUT,
                    help="centroid distance from the wall below which a cell "
                         "is ribbon (default %(default)s)")
    ap.add_argument("--window", type=float, nargs=4, default=list(WINDOW),
                    metavar=("XMIN", "XMAX", "YMIN", "YMAX"),
                    help="the near field (default %(default)s)")
    args = ap.parse_args()

    pts, tris, others = read_vtk(args.mesh)
    a, b, c = pts[tris[:, 0]], pts[tris[:, 1]], pts[tris[:, 2]]
    cen = (a + b + c) / 3.0
    sarea = 0.5 * ((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1])
                   - (c[:, 0] - a[:, 0]) * (b[:, 1] - a[:, 1]))
    e = np.stack([np.linalg.norm(b - a, axis=1),
                  np.linalg.norm(c - b, axis=1),
                  np.linalg.norm(a - c, axis=1)], axis=1)
    med_edge = np.median(e, axis=1)
    ratio = e.max(axis=1) / np.maximum(e.min(axis=1), 1e-300)

    wall = np.vstack([np.loadtxt(g)[:, :2] for g in args.geometry])
    dist = nearest_wall_distance(cen, wall)
    ribbon = dist < args.ribbon_cut
    bulk = ~ribbon
    x0, x1, y0, y1 = args.window
    win = ((cen[:, 0] >= x0) & (cen[:, 0] <= x1)
           & (cen[:, 1] >= y0) & (cen[:, 1] <= y1))

    def row(label, mask):
        if not mask.any():
            print("  %-34s %9d cells" % (label, 0))
            return
        print("  %-34s %9d cells   median edge %.5f   median sqrt(area) %.5f"
              % (label, mask.sum(), np.median(med_edge[mask]),
                 np.median(np.sqrt(np.abs(sarea[mask])))))

    print("mesh      %s" % args.mesh)
    print("geometry  %s  (%d wall points)"
          % (", ".join(os.path.basename(g) for g in args.geometry), len(wall)))
    print("ribbon    centroid within %.4f of a wall point" % args.ribbon_cut)
    print()

    print("ROW 5 — total cells")
    row("all triangles", np.ones(len(tris), bool))
    if others:
        kinds = ", ".join("VTK type %d with %d vertices" % k for k in sorted(set(others)))
        print("  plus %d non-triangle cells: %s" % (len(others), kinds))
        print("  (the domain box's sides, NOT degenerate cells — see row 6)")
    print()

    print("ROW 1 — the ribbon, and what it is told apart from")
    row("ribbon", ribbon)
    row("bulk (unstructured fill)", bulk)
    own, side = provenance_layer_cells(args.mesh)
    if own is None:
        print("  the mesher's own layer count: no sidecar at %s" % side)
    else:
        n = int(ribbon.sum())
        print("  the mesher's own layer count: %d, against %d here — %.2f%% apart"
              % (own, n, 100.0 * abs(own - n) / max(1, own)))
    print("  an INDEPENDENT cut, edge ratio > 2: %d cells" % int((ratio > 2).sum()))
    print("  ribbon cells reach %.5f from the wall (max centroid distance)"
          % (dist[ribbon].max() if ribbon.any() else 0.0))
    print()

    print("ROW 4 — near field  x %g..%g, y %g..%g, by centroid" % (x0, x1, y0, y1))
    row("all cells in the window", win)
    row("of which ribbon", win & ribbon)
    row("of which unstructured", win & bulk)
    print()

    print("ROW 6 — inverted or degenerate")
    print("  negative area: %d     zero area: %d     (over %d triangles)"
          % (int((sarea < 0).sum()), int((sarea == 0).sum()), len(tris)))
    print()

    print("TRIANGLE QUALITY outside the ribbon (1.0 is equilateral)")
    print("  edge ratio: median %.3f   p95 %.3f"
          % (np.median(ratio[bulk]), np.percentile(ratio[bulk], 95)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
