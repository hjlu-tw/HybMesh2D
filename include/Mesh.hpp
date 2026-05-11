#ifndef MESH_HPP
#define MESH_HPP

#include "GeomUtils.hpp"
#include "Config.hpp"
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
};

struct Edge {
    int v1, v2;
};

struct Element {
    std::vector<int> nodeIds;
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
    void generateFarFieldGmsh(const Config& config, double finalBLThickness);

    // Phase 5: 針對碰撞區域進行局部網格平滑化
    void smoothMesh(int iters);

    void generateCartesianMesh(double xMin, double xMax, double yMin, double yMax, double ds);

    void exportVTK(const std::string& filename) const;
    void exportStarCD(const std::string& baseFilename, const Config& config) const;
};

#endif
