#pragma once
#include <vector>
#include <iostream>
#include <cmath>
#include <iomanip>
#include <algorithm>
#include "GeomUtils.hpp"

namespace HybMesh {

struct QualityReport {
    double min_ds = 0;
    double max_ds = 0;
    double avg_ds = 0;
    double max_ratio = 1.0;
    size_t n_points = 0;

    void print() const {
        std::cout << "\n--- Resampling Quality Report ---" << std::endl;
        std::cout << "  Points: " << n_points << std::endl;
        std::cout << "  Spacing: [Min: " << min_ds << ", Max: " << max_ds << ", Avg: " << avg_ds << "]" << std::endl;
        
        if (max_ratio > 1.25) {
            std::cout << "  \033[1;33mWarning: Max Expansion Ratio (" << max_ratio << ") exceeds 1.25\033[0m" << std::endl;
        } else {
            std::cout << "  Max Expansion Ratio: " << max_ratio << " (OK)" << std::endl;
        }
        std::cout << "---------------------------------\n" << std::endl;
    }
};

class Quality {
public:
    static QualityReport analyze(const std::vector<Point2D>& points) {
        QualityReport report;
        report.n_points = points.size();
        if (points.size() < 2) return report;

        std::vector<double> ds;
        double total_ds = 0;
        for (size_t i = 1; i < points.size(); ++i) {
            double d = (points[i] - points[i-1]).length();
            ds.push_back(d);
            total_ds += d;
        }

        auto it = std::minmax_element(ds.begin(), ds.end());
        report.min_ds = *it.first;
        report.max_ds = *it.second;
        report.avg_ds = total_ds / ds.size();

        double max_r = 1.0;
        for (size_t i = 1; i < ds.size(); ++i) {
            if (ds[i-1] > 1e-12 && ds[i] > 1e-12) {
                double r = std::max(ds[i]/ds[i-1], ds[i-1]/ds[i]);
                max_r = std::max(max_r, r);
            }
        }
        report.max_ratio = max_r;
        return report;
    }
};

} // namespace HybMesh
