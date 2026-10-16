#ifndef MBCURVE_HPP
#define MBCURVE_HPP

#include "GeomUtils.hpp"

#include <string>
#include <vector>

// AN ANALYTIC CURVE A TOPOLOGY EDGE CAN BE, declared in the document rather than
// pointed at in a geometry file (issue #175).
//
// WHY THIS EXISTS. `binding` (#52) and `follows` (#151) both answer "where does
// this edge lie" with `{geom, seg}` — a drawn geometry, a `.meta` sidecar, a
// segment id and a STORED POLYLINE. That is the right answer when the curve is
// something the user drew and the mesh must agree with; it is a poor one when the
// curve is a ring seam nobody will ever look at, which is why
// `services/topology_tworing.py` refuses to generate one and sends the user to
// `CAD ▸ Offset Geometry…`, and why #153's middle ring had to be faceted at 120
// per quarter to satisfy two divisibility rules at once. This module is the third
// answer: the edge IS the curve, and there is no file.
//
// WHAT IT BUYS BEYOND CONVENIENCE. A polyline is an approximation with a
// measurable residue — the named blind spot "Nothing projects onto an ANALYTIC
// curve" is that residue seen from the wall's side, and #93's non-orthogonality is
// the same faceting seen from the interior's. A node placed HERE is placed on the
// curve itself, at exact arc length, so:
//   * the sagitta residue is 0 rather than a stated number;
//   * #94's sample-rate advice has nothing to advise about, because there is no
//     source polyline whose facet count could disagree with the node count;
//   * `BL_INITIAL_THICKNESS` reaches the wall as a length on the curve and not as
//     a length on a chord through it.
//
// ONE PARAMETRIC FORM, NOT TWO:
//
//     P(t) = C + R(rot) * (a * cos t, b * sin t)
//
// A circle is the `a == b` case and is NOT a separate branch. Its arc length is
// the integral of a CONSTANT, which the quadrature below integrates exactly, so
// the general path REPRODUCES the closed form instead of sitting beside it. That
// shape is deliberate: a closed form written beside a loop is how `D_total` came
// to be wrong by r/g at the base/transition seam, with a FALSE left/right
// asymmetry as the only symptom.
//
// THE SPAN IS NOT DECLARED, IT IS DERIVED FROM THE EDGE's OWN TWO CORNERS. A pair
// of angles declared beside corners declared as coordinates is two numberings of
// one thing with nothing checking that they agree — the defect class that put all
// four of an O-grid's "radial" edges a quarter turn around the annulus (the body's
// segment 0 started at 225 deg and the hand-written far field's at -45) and that
// rotated a cut list onto its neighbour's box node. Here the corners ARE the span:
// they are inverse-mapped onto the curve, they must LIE on it, and the sweep
// direction picks which of the two arcs between them the edge is.
//
// ITS OWN `Mb*` MODULE. The multi-block rule file's globs are PATTERNS over
// `include/Mb*.hpp` and `src/Mb*.cpp`, so a module named this way starts life with
// this path's rules attached while a `MultiBlockCurve.cpp` would have arrived
// ruleless — the rule file says so in as many words.
//
// It lives in `hybmesh_pure`: arithmetic over coordinates, no `Mesh`, no gmsh.
// See tools/PreProcessor/tests/test_cpp_pure_layer.py.
namespace hybmesh {

enum MbCurveKind {
    MB_CURVE_ARC = 0,      // a == b == r
    MB_CURVE_ELLIPSE = 1,
};

// The name a refusal and a report spell this kind with — ONE place, so the parser's
// accepted-values list and the shared-edge report cannot disagree.
const char* mbCurveKindName(MbCurveKind k);

// A curve, and — once `mbCurveResolveSpan` has run — the stretch of it one edge is.
//
// `t0` and `t1` are in the curve's own parameter and are MONOTONE: `t1 > t0` for a
// counter-clockwise sweep and `t1 < t0` for a clockwise one, so arc length runs
// forward from `t0` either way and no code below branches on direction.
struct MbCurve {
    MbCurveKind kind = MB_CURVE_ARC;
    double cx = 0.0, cy = 0.0;   // centre
    double a = 0.0, b = 0.0;     // semi-axes; for an arc both are the radius
    double rot = 0.0;            // the ellipse's rotation, radians; 0 for an arc
    bool ccw = true;             // which of the two arcs between the corners

