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
#include "BLParams.hpp"
#include "MeshMode.hpp"

struct Config {
    // Which GENERATION PATH runs. 0 = the existing hybrid path (boundary-layer
    // quads grown from every geometry, Gmsh triangles in the far field) and the
    // DEFAULT, so every case that exists today produces exactly the mesh it
    // produced before. 1 = the topology-driven multi-block path, where the
    // blocking is DECLARED in topologyFile rather than inferred from angles and
    // distance tolerances.
    //
    // The two paths read different parameters. A parameter the ACTIVE mode never
    // reads is named in a warning rather than silently doing nothing — see
    // include/MeshMode.hpp, which owns that list and is where the answer is
    // computed.
    // Spelled `0` rather than `MESH_MODE_HYBRID`, and that is not laziness: the
    // GUI/C++ parity gate resolves this member's INITIALISER to compare it with
    // MeshConfig.mesh_mode's default, and it reads a literal. An enum name here
    // would make the gate report "initialiser not readable" — i.e. one of the two
    // sides would stop being compared. The name is in the comment above instead.
    int meshMode = 0;

    // The block topology document (JSON) the multi-block path reads. Chosen by
    // EXPLICIT declaration, never guessed from a filename convention sitting
    // beside the geometry: a guess is silent when it is wrong, and the file
    // decides the whole mesh here.
    // `= ""` for the same reason: the gate's struct reader only sees a member that
    // carries an initialiser, and a member it cannot see is a key it cannot compare.
    std::string topologyFile = "";

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
    // The GLOBAL boundary-layer settings, and the only copy of them. A geometry
    // that grows a BL reads either this struct (globalBLParams(), which now hands it
    // over as-is) or a copy with its own KEY=VALUE tokens applied (blParamsFor()).
    //
    // This used to be a second, hand-aligned declaration of BLParams' 22 fields
    // sitting right here, with its own set of defaults, bridged by a 22-line
    // field-by-field copy in globalBLParams(). The two default lists agreed only
    // because someone kept them agreeing: a new parameter given 0.01 on one and
    // 0.001 on the other would have run a plain mesh at one value and an
    // override-carrying mesh at the other, with nothing to report it.
    BLParams bl;

    // Global-only BL settings, deliberately NOT part of BLParams: neither is
    // per-geometry overridable, so neither is a duplicate of anything.
    // blSmoothingIters smooths the FINISHED mesh (src/cli.cpp), i.e. it is not a
    // property of one geometry's front; blMergeConcave is read by print() alone and
    // survives only to round-trip through the GUI.
    int blSmoothingIters = 0;
    bool blMergeConcave = false;

    double globalAvgSegmentLength = -1.0; // 用於模式 1 (see bl.blAutoTransitionLayers)
    
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

    // Units. The unit every length in this config (and in the geometry files) is
    // expressed in. The mesher deliberately does NOT convert anything: it only ever
    // compares lengths against each other, so rescaling them would change nothing
    // except the chance of a bug. It records the unit because the SOLVER is
    // dimensional — Linf is metres-per-grid-unit and Re = fs_UnitRe * Linf — so a
    // mesh must not travel downstream without saying what its coordinates mean.
    // lengthUnitMetres is used only for lengthUnit == "custom".
    std::string lengthUnit = "m";
    double lengthUnitMetres = 1.0;
    std::string lengthUnitName = "";

