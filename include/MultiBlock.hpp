#ifndef MULTIBLOCK_HPP
#define MULTIBLOCK_HPP

#include "GeomUtils.hpp"
#include "MbSplitRule.hpp"   // the four diagonal rules, shared with Config.hpp

#include <cstdint>
#include <map>
#include <string>
#include <vector>

// The topology-driven multi-block structured path (MESH_MODE 1), as ONE pure
// entry point.
//
// This is the only seam this feature gets, and the shape is deliberate. JSON
// parsing sits INSIDE it, so a test can hand `buildMultiBlock` a topology
// document as text and assert on what comes back: schema errors, count
// resolution, node positions, the diagonal split and the resolved boundary
// conditions are all EXTERNAL behaviour of this one function. A separate
// "parse the document" entry point would have made half of that internal.
//
// The adapter that writes an `MbResult` into the mesh container deliberately
// gets NO seam of its own (it lives in src/cli.cpp). It is a loop with no
// decisions in it — every boundary edge comes back already resolved — and
// giving it a seam would concede that it has logic worth testing separately.
// Recorded honestly: the adapter has since grown three PRESENTATION blocks (the
// boundary-patch summary from #52, the propagated-count and shared-edge rows from
// #53). None of them classifies anything or changes a mesh, but the claim is no
// longer literally "no decisions", and if a fourth appears the grouping belongs on
// the pure side beside `measureMbQuality`.
//
// Everything here is Gmsh-free and Mesh-free by construction: the module lives
// in `hybmesh_pure`, whose tests link that library and NOTHING else, so the
// moment this file reaches for `Mesh` or gmsh those executables stop linking.
// See tools/PreProcessor/tests/test_cpp_pure_layer.py.
namespace hybmesh {

// One loaded geometry, as this seam sees it: the resampled polyline plus the two
// facts its `.meta` sidecar carries about where one segment ends and the next
// begins, and what boundary condition each carries.
//
// A topology attaches to a geometry BY NAME (`file`, matched exactly or by
// basename) and never by position in this vector — for the reason the ticket
// gives about point indices one level down: a list that can be reordered is a
// binding that can silently relocate.
struct MbGeometry {
    std::string file;
    std::vector<Point2D> points;
    // Parallel to `points`: which source segment each point belongs to, from the
    // sidecar's POINTS block. EMPTY when the geometry has no readable sidecar,
    // and a document that attaches to such a geometry is refused by name rather
    // than falling back to "the whole polyline is segment 0" — a corner that
    // lands somewhere plausible on the wrong segment is the slightly-wrong-mesh-
    // with-no-error outcome this whole path exists to avoid.
    std::vector<int> segId;
    // Indices in `points` at which a new disconnected PIECE starts, from the
    // sidecar's NPIECES block. Read for one reason, and it is not cosmetic: a
    // segment's arc length runs from its own first point to the first point of
    // the NEXT segment (the sidecar assigns a shared joint to the LATER segment,
    // so a segment's own run stops one point short of where it ends). Across a
    // piece break there is no next point to reach for, and taking one anyway
    // would stretch the segment across the gap between two disjoint pieces —
    // there, as on the last segment of an open polyline, t = 1 is the segment's
    // own final point, which the resampler pins and so does not drift either.
    std::vector<size_t> pieceBreaks;
    // Did the loader weld this polyline into a closed loop? It drops the trailing
    // duplicate of the first point when it does, so the LAST segment's end is not
    // one past the end of `points` but index 0 — and without knowing that, t = 1 on
    // the last segment of a closed body lands one resampling interval short of the
    // seam, which is the very drift arc length is used to avoid.
    bool closed = false;
    // seg id -> the per-segment boundary condition LABEL the sidecar carries.
    //
    // A LABEL, not a physical BC type: the GUI groups segments under a label and
    // maps label -> type separately (the sidecar's GROUP_BC trailer), and the
    // exporter resolves it through `Config::resolveGroupBc`. Resolving it here
    // would put a second resolver in the chain, which is how the two came to
    // disagree the last time. A segment with no label falls back to
    // `MbParams::defaultBc`.
    std::map<int, std::string> segBc;
};

// The resolved parameters this path reads. Deliberately a handful of values
// rather than a `Config&`: Config.hpp is a header-only .dat parser and pulling
// it in would tie the decision layer to the file format it is a decision about.
struct MbParams {
    // The FALLBACK boundary condition, from BC_GEOM. An edge that declares a
    // binding takes its source segment's own label instead; this is what an
    // unbound edge — or a bound one whose segment carries no label — gets.
    std::string defaultBc = "wall";
    // Split every quad into two triangles before the mesh leaves this seam.
    // ON by default: the solver's incenter reconstruction is undefined on quad
    // cells, so triangles are the point of this whole path. Switchable off so
    // the quad mesh can be inspected when a topology is being diagnosed.
    bool splitQuads = true;
    // WHICH diagonal each quad is cut on. An `int` rather than an `MbSplitRule`
    // deliberately: the value arrives from a config file, an out-of-range one has
    // to be REFUSABLE, and casting an unknown number to an enum to then range-check
    // it is the one shape that makes the refusal itself undefined behaviour.
    int splitRule = MB_SPLIT_ALTERNATING;
    // The seed MB_SPLIT_RANDOM hashes. Read by that rule and by nothing else —
    // set alongside any other rule it is inert, and this seam SAYS so in a warning
    // rather than letting a recorded seed imply a reproducibility it does not have.
    //
    // Fixed-width, not `unsigned`: the whole argument for hand-writing the hash is
    // that the answer is a function of its inputs and of nothing else, and a width
    // the platform chooses is exactly the kind of thing that quietly is not.
    std::uint32_t splitSeed = 0;
    // THE GLOBAL WALL SPACING, from BL_INITIAL_THICKNESS — the first-cell height a
    // topology edge gets where it declares that an end of it sits on a wall and
    // does not say how fine. Reusing the boundary-layer parameter rather than
    // inventing an alias is deliberate: the physical quantity is identical, and
    // two names for one quantity is worse than one name that reads oddly in a mode
    // with no boundary-layer stage. A per-edge `ds_start` / `ds_end` beats it.
    //
    // 0 means "no global default was resolved", and an edge that then asks for one
    // is REFUSED by name rather than quietly left uniform: a wall-normal edge that
    // silently loses its clustering is a mesh with no boundary layer and no
    // symptom.
    double wallSpacing = 0.0;
    // The global default GROWTH RATIO for the `geometric` law, from BL_GROWTH_RATE,
    // for the same reason and on the same terms. An edge that declares its own
    // `growth` beats it; 0 means none was resolved, and then `geometric` must
    // declare one.
    double wallGrowth = 0.0;
    // THE ITERATION CAP on the elliptic smoother that runs over each block's
    // INTERIOR nodes, between the fill and the split. 0 — the default — is "no
    // sweep runs at all", and at that value this seam returns exactly what it
    // returned before the smoother existed.
    //
    // A CAP, not a sweep count, since #82: the solve stops early the moment its
    // residual falls under `MB_SMOOTH_TOL`, and a run that reaches this number
    // still moving SAYS SO (`MbResult::smoothConverged`, plus a warning) rather
    // than handing back a truncated solve that looks finished. Both halves are
    // published, so "47 of 200, converged" and "200 of 200, NOT converged" are
    // different answers a reader can tell apart.
    //
    // An `int` rather than a `size_t`, for the reason `splitRule` gives one line
    // up: the value arrives from a config file, a negative one has to be
    // REFUSABLE by name, and a type that cannot hold the bad value makes the
    // refusal itself unwritable — an unsigned conversion turns -1 into four
    // billion sweeps, which is not a refusal but a hang.
    //
    // Named MB_SMOOTH_ITERS on the `.dat` side, and neither BL_* nor SEED_*:
    // `BL_SMOOTHING_ITERS` is the OTHER path's collision remedy (it moves nodes
    // around a frozen boundary-layer front and returns immediately when no node is
    // frozen), and a key that reads as its sibling would claim a kinship these two
    // do not have. SEED_* is the refinement-seed namespace.
    int smoothIters = 0;
};

// WHEN THE ELLIPTIC SOLVE IS FINISHED: the largest distance any interior node
// moved in a sweep, divided by the bounding-box diagonal of the mesh the solve
// started from, has fallen to this.
//
// Relative and not absolute, because this module is scale-free everywhere else:
// a topology in millimetres and the same topology in metres must take the same
// number of sweeps, and an absolute floor would make one of them converge
// instantly and the other never.
//
// NOT a config key, deliberately. It is the tolerance a solve is "done" at, not a
// knob with a right answer per case — the knob a user has is the cap. A second
// key here would be one more number to keep in agreement across the `.dat`
// reader, the GUI field-spec table and the parity gate, in exchange for a
// question nobody has asked.
constexpr double MB_SMOOTH_TOL = 1e-8;

// WHEN THE ELLIPTIC SOLVE IS DECLARED LOST: the sweep residual has climbed back to
// this many times the smallest it ever reached.
//
// It is a real regime and not a defensive nicety — measured 2026-09-04 on the
// SHIPPED C-grid, where the residual falls monotonically to 2.7e-08 by sweep 3724
// and then GROWS, at about 1.0017 per sweep: 2.8e-07 by sweep 5000, 1.7e-06 by
// 6000, and 1.3e-03 by sweep 10000 with 88 cells folded (that tail measured with
// the stop below removed, since with it in place the solve never gets there). The
// lagged-coefficient point iteration is only conditionally stable, and a grid this
// equidistributed (max non-orthogonality 74.8 deg by then) is where the condition
// fails.
//
// TEN and not two: the residual of a healthy solve falls monotonically on every
// case measured here, so a factor of two would be a live tripwire on a wobble,
// while a factor of ten is a mode that has grown through an order of magnitude and
// is not coming back.
constexpr double MB_SMOOTH_DIVERGE_FACTOR = 10.0;

// THE TWO SOURCE TERMS of one interior node's update — the CONTROL FUNCTIONS
// (issue #83), and what turns an elliptic smoother into one that has been TOLD
// what the boundary should look like.
//
// Without them the solve relaxes toward each block's harmonic map, which is
// UNIFORM: on a grid graded 250:1 off a viscous wall that is the opposite of what
// the declaration asked for, and #82 measured the cost — a converged plain
// Winslow solve on the shipped C-grid is 3133% off its declared first-cell
// height. `phi` and `psi` are how the wall's two requirements — a grid line
// leaving it at 90 degrees, and a first cell of the height the document asked
// for — enter the interior equation.
//
// Each is the coefficient of the FIRST derivative in its own logical direction,
// so the system solved becomes
//
//     a * (x_ii + phi * x_i)  -  2b * x_ij  +  g * (x_jj + psi * x_j)  =  0
//
// and BOTH ZERO reproduces the plain Winslow update exactly, which is the
// property the kernel's exactness gate rests on. Where they come from is
// `include/MbControl.hpp`; this is only their shape.
struct MbControl {
    double phi = 0.0;   // the i-direction source
    double psi = 0.0;   // the j-direction source
};

// HOW LARGE A SOURCE TERM THE KERNEL WILL ACCEPT, and it is a stability bound
// rather than a taste: the update below weights `iPlus` by a*(1 + phi/2) and
// `iMinus` by a*(1 - phi/2), so at |phi| = 2 one of the two coefficients reaches
// zero and past it the node is no longer a convex combination of its neighbours.
// The iteration then has no maximum principle, and a node can be pushed OUTSIDE
// the hull of the nine positions it was computed from — which is a fold, not a
// smoother.
//
// So a raw control value larger than this is CLIPPED, and clipping is a request
// the solve could not honour in full: `MbControlField::clipped` counts it and the
// seam warns on it. It is not silently obeyed and not silently dropped.
constexpr double MB_CONTROL_CLIP = 2.0;

// The nine positions the Winslow update of ONE interior node reads: itself, its
// four logical neighbours and its four logical diagonals.
//
// Named fields rather than a 3x3 array because every one of them is read by name
// in the kernel, and an off-by-one in an index expression is exactly the defect
// the exactness gate next door exists to catch.
struct MbWinslowStencil {
    Point2D c;                 // (i,   j  ) — the node being moved
    Point2D iPlus, iMinus;     // (i+1, j  ), (i-1, j  )
    Point2D jPlus, jMinus;     // (i,   j+1), (i,   j-1)
    Point2D pp, mp, pm, mm;    // (i+1, j+1), (i-1, j+1), (i+1, j-1), (i-1, j-1)
};

// WHERE THAT NODE GOES under one Winslow (elliptic) update, with unit spacing in
// the computational coordinates — which is what makes the i/j indices themselves
// the coordinate system and is why `MbBlock` retains them.
//
// The system solved is the transform of Laplace's equation for the COMPUTATIONAL
// coordinates, so it is the physical coordinates that come out as the unknowns:
//
//     a * x_ii  -  2b * x_ij  +  g * x_jj  =  0        (and the same for y)
//     a = x_j^2 + y_j^2,   b = x_i x_j + y_i y_j,   g = x_i^2 + y_i^2
//
// EXPOSED FROM THE HEADER, unlike every other step of the fill, because the gate
// #82 asks for is an arithmetic one: a stencil whose answer is known by hand, so
// that a swapped `a`/`g`, a dropped `b` or a wrong cross-derivative stencil is
// caught by a number rather than by a mesh looking odd. Driving that through
// `buildMultiBlock` would test the loop, not the kernel.
//
// THE DIFFERENCE FROM A PLAIN LAPLACIAN, which is the whole of #82: the physical
// Laplacian sends the node to the mean of its four neighbours, so on a grid graded
// 250:1 from a wall it walks straight down the stretching gradient. Here the
// grading sits in `a` and `g` — the squared spacings of the OTHER direction — so a
// direction that is finely spaced is weighted by how finely spaced its neighbour
// direction is, and strong grading survives that a mean does not.
//
// DEGENERATE INPUT returns `c` unchanged: `a + g` is zero only when all four
// logical neighbours coincide with each other, which is not a grid. Returning the
// node is the answer that changes nothing, rather than a NaN that propagates into
// every later sweep and out through the exporter.
// `q` IS NOT DEFAULTED, deliberately. A caller that wants the plain kernel says
// so with `{}` at the call site, so every use states which of the two systems it
// means — and the checks that pin the plain arithmetic keep saying "no control
// functions" out loud rather than by omission.
Point2D mbWinslowUpdate(const MbWinslowStencil& s, const MbControl& q);

// A block's four sides, in the [south, east, north, west] order the topology
// document declares them and every check in this module is written against.
enum MbSide { MB_SOUTH = 0, MB_EAST = 1, MB_NORTH = 2, MB_WEST = 3 };

// WHERE a side sits in the block's logical grid. This is the [south, east,
// north, west] convention as DATA, in one place, because it was on its way to
// being encoded three times: once to pick the perpendicular edge whose spacing
// law a wall's first-cell height is asked of (src/MultiBlock.cpp), once to walk
// that side and step one grid line inward (src/MbQuality.cpp), and once to name
// it in a report. Two of those were `switch (side)` cascades over the same four
// values, which is the shape that lets one of them disagree with the others.
//
// The two facts are enough to derive all three: south and north run along i and
// the other two along j, and north and east sit at the transverse index MAXIMUM.
// So the perpendicular edges are (alongI ? west/east : south/north), read from
// (atFarEnd ? the far end : the near end).
struct MbSideAxis {
    const char* name;   // "south" | "east" | "north" | "west"
    bool alongI;        // the side runs along i (south, north) rather than along j
    bool atFarEnd;      // it sits at the transverse index maximum (north, east)
};

inline MbSideAxis mbSideAxis(MbSide s) {
    switch (s) {
        case MB_EAST:  return {"east",  false, true};
        case MB_NORTH: return {"north", true,  true};
        case MB_WEST:  return {"west",  false, false};
        case MB_SOUTH: break;
    }
    return {"south", true, false};
}

// What an edge IS: a CLOSED SET, in one place, with its declared names beside it.
//
// An enum rather than a validated string, and the difference is not cosmetic —
// the kind was compared against a literal at six sites, which is six chances for
// one of them to disagree with the others, and it travelled out of the seam as a
// string a reader had to match by hand. The names live here too, so the parser,
// every refusal message and the banner read the same four words. Same shape as
// `mbSideAxis` below and for the same reason.
//
// The kind is DECLARED and never inferred from whether a `binding` is present: a
// wake cut is two blocks sharing one line that is NOT a boundary, and inference
// would file it as an ordinary interface.
enum MbEdgeKind { MB_EDGE_WALL = 0, MB_EDGE_INTERFACE = 1, MB_EDGE_CUT = 2 };

inline const char* mbEdgeKindName(MbEdgeKind k) {
    switch (k) {
        case MB_EDGE_INTERFACE: return "interface";
        case MB_EDGE_CUT:       return "cut";
        case MB_EDGE_WALL:      break;
    }
    return "wall";
}

// One shared INTERIOR edge, and the two block sides welded along it.
//
// Published as data because the kind is a DECLARATION and a run has to be able to
// show it: an "interface" is an interior boundary between two blocks and a "cut"
// is a wake or branch line that is likewise shared but is not a boundary of
// anything. Neither is inferred from whether a binding is present — that
// inference is precisely what would file a wake cut as an ordinary interface.
//
// WHAT IS AND IS NOT DISTINGUISHED, said plainly because the name invites a
// stronger reading. The kind decides three things today, all of them checkable:
// how many block sides the edge may be (a wall exactly one, the other two exactly
// two), whether it may declare a `binding` (a wall only — a cut lies in the fluid
// and has no source segment to lie on), and whether it is exported as a boundary
// face carrying a BC (a wall only). What it does NOT yet decide is any arithmetic:
// an interface and a cut weld by the same rule, because with node identity shared
// there is nothing left for a second rule to do. The kind is what makes a later
// divergence — a periodic cut, a non-matching interface — a change rather than a
// rewrite, and `MbResult::sharedEdges` is what lets a user see which shared lines
// are which in the meantime.
struct MbSharedEdge {
    std::string edgeId;
    MbEdgeKind kind = MB_EDGE_INTERFACE;
    int blockA = -1, blockB = -1;  // indices into MbResult::blocks
    MbSide sideA = MB_SOUTH;       // ...and which of its sides, as each declared it
    MbSide sideB = MB_SOUTH;
    int nodes = 0;                 // node count along it, ONE number by construction
};

// One edge's resolved node count, and whether the document said so.
//
// Published because point-count propagation is the one place on this path where
// the mesh is decided by something the user did NOT write down: they seed a few
// edges and the rest are forced. A run that cannot show which counts it derived
// is a run in which a propagation defect looks like a design choice.
struct MbEdgeCount {
    std::string edgeId;
    int count = 0;
    bool seeded = false;   // the document declared this count; else it propagated
};

// One filled block, with its LOGICAL i/j indexing retained.
//
// Retained rather than flattened because the diagonal rules depend on it: the
// alternating split is a function of (i + j) parity and the randomized one hashes
// (block id, i, j, seed). Flattening before the split would destroy the only
// information the split reads.
struct MbBlock {
    std::string id;
    int ni = 0;                  // node count along i
    int nj = 0;                  // node count along j
    std::vector<int> nodeIds;    // ni*nj global node ids; index = j * ni + i

