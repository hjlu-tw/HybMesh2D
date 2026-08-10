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
    // Per-geometry boundary-layer parameters (global defaults + this geometry's
    // overrides) and the running layer thickness for this front. Each front
    // advances its own thickness, so geometries may differ in initial
    // thickness / growth rate / layer count.
    BLParams bl;
    double currentH = 0.0;
    std::map<int, Vector2D> nodeDirections;
    std::map<int, double> nodeStepMultipliers;
    std::map<int, RayInfo> rayInfoMap; // 追蹤每個節點的射線屬性
    std::map<int, std::vector<std::vector<int>>> blParaGroups; // rootNodeId -> vector of layers, each layer is vector of nodeIds
    std::vector<Vector2D> n1_init, n2_init;
    std::vector<bool> isConvexInit, isConcaveInit;
    std::vector<Point2D> pos_init;
    std::vector<int> fanNodeCounts;
    std::set<int> paraCenterNodes;
    // Nodes at a BL / no-BL junction whose growth ray is pinned to their own BL
    // edge's outward normal (see the junction handling in generate()): the BL's
    // lateral cap grows perpendicular to the BL wall at full height instead of
    // splitting the corner with the bisector or leaning onto the no-BL edge.
    std::set<int> junctionCapNodes;
    // no-BL surface nodes ABSORBED by an adjacent SLIDE junction: they lie within
    // the BL height along a wall/symmetry edge, so the sliding cap column is the
    // boundary there instead. Dropped from the FINAL front ring (and thus the
    // far-field inner boundary) so the front does not fold back on them.
    std::set<int> absorbedNoBLNodes;
    // --- 4-case junction scheme (blJunctionMethod == 1) ---------------------
    // For each BL/no-BL junction node (a growing node with a no-BL neighbour) the
    // flow-facing angle theta is binned into case 1..4 (see generate()). Case 1
    // (concave) slides along the neighbour edge + absorbs it; cases 2/3/4 grow a
    // free full-height lateral cap whose exposed column edges become far-field
    // inner-boundary constraints so the wedge to the neighbour edge is triangulated.
    std::map<int, int> junctionCase;                 // root surface nodeId -> case 1..4
    std::map<int, std::vector<int>> junctionColumns; // root surface nodeId -> [surface, L1, ..., outer] (cases 2/3/4)
    std::map<int, int> nodeToJunctionRoot;           // any cap-column nodeId -> its root surface nodeId
    // Case 1 (slide) only. The slide RE-DISCRETIZES the no-BL wall run it absorbs:
    // its column lies ON that wall, so the column's lateral edges are the domain
    // boundary there, in place of the absorbed surface edges. Both halves are kept
    // so the BC of the replaced wall can be carried onto the replacing edges by
    // construction (see the slide-BC registration in generate()) — geometry cannot
    // recover it, because the column is a straight ray while the wall may curve.
    std::map<int, std::vector<int>> slideColumns;    // root -> [surface, L1, ..., outer]
    std::map<int, std::vector<int>> slideWallRun;    // root -> [root, absorbed..., first surviving node]
};

class BoundaryLayerGenerator {
public:
    BoundaryLayerGenerator(Mesh& mesh, const Config& config);

    // 從多組初始邊界節點 ID 同步生成邊界層，並回傳最後一層的厚度。
    // growModes (若提供) 與 allBoundaryNodeIds 平行，逐迴圈指定生長方向：
    //   0 = auto (沿用矩形域框判定, 外流預設), +1 = 往迴圈內側 (內流壁面),
    //  -1 = 往迴圈外側 (障礙物 / 島嶼)。空 vector -> 全部 auto。
    // blParamsPerLoop (若提供) 與 allBoundaryNodeIds 平行，逐迴圈指定該幾何的
    // 邊界層參數；缺項或空 vector -> 使用全域 config 參數。
    double generate(const std::vector<std::vector<int>>& allBoundaryNodeIds,
                    const std::vector<int>& growModes = {},
                    const std::vector<BLParams>& blParamsPerLoop = {});

private:
    Mesh& m_mesh;
    const Config& m_config;

    // 偵測生長方向。growMode: 0=auto(域框判定), +1=內側, -1=外側。
    double detectGrowthDirection(const std::vector<int>& nodeIds, int growMode = 0);
    bool checkCollision(Point2D p, double threshold, const std::set<int>& ignoreIds, int currentGeomId);
};

#endif