    double t0 = 0.0, t1 = 0.0;   // the resolved span
    bool spanned = false;        // has `mbCurveResolveSpan` run?
};

// ── The parametric form ───────────────────────────────────────────────────

// P(t).
Point2D mbCurveAt(const MbCurve& c, double t);

// |P'(t)| — the speed, which is what arc length integrates. Independent of `rot`:
// a rotation is an isometry, so it moves the curve and not its length.
double mbCurveSpeed(const MbCurve& c, double t);

// The parameter whose point is nearest `p` ALONG THE WHOLE CURVE, found by
// un-rotating, un-scaling and taking `atan2`. EXACT for a circle and an
// INVERSE MAP rather than a projection for an ellipse: the point it names is where
// the ray from the centre through `p` crosses the curve, which is not the closest
// point unless `a == b`. That is what it is for — resolving a corner that is
// SUPPOSED to be on the curve, where the two agree to the distance the corner is
// off by. For the closest point, call `mbCurveProject`.
double mbCurveParam(const MbCurve& c, const Point2D& p);

// ── Arc length ────────────────────────────────────────────────────────────

// The length of the curve from `from` to `to`, by composite Gauss-Legendre over
// panels no wider than `kPanelWidth`. SIGNED: negative when `to < from`.
//
// Gauss-Legendre rather than Simpson because the integrand is analytic and
// periodic, so a fixed-order rule on bounded panels converges to the last bit
// instead of to a stated tolerance — and because an 8-point rule integrates a
// CONSTANT exactly, which is what makes the circle fall out of the general path.
double mbCurveArc(const MbCurve& c, double from, double to);

// The span's total length, `t0` to `t1`. Always >= 0, since the span is monotone
// in the direction of travel.
double mbCurveLength(const MbCurve& c);

// The point at arc length `s` measured from `t0`, by Newton against the exact
// speed, bracketed by bisection so it is TOTAL: an `s` outside [0, L] is clamped
// to the span's own ends rather than extrapolated off it.
Point2D mbCurveAtArc(const MbCurve& c, double s);

// ── Projection ────────────────────────────────────────────────────────────

// The CLOSEST point of the curve to `p`, and its parameter.
//
// Minimises |P(t) - p|^2 by Newton on its derivative, seeded from `mbCurveParam`
// — which is the answer outright for a circle, so the iteration does no work
// there. `clampToSpan` restricts the answer to [t0, t1]: what a smoother sliding a
// node along one EDGE wants, where leaving the span means leaving the edge.
Point2D mbCurveProject(const MbCurve& c, const Point2D& p, bool clampToSpan,
                       double* tOut = nullptr);

// How far `p` is from the curve — the distance to `mbCurveProject`'s answer,
// unclamped. The measure a corner is checked with.
double mbCurveDistance(const MbCurve& c, const Point2D& p);

// ── The span, derived from two corners ────────────────────────────────────

// Why a span could not be resolved. Published as an enum rather than as a message
// so the caller — which knows the edge's id, the keys the user typed and the
// surrounding document — writes the sentence; this module knows geometry and not
// the schema.
enum MbCurveSpanStatus {
    MB_CURVE_SPAN_OK = 0,
    MB_CURVE_SPAN_DEGENERATE,   // a non-positive semi-axis
    MB_CURVE_SPAN_OFF_CURVE,    // a corner is not on the curve
    MB_CURVE_SPAN_SAME_POINT,   // both corners map to one parameter: no length
};

// The outcome of resolving a span, with the numbers a refusal needs to be
// actionable: WHICH corner was off (0 or 1), by how far, and where on the curve it
// should have been.
struct MbCurveSpanResult {
    MbCurveSpanStatus status = MB_CURVE_SPAN_OK;
    int corner = -1;             // 0 or 1, for OFF_CURVE
    double distance = 0.0;       // ...and how far off it is
    Point2D nearest{0.0, 0.0};   // ...and the point on the curve it is nearest
    double tolerance = 0.0;      // the bar it had to clear
    double sweptRad = 0.0;       // the angle the resolved span covers, >= 0
};

// THE TOLERANCE A CORNER IS CHECKED AGAINST, relative to the curve's own size.
//
// This path refuses coordinate welding because wall spacing near 1e-7 and
// far-field spacing near 1e-1 leave no single tolerance between them — and that
// argument does NOT apply here. This compares one length (how far a corner is from
// a curve) against another length at the SAME scale (the curve's larger semi-axis)
// in a test whose whole content is "did the author mean this corner to be on this
// curve". A corner off by 1e-12 of the radius was meant to be on it; one off by
// 1e-3 of the radius was not, and no mesh either way is the right outcome.
//
// 1e-9 rather than something tighter: a corner is routinely a round decimal the
// author typed (0.75, 0.5) against a curve whose parameters are other round
// decimals, and the two agree to about 1e-16 relative — but a corner derived
// through `on_geometry` is an arc-length position along a RESAMPLED polyline, and
// that lands within a facet sagitta of the curve rather than on it. The bar has to
// clear typing noise without admitting a facet.
extern const double MB_CURVE_ON_TOL;

// Resolve `c`'s span so that it runs from `pa` to `pb` in `c.ccw`'s direction.
// Sets `t0`, `t1` and `spanned` on success and leaves them alone otherwise.
MbCurveSpanResult mbCurveResolveSpan(MbCurve& c, const Point2D& pa, const Point2D& pb);

// `n` points along the resolved span at EQUAL arc length, ends included. The
// polyline form of the curve, for the one caller that still wants one; the node
// positions themselves never come from this.
std::vector<Point2D> mbCurveSample(const MbCurve& c, int n);

}  // namespace hybmesh

#endif  // MBCURVE_HPP
