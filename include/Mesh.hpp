#ifndef MESH_HPP
#define MESH_HPP

#include "GeomUtils.hpp"
#include "Config.hpp"
#include "Curve.hpp"
#include <vector>
#include <string>
#include <map>
#include <optional>
#include <utility>

enum class NodeType {
    Boundary,
    BoundaryLayer,
    Interior
};

struct Node {
    Point2D pos;
    NodeType type;
    int id;
    int geomId = -1; // -1 for domain/interior, >=0 for specific geometries
    bool isFrozen = false;

    // Phase 1: provenance carried from the preprocessor's metadata sidecar.
    // Defaults keep nodes without metadata (domain box, BL, interior) inert.
    int segId = -1;        // source segment id, -1 if unknown
    bool isCorner = false; // pinned structural vertex (sharp corner / shape vertex)
    bool skipBL = false;   // per-segment BL disabled on this node -> grow no layer here
    std::string bcTag;     // per-segment boundary condition, empty -> use config default

    // Phase 2: local curve model of the source segment, so BL growth can query
    // an analytic/spline tangent & curvature instead of a one-sided difference.
    CurveKind curveKind = CurveKind::Polyline;
};

struct Edge {
    int v1, v2;
    // Boundary condition tag for a domain / far-field boundary edge (a rectangle
    // side or a custom polygon edge). Empty -> not a tagged domain edge; geometry
    // surface edges instead carry their BC via Node::bcTag. The exporters classify
    // boundary edges by this attached tag rather than by domain proximity, which is
    // what lets arbitrary (non-rectangular) domains keep correct per-edge BCs.
    std::string bcTag;
    // Source-segment key (encoded geomId+segId, see Mesh::makeSegKey). Lets the
    // STAR-CD/CGNS exporters give each distinct source segment its OWN patch id
    // (segm_no) even when several segments resolve to the same BC-type name, so the
    // solver BC table can address them individually. -1 -> group by name instead.
    long long segKey = -1;
};

struct Element {
    std::vector<int> nodeIds;
    // MESH_MODE 1 only: which declared block this cell was filled from, as the
    // INDEX into MbResult::blocks (never the block's declared `id` string — the
    // randomized split rule hashes that one, and MultiBlock.hpp says why the two
    // must not be conflated). Written to the VTK as a cell field so a mesh under
    // inspection can say which declaration produced a bad corner; issue #106.
    //
    // OPTIONAL, and that is the decision: the hybrid path has no blocks, so a
    // defaulted 0 would claim every one of its cells came from block 0, and a -1
    // sentinel would be a field every reader has to know to ignore. Absent means
    // absent, and the exporter writes no section at all.
    std::optional<int> blockId;

    // WHETHER THE BOUNDARY LAYER EMITTED THIS CELL, recorded where it is emitted
    // (issue #143, parent #128). The hybrid path's report separates the cells the
    // BL grew from the rest of the mesh, so that a percentile describes the mesh
    // the user is asking about: on the shipped NACA case more than 5% of the
    // exported triangles are BL cells, which makes the whole-mesh p95 a BL figure
    // and leaves "what shape is the rest of my mesh" answerable from the median
    // alone.
    //
    // A PLAIN `bool`, NOT AN `optional`, and the asymmetry with `blockId` above is
    // the point: absent is not a third state here. Every element of a hybrid mesh
    // either came out of `BoundaryLayer::generate` or did not, and the default
    // `false` is the true answer for every other producer (the far-field
    // triangulation, the Cartesian fallback, the visualisation loops, and every
    // multi-block cell). It is NOT exported to any mesh file — it exists to be
    // read by `printHybridQuality` while the mesh is still in memory.
    bool fromBoundaryLayer = false;
};

// Refinement seed (Pointwise-like source): a geometry used only to drive a local
// minimum mesh size in the far-field triangulation. Never grown into a boundary
// layer nor treated as a domain boundary. In 'embed' mode the mesh is forced to
// conform to the seed curve (gmsh embed); otherwise it is a pure sizing source.
struct SeedGeom {
    std::vector<Point2D> points;
    bool closed = false;
    double size = -1.0;    // target min size at the seed (<0 -> resolved from config)
    double radius = -1.0;  // influence radius     (<0 -> resolved from config)
    bool embed = false;    // true: conform (embed); false: sizing source only
};

class Mesh {
public:
    std::vector<Node> nodes;
    std::vector<Edge> edges;
    std::vector<Element> elements;

    // What one boundary edge was recorded as carrying: the BC name, and the source
    // segment it came from. `bc` empty -> nothing was recorded for that edge.
    struct EdgeBc {
        std::string bc;
        long long segKey = -1;
        explicit operator bool() const { return !bc.empty(); }
    };

    // Record what one boundary edge carries, keyed on the sorted (v1,v2) node pair.
    //
    // A boundary edge is a per-EDGE BC: it belongs to exactly one surface segment —
    // the segment of its starting point (the same convention addTaggedLoop uses for
    // far-field / no-BL edges), which is why the whole source `Node` is passed
    // rather than a tag. BL-grown surfaces do not add their wall edges to `edges`,
    // so this is what carries their per-edge BC to the exporter, letting it tag each
    // wall edge directly (including the edge that ends at a segment junction, whose
    // two endpoints carry different segment tags) instead of guessing from endpoint
    // agreement.
    //
    // The BC and the segment key are written TOGETHER and can only be read together
    // (see boundaryEdgeInfo). They used to be two public parallel maps that every
    // caller keyed, wrote and looked up by hand, so "wrote the BC, forgot the segment
    // key" was a defect the interface could not prevent — and a boundary edge that
    // reaches the exporter with only half its identity is exported as the wall
    // default, which reads as a converged solve of the wrong problem.
    //
    // `overwrite == false` refuses to replace an already-recorded non-empty BC,
    // which is what a case-1 slide column needs: it re-discretizes a stretch of
    // no-BL wall and must not restamp a real surface edge it happens to touch.
    // Returns whether anything was recorded (false for an untagged source node, or
    // for a refused overwrite).
    bool recordBoundaryEdge(int v1, int v2, const Node& src, bool overwrite = true);

