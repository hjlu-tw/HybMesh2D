#include "Mesh.hpp"
#include <fstream>
#include <iostream>
#include <gmsh.h>
#include <map>
#include <set>
#include <iomanip>
#include <algorithm>
#include <array>
#include <thread>
#include <exception>

#ifdef HAVE_CGNS
#include <cgnslib.h>
namespace {
// Map a user BC string to the closest CGNS BCType_t. The user's original name
// is always preserved as the BC node name; this only sets the typed enum so
// CGNS-aware solvers can reason about it. Unknown names fall back to BCGeneral.
CGNS_ENUMT(BCType_t) mapCgnsBcType(const std::string& n) {
    if (n == "wall" || n == "movingwall") return CGNS_ENUMV(BCWall);
    if (n == "inlet")    return CGNS_ENUMV(BCInflow);
    if (n == "outlet")   return CGNS_ENUMV(BCOutflow);
    if (n == "symmetry") return CGNS_ENUMV(BCSymmetryPlane);
    if (n == "farfield") return CGNS_ENUMV(BCFarfield);
    return CGNS_ENUMV(BCGeneral);
}
} // namespace
#endif

namespace {
// True if p lies on segment a-b (within eps of the line and inside its span).
// Used to attach a domain-boundary edge's BC to the (possibly Gmsh-subdivided)
// mesh edges that fall on it — a generalization of the axis-aligned x≈xMin test.
bool pointOnSegment(const Point2D& p, const Point2D& a, const Point2D& b,
                    double eps = 1e-5) {
    double abx = b.x - a.x, aby = b.y - a.y;
    double len2 = abx * abx + aby * aby;
    if (len2 < 1e-18) {
        double dx0 = p.x - a.x, dy0 = p.y - a.y;
        return (dx0 * dx0 + dy0 * dy0) < eps * eps;
    }
    double t = ((p.x - a.x) * abx + (p.y - a.y) * aby) / len2;
    if (t < -eps || t > 1.0 + eps) return false;
    double dx = p.x - (a.x + t * abx), dy = p.y - (a.y + t * aby);
    return (dx * dx + dy * dy) < eps * eps;
}
} // namespace

std::vector<Mesh::BcRefSeg> Mesh::collectBcRefSegs() const {
    std::vector<BcRefSeg> refs;
    for (const auto& e : edges) {
        if (e.bcTag.empty()) continue;
        refs.push_back({nodes[e.v1].pos, nodes[e.v2].pos, e.bcTag});
    }
    return refs;
}

std::string Mesh::classifyBoundaryBc(int v1, int v2,
                                     const std::vector<BcRefSeg>& refs,
                                     const Config& config) const {
    const Point2D& p1 = nodes[v1].pos;
    const Point2D& p2 = nodes[v2].pos;

    // 1. Domain / far-field reference segment (rectangle side or polygon edge):
    //    generalizes the legacy axis (x≈xMin …) classification to any shape.
    //    For external flow the box/outline is always tagged, so this catches every
    //    far-field edge; for internal flow there are no such segments.
    for (const auto& r : refs) {
        if (pointOnSegment(p1, r.a, r.b) && pointOnSegment(p2, r.a, r.b))
            return r.bc;
    }

    // 2. Geometry per-segment tag carried on the nodes (both endpoints agree).
    if (!nodes[v1].bcTag.empty() && nodes[v1].bcTag == nodes[v2].bcTag)
        return nodes[v1].bcTag;

    // 3. Default geometry / wall BC (untagged geometry surface, internal-flow wall).
    return config.bcGeom;
}

void Mesh::addNode(Point2D p, NodeType type) {
    int id = static_cast<int>(nodes.size());
    Node n;
    n.pos = p;
    n.type = type;
    n.id = id;
    n.geomId = -1;
    n.isFrozen = false;
    nodes.push_back(n);
}

void Mesh::smoothMesh(int iters) {
    if (iters <= 0 || nodes.empty()) return;

    // 1. Build adjacency
    std::vector<std::set<int>> adj(nodes.size());
    for (const auto& el : elements) {
        for (size_t i = 0; i < el.nodeIds.size(); ++i) {
            int u = el.nodeIds[i];
            int v = el.nodeIds[(i + 1) % el.nodeIds.size()];
            adj[u].insert(v);
            adj[v].insert(u);
        }
    }

    // 2. Identify movable nodes (Collision-based Local Smoothing)
    std::set<int> movable;
    std::set<int> currentFront;
    
    for (const auto& node : nodes) {
        if (node.isFrozen) {
            currentFront.insert(node.id);
        }
    }

    if (currentFront.empty()) {
        std::cout << "Step: Local smoothing - No collision detected (no frozen nodes). Skipping." << std::endl;
        return;
    }

    std::set<int> allAffected = currentFront;
    // BFS to expand the affected region (e.g., 5 steps)
    for (int step = 0; step < 5; ++step) {
        std::set<int> nextFront;
        for (int u : currentFront) {
            for (int v : adj[u]) {
                if (allAffected.find(v) == allAffected.end()) {
                    allAffected.insert(v);
                    nextFront.insert(v);
                }
            }
        }
        currentFront = nextFront;
        if (currentFront.empty()) break;
    }

    for (int id : allAffected) {
        // Only move BoundaryLayer or Interior nodes. Protect Boundary nodes.
        if (nodes[id].type != NodeType::Boundary) {
            movable.insert(id);
        }
    }

    if (movable.empty()) return;

    std::cout << "Step: Local smoothing - " << movable.size() << " nodes identified near collision zones. Iterations: " << iters << std::endl;

    // 3. Laplacian Smoothing
    for (int iter = 0; iter < iters; ++iter) {
        std::vector<Point2D> nextPos(nodes.size());
        for (int id : movable) {
            Point2D sum = {0, 0};
            int count = 0;
            for (int neighbor : adj[id]) {
                sum.x += nodes[neighbor].pos.x;
                sum.y += nodes[neighbor].pos.y;
                count++;
            }
            if (count > 0) {
                nextPos[id] = {sum.x / count, sum.y / count};
            } else {
                nextPos[id] = nodes[id].pos;
            }
        }
        // Update positions
        for (int id : movable) {
            nodes[id].pos = nextPos[id];
        }
    }
}

