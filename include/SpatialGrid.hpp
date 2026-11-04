#ifndef SPATIAL_GRID_HPP
#define SPATIAL_GRID_HPP

#include "GeomUtils.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <vector>

// A UNIFORM BUCKET INDEX OVER 2D POINTS, in CSR form (issue #180).
//
// WHAT IT IS FOR. Every test in the cross-geometry collision phase asks the same
// question — "is anything within `th` of here" — and before #180 all three asked
// it by scanning: A over every node of the mesh, B over every candidate of every
// other front, B2 over every segment of every other front's committed ring. On
// `config/hybrid_30p30n.dat` at `BL_LAYERS 120` that was 137-144 s of a 143 s
// boundary-layer phase, against 0.14 s with `ENABLE_COLLISION_DETECTION 0`.
//
// IT PRUNES, IT DOES NOT DECIDE. `forEachNear` hands back every point whose CELL
// overlaps the query box, which is a superset of the points within `r`: the
// caller still runs its own exact comparison on each one. That is deliberate and
// it is what makes #180 a pure speed change — the index cannot move a node,
// because it never answers the question, it only shortens the list of things the
// unchanged comparison is run against. A missed point WOULD change the answer,
// so the gate (`tests/cpp/test_spatial_grid.cpp`) is written against a
// brute-force oracle and asserts a SUPERSET, never an equality.
//
// WHY A SUPERSET AND NOT A RADIUS FILTER. Two of the three callers do not ask
// about a radius at all: B2 asks whether two SEGMENTS cross, and reaches this
// index through the midpoint bound (see `forEachNear`'s note below). A grid that
// filtered by distance would be useless to it.
//
// CELL SIZE. `hintRadius` is the radius most queries will use, and is the
// natural cell size: at one cell per radius a query touches 2x2 cells. But the
// boundary layer's threshold is a FIRST CELL HEIGHT — 5.4e-5 on the 30P30N case
// against a 1.1 x 0.35 ribbon bounding box — so honouring it literally would ask
// for 140 million cells. The cell is therefore grown until the grid fits
// `maxCells`, which trades a few more points per query for a bounded build. The
// index stays exact either way; only the pruning gets weaker.
//
// IT HOLDS NO POINTS. `build` keeps a permutation of INDICES, and `forEachNear`
// hands those indices back, so the caller reads its own array — a mesh node, a
// candidate, a ring segment — rather than a copy this class would have to keep
// in step. Buffers are reused across `build` calls, so one instance hoisted out
// of the layer loop allocates once per run rather than once per layer.
// THE ONE-CELL VERSION OF THE SAME PRUNING: an axis-aligned extent, for
// rejecting a whole pair of point sets before either is walked. It lives here
// rather than inside its caller because it is the same idea as the grid at the
// coarsest possible resolution, and because `BoundaryLayer::generate()` is a
// function nothing should be added to.
struct Bounds2D {
    double x0 = 0, y0 = 0, x1 = 0, y1 = 0;
    bool empty = true;
    void add(Point2D p) {
        if (empty) { x0 = x1 = p.x; y0 = y1 = p.y; empty = false; return; }
        x0 = std::min(x0, p.x); x1 = std::max(x1, p.x);
        y0 = std::min(y0, p.y); y1 = std::max(y1, p.y);
    }
    // Inclusive, and padded on THIS extent only: it reports false only when no
    // point of one set can be within `pad` of any point of the other, so a
    // rejection can never drop something the inner loop would have found.
    bool overlaps(const Bounds2D& o, double pad) const {
        return !empty && !o.empty
            && x0 - pad <= o.x1 && o.x0 <= x1 + pad
            && y0 - pad <= o.y1 && o.y0 <= y1 + pad;
    }
};

