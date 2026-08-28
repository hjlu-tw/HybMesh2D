#include "Cli.hpp"
#include "Mesh.hpp"
#include "Config.hpp"
#include "BoundaryLayer.hpp"
#include "Logger.hpp"
#include "Provenance.hpp"
#include "ExitCodes.hpp"
#include "MeshMode.hpp"
#include "MbQuality.hpp"
#include "MultiBlock.hpp"
#include "PointTolerance.hpp"
#include <iostream>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <cstdint>
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

    // 如果起點與終點重合 (或近乎重合)，移除最後一個點以避免產生重疊的邊界節點，
    // 這會導致法向量計算錯誤。
    //
    // 容差取接縫兩側「實際的點距」，而不是固定的 1e-6：重取樣是逐段獨立進行的，
    // 首段起點與末段終點對不齊時會留下一個比鄰邊小上數個數量級的接縫邊 (實測
    // 3.8e-5 對 0.05，相差 1300 倍)。固定容差抓不到它，於是這條 sliver 邊會進到
    // 封閉迴圈裡，造成兩個很難診斷的症狀：
    //   * 邊界層在接縫處自交 (內流域尤其明顯，前緣往內長就撞在一起)；
    //   * 外形在接縫處自我相交，Gmsh 於該處三角化時停不下來 (看起來像當掉)。
    // 5% 的鄰邊長度是安全的門檻：真正開放的曲線，兩端不會落在一個點距的 5% 內。
    if (points.size() > 1) {
        const double gap = (points.front() - points.back()).length();
        double span = 0.0;   // local point spacing either side of the seam
        double tol = 1e-6;
        if (points.size() > 2) {
            span = std::min((points[1] - points[0]).length(),
                            (points[points.size() - 1] - points[points.size() - 2]).length());
            if (span > 0.0)
                tol = std::max(tol, hybmesh::POINT_COINCIDENCE_FRACTION * span);
        }
        if (gap <= tol) {
            points.pop_back();
            if (closed) *closed = true;
            // Silent only when the file was already exactly closed; a real gap that
            // we welded is a defect in the upstream geometry and must be visible.
            if (gap > 0.0)
                LOG_WARN("Geometry file '" << filename << "' is not exactly closed: the first "
                         "and last points are " << gap << " apart against a local point spacing "
                         "of " << span << ". The seam was welded; fix it upstream so no sliver "
                         "edge is produced there.");
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

// <case> length cap, in UTF-8 code points. results/meshes/<case>/mesh_<case>.vtk
// puts <case> in a single path component, which must stay inside the 255-byte
// NAME_MAX; 60 code points is safe even for 4-byte sequences.
static const size_t CASE_NAME_MAX_LEN = 60;

// Clamp a <case> label so the per-case output path is writable. A many-body run
// joins every boundary stem and easily runs past NAME_MAX, which would make
// create_directories and every export fail. Keep a readable prefix and
// disambiguate with an FNV-1a digest of the full name.
//
// MUST match MeshConfig.clamp_case_name (tools/PreProcessor/gui/app/models/
// mesh_config.py): the GUI looks for the mesh at the path computed there, so a
// divergence means "expected VTK file not found" after a successful run.
static std::string clampCaseName(const std::string& name) {
    // Count code points, not bytes, so the cut matches Python's str slicing.
    size_t nchars = 0;
    for (unsigned char c : name)
        if ((c & 0xC0) != 0x80) ++nchars;   // skip UTF-8 continuation bytes
    if (nchars <= CASE_NAME_MAX_LEN) return name;

    uint32_t h = 0x811C9DC5u;               // FNV-1a over the full name
    for (unsigned char c : name) {
        h ^= c;
        h *= 0x01000193u;
    }
    const size_t keep = CASE_NAME_MAX_LEN - 9;   // room for '_' + 8 hex digits
    size_t cut = 0, seen = 0;
    while (cut < name.size() && seen < keep) {
        ++cut;
        while (cut < name.size() && (static_cast<unsigned char>(name[cut]) & 0xC0) == 0x80)
            ++cut;                          // keep whole code points
        ++seen;
    }
    std::ostringstream oss;
    oss << name.substr(0, cut) << "_" << std::hex << std::setfill('0')
        << std::setw(8) << h;
    return oss.str();
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
    std::map<std::string, std::string> groupBc;  // trailer "GROUP_BC <label> <bc_type>": per-segment grouping label -> physical BC type (GUI-written; merged into Config.groupBc by the caller)
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
    // GUI-only trailer after the POINTS block: "GROUP_BC <label> <bc_type>" lines
    // mapping a per-segment grouping label to its physical BC type. The GUI
    // persists this label->BC map ONLY here (not always in the config .dat), so
    // without reading it a geometry whose .meta tags segments with grouping labels
    // resolves every patch to the wall default — BC lost for ALL-BL, no-BL and
    // partial-BL alike. Parsed with the stream extractor (whitespace-delimited);
    // non-GROUP_BC tokens are skipped. The caller merges m.groupBc into
    // Config.groupBc so resolveGroupBc() finds the mapping.
    {
        std::string t;
        while (ifs >> t) {
            if (t == "GROUP_BC") {
                std::string name, type;
                if (ifs >> name >> type) m.groupBc[name] = type;
            }
        }
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
        // The edge's source segment travels with its BC, so the exporter can give
        // each distinct segment its own patch id (segm_no) even when several share
        // a BC name.
        mesh.addTaggedEdge(ids[i], ids[(i + 1) % n], edgeBc[i],
                           Mesh::makeSegKey(geomId, useMeta ? meta.segId[i] : -1));
        mesh.addElement({ids[i], ids[(i + 1) % n]}); // 視覺化用
    }
    return ids;
}

// The multi-block adapter (MESH_MODE 1): read the topology document, ask the
// decision layer for a mesh, write what comes back into the container.
//
// Deliberately NOT a seam of its own. Every boundary edge comes back already
// resolved — node pair, BC name and source segment together — so there is no
// classification, no tolerance and no decision left here; giving this a seam
// would concede that it has logic. Everything worth testing about this path is
// external behaviour of hybmesh::buildMultiBlock, which a test drives with a
// topology document and no mesh at all.
//
// Returns EXIT_OK, or the code the caller should exit with (nothing is exported
// after a non-zero return: an invalid declaration is "fix your JSON", which is
// what EXIT_ERR_TOPOLOGY exists to say).
// One banner row's label column: 25 characters, then ": ". Every row of both
// multi-block blocks goes through this; there used to be a second copy of the pad
// expression inline in the topology banner.
static std::string mbLabel(const std::string& prefix, const std::string& text) {
    const std::string l = prefix + text;
    return l + std::string(l.size() < 25 ? 25 - l.size() : 0, ' ') + ": ";
}
static std::string mbRow(const std::string& text) { return mbLabel("  - ", text); }
// A per-wall detail row is indented WITHOUT a bullet, so it reads as detail under
// the summary line above it rather than as another number beside it.
static std::string mbSub(const std::string& text) { return mbLabel("      ", text); }

// Print the quality report. Split out of the adapter because the adapter's whole
// character is "a loop with no decisions in it", and eleven lines of formatting
// was on its way to obscuring the one decision it does now make (the exit code).
static void printMbQuality(const hybmesh::MbQualityReport& q) {
    std::ostringstream sci;
    sci << std::scientific << std::setprecision(3);
    auto num = [&sci](double v) { sci.str(""); sci << v; return sci.str(); };
    auto rel = [](double v) {
        // NEGATIVE means not measured, and it must not print as a percentage —
        // "0.00%" is an excellent result and would be a false claim here. See
        // MbQualityReport.
        if (v < 0.0) return std::string("not measured");
        std::ostringstream os;
        os << std::fixed << std::setprecision(2) << (100.0 * v) << "%";
        return os.str();
    };

    std::cout << "\n[ Multi-block Mesh Quality ]\n";
    std::cout << mbRow("Inverted cells") << q.invertedCells << " of " << q.cells
              << " cells\n";
    if (q.nonOrthoSamples == 0) {
        std::cout << mbRow("Non-orthogonality")
                  << "not measured (no structured block in the result)\n";
    } else {
        std::ostringstream ang;
        ang << std::fixed << std::setprecision(3)
            << "max " << q.maxNonOrthoDeg << " deg, mean " << q.meanNonOrthoDeg << " deg";
        std::cout << mbRow("Non-orthogonality") << ang.str() << " (over "
                  << q.nonOrthoSamples << " structured-cell corners)\n";
    }
    if (q.worstWallRelError < 0.0)
        std::cout << mbRow("Wall first cell")
                  << "not measured (no block side declares a measurable one)\n";
    else
        std::cout << mbRow("Wall first cell") << "worst " << rel(q.worstWallRelError)
                  << " off the height the declaration asks for\n";
    for (const hybmesh::MbWallHeight& w : q.walls)
        std::cout << mbSub(std::string(w.side) + " '" + w.edgeId + "'")
                  << "asked " << num(w.requestedLo) << " .. " << num(w.requestedHi)
                  << ", got " << num(w.achievedMin) << " .. " << num(w.achievedMax)
                  << " (" << rel(w.worstRelError) << ")\n";

    // One machine-readable line, in the shape of the HYBMESH_ERROR convention, so
    // the acceptance gate this instrument exists for is a grep rather than a prose
    // parse. Each of the three measured figures is NEGATIVE when it could not be
    // measured, never 0 — see MbQualityReport.
    std::ostringstream mr;
    mr << std::setprecision(6) << std::fixed;
    mr << "HYBMESH_MB_QUALITY cells=" << q.cells
       << " inverted=" << q.invertedCells
       << " nonortho_max_deg=" << q.maxNonOrthoDeg
       << " nonortho_mean_deg=" << q.meanNonOrthoDeg
       << " wall_first_cell_worst_rel=" << q.worstWallRelError;
    std::cout << mr.str() << std::endl;
}

static int buildMultiBlockMesh(Mesh& mesh, Config& config,
                               std::vector<std::string>& inputFiles) {
    if (config.topologyFile.empty()) {
        LOG_ERROR("MESH_MODE " << MESH_MODE_MULTIBLOCK << " ("
                  << hybmesh::meshModeName(MESH_MODE_MULTIBLOCK)
                  << ") fills a DECLARED block topology, and MESH_TOPOLOGY_FILE names "
                     "no document. Nothing was meshed or exported.");
        return EXIT_ERR_TOPOLOGY;
    }
    std::ifstream tin(config.topologyFile);
    if (!tin) {
        LOG_ERROR("Topology file '" << config.topologyFile
                  << "' could not be opened. Nothing was meshed or exported.");
        return EXIT_ERR_TOPOLOGY;
    }
    std::stringstream buf;
    buf << tin.rdbuf();
    // The topology decides this mesh as much as the geometry does, so it is an
    // INPUT for provenance purposes.
    inputFiles.push_back(config.topologyFile);

    // The loaded geometries, each with the two facts its '.meta' sidecar carries
    // that a topology attaches to: which source segment every point belongs to,
    // and what boundary condition label each segment holds.
    //
    // A geometry that will not load is still a WARNING here and not a refusal —
    // the opposite of the hybrid path's answer, and right for the same reason:
    // there the geometry IS the mesh, here a topology may legitimately refer to
    // none of them, so refusing would stop a mesh that does not depend on the
    // file. What changed with geometry binding is that a declaration REFERRING to
    // such a file is now refused by name, inside the seam, where the reference is
    // visible.
    std::vector<hybmesh::MbGeometry> geoms;
    for (const auto& f : config.geomFiles) {
        hybmesh::MbGeometry g;
        g.file = f;
        LoadStatus st = LoadStatus::Ok;
        bool closed = false;
        g.points = loadGeometry(f, &closed, &st);
        g.closed = closed;
        if (g.points.empty()) {
            LOG_WARN("Geometry '" << f << "' could not be loaded ("
                     << (st == LoadStatus::CannotOpen ? "cannot open" : "no usable points")
                     << "). A topology need not refer to any geometry, so the mesh is "
                        "unaffected unless a corner or an edge names this file — and "
                        "then it is refused by name.");
        } else {
            SurfaceMeta meta = loadSurfaceMeta(f);
            reconcileMeta(meta, g.points.size(), f);
            if (meta.valid) {
                g.segId = meta.segId;
                g.pieceBreaks = meta.pieceBreaks;
                g.segBc = meta.segBc;
                // The label -> physical BC type map the GUI persists in the sidecar
                // trailer. Merged into the config exactly as the hybrid path does it,
                // and for the same reason: the seam emits a grouping LABEL, and
                // `Config::resolveGroupBc` is the ONE place that turns one into the BC
                // type the exporter writes. Resolving it inside the seam instead would
                // put a second resolver in the chain, which is how the two came to
                // disagree the last time. emplace() keeps an explicit config mapping.
                for (const auto& kv : meta.groupBc) config.groupBc.emplace(kv.first, kv.second);
            }
        }
        geoms.push_back(std::move(g));
    }

    hybmesh::MbParams params;
    params.defaultBc = config.bcGeom;
    params.splitQuads = config.mbSplitQuads;

    const hybmesh::MbResult res = hybmesh::buildMultiBlock(buf.str(), geoms, params);
    // Warnings are DATA on the way out of the seam; saying them is this layer's job.
    for (const std::string& w : res.warnings)
        LOG_WARN("Topology '" << config.topologyFile << "': " << w);
    if (!res.ok) {
        LOG_ERROR("Topology '" << config.topologyFile << "': " << res.error);
        return EXIT_ERR_TOPOLOGY;
    }

    for (const Point2D& p : res.nodes) mesh.addNode(p, NodeType::Interior);
    for (const auto& c : res.cells) mesh.addElement(c.nodeIds);
    for (const auto& be : res.boundaryEdges) {
        // A synthetic carrier node, because recordBoundaryEdge takes the whole
        // source Node: its convention is "an edge belongs to the segment of its
        // starting point", and here the seam has already resolved BC and segment
        // PER EDGE, so there is no starting point left to consult.
        Node carrier{};
        carrier.bcTag = be.bc;
        carrier.geomId = be.geomId;
        carrier.segId = be.segId;
        mesh.recordBoundaryEdge(be.v1, be.v2, carrier);
        // Also as a tagged edge, so the boundary-edge statistic and every reader
        // of `edges` see the same boundary the exporter classifies. One loop, one
        // source: the two cannot describe different boundaries.
        mesh.addTaggedEdge(be.v1, be.v2, be.bc, Mesh::makeSegKey(be.geomId, be.segId));
        for (int v : {be.v1, be.v2}) mesh.nodes[static_cast<size_t>(v)].type = NodeType::Boundary;
    }

    std::cout << "\n[ Multi-block Topology ]\n";
    std::cout << "  - Source               : " << config.topologyFile << "\n";
    for (const auto& b : res.blocks)
        std::cout << mbRow("Block '" + b.id + "'") << b.ni << " x " << b.nj << " nodes\n";
    std::cout << "  - Cells                : " << res.cells.size() << " "
              << (config.mbSplitQuads ? "triangles (alternating diagonal by index parity)"
                                      : "quads (splitting is OFF)") << "\n";

    // WHERE EACH BOUNDARY CONDITION CAME FROM. The whole claim of this path is
    // that a condition is declared rather than discovered, and a claim a run
    // cannot show is one nobody can check: each row names the BC and the source
    // segment it was read off, or says plainly that it is the config default.
    // Grouped in first-seen order, which is the counter-clockwise perimeter walk,
    // so the rows read around the block.
    {
        struct Patch { std::string bc; int geomId; int segId; size_t faces; };
        std::vector<Patch> patches;
        for (const auto& be : res.boundaryEdges) {
            bool merged = false;
            for (auto& p : patches) {
                if (p.bc != be.bc || p.geomId != be.geomId || p.segId != be.segId) continue;
                ++p.faces;
                merged = true;
                break;
            }
            if (!merged) patches.push_back({be.bc, be.geomId, be.segId, 1});
        }
        for (const auto& p : patches) {
            std::string from = "the config default (no source segment declared)";
            if (p.segId >= 0 && p.geomId >= 0
                && static_cast<size_t>(p.geomId) < geoms.size())
                from = "segment " + std::to_string(p.segId) + " of '"
                     + geoms[static_cast<size_t>(p.geomId)].file + "'";
            // The name reported is the RESOLVED BC TYPE, the same string the
            // exporter writes as the patch name — not the sidecar's grouping
            // label. Reporting the label here named something that appears
            // nowhere in the exported grid, which is the label/type namespace
            // confusion that produced this repo's most expensive bug class. The
            // label is still worth seeing when it differs, because it is what the
            // geometry actually carries, so it is named beside the type.
            const std::string type = config.resolveGroupBc(p.bc);
            std::cout << mbRow("Boundary '" + type + "'") << p.faces
                      << " edge(s), from " << from
                      << (type == p.bc ? std::string()
                                       : " (label '" + p.bc + "')") << "\n";
        }
    }

    // ── The mesh-quality report (issue #51) ─────────────────────────────────
    // Printed on EVERY run of this path, not only on a bad one: three of the four
    // numbers are a baseline the later elliptic-smoothing increment is judged
    // against, and a baseline that is only recorded when something went wrong is
    // not a baseline. The measuring itself is the pure instrument next door; this
    // layer only says what came back and decides the exit code.
    const hybmesh::MbQualityReport q = hybmesh::measureMbQuality(res);
    printMbQuality(q);

    if (q.invertedCells > 0) {
        LOG_ERROR(q.invertedCells << " of " << q.cells << " cells are INVERTED (a corner "
                  "that folds back on itself). The mesh is EXPORTED anyway, following the "
                  "same precedent as a failed boundary layer, for the practical reason that "
                  "an inverted cell is far easier to fix once you can look at it. The "
                  "declaration itself is valid — its block corners wind correctly — so what "
                  "folded is the interpolated interior, not the document.");
        return EXIT_ERR_INVERTED;
    }
    return EXIT_OK;
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
        // segKey -1: a generated box side has no SOURCE segment, so the exporter
        // groups it by BC name. Passed explicitly rather than left to a default,
        // because that is the fact and not an omission.
        mesh.addTaggedEdge(domainNodeIds[i], domainNodeIds[(i + 1) % 4],
                           domainBcTags[i], -1);
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

int hybmesh::runCli(int argc, char* argv[]) {
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

    // ".*" is the GUI's "whichever formats are enabled" placeholder — its Output
    // field shows results/meshes/<case>/mesh_<case>.* — and it reaches us verbatim
    // through a saved config, a pipeline script or -out_name. It is a WILDCARD, not
    // an extension: extPos() below finds that dot, so ".vtk" was never appended and
    // the VTK was written into a file literally NAMED "mesh_<case>.*" (and, before
    // stripExt existed, a "mesh_<case>.*.vrt" STAR-CD set beside it — those files
    // are still findable on disk). Stripped once here, before validate()/print(),
    // so the banner, the provenance sidecar and every writer share one basename.
    // An empty remainder falls through to the auto-generated name below.
    if (config.outputFilename.size() >= 2 &&
        config.outputFilename.compare(config.outputFilename.size() - 2, 2, ".*") == 0) {
        config.outputFilename.erase(config.outputFilename.size() - 2);
    }

    // Validate/clamp config ranges after the config load + all CLI overrides.
    // A contradiction that cannot be clamped (empty domain span) is fatal.
    if (!config.validate()) {
        LOG_ERROR("Configuration failed validation (see warnings above).");
        return reportError(EXIT_ERR_CONFIG, "validation");
    }

    config.print();

    // A parameter the active mode never reads is NAMED. One line per key, and the
    // list is data (include/MeshMode.hpp) rather than prose here, so the GUI's
    // per-field `modes=` declaration can be compared against it in both directions.
    // Emitted after the banner so the banner still reports the config verbatim,
    // and before the refusal below so a user sees both in one run.
    for (const std::string& key : hybmesh::inertParamsSet(config)) {
        LOG_WARN("MESH_MODE " << config.meshMode << " ("
                 << hybmesh::meshModeName(config.meshMode) << ") never reads '"
                 << key << "'; the value set for it has no effect on this mesh.");
    }

    Mesh mesh;

    // Auto output paths are per-case: results/meshes/<case>/mesh_<case>.vtk so
    // each run lands in its own subdirectory instead of cluttering the top level.
    std::string outputFilename = "results/meshes/cartesian/mesh_cartesian.vtk";
    if (!config.outputFilename.empty()) {
        outputFilename = config.outputFilename;
    } else if (!config.geomFiles.empty()) {
        // Case name from the boundary stems: single body -> its stem, several ->
        // their stems joined by '_'. Must match the GUI's MeshConfig.auto_case_name
        // (mesh_config.py) so the GUI can locate the file we write.
        std::string caseName;
        for (const auto& f : config.geomFiles) {
            if (!caseName.empty()) caseName += "_";
            caseName += fs::path(f).stem().string();
        }
        // Clamped (see clampCaseName): a many-body join would otherwise exceed
        // NAME_MAX and make every write below fail.
        caseName = clampCaseName(caseName);
        outputFilename = "results/meshes/" + caseName + "/mesh_" + caseName + ".vtk";
    }

    // Ensure the output directory exists so VTK/STAR-CD exports do not silently
    // vanish on a fresh clone or case-sensitive filesystem. This is fatal: if the
    // directory cannot be created, every export below fails too, and continuing
    // would exit 0 with no mesh anywhere on disk.
    {
        fs::path outParent = fs::path(outputFilename).parent_path();
        if (!outParent.empty()) {
            std::error_code ec;
            fs::create_directories(outParent, ec);
            if (ec && !fs::is_directory(outParent)) {
                LOG_ERROR("Cannot create output directory '"
                          << outParent.string() << "': " << ec.message());
                return reportError(EXIT_ERR_EXPORT, outParent.string());
            }
        }
    }

    bool hasIntersection = false;
    bool blSuccess = true;
    int failExit = EXIT_OK;                 // set to a distinct code on failure
    std::string failDetail;                 // optional detail for that code's machine line
    std::string gmshVersion;                // resolved for provenance
    std::vector<std::string> inputFiles;    // geometry inputs for provenance
    for (const auto& f : config.geomFiles) inputFiles.push_back(f);
    if (!config.domainFile.empty()) inputFiles.push_back(config.domainFile);
    // Declared to survive into this mode, but not read by it YET. A different
    // sentence from the one above on purpose: an inert value will never be read
    // here, while one of these is waiting for the wall-normal clustering law and
    // is worth keeping. Both exist for one reason — a value the run does not read
    // must be NAMED rather than silently do nothing.
    for (const std::string& key : hybmesh::blSurvivorsUnread(config)) {
        LOG_WARN("MESH_MODE " << config.meshMode << " ("
                 << hybmesh::meshModeName(config.meshMode) << ") does not read '"
                 << key << "' yet; every topology edge declares its own point count "
                    "and spacing law in this release, so the value set for it has no "
                    "effect on this mesh.");
    }

    if (config.meshMode == MESH_MODE_MULTIBLOCK) {
        // The second generation path. It shares this function's export block and
        // nothing else: no domain box, no boundary layer, no far field, and Gmsh
        // is used nowhere — the whole domain is blocked by declaration.
        int rc = buildMultiBlockMesh(mesh, config, inputFiles);
        // A detail that is never empty: with no MESH_TOPOLOGY_FILE declared the
        // path is "", and a machine-readable line naming nothing is one a script
        // cannot act on.
        const std::string topoDetail = config.topologyFile.empty()
                                     ? std::string("(no MESH_TOPOLOGY_FILE)")
                                     : config.topologyFile;
        if (rc == EXIT_ERR_INVERTED) {
            // The one outcome on this path that EXPORTS AND FAILS, and the whole
            // reason there are two multi-block exit codes rather than one. It goes
            // through the same `failExit` mechanism a failed boundary layer uses,
            // so the difference between the two failure kinds is where the code is
            // set and not a second way of stopping.
            //
            // `blSuccess` is deliberately left TRUE, so the VTK keeps its ordinary
            // name: the `_er` suffix marks a PARTIAL mesh, and this one is complete
            // — it is the cell shapes that are wrong, which is the thing the export
            // exists to let you look at.
            failExit = EXIT_ERR_INVERTED;
            failDetail = topoDetail;
        } else if (rc != EXIT_OK) {
            return reportError(rc, topoDetail);
        }
    } else if (config.geomFiles.empty() && config.seedFiles.empty() && config.domainFile.empty()) {
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
        double lastH = config.bl.blInitialThickness;

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

        // Merge each geometry's .meta GROUP_BC trailer (grouping label -> physical
        // BC type) into the config resolution map, so a per-segment label resolves
        // even when the config .dat carried no GROUP_BC lines (the GUI persists the
        // map in the .meta trailer, which the mesher otherwise never reads). This is
        // what makes per-segment BC survive in EVERY case — all-BL, no-BL, partial.
        // emplace() keeps any explicit config .dat mapping (it takes precedence).
        for (const auto& g : inputs)
            for (const auto& kv : g.meta.groupBc)
                config.groupBc.emplace(kv.first, kv.second);

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

        if (config.bl.blAutoTransitionLayers == 1) {
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
            // BL/no-BL junction corner ownership fix: the resampler gives a shared
            // corner to the segment STARTING there, so at a BL->no-BL corner the
            // vertex lands on the no-BL segment (skipBL) and the BL would stop one
            // surface point short of the corner. Promote such a corner (a tagged
            // corner that is skipBL but has a BL neighbour) back into the BL region so
            // the layer reaches the actual corner vertex — symmetric with the
            // no-BL->BL corner, which the resampler already gives to the BL segment.
            // isCorner is required so an interior no-BL point next to the BL corner is
            // NOT promoted (only the shared vertex is).
            if (g.meta.valid) {
                int nb = static_cast<int>(boundaryIds.size());
                for (int i = 0; i < nb; ++i) {
                    Node& cn = mesh.nodes[boundaryIds[i]];
                    if (!cn.skipBL || !cn.isCorner) continue;
                    bool prevBL = !mesh.nodes[boundaryIds[(i - 1 + nb) % nb]].skipBL;
                    bool nextBL = !mesh.nodes[boundaryIds[(i + 1) % nb]].skipBL;
                    if (prevBL || nextBL) cn.skipBL = false;
                }
            }
            // Record the per-edge wall BC now, while the boundary ORDER is known.
            // A boundary edge is a per-EDGE quantity: edge i belongs to the segment
            // of its starting node boundaryIds[i] (same convention as addTaggedLoop's
            // edgeBc[i] for far-field / no-BL loops). BL-grown surfaces don't add
            // their wall edges to mesh.edges, so without this the exporter could only
            // guess an edge's BC from whether its two endpoints agree — which fails
            // for the edge ending at a segment junction (endpoints on different
            // segments), dropping it to the wall default. This tags it directly.
            {
                int nb = static_cast<int>(boundaryIds.size());
                for (int i = 0; i < nb; ++i) {
                    int a = boundaryIds[i], b = boundaryIds[(i + 1) % nb];
                    // The starting node carries both halves: the BC tag, and the
                    // source segment the exporter needs for a distinct segm_no
                    // (which is also what lets a no-BL run keep its BC after the
                    // BL front drops absorbed nodes — collectBcRefSegs reads it).
                    mesh.recordBoundaryEdge(a, b, mesh.nodes[a]);
                }
            }
            allBoundaryIds.push_back(boundaryIds);
            growModes.push_back(g.isDomainWall ? 1 : -1);
            blParamsPerLoop.push_back(g.bl);
        }
        if (taggedCorners > 0)
            std::cout << "  - Surface metadata     : " << taggedCorners << " corner node(s) tagged\n";
        if (domainIsWall)
            std::cout << "  - Internal flow        : domain wall grows BL inward\n";

        // A GROUP_BC entry whose label NO segment carries resolves to nothing, and
        // every patch then silently falls back to the wall default. The label lives in
        // the .meta NSEGMENTS bc column while the label->type map lives in the .meta
        // trailer / config, and only the trailer survives a re-resample (saveMetadata
        // rewrites the NSEGMENTS block from the pipeline config, where BCs are a
        // later, mesh-stage edit). So re-resampling an already-BC-assigned geometry
        // leaves the map without its labels, and the whole mesh exports as `wall` —
        // indistinguishable, from the solver, from a boundary-condition bug. Say so
        // here, where both halves are in hand.
        if (!config.groupBc.empty()) {
            std::set<std::string> carried;
            for (const auto& nd : mesh.nodes)
                if (!nd.bcTag.empty()) carried.insert(nd.bcTag);
            std::vector<std::string> orphan;
            for (const auto& kv : config.groupBc)
                if (!carried.count(kv.first)) orphan.push_back(kv.first);
            if (!orphan.empty()) {
                std::ostringstream names;
                for (size_t i = 0; i < orphan.size(); ++i)
                    names << (i ? ", " : "") << orphan[i];
                bool all = orphan.size() == config.groupBc.size();
                LOG_WARN((all ? "NO boundary segment carries any of the "
                              : "Some GROUP_BC labels are unused: ")
                         << orphan.size() << " GROUP_BC label(s) mapped in this run ("
                         << names.str() << "). A label is stored per segment in the "
                         "geometry's .meta (NSEGMENTS bc column) and the mapping in its "
                         "trailer; re-resampling the geometry rewrites the former and "
                         "keeps the latter, so the map can outlive its labels. "
                         << (all ? "Every patch will therefore export as the wall "
                                   "default (" : "The affected patches fall back to (")
                         << config.bcGeom << "), whatever the config says. Re-apply the "
                         "per-segment BCs (GUI: Mesh > per-segment BC dialog, then OK) "
                         "and re-run.");
            }
        }

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

    // Extension position in the FILE NAME (npos when there is none). Must ignore a
    // dot in a directory component — a path like ~/.claude/out would otherwise get a
    // suffix spliced into the directory name and every export would fail to open.
    auto extPos = [](const std::string& s) -> size_t {
        size_t dot = s.find_last_of('.');
        size_t slash = s.find_last_of("/\\");
        if (dot == std::string::npos || (slash != std::string::npos && dot < slash))
            return std::string::npos;
        return dot;
    };

    // Strip a trailing ".vtk"/known extension to a provenance basename.
    auto stripExt = [&extPos](std::string s) {
        size_t dot = extPos(s);
        if (dot != std::string::npos) s.erase(dot);
        return s;
    };

    if (config.exportVTK) {
        std::string vtkFile = outputFilename;
        size_t dotPos = extPos(vtkFile);
        if (!blSuccess) {
            if (dotPos != std::string::npos) {
                vtkFile.insert(dotPos, "_er");
            } else {
                vtkFile += "_er.vtk";
            }
        } else {
            if (dotPos == std::string::npos) vtkFile += ".vtk";
        }
        mesh.exportVTK(vtkFile);
        hybmesh::writeProvenance(stripExt(vtkFile), config, inputFiles, gmshVersion,
                                 mesh.nodes.size(), mesh.elements.size());
        std::cout << "Mesh saved to: " << vtkFile << std::endl;
    }

    if (config.exportStarCD) {
        // stripExt, not a literal ".vtk": with `-out mesh_run.dat` the VTK branch above
        // treats .dat as the extension while this one found no ".vtk" to strip, so one
        // run wrote mesh_run + mesh_run.dat.vrt and handed writeProvenance two different
        // basenames — and left a .bnd that a `<base>.bnd` guess (the GUI auto-link,
        // run_case.sh) no longer finds.
        std::string starCDPrefix = stripExt(outputFilename);
        mesh.exportStarCD(starCDPrefix, config);
        hybmesh::writeProvenance(starCDPrefix, config, inputFiles, gmshVersion,
                                 mesh.nodes.size(), mesh.elements.size());
        std::cout << "StarCD mesh saved to: " << starCDPrefix << ".*" << std::endl;
    }

    if (config.exportCGNS) {
        std::string cgnsFile = stripExt(outputFilename) + ".cgns";
        mesh.exportCGNS(cgnsFile, config);
        hybmesh::writeProvenance(stripExt(cgnsFile), config, inputFiles, gmshVersion,
                                 mesh.nodes.size(), mesh.elements.size());
    }

    if (failExit != EXIT_OK)
        return reportError(failExit, failDetail);
    // Backward-compat: any other unclassified stop still returns a nonzero code.
    return hasIntersection ? EXIT_ERR_BL : EXIT_OK;
}
