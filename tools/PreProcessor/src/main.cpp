#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cmath>
#include <algorithm>
#include <iomanip>
#include "json.hpp"
#include "GeomUtils.hpp"

using json = nlohmann::json;

// 三次樣條插值類別 (Natural Cubic Spline)
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

// 數值求解器：根據總長 L, 間隔數 n, 初始間距 d0 求解增長率 r
// 方程式：f(r) = d0 * (r^n - 1) / (r - 1) - L = 0
double solveGrowthRate(double L, int n, double d0) {
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
    return std::max(0.1, std::min(r, 10.0)); // 限制合理範圍
}

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
        s[i] = s[i-1] + (points[i] - points[i-1]).length();
    return s;
}

Point2D interpolateLinear(const std::vector<Point2D>& points, const std::vector<double>& s, double targetS) {
    if (targetS <= s.front()) return points.front();
    if (targetS >= s.back()) return points.back();
    auto it = std::lower_bound(s.begin(), s.end(), targetS);
    int idx = std::distance(s.begin(), it);
    if (idx == 0) return points.front();
    double s0 = s[idx-1], s1 = s[idx], t = (targetS - s0) / (s1 - s0);
    return points[idx-1] * (1.0 - t) + points[idx] * t;
}

class MathEvaluator {
public:
    MathEvaluator(const std::string& expr) : expression(expr), pos(0) {}
    double eval(double v, char name = 'x') { xV = (name=='x'?v:0); tV = (name=='t'?v:0); pos = 0; return parseExpression(); }
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

std::vector<Point2D> generateCurvePoints(const json& seg) {
    std::vector<Point2D> pts; const json& p = seg["parameters"];
    std::vector<double> r = p.value("range", std::vector<double>{0.0, 1.0});
    int n = p.value("n_points", 50); double t0 = r[0], t1 = r[1];
    if (seg.contains("x_formula") && seg.contains("y_formula")) {
        MathEvaluator ex(seg["x_formula"]), ey(seg["y_formula"]);
        for (int i = 0; i < n; ++i) { double t = t0 + (t1-t0)*i/(n-1); pts.push_back({ex.eval(t,'t'), ey.eval(t,'t')}); }
    } else {
        std::string f = seg.value("formula", "line");
        if (f == "sin") {
            double a = p.value("amplitude", 1.0), fr = p.value("frequency", 1.0), ph = p.value("phase", 0.0), oy = p.value("offset_y", 0.0);
            for (int i = 0; i < n; ++i) { double x = t0+(t1-t0)*i/(n-1); pts.push_back({x, a*std::sin(fr*x+ph)+oy}); }
        } else if (f == "line") {
            double x0 = p.value("x0", 0.0), y0 = p.value("y0", 0.0), x1 = p.value("x1", 1.0), y1 = p.value("y1", 1.0);
            for (int i = 0; i < n; ++i) { double t = (double)i/(n-1); pts.push_back({x0+t*(x1-x0), y0+t*(y1-y0)}); }
        } else {
            MathEvaluator ev(f); for (int i = 0; i < n; ++i) { double x = t0+(t1-t0)*i/(n-1); pts.push_back({x, ev.eval(x,'x')}); }
        }
    }
    return pts;
}

std::vector<int> detectFeaturePoints(const std::vector<Point2D>& points, double threshold) {
    std::vector<int> feat = {0}; if (points.size() < 3) { feat.push_back((int)points.size()-1); return feat; }
    double thr = threshold * M_PI / 180.0;
    for (size_t i = 1; i < points.size() - 1; ++i) {
        Vector2D v1 = (points[i]-points[i-1]).normalized(), v2 = (points[i+1]-points[i]).normalized();
        if ((points[i]-points[i-1]).length() < 1e-10 || (points[i+1]-points[i]).length() < 1e-10) continue;
        if (std::acos(std::clamp(v1.dot(v2), -1.0, 1.0)) > thr) feat.push_back((int)i);
    }
    feat.push_back((int)points.size()-1); feat.erase(std::unique(feat.begin(), feat.end()), feat.end());
    return feat;
}

void processElement(const json& config) {
    std::vector<Point2D> gp = loadGeometry(config.value("input_file", ""));
    if (config.value("is_closed", false) && !gp.empty()) {
        if ((gp.front() - gp.back()).length() > 1e-9) gp.push_back(gp.front());
    }
    std::vector<Point2D> resPts;
    for (const auto& sj : config["segments"]) {
        std::string type = sj.value("type", "file"); bool autoSplit = sj.value("auto_split", false);
        std::vector<std::pair<int, int>> ranges;
        if (type == "curve") ranges.push_back({-1,-1});
        else {
            int s = sj.value("start_index", 0), e = sj.value("end_index", -1);
            if (e == -1 && !gp.empty()) e = (int)gp.size()-1;
            if (autoSplit && !gp.empty()) {
                std::vector<Point2D> sub; for(int i=s; i<=e; ++i) sub.push_back(gp[i]);
                std::vector<int> f = detectFeaturePoints(sub, sj.value("split_threshold", 20.0));
                for(size_t i=0; i<f.size()-1; ++i) ranges.push_back({s+f[i], s+f[i+1]});
            } else ranges.push_back({s, e});
        }
        for (auto& r : ranges) {
            std::vector<Point2D> sp; if (type == "curve") sp = generateCurvePoints(sj); else for(int i=r.first; i<=r.second; ++i) sp.push_back(gp[i]);
            if (sp.size() < 2) continue;
            std::vector<double> s = calculateArcLengths(sp); double L = s.back();
            Spline2D spline; bool useSpline = (type == "file" && sp.size() >= 3); if (useSpline) spline.build(sp, s);
            std::string strat = sj.value("strategy", "uniform");
            int nT; if (sj["parameters"].contains("spacing")) nT = std::max(2, (int)std::round(L / (double)sj["parameters"]["spacing"]) + 1);
            else nT = sj["parameters"].value("n_points", (int)sp.size());
            if (nT < 2) nT = 2;
            std::vector<double> tS;
            if (strat == "cosine") for(int i=0; i<nT; ++i) tS.push_back(L*(1.0-std::cos(M_PI*i/(nT-1)))*0.5);
            else if (strat == "geometric") {
                double ratio = 1.1;
                if (sj["parameters"].contains("spacing_start")) ratio = solveGrowthRate(L, nT-1, sj["parameters"]["spacing_start"]);
                else if (sj["parameters"].contains("spacing_end")) ratio = 1.0 / solveGrowthRate(L, nT-1, sj["parameters"]["spacing_end"]);
                else ratio = sj["parameters"].value("ratio", 1.1);
                if (std::abs(ratio-1.0) < 1e-6) for(int i=0; i<nT; ++i) tS.push_back(L*i/(nT-1));
                else {
                    double d0 = L*(1.0-ratio)/(1.0-std::pow(ratio, nT-1)); tS.push_back(0.0);
                    double cur = 0; for(int i=1; i<nT; ++i) { cur += d0*std::pow(ratio, i-1); tS.push_back(cur); }
                }
            } else if (strat == "tanh") {
                double dlt = sj["parameters"].value("intensity", 2.0);
                if (sj["parameters"].contains("spacing_start") && sj["parameters"].contains("spacing_end"))
                    dlt = std::log(L / std::min((double)sj["parameters"]["spacing_start"], (double)sj["parameters"]["spacing_end"])) * 0.5;
                for(int i=0; i<nT; ++i) { double xi = (double)i/(nT-1); tS.push_back(L*0.5*(1.0+std::tanh(dlt*(2.0*xi-1.0))/std::tanh(dlt))); }
            } else if (strat == "curvature") {
                double sens = sj["parameters"].value("sensitivity", 1.0); std::vector<double> w(sp.size(), 1.0);
                for (size_t i=1; i<sp.size()-1; ++i) {
                    Vector2D v1=(sp[i]-sp[i-1]).normalized(), v2=(sp[i+1]-sp[i]).normalized();
                    w[i] = 1.0 + sens * std::acos(std::clamp(v1.dot(v2), -1.0, 1.0));
                }
                std::vector<double> cS(sp.size(), 0.0); for(size_t i=1; i<sp.size(); ++i) cS[i]=cS[i-1]+(w[i-1]+w[i])*0.5*(s[i]-s[i-1]);
                for (int i=0; i<nT; ++i) {
                    double tC = cS.back()*i/(nT-1); auto it = std::lower_bound(cS.begin(), cS.end(), tC);
                    int idx = std::distance(cS.begin(), it);
                    if (idx == 0) tS.push_back(0.0); else {
                        double t = (tC-cS[idx-1])/(cS[idx]-cS[idx-1]); tS.push_back(s[idx-1]+t*(s[idx]-s[idx-1]));
                    }
                }
            } else for(int i=0; i<nT; ++i) tS.push_back(L*i/(nT-1));
            for (double ts : tS) resPts.push_back(useSpline ? spline.eval(ts) : interpolateLinear(sp, s, ts));
            if (resPts.size() >= 2) { /* merge join point check could go here if needed */ }
        }
    }
    if (config.contains("transform")) {
        const auto& t = config["transform"]; double sc = t.value("scale", 1.0), ang = t.value("rotate", 0.0)*M_PI/180.0;
        std::vector<double> tr = t.value("translate", std::vector<double>{0.0, 0.0});
        for (auto& p : resPts) {
            p.x *= sc; p.y *= sc; double xN = p.x*std::cos(ang)-p.y*std::sin(ang), yN = p.x*std::sin(ang)+p.y*std::cos(ang);
            p.x = xN+tr[0]; p.y = yN+tr[1];
        }
    }
    saveGeometry(config.value("output_file", "Results/output.dat"), resPts);
    std::cout << "Successfully processed element to " << config.value("output_file", "Results/output.dat") << " (" << resPts.size() << " points)" << std::endl;
}

int main(int argc, char* argv[]) {
    if (argc < 2) return 1;
    std::ifstream f(argv[1]); if (!f) return 1;
    json c = json::parse(f);
    if (c.contains("elements") && c["elements"].is_array()) for (const auto& e : c["elements"]) processElement(e);
    else processElement(c);
    return 0;
}
