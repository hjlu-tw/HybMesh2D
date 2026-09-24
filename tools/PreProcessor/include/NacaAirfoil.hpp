#pragma once
#include <string>
#include <vector>
#include <cmath>
#include <algorithm>
#include <cctype>
#include <cstdio>
#include <iostream>
#include "GeomUtils.hpp"

// The NACA 4-digit aerofoil law, resampler side.
//
// This is the SECOND host of a law whose first host is
// tools/PreProcessor/gui/app/services/naca_airfoil.py, and that file's docstring
// carries the reason there are two: a Python module cannot be read by this
// binary, and the canvas preview it serves must run on every drag of a control
// point in a checkout with no build tree. Every expression below is written to
// mirror that module LITERALLY -- same order, powers as repeated multiplication,
// the two exact endpoints assigned rather than computed -- and what makes the
// pair behave as one owner is tools/PreProcessor/tests/test_naca_airfoil_parity.py,
// which drives the GUI preview and this binary and compares the coordinates.
//
// Changing a line here without changing the matching line there is what that
// gate exists to catch; it will.

namespace HybMesh {

class NacaAirfoil {
public:
    // The trailing-edge coefficient: the report's -0.1015 leaves the section
    // OPEN at x = 1 (a blunt trailing edge); -0.1036 makes the five coefficients
    // sum to zero, so the two surfaces meet at one point.
    static constexpr double TE_COEFF_SHARP = -0.1036;
    static constexpr double TE_COEFF_BLUNT = -0.1015;

    // Points spent on the base of a blunt trailing edge inside the `full` loop.
    static constexpr int TE_LOOP_POINTS = 4;

    // "2412" -> m = 0.02, p = 0.4, t = 0.12. Returns false (with `why` set) for
    // anything the Python owner also refuses, so a bad designation is reported
    // rather than meshed as an accidental shape.
    static bool parseDesignation(const std::string& text, double& m, double& p,
                                 double& t, std::string& why) {
        // SURROUNDING whitespace only, and ASCII digits only -- both of these
        // were divergences from the Python owner, found by review rather than
        // imagined here: stripping whitespace ANYWHERE made "0 012" a valid
        // section in this binary and a refusal on the canvas. The messages
        // below are the Python owner's word for word, because the parity gate
        // reads them to prove the binary refused for the reason the law
        // refuses -- two wordings make that check pass on a different refusal.
        std::string s = trim(text);
        for (auto& c : s) c = static_cast<char>(std::toupper(static_cast<unsigned char>(c)));
        if (s.rfind("NACA", 0) == 0) s = trim(s.substr(4));
        bool digits = (s.size() == 4);
        for (char c : s) if (c < '0' || c > '9') digits = false;
        if (!digits) {
            why = "NACA designation '" + text + "' is not four digits (e.g. 0012 or 2412).";
            return false;
        }
        m = (s[0] - '0') / 100.0;
        p = (s[1] - '0') / 10.0;
        t = std::stoi(s.substr(2)) / 100.0;
        if (t <= 0.0) {
            why = "NACA designation '" + text + "' has zero thickness; the last "
                  "two digits are thickness in per cent of chord.";
            return false;
        }
        if (m > 0.0 && p <= 0.0) {
            why = "NACA designation '" + text + "' has camber (first digit "
                  + std::string(1, s[0]) + ") but places it at x = 0 (second "
                  "digit 0); a cambered section needs 1-9 there.";
            return false;
        }
        return true;
    }

    static double halfThickness(double x, double t, bool sharpTe) {
        double a4 = sharpTe ? TE_COEFF_SHARP : TE_COEFF_BLUNT;
        double xx = x * x;
        return 5.0 * t * (0.2969 * std::sqrt(x > 0.0 ? x : 0.0)
                          - 0.1260 * x - 0.3516 * xx + 0.2843 * xx * x
                          + a4 * xx * xx);
    }

    static void camber(double x, double m, double p, double& yc, double& dyc) {
        if (m <= 0.0 || p <= 0.0 || p >= 1.0) { yc = 0.0; dyc = 0.0; return; }
        if (x < p) {
            yc = m / (p * p) * (2.0 * p * x - x * x);
            dyc = 2.0 * m / (p * p) * (p - x);
            return;
        }
        double q = 1.0 - p;
        yc = m / (q * q) * ((1.0 - 2.0 * p) + 2.0 * p * x - x * x);
        dyc = 2.0 * m / (q * q) * (p - x);
    }

    static Point2D surfacePoint(double x, double m, double p, double t,
                                bool sharpTe, bool upper) {
        double yt = halfThickness(x, t, sharpTe);
        double yc = 0.0, dyc = 0.0;
        camber(x, m, p, yc, dyc);
        double theta = std::atan(dyc);
        double st = std::sin(theta);
        double ct = std::cos(theta);
        if (upper) return Point2D{x - yt * st, yc + yt * ct};
        return Point2D{x + yt * st, yc - yt * ct};
    }

