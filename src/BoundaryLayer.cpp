#include "BoundaryLayer.hpp"
#include <iostream>
#include <map>
#include <cmath>
#include <algorithm>
#include <vector>

BoundaryLayerGenerator::BoundaryLayerGenerator(Mesh& mesh, const Config& config)
    : m_mesh(mesh), m_config(config) {}

bool willIntersect(const Point2D& p1, const Point2D& p2, const std::vector<Point2D>& front, int excludeIdx) {
    int nf = (int)front.size();
    for (int i = 0; i < nf; ++i) {
        if (i == excludeIdx || i == (excludeIdx - 1 + nf) % nf || i == (excludeIdx + 1) % nf) continue;
        if (segmentsIntersect(p1, p2, front[i], front[(i + 1) % nf])) return true;
    }
    return false;
}

void BoundaryLayerGenerator::detectGrowthDirection(const std::vector<int>& nodeIds) {
    int n = static_cast<int>(nodeIds.size());
    if (n < 3) return;
    Point2D centroid = {0, 0};
    for (int id : nodeIds) centroid = centroid + m_mesh.nodes[id].pos;
    centroid = centroid / (double)n;
    const Point2D& p0 = m_mesh.nodes[nodeIds[0]].pos;
    const Point2D& p1 = m_mesh.nodes[nodeIds[1]].pos;
    Vector2D edge = (p1 - p0).normalized();
    Vector2D leftN = edge.leftNormal();
    Vector2D rightN = edge.rightNormal();
    auto isInside = [&](const Point2D& p) {
        return (p.x > m_config.xMin && p.x < m_config.xMax && p.y > m_config.yMin && p.y < m_config.yMax);
    };
    if (isInside(p0)) {
        m_growthSign = ((p0 + leftN * 0.1 - centroid).lengthSq() > (p0 + rightN * 0.1 - centroid).lengthSq()) ? 1.0 : -1.0;
    } else {
        m_growthSign = ((p0 + leftN * 0.1 - centroid).lengthSq() < (p0 + rightN * 0.1 - centroid).lengthSq()) ? 1.0 : -1.0;
    }
    std::cout << "Detected Growth Sign: " << m_growthSign << " (1: Left Normal, -1: Right Normal)\n";
}

