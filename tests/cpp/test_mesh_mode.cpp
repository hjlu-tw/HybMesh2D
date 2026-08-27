// hybmesh::inertParamsSet — "which parameters does the active mode never read?"
//
// This executable links hybmesh_pure and NOTHING else: not gmsh, not
// hybmesh_core, not a Mesh. Config.hpp is a header-only .dat parser, so the
// question is answerable here, and this executable failing to link is the signal
// that stopped being true.
//
// What the seam buys, concretely. The answer is DATA, so every claim below is a
// vector comparison rather than a scrape of a log:
//
//   * the four surviving boundary-layer parameters are proven silent on the INERT
//     list (check 6b covers the second list they ARE on), which is a
//     negative and is the half a "does it warn?" test through the binary makes
//     awkward — you have to prove the absence of a line;
//   * the 18 casualties are DERIVED from include/BLParams.hpp minus the four
//     survivors, so a parameter added to that declaration is covered here with no
//     edit, and check 4 below is what makes that derivation a property rather
//     than a coincidence;
//   * "set" means "differs from a default-constructed Config", and check 2 pins
//     it in the one direction that is easy to get wrong: a value the user wrote
//     that happens to EQUAL the default must not warn, or a GUI-written config
//     (which emits nearly every key on every save) would warn about all of them
//     and mean nothing.
//
// Blind spots, named rather than papered over. This file does not run the mesher,
// so it says nothing about the exit code, the wording of the warning line or the
// refusal — those are behavioural and belong to
// tools/PreProcessor/tests/test_mesh_mode_surface.py, which drives the real
// binary. And it cannot see a key that is inert in fact but missing from
// HYBMESH_MULTIBLOCK_INERT_GLOBALS: nothing here knows what the unwritten
// multi-block path will read. That direction is covered, for the keys the GUI
// also carries, by test_field_spec_tables.py check 14.
#include "check.hpp"

#include "Config.hpp"
#include "ExitCodes.hpp"
#include "MeshMode.hpp"

#include <algorithm>
#include <set>
#include <string>
#include <vector>

namespace {

bool has(const std::vector<std::string>& v, const std::string& k) {
    return std::find(v.begin(), v.end(), k) != v.end();
}

// Every KEY the boundary-layer declaration carries.
std::set<std::string> declaredBLKeys() {
    std::set<std::string> out;
    BLParams p;
    forEachBLParam(p, [&out](const char* key, const auto&) { out.insert(key); });
    return out;
}

std::set<std::string> survivingBLKeys() {
#define HYBMESH_MB_SURV_KEY(k) k,
    return { HYBMESH_MULTIBLOCK_BL_SURVIVING(HYBMESH_MB_SURV_KEY) };
#undef HYBMESH_MB_SURV_KEY
}

// A Config in multi-block mode with EVERY inert parameter moved off its default,
// so one call answers "is each of them named?".
Config allInertSet() {
    Config c;
    c.meshMode = MESH_MODE_MULTIBLOCK;
    c.xMin -= 1.0; c.xMax += 1.0; c.yMin -= 1.0; c.yMax += 1.0;
    c.farFieldSize += 1.0;
    c.autoFarFieldSize = !c.autoFarFieldSize;
    c.farFieldGrowthRate += 0.1;
    c.farFieldBidirectional = !c.farFieldBidirectional;
    c.farFieldGrowthRateOuter += 0.1;
    c.gmshAlgorithm = 1;
    c.gmshOptimize = 0;
    c.gmshNumThreads = 4;
    c.seedSize = 0.5;
    c.seedRadius = 5.0;
    c.seedMode = 1;
    c.blMergeConcave = !c.blMergeConcave;
    c.blSmoothingIters += 3;
    Config::SeedSpec s; s.file = "seed.dat"; c.seedFiles.push_back(s);
    // Every declared BL parameter nudged off its default. The narrowing is the
    // declaration's own, so a bool becomes 1 and an int/double gains 1.
    forEachBLParam(c.bl, [](const char*, auto& v) {
        using T = std::decay_t<decltype(v)>;
        if constexpr (std::is_same_v<T, bool>) v = !v;
        else v = static_cast<T>(v + 1);
    });
    return c;
}

}  // namespace

