#include "Mesh.hpp"
#include <fstream>
#include <iostream>

void Mesh::addNode(Point2D p, NodeType type) {
    int id = static_cast<int>(nodes.size());
    nodes.push_back({p, type, id});
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
