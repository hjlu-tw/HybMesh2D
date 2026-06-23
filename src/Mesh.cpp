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
    double xMin = 1e9, xMax = -1e9, yMin = 1e9, yMax = -1e9;
    for (size_t i = 0; i < nodes.size(); ++i) {
        // 依據需求：總共 4 欄 (ID, x, y, z)
        vofs << (i + 1) << " " << nodes[i].pos.x << " " << nodes[i].pos.y << " 0.0\n";
        
        if (nodes[i].pos.x < xMin) xMin = nodes[i].pos.x;
        if (nodes[i].pos.x > xMax) xMax = nodes[i].pos.x;
        if (nodes[i].pos.y < yMin) yMin = nodes[i].pos.y;
        if (nodes[i].pos.y > yMax) yMax = nodes[i].pos.y;
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

    int bndCount = 1;
    double eps = 1e-5;
    for (const auto& kv : edgeCellCount) {
        if (kv.second == 1) { // 邊界邊
            int v1 = edgeNodes[kv.first].first;
            int v2 = edgeNodes[kv.first].second;
            
            // 判斷邊界類別
            bool isXMin = (std::abs(nodes[v1].pos.x - xMin) < eps && std::abs(nodes[v2].pos.x - xMin) < eps);
            bool isXMax = (std::abs(nodes[v1].pos.x - xMax) < eps && std::abs(nodes[v2].pos.x - xMax) < eps);
            bool isYMin = (std::abs(nodes[v1].pos.y - yMin) < eps && std::abs(nodes[v2].pos.y - yMin) < eps);
            bool isYMax = (std::abs(nodes[v1].pos.y - yMax) < eps && std::abs(nodes[v2].pos.y - yMax) < eps);
            
            int groupId = 5; // geometries surface grid
            std::string bcName = config.bcGeom;

            if (isXMin) { groupId = 1; bcName = config.bcXMin; }
            else if (isXMax) { groupId = 2; bcName = config.bcXMax; }
            else if (isYMin) { groupId = 3; bcName = config.bcYMin; }
            else if (isYMax) { groupId = 4; bcName = config.bcYMax; }
            // Phase 1: a geometry edge carrying an explicit per-segment BC tag
            // (both endpoints agree) overrides the global BC_GEOM default. This
            // replaces guessing the surface BC purely from domain proximity.
            else if (!nodes[v1].bcTag.empty() && nodes[v1].bcTag == nodes[v2].bcTag) {
                bcName = nodes[v1].bcTag;
            }
            
            // 格式：bnd編號, v1, v2, 0, 0, groupId, 0, bcName (共 8 欄)
            bofs << bndCount++ << " " << (v1 + 1) << " " << (v2 + 1) << " 0 0 " << groupId << " 0 " << bcName << "\n";
        }
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

    // --- 2. Domain extents, then group boundary edges (used by exactly one
    //        cell) by BC name — same classification as exportStarCD. ---
    double xMin = 1e9, xMax = -1e9, yMin = 1e9, yMax = -1e9;
    for (const auto& nd : nodes) {
        xMin = std::min(xMin, nd.pos.x); xMax = std::max(xMax, nd.pos.x);
        yMin = std::min(yMin, nd.pos.y); yMax = std::max(yMax, nd.pos.y);
    }
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
    const double eps = 1e-5;
    for (const auto& kv : edgeCount) {
        if (kv.second != 1) continue;
        int v1 = edgeNodes[kv.first].first, v2 = edgeNodes[kv.first].second;
        bool isXMin = (std::abs(nodes[v1].pos.x - xMin) < eps && std::abs(nodes[v2].pos.x - xMin) < eps);
        bool isXMax = (std::abs(nodes[v1].pos.x - xMax) < eps && std::abs(nodes[v2].pos.x - xMax) < eps);
        bool isYMin = (std::abs(nodes[v1].pos.y - yMin) < eps && std::abs(nodes[v2].pos.y - yMin) < eps);
        bool isYMax = (std::abs(nodes[v1].pos.y - yMax) < eps && std::abs(nodes[v2].pos.y - yMax) < eps);
        std::string bc = config.bcGeom;
        if (isXMin) bc = config.bcXMin;
        else if (isXMax) bc = config.bcXMax;
        else if (isYMin) bc = config.bcYMin;
        else if (isYMax) bc = config.bcYMax;
        else if (!nodes[v1].bcTag.empty() && nodes[v1].bcTag == nodes[v2].bcTag) bc = nodes[v1].bcTag;
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

void Mesh::generateFarFieldGmsh(const Config& config, double finalBLThickness) {
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

    // 2. 拓撲分析 (使用過濾後的邊)
    std::vector<int> loops;
    std::vector<bool> used(allLines.size(), false);
    for (size_t i = 0; i < allLines.size(); ++i) {
        if (used[i]) continue;
        std::vector<int> currentLoopLines;
        int firstLine = allLines[i];
        currentLoopLines.push_back(firstLine);
        used[i] = true;
        
        int startGmshNode = nodeToGmshTag[filteredEdges[i].v1];
        int currGmshNode = nodeToGmshTag[filteredEdges[i].v2];

        while (currGmshNode != startGmshNode) {
            bool found = false;
            for (size_t k = 0; k < allLines.size(); ++k) {
                if (!used[k]) {
                    int v1_tag = nodeToGmshTag[filteredEdges[k].v1];
                    int v2_tag = nodeToGmshTag[filteredEdges[k].v2];

                    if (v1_tag == currGmshNode) { 
                        currentLoopLines.push_back(allLines[k]); 
                        currGmshNode = v2_tag; 
                        used[k] = true; 
                        found = true; 
                        break; 
                    }
                    else if (v2_tag == currGmshNode) { 
                        currentLoopLines.push_back(-allLines[k]); 
                        currGmshNode = v1_tag; 
                        used[k] = true; 
                        found = true; 
                        break; 
                    }
                }
            }
            if (!found) break;
        }
        if (currentLoopLines.size() >= 3 && currGmshNode == startGmshNode) {
            loops.push_back(gmsh::model::geo::addCurveLoop(currentLoopLines));
        }
    }

    if (!loops.empty()) {
        gmsh::model::geo::addPlaneSurface(loops);
    }

    gmsh::model::geo::synchronize();

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
    if (!frontLineTags.empty()) {
        std::cout << "Step: Setting up Gmsh fields..." << std::endl;
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
            } else {
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

        int fDist = gmsh::model::mesh::field::add("Distance");
        gmsh::model::mesh::field::setNumbers(fDist, "CurvesList", frontLineTags);

        // 建立緩衝區：在 dBuffer 距離內維持 hBase 尺寸，避免 1 個大網格接多個小網格
        // dBuffer 透過設定檔 BL_TRANSITION_BUFFER 控制
        double dBuffer = hBase * config.blTransitionBuffer;
        
        // 使用 MathEval 實現：在 dBuffer 內維持 hBase，之後才開始增長
        // 公式：Min(farFieldSize, hBase + Max(0, dist - dBuffer) * growthRate)
        std::string expr = "Min(" + std::to_string(config.farFieldSize) + ", " + 
                           std::to_string(hBase) + " + Max(0, F" + std::to_string(fDist) + " - " + std::to_string(dBuffer) + ") * " + std::to_string(config.farFieldGrowthRate) + ")";
        
        int fFinal = gmsh::model::mesh::field::add("MathEval");
        gmsh::model::mesh::field::setString(fFinal, "F", expr);
        gmsh::model::mesh::field::setAsBackgroundMesh(fFinal);

        // 設定全域尺寸範圍，確保尺寸場有權限控制網格
        gmsh::option::setNumber("Mesh.MeshSizeMin", std::min(hEnd, config.farFieldSize));
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
    
    // 優化：建立座標查找表
    std::map<std::pair<long long, long long>, int> coordMap;
    for(auto const& nm : nodeToGmshTag) {
        coordMap[getCoordKey(nodes[nm.first].pos.x, nodes[nm.first].pos.y)] = nm.first;
    }

    std::map<std::size_t, int> gmshToOurNode;
    for (size_t i = 0; i < nodeTags.size(); ++i) {
        double x = coord[3*i], y = coord[3*i+1];
        auto key = getCoordKey(x, y);
        if (coordMap.count(key)) {
            gmshToOurNode[nodeTags[i]] = coordMap[key];
        } else {
            addNode({x, y}, NodeType::Interior);
            int newId = nodes.back().id;
            gmshToOurNode[nodeTags[i]] = newId;
            coordMap[key] = newId;
        }
    }

    std::cout << "Step: Syncing elements..." << std::endl;
    std::vector<int> elementTypes;
    std::vector<std::vector<std::size_t>> elementTags, nodeTagsByElement;
    gmsh::model::mesh::getElements(elementTypes, elementTags, nodeTagsByElement, 2);
    
    for (size_t i = 0; i < elementTypes.size(); ++i) {
        if (elementTypes[i] == 2) { // Triangles
            for (size_t j = 0; j < nodeTagsByElement[i].size(); j += 3) {
                int n1 = gmshToOurNode[nodeTagsByElement[i][j]];
                int n2 = gmshToOurNode[nodeTagsByElement[i][j+1]];
                int n3 = gmshToOurNode[nodeTagsByElement[i][j+2]];
                addElement({n1, n2, n3});
            }
        }
    }

    std::cout << "Step: Finalizing Gmsh..." << std::endl;
    gmsh::finalize();
    std::cout << "Mesh generation completed successfully!" << std::endl;
}
