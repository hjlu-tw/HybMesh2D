// The multi-block seam, tested through `buildMultiBlock` and nothing else.
//
// Every check here feeds a topology DOCUMENT (as text) and asserts on what comes
// back — block dimensions, node positions, the diagonal split, the resolved
// boundary edges, warnings and errors. That is external behaviour of the one
// seam; reaching for the parser or the interpolation kernel would pin how it
// computed rather than what it returns.
//
// This executable links `hybmesh_pure` and NOTHING else — not gmsh, not
// hybmesh_core. That build property is itself the test: the moment the module
// reaches for the mesh container or gmsh, this stops linking.
//
// BLIND SPOTS, named rather than papered over:
//   * Nothing here exports anything. That the exporters accept these cells is
//     covered by the golden comparator's multi-block case family, and that the
//     solver runs on the result is the dated acceptance run recorded in
//     tools/PreProcessor/tests/test_multiblock_surface.py (one block) and
//     tools/PreProcessor/tests/test_multiblock_ogrid_surface.py (four, the first
//     multi-block grid to reach getPGrid or unicones).
//   * The refusal checks assert that the message NAMES the offending id and
//     that nothing was produced. They do not pin the surrounding prose, which
//     is meant to be edited.
//   * Welding, count propagation and the three edge kinds arrived with #53 and are
//     checks 17-23. What is still NOT exercised anywhere: a shared edge that is
//     also BOUND to a geometry, and a block welded to itself (which `parseBlocks`
//     refuses, correctly for a transfinite fill over four sides, so an O-grid seam
//     cannot be declared as one edge). The wrap-around class #53 could not reach
//     is check 33.
//   * Wall clustering and the O-grid are checks 30-36 (#55). Three limits they do
//     NOT cover, each refused by name rather than approximated: a two-sided
//     stretching function with DIFFERENT heights at the two ends; a curved
//     INTERFACE (a binding is still wall-only, so a block-to-block seam is a
//     straight chord, which is why the shipped O-grid is a single ring); and
//     projection onto an analytic curve rather than the stored polyline, which is
//     why BL_USE_ANALYTIC_GEOM is still a declared survivor that nothing reads.
//   * The ARC-LENGTH BLENDING that makes the fill reproduce a curved block is
//     measured HERE only through its consequence (check 33's node count, check
//     34's request/achieved pair). Its magnitude — 6927% wall-height error under
//     the logical-index blend, 0 under this one — was measured out of tree and is
//     recorded in docs/design_notes/mesher.md, not re-measured by any gate.
//   * The SMOOTHING pass is checks 40-50 (#81 built the stage, #82 replaced its
//     kernel with the Winslow one and deleted the Laplacian). What they do NOT
//     cover: the STAGE'S POSITION, which injection Y shows nothing can see
//     (above); anything downstream of the seam — that MB_SMOOTH_ITERS reaches
//     these parameters from a `.dat`, that the run reports before AND after, and
//     that a negative count is a CONFIG refusal are
//     tools/PreProcessor/tests/test_multiblock_smooth_surface.py; and the QUALITY
//     figures themselves, which are that gate's dated table, not a number
//     re-measured here. Check 45 asserts the wall-height regression as a DIRECTION
//     with a floor on a fixture, not as the shipped case's 0.44% -> 11.65%. Check
//     46 shows a FOLD but never an EXIT CODE — this file cannot reach one — so
//     "a smoothing fold exits 9 like any other" is the surface gate's claim alone.
//     THE THIRD ENDING OF THE SOLVE IS NOT HERE EITHER: `smoothDiverged` and the
//     rollback to the best iterate are gated only by that surface gate's group 7,
//     because no fixture in this file diverges — 26 were tried on 2026-09-04 (the
//     clustered C-grid at four wall spacings x two wall resolutions, a non-convex
//     dart at three depths x three gradings x two resolutions) and every one
//     CONVERGED. The case that diverges is the shipped C-grid.
//     Check 46's fixture also records a fact worth keeping, now twice over: the
//     C-grid fixture checks 37-39 use CANNOT fold at any sweep count (one interior
//     row per block), and neither can a merely denser UNIFORM version of it — the
//     CLUSTERING is what makes a fold reachable. #82 then had to go FURTHER,
//     from a declared first cell of 0.002 to 0.0005, because the Winslow kernel
//     folds nothing the Laplacian folded; check 50 is that finding from the other
//     side.
//   * The diagonal split RULES are checks 24-28 and the id-uniqueness refusals
//     29 (#54). What they do NOT check is
//     the QUALITY of the randomized rule's bit stream: nothing here asks whether
//     the diagonals are well distributed, only that both appear, that the pattern
//     is not parity's, and that it is a function of the four declared inputs. A
//     hash with a visible period would pass everything here. That is deliberate —
//     a distribution test on 12 cells asserts noise — and the property that
//     actually matters (no direction imprinted on a uniform region) is what
//     MbQuality measures on a real case.
//   * Nor does anything here reach the `.dat` keys. That MB_SPLIT_RULE and
//     MB_SPLIT_SEED arrive at these parameters at all, that an unknown rule is a
//     CONFIG refusal rather than a topology one, and that the seed survives into
//     the EXPORT are check 6 of
//     tools/PreProcessor/tests/test_multiblock_surface.py, plus check 5b of
//     tests/cpp/test_mesh_mode.cpp for Config::validate().
//   * The geometry fixtures are BUILT here rather than resampled. What they
//     reproduce is the two conventions of the real chain that decide where an
//     attachment lands (a joint belongs to the later segment; a closed loop's
//     duplicate closing point is dropped), and those were measured against the
//     real `surface_resampler` — but a change to the resampler that broke either
//     would be invisible from in here. The end-to-end gate next door
//     (tools/PreProcessor/tests/test_multiblock_binding_surface.py) drives the
//     real binary against real resamplings for exactly that reason.
//
// THE INJECTIONS ARE HAND RUNS, dated and recorded here with the checks each one
// broke — deliberately NOT written up as in-test injections, because a C++ test
// cannot mutate the implementation it linked against the way the Python gates
// next door can. Measured 2026-08-28, each patch applied to src/MultiBlock.cpp
// alone, rebuilt and run, with a control run confirming a clean tree passes:
//
//   A  position resolved by point INDEX (path[t * (n-1)]) rather than by arc
//      length                                                    -> 13
//   B  the segment run NOT extended to where the segment ends     -> 12, 13, 15
//   C  no wrap to index 0 for the last segment of a closed loop   -> 12
//   D  a bound edge cuts the chord instead of walking the polyline-> 15
//   E  every boundary edge takes the config default BC            -> 14
//   F  the (geometry, segment) key dropped on the way out         -> 14
//   G  the "both corners on the bound segment" refusal removed    -> 12, 16
//
// Two of those are recorded because the FIRST attempt at them did not bite, and
// both failures were in the INJECTION rather than in the code. A's first form
// picked the index and then interpolated by arc length WITHIN that span, which
// self-corrects to the right answer — an injection that changes no behaviour
// proves nothing about the check. And a build race (a rewritten source against a
// same-second object file) scored B as inert when it in fact breaks seven checks,
// until the run was re-done and the compiler output checked for a recompile.
// Both are recorded as what HAPPENED during a hand run; neither is a standing
// guard, because there is none — a scratch script that rewrites src/ and rebuilds
// is not something this repo ships, which is the same reason these injections are
// hand runs at all.
//
// SEVEN MORE for the split rules, measured 2026-09-03 the same way (each patch
// applied alone, rebuilt, ctest run, control run clean). N is against
// include/Config.hpp; the rest against src/MultiBlock.cpp:
//
//   H  the randomized rule hashes the block INDEX, not its declared id -> 26
//   I  the randomized rule drawn from a sequential stream              -> 25, 26
//   J  the two fixed directions swapped                                -> 24
//   K  the seed never mixed into the hash                              -> 25
//   L  an unknown rule clamped to the default instead of refused       -> 27
//   M  the inert-seed warning removed                                  -> 28
//   N  Config::validate() no longer refuses an unknown rule
//                                                 -> test_mesh_mode check 5b
//   O  a duplicate block id no longer refused                          -> 29
//   P  a duplicate EDGE id no longer refused                           -> 29
//
// Three of those are recorded for what the FIRST run showed rather than the
// second. H would not COMPILE in its first form: dropping the only call to
// mbHashId made it an unused static function, which this build treats as an
// error, so the injection had to keep the call and discard its value. With the
// original 4-and-6-quad fixture H then broke only ONE of the two blocks, because
// the six-quad block's renumbered pattern collided with its own by chance —
// check 26's fixture was enlarged to 16 and 20 quads for that reason, and it
// asserts its own sizes before comparing, since two unreadable blocks compare
// equal. And N is the one that found something rather than confirming it: before
// check 5b existed, disabling the `.dat`-level refusal broke NOTHING, because
// every other gate for the rule goes through the pure seam.
//
// O and P both come from the SPEC review of #54, and P from a mis-aimed
// injection. The review found that `parseBlocks` refused a duplicate corner id
// and a duplicate edge id but not a duplicate BLOCK id — harmless while nothing
// read a block id, and a correlated diagonal pattern the moment the randomized
// rule hashed it, since two blocks under one id are then cut identically. O is
// that refusal. P is what O's first attempt hit instead: the three duplicate-id
// loops are textually identical, the anchor matched the EDGE one, and disabling
// it left the whole suite green — a refusal that had been unguarded since #50.
// Check 29 covers both.
//
// FOUR MORE for the C-grid, measured 2026-09-04 the same way (each patch applied
// to src/MultiBlock.cpp alone, rebuilt, run, control run clean):
//
//   Q  a side's traversal reversal dropped for the WEST side       -> 37, 38, 39
//                                                       (and, first, check 9)
//   R  a CUT exported as a boundary face, like a wall              -> 21, 37
//   S  the four-way corner welds its first TWO users only          -> 37, 38, 39
//   T  a CUT does not join its two blocks' count classes           -> 21, 37, 38, 39
//
// Q, S and T are all caught by invariants that ALREADY existed — the four-shared-
// corner refusal and the no-seed refusal — so what checks 37-39 add is not a new
// guard but a topology that REACHES those guards: no earlier fixture puts one
// edge on the same side of two blocks, or four blocks on one corner. R is the one
// with nothing behind it: only the kind gate stops a wake cut becoming a wall
// through the middle of the fluid, and check 37 is the second thing that looks.
//
// S was scored ZERO twice before it was scored at all. Its first two forms exited
// 139 (SIGSEGV), which a run scored by counting FAIL lines reads as "no effect":
// the first pushed a node while holding a reference into the same vector, and the
// second de-welded EVERY corner with three or more users, so an ogrid fixture
// refused and an older check indexed r.blocks[0] on an empty vector. Read the
// EXIT CODE before the FAIL count.
//
// SEVEN MORE for the smoothing pass, measured 2026-09-04 the same way (each patch
// applied alone, rebuilt, BOTH this executable and
// tools/PreProcessor/tests/test_multiblock_smooth_surface.py run, exit codes read
// BEFORE the FAIL counts, control run clean). AA is against include/Config.hpp;
// the rest against src/MultiBlock.cpp:
//
//   U  the freeze lost: block-boundary nodes swept too    -> 41, 43; surface 5
//   V  Gauss-Seidel — the sweep reads what it just wrote  -> 42, 43
//   W  the seam's negative-count refusal removed          -> 44
//   X  the 'before' list never published                  -> 41, 42, 43, 46;
//                                                            surface 2, 5
//   Y  the whole sweep block moved PAST the split         -> NOTHING (see below)
//   Z  the kernel averages the two i-neighbours only      -> 42, 43, 45; surface 5
//   AA Config::validate() no longer refuses a negative    -> surface 6 only
//
// FOUR OF THOSE ARE RECORDED FOR WHAT THEY SHOWED, not for confirming a check.
//
// X exited 139 with ZERO FAIL lines in its first run — checks 42 and 43 indexed an
// empty `preSmoothNodes` — which is the third time this repo has scored a SIGSEGV
// as "the injection did nothing" (see S above, and H under the split rules). Both
// checks are now guarded, and the same patch re-run reports 7 failures.
//
// Y IS INERT, and that is recorded rather than fixed. Every reader downstream of
// the smoothing stage — the split and the boundary-edge walk — reads node IDS and
// the sides' own positions, never the interior coordinates, so moving the sweeps
// past them changes nothing today. The fill-then-smooth-then-split ordering is a
// design rule held by a comment, not by a gate; it is what makes "no downstream
// reader can tell a smoothed result from an unsmoothed one by its shape" true by
// construction rather than by re-inspecting each reader whenever one is added.
//
// TEN MORE for #82's Winslow kernel, measured 2026-09-04 the same way (each patch
// applied alone, rebuilt, BOTH this executable and
// tools/PreProcessor/tests/test_multiblock_smooth_surface.py run, exit codes read
// BEFORE the FAIL counts, control run clean). All against src/MultiBlock.cpp:
//
//   A  the kernel is the mean of the four neighbours   -> 42, 45, 46, 50 (5);
//      again (i.e. #81's deleted Laplacian)               surface 4, 5, 8 (11)
//   B  alpha and gamma swapped                         -> 42, 46, 48, 50 (4);
//                                                         surface 4, 5, 8 (5)
//   C  the cross term dropped                          -> 42, 48, 50 (3);
//                                                         surface 5, 8 (2)
//   D  the cross term's sign flipped                   -> 42, 48, 50 (3); surface 3
//   E' pp and mp filled from swapped indices           -> 42 (1); surface 5 (1)
//   F  the convergence stop removed                    -> 47, 49 (5); surface 7 (1)
//   G  the divergence rollback removed                 -> surface 7 ONLY (1)
//   H  the residual not made relative to the diagonal  -> 47 (1); surface NOTHING
//   I  the rolled-back sweep count not rolled back     -> surface 7 ONLY (1)
//   J  the sweep also writes into its own source       -> 42, 43 (2);
//      (Gauss-Seidel by the back door)                    surface 4, 5 (3)
//
// AND ONE THAT IS INERT BECAUSE IT CANNOT BE ANYTHING ELSE. E — the two OFF
// diagonals (mp and pm) filled from swapped indices — changes nothing and no gate
// can catch it, because the cross-derivative stencil is (pp - mp - pm + mm) and
// those two enter with the SAME sign. That is a symmetry of the discretisation,
// not a hole in the tests, and it is the reason E' exists: pp and mp have opposite
// signs, and swapping THOSE is caught by check 42 immediately.
//
// TWO OF THEM ARE THE ONLY REASON GROUP 7's ROLLBACK CHECK EXISTS. G (the rollback
// removed, so the last iterate is returned under the best iterate's sweep number)
// and I (the reverse) were BOTH inert against every check in this file and against
// every check the surface gate had — including the one asserting the diverged run
// exports a mesh with no folded cell, which is true of either iterate. What
// catches them is a ROUND TRIP: re-running at the sweep count the diverged run
// reports must produce that same mesh, and must itself stop at its cap rather than
// diverge. Neither half alone is enough; G passes the second and fails the first,
// I the other way round.
//
// AND H IS THE OPPOSITE SHAPE. Making the residual absolute instead of relative to
// the domain diagonal is caught HERE and by NOTHING in the surface gate. Check 47's
// box is 250 units across, so its residual goes from 1.1e-16 to 2.8e-14 and the
// solve stops calling itself converged on the first sweep. The surface gate does
// not notice because its assertions are about WHICH ENDING each case reaches, and
// neither ending moves: the divergence test is a RATIO of residuals and cancels the
// change entirely, and the O-grid still converges inside its cap, just later. A
// scale-free rule needs a fixture with a scale in it, and needs a check that reads
// the number rather than the verdict.
//
// AA left this whole executable GREEN. The seam's own door still refused the value
// — with the TOPOLOGY code instead of the CONFIG one — so only the surface gate's
// "which exit code" line caught it. Same shape as N above, and the same lesson: a
// refusal that exists twice needs a check on each door, not one on the outcome.
//
// V passed the SURFACE gate cleanly. That is the division of labour working: the
// surface gate asserts a direction with a floor, so a different-but-still-degrading
// kernel satisfies it, and the kernel's arithmetic belongs to check 42 alone.
#include "MultiBlock.hpp"
#include "check.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <set>
#include <string>
#include <vector>

using hybmesh::MbParams;
using hybmesh::MbResult;

namespace {

// A single square block, [0,1]x[0,1], with the counts and extra edge text the
// caller asks for. Written as a builder rather than as one literal per case so
// that a case differs from the valid document by exactly the thing it is about.
std::string square(int ni, int nj, const std::string& southExtra = "",
                   const std::string& blockExtra = "") {
    return std::string(R"({
  "format_version": 1,
  "corners": [
    {"id": "sw", "kind": "free", "xy": [0.0, 0.0]},
    {"id": "se", "kind": "free", "xy": [1.0, 0.0]},
    {"id": "ne", "kind": "free", "xy": [1.0, 1.0]},
    {"id": "nw", "kind": "free", "xy": [0.0, 1.0]}
  ],
  "edges": [
    {"id": "s", "corners": ["sw", "se"], "kind": "wall", "count": )") + std::to_string(ni)
        + southExtra + R"(},
    {"id": "e", "corners": ["se", "ne"], "kind": "wall", "count": )" + std::to_string(nj) + R"(},
    {"id": "n", "corners": ["nw", "ne"], "kind": "wall", "count": )" + std::to_string(ni) + R"(},
    {"id": "w", "corners": ["sw", "nw"], "kind": "wall", "count": )" + std::to_string(nj) + R"(}
  ],
  "blocks": [
    {"id": "b0", "edges": ["s", "e", "n", "w"])" + blockExtra + R"(}
  ]
})";
}

MbResult build(const std::string& doc, const MbParams& p = MbParams{}) {
    // No geometries: nothing in this release binds to one, and a document that
    // TRIES to is refused by name (check 10) rather than resolved against a list.
    return hybmesh::buildMultiBlock(doc, {}, p);
}

bool mentions(const std::string& hay, const std::string& needle) {
    return hay.find(needle) != std::string::npos;
}

// One edit to an otherwise-valid document, so a failing case differs from the
// passing one by exactly the thing it is about. Aborts loudly rather than
// silently returning the original: a swap that matched nothing would make the
// case assert against the VALID document and pass for the wrong reason.
std::string swap1(std::string doc, const std::string& from, const std::string& to) {
    const size_t at = doc.find(from);
    if (at == std::string::npos) {
        std::printf("FAIL  test setup: '%s' is not in the document\n", from.c_str());
        ++hybmesh::test::g_failures;
        return doc;
    }
    return doc.replace(at, from.size(), to);
}

// A refusal must name what is wrong AND leave nothing behind: the mode's whole
// contract is "refused with the topology exit code and nothing exported".
void refuses(const std::string& doc, const std::string& names, const std::string& what,
             const std::vector<hybmesh::MbGeometry>& geoms = {}) {
    MbResult r = hybmesh::buildMultiBlock(doc, geoms, MbParams{});
    CHECK(!r.ok, what + ": must be refused");
    CHECK(mentions(r.error, names), what + ": the message must name '" + names
                                    + "' (got: " + r.error + ")");
    CHECK(r.nodes.empty() && r.cells.empty() && r.boundaryEdges.empty() && r.blocks.empty(),
          what + ": a refusal must produce nothing");
}

// ── Two blocks, and the ways they can meet (issue #53) ────────────────────
//
//   d ──n0── e ──n1── f          b0 = [s0, m,  n0, w ]
//   │        │        │          b1 = [s1, ee, n1, m ]
//   w   b0   m   b1   ee
//   │        │        │
//   a ──s0── b ──s1── c
//
// Only THREE of the seven edges declare a count, and the choice is deliberate:
// 's0' fixes b0's i and so 'n0'; 'w' fixes b0's j and so 'm', which is b1's j and
// so 'ee'; 's1' fixes b1's i and so 'n1'. So one class spans both blocks through
// the shared edge, which is what makes a conflict report need a CHAIN.
//
// `sharedKind` is what the shared line 'm' declares, and `sharedExtra` / `wExtra`
// append to that edge and to 'w' — so a case differs from the valid document by
// exactly the thing it is about.
std::string twoBlocks(const std::string& sharedKind = "interface",
                      const std::string& sharedExtra = "",
                      const std::string& wExtra = "",
                      const std::string& eeExtra = "") {
    return std::string(R"({
  "format_version": 1,
  "corners": [
    {"id": "a", "kind": "free", "xy": [0.0, 0.0]},
    {"id": "b", "kind": "free", "xy": [1.0, 0.0]},
    {"id": "c", "kind": "free", "xy": [2.0, 0.0]},
    {"id": "d", "kind": "free", "xy": [0.0, 1.0]},
    {"id": "e", "kind": "free", "xy": [1.0, 1.0]},
    {"id": "f", "kind": "free", "xy": [2.0, 1.0]}
  ],
  "edges": [
    {"id": "s0", "corners": ["a", "b"], "kind": "wall", "count": 3},
    {"id": "s1", "corners": ["b", "c"], "kind": "wall", "count": 4},
    {"id": "w", "corners": ["a", "d"], "kind": "wall", "count": 3)") + wExtra + R"(},
    {"id": "m", "corners": ["b", "e"], "kind": ")" + sharedKind + R"(")" + sharedExtra + R"(},
    {"id": "n0", "corners": ["d", "e"], "kind": "wall"},
    {"id": "n1", "corners": ["e", "f"], "kind": "wall"},
    {"id": "ee", "corners": ["c", "f"], "kind": "wall")" + eeExtra + R"(}
  ],
  "blocks": [
    {"id": "b0", "edges": ["s0", "m", "n0", "w"]},
    {"id": "b1", "edges": ["s1", "ee", "n1", "m"]}
  ]
})";
}

