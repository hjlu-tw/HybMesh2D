#include "MbCurve.hpp"

#include <algorithm>
#include <cmath>

namespace {

constexpr double kPi = 3.14159265358979323846;
constexpr double kTwoPi = 2.0 * kPi;

// THE QUADRATURE. An 8-point Gauss-Legendre rule on panels no wider than
// `kPanelWidth`.
//
// Gauss-Legendre rather than Simpson because the integrand — sqrt(a^2 sin^2 t +
// b^2 cos^2 t) — is analytic and periodic, so a fixed-order rule on bounded panels
// converges geometrically rather than to a stated tolerance. And because an
// 8-point rule integrates a polynomial of degree 15 exactly, a CONSTANT integrand
// (which is what a circle's speed is) comes out to the last bit: that is what lets
// the circle fall out of the general path instead of needing a branch beside it.
//
// The width is the accuracy knob and it is stated rather than tuned: at pi/16 a
// panel sees at most 11.25 degrees of a curve whose speed varies by at most the
// axis ratio over a quarter turn, which on the 2:1 ellipse this feature was built
// for leaves a relative error below 1e-15 — checked in tests/cpp/test_mb_curve.cpp
// against a halved panel width, which is the only honest way to assert a
// quadrature's accuracy without a second implementation of it.
constexpr double kPanelWidth = kPi / 16.0;

const double kGlX[4] = {0.1834346424956498, 0.5255324099163290,
                        0.7966664774136267, 0.9602898564975363};
const double kGlW[4] = {0.3626837833783620, 0.3137066458778873,
                        0.2223810344533745, 0.1012285362903763};

}  // namespace

