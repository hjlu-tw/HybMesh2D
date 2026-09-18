#ifndef CELLSHAPE_HPP
#define CELLSHAPE_HPP

#include "GeomUtils.hpp"

#include <cstddef>
#include <vector>

// The per-cell SHAPE metric, and the reducer that turns a mesh full of them into
// three numbers (issue #129, parent #128).
//
// This module knows nothing about `MbResult`, `Mesh` or gmsh: a cell arrives as
// its corner coordinates and leaves as one number. That is what will let both
// generation paths share ONE definition of "how badly shaped is this cell" while
// keeping their two entry points, their two output lines and their two metric
// NAMES apart — writing the arithmetic twice is what guarantees the two drift.
//
// BOTH BRANCHES NOW HAVE A PRODUCTION CALLER. #129 built the shared half and wired
// the multi-block path's quads to it, leaving the triangle branch and
// `measureCellShapes` NAMED as unread rather than shipped as if read; #130 is the
// caller it was named for, and it added no arithmetic here. The claim "shared by
// both paths" is one the tree supports, and this file is where it would be
// believed, so it is stated here with the tickets that make it true.
//
// WHY THE METRIC DEPENDS ON THE CELL KIND, and why the two names must differ:
//
// * A QUAD is measured by the ratio of the distances between the midpoints of its
//   OPPOSITE EDGES. That distance IS the cell's extent in one of its two logical
//   directions, so the ratio answers the question the user is actually asking —
//   "is this cell 1:1?" It is orientation-free (rotate the cell and nothing
//   moves), exactly 1.0 on a square, and exactly the side ratio on an a-by-b
//   rectangle, so it can be read against 1:1 without first learning what the
//   baseline is.
//
//   It is NOT the edge-length ratio, and the difference is not a refinement: on a
//   TAPERED cell the longest and the shortest edge are both in the SAME logical
//   direction, so an edge ratio reports the TAPER and says nothing about the
//   aspect. The symmetric trapezoid (0,0) (4,0) (3,2) (1,2) is 3 wide on average
//   and 2 tall — a midline ratio of 1.5 — while its edge ratio is 2.0, taken
//   between its own bottom and its own top. Check 4 of tests/cpp/test_cell_shape
//   .cpp computes both. On a PARALLELOGRAM the two definitions agree exactly
//   (each midline is a translate of a side), so a sheared parallelogram is NOT
//   what tells them apart, and that is pinned there too rather than left as a
//   plausible-sounding example.
//
// * A TRIANGLE is measured by longest edge / shortest edge, because a triangle
//   has no opposite edges to take midlines between.
//
// The two are DIFFERENT QUANTITIES and are to be reported under different names
// (`quad_midline_ratio` from the multi-block path, `tri_edge_ratio` from the
// hybrid one). A square split on its diagonal is the
// case that makes the point: the quad measures 1.0 and each of its two triangles
// measures sqrt(2), so a shared label would invite a comparison that means
// nothing. It is also why the multi-block path measures its STRUCTURED quads
// rather than the triangles it exports — the same reasoning non-orthogonality
// already follows, and what makes the figure independent of `MB_SPLIT_QUADS`.
//
// EVERY FIGURE HERE IS NEGATIVE WHEN IT WAS NOT MEASURED, never 0 — and unlike
// the other report in this tree, 0 here is not merely flattering but IMPOSSIBLE:
// the metric's floor is 1.0, so a 0.0 could only ever be an absent measurement
// wearing a number. The rule is the same one `MbQualityReport` states.
namespace hybmesh {

// One cell's shape metric, from its corner coordinates in order around the cell.
//
// Returns NEGATIVE, never 0 and never infinity, when the cell cannot be measured:
// fewer than 3 corners, more than 4 (no metric is defined for one, and guessing
// would be worse than saying so), or a degenerate cell whose smaller distance is
// zero — a collapsed edge, or two coincident corners. Total and never throws.
double cellShapeRatio(const std::vector<Point2D>& corners);

// A QUAD'S TWO EXTENTS, in its own logical directions — the pair the quad branch
// above takes the ratio of, handed out so a caller can ask WHICH of the two is
// which.
//
// `extent01` is the cell's extent in the 0->1 direction and `extent12` its extent
// in the 1->2 direction. Each is the distance between the midpoints of the two
// edges that CROSS that direction, so on an a-by-b rectangle they are exactly a
// and b, and `cellShapeRatio`'s quad branch is the larger over the smaller. It
// lives here, and that branch READS it, for the reason the whole module exists:
// the midline arithmetic written a second time is the copy that drifts.
//
// ITS OTHER CALLER IS THE MULTI-BLOCK WALL BAND (#144), which has to know whether
// a cell is thinner ACROSS a declared wall than along it. That is a question about
// the two extents SEPARATELY, and a ratio — which is orientation-free on purpose —
// cannot answer it.
//
// Returns false for anything but four corners, leaving both outputs untouched. A
// DEGENERATE quad still returns true, with a zero extent: "which direction is
// shorter" has no answer there, and a caller that needs one asks for a positive
// length itself rather than reading a zero as small.
bool quadExtents(const std::vector<Point2D>& corners, double& extent01,
                 double& extent12);

// Median, p95 and max over a set of per-cell metrics.
//
// `cells` counts the cells that were actually MEASURED, not the cells offered:
// an unmeasurable cell is left out of the statistics rather than fabricating a
// value for it, exactly as a coincident-node corner is left out of the
// non-orthogonality samples. It is 0 exactly when the three figures are negative.
struct ShapeStats {
    size_t cells = 0;
    double median = -1.0;
    double p95 = -1.0;
    double max = -1.0;
};

// Reduce per-cell metrics. NEGATIVE entries are DROPPED (they are the "could not
// measure this one" signal, not small values), so the result describes the cells
// it could measure and says how many those were.
//
// The two percentile rules, stated because a percentile with no stated rule is a
// number nobody can reproduce:
//   * median  — the middle value, or the MEAN of the two middle ones on an even
//               count.
//   * p95     — NEAREST RANK, `ceil(0.95 * n)` counting from 1, with no
//               interpolation. On a small set that is an actual cell's actual
//               shape rather than a blend of two cells that both exist.
// Both are over the ascending order of the measured values.
ShapeStats reduceCellShapes(std::vector<double> ratios);

// The two composed: measure every cell, then reduce. `cells` holds one corner
// list per cell.
//
// THE HYBRID PATH IS ITS CALLER (`measureHybridCellShapes` in HybridQuality.hpp;
// #130 wired it from `printHybridQuality` in src/cli.cpp and #141 moved that half
// into the pure layer beside this one): one flat list of exported cells, no
// per-block partition to keep and no quad to tell from a triangle. The
// multi-block path composes the two halves itself instead, because it needs both
// of those (see `measureMbQuality`) — which is why this function exists beside
// them rather than under them.
ShapeStats measureCellShapes(const std::vector<std::vector<Point2D>>& cells);

}  // namespace hybmesh

#endif  // CELLSHAPE_HPP
