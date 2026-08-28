// The multi-block seam, tested through `buildMultiBlock` and nothing else.
//
// Every check here feeds a topology DOCUMENT (as text) and asserts on what comes
// back — block dimensions, node positions, the diagonal split, the resolved
// boundary edges, warnings and errors. That is external behaviour of the one
// seam; reaching for the parser or the interpolation kernel would pin how it
// computed rather than what it returns.
//
// This executable links `hybmesh_pure` and NOTHING else — not gmsh, not
// hybmesh_core. That build property is itself the test: the moment the module
// reaches for the mesh container or gmsh, this stops linking.
//
// BLIND SPOTS, named rather than papered over:
//   * Nothing here exports anything. That the exporters accept these cells is
//     covered by the golden comparator's multi-block case family, and that the
//     solver runs on the result is the dated acceptance run recorded in
//     tools/PreProcessor/tests/test_multiblock_surface.py.
//   * The refusal checks assert that the message NAMES the offending id and
//     that nothing was produced. They do not pin the surrounding prose, which
//     is meant to be edited.
//   * Welding, count propagation and the three edge kinds arrived with #53 and are
//     checks 17-23. What is still NOT exercised anywhere: a shared edge that is
//     also BOUND to a geometry, and a block welded to itself (which `parseBlocks`
//     refuses, correctly for a transfinite fill over four sides, so an O-grid seam
//     cannot be declared as one edge).
//   * The geometry fixtures are BUILT here rather than resampled. What they
//     reproduce is the two conventions of the real chain that decide where an
//     attachment lands (a joint belongs to the later segment; a closed loop's
//     duplicate closing point is dropped), and those were measured against the
//     real `surface_resampler` — but a change to the resampler that broke either
//     would be invisible from in here. The end-to-end gate next door
//     (tools/PreProcessor/tests/test_multiblock_binding_surface.py) drives the
//     real binary against real resamplings for exactly that reason.
//
// THE INJECTIONS ARE HAND RUNS, dated and recorded here with the checks each one
// broke — deliberately NOT written up as in-test injections, because a C++ test
// cannot mutate the implementation it linked against the way the Python gates
// next door can. Measured 2026-08-28, each patch applied to src/MultiBlock.cpp
// alone, rebuilt and run, with a control run confirming a clean tree passes:
//
//   A  position resolved by point INDEX (path[t * (n-1)]) rather than by arc
//      length                                                    -> 13
//   B  the segment run NOT extended to where the segment ends     -> 12, 13, 15
//   C  no wrap to index 0 for the last segment of a closed loop   -> 12
//   D  a bound edge cuts the chord instead of walking the polyline-> 15
//   E  every boundary edge takes the config default BC            -> 14
//   F  the (geometry, segment) key dropped on the way out         -> 14
//   G  the "both corners on the bound segment" refusal removed    -> 12, 16
//
// Two of those are recorded because the FIRST attempt at them did not bite, and
// both failures were in the INJECTION rather than in the code. A's first form
// picked the index and then interpolated by arc length WITHIN that span, which
// self-corrects to the right answer — an injection that changes no behaviour
// proves nothing about the check. And a build race (a rewritten source against a
// same-second object file) scored B as inert when it in fact breaks seven checks,
// until the run was re-done and the compiler output checked for a recompile.
// Both are recorded as what HAPPENED during a hand run; neither is a standing
// guard, because there is none — a scratch script that rewrites src/ and rebuilds
// is not something this repo ships, which is the same reason these injections are
// hand runs at all.
#include "MultiBlock.hpp"
#include "check.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <string>
#include <vector>

using hybmesh::MbParams;
using hybmesh::MbResult;

namespace {

// A single square block, [0,1]x[0,1], with the counts and extra edge text the
// caller asks for. Written as a builder rather than as one literal per case so
// that a case differs from the valid document by exactly the thing it is about.
std::string square(int ni, int nj, const std::string& southExtra = "",
                   const std::string& blockExtra = "") {
    return std::string(R"({
  "format_version": 1,
  "corners": [
    {"id": "sw", "kind": "free", "xy": [0.0, 0.0]},
    {"id": "se", "kind": "free", "xy": [1.0, 0.0]},
    {"id": "ne", "kind": "free", "xy": [1.0, 1.0]},
    {"id": "nw", "kind": "free", "xy": [0.0, 1.0]}
  ],
  "edges": [
    {"id": "s", "corners": ["sw", "se"], "kind": "wall", "count": )") + std::to_string(ni)
        + southExtra + R"(},
    {"id": "e", "corners": ["se", "ne"], "kind": "wall", "count": )" + std::to_string(nj) + R"(},
    {"id": "n", "corners": ["nw", "ne"], "kind": "wall", "count": )" + std::to_string(ni) + R"(},
    {"id": "w", "corners": ["sw", "nw"], "kind": "wall", "count": )" + std::to_string(nj) + R"(}
  ],
  "blocks": [
    {"id": "b0", "edges": ["s", "e", "n", "w"])" + blockExtra + R"(}
  ]
})";
}

MbResult build(const std::string& doc, const MbParams& p = MbParams{}) {
    // No geometries: nothing in this release binds to one, and a document that
    // TRIES to is refused by name (check 10) rather than resolved against a list.
    return hybmesh::buildMultiBlock(doc, {}, p);
}

bool mentions(const std::string& hay, const std::string& needle) {
    return hay.find(needle) != std::string::npos;
}

// One edit to an otherwise-valid document, so a failing case differs from the
// passing one by exactly the thing it is about. Aborts loudly rather than
// silently returning the original: a swap that matched nothing would make the
// case assert against the VALID document and pass for the wrong reason.
std::string swap1(std::string doc, const std::string& from, const std::string& to) {
    const size_t at = doc.find(from);
    if (at == std::string::npos) {
        std::printf("FAIL  test setup: '%s' is not in the document\n", from.c_str());
        ++hybmesh::test::g_failures;
        return doc;
    }
    return doc.replace(at, from.size(), to);
}

// A refusal must name what is wrong AND leave nothing behind: the mode's whole
// contract is "refused with the topology exit code and nothing exported".
void refuses(const std::string& doc, const std::string& names, const std::string& what,
             const std::vector<hybmesh::MbGeometry>& geoms = {}) {
    MbResult r = hybmesh::buildMultiBlock(doc, geoms, MbParams{});
    CHECK(!r.ok, what + ": must be refused");
    CHECK(mentions(r.error, names), what + ": the message must name '" + names
                                    + "' (got: " + r.error + ")");
    CHECK(r.nodes.empty() && r.cells.empty() && r.boundaryEdges.empty() && r.blocks.empty(),
          what + ": a refusal must produce nothing");
}

// ── Two blocks, and the ways they can meet (issue #53) ────────────────────
//
//   d ──n0── e ──n1── f          b0 = [s0, m,  n0, w ]
//   │        │        │          b1 = [s1, ee, n1, m ]
//   w   b0   m   b1   ee
//   │        │        │
//   a ──s0── b ──s1── c
//
// Only THREE of the seven edges declare a count, and the choice is deliberate:
// 's0' fixes b0's i and so 'n0'; 'w' fixes b0's j and so 'm', which is b1's j and
// so 'ee'; 's1' fixes b1's i and so 'n1'. So one class spans both blocks through
// the shared edge, which is what makes a conflict report need a CHAIN.
//
// `sharedKind` is what the shared line 'm' declares, and `sharedExtra` / `wExtra`
// append to that edge and to 'w' — so a case differs from the valid document by
// exactly the thing it is about.
std::string twoBlocks(const std::string& sharedKind = "interface",
                      const std::string& sharedExtra = "",
                      const std::string& wExtra = "",
                      const std::string& eeExtra = "") {
    return std::string(R"({
  "format_version": 1,
  "corners": [
    {"id": "a", "kind": "free", "xy": [0.0, 0.0]},
    {"id": "b", "kind": "free", "xy": [1.0, 0.0]},
    {"id": "c", "kind": "free", "xy": [2.0, 0.0]},
    {"id": "d", "kind": "free", "xy": [0.0, 1.0]},
    {"id": "e", "kind": "free", "xy": [1.0, 1.0]},
    {"id": "f", "kind": "free", "xy": [2.0, 1.0]}
  ],
  "edges": [
    {"id": "s0", "corners": ["a", "b"], "kind": "wall", "count": 3},
    {"id": "s1", "corners": ["b", "c"], "kind": "wall", "count": 4},
    {"id": "w", "corners": ["a", "d"], "kind": "wall", "count": 3)") + wExtra + R"(},
    {"id": "m", "corners": ["b", "e"], "kind": ")" + sharedKind + R"(")" + sharedExtra + R"(},
    {"id": "n0", "corners": ["d", "e"], "kind": "wall"},
    {"id": "n1", "corners": ["e", "f"], "kind": "wall"},
    {"id": "ee", "corners": ["c", "f"], "kind": "wall")" + eeExtra + R"(}
  ],
  "blocks": [
    {"id": "b0", "edges": ["s0", "m", "n0", "w"]},
    {"id": "b1", "edges": ["s1", "ee", "n1", "m"]}
  ]
})";
}