void Mesh::addEdge(int v1, int v2) {
    edges.push_back({v1, v2});
}

void Mesh::addElement(const std::vector<int>& ids) {
    elements.push_back({ids});
}

void Mesh::generateCartesianMesh(double xMin, double xMax, double yMin, double yMax, double ds) {
    int nx = static_cast<int>((xMax - xMin) / ds) + 1;
    int ny = static_cast<int>((yMax - yMin) / ds) + 1;

    double dx = (xMax - xMin) / (nx - 1);
    double dy = (yMax - yMin) / (ny - 1);

    // 生成節點
    int startIdx = static_cast<int>(nodes.size());
    for (int j = 0; j < ny; ++j) {
        for (int i = 0; i < nx; ++i) {
            addNode({xMin + i * dx, yMin + j * dy}, NodeType::Interior);
        }
    }

    // 生成四邊形單元
    for (int j = 0; j < ny - 1; ++j) {
        for (int i = 0; i < nx - 1; ++i) {
            int n1 = startIdx + j * nx + i;
            int n2 = n1 + 1;
            int n3 = n1 + nx + 1;
            int n4 = n1 + nx;
            addElement({n1, n2, n3, n4});
        }
    }
    std::cout << "Cartesian mesh generated: " << nx << "x" << ny << " nodes.\n";
}

void Mesh::exportVTK(const std::string& filename) const {
    std::ofstream ofs(filename);
    if (!ofs) {
        std::cerr << "Error: Could not open file " << filename << " for writing.\n";
        return;
    }

    ofs << "# vtk DataFile Version 3.0\n";
    ofs << "HybMesh2D Export\n";
    ofs << "ASCII\n";
    ofs << "DATASET UNSTRUCTURED_GRID\n";

    // Points
    ofs << "POINTS " << nodes.size() << " double\n";
    for (const auto& node : nodes) {
        ofs << node.pos.x << " " << node.pos.y << " 0.0\n";
    }

    // Cells
    int totalCellData = 0;
    for (const auto& el : elements) {
        totalCellData += (1 + el.nodeIds.size());
    }

    ofs << "CELLS " << elements.size() << " " << totalCellData << "\n";
    for (const auto& el : elements) {
        ofs << el.nodeIds.size();
        for (int id : el.nodeIds) {
            ofs << " " << id;
        }
        ofs << "\n";
    }

    // Cell Types (5 = Triangle, 9 = Quad)
    ofs << "CELL_TYPES " << elements.size() << "\n";
    for (const auto& el : elements) {
        if (el.nodeIds.size() == 3) ofs << "5\n";
        else if (el.nodeIds.size() == 4) ofs << "9\n";
        else ofs << "7\n"; // Polygon
    }

    ofs.close();
    std::cout << "Mesh exported to " << filename << std::endl;
}

