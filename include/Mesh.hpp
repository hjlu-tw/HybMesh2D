#ifndef MESH_HPP
#define MESH_HPP

#include "GeomUtils.hpp"
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
    std::vector<Element> elements;

    void addNode(Point2D p, NodeType type = NodeType::Interior);
    void addElement(const std::vector<int>& ids);
    
    void generateCartesianMesh(double xMin, double xMax, double yMin, double yMax, double ds);
    
    void exportVTK(const std::string& filename) const;
};

#endif