    int nodeAt(int i, int j) const { return nodeIds[static_cast<size_t>(j) * ni + i]; }
};

// HOW TO WALK ONE SIDE OF ONE BLOCK: every index a reader of that side needs,
// derived once from `mbSideAxis` instead of once per reader by hand.
//
// Here rather than in a module because it has THREE readers in two files now —
// the control functions (src/MbControl.cpp), the ghost layer and the freeze rule
// (src/MbShared.cpp) — and it is the same argument `mbSideAxis` itself carries
// one screen up: this was written out three times inside `MbControl.cpp` alone,
// each with its own copy of `t0 = atFarEnd ? m - 1 : 0`, which is the shape that
// lets one of them disagree with the others.
//
// `k` is the station ALONG the side and `tt` the grid line ACROSS it, so nothing
// above has to know which of i and j a given side runs along. `tt` may be -1 or
// `m` — one step OUTSIDE the block — which is exactly what a ghost layer is
// addressed by; `MbGhostFrame` in include/MbShared.hpp is what answers there, and
// `MbBlock::nodeAt` is not to be handed those.
//
// `ok` is false for a block too thin to walk. Checked by the caller rather than
// returned as an optional: each caller has a different thing to do about it, and
// some still publish part of their answer for such a side.
struct MbSideWalk {
    MbSideAxis ax{"south", true, false};
    int n = 0;       // stations along the side
    int m = 0;       // grid lines across it
    int t0 = 0;      // the line ON the side
    int t1 = 0;      // one line in from it
    int tFar = 0;    // the line facing it
    int tOut = 0;    // one line OUTSIDE the block, where a ghost layer sits
    bool ok = false;

