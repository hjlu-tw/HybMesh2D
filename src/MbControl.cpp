#include "MbControl.hpp"

#include <algorithm>
#include <cmath>

// The multi-block control functions. See include/MbControl.hpp for what these are
// for and why they are their own module; this file is the arithmetic.
//
// ONE DERIVATION, WRITTEN OUT ONCE, because every term in it is load bearing and
// a wrong one is not visible in a mesh until it is a fold.
//
// WHAT THE DECLARATION ASKS FOR is one vector per station along a declared wall:
// the node one grid line in from the wall node should sit at
//
//     p_target  =  p_wall  +  requested_height * inward_unit_normal
//
// which is BOTH requirements at once — the grid line leaves the wall at 90
// degrees, and its first cell is the height the document asked for.
//
// THE TARGET IS A POSITION, NOT A DERIVATIVE, and that distinction is worth 8.7%
// on the shipped C-grid. The textbook Steger-Sorenson wall condition specifies
// r_n, the derivative of the map at the wall — but what the declaration asks for
// and what the ruler measures is |p_1 - p_0|, the first INTERVAL. On a
// geometrically graded line of ratio q the two differ by (q - 1) / ln q: at this
// case's q of about 1.18 a control aimed at the derivative settles neatly onto an
// interval 8.7% larger than anybody asked for. So the condition here is stated on
// the POSITION, which is unambiguous and is the quantity the acceptance gate reads.
//
// AND IT IS SOLVED FOR EXACTLY, at the first INTERIOR row rather than at the
// frozen wall row. Write the kernel's own update of the node (k, 1) with unknown
// source terms: with D = 2(a + g) it is a weighted mean, and it is LINEAR in phi
// and psi.
//
//     update  =  (S  +  phi * A  +  psi * B) / D
//     S = a*(p[k+1][1] + p[k-1][1]) + g*(p[k][2] + p[k][0]) - 2b * cross
//     A = (a/2) * (p[k+1][1] - p[k-1][1])         (what phi moves it along)
//     B = (g/2) * (p[k][2]   - p[k][0])           (what psi moves it along)
//
// Asking that the update land on p_target is then two scalar equations in two
// unknowns; A and B are independent directions on any cell that is not
// degenerate, so Cramer's rule finishes it:
//
//     R    =  D * p_target - S
//     phi  =  (R x B) / (A x B)
//     psi  =  (A x R) / (A x B)
//
// This is a source term and NOT a Dirichlet condition on row 1: what is written
// is phi and psi, they are damped into the interior like any control function,
// and every row including that one is still solved by the kernel from its own
// nine neighbours. The solve is LAGGED, so each sweep re-solves against the mesh
// the last one left and the target and the mesh converge on each other.
//
// THE TWO REQUIREMENTS ARE NOT DRIVEN EQUALLY, and saying so plainly matters more
// than the formula, because the name "control functions" invites a stronger claim
// than what is here.
//
// THE HEIGHT IS SOLVED FOR. One scalar, one equation, exactly: the source term
// that lands the node at the requested distance from the wall. That is why it is
// held to 0.09% on the shipped C-grid and why a graded rectangle is a fixed point.
//
// THE 90 DEGREES IS DRIVEN INDIRECTLY, by three things and by no term that states
// it. It enters as the TIE-BREAK between the quadratic's two roots — both put the
// node at the correct distance, and the one taken is on the perpendicular side —
// and then as the elliptic operator's own tendency, helped by the along-wall
// Thomas-Middlecoff source keeping the first interior line's distribution matched
// to the wall's so the two do not shear. A DIRECT condition on the angle was
// tried: it is the Steger-Sorenson projection onto r_s, and near a viscous wall
// a = |r_n|^2 is the SMALL metric coefficient while g = |r_s|^2 is the large one,
// so the source it asks for goes as 1/h^2 — about -21 on this case. It clips, and
// the clipped value carried into the interior destabilises the solve. So the angle
// is not a knob here, and the measured consequence is that it improves and then
// TURNS: 32.04 deg -> 29.90 at twenty sweeps, back to 31.55 at thirty and 34.78 at
// forty. Recorded rather than implied by the module's name.
namespace {

// One boundary line's tangent at station `k`: central where it exists, one-sided
// at the two ends. Shared because three callers need it and a one-sided
// difference is the kind of detail that gets written differently in two places.
template <typename At>
Point2D wallTangent(int k, int n, const At& at) {
    const int ka = (k > 0) ? k - 1 : k;
    const int kb = (k + 1 < n) ? k + 1 : k;
    return at(kb) - at(ka);
}

// HOW TO WALK ONE DECLARED WALL SIDE: the indices all three functions below need,
// derived once from `mbSideAxis` instead of three times by hand.
//
// Extracted for the reason `wallTangent` next door gives and this clump did not
// heed: it was written three times, each with its own copy of
// `t0 = ax.atFarEnd ? m - 1 : 0`, `t1 = ax.atFarEnd ? m - 2 : 1` and its own
// bounds-clamped position lambda — which is the shape that lets one of them
// disagree with the others, and #83's review named it.
//
// `ok` is false for a block too thin to walk. Checked by the caller rather than
// returning an optional: each caller has a different thing to do about it, and two
// of them still publish part of their answer for such a side.
struct SideWalk {
    hybmesh::MbSideAxis ax{"south", true, false};
    int n = 0;       // stations along the side
    int m = 0;       // grid lines across it
    int t0 = 0;      // the on-wall line
    int t1 = 0;      // one line in from it
    int tFar = 0;    // the line facing the wall
    bool ok = false;
};

SideWalk sideWalk(const hybmesh::MbBlock& b, hybmesh::MbSide side) {
    SideWalk w;
    w.ax = hybmesh::mbSideAxis(side);
    const size_t want = static_cast<size_t>(b.ni) * static_cast<size_t>(b.nj);
    if (b.ni < 2 || b.nj < 2 || b.nodeIds.size() != want) return w;
    w.n = w.ax.alongI ? b.ni : b.nj;
    w.m = w.ax.alongI ? b.nj : b.ni;
    w.t0 = w.ax.atFarEnd ? w.m - 1 : 0;
    w.t1 = w.ax.atFarEnd ? w.m - 2 : 1;
    w.tFar = w.ax.atFarEnd ? 0 : w.m - 1;
    w.ok = true;
    return w;
}

// The node at station `k`, `tt` grid lines across — in the SIDE's frame, so
// nothing above has to know which of i and j the side runs along. Out of range
// returns the origin rather than reading past the end, on the same rule
// `MbControlField::at` follows: this module promises never to throw.
Point2D sideNode(const hybmesh::MbBlock& b, const std::vector<Point2D>& nodes,
                 const SideWalk& w, int k, int tt) {
    const int i = w.ax.alongI ? k : tt, j = w.ax.alongI ? tt : k;
    if (i < 0 || j < 0 || i >= b.ni || j >= b.nj) return {0.0, 0.0};
    const int id = b.nodeAt(i, j);
    if (id < 0 || static_cast<size_t>(id) >= nodes.size()) return {0.0, 0.0};
    return nodes[static_cast<size_t>(id)];
}

// THOMAS-MIDDLECOFF: the source term that reproduces a boundary line's OWN point
// distribution, from that line alone. Projecting (r_ss + phi * r_s) = 0 onto r_s
// gives phi = -(r_ss . r_s) / |r_s|^2, which is the same statement as
// `geometricSource` for a line that happens to be geometric and is more general:
// it reproduces a tanh, a cosine or a hand-written distribution equally.
//
// Read off FROZEN nodes at every use below — a boundary line of the block — so
// this is a declaration realised, not a measurement of something the solve moved.
double tmSource(const Point2D& rs, const Point2D& rss) {
    const double g = rs.lengthSq();
    if (!(g > 0.0)) return 0.0;
    return -rss.dot(rs) / g;
}

}  // namespace

