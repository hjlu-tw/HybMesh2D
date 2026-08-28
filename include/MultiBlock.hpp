#ifndef MULTIBLOCK_HPP
#define MULTIBLOCK_HPP

#include "GeomUtils.hpp"

#include <map>
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

// One loaded geometry, as this seam sees it: the resampled polyline plus the two
// facts its `.meta` sidecar carries about where one segment ends and the next
// begins, and what boundary condition each carries.
//
// A topology attaches to a geometry BY NAME (`file`, matched exactly or by
// basename) and never by position in this vector — for the reason the ticket
// gives about point indices one level down: a list that can be reordered is a
// binding that can silently relocate.
struct MbGeometry {
    std::string file;
    std::vector<Point2D> points;
    // Parallel to `points`: which source segment each point belongs to, from the
    // sidecar's POINTS block. EMPTY when the geometry has no readable sidecar,
    // and a document that attaches to such a geometry is refused by name rather
    // than falling back to "the whole polyline is segment 0" — a corner that
    // lands somewhere plausible on the wrong segment is the slightly-wrong-mesh-
    // with-no-error outcome this whole path exists to avoid.
    std::vector<int> segId;
    // Indices in `points` at which a new disconnected PIECE starts, from the
    // sidecar's NPIECES block. Read for one reason, and it is not cosmetic: a
    // segment's arc length runs from its own first point to the first point of
    // the NEXT segment (the sidecar assigns a shared joint to the LATER segment,
    // so a segment's own run stops one point short of where it ends). Across a
    // piece break there is no next point to reach for, and taking one anyway
    // would stretch the segment across the gap between two disjoint pieces.
    std::vector<size_t> pieceBreaks;
    // Did the loader weld this polyline into a closed loop? It drops the trailing
    // duplicate of the first point when it does, so the LAST segment's end is not
    // one past the end of `points` but index 0 — and without knowing that, t = 1 on
    // the last segment of a closed body lands one resampling interval short of the
    // seam, which is the very drift arc length is used to avoid.
    bool closed = false;
    // seg id -> the per-segment boundary condition LABEL the sidecar carries.
    //
    // A LABEL, not a physical BC type: the GUI groups segments under a label and
    // maps label -> type separately (the sidecar's GROUP_BC trailer), and the
    // exporter resolves it through `Config::resolveGroupBc`. Resolving it here
    // would put a second resolver in the chain, which is how the two came to
    // disagree the last time. A segment with no label falls back to
    // `MbParams::defaultBc`.
    std::map<int, std::string> segBc;
};

// The resolved parameters this path reads. Deliberately a handful of values
// rather than a `Config&`: Config.hpp is a header-only .dat parser and pulling
// it in would tie the decision layer to the file format it is a decision about.
struct MbParams {
    // The FALLBACK boundary condition, from BC_GEOM. An edge that declares a
    // binding takes its source segment's own label instead; this is what an
    // unbound edge — or a bound one whose segment carries no label — gets.
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
    // The BC LABEL this edge carries: the bound segment's own label, else
    // `MbParams::defaultBc`. Resolved to a physical type by the exporter.
    std::string bc;
    // The SOURCE SEGMENT this edge lies on, as (index into `geoms`, sidecar seg
    // id). Both stay -1 for an edge that declares no binding — which is not a
    // failure but the ordinary case for a block face in open fluid, and is what
    // makes the pre-binding topologies mesh unchanged.
    int geomId = -1;
    int segId = -1;
};

// A block's four sides, in the [south, east, north, west] order the topology
// document declares them and every check in this module is written against.
enum MbSide { MB_SOUTH = 0, MB_EAST = 1, MB_NORTH = 2, MB_WEST = 3 };

// WHERE a side sits in the block's logical grid. This is the [south, east,
// north, west] convention as DATA, in one place, because it was on its way to
// being encoded three times: once to pick the perpendicular edge whose spacing
// law a wall's first-cell height is asked of (src/MultiBlock.cpp), once to walk
// that side and step one grid line inward (src/MbQuality.cpp), and once to name
// it in a report. Two of those were `switch (side)` cascades over the same four
// values, which is the shape that lets one of them disagree with the others.
//
// The two facts are enough to derive all three: south and north run along i and
// the other two along j, and north and east sit at the transverse index MAXIMUM.
// So the perpendicular edges are (alongI ? west/east : south/north), read from
// (atFarEnd ? the far end : the near end).
struct MbSideAxis {
    const char* name;   // "south" | "east" | "north" | "west"
    bool alongI;        // the side runs along i (south, north) rather than along j
    bool atFarEnd;      // it sits at the transverse index maximum (north, east)
};

inline MbSideAxis mbSideAxis(MbSide s) {
    switch (s) {
        case MB_EAST:  return {"east",  false, true};
        case MB_NORTH: return {"north", true,  true};
        case MB_WEST:  return {"west",  false, false};
        case MB_SOUTH: break;
    }
    return {"south", true, false};
}

// One side of one block that was declared kind "wall", carrying the first-cell
// height the DECLARATION asks for off it.
//
// It is published here rather than measured downstream because only the seam
// knows the declaration: the request comes from the spacing law of the edge
// running away from this side, and by the time the block is a grid of node
// positions that law is gone. `MbQuality.hpp` then measures what the fill
// achieved against it.
//
// Every boundary edge is kind "wall" (interface and cut are refused by name), so
// all four sides of the one block are reported. Note what did NOT change this:
// boundary conditions now DO come from the declaration, and a side may carry a
// segment labelled "inlet" — but that is the flow condition, not the answer to
// "is this a viscous surface whose first cell height matters". The gate stays
// `kind`, which is the declaration's own word for it; when a kind distinguishes
// the two, this list gets shorter and nothing that reads it has to change.
struct MbWallSpec {
    int block = 0;                   // index into MbResult::blocks
    MbSide side = MB_SOUTH;
    std::string edgeId;
    double requestedLo = 0.0;        // first interval off this side at its START corner
    double requestedHi = 0.0;        // ... and at its END corner
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
    std::vector<MbWallSpec> wallSpecs;
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
