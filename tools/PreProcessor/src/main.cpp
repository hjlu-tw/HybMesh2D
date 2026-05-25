#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cmath>
#include <algorithm>
#include <numeric>
#include <iomanip>
#include <sstream>

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

// Vertex-pinned polyline sampler: every vertex in `vertices` is guaranteed
// to appear in the output.  Interior points are distributed proportionally
// to each edge's length.  Total output count = n (includes repeated first
// vertex at end for closed polygons).
std::vector<Point2D> samplePolylinePinned(const std::vector<Point2D>& vertices, int n) {
    int k = (int)vertices.size() - 1; // number of distinct vertices / edges
    if (k < 1) return std::vector<Point2D>(n, vertices.empty() ? Point2D{0,0} : vertices[0]);

    // Compute edge lengths
    std::vector<double> edgeLen(k);
    double Ltotal = 0.0;
    for (int i = 0; i < k; ++i) {
        edgeLen[i] = (vertices[i + 1] - vertices[i]).length();
        Ltotal += edgeLen[i];
    }
    if (Ltotal < 1e-12) return std::vector<Point2D>(n, vertices[0]);

    // Allocate interior (non-vertex) points per edge proportionally
    int nPinned = k + 1; // k distinct vertices + repeated start vertex
    int nInterior = std::max(0, n - nPinned);

    std::vector<int> edgeInter(k, 0);
    {
        int allocated = 0;
        for (int i = 0; i < k; ++i) {
            edgeInter[i] = (int)std::floor(nInterior * edgeLen[i] / Ltotal);
            allocated += edgeInter[i];
        }
        // Distribute remaining to longest edges first
        int remaining = nInterior - allocated;
        // Build sorted index by length descending
        std::vector<int> order(k);
        std::iota(order.begin(), order.end(), 0);
        std::stable_sort(order.begin(), order.end(),
            [&](int a, int b){ return edgeLen[a] > edgeLen[b]; });
        for (int i = 0; i < remaining; ++i)
            edgeInter[order[i % k]] += 1;
    }

    // Build output
    std::vector<Point2D> result;
    result.reserve(n);
    for (int i = 0; i < k; ++i) {
        result.push_back(vertices[i]);
        int ni = edgeInter[i];
        for (int j = 1; j <= ni; ++j) {
            double t = (double)j / (ni + 1);
            result.push_back(vertices[i] * (1.0 - t) + vertices[i + 1] * t);
        }
    }
    result.push_back(vertices[k]); // repeated first vertex (closes polygon)
    return result;
}