hybmesh::MbControlField hybmesh::mbControlField(
        const MbBlock& b, int blockIdx,
        const std::vector<Point2D>& nodes,
        const std::vector<MbWallTarget>& targets) {
    MbControlField f;
    f.ni = b.ni;
    f.nj = b.nj;
    const size_t want = static_cast<size_t>(b.ni) * static_cast<size_t>(b.nj);
    if (b.ni < 3 || b.nj < 3 || b.nodeIds.size() != want) return f;
    f.q.assign(want, MbControl{});
    // Accumulated as (value * weight, weight) and divided at the end, so two
    // OPPOSITE walls driving one direction produce a linear blend between what
    // each asks for rather than the sum of two full-strength demands. With a
    // single wall the weights cancel and its value stands, which is what a
    // Thomas-Middlecoff control does and is what preserves a grading.
    std::vector<MbControl> acc(want, MbControl{});
    std::vector<double> wI(want, 0.0), wJ(want, 0.0);

    auto node = [&](int i, int j) -> Point2D {
        const int id = b.nodeAt(i, j);
        if (id < 0 || static_cast<size_t>(id) >= nodes.size()) return {0.0, 0.0};
        return nodes[static_cast<size_t>(id)];
    };

    for (const MbWallTarget& t : targets) {
        if (t.block != blockIdx || !t.usable) continue;
        const SideWalk sw = sideWalk(b, t.side);
        if (!sw.ok) continue;
        const MbSideAxis& ax = sw.ax;
        const int n = sw.n, m = sw.m, t0 = sw.t0, t1 = sw.t1, tFar = sw.tFar;
        if (static_cast<int>(t.requested.size()) != n
            || static_cast<int>(t.normal.size()) != n) continue;
        auto pos = [&](int k, int tt) { return sideNode(b, nodes, sw, k, tt); };

        for (int k = 1; k + 1 < n; ++k) {
            const double h = t.requested[static_cast<size_t>(k)];
            const Point2D nhat = t.normal[static_cast<size_t>(k)];
            if (!(h > 0.0) || nhat.lengthSq() <= 0.0) continue;

            // ── THE ALONG-WALL SOURCE: hold each end's OWN distribution ──
            //
            // Thomas-Middlecoff at both ends of the off-wall direction, blended
            // linearly across it. The wall end holds the surface distribution the
            // declaration laid down, which is what keeps the first interior line
            // from shearing along the wall. The FAR end is read the same way off
            // its own frozen row, because that row is frozen too and a control
            // that ignored it would fight it and pile the conflict into the last
            // cells before it.
            const Point2D wRs  = (pos(k + 1, t0) - pos(k - 1, t0)) * 0.5;
            const Point2D wRss = pos(k + 1, t0) - pos(k, t0) * 2.0 + pos(k - 1, t0);
            const Point2D fRs  = (pos(k + 1, tFar) - pos(k - 1, tFar)) * 0.5;
            const Point2D fRss = pos(k + 1, tFar) - pos(k, tFar) * 2.0
                               + pos(k - 1, tFar);
            const double alongWall = tmSource(wRs, wRss);
            const double alongFar  = tmSource(fRs, fRss);
            if (!std::isfinite(alongWall) || !std::isfinite(alongFar)) continue;

            // ── THE OFF-WALL SOURCE: land the first line AT the declared height ──
            //
            // Solved against the FULL kernel at the one node the declaration is
            // about, and solved for the quantity the RULER measures — the
            // DISTANCE |p_1 - p_wall| — rather than for a component of it.
            //
            // The kernel's update of (i1, j1) is (S + phi*A + psi*B) / D, linear
            // in both sources by construction (see mbWinslowUpdate), and the
            // along-wall source is already decided above. So write the update as
            // `base + source * dir` measured from the wall node and the condition
            // |base + source * dir| = h is one QUADRATIC in one scalar:
            //
            //     |dir|^2 s^2  +  2 (base.dir) s  +  |base|^2 - h^2  =  0
            //
            // Two roots, and the one taken is the root whose node lands nearer the
            // target position p_wall + h * n — which is where the 90-degree half
            // of the declaration enters this solve, as the tie-break between two
            // points at the same correct distance on opposite sides.
            //
            // TWO WEAKER VERSIONS WERE MEASURED AND REJECTED, both on the shipped
            // C-grid at one sweep against this one's 0.10%:
            //
            //   * the near-wall 1-D limit (psi = 4h/span - 2, from the update with
            //     the along-wall weights dropped) — 2.96%, and it got WORSE with
            //     more sweeps rather than better, because the 2-D miss it ignores
            //     never feeds back into the next sweep's source;
            //   * the LEAST-SQUARES solve for the target POSITION, projecting the
            //     required displacement onto `dir` — 11.75% and 36 saturated
            //     nodes, because one scalar cannot place a node in a plane and
            //     projecting spends it on both components instead of nailing the
            //     one that is measured.
            //
            // NO REAL ROOT is the control function meeting a request it cannot
            // honour: the whole line `dir` sweeps out lies further from the wall
            // than h, so no source term places the node at that distance. It then
            // takes the CLOSEST APPROACH, which is the honest best, and the wall
            // residual warning is what tells the user — measured on the nodes that
            // came out, not predicted from this branch being taken.
            const int i1 = ax.alongI ? k : t1, j1 = ax.alongI ? t1 : k;
            const Point2D iP = node(i1 + 1, j1), iM = node(i1 - 1, j1);
            const Point2D jP = node(i1, j1 + 1), jM = node(i1, j1 - 1);
            const Point2D di = (iP - iM) * 0.5, dj = (jP - jM) * 0.5;
            const double aa = dj.lengthSq();
            const double bb = di.dot(dj);
            const double gg = di.lengthSq();
            const double D = 2.0 * (aa + gg);
            if (!(D > 0.0)) continue;
            const Point2D crs = (node(i1 + 1, j1 + 1) - node(i1 - 1, j1 + 1)
                               - node(i1 + 1, j1 - 1) + node(i1 - 1, j1 - 1)) * 0.25;
            const Point2D S = (iP + iM) * aa + (jP + jM) * gg - crs * (2.0 * bb);
            const Point2D Aphi = (iP - iM) * (aa * 0.5);   // what phi moves it along
            const Point2D Bpsi = (jP - jM) * (gg * 0.5);   // what psi moves it along
            // A south/north wall runs along i, so ITS along-wall source is phi and
            // its off-wall source is psi; a west/east wall is the other way round.
            const Point2D& known = ax.alongI ? Aphi : Bpsi;
            const Point2D& unk   = ax.alongI ? Bpsi : Aphi;
            const Point2D p0 = pos(k, t0);
            const Point2D base = (S + known * alongWall) * (1.0 / D) - p0;
            const Point2D dir = unk * (1.0 / D);
            const double d2 = dir.lengthSq();
            if (!(d2 > 0.0)) continue;
            const double bd = base.dot(dir);
            const double disc = bd * bd - d2 * (base.lengthSq() - h * h);
            double offWall = -bd / d2;                       // the closest approach
            if (disc >= 0.0) {
                const double rt = std::sqrt(disc);
                const double s1 = (-bd + rt) / d2, s2 = (-bd - rt) / d2;
                const Point2D aim = nhat * h;
                offWall = ((base + dir * s1 - aim).lengthSq()
                           <= (base + dir * s2 - aim).lengthSq()) ? s1 : s2;
            }
            if (!std::isfinite(offWall)) continue;

            for (int tt = 1; tt + 1 < m; ++tt) {
                const int r = std::abs(tt - t0);   // grid lines from the wall
                const double e = static_cast<double>(r) / static_cast<double>(m - 1);
                const double w = 1.0 - e;          // this wall's share of the node
                const double along = (1.0 - e) * alongWall + e * alongFar;
                // THE OFF-WALL SOURCE IS WRITTEN AT THE FIRST LINE AND NOWHERE
                // ELSE, and that is the scope of what the declaration says. It
                // asks for ONE height — the first cell — and says nothing about
                // the rest of the line, so a control that carried this source
                // outward would be imposing a distribution nobody declared. It
                // was tried the other way (an ideal geometric line fitted to the
                // declared height and the line's length, sourced at every row):
                // the shipped C-grid's radial edges declare a TANH law, the ideal
                // and the actual diverge with distance, and the source saturated
                // at 2120 nodes and folded 432 cells. Measured, not reasoned.
                const int i = ax.alongI ? k : tt, j = ax.alongI ? tt : k;
                const size_t idx = static_cast<size_t>(j) * b.ni + i;
                // AT THE FIRST LINE the off-wall source is the declaration's;
                // BEYOND IT, it is Thomas-Middlecoff on the line's own current
                // spacing, which HOLDS whatever distribution the fill produced
                // there rather than relaxing it.
                //
                // That second half is what makes all three of #80's figures
                // improve at once, and the alternatives were measured on the
                // shipped C-grid rather than reasoned about. Sourcing NOTHING
                // beyond the first line lets the rest of the radial distribution
                // relax toward uniform, and the mean non-orthogonality then RISES
                // with every sweep (4.65 deg at one sweep, 6.14 at twenty, against
                // the unsmoothed fill's 4.56) because equidistributing a graded
                // grid skews every cell it touches a little. Sourcing an ideal
                // GEOMETRIC line instead — fitted to the declared height and the
                // line's length — imposes a distribution nobody declared: these
                // radial edges declare a TANH law, so the ideal and the actual
                // diverge with distance, and it saturated 2120 nodes and folded
                // 432 cells. Holding what is there costs nothing and asks for
                // nothing: the declaration owns the first cell, the fill owns the
                // rest of the line, and the solve is left to move the lines
                // themselves rather than the spacing along them.
                const Point2D ors = (pos(k, tt + 1) - pos(k, tt - 1)) * 0.5;
                const Point2D orss = pos(k, tt + 1) - pos(k, tt) * 2.0
                                   + pos(k, tt - 1);
                const double off = (r == 1) ? offWall : tmSource(ors, orss);
                if (ax.alongI) {
                    acc[idx].phi += along * w;  wI[idx] += w;
                    acc[idx].psi += off   * w;  wJ[idx] += w;
                } else {
                    acc[idx].psi += along * w;  wJ[idx] += w;
                    acc[idx].phi += off   * w;  wI[idx] += w;
                }
            }
        }
    }

    for (size_t idx = 0; idx < want; ++idx) {
        MbControl c;
        if (wI[idx] > 0.0) c.phi = acc[idx].phi / wI[idx];
        if (wJ[idx] > 0.0) c.psi = acc[idx].psi / wJ[idx];
        bool clip = false;
        if (c.phi >  MB_CONTROL_CLIP) { c.phi =  MB_CONTROL_CLIP; clip = true; }
        if (c.phi < -MB_CONTROL_CLIP) { c.phi = -MB_CONTROL_CLIP; clip = true; }
        if (c.psi >  MB_CONTROL_CLIP) { c.psi =  MB_CONTROL_CLIP; clip = true; }
        if (c.psi < -MB_CONTROL_CLIP) { c.psi = -MB_CONTROL_CLIP; clip = true; }
        if (clip) ++f.clipped;
        f.q[idx] = c;
    }
    return f;
}

