#include "MbShared.hpp"

#include <array>

// The shared-edge half of the multi-block smoother. See include/MbShared.hpp for
// what this answers and why it is its own module; this file is the derivation.
//
// NOTHING HERE COMPARES A POSITION. Every answer below comes from node IDS and
// from the declaration's own published lists (`MbResult::wallSpecs` and
// `MbResult::sharedEdges`), which is what keeps this module inside the rule the
// whole path rests on: welding is by allocation, not by comparison, and a
// smoother that reconciled two coordinates would have put a tolerance back into a
// module that has none. `nodes` is not read in this file at all — grep it.
namespace {

using hybmesh::MbBlock;
using hybmesh::MbGhostFrame;
using hybmesh::MbResult;
using hybmesh::MbSide;
using hybmesh::MbSideWalk;

// The node id at station `k`, `tt` grid lines across, in the SIDE's frame.
// -1 outside the block, on the rule this module's header states: an index with no
// node behind it says so rather than being clamped onto one that has.
int sideId(const MbBlock& b, const MbSideWalk& w, int k, int tt) {
    const int i = w.i(k, tt), j = w.j(k, tt);
    if (i < 0 || j < 0 || i >= b.ni || j >= b.nj) return -1;
    return b.nodeAt(i, j);
}

// THE GHOST LAYER ACROSS ONE SHARED EDGE, in the frame of `bIdx`.
//
// The two sides are welded, so they are the SAME node ids in some order; which
// order is read off those ids rather than derived from either block's winding,
// because a frame may be turned a quarter turn (the shipped H-grid turns one) and
// then the two blocks genuinely disagree about which way the shared line runs.
//
// EVERY STATION IS CHECKED, not just the two ends. Matching the ends and assuming
// the middle is what would let a mis-welded interior line smooth against the
// wrong neighbour node — a wrong mesh with no error, which is the one outcome
// this path refuses everywhere else. A side that does not match station for
// station gets NO ghost layer, so every node on it stays frozen.
bool addGhosts(MbGhostFrame& frame, const MbBlock& bA, MbSide sA,
               const MbBlock& bB, MbSide sB) {
    const MbSideWalk wA = hybmesh::mbSideWalk(bA, sA);
    const MbSideWalk wB = hybmesh::mbSideWalk(bB, sB);
    if (!wA.ok || !wB.ok || wA.n != wB.n || wA.n < 2) return false;
    const int n = wA.n;
    const int idA0 = sideId(bA, wA, 0, wA.t0);
    bool rev;
    if (idA0 >= 0 && idA0 == sideId(bB, wB, 0, wB.t0)) rev = false;
    else if (idA0 >= 0 && idA0 == sideId(bB, wB, n - 1, wB.t0)) rev = true;
    else return false;
    for (int k = 0; k < n; ++k) {
        const int kb = rev ? n - 1 - k : k;
        if (sideId(bA, wA, k, wA.t0) != sideId(bB, wB, kb, wB.t0)) return false;
    }
    // Written only once every station has matched, so a refusal leaves the frame
    // exactly as it was rather than half extended.
    const size_t w = static_cast<size_t>(frame.ni) + 2;
    for (int k = 0; k < n; ++k) {
        const int kb = rev ? n - 1 - k : k;
        const int ghost = sideId(bB, wB, kb, wB.t1);
        if (ghost < 0) return false;
        const int i = wA.i(k, wA.tOut), j = wA.j(k, wA.tOut);
        frame.ext[static_cast<size_t>(j + 1) * w + static_cast<size_t>(i + 1)] = ghost;
    }
    return true;
}

// HOW MANY OF A BLOCK'S DECLARED WALLS RUN PERPENDICULAR TO ONE SIDE — the score
// the ownership rule is decided on.
//
// The two perpendicular sides come from `mbSideAxis`'s own derivation, read here
// rather than restated: south and north run along i, so their perpendiculars are
// west and east, and the other two the other way round. It is the SAME derivation
// the fill uses to pick the edge a wall's first-cell height is asked of.
int perpWalls(const std::array<bool, 4>& wall, MbSide side) {
    const bool alongI = hybmesh::mbSideAxis(side).alongI;
    const size_t a = alongI ? hybmesh::MB_WEST : hybmesh::MB_SOUTH;
    const size_t b = alongI ? hybmesh::MB_EAST : hybmesh::MB_NORTH;
    return (wall[a] ? 1 : 0) + (wall[b] ? 1 : 0);
}

// Which SIDES of a block a node at (i, j) lies on. 0 for a strictly interior
// node, 1 for a node on the interior of one side, 2 for a corner of the block.
// (A block thinner than 3 either way has nodes on two opposite sides at once, and
// counting them as corners is the right answer: nothing about them is interior.)
int sidesAt(const MbBlock& b, int i, int j, MbSide& only) {
    int count = 0;
    if (j == 0)         { only = hybmesh::MB_SOUTH; ++count; }
    if (i == b.ni - 1)  { only = hybmesh::MB_EAST;  ++count; }
    if (j == b.nj - 1)  { only = hybmesh::MB_NORTH; ++count; }
    if (i == 0)         { only = hybmesh::MB_WEST;  ++count; }
    return count;
}

}  // namespace

