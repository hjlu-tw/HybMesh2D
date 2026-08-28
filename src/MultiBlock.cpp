#include "MultiBlock.hpp"

#include "Spacing.hpp"   // the existing spacing laws, shared rather than re-implemented
#include "json.hpp"      // the repo's bundled header-only parser (nlohmann 3.12)

#include <algorithm>
#include <cmath>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <vector>

using nlohmann::json;

namespace {

// The topology document's OWN version, independent of the pipeline script's:
// the two evolve at unrelated rates, so coupling them would force a bump of one
// every time the other moved.
constexpr int kFormatVersion = 1;

// ── The parsed document ───────────────────────────────────────────────────
// Kept as a corner/edge/block hierarchy rather than as fixed-size arrays of 2D
// points. No 3D code is written here, but the shape is what makes a later 3D
// generalization a change rather than a rewrite.

struct Corner {
    std::string id;
    Point2D xy{0.0, 0.0};
    // Geometry attachment (kind "on_geometry"); `geom` empty for a free corner,
    // whose declared `xy` IS its position.
    //
    // The position is a NORMALIZED ARC LENGTH along one source segment and never
    // a point index. The workflow this tool is built for is edit CAD, re-resample,
    // re-mesh — and re-resampling changes the point count, so an index binding
    // would silently relocate every attached corner on each resample and produce a
    // slightly wrong mesh with no error at all.
    std::string geom;
    int seg = -1;
    double t = 0.0;
    int geomIdx = -1;        // filled once `geom` is resolved against the loaded list
};

struct EdgeSpec {
    std::string id;
    std::string a, b;        // corner ids, in the edge's own direction
    std::string kind;        // "wall" | "interface" | "cut"
    int count = 0;           // node count along the edge (>= 2)
    std::string law = "uniform";
    double growth = 1.0;     // "geometric"
    double delta = 0.0;      // "tanh"
    // The source segment this edge LIES ON ("binding"); `bindGeom` empty for an
    // unbound edge. Every boundary edge generated along a bound edge carries that
    // segment's own BC label and its (geometry, segment) key, so the condition is
    // in the declaration before a single node exists and nothing downstream has to
    // re-derive it from a position.
    std::string bindGeom;
    int bindSeg = -1;
};

struct BlockSpec {
    std::string id;
    std::vector<std::string> edges;   // exactly 4, in [south, east, north, west]
};

// ── Schema helpers ────────────────────────────────────────────────────────
//
// Unknown keys are REFUSED, not ignored. A typo'd `"spacng"` that is skipped
// silently produces a mesh with the wrong node distribution and no symptom
// except a mesh nobody asked for — the same failure class the mesher's
// inert-parameter warning exists to close. Strict now is relaxable later; the
// reverse is a breaking change.
bool rejectUnknownKeys(const json& obj, const char* where,
                       const std::vector<std::string>& allowed, std::string& err) {
    for (auto it = obj.begin(); it != obj.end(); ++it) {
        if (std::find(allowed.begin(), allowed.end(), it.key()) != allowed.end()) continue;
        std::ostringstream os;
        os << where << ": unknown key '" << it.key() << "'. Accepted here: ";
        for (size_t k = 0; k < allowed.size(); ++k)
            os << (k ? ", " : "") << "'" << allowed[k] << "'";
        os << ".";
        err = os.str();
        return false;
    }
    return true;
}

bool requireString(const json& obj, const char* key, const char* where,
                   std::string& out, std::string& err) {
    auto it = obj.find(key);
    if (it == obj.end() || !it->is_string() || it->get<std::string>().empty()) {
        err = std::string(where) + ": '" + key + "' must be a non-empty string.";
        return false;
    }
    out = it->get<std::string>();
    return true;
}

bool requireArray(const json& doc, const char* key, const json*& out, std::string& err) {
    auto it = doc.find(key);
    if (it == doc.end() || !it->is_array() || it->empty()) {
        err = std::string("'") + key + "' must be a non-empty array.";
        return false;
    }
    out = &(*it);
    return true;
}

// ── Parsing ───────────────────────────────────────────────────────────────

bool parseCorners(const json& doc, std::vector<Corner>& out, std::string& err) {
    const json* arr = nullptr;
    if (!requireArray(doc, "corners", arr, err)) return false;
    for (size_t i = 0; i < arr->size(); ++i) {
        const json& c = (*arr)[i];
        std::ostringstream w; w << "corners[" << i << "]";
        const std::string where = w.str();
        if (!c.is_object()) { err = where + ": must be an object."; return false; }
        if (!rejectUnknownKeys(c, where.c_str(), {"id", "kind", "xy", "geom", "seg", "t"}, err))
            return false;

        Corner corner;
        if (!requireString(c, "id", where.c_str(), corner.id, err)) return false;
        std::string kind;
        if (!requireString(c, "kind", where.c_str(), kind, err)) return false;

        if (kind == "on_geometry") {
            // Attached, not approximated: the position is resolved from the
            // geometry before a single node exists. A corner placed NEAR a feature
            // instead of on it is a slightly wrong mesh with no error, which is the
            // outcome this whole path is built to make impossible.
            //
            // A second declaration of the same position is refused rather than
            // reconciled, on the argument `blocks[].orientation` already gets: two
            // statements of one fact can only ever disagree.
            if (c.contains("xy")) {
                err = where + " ('" + corner.id + "'): an 'on_geometry' corner takes its "
                      "position FROM the geometry, so it must not also declare 'xy'.";
                return false;
            }
            if (!requireString(c, "geom", where.c_str(), corner.geom, err)) return false;
            auto sg = c.find("seg");
            if (sg == c.end() || !sg->is_number_integer() || sg->get<int>() < 0) {
                err = where + " ('" + corner.id + "'): an 'on_geometry' corner needs "
                      "\"seg\": <id>, the source segment it attaches to — one of the ids "
                      "the geometry's '.meta' sidecar lists.";
                return false;
            }
            corner.seg = sg->get<int>();
            auto tt = c.find("t");
            if (tt == c.end() || !tt->is_number()) {
                err = where + " ('" + corner.id + "'): an 'on_geometry' corner needs "
                      "\"t\": <0..1>, its NORMALIZED ARC LENGTH along that segment "
                      "(0 at the segment's own first point, 1 where the next segment "
                      "begins). Arc length rather than a point index, so re-resampling "
                      "the geometry leaves the corner where it was.";
                return false;
            }
            corner.t = tt->get<double>();
            // Written as a positive range so a NaN 't' is refused here too rather
            // than travelling on to produce a NaN node position.
            if (!(corner.t >= 0.0 && corner.t <= 1.0)) {
                err = where + " ('" + corner.id + "'): 't' is " + std::to_string(corner.t)
                    + "; a normalized arc-length position must lie between 0 and 1.";
                return false;
            }
        } else if (kind == "free") {
            for (const char* k : {"geom", "seg", "t"}) {
                if (!c.contains(k)) continue;
                err = where + " ('" + corner.id + "'): a 'free' corner declares '"
                    + std::string(k) + "', which only an 'on_geometry' corner reads. "
                      "Set \"kind\": \"on_geometry\" to attach it, or drop the key.";
                return false;
            }
            auto xy = c.find("xy");
            if (xy == c.end() || !xy->is_array() || xy->size() != 2
                || !(*xy)[0].is_number() || !(*xy)[1].is_number()) {
                err = where + " ('" + corner.id + "'): a 'free' corner needs "
                      "\"xy\": [x, y] with two numbers.";
                return false;
            }
            corner.xy = {(*xy)[0].get<double>(), (*xy)[1].get<double>()};
        } else {
            err = where + " ('" + corner.id + "'): unknown kind '" + kind
                + "'. Accepted: 'free', 'on_geometry'.";
            return false;
        }
        for (const auto& prev : out) {
            if (prev.id == corner.id) {
                err = where + ": duplicate corner id '" + corner.id
                    + "'; every corner id must be unique.";
                return false;
            }
        }
        out.push_back(corner);
    }
    return true;
}

bool parseSpacing(const json& s, const std::string& where, EdgeSpec& e, std::string& err) {
    if (!s.is_object()) { err = where + ": 'spacing' must be an object."; return false; }
    if (!rejectUnknownKeys(s, where.c_str(), {"law", "growth", "delta"}, err)) return false;
    if (!requireString(s, "law", where.c_str(), e.law, err)) return false;
    if (e.law == "uniform") return true;
    if (e.law == "geometric") {
        auto g = s.find("growth");
        if (g == s.end() || !g->is_number() || g->get<double>() <= 0.0) {
            err = where + ": spacing law 'geometric' needs a positive 'growth'.";
            return false;
        }
        e.growth = g->get<double>();
        return true;
    }
    if (e.law == "tanh") {
        auto d = s.find("delta");
        if (d == s.end() || !d->is_number()) {
            err = where + ": spacing law 'tanh' needs a numeric 'delta' "
                  "(the clustering strength; 0 degenerates to uniform).";
            return false;
        }
        e.delta = d->get<double>();
        return true;
    }
    err = where + ": unknown spacing law '" + e.law
        + "'. Accepted: 'uniform', 'geometric', 'tanh'.";
    return false;
}

bool parseEdges(const json& doc, const std::vector<Corner>& corners,
                std::vector<EdgeSpec>& out, std::string& err) {
    const json* arr = nullptr;
    if (!requireArray(doc, "edges", arr, err)) return false;
    auto knownCorner = [&](const std::string& id) {
        for (const auto& c : corners) if (c.id == id) return true;
        return false;
    };
    for (size_t i = 0; i < arr->size(); ++i) {
        const json& e = (*arr)[i];
        std::ostringstream w; w << "edges[" << i << "]";
        const std::string where = w.str();
        if (!e.is_object()) { err = where + ": must be an object."; return false; }
        if (!rejectUnknownKeys(e, where.c_str(),
                               {"id", "corners", "kind", "binding", "count", "spacing"}, err))
            return false;

        EdgeSpec spec;
        if (!requireString(e, "id", where.c_str(), spec.id, err)) return false;
        for (const auto& prev : out) {
            if (prev.id == spec.id) {
                err = where + ": duplicate edge id '" + spec.id
                    + "'; every edge id must be unique.";
                return false;
            }
        }
        auto cs = e.find("corners");
        if (cs == e.end() || !cs->is_array() || cs->size() != 2
            || !(*cs)[0].is_string() || !(*cs)[1].is_string()) {
            err = where + " ('" + spec.id + "'): 'corners' must be two corner ids.";
            return false;
        }
        spec.a = (*cs)[0].get<std::string>();
        spec.b = (*cs)[1].get<std::string>();
        for (const std::string& id : {spec.a, spec.b}) {
            if (!knownCorner(id)) {
                err = where + " ('" + spec.id + "'): corner '" + id
                    + "' is not declared in 'corners'.";
                return false;
            }
        }
        if (spec.a == spec.b) {
            err = where + " ('" + spec.id + "'): both ends are corner '" + spec.a
                + "'; an edge needs two distinct corners.";
            return false;
        }

        // The kind is an explicit enum and is NEVER inferred from whether a
        // binding is present: a wake cut is two blocks sharing one line that is
        // not a boundary, and inferring would classify it as an ordinary
        // interface.
        if (!requireString(e, "kind", where.c_str(), spec.kind, err)) return false;
        if (spec.kind != "wall" && spec.kind != "interface" && spec.kind != "cut") {
            err = where + " ('" + spec.id + "'): unknown kind '" + spec.kind
                + "'. Accepted: 'wall', 'interface', 'cut'.";
            return false;
        }
        if (spec.kind != "wall") {
            err = where + " ('" + spec.id + "'): kind '" + spec.kind + "' needs a second "
                  "block to be shared with, and this release fills exactly one block. "
                  "Interfaces and cuts arrive with the multi-block welding work.";
            return false;
        }
        // The source segment this edge LIES ON. This is where a boundary condition
        // comes from on this path: the segment's own label, carried into the export
        // with its (geometry, segment) key. Nothing downstream tests whether a node
        // is near a reference segment, so there is no tolerance in the chain to
        // drift past — which is how a curved inlet came to export a band of wall on
        // the other path.
        auto bd = e.find("binding");
        if (bd != e.end()) {
            const std::string bw = where + " ('" + spec.id + "') binding";
            if (!bd->is_object()) {
                err = bw + ": must be an object, \"binding\": "
                           "{\"geom\": \"<file>\", \"seg\": <id>}.";
                return false;
            }
            if (!rejectUnknownKeys(*bd, bw.c_str(), {"geom", "seg"}, err)) return false;
            if (!requireString(*bd, "geom", bw.c_str(), spec.bindGeom, err)) return false;
            auto sg = bd->find("seg");
            if (sg == bd->end() || !sg->is_number_integer() || sg->get<int>() < 0) {
                err = bw + ": needs \"seg\": <id>, the source segment this edge lies on.";
                return false;
            }
            spec.bindSeg = sg->get<int>();
        }

        // No count propagation in this release (that is its own increment), so
        // every edge must say how many nodes it carries. Refusing beats picking a
        // default: a silently-chosen count decides the whole mesh density.
        auto cnt = e.find("count");
        if (cnt == e.end() || !cnt->is_number_integer()) {
            err = where + " ('" + spec.id + "'): 'count' (an integer node count >= 2) "
                  "is required. Seeding a few edges and propagating the rest across "
                  "the edges that are structurally forced to match arrives with the "
                  "point-count propagation work.";
            return false;
        }
        spec.count = cnt->get<int>();
        if (spec.count < 2) {
            err = where + " ('" + spec.id + "'): 'count' is " + std::to_string(spec.count)
                + "; an edge needs at least 2 nodes (its two end corners).";
            return false;
        }
        auto sp = e.find("spacing");
        if (sp != e.end() && !parseSpacing(*sp, where + " ('" + spec.id + "')", spec, err))
            return false;

        out.push_back(spec);
    }
    return true;
}

bool parseBlocks(const json& doc, const std::vector<EdgeSpec>& edges,
                 std::vector<BlockSpec>& out, std::string& err) {
    const json* arr = nullptr;
    if (!requireArray(doc, "blocks", arr, err)) return false;
    auto knownEdge = [&](const std::string& id) {
        for (const auto& e : edges) if (e.id == id) return true;
        return false;
    };
    for (size_t i = 0; i < arr->size(); ++i) {
        const json& b = (*arr)[i];
        std::ostringstream w; w << "blocks[" << i << "]";
        const std::string where = w.str();
        if (!b.is_object()) { err = where + ": must be an object."; return false; }
        if (!rejectUnknownKeys(b, where.c_str(), {"id", "edges", "orientation"}, err))
            return false;

        BlockSpec spec;
        if (!requireString(b, "id", where.c_str(), spec.id, err)) return false;
        if (b.contains("orientation")) {
            err = where + " ('" + spec.id + "'): 'orientation' is not read in this "
                  "release. A block's orientation follows from the corner order of "
                  "its own four edges (see the [south, east, north, west] convention "
                  "reported by any mismatch), so a second declaration of it could "
                  "only ever disagree.";
            return false;
        }
        auto es = b.find("edges");
        if (es == b.end() || !es->is_array() || es->size() != 4) {
            err = where + " ('" + spec.id + "'): 'edges' must be exactly four edge ids, "
                  "in the order [south, east, north, west].";
            return false;
        }
        for (size_t k = 0; k < 4; ++k) {
            if (!(*es)[k].is_string()) {
                err = where + " ('" + spec.id + "'): edges[" + std::to_string(k)
                    + "] must be an edge id.";
                return false;
            }
            std::string id = (*es)[k].get<std::string>();
            if (!knownEdge(id)) {
                err = where + " ('" + spec.id + "'): edge '" + id
                    + "' is not declared in 'edges'.";
                return false;
            }
            if (std::find(spec.edges.begin(), spec.edges.end(), id) != spec.edges.end()) {
                err = where + " ('" + spec.id + "'): edge '" + id + "' is named twice; a "
                      "block's four sides must be four distinct edges.";
                return false;
            }
            spec.edges.push_back(id);
        }
        out.push_back(spec);
    }
    return true;
}

// ── Discretisation ────────────────────────────────────────────────────────

// ── Arc length ────────────────────────────────────────────────────────────
//
// Every position on this path is an ARC LENGTH along a polyline, never a point
// index. That is the ticket's central rule and it is not a preference: the
// workflow is edit CAD, re-resample, re-mesh, and re-resampling changes the
// point count — so an index would silently relocate every attachment on each
// resample and produce a slightly wrong mesh with no error at all.

std::vector<double> arcLengths(const std::vector<Point2D>& path) {
    std::vector<double> cum(path.size(), 0.0);
    for (size_t k = 1; k < path.size(); ++k)
        cum[k] = cum[k - 1] + (path[k] - path[k - 1]).length();
    return cum;
}

// Where normalized arc-length position `t` lands on `path`.
//
// The two ENDS are returned as the path's own points rather than interpolated
// onto them, so a corner declared at t = 0 or t = 1 IS a geometry point and not
// a value 1e-16 away from one. Same reasoning as the end pinning in
// `discretise`: welding here is topological precisely so that no tolerance ever
// has to rescue a near miss.
Point2D pointAtArc(const std::vector<Point2D>& path,
                   const std::vector<double>& cum, double t) {
    if (path.empty()) return Point2D{0.0, 0.0};
    if (path.size() < 2 || t <= 0.0) return path.front();
    if (t >= 1.0) return path.back();
    const double L = cum.back();
    if (!(L > 0.0)) return path.front();
    const double s = t * L;
    size_t m = 0;
    while (m + 2 < path.size() && cum[m + 1] < s) ++m;
    const double span = cum[m + 1] - cum[m];
    const double f = (span > 0.0) ? (s - cum[m]) / span : 0.0;
    return path[m] + (path[m + 1] - path[m]) * f;
}

// The stretch of `path` between normalized positions t0 and t1, with both ends
// landing exactly where `pointAtArc` puts them — so a bound edge begins and ends
// on its own corners by construction rather than to within a tolerance.
//
// Walks BACKWARDS when t1 < t0, so an edge declared against its segment's own
// direction follows the geometry rather than being refused over bookkeeping.
std::vector<Point2D> subPath(const std::vector<Point2D>& path,
                             const std::vector<double>& cum, double t0, double t1) {
    const double L = cum.back();
    const double s0 = t0 * L, s1 = t1 * L;
    std::vector<Point2D> out;
    out.push_back(pointAtArc(path, cum, t0));
    if (s1 >= s0) {
        for (size_t k = 0; k < path.size(); ++k)
            if (cum[k] > s0 && cum[k] < s1) out.push_back(path[k]);
    } else {
        for (size_t k = path.size(); k-- > 0;)
            if (cum[k] < s0 && cum[k] > s1) out.push_back(path[k]);
    }
    out.push_back(pointAtArc(path, cum, t1));
    return out;
}

// The points along one edge, including both end corners.
//
// `path` is the polyline the edge RUNS ALONG. For an unbound edge that is just
// its two corners, so this is a straight chord and every expression below
// reduces to exactly the arithmetic this function had before geometry binding —
// measured rather than assumed, by the golden set's pre-binding cases.
//
// For a BOUND edge the path is the source segment's own points between its two
// corners, which is what makes "this edge lies on that segment" true instead of
// merely declared: a straight chord across a curved wall sits a sagitta off the
// body everywhere in between, and that drift is precisely what made a curved
// inlet export a band of wall on the other path.
//
// Goes through the existing spacing laws rather than re-deriving them: they are
// pure arithmetic already used by the preprocessor, and a second implementation
// of a growth-rate solver is a guaranteed future divergence. `generateGeometric`
// at ratio 1 IS the uniform law, so "uniform" is not a special case here either.
std::vector<Point2D> discretise(const EdgeSpec& e, const std::vector<Point2D>& path) {
    std::vector<Point2D> pts;
    if (path.size() < 2) return pts;
    const std::vector<double> cum = arcLengths(path);
    const double L = cum.back();
    std::vector<double> t;
    if (e.law == "tanh")            t = HybMesh::Spacing::generateTanh(L, e.count, e.delta);
    else if (e.law == "geometric")  t = HybMesh::Spacing::generateGeometric(L, e.count, e.growth);
    else                            t = HybMesh::Spacing::generateGeometric(L, e.count, 1.0);

    pts.reserve(static_cast<size_t>(e.count));
    size_t m = 0;
    for (int k = 0; k < e.count; ++k) {
        // Parametrise by arc length, and pin both ends onto the corners exactly.
        // A t/L that lands 1e-16 short of 1 would leave the last node off the
        // corner it is supposed to BE.
        if (k == 0)               { pts.push_back(path.front()); continue; }
        if (k == e.count - 1)     { pts.push_back(path.back());  continue; }
        const double s = (L > 0.0) ? t[static_cast<size_t>(k)] : 0.0;
        while (m + 2 < path.size() && cum[m + 1] < s) ++m;
        const double span = cum[m + 1] - cum[m];
        const double f = (span > 0.0) ? (s - cum[m]) / span : 0.0;
        pts.push_back(path[m] + (path[m + 1] - path[m]) * f);
    }
    return pts;
}

// ── Geometry lookup ───────────────────────────────────────────────────────

std::string basenameOf(const std::string& path) {
    const size_t at = path.find_last_of("/\\");
    return at == std::string::npos ? path : path.substr(at + 1);
}

// Which loaded geometry a topology names. BY NAME — exact match on the path the
// config declared, then a UNIQUE basename match so a topology may say
// "naca0012.dat" for a run that loaded "examples/geometries/naca0012.dat".
//
// Never by position in the list: a binding that moves when GEOM_FILE lines are
// reordered is the same silent relocation an index-based point attachment would
// be, one level up. Two geometries sharing a basename make the short form
// AMBIGUOUS, and that is refused rather than resolved by order.
int findGeometry(const std::vector<hybmesh::MbGeometry>& geoms,
                 const std::string& name, const std::string& who, std::string& err) {
    if (geoms.empty()) {
        err = who + ": names geometry '" + name + "', but this run loaded no geometry "
              "at all (no GEOM_FILE in the config).";
        return -1;
    }
    for (size_t k = 0; k < geoms.size(); ++k)
        if (geoms[k].file == name) return static_cast<int>(k);

    std::vector<int> byBase;
    const std::string want = basenameOf(name);
    for (size_t k = 0; k < geoms.size(); ++k)
        if (basenameOf(geoms[k].file) == want) byBase.push_back(static_cast<int>(k));
    if (byBase.size() == 1) return byBase.front();

    std::ostringstream os;
    os << who << ": ";
    if (byBase.size() > 1) {
        os << "geometry '" << name << "' is ambiguous — ";
        for (size_t k = 0; k < byBase.size(); ++k)
            os << (k ? " and " : "") << "'" << geoms[static_cast<size_t>(byBase[k])].file << "'";
        os << " share that name. Name one of them in full.";
    } else {
        os << "no geometry named '" << name << "' was loaded. This run loaded";
        for (const auto& g : geoms) os << " '" << g.file << "'";
        os << ".";
    }
    err = os.str();
    return -1;
}

// The polyline of one source segment of one geometry, and the refusals that make
// an arc length along it mean something.
//
// A segment's own points stop ONE POINT SHORT of where it ends: the preprocessor
// assigns a joint shared by two segments to the LATER of them (`resSegId` in
// tools/PreProcessor/src/main.cpp). The run is therefore extended by the next
// point in the file, which makes t = 1 of a segment and t = 0 of its successor
// the same physical point — and, more to the point, makes t = 1 mean where the
// segment really ends instead of one resampling interval short of it, which is a
// place that MOVES under exactly the re-resampling this attachment exists to
// survive. Across a piece break there is no next point to reach for, and taking
// one anyway would stretch the segment over the gap between two disjoint pieces.
// One source segment, resolved: its polyline, its cumulative arc length, and the
// INDICES in the geometry where it begins and ends.
//
// The indices are what make a joint expressible. A segment end is a point SHARED
// with the neighbouring segment, so two attachments can name it from either side;
// everything strictly between is interior to its own segment and equal only to
// itself. Comparing those indices is a fact about the sidecar's own numbering —
// no two coordinates are ever compared, so this is not a tolerance creeping back
// in through the corner.
struct SegSpan {
    std::vector<Point2D> pts;
    std::vector<double> cum;
    size_t first = 0;      // index of the t = 0 point
    size_t endIdx = 0;     // index of the t = 1 point (0 on a closed loop's last segment)
};

// Does this geometry really hold more than one disconnected piece?
//
// Asked rather than testing `pieceBreaks.empty()`, because a break at index 0
// carries no information — every polyline starts a piece at its first point, and
// sidecars in this repo disagree about whether to record that one (a resampled
// square writes NPIECES 0, while examples/geometries/square_cavity.dat.meta
// writes NPIECES 1 with a break at 0). Reading the trivial entry as "multi-piece"
// would silently switch off the closed-loop wrap below and put the last segment's
// t = 1 one resampling interval short of the seam.
bool multiPiece(const hybmesh::MbGeometry& g) {
    for (size_t b : g.pieceBreaks)
        if (b > 0 && b < g.points.size()) return true;
    return false;
}

bool segmentRun(const hybmesh::MbGeometry& g, int seg, const std::string& who,
                SegSpan& span, std::string& err) {
    std::vector<Point2D>& out = span.pts;
    if (g.points.empty()) {
        err = who + ": geometry '" + g.file + "' carries no points, so there is nothing "
              "to attach to. An unloadable geometry is only a warning on this path while "
              "nothing refers to it — this declaration refers to it.";
        return false;
    }
    if (g.segId.size() != g.points.size()) {
        err = who + ": geometry '" + g.file + "' carries no per-point source-segment "
              "data, so it has no segments to attach to. That comes from the '.meta' "
              "sidecar the PreProcessor writes beside the .dat; re-export the geometry "
              "to get one.";
        return false;
    }
    const size_t n = g.points.size();
    size_t first = n, last = 0;
    std::set<int> present;
    for (size_t k = 0; k < n; ++k) {
        present.insert(g.segId[k]);
        if (g.segId[k] != seg) continue;
        if (first == n) first = k;
        last = k;
    }
    if (first == n) {
        std::ostringstream os;
        os << who << ": geometry '" << g.file << "' has no segment " << seg
           << ". It carries segment(s)";
        for (int id : present) os << " " << id;
        os << ".";
        err = os.str();
        return false;
    }
    for (size_t k = first; k <= last; ++k) {
        if (g.segId[k] == seg) continue;
        err = who + ": segment " + std::to_string(seg) + " of geometry '" + g.file
            + "' is not one contiguous run of points, so an arc length along it is not "
              "a length of anything.";
        return false;
    }
    size_t stop = last;
    bool wrapToStart = false;
    const bool breakAfter = std::find(g.pieceBreaks.begin(), g.pieceBreaks.end(),
                                      last + 1) != g.pieceBreaks.end();
    if (last + 1 < n && !breakAfter) {
        stop = last + 1;
    } else if (last + 1 == n && g.closed && !multiPiece(g)) {
        // The last segment of a CLOSED loop ends where the first one begins, and
        // the loader has already dropped the duplicate closing point — so the point
        // to reach for is index 0, not one past the end.
        wrapToStart = true;
    }
    out.assign(g.points.begin() + static_cast<std::ptrdiff_t>(first),
               g.points.begin() + static_cast<std::ptrdiff_t>(stop) + 1);
    if (wrapToStart) out.push_back(g.points.front());
    span.first = first;
    span.endIdx = wrapToStart ? 0 : stop;
    double L = 0.0;
    for (size_t k = 1; k < out.size(); ++k) L += (out[k] - out[k - 1]).length();
    span.cum = arcLengths(out);
    if (out.size() < 2 || !(L > 0.0)) {
        out.clear();
        err = who + ": segment " + std::to_string(seg) + " of geometry '" + g.file
            + "' has no arc length (it is a single point, or every point on it "
              "coincides), so there is no position along it to attach to.";
        return false;
    }
    return true;
}

// Transfinite (Coons) interpolation of a block interior from its four
// discretised sides. Exact for a rectangle — the tensor product falls out and
// the blend terms cancel — which is why v0 rests on it with no smoother.
// `south`/`north` run i-min -> i-max; `west`/`east` run j-min -> j-max.
Point2D coons(const std::vector<Point2D>& south, const std::vector<Point2D>& north,
              const std::vector<Point2D>& west, const std::vector<Point2D>& east,
              int i, int j, int ni, int nj) {
    const double u = static_cast<double>(i) / (ni - 1);
    const double v = static_cast<double>(j) / (nj - 1);
    const Point2D A = south.front(), B = south.back();
    const Point2D D = north.front(), C = north.back();
    Point2D p = south[static_cast<size_t>(i)] * (1.0 - v)
              + north[static_cast<size_t>(i)] * v
              + west[static_cast<size_t>(j)] * (1.0 - u)
              + east[static_cast<size_t>(j)] * u;
    Point2D corr = A * ((1.0 - u) * (1.0 - v)) + B * (u * (1.0 - v))
                 + C * (u * v)                 + D * ((1.0 - u) * v);
    return p - corr;
}

}  // namespace