int main() {
    // ── 1. the hybrid path reads everything it parses ───────────────────────
    {
        Config c = allInertSet();
        c.meshMode = MESH_MODE_HYBRID;
        CHECK(hybmesh::inertParamsSet(c).empty(),
              "the DEFAULT mode must never warn: it reads every key it parses, and "
              "a warning on the existing path would be a behaviour change on a "
              "ticket whose whole first claim is that nothing changed");
    }

    // ── 2. "set" means "differs from the default", in both directions ───────
    {
        Config pristine;
        pristine.meshMode = MESH_MODE_MULTIBLOCK;
        CHECK(hybmesh::inertParamsSet(pristine).empty(),
              "a config that sets nothing must warn about nothing — otherwise every "
              "GUI-written .dat (which emits nearly every key on every save) would "
              "warn about all of them at once and mean nothing");

        Config same = pristine;
        const Config def;
        same.farFieldGrowthRate = def.farFieldGrowthRate;   // written, equal to default
        same.gmshAlgorithm = def.gmshAlgorithm;
        CHECK(hybmesh::inertParamsSet(same).empty(),
              "a value equal to the default is not 'set'");

        Config one = pristine;
        one.farFieldGrowthRate = def.farFieldGrowthRate + 0.25;
        const auto w = hybmesh::inertParamsSet(one);
        CHECK(w.size() == 1 && has(w, "FARFIELD_GROWTH_RATE"),
              "one changed inert parameter names exactly that one parameter");
    }

    // ── 3. every declared inert global is named ─────────────────────────────
    {
        const auto w = hybmesh::inertParamsSet(allInertSet());
#define HYBMESH_MB_CHECK_NAMED(key, member) \
        CHECK(has(w, key), std::string("inert global not named: ") + key);
        HYBMESH_MULTIBLOCK_INERT_GLOBALS(HYBMESH_MB_CHECK_NAMED)
#undef HYBMESH_MB_CHECK_NAMED
        CHECK(has(w, "SEED_FILE"),
              "a declared refinement seed is inert here too (it only ever drove the "
              "far-field size field, and this path has no far field)");
        // The four the acceptance criteria enumerate, asked by name rather than
        // via the macro, so a row silently deleted from the macro cannot make
        // check 3 pass by having nothing to iterate.
        CHECK(has(w, "DOMAIN_X_MIN") && has(w, "DOMAIN_X_MAX")
              && has(w, "DOMAIN_Y_MIN") && has(w, "DOMAIN_Y_MAX"),
              "the four domain-extent settings are named");
        CHECK(has(w, "GMSH_ALGORITHM") && has(w, "GMSH_OPTIMIZE"),
              "the Gmsh algorithm and optimize settings are named");
    }

    // ── 4. the BL split is 4 surviving / 18 warned, and DERIVED ─────────────
    {
        const auto declared = declaredBLKeys();
        const auto surviving = survivingBLKeys();
        CHECK(declared.size() == 22,
              "22 boundary-layer parameters are declared (the count the split below "
              "is stated against)");
        CHECK(surviving.size() == 4, "four of them survive into the multi-block path");
        for (const auto& k : surviving)
            CHECK(declared.count(k) == 1,
                  "a surviving key must be one of the declared parameters, or the "
                  "subtraction silently exempts nothing: " + k);

        const auto w = hybmesh::inertParamsSet(allInertSet());
        int warned = 0;
        for (const auto& k : declared) {
            const bool survives = surviving.count(k) == 1;
            CHECK(has(w, k) == !survives,
                  std::string(survives ? "surviving BL parameter must NOT warn: "
                                       : "non-surviving BL parameter must warn: ") + k);
            if (!survives) ++warned;
        }
        CHECK(warned == 18,
              "18 boundary-layer parameters do not survive into this mode");
        CHECK(hybmesh::blParamSurvives(MESH_MODE_MULTIBLOCK, "BL_INITIAL_THICKNESS")
              && hybmesh::blParamSurvives(MESH_MODE_MULTIBLOCK, "BL_GROWTH_RATE")
              && hybmesh::blParamSurvives(MESH_MODE_MULTIBLOCK, "BL_LAYERS")
              && hybmesh::blParamSurvives(MESH_MODE_MULTIBLOCK, "BL_USE_ANALYTIC_GEOM"),
              "the wall first-cell thickness, growth rate, layer count and the "
              "analytic-geometry flag survive");
        CHECK(hybmesh::blParamSurvives(MESH_MODE_HYBRID, "BL_FAN_NODES"),
              "...and the survival question is per MODE: in the hybrid path every "
              "parameter survives");
    }

    // ── 5. the mode itself ─────────────────────────────────────────────────
    {
        Config c;
        CHECK(c.meshMode == MESH_MODE_HYBRID,
              "the DEFAULT is the existing path, which is what makes this whole "
              "feature's correct effect on an existing case zero");
        CHECK(hybmesh::isKnownMeshMode(MESH_MODE_HYBRID)
              && hybmesh::isKnownMeshMode(MESH_MODE_MULTIBLOCK),
              "both modes are known");
        CHECK(!hybmesh::isKnownMeshMode(2) && !hybmesh::isKnownMeshMode(-1),
              "an unknown mode is not silently accepted — Config::validate refuses "
              "it rather than clamping to 0, which would mesh the hybrid path for "
              "someone who asked for something else");
        Config bad; bad.meshMode = 2;
        CHECK(!bad.validate(), "validate() refuses an unknown MESH_MODE");
        Config good; good.meshMode = MESH_MODE_MULTIBLOCK;
        CHECK(good.validate(), "...and accepts a known one");
    }

    // ── 6. the two new exit codes have stable tokens ────────────────────────
    {
        CHECK(EXIT_ERR_TOPOLOGY == 8 && EXIT_ERR_INVERTED == 9,
              "the two new codes are 8 and 9, distinct from every existing one");
        CHECK(std::string(exitCodeToken(EXIT_ERR_TOPOLOGY)) == "TOPOLOGY",
              "an invalid topology declaration has the stable token TOPOLOGY");
        CHECK(std::string(exitCodeToken(EXIT_ERR_INVERTED)) == "INVERTED",
              "a mesh with inverted cells has the stable token INVERTED");
        // A token is machine-readable only while it is UNIQUE: two codes sharing
        // one token would make a caller branch on the wrong remedy.
        const int codes[] = {EXIT_ERR_CONFIG, EXIT_ERR_GEOMETRY_LOAD,
                             EXIT_ERR_INTERSECTION, EXIT_ERR_BL, EXIT_ERR_GMSH,
                             EXIT_ERR_EXPORT, EXIT_ERR_TOPOLOGY, EXIT_ERR_INVERTED};
        std::set<std::string> tokens;
        for (int c : codes) tokens.insert(exitCodeToken(c));
        CHECK(tokens.size() == sizeof(codes) / sizeof(codes[0]),
              "every exit code's token is distinct");
        CHECK(tokens.count("UNKNOWN") == 0,
              "...and none of them falls through to UNKNOWN, which is what a code "
              "added to the enum and forgotten in the switch would look like");
    }

    // ── 6b. SURVIVING is not the same as READ ───────────────────────────────
    // The four survivors are declared to belong to the multi-block path and are
    // not read by it yet, so they are reported by a SECOND list rather than
    // silently doing nothing. The two lists must stay disjoint: a key on both
    // would be described to the user twice, in contradictory terms.
    {
        Config c;
        c.meshMode = MESH_MODE_MULTIBLOCK;
        CHECK(hybmesh::blSurvivorsUnread(c).empty(),
              "an untouched config reports no unread survivor: this list is about "
              "what the USER set, exactly like the inert one");

        c.bl.blInitialThickness = 2.5e-6;
        c.bl.blLayers = 17;
        c.gmshAlgorithm = 5;                       // inert, and must not leak in
        const std::vector<std::string> unread = hybmesh::blSurvivorsUnread(c);
        const std::set<std::string> got(unread.begin(), unread.end());
        CHECK(got == std::set<std::string>({"BL_INITIAL_THICKNESS", "BL_LAYERS"}),
              "exactly the survivors the user SET are reported — not the two left "
              "at their defaults, and not the inert key set beside them");

        const std::vector<std::string> inert = hybmesh::inertParamsSet(c);
        const std::set<std::string> inertSet(inert.begin(), inert.end());
        std::set<std::string> both;
        for (const std::string& k : got) if (inertSet.count(k)) both.insert(k);
        CHECK(both.empty(),
              "no key is on BOTH lists: 'never read here' and 'not read yet' are "
              "different claims and a key can only be one of them");
        CHECK(inertSet.count("GMSH_ALGORITHM") == 1,
              "...and the inert list is still doing its own job, so the check above "
              "cannot pass by both lists being empty");

        Config h;
        h.bl.blInitialThickness = 2.5e-6;
        CHECK(hybmesh::blSurvivorsUnread(h).empty(),
              "the hybrid path reports nothing: it reads every one of them");
    }

    // ── 7. the topology file is declared, never derived from a name ─────────
    {
        Config c;
        CHECK(c.topologyFile.empty(),
              "no topology file is assumed: it is chosen by declaration, so a case "
              "with none named must not pick one up from a geometry's directory");
    }

    return hybmesh::test::report("test_mesh_mode");
}