// ── The diagonal each quad actually took (issue #54) ──────────────────────
//
// Read BACK from the emitted cells rather than recomputed from the rule, so what
// it reports is what the mesh holds. `true` = the forward (i,j)-(i+1,j+1)
// diagonal, in the (j, i) order the fill emits.
//
// Keyed by the block's declared ID and not by its index, because that is exactly
// the difference the invariance check below is about: the same block sits at a
// different index once another block is declared ahead of it.
std::vector<bool> diagonals(const MbResult& r, const std::string& id) {
    int bi = -1;
    for (size_t k = 0; k < r.blocks.size(); ++k)
        if (r.blocks[k].id == id) bi = static_cast<int>(k);
    if (bi < 0) return {};
    const hybmesh::MbBlock& b = r.blocks[static_cast<size_t>(bi)];

    std::vector<const hybmesh::MbCell*> mine;
    for (const auto& c : r.cells) if (c.block == bi) mine.push_back(&c);

    std::vector<bool> out;
    size_t q = 0;
    for (int j = 0; j + 1 < b.nj; ++j) {
        for (int i = 0; i + 1 < b.ni; ++i, ++q) {
            if (2 * q + 1 >= mine.size() || mine[2 * q]->nodeIds.size() != 3) return {};
            out.push_back(mine[2 * q]->nodeIds[2] == b.nodeAt(i + 1, j + 1));
        }
    }
    return out;
}

MbParams splitRule(int rule, unsigned seed = 0) {
    MbParams p;
    p.splitRule = rule;
    p.splitSeed = seed;
    return p;
}

// The whole mesh's connectivity as one comparable string: every cell's node ids
// in order. What "byte-identical connectivity" means for this seam, and what a
// diagonal decides -- so two runs that agree here produce the same export.
std::string connectivity(const MbResult& r) {
    std::string out;
    for (const auto& c : r.cells) {
        for (int v : c.nodeIds) out += std::to_string(v) + ",";
        out += ";";
    }
    return out;
}

// Two welded blocks, and OPTIONALLY a third, entirely unrelated one declared
// AHEAD of them: its own four corners, its own four edges, off to the right and
// touching nothing. One builder for both documents, so the pair differs by
// exactly the extra block and by nothing else.
//
// Declared FIRST rather than appended, and that is the point of the fixture. An
// appended block cannot tell an index-based hash from an id-based one -- every
// existing block keeps its index. Inserting one ahead of them renumbers both, so
// a rule that hashed the index would move every diagonal in the mesh, which is
// the failure this fixture exists to catch.
//
// The counts are larger than `twoBlocks()`'s (16 and 20 quads rather than 4 and
// 6) for a reason measured during the injection runs: at 6 quads a renumbered
// block's pattern collided with its own by chance, so half the check went quiet
// while the other half caught the injection. A block of 16 quads makes that
// coincidence 2^-16.
std::string weldedPair(bool withUnrelated) {
    const std::string unrelatedCorners = withUnrelated ? R"(,
    {"id": "p", "kind": "free", "xy": [5.0, 0.0]},
    {"id": "q", "kind": "free", "xy": [6.0, 0.0]},
    {"id": "r", "kind": "free", "xy": [6.0, 1.0]},
    {"id": "t", "kind": "free", "xy": [5.0, 1.0]})" : "";
    const std::string unrelatedEdges = withUnrelated ? R"(,
    {"id": "xs", "corners": ["p", "q"], "kind": "wall", "count": 5},
    {"id": "xe", "corners": ["q", "r"], "kind": "wall", "count": 4},
    {"id": "xn", "corners": ["t", "r"], "kind": "wall", "count": 5},
    {"id": "xw", "corners": ["p", "t"], "kind": "wall", "count": 4})" : "";
    const std::string unrelatedBlock = withUnrelated
        ? R"(    {"id": "bx", "edges": ["xs", "xe", "xn", "xw"]},
)" : "";
    return std::string(R"({
  "format_version": 1,
  "corners": [
    {"id": "a", "kind": "free", "xy": [0.0, 0.0]},
    {"id": "b", "kind": "free", "xy": [1.0, 0.0]},
    {"id": "c", "kind": "free", "xy": [2.0, 0.0]},
    {"id": "d", "kind": "free", "xy": [0.0, 1.0]},
    {"id": "e", "kind": "free", "xy": [1.0, 1.0]},
    {"id": "f", "kind": "free", "xy": [2.0, 1.0]})") + unrelatedCorners + R"(
  ],
  "edges": [
    {"id": "s0", "corners": ["a", "b"], "kind": "wall", "count": 5},
    {"id": "s1", "corners": ["b", "c"], "kind": "wall", "count": 6},
    {"id": "w", "corners": ["a", "d"], "kind": "wall", "count": 5},
    {"id": "m", "corners": ["b", "e"], "kind": "interface"},
    {"id": "n0", "corners": ["d", "e"], "kind": "wall"},
    {"id": "n1", "corners": ["e", "f"], "kind": "wall"},
    {"id": "ee", "corners": ["c", "f"], "kind": "wall"})" + unrelatedEdges + R"(
  ],
  "blocks": [
)" + unrelatedBlock + R"(    {"id": "b0", "edges": ["s0", "m", "n0", "w"]},
    {"id": "b1", "edges": ["s1", "ee", "n1", "m"]}
  ]
})";
}

// The same two blocks, with the RIGHT one turned a quarter turn: its i direction
// runs DOWN the shared edge 'm', which the left block uses as its own j
// direction. 'm' is declared once, [e, b], so b1 traverses it forwards and b0
// backwards — the two blocks genuinely disagree about which way the shared edge
// runs, which is the case a per-block reversal exists for and one that cannot be
// reached with both blocks in the same frame.
std::string rotatedNeighbour() {
    return R"({
  "format_version": 1,
  "corners": [
    {"id": "a", "kind": "free", "xy": [0.0, 0.0]},
    {"id": "b", "kind": "free", "xy": [1.0, 0.0]},
    {"id": "c", "kind": "free", "xy": [2.0, 0.0]},
    {"id": "d", "kind": "free", "xy": [0.0, 1.0]},
    {"id": "e", "kind": "free", "xy": [1.0, 1.0]},
    {"id": "f", "kind": "free", "xy": [2.0, 1.0]}
  ],
  "edges": [
    {"id": "s0", "corners": ["a", "b"], "kind": "wall", "count": 3},
    {"id": "w",  "corners": ["a", "d"], "kind": "wall", "count": 3},
    {"id": "m",  "corners": ["e", "b"], "kind": "interface"},
    {"id": "n0", "corners": ["d", "e"], "kind": "wall"},
    {"id": "n1", "corners": ["e", "f"], "kind": "wall", "count": 4},
    {"id": "s1", "corners": ["b", "c"], "kind": "wall"},
    {"id": "ee", "corners": ["c", "f"], "kind": "wall"}
  ],
  "blocks": [
    {"id": "b0", "edges": ["s0", "m", "n0", "w"]},
    {"id": "b1", "edges": ["m", "s1", "ee", "n1"]}
  ]
})";
}

// The same two blocks, with the shared line declared as TWO edges whose corners
// sit at IDENTICAL coordinates under different ids ('b2' on 'b', 'e2' on 'e').
// Nothing may weld them: the negative control for "no distance tolerance appears
// anywhere in the welding path", asked at a separation of exactly zero.
std::string coincidentButSeparate() {
    return R"({
  "format_version": 1,
  "corners": [
    {"id": "a",  "kind": "free", "xy": [0.0, 0.0]},
    {"id": "b",  "kind": "free", "xy": [1.0, 0.0]},
    {"id": "b2", "kind": "free", "xy": [1.0, 0.0]},
    {"id": "c",  "kind": "free", "xy": [2.0, 0.0]},
    {"id": "d",  "kind": "free", "xy": [0.0, 1.0]},
    {"id": "e",  "kind": "free", "xy": [1.0, 1.0]},
    {"id": "e2", "kind": "free", "xy": [1.0, 1.0]},
    {"id": "f",  "kind": "free", "xy": [2.0, 1.0]}
  ],
  "edges": [
    {"id": "s0", "corners": ["a", "b"], "kind": "wall", "count": 3},
    {"id": "w",  "corners": ["a", "d"], "kind": "wall", "count": 3},
    {"id": "m0", "corners": ["b", "e"], "kind": "wall"},
    {"id": "n0", "corners": ["d", "e"], "kind": "wall"},
    {"id": "s1", "corners": ["b2", "c"], "kind": "wall", "count": 4},
    {"id": "m1", "corners": ["b2", "e2"], "kind": "wall", "count": 3},
    {"id": "n1", "corners": ["e2", "f"], "kind": "wall"},
    {"id": "ee", "corners": ["c", "f"], "kind": "wall"}
  ],
  "blocks": [
    {"id": "b0", "edges": ["s0", "m0", "n0", "w"]},
    {"id": "b1", "edges": ["s1", "ee", "n1", "m1"]}
  ]
})";
}

// How many pairs of nodes sit at EXACTLY the same place. Exact equality on
// purpose: the claim is that welding is topological, so a welded mesh has none of
// these and an unwelded one has exactly as many as it duplicated. A tolerance
// here would be the very thing under test.
size_t coincidentPairs(const std::vector<Point2D>& nodes) {
    size_t n = 0;
    for (size_t i = 0; i < nodes.size(); ++i)
        for (size_t j = i + 1; j < nodes.size(); ++j)
            if (nodes[i].x == nodes[j].x && nodes[i].y == nodes[j].y) ++n;
    return n;
}

size_t invertedCells(const MbResult& r) {
    size_t bad = 0;
    for (const auto& c : r.cells) {
        const size_t k = c.nodeIds.size();
        for (size_t t = 0; t < k; ++t) {
            const Point2D& p = r.nodes[static_cast<size_t>(c.nodeIds[(t + k - 1) % k])];
            const Point2D& q = r.nodes[static_cast<size_t>(c.nodeIds[t])];
            const Point2D& s = r.nodes[static_cast<size_t>(c.nodeIds[(t + 1) % k])];
            if ((q - p).cross(s - q) <= 0.0) { ++bad; break; }
        }
    }
    return bad;
}

// One edge's resolved count, and the ids the document actually SEEDED, read off
// the result rather than recomputed — the point of publishing them is that a run
// can show which of the two each count was.
int countOf(const MbResult& r, const std::string& id) {
    for (const auto& ec : r.edgeCounts) if (ec.edgeId == id) return ec.count;
    return -1;
}

std::vector<std::string> seededSet(const MbResult& r) {
    std::vector<std::string> out;
    for (const auto& ec : r.edgeCounts) if (ec.seeded) out.push_back(ec.edgeId);
    std::sort(out.begin(), out.end());
    return out;
}

// ── A geometry, as the loader and the sidecar together hand one over ──────
//
// A CLOSED unit square walked counter-clockwise from the origin, `perSide` points
// on each side, split into four source segments with a boundary condition label
// each. Two conventions of the real chain are reproduced here EXACTLY, because
// getting either wrong moves an attachment by one resampling interval — which is
// the failure this whole feature exists to prevent, and which no round number in
// a hand-written fixture would reveal:
//
//   * a joint shared by two segments belongs to the LATER of them, so a segment's
//     own points stop one point short of where it ends (measured against the real
//     `surface_resampler`, whose output this mirrors);
//   * the loader drops the duplicate closing point of a closed loop, so the last
//     segment's end is index 0 and not one past the end.
//
// `perSide` is the parameter the re-resampling check varies: two calls with
// different counts are two resamplings of ONE geometry.
hybmesh::MbGeometry squareGeom(int perSide, const std::string& file = "square.dat") {
    hybmesh::MbGeometry g;
    g.file = file;
    g.closed = true;
    const Point2D corner[4] = {{0.0, 0.0}, {1.0, 0.0}, {1.0, 1.0}, {0.0, 1.0}};
    for (int side = 0; side < 4; ++side) {
        const Point2D a = corner[side], b = corner[(side + 1) % 4];
        for (int k = 0; k < perSide; ++k) {
            const double u = static_cast<double>(k) / perSide;   // k == perSide is b,
            g.points.push_back({a.x + (b.x - a.x) * u,           // i.e. the next
                                a.y + (b.y - a.y) * u});         // segment's first point
            g.segId.push_back(side + 1);
        }
    }
    g.segBc = {{1, "bottom"}, {2, "outlet"}, {3, "top"}, {4, "inlet"}};
    return g;
}

// A block sitting on the square's SOUTH side. `southBind` and the corner
// declarations are what each case varies; everything else is held fixed so a
// failing case differs from the passing one by exactly the thing it is about.
std::string boundSquare(const std::string& sw, const std::string& se,
                        const std::string& southBind = R"(, "binding": {"geom": "square.dat", "seg": 1})") {
    return std::string(R"({
  "format_version": 1,
  "corners": [
    )") + sw + R"(,
    )" + se + R"(,
    {"id": "ne", "kind": "free", "xy": [1.0, 0.5]},
    {"id": "nw", "kind": "free", "xy": [0.0, 0.5]}
  ],
  "edges": [
    {"id": "s", "corners": ["sw", "se"], "kind": "wall", "count": 5)" + southBind + R"(},
    {"id": "e", "corners": ["se", "ne"], "kind": "wall", "count": 3},
    {"id": "n", "corners": ["nw", "ne"], "kind": "wall", "count": 5},
    {"id": "w", "corners": ["sw", "nw"], "kind": "wall", "count": 3}
  ],
  "blocks": [
    {"id": "b0", "edges": ["s", "e", "n", "w"]}
  ]
})";
}

// The two corners of that block's south side, attached to segment 1 at `t0`/`t1`.
std::string att(const std::string& id, double t, int seg = 1,
                const std::string& geom = "square.dat") {
    return "{\"id\": \"" + id + "\", \"kind\": \"on_geometry\", \"geom\": \""
         + geom + "\", \"seg\": " + std::to_string(seg) + ", \"t\": "
         + std::to_string(t) + "}";
}

// A CLOSED circle of `perQuarter` points per quarter, in four source segments —
// the same two conventions `squareGeom` reproduces (a joint belongs to the LATER
// segment; the loader dropped the closing duplicate), on a body that is CURVED.
//
// Curved is the point: on a straight side an arc-length attachment is exact and a
// chord IS the geometry, so nothing a square can express distinguishes an edge
// that follows its segment from one that cuts across it.
// `nseg` is how many source segments the circle is cut into, and it is a
// parameter rather than a constant because a C-grid body is cut in TWO (an upper
// surface and a lower one, joined at the two points a block corner has to sit on)
// while an O-grid body is cut in four.
hybmesh::MbGeometry circleGeom(int perSeg, double radius,
                               const std::string& file, const std::string& bc,
                               int nseg = 4) {
    hybmesh::MbGeometry g;
    g.file = file;
    g.closed = true;
    const int n = nseg * perSeg;
    for (int k = 0; k < n; ++k) {
        const double a = 2.0 * M_PI * k / n;
        g.points.push_back({radius * std::cos(a), radius * std::sin(a)});
        g.segId.push_back((k / perSeg) % nseg);
    }
    for (int s = 0; s < nseg; ++s) g.segBc[s] = bc;
    return g;
}

// A four-block O-GRID around `circleGeom`: four radial interfaces, four bound
// body arcs, four bound far-field arcs.
//
// The RING is what this fixture exists for. Each block's south and north are two
// consecutive radials, so the four of them are ONE equivalence class — and the
// class WRAPS: 'q3' has 'r3' as its south and 'r0' as its north, closing the ring
// back onto the edge 'q0' declares as ITS south. Only 'r0' carries a count.
//
// `radialSpacing` is appended to every radial edge, so a case differs from the
// plain one by exactly the clustering it declares.
std::string ogrid(const std::string& radialSpacing = "", int radialCount = 7,
                  int arcCount = 5, const std::string& arcSpacing = "") {
    std::string doc = R"({
  "format_version": 1,
  "corners": [)";
    for (int k = 0; k < 4; ++k) {
        doc += (k ? ",\n    " : "\n    ");
        doc += "{\"id\": \"b" + std::to_string(k) + "\", \"kind\": \"on_geometry\", "
               "\"geom\": \"body.dat\", \"seg\": " + std::to_string(k) + ", \"t\": 0.0}";
    }
    for (int k = 0; k < 4; ++k) {
        doc += ",\n    ";
        doc += "{\"id\": \"f" + std::to_string(k) + "\", \"kind\": \"on_geometry\", "
               "\"geom\": \"far.dat\", \"seg\": " + std::to_string(k) + ", \"t\": 0.0}";
    }
    doc += "\n  ],\n  \"edges\": [";
    for (int k = 0; k < 4; ++k) {
        doc += (k ? ",\n    " : "\n    ");
        doc += "{\"id\": \"r" + std::to_string(k) + "\", \"corners\": [\"b"
             + std::to_string(k) + "\", \"f" + std::to_string(k) + "\"], "
               "\"kind\": \"interface\"";
        if (k == 0) doc += ", \"count\": " + std::to_string(radialCount);
        doc += radialSpacing + "}";
    }
    for (int k = 0; k < 4; ++k) {
        const std::string nxt = std::to_string((k + 1) % 4);
        doc += ",\n    {\"id\": \"w" + std::to_string(k) + "\", \"corners\": [\"b"
             + std::to_string(k) + "\", \"b" + nxt + "\"], \"kind\": \"wall\", "
               "\"count\": " + std::to_string(arcCount)
             + ", \"binding\": {\"geom\": \"body.dat\", \"seg\": "
             + std::to_string(k) + "}" + arcSpacing + "}";
        doc += ",\n    {\"id\": \"o" + std::to_string(k) + "\", \"corners\": [\"f"
             + std::to_string(k) + "\", \"f" + nxt + "\"], \"kind\": \"wall\""
               ", \"binding\": {\"geom\": \"far.dat\", \"seg\": "
             + std::to_string(k) + "}}";
    }
    doc += "\n  ],\n  \"blocks\": [";
    for (int k = 0; k < 4; ++k) {
        doc += (k ? ",\n    " : "\n    ");
        doc += "{\"id\": \"q" + std::to_string(k) + "\", \"edges\": [\"r"
             + std::to_string(k) + "\", \"o" + std::to_string(k) + "\", \"r"
             + std::to_string((k + 1) % 4) + "\", \"w" + std::to_string(k) + "\"]}";
    }
    doc += "\n  ]\n}";
    return doc;
}

// One node of one filled block, by its logical index. A three-line reader, added
// where four checks below wanted the same two lines each.
Point2D nodeOf(const MbResult& r, const hybmesh::MbBlock& b, int i, int j) {
    return r.nodes[static_cast<size_t>(b.nodeAt(i, j))];
}

std::vector<hybmesh::MbGeometry> ogridGeoms(int perQuarter = 40) {
    return {circleGeom(perQuarter, 0.5, "body.dat", "wall"),
            circleGeom(perQuarter / 2, 10.0, "far.dat", "farfield")};
}