void Mesh::exportStarCD(const std::string& baseFilename, const Config& config) const {
    // 1. Export .vrt (Vertices)
    std::string vrtFile = baseFilename + ".vrt";
    std::ofstream vofs(vrtFile);
    if (!vofs) {
        std::cerr << "Error: Could not open " << vrtFile << " for writing.\n";
        return;
    }
    vofs << std::fixed << std::setprecision(8);
    for (size_t i = 0; i < nodes.size(); ++i) {
        // 依據需求：總共 4 欄 (ID, x, y, z)
        vofs << (i + 1) << " " << nodes[i].pos.x << " " << nodes[i].pos.y << " 0.0\n";
    }
    vofs.close();

    // 2. Export .cel (Cells)
    std::string celFile = baseFilename + ".cel";
    std::ofstream cofs(celFile);
    if (!cofs) {
        std::cerr << "Error: Could not open " << celFile << " for writing.\n";
        return;
    }
    int cellCount = 1;
    std::set<std::vector<int>> seenElements;
    for (size_t i = 0; i < elements.size(); ++i) {
        const auto& el = elements[i];
        if (el.nodeIds.size() < 3) continue; // 略過線段元素
        
        // 檢查退化單元 (節點重複)
        std::vector<int> sortedIds = el.nodeIds;
        std::sort(sortedIds.begin(), sortedIds.end());
        bool degenerate = false;
        for (size_t k = 0; k < sortedIds.size() - 1; ++k) {
            if (sortedIds[k] == sortedIds[k+1]) {
                degenerate = true;
                break;
            }
        }
        if (degenerate) continue;

        // 檢查重複單元
        if (seenElements.count(sortedIds)) continue;
        seenElements.insert(sortedIds);

        cofs << cellCount++ << " ";
        if (el.nodeIds.size() == 3) {
            int n0 = el.nodeIds[0], n1 = el.nodeIds[1], n2 = el.nodeIds[2];
            double cross = (nodes[n1].pos.x - nodes[n0].pos.x) * (nodes[n2].pos.y - nodes[n0].pos.y) - 
                           (nodes[n1].pos.y - nodes[n0].pos.y) * (nodes[n2].pos.x - nodes[n0].pos.x);
            if (cross < 0) std::swap(n1, n2);
            // 三角形：ID, v1, v2, v3, v3, 1, 1 (共 7 欄)
            cofs << (n0 + 1) << " " << (n1 + 1) << " " 
                 << (n2 + 1) << " " << (n2 + 1) << " 1 1\n";
        } else if (el.nodeIds.size() == 4) {
            int n0 = el.nodeIds[0], n1 = el.nodeIds[1], n2 = el.nodeIds[2], n3 = el.nodeIds[3];
            double cross = (nodes[n1].pos.x - nodes[n0].pos.x) * (nodes[n2].pos.y - nodes[n0].pos.y) - 
                           (nodes[n1].pos.y - nodes[n0].pos.y) * (nodes[n2].pos.x - nodes[n0].pos.x);
            if (cross < 0) std::swap(n1, n3);
            // 四角形：ID, v1, v2, v3, v4, 1, 1 (共 7 欄)
            cofs << (n0 + 1) << " " << (n1 + 1) << " " 
                 << (n2 + 1) << " " << (n3 + 1) << " 1 1\n";
        }
    }
    cofs.close();

    // 3. Export .bnd (Boundaries)
    std::string bndFile = baseFilename + ".bnd";
    std::ofstream bofs(bndFile);
    if (!bofs) {
        std::cerr << "Error: Could not open " << bndFile << " for writing.\n";
        return;
    }

    // 統計每條邊被 Element 使用的次數，只被使用一次的即為邊界
    std::map<std::pair<int, int>, int> edgeCellCount;
    std::map<std::pair<int, int>, std::pair<int, int>> edgeNodes;
    std::set<std::vector<int>> seenElementsForBnd;
    for (size_t i = 0; i < elements.size(); ++i) {
        const auto& el = elements[i];
        if (el.nodeIds.size() < 3) continue;

        // 檢查退化單元
        std::vector<int> sortedIds = el.nodeIds;
        std::sort(sortedIds.begin(), sortedIds.end());
        bool degenerate = false;
        for (size_t k = 0; k < sortedIds.size() - 1; ++k) {
            if (sortedIds[k] == sortedIds[k+1]) {
                degenerate = true;
                break;
            }
        }
        if (degenerate) continue;

        // 檢查重複單元
        if (seenElementsForBnd.count(sortedIds)) continue;
        seenElementsForBnd.insert(sortedIds);

        int numNodes = static_cast<int>(el.nodeIds.size());
        for (int j = 0; j < numNodes; ++j) {
            int n1 = el.nodeIds[j];
            int n2 = el.nodeIds[(j + 1) % numNodes];
            int vMin = std::min(n1, n2);
            int vMax = std::max(n1, n2);
            edgeCellCount[{vMin, vMax}]++;
            edgeNodes[{vMin, vMax}] = {n1, n2};
        }
    }

    // Boundary edges (used by exactly one cell), classified by their attached BC
    // tag: a domain reference segment wins, else a geometry per-segment Node::bcTag,
    // else the axis/geom fallback. Group ids are assigned per unique BC name in
    // first-appearance order (name-based grouping, like STAR-CCM+/Fluent).
    const std::vector<BcRefSeg> bcRefs = collectBcRefSegs();
    std::map<std::string, int> groupIds;
    int nextGroup = 1;
    int bndCount = 1;
    for (const auto& kv : edgeCellCount) {
        if (kv.second != 1) continue; // 只輸出邊界邊
        int v1 = edgeNodes[kv.first].first;
        int v2 = edgeNodes[kv.first].second;

        std::string bcName = classifyBoundaryBc(v1, v2, bcRefs, config);
        int gid;
        auto git = groupIds.find(bcName);
        if (git == groupIds.end()) { gid = nextGroup++; groupIds[bcName] = gid; }
        else gid = git->second;

        // 格式：bnd編號, v1, v2, 0, 0, groupId, 0, bcName (共 8 欄)
        bofs << bndCount++ << " " << (v1 + 1) << " " << (v2 + 1) << " 0 0 " << gid << " 0 " << bcName << "\n";
    }
    bofs.close();

    std::cout << "StarCD mesh exported to " << baseFilename << " (.vrt, .cel, .bnd)" << std::endl;
}

