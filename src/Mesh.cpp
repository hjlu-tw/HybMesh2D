#include "Mesh.hpp"
#include <fstream>
#include <iostream>
#include <gmsh.h>
#include <map>

void Mesh::addNode(Point2D p, NodeType type) {
    int id = static_cast<int>(nodes.size());
    nodes.push_back({p, type, id, false});
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

void Mesh::generateFarFieldGmsh(const Config& config) {
    gmsh::initialize();
    gmsh::model::add("FarField");

    // 1. 建立點與線
    std::map<int, int> nodeMap; 
    for (const auto& edge : edges) {
        for (int vid : {edge.v1, edge.v2}) {
            if (nodeMap.find(vid) == nodeMap.end()) {
                // 根據節點類型設定網格大小
                double lsize = (nodes[vid].type == NodeType::BoundaryLayer) ? config.surfaceSize : config.farFieldSize;
                int tag = gmsh::model::geo::addPoint(nodes[vid].pos.x, nodes[vid].pos.y, 0.0, lsize);
                nodeMap[vid] = tag;
            }
        }
    }

    std::vector<int> allLines;
    std::map<int, std::vector<int>> adj; // 節點 -> 相連的 Line Tags
    for (const auto& edge : edges) {
        int tag = gmsh::model::geo::addLine(nodeMap[edge.v1], nodeMap[edge.v2]);
        allLines.push_back(tag);
    }

    // 2. 拓撲分析：將 Line 組織成多個閉合的 Curve Loop
    // 為了簡化，我們假設 edges 是分段連續的（例如前 4 個是 Domain，後續是 Front）
    // 這裡我們使用 gmsh::model::geo::addCurveLoop 的自動搜尋功能，
    // 但我們需要分開傳遞，否則它會建立 subloops

    // 改進方案：搜尋連通分量
    std::vector<int> loops;
    std::vector<bool> used(allLines.size(), false);

    for (size_t i = 0; i < allLines.size(); ++i) {
        if (used[i]) continue;

        std::vector<int> currentLoopLines;
        int firstLine = allLines[i];
        currentLoopLines.push_back(firstLine);
        used[i] = true;

        // 取得這條線的起終點 (我們的 ID)
        int startNode = edges[i].v1;
        int currNode = edges[i].v2;

        // 尋找接續的線
        while (currNode != startNode) {
            bool found = false;
            for (size_t k = 0; k < allLines.size(); ++k) {
                if (!used[k]) {
                    if (edges[k].v1 == currNode) {
                        currentLoopLines.push_back(allLines[k]);
                        currNode = edges[k].v2;
                        used[k] = true;
                        found = true;
                        break;
                    } else if (edges[k].v2 == currNode) { // 方向相反
                        currentLoopLines.push_back(-allLines[k]);
                        currNode = edges[k].v1;
                        used[k] = true;
                        found = true;
                        break;
                    }
                }
            }
            if (!found) break; // 鏈條中斷 (非閉合)
        }

        if (currentLoopLines.size() >= 3) {
            int loopTag = gmsh::model::geo::addCurveLoop(currentLoopLines);
            loops.push_back(loopTag);
        }
    }

    if (!loops.empty()) {
        gmsh::model::geo::addPlaneSurface(loops);
    }

    gmsh::model::geo::synchronize();

    // 設定全域網格控制參數
    gmsh::option::setNumber("Mesh.Algorithm", 6); // Frontal-Delaunay
    gmsh::option::setNumber("Mesh.CharacteristicLengthExtendFromBoundary", 1);

    gmsh::model::mesh::generate(2);


    std::vector<double> coord, dummy;
    std::vector<std::size_t> nodeTags;
    gmsh::model::mesh::getNodes(nodeTags, coord, dummy);
    
    std::map<std::size_t, int> gmshToOurNode;
    for (size_t i = 0; i < nodeTags.size(); ++i) {
        Point2D p = {coord[3*i], coord[3*i+1]};
        bool exists = false;
        int existingId = -1;
        for(const auto& nm : nodeMap) {
            if((nodes[nm.first].pos - p).length() < 1e-6) {
                exists = true; existingId = nm.first; break;
            }
        }
        
        if (!exists) {
            addNode(p, NodeType::Interior);
            gmshToOurNode[nodeTags[i]] = nodes.back().id;
        } else {
            gmshToOurNode[nodeTags[i]] = existingId;
        }
    }

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

    gmsh::finalize();
}
