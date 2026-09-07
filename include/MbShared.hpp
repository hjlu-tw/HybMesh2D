#ifndef MBSHARED_HPP
#define MBSHARED_HPP

#include "MultiBlock.hpp"

#include <cstddef>
#include <vector>

// WHICH NODES THE SMOOTHER MAY MOVE, and — for a node two blocks share — in
// WHOSE logical frame it is moved (issue #84).
//
// WHY THIS EXISTS AT ALL. #81 through #83 froze every node on every block
// boundary, and said so honestly: a boundary node is written by the EDGE, an edge
// is SHARED, and a per-block smoother that computed a position from block A and
// another from block B would have to reconcile two answers. On a grid where wall
// spacing is near 1e-7 and far-field spacing near 1e-1 there is no tolerance
// between those scales to reconcile them WITH, and inventing one would put
// coordinate welding back into a module whose whole premise is that welding is by
// allocation. So the freeze was the right call for those tickets and the wrong
// mesh: #83 measured the cost and localised it — the worst corners of the
// smoothed O-grid sit mid-block on the four DECLARED RADIAL INTERFACES, and the
// worst lines of a smoothed multi-block mesh became the ones the topology
// declared as interior.
//
// WHAT THIS MODULE DOES INSTEAD OF RECONCILING. A shared node is ONE node, and it
// is moved ONCE, in ONE frame, by ONE stencil. The stencil is not a per-block one
// patched up afterwards: a node on the south side of a block has no `j - 1` row
// inside that block, and the row that IS its `j - 1` lives in the neighbour — one
// grid line in from the neighbour's matching side. `MbGhostFrame` below is that
// continuation, so the node's nine logical neighbours are nine real nodes and the
// kernel is handed the same shape it is handed for an interior node. No position
// is computed twice, nothing is averaged, and no distance is compared anywhere in
// this file.
//
// ITS OWN MODULE rather than more of `src/MultiBlock.cpp`, on the same grounds
// `MbQuality` and `MbControl` are: a different question ("who may move, and in
// which frame?" against "what does this document declare?"), and a PURE, TOTAL
// function of a finished fill — so a check can drive it on a mesh nobody parsed
// and read the answer as data. The module NAME is load bearing as well: the rule
// file's globs cover `include/Mb*.hpp` and `src/Mb*.cpp` as PATTERNS, so a module
// named this way starts life with this path's rules attached while a
// `MultiBlockShared.cpp` would have arrived ruleless.
//
// It lives in `hybmesh_pure`. See tools/PreProcessor/tests/test_cpp_pure_layer.py.
namespace hybmesh {

// ONE BLOCK'S LOGICAL FRAME, EXTENDED BY ONE GHOST LAYER across every side the
// declaration SHARES with another block.
//
// Addressed on i in [-1, ni] and j in [-1, nj]. Inside the block it is the
// block's own `nodeAt`; one step outside a shared side it is the neighbour's node
// one grid line in from ITS matching side, at the same station along the line.
// Everywhere else — outside a side declared `wall`, and at the four DIAGONAL
// corners of the extended range — it is -1, meaning "no node exists there".
//
// THE FOUR DIAGONAL CORNERS HAVE NO ANSWER AND ARE NOT GIVEN ONE. (-1, -1) is
// "one step west and one step south of the block's own corner", and which node
// that is depends on what meets at that corner — one block, two, or the four of
// a four-way corner. Nothing here guesses: the freeze rule below is written so
// that no movable node's stencil ever reaches one.
//
// WHY THE GHOST IS THE NEIGHBOUR'S FIRST INTERIOR LINE AND NOT ITS BOUNDARY. The
// shared side itself is ONE line of nodes that both blocks read, so it is already
// row `t0` of both frames. The next line out, in the glued frame, is therefore the
// neighbour's `t1` — its own first line in. That is not an approximation of a
// ghost node, it IS the node, which is what makes the stencil exact rather than
// one-sided.
struct MbGhostFrame {
    int ni = 0, nj = 0;
    // (ni + 2) * (nj + 2) node ids; index = (j + 1) * (ni + 2) + (i + 1).
    std::vector<int> ext;

