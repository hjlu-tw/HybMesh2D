#ifndef GEOM_UTILS_HPP
#define GEOM_UTILS_HPP

#include <cmath>
#include <iostream>

struct Vector2D {
    double x, y;

    Vector2D operator+(const Vector2D& v) const { return {x + v.x, y + v.y}; }
    Vector2D operator-(const Vector2D& v) const { return {x - v.x, y - v.y}; }
    Vector2D operator*(double s) const { return {x * s, y * s}; }
    Vector2D operator/(double s) const { return {x / s, y / s}; }

    double dot(const Vector2D& v) const { return x * v.x + y * v.y; }
    double cross(const Vector2D& v) const { return x * v.y - y * v.x; }
    double lengthSq() const { return x * x + y * y; }
    double length() const { return std::sqrt(lengthSq()); }

    Vector2D normalized() const {
        double l = length();
        return (l > 1e-12) ? (*this / l) : Vector2D{0, 0};
    }

    // 取得左側法向量 (逆時針旋轉 90 度)
    Vector2D leftNormal() const { return {-y, x}; }
    // 取得右側法向量 (順時針旋轉 90 度)
    Vector2D rightNormal() const { return {y, -x}; }
};

using Point2D = Vector2D;

// 檢查線段 (a,b) 與 (c,d) 是否相交 (不包含頂點重合或共線)
inline bool segmentsIntersect(Point2D a, Point2D b, Point2D c, Point2D d) {
    auto ccw = [](Point2D p1, Point2D p2, Point2D p3) {
        double val = (p2.x - p1.x) * (p3.y - p1.y) - (p2.y - p1.y) * (p3.x - p1.x);
        if (std::abs(val) < 1e-12) return 0;
        return (val > 0) ? 1 : -1;
    };
    int ab_c = ccw(a, b, c);
    int ab_d = ccw(a, b, d);
    int cd_a = ccw(c, d, a);
    int cd_b = ccw(c, d, b);
    return (ab_c * ab_d < 0 && cd_a * cd_b < 0);
}

inline Point2D getIntersectionPoint(Point2D a, Point2D b, Point2D c, Point2D d) {
    double denom = (b - a).cross(d - c);
    if (std::abs(denom) < 1e-12) return (a + b + c + d) * 0.25;
    double t = (c - a).cross(d - c) / denom;
    return a + (b - a) * t;
}

#endif
