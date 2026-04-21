#include "BoundaryLayer.hpp"
#include <iostream>

BoundaryLayerGenerator::BoundaryLayerGenerator(Mesh& mesh, const Config& config)
    : m_mesh(mesh), m_config(config) {}

void BoundaryLayerGenerator::detectGrowthDirection(const std::vector<int>& nodeIds) {
    int n = static_cast<int>(nodeIds.size());
    if (n < 3) return;

    // 1. 計算幾何體中心 (Centroid)
    Point2D centroid = {0, 0};
    for (int id : nodeIds) centroid = centroid + m_mesh.nodes[id].pos;
    centroid = centroid / n;

    const Point2D& p0 = m_mesh.nodes[nodeIds[0]].pos;
    const Point2D& p1 = m_mesh.nodes[nodeIds[1]].pos;
    Vector2D edge = (p1 - p0).normalized();
    Vector2D leftN = edge.leftNormal();
    Vector2D rightN = edge.rightNormal();

    // 2. 判斷第一個點是否在計算域內部
    auto isInside = [&](const Point2D& p) {
        return (p.x > m_config.xMin && p.x < m_config.xMax &&
                p.y > m_config.yMin && p.y < m_config.yMax);
    };

    bool p0Inside = isInside(p0);
    
    Point2D testLeft = p0 + leftN * 0.1;
    Point2D testRight = p0 + rightN * 0.1;
    double dL = (testLeft - centroid).lengthSq();
    double dR = (testRight - centroid).lengthSq();

    if (p0Inside) {
        // 如果幾何體在計算域內部 (外流場)，則選擇「遠離幾何中心」的方向
        m_growthSign = (dL > dR) ? 1.0 : -1.0;
        std::cout << "External flow detected: Growing AWAY from geometry centroid.\n";
    } else {
        // 如果幾何體在計算域外部 (內流場)，則選擇「朝向幾何中心」的方向
        m_growthSign = (dL < dR) ? 1.0 : -1.0;
        std::cout << "Internal flow detected: Growing TOWARDS geometry centroid.\n";
    }
    
    std::cout << "Direction chosen: " << (m_growthSign > 0 ? "Left" : "Right") << "\n";
}

std::vector<Vector2D> BoundaryLayerGenerator::computeNormals(const std::vector<int>& nodeIds) {
    int n = static_cast<int>(nodeIds.size());
    std::vector<Vector2D> normals(n);

    for (int i = 0; i < n; ++i) {
        const Point2D& p_prev = m_mesh.nodes[nodeIds[(i - 1 + n) % n]].pos;
        const Point2D& p_curr = m_mesh.nodes[nodeIds[i]].pos;
        const Point2D& p_next = m_mesh.nodes[nodeIds[(i + 1) % n]].pos;

        Vector2D v1 = (p_curr - p_prev).normalized();
        Vector2D v2 = (p_next - p_curr).normalized();

        Vector2D n1 = (m_growthSign > 0) ? v1.leftNormal() : v1.rightNormal();
        Vector2D n2 = (m_growthSign > 0) ? v2.leftNormal() : v2.rightNormal();

        normals[i] = (n1 + n2).normalized();
    }
    return normals;
}

double BoundaryLayerGenerator::generate(const std::vector<int>& boundaryNodeIds) {
    detectGrowthDirection(boundaryNodeIds);
    
    std::vector<int> currentFront = boundaryNodeIds;
    double currentH = m_config.blInitialThickness;
    double lastH = currentH;

    for (int layer = 0; layer < m_config.blLayers; ++layer) {
        lastH = currentH;
        std::vector<Vector2D> normals = computeNormals(currentFront);
        std::vector<int> nextFront;

        for (int i = 0; i < currentFront.size(); ++i) {
            Point2D oldPos = m_mesh.nodes[currentFront[i]].pos;
            Point2D newPos = oldPos + normals[i] * currentH;
            
            m_mesh.addNode(newPos, NodeType::BoundaryLayer);
            nextFront.push_back(m_mesh.nodes.back().id);
        }

        int n = static_cast<int>(currentFront.size());
        for (int i = 0; i < currentFront.size(); ++i) {
            int i_next = (i + 1) % n;
            m_mesh.addElement({currentFront[i], currentFront[i_next], nextFront[i_next], nextFront[i]});
        }
        currentFront = nextFront;
        currentH *= m_config.blGrowthRate;
    }

    // 將最外層波前 (Outer Front) 加入 edges 供遠場三角化使用
    int nFinal = static_cast<int>(currentFront.size());
    for (int i = 0; i < nFinal; ++i) {
        m_mesh.addEdge(currentFront[i], currentFront[(i + 1) % nFinal]);
    }

    return lastH;
}