std::vector<hybmesh::MbWallTarget> hybmesh::mbWallTargets(const MbResult& mesh) {
    std::vector<MbWallTarget> out;
    out.reserve(mesh.wallSpecs.size());
    for (const MbWallSpec& ws : mesh.wallSpecs) {
        MbWallTarget t;
        t.block = ws.block;
        t.side = ws.side;
        t.edgeId = ws.edgeId;
        if (ws.block < 0 || static_cast<size_t>(ws.block) >= mesh.blocks.size()) {
            out.push_back(t);
            continue;
        }
        const MbBlock& b = mesh.blocks[static_cast<size_t>(ws.block)];
        const size_t want = static_cast<size_t>(b.ni) * static_cast<size_t>(b.nj);
        if (b.ni < 2 || b.nj < 2 || b.nodeIds.size() != want) {
            out.push_back(t);
            continue;
        }
        const SideWalk sw = sideWalk(b, ws.side);
        const int n = sw.n, t0 = sw.t0, t1 = sw.t1;
        auto pos = [&](int k, int tt) { return sideNode(b, mesh.nodes, sw, k, tt); };

        // THE REQUEST, station by station, and it is the RULER'S BLEND. See the
        // header: aiming the control at any other interpolation of the two
        // declared corner heights would drive the mesh at one number while the
        // gate measured it against another.
        t.requested.assign(static_cast<size_t>(n), 0.0);
        for (int k = 0; k < n; ++k) {
            const double u = (n > 1) ? static_cast<double>(k) / (n - 1) : 0.0;
            t.requested[static_cast<size_t>(k)] =
                (1.0 - u) * ws.requestedLo + u * ws.requestedHi;
        }

        // THE INWARD NORMALS, which need an interior grid line to orient against
        // and a neighbour station to take a tangent from — so a side thinner than
        // three nodes either way stays unusable while its `requested` above is
        // still published, because the residual measurement needs only that half.
        if (b.ni >= 3 && b.nj >= 3) {
            t.normal.assign(static_cast<size_t>(n), Point2D{0.0, 0.0});
            bool any = false;
            for (int k = 0; k < n; ++k) {
                const auto row = [&](int kk) { return pos(kk, t0); };
                const Point2D nrm = wallTangent(k, n, row).leftNormal().normalized();
                if (nrm.lengthSq() <= 0.0) continue;
                // INWARD IS READ OFF THE MESH, not off the block's winding: a frame
                // may be turned a quarter turn (the shipped H-grid turns one), so
                // which side of the tangent the interior lies on is not a constant.
                const Point2D inward = pos(k, t1) - pos(k, t0);
                t.normal[static_cast<size_t>(k)] =
                    (nrm.dot(inward) < 0.0) ? nrm * -1.0 : nrm;
                if (t.requested[static_cast<size_t>(k)] > 0.0) any = true;
            }
            t.usable = any;
        }
        out.push_back(t);
    }
    return out;
}

