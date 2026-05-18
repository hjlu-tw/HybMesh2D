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

    std::string inputFile = config["input_file"];
    std::string outputFile = config["output_file"];

    std::vector<Point2D> originalPoints = loadGeometry(inputFile);
    if (originalPoints.empty()) return 1;

    // 處理封閉迴圈：如果使用者指定為封閉迴圈且頭尾不相連，自動補上起點
    bool isClosed = config.value("is_closed", false);
    if (isClosed && originalPoints.size() > 1) {
        double dx = originalPoints.front().x - originalPoints.back().x;
        double dy = originalPoints.front().y - originalPoints.back().y;
        if (std::sqrt(dx * dx + dy * dy) > 1e-12) {
            originalPoints.push_back(originalPoints.front());
        }
    }

    std::vector<Point2D> resampledPoints;

    for (auto& segJson : config["segments"]) {
        int startIdx = segJson["start_index"];
        int endIdx = segJson["end_index"];
        std::string strategy = segJson["strategy"];
        
        // 處理 -1 代表最後一個點
        if (endIdx == -1) endIdx = originalPoints.size() - 1;

        // 提取該線段的點
        std::vector<Point2D> segmentPoints;
        for (int i = startIdx; i <= endIdx; ++i) {
            segmentPoints.push_back(originalPoints[i]);
        }

        if (segmentPoints.size() < 2) continue;

        std::vector<double> s = calculateArcLengths(segmentPoints);
        double totalLength = s.back();
        std::vector<Point2D> newSegmentPoints;

        if (strategy == "uniform") {
            int nPoints = segJson["parameters"]["n_points"];
            for (int i = 0; i < nPoints; ++i) {
                double targetS = (totalLength * i) / (nPoints - 1);
                newSegmentPoints.push_back(interpolate(segmentPoints, s, targetS));
            }
        } else {
            // 如果策略不支援，就維持原樣
            newSegmentPoints = segmentPoints;
        }

        // 合併點，避免重疊的連接點
        if (!resampledPoints.empty() && !newSegmentPoints.empty()) {
            resampledPoints.pop_back(); 
        }
        resampledPoints.insert(resampledPoints.end(), newSegmentPoints.begin(), newSegmentPoints.end());
    }

    saveGeometry(outputFile, resampledPoints);
    std::cout << "Successfully resampled surface to " << outputFile << std::endl;

    return 0;
}