// The same two blocks, with the RIGHT one turned a quarter turn: its i direction
// runs DOWN the shared edge 'm', which the left block uses as its own j
// direction. 'm' is declared once, [e, b], so b1 traverses it forwards and b0
// backwards — the two blocks genuinely disagree about which way the shared edge
// runs, which is the case a per-block reversal exists for and one that cannot be
// reached with both blocks in the same frame.
std::string rotatedNeighbour() {
    return R"({
  "format_version": 1,
  "corners": [
    {"id": "a", "kind": "free", "xy": [0.0, 0.0]},
    {"id": "b", "kind": "free", "xy": [1.0, 0.0]},
    {"id": "c", "kind": "free", "xy": [2.0, 0.0]},
    {"id": "d", "kind": "free", "xy": [0.0, 1.0]},
    {"id": "e", "kind": "free", "xy": [1.0, 1.0]},
    {"id": "f", "kind": "free", "xy": [2.0, 1.0]}
  ],
  "edges": [
    {"id": "s0", "corners": ["a", "b"], "kind": "wall", "count": 3},
    {"id": "w",  "corners": ["a", "d"], "kind": "wall", "count": 3},
    {"id": "m",  "corners": ["e", "b"], "kind": "interface"},
    {"id": "n0", "corners": ["d", "e"], "kind": "wall"},
    {"id": "n1", "corners": ["e", "f"], "kind": "wall", "count": 4},
    {"id": "s1", "corners": ["b", "c"], "kind": "wall"},
    {"id": "ee", "corners": ["c", "f"], "kind": "wall"}
  ],
  "blocks": [
    {"id": "b0", "edges": ["s0", "m", "n0", "w"]},
    {"id": "b1", "edges": ["m", "s1", "ee", "n1"]}
  ]
})";
}

// The same two blocks, with the shared line declared as TWO edges whose corners
// sit at IDENTICAL coordinates under different ids ('b2' on 'b', 'e2' on 'e').
// Nothing may weld them: the negative control for "no distance tolerance appears
// anywhere in the welding path", asked at a separation of exactly zero.
std::string coincidentButSeparate() {
    return R"({
  "format_version": 1,
  "corners": [
    {"id": "a",  "kind": "free", "xy": [0.0, 0.0]},
    {"id": "b",  "kind": "free", "xy": [1.0, 0.0]},
    {"id": "b2", "kind": "free", "xy": [1.0, 0.0]},
    {"id": "c",  "kind": "free", "xy": [2.0, 0.0]},
    {"id": "d",  "kind": "free", "xy": [0.0, 1.0]},
    {"id": "e",  "kind": "free", "xy": [1.0, 1.0]},
    {"id": "e2", "kind": "free", "xy": [1.0, 1.0]},
    {"id": "f",  "kind": "free", "xy": [2.0, 1.0]}
  ],
  "edges": [
    {"id": "s0", "corners": ["a", "b"], "kind": "wall", "count": 3},
    {"id": "w",  "corners": ["a", "d"], "kind": "wall", "count": 3},
    {"id": "m0", "corners": ["b", "e"], "kind": "wall"},
    {"id": "n0", "corners": ["d", "e"], "kind": "wall"},
    {"id": "s1", "corners": ["b2", "c"], "kind": "wall", "count": 4},
    {"id": "m1", "corners": ["b2", "e2"], "kind": "wall", "count": 3},
    {"id": "n1", "corners": ["e2", "f"], "kind": "wall"},
    {"id": "ee", "corners": ["c", "f"], "kind": "wall"}
  ],
  "blocks": [
    {"id": "b0", "edges": ["s0", "m0", "n0", "w"]},
    {"id": "b1", "edges": ["s1", "ee", "n1", "m1"]}
  ]
})";
}

// How many pairs of nodes sit at EXACTLY the same place. Exact equality on
// purpose: the claim is that welding is topological, so a welded mesh has none of
// these and an unwelded one has exactly as many as it duplicated. A tolerance
// here would be the very thing under test.
size_t coincidentPairs(const std::vector<Point2D>& nodes) {
    size_t n = 0;
    for (size_t i = 0; i < nodes.size(); ++i)
        for (size_t j = i + 1; j < nodes.size(); ++j)
            if (nodes[i].x == nodes[j].x && nodes[i].y == nodes[j].y) ++n;
    return n;
}

size_t invertedCells(const MbResult& r) {
    size_t bad = 0;
    for (const auto& c : r.cells) {
        const size_t k = c.nodeIds.size();
        for (size_t t = 0; t < k; ++t) {
            const Point2D& p = r.nodes[static_cast<size_t>(c.nodeIds[(t + k - 1) % k])];
            const Point2D& q = r.nodes[static_cast<size_t>(c.nodeIds[t])];
            const Point2D& s = r.nodes[static_cast<size_t>(c.nodeIds[(t + 1) % k])];
            if ((q - p).cross(s - q) <= 0.0) { ++bad; break; }
        }
    }
    return bad;
}

// One edge's resolved count, and the ids the document actually SEEDED, read off
// the result rather than recomputed — the point of publishing them is that a run
// can show which of the two each count was.
int countOf(const MbResult& r, const std::string& id) {
    for (const auto& ec : r.edgeCounts) if (ec.edgeId == id) return ec.count;
    return -1;
}

std::vector<std::string> seededSet(const MbResult& r) {
    std::vector<std::string> out;
    for (const auto& ec : r.edgeCounts) if (ec.seeded) out.push_back(ec.edgeId);
    std::sort(out.begin(), out.end());
    return out;
}

// ── A geometry, as the loader and the sidecar together hand one over ──────
//
// A CLOSED unit square walked counter-clockwise from the origin, `perSide` points
// on each side, split into four source segments with a boundary condition label
// each. Two conventions of the real chain are reproduced here EXACTLY, because
// getting either wrong moves an attachment by one resampling interval — which is
// the failure this whole feature exists to prevent, and which no round number in
// a hand-written fixture would reveal:
//
//   * a joint shared by two segments belongs to the LATER of them, so a segment's
//     own points stop one point short of where it ends (measured against the real
//     `surface_resampler`, whose output this mirrors);
//   * the loader drops the duplicate closing point of a closed loop, so the last
//     segment's end is index 0 and not one past the end.
//
// `perSide` is the parameter the re-resampling check varies: two calls with
// different counts are two resamplings of ONE geometry.
hybmesh::MbGeometry squareGeom(int perSide, const std::string& file = "square.dat") {
    hybmesh::MbGeometry g;
    g.file = file;
    g.closed = true;
    const Point2D corner[4] = {{0.0, 0.0}, {1.0, 0.0}, {1.0, 1.0}, {0.0, 1.0}};
    for (int side = 0; side < 4; ++side) {
        const Point2D a = corner[side], b = corner[(side + 1) % 4];
        for (int k = 0; k < perSide; ++k) {
            const double u = static_cast<double>(k) / perSide;   // k == perSide is b,
            g.points.push_back({a.x + (b.x - a.x) * u,           // i.e. the next
                                a.y + (b.y - a.y) * u});         // segment's first point
            g.segId.push_back(side + 1);
        }
    }
    g.segBc = {{1, "bottom"}, {2, "outlet"}, {3, "top"}, {4, "inlet"}};
    return g;
}

