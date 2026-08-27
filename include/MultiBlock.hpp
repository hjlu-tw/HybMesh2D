#ifndef MULTIBLOCK_HPP
#define MULTIBLOCK_HPP

#include "GeomUtils.hpp"

#include <string>
#include <vector>

// The topology-driven multi-block structured path (MESH_MODE 1), as ONE pure
// entry point.
//
// This is the only seam this feature gets, and the shape is deliberate. JSON
// parsing sits INSIDE it, so a test can hand `buildMultiBlock` a topology
// document as text and assert on what comes back: schema errors, count
// resolution, node positions, the diagonal split and the resolved boundary
// conditions are all EXTERNAL behaviour of this one function. A separate
// "parse the document" entry point would have made half of that internal.
//
// The adapter that writes an `MbResult` into the mesh container deliberately
// gets NO seam of its own (it lives in src/cli.cpp). It is a loop with no
// decisions in it — every boundary edge comes back already resolved — and
// giving it a seam would concede that it has logic worth testing separately.
//
// Everything here is Gmsh-free and Mesh-free by construction: the module lives
// in `hybmesh_pure`, whose tests link that library and NOTHING else, so the
// moment this file reaches for `Mesh` or gmsh those executables stop linking.
// See tools/PreProcessor/tests/test_cpp_pure_layer.py.
namespace hybmesh {

// One loaded geometry, as this seam sees it.
//
// v0 (issue #50) binds NO geometry: every topology corner is a free coordinate
// and every boundary condition comes from the config default. The parameter is
// here anyway because the seam is declared once — issue #52 fills these in for
// arc-length corner attachment and per-segment BC labels, and it should not
// have to change the signature to do it. A topology document that DOES declare
// a geometry binding is refused by name rather than silently ignored.
// Deliberately only what the CALLER fills today. The per-point source segment
// and BC label a geometry sidecar carries are not declared here yet: a field
// nothing writes reads as a field somebody forgot to write, and the ticket that
// needs them is the one that should add them.
struct MbGeometry {
    std::string file;
    std::vector<Point2D> points;
};

// The resolved parameters this path reads. Deliberately a handful of values
// rather than a `Config&`: Config.hpp is a header-only .dat parser and pulling
// it in would tie the decision layer to the file format it is a decision about.
struct MbParams {
    // The BC every boundary edge carries in v0. Comes from BC_GEOM.
    std::string defaultBc = "wall";
    // Split every quad into two triangles before the mesh leaves this seam.
    // ON by default: the solver's incenter reconstruction is undefined on quad
    // cells, so triangles are the point of this whole path. Switchable off so
    // the quad mesh can be inspected when a topology is being diagnosed.
    bool splitQuads = true;
};

// One filled block, with its LOGICAL i/j indexing retained.
//
// Retained rather than flattened because the diagonal rules depend on it: the
// alternating split is a function of (i + j) parity, and issue #54's randomized
// rule hashes (block, i, j, seed). Flattening before the split would destroy
// the only information the split reads.
struct MbBlock {
    std::string id;
    int ni = 0;                  // node count along i
    int nj = 0;                  // node count along j
    std::vector<int> nodeIds;    // ni*nj global node ids; index = j * ni + i

    int nodeAt(int i, int j) const { return nodeIds[static_cast<size_t>(j) * ni + i]; }
};

// One cell, already split (3 node ids) or still a quad (4), wound CCW.
struct MbCell {
    std::vector<int> nodeIds;
    // Which block this cell came from. Carried because flattening is otherwise
    // one-way: once the cells are a flat list there is nothing left to ask. The
    // split rules are functions of it (issue #54's randomized diagonal hashes
    // block, i, j and a seed), and issue #48 wants it as a VTK cell field for
    // debugging — which nothing writes yet, since #50 changes no exporter.
    int block = -1;
};

// One boundary edge, ALREADY RESOLVED. The adapter records it through the
// mesh's existing paired write and makes no classification decision — position
// based classification is not used in this path, because the declaration
// already contains the answer and re-deriving it by proximity is how a curved
// inlet came to export partly as wall.
struct MbBoundaryEdge {
    int v1 = -1, v2 = -1;
    std::string bc;
    int geomId = -1;             // -1 in v0: nothing binds geometry yet (#52)
    int segId = -1;
};

struct MbResult {
    // false -> `error` names what is wrong and NOTHING was produced. The caller
    // turns this into EXIT_ERR_TOPOLOGY and exports nothing.
    bool ok = false;
    std::string error;
    // Warnings as DATA: the caller decides how to say them, and a test can
    // assert on the list without capturing a log.
    std::vector<std::string> warnings;

    std::vector<Point2D> nodes;
    std::vector<MbBlock> blocks;
    std::vector<MbCell> cells;
    std::vector<MbBoundaryEdge> boundaryEdges;
};

// Parse `topologyJson`, resolve it against `geoms` and `params`, fill every
// block with structured quads, split them and return the flattened result.
// Never throws: a malformed document comes back as `ok == false` with `error`
// naming what is wrong and where.
MbResult buildMultiBlock(const std::string& topologyJson,
                         const std::vector<MbGeometry>& geoms,
                         const MbParams& params);

}  // namespace hybmesh

#endif  // MULTIBLOCK_HPP