// ── A four-block C-GRID: a cut, and a four-way corner (issue #57) ─────────
//
//                fu ────e_ff_up──── f1 ───e_ff_nose_up─── f2
//                 │                  │                     │
//              e_out_up  b_wake_up  r_te_up    b_upper    r_le
//                 │                  │                     │
//                wk ─────wake────── te ──────af_up──────── le
//                 │                  │                     │
//              e_out_lo  b_wake_lo  r_te_lo    b_lower    r_le
//                 │                  │                     │
//                fl ────e_ff_lo──── f3 ───e_ff_nose_lo─── f2
//
// (the two halves are drawn apart; `te`, `le`, `wake` and `r_le` are ONE
// declaration each, which is the whole point.)
//
// The body is a CIRCLE in two segments so that `af_up` and `af_lo` are distinct
// curves with the joints exactly where the block corners are — a straight chord
// from `te` to `le` would make the two surface edges the same line and the two
// airfoil blocks degenerate. The far field is free corners and straight chords:
// nothing here is about geometry binding, which #52 and #55 already pin.
//
// TWO STRUCTURAL FACTS NO EARLIER FIXTURE HAS.
//
//   * `wake` is the WEST of BOTH wake blocks. Every shared edge before this one
//     was one block's east and another's west, so the two frames ran the same
//     way along it; here they are mirror images and the edge is traversed in
//     OPPOSITE senses from the same side index.
//   * `te` is on FIVE edges and all FOUR blocks meet on it. Nothing else in this
//     file puts more than two blocks on one corner.
std::string cgrid() {
    return R"({
  "format_version": 1,
  "corners": [
    {"id": "te", "kind": "on_geometry", "geom": "body.dat", "seg": 0, "t": 0.0},
    {"id": "le", "kind": "on_geometry", "geom": "body.dat", "seg": 1, "t": 0.0},
    {"id": "wk", "kind": "free", "xy": [10.0,  0.0]},
    {"id": "fu", "kind": "free", "xy": [10.0,  5.0]},
    {"id": "f1", "kind": "free", "xy": [ 0.5,  5.0]},
    {"id": "f2", "kind": "free", "xy": [-5.0,  0.0]},
    {"id": "f3", "kind": "free", "xy": [ 0.5, -5.0]},
    {"id": "fl", "kind": "free", "xy": [10.0, -5.0]}
  ],
  "edges": [
    {"id": "wake",    "corners": ["te", "wk"], "kind": "cut", "count": 4},
    {"id": "r_te_up", "corners": ["te", "f1"], "kind": "interface", "count": 3},
    {"id": "r_le",    "corners": ["le", "f2"], "kind": "interface"},
    {"id": "r_te_lo", "corners": ["te", "f3"], "kind": "interface"},
    {"id": "af_up", "corners": ["te", "le"], "kind": "wall", "count": 6,
     "binding": {"geom": "body.dat", "seg": 0}},
    {"id": "af_lo", "corners": ["le", "te"], "kind": "wall", "count": 6,
     "binding": {"geom": "body.dat", "seg": 1}},
    {"id": "e_out_up",     "corners": ["wk", "fu"], "kind": "wall"},
    {"id": "e_ff_up",      "corners": ["fu", "f1"], "kind": "wall"},
    {"id": "e_ff_nose_up", "corners": ["f1", "f2"], "kind": "wall"},
    {"id": "e_ff_nose_lo", "corners": ["f2", "f3"], "kind": "wall"},
    {"id": "e_ff_lo",      "corners": ["f3", "fl"], "kind": "wall"},
    {"id": "e_out_lo",     "corners": ["wk", "fl"], "kind": "wall"}
  ],
  "blocks": [
    {"id": "b_wake_up", "edges": ["e_out_up", "e_ff_up", "r_te_up", "wake"]},
    {"id": "b_upper",   "edges": ["r_te_up", "e_ff_nose_up", "r_le", "af_up"]},
    {"id": "b_lower",   "edges": ["r_le", "e_ff_nose_lo", "r_te_lo", "af_lo"]},
    {"id": "b_wake_lo", "edges": ["r_te_lo", "e_ff_lo", "e_out_lo", "wake"]}
  ]
})";
}

// The C-grid's one geometry: the body, cut into an upper and a lower surface.
std::vector<hybmesh::MbGeometry> cgridGeoms(int perSeg = 40) {
    return {circleGeom(perSeg, 0.5, "body.dat", "wall", 2)};
}

// ── The C-grid made DENSE and WALL-CLUSTERED (issue #81, check 46) ────────
//
// Two edits to the fixture above, and both are load bearing — measured, not
// assumed. At the counts checks 37-39 use, each block has ONE interior row, and a
// Laplacian over one row between frozen boundaries relaxes toward a straight line
// and folds NOTHING however many sweeps it runs. Raising the counts alone is still
// not enough: 60 sweeps on the denser UNIFORM grid also fold nothing.
//
// What makes a fold reachable is the CLUSTERING, which is exactly the mechanism at
// work on the shipped grid: the three radials ask for a first cell of 0.002 off a
// body of radius 0.5 in a far field of radius 5, the kernel equalises that grading
// against a frozen wall line, and the near-wall row is dragged out past its
// neighbours. 0 folded quads before, 26 after. So this is not "the same fixture but
// bigger" — it is the smallest one here that reproduces what the shipped C-grid
// does at 5 sweeps.
std::string cgridClustered(const std::string& ds = "0.002") {
    std::string d = cgrid();
    d = swap1(d, R"("kind": "cut", "count": 4)", R"("kind": "cut", "count": 12)");
    d = swap1(d, R"("id": "r_te_up", "corners": ["te", "f1"], "kind": "interface", "count": 3)",
              R"("id": "r_te_up", "corners": ["te", "f1"], "kind": "interface", "count": 15,
     "spacing": {"ds_start": )" + ds + R"(})");
    d = swap1(d, R"("id": "r_le",    "corners": ["le", "f2"], "kind": "interface")",
              R"("id": "r_le",    "corners": ["le", "f2"], "kind": "interface",
     "spacing": {"ds_start": )" + ds + R"(})");
    d = swap1(d, R"("id": "r_te_lo", "corners": ["te", "f3"], "kind": "interface")",
              R"("id": "r_te_lo", "corners": ["te", "f3"], "kind": "interface",
     "spacing": {"ds_start": )" + ds + R"(})");
    d = swap1(d, R"("id": "af_up", "corners": ["te", "le"], "kind": "wall", "count": 6)",
              R"("id": "af_up", "corners": ["te", "le"], "kind": "wall", "count": 25)");
    d = swap1(d, R"("id": "af_lo", "corners": ["le", "te"], "kind": "wall", "count": 6)",
              R"("id": "af_lo", "corners": ["le", "te"], "kind": "wall", "count": 25)");
    return d;
}

// ── A wall block, graded off its SOUTH side (issue #81) ───────────────────
//
// The unit square again, but with both j-running sides declaring the same
// first-cell height at their START, so every column's first cell off the south
// side is `ds` and the block is graded in j and uniform in i. That is the shape a
// wall block on this path really has, and it is the one a plain Laplacian sweep is
// known to spoil: the kernel equalises spacing, so it pulls the first interior
// line AWAY from the wall.
//
// Uniform in i and graded in j on purpose: the fill then puts node (i, j) at
// (i/(ni-1), g(j)) exactly, so a sweep's effect on each coordinate is separately
// predictable and check 45's "the first cell got taller" cannot be an artefact of
// the two directions interacting.
std::string wallSquare(int ni, int nj, const std::string& ds) {
    const std::string sp = R"(, "spacing": {"ds_start": )" + ds + "}";
    return std::string(R"({
  "format_version": 1,
  "corners": [
    {"id": "sw", "kind": "free", "xy": [0.0, 0.0]},
    {"id": "se", "kind": "free", "xy": [1.0, 0.0]},
    {"id": "ne", "kind": "free", "xy": [1.0, 1.0]},
    {"id": "nw", "kind": "free", "xy": [0.0, 1.0]}
  ],
  "edges": [
    {"id": "s", "corners": ["sw", "se"], "kind": "wall", "count": )") + std::to_string(ni)
        + R"(},
    {"id": "e", "corners": ["se", "ne"], "kind": "wall", "count": )" + std::to_string(nj)
        + sp + R"(},
    {"id": "n", "corners": ["nw", "ne"], "kind": "wall", "count": )" + std::to_string(ni)
        + R"(},
    {"id": "w", "corners": ["sw", "nw"], "kind": "wall", "count": )" + std::to_string(nj)
        + sp + R"(}
  ],
  "blocks": [
    {"id": "b0", "edges": ["s", "e", "n", "w"]}
  ]
})";
}

// ── A UNIFORM grid on a STRETCHED rectangle (issue #82) ───────────────────
//
// `w` by `h` with every edge uniformly spaced, so node (i, j) lands exactly at
// (i*w/(ni-1), j*h/(nj-1)). This is the grid whose Winslow answer is known in
// closed form: every second difference of a bilinear-in-(i, j) map is zero, so
// the elliptic residual is zero whatever the metric coefficients are and the
// solve must return the grid UNMOVED. Check 47 is that gate, and its docstring
// says plainly what such a grid can and cannot catch.
//
// The aspect ratio is the point of the "stretched" — #80's grids run 250:1 from a
// wall to the far field, and a kernel that only holds a square is a kernel that
// holds nothing this path makes.
std::string stretchedBox(int ni, int nj, const std::string& w, const std::string& h) {
    return std::string(R"({
  "format_version": 1,
  "corners": [
    {"id": "sw", "kind": "free", "xy": [0.0, 0.0]},
    {"id": "se", "kind": "free", "xy": [)") + w + R"(, 0.0]},
    {"id": "ne", "kind": "free", "xy": [)" + w + ", " + h + R"(]},
    {"id": "nw", "kind": "free", "xy": [0.0, )" + h + R"(]}
  ],
  "edges": [
    {"id": "s", "corners": ["sw", "se"], "kind": "wall", "count": )" + std::to_string(ni) + R"(},
    {"id": "e", "corners": ["se", "ne"], "kind": "wall", "count": )" + std::to_string(nj) + R"(},
    {"id": "n", "corners": ["nw", "ne"], "kind": "wall", "count": )" + std::to_string(ni) + R"(},
    {"id": "w", "corners": ["sw", "nw"], "kind": "wall", "count": )" + std::to_string(nj) + R"(}
  ],
  "blocks": [
    {"id": "b0", "edges": ["s", "e", "n", "w"]}
  ]
})";
}

// ── A NON-CONVEX block, which the algebraic fill FOLDS (issue #82) ────────
//
// The unit square with its north-east corner pulled back inside the other three,
// so the block's own boundary is re-entrant there. Transfinite interpolation
// blends the four sides and has no way to notice: it lays cells straight across
// the notch and some of them come out folded, on a declaration that is perfectly
// valid. Check 50 is what that fixture is for.
//
// `ne` is BOTH coordinates of that corner, so one number says how deep the notch
// is. At 0.35 the fill folds 13 quads of the 11x9 grid; at 0.45 it folds 2.
std::string notchedBox(int ni, int nj, const std::string& ne) {
    return std::string(R"({
  "format_version": 1,
  "corners": [
    {"id": "sw", "kind": "free", "xy": [0.0, 0.0]},
    {"id": "se", "kind": "free", "xy": [1.0, 0.0]},
    {"id": "ne", "kind": "free", "xy": [)") + ne + ", " + ne + R"(]},
    {"id": "nw", "kind": "free", "xy": [0.0, 1.0]}
  ],
  "edges": [
    {"id": "s", "corners": ["sw", "se"], "kind": "wall", "count": )" + std::to_string(ni) + R"(},
    {"id": "e", "corners": ["se", "ne"], "kind": "wall", "count": )" + std::to_string(nj) + R"(},
    {"id": "n", "corners": ["nw", "ne"], "kind": "wall", "count": )" + std::to_string(ni) + R"(},
    {"id": "w", "corners": ["sw", "nw"], "kind": "wall", "count": )" + std::to_string(nj) + R"(}
  ],
  "blocks": [
    {"id": "b0", "edges": ["s", "e", "n", "w"]}
  ]
})";
}

// One WINSLOW sweep, computed HERE from `src` and returned, so a check can compare
// the seam's answer against an independent one rather than against itself.
// Deliberately Jacobi (every node reads `src`), which is the property check 43 is
// about.
//
// The arithmetic is SPELT OUT rather than delegated to `hybmesh::mbWinslowUpdate`,
// on purpose and against this repo's usual objection to a near-copy: a re-derivation
// that called the thing it is checking would make check 43 an identity. The kernel
// itself is pinned against HAND NUMBERS in check 48, which is where a disagreement
// between these two expressions gets adjudicated.
std::vector<Point2D> sweepByHand(const MbResult& r, const std::vector<Point2D>& src) {
    std::vector<Point2D> out = src;
    auto at = [&src](const hybmesh::MbBlock& b, int i, int j) {
        return src[static_cast<size_t>(b.nodeAt(i, j))];
    };
    for (const hybmesh::MbBlock& b : r.blocks)
        for (int j = 1; j + 1 < b.nj; ++j)
            for (int i = 1; i + 1 < b.ni; ++i) {
                const double xi = 0.5 * (at(b, i + 1, j).x - at(b, i - 1, j).x);
                const double yi = 0.5 * (at(b, i + 1, j).y - at(b, i - 1, j).y);
                const double xj = 0.5 * (at(b, i, j + 1).x - at(b, i, j - 1).x);
                const double yj = 0.5 * (at(b, i, j + 1).y - at(b, i, j - 1).y);
                const double al = xj * xj + yj * yj;
                const double be = xi * xj + yi * yj;
                const double ga = xi * xi + yi * yi;
                const double xij = 0.25 * (at(b, i + 1, j + 1).x - at(b, i - 1, j + 1).x
                                         - at(b, i + 1, j - 1).x + at(b, i - 1, j - 1).x);
                const double yij = 0.25 * (at(b, i + 1, j + 1).y - at(b, i - 1, j + 1).y
                                         - at(b, i + 1, j - 1).y + at(b, i - 1, j - 1).y);
                const double den = 2.0 * (al + ga);
                if (!(den > 0.0)) continue;
                out[static_cast<size_t>(b.nodeAt(i, j))] = Point2D{
                    (al * (at(b, i + 1, j).x + at(b, i - 1, j).x)
                     + ga * (at(b, i, j + 1).x + at(b, i, j - 1).x)
                     - 2.0 * be * xij) / den,
                    (al * (at(b, i + 1, j).y + at(b, i - 1, j).y)
                     + ga * (at(b, i, j + 1).y + at(b, i, j - 1).y)
                     - 2.0 * be * yij) / den};
            }
    return out;
}

// The same sweep with the kernel #81 shipped and #82 deleted: the mean of a node's
// four logical neighbours in PHYSICAL space. Kept in the test and nowhere else,
// because several checks below are about the two kernels giving DIFFERENT answers
// and a claim like that needs both sides written down.
std::vector<Point2D> laplacianByHand(const MbResult& r, const std::vector<Point2D>& src) {
    std::vector<Point2D> out = src;
    for (const hybmesh::MbBlock& b : r.blocks)
        for (int j = 1; j + 1 < b.nj; ++j)
            for (int i = 1; i + 1 < b.ni; ++i) {
                const Point2D sum = src[static_cast<size_t>(b.nodeAt(i - 1, j))]
                                  + src[static_cast<size_t>(b.nodeAt(i + 1, j))]
                                  + src[static_cast<size_t>(b.nodeAt(i, j - 1))]
                                  + src[static_cast<size_t>(b.nodeAt(i, j + 1))];
                out[static_cast<size_t>(b.nodeAt(i, j))] = sum * 0.25;
            }
    return out;
}

// Only the SMOOTHER's warnings. Every fixture in this file declares no binding and
// so already carries one warning about the default BC; counting the whole list
// would make every check below assert on that one too, and a check that has to be
// re-tuned when an unrelated warning is added is a check nobody will keep true.
std::vector<std::string> smoothWarnings(const MbResult& r) {
    std::vector<std::string> out;
    for (const std::string& w : r.warnings)
        if (w.find("smoother") != std::string::npos) out.push_back(w);
    return out;
}

// The worst distance between two parallel node lists, or -1 when they are not
// parallel at all. NEGATIVE for "not comparable", the same convention MbQuality
// uses, so "they agree perfectly" and "there was nothing to compare" cannot print
// as the same number.
double worstMove(const std::vector<Point2D>& a, const std::vector<Point2D>& b) {
    if (a.size() != b.size()) return -1.0;
    double worst = 0.0;
    for (size_t k = 0; k < a.size(); ++k) {
        const double d = (a[k] - b[k]).length();
        if (d > worst) worst = d;
    }
    return worst;
}

}  // namespace

