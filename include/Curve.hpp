#ifndef CURVE_HPP
#define CURVE_HPP

// Phase 2: a small, shared analytic-curve abstraction used by BOTH the
// preprocessor (which knows each segment's curve kind) and the mesher (which
// rebuilds the curve from the surface points to query smooth tangents,
// curvature and normals during boundary-layer growth — see Phase 3).
//
// Header-only and dependency-free (only GeomUtils.hpp) so it can be included
// from src/ and tools/PreProcessor/src/ alike.
//
// Design choice (Phase 2, "lightweight"): curves are reconstructed from the
// ACTUAL surface points, not from serialized analytic parameters. This is
// transform-safe — a line/circle segment that was rotated/scaled to align with
// the file geometry is still recovered correctly, because we fit to the points
// that were actually written. The preprocessor only needs to record the curve
// KIND in the metadata sidecar; the geometry travels in the .dat as before.

#include "GeomUtils.hpp"
#include <vector>
#include <memory>
#include <string>
#include <cmath>

enum class CurveKind {
    Polyline,  // piecewise-linear; real corners are flagged separately
    Line,      // straight: constant tangent, zero curvature
    Circle,    // constant curvature; tangent is perpendicular to the radius
    Smooth     // general smooth curve; spline-style tangent/curvature estimate
};

inline CurveKind curveKindFromString(const std::string& s) {
    if (s == "line")    return CurveKind::Line;
    if (s == "circle")  return CurveKind::Circle;
    if (s == "smooth")  return CurveKind::Smooth;
    return CurveKind::Polyline;
}

inline const char* curveKindToString(CurveKind k) {
    switch (k) {
        case CurveKind::Line:   return "line";
        case CurveKind::Circle: return "circle";
        case CurveKind::Smooth: return "smooth";
        default:                return "polyline";
    }
}

// A curve sampled at an ordered set of points. Queries are by point index so
// the mesher can ask "what is the smooth tangent/curvature at surface node i".
class Curve {
public:
    virtual ~Curve() = default;
    // Unit tangent at point i, oriented along increasing index.
    virtual Vector2D tangentAt(int i) const = 0;
    // Signed curvature at point i (1/radius; sign follows left-turn positive).
    virtual double curvatureAt(int i) const = 0;
    int size() const { return (int)m_pts.size(); }
protected:
    explicit Curve(const std::vector<Point2D>& pts) : m_pts(pts) {}
    std::vector<Point2D> m_pts;
};

// --- Straight segment: tangent is constant, curvature is zero. ------------
class LineCurve : public Curve {
public:
    explicit LineCurve(const std::vector<Point2D>& pts) : Curve(pts) {
        if (m_pts.size() >= 2)
            m_tan = (m_pts.back() - m_pts.front()).normalized();
        else
            m_tan = {1.0, 0.0};
    }
    Vector2D tangentAt(int) const override { return m_tan; }
    double curvatureAt(int) const override { return 0.0; }
private:
    Vector2D m_tan{1.0, 0.0};
};

// --- Circular arc: fit a circle (Kåsa least squares) to the points. -------
// tangent is perpendicular to the radius; curvature is the (signed) 1/r.
class CircleCurve : public Curve {
public:
    explicit CircleCurve(const std::vector<Point2D>& pts) : Curve(pts) {
        fit();
    }
    Vector2D tangentAt(int i) const override {
        if (!m_valid || size() < 2) return fallbackTangent(i);
        Vector2D radial = (m_pts[clamp(i)] - m_center);
        // Tangent perpendicular to radius, oriented by traversal direction.
        Vector2D t = radial.leftNormal().normalized();
        Vector2D chord = chordDir(i);
        if (t.dot(chord) < 0) t = t * -1.0;
        return t;
    }
    double curvatureAt(int) const override {
        if (!m_valid || m_radius < 1e-12) return 0.0;
        return m_sign / m_radius;
    }
    bool valid() const { return m_valid; }
    double radius() const { return m_radius; }
    Point2D center() const { return m_center; }
private:
    int clamp(int i) const { return i < 0 ? 0 : (i >= size() ? size() - 1 : i); }
    Vector2D chordDir(int i) const {
        int a = clamp(i == 0 ? 0 : i - 1);
        int b = clamp(i == 0 ? 1 : i);
        return (m_pts[b] - m_pts[a]).normalized();
    }
    Vector2D fallbackTangent(int i) const {
        if (size() < 2) return {1.0, 0.0};
        return chordDir(i);
    }
    void fit() {
        const int n = size();
        if (n < 3) { m_valid = false; return; }
        // Kåsa fit: minimise sum (x^2+y^2 + D x + E y + F).
        double Sx = 0, Sy = 0, Sxx = 0, Syy = 0, Sxy = 0, Sxz = 0, Syz = 0, Sz = 0;
        for (const auto& p : m_pts) {
            double z = p.x * p.x + p.y * p.y;
            Sx += p.x; Sy += p.y; Sxx += p.x * p.x; Syy += p.y * p.y;
            Sxy += p.x * p.y; Sxz += p.x * z; Syz += p.y * z; Sz += z;
        }
        // Normal equations for [D, E, F].
        double a11 = Sxx, a12 = Sxy, a13 = Sx;
        double a22 = Syy, a23 = Sy, a33 = (double)n;
        double b1 = -Sxz, b2 = -Syz, b3 = -Sz;
        // Solve the 3x3 symmetric system by Cramer's rule.
        auto det3 = [](double m11, double m12, double m13,
                       double m21, double m22, double m23,
                       double m31, double m32, double m33) {
            return m11 * (m22 * m33 - m23 * m32)
                 - m12 * (m21 * m33 - m23 * m31)
                 + m13 * (m21 * m32 - m22 * m31);
        };
        double det = det3(a11, a12, a13, a12, a22, a23, a13, a23, a33);
        if (std::abs(det) < 1e-18) { m_valid = false; return; }
        double D = det3(b1, a12, a13, b2, a22, a23, b3, a23, a33) / det;
        double E = det3(a11, b1, a13, a12, b2, a23, a13, b3, a33) / det;
        double F = det3(a11, a12, b1, a12, a22, b2, a13, a23, b3) / det;
        m_center = {-D / 2.0, -E / 2.0};
        double r2 = m_center.x * m_center.x + m_center.y * m_center.y - F;
        if (r2 <= 1e-18) { m_valid = false; return; }
        m_radius = std::sqrt(r2);
        // Sign of curvature from the turn direction of the first triple.
        Vector2D t0 = (m_pts[1] - m_pts[0]);
        Vector2D t1 = (m_pts[2] - m_pts[1]);
        m_sign = (t0.cross(t1) >= 0) ? 1.0 : -1.0;
        m_valid = true;
    }
    Point2D m_center{0, 0};
    double m_radius = 0.0;
    double m_sign = 1.0;
    bool m_valid = false;
};

