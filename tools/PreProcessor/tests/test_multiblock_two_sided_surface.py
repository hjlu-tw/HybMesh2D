#!/usr/bin/env python3
"""An edge clustering to a DIFFERENT height at each end, through the real binary (#177).

The arithmetic is pinned next door in ``tests/cpp/test_multiblock.cpp`` check 60,
which links the pure layer alone and measures the two declared intervals, the
reduction to the symmetric law, the reversal equivariance and the two fallbacks on
node positions nobody exported. What can only be checked OUT HERE is that the
chain connects on a mesh a user runs: that four declared heights on one radial
line come back as four intervals in the exported ``.vtk``, and that the capability
is the one the shipped document was working around.

THE FIXTURE IS THE SHIPPED TWO-RING O-GRID, one key away. This is not a convenient
example — it is issue #177's user story 2, written down in
``examples/topology/tworing_ogrid.json`` as a hand-computed constant:

    the outer ring's radials "cluster at their 'start', the corner on the SEAM, to
    the height the inner ring finished at"  ...  "ds_start": 0.05813418

That number is not a quantity anybody chose. It is what the ONE-SIDED tanh happens
to leave at the far end of the inner ring at that count, over that span, at that
``BL_INITIAL_THICKNESS`` — read off a run and typed back in, so the seam would not
be a jump in cell size. Until #177 it could not be declared, because the inner
ring already clustered at its wall end and a second, different height at the other
end was refused by name. What this gate measures is that it is a DECLARATION now:
the inner ring says where it finishes, the outer ring says where it starts, both
are honoured, and the height is free.

What this pins down:

  1. The shipped one-sided mesh still contains that constant, read OUT of the
     shipped document rather than written here — so an edit to either the document
     or the law is caught, and the paragraph above cannot quietly stop being true.
  2. FOUR DECLARED HEIGHTS ON ONE LINE, all four produced: the body wall's
     ``BL_INITIAL_THICKNESS``, the inner ring's ``ds_end``, the outer ring's
     ``ds_start`` and its ``ds_end``, measured as distances between exported nodes
     along the +x ray and never read off the law. Two of the four are on edges
     that declare BOTH ends, which is the whole feature.
  3. THE SEAM HEIGHT IS FREE, AND 0.05813418 WAS NOT THE BEST CHOICE. Three
     declared seam heights, and the figures the quality report already publishes
     move MONOTONICALLY with it: a coarser seam gives a better worst neighbour
     size jump and a better bulk cell shape. The shipped constant is in that
     sweep, so what the document has is placed against what it could have had.
  4. DECLARING THE CONSTANT THE DOCUMENT ALREADY CARRIES REPRODUCES THE ONE-SIDED
     MESH, to the eight decimals the constant is written at. The negative control
     for 2 and 3, and the only check here that can tell "a new law" from "the same
     law with its other end named".
  5. The mesh is a MESH: zero inverted cells, one connected component, every
     interior edge in exactly two cells, the boundary set equal to the ``.bnd`` —
     #53's conformity measure, because a new distribution is exactly the kind of
     change that can leave a conforming topology with a torn grid.
  6. THE REFUSAL IS GONE AND THE WARNING IS NOT. A pair the count cannot carry
     still meshes, exits 0, and says per END which one gave way — plus the clause
     naming the PAIR condition, so a reader is not sent to refine an end that is
     already as fine as it asked to be.

Known blind spots, stated rather than pretended away:

  a. EVERY MEASUREMENT IS ON THE +x RAY. That ray is one of the four radial
     interfaces and the other three are its images under the topology's own
     symmetry, so a defect confined to one of the other three is invisible here.
     The C++ check next door reads every edge of its fixture by index and does not
     share this hole; what nothing covers either way is a two-ended edge whose two
     blocks disagree about its direction, which no shipped document declares.
  b. THE SWEEP IN CHECK 3 IS THREE SAMPLES. "Monotone" is a claim about the three
     heights SAMPLED and not about the interval between them, exactly as
     ``test_multiblock_smooth_surface.py`` group 14's cap sweep is.
  c. NOTHING HERE RUNS THE SOLVER. The meshes this gate makes are better or worse
     by the ruler ``MbQuality`` publishes, and that ruler is not a solve. Gate 2
     for this family is ``test_multiblock_cgrid_surface.py``'s dated quotation.
  d. UNSMOOTHED. Every figure is at ``MB_SMOOTH_ITERS 0``, because the subject is
     the LAW and the default 20 sweeps move interior interface nodes (#84) — which
     is exactly the +x ray. Check 5 drives the DEFAULT as well, so a declaration
     that only fills at zero sweeps is caught; nothing here says what the law's
     advantage is worth after the solve.

THE INJECTIONS ARE HAND RUNS and are recorded ONCE, beside check 60 in
``tests/cpp/test_multiblock.cpp``: eleven mutations of the new code, dated
2026-10-20, each built and its EXIT CODE read against BOTH gates, with a named
negative control. Four of the eight that bite are seen only here — the message's
own arithmetic among them — and three are seen only by the C++ group, which is
why neither file is worth much alone. Restating the ledger here would be a second
home for it; read it there.

Run:  python3 tools/PreProcessor/tests/test_multiblock_two_sided_surface.py
"""
import json
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_TOPO = os.path.join(_REPO, "examples", "topology", "tworing_ogrid.json")
sys.path.insert(0, _HERE)
from mesher_bin import mesher_env as _mesher_env  # noqa: E402
from mb_shipped_config import shipped_config  # noqa: E402