    // The requested PART ("full" | "upper" | "lower" | "te") of the section.
    // Returns an empty vector and sets `why` when the request is refused -- the
    // caller reports it; a segment with no points is skipped downstream rather
    // than meshed as something the user did not draw.
    static std::vector<Point2D> points(const std::string& designation, int n,
                                       const std::string& partIn, double chord,
                                       double xLe, double yLe, double alphaDeg,
                                       bool sharpTe, std::string& why) {
        std::vector<Point2D> out;
        double m = 0.0, p = 0.0, t = 0.0;
        if (!parseDesignation(designation, m, p, t, why)) return out;
        // The Python owner spells this `str(part or "full").lower()`, so an
        // empty key and a capitalised one mean the same thing there; they were
        // refusals here, which is a divergence about what the two hosts ACCEPT
        // rather than about where either puts a point -- the class of defect no
        // comparison of coordinates can see.
        std::string part = partIn.empty() ? std::string("full") : partIn;
        for (auto& c : part) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
        if (part != "full" && part != "upper" && part != "lower" && part != "te") {
            why = "Unknown aerofoil part '" + partIn + "'; expected one of "
                  "full, upper, lower, te.";
            return out;
        }
        if (chord <= 0.0) {
            why = "Aerofoil chord must be positive (got " + fmtG(chord) + ").";
            return out;
        }
        if (n < 2) n = 2;

        std::vector<Point2D> local;
        if (part == "te") {
            if (sharpTe) {
                why = "This aerofoil has a SHARP trailing edge, so it has no "
                      "trailing-edge segment: the upper and lower surfaces meet "
                      "at one point. Turn the sharp trailing edge off to give "
                      "it a blunt base.";
                return out;
            }
            Point2D lo = surfacePoint(1.0, m, p, t, false, false);
            Point2D up = surfacePoint(1.0, m, p, t, false, true);
            for (int k = 0; k < n; ++k) {
                double f = (double)k / (n - 1);
                local.push_back(Point2D{lo.x + (up.x - lo.x) * f,
                                        lo.y + (up.y - lo.y) * f});
            }
        } else if (part == "upper") {
            local = surface(n, m, p, t, sharpTe, true);
        } else if (part == "lower") {
            local = surface(n, m, p, t, sharpTe, false);
        } else {
            local = fullLoop(n, m, p, t, sharpTe);
        }

        double a = -alphaDeg * M_PI / 180.0;
        double ca = std::cos(a);
        double sa = std::sin(a);
        for (const auto& q : local)
            out.push_back(Point2D{xLe + chord * (q.x * ca - q.y * sa),
                                  yLe + chord * (q.x * sa + q.y * ca)});
        return out;
    }

private:
    // `%g` for a double, so a refusal message reads the same on both sides of
    // the seam (Python formats the same value the same way).
    static std::string fmtG(double v) {
        char buf[64];
        std::snprintf(buf, sizeof(buf), "%g", v);
        return std::string(buf);
    }

    static std::string trim(const std::string& v) {
        size_t a = 0, b = v.size();
        while (a < b && std::isspace(static_cast<unsigned char>(v[a]))) ++a;
        while (b > a && std::isspace(static_cast<unsigned char>(v[b - 1]))) --b;
        return v.substr(a, b - a);
    }

    // Cosine spacing; `fromTe` runs 1 -> 0 (the upper surface's direction).
    // cos(0) is 1.0 and cos(pi) is -1.0 exactly, so both ends are exact.
    static double cosineX(int k, int n, bool fromTe) {
        double c = std::cos(M_PI * k / (n - 1));
        return fromTe ? 0.5 * (1.0 + c) : 0.5 * (1.0 - c);
    }

    // The leading edge is (0, 0) for every 4-digit section and a sharp trailing
    // edge is (1, 0); neither comes out exactly from decimal coefficients, and
    // exactly is the point -- it is where the two surfaces meet.
    static std::vector<Point2D> surface(int n, double m, double p, double t,
                                        bool sharpTe, bool upper) {
        std::vector<Point2D> pts;
        for (int k = 0; k < n; ++k)
            pts.push_back(surfacePoint(cosineX(k, n, upper), m, p, t, sharpTe, upper));
        Point2D le{0.0, 0.0};
        Point2D te = sharpTe ? Point2D{1.0, 0.0}
                             : surfacePoint(1.0, m, p, t, false, upper);
        if (upper) { pts.front() = te; pts.back() = le; }
        else       { pts.front() = le; pts.back() = te; }
        return pts;
    }

    static std::vector<Point2D> fullLoop(int n, double m, double p, double t,
                                         bool sharpTe) {
        int perSide = std::max(2, (n + 1) / 2);
        std::vector<Point2D> up = surface(perSide, m, p, t, sharpTe, true);
        std::vector<Point2D> lo = surface(perSide, m, p, t, sharpTe, false);
        std::vector<Point2D> loop = up;
        loop.insert(loop.end(), lo.begin() + 1, lo.end());   // LE shared, not repeated
        if (sharpTe) { loop.push_back(up.front()); return loop; }
        Point2D loTe = lo.back(), upTe = up.front();
        for (int k = 1; k <= TE_LOOP_POINTS; ++k) {
            double f = (double)k / TE_LOOP_POINTS;
            loop.push_back(Point2D{loTe.x + (upTe.x - loTe.x) * f,
                                   loTe.y + (upTe.y - loTe.y) * f});
        }
        return loop;
    }
};

}  // namespace HybMesh
