// THE TWO-SIDED TANH's REDUCTION TO THE ONE-PARAMETER LAW (#177).
//
// WHY THIS FILE EXISTS AND IS NOT PART OF `test_multiblock.cpp`. #177's own
// Implementation decision asks for one thing this repo could not reach from
// there:
//
//   "The one-parameter solvers STAY. `solveTanhStartDelta` is what `wall_ends`
//    resolves to and is exercised by every shipped case; a two-parameter solver
//    ASKED FOR A SYMMETRIC PAIR must reproduce it, and that equality is the gate
//    rather than a claim."
//
// `spacingAlong` sends an EQUAL pair to `solveTanhDelta` and a SINGLE clustered
// end to `solveTanhStartDelta` — which is what keeps every shipped document's
// nodes where they were, and also means the two-sided solver is NEVER CALLED at
// a symmetric pair. So no document, and no check driven through
// `buildMultiBlock`, can ask it the question the decision asks about. A review
// axis read `test_multiblock.cpp` 60(b) — which measures one ulp AWAY from the
// symmetric point, through the real dispatch — and said, correctly, that it is
// the shipped BEHAVIOUR's gate and not that decision's. Both are wanted; 60(b)
// stays and this file is the other one.
//
// IT LINKS NOTHING. `tools/PreProcessor/include/Spacing.hpp` is header-only pure
// arithmetic, so this executable has no library at all, not even `hybmesh_pure`
// — which is the same signal the pure tests carry one level stronger: if the
// spacing laws ever need a mesh, a topology or gmsh, this file stops building.
// Its include path is granted EXPLICITLY in `tests/cpp/CMakeLists.txt` rather
// than inherited; `hybmesh_pure` keeps that directory PRIVATE, and asking for it
// by name is not the same thing as a test picking it up by accident.
//
// THE INJECTIONS ARE HAND RUNS, and they are #177's, recorded once beside check
// 60 in `tests/cpp/test_multiblock.cpp`. I1 (the Mobius map dropped) and I2
// (`tanhTwoSidedA` losing its `- 1.0`) both redden this file as well.
//
// IT HAS ALREADY EARNED ITS KEEP ONCE: check 4 was written to confirm a claim
// #177 had made three times in prose and reddened it instead. See that check.
#include "Spacing.hpp"
#include "check.hpp"

#include <cmath>
#include <string>
#include <vector>

using HybMesh::Spacing;

namespace {

std::string f(double v) {
    char buf[64];
    std::snprintf(buf, sizeof(buf), "%.17g", v);
    return buf;
}

}  // namespace

