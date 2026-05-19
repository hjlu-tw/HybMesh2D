#pragma once
#include <vector>
#include <algorithm>
#include <cmath>
#include "GeomUtils.hpp"

namespace HybMesh {

class CubicSpline {
public:
    void build(const std::vector<double>& x, const std::vector<double>& y) {
        int n = x.size();
        if (n < 3) { is_valid = false; return; }
        is_valid = true;
        this->x = x;
        a = y;
        b.resize(n); d.resize(n); c.resize(n);
        std::vector<double> h(n - 1), alpha(n - 1);
        for (int i = 0; i < n - 1; ++i) h[i] = x[i + 1] - x[i];
        for (int i = 1; i < n - 1; ++i)
            alpha[i] = (3.0 / h[i]) * (a[i + 1] - a[i]) - (3.0 / h[i - 1]) * (a[i] - a[i - 1]);

        std::vector<double> l(n), mu(n), z(n);
        l[0] = 1.0; mu[0] = 0.0; z[0] = 0.0;
        for (int i = 1; i < n - 1; ++i) {
            l[i] = 2.0 * (x[i + 1] - x[i - 1]) - h[i - 1] * mu[i - 1];
            mu[i] = h[i] / l[i];
            z[i] = (alpha[i] - h[i - 1] * z[i - 1]) / l[i];
        }
        l[n - 1] = 1.0; z[n - 1] = 0.0; c[n - 1] = 0.0;
        for (int j = n - 2; j >= 0; --j) {
            c[j] = z[j] - mu[j] * c[j + 1];
            b[j] = (a[j + 1] - a[j]) / h[j] - h[j] * (c[j + 1] + 2.0 * c[j]) / 3.0;
            d[j] = (c[j + 1] - c[j]) / (3.0 * h[j]);
        }
    }

    double eval(double val) const {
        if (!is_valid) return 0;
        auto it = std::lower_bound(x.begin(), x.end(), val);
        int i = std::distance(x.begin(), it) - 1;
        if (i < 0) i = 0;
        if (i >= (int)x.size() - 1) i = x.size() - 2;
        double dx = val - x[i];
        return a[i] + b[i] * dx + c[i] * dx * dx + d[i] * dx * dx * dx;
    }

    bool valid() const { return is_valid; }

private:
    std::vector<double> x, a, b, c, d;
    bool is_valid = false;
};

struct Spline2D {
    CubicSpline splineX, splineY;
    void build(const std::vector<Point2D>& points, const std::vector<double>& s) {
        std::vector<double> px, py;
        for (const auto& p : points) { px.push_back(p.x); py.push_back(p.y); }
        splineX.build(s, px);
        splineY.build(s, py);
    }
    Point2D eval(double s) const { return { splineX.eval(s), splineY.eval(s) }; }
    bool valid() const { return splineX.valid() && splineY.valid(); }
};

} // namespace HybMesh
