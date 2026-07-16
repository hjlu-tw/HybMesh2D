#include "Mesh.hpp"
#include "Config.hpp"
#include "BoundaryLayer.hpp"
#include "Logger.hpp"
#include "Provenance.hpp"
#include "ExitCodes.hpp"
#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <map>
#include <set>
#include <filesystem>

namespace fs = std::filesystem;

// Emit a machine-readable failure line the GUI/CI can parse without regex on
// prose, then return the code. Human-readable detail should already have been
// logged via LOG_ERROR at the failure site.
static int reportError(int code, const std::string& detail = "") {
    std::cout << "HYBMESH_ERROR " << code << " " << exitCodeToken(code)
              << (detail.empty() ? "" : (" " + detail)) << std::endl;
    return code;
}

// Outcome of a geometry load, so the caller can distinguish "the file isn't
// there / can't be opened" (a hard, user-facing error) from "the file opened
// but held no usable points" (also an error, different message).
enum class LoadStatus { Ok, CannotOpen, Empty };

// Load a polyline. If `closed` is provided, report whether the first/last
// points coincided (a closed loop) — refinement seeds use this to decide
// whether to add the closing segment; boundary loads pass nullptr and ignore it.
// `status` (optional) reports why an empty result occurred.
std::vector<Point2D> loadGeometry(const std::string& filename, bool* closed = nullptr,
                                  LoadStatus* status = nullptr) {
    std::vector<Point2D> points;
    if (closed) *closed = false;
    if (status) *status = LoadStatus::Ok;
    std::ifstream ifs(filename);
    if (!ifs.is_open()) {
        if (status) *status = LoadStatus::CannotOpen;
        return points;
    }
    double x, y;
    while (ifs >> x >> y) points.push_back({x, y});

    // Distinguish a clean EOF from a truncated/corrupt file: if extraction
    // stopped before EOF, there are unconsumed non-whitespace tokens.
    if (ifs.fail() && !ifs.eof()) {
        LOG_WARN("Geometry file '" << filename
                 << "' appears truncated or malformed; parsing stopped after "
                 << points.size() << " point(s).");
    }

    if (points.empty() && status) *status = LoadStatus::Empty;

    // 如果起點與終點重合，移除最後一個點以避免產生重疊的邊界節點，這會導致法向量計算錯誤
    if (points.size() > 1) {
        double dx = points.front().x - points.back().x;
        double dy = points.front().y - points.back().y;
        if (dx * dx + dy * dy < 1e-12) {
            points.pop_back();
            if (closed) *closed = true;
        }
    }
    return points;
}

// Parse a numeric command-line argument. On malformed input, warn and leave the
// target unchanged (so it falls back to its config/auto default) rather than
// letting std::stod throw and abort the program.
static bool parseDoubleArg(const std::string& s, double& out) {
    try {
        out = std::stod(s);
        return true;
    } catch (const std::exception&) {
        std::cerr << "Warning: invalid numeric value '" << s
                  << "' for a command-line argument; ignoring.\n";
        return false;
    }
}

// Guarded int parse for the -out_* toggle flags. std::stoi throws on a
// non-numeric argument; catch it so a bad value logs and leaves `out` unchanged
// (keeping the config/default) instead of aborting the whole program.
static bool parseIntArg(const std::string& s, int& out) {
    try {
        out = std::stoi(s);
        return true;
    } catch (const std::exception&) {
        std::cerr << "Warning: invalid integer value '" << s
                  << "' for a command-line argument; ignoring.\n";
        return false;
    }
}

// Phase 1: optional metadata sidecar produced by the preprocessor next to the
// .dat (see saveMetadata in tools/PreProcessor/src/main.cpp). Parsed with the
// stream extractor only — no JSON dependency. A missing or malformed sidecar
// returns valid==false and the caller transparently falls back to the legacy
// behaviour (BC from config, no corner info).
struct SurfaceMeta {
    bool valid = false;
    std::vector<int> segId;             // parallel to the .dat points
    std::vector<char> isCorner;         // parallel to the .dat points
    std::map<int, std::string> segBc;   // seg_id -> boundary condition tag
    std::map<int, std::string> segKind; // seg_id -> curve kind (v2+)
    std::map<int, int> segGrowBL;       // seg_id -> grow boundary layer? 1/0 (v3+; absent -> 1)
    std::vector<size_t> pieceBreaks;
};

