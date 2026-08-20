#pragma once
#include <vector>
#include <cmath>
#include <algorithm>
#include <iostream>
#include "GeomUtils.hpp"

namespace HybMesh {

class Spacing {
public:
    static double solveGrowthRate(double L, int n, double d0) {
        if (n <= 1) return 1.0;
        double r = std::pow(L / d0, 1.0 / n);
        for (int i = 0; i < 25; ++i) {
            double rn = std::pow(r, n);
            double f = d0 * (rn - 1.0) / (r - 1.0) - L;
            double df = d0 * (n * std::pow(r, n - 1) * (r - 1.0) - (rn - 1.0)) / ((r - 1.0) * (r - 1.0));
            double dr = f / df;
            if (std::isnan(dr) || std::isinf(dr)) break;
            r -= dr;
            if (std::abs(dr) < 1e-8) break;
        }
        double clamped = std::max(0.1, std::min(r, 10.0));
        if (clamped != r)
            std::cerr << "Warning: requested first-cell spacing unattainable; growth rate clamped to "
                      << clamped << "." << std::endl;
        return clamped;
    }

    static std::vector<double> generateGeometric(double L, int nT, double ratio) {
        std::vector<double> tS;
        if (std::abs(ratio - 1.0) < 1e-6) {
            for (int i = 0; i < nT; ++i) tS.push_back(L * i / (nT - 1));
        } else {
            double d0 = L * (1.0 - ratio) / (1.0 - std::pow(ratio, nT - 1));
            tS.push_back(0.0);
            double cur = 0;
            for (int i = 1; i < nT; ++i) {
                cur += d0 * std::pow(ratio, i - 1);
                tS.push_back(cur);
            }
        }
        return tS;
    }

    static std::vector<double> generateTanh(double L, int nT, double dlt) {
        std::vector<double> tS;
        // dlt == 0 makes tanh(dlt) == 0 -> division by zero (NaN). Degenerate
        // to a uniform distribution, matching generateGeometric at ratio ~= 1.
        if (std::abs(dlt) < 1e-9) {
            for (int i = 0; i < nT; ++i) tS.push_back(L * i / (nT - 1));
            return tS;
        }
        for (int i = 0; i < nT; ++i) {
            double xi = (double)i / (nT - 1);
            tS.push_back(L * 0.5 * (1.0 + std::tanh(dlt * (2.0 * xi - 1.0)) / std::tanh(dlt)));
        }
        return tS;
    }

    // Clustering parameter `dlt` that makes generateTanh's FIRST interval equal
    // `ds_first`, found by bisection.
    //
    // Previously the caller mapped a requested spacing to dlt with the heuristic
    // `log(L / min(s0,s1)) * 0.5`, which does not reproduce the requested spacing
    // (it was off by ~40x for a chord-scale edge) and could only use one of the two
    // ends. A boundary-layer-like distribution is specified BY its first cell size,
    // so that has to be solved for, not approximated.
    //
    // generateTanh's first interval is monotonically DECREASING in dlt (more
    // clustering -> finer ends), which is what makes plain bisection safe here.
    // Returns 0 when the request is not achievable (>= the uniform spacing), so the
    // caller can fall back to uniform rather than clamp to a misleading value.
    static double solveTanhDelta(double L, int nT, double ds_first) {
        if (nT < 3 || L <= 0.0 || ds_first <= 0.0) return 0.0;
        const double uniform = L / (nT - 1);
        // At dlt -> 0 the distribution IS uniform, so nothing coarser than uniform
        // can be asked for.
        if (ds_first >= uniform) return 0.0;

        auto first_interval = [&](double dlt) {
            const double xi = 1.0 / (nT - 1);
            return L * 0.5 * (1.0 + std::tanh(dlt * (2.0 * xi - 1.0)) / std::tanh(dlt));
        };

        double lo = 1e-6, hi = 1.0;
        // Grow the bracket until the finest achievable interval is at or below the
        // request; 60 is far past the point where tanh saturates in double.
        while (first_interval(hi) > ds_first && hi < 60.0) hi *= 2.0;
        if (first_interval(hi) > ds_first) return hi;   // unreachable: finest we can do
        for (int it = 0; it < 200; ++it) {
            const double mid = 0.5 * (lo + hi);
            if (first_interval(mid) > ds_first) lo = mid;
            else hi = mid;
        }
        return 0.5 * (lo + hi);
    }

    // Task 1: Advanced Curvature-based spacing
    // L / min_ds / max_ds are part of the shared spacing-strategy signature
    // (all generateXxx take the same arguments) but are not needed by the
    // curvature weighting, which is driven purely by local turning angle.
    static std::vector<double> generateCurvature([[maybe_unused]] double L,
                                               const std::vector<Point2D>& points, const std::vector<double>& s, 
                                               int nT, double sensitivity, double max_angle_deg = 2.0, 
                                               [[maybe_unused]] double min_ds = 0.0,
                                               [[maybe_unused]] double max_ds = 1e30) {
        std::vector<double> w(points.size(), 1.0);
        double max_angle_rad = max_angle_deg * M_PI / 180.0;

        for (size_t i = 1; i < points.size() - 1; ++i) {
            Vector2D v1 = (points[i] - points[i - 1]).normalized();
            Vector2D v2 = (points[i + 1] - points[i]).normalized();
            double angle = std::acos(std::clamp(v1.dot(v2), -1.0, 1.0));
            
            // Weight based on curvature: w = 1 + sensitivity * (angle / target_angle)
            // This effectively reduces spacing where angle is large
            w[i] = 1.0 + sensitivity * (angle / std::max(1e-6, max_angle_rad));
        }

        std::vector<double> cS(points.size(), 0.0);
        for (size_t i = 1; i < points.size(); ++i) {
            cS[i] = cS[i - 1] + (w[i - 1] + w[i]) * 0.5 * (s[i] - s[i - 1]);
        }

        std::vector<double> tS;
        for (int i = 0; i < nT; ++i) {
            double tC = cS.back() * i / (nT - 1);
            auto it = std::lower_bound(cS.begin(), cS.end(), tC);
            int idx = std::distance(cS.begin(), it);
            if (idx <= 0) { tS.push_back(0.0); continue; }
            if (idx >= (int)cS.size()) idx = (int)cS.size() - 1; // clamp float overshoot past cS.back()
            if (cS[idx] - cS[idx - 1] < 1e-12) { tS.push_back(s[idx - 1]); continue; } // coincident points
            double t = (tC - cS[idx - 1]) / (cS[idx] - cS[idx - 1]);
            double ts_val = s[idx - 1] + t * (s[idx] - s[idx - 1]);
            tS.push_back(ts_val);
        }
        return tS;
    }
};

} // namespace HybMesh
