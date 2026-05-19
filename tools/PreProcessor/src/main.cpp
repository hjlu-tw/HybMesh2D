#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cmath>
#include <algorithm>
#include <iomanip>

#include "json.hpp"
#include "GeomUtils.hpp"
#include "Spline.hpp"
#include "Spacing.hpp"
#include "Quality.hpp"

using json = nlohmann::json;
using namespace HybMesh;

// 數學表達式求值器 (保持在 main.cpp 以簡化)
class MathEvaluator {
public:
    MathEvaluator(const std::string& expr) : expression(expr), pos(0) {}
    double eval(double v, char name = 'x') { xV = (name == 'x' ? v : 0); tV = (name == 't' ? v : 0); pos = 0; return parseExpression(); }
    double eval(double x, double t) { xV = x; tV = t; pos = 0; return parseExpression(); }
private:
    std::string expression; size_t pos; double xV = 0, tV = 0;
    void skip() { while (pos < expression.length() && isspace(expression[pos])) pos++; }
    double parseExpression() {
        double res = parseTerm(); skip();
        while (pos < expression.length() && (expression[pos] == '+' || expression[pos] == '-')) {
            char op = expression[pos++]; double next = parseTerm();
            if (op == '+') res += next; else res -= next; skip();
        }
        return res;
    }
    double parseTerm() {
        double res = parseFactor(); skip();
        while (pos < expression.length() && (expression[pos] == '*' || expression[pos] == '/')) {
            char op = expression[pos++]; double next = parseFactor();
            if (op == '*') res *= next; else res /= next; skip();
        }
        return res;
    }
    double parseFactor() {
        double res = parseBase(); skip();
        if (pos < expression.length() && expression[pos] == '^') { pos++; res = std::pow(res, parseFactor()); }
        return res;
    }
    double parseBase() {
        skip(); if (pos >= expression.length()) return 0;
        if (expression[pos] == '(') { pos++; double res = parseExpression(); if (pos < expression.length() && expression[pos] == ')') pos++; return res; }
        if (expression[pos] == '-') { pos++; return -parseBase(); }
        if (isdigit(expression[pos]) || expression[pos] == '.') {
            size_t s = pos; while (pos < expression.length() && (isdigit(expression[pos]) || expression[pos] == '.')) pos++;
            return std::stod(expression.substr(s, pos - s));
        }
        if (isalpha(expression[pos])) {
            size_t s = pos; while (pos < expression.length() && isalnum(expression[pos])) pos++;
            std::string n = expression.substr(s, pos - s);
            if (n == "x") return xV; if (n == "t") return tV; if (n == "pi") return M_PI;
            skip(); if (pos < expression.length() && expression[pos] == '(') {
                pos++; double a = parseExpression(); if (pos < expression.length() && expression[pos] == ')') pos++;
                if (n == "sin") return std::sin(a); if (n == "cos") return std::cos(a); if (n == "tan") return std::tan(a);
                if (n == "exp") return std::exp(a); if (n == "log") return std::log(a); if (n == "sqrt") return std::sqrt(a);
                if (n == "abs") return std::abs(a);
            }
        }
        return 0;
    }
};

std::vector<Point2D> loadGeometry(const std::string& filename) {
    std::vector<Point2D> points;
    std::ifstream ifs(filename);
    if (!ifs) return points;
    double x, y;
    while (ifs >> x >> y) points.push_back({x, y});
    return points;
}

void saveGeometry(const std::string& filename, const std::vector<Point2D>& points) {
    std::ofstream ofs(filename);
    if (!ofs) return;
    ofs << std::fixed << std::setprecision(10);
    for (const auto& p : points) ofs << p.x << " " << p.y << "\n";
}

std::vector<double> calculateArcLengths(const std::vector<Point2D>& points) {
    std::vector<double> s(points.size(), 0.0);
    for (size_t i = 1; i < points.size(); ++i)
        s[i] = s[i - 1] + (points[i] - points[i - 1]).length();
    return s;
}

Point2D interpolateLinear(const std::vector<Point2D>& points, const std::vector<double>& s, double targetS) {
    if (targetS <= s.front()) return points.front();
    if (targetS >= s.back()) return points.back();
    auto it = std::lower_bound(s.begin(), s.end(), targetS);
    int idx = std::distance(s.begin(), it);
    if (idx == 0) return points.front();
    double s0 = s[idx - 1], s1 = s[idx], t = (targetS - s0) / (s1 - s0);
    return points[idx - 1] * (1.0 - t) + points[idx] * t;
}

