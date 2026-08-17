// hybmesh::classifyJunctions — the BL/no-BL junction binning.
//
// This executable links hybmesh_pure and NOTHING else: not gmsh, not
// hybmesh_core, not a Mesh. That is the point. The binning was extracted from
// generate() specifically so it could be reasoned about and tested, and then sat
// unreachable for two reasons at once — it was private, and reaching it meant
// building a mesh. Both are gone, and it shows in what this file can cover:
//
//   * cases 3 and 4 (theta > 270 deg, a strongly CONVEX junction) have NO
//     geometry generator anywhere in the repo, so no mesh-level test has ever
//     exercised them. Here they are four lines each.
//   * the very-sharp-wedge warning threshold is pinned directly, including how it
//     moves with BL_CONCAVE_INFLUENCE_MULTIPLIER. Through a mesh, the same claim
//     needed a run per angle and a scrape of stderr.
//   * the internal-vs-external-flow symmetry the sweep-sign rule exists for is
//     checked as an INVARIANT (mirror the geometry, get the same answer) rather
//     than as two hard-coded numbers.
#include "check.hpp"

#include "JunctionScheme.hpp"

#include <cmath>
#include <vector>

using hybmesh::JunctionNode;
using hybmesh::JunctionParams;
using hybmesh::classifyJunctions;

namespace {

// A 4-node ring holding ONE junction, at index 0, whose flow-facing angle is
// exactly `thetaDeg`:
//   index 3 — the BL neighbour, at +x, so the BL edge direction is +x
//   index 1 — the first no-BL neighbour, placed at `thetaDeg` from +x
//   index 2 — a GROWING filler: it keeps the second no-BL node absent, which is
//             what keeps the corner-disambiguation branch out of the way here
//             (that branch gets its own case below)
// The BL edge normal is +y, so the sweep is not sign-flipped and theta comes out
// as the angle placed at index 1 — which is what lets any bin be requested
// directly. `sign = -1` mirrors the whole thing in y (flow on the other side).
std::vector<JunctionNode> ringAt(double thetaDeg, double sign = 1.0) {
    const double r = thetaDeg * M_PI / 180.0;
    std::vector<JunctionNode> ring(4);
    ring[0].pos = {0.0, 0.0};
    ring[0].n1 = {0.0, sign};          // backward edge (3 -> 0) = the BL edge
    ring[0].n2 = {0.0, sign};
    ring[0].baseN = {0.0, sign};
    ring[0].isJunction = true;
    ring[3].pos = {1.0, 0.0};
    ring[1].pos = {std::cos(r), sign * std::sin(r)};
    ring[1].skipBL = true;
    ring[2].pos = {5.0, sign * 5.0};
    return ring;
}

JunctionParams params(double influence = 2.5, double dTotal = 0.2) {
    JunctionParams p;
    p.angleC2 = 270.0;
    p.angleC3 = 315.0;
    p.concaveInfluence = influence;
    p.dTotal = dTotal;
    return p;
}

// caseId of the single junction in a ring built by ringAt().
int caseOf(double thetaDeg, double sign = 1.0) {
    return classifyJunctions(ringAt(thetaDeg, sign), params()).decisions[0].caseId;
}

}  // namespace