// A block sitting on the square's SOUTH side. `southBind` and the corner
// declarations are what each case varies; everything else is held fixed so a
// failing case differs from the passing one by exactly the thing it is about.
std::string boundSquare(const std::string& sw, const std::string& se,
                        const std::string& southBind = R"(, "binding": {"geom": "square.dat", "seg": 1})") {
    return std::string(R"({
  "format_version": 1,
  "corners": [
    )") + sw + R"(,
    )" + se + R"(,
    {"id": "ne", "kind": "free", "xy": [1.0, 0.5]},
    {"id": "nw", "kind": "free", "xy": [0.0, 0.5]}
  ],
  "edges": [
    {"id": "s", "corners": ["sw", "se"], "kind": "wall", "count": 5)" + southBind + R"(},
    {"id": "e", "corners": ["se", "ne"], "kind": "wall", "count": 3},
    {"id": "n", "corners": ["nw", "ne"], "kind": "wall", "count": 5},
    {"id": "w", "corners": ["sw", "nw"], "kind": "wall", "count": 3}
  ],
  "blocks": [
    {"id": "b0", "edges": ["s", "e", "n", "w"]}
  ]
})";
}

// The two corners of that block's south side, attached to segment 1 at `t0`/`t1`.
std::string att(const std::string& id, double t, int seg = 1,
                const std::string& geom = "square.dat") {
    return "{\"id\": \"" + id + "\", \"kind\": \"on_geometry\", \"geom\": \""
         + geom + "\", \"seg\": " + std::to_string(seg) + ", \"t\": "
         + std::to_string(t) + "}";
}

}  // namespace