# The two equivalence classes of the shipped two-ring O-grid, by the ids the
# document gives them: the inner ring's radials run body -> seam and the outer
# ring's run seam -> far field.
_INNER = ("ri0", "ri1", "ri2", "ri3")
_OUTER = ("ro0", "ro1", "ro2", "ro3")

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(tmp, conf):
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=600)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def fixture():
    """The shipped topology as data, so a variant differs from it by one key.

    The shipped documents carry ``//`` comments, which the mesher's parser accepts
    and Python's does not."""
    text = "\n".join(ln for ln in open(_TOPO, encoding="utf-8").read().splitlines()
                     if not ln.lstrip().startswith("//"))
    return json.loads(text)


def edge(doc, eid):
    for e in doc["edges"]:
        if e["id"] == eid:
            return e
    raise AssertionError("no edge %r in the shipped topology" % eid)


def variant(seam=None, far=None):
    """The shipped topology with the seam and far-field heights DECLARED.

    `seam` goes on both sides of it — the inner ring's ``ds_end`` and the outer
    ring's ``ds_start`` — which is the point: the match is then held by two
    declarations rather than by a constant somebody read off a run. `far` is the
    outer ring's ``ds_end``, the end the shipped document leaves to the law.
    """
    doc = fixture()
    for eid in _INNER:
        if seam is not None:
            edge(doc, eid)["spacing"]["ds_end"] = seam
    for eid in _OUTER:
        if seam is not None:
            edge(doc, eid)["spacing"]["ds_start"] = seam
        if far is not None:
            edge(doc, eid)["spacing"]["ds_end"] = far
    return doc


def write_topo(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    return path


def base_config(topo=None, geom_dir=None):
    """The shipped config, retargeted. See `mb_shipped_config.shipped_config`."""
    return shipped_config(
        "multiblock_tworing",
        paths=({"MESH_TOPOLOGY_FILE": topo} if topo is not None else None),
        dirs=({"GEOM_FILE": geom_dir} if geom_dir is not None else None))


def write_config(path, topology, out_stem, extra=""):
    text = base_config(topo=topology).replace("@STEM@", out_stem)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text + "\n" + extra)
    return path


def wall_spacing():
    """``BL_INITIAL_THICKNESS`` as the SHIPPED config states it.

    Read rather than written down, for the reason the seam constant is: the first
    interval off the body is that key's value and nothing else, so a gate carrying
    its own copy would go on passing after the config changed."""
    for ln in base_config().splitlines():
        if ln.split(None, 1)[:1] == ["BL_INITIAL_THICKNESS"]:
            return float(ln.split(None, 1)[1])
    raise AssertionError("the shipped two-ring config declares no BL_INITIAL_THICKNESS")


def shipped_seam():
    """The hand-computed constant the shipped document carries on its outer ring.

    All four outer radials must agree on it; a document where they do not is one
    this gate's whole premise is wrong about, so it raises rather than picking."""
    doc = fixture()
    vals = {edge(doc, eid)["spacing"]["ds_start"] for eid in _OUTER}
    assert len(vals) == 1, "the shipped outer radials disagree: %r" % (vals,)
    return vals.pop()