hybmesh::MbResult hybmesh::buildMultiBlock(const std::string& topologyJson,
                                           const std::vector<MbGeometry>& geoms,
                                           const MbParams& params) {
    MbResult r;
    auto fail = [&r](const std::string& msg) -> MbResult& {
        r.ok = false;
        r.error = msg;
        r.nodes.clear(); r.blocks.clear(); r.cells.clear(); r.boundaryEdges.clear();
        return r;
    };

    // Never throws: a malformed document is an ordinary outcome of this seam,
    // not an exception the caller has to remember to catch.
    json doc = json::parse(topologyJson, nullptr, /*allow_exceptions*/ false,
                           /*ignore_comments*/ true);
    if (doc.is_discarded())
        return fail("the topology document is not valid JSON (check for a trailing "
                    "comma, an unquoted key or a missing brace).");
    if (!doc.is_object())
        return fail("the topology document must be a JSON object.");

    std::string err;
    if (!rejectUnknownKeys(doc, "topology", {"format_version", "corners", "edges", "blocks"}, err))
        return fail(err);

    auto fv = doc.find("format_version");
    if (fv == doc.end() || !fv->is_number_integer())
        return fail("'format_version' is required and must be an integer (this build "
                    "reads version " + std::to_string(kFormatVersion) + ").");
    if (fv->get<int>() != kFormatVersion)
        return fail("topology format_version " + std::to_string(fv->get<int>())
                    + " is not readable by this build, which reads version "
                    + std::to_string(kFormatVersion) + ".");

    std::vector<Corner> corners;
    std::vector<EdgeSpec> edges;
    std::vector<BlockSpec> blocks;
    if (!parseCorners(doc, corners, err)) return fail(err);
    if (!parseEdges(doc, corners, edges, err)) return fail(err);
    if (!parseBlocks(doc, edges, blocks, err)) return fail(err);

    if (blocks.size() != 1)
        return fail("this release fills exactly one block and the topology declares "
                    + std::to_string(blocks.size()) + ". Several blocks need the point "
                    "counts propagated across shared edges and the two sides welded "
                    "topologically, which arrives with the multi-block welding work.");

    // A declaration that reaches nothing is a typo, not a preference: an edge in
    // no block and a corner on no edge are both silently absent from the mesh.
    for (const auto& e : edges) {
        bool used = false;
        for (const auto& b : blocks)
            if (std::find(b.edges.begin(), b.edges.end(), e.id) != b.edges.end()) used = true;
        if (!used)
            return fail("edge '" + e.id + "' belongs to no block. Every declared edge "
                        "must be one of some block's four sides.");
    }
    for (const auto& c : corners) {
        bool used = false;
        for (const auto& e : edges) if (e.a == c.id || e.b == c.id) used = true;
        if (!used)
            return fail("corner '" + c.id + "' is on no edge. Every declared corner "
                        "must be an end of some edge.");
    }

    // ── The fallback boundary condition ───────────────────────────────────
    // Resolved before attachment, because a bound edge whose segment carries no
    // label falls back to it and has to be able to say so.
    std::string bc = params.defaultBc;
    if (bc.empty()) {
        bc = "wall";
        r.warnings.push_back("no default boundary condition was resolved (BC_GEOM is "
                             "empty); every boundary edge with no source segment of "
                             "its own is exported as 'wall'.");
    }

    // ── Geometry attachment, resolved before a single node exists ─────────
    //
    // This is what "declared, not discovered" means concretely. A corner's
    // position and a boundary edge's condition are both read out of the
    // declaration HERE, and nothing downstream re-derives either from a
    // coordinate: there is no tolerance anywhere in this chain, so there is
    // nothing for a curved wall to drift past.

    // A bound edge carries its source segment AND the stretch of it the edge
    // covers, in that segment's OWN parametrisation — which is not always the
    // parametrisation its corners were declared in, see `tOnSegment` below.
    struct Attached {
        int geomId = -1;
        int segId = -1;
        std::string bc;
        double ta = 0.0, tb = 1.0;
    };
    std::map<std::string, Attached> bound;              // edge id -> its source segment
    std::map<std::pair<int, int>, SegSpan> spans;       // (geom, seg) -> resolved segment

    auto spanFor = [&](int gi, int seg, const std::string& who,
                       const SegSpan*& out) -> bool {
        const auto key = std::make_pair(gi, seg);
        auto it = spans.find(key);
        if (it == spans.end()) {
            SegSpan sp;
            if (!segmentRun(geoms[static_cast<size_t>(gi)], seg, who, sp, err))
                return false;
            it = spans.emplace(key, std::move(sp)).first;
        }
        out = &it->second;
        return true;
    };

    // Corners first: an edge's binding is checked against its two corners'
    // attachments, so those have to be resolved before it can be.
    for (auto& c : corners) {
        if (c.geom.empty()) continue;
        const std::string who = "corner '" + c.id + "'";
        const int gi = findGeometry(geoms, c.geom, who, err);
        if (gi < 0) return fail(err);
        const SegSpan* sp = nullptr;
        if (!spanFor(gi, c.seg, who, sp)) return fail(err);
        c.geomIdx = gi;
        c.xy = pointAtArc(sp->pts, sp->cum, c.t);
    }

    auto cornerById = [&](const std::string& id) -> const Corner* {
        for (const auto& c : corners) if (c.id == id) return &c;
        return nullptr;
    };

    // A corner's position IN A GIVEN SEGMENT'S parametrisation.
    //
    // A corner attached to that segment answers directly. A corner attached to a
    // NEIGHBOUR answers when it sits on the joint the two share — t = 0 and t = 1
    // are segment ends, and a segment end is one point that both segments own.
    // That case is not a nicety: on a closed body every block corner IS a joint,
    // and its two edges bind to different segments, so without it the canonical
    // declaration — one block side per source segment — could not be written at
    // all. Anything strictly inside a segment answers only for that segment.
    auto tOnSegment = [&](const Corner& c, int gi, int seg, double& t) -> bool {
        if (c.geomIdx != gi) return false;
        if (c.seg == seg) { t = c.t; return true; }
        const auto own = spans.find({gi, c.seg});
        const auto want = spans.find({gi, seg});
        if (own == spans.end() || want == spans.end()) return false;
        size_t at;
        if (c.t == 0.0)      at = own->second.first;
        else if (c.t == 1.0) at = own->second.endIdx;
        else                 return false;
        if (at == want->second.first)  { t = 0.0; return true; }
        if (at == want->second.endIdx) { t = 1.0; return true; }
        return false;
    };

    for (const auto& e : edges) {
        if (e.bindGeom.empty()) continue;
        const std::string who = "edge '" + e.id + "'";
        const int gi = findGeometry(geoms, e.bindGeom, who, err);
        if (gi < 0) return fail(err);
        const SegSpan* sp = nullptr;
        if (!spanFor(gi, e.bindSeg, who, sp)) return fail(err);

        // A bound edge LIES ON its segment, so both of its corners must be ON it.
        // Without that there is no stretch of geometry for the edge to follow, and
        // a straight chord drawn between two free corners and then CALLED a piece
        // of that wall is exactly the slightly-wrong-mesh-with-no-error this path
        // exists to refuse.
        Attached at;
        const Corner* ends[2] = {cornerById(e.a), cornerById(e.b)};
        double ts[2] = {0.0, 0.0};
        for (int k = 0; k < 2; ++k) {
            const Corner* c = ends[k];
            if (!c)
                return fail(who + ": corner '" + (k ? e.b : e.a) + "' resolved during "
                            "parsing and not during binding; the topology was not read "
                            "consistently and no mesh was made.");
            if (tOnSegment(*c, gi, e.bindSeg, ts[k])) continue;
            return fail(who + " binds to segment " + std::to_string(e.bindSeg) + " of '"
                        + geoms[static_cast<size_t>(gi)].file + "', so both of its "
                          "corners must lie on that segment — but corner '"
                        + c->id + "' is "
                        + (c->geom.empty()
                               ? std::string("a free coordinate")
                               : "attached to segment " + std::to_string(c->seg)
                                     + " of '" + c->geom + "' at t = "
                                     + std::to_string(c->t))
                        + ". An edge that lies on a segment has to start and end on it "
                          "— at a position on it, or on a joint it shares with the "
                          "segment next to it.");
        }
        if (ts[0] == ts[1])
            return fail(who + ": both of its corners lie at t = " + std::to_string(ts[0])
                        + " on segment " + std::to_string(e.bindSeg)
                        + ", so the edge has no length.");
        at.ta = ts[0];
        at.tb = ts[1];
        at.geomId = gi;
        at.segId = e.bindSeg;
        const auto& labels = geoms[static_cast<size_t>(gi)].segBc;
        const auto lb = labels.find(e.bindSeg);
        at.bc = (lb != labels.end()) ? lb->second : std::string();
        if (at.bc.empty()) {
            // Bound, and still on the fallback. Worth saying out loud: the user
            // named a segment precisely so the condition would follow from the
            // declaration, and here it did not.
            at.bc = bc;
            r.warnings.push_back("edge '" + e.id + "' binds to segment "
                + std::to_string(e.bindSeg) + " of '"
                + geoms[static_cast<size_t>(gi)].file + "', which carries no boundary "
                  "condition label in its '.meta' sidecar, so the edge takes the config "
                  "default '" + bc + "'. Assign that segment a condition in the "
                  "PreProcessor to have it follow from the declaration.");
        }
        bound[e.id] = at;
    }

    if (bound.empty())
        r.warnings.push_back("no topology edge declares a 'binding', so every boundary "
                             "edge carries the config default BC '" + bc + "'. Bind a "
                             "wall edge to a source segment to have its condition come "
                             "from the declaration instead.");

    // Both lookups return a POINTER and the caller refuses on null, rather than
    // falling back to the origin or to the first edge. The parse already proved
    // every id resolves, so these branches should be dead — but a silent fallback
    // on a broken invariant meshes a block nobody declared, and a wrong mesh is
    // the one outcome worse than no mesh.
    auto cornerXy = [&](const std::string& id) -> const Point2D* {
        for (const auto& c : corners) if (c.id == id) return &c.xy;
        return nullptr;
    };
    auto edgeById = [&](const std::string& id) -> const EdgeSpec* {
        for (const auto& e : edges) if (e.id == id) return &e;
        return nullptr;
    };

    const BlockSpec& blk = blocks.front();
    const EdgeSpec* sides[4] = {edgeById(blk.edges[0]), edgeById(blk.edges[1]),
                                edgeById(blk.edges[2]), edgeById(blk.edges[3])};
    for (int k = 0; k < 4; ++k)
        if (!sides[k])
            return fail("block '" + blk.id + "': edge '" + blk.edges[static_cast<size_t>(k)]
                        + "' resolved during parsing and not during filling; the "
                          "topology was not read consistently and no mesh was made.");
    const EdgeSpec& S = *sides[0];
    const EdgeSpec& E = *sides[1];
    const EdgeSpec& N = *sides[2];
    const EdgeSpec& W = *sides[3];

    // The block's four corners, named for their logical position:
    //   A = (0, 0)   B = (ni-1, 0)   C = (ni-1, nj-1)   D = (0, nj-1)
    // and the convention every side is checked against is
    //   south [A,B]   east [B,C]   north [D,C]   west [A,D]
    // i.e. south and north both run i-min -> i-max, west and east both run
    // j-min -> j-max. Declaring it and refusing deviations by name beats
    // inferring the orientation: an inferred one that guesses wrong produces a
    // mirrored or inside-out block, which is a mesh rather than an error.
    const std::string A = S.a, B = S.b;
    auto sideMismatch = [&](const EdgeSpec& e, const char* side,
                            const std::string& want0, const std::string& want1) {
        return "block '" + blk.id + "': its " + std::string(side) + " edge '" + e.id
             + "' runs ['" + e.a + "', '" + e.b + "'] but the [south, east, north, west] "
               "convention needs ['" + want0 + "', '" + want1 + "'] — south and north both "
               "run i-min to i-max, west and east both run j-min to j-max, and all four "
               "meet at the block's corners.";
    };
    if (W.a != A) return fail(sideMismatch(W, "west", A, "<the block's j-max corner>"));
    const std::string D = W.b;
    if (E.a != B) return fail(sideMismatch(E, "east", B, "<the block's j-max corner>"));
    const std::string C = E.b;
    if (N.a != D || N.b != C) return fail(sideMismatch(N, "north", D, C));

    // Opposite sides of a block are structurally forced to carry equal counts.
    // Until propagation lands, a mismatch is a hard refusal naming both edges and
    // both requested counts — the same report a conflicting seed will get once
    // counts propagate, so one mistake reads the same either way.
    auto countClash = [&](const EdgeSpec& x, const char* sx,
                          const EdgeSpec& y, const char* sy) {
        return "block '" + blk.id + "': opposite sides must carry equal node counts, "
               "but its " + std::string(sx) + " edge '" + x.id + "' declares count "
             + std::to_string(x.count) + " and its " + std::string(sy) + " edge '"
             + y.id + "' declares count " + std::to_string(y.count) + ".";
    };
    if (S.count != N.count) return fail(countClash(S, "south", N, "north"));
    if (W.count != E.count) return fail(countClash(W, "west", E, "east"));

    const int ni = S.count;
    const int nj = W.count;

    const Point2D* pc[4] = {cornerXy(A), cornerXy(B), cornerXy(C), cornerXy(D)};
    const std::string names[4] = {A, B, C, D};
    for (int k = 0; k < 4; ++k)
        if (!pc[k])
            return fail("block '" + blk.id + "': corner '" + names[k] + "' resolved "
                        "during parsing and not during filling; the topology was not "
                        "read consistently and no mesh was made.");
    const Point2D pa = *pc[0], pb = *pc[1], pcc = *pc[2], pd = *pc[3];

    // The polyline each side runs along. Every one of the four is discretised in
    // its OWN declared direction (a -> b) — which the convention check above has
    // just proved is also the block's i/j direction for that side — so one rule
    // covers all four and a bound edge needs no second orientation argument.
    auto pathFor = [&](const EdgeSpec& e, Point2D p0, Point2D p1) -> std::vector<Point2D> {
        const auto it = bound.find(e.id);
        if (it == bound.end()) return {p0, p1};
        const SegSpan& sp = spans.at({it->second.geomId, it->second.segId});
        return subPath(sp.pts, sp.cum, it->second.ta, it->second.tb);
    };
    const std::vector<Point2D> south = discretise(S, pathFor(S, pa, pb));
    const std::vector<Point2D> north = discretise(N, pathFor(N, pd, pcc));
    const std::vector<Point2D> west  = discretise(W, pathFor(W, pa, pd));
    const std::vector<Point2D> east  = discretise(E, pathFor(E, pb, pcc));

    // A clockwise corner ring makes EVERY cell in the block inverted, so this is
    // a bad block orientation: a defect of the DECLARATION, readable before a
    // single node exists, with an actionable fix. Refused with the topology code
    // rather than exported under the inverted-cell one, and the difference is not
    // a technicality — the inverted-cell code is for a valid declaration whose
    // GEOMETRY came out folded, which is worth looking at; a backwards-wound ring
    // is worth fixing, and there is nothing to look at because no one wants the
    // mesh either way. Not repaired silently either: re-winding would mean the
    // mesh no longer matches the document that declared it.
    {
        const double area2 = (pb - pa).cross(pcc - pa) + (pcc - pa).cross(pd - pa);
        if (area2 <= 0.0)
            return fail("block '" + blk.id + "': its corners '" + A + "', '" + B
                + "', '" + C + "', '" + D + "' wind clockwise (signed area "
                + std::to_string(0.5 * area2) + "), so every cell in it would be "
                "inverted. Swap the block's south and north edges, or reverse each "
                "edge's own corner pair.");
    }

    MbBlock filled;
    filled.id = blk.id;
    filled.ni = ni;
    filled.nj = nj;
    filled.nodeIds.resize(static_cast<size_t>(ni) * static_cast<size_t>(nj));
    r.nodes.reserve(static_cast<size_t>(ni) * static_cast<size_t>(nj));
    for (int j = 0; j < nj; ++j) {
        for (int i = 0; i < ni; ++i) {
            filled.nodeIds[static_cast<size_t>(j) * ni + i] = static_cast<int>(r.nodes.size());
            r.nodes.push_back(coons(south, north, west, east, i, j, ni, nj));
        }
    }
    r.blocks.push_back(filled);
    const MbBlock& b0 = r.blocks.front();
    const int blockIdx = 0;

    // Publish what the DECLARATION asks the first cell height off each wall to
    // be, for the quality report to measure the fill against (include/MbQuality.hpp).
    //
    // It has to be published from here because only this scope still knows the
    // spacing laws: the request off a side is the FIRST INTERVAL of the edge
    // running away from it, taken from the perpendicular edge at each of the
    // side's two corners, and once the block is a grid of positions those laws
    // are gone. Which edge that is comes from `mbSideAxis`, so the [south, east,
    // north, west] convention is read here rather than restated.
    //
    // WHAT THIS IS NOT, stated here because it is easy to over-read: in this
    // release nothing declares a wall-normal first-cell height independently of
    // the edge distribution, so the request is DERIVED FROM THE SAME LAW the fill
    // reproduces. The transfinite blend is exact on the boundary, so the number
    // the report computes from it is zero at the side's two end columns BY
    // CONSTRUCTION, and what it really measures in between is interior
    // distortion. An independent target arrives with the wall-spacing resolution
    // work (BL_INITIAL_THICKNESS and friends); when it does, only these two lines
    // change source and nothing that reads the report has to change.
    {
        auto firstInterval = [](const std::vector<Point2D>& e, bool fromEnd) {
            if (e.size() < 2) return 0.0;
            return fromEnd ? (e[e.size() - 1] - e[e.size() - 2]).length()
                           : (e[1] - e[0]).length();
        };
        for (int k = 0; k < 4; ++k) {
            const MbSide side = static_cast<MbSide>(k);   // sides[] is in this order
            const MbSideAxis ax = mbSideAxis(side);
            const EdgeSpec& e = *sides[k];
            // Gated on the KIND rather than on "v0 has only walls": interface and
            // cut edges are refused by name today, so this is dead by construction
            // now and correct the day they are not.
            if (e.kind != "wall") continue;
            const std::vector<Point2D>& perpLo = ax.alongI ? west : south;
            const std::vector<Point2D>& perpHi = ax.alongI ? east : north;
            MbWallSpec ws;
            ws.block = blockIdx;
            ws.side = side;
            ws.edgeId = e.id;
            ws.requestedLo = firstInterval(perpLo, ax.atFarEnd);
            ws.requestedHi = firstInterval(perpHi, ax.atFarEnd);
            r.wallSpecs.push_back(ws);
        }
    }

    for (int j = 0; j + 1 < nj; ++j) {
        for (int i = 0; i + 1 < ni; ++i) {
            const int n00 = b0.nodeAt(i, j),     n10 = b0.nodeAt(i + 1, j);
            const int n11 = b0.nodeAt(i + 1, j + 1), n01 = b0.nodeAt(i, j + 1);
            if (!params.splitQuads) {
                r.cells.push_back(MbCell{{n00, n10, n11, n01}, blockIdx});
                continue;
            }
            // ALTERNATING BY INDEX PARITY — the default, and correct from the
            // first mesh rather than a later refinement. A single consistent
            // diagonal imprints its own direction on a uniform structured
            // region; flipping with (i + j) does not, needs no seed, and stays
            // deterministic, so this path remains comparable run to run.
            if (((i + j) % 2) == 0) {
                r.cells.push_back(MbCell{{n00, n10, n11}, blockIdx});
                r.cells.push_back(MbCell{{n00, n11, n01}, blockIdx});
            } else {
                r.cells.push_back(MbCell{{n00, n10, n01}, blockIdx});
                r.cells.push_back(MbCell{{n10, n11, n01}, blockIdx});
            }
        }
    }
    if (!params.splitQuads)
        r.warnings.push_back("quad splitting is OFF, so this mesh is exported as quads. "
                             "That is a diagnostic setting: the solver's incenter "
                             "reconstruction is undefined on quad cells, and the grid "
                             "converter's own slicer refuses a mixed mesh.");

    // Every boundary edge of a side carries THAT SIDE'S declaration: its bound
    // segment's own BC label and (geometry, segment) key, or the config default
    // for a side that declares no binding. Resolved once per side rather than
    // once per edge, because the answer is a property of the side.
    Attached sideOf[4];
    for (int k = 0; k < 4; ++k) {
        const auto it = bound.find(sides[k]->id);
        if (it == bound.end()) sideOf[k].bc = bc;
        else                   sideOf[k] = it->second;
    }
    auto addBoundary = [&](const Attached& a, int v1, int v2) {
        MbBoundaryEdge be;
        be.v1 = v1;
        be.v2 = v2;
        be.bc = a.bc;
        be.geomId = a.geomId;
        be.segId = a.segId;
        r.boundaryEdges.push_back(be);
    };
    // ONE counter-clockwise walk of the perimeter — south left to right, east up,
    // north right to left, west down — matching the direction every other emitter
    // in this repo uses (addTaggedLoop, buildDomainBoundary). Measured, and worth
    // recording so nobody re-derives it: the direction does NOT reach the `.bnd`,
    // because exportStarCD takes a boundary face's node ORDER from the cell that
    // owns it and not from `edges`. It is consistency for a reader, not a fix.
    for (int i = 0; i + 1 < ni; ++i)
        addBoundary(sideOf[MB_SOUTH], b0.nodeAt(i, 0), b0.nodeAt(i + 1, 0));
    for (int j = 0; j + 1 < nj; ++j)
        addBoundary(sideOf[MB_EAST], b0.nodeAt(ni - 1, j), b0.nodeAt(ni - 1, j + 1));
    for (int i = ni - 1; i > 0; --i)
        addBoundary(sideOf[MB_NORTH], b0.nodeAt(i, nj - 1), b0.nodeAt(i - 1, nj - 1));
    for (int j = nj - 1; j > 0; --j)
        addBoundary(sideOf[MB_WEST], b0.nodeAt(0, j), b0.nodeAt(0, j - 1));

    r.ok = true;
    return r;
}