hybmesh::MbSmoothPlan hybmesh::mbSmoothPlan(const MbResult& mesh) {
    MbSmoothPlan plan;
    const size_t nb = mesh.blocks.size();
    plan.frames.resize(nb);
    plan.moves.resize(nb);
    for (size_t bi = 0; bi < nb; ++bi) {
        const MbBlock& b = mesh.blocks[bi];
        MbGhostFrame& fr = plan.frames[bi];
        fr.ni = b.ni;
        fr.nj = b.nj;
        const size_t want = static_cast<size_t>(b.ni) * static_cast<size_t>(b.nj);
        if (b.ni < 2 || b.nj < 2 || b.nodeIds.size() != want) continue;
        const size_t w = static_cast<size_t>(b.ni) + 2;
        fr.ext.assign(w * (static_cast<size_t>(b.nj) + 2), -1);
        for (int j = 0; j < b.nj; ++j)
            for (int i = 0; i < b.ni; ++i)
                fr.ext[static_cast<size_t>(j + 1) * w + static_cast<size_t>(i + 1)] =
                    b.nodeAt(i, j);
    }

    // ── The ghost layers, one per shared edge, on BOTH of its two sides ─────
    for (const MbSharedEdge& se : mesh.sharedEdges) {
        if (se.blockA < 0 || static_cast<size_t>(se.blockA) >= nb) continue;
        if (se.blockB < 0 || static_cast<size_t>(se.blockB) >= nb) continue;
        const MbBlock& bA = mesh.blocks[static_cast<size_t>(se.blockA)];
        const MbBlock& bB = mesh.blocks[static_cast<size_t>(se.blockB)];
        MbGhostFrame& fA = plan.frames[static_cast<size_t>(se.blockA)];
        MbGhostFrame& fB = plan.frames[static_cast<size_t>(se.blockB)];
        if (fA.ext.empty() || fB.ext.empty()) continue;
        const bool okA = addGhosts(fA, bA, se.sideA, bB, se.sideB);
        const bool okB = addGhosts(fB, bB, se.sideB, bA, se.sideA);
        if (okA && okB) ++plan.ghostEdges;
    }

    // ── WHICH SIDES ARE WALLS, from the declaration's own published list ────
    //
    // `wallSpecs` is the seam's list of sides whose declared KIND is `wall`, and
    // it is the SAME list `measureMbQuality` and `mbWallTargets` walk. There is no
    // second answer to "is this a wall" here and no kind string is compared.
    //
    // A side named by NEITHER list cannot happen on a well-formed fill — every
    // block side references one edge, and an edge is a wall or is shared — but if
    // one did, the answer this makes is FROZEN, which is the answer that changes
    // nothing.
    std::vector<std::array<bool, 4>> isWall(nb, {false, false, false, false});
    for (const MbWallSpec& ws : mesh.wallSpecs) {
        if (ws.block < 0 || static_cast<size_t>(ws.block) >= nb) continue;
        isWall[static_cast<size_t>(ws.block)][static_cast<size_t>(ws.side)] = true;
    }
    std::vector<std::array<bool, 4>> isShared(nb, {false, false, false, false});
    for (const MbSharedEdge& se : mesh.sharedEdges) {
        if (se.blockA >= 0 && static_cast<size_t>(se.blockA) < nb)
            isShared[static_cast<size_t>(se.blockA)][static_cast<size_t>(se.sideA)] = true;
        if (se.blockB >= 0 && static_cast<size_t>(se.blockB) < nb)
            isShared[static_cast<size_t>(se.blockB)][static_cast<size_t>(se.sideB)] = true;
    }

    // ── WHICH OF THE TWO BLOCKS MOVES A SHARED EDGE'S NODES ────────────────
    //
    // THE OWNER IS THE BLOCK WITH MORE OF THE DECLARATION TO HONOUR ALONG THAT
    // LINE: the one declaring more WALL sides perpendicular to it. Ties go to the
    // first of the two, which is the lower block index, so the answer is a
    // function of the document and of nothing else.
    //
    // WHY THAT AND NOT SIMPLY THE LOWER INDEX, which is what this ticket wrote
    // first. Either block computes the same POSITION — the Winslow update is
    // invariant under the frame change between them, see this module's header — so
    // ownership is free as far as the kernel goes. It is NOT free as far as the
    // CONTROL goes: a wall's control reaches a shared line only as the `k = 0` or
    // `k = n - 1` station of that wall's own walk, so the number of perpendicular
    // walls IS the number of declarations that can reach the line in that frame.
    // On the shipped C-grid the two differ and it is the trailing-edge radial that
    // shows it: `r_te_up` is the wake block's north (one perpendicular wall, the
    // far field) and the upper airfoil block's south (two — the airfoil AND the far
    // field). Under the lower-index rule the wake block owned it and the airfoil's
    // declared first cell reached the line's wall end at zero weight.
    std::vector<std::array<bool, 4>> ownsSide(nb, {false, false, false, false});
    for (const MbSharedEdge& se : mesh.sharedEdges) {
        if (se.blockA < 0 || static_cast<size_t>(se.blockA) >= nb) continue;
        if (se.blockB < 0 || static_cast<size_t>(se.blockB) >= nb) continue;
        const size_t ba = static_cast<size_t>(se.blockA);
        const size_t bb = static_cast<size_t>(se.blockB);
        const int scoreA = perpWalls(isWall[ba], se.sideA);
        const int scoreB = perpWalls(isWall[bb], se.sideB);
        if (scoreB > scoreA) ownsSide[bb][static_cast<size_t>(se.sideB)] = true;
        else                 ownsSide[ba][static_cast<size_t>(se.sideA)] = true;
    }

    // ── WHO MOVES, and in whose frame ──────────────────────────────────────
    //
    // ONE PASS IN BLOCK ORDER. "Moved once, as one node" holds because `ownsSide`
    // above picks exactly ONE of a shared edge's two uses, so a shared node is
    // reached by exactly one block — and it is held by that one line rather than
    // by a second dedupe pass beside it. A `claimed` set was written first and
    // then removed: it made the property true twice and therefore made the check
    // that asserts it unfalsifiable, so an injection setting BOTH uses came back
    // inert on the check that exists to catch exactly that.
    for (size_t bi = 0; bi < nb; ++bi) {
        const MbBlock& b = mesh.blocks[bi];
        const MbGhostFrame& fr = plan.frames[bi];
        if (fr.ext.empty()) continue;
        for (int j = 0; j < b.nj; ++j) {
            for (int i = 0; i < b.ni; ++i) {
                MbSide side = MB_SOUTH;
                const int on = sidesAt(b, i, j, side);
                // A DECLARED CORNER IS FROZEN, and this is that test — ONE test,
                // not two. "On two of this block's sides at once" and "is one of
                // the document's declared corners" are the SAME set on this path:
                // an edge runs corner to corner, so a declared corner always lands
                // at a side's own end and therefore at a block corner, and the fill
                // refuses a block whose four sides do not meet at four shared
                // corner nodes. A separate corner-id set was written first and
                // removed for the reason the ownership note below gives: two
                // sufficient conditions for one rule MASK each other, and an
                // injection disabling either came back inert while the four-way
                // corner it is about stayed frozen for the other reason.
                if (on >= 2) continue;
                const int id = b.nodeAt(i, j);
                if (id < 0) continue;
                const bool shared = (on == 1);
                if (shared) {
                    // On a WALL side: the domain, not the discretisation.
                    if (isWall[bi][static_cast<size_t>(side)]) continue;
                    if (!isShared[bi][static_cast<size_t>(side)]) continue;
                    // The other block's to move.
                    if (!ownsSide[bi][static_cast<size_t>(side)]) continue;
                }
                // EVERY ONE OF THE NINE MUST BE A REAL NODE. For an interior node
                // that is automatic; for a node on a shared side it is what the
                // ghost layer provides, and it is checked HERE rather than in the
                // sweep so the plan is the one place the rule lives. A node whose
                // stencil is incomplete — an edge whose sides could not be matched
                // station for station — stays frozen.
                bool full = true;
                for (int dj = -1; dj <= 1 && full; ++dj)
                    for (int di = -1; di <= 1 && full; ++di)
                        if (!fr.has(i + di, j + dj)) full = false;
                if (!full) continue;
                MbNodeMove mv;
                mv.node = id;
                mv.i = i;
                mv.j = j;
                mv.shared = shared;
                plan.moves[bi].push_back(mv);
                ++plan.movedNodes;
                if (shared) ++plan.movedShared;
            }
        }
    }
    return plan;
}
