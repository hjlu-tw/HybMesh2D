"""The structural rules the mesher refuses a topology document for, checked ONCE.

Not a gate — a helper two gates call (``test_topology_templates.py`` for the H-grid,
``test_topology_ogrid.py`` for the O-grid), so that "what must every family's output
satisfy" is one statement rather than one per family. #133's testing decision is that
EVERY family function is tested against these invariants over a spread of parameters;
a second copy of them is a copy that can come to disagree, and the family it disagreed
about would be the one that shipped a refusal.

Each function takes ``(why, doc)`` and returns a list of COMPLAINT strings — empty
when the document satisfies the rule. Returning rather than asserting is what lets a
caller run one invariant across a whole spread and report every failure in one line,
which is the shape both gates already had.

Every rule here is a named refusal in ``src/MultiBlock.cpp`` and a bullet in
``.claude/rules/mesher-multiblock.md``. A template that can produce one has handed the
user back the JSON they came to avoid.
"""
from __future__ import annotations

import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))


class _UF:
    """Union-find, for deriving the count equivalence classes independently."""

    def __init__(self):
        self.p = {}

    def find(self, a):
        self.p.setdefault(a, a)
        while self.p[a] != a:
            self.p[a] = self.p[self.p[a]]
            a = self.p[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def unique_ids(why, doc) -> list:
    """Every corner, edge and block id is unique within its family."""
    bad = []
    for kind in ("corners", "edges", "blocks"):
        ids = [x["id"] for x in doc[kind]]
        if len(ids) != len(set(ids)):
            bad.append(f"{why}: duplicate {kind} id")
    return bad


def ring_closes(why, doc) -> list:
    """Each block's four edges close a ring, by THE MESHER'S OWN RULE.

    Walked BY DIRECTION, not as a set: a block whose east and west are swapped still
    names the same four edges, so a set comparison passes it while the mesher refuses
    it (injection A of the H-grid gate).

    THE RULE IS `resolveBlockFrames`'s, MIRRORED — and this used to be STRICTER than
    it, which #148 found by measuring the shipped, working, hand-written
    ``examples/topology/cgrid_naca0012.json`` against it and getting one complaint.
    The mesher fixes the block's i direction from the SOUTH edge's own declared
    direction and then allows the other three to be declared EITHER WAY, traversing
    each in whichever direction closes the ring. It has to: a shared edge is ONE edge
    with ONE direction named by two blocks whose logical frames need not agree about
    it, and a C-grid's wake cut is the WEST of both wake blocks — so no single
    declaration of it can satisfy a rule that pins west to one direction, and no
    C-grid could ever pass the version of this check that did.

    Nothing is inferred by the relaxation, which is the mesher's own argument: the
    frame is still fixed entirely by the south edge plus which corners the other
    three touch. A set of four edges that does not close is still a complaint, and so
    is a ring that closes onto fewer than four distinct corners — the mesher refuses
    that too, and it is reachable (two distinct edges over one corner pair make the
    block's j-max corner its own i-max corner, and there is no interior to fill).
    """
    by_id = {e["id"]: e for e in doc["edges"]}
    bad = []
    for b in doc["blocks"]:
        if len(b["edges"]) != 4 or any(i not in by_id for i in b["edges"]):
            bad.append(f"{why}/{b['id']}: does not name four known edges")
            continue
        s, e, n, w = (by_id[i]["corners"] for i in b["edges"])
        a, bb = s                       # the south edge fixes the i direction
        d = _other_end(w, a)            # west meets south at the i-min/j-min corner
        c = _other_end(e, bb)           # east meets south at i-max/j-min
        if d is None or c is None or sorted(n) != sorted([d, c]):
            bad.append(f"{why}/{b['id']}")
            continue
        if len({a, bb, c, d}) != 4:
            bad.append(f"{why}/{b['id']}: closes onto {len({a, bb, c, d})} corners")
    return bad


def _other_end(edge_corners, at):
    """The far end of ``edge_corners`` given that one of its ends is ``at``.

    ``None`` when neither end is — which is the mesher's ``ringFail``: "its <side>
    edge must have an end at corner '<at>'".
    """
    x, y = edge_corners
    if x == at:
        return y
    if y == at:
        return x
    return None


def legal_counts(why, doc) -> list:
    """Every declared count is an integer >= 2 — the mesher's floor, its two ends."""
    return [f"{why}/{e['id']}={e['count']}" for e in doc["edges"]
            if "count" in e and (not isinstance(e["count"], int)
                                 or isinstance(e["count"], bool) or e["count"] < 2)]


def count_classes(doc) -> list:
    """The count equivalence classes of ``doc``, as lists of edge ids.

    Derived from the mesher's two propagation rules — opposite sides of a block
    carry equal counts, and a shared edge is one edge two blocks name — rather than
    from any builder's idea of them. Its own function since #155, whose family
    declares TWO radial classes where the O-grid declares one and has to assert that
    they really are two; a gate deriving them a second way would be free to agree
    with the builder and disagree with the mesher.
    """
    uf = _UF()
    for e in doc["edges"]:
        uf.find(e["id"])
    for b in doc["blocks"]:
        if len(b["edges"]) != 4:
            continue
        s, e, n, w = b["edges"]
        uf.union(s, n)
        uf.union(e, w)
    cls = {}
    for e in doc["edges"]:
        cls.setdefault(uf.find(e["id"]), []).append(e["id"])
    return list(cls.values())


def one_seed_per_class(why, doc) -> list:
    """Exactly one count seed per equivalence class."""
    by_id = {e["id"]: e for e in doc["edges"]}
    cls = {k: v for k, v in enumerate(count_classes(doc))}
    bad = []
    for members in cls.values():
        seeds = [m for m in members if "count" in by_id[m]]
        if len(seeds) != 1:
            bad.append(f"{why}: class {sorted(members)} has {len(seeds)} seed(s)")
    return bad


def kind_usage(why, doc) -> list:
    """A ``wall`` bounds exactly one block side; an interior line exactly two."""
    uses = {e["id"]: 0 for e in doc["edges"]}
    for b in doc["blocks"]:
        for eid in b["edges"]:
            if eid in uses:
                uses[eid] += 1
    bad = []
    for e in doc["edges"]:
        want = 1 if e["kind"] == "wall" else 2
        if uses[e["id"]] != want:
            bad.append(f"{why}/{e['id']} kind={e['kind']} used {uses[e['id']]}x")
    return bad


def nothing_orphaned(why, doc) -> list:
    """No corner lies on no edge, and no edge lies in no block."""
    on_edge = {c for e in doc["edges"] for c in e["corners"]}
    in_block = {eid for b in doc["blocks"] for eid in b["edges"]}
    orphan_c = [c["id"] for c in doc["corners"] if c["id"] not in on_edge]
    orphan_e = [e["id"] for e in doc["edges"] if e["id"] not in in_block]
    return ([f"{why}: corners {orphan_c}, edges {orphan_e}"]
            if (orphan_c or orphan_e) else [])


# ── the mesher's own schema, READ OUT OF THE C++ ────────────────────────────

_MB_SRC = open(os.path.join(_REPO, "src", "MultiBlock.cpp"), encoding="utf-8").read()


def _key_sets() -> list:
    """Every ``rejectUnknownKeys`` key set in the parser, as a list of sets."""
    out = []
    for m in re.finditer(r"rejectUnknownKeys\(([^;]*?)\{([^}]*)\}", _MB_SRC, re.S):
        ks = set(re.findall(r'"([^"]+)"', m.group(2)))
        if ks:
            out.append(ks)
    return out


_SETS = _key_sets()


def schema_keys(marker: str):
    """The key set containing ``marker``, or None if it is not EXACTLY one.

    Selected by a marker key rather than by the call's ``where`` argument, which is a
    runtime-built variable at most call sites and so is not in the source to match on.
    Returning None on an ambiguous or absent marker is what stops this answering on
    input it did not understand (#116); the callers check for it rather than letting
    a vacuous pass stand in for a measurement.
    """
    hits = [s for s in _SETS if marker in s]
    return hits[0] if len(hits) == 1 else None


#: The five sets, by the marker that selects each. ``None`` for any of them means the
#: derivation failed and the caller must fail rather than check nothing.
SCHEMA = {
    "corner": schema_keys("xy"),
    "edge": schema_keys("binding"),
    "block": schema_keys("orientation"),
    "doc": schema_keys("format_version"),
    "spacing": schema_keys("law"),
}


def schema_readable() -> bool:
    return all(SCHEMA.values())


def no_unknown_keys(why, doc) -> list:
    """Every emitted key is one the mesher's schema accepts."""
    if not schema_readable():
        return [f"{why}: the schema could not be read out of src/MultiBlock.cpp"]
    bad = []
    bad += [f"{why}: document key '{k}'" for k in doc if k not in SCHEMA["doc"]]
    for c in doc["corners"]:
        bad += [f"{why}: corner key '{k}'" for k in c if k not in SCHEMA["corner"]]
    for e in doc["edges"]:
        bad += [f"{why}: edge key '{k}'" for k in e if k not in SCHEMA["edge"]]
        bad += [f"{why}: spacing key '{k}'"
                for k in e.get("spacing", {}) if k not in SCHEMA["spacing"]]
    for b in doc["blocks"]:
        bad += [f"{why}: block key '{k}'" for k in b if k not in SCHEMA["block"]]
    return sorted(set(bad))
