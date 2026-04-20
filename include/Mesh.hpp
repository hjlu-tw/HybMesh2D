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
    
    void generateFarFieldGmsh(const Config& config);

    void generateCartesianMesh(double xMin, double xMax, double yMin, double yMax, double ds);
    
    void exportVTK(const std::string& filename) const;
};

#endif
