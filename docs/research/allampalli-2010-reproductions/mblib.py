#!/usr/bin/env python3
"""Shared helpers for the four reproduction harnesses beside this file.

A RESEARCH HARNESS, like ``docs/research/gridpro-blocking-method/``'s. Nothing
shipped reads it; nothing in ``config/``, ``examples/``, ``src/`` or
``include/`` is written or changed by any of the four scripts that import it.

WHAT IS HERE AND WHY IT IS NOT COPIED PER SCRIPT. Four target figures from one
thesis (entry 17 of ``docs/research/gridpro-mesh-samples/``) need the same four
things: a closed body written as a ``.dat`` + ``.meta`` pair, a topology
document whose block rings are oriented for me rather than by hand, a
``MESH_MODE 1`` ``.dat`` config, and one way of running the binary. A second
copy of the ``.meta`` conventions is the failure mode
``tools/PreProcessor/tests/test_multiblock_cgrid_surface.py`` names out loud --
a mesh with corners on the wrong segments and no error at all -- so there is one
copy here and the four scripts call it.

``closed_polyline_meta`` reproduces that file's conventions and nothing else:
the closing duplicate ``loadGeometry`` drops, and a joint belonging to the LATER
segment. It is NOT imported from there because that is a gate, which lives under
``tools/PreProcessor/tests/`` and brings a module path with it; this directory
is research and must stay runnable from the repo root with no sys.path games.
The two are checked against each other by ``selfcheck()`` below instead.
"""

import json
import math
import os
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", ".."))
HERE = os.path.dirname(os.path.abspath(__file__))
BIN = os.path.join(ROOT, "build", "HybMesh2D")


# ── geometry ──────────────────────────────────────────────────────────────

def closed_polyline_meta(segs, bcs, first_id=0):
    """``(dat_text, meta_text)`` for a CLOSED polyline in numbered segments.

    ``segs`` is one list of points per segment, each INCLUDING both endpoints,
    so consecutive segments overlap by exactly one point. Verbatim in behaviour
    with the writer of the same name in
    ``tools/PreProcessor/tests/test_multiblock_cgrid_surface.py``; see the
    module docstring for why it is a second copy and what checks it.
    """
    pts, rows = [], []
    for s, seg in enumerate(segs):
        for j, p in enumerate(seg[:-1]):
            pts.append(p)
            rows.append((first_id + s, 1 if j == 0 else 0))
    pts.append(pts[0])
    rows.append((first_id, 1))
    dat = "".join("%.12f %.12f\n" % p for p in pts)
    meta = ["HYBMESH_META 2", "COUNT %d" % len(pts), "NPIECES 0",
            "NSEGMENTS %d" % len(segs)]
    meta += ["%d %s line" % (first_id + s, bcs[s]) for s in range(len(segs))]
    meta += ["POINTS %d" % len(pts)]
    meta += ["%d %d" % r for r in rows]
    return dat, "\n".join(meta) + "\n"


def write_geom(name, segs, bcs, first_id=0, where=HERE):
    dat, meta = closed_polyline_meta(segs, bcs, first_id=first_id)
    with open(os.path.join(where, name + ".dat"), "w", encoding="utf-8") as f:
        f.write(dat)
    with open(os.path.join(where, name + ".dat.meta"), "w", encoding="utf-8") as f:
        f.write(meta)
    return name + ".dat"


def resample(poly, n):
    """``n + 1`` points at equal ARC LENGTH along an open polyline."""
    cum = [0.0]
    for a, b in zip(poly, poly[1:]):
        cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = cum[-1]
    out = []
    for k in range(n + 1):
        s = total * k / n
        i = min(range(len(cum) - 1), key=lambda j: (cum[j] > s, -cum[j]))
        while i + 1 < len(cum) - 1 and cum[i + 1] < s:
            i += 1
        d = cum[i + 1] - cum[i]
        u = 0.0 if d <= 0 else (s - cum[i]) / d
        out.append((poly[i][0] + u * (poly[i + 1][0] - poly[i][0]),
                    poly[i][1] + u * (poly[i + 1][1] - poly[i][1])))
    return out


