#ifndef BOUNDARY_LAYER_HPP
#define BOUNDARY_LAYER_HPP

#include "Mesh.hpp"
#include "Config.hpp"
#include <vector>
#include <map>
#include <set>

enum class RayRole { None, Left, Center, Right, ML, MR, Bisector };

struct RayInfo {
    RayRole role = RayRole::None;
    Vector2D direction;
    double multiplier = 1.0;
    int rootNodeId = -1; // 幾何表面的原始節點 ID
};

struct FrontState {
    int geomId;
    std::vector<int> activeFront;
    double growthSign;
    int nTrans;
    std::map<int, Vector2D> nodeDirections;
    std::map<int, double> nodeStepMultipliers;
    std::map<int, RayInfo> rayInfoMap; // 追蹤每個節點的射線屬性
    std::map<int, std::vector<std::vector<int>>> blParaGroups; // rootNodeId -> vector of layers, each layer is vector of nodeIds
    std::vector<Vector2D> n1_init, n2_init;
    std::vector<bool> isConvexInit, isConcaveInit;
    std::vector<Point2D> pos_init;
    std::vector<int> fanNodeCounts;
    std::set<int> paraCenterNodes;
};

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
