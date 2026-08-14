#!/usr/bin/env python3
"""Regression test: a BL wall meeting a no-BL wall at <= 90 deg must still mesh.

Reported symptom: an internal-flow domain (custom geometry, wall/BL-in) meshed
fine with every segment growing a BL, but marking ONE segment No-BL failed with

    Error: Self-intersection detected in the final front of Geometry 0 ...
    HYBMESH_ERROR 5 BL

The junction cap direction was the cause. A cap has to point INTO the fluid wedge
at the corner; that wedge spans theta (the flow-facing angle from the BL edge to
its no-BL neighbour), while a PERPENDICULAR cap sits at 90 deg from the BL edge.
So for theta <= 90 the perpendicular cap points at or past the no-BL wall and the
column walks straight out of the domain:

  * theta < 90  -> the final front crosses the no-BL surface run  -> exit 5;
  * theta == 90 -> the cap lands exactly ON the wall, so the front doubles back
                   on itself and Gmsh gets a degenerate hole boundary -> exit 6.
                   theta == 90 is a plain RECTANGULAR duct with one wall marked
                   No-BL, i.e. the most ordinary internal-flow case there is.

Such a junction now leans onto the neighbour edge instead (the "slide"), keeping
its perpendicular height and absorbing the no-BL nodes it covers. Cases 2/3/4
(theta > 95) are unchanged, which case_120_still_caps_perpendicular pins down.

Also covered: the BC of a no-BL wall must survive the slide. A boundary edge
lying on a no-BL run is spaced by BL layer height, not by surface point spacing,
so it straddles surface points; the classifier only accepted an edge covered by a
SINGLE reference segment and quietly dropped the rest to the wall default,
relabelling part of a no-BL inlet/outlet.

That positional rescue only works on a STRAIGHT no-BL wall. A slide column is a
straight ray along the FIRST neighbour chord, so on a CURVED wall — any resampled
smooth curve — it drifts off the wall polyline by about a chord sagitta, which is
orders of magnitude more than the 1e-6-of-a-chord that pointOnSegment allows
(measured 6e-8 .. 1.8e-6 against a 2.0e-8 tolerance on a 0.02 resample). Reported
symptom: an internal-flow duct whose inlet was marked No-BL exported a `wall` band
exactly the BL's total height long at each end of the inlet, and the solver duly
ran a wall across those two stretches of the inlet. The slide now carries the
replaced wall's BC onto its own edges by construction; curved_wall_keeps_bc pins
it down, and the straight ducts above pin down that nothing else moved.

Run:  python3 tools/PreProcessor/tests/test_nobl_junction_acute.py
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import math
import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_LIB = os.path.join(_REPO, "build")

# The duct is 4 x 3 with a BL total height of ~0.21, so the layer is thin
# relative to every feature: any failure here is the junction, not the BL size.
DUCT_W, DUCT_H = 4.0, 3.0
failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def write_duct(path, theta_deg, bc_labels=None):
    """A closed CCW quad duct whose RIGHT wall is the only no-BL segment, tilted
    so the bottom-wall junction angle is exactly `theta_deg`. Returns its points.

    Segments: 1 bottom (BL), 2 right (no-BL), 3 top (BL), 4 left (BL). The shared
    corner belongs to the segment STARTING there, matching the resampler, so this
    exercises the production path rather than a contrived tagging.
    """
    dx = DUCT_H / math.tan(math.radians(theta_deg))
    verts = [(0.0, 0.0), (DUCT_W, 0.0), (DUCT_W - dx, DUCT_H), (0.0, DUCT_H)]
    grow = [1, 0, 1, 1]
    pts, seg, corner = [], [], []
    for j in range(4):
        ax, ay = verts[j]
        bx, by = verts[(j + 1) % 4]
        n = max(6, int(math.hypot(bx - ax, by - ay) * 12))
        for m in range(n):
            t = m / n
            pts.append((ax + (bx - ax) * t, ay + (by - ay) * t))
            seg.append(j + 1)
            corner.append(1 if m == 0 else 0)
    with open(path, "w") as f:
        # 10 decimals: at 6 the polygon itself wiggles by ~5e-7, which would show
        # up as "nodes outside the domain" in the containment check below.
        f.write("".join(f"{x:.10f} {y:.10f}\n" for x, y in pts))
        f.write(f"{pts[0][0]:.10f} {pts[0][1]:.10f}\n")
    labels = bc_labels or ["wall"] * 4
    with open(path + ".meta", "w") as f:
        f.write(f"HYBMESH_META 3\nCOUNT {len(pts)}\nNPIECES 0\nNSEGMENTS 4\n")
        for j in range(4):
            f.write(f"{j + 1} {labels[j]} polyline {grow[j]}\n")
        f.write(f"POINTS {len(pts)}\n")
        for i in range(len(pts)):
            f.write(f"{seg[i]} {corner[i]}\n")
        if bc_labels:
            for lab, bc in zip(labels, ["wall", "outlet", "wall", "inlet"]):
                f.write(f"GROUP_BC {lab} {bc}\n")
    return pts, verts


def arc_samples(a, apex, b, n):
    """`n` points from `a` towards `b` (excluding `b`) along the circle through the
    three points, taking the side `apex` is on. Signed-bulge safe."""
    (ax, ay), (px, py), (bx, by) = a, apex, b
    d = 2.0 * (ax * (py - by) + px * (by - ay) + bx * (ay - py))
    qa, qp, qb = ax * ax + ay * ay, px * px + py * py, bx * bx + by * by
    ux = (qa * (py - by) + qp * (by - ay) + qb * (ay - py)) / d
    uy = (qa * (bx - px) + qp * (ax - bx) + qb * (px - ax)) / d
    R = math.dist((ux, uy), a)
    a0 = math.atan2(ay - uy, ax - ux)
    turn = (math.atan2(by - uy, bx - ux) - a0) % (2.0 * math.pi)
    if (math.atan2(py - uy, px - ux) - a0) % (2.0 * math.pi) > turn:
        turn -= 2.0 * math.pi                       # the apex is the other way round
    return [(ux + R * math.cos(a0 + turn * m / n),
             uy + R * math.sin(a0 + turn * m / n)) for m in range(n)], abs(turn) * R


def write_curved_duct(path, bulge=-0.15, bc_labels=("bot", "rgt", "top", "lft")):
    """The theta=90 duct with its no-BL RIGHT wall replaced by a shallow circular
    ARC of the given signed `bulge` (negative = bowed into the fluid). Segments and
    BC labels are unchanged.

    The curvature is the whole point: it is what makes the slide column leave the
    wall polyline, and a straight wall cannot exercise that at all. The arc is
    symmetric about the duct's mid-line, so BOTH of its junctions move the same way
    — bowing INTO the fluid closes them to just under 90 deg, which is the slide.
    (Bowing outward opens both to ~101 deg and gets two perpendicular caps instead,
    exercising nothing new.)

    Returns (outline, arc_polyline) — the arc in wall order, including the top
    corner that closes it, so it can be used as the BC probe.
    """
    verts = [(0.0, 0.0), (DUCT_W, 0.0), (DUCT_W, DUCT_H), (0.0, DUCT_H)]
    grow = [1, 0, 1, 1]
    pts, seg, corner = [], [], []
    for j in range(4):
        if j == 1:                                    # the arc (no-BL) wall
            apex = (DUCT_W + bulge, DUCT_H / 2.0)
            _, arc_len = arc_samples(verts[1], apex, verts[2], 2)   # length only
            samples, _ = arc_samples(verts[1], apex, verts[2],
                                     max(6, int(arc_len * 12)))
        else:
            ax, ay = verts[j]
            bx, by = verts[(j + 1) % 4]
            n = max(6, int(math.hypot(bx - ax, by - ay) * 12))
            samples = [(ax + (bx - ax) * m / n, ay + (by - ay) * m / n) for m in range(n)]
        for m, p in enumerate(samples):
            pts.append(p)
            seg.append(j + 1)
            corner.append(1 if m == 0 else 0)
    with open(path, "w") as f:
        f.write("".join(f"{x:.10f} {y:.10f}\n" for x, y in pts))
        f.write(f"{pts[0][0]:.10f} {pts[0][1]:.10f}\n")
    with open(path + ".meta", "w") as f:
        f.write(f"HYBMESH_META 3\nCOUNT {len(pts)}\nNPIECES 0\nNSEGMENTS 4\n")
        for j in range(4):
            f.write(f"{j + 1} {bc_labels[j]} smooth {grow[j]}\n")
        f.write(f"POINTS {len(pts)}\n")
        for i in range(len(pts)):
            f.write(f"{seg[i]} {corner[i]}\n")
        for lab, bc in zip(bc_labels, ["wall", "outlet", "wall", "inlet"]):
            f.write(f"GROUP_BC {lab} {bc}\n")
    arc = [p for p, s in zip(pts, seg) if s == 2] + [verts[2]]
    return pts, arc


def write_wedge(path, theta_deg, nbr_len=2.0):
    """A roomy domain holding ONE sharp BL/no-BL wedge, so a failure there can only
    come from the wedge. Bottom wall (BL) meets a short no-BL edge leaning back over
    it at `theta_deg`; the far side of the domain is wide open."""
    a = math.radians(180.0 - theta_deg)
    b = (6.0, 0.0)
    c = (b[0] + nbr_len * math.cos(a), b[1] + nbr_len * math.sin(a))
    verts = [(0.0, 0.0), b, c, (c[0], 4.0), (0.0, 4.0)]
    grow = [1, 0, 1, 1, 1]
    pts, seg, corner = [], [], []
    for j in range(len(verts)):
        px, py = verts[j]
        qx, qy = verts[(j + 1) % len(verts)]
        n = max(8, int(math.hypot(qx - px, qy - py) * 12))
        for m in range(n):
            t = m / n
            pts.append((px + (qx - px) * t, py + (qy - py) * t))
            seg.append(j + 1)
            corner.append(1 if m == 0 else 0)
    with open(path, "w") as f:
        f.write("".join(f"{x:.10f} {y:.10f}\n" for x, y in pts))
        f.write(f"{pts[0][0]:.10f} {pts[0][1]:.10f}\n")
    with open(path + ".meta", "w") as f:
        f.write(f"HYBMESH_META 3\nCOUNT {len(pts)}\nNPIECES 0\nNSEGMENTS {len(verts)}\n")
        for j in range(len(verts)):
            f.write(f"{j + 1} wall polyline {grow[j]}\n")
        f.write(f"POINTS {len(pts)}\n")
        for i in range(len(pts)):
            f.write(f"{seg[i]} {corner[i]}\n")
    return b


def write_isolated_corner_duct(path):
    """A duct with an ISOLATED BL corner: one BL node whose BOTH neighbours are no-BL.

    Every other case in this file marks exactly ONE segment no-BL (`grow=[1,0,1,1]`),
    so every junction node keeps a BL neighbour on one side. The generator has a
    separate branch for the case where BOTH neighbours are no-BL — it must keep the
    perpendicular cap direction chosen by the base detection instead of splitting
    the corner with a bisector — and nothing exercised it.

    Getting there needs BOTH halves, and the second one is not obvious. The TOP
    segment emits only its starting corner, so in the ring that node is flanked by
    the right wall's last point and the left wall's first point — but `src/cli.cpp`'s
    corner rescue (`if (prevBL || nextBL) cn.skipBL = false;`) then promotes the
    top-LEFT corner back to BL because its neighbour grows one, and the isolated
    node is left with a BL neighbour after all. The rescue is gated on `isCorner`,
    so the top-left split is declared SMOOTH (`corner = 0`) — which is exactly what
    the resampler emits for a segment boundary that is not a sharp vertex. Verified
    with a probe in the branch itself: without this it never fires and the node is
    classified case 1 (slide) instead.

    The BOTTOM wall still grows a full BL, so this is a real mesh with an isolated
    corner in it rather than a degenerate one-column model.

    Segments: 1 bottom (BL), 2 right (no-BL), 3 top (BL, one point), 4 left (no-BL).
    Returns (points, verts, isolated_corner).
    """
    verts = [(0.0, 0.0), (DUCT_W, 0.0), (DUCT_W, DUCT_H), (0.0, DUCT_H)]
    grow = [1, 0, 1, 0]
    pts, seg, corner = [], [], []
    for j in range(4):
        ax, ay = verts[j]
        bx, by = verts[(j + 1) % 4]
        # The top segment (j == 2) is the isolated one: its ONLY point is its start.
        n = 1 if j == 2 else max(6, int(math.hypot(bx - ax, by - ay) * 12))
        for m in range(n):
            t = m / n
            pts.append((ax + (bx - ax) * t, ay + (by - ay) * t))
            seg.append(j + 1)
            # j == 3 is the top-left split: smooth, so the corner rescue skips it.
            corner.append(1 if (m == 0 and j != 3) else 0)
    with open(path, "w") as f:
        f.write("".join(f"{x:.10f} {y:.10f}\n" for x, y in pts))
        f.write(f"{pts[0][0]:.10f} {pts[0][1]:.10f}\n")
    with open(path + ".meta", "w") as f:
        f.write(f"HYBMESH_META 3\nCOUNT {len(pts)}\nNPIECES 0\nNSEGMENTS 4\n")
        for j in range(4):
            f.write(f"{j + 1} wall polyline {grow[j]}\n")
        f.write(f"POINTS {len(pts)}\n")
        for i in range(len(pts)):
            f.write(f"{seg[i]} {corner[i]}\n")
    return pts, verts, verts[2]


def run(tmp, dat, name, starcd=False, timeout=300):
    """Run HybMesh2D on the duct; returns (rc, stdout+stderr, output stem)."""
    out = os.path.join(tmp, name)
    conf = os.path.join(tmp, name + ".conf")
    with open(conf, "w") as f:
        f.write(
            f"DOMAIN_FILE {dat} bl\n"
            "AUTO_SURFACE_SIZE 1\nSURFACE_MESH_SIZE 0.1\nFARFIELD_MESH_SIZE 1\n"
            "BL_INITIAL_THICKNESS 0.01\nBL_GROWTH_RATE 1.2\nBL_LAYERS 5\n"
            "BL_TRANSITION_LAYERS 3\nBL_AUTO_TRANSITION_LAYERS 2\n"
            "BL_TRANSITION_GROWTH_RATE 1.2\nBL_TRANSITION_BUFFER 2\n"
            "FARFIELD_GROWTH_RATE 0.1\nGMSH_ALGORITHM 6\nGMSH_OPTIMIZE 1\n"
            "BL_CONVEX_METHOD 2\nBL_CONCAVE_METHOD 5\nBL_JUNCTION_METHOD 1\n"
            f"EXPORT_VTK 1\nEXPORT_STARCD {1 if starcd else 0}\n"
            f"OUTPUT_FILENAME {out}.vtk\n"
        )
    env = dict(os.environ, DYLD_LIBRARY_PATH=_LIB, LD_LIBRARY_PATH=_LIB,
               HYBMESH_JUNC_DEBUG="1")
    try:
        p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=env,
                           capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr, out
    except subprocess.TimeoutExpired:
        return None, f"<timed out after {timeout}s>", out


def junctions(log):
    """[(theta, case), ...] from the HYBMESH_JUNC_DEBUG trace."""
    return [(float(t), int(c))
            for t, c in re.findall(r"theta=([\d.]+) case=(\d)", log)]


def read_vtk_points(path):
    with open(path) as f:
        txt = f.read().split("\n")
    i = 0
    while i < len(txt):
        s = txt[i].split()
        if s and s[0] == "POINTS":
            n, vals = int(s[1]), []
            i += 1
            while len(vals) < 3 * n:
                vals += [float(v) for v in txt[i].split()]
                i += 1
            return [(vals[3 * k], vals[3 * k + 1]) for k in range(n)]
        i += 1
    return []


def outside_depth(points, poly):
    """Deepest excursion of any mesh node past the domain outline (0 = all in)."""
    def inside(p):
        x, y = p
        hit = False
        for j in range(len(poly)):
            ax, ay = poly[j]
            bx, by = poly[(j + 1) % len(poly)]
            if (ay > y) != (by > y) and x < ax + (y - ay) / (by - ay) * (bx - ax):
                hit = not hit
        return hit

    def dist(p):
        best = float("inf")
        for j in range(len(poly)):
            ax, ay = poly[j]
            bx, by = poly[(j + 1) % len(poly)]
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
            best = min(best, math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy)))
        return best

    return max((dist(p) for p in points if not inside(p)), default=0.0)


def wall_faces(stem, ax, ay, bx, by):
    """[(t_along_wall_min, t_max, patch)] for .bnd faces lying on the given wall."""
    verts = {}
    with open(stem + ".vrt") as f:
        for line in f:
            s = line.split()
            if len(s) >= 4:
                try:
                    verts[int(s[0])] = (float(s[1]), float(s[2]))
                except ValueError:
                    pass
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    out = []
    with open(stem + ".bnd") as f:
        for line in f:
            s = line.split()
            if len(s) < 7:
                continue
            try:
                ids = [int(v) for v in s[1:5]]
            except ValueError:
                continue
            ps = [verts[i] for i in ids if i in verts]
            if not ps:
                continue
            ts, offs = [], []
            for px, py in ps:
                ts.append((px - ax) * ux + (py - ay) * uy)
                offs.append(abs((px - ax) * -uy + (py - ay) * ux))
            if max(offs) < 1e-6 and min(ts) > -1e-6 and max(ts) < L + 1e-6:
                out.append((min(ts), max(ts), s[-1]))
    return sorted(out)


def polyline_faces(stem, poly, tol=0.0025):
    """[(s_min, s_max, patch)] for .bnd faces lying ON the polyline `poly`, keyed by
    arc-length position along it.

    Distance is measured to the polyline as a whole rather than to one chord, so a
    face whose nodes sit a chord sagitta off it is still recognised as being on that
    wall — which is the entire point: drifting off the polyline must not be allowed
    to change a face's BC. `tol` sits well above that drift (~7e-4 here) and well
    below the first BL front (0.01 from the wall), so nothing off-wall is selected.
    """
    verts = {}
    with open(stem + ".vrt") as f:
        for line in f:
            s = line.split()
            if len(s) >= 4:
                try:
                    verts[int(s[0])] = (float(s[1]), float(s[2]))
                except ValueError:
                    pass
    cum = [0.0]
    for k in range(1, len(poly)):
        cum.append(cum[-1] + math.dist(poly[k - 1], poly[k]))

    def project(p):
        """(distance, arc position) of p against the whole polyline."""
        best = (float("inf"), 0.0)
        for k in range(len(poly) - 1):
            ax, ay = poly[k]
            bx, by = poly[k + 1]
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
            d = math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))
            if d < best[0]:
                best = (d, cum[k] + t * math.sqrt(L2))
        return best

    out = []
    with open(stem + ".bnd") as f:
        for line in f:
            s = line.split()
            if len(s) < 7:
                continue
            try:
                ids = [int(v) for v in s[1:5]]
            except ValueError:
                continue
            ps = [verts[i] for i in ids if i in verts]
            if not ps:
                continue
            pr = [project(p) for p in ps]
            if max(d for d, _ in pr) < tol:
                out.append((min(a for _, a in pr), max(a for _, a in pr), s[-1]))
    return sorted(out)


def ray_nodes(points, base, tangent, direction):
    """Sorted distances of every mesh node lying on the ray `base` + t*direction.

    A BL column is a straight ray, so a tight lateral tolerance picks out its
    nodes. On the junction ray the list also holds the absorbed no-BL surface
    points and the far-field nodes further up the same wall, so callers match
    against an expected height rather than taking the n-th entry.
    """
    along = []
    for px, py in points:
        dx, dy = px - base[0], py - base[1]
        a = dx * direction[0] + dy * direction[1]
        lat = abs(dx * tangent[0] + dy * tangent[1])
        if lat < 1e-9 and a > 1e-12:
            along.append(a)
    return sorted(along)


def main():
    if not os.path.exists(_BIN):
        print(f"SKIP HybMesh2D not built ({_BIN})")
        return 0

    tmp = tempfile.mkdtemp(prefix="hybmesh_junction_")
    quiet_logs = []          # runs whose junctions are all comfortably wide

    # --- 1. theta == 90: a plain rectangular duct, one wall No-BL -------------
    dat = os.path.join(tmp, "duct90.dat")
    _, verts = write_duct(dat, 90.0)
    rc, log, stem = run(tmp, dat, "duct90")
    quiet_logs.append(log)
    check("theta=90 rectangular duct meshes (was: exit 6, degenerate hole)", rc == 0)
    check("theta=90 junctions slide onto the no-BL wall, not cap into it",
          junctions(log) and all(c == 1 for _, c in junctions(log)))
    check("theta=90 wrote a mesh", os.path.exists(stem + ".vtk"))
    if os.path.exists(stem + ".vtk"):
        d = outside_depth(read_vtk_points(stem + ".vtk"), verts)
        check(f"theta=90 keeps every node inside the domain (worst {d:.2e})", d < 1e-9)

    # --- 2. theta < 90: the reported acute junction ---------------------------
    dat = os.path.join(tmp, "duct85.dat")
    _, verts = write_duct(dat, 85.0)
    rc, log, stem = run(tmp, dat, "duct85")
    quiet_logs.append(log)
    check("theta=85 acute junction meshes (was: exit 5, self-intersection)", rc == 0)
    check("theta=85 reports no self-intersection", "Self-intersection" not in log)
    acute = [(t, c) for t, c in junctions(log) if t < 90.0]
    check("theta=85 junction is a slide", acute and all(c == 1 for _, c in acute))
    pts = read_vtk_points(stem + ".vtk") if os.path.exists(stem + ".vtk") else []
    check("theta=85 wrote a mesh", bool(pts))
    if pts:
        d = outside_depth(pts, verts)
        check(f"theta=85 keeps every node inside the domain (worst {d:.2e})", d < 1e-9)

        # The slide must not collapse or taper the layer: the column standing at
        # the junction has to reach the same PERPENDICULAR height as one well
        # inside the BL run. The junction column leans along the no-BL wall, so
        # measure it along that wall and project.
        m = re.search(r"Generating (\d+) boundary layers", log)
        nlayers = int(m.group(1)) if m else 0
        # Interior reference column: a bottom-wall node far from either corner,
        # so it is a plain perpendicular column of exactly nlayers nodes.
        interior_col = ray_nodes(pts, (DUCT_W * 0.5, 0.0), (1.0, 0.0), (0.0, 1.0))
        d_total = interior_col[nlayers - 1] if len(interior_col) >= nlayers else 0.0
        # The junction column leans along the no-BL wall; measure along that wall
        # and project back onto the BL wall's normal.
        corner, wall = verts[1], verts[2]       # the acute corner, then up the wall
        wl = math.dist(corner, wall)
        e = ((wall[0] - corner[0]) / wl, (wall[1] - corner[1]) / wl)
        sin_t = math.sin(math.radians(85.0))
        slide_col = [a * sin_t for a in ray_nodes(pts, corner, (-e[1], e[0]), e)]
        check(f"the slide reaches the BL's full perpendicular height "
              f"(D_total {d_total:.5f} over {nlayers} layers)",
              d_total > 0 and slide_col
              and min(abs(p - d_total) for p in slide_col) < 0.02 * d_total)
        # What a taper-to-zero junction destroys, and what the solver actually
        # needs: the FIRST cell height must be unchanged at the junction.
        check(f"the first cell height survives at the junction "
              f"(got {slide_col[0]:.5f} vs {interior_col[0]:.5f})",
              slide_col and abs(slide_col[0] - interior_col[0]) < 0.05 * interior_col[0])

    # --- 3. theta > 95 still caps perpendicular (cases 2/3/4 untouched) -------
    dat = os.path.join(tmp, "duct120.dat")
    _, verts = write_duct(dat, 120.0)
    rc, log, stem = run(tmp, dat, "duct120")
    quiet_logs.append(log)
    check("theta=120 duct meshes", rc == 0)
    obtuse = [(t, c) for t, c in junctions(log) if t > 95.0]
    check("an obtuse junction still gets the perpendicular cap, not a slide",
          obtuse and all(c == 2 for _, c in obtuse))

    # --- 4. a no-BL wall keeps its BC across the slide ------------------------
    dat = os.path.join(tmp, "ductbc.dat")
    _, verts = write_duct(dat, 90.0, bc_labels=["bot", "rgt", "top", "lft"])
    rc, log, stem = run(tmp, dat, "ductbc", starcd=True)
    quiet_logs.append(log)
    check("the BC duct meshes", rc == 0)
    if os.path.exists(stem + ".bnd"):
        faces = wall_faces(stem, verts[1][0], verts[1][1], verts[2][0], verts[2][1])
        wrong = [f for f in faces if f[2] != "outlet"]
        check(f"every .bnd face on the no-BL outlet wall is 'outlet' "
              f"({len(faces)} faces, {len(wrong)} mislabelled)",
              faces and not wrong)
        # The slide covers the first BL height of the wall; that stretch is
        # exactly what used to fall through to the wall default.
        covered = [f for f in faces if f[1] <= 0.25]
        check("the slid stretch nearest the corner is covered by outlet faces",
              covered and all(f[2] == "outlet" for f in covered))

    # --- 4b. a CURVED no-BL wall keeps its BC across the slide ----------------
    # The reported bug. The slide column is a straight ray, so on a curved wall its
    # nodes leave the wall polyline; positional classification then rejected them and
    # the band the slide covers — exactly the BL's total height at each junction —
    # exported as the wall default. The BC now rides on the edges by construction.
    dat = os.path.join(tmp, "ductcurved.dat")
    outline, arc = write_curved_duct(dat)
    rc, log, stem = run(tmp, dat, "ductcurved", starcd=True)
    quiet_logs.append(log)
    check("a duct with a CURVED no-BL wall meshes", rc == 0)
    slides = [(t, c) for t, c in junctions(log) if c == 1]
    check("the curved wall's acute end still slides", bool(slides))
    if os.path.exists(stem + ".vtk"):
        d = outside_depth(read_vtk_points(stem + ".vtk"), outline)
        check(f"the curved duct keeps every node inside the domain (worst {d:.2e})",
              d < 1e-9)
    if os.path.exists(stem + ".bnd"):
        faces = polyline_faces(stem, arc)
        wrong = [f for f in faces if f[2] != "outlet"]
        # The selector must actually find the wall, or "no mislabelled faces" is
        # vacuous: one face per arc point is the floor (the slide subdivides further).
        check(f"the arc probe finds the whole no-BL wall ({len(faces)} faces "
              f"for {len(arc) - 1} arc chords)", len(faces) >= len(arc) - 1)
        check(f"every .bnd face on the CURVED no-BL outlet wall is 'outlet' "
              f"({len(faces)} faces, {len(wrong)} mislabelled)",
              faces and not wrong)
        # Name the failure mode explicitly: the band the slide covers, at the acute
        # end (arc position 0). D_total is ~0.165 over 5 BL + 3 transition layers.
        slid = [f for f in faces if f[1] <= 0.2]
        check(f"the slid band at the curved acute corner is outlet, not wall "
              f"({len(slid)} faces, {sum(1 for f in slid if f[2] != 'outlet')} wrong)",
              slid and all(f[2] == "outlet" for f in slid))

    # --- 5. a wedge too sharp to grade is CALLED OUT, not left to fail blind ---
    # A slide only works while the concave blend can lean the squeezed columns over:
    # the corner compromises D_total/tan(theta) of wall against a blend reach of
    # influence*D_total, so the limit is tan(theta)*influence ~ 1 — at the default
    # 2.5 that is 21.8 deg, and the mesher does break between 22 and 21. The warning
    # must therefore fire on every failing wedge, and stay quiet on healthy ones.
    dat = os.path.join(tmp, "wedge20.dat")
    apex = write_wedge(dat, 20.0)
    rc, log, stem = run(tmp, dat, "wedge20")
    warned = [ln for ln in log.splitlines() if "Very sharp BL/no-BL wedge" in ln]
    check("a 20 deg wedge (past the limit) is warned about before it fails",
          bool(warned))
    check(f"the warning names the offending corner ({apex[0]:g}, {apex[1]:g})",
          any(f"({apex[0]:g}, {apex[1]:g})" in ln for ln in warned))
    check("the warning says which knobs move it",
          any("BL_INITIAL_THICKNESS" in ln and "BL_CONCAVE_INFLUENCE_MULTIPLIER" in ln
              for ln in warned))
    # Whether 20 deg meshes depends on the geometry; what must never happen is a
    # failure with no warning pointing at the wedge.
    check("a sharp-wedge failure is never silent",
          rc == 0 or bool(warned))

    dat = os.path.join(tmp, "wedge45.dat")
    write_wedge(dat, 45.0)
    rc, log, stem = run(tmp, dat, "wedge45")
    check("a 45 deg wedge meshes", rc == 0)
    check("a wedge the blend can absorb is NOT warned about",
          "Very sharp BL/no-BL wedge" not in log)
    check("none of the healthy junctions above were warned about either",
          all("Very sharp" not in s for s in quiet_logs))

    # ── isolated BL corner: BOTH neighbours no-BL ────────────────────────────
    # The generator has a branch for a BL node whose BOTH neighbours are no-BL
    # ("an isolated BL corner ... a rare/degenerate configuration we do not
    # special-case further"). Nothing exercised it; this does — and what it
    # documents is that reaching the branch means the run CANNOT produce a mesh.
    #
    # The isolated node grows a single full-height column but registers no lateral
    # column, so the final front ring runs out along that column and back down the
    # same one: a zero-width spike. Gmsh gets a hole boundary that doubles back and
    # triangulates nothing. Measured: exit 6, "Gmsh produced an empty far-field
    # mesh (0 triangles)".
    #
    # So this is pinned as a CLEAN FAILURE, not as a working case. What it protects
    # is the failure MODE: a future change here must not turn a diagnosed exit into
    # a hang, a crash, or — worst — a silently exported empty mesh. It deliberately
    # does not assert the column's direction: with no mesh written there is nothing
    # to measure, which is exactly why this branch cannot serve as a regression
    # guard for the classifyJunctions extraction (see the note in that commit).
    dat = os.path.join(tmp, "isolated.dat")
    _, iso_verts, iso = write_isolated_corner_duct(dat)
    rc, log, stem = run(tmp, dat, "isolated")
    check("an isolated BL corner fails cleanly rather than hanging or crashing",
          rc == 6)
    check("...naming the empty far-field mesh as the reason",
          "empty far-field mesh" in log)
    check("...and exports nothing rather than an empty mesh",
          not os.path.exists(stem + ".vtk"))
    check("...having reached the junction stage at all (the tally is printed)",
          "BL/no-BL junctions" in log)

    print()
    print("RESULT:", "ALL PASS" if not failures else f"{len(failures)} FAILED: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
