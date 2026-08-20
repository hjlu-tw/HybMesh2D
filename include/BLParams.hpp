#ifndef BL_PARAMS_HPP
#define BL_PARAMS_HPP

#include <istream>
#include <string>

// ONE declaration of the boundary-layer parameters. Each row carries the four
// facts that used to be spread across four independent traversals of the same
// names: the .dat KEY, the C++ type, the field name and the default.
//
//   X(KEY, type, field, default)
//
// Everything that walks the parameters is GENERATED from this list — the struct
// below, the .dat reader (readBLParam), the per-geometry override parser
// (applyBLParam) and the enumeration the tests and the printer use
// (forEachBLParam). Before this, `include/Config.hpp` traversed the same 22
// names five times: BLParams' fields, Config's own second copy of them WITH A
// SECOND SET OF DEFAULTS, loadConfig's `key == "BL_…"` chain, the override
// parser's chain, and a 22-line field-by-field bridge between the two structs. Adding a
// parameter meant remembering all of them, and forgetting the parse branch gave
// a parameter that silently kept its default — an outcome with no symptom
// except a mesh nobody asked for.
//
// Adding a parameter is now this list, plus a banner line in Config::print()
// (which stays hand-written on purpose: it is a grouped report reused verbatim
// by the provenance sidecar, not a dump — and tests/cpp/test_bl_params_decl.cpp
// fails the build if a declared KEY never reaches it).
//
// The order of the rows is the order of the fields, which is the order the
// banner and the .dat both read most naturally: base growth, fans, corners,
// junction, transition, then the two opt-in smoothers.
#define HYBMESH_BL_PARAMS(X)                                                     \
    X("BL_INITIAL_THICKNESS",           double, blInitialThickness,          0.01)\
    X("BL_GROWTH_RATE",                 double, blGrowthRate,                 1.2)\
    X("BL_LAYERS",                      int,    blLayers,                       5)\
    /* Fan elements at a convex corner. blAutoFanNodes: 0 OFF / 1 Global Avg  */  \
    /* / 2 Local Avg — an int with three meanings, and the parameter whose two */  \
    /* parsers disagreed about that (see applyBLParam below).                  */  \
    X("BL_FAN_NODES",                   int,    blFanNodes,                     5)\
    X("BL_AUTO_FAN_NODES",              int,    blAutoFanNodes,                 0)\
    X("BL_FAN_ANGLE_THRESHOLD",         double, blFanAngleThreshold,         60.0)\
    /* Convex handling: 0 Fan (default) / 2 Parallelogram.                    */  \
    X("BL_CONVEX_METHOD",               int,    blConvexMethod,                 0)\
    X("BL_PARA_FALLBACK_ANGLE",         double, blParaFallbackAngle,        300.0)\
    X("BL_CONVEX_ANGLE_THRESHOLD",      double, blConvexAngleThreshold,     260.0)\
    /* Concave handling: 0 Vector Merge (default) / 5 Thickness Blending.     */  \
    X("BL_CONCAVE_METHOD",              int,    blConcaveMethod,                0)\
    X("BL_CONCAVE_INFLUENCE_MULTIPLIER",double, blConcaveInfluenceMultiplier, 2.5)\
    X("BL_CONCAVE_ANGLE_THRESHOLD",     double, blConcaveAngleThreshold,    100.0)\
    /* BL / non-BL junction; see the block comment on BLParams below.         */  \
    X("BL_JUNCTION_METHOD",             int,    blJunctionMethod,               1)\
    X("BL_JUNCTION_ANGLE_C1",           double, blJunctionAngleC1,          135.0)\
    X("BL_JUNCTION_ANGLE_C2",           double, blJunctionAngleC2,          270.0)\
    X("BL_JUNCTION_ANGLE_C3",           double, blJunctionAngleC3,          315.0)\
    /* Transition layers. blAutoTransitionLayers: 0 OFF / 1 Global Avg        */  \
    /* / 2 Per-Geometry Avg.                                                  */  \
    X("BL_TRANSITION_LAYERS",           int,    blTransitionLayers,             3)\
    X("BL_AUTO_TRANSITION_LAYERS",      int,    blAutoTransitionLayers,         0)\
    X("BL_TRANSITION_GROWTH_RATE",      double, blTransitionGrowthRate,       1.2)\
    X("BL_TRANSITION_BUFFER",           double, blTransitionBuffer,           2.0)\
    X("BL_USE_ANALYTIC_GEOM",           bool,   blUseAnalyticGeom,          false)\
    X("BL_FRONT_SMOOTHING_ITERS",       int,    blFrontSmoothingIters,          0)