SurfaceMeta loadSurfaceMeta(const std::string& datFile) {
    SurfaceMeta m;
    std::ifstream ifs(datFile + ".meta");
    if (!ifs) return m;
    std::string tok;
    int version = 0;
    if (!(ifs >> tok >> version) || tok != "HYBMESH_META") return m;
    size_t count = 0, nPieces = 0, nSeg = 0, nPts = 0;
    if (!(ifs >> tok >> count) || tok != "COUNT") return m;
    if (!(ifs >> tok >> nPieces) || tok != "NPIECES") return m;
    for (size_t i = 0; i < nPieces; ++i) { size_t b; if (!(ifs >> b)) return m; m.pieceBreaks.push_back(b); }
    if (!(ifs >> tok >> nSeg) || tok != "NSEGMENTS") return m;
    for (size_t i = 0; i < nSeg; ++i) {
        int sid; std::string bc;
        if (!(ifs >> sid >> bc)) return m;
        m.segBc[sid] = (bc == "-") ? std::string() : bc;
        if (version >= 2) {              // v2 carries the curve kind per segment
            std::string kind;
            if (!(ifs >> kind)) return m;
            m.segKind[sid] = kind;
        }
        if (version >= 3) {              // v3 carries a per-segment grow-BL flag
            int growBL = 1;
            if (!(ifs >> growBL)) return m;
            m.segGrowBL[sid] = growBL;
        }
    }
    if (!(ifs >> tok >> nPts) || tok != "POINTS") return m;
    m.segId.reserve(nPts);
    m.isCorner.reserve(nPts);
    for (size_t i = 0; i < nPts; ++i) {
        int sid = -1, corner = 0;
        if (!(ifs >> sid >> corner)) return m;
        m.segId.push_back(sid);
        m.isCorner.push_back((char)(corner != 0));
    }
    m.valid = true;
    return m;
}

// True if a geometry loop crosses the domain outline. `domain` is the ordered,
// closed domain polyline (a rectangle's 4 corners, or a custom outline) — testing
// against the real outline (not just its bbox) keeps the check valid for arbitrary
// domain shapes.
bool checkDomainIntersection(const std::vector<Point2D>& geom, const std::vector<Point2D>& domain) {
    int nGeom = static_cast<int>(geom.size());
    int nDom = static_cast<int>(domain.size());
    if (nDom < 3) return false;
    for (int i = 0; i < nGeom; ++i) {
        Point2D g1 = geom[i];
        Point2D g2 = geom[(i + 1) % nGeom];

        for (int j = 0; j < nDom; ++j) {
            Point2D d1 = domain[j];
            Point2D d2 = domain[(j + 1) % nDom];

            if (segmentsIntersect(g1, g2, d1, d2)) {
                return true;
            }
        }
    }
    return false;
}

// Reconcile a metadata sidecar against the points actually loaded. loadGeometry
// drops a trailing duplicate of the first point on closed loops, so a sidecar for
// a closed shape legitimately has one extra entry; anything else is a stale/edited
// mismatch and the sidecar is dropped. Shared by every geometry load (obstacles,
// the domain outline, no-BL holes) so per-segment BCs survive loop closure.
static void reconcileMeta(SurfaceMeta& meta, size_t nPts, const std::string& file) {
    if (!meta.valid) return;
    if (meta.segId.size() == nPts + 1) { meta.segId.pop_back(); meta.isCorner.pop_back(); }
    else if (meta.segId.size() != nPts) {
        LOG_WARN("Metadata sidecar for " << file << " has " << meta.segId.size()
                 << " points but geometry has " << nPts << "; ignoring sidecar.");
        meta.valid = false;
    }
}

// Add a closed polyline as boundary nodes + edges, each edge tagged with its
// per-segment BC (edge i -> point i's segment BC, else defaultBc); nodes carry the
// per-point metadata. Used for boundaries that do NOT grow a boundary layer — the
// far-field outline and no-BL obstacle holes — which conform to the mesh at
// far-field size. Returns the node ids.
static std::vector<int> addTaggedLoop(Mesh& mesh, const std::vector<Point2D>& pts,
                                      const SurfaceMeta& meta, const std::string& defaultBc,
                                      int geomId) {
    bool useMeta = meta.valid && meta.segId.size() == pts.size();
    std::vector<int> ids; ids.reserve(pts.size());
    std::vector<std::string> edgeBc(pts.size(), defaultBc);
    for (size_t i = 0; i < pts.size(); ++i) {
        mesh.addNode(pts[i], NodeType::Boundary);
        Node& nd = mesh.nodes.back();
        nd.geomId = geomId;
        if (useMeta) {
            nd.segId = meta.segId[i];
            nd.isCorner = meta.isCorner[i] != 0;
            auto it = meta.segBc.find(nd.segId);
            if (it != meta.segBc.end() && !it->second.empty()) { nd.bcTag = it->second; edgeBc[i] = it->second; }
            auto kit = meta.segKind.find(nd.segId);
            if (kit != meta.segKind.end()) nd.curveKind = curveKindFromString(kit->second);
        }
        ids.push_back(nd.id);
    }
    int n = static_cast<int>(ids.size());
    for (int i = 0; i < n; ++i) {
        mesh.addEdge(ids[i], ids[(i + 1) % n]);
        mesh.edges.back().bcTag = edgeBc[i];
        mesh.addElement({ids[i], ids[(i + 1) % n]}); // 視覺化用
    }
    return ids;
}

