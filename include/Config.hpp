#ifndef CONFIG_HPP
#define CONFIG_HPP

#include <vector>
#include <string>
#include <fstream>
#include <sstream>
#include <map>
#include <iostream>

struct Config {
    // 預設參數值 (若檔案中未指定則使用)
    std::vector<std::string> geomFiles;
    double xMin = -10.0, xMax = 10.0, yMin = -10.0, yMax = 10.0;
    double surfaceSize = 0.1, farFieldSize = 1.0;
    double blInitialThickness = 0.01, blGrowthRate = 1.2;
    int blLayers = 5;

    // 邊界層扇形網格控制 (Fan Elements)
    int blFanNodes = 5;
    int blAutoFanNodes = 0; // 0: OFF, 1: Global Avg, 2: Local Avg
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
    int blAutoTransitionLayers = 0; // 0: OFF, 1: Global Avg, 2: Per-Geometry Avg
    double blTransitionGrowthRate = 1.2;
    double globalAvgSegmentLength = -1.0; // 用於模式 1
    
    // 進階遠場過渡控制
    double farFieldGrowthRate = 0.1;
    int gmshAlgorithm = 6; // 6: Frontal-Delaunay
    int gmshOptimize = 1;  // 1: Enable mesh optimization

    // StarCD 邊界字串
    std::string bcXMin = "wall", bcXMax = "wall", bcYMin = "wall", bcYMax = "wall", bcGeom = "wall";

    // 輸出開關
    bool exportVTK = true;
    bool exportStarCD = false;

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
            if (key == "GEOM_FILE") {
                std::string f;
                if (ss >> f) geomFiles.push_back(f);
            }
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
                double val; ss >> val; blAutoTransitionLayers = static_cast<int>(val);
            }
            else if (key == "BL_TRANSITION_GROWTH_RATE") ss >> blTransitionGrowthRate;
            else if (key == "FARFIELD_GROWTH_RATE") ss >> farFieldGrowthRate;
            else if (key == "GMSH_ALGORITHM") {
                double val; ss >> val; gmshAlgorithm = static_cast<int>(val);
            }
            else if (key == "GMSH_OPTIMIZE") {
                double val; ss >> val; gmshOptimize = static_cast<int>(val);
            }
            else if (key == "BC_XMIN") ss >> bcXMin;
            else if (key == "BC_XMAX") ss >> bcXMax;
            else if (key == "BC_YMIN") ss >> bcYMin;
            else if (key == "BC_YMAX") ss >> bcYMax;
            else if (key == "BC_GEOM") ss >> bcGeom;
            else if (key == "EXPORT_VTK") {
                int val; ss >> val; exportVTK = (val != 0);
            }
            else if (key == "EXPORT_STARCD") {
                int val; ss >> val; exportStarCD = (val != 0);
            }
        }
        return true;
    }

    void print() const {
        std::cout << "----- Configuration -----\n";
        std::cout << "Geom Files: ";
        if (geomFiles.empty()) std::cout << "NONE";
        else {
            for (const auto& f : geomFiles) std::cout << f << " ";
        }
        std::cout << "\n";
        std::cout << "Domain: [" << xMin << ", " << xMax << "] x [" << yMin << ", " << yMax << "]\n";
        std::cout << "Surface Size: " << surfaceSize << ", Far-field Size: " << farFieldSize << "\n";
        std::cout << "BL: " << blLayers << " layers, start " << blInitialThickness << ", rate " << blGrowthRate << "\n";
        std::cout << "BL Fan Elements: " << blFanNodes << " nodes (Auto: " 
                  << (blAutoFanNodes == 0 ? "OFF" : (blAutoFanNodes == 1 ? "GLOBAL" : "LOCAL")) 
                  << "), trigger angle > " << blFanAngleThreshold << " deg\n";
        std::cout << "BL Corner Thresholds: Convex > " << blConvexAngleThreshold << " deg, Concave < " << blConcaveAngleThreshold << " deg\n";
        std::cout << "BL Concave Handling: Smoothing " << blSmoothingIters << " iters, Merge " << (blMergeConcave ? "ON" : "OFF") << ", Method " << blConcaveMethod << "\n";
        if (blConcaveMethod == 5) std::cout << "  - Thickness Blending Influence Multiplier: " << blConcaveInfluenceMultiplier << "\n";
        std::cout << "Transition: " << blTransitionLayers << " layers (Auto: " 
                  << (blAutoTransitionLayers == 0 ? "OFF" : (blAutoTransitionLayers == 1 ? "GLOBAL" : "LOCAL")) 
                  << "), rate " << blTransitionGrowthRate << "\n";
        std::cout << "Farfield Growth: " << farFieldGrowthRate << "\n";
        std::cout << "Gmsh: Algorithm " << gmshAlgorithm << ", Optimize " << (gmshOptimize ? "ON" : "OFF") << "\n";
        std::cout << "StarCD BCs: XMin=" << bcXMin << ", XMax=" << bcXMax << ", YMin=" << bcYMin << ", YMax=" << bcYMax << ", Geom=" << bcGeom << "\n";
        std::cout << "Exports: VTK=" << (exportVTK ? "ON" : "OFF") << ", StarCD=" << (exportStarCD ? "ON" : "OFF") << "\n";
        std::cout << "-------------------------\n";
    }
};

#endif