void Mesh::exportCGNS(const std::string& filename, const Config& config) const {
#ifndef HAVE_CGNS
    (void)config;
    std::cerr << "Warning: CGNS export requested but this build was configured "
                 "without the CGNS library; skipping '" << filename << "'.\n"
                 "         Reinstall CGNS and re-run cmake to enable it.\n";
#else
    // --- 1. Collect valid volume cells, mirroring exportStarCD's filtering
    //        (skip line/degenerate/duplicate elements, enforce CCW winding). ---
    std::vector<std::array<cgsize_t, 3>> tris;
    std::vector<std::array<cgsize_t, 4>> quads;
    std::set<std::vector<int>> seenCells;
    auto degenerate = [](std::vector<int> ids) {
        std::sort(ids.begin(), ids.end());
        for (size_t k = 0; k + 1 < ids.size(); ++k) if (ids[k] == ids[k + 1]) return true;
        return false;
    };
    for (const auto& el : elements) {
        if (el.nodeIds.size() < 3) continue;
        if (degenerate(el.nodeIds)) continue;
        std::vector<int> key = el.nodeIds;
        std::sort(key.begin(), key.end());
        if (!seenCells.insert(key).second) continue;
        if (el.nodeIds.size() == 3) {
            int n0 = el.nodeIds[0], n1 = el.nodeIds[1], n2 = el.nodeIds[2];
            double cr = (nodes[n1].pos.x - nodes[n0].pos.x) * (nodes[n2].pos.y - nodes[n0].pos.y)
                      - (nodes[n1].pos.y - nodes[n0].pos.y) * (nodes[n2].pos.x - nodes[n0].pos.x);
            if (cr < 0) std::swap(n1, n2);
            tris.push_back({(cgsize_t)(n0 + 1), (cgsize_t)(n1 + 1), (cgsize_t)(n2 + 1)});
        } else if (el.nodeIds.size() == 4) {
            int n0 = el.nodeIds[0], n1 = el.nodeIds[1], n2 = el.nodeIds[2], n3 = el.nodeIds[3];
            double cr = (nodes[n1].pos.x - nodes[n0].pos.x) * (nodes[n2].pos.y - nodes[n0].pos.y)
                      - (nodes[n1].pos.y - nodes[n0].pos.y) * (nodes[n2].pos.x - nodes[n0].pos.x);
            if (cr < 0) std::swap(n1, n3);
            quads.push_back({(cgsize_t)(n0 + 1), (cgsize_t)(n1 + 1), (cgsize_t)(n2 + 1), (cgsize_t)(n3 + 1)});
        }
    }
    const cgsize_t nCells = (cgsize_t)(tris.size() + quads.size());

    // --- 2. Group boundary edges (used by exactly one cell) by BC name —
    //        same classification as exportStarCD. ---
    std::map<std::pair<int, int>, int> edgeCount;
    std::map<std::pair<int, int>, std::pair<int, int>> edgeNodes;
    std::set<std::vector<int>> seenForBnd;
    for (const auto& el : elements) {
        if (el.nodeIds.size() < 3) continue;
        if (degenerate(el.nodeIds)) continue;
        std::vector<int> key = el.nodeIds;
        std::sort(key.begin(), key.end());
        if (!seenForBnd.insert(key).second) continue;
        int m = (int)el.nodeIds.size();
        for (int j = 0; j < m; ++j) {
            int a = el.nodeIds[j], b = el.nodeIds[(j + 1) % m];
            int lo = std::min(a, b), hi = std::max(a, b);
            edgeCount[{lo, hi}]++;
            edgeNodes[{lo, hi}] = {a, b};
        }
    }
    std::map<std::string, std::vector<std::pair<int, int>>> bcGroups;
    const std::vector<BcRefSeg> bcRefs = collectBcRefSegs();
    for (const auto& kv : edgeCount) {
        if (kv.second != 1) continue;
        int v1 = edgeNodes[kv.first].first, v2 = edgeNodes[kv.first].second;
        std::string bc = classifyBoundaryBc(v1, v2, bcRefs, config);
        bcGroups[bc].push_back({v1, v2});
    }

    // --- 3. Write the CGNS/HDF5 file: base -> zone -> coords -> element
    //        sections -> boundary edge sections + BC patches. ---
    int fn = 0, B = 0, Z = 0;
    if (cg_open(filename.c_str(), CG_MODE_WRITE, &fn)) {
        std::cerr << "Error: cg_open failed for " << filename << ": " << cg_get_error() << "\n";
        return;
    }
    auto cgChk = [](const char* what, int ier) {
        if (ier) std::cerr << "CGNS warning: " << what << " -> " << cg_get_error() << "\n";
    };
    cgChk("cg_base_write", cg_base_write(fn, "Base", /*cell_dim=*/2, /*phys_dim=*/2, &B));
    cgsize_t zoneSize[3] = {(cgsize_t)nodes.size(), nCells, 0};
    cgChk("cg_zone_write", cg_zone_write(fn, B, "Zone1", zoneSize, CGNS_ENUMV(Unstructured), &Z));

    std::vector<double> X(nodes.size()), Y(nodes.size());
    for (size_t i = 0; i < nodes.size(); ++i) { X[i] = nodes[i].pos.x; Y[i] = nodes[i].pos.y; }
    int ci = 0;
    cgChk("cg_coord_write X", cg_coord_write(fn, B, Z, CGNS_ENUMV(RealDouble), "CoordinateX", X.data(), &ci));
    cgChk("cg_coord_write Y", cg_coord_write(fn, B, Z, CGNS_ENUMV(RealDouble), "CoordinateY", Y.data(), &ci));

    cgsize_t eStart = 1;
    int S = 0;
    if (!tris.empty()) {
        std::vector<cgsize_t> conn;
        conn.reserve(tris.size() * 3);
        for (const auto& t : tris) { conn.push_back(t[0]); conn.push_back(t[1]); conn.push_back(t[2]); }
        cgsize_t eEnd = eStart + (cgsize_t)tris.size() - 1;
        cgChk("cg_section_write TRI_3", cg_section_write(fn, B, Z, "TriElements", CGNS_ENUMV(TRI_3), eStart, eEnd, 0, conn.data(), &S));
        eStart = eEnd + 1;
    }
    if (!quads.empty()) {
        std::vector<cgsize_t> conn;
        conn.reserve(quads.size() * 4);
        for (const auto& q : quads) { conn.push_back(q[0]); conn.push_back(q[1]); conn.push_back(q[2]); conn.push_back(q[3]); }
        cgsize_t eEnd = eStart + (cgsize_t)quads.size() - 1;
        cgChk("cg_section_write QUAD_4", cg_section_write(fn, B, Z, "QuadElements", CGNS_ENUMV(QUAD_4), eStart, eEnd, 0, conn.data(), &S));
        eStart = eEnd + 1;
    }

    // Each BC group becomes a BAR_2 edge section plus a BC_t patch that
    // references that section's element range (GridLocation = EdgeCenter).
    for (const auto& kv : bcGroups) {
        const std::string& bcName = kv.first;
        const auto& edges = kv.second;
        std::vector<cgsize_t> conn;
        conn.reserve(edges.size() * 2);
        for (const auto& e : edges) { conn.push_back((cgsize_t)(e.first + 1)); conn.push_back((cgsize_t)(e.second + 1)); }
        cgsize_t eEnd = eStart + (cgsize_t)edges.size() - 1;
        int sec = 0;
        std::string secName = bcName + "_edges";
        cgChk("cg_section_write BAR_2", cg_section_write(fn, B, Z, secName.c_str(), CGNS_ENUMV(BAR_2), eStart, eEnd, 0, conn.data(), &sec));
        cgsize_t range[2] = {eStart, eEnd};
        int bcIdx = 0;
        cgChk("cg_boco_write", cg_boco_write(fn, B, Z, bcName.c_str(), mapCgnsBcType(bcName), CGNS_ENUMV(PointRange), 2, range, &bcIdx));
        cgChk("cg_boco_gridlocation_write", cg_boco_gridlocation_write(fn, B, Z, bcIdx, CGNS_ENUMV(EdgeCenter)));
        eStart = eEnd + 1;
    }

    cg_close(fn);
    std::cout << "CGNS mesh exported to " << filename << " ("
              << nodes.size() << " nodes, " << nCells << " cells, "
              << bcGroups.size() << " BC patch(es))" << std::endl;
#endif
}

