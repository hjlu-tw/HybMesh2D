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

    double area = 0.0;
    for (int i = 0; i < n; ++i) {
        const Point2D& p1 = m_mesh.nodes[nodeIds[i]].pos;
        const Point2D& p2 = m_mesh.nodes[nodeIds[(i + 1) % n]].pos;
        area += (p1.x * p2.y - p2.x * p1.y);
    }
    bool isCCW = (area > 0);

    const Point2D& p0 = m_mesh.nodes[nodeIds[0]].pos;
    auto isInside = [&](const Point2D& p) {
        return (p.x > m_config.xMin && p.x < m_config.xMax && p.y > m_config.yMin && p.y < m_config.yMax);
    };

    if (isInside(p0)) {
        // Internal object (e.g. airfoil): CCW -> inside is left, outward is right (-1.0)
        m_growthSign = isCCW ? -1.0 : 1.0;
    } else {
        // External boundary: CCW -> inside is left, inward is left (1.0)
        m_growthSign = isCCW ? 1.0 : -1.0;
    }
    std::cout << "Detected Growth Sign: " << m_growthSign << " (Orientation: " << (isCCW ? "CCW" : "CW") << ", Area: " << area << ")\n";
}

double BoundaryLayerGenerator::generate(const std::vector<int>& boundaryNodeIds) {
    detectGrowthDirection(boundaryNodeIds);
    std::vector<int> activeFront = boundaryNodeIds;
    double currentH = m_config.blInitialThickness;
    double lastH = currentH;
    std::map<int, Vector2D> nodeDirections;
    std::map<int, double> nodeStepMultipliers;

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
                Vector2D N_i = (n1_init[i] + n2_init[i]).normalized();
                Point2D P_base_i = pos_init[i] + N_i * D_total;

                double weight_sum = 0.0;
                Vector2D shift_sum = {0, 0};
                for (int k_idx : concaveIndices) {
                    double d = std::abs(S[i] - S[k_idx]);
                    double shortest_d = std::min(d, L_total - d);
                    if (shortest_d < D_inf) {
                        double w = (D_inf - shortest_d) / D_inf;
                        weight_sum += w;
                        
                        Vector2D B_k = (n1_init[k_idx] + n2_init[k_idx]).normalized();
                        double len = (n1_init[k_idx] + n2_init[k_idx]).length();
                        double M_k = (len > 1e-6) ? (2.0 / len) : 1.0;
                        M_k = std::min(M_k, 10.0);
                        
                        Point2D C_k = pos_init[k_idx] + B_k * (D_total * M_k);
                        Vector2D S_ki = C_k - (pos_init[k_idx] + N_i * D_total);
                        shift_sum = shift_sum + S_ki * w;
                    }
                }
                
                if (weight_sum > 0) {
                    double W_ratio = std::min(1.0, weight_sum) / weight_sum;
                    Point2D P_final_i = P_base_i + shift_sum * W_ratio;
                    
                    Vector2D ray = P_final_i - pos_init[i];
                    nodeDirections[boundaryNodeIds[i]] = ray.normalized();
                    nodeStepMultipliers[boundaryNodeIds[i]] = ray.length() / D_total;
                } else {
                    nodeDirections[boundaryNodeIds[i]] = N_i;
                    nodeStepMultipliers[boundaryNodeIds[i]] = 1.0;
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

        std::vector<int> nextFront;
        std::vector<std::vector<int>> p2c(n);
        std::map<int, std::vector<int>> clusterToNewNodes;

        for (int i = 0; i < n; ++i) {
            int cid = clusterId[i];
            if (clusterToNewNodes.count(cid)) { p2c[i] = clusterToNewNodes[cid]; continue; }
            int clusterSize = 0;
            for (int j = 0; j < n; ++j) if (clusterId[j] == cid) clusterSize++;

            if (clusterSize > 1) {
                Point2D avgPos = {0, 0}; Vector2D avgDir = {0, 0}; double avgMultiplier = 0.0;
                for (int j = 0; j < n; ++j) {
                    if (clusterId[j] == cid) {
                        Vector2D dir = nodeDirections.count(activeFront[j]) ? nodeDirections[activeFront[j]] : (n1_list[j] + n2_list[j]).normalized();
                        double multiplier = nodeStepMultipliers.count(activeFront[j]) ? nodeStepMultipliers[activeFront[j]] : 1.0;
                        avgPos = avgPos + currentPos[j] + dir * (currentH * multiplier); 
                        avgDir = avgDir + dir;
                        avgMultiplier += multiplier;
                    }
                }
                m_mesh.addNode(avgPos / (double)clusterSize, NodeType::BoundaryLayer);
                int newId = m_mesh.nodes.back().id;
                nextFront.push_back(newId); p2c[i].push_back(newId);
                clusterToNewNodes[cid] = p2c[i]; 
                nodeDirections[newId] = avgDir.normalized();
                nodeStepMultipliers[newId] = avgMultiplier / (double)clusterSize;
            } else {
                if (layer == 0 && isConvexList[i]) {
                    int numFanNodes = std::max(2, fanNodeCounts[i]);
                    
                    // 根據鄰居的「網格現況」重新規劃扇形邊界
                    Vector2D d_prev = nodeDirections[activeFront[(i - 1 + n) % n]];
                    Vector2D d_next = nodeDirections[activeFront[(i + 1) % n]];

                    // 安全機制：如果鄰居也是凸角，則該側回歸幾何法向以維持邊界穩定
                    if (isConvexList[(i - 1 + n) % n]) d_prev = n1_list[i];
                    if (isConvexList[(i + 1) % n]) d_next = n2_list[i];

                    double a1 = std::atan2(d_prev.y, d_prev.x);
                    double a2 = std::atan2(d_next.y, d_next.x);

                    if (m_growthSign > 0) { while (a2 > a1) a2 -= 2*M_PI; } else { while (a2 < a1) a2 += 2*M_PI; }
                    
                    double fanAngleDeg = std::abs(a2 - a1) * 180.0 / M_PI;
                    
                    double center_multiplier = nodeStepMultipliers.count(activeFront[i]) ? nodeStepMultipliers[activeFront[i]] : 1.0;
                    double m_prev = nodeStepMultipliers.count(activeFront[(i - 1 + n) % n]) ? nodeStepMultipliers[activeFront[(i - 1 + n) % n]] : center_multiplier;
                    double m_next = nodeStepMultipliers.count(activeFront[(i + 1) % n]) ? nodeStepMultipliers[activeFront[(i + 1) % n]] : center_multiplier;
                    
                    // 如果鄰居本身是凸角，其高度可能與當前扇形起點不匹配，此時回歸中心值
                    if (isConvexList[(i - 1 + n) % n]) m_prev = center_multiplier;
                    if (isConvexList[(i + 1) % n]) m_next = center_multiplier;

                    if (activeFront[i] == 246) {
                        Vector2D bisector = (n1_list[i] + n2_list[i]).normalized();
                        double a_bisect = std::atan2(bisector.y, bisector.x) * 180.0 / M_PI;
                        double a1_deg = a1 * 180.0 / M_PI;
                        double a2_deg = a2 * 180.0 / M_PI;
                        std::cout << "  [DEBUG Node 246]:\n";
                        std::cout << "    - Normal 1 (In): " << a1_deg << " deg, Multiplier: " << m_prev << "\n";
                        std::cout << "    - Normal 2 (Out): " << a2_deg << " deg, Multiplier: " << m_next << "\n";
                        std::cout << "    - Total Fan Sweep: " << fanAngleDeg << " deg\n";
                    }
                    std::cout << "  - Fan Angle Detail [Node " << activeFront[i] << "]: Total sweep = " << fanAngleDeg << " deg\n";

                    for (int k = 0; k < numFanNodes; ++k) {
                        double t = (double)k / (double)(numFanNodes - 1);
                        double angle = a1 * (1.0 - t) + a2 * t;
                        double local_multiplier = m_prev * (1.0 - t) + m_next * t;
                        
                        Vector2D nk = {std::cos(angle), std::sin(angle)};
                        m_mesh.addNode(currentPos[i] + nk * (currentH * local_multiplier), NodeType::BoundaryLayer);
                        int newId = m_mesh.nodes.back().id;
                        nextFront.push_back(newId); p2c[i].push_back(newId);
                        nodeDirections[newId] = nk;
                        nodeStepMultipliers[newId] = local_multiplier;
                    }
                    for (int k = 0; k < (int)p2c[i].size() - 1; ++k) m_mesh.addElement({activeFront[i], p2c[i][k+1], p2c[i][k]});
                } else {
                    Vector2D dir = nodeDirections.count(activeFront[i]) ? nodeDirections[activeFront[i]] : (n1_list[i] + n2_list[i]).normalized();
                    double multiplier = nodeStepMultipliers.count(activeFront[i]) ? nodeStepMultipliers[activeFront[i]] : 1.0;
                    m_mesh.addNode(currentPos[i] + dir * (currentH * multiplier), NodeType::BoundaryLayer);
                    int newId = m_mesh.nodes.back().id;
                    nextFront.push_back(newId); p2c[i].push_back(newId);
                    nodeDirections[newId] = dir;
                    nodeStepMultipliers[newId] = multiplier;
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
