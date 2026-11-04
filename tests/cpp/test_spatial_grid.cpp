// THE UNIFORM BUCKET INDEX THE COLLISION PHASE PRUNES WITH (#180).
//
// WHAT THIS FILE GUARDS, and why it is the only thing standing between a speed
// change and a changed mesh. `SpatialGrid` does not answer any of the collision
// phase's questions; it shortens the list each unchanged comparison is run
// against. So the ONE property that matters is that the list is a SUPERSET of
// the brute-force answer — a point the grid drops is a node that stops freezing,
// and `tools/scripts/golden_mesh.py` would see it as a moved mesh several
// minutes later with no idea why. Every check below is therefore written
// against a brute-force oracle over the same cloud, and asserts containment,
// never equality: returning too much is slow, returning too little is wrong.
//
// IT LINKS NOTHING, like `test_spacing_two_sided.cpp` beside it. `SpatialGrid`
// is arithmetic over coordinates and `std::vector`, so this executable failing
// to build is the signal that it has grown a dependency on a mesh, a front or
// gmsh — the property that lets the three collision tests, which know about all
// three, share one index.
//
// THE CLOUDS ARE THE CALLERS' SHAPES, not round numbers: check 2 is a thin
// ribbon inside a wide box, which is what a boundary layer IS, and it is the
// shape that breaks a grid sized naively from the query radius.
//
// INJECTIONS (hand runs, 2026-11-04; each reverted):
//   I1  `forEachNear`'s i0/j0 clamped to the UPPER index (`p.x + r` at both
//       ends), i.e. one cell scanned instead of the span -> 13 checks red,
//       first 1 at r=0.01.
//   I2  the early-out box test widened from `<` to `<=` -> check 6 red, and
//       ONLY check 6: a point exactly r away is the single case that separates
//       the two, which is why that check is worth its three lines.
//   I3  `clampIdx` losing its negative/NaN guard (keeping the upper clamp, so
//       it still compiles) -> the executable dies with SIGBUS, exit 138, on
//       check 4's query at the cloud's left edge. A crash IS the red here:
//       ctest's verdict is the executable's own exit code.
//   I4  `build`'s cell-growth loop removed -> checks 2c and 8 red (962,136
//       cells for 240,000 points; 681,176 for 100). IT WAS INERT WHEN FIRST
//       RUN: the cell is also sized from sqrt(area / maxCells), which bounds a
//       square cloud on its own, so nothing here could see the loop until 2c
//       and 8 were added to measure the CELL COUNT. The loop is what bounds the
//       one shape that estimate misses, and check 8 is that shape.
//   I5  the midpoint bound in check 7 relaxed to (lenA + lenB)/4 -> check 7 red
//       on the first crossing, confirming the bound B2 rests on is the tight
//       one and not a guess.
//   I6  `Bounds2D::overlaps` padding the WRONG side (`x0 + pad <= o.x1 &&
//       o.x0 <= x1 - pad`, i.e. shrinking) -> 9a red: a pair with a point
//       inside the pad was rejected.
//   I7  `Bounds2D::overlaps` stuck at `return true` -> 9a and 9b stay GREEN
//       (nothing is ever rejected, so nothing is wrongly rejected) and 9c is
//       what fails, at 0 of 4000. That asymmetry is the reason 9c exists: a
//       conservativeness check cannot see a rejection that never happens.
//   I8  the `!empty && !o.empty` guard dropped -> 9d red.
//
// THE OTHER HALF OF THE SUBJECT. `Bounds2D` is the same pruning at one cell,
// and it was reachable only from inside `BoundaryLayer::generate()` until
// #180's review moved it beside the grid. It is here because the pair
// rejection is load bearing for "the answer must not change" in two different
// shapes -- a real radius for B, a pad of 0 over the ring's NODES for B2 --
// and golden_mesh.py, minutes downstream, was its only witness.
#include "SpatialGrid.hpp"
#include "check.hpp"

#include <cstdint>
#include <set>
#include <string>
#include <vector>

using namespace hybmesh::test;

