#pragma once

namespace hybmesh {

/// Fraction of the LOCAL point spacing within which two points count as the same point.
///
/// Both binaries must agree on this number and they are compiled separately, which is
/// why it lives in a header rather than as a literal in each: the resampler welds a
/// closed loop's seam when its two ends are within this fraction of the neighbouring
/// spacing (tools/PreProcessor/src/main.cpp), drops a feature corner that lands this
/// close to an endpoint sample it cannot snap to (same file), and the mesher pops the
/// duplicate under the same fraction (src/main.cpp::loadGeometry).
///
/// Tighten one of those alone and a gap band reopens between them: the resampler leaves
/// a sliver edge that the mesher no longer recognises as a seam. Measured, that sliver
/// was 3.8e-5 against a 0.05 neighbour — 1300x shorter — and it makes the outline
/// self-intersect at the seam, so the boundary layer collides with itself there and Gmsh
/// can spin indefinitely triangulating around it.
///
/// It is deliberately RELATIVE. A fixed tolerance cannot do this job: the same geometry
/// at another scale has a different "hair", which is how 1e-6 missed this one entirely.
inline constexpr double POINT_COINCIDENCE_FRACTION = 0.05;

}  // namespace hybmesh