// Per-geometry boundary-layer parameters. A geometry that grows a BL uses either
// the global settings (Config::bl, handed over by Config::globalBLParams) or a
// copy with the overrides declared on its GEOM_FILE / DOMAIN_FILE line applied
// (Config::blParamsFor).
//
// Notes on individual parameters that the one-line comments above cannot hold:
//
// blConcaveInfluenceMultiplier — arc-length reach of the concave/blend
//   correction, in BL total heights. 10 over-blended: it tilted every column
//   along an edge toward the corner apex, so a segment's BL -> far-field edge
//   came out curved instead of a straight uniform-height band. 2.5 keeps the
//   outer edge straight with a short transition only at the corner (still enough
//   to avoid front self-intersection at typical concave corners).
//
// blJunctionMethod / C1..C3 — BL / non-BL junction handling (see
//   BoundaryLayer.cpp). Method 0 = taper-to-zero (collapsing prisms, legacy);
//   1 = 4-case angle-driven (default). The flow-facing included angle theta
//   (deg) between the BL edge and its non-BL neighbour bins as:
//     (0,95] slide along the neighbour edge | (95,C2] perpendicular cap
//     | (C2,C3] neighbour-extension cap    | (C3,360) perpendicular cap.
//   The 95 is geometric, not a preference: a cap must point INTO the fluid
//   wedge, which spans theta, while the perpendicular sits at 90 deg — so at
//   theta <= 90 a cap provably leaves the domain through the no-BL wall (+5 deg
//   of guard band against degenerate slivers). C1 is therefore NOT read by
//   method 1; it still bins method 0 and round-trips through the GUI/config.
//
// blUseAnalyticGeom — 在平滑表面點以解析曲線(line/circle/spline)的法向取代有限
//   差分。預設關閉，行為與舊版逐位元相同；開啟後角點仍維持既有 fan/merge 處理。
//
// blFrontSmoothingIters — per-layer tangential smoothing of the advancing front.
//   Redistributes PLAIN (non-corner/fan/junction/frozen) front nodes ALONG the
//   front — the growth-direction component is removed so layer height is
//   preserved — cancelling the finite-difference bisector drift that made smooth
//   arcs/circles go wavy or self-intersect in the outer layers at high growth
//   rate / many layers. Opt-in (0 = off): keeps existing meshes bit-identical;
//   raise it (e.g. 2) to damp residual drift on noisy/non-uniform inputs.
struct BLParams {
#define HYBMESH_BL_FIELD(key, type, field, def) type field = def;
    HYBMESH_BL_PARAMS(HYBMESH_BL_FIELD)
#undef HYBMESH_BL_FIELD
};

// Number of declared parameters. Derived from the list, so it cannot drift.
inline constexpr int blParamCount() {
    int n = 0;
#define HYBMESH_BL_COUNT(key, type, field, def) ++n;
    HYBMESH_BL_PARAMS(HYBMESH_BL_COUNT)
#undef HYBMESH_BL_COUNT
    return n;
}

// Visit every declared parameter as (KEY, reference-to-field). The callable is
// invoked with a `double&`, `int&` or `bool&` depending on the row, so it must be
// generic (a lambda taking `auto&`). This is the enumeration the tests walk, and
// it is what makes "the declaration covers every field" a property of the build
// rather than a claim: the fields ARE the list.
template <class F>
inline void forEachBLParam(BLParams& p, F&& f) {
#define HYBMESH_BL_VISIT(key, type, field, def) f(key, p.field);
    HYBMESH_BL_PARAMS(HYBMESH_BL_VISIT)
#undef HYBMESH_BL_VISIT
}

template <class F>
inline void forEachBLParam(const BLParams& p, F&& f) {
#define HYBMESH_BL_VISIT(key, type, field, def) f(key, p.field);
    HYBMESH_BL_PARAMS(HYBMESH_BL_VISIT)
#undef HYBMESH_BL_VISIT
}

// Apply a numeric value to the parameter named by `key`. Returns false when the
// key is not one of ours, so a caller can fall through to its other keys.
//
// The value is taken as a double and narrowed with static_cast, for every row:
// that is one rule rather than a per-field decision, and a per-field decision is
// how BL_AUTO_FAN_NODES came to be read as a bool by the .dat parser (silently
// running a requested 2 as 1) while the override parser read it as the int it is.
inline bool applyBLParam(BLParams& p, const std::string& key, double v) {
#define HYBMESH_BL_APPLY(k, type, field, def) \
    if (key == k) { p.field = static_cast<type>(v); return true; }
    HYBMESH_BL_PARAMS(HYBMESH_BL_APPLY)
#undef HYBMESH_BL_APPLY
    return false;
}

// True when `key` names a declared BL parameter. Generated from the list, so it
// cannot fall behind it — which matters because the caller uses it to REFUSE a
// per-geometry `KEY=VALUE` token it does not recognise, and a stale answer there
// would reject a real parameter.
inline bool isBLParam(const std::string& key) {
#define HYBMESH_BL_HAS(k, type, field, def) if (key == k) return true;
    HYBMESH_BL_PARAMS(HYBMESH_BL_HAS)
#undef HYBMESH_BL_HAS
    return false;
}

// Read the value for `key` off a .dat line's remaining stream. Returns false when
// the key is not one of ours. Same narrowing rule as applyBLParam, so the two
// parsers cannot disagree about a parameter's type — which they used to. A value
// that will not parse leaves 0 in the field, which is what the branches this
// replaces already did (`operator>>` zeroes its target on failure).
//
// One further behaviour change the single rule causes, small but real: a bool row is
// now read through a double, so `BL_USE_ANALYTIC_GEOM 0.5` is TRUE where the branch
// this replaces (`int val; ss >> val`) read 0 and got false. Measured on both trees.
// Integral values — every value any config in this repo or the GUI writes — are
// unaffected. Recorded rather than special-cased: reinstating a per-row parse rule to
// preserve it would put back the very thing that let the two parsers disagree.
inline bool readBLParam(BLParams& p, const std::string& key, std::istream& ss) {
#define HYBMESH_BL_READ(k, type, field, def)                          \
    if (key == k) { double v = 0.0; ss >> v; p.field = static_cast<type>(v); return true; }
    HYBMESH_BL_PARAMS(HYBMESH_BL_READ)
#undef HYBMESH_BL_READ
    return false;
}

#endif // BL_PARAMS_HPP