namespace hybmesh {

// See the header: relative to the curve's own size, because both quantities here
// are lengths at the same scale.
const double MB_CURVE_ON_TOL = 1e-9;

const char* mbCurveKindName(MbCurveKind k) {
    switch (k) {
        case MB_CURVE_ARC:     return "arc";
        case MB_CURVE_ELLIPSE: return "ellipse";
    }
    return "?";
}

Point2D mbCurveAt(const MbCurve& c, double t) {
    const double lx = c.a * std::cos(t);
    const double ly = c.b * std::sin(t);
    const double cr = std::cos(c.rot), sr = std::sin(c.rot);
    return Point2D{c.cx + lx * cr - ly * sr, c.cy + lx * sr + ly * cr};
}

// The first derivative. Private, because a caller outside this file that wants a
// tangent wants a NORMALISED one and would have to remember that this is not.
static Point2D curveD1(const MbCurve& c, double t) {
    const double lx = -c.a * std::sin(t);
    const double ly = c.b * std::cos(t);
    const double cr = std::cos(c.rot), sr = std::sin(c.rot);
    return Point2D{lx * cr - ly * sr, lx * sr + ly * cr};
}

// The second derivative, which is just the inward radius vector: P''(t) =
// -(P(t) - C). Written out rather than computed from `mbCurveAt` so that the
// projection's Newton step reads as the formula it is.
static Point2D curveD2(const MbCurve& c, double t) {
    const double lx = -c.a * std::cos(t);
    const double ly = -c.b * std::sin(t);
    const double cr = std::cos(c.rot), sr = std::sin(c.rot);
    return Point2D{lx * cr - ly * sr, lx * sr + ly * cr};
}

double mbCurveSpeed(const MbCurve& c, double t) {
    const double s = std::sin(t), co = std::cos(t);
    return std::sqrt(c.a * c.a * s * s + c.b * c.b * co * co);
}

double mbCurveParam(const MbCurve& c, const Point2D& p) {
    const double cr = std::cos(c.rot), sr = std::sin(c.rot);
    const double dx = p.x - c.cx, dy = p.y - c.cy;
    // R(-rot) * (p - C)
    const double qx = dx * cr + dy * sr;
    const double qy = -dx * sr + dy * cr;
    const double ax = (c.a > 0.0) ? (qx / c.a) : qx;
    const double by = (c.b > 0.0) ? (qy / c.b) : qy;
    return std::atan2(by, ax);
}

double mbCurveArc(const MbCurve& c, double from, double to) {
    if (from == to) return 0.0;
    const double sign = (to > from) ? 1.0 : -1.0;
    const double lo = std::min(from, to), hi = std::max(from, to);
    const double width = hi - lo;
    int panels = static_cast<int>(std::ceil(width / kPanelWidth));
    if (panels < 1) panels = 1;
    const double h = width / panels;
    double total = 0.0;
    for (int k = 0; k < panels; ++k) {
        const double aK = lo + k * h;
        const double mid = aK + 0.5 * h;
        const double half = 0.5 * h;
        double acc = 0.0;
        for (int g = 0; g < 4; ++g) {
            acc += kGlW[g] * (mbCurveSpeed(c, mid - half * kGlX[g])
                              + mbCurveSpeed(c, mid + half * kGlX[g]));
        }
        total += acc * half;
    }
    return sign * total;
}

double mbCurveLength(const MbCurve& c) {
    if (!c.spanned) return 0.0;
    return std::fabs(mbCurveArc(c, c.t0, c.t1));
}

Point2D mbCurveAtArc(const MbCurve& c, double s) {
    if (!c.spanned) return mbCurveAt(c, c.t0);
    const double span = c.t1 - c.t0;
    const double dir = (span >= 0.0) ? 1.0 : -1.0;
    const double uMax = std::fabs(span);
    const double L = mbCurveLength(c);
    // TOTAL, not merely guarded: an `s` off the end is CLAMPED to the span's own
    // end rather than extrapolated past it. Extrapolating a periodic parameter
    // wraps silently onto the other side of the curve, which is a node placed on
    // the far side of a ring with no symptom but a folded cell.
    if (!(L > 0.0) || !(s > 0.0)) return mbCurveAt(c, c.t0);
    if (s >= L) return mbCurveAt(c, c.t1);

    // Newton against the EXACT speed, bracketed by bisection so a bad step cannot
    // leave the span. `S(u)` is strictly increasing with derivative `speed > 0`,
    // so the bracket only ever tightens.
    double lo = 0.0, hi = uMax;
    double u = uMax * (s / L);            // the uniform-speed guess; exact on a circle
    for (int it = 0; it < 60; ++it) {
        const double theta = c.t0 + dir * u;
        const double Su = std::fabs(mbCurveArc(c, c.t0, theta));
        const double f = Su - s;
        if (f > 0.0) hi = u; else lo = u;
        const double sp = mbCurveSpeed(c, theta);
        if (!(sp > 0.0)) break;
        double step = -f / sp;
        double next = u + step;
        if (!(next > lo && next < hi)) next = 0.5 * (lo + hi);
        if (std::fabs(next - u) <= 1e-16 * std::max(1.0, uMax)) { u = next; break; }
        u = next;
    }
    return mbCurveAt(c, c.t0 + dir * u);
}

Point2D mbCurveProject(const MbCurve& c, const Point2D& p, bool clampToSpan,
                       double* tOut) {
    // Minimise |P(t) - p|^2: f(t) = (P(t) - p) . P'(t) = 0, by Newton from the
    // inverse map — which IS the answer on a circle, where the radius through `p`
    // meets the curve at right angles to the tangent, so `f` is already 0 there and
    // the iteration does no work.
    double t = mbCurveParam(c, p);
    for (int it = 0; it < 50; ++it) {
        const Point2D d = mbCurveAt(c, t) - p;
        const Point2D d1 = curveD1(c, t);
        const Point2D d2 = curveD2(c, t);
        const double f = d.dot(d1);
        const double fp = d1.lengthSq() + d.dot(d2);
        if (!(std::fabs(fp) > 0.0)) break;
        const double step = -f / fp;
        t += step;
        if (std::fabs(step) <= 1e-15) break;
    }
    // A SCAN BESIDE THE ITERATION, and it is not belt and braces. `f` has up to
    // four roots on an ellipse — two minima and two maxima — and Newton from the
    // inverse map converges to the nearest one, which for a point inside a slender
    // ellipse near the centre is the WRONG extremum. The scan is what makes this
    // function total: whichever of the two is closer wins, so the answer is never
    // worse than a coarse sample of the curve.
    double best = t;
    double bestD2 = (mbCurveAt(c, t) - p).lengthSq();
    for (int k = 0; k < 128; ++k) {
        const double tk = -kPi + kTwoPi * k / 128.0;
        const double dk = (mbCurveAt(c, tk) - p).lengthSq();
        if (dk < bestD2) { bestD2 = dk; best = tk; }
    }
    if (best != t) {
        // Polish the scan's winner the same way, so the answer is a root and not a
        // sample of one.
        double u = best;
        for (int it = 0; it < 50; ++it) {
            const Point2D d = mbCurveAt(c, u) - p;
            const Point2D d1 = curveD1(c, u);
            const Point2D d2 = curveD2(c, u);
            const double f = d.dot(d1);
            const double fp = d1.lengthSq() + d.dot(d2);
            if (!(std::fabs(fp) > 0.0)) break;
            const double step = -f / fp;
            u += step;
            if (std::fabs(step) <= 1e-15) break;
        }
        if ((mbCurveAt(c, u) - p).lengthSq() < (mbCurveAt(c, t) - p).lengthSq()) t = u;
    }

    if (clampToSpan && c.spanned) {
        // Clamp IN THE SPAN's OWN DIRECTION, by arc length from `t0`. Comparing the
        // raw parameter would be wrong across the +pi/-pi seam, which every O-grid
        // in this repo has a span crossing.
        const double span = c.t1 - c.t0;
        const double dir = (span >= 0.0) ? 1.0 : -1.0;
        double u = dir * (t - c.t0);
        while (u < 0.0) u += kTwoPi;
        while (u > kTwoPi) u -= kTwoPi;
        const double uMax = std::fabs(span);
        if (u > uMax) {
            // Outside the span: the nearer END, measured the way the span is.
            u = (u - uMax < kTwoPi - u) ? uMax : 0.0;
        }
        t = c.t0 + dir * u;
    }
    if (tOut) *tOut = t;
    return mbCurveAt(c, t);
}

double mbCurveDistance(const MbCurve& c, const Point2D& p) {
    return (mbCurveProject(c, p, false) - p).length();
}

MbCurveSpanResult mbCurveResolveSpan(MbCurve& c, const Point2D& pa, const Point2D& pb) {
    MbCurveSpanResult out;
    if (!(c.a > 0.0) || !(c.b > 0.0)) {
        out.status = MB_CURVE_SPAN_DEGENERATE;
        return out;
    }
    const double tol = MB_CURVE_ON_TOL * std::max(c.a, c.b);
    out.tolerance = tol;
    const Point2D ends[2] = {pa, pb};
    for (int k = 0; k < 2; ++k) {
        double tk = 0.0;
        const Point2D near = mbCurveProject(c, ends[k], false, &tk);
        const double d = (near - ends[k]).length();
        if (d > tol) {
            out.status = MB_CURVE_SPAN_OFF_CURVE;
            out.corner = k;
            out.distance = d;
            out.nearest = near;
            return out;
        }
    }
    const double ta = mbCurveParam(c, pa);
    const double tb = mbCurveParam(c, pb);
    double delta = tb - ta;
    if (c.ccw) {
        while (delta <= 0.0) delta += kTwoPi;
        while (delta > kTwoPi) delta -= kTwoPi;
    } else {
        while (delta >= 0.0) delta -= kTwoPi;
        while (delta < -kTwoPi) delta += kTwoPi;
    }
    const double swept = std::fabs(delta);
    // A SWEEP OF NOTHING AND A SWEEP OF EVERYTHING ARE THE SAME REFUSAL. Two
    // distinct corners at one position wrap to a full turn under the normalisation
    // above, and an edge that is the whole closed curve has its two ends at one
    // node — which is an edge with no length however it is spelled.
    if (swept < 1e-12 || std::fabs(kTwoPi - swept) < 1e-12) {
        out.status = MB_CURVE_SPAN_SAME_POINT;
        return out;
    }
    c.t0 = ta;
    c.t1 = ta + delta;
    c.spanned = true;
    out.sweptRad = swept;
    return out;
}

std::vector<Point2D> mbCurveSample(const MbCurve& c, int n) {
    std::vector<Point2D> pts;
    if (!c.spanned || n < 2) return pts;
    const double L = mbCurveLength(c);
    pts.reserve(static_cast<size_t>(n));
    for (int k = 0; k < n; ++k) {
        if (k == 0)          { pts.push_back(mbCurveAt(c, c.t0)); continue; }
        if (k == n - 1)      { pts.push_back(mbCurveAt(c, c.t1)); continue; }
        pts.push_back(mbCurveAtArc(c, L * k / (n - 1)));
    }
    return pts;
}

}  // namespace hybmesh
