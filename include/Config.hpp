#ifndef CONFIG_HPP
#define CONFIG_HPP

#include <string>
#include <fstream>
#include <sstream>
#include <map>
#include <iostream>

struct Config {
    std::string geomFile = "NONE";
    double xMin, xMax, yMin, yMax;
    double surfaceSize, farFieldSize;
    double blInitialThickness, blGrowthRate;
    int blLayers;

    bool loadFromFile(const std::string& filename) {
        std::ifstream ifs(filename);
        if (!ifs) {
            std::cerr << "Error: Could not open config file " << filename << std::endl;
            return false;
        }

        std::string line, key;
        while (std::getline(ifs, line)) {
            if (line.empty() || line[0] == '#') continue;
            std::stringstream ss(line);
            ss >> key;
            if (key == "GEOM_FILE") ss >> geomFile;
            else if (key == "DOMAIN_X_MIN") ss >> xMin;
            else if (key == "DOMAIN_X_MAX") ss >> xMax;
            else if (key == "DOMAIN_Y_MIN") ss >> yMin;
            else if (key == "DOMAIN_Y_MAX") ss >> yMax;
            else if (key == "SURFACE_MESH_SIZE") ss >> surfaceSize;
            else if (key == "FARFIELD_MESH_SIZE") ss >> farFieldSize;
            else if (key == "BL_INITIAL_THICKNESS") ss >> blInitialThickness;
            else if (key == "BL_GROWTH_RATE") ss >> blGrowthRate;
            else if (key == "BL_LAYERS") {
                double val;
                ss >> val;
                blLayers = static_cast<int>(val);
            }
        }
        return true;
    }

    void print() const {
        std::cout << "----- Configuration -----\n";
        std::cout << "Geom File: " << geomFile << "\n";
        std::cout << "Domain: [" << xMin << ", " << xMax << "] x [" << yMin << ", " << yMax << "]\n";
        std::cout << "Surface Size: " << surfaceSize << ", Far-field Size: " << farFieldSize << "\n";
        std::cout << "BL: " << blLayers << " layers, start " << blInitialThickness << ", rate " << blGrowthRate << "\n";
        std::cout << "-------------------------\n";
    }
};

#endif
