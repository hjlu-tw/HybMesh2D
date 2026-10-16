// The analytic curve a topology edge can BE (issue #175).
//
// Links `hybmesh_pure` alone: this file builds no mesh, parses no document and
// never names `MbResult`. That is the property the module claims and the linker is
// what checks it.
//
// WHAT THIS FILE CAN AND CANNOT ASSERT. A quadrature's accuracy cannot be asserted
// against its own output, so every numeric claim below is measured against
// SOMETHING ELSE: a closed form (the circle), a halved panel width (the ellipse's
// convergence), an independent series (Ramanujan's perimeter), or a property that
// does not need the number at all (monotonicity, the ends landing on the corners).
// A check that re-derives the figure the same way the code does is the shape
// `docs/agents/rule-file-style.md` and this repo's own memory call a check true by
// construction, and there is none below.
//
// HAND INJECTIONS, 2026-10-16. A C++ test cannot mutate the implementation it
// linked against, so these were run by editing src/MbCurve.cpp, building and
// reading the EXIT CODE (not only the FAIL-line count), then reverting. Each line
// records where the injection landed FIRST, because seven injections that all
// report the same count are seven injections that may all be hitting one cascade:
//   1. `mbCurveParam` without the /a and /b un-scaling   -> exit 1, 26 FAIL, first 3a
//   2. `kPanelWidth` widened 1600x (one panel per span)  -> exit 1,  5 FAIL, first 2d
//   3. `mbCurveAtArc` returning the uniform-speed guess  -> exit 1, 19 FAIL, first 4d
//   4. `mbCurveResolveSpan` not normalising `delta` (cw) -> exit 1,  2 FAIL, first 5b
//   5. the full-turn clause of the SAME_POINT refusal    -> exit 1,  1 FAIL, first 6c
//   6. `mbCurveProject`'s 128-point scan deleted         -> exit 1,  1 FAIL, first 7c
//   7. the `clampToSpan` branch made inert               -> exit 1,  1 FAIL, first 7d
// Control after reverting each: exit 0, PASS.
//
// ONE OF THEM CAME BACK INERT FIRST TIME AND THE FIXTURE WAS WRONG, NOT THE RULE.
// Injection 6's original fixture was a point near a slender ellipse's centre and
// OFF its major axis, where Newton from the inverse map finds the right minimum
// anyway: the scan's deletion changed nothing and the check passed. The case that
// actually needs it is a point ON the major axis inside the evolute's cusp, where
// the seed is an exact critical point of the wrong kind. See check 7c.
#include "MbCurve.hpp"
#include "check.hpp"

#include <algorithm>
#include <cmath>
#include <vector>

using namespace hybmesh;

namespace {

constexpr double kPi = 3.14159265358979323846;

MbCurve circle(double r, bool ccw = true) {
    MbCurve c;
    c.kind = MB_CURVE_ARC;
    c.cx = 0.0; c.cy = 0.0;
    c.a = r; c.b = r;
    c.ccw = ccw;
    return c;
}

MbCurve ellipse(double a, double b, double rotDeg = 0.0, bool ccw = true) {
    MbCurve c;
    c.kind = MB_CURVE_ELLIPSE;
    c.cx = 0.0; c.cy = 0.0;
    c.a = a; c.b = b;
    c.rot = rotDeg * kPi / 180.0;
    c.ccw = ccw;
    return c;
}

// Ramanujan's second approximation to an ellipse's perimeter. An INDEPENDENT
// number: a closed-form series in a and b with no integral in it, so it cannot
// agree with the quadrature by sharing its method.
//
// ITS OWN ERROR IS THE BAR, and it is NOT small at every axis ratio. Measured
// 2026-10-16 against a 2e6-panel midpoint integration: 4.6e-10 relative at 2:1,
// 2.5e-07 at 4:1 and 1.2e-05 at 10:1. So this reference is used at 2:1 ONLY, at a
// bar of 1e-8 — asserting it at 10:1 would be asserting the approximation rather
// than the quadrature, and the first run of this file did exactly that and went
// red on a correct implementation.
double ramanujanPerimeter(double a, double b) {
    const double h = (a - b) * (a - b) / ((a + b) * (a + b));
    return kPi * (a + b) * (1.0 + 3.0 * h / (10.0 + std::sqrt(4.0 - 3.0 * h)));
}

// A COMPOSITE MIDPOINT INTEGRATION of the same speed, at 4e6 panels. A different
// RULE, not a second call of the same one: midpoint is open and second order where
// the module's is closed and eighth, so the two share no node, no weight and no
// panel boundary, and a defect in either shows as a disagreement. Its own
// truncation error is O(h^2 f'') ~ 1e-12 absolute here, which is what lets the bar
// below be 1e-10 relative at every ratio.
double midpointPerimeter(double a, double b) {
    const int n = 4000000;
    const double h = 2.0 * kPi / n;
    double total = 0.0;
    for (int k = 0; k < n; ++k) {
        const double t = (k + 0.5) * h;
        const double s = std::sin(t), c = std::cos(t);
        total += std::sqrt(a * a * s * s + b * b * c * c);
    }
    return total * h;
}

}  // namespace