int main() {
    // ── 1. AT A == 1 THE FAMILY IS THE SYMMETRIC LAW, BIT FOR BIT ──────────
    //
    // The structural half, and it is an EQUALITY rather than a tolerance:
    // `A + (1 - A) * u` is exactly 1.0 when A is exactly 1.0, so the expression
    // collapses to `L * u`, and `L * (0.5 * x)` and `(L * 0.5) * x` round the
    // same way because halving is exact. Asserted over four edge lengths and
    // four counts, because "exact" that holds only on a unit edge is the shape
    // check 3 below had to be weakened for.
    {
        int pairs = 0;
        for (double L : {0.125, 1.0, 9.5, 1000.0}) {
            for (int n : {3, 5, 41, 97}) {
                for (double dlt : {0.5, 2.0, 4.295, 12.0}) {
                    for (int i = 0; i < n; ++i) {
                        const double a = Spacing::tanhTwoSidedPos(L, n, dlt, 1.0, i);
                        const double b = Spacing::tanhBothPos(L, n, dlt, i);
                        CHECK(a == b,
                              "1. tanhTwoSidedPos(A=1) IS tanhBothPos at L="
                              + f(L) + " n=" + std::to_string(n) + " dlt=" + f(dlt)
                              + " i=" + std::to_string(i) + ": " + f(a) + " vs " + f(b));
                        ++pairs;
                    }
                }
            }
        }
        CHECK(pairs == 4 * (3 + 5 + 41 + 97) * 4,
              "1. ...over every (L, n, dlt, i) the loop claims ("
              + std::to_string(pairs) + ")");
    }

    // ── 2. ASKED FOR A SYMMETRIC PAIR, THE TWO-PARAMETER SOLVER REPRODUCES
    //       THE ONE-PARAMETER ONE ───────────────────────────────────────────
    //
    // #177's Implementation decision, as a measurement. NOT bit for bit, and
    // the reason is in the two solvers rather than in the law: `solveTanhDelta`
    // bisects on `dlt` directly while `solveTanhTwoSided` bisects on it with
    // `A` closed-form beside it, so each converges to its own last bit. The
    // bound is DERIVED the way check 31's is — a station is `L` times a
    // normalized position, so its rounding is eps of the EDGE, and `A` carries
    // about `eps * L / ds` because `u(xi_1)` is a difference of two nearly
    // equal tanh values. Measured worst below, printed so a regression names a
    // number instead of a verdict.
    {
        double worstA = 0.0, worstNode = 0.0, worstRel = 0.0;
        for (double L : {0.125, 1.0, 9.5, 1000.0}) {
            for (int n : {5, 21, 41, 97}) {
                for (double frac : {1e-1, 1e-2, 1e-4}) {
                    const double ds = L * frac;
                    double dlt = 0.0, A = 1.0;
                    Spacing::solveTanhTwoSided(L, n, ds, ds, dlt, A);
                    const std::vector<double> two =
                        Spacing::generateTanhTwoSided(L, n, dlt, A);
                    const std::vector<double> one =
                        Spacing::generateTanh(L, n, Spacing::solveTanhDelta(L, n, ds));
                    CHECK(two.size() == one.size() && (int)two.size() == n,
                          "2. both laws give n stations at L=" + f(L)
                          + " n=" + std::to_string(n));
                    worstA = std::max(worstA, std::fabs(A - 1.0));
                    // The DERIVED bar: eps of the edge, over the cell's
                    // relative size, with a factor of 64 so a different libm's
                    // tanh cannot flake it.
                    const double bar = 64.0 * 2.221e-16 * L / frac;
                    for (size_t k = 0; k < two.size() && k < one.size(); ++k) {
                        const double d = std::fabs(two[k] - one[k]);
                        worstNode = std::max(worstNode, d);
                        worstRel = std::max(worstRel, d / L);
                        CHECK(d <= bar,
                              "2. a symmetric pair reproduces generateTanh at L=" + f(L)
                              + " n=" + std::to_string(n) + " ds/L=" + f(frac)
                              + " station " + std::to_string(k) + ": gap " + f(d)
                              + " against a derived " + f(bar));
                    }
                }
            }
        }
        std::printf("    [2] worst |A - 1| %.3e, worst station gap %.3e absolute "
                    "/ %.3e of the edge\n", worstA, worstNode, worstRel);
        // A IS the asymmetry, so a symmetric request must put it at 1. Asserted
        // on its own as well: a solver that reached the right stations with a
        // wrong A and a compensating dlt would pass the loop above.
        CHECK(worstA <= 1e-9,
              "2. ...with A at 1, which is what 'symmetric' MEANS in this family "
              "(worst |A - 1| " + f(worstA) + ")");
    }

    // ── 3. THE DEGENERATE END: dlt 0, A 1 IS THE UNIFORM LAW ───────────────
    //
    // WEAKER THAN CHECK 1, AND MEASURED RATHER THAN ASSUMED. At `dlt == 0` the
    // family's `u` is `(double)i / (nT - 1)` and the station is `L * u`, while
    // `generateGeometric` at ratio 1 writes `L * i / (nT - 1)` — the same value
    // associated differently, so the two agree exactly only where multiplying
    // by L is exact. They DO on a unit edge, which is every fixture
    // `test_multiblock.cpp` 60(e) has; a review measured tens of thousands of
    // one-ulp mismatches across other lengths. So the bit claim is made where
    // it is true and the rest is a one-ulp bound, rather than an equality that
    // is one scale change from red.
    {
        int bitExact = 0, within = 0, total = 0;
        for (double L : {0.125, 1.0, 9.5, 1000.0}) {
            for (int n : {3, 21, 97}) {
                const std::vector<double> two = Spacing::generateTanhTwoSided(L, n, 0.0, 1.0);
                const std::vector<double> uni = Spacing::generateGeometric(L, n, 1.0);
                CHECK(two.size() == uni.size(), "3. same station count at L=" + f(L));
                for (size_t k = 0; k < two.size() && k < uni.size(); ++k) {
                    ++total;
                    if (two[k] == uni[k]) ++bitExact;
                    if (std::fabs(two[k] - uni[k]) <= 4.0 * 2.221e-16 * L) ++within;
                }
            }
        }
        CHECK(within == total,
              "3. dlt 0 with A 1 IS the uniform law, to one rounding of the "
              "normalisation (" + std::to_string(within) + " of "
              + std::to_string(total) + ")");
        std::printf("    [3] %d of %d stations are bit-exact; the rest differ by "
                    "one ulp of L * i / (n - 1)\n", bitExact, total);
        // The unit edge is where it IS exact, and that is the fixture the
        // multi-block gate's own bit assertion runs on. Pinned here so that
        // claim has a home that says WHY it holds.
        {
            const std::vector<double> two = Spacing::generateTanhTwoSided(1.0, 21, 0.0, 1.0);
            const std::vector<double> uni = Spacing::generateGeometric(1.0, 21, 1.0);
            bool same = two.size() == uni.size();
            for (size_t k = 0; same && k < two.size(); ++k) same = two[k] == uni[k];
            CHECK(same, "3. ...and on a UNIT edge it is bit for bit, which is the "
                        "scale test_multiblock.cpp 60(e) asserts that on");
        }
    }

    // ── 4. THE ONE-SIDED LAW IS A MEMBER OF THIS FAMILY TOO ────────────────
    //
    // THIS CHECK WAS WRITTEN TO ASSERT THE OPPOSITE AND WENT RED, which is the
    // most useful thing it has done. #177 said in three places that a single
    // clustered end "is not expressible in this family at all" — reasoning from
    // Pointwise's `Tanh` falling back to "a *different*, one-sided function ...
    // if the spacing is unconstrained at only one end". That is an API fact
    // about an UNDECLARED end, and it was read as a statement about the
    // mathematics: the SAME error as the refusal this ticket removes, made
    // inside the ticket that removes it.
    //
    // Measured: handed the one-sided law's own two end intervals — with the
    // FINER one leading, which is the contract `spacingAlong` honours and which
    // the first version of this loop got wrong — the two-sided solver
    // reproduces its whole distribution to 7.7e-13 of the edge over 64
    // combinations of length, count and cell size.
    //
    // WHAT THE DISPATCH IS ACTUALLY FOR, then, is DETERMINACY and not
    // capability: one declared height is ONE equation and this family has TWO
    // parameters, so with the far end undeclared there is nothing to solve `A`
    // from. `solveTanhStartDelta` picks a member rather than offering a rival.
    {
        double worstRel = 0.0;
        int cases = 0;
        for (double L : {0.125, 1.0, 9.5, 1000.0}) {
            for (int n : {5, 11, 41, 97}) {
                for (double frac : {1e-1, 1e-2, 1e-4, 1e-6}) {
                    const double ds = L * frac;
                    const std::vector<double> one = Spacing::generateTanhStart(
                        L, n, Spacing::solveTanhStartDelta(L, n, ds));
                    if ((int)one.size() != n) continue;
                    const double trail = one[n - 1] - one[n - 2];
                    // THE CALLER's OWN CONTRACT: the finer height leads, and the
                    // result is mirrored when it was declared trailing. Calling
                    // the solver against that contract is what made the first
                    // run of this loop report half an edge of disagreement on
                    // the rows where the one-sided law had degenerated to
                    // uniform — a harness defect read as a counter-example.
                    const bool leads = ds <= trail;
                    double dlt = 0.0, A = 1.0;
                    Spacing::solveTanhTwoSided(L, n, leads ? ds : trail,
                                               leads ? trail : ds, dlt, A);
                    std::vector<double> two = Spacing::generateTanhTwoSided(L, n, dlt, A);
                    if (!leads) {
                        std::vector<double> m(two.size());
                        for (size_t x = 0; x < two.size(); ++x)
                            m[x] = L - two[two.size() - 1 - x];
                        two = m;
                    }
                    double w = 0.0;
                    for (int k = 0; k < n && k < (int)two.size(); ++k)
                        w = std::max(w, std::fabs(two[k] - one[k]));
                    worstRel = std::max(worstRel, w / L);
                    ++cases;
                    CHECK(w <= 1e-11 * L,
                          "4. the two-sided law reproduces the ONE-SIDED law at L=" + f(L)
                          + " n=" + std::to_string(n) + " ds/L=" + f(frac)
                          + ": worst " + f(w / L) + " of the edge");
                }
            }
        }
        std::printf("    [4] the one-sided law is a MEMBER: worst %.3e of the edge "
                    "over %d combinations\n", worstRel, cases);
        CHECK(cases == 64, "4. ...over all 64 combinations (" + std::to_string(cases) + ")");
    }

    return hybmesh::test::report("test_spacing_two_sided");
}