def vtk_nodes(stem):
    """Node positions from the `.vtk`, at full precision.

    NOT the `.vrt`, whose vertices are written at 8 decimals: an interval read
    from that file carries 1e-08 of the WRITER's format, which is four orders
    above what the law delivers and would turn this gate into a measurement of
    `exportStarCD`."""
    out = []
    lines = open(stem + ".vtk", encoding="utf-8").read().split("\n")
    i = next(k for k, ln in enumerate(lines) if ln.startswith("POINTS"))
    n = int(lines[i].split()[1])
    k = i + 1
    while len(out) < n:
        v = lines[k].split()
        for j in range(0, len(v), 3):
            out.append((float(v[j]), float(v[j + 1])))
        k += 1
    return out


def ray(nodes):
    """The +x radial line's node x-coordinates, body outward.

    One of the four radial interfaces, picked because the topology puts a corner
    of every ring on it: `b0`, `m0` and `f0` are all at y = 0, x > 0."""
    xs = sorted(p[0] for p in nodes if abs(p[1]) < 1e-9 and p[0] > 0.0)
    return [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]


def cel_cells(stem):
    out = []
    with open(stem + ".cel", encoding="utf-8") as f:
        for line in f:
            s = line.split()
            if len(s) >= 5:
                ids, seen = [], []
                for v in s[1:5]:
                    iv = int(v)
                    if iv not in seen:
                        seen.append(iv)
                        ids.append(iv)
                out.append(tuple(ids))
    return out


def bnd_faces(stem):
    out = []
    with open(stem + ".bnd", encoding="utf-8") as f:
        for line in f:
            s = line.split()
            if len(s) >= 8:
                out.append(frozenset((int(s[1]), int(s[2]))))
    return out


def edge_use(cells):
    """How many cells each undirected cell edge belongs to (#53's measure)."""
    use = {}
    for c in cells:
        for k in range(len(c)):
            e = frozenset((c[k], c[(k + 1) % len(c)]))
            if len(e) == 2:
                use[e] = use.get(e, 0) + 1
    return use


def components(cells, n_nodes):
    parent = list(range(n_nodes + 1))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    seen = set()
    for c in cells:
        for v in c[1:]:
            ra, rb = find(c[0]), find(v)
            if ra != rb:
                parent[ra] = rb
        seen.update(c)
    return len({find(v) for v in seen})


def qline(out):
    """`HYBMESH_MB_QUALITY` as a dict of floats. The prefix is matched WITH its
    trailing space, so `..._BEFORE` is never read as the real one."""
    for ln in out.splitlines():
        if ln.startswith("HYBMESH_MB_QUALITY "):
            return {k: float(v) for k, v in
                    (tok.split("=") for tok in ln.split()[1:])}
    raise AssertionError("no HYBMESH_MB_QUALITY line in the run's output")


def mesh(tmp, name, doc, extra="MB_SMOOTH_ITERS 0\n"):
    """One run of a variant topology. Returns (rc, output, stem)."""
    topo = write_topo(os.path.join(tmp, name + ".json"), doc)
    stem = os.path.join(tmp, name)
    conf = write_config(os.path.join(tmp, name + ".dat"), topo, stem, extra)
    rc, out = run(tmp, conf)
    return rc, out, stem


