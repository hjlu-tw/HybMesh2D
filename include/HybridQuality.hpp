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
namespace hybmesh {

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
    ShapeStats shape;         // over the cells that could be measured
};

// Collect the exported cells worth measuring and reduce them, in one pass.
//
// `cellNodeIds` is one entry per exported element, holding its node ids in order
// around the cell; `nodes` is the coordinate for each id. An entry with fewer than
// 3 ids is NOT A CELL and is not offered — the two-node entries are the
// visualisation line segments `Mesh::addTaggedLoop` records, which
// `Mesh::exportStarCD` skips by the same test.
//
// A CELL WHOSE IDS DO NOT ALL RESOLVE IS UNMEASURABLE, said here rather than left
// to the metric. Passing on the corners that did resolve would reach
// `cellShapeRatio` as a SHORTER cell and come back with an ordinary ratio for a
// cell nobody could measure; such a cell is counted as offered and dropped from
// the statistics. Same rule, same reason, as the quad case in `measureMbQuality`.
//
// Total, and never throws: an out-of-range or negative id is the case above, and
// an empty input reduces to `cells 0` with three NEGATIVE figures rather than
// zeros — on a metric whose floor is 1.0, a 0.0 could only ever be an absent
// measurement wearing a number.
HybridShapeReport measureHybridCellShapes(
    const std::vector<std::vector<int>>& cellNodeIds,
    const std::vector<Point2D>& nodes);

}  // namespace hybmesh

#endif  // HYBRIDQUALITY_HPP
