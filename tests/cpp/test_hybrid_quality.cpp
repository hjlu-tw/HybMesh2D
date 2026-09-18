// WHICH CELLS THE HYBRID PATH OFFERS TO THE SHAPE METRIC (issue #141; the rule
// and the figures are #130's), tested through `measureHybridCellShapes` and
// nothing else.
//
// This executable links `hybmesh_pure` and NOTHING else — not gmsh, not
// hybmesh_core, and it never builds a `Mesh`. That build property is the whole
// reason the decision was lifted out of `src/cli.cpp` at all: until #141 it was a
// `static` function inside the CLI translation unit, so its three separate rules
// — the corner-count floor, the corner-count ceiling and the unresolved id —
// were covered only by a surface gate driving the whole binary, one mesh at a
// time. Each of them can be wrong on its own, and each gets its own check here.
//
// WHAT IS NOT THIS FILE'S SUBJECT. The arithmetic of the metric is
// tests/cpp/test_cell_shape.cpp: a square is 1.0 and each of its split triangles
// sqrt(2), a degenerate cell does not divide by zero, how p95 is ranked. This
// file takes that as given and asserts what reaches it and what does not.
// WHERE A CHECK HAS TO SAY WHICH CELL REACHED THE METRIC, its fixture is built so
// the two answers cannot coincide — check 4's 4x1 rectangle measures 4.0 beside a
// triangle's 1.0, and a SQUARE there would have measured 1.0 either way. That is a
// rule about those checks, not about every fixture here: checks 1, 8 and 9 hand in
// cells that measure alike on purpose, because what they assert is a COUNT.
//
// BLIND SPOTS, named rather than papered over:
//   * Nothing here prints a banner row, a machine line or a sidecar. That the
//     figures and BOTH counts reach a run's three surfaces and agree there is
//     external behaviour of the binary, pinned in
//     tools/PreProcessor/tests/test_hybrid_shape_surface.py.
//   * Nothing here says that the exported cells of a real hybrid mesh are
//     triangles. That is `src/BoundaryLayer.cpp`'s doing (the BL strip is emitted
//     as two triangles per column) and the surface gate's 15233-cell run is where
//     it is visible; here it is an assumption the fixtures encode.
//   * The `nodes` array this file hands in is a copy of the mesh's coordinates.
//     That `src/cli.cpp` fills it from `Mesh::nodes` in the right order — rather
//     than, say, from a renumbered export — is not checked here and cannot be:
//     the surface gate's figures are what would move.
//   * A cell whose ids all RESOLVE but name a coincident corner (check 6's
//     `{0, 0, 1}`) is degenerate, not unresolved, and is dropped by the metric
//     rather than by this module. Check 6 pins that it lands in the gap between
//     the two counts, not which of the two modules dropped it.
//   * The module's "an unresolved cell must not pass on SHORT" rule is NOT
//     guarded here, and injection C below is the measurement that says so rather
//     than an omission noticed later: on this path no fixture can reach the defect
//     it stops, because only three-id cells reach the resolve loop. It is guarded
//     one level down by the metric's own corner-count floor, and it starts
//     mattering here the moment a cell with more than three corners is offered.
//
// INJECTIONS: run BY HAND at review time, 2026-09-18, and recorded here rather
// than written as in-test injections — a C++ test cannot mutate the
// implementation it linked against, so unlike the Python gates next door these
// cannot re-run themselves. Each names the checks it broke, so a later reader can
// tell a check that bites from one that merely passes:
//
//   A. the corner-count floor widened from `< 3` to `< 2`, so a two-node
//      visualisation entry becomes a cell -> 4 failures: `offered` and
//      `nonTriangles` in BOTH check 2 and check 3. The second half of that is the
//      finding — such an entry is offered and then lands on the NON-TRIANGLE row,
//      so the banner would tell a user that a boundary segment is a cell with the
//      wrong corner count. `shape.cells` moves in neither check, because the
//      corner-count ceiling still skips the entry before the metric sees it.
//   B. the corner-count ceiling dropped (`!= 3` no longer skips, every offered
//      cell fed to the metric) -> 4 failures: check 4's `cells` and its figure,
//      check 6's `cells`, and check 8's whole not-measured state. The 4x1
//      rectangle then comes back as a MIDLINE ratio of 4.0 wearing the name
//      `tri_edge_ratio`, which is what check 4's fixture is built to see: a SQUARE
//      beside an equilateral triangle would have measured 1.0 either way and this
//      injection would have passed.
//   C. an unresolved cell passed on SHORT (`corners` as walked, instead of an
//      empty list) -> **INERT, 0 failures**, recorded because "we tried and it did
//      not bite" is worth more than silence. Only THREE-id cells reach the resolve
//      loop at all — the ceiling skipped everything longer — so the prefix walked
//      before the bad id is at most two corners, which `cellShapeRatio` refuses
//      for being too short and `reduceCellShapes` drops by the same `> 0.0` test
//      it drops a negative by. The empty list is therefore belt to the metric's
//      braces ON THIS PATH, and the rule is guarded one level down in
//      tests/cpp/test_cell_shape.cpp. The shape it exists to stop — a cell whose
//      surviving prefix is still long enough to measure — needs a FOUR-corner cell
//      with three resolving ids, which is the multi-block path's case and is check
//      9e of test_mb_quality.cpp. There is no fixture here that would reach it,
//      which is why none is written: a check for a defect it cannot reach is the
//      shape this repo keeps finding. It matters again the moment #143 offers a
//      longer cell.
//      Worth knowing for the next injector: the literal spelling of this mutation
//      does not COMPILE under the `-Werror` build CI uses (`resolved` is then set
//      and never read), so it had to be written with a `(void)resolved;` beside
//      it. A defect the compiler refuses is guarded, but only in that spelling.
//   D. `nonTriangles` counted over ALL entries rather than the offered ones, so a
//      two-node entry lands on the non-triangle row -> 2 failures, that one
//      assertion in check 2 and in check 3. Nothing else moves: `offered` is still
//      right, which is what makes the two counts worth asserting separately.
//   E. an empty input short-circuited to a zero-filled report (figures 0.0 instead
//      of negative) -> 1 failure, check 7's third assertion alone. `cells` is 0
//      either way, so the count says nothing about this defect. Check 8 does NOT
//      move: its input is non-empty, so the short circuit never runs — the two are
//      separate inputs to one reported state, which is the surface gate's checks
//      10 and 12 one level down.
#include "HybridQuality.hpp"
#include "check.hpp"

