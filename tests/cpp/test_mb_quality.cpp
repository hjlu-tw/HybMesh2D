// The multi-block mesh-quality instrument (issue #51), tested through
// `measureMbQuality` and nothing else.
//
// This is the RULER, and the ticket builds it before the thing it measures so
// that the v1 acceptance gate cannot be negotiated down at the end. A ruler is
// only worth having if it is known to bite, so the checks here are chosen to be
// falsifiable: a parallelogram whose non-orthogonality has a closed form, a
// strongly stretched but perfectly orthogonal block, a corner ring the
// DECLARATION accepts whose fill folds anyway, and a bow-tie quad whose total
// signed area is POSITIVE.
//
// This executable links `hybmesh_pure` and NOTHING else — not gmsh, not
// hybmesh_core. That build property is itself part of the test: measuring a
// mesh must not require a mesh container.
//
// BLIND SPOTS, named rather than papered over:
//   * Nothing here prints a banner or sets an exit code. That a mesh holding
//     inverted cells is EXPORTED and exits 9 while an invalid declaration
//     exports nothing and exits 8 is external behaviour of the binary, pinned
//     in tools/PreProcessor/tests/test_multiblock_quality_surface.py.
//   * Non-orthogonality is measured on the STRUCTURED grid cells, so nothing
//     here says anything about the shape of the split triangles. That is
//     deliberate and argued at the declaration in include/MbQuality.hpp; a
//     solver-facing skewness metric for the split cells is a different
//     instrument.
//   * The wall first-cell height is a distance ALONG the grid line, not the
//     perpendicular distance to the wall. On a non-orthogonal block the two
//     differ by cos(non-orthogonality), which is why both numbers are reported
//     together — but no check here pins that relationship.
//   * The wall figure's REQUEST is derived from the same spacing law the fill
//     reproduces, so on a rectangle it is 0.00% as a TAUTOLOGY (check 1 pins
//     that, and says so). Check 7 is where it earns its keep. An independent
//     wall-spacing target is later work; see MbWallHeight's declaration.
//
// INJECTIONS: run BY HAND at review time, 2026-08-27, and recorded here rather
// than written as in-test injections — a C++ test cannot mutate the
// implementation it linked against, so unlike the Python gates next door these
// cannot re-run themselves. Each names the checks it broke, so a later reader can
// tell a check that bites from one that merely passes:
//
//   A. the per-corner rule replaced by the cell's signed area -> 1 failure,
//      check 6 alone. (The two agree on every triangle, which is why only the
//      hand-built bow-tie catches it.)
//   B. non-orthogonality inferred from an edge-length ratio -> 5 failures,
//      checks 2, 3 (x2), 4, 7.
//   C. the wall request read back off the mesh instead of the declaration
//      -> 4 failures, checks 4, 6b (x2), 7.
//   D. the report's angle figures defaulting to 0.0 instead of negative
//      -> 2 failures, checks 6 and 8.
//   E. a wall ROW's `worstRelError` defaulting to 0.0 -> 2 failures, check 6b
//      (x2). CHECK 6b EXISTS BECAUSE OF THIS INJECTION: run against the first
//      version of this file it broke NOTHING, because check 6 declares no wall
//      at all and so only ever exercised the REPORT's default. The rule the
//      header states was unguarded until the injection said so.
//   F. non-orthogonality measured on the split triangles instead of the
//      structured cells -> 10 failures, across checks 1 (x3), 2, 3 (x2), 5,
//      6 (x2) and 7.
//
// What survives that limitation is the two NEGATIVE CONTROLS below, which are
// permanent because they measure the injections' own premises inside the test:
// check 6 computes its bow-tie's shoelace area (an area test really would pass
// it) and check 2 computes its own stretch ratio (the mesh really is stretched).
// An argument in a comment decays; those two do not.
#include "MbQuality.hpp"
#include "MultiBlock.hpp"
#include "check.hpp"

#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

using hybmesh::MbParams;
using hybmesh::MbQualityReport;
using hybmesh::MbResult;

