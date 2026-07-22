#ifndef CONFIG_HPP
#define CONFIG_HPP

#include <vector>
#include <string>
#include <fstream>
#include <sstream>
#include <map>
#include <set>
#include <iostream>
#include "Logger.hpp"

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
    // BL / non-BL junction handling (see BoundaryLayer.cpp). Method 0 = taper-to-zero
    // (collapsing prisms, legacy); 1 = 4-case angle-driven (default). C1/C2/C3 bin the
    // flow-facing included angle theta (deg) between the BL edge and its non-BL neighbour:
    //   (0,C1] concave slide | (C1,C2] perpendicular | (C2,C3] neighbour-extension | (C3,360) perpendicular.
    int blJunctionMethod = 1;
    double blJunctionAngleC1 = 135.0;
    double blJunctionAngleC2 = 270.0;
    double blJunctionAngleC3 = 315.0;
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

    // Patch/group NAME -> physical BC TYPE (from GROUP_BC lines emitted by the
    // GUI Mesh Generator's "Edit segment BCs…"). A per-segment .meta tag is a
    // grouping LABEL only; its physical BC type is chosen per group here. Used at
    // .bnd export to write the resolved BC type as the patch name, so the
    // downstream solver (getPGrid's getBCType, which name-guesses) sees a BC type
    // it recognises instead of an arbitrary label it would default to wall.
    std::map<std::string, std::string> groupBc;

    // Resolve a patch/group label to its physical BC type via GROUP_BC; returns
    // the label unchanged when no mapping exists.
    std::string resolveGroupBc(const std::string& label) const {
        auto it = groupBc.find(label);
        return (it != groupBc.end() && !it->second.empty()) ? it->second : label;
    }

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

    // BL / non-BL 交界處理: 0 = taper-to-zero (collapsing prisms, 舊版), 1 = 4-case
    // 角度驅動 (預設)。C1/C2/C3 為面向流場夾角 theta (度) 的分類門檻。
    int blJunctionMethod = 1;
    double blJunctionAngleC1 = 135.0;
    double blJunctionAngleC2 = 270.0;
    double blJunctionAngleC3 = 315.0;

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
    // Gmsh thread count for far-field meshing. 0 = auto (hardware_concurrency).
    int gmshNumThreads = 0;

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

    // Load configuration from a .dat file. Returns FALSE when the file cannot be
    // opened so the caller can decide whether a missing config is fatal (an
    // explicitly-requested -conf) or tolerable (the default path -> use defaults).
    bool loadFromFile(const std::string& filename) {
        std::ifstream ifs(filename);
        if (!ifs) {
            LOG_WARN("Could not open config file " << filename << ". Using defaults.");
            return false;
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
            else if (key == "GROUP_BC") {
                // GROUP_BC <name> <bc_type>: the grouping label <name> (carried
                // on the per-segment .meta tag and thus onto boundary edges) maps
                // to the physical BC type <bc_type> chosen in the GUI. Applied at
                // .bnd export so the patch name is the BC type the solver knows.
                std::string gname, gtype;
                if (ss >> gname >> gtype) groupBc[gname] = gtype;
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
            else if (key == "BL_JUNCTION_METHOD") {
                double val; ss >> val; blJunctionMethod = static_cast<int>(val);
            }
            else if (key == "BL_JUNCTION_ANGLE_C1") ss >> blJunctionAngleC1;
            else if (key == "BL_JUNCTION_ANGLE_C2") ss >> blJunctionAngleC2;
            else if (key == "BL_JUNCTION_ANGLE_C3") ss >> blJunctionAngleC3;
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
            else if (key == "GMSH_NUM_THREADS") {
                double val; ss >> val; gmshNumThreads = static_cast<int>(val);
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

    // Validate and clamp config ranges after load + arg override. Each fix is
    // warned so a silently-nonsensical parameter can't produce a silently-wrong
    // (or NaN/Inf) mesh. Returns true if the config is usable (clamped values are
    // still usable); returns false only for a contradiction that cannot be
    // clamped meaningfully (an empty x or y domain span).
    bool validate() {
        bool ok = true;
        if (blLayers < 0) {
            LOG_WARN("BL_LAYERS < 0 (" << blLayers << "); clamping to 0.");
            blLayers = 0;
        }
        if (blInitialThickness <= 0.0) {
            LOG_WARN("BL_INITIAL_THICKNESS <= 0 (" << blInitialThickness
                     << "); clamping to 0.01.");
            blInitialThickness = 0.01;
        }
        if (blLayers > 0 && blGrowthRate <= 1.0) {
            LOG_WARN("BL_GROWTH_RATE <= 1.0 (" << blGrowthRate
                     << "); a boundary layer must expand. Clamping to 1.2.");
            blGrowthRate = 1.2;
        }
        if (blTransitionLayers > 0 && blTransitionGrowthRate <= 1.0) {
            LOG_WARN("BL_TRANSITION_GROWTH_RATE <= 1.0 (" << blTransitionGrowthRate
                     << "); transition layers must expand. Clamping to 1.2.");
            blTransitionGrowthRate = 1.2;
        }
        if (surfaceSize <= 0.0) {
            LOG_WARN("SURFACE_MESH_SIZE <= 0 (" << surfaceSize << "); clamping to 0.1.");
            surfaceSize = 0.1;
        }
        if (farFieldSize <= 0.0) {
            LOG_WARN("FARFIELD_MESH_SIZE <= 0 (" << farFieldSize << "); clamping to 1.0.");
            farFieldSize = 1.0;
        }
        // Domain span: only meaningful for the rectangular box (no custom outline,
        // no internal-flow wall — those overwrite xMin..yMax from the geometry).
        if (domainFile.empty()) {
            if (!(xMin < xMax)) {
                LOG_ERROR("DOMAIN_X_MIN (" << xMin << ") must be < DOMAIN_X_MAX ("
                          << xMax << ").");
                ok = false;
            }
            if (!(yMin < yMax)) {
                LOG_ERROR("DOMAIN_Y_MIN (" << yMin << ") must be < DOMAIN_Y_MAX ("
                          << yMax << ").");
                ok = false;
            }
        }
        return ok;
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
        p.blJunctionMethod = blJunctionMethod;
        p.blJunctionAngleC1 = blJunctionAngleC1;
        p.blJunctionAngleC2 = blJunctionAngleC2;
        p.blJunctionAngleC3 = blJunctionAngleC3;
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
        else if (key == "BL_JUNCTION_METHOD") p.blJunctionMethod = static_cast<int>(v);
        else if (key == "BL_JUNCTION_ANGLE_C1") p.blJunctionAngleC1 = v;
        else if (key == "BL_JUNCTION_ANGLE_C2") p.blJunctionAngleC2 = v;
        else if (key == "BL_JUNCTION_ANGLE_C3") p.blJunctionAngleC3 = v;
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

    void print() const { print(std::cout); }

    // Stream the fully-resolved effective config to any ostream (reused by the
    // console banner above and by the provenance sidecar writer).
    void print(std::ostream& os) const {
        os << "==================================================\n";
        os << "              HybMesh2D Configuration             \n";
        os << "==================================================\n\n";

        os << "[ Input & Domain ]\n";
        os << "  - Geometry Files       : ";
        if (geomFiles.empty()) {
            os << "NONE\n";
        } else {
            os << "\n";
            int count = 1;
            for (const auto& f : geomFiles) {
                os << "          " << count++ << ". " << f << "\n";
            }
        }
        if (!seedFiles.empty()) {
            os << "  - Refinement Seeds     : \n";
            int sc = 1;
            for (const auto& s : seedFiles) {
                int m = (s.mode >= 0) ? s.mode : seedMode;
                os << "          " << sc++ << ". " << s.file
                          << " (size=" << (s.size > 0 ? std::to_string(s.size) : "auto")
                          << ", radius=" << (s.radius > 0 ? std::to_string(s.radius) : "auto")
                          << ", mode=" << (m == 1 ? "embed" : "source") << ")\n";
            }
        }
        if (!noBLGeoms.empty())
            os << "  - No-BL geometries     : " << noBLGeoms.size() << " (conform at far-field size)\n";
        if (!domainFile.empty()) {
            os << "  - Flow Type            : " << (domainGrowBL ? "INTERNAL (domain wall, BL grows inward)" : "EXTERNAL (custom far-field outline)") << "\n";
            os << "  - Domain Boundary      : " << domainFile << (domainGrowBL ? " (wall, BL)" : " (far-field, no BL)") << "\n";
            os << "  - Domain Box           : " << (domainGrowBL ? "(bounded by the domain wall)" : "(bounding box of the outline)") << "\n\n";
        } else {
            os << "  - Flow Type            : EXTERNAL (rectangular box)\n";
            os << "  - Domain Box           : [" << xMin << ", " << xMax << "] x [" << yMin << ", " << yMax << "]\n\n";
        }

        os << "[ Mesh Sizing ]\n";
        os << "  - Auto Surface Sizing  : " << (autoSurfaceSize ? "[ON]" : "[OFF]") << "\n";
        os << "  - Surface Mesh Size    : " << surfaceSize << (autoSurfaceSize ? " (Manual fallback)" : "") << "\n";
        os << "  - Auto Far-field Sizing: " << (autoFarFieldSize ? "[ON]" : "[OFF]") << "\n";
        os << "  - Far-field Mesh Size  : " << farFieldSize << (autoFarFieldSize ? " (Manual fallback)" : "") << "\n\n";

        os << "[ Mesh Generation (BL, Transition, Far-field) ]\n";
        os << "  - Base Layers          : " << blLayers << " (Initial: " << blInitialThickness << ", Growth Rate: " << blGrowthRate << ")\n";
        os << "  - Transition Layers    : " << blTransitionLayers << " (Auto: "
                  << (blAutoTransitionLayers == 0 ? "OFF" : (blAutoTransitionLayers == 1 ? "GLOBAL" : "LOCAL"))
                  << ") | Growth Rate: " << blTransitionGrowthRate << " | Buffer: " << blTransitionBuffer << "\n";
        os << "  - Farfield Growth Rate : " << farFieldGrowthRate << "\n";
        os << "  - Gmsh Generator       : Algorithm " << gmshAlgorithm << " | Optimize: " << (gmshOptimize ? "[ON]" : "[OFF]") << "\n";
        os << "  - Analytic BL Normals  : " << (blUseAnalyticGeom ? "[ON]" : "[OFF]") << "\n\n";

        os << "[ Corner Handling (Convex & Concave) ]\n";
        os << "  - Corner Thresholds    : Convex > " << blConvexAngleThreshold << " deg, Concave < " << blConcaveAngleThreshold << " deg\n";
        os << "  - BL/no-BL Junction    : " << (blJunctionMethod == 0 ? "Taper-to-zero" : "4-case angle-driven")
                  << " (theta bins " << blJunctionAngleC1 << " / " << blJunctionAngleC2 << " / " << blJunctionAngleC3 << " deg)\n";
        os << "  - Convex Handling      : " << (blConvexMethod == 0 ? "Fan" : (blConvexMethod == 2 ? "Parallelogram" : "Unknown")) << "\n";
        if (blConvexMethod == 0) {
            os << "      * Fan Elements         : " << blFanNodes << " nodes (Auto: "
                      << (blAutoFanNodes == 0 ? "OFF" : (blAutoFanNodes == 1 ? "GLOBAL" : "LOCAL"))
                      << ") | Trigger Angle > " << blFanAngleThreshold << " deg\n";
        } else if (blConvexMethod == 2) {
            os << "      * Fallback Angle       : > " << blParaFallbackAngle << " deg\n";
        }
        os << "  - Concave Handling     : " << (blConcaveMethod == 0 ? "Vector Merge" : (blConcaveMethod == 5 ? "Thickness Blending" : "Unknown"))
                  << " | Merge: " << (blMergeConcave ? "[ON]" : "[OFF]")
                  << " | Smoothing: " << blSmoothingIters << " iters\n";
        if (blConcaveMethod == 5) {
            os << "      * Influence Multiplier : " << blConcaveInfluenceMultiplier << "\n";
        }
        os << "\n";

        os << "[ Boundary Conditions (StarCD) ]\n";
        os << "  - XMin                 : " << bcXMin << "\n";
        os << "  - XMax                 : " << bcXMax << "\n";
        os << "  - YMin                 : " << bcYMin << "\n";
        os << "  - YMax                 : " << bcYMax << "\n";
        os << "  - Geom                 : " << bcGeom << "\n\n";

        os << "[ Features & Export Options ]\n";
        os << "  - Collision Detection  : " << (enableCollisionDetection ? "[ON]" : "[OFF]") << "\n";
        os << "  - VTK Export           : " << (exportVTK ? "[ON]" : "[OFF]") << "\n";
        os << "  - StarCD Export        : " << (exportStarCD ? "[ON]" : "[OFF]") << "\n";
        os << "  - CGNS Export          : " << (exportCGNS ? "[ON]" : "[OFF]") << "\n";
        os << "  - Output Filename      : " << (outputFilename.empty() ? "(Auto-generated)" : outputFilename) << "\n";
        os << "==================================================\n";
    }
};

#endif
