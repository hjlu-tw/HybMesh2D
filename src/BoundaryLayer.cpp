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

double BoundaryLayerGenerator::generate(const std::vector<int>& boundaryNodeIds) {
    detectGrowthDirection(boundaryNodeIds);
    
    std::vector<int> currentFront = boundaryNodeIds;
    double currentH = m_config.blInitialThickness;
    double lastH = currentH;

    // 用於追蹤強制沿對稱線生長的節點，防止扇形網格歪斜
    std::map<int, Vector2D> forcedNormals;

    for (int layer = 0; layer < m_config.blLayers; ++layer) {
        lastH = currentH;
        int n = static_cast<int>(currentFront.size());
        std::vector<std::vector<int>> layerNodes(n);
        
        for (int i = 0; i < n; ++i) {
            const Point2D& p_prev = m_mesh.nodes[currentFront[(i - 1 + n) % n]].pos;
            const Point2D& p_curr = m_mesh.nodes[currentFront[i]].pos;
            const Point2D& p_next = m_mesh.nodes[currentFront[(i + 1) % n]].pos;

            Vector2D v1 = (p_curr - p_prev).normalized();
            Vector2D v2 = (p_next - p_curr).normalized();

            Vector2D n1 = (m_growthSign > 0) ? v1.leftNormal() : v1.rightNormal();
            Vector2D n2 = (m_growthSign > 0) ? v2.leftNormal() : v2.rightNormal();

            // 銳角偵測與 Fan 處理
            double cross = v1.x * v2.y - v1.y * v2.x;
            bool isConvex = (m_growthSign > 0) ? (cross < 0) : (cross > 0);
            double dot = v1.dot(v2);

            // 使用設定檔中的閾值 (角度轉餘弦)
            double cosThreshold = std::cos(m_config.blFanAngleThreshold * M_PI / 180.0);

            if (isConvex && dot < cosThreshold) { // 轉角大於閾值且為凸角
                int numFanNodes = m_config.blFanNodes;
                double angle1 = std::atan2(n1.y, n1.x);
                double angle2 = std::atan2(n2.y, n2.x);

                if (m_growthSign > 0) { // 向左長，順時針旋轉
                    while (angle2 > angle1) angle2 -= 2 * M_PI;
                } else { // 向右長，逆時針旋轉
                    while (angle2 < angle1) angle2 += 2 * M_PI;
                }

                for (int k = 0; k < numFanNodes; ++k) {
                    double t = static_cast<double>(k) / (numFanNodes - 1);
                    double angle = angle1 * (1.0 - t) + angle2 * t;
                    Vector2D nk = {std::cos(angle), std::sin(angle)};
                    m_mesh.addNode(p_curr + nk * currentH, NodeType::BoundaryLayer);
                    int newNodeId = m_mesh.nodes.back().id;
                    layerNodes[i].push_back(newNodeId);

                    // 強制扇形最中間的節點沿著平分線生長，確保對稱性
                    if (numFanNodes % 2 != 0 && k == numFanNodes / 2) {
                        forcedNormals[newNodeId] = nk;
                    }
                }

                // 加入 Fan 內部的三角形 (反向以符合主網格 orientation)
                for (int k = 0; k < numFanNodes - 1; ++k) {
                    m_mesh.addElement({currentFront[i], layerNodes[i][k+1], layerNodes[i][k]});
                }
            } else {
                Vector2D n_avg;
                if (forcedNormals.count(currentFront[i])) {
                    n_avg = forcedNormals[currentFront[i]];
                } else {
                    n_avg = (n1 + n2).normalized();
                }

                m_mesh.addNode(p_curr + n_avg * currentH, NodeType::BoundaryLayer);
                int newNodeId = m_mesh.nodes.back().id;
                layerNodes[i].push_back(newNodeId);

                // 將強制的方向傳遞給下一層節點
                if (forcedNormals.count(currentFront[i])) {
                    forcedNormals[newNodeId] = forcedNormals[currentFront[i]];
                    forcedNormals.erase(currentFront[i]);
                }
            }
        }

        std::vector<int> nextFront;
        for (int i = 0; i < n; ++i) {
            int i_next = (i + 1) % n;
            int n_last = layerNodes[i].back();
            int n_next_first = layerNodes[i_next].front();

            m_mesh.addElement({currentFront[i], currentFront[i_next], n_last});
            m_mesh.addElement({currentFront[i_next], n_next_first, n_last});

            for (int id : layerNodes[i]) nextFront.push_back(id);
        }

        currentFront = nextFront;
        currentH *= m_config.blGrowthRate;
    }

    int nFinal = static_cast<int>(currentFront.size());
    for (int i = 0; i < nFinal; ++i) {
        m_mesh.addEdge(currentFront[i], currentFront[(i + 1) % nFinal]);
    }

    return lastH;
}

