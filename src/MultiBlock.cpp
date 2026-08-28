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

// The [south, east, north, west] declaration order as PROSE, so a refusal can
// point at the side the document actually wrote. `mbSideAxis` in the header owns
// the same convention's geometry (which axis a side runs along, which end it sits
// at); this array is only its names, and the two are indexed identically.
const char* const kSideName[4] = {"south", "east", "north", "west"};
// A block's four corners in logical order: (0,0), (ni-1,0), (ni-1,nj-1), (0,nj-1).
const char* const kCornerName[4] = {"i-min/j-min", "i-max/j-min",
                                    "i-max/j-max", "i-min/j-max"};

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
        // How many block sides each kind may be is checked once the blocks are
        // parsed (a wall exactly one, an interface or a cut exactly two), because
        // that is a fact about the topology and not about this edge's own object.
        // The source segment this edge LIES ON. This is where a boundary condition
        // comes from on this path: the segment's own label, carried into the export
        // with its (geometry, segment) key. Nothing downstream tests whether a node
        // is near a reference segment, so there is no tolerance in the chain to
        // drift past — which is how a curved inlet came to export a band of wall on
        // the other path.
        auto bd = e.find("binding");
        if (bd != e.end()) {
            // A binding says "this edge LIES ON that source segment", which is a
            // statement about a wall. An interface and a cut are interior lines in
            // the fluid; there is no segment for them to lie on, and accepting one
            // would make the kind and the binding two statements of one fact that
            // can only ever disagree.
            if (spec.kind != "wall") {
                err = where + " ('" + spec.id + "'): kind '" + spec.kind + "' declares a "
                      "'binding', but only a 'wall' lies on a source segment — an "
                      "interface and a cut are interior lines in the fluid. Drop the "
                      "binding, or declare the edge a wall.";
                return false;
            }
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

        // 'count' is a SEED, not a requirement: opposite sides of a block carry
        // equal counts and a shared edge is one edge named by two blocks, so the
        // counts partition into equivalence classes and one seed decides a whole
        // class. An edge that declares none keeps 0 here and is resolved later; a
        // class with no seed at all is refused naming every edge in it, because a
        // silently-chosen count decides the whole mesh density.
        auto cnt = e.find("count");
        if (cnt != e.end()) {
            if (!cnt->is_number_integer()) {
                err = where + " ('" + spec.id + "'): 'count' must be an integer node "
                      "count >= 2. Leave it out to have it propagate from an edge that "
                      "is structurally forced to match this one.";
                return false;
            }
            spec.count = cnt->get<int>();
            if (spec.count < 2) {
                err = where + " ('" + spec.id + "'): 'count' is "
                    + std::to_string(spec.count)
                    + "; an edge needs at least 2 nodes (its two end corners).";
                return false;
            }
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

// The point at ABSOLUTE arc length `s` along `path`, resuming the interval walk
// from `m` (which advances, so a caller stepping s upwards stays linear).
//
// The one place this arithmetic lives. It was written twice — here and in
// `discretise` — and the two must agree exactly or a bound edge's endpoint stops
// being the corner it is supposed to BE, which is the one disagreement this path
// has no tolerance to absorb.
Point2D lerpAtArc(const std::vector<Point2D>& path, const std::vector<double>& cum,
                  double s, size_t& m) {
    while (m + 2 < path.size() && cum[m + 1] < s) ++m;
    const double span = cum[m + 1] - cum[m];
    const double f = (span > 0.0) ? (s - cum[m]) / span : 0.0;
    return path[m] + (path[m + 1] - path[m]) * f;
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
    size_t m = 0;
    return lerpAtArc(path, cum, t * L, m);
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
        pts.push_back(lerpAtArc(path, cum, s, m));
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
    span.cum = arcLengths(out);
    const double L = span.cum.empty() ? 0.0 : span.cum.back();
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
        r.wallSpecs.clear(); r.sharedEdges.clear(); r.edgeCounts.clear();
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

    // ── Which block sides each edge is, and what its KIND allows ──────────
    //
    // Built before anything is resolved, because the kind is a claim about exactly
    // this. A "wall" is the outside of the mesh, so one block has it. An
    // "interface" is an interior boundary between two blocks and a "cut" is a wake
    // or branch line that is likewise shared but is not a boundary of anything, so
    // each of those is a side of exactly two. The kind is DECLARED and never
    // inferred from whether a binding is present: inference would file a wake cut
    // as an ordinary interface, and the two are different statements about one
    // line. `parseBlocks` has already refused an edge named twice within one
    // block, so a shared edge is always shared between two DIFFERENT blocks — a
    // block welded to itself is not fillable by a transfinite map over four sides
    // and is not silently accepted here.
    struct Use { int block; int side; };
    std::map<std::string, std::vector<Use>> uses;
    for (size_t bi = 0; bi < blocks.size(); ++bi)
        for (int k = 0; k < 4; ++k)
            uses[blocks[bi].edges[static_cast<size_t>(k)]]
                .push_back({static_cast<int>(bi), k});

    // A declaration that reaches nothing is a typo, not a preference: an edge in
    // no block and a corner on no edge are both silently absent from the mesh.
    for (const auto& e : edges) {
        const std::vector<Use>& u = uses[e.id];
        if (u.empty())
            return fail("edge '" + e.id + "' belongs to no block. Every declared edge "
                        "must be one of some block's four sides.");
        const size_t want = (e.kind == "wall") ? 1u : 2u;
        if (u.size() == want) continue;
        std::ostringstream os;
        os << "edge '" << e.id << "' is declared kind '" << e.kind << "' but is a side of "
           << u.size() << " block(s) —";
        for (const Use& x : u)
            os << " the " << kSideName[x.side] << " of block '"
               << blocks[static_cast<size_t>(x.block)].id << "'";
        os << ". A 'wall' is the outside of the mesh, so exactly one block has it; an "
              "'interface' (an interior boundary between two blocks) and a 'cut' (a wake "
              "or branch line) are each a side of exactly two.";
        return fail(os.str());
    }
    for (const auto& c : corners) {
        bool used = false;
        for (const auto& e : edges) if (e.a == c.id || e.b == c.id) used = true;
        if (!used)
            return fail("corner '" + c.id + "' is on no edge. Every declared corner "
                        "must be an end of some edge.");
    }

    auto edgeIndexById = [&edges](const std::string& id) -> int {
        for (size_t k = 0; k < edges.size(); ++k)
            if (edges[k].id == id) return static_cast<int>(k);
        return -1;
    };

    // ── A block's frame comes from its OWN declaration ────────────────────
    //
    // The four edges are declared in [south, east, north, west] order, and the
    // block's i direction is its SOUTH edge's own declared direction. The other
    // three sides are then traversed in whichever direction closes the ring:
    // south and west meet at the block's i-min/j-min corner, south and east at
    // i-max/j-min, north and west at i-min/j-max, north and east at i-max/j-max.
    //
    // Allowing those three to be declared either way is a DEPARTURE from the
    // single-block release, which refused any side not written in the convention's
    // direction. The reason is welding: a shared edge is ONE edge with ONE declared
    // direction, named by two blocks whose logical frames need not agree about it,
    // so under the old rule a neighbour whose shared edge runs the other way could
    // not be declared at all. Nothing is INFERRED by the change — the frame is
    // still fixed entirely by the south edge plus which corners the other three
    // touch, and a set of four edges that does not close a ring is refused BY NAME
    // rather than repaired, because a repaired one is a mirrored block, i.e. a mesh
    // rather than an error.
    struct Frame {
        std::string corner[4];   // A (0,0), B (ni-1,0), C (ni-1,nj-1), D (0,nj-1)
        int edge[4] = {-1, -1, -1, -1};
        bool rev[4] = {false, false, false, false};
    };
    std::vector<Frame> frames(blocks.size());
    for (size_t bi = 0; bi < blocks.size(); ++bi) {
        const BlockSpec& blk = blocks[bi];
        Frame& f = frames[bi];
        for (int k = 0; k < 4; ++k) {
            f.edge[k] = edgeIndexById(blk.edges[static_cast<size_t>(k)]);
            if (f.edge[k] < 0)
                return fail("block '" + blk.id + "': edge '"
                            + blk.edges[static_cast<size_t>(k)] + "' resolved during "
                              "parsing and not during filling; the topology was not read "
                              "consistently and no mesh was made.");
        }
        const EdgeSpec& S = edges[static_cast<size_t>(f.edge[0])];
        const EdgeSpec& E = edges[static_cast<size_t>(f.edge[1])];
        const EdgeSpec& N = edges[static_cast<size_t>(f.edge[2])];
        const EdgeSpec& W = edges[static_cast<size_t>(f.edge[3])];
        auto ringFail = [&](const EdgeSpec& e, const char* side,
                            const std::string& want) -> MbResult& {
            return fail("block '" + blk.id + "': its four sides do not close a ring. Its "
                        "south edge '" + S.id + "' runs ['" + S.a + "', '" + S.b
                      + "'], which fixes the block's i direction, so its "
                      + std::string(side) + " edge '" + e.id + "' must have an end at "
                      + want + " — but it runs ['" + e.a + "', '" + e.b + "']. A block's "
                        "four edges must close a ring: south and west meet at its "
                        "i-min/j-min corner, south and east at i-max/j-min, north and west "
                        "at i-min/j-max, north and east at i-max/j-max. Each of the other "
                        "three may be declared in either direction; which way it is "
                        "traversed follows from the ring.");
        };
        f.corner[0] = S.a;
        f.corner[1] = S.b;
        if (W.a == f.corner[0])      { f.corner[3] = W.b; f.rev[3] = false; }
        else if (W.b == f.corner[0]) { f.corner[3] = W.a; f.rev[3] = true; }
        else return ringFail(W, "west", "corner '" + f.corner[0] + "'");
        if (E.a == f.corner[1])      { f.corner[2] = E.b; f.rev[1] = false; }
        else if (E.b == f.corner[1]) { f.corner[2] = E.a; f.rev[1] = true; }
        else return ringFail(E, "east", "corner '" + f.corner[1] + "'");
        if (N.a == f.corner[3] && N.b == f.corner[2])      f.rev[2] = false;
        else if (N.a == f.corner[2] && N.b == f.corner[3]) f.rev[2] = true;
        else return ringFail(N, "north", "both corners '" + f.corner[3] + "' and '"
                                       + f.corner[2] + "'");
        for (int x = 0; x < 4; ++x)
            for (int y = x + 1; y < 4; ++y)
                if (f.corner[x] == f.corner[y])
                    return fail("block '" + blk.id + "': its four sides do not close a "
                                "ring — corner '" + f.corner[x] + "' comes out as two "
                                "different corners of the block (" + kCornerName[x]
                              + " and " + kCornerName[y] + "), so it has no interior to "
                                "fill.");
    }

    // ── Point-count propagation ───────────────────────────────────────────
    //
    // Two edges are structurally forced to carry the same node count when they are
    // OPPOSITE SIDES of one block: a structured block is ni x nj nodes, so its
    // south and north sides have the same number and so do its west and east.
    // Because a shared edge is ONE declared edge that two blocks both name, that
    // single relation propagates ACROSS blocks too — which is why there is no
    // second rule here for an interface. The relation partitions the edges into
    // equivalence classes; the user seeds a few and the rest are resolved.
    std::vector<int> parent(edges.size());
    for (size_t k = 0; k < edges.size(); ++k) parent[k] = static_cast<int>(k);
    auto findRoot = [&parent](int x) {
        while (parent[static_cast<size_t>(x)] != x) {
            parent[static_cast<size_t>(x)] =
                parent[static_cast<size_t>(parent[static_cast<size_t>(x)])];
            x = parent[static_cast<size_t>(x)];
        }
        return x;
    };
    // Each merge is also recorded as a LINK, because a conflict has to be reported
    // with the chain that propagated between the two seeds. On a topology with
    // dozens of edges "counts disagree" does not say which declaration to change.
    struct Link { int other; size_t block; int sideA; int sideB; };
    std::vector<std::vector<Link>> adj(edges.size());
    for (size_t bi = 0; bi < blocks.size(); ++bi) {
        const int pairs[2][2] = {{0, 2}, {3, 1}};   // south/north, west/east
        for (const auto& pr : pairs) {
            const int a = frames[bi].edge[pr[0]], b = frames[bi].edge[pr[1]];
            adj[static_cast<size_t>(a)].push_back({b, bi, pr[0], pr[1]});
            adj[static_cast<size_t>(b)].push_back({a, bi, pr[1], pr[0]});
            parent[static_cast<size_t>(findRoot(a))] = findRoot(b);
        }
    }
    // `adj` is complete and never touched again, so the Link pointers this walk
    // keeps cannot dangle.
    auto chainBetween = [&](int from, int to) {
        std::vector<int> prevE(edges.size(), -1);
        std::vector<const Link*> via(edges.size(), nullptr);
        std::vector<bool> seen(edges.size(), false);
        std::vector<int> queue;
        queue.push_back(from);
        seen[static_cast<size_t>(from)] = true;
        for (size_t qi = 0; qi < queue.size(); ++qi) {
            const int cur = queue[qi];
            if (cur == to) break;
            for (const Link& l : adj[static_cast<size_t>(cur)]) {
                if (seen[static_cast<size_t>(l.other)]) continue;
                seen[static_cast<size_t>(l.other)] = true;
                prevE[static_cast<size_t>(l.other)] = cur;
                via[static_cast<size_t>(l.other)] = &l;
                queue.push_back(l.other);
            }
        }
        std::vector<std::string> lines;
        for (int at = to; at != from && prevE[static_cast<size_t>(at)] >= 0;
             at = prevE[static_cast<size_t>(at)]) {
            const Link* l = via[static_cast<size_t>(at)];
            lines.push_back(std::string("    '")
                + edges[static_cast<size_t>(prevE[static_cast<size_t>(at)])].id
                + "' and '" + edges[static_cast<size_t>(at)].id
                + "' are opposite sides (" + kSideName[l->sideA] + " / "
                + kSideName[l->sideB] + ") of block '" + blocks[l->block].id + "'\n");
        }
        std::string out;
        for (size_t k = lines.size(); k-- > 0;) out += lines[k];
        return out;
    };

    // The seeds, kept apart from the resolved counts so a run can report which of
    // the two each edge got.
    std::vector<int> seeded(edges.size(), 0);
    for (size_t k = 0; k < edges.size(); ++k) seeded[k] = edges[k].count;
    std::map<int, std::vector<int>> classes;
    for (size_t k = 0; k < edges.size(); ++k)
        classes[findRoot(static_cast<int>(k))].push_back(static_cast<int>(k));
    for (const auto& kv : classes) {
        int seed = -1;
        for (int i : kv.second) {
            if (seeded[static_cast<size_t>(i)] <= 0) continue;
            if (seed < 0) { seed = i; continue; }
            if (seeded[static_cast<size_t>(i)] == seeded[static_cast<size_t>(seed)]) continue;
            return fail("the topology declares two different node counts for edges that "
                        "are structurally forced to carry the same one: edge '"
                      + edges[static_cast<size_t>(seed)].id + "' declares count "
                      + std::to_string(seeded[static_cast<size_t>(seed)]) + " and edge '"
                      + edges[static_cast<size_t>(i)].id + "' declares count "
                      + std::to_string(seeded[static_cast<size_t>(i)])
                      + ". Opposite sides of a block carry equal counts, and a shared edge "
                        "is ONE edge named by two blocks, so the count propagates along "
                        "this chain:\n" + chainBetween(seed, i)
                      + "  Change one of the two counts, or declare a topology in which "
                        "those two edges are not linked by such a chain.");
        }
        if (seed < 0) {
            std::ostringstream os;
            os << "no edge in a group of " << kv.second.size() << " structurally linked "
                  "edge(s) declares a 'count', so nothing fixes the node count for any of "
                  "them:";
            for (int i : kv.second) os << " '" << edges[static_cast<size_t>(i)].id << "'";
            os << ". Seed ONE of them with \"count\": <n> (an integer >= 2) and the rest "
                  "follow — opposite sides of a block carry equal counts, and a shared "
                  "edge is one edge named by two blocks.";
            return fail(os.str());
        }
        for (int i : kv.second)
            edges[static_cast<size_t>(i)].count = seeded[static_cast<size_t>(seed)];
    }
    for (size_t k = 0; k < edges.size(); ++k)
        r.edgeCounts.push_back({edges[k].id, edges[k].count, seeded[k] > 0});

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

    // Resolved once per edge rather than once per boundary edge, because the answer
    // is a property of the edge: its bound segment's own BC label and (geometry,
    // segment) key, or the config default for an edge that declares no binding.
    std::vector<Attached> edgeBc(edges.size());
    for (size_t k = 0; k < edges.size(); ++k) {
        const auto it = bound.find(edges[k].id);
        if (it == bound.end()) edgeBc[k].bc = bc;
        else                   edgeBc[k] = it->second;
    }

    // ── Node allocation: every shared node is allocated ONCE ──────────────
    //
    // This is the whole of the welding, and there is no distance anywhere in it. A
    // corner gets one node because it is one declared corner; an edge gets its
    // interior nodes once because it is one declared edge; and a block reads the
    // node IDS of its four sides instead of generating its own boundary. So the
    // k-th node along a shared edge IS the k-th node both blocks see, and the two
    // sides cannot be a tolerance apart because there is only one of them.
    //
    // Coordinate welding is not merely not preferred here, it is unavailable: wall
    // spacing on a real case is around 1e-7 while far-field spacing is around
    // 1e-1, and no single tolerance exists between those two scales. This is the
    // same rule the iso-line tracer follows, which chains by mesh EDGE IDENTITY
    // and never by welding coordinates. Two corners declared at the SAME
    // coordinates under DIFFERENT ids therefore stay two nodes: the declaration is
    // the only thing that can say they are one.
    std::map<std::string, int> cornerNode;
    for (const auto& c : corners) {
        cornerNode[c.id] = static_cast<int>(r.nodes.size());
        r.nodes.push_back(c.xy);
    }

    // One edge's node ids, in its OWN declared direction, and their positions.
    struct EdgeNodes { std::vector<int> ids; std::vector<Point2D> pts; };
    std::vector<EdgeNodes> eNodes(edges.size());
    for (size_t k = 0; k < edges.size(); ++k) {
        const EdgeSpec& e = edges[k];
        const Corner* ca = cornerById(e.a);
        const Corner* cb = cornerById(e.b);
        // The parse already proved both ends resolve, so this branch should be
        // dead — but a silent fallback on a broken invariant meshes a block nobody
        // declared, and a wrong mesh is the one outcome worse than no mesh.
        if (!ca || !cb)
            return fail("edge '" + e.id + "': a corner resolved during parsing and not "
                        "during filling; the topology was not read consistently and no "
                        "mesh was made.");
        // The polyline this edge RUNS ALONG. For an unbound edge that is the chord
        // between its two corners; for a bound one it is the stretch of its source
        // segment the edge covers, which is what makes "this edge lies on that
        // segment" true rather than merely declared.
        std::vector<Point2D> path;
        const auto bd = bound.find(e.id);
        if (bd == bound.end()) path = {ca->xy, cb->xy};
        else {
            const SegSpan& sp = spans.at({bd->second.geomId, bd->second.segId});
            path = subPath(sp.pts, sp.cum, bd->second.ta, bd->second.tb);
        }
        eNodes[k].pts = discretise(e, path);
        if (eNodes[k].pts.size() != static_cast<size_t>(e.count))
            return fail("edge '" + e.id + "': its " + std::to_string(e.count)
                        + " nodes could not be distributed along it; the topology was not "
                          "read consistently and no mesh was made.");
        // The two ends ARE the corner nodes rather than copies of them a tolerance
        // away. `discretise` pins them onto the path's own first and last point,
        // and for a bound edge that point is the very geometry point the corner
        // resolved to — both come out of `pointAtArc` at the same index, so they
        // are equal bit for bit and the position written here is the corner's.
        eNodes[k].ids.resize(static_cast<size_t>(e.count));
        eNodes[k].ids.front() = cornerNode[e.a];
        eNodes[k].ids.back() = cornerNode[e.b];
        for (int t = 1; t + 1 < e.count; ++t) {
            eNodes[k].ids[static_cast<size_t>(t)] = static_cast<int>(r.nodes.size());
            r.nodes.push_back(eNodes[k].pts[static_cast<size_t>(t)]);
        }
    }

    // ── Fill every block ──────────────────────────────────────────────────
    for (size_t bi = 0; bi < blocks.size(); ++bi) {
        const BlockSpec& blk = blocks[bi];
        const Frame& f = frames[bi];
        const int blockIdx = static_cast<int>(bi);

        // The four sides in the BLOCK's own i/j direction: the declared edge, run
        // forwards or backwards as the ring requires. That one reversal is what
        // lets a single declared edge serve two blocks whose frames disagree about
        // which way it runs — and it is the only place orientation is applied, so
        // the ids and the positions cannot come out reversed with respect to each
        // other.
        std::vector<Point2D> sPts[4];
        std::vector<int> sIds[4];
        for (int k = 0; k < 4; ++k) {
            const EdgeNodes& en = eNodes[static_cast<size_t>(f.edge[k])];
            sPts[k] = en.pts;
            sIds[k] = en.ids;
            if (f.rev[k]) {
                std::reverse(sPts[k].begin(), sPts[k].end());
                std::reverse(sIds[k].begin(), sIds[k].end());
            }
        }
        const int ni = static_cast<int>(sPts[MB_SOUTH].size());
        const int nj = static_cast<int>(sPts[MB_WEST].size());
        if (static_cast<int>(sPts[MB_NORTH].size()) != ni
            || static_cast<int>(sPts[MB_EAST].size()) != nj)
            return fail("block '" + blk.id + "': its opposite sides came out with "
                        "different node counts after propagation; the topology was not "
                        "read consistently and no mesh was made.");

        // A clockwise corner ring makes EVERY cell in the block inverted, so this
        // is a bad block orientation: a defect of the DECLARATION, readable before
        // a single node exists, with an actionable fix. Refused with the topology
        // code rather than exported under the inverted-cell one, and the difference
        // is not a technicality — the inverted-cell code is for a valid declaration
        // whose GEOMETRY came out folded, which is worth looking at; a backwards
        // ring is worth fixing, and there is nothing to look at because no one
        // wants the mesh either way. Not repaired silently either: re-winding would
        // mean the mesh no longer matches the document that declared it.
        const Point2D pa = sPts[MB_SOUTH].front(), pb = sPts[MB_SOUTH].back();
        const Point2D pcc = sPts[MB_EAST].back(), pd = sPts[MB_WEST].back();
        {
            const double area2 = (pb - pa).cross(pcc - pa) + (pcc - pa).cross(pd - pa);
            if (area2 <= 0.0)
                return fail("block '" + blk.id + "': its corners '" + f.corner[0] + "', '"
                    + f.corner[1] + "', '" + f.corner[2] + "', '" + f.corner[3]
                    + "' wind clockwise (signed area " + std::to_string(0.5 * area2)
                    + "), so every cell in it would be inverted. Reverse its south edge's "
                      "own corner pair, or swap the block's south and north edges.");
        }

        // The four sides meet at four SHARED corner nodes, which the ring match
        // already proved as ids. Checked rather than assumed, and checked BEFORE
        // the writes below overwrite one with the other: a mismatch here would be a
        // block stitched to itself wrongly, which is a wrong mesh and not an error.
        if (sIds[MB_SOUTH].front() != sIds[MB_WEST].front()
            || sIds[MB_SOUTH].back() != sIds[MB_EAST].front()
            || sIds[MB_NORTH].front() != sIds[MB_WEST].back()
            || sIds[MB_NORTH].back() != sIds[MB_EAST].back())
            return fail("block '" + blk.id + "': its four sides do not meet at four shared "
                        "corner nodes; the topology was not read consistently and no mesh "
                        "was made.");

        MbBlock filled;
        filled.id = blk.id;
        filled.ni = ni;
        filled.nj = nj;
        filled.nodeIds.assign(static_cast<size_t>(ni) * static_cast<size_t>(nj), -1);
        auto at = [&filled, ni](int i, int j) -> int& {
            return filled.nodeIds[static_cast<size_t>(j) * static_cast<size_t>(ni)
                                  + static_cast<size_t>(i)];
        };
        // The boundary is READ from the sides, never regenerated. That is the
        // welding: a node on a shared edge is written once, by the edge.
        for (int i = 0; i < ni; ++i) {
            at(i, 0) = sIds[MB_SOUTH][static_cast<size_t>(i)];
            at(i, nj - 1) = sIds[MB_NORTH][static_cast<size_t>(i)];
        }
        for (int j = 0; j < nj; ++j) {
            at(0, j) = sIds[MB_WEST][static_cast<size_t>(j)];
            at(ni - 1, j) = sIds[MB_EAST][static_cast<size_t>(j)];
        }
        // Only the INTERIOR is interpolated. Transfinite (Coons) interpolation is
        // exact on the boundary, but "exact" there means it reproduces the side to
        // within the rounding of one subtraction, and a shared edge must be one
        // curve rather than two agreeing ones — so the side's own discretisation is
        // the definitive answer and the blend is asked only about the inside.
        for (int j = 1; j + 1 < nj; ++j) {
            for (int i = 1; i + 1 < ni; ++i) {
                at(i, j) = static_cast<int>(r.nodes.size());
                r.nodes.push_back(coons(sPts[MB_SOUTH], sPts[MB_NORTH],
                                        sPts[MB_WEST], sPts[MB_EAST], i, j, ni, nj));
            }
        }
        r.blocks.push_back(filled);
        const MbBlock& b0 = r.blocks.back();

        // Publish what the DECLARATION asks the first cell height off each wall to
        // be, for the quality report to measure the fill against
        // (include/MbQuality.hpp).
        //
        // It has to be published from here because only this scope still knows the
        // spacing laws: the request off a side is the FIRST INTERVAL of the edge
        // running away from it, taken from the perpendicular edge at each of the
        // side's two corners, and once the block is a grid of positions those laws
        // are gone. Which edge that is comes from `mbSideAxis`, so the [south,
        // east, north, west] convention is read here rather than restated.
        //
        // WHAT THIS IS NOT, stated here because it is easy to over-read: in this
        // release nothing declares a wall-normal first-cell height independently of
        // the edge distribution, so the request is DERIVED FROM THE SAME LAW the
        // fill reproduces. The transfinite blend is exact on the boundary, so the
        // number the report computes from it is zero at the side's two end columns
        // BY CONSTRUCTION, and what it really measures in between is interior
        // distortion. An independent target arrives with the wall-spacing
        // resolution work (BL_INITIAL_THICKNESS and friends); when it does, only
        // these two lines change source and nothing that reads the report has to
        // change.
        {
            auto firstInterval = [](const std::vector<Point2D>& e, bool fromEnd) {
                if (e.size() < 2) return 0.0;
                return fromEnd ? (e[e.size() - 1] - e[e.size() - 2]).length()
                               : (e[1] - e[0]).length();
            };
            for (int k = 0; k < 4; ++k) {
                const MbSide side = static_cast<MbSide>(k);   // sIds[] is in this order
                const MbSideAxis ax = mbSideAxis(side);
                const EdgeSpec& e = edges[static_cast<size_t>(f.edge[k])];
                // Gated on the KIND: an interface or a cut is an interior line, and
                // "how tall is the first cell off it" is not a question about one.
                if (e.kind != "wall") continue;
                const std::vector<Point2D>& perpLo = ax.alongI ? sPts[MB_WEST]
                                                               : sPts[MB_SOUTH];
                const std::vector<Point2D>& perpHi = ax.alongI ? sPts[MB_EAST]
                                                               : sPts[MB_NORTH];
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
                const int n00 = b0.nodeAt(i, j),         n10 = b0.nodeAt(i + 1, j);
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

        // ONE counter-clockwise walk of the block's perimeter — south left to
        // right, east up, north right to left, west down — matching the direction
        // every other emitter in this repo uses (addTaggedLoop, buildDomainBoundary).
        // Measured, and worth recording so nobody re-derives it: the direction does
        // NOT reach the `.bnd`, because exportStarCD takes a boundary face's node
        // ORDER from the cell that owns it and not from `edges`. It is consistency
        // for a reader, not a fix.
        //
        // Only a WALL side is emitted. An interface or a cut is an INTERIOR line:
        // both blocks have cells against it, so emitting it as a boundary face
        // would hand the exporter a face with two owners and the solver a wall
        // through the middle of the fluid.
        auto isWall = [&](int k) {
            return edges[static_cast<size_t>(f.edge[k])].kind == "wall";
        };
        auto addBoundary = [&](int k, int v1, int v2) {
            const Attached& a = edgeBc[static_cast<size_t>(f.edge[k])];
            MbBoundaryEdge be;
            be.v1 = v1;
            be.v2 = v2;
            be.bc = a.bc;
            be.geomId = a.geomId;
            be.segId = a.segId;
            r.boundaryEdges.push_back(be);
        };
        if (isWall(MB_SOUTH))
            for (int i = 0; i + 1 < ni; ++i)
                addBoundary(MB_SOUTH, b0.nodeAt(i, 0), b0.nodeAt(i + 1, 0));
        if (isWall(MB_EAST))
            for (int j = 0; j + 1 < nj; ++j)
                addBoundary(MB_EAST, b0.nodeAt(ni - 1, j), b0.nodeAt(ni - 1, j + 1));
        if (isWall(MB_NORTH))
            for (int i = ni - 1; i > 0; --i)
                addBoundary(MB_NORTH, b0.nodeAt(i, nj - 1), b0.nodeAt(i - 1, nj - 1));
        if (isWall(MB_WEST))
            for (int j = nj - 1; j > 0; --j)
                addBoundary(MB_WEST, b0.nodeAt(0, j), b0.nodeAt(0, j - 1));
    }

    // The interior lines two blocks were welded along, as data. Reported rather
    // than left implicit because the KIND is a declaration and a claim a run
    // cannot show is one nobody can check: an interface and a cut weld by the same
    // rule today, so the report is what tells a user which shared lines the
    // document says are wake cuts. See MbSharedEdge.
    for (size_t k = 0; k < edges.size(); ++k) {
        if (edges[k].kind == "wall") continue;
        const std::vector<Use>& u = uses[edges[k].id];
        // The arity check above already refused anything but exactly two, so this
        // branch should be dead — but reading past the end of a vector on a broken
        // invariant is the one failure that would not announce itself.
        if (u.size() != 2)
            return fail("edge '" + edges[k].id + "': it is shared by "
                        + std::to_string(u.size()) + " block sides during reporting and "
                          "by two during checking; the topology was not read "
                          "consistently and no mesh was made.");
        MbSharedEdge se;
        se.edgeId = edges[k].id;
        se.kind = edges[k].kind;
        se.nodes = edges[k].count;
        se.blockA = u[0].block;
        se.sideA = u[0].side;
        se.blockB = u[1].block;
        se.sideB = u[1].side;
        r.sharedEdges.push_back(se);
    }

    if (!params.splitQuads)
        r.warnings.push_back("quad splitting is OFF, so this mesh is exported as quads. "
                             "That is a diagnostic setting: the solver's incenter "
                             "reconstruction is undefined on quad cells, and the grid "
                             "converter's own slicer refuses a mixed mesh.");

    r.ok = true;
    return r;
}