std::vector<Point2D> generateCurvePoints(const json& seg) {
    std::vector<Point2D> pts; 
    json p = seg.value("parameters", json::object());
    std::vector<double> r = p.value("range", std::vector<double>{0.0, 1.0});
    int n = p.value("n_points", 50); double t0 = r[0], t1 = r[1];
    if (seg.contains("x_formula") && seg.contains("y_formula")) {
        MathEvaluator ex(seg["x_formula"]), ey(seg["y_formula"]);
        for (int i = 0; i < n; ++i) { double t = t0 + (t1 - t0) * i / (n - 1); pts.push_back({ex.eval(t, 't'), ey.eval(t, 't')}); }
    } else {
        std::string f = seg.value("formula", "line");
        if (f == "sin") {
            double a = p.value("amplitude", 1.0), fr = p.value("frequency", 1.0), ph = p.value("phase", 0.0), oy = p.value("offset_y", 0.0);
            for (int i = 0; i < n; ++i) { double x = t0 + (t1 - t0) * i / (n - 1); pts.push_back({x, a * std::sin(fr * x + ph) + oy}); }
        } else if (f == "line") {
            double x0 = p.value("x0", 0.0), y0 = p.value("y0", 0.0), x1 = p.value("x1", 1.0), y1 = p.value("y1", 1.0);
            for (int i = 0; i < n; ++i) { double t = (double)i / (n - 1); pts.push_back({x0 + t * (x1 - x0), y0 + t * (y1 - y0)}); }
        } else {
            MathEvaluator ev(f); for (int i = 0; i < n; ++i) { double x = t0 + (t1 - t0) * i / (n - 1); pts.push_back({x, ev.eval(x, 'x')}); }
        }
    }
    return pts;
}

std::vector<int> detectFeaturePoints(const std::vector<Point2D>& points, double threshold) {
    std::vector<int> feat = {0}; if (points.size() < 3) { feat.push_back((int)points.size() - 1); return feat; }
    double thr = threshold * M_PI / 180.0;
    for (size_t i = 1; i < points.size() - 1; ++i) {
        Vector2D v1 = (points[i] - points[i - 1]).normalized(), v2 = (points[i + 1] - points[i]).normalized();
        if ((points[i] - points[i - 1]).length() < 1e-10 || (points[i + 1] - points[i]).length() < 1e-10) continue;
        if (std::acos(std::clamp(v1.dot(v2), -1.0, 1.0)) > thr) feat.push_back((int)i);
    }
    feat.push_back((int)points.size() - 1); feat.erase(std::unique(feat.begin(), feat.end()), feat.end());
    return feat;
}