    int at(int i, int j) const {
        if (i < -1 || j < -1 || i > ni || j > nj) return -1;
        const size_t w = static_cast<size_t>(ni) + 2;
        const size_t k = static_cast<size_t>(j + 1) * w + static_cast<size_t>(i + 1);
        return (k < ext.size()) ? ext[k] : -1;
    }
    bool has(int i, int j) const { return at(i, j) >= 0; }
};

// ONE NODE THE SMOOTHER MOVES, and where in its frame it is moved.
//
// `node` is the global id and `i` / `j` the ONE place it is computed from; WHICH
// frame is the index of the outer vector in `MbSmoothPlan::moves`, and is not
// repeated here — a `block` field was written first and deleted, because nothing
// read it and an inert published field is the shape #83's review named.
//
// A node appears in a plan AT MOST ONCE, across every block — that is the whole
// of "moved once, as one node", and it is a property of this list rather than of
// the loop that walks it, so a check can read it off by IDENTITY without
// measuring a distance.
struct MbNodeMove {
    int node = -1;
    int i = 0;
    int j = 0;
    // Does this node lie on a side two blocks share? Carried so a run can report
    // the freeze rule it is running under rather than have a reader infer it.
    bool shared = false;
};

// WHO MOVES, DERIVED ONCE FROM THE DECLARATION.
//
// THE FREEZE RULE, stated here because the ticket asks for it to be stated rather
// than read off a loop:
//
//   * A node on an edge whose declared KIND is `wall` is FROZEN. Those are the
//     outer boundaries — walls, bound edges, the outlet plane — and they are the
//     DOMAIN rather than the discretisation. A node on a bound edge would also
//     leave the geometry it was attached to by arc length.
//   * A DECLARED CORNER is FROZEN, whatever meets there. Two reasons, and either
//     alone would be enough. It is a declared POSITION — a free coordinate, or an
//     arc length along a source segment — so moving it moves the document. And it
//     is the one node with no frame to be moved in: it is a corner of up to four
//     blocks and lies on up to five edges, so its stencil would need the diagonal
//     ghosts that do not exist. THIS IS THE FOUR-WAY CORNER'S ANSWER: it does not
//     move, and the shipped C-grid's trailing edge and the shipped H-grid's centre
//     node are both covered by it — the first is on a wall as well, the second is
//     on four interfaces and no wall at all.
//     Implemented as "on two of this block's sides at once", which is the SAME
//     SET: an edge runs corner to corner, so a declared corner always lands at a
//     side's own end, and the fill refuses a block whose four sides do not meet at
//     four shared corner nodes.
//   * Every OTHER node moves: strictly interior to a block, or interior to an
//     edge declared `interface` or `cut`.
//
// The gate for "is this a wall" is `MbResult::wallSpecs`, the seam's own published
// list — the SAME list `measureMbQuality` and `mbWallTargets` walk. There is no
// second answer to that question here, and no kind string is compared.
//
// WHICH BLOCK OWNS A SHARED NODE: the one declaring MORE WALL SIDES PERPENDICULAR
// to the shared line, ties to the first of the two (the lower block index). So the
// answer is a function of the document and of nothing else.
//
// THE KERNEL DOES NOT CARE, AND THE CONTROL DOES — which is the whole of that
// rule. The Winslow update is INVARIANT under the change of logical frame between
// two blocks meeting at a shared edge: reflecting a logical axis flips the sign of
// both `b` and `x_ij` and leaves `a`, `g` and the second derivatives alone, and
// swapping i for j swaps `a` with `g` and leaves the equation term for term. So
// either block computes the SAME position from the same nine nodes, which is
// checked rather than asserted (tests/cpp/test_multiblock.cpp check 56). The
// CONTROL functions are the frame-dependent half: a wall's control reaches a
// shared line only as the `k = 0` or `k = n - 1` station of that wall's own walk,
// so the count of perpendicular walls IS the count of declarations that can reach
// the line in that frame. On the shipped C-grid the two rules differ and the
// trailing-edge radial is where: `r_te_up` is the wake block's north (one
// perpendicular wall, the far field) and the upper airfoil block's south (two —
// the airfoil AND the far field), and the wake block is the lower index. Under a
// lower-index rule the airfoil's declared first cell reached that line's wall end
// at zero weight.
struct MbSmoothPlan {
    // Parallel to `MbResult::blocks`.
    std::vector<MbGhostFrame> frames;
    // Parallel to `MbResult::blocks`: the nodes each block's frame moves. Grouped
    // by block rather than flat so the sweep can build one control field at a time
    // instead of holding one per block; a check that wants the identity property
    // flattens it.
    std::vector<std::vector<MbNodeMove>> moves;
    // How many nodes move in total, and how many of those are on a shared side.
    // Published as counts because they are what a run can SHOW: "the interfaces
    // are free" is otherwise a claim about a loop nobody can see.
    int movedNodes = 0;
    int movedShared = 0;
    // How many shared edges got a ghost layer on both sides. Equal to
    // `MbResult::sharedEdges.size()` on a well-formed fill; less means an edge
    // whose two sides could not be matched station for station, which this module
    // REFUSES to smooth across rather than smoothing against a guess.
    int ghostEdges = 0;
};

// The plan for a finished fill. Pure, total, never throws: a half-built result
// yields the frames and moves it can and freezes the rest.
MbSmoothPlan mbSmoothPlan(const MbResult& mesh);

}  // namespace hybmesh

#endif  // MBSHARED_HPP