int main() {
    // --- 1. the bins, at their boundaries -------------------------------------
    // The 95 deg slide bound is geometric, not a knob: below 90 a perpendicular
    // cap provably exits through the no-BL wall, and 90 exactly is a plain
    // rectangular duct with one wall marked No-BL.
    CHECK(caseOf(60.0) == 1, "an acute junction slides (case 1)");
    CHECK(caseOf(85.0) == 1, "85 deg — the reported acute junction — slides");
    CHECK(caseOf(90.0) == 1, "90 deg (a rectangular duct with one No-BL wall) slides");
    CHECK(caseOf(95.0) == 1, "the slide band is inclusive at 95 deg");
    CHECK(caseOf(95.5) == 2, "just past it, a perpendicular cap (case 2)");
    CHECK(caseOf(120.0) == 2, "120 deg caps perpendicular");
    CHECK(caseOf(270.0) == 2, "case 2 runs up to and including C2");
    // Cases 3 and 4 are what no mesh-level test in this repo reaches.
    CHECK(caseOf(271.0) == 3, "past C2, the neighbour-edge extension cap (case 3)");
    CHECK(caseOf(315.0) == 3, "case 3 runs up to and including C3");
    CHECK(caseOf(316.0) == 4, "past C3, back to a perpendicular cap (case 4)");
    CHECK(caseOf(350.0) == 4, "a nearly-closed convex junction is case 4");

    // --- 2. the direction and the height correction ----------------------------
    // What stays fixed across every case is the PERPENDICULAR height, so a tilted
    // cap's step is scaled by 1/cos(tilt) = 1/dot(dir, nBL).
    {
        const double th = 85.0, r = th * M_PI / 180.0;
        hybmesh::JunctionDecision d = classifyJunctions(ringAt(th), params()).decisions[0];
        CHECK_NEAR(d.thetaDeg, th, 1e-9, "the binned angle is reported, not just the case");
        CHECK_NEAR(d.dir.x, std::cos(r), 1e-12, "a slide grows ALONG the neighbour edge (x)");
        CHECK_NEAR(d.dir.y, std::sin(r), 1e-12, "...and (y)");
        CHECK_NEAR(d.mult, 1.0 / std::sin(r), 1e-12,
                   "the step is scaled by 1/cos(tilt) so the perpendicular height holds");
    }
    {
        hybmesh::JunctionDecision d = classifyJunctions(ringAt(120.0), params()).decisions[0];
        CHECK_NEAR(d.dir.x, 0.0, 1e-12, "a perpendicular cap grows along the BL normal (x)");
        CHECK_NEAR(d.dir.y, 1.0, 1e-12, "...and (y)");
        CHECK_NEAR(d.mult, 1.0, 1e-12, "an untilted cap needs no height correction");
    }
    {
        const double th = 300.0, r = th * M_PI / 180.0;
        hybmesh::JunctionDecision d = classifyJunctions(ringAt(th), params()).decisions[0];
        CHECK_NEAR(d.dir.x, -std::cos(r), 1e-12,
                   "case 3 grows along the neighbour edge REVERSED (x)");
        CHECK_NEAR(d.dir.y, -std::sin(r), 1e-12, "...and (y)");
        CHECK_NEAR(d.mult, 1.0 / -std::sin(r), 1e-12, "...with its own tilt correction");
    }
    {
        // A very sharp slide would blow the column length up, so the cosine is
        // clamped at 0.25 — the multiplier saturates at 4 instead of diverging.
        hybmesh::JunctionDecision d = classifyJunctions(ringAt(10.0), params()).decisions[0];
        CHECK(d.caseId == 1, "a 10 deg wedge still slides");
        CHECK_NEAR(d.mult, 4.0, 1e-12, "the height correction is clamped at 1/0.25");
    }

    // --- 3. internal and external flow must agree -----------------------------
    // The sweep is measured THROUGH THE FLOW, and the sign flip exists so which
    // side the fluid is on cannot change the answer. Checked as an invariant
    // rather than as a second set of magic numbers.
    for (double th : {60.0, 85.0, 95.0, 120.0, 271.0, 316.0}) {
        hybmesh::JunctionDecision a = classifyJunctions(ringAt(th, 1.0), params()).decisions[0];
        hybmesh::JunctionDecision b = classifyJunctions(ringAt(th, -1.0), params()).decisions[0];
        CHECK(a.caseId == b.caseId,
              "mirroring the flow to the other side gives the same case");
        CHECK_NEAR(a.thetaDeg, b.thetaDeg, 1e-9, "...and the same angle");
        CHECK_NEAR(a.mult, b.mult, 1e-12, "...and the same height correction");
        CHECK_NEAR(a.dir.x, b.dir.x, 1e-12, "...and a mirrored direction (x unchanged)");
        CHECK_NEAR(a.dir.y, -b.dir.y, 1e-12, "...(y mirrored)");
    }

    // --- 4. an isolated BL corner keeps its perpendicular ---------------------
    // Both neighbours no-BL: no angle can be measured across the corner, so the
    // node must keep the perpendicular the base detection already chose.
    //
    // The mesh-level suite is NOT blind here, and measurement said so: breaking
    // this branch is caught by test_nobl_junction_acute.py and by the golden set
    // too, because the case's sanctioned outcome is a clean rc=6 with no mesh and
    // the break turns it into a successful run. What only this test can check is
    // the DIRECTION and the multiplier — with no mesh written there is nothing
    // downstream to measure them on.
    {
        std::vector<JunctionNode> ring = ringAt(85.0);
        ring[3].skipBL = true;                       // now BOTH neighbours are no-BL
        ring[0].baseN = {0.0, 1.0};
        hybmesh::JunctionClassification c = classifyJunctions(ring, params());
        CHECK(c.decisions[0].caseId == 2, "an isolated BL corner caps perpendicular");
        CHECK_NEAR(c.decisions[0].dir.y, 1.0, 1e-12, "...along the direction it was given");
        CHECK_NEAR(c.decisions[0].mult, 1.0, 1e-12, "...at full height");
        CHECK(c.decisions[0].thetaDeg < 0.0,
              "...reporting no angle, so the caller emits no trace line for it");
        CHECK(c.warnings.empty(), "...and warns about nothing");
    }

    // --- 5. the corner may belong to the neighbouring segment -----------------
    // The resampler gives a shared corner to the segment STARTING there, so the
    // first no-BL neighbour can simply continue the BL edge, putting the real
    // corner one node further on. Measured at the wrong node, the angle here
    // would come out 180 (case 2) instead of 300 (case 3).
    {
        std::vector<JunctionNode> ring(5);
        const double psi = 300.0 * M_PI / 180.0;
        ring[0].pos = {0.0, 0.0};
        ring[0].n1 = {0.0, 1.0};
        ring[0].n2 = {0.0, 1.0};
        ring[0].baseN = {0.0, 1.0};
        ring[0].isJunction = true;
        ring[4].pos = {1.0, 0.0};                    // BL neighbour: BL edge is +x
        ring[1].pos = {-1.0, 0.0};                   // no-BL, straight on from the BL edge
        ring[1].skipBL = true;
        ring[2].pos = {-1.0 + std::cos(psi), std::sin(psi)};   // the REAL corner is at [1]
        ring[2].skipBL = true;
        ring[3].pos = {5.0, 5.0};
        hybmesh::JunctionDecision d = classifyJunctions(ring, params()).decisions[0];
        CHECK_NEAR(d.thetaDeg, 300.0, 1e-9,
                   "the angle is measured at the corner, not at the tagged node");
        CHECK(d.caseId == 3, "...so the case follows the real corner (300 deg -> case 3)");
    }

    // --- 6. the very-sharp-wedge warning -------------------------------------
    // Criterion: tan(theta) * influence < 1.15, independent of the BL height. The
    // 1.15 is margin, so the warning must land BEFORE the measured failure at
    // ~21.8 deg (the mesher meshes 22 and fails 21 at influence 2.5) — the
    // threshold therefore sits at atan(1.15/2.5) = 24.7 deg, and moves with the
    // influence. Nothing here generates a mesh.
    {
        JunctionParams p = params(2.5, 0.2);
        CHECK(classifyJunctions(ringAt(21.0), p).warnings.size() == 1,
              "a 21 deg wedge (the mesher fails there) is warned about");
        CHECK(classifyJunctions(ringAt(22.0), p).warnings.size() == 1,
              "so is 22 deg — the warning has margin over the 21.8 deg break");
        CHECK(classifyJunctions(ringAt(24.0), p).warnings.size() == 1,
              "...up to the atan(1.15/2.5) = 24.7 deg threshold");
        CHECK(classifyJunctions(ringAt(26.0), p).warnings.empty(),
              "...and 26 deg is quiet");

        JunctionParams wide = params(5.0, 0.2);
        CHECK(classifyJunctions(ringAt(12.0), wide).warnings.size() == 1,
              "a longer concave blend moves the threshold down (12 deg warns at 5.0)");
        CHECK(classifyJunctions(ringAt(14.0), wide).warnings.empty(),
              "...and 14 deg no longer does");

        JunctionParams narrow = params(1.5, 0.2);
        CHECK(classifyJunctions(ringAt(36.0), narrow).warnings.size() == 1,
              "a shorter blend moves it up (36 deg warns at 1.5)");
        CHECK(classifyJunctions(ringAt(39.0), narrow).warnings.empty(),
              "...and 39 deg does not");

        // The theta < 90 guard is load bearing: tan(theta) is NEGATIVE above 90,
        // so without it the criterion is satisfied by every obtuse junction and
        // the warning fires on healthy caps.
        CHECK(classifyJunctions(ringAt(92.0), p).warnings.empty(),
              "an obtuse junction is never a sharp wedge (tan goes negative)");
        CHECK(classifyJunctions(ringAt(300.0), p).warnings.empty(),
              "...nor is a convex one");
    }

    // --- 7. what the warning carries -----------------------------------------
    // The numbers travel as data so the message (config-key prose) can live at
    // the call site while the threshold stays testable here.
    {
        const double th = 20.0, tanT = std::tan(th * M_PI / 180.0);
        JunctionParams p = params(2.5, 0.2);
        hybmesh::JunctionClassification c = classifyJunctions(ringAt(th), p);
        CHECK(c.warnings.size() == 1, "one wedge, one warning");
        if (c.warnings.size() == 1) {
            const hybmesh::JunctionWarning& w = c.warnings[0];
            CHECK_NEAR(w.thetaDeg, th, 1e-9, "the warning names the angle");
            CHECK_NEAR(w.pos.x, 0.0, 1e-12, "...and where the corner is (x)");
            CHECK_NEAR(w.pos.y, 0.0, 1e-12, "...(y)");
            CHECK_NEAR(w.squeezedLen, 0.2 / tanT, 1e-12,
                       "the squeezed wall run is dTotal/tan(theta)");
            CHECK_NEAR(w.blendReach, 2.5 * 0.2, 1e-12,
                       "the blend reach is influence*dTotal");
            CHECK_NEAR(w.needMult, std::ceil((1.0 / tanT) * 10.0) / 10.0, 1e-12,
                       "the suggested influence is 1/tan(theta), rounded up to 0.1");
        }
    }

    // --- 8. nodes that are not junctions, and no nodes at all ----------------
    {
        hybmesh::JunctionClassification c = classifyJunctions(ringAt(85.0), params());
        CHECK(c.decisions.size() == 4, "one decision per ring node");
        CHECK(c.decisions[1].caseId == 0 && c.decisions[2].caseId == 0
              && c.decisions[3].caseId == 0,
              "a node that is not a junction gets caseId 0");
        CHECK(classifyJunctions({}, params()).decisions.empty(),
              "an empty front classifies to nothing rather than crashing");
    }

    return hybmesh::test::report("test_junction_scheme");
}
