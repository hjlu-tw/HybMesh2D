#ifndef BOUNDARY_LAYER_HPP
#define BOUNDARY_LAYER_HPP

#include "Mesh.hpp"
#include "Config.hpp"
#include <vector>

#include <map>

struct FrontState {
    int geomId;
    std::vector<int> activeFront;
    double growthSign;
    int nTrans;
    std::map<int, Vector2D> nodeDirections;
    std::map<int, double> nodeStepMultipliers;
    std::vector<Vector2D> n1_init, n2_init;
    std::vector<bool> isConvexInit, isConcaveInit;
    std::vector<Point2D> pos_init;
    std::vector<int> fanNodeCounts;
};

#include <set>

class BoundaryLayerGenerator {
public:
    BoundaryLayerGenerator(Mesh& mesh, const Config& config);

    // 從多組初始邊界節點 ID 同步生成邊界層，並回傳最後一層的厚度
    double generate(const std::vector<std::vector<int>>& allBoundaryNodeIds);

private:
    Mesh& m_mesh;
    const Config& m_config;

    // 自動偵測生長方向
    double detectGrowthDirection(const std::vector<int>& nodeIds);
    bool checkCollision(Point2D p, double threshold, const std::set<int>& ignoreIds, int currentGeomId);
};

#endif
