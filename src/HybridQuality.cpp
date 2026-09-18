#include "HybridQuality.hpp"

namespace hybmesh {

HybridShapeReport measureHybridCellShapes(
    const std::vector<std::vector<int>>& cellNodeIds,
    const std::vector<Point2D>& nodes) {
    HybridShapeReport rep;
    std::vector<std::vector<Point2D>> tris;
    tris.reserve(cellNodeIds.size());
    for (const std::vector<int>& ids : cellNodeIds) {
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
        tris.push_back(resolved ? corners : std::vector<Point2D>());
    }
    rep.shape = measureCellShapes(tris);
    return rep;
}

}  // namespace hybmesh
