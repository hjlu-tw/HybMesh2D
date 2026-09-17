// The pure cell-shape module (issue #129, parent #128), tested through
// `cellShapeRatio`, `reduceCellShapes` and `measureCellShapes` and nothing else.
//
// This executable links `hybmesh_pure` and NOTHING else — not gmsh, not
// hybmesh_core, and it never builds an `MbResult` either. That build property is
// itself part of the ticket: the whole reason this module exists separately is
// that "how badly shaped is this one cell" must be answerable without a mesh, a
// topology or a mesh container, so that BOTH generation paths can share one
// definition of it.
//
// The checks are chosen to be FALSIFIABLE rather than merely green, and the two
// that carry the argument are the ones whose premise is computed here:
//
//   * A square measures exactly 1.0 and each half of it, split on its diagonal,
//     measures exactly sqrt(2) — which is the parent ticket's whole reason for
//     measuring the STRUCTURED quad rather than the exported triangle, and the
//     reason the two metrics carry different names. Check 2 computes that sqrt(2)
//     from the triangle's own edge lengths instead of pasting 1.414, so the
//     number is derived here rather than asserted.
//   * On a TAPERED cell the longest and the shortest edge are the same logical
//     direction, so an edge-length ratio reports the taper and says nothing about
//     the shape. Check 4 computes that cell's own edge lengths, shows which two
//     edges the extremes are, and prints both numbers — so "an edge ratio would
//     have said 2.0 where the cell is 3:2" is measured in the test rather than
//     claimed in a comment. Check 4b is its negative half: on a PARALLELOGRAM the
//     two definitions agree exactly, so the plausible-sounding sheared-square
//     example is pinned as NOT a discriminator.
//
// BLIND SPOTS, named rather than papered over:
//   * Nothing here prints a banner, a machine-readable line or a sidecar. That
//     the three figures reach a run's output, agree with each other, and do not
//     move with `MB_SPLIT_QUADS`, is external behaviour of the binary and is
//     pinned in tools/PreProcessor/tests/test_multiblock_shape_surface.py.
//   * Nothing here says which cells the multi-block path feeds in. That it is the
//     STRUCTURED (i,j) quads and not the exported triangles is
//     `measureMbQuality`'s decision, pinned in tests/cpp/test_mb_quality.cpp.
//   * The metric says nothing about ORIENTATION or about inversion: a folded cell
//     may well measure a perfectly ordinary ratio. Inversion is a different
//     instrument (`MbQualityReport::invertedCells`) and this one is not it
//     wearing another name.
//   * p95 is nearest-rank with no interpolation, so on a small set it is an
//     actual cell's actual shape. Nothing here compares it against an
//     interpolating definition, because there is only one definition in the tree.
//
// INJECTIONS: run BY HAND at review time, 2026-09-17, and recorded here rather
// than written as in-test injections — a C++ test cannot mutate the
// implementation it linked against, so unlike the Python gates next door these
// cannot re-run themselves. Each names the checks it broke, so a later reader can
// tell a check that bites from one that merely passes:
//
//   A. the quad metric replaced by longest-edge / shortest-edge -> 2 failures,
//      checks 4 and 5. A square, a rectangle, a sliver AND a parallelogram all
//      agree under both definitions, which is why check 4 has to be a TAPERED
//      cell and why check 4b pins the parallelogram's agreement rather than
//      leaving it as a discriminator it is not.
//   B. the quad midlines paired with the ADJACENT edges instead of the opposite
//      ones -> 9 failures, across checks 3 (x3), 4, 4b, 5, 6 and 8 (x2).
//   C. `ratioOf` returning 0.0 instead of a negative for a degenerate cell
//      -> 3 failures, check 6 alone. Note what does NOT move: the reducer drops
//      a 0.0 by the same `> 0.0` test it drops a negative by, so checks 7 and 8
//      stay green. That is the belt to check 6's braces and not a gap — but it
//      does mean the rule is guarded at ONE place, and check 6 is it.
//   D. `reduceCellShapes` returning 0.0 figures for an empty input instead of
//      negative ones -> 3 failures, check 7 alone.
//   E. p95 taken as `ratios[n * 95 / 100]` (a 0-based index, one rank high on a
//      20-value set) -> 1 failure, check 9.
//   F. the median on an even count taken as the upper of the two middles
//      -> 2 failures, checks 8 and 9.
#include "CellShape.hpp"
#include "check.hpp"

#include <algorithm>
#include <cmath>
#include <vector>

using hybmesh::ShapeStats;
using hybmesh::cellShapeRatio;
using hybmesh::measureCellShapes;
using hybmesh::reduceCellShapes;

