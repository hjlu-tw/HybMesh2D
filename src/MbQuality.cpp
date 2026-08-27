#include "MbQuality.hpp"

#include <algorithm>
#include <cmath>

namespace {

// A cell corner is CONVEX-and-correctly-wound when the turn from the incoming
// edge to the outgoing one is counter-clockwise. `<= 0` therefore catches a
// reflex corner, a folded (self-intersecting) quad and a degenerate one in the
// same test.
//
// For a triangle all three corners share this value with twice the signed area,
// so the rule reduces to "signed area <= 0" there — one rule for both cell
// kinds, and NOT the signed area itself: a bow-tie quad can self-intersect with
// a positive shoelace area, which the obvious area-based implementation passes.
bool cornerIsBad(const Point2D& prev, const Point2D& cur, const Point2D& next) {
    return (cur - prev).cross(next - cur) <= 0.0;
}

bool cellIsInverted(const std::vector<Point2D>& nodes, const std::vector<int>& ids) {
    // A "cell" that is not a polygon is not a usable cell. Counted rather than
    // skipped, so a producer that emits one cannot hide behind a clean report.
    if (ids.size() < 3) return true;
    const size_t n = ids.size();
    // A node id that names nothing is not a cell we can vouch for, and reporting
    // it as sound would be the one wrong answer here.
    for (int id : ids)
        if (id < 0 || static_cast<size_t>(id) >= nodes.size()) return true;
    for (size_t k = 0; k < n; ++k)
        if (cornerIsBad(nodes[static_cast<size_t>(ids[(k + n - 1) % n])],
                        nodes[static_cast<size_t>(ids[k])],
                        nodes[static_cast<size_t>(ids[(k + 1) % n])]))
            return true;
    return false;
}

// The interior angle at `o` between the two edges to `a` and `b`, in degrees.
// Returns a negative value when either edge has no direction, so the caller can
// leave the sample OUT of the statistics rather than fabricate a 90-degree
// deviation for a pair of coincident nodes (which the inverted count already
// reports, on its own terms).
double interiorAngleDeg(const Point2D& o, const Point2D& a, const Point2D& b) {
    const Vector2D u = a - o, v = b - o;
    const double lu = u.length(), lv = v.length();
    if (lu <= 0.0 || lv <= 0.0) return -1.0;
    const double c = std::max(-1.0, std::min(1.0, u.dot(v) / (lu * lv)));
    return std::acos(c) * 180.0 / M_PI;
}

}  // namespace