double BoundaryLayerGenerator::generate(const std::vector<int>& boundaryNodeIds) {
    detectGrowthDirection(boundaryNodeIds);
    std::vector<int> activeFront = boundaryNodeIds;
    double currentH = m_config.blInitialThickness;
    double lastH = currentH;
    std::map<int, Vector2D> nodeDirections;

    for (int layer = 0; layer < m_config.blLayers; ++layer) {
        lastH = currentH;
        int n = static_cast<int>(activeFront.size());
        if (n < 3) break;

        std::vector<Vector2D> n1_list(n), n2_list(n);
        std::vector<bool> isConvexList(n, false);
        std::vector<bool> isConcaveList(n, false);
        std::vector<Point2D> currentPos(n);

        for (int i = 0; i < n; ++i) {
            currentPos[i] = m_mesh.nodes[activeFront[i]].pos;
            Point2D p_prev = m_mesh.nodes[activeFront[(i - 1 + n) % n]].pos;
            Point2D p_next = m_mesh.nodes[activeFront[(i + 1) % n]].pos;
            Vector2D v1 = (currentPos[i] - p_prev).normalized();
            Vector2D v2 = (p_next - currentPos[i]).normalized();
            
            n1_list[i] = (m_growthSign > 0 ? v1.leftNormal() : v1.rightNormal());
            n2_list[i] = (m_growthSign > 0 ? v2.leftNormal() : v2.rightNormal());

            // 計算轉角 (Turn Angle): 凸角為負, 凹角為正 (若生長方向為左)
            double angle1 = std::atan2(v1.y, v1.x);
            double angle2 = std::atan2(v2.y, v2.x);
            double diff = angle2 - angle1;
            while (diff > M_PI) diff -= 2*M_PI;
            while (diff < -M_PI) diff += 2*M_PI;

            // 計算外部夾角 (Exterior Angle)
            // 對於外生長來說：180 - diff(弧度轉角度)
            double turnDeg = diff * 180.0 / M_PI;
            double exteriorAngle = 180.0 - (m_growthSign * turnDeg);

            if (exteriorAngle > m_config.blConvexAngleThreshold) {
                isConvexList[i] = true;
            } else if (exteriorAngle < m_config.blConcaveAngleThreshold) {
                isConcaveList[i] = true;
            }
        }

        std::vector<int> clusterId(n);
        for (int i = 0; i < n; ++i) clusterId[i] = i;

        if (m_config.blMergeConcave) {
            for (int i = 0; i < n; ++i) {
                int i_next = (i + 1) % n;
                Vector2D dir_i = nodeDirections.count(activeFront[i]) ? nodeDirections[activeFront[i]] : (n1_list[i] + n2_list[i]).normalized();
                Vector2D dir_next = nodeDirections.count(activeFront[i_next]) ? nodeDirections[activeFront[i_next]] : (n1_list[i_next] + n2_list[i_next]).normalized();
                Point2D target_i = currentPos[i] + dir_i * currentH;
                Point2D target_next = currentPos[i_next] + dir_next * currentH;
                double currentDistSq = (currentPos[i] - currentPos[i_next]).lengthSq();
                double targetDistSq = (target_i - target_next).lengthSq();
                if (isConcaveList[i] || (targetDistSq < (currentH * 0.3) * (currentH * 0.3) && targetDistSq < currentDistSq) || willIntersect(target_i, target_next, currentPos, i)) {
                    int id1 = clusterId[i], id2 = clusterId[i_next];
                    int newId = std::min(id1, id2);
                    for (int j = 0; j < n; ++j) if (clusterId[j] == id1 || clusterId[j] == id2) clusterId[j] = newId;
                }
            }
        }

        std::vector<int> nextFront;
        std::vector<std::vector<int>> p2c(n);
        std::map<int, std::vector<int>> clusterToNewNodes;

        for (int i = 0; i < n; ++i) {
            int cid = clusterId[i];
            if (clusterToNewNodes.count(cid)) { p2c[i] = clusterToNewNodes[cid]; continue; }
            int clusterSize = 0;
            for (int j = 0; j < n; ++j) if (clusterId[j] == cid) clusterSize++;

            if (clusterSize > 1) {
                Point2D avgPos = {0, 0}; Vector2D avgDir = {0, 0};
                for (int j = 0; j < n; ++j) {
                    if (clusterId[j] == cid) {
                        Vector2D dir = nodeDirections.count(activeFront[j]) ? nodeDirections[activeFront[j]] : (n1_list[j] + n2_list[j]).normalized();
                        avgPos = avgPos + currentPos[j] + dir * currentH; avgDir = avgDir + dir;
                    }
                }
                m_mesh.addNode(avgPos / (double)clusterSize, NodeType::BoundaryLayer);
                int newId = m_mesh.nodes.back().id;
                nextFront.push_back(newId); p2c[i].push_back(newId);
                clusterToNewNodes[cid] = p2c[i]; nodeDirections[newId] = avgDir.normalized();
            } else {
                if (layer == 0 && isConvexList[i]) {
                    int numFanNodes = std::max(2, m_config.blFanNodes);
                    double a1 = std::atan2(n1_list[i].y, n1_list[i].x), a2 = std::atan2(n2_list[i].y, n2_list[i].x);
                    if (m_growthSign > 0) { while (a2 > a1) a2 -= 2*M_PI; } else { while (a2 < a1) a2 += 2*M_PI; }
                    for (int k = 0; k < numFanNodes; ++k) {
                        double t = (double)k / (double)(numFanNodes - 1);
                        double angle = a1 * (1.0 - t) + a2 * t;
                        Vector2D nk = {std::cos(angle), std::sin(angle)};
                        m_mesh.addNode(currentPos[i] + nk * currentH, NodeType::BoundaryLayer);
                        int newId = m_mesh.nodes.back().id;
                        nextFront.push_back(newId); p2c[i].push_back(newId);
                        nodeDirections[newId] = nk;
                    }
                    for (int k = 0; k < (int)p2c[i].size() - 1; ++k) m_mesh.addElement({activeFront[i], p2c[i][k+1], p2c[i][k]});
                } else {
                    Vector2D dir = nodeDirections.count(activeFront[i]) ? nodeDirections[activeFront[i]] : (n1_list[i] + n2_list[i]).normalized();
                    m_mesh.addNode(currentPos[i] + dir * currentH, NodeType::BoundaryLayer);
                    int newId = m_mesh.nodes.back().id;
                    nextFront.push_back(newId); p2c[i].push_back(newId);
                    nodeDirections[newId] = dir;
                }
                clusterToNewNodes[cid] = p2c[i];
            }
        }
        for (int i = 0; i < n; ++i) {
            int i_next = (i + 1) % n;
            int n_curr_last = p2c[i].back(); int n_next_first = p2c[i_next].front();
            if (n_curr_last == n_next_first) m_mesh.addElement({activeFront[i], activeFront[i_next], n_curr_last});
            else { m_mesh.addElement({activeFront[i], activeFront[i_next], n_next_first}); m_mesh.addElement({activeFront[i], n_next_first, n_curr_last}); }
        }
        activeFront = nextFront; currentH *= m_config.blGrowthRate;
    }
    int nFinal = (int)activeFront.size();
    for (int i = 0; i < nFinal; ++i) m_mesh.addEdge(activeFront[i], activeFront[(i + 1) % nFinal]);
    return lastH;
}
