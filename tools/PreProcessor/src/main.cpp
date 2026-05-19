#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <cmath>
#include <algorithm>
#include "json.hpp"
#include "GeomUtils.hpp"

using json = nlohmann::json;

struct ResampleSegment {
    int id;
    int startIndex;
    int endIndex;
    std::string strategy;
    json parameters;
};

std::vector<Point2D> loadGeometry(const std::string& filename) {
    std::vector<Point2D> points;
    std::ifstream ifs(filename);
    if (!ifs) {
        std::cerr << "Error: Could not open input file " << filename << std::endl;
        return points;
    }
    double x, y;
    while (ifs >> x >> y) {
        points.push_back({x, y});
    }
    return points;
}

void saveGeometry(const std::string& filename, const std::vector<Point2D>& points) {
    std::ofstream ofs(filename);
    if (!ofs) {
        std::cerr << "Error: Could not open output file " << filename << std::endl;
        return;
    }
    ofs << std::fixed << std::setprecision(10);
    for (const auto& p : points) {
        ofs << p.x << " " << p.y << "\n";
    }
}

// 計算累積弧長
std::vector<double> calculateArcLengths(const std::vector<Point2D>& points) {
    std::vector<double> s(points.size(), 0.0);
    for (size_t i = 1; i < points.size(); ++i) {
        double dx = points[i].x - points[i-1].x;
        double dy = points[i].y - points[i-1].y;
        s[i] = s[i-1] + std::sqrt(dx*dx + dy*dy);
    }
    return s;
}

// 線性插值
Point2D interpolate(const std::vector<Point2D>& points, const std::vector<double>& s, double targetS) {
    if (targetS <= s.front()) return points.front();
    if (targetS >= s.back()) return points.back();

    auto it = std::lower_bound(s.begin(), s.end(), targetS);
    int idx = std::distance(s.begin(), it);
    
    if (idx == 0) return points.front();
    
    double s0 = s[idx-1];
    double s1 = s[idx];
    double t = (targetS - s0) / (s1 - s0);
    
    return points[idx-1] * (1.0 - t) + points[idx] * t;
}

// 簡易數學表達式解析器 (遞迴下降法)
class MathEvaluator {
public:
    MathEvaluator(const std::string& expr) : expression(expr), pos(0) {}

    double eval(double xVal) {
        x = xVal;
        pos = 0;
        return parseExpression();
    }

private:
    std::string expression;
    size_t pos;
    double x;

    void skipWhitespace() {
        while (pos < expression.length() && isspace(expression[pos])) pos++;
    }

    double parseExpression() {
        double result = parseTerm();
        skipWhitespace();
        while (pos < expression.length() && (expression[pos] == '+' || expression[pos] == '-')) {
            char op = expression[pos++];
            double nextTerm = parseTerm();
            if (op == '+') result += nextTerm;
            else result -= nextTerm;
            skipWhitespace();
        }
        return result;
    }

    double parseTerm() {
        double result = parseFactor();
        skipWhitespace();
        while (pos < expression.length() && (expression[pos] == '*' || expression[pos] == '/')) {
            char op = expression[pos++];
            double nextFactor = parseFactor();
            if (op == '*') result *= nextFactor;
            else result /= nextFactor;
            skipWhitespace();
        }
        return result;
    }

    double parseFactor() {
        double result = parseBase();
        skipWhitespace();
        if (pos < expression.length() && expression[pos] == '^') {
            pos++;
            double exponent = parseFactor();
            result = std::pow(result, exponent);
        }
        return result;
    }

    double parseBase() {
        skipWhitespace();
        if (pos >= expression.length()) return 0;

        if (expression[pos] == '(') {
            pos++;
            double result = parseExpression();
            skipWhitespace();
            if (pos < expression.length() && expression[pos] == ')') pos++;
            return result;
        }

        if (expression[pos] == '-') {
            pos++;
            return -parseBase();
        }

        if (isdigit(expression[pos]) || expression[pos] == '.') {
            size_t start = pos;
            while (pos < expression.length() && (isdigit(expression[pos]) || expression[pos] == '.')) pos++;
            return std::stod(expression.substr(start, pos - start));
        }

        if (isalpha(expression[pos])) {
            size_t start = pos;
            while (pos < expression.length() && isalnum(expression[pos])) pos++;
            std::string name = expression.substr(start, pos - start);
            
            if (name == "x") return x;
            
            skipWhitespace();
            if (pos < expression.length() && expression[pos] == '(') {
                pos++;
                double arg = parseExpression();
                skipWhitespace();
                if (pos < expression.length() && expression[pos] == ')') pos++;
                
                if (name == "sin") return std::sin(arg);
                if (name == "cos") return std::cos(arg);
                if (name == "tan") return std::tan(arg);
                if (name == "exp") return std::exp(arg);
                if (name == "log") return std::log(arg);
                if (name == "sqrt") return std::sqrt(arg);
                if (name == "abs") return std::abs(arg);
            }
            return 0; // Unknown name
        }

        return 0;
    }
};

