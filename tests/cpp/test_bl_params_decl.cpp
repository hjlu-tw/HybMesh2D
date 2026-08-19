// The boundary-layer parameters are declared ONCE (include/BLParams.hpp) and every
// traversal of them is generated from that declaration. This test pins the
// properties that "generated" is supposed to buy, because most of them are not
// visible in a build that merely compiles:
//
//   1. the list has the expected size, so growing it is a deliberate act
//   2. no two rows share a KEY, and no two rows share a FIELD (the copy-paste
//      where a new row keeps the previous row's field name still compiles, and
//      silently makes one parameter unsettable)
//   3. every declared KEY round-trips through a .dat write -> read, into its OWN
//      field — which is what "a missing parse branch cannot happen" means
//   4. every declared KEY reaches the per-geometry override parser too, and the
//      two parsers agree on the value they produce. They used not to:
//      BL_AUTO_FAN_NODES was narrowed to an int by one and to a bool by the other,
//      so a global `BL_AUTO_FAN_NODES 2` ran as 1 while the same token on a
//      GEOM_FILE line ran as 2. Check 5 pins that specific case as a regression.
//   6. Config::print() reads every declared parameter. The banner is hand-written
//      on purpose (it is a grouped report, reused verbatim as the provenance
//      sidecar, not a dump), so this is the check that stops a new parameter from
//      going unrecorded — writing it found that BL_FRONT_SMOOTHING_ITERS was
//      never printed at all.
//
// It links hybmesh_pure and NOTHING else: Config.hpp is a header-only .dat parser
// with no mesh and no gmsh in it, and this executable failing to link would be the
// signal that stopped being true.
#include "Config.hpp"
#include "check.hpp"

#include <cstdio>
#include <fstream>
#include <set>
#include <sstream>
#include <string>
#include <vector>

using namespace hybmesh::test;

namespace {

// The KEYs, in declaration order. Collected through the same visitor the
// production parsers use, so the test cannot read a different list.
std::vector<std::string> keys() {
    BLParams p;
    std::vector<std::string> k;
    forEachBLParam(p, [&](const char* key, auto&) { k.emplace_back(key); });
    return k;
}

// One distinct value per parameter, keyed by position. Distinctness is the point:
// a parser that writes key i's value into field j is only visible if no two
// expected values are equal. `bool` can hold only 0 or 1, so a bool row is
// verified by flipping it away from its default instead.
double probeValue(std::size_t i) { return 3.0 + 2.0 * static_cast<double>(i); }

// Snapshot every field as a double, in declaration order.
std::vector<double> snapshot(const BLParams& p) {
    std::vector<double> v;
    forEachBLParam(p, [&](const char*, const auto& f) {
        v.push_back(static_cast<double>(f));
    });
    return v;
}

std::string printed(const Config& c) {
    std::ostringstream os;
    c.print(os);
    return os.str();
}

}  // namespace

