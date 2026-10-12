#ifndef MBQUALITY_HPP
#define MBQUALITY_HPP

#include "CellShape.hpp"
#include "MultiBlock.hpp"

#include <cstddef>
#include <string>
#include <vector>

// The multi-block mesh-quality instrument (issue #51).
//
// This is the RULER, not the thing being measured, and it is built before the
// thing being measured on purpose: zero inverted cells is one of only two binary
// pass conditions for the v1 acceptance gate, and the other three numbers are the
// baseline the later elliptic-smoothing increment is judged against. A gate whose
// instrument arrives last is a gate that gets negotiated down.
//
// It is its own module rather than more of `MultiBlock.cpp` for two reasons. It
// answers a different question — "is this mesh usable?" against "what does this
// document declare?" — and it is a pure function of a finished mesh, so a test
// can hand it a mesh nobody parsed (see check 6 of tests/cpp/test_mb_quality.cpp,
// a bow-tie quad built by hand). It lives in `hybmesh_pure`: measuring a mesh must
// not require the mesh container or gmsh.
//
// THREE MEASUREMENT DECISIONS, all load bearing:
//
// * INVERTED is counted over the cells that are EXPORTED — triangles normally,
//   quads when MB_SPLIT_QUADS is off — because those are the cells the solver
//   reads. The test is PER CORNER, not the cell's signed area: a bow-tie quad can
//   have a positive shoelace area while self-intersecting, and the obvious
//   area-based implementation calls it fine. For a triangle the per-corner rule
//   reduces to the signed area, so it is one rule for both cell kinds.
//
// * NON-ORTHOGONALITY is measured on the STRUCTURED grid cells (the (i,j) quads
//   of each block), as the deviation of each corner angle from 90 degrees, and
//   NOT on the split triangles. Three reasons, and the first is what the ticket
//   asks for: it is computed from the corner positions directly, so a block that
//   is strongly stretched but axis-aligned measures exactly zero, which no
//   size-or-edge-length proxy can report (the same trap the mesh size-field
//   ceiling report had to avoid, where cell edges run ~15% long on stretched
//   triangles). Second, it is the quantity elliptic smoothing moves, so it is
//   usable as that increment's baseline; measuring the triangles instead would let
//   the fixed diagonal — an artefact of the split that no smoother touches —
//   dominate the number, so a grid that got worse in the way that matters could
//   report an unchanged figure. Third, it is therefore independent of
//   MB_SPLIT_QUADS, so the quads-for-diagnosis mode and the shipped triangles
//   report the same grid quality. What it does NOT say is anything about the
//   shape of the split triangles themselves; a solver-facing skewness metric for
//   those is a different instrument and is not this one wearing another name.
//
// * CELL SHAPE is measured on the STRUCTURED cells too (issue #129), by the quad
//   rule of the pure `cellShapeRatio` next door, which both generation paths
//   share so that the arithmetic cannot drift. It follows non-orthogonality's
//   precedent for the same three reasons, stated where the fields are declared —
//   and it is the answer to what the sentence above leaves open: the shape of the
//   split triangles is NOT reported here under a quad's name. The HYBRID path
//   reports the shape of the cells IT exports, under its own name
//   (`tri_edge_ratio`, #130) — a different quantity on a different line, and the
//   two are never to be compared.
namespace hybmesh {

// One declared wall side of one filled block: what the DECLARATION asks the first
// cell height off it to be, and what the fill actually produced.
//
// "Requested" is the first interval of the edge running AWAY from this side — at
// this side's start corner (`requestedLo`) and at its end corner (`requestedHi`),
// which are two different edges and may legitimately differ. In between, the
// request is the same linear blend in the logical coordinate that the transfinite
// fill itself uses.
//
// WHAT THIS FIGURE IS, said plainly, because its name invites a stronger reading
// than the weaker of its two cases can support. It now has TWO cases, and which
// one a wall is in depends on the DOCUMENT, not on this header.
//
// * The perpendicular edge DECLARES a wall spacing (`wall_ends` / `ds_start` /
//   `ds_end`, issue #55). Then the request is an INDEPENDENT TARGET — a length
//   the topology asked for, resolved from `BL_INITIAL_THICKNESS` or from the
//   edge's own override — and this figure is a real comparison of the mesh
//   against the declaration. It is nonzero for two reasons worth telling apart:
//   interior distortion, and the FACETING of a curved geometry stored as a
//   polyline (0.08% on the shipped O-grid, 0.0007% on a 10x finer circle).
//
// * The perpendicular edge declares nothing. Then the request falls back to the
//   first interval the fill produced, which is DERIVED from the same spacing law
//   the fill reproduces — and the transfinite blend is exact on the boundary, so
//   at the side's two END COLUMNS the achieved height IS the requested one
//   identically, by construction. A rectangle therefore reports 0.00% as a
//   tautology, not as evidence that the instrument works; the discriminating
//   evidence is a block the blend distorts (a trapezoid measures 7.4%, a folded
//   dart 25.4%). Read it as "how far the interior drifted from what the two ends
//   declare", which is exactly the figure elliptic smoothing moves.
//
// #51 predicted that when the independent target arrived only the PUBLISHER in
// `buildMultiBlock` would change. It did: this struct and every reader of it are
// untouched, and the fallback above is what keeps the second case's older reading
// true for a topology that asks for no height.
//
// The height is a distance ALONG the grid line, not the perpendicular distance to
// the wall; on a non-orthogonal block the two differ by cos(non-orthogonality),
// which is why this number and the angle are always reported together.
struct MbWallHeight {
    std::string edgeId;              // the edge id the topology document declared
    std::string side;                // "south" | "east" | "north" | "west"
    double requestedLo = 0.0;
    double requestedHi = 0.0;
    double achievedMin = 0.0;
    double achievedMax = 0.0;
    // max |achieved - requested| / requested along the side, or NEGATIVE when the
    // request was not a positive length anywhere on it — see below.
    double worstRelError = -1.0;
};

// One block's structured-cell SHAPE, so the headline figure below has rows under
// it the way the wall figure has rows under its own (issue #129).
//
// It is per BLOCK and not per cell because a block is the unit the user declared:
// "the wake blocks are the stretched ones" is an answer they can act on, where a
// list of 4608 numbers is not. The block id is the one the topology document
// gave it, so the row names something the reader wrote down.
//
// `shape.cells` counts the STRUCTURED quads of this block, which is NOT the number
// of cells it exports — at the default `MB_SPLIT_QUADS 1` each of them leaves as
// two triangles. That difference is the figure's whole point and is visible on the
// machine-readable line: on a mesh every cell of which could be measured, `cells=`
// and `quad_midline_ratio_cells=` differ by exactly the factor two.
struct MbBlockShape {
    std::string blockId;
    ShapeStats shape;   // negative throughout when this block had nothing measurable
};

// HOW BIG A STEP THERE IS BETWEEN TWO CELLS THAT TOUCH (issue #174).
//
// The ratio of the larger structured quad's area to the smaller's, over every
// pair of structured quads that SHARE AN EDGE. 1.0 is no change at all; a pair at
// 10 means a solver crossing that face sees its control volume change tenfold in
// one step, which is where a gradient reconstruction loses its order.
//
// WHY A FIGURE OF ITS OWN, and this is the measurement that asked for it: on a
// twelve-block cylinder-in-channel the elliptic smoother took this ratio from
// 1.68 to 10.66 and put 400 faces over 2x where there had been none — while
// `maxNonOrthoDeg` moved 45.0 -> 53.4, `meanNonOrthoDeg` moved 4.88 -> 4.05, and
// every `structuredShape` figure came back BIT-IDENTICAL at every sweep count.
// Three figures that all looked the same or better on a mesh that had got
// materially worse. None of them can see this: non-orthogonality is an ANGLE and
// this is a SIZE, and the midline ratio is computed inside ONE cell and never
// looks at its neighbour.
//
// MEASURED ON THE STRUCTURED QUADS, for non-orthogonality's three reasons and one
// more that is specific here: the split halves every quad, and the two triangles
// of one quad do NOT have equal areas unless it is a parallelogram, so measuring
// the exported cells would report the SPLIT's own artefact as a size jump. It is
// therefore independent of `MB_SPLIT_QUADS`, like the other two.
//
// ADJACENCY IS BY SHARED NODE IDS, not by logical (i,j), which is what makes the
// figure see ACROSS a block boundary — the place a size jump is most likely and
// least visible. Welding is allocation rather than comparison (one node per
// declared corner, an edge's interior nodes once per declared edge), so two quads
// in different blocks that touch really do name the same two node ids, and there
// is no tolerance anywhere in this lookup for the same reason there is none in the
// welding.
//
// NO THRESHOLD AND NO COLOUR, like every figure beside it. What ratio is too big
// depends on the solver's reconstruction and on where in the mesh it sits; the
// case types one layer up are where a bar on it may live.
//
// `pairs` is NOT `cells` under another name and is deliberately not spelled that
// way: it counts PAIRS of quads, so on a mesh of N structured quads it is neither
// N nor a fixed multiple of it — an interior quad contributes four pairs and a
// corner quad two, each counted once from the edge they share.
struct MbAdjacentAreaRatio {
    size_t pairs = 0;     // adjacent structured-quad pairs actually measured
    double median = -1.0;
    double p95 = -1.0;
    double max = -1.0;
};

// EVERY MEASURED QUANTITY HERE IS NEGATIVE WHEN IT WAS NOT MEASURED, never 0.
//
// This is the one rule of the report and it is not a formality: 0.000 deg of
// non-orthogonality and "0.00% off the requested height" are both excellent
// results, so emitting them for a mesh nothing could be measured on turns "we do
// not know" into a positive false claim — the distinction `case_run_note` keeps
// between an unreadable convergence history and a genuine cold start, and the
// reason its unreadable case reports -1 rather than the 0 a cold start really
// prints. `nonOrthoSamples` says how many corners the angles came from, and it is
// 0 exactly when the two angle figures are negative.
struct MbQualityReport {
    size_t cells = 0;                // cells as exported (triangles, or quads)
    size_t invertedCells = 0;
    size_t nonOrthoSamples = 0;      // corners of structured cells actually measured
    double maxNonOrthoDeg = -1.0;
    double meanNonOrthoDeg = -1.0;
    // Only walls whose request WAS a positive length; a wall that could not be
    // measured is still listed, with its own `worstRelError` negative.
    std::vector<MbWallHeight> walls;
    double worstWallRelError = -1.0; // the worst measured wall, or negative if none

