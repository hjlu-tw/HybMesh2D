#ifndef BOUNDARY_LAYER_HPP
#define BOUNDARY_LAYER_HPP

#include "Mesh.hpp"
#include "Config.hpp"
#include <vector>

class BoundaryLayerGenerator {
public:
    BoundaryLayerGenerator(Mesh& mesh, const Config& config);

    // 從一組初始邊界節點 ID 生成邊界層，並回傳最後一層的厚度
    double generate(const std::vector<int>& boundaryNodeIds);

private:
    Mesh& m_mesh;
    const Config& m_config;
    double m_growthSign = 1.0; // 1.0 為向左(CCW時為內), -1.0 為向右(CCW時為外)

    // 自動偵測生長方向
    void detectGrowthDirection(const std::vector<int>& nodeIds);

    // 計算封閉曲線各點的平滑法向量
    std::vector<Vector2D> computeNormals(const std::vector<int>& nodeIds);
};

#endif