    int i(int k, int tt) const { return ax.alongI ? k : tt; }
    int j(int k, int tt) const { return ax.alongI ? tt : k; }
};

inline MbSideWalk mbSideWalk(const MbBlock& b, MbSide side) {
    MbSideWalk w;
    w.ax = mbSideAxis(side);
    const size_t want = static_cast<size_t>(b.ni) * static_cast<size_t>(b.nj);
    if (b.ni < 2 || b.nj < 2 || b.nodeIds.size() != want) return w;
    w.n = w.ax.alongI ? b.ni : b.nj;
    w.m = w.ax.alongI ? b.nj : b.ni;
    w.t0 = w.ax.atFarEnd ? w.m - 1 : 0;
    w.t1 = w.ax.atFarEnd ? w.m - 2 : 1;
    w.tFar = w.ax.atFarEnd ? 0 : w.m - 1;
    w.tOut = w.ax.atFarEnd ? w.m : -1;
    w.ok = true;
    return w;
}

// One cell, already split (3 node ids) or still a quad (4), wound CCW.
struct MbCell {
    std::vector<int> nodeIds;
    // Which block this cell came from. Carried because flattening is otherwise
    // one-way: once the cells are a flat list there is nothing left to ask.
    // Issue #48 wants it as a VTK cell field for debugging — which nothing writes
    // yet, since no exporter has changed.
    //
    // NOT what the randomized diagonal hashes, and the difference is the whole
    // point of that rule: this is a POSITION in `MbResult::blocks`, so declaring a
    // new block ahead of an existing one renumbers it. The hash takes the block's
    // declared `id` instead, which nothing but renaming that block can move.
    int block = -1;
};

// One boundary edge, ALREADY RESOLVED. The adapter records it through the
// mesh's existing paired write and makes no classification decision — position
// based classification is not used in this path, because the declaration
// already contains the answer and re-deriving it by proximity is how a curved
// inlet came to export partly as wall.
struct MbBoundaryEdge {
    int v1 = -1, v2 = -1;
    // The BC LABEL this edge carries: the bound segment's own label, else
    // `MbParams::defaultBc`. Resolved to a physical type by the exporter.
    std::string bc;
    // The SOURCE SEGMENT this edge lies on, as (index into `geoms`, sidecar seg
    // id). Both stay -1 for an edge that declares no binding — which is not a
    // failure but the ordinary case for a block face in open fluid, and is what
    // makes the pre-binding topologies mesh unchanged.
    int geomId = -1;
    int segId = -1;
};

// One side of one block that was declared kind "wall", carrying the first-cell
// height the DECLARATION asks for off it.
//
// It is published here rather than measured downstream because only the seam
// knows the declaration: the request comes from the spacing law of the edge
// running away from this side, and by the time the block is a grid of node
// positions that law is gone. `MbQuality.hpp` then measures what the fill
// achieved against it.
//
// The gate is the KIND: a side declared "interface" or "cut" is an interior line
// and is not listed, so on a multi-block topology this list is exactly the outer
// walls. Note what did NOT change this: boundary conditions DO come from the
// declaration, and a side may carry a segment labelled "inlet" — but that is the
// flow condition, not the answer to "is this a viscous surface whose first cell
// height matters". The gate stays `kind`, which is the declaration's own word for
// it; when a kind distinguishes the two, this list gets shorter and nothing that
// reads it has to change.
struct MbWallSpec {
    int block = 0;                   // index into MbResult::blocks
    MbSide side = MB_SOUTH;
    std::string edgeId;
    double requestedLo = 0.0;        // first interval off this side at its START corner
    double requestedHi = 0.0;        // ... and at its END corner
};

struct MbResult {
    // false -> `error` names what is wrong and NOTHING was produced. The caller
    // turns this into EXIT_ERR_TOPOLOGY and exports nothing.
    bool ok = false;
    std::string error;
    // Warnings as DATA: the caller decides how to say them, and a test can
    // assert on the list without capturing a log.
    std::vector<std::string> warnings;