namespace {

// One block from its four corners, in [south, east, north, west] order with the
// convention buildMultiBlock declares. `iExtra` / `jExtra` append spacing text to
// the i- and j-direction edges, so a graded case differs from a uniform one by
// exactly that.
std::string blockDoc(double ax, double ay, double bx, double by,
                     double cx, double cy, double dx, double dy,
                     int ni, int nj,
                     const std::string& iExtra = "", const std::string& jExtra = "") {
    auto num = [](double v) { char b[64]; std::snprintf(b, sizeof b, "%.17g", v); return std::string(b); };
    return std::string("{\n  \"format_version\": 1,\n  \"corners\": [\n")
        + "    {\"id\": \"sw\", \"kind\": \"free\", \"xy\": [" + num(ax) + ", " + num(ay) + "]},\n"
        + "    {\"id\": \"se\", \"kind\": \"free\", \"xy\": [" + num(bx) + ", " + num(by) + "]},\n"
        + "    {\"id\": \"ne\", \"kind\": \"free\", \"xy\": [" + num(cx) + ", " + num(cy) + "]},\n"
        + "    {\"id\": \"nw\", \"kind\": \"free\", \"xy\": [" + num(dx) + ", " + num(dy) + "]}\n"
        + "  ],\n  \"edges\": [\n"
        + "    {\"id\": \"s\", \"corners\": [\"sw\", \"se\"], \"kind\": \"wall\", \"count\": "
        + std::to_string(ni) + iExtra + "},\n"
        + "    {\"id\": \"e\", \"corners\": [\"se\", \"ne\"], \"kind\": \"wall\", \"count\": "
        + std::to_string(nj) + jExtra + "},\n"
        + "    {\"id\": \"n\", \"corners\": [\"nw\", \"ne\"], \"kind\": \"wall\", \"count\": "
        + std::to_string(ni) + iExtra + "},\n"
        + "    {\"id\": \"w\", \"corners\": [\"sw\", \"nw\"], \"kind\": \"wall\", \"count\": "
        + std::to_string(nj) + jExtra + "}\n"
        + "  ],\n  \"blocks\": [\n    {\"id\": \"b0\", \"edges\": [\"s\", \"e\", \"n\", \"w\"]}\n  ]\n}";
}

std::string unitSquare(int ni, int nj, const std::string& iExtra = "",
                       const std::string& jExtra = "") {
    return blockDoc(0, 0, 1, 0, 1, 1, 0, 1, ni, nj, iExtra, jExtra);
}

MbResult build(const std::string& doc, bool split = true) {
    MbParams p;
    p.splitQuads = split;
    return hybmesh::buildMultiBlock(doc, {}, p);
}

const hybmesh::MbWallHeight* wall(const MbQualityReport& q, const std::string& side) {
    for (const auto& w : q.walls) if (w.side == side) return &w;
    return nullptr;
}

}  // namespace

