#ifndef CONFIG_HPP
#define CONFIG_HPP

#include <vector>
#include <string>
#include <fstream>
#include <sstream>
#include <map>
#include <set>
#include <iostream>

// Per-geometry boundary-layer parameters. A geometry that grows a BL uses either
// the global defaults (see Config::globalBLParams) or a copy with the overrides
// declared on its GEOM_FILE / DOMAIN_FILE line applied (see Config::blParamsFor).
struct BLParams {
    double blInitialThickness = 0.01;
    double blGrowthRate = 1.2;
    int blLayers = 5;
    int blFanNodes = 5;
    int blAutoFanNodes = 0;
    double blFanAngleThreshold = 60.0;
    int blConvexMethod = 0;
    double blParaFallbackAngle = 300.0;
    double blConvexAngleThreshold = 260.0;
    int blConcaveMethod = 0;
    double blConcaveInfluenceMultiplier = 10.0;
    double blConcaveAngleThreshold = 100.0;
    int blTransitionLayers = 3;
    int blAutoTransitionLayers = 0;
    double blTransitionGrowthRate = 1.2;
    double blTransitionBuffer = 2.0;
    bool blUseAnalyticGeom = false;
};

struct Config {
    // 預設參數值 (若檔案中未指定則使用)
    std::vector<std::string> geomFiles;

    // 加密種子 (Refinement seeds, 類似 Pointwise source)：僅用來驅動遠場三角
    // 網格的「局部最小尺寸」，絕不長邊界層、也不當成計算域邊界。
    //   mode = -1: 沿用全域 seedMode, 0: source (純尺寸來源), 1: embed (內嵌貼合)
    //   size / radius < 0 時退回全域 seedSize / seedRadius，仍為負時於 Gmsh 端自動推得
    struct SeedSpec {
        std::string file;
        double size = -1.0;
        double radius = -1.0;
        int mode = -1;
    };
    std::vector<SeedSpec> seedFiles;
    double seedSize = -1.0;    // 全域預設種子尺寸 (<0 -> 依表面尺寸自動)
    double seedRadius = -1.0;  // 全域預設影響半徑 (<0 -> 約 25×size)
    int seedMode = 0;          // 0: source (僅尺寸), 1: embed (貼合、無邊界層)

    double xMin = -10.0, xMax = 10.0, yMin = -10.0, yMax = 10.0;

    // 自訂計算域外框 (Phase 2/5)：一條封閉多邊線 .dat，取代 xMin..yMax 的矩形外框。
    // 空字串 -> 用矩形 (向後相容)。多邊形/圓/扇形皆以重取樣多邊線表示；每段可
    // 由旁附 .meta 帶各自的 BC。載入後會以其 bounding box 覆寫 xMin..yMax。
    std::string domainFile;

    // Per-geometry role (Phase 5, 取代舊的全域 internalFlow + 最大面積啟發式)：
    //   - domainGrowBL：domain 外框幾何是否生長邊界層。false=遠場外框(不長 BL、
    //     外流)；true=域壁面(BL 往「內」長、無獨立外框 -> 內流)。方向由此確定，
    //     不再用最大面積猜測。
    //   - noBLGeoms：這些 GEOM_FILE 幾何不長 BL，而是以遠場尺寸貼合的邊界(洞)。
    //     不在集合中的 GEOM_FILE 為長 BL 的障礙物(往外長)。
    // Config 語法：DOMAIN_FILE <path> [bl|nobl]、GEOM_FILE <path> [bl|nobl]。
    bool domainGrowBL = false;
    std::set<std::string> noBLGeoms;

    // Per-geometry BL parameter overrides, keyed by the geometry path exactly as
    // written on its GEOM_FILE / DOMAIN_FILE line. Values use the same KEY names
    // as the global .dat keys (e.g. BL_INITIAL_THICKNESS). Only the listed keys
    // override; the rest fall back to the global BL settings. Populated from
    // trailing KEY=VALUE tokens on the geometry line (kept in sync with the GUI
    // emitter in tools/PreProcessor/gui/app/models/mesh_config.py).
    std::map<std::string, std::map<std::string, double>> blOverrides;

    // Per-geometry wall BC override, keyed by the geometry path on its
    // GEOM_FILE / DOMAIN_FILE line (from a trailing `bc=<name>` token). Lets each
    // geometry use a different wall BC instead of the single global bcGeom.
    // A per-segment .meta tag still wins over this.
    std::map<std::string, std::string> bcOverrides;

    double surfaceSize = 0.1, farFieldSize = 1.0;
    bool autoSurfaceSize = true;
    bool autoFarFieldSize = false;   // derive farFieldSize from the domain extent
    double blInitialThickness = 0.01, blGrowthRate = 1.2;
    int blLayers = 5;

