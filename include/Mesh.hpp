#ifndef MESH_HPP
#define MESH_HPP

#include "GeomUtils.hpp"
#include "Config.hpp"
#include "Curve.hpp"
#include <vector>
#include <string>

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
};

struct Element {
    std::vector<int> nodeIds;
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

    void addNode(Point2D p, NodeType type = NodeType::Interior);
    void addEdge(int v1, int v2);
    void addElement(const std::vector<int>& ids);

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
    // A tagged domain / far-field boundary segment (rectangle side or custom
    // polygon edge). Boundary cell-edges lying on it inherit its BC; this
    // generalizes the legacy axis-aligned (x≈xMin …) classification to any shape.
    struct BcRefSeg { Point2D a, b; std::string bc; };
    // Gather the tagged domain-boundary segments from `edges` (non-empty bcTag).
    std::vector<BcRefSeg> collectBcRefSegs() const;
    // Classify one boundary edge (endpoints v1,v2) to a BC name. Priority:
    //   1) a domain reference segment it lies on (rectangle side / polygon edge),
    //   2) a geometry per-segment Node::bcTag shared by both endpoints,
    //   3) config.bcGeom (also the internal-flow wall default).
    std::string classifyBoundaryBc(int v1, int v2,
                                   const std::vector<BcRefSeg>& refs,
                                   const Config& config) const;
};

#endif
