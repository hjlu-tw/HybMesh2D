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

#include <set>

double BoundaryLayerGenerator::detectGrowthDirection(const std::vector<int>& nodeIds) {
    int n = static_cast<int>(nodeIds.size());
    if (n < 3) return 1.0;

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

    double sign = 1.0;
    if (isInside(p0)) {
        sign = isCCW ? -1.0 : 1.0;
    } else {
        sign = isCCW ? 1.0 : -1.0;
    }
    return sign;
}
bool BoundaryLayerGenerator::checkCollision(Point2D p, double threshold, const std::set<int>& ignoreIds, int currentGeomId) {
    for (const auto& node : m_mesh.nodes) {
        if (ignoreIds.count(node.id)) continue;
        
        // 忽略來自同一個幾何對象的節點 (Self-collision)
        // 這是為了解決細長幾何（如 wing trailing edge）在生長時誤判自我碰撞的問題
        if (node.geomId == currentGeomId) continue;

        double d2 = (p - node.pos).lengthSq();
        if (d2 < threshold * threshold) return true;
    }
    return false;
}

double BoundaryLayerGenerator::generate(const std::vector<std::vector<int>>& allBoundaryNodeIds) {
    std::vector<FrontState> fronts;
    int maxNTrans = 0;
    std::set<int> allInitialBoundaryIds;

    int currentId = 0;
    for (const auto& boundaryNodeIds : allBoundaryNodeIds) {
        allInitialBoundaryIds.insert(boundaryNodeIds.begin(), boundaryNodeIds.end());
        FrontState fs;
        fs.geomId = currentId++;
        fs.activeFront = boundaryNodeIds;
        fs.growthSign = detectGrowthDirection(boundaryNodeIds);
        
        int n_init = static_cast<int>(boundaryNodeIds.size());
        fs.fanNodeCounts.assign(n_init, m_config.blFanNodes);
        fs.n1_init.resize(n_init); fs.n2_init.resize(n_init);
        fs.isConvexInit.assign(n_init, false); fs.isConcaveInit.assign(n_init, false);
        fs.pos_init.resize(n_init);

        for (int i = 0; i < n_init; ++i) {
            fs.pos_init[i] = m_mesh.nodes[boundaryNodeIds[i]].pos;
            Point2D p_prev = m_mesh.nodes[boundaryNodeIds[(i - 1 + n_init) % n_init]].pos;
            Point2D p_next = m_mesh.nodes[boundaryNodeIds[(i + 1) % n_init]].pos;
            Vector2D v1 = (fs.pos_init[i] - p_prev).normalized();
            Vector2D v2 = (p_next - fs.pos_init[i]).normalized();
            fs.n1_init[i] = (fs.growthSign > 0 ? v1.leftNormal() : v1.rightNormal());
            fs.n2_init[i] = (fs.growthSign > 0 ? v2.leftNormal() : v2.rightNormal());
            double angle1 = std::atan2(v1.y, v1.x), angle2 = std::atan2(v2.y, v2.x);
            double diff = angle2 - angle1;
            while (diff > M_PI) diff -= 2*M_PI;
            while (diff < -M_PI) diff += 2*M_PI;
            double exteriorAngle = 180.0 - (fs.growthSign * diff * 180.0 / M_PI);
            if (exteriorAngle > m_config.blConvexAngleThreshold) fs.isConvexInit[i] = true;
            else if (exteriorAngle < m_config.blConcaveAngleThreshold) fs.isConcaveInit[i] = true;
        }

        // 計算過渡層數
        double h_tmp = m_config.blInitialThickness;
        for (int l = 0; l < m_config.blLayers; ++l) h_tmp *= m_config.blGrowthRate;
        double hFirst = h_tmp, rTrans = m_config.blTransitionGrowthRate;
        fs.nTrans = m_config.blTransitionLayers;
        if (m_config.blAutoTransitionLayers == 1 && m_config.globalAvgSegmentLength > 0) {
            fs.nTrans = std::max(0, (int)std::round(std::log(m_config.globalAvgSegmentLength / hFirst) / std::log(rTrans)));
        } else if (m_config.blAutoTransitionLayers == 2) {
            double totalLen = 0;
            for(int i=0; i<n_init; ++i) totalLen += (fs.pos_init[(i+1)%n_init] - fs.pos_init[i]).length();
            fs.nTrans = std::max(0, (int)std::round(std::log((totalLen/n_init) / hFirst) / std::log(rTrans)));
        }
        maxNTrans = std::max(maxNTrans, fs.nTrans);

        // Adaptive Fan Nodes
        double R_BL = 0.0, h_tmp2 = m_config.blInitialThickness;
        for (int l = 0; l < m_config.blLayers; ++l) { R_BL += h_tmp2; h_tmp2 *= m_config.blGrowthRate; }
        double R_trans = (fs.nTrans > 0) ? hFirst * (std::pow(rTrans, fs.nTrans) - 1.0) / (rTrans - 1.0) : 0.0;
        double D_total = R_BL + R_trans;

        if (m_config.blAutoFanNodes > 0) {
            std::vector<double> projectedWidths(n_init);
            double totalProjectedWidth = 0.0;
            for (int i = 0; i < n_init; ++i) {
                int i_next = (i + 1) % n_init;
                Vector2D ray_i = fs.isConvexInit[i] ? fs.n2_init[i] : (fs.n1_init[i] + fs.n2_init[i]).normalized();
                Vector2D ray_next = fs.isConvexInit[i_next] ? fs.n1_init[i_next] : (fs.n1_init[i_next] + fs.n2_init[i_next]).normalized();
                Point2D p_outer_i = fs.pos_init[i] + ray_i * D_total;
                Point2D p_outer_next = fs.pos_init[i_next] + ray_next * D_total;
                projectedWidths[i] = (p_outer_next - p_outer_i).length();
                totalProjectedWidth += projectedWidths[i];
            }
            double globalAvgWidth = totalProjectedWidth / (double)n_init;

            for (int i = 0; i < n_init; ++i) {
                if (fs.isConvexInit[i]) {
                    double a1 = std::atan2(fs.n1_init[i].y, fs.n1_init[i].x), a2 = std::atan2(fs.n2_init[i].y, fs.n2_init[i].x);
                    if (fs.growthSign > 0) { while (a2 > a1) a2 -= 2*M_PI; } else { while (a2 < a1) a2 += 2*M_PI; }
                    double arcLength = D_total * std::abs(a2 - a1);
                    double targetWidth = globalAvgWidth;
                    if (m_config.blAutoFanNodes == 2) {
                        double localWidthSum = 0.0; int neighborCount = 0;
                        for (int j = 1; j <= 5; ++j) {
                            localWidthSum += projectedWidths[(i - j + n_init) % n_init];
                            localWidthSum += projectedWidths[(i + j - 1 + n_init) % n_init];
                            neighborCount += 2;
                        }
                        targetWidth = localWidthSum / (double)neighborCount;
                    }
                    fs.fanNodeCounts[i] = std::max(2, (int)std::round(arcLength / targetWidth) + 1);
                }
            }
        }

        // Concave Handling (Method 5)
        if (m_config.blConcaveMethod == 5) {
            std::vector<double> S(n_init); S[0] = 0.0;
            for (int i = 1; i < n_init; ++i) S[i] = S[i-1] + (fs.pos_init[i] - fs.pos_init[i-1]).length();
            double L_total = S[n_init-1] + (fs.pos_init[0] - fs.pos_init[n_init-1]).length();
            std::vector<int> concaveIndices;
            for (int i = 0; i < n_init; ++i) if (fs.isConcaveInit[i]) concaveIndices.push_back(i);
            
            if (!concaveIndices.empty()) {
                double D_inf = m_config.blConcaveInfluenceMultiplier * D_total;
                for (int i = 0; i < n_init; ++i) {
                    Vector2D N_i = (fs.n1_init[i] + fs.n2_init[i]).normalized();
                    Point2D P_base_i = fs.pos_init[i] + N_i * D_total;
                    double weight_sum = 0.0; Vector2D shift_sum = {0, 0};
                    for (int k_idx : concaveIndices) {
                        double d = std::abs(S[i] - S[k_idx]);
                        double shortest_d = std::min(d, L_total - d);
                        if (shortest_d < D_inf) {
                            double w = (D_inf - shortest_d) / D_inf;
                            weight_sum += w;
                            Vector2D B_k = (fs.n1_init[k_idx] + fs.n2_init[k_idx]).normalized();
                            double len = (fs.n1_init[k_idx] + fs.n2_init[k_idx]).length();
                            double M_k = (len > 1e-6) ? (2.0 / len) : 1.0;
                            Point2D C_k = fs.pos_init[k_idx] + B_k * (D_total * M_k);
                            Vector2D S_ki = C_k - (fs.pos_init[k_idx] + N_i * D_total);
                            shift_sum = shift_sum + S_ki * w;
                        }
                    }
                    if (weight_sum > 0) {
                        double W_ratio = std::min(1.0, weight_sum) / weight_sum;
                        Point2D P_final_i = P_base_i + shift_sum * W_ratio;
                        Vector2D ray = P_final_i - fs.pos_init[i];
                        fs.nodeDirections[boundaryNodeIds[i]] = ray.normalized();
                        fs.nodeStepMultipliers[boundaryNodeIds[i]] = ray.length() / D_total;
                    } else {
                        fs.nodeDirections[boundaryNodeIds[i]] = N_i;
                        fs.nodeStepMultipliers[boundaryNodeIds[i]] = 1.0;
                    }
                }
            }
        }
        fronts.push_back(fs);
    }

    double currentH = m_config.blInitialThickness;
    double lastH = currentH;
    int totalLayers = m_config.blLayers + maxNTrans;
    for (int layer = 0; layer < totalLayers; ++layer) {
        lastH = currentH;
        
        // --- 1. 候選位置預算 (Candidate Phase) ---
        struct CandidateNode {
            int frontIdx;
            int parentNodeId;
            Point2D pos;
            Vector2D dir;
            double multiplier;
        };
        std::vector<std::vector<CandidateNode>> allCandidates(fronts.size());

        for (int fIdx = 0; fIdx < (int)fronts.size(); ++fIdx) {
            auto& fs = fronts[fIdx];
            if (layer >= m_config.blLayers + fs.nTrans) continue;

            int n = (int)fs.activeFront.size();
            std::vector<Vector2D> n1_list(n), n2_list(n);
            std::vector<bool> isConvexList(n, false);
            std::vector<Point2D> currentPos(n);

            for (int i = 0; i < n; ++i) {
                currentPos[i] = m_mesh.nodes[fs.activeFront[i]].pos;
                Point2D p_prev = m_mesh.nodes[fs.activeFront[(i - 1 + n) % n]].pos;
                Point2D p_next = m_mesh.nodes[fs.activeFront[(i + 1) % n]].pos;
                Vector2D v1 = (currentPos[i] - p_prev).normalized();
                Vector2D v2 = (p_next - currentPos[i]).normalized();
                n1_list[i] = (fs.growthSign > 0 ? v1.leftNormal() : v1.rightNormal());
                n2_list[i] = (fs.growthSign > 0 ? v2.leftNormal() : v2.rightNormal());
                double angle1 = std::atan2(v1.y, v1.x), angle2 = std::atan2(v2.y, v2.x);
                double diff = angle2 - angle1;
                while (diff > M_PI) diff -= 2*M_PI;
                while (diff < -M_PI) diff += 2*M_PI;
                double exteriorAngle = 180.0 - (fs.growthSign * diff * 180.0 / M_PI);
                if (exteriorAngle > m_config.blConvexAngleThreshold) isConvexList[i] = true;
            }

            for (int i = 0; i < n; ++i) {
                int nodeId = fs.activeFront[i];
                if (m_mesh.nodes[nodeId].isFrozen) continue;

                if (layer == 0 && isConvexList[i]) {
                    int numFanNodes = std::max(2, fs.fanNodeCounts[i]);
                    auto getDir = [&](int idx) {
                        int nid = fs.activeFront[idx];
                        return fs.nodeDirections.count(nid) ? fs.nodeDirections[nid] : (n1_list[idx] + n2_list[idx]).normalized();
                    };
                    auto getMult = [&](int idx) {
                        int nid = fs.activeFront[idx];
                        return fs.nodeStepMultipliers.count(nid) ? fs.nodeStepMultipliers[nid] : 1.0;
                    };
                    Vector2D d_p = getDir((i - 1 + n) % n), d_n = getDir((i + 1) % n);
                    if (isConvexList[(i - 1 + n) % n]) d_p = n1_list[i];
                    if (isConvexList[(i + 1) % n]) d_n = n2_list[i];
                    double a1 = std::atan2(d_p.y, d_p.x), a2 = std::atan2(d_n.y, d_n.x);
                    if (fs.growthSign > 0) { while (a2 > a1) a2 -= 2*M_PI; } else { while (a2 < a1) a2 += 2*M_PI; }
                    double m_p = getMult((i - 1 + n) % n), m_n = getMult((i + 1) % n);
                    if (isConvexList[(i - 1 + n) % n]) m_p = fs.nodeStepMultipliers.count(nodeId) ? fs.nodeStepMultipliers[nodeId] : 1.0;
                    if (isConvexList[(i + 1) % n]) m_n = fs.nodeStepMultipliers.count(nodeId) ? fs.nodeStepMultipliers[nodeId] : 1.0;

                    for (int k = 0; k < numFanNodes; ++k) {
                        double t = (double)k / (double)(numFanNodes - 1);
                        double angle = a1 * (1.0 - t) + a2 * t;
                        double local_m = m_p * (1.0 - t) + m_n * t;
                        Vector2D nk = {std::cos(angle), std::sin(angle)};
                        allCandidates[fIdx].push_back({fIdx, nodeId, currentPos[i] + nk * (currentH * local_m), nk, local_m});
                    }
                } else {
                    Vector2D dir = fs.nodeDirections.count(nodeId) ? fs.nodeDirections[nodeId] : (n1_list[i] + n2_list[i]).normalized();
                    double mult = fs.nodeStepMultipliers.count(nodeId) ? fs.nodeStepMultipliers[nodeId] : 1.0;
                    allCandidates[fIdx].push_back({fIdx, nodeId, currentPos[i] + dir * (currentH * mult), dir, mult});
                }
            }
        }

        // --- 2. 碰撞偵測與退回判定 (Collision Phase) ---
        std::set<int> currentLayerNodesToFreeze;
        double collisionThreshold = currentH;

        std::set<int> currentAllFrontsSet;
        for (const auto& fs : fronts) currentAllFrontsSet.insert(fs.activeFront.begin(), fs.activeFront.end());

        for (int fIdx = 0; fIdx < (int)fronts.size(); ++fIdx) {
            for (auto& cand : allCandidates[fIdx]) {
                // A. 候選點 vs 已有節點
                if (checkCollision(cand.pos, collisionThreshold, currentAllFrontsSet, fronts[fIdx].geomId)) {
                    currentLayerNodesToFreeze.insert(cand.parentNodeId);
                }
                // B. 候選點 vs 其他幾何候選點
                for (int fIdx2 = fIdx + 1; fIdx2 < (int)fronts.size(); ++fIdx2) {
                    if (fronts[fIdx].geomId == fronts[fIdx2].geomId) continue;
                    for (auto& cand2 : allCandidates[fIdx2]) {
                        if ((cand.pos - cand2.pos).lengthSq() < collisionThreshold * collisionThreshold) {
                            currentLayerNodesToFreeze.insert(cand.parentNodeId);
                            currentLayerNodesToFreeze.insert(cand2.parentNodeId);
                        }
                    }
                }
            }
        }

        // --- 3. 提交階段 (Commit Phase) ---
        for (int fIdx = 0; fIdx < (int)fronts.size(); ++fIdx) {
            auto& fs = fronts[fIdx];
            if (layer >= m_config.blLayers + fs.nTrans) continue;
            
            int n = (int)fs.activeFront.size();
            std::vector<int> nextFront;
            std::vector<std::vector<int>> p2c(n);

            for (int i = 0; i < n; ++i) {
                int nodeId = fs.activeFront[i];
                if (m_mesh.nodes[nodeId].isFrozen || currentLayerNodesToFreeze.count(nodeId)) {
                    m_mesh.nodes[nodeId].isFrozen = true;
                    nextFront.push_back(nodeId);
                    p2c[i].push_back(nodeId);
                    
                    if (checkCollision(m_mesh.nodes[nodeId].pos, m_config.blInitialThickness, {nodeId}, fs.geomId)) {
                        throw std::runtime_error("Error: Critical proximity detected after retreat at node " + std::to_string(nodeId));
                    }
                    continue;
                }

                for (const auto& cand : allCandidates[fIdx]) {
                    if (cand.parentNodeId == nodeId) {
                        m_mesh.addNode(cand.pos, NodeType::BoundaryLayer);
                        int newId = m_mesh.nodes.back().id;
                        m_mesh.nodes.back().geomId = fs.geomId;
                        nextFront.push_back(newId);
                        p2c[i].push_back(newId);
                        fs.nodeDirections[newId] = cand.dir;
                        fs.nodeStepMultipliers[newId] = cand.multiplier;
                    }
                }
                
                if (p2c[i].size() > 1) {
                    for (int k = 0; k < (int)p2c[i].size() - 1; ++k) {
                        m_mesh.addElement({nodeId, p2c[i][k+1], p2c[i][k]});
                    }
                }
            }

            for (int i = 0; i < n; ++i) {
                int i_next = (i + 1) % n;
                int n_curr_last = p2c[i].back();
                int n_next_first = p2c[i_next].front();
                
                bool i_frozen = m_mesh.nodes[fs.activeFront[i]].isFrozen;
                bool next_frozen = m_mesh.nodes[fs.activeFront[i_next]].isFrozen;

                if (n_curr_last == n_next_first) {
                    if (!i_frozen || !next_frozen) {
                        m_mesh.addElement({fs.activeFront[i], fs.activeFront[i_next], n_curr_last});
                    }
                } else {
                    if (!next_frozen) {
                        m_mesh.addElement({fs.activeFront[i], fs.activeFront[i_next], n_next_first});
                    }
                    if (!i_frozen) {
                        m_mesh.addElement({fs.activeFront[i], n_next_first, n_curr_last});
                    }
                }
            }
            fs.activeFront = nextFront;
        }

        if (layer < m_config.blLayers - 1) currentH *= m_config.blGrowthRate;
        else currentH *= m_config.blTransitionGrowthRate;
    }

    for (const auto& fs : fronts) {
        int nFinal = (int)fs.activeFront.size();
        for (int i = 0; i < nFinal; ++i) {
            if (fs.activeFront[i] != fs.activeFront[(i + 1) % nFinal]) {
                m_mesh.addEdge(fs.activeFront[i], fs.activeFront[(i + 1) % nFinal]);
            }
        }
    }
    return lastH;
}