// Build the outer computational-domain boundary for the cases that do NOT grow a
// boundary layer: the rectangular box (config.domainFile empty) or a custom
// far-field outline (config.domainFile set, config.domainGrowBL false). The
// internal-flow case (domainGrowBL true) is handled by the caller, which loads the
// domain file as a BL wall so its inner front bounds the triangulated core. For a
// custom outline the config box is overwritten with the outline's bounding box so
// downstream logic that reads xMin..yMax (mesh sizing, front validation) stays
// valid. Returns the ordered domain polyline for intersection tests.
static std::vector<Point2D> buildDomainBoundary(Mesh& mesh, Config& config) {
    std::vector<Point2D> outline;
    if (!config.domainFile.empty()) {
        outline = loadGeometry(config.domainFile);
        if (outline.size() < 3) {
            LOG_WARN("Domain file '" << config.domainFile
                     << "' has fewer than 3 points; using the rectangular box instead.");
            outline.clear();
        }
    }

    if (!outline.empty()) {
        SurfaceMeta meta = loadSurfaceMeta(config.domainFile);
        reconcileMeta(meta, outline.size(), config.domainFile);
        double bxMin = outline[0].x, bxMax = outline[0].x;
        double byMin = outline[0].y, byMax = outline[0].y;
        for (const auto& p : outline) {
            if (p.x < bxMin) bxMin = p.x;
            if (p.x > bxMax) bxMax = p.x;
            if (p.y < byMin) byMin = p.y;
            if (p.y > byMax) byMax = p.y;
        }
        config.xMin = bxMin; config.xMax = bxMax;
        config.yMin = byMin; config.yMax = byMax;
        addTaggedLoop(mesh, outline, meta, config.bcFor(config.domainFile), /*geomId*/ -1);
        std::cout << "  - Domain Boundary      : custom far-field outline ("
                  << outline.size() << " segment(s)) from " << config.domainFile << "\n";
        return outline;
    }

    // Rectangular box. Sides tagged to match node order: bottom(YMin), right(XMax),
    // top(YMax), left(XMin).
    std::vector<int> domainNodeIds;
    mesh.addNode({config.xMin, config.yMin}, NodeType::Boundary); domainNodeIds.push_back(mesh.nodes.back().id);
    mesh.addNode({config.xMax, config.yMin}, NodeType::Boundary); domainNodeIds.push_back(mesh.nodes.back().id);
    mesh.addNode({config.xMax, config.yMax}, NodeType::Boundary); domainNodeIds.push_back(mesh.nodes.back().id);
    mesh.addNode({config.xMin, config.yMax}, NodeType::Boundary); domainNodeIds.push_back(mesh.nodes.back().id);
    const std::string domainBcTags[4] = {
        config.bcYMin, config.bcXMax, config.bcYMax, config.bcXMin
    };
    std::vector<Point2D> rect;
    for (int i = 0; i < 4; ++i) {
        mesh.addEdge(domainNodeIds[i], domainNodeIds[(i + 1) % 4]);
        mesh.edges.back().bcTag = domainBcTags[i];
        mesh.addElement({domainNodeIds[i], domainNodeIds[(i + 1) % 4]}); // 視覺化用
        rect.push_back(mesh.nodes[domainNodeIds[i]].pos);
    }
    return rect;
}

bool isPointInPolygon(Point2D p, const std::vector<Point2D>& poly) {
    int n = static_cast<int>(poly.size());
    bool inside = false;
    for (int i = 0, j = n - 1; i < n; j = i++) {
        if (((poly[i].y > p.y) != (poly[j].y > p.y)) &&
            (p.x < (poly[j].x - poly[i].x) * (p.y - poly[i].y) / (poly[j].y - poly[i].y) + poly[i].x)) {
            inside = !inside;
        }
    }
    return inside;
}

