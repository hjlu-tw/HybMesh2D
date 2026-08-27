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
};

struct EdgeSpec {
    std::string id;
    std::string a, b;        // corner ids, in the edge's own direction
    std::string kind;        // "wall" | "interface" | "cut"
    int count = 0;           // node count along the edge (>= 2)
    std::string law = "uniform";
    double growth = 1.0;     // "geometric"
    double delta = 0.0;      // "tanh"
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
            // Refused rather than approximated. The whole point of an
            // arc-length attachment is that a block boundary lands EXACTLY on a
            // geometry feature; guessing one would produce a slightly wrong mesh
            // with no error, which is worse than no mesh at all.
            err = where + " ('" + corner.id + "'): kind 'on_geometry' is not read in "
                  "this release. Geometry-attached corners (normalized arc length "
                  "along a source segment) arrive with the geometry-binding work; "
                  "until then every corner must be kind 'free' with an explicit 'xy'.";
            return false;
        }
        if (kind != "free") {
            err = where + " ('" + corner.id + "'): unknown kind '" + kind
                + "'. Accepted: 'free', 'on_geometry'.";
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
        if (e.contains("binding")) {
            err = where + " ('" + spec.id + "'): 'binding' (the source segment this "
                  "edge lies on) is not read in this release; every boundary edge "
                  "takes the config default BC. Geometry binding arrives with the "
                  "boundary-conditions-by-construction work.";
            return false;
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

// The points along one straight edge, including both end corners.
//
// Goes through the existing spacing laws rather than re-deriving them: they are
// pure arithmetic already used by the preprocessor, and a second implementation
// of a growth-rate solver is a guaranteed future divergence. `generateGeometric`
// at ratio 1 IS the uniform law, so "uniform" is not a special case here either.
std::vector<Point2D> discretise(const EdgeSpec& e, Point2D p0, Point2D p1) {
    const Vector2D d = p1 - p0;
    const double L = d.length();
    std::vector<double> t;
    if (e.law == "tanh")            t = HybMesh::Spacing::generateTanh(L, e.count, e.delta);
    else if (e.law == "geometric")  t = HybMesh::Spacing::generateGeometric(L, e.count, e.growth);
    else                            t = HybMesh::Spacing::generateGeometric(L, e.count, 1.0);

    std::vector<Point2D> pts;
    pts.reserve(static_cast<size_t>(e.count));
    for (int k = 0; k < e.count; ++k) {
        // Parametrise by arc-length fraction, and pin both ends onto the corners
        // exactly. A t/L that lands 1e-16 short of 1 would leave the last node
        // off the corner it is supposed to BE, and welding in this path is
        // topological precisely so that no tolerance has to rescue that.
        if (k == 0)               { pts.push_back(p0); continue; }
        if (k == e.count - 1)     { pts.push_back(p1); continue; }
        double s = (L > 0.0) ? t[static_cast<size_t>(k)] / L : 0.0;
        pts.push_back(p0 + d * s);
    }
    return pts;
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
                                           [[maybe_unused]] const std::vector<MbGeometry>& geoms,
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

    const std::vector<Point2D> south = discretise(S, pa, pb);
    const std::vector<Point2D> north = discretise(N, pd, pcc);
    const std::vector<Point2D> west  = discretise(W, pa, pd);
    const std::vector<Point2D> east  = discretise(E, pb, pcc);

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

    std::string bc = params.defaultBc;
    if (bc.empty()) {
        bc = "wall";
        r.warnings.push_back("no default boundary condition was resolved (BC_GEOM is "
                             "empty); every boundary edge is exported as 'wall'.");
    }
    r.warnings.push_back("every boundary edge carries the config default BC '" + bc
                         + "'. Naming the source segment an edge lies on, so its BC "
                           "follows from the declaration, arrives with the "
                           "boundary-conditions-by-construction work.");

    auto addBoundary = [&](int v1, int v2) {
        MbBoundaryEdge be;
        be.v1 = v1;
        be.v2 = v2;
        be.bc = bc;                 // geomId/segId stay -1: nothing binds geometry yet
        r.boundaryEdges.push_back(be);
    };
    // ONE counter-clockwise walk of the perimeter — south left to right, east up,
    // north right to left, west down — matching the direction every other emitter
    // in this repo uses (addTaggedLoop, buildDomainBoundary). Measured, and worth
    // recording so nobody re-derives it: the direction does NOT reach the `.bnd`,
    // because exportStarCD takes a boundary face's node ORDER from the cell that
    // owns it and not from `edges`. It is consistency for a reader, not a fix.
    for (int i = 0; i + 1 < ni; ++i) addBoundary(b0.nodeAt(i, 0), b0.nodeAt(i + 1, 0));
    for (int j = 0; j + 1 < nj; ++j) addBoundary(b0.nodeAt(ni - 1, j), b0.nodeAt(ni - 1, j + 1));
    for (int i = ni - 1; i > 0; --i) addBoundary(b0.nodeAt(i, nj - 1), b0.nodeAt(i - 1, nj - 1));
    for (int j = nj - 1; j > 0; --j) addBoundary(b0.nodeAt(0, j), b0.nodeAt(0, j - 1));

    r.ok = true;
    return r;
}
