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
//   * Non-orthogonality AND cell shape are both measured on the STRUCTURED grid
//     cells, so nothing here says anything about the shape of the split
//     triangles. That is deliberate and argued at the declaration in
//     include/MbQuality.hpp; the exported triangles are the HYBRID path's figure,
//     under its own name (`tri_edge_ratio`), and a solver-facing skewness metric
//     is a third instrument again.
//   * Nothing here pins the METRIC's own arithmetic — that a square is 1.0, that
//     a degenerate cell does not divide by zero, how p95 is ranked. That is the
//     shared pure module's, and it is pinned in tests/cpp/test_cell_shape.cpp.
//     What check 9 pins is which cells this report hands it and what it does with
//     the answer.
//   * Nothing here says the three shape figures reach the banner, the machine
//     line or the `.provenance.json` sidecar, or that those three agree. That is
//     external behaviour of the binary, pinned in
//     tools/PreProcessor/tests/test_multiblock_shape_surface.py.
//   * The wall first-cell height is a distance ALONG the grid line, not the
//     perpendicular distance to the wall. On a non-orthogonal block the two
//     differ by cos(non-orthogonality), which is why both numbers are reported
//     together — but no check here pins that relationship.
//   * The wall figure's REQUEST is derived from the same spacing law the fill
//     reproduces, so on a rectangle it is 0.00% as a TAUTOLOGY (check 1 pins
//     that, and says so). Check 7 is where it earns its keep. An independent
//     wall-spacing target is later work; see MbWallHeight's declaration.
//
// INJECTIONS: run BY HAND at review time — 2026-08-27 for A-F, 2026-09-17 for
// G, H, I, J and K, which are #129's — and recorded here rather
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
//   G. CELL SHAPE measured on the EXPORTED cells instead of the structured quads
//      -> 11 failures, across checks 9 (x6), 9b (x2), 9c (x2) and 9d (x2).
//   H. a block whose shape could not be measured dropped from `blockShapes`
//      instead of listed with negative figures -> 1 failure, check 9d alone.
//      CHECK 9d EXISTS BECAUSE OF 6b's history: the row-level half of the
//      negative rule was unguarded there until an injection said so, and this
//      figure's rows would have repeated it.
//   K. a structured quad whose ids do not all resolve passed on SHORT, so three
//      resolving corners reach the metric as a TRIANGLE and come back with an
//      ordinary edge ratio for a cell nobody could measure -> 2 failures, check
//      9e alone. WORTH READING WITH ITS FIXTURE: check 9e's first draft put the
//      dangling id in the slot walked THIRD, which stops the walk at two corners
//      and is refused for being too short — so this injection PASSED until the
//      fixture moved it to the slot walked last. The check was written for the
//      defect and did not reach it.
//   J. the structured quad's four corners read in Z order — (i,j) (i+1,j)
//      (i,j+1) (i+1,j+1) — instead of around the ring -> 11 failures, across
//      checks 9 (x4), 9b, 9c (x2) and 9d (x4). The classic transcription slip,
//      and it collapses one midline to zero, so the cells report unmeasurable
//      rather than merely wrong.
//
// AND ONE THAT IS INERT, recorded because "we tried and it did not bite" is worth
// more than silence:
//   I. an unmeasurable structured quad folded into the statistics as 0.0 instead
//      of being dropped -> 0 failures. `reduceCellShapes` discards a 0.0 by the
//      same `> 0.0` test it discards a negative by, so the rule survives this
//      layer getting it wrong. It is guarded ONE level down, in
//      tests/cpp/test_cell_shape.cpp check 8, and this file inherits it rather
//      than holding it.
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