bool checkGeometriesIntersection(const std::vector<Point2D>& geom1, const std::vector<Point2D>& geom2,
                                 bool internalFlow = false) {
    int n1 = static_cast<int>(geom1.size());
    int n2 = static_cast<int>(geom2.size());
    
    // 1. 檢查線段是否交叉或重合
    for (int i = 0; i < n1; ++i) {
        Point2D g1_a = geom1[i];
        Point2D g1_b = geom1[(i + 1) % n1];
        for (int j = 0; j < n2; ++j) {
            Point2D g2_a = geom2[j];
            Point2D g2_b = geom2[(j + 1) % n2];
            
            // 正常的交叉檢查
            if (segmentsIntersect(g1_a, g1_b, g2_a, g2_b)) return true;

            // 檢查頂點是否落在另一條線段上 (處理重合或觸碰)
            auto isPointOnSegment = [](Point2D p, Point2D s1, Point2D s2) {
                double cross = (p.y - s1.y) * (s2.x - s1.x) - (p.x - s1.x) * (s2.y - s1.y);
                if (std::abs(cross) > 1e-10) return false;
                double dot = (p.x - s1.x) * (s2.x - s1.x) + (p.y - s1.y) * (s2.y - s1.y);
                if (dot < 0) return false;
                double squaredLength = (s2.x - s1.x) * (s2.x - s1.x) + (s2.y - s1.y) * (s2.y - s1.y);
                if (dot > squaredLength) return false;
                return true;
            };

            if (isPointOnSegment(g1_a, g2_a, g2_b)) return true;
            if (isPointOnSegment(g2_a, g1_a, g1_b)) return true;
        }
    }

    // 2. 檢查一個幾何是否完全在另一個內部。內流時島嶼障礙物本就位於外壁之內，
    //    此為合法的環狀域，故略過此包含檢查 (線段交叉檢查於上方仍生效)。
    if (!internalFlow) {
        if (isPointInPolygon(geom1[0], geom2)) return true;
        if (isPointInPolygon(geom2[0], geom1)) return true;
    }

    return false;
}