int main() {
    // ── 1. The parametric form, and the circle as the a == b case ──────────
    {
        MbCurve c = circle(2.0);
        const Point2D p = mbCurveAt(c, 0.0);
        CHECK_NEAR(p.x, 2.0, 1e-15, "1a: t=0 is (r, 0)");
        CHECK_NEAR(p.y, 0.0, 1e-15, "1a: t=0 is (r, 0)");
        const Point2D q = mbCurveAt(c, kPi / 2);
        CHECK_NEAR(q.x, 0.0, 1e-15, "1b: t=pi/2 is (0, r)");
        CHECK_NEAR(q.y, 2.0, 1e-15, "1b: t=pi/2 is (0, r)");
        CHECK_NEAR(mbCurveSpeed(c, 0.37), 2.0, 1e-15,
                   "1c: a circle's speed is its radius, at every t");
        CHECK_NEAR(mbCurveSpeed(c, 2.91), 2.0, 1e-15,
                   "1c: a circle's speed is its radius, at every t");
    }

    // An ellipse's centre is NOT on it, and a rotation moves the curve and not its
    // shape: the point at t on a rotated ellipse is the rotation of the point at t.
    {
        MbCurve c = ellipse(2.0, 1.0, 90.0);
        const Point2D p = mbCurveAt(c, 0.0);
        CHECK_NEAR(p.x, 0.0, 1e-15, "1d: a 90-degree rotation puts the a-axis on y");
        CHECK_NEAR(p.y, 2.0, 1e-15, "1d: a 90-degree rotation puts the a-axis on y");
    }

    // ── 2. Arc length: the circle's closed form, from the general path ──────
    //
    // The quadrature is handed a CONSTANT integrand here, which an 8-point
    // Gauss-Legendre rule integrates exactly. If this is not exact to the last few
    // bits, the general path is not reproducing the closed form and the module's
    // "one parametric form, not two" claim is false.
    {
        MbCurve c = circle(3.0);
        CHECK_NEAR(mbCurveArc(c, 0.0, kPi / 2), 3.0 * kPi / 2, 1e-14,
                   "2a: a quarter of radius 3 is 3*pi/2, from the general quadrature");
        CHECK_NEAR(mbCurveArc(c, 0.0, 2 * kPi), 6.0 * kPi, 1e-13,
                   "2b: the full turn is 2*pi*r");
        CHECK_NEAR(mbCurveArc(c, 1.0, 0.2), -mbCurveArc(c, 0.2, 1.0), 1e-15,
                   "2c: arc length is SIGNED and antisymmetric");
    }

    // The ellipse, against TWO independent references — one closed form and one
    // quadrature of a different rule — because neither alone covers the range.
    {
        MbCurve c2 = ellipse(2.0, 1.0);
        const double ram = ramanujanPerimeter(2.0, 1.0);
        CHECK(std::fabs(mbCurveArc(c2, 0.0, 2 * kPi) - ram) <= 1e-8 * ram,
              "2d: at 2:1 the perimeter agrees with Ramanujan's closed form");

        for (double ratio : {2.0, 4.0, 10.0}) {
            MbCurve c = ellipse(ratio, 1.0);
            const double quad = mbCurveArc(c, 0.0, 2 * kPi);
            const double mid = midpointPerimeter(ratio, 1.0);
            CHECK(std::fabs(quad - mid) <= 1e-10 * mid,
                  "2d: ...and agrees with a midpoint rule at every axis ratio");
        }
    }

    // CONVERGENCE, not accuracy: a quarter of a 2:1 ellipse computed as one span
    // and as the sum of eight sub-spans must agree. A quadrature whose panels were
    // too wide would disagree here, and this does not need a reference value.
    {
        MbCurve c = ellipse(2.0, 1.0);
        const double whole = mbCurveArc(c, 0.0, kPi / 2);
        double parts = 0.0;
        for (int k = 0; k < 8; ++k)
            parts += mbCurveArc(c, kPi / 2 * k / 8.0, kPi / 2 * (k + 1) / 8.0);
        CHECK_NEAR(whole, parts, 1e-14,
                   "2e: the panelling is fine enough that splitting the span changes nothing");
    }

    // ── 3. The inverse map ─────────────────────────────────────────────────
    {
        MbCurve c = ellipse(2.0, 0.5, 30.0);
        for (double t : {0.0, 0.7, 2.2, -1.9, 3.0}) {
            const Point2D p = mbCurveAt(c, t);
            const double back = mbCurveParam(c, p);
            CHECK_NEAR(std::sin(back), std::sin(t), 1e-12,
                       "3a: the inverse map round-trips through the point");
            CHECK_NEAR(std::cos(back), std::cos(t), 1e-12,
                       "3a: the inverse map round-trips through the point");
        }
    }

    // ── 4. Arc-length placement ────────────────────────────────────────────
    //
    // On a circle the answer is a closed form the module never uses: the point at
    // arc length s from t0 is at angle t0 + s/r.
    {
        MbCurve c = circle(2.5);
        MbCurveSpanResult sr = mbCurveResolveSpan(c, Point2D{2.5, 0.0}, Point2D{0.0, 2.5});
        CHECK(sr.status == MB_CURVE_SPAN_OK, "4a: a quarter span resolves");
        const double L = mbCurveLength(c);
        CHECK_NEAR(L, 2.5 * kPi / 2, 1e-13, "4a: the quarter's length");
        for (double frac : {0.0, 0.25, 0.5, 0.75, 1.0}) {
            const Point2D got = mbCurveAtArc(c, L * frac);
            const double wantT = L * frac / 2.5;
            CHECK_NEAR(got.x, 2.5 * std::cos(wantT), 1e-12,
                       "4b: placement on a circle matches the closed form");
            CHECK_NEAR(got.y, 2.5 * std::sin(wantT), 1e-12,
                       "4b: placement on a circle matches the closed form");
        }
    }

    // On an ellipse there is no closed form, so the property checked is the
    // DEFINING one: the arc length from the span's start to the returned point is
    // the arc length asked for. That is not circular — the placement is a Newton
    // SOLVE and this measures its residual, which an unconverged solve fails.
    {
        MbCurve c = ellipse(2.0, 0.5);
        MbCurveSpanResult sr = mbCurveResolveSpan(c, Point2D{2.0, 0.0}, Point2D{-2.0, 0.0});
        CHECK(sr.status == MB_CURVE_SPAN_OK, "4c: a half span on an ellipse resolves");
        const double L = mbCurveLength(c);
        double prev = -1.0;
        for (int k = 0; k <= 20; ++k) {
            const double s = L * k / 20.0;
            const Point2D got = mbCurveAtArc(c, s);
            const double back = std::fabs(mbCurveArc(c, c.t0, mbCurveParam(c, got)));
            CHECK(std::fabs(back - s) <= 1e-10 * std::max(1.0, L),
                  "4d: the point at arc length s really is at arc length s");
            // ...and the placement is monotone, which a Newton that jumped to
            // another root would break while still landing on the curve.
            const double u = mbCurveParam(c, got);
            CHECK(u > prev - 1e-12, "4e: placement advances monotonically along the span");
            prev = u;
        }
    }

    // THE ENDS ARE THE SPAN's ENDS, not a value the law rounded to. An `s` past the
    // end is clamped rather than wrapped onto the far side of the curve.
    {
        MbCurve c = circle(1.0);
        mbCurveResolveSpan(c, Point2D{1.0, 0.0}, Point2D{0.0, 1.0});
        const double L = mbCurveLength(c);
        const Point2D over = mbCurveAtArc(c, L * 3.0);
        CHECK_NEAR(over.x, 0.0, 1e-14, "4f: past the end clamps to the end, never wraps");
        CHECK_NEAR(over.y, 1.0, 1e-14, "4f: past the end clamps to the end, never wraps");
        const Point2D under = mbCurveAtArc(c, -5.0);
        CHECK_NEAR(under.x, 1.0, 1e-14, "4f: before the start clamps to the start");
    }

    // ── 5. The span is derived from the corners, in the sweep's direction ──
    {
        MbCurve ccwC = circle(1.0, true);
        MbCurveSpanResult a = mbCurveResolveSpan(ccwC, Point2D{1.0, 0.0}, Point2D{0.0, 1.0});
        CHECK(a.status == MB_CURVE_SPAN_OK, "5a: ccw from (1,0) to (0,1) resolves");
        CHECK_NEAR(a.sweptRad, kPi / 2, 1e-12, "5a: ...and sweeps a quarter turn");

        MbCurve cwC = circle(1.0, false);
        MbCurveSpanResult b = mbCurveResolveSpan(cwC, Point2D{1.0, 0.0}, Point2D{0.0, 1.0});
        CHECK(b.status == MB_CURVE_SPAN_OK, "5b: the SAME two corners resolve cw as well");
        CHECK_NEAR(b.sweptRad, 3 * kPi / 2, 1e-12,
                   "5b: ...and that is the OTHER arc, three quarters of the turn");
        // The two spans are different curves through the same two points — which is
        // exactly why `sweep` exists and why the long way round is warned about one
        // level up.
        const Point2D mid1 = mbCurveAtArc(ccwC, mbCurveLength(ccwC) * 0.5);
        const Point2D mid2 = mbCurveAtArc(cwC, mbCurveLength(cwC) * 0.5);
        CHECK((mid1 - mid2).length() > 1.0,
              "5c: the two sweeps run on opposite sides of the circle");
    }

    // A span crossing the +pi / -pi seam, which every O-grid quadrant in this repo
    // has one of.
    {
        MbCurve c = circle(1.0, true);
        MbCurveSpanResult r = mbCurveResolveSpan(c, Point2D{-1.0, 0.0}, Point2D{0.0, -1.0});
        CHECK(r.status == MB_CURVE_SPAN_OK, "5d: a span across the parameter seam resolves");
        CHECK_NEAR(r.sweptRad, kPi / 2, 1e-12, "5d: ...and is still a quarter turn");
        const Point2D mid = mbCurveAtArc(c, mbCurveLength(c) * 0.5);
        CHECK(mid.x < 0.0 && mid.y < 0.0,
              "5e: ...and its midpoint is in the third quadrant, not the first");
    }

    // ── 6. The three refusals ──────────────────────────────────────────────
    {
        MbCurve bad = circle(0.0);
        CHECK(mbCurveResolveSpan(bad, Point2D{0, 0}, Point2D{1, 0}).status
                  == MB_CURVE_SPAN_DEGENERATE,
              "6a: a zero radius is refused, never meshed as a point");

        MbCurve c = circle(1.0);
        MbCurveSpanResult off = mbCurveResolveSpan(c, Point2D{1.0, 0.0}, Point2D{0.0, 1.2});
        CHECK(off.status == MB_CURVE_SPAN_OFF_CURVE, "6b: a corner off the curve is refused");
        CHECK(off.corner == 1, "6b: ...and the refusal names WHICH corner");
        CHECK_NEAR(off.distance, 0.2, 1e-12, "6b: ...and by how far");
        CHECK_NEAR(off.nearest.y, 1.0, 1e-12, "6b: ...and where it should have been");
        CHECK(off.tolerance > 0.0, "6b: ...and the bar it had to clear");

        MbCurve same = circle(1.0);
        CHECK(mbCurveResolveSpan(same, Point2D{1.0, 0.0}, Point2D{1.0, 0.0}).status
                  == MB_CURVE_SPAN_SAME_POINT,
              "6c: two corners at one point is a span of the WHOLE curve and is refused");
    }

    // The tolerance is RELATIVE: the same absolute offset passes on a large curve
    // and fails on a small one, which is the whole content of "relative to the
    // curve's own size".
    {
        MbCurve big = circle(1.0e6);
        CHECK(mbCurveResolveSpan(big, Point2D{1.0e6, 0.0}, Point2D{0.0, 1.0e6 + 1e-4}).status
                  == MB_CURVE_SPAN_OK,
              "6d: 1e-4 off a 1e6 curve is typing noise and passes");
        MbCurve small = circle(1.0e-3);
        CHECK(mbCurveResolveSpan(small, Point2D{1.0e-3, 0.0},
                                 Point2D{0.0, 1.0e-3 + 1e-4}).status
                  == MB_CURVE_SPAN_OFF_CURVE,
              "6d: the SAME 1e-4 off a 1e-3 curve is a different corner and is refused");
    }

    // ── 7. Projection ──────────────────────────────────────────────────────
    {
        MbCurve c = circle(2.0);
        double t = 0.0;
        const Point2D p = mbCurveProject(c, Point2D{6.0, 0.0}, false, &t);
        CHECK_NEAR(p.x, 2.0, 1e-14, "7a: a circle projects along its own radius");
        CHECK_NEAR(mbCurveDistance(c, Point2D{6.0, 0.0}), 4.0, 1e-13,
                   "7a: ...and the distance is the closed form");
    }
    {
        // ON an ellipse, the projection of a point ON the curve is itself.
        MbCurve c = ellipse(3.0, 1.0, 20.0);
        for (double t : {0.3, 1.7, -2.4}) {
            const Point2D on = mbCurveAt(c, t);
            CHECK(mbCurveDistance(c, on) <= 1e-12,
                  "7b: a point on the ellipse is at distance zero from it");
        }
    }
    {
        // THE CASE THE SCAN EXISTS FOR, and it is not hypothetical: a point ON a
        // slender ellipse's MAJOR AXIS, inside the evolute's cusp at
        // x = (a^2 - b^2)/a = 9.9. The inverse map seeds Newton at t = 0, where
        // (P - p) is parallel to the axis and P' is perpendicular to it, so
        // f(0) = 0 EXACTLY and Newton stops on the first step — on a critical point
        // that is not the minimum. The nearest point is on the flank at about
        // t = 59.6 degrees and five times nearer. Measured 2026-10-16: without the
        // scan this returns (10, 0) at distance 5.0 instead of 0.862.
        MbCurve c = ellipse(10.0, 1.0);
        const Point2D p{5.0, 0.0};
        double t = 0.0;
        const Point2D got = mbCurveProject(c, p, false, &t);
        const double d = (got - p).length();
        double brute = 1e30;
        for (int k = 0; k < 200000; ++k) {
            const double tk = -kPi + 2 * kPi * k / 200000.0;
            brute = std::min(brute, (mbCurveAt(c, tk) - p).length());
        }
        CHECK(d <= brute + 1e-9,
              "7c: the projection is the GLOBAL nearest point, not the nearest root");
    }
    {
        // Clamping to the span, across the seam.
        MbCurve c = circle(1.0, true);
        mbCurveResolveSpan(c, Point2D{1.0, 0.0}, Point2D{0.0, 1.0});   // the first quadrant
        double t = 0.0;
        const Point2D out = mbCurveProject(c, Point2D{-5.0, -5.0}, true, &t);
        const double dStart = (out - Point2D{1.0, 0.0}).length();
        const double dEnd = (out - Point2D{0.0, 1.0}).length();
        CHECK(std::min(dStart, dEnd) <= 1e-12,
              "7d: a point outside the span clamps onto one of the span's own ends");
        const Point2D in = mbCurveProject(c, Point2D{1.0, 1.0}, true, &t);
        CHECK_NEAR(in.x, std::sqrt(0.5), 1e-12, "7e: a point inside the span is not clamped");
        CHECK_NEAR(in.y, std::sqrt(0.5), 1e-12, "7e: a point inside the span is not clamped");
    }

    // ── 8. Sampling ────────────────────────────────────────────────────────
    {
        MbCurve c = ellipse(2.0, 1.0);
        mbCurveResolveSpan(c, Point2D{2.0, 0.0}, Point2D{0.0, 1.0});
        const std::vector<Point2D> pts = mbCurveSample(c, 17);
        CHECK(pts.size() == 17, "8a: the sample has the count asked for");
        CHECK_NEAR(pts.front().x, 2.0, 1e-14, "8b: ...and starts on the span's start");
        CHECK_NEAR(pts.back().y, 1.0, 1e-14, "8b: ...and ends on the span's end");
        // EQUAL arc length, which a sample even in the PARAMETER would fail on an
        // ellipse — the 2:1 case's chords would run 2:1 apart.
        double shortest = 1e30, longest = 0.0;
        for (size_t k = 1; k < pts.size(); ++k) {
            const double d = (pts[k] - pts[k - 1]).length();
            shortest = std::min(shortest, d);
            longest = std::max(longest, d);
        }
        CHECK(longest / shortest < 1.01,
              "8c: the sample is even in ARC LENGTH, not in the parameter");
        // Every sample is ON the curve.
        for (const Point2D& p : pts)
            CHECK(mbCurveDistance(c, p) <= 1e-12, "8d: every sampled point is on the curve");
    }

    return hybmesh::test::report("test_mb_curve");
}