def arc_pts(centre, r, deg_a, deg_b, n):
    """``n + 1`` points on a circle from ``deg_a`` to ``deg_b`` inclusive."""
    return [(centre[0] + r * math.cos(math.radians(deg_a + (deg_b - deg_a) * k / n)),
             centre[1] + r * math.sin(math.radians(deg_a + (deg_b - deg_a) * k / n)))
            for k in range(n + 1)]


def naca_half_thickness(x, t):
    """The NACA 4-digit thickness law, CLOSED-trailing-edge variant (-0.1036),
    so ``y(1)`` is exactly 0 and the trailing edge is one point."""
    return (t / 0.2) * (0.2969 * math.sqrt(max(x, 0.0)) - 0.1260 * x
                        - 0.3516 * x * x + 0.2843 * x ** 3 - 0.1036 * x ** 4)


def naca64a010_half_thickness(x):
    """NACA 64A010 half thickness, from the section's published ordinates
    (Abbott & von Doenhoff, Appendix I), linearly interpolated in x/c.

    A 10%-thick laminar-flow section: maximum thickness at 40% chord rather
    than the 4-digit family's 30%, and a SHARP trailing edge. The published
    table ends at y = 0.00105 at x = 1.0, which is the real section's finite
    trailing-edge thickness; the last ordinate is pulled to 0 here so the
    trailing edge is one point, exactly as the 4-digit law above is closed.
    """
    xs = [0.0, 0.005, 0.0075, 0.0125, 0.025, 0.05, 0.075, 0.10, 0.15, 0.20,
          0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75,
          0.80, 0.85, 0.90, 0.95, 1.0]
    ys = [0.0, 0.00804, 0.00969, 0.01225, 0.01688, 0.02327, 0.02805, 0.03199,
          0.03813, 0.04272, 0.04606, 0.04837, 0.04968, 0.04995, 0.04894,
          0.04684, 0.04388, 0.04021, 0.03597, 0.03127, 0.02623, 0.02103,
          0.01582, 0.01062, 0.00541, 0.0]
    x = min(max(x, 0.0), 1.0)
    for i in range(len(xs) - 1):
        if x <= xs[i + 1]:
            u = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + u * (ys[i + 1] - ys[i])
    return 0.0


def cosine_x(n):
    """``n + 1`` chordwise stations, cosine spaced, dense at both ends."""
    return [0.5 * (1.0 - math.cos(math.pi * k / n)) for k in range(n + 1)]


# ── the topology document ─────────────────────────────────────────────────

