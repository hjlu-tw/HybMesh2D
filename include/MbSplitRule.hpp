#ifndef MB_SPLIT_RULE_HPP
#define MB_SPLIT_RULE_HPP

#include <cstdint>
#include <string>

// HOW each quad of a multi-block fill is cut into two triangles: a CLOSED SET,
// in one place, with its declared numbers and names beside it.
//
// Its OWN header, and small on purpose. Two very different files need these four
// numbers — `MultiBlock.hpp`, which is the pure seam that acts on them, and
// `Config.hpp`, which is a header-only `.dat` parser that must REFUSE an unknown
// one — and `Config.hpp` is included by `Mesh.hpp` and `BoundaryLayer.hpp` in
// turn. Including the whole seam header there to reach an enum would drag
// `MbResult`, `MbBlock` and `GeomUtils.hpp` into every one of those translation
// units, and it would invert the coupling `MultiBlock.hpp` states as a rule (its
// parameters are a handful of values rather than a `Config&`, precisely so the
// decision layer does not know the file format). `MeshMode.hpp` is the same
// shape for the same reason and is the precedent this follows.
//
// The numbers are the `.dat` file's (`MB_SPLIT_RULE`) and the GUI's combo offers
// exactly these four. ALTERNATING is 0 because it is the default and shipped
// first: a case written before this key existed, which names no rule at all, must
// produce the mesh it produced before.
//
// Why four and not two: a single fixed diagonal imprints its own direction on a
// uniform structured region, which is why it is not the default — but it is the
// right answer when a region's flow direction is known, and BOTH directions have
// to be reachable or "fixed" means "whichever one we happened to hard-code".
namespace hybmesh {

enum MbSplitRule {
    // Flip with (i + j) parity. The default: no seed, no bias, deterministic.
    MB_SPLIT_ALTERNATING = 0,
    // Always the (i,j)-(i+1,j+1) diagonal.
    MB_SPLIT_FORWARD     = 1,
    // Always the (i+1,j)-(i,j+1) diagonal.
    MB_SPLIT_BACKWARD    = 2,
    // Chosen by a HASH of the cell's own identity — block id, i, j and the seed.
    // Hash-based rather than drawn from a sequential generator, and that is the
    // one property of this rule that is not negotiable: a sequential stream makes
    // every cell's diagonal a function of traversal order, so adding one block
    // anywhere in the topology would reshuffle the diagonals of the entire mesh.
    // "I moved one corner and the whole mesh changed" would become the normal
    // experience, and the regression comparator — which compares exported
    // connectivity, exactly what a diagonal decides — would have nothing left to
    // compare. Pinned by check 26 in tests/cpp/test_multiblock.cpp.
    MB_SPLIT_RANDOM      = 3,
};

// An unknown rule gets "unknown", never the default's name. Every caller today
// runs after the value has been range-checked, so it is unreachable — but this is
// the one function here that could answer an unknown rule with a PLAUSIBLE name,
// which is the opposite of the refuse-never-clamp convention `isKnownMbSplitRule`
// states below, and a name in a banner is what a reader trusts.
inline const char* mbSplitRuleName(int r) {
    switch (r) {
        case MB_SPLIT_ALTERNATING: return "alternating by index parity";
        case MB_SPLIT_FORWARD:     return "fixed forward diagonal";
        case MB_SPLIT_BACKWARD:    return "fixed backward diagonal";
        case MB_SPLIT_RANDOM:      return "randomized, hashed from block, i, j and seed";
    }
    return "unknown";
}

// Is this a rule the tool has? An unknown value is REFUSED — by
// `Config::validate()` on the `.dat` path and by `buildMultiBlock` itself for any
// other caller — and never clamped to the default, for the reason MESH_MODE
// records: silently meshing with a rule nobody asked for has no symptom.
inline bool isKnownMbSplitRule(int r) {
    return r >= MB_SPLIT_ALTERNATING && r <= MB_SPLIT_RANDOM;
}

// Does this rule read `MB_SPLIT_SEED`? Asked at four sites — the two refusal-time
// and banner-time decisions to print the seed, the seam's inert-seed warning, and
// the split itself — and written once here, because four hand-written
// `== MB_SPLIT_RANDOM` comparisons are four chances for one of them to keep
// answering the old way when a second seeded rule arrives.
inline bool mbSplitRuleReadsSeed(int r) { return r == MB_SPLIT_RANDOM; }

// The four rules as one "N = name" list, for a refusal message. Both refusals
// (Config::validate and buildMultiBlock) print this: they are deliberately two
// doors with two exit codes, but they are not two hand-maintained texts, and a
// fifth rule must not be able to appear in one message and not the other.
inline std::string mbSplitRuleList() {
    std::string out;
    for (int r = MB_SPLIT_ALTERNATING; r <= MB_SPLIT_RANDOM; ++r) {
        if (!out.empty()) out += ", ";
        out += std::to_string(r) + " = " + mbSplitRuleName(r);
    }
    return out;
}

}  // namespace hybmesh

#endif  // MB_SPLIT_RULE_HPP
