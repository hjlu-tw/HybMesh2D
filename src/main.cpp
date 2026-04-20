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
    Config config;
    if (!config.loadFromFile("Background_para.dat")) return 1;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-geom" && i + 1 < argc) config.geomFile = argv[++i];
    }

    config.print();
    Mesh mesh;

    if (config.geomFile == "NONE") {
        mesh.generateCartesianMesh(config.xMin, config.xMax, config.yMin, config.yMax, config.farFieldSize);
    } else {
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
        blGen.generate(boundaryIds);
    }

    mesh.exportVTK("output.vtk");
    return 0;
}
