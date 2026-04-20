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

    // 取得法向量 (逆時針旋轉 90 度)
    Vector2D normal() const { return {-y, x}; }
};

using Point2D = Vector2D;

#endif