    std::vector<Point2D> nodes;
    std::vector<MbBlock> blocks;
    std::vector<MbCell> cells;
    std::vector<MbBoundaryEdge> boundaryEdges;
    std::vector<MbWallSpec> wallSpecs;
    // The interior edges two blocks were welded along, and every edge's resolved
    // node count. Both are DECLARATION facts a run has to be able to report: see
    // MbSharedEdge and MbEdgeCount.
    std::vector<MbSharedEdge> sharedEdges;
    std::vector<MbEdgeCount> edgeCounts;
    // THE SAME MESH BEFORE SMOOTHING: `nodes` as it stood the instant before the
    // first sweep, parallel to `nodes` and empty when no sweep ran.
    //
    // Published from the seam for the reason `MbWallSpec` is: only this function
    // is ever in a position to know it, and a caller that wanted to measure what
    // smoothing bought would otherwise have to run the whole build twice and
    // trust that the two runs agree about everything else. With this, "before"
    // and "after" are the same cells, the same blocks and the same node ids over
    // two coordinate sets — so a difference between the two reports is the
    // smoother and nothing else.
    //
    // EMPTY IS THE HONEST ANSWER, not a zero-length before/after pair: a run that
    // did not smooth has no "before" distinct from what it returned, and reporting
    // one would put two identical quality blocks in front of a reader who asked
    // for no smoothing.
    std::vector<Point2D> preSmoothNodes;
    // WHAT THE ELLIPTIC SOLVE ACTUALLY DID (#82). Published as three numbers
    // rather than one, because "it ran 200 sweeps" and "it finished" are different
    // claims and a truncated solve that reports only the first reads as finished.
    //
    //   smoothSweeps    how many sweeps the RETURNED mesh is the product of,
    //                   <= MbParams::smoothIters. Less than the cap means the
    //                   solve stopped early — converged, or diverged.
    //   smoothConverged the residual reached MB_SMOOTH_TOL. FALSE at the cap is
    //                   not an error — the mesh may be perfectly usable — but it
    //                   is a warning in `warnings` and a row in the report, so it
    //                   is never something a reader has to infer.
    //   smoothDiverged  the residual climbed back to MB_SMOOTH_DIVERGE_FACTOR
    //                   times the smallest it had reached, so the iteration is
    //                   growing a mode rather than settling. The returned mesh is
    //                   then the BEST iterate, not the last one — see the solve
    //                   itself in src/MultiBlock.cpp for why rolling back is the
    //                   honest answer and not a cover-up.
    //   smoothResidual  the largest node move of the sweep that produced the
    //                   RETURNED mesh, over the starting mesh's bounding-box
    //                   diagonal. NEGATIVE means no sweep ran, for the reason
    //                   `MbQualityReport` gives: 0.0 is a superb result and must
    //                   not stand in for "not measured".
    //   smoothBest*     the SMALLEST residual the solve reached and the sweep that
    //                   reached it. Equal to the pair above on a converged solve
    //                   and on a diverged one (which returns that iterate); on a
    //                   solve stopped by its CAP they can differ, and when they do
    //                   the returned mesh is past the turn — the iteration is
    //                   already growing a mode, and raising the cap makes the mesh
    //                   worse rather than more converged. Published because that
    //                   is not derivable from the other two and is the difference
    //                   between "keep going" and "stop, you are past it".
    //
    // FLAT, and not bundled into an `MbSmoothReport` the way `MbQualityReport`
    // bundles the mesh figures — considered and declined in #82's review. The
    // fifth member of this story is `preSmoothNodes` above, which is #81's
    // published contract and is read as `res.preSmoothNodes` by the adapter; a
    // struct holding four of the five would split one concern across two shapes,
    // which is worse than the clump. Bundle all five or none.
    //   smoothClipped   how many of the RETURNED mesh's nodes had a control
    //                   function clipped to MB_CONTROL_CLIP — the count of places
    //                   the wall condition asked for a push the kernel cannot take
    //                   without losing its maximum principle (#83). NEGATIVE means
    //                   no sweep ran, on the same rule as `smoothResidual`: 0 is
    //                   "every request was honoured in full" and must not stand in
    //                   for not having looked.
    //   smoothMoved     how many NODES the solve was free to move, and
    //   smoothMovedShared  how many of those lie on a side two blocks SHARE (#84).
    //                   Published because the freeze rule is otherwise a claim
    //                   about a loop nobody can see: before #84 the second figure
    //                   was zero by construction, and a run that cannot show which
    //                   nodes it was allowed to touch cannot show that an interface
    //                   is no longer a kink. NEGATIVE means no sweep ran, on the
    //                   same rule as `smoothResidual` — 0 movable nodes is a real
    //                   answer (a topology of nothing but 2-node edges) and must
    //                   not stand in for not having looked.
    int smoothSweeps = 0;
    int smoothClipped = -1;
    int smoothMoved = -1;
    int smoothMovedShared = -1;
    bool smoothConverged = false;
    bool smoothDiverged = false;
    double smoothResidual = -1.0;
    int smoothBestSweep = 0;
    double smoothBestResidual = -1.0;
};

// Parse `topologyJson`, resolve it against `geoms` and `params`, resolve every
// edge's node count, fill every block with structured quads welded to its
// neighbours, split them and return the flattened result.
// Never throws: a malformed document comes back as `ok == false` with `error`
// naming what is wrong and where.
MbResult buildMultiBlock(const std::string& topologyJson,
                         const std::vector<MbGeometry>& geoms,
                         const MbParams& params);

}  // namespace hybmesh

#endif  // MULTIBLOCK_HPP