std::vector<Point2D> generateCurvePoints(const json& seg, const std::vector<Point2D>& gp) {
    std::vector<Point2D> pts; 
    json p = seg.value("parameters", json::object());
    std::vector<double> r = p.value("range", std::vector<double>{0.0, 1.0});
    int n = p.value("n_points", 50); double t0 = r[0], t1 = r[1];
    
    std::string curve_type = seg.value("curve_type", "custom");
    
    if (curve_type == "horizontal_line") {
        double y = p.value("y", 0.0);
        double x0 = p.value("x0", 0.0);
        double x1 = p.value("x1", 1.0);
        for (int i = 0; i < n; ++i) {
            double t = (double)i / (n - 1);
            pts.push_back({x0 + t * (x1 - x0), y});
        }
    } else if (curve_type == "vertical_line") {
        double x = p.value("x", 0.0);
        double y0 = p.value("y0", 0.0);
        double y1 = p.value("y1", 1.0);
        for (int i = 0; i < n; ++i) {
            double t = (double)i / (n - 1);
            pts.push_back({x, y0 + t * (y1 - y0)});
        }
    } else if (curve_type == "line") {
        double x0 = p.value("x0", 0.0);
        double y0 = p.value("y0", 0.0);
        double x1 = p.value("x1", 1.0);
        double y1 = p.value("y1", 1.0);
        for (int i = 0; i < n; ++i) {
            double t = (double)i / (n - 1);
            pts.push_back({x0 + t * (x1 - x0), y0 + t * (y1 - y0)});
        }
    } else if (curve_type == "circle") {
        double cx = p.value("cx", 0.0);
        double cy = p.value("cy", 0.0);
        double r_val = p.value("r", 1.0);
        for (int i = 0; i < n; ++i) {
            double t = 2.0 * M_PI * i / (n - 1);
            pts.push_back({cx + r_val * std::cos(t), cy + r_val * std::sin(t)});
        }
    } else if (curve_type == "triangle" || curve_type == "quadrilateral" || curve_type == "polygon") {
        std::vector<Point2D> vertices;
        if (curve_type == "triangle") {
            vertices = {
                {p.value("x0", 0.0), p.value("y0", 0.0)},
                {p.value("x1", 1.0), p.value("y1", 0.0)},
                {p.value("x2", 0.5), p.value("y2", 1.0)}
            };
        } else if (curve_type == "quadrilateral") {
            vertices = {
                {p.value("x0", 0.0), p.value("y0", 0.0)},
                {p.value("x1", 1.0), p.value("y1", 0.0)},
                {p.value("x2", 1.0), p.value("y2", 1.0)},
                {p.value("x3", 0.0), p.value("y3", 1.0)}
            };
        } else { // polygon
            std::string v_str = p.value("vertices_str", "0,0; 1,0; 1,1; 0,1");
            std::stringstream ss(v_str);
            std::string pair;
            while (std::getline(ss, pair, ';')) {
                if (pair.empty() || pair.find_first_not_of(" \t\r\n") == std::string::npos) continue;
                size_t comma = pair.find(',');
                if (comma != std::string::npos) {
                    try {
                        double vx = std::stod(pair.substr(0, comma));
                        double vy = std::stod(pair.substr(comma + 1));
                        vertices.push_back({vx, vy});
                    } catch (...) {}
                }
            }
            if (vertices.size() < 2) {
                vertices = {{0.0, 0.0}, {1.0, 1.0}};
            }
        }
        
        // Ensure polygon/triangle/quadrilateral is closed
        if (!vertices.empty()) {
            double dx = vertices.front().x - vertices.back().x;
            double dy = vertices.front().y - vertices.back().y;
            if (std::sqrt(dx*dx + dy*dy) > 1e-9) {
                vertices.push_back(vertices.front());
            }
        }
        
        pts = samplePolylinePinned(vertices, n);
    } else {
        // Fallback to "custom" type
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
    }

    int start_idx = seg.value("start_index", -1);
    int end_idx = seg.value("end_index", -1);

    bool start_valid = (!gp.empty() && start_idx >= 0 && start_idx < (int)gp.size());
    bool end_valid = (!gp.empty() && end_idx >= 0 && end_idx < (int)gp.size());

    if (pts.size() >= 2 && (start_valid || end_valid)) {
        Point2D P0 = pts.front();
        Point2D P1 = pts.back();

        if (start_valid && end_valid) {
            Point2D Q0 = gp[start_idx];
            Point2D Q1 = gp[end_idx];
            double dx_P = P1.x - P0.x;
            double dy_P = P1.y - P0.y;
            double dx_Q = Q1.x - Q0.x;
            double dy_Q = Q1.y - Q0.y;
            double L_P2 = dx_P * dx_P + dy_P * dy_P;

            if (L_P2 > 1e-12) {
                double A = (dx_Q * dx_P + dy_Q * dy_P) / L_P2;
                double B = (dy_Q * dx_P - dx_Q * dy_P) / L_P2;

                for (auto& pt : pts) {
                    double x_rel = pt.x - P0.x;
                    double y_rel = pt.y - P0.y;
                    pt.x = A * x_rel - B * y_rel + Q0.x;
                    pt.y = B * x_rel + A * y_rel + Q0.y;
                }
            } else {
                for (auto& pt : pts) {
                    pt.x = pt.x - P0.x + Q0.x;
                    pt.y = pt.y - P0.y + Q0.y;
                }
            }
        } else if (start_valid) {
            Point2D Q0 = gp[start_idx];
            for (auto& pt : pts) {
                pt.x = pt.x - P0.x + Q0.x;
                pt.y = pt.y - P0.y + Q0.y;
            }
        } else if (end_valid) {
            Point2D Q1 = gp[end_idx];
            for (auto& pt : pts) {
                pt.x = pt.x - P1.x + Q1.x;
                pt.y = pt.y - P1.y + Q1.y;
            }
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

struct ResampleTask {
    std::string type;
    std::vector<Point2D> sp;
    int start_gp_idx = -1;
    int end_gp_idx = -1;
    int n_points_alloc = -1;
    json segment_json;
};

void alignEndpoints(std::vector<Point2D>& pts, int start_idx, int end_idx, const std::vector<Point2D>& gp) {
    bool start_valid = (!gp.empty() && start_idx >= 0 && start_idx < (int)gp.size());
    bool end_valid = (!gp.empty() && end_idx >= 0 && end_idx < (int)gp.size());
    if (pts.size() >= 2 && (start_valid || end_valid)) {
        Point2D P0 = pts.front();
        Point2D P1 = pts.back();
        if (start_valid && end_valid) {
            Point2D Q0 = gp[start_idx];
            Point2D Q1 = gp[end_idx];
            double dx_P = P1.x - P0.x;
            double dy_P = P1.y - P0.y;
            double dx_Q = Q1.x - Q0.x;
            double dy_Q = Q1.y - Q0.y;
            double L_P2 = dx_P * dx_P + dy_P * dy_P;
            if (L_P2 > 1e-12) {
                double A = (dx_Q * dx_P + dy_Q * dy_P) / L_P2;
                double B = (dy_Q * dx_P - dx_Q * dy_P) / L_P2;
                for (auto& pt : pts) {
                    double x_rel = pt.x - P0.x;
                    double y_rel = pt.y - P0.y;
                    pt.x = A * x_rel - B * y_rel + Q0.x;
                    pt.y = B * x_rel + A * y_rel + Q0.y;
                }
            } else {
                for (auto& pt : pts) {
                    pt.x = pt.x - P0.x + Q0.x;
                    pt.y = pt.y - P0.y + Q0.y;
                }
            }
        } else if (start_valid) {
            Point2D Q0 = gp[start_idx];
            for (auto& pt : pts) {
                pt.x = pt.x - P0.x + Q0.x;
                pt.y = pt.y - P0.y + Q0.y;
            }
        } else if (end_valid) {
            Point2D Q1 = gp[end_idx];
            for (auto& pt : pts) {
                pt.x = pt.x - P1.x + Q1.x;
                pt.y = pt.y - P1.y + Q1.y;
            }
        }
    }
}

std::vector<int> distributePointsProportionally(const std::vector<double>& lengths, int N) {
    int M = (int)lengths.size();
    if (M == 0) return {};
    if (M == 1) return {N};
    
    double Ltotal = 0.0;
    for (double l : lengths) Ltotal += l;
    
    std::vector<int> alloc(M, 2);
    if (Ltotal < 1e-12) return alloc;
    
    int nInterior = N + M - 1 - 2 * M; // N - M - 1
    if (nInterior <= 0) return alloc;
    
    int allocated = 0;
    std::vector<double> remainders(M);
    for (int i = 0; i < M; ++i) {
        double exact = nInterior * lengths[i] / Ltotal;
        int val = (int)std::floor(exact);
        alloc[i] += val;
        allocated += val;
        remainders[i] = exact - val;
    }
    
    int remaining = nInterior - allocated;
    if (remaining > 0) {
        std::vector<int> order(M);
        std::iota(order.begin(), order.end(), 0);
        std::stable_sort(order.begin(), order.end(),
            [&](int a, int b) { return remainders[a] > remainders[b]; });
        for (int i = 0; i < remaining; ++i) {
            alloc[order[i % M]] += 1;
        }
    }
    return alloc;
}

std::vector<std::vector<Point2D>> splitPolyline(const std::vector<Point2D>& pts, const std::vector<int>& indices) {
    std::vector<std::vector<Point2D>> subs;
    if (indices.size() < 2) return subs;
    for (size_t i = 0; i < indices.size() - 1; ++i) {
        int start = indices[i];
        int end = indices[i + 1];
        std::vector<Point2D> sub;
        for (int j = start; j <= end; ++j) {
            sub.push_back(pts[j]);
        }
        subs.push_back(sub);
    }
    return subs;
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
        double splitThreshold = sj.value("split_threshold", 20.0);

        std::vector<ResampleTask> tasks;

        if (type == "curve") {
            std::string curve_type = sj.value("curve_type", "custom");
            int n_points = sj.value("parameters", json::object()).value("n_points", 50);

            if (curve_type == "triangle" || curve_type == "quadrilateral" || curve_type == "polygon") {
                // Predefined shape: extract vertices
                std::vector<Point2D> vertices;
                json p = sj.value("parameters", json::object());
                if (curve_type == "triangle") {
                    vertices = {
                        {p.value("x0", 0.0), p.value("y0", 0.0)},
                        {p.value("x1", 1.0), p.value("y1", 0.0)},
                        {p.value("x2", 0.5), p.value("y2", 1.0)}
                    };
                } else if (curve_type == "quadrilateral") {
                    vertices = {
                        {p.value("x0", 0.0), p.value("y0", 0.0)},
                        {p.value("x1", 1.0), p.value("y1", 0.0)},
                        {p.value("x2", 1.0), p.value("y2", 1.0)},
                        {p.value("x3", 0.0), p.value("y3", 1.0)}
                    };
                } else { // polygon
                    std::string v_str = p.value("vertices_str", "0,0; 1,0; 1,1; 0,1");
                    std::stringstream ss(v_str);
                    std::string pair;
                    while (std::getline(ss, pair, ';')) {
                        if (pair.empty() || pair.find_first_not_of(" \t\r\n") == std::string::npos) continue;
                        size_t comma = pair.find(',');
                        if (comma != std::string::npos) {
                            try {
                                double vx = std::stod(pair.substr(0, comma));
                                double vy = std::stod(pair.substr(comma + 1));
                                vertices.push_back({vx, vy});
                            } catch (...) {}
                        }
                    }
                    if (vertices.size() < 2) {
                        vertices = {{0.0, 0.0}, {1.0, 1.0}};
                    }
                }

                if (!vertices.empty()) {
                    double dx = vertices.front().x - vertices.back().x;
                    double dy = vertices.front().y - vertices.back().y;
                    if (std::sqrt(dx*dx + dy*dy) > 1e-9) {
                        vertices.push_back(vertices.front());
                    }
                }

                // Align vertices using start/end indices
                int start_idx = sj.value("start_index", -1);
                int end_idx = sj.value("end_index", -1);
                alignEndpoints(vertices, start_idx, end_idx, gp);

                int k = (int)vertices.size() - 1;
                if (k >= 1) {
                    std::vector<double> lengths(k);
                    for (int i = 0; i < k; ++i) {
                        lengths[i] = (vertices[i + 1] - vertices[i]).length();
                    }
                    
                    std::vector<int> alloc_points;
                    json params = sj.value("parameters", json::object());
                    bool is_count_based = !params.contains("spacing") && 
                                          !params.contains("spacing_start") && 
                                          !params.contains("spacing_end");
                    if (is_count_based) {
                        alloc_points = distributePointsProportionally(lengths, n_points);
                    }

                    for (int i = 0; i < k; ++i) {
                        ResampleTask task;
                        task.type = "curve";
                        task.sp = {vertices[i], vertices[i + 1]};
                        task.n_points_alloc = is_count_based ? alloc_points[i] : -1;
                        task.segment_json = sj;
                        tasks.push_back(task);
                    }
                }
            } else {
                // Other curves
                std::vector<Point2D> full_pts = generateCurvePoints(sj, gp);
                if (autoSplit && full_pts.size() >= 3) {
                    std::vector<int> f = detectFeaturePoints(full_pts, splitThreshold);
                    if (f.size() > 2) {
                        auto subs = splitPolyline(full_pts, f);
                        int M = (int)subs.size();
                        std::vector<double> lengths(M);
                        for (int i = 0; i < M; ++i) {
                            lengths[i] = calculateArcLengths(subs[i]).back();
                        }

                        json params = sj.value("parameters", json::object());
                        bool is_count_based = !params.contains("spacing") && 
                                              !params.contains("spacing_start") && 
                                              !params.contains("spacing_end");
                        std::vector<int> alloc_points;
                        if (is_count_based) {
                            alloc_points = distributePointsProportionally(lengths, n_points);
                        }

                        for (int i = 0; i < M; ++i) {
                            ResampleTask task;
                            task.type = "curve";
                            task.sp = subs[i];
                            task.n_points_alloc = is_count_based ? alloc_points[i] : -1;
                            task.segment_json = sj;
                            tasks.push_back(task);
                        }
                    } else {
                        ResampleTask task;
                        task.type = "curve";
                        task.sp = full_pts;
                        task.n_points_alloc = -1;
                        task.segment_json = sj;
                        tasks.push_back(task);
                    }
                } else {
                    ResampleTask task;
                    task.type = "curve";
                    task.sp = full_pts;
                    task.n_points_alloc = -1;
                    task.segment_json = sj;
                    tasks.push_back(task);
                }
            }
        } else {
            // File segment
            int s = sj.value("start_index", 0), e = sj.value("end_index", -1);
            if (e == -1 && !gp.empty()) e = (int)gp.size() - 1;

            if (autoSplit && !gp.empty() && e > s) {
                std::vector<Point2D> sub; 
                for (int i = s; i <= e; ++i) sub.push_back(gp[i]);
                std::vector<int> f = detectFeaturePoints(sub, splitThreshold);
                if (f.size() > 2) {
                    auto subs = splitPolyline(sub, f);
                    int M = (int)subs.size();
                    std::vector<double> lengths(M);
                    for (int i = 0; i < M; ++i) {
                        lengths[i] = calculateArcLengths(subs[i]).back();
                    }

                    int n_points = sj.value("parameters", json::object()).value("n_points", (int)sub.size());
                    json params = sj.value("parameters", json::object());
                    bool is_count_based = !params.contains("spacing") && 
                                          !params.contains("spacing_start") && 
                                          !params.contains("spacing_end");
                    std::vector<int> alloc_points;
                    if (is_count_based) {
                        alloc_points = distributePointsProportionally(lengths, n_points);
                    }

                    for (int i = 0; i < M; ++i) {
                        ResampleTask task;
                        task.type = "file";
                        task.sp = subs[i];
                        task.start_gp_idx = s + f[i];
                        task.end_gp_idx = s + f[i + 1];
                        task.n_points_alloc = is_count_based ? alloc_points[i] : -1;
                        task.segment_json = sj;
                        tasks.push_back(task);
                    }
                } else {
                    ResampleTask task;
                    task.type = "file";
                    task.sp = sub;
                    task.start_gp_idx = s;
                    task.end_gp_idx = e;
                    task.n_points_alloc = -1;
                    task.segment_json = sj;
                    tasks.push_back(task);
                }
            } else {
                std::vector<Point2D> sub;
                for (int i = s; i <= e; ++i) sub.push_back(gp[i]);
                ResampleTask task;
                task.type = "file";
                task.sp = sub;
                task.start_gp_idx = s;
                task.end_gp_idx = e;
                task.n_points_alloc = -1;
                task.segment_json = sj;
                tasks.push_back(task);
            }
        }

        // Now run the tasks for the segment
        for (auto& task : tasks) {
            std::vector<Point2D>& sp = task.sp;
            if (sp.size() < 2) continue;

            std::vector<double> s = calculateArcLengths(sp); 
            double L = s.back();
            
            // Build segment-local spline if not using global
            Spline2D localSpline;
            bool useLocalSpline = (task.type == "file" && sp.size() >= 3 && !useGlobalSpline);
            if (useLocalSpline) localSpline.build(sp, s);

            std::string strat = task.segment_json.value("strategy", "uniform");
            json params = task.segment_json.value("parameters", json::object());

            // Task 4: Spacing matching
            if (task.segment_json.value("match_previous", false) && last_ds > 0) {
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
            else {
                if (task.n_points_alloc != -1) {
                    nT = task.n_points_alloc;
                } else {
                    nT = params.value("n_points", (int)sp.size());
                }
            }
            if (nT < 2) nT = 2;

            std::vector<double> tS;
            if (strat == "cosine") {
                for (int i = 0; i < nT; ++i) tS.push_back(L * (1.0 - std::cos(M_PI * i / (nT - 1))) * 0.5);
            } else if (strat == "geometric") {
                double ratio = 1.1;
                if (params.contains("spacing_start")) ratio = Spacing::solveGrowthRate(L, nT - 1, params["spacing_start"]);
                else if (params.contains("spacing_end")) ratio = 1.0 / Spacing::solveGrowthRate(L, nT - 1, params["spacing_end"]);
                else ratio = params.value("ratio", 1.1);

                double ratio_end = params.value("ratio_end", 1.0);
                if (ratio_end != 1.0 && nT >= 4) {
                    // Two-sided geometric: blend half from start, half from end
                    int nHalf = nT / 2 + 1;
                    auto tsA = Spacing::generateGeometric(L * 0.5, nHalf, ratio);
                    auto tsB = Spacing::generateGeometric(L * 0.5, nHalf, ratio_end);
                    tS.clear();
                    for (int i = 0; i < nHalf; ++i) tS.push_back(tsA[i]);
                    for (int i = (int)tsB.size() - 2; i >= 0; --i) tS.push_back(L - tsB[i]);
                    // Rescale to ensure endpoints are exactly [0, L]
                    if (!tS.empty()) { tS.front() = 0.0; tS.back() = L; }
                } else {
                    tS = Spacing::generateGeometric(L, nT, ratio);
                }
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
                if (useGlobalSpline && task.type == "file" && task.start_gp_idx != -1) {
                    // Map local s to global s
                    double start_s = globalS[task.start_gp_idx];
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