// 從公式產生點
std::vector<Point2D> generateCurvePoints(const std::string& formula, const json& params) {
    std::vector<Point2D> points;
    std::vector<double> range = params.value("range", std::vector<double>{0.0, 1.0});
    int nPoints = params.value("n_points", 50);
    double xMin = range[0];
    double xMax = range[1];

    if (formula == "sin") {
        double amp = params.value("amplitude", 1.0);
        double freq = params.value("frequency", 1.0);
        double phase = params.value("phase", 0.0);
        double offsetY = params.value("offset_y", 0.0);
        for (int i = 0; i < nPoints; ++i) {
            double x = xMin + (xMax - xMin) * i / (nPoints - 1);
            double y = amp * std::sin(freq * x + phase) + offsetY;
            points.push_back({x, y});
        }
    } else if (formula == "polynomial") {
        std::vector<double> coeffs = params.value("coeffs", std::vector<double>{0.0, 1.0}); // Default y = x
        for (int i = 0; i < nPoints; ++i) {
            double x = xMin + (xMax - xMin) * i / (nPoints - 1);
            double y = 0;
            double xPow = 1.0;
            for (double c : coeffs) {
                y += c * xPow;
                xPow *= x;
            }
            points.push_back({x, y});
        }
    } else if (formula == "line") {
        double x0 = params.value("x0", 0.0);
        double y0 = params.value("y0", 0.0);
        double x1 = params.value("x1", 1.0);
        double y1 = params.value("y1", 1.0);
        for (int i = 0; i < nPoints; ++i) {
            double t = static_cast<double>(i) / (nPoints - 1);
            points.push_back({x0 + t * (x1 - x0), y0 + t * (y1 - y0)});
        }
    } else {
        // 使用 MathEvaluator 解析任意公式
        MathEvaluator evaluator(formula);
        for (int i = 0; i < nPoints; ++i) {
            double x = xMin + (xMax - xMin) * i / (nPoints - 1);
            double y = evaluator.eval(x);
            points.push_back({x, y});
        }
    }
    return points;
}

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cout << "Usage: " << argv[0] << " <config.json>" << std::endl;
        return 1;
    }

    std::ifstream f(argv[1]);
    if (!f) {
        std::cerr << "Error: Could not open config file " << argv[1] << std::endl;
        return 1;
    }
    json config = json::parse(f);

    std::string outputFile = config["output_file"];
    std::string globalInputFile = config.value("input_file", "");

    std::vector<Point2D> globalPoints;
    if (!globalInputFile.empty()) {
        globalPoints = loadGeometry(globalInputFile);
    }

    std::vector<Point2D> resampledPoints;

    for (auto& segJson : config["segments"]) {
        std::string type = segJson.value("type", "file");
        std::vector<Point2D> segmentPoints;

        if (type == "curve") {
            std::string formula = segJson.value("formula", "line");
            segmentPoints = generateCurvePoints(formula, segJson["parameters"]);
        } else {
            // 原有的從檔案讀取邏輯
            int startIdx = segJson["start_index"];
            int endIdx = segJson["end_index"];
            
            if (globalPoints.empty()) {
                std::cerr << "Error: Global input_file is required for 'file' type segments." << std::endl;
                continue;
            }

            // 處理 -1 代表最後一個點
            if (endIdx == -1) endIdx = globalPoints.size() - 1;

            for (int i = startIdx; i <= endIdx; ++i) {
                segmentPoints.push_back(globalPoints[i]);
            }
        }

        if (segmentPoints.size() < 2) continue;
if (segmentPoints.size() < 2) continue;

std::vector<double> s = calculateArcLengths(segmentPoints);
double totalLength = s.back();
std::vector<Point2D> newSegmentPoints;

std::string strategy = segJson.value("strategy", "uniform");

int nTargetPoints = segJson["parameters"].value("n_points", (int)segmentPoints.size());
if (nTargetPoints < 2) nTargetPoints = 2;

std::vector<double> targetS;
if (strategy == "cosine") {
    for (int i = 0; i < nTargetPoints; ++i) {
        double xi = static_cast<double>(i) / (nTargetPoints - 1);
        targetS.push_back(totalLength * (1.0 - std::cos(M_PI * xi)) * 0.5);
    }
} else if (strategy == "geometric") {
    double r = segJson["parameters"].value("ratio", 1.1);
    if (std::abs(r - 1.0) < 1e-6) {
        for (int i = 0; i < nTargetPoints; ++i) targetS.push_back(totalLength * i / (nTargetPoints - 1));
    } else {
        double d0 = totalLength * (1.0 - r) / (1.0 - std::pow(r, nTargetPoints - 1));
        targetS.push_back(0.0);
        double currentS = 0.0;
        for (int i = 1; i < nTargetPoints; ++i) {
            currentS += d0 * std::pow(r, i - 1);
            targetS.push_back(currentS);
        }
    }
} else if (strategy == "tanh") {
    double delta = segJson["parameters"].value("intensity", 2.0);
    for (int i = 0; i < nTargetPoints; ++i) {
        double xi = static_cast<double>(i) / (nTargetPoints - 1);
        double val = 0.5 * (1.0 + std::tanh(delta * (2.0 * xi - 1.0)) / std::tanh(delta));
        targetS.push_back(totalLength * val);
    }
} else if (strategy == "curvature") {
    double sensitivity = segJson["parameters"].value("sensitivity", 1.0);
    // 1. 計算每個點的局部轉角
    std::vector<double> weights(segmentPoints.size(), 1.0);
    for (size_t i = 1; i < segmentPoints.size() - 1; ++i) {
        Vector2D v1 = (segmentPoints[i] - segmentPoints[i-1]).normalized();
        Vector2D v2 = (segmentPoints[i+1] - segmentPoints[i]).normalized();
        double dot = std::clamp(v1.dot(v2), -1.0, 1.0);
        double angle = std::acos(dot);
        weights[i] = 1.0 + sensitivity * angle;
    }
    // 2. 建立累計權重空間 (C-space)
    std::vector<double> cSpace(segmentPoints.size(), 0.0);
    for (size_t i = 1; i < segmentPoints.size(); ++i) {
        double avgW = (weights[i-1] + weights[i]) * 0.5;
        double ds = s[i] - s[i-1];
        cSpace[i] = cSpace[i-1] + avgW * ds;
    }
    double totalC = cSpace.back();
    // 3. 在 C-space 均勻取樣並映射回弧長 s
    for (int i = 0; i < nTargetPoints; ++i) {
        double targetC = totalC * i / (nTargetPoints - 1);
        auto it = std::lower_bound(cSpace.begin(), cSpace.end(), targetC);
        int idx = std::distance(cSpace.begin(), it);
        if (idx == 0) targetS.push_back(0.0);
        else {
            double c0 = cSpace[idx-1], c1 = cSpace[idx];
            double s0 = s[idx-1], s1 = s[idx];
            double t = (targetC - c0) / (c1 - c0);
            targetS.push_back(s0 + t * (s1 - s0));
        }
    }
} else { // uniform (fallback)
    for (int i = 0; i < nTargetPoints; ++i) {
        targetS.push_back((totalLength * i) / (nTargetPoints - 1));
    }
}

for (double ts : targetS) {
    newSegmentPoints.push_back(interpolate(segmentPoints, s, ts));
}


        // 合併點，避免重疊的連接點
        if (!resampledPoints.empty() && !newSegmentPoints.empty()) {
            // 檢查是否足夠接近，如果太近才 pop
            double dx = resampledPoints.back().x - newSegmentPoints.front().x;
            double dy = resampledPoints.back().y - newSegmentPoints.front().y;
            if (std::sqrt(dx*dx + dy*dy) < 1e-9) {
                resampledPoints.pop_back(); 
            }
        }
        resampledPoints.insert(resampledPoints.end(), newSegmentPoints.begin(), newSegmentPoints.end());
    }

    // 處理封閉迴圈：如果使用者指定為封閉迴圈且頭尾不相連，自動補上起點
    bool isClosed = config.value("is_closed", false);
    if (isClosed && !resampledPoints.empty()) {
        double dx = resampledPoints.front().x - resampledPoints.back().x;
        double dy = resampledPoints.front().y - resampledPoints.back().y;
        if (std::sqrt(dx * dx + dy * dy) > 1e-9) {
            resampledPoints.push_back(resampledPoints.front());
        }
    }

    saveGeometry(outputFile, resampledPoints);
    std::cout << "Successfully processed geometry to " << outputFile << " (" << resampledPoints.size() << " points)" << std::endl;

    return 0;
}