class Topo(object):
    """Corners, edges and blocks, with the block ring ORIENTED for me.

    The orientation convention is ``.claude/rules/mesher-block-side.md``'s:
    ``[south, east, north, west]``, south/north running i-min to i-max and
    west/east j-min to j-max, with the four corners winding counter-clockwise.
    ``block()`` takes the four CORNERS, winds them counter-clockwise by signed
    area and then reads the four declared edges off that ring, so no script
    that imports this file ever writes a side order by hand. The same shape as
    ``docs/research/gridpro-blocking-method/make_ch.py``'s, which is where it
    was proved; the difference is that this one does not require the south side
    to have been DECLARED forward, because #53 stopped refusing a direction
    deviation and only the ring still has to close.
    """

    def __init__(self):
        self.pos, self.corners, self.edges, self.blocks, self.ends = \
            {}, [], [], [], {}

    def free(self, cid, xy):
        if cid in self.pos:
            return cid
        self.pos[cid] = (float(xy[0]), float(xy[1]))
        self.corners.append({"id": cid, "kind": "free",
                             "xy": [float(xy[0]), float(xy[1])]})
        return cid

    def onbody(self, cid, geom, seg, t, xy):
        if cid in self.pos:
            return cid
        self.pos[cid] = (float(xy[0]), float(xy[1]))
        self.corners.append({"id": cid, "kind": "on_geometry",
                             "geom": geom, "seg": seg, "t": t})
        return cid

    def edge(self, eid, a, b, kind, **kw):
        if eid in self.ends:
            raise SystemExit("edge %s declared twice" % eid)
        e = {"id": eid, "corners": [a, b], "kind": kind}
        for k, v in kw.items():
            if v is not None and v != {} and v is not False:
                e[k] = v
        self.edges.append(e)
        self.ends[eid] = (a, b)
        return eid

    def _side(self, a, b):
        for eid, (x, y) in self.ends.items():
            if (x, y) == (a, b) or (x, y) == (b, a):
                return eid
        raise SystemExit("no edge between %s and %s" % (a, b))

    def block(self, bid, ring):
        p = [self.pos[c] for c in ring]
        area = sum(p[i][0] * p[(i + 1) % 4][1] - p[(i + 1) % 4][0] * p[i][1]
                   for i in range(4))
        if area < 0:
            ring = list(reversed(ring))
        # THE SOUTH SIDE FIXES THE FRAME, and it is read in the direction it
        # was DECLARED (`.claude/rules/mesher-block-side.md`). So the ring is
        # rotated until its first pair is a forward-declared edge; the other
        # three may be declared either way and are traversed as the ring
        # requires. Winding counter-clockwise first is what makes the result
        # an accepted ring rather than a refused clockwise one.
        fwd = {v: k for k, v in self.ends.items()}
        for r in range(4):
            c = ring[r:] + ring[:r]
            if (c[0], c[1]) not in fwd:
                continue
            self.blocks.append({"id": bid, "edges": [
                fwd[(c[0], c[1])], self._side(c[1], c[2]),
                self._side(c[3], c[2]), self._side(c[0], c[3])]})
            return bid
        raise SystemExit(
            "block %s: none of its four sides is declared along the "
            "counter-clockwise ring %s -- flip one edge's corner order"
            % (bid, ring))

    def doc(self):
        return {"format_version": 1, "corners": self.corners,
                "edges": self.edges, "blocks": self.blocks}

    def write(self, name, header="", where=HERE):
        path = os.path.join(where, name)
        body = json.dumps(self.doc(), indent=2)
        with open(path, "w", encoding="utf-8") as f:
            if header:
                f.write("".join("// " + ln + "\n" if ln else "//\n"
                                for ln in header.strip("\n").split("\n")))
            f.write(body + "\n")
        return path

    def stats(self):
        return "%d corners, %d edges, %d blocks" % (
            len(self.corners), len(self.edges), len(self.blocks))


# ── the run ───────────────────────────────────────────────────────────────

def write_conf(name, lines, where=HERE):
    path = os.path.join(where, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def run(conf, quality=True):
    """Run the mesher on ``conf`` from the repo root and return the process."""
    env = dict(os.environ)
    gmsh = subprocess.run(["bash", os.path.join(ROOT, "tools", "scripts",
                                                "gmsh_lib_dir.sh")],
                          capture_output=True, text=True)
    if gmsh.returncode == 0 and gmsh.stdout.strip():
        env["DYLD_LIBRARY_PATH"] = gmsh.stdout.strip()
    if quality:
        env["HYBMESH_MB_QUALITY"] = "1"
    return subprocess.run([BIN, "-conf", conf], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=900)


def report(p):
    """Print the lines of a run worth reading: the quality block, the warnings
    and the error, and nothing else."""
    keep = []
    for ln in (p.stdout + p.stderr).splitlines():
        s = ln.strip()
        if (s.startswith("HYBMESH_MB_QUALITY") or s.startswith("MB_QUALITY")
                or "WARN" in s or "Error" in s or "error" in s
                or "inverted" in s.lower() or "non-orthogonality" in s.lower()
                or s.startswith("[multiblock]") or "first cell" in s.lower()):
            keep.append(s)
    print("\n".join(keep[-60:]))
    print("exit %d" % p.returncode)
    return p.returncode


def selfcheck():
    """``closed_polyline_meta`` against the gate's own copy, when that copy can
    be imported. The module docstring says why this file carries a second one;
    this is what keeps the two from drifting apart in silence."""
    import sys
    sys.path.insert(0, os.path.join(ROOT, "tools", "PreProcessor", "tests"))
    try:
        from test_multiblock_cgrid_surface import closed_polyline_meta as theirs
    except Exception as exc:                       # noqa: BLE001 - research harness
        print("SKIP selfcheck: %s" % exc)
        return True
    segs = [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)], [(1.0, 1.0), (0.0, 1.0),
                                                   (0.0, 0.0)]]
    a = closed_polyline_meta(segs, ["wall", "farfield"], first_id=1)
    b = theirs(segs, ["wall", "farfield"], first_id=1)
    print("selfcheck closed_polyline_meta: %s" % ("SAME" if a == b else "DIFFERENT"))
    return a == b


