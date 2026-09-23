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
    """Each block's four edges close a ring in ``[south, east, north, west]``.

    Walked BY DIRECTION, not as a set: a block whose east and west are swapped still
    names the same four edges, so a set comparison passes it while the mesher refuses
    it (injection A of the H-grid gate). South and north run i-min -> i-max, west and
    east run j-min -> j-max, so the ring is south -> east -> reversed north ->
    reversed west and must return to where it started.
    """
    by_id = {e["id"]: e for e in doc["edges"]}
    bad = []
    for b in doc["blocks"]:
        if len(b["edges"]) != 4 or any(i not in by_id for i in b["edges"]):
            bad.append(f"{why}/{b['id']}: does not name four known edges")
            continue
        s, e, n, w = (by_id[i]["corners"] for i in b["edges"])
        if not (s[1] == e[0] and e[1] == n[1] and n[0] == w[1] and w[0] == s[0]):
            bad.append(f"{why}/{b['id']}")
    return bad


def legal_counts(why, doc) -> list:
    """Every declared count is an integer >= 2 — the mesher's floor, its two ends."""
    return [f"{why}/{e['id']}={e['count']}" for e in doc["edges"]
            if "count" in e and (not isinstance(e["count"], int)
                                 or isinstance(e["count"], bool) or e["count"] < 2)]


def one_seed_per_class(why, doc) -> list:
    """Exactly one count seed per equivalence class.

    The classes are derived HERE from the mesher's two propagation rules — opposite
    sides of a block carry equal counts, and a shared edge is one edge two blocks
    name — rather than from any builder's idea of them.
    """
    by_id = {e["id"]: e for e in doc["edges"]}
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
    for eid in by_id:
        cls.setdefault(uf.find(eid), []).append(eid)
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
