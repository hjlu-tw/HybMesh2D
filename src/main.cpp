#include "Mesh.hpp"
#include "Config.hpp"
#include "BoundaryLayer.hpp"
#include <iostream>
#include <vector>
#include <string>
#include <filesystem>

namespace fs = std::filesystem;

std::vector<Point2D> loadGeometry(const std::string& filename) {
    std::vector<Point2D> points;
    std::ifstream ifs(filename);
    if (!ifs) return points;
    double x, y;
    while (ifs >> x >> y) points.push_back({x, y});

    // 如果起點與終點重合，移除最後一個點以避免產生重疊的邊界節點，這會導致法向量計算錯誤
    if (points.size() > 1) {
        double dx = points.front().x - points.back().x;
        double dy = points.front().y - points.back().y;
        if (dx * dx + dy * dy < 1e-12) {
            points.pop_back();
        }
    }
    return points;
}

bool checkDomainIntersection(const std::vector<Point2D>& geom, const Config& config) {
    std::vector<Point2D> domain = {
        {config.xMin, config.yMin}, {config.xMax, config.yMin},
        {config.xMax, config.yMax}, {config.xMin, config.yMax}
    };
    
    int nGeom = static_cast<int>(geom.size());
    for (int i = 0; i < nGeom; ++i) {
        Point2D g1 = geom[i];
        Point2D g2 = geom[(i + 1) % nGeom];

        for (int j = 0; j < 4; ++j) {
            Point2D d1 = domain[j];
            Point2D d2 = domain[(j + 1) % 4];

            if (segmentsIntersect(g1, g2, d1, d2)) {
                return true;
            }
        }
    }
    return false;
}

bool isPointInPolygon(Point2D p, const std::vector<Point2D>& poly) {
    int n = static_cast<int>(poly.size());
    bool inside = false;
    for (int i = 0, j = n - 1; i < n; j = i++) {
        if (((poly[i].y > p.y) != (poly[j].y > p.y)) &&
            (p.x < (poly[j].x - poly[i].x) * (p.y - poly[i].y) / (poly[j].y - poly[i].y) + poly[i].x)) {
            inside = !inside;
        }
    }
    return inside;
}

bool checkGeometriesIntersection(const std::vector<Point2D>& geom1, const std::vector<Point2D>& geom2) {
    int n1 = static_cast<int>(geom1.size());
    int n2 = static_cast<int>(geom2.size());
    
    // 1. 檢查線段是否交叉或重合
    for (int i = 0; i < n1; ++i) {
        Point2D g1_a = geom1[i];
        Point2D g1_b = geom1[(i + 1) % n1];
        for (int j = 0; j < n2; ++j) {
            Point2D g2_a = geom2[j];
            Point2D g2_b = geom2[(j + 1) % n2];
            
            // 正常的交叉檢查
            if (segmentsIntersect(g1_a, g1_b, g2_a, g2_b)) return true;

            // 檢查頂點是否落在另一條線段上 (處理重合或觸碰)
            auto isPointOnSegment = [](Point2D p, Point2D s1, Point2D s2) {
                double cross = (p.y - s1.y) * (s2.x - s1.x) - (p.x - s1.x) * (s2.y - s1.y);
                if (std::abs(cross) > 1e-10) return false;
                double dot = (p.x - s1.x) * (s2.x - s1.x) + (p.y - s1.y) * (s2.y - s1.y);
                if (dot < 0) return false;
                double squaredLength = (s2.x - s1.x) * (s2.x - s1.x) + (s2.y - s1.y) * (s2.y - s1.y);
                if (dot > squaredLength) return false;
                return true;
            };

            if (isPointOnSegment(g1_a, g2_a, g2_b)) return true;
            if (isPointOnSegment(g2_a, g1_a, g1_b)) return true;
        }
    }

    // 2. 檢查一個幾何是否完全在另一個內部
    if (isPointInPolygon(geom1[0], geom2)) return true;
    if (isPointInPolygon(geom2[0], geom1)) return true;

    return false;
}