    // ── CELL SHAPE (issue #129) ─────────────────────────────────────────────
    // Measured on the STRUCTURED (i,j) quads, by `cellShapeRatio`'s quad rule,
    // for the same three reasons non-orthogonality is measured there: it is the
    // cell the DOCUMENT declares and the one the wall spacing and the count
    // propagation are about; a square reads 1.0 rather than the 1.414 the split
    // triangles would report, so the number can be read against "is this 1:1?";
    // and it is therefore independent of `MB_SPLIT_QUADS`, so turning the split
    // off to diagnose a mesh does not change the number being diagnosed.
    //
    // NO THRESHOLD AND NO COLOUR belongs to this figure anywhere downstream. The
    // shipped O-grid's max is ~32.8 and that is arithmetic, not a defect: the
    // azimuthal spacing divided by the `BL_INITIAL_THICKNESS` the user asked for.
    // A figure the tool colours red on a correct mesh is a figure users learn to
    // ignore.
    ShapeStats structuredShape;            // over every block's structured quads
    std::vector<MbBlockShape> blockShapes; // one row per block, in declaration order

    // ── THE WALL BAND (issue #144) ──────────────────────────────────────────
    // The same three figures over the quads the WALL CLUSTERING squeezed and
    // over every other structured quad, BESIDE `structuredShape` and never
    // instead of it. The shipped O-grid is why: its whole-mesh p95 is 23.662
    // against a median of 1.846, so that percentile describes the wall band and
    // not the mesh a user is asking after — the failure #128's problem statement
    // attributed to the max and the mean, reaching this path too.
    //
    // WHAT A WALL-BAND CELL IS, and it is a property of the GRID, not of a
    // distance: walking outward from a side the document declares a `wall`, a
    // cell is in the band while its extent ACROSS that side is shorter than its
    // extent ALONG it, and the walk stops at the first cell where it is not. That
    // is the definition of "the clustering squeezed this cell toward the wall",
    // stated without a cut-off — no radius, no layer count, no multiple of the
    // first-cell height, so nothing here is a knob that decides the figures. It
    // uses `quadExtents` for that comparison and not `cellShapeRatio`, whose ratio
    // is orientation-free and therefore cannot say WHICH direction is the short
    // one.
    //
    // ONE ROW OFF THE WALL IS NOT THE BAND, and the measurement is what settles
    // it: on the shipped O-grid the wall row measures 32.77, the next 28.49, and
    // the figures fall smoothly to 1.01 twenty-four rows out. A band of one row
    // leaves the bulk p95 at 20.05 — still a wall figure, so the split would have
    // changed nothing about the number it exists to fix. The walk measured 24
    // rows, and the bulk p95 is 1.878.
    //
    // THE WALK IS PER STATION ALONG THE SIDE, not per row, so a wall whose
    // clustering varies along its own length reports a band that varies with it.
    // On the shipped cases every station agrees, which is why the paragraph above
    // can speak of rows at all.
    //
    // A BLOCK WITH NO DECLARED WALL SIDE CONTRIBUTES TO `structuredBulkShape`
    // ONLY, by construction rather than by a rule written twice: it has no side
    // to walk from, so nothing marks any of its cells. The two sets PARTITION the
    // structured quads — `structuredShape.cells == structuredLayerShape.cells +
    // structuredBulkShape.cells` — because each cell's ratio is pushed into the
    // whole-mesh set and into exactly one of these, and an unmeasurable cell is
    // dropped from all three by the same rule in `reduceCellShapes`.
    //
    // BOTH ARE MEASURED ON THE STRUCTURED QUADS, so both are independent of
    // `MB_SPLIT_QUADS` for the reason `structuredShape` already is.
    //
    // AN EMPTY BAND IS `cells 0` WITH NEGATIVE FIGURES, and here that is an
    // ORDINARY case: a uniform rectangle (the shipped square and cavity) clusters
    // nothing at all, so no cell is thinner across a wall than along it and the
    // bulk half is the whole mesh.
    ShapeStats structuredLayerShape;       // the wall-clustered band
    ShapeStats structuredBulkShape;        // every other structured quad

    // ── THE SIZE JUMP (issue #174) ──────────────────────────────────────────
    // See MbAdjacentAreaRatio above for what it is, what it sees that the three
    // figures above cannot, and why it is measured where it is. Its three
    // statistics come from `reduceCellShapes`, the same reduction with the same
    // two percentile rules the shape figures use, so there is still exactly one
    // definition of "median" and "p95" in this report.
    MbAdjacentAreaRatio adjacentAreaRatio;
};

// Measure a finished multi-block mesh. Pure, total, and never throws: an empty or
// half-built result is measured as what it is rather than refused.
MbQualityReport measureMbQuality(const MbResult& mesh);

}  // namespace hybmesh

#endif  // MBQUALITY_HPP
