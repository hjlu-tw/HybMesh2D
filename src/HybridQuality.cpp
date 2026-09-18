#include "HybridQuality.hpp"

namespace hybmesh {

HybridShapeReport measureHybridCellShapes(
    const std::vector<HybridCell>& cells,
    const std::vector<Point2D>& nodes) {
    HybridShapeReport rep;
    std::vector<std::vector<Point2D>> tris;      // every measurable cell
    std::vector<std::vector<Point2D>> layer;     // those the boundary layer emitted
    std::vector<std::vector<Point2D>> bulk;      // the rest
    tris.reserve(cells.size());
    for (const HybridCell& cell : cells) {
        const std::vector<int>& ids = cell.nodeIds;
        // Not a cell. The header says what the two-node entries are and who else
        // skips them by this same test; one home for that, not two.
        if (ids.size() < 3) continue;
        ++rep.offered;
        if (ids.size() != 3) { ++rep.nonTriangles; continue; }
        std::vector<Point2D> corners;
        corners.reserve(3);
        bool resolved = true;
        for (int id : ids) {
            if (id < 0 || static_cast<size_t>(id) >= nodes.size()) {
                resolved = false;
                break;
            }
            corners.push_back(nodes[static_cast<size_t>(id)]);
        }
        // An unresolved cell reaches the reducer as an EMPTY corner list, which is
        // the "could not measure this one" signal `reduceCellShapes` drops —
        // never as the corners that happened to resolve, which would come back as
        // an ordinary ratio for a cell nobody could measure. See the header.
        std::vector<Point2D> entry = resolved ? corners : std::vector<Point2D>();
        // The SAME entry into the whole-mesh set and into its half, so the two
        // halves partition what the whole set measured rather than re-deciding it.
        (cell.fromBoundaryLayer ? layer : bulk).push_back(entry);
        tris.push_back(std::move(entry));
    }
    rep.shape = measureCellShapes(tris);
    rep.layer = measureCellShapes(layer);
    rep.bulk = measureCellShapes(bulk);
    return rep;
}

}  // namespace hybmesh
