#ifndef MESH_MODE_HPP
#define MESH_MODE_HPP

#include <string>
#include <vector>

// Which GENERATION PATH a run takes, and which parameters that path never reads.
//
// This header is the ONE declaration of the second fact. A parameter that means
// nothing in the active mode must be NAMED in a warning rather than silently do
// nothing — the same rule `Config::parseBLOverrideToken` already applies to an
// unrecognised per-geometry override, and for the same reason: "the user sets a
// value and it does nothing" has no symptom except a mesh nobody asked for.
//
// The list lives here rather than at the warning site so it can be answered
// WITHOUT a Config in hand (the GUI's field-spec tables carry the same fact as a
// per-field `modes=` declaration, and `tests/test_field_spec_tables.py` check 14
// compares the two lists in both directions by reading these macros). A prose
// list at the call site could not be compared with anything.
struct Config;   // include Config.hpp for the definition; declared here to stay acyclic

enum MeshMode {
    // The existing path: boundary-layer quads grown outward from every geometry,
    // transition layers, Gmsh triangles in the far field. THE DEFAULT, so every
    // case that exists today produces exactly the mesh it produced before.
    MESH_MODE_HYBRID     = 0,
    // Topology-driven multi-block structured: the blocking is DECLARED in a JSON
    // document, every block is filled with structured quads and the quads are
    // split to triangles before export. Uses Gmsh nowhere.
    MESH_MODE_MULTIBLOCK = 1,
};

// Parameters the multi-block path never reads, as (KEY, Config member) rows. The
// member is here so "did the user set it?" is answered by comparing against a
// default-constructed Config rather than by tracking which lines a file carried:
// the GUI writes nearly every key on every save, so "the key appeared in the file"
// would warn about all of them at once and mean nothing.
//
// GMSH_NUM_THREADS is on this list although issue #49's acceptance text names only
// "the Gmsh algorithm and optimize settings": this path uses Gmsh nowhere, so a
// thread count for it is inert by exactly the same argument. SURFACE_MESH_SIZE /
// AUTO_SURFACE_SIZE are deliberately NOT here — #49 does not name them, and
// whether a surface size seeds default edge counts in this path is a question the
// later tickets answer. Claiming it inert now would be a guess written into a gate.
#define HYBMESH_MULTIBLOCK_INERT_GLOBALS(X)                 \
    X("DOMAIN_X_MIN",              xMin)                    \
    X("DOMAIN_X_MAX",              xMax)                    \
    X("DOMAIN_Y_MIN",              yMin)                    \
    X("DOMAIN_Y_MAX",              yMax)                    \
    X("FARFIELD_MESH_SIZE",        farFieldSize)            \
    X("AUTO_FARFIELD_SIZE",        autoFarFieldSize)        \
    X("FARFIELD_GROWTH_RATE",      farFieldGrowthRate)      \
    X("FARFIELD_BIDIRECTIONAL",    farFieldBidirectional)   \
    X("FARFIELD_GROWTH_RATE_OUTER",farFieldGrowthRateOuter) \
    X("GMSH_ALGORITHM",            gmshAlgorithm)           \
    X("GMSH_OPTIMIZE",             gmshOptimize)            \
    X("GMSH_NUM_THREADS",          gmshNumThreads)          \
    X("SEED_SIZE",                 seedSize)                \
    X("SEED_RADIUS",               seedRadius)              \
    X("SEED_MODE",                 seedMode)                \
    X("BL_MERGE_CONCAVE",          blMergeConcave)          \
    X("BL_SMOOTHING_ITERS",        blSmoothingIters)

// Inert parameters whose value is a LIST rather than a scalar, so "did the user
// set it?" is "is there one at all". Declared here rather than special-cased in the
// .cpp for one reason: the GUI's cross-check reads these macros, and a key warned
// about by a hand-written branch would be invisible to it.
#define HYBMESH_MULTIBLOCK_INERT_LISTS(X) \
    X("SEED_FILE", seedFiles)

// The boundary-layer parameters that DO survive into the multi-block path, where
// they are the wall-normal clustering law plus the projection basis. Declared as
// the SURVIVORS rather than as the 18 casualties, because the survivors are the
// short list and because a BL parameter added to include/BLParams.hpp tomorrow is
// far more likely to be another corner/junction knob than another wall-spacing
// one — so the derived list (every declared BL key minus these four) gets a new
// row right by default instead of silently exempting it.
#define HYBMESH_MULTIBLOCK_BL_SURVIVING(X) \
    X("BL_INITIAL_THICKNESS")              \
    X("BL_GROWTH_RATE")                    \
    X("BL_LAYERS")                         \
    X("BL_USE_ANALYTIC_GEOM")

namespace hybmesh {

// Human-readable name for the banner and for an error message.
const char* meshModeName(int mode);

// Is this a mode the tool has? Unknown modes are REFUSED by Config::validate()
// rather than clamped to 0 — see the comment there.
bool isKnownMeshMode(int mode);

// Does the declared boundary-layer parameter `key` survive into `mode`?
bool blParamSurvives(int mode, const std::string& key);

// The keys `cfg`'s mode never reads AND which `cfg` actually SETS, i.e. whose
// value differs from a default-constructed Config's. Warnings as DATA: the caller
// decides how to say it, and a test can assert on the list without capturing a log.
//
// In MESH_MODE_HYBRID this is always empty: that path reads everything it parses.
std::vector<std::string> inertParamsSet(const Config& cfg);

}  // namespace hybmesh

#endif  // MESH_MODE_HPP