int main() {
    // ── 1. a valid minimal topology fills the block ────────────────────────
    {
        MbResult r = build(square(4, 3));
        CHECK(r.ok, "1. a valid single-block square is accepted (err: " + r.error + ")");
        CHECK(r.error.empty(), "1. an accepted document reports no error");
        CHECK(r.blocks.size() == 1, "1. one block comes back");
        if (r.blocks.size() == 1) {
            const auto& b = r.blocks[0];
            CHECK(b.id == "b0", "1. the block keeps its declared id");
            CHECK(b.ni == 4 && b.nj == 3,
                  "1. the block's logical i/j node counts are the declared counts");
            CHECK(b.nodeIds.size() == 12, "1. the block indexes ni*nj nodes");
        }
        CHECK(r.nodes.size() == 12, "1. ni*nj nodes are produced");
    }

    // ── 2. logical i/j is retained, and the fill is exact on a rectangle ────
    // Transfinite interpolation on a rectangle degenerates to the tensor
    // product of the two side distributions, which is why v0 rests on it with
    // no smoother. Asserting the interior node, not just the corners, is what
    // makes that a claim about the fill rather than about the parser.
    {
        MbResult r = build(square(4, 3));
        CHECK(r.ok, "2. setup");
        if (r.ok && r.blocks.size() == 1) {
            const auto& b = r.blocks[0];
            for (int j = 0; j < b.nj; ++j) {
                for (int i = 0; i < b.ni; ++i) {
                    const auto& p = r.nodes[static_cast<size_t>(b.nodeAt(i, j))];
                    CHECK_NEAR(p.x, i / 3.0, 1e-12, "2. node(" + std::to_string(i) + ","
                               + std::to_string(j) + ").x is the uniform i fraction");
                    CHECK_NEAR(p.y, j / 2.0, 1e-12, "2. node(" + std::to_string(i) + ","
                               + std::to_string(j) + ").y is the uniform j fraction");
                }
            }
        }
    }

    // ── 3. the split is alternating by index parity, by default ────────────
    {
        MbResult r = build(square(4, 3));
        CHECK(r.ok, "3. setup");
        CHECK(r.cells.size() == 2u * 3u * 2u,
              "3. every quad becomes two triangles by default");
        bool allTris = true;
        bool blockTagged = true;
        for (const auto& c : r.cells) {
            if (c.nodeIds.size() != 3) allTris = false;
            if (c.block != 0) blockTagged = false;
        }
        CHECK(allTris, "3. ...and every cell is a triangle");
        CHECK(blockTagged, "3. ...each carrying the index of the block it came from");

        if (r.ok && r.blocks.size() == 1 && r.cells.size() >= 4) {
            const auto& b = r.blocks[0];
            // Cell (0,0) has even (i+j) and splits on the sw-ne diagonal; cell
            // (1,0) is odd and splits on the se-nw one. The two rules being
            // DIFFERENT is the whole content of "alternating": a single fixed
            // diagonal would pass every count-based check above.
            const int n00 = b.nodeAt(0, 0), n10 = b.nodeAt(1, 0);
            const int n11 = b.nodeAt(1, 1), n01 = b.nodeAt(0, 1);
            CHECK(r.cells[0].nodeIds == std::vector<int>({n00, n10, n11}) &&
                  r.cells[1].nodeIds == std::vector<int>({n00, n11, n01}),
                  "3. cell (0,0) — even (i+j) — splits on the (0,0)-(1,1) diagonal");
            const int m00 = b.nodeAt(1, 0), m10 = b.nodeAt(2, 0);
            const int m11 = b.nodeAt(2, 1), m01 = b.nodeAt(1, 1);
            CHECK(r.cells[2].nodeIds == std::vector<int>({m00, m10, m01}) &&
                  r.cells[3].nodeIds == std::vector<int>({m10, m11, m01}),
                  "3. cell (1,0) — odd (i+j) — splits on the OTHER diagonal");
        }
    }

    // ── 4. every produced triangle is wound counter-clockwise ──────────────
    {
        MbResult r = build(square(5, 4));
        int inverted = 0;
        for (const auto& c : r.cells) {
            const auto& a = r.nodes[static_cast<size_t>(c.nodeIds[0])];
            const auto& b = r.nodes[static_cast<size_t>(c.nodeIds[1])];
            const auto& d = r.nodes[static_cast<size_t>(c.nodeIds[2])];
            if ((b - a).cross(d - a) <= 0.0) ++inverted;
        }
        CHECK(inverted == 0, "4. no cell is inverted ("
              + std::to_string(inverted) + " of " + std::to_string(r.cells.size()) + " are)");
    }

    // ── 5. the split is switchable off ─────────────────────────────────────
    {
        MbParams p; p.splitQuads = false;
        MbResult r = build(square(4, 3), p);
        CHECK(r.ok, "5. setup");
        CHECK(r.cells.size() == 3u * 2u, "5. splitting off leaves one cell per quad");
        bool allQuads = true;
        for (const auto& c : r.cells) if (c.nodeIds.size() != 4) allQuads = false;
        CHECK(allQuads, "5. ...and every cell has four nodes");
        bool said = false;
        for (const auto& w : r.warnings) if (mentions(w, "quad")) said = true;
        CHECK(said, "5. ...and it is said out loud, since the solver cannot use quads");
    }

    // ── 6. boundary edges come back already resolved ───────────────────────
    {
        MbResult r = build(square(4, 3));
        CHECK(r.boundaryEdges.size() == 2u * (3u + 2u),
              "6. one boundary edge per perimeter cell side");
        bool named = true;
        bool unbound = true;
        for (const auto& be : r.boundaryEdges) {
            if (be.bc != "wall") named = false;
            if (be.geomId != -1 || be.segId != -1) unbound = false;
        }
        CHECK(named, "6. ...each carrying the resolved BC name, not a position to classify");
        CHECK(unbound, "6. ...and no source segment, because this document declares "
                       "no binding");
        bool told = false;
        for (const auto& w : r.warnings)
            if (mentions(w, "config default BC")) told = true;
        CHECK(told, "6. ...which the caller is told, rather than left to discover");
        // ONE closed walk: every edge starts where the previous one ended, and the
        // last returns to the first. A per-side emitter that got a direction wrong
        // still produces the right SET of edges, so only the chaining catches it.
        bool chained = !r.boundaryEdges.empty();
        for (size_t k = 1; k < r.boundaryEdges.size(); ++k)
            if (r.boundaryEdges[k].v1 != r.boundaryEdges[k - 1].v2) chained = false;
        CHECK(chained && r.boundaryEdges.back().v2 == r.boundaryEdges.front().v1,
              "6. ...and the perimeter is one closed walk, in one direction");
    }

    // ── 7. a per-edge spacing law reaches the nodes ────────────────────────
    // The decision layer shares the existing spacing header rather than
    // carrying a second growth-rate solver; this is what proves the sharing is
    // wired up and not merely on the include path.
    {
        MbResult r = build(square(5, 3, R"(, "spacing": {"law": "geometric", "growth": 2.0})"));
        CHECK(r.ok, "7. a geometric spacing law is accepted (err: " + r.error + ")");
        if (r.ok && r.blocks.size() == 1) {
            const auto& b = r.blocks[0];
            const double x1 = r.nodes[static_cast<size_t>(b.nodeAt(1, 0))].x;
            const double x2 = r.nodes[static_cast<size_t>(b.nodeAt(2, 0))].x;
            const double x3 = r.nodes[static_cast<size_t>(b.nodeAt(3, 0))].x;
            CHECK((x2 - x1) > (x1 - 0.0) && (x3 - x2) > (x2 - x1),
                  "7. ...and the spacing along that edge really grows");
            CHECK_NEAR(r.nodes[static_cast<size_t>(b.nodeAt(4, 0))].x, 1.0, 1e-12,
                       "7. ...while the far corner stays exactly where it was declared");
        }
        refuses(square(5, 3, R"(, "spacing": {"law": "parabolic"})"), "parabolic",
                "7. an unknown spacing law");
        refuses(square(5, 3, R"(, "spacing": {"law": "geometric"})"), "growth",
                "7. a geometric law with no growth rate");
    }

    // ── 8. a clockwise block is REFUSED, not silently re-wound ─────────────
    {
        // The same square, but its corner ring declared sw -> nw -> ne -> se,
        // i.e. clockwise. The geometry is identical; only the declaration's
        // handedness differs, and that alone makes every cell inverted.
        //
        // Refused with the topology error rather than exported: this is a bad
        // block ORIENTATION, readable from the declaration before a node exists,
        // and the fix is in the document. The inverted-cell outcome that exports
        // anyway is for a valid declaration whose geometry came out folded, which
        // is worth looking at; a backwards-wound ring is not.
        const std::string cw = R"({
  "format_version": 1,
  "corners": [
    {"id": "sw", "kind": "free", "xy": [0.0, 0.0]},
    {"id": "se", "kind": "free", "xy": [1.0, 0.0]},
    {"id": "ne", "kind": "free", "xy": [1.0, 1.0]},
    {"id": "nw", "kind": "free", "xy": [0.0, 1.0]}
  ],
  "edges": [
    {"id": "s", "corners": ["sw", "nw"], "kind": "wall", "count": 3},
    {"id": "e", "corners": ["nw", "ne"], "kind": "wall", "count": 4},
    {"id": "n", "corners": ["se", "ne"], "kind": "wall", "count": 3},
    {"id": "w", "corners": ["sw", "se"], "kind": "wall", "count": 4}
  ],
  "blocks": [
    {"id": "b0", "edges": ["s", "e", "n", "w"]}
  ]
})";
        refuses(cw, "clockwise", "8. a clockwise block");
        // The mirror: the SAME four corners wound the other way are accepted, so
        // the check above cannot be passing because the document is malformed in
        // some other way.
        MbResult ok = build(square(3, 4));
        CHECK(ok.ok, "8. ...while a counter-clockwise ring of the same square is "
                     "accepted (err: " + ok.error + ")");
    }

    // ── 9. a malformed document is refused, naming what is wrong ───────────
    refuses("{\"format_version\": 1,,}", "JSON", "9. invalid JSON");
    refuses("[1, 2, 3]", "object", "9. a document that is not an object");
    refuses(R"({"corners": [], "edges": [], "blocks": []})", "format_version",
            "9. a document with no format_version");
    {
        refuses(swap1(square(4, 3), "\"format_version\": 1", "\"format_version\": 99"),
                "99", "9. a format_version this build cannot read");
    }
    {
        refuses(swap1(square(4, 3), "\"count\": 4", "\"cout\": 4"),
                "cout", "9. a typo'd key (unknown keys are refused, not skipped)");
    }
    refuses(square(1, 3), "at least 2", "9. an edge with fewer than two nodes");
    {
        MbResult r = build(swap1(square(4, 3),
            R"("id": "n", "corners": ["nw", "ne"], "kind": "wall", "count": 4)",
            R"("id": "n", "corners": ["nw", "ne"], "kind": "wall", "count": 7)"));
        CHECK(!r.ok, "9. opposite sides with different counts are refused");
        CHECK(mentions(r.error, "'s'") && mentions(r.error, "'n'")
              && mentions(r.error, "4") && mentions(r.error, "7"),
              "9. ...naming BOTH edges and BOTH counts (got: " + r.error + ")");
    }
    {
        refuses(swap1(square(4, 3), R"(["sw", "se"])", R"(["sw", "zz"])"),
                "zz", "9. an edge naming a corner that does not exist");
    }
    {
        refuses(swap1(square(4, 3), R"(["s", "e", "n", "w"])", R"(["s", "e", "n", "q"])"),
                "q", "9. a block naming an edge that does not exist");
    }
    {
        // INVERTED by #53, deliberately: this used to be a refusal ("a block side
        // declared in the wrong direction"), and the single-block release named the
        // edge and the convention. It cannot stay one. A shared edge is ONE edge
        // with ONE declared direction, named by two blocks whose logical frames need
        // not agree about which way it runs, so requiring the convention's direction
        // in every block makes a whole class of topology undeclarable. The block's i
        // direction is still fixed by its SOUTH edge alone; the other three sides are
        // traversed as the ring requires, and a set of four that does not CLOSE a
        // ring is still refused by name (check 22).
        MbResult r = build(swap1(square(4, 3), R"("id": "w", "corners": ["sw", "nw"])",
                                               R"("id": "w", "corners": ["nw", "sw"])"));
        CHECK(r.ok, "9. a block side declared against the convention is accepted and "
                    "reversed (err: " + r.error + ")");
        if (r.ok && r.blocks.size() == 1) {
            // ...and REVERSED rather than merely tolerated: the block's (0, 0) is
            // still the corner its south and west edges share, so accepting the
            // backwards declaration must not mirror the block.
            const auto& b = r.blocks[0];
            const auto& p00 = r.nodes[static_cast<size_t>(b.nodeAt(0, 0))];
            const auto& pnj = r.nodes[static_cast<size_t>(b.nodeAt(0, b.nj - 1))];
            CHECK(p00.x == 0.0 && p00.y == 0.0 && pnj.x == 0.0 && pnj.y == 1.0,
                  "9. ...with j still running from 'sw' to 'nw', not mirrored");
        }
    }

    // ── 10. what this release does not do yet is refused BY NAME ───────────
    // Not silently approximated: a corner placed near a geometry feature rather
    // than on it, or a BC guessed instead of declared, is a slightly wrong mesh
    // with no error — which is worse than no mesh.
    //
    // Two entries of this list were REMOVED by #53 and are now covered by checks
    // 17-23 instead: a cut edge, and a topology with more than one block. What
    // stays is the one refusal that is not a "not yet" at all.
    refuses(square(4, 3, "", R"(, "orientation": [0, 1, 2, 3])"), "orientation",
            "10. a block orientation declared twice over");

    // ── 11. a declaration that reaches nothing is a typo, not a preference ──
    {
        const std::string last = R"({"id": "w", "corners": ["sw", "nw"], "kind": "wall", "count": 3})";
        refuses(swap1(square(4, 3), last,
                      last + R"(, {"id": "orphan", "corners": ["sw", "ne"], "kind": "wall", "count": 3})"),
                "orphan", "11. an edge that belongs to no block");
    }
    {
        const std::string last = R"({"id": "nw", "kind": "free", "xy": [0.0, 1.0]})";
        refuses(swap1(square(4, 3), last,
                      last + R"(, {"id": "stray", "kind": "free", "xy": [9.0, 9.0]})"),
                "stray", "11. a corner that is on no edge");
    }

    // ══ Geometry binding (issue #52) ══════════════════════════════════════
    //
    // The claim under test is that a boundary condition is DECLARED and never
    // discovered: it is read out of the topology and the geometry's sidecar
    // before a single node exists, so there is no tolerance in the chain for a
    // curved wall to drift past.

    // ── 12. a corner attaches by ARC LENGTH and lands there ────────────────
    {
        const auto g = squareGeom(4);
        const std::vector<hybmesh::MbGeometry> gs{g};
        MbResult r = hybmesh::buildMultiBlock(
            boundSquare(att("sw", 0.0), att("se", 1.0)), gs, MbParams{});
        CHECK(r.ok, "12. a topology attached to a geometry is accepted (err: " + r.error + ")");
        if (r.ok && r.blocks.size() == 1) {
            const auto& b = r.blocks.front();
            const Point2D p0 = r.nodes[static_cast<size_t>(b.nodeAt(0, 0))];
            const Point2D p1 = r.nodes[static_cast<size_t>(b.nodeAt(b.ni - 1, 0))];
            CHECK_NEAR(p0.x, 0.0, 1e-12, "12. t = 0 lands on the segment's first point");
            CHECK_NEAR(p0.y, 0.0, 1e-12, "12. ...in y too");
            // t = 1 is where the NEXT segment begins, not one resampling interval
            // short of it. That is the whole reason `segmentRun` extends the run:
            // a sidecar gives the shared joint to the later segment, so a segment's
            // own last point is 0.75 here and stopping there would put the corner
            // at a place that MOVES when the geometry is resampled.
            CHECK_NEAR(p1.x, 1.0, 1e-12,
                       "12. t = 1 lands where the segment ENDS, not on its own last point");
            CHECK_NEAR(p1.y, 0.0, 1e-12, "12. ...in y too");
        }
        MbResult mid = hybmesh::buildMultiBlock(
            boundSquare(att("sw", 0.25), att("se", 0.75)), gs, MbParams{});
        CHECK(mid.ok, "12. a corner part-way along a segment is accepted (err: " + mid.error + ")");
        if (mid.ok && mid.blocks.size() == 1) {
            const auto& b = mid.blocks.front();
            CHECK_NEAR(mid.nodes[static_cast<size_t>(b.nodeAt(0, 0))].x, 0.25, 1e-12,
                       "12. ...at the arc-length position it declares");
            CHECK_NEAR(mid.nodes[static_cast<size_t>(b.nodeAt(b.ni - 1, 0))].x, 0.75, 1e-12,
                       "12. ...at both ends");
        }
        // t = 1 of one segment and t = 0 of the next are the SAME physical point,
        // EXACTLY — not to within a tolerance. That is what the run extension buys,
        // and it is what will let two blocks meeting at a geometry feature agree
        // without one. Asked at the SEAM of the closed loop (segment 4's end is the
        // origin, which the loader dropped as a duplicate), because that is the
        // joint the wrap-around handling is about and the one a fixture is most
        // likely to get wrong.
        const std::string freeSe = R"({"id": "se", "kind": "free", "xy": [1.0, 0.0]})";
        MbResult viaFirst = hybmesh::buildMultiBlock(
            boundSquare(att("sw", 0.0, 1), freeSe, ""), gs, MbParams{});
        MbResult viaLast = hybmesh::buildMultiBlock(
            boundSquare(att("sw", 1.0, 4), freeSe, ""), gs, MbParams{});
        CHECK(viaFirst.ok && viaLast.ok,
              "12. the seam is reachable from either segment that meets there (err: "
              + viaFirst.error + viaLast.error + ")");
        if (viaFirst.ok && viaLast.ok) {
            const Point2D a = viaFirst.nodes[static_cast<size_t>(
                viaFirst.blocks.front().nodeAt(0, 0))];
            const Point2D c = viaLast.nodes[static_cast<size_t>(
                viaLast.blocks.front().nodeAt(0, 0))];
            CHECK(a.x == c.x && a.y == c.y && a.x == 0.0 && a.y == 0.0,
                  "12. ...and is the same point, so a joint needs no tolerance");
        }
        // So an edge bound to segment 1 accepts a corner declared as segment 2's
        // t = 0: that is the joint the two share, named from the other side. It is
        // the same POINT by the sidecar's own indexing, not by comparing two
        // coordinates — and it has to be accepted, because on a closed body every
        // block corner is a joint whose two edges bind to different segments.
        MbResult fromNext = hybmesh::buildMultiBlock(
            boundSquare(att("sw", 0.5), att("se", 0.0, 2)), gs, MbParams{});
        CHECK(fromNext.ok, "12. a bound edge accepts a corner naming its far joint from "
                           "the NEXT segment (err: " + fromNext.error + ")");
        if (fromNext.ok)
            CHECK_NEAR(fromNext.nodes[static_cast<size_t>(
                           fromNext.blocks.front().nodeAt(
                               fromNext.blocks.front().ni - 1, 0))].x, 1.0, 1e-12,
                       "12. ...landing on that joint, i.e. segment 1's own t = 1");
        // A position strictly INSIDE another segment is still refused: it is not a
        // point segment 1 owns, so "this edge lies on segment 1" would be false.
        refuses(boundSquare(att("sw", 0.5), att("se", 0.3, 2)),
                "has to start and end on it",
                "12. ...but not one strictly inside the neighbour", gs);
    }

    // ── 13. re-resampling does not move an attached corner ─────────────────
    // The ticket's central rule, and the reason attachment is an arc length
    // rather than a point index: the workflow is edit CAD, re-resample, re-mesh.
    {
        const std::string doc = boundSquare(att("sw", 0.3), att("se", 0.9));
        MbResult coarse = hybmesh::buildMultiBlock(doc, {squareGeom(4)}, MbParams{});
        MbResult fine   = hybmesh::buildMultiBlock(doc, {squareGeom(13)}, MbParams{});
        CHECK(coarse.ok && fine.ok,
              "13. one topology meshes against two resamplings of one geometry");
        if (coarse.ok && fine.ok) {
            const Point2D a = coarse.nodes[static_cast<size_t>(
                coarse.blocks.front().nodeAt(0, 0))];
            const Point2D b = fine.nodes[static_cast<size_t>(
                fine.blocks.front().nodeAt(0, 0))];
            CHECK_NEAR(a.x, b.x, 1e-12,
                       "13. the attached corner is in the same physical place");
            CHECK_NEAR(a.y, b.y, 1e-12, "13. ...in y too");
            CHECK_NEAR(a.x, 0.3, 1e-12, "13. ...which is the place it declared");
            // NEGATIVE CONTROL. Without it this check would pass just as well on an
            // implementation that never resamples anything, so it says nothing about
            // arc length until the alternative is shown to differ: the point INDEX
            // nearest t = 0.3 is a different physical place in the two samplings, by
            // ~10 orders of magnitude more than the residue above.
            const auto g4 = squareGeom(4), g13 = squareGeom(13);
            const double byIndex4 = g4.points[static_cast<size_t>(0.3 * 4)].x;
            const double byIndex13 = g13.points[static_cast<size_t>(0.3 * 13)].x;
            CHECK(std::fabs(byIndex4 - byIndex13) > 1e-3,
                  "13. (negative control) an INDEX binding really would have moved it ("
                  + std::to_string(byIndex4) + " vs " + std::to_string(byIndex13) + ")");
        }
    }

    // ── 14. a bound edge carries its segment's condition, already resolved ──
    {
        const auto g = squareGeom(4);
        MbResult r = hybmesh::buildMultiBlock(
            boundSquare(att("sw", 0.0), att("se", 1.0)), {g}, MbParams{});
        CHECK(r.ok, "14. setup (err: " + r.error + ")");
        size_t onSeg = 0, onDefault = 0;
        bool keyed = true, defaultUnkeyed = true;
        for (const auto& be : r.boundaryEdges) {
            if (be.bc == "bottom") {
                ++onSeg;
                if (be.geomId != 0 || be.segId != 1) keyed = false;
            } else {
                ++onDefault;
                if (be.geomId != -1 || be.segId != -1) defaultUnkeyed = false;
            }
        }
        // The south side of a 5 x 3 block is four edges; the other three sides are
        // the rest of the perimeter and declare no binding.
        CHECK(onSeg == 4, "14. every edge along the bound side carries that segment's "
                          "own BC label (" + std::to_string(onSeg) + ")");
        CHECK(keyed, "14. ...together with its (geometry, segment) key, so the exporter "
                     "groups it as one patch");
        // The perimeter of a 5 x 3 block is 2 * ((5 - 1) + (3 - 1)) = 12 edges.
        CHECK(onDefault == 12u - 4u,
              "14. ...while a side with no binding keeps the config default ("
              + std::to_string(onDefault) + ")");
        CHECK(defaultUnkeyed, "14. ...and carries no source segment, rather than a "
                              "borrowed one");
        // A segment with no label in the sidecar falls back — and SAYS so, because
        // the user named a segment precisely so the condition would follow from it.
        auto blank = g;
        blank.segBc[1] = "";
        MbResult nb = hybmesh::buildMultiBlock(
            boundSquare(att("sw", 0.0), att("se", 1.0)), {blank}, MbParams{});
        bool told = false;
        for (const auto& w : nb.warnings)
            if (mentions(w, "no boundary condition label")) told = true;
        CHECK(nb.ok && told,
              "14. a bound segment with no label falls back to the default and says so");
    }

    // ── 15. a bound edge FOLLOWS the geometry, it does not cut the chord ────
    // The difference between an edge that lies on a segment and one that merely
    // says so. On a curved wall a chord sits a sagitta off the body everywhere
    // between its ends, and that drift is exactly what made a curved inlet export
    // a band of wall on the other path.
    {
        hybmesh::MbGeometry g;
        g.file = "chevron.dat";
        g.points = {{0.0, 0.0}, {0.5, 0.5}, {1.0, 0.0}, {1.0, -1.0}};
        g.segId  = {1, 1, 2, 2};
        g.segBc  = {{1, "body"}, {2, "outlet"}};
        MbResult r = hybmesh::buildMultiBlock(
            swap1(swap1(boundSquare(att("sw", 0.0, 1, "chevron.dat"),
                                    att("se", 1.0, 1, "chevron.dat")),
                        R"("geom": "square.dat", "seg": 1)", R"("geom": "chevron.dat", "seg": 1)"),
                  R"("xy": [1.0, 0.5])", R"("xy": [1.0, 1.5])"),
            {g}, MbParams{});
        CHECK(r.ok, "15. an edge bound to a bent segment is accepted (err: " + r.error + ")");
        if (r.ok && r.blocks.size() == 1) {
            const auto& b = r.blocks.front();
            // The apex is the midpoint of the segment's arc length, and the south
            // edge has 5 nodes, so node 2 sits on it. A chord would put that node
            // at y = 0.
            const Point2D apex = r.nodes[static_cast<size_t>(b.nodeAt(2, 0))];
            CHECK_NEAR(apex.x, 0.5, 1e-12, "15. the middle node walks the polyline");
            CHECK_NEAR(apex.y, 0.5, 1e-12,
                       "15. ...to the bend itself, not to the chord across it");
        }
    }

    // ── 16. what cannot be resolved is refused BY NAME ─────────────────────
    // Never approximated, and never resolved by position in a list: a corner
    // placed NEAR a feature instead of on it is a slightly wrong mesh with no
    // error, which is worse than no mesh at all.
    {
        const std::vector<hybmesh::MbGeometry> gs{squareGeom(4)};
        const std::string ok0 = att("sw", 0.0), ok1 = att("se", 1.0);

        refuses(boundSquare(att("sw", 0.0, 1, "elsewhere.dat"), ok1), "elsewhere.dat",
                "16. a corner on a geometry this run never loaded", gs);
        refuses(boundSquare(att("sw", 0.0, 9), ok1), "segment 9",
                "16. a corner on a segment the geometry does not have", gs);
        refuses(boundSquare(ok0, ok1), "loaded no geometry",
                "16. an attachment when nothing was loaded at all");
        refuses(swap1(boundSquare(ok0, ok1), R"("t": 0.000000)", R"("t": 1.500000)"),
                "between 0 and 1", "16. an arc-length position off the segment", gs);
        refuses(swap1(boundSquare(ok0, ok1), R"("kind": "on_geometry", "geom")",
                      R"("kind": "on_geometry", "xy": [0.0, 0.0], "geom")"),
                "must not also declare", "16. a corner declaring its position twice", gs);
        refuses(swap1(boundSquare(ok0, ok1),
                      R"({"id": "ne", "kind": "free", "xy": [1.0, 0.5]})",
                      R"({"id": "ne", "kind": "free", "xy": [1.0, 0.5], "seg": 2})"),
                "only an 'on_geometry' corner reads",
                "16. a free corner wearing an attachment key", gs);
        // A bound edge whose corner is a free coordinate: there is no stretch of
        // geometry for it to follow, so "it lies on that segment" is unverifiable.
        refuses(boundSquare(R"({"id": "sw", "kind": "free", "xy": [0.0, 0.0]})", ok1),
                "has to start and end on it",
                "16. an edge bound to a segment its corner is not on", gs);
        refuses(boundSquare(att("sw", 0.4), att("se", 0.4)), "no length",
                "16. an edge whose two corners attach at the same position", gs);
        // A trivial piece break at index 0 is not a second piece. Sidecars in this
        // repo disagree about whether to record it (a resampled square writes
        // NPIECES 0; examples/geometries/square_cavity.dat.meta writes a break at
        // 0), and reading it as multi-piece switches off the closed-loop wrap —
        // putting the last segment's t = 1 one resampling interval short of the
        // seam, silently.
        {
            auto trivial = squareGeom(4);
            trivial.pieceBreaks = {0};
            MbResult r = hybmesh::buildMultiBlock(
                boundSquare(att("sw", 1.0, 4),
                            R"({"id": "se", "kind": "free", "xy": [1.0, 0.0]})", ""),
                {trivial}, MbParams{});
            CHECK(r.ok, "16. a break at index 0 is not a second piece (err: "
                        + r.error + ")");
            if (r.ok) {
                const Point2D p = r.nodes[static_cast<size_t>(
                    r.blocks.front().nodeAt(0, 0))];
                CHECK(p.x == 0.0 && p.y == 0.0,
                      "16. ...so the last segment still reaches the seam");
            }
        }
        // A REAL second piece does stop the wrap, because there is no next point
        // to reach for across a gap between two disjoint pieces.
        {
            auto split = squareGeom(4);
            split.pieceBreaks = {8};
            MbResult r = hybmesh::buildMultiBlock(
                boundSquare(att("sw", 1.0, 4),
                            R"({"id": "se", "kind": "free", "xy": [1.0, 0.0]})", ""),
                {split}, MbParams{});
            CHECK(r.ok && r.nodes[static_cast<size_t>(
                      r.blocks.front().nodeAt(0, 0))].y != 0.0,
                  "16. ...while a real second piece stops the segment at its own end");
        }
        // t = 1 means "where this segment ENDS", which is the next segment's first
        // point only when there IS a next one. On the last segment of an open
        // polyline it is that segment's own final point — and that is stable under
        // resampling for a different reason: the resampler pins every segment's
        // endpoints, so a segment's last sample is a declared endpoint and not a
        // floating sample. Measured 2026-08-28 through the real binary: an open
        // two-segment polyline resampled at 6 and 11 points per segment ends at
        // (1.0, 1.0) both times.
        {
            hybmesh::MbGeometry open;
            open.file = "open.dat";
            open.points = {{0.0, 1.0}, {0.5, 1.0}, {1.0, 1.0}, {0.5, 0.5}, {0.0, 0.0}};
            open.segId  = {1, 1, 2, 2, 2};
            open.segBc  = {{1, "in"}, {2, "out"}};
            MbResult r = hybmesh::buildMultiBlock(
                boundSquare(att("sw", 1.0, 2, "open.dat"),
                            R"({"id": "se", "kind": "free", "xy": [1.0, 0.0]})", ""),
                {open}, MbParams{});
            CHECK(r.ok, "16. the last segment of an OPEN polyline is attachable (err: "
                        + r.error + ")");
            if (r.ok) {
                const Point2D p = r.nodes[static_cast<size_t>(
                    r.blocks.front().nodeAt(0, 0))];
                CHECK(p.x == 0.0 && p.y == 0.0,
                      "16. ...and its t = 1 is its own final point, there being no "
                      "next segment to reach for");
            }
        }
        // A geometry that would not load is a warning while nothing refers to it,
        // and an error the moment something does.
        {
            hybmesh::MbGeometry gone;
            gone.file = "square.dat";
            refuses(boundSquare(ok0, ok1), "carries no points",
                    "16. an attachment to a geometry that would not load", {gone});
        }
        {
            hybmesh::MbGeometry bare = squareGeom(4);
            bare.segId.clear();
            refuses(boundSquare(ok0, ok1), ".meta",
                    "16. an attachment to a geometry with no sidecar", {bare});
        }
        // Two geometries sharing a basename make the short form ambiguous. Refused
        // rather than resolved by order, because position in the list is exactly
        // the binding this feature exists not to have.
        {
            auto a = squareGeom(4, "left/square.dat");
            auto b = squareGeom(4, "right/square.dat");
            refuses(boundSquare(ok0, ok1), "ambiguous",
                    "16. a geometry named by an ambiguous basename", {a, b});
        }
        // ...while a UNIQUE basename resolves, so a topology need not repeat the
        // config's whole path.
        {
            MbResult r = hybmesh::buildMultiBlock(boundSquare(ok0, ok1),
                                                  {squareGeom(4, "geom/square.dat")}, MbParams{});
            CHECK(r.ok, "16. ...while a unique basename resolves (err: " + r.error + ")");
        }
    }


    // ══ Multi-block welding (issue #53) ═══════════════════════════════════
    //
    // Three claims are under test here, and they are one mechanism seen from
    // three sides. Point counts PROPAGATE, so the user seeds a few edges and the
    // rest are forced. Blocks are welded TOPOLOGICALLY, so the k-th node on one
    // side of a shared edge IS the k-th node on the other and no distance is
    // compared anywhere. And an edge's KIND is declared, never inferred from
    // whether a binding is present.

    // ── 17. two blocks come back as ONE welded mesh ────────────────────────
    {
        MbResult r = build(twoBlocks());
        CHECK(r.ok, "17. a two-block topology is accepted (err: " + r.error + ")");
        CHECK(r.blocks.size() == 2, "17. both blocks come back");
        if (r.ok && r.blocks.size() == 2) {
            const auto& b0 = r.blocks[0];
            const auto& b1 = r.blocks[1];
            CHECK(b0.ni == 3 && b0.nj == 3 && b1.ni == 4 && b1.nj == 3,
                  "17. each block is filled at its own resolved logical size ("
                  + std::to_string(b0.ni) + "x" + std::to_string(b0.nj) + ", "
                  + std::to_string(b1.ni) + "x" + std::to_string(b1.nj) + ")");
            // THE WELD, as node IDENTITY. Not "the two sides are close": the same
            // integer, which is the only claim that holds at a wall spacing of
            // 1e-7 beside a far-field spacing of 1e-1.
            bool shared = true;
            for (int j = 0; j < b0.nj; ++j)
                if (b0.nodeAt(b0.ni - 1, j) != b1.nodeAt(0, j)) shared = false;
            CHECK(shared, "17. the k-th node of the shared edge IS the k-th node both "
                          "blocks see — the same id, not a coordinate match");
            // ...and the saving is real: two unwelded blocks would need 3*3 + 4*3.
            CHECK(r.nodes.size() == 18,
                  "17. ...so the mesh holds 18 nodes and not the 21 two separate "
                  "blocks would need (" + std::to_string(r.nodes.size()) + ")");
            CHECK(coincidentPairs(r.nodes) == 0,
                  "17. ...and no two nodes sit at the same place, so it is ONE mesh "
                  "rather than two meshes touching");
            CHECK(r.cells.size() == 2u * (2u * 2u + 3u * 2u),
                  "17. every quad of both blocks is split ("
                  + std::to_string(r.cells.size()) + ")");
            CHECK(invertedCells(r) == 0, "17. ...and no cell is inverted");
            // The interface is an INTERIOR line: both blocks have cells against it,
            // so emitting it as a boundary face would hand the exporter a face with
            // two owners and the solver a wall through the middle of the fluid.
            CHECK(r.boundaryEdges.size() == 14,
                  "17. only the six WALL sides reach the boundary, not the shared "
                  "interface (" + std::to_string(r.boundaryEdges.size()) + ")");
            CHECK(r.sharedEdges.size() == 1
                  && r.sharedEdges[0].edgeId == "m"
                  && r.sharedEdges[0].kind == hybmesh::MB_EDGE_INTERFACE
                  && r.sharedEdges[0].nodes == 3,
                  "17. ...and the interface is reported as data, with the two block "
                  "sides it welds");
            if (r.sharedEdges.size() == 1) {
                const auto& se = r.sharedEdges[0];
                CHECK((se.blockA == 0 && se.sideA == hybmesh::MB_EAST
                       && se.blockB == 1 && se.sideB == hybmesh::MB_WEST),
                      "17. ...naming which side of which block, in declaration order");
            }
        }
    }

    // ── 18. a seeded count propagates; a spacing LAW does not ──────────────
    {
        MbResult r = build(twoBlocks());
        CHECK(r.ok, "18. setup (err: " + r.error + ")");
        // Three of the seven edges declare a count. Everything else is forced:
        // 's0' fixes b0's i and so 'n0'; 'w' fixes b0's j and so 'm', which is b1's
        // j and so 'ee'; 's1' fixes b1's i and so 'n1'.
        CHECK(countOf(r, "s0") == 3 && countOf(r, "n0") == 3
              && countOf(r, "w") == 3 && countOf(r, "m") == 3 && countOf(r, "ee") == 3
              && countOf(r, "s1") == 4 && countOf(r, "n1") == 4,
              "18. every edge's count is resolved, three seeded and four propagated");
        CHECK(seededSet(r) == std::vector<std::string>({"s0", "s1", "w"}),
              "18. ...and which of the two each one was is reported, so a propagation "
              "defect cannot read as a design choice");
        // The COUNT propagates and the SPACING LAW does not. They are different
        // facts: a wall edge legitimately clusters toward the wall while the
        // interface in its own count class stays uniform, and forcing the law
        // across a class would silently redistribute an edge nobody edited.
        MbResult g = build(twoBlocks("interface", "",
                                     R"(, "spacing": {"law": "geometric", "growth": 3.0})"));
        CHECK(g.ok, "18. a graded seed edge is accepted (err: " + g.error + ")");
        if (g.ok && g.blocks.size() == 2) {
            const auto& b0 = g.blocks[0];
            const double wy = g.nodes[static_cast<size_t>(b0.nodeAt(0, 1))].y;
            const double my = g.nodes[static_cast<size_t>(b0.nodeAt(b0.ni - 1, 1))].y;
            CHECK(wy < 0.3, "18. ...the graded edge 'w' clusters toward its start ("
                            + std::to_string(wy) + ")");
            CHECK_NEAR(my, 0.5, 1e-12,
                       "18. ...while 'm', which took its COUNT from 'w', keeps its own "
                       "uniform law");
        }
    }

    // ── 19. two conflicting seeds name both edges, both counts and the CHAIN ─
    // A bare "counts disagree" is not enough on a topology with dozens of edges:
    // what the user has to be told is which two declarations are in conflict and
    // by what route, since the two need not be anywhere near each other.
    {
        // The conflicting seed is deliberately TWO blocks away from the one it
        // clashes with: 'w' is b0's west, 'ee' is b1's east, and the two are in one
        // class only through the shared edge 'm'. A one-block conflict would let a
        // report that names no chain at all pass this check.
        MbResult r = build(twoBlocks("interface", "", "", R"(, "count": 9)"));
        CHECK(!r.ok, "19. two conflicting seeds in one class are refused");
        CHECK(mentions(r.error, "'w'") && mentions(r.error, "'ee'")
              && mentions(r.error, "3") && mentions(r.error, "9"),
              "19. ...naming BOTH edges and BOTH counts (got: " + r.error + ")");
        CHECK(mentions(r.error, "'b0'") && mentions(r.error, "'b1'")
              && mentions(r.error, "'m'") && mentions(r.error, "west / east"),
              "19. ...and the chain that propagated between them, block by block, "
              "naming the edge in between (got: " + r.error + ")");
        CHECK(r.nodes.empty() && r.blocks.empty(),
              "19. ...and producing nothing");
    }

    // ── 20. a class with NO seed is refused naming every edge in it ─────────
    // Refusing beats picking a default: a silently-chosen count decides the whole
    // mesh density, and the user cannot see a number nobody wrote down.
    {
        MbResult r = build(swap1(twoBlocks(),
                                 R"("id": "w", "corners": ["a", "d"], "kind": "wall", "count": 3)",
                                 R"("id": "w", "corners": ["a", "d"], "kind": "wall")"));
        CHECK(!r.ok, "20. an equivalence class with no seed is refused");
        CHECK(mentions(r.error, "'w'") && mentions(r.error, "'m'")
              && mentions(r.error, "'ee'"),
              "20. ...naming every edge it could not resolve (got: " + r.error + ")");
        CHECK(mentions(r.error, "count"),
              "20. ...and what to add to fix it");
    }

    // ── 21. the three edge kinds are honoured distinctly ───────────────────
    {
        // A wall is the OUTSIDE of the mesh, so two blocks cannot share one.
        MbResult r = build(twoBlocks("wall"));
        CHECK(!r.ok, "21. a 'wall' named by two blocks is refused");
        CHECK(mentions(r.error, "'m'") && mentions(r.error, "'b0'")
              && mentions(r.error, "'b1'"),
              "21. ...naming the edge and both blocks that claim it (got: "
              + r.error + ")");
    }
    {
        // ...and the converse: an interface is an INTERIOR boundary, so one block
        // alone cannot have one. Inferring "only one block has it, so it must be a
        // wall" is exactly the inference this enum exists to refuse.
        refuses(swap1(square(4, 3), R"("id": "e", "corners": ["se", "ne"], "kind": "wall")",
                                    R"("id": "e", "corners": ["se", "ne"], "kind": "interface")"),
                "'e'", "21. an 'interface' named by only one block");
    }
    {
        // A cut welds by the same rule an interface does — there is nothing left
        // for a second rule to do once node identity is shared — so what has to
        // hold is that the DECLARATION survives: the mesh is identical and the
        // report says "cut". A kind that vanished on the way through would leave
        // the enum a comment.
        MbResult i = build(twoBlocks("interface"));
        MbResult c = build(twoBlocks("cut"));
        CHECK(c.ok, "21. a 'cut' shared by two blocks is accepted (err: " + c.error + ")");
        CHECK(c.sharedEdges.size() == 1
              && c.sharedEdges[0].kind == hybmesh::MB_EDGE_CUT,
              "21. ...and comes back reported as a CUT, not as an ordinary interface");
        CHECK(i.ok && c.nodes.size() == i.nodes.size()
              && c.cells.size() == i.cells.size()
              && c.boundaryEdges.size() == i.boundaryEdges.size(),
              "21. ...welding the same way an interface does, which is what the two "
              "kinds share and all they share");
    }
    {
        // A binding says "this edge LIES ON that source segment", which is a
        // statement about a wall. An interior line in the fluid has no segment to
        // lie on, and accepting one would make the kind and the binding two
        // statements of one fact that can only ever disagree.
        refuses(twoBlocks("interface",
                          R"(, "binding": {"geom": "square.dat", "seg": 0})"),
                "binding", "21. a 'binding' on an interface");
    }

    // ── 22. orientation comes from the DECLARATION, either way round ────────
    {
        // The right-hand block turned a quarter turn: its i direction runs DOWN the
        // shared edge, which the left-hand block uses as its own j direction. One
        // edge, one declared direction, two blocks that disagree about which way it
        // runs — the case a per-block reversal exists for, and one that cannot be
        // reached with both blocks in the same frame.
        MbResult r = build(rotatedNeighbour());
        CHECK(r.ok, "22. a neighbour whose shared edge runs the opposite way is "
                    "accepted (err: " + r.error + ")");
        if (r.ok && r.blocks.size() == 2) {
            const auto& b0 = r.blocks[0];
            const auto& b1 = r.blocks[1];
            CHECK(b0.ni == 3 && b0.nj == 3 && b1.ni == 3 && b1.nj == 4,
                  "22. ...each block filled in its own frame ("
                  + std::to_string(b1.ni) + "x" + std::to_string(b1.nj) + ")");
            // b0 walks the shared edge as its east, j-min -> j-max; b1 walks the
            // SAME edge as its south, i-min -> i-max, in the opposite direction. So
            // the weld is index-reversed, and it is still node IDENTITY.
            bool welded = true;
            for (int j = 0; j < b0.nj; ++j)
                if (b0.nodeAt(b0.ni - 1, j) != b1.nodeAt(b0.nj - 1 - j, 0)) welded = false;
            CHECK(welded, "22. ...and still welded, with the shared edge's node order "
                          "reversed for the block that traverses it backwards");
            CHECK(r.nodes.size() == 18 && coincidentPairs(r.nodes) == 0,
                  "22. ...into one mesh with no duplicated node ("
                  + std::to_string(r.nodes.size()) + " nodes, "
                  + std::to_string(coincidentPairs(r.nodes)) + " coincident pairs)");
            CHECK(invertedCells(r) == 0,
                  "22. ...and no cell inverted, so the reversal did not mirror a block");
        }
    }
    {
        // A block whose four sides do not CLOSE a ring is refused by name. This is
        // what the retired wrong-direction refusal becomes: the direction of three
        // of the four sides is free, which corners they touch is not.
        refuses(swap1(twoBlocks(), R"("id": "w", "corners": ["a", "d"])",
                                   R"("id": "w", "corners": ["b", "d"])"),
                "'b0'", "22. a block whose sides do not close a ring");
        refuses(swap1(twoBlocks(), R"("id": "w", "corners": ["a", "d"])",
                                   R"("id": "w", "corners": ["b", "d"])"),
                "'w'", "22. ...naming the edge that does not reach the ring");
        // ...and the other way a ring can fail: it CLOSES, but onto three corners
        // instead of four. Two distinct edges over the same corner pair make the
        // block's j-max corner its own i-max corner, so every match above succeeds
        // and there is still no interior to fill. Reachable, not hypothetical —
        // which is why the four corners are checked pairwise distinct after the
        // ring is matched and not instead of it.
        refuses(R"({
  "format_version": 1,
  "corners": [
    {"id": "a", "kind": "free", "xy": [0.0, 0.0]},
    {"id": "b", "kind": "free", "xy": [1.0, 0.0]},
    {"id": "e", "kind": "free", "xy": [1.0, 1.0]}
  ],
  "edges": [
    {"id": "s", "corners": ["a", "b"], "kind": "wall", "count": 3},
    {"id": "w", "corners": ["a", "b"], "kind": "wall", "count": 3},
    {"id": "e1", "corners": ["b", "e"], "kind": "wall"},
    {"id": "n", "corners": ["b", "e"], "kind": "wall"}
  ],
  "blocks": [
    {"id": "b0", "edges": ["s", "e1", "n", "w"]}
  ]
})", "two different corners", "22. a ring that closes onto three corners");
    }

    // ── 23. NOTHING welds by coordinate — the negative control ─────────────
    //
    // The same two blocks, but the shared line declared as TWO edges whose corners
    // sit at IDENTICAL coordinates under different ids. Nothing welds them, and
    // that is the point: if any distance comparison existed in this path it would
    // fire exactly here, at a separation of zero. Wall spacing on a real case is
    // around 1e-7 while far-field spacing is around 1e-1, so no single tolerance
    // exists between the two scales — the declaration is the only thing that can
    // say two nodes are one.
    {
        MbResult r = build(coincidentButSeparate());
        CHECK(r.ok, "23. two blocks that merely TOUCH are accepted (err: "
                    + r.error + ")");
        if (r.ok && r.blocks.size() == 2) {
            const auto& b0 = r.blocks[0];
            const auto& b1 = r.blocks[1];
            bool anyShared = false;
            for (int j = 0; j < b0.nj; ++j)
                if (b0.nodeAt(b0.ni - 1, j) == b1.nodeAt(0, j)) anyShared = true;
            CHECK(!anyShared, "23. ...and are NOT welded, though their corners sit at "
                              "exactly the same coordinates");
            CHECK(r.nodes.size() == 21,
                  "23. ...so the mesh holds all 21 nodes, three of them duplicated ("
                  + std::to_string(r.nodes.size()) + ")");
            CHECK(coincidentPairs(r.nodes) == 3,
                  "23. ...which is visible as three coincident pairs ("
                  + std::to_string(coincidentPairs(r.nodes)) + ")");
            CHECK(r.sharedEdges.empty(),
                  "23. ...and nothing is reported as shared, because nothing is");
        }
    }

    // ── 24. all four diagonal rules, each on a known block ─────────────────
    //
    // Through the seam and read off the cells, never off an export: what a rule
    // does is which of two triangles a quad becomes, and that is a fact about
    // `MbResult`. Check 3 already pins the default; this pins the other three
    // against it, which is the only way "selectable" means anything.
    {
        const std::string doc = square(5, 4);   // 4x3 = 12 quads
        const MbResult alt = build(doc);
        const MbResult fwd = build(doc, splitRule(hybmesh::MB_SPLIT_FORWARD));
        const MbResult bwd = build(doc, splitRule(hybmesh::MB_SPLIT_BACKWARD));
        const MbResult rnd = build(doc, splitRule(hybmesh::MB_SPLIT_RANDOM, 7));
        CHECK(alt.ok && fwd.ok && bwd.ok && rnd.ok, "24. setup: all four rules build");

        const std::vector<bool> dA = diagonals(alt, "b0");
        const std::vector<bool> dF = diagonals(fwd, "b0");
        const std::vector<bool> dB = diagonals(bwd, "b0");
        const std::vector<bool> dR = diagonals(rnd, "b0");
        CHECK(dA.size() == 12 && dF.size() == 12 && dB.size() == 12 && dR.size() == 12,
              "24. every rule fills the same 12 quads ("
              + std::to_string(dA.size()) + "/" + std::to_string(dF.size()) + "/"
              + std::to_string(dB.size()) + "/" + std::to_string(dR.size()) + ")");

        CHECK(std::all_of(dF.begin(), dF.end(), [](bool d) { return d; }),
              "24. rule 1 takes the FORWARD diagonal in every quad");
        CHECK(std::none_of(dB.begin(), dB.end(), [](bool d) { return d; }),
              "24. rule 2 takes the BACKWARD diagonal in every quad");

        // The default is neither fixed rule: that it ALTERNATES is check 3's job,
        // and this only has to establish that "fixed" is a different mesh from it.
        CHECK(dA != dF && dA != dB, "24. rule 0 is neither of the two fixed rules");

        // The randomized rule uses BOTH diagonals -- a hash that always returned
        // the same bit would pass every count-based check above -- and lays them
        // down in a pattern that is not the parity one.
        const size_t fwdCount = static_cast<size_t>(
            std::count(dR.begin(), dR.end(), true));
        CHECK(fwdCount > 0 && fwdCount < dR.size(),
              "24. rule 3 uses both diagonals (" + std::to_string(fwdCount)
              + " of " + std::to_string(dR.size()) + " forward)");
        CHECK(dR != dA, "24. ...and is not the alternating pattern under another name");

        // Whatever the rule, the mesh must still be a mesh.
        for (const MbResult* res : {&alt, &fwd, &bwd, &rnd}) {
            CHECK(res->cells.size() == 24u, "24. ...and every rule emits two triangles "
                                            "per quad");
            CHECK(invertedCells(*res) == 0,
                  "24. ...wound counter-clockwise, so no rule inverts a cell");
        }
    }

    // ── 25. the randomized rule is REPRODUCIBLE from its seed ──────────────
    //
    // The comparator compares exported connectivity and a diagonal changes exactly
    // that, so without this property the randomized rule would take this path out
    // of regression testing altogether. Same topology, same seed, byte-identical
    // connectivity; a different seed, a different mesh.
    {
        const std::string doc = square(6, 5);
        const MbResult a = build(doc, splitRule(hybmesh::MB_SPLIT_RANDOM, 12345));
        const MbResult b = build(doc, splitRule(hybmesh::MB_SPLIT_RANDOM, 12345));
        const MbResult c = build(doc, splitRule(hybmesh::MB_SPLIT_RANDOM, 12346));
        CHECK(a.ok && b.ok && c.ok, "25. setup");
        CHECK(connectivity(a) == connectivity(b),
              "25. the same topology and seed give byte-identical connectivity");
        CHECK(connectivity(a) != connectivity(c),
              "25. ...and a different seed gives a different mesh, so the seed is "
              "read rather than ignored");
        // The seed changes the DIAGONALS and nothing else: same nodes, same
        // positions, same boundary. A seed that moved a node would not be a split
        // rule.
        CHECK(a.nodes.size() == c.nodes.size()
                  && a.boundaryEdges.size() == c.boundaryEdges.size()
                  && a.cells.size() == c.cells.size(),
              "25. ...and changes only which diagonal, never the node set");
    }

    // ── 26. an unrelated block does not disturb anyone else's diagonals ─────
    //
    // THE property a sequential generator violates, and the reason this rule is
    // hash-based. The extra block is declared FIRST, so both existing blocks are
    // renumbered: a hash of the block INDEX would move every diagonal in the mesh,
    // and a draw from a stream would move them all as soon as the extra block's
    // cells were drawn first. Tested directly rather than argued for.
    {
        const MbParams p = splitRule(hybmesh::MB_SPLIT_RANDOM, 99);
        const MbResult two   = build(weldedPair(false), p);
        const MbResult three = build(weldedPair(true), p);
        CHECK(two.ok && three.ok, "26. setup (err: " + two.error + " / "
                                  + three.error + ")");
        CHECK(two.blocks.size() == 2 && three.blocks.size() == 3,
              "26. ...the third block really is in the second document");

        // The renumbering the fixture exists to cause, asserted so the check
        // cannot quietly stop testing what it says it tests.
        CHECK(three.blocks[0].id == "bx",
              "26. ...and is declared AHEAD of them, so 'b0' and 'b1' move index");

        const std::vector<bool> b0two = diagonals(two, "b0");
        const std::vector<bool> b1two = diagonals(two, "b1");
        const std::vector<bool> b0three = diagonals(three, "b0");
        const std::vector<bool> b1three = diagonals(three, "b1");
        // Non-empty on BOTH sides before they are compared. `diagonals` returns an
        // empty vector for a block it cannot read, and two empty vectors compare
        // equal — so without this line the two checks below would pass loudest
        // exactly when the helper had stopped working.
        CHECK(b0two.size() == 16 && b1two.size() == 20
                  && b0three.size() == 16 && b1three.size() == 20,
              "26. ...setup: both blocks' quads are readable in both documents ("
              + std::to_string(b0two.size()) + "/" + std::to_string(b1two.size())
              + " vs " + std::to_string(b0three.size()) + "/"
              + std::to_string(b1three.size()) + ")");
        CHECK(b0two == b0three, "26. block 'b0' keeps every one of its diagonals");
        CHECK(b1two == b1three, "26. block 'b1' keeps every one of its diagonals");

        // ...and the new block is not simply a copy of one of them, which is what
        // "unchanged" would degenerate to if the hash ignored the block entirely.
        CHECK(diagonals(three, "bx") != b1three,
              "26. ...while the new block gets its own pattern, so the block's "
              "identity is in the hash at all");
    }

    // ── 27. an unknown split rule is REFUSED, never clamped ────────────────
    //
    // Same answer as an unknown MESH_MODE and for the same reason: there is no
    // obviously right rule to fall back on, and meshing with one nobody asked for
    // leaves no symptom. The refusal is the seam's, so a caller that is not the
    // .dat reader gets it too.
    {
        for (int bad : {-1, 4, 99}) {
            MbResult r = build(square(4, 3), splitRule(bad));
            CHECK(!r.ok, "27. split rule " + std::to_string(bad) + " is refused");
            CHECK(mentions(r.error, std::to_string(bad)),
                  "27. ...and the message names it (got: " + r.error + ")");
            CHECK(r.cells.empty() && r.nodes.empty(),
                  "27. ...and nothing is produced");
        }
    }

    // ── 28. a seed nothing reads is SAID, not silently kept ────────────────
    //
    // A seed set beside a rule that does not hash it decides nothing, but it still
    // reaches the run's provenance record -- where it implies that the mesh can be
    // reproduced from it. That is the silent-wrong-value failure this repo keeps
    // closing, so the seam names it.
    {
        auto seedWarned = [](const MbResult& r) {
            for (const auto& w : r.warnings) if (mentions(w, "split seed")) return true;
            return false;
        };
        CHECK(seedWarned(build(square(4, 3),
                               splitRule(hybmesh::MB_SPLIT_ALTERNATING, 5))),
              "28. a seed set beside the alternating rule is named");
        CHECK(seedWarned(build(square(4, 3), splitRule(hybmesh::MB_SPLIT_FORWARD, 5))),
              "28. ...and beside a fixed rule");
        {
            MbParams p = splitRule(hybmesh::MB_SPLIT_RANDOM, 5);
            p.splitQuads = false;
            CHECK(seedWarned(build(square(4, 3), p)),
                  "28. ...and with the randomized rule chosen but splitting OFF, "
                  "where it likewise decides nothing");
        }
        CHECK(!seedWarned(build(square(4, 3), splitRule(hybmesh::MB_SPLIT_RANDOM, 5))),
              "28. ...and NOT when the randomized rule is actually the one running");
        CHECK(!seedWarned(build(square(4, 3), splitRule(hybmesh::MB_SPLIT_ALTERNATING, 0))),
              "28. ...nor when no seed was set at all");
    }

    // ── 29. two blocks may not share an id ─────────────────────────────────
    //
    // Refused like a duplicate corner or edge id, and found by the SPEC review of
    // #54 rather than by symmetry: nothing read a block id until the randomized
    // rule hashed it, so two blocks under one id were accepted and cut IDENTICALLY
    // — a correlated pattern, which is the bias that rule exists to break.
    {
        refuses(swap1(weldedPair(false), R"("id": "b1", "edges")",
                                         R"("id": "b0", "edges")"),
                "duplicate block id", "29. two blocks declared under one id");
        refuses(swap1(weldedPair(false), R"("id": "b1", "edges")",
                                         R"("id": "b0", "edges")"),
                "'b0'", "29. ...naming the id that repeats");
        // The duplicate EDGE id refusal, which has existed since #50 and which
        // nothing covered: injection O was first aimed at the wrong one of the
        // three identical-looking `prev.id == spec.id` loops, disabled THIS one,
        // and the whole suite stayed green. Added here rather than left as a known
        // hole — it is three lines, and the refusal it guards is the same family as
        // the one above.
        refuses(swap1(weldedPair(false), R"("id": "n0", "corners")",
                                         R"("id": "s0", "corners")"),
                "duplicate edge id", "29. two edges declared under one id");
    }

    // ── 30. the default distribution law is TANH, and it is uniform unless
    //        something asks it to cluster ───────────────────────────────────
    //
    // The default is structural: a count can be decided FOR an edge by
    // propagation, so the law has to absorb one it did not choose. Asserted as
    // BIT EQUALITY against an explicitly uniform document rather than as
    // "roughly uniform", because the whole reason the default could be changed
    // at all is that tanh at delta 0 evaluates the same expression.
    {
        MbResult a = build(square(9, 5));
        MbResult b = build(square(9, 5, R"(, "spacing": {"law": "uniform"})"));
        CHECK(a.ok && b.ok, "30. both documents are accepted");
        CHECK(a.nodes.size() == b.nodes.size(), "30. ...with the same node count");
        bool same = a.nodes.size() == b.nodes.size();
        for (size_t k = 0; same && k < a.nodes.size(); ++k)
            same = a.nodes[k].x == b.nodes[k].x && a.nodes[k].y == b.nodes[k].y;
        CHECK(same, "30. an edge that declares no law is BIT-IDENTICAL to one that "
                    "declares 'uniform': the default is tanh, and tanh with nothing "
                    "to cluster IS the uniform law");
        // ...and the schema really did take 'tanh' as the default rather than
        // ignoring the key: a raw delta on an edge that declares no law at all
        // must be accepted and must MOVE the nodes.
        MbResult c = build(square(9, 5, R"(, "spacing": {"delta": 2.0})"));
        CHECK(c.ok, "30. a 'delta' with no 'law' is accepted — the law it belongs to "
                    "is the default (err: " + c.error + ")");
        bool moved = false;
        for (size_t k = 0; c.ok && k < a.nodes.size() && k < c.nodes.size(); ++k)
            if (a.nodes[k].x != c.nodes[k].x) moved = true;
        CHECK(moved, "30. ...and it clusters, so the default is not merely a name");
    }

    // ── 31. a declared wall spacing IS the first interval, at any count ─────
    //
    // The property the tanh default exists to provide, measured rather than
    // argued: the same declaration under three different SEEDED counts must put
    // the first node the same distance off the wall. A "first N layers geometric"
    // formulation would move it every time.
    {
        const double want = 1.0e-4;
        for (int n : {5, 9, 33}) {
            MbParams p;
            // The west edge runs from (0,0) to (0,1) and carries `nj`; clustering
            // its START puts the fine cell at the block's south-west corner.
            const std::string doc = swap1(
                square(4, n),
                R"({"id": "w", "corners": ["sw", "nw"], "kind": "wall", "count": )"
                    + std::to_string(n),
                R"({"id": "w", "corners": ["sw", "nw"], "kind": "wall", "count": )"
                    + std::to_string(n)
                    + R"(, "spacing": {"ds_start": 0.0001})");
            MbResult r = build(doc, p);
            CHECK(r.ok, "31. a wall spacing is accepted at count " + std::to_string(n)
                        + " (err: " + r.error + ")");
            if (!r.ok || r.blocks.empty()) continue;
            const auto& b = r.blocks[0];
            const double got = (nodeOf(r, b, 0, 1) - nodeOf(r, b, 0, 0)).length();
            // 1e-9 relative, and the bound is DERIVED rather than picked: a node
            // is placed as `p0 + (p1 - p0) * f` along an edge of length 1, so its
            // rounding is ~eps of the EDGE, not of the first cell. A first cell of
            // relative size 1e-4 therefore lands within ~eps/1e-4 = 1e-12 of what
            // was asked for, measured at exactly 1.000e-12 here. The bound is three
            // orders looser than that so a different libm cannot flake it, and it
            // is still eight orders tighter than the 0.08% a real curved geometry's
            // own faceting costs (recorded in the surface gate next door).
            CHECK(std::fabs(got - want) <= 1e-9 * want,
                  "31. the first interval off the wall IS the declared "
                  + std::to_string(want) + " at count " + std::to_string(n)
                  + " (got " + std::to_string(got) + ")");
        }
    }

    // ── 32. the global default, and the per-edge override that beats it ─────
    {
        MbParams glob;
        glob.wallSpacing = 2.5e-3;
        const std::string usesGlobal = swap1(
            square(4, 9),
            R"("id": "w", "corners": ["sw", "nw"], "kind": "wall", "count": 9)",
            R"("id": "w", "corners": ["sw", "nw"], "kind": "wall", "count": 9,
     "spacing": {"wall_ends": "start"})");
        MbResult g = build(usesGlobal, glob);
        CHECK(g.ok, "32. an edge naming a wall end with no number takes the global "
                    "(err: " + g.error + ")");
        if (g.ok && !g.blocks.empty()) {
            const auto& b = g.blocks[0];
            const double got = (nodeOf(g, b, 0, 1) - nodeOf(g, b, 0, 0)).length();
            CHECK(std::fabs(got - glob.wallSpacing) <= 1e-12 * glob.wallSpacing,
                  "32. ...and that global IS the first interval (got "
                  + std::to_string(got) + ")");
        }
        // The override wins, and it wins over a global that is SET — a test
        // against an unset global could not tell "the override applied" from
        // "there was nothing else to apply".
        const std::string overrides = swap1(
            square(4, 9),
            R"("id": "w", "corners": ["sw", "nw"], "kind": "wall", "count": 9)",
            R"("id": "w", "corners": ["sw", "nw"], "kind": "wall", "count": 9,
     "spacing": {"ds_start": 7.5e-05})");
        MbResult o = build(overrides, glob);
        CHECK(o.ok, "32. a per-edge ds_start is accepted beside a global (err: "
                    + o.error + ")");
        if (o.ok && !o.blocks.empty()) {
            const auto& b = o.blocks[0];
            const double got = (nodeOf(o, b, 0, 1) - nodeOf(o, b, 0, 0)).length();
            CHECK(std::fabs(got - 7.5e-5) <= 1e-12 * 7.5e-5,
                  "32. ...and the EDGE's number beats the global (got "
                  + std::to_string(got) + ")");
        }
        // No global, and no number on the edge: refused BY NAME rather than
        // quietly left uniform. An edge that asked to cluster and silently did
        // not is a mesh with no boundary layer and no symptom.
        refuses(usesGlobal, "BL_INITIAL_THICKNESS",
                "32. a wall end with no spacing anywhere is refused, naming the "
                "config key that would supply it");
    }

    // ── 33. the ring's equivalence class WRAPS AROUND and closes ────────────
    //
    // The case a linear chain of blocks never reaches, and the one most likely to
    // hide a defect in propagation or welding: 'q3' names as its north the very
    // edge 'q0' names as its south. One seed, three propagated, and the seam is
    // node IDENTITY — the same ids, not two curves a tolerance apart.
    {
        const auto geoms = ogridGeoms();
        MbParams p;
        p.wallSpacing = 1.0e-3;
        MbResult r = hybmesh::buildMultiBlock(ogrid(R"(, "spacing": {"wall_ends": "start"})"),
                                              geoms, p);
        CHECK(r.ok, "33. a four-block O-grid is accepted (err: " + r.error + ")");
        CHECK(r.blocks.size() == 4, "33. four blocks come back");
        // Every radial resolved to the seeded count, and exactly one of the four
        // says it was seeded.
        int seeded = 0, radials = 0;
        for (const auto& ec : r.edgeCounts) {
            if (ec.edgeId.size() != 2 || ec.edgeId[0] != 'r') continue;
            ++radials;
            if (ec.seeded) ++seeded;
            CHECK(ec.count == 7, "33. radial '" + ec.edgeId + "' carries the ring's "
                                 "one seeded count (got " + std::to_string(ec.count) + ")");
        }
        CHECK(radials == 4 && seeded == 1,
              "33. one radial is seeded and three propagate AROUND the ring "
              "(seeded " + std::to_string(seeded) + " of " + std::to_string(radials) + ")");
        if (r.blocks.size() == 4) {
            // THE CLOSURE, as node ids. q3's north (j runs the other way in each
            // block's own frame, so compare the two sides as SETS of ids in order
            // along the edge) is q0's south.
            const auto& q0 = r.blocks[0];
            const auto& q3 = r.blocks[3];
            bool welded = q0.ni == q3.ni;
            for (int i = 0; welded && i < q0.ni; ++i)
                welded = q0.nodeAt(i, 0) == q3.nodeAt(i, q3.nj - 1);
            CHECK(welded, "33. the LAST block's north edge is the FIRST block's south "
                          "edge, node for node, by identity — the ring closes");
        }
        // ...and nothing was double-allocated where it closed: an O-grid of four
        // blocks has exactly 4 * (ni * nj) - 4 * ni nodes, the four shared radials
        // counted once each.
        {
            size_t want = 0;
            for (const auto& b : r.blocks)
                want += static_cast<size_t>(b.ni) * static_cast<size_t>(b.nj);
            for (const auto& b : r.blocks) want -= static_cast<size_t>(b.ni);
            CHECK(r.nodes.size() == want,
                  "33. ...and the shared radials are allocated ONCE, so the ring has "
                  + std::to_string(want) + " nodes (got "
                  + std::to_string(r.nodes.size()) + ")");
        }
        // The body arcs FOLLOW the circle. A chord across a quarter circle sits
        // 0.293 r off the body at its midpoint, so this is the difference between
        // a circle and a square, not a refinement.
        {
            double worst = 0.0;
            for (const auto& be : r.boundaryEdges) {
                if (be.bc != "wall") continue;
                for (int v : {be.v1, be.v2}) {
                    const Point2D& q = r.nodes[static_cast<size_t>(v)];
                    worst = std::max(worst, std::fabs(std::sqrt(q.x * q.x + q.y * q.y) - 0.5));
                }
            }
            CHECK(worst < 1.0e-3,
                  "33. every wall node sits ON the circle, not on a chord across it "
                  "(worst radial deviation " + std::to_string(worst) + ")");
        }
        // Both geometries' conditions reach the export, from their own sidecars.
        {
            size_t wall = 0, far = 0;
            for (const auto& be : r.boundaryEdges) {
                if (be.bc == "wall") ++wall;
                else if (be.bc == "farfield") ++far;
            }
            CHECK(wall > 0 && far > 0 && wall + far == r.boundaryEdges.size(),
                  "33. the body exports as 'wall' and the far field as 'farfield', "
                  "each from its own geometry (" + std::to_string(wall) + " / "
                  + std::to_string(far) + " of "
                  + std::to_string(r.boundaryEdges.size()) + ")");
        }
    }

    // ── 34. the wall REQUEST is the declaration, not the mesh's own answer ──
    //
    // Until this release `MbWallSpec` published the first interval the fill had
    // already produced, so a rectangle's 0.00% was a tautology. It now publishes
    // what the perpendicular edge DECLARED, which is what makes the quality
    // report a comparison. The negative control is the second half: an edge that
    // declares nothing still publishes the produced interval, so a topology that
    // never asks for a height keeps a meaningful figure.
    {
        MbParams p;
        p.wallSpacing = 1.0e-3;
        MbResult r = hybmesh::buildMultiBlock(ogrid(R"(, "spacing": {"wall_ends": "start"})"),
                                              ogridGeoms(), p);
        CHECK(r.ok, "34. the O-grid is accepted (err: " + r.error + ")");
        size_t body = 0, outer = 0;
        for (const auto& ws : r.wallSpecs) {
            if (ws.edgeId.empty()) continue;
            if (ws.edgeId[0] == 'w') {
                ++body;
                CHECK(ws.requestedLo == 1.0e-3 && ws.requestedHi == 1.0e-3,
                      "34. a body arc's request is the DECLARED 1e-3 at both ends, "
                      "not the interval the fill produced (got "
                      + std::to_string(ws.requestedLo) + ")");
            } else if (ws.edgeId[0] == 'o') {
                ++outer;
                // The far-field end of the same radials declares nothing, so the
                // request there falls back to what was produced — a number far
                // larger than the wall spacing, which is the whole point.
                CHECK(ws.requestedLo > 1.0e-2,
                      "34. the far-field side, whose perpendiculars declare nothing "
                      "at that end, still publishes the produced interval (got "
                      + std::to_string(ws.requestedLo) + ")");
            }
        }
        CHECK(body == 4 && outer == 4,
              "34. all eight outer sides are listed and the four interfaces are not "
              "(" + std::to_string(body) + " body, " + std::to_string(outer) + " outer)");
    }

    // ── 35. what this release cannot do is refused BY NAME ──────────────────
    {
        MbParams p;
        p.wallSpacing = 1.0e-3;
        auto sq = [](const std::string& sp) {
            return swap1(square(4, 9),
                         R"("id": "w", "corners": ["sw", "nw"], "kind": "wall", "count": 9)",
                         R"("id": "w", "corners": ["sw", "nw"], "kind": "wall", "count": 9,
     "spacing": )" + sp);
        };
        auto refusesWith = [&](const std::string& doc, const std::string& names,
                               const std::string& what) {
            MbResult r = hybmesh::buildMultiBlock(doc, {}, p);
            CHECK(!r.ok, what + ": must be refused");
            CHECK(mentions(r.error, names),
                  what + ": the message must name '" + names + "' (got: " + r.error + ")");
        };
        refusesWith(sq(R"({"ds_start": 1e-4, "ds_end": 5e-4})"), "'w'",
                    "35. two DIFFERENT heights at the two ends");
        refusesWith(sq(R"({"law": "geometric", "growth": 1.1, "ds_start": 1e-4})"),
                    "geometric",
                    "35. a wall spacing on a law that cannot solve for one");
        refusesWith(sq(R"({"delta": 2.0, "ds_start": 1e-4})"), "delta",
                    "35. the raw tanh parameter AND the spacing it would be solved from");
        refusesWith(sq(R"({"ds_start": -1e-4})"), "ds_start",
                    "35. a first-cell height that is not a positive length");
        refusesWith(sq(R"({"wall_ends": "middle"})"), "wall_ends",
                    "35. an unknown 'wall_ends' value");
        refusesWith(sq(R"({"law": "tanh", "growth": 1.1})"), "growth",
                    "35. a geometric ratio on an edge that declares tanh");
        // ...and equal heights at both ends are ACCEPTED, so the refusal above is
        // about the DIFFERENCE and not about declaring two ends at all.
        MbResult ok = hybmesh::buildMultiBlock(
            sq(R"({"ds_start": 1e-4, "ds_end": 1e-4})"), {}, p);
        CHECK(ok.ok, "35. equal heights at both ends are accepted (err: " + ok.error + ")");
    }

    // ── 36. a BOUND, CURVED edge that asks for a wall spacing gets it, and is
    //        not accused of failing ────────────────────────────────────────
    //
    // The defect BOTH review axes found independently, kept as a check because it
    // is the exact geometry this feature exists for. The "you asked for a spacing
    // you did not get" warning measured the produced CHORD against an ARC-LENGTH
    // request: a bound edge follows a polyline, so a first interval spanning
    // several facets has a chord shorter than the arc, and the warning fired on a
    // law that had honoured the request exactly — blaming the node count for the
    // geometry's own faceting. Measured on the shipped circle at the time: a 0.05
    // request reported as a 0.049978 chord.
    {
        MbParams p;
        // Fine enough to be achievable at this count, coarse enough to span
        // several of the polyline's facets — the only configuration in which a
        // chord and an arc differ at all.
        MbResult r = hybmesh::buildMultiBlock(
            ogrid("", 7, 5, R"(, "spacing": {"ds_start": 0.05})"), ogridGeoms(), p);
        CHECK(r.ok, "36. a bound curved edge may declare a wall spacing (err: "
                    + r.error + ")");
        std::string spurious;
        for (const std::string& w : r.warnings)
            if (mentions(w, "asks for a first cell height")) spurious += w;
        CHECK(spurious.empty(),
              "36. ...and nothing accuses it of missing a target it hit: the request "
              "is an ARC LENGTH along the polyline and so is what it is measured "
              "against (got: " + spurious + ")");
        // THE NEGATIVE CONTROL. The warning must still bite on a request the law
        // genuinely cannot honour — coarser than the uniform spacing the count
        // already gives — or the check above would pass on a dead warning.
        MbResult c = hybmesh::buildMultiBlock(
            ogrid("", 7, 5, R"(, "spacing": {"ds_start": 0.5})"), ogridGeoms(), p);
        bool warned = false;
        for (const std::string& w : c.warnings)
            if (mentions(w, "asks for a first cell height")) warned = true;
        CHECK(c.ok && warned,
              "36. a request COARSER than the edge's own uniform spacing is still "
              "reported, so the check above is not passing on a dead warning");
    }

    // ── 37. a four-block C-GRID welds along a CUT that is BOTH blocks' west ──
    //
    // Every shared edge before this one was one block's east and another's west,
    // so the two frames ran the same way along it. A wake cut is the case that
    // breaks that assumption: the two blocks sit on OPPOSITE sides of one line,
    // so both declare it as the same side and traverse it in opposite senses.
    {
        MbResult r = hybmesh::buildMultiBlock(cgrid(), cgridGeoms(), MbParams{});
        CHECK(r.ok, "37. a four-block C-grid is accepted (err: " + r.error + ")");
        CHECK(r.blocks.size() == 4, "37. four blocks come back");
        const hybmesh::MbSharedEdge* cut = nullptr;
        for (const auto& se : r.sharedEdges) if (se.edgeId == "wake") cut = &se;
        CHECK(cut != nullptr, "37. 'wake' comes back as a SHARED edge");
        if (cut) {
            CHECK(cut->kind == hybmesh::MB_EDGE_CUT,
                  "37. ...declared a CUT, not inferred to be an interface");
            CHECK(cut->sideA == hybmesh::MB_WEST && cut->sideB == hybmesh::MB_WEST,
                  "37. ...and it is the WEST of BOTH blocks, which no earlier "
                  "fixture in this file produces");
        }
        if (r.blocks.size() == 4) {
            const auto& up = r.blocks[0];   // b_wake_up
            const auto& lo = r.blocks[3];   // b_wake_lo
            bool mirrored = up.nj == lo.nj;
            for (int j = 0; mirrored && j < up.nj; ++j)
                mirrored = up.nodeAt(0, j) == lo.nodeAt(0, lo.nj - 1 - j);
            CHECK(mirrored,
                  "37. the two wake blocks share the cut node for node, in "
                  "OPPOSITE j order — one line, two frames, no tolerance");
            // THE NEGATIVE CONTROL for the reversal: a straight-through match
            // must NOT also hold, or the check above would pass on a palindrome.
            bool forward = true;
            for (int j = 0; forward && j < up.nj; ++j)
                forward = up.nodeAt(0, j) == lo.nodeAt(0, j);
            CHECK(!forward,
                  "37. ...and the same-order match does NOT hold, so the "
                  "reversal above is real and not a palindrome");
        }
        // A cut is NOT a boundary of anything: no face of it is exported. Its
        // nodes are the ones the two wake blocks share, and no boundary edge may
        // have both ends among them.
        if (r.blocks.size() == 4) {
            std::set<int> cutNodes;
            for (int j = 0; j < r.blocks[0].nj; ++j)
                cutNodes.insert(r.blocks[0].nodeAt(0, j));
            int onCut = 0;
            for (const auto& be : r.boundaryEdges)
                if (cutNodes.count(be.v1) && cutNodes.count(be.v2)) ++onCut;
            CHECK(onCut == 0,
                  "37. ...and NO boundary face lies on it (" + std::to_string(onCut)
                  + ") — that is the whole difference between a cut and a wall");
        }
    }

    // ── 38. the FOUR-WAY corner is ONE node, and all four blocks hold it ─────
    //
    // The highest-risk single point in a C-grid, and the one a proximity weld
    // would have to guess at: five edges end on 'te' and four blocks meet there.
    // It is one declaration, so it is one node, and each block finds it at the
    // logical corner its own frame puts it at.
    {
        MbResult r = hybmesh::buildMultiBlock(cgrid(), cgridGeoms(), MbParams{});
        CHECK(r.ok, "38. the C-grid is accepted (err: " + r.error + ")");
        if (r.ok && r.blocks.size() == 4) {
            const auto& up = r.blocks[0], &b1 = r.blocks[1];
            const auto& b2 = r.blocks[2], &lo = r.blocks[3];
            const int id = up.nodeAt(0, up.nj - 1);
            const bool one = id == b1.nodeAt(0, 0)
                          && id == b2.nodeAt(0, b2.nj - 1)
                          && id == lo.nodeAt(0, 0);
            CHECK(one, "38. all FOUR blocks hold the trailing edge as the SAME "
                       "node id — welded by declaration, not by coordinate");
            CHECK(std::abs(r.nodes[static_cast<size_t>(id)].x - 0.5) < 1e-12
                  && std::abs(r.nodes[static_cast<size_t>(id)].y) < 1e-12,
                  "38. ...and it is where the geometry attachment puts it, (0.5, 0)");
            // Exactly ONE node is there. The negative control for the whole
            // corner: four blocks that failed to identify it would leave up to
            // four coincident nodes, which is a mesh no conformity check on
            // coordinates could tell from a correct one.
            int coincident = 0;
            for (const auto& n : r.nodes)
                if (std::abs(n.x - 0.5) < 1e-12 && std::abs(n.y) < 1e-12) ++coincident;
            CHECK(coincident == 1,
                  "38. ...and it is the ONLY node at that point (found "
                  + std::to_string(coincident) + ")");
        }
        // The count, derived rather than observed. The four blocks own
        // 3*4 + 3*6 + 3*6 + 3*4 = 60 node SLOTS; the cut identifies 4 of them
        // and each of the three radials 3, so 13 identifications leave 47 nodes.
        // Three of those 13 are the trailing edge's own, which is exactly what it
        // takes to bring four occurrences of it down to one.
        {
            size_t slots = 0;
            for (const auto& b : r.blocks)
                slots += static_cast<size_t>(b.ni) * static_cast<size_t>(b.nj);
            CHECK(slots == 60 && r.nodes.size() == 47,
                  "38. 60 node slots resolve to 47 nodes — 4 identified along the "
                  "cut and 3 along each radial (got " + std::to_string(slots)
                  + " slots, " + std::to_string(r.nodes.size()) + " nodes)");
        }
    }

    // ── 39. the count propagates the LENGTH of the C, through the cut ────────
    //
    // The C is a chain of four blocks and its five radials are ONE equivalence
    // class: 'r_te_up' is the only one that declares a count, and it reaches the
    // two outlet edges at the far ends by passing through blocks that are linked
    // only by the cut and by each other's radials. The O-grid's ring closes on
    // itself; this one does not, and the open ends are where a chain-walking
    // defect would stop early.
    {
        MbResult r = hybmesh::buildMultiBlock(cgrid(), cgridGeoms(), MbParams{});
        CHECK(r.ok, "39. the C-grid is accepted (err: " + r.error + ")");
        int seeded = 0, radials = 0;
        for (const auto& ec : r.edgeCounts) {
            const bool isRadial = ec.edgeId == "r_te_up" || ec.edgeId == "r_le"
                               || ec.edgeId == "r_te_lo" || ec.edgeId == "e_out_up"
                               || ec.edgeId == "e_out_lo";
            if (!isRadial) continue;
            ++radials;
            if (ec.seeded) ++seeded;
            CHECK(ec.count == 3, "39. radial '" + ec.edgeId + "' carries the C's one "
                                 "seeded count (got " + std::to_string(ec.count) + ")");
        }
        CHECK(radials == 5 && seeded == 1,
              "39. one of the FIVE radials is seeded and four propagate down the "
              "chain (seeded " + std::to_string(seeded) + " of "
              + std::to_string(radials) + ")");
        // The j class the CUT spans: 'wake' seeds it and both far-field sides of
        // the two wake blocks take it, which they can only do THROUGH the cut.
        int wakeClass = 0;
        for (const auto& ec : r.edgeCounts)
            if (ec.edgeId == "wake" || ec.edgeId == "e_ff_up" || ec.edgeId == "e_ff_lo") {
                ++wakeClass;
                CHECK(ec.count == 4, "39. '" + ec.edgeId + "' is in the cut's own "
                                     "count class (got " + std::to_string(ec.count) + ")");
            }
        CHECK(wakeClass == 3,
              "39. ...and that class has all three of its members");
    }

    // ── 40. at its default the smoother is NOT THERE, not merely quiet ──────
    //
    // The whole increment is built behind a parameter whose default is "do
    // nothing", so the claim that has to hold first is that a run at the default
    // returns what it returned before the smoother existed — including the absence
    // of a "before" list, since a run that did not smooth has no before distinct
    // from what it returned. Asserted as BIT equality: an "approximately the same"
    // default is a default that has already changed the eighteen golden meshes.
    {
        MbParams zero;
        zero.smoothIters = 0;
        MbResult a = build(wallSquare(9, 7, "0.02"));            // MbParams{}
        MbResult b = build(wallSquare(9, 7, "0.02"), zero);      // said out loud
        CHECK(a.ok && b.ok, "40. the graded wall block is accepted (err: " + a.error
                            + " / " + b.error + ")");
        CHECK(a.preSmoothNodes.empty() && b.preSmoothNodes.empty(),
              "40. a run that does not smooth publishes NO 'before' list");
        CHECK(worstMove(a.nodes, b.nodes) == 0.0,
              "40. ...and the default IS zero sweeps, bit for bit");
        CHECK(a.cells.size() == b.cells.size() && a.blocks.size() == b.blocks.size(),
              "40. ...over the same cells and blocks");
    }

    // ── 41. only STRICTLY INTERIOR nodes move; every block boundary is frozen ─
    //
    // The decision this ticket had to make rather than defer, checked as data:
    // outer walls, bound edges, interfaces and cuts are all block boundaries, and
    // a node on any of them is written by the EDGE — which is SHARED, so moving
    // one would move it in two blocks at once and would take a bound node off the
    // geometry it was attached to by arc length. Driven on the four-block C-grid
    // because that is the only fixture here whose boundaries include all four
    // kinds at once.
    {
        MbParams p;
        p.smoothIters = 3;
        MbResult u = hybmesh::buildMultiBlock(cgrid(), cgridGeoms(), MbParams{});
        MbResult r = hybmesh::buildMultiBlock(cgrid(), cgridGeoms(), p);
        CHECK(u.ok && r.ok, "41. the C-grid is accepted with and without smoothing "
                            "(err: " + u.error + " / " + r.error + ")");
        CHECK(r.preSmoothNodes.size() == r.nodes.size(),
              "41. a smoothed run publishes a 'before' list parallel to its nodes");
        CHECK(worstMove(r.preSmoothNodes, u.nodes) == 0.0,
              "41. ...and that list IS the unsmoothed mesh, bit for bit — so the two "
              "quality reports differ by the smoother and by nothing else");
        // Frozen, and MOVED, counted separately: "nothing moved" would satisfy the
        // frozen half on its own.
        std::vector<bool> boundary(r.nodes.size(), false);
        for (const auto& b : r.blocks)
            for (int j = 0; j < b.nj; ++j)
                for (int i = 0; i < b.ni; ++i)
                    if (i == 0 || j == 0 || i == b.ni - 1 || j == b.nj - 1)
                        boundary[static_cast<size_t>(b.nodeAt(i, j))] = true;
        size_t frozen = 0, movedInterior = 0, movedBoundary = 0;
        for (size_t k = 0; k < r.nodes.size(); ++k) {
            const bool same = r.nodes[k].x == u.nodes[k].x
                           && r.nodes[k].y == u.nodes[k].y;
            if (boundary[k]) { if (same) ++frozen; else ++movedBoundary; }
            else if (!same) ++movedInterior;
        }
        CHECK(movedBoundary == 0,
              "41. every node on ANY block boundary is frozen — walls, bound edges, "
              "interfaces and the wake cut alike (" + std::to_string(movedBoundary)
              + " moved of " + std::to_string(frozen + movedBoundary) + ")");
        CHECK(movedInterior > 0,
              "41. ...and interior nodes really did move, so the check above is not "
              "passing on a mesh nothing touched (" + std::to_string(movedInterior)
              + " moved)");
        // Node IDENTITY is what welding rests on: the smoother writes coordinates
        // and allocates nothing, so a shared node is still ONE node.
        CHECK(r.nodes.size() == u.nodes.size(),
              "41. smoothing allocates no node and drops none");
        bool cellsSame = r.cells.size() == u.cells.size();
        for (size_t k = 0; cellsSame && k < r.cells.size(); ++k)
            cellsSame = r.cells[k].nodeIds == u.cells[k].nodeIds
                     && r.cells[k].block == u.cells[k].block;
        CHECK(cellsSame,
              "41. ...and no downstream reader can tell the two apart by SHAPE: the "
              "cells are the same ids in the same order, smoothed or not");
        bool edgesSame = r.boundaryEdges.size() == u.boundaryEdges.size();
        for (size_t k = 0; edgesSame && k < r.boundaryEdges.size(); ++k)
            edgesSame = r.boundaryEdges[k].v1 == u.boundaryEdges[k].v1
                     && r.boundaryEdges[k].v2 == u.boundaryEdges[k].v2
                     && r.boundaryEdges[k].bc == u.boundaryEdges[k].bc
                     && r.boundaryEdges[k].segId == u.boundaryEdges[k].segId;
        CHECK(edgesSame, "41. ...nor by the boundary edges, which carry the same "
                         "conditions off the same source segments");
    }

    // ── 42. the kernel IS Winslow, and is NOT the Laplacian it replaced ─────
    //
    // Pinned as arithmetic rather than as "something moved", because a check that
    // only knew the nodes had shifted could not tell a Winslow kernel from a
    // broken Laplacian one. Computed against `preSmoothNodes`, which is also the
    // Jacobi claim — a Gauss-Seidel sweep would read neighbours this sweep had
    // already written.
    //
    // BOTH HALVES. The seam's sweep is compared against an independently written
    // Winslow sweep AND against the mean-of-four kernel #81 shipped, which must
    // now be WRONG by a wide margin. #82's first acceptance criterion is that the
    // Laplacian keeps no user; the way that could go quietly wrong is a kernel
    // that still behaves like one, so the difference is asserted rather than
    // assumed.
    {
        MbParams p;
        p.smoothIters = 1;
        MbResult r = build(wallSquare(9, 7, "0.02"), p);
        CHECK(r.ok, "42. the graded wall block smooths (err: " + r.error + ")");
        // GUARDED, and the guard is not defensive habit: an injection that stopped
        // publishing `preSmoothNodes` made this loop index an EMPTY vector, and the
        // run died with SIGSEGV and printed no FAIL line at all — which a score
        // taken from the FAIL count reads as "the injection did nothing". Check 41
        // has already reported the missing list; this must report too, not crash.
        CHECK(r.preSmoothNodes.size() == r.nodes.size(),
              "42. ...publishing a 'before' list to compare the kernel against");
        const bool parallel = r.preSmoothNodes.size() == r.nodes.size();
        const std::vector<Point2D> want =
            parallel ? sweepByHand(r, r.preSmoothNodes) : std::vector<Point2D>();
        const std::vector<Point2D> lap =
            parallel ? laplacianByHand(r, r.preSmoothNodes) : std::vector<Point2D>();
        // 1e-15 absolute on a unit square: the kernel is a dozen additions and one
        // division, so the two ways of writing it differ by rounding alone.
        const double gap = worstMove(r.nodes, want);
        CHECK(gap >= 0.0 && gap < 1e-15,
              "42. every interior node lands where the WINSLOW update of its nine "
              "logical neighbours' PRE-SWEEP positions puts it (worst "
              + std::to_string(gap) + ")");
        const double vsLap = worstMove(r.nodes, lap);
        CHECK(vsLap > 1e-6,
              "42. ...and NOT where the mean of its four neighbours would (worst "
              + std::to_string(vsLap) + ") — the Laplacian #81 shipped is gone, not "
              "hiding behind the same parameter");
    }

    // ── 43. N sweeps are N applications of that kernel, in Jacobi order ──────
    //
    // The property that makes the answer independent of the order the blocks and
    // the (i, j) pairs are visited, which a Gauss-Seidel loop would quietly take
    // away. Two sweeps are compared against the kernel applied twice by hand from
    // the same start, and the one-sweep result is checked to DIFFER from it, so
    // the comparison cannot pass by both sides doing nothing.
    {
        MbParams one, two;
        one.smoothIters = 1;
        two.smoothIters = 2;
        MbResult r1 = build(wallSquare(9, 7, "0.02"), one);
        MbResult r2 = build(wallSquare(9, 7, "0.02"), two);
        CHECK(r1.ok && r2.ok, "43. one and two sweeps are both accepted");
        CHECK(worstMove(r2.preSmoothNodes, r1.preSmoothNodes) == 0.0,
              "43. both runs start from the same unsmoothed mesh");
        // Guarded for the reason check 42 records: `sweepByHand` indexes by node id,
        // and a missing 'before' list must be a FAIL line rather than a segfault.
        const std::vector<Point2D> byHand =
            r2.preSmoothNodes.size() == r2.nodes.size()
                ? sweepByHand(r2, sweepByHand(r2, r2.preSmoothNodes))
                : std::vector<Point2D>();
        const double gap = worstMove(r2.nodes, byHand);
        CHECK(gap >= 0.0 && gap < 1e-15,
              "43. two sweeps ARE the Jacobi Winslow kernel applied twice, with its "
              "metric coefficients re-read from the sweep's OWN starting positions "
              "(worst " + std::to_string(gap) + ")");
        CHECK(worstMove(r2.nodes, r1.nodes) > 1e-9,
              "43. ...and the second sweep really moved something, so the comparison "
              "above is not two identity operations agreeing");
    }

    // ── 44. a NEGATIVE sweep count is refused BY NAME, never clamped ─────────
    //
    // The refuse-never-clamp convention MESH_MODE and MB_SPLIT_RULE already state,
    // and here it is also what keeps the parameter's type honest: `smoothIters` is
    // a signed int precisely so this refusal can be written, since widening -1 to
    // an unsigned count is four billion sweeps — a hang, not a mesh.
    {
        MbParams bad;
        bad.smoothIters = -1;
        MbResult r = build(square(4, 3), bad);
        CHECK(!r.ok, "44. a negative sweep count is refused");
        CHECK(mentions(r.error, "MB_SMOOTH_ITERS"),
              "44. ...naming the key the user has to fix (got: " + r.error + ")");
        CHECK(r.nodes.empty() && r.cells.empty() && r.blocks.empty(),
              "44. ...and producing nothing");
    }

    // ── 45. THE WALL FIRST CELL IS STILL WORSE, and that is #83's job ───────
    //
    // Winslow drives the interior toward the harmonic map of the block, which has
    // no memory of the first-cell height the declaration asked for — so on a
    // wall-clustered block it still drags the first interior line away from the
    // wall. #82 says so in as many words: the control functions that hold the wall
    // spacing are ticket 3, and by how much it misses in the meantime is to be
    // recorded rather than glossed. Asserted as a DIRECTION with a floor, not as a
    // fixed number: the numbers belong to the shipped cases and are recorded in the
    // surface gate and the design note. What is pinned here is that the regression
    // is real and is not a rounding wobble — and that the seam's own `wallSpecs`
    // still asks for the declared height, so the quality report will SEE the miss
    // rather than move the target with it.
    {
        MbParams p;
        p.smoothIters = 4;
        MbResult u = build(wallSquare(9, 7, "0.02"));
        MbResult r = build(wallSquare(9, 7, "0.02"), p);
        CHECK(u.ok && r.ok, "45. the graded wall block is accepted both ways");
        const auto& bu = u.blocks[0];
        const auto& br = r.blocks[0];
        // The first interval off the SOUTH side, one grid line in from the corner
        // so the node above it is an interior node the sweep may move.
        const double before = (nodeOf(u, bu, 4, 1) - nodeOf(u, bu, 4, 0)).length();
        const double after  = (nodeOf(r, br, 4, 1) - nodeOf(r, br, 4, 0)).length();
        CHECK(after > before * 1.5,
              "45. the first cell off the wall gets TALLER under this kernel too — "
              "the cost #83's control functions are what remove (" + std::to_string(before)
              + " -> " + std::to_string(after) + ")");
        bool sameRequest = u.wallSpecs.size() == r.wallSpecs.size();
        for (size_t k = 0; sameRequest && k < r.wallSpecs.size(); ++k)
            sameRequest = r.wallSpecs[k].edgeId == u.wallSpecs[k].edgeId
                       && r.wallSpecs[k].side == u.wallSpecs[k].side
                       && r.wallSpecs[k].requestedLo == u.wallSpecs[k].requestedLo
                       && r.wallSpecs[k].requestedHi == u.wallSpecs[k].requestedHi;
        CHECK(sameRequest,
              "45. ...while the published REQUEST is unchanged, so the miss is "
              "measured against the declaration rather than against the mesh that "
              "drifted away from it");
    }

    // ── 46. the smoother can STILL fold a cell, on a mesh that started sound ─
    //
    // Not a new failure mode and deliberately not a new exit code: a smoothing pass
    // that folds a cell is a valid declaration whose interior came out folded, which
    // is exactly what the inverted-cell code already means. What this pins is that
    // the fold is REACHABLE from this parameter alone; the counting and the exit
    // code are one level up, in `measureMbQuality` and the adapter.
    //
    // THE FIXTURE HAD TO GET HARDER, and that is the measurement (#82). Under #81's
    // Laplacian this same C-grid folded 26 cells at 60 sweeps. Under Winslow it
    // folds NOTHING at any sweep count — 905 sweeps to convergence, zero flipped —
    // so the fixture now asks for a wall first cell of 0.0005 rather than 0.002.
    // Check 50 is the other half of that finding, and the reason it is worth
    // writing down: the elliptic kernel does not merely avoid folding, it UNFOLDS
    // what the algebraic fill folded.
    //
    // The dart from tests/cpp/test_mb_quality.cpp's fixture is deliberately NOT
    // reused: this mesh starts SOUND, so the fold is the smoother's doing and not
    // the fill's — which is the whole claim, and the reason the unsmoothed run is
    // checked to have no flipped quad at all.
    //
    // The winding of a structured quad, computed here rather than by asking
    // `measureMbQuality`: this file drives `buildMultiBlock` and nothing else, and a
    // shoelace sign is a weaker statement than the ruler's per-corner rule — a
    // flipped quad is inverted under both, so the direction of the implication is
    // the right way round for the claim being made.
    {
        auto flipped = [](const MbResult& r) {
            size_t n = 0;
            for (const auto& b : r.blocks)
                for (int j = 0; j + 1 < b.nj; ++j)
                    for (int i = 0; i + 1 < b.ni; ++i) {
                        const Point2D p00 = nodeOf(r, b, i, j), p10 = nodeOf(r, b, i + 1, j);
                        const Point2D p11 = nodeOf(r, b, i + 1, j + 1),
                                      p01 = nodeOf(r, b, i, j + 1);
                        const double a2 = (p10 - p00).cross(p11 - p00)
                                        + (p11 - p00).cross(p01 - p00);
                        if (a2 <= 0.0) ++n;
                    }
            return n;
        };
        MbParams p;
        p.smoothIters = 100000;
        const std::string doc = cgridClustered("0.0005");
        MbResult u = hybmesh::buildMultiBlock(doc, cgridGeoms(), MbParams{});
        MbResult r = hybmesh::buildMultiBlock(doc, cgridGeoms(), p);
        CHECK(u.ok && r.ok, "46. a heavily smoothed C-grid is still a valid "
                            "declaration and still returns a mesh (err: " + r.error + ")");
        CHECK(flipped(u) == 0,
              "46. the unsmoothed C-grid folds NOTHING, so the count below belongs to "
              "the smoother (got " + std::to_string(flipped(u)) + ")");
        CHECK(flipped(r) > 0,
              "46. ...and a wall this finely clustered DOES fold structured cells — "
              "reachable from this parameter alone, with no help from a bad "
              "declaration (got " + std::to_string(flipped(r)) + ")");
        CHECK(r.preSmoothNodes.size() == r.nodes.size(),
              "46. ...with its before/after pair intact, so the damage is reportable");
    }

    // ── 47. A GRID THE ANSWER IS KNOWN FOR comes back UNMOVED ───────────────
    //
    // #82's exactness gate. A uniformly spaced grid on a stretched rectangle puts
    // node (i, j) at a map that is LINEAR in i and in j, so every second
    // difference in the elliptic operator — x_ii, x_jj and the cross term x_ij —
    // is exactly zero and the grid is a fixed point of the solve. It must come
    // back not merely close but IDENTICAL, and the solve must SAY it converged
    // rather than run its cap out on a grid it is not moving.
    //
    // WHAT THIS CAN AND CANNOT CATCH, said plainly because the criterion invites
    // the stronger reading. Because every second difference vanishes, the residual
    // is zero for ANY values of the metric coefficients: a swapped alpha/gamma or a
    // dropped beta passes here untouched. This gate catches the denominator, the
    // neighbour indices and any term that does not cancel — the arithmetic of the
    // coefficients themselves is check 48's job, against hand numbers. Two gates,
    // because one of them cannot be both.
    //
    // AND THE TICKET'S PREMISE IS CORRECTED HERE, measured rather than argued.
    // #82 says "a stretched rectangle is smooth already, so the solve must return
    // it unmoved". That is true of a rectangle STRETCHED IN ASPECT and false of one
    // GRADED in its spacing: plain Winslow's fixed point is the harmonic map, whose
    // interior spacing is uniform, so a graded rectangle is NOT returned unmoved and
    // cannot be. That is not a defect of this kernel — it is exactly why #80 has a
    // ticket 3 for control functions — but it is the difference between a gate that
    // holds and a gate that was never true.
    {
        // 250:1, the stretching #80 names on the grids this path makes.
        const std::string doc = stretchedBox(11, 9, "250.0", "1.0");
        MbParams none, many;
        many.smoothIters = 500;
        MbResult u = build(doc, none);
        MbResult r = build(doc, many);
        CHECK(u.ok && r.ok, "47. the stretched box meshes both ways (err: "
                            + u.error + " / " + r.error + ")");
        // 1e-12 on a domain 250 units across, i.e. 4e-15 relative — measured at
        // 2.8e-14 absolute, which is the transfinite fill's own rounding and not
        // the solve's: the fill lands its nodes within an ulp or two of the linear
        // map, and the solve holds them there. Bit equality is the wrong assertion
        // for that reason and not because the tolerance is generous.
        const double held = worstMove(r.nodes, u.nodes);
        CHECK(held >= 0.0 && held < 1e-12,
              "47. a uniform grid on a 250:1 rectangle is a FIXED POINT of the "
              "elliptic solve — returned unmoved to far better than solver "
              "tolerance (worst " + std::to_string(held) + ")");
        CHECK(r.smoothConverged && r.smoothSweeps == 1 && r.smoothResidual < 1e-14,
              "47. ...and the solve SAYS so on its first sweep instead of spending "
              "its cap (sweeps " + std::to_string(r.smoothSweeps) + ", converged "
              + std::to_string(r.smoothConverged) + ", residual "
              + std::to_string(r.smoothResidual) + ")");
        CHECK(!r.smoothDiverged && smoothWarnings(r).empty(),
              "47. ...with nothing to warn about");
        // The premise correction, as a measurement: the same rectangle GRADED is
        // moved, and the fixed point it is moving toward is not where it started.
        MbResult g0 = build(wallSquare(11, 9, "0.02"), none);
        MbResult g1 = build(wallSquare(11, 9, "0.02"), many);
        CHECK(g0.ok && g1.ok, "47. the graded box meshes both ways");
        CHECK(worstMove(g1.nodes, g0.nodes) > 1e-6,
              "47. a GRADED rectangle is NOT a fixed point — plain Winslow relaxes "
              "toward the harmonic map, whose interior spacing is uniform, so the "
              "grading moves (worst " + std::to_string(worstMove(g1.nodes, g0.nodes))
              + "). Holding it is #80's ticket 3, not this kernel.");
    }

    // ── 48. THE COEFFICIENTS, against numbers derived by hand ───────────────
    //
    // The gate a wrong metric term cannot pass, which check 47 by construction
    // cannot be. One stencil, nine positions chosen so that alpha, beta, gamma and
    // the cross derivative are all non-zero and all DIFFERENT, worked through on
    // paper:
    //
    //   x_i = (iPlus - iMinus)/2 = ((4,2) - (0,0))/2 = (2, 1)
    //   x_j = (jPlus - jMinus)/2 = ((2,6) - (0,0))/2 = (1, 3)
    //   alpha = x_j . x_j = 1 + 9  = 10
    //   beta  = x_i . x_j = 2 + 3  =  5
    //   gamma = x_i . x_i = 4 + 1  =  5
    //   x_ij  = (pp - mp - pm + mm)/4
    //         = ((5,8) - (-1,5) - (3,-3) + (0,0))/4 = (3, 6)/4 = (0.75, 1.5)
    //   denom = 2(alpha + gamma) = 30
    //   answer = [alpha*(iPlus + iMinus) + gamma*(jPlus + jMinus) - 2*beta*x_ij] / denom
    //          = [10*(4,2) + 5*(2,6) - 10*(0.75,1.5)] / 30
    //          = [(40,20) + (10,30) - (7.5,15)] / 30 = (42.5, 35)/30
    //
    // `c` is (7, 9) — nowhere near the answer — because the update must not read
    // the node it is moving. A kernel that blended the old position in would land
    // somewhere else entirely.
    //
    // AND THE CHECK IS SHOWN TO DISCRIMINATE, which is the half that makes it worth
    // having: the four ways this arithmetic is usually got wrong are each computed
    // beside it and each lands somewhere else. A gate whose passing value is also
    // the wrong answer's value is not a gate.
    {
        hybmesh::MbWinslowStencil st;
        st.c      = Point2D{7.0, 9.0};
        st.iPlus  = Point2D{4.0, 2.0};
        st.iMinus = Point2D{0.0, 0.0};
        st.jPlus  = Point2D{2.0, 6.0};
        st.jMinus = Point2D{0.0, 0.0};
        st.pp     = Point2D{5.0, 8.0};
        st.mp     = Point2D{-1.0, 5.0};
        st.pm     = Point2D{3.0, -3.0};
        st.mm     = Point2D{0.0, 0.0};
        const Point2D got = hybmesh::mbWinslowUpdate(st);
        const Point2D want{42.5 / 30.0, 35.0 / 30.0};
        CHECK((got - want).length() < 1e-15,
              "48. the Winslow update of a hand-worked stencil is (" 
              + std::to_string(want.x) + ", " + std::to_string(want.y) + "), got ("
              + std::to_string(got.x) + ", " + std::to_string(got.y) + ")");
        // alpha = 10, beta = 5, gamma = 5, cross = (0.75, 1.5), denom = 30.
        const Point2D sumI{4.0, 2.0}, sumJ{2.0, 6.0}, cross{0.75, 1.5};
        struct Wrong { const char* how; Point2D at; };
        const Wrong wrong[] = {
            {"alpha and gamma swapped",
             (sumI * 5.0 + sumJ * 10.0 - cross * 10.0) * (1.0 / 30.0)},
            {"the cross term dropped",
             (sumI * 10.0 + sumJ * 5.0) * (1.0 / 30.0)},
            {"the cross term's sign flipped",
             (sumI * 10.0 + sumJ * 5.0 + cross * 10.0) * (1.0 / 30.0)},
            {"the mean of the four neighbours (the kernel #81 shipped)",
             (st.iPlus + st.iMinus + st.jPlus + st.jMinus) * 0.25},
        };
        for (const Wrong& w : wrong)
            CHECK((want - w.at).length() > 0.05,
                  std::string("48. ...and this stencil TELLS THAT APART from ") + w.how
                  + " (" + std::to_string((want - w.at).length()) + " away)");
        // The degenerate branch, so it is a decision rather than an accident: four
        // coincident neighbours have no metric at all, and the node stays put.
        hybmesh::MbWinslowStencil flat;
        flat.c = Point2D{3.0, -4.0};
        const Point2D held = hybmesh::mbWinslowUpdate(flat);
        CHECK(held.x == 3.0 && held.y == -4.0,
              "48. a stencil with no metric at all leaves the node WHERE IT IS "
              "rather than returning a NaN every later sweep would spread");
    }

    // ── 49. THE SOLVE IS BOUNDED, AND SAYS WHICH OF THE THREE ENDINGS ───────
    //
    // #82: "a solve that does not converge says so and is not silently truncated
    // into a result that looks finished." There are three endings and they are
    // three different answers, so the seam publishes both flags rather than one:
    //
    //   converged  — the residual reached MB_SMOOTH_TOL and the solve stopped
    //                early, so `smoothSweeps` is BELOW the cap.
    //   capped     — still moving at the cap. A warning names the number to raise.
    //   diverged   — the residual climbed back through
    //                MB_SMOOTH_DIVERGE_FACTOR times its best, so the mesh returned
    //                is the BEST iterate and its sweep number, not the last one.
    //
    // The graded box converges, and the same box at a cap of one does not.
    //
    // THE THIRD ENDING IS NOT DRIVEN HERE, and that is a gap with a reason rather
    // than an oversight. Divergence was found on the SHIPPED C-grid — the residual
    // falls to 2.7e-08 by sweep 3724 and then grows — and no synthetic fixture in
    // this file reproduces it: measured 2026-09-04 over 26 variants (the clustered
    // C-grid at four wall spacings and two wall resolutions, and a non-convex dart
    // at three shapes x three gradings x two resolutions), every one of which
    // CONVERGED. So `tests/test_multiblock_smooth_surface.py` group 7 is the only
    // gate on `smoothDiverged` and on the rollback, and it drives the real file.
    {
        MbParams cap1, big;
        cap1.smoothIters = 1;
        big.smoothIters = 100000;
        MbResult r1 = build(wallSquare(9, 7, "0.02"), cap1);
        MbResult rc = build(wallSquare(9, 7, "0.02"), big);
        CHECK(r1.ok && rc.ok, "49. the graded box meshes at both caps");
        CHECK(!r1.smoothConverged && !r1.smoothDiverged && r1.smoothSweeps == 1
                  && r1.smoothResidual > 0.0,
              "49. a cap of one is a solve that has NOT converged, and says so "
              "(sweeps " + std::to_string(r1.smoothSweeps) + ", residual "
              + std::to_string(r1.smoothResidual) + ")");
        const std::vector<std::string> w1 = smoothWarnings(r1);
        CHECK(w1.size() == 1 && mentions(w1.empty() ? "" : w1[0], "MB_SMOOTH_ITERS"),
              "49. ...with ONE warning naming the key to raise, so a truncated "
              "solve cannot read as a finished one");
        CHECK(rc.smoothConverged && rc.smoothSweeps < big.smoothIters
                  && rc.smoothResidual <= hybmesh::MB_SMOOTH_TOL,
              "49. ...while a cap it does not need is left unspent: the solve stops "
              "the sweep it converges on (sweeps " + std::to_string(rc.smoothSweeps)
              + " of " + std::to_string(big.smoothIters) + ", residual "
              + std::to_string(rc.smoothResidual) + ")");
        CHECK(smoothWarnings(rc).empty(),
              "49. ...and a converged solve warns about nothing");
        // A run at exactly the sweep count the converged one used must land on the
        // same mesh: the early stop is a stop, not a different answer.
        MbParams exact;
        exact.smoothIters = rc.smoothSweeps;
        MbResult re = build(wallSquare(9, 7, "0.02"), exact);
        CHECK(worstMove(re.nodes, rc.nodes) == 0.0,
              "49. ...and stopping early returns the SAME mesh the cap would have, "
              "bit for bit");
    }

    // ── 50. AND IT UNFOLDS WHAT THE ALGEBRAIC FILL FOLDED ───────────────────
    //
    // The other half of check 46's finding, and the one that says what changed
    // between #81's kernel and this one. A plain Laplacian folds sound meshes; the
    // elliptic solve REPAIRS folded ones. On a block with a re-entrant corner the
    // transfinite fill lays 13 folded quads across the notch — a valid declaration
    // with a broken interior — and the solve converges to a mesh with none.
    //
    // Not a claim about all folds: check 46 has a clustered C-grid this same solve
    // folds. What is pinned here is the direction on a case where the fill is the
    // thing that is wrong, and that #81's kernel does NOT do it — the Laplacian is
    // run by hand from the same start for exactly that comparison, because "the new
    // kernel is better" is otherwise a sentence rather than a measurement.
    {
        auto flipped = [](const MbResult& r, const std::vector<Point2D>& at) {
            size_t n = 0;
            for (const auto& b : r.blocks)
                for (int j = 0; j + 1 < b.nj; ++j)
                    for (int i = 0; i + 1 < b.ni; ++i) {
                        const Point2D p00 = at[static_cast<size_t>(b.nodeAt(i, j))],
                                      p10 = at[static_cast<size_t>(b.nodeAt(i + 1, j))],
                                      p11 = at[static_cast<size_t>(b.nodeAt(i + 1, j + 1))],
                                      p01 = at[static_cast<size_t>(b.nodeAt(i, j + 1))];
                        const double a2 = (p10 - p00).cross(p11 - p00)
                                        + (p11 - p00).cross(p01 - p00);
                        if (a2 <= 0.0) ++n;
                    }
            return n;
        };
        MbParams big;
        big.smoothIters = 100000;
        const std::string doc = notchedBox(11, 9, "0.35");
        MbResult u = build(doc, MbParams{});
        MbResult r = build(doc, big);
        CHECK(u.ok && r.ok, "50. the notched block is a VALID declaration both ways "
                            "(err: " + u.error + " / " + r.error + ")");
        const size_t before = flipped(u, u.nodes);
        CHECK(before > 0,
              "50. the transfinite fill FOLDS cells across the notch, with nothing "
              "wrong with the document (got " + std::to_string(before) + ")");
        CHECK(r.smoothConverged,
              "50. ...the elliptic solve converges on it (sweeps "
              + std::to_string(r.smoothSweeps) + ", residual "
              + std::to_string(r.smoothResidual) + ")");
        CHECK(flipped(r, r.nodes) == 0,
              "50. ...and REPAIRS every one of them (got "
              + std::to_string(flipped(r, r.nodes)) + " of "
              + std::to_string(before) + " left)");
        // The same start, the same sweep count, #81's kernel: it does not.
        std::vector<Point2D> lap = u.nodes;
        for (int k = 0; k < r.smoothSweeps; ++k) lap = laplacianByHand(u, lap);
        CHECK(flipped(u, lap) > 0,
              "50. ...where the mean-of-four kernel #82 deleted does NOT, from the "
              "same mesh and the same number of sweeps (got "
              + std::to_string(flipped(u, lap)) + " left of "
              + std::to_string(before) + ")");
    }

    return hybmesh::test::report("test_multiblock");
}