hybmesh::MbQualityReport hybmesh::measureMbQuality(const MbResult& mesh) {
    MbQualityReport q;
    q.cells = mesh.cells.size();

    // ── Inverted cells: over the cells that are EXPORTED ────────────────────
    for (const MbCell& c : mesh.cells)
        if (cellIsInverted(mesh.nodes, c.nodeIds)) ++q.invertedCells;

    // ── Non-orthogonality: the corner angles of the STRUCTURED cells ────────
    // Read off the block's logical i/j, which is retained for exactly this kind
    // of question. Independent of how (or whether) the quads were split.
    double sum = 0.0;
    for (const MbBlock& b : mesh.blocks) {
        const size_t want = static_cast<size_t>(b.ni) * static_cast<size_t>(b.nj);
        if (b.ni < 2 || b.nj < 2 || b.nodeIds.size() != want) continue;
        for (int j = 0; j + 1 < b.nj; ++j) {
            for (int i = 0; i + 1 < b.ni; ++i) {
                const int ids[4] = {b.nodeAt(i, j), b.nodeAt(i + 1, j),
                                    b.nodeAt(i + 1, j + 1), b.nodeAt(i, j + 1)};
                bool inRange = true;
                for (int k = 0; k < 4; ++k)
                    if (ids[k] < 0 || static_cast<size_t>(ids[k]) >= mesh.nodes.size())
                        inRange = false;
                if (!inRange) continue;
                for (int k = 0; k < 4; ++k) {
                    const double a = interiorAngleDeg(
                        mesh.nodes[static_cast<size_t>(ids[k])],
                        mesh.nodes[static_cast<size_t>(ids[(k + 1) % 4])],
                        mesh.nodes[static_cast<size_t>(ids[(k + 3) % 4])]);
                    if (a < 0.0) continue;
                    const double dev = std::fabs(90.0 - a);
                    q.maxNonOrthoDeg = std::max(q.maxNonOrthoDeg, dev);
                    sum += dev;
                    ++q.nonOrthoSamples;
                }
            }
        }
    }
    // maxNonOrthoDeg came up from its -1 default through std::max the moment a
    // sample landed, so both figures stay negative exactly when nothing was
    // measured — which is what stops a mesh with no structured block reporting
    // the excellent-looking 0.000 deg. See MbQualityReport.
    if (q.nonOrthoSamples > 0)
        q.meanNonOrthoDeg = sum / static_cast<double>(q.nonOrthoSamples);

    // ── Wall first-cell height: what was asked for, against what was filled ──
    for (const MbWallSpec& ws : mesh.wallSpecs) {
        if (ws.block < 0 || static_cast<size_t>(ws.block) >= mesh.blocks.size()) continue;
        const MbBlock& b = mesh.blocks[static_cast<size_t>(ws.block)];
        const size_t want = static_cast<size_t>(b.ni) * static_cast<size_t>(b.nj);
        if (b.ni < 2 || b.nj < 2 || b.nodeIds.size() != want) continue;

        // Walk the side, and step ONE grid line inward at each position. Both
        // facts come from `mbSideAxis` rather than from a cascade over the four
        // side values here: the convention has one home (include/MultiBlock.hpp),
        // and the publisher of the request reads the same one.
        const MbSideAxis ax = mbSideAxis(ws.side);
        const int n = ax.alongI ? b.ni : b.nj;   // positions along the side
        const int m = ax.alongI ? b.nj : b.ni;   // extent across it
        const int t0 = ax.atFarEnd ? m - 1 : 0;  // the on-wall grid line
        const int t1 = ax.atFarEnd ? m - 2 : 1;  // one line inward from it
        MbWallHeight w;
        w.edgeId = ws.edgeId;
        w.side = ax.name;
        w.requestedLo = ws.requestedLo;
        w.requestedHi = ws.requestedHi;

        bool any = false;      // at least one position had nodes to measure
        bool asked = false;    // ...and a POSITIVE requested height to measure against
        double worst = 0.0;
        for (int k = 0; k < n; ++k) {
            const int i0 = ax.alongI ? k : t0, j0 = ax.alongI ? t0 : k;
            const int i1 = ax.alongI ? k : t1, j1 = ax.alongI ? t1 : k;
            const int a = b.nodeAt(i0, j0), c = b.nodeAt(i1, j1);
            if (a < 0 || c < 0 || static_cast<size_t>(a) >= mesh.nodes.size()
                || static_cast<size_t>(c) >= mesh.nodes.size())
                continue;
            const double got = (mesh.nodes[static_cast<size_t>(c)]
                              - mesh.nodes[static_cast<size_t>(a)]).length();
            if (!any) { w.achievedMin = w.achievedMax = got; any = true; }
            w.achievedMin = std::min(w.achievedMin, got);
            w.achievedMax = std::max(w.achievedMax, got);

            // The request between the two corners is the SAME linear blend in the
            // logical coordinate that the transfinite fill uses, so a rectangle
            // asks for one number and gets it exactly, and the figure is nonzero
            // only where the fill genuinely could not honour the declaration.
            const double u = (n > 1) ? static_cast<double>(k) / (n - 1) : 0.0;
            const double req = (1.0 - u) * ws.requestedLo + u * ws.requestedHi;
            if (req > 0.0) {
                asked = true;
                worst = std::max(worst, std::fabs(got - req) / req);
            }
        }
        if (!any) continue;
        // A wall the request said nothing measurable about keeps its NEGATIVE
        // `worstRelError` and does not reach the headline. Accumulating a 0.0 for
        // it would report the best possible accuracy for a wall nobody could
        // measure, which is the one wrong answer this report has (see
        // MbQualityReport) — and a degenerate perpendicular edge is exactly how a
        // zero request arises. The row is still LISTED, because a wall that could
        // not be measured is worth seeing.
        if (asked) {
            w.worstRelError = worst;
            q.worstWallRelError = std::max(q.worstWallRelError, worst);
        }
        q.walls.push_back(w);
    }

    return q;
}