int main() {
    const std::vector<std::string> K = keys();

    // --- 1. the declaration's size is pinned --------------------------------
    CHECK(blParamCount() == 22,
          "blParamCount() is derived from the declaration; update this number "
          "deliberately when a parameter is added");
    CHECK(static_cast<int>(K.size()) == blParamCount(),
          "forEachBLParam must visit exactly blParamCount() parameters");

    // --- 2. no duplicate KEY, no duplicate FIELD ----------------------------
    CHECK(std::set<std::string>(K.begin(), K.end()).size() == K.size(),
          "two rows of the declaration share a .dat KEY");
    {
        BLParams p;
        std::set<const void*> addrs;
        forEachBLParam(p, [&](const char*, auto& f) { addrs.insert(&f); });
        CHECK(addrs.size() == K.size(),
              "two rows of the declaration name the SAME field, so one of those "
              "parameters can never be set");
    }

    // --- 3. every KEY round-trips through a .dat, into its own field ---------
    {
        BLParams want;
        {
            std::size_t i = 0;
            forEachBLParam(want, [&](const char*, auto& f) {
                using T = std::decay_t<decltype(f)>;
                // A bool cannot carry a distinct probe value; flip it instead, so
                // "the field was written" is still observable.
                f = std::is_same_v<T, bool> ? static_cast<T>(1)
                                            : static_cast<T>(probeValue(i));
                ++i;
            });
        }

        const std::string path = "test_bl_params_decl.tmp.dat";
        {
            std::ofstream ofs(path);
            std::size_t i = 0;
            forEachBLParam(want, [&](const char* key, const auto& f) {
                ofs << key << " " << static_cast<double>(f) << "\n";
                ++i;
            });
        }

        Config got;
        CHECK(got.loadFromFile(path), "the probe .dat must be readable");
        std::remove(path.c_str());

        const std::vector<double> w = snapshot(want), g = snapshot(got.bl);
        for (std::size_t i = 0; i < K.size(); ++i) {
            CHECK_NEAR(g[i], w[i], 1e-12,
                       "BL parameter " + K[i] + " did not survive a .dat "
                       "write -> read into its own field");
        }
        // Not vacuous: the probe values must actually differ from the defaults,
        // or a parser that ignored the file entirely would pass the loop above.
        const std::vector<double> d = snapshot(BLParams{});
        std::size_t same = 0;
        for (std::size_t i = 0; i < K.size(); ++i)
            if (d[i] == w[i]) ++same;
        CHECK(same == 0, "every probe value must differ from its default, or the "
                         "round-trip check proves nothing");
    }

    // --- 4. the per-geometry override parser reaches every KEY, and agrees ---
    for (std::size_t i = 0; i < K.size(); ++i) {
        const double v = probeValue(i);
        BLParams viaToken;
        CHECK(applyBLParam(viaToken, K[i], v),
              "applyBLParam must claim the declared key " + K[i]);

        BLParams viaDat;
        std::istringstream ss(std::to_string(v));
        CHECK(readBLParam(viaDat, K[i], ss),
              "readBLParam must claim the declared key " + K[i]);

        const std::vector<double> a = snapshot(viaToken), b = snapshot(viaDat);
        for (std::size_t j = 0; j < K.size(); ++j) {
            CHECK_NEAR(a[j], b[j], 1e-12,
                       "the .dat reader and the override parser disagree about " +
                       K[i] + " (differing at " + K[j] + ")");
        }
        // ...and it touched only its own field.
        const std::vector<double> d = snapshot(BLParams{});
        std::size_t changed = 0;
        for (std::size_t j = 0; j < K.size(); ++j)
            if (a[j] != d[j]) ++changed;
        CHECK(changed == 1, "applying " + K[i] + " must change exactly one field");
    }

    // --- 5. an unknown key belongs to nobody --------------------------------
    {
        BLParams p;
        std::istringstream ss("1");
        CHECK(!applyBLParam(p, "BL_NOT_A_PARAMETER", 1.0),
              "applyBLParam must not claim an undeclared key");
        CHECK(!readBLParam(p, "BL_NOT_A_PARAMETER", ss),
              "readBLParam must not claim an undeclared key");
        CHECK(snapshot(p) == snapshot(BLParams{}),
              "an undeclared key must leave every field alone");
    }

    // --- 5b. regression: BL_AUTO_FAN_NODES is an int on BOTH paths -----------
    // 0 OFF / 1 Global Avg / 2 Local Avg, and BoundaryLayer.cpp really branches on
    // 2. The .dat parser used to collapse it with `(val != 0)`, so this read back
    // as 1 and Local Avg was reachable only through a GEOM_FILE override token.
    {
        const std::string path = "test_bl_afn.tmp.dat";
        { std::ofstream ofs(path); ofs << "BL_AUTO_FAN_NODES 2\n"; }
        Config c;
        CHECK(c.loadFromFile(path), "the probe .dat must be readable");
        std::remove(path.c_str());
        CHECK(c.bl.blAutoFanNodes == 2,
              "BL_AUTO_FAN_NODES 2 must mean Local Avg, not 1");
        BLParams viaToken;
        Config::applyBLKey(viaToken, "BL_AUTO_FAN_NODES", 2.0);
        CHECK(viaToken.blAutoFanNodes == 2,
              "the override token path must agree with the .dat path");
    }

    // --- 6. print() reads every declared parameter --------------------------
    // Not a substring search for the KEY (the banner prints prose labels, not
    // keys) but a differential: for each parameter there must exist a value whose
    // banner differs from the baseline's. That is exactly "the printer reads this
    // field", and it survives any reformatting of the banner.
    //
    // Several lines are conditional on a method (fan nodes only under convex
    // method 0, fallback angle only under 2, influence multiplier only under
    // concave method 5), so the sweep runs under two bases and a parameter needs
    // to be visible under either.
    {
        std::vector<Config> bases(2);
        bases[1].bl.blConvexMethod = 2;
        bases[1].bl.blConcaveMethod = 5;

        const double CANDIDATES[] = {0.0, 1.0, 2.0, 5.0, 7.0, 123.5};
        for (std::size_t i = 0; i < K.size(); ++i) {
            bool visible = false;
            for (const Config& base : bases) {
                const std::string ref = printed(base);
                const std::vector<double> d = snapshot(base.bl);
                for (double cand : CANDIDATES) {
                    if (cand == d[i]) continue;   // not a change at all
                    Config c = base;
                    applyBLParam(c.bl, K[i], cand);
                    if (snapshot(c.bl)[i] == d[i]) continue;  // narrowed back
                    if (printed(c) != ref) { visible = true; break; }
                }
                if (visible) break;
            }
            CHECK(visible, "Config::print() never reads " + K[i] +
                           ", so a mesh's banner and provenance sidecar cannot "
                           "account for it");
        }
    }

    return report("test_bl_params_decl");
}
