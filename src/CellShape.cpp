#include "CellShape.hpp"

#include <algorithm>
#include <cmath>

namespace {

// The distance between the midpoints of two edges, each given by its two corners.
double midlineLength(const Point2D& a0, const Point2D& a1,
                     const Point2D& b0, const Point2D& b1) {
    const Point2D ma{(a0.x + a1.x) * 0.5, (a0.y + a1.y) * 0.5};
    const Point2D mb{(b0.x + b1.x) * 0.5, (b0.y + b1.y) * 0.5};
    return (mb - ma).length();
}

// The ratio of the larger to the smaller, or NEGATIVE when the smaller is not a
// positive length. Never divides by zero, and never returns 0 or infinity: the
// one caller-visible "no" is a negative number.
double ratioOf(double a, double b) {
    const double lo = std::min(a, b), hi = std::max(a, b);
    if (!(lo > 0.0)) return -1.0;   // catches 0, a negative and a NaN alike
    return hi / lo;
}

}  // namespace

double hybmesh::cellShapeRatio(const std::vector<Point2D>& corners) {
    if (corners.size() == 3) {
        // Longest edge / shortest edge.
        double lo = -1.0, hi = -1.0;
        for (size_t k = 0; k < 3; ++k) {
            const double e = (corners[(k + 1) % 3] - corners[k]).length();
            if (lo < 0.0 || e < lo) lo = e;
            if (e > hi) hi = e;
        }
        return ratioOf(lo, hi);
    }
    if (corners.size() == 4) {
        // The two OPPOSITE-EDGE midlines, read from `quadExtents` below rather
        // than taken again here: exactly 1.0 on a square, exactly the side ratio
        // on a rectangle, and unchanged by rotating the cell. One home for the
        // arithmetic, because the multi-block wall band (#144) needs the same two
        // lengths without the ratio and a second copy is the one that drifts.
        double e01 = 0.0, e12 = 0.0;
        quadExtents(corners, e01, e12);
        return ratioOf(e01, e12);
    }
    // Fewer than 3 corners is not a cell; more than 4 has no metric defined here,
    // and a guess would be worse than the honest negative. See CellShape.hpp.
    return -1.0;
}

bool hybmesh::quadExtents(const std::vector<Point2D>& corners, double& extent01,
                          double& extent12) {
    if (corners.size() != 4) return false;
    // The extent in the 0->1 direction is the midline between the two edges that
    // CROSS it (1-2 and 3-0), and vice versa. Getting these two the wrong way
    // round is invisible in `cellShapeRatio`, which takes max over min — and is
    // exactly what the wall band would get wrong, so the naming is by DIRECTION
    // rather than by the edges each midline joins.
    extent01 = midlineLength(corners[1], corners[2], corners[3], corners[0]);
    extent12 = midlineLength(corners[0], corners[1], corners[2], corners[3]);
    return true;
}

hybmesh::ShapeStats hybmesh::reduceCellShapes(std::vector<double> ratios) {
    ShapeStats s;
    // A negative entry is "this one could not be measured", not a small value, so
    // it is dropped rather than sorted in beside the real ones — where it would
    // drag the median down and make an unmeasurable mesh look better than a
    // measurable one.
    ratios.erase(std::remove_if(ratios.begin(), ratios.end(),
                                [](double v) { return !(v > 0.0); }),
                 ratios.end());
    if (ratios.empty()) return s;   // every figure stays negative; cells stays 0
    std::sort(ratios.begin(), ratios.end());
    const size_t n = ratios.size();
    s.cells = n;
    s.median = (n % 2 == 1) ? ratios[n / 2]
                            : 0.5 * (ratios[n / 2 - 1] + ratios[n / 2]);
    // Nearest rank, counting from 1, then back to a 0-based index. n == 1 gives
    // rank 1, and the clamp is belt-and-braces against a rounding surprise.
    size_t rank = static_cast<size_t>(std::ceil(0.95 * static_cast<double>(n)));
    if (rank < 1) rank = 1;
    if (rank > n) rank = n;
    s.p95 = ratios[rank - 1];
    s.max = ratios[n - 1];
    return s;
}

hybmesh::ShapeStats hybmesh::measureCellShapes(
    const std::vector<std::vector<Point2D>>& cells) {
    std::vector<double> ratios;
    ratios.reserve(cells.size());
    for (const std::vector<Point2D>& c : cells) ratios.push_back(cellShapeRatio(c));
    return reduceCellShapes(std::move(ratios));
}
