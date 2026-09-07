#ifndef MBCONTROL_HPP
#define MBCONTROL_HPP

#include "MultiBlock.hpp"

#include <cstddef>
#include <string>
#include <vector>

// The multi-block CONTROL FUNCTIONS (issue #83) — the source terms that tell the
// elliptic solve what a viscous wall is supposed to look like.
//
// WHY THIS EXISTS AT ALL. #82 put a Winslow solve behind the smoothing seam and
// measured what a converged one is: each block's harmonic map, which is as
// UNIFORM as its boundary allows. On the shipped C-grid that is 3133% off the
// declared first-cell height, and on the O-grid 1382%. An elliptic smoother with
// no source terms improves an angle by destroying a boundary layer, so #82's
// honest advice had to be "use a small cap" — a workaround for a missing input,
// not a setting. These are that input.
//
// TWO REQUIREMENTS, ONE VECTOR. At every station along a declared wall the
// declaration asks for two things: the grid line leaving the wall should leave it
// at 90 degrees, and its first cell should be the height the document asked for.
// Both are one statement about one vector — the step from the wall node to the
// node one grid line inward should be `requested * inward unit normal` — and
// `MbWallTarget` below is exactly that vector, per station. Nothing here trades
// one requirement against the other, because they are not two knobs.
//
// ITS OWN MODULE rather than more of `MultiBlock.cpp`, on the same grounds
// `MbQuality` is: a different question ("what should this wall look like?"
// against "what does this document declare?"), and a PURE FUNCTION of a finished
// fill — every function here takes node positions and gives numbers, so a check
// can drive it on a grid nobody parsed and compare against arithmetic worked by
// hand. `src/MultiBlock.cpp` is 2200 lines and the sweep loop is the one caller.
//
// It lives in `hybmesh_pure`, and the module name matters beyond taste: the rule
// file's globs cover `include/Mb*.hpp` and `src/Mb*.cpp` as PATTERNS, so a module
// named this way starts life with this path's rules attached, while a
// `MultiBlockControl.cpp` would have arrived ruleless.
namespace hybmesh {

// HOW A WALL'S CONTROL REACHES ACROSS A BLOCK: linearly in the NORMALIZED
// LOGICAL off-wall coordinate — full weight on the wall's own row, none on the
// row facing it, and the facing row's own control taking over as this one fades.
//
// LOGICAL and not physical, which is the point of solving in the computational
// domain at all: on a grid graded 250:1 the near-wall lines occupy almost no
// physical distance, so a weight measured in metres would spend its whole budget
// inside the first two cells and leave the rest of the boundary layer
// uncontrolled. In the logical coordinate every grid line gets an equal share.
//
// LINEAR AND NOT AN EXPONENTIAL DECAY, which this ticket tried first and dropped.
// A decay rate is a constant with no derivation behind it, and it leaves the row
// facing the wall driven by a fraction of the wall's demand rather than by its own
// — so the conflict between two frozen boundary distributions piles into the last
// cells before the far one instead of being shared out. The linear blend has no
// constant in it and reduces to "the wall's value, everywhere" when the wall is
// the only side asking, which is exactly what preserves a grading.

// One declared wall side of one block, as a TARGET: where the first grid line off
// it should end up, station by station.
//
// The gate for "is this a wall" is `MbResult::wallSpecs`, which is the seam's own
// published list of sides whose declared KIND is `wall`. It is not re-derived
// here and there is no second answer to that question: an interface or a cut is
// an interior line, is not in that list, and so is not driven toward anything.
// The same list is what `measureMbQuality` walks, which is what keeps the ruler
// and the control aimed at the same set of sides.
struct MbWallTarget {
    int block = -1;
    MbSide side = MB_SOUTH;
    std::string edgeId;
    // Per station along the side, in the side's own index order — `ni` entries for
    // a south/north wall, `nj` for a west/east one.
    //
    // `requested` IS THE RULER'S OWN BLEND and not a second interpolation of the
    // published spec. `MbWallSpec` carries the height at the side's two corners;
    // between them `measureMbQuality` blends LINEARLY IN THE LOGICAL COORDINATE,
    // and a control function aiming at any other interpolation — arc length along
    // the wall, chord between the corners — would be driving the mesh at one
    // number while the acceptance gate measured it against another. That is the
    // "second answer to the same question" the ticket forbids, and it is the same
    // trap the edge-distribution warning fell into the other way round: it
    // compared a CHORD against a request expressed in ARC LENGTH and fired on an
    // edge that had honoured the request exactly. The rule both times is that the
    // measure of the request and the measure of the achievement must be the same
    // measure — here, both are the logical blend of the two declared corners.
    std::vector<double> requested;
    // The INWARD unit normal at each station: perpendicular to the wall row's own
    // tangent, oriented by the current position of the node one line inward. The
    // orientation is read off the mesh rather than off the block's winding because
    // a frame may be turned a quarter turn (the H-grid case does exactly that) and
    // "inward" is then not a fixed side of the tangent.
    std::vector<Point2D> normal;
    // ZERO-LENGTH `requested` OR `normal` MEANS THE SIDE COULD NOT BE READ, not
    // that it asks for nothing: a side of fewer than three stations has no central
    // difference to take a tangent from, and a degenerate perpendicular edge
    // publishes a zero height. Such a side is still LISTED — a wall nothing could
    // be derived for is worth seeing — and contributes no source term.
    bool usable = false;
};

// Every declared wall side of a finished fill, as targets. Pure, total, never
// throws: a half-built result yields the targets it can and marks the rest
// unusable.
std::vector<MbWallTarget> mbWallTargets(const MbResult& mesh);

// One block's control field: the two source terms at every node of it.
struct MbControlField {
    int ni = 0, nj = 0;
    // ni*nj entries, index = j * ni + i, exactly like `MbBlock::nodeIds`.
    std::vector<MbControl> q;
    // HOW MANY NODES HAD A RAW SOURCE TERM CLIPPED to MB_CONTROL_CLIP. This is
    // the control function saying it could not honour its request in full, and it
    // is counted rather than swallowed: at the clip the wall condition is asking
    // for a push the kernel cannot take without losing its maximum principle, so
    // the mesh will land somewhere short of the target and the run has to be able
    // to say so.
    size_t clipped = 0;
    MbControl at(int i, int j) const {
        return q[static_cast<size_t>(j) * static_cast<size_t>(ni) + static_cast<size_t>(i)];
    }
};

// The control field of block `blockIdx`, from the CURRENT node positions.
//
// Recomputed every sweep, and that is not an optimisation left on the table: the
// wall condition is stated against the node one grid line inward, which is a node
// the solve is moving. Freezing the field after the first sweep would aim the
// control at a mesh that no longer exists — the whole point of the iteration is
// that the target and the mesh converge on each other.
//
// The targets for OTHER blocks are ignored; passing the whole list rather than
// pre-filtering keeps the caller from having to build one vector per block per
// sweep.
MbControlField mbControlField(const MbBlock& b, int blockIdx,
                              const std::vector<Point2D>& nodes,
                              const std::vector<MbWallTarget>& targets);

// WHAT THE PRODUCED MESH ACTUALLY DID against what one wall asked for.
//
// Measured on the nodes as they came out, never re-derived from the law and never
// predicted from the control values — a source term that was applied is not
// evidence that it worked, which is the whole reason this is a separate function
// from the field above.
//
// The height half is arithmetically the SAME quantity `measureMbQuality` reports
// as `MbWallHeight::worstRelError`, and it is computed here as well for a reason
// that is structural rather than sloppy: a warning belongs to the SEAM, and the
// seam cannot call the ruler — `MbQuality.hpp` includes `MultiBlock.hpp`, so the
// dependency only runs one way. The two are kept from drifting by a gate rather
// than by this comment: `tests/cpp/test_multiblock.cpp` compares them on the same
// mesh and fails if they disagree.
struct MbWallResidual {
    // max |achieved - requested| / requested over the side, or NEGATIVE when
    // nothing on it could be measured. Never 0.0 for "not measured", for the
    // reason `MbQualityReport` gives at length: 0.00% off is a superb result and
    // must not stand in for not knowing.
    double worstHeightRel = -1.0;
    // The largest deviation from 90 degrees, in degrees, of the first grid line
    // off the wall — the other half of the target vector, and the metric #80
    // exists for. NEGATIVE when unmeasurable, on the same rule.
    double worstAngleDeg = -1.0;
};

MbWallResidual mbWallResidual(const MbResult& mesh, const MbWallTarget& t);

}  // namespace hybmesh

#endif  // MBCONTROL_HPP