hybmesh::MbWallResidual hybmesh::mbWallResidual(const MbResult& mesh,
                                                const MbWallTarget& t) {
    MbWallResidual out;
    if (t.block < 0 || static_cast<size_t>(t.block) >= mesh.blocks.size()) return out;
    const MbBlock& b = mesh.blocks[static_cast<size_t>(t.block)];
    const size_t want = static_cast<size_t>(b.ni) * static_cast<size_t>(b.nj);
    if (b.ni < 2 || b.nj < 2 || b.nodeIds.size() != want) return out;
    const SideWalk sw = sideWalk(b, t.side);
    if (!sw.ok) return out;
    const int n = sw.n, t0 = sw.t0, t1 = sw.t1;
    if (static_cast<int>(t.requested.size()) != n) return out;
    auto pos = [&](int k, int tt) { return sideNode(b, mesh.nodes, sw, k, tt); };

    bool askedHeight = false, gotAngle = false;
    double worstH = 0.0, worstA = 0.0;
    for (int k = 0; k < n; ++k) {
        const Point2D step = pos(k, t1) - pos(k, t0);
        const double got = step.length();
        // THE HEIGHT. Same arithmetic `measureMbQuality` reports, on the same
        // blend, measured on the produced nodes and not predicted from the source
        // term that was applied. The step off the wall is ONE straight segment, so
        // its chord IS its arc length here and the measure of the achievement is
        // the measure of the request — which is the lesson the edge-distribution
        // warning learned the hard way, stated rather than assumed.
        const double req = t.requested[static_cast<size_t>(k)];
        if (req > 0.0) {
            askedHeight = true;
            worstH = std::max(worstH, std::fabs(got - req) / req);
        }
        // THE ANGLE, the other half of the same target vector: how far the grid
        // line leaving the wall is from perpendicular to it. Measured against the
        // wall row's own tangent, which is the same corner angle
        // `measureMbQuality` counts into its non-orthogonality figure — restricted
        // here to the corners that sit ON a declared wall.
        if (b.ni >= 3 && b.nj >= 3 && got > 0.0) {
            const auto row = [&](int kk) { return pos(kk, t0); };
            const Point2D tang = wallTangent(k, n, row);
            const double tl = tang.length();
            if (tl > 0.0) {
                double c = tang.dot(step) / (tl * got);
                c = std::max(-1.0, std::min(1.0, c));
                const double deg = std::acos(c) * 180.0 / 3.14159265358979323846;
                worstA = std::max(worstA, std::fabs(90.0 - deg));
                gotAngle = true;
            }
        }
    }
    if (askedHeight) out.worstHeightRel = worstH;
    if (gotAngle) out.worstAngleDeg = worstA;
    return out;
}