namespace {

// A reproducible LCG: the clouds must be the same on every machine, so a defect
// cannot be a platform's RNG.
struct Rng {
    std::uint64_t s = 0x2026110480808080ull;
    double next() {
        s = s * 6364136223846793005ull + 1442695040888963407ull;
        return (double)((s >> 11) & ((1ull << 53) - 1)) / (double)(1ull << 53);
    }
    double in(double a, double b) { return a + (b - a) * next(); }
};

std::set<int> bruteForce(const std::vector<Point2D>& pts, Point2D p, double r) {
    std::set<int> out;
    for (std::size_t i = 0; i < pts.size(); ++i)
        if ((pts[i] - p).lengthSq() < r * r) out.insert((int)i);
    return out;
}

// Everything the grid hands back for one query, plus how much it had to look at.
struct Visit {
    std::set<int> seen;
    long count = 0;
};
Visit query(const SpatialGrid& g, Point2D p, double r) {
    Visit v;
    g.forEachNear(p, r, [&](int i) { v.seen.insert(i); ++v.count; return true; });
    return v;
}

// Does the grid's answer CONTAIN the brute-force one, for every query?
bool superset(const SpatialGrid& g, const std::vector<Point2D>& pts,
              const std::vector<Point2D>& qs, double r, long* visited = nullptr) {
    for (Point2D q : qs) {
        Visit v = query(g, q, r);
        if (visited) *visited += v.count;
        for (int i : bruteForce(pts, q, r))
            if (!v.seen.count(i)) return false;
    }
    return true;
}

}  // namespace

