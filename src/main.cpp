#include "Mesh.hpp"
#include "Config.hpp"
#include <iostream>

int main() {
    Config config;
    if (!config.loadFromFile("Background_para.dat")) {
        return 1;
    }
    config.print();

    Mesh mesh;

    if (config.geomFile == "NONE") {
        std::cout << "No geometry file specified. Generating Cartesian background mesh...\n";
        mesh.generateCartesianMesh(config.xMin, config.xMax, config.yMin, config.yMax, config.farFieldSize);
    } else {
        std::cout << "Geometry file: " << config.geomFile << " detected. Proceeding with hybrid meshing (TBD).\n";
        // 未來在此處實作 Phase 2: Hybrid Meshing 流程
    }

    mesh.exportVTK("output.vtk");

    std::cout << "Process completed successfully.\n";

    return 0;
}
