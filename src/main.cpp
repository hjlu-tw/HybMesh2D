#include "Mesh.hpp"
#include "Config.hpp"
#include "BoundaryLayer.hpp"
#include <iostream>
#include <vector>
#include <string>

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
        if (arg == "-geom" && i + 1 < argc) config.geomFile = argv[++i];
    }

    config.print();
    Mesh mesh;

    if (config.geomFile == "NONE") {
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

        std::vector<Point2D> geomPoints = loadGeometry(config.geomFile);
        if (geomPoints.empty()) {
            std::cerr << "Error: Failed to load geometry from " << config.geomFile << std::endl;
            return 1;
        }

        // 檢查是否與計算域相交
        if (checkDomainIntersection(geomPoints, config)) {
            std::cerr << "Error: Geometry intersects with domain boundary. Process stopped.\n";
            return 1;
        }
        
        std::vector<int> boundaryIds;
        for (const auto& p : geomPoints) {
            mesh.addNode(p, NodeType::Boundary);
            boundaryIds.push_back(mesh.nodes.back().id);
        }

        BoundaryLayerGenerator blGen(mesh, config);
        double lastH = blGen.generate(boundaryIds);

        // Phase 4: 遠場三角化 (傳入最後一層厚度以控制長寬比過渡)
        mesh.generateFarFieldGmsh(config, lastH);
    }

    mesh.exportVTK("results/output.vtk");
    return 0;
}