int main() {
    // --- 1. A uniform cloud: no query may miss a point the scan would find. ---
    {
        Rng rng;
        std::vector<Point2D> pts;
        for (int i = 0; i < 4000; ++i) pts.push_back({rng.in(-2, 3), rng.in(-1, 4)});
        std::vector<Point2D> qs;
        for (int i = 0; i < 500; ++i) qs.push_back({rng.in(-2.5, 3.5), rng.in(-1.5, 4.5)});
        for (double r : {0.001, 0.01, 0.1, 0.5, 2.0}) {
            SpatialGrid g;
            g.build(pts.data(), pts.size(), r);
            CHECK(superset(g, pts, qs, r),
                  "1. uniform cloud, r=" + std::to_string(r) + ": a point within r was missed");
        }
        // The hint is a hint: a grid built for one radius must still be exact
        // when queried at another, which is what B and B2 do (their radii are
        // per front PAIR and per SEGMENT, the hint is the layer's maximum).
        SpatialGrid g;
        g.build(pts.data(), pts.size(), 0.05);
        for (double r : {0.0005, 0.02, 1.0})
            CHECK(superset(g, pts, qs, r),
                  "1b. hint 0.05 queried at r=" + std::to_string(r) + ": a point was missed");
    }

    // --- 2. The caller's own shape: a thin ribbon inside a wide box. ---
    // 2000 wall stations x 120 layers of 1e-4, in a 1.1 x 0.35 box -- the 30P30N
    // case at BL_LAYERS 120, which is the run #180 was opened for.
    {
        std::vector<Point2D> pts;
        for (int i = 0; i < 2000; ++i) {
            double t = (double)i / 2000.0 * 2.0 * 3.14159265358979;
            double cx = 0.5 + 0.45 * std::cos(t), cy = 0.02 + 0.15 * std::sin(t);
            for (int L = 0; L < 120; ++L)
                pts.push_back({cx + 1e-4 * L * std::cos(t), cy + 1e-4 * L * std::sin(t)});
        }
        Rng rng;
        std::vector<Point2D> qs;
        for (int i = 0; i < 300; ++i) {
            int k = (int)(rng.next() * (double)pts.size());
            qs.push_back({pts[k].x + rng.in(-3e-4, 3e-4), pts[k].y + rng.in(-3e-4, 3e-4)});
        }
        const double th = 1e-4;
        SpatialGrid g;
        g.build(pts.data(), pts.size(), th);
        long visited = 0;
        CHECK(superset(g, pts, qs, th, &visited),
              "2. ribbon cloud: a point within the first-cell height was missed");
        // 2b. ...and it PRUNED. Without this the check above passes on a grid
        // that hands back the whole cloud, which is the scan #180 replaced.
        double perQuery = (double)visited / (double)qs.size();
        CHECK(perQuery < (double)pts.size() / 100.0,
              "2b. ribbon cloud: " + std::to_string(perQuery) + " points visited per query of "
              + std::to_string(pts.size()) + " -- the index is not pruning");
        // 2c. ...and the grid it allocated is bounded by the CLOUD, not by the
        // radius: 1.1 x 0.35 at a 1e-4 cell would be 14 million cells to clear
        // on every layer, which is slower than the scan #180 replaced.
        CHECK(g.cells() <= 4 * pts.size() + 64,
              "2c. ribbon cloud: " + std::to_string(g.cells()) + " cells for "
              + std::to_string(pts.size()) + " points -- the grid is unbounded");
    }

    // --- 3. Degenerate clouds: no crash, and still exact. ---
    {
        SpatialGrid g;
        g.build(nullptr, 0, 0.1);
        CHECK(query(g, {0, 0}, 1.0).count == 0, "3. an empty cloud yields nothing");
        CHECK(g.size() == 0, "3b. ...and says so");

        std::vector<Point2D> one{{1.5, -2.5}};
        g.build(one.data(), one.size(), 0.1);
        CHECK(query(g, {1.5, -2.5}, 0.1).seen.count(0) == 1, "3c. a single point is found");
        CHECK(query(g, {9.0, 9.0}, 0.1).count == 0, "3d. ...and not found from far away");

        std::vector<Point2D> same(50, Point2D{0.25, 0.25});
        g.build(same.data(), same.size(), 1e-9);
        CHECK((long)query(g, {0.25, 0.25}, 1e-6).seen.size() == 50,
              "3e. 50 coincident points are all found");

        std::vector<Point2D> line;            // no extent in x: w == 0
        for (int i = 0; i < 200; ++i) line.push_back({3.0, 0.01 * i});
        g.build(line.data(), line.size(), 0.02);
        std::vector<Point2D> lq{{3.0, 1.0}, {3.0, 0.0}, {3.0, 1.99}, {2.99, 0.5}};
        CHECK(superset(g, line, lq, 0.02), "3f. a cloud with no x extent is still exact");
        for (auto& p : line) p = {p.y, 3.0};  // and no extent in y
        g.build(line.data(), line.size(), 0.02);
        std::vector<Point2D> lq2{{1.0, 3.0}, {0.0, 3.0}, {1.99, 3.0}, {0.5, 2.99}};
        CHECK(superset(g, line, lq2, 0.02), "3g. a cloud with no y extent is still exact");
    }

    // --- 4. The hint is not a limit: r far larger than the cell. ---
    {
        Rng rng;
        std::vector<Point2D> pts;
        for (int i = 0; i < 1500; ++i) pts.push_back({rng.in(0, 1), rng.in(0, 1)});
        SpatialGrid g;
        g.build(pts.data(), pts.size(), 1e-3);
        std::vector<Point2D> qs{{0.5, 0.5}, {0.0, 0.0}, {1.0, 1.0}, {-5.0, 0.5}};
        CHECK(superset(g, pts, qs, 0.9), "4. r >> cell size: a point was missed");
        CHECK((long)query(g, {0.5, 0.5}, 10.0).seen.size() == 1500,
              "4b. a radius covering the cloud returns all of it");
    }

    // --- 5. A query nowhere near the cloud, and a nonsense hint. ---
    {
        std::vector<Point2D> pts{{0, 0}, {1, 1}, {0, 1}, {1, 0}};
        SpatialGrid g;
        g.build(pts.data(), pts.size(), 0.5);
        CHECK(query(g, {1e9, -1e9}, 1.0).count == 0, "5. a query 1e9 away yields nothing");
        CHECK(query(g, {-1e300, 0}, 1.0).count == 0, "5b. ...and does not overflow the cast");
        g.build(pts.data(), pts.size(), 0.0);
        CHECK(superset(g, pts, {{0.5, 0.5}, {0, 0}}, 0.8), "5c. a zero hint is still exact");
        g.build(pts.data(), pts.size(), -3.0);
        CHECK(superset(g, pts, {{0.5, 0.5}, {0, 0}}, 0.8), "5d. a negative hint is still exact");
    }

    // --- 6. The boundary of the box, and the early stop. ---
    {
        std::vector<Point2D> pts{{0, 0}, {1, 0}};
        SpatialGrid g;
        g.build(pts.data(), pts.size(), 1.0);
        // A point exactly r away is NOT within r (the callers compare d2 < r2),
        // but the grid must still offer it: pruning it would be the index
        // deciding, which is the one thing it must never do.
        CHECK(query(g, {2.0, 0.0}, 1.0).seen.count(1) == 1,
              "6. a point exactly r away is still offered to the caller");
        int visits = 0;
        g.forEachNear({0.5, 0.0}, 5.0, [&](int) { ++visits; return false; });
        CHECK(visits == 1, "6b. returning false from the callback stops the walk");
    }

    // --- 7. The bound B2 reaches this index through. ---
    // Two segments that properly cross share the crossing point, so their
    // midpoints are within (lenA + lenB)/2 of each other. B2 prunes ring
    // segments by exactly that, so if it were false the segment test would stop
    // firing -- silently, and only on the crossing it was added to catch.
    {
        Rng rng;
        long crossings = 0;
        for (int i = 0; i < 200000; ++i) {
            Point2D a{rng.in(-1, 1), rng.in(-1, 1)}, b{rng.in(-1, 1), rng.in(-1, 1)};
            Point2D c{rng.in(-1, 1), rng.in(-1, 1)}, d{rng.in(-1, 1), rng.in(-1, 1)};
            if (!segmentsIntersect(a, b, c, d)) continue;
            ++crossings;
            Point2D mA = (a + b) * 0.5, mB = (c + d) * 0.5;
            double bound = ((b - a).length() + (d - c).length()) * 0.5;
            if ((mA - mB).length() > bound) {
                CHECK(false, "7. a crossing pair's midpoints exceeded (lenA + lenB)/2");
                break;
            }
        }
        CHECK(crossings > 1000,
              "7b. the midpoint bound was exercised on " + std::to_string(crossings)
              + " real crossings");
    }

    // --- 8. An extreme aspect ratio: the one shape the area estimate misses. ---
    // `build` sizes its cell from sqrt(area / maxCells), which bounds a square
    // cloud on its own. A cloud 1 wide and 1e-9 tall has almost no area, so that
    // estimate asks for a 680,000 x 1 grid over 100 points; the growth loop is
    // what refuses, and without this check it is an unguarded guard.
    {
        std::vector<Point2D> thin;
        for (int i = 0; i < 100; ++i) thin.push_back({0.01 * i, 1e-11 * i});
        SpatialGrid g;
        g.build(thin.data(), thin.size(), 1e-9);
        CHECK(g.cells() <= 4 * thin.size() + 64,
              "8. a 1 x 1e-9 cloud allocated " + std::to_string(g.cells())
              + " cells for " + std::to_string(thin.size()) + " points");
        CHECK(superset(g, thin, {{0.5, 5e-10}, {0.0, 0.0}, {0.99, 1e-9}}, 1e-9),
              "8b. ...and is still exact after the cell grew");
    }

    // --- 9. The COARSEST pruning: Bounds2D, the per-front pair rejection. ---
    // This is the other half of "the answer must not change", and until #180's
    // review it was argued in a comment and witnessed only by golden_mesh.py
    // several minutes downstream. It is load bearing in two different shapes:
    // B rejects a front pair whose candidates cannot come within `th2`, so its
    // pad is a real radius; B2 rejects one whose segments cannot cross, so its
    // pad is 0 and the extents are over the ring's NODES. Both are asserted
    // here against brute force, and a rejection that is ever wrong is a node
    // that silently stops freezing.
    {
        Rng rng;
        long rejected = 0, padRejected = 0;
        for (int trial = 0; trial < 4000; ++trial) {
            // Two small clouds placed at a random offset, so some pairs overlap
            // and most do not -- the regime the eight-body case is in.
            double ox = rng.in(-2.0, 2.0), oy = rng.in(-2.0, 2.0);
            std::vector<Point2D> A, B;
            for (int i = 0; i < 12; ++i) A.push_back({rng.in(0, 1), rng.in(0, 1)});
            for (int i = 0; i < 12; ++i) B.push_back({ox + rng.in(0, 1), oy + rng.in(0, 1)});
            Bounds2D bA, bB;
            for (Point2D p : A) bA.add(p);
            for (Point2D p : B) bB.add(p);

            // 9a. B's shape: a pad that is a radius.
            const double pad = rng.in(0.0, 0.5);
            bool anyNear = false;
            for (Point2D p : A)
                for (Point2D q : B)
                    if ((p - q).lengthSq() < pad * pad) anyNear = true;
            if (!bA.overlaps(bB, pad)) {
                ++padRejected;
                if (anyNear) {
                    CHECK(false, "9a. a padded extent rejected a pair that HAS a point within pad");
                    break;
                }
            }

            // 9b. B2's shape: pad 0, and the question is whether segments cross.
            bool anyCross = false;
            for (std::size_t i = 0; i + 1 < A.size() && !anyCross; ++i)
                for (std::size_t j = 0; j + 1 < B.size(); ++j)
                    if (segmentsIntersect(A[i], A[i + 1], B[j], B[j + 1])) { anyCross = true; break; }
            if (!bA.overlaps(bB, 0.0)) {
                ++rejected;
                if (anyCross) {
                    CHECK(false, "9b. an unpadded extent rejected a pair whose segments CROSS");
                    break;
                }
            }
        }
        // 9c. ...and it rejected something. Without this, an `overlaps` stuck at
        // `true` passes 9a and 9b and the pair rejection does nothing at all.
        CHECK(rejected > 400 && padRejected > 400,
              "9c. the extent rejected " + std::to_string(rejected) + " unpadded and "
              + std::to_string(padRejected) + " padded pairs of 4000 -- it is not rejecting");
        // 9d. An empty extent is never an excuse to skip work... it rejects,
        // because a front with no candidates has nothing to collide with. Both
        // callers rely on that: `allCandidates[f]` is empty on a fully frozen
        // front and the loops below still run.
        Bounds2D none, some;
        some.add({0, 0});
        CHECK(!none.overlaps(some, 1e9) && !some.overlaps(none, 1e9),
              "9d. an empty extent overlaps nothing, at any pad");
        CHECK(some.overlaps(some, 0.0), "9e. a one-point extent overlaps itself");
    }

    return report("test_spatial_grid");
}