def main() -> int:
    if not os.path.exists(_BIN):
        print("SKIP  no mesher binary at %s — run ./build.sh" % _BIN)
        return 0

    wall = wall_spacing()
    ship = shipped_seam()

    with tempfile.TemporaryDirectory() as tmp:
        # ── 1. the shipped document's constant is what the one-sided law leaves ──
        rc, out, stem = mesh(tmp, "shipped", fixture())
        check("1. the shipped two-ring O-grid meshes unsmoothed (rc=%d)" % rc, rc == 0)
        d0 = ray(vtk_nodes(stem)) if rc == 0 else []
        check("1. ...over 48 intervals on the +x ray, 24 per ring (%d)" % len(d0),
              len(d0) == 48)
        if len(d0) == 48:
            check("1. ...whose first interval off the body IS BL_INITIAL_THICKNESS "
                  "%g (got %.9g)" % (wall, d0[0]),
                  abs(d0[0] - wall) <= 1e-9 * wall)
            # The inner ring's LAST interval, which the document's outer ring
            # hard-codes as its own first. Read off the mesh, compared with the
            # document — neither number written here.
            check("1. ...and whose inner ring finishes at the %g the shipped "
                  "document types into its outer ring, which is where that "
                  "constant came from (got %.9g)" % (ship, d0[23]),
                  abs(d0[23] - ship) <= 1e-7 * ship)
            check("1. ...so the seam is not a jump in cell size: the ratio across "
                  "it is %.9f" % (d0[24] / d0[23]),
                  abs(d0[24] / d0[23] - 1.0) <= 1e-7)

        # ── 2. four declared heights on one line, all four produced ─────────────
        seam, far = 0.04, 0.6
        rc, out, stem = mesh(tmp, "four", variant(seam=seam, far=far))
        check("2. a topology declaring BOTH ends of BOTH radial classes meshes "
              "(rc=%d) — refused by name until #177" % rc, rc == 0)
        d = ray(vtk_nodes(stem)) if rc == 0 else []
        check("2. ...over the same 48 intervals (%d)" % len(d), len(d) == 48)
        if len(d) == 48:
            for label, got, want in (("the body wall's BL_INITIAL_THICKNESS", d[0], wall),
                                     ("the inner ring's declared ds_end", d[23], seam),
                                     ("the outer ring's declared ds_start", d[24], seam),
                                     ("the outer ring's declared ds_end", d[47], far)):
                check("2. ...%s is the interval produced: want %g, got %.12g"
                      % (label, want, got),
                      abs(got - want) <= 1e-6 * want)
            check("2. ...and the seam ratio is 1.000000000 BY DECLARATION rather "
                  "than by a constant read off an earlier run (%.9f)"
                  % (d[24] / d[23]), abs(d[24] / d[23] - 1.0) <= 1e-6)
        check("2. ...and no end is accused of missing its request",
              "asks for a first cell height" not in out)

        # ── 3. the seam height is free, and the shipped constant is in the sweep ─
        #
        # THE DIRECTION IS THE CLAIM, not any one figure. Both are published by
        # the quality report already: `adjacent_area_ratio_p95` is the worst
        # neighbour size jump and `quad_midline_ratio_bulk_p95` the cell shape
        # outside the wall band, and the two must agree about which way the seam
        # should move or this check says nothing.
        rows = []
        for h in (0.03, ship, 0.08):
            rc, out, stem = mesh(tmp, "seam_%s" % h, variant(seam=h))
            check("3. the two-ring O-grid meshes with its seam declared at %g "
                  "(rc=%d)" % (h, rc), rc == 0)
            if rc == 0:
                q = qline(out)
                rows.append((h, q["adjacent_area_ratio_p95"],
                             q["quad_midline_ratio_bulk_p95"], q["inverted"],
                             q["nonortho_max_deg"]))
                print("    [3] seam=%-10g adj_p95=%.6f bulk_p95=%.6f inverted=%d "
                      "nonortho_max=%.6f" % rows[-1])
        check("3. all three seam heights fill (%d of 3)" % len(rows), len(rows) == 3)
        if len(rows) == 3:
            check("3. ...none of them inverting a cell",
                  all(r[3] == 0 for r in rows))
            check("3. ...with non-orthogonality untouched, so the seam height is "
                  "not buying its improvement there (%s)"
                  % ", ".join("%.6f" % r[4] for r in rows),
                  max(r[4] for r in rows) - min(r[4] for r in rows) <= 1e-6)
            check("3. ...and a COARSER seam strictly improves the worst neighbour "
                  "size jump: %s" % " > ".join("%.6f" % r[1] for r in rows),
                  rows[0][1] > rows[1][1] > rows[2][1])
            check("3. ...and the bulk cell shape with it, so the two agree: %s"
                  % " > ".join("%.6f" % r[2] for r in rows),
                  rows[0][2] > rows[1][2] > rows[2][2])
            check("3. ...which places the shipped %g in that sweep rather than at "
                  "its best end — it is what the ONE-SIDED law left, and #177 is "
                  "what makes it a choice" % ship,
                  rows[1][1] > rows[2][1])

        # ── 4. the constant the document carries reproduces the one-sided mesh ──
        rc, out, stem = mesh(tmp, "same", variant(seam=ship))
        check("4. declaring the shipped constant at both sides of the seam meshes "
              "(rc=%d)" % rc, rc == 0)
        d1 = ray(vtk_nodes(stem)) if rc == 0 else []
        if len(d0) == 48 and len(d1) == 48:
            worst = max(abs(a - b) for a, b in zip(d0, d1))
            print("    [4] worst +x-ray interval gap one-sided vs two-ended: %.3e"
                  % worst)
            # The constant is written at EIGHT decimals, so the two laws can only
            # agree to the precision the document states it at. The bound is that
            # rounding carried through the span, not a tolerance on the law: at
            # 1e-12 this would be measuring how many digits somebody typed.
            check("4. ...and reproduces the one-sided mesh to the eight decimals "
                  "the constant is written at (worst interval gap %.3e)" % worst,
                  worst <= 1e-7)

        # ── 5. the grid is a GRID, at zero sweeps and at the shipped default ────
        for sweeps, extra in ((0, "MB_SMOOTH_ITERS 0\n"), ("the shipped default", "")):
            rc, out, stem = mesh(tmp, "conf_%s" % str(sweeps).split()[-1],
                                 variant(seam=seam, far=far), extra)
            check("5. the two-ended declaration fills at %s (rc=%d)" % (sweeps, rc),
                  rc == 0)
            if rc != 0:
                continue
            q = qline(out)
            check("5. ...with 0 inverted cells (%d)" % q["inverted"],
                  q["inverted"] == 0)
            nodes, cells = vtk_nodes(stem), cel_cells(stem)
            use = edge_use(cells)
            interior = {e for e, n in use.items() if n == 2}
            boundary = {e for e, n in use.items() if n == 1}
            check("5. ...every cell edge in exactly one or two cells (%d bad)"
                  % len([n for n in use.values() if n > 2]),
                  all(n <= 2 for n in use.values()))
            check("5. ...the boundary set equal to the .bnd (%d vs %d)"
                  % (len(boundary), len(set(bnd_faces(stem)))),
                  boundary == set(bnd_faces(stem)))
            check("5. ...and one connected component (%d), over %d interior edges"
                  % (components(cells, len(nodes)), len(interior)),
                  components(cells, len(nodes)) == 1)

        # ── 6. the refusal is gone; the warning is not ──────────────────────────
        #
        # A pair the count cannot carry, on the OUTER ring alone: it keeps the
        # shipped document's own 0.05813418 at the seam and asks for 4.0 at the
        # far field over a span of about 9. The inner ring is left ONE-SIDED on
        # purpose, so the lines this check reads can only be the outer ring's —
        # a first draft declared the impossible pair on both classes and parsed
        # an inner radial's message against the outer radial's numbers.
        FAR = 4.0
        rc, out, stem = mesh(tmp, "impossible", variant(far=FAR))
        check("6. a pair the count cannot carry still MESHES (rc=%d) — the refusal "
              "this ticket removed was about the law, and what replaced it is a "
              "measurement" % rc, rc == 0)
        check("6. ...and the old refusal's words are nowhere in the output",
              "different first cell height at each end" not in out)
        check("6. ...while the per-END warning names an end that did not get what "
              "it asked for", "asks for a first cell height" in out)
        check("6. ...and says it was the PAIR, so the reader is not sent to refine "
              "an end that is already as fine as it asked to be",
              "it is the PAIR that did not fit" in out)
        # THE TWO FIGURES ARE READ BACK OUT AND RE-DERIVED HERE, not matched as
        # words. `"(count - 2) squared" in out` passes whichever base the code
        # actually squares, and an exponent off by one in a message nobody
        # recomputes is the defect this ticket already made once in its own
        # derivation. The outer radials declare 25 nodes, so the bound is 23*23.
        said = [ln for ln in out.splitlines() if "it is the PAIR that did not fit" in ln]
        check("6. ...once per outer radial and on ONE of each edge's two ends, so "
              "the end that was honoured is not also accused (%d lines)" % len(said),
              len(said) == len(_OUTER))
        if said:
            txt = said[0]
            after = txt.split("which is", 1)[-1]
            got = after.split("against")
            lhs = float(got[0].strip())
            rhs = float(got[1].strip().split()[0])
            span = float(got[1].split("on this edge's")[1].strip().split()[0])
            want_lhs = (span / ship - 1.0) * (span / FAR - 1.0)
            print("    [6] span=%.3f lhs=%.3f (recomputed %.3f) rhs=%.3f"
                  % (span, lhs, want_lhs, rhs))
            check("6. ...stating the bound as (count - 2) squared = 23*23 = 529 "
                  "for a 25-node edge, not (count - 1) squared (got %.3f)" % rhs,
                  abs(rhs - 529.0) < 0.5)
            check("6. ...and the left-hand side it printed is the one this gate "
                  "recomputes from the span it also printed (%.3f vs %.3f)"
                  % (lhs, want_lhs),
                  abs(lhs - want_lhs) <= 2e-3 * max(1.0, abs(want_lhs)))
            check("6. ...and that left-hand side really is below the bound, so the "
                  "message is not announcing a failure it cannot see", lhs < rhs)

    print("\n%d check(s) failed" % len(failures) if failures else "\nAll checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