int main(int argc, char* argv[]) {
    Config config;
    std::string configFile = "config/Background_para.dat";
    std::vector<std::string> cmdGeomFiles;
    std::vector<std::string> cmdNoBLGeomFiles;   // -geom_nobl: obstacles that don't grow BL
    std::vector<std::string> cmdSeedFiles;
    bool geomProvided = false;
    bool seedProvided = false;
    bool confExplicit = false;

    // Phase-2 flags that consume exactly one value. Phase 1 must skip their value
    // so it is never mistaken for the bare positional config path (e.g. the "1" in
    // "-out_starcd 1", or the filename in "-domain outline.dat").
    static const std::set<std::string> kValueFlags = {
        "-bc_xmin", "-bc_xmax", "-bc_ymin", "-bc_ymax", "-bc_geom",
        "-out_vtk", "-out_starcd", "-out_cgns", "-out_name",
        "-domain", "-seed_size", "-seed_radius", "-seed_mode"
    };

    // 第一階段：掃描以找出設定檔路徑與 -geom / -seed 參數
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-conf" && i + 1 < argc) {
            configFile = argv[++i];
            confExplicit = true;
        } else if (arg == "-geom") {
            geomProvided = true;
            while (i + 1 < argc && argv[i+1][0] != '-') {
                cmdGeomFiles.push_back(argv[++i]);
            }
        } else if (arg == "-seed") {
            seedProvided = true;
            while (i + 1 < argc && argv[i+1][0] != '-') {
                cmdSeedFiles.push_back(argv[++i]);
            }
        } else if (arg == "-geom_nobl") {
            while (i + 1 < argc && argv[i+1][0] != '-') {
                cmdNoBLGeomFiles.push_back(argv[++i]);
            }
        } else if (kValueFlags.count(arg) && i + 1 < argc) {
            ++i; // value belongs to a phase-2 flag, not the config path
        } else if (arg[0] != '-' && !confExplicit) {
            // Bare positional config path (only the first one; guarded so a stray
            // value can't override it).
            configFile = arg;
            confExplicit = true;
        }
    }

    // loadFromFile now returns false when the file cannot be opened. An
    // explicitly-requested -conf that cannot be opened is a fatal config error;
    // the default path missing just falls back to built-in defaults.
    if (!config.loadFromFile(configFile)) {
        if (confExplicit) {
            LOG_ERROR("Config file '" << configFile << "' could not be opened.");
            return reportError(EXIT_ERR_CONFIG, configFile);
        }
        // else: defaults are in use (loadFromFile already warned).
    }

    // 如果命令列提供了 -geom，則覆蓋設定檔中的幾何物件
    if (geomProvided) {
        config.geomFiles = cmdGeomFiles;
    }
    // -geom_nobl：附加不長 BL 的障礙物 (以遠場尺寸貼合)。
    for (const auto& f : cmdNoBLGeomFiles) {
        config.geomFiles.push_back(f);
        config.noBLGeoms.insert(f);
    }
    // 如果命令列提供了 -seed，則覆蓋設定檔中的加密種子 (套用全域 size/radius/mode)
    if (seedProvided) {
        config.seedFiles.clear();
        for (const auto& f : cmdSeedFiles) {
            Config::SeedSpec s; s.file = f; config.seedFiles.push_back(s);
        }
    }

    // 第二階段：處理其他命令列參數，這些參數優先於設定檔
    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "-bc_xmin" && i + 1 < argc) config.bcXMin = argv[++i];
        else if (arg == "-bc_xmax" && i + 1 < argc) config.bcXMax = argv[++i];
        else if (arg == "-bc_ymin" && i + 1 < argc) config.bcYMin = argv[++i];
        else if (arg == "-bc_ymax" && i + 1 < argc) config.bcYMax = argv[++i];
        else if (arg == "-bc_geom" && i + 1 < argc) config.bcGeom = argv[++i];
        else if (arg == "-out_vtk" && i + 1 < argc) { int v; if (parseIntArg(argv[++i], v)) config.exportVTK = (v != 0); }
        else if (arg == "-out_starcd" && i + 1 < argc) { int v; if (parseIntArg(argv[++i], v)) config.exportStarCD = (v != 0); }
        else if (arg == "-out_cgns" && i + 1 < argc) { int v; if (parseIntArg(argv[++i], v)) config.exportCGNS = (v != 0); }
        else if (arg == "-out_name" && i + 1 < argc) config.outputFilename = argv[++i];
        else if (arg == "-domain" && i + 1 < argc) config.domainFile = argv[++i];
        else if (arg == "-domain_bl") config.domainGrowBL = true; // domain wall grows BL inward (internal flow)
        else if (arg == "-geom_nobl") { // already collected in phase 1; skip its values here
            while (i + 1 < argc && argv[i+1][0] != '-') ++i;
        }
        else if (arg == "-seed_size" && i + 1 < argc) parseDoubleArg(argv[++i], config.seedSize);
        else if (arg == "-seed_radius" && i + 1 < argc) parseDoubleArg(argv[++i], config.seedRadius);
        else if (arg == "-seed_mode" && i + 1 < argc) {
            std::string m = argv[++i]; config.seedMode = (m == "embed" || m == "1") ? 1 : 0;
        }
        // -geom / -seed / -conf 已經處理過，但在這裡跳過它們的參數以避免干擾
        else if (arg == "-geom") {
            while (i + 1 < argc && argv[i+1][0] != '-') ++i;
        }
        else if (arg == "-seed") {
            while (i + 1 < argc && argv[i+1][0] != '-') ++i;
        }
        else if (arg == "-conf") {
            if (i + 1 < argc) ++i;
        }
    }

    // Validate/clamp config ranges after the config load + all CLI overrides.
    // A contradiction that cannot be clamped (empty domain span) is fatal.
    if (!config.validate()) {
        LOG_ERROR("Configuration failed validation (see warnings above).");
        return reportError(EXIT_ERR_CONFIG, "validation");
    }

    config.print();
    Mesh mesh;

    std::string outputFilename = "Results/mesh_cartesian.vtk";
    if (!config.outputFilename.empty()) {
        outputFilename = config.outputFilename;
    } else if (!config.geomFiles.empty()) {
        if (config.geomFiles.size() == 1) {
            fs::path geomPath(config.geomFiles[0]);
            outputFilename = "Results/mesh_" + geomPath.stem().string() + ".vtk";
        } else {
            outputFilename = "Results/mesh_multiple.vtk";
        }
    }

    // Ensure the output directory exists so VTK/STAR-CD exports do not silently
    // vanish on a fresh clone or case-sensitive filesystem.
    {
        fs::path outParent = fs::path(outputFilename).parent_path();
        if (!outParent.empty()) {
            std::error_code ec;
            fs::create_directories(outParent, ec);
            if (ec) LOG_WARN("Cannot create output directory '"
                             << outParent.string() << "': " << ec.message());
        }
    }

    bool hasIntersection = false;
    bool blSuccess = true;
    int failExit = EXIT_OK;                 // set to a distinct code on failure
    std::string gmshVersion;                // resolved for provenance
    std::vector<std::string> inputFiles;    // geometry inputs for provenance
    for (const auto& f : config.geomFiles) inputFiles.push_back(f);
    if (!config.domainFile.empty()) inputFiles.push_back(config.domainFile);
    if (config.geomFiles.empty() && config.seedFiles.empty() && config.domainFile.empty()) {
        mesh.generateCartesianMesh(config.xMin, config.xMax, config.yMin, config.yMax, config.farFieldSize);
    } else {
        // ---- Domain boundary ----------------------------------------------
        // Rectangle box, or a custom far-field outline (no BL). The internal-flow
        // case (a domain wall that grows BL inward) is NOT built here — it is loaded
        // below as a BL geometry so its inner front bounds the triangulated core.
        std::vector<Point2D> domainOutline;
        bool domainIsWall = (!config.domainFile.empty() && config.domainGrowBL);
        if (!domainIsWall) {
            domainOutline = buildDomainBoundary(mesh, config); // box or far-field outline
        }

        BoundaryLayerGenerator blGen(mesh, config);
        double lastH = config.blInitialThickness;

        // ---- Gather input geometries with their per-geometry role -----------
        struct GeomInput {
            std::string file;
            std::vector<Point2D> points;
            SurfaceMeta meta;
            bool isDomainWall;   // domain outline that grows BL inward (internal flow)
            bool growBL;         // grow a boundary layer (false = conform at far-field size)
            BLParams bl;         // effective per-geometry BL parameters (global + overrides)
        };
        std::vector<GeomInput> inputs;

        // Domain wall first (internal flow): its bbox drives the config box so the
        // BL front validation (xMin..yMax) stays valid for geometries beyond ±10.
        if (domainIsWall) {
            LoadStatus st = LoadStatus::Ok;
            std::vector<Point2D> pts = loadGeometry(config.domainFile, nullptr, &st);
            if (st == LoadStatus::CannotOpen) {
                LOG_ERROR("Internal-flow domain wall '" << config.domainFile
                          << "' could not be opened.");
                return reportError(EXIT_ERR_GEOMETRY_LOAD, config.domainFile);
            }
            if (pts.size() < 3) {
                LOG_ERROR("Internal-flow domain wall '" << config.domainFile
                          << "' has fewer than 3 points.");
                return reportError(EXIT_ERR_GEOMETRY_LOAD, config.domainFile);
            }
            SurfaceMeta meta = loadSurfaceMeta(config.domainFile);
            reconcileMeta(meta, pts.size(), config.domainFile);
            double bxMin = pts[0].x, bxMax = pts[0].x, byMin = pts[0].y, byMax = pts[0].y;
            for (const auto& p : pts) {
                if (p.x < bxMin) bxMin = p.x;
                if (p.x > bxMax) bxMax = p.x;
                if (p.y < byMin) byMin = p.y;
                if (p.y > byMax) byMax = p.y;
            }
            config.xMin = bxMin; config.xMax = bxMax;
            config.yMin = byMin; config.yMax = byMax;
            inputs.push_back({config.domainFile, pts, meta, true, true,
                              config.blParamsFor(config.domainFile)});
        }

        // Obstacles / objects (GEOM_FILE). growBL unless listed in noBLGeoms.
        // A requested geometry that cannot be loaded is a HARD error: an unloadable
        // input must not let the run quietly "succeed" with a wrong (partial) mesh.
        for (const auto& gFile : config.geomFiles) {
            LoadStatus st = LoadStatus::Ok;
            std::vector<Point2D> geomPoints = loadGeometry(gFile, nullptr, &st);
            if (geomPoints.empty()) {
                if (st == LoadStatus::CannotOpen)
                    LOG_ERROR("Requested geometry '" << gFile << "' could not be opened "
                              "(file not found / unreadable).");
                else
                    LOG_ERROR("Requested geometry '" << gFile << "' contains no usable "
                              "points (empty or malformed).");
                return reportError(EXIT_ERR_GEOMETRY_LOAD, gFile);
            }
            if (checkDomainIntersection(geomPoints, domainOutline)) { // no-op when domainOutline empty
                LOG_ERROR("Geometry '" << gFile << "' intersects the domain boundary.");
                return reportError(EXIT_ERR_INTERSECTION, gFile);
            }
            SurfaceMeta meta = loadSurfaceMeta(gFile);
            reconcileMeta(meta, geomPoints.size(), gFile);
            bool bl = config.noBLGeoms.find(gFile) == config.noBLGeoms.end();
            inputs.push_back({gFile, geomPoints, meta, false, bl,
                              config.blParamsFor(gFile)});
        }

        // ---- Pairwise collision detection -----------------------------------
        // A domain wall legitimately contains islands, so skip the containment check
        // for internal flow; segment-crossing checks still apply.
        if (config.enableCollisionDetection) {
            for (size_t i = 0; i < inputs.size(); ++i)
                for (size_t j = i + 1; j < inputs.size(); ++j)
                    if (checkGeometriesIntersection(inputs[i].points, inputs[j].points, domainIsWall)) {
                        LOG_ERROR("Geometry '" << inputs[i].file
                                  << "' and geometry '" << inputs[j].file
                                  << "' intersect. Process stopped.");
                        hasIntersection = true;
                    }
        }
        if (hasIntersection) return reportError(EXIT_ERR_INTERSECTION);

        if (config.blAutoTransitionLayers == 1) {
            double totalLen = 0.0; int totalSegments = 0;
            for (const auto& g : inputs) {
                int np = (int)g.points.size();
                for (int i = 0; i < np; ++i) {
                    totalLen += (g.points[(i + 1) % np] - g.points[i]).length();
                    totalSegments++;
                }
            }
            if (totalSegments > 0) config.globalAvgSegmentLength = totalLen / (double)totalSegments;
        }

        // ---- Build nodes/edges + per-loop growth direction ------------------
        // BL geometries -> allBoundaryIds (growMode: domain wall +1 inward, obstacle
        // -1 outward — deterministic, no area heuristic). No-BL geometries -> tagged
        // edge loops (holes) meshed at far-field size, not grown.
        std::vector<std::vector<int>> allBoundaryIds;
        std::vector<int> growModes;
        std::vector<BLParams> blParamsPerLoop;   // parallel to allBoundaryIds
        int taggedCorners = 0;
        int noBLGeomId = 100000;   // distinct geomIds for no-BL loops (BL self-collision)
        for (const auto& g : inputs) {
            if (!g.growBL) {
                addTaggedLoop(mesh, g.points, g.meta, config.bcFor(g.file), noBLGeomId++);
                continue;
            }
            int blIndex = static_cast<int>(allBoundaryIds.size()); // == FrontState.geomId
            std::vector<int> boundaryIds;
            boundaryIds.reserve(g.points.size());
            for (size_t pi = 0; pi < g.points.size(); ++pi) {
                mesh.addNode(g.points[pi], NodeType::Boundary);
                Node& nd = mesh.nodes.back();
                nd.geomId = blIndex;
                if (g.meta.valid) {
                    nd.segId = g.meta.segId[pi];
                    nd.isCorner = g.meta.isCorner[pi] != 0;
                    if (nd.isCorner) ++taggedCorners;
                    // Per-segment BL toggle (.meta v3): a segment flagged grow=0
                    // pins its nodes on the surface (no layer grows here).
                    auto git = g.meta.segGrowBL.find(nd.segId);
                    if (git != g.meta.segGrowBL.end() && git->second == 0)
                        nd.skipBL = true;
                    auto it = g.meta.segBc.find(nd.segId);
                    if (it != g.meta.segBc.end() && !it->second.empty()) nd.bcTag = it->second;
                    auto kit = g.meta.segKind.find(nd.segId);
                    if (kit != g.meta.segKind.end()) nd.curveKind = curveKindFromString(kit->second);
                }
                // No per-segment .meta BC on this node -> use the geometry's own
                // wall BC (its per-geometry override, or the global bcGeom). This
                // gives each geometry an individual wall BC instead of one shared
                // global value, while a per-segment .meta tag still wins above.
                if (nd.bcTag.empty()) nd.bcTag = config.bcFor(g.file);
                boundaryIds.push_back(nd.id);
            }
            allBoundaryIds.push_back(boundaryIds);
            growModes.push_back(g.isDomainWall ? 1 : -1);
            blParamsPerLoop.push_back(g.bl);
        }
        if (taggedCorners > 0)
            std::cout << "  - Surface metadata     : " << taggedCorners << " corner node(s) tagged\n";
        if (domainIsWall)
            std::cout << "  - Internal flow        : domain wall grows BL inward\n";

        // Report the analytic-curve coverage and sanity-check a fit (diagnostic).
        {
            int nLine = 0, nCircle = 0, nSmooth = 0, nPoly = 0;
            for (const auto& nd : mesh.nodes) {
                if (nd.type != NodeType::Boundary || nd.geomId < 0) continue;
                switch (nd.curveKind) {
                    case CurveKind::Line:   ++nLine; break;
                    case CurveKind::Circle: ++nCircle; break;
                    case CurveKind::Smooth: ++nSmooth; break;
                    default:                ++nPoly; break;
                }
            }
            if (nLine + nCircle + nSmooth > 0) {
                std::cout << "  - Surface curve model  : line=" << nLine
                          << " circle=" << nCircle << " smooth=" << nSmooth
                          << " polyline=" << nPoly << "\n";
                for (const auto& g : inputs) {
                    if (!g.meta.valid) continue;
                    std::vector<Point2D> circPts;
                    for (size_t pi = 0; pi < g.points.size(); ++pi) {
                        auto kit = g.meta.segKind.find(g.meta.segId[pi]);
                        if (kit != g.meta.segKind.end() && kit->second == "circle")
                            circPts.push_back(g.points[pi]);
                    }
                    if (circPts.size() >= 3) {
                        CircleCurve cc(circPts);
                        if (cc.valid())
                            std::cout << "      * circle fit           : r=" << cc.radius()
                                      << " center=(" << cc.center().x << ", " << cc.center().y << ")\n";
                        break;
                    }
                }
            }
        }

        try {
            lastH = blGen.generate(allBoundaryIds, growModes, blParamsPerLoop);
        } catch (const std::exception& e) {
            LOG_ERROR(e.what());
            std::cerr << "Proceeding to export partial mesh for debugging..." << std::endl;
            blSuccess = false;
            failExit = EXIT_ERR_BL;
        }

        // 載入加密種子 (seeds)：僅供遠場 Gmsh 使用，不進邊界層、也不當域邊界。
        // size/radius 若未指定 (含全域預設仍為負) 交由 Gmsh 端自動推得。
        std::vector<SeedGeom> seeds;
        const int seedRequested = static_cast<int>(config.seedFiles.size());
        for (const auto& spec : config.seedFiles) {
            bool closed = false;
            std::vector<Point2D> pts = loadGeometry(spec.file, &closed);
            if (pts.empty()) {
                // Loud (not silent): a specified seed that can't be loaded means
                // the mesh is generated WITHOUT the intended refinement.
                LOG_ERROR("Refinement seed '" << spec.file
                          << "' could not be loaded (missing or empty); it will NOT refine the mesh.");
                continue;
            }
            SeedGeom s;
            s.points = pts;
            s.closed = closed;
            s.size = (spec.size > 0) ? spec.size : config.seedSize;
            s.radius = (spec.radius > 0) ? spec.radius : config.seedRadius;
            int m = (spec.mode >= 0) ? spec.mode : config.seedMode;
            s.embed = (m == 1);
            seeds.push_back(s);
        }
        if (seedRequested > 0) {
            std::cout << "  - Refinement seeds     : " << seeds.size()
                      << " of " << seedRequested << " loaded\n";
            if (static_cast<int>(seeds.size()) < seedRequested)
                LOG_ERROR((seedRequested - static_cast<int>(seeds.size()))
                          << " of " << seedRequested
                          << " refinement seed(s) failed to load; mesh generated WITHOUT that refinement.");
        }

        if (blSuccess) {
            bool gmshOk = mesh.generateFarFieldGmsh(config, lastH, seeds, &gmshVersion);
            if (!gmshOk) {
                // Gmsh threw or produced an empty mesh (already reported inside).
                // Do NOT export an empty/partial far-field as if it succeeded.
                blSuccess = false;
                failExit = EXIT_ERR_GMSH;
            } else if (config.blSmoothingIters > 0) {
                mesh.smoothMesh(config.blSmoothingIters);
            }
        }

        if (!blSuccess) {
            hasIntersection = true; // trigger a nonzero exit later (see failExit)
        }
    }

    std::cout << "\n[ Mesh Statistics ]\n";
    std::cout << "  - Vertices (VRT)       : " << mesh.nodes.size() << "\n";
    std::cout << "  - Elements (CEL)       : " << mesh.elements.size() << "\n";
    std::cout << "  - Boundary Edges (BND) : " << mesh.edges.size() << "\n\n";

    // Strip a trailing ".vtk"/known extension to a provenance basename.
    auto stripExt = [](std::string s) {
        size_t dot = s.find_last_of('.');
        size_t slash = s.find_last_of("/\\");
        if (dot != std::string::npos && (slash == std::string::npos || dot > slash))
            s.erase(dot);
        return s;
    };

    if (config.exportVTK) {
        std::string vtkFile = outputFilename;
        if (!blSuccess) {
            size_t dotPos = vtkFile.find_last_of('.');
            if (dotPos != std::string::npos) {
                vtkFile.insert(dotPos, "_er");
            } else {
                vtkFile += "_er.vtk";
            }
        } else {
            if (vtkFile.find('.') == std::string::npos) vtkFile += ".vtk";
        }
        mesh.exportVTK(vtkFile);
        hybmesh::writeProvenance(stripExt(vtkFile), config, inputFiles, gmshVersion,
                                 mesh.nodes.size(), mesh.elements.size());
        std::cout << "Mesh saved to: " << vtkFile << std::endl;
    }

    if (config.exportStarCD) {
        std::string starCDPrefix = outputFilename;
        if (starCDPrefix.length() > 4 && starCDPrefix.substr(starCDPrefix.length() - 4) == ".vtk") {
            starCDPrefix = starCDPrefix.substr(0, starCDPrefix.length() - 4);
        }
        mesh.exportStarCD(starCDPrefix, config);
        hybmesh::writeProvenance(starCDPrefix, config, inputFiles, gmshVersion,
                                 mesh.nodes.size(), mesh.elements.size());
        std::cout << "StarCD mesh saved to: " << starCDPrefix << ".*" << std::endl;
    }

    if (config.exportCGNS) {
        std::string cgnsFile = outputFilename;
        if (cgnsFile.length() > 4 && cgnsFile.substr(cgnsFile.length() - 4) == ".vtk")
            cgnsFile = cgnsFile.substr(0, cgnsFile.length() - 4);
        cgnsFile += ".cgns";
        mesh.exportCGNS(cgnsFile, config);
        hybmesh::writeProvenance(stripExt(cgnsFile), config, inputFiles, gmshVersion,
                                 mesh.nodes.size(), mesh.elements.size());
    }

    if (failExit != EXIT_OK)
        return reportError(failExit);
    // Backward-compat: any other unclassified stop still returns a nonzero code.
    return hasIntersection ? EXIT_ERR_BL : EXIT_OK;
}
