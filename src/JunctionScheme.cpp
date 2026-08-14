// See JunctionScheme.hpp for what this decides and why it needs no mesh.
//
// Moved out of BoundaryLayerGenerator verbatim: the geometry below is unchanged
// from the private member it replaces (which was itself extracted from 135 lines
// in the middle of generate()). The two behavioural differences are both about
// OUTPUT, not about the decision: the very-sharp-wedge warning is returned
// instead of logged, and the debug trace is left to the caller (which is why the
// computed angle now travels in the decision).
#include "JunctionScheme.hpp"

#include <cmath>

namespace hybmesh {

JunctionClassification classifyJunctions(const std::vector<JunctionNode>& ring,
                                         const JunctionParams& p) {
    const int n_init = static_cast<int>(ring.size());
    JunctionClassification out;
    out.decisions.assign(static_cast<size_t>(n_init), JunctionDecision{});
    if (n_init == 0) return out;

    for (int i = 0; i < n_init; ++i) {
        if (!ring[i].isJunction) continue;
        int ip = (i - 1 + n_init) % n_init, in = (i + 1) % n_init;
        bool prevSkip = ring[ip].skipBL;
        bool nextSkip = ring[in].skipBL;
        // Isolated BL node (both neighbours no-BL): keep the perpendicular cap
        // direction the base detection already chose for it. No angle is computed,
        // so thetaDeg stays negative and the caller emits no trace line for it.
        if (prevSkip && nextSkip) {
            out.decisions[i] = JunctionDecision{2, ring[i].baseN, 1.0, -1.0};
            continue;
        }

        // step points from this node INTO the no-BL run; the BL neighbour is
        // on the other side. nBL is the BL edge's outward (into-flow) normal.
        int step   = nextSkip ? 1 : -1;
        Vector2D nBL = (nextSkip ? ring[i].n1 : ring[i].n2).normalized();
        int blNbr = (i - step + n_init) % n_init;
        int s1    = (i + step + n_init) % n_init;
        int s2    = (i + 2 * step + n_init) % n_init;
        bool s2skip = ring[s2].skipBL;

        Vector2D tBL = (ring[blNbr].pos - ring[i].pos).normalized(); // node -> BL interior
        Vector2D d1  = (ring[s1].pos    - ring[i].pos).normalized(); // node -> first no-BL nbr
        // The shared corner may belong to EITHER segment (the resampler gives
        // it to the segment starting there). If the first no-BL neighbour just
        // continues the BL edge (d1 ~ -tBL), the real corner is at s1 and the
        // no-BL EDGE direction is s1->s2; otherwise the corner is this node and
        // the no-BL edge is node->s1. This keeps theta = the true edge-to-edge
        // angle regardless of which segment owns the corner point.
        Vector2D tCorner, eNbr;
        if (s2skip && d1.dot(tBL) < -0.7) {
            tCorner = (ring[i].pos  - ring[s1].pos).normalized();    // corner s1 -> BL interior
            eNbr    = (ring[s2].pos - ring[s1].pos).normalized();    // corner s1 -> no-BL edge
        } else {
            tCorner = tBL;
            eNbr    = d1;
        }
        // theta = angle from the BL edge to the no-BL edge, swept THROUGH THE
        // FLOW (the side nBL points to); 180 = collinear, <180 concave, >180
        // convex — identical for internal/external flow.
        double a = std::atan2(tCorner.cross(eNbr), tCorner.dot(eNbr));
        if (tCorner.cross(nBL) < 0.0) a = -a;           // flow on the CW side -> flip sweep sign
        double theta = a; if (theta <= 1e-9) theta += 2.0 * M_PI;
        double thetaDeg = theta * 180.0 / M_PI;

        int caseId; Vector2D dir;
        // A cap only works while it points INTO the fluid wedge at the corner.
        // That wedge spans theta (BL edge -> no-BL edge, measured through the
        // flow); a PERPENDICULAR cap sits at 90 deg from the BL edge. So for
        // theta <= 90 the perpendicular points AT or PAST the no-BL edge and
        // the column leaves the domain through the wall it is supposed to stop
        // at: the final front then crosses the no-BL surface run (theta < 90)
        // or lands exactly on it and hands Gmsh a doubled-back hole boundary
        // (theta == 90 — i.e. EVERY rectangular internal-flow duct with one
        // wall marked no-BL). Such a junction must lean onto the neighbour
        // edge; it is the wedge that is too narrow for a cap, not the BL that
        // is too thick. Just above 90 a cap is admissible but leaves a sliver
        // wedge (width dTotal*tan(theta-90)) running the cap's whole length,
        // so a small guard band leans too: tilting the column by <= 5 deg is
        // cheaper than a triangle strip < 0.09*dTotal wide, and it keeps the
        // decision robust against a "90 deg" corner that floats to 90.000001.
        // Leaning = case 1: the column SLIDES along the neighbour edge and
        // absorbs the no-BL nodes it covers (so the ring resumes beyond the
        // slide instead of doubling back), and the 1/cos(tilt) correction
        // below keeps its PERPENDICULAR height at dTotal.
        //
        // This bound is geometric, not a preference, so it is fixed here
        // rather than read from BL_JUNCTION_ANGLE_C1: C1 defaulted to 135 deg,
        // which slid at corners wide enough for an honest perpendicular cap
        // and needlessly collapsed the layer onto the no-BL wall (fixed in
        // 6a830f7 by dropping case 1 altogether — which is what broke every
        // theta <= 90 junction). C1 still drives BL_JUNCTION_METHOD=0 and
        // config round-trip. Above the band, cases 2/3/4 are unchanged.
        const double kSlideMaxTheta = 95.0;   // deg; see above
        if      (thetaDeg <= kSlideMaxTheta) { caseId = 1; dir = eNbr; }
        else if (thetaDeg <= p.angleC2)      { caseId = 2; dir = nBL; }
        else if (thetaDeg <= p.angleC3)      { caseId = 3; dir = eNbr * -1.0; }
        else                                 { caseId = 4; dir = nBL; }
        // Height (not edge-length) correction: what stays fixed across ALL
        // cases is the BL's PERPENDICULAR total height dTotal. A tilted cap
        // grown a fixed EDGE length would only reach dTotal*cos(tilt) high and
        // dip below the neighbouring perpendicular columns, skewing the corner.
        // So scale the step by 1/cos(tilt) = 1/dot(dir,nBL) — the same trick the
        // convex parallelogram uses for its diagonal ray (cos clamped so a very
        // sharp concave cannot blow the column length up).
        double hmult = 1.0 / std::max(0.25, dir.dot(nBL));
        out.decisions[i] = JunctionDecision{caseId, dir, hmult, thetaDeg};

        // A slide at a VERY SHARP wedge cannot be graded, and without this the
        // failure surfaces only as a bare front self-intersection / Gmsh error
        // whose message points at the BL size anywhere on the model. Report it
        // here, while the cause is still identifiable.
        //
        // The wedge closes at theta, so at arc distance x from the corner the
        // clearance to the no-BL edge is only x*tan(theta): every column within
        // dTotal/tan(theta) of the corner has to be leaned over, and only the
        // concave blend does that, over concaveInfluence * dTotal of arc length.
        // Once the squeezed run outgrows that reach, the columns beyond it still
        // grow perpendicular into a gap too narrow to hold them and the front
        // folds — i.e. the criterion is tan(theta) * influence < 1, independent
        // of dTotal. Measured: at the default influence 2.5 the break sits
        // between 22 deg (meshes) and 21 deg (fails), against a predicted
        // atan(1/2.5) = 21.8; influence 5.0 moves it to between 15 and 10 deg
        // and influence 1.5 to between 35 and 30 deg, both as predicted.
        // 1.15 is a small margin so the warning lands BEFORE the failure, and
        // the global influence is used deliberately — concave_D_inf's extra cap
        // for a nearby corner is a different mechanism and does not fail this way.
        if (caseId == 1 && thetaDeg < 90.0) {
            double tanT = std::tan(thetaDeg * M_PI / 180.0);   // > 0 below 90 deg
            if (tanT * p.concaveInfluence < 1.15) {
                JunctionWarning w;
                w.pos         = ring[i].pos;
                w.thetaDeg    = thetaDeg;
                w.squeezedLen = (tanT > 1e-9) ? p.dTotal / tanT : 0.0;
                w.blendReach  = p.concaveInfluence * p.dTotal;
                w.needMult    = std::ceil(((tanT > 1e-9) ? 1.0 / tanT : 99.0) * 10.0) / 10.0;
                out.warnings.push_back(w);
            }
        }
    }
    return out;
}

}  // namespace hybmesh