    // 邊界層扇形網格控制 (Fan Elements)
    int blFanNodes = 5;
    int blAutoFanNodes = 0; // 0: OFF, 1: Global Avg, 2: Local Avg
    double blFanAngleThreshold = 60.0; // 度數
    
    // 凸角處理 (Convex Handling)
    int blConvexMethod = 0; // 0: Fan (Default), 2: Parallelogram
    double blParaFallbackAngle = 300.0; // 角度大於此值時，由單一平行四邊形改為雙平行四邊形策略
    
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
    double blTransitionBuffer = 2.0;
    double globalAvgSegmentLength = -1.0; // 用於模式 1
    
    // 進階遠場過渡控制
    double farFieldGrowthRate = 0.1;
    // 雙向分級：除了由幾何/邊界層外緣向外成長，另由計算域外邊界向內成長，兩側各自
    // 使用一個成長率，於中間取較粗者 (Min 尺寸場)。預設關閉，行為與單向相同。
    bool farFieldBidirectional = false;
    double farFieldGrowthRateOuter = 0.1; // 外邊界側成長率 (bidirectional 時生效)
    int gmshAlgorithm = 6; // 6: Frontal-Delaunay
    int gmshOptimize = 1;  // 1: Enable mesh optimization

    // Phase 3: 在平滑表面點以解析曲線(line/circle/spline)的法向取代有限差分。
    // 預設關閉，行為與舊版逐位元相同；開啟後角點仍維持既有 fan/merge 處理。
    bool blUseAnalyticGeom = false;

    // StarCD 邊界字串
    std::string bcXMin = "wall", bcXMax = "wall", bcYMin = "wall", bcYMax = "wall", bcGeom = "wall";

