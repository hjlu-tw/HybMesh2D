#include "BoundaryLayer.hpp"
#include <iostream>
#include <map>
#include <cmath>
#include <algorithm>
#include <vector>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

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

    int n_init = static_cast<int>(boundaryNodeIds.size());
    std::vector<int> fanNodeCounts(n_init, m_config.blFanNodes);
    std::vector<Vector2D> n1_init(n_init), n2_init(n_init);
    std::vector<bool> isConvexInit(n_init, false), isConcaveInit(n_init, false);
    std::vector<Point2D> pos_init(n_init);

    for (int i = 0; i < n_init; ++i) {
        pos_init[i] = m_mesh.nodes[boundaryNodeIds[i]].pos;
        Point2D p_prev = m_mesh.nodes[boundaryNodeIds[(i - 1 + n_init) % n_init]].pos;
        Point2D p_next = m_mesh.nodes[boundaryNodeIds[(i + 1) % n_init]].pos;
        Vector2D v1 = (pos_init[i] - p_prev).normalized();
        Vector2D v2 = (p_next - pos_init[i]).normalized();
        n1_init[i] = (m_growthSign > 0 ? v1.leftNormal() : v1.rightNormal());
        n2_init[i] = (m_growthSign > 0 ? v2.leftNormal() : v2.rightNormal());
        double angle1 = std::atan2(v1.y, v1.x), angle2 = std::atan2(v2.y, v2.x);
        double diff = angle2 - angle1;
        while (diff > M_PI) diff -= 2*M_PI;
        while (diff < -M_PI) diff += 2*M_PI;
        double exteriorAngle = 180.0 - (m_growthSign * diff * 180.0 / M_PI);
        if (exteriorAngle > m_config.blConvexAngleThreshold) isConvexInit[i] = true;
        else if (exteriorAngle < m_config.blConcaveAngleThreshold) isConcaveInit[i] = true;
    }

    // 計算總深度 D_total (BL + Transition)
    double R_BL = 0.0, h_tmp = m_config.blInitialThickness;
    for (int l = 0; l < m_config.blLayers; ++l) { R_BL += h_tmp; h_tmp *= m_config.blGrowthRate; }
    double hFirst = h_tmp, rTrans = m_config.blTransitionGrowthRate;
    int nTrans = m_config.blTransitionLayers;
    if (m_config.blAutoTransitionLayers) {
        double totalLen = 0;
        for(int i=0; i<n_init; ++i) totalLen += (pos_init[(i+1)%n_init] - pos_init[i]).length();
        nTrans = std::max(0, (int)std::round(std::log((totalLen/n_init) / hFirst) / std::log(rTrans)));
    }
    double R_trans = (nTrans > 0) ? hFirst * (std::pow(rTrans, nTrans) - 1.0) / (rTrans - 1.0) : 0.0;
    double D_total = R_BL + R_trans;

    if (m_config.blAutoFanNodes) {
        std::cout << "----- Fan Node Auto-Detection -----\n";
        double totalNonFanWidth = 0.0;
        for (int i = 0; i < n_init; ++i) {
            int i_next = (i + 1) % n_init;
            Vector2D ray_i = isConvexInit[i] ? n2_init[i] : (n1_init[i] + n2_init[i]).normalized();
            Vector2D ray_next = isConvexInit[i_next] ? n1_init[i_next] : (n1_init[i_next] + n2_init[i_next]).normalized();
            totalNonFanWidth += (pos_init[i] + ray_i * D_total - (pos_init[i_next] + ray_next * D_total)).length();
        }
        double baselineWidth = totalNonFanWidth / (double)n_init;

        for (int i = 0; i < n_init; ++i) {
            if (isConvexInit[i]) {
                double a1 = std::atan2(n1_init[i].y, n1_init[i].x), a2 = std::atan2(n2_init[i].y, n2_init[i].x);
                if (m_growthSign > 0) { while (a2 > a1) a2 -= 2*M_PI; } else { while (a2 < a1) a2 += 2*M_PI; }
                double arcLength = D_total * std::abs(a2 - a1);
                fanNodeCounts[i] = std::max(2, (int)std::round(arcLength / baselineWidth) + 1);
                std::cout << "  - Convex Node " << boundaryNodeIds[i] << ": Angle=" << std::abs(a2-a1)*180.0/M_PI 
                          << " deg, ArcLength=" << arcLength << " -> FanNodes=" << fanNodeCounts[i] << "\n";
            }
        }
        std::cout << "Baseline Width: " << baselineWidth << ", Total Depth (D_total): " << D_total << "\n";
        std::cout << "-----------------------------------\n";
    }

    if (m_config.blConcaveMethod == 5) {
        std::cout << "----- Thickness-based Global Blending (Method 5) -----\n";
        std::vector<double> S(n_init); S[0] = 0.0;
        for (int i = 1; i < n_init; ++i) S[i] = S[i-1] + (pos_init[i] - pos_init[i-1]).length();
        double L_total = S[n_init-1] + (pos_init[0] - pos_init[n_init-1]).length();
        
        std::vector<int> concaveIndices;
        for (int i = 0; i < n_init; ++i) {
            if (isConcaveInit[i]) {
                concaveIndices.push_back(i);
                std::cout << "  - Detected Concave Corner at node " << boundaryNodeIds[i] << " (index " << i << ")\n";
            }
        }
        
        if (!concaveIndices.empty()) {
            double D_inf = m_config.blConcaveInfluenceMultiplier * D_total;
            std::cout << "Influence Distance (D_inf): " << D_inf << "\n";
            for (int i = 0; i < n_init; ++i) {
                double weight_sum = 0.0;
                Vector2D bisector_sum = {0, 0};
                for (int k_idx : concaveIndices) {
                    double d = std::abs(S[i] - S[k_idx]);
                    double shortest_d = std::min(d, L_total - d);
                    if (shortest_d < D_inf) {
                        double w = (D_inf - shortest_d) / D_inf;
                        weight_sum += w;
                        Vector2D B_k = (n1_init[k_idx] + n2_init[k_idx]).normalized();
                        bisector_sum = bisector_sum + B_k * w;
                    }
                }
                if (weight_sum > 0) {
                    double W = std::min(1.0, weight_sum);
                    Vector2D NaturalNormal = (n1_init[i] + n2_init[i]).normalized();
                    Vector2D B_blend = (bisector_sum / weight_sum).normalized();
                    Vector2D Dir_i = (NaturalNormal * (1.0 - W) + B_blend * W).normalized();
                    nodeDirections[boundaryNodeIds[i]] = Dir_i;
                }
            }
        }
        std::cout << "------------------------------------------------------\n";
    }

    int totalLayers = m_config.blLayers + nTrans;
    for (int layer = 0; layer < totalLayers; ++layer) {
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
                    int numFanNodes = std::max(2, fanNodeCounts[i]);
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
        activeFront = nextFront; 
        if (layer < m_config.blLayers - 1) {
            currentH *= m_config.blGrowthRate;
        } else {
            currentH *= m_config.blTransitionGrowthRate;
        }
    }
    int nFinal = (int)activeFront.size();
    for (int i = 0; i < nFinal; ++i) m_mesh.addEdge(activeFront[i], activeFront[(i + 1) % nFinal]);
    return lastH;
}
