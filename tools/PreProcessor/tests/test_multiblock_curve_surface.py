#!/usr/bin/env python3
"""A topology edge that IS a curve, end to end through the real binary (#175).

The arithmetic is pinned next door in ``tests/cpp/test_mb_curve.cpp``, which links
the pure layer alone and measures the quadrature, the arc-length placement, the
projection and the three span refusals against references that are NOT the module
itself. What can only be checked out here is that the chain CONNECTS: that a
topology declaring ``"curve": {"kind": "ellipse", ...}`` — with no geometry file,
no sidecar and no segment id for that curve anywhere — becomes one conforming grid
on disk whose block boundary is that ellipse to machine precision.

THE FIXTURE IS THE SHIPPED CASE, and it is deliberately ONE DECLARATION away from
the case beside it. ``config/multiblock_tworing_curve.dat`` and
``examples/topology/tworing_curve.json`` are ``multiblock_tworing_offset``'s eight
blocks with the four ``follows`` seams replaced by four declared ellipses and the
third geometry file deleted. Everything else — body, far field, counts, both
radial equivalence classes, the winding — is identical, so a difference between
the two meshes is attributable to the one key.

What this pins down:

  1. The shipped case meshes (rc = 0) with zero inverted cells at the shipped
     O-grid budget — 4704 vertices, 9216 triangles, 192 boundary edges — so the
     two two-ring cases are comparable cell for cell.
  2. The run NAMES each seam ``a declared ellipse`` in the shared-edge report,
     which is how a user sees that the seam they declared is the seam they got.
  3. The 96 seam nodes in the EXPORTED ``.vrt`` lie on the declared ellipse. Not
     "close to": measured at 1.8e-16 worst, which is the arithmetic of the
     placement and not a tolerance anybody chose. The CHORD CONTROL is the same
     topology with the four ``curve`` keys removed: there the same nodes sit on
     the chords, up to 7.9e-02 off the ellipse, and the run says ``a straight
     chord``. Without that pair the first half describes a fixture rather than
     measuring a feature.
  4. The seam SURVIVES the default 20 Winslow sweeps, because a declared curve is
     a declared SHAPE and ``MbSharedEdge::hasDeclaredShape`` is what the freeze
     reads. 184 shared nodes move — the eight radials' interiors, 8 x 23 — and the
     96 on the seams do not, in the exported file and not only in the plan.
  5. The placement is EVEN IN ARC LENGTH along the ellipse, checked against an
     independent numerical integration written here. A placement even in the
     PARAMETER would pass every check above and fail this one: on a 1.5:1 quarter
     its chords would run about 1.4 apart end to end.
  6. The grid is CONFORMING on the exported files rather than argued: every
     interior edge belongs to exactly two cells, the boundary edge set is exactly
     the ``.bnd``, and it is one connected component. A declared seam carries no
     ``.bnd`` face and no patch of its own.
  7. Every refusal and both warnings this ticket adds, through the binary: a
     corner off the curve, a ``curve`` beside a ``follows``, an unknown curve kind,
     an ``r`` written on an ellipse, a non-positive extent, two corners at one
     point, an unknown ``sweep`` — all exit 8 with the machine-readable line and
     export NOTHING — plus the LONG-WAY-ROUND warning and the wall-with-a-curve
     warning, which are warnings precisely because each is a mesh and not an error.

EIGHT INJECTIONS, run 2026-10-16 against this gate with the EXIT CODE read and not only
the FAIL-line count, and each one's FIRST failing check recorded — eight injections
reporting the same count are eight that may all be hitting one cascade:

  I1  the corner-on-curve check accepts anything        exit 1, 1 FAIL, first 7/off_curve
  I2  the three-way exclusion back to a PAIR            exit 1, 1 FAIL, first 7/both_keys
  I3  unknown keys checked against the UNION of kinds   exit 1, 1 FAIL, first 7/r_on_ellipse
  I4  the LONG-way-round warning deleted                exit 1, 1 FAIL, first 7/long
  I5  the wall-with-a-curve warning deleted             exit 1, 1 FAIL, first 7/wall
  I6  nodes interpolated on the CHORD, not solved on
      the curve                                         exit 1, 3 FAIL, first 1 (rc 9)
  I7  the freeze gate back to `followsGeom` alone       exit 1, 2 FAIL, first 3
  I8  NEGATIVE CONTROL: `paths[k]` left as the chord
      for a curve edge                                  exit 0, 0 FAIL — inert BY DESIGN

I8 is the control that makes the others mean something here. `paths[k]` is built for a
curve edge as a fine rendering, and the module's own comment says nothing reads it; this
injection is what turns that comment into a measurement. Leave it inert — a check written
to redden it would be pinning a value the mesh does not depend on.

I7 CAME BACK INERT ON THE FIRST RUN AND THE HARNESS WAS AT FAULT, not the gate. That batch
was driven by a script sharing `build/` with a full `run_all.sh` left running in the
background, and the preceding injection had failed to BUILD; re-run alone the same mutation
reddens checks 3 and 4 exactly as it should. Recorded rather than quietly re-run: an
injection whose result depends on what else was touching the build tree is not evidence,
and "it came back inert" has twice in this repo meant the harness rather than the rule.

BLIND SPOTS, named:

  * Nothing here drives the SOLVER. The comparison this case exists for is a MESH
    comparison, recorded in ``docs/design_notes/mesher.md``; no flow has been run
    on either two-ring ellipse and neither case claims one.
  * The ellipse this file measures against is RE-DECLARED here from the same two
    numbers the topology uses (a = 0.75, b = 0.5), so an edit that changed both the
    document and this constant together would pass. What stops that being vacuous
    is check 3's chord control and check 5's independent integration: the first
    fails if the nodes stop being on ANY curve, the second if they stop being
    placed by arc length.
  * The 1.5:1 axis ratio is mild. The projection's hard case — a point inside a
    slender ellipse's evolute — is exercised in the C++ gate and by nothing here;
    no shipped topology reaches it, because a corner is on the curve by the time
    the span is resolved.

Run:  python3 tools/PreProcessor/tests/test_multiblock_curve_surface.py
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import json
import math
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_CONF = os.path.join(_REPO, "config", "multiblock_tworing_curve.dat")
_TOPO = os.path.join(_REPO, "examples", "topology", "tworing_curve.json")
sys.path.insert(0, _HERE)
from mesher_bin import mesher_env as _mesher_env  # noqa: E402
from mb_shipped_config import shipped_config  # noqa: E402

# The seam's ellipse. Two numbers, and the file says why re-declaring them here is
# not circular; see the blind spot above.
_A, _B = 0.75, 0.5
_SEAMS = ("s0", "s1", "s2", "s3")

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
    """The shipped topology as data, so a variant differs from it by one key."""
    text = "\n".join(ln for ln in open(_TOPO, encoding="utf-8").read().splitlines()
                     if not ln.lstrip().startswith("//"))
    return json.loads(text)


def edge(doc, eid):
    for e in doc["edges"]:
        if e["id"] == eid:
            return e
    raise AssertionError("no edge %r in the shipped topology" % eid)


def corner(doc, cid):
    for c in doc["corners"]:
        if c["id"] == cid:
            return c
    raise AssertionError("no corner %r in the shipped topology" % cid)


def write_topo(path, doc):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2)
    return path


def base_config(topo=None, geom_dir=None):
    """The shipped config, retargeted at a temp output stem.

    The name is ``base_config`` because ``tools/scripts/golden_mesh.py`` reaches
    every shipped multi-block case through ``mod.base_config()``, and every shipped
    ``config/multiblock_*.dat`` is one of its cases — a property nothing enforces,
    so leaving this out would quietly make it false for the newest one.

    BOTH arguments default to nothing rather than to this file's own paths: a
    default that names the shipped value asks for it BY NAME, so the gate would go
    on driving the same topology after the shipped config was repointed.
    """
    return shipped_config(
        "multiblock_tworing_curve",
        paths=({"MESH_TOPOLOGY_FILE": topo} if topo is not None else None),
        dirs=({"GEOM_FILE": geom_dir} if geom_dir is not None else None))


def write_config(path, topology, out_stem, extra=""):
    """The SHIPPED config with its topology and output re-pointed.

    Read from disk rather than composed, for the reason the topology is: the two
    geometry lines, the wall height and the split setting are what the user runs,
    and a composed lookalike would leave an edit to the shipped file invisible.
    """
    text = open(_CONF, encoding="utf-8").read()
    out = []
    for ln in text.splitlines():
        if ln.startswith("MESH_TOPOLOGY_FILE"):
            out.append("MESH_TOPOLOGY_FILE " + topology)
        elif ln.startswith("OUTPUT_FILENAME"):
            out.append("OUTPUT_FILENAME " + out_stem + ".vtk")
        elif ln.startswith("GEOM_FILE"):
            out.append("GEOM_FILE " + os.path.join(_REPO, ln.split(None, 1)[1].strip()))
        else:
            out.append(ln)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n" + extra)
    return path


def vtk_nodes(stem):
    """Node positions from the `.vtk`, in the same order as the `.vrt`'s ids.

    THE PRECISION CLAIM IS MEASURED HERE AND NOT ON THE `.vrt`. STAR-CD vertices
    are written at 8 decimals, so a node exactly on the curve reads back up to
    ~5e-09 off it, and a 1e-12 assertion against that file would be measuring the
    writer's format. The `.vtk` carries full precision and is the file a user
    looks at.
    """
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


def vrt_nodes(stem):
    out = []
    with open(stem + ".vrt", encoding="utf-8") as f:
        for line in f:
            s = line.split()
            if len(s) >= 4:
                out.append((float(s[1]), float(s[2])))
    return out


def cel_cells(stem):
    """One tuple of DISTINCT vertex ids per `.cel` row (a triangle is `v1 v2 v3 v3`)."""
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
            if len(s) >= 7:
                # A 2D face is two vertices written into four columns and
                # padded with 0, which is not a vertex id. Keeping the pad made
                # every face a 3-tuple and the comparison with the cell edges
                # below could never have matched.
                vs = tuple(sorted({int(v) for v in s[1:5] if int(v) != 0}))
                out.append((vs, s[-1]))
    return out


def off_ellipse(p):
    """Distance from `p` to the declared ellipse, by Newton on the squared distance.

    The same minimisation the mesher does, written independently here — the point
    of a surface gate is that it recomputes the answer rather than reading the
    mesher's own.
    """
    t = math.atan2(p[1] / _B, p[0] / _A)
    for _ in range(80):
        P = (_A * math.cos(t), _B * math.sin(t))
        d1 = (-_A * math.sin(t), _B * math.cos(t))
        d2 = (-_A * math.cos(t), -_B * math.sin(t))
        d = (P[0] - p[0], P[1] - p[1])
        f = d[0] * d1[0] + d[1] * d1[1]
        fp = d1[0] ** 2 + d1[1] ** 2 + d[0] * d2[0] + d[1] * d2[1]
        if fp == 0.0:
            break
        t -= f / fp
    P = (_A * math.cos(t), _B * math.sin(t))
    return math.hypot(P[0] - p[0], P[1] - p[1])


def arc_len(t0, t1, n=20000):
    """Arc length of the declared ellipse from t0 to t1, by a midpoint rule.

    A DIFFERENT rule from the module's composite Gauss-Legendre, so agreement is
    evidence rather than a second run of one implementation.
    """
    h = (t1 - t0) / n
    tot = 0.0
    for k in range(n):
        t = t0 + (k + 0.5) * h
        tot += math.hypot(_A * math.sin(t), _B * math.cos(t))
    return tot * h


def seam_nodes(nodes, tol=1e-9):
    return [p for p in nodes if off_ellipse(p) < tol]


def edge_use(cells):
    use = {}
    for c in cells:
        for k in range(len(c)):
            key = tuple(sorted((c[k], c[(k + 1) % len(c)])))
            use[key] = use.get(key, 0) + 1
    return use


def components(cells, n):
    parent = list(range(n + 1))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for c in cells:
        for v in c[1:]:
            a, b = find(c[0]), find(v)
            if a != b:
                parent[a] = b
    seen = {find(v) for c in cells for v in c}
    return len(seen)


def refusal(tmp, name, mutate, *needles):
    doc = fixture()
    mutate(doc)
    stem = os.path.join(tmp, name)
    rc, out = run(tmp, write_config(os.path.join(tmp, name + ".dat"),
                                    write_topo(os.path.join(tmp, name + ".json"), doc),
                                    stem))
    wrote = any(os.path.exists(stem + e) for e in (".vtk", ".vrt", ".cel", ".bnd"))
    ok = (rc == 8 and "HYBMESH_ERROR 8 TOPOLOGY" in out
          and all(n in out for n in needles) and not wrote)
    check("7. %s is refused with the TOPOLOGY code, naming %s, and exports nothing "
          "(rc=%d, wrote=%s)" % (name, ", ".join(repr(n) for n in needles), rc, wrote),
          ok)
    if not ok:
        print("     ...message was: " + " | ".join(
            ln for ln in out.splitlines() if "edge" in ln or "ERROR" in ln)[:600])


def main():
    if not os.path.exists(_BIN):
        print("SKIP  ./build/HybMesh2D not built")
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        # -- 1. the shipped case, through the shipped config -------------------
        stem = os.path.join(tmp, "curve")
        rc, out = run(tmp, write_config(os.path.join(tmp, "curve.dat"), _TOPO, stem))
        check("1. the shipped tworing_curve case meshes (rc=%d)" % rc, rc == 0)
        check("1. ...with zero inverted cells",
              "HYBMESH_MB_QUALITY " in out and " inverted=0 " in out)
        check("1. ...at the shipped O-grid budget: 4704 vertices, 9216 triangles, "
              "192 boundary edges",
              "Vertices (VRT)       : 4704" in out
              and "Cells                : 9216 triangles" in out
              and "Boundary Edges (BND) : 192" in out)

        # -- 2. the report NAMES the declared curve ----------------------------
        named = [s for s in _SEAMS
                 if ("Interface '%s'" % s) in out
                 and "a declared ellipse" in out.split("Interface '%s'" % s)[1]
                                                .split("\n")[0]]
        check("2. all four seams are reported as 'a declared ellipse' (%d of 4)"
              % len(named), len(named) == 4)

        # -- 3. the seam is ON the ellipse, with a CHORD control ---------------
        nodes = vtk_nodes(stem)
        check("3. the .vtk and the .vrt agree on the node count, so an id from one "
              "indexes the other (%d vs %d)" % (len(nodes), len(vrt_nodes(stem))),
              len(nodes) == len(vrt_nodes(stem)))
        on = seam_nodes(nodes, 1e-9)
        worst = max((off_ellipse(p) for p in on), default=1.0)
        check("3. 96 exported nodes lie on the declared ellipse — 4 seams x 25 nodes "
              "minus the 4 corners they share (%d)" % len(on), len(on) == 96)
        check("3. ...to 1e-12, which is the placement's arithmetic and not a chosen "
              "tolerance (worst %.3e)" % worst, worst < 1e-12)

        chord_doc = fixture()
        for s in _SEAMS:
            del edge(chord_doc, s)["curve"]
        c_stem = os.path.join(tmp, "chord")
        rc_c, out_c = run(tmp, write_config(
            os.path.join(tmp, "chord.dat"),
            write_topo(os.path.join(tmp, "chord.json"), chord_doc), c_stem))
        # The chord run's own seam: the nodes of the four straight lines between the
        # same corner pairs. Found by their distance to those chords, which is the
        # control's own measure and not the ellipse's.
        corners = [(0.75, 0.0), (0.0, 0.5), (-0.75, 0.0), (0.0, -0.5)]

        def off_chords(p):
            best = 1e30
            for k in range(4):
                a, b = corners[k], corners[(k + 1) % 4]
                vx, vy = b[0] - a[0], b[1] - a[1]
                L2 = vx * vx + vy * vy
                u = max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / L2))
                best = min(best, math.hypot(p[0] - a[0] - u * vx, p[1] - a[1] - u * vy))
            return best

        # THE POSITION CLAIM IS MADE ON THE UNSMOOTHED CONTROL, and that is not a
        # convenience. With no declared shape the chord seam is not frozen — #84
        # freed exactly the interior lines that have nothing to lose — so the 20
        # default sweeps move it off the chords, and a check that looked for them
        # there after smoothing would find only the four corners. What the FILL
        # produces is the thing being contrasted with.
        cu_stem = os.path.join(tmp, "chord_unsm")
        rc_cu, out_cu = run(tmp, write_config(
            os.path.join(tmp, "chord_unsm.dat"),
            os.path.join(tmp, "chord.json"), cu_stem, extra="MB_SMOOTH_ITERS 0\n"))
        cu_nodes = vtk_nodes(cu_stem)
        c_seam = [p for p in cu_nodes if off_chords(p) < 1e-12]
        c_worst = max((off_ellipse(p) for p in c_seam), default=0.0)
        check("3. CONTROL: with the four 'curve' keys removed the run says 'a straight "
              "chord' and the fill puts 96 nodes on the chords, up to %.3e off the "
              "ellipse (rc=%d, %d nodes)" % (c_worst, rc_cu, len(c_seam)),
              rc_cu == 0 and "a straight chord" in out_c
              and "a declared ellipse" not in out_c
              and len(c_seam) == 96 and c_worst > 1e-2)
        # AND THE CONTROL DOES NOT MERELY DIFFER, IT FAILS. Measured 2026-10-16: the
        # chord seam exits 9 with 96 INVERTED cells after the default sweeps, a worst
        # non-orthogonality of 77.658 deg against the declared ellipse's 29.170, and
        # a wall first cell 0.632 of the way off its target before smoothing against
        # 0.037. So a curved block boundary here is not a refinement of a working
        # mesh; it is what makes the mesh valid at all. This is the sharpest thing
        # this gate measures and it is asserted rather than left in a note.
        check("3. ...and that control mesh is INVALID: rc 9 with 96 inverted cells, "
              "where the declared ellipse has 0 (rc=%d)" % rc_c,
              rc_c == 9 and " inverted=96 " in out_c)

        # -- 4. the seam survives the sweeps -----------------------------------
        check("4. 184 shared nodes move — the eight radials' interiors, 8 x 23 — and "
              "the smoother ran its 20 sweeps",
              "of which 184 on a shared edge" in out and "Sweeps" in out)
        check("4. ...and the banner states the rule as a DECLARED SHAPE rather than "
              "as 'follows', which is now one of two ways to have one",
              "WITH A DECLARED SHAPE" in out)
        u_stem = os.path.join(tmp, "unsm")
        rc_u, out_u = run(tmp, write_config(os.path.join(tmp, "unsm.dat"), _TOPO,
                                            u_stem, extra="MB_SMOOTH_ITERS 0\n"))
        u_on = seam_nodes(vtk_nodes(u_stem), 1e-9)
        check("4. ...and the UNSMOOTHED run puts the same 96 there, so the freeze is "
              "holding a position the fill already produced (rc=%d, %d)"
              % (rc_u, len(u_on)), rc_u == 0 and len(u_on) == 96)

        # -- 5. the placement is even in ARC LENGTH ----------------------------
        #
        # The seam edges declare no spacing, so the law is the default tanh at
        # delta 0, which IS the uniform distribution — in arc length along the
        # curve. Measured on one quarter, against an integration written here.
        quarter = [p for p in on if p[0] > 1e-12 and p[1] > 1e-12]
        quarter.sort(key=lambda p: math.atan2(p[1] / _B, p[0] / _A))
        params = [math.atan2(p[1] / _B, p[0] / _A) for p in quarter]
        L = arc_len(0.0, math.pi / 2)
        steps = ([arc_len(0.0, params[0])]
                 + [arc_len(params[k], params[k + 1]) for k in range(len(params) - 1)]
                 + [arc_len(params[-1], math.pi / 2)])
        check("5. the first quarter carries 23 interior seam nodes (%d)"
              % len(quarter), len(quarter) == 23)
        spread = max(steps) / min(steps)
        check("5. ...and its 24 intervals are equal in ARC LENGTH to 1e-6 "
              "(max/min %.9f), which a placement even in the PARAMETER would miss "
              "by about 1.4" % spread, spread < 1.000001)
        check("5. ...and they sum to the quarter's own length (%.12f vs %.12f)"
              % (sum(steps), L), abs(sum(steps) - L) < 1e-9)

        # -- 6. the grid is conforming, and the seam is not a boundary ---------
        cells = cel_cells(stem)
        faces = bnd_faces(stem)
        use = edge_use(cells)
        odd = {k: v for k, v in use.items() if v not in (1, 2)}
        boundary = [k for k, v in use.items() if v == 1]
        check("6. no cell edge belongs to more than two cells (%s)" % odd, not odd)
        check("6. ...the triangulation is ONE connected component, so the inner and "
              "outer rings are welded along the declared ellipse rather than "
              "touching along it", components(cells, len(nodes)) == 1)
        check("6. ...and its boundary is exactly the .bnd, face for face (%d vs %d)"
              % (len(boundary), len(faces)),
              set(boundary) == {f[0] for f in faces})
        on_ids = {i + 1 for i, p in enumerate(nodes) if off_ellipse(p) < 1e-9}
        on_seam_faces = [f for f in faces if set(f[0]) <= on_ids]
        check("6. ...no .bnd face lies on the declared seam — a face there would be a "
              "wall through the middle of the fluid (%d)" % len(on_seam_faces),
              not on_seam_faces)
        check("6. ...and the patches are the two bound geometries' and nothing else "
              "(%s)" % sorted({f[1] for f in faces}),
              {f[1] for f in faces} == {"wall", "farfield"})

        # -- 7. every refusal, and both warnings -------------------------------
        def off_curve(doc):
            corner(doc, "m1")["xy"] = [0.0, 0.52]

        def both_keys(doc):
            edge(doc, "s0")["follows"] = {"geom": "ellipse_body.dat", "seg": 1}

        def bad_kind(doc):
            edge(doc, "s0")["curve"]["kind"] = "parabola"

        def r_on_ellipse(doc):
            edge(doc, "s0")["curve"]["r"] = 0.75

        def zero_extent(doc):
            edge(doc, "s0")["curve"]["b"] = 0.0

        def same_point(doc):
            corner(doc, "m1")["xy"] = [0.75, 0.0]

        def bad_sweep(doc):
            edge(doc, "s0")["curve"]["sweep"] = "clockwise"

        refusal(tmp, "off_curve", off_curve, "'m1'", "away from it", "nearest point")
        refusal(tmp, "both_keys", both_keys, "'follows'", "'curve'", "ONE question")
        refusal(tmp, "bad_kind", bad_kind, "unknown kind 'parabola'", "'ellipse'")
        refusal(tmp, "r_on_ellipse", r_on_ellipse, "unknown key 'r'")
        refusal(tmp, "zero_extent", zero_extent, "'b' is", "greater than zero")
        refusal(tmp, "same_point", same_point, "same point", "at least two edges")
        refusal(tmp, "bad_sweep", bad_sweep, "unknown sweep 'clockwise'", "'cw'")

        long_doc = fixture()
        edge(long_doc, "s0")["curve"]["sweep"] = "cw"
        rc_l, out_l = run(tmp, write_config(
            os.path.join(tmp, "long.dat"),
            write_topo(os.path.join(tmp, "long.json"), long_doc),
            os.path.join(tmp, "long")))
        check("7. the LONG way round is a WARNING and not a refusal — it is a valid "
              "mesh nobody meant — naming the swept angle and the other sweep "
              "(rc=%d)" % rc_l,
              "LONG way round" in out_l and "270.000 deg" in out_l
              and '"sweep": "ccw"' in out_l)

        wall_doc = fixture()
        del edge(wall_doc, "o0")["binding"]
        edge(wall_doc, "o0")["curve"] = {"kind": "arc", "centre": [0.0, 0.0], "r": 10.0}
        rc_w, out_w = run(tmp, write_config(
            os.path.join(tmp, "wallc.dat"),
            write_topo(os.path.join(tmp, "wallc.json"), wall_doc),
            os.path.join(tmp, "wallc")))
        check("7. a WALL declared as a curve meshes (rc=%d) and says out loud that it "
              "carries no condition of its own, which the 'nothing is bound' warning "
              "would not have said on this mixed topology" % rc_w,
              rc_w == 0 and "carries no boundary condition of its own" in out_w
              and "\"binding\"" in out_w)

    print()
    if failures:
        print("%d check(s) failed" % len(failures))
        for f in failures:
            print("  - " + f)
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