if __name__ == "__main__":
    raise SystemExit(0 if selfcheck() else 1)


def write_pair(stem, topo_name, geom_lines, bl, extra=(), where=HERE,
               rel=None, title=""):
    """Write the TWO configs every case in this directory needs and return
    ``(tri_conf, quad_conf)``.

    WHY TWO. The shipped default splits every structured quad to two triangles
    (``MB_SPLIT_QUADS 1``) because that is what the solver reads, and the
    quality instrument measures the structured cells either way. The eight
    target figures are structured grids with no diagonals, so a figure drawn
    from the split export would carry a diagonal that is in neither the target
    nor the mesh being compared. The quads config exists ONLY to be drawn, and
    `plot.py` says so in its own docstring.
    """
    rel = rel or os.path.relpath(where, ROOT)
    os.makedirs(os.path.join(where, "out"), exist_ok=True)
    out = []
    for suffix, split in (("", 1), ("_quads", 0)):
        lines = ["# %s" % (title or stem),
                 "# Written by docs/research/allampalli-2010-reproductions/"
                 "make_%s.py -- do not hand-edit." % stem,
                 "",
                 "MESH_MODE 1",
                 "MESH_TOPOLOGY_FILE %s/%s" % (rel, topo_name),
                 ""] + list(geom_lines) + [
                 "",
                 "BL_INITIAL_THICKNESS %g" % bl,
                 "MB_SPLIT_QUADS %d" % split,
                 "BC_GEOM wall"] + list(extra) + [
                 "",
                 "EXPORT_VTK 1",
                 "EXPORT_STARCD 0",
                 "OUTPUT_FILENAME %s/out/%s%s.vtk" % (rel, stem, suffix)]
        out.append(write_conf("%s%s.dat" % (stem, suffix), lines, where=where))
    return out


def quality(p):
    """The ``HYBMESH_MB_QUALITY`` line of a run, as a dict."""
    for ln in reversed((p.stdout + p.stderr).splitlines()):
        if ln.startswith("HYBMESH_MB_QUALITY "):
            d = {}
            for tok in ln.split()[1:]:
                k, _, v = tok.partition("=")
                try:
                    d[k] = float(v)
                except ValueError:
                    d[k] = v
            return d
    return {}


def summarise(p, label):
    q = quality(p)
    if p.returncode != 0 or not q:
        tail = [ln for ln in (p.stdout + p.stderr).splitlines()
                if "ERROR" in ln or "HYBMESH_ERROR" in ln]
        print("%-22s FAILED exit %d" % (label, p.returncode))
        print("\n".join(tail[-4:]))
        return False
    print("%-22s cells %-8d inverted %-4d nonortho max %7.3f mean %6.3f  "
          "wall %.4f%%" % (label, q.get("cells", 0), q.get("inverted", -1),
                           q.get("nonortho_max_deg", -1),
                           q.get("nonortho_mean_deg", -1),
                           100.0 * q.get("wall_first_cell_worst_rel", 0)))
    return q.get("inverted", 1) == 0
