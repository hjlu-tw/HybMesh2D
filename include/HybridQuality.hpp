#ifndef HYBRIDQUALITY_HPP
#define HYBRIDQUALITY_HPP

#include "CellShape.hpp"

#include <cstddef>
#include <vector>

// WHICH CELLS THE HYBRID PATH OFFERS TO THE SHAPE METRIC, and what the two counts
// beside the figures mean (issue #141; the rule and the figures are #130's).
//
// This is the multi-block path's `measureMbQuality` at the same level, for the
// other generation path: `CellShape.hpp` next door answers "how badly shaped is
// THIS cell" from corner coordinates alone, and something has to decide which
// cells of a finished mesh become those corner lists. On the multi-block path
// that decision is "the structured (i,j) quads"; here it is "the exported cells
// with three corners", and it has three separate rules in it — the corner-count
// floor, the corner-count ceiling and the unresolved id — each of which can be
// wrong on its own.
//
// It lives HERE rather than in `src/cli.cpp`, where #130 first wrote it, for the
// reason the pure layer exists at all: deciding which cells are measurable must
// not require the mesh container or gmsh, and while it sat in a `static` function
// inside the CLI translation unit its only cover was the surface gate driving the
// whole binary. It takes the mesh as IDS AND COORDINATES rather than as a `Mesh&`
// — that is what keeps `tests/cpp/test_hybrid_quality.cpp` linking `hybmesh_pure`
// alone, and that executable failing to link is the signal the decision has grown
// a dependency on the container. What stays in the CLI is the half that is about
// output rather than measurement: the banner rows, the machine-readable line and
// the sidecar hand-off.
//
// ONLY THREE-CORNERED CELLS ARE OFFERED, and that is a reachable case rather than
// a defensive habit: with no geometry, no seed and no domain file the hybrid path
// builds a CARTESIAN QUAD fallback (`Mesh::generateCartesianMesh`), so "this path
// exports no quads" is true of every case that meshes a geometry and false of that
// one. A quad handed to `cellShapeRatio` comes back as a MIDLINE ratio — a correct
// number under the name `tri_edge_ratio`, which is the one thing the two metric
// names exist to prevent. Such a cell is left out of the figure and COUNTED, so
// the report says so rather than quietly describing a mesh by a fraction of itself.
//
// AND SINCE #143 IT SPLITS WHAT IT MEASURES IN TWO. The whole-mesh p95 on the
// shipped NACA case is 52.186 against a median of 1.158: more than 5% of its 15233
// triangles are boundary-layer cells, so that percentile describes the LAYER and
// not the mesh the user is asking about — the very failure #128's problem statement
// attributed to the max and the mean. The report therefore carries the same three
// figures over the cells the boundary layer emitted and over the rest, BESIDE the
// whole-mesh set rather than instead of it.
//
// THE SPLIT COMES FROM THE GENERATOR'S OWN RECORD, NOT FROM GEOMETRY. Each cell
// says whether `BoundaryLayer::generate` emitted it (`Element::fromBoundaryLayer`,
// set at the four `addBoundaryLayerElement` call sites in src/BoundaryLayer.cpp);
// nothing here measures a distance to a wall or guesses from a cell's shape. A
// distance test would have to pick a cut-off, and the cut-off would then decide
// the figures — which is how a measurement becomes a knob. It also could not tell
// a fan cell three layers out from a far-field triangle beside it, and both are
// cases the shipped NACA mesh has.
//
// AN EMPTY SET IS `cells 0` WITH NEGATIVE FIGURES, and on this path that is an
// ORDINARY case rather than an error: a geometry meshed through `-geom_nobl` grows
// no layer at all, so its layer set is empty and its bulk set is the whole mesh.
// The reporter prints `not measured` for such a set; it never prints 0.0, which on
// a metric whose floor is 1.0 could only ever be an absent measurement wearing a
// number.
namespace hybmesh {

// One exported element as this module takes it: its node ids in order around the
// cell, and whether the boundary layer emitted it.
//
// ONE STRUCT RATHER THAN TWO PARALLEL ARRAYS, and that is the decision: a
// `std::vector<bool>` beside the id lists could arrive shorter than them, and
// whatever this module then did with the unflagged tail — treat it as bulk, refuse
// the call — would be a rule nobody asked for, silently deciding which set some
// cells land in. Paired in the type, a cell cannot lose its mark on the way here.
struct HybridCell {
    std::vector<int> nodeIds;
    bool fromBoundaryLayer = false;
};

// What was offered to the metric, and what came back.
//
// THE TWO COUNTS ARE BOTH REPORTED AND NEITHER IS INFERRED FROM THE OTHER.
// `offered` is the entries with at least 3 corners; `shape.cells` is the ones that
// were actually MEASURED. The gap between them has three ways in — a corner count
// the metric is not defined for (counted separately as `nonTriangles`), a cell
// whose node ids do not all resolve, and a degenerate cell the metric refuses —
// so a reader who had only one of the counts could not tell which happened.
//
// `offered` is NOT "what the exporters write", which was this count's first name
// in `src/cli.cpp` and is over-claimed by one exporter: `Mesh::exportStarCD` does
// skip the shorter entries (and drops degenerates and duplicates besides), but
// `Mesh::exportVTK` writes EVERY element, so on the shipped demo it emits 15237
// where this counts 15233. A count is the thing it counts.
struct HybridShapeReport {
    size_t offered = 0;       // entries with >= 3 corners
    size_t nonTriangles = 0;  // of those, the ones this metric is not defined for
    ShapeStats shape;         // over every cell that could be measured
    ShapeStats layer;         // over those the boundary layer emitted
    ShapeStats bulk;          // over the rest
};

// Collect the exported cells worth measuring, then reduce them.
//
// `cells` is one entry per exported element, holding its node ids in order around
// the cell and whether the boundary layer emitted it; `nodes` is the coordinate
// for each id. An entry with fewer than 3 ids is NOT A CELL and is not offered —
// the two-node entries are the visualisation line segments `addTaggedLoop` (a
// file-static in src/cli.cpp) records, which `Mesh::exportStarCD` skips by the
// same test.
//
// A CELL WHOSE IDS DO NOT ALL RESOLVE IS UNMEASURABLE, said here rather than left
// to the metric. Passing on the corners that did resolve would reach
// `cellShapeRatio` as a SHORTER cell and come back with an ordinary ratio for a
// cell nobody could measure; such a cell is counted as offered and dropped from
// the statistics. Same rule, same reason, as the quad case in `measureMbQuality`.
//
// THE THREE SETS ARE THREE REDUCTIONS OF ONE COLLECTION, not three collections.
// A cell is offered, counted and resolved exactly once, and the corner list that
// results is handed to `measureCellShapes` in the whole-mesh set AND in whichever
// of the two halves its mark puts it — so `shape.cells == layer.cells +
// bulk.cells` by construction, and no rule about which cells are measurable can
// hold in one set and not in another. The per-cell ratio is computed twice (once
// in the whole-mesh pass, once in its half's) rather than computed once and
// partitioned, because the alternative is this module reducing the metric itself
// and `measureCellShapes` losing its only production caller.
//
// Total, and never throws: an out-of-range or negative id is the case above, and
// an empty input — or an empty half — reduces to `cells 0` with three NEGATIVE
// figures rather than zeros; on a metric whose floor is 1.0, a 0.0 could only ever
// be an absent measurement wearing a number.
HybridShapeReport measureHybridCellShapes(
    const std::vector<HybridCell>& cells,
    const std::vector<Point2D>& nodes);

}  // namespace hybmesh

#endif  // HYBRIDQUALITY_HPP
