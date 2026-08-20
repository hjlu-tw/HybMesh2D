#ifndef HYBMESH_JUNCTION_SCHEME_HPP
#define HYBMESH_JUNCTION_SCHEME_HPP

#include "GeomUtils.hpp"
#include <vector>

// The BL/no-BL junction binning, as a function of DATA.
//
// This is the decision layer's first member: it knows no `Mesh`, no `Config` and
// no gmsh, so a test of it needs none of them — the test executable links
// `hybmesh_pure` alone and is not linked against libgmsh at all, which means the
// build itself proves the independence instead of a rule asserting it.
//
// That independence is not a purity exercise, it is what the binning's real input
// turned out to be. As a private member of BoundaryLayerGenerator it took a
// 22-field mutable FrontState plus `Mesh&`, and read from all of that: three
// positions/normals per node, one `skipBL` bool per node, and three scalars. The
// wide signature hid how narrow the dependency was, and made a unit test require
// building a mesh.
namespace hybmesh {

// One surface node's resolved junction decision under the 4-case angle-driven
// scheme (BL_JUNCTION_METHOD == 1). `caseId == 0` means the node is not a
// junction and every other field is meaningless.
//
// The four fields are ONE decision and are returned as one; they used to be
// three parallel per-node arrays filled in place in the middle of generate().
struct JunctionDecision {
    int      caseId = 0;      // 1 = slide, 2/4 = perpendicular cap, 3 = extension cap
    Vector2D dir;             // growth ray for this node
    double   mult = 1.0;      // step scale (1/cos(tilt)) holding the PERPENDICULAR
                              // height at dTotal for a tilted cap
    double   thetaDeg = -1.0; // the flow-facing angle the case was binned from.
                              // NEGATIVE means no angle was computed: an isolated
                              // BL corner (both neighbours no-BL) keeps the
                              // perpendicular it was already given, and the caller
                              // uses the sign to reproduce the debug trace exactly.
};

// One node of the front ring: exactly what the binning reads, and nothing else.
// The ring is CLOSED — index arithmetic wraps — because a BL front is a loop.
struct JunctionNode {
    Point2D  pos;                // initial position
    Vector2D n1, n2;             // outward normals of the backward / forward edge
    Vector2D baseN;              // perpendicular cap direction the base detection chose.
                                 // Passed IN so the isolated-BL-corner case, which keeps
                                 // it, needs no exception at the call site.
    bool     skipBL = false;     // this node grows no layer
    bool     isJunction = false; // a growing node with at least one no-BL neighbour
};

// The three config scalars the binning actually uses, plus the layer's total
// height. Deliberately NOT `BLParams`: naming them is what makes the narrowness
// visible, and it keeps `Config.hpp`'s .dat parser out of the decision layer.
//
// The members are zeroed rather than pre-filled with the real defaults. Those
// live in Config.hpp and every caller supplies all four, so a copy here would be
// a THIRD place the numbers are written — free to drift from the config parser
// with nothing to notice.
struct JunctionParams {
    double angleC2 = 0.0;            // BL_JUNCTION_ANGLE_C2: case 2 / case 3 boundary
    double angleC3 = 0.0;            // BL_JUNCTION_ANGLE_C3: case 3 / case 4 boundary
    double concaveInfluence = 0.0;   // BL_CONCAVE_INFLUENCE_MULTIPLIER
    double dTotal = 0.0;             // the BL's total perpendicular height
};

// A junction whose wedge is too sharp for the concave blend to lean the layer
// over. Reported as DATA rather than logged here, for two reasons: the message
// is user-interface prose naming config keys (a CLI concern, not a geometric
// one), and a threshold that returns a value can be tested — the 21.8 deg
// prediction and the measured 22-meshes / 21-fails break are pinned by
// tests/cpp/test_junction_scheme.cpp without generating a mesh.
struct JunctionWarning {
    Point2D pos;
    double thetaDeg = 0.0;
    double squeezedLen = 0.0;  // wall the corner squeezes the layer over: dTotal/tan(theta)
    double blendReach = 0.0;   // how far the concave blend reaches: influence * dTotal
    double needMult = 0.0;     // the influence that would cover squeezedLen
};

struct JunctionClassification {
    std::vector<JunctionDecision> decisions;  // parallel to the input ring
    std::vector<JunctionWarning>  warnings;   // in ring order; usually empty
    // Positions of ISOLATED BL corners — nodes whose BOTH neighbours grow no
    // layer. Such a node grows a full-height column but registers no lateral
    // one, so the final front runs out along that column and back down the same
    // one; Gmsh gets a hole boundary that doubles back and triangulates nothing,
    // and the run ends at "empty far-field mesh ... the domain loop likely
    // failed to close". That message names the symptom, at the wrong layer, and
    // gives the user nothing to act on — so the corner is reported here and the
    // caller names its coordinates.
    //
    // Position ONLY: the wedge warning's angle, squeezed length and blend reach
    // are meaningless for this case, and borrowing that struct to carry three
    // dead fields is how a record starts lying about what it knows.
    //
    // Advisory. The run still fails, with the same exit code as before — that
    // failure is honest, and refusing earlier would only stand in the way of one
    // day giving this node a lateral column so it meshes.
    std::vector<Point2D> isolatedCorners;
};

// Bin every junction node of one front from the flow-facing included angle theta
// between its BL edge and its no-BL neighbour edge. Reads nothing but `ring` and
// `p`, mutates nothing, and the geometric 95-degree slide bound is explained at
// the definition.
JunctionClassification classifyJunctions(const std::vector<JunctionNode>& ring,
                                         const JunctionParams& p);

}  // namespace hybmesh

#endif