#include <cmath>
#include <vector>

using hybmesh::HybridShapeReport;
using hybmesh::measureHybridCellShapes;

namespace {

// A node table shared by most fixtures below. The first three make an EQUILATERAL
// triangle (ratio exactly 1.0, the metric's floor); 3..6 make a 4x1 RECTANGLE
// (midline ratio exactly 4.0). Two cells whose measurements cannot be confused,
// so a check can say WHICH of them reached the metric.
const std::vector<Point2D>& nodes() {
    static const std::vector<Point2D> n = {
        {0.0, 0.0}, {1.0, 0.0}, {0.5, std::sqrt(3.0) / 2.0},   // 0,1,2 equilateral
        {10.0, 0.0}, {14.0, 0.0}, {14.0, 1.0}, {10.0, 1.0},    // 3,4,5,6 4x1 quad
    };
    return n;
}

const std::vector<int> kEquilateral = {0, 1, 2};
const std::vector<int> kRectangle = {3, 4, 5, 6};

}  // namespace

int main() {
    // ── 1. A mesh of plain triangles: both counts agree, and the figure is the
    //      metric's ────────────────────────────────────────────────────────────
    {
        // The two halves of a unit square, which test_cell_shape.cpp derives as
        // sqrt(2) from the triangle's own edge lengths.
        const std::vector<Point2D> sq = {{0, 0}, {1, 0}, {1, 1}, {0, 1}};
        const HybridShapeReport r = measureHybridCellShapes({{0, 1, 2}, {0, 2, 3}}, sq);
        CHECK(r.offered == 2, "1. two three-cornered cells are two offered cells");
        CHECK(r.nonTriangles == 0, "1. ...and neither is on the non-triangle row");
        CHECK(r.shape.cells == 2, "1. ...and both were measured, so the two counts agree");
        CHECK_NEAR(r.shape.max, std::sqrt(2.0), 1e-15,
                   "1. ...and the figure is the triangle rule's, not a second "
                   "implementation of it");
    }

    // ── 2. ONLY ENTRIES WITH AT LEAST 3 CORNERS ARE OFFERED ──────────────────
    // An empty entry and a one-node entry are not cells either; the two-node case
    // gets its own check below because it is the one a real mesh contains.
    {
        const HybridShapeReport r = measureHybridCellShapes(
            {{}, {0}, {0, 1}, kEquilateral}, nodes());
        CHECK(r.offered == 1,
              "2. of four entries only the three-cornered one is offered — the "
              "floor is a rule about what a CELL is, not a guard against bad data");
        CHECK(r.nonTriangles == 0,
              "2. ...and the three short entries are not on the non-triangle row "
              "either: that row is a corner count the metric cannot handle, not "
              "an entry that is not a cell");
        CHECK(r.shape.cells == 1, "2. ...and exactly one cell was measured");
        CHECK_NEAR(r.shape.max, 1.0, 1e-15,
                   "2. ...the equilateral one, at the metric's floor");
    }

    // ── 3. A TWO-NODE VISUALISATION ENTRY IS NOT A CELL ───────────────────────
    // `addTaggedLoop` (a file-static in src/cli.cpp) records boundary segments
    // as two-node elements and
    // `Mesh::exportStarCD` skips them by this same test. A mesh made ONLY of them
    // offers nothing — the case that separates "not a cell" from "a cell I could
    // not measure", which reports the same three figures for a different reason.
    {
        const HybridShapeReport r = measureHybridCellShapes(
            {{0, 1}, {1, 2}, {2, 0}}, nodes());
        CHECK(r.offered == 0,
              "3. three two-node boundary segments offer NO cells, so the count "
              "beside the figures cannot be inflated by the visualisation entries");
        CHECK(r.nonTriangles == 0,
              "3. ...and none of them reaches the non-triangle row");
        CHECK(r.shape.cells == 0 && r.shape.median < 0.0,
              "3. ...and a mesh of nothing but segments reports not-measured");
    }

    // ── 4. A FOUR-CORNERED CELL IS COUNTED AND CARRIES NO FIGURE ──────────────
    // The Cartesian fallback's case: a quad handed to `cellShapeRatio` comes back
    // with a perfectly correct MIDLINE ratio under the name `tri_edge_ratio`,
    // which is the one thing the two metric names exist to prevent. The fixture
    // is a 4x1 rectangle beside an equilateral triangle precisely so the two
    // answers differ — a SQUARE would measure 1.0 either way and this check would
    // pass with the quad folded in.
    {
        const HybridShapeReport r = measureHybridCellShapes(
            {kEquilateral, kRectangle}, nodes());
        CHECK(r.offered == 2, "4. the quad IS offered — it is a cell, and counted");
        CHECK(r.nonTriangles == 1,
              "4. ...and it lands on the non-triangle row, so the banner says so "
              "rather than describing the mesh by a fraction of itself");
        CHECK(r.shape.cells == 1, "4. ...but only the triangle was measured");
        CHECK_NEAR(r.shape.max, 1.0, 1e-15,
                   "4. ...and the figure is the triangle's 1.0, NOT the "
                   "rectangle's midline ratio of 4.0 wearing this metric's name");
    }

    // ── 5. A CELL WHOSE IDS DO NOT RESOLVE IS OFFERED AND NOT MEASURED ────────
    // Both ways out of the table: past its end, and negative. Neither is a corner
    // count, so neither belongs on the non-triangle row.
    {
        const std::vector<int> past = {0, 1, static_cast<int>(nodes().size())};
        const std::vector<int> negative = {0, -1, 2};
        const HybridShapeReport r = measureHybridCellShapes(
            {kEquilateral, past, negative}, nodes());
        CHECK(r.offered == 3,
              "5. all three are three-cornered, so all three are offered");
        CHECK(r.nonTriangles == 0,
              "5. ...and an unresolved id is not a corner-count problem, so the "
              "non-triangle row stays empty");
        CHECK(r.shape.cells == 1,
              "5. ...but only the resolving cell was measured: an id past the end "
              "of the node table and a negative id are both unmeasurable");
        CHECK_NEAR(r.shape.max, 1.0, 1e-15,
                   "5. ...and the two dropped cells left no figure behind");
    }

    // ── 6. THE GAP BETWEEN THE TWO COUNTS HAS THREE WAYS IN ───────────────────
    // Which is why both counts are on the machine line and neither is inferred
    // from the other: one number could not tell these apart.
    {
        const std::vector<int> unresolved = {0, 1, 99};
        const std::vector<int> degenerate = {0, 0, 1};   // two coincident corners
        const HybridShapeReport r = measureHybridCellShapes(
            {kEquilateral, kRectangle, unresolved, degenerate}, nodes());
        CHECK(r.offered == 4, "6. four cells offered");
        CHECK(r.shape.cells == 1,
              "6. ...one measured: a corner count the metric is not defined for, "
              "an unresolved id and a degenerate cell are three separate ways to "
              "lose one");
        CHECK(r.nonTriangles == 1,
              "6. ...and only ONE of the three is a corner-count problem, so the "
              "non-triangle row never stands in for the whole gap");
    }

    // ── 7. AN EMPTY CELL SET REPORTS NEGATIVE FIGURES, NEVER 0.0 ─────────────
    {
        const HybridShapeReport r = measureHybridCellShapes({}, nodes());
        CHECK(r.offered == 0 && r.nonTriangles == 0,
              "7. nothing offered and nothing on the non-triangle row");
        CHECK(r.shape.cells == 0, "7. ...and `cells 0`");
        CHECK(r.shape.median < 0.0 && r.shape.p95 < 0.0 && r.shape.max < 0.0,
              "7. ...with all three figures NEGATIVE — on a metric whose floor is "
              "1.0 a 0.0 could only ever be an absent measurement wearing a number");
    }

    // ── 8. ...AND SO DOES A MESH WHOSE CELLS ALL EXIST AND NONE CAN BE MEASURED
    // The Cartesian fallback's own state, and a DIFFERENT INPUT from check 7's:
    // both report `cells 0` with three negative figures, which is why the surface
    // gate drives both through the binary rather than calling one the other's
    // control. Here the distinguishing evidence is `offered`, which check 7 has at
    // 0 and this one does not.
    {
        const HybridShapeReport r = measureHybridCellShapes(
            {kRectangle, kRectangle}, nodes());
        CHECK(r.offered == 2 && r.nonTriangles == 2,
              "8. two cells offered, both on the non-triangle row");
        CHECK(r.shape.cells == 0 &&
              r.shape.median < 0.0 && r.shape.p95 < 0.0 && r.shape.max < 0.0,
              "8. ...and the report is `not measured` with three negative figures "
              "— the same state as check 7 reached by a different input");
    }

    // ── 9. AN EMPTY NODE TABLE MAKES EVERY CELL UNRESOLVED, and does not crash ─
    // Total is a property of this module, not a hope: the surface gate's smallest
    // case leaves 0 nodes and 0 elements, and a mesh with elements but no nodes is
    // one step from it.
    {
        const HybridShapeReport r = measureHybridCellShapes(
            {kEquilateral, kEquilateral}, {});
        CHECK(r.offered == 2 && r.nonTriangles == 0,
              "9. both cells are three-cornered, so both are offered");
        CHECK(r.shape.cells == 0 && r.shape.max < 0.0,
              "9. ...and with no coordinates to resolve against, neither is "
              "measurable and no figure is reported");
    }

    return hybmesh::test::report("test_hybrid_quality");
}