class SpatialGrid {
public:
    // Index `pts[0..n)`. Safe on n == 0, on coincident points, and on a cloud
    // with no extent in one axis (every point on one line).
    void build(const Point2D* pts, std::size_t n, double hintRadius) {
        m_count = n;
        if (n == 0) { m_nx = m_ny = 0; return; }

        m_x0 = m_x1 = pts[0].x;
        m_y0 = m_y1 = pts[0].y;
        for (std::size_t i = 1; i < n; ++i) {
            m_x0 = std::min(m_x0, pts[i].x); m_x1 = std::max(m_x1, pts[i].x);
            m_y0 = std::min(m_y0, pts[i].y); m_y1 = std::max(m_y1, pts[i].y);
        }
        const double w = m_x1 - m_x0, h = m_y1 - m_y0;

        // Cap the grid at a few cells per point: the memory and the per-layer
        // clear are both proportional to the CELL count, so an unbounded one is
        // slower than the scan it replaces.
        const double maxCells = std::min(4.0 * (double)n + 64.0, 4.0e6);
        m_cell = (hintRadius > 0.0 && std::isfinite(hintRadius)) ? hintRadius : 0.0;
        const double area = std::max(w, 0.0) * std::max(h, 0.0);
        if (area > 0.0) m_cell = std::max(m_cell, std::sqrt(area / maxCells));
        if (!(m_cell > 0.0)) m_cell = std::max({w, h, 1.0});
        while (true) {
            double fx = std::floor(w / m_cell) + 1.0, fy = std::floor(h / m_cell) + 1.0;
            if (fx * fy <= maxCells) { m_nx = (int)fx; m_ny = (int)fy; break; }
            m_cell *= 2.0;
        }

        const std::size_t cells = (std::size_t)m_nx * (std::size_t)m_ny;
        m_start.assign(cells + 1, 0);
        m_order.resize(n);
        for (std::size_t i = 0; i < n; ++i) ++m_start[cellOf(pts[i]) + 1];
        for (std::size_t c = 0; c < cells; ++c) m_start[c + 1] += m_start[c];
        m_fill = m_start;                       // running cursor per cell
        for (std::size_t i = 0; i < n; ++i) m_order[m_fill[cellOf(pts[i])]++] = (int)i;
    }

    // Call `f(i)` for every point index `i` whose cell overlaps the square
    // [p.x +/- r] x [p.y +/- r]. `f` returns false to stop the walk early.
    //
    // THE BOX IS THE CONTRACT, not a disc: a caller asking "within r" gets a
    // superset because |dx| < r and |dy| < r hold for anything with d^2 < r^2.
    // The segment caller (B2) uses the same box through a different bound: two
    // segments that properly cross share the crossing point X, so each midpoint
    // is within half its own length of X and the two midpoints are therefore
    // within (lenA + lenB)/2 of each other. That is why r is a parameter here
    // and not baked into `build`.
    template <class F>
    void forEachNear(Point2D p, double r, F&& f) const {
        if (m_count == 0 || m_nx == 0 || m_ny == 0) return;
        if (p.x + r < m_x0 || p.x - r > m_x1 || p.y + r < m_y0 || p.y - r > m_y1) return;
        const int i0 = clampIdx((p.x - r - m_x0) / m_cell, m_nx);
        const int i1 = clampIdx((p.x + r - m_x0) / m_cell, m_nx);
        const int j0 = clampIdx((p.y - r - m_y0) / m_cell, m_ny);
        const int j1 = clampIdx((p.y + r - m_y0) / m_cell, m_ny);
        for (int j = j0; j <= j1; ++j) {
            const std::size_t row = (std::size_t)j * (std::size_t)m_nx;
            for (int i = i0; i <= i1; ++i) {
                const std::size_t c = row + (std::size_t)i;
                for (int k = m_start[c]; k < m_start[c + 1]; ++k)
                    if (!f(m_order[k])) return;
            }
        }
    }

    // BOTH ACCESSORS BELOW EXIST FOR THE GATE and have no production caller.
    // `cells()` is what the growth loop in `build` bounds -- an unbounded grid
    // is slower than the scan it replaces rather than wrong, so no caller may
    // branch on it -- and `size()` is how an empty cloud is asserted to say so.
    std::size_t size() const { return m_count; }
    std::size_t cells() const { return (std::size_t)m_nx * (std::size_t)m_ny; }

private:
    std::size_t cellOf(Point2D p) const {
        return (std::size_t)clampIdx((p.y - m_y0) / m_cell, m_ny) * (std::size_t)m_nx
             + (std::size_t)clampIdx((p.x - m_x0) / m_cell, m_nx);
    }
    // Clamped in DOUBLE before the cast: a query far outside the cloud would
    // otherwise overflow the int conversion rather than land on the edge cell.
    static int clampIdx(double v, int n) {
        if (!(v > 0.0)) return 0;                   // also catches NaN
        if (v >= (double)(n - 1)) return n - 1;
        return (int)v;
    }

    std::size_t m_count = 0;
    int m_nx = 0, m_ny = 0;
    double m_x0 = 0, m_y0 = 0, m_x1 = 0, m_y1 = 0, m_cell = 1.0;
    std::vector<int> m_start, m_fill;
    std::vector<int> m_order;
};

#endif