int main() {
    // ── 1. a valid minimal topology fills the block ────────────────────────
    {
        MbResult r = build(square(4, 3));
        CHECK(r.ok, "1. a valid single-block square is accepted (err: " + r.error + ")");
        CHECK(r.error.empty(), "1. an accepted document reports no error");
        CHECK(r.blocks.size() == 1, "1. one block comes back");
        if (r.blocks.size() == 1) {
            const auto& b = r.blocks[0];
            CHECK(b.id == "b0", "1. the block keeps its declared id");
            CHECK(b.ni == 4 && b.nj == 3,
                  "1. the block's logical i/j node counts are the declared counts");
            CHECK(b.nodeIds.size() == 12, "1. the block indexes ni*nj nodes");
        }
        CHECK(r.nodes.size() == 12, "1. ni*nj nodes are produced");
    }

    // ── 2. logical i/j is retained, and the fill is exact on a rectangle ────
    // Transfinite interpolation on a rectangle degenerates to the tensor
    // product of the two side distributions, which is why v0 rests on it with
    // no smoother. Asserting the interior node, not just the corners, is what
    // makes that a claim about the fill rather than about the parser.
    {
        MbResult r = build(square(4, 3));
        CHECK(r.ok, "2. setup");
        if (r.ok && r.blocks.size() == 1) {
            const auto& b = r.blocks[0];
            for (int j = 0; j < b.nj; ++j) {
                for (int i = 0; i < b.ni; ++i) {
                    const auto& p = r.nodes[static_cast<size_t>(b.nodeAt(i, j))];
                    CHECK_NEAR(p.x, i / 3.0, 1e-12, "2. node(" + std::to_string(i) + ","
                               + std::to_string(j) + ").x is the uniform i fraction");
                    CHECK_NEAR(p.y, j / 2.0, 1e-12, "2. node(" + std::to_string(i) + ","
                               + std::to_string(j) + ").y is the uniform j fraction");
                }
            }
        }
    }

    // ── 3. the split is alternating by index parity, by default ────────────
    {
        MbResult r = build(square(4, 3));
        CHECK(r.ok, "3. setup");
        CHECK(r.cells.size() == 2u * 3u * 2u,
              "3. every quad becomes two triangles by default");
        bool allTris = true;
        bool blockTagged = true;
        for (const auto& c : r.cells) {
            if (c.nodeIds.size() != 3) allTris = false;
            if (c.block != 0) blockTagged = false;
        }
        CHECK(allTris, "3. ...and every cell is a triangle");
        CHECK(blockTagged, "3. ...each carrying the index of the block it came from");

        if (r.ok && r.blocks.size() == 1 && r.cells.size() >= 4) {
            const auto& b = r.blocks[0];
            // Cell (0,0) has even (i+j) and splits on the sw-ne diagonal; cell
            // (1,0) is odd and splits on the se-nw one. The two rules being
            // DIFFERENT is the whole content of "alternating": a single fixed
            // diagonal would pass every count-based check above.
            const int n00 = b.nodeAt(0, 0), n10 = b.nodeAt(1, 0);
            const int n11 = b.nodeAt(1, 1), n01 = b.nodeAt(0, 1);
            CHECK(r.cells[0].nodeIds == std::vector<int>({n00, n10, n11}) &&
                  r.cells[1].nodeIds == std::vector<int>({n00, n11, n01}),
                  "3. cell (0,0) — even (i+j) — splits on the (0,0)-(1,1) diagonal");
            const int m00 = b.nodeAt(1, 0), m10 = b.nodeAt(2, 0);
            const int m11 = b.nodeAt(2, 1), m01 = b.nodeAt(1, 1);
            CHECK(r.cells[2].nodeIds == std::vector<int>({m00, m10, m01}) &&
                  r.cells[3].nodeIds == std::vector<int>({m10, m11, m01}),
                  "3. cell (1,0) — odd (i+j) — splits on the OTHER diagonal");
        }
    }

    // ── 4. every produced triangle is wound counter-clockwise ──────────────
    {
        MbResult r = build(square(5, 4));
        int inverted = 0;
        for (const auto& c : r.cells) {
            const auto& a = r.nodes[static_cast<size_t>(c.nodeIds[0])];
            const auto& b = r.nodes[static_cast<size_t>(c.nodeIds[1])];
            const auto& d = r.nodes[static_cast<size_t>(c.nodeIds[2])];
            if ((b - a).cross(d - a) <= 0.0) ++inverted;
        }
        CHECK(inverted == 0, "4. no cell is inverted ("
              + std::to_string(inverted) + " of " + std::to_string(r.cells.size()) + " are)");
    }

    // ── 5. the split is switchable off ─────────────────────────────────────
    {
        MbParams p; p.splitQuads = false;
        MbResult r = build(square(4, 3), p);
        CHECK(r.ok, "5. setup");
        CHECK(r.cells.size() == 3u * 2u, "5. splitting off leaves one cell per quad");
        bool allQuads = true;
        for (const auto& c : r.cells) if (c.nodeIds.size() != 4) allQuads = false;
        CHECK(allQuads, "5. ...and every cell has four nodes");
        bool said = false;
        for (const auto& w : r.warnings) if (mentions(w, "quad")) said = true;
        CHECK(said, "5. ...and it is said out loud, since the solver cannot use quads");
    }

    // ── 6. boundary edges come back already resolved ───────────────────────
    {
        MbResult r = build(square(4, 3));
        CHECK(r.boundaryEdges.size() == 2u * (3u + 2u),
              "6. one boundary edge per perimeter cell side");
        bool named = true;
        bool unbound = true;
        for (const auto& be : r.boundaryEdges) {
            if (be.bc != "wall") named = false;
            if (be.geomId != -1 || be.segId != -1) unbound = false;
        }
        CHECK(named, "6. ...each carrying the resolved BC name, not a position to classify");
        CHECK(unbound, "6. ...and no source segment, because this document declares "
                       "no binding");
        bool told = false;
        for (const auto& w : r.warnings)
            if (mentions(w, "config default BC")) told = true;
        CHECK(told, "6. ...which the caller is told, rather than left to discover");
        // ONE closed walk: every edge starts where the previous one ended, and the
        // last returns to the first. A per-side emitter that got a direction wrong
        // still produces the right SET of edges, so only the chaining catches it.
        bool chained = !r.boundaryEdges.empty();
        for (size_t k = 1; k < r.boundaryEdges.size(); ++k)
            if (r.boundaryEdges[k].v1 != r.boundaryEdges[k - 1].v2) chained = false;
        CHECK(chained && r.boundaryEdges.back().v2 == r.boundaryEdges.front().v1,
              "6. ...and the perimeter is one closed walk, in one direction");
    }

    // ── 7. a per-edge spacing law reaches the nodes ────────────────────────
    // The decision layer shares the existing spacing header rather than
    // carrying a second growth-rate solver; this is what proves the sharing is
    // wired up and not merely on the include path.
    {
        MbResult r = build(square(5, 3, R"(, "spacing": {"law": "geometric", "growth": 2.0})"));
        CHECK(r.ok, "7. a geometric spacing law is accepted (err: " + r.error + ")");
        if (r.ok && r.blocks.size() == 1) {
            const auto& b = r.blocks[0];
            const double x1 = r.nodes[static_cast<size_t>(b.nodeAt(1, 0))].x;
            const double x2 = r.nodes[static_cast<size_t>(b.nodeAt(2, 0))].x;
            const double x3 = r.nodes[static_cast<size_t>(b.nodeAt(3, 0))].x;
            CHECK((x2 - x1) > (x1 - 0.0) && (x3 - x2) > (x2 - x1),
                  "7. ...and the spacing along that edge really grows");
            CHECK_NEAR(r.nodes[static_cast<size_t>(b.nodeAt(4, 0))].x, 1.0, 1e-12,
                       "7. ...while the far corner stays exactly where it was declared");
        }
        refuses(square(5, 3, R"(, "spacing": {"law": "parabolic"})"), "parabolic",
                "7. an unknown spacing law");
        refuses(square(5, 3, R"(, "spacing": {"law": "geometric"})"), "growth",
                "7. a geometric law with no growth rate");
    }

    // ── 8. a clockwise block is REFUSED, not silently re-wound ─────────────
    {
        // The same square, but its corner ring declared sw -> nw -> ne -> se,
        // i.e. clockwise. The geometry is identical; only the declaration's
        // handedness differs, and that alone makes every cell inverted.
        //
        // Refused with the topology error rather than exported: this is a bad
        // block ORIENTATION, readable from the declaration before a node exists,
        // and the fix is in the document. The inverted-cell outcome that exports
        // anyway is for a valid declaration whose geometry came out folded, which
        // is worth looking at; a backwards-wound ring is not.
        const std::string cw = R"({
  "format_version": 1,
  "corners": [
    {"id": "sw", "kind": "free", "xy": [0.0, 0.0]},
    {"id": "se", "kind": "free", "xy": [1.0, 0.0]},
    {"id": "ne", "kind": "free", "xy": [1.0, 1.0]},
    {"id": "nw", "kind": "free", "xy": [0.0, 1.0]}
  ],
  "edges": [
    {"id": "s", "corners": ["sw", "nw"], "kind": "wall", "count": 3},
    {"id": "e", "corners": ["nw", "ne"], "kind": "wall", "count": 4},
    {"id": "n", "corners": ["se", "ne"], "kind": "wall", "count": 3},
    {"id": "w", "corners": ["sw", "se"], "kind": "wall", "count": 4}
  ],
  "blocks": [
    {"id": "b0", "edges": ["s", "e", "n", "w"]}
  ]
})";
        refuses(cw, "clockwise", "8. a clockwise block");
        // The mirror: the SAME four corners wound the other way are accepted, so
        // the check above cannot be passing because the document is malformed in
        // some other way.
        MbResult ok = build(square(3, 4));
        CHECK(ok.ok, "8. ...while a counter-clockwise ring of the same square is "
                     "accepted (err: " + ok.error + ")");
    }

    // ── 9. a malformed document is refused, naming what is wrong ───────────
    refuses("{\"format_version\": 1,,}", "JSON", "9. invalid JSON");
    refuses("[1, 2, 3]", "object", "9. a document that is not an object");
    refuses(R"({"corners": [], "edges": [], "blocks": []})", "format_version",
            "9. a document with no format_version");
    {
        refuses(swap1(square(4, 3), "\"format_version\": 1", "\"format_version\": 99"),
                "99", "9. a format_version this build cannot read");
    }
    {
        refuses(swap1(square(4, 3), "\"count\": 4", "\"cout\": 4"),
                "cout", "9. a typo'd key (unknown keys are refused, not skipped)");
    }
    refuses(square(1, 3), "at least 2", "9. an edge with fewer than two nodes");
    {
        MbResult r = build(swap1(square(4, 3),
            R"("id": "n", "corners": ["nw", "ne"], "kind": "wall", "count": 4)",
            R"("id": "n", "corners": ["nw", "ne"], "kind": "wall", "count": 7)"));
        CHECK(!r.ok, "9. opposite sides with different counts are refused");
        CHECK(mentions(r.error, "'s'") && mentions(r.error, "'n'")
              && mentions(r.error, "4") && mentions(r.error, "7"),
              "9. ...naming BOTH edges and BOTH counts (got: " + r.error + ")");
    }
    {
        refuses(swap1(square(4, 3), R"(["sw", "se"])", R"(["sw", "zz"])"),
                "zz", "9. an edge naming a corner that does not exist");
    }
    {
        refuses(swap1(square(4, 3), R"(["s", "e", "n", "w"])", R"(["s", "e", "n", "q"])"),
                "q", "9. a block naming an edge that does not exist");
    }
    {
        // INVERTED by #53, deliberately: this used to be a refusal ("a block side
        // declared in the wrong direction"), and the single-block release named the
        // edge and the convention. It cannot stay one. A shared edge is ONE edge
        // with ONE declared direction, named by two blocks whose logical frames need
        // not agree about which way it runs, so requiring the convention's direction
        // in every block makes a whole class of topology undeclarable. The block's i
        // direction is still fixed by its SOUTH edge alone; the other three sides are
        // traversed as the ring requires, and a set of four that does not CLOSE a
        // ring is still refused by name (check 22).
        MbResult r = build(swap1(square(4, 3), R"("id": "w", "corners": ["sw", "nw"])",
                                               R"("id": "w", "corners": ["nw", "sw"])"));
        CHECK(r.ok, "9. a block side declared against the convention is accepted and "
                    "reversed (err: " + r.error + ")");
        if (r.ok && r.blocks.size() == 1) {
            // ...and REVERSED rather than merely tolerated: the block's (0, 0) is
            // still the corner its south and west edges share, so accepting the
            // backwards declaration must not mirror the block.
            const auto& b = r.blocks[0];
            const auto& p00 = r.nodes[static_cast<size_t>(b.nodeAt(0, 0))];
            const auto& pnj = r.nodes[static_cast<size_t>(b.nodeAt(0, b.nj - 1))];
            CHECK(p00.x == 0.0 && p00.y == 0.0 && pnj.x == 0.0 && pnj.y == 1.0,
                  "9. ...with j still running from 'sw' to 'nw', not mirrored");
        }
    }

    // ── 10. what this release does not do yet is refused BY NAME ───────────
    // Not silently approximated: a corner placed near a geometry feature rather
    // than on it, or a BC guessed instead of declared, is a slightly wrong mesh
    // with no error — which is worse than no mesh.
    //
    // Two entries of this list were REMOVED by #53 and are now covered by checks
    // 17-23 instead: a cut edge, and a topology with more than one block. What
    // stays is the one refusal that is not a "not yet" at all.
    refuses(square(4, 3, "", R"(, "orientation": [0, 1, 2, 3])"), "orientation",
            "10. a block orientation declared twice over");

    // ── 11. a declaration that reaches nothing is a typo, not a preference ──
    {
        const std::string last = R"({"id": "w", "corners": ["sw", "nw"], "kind": "wall", "count": 3})";
        refuses(swap1(square(4, 3), last,
                      last + R"(, {"id": "orphan", "corners": ["sw", "ne"], "kind": "wall", "count": 3})"),
                "orphan", "11. an edge that belongs to no block");
    }
    {
        const std::string last = R"({"id": "nw", "kind": "free", "xy": [0.0, 1.0]})";
        refuses(swap1(square(4, 3), last,
                      last + R"(, {"id": "stray", "kind": "free", "xy": [9.0, 9.0]})"),
                "stray", "11. a corner that is on no edge");
    }

    // ══ Geometry binding (issue #52) ══════════════════════════════════════
    //
    // The claim under test is that a boundary condition is DECLARED and never
    // discovered: it is read out of the topology and the geometry's sidecar
    // before a single node exists, so there is no tolerance in the chain for a
    // curved wall to drift past.

    // ── 12. a corner attaches by ARC LENGTH and lands there ────────────────
    {
        const auto g = squareGeom(4);
        const std::vector<hybmesh::MbGeometry> gs{g};
        MbResult r = hybmesh::buildMultiBlock(
            boundSquare(att("sw", 0.0), att("se", 1.0)), gs, MbParams{});
        CHECK(r.ok, "12. a topology attached to a geometry is accepted (err: " + r.error + ")");
        if (r.ok && r.blocks.size() == 1) {
            const auto& b = r.blocks.front();
            const Point2D p0 = r.nodes[static_cast<size_t>(b.nodeAt(0, 0))];
            const Point2D p1 = r.nodes[static_cast<size_t>(b.nodeAt(b.ni - 1, 0))];
            CHECK_NEAR(p0.x, 0.0, 1e-12, "12. t = 0 lands on the segment's first point");
            CHECK_NEAR(p0.y, 0.0, 1e-12, "12. ...in y too");
            // t = 1 is where the NEXT segment begins, not one resampling interval
            // short of it. That is the whole reason `segmentRun` extends the run:
            // a sidecar gives the shared joint to the later segment, so a segment's
            // own last point is 0.75 here and stopping there would put the corner
            // at a place that MOVES when the geometry is resampled.
            CHECK_NEAR(p1.x, 1.0, 1e-12,
                       "12. t = 1 lands where the segment ENDS, not on its own last point");
            CHECK_NEAR(p1.y, 0.0, 1e-12, "12. ...in y too");
        }
        MbResult mid = hybmesh::buildMultiBlock(
            boundSquare(att("sw", 0.25), att("se", 0.75)), gs, MbParams{});
        CHECK(mid.ok, "12. a corner part-way along a segment is accepted (err: " + mid.error + ")");
        if (mid.ok && mid.blocks.size() == 1) {
            const auto& b = mid.blocks.front();
            CHECK_NEAR(mid.nodes[static_cast<size_t>(b.nodeAt(0, 0))].x, 0.25, 1e-12,
                       "12. ...at the arc-length position it declares");
            CHECK_NEAR(mid.nodes[static_cast<size_t>(b.nodeAt(b.ni - 1, 0))].x, 0.75, 1e-12,
                       "12. ...at both ends");
        }
        // t = 1 of one segment and t = 0 of the next are the SAME physical point,
        // EXACTLY — not to within a tolerance. That is what the run extension buys,
        // and it is what will let two blocks meeting at a geometry feature agree
        // without one. Asked at the SEAM of the closed loop (segment 4's end is the
        // origin, which the loader dropped as a duplicate), because that is the
        // joint the wrap-around handling is about and the one a fixture is most
        // likely to get wrong.
        const std::string freeSe = R"({"id": "se", "kind": "free", "xy": [1.0, 0.0]})";
        MbResult viaFirst = hybmesh::buildMultiBlock(
            boundSquare(att("sw", 0.0, 1), freeSe, ""), gs, MbParams{});
        MbResult viaLast = hybmesh::buildMultiBlock(
            boundSquare(att("sw", 1.0, 4), freeSe, ""), gs, MbParams{});
        CHECK(viaFirst.ok && viaLast.ok,
              "12. the seam is reachable from either segment that meets there (err: "
              + viaFirst.error + viaLast.error + ")");
        if (viaFirst.ok && viaLast.ok) {
            const Point2D a = viaFirst.nodes[static_cast<size_t>(
                viaFirst.blocks.front().nodeAt(0, 0))];
            const Point2D c = viaLast.nodes[static_cast<size_t>(
                viaLast.blocks.front().nodeAt(0, 0))];
            CHECK(a.x == c.x && a.y == c.y && a.x == 0.0 && a.y == 0.0,
                  "12. ...and is the same point, so a joint needs no tolerance");
        }
        // So an edge bound to segment 1 accepts a corner declared as segment 2's
        // t = 0: that is the joint the two share, named from the other side. It is
        // the same POINT by the sidecar's own indexing, not by comparing two
        // coordinates — and it has to be accepted, because on a closed body every
        // block corner is a joint whose two edges bind to different segments.
        MbResult fromNext = hybmesh::buildMultiBlock(
            boundSquare(att("sw", 0.5), att("se", 0.0, 2)), gs, MbParams{});
        CHECK(fromNext.ok, "12. a bound edge accepts a corner naming its far joint from "
                           "the NEXT segment (err: " + fromNext.error + ")");
        if (fromNext.ok)
            CHECK_NEAR(fromNext.nodes[static_cast<size_t>(
                           fromNext.blocks.front().nodeAt(
                               fromNext.blocks.front().ni - 1, 0))].x, 1.0, 1e-12,
                       "12. ...landing on that joint, i.e. segment 1's own t = 1");
        // A position strictly INSIDE another segment is still refused: it is not a
        // point segment 1 owns, so "this edge lies on segment 1" would be false.
        refuses(boundSquare(att("sw", 0.5), att("se", 0.3, 2)),
                "has to start and end on it",
                "12. ...but not one strictly inside the neighbour", gs);
    }

    // ── 13. re-resampling does not move an attached corner ─────────────────
    // The ticket's central rule, and the reason attachment is an arc length
    // rather than a point index: the workflow is edit CAD, re-resample, re-mesh.
    {
        const std::string doc = boundSquare(att("sw", 0.3), att("se", 0.9));
        MbResult coarse = hybmesh::buildMultiBlock(doc, {squareGeom(4)}, MbParams{});
        MbResult fine   = hybmesh::buildMultiBlock(doc, {squareGeom(13)}, MbParams{});
        CHECK(coarse.ok && fine.ok,
              "13. one topology meshes against two resamplings of one geometry");
        if (coarse.ok && fine.ok) {
            const Point2D a = coarse.nodes[static_cast<size_t>(
                coarse.blocks.front().nodeAt(0, 0))];
            const Point2D b = fine.nodes[static_cast<size_t>(
                fine.blocks.front().nodeAt(0, 0))];
            CHECK_NEAR(a.x, b.x, 1e-12,
                       "13. the attached corner is in the same physical place");
            CHECK_NEAR(a.y, b.y, 1e-12, "13. ...in y too");
            CHECK_NEAR(a.x, 0.3, 1e-12, "13. ...which is the place it declared");
            // NEGATIVE CONTROL. Without it this check would pass just as well on an
            // implementation that never resamples anything, so it says nothing about
            // arc length until the alternative is shown to differ: the point INDEX
            // nearest t = 0.3 is a different physical place in the two samplings, by
            // ~10 orders of magnitude more than the residue above.
            const auto g4 = squareGeom(4), g13 = squareGeom(13);
            const double byIndex4 = g4.points[static_cast<size_t>(0.3 * 4)].x;
            const double byIndex13 = g13.points[static_cast<size_t>(0.3 * 13)].x;
            CHECK(std::fabs(byIndex4 - byIndex13) > 1e-3,
                  "13. (negative control) an INDEX binding really would have moved it ("
                  + std::to_string(byIndex4) + " vs " + std::to_string(byIndex13) + ")");
        }
    }

    // ── 14. a bound edge carries its segment's condition, already resolved ──
    {
        const auto g = squareGeom(4);
        MbResult r = hybmesh::buildMultiBlock(
            boundSquare(att("sw", 0.0), att("se", 1.0)), {g}, MbParams{});
        CHECK(r.ok, "14. setup (err: " + r.error + ")");
        size_t onSeg = 0, onDefault = 0;
        bool keyed = true, defaultUnkeyed = true;
        for (const auto& be : r.boundaryEdges) {
            if (be.bc == "bottom") {
                ++onSeg;
                if (be.geomId != 0 || be.segId != 1) keyed = false;
            } else {
                ++onDefault;
                if (be.geomId != -1 || be.segId != -1) defaultUnkeyed = false;
            }
        }
        // The south side of a 5 x 3 block is four edges; the other three sides are
        // the rest of the perimeter and declare no binding.
        CHECK(onSeg == 4, "14. every edge along the bound side carries that segment's "
                          "own BC label (" + std::to_string(onSeg) + ")");
        CHECK(keyed, "14. ...together with its (geometry, segment) key, so the exporter "
                     "groups it as one patch");
        // The perimeter of a 5 x 3 block is 2 * ((5 - 1) + (3 - 1)) = 12 edges.
        CHECK(onDefault == 12u - 4u,
              "14. ...while a side with no binding keeps the config default ("
              + std::to_string(onDefault) + ")");
        CHECK(defaultUnkeyed, "14. ...and carries no source segment, rather than a "
                              "borrowed one");
        // A segment with no label in the sidecar falls back — and SAYS so, because
        // the user named a segment precisely so the condition would follow from it.
        auto blank = g;
        blank.segBc[1] = "";
        MbResult nb = hybmesh::buildMultiBlock(
            boundSquare(att("sw", 0.0), att("se", 1.0)), {blank}, MbParams{});
        bool told = false;
        for (const auto& w : nb.warnings)
            if (mentions(w, "no boundary condition label")) told = true;
        CHECK(nb.ok && told,
              "14. a bound segment with no label falls back to the default and says so");
    }

    // ── 15. a bound edge FOLLOWS the geometry, it does not cut the chord ────
    // The difference between an edge that lies on a segment and one that merely
    // says so. On a curved wall a chord sits a sagitta off the body everywhere
    // between its ends, and that drift is exactly what made a curved inlet export
    // a band of wall on the other path.
    {
        hybmesh::MbGeometry g;
        g.file = "chevron.dat";
        g.points = {{0.0, 0.0}, {0.5, 0.5}, {1.0, 0.0}, {1.0, -1.0}};
        g.segId  = {1, 1, 2, 2};
        g.segBc  = {{1, "body"}, {2, "outlet"}};
        MbResult r = hybmesh::buildMultiBlock(
            swap1(swap1(boundSquare(att("sw", 0.0, 1, "chevron.dat"),
                                    att("se", 1.0, 1, "chevron.dat")),
                        R"("geom": "square.dat", "seg": 1)", R"("geom": "chevron.dat", "seg": 1)"),
                  R"("xy": [1.0, 0.5])", R"("xy": [1.0, 1.5])"),
            {g}, MbParams{});
        CHECK(r.ok, "15. an edge bound to a bent segment is accepted (err: " + r.error + ")");
        if (r.ok && r.blocks.size() == 1) {
            const auto& b = r.blocks.front();
            // The apex is the midpoint of the segment's arc length, and the south
            // edge has 5 nodes, so node 2 sits on it. A chord would put that node
            // at y = 0.
            const Point2D apex = r.nodes[static_cast<size_t>(b.nodeAt(2, 0))];
            CHECK_NEAR(apex.x, 0.5, 1e-12, "15. the middle node walks the polyline");
            CHECK_NEAR(apex.y, 0.5, 1e-12,
                       "15. ...to the bend itself, not to the chord across it");
        }
    }

    // ── 16. what cannot be resolved is refused BY NAME ─────────────────────
    // Never approximated, and never resolved by position in a list: a corner
    // placed NEAR a feature instead of on it is a slightly wrong mesh with no
    // error, which is worse than no mesh at all.
    {
        const std::vector<hybmesh::MbGeometry> gs{squareGeom(4)};
        const std::string ok0 = att("sw", 0.0), ok1 = att("se", 1.0);

        refuses(boundSquare(att("sw", 0.0, 1, "elsewhere.dat"), ok1), "elsewhere.dat",
                "16. a corner on a geometry this run never loaded", gs);
        refuses(boundSquare(att("sw", 0.0, 9), ok1), "segment 9",
                "16. a corner on a segment the geometry does not have", gs);
        refuses(boundSquare(ok0, ok1), "loaded no geometry",
                "16. an attachment when nothing was loaded at all");
        refuses(swap1(boundSquare(ok0, ok1), R"("t": 0.000000)", R"("t": 1.500000)"),
                "between 0 and 1", "16. an arc-length position off the segment", gs);
        refuses(swap1(boundSquare(ok0, ok1), R"("kind": "on_geometry", "geom")",
                      R"("kind": "on_geometry", "xy": [0.0, 0.0], "geom")"),
                "must not also declare", "16. a corner declaring its position twice", gs);
        refuses(swap1(boundSquare(ok0, ok1),
                      R"({"id": "ne", "kind": "free", "xy": [1.0, 0.5]})",
                      R"({"id": "ne", "kind": "free", "xy": [1.0, 0.5], "seg": 2})"),
                "only an 'on_geometry' corner reads",
                "16. a free corner wearing an attachment key", gs);
        // A bound edge whose corner is a free coordinate: there is no stretch of
        // geometry for it to follow, so "it lies on that segment" is unverifiable.
        refuses(boundSquare(R"({"id": "sw", "kind": "free", "xy": [0.0, 0.0]})", ok1),
                "has to start and end on it",
                "16. an edge bound to a segment its corner is not on", gs);
        refuses(boundSquare(att("sw", 0.4), att("se", 0.4)), "no length",
                "16. an edge whose two corners attach at the same position", gs);
        // A trivial piece break at index 0 is not a second piece. Sidecars in this
        // repo disagree about whether to record it (a resampled square writes
        // NPIECES 0; examples/geometries/square_cavity.dat.meta writes a break at
        // 0), and reading it as multi-piece switches off the closed-loop wrap —
        // putting the last segment's t = 1 one resampling interval short of the
        // seam, silently.
        {
            auto trivial = squareGeom(4);
            trivial.pieceBreaks = {0};
            MbResult r = hybmesh::buildMultiBlock(
                boundSquare(att("sw", 1.0, 4),
                            R"({"id": "se", "kind": "free", "xy": [1.0, 0.0]})", ""),
                {trivial}, MbParams{});
            CHECK(r.ok, "16. a break at index 0 is not a second piece (err: "
                        + r.error + ")");
            if (r.ok) {
                const Point2D p = r.nodes[static_cast<size_t>(
                    r.blocks.front().nodeAt(0, 0))];
                CHECK(p.x == 0.0 && p.y == 0.0,
                      "16. ...so the last segment still reaches the seam");
            }
        }
        // A REAL second piece does stop the wrap, because there is no next point
        // to reach for across a gap between two disjoint pieces.
        {
            auto split = squareGeom(4);
            split.pieceBreaks = {8};
            MbResult r = hybmesh::buildMultiBlock(
                boundSquare(att("sw", 1.0, 4),
                            R"({"id": "se", "kind": "free", "xy": [1.0, 0.0]})", ""),
                {split}, MbParams{});
            CHECK(r.ok && r.nodes[static_cast<size_t>(
                      r.blocks.front().nodeAt(0, 0))].y != 0.0,
                  "16. ...while a real second piece stops the segment at its own end");
        }
        // t = 1 means "where this segment ENDS", which is the next segment's first
        // point only when there IS a next one. On the last segment of an open
        // polyline it is that segment's own final point — and that is stable under
        // resampling for a different reason: the resampler pins every segment's
        // endpoints, so a segment's last sample is a declared endpoint and not a
        // floating sample. Measured 2026-08-28 through the real binary: an open
        // two-segment polyline resampled at 6 and 11 points per segment ends at
        // (1.0, 1.0) both times.
        {
            hybmesh::MbGeometry open;
            open.file = "open.dat";
            open.points = {{0.0, 1.0}, {0.5, 1.0}, {1.0, 1.0}, {0.5, 0.5}, {0.0, 0.0}};
            open.segId  = {1, 1, 2, 2, 2};
            open.segBc  = {{1, "in"}, {2, "out"}};
            MbResult r = hybmesh::buildMultiBlock(
                boundSquare(att("sw", 1.0, 2, "open.dat"),
                            R"({"id": "se", "kind": "free", "xy": [1.0, 0.0]})", ""),
                {open}, MbParams{});
            CHECK(r.ok, "16. the last segment of an OPEN polyline is attachable (err: "
                        + r.error + ")");
            if (r.ok) {
                const Point2D p = r.nodes[static_cast<size_t>(
                    r.blocks.front().nodeAt(0, 0))];
                CHECK(p.x == 0.0 && p.y == 0.0,
                      "16. ...and its t = 1 is its own final point, there being no "
                      "next segment to reach for");
            }
        }
        // A geometry that would not load is a warning while nothing refers to it,
        // and an error the moment something does.
        {
            hybmesh::MbGeometry gone;
            gone.file = "square.dat";
            refuses(boundSquare(ok0, ok1), "carries no points",
                    "16. an attachment to a geometry that would not load", {gone});
        }
        {
            hybmesh::MbGeometry bare = squareGeom(4);
            bare.segId.clear();
            refuses(boundSquare(ok0, ok1), ".meta",
                    "16. an attachment to a geometry with no sidecar", {bare});
        }
        // Two geometries sharing a basename make the short form ambiguous. Refused
        // rather than resolved by order, because position in the list is exactly
        // the binding this feature exists not to have.
        {
            auto a = squareGeom(4, "left/square.dat");
            auto b = squareGeom(4, "right/square.dat");
            refuses(boundSquare(ok0, ok1), "ambiguous",
                    "16. a geometry named by an ambiguous basename", {a, b});
        }
        // ...while a UNIQUE basename resolves, so a topology need not repeat the
        // config's whole path.
        {
            MbResult r = hybmesh::buildMultiBlock(boundSquare(ok0, ok1),
                                                  {squareGeom(4, "geom/square.dat")}, MbParams{});
            CHECK(r.ok, "16. ...while a unique basename resolves (err: " + r.error + ")");
        }
    }


    // ══ Multi-block welding (issue #53) ═══════════════════════════════════
    //
    // Three claims are under test here, and they are one mechanism seen from
    // three sides. Point counts PROPAGATE, so the user seeds a few edges and the
    // rest are forced. Blocks are welded TOPOLOGICALLY, so the k-th node on one
    // side of a shared edge IS the k-th node on the other and no distance is
    // compared anywhere. And an edge's KIND is declared, never inferred from
    // whether a binding is present.

    // ── 17. two blocks come back as ONE welded mesh ────────────────────────
    {
        MbResult r = build(twoBlocks());
        CHECK(r.ok, "17. a two-block topology is accepted (err: " + r.error + ")");
        CHECK(r.blocks.size() == 2, "17. both blocks come back");
        if (r.ok && r.blocks.size() == 2) {
            const auto& b0 = r.blocks[0];
            const auto& b1 = r.blocks[1];
            CHECK(b0.ni == 3 && b0.nj == 3 && b1.ni == 4 && b1.nj == 3,
                  "17. each block is filled at its own resolved logical size ("
                  + std::to_string(b0.ni) + "x" + std::to_string(b0.nj) + ", "
                  + std::to_string(b1.ni) + "x" + std::to_string(b1.nj) + ")");
            // THE WELD, as node IDENTITY. Not "the two sides are close": the same
            // integer, which is the only claim that holds at a wall spacing of
            // 1e-7 beside a far-field spacing of 1e-1.
            bool shared = true;
            for (int j = 0; j < b0.nj; ++j)
                if (b0.nodeAt(b0.ni - 1, j) != b1.nodeAt(0, j)) shared = false;
            CHECK(shared, "17. the k-th node of the shared edge IS the k-th node both "
                          "blocks see — the same id, not a coordinate match");
            // ...and the saving is real: two unwelded blocks would need 3*3 + 4*3.
            CHECK(r.nodes.size() == 18,
                  "17. ...so the mesh holds 18 nodes and not the 21 two separate "
                  "blocks would need (" + std::to_string(r.nodes.size()) + ")");
            CHECK(coincidentPairs(r.nodes) == 0,
                  "17. ...and no two nodes sit at the same place, so it is ONE mesh "
                  "rather than two meshes touching");
            CHECK(r.cells.size() == 2u * (2u * 2u + 3u * 2u),
                  "17. every quad of both blocks is split ("
                  + std::to_string(r.cells.size()) + ")");
            CHECK(invertedCells(r) == 0, "17. ...and no cell is inverted");
            // The interface is an INTERIOR line: both blocks have cells against it,
            // so emitting it as a boundary face would hand the exporter a face with
            // two owners and the solver a wall through the middle of the fluid.
            CHECK(r.boundaryEdges.size() == 14,
                  "17. only the six WALL sides reach the boundary, not the shared "
                  "interface (" + std::to_string(r.boundaryEdges.size()) + ")");
            CHECK(r.sharedEdges.size() == 1
                  && r.sharedEdges[0].edgeId == "m"
                  && r.sharedEdges[0].kind == "interface"
                  && r.sharedEdges[0].nodes == 3,
                  "17. ...and the interface is reported as data, with the two block "
                  "sides it welds");
            if (r.sharedEdges.size() == 1) {
                const auto& se = r.sharedEdges[0];
                CHECK((se.blockA == 0 && se.sideA == hybmesh::MB_EAST
                       && se.blockB == 1 && se.sideB == hybmesh::MB_WEST),
                      "17. ...naming which side of which block, in declaration order");
            }
        }
    }

    // ── 18. a seeded count propagates; a spacing LAW does not ──────────────
    {
        MbResult r = build(twoBlocks());
        CHECK(r.ok, "18. setup (err: " + r.error + ")");
        // Three of the seven edges declare a count. Everything else is forced:
        // 's0' fixes b0's i and so 'n0'; 'w' fixes b0's j and so 'm', which is b1's
        // j and so 'ee'; 's1' fixes b1's i and so 'n1'.
        CHECK(countOf(r, "s0") == 3 && countOf(r, "n0") == 3
              && countOf(r, "w") == 3 && countOf(r, "m") == 3 && countOf(r, "ee") == 3
              && countOf(r, "s1") == 4 && countOf(r, "n1") == 4,
              "18. every edge's count is resolved, three seeded and four propagated");
        CHECK(seededSet(r) == std::vector<std::string>({"s0", "s1", "w"}),
              "18. ...and which of the two each one was is reported, so a propagation "
              "defect cannot read as a design choice");
        // The COUNT propagates and the SPACING LAW does not. They are different
        // facts: a wall edge legitimately clusters toward the wall while the
        // interface in its own count class stays uniform, and forcing the law
        // across a class would silently redistribute an edge nobody edited.
        MbResult g = build(twoBlocks("interface", "",
                                     R"(, "spacing": {"law": "geometric", "growth": 3.0})"));
        CHECK(g.ok, "18. a graded seed edge is accepted (err: " + g.error + ")");
        if (g.ok && g.blocks.size() == 2) {
            const auto& b0 = g.blocks[0];
            const double wy = g.nodes[static_cast<size_t>(b0.nodeAt(0, 1))].y;
            const double my = g.nodes[static_cast<size_t>(b0.nodeAt(b0.ni - 1, 1))].y;
            CHECK(wy < 0.3, "18. ...the graded edge 'w' clusters toward its start ("
                            + std::to_string(wy) + ")");
            CHECK_NEAR(my, 0.5, 1e-12,
                       "18. ...while 'm', which took its COUNT from 'w', keeps its own "
                       "uniform law");
        }
    }

    // ── 19. two conflicting seeds name both edges, both counts and the CHAIN ─
    // A bare "counts disagree" is not enough on a topology with dozens of edges:
    // what the user has to be told is which two declarations are in conflict and
    // by what route, since the two need not be anywhere near each other.
    {
        // The conflicting seed is deliberately TWO blocks away from the one it
        // clashes with: 'w' is b0's west, 'ee' is b1's east, and the two are in one
        // class only through the shared edge 'm'. A one-block conflict would let a
        // report that names no chain at all pass this check.
        MbResult r = build(twoBlocks("interface", "", "", R"(, "count": 9)"));
        CHECK(!r.ok, "19. two conflicting seeds in one class are refused");
        CHECK(mentions(r.error, "'w'") && mentions(r.error, "'ee'")
              && mentions(r.error, "3") && mentions(r.error, "9"),
              "19. ...naming BOTH edges and BOTH counts (got: " + r.error + ")");
        CHECK(mentions(r.error, "'b0'") && mentions(r.error, "'b1'")
              && mentions(r.error, "'m'") && mentions(r.error, "west / east"),
              "19. ...and the chain that propagated between them, block by block, "
              "naming the edge in between (got: " + r.error + ")");
        CHECK(r.nodes.empty() && r.blocks.empty(),
              "19. ...and producing nothing");
    }

    // ── 20. a class with NO seed is refused naming every edge in it ─────────
    // Refusing beats picking a default: a silently-chosen count decides the whole
    // mesh density, and the user cannot see a number nobody wrote down.
    {
        MbResult r = build(swap1(twoBlocks(),
                                 R"("id": "w", "corners": ["a", "d"], "kind": "wall", "count": 3)",
                                 R"("id": "w", "corners": ["a", "d"], "kind": "wall")"));
        CHECK(!r.ok, "20. an equivalence class with no seed is refused");
        CHECK(mentions(r.error, "'w'") && mentions(r.error, "'m'")
              && mentions(r.error, "'ee'"),
              "20. ...naming every edge it could not resolve (got: " + r.error + ")");
        CHECK(mentions(r.error, "count"),
              "20. ...and what to add to fix it");
    }

    // ── 21. the three edge kinds are honoured distinctly ───────────────────
    {
        // A wall is the OUTSIDE of the mesh, so two blocks cannot share one.
        MbResult r = build(twoBlocks("wall"));
        CHECK(!r.ok, "21. a 'wall' named by two blocks is refused");
        CHECK(mentions(r.error, "'m'") && mentions(r.error, "'b0'")
              && mentions(r.error, "'b1'"),
              "21. ...naming the edge and both blocks that claim it (got: "
              + r.error + ")");
    }
    {
        // ...and the converse: an interface is an INTERIOR boundary, so one block
        // alone cannot have one. Inferring "only one block has it, so it must be a
        // wall" is exactly the inference this enum exists to refuse.
        refuses(swap1(square(4, 3), R"("id": "e", "corners": ["se", "ne"], "kind": "wall")",
                                    R"("id": "e", "corners": ["se", "ne"], "kind": "interface")"),
                "'e'", "21. an 'interface' named by only one block");
    }
    {
        // A cut welds by the same rule an interface does — there is nothing left
        // for a second rule to do once node identity is shared — so what has to
        // hold is that the DECLARATION survives: the mesh is identical and the
        // report says "cut". A kind that vanished on the way through would leave
        // the enum a comment.
        MbResult i = build(twoBlocks("interface"));
        MbResult c = build(twoBlocks("cut"));
        CHECK(c.ok, "21. a 'cut' shared by two blocks is accepted (err: " + c.error + ")");
        CHECK(c.sharedEdges.size() == 1 && c.sharedEdges[0].kind == "cut",
              "21. ...and comes back reported as a CUT, not as an ordinary interface");
        CHECK(i.ok && c.nodes.size() == i.nodes.size()
              && c.cells.size() == i.cells.size()
              && c.boundaryEdges.size() == i.boundaryEdges.size(),
              "21. ...welding the same way an interface does, which is what the two "
              "kinds share and all they share");
    }
    {
        // A binding says "this edge LIES ON that source segment", which is a
        // statement about a wall. An interior line in the fluid has no segment to
        // lie on, and accepting one would make the kind and the binding two
        // statements of one fact that can only ever disagree.
        refuses(twoBlocks("interface",
                          R"(, "binding": {"geom": "square.dat", "seg": 0})"),
                "binding", "21. a 'binding' on an interface");
    }

    // ── 22. orientation comes from the DECLARATION, either way round ────────
    {
        // The right-hand block turned a quarter turn: its i direction runs DOWN the
        // shared edge, which the left-hand block uses as its own j direction. One
        // edge, one declared direction, two blocks that disagree about which way it
        // runs — the case a per-block reversal exists for, and one that cannot be
        // reached with both blocks in the same frame.
        MbResult r = build(rotatedNeighbour());
        CHECK(r.ok, "22. a neighbour whose shared edge runs the opposite way is "
                    "accepted (err: " + r.error + ")");
        if (r.ok && r.blocks.size() == 2) {
            const auto& b0 = r.blocks[0];
            const auto& b1 = r.blocks[1];
            CHECK(b0.ni == 3 && b0.nj == 3 && b1.ni == 3 && b1.nj == 4,
                  "22. ...each block filled in its own frame ("
                  + std::to_string(b1.ni) + "x" + std::to_string(b1.nj) + ")");
            // b0 walks the shared edge as its east, j-min -> j-max; b1 walks the
            // SAME edge as its south, i-min -> i-max, in the opposite direction. So
            // the weld is index-reversed, and it is still node IDENTITY.
            bool welded = true;
            for (int j = 0; j < b0.nj; ++j)
                if (b0.nodeAt(b0.ni - 1, j) != b1.nodeAt(b0.nj - 1 - j, 0)) welded = false;
            CHECK(welded, "22. ...and still welded, with the shared edge's node order "
                          "reversed for the block that traverses it backwards");
            CHECK(r.nodes.size() == 18 && coincidentPairs(r.nodes) == 0,
                  "22. ...into one mesh with no duplicated node ("
                  + std::to_string(r.nodes.size()) + " nodes, "
                  + std::to_string(coincidentPairs(r.nodes)) + " coincident pairs)");
            CHECK(invertedCells(r) == 0,
                  "22. ...and no cell inverted, so the reversal did not mirror a block");
        }
    }
    {
        // A block whose four sides do not CLOSE a ring is refused by name. This is
        // what the retired wrong-direction refusal becomes: the direction of three
        // of the four sides is free, which corners they touch is not.
        refuses(swap1(twoBlocks(), R"("id": "w", "corners": ["a", "d"])",
                                   R"("id": "w", "corners": ["b", "d"])"),
                "'b0'", "22. a block whose sides do not close a ring");
        refuses(swap1(twoBlocks(), R"("id": "w", "corners": ["a", "d"])",
                                   R"("id": "w", "corners": ["b", "d"])"),
                "'w'", "22. ...naming the edge that does not reach the ring");
        // ...and the other way a ring can fail: it CLOSES, but onto three corners
        // instead of four. Two distinct edges over the same corner pair make the
        // block's j-max corner its own i-max corner, so every match above succeeds
        // and there is still no interior to fill. Reachable, not hypothetical —
        // which is why the four corners are checked pairwise distinct after the
        // ring is matched and not instead of it.
        refuses(R"({
  "format_version": 1,
  "corners": [
    {"id": "a", "kind": "free", "xy": [0.0, 0.0]},
    {"id": "b", "kind": "free", "xy": [1.0, 0.0]},
    {"id": "e", "kind": "free", "xy": [1.0, 1.0]}
  ],
  "edges": [
    {"id": "s", "corners": ["a", "b"], "kind": "wall", "count": 3},
    {"id": "w", "corners": ["a", "b"], "kind": "wall", "count": 3},
    {"id": "e1", "corners": ["b", "e"], "kind": "wall"},
    {"id": "n", "corners": ["b", "e"], "kind": "wall"}
  ],
  "blocks": [
    {"id": "b0", "edges": ["s", "e1", "n", "w"]}
  ]
})", "two different corners", "22. a ring that closes onto three corners");
    }

    // ── 23. NOTHING welds by coordinate — the negative control ─────────────
    //
    // The same two blocks, but the shared line declared as TWO edges whose corners
    // sit at IDENTICAL coordinates under different ids. Nothing welds them, and
    // that is the point: if any distance comparison existed in this path it would
    // fire exactly here, at a separation of zero. Wall spacing on a real case is
    // around 1e-7 while far-field spacing is around 1e-1, so no single tolerance
    // exists between the two scales — the declaration is the only thing that can
    // say two nodes are one.
    {
        MbResult r = build(coincidentButSeparate());
        CHECK(r.ok, "23. two blocks that merely TOUCH are accepted (err: "
                    + r.error + ")");
        if (r.ok && r.blocks.size() == 2) {
            const auto& b0 = r.blocks[0];
            const auto& b1 = r.blocks[1];
            bool anyShared = false;
            for (int j = 0; j < b0.nj; ++j)
                if (b0.nodeAt(b0.ni - 1, j) == b1.nodeAt(0, j)) anyShared = true;
            CHECK(!anyShared, "23. ...and are NOT welded, though their corners sit at "
                              "exactly the same coordinates");
            CHECK(r.nodes.size() == 21,
                  "23. ...so the mesh holds all 21 nodes, three of them duplicated ("
                  + std::to_string(r.nodes.size()) + ")");
            CHECK(coincidentPairs(r.nodes) == 3,
                  "23. ...which is visible as three coincident pairs ("
                  + std::to_string(coincidentPairs(r.nodes)) + ")");
            CHECK(r.sharedEdges.empty(),
                  "23. ...and nothing is reported as shared, because nothing is");
        }
    }

    return hybmesh::test::report("test_multiblock");
}