// --- General curve: central-difference tangent, circumradius curvature. ---
// A modest but real improvement over a one-sided finite difference at coarse
// resolution; used for splined file segments and analytic "custom" curves.
class SmoothCurve : public Curve {
public:
    explicit SmoothCurve(const std::vector<Point2D>& pts) : Curve(pts) {}
    Vector2D tangentAt(int i) const override {
        const int n = size();
        if (n < 2) return {1.0, 0.0};
        if (i <= 0)        return (m_pts[1] - m_pts[0]).normalized();
        if (i >= n - 1)    return (m_pts[n - 1] - m_pts[n - 2]).normalized();
        // Central difference (smoother than either one-sided edge).
        return (m_pts[i + 1] - m_pts[i - 1]).normalized();
    }
    double curvatureAt(int i) const override {
        const int n = size();
        if (n < 3 || i <= 0 || i >= n - 1) return 0.0;
        return menger(m_pts[i - 1], m_pts[i], m_pts[i + 1]);
    }
private:
    // Signed Menger curvature of three points (= 1/circumradius).
    static double menger(const Point2D& a, const Point2D& b, const Point2D& c) {
        Vector2D ab = b - a, cb = b - c, ac = c - a;
        double area2 = ab.cross(ac);                 // 2*signed area
        double la = ab.length(), lb = cb.length(), lc = ac.length();
        double denom = la * lb * lc;
        if (denom < 1e-18) return 0.0;
        return 2.0 * area2 / denom;                  // signed
    }
};

// Polyline: piecewise-linear. Tangent is the average of the adjacent edge
// directions; curvature is treated as zero (real corners come from the
// is_corner flags carried in the metadata sidecar, not from this estimate).
class PolylineCurve : public Curve {
public:
    explicit PolylineCurve(const std::vector<Point2D>& pts) : Curve(pts) {}
    Vector2D tangentAt(int i) const override {
        const int n = size();
        if (n < 2) return {1.0, 0.0};
        if (i <= 0)     return (m_pts[1] - m_pts[0]).normalized();
        if (i >= n - 1) return (m_pts[n - 1] - m_pts[n - 2]).normalized();
        Vector2D e0 = (m_pts[i] - m_pts[i - 1]).normalized();
        Vector2D e1 = (m_pts[i + 1] - m_pts[i]).normalized();
        Vector2D avg = e0 + e1;
        return avg.lengthSq() > 1e-18 ? avg.normalized() : e1;
    }
    double curvatureAt(int) const override { return 0.0; }
};

// Factory: build the appropriate curve from a segment's ordered points.
inline std::unique_ptr<Curve> makeCurve(CurveKind kind, const std::vector<Point2D>& pts) {
    switch (kind) {
        case CurveKind::Line:   return std::make_unique<LineCurve>(pts);
        case CurveKind::Circle: {
            auto c = std::make_unique<CircleCurve>(pts);
            if (c->valid()) return c;
            return std::make_unique<SmoothCurve>(pts);  // fit failed -> smooth fallback
        }
        case CurveKind::Smooth: return std::make_unique<SmoothCurve>(pts);
        default:                return std::make_unique<PolylineCurve>(pts);
    }
}

#endif // CURVE_HPP
