// Mesh::recordBoundaryEdge / boundaryEdgeInfo — the paired write and paired read
// that carry a boundary edge's BC and its source segment as ONE fact.
//
// This test's other job is to prove the seam exists. It links hybmesh_core and
// calls Mesh directly; before the library target there was no way to do that at
// all, so the only way to exercise this pair was to generate a whole mesh and
// read the exported .bnd back. A unit test of a std::map round-trip is worth
// little on its own — what it pins down is the INVARIANT the interface was
// created for: the BC and the segment key are written together, refused
// together and read together, so no caller can produce an edge carrying half an
// identity (which the exporter silently turns into the wall default, and a wall
// where an inlet belongs reads as a converged solve of the wrong problem).
//
// Note what deliberately is NOT tested: that nobody bypasses the pair by
// touching the two maps directly. They are private, so the compiler rejects it —
// a test there would only be re-checking the language.
#include "check.hpp"

#include "Mesh.hpp"

namespace {

// A surface node as the resampler's sidecar would leave it: a BC label plus the
// (geomId, segId) that says which source segment it came from.
Node taggedNode(const char* bc, int geomId, int segId) {
    Node n{};
    n.type = NodeType::Boundary;
    n.bcTag = bc;
    n.geomId = geomId;
    n.segId = segId;
    return n;
}

}  // namespace

int main() {
    using hybmesh::test::report;

    Mesh m;
    m.addNode({0.0, 0.0}, NodeType::Boundary);   // 0
    m.addNode({1.0, 0.0}, NodeType::Boundary);   // 1
    m.addNode({2.0, 0.0}, NodeType::Boundary);   // 2

    // --- 1. an untagged source records nothing --------------------------------
    // Every node of a domain box or a BL front is untagged; recording from one
    // must not create an entry whose BC is empty but whose segment key is set.
    Node untagged{};
    untagged.geomId = 0;
    untagged.segId = 3;
    CHECK(m.recordBoundaryEdge(0, 1, untagged) == false,
          "an untagged source node records nothing");
    CHECK(!m.boundaryEdgeInfo(0, 1),
          "...and the edge reads back as carrying nothing");
    CHECK(m.boundaryEdgeInfo(0, 1).segKey == -1,
          "...leaving no segment key behind either");

    // --- 2. a tagged source records both halves -------------------------------
    CHECK(m.recordBoundaryEdge(0, 1, taggedNode("inlet", 2, 7)) == true,
          "a tagged source node records the edge");
    Mesh::EdgeBc rec = m.boundaryEdgeInfo(0, 1);
    CHECK(bool(rec), "the recorded edge reads back as carrying something");
    CHECK(rec.bc == "inlet", "the BC name survives the round trip");
    CHECK(rec.segKey == Mesh::makeSegKey(2, 7),
          "the source segment key survives WITH it");
    // Deliberately NOT asserting the literal encoding (it was `== 2000007`
    // here): how makeSegKey packs the pair is internal, and pinning it is the
    // "assert how it arrived there" the spec for this interface rules out. What
    // callers depend on is that distinct segments stay distinguishable.
    CHECK(Mesh::makeSegKey(2, 7) != Mesh::makeSegKey(7, 2),
          "the key distinguishes (geom 2, seg 7) from (geom 7, seg 2)");
    CHECK(Mesh::makeSegKey(2, 7) != Mesh::makeSegKey(2, 8),
          "...and two segments of one geometry from each other");

    // --- 3. the key is the unordered node pair --------------------------------
    // Callers reach the same edge from either owning cell, so (v1,v2) and
    // (v2,v1) must be one entry, not two.
    Mesh::EdgeBc flipped = m.boundaryEdgeInfo(1, 0);
    CHECK(flipped.bc == rec.bc && flipped.segKey == rec.segKey,
          "reading the edge back reversed gives the identical record");

    // --- 4. a refused overwrite must not half-apply ---------------------------
    // This is the case a case-1 slide column needs: it re-discretizes a stretch
    // of no-BL wall and must not restamp a real surface edge it happens to
    // touch. The refusal has to cover BOTH halves — a refusal that returns
    // false after having already written the segment key would leave the edge
    // claiming "inlet" while pointing at the outlet's segment.
    CHECK(m.recordBoundaryEdge(0, 1, taggedNode("outlet", 5, 1), false) == false,
          "overwrite=false refuses to replace an existing BC");
    Mesh::EdgeBc after = m.boundaryEdgeInfo(0, 1);
    CHECK(after.bc == "inlet", "...leaving the original BC in place");
    CHECK(after.segKey == Mesh::makeSegKey(2, 7),
          "...and the original segment key with it");

    // --- 5. an allowed overwrite replaces both halves -------------------------
    CHECK(m.recordBoundaryEdge(0, 1, taggedNode("outlet", 5, 1), true) == true,
          "overwrite=true replaces the record");
    Mesh::EdgeBc over = m.boundaryEdgeInfo(0, 1);
    CHECK(over.bc == "outlet", "...with the new BC");
    CHECK(over.segKey == Mesh::makeSegKey(5, 1),
          "...and the new segment key, not the old one");

    // --- 6. half an identity is legitimate, and must not suppress the BC ------
    // A custom domain outline is added with geomId = -1, so its nodes carry a
    // real BC and NO resolvable segment. makeSegKey reports -1 for that, and the
    // exporter falls back to grouping by name — but the BC itself must survive,
    // or every custom-domain patch exports as wall.
    CHECK(Mesh::makeSegKey(-1, 4) == -1,
          "an unknown geometry makes the segment key unknown");
    CHECK(Mesh::makeSegKey(0, -1) == -1,
          "an unknown segment does too");
    CHECK(m.recordBoundaryEdge(1, 2, taggedNode("symmetry", -1, -1)) == true,
          "a BC with no resolvable segment still records");
    Mesh::EdgeBc dom = m.boundaryEdgeInfo(1, 2);
    CHECK(dom.bc == "symmetry", "...and keeps its BC");
    CHECK(dom.segKey == -1, "...reporting the segment as unknown");

    // --- 7. an edge nobody recorded reads as nothing --------------------------
    CHECK(!m.boundaryEdgeInfo(0, 2),
          "an unrecorded edge carries nothing");
    CHECK(m.boundaryEdgeInfo(0, 2).bc.empty(),
          "...with an empty BC rather than a stale neighbour's");

    return report("test_mesh_boundary_edge");
}