void Mesh::generateFarFieldGmsh(const Config& config, double finalBLThickness,
                                const std::vector<SeedGeom>& seeds) {
    gmsh::initialize();
    gmsh::option::setNumber("General.Terminal", 0); // 關閉 Gmsh 終端輸出

    // Let Gmsh use all available cores for the far-field meshing stage.
    // Mesh.MaxNumThreads* default to 0 (= follow General.NumThreads).
    unsigned int nthreads = std::thread::hardware_concurrency();
    if (nthreads == 0) nthreads = 1;
    gmsh::option::setNumber("General.NumThreads", static_cast<double>(nthreads));
    std::cout << "Step: Gmsh configured to use " << nthreads << " thread(s)." << std::endl;

    gmsh::model::add("FarField");

    auto getCoordKey = [](double x, double y) {
        return std::make_pair((long long)(std::round(x * 1e9)), (long long)(std::round(y * 1e9)));
    };

    // 1. 建立點與線
    std::map<int, int> nodeToGmshTag; 
    std::map<std::pair<long long, long long>, int> coordToGmshTag;

    for (const auto& edge : edges) {
        for (int vid : {edge.v1, edge.v2}) {
            if (nodeToGmshTag.find(vid) == nodeToGmshTag.end()) {
                auto key = getCoordKey(nodes[vid].pos.x, nodes[vid].pos.y);
                if (coordToGmshTag.count(key)) {
                    nodeToGmshTag[vid] = coordToGmshTag[key];
                } else {
                    int tag = gmsh::model::geo::addPoint(nodes[vid].pos.x, nodes[vid].pos.y, 0.0);
                    nodeToGmshTag[vid] = tag;
                    coordToGmshTag[key] = tag;
                }
            }
        }
    }

    std::vector<int> allLines;
    std::vector<Edge> filteredEdges; // 用於後續拓撲分析
    std::vector<double> frontLineTags; // 用於尺寸場的邊界來源

    for (size_t i = 0; i < edges.size(); ++i) {
        int t1 = nodeToGmshTag[edges[i].v1];
        int t2 = nodeToGmshTag[edges[i].v2];
        
        if (t1 == t2) continue; // 跳過零長度邊 (座標重合)

        int tag = gmsh::model::geo::addLine(t1, t2);
        allLines.push_back(tag);
        filteredEdges.push_back(edges[i]);
        
        if (nodes[edges[i].v1].type == NodeType::BoundaryLayer && 
            nodes[edges[i].v2].type == NodeType::BoundaryLayer) {
            frontLineTags.push_back(static_cast<double>(tag));
        }
    }

    // 2. 拓撲分析 (使用過濾後的邊)。同時記錄每個 loop 的節點序列以計算面積。
    struct LoopInfo { int tag; double absArea; };
    std::vector<LoopInfo> loopInfos;
    std::vector<bool> used(allLines.size(), false);
    for (size_t i = 0; i < allLines.size(); ++i) {
        if (used[i]) continue;
        std::vector<int> currentLoopLines;
        std::vector<int> loopNodeSeq;                 // 依序的「本地」節點 id
        currentLoopLines.push_back(allLines[i]);
        used[i] = true;

        int startGmshNode = nodeToGmshTag[filteredEdges[i].v1];
        int currGmshNode = nodeToGmshTag[filteredEdges[i].v2];
        loopNodeSeq.push_back(filteredEdges[i].v1);
        loopNodeSeq.push_back(filteredEdges[i].v2);

        while (currGmshNode != startGmshNode) {
            bool found = false;
            for (size_t k = 0; k < allLines.size(); ++k) {
                if (!used[k]) {
                    int v1_tag = nodeToGmshTag[filteredEdges[k].v1];
                    int v2_tag = nodeToGmshTag[filteredEdges[k].v2];

                    if (v1_tag == currGmshNode) {
                        currentLoopLines.push_back(allLines[k]);
                        currGmshNode = v2_tag;
                        loopNodeSeq.push_back(filteredEdges[k].v2);
                        used[k] = true;
                        found = true;
                        break;
                    }
                    else if (v2_tag == currGmshNode) {
                        currentLoopLines.push_back(-allLines[k]);
                        currGmshNode = v1_tag;
                        loopNodeSeq.push_back(filteredEdges[k].v1);
                        used[k] = true;
                        found = true;
                        break;
                    }
                }
            }
            if (!found) break;
        }
        if (currentLoopLines.size() >= 3 && currGmshNode == startGmshNode) {
            int loopTag = gmsh::model::geo::addCurveLoop(currentLoopLines);
            double area2 = 0.0;                        // shoelace (帶符號 ×2)
            int m = static_cast<int>(loopNodeSeq.size());
            for (int a = 0; a < m; ++a) {
                const Point2D& p1 = nodes[loopNodeSeq[a]].pos;
                const Point2D& p2 = nodes[loopNodeSeq[(a + 1) % m]].pos;
                area2 += (p1.x * p2.y - p2.x * p1.y);
            }
            loopInfos.push_back({loopTag, std::abs(area2) * 0.5});
        }
    }

    // 依 |面積| 由大到小排序：最大 loop 為外邊界置於首位，其餘為洞。這讓任意外框
    // 形狀 (多邊形/圓/扇形) 與內流 (BL 內緣 front 為外圈) 交給 Gmsh 時皆正確。
    std::sort(loopInfos.begin(), loopInfos.end(),
              [](const LoopInfo& a, const LoopInfo& b) { return a.absArea > b.absArea; });
    std::vector<int> loops;
    loops.reserve(loopInfos.size());
    for (const auto& li : loopInfos) loops.push_back(li.tag);

    int surfTag = -1;
    if (!loops.empty()) {
        surfTag = gmsh::model::geo::addPlaneSurface(loops);
    }

    // Seeds: 把種子的點/線加入 geo 模型，供後續 Distance 尺寸場參考。
    // 它們不放進 `loops`，所以既非域邊界也不會被長成邊界層；source 模式為浮動
    // 幾何 (只被尺寸場使用)，embed 模式則於 synchronize 後內嵌進遠場面。
    struct SeedFieldData {
        std::vector<double> curveTags; // gmsh 線 tag (Distance CurvesList)
        std::vector<int> pointTags;    // gmsh 點 tag (單點種子 / embed)
        std::vector<int> lineTags;     // gmsh 線 tag (embed)
        double size;
        double radius;
        double spacing;                // 種子自身的平均點距 (auto size 依此)
        bool embed;
    };
    std::vector<SeedFieldData> seedFieldData;
    for (const auto& seed : seeds) {
        if (seed.points.empty()) continue;
        SeedFieldData sd;
        sd.size = seed.size; sd.radius = seed.radius; sd.embed = seed.embed;
        sd.spacing = 0.0;
        std::vector<int> gpts;
        gpts.reserve(seed.points.size());
        for (const auto& p : seed.points) {
            gpts.push_back(gmsh::model::geo::addPoint(p.x, p.y, 0.0));
        }
        int nseg = static_cast<int>(seed.points.size());
        int limit = seed.closed ? nseg : nseg - 1;
        double spanLen = 0.0; int spanCnt = 0;
        for (int i = 0; i < limit; ++i) {
            int a = gpts[i];
            int b = gpts[(i + 1) % nseg];
            if (a == b) continue;
            int lt = gmsh::model::geo::addLine(a, b);
            sd.lineTags.push_back(lt);
            sd.curveTags.push_back(static_cast<double>(lt));
            spanLen += (seed.points[(i + 1) % nseg] - seed.points[i]).length();
            spanCnt++;
        }
        // 種子自身重採樣後的平均點距，供 auto size 使用 (貼合 surface point 分布)。
        if (spanCnt > 0) sd.spacing = spanLen / (double)spanCnt;
        // 單點種子 (無法連線) 時，改以點本身作為尺寸場來源。
        if (sd.lineTags.empty()) sd.pointTags = gpts;
        seedFieldData.push_back(sd);
    }

    gmsh::model::geo::synchronize();

    // embed 模式：把種子曲線內嵌進遠場面，強制網格節點貼合它 (仍不長邊界層)。
    // 逐一 try/catch：種子若落在邊界層洞內/域外會使 embed 拋例外，此時退化為
    // 純尺寸來源 (尺寸場仍會套用)。
    if (surfTag > 0) {
        for (const auto& sd : seedFieldData) {
            if (!sd.embed) continue;
            try {
                if (!sd.lineTags.empty())
                    gmsh::model::mesh::embed(1, sd.lineTags, 2, surfTag);
                else if (!sd.pointTags.empty())
                    gmsh::model::mesh::embed(0, sd.pointTags, 2, surfTag);
            } catch (const std::exception& e) {
                std::cerr << "Warning: could not embed a refinement seed ("
                          << e.what() << "); using it as a sizing source only." << std::endl;
            }
        }
    }

    // 2.2 局部強制邊界層外緣 1-對-1 對接
    std::vector<double> collisionLineTags;
    double collisionTotalLen = 0.0;
    int collisionCount = 0;

    for (size_t i = 0; i < allLines.size(); ++i) {
        if (nodes[filteredEdges[i].v1].type == NodeType::BoundaryLayer && 
            nodes[filteredEdges[i].v2].type == NodeType::BoundaryLayer) {
            
            gmsh::model::mesh::setTransfiniteCurve(allLines[i], 2);

            // 偵測碰撞區域的邊 (包含至少一個 frozen 節點)
            if (nodes[filteredEdges[i].v1].isFrozen || nodes[filteredEdges[i].v2].isFrozen) {
                collisionLineTags.push_back(static_cast<double>(allLines[i]));
                collisionTotalLen += (nodes[filteredEdges[i].v1].pos - nodes[filteredEdges[i].v2].pos).length();
                collisionCount++;
            }
        }
    }

    // --- 3. 建立尺寸過渡場 ---
    std::cout << "Step: Setting up Gmsh fields..." << std::endl;

    // 3.0 計算基準尺寸 hEnd / hBase。即使沒有邊界層 (frontLineTags 為空、
    //     例如僅有加密種子) 也要先算好，供種子尺寸場的預設值使用。
    double hEnd = config.surfaceSize;
    double hGap = -1.0;
    if (collisionCount > 0) {
        hGap = collisionTotalLen / (double)collisionCount;
        std::cout << "  -> Detected Collision Zone Mesh Size (hGap): " << hGap << std::endl;
    }
    if (config.autoSurfaceSize) {
        double totalLen = 0.0;
        int count = 0;
        for (const auto& edge : edges) {
            if (nodes[edge.v1].type == NodeType::BoundaryLayer &&
                nodes[edge.v2].type == NodeType::BoundaryLayer) {
                totalLen += (nodes[edge.v1].pos - nodes[edge.v2].pos).length();
                count++;
            }
        }
        if (count > 0) {
            hEnd = totalLen / (double)count;
            std::cout << "  -> Final Surface Mesh Size (Auto Avg): " << hEnd << std::endl;
        } else if (finalBLThickness > 0) {
            hEnd = finalBLThickness;
            std::cout << "  -> Final Surface Mesh Size (Fallback to BL height): " << hEnd << std::endl;
        }
    } else {
        std::cout << "  -> Final Surface Mesh Size (Manual): " << hEnd << std::endl;
    }
    // 如果偵測到碰撞區域，優先使用 hGap 作為局部基準
    double hBase = (hGap > 0) ? hGap : hEnd;
    if (hGap > 0) {
        std::cout << "  -> Using hGap (" << hGap << ") as baseline for triangulation near collisions." << std::endl;
    }

    // 收集所有尺寸場，最後取 Min 作為背景尺寸場。
    std::vector<double> sizeFields;

    // 3.1 邊界層距離場 (僅在存在邊界層外緣時)：
    //     Min(farFieldSize, hBase + Max(0, dist - dBuffer) * growthRate)
    if (!frontLineTags.empty()) {
        int fDist = gmsh::model::mesh::field::add("Distance");
        gmsh::model::mesh::field::setNumbers(fDist, "CurvesList", frontLineTags);

        // 建立緩衝區：在 dBuffer 距離內維持 hBase 尺寸，避免 1 個大網格接多個小網格
        double dBuffer = hBase * config.blTransitionBuffer;
        std::string expr = "Min(" + std::to_string(config.farFieldSize) + ", " +
                           std::to_string(hBase) + " + Max(0, F" + std::to_string(fDist) + " - " +
                           std::to_string(dBuffer) + ") * " + std::to_string(config.farFieldGrowthRate) + ")";

        int fFinal = gmsh::model::mesh::field::add("MathEval");
        gmsh::model::mesh::field::setString(fFinal, "F", expr);
        sizeFields.push_back(static_cast<double>(fFinal));
    }

    // 3.2 加密種子尺寸場 (Distance + Threshold)：種子附近維持 effSize，於 effRadius
    //     之外藉 StopAtDistMax 失效，交由邊界層/遠場尺寸接手；多個種子與邊界層場
    //     一併取 Min。effSize / effRadius 未指定時自動推得。
    double seedMinSize = config.farFieldSize;
    for (const auto& sd : seedFieldData) {
        // main.cpp already folded the per-file value and the global default
        // (config.seedSize/seedRadius) into sd.size/sd.radius; here we only do
        // the remaining auto step, so the defaulting isn't split.
        // Auto size follows the seed's own resampled point spacing (surface
        // point distribution), falling back to the local base size only if the
        // seed is a single point / degenerate.
        double effSize = (sd.size > 0) ? sd.size
                        : (sd.spacing > 0 ? sd.spacing : hBase);
        if (effSize <= 0) effSize = config.surfaceSize;
        // Radius is independent of size: an explicit radius is honoured even when
        // the size is auto; only a fully-auto radius derives from the size.
        double effRadius = (sd.radius > 0) ? sd.radius : 100.0 * effSize;

        int fSeedDist = gmsh::model::mesh::field::add("Distance");
        if (!sd.curveTags.empty()) {
            gmsh::model::mesh::field::setNumbers(fSeedDist, "CurvesList", sd.curveTags);
            gmsh::model::mesh::field::setNumber(fSeedDist, "Sampling", 100);
        } else {
            std::vector<double> pts(sd.pointTags.begin(), sd.pointTags.end());
            gmsh::model::mesh::field::setNumbers(fSeedDist, "PointsList", pts);
        }

        int fSeedTh = gmsh::model::mesh::field::add("Threshold");
        gmsh::model::mesh::field::setNumber(fSeedTh, "InField", fSeedDist);
        gmsh::model::mesh::field::setNumber(fSeedTh, "SizeMin", effSize);
        gmsh::model::mesh::field::setNumber(fSeedTh, "SizeMax", config.farFieldSize);
        gmsh::model::mesh::field::setNumber(fSeedTh, "DistMin", 0.0);
        gmsh::model::mesh::field::setNumber(fSeedTh, "DistMax", effRadius);
        gmsh::model::mesh::field::setNumber(fSeedTh, "StopAtDistMax", 1);
        sizeFields.push_back(static_cast<double>(fSeedTh));

        if (effSize < seedMinSize) seedMinSize = effSize;
        std::cout << "  -> Refinement seed: size=" << effSize << ", radius=" << effRadius
                  << (sd.embed ? " (embed)" : " (source)") << std::endl;
    }

    // 3.3 合併所有尺寸場並設定全域尺寸範圍
    if (!sizeFields.empty()) {
        int fMin = gmsh::model::mesh::field::add("Min");
        gmsh::model::mesh::field::setNumbers(fMin, "FieldsList", sizeFields);
        gmsh::model::mesh::field::setAsBackgroundMesh(fMin);

        double meshMin = std::min(std::min(hEnd, config.farFieldSize), seedMinSize);
        gmsh::option::setNumber("Mesh.MeshSizeMin", meshMin);
        gmsh::option::setNumber("Mesh.MeshSizeMax", config.farFieldSize);
    } else {
        gmsh::option::setNumber("Mesh.MeshSizeMin", config.farFieldSize);
        gmsh::option::setNumber("Mesh.MeshSizeMax", config.farFieldSize);
    }

    gmsh::option::setNumber("Mesh.MeshSizeExtendFromBoundary", 0);
    gmsh::option::setNumber("Mesh.MeshSizeFromPoints", 0);
    gmsh::option::setNumber("Mesh.Algorithm", config.gmshAlgorithm); 
    
    if (config.gmshOptimize) {
        gmsh::option::setNumber("Mesh.Optimize", 1);
        gmsh::option::setNumber("Mesh.OptimizeNetgen", 1);
    }
    
    std::cout << "Step: Generating far-field triangle mesh (Gmsh)..." << std::endl;
    gmsh::model::mesh::generate(2);
    std::cout << "Step: Gmsh generation finished. Syncing nodes..." << std::endl;

    std::vector<double> coord, dummy;
    std::vector<std::size_t> nodeTags;
    gmsh::model::mesh::getNodes(nodeTags, coord, dummy);

    // gmsh 節點 tag -> 座標，供三角形連線時按需解析
    std::map<std::size_t, std::pair<double, double>> gmshTagCoord;
    for (size_t i = 0; i < nodeTags.size(); ++i) {
        gmshTagCoord[nodeTags[i]] = {coord[3*i], coord[3*i+1]};
    }

    // 優化：建立座標查找表，把 gmsh 節點對應回既有的邊界/邊界層節點
    std::map<std::pair<long long, long long>, int> coordMap;
    for(auto const& nm : nodeToGmshTag) {
        coordMap[getCoordKey(nodes[nm.first].pos.x, nodes[nm.first].pos.y)] = nm.first;
    }

    // 只建立實際被三角形引用的節點；如此 source 模式下浮動的種子線/點所產生的
    // 1D 網格節點不會混入最終網格。
    std::map<std::size_t, int> gmshToOurNode;
    auto resolveGmshNode = [&](std::size_t gt) -> int {
        auto cached = gmshToOurNode.find(gt);
        if (cached != gmshToOurNode.end()) return cached->second;
        double x = 0.0, y = 0.0;
        auto cit = gmshTagCoord.find(gt);
        if (cit != gmshTagCoord.end()) { x = cit->second.first; y = cit->second.second; }
        auto key = getCoordKey(x, y);
        int id;
        auto it = coordMap.find(key);
        if (it != coordMap.end()) {
            id = it->second;
        } else {
            addNode({x, y}, NodeType::Interior);
            id = nodes.back().id;
            coordMap[key] = id;
        }
        gmshToOurNode[gt] = id;
        return id;
    };

    std::cout << "Step: Syncing elements..." << std::endl;
    std::vector<int> elementTypes;
    std::vector<std::vector<std::size_t>> elementTags, nodeTagsByElement;
    gmsh::model::mesh::getElements(elementTypes, elementTags, nodeTagsByElement, 2);

    for (size_t i = 0; i < elementTypes.size(); ++i) {
        if (elementTypes[i] == 2) { // Triangles
            for (size_t j = 0; j < nodeTagsByElement[i].size(); j += 3) {
                int n1 = resolveGmshNode(nodeTagsByElement[i][j]);
                int n2 = resolveGmshNode(nodeTagsByElement[i][j+1]);
                int n3 = resolveGmshNode(nodeTagsByElement[i][j+2]);
                addElement({n1, n2, n3});
            }
        }
    }

    std::cout << "Step: Finalizing Gmsh..." << std::endl;
    gmsh::finalize();
    std::cout << "Mesh generation completed successfully!" << std::endl;
}
