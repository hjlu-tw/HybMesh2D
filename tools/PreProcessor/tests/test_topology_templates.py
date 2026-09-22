#!/usr/bin/env python3
"""The H-grid template: a pure function whose output the mesher cannot refuse
(issue #134, parent #133).

The template library exists so a user never types a block topology document. That
promise is only worth something if what the template produces is a document the
mesher ACCEPTS — so this gate holds the two halves of it:

  * the family function's output satisfies, ACROSS A SPREAD OF PARAMETERS, every
    structural rule the mesher refuses a document for. Each of those rules is a
    named refusal in ``src/MultiBlock.cpp`` and a bullet in
    ``.claude/rules/mesher-multiblock.md``; a template that can produce one has
    handed the user back the JSON they came here to avoid.
  * the DEFAULTS run the real binary to a zero exit code with zero inverted cells.
    A template that produces a document but not a mesh has done nothing, and the
    ticket's demo is "pick H-grid, accept the defaults, generate, see a mesh".

A SPREAD RATHER THAN ONE CASE, deliberately. The shipped hand-written H-grid is a
2x2; a 1x1 has no interior line at all, a 1xN has them in only one direction, and
a 4x3 has a block whose four neighbours are all interior. Every one of those is a
different branch of the interior/boundary test, and the 2x2 exercises none of them
on its own.

WHAT THIS FILE DOES NOT CHECK, because another gate owns it: that the parameters
the family reads are the ones the panel offers (``test_topology_param_specs.py``,
in both directions), and that the arithmetic of the shape metric it is measured by
is right (``tests/cpp/test_cell_shape.cpp``).

INJECTIONS: run by hand, 2026-09-22, each reverted and the file's checksum
compared against its pre-injection copy afterwards. Recorded here rather than
automated because the harness lived in a scratchpad. Six, all of which bit — and
TWO of them corrected the prediction written beside them, which is recorded rather
than tidied away:

  A. ``blocks`` emitted as ``[south, west, north, east]`` (the east/west pair
     swapped) -> check 2 red on ALL EIGHT spreads, not the "six" first written
     here — the spread had grown and the count was remembered rather than counted.
     The ring still CLOSES as a set, which is why check 2 walks the declared
     direction rather than the corner set. The real binary ALSO refuses it (exit
     8), so checks 14a-c go red too: a stronger bite than predicted.
  B. seed the count on every horizontal edge instead of only the bottom row ->
     check 4 red on EVERY spread, including the 1x1, which this note first
     predicted would stay green. It does not: even a 1x1 block has a south AND a
     north horizontal edge, and they are one class, so seeding both is two seeds.
     The prediction was reasoning about interior lines; the class is about
     OPPOSITE SIDES, which every block has.
  C. ``kind`` computed as ``0 < j <= ny`` (an off-by-one making the TOP row
     interior) -> check 5 red (an interface named by one block), and the real
     binary refuses (exit 8).
  D. drop the ``max(1, ...)`` in ``_cell_counts`` -> check 3 red on the spread
     whose cell target is larger than its block (count 1 < 2). This is the
     injection that showed the floor is load-bearing rather than defensive:
     without it the mesher's refusal is the user's first symptom.
  E. emit a stray ``"note"`` key on each edge -> check 6b red, AND the real binary
     refuses (exit 8) — check 7's negative control, done for real.
  F. NOT PLANNED, and it fired on its own: check 6a went red the first time this
     file ran, because the first draft selected each schema key set by the
     ``where`` argument of its ``rejectUnknownKeys`` call, which is a runtime-built
     variable at four of the five call sites and so is not in the source to match
     on. It reported ``corner=None, edge=None, block=None`` and check 6b passed
     VACUOUSLY beside it. That is the shape 6a exists for — a derivation that
     answers on input it did not understand is worse than no derivation — and it
     is why the selector is now a marker key and why 6a is a check rather than an
     assumption.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
sys.path.insert(0, _GUI)
sys.path.insert(0, _HERE)

from app.services import topology_hgrid, topology_model as tm  # noqa: E402

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


#: The spread. Each is a reason, not a number picked to fill a table.
SPREAD = [
    ("1x1 — no interior line at all",
     dict(hgrid_nx=1, hgrid_ny=1)),
    ("2x1 — interior lines in one direction only",
     dict(hgrid_nx=2, hgrid_ny=1)),
    ("1x3 — interior lines in the other direction only",
     dict(hgrid_nx=1, hgrid_ny=3)),
    ("2x2 — the shipped hand-written case's shape",
     dict(hgrid_nx=2, hgrid_ny=2)),
    ("4x3 — a block whose four sides are all interior",
     dict(hgrid_nx=4, hgrid_ny=3)),
    ("a cell target larger than the block, and no floor wall",
     dict(hgrid_nx=2, hgrid_ny=2, hgrid_cell=99.0, hgrid_wall_bottom=False)),
    ("overridden counts, one direction partly and one fully",
     dict(hgrid_nx=3, hgrid_ny=2, hgrid_counts_x="9,,4", hgrid_counts_y="3,7")),
    ("a negative-quadrant domain, so a span is not its own maximum",
     dict(hgrid_x_min=-4.0, hgrid_x_max=-1.0, hgrid_y_min=-2.5,
          hgrid_y_max=-0.5, hgrid_nx=3, hgrid_ny=2)),
]


def model(**kw):
    return tm.TopologyModel(family=topology_hgrid.FAMILY, **kw)


def docs():
    return [(why, tm.build_document(model(**kw))) for why, kw in SPREAD]


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


# ── 1. every id is unique ────────────────────────────────────────────────────
bad = []
for why, d in docs():
    for kind in ("corners", "edges", "blocks"):
        ids = [x["id"] for x in d[kind]]
        if len(ids) != len(set(ids)):
            bad.append(f"{why}: duplicate {kind} id")
check("1. every corner, edge and block id is unique, across the spread: "
      + (", ".join(bad) if bad else "none duplicated"), not bad)

# ── 2. the ring closes, counter-clockwise, in [south, east, north, west] ─────
# Walked by DIRECTION, not as a set: a block whose east and west are swapped
# still names the same four edges, so a set comparison would pass it (injection A).
bad = []
for why, d in docs():
    by_id = {e["id"]: e for e in d["edges"]}
    for b in d["blocks"]:
        s, e, n, w = (by_id[i]["corners"] for i in b["edges"])
        # south i-min->i-max, east j-min->j-max, north i-min->i-max,
        # west j-min->j-max. So the ring is south -> east -> reversed north ->
        # reversed west, and it must return to where it started.
        if not (s[1] == e[0] and e[1] == n[1] and n[0] == w[1] and w[0] == s[0]):
            bad.append(f"{why}/{b['id']}")
check("2. every block's four edges close a ring in [south, east, north, west] "
      "with south/north running i-min->i-max and west/east j-min->j-max: "
      + (", ".join(bad) if bad else "all closed"), not bad)

# ── 3. every declared count is a legal node count ───────────────────────────
bad = [f"{why}/{e['id']}={e['count']}"
       for why, d in docs() for e in d["edges"]
       if "count" in e and (not isinstance(e["count"], int) or e["count"] < 2)]
check("3. every declared count is an integer >= 2 (the mesher's floor, its two "
      "end corners): " + (", ".join(bad) if bad else "all legal"), not bad)

# ── 4. exactly one count seed per equivalence class ─────────────────────────
bad = []
for why, d in docs():
    by_id = {e["id"]: e for e in d["edges"]}
    uf = _UF()
    for e in d["edges"]:
        uf.find(e["id"])
    for b in d["blocks"]:
        s, e, n, w = b["edges"]
        uf.union(s, n)   # opposite sides of a block carry equal counts
        uf.union(e, w)
    cls = {}
    for eid in by_id:
        cls.setdefault(uf.find(eid), []).append(eid)
    for root, members in cls.items():
        seeds = [m for m in members if "count" in by_id[m]]
        if len(seeds) != 1:
            bad.append(f"{why}: class {sorted(members)} has {len(seeds)} seed(s)")
check("4. exactly one count seed per equivalence class, classes derived here "
      "from the mesher's two propagation rules rather than from the builder: "
      + ("; ".join(bad) if bad else "one seed in every class"), not bad)

# ── 5. a wall bounds one block side, an interface exactly two ───────────────
bad = []
for why, d in docs():
    uses = {e["id"]: 0 for e in d["edges"]}
    for b in d["blocks"]:
        for eid in b["edges"]:
            uses[eid] += 1
    for e in d["edges"]:
        want = 1 if e["kind"] == "wall" else 2
        if uses[e["id"]] != want:
            bad.append(f"{why}/{e['id']} kind={e['kind']} used {uses[e['id']]}x")
check("5. every 'wall' bounds exactly one block side and every 'interface' "
      "exactly two: " + (", ".join(bad) if bad else "all as declared"), not bad)

# ── 6. no key outside the mesher's schema ───────────────────────────────────
# The accepted sets are READ OUT OF THE C++, not restated here: a schema that gains
# a key must not silently make this check weaker, and one that loses a key must
# fail here rather than at the user's first run. A derivation that answers on bad
# input is worse than none (#116), so a set that does not parse fails the check.
_mb = open(os.path.join(_REPO, "src", "MultiBlock.cpp"), encoding="utf-8").read()


def _key_sets():
    """Every ``rejectUnknownKeys`` key set in the parser, as a list of sets."""
    out = []
    for m in re.finditer(r"rejectUnknownKeys\(([^;]*?)\{([^}]*)\}", _mb, re.S):
        ks = set(re.findall(r'"([^"]+)"', m.group(2)))
        if ks:
            out.append(ks)
    return out


_SETS = _key_sets()


def schema_keys(marker: str):
    """The key set containing ``marker``, or None if it is not EXACTLY one.

    Selected by a marker key rather than by the call's ``where`` argument, which is
    a runtime-built variable at three of the four call sites and so is not in the
    source to match on. Each marker below appears in exactly one set; requiring
    exactly one match is what makes this a derivation rather than a guess, and
    returning None on an ambiguous or absent marker is what stops it answering on
    input it did not understand (#116).
    """
    hits = [s for s in _SETS if marker in s]
    return hits[0] if len(hits) == 1 else None


_corner_keys = schema_keys("xy")
_edge_keys = schema_keys("binding")
_block_keys = schema_keys("orientation")
_doc_keys = schema_keys("format_version")
_spacing_keys = schema_keys("law")
check("6a. all FIVE schema key sets were READ from src/MultiBlock.cpp by a "
      f"marker key, not assumed: corner={_corner_keys}, edge={_edge_keys}, "
      f"block={_block_keys}, doc={_doc_keys}, spacing={_spacing_keys}",
      all(x for x in (_corner_keys, _edge_keys, _block_keys, _doc_keys,
                      _spacing_keys)))
bad = []
if all(x for x in (_corner_keys, _edge_keys, _block_keys, _doc_keys,
                   _spacing_keys)):
    for why, d in docs():
        for k in d:
            if k not in _doc_keys:
                bad.append(f"{why}: document key '{k}'")
        for c in d["corners"]:
            bad += [f"{why}: corner key '{k}'" for k in c if k not in _corner_keys]
        for e in d["edges"]:
            bad += [f"{why}: edge key '{k}'" for k in e if k not in _edge_keys]
            bad += [f"{why}: spacing key '{k}'"
                    for k in e.get("spacing", {}) if k not in _spacing_keys]
        for b in d["blocks"]:
            bad += [f"{why}: block key '{k}'" for k in b if k not in _block_keys]
check("6b. every emitted key is one the mesher's schema accepts: "
      + (", ".join(sorted(set(bad))) if bad else "no unknown key"), not bad)

# ── 7. nothing is declared that reaches nothing ─────────────────────────────
bad = []
for why, d in docs():
    on_edge = {c for e in d["edges"] for c in e["corners"]}
    in_block = {eid for b in d["blocks"] for eid in b["edges"]}
    orphan_c = [c["id"] for c in d["corners"] if c["id"] not in on_edge]
    orphan_e = [e["id"] for e in d["edges"] if e["id"] not in in_block]
    if orphan_c or orphan_e:
        bad.append(f"{why}: corners {orphan_c}, edges {orphan_e}")
check("7. no corner lies on no edge and no edge lies in no block: "
      + ("; ".join(bad) if bad else "everything reaches something"), not bad)

# ── 8. the corner grid is the declared range, exactly at both ends ──────────
bad = []
for why, kw in SPREAD:
    m = model(**kw)
    d = tm.build_document(m)
    xs = sorted({round(c["xy"][0], 12) for c in d["corners"]})
    ys = sorted({round(c["xy"][1], 12) for c in d["corners"]})
    if (xs[0], xs[-1]) != (m.hgrid_x_min, m.hgrid_x_max):
        bad.append(f"{why}: x {xs[0]}..{xs[-1]}")
    if (ys[0], ys[-1]) != (m.hgrid_y_min, m.hgrid_y_max):
        bad.append(f"{why}: y {ys[0]}..{ys[-1]}")
    if len(xs) != m.hgrid_nx + 1 or len(ys) != m.hgrid_ny + 1:
        bad.append(f"{why}: {len(xs)}x{len(ys)} grid lines")
check("8. the corner grid spans exactly the declared range and has one line per "
      "block boundary: " + ("; ".join(bad) if bad else "exact at both ends"), not bad)

# ── 9. the floor clustering is on every bottom edge, or on none ─────────────
bad = []
for why, kw in SPREAD:
    m = model(**kw)
    d = tm.build_document(m)
    bottom = [e for e in d["edges"] if e["id"].startswith("v_") and
              e["id"].endswith("_0")]
    got = [e for e in bottom if e.get("spacing")]
    want = len(bottom) if m.hgrid_wall_bottom else 0
    if len(got) != want:
        bad.append(f"{why}: {len(got)} of {len(bottom)} bottom edges clustered")
    for e in got:
        if e["spacing"] != {"wall_ends": "start"}:
            bad.append(f"{why}/{e['id']}: {e['spacing']}")
check("9. the floor clustering reaches EVERY vertical edge of the bottom row "
      "(spacing does not propagate, only counts do), and names the 'start' end "
      "because those edges are declared upward: "
      + ("; ".join(bad) if bad else "all or none, always 'start'"), not bad)

# ── 10. the derivation has ONE owner, shared with the panel ────────────────
m = model(hgrid_x_min=0.0, hgrid_x_max=2.0, hgrid_nx=2, hgrid_cell=0.1)
xc, yc = topology_hgrid.hgrid_counts(m)
d = tm.build_document(m)
seeded_x = [e["count"] for e in d["edges"]
            if e["id"].startswith("h_") and e["id"].endswith("_0")]
check(f"10. the counts the document seeds are the ones hgrid_counts reports "
      f"({seeded_x} vs {xc}) — the panel displays that same function's answer",
      seeded_x == xc)
check("10b. ...and a 2.0 span in 2 blocks at a 0.1 target is 11 nodes per column "
      f"(10 intervals + 1), measured: {xc}", xc == [11, 11])

# ── 11. an override replaces only the position it names ────────────────────
m = model(hgrid_nx=3, hgrid_cell=0.1, hgrid_x_min=0.0, hgrid_x_max=3.0,
          hgrid_counts_x="9,,4")
xc, _ = topology_hgrid.hgrid_counts(m)
check(f"11. an override replaces the positions it names and leaves the blank one "
      f"derived: {xc} (derived would be [11, 11, 11])", xc == [9, 11, 4])
m = model(hgrid_nx=2, hgrid_counts_x="oops,1")
xc, _ = topology_hgrid.hgrid_counts(m)
check("11b. an unparseable or below-floor override keeps the derived value "
      f"rather than refusing while the user is still typing: {xc}",
      all(v >= 2 for v in xc))

# ── 12. the model names no family -> a refusal, not an empty document ──────
try:
    tm.build_document(tm.TopologyModel())
    _raised = False
except ValueError as exc:
    _raised = "names no topology family" in str(exc)
check("12. building from a model that names no family raises rather than "
      "returning an empty document", _raised)

# ── 13. Qt-free, in a subprocess ──────────────────────────────────────────
_probe = (
    "import sys; sys.path.insert(0, %r);"
    "import app.services.topology_model, app.services.topology_hgrid;"
    "print('PyQt6' in sys.modules)" % _GUI)
p = subprocess.run([sys.executable, "-c", _probe], capture_output=True, text=True,
                   cwd=_REPO)
check("13. importing the topology model and the H-grid family leaves PyQt6 "
      f"unimported (subprocess said {p.stdout.strip()!r}; in-process this check "
      "could only ever say 'loaded')", p.stdout.strip() == "False")

# ── 14. the defaults, through the REAL binary ─────────────────────────────
if not os.path.exists(_BIN):
    print("SKIP  build/HybMesh2D not built; the real-binary half is not measured.")
else:
    with tempfile.TemporaryDirectory() as tmp:
        m = model()
        topo = tm.project(m, os.path.join(tmp, "case.dat"))
        stem = os.path.join(tmp, "mesh")
        conf = os.path.join(tmp, "case.dat")
        with open(conf, "w", encoding="utf-8") as f:
            f.write("MESH_MODE 1\n"
                    f"MESH_TOPOLOGY_FILE {topo}\n"
                    "MB_SPLIT_QUADS 1\nBL_INITIAL_THICKNESS 0.002\n"
                    "EXPORT_VTK 1\nBC_GEOM wall\n"
                    f"OUTPUT_FILENAME {stem}.vtk\n")
        env = dict(os.environ)
        lib = subprocess.run(["bash", os.path.join(_REPO, "tools", "scripts",
                                                   "gmsh_lib_dir.sh")],
                             capture_output=True, text=True)
        if lib.returncode == 0 and lib.stdout.strip():
            env["DYLD_LIBRARY_PATH"] = lib.stdout.strip()
        p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=env,
                           capture_output=True, text=True, timeout=900)
        out = (p.stdout or "") + (p.stderr or "")
        check(f"14. the DEFAULT parameters run the real mesher to exit 0 "
              f"(got {p.returncode})", p.returncode == 0)
        mm = re.search(r"Inverted cells\s*:\s*(\d+) of (\d+)", out)
        check("14b. ...with zero inverted cells, over a mesh that exists "
              f"({mm.group(0) if mm else 'no Inverted cells row'})",
              bool(mm) and mm.group(1) == "0" and int(mm.group(2)) > 0)
        check("14c. ...and the mesh file it names was written",
              os.path.exists(stem + ".vtk"))
        # 15. NO SECOND QUALITY PATH. A template's mesh is a mesh, so the figures
        # the Mesh Statistics panel and both headless hosts show come from the
        # sidecar the mesher already writes and the ONE reader #131 built — this
        # ticket adds no quality code, and the check proves that by asking that
        # reader rather than by parsing the run's output again.
        sys.path.insert(0, _GUI)
        from app.services import mesh_shape_stats  # noqa: E402
        rep = mesh_shape_stats.shape_report(stem + ".vtk")
        check(f"15. the existing one reader reports the template mesh's shape "
              f"figures, so the panel and both headless hosts show them with no "
              f"second quality path added here: {rep!r}",
              "quad_midline_ratio" in rep and "median" in rep)

print()
if failures:
    print(f"FAILED {len(failures)} check(s)")
    sys.exit(1)
print("All checks passed.")
