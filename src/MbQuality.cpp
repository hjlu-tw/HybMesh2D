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

// A block is walkable as a structured grid when it is at least 2x2 and its id
// array is the size its own ni/nj declare. Both structured-cell loops below ask
// this, and asking it in two places is how they would come to disagree about which
// cells are "the structured cells" — the phrase both figures' headers use.
bool blockIsWalkable(const hybmesh::MbBlock& b) {
    return b.ni >= 2 && b.nj >= 2
        && b.nodeIds.size() == static_cast<size_t>(b.ni) * static_cast<size_t>(b.nj);
}

// The four corners of the structured cell at logical (i, j), AROUND THE RING:
// (i,j) (i+1,j) (i+1,j+1) (i,j+1). False when any of the four ids names no node,
// and then `out` is not to be read.
//
// ONE HOME FOR THE RING ORDER, and that is the point of the helper rather than a
// tidy-up. Both figures measured on the structured cells depend on it — the corner
// angles' deviation from 90 degrees and the opposite-edge midline ratio — and
// reading the four in Z order instead is the classic transcription slip (injection
// J of tests/cpp/test_mb_quality.cpp, 11 failures). Written twice, one copy could
// have it and the other not, and the two figures would describe different cells
// while both calling them "the structured cells".
bool quadCorners(const hybmesh::MbResult& mesh, const hybmesh::MbBlock& b, int i, int j,
                 Point2D out[4]) {
    const int ids[4] = {b.nodeAt(i, j), b.nodeAt(i + 1, j),
                        b.nodeAt(i + 1, j + 1), b.nodeAt(i, j + 1)};
    for (int k = 0; k < 4; ++k) {
        if (ids[k] < 0 || static_cast<size_t>(ids[k]) >= mesh.nodes.size()) return false;
        out[k] = mesh.nodes[static_cast<size_t>(ids[k])];
    }
    return true;
}

// See the comparison inside `wallBandMask` below for what this is and what it is
// NOT. Above that function's own doc block rather than between the two, so the
// block reads as the function's and not as this constant's.
constexpr double TIE_REL = 1e-12;