    // What was recorded for one boundary edge; `bc` empty if nothing was.
    EdgeBc boundaryEdgeInfo(int v1, int v2) const;

    // Encode a (geomId, segId) pair into a single comparable key that uniquely
    // identifies one source segment. -1 when either component is unknown (domain
    // box / BL / interior nodes), which makes the exporter fall back to name-based
    // grouping for that edge.
    static long long makeSegKey(int geomId, int segId) {
        if (geomId < 0 || segId < 0) return -1;
        return static_cast<long long>(geomId) * 1000000LL + segId;
    }

    void addNode(Point2D p, NodeType type = NodeType::Interior);
    void addEdge(int v1, int v2);
    // A domain / far-field boundary edge and the two things it carries, written
    // together. `addEdge` followed by two assignments to `edges.back()` was the
    // idiom at every call site, i.e. two chances to write half an identity — the
    // same defect shape `recordBoundaryEdge` exists to prevent one level down.
    void addTaggedEdge(int v1, int v2, const std::string& bc, long long segKey);
    void addElement(const std::vector<int>& ids);
    // The same cell, carrying the multi-block block index it came from. An
    // overload rather than a write to `elements.back()`, for the reason
    // `addTaggedEdge` exists one line up: the call site cannot then record the
    // cell and forget the tag.
    void addElement(const std::vector<int>& ids, int blockId);
    // The same cell, marked as one the BOUNDARY LAYER emitted. A third named
    // entry point rather than a bool parameter on the first, for the reason the
    // overload above exists: the mark is made where the cell is made, so a call
    // site cannot record the cell and forget what produced it. `src/BoundaryLayer
    // .cpp` is its only caller, and that is the rule — any other producer's cells
    // are bulk by construction rather than by remembering to pass `false`.
    void addBoundaryLayerElement(const std::vector<int>& ids);

    // Phase 4: 使用 Gmsh 生成遠場三角形網格，支援長寬比過渡控制
    // seeds: 加密種子 (Pointwise-like sources)，只驅動局部最小尺寸/選擇性內嵌貼合
    // Returns true on success. Returns false (and reports an actionable message)
    // if Gmsh threw or produced an empty mesh; on failure gmsh::finalize() has
    // still run and no partial far-field cells were added. The resolved Gmsh
    // version string is written to `gmshVersionOut` for provenance when non-null.
    bool generateFarFieldGmsh(const Config& config, double finalBLThickness,
                              const std::vector<SeedGeom>& seeds = {},
                              std::string* gmshVersionOut = nullptr);

    // Phase 5: 針對碰撞區域進行局部網格平滑化
    void smoothMesh(int iters);

    void generateCartesianMesh(double xMin, double xMax, double yMin, double yMax, double ds);

    void exportVTK(const std::string& filename) const;
    void exportStarCD(const std::string& baseFilename, const Config& config) const;

    // Phase 4: CGNS unstructured export with per-BC patches. Compiled only when
    // the CGNS library is found at configure time; otherwise a no-op stub warns.
    void exportCGNS(const std::string& filename, const Config& config) const;

private:
    // The two halves of a recorded boundary edge. Private on purpose: they are a
    // single fact stored in two containers, so only recordBoundaryEdge /
    // boundaryEdgeInfo may touch them (see those for the full reasoning).
    std::map<std::pair<int, int>, std::string> boundaryEdgeBc;
    std::map<std::pair<int, int>, long long> boundaryEdgeSeg;

    static std::pair<int, int> edgeKey(int v1, int v2) {
        return {std::min(v1, v2), std::max(v1, v2)};
    }

    // A tagged domain / far-field boundary segment (rectangle side or custom
    // polygon edge). Boundary cell-edges lying on it inherit its BC; this
    // generalizes the legacy axis-aligned (x≈xMin …) classification to any shape.
    struct BcRefSeg { Point2D a, b; std::string bc; long long segKey = -1; };
    // Gather the tagged boundary reference segments: the explicitly tagged domain /
    // far-field edges in `edges`, PLUS every recorded surface segment from
    // boundaryEdgeBc. Including the latter lets a Gmsh-subdivided sub-edge of a
    // NO-BL surface resolve its BC by position even when the BL absorbed the
    // original edge out of the front ring (so it was never emitted to `edges`).
    std::vector<BcRefSeg> collectBcRefSegs() const;
    // Classify one boundary edge (endpoints v1,v2) to a BC name, and (if segKeyOut
    // is non-null) report the source-segment key it belongs to. Priority:
    //   0) an exact per-edge BC recorded at construction (boundaryEdgeBc) — the
    //      authoritative per-EDGE tag for BL-grown surface edges,
    //   1) a domain reference segment it lies on (rectangle side / polygon edge /
    //      any surface segment via boundaryEdgeBc),
    //   2) a geometry per-segment Node::bcTag shared by both endpoints (fallback
    //      for Gmsh-subdivided edges not present in boundaryEdgeBc),
    //   3) config.bcGeom (also the internal-flow wall default).
    std::string classifyBoundaryBc(int v1, int v2,
                                   const std::vector<BcRefSeg>& refs,
                                   const Config& config,
                                   long long* segKeyOut = nullptr) const;
};

#endif
