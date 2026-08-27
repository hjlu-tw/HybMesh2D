#include "MeshMode.hpp"
#include "Config.hpp"

#include <map>

namespace {

// Every declared boundary-layer parameter as (KEY -> value-as-double), so the
// user's settings and the defaults can be compared without naming a single field
// by hand. The narrowing rule is the declaration's own (see BLParams.hpp): one
// rule for every row, rather than a per-field decision.
std::map<std::string, double> blSnapshot(const BLParams& p) {
    std::map<std::string, double> out;
    forEachBLParam(p, [&out](const char* key, const auto& v) {
        out[key] = static_cast<double>(v);
    });
    return out;
}

// Did the user set `key` to something other than a default-constructed BLParams'
// value? One comparison for every row, over the declaration itself, so neither
// caller below names a field by hand.
bool blParamDiffersFromDefault(const BLParams& p, const std::string& key) {
    static const std::map<std::string, double> base = blSnapshot(BLParams{});
    const std::map<std::string, double> mine = blSnapshot(p);
    auto a = mine.find(key), b = base.find(key);
    return a != mine.end() && b != base.end() && a->second != b->second;
}

}  // namespace

const char* hybmesh::meshModeName(int mode) {
    switch (mode) {
        case MESH_MODE_HYBRID:     return "hybrid: boundary layer + Gmsh far field";
        case MESH_MODE_MULTIBLOCK: return "multi-block structured (topology-driven)";
        default:                   return "unknown";
    }
}

bool hybmesh::isKnownMeshMode(int mode) {
    return mode == MESH_MODE_HYBRID || mode == MESH_MODE_MULTIBLOCK;
}

bool hybmesh::blParamSurvives(int mode, const std::string& key) {
    if (mode != MESH_MODE_MULTIBLOCK) return true;
#define HYBMESH_MB_SURVIVES(k) if (key == k) return true;
    HYBMESH_MULTIBLOCK_BL_SURVIVING(HYBMESH_MB_SURVIVES)
#undef HYBMESH_MB_SURVIVES
    return false;
}

std::vector<std::string> hybmesh::inertParamsSet(const Config& cfg) {
    // BLIND SPOT, named rather than papered over: "set" is measured against a
    // default-constructed Config, and the caller asks this AFTER Config::validate()
    // has had its say. Two of validate()'s clamps land back exactly ON the default
    // (FARFIELD_MESH_SIZE <= 0 -> 1.0, BL_TRANSITION_GROWTH_RATE <= 1.0 -> 1.2), so
    // a user who wrote one of those two invalid values gets no inert-parameter
    // warning for it. Deliberately not chased: validate() has already warned about
    // that value by name on its own line, so the parameter is not silent — which is
    // the property this function exists to provide.
    std::vector<std::string> out;
    if (cfg.meshMode != MESH_MODE_MULTIBLOCK) return out;

    const Config def;

    // A refinement seed is a FILE list rather than a scalar, so "set" is "there is
    // one at all". Named for the same reason as the three scalars beside it: a seed
    // only ever drove the far-field size field, and this path has no far field.
#define HYBMESH_MB_INERT_LIST_CHECK(key, member) \
    if (!cfg.member.empty()) out.push_back(key);
    HYBMESH_MULTIBLOCK_INERT_LISTS(HYBMESH_MB_INERT_LIST_CHECK)
#undef HYBMESH_MB_INERT_LIST_CHECK

#define HYBMESH_MB_INERT_CHECK(key, member) \
    if (!(cfg.member == def.member)) out.push_back(key);
    HYBMESH_MULTIBLOCK_INERT_GLOBALS(HYBMESH_MB_INERT_CHECK)
#undef HYBMESH_MB_INERT_CHECK

    // The boundary-layer parameters, in declaration order. Derived from
    // BLParams.hpp rather than listed, so a parameter added there is covered here
    // with no edit — the same property that makes the .dat reader unforgettable.
    forEachBLParam(cfg.bl, [&](const char* key, const auto&) {
        if (blParamSurvives(cfg.meshMode, key)) return;
        if (blParamDiffersFromDefault(cfg.bl, key)) out.push_back(key);
    });

    return out;
}

std::vector<std::string> hybmesh::blSurvivorsUnread(const Config& cfg) {
    // The other half of "a value this run does not read is NAMED". The mirror of
    // the loop above — same declaration, same "set" test, opposite membership —
    // and it goes away entirely when the multi-block path grows its wall-normal
    // clustering law. See HYBMESH_MULTIBLOCK_BL_SURVIVING for why they are not
    // simply moved onto the inert list instead.
    std::vector<std::string> out;
    if (cfg.meshMode != MESH_MODE_MULTIBLOCK) return out;
    forEachBLParam(cfg.bl, [&](const char* key, const auto&) {
        if (!blParamSurvives(cfg.meshMode, key)) return;
        if (blParamDiffersFromDefault(cfg.bl, key)) out.push_back(key);
    });
    return out;
}