// WHICH OF ONE BLOCK'S STRUCTURED QUADS THE WALL CLUSTERING SQUEEZED (issue
// #144), as a mask indexed `j * (ni - 1) + i`. Empty for a block this report
// cannot walk, and all zeroes for a block no `wall` side of which was declared —
// which is how "a block with no wall side is all bulk" holds without a rule of
// its own.
//
// The walk starts ON the declared side and steps outward one cell at a time,
// stopping at the first cell whose extent ACROSS the side is not shorter than its
// extent ALONG it. That comparison is the whole definition of the band and it
// carries no cut-off: no radius, no layer count, no multiple of the first-cell
// height. See MbQualityReport, where the rule and the measurement behind it are
// stated.
//
// PER STATION ALONG THE SIDE, not per row: `k` walks the side and `d` walks away
// from it, so each station stops where its own clustering stops. A `break` ends
// that station's walk and not the side's.
//
// TWO SIDES OF ONE BLOCK MAY BOTH BE WALLS (the shipped O-grid's body arc and its
// far-field arc both are), so this is a UNION over the block's declared sides. A
// cell reached from either is in the band once; the mask cannot double-count it,
// which is what keeps the two sets a partition.
std::vector<char> wallBandMask(const hybmesh::MbResult& mesh, size_t blockIdx) {
    const hybmesh::MbBlock& b = mesh.blocks[blockIdx];
    if (!blockIsWalkable(b)) return {};
    const size_t nci = static_cast<size_t>(b.ni - 1);
    std::vector<char> mask(nci * static_cast<size_t>(b.nj - 1), 0);
    for (const hybmesh::MbWallSpec& ws : mesh.wallSpecs) {
        if (ws.block < 0 || static_cast<size_t>(ws.block) != blockIdx) continue;
        const hybmesh::MbSideWalk w = hybmesh::mbSideWalk(b, ws.side);
        if (!w.ok) continue;
        for (int k = 0; k + 1 < w.n; ++k) {
            for (int d = 0; d + 1 < w.m; ++d) {
                // The cell's LOW transverse index, counting away from the side:
                // at the near end that is `d`, at the far end the block is walked
                // inward from its last cell. `mbSideAxis` owns which of the two a
                // side is, here as everywhere else in this file.
                const int tlo = w.ax.atFarEnd ? (w.m - 2 - d) : d;
                const int i = w.ax.alongI ? k : tlo;
                const int j = w.ax.alongI ? tlo : k;
                Point2D c[4];
                // A cell this report cannot resolve ends the walk rather than
                // being guessed past: nothing here can say whether it was
                // clustered, and marking it either way would be an answer nobody
                // measured. It still reaches the statistics, as the unmeasurable
                // cell it is, through the loop below.
                if (!quadCorners(mesh, b, i, j, c)) break;
                double e01 = 0.0, e12 = 0.0;   // extents along i and along j
                if (!hybmesh::quadExtents({c[0], c[1], c[2], c[3]}, e01, e12)) break;
                // A side running along i is crossed in j, and vice versa. Both
                // lengths must be positive: a degenerate cell has no shorter
                // direction, and reading its 0 as "very thin" would put a cell
                // nobody could measure at the head of the band.
                const double across = w.ax.alongI ? e12 : e01;
                const double along = w.ax.alongI ? e01 : e12;
                if (!(across > 0.0) || !(along > 0.0)) break;
                // TWO EXTENTS THAT AGREE TO WITHIN ROUNDING ARE NOT A SQUEEZED
                // CELL, and this is a FLOATING-POINT EQUALITY tolerance rather
                // than a physical cut-off: it decides ties, never how far the
                // band reaches. A bare `across < along` was measured on the
                // shipped square — a 1x1 domain filled with 400 geometrically
                // IDENTICAL 0.05-by-0.05 cells — and banded 72 of them, because
                // the two midlines of a square come out of a few adds and a
                // `hypot` a last bit apart and the sign of that bit is noise. A
                // uniform grid clusters nothing, and the report now says so.
                // 3.7 orders above a double's own epsilon, and TEN below the
                // nearest margin any shipped case has: the O-grid's first
                // UNBANDED cell misses the tie by 1.2% and its shallowest banded
                // one by 8.9%. (An earlier draft of this comment said TWELVE,
                // comparing the tolerance against 1 rather than against the
                // margin the sentence's own parenthetical names.) It empties the
                // square's spurious 72 and the cavity's 0, and moves no other
                // shipped case's band by a single cell.
                if (!(across < along * (1.0 - TIE_REL))) break;
                mask[static_cast<size_t>(j) * nci + static_cast<size_t>(i)] = 1;
            }
        }
    }
    return mask;
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
        if (!blockIsWalkable(b)) continue;
        for (int j = 0; j + 1 < b.nj; ++j) {
            for (int i = 0; i + 1 < b.ni; ++i) {
                Point2D c[4];
                if (!quadCorners(mesh, b, i, j, c)) continue;
                for (int k = 0; k < 4; ++k) {
                    const double a = interiorAngleDeg(c[k], c[(k + 1) % 4], c[(k + 3) % 4]);
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

    // ── Cell shape: the STRUCTURED quads, per block and overall ─────────────
    // Same loop shape as the angles above and the same reason for it — the (i,j)
    // quads are the cells the document declares — but the per-cell arithmetic is
    // the SHARED pure one, so this path and the hybrid path cannot drift apart on
    // what "badly shaped" means. A block that yields nothing measurable is still
    // LISTED, with its own figures negative, for the reason the unmeasurable wall
    // row is listed: a block nobody could measure is worth seeing.
    //
    // AND SPLIT IN TWO SINCE #144: the same per-cell ratio goes into the whole-mesh
    // set and into exactly one of the wall band and the bulk, so the two halves
    // partition what the whole set measured by construction. The mask decides
    // which, and an unmeasurable cell is dropped from all three by the one rule in
    // `reduceCellShapes` — so no rule about measurability can hold in one set and
    // not another.
    {
        std::vector<double> all, band, rest;
        for (size_t bi = 0; bi < mesh.blocks.size(); ++bi) {
            const MbBlock& b = mesh.blocks[bi];
            MbBlockShape row;
            row.blockId = b.id;
            std::vector<double> mine;
            const std::vector<char> mask = wallBandMask(mesh, bi);
            if (blockIsWalkable(b)) {
                for (int j = 0; j + 1 < b.nj; ++j) {
                    for (int i = 0; i + 1 < b.ni; ++i) {
                        Point2D c[4];
                        // A quad one of whose ids names nothing is UNMEASURABLE, and
                        // is pushed as such rather than handed on short: three
                        // resolving corners would reach `cellShapeRatio` as a TRIANGLE
                        // and come back with a perfectly ordinary edge ratio for a
                        // cell nobody could measure. Check 9e is that case, and is why
                        // `quadCorners` returns all four or none.
                        const double r = quadCorners(mesh, b, i, j, c)
                                             ? cellShapeRatio({c[0], c[1], c[2], c[3]})
                                             : -1.0;
                        mine.push_back(r);
                        const size_t idx = static_cast<size_t>(j)
                                             * static_cast<size_t>(b.ni - 1)
                                         + static_cast<size_t>(i);
                        (mask[idx] ? band : rest).push_back(r);
                    }
                }
            }
            all.insert(all.end(), mine.begin(), mine.end());
            row.shape = reduceCellShapes(std::move(mine));
            q.blockShapes.push_back(std::move(row));
        }
        q.structuredShape = reduceCellShapes(std::move(all));
        q.structuredLayerShape = reduceCellShapes(std::move(band));
        q.structuredBulkShape = reduceCellShapes(std::move(rest));
    }

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
