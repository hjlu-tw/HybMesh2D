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
//   * Only one block can be filled in this release, so nothing here exercises
//     welding, count propagation across an interface, or a cut edge; those are
//     refused by name and the refusals ARE checked.
#include "MultiBlock.hpp"
#include "check.hpp"

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
void refuses(const std::string& doc, const std::string& names, const std::string& what) {
    MbResult r = build(doc);
    CHECK(!r.ok, what + ": must be refused");
    CHECK(mentions(r.error, names), what + ": the message must name '" + names
                                    + "' (got: " + r.error + ")");
    CHECK(r.nodes.empty() && r.cells.empty() && r.boundaryEdges.empty() && r.blocks.empty(),
          what + ": a refusal must produce nothing");
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
        CHECK(unbound, "6. ...and no source segment, because nothing binds geometry yet");
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
        // West declared backwards: the [south, east, north, west] convention
        // needs it to run j-min -> j-max, i.e. to START at the block's (0,0).
        refuses(swap1(square(4, 3), R"("id": "w", "corners": ["sw", "nw"])",
                                    R"("id": "w", "corners": ["nw", "sw"])"),
                "west", "9. a block side declared in the wrong direction");
    }

    // ── 10. what this release does not do yet is refused BY NAME ───────────
    // Not silently approximated: a corner placed near a geometry feature rather
    // than on it, or a BC guessed instead of declared, is a slightly wrong mesh
    // with no error — which is worse than no mesh.
    {
        refuses(swap1(square(4, 3), R"({"id": "sw", "kind": "free", "xy": [0.0, 0.0]})",
                      R"({"id": "sw", "kind": "on_geometry", "geom": 0, "seg": 1, "t": 0.5})"),
                "on_geometry", "10. a geometry-attached corner");
    }
    refuses(square(4, 3, R"(, "binding": {"geom": 0, "seg": 1})"), "binding",
            "10. an edge bound to a source segment");
    {
        refuses(swap1(square(4, 3), R"("id": "e", "corners": ["se", "ne"], "kind": "wall")",
                                    R"("id": "e", "corners": ["se", "ne"], "kind": "cut")"),
                "cut", "10. a cut edge (it needs a second block to be shared with)");
    }
    refuses(square(4, 3, "", R"(, "orientation": [0, 1, 2, 3])"), "orientation",
            "10. a block orientation declared twice over");
    {
        // A second block, sharing nothing: still refused, because welding and
        // count propagation are what a second block needs.
        const std::string one = R"({"id": "b0", "edges": ["s", "e", "n", "w"]})";
        MbResult r = build(swap1(square(4, 3), one,
                                 one + R"(, {"id": "b1", "edges": ["s", "e", "n", "w"]})"));
        CHECK(!r.ok, "10. a topology with two blocks is refused");
        CHECK(mentions(r.error, "one block"),
              "10. ...saying so, rather than meshing the first (got: " + r.error + ")");
    }

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

    return hybmesh::test::report("test_multiblock");
}
