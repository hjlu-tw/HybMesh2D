#ifndef CONFIG_HPP
#define CONFIG_HPP

#include <string>
#include <fstream>
#include <sstream>
#include <map>
#include <iostream>

struct Config {
    // 預設參數值 (若檔案中未指定則使用)
    std::string geomFile = "NONE";
    double xMin = -10.0, xMax = 10.0, yMin = -10.0, yMax = 10.0;
    double surfaceSize = 0.1, farFieldSize = 1.0;
    double blInitialThickness = 0.01, blGrowthRate = 1.2;
    int blLayers = 5;

    // 邊界層扇形網格控制 (Fan Elements)
    int blFanNodes = 5;
    bool blAutoFanNodes = false;
    double blFanAngleThreshold = 60.0; // 度數
    
    // 凹角處理 (Concave Handling)
    int blSmoothingIters = 0;
    bool blMergeConcave = false;
    int blConcaveMethod = 0; // 0: Default (Merge), 5: Thickness-based Blending
    double blConcaveInfluenceMultiplier = 10.0;
    double blConvexAngleThreshold = 260.0;
    double blConcaveAngleThreshold = 100.0;
    
    // 過渡層設定 (Phase 4)
    int blTransitionLayers = 3;
    bool blAutoTransitionLayers = false;
    double blTransitionGrowthRate = 1.2;
    
    // 進階遠場過渡控制
    double farFieldGrowthRate = 0.1;
    int gmshAlgorithm = 6; // 6: Frontal-Delaunay
    int gmshOptimize = 1;  // 1: Enable mesh optimization

    bool loadFromFile(const std::string& filename) {
        std::ifstream ifs(filename);
        if (!ifs) {
            std::cerr << "Warning: Could not open config file " << filename << ". Using defaults.\n";
            return true;
        }

        std::string line, key;
        while (std::getline(ifs, line)) {
            // 跳過註解與空行
            if (line.empty() || line[0] == '#' || line[0] == '/') continue;
            
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
                double val; ss >> val; blLayers = static_cast<int>(val);
            }
            else if (key == "BL_FAN_NODES") {
                double val; ss >> val; blFanNodes = static_cast<int>(val);
            }
            else if (key == "BL_AUTO_FAN_NODES") {
                int val; ss >> val; blAutoFanNodes = (val != 0);
            }
            else if (key == "BL_FAN_ANGLE_THRESHOLD") ss >> blFanAngleThreshold;
            else if (key == "BL_SMOOTHING_ITERS") {
                double val; ss >> val; blSmoothingIters = static_cast<int>(val);
            }
            else if (key == "BL_MERGE_CONCAVE") {
                int val; ss >> val; blMergeConcave = (val != 0);
            }
            else if (key == "BL_CONCAVE_METHOD") {
                double val; ss >> val; blConcaveMethod = static_cast<int>(val);
            }
            else if (key == "BL_CONCAVE_INFLUENCE_MULTIPLIER") ss >> blConcaveInfluenceMultiplier;
            else if (key == "BL_CONVEX_ANGLE_THRESHOLD") ss >> blConvexAngleThreshold;
            else if (key == "BL_CONCAVE_ANGLE_THRESHOLD") ss >> blConcaveAngleThreshold;
            else if (key == "BL_TRANSITION_LAYERS") {
                double val; ss >> val; blTransitionLayers = static_cast<int>(val);
            }
            else if (key == "BL_AUTO_TRANSITION_LAYERS") {
                int val; ss >> val; blAutoTransitionLayers = (val != 0);
            }
            else if (key == "BL_TRANSITION_GROWTH_RATE") ss >> blTransitionGrowthRate;
            else if (key == "FARFIELD_GROWTH_RATE") ss >> farFieldGrowthRate;
            else if (key == "GMSH_ALGORITHM") {
                double val; ss >> val; gmshAlgorithm = static_cast<int>(val);
            }
            else if (key == "GMSH_OPTIMIZE") {
                double val; ss >> val; gmshOptimize = static_cast<int>(val);
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
        std::cout << "BL Fan Elements: " << blFanNodes << " nodes (Auto: " << (blAutoFanNodes ? "ON" : "OFF") << "), trigger angle > " << blFanAngleThreshold << " deg\n";
        std::cout << "BL Corner Thresholds: Convex > " << blConvexAngleThreshold << " deg, Concave < " << blConcaveAngleThreshold << " deg\n";
        std::cout << "BL Concave Handling: Smoothing " << blSmoothingIters << " iters, Merge " << (blMergeConcave ? "ON" : "OFF") << ", Method " << blConcaveMethod << "\n";
        if (blConcaveMethod == 5) std::cout << "  - Thickness Blending Influence Multiplier: " << blConcaveInfluenceMultiplier << "\n";
        std::cout << "Transition: " << blTransitionLayers << " layers (Auto: " << (blAutoTransitionLayers ? "ON" : "OFF") << "), rate " << blTransitionGrowthRate << "\n";
        std::cout << "Farfield Growth: " << farFieldGrowthRate << "\n";
        std::cout << "Gmsh: Algorithm " << gmshAlgorithm << ", Optimize " << (gmshOptimize ? "ON" : "OFF") << "\n";
        std::cout << "-------------------------\n";
    }
};

#endif