int main() {
    // ── 1. A perfect block measures perfect, and every number is present ────
    // The instrument's zero. Without this every later check could be passing on
    // a metric that is simply always large.
    {
        const MbResult m = build(unitSquare(5, 5));
        CHECK(m.ok, "1. a unit square block fills");
        const MbQualityReport q = hybmesh::measureMbQuality(m);
        CHECK(q.cells == 32, "1. the report counts the cells that were produced");
        CHECK(q.invertedCells == 0, "1. a unit square holds no inverted cell");
        CHECK_NEAR(q.maxNonOrthoDeg, 0.0, 1e-9,
                   "1. ...and its grid lines are exactly orthogonal");
        CHECK_NEAR(q.meanNonOrthoDeg, 0.0, 1e-9, "1. ...on average too");
        CHECK(q.nonOrthoSamples == 4 * 4 * 4,
              "1. ...measured at all four corners of all 4x4 structured cells");
        CHECK(q.walls.size() == 4,
              "1. all four declared sides are reported, since v0 has no way to say "
              "which boundary is a viscous wall");
        // A TAUTOLOGY, and pinned as one: the request is the perpendicular edge's
        // own first interval and the transfinite blend is exact on the boundary,
        // so on a rectangle the two cannot differ. It is here to catch a sign or
        // an off-by-one, NOT as evidence the figure discriminates — check 7 is.
        CHECK_NEAR(q.worstWallRelError, 0.0, 1e-12,
                   "1. ...and on a rectangle the first cell off each of them equals "
                   "the request BY CONSTRUCTION, so this is a tautology check");
        const hybmesh::MbWallHeight* s = wall(q, "south");
        CHECK(s != nullptr, "1. the south side is named by its own side name");
        if (s) {
            CHECK(s->edgeId == "s",
                  "1. ...and carries the edge id the DOCUMENT declared, so the report "
                  "names the user's own edge rather than an index");
            CHECK_NEAR(s->requestedLo, 0.25, 1e-12, "1. ...asking 1/4 at its start corner");
            CHECK_NEAR(s->requestedHi, 0.25, 1e-12, "1. ...and 1/4 at its end corner");
            CHECK_NEAR(s->achievedMin, 0.25, 1e-12, "1. ...and getting 1/4 everywhere");
            CHECK_NEAR(s->achievedMax, 0.25, 1e-12, "1. ...at both ends of the range");
        }
    }

    // ── 2. STRETCH IS NOT NON-ORTHOGONALITY ─────────────────────────────────
    // The acceptance criterion in as many words: the number must come from cell
    // geometry and not from a proxy that runs long on stretched cells. A square
    // graded geometrically at 1.5 has a ~17x spread of cell sizes and grid lines
    // that are still exactly axis-aligned, so the honest answer is ZERO. An
    // aspect-ratio or edge-length proxy cannot produce zero here.
    {
        const MbResult m = build(unitSquare(9, 9, ", \"spacing\": {\"law\": \"geometric\", \"growth\": 1.5}"));
        CHECK(m.ok, "2. a geometrically graded square fills");
        const MbQualityReport q = hybmesh::measureMbQuality(m);
        CHECK_NEAR(q.maxNonOrthoDeg, 0.0, 1e-9,
                   "2. a strongly stretched but axis-aligned block is EXACTLY orthogonal, "
                   "which no size-based proxy can report");
        CHECK(q.invertedCells == 0, "2. ...and stretching alone inverts nothing");
        const hybmesh::MbWallHeight* w = wall(q, "west");
        const hybmesh::MbWallHeight* ea = wall(q, "east");
        CHECK(w != nullptr && ea != nullptr, "2. both i-graded sides are reported");
        if (w && ea) {
            // NEGATIVE CONTROL, computed rather than asserted: the zero above is
            // only interesting if this mesh really is stretched. The first cell off
            // the west wall against the first cell off the east wall IS the i-grading,
            // and at growth 1.5 over 8 intervals it is 1.5^7 ~= 17x.
            const double ratio = ea->requestedLo / w->requestedLo;
            CHECK(ratio > 15.0,
                  "2. ...on a mesh whose cells really do span a ~17x size range, so "
                  "the zero is a measurement and not a flat-mesh artefact");
            CHECK(w->requestedLo < 0.03 && w->requestedLo > 0.0,
                  "2. the first cell off the west wall is the graded interval, not the "
                  "uniform one");
            CHECK_NEAR(w->achievedMin, w->requestedLo, 1e-12,
                       "2. ...and the fill delivers exactly what the law asked for");
            CHECK_NEAR(w->worstRelError, 0.0, 1e-12,
                       "2. ...so its accuracy is 0% off, on a mesh no proxy would call good");
        }
    }

    // ── 3. A closed-form angle ──────────────────────────────────────────────
    // Every cell of a parallelogram block is the same parallelogram, so max and
    // mean must be EQUAL and both must be atan(1/2) exactly. A metric that is
    // merely monotone in "badness" cannot hit a closed form.
    {
        const MbResult m = build(blockDoc(0, 0, 1, 0, 1.5, 1, 0.5, 1, 5, 5));
        CHECK(m.ok, "3. a parallelogram block fills");
        const MbQualityReport q = hybmesh::measureMbQuality(m);
        const double want = std::atan(0.5) * 180.0 / M_PI;   // 26.565051...
        CHECK_NEAR(q.maxNonOrthoDeg, want, 1e-9,
                   "3. a shear of 1/2 measures atan(1/2) of non-orthogonality");
        CHECK_NEAR(q.meanNonOrthoDeg, want, 1e-9,
                   "3. ...and every corner of every cell agrees, so mean == max");
        CHECK(q.invertedCells == 0, "3. a sheared block is not an inverted one");
    }

    // ── 4. The detector BITES, through a declaration that is accepted ────────
    // A dart: the corner ring winds counter-clockwise (signed area +0.1), so
    // buildMultiBlock's clockwise-ring refusal does NOT fire — this is a VALID
    // declaration whose transfinite fill folds, which is exactly the case the
    // inverted-cell exit code exists for. Proven to bite rather than asserted.
    {
        const std::string dart = blockDoc(0, 0, 1, 0, 0.1, 0.1, 0, 1, 5, 5);
        const MbResult m = build(dart);
        CHECK(m.ok, "4. the dart topology is ACCEPTED — its corners wind CCW, so this "
                    "is a valid declaration and not a refusal in disguise");
        const MbQualityReport q = hybmesh::measureMbQuality(m);
        CHECK(q.invertedCells > 0,
              "4. ...and the fill folds, so the detector reports inverted cells");
        CHECK(q.invertedCells == 16,
              "4. ...16 of the 32 triangles, alternating diagonals included");
        CHECK(q.maxNonOrthoDeg > 45.0,
              "4. ...with a non-orthogonality that says the same thing another way");
        CHECK(q.worstWallRelError > 0.1,
              "4. ...and a wall first cell that missed what was asked for by more "
              "than 10%, so all three numbers are live on one mesh");
    }

    // ── 5. Inverted is counted over the EXPORTED cells ───────────────────────
    // With the split OFF the exported cells are quads, and the count has to be a
    // count of THOSE. A detector wired to the structured cells regardless would
    // report the same number either way.
    {
        const std::string dart = blockDoc(0, 0, 1, 0, 0.1, 0.1, 0, 1, 5, 5);
        const MbQualityReport tri = hybmesh::measureMbQuality(build(dart, true));
        const MbQualityReport quad = hybmesh::measureMbQuality(build(dart, false));
        CHECK(tri.cells == 32 && quad.cells == 16,
              "5. the same topology exports 32 triangles or 16 quads");
        CHECK(quad.invertedCells > 0, "5. the quad export reports inverted cells too");
        CHECK(tri.invertedCells != quad.invertedCells,
              "5. ...and a different number of them, because the count is over the "
              "cells that are actually exported");
        CHECK_NEAR(tri.maxNonOrthoDeg, quad.maxNonOrthoDeg, 1e-12,
                   "5. non-orthogonality, by contrast, is the same either way — it is a "
                   "property of the grid and not of how the quads were cut");
    }

    // ── 6. A bow-tie quad, whose SIGNED AREA IS POSITIVE ────────────────────
    // (0,0) (3,0) (0,1) (2,1) self-intersects, and its shoelace area is +0.5. A
    // signed-area test — the obvious implementation — calls it fine. The rule has
    // to be per-corner. Hand-built, so this holds for any producer of cells and
    // not just for the transfinite fill.
    {
        MbResult m;
        m.ok = true;
        m.nodes = {{0.0, 0.0}, {3.0, 0.0}, {0.0, 1.0}, {2.0, 1.0}};
        m.cells.push_back(hybmesh::MbCell{{0, 1, 2, 3}, 0});
        // NEGATIVE CONTROL, computed here rather than claimed in a comment: the
        // shoelace area really is positive, so an area-based detector really would
        // pass this cell. Without it the check below could be passing for any reason.
        double area2 = 0.0;
        for (size_t k = 0; k < m.nodes.size(); ++k)
            area2 += m.nodes[k].cross(m.nodes[(k + 1) % m.nodes.size()]);
        CHECK(area2 > 0.0,
              "6. the bow-tie's own shoelace area is POSITIVE, so an area test would "
              "call it sound");
        const MbQualityReport q = hybmesh::measureMbQuality(m);
        CHECK(q.invertedCells == 1,
              "6. ...and it is reported inverted anyway, so the rule is per-corner "
              "and not an area test");
        CHECK(q.nonOrthoSamples == 0,
              "6. ...and with no block declared there is no structured grid to measure");
        CHECK(q.maxNonOrthoDeg < 0.0 && q.meanNonOrthoDeg < 0.0,
              "6. ...so both angle figures are NEGATIVE, not the excellent-looking "
              "0.000 deg that would be a false claim");
        CHECK(q.worstWallRelError < 0.0,
              "6. ...and an unmeasured wall accuracy is negative, never 0% — "
              "'we did not measure' must not read as 'it was perfect'");
    }

    // ── 6b. A wall the request says nothing measurable about ────────────────
    // The ROW-level half of the "negative when unmeasured" rule, and it needs its
    // own case: check 6 declares no wall at all, so it exercises the REPORT's
    // default and never a row's. A degenerate perpendicular edge — two coincident
    // corners — is how a zero request really arises. This check exists BECAUSE the
    // injection that defaults `MbWallHeight::worstRelError` to 0.0 passed every
    // other check in this file; the rule was unguarded until it was written.
    {
        MbResult m;
        m.ok = true;
        // A 2x2 block, so there really is a first cell to measure off the south side.
        m.nodes = {{0.0, 0.0}, {1.0, 0.0}, {0.0, 1.0}, {1.0, 1.0}};
        hybmesh::MbBlock b;
        b.id = "b";
        b.ni = 2;
        b.nj = 2;
        b.nodeIds = {0, 1, 2, 3};      // index = j * ni + i
        m.blocks.push_back(b);
        hybmesh::MbWallSpec ws;
        ws.block = 0;
        ws.side = hybmesh::MB_SOUTH;
        ws.edgeId = "collapsed";
        ws.requestedLo = 0.0;          // the perpendicular edges asked for nothing
        ws.requestedHi = 0.0;
        m.wallSpecs.push_back(ws);
        const MbQualityReport q = hybmesh::measureMbQuality(m);
        CHECK(q.walls.size() == 1,
              "6b. a wall whose request is unmeasurable is still LISTED — a wall that "
              "could not be measured is worth seeing");
        if (q.walls.size() == 1)
            CHECK(q.walls[0].worstRelError < 0.0,
                  "6b. ...with its OWN accuracy negative rather than a flawless 0%");
        CHECK(q.worstWallRelError < 0.0,
              "6b. ...and it does not drag the headline down to 0% either, which would "
              "report the best possible accuracy for a wall nobody could measure");
    }

    // ── 7. A block whose fill cannot honour the declared wall spacing ────────
    // A trapezoid: both i-edges ask for the same first interval at one end and a
    // longer one at the other, and the transfinite blend lands between them, so
    // the number is neither 0 nor the dart's. This is the figure the later
    // elliptic-smoothing increment moves.
    {
        const MbResult m = build(blockDoc(0, 0, 1, 0, 2, 1, 0, 1, 5, 5));
        CHECK(m.ok, "7. a trapezoid block fills");
        const MbQualityReport q = hybmesh::measureMbQuality(m);
        CHECK(q.invertedCells == 0, "7. ...without inverting anything");
        CHECK(q.worstWallRelError > 0.01,
              "7. ...but its wall first cell is measurably off what was declared");
        CHECK(q.worstWallRelError < 0.2,
              "7. ...by less than the folded case, so the number discriminates rather "
              "than merely firing");
        CHECK_NEAR(q.maxNonOrthoDeg, 45.0, 1e-9,
                   "7. and its worst corner is the 45 degrees the two edges meet at");
        // WHERE the deviation is, pinned so the figure is not over-read: the side's
        // two END columns reproduce their own perpendicular edge exactly (the blend
        // is exact on the boundary), so the whole 7.4% comes from the interior. This
        // is the blind spot MbWallHeight declares, as a check rather than as prose.
        const hybmesh::MbWallHeight* sw = wall(q, "south");
        CHECK(sw != nullptr, "7. the south side is reported");
        if (sw) {
            CHECK_NEAR(sw->achievedMin, std::min(sw->requestedLo, sw->requestedHi), 1e-12,
                       "7. ...its end columns are the request itself, exactly");
            CHECK_NEAR(sw->achievedMax, std::max(sw->requestedLo, sw->requestedHi), 1e-12,
                       "7. ...at both ends, so the figure measures interior drift only");
        }
    }

    // ── 8. An empty mesh is measured, not crashed on ─────────────────────────
    {
        MbResult m;
        m.ok = true;
        const MbQualityReport q = hybmesh::measureMbQuality(m);
        CHECK(q.cells == 0 && q.invertedCells == 0 && q.walls.empty(),
              "8. measuring nothing reports nothing and does not reach past an end");
        CHECK(q.nonOrthoSamples == 0 && q.maxNonOrthoDeg < 0.0 && q.meanNonOrthoDeg < 0.0
              && q.worstWallRelError < 0.0,
              "8. ...and EVERY measured figure comes back negative rather than 0, so an "
              "empty mesh cannot read as a flawless one (and nothing divided by a zero "
              "sample count)");
    }

    return hybmesh::test::report("test_mb_quality");
}