int main(int argc, char* argv[]) {
    std::string configFile = "config/Background_para.dat";
    
    // 預解析參數以尋找自定義設定檔
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-conf" && i + 1 < argc) configFile = argv[++i];
    }

    Config config;
    if (!config.loadFromFile(configFile)) return 1;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-geom") {
            config.geomFiles.clear();
            while (i + 1 < argc && argv[i+1][0] != '-') {
                config.geomFiles.push_back(argv[++i]);
            }
        }
    }

    config.print();
    Mesh mesh;

    std::string outputFilename = "results/mesh_cartesian.vtk";
    if (!config.geomFiles.empty()) {
        if (config.geomFiles.size() == 1) {
            fs::path geomPath(config.geomFiles[0]);
            outputFilename = "results/mesh_" + geomPath.stem().string() + ".vtk";
        } else {
            outputFilename = "results/mesh_multiple.vtk";
        }
    }

    if (config.geomFiles.empty()) {
        mesh.generateCartesianMesh(config.xMin, config.xMax, config.yMin, config.yMax, config.farFieldSize);
    } else {
        // 加入計算域邊界 (Domain Box) 到 edges
        std::vector<int> domainNodeIds;
        mesh.addNode({config.xMin, config.yMin}, NodeType::Boundary); domainNodeIds.push_back(mesh.nodes.back().id);
        mesh.addNode({config.xMax, config.yMin}, NodeType::Boundary); domainNodeIds.push_back(mesh.nodes.back().id);
        mesh.addNode({config.xMax, config.yMax}, NodeType::Boundary); domainNodeIds.push_back(mesh.nodes.back().id);
        mesh.addNode({config.xMin, config.yMax}, NodeType::Boundary); domainNodeIds.push_back(mesh.nodes.back().id);
        
        for (int i = 0; i < 4; ++i) {
            mesh.addEdge(domainNodeIds[i], domainNodeIds[(i + 1) % 4]);
            mesh.addElement({domainNodeIds[i], domainNodeIds[(i + 1) % 4]}); // 視覺化用
        }

        BoundaryLayerGenerator blGen(mesh, config);
        double lastH = config.blInitialThickness;

        struct GeomData {
            std::string filename;
            std::vector<Point2D> points;
        };
        std::vector<GeomData> allGeometries;

        for (const auto& gFile : config.geomFiles) {
            std::vector<Point2D> geomPoints = loadGeometry(gFile);
            if (geomPoints.empty()) {
                std::cerr << "Error: Failed to load geometry from " << gFile << std::endl;
                continue;
            }

            // 檢查是否與計算域相交
            if (checkDomainIntersection(geomPoints, config)) {
                std::cerr << "Error: Geometry " << gFile << " intersects with domain boundary. Skipping.\n";
                continue;
            }
            
            allGeometries.push_back({gFile, geomPoints});
        }

        bool hasIntersection = false;
        for (size_t i = 0; i < allGeometries.size(); ++i) {
            for (size_t j = i + 1; j < allGeometries.size(); ++j) {
                if (checkGeometriesIntersection(allGeometries[i].points, allGeometries[j].points)) {
                    std::cerr << "Error: Geometry " << allGeometries[i].filename 
                              << " and Geometry " << allGeometries[j].filename 
                              << " intersect. Process stopped.\n";
                    hasIntersection = true;
                }
            }
        }

        if (hasIntersection) {
            return 1;
        }

        for (const auto& geomData : allGeometries) {
            std::vector<int> boundaryIds;
            for (const auto& p : geomData.points) {
                mesh.addNode(p, NodeType::Boundary);
                boundaryIds.push_back(mesh.nodes.back().id);
            }

            lastH = blGen.generate(boundaryIds);
        }

        // Phase 4: 遠場三角化 (傳入最後一層厚度以控制長寬比過渡)
        mesh.generateFarFieldGmsh(config, lastH);
    }

    mesh.exportVTK(outputFilename);
    std::cout << "Mesh saved to: " << outputFilename << std::endl;
    return 0;
}
