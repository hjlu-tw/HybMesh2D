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

void Mesh::generateFarFieldGmsh(const Config& config, double finalBLThickness) {
    gmsh::initialize();
    gmsh::model::add("FarField");

    // 1. 建立點與線
    std::map<int, int> nodeMap; 
    for (const auto& edge : edges) {
        for (int vid : {edge.v1, edge.v2}) {
            if (nodeMap.find(vid) == nodeMap.end()) {
                int tag = gmsh::model::geo::addPoint(nodes[vid].pos.x, nodes[vid].pos.y, 0.0);
                nodeMap[vid] = tag;
            }
        }
    }

    std::vector<int> allLines;
    std::vector<double> frontLineTags; // 用於尺寸場的邊界來源
    for (size_t i = 0; i < edges.size(); ++i) {
        int tag = gmsh::model::geo::addLine(nodeMap[edges[i].v1], nodeMap[edges[i].v2]);
        allLines.push_back(tag);
        
        // 識別 Outer Front
        if (nodes[edges[i].v1].type == NodeType::BoundaryLayer && 
            nodes[edges[i].v2].type == NodeType::BoundaryLayer) {
            frontLineTags.push_back(static_cast<double>(tag));
        }
    }

    // 2. 拓撲分析 (迴圈追蹤保持不變)
    std::vector<int> loops;
    std::vector<bool> used(allLines.size(), false);
    for (size_t i = 0; i < allLines.size(); ++i) {
        if (used[i]) continue;
        std::vector<int> currentLoopLines;
        int firstLine = allLines[i];
        currentLoopLines.push_back(firstLine);
        used[i] = true;
        int startNode = edges[i].v1;
        int currNode = edges[i].v2;
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
                    } else if (edges[k].v2 == currNode) {
                        currentLoopLines.push_back(-allLines[k]);
                        currNode = edges[k].v1;
                        used[k] = true;
                        found = true;
                        break;
                    }
                }
            }
            if (!found) break;
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

    // 2.1 局部強制邊界層外緣 1-對-1 對接
    // 只針對邊界層外緣 (Outer Front) 的線段強制節點數量為 2
    // 其他邊界 (如計算域外框) 則允許 Gmsh 依據尺寸場自動分割，以獲得平均分佈
    for (size_t i = 0; i < edges.size(); ++i) {
        if (nodes[edges[i].v1].type == NodeType::BoundaryLayer && 
            nodes[edges[i].v2].type == NodeType::BoundaryLayer) {
            gmsh::model::mesh::setTransfiniteCurve(allLines[i], 2);
        }
    }

    // --- 3. 建立尺寸過渡場 ---
    if (!frontLineTags.empty()) {
        // 3.1 扁平三角形過渡層 (BoundaryLayer Field)
        double hFirst = finalBLThickness * config.blGrowthRate;
        int fBL = gmsh::model::mesh::field::add("BoundaryLayer");
        gmsh::model::mesh::field::setNumbers(fBL, "CurvesList", frontLineTags);
        gmsh::model::mesh::field::setNumber(fBL, "Size", hFirst);
        gmsh::model::mesh::field::setNumber(fBL, "Ratio", config.blGrowthRate);
        gmsh::model::mesh::field::setNumber(fBL, "Quads", 0);
        
        double r = config.blGrowthRate;
        int numTransitionLayers = config.blTransitionLayers; // 從設定檔讀取過渡層數
        double totalTransThickness = hFirst * (std::pow(r, numTransitionLayers) - 1.0) / (r - 1.0);
        gmsh::model::mesh::field::setNumber(fBL, "Thickness", totalTransThickness);
        gmsh::model::mesh::field::setAsBoundaryLayer(fBL);

        // 3.2 遠場平滑銜接優化 (Smooth Transition Optimization)
        // 計算過渡層結束時的網格尺寸
        double hEnd = hFirst * std::pow(r, numTransitionLayers);
        
        int fDist = gmsh::model::mesh::field::add("Distance");
        gmsh::model::mesh::field::setNumbers(fDist, "CurvesList", frontLineTags);

        // 使用 MathEval 讓網格從 hEnd 平滑過渡到 farFieldSize
        // 增長梯度從設定檔讀取 FARFIELD_GROWTH_RATE
        std::string expr = "Min(" + std::to_string(config.farFieldSize) + ", " + 
                           std::to_string(hEnd) + " + " + std::to_string(config.farFieldGrowthRate) + " * F" + std::to_string(fDist) + ")";
        
        int fFinal = gmsh::model::mesh::field::add("MathEval");
        gmsh::model::mesh::field::setString(fFinal, "F", expr);
        gmsh::model::mesh::field::setAsBackgroundMesh(fFinal);

        // 設定全域尺寸範圍，確保尺寸場有權限控制網格
        gmsh::option::setNumber("Mesh.MeshSizeMin", hFirst);
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
    
    gmsh::model::mesh::generate(2);

    std::vector<double> coord, dummy;
    std::vector<std::size_t> nodeTags;
    gmsh::model::mesh::getNodes(nodeTags, coord, dummy);
    
    // 優化：建立座標查找表
    std::map<std::pair<long long, long long>, int> coordMap;
    auto getCoordKey = [](double x, double y) {
        return std::make_pair((long long)(x * 1e7), (long long)(y * 1e7));
    };
    for(auto const& nm : nodeMap) {
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
