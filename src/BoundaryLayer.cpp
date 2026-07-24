#include "BoundaryLayer.hpp"
#include "Logger.hpp"
#include <iostream>
#include <map>
#include <cmath>
#include <algorithm>
#include <vector>
#include <cstdio>
#include <cstdlib>

// isatty: gate the '\r' in-place progress bar so a piped / CI / GUI stdout gets
// newline-terminated progress lines instead of unflushed carriage returns.
#if defined(_WIN32)
#include <io.h>
#define HYBMESH_ISATTY(fd) _isatty(fd)
#define HYBMESH_FILENO(f)  _fileno(f)
#else
#include <unistd.h>
#define HYBMESH_ISATTY(fd) isatty(fd)
#define HYBMESH_FILENO(f)  fileno(f)
#endif

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

double BoundaryLayerGenerator::detectGrowthDirection(const std::vector<int>& nodeIds, int growMode) {
    int n = static_cast<int>(nodeIds.size());
    if (n < 3) return 1.0;

    double area = 0.0;
    for (int i = 0; i < n; ++i) {
        const Point2D& p1 = m_mesh.nodes[nodeIds[i]].pos;
        const Point2D& p2 = m_mesh.nodes[nodeIds[(i + 1) % n]].pos;
        area += (p1.x * p2.y - p2.x * p1.y);
    }
    bool isCCW = (area > 0);

    // Explicit role (Phase 3). For a CCW loop, leftNormal (sign>0) points to the
    // interior and rightNormal (sign<0) to the exterior; a CW loop is the mirror,
    // and the isCCW branch below encodes both windings.
    if (growMode > 0) return isCCW ? 1.0 : -1.0;   // grow toward loop interior (internal wall)
    if (growMode < 0) return isCCW ? -1.0 : 1.0;   // grow toward loop exterior (obstacle/island)

    // Auto (legacy, external flow): decide from whether the loop sits inside the
    // rectangular domain box. Unchanged for backward compatibility.
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

double BoundaryLayerGenerator::generate(const std::vector<std::vector<int>>& allBoundaryNodeIds,
                                        const std::vector<int>& growModes,
                                        const std::vector<BLParams>& blParamsPerLoop) {
    std::vector<FrontState> fronts;
    int maxNTrans = 0;
    std::set<int> allInitialBoundaryIds;
    int nJuncCap = 0;   // #6: BL/no-BL junction taper tally

    // Query the debug env var ONCE — it can't change mid-run, and getenv is a
    // locking libc lookup that would otherwise be re-run for every surface node
    // on every front (thousands of redundant calls per generate()).
    const bool juncDebug = (std::getenv("HYBMESH_JUNC_DEBUG") != nullptr);

    int currentId = 0;
    for (const auto& boundaryNodeIds : allBoundaryNodeIds) {
        allInitialBoundaryIds.insert(boundaryNodeIds.begin(), boundaryNodeIds.end());
        FrontState fs;
        int gm = (currentId < static_cast<int>(growModes.size())) ? growModes[currentId] : 0;
        fs.geomId = currentId++;
        fs.activeFront = boundaryNodeIds;
        fs.growthSign = detectGrowthDirection(boundaryNodeIds, gm);
        // Effective per-geometry BL parameters (this loop's overrides on top of
        // the global defaults) and the front's starting layer thickness.
        fs.bl = (fs.geomId < static_cast<int>(blParamsPerLoop.size()))
                    ? blParamsPerLoop[fs.geomId] : m_config.globalBLParams();
        fs.currentH = fs.bl.blInitialThickness;

        int n_init = static_cast<int>(boundaryNodeIds.size());
        fs.fanNodeCounts.assign(n_init, fs.bl.blFanNodes);
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
            if (exteriorAngle > fs.bl.blConvexAngleThreshold) fs.isConvexInit[i] = true;
            else if (exteriorAngle < fs.bl.blConcaveAngleThreshold) fs.isConcaveInit[i] = true;
            if (std::getenv("HYBMESH_CORNER_DEBUG") && m_mesh.nodes[boundaryNodeIds[i]].isCorner)
                std::cerr << "[CORNER] pos(" << fs.pos_init[i].x << "," << fs.pos_init[i].y
                          << ") extAngle=" << exteriorAngle
                          << (fs.isConvexInit[i] ? " CONVEX" : (fs.isConcaveInit[i] ? " CONCAVE" : " mild(bisector)"))
                          << std::endl;
        }

        // Phase 3: on line/circle surface runs, replace the finite-difference
        // initial normals with exact analytic normals at smooth (non-corner)
        // nodes. Smooth/polyline runs and corner/convex/concave nodes are left
        // untouched, so with the flag off — or for any non-line/circle body —
        // the result is bit-for-bit identical to before. The win is on curved
        // surfaces (cylinders, leading edges) where the chord normal is only
        // O(dtheta^2)-accurate but the radial normal is exact.
        if (fs.bl.blUseAnalyticGeom) {
            int nOverridden = 0;
            double maxAngleDeg = 0.0;
            int i = 0;
            while (i < n_init) {
                CurveKind kind = m_mesh.nodes[boundaryNodeIds[i]].curveKind;
                int j = i;
                while (j + 1 < n_init &&
                       m_mesh.nodes[boundaryNodeIds[j + 1]].curveKind == kind) ++j;
                if ((kind == CurveKind::Line || kind == CurveKind::Circle) && (j - i + 1) >= 2) {
                    std::vector<Point2D> runPts(fs.pos_init.begin() + i, fs.pos_init.begin() + j + 1);
                    auto curve = makeCurve(kind, runPts);
                    for (int k = i; k <= j; ++k) {
                        if (m_mesh.nodes[boundaryNodeIds[k]].isCorner ||
                            fs.isConvexInit[k] || fs.isConcaveInit[k]) continue;
                        // The growth direction for a smooth node is the bisector of
                        // the two edge normals; measure how far the exact analytic
                        // normal moves it (deterministic, unlike the gmsh far-field).
                        Vector2D oldDir = (fs.n1_init[k] + fs.n2_init[k]).normalized();
                        Vector2D t = curve->tangentAt(k - i);
                        Vector2D nrm = (fs.growthSign > 0 ? t.leftNormal() : t.rightNormal()).normalized();
                        double d = std::max(-1.0, std::min(1.0, oldDir.dot(nrm)));
                        maxAngleDeg = std::max(maxAngleDeg, std::acos(d) * 180.0 / M_PI);
                        fs.n1_init[k] = nrm;
                        fs.n2_init[k] = nrm;
                        ++nOverridden;
                    }
                }
                i = j + 1;
            }
            if (nOverridden > 0)
                std::cout << "  [Analytic BL] geom " << fs.geomId << ": " << nOverridden
                          << " smooth node normal(s) set analytically (max shift "
                          << maxAngleDeg << " deg vs finite-difference)\n";
        }

        // Validate BL params before use. Non-positive thickness / growth make
        // hFirst <= 0 (log of a non-positive number is NaN) and a transition rate
        // that isn't > 1 makes the auto-count divisor 0/negative -> the round()
        // of Inf/NaN is UB. Clamp to safe values with a one-time warning instead.
        if (!(fs.bl.blInitialThickness > 0.0)) {
            LOG_WARN("BL initial thickness <= 0 (" << fs.bl.blInitialThickness
                     << ") on geometry " << fs.geomId << "; clamping to 0.01.");
            fs.bl.blInitialThickness = 0.01;
            fs.currentH = fs.bl.blInitialThickness;
        }
        if (!(fs.bl.blGrowthRate > 0.0)) {
            LOG_WARN("BL growth rate <= 0 (" << fs.bl.blGrowthRate
                     << ") on geometry " << fs.geomId << "; clamping to 1.2.");
            fs.bl.blGrowthRate = 1.2;
        }

        // 計算過渡層數
        double h_tmp = fs.bl.blInitialThickness;
        for (int l = 0; l < fs.bl.blLayers; ++l) h_tmp *= fs.bl.blGrowthRate;
        double hFirst = h_tmp, rTrans = fs.bl.blTransitionGrowthRate;
        fs.nTrans = fs.bl.blTransitionLayers;
        // Auto transition-layer count solves for how many geometrically-growing
        // layers reach the target size, so it needs rTrans > 1 and hFirst > 0.
        // With no growth (rTrans <= 1) std::log(rTrans) is 0/negative and the
        // division blows up to inf/nan; keep the manual count in that case. A
        // rate barely above 1 can also explode the count, so clamp nTrans to a
        // sane maximum (avoids a hang / OOM).
        const int kMaxTransLayers = 1000;
        if (rTrans > 1.0 && hFirst > 0.0 && fs.bl.blAutoTransitionLayers == 1 && m_config.globalAvgSegmentLength > 0) {
            fs.nTrans = std::max(0, (int)std::round(std::log(m_config.globalAvgSegmentLength / hFirst) / std::log(rTrans)));
        } else if (rTrans > 1.0 && hFirst > 0.0 && fs.bl.blAutoTransitionLayers == 2) {
            double totalLen = 0;
            for(int i=0; i<n_init; ++i) totalLen += (fs.pos_init[(i+1)%n_init] - fs.pos_init[i]).length();
            fs.nTrans = std::max(0, (int)std::round(std::log((totalLen/n_init) / hFirst) / std::log(rTrans)));
        }
        if (fs.nTrans > kMaxTransLayers) {
            LOG_WARN("auto transition-layer count (" << fs.nTrans
                     << ") on geometry " << fs.geomId << " exceeds the cap; clamping to "
                     << kMaxTransLayers << " (transition growth rate "
                     << rTrans << " is very close to 1).");
            fs.nTrans = kMaxTransLayers;
        }
        maxNTrans = std::max(maxNTrans, fs.nTrans);

        // Adaptive Fan Nodes
        double R_BL = 0.0, h_tmp2 = fs.bl.blInitialThickness;
        for (int l = 0; l < fs.bl.blLayers; ++l) { R_BL += h_tmp2; h_tmp2 *= fs.bl.blGrowthRate; }
        // Geometric-series sum of the transition layer thicknesses. When rTrans
        // == 1 the closed form divides by zero, so use the degenerate (uniform)
        // sum hFirst * nTrans instead.
        double R_trans = 0.0;
        if (fs.nTrans > 0) {
            R_trans = (std::abs(rTrans - 1.0) < 1e-9)
                ? hFirst * fs.nTrans
                : hFirst * (std::pow(rTrans, fs.nTrans) - 1.0) / (rTrans - 1.0);
        }
        double D_total = R_BL + R_trans;

        if (fs.bl.blAutoFanNodes > 0) {
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
                    if (fs.bl.blAutoFanNodes == 2) {
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

        // --- BL / no-BL junction: perpendicular cap + height taper (#6) ----
        // Where a growing node borders a segment that grows NO boundary layer
        // (skipBL, from a .meta grow=0 segment), the corner bisector would tilt
        // the growth ray toward the no-BL edge and skew / invert the cell, and a
        // full-height cap leaves an abrupt cliff of quads facing the no-BL run.
        // Following how commercial prism-layer meshers terminate layers against a
        // no-layer region, the BL here is TAPERED to (near) zero approaching the
        // junction — a smooth "collapsing prisms" transition — instead of capping
        // at full height or leaning onto the no-BL edge:
        //   • the JUNCTION node (a BL node with a no-BL neighbour) grows along its
        //     own BL edge's outward NORMAL — perpendicular, never the 45° bisector
        //     (the reported "grows on the 角平分線" bug at a BL→no-BL end);
        //   • every node's layer HEIGHT is scaled by a taper factor that is a
        //     small floor at the junction and ramps smoothly back to 1 over a
        //     taper distance (arc length) into the BL interior, so the outer
        //     front descends toward the surface at the junction with no cliff and
        //     the far-field mesher fills the shrinking wedge (the skipBL stitch
        //     below already emits the filler triangle there).
        // baseN is each node's base direction; the concave pass below bends the
        // non-junction rays; the junction is finalised after the concave pass.
        std::vector<bool>     isJunction(n_init, false);
        std::vector<Vector2D> baseN(n_init);
        std::vector<int>      caseOf(n_init, 0);   // 4-case bin (blJunctionMethod==1); 0 = not a junction
        std::vector<double>   junctionMult(n_init, 1.0);  // per-junction step scale (perpendicular-height correction)
        for (int i = 0; i < n_init; ++i) {
            baseN[i] = (fs.n1_init[i] + fs.n2_init[i]).normalized();   // bisector default
            if (m_mesh.nodes[boundaryNodeIds[i]].skipBL) continue;     // grows no BL itself
            int ip = (i - 1 + n_init) % n_init, in = (i + 1) % n_init;
            bool prevSkip = m_mesh.nodes[boundaryNodeIds[ip]].skipBL;
            bool nextSkip = m_mesh.nodes[boundaryNodeIds[in]].skipBL;
            if (!prevSkip && !nextSkip) continue;                      // interior BL node: no junction
            // Pick the BL edge to grow along. With exactly ONE no-BL neighbour it
            // is the OTHER (BL) edge; with BOTH neighbours no-BL (an isolated BL
            // corner, e.g. a rectangle side resampled to just its two corners) the
            // node's own BL segment is the FORWARD edge (the resampler gives a
            // shared corner to the segment starting there), so use n2_init —
            // without this the corner fell through to the 45° bisector.
            Vector2D blNormal = (nextSkip && !prevSkip) ? fs.n1_init[i] : fs.n2_init[i];
            if (blNormal.length() < 1e-9) continue;                    // degenerate; keep bisector
            isJunction[i] = true;
            baseN[i] = blNormal.normalized();                          // perpendicular cap dir
        }

        // 4-case angle-driven junction scheme (blJunctionMethod == 1): override the
        // perpendicular baseN above with the growth direction dictated by the
        // flow-facing included angle theta between the BL edge and its no-BL
        // neighbour (see the case table in Config.hpp). No height taper is applied in
        // this scheme; cases 2/3/4 grow a free full-height lateral cap (the wedge to
        // the neighbour edge is filled by far-field triangles) and case 1 slides the
        // column along the neighbour edge (concave notch fill).
        if (fs.bl.blJunctionMethod == 1) {
            for (int i = 0; i < n_init; ++i) {
                if (!isJunction[i]) continue;
                int ip = (i - 1 + n_init) % n_init, in = (i + 1) % n_init;
                bool prevSkip = m_mesh.nodes[boundaryNodeIds[ip]].skipBL;
                bool nextSkip = m_mesh.nodes[boundaryNodeIds[in]].skipBL;
                // Isolated BL node (both neighbours no-BL): keep the perpendicular
                // cap that the base detection already set into baseN.
                if (prevSkip && nextSkip) { caseOf[i] = 2; continue; }

                // step points from this node INTO the no-BL run; the BL neighbour is
                // on the other side. nBL is the BL edge's outward (into-flow) normal.
                int step   = nextSkip ? 1 : -1;
                Vector2D nBL = (nextSkip ? fs.n1_init[i] : fs.n2_init[i]).normalized();
                int blNbr = (i - step + n_init) % n_init;
                int s1    = (i + step + n_init) % n_init;
                int s2    = (i + 2 * step + n_init) % n_init;
                bool s2skip = m_mesh.nodes[boundaryNodeIds[s2]].skipBL;

                Vector2D tBL = (fs.pos_init[blNbr] - fs.pos_init[i]).normalized(); // node -> BL interior
                Vector2D d1  = (fs.pos_init[s1]    - fs.pos_init[i]).normalized(); // node -> first no-BL nbr
                // The shared corner may belong to EITHER segment (the resampler gives
                // it to the segment starting there). If the first no-BL neighbour just
                // continues the BL edge (d1 ~ -tBL), the real corner is at s1 and the
                // no-BL EDGE direction is s1->s2; otherwise the corner is this node and
                // the no-BL edge is node->s1. This keeps theta = the true edge-to-edge
                // angle regardless of which segment owns the corner point.
                Vector2D tCorner, eNbr;
                if (s2skip && d1.dot(tBL) < -0.7) {
                    tCorner = (fs.pos_init[i]  - fs.pos_init[s1]).normalized();     // corner s1 -> BL interior
                    eNbr    = (fs.pos_init[s2] - fs.pos_init[s1]).normalized();     // corner s1 -> no-BL edge
                } else {
                    tCorner = tBL;
                    eNbr    = d1;
                }
                // theta = angle from the BL edge to the no-BL edge, swept THROUGH THE
                // FLOW (the side nBL points to); 180 = collinear, <180 concave, >180
                // convex — identical for internal/external flow.
                double a = std::atan2(tCorner.cross(eNbr), tCorner.dot(eNbr));
                if (tCorner.cross(nBL) < 0.0) a = -a;           // flow on the CW side -> flip sweep sign
                double theta = a; if (theta <= 1e-9) theta += 2.0 * M_PI;
                double thetaDeg = theta * 180.0 / M_PI;

                int caseId; Vector2D dir;
                // A CONCAVE BL/no-BL junction (theta <= C1) was formerly "case 1":
                // the BL column slid ALONG the no-BL neighbour edge and absorbed that
                // segment's surface nodes. On internal-flow concave corners (the
                // common case — a closed fluid domain growing its BL inward) this
                // collapsed the layer onto the wall the user explicitly marked no-BL
                // and did NOT preserve the layer height. Cap it PERPENDICULAR (case 2)
                // instead: the BL keeps a constant full height at the junction and the
                // wedge to the neighbour edge is graded by far-field triangles, never
                // touching the no-BL surface. (BL_JUNCTION_METHOD=0 restores the legacy
                // taper-to-zero; C1 is retained in Config for that scheme + round-trip.)
                if      (thetaDeg <= fs.bl.blJunctionAngleC2) { caseId = 2; dir = nBL; }
                else if (thetaDeg <= fs.bl.blJunctionAngleC3) { caseId = 3; dir = eNbr * -1.0; }
                else                                          { caseId = 4; dir = nBL; }
                // Height (not edge-length) correction: what stays fixed across ALL
                // cases is the BL's PERPENDICULAR total height D_total. A tilted cap
                // grown a fixed EDGE length would only reach D_total*cos(tilt) high and
                // dip below the neighbouring perpendicular columns, skewing the corner.
                // So scale the step by 1/cos(tilt) = 1/dot(dir,nBL) — the same trick the
                // convex parallelogram uses for its diagonal ray (cos clamped so a very
                // sharp concave cannot blow the column length up).
                double hmult = 1.0 / std::max(0.25, dir.dot(nBL));
                baseN[i] = dir;
                caseOf[i] = caseId;
                junctionMult[i] = hmult;
                if (juncDebug)
                    std::cerr << "[JUNC] pos(" << fs.pos_init[i].x << "," << fs.pos_init[i].y
                              << ") theta=" << thetaDeg << " case=" << caseId
                              << " dir(" << dir.x << "," << dir.y << ")" << std::endl;
            }
        }

        // Per-node height-taper factor: a small floor at a junction node, ramping
        // (smoothstep) back to 1.0 over L_taper of arc length into the interior.
        // Computed by relaxing the arc-length distance to the nearest junction
        // around the ring; stays 1.0 everywhere when the front has no junction so
        // a normal (no no-BL) geometry is bit-for-bit unchanged.
        std::vector<double> taperScale(n_init, 1.0);
        if (fs.bl.blJunctionMethod == 0) {
            std::vector<int> junctions;
            for (int i = 0; i < n_init; ++i) if (isJunction[i]) junctions.push_back(i);
            if (!junctions.empty()) {
                std::vector<double> segLen(n_init, 0.0);
                for (int i = 0; i < n_init; ++i)
                    segLen[i] = (fs.pos_init[(i + 1) % n_init] - fs.pos_init[i]).length();
                const double INF = 1e300;
                std::vector<double> dist(n_init, INF);
                for (int j : junctions) dist[j] = 0.0;
                // Two forward+backward sweeps converge the shortest ring distance.
                for (int rep = 0; rep < 2; ++rep) {
                    for (int k = 0; k < n_init; ++k) {
                        int ip = (k - 1 + n_init) % n_init;
                        if (dist[ip] + segLen[ip] < dist[k]) dist[k] = dist[ip] + segLen[ip];
                    }
                    for (int k = n_init - 1; k >= 0; --k) {
                        int in = (k + 1) % n_init;
                        if (dist[in] + segLen[k] < dist[k]) dist[k] = dist[in] + segLen[k];
                    }
                }
                const double L_taper = std::max(D_total * 2.0, 1e-12);
                const double floorScale = 0.12;   // junction ~12% height (thin but non-degenerate)
                for (int i = 0; i < n_init; ++i) {
                    if (dist[i] >= INF) continue;
                    double t = std::min(1.0, dist[i] / L_taper);
                    double s = t * t * (3.0 - 2.0 * t);            // smoothstep 0->1
                    taperScale[i] = floorScale + (1.0 - floorScale) * s;
                }
            }
        }

        // Mild corners get the height (not edge-length) correction UNCONDITIONALLY: a
        // tagged corner that is neither convex-fanned nor concave-blended nor a junction
        // grows a plain bisector; scale its step by 1/cos(half) so the bisector reaches
        // the full perpendicular height D_total (not D_total*cos(half), which dips and
        // skews the corner). The concave blend below refines this and tilts the
        // neighbours when method 5 is on; this keeps the height right even for method 0.
        for (int i = 0; i < n_init; ++i) {
            if (!m_mesh.nodes[boundaryNodeIds[i]].isCorner) continue;
            if (fs.isConvexInit[i] || fs.isConcaveInit[i] || isJunction[i]) continue;
            double cosHalf = std::max(0.34, baseN[i].dot(fs.n1_init[i]));
            fs.nodeStepMultipliers[boundaryNodeIds[i]] = 1.0 / cosHalf;
        }

        // Concave thickness-blending (method 5) AND 4-case junction blending. Runs
        // when method 5 is selected (pure concave corners) OR when the 4-case scheme
        // produced a case-1 (concave slide) or case-3 (convex, outward-flared
        // extension cap) junction. Such a junction blends the nearby columns from
        // perpendicular toward its cap direction (baseN) using the same weighted-shift
        // maths below, so the grid lines change slope GRADUALLY over a few columns
        // instead of jumping at the single cap column: case 1 leans them inward toward
        // the neighbour edge, case 3 flares them outward along the extension line.
        bool anyBlendJunction = false;
        for (int i = 0; i < n_init; ++i) if (caseOf[i] == 1 || caseOf[i] == 3) { anyBlendJunction = true; break; }
        if (fs.bl.blConcaveMethod == 5 || anyBlendJunction) {
            std::vector<double> S(n_init); S[0] = 0.0;
            for (int i = 1; i < n_init; ++i) S[i] = S[i-1] + (fs.pos_init[i] - fs.pos_init[i-1]).length();
            double L_total = S[n_init-1] + (fs.pos_init[0] - fs.pos_init[n_init-1]).length();
            std::vector<int> concaveIndices;
            for (int i = 0; i < n_init; ++i) {
                // 4-case junctions (scheme 1) always blend toward their case direction.
                if (fs.bl.blJunctionMethod == 1 && (caseOf[i] == 1 || caseOf[i] == 3)) {
                    concaveIndices.push_back(i);
                    continue;
                }
                if (fs.bl.blConcaveMethod != 5) continue;
                if (fs.bl.blJunctionMethod == 1 && isJunction[i]) continue;  // handled by its case
                // Method 5 blends: geometric concave corners AND "mild" tagged corners —
                // a corner that is neither convex-fanned (>convex thresh) nor concave-
                // blended (<concave thresh): the middle-angle range that otherwise grows
                // a plain bisector, dipping in height and jumping in slope at the corner.
                // Both blend toward the height-corrected bisector apex (M_k=1/cos(half)),
                // so the corner reaches full height D_total and the neighbours tilt gradually.
                bool mild = m_mesh.nodes[boundaryNodeIds[i]].isCorner
                            && !fs.isConvexInit[i] && !fs.isConcaveInit[i];
                if (fs.isConcaveInit[i] || mild) concaveIndices.push_back(i);
            }
            
            if (!concaveIndices.empty()) {
                double global_D_inf = fs.bl.blConcaveInfluenceMultiplier * D_total;
                std::vector<double> concave_D_inf(concaveIndices.size(), global_D_inf);
                for (size_t c = 0; c < concaveIndices.size(); ++c) {
                    int k_idx = concaveIndices[c];
                    double min_corner_dist = L_total;
                    for (int j = 0; j < n_init; ++j) {
                        if (j != k_idx && (fs.isConvexInit[j] || fs.isConcaveInit[j])) {
                            double d = std::abs(S[k_idx] - S[j]);
                            double shortest_d = std::min(d, L_total - d);
                            min_corner_dist = std::min(min_corner_dist, shortest_d);
                        }
                    }
                    if (min_corner_dist < L_total) {
                        concave_D_inf[c] = std::min(global_D_inf, min_corner_dist * 0.9);
                    }
                    // A MILD corner only needs a LOCAL blend ("a few lines"): cap its
                    // influence well below the full concave range. A large influence on
                    // a thick BL over-shifts the nearby columns and folds the front
                    // (self-intersection); genuine concave corners / junctions keep the
                    // full range.
                    bool mildSrc = m_mesh.nodes[boundaryNodeIds[k_idx]].isCorner
                                   && !fs.isConvexInit[k_idx] && !fs.isConcaveInit[k_idx]
                                   && caseOf[k_idx] == 0;
                    if (mildSrc) concave_D_inf[c] = std::min(concave_D_inf[c], 2.0 * D_total);
                }

                for (int i = 0; i < n_init; ++i) {
                    // #6: a junction node must stay perpendicular to its BL wall
                    // (it caps/tapers), so it is never bent by the concave
                    // influence — bending it produces a bisector-like ray at the
                    // corner (the reported "grows on the 角平分線" bug).
                    if (isJunction[i]) continue;
                    Vector2D N_i = baseN[i];
                    Point2D P_base_i = fs.pos_init[i] + N_i * D_total;
                    double weight_sum = 0.0; Vector2D shift_sum = {0, 0};
                    for (size_t c = 0; c < concaveIndices.size(); ++c) {
                        int k_idx = concaveIndices[c];
                        double current_D_inf = concave_D_inf[c];
                        double d = std::abs(S[i] - S[k_idx]);
                        double shortest_d = std::min(d, L_total - d);
                        if (shortest_d < current_D_inf) {
                            double w = (current_D_inf - shortest_d) / current_D_inf;
                            weight_sum += w;
                            // #6: a concave corner that is ALSO a BL/no-BL
                            // junction pulls toward its perpendicular BL-edge
                            // normal (baseN), not the bisector (which would lean
                            // into the no-BL side).
                            Vector2D B_k; double M_k;
                            if (isJunction[k_idx]) {
                                B_k = baseN[k_idx];
                                M_k = junctionMult[k_idx];  // target the cap's height-corrected outer node
                            } else {
                                B_k = (fs.n1_init[k_idx] + fs.n2_init[k_idx]).normalized();
                                double len = (fs.n1_init[k_idx] + fs.n2_init[k_idx]).length();
                                M_k = (len > 1e-6) ? (2.0 / len) : 1.0;
                            }
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

        // --- BL / no-BL junction finalise -----------------------------------
        // Every junction node grows a SINGLE ray along baseN[i] (never fan/split;
        // enforced via junctionCapNodes) and the direction propagates to each layer
        // as children inherit their candidate dir at commit.
        //   • Scheme 0 (taper): folds the taper factor into the step multiplier so
        //     the columns collapse toward the junction (collapsing prisms).
        //   • Scheme 1 (4-case): no taper. Cap junctions (cases 2/3/4) seed a lateral
        //     column (surface node) that commit extends layer by layer and emission
        //     turns into far-field inner-boundary edges. Slide junctions (case 1)
        //     absorb the no-BL neighbour nodes they cover so the far field resumes
        //     beyond them along the neighbour edge.
        for (int i = 0; i < n_init; ++i) {
            int nid = boundaryNodeIds[i];
            if (isJunction[i]) {
                fs.nodeDirections[nid] = baseN[i];
                fs.junctionCapNodes.insert(nid);
                ++nJuncCap;
                if (fs.bl.blJunctionMethod == 1) {
                    int ipf = (i - 1 + n_init) % n_init, inf = (i + 1) % n_init;
                    bool prevSkip = m_mesh.nodes[boundaryNodeIds[ipf]].skipBL;
                    bool nextSkip = m_mesh.nodes[boundaryNodeIds[inf]].skipBL;
                    int c = caseOf[i] > 0 ? caseOf[i] : 2;
                    fs.junctionCase[nid] = c;
                    // Keep the cap's PERPENDICULAR height = D_total (scale the whole
                    // single-ray column by 1/cos(tilt); =1 for a perpendicular cap).
                    fs.nodeStepMultipliers[nid] = junctionMult[i];
                    // An ISOLATED BL node (both neighbours no-BL) has two exposed sides
                    // and no single lateral column; leave it to stitch normally (like a
                    // plain perpendicular cap) rather than detaching it — a rare/degenerate
                    // configuration we do not special-case further.
                    if (prevSkip && nextSkip) {
                        // no column / no absorb / no wedge suppression
                    } else if (c != 1) {
                        fs.nodeToJunctionRoot[nid] = nid;
                        fs.junctionColumns[nid] = { nid };  // cap: lateral column starts at surface
                    } else {
                        fs.nodeToJunctionRoot[nid] = nid;
                        int step = nextSkip ? 1 : -1;       // walk into the no-BL run
                        double acc = 0.0; int cur = i;
                        while (true) {
                            int nxt = (cur + step + n_init) % n_init;
                            if (!m_mesh.nodes[boundaryNodeIds[nxt]].skipBL) break;
                            double L = (fs.pos_init[nxt] - fs.pos_init[cur]).length();
                            if (acc + L >= D_total * junctionMult[i]) break;   // nxt is at/beyond the slide end
                            acc += L;
                            fs.absorbedNoBLNodes.insert(boundaryNodeIds[nxt]);
                            cur = nxt;
                        }
                    }
                }
            }
            if (fs.bl.blJunctionMethod == 0 && taperScale[i] < 1.0 - 1e-9) {
                double base = fs.nodeStepMultipliers.count(nid) ? fs.nodeStepMultipliers[nid] : 1.0;
                fs.nodeStepMultipliers[nid] = base * taperScale[i];
            }
            if (juncDebug && fs.bl.blJunctionMethod == 0 && (isJunction[i] || taperScale[i] < 0.999))
                std::cerr << "[JUNC] pos(" << fs.pos_init[i].x << "," << fs.pos_init[i].y << ")"
                          << (isJunction[i] ? " JUNCTION" : " taper")
                          << " taper=" << taperScale[i]
                          << " mult=" << (fs.nodeStepMultipliers.count(nid) ? fs.nodeStepMultipliers[nid] : 1.0)
                          << " dir(" << fs.nodeDirections[nid].x << "," << fs.nodeDirections[nid].y << ")"
                          << std::endl;
        }
        fronts.push_back(fs);
    }
    if (nJuncCap > 0)
        std::cout << "  - BL/no-BL junctions   : " << nJuncCap
                  << (m_config.blJunctionMethod == 0 ? " tapered to zero (collapsing prisms)\n"
                                                     : " handled (4-case angle-driven)\n");

    // Each front carries its own thickness schedule (fs.currentH advanced with
    // its own growth rate), so the loop runs for the deepest front's layer count
    // and the returned outer thickness is the largest last-layer height across
    // fronts (it drives the far-field starting size).
    double lastH = m_config.blInitialThickness;
    int totalLayers = 0;
    for (const auto& fs : fronts)
        totalLayers = std::max(totalLayers, fs.bl.blLayers + fs.nTrans);
    (void)maxNTrans;
    const bool stdoutIsTty = HYBMESH_ISATTY(HYBMESH_FILENO(stdout)) != 0;
    std::cout << "Step: Generating " << totalLayers << " boundary layers..." << std::endl;
    for (int layer = 0; layer < totalLayers; ++layer) {

        // --- 1. 候選位置預算 (Candidate Phase) ---
        struct CandidateNode {
            int frontIdx;
            int parentNodeId;
            Point2D pos;
            Vector2D dir;
            double multiplier;
            bool isParaCenter = false;
            RayInfo rayInfo;
        };
        std::vector<std::vector<CandidateNode>> allCandidates(fronts.size());

        for (int fIdx = 0; fIdx < (int)fronts.size(); ++fIdx) {
            auto& fs = fronts[fIdx];
            if (layer >= fs.bl.blLayers + fs.nTrans) continue;
            double currentH = fs.currentH;  // this front's thickness for this layer

            int n = (int)fs.activeFront.size();
            std::vector<Vector2D> n1_list(n), n2_list(n);
            std::vector<bool> isConvexList(n, false);
            std::vector<bool> useParaList(n, false);
            std::vector<bool> useSplitParaList(n, false);
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
                if (exteriorAngle > fs.bl.blConvexAngleThreshold) {
                    isConvexList[i] = true;
                    if (fs.bl.blConvexMethod == 2) {
                        if (exteriorAngle <= fs.bl.blParaFallbackAngle) {
                            useParaList[i] = true;
                        } else {
                            useSplitParaList[i] = true;
                        }
                    }
                }
            }

            for (int i = 0; i < n; ++i) {
                int nodeId = fs.activeFront[i];
                // isFrozen: collision-retreat pin. skipBL: per-segment BL disabled
                // on this node (.meta grow=0) — grow no candidate either way.
                if (m_mesh.nodes[nodeId].isFrozen || m_mesh.nodes[nodeId].skipBL) continue;

                double mult = fs.nodeStepMultipliers.count(nodeId) ? fs.nodeStepMultipliers[nodeId] : 1.0;
                bool shouldSplit = false;
                bool localUsePara = false;
                bool localUseSplitPara = false;
                RayInfo inheritedRay = fs.rayInfoMap.count(nodeId) ? fs.rayInfoMap[nodeId] : RayInfo();
                
                if (fs.bl.blConvexMethod == 2) {
                    if (layer == 0) {
                        shouldSplit = isConvexList[i];
                        localUsePara = useParaList[i];
                        localUseSplitPara = useSplitParaList[i];
                    } else {
                        // Restore recursive splitting: Center nodes split again
                        shouldSplit = fs.paraCenterNodes.count(nodeId);
                        localUsePara = shouldSplit;
                    }
                } else {
                    shouldSplit = (layer == 0 && isConvexList[i]);
                    localUsePara = false;
                }

                // BL/no-BL junction cap: force plain single-ray growth along the
                // BL edge's own normal (direction preset in fs.nodeDirections at
                // init), overriding any fan/parallelogram split so the BL's
                // lateral cap stays a clean perpendicular face across all layers.
                if (fs.junctionCapNodes.count(nodeId)) {
                    shouldSplit = false;
                    localUsePara = false;
                    localUseSplitPara = false;
                }

                if (shouldSplit) {
                    int rootId = (layer == 0) ? nodeId : inheritedRay.rootNodeId;
                    if (localUsePara) {
                        // Parallelogram Strategy: Spawn 3 nodes (Left, Center, Right)
                        Vector2D d_p = n1_list[i];
                        Vector2D d_n = n2_list[i];
                        double dot_prod = std::max(-0.999, d_p.x * d_n.x + d_p.y * d_n.y);
                        double m = 1.0 / (1.0 + dot_prod);
                        Vector2D d_c = (d_p + d_n) * m;
                        double diagLen = d_c.length();
                        
                        RayRole centerRole = (inheritedRay.role == RayRole::ML || inheritedRay.role == RayRole::MR) ? inheritedRay.role : RayRole::Center;
                        RayInfo rL = {RayRole::Left, d_p, 1.0, rootId};
                        RayInfo rC = {centerRole, d_c.normalized(), diagLen, rootId};
                        RayInfo rR = {RayRole::Right, d_n, 1.0, rootId};

                        allCandidates[fIdx].push_back({fIdx, nodeId, currentPos[i] + d_p * currentH, d_p, 1.0, false, rL});
                        allCandidates[fIdx].push_back({fIdx, nodeId, currentPos[i] + d_c * currentH, d_c.normalized(), diagLen, true, rC});
                        allCandidates[fIdx].push_back({fIdx, nodeId, currentPos[i] + d_n * currentH, d_n, 1.0, false, rR});
                    } else if (localUseSplitPara) {
                        // Double (Split) Parallelogram Strategy (Only at layer 0)
                        Vector2D d_p = n1_list[i];
                        Vector2D d_n = n2_list[i];
                        
                        double a1 = std::atan2(d_p.y, d_p.x), a2 = std::atan2(d_n.y, d_n.x);
                        if (fs.growthSign > 0) { while (a2 > a1) a2 -= 2*M_PI; } else { while (a2 < a1) a2 += 2*M_PI; }
                        double angle = (a1 + a2) / 2.0;
                        Vector2D d_b = {std::cos(angle), std::sin(angle)};
                        
                        double dot1 = std::max(-0.999, d_p.x * d_b.x + d_p.y * d_b.y);
                        double m1 = 1.0 / (1.0 + dot1);
                        Vector2D d_ML = (d_p + d_b) * m1;
                        
                        double dot2 = std::max(-0.999, d_b.x * d_n.x + d_b.y * d_n.y);
                        double m2 = 1.0 / (1.0 + dot2);
                        Vector2D d_MR = (d_b + d_n) * m2;

                        RayInfo rL = {RayRole::Left, d_p, 1.0, rootId};
                        RayInfo rML = {RayRole::ML, d_ML.normalized(), d_ML.length(), rootId};
                        RayInfo rB = {RayRole::Bisector, d_b, 1.0, rootId};
                        RayInfo rMR = {RayRole::MR, d_MR.normalized(), d_MR.length(), rootId};
                        RayInfo rR = {RayRole::Right, d_n, 1.0, rootId};
                        
                        allCandidates[fIdx].push_back({fIdx, nodeId, currentPos[i] + d_p * currentH, d_p, 1.0, false, rL});
                        allCandidates[fIdx].push_back({fIdx, nodeId, currentPos[i] + d_ML * currentH, d_ML.normalized(), d_ML.length(), true, rML});
                        allCandidates[fIdx].push_back({fIdx, nodeId, currentPos[i] + d_b * currentH, d_b, 1.0, false, rB});
                        allCandidates[fIdx].push_back({fIdx, nodeId, currentPos[i] + d_MR * currentH, d_MR.normalized(), d_MR.length(), true, rMR});
                        allCandidates[fIdx].push_back({fIdx, nodeId, currentPos[i] + d_n * currentH, d_n, 1.0, false, rR});
                    } else if (layer == 0) {
                        // Fan Strategy (Only at layer 0)
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
                            allCandidates[fIdx].push_back({fIdx, nodeId, currentPos[i] + nk * (currentH * local_m), nk, local_m, false, {RayRole::None, nk, local_m, rootId}});
                        }
                    } else {
                        // Fallback for Fan at layer > 0
                        Vector2D dir = fs.nodeDirections.count(nodeId) ? fs.nodeDirections[nodeId] : (n1_list[i] + n2_list[i]).normalized();
                        double mult = fs.nodeStepMultipliers.count(nodeId) ? fs.nodeStepMultipliers[nodeId] : 1.0;
                        allCandidates[fIdx].push_back({fIdx, nodeId, currentPos[i] + dir * (currentH * mult), dir, mult, false, {RayRole::None, dir, mult, rootId}});
                    }
                } else {
                    // Regular node growth or continued ray growth for split nodes
                    Vector2D dir = inheritedRay.role != RayRole::None ? inheritedRay.direction : 
                                   (fs.nodeDirections.count(nodeId) ? fs.nodeDirections[nodeId] : (n1_list[i] + n2_list[i]).normalized());
                    int rootId = (inheritedRay.role != RayRole::None) ? inheritedRay.rootNodeId : -1;
                    
                    allCandidates[fIdx].push_back({fIdx, nodeId, currentPos[i] + dir * (currentH * mult), dir, mult, false, {inheritedRay.role, dir, mult, rootId}});
                }
            }
        }

        // --- 2. Collision Detection & Retreat Phase ---
        std::set<int> currentLayerNodesToFreeze;
        if (m_config.enableCollisionDetection) {
            std::set<int> currentAllFrontsSet;
            for (const auto& fs : fronts) currentAllFrontsSet.insert(fs.activeFront.begin(), fs.activeFront.end());

            for (int fIdx = 0; fIdx < (int)fronts.size(); ++fIdx) {
                // Each front's proximity threshold is its own current thickness.
                double th = fronts[fIdx].currentH;
                for (auto& cand : allCandidates[fIdx]) {
                    // A. 候選點 vs 已有節點
                    if (checkCollision(cand.pos, th, currentAllFrontsSet, fronts[fIdx].geomId)) {
                        currentLayerNodesToFreeze.insert(cand.parentNodeId);
                    }
                    // B. 候選點 vs 其他幾何候選點 (use the larger of the two fronts'
                    //    thicknesses so either front's cell size can trigger a freeze)
                    for (int fIdx2 = fIdx + 1; fIdx2 < (int)fronts.size(); ++fIdx2) {
                        if (fronts[fIdx].geomId == fronts[fIdx2].geomId) continue;
                        double th2 = std::max(th, fronts[fIdx2].currentH);
                        for (auto& cand2 : allCandidates[fIdx2]) {
                            if ((cand.pos - cand2.pos).lengthSq() < th2 * th2) {
                                currentLayerNodesToFreeze.insert(cand.parentNodeId);
                                currentLayerNodesToFreeze.insert(cand2.parentNodeId);
                            }
                        }
                    }
                }
            }
        }

        // --- 3. 提交階段 (Commit Phase) ---
        for (int fIdx = 0; fIdx < (int)fronts.size(); ++fIdx) {
            auto& fs = fronts[fIdx];
            if (layer >= fs.bl.blLayers + fs.nTrans) continue;

            int n = (int)fs.activeFront.size();
            std::vector<int> nextFront;
            std::vector<std::vector<int>> p2c(n);

            for (int i = 0; i < n; ++i) {
                int nodeId = fs.activeFront[i];
                // Per-segment BL disabled: keep the node pinned on the surface and
                // grow no child. Marked frozen so the quad-strip below skips the
                // (degenerate) elements adjacent to it — this is intentional, so
                // unlike a collision retreat it never throws on proximity. The BL
                // simply tapers to zero here and the far-field mesher fills the gap.
                if (m_mesh.nodes[nodeId].skipBL) {
                    m_mesh.nodes[nodeId].isFrozen = true;
                    nextFront.push_back(nodeId);
                    p2c[i].push_back(nodeId);
                    continue;
                }
                if (m_mesh.nodes[nodeId].isFrozen || currentLayerNodesToFreeze.count(nodeId)) {
                    m_mesh.nodes[nodeId].isFrozen = true;
                    nextFront.push_back(nodeId);
                    p2c[i].push_back(nodeId);

                    if (checkCollision(m_mesh.nodes[nodeId].pos, fs.bl.blInitialThickness, {nodeId}, fs.geomId)) {
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
                        if (cand.isParaCenter) fs.paraCenterNodes.insert(newId);
                        
                        // 儲存射線資訊與分組
                        if (cand.rayInfo.role != RayRole::None) {
                            fs.rayInfoMap[newId] = cand.rayInfo;
                            int root = cand.rayInfo.rootNodeId;
                            if (fs.blParaGroups[root].size() <= (size_t)layer) {
                                fs.blParaGroups[root].resize(layer + 1);
                            }
                            fs.blParaGroups[root][layer].push_back(newId);
                        }
                    }
                }
                
                // 4-case junction: extend this node's lateral column (single-ray
                // growth). nodeToJunctionRoot maps any column node -> its root; cap
                // junctions (cases 2/3/4) also accumulate the ordered column in
                // junctionColumns for far-field emission. Case-1 (slide) roots are
                // tracked too (for the stitch-suppression test) but keep no column.
                if (fs.nodeToJunctionRoot.count(nodeId) && p2c[i].size() == 1) {
                    int root = fs.nodeToJunctionRoot[nodeId];
                    int child = p2c[i][0];
                    fs.nodeToJunctionRoot[child] = root;
                    auto it = fs.junctionColumns.find(root);
                    if (it != fs.junctionColumns.end()) it->second.push_back(child);
                }

                if (p2c[i].size() > 1) {
                    for (int k = 0; k < (int)p2c[i].size() - 1; ++k) {
                        m_mesh.addElement({nodeId, p2c[i][k+1], p2c[i][k]});
                    }
                }
            }

            for (int i = 0; i < n; ++i) {
                int i_next = (i + 1) % n;
                // Guard: back()/front() on an empty vector is UB. A node can
                // produce no child (e.g. skipBL, or a collision-frozen node), so
                // skip stitching this pair if either side has no children.
                if (p2c[i].empty() || p2c[i_next].empty()) continue;

                // 4-case scheme: suppress the wedge element between a no-BL (skipBL)
                // node and an adjacent BL/no-BL junction column. Case 1 it would be a
                // degenerate collinear triangle (the slide column lies on the neighbour
                // edge); cases 2/3/4 the wedge to the neighbour edge is filled by
                // far-field triangles instead (the column's exposed lateral edges are
                // emitted as inner-boundary constraints in the final ring).
                if (fs.bl.blJunctionMethod == 1) {
                    bool i_skip    = m_mesh.nodes[fs.activeFront[i]].skipBL;
                    bool next_skip = m_mesh.nodes[fs.activeFront[i_next]].skipBL;
                    bool i_junc    = fs.nodeToJunctionRoot.count(fs.activeFront[i]) > 0;
                    bool next_junc = fs.nodeToJunctionRoot.count(fs.activeFront[i_next]) > 0;
                    if ((i_skip && next_junc) || (next_skip && i_junc)) continue;
                }

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

            // Track the largest last-layer thickness across fronts, then advance
            // this front's own thickness for the next layer (core growth rate
            // within the BL, transition growth rate beyond it).
            lastH = std::max(lastH, fs.currentH);
            if (layer < fs.bl.blLayers - 1) fs.currentH *= fs.bl.blGrowthRate;
            else fs.currentH *= fs.bl.blTransitionGrowthRate;
        }
        if (stdoutIsTty) {
            // Interactive: overwrite in place with a carriage return.
            std::cout << "\r  - Boundary Layer progress: " << layer + 1 << " / "
                      << totalLayers << " complete." << std::flush;
        } else {
            // Piped / CI / GUI: emit a periodic newline-terminated line (first,
            // last, and every 10th layer) so logs stay readable without \r noise.
            if (layer == 0 || layer + 1 == totalLayers || (layer + 1) % 10 == 0)
                std::cout << "  - Boundary Layer progress: " << layer + 1 << " / "
                          << totalLayers << " complete." << std::endl;
        }
    }
    if (stdoutIsTty) std::cout << std::endl;

    // --- 4. Final Geometric Validation (Pre-Gmsh) ---
    std::cout << "Step: Validating final boundary layer fronts before Gmsh..." << std::endl;
    // Ordered boundary ring per front = the closed loop handed to the far-field
    // mesher as this geometry's inner "hole". It follows the outer BL front over BL
    // runs, DESCENDS / ASCENDS the lateral cap column at each 4-case cap junction
    // (cases 2/3/4 — so the wedge between the cap and the no-BL neighbour edge is
    // triangulated by the far field), traces the surface over no-BL runs, and drops
    // the case-1 (slide) absorbed neighbour nodes so the boundary resumes along the
    // neighbour edge beyond the slide. With no junctions it equals activeFront, so a
    // normal geometry is bit-for-bit unchanged. Used for BOTH the validation below
    // and the far-field edge emission so they stay consistent.
    std::vector<std::vector<int>> finalFronts(fronts.size());
    for (size_t fi = 0; fi < fronts.size(); ++fi) {
        const auto& fsr = fronts[fi];
        const auto& af  = fsr.activeFront;
        int N = (int)af.size();
        std::map<int,int> capOuterToRoot;   // cap-junction outer node -> root (column = [surface,...,outer])
        for (const auto& kv : fsr.junctionColumns)
            if (!kv.second.empty()) capOuterToRoot[kv.second.back()] = kv.first;
        auto absorbed = [&](int id){ return fsr.absorbedNoBLNodes.count(id) > 0; };
        auto isSkip   = [&](int id){ return m_mesh.nodes[id].skipBL; };
        auto nbrNonAbsorbed = [&](int k, int dir){
            for (int s = 1; s <= N; ++s) {
                int idx = ((k + dir * s) % N + N) % N;
                if (!absorbed(af[idx])) return af[idx];
            }
            return af[k];
        };
        auto& ring = finalFronts[fi];
        for (int k = 0; k < N; ++k) {
            int id = af[k];
            if (absorbed(id)) continue;
            auto cj = capOuterToRoot.find(id);
            if (cj != capOuterToRoot.end()) {
                const auto& col = fsr.junctionColumns.at(cj->second);   // [surface, ..., outer=id]
                bool nextSkip = isSkip(nbrNonAbsorbed(k, +1));
                bool prevSkip = isSkip(nbrNonAbsorbed(k, -1));
                if (nextSkip && !prevSkip) {
                    for (int m = (int)col.size() - 1; m >= 0; --m) ring.push_back(col[m]);   // outer -> surface
                } else if (prevSkip && !nextSkip) {
                    for (int m = 0; m < (int)col.size(); ++m) ring.push_back(col[m]);         // surface -> outer
                } else {
                    ring.push_back(id);   // fallback (a cap junction always has one no-BL neighbour)
                }
            } else {
                ring.push_back(id);
            }
        }
    }
    for (int i = 0; i < (int)fronts.size(); ++i) {
        const auto& fs = fronts[i];
        const auto& ring = finalFronts[i];
        int nNodes = (int)ring.size();
        if (nNodes < 3) continue;

        // A. Self-intersection check
        for (int j = 0; j < nNodes; ++j) {
            Point2D a = m_mesh.nodes[ring[j]].pos;
            Point2D b = m_mesh.nodes[ring[(j + 1) % nNodes]].pos;

            // Check against domain boundary
            if (a.x < m_config.xMin || a.x > m_config.xMax || a.y < m_config.yMin || a.y > m_config.yMax) {
                throw std::runtime_error("Error: Boundary layer at Geometry " + std::to_string(fs.geomId) + " exceeded domain boundaries.");
            }

            for (int k = j + 2; k < nNodes; ++k) {
                if ((k + 1) % nNodes == j) continue; // Skip adjacent edges
                Point2D c = m_mesh.nodes[ring[k]].pos;
                Point2D d = m_mesh.nodes[ring[(k + 1) % nNodes]].pos;

                if (segmentsIntersect(a, b, c, d)) {
                    Point2D pt = getIntersectionPoint(a, b, c, d);
                    throw std::runtime_error(
                        "Error: Self-intersection detected in the final front of Geometry "
                        + std::to_string(fs.geomId) + " at point ("
                        + std::to_string(pt.x) + ", " + std::to_string(pt.y) + "). "
                        "The boundary layer is too thick for the local geometry there "
                        "(fronts collide) — reduce BL_LAYERS / BL_INITIAL_THICKNESS / "
                        "BL_GROWTH_RATE, or refine the surface, so the total BL height "
                        "fits the feature/corner clearance. This is a geometry-vs-BL-size "
                        "issue, not the no-BL junction scheme (a BL sized to the geometry "
                        "keeps a constant first-layer height up to the junction).");
                }
            }
        }

        // B. Cross-geometry intersection check
        for (int j = i + 1; j < (int)fronts.size(); ++j) {
            const auto& ring2 = finalFronts[j];
            int nNodes2 = (int)ring2.size();
            for (int k1 = 0; k1 < nNodes; ++k1) {
                Point2D a = m_mesh.nodes[ring[k1]].pos;
                Point2D b = m_mesh.nodes[ring[(k1 + 1) % nNodes]].pos;
                for (int k2 = 0; k2 < nNodes2; ++k2) {
                    Point2D c = m_mesh.nodes[ring2[k2]].pos;
                    Point2D d = m_mesh.nodes[ring2[(k2 + 1) % nNodes2]].pos;
                    if (segmentsIntersect(a, b, c, d)) {
                        Point2D pt = getIntersectionPoint(a, b, c, d);
                        throw std::runtime_error("Error: Intersection detected between Geometry " + std::to_string(fs.geomId) + " and Geometry " + std::to_string(fronts[j].geomId) + " at the final front at point (" + std::to_string(pt.x) + ", " + std::to_string(pt.y) + ").");
                    }
                }
            }
        }
    }

    // --- 5. Global Transverse Balancing (Post-processing) ---
    // Adjust node positions to ensure even segment widths across ALL layers.
    // Anchor points are identified by their RayRole to ensure correct handling of 3-point vs 5-point strategies.
    std::cout << "Step: Applying Global Transverse Balancing to Parallelogram regions..." << std::endl;
    for (auto& fs : fronts) {
        for (auto& group : fs.blParaGroups) {
            auto& layers = group.second;

            for (size_t l = 0; l < layers.size(); ++l) {
                auto& nodeIds = layers[l];
                if (nodeIds.size() < 3) continue;

                // Identify anchors by role
                int iL = 0, iR = (int)nodeIds.size() - 1;
                int iC = -1, iML = -1, iB = -1, iMR = -1;

                for (int i = 0; i < (int)nodeIds.size(); ++i) {
                    if (!fs.rayInfoMap.count(nodeIds[i])) continue;
                    RayRole role = fs.rayInfoMap[nodeIds[i]].role;
                    if (role == RayRole::Center) iC = i;
                    else if (role == RayRole::ML) iML = i;
                    else if (role == RayRole::Bisector) iB = i;
                    else if (role == RayRole::MR) iMR = i;
                }

                auto balance = [&](int start, int end) {
                    if (start < 0 || end < 0 || start >= end) return;
                    Point2D sPos = m_mesh.nodes[nodeIds[start]].pos;
                    Point2D ePos = m_mesh.nodes[nodeIds[end]].pos;
                    for (int j = start + 1; j < end; ++j) {
                        m_mesh.nodes[nodeIds[j]].pos = sPos + (ePos - sPos) * ((double)(j - start) / (double)(end - start));
                    }
                };

                if (iB >= 0 && iML >= 0 && iMR >= 0) {
                    // Split 5-anchor case: Balance across 4 segments
                    balance(iL, iML);
                    balance(iML, iB);
                    balance(iB, iMR);
                    balance(iMR, iR);
                } else if (iC >= 0) {
                    // Standard 3-anchor case: Balance across 2 segments
                    balance(iL, iC);
                    balance(iC, iR);
                } else {
                    // Fallback: simple linear distribution across the whole layer
                    balance(iL, iR);
                }
            }
        }
    }

    // Emit the far-field inner-boundary edges from the ordered boundary ring built
    // above (outer front + lateral cap columns + surface runs, absorbed slide nodes
    // dropped). The Gmsh side chains these into the hole loop; the cap columns become
    // constraints so the wedge to each no-BL neighbour edge is filled with triangles.
    for (const auto& ring : finalFronts) {
        int nFinal = (int)ring.size();
        for (int i = 0; i < nFinal; ++i) {
            int a = ring[i], b = ring[(i + 1) % nFinal];
            if (a == b) continue;
            m_mesh.addEdge(a, b);
            // Carry the per-segment BC tag onto the emitted far-field boundary
            // edge so a NO-BL surface run keeps its inlet/outlet/wall label after
            // Gmsh subdivides it. Without this the edge is emitted with an empty
            // bcTag, is excluded from collectBcRefSegs(), and after subdivision the
            // new nodes fall through classifyBoundaryBc() to the wall default —
            // silently mislabelling e.g. a no-BL left/right boundary that should be
            // inlet/outlet. Only original consecutive surface pairs (the no-BL runs)
            // are present in boundaryEdgeBc; BL outer-front and lateral-cap edges
            // have no entry and stay untagged (they are the BL/triangle interface or
            // a free cap, not a domain boundary). Mirrors addTaggedLoop's edge tag.
            auto key = std::make_pair(std::min(a, b), std::max(a, b));
            auto it = m_mesh.boundaryEdgeBc.find(key);
            if (it != m_mesh.boundaryEdgeBc.end() && !it->second.empty()) {
                m_mesh.edges.back().bcTag = it->second;
                auto sit = m_mesh.boundaryEdgeSeg.find(key);
                if (sit != m_mesh.boundaryEdgeSeg.end())
                    m_mesh.edges.back().segKey = sit->second;
            }
        }
    }
    return lastH;
}