    // Metres per model unit, i.e. the solver's Linf. Kept here (rather than in the
    // GUI alone) so a hand-written config still reports a coherent unit.
    double metresPerUnit() const {
        if (lengthUnit == "custom") return lengthUnitMetres > 0.0 ? lengthUnitMetres : 1.0;
        if (lengthUnit == "m")  return 1.0;
        if (lengthUnit == "cm") return 1.0e-2;
        if (lengthUnit == "mm") return 1.0e-3;
        if (lengthUnit == "um") return 1.0e-6;
        if (lengthUnit == "in") return 0.0254;
        if (lengthUnit == "ft") return 0.3048;
        return 1.0;   // unknown code: behave as dimensionless rather than refuse to run
    }

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
            else if (key == "MESH_MODE") {
                double val; ss >> val; meshMode = static_cast<int>(val);
            }
            else if (key == "MESH_TOPOLOGY_FILE") ss >> topologyFile;
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
            // Every declared BL parameter, read straight off the declaration in
            // BLParams.hpp. Nothing to forget here: a row added there is parsed,
            // overridable per geometry and covered by the round-trip test with no
            // edit in this file. (BL_SMOOTHING_ITERS and BL_MERGE_CONCAVE are NOT
            // declared there — they are global-only, see Config::bl — so they keep
            // their own branches below.)
            else if (readBLParam(bl, key, ss)) { /* handled by the declaration */ }
            else if (key == "BL_SMOOTHING_ITERS") {
                double val; ss >> val; blSmoothingIters = static_cast<int>(val);
            }
            else if (key == "BL_MERGE_CONCAVE") {
                int val; ss >> val; blMergeConcave = (val != 0);
            }
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
            else if (key == "LENGTH_UNIT") {
                std::string u; ss >> u;
                if (!u.empty()) lengthUnit = u;
            }
            else if (key == "LENGTH_UNIT_METRES") {
                double v; if (ss >> v && v > 0.0) lengthUnitMetres = v;
            }
            else if (key == "LENGTH_UNIT_NAME") {
                ss >> lengthUnitName;
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
        // NOT clamped to 0. Every other repair in this function has an obviously
        // right value to fall back on; a mode does not — silently running the
        // hybrid path for someone who asked for MESH_MODE 2 would produce a mesh
        // nobody asked for, which is the failure class this file keeps closing.
        if (!hybmesh::isKnownMeshMode(meshMode)) {
            LOG_ERROR("MESH_MODE " << meshMode << " is not a known mode ("
                      << MESH_MODE_HYBRID << " = hybrid BL + Gmsh, "
                      << MESH_MODE_MULTIBLOCK << " = multi-block structured).");
            ok = false;
        }
        if (bl.blLayers < 0) {
            LOG_WARN("BL_LAYERS < 0 (" << bl.blLayers << "); clamping to 0.");
            bl.blLayers = 0;
        }
        if (bl.blInitialThickness <= 0.0) {
            LOG_WARN("BL_INITIAL_THICKNESS <= 0 (" << bl.blInitialThickness
                     << "); clamping to 0.01.");
            bl.blInitialThickness = 0.01;
        }
        if (bl.blLayers > 0 && bl.blGrowthRate <= 1.0) {
            LOG_WARN("BL_GROWTH_RATE <= 1.0 (" << bl.blGrowthRate
                     << "); a boundary layer must expand. Clamping to 1.2.");
            bl.blGrowthRate = 1.2;
        }
        if (bl.blTransitionLayers > 0 && bl.blTransitionGrowthRate <= 1.0) {
            LOG_WARN("BL_TRANSITION_GROWTH_RATE <= 1.0 (" << bl.blTransitionGrowthRate
                     << "); transition layers must expand. Clamping to 1.2.");
            bl.blTransitionGrowthRate = 1.2;
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

    // Parse a "KEY=VALUE" per-geometry override token (ignored if it isn't of that
    // form or the value isn't numeric).
    //
    // An unrecognised KEY is NAMED rather than dropped. It used to be dropped twice
    // over — stored here, then silently skipped by the applier, which is the
    // "the user sets a value and it does nothing" failure this whole area exists to
    // remove. The declaration answers whether a key is real (isBLParam), so this
    // check cannot fall behind the parameter list. Warned at LOAD time, once per
    // token, rather than in blParamsFor, which runs per geometry per BL loop.
    static void parseBLOverrideToken(const std::string& tok,
                                     std::map<std::string, double>& out) {
        auto eq = tok.find('=');
        if (eq == std::string::npos || eq == 0) return;
        const std::string key = tok.substr(0, eq);
        if (!isBLParam(key)) {
            LOG_WARN("Unknown per-geometry BL override '" << key << "' ignored; it is "
                     "not a boundary-layer parameter (see include/BLParams.hpp).");
            return;
        }
        try { out[key] = std::stod(tok.substr(eq + 1)); }
        catch (...) { /* ignore malformed values */ }
    }

    // The global BL settings. Nothing to copy: Config HOLDS a BLParams, so this
    // is an accessor rather than the 22-line field-by-field bridge it used to be.
    BLParams globalBLParams() const { return bl; }

    // Effective BL parameters for a geometry: global defaults with any overrides
    // declared on its GEOM_FILE / DOMAIN_FILE line applied on top.
    BLParams blParamsFor(const std::string& file) const {
        BLParams p = globalBLParams();
        auto it = blOverrides.find(file);
        if (it != blOverrides.end())
            for (const auto& kv : it->second) applyBLParam(p, kv.first, kv.second);
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

        os << "[ Mesh Mode ]\n";
        os << "  - Mesh Mode            : " << meshMode << " ("
           << hybmesh::meshModeName(meshMode) << ")\n";
        if (meshMode == MESH_MODE_MULTIBLOCK)
            os << "  - Topology File        : "
               << (topologyFile.empty() ? "(none declared)" : topologyFile) << "\n";
        os << "\n";

        os << "[ Input & Domain ]\n";
        // Printed first, and deliberately in the banner rather than only in the
        // config file: every length below is meaningless without it, and this is the
        // number the solver needs as Linf (Re = fs_UnitRe * Linf).
        os << "  - Model Unit           : "
           << (lengthUnitName.empty() ? lengthUnit : lengthUnitName)
           << "  (1 unit = " << metresPerUnit() << " m; solver Linf)\n";
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
        os << "  - Base Layers          : " << bl.blLayers << " (Initial: " << bl.blInitialThickness << ", Growth Rate: " << bl.blGrowthRate << ")\n";
        os << "  - Transition Layers    : " << bl.blTransitionLayers << " (Auto: "
                  << (bl.blAutoTransitionLayers == 0 ? "OFF" : (bl.blAutoTransitionLayers == 1 ? "GLOBAL" : "LOCAL"))
                  << ") | Growth Rate: " << bl.blTransitionGrowthRate << " | Buffer: " << bl.blTransitionBuffer << "\n";
        os << "  - Farfield Growth Rate : " << farFieldGrowthRate << "\n";
        os << "  - Gmsh Generator       : Algorithm " << gmshAlgorithm << " | Optimize: " << (gmshOptimize ? "[ON]" : "[OFF]") << "\n";
        os << "  - Analytic BL Normals  : " << (bl.blUseAnalyticGeom ? "[ON]" : "[OFF]") << "\n";
        // Printed because the banner IS the provenance sidecar: a declared
        // parameter the banner omits is one a finished mesh cannot account for.
        // This one was omitted (found by the coverage check in
        // tests/cpp/test_bl_params_decl.cpp, which now fails if any row of the
        // declaration never reaches this function).
        os << "  - Front Smoothing      : " << bl.blFrontSmoothingIters << " iters/layer\n\n";

        os << "[ Corner Handling (Convex & Concave) ]\n";
        os << "  - Corner Thresholds    : Convex > " << bl.blConvexAngleThreshold << " deg, Concave < " << bl.blConcaveAngleThreshold << " deg\n";
        os << "  - BL/no-BL Junction    : " << (bl.blJunctionMethod == 0 ? "Taper-to-zero" : "4-case angle-driven")
                  << " (theta bins " << bl.blJunctionAngleC1 << " / " << bl.blJunctionAngleC2 << " / " << bl.blJunctionAngleC3 << " deg)\n";
        os << "  - Convex Handling      : " << (bl.blConvexMethod == 0 ? "Fan" : (bl.blConvexMethod == 2 ? "Parallelogram" : "Unknown")) << "\n";
        if (bl.blConvexMethod == 0) {
            os << "      * Fan Elements         : " << bl.blFanNodes << " nodes (Auto: "
                      << (bl.blAutoFanNodes == 0 ? "OFF" : (bl.blAutoFanNodes == 1 ? "GLOBAL" : "LOCAL"))
                      << ") | Trigger Angle > " << bl.blFanAngleThreshold << " deg\n";
        } else if (bl.blConvexMethod == 2) {
            os << "      * Fallback Angle       : > " << bl.blParaFallbackAngle << " deg\n";
        }
        os << "  - Concave Handling     : " << (bl.blConcaveMethod == 0 ? "Vector Merge" : (bl.blConcaveMethod == 5 ? "Thickness Blending" : "Unknown"))
                  << " | Merge: " << (blMergeConcave ? "[ON]" : "[OFF]")
                  << " | Smoothing: " << blSmoothingIters << " iters\n";
        if (bl.blConcaveMethod == 5) {
            os << "      * Influence Multiplier : " << bl.blConcaveInfluenceMultiplier << "\n";
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