namespace {

std::vector<Point2D> quad(double ax, double ay, double bx, double by,
                          double cx, double cy, double dx, double dy) {
    return {{ax, ay}, {bx, by}, {cx, cy}, {dx, dy}};
}

std::vector<Point2D> tri(double ax, double ay, double bx, double by,
                         double cx, double cy) {
    return {{ax, ay}, {bx, by}, {cx, cy}};
}

// The edge lengths of a cell, in order around it. Used by the two negative
// controls to compute their own premise rather than assert a pasted number.
std::vector<double> edges(const std::vector<Point2D>& c) {
    std::vector<double> out;
    for (size_t k = 0; k < c.size(); ++k)
        out.push_back((c[(k + 1) % c.size()] - c[k]).length());
    return out;
}

}  // namespace

int main() {
    // ── 1. A square is exactly 1.0, and stays 1.0 wherever it is ─────────────
    {
        CHECK_NEAR(cellShapeRatio(quad(0, 0, 1, 0, 1, 1, 0, 1)), 1.0, 0.0,
                   "1. a unit square measures EXACTLY 1.0 — not 1 within a "
                   "tolerance, which is the property that lets a user read the "
                   "figure against 'is this 1:1?'");
        CHECK_NEAR(cellShapeRatio(quad(-7, 3, -4, 3, -4, 6, -7, 6)), 1.0, 0.0,
                   "1. ...and so does a square of another size, somewhere else");
        // Rotated 30 degrees about the origin. The metric is built from midline
        // DISTANCES, so a rotation cannot move it; an axis-projected proxy would.
        const double c30 = std::cos(30.0 * M_PI / 180.0), s30 = std::sin(30.0 * M_PI / 180.0);
        auto rot = [&](double x, double y) {
            return Point2D{c30 * x - s30 * y, s30 * x + c30 * y};
        };
        const std::vector<Point2D> turned = {rot(0, 0), rot(1, 0), rot(1, 1), rot(0, 1)};
        CHECK_NEAR(cellShapeRatio(turned), 1.0, 1e-15,
                   "1. ...and a square turned 30 degrees is still 1.0, so the "
                   "figure is orientation-free");
    }

    // ── 2. A square split on its diagonal is sqrt(2), NOT 1.0 ────────────────
    // The parent ticket's whole reason for measuring the structured quad, and the
    // reason the quad figure and the triangle figure must not share a name.
    {
        const std::vector<Point2D> half = tri(0, 0, 1, 0, 1, 1);
        const std::vector<double> e = edges(half);
        // NEGATIVE CONTROL, computing this check's own premise: the two legs
        // really are equal and the hypotenuse really is the longer one, so the
        // sqrt(2) below is this triangle's own arithmetic and not a pasted 1.414.
        const double lo = *std::min_element(e.begin(), e.end());
        const double hi = *std::max_element(e.begin(), e.end());
        CHECK_NEAR(lo, 1.0, 1e-15, "2. the split triangle's shortest edge is the unit side");
        CHECK_NEAR(hi, std::sqrt(2.0), 1e-15, "2. ...and its longest is the diagonal");
        CHECK_NEAR(cellShapeRatio(half), std::sqrt(2.0), 1e-15,
                   "2. half a square measures sqrt(2) — so the SAME cell reports "
                   "1.0 as a quad and 1.414 as two triangles, which is why the two "
                   "metrics carry different names");
        CHECK_NEAR(cellShapeRatio(tri(0, 0, 1, 1, 0, 1)), std::sqrt(2.0), 1e-15,
                   "2. ...and so does the other half");
        CHECK_NEAR(cellShapeRatio(tri(0, 0, 1, 0, 0.5, std::sqrt(3.0) / 2.0)), 1.0, 1e-15,
                   "2. an equilateral triangle is exactly 1.0, so the triangle "
                   "metric has the same floor and the same meaning at it");
    }

    // ── 3. A rectangle measures its own side ratio ───────────────────────────
    {
        CHECK_NEAR(cellShapeRatio(quad(0, 0, 4, 0, 4, 1, 0, 1)), 4.0, 1e-15,
                   "3. a 4x1 rectangle measures 4.0 — its own side ratio, in the "
                   "units a user already has");
        CHECK_NEAR(cellShapeRatio(quad(0, 0, 1, 0, 1, 4, 0, 4)), 4.0, 1e-15,
                   "3. ...and so does the same rectangle stood on its end, so the "
                   "figure does not depend on which way round the corners run");
        CHECK_NEAR(cellShapeRatio(quad(0, 0, 0.001, 0, 0.001, 1, 0, 1)), 1000.0, 1e-9,
                   "3. a 1000:1 sliver measures 1000 rather than saturating");
    }

    // ── 4. A tapered cell: the edge ratio measures the TAPER, not the shape ──
    // This is what makes the metric a midline ratio rather than an edge ratio,
    // and the check computes BOTH numbers rather than asserting the difference.
    {
        // A symmetric trapezoid: 4 wide at the bottom, 2 at the top, 2 tall. Its
        // average width is 3, so its honest aspect ratio is 3:2.
        const std::vector<Point2D> taper = quad(0, 0, 4, 0, 3, 2, 1, 2);
        const std::vector<double> e = edges(taper);
        // NEGATIVE CONTROL, computing this check's own premise: the longest and
        // the shortest edge of this cell really are its BOTTOM and its TOP, which
        // are the same logical direction — so an edge-length proxy compares a cell
        // against itself along one axis and reports a number with no aspect in it.
        const double lo = *std::min_element(e.begin(), e.end());
        const double hi = *std::max_element(e.begin(), e.end());
        CHECK_NEAR(hi, e[0], 1e-15, "4. the tapered cell's longest edge is its bottom");
        CHECK_NEAR(lo, e[2], 1e-15,
                   "4. ...and its shortest is its top, the SAME logical direction");
        CHECK_NEAR(hi / lo, 2.0, 1e-15,
                   "4. ...so an edge-ratio proxy would report 2.0 for this cell");
        CHECK_NEAR(cellShapeRatio(taper), 1.5, 1e-15,
                   "4. the midline ratio reports 1.5 — three wide on average by two "
                   "tall, which is the cell's actual shape and not its taper");
    }

    // ── 4b. On a PARALLELOGRAM the two definitions AGREE ─────────────────────
    // Pinned so the argument above is not over-read: a sheared parallelogram is a
    // plausible-sounding discriminator and is not one, because each of its
    // midlines is a translate of a side.
    {
        const std::vector<Point2D> shear = quad(0, 0, 1, 0, 2, 1, 1, 1);
        const std::vector<double> e = edges(shear);
        const double lo = *std::min_element(e.begin(), e.end());
        const double hi = *std::max_element(e.begin(), e.end());
        CHECK_NEAR(hi / lo, std::sqrt(2.0), 1e-15,
                   "4b. the sheared parallelogram's edge ratio is sqrt(2)");
        CHECK_NEAR(cellShapeRatio(shear), hi / lo, 1e-15,
                   "4b. ...and its midline ratio is the SAME number, so this cell "
                   "does NOT tell the two definitions apart — check 4's does");
    }

    // ── 5. A trapezoid, where the two definitions disagree by construction ───
    {
        // Edges: bottom 4, right sqrt(1+1), top 2, left sqrt(1+1). Edge ratio 2.
        // Midlines: bottom-to-top (2,0)->(2,1) = 1; left-to-right = 3. Ratio 3.
        const std::vector<Point2D> trap = quad(0, 0, 4, 0, 3, 1, 1, 1);
        CHECK_NEAR(cellShapeRatio(trap), 3.0, 1e-15,
                   "5. a trapezoid measures its midline ratio (3.0), which is not "
                   "its edge ratio (2.0) — the two definitions are distinguished "
                   "by this cell and not merely by argument");
    }

    // ── 6. Degenerate cells: negative, never a division by zero ──────────────
    {
        CHECK(cellShapeRatio(quad(0, 0, 1, 0, 1, 0, 0, 0)) < 0.0,
              "6. a quad collapsed onto a line reports NEGATIVE rather than "
              "dividing by a zero midline");
        CHECK(cellShapeRatio(quad(0, 0, 0, 0, 0, 0, 0, 0)) < 0.0,
              "6. ...and so does a quad whose four corners coincide");
        CHECK(cellShapeRatio(tri(0, 0, 1, 0, 2, 0)) < 0.0 ||
              cellShapeRatio(tri(0, 0, 1, 0, 2, 0)) >= 1.0,
              "6. a collinear triangle either measures its real edge ratio or "
              "reports negative — what it must never do is report 0");
        CHECK(cellShapeRatio(tri(0, 0, 0, 0, 0, 0)) < 0.0,
              "6. a triangle whose corners coincide reports NEGATIVE");
        CHECK(cellShapeRatio({{0, 0}, {1, 1}}) < 0.0,
              "6. two corners are not a cell");
        CHECK(cellShapeRatio({}) < 0.0, "6. and neither is nothing");
        CHECK(cellShapeRatio({{0, 0}, {1, 0}, {1, 1}, {0.5, 1.5}, {0, 1}}) < 0.0,
              "6. a five-corner cell reports NEGATIVE rather than a guess: no "
              "metric is defined for it here");
    }

    // ── 7. Nothing measurable reports NEGATIVE, never 0.0 ────────────────────
    // 0.0 is not merely a flattering answer here, it is an IMPOSSIBLE one: the
    // metric's floor is 1.0, so a 0.0 could only ever be an absent measurement
    // wearing a number.
    {
        const ShapeStats empty = measureCellShapes({});
        CHECK(empty.cells == 0 && empty.median < 0.0 && empty.p95 < 0.0
              && empty.max < 0.0,
              "7. measuring no cells at all reports 0 measured cells and THREE "
              "negative figures, so an unmeasured mesh cannot read as a perfect one");
        const ShapeStats degenerate = measureCellShapes({quad(0, 0, 0, 0, 0, 0, 0, 0)});
        CHECK(degenerate.cells == 0 && degenerate.median < 0.0 && degenerate.p95 < 0.0
              && degenerate.max < 0.0,
              "7. ...and so does a mesh whose only cell could not be measured — the "
              "count is the cells MEASURED, not the cells offered");
        const ShapeStats none = reduceCellShapes({});
        CHECK(none.cells == 0 && none.median < 0.0 && none.p95 < 0.0 && none.max < 0.0,
              "7. the reducer alone obeys the same rule, so a caller that measures "
              "its own cells cannot reach a 0.0 either");
    }

    // ── 8. An unmeasurable cell is DROPPED, not folded in as a small value ───
    {
        const ShapeStats s = measureCellShapes({
            quad(0, 0, 1, 0, 1, 1, 0, 1),        // 1.0
            quad(0, 0, 0, 0, 0, 0, 0, 0),        // unmeasurable
            quad(0, 0, 3, 0, 3, 1, 0, 1),        // 3.0
        });
        CHECK(s.cells == 2,
              "8. two of the three cells were measurable, and the count says two");
        CHECK_NEAR(s.median, 2.0, 1e-15,
                   "8. ...and the median is the mean of 1 and 3, so the "
                   "unmeasurable cell did not join the statistics as a zero");
        CHECK_NEAR(s.max, 3.0, 1e-15, "8. ...with the worst cell as the max");
    }

    // ── 9. The two percentile rules, on a set whose answer is hand-countable ─
    {
        // 20 values, 1.0 .. 20.0. Median = mean of the 10th and 11th = 10.5;
        // p95 nearest rank = ceil(0.95*20) = 19th = 19.0; max = 20.0. Every one
        // of the three is a different number, so a check cannot pass by accident.
        std::vector<double> v;
        for (int k = 1; k <= 20; ++k) v.push_back(static_cast<double>(k));
        const ShapeStats s = reduceCellShapes(v);
        CHECK(s.cells == 20, "9. twenty values reduce to twenty measured cells");
        CHECK_NEAR(s.median, 10.5, 1e-15,
                   "9. the median of an EVEN count is the mean of the two middle "
                   "values (10 and 11), not either one of them");
        CHECK_NEAR(s.p95, 19.0, 1e-15,
                   "9. p95 is NEAREST RANK: the 19th of 20, an actual value, not "
                   "an interpolation between the 19th and the 20th");
        CHECK_NEAR(s.max, 20.0, 1e-15, "9. and the max is the last one");
        // Order in must not matter.
        std::reverse(v.begin(), v.end());
        const ShapeStats r = reduceCellShapes(v);
        CHECK(r.cells == s.cells && r.median == s.median && r.p95 == s.p95
              && r.max == s.max,
              "9. handing the same values in the opposite order reports the same "
              "three figures, so the reducer sorts rather than trusts its input");
        // One value: every figure is that value, and p95 cannot fall off the end.
        const ShapeStats one = reduceCellShapes({2.5});
        CHECK(one.cells == 1 && one.median == 2.5 && one.p95 == 2.5 && one.max == 2.5,
              "9. a single cell is its own median, p95 and max — the nearest rank "
              "clamps to it instead of reaching past the end");
    }

    // ── 10. The median is not the mean, and the max is not the median ────────
    // The parent ticket's reason for reporting three numbers: one outlier must not
    // be able to speak for the mesh, and the mean lets it.
    {
        std::vector<double> v(99, 1.1);
        v.push_back(70.0);                       // one boundary-layer cell
        const ShapeStats s = reduceCellShapes(v);
        double mean = 0.0;
        for (double x : v) mean += x;
        mean /= static_cast<double>(v.size());
        CHECK_NEAR(s.median, 1.1, 1e-15,
                   "10. one cell at 70 among ninety-nine at 1.1 leaves the median "
                   "at 1.1, which is what the other 99% of the mesh looks like");
        CHECK_NEAR(s.p95, 1.1, 1e-15,
                   "10. ...and p95 too, because a single outlier is 1% and not 5%");
        CHECK_NEAR(s.max, 70.0, 1e-15, "10. ...while the max still reports it");
        CHECK(mean > 1.5,
              "10. NEGATIVE CONTROL: the MEAN of that same set is dragged past 1.5 "
              "by the one cell, which is the figure this ticket replaces");
    }

    return hybmesh::test::report("test_cell_shape");
}
