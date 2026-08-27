#ifndef MBQUALITY_HPP
#define MBQUALITY_HPP

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
// TWO MEASUREMENT DECISIONS, both load bearing:
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
// than it can support in this release. Nothing in a v0 topology declares a
// wall-normal first-cell height independently of the edge distribution, so the
// request is DERIVED from the same spacing law the fill reproduces — and the
// transfinite blend is exact on the boundary, so at the side's two END COLUMNS the
// achieved height IS the requested one identically, by construction. A rectangle
// therefore reports 0.00% as a tautology, not as evidence that the instrument
// works; the discriminating evidence is a block the blend distorts (a trapezoid
// measures 7.4%, a folded dart 25.4%). Read it as "how far the interior drifted
// from what the two ends declare", which is exactly the figure elliptic smoothing
// moves. The independent target — a wall spacing asked for by
// `BL_INITIAL_THICKNESS` and friends rather than by an edge count — arrives with
// the wall-spacing resolution work, and when it does only the PUBLISHER in
// `buildMultiBlock` changes; this struct and every reader of it stay as they are.
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
};

// Measure a finished multi-block mesh. Pure, total, and never throws: an empty or
// half-built result is measured as what it is rather than refused.
MbQualityReport measureMbQuality(const MbResult& mesh);

}  // namespace hybmesh

#endif  // MBQUALITY_HPP