void processElement(const json& config) {
    std::vector<Point2D> gp = loadGeometry(config.value("input_file", ""));
    if (config.value("is_closed", false) && !gp.empty()) {
        if ((gp.front() - gp.back()).length() > 1e-9) gp.push_back(gp.front());
    }

    // Task 3: Global Spline for G1 continuity
    Spline2D globalSpline;
    std::vector<double> globalS;
    bool useGlobalSpline = config.value("global_spline", false) && gp.size() >= 3;
    if (useGlobalSpline) {
        globalS = calculateArcLengths(gp);
        globalSpline.build(gp, globalS);
    }

    std::vector<Point2D> resPts;
    double last_ds = -1.0; // Task 4: Spacing matching state

    for (const auto& sj : config["segments"]) {
        std::string type = sj.value("type", "file"); 
        bool autoSplit = sj.value("auto_split", false);
        std::vector<std::pair<int, int>> ranges;

        if (type == "curve") ranges.push_back({-1, -1});
        else {
            int s = sj.value("start_index", 0), e = sj.value("end_index", -1);
            if (e == -1 && !gp.empty()) e = (int)gp.size() - 1;
            if (autoSplit && !gp.empty()) {
                std::vector<Point2D> sub; for (int i = s; i <= e; ++i) sub.push_back(gp[i]);
                std::vector<int> f = detectFeaturePoints(sub, sj.value("split_threshold", 20.0));
                for (size_t i = 0; i < f.size() - 1; ++i) ranges.push_back({s + f[i], s + f[i + 1]});
            } else ranges.push_back({s, e});
        }

        for (auto& r : ranges) {
            std::vector<Point2D> sp; 
            if (type == "curve") sp = generateCurvePoints(sj); 
            else for (int i = r.first; i <= r.second; ++i) sp.push_back(gp[i]);
            if (sp.size() < 2) continue;

            std::vector<double> s = calculateArcLengths(sp); 
            double L = s.back();
            
            // Build segment-local spline if not using global
            Spline2D localSpline;
            bool useLocalSpline = (type == "file" && sp.size() >= 3 && !useGlobalSpline);
            if (useLocalSpline) localSpline.build(sp, s);

            std::string strat = sj.value("strategy", "uniform");
            json params = sj.value("parameters", json::object());

            // Task 4: Spacing matching
            if (sj.value("match_previous", false) && last_ds > 0) {
                if (strat == "uniform") params["spacing"] = last_ds;
                else params["spacing_start"] = last_ds;
            }

            int nT; 
            if (params.contains("spacing")) nT = std::max(2, (int)std::round(L / (double)params["spacing"]) + 1);
            else if (params.contains("spacing_start") || params.contains("spacing_end")) {
                double ds_avg = L;
                if (params.contains("spacing_start") && params.contains("spacing_end")) 
                    ds_avg = 0.5 * ((double)params["spacing_start"] + (double)params["spacing_end"]);
                else if (params.contains("spacing_start")) ds_avg = params["spacing_start"];
                else ds_avg = params["spacing_end"];
                nT = std::max(2, (int)std::round(L / ds_avg) + 1);
            }
            else nT = params.value("n_points", (int)sp.size());
            if (nT < 2) nT = 2;

            std::vector<double> tS;
            if (strat == "cosine") {
                for (int i = 0; i < nT; ++i) tS.push_back(L * (1.0 - std::cos(M_PI * i / (nT - 1))) * 0.5);
            } else if (strat == "geometric") {
                double ratio = 1.1;
                if (params.contains("spacing_start")) ratio = Spacing::solveGrowthRate(L, nT - 1, params["spacing_start"]);
                else if (params.contains("spacing_end")) ratio = 1.0 / Spacing::solveGrowthRate(L, nT - 1, params["spacing_end"]);
                else ratio = params.value("ratio", 1.1);
                tS = Spacing::generateGeometric(L, nT, ratio);
            } else if (strat == "tanh") {
                double dlt = params.value("intensity", 2.0);
                if (params.contains("spacing_start") && params.contains("spacing_end")) {
                    double s0 = params["spacing_start"], s1 = params["spacing_end"];
                    dlt = std::log(L / std::min(s0, s1)) * 0.5;
                }
                tS = Spacing::generateTanh(L, nT, dlt);
            } else if (strat == "curvature") {
                double sens = params.value("sensitivity", 1.0);
                double max_ang = params.value("max_angle", 2.0);
                tS = Spacing::generateCurvature(L, sp, s, nT, sens, max_ang);
            } else {
                for (int i = 0; i < nT; ++i) tS.push_back(L * i / (nT - 1));
            }

            std::vector<Point2D> segmentPts;
            for (double ts : tS) {
                Point2D p;
                if (useGlobalSpline) {
                    // Map local s to global s
                    double start_s = globalS[r.first];
                    p = globalSpline.eval(start_s + ts);
                } else if (useLocalSpline) {
                    p = localSpline.eval(ts);
                } else {
                    p = interpolateLinear(sp, s, ts);
                }
                
                // Avoid duplicate points at segment boundaries
                if (resPts.empty() || (p - resPts.back()).length() > 1e-10) {
                    resPts.push_back(p);
                    segmentPts.push_back(p);
                }
            }
            
            // Task 4: Update last_ds for next segment
            if (segmentPts.size() >= 2) {
                last_ds = (segmentPts.back() - segmentPts[segmentPts.size() - 2]).length();
            }
        }
    }

    if (config.contains("transform")) {
        const auto& t = config.at("transform"); 
        double sc = t.value("scale", 1.0), ang = t.value("rotate", 0.0) * M_PI / 180.0;
        std::vector<double> tr = t.value("translate", std::vector<double>{0.0, 0.0});
        for (auto& p : resPts) {
            p.x *= sc; p.y *= sc; double xN = p.x * std::cos(ang) - p.y * std::sin(ang), yN = p.x * std::sin(ang) + p.y * std::cos(ang);
            p.x = xN + tr[0]; p.y = yN + tr[1];
        }
    }

    saveGeometry(config.value("output_file", "Results/output.dat"), resPts);
    std::cout << "Successfully processed element to " << config.value("output_file", "Results/output.dat") << " (" << resPts.size() << " points)" << std::endl;

    // Task 5: Quality Report
    Quality::analyze(resPts).print();
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cout << "Usage: surface_resampler <config.json>" << std::endl;
        return 1;
    }
    std::ifstream f(argv[1]); if (!f) return 1;
    json c;
    try {
        c = json::parse(f);
    } catch (const std::exception& e) {
        std::cerr << "JSON Parse Error: " << e.what() << std::endl;
        return 1;
    }
    
    if (c.contains("elements") && c["elements"].is_array()) for (const auto& e : c["elements"]) processElement(e);
    else processElement(c);
    return 0;
}