    // 輸出開關
    bool exportVTK = true;
    bool exportStarCD = false;
    bool exportCGNS = false;
    bool enableCollisionDetection = true;
    std::string outputFilename = "";

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
                // GEOM_FILE <path> [bl|nobl]  (bl = grow boundary layer, default;
                // nobl = no BL, conform at far-field size). The GUI in
                // tools/PreProcessor/gui/app/models/mesh_config.py must emit the
                // same token; keep the two parsers in sync.
                std::string f;
                if (ss >> f) {
                    geomFiles.push_back(f);
                    // Optional trailing tokens: role (bl|nobl) then KEY=VALUE
                    // per-geometry BL overrides.
                    std::string tok;
                    while (ss >> tok) {
                        if (tok == "nobl") noBLGeoms.insert(f);
                        else if (tok == "bl") { /* explicit grow-BL (default) */ }
                        else if (tok.rfind("bc=", 0) == 0) bcOverrides[f] = tok.substr(3);
                        else parseBLOverrideToken(tok, blOverrides[f]);
                    }
                }
            }
            else if (key == "SEED_FILE") {
                // SEED_FILE <path> [size] [radius] [mode(source|embed)]
                // 順序容忍：mode 關鍵字 (source/embed) 可出現在任意位置，數值則
                // 依序填入 size、radius。如此「SEED_FILE f embed」或
                // 「SEED_FILE f 0.02 embed」皆可正確解析。
                // 注意：GUI 端於 tools/PreProcessor/gui/app/models/mesh_config.py
                //   的 load_from_file 有一份等價的 SEED_FILE 解析，二者需保持一致。
                SeedSpec s;
                if (ss >> s.file) {
                    std::string tok;
                    int numIdx = 0;   // 0=size slot, 1=radius slot
                    while (ss >> tok) {
                        if (tok == "embed") s.mode = 1;
                        else if (tok == "source") s.mode = 0;
                        // "auto" 明確跳過目前數值槽 (維持該項為自動)，讓後面的數字
                        // 落到下一槽，如此「SEED_FILE f auto 0.5」= size 自動、radius=0.5。
                        else if (tok == "auto") ++numIdx;
                        else {
                            try {
                                double v = std::stod(tok);
                                if (numIdx == 0) s.size = v;
                                else if (numIdx == 1) s.radius = v;
                                ++numIdx;
                            } catch (...) { /* 忽略無法辨識的 token */ }
                        }
                    }
                    seedFiles.push_back(s);
                }
            }
            else if (key == "SEED_SIZE") ss >> seedSize;
            else if (key == "SEED_RADIUS") ss >> seedRadius;
            else if (key == "SEED_MODE") {
                std::string m; ss >> m; seedMode = (m == "embed" || m == "1") ? 1 : 0;
            }
            else if (key == "DOMAIN_FILE") {
                // DOMAIN_FILE <path> [bl|nobl]  (nobl = far-field outline, no BL,
                // external flow, default; bl = domain wall, BL grows inward ->
                // internal flow). Replaces the old global INTERNAL_FLOW flag.
                if (ss >> domainFile) {
                    domainGrowBL = false;
                    // Optional trailing tokens: role (bl|nobl) then KEY=VALUE
                    // per-domain BL overrides (only meaningful when bl / wall).
                    std::string tok;
                    while (ss >> tok) {
                        if (tok == "bl") domainGrowBL = true;
                        else if (tok == "nobl") domainGrowBL = false;
                        else if (tok.rfind("bc=", 0) == 0) bcOverrides[domainFile] = tok.substr(3);
                        else parseBLOverrideToken(tok, blOverrides[domainFile]);
                    }
                }
            }
            else if (key == "DOMAIN_X_MIN") ss >> xMin;
            else if (key == "DOMAIN_X_MAX") ss >> xMax;
            else if (key == "DOMAIN_Y_MIN") ss >> yMin;
            else if (key == "DOMAIN_Y_MAX") ss >> yMax;
            else if (key == "SURFACE_MESH_SIZE") ss >> surfaceSize;
            else if (key == "AUTO_SURFACE_SIZE") {
                int val; ss >> val; autoSurfaceSize = (val != 0);
            }
            else if (key == "FARFIELD_MESH_SIZE") ss >> farFieldSize;
            else if (key == "AUTO_FARFIELD_SIZE") {
                int val; ss >> val; autoFarFieldSize = (val != 0);
            }
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
            else if (key == "BL_CONVEX_METHOD") {
                double val; ss >> val; blConvexMethod = static_cast<int>(val);
            }
            else if (key == "BL_PARA_FALLBACK_ANGLE") ss >> blParaFallbackAngle;
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
            else if (key == "BL_TRANSITION_BUFFER") ss >> blTransitionBuffer;
            else if (key == "FARFIELD_GROWTH_RATE") ss >> farFieldGrowthRate;
            else if (key == "FARFIELD_GROWTH_RATE_OUTER") ss >> farFieldGrowthRateOuter;
            else if (key == "FARFIELD_BIDIRECTIONAL") {
                double val; ss >> val; farFieldBidirectional = (val != 0.0);
            }
            else if (key == "GMSH_ALGORITHM") {
                double val; ss >> val; gmshAlgorithm = static_cast<int>(val);
            }
            else if (key == "GMSH_OPTIMIZE") {
                double val; ss >> val; gmshOptimize = static_cast<int>(val);
            }
            else if (key == "BL_USE_ANALYTIC_GEOM") {
                int val; ss >> val; blUseAnalyticGeom = (val != 0);
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
            else if (key == "EXPORT_CGNS") {
                int val; ss >> val; exportCGNS = (val != 0);
            }
            else if (key == "ENABLE_COLLISION_DETECTION") {
                int val; ss >> val; enableCollisionDetection = (val != 0);
            }
            else if (key == "OUTPUT_FILENAME") {
                ss >> outputFilename;
            }
        }
        return true;
    }

    // Parse a "KEY=VALUE" token into a per-geometry override map (ignored if it
    // isn't of that form or the value isn't numeric).
    static void parseBLOverrideToken(const std::string& tok,
                                     std::map<std::string, double>& out) {
        auto eq = tok.find('=');
        if (eq == std::string::npos || eq == 0) return;
        try { out[tok.substr(0, eq)] = std::stod(tok.substr(eq + 1)); }
        catch (...) { /* ignore malformed values */ }
    }

    // Copy the global BL settings into a BLParams bundle.
    BLParams globalBLParams() const {
        BLParams p;
        p.blInitialThickness = blInitialThickness;
        p.blGrowthRate = blGrowthRate;
        p.blLayers = blLayers;
        p.blFanNodes = blFanNodes;
        p.blAutoFanNodes = blAutoFanNodes;
        p.blFanAngleThreshold = blFanAngleThreshold;
        p.blConvexMethod = blConvexMethod;
        p.blParaFallbackAngle = blParaFallbackAngle;
        p.blConvexAngleThreshold = blConvexAngleThreshold;
        p.blConcaveMethod = blConcaveMethod;
        p.blConcaveInfluenceMultiplier = blConcaveInfluenceMultiplier;
        p.blConcaveAngleThreshold = blConcaveAngleThreshold;
        p.blTransitionLayers = blTransitionLayers;
        p.blAutoTransitionLayers = blAutoTransitionLayers;
        p.blTransitionGrowthRate = blTransitionGrowthRate;
        p.blTransitionBuffer = blTransitionBuffer;
        p.blUseAnalyticGeom = blUseAnalyticGeom;
        return p;
    }

    static void applyBLKey(BLParams& p, const std::string& key, double v) {
        if (key == "BL_INITIAL_THICKNESS") p.blInitialThickness = v;
        else if (key == "BL_GROWTH_RATE") p.blGrowthRate = v;
        else if (key == "BL_LAYERS") p.blLayers = static_cast<int>(v);
        else if (key == "BL_FAN_NODES") p.blFanNodes = static_cast<int>(v);
        else if (key == "BL_AUTO_FAN_NODES") p.blAutoFanNodes = static_cast<int>(v);
        else if (key == "BL_FAN_ANGLE_THRESHOLD") p.blFanAngleThreshold = v;
        else if (key == "BL_CONVEX_METHOD") p.blConvexMethod = static_cast<int>(v);
        else if (key == "BL_PARA_FALLBACK_ANGLE") p.blParaFallbackAngle = v;
        else if (key == "BL_CONVEX_ANGLE_THRESHOLD") p.blConvexAngleThreshold = v;
        else if (key == "BL_CONCAVE_METHOD") p.blConcaveMethod = static_cast<int>(v);
        else if (key == "BL_CONCAVE_INFLUENCE_MULTIPLIER") p.blConcaveInfluenceMultiplier = v;
        else if (key == "BL_CONCAVE_ANGLE_THRESHOLD") p.blConcaveAngleThreshold = v;
        else if (key == "BL_TRANSITION_LAYERS") p.blTransitionLayers = static_cast<int>(v);
        else if (key == "BL_AUTO_TRANSITION_LAYERS") p.blAutoTransitionLayers = static_cast<int>(v);
        else if (key == "BL_TRANSITION_GROWTH_RATE") p.blTransitionGrowthRate = v;
        else if (key == "BL_TRANSITION_BUFFER") p.blTransitionBuffer = v;
        else if (key == "BL_USE_ANALYTIC_GEOM") p.blUseAnalyticGeom = (v != 0.0);
    }

    // Effective BL parameters for a geometry: global defaults with any overrides
    // declared on its GEOM_FILE / DOMAIN_FILE line applied on top.
    BLParams blParamsFor(const std::string& file) const {
        BLParams p = globalBLParams();
        auto it = blOverrides.find(file);
        if (it != blOverrides.end())
            for (const auto& kv : it->second) applyBLKey(p, kv.first, kv.second);
        return p;
    }

    // Effective wall BC for a geometry: its per-geometry override, else the
    // global bcGeom. (A per-segment .meta tag still takes priority downstream.)
    std::string bcFor(const std::string& file) const {
        auto it = bcOverrides.find(file);
        return (it != bcOverrides.end() && !it->second.empty()) ? it->second : bcGeom;
    }

    void print() const {
        std::cout << "==================================================\n";
        std::cout << "              HybMesh2D Configuration             \n";
        std::cout << "==================================================\n\n";

        std::cout << "[ Input & Domain ]\n";
        std::cout << "  - Geometry Files       : ";
        if (geomFiles.empty()) {
            std::cout << "NONE\n";
        } else {
            std::cout << "\n";
            int count = 1;
            for (const auto& f : geomFiles) {
                std::cout << "          " << count++ << ". " << f << "\n";
            }
        }
        if (!seedFiles.empty()) {
            std::cout << "  - Refinement Seeds     : \n";
            int sc = 1;
            for (const auto& s : seedFiles) {
                int m = (s.mode >= 0) ? s.mode : seedMode;
                std::cout << "          " << sc++ << ". " << s.file
                          << " (size=" << (s.size > 0 ? std::to_string(s.size) : "auto")
                          << ", radius=" << (s.radius > 0 ? std::to_string(s.radius) : "auto")
                          << ", mode=" << (m == 1 ? "embed" : "source") << ")\n";
            }
        }
        if (!noBLGeoms.empty())
            std::cout << "  - No-BL geometries     : " << noBLGeoms.size() << " (conform at far-field size)\n";
        if (!domainFile.empty()) {
            std::cout << "  - Flow Type            : " << (domainGrowBL ? "INTERNAL (domain wall, BL grows inward)" : "EXTERNAL (custom far-field outline)") << "\n";
            std::cout << "  - Domain Boundary      : " << domainFile << (domainGrowBL ? " (wall, BL)" : " (far-field, no BL)") << "\n";
            std::cout << "  - Domain Box           : " << (domainGrowBL ? "(bounded by the domain wall)" : "(bounding box of the outline)") << "\n\n";
        } else {
            std::cout << "  - Flow Type            : EXTERNAL (rectangular box)\n";
            std::cout << "  - Domain Box           : [" << xMin << ", " << xMax << "] x [" << yMin << ", " << yMax << "]\n\n";
        }

        std::cout << "[ Mesh Sizing ]\n";
        std::cout << "  - Auto Surface Sizing  : " << (autoSurfaceSize ? "[ON]" : "[OFF]") << "\n";
        std::cout << "  - Surface Mesh Size    : " << surfaceSize << (autoSurfaceSize ? " (Manual fallback)" : "") << "\n";
        std::cout << "  - Auto Far-field Sizing: " << (autoFarFieldSize ? "[ON]" : "[OFF]") << "\n";
        std::cout << "  - Far-field Mesh Size  : " << farFieldSize << (autoFarFieldSize ? " (Manual fallback)" : "") << "\n\n";

        std::cout << "[ Mesh Generation (BL, Transition, Far-field) ]\n";
        std::cout << "  - Base Layers          : " << blLayers << " (Initial: " << blInitialThickness << ", Growth Rate: " << blGrowthRate << ")\n";
        std::cout << "  - Transition Layers    : " << blTransitionLayers << " (Auto: " 
                  << (blAutoTransitionLayers == 0 ? "OFF" : (blAutoTransitionLayers == 1 ? "GLOBAL" : "LOCAL")) 
                  << ") | Growth Rate: " << blTransitionGrowthRate << " | Buffer: " << blTransitionBuffer << "\n";
        std::cout << "  - Farfield Growth Rate : " << farFieldGrowthRate << "\n";
        std::cout << "  - Gmsh Generator       : Algorithm " << gmshAlgorithm << " | Optimize: " << (gmshOptimize ? "[ON]" : "[OFF]") << "\n";
        std::cout << "  - Analytic BL Normals  : " << (blUseAnalyticGeom ? "[ON]" : "[OFF]") << "\n\n";

        std::cout << "[ Corner Handling (Convex & Concave) ]\n";
        std::cout << "  - Corner Thresholds    : Convex > " << blConvexAngleThreshold << " deg, Concave < " << blConcaveAngleThreshold << " deg\n";
        std::cout << "  - Convex Handling      : " << (blConvexMethod == 0 ? "Fan" : (blConvexMethod == 2 ? "Parallelogram" : "Unknown")) << "\n";
        if (blConvexMethod == 0) {
            std::cout << "      * Fan Elements         : " << blFanNodes << " nodes (Auto: " 
                      << (blAutoFanNodes == 0 ? "OFF" : (blAutoFanNodes == 1 ? "GLOBAL" : "LOCAL")) 
                      << ") | Trigger Angle > " << blFanAngleThreshold << " deg\n";
        } else if (blConvexMethod == 2) {
            std::cout << "      * Fallback Angle       : > " << blParaFallbackAngle << " deg\n";
        }
        std::cout << "  - Concave Handling     : " << (blConcaveMethod == 0 ? "Vector Merge" : (blConcaveMethod == 5 ? "Thickness Blending" : "Unknown")) 
                  << " | Merge: " << (blMergeConcave ? "[ON]" : "[OFF]") 
                  << " | Smoothing: " << blSmoothingIters << " iters\n";
        if (blConcaveMethod == 5) {
            std::cout << "      * Influence Multiplier : " << blConcaveInfluenceMultiplier << "\n";
        }
        std::cout << "\n";

        std::cout << "[ Boundary Conditions (StarCD) ]\n";
        std::cout << "  - XMin                 : " << bcXMin << "\n";
        std::cout << "  - XMax                 : " << bcXMax << "\n";
        std::cout << "  - YMin                 : " << bcYMin << "\n";
        std::cout << "  - YMax                 : " << bcYMax << "\n";
        std::cout << "  - Geom                 : " << bcGeom << "\n\n";

        std::cout << "[ Features & Export Options ]\n";
        std::cout << "  - Collision Detection  : " << (enableCollisionDetection ? "[ON]" : "[OFF]") << "\n";
        std::cout << "  - VTK Export           : " << (exportVTK ? "[ON]" : "[OFF]") << "\n";
        std::cout << "  - StarCD Export        : " << (exportStarCD ? "[ON]" : "[OFF]") << "\n";
        std::cout << "  - CGNS Export          : " << (exportCGNS ? "[ON]" : "[OFF]") << "\n";
        std::cout << "  - Output Filename      : " << (outputFilename.empty() ? "(Auto-generated)" : outputFilename) << "\n";
        std::cout << "==================================================\n";
    }
};

#endif