// A hand-built block on an explicit grid of y levels, uniform in x at spacing 1.0,
// so every cell's two extents are known exactly and the wall band's walk can be
// pinned cell by cell. `wallSides` is what the DOCUMENT is taken to have declared.
//
// BUILT BY HAND RATHER THAN PARSED, for check 9e's reason: the band is a rule about
// which cells a walk reaches, and a fixture whose spacing came out of a spacing law
// would make the expected answer something this test also has to derive.
MbResult ladder(const std::vector<double>& ys, int ni,
                const std::vector<hybmesh::MbSide>& wallSides) {
    MbResult m;
    m.ok = true;
    hybmesh::MbBlock b;
    b.id = "ladder";
    b.ni = ni;
    b.nj = static_cast<int>(ys.size());
    for (double y : ys)
        for (int i = 0; i < ni; ++i) {
            b.nodeIds.push_back(static_cast<int>(m.nodes.size()));
            m.nodes.push_back({static_cast<double>(i), y});
        }
    m.blocks.push_back(b);
    for (hybmesh::MbSide side : wallSides) {
        hybmesh::MbWallSpec ws;
        ws.block = 0;
        ws.side = side;
        ws.edgeId = "declared";
        m.wallSpecs.push_back(ws);
    }
    return m;
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
        CHECK(q.structuredShape.cells == 0 && q.structuredShape.median < 0.0
              && q.structuredShape.p95 < 0.0 && q.structuredShape.max < 0.0,
              "8. ...the three SHAPE figures included, which is the same rule applied to "
              "the figures #129 added and not a second rule beside it");
        CHECK(q.blockShapes.empty(),
              "8. ...and a mesh with no blocks lists no per-block shape rows");
    }

    // ── 9. CELL SHAPE: the structured quads, and the split cannot move it ────
    // Issue #129. The figure exists so a user can read a mesh against "is this
    // 1:1?", which is only possible because it is measured on the cell the
    // DOCUMENT declares rather than on the triangles the split produces.
    {
        const MbQualityReport q = hybmesh::measureMbQuality(build(unitSquare(5, 5)));
        CHECK(q.structuredShape.cells == 16,
              "9. a 5x5-node block has 16 structured quads, and the shape figure is "
              "measured over all of them");
        CHECK(q.cells == 32,
              "9. ...while it EXPORTS 32 triangles, so the two counts are visibly "
              "different quantities and not one number used twice");
        CHECK_NEAR(q.structuredShape.median, 1.0, 1e-12,
                   "9. every cell of a unit square is square, so the median is EXACTLY "
                   "1.0 — not the 1.414 the split triangles would report");
        CHECK_NEAR(q.structuredShape.p95, 1.0, 1e-12, "9. ...and so is p95");
        CHECK_NEAR(q.structuredShape.max, 1.0, 1e-12, "9. ...and so is the max");
        CHECK(q.blockShapes.size() == 1 && q.blockShapes[0].blockId == "b0",
              "9. one row per block, named with the id the DOCUMENT gave it");
        if (q.blockShapes.size() == 1)
            CHECK(q.blockShapes[0].shape.cells == q.structuredShape.cells
                  && q.blockShapes[0].shape.max == q.structuredShape.max,
                  "9. ...and with one block the row and the headline agree exactly");
    }

    // ── 9b. INDEPENDENT OF MB_SPLIT_QUADS, measured rather than argued ───────
    // The same topology filled twice, once exporting triangles and once quads. The
    // EXPORTED count must move and the four shape figures must not — the precedent
    // non-orthogonality already set (check 5), applied to the new figure.
    {
        // A graded, non-square block, so the figures are a spread of real numbers
        // rather than 1.0 four times over, which any pair of runs would agree on.
        const std::string doc = blockDoc(0, 0, 4, 0, 4, 1, 0, 1, 9, 9,
                                         ", \"spacing\": {\"law\": \"geometric\", \"growth\": 1.5}");
        const MbQualityReport tri = hybmesh::measureMbQuality(build(doc, true));
        const MbQualityReport quad = hybmesh::measureMbQuality(build(doc, false));
        // NEGATIVE CONTROL, computing this check's own premise twice over: the two
        // runs really did export different cells, and the figure really does have a
        // spread to lose — so "unchanged" below is a measurement and not two
        // constants agreeing.
        CHECK(tri.cells == 2 * quad.cells && quad.cells == 64,
              "9b. the split really did change what was exported: 128 triangles "
              "against 64 quads");
        CHECK(tri.structuredShape.max > tri.structuredShape.median + 0.5,
              "9b. ...and this block's cells really do span a range, so an unchanged "
              "median is not an artefact of every cell being the same");
        CHECK(tri.structuredShape.cells == quad.structuredShape.cells
              && tri.structuredShape.cells == 64,
              "9b. both runs measure the same 64 STRUCTURED quads");
        CHECK(tri.structuredShape.median == quad.structuredShape.median
              && tri.structuredShape.p95 == quad.structuredShape.p95
              && tri.structuredShape.max == quad.structuredShape.max,
              "9b. ...and report BITWISE the same three figures, so turning the split "
              "off to diagnose a mesh does not change the number being diagnosed");
    }

    // ── 9c. A rectangle reports its own side ratio, through the whole report ─
    // The end-to-end reading of the figure: a user who declares a 4-by-1 block at
    // equal counts gets a 4:1 cell and the report says 4.
    {
        const MbQualityReport q =
            hybmesh::measureMbQuality(build(blockDoc(0, 0, 4, 0, 4, 1, 0, 1, 5, 5)));
        CHECK_NEAR(q.structuredShape.max, 4.0, 1e-12,
                   "9c. a 4x1 block at equal counts reports 4.0 — the user's own side "
                   "ratio, in the units they already have");
        CHECK_NEAR(q.structuredShape.median, 4.0, 1e-12,
                   "9c. ...for every cell in it, so median and max agree");
        CHECK_NEAR(q.maxNonOrthoDeg, 0.0, 1e-9,
                   "9c. ...on a block that is EXACTLY orthogonal, which is the pair of "
                   "numbers that makes the two figures readable together: stretched and "
                   "square-cornered is a different mesh from skewed and 1:1");
    }

    // ── 9d. The ROW level of the 'negative when unmeasured' rule ─────────────
    // The half check 9 cannot reach: a report holding one measurable block AND one
    // that yields nothing. The headline must describe the block it could measure
    // while the other block's own row stays negative — never 0, which on this
    // metric is not merely flattering but IMPOSSIBLE, since its floor is 1.0.
    // Hand-built, so it holds for any producer of blocks and not just the fill.
    {
        MbResult m;
        m.ok = true;
        m.nodes = {{0.0, 0.0}, {1.0, 0.0}, {0.0, 1.0}, {1.0, 1.0}};
        hybmesh::MbBlock good;
        good.id = "good";
        good.ni = 2;
        good.nj = 2;
        good.nodeIds = {0, 1, 2, 3};   // index = j * ni + i
        m.blocks.push_back(good);
        hybmesh::MbBlock thin;
        thin.id = "thin";              // one node wide: it has no quad at all
        thin.ni = 1;
        thin.nj = 2;
        thin.nodeIds = {0, 2};
        m.blocks.push_back(thin);
        const MbQualityReport q = hybmesh::measureMbQuality(m);
        CHECK(q.blockShapes.size() == 2,
              "9d. a block that yields nothing measurable is still LISTED, the way an "
              "unmeasurable wall row is");
        if (q.blockShapes.size() == 2) {
            CHECK(q.blockShapes[0].blockId == "good" && q.blockShapes[0].shape.cells == 1,
                  "9d. the measurable block reports its one quad");
            CHECK_NEAR(q.blockShapes[0].shape.median, 1.0, 1e-12,
                       "9d. ...as the unit square it is");
            CHECK(q.blockShapes[1].blockId == "thin" && q.blockShapes[1].shape.cells == 0,
                  "9d. the one-node-wide block measures no cells");
            CHECK(q.blockShapes[1].shape.median < 0.0 && q.blockShapes[1].shape.p95 < 0.0
                  && q.blockShapes[1].shape.max < 0.0,
                  "9d. ...and its OWN three figures are NEGATIVE, so the row prints "
                  "'not measured' rather than a number the metric cannot even produce");
        }
        CHECK(q.structuredShape.cells == 1,
              "9d. the headline is over the cells that WERE measurable, one of them");
        CHECK_NEAR(q.structuredShape.max, 1.0, 1e-12,
                   "9d. ...and the unmeasurable block does not drag it anywhere, which a "
                   "0.0 folded into the statistics would");
    }

    // ── 9e. A structured quad one of whose ids names nothing ────────────────
    // The shape loop resolves four ids per cell, and the obvious implementation
    // passes on whatever resolved. Three of four resolving is then handed to the
    // pure metric as a TRIANGLE, which measures it happily and reports an ordinary
    // edge ratio for a cell nobody could measure. The only honest answer is that
    // the cell is unmeasurable, and this check is what says so.
    {
        MbResult m;
        m.ok = true;
        m.nodes = {{0.0, 0.0}, {1.0, 0.0}, {0.0, 1.0}};   // one node short
        hybmesh::MbBlock b;
        b.id = "ragged";
        b.ni = 2;
        b.nj = 2;
        // THE DANGLING ID HAS TO BE THE ONE VISITED LAST, or this check does not
        // discriminate: the ring order is (i,j) (i+1,j) (i+1,j+1) (i,j+1), i.e.
        // nodeIds 0, 1, 3, 2, so a bad id anywhere but slot 2 stops the walk with
        // FEWER than three corners and the metric refuses it for being too short
        // rather than for the reason this check is about. The first draft put it in
        // slot 3 and the injection below passed. `nodeAt(i, j)` is `nodeIds[j*ni+i]`.
        b.nodeIds = {0, 1, 99, 2};    // the NW corner, walked last, names nothing
        m.blocks.push_back(b);
        // NEGATIVE CONTROL, computed rather than claimed: the three ids that DO
        // resolve really do form a measurable triangle, so "unmeasurable" below is
        // this loop's decision and not an accident of the coordinates.
        CHECK(hybmesh::cellShapeRatio({m.nodes[0], m.nodes[1], m.nodes[2]}) > 0.0,
              "9e. the three resolving corners DO form a measurable triangle, so a "
              "loop that passed on what resolved would report a number here");
        const MbQualityReport q = hybmesh::measureMbQuality(m);
        CHECK(q.structuredShape.cells == 0 && q.structuredShape.max < 0.0,
              "9e. ...and the report measures nothing, because a quad missing a "
              "corner is not a triangle");
        CHECK(q.blockShapes.size() == 1 && q.blockShapes[0].shape.cells == 0,
              "9e. ...with the block still listed and its own figures negative");
    }

    // ── 10. THE WALL BAND: the contiguous run off a declared wall ───────────
    // #144's subject. A ladder whose first two rows are thinner across the wall
    // than along it and whose third is not: the band is the first two, the walk
    // STOPS at the third, and the two halves partition what the whole set
    // measured.
    {
        const MbResult m = ladder({0.0, 0.1, 0.5, 2.0}, 4, {hybmesh::MB_SOUTH});
        const MbQualityReport q = hybmesh::measureMbQuality(m);
        // NEGATIVE CONTROLS, computed rather than claimed: the row the walk stops
        // at is MEASURABLE and is genuinely wider across the wall than along it,
        // so "the band ends here" is this walk's decision and not an absent or
        // unmeasurable cell. Both extents are read from the shared pure helper the
        // implementation uses, in the ring order `quadCorners` builds.
        double e01 = 0.0, e12 = 0.0;
        CHECK(hybmesh::quadExtents({{0.0, 0.5}, {1.0, 0.5}, {1.0, 2.0}, {0.0, 2.0}},
                                   e01, e12)
              && e12 > e01 && hybmesh::cellShapeRatio({{0.0, 0.5}, {1.0, 0.5},
                                                       {1.0, 2.0}, {0.0, 2.0}}) > 0.0,
              "10. the row the walk stops at is measurable and really is WIDER "
              "across the wall than along it (1.5 against 1.0)");
        CHECK(q.structuredShape.cells == 9
              && q.structuredLayerShape.cells == 6
              && q.structuredBulkShape.cells == 3,
              "10. the band is the two squeezed rows and the bulk is the third: "
              "the walk stops at the first cell that is not squeezed rather than "
              "collecting every squeezed cell in the block");
        CHECK(q.structuredLayerShape.cells + q.structuredBulkShape.cells
                  == q.structuredShape.cells,
              "10. ...and the two halves PARTITION what the whole set measured, so "
              "no cell is counted twice and none is lost between them");
        // The rows measure 1/0.1, 1/0.4 and 1.5/1, so every figure below is
        // arithmetic on the fixture rather than a number read off a run.
        CHECK_NEAR(q.structuredLayerShape.median, 6.25, 1e-12,
                   "10. ...the band's median is the two squeezed rows' (10 and 2.5)");
        CHECK_NEAR(q.structuredLayerShape.max, 10.0, 1e-12,
                   "10. ...and its max is the row ON the wall");
        CHECK_NEAR(q.structuredBulkShape.median, 1.5, 1e-12,
                   "10. ...while the bulk is the third row alone");
        CHECK_NEAR(q.structuredBulkShape.max, 1.5, 1e-12,
                   "10. ...max included, so the band took the whole stretch with it");
        CHECK_NEAR(q.structuredShape.median, 2.5, 1e-12,
                   "10. ...and the WHOLE-MESH figures are untouched by the split");
        CHECK_NEAR(q.structuredShape.max, 10.0, 1e-12,
                   "10. ...max included");
    }

    // ── 10b. A block with NO declared wall side is all bulk ─────────────────
    // By construction — it has no side to walk from — which is the half of the
    // rule that would otherwise be written twice.
    {
        const MbResult m = ladder({0.0, 0.1, 0.5, 2.0}, 4, {});
        const MbQualityReport q = hybmesh::measureMbQuality(m);
        CHECK(q.structuredLayerShape.cells == 0
              && q.structuredLayerShape.median < 0.0
              && q.structuredLayerShape.p95 < 0.0
              && q.structuredLayerShape.max < 0.0,
              "10b. a block no side of which is declared a wall has an EMPTY band, "
              "reported as 0 cells with three NEGATIVE figures rather than zeros");
        CHECK(q.structuredBulkShape.cells == q.structuredShape.cells
              && q.structuredBulkShape.cells == 9,
              "10b. ...and every one of its cells is bulk — the same ladder whose "
              "first two rows check 10 banded, so this is the DECLARATION deciding "
              "it and not the geometry");
    }

    // ── 10c. The band does not jump a gap ──────────────────────────────────
    // A ladder whose row ON the wall is not squeezed and whose SECOND row is. The
    // band is empty: it is the contiguous run off the wall, not every squeezed
    // cell in the block wherever it sits.
    {
        const MbResult m = ladder({0.0, 2.0, 2.1, 4.0}, 4, {hybmesh::MB_SOUTH});
        const MbQualityReport q = hybmesh::measureMbQuality(m);
        // NEGATIVE CONTROL: the second row really IS squeezed, so "empty" below is
        // the walk refusing to jump the first row rather than a fixture with
        // nothing in it to find.
        double e01 = 0.0, e12 = 0.0;
        CHECK(hybmesh::quadExtents({{0.0, 2.0}, {1.0, 2.0}, {1.0, 2.1}, {0.0, 2.1}},
                                   e01, e12) && e12 < e01,
              "10c. the SECOND row really is squeezed toward the wall (0.1 across "
              "against 1.0 along), so a band that collected it would not be empty");
        CHECK(q.structuredLayerShape.cells == 0
              && q.structuredBulkShape.cells == q.structuredShape.cells,
              "10c. ...and the band is still EMPTY, because the walk stops at the "
              "row on the wall: the band is contiguous FROM the wall");
    }

    // ── 10d. Two walls on one block, unioned and not double-counted ────────
    // The shipped O-grid declares both its body arc and its far-field arc `wall`,
    // so a block really can be walked from opposite sides. This also pins the
    // FAR-END walk's indexing: a north side that stepped the wrong way would band
    // the middle rows instead of the last.
    {
        const MbResult m = ladder({0.0, 0.1, 1.6, 3.1, 3.2}, 4,
                                  {hybmesh::MB_SOUTH, hybmesh::MB_NORTH});
        const MbQualityReport q = hybmesh::measureMbQuality(m);
        CHECK(q.structuredShape.cells == 12
              && q.structuredLayerShape.cells == 6
              && q.structuredBulkShape.cells == 6,
              "10d. both walls contribute their own row and the two middle rows "
              "are bulk, so the sides UNION rather than one of them winning");
        // The two banded rows are 1/0.1 and the two bulk rows 1.5/1, so the
        // figures say WHICH cells landed where — a north walk that stepped inward
        // from the wrong end would band a 1.5 row and show up here.
        CHECK_NEAR(q.structuredLayerShape.median, 10.0, 1e-12,
                   "10d. ...and the band is the two rows ON the walls (10 each), "
                   "not the two in the middle");
        CHECK_NEAR(q.structuredBulkShape.max, 1.5, 1e-12,
                   "10d. ...while the bulk is the two middle rows (1.5 each)");
        CHECK(q.structuredLayerShape.cells + q.structuredBulkShape.cells
                  == q.structuredShape.cells,
              "10d. ...with no cell counted twice, which a union has to be asked");
    }

    // ── 10e. Two extents that agree to within rounding are not a band ──────
    // A uniform grid clusters NOTHING, and the shipped square is one: 400
    // geometrically identical cells whose two midlines come out of a `hypot` a
    // last bit apart. A bare `across < along` banded 72 of them.
    {
        const MbResult m = ladder({0.0, 1.0, 2.0, 3.0}, 4, {hybmesh::MB_SOUTH});
        const MbQualityReport q = hybmesh::measureMbQuality(m);
        // NEGATIVE CONTROL: every cell here is measurable and square, so an empty
        // band below is the tie rule and not an unmeasurable fixture.
        CHECK_NEAR(q.structuredShape.max, 1.0, 1e-12,
                   "10e. every cell of a uniform ladder is square, so nothing in it "
                   "is squeezed toward anything");
        CHECK(q.structuredLayerShape.cells == 0
              && q.structuredBulkShape.cells == 9,
              "10e. ...and its band is EMPTY rather than however many cells the "
              "last bit of a midline happened to fall the wrong way");
    }

    // ── 10f. The band is independent of MB_SPLIT_QUADS ─────────────────────
    // The same rule `structuredShape` already follows (check 9b), through the real
    // builder: both sets are measured on the structured quads, so turning the split
    // off to diagnose a mesh does not change the sets being diagnosed.
    //
    // THIS FIXTURE'S BULK IS EMPTY, and that is a property of a ONE-BLOCK document
    // rather than a weakness that went unnoticed: every side of one is a `wall`, so
    // a row wider in j than in i is banded across its whole width from the west and
    // the east. The O-grid has a bulk because its two radial sides are `interface`
    // edges and its far-field row is longer radially than azimuthally — a topology
    // this file cannot write in four lines. The STRICT-SUBSET case is pinned on all
    // five shipped cases at `MB_SPLIT_QUADS 0` in
    // tools/PreProcessor/tests/test_multiblock_shape_surface.py check 15.
    {
        const std::string doc = unitSquare(9, 9, "", ", \"spacing\": {\"ds_start\": 0.01}");
        const MbQualityReport tri = hybmesh::measureMbQuality(build(doc, true));
        const MbQualityReport quad = hybmesh::measureMbQuality(build(doc, false));
        CHECK(tri.structuredShape.cells == 64
              && tri.structuredLayerShape.cells == 64
              && tri.structuredBulkShape.cells == 0,
              "10f. a one-block document clustered toward one wall bands every cell, "
              "because all four of its sides are walls and the band reaches across");
        CHECK(tri.cells == 2 * quad.cells && quad.cells == 64,
              "10f. ...and the split really did change what was exported, so an "
              "unchanged pair of sets below is a measurement and not two runs of "
              "the same thing");
        CHECK(tri.structuredLayerShape.cells == quad.structuredLayerShape.cells
              && tri.structuredBulkShape.cells == quad.structuredBulkShape.cells
              && tri.structuredLayerShape.median == quad.structuredLayerShape.median
              && tri.structuredLayerShape.p95 == quad.structuredLayerShape.p95
              && tri.structuredLayerShape.max == quad.structuredLayerShape.max,
              "10f. ...reporting BITWISE the same two sets either way");
    }

    return hybmesh::test::report("test_mb_quality");
}
