#!/usr/bin/env python3
"""Generate BL/non-BL junction test geometries (.dat + .meta v3) for the 4-case
angle-driven junction scheme. Each geometry is a closed polygon; per edge we set a
grow-BL flag. The shared corner is assigned to the segment STARTING there (the
resampler's convention) so this exercises the production code path.

Usage: python3 tools/scripts/gen_junction_tests.py <out_dir>
"""
import math, os, sys

def densify(verts, grow, pts_per_unit=12, min_pts=6):
    """verts: list of (x,y) polygon vertices (open, CCW). grow: per-edge 0/1.
    Returns (points, seg_ids, corner_flags). Corner (start vertex) belongs to the
    segment starting there; interiors carry that segment's id too."""
    pts, seg, corner = [], [], []
    k = len(verts)
    for j in range(k):
        a = verts[j]
        b = verts[(j + 1) % k]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(min_pts, int(L * pts_per_unit))
        # include start vertex + interiors, exclude end vertex (next seg's start)
        for m in range(n):
            t = m / n
            pts.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            seg.append(j + 1)                 # 1-based segment id
            corner.append(1 if m == 0 else 0)  # start vertex is a corner
    return pts, seg, corner

def write_case(out_dir, name, verts, grow):
    pts, seg, corner = densify(verts, grow)
    N = len(pts)
    dat = os.path.join(out_dir, name + ".dat")
    with open(dat, "w") as f:
        for (x, y) in pts:
            f.write(f"{x:.6f} {y:.6f}\n")
        f.write(f"{pts[0][0]:.6f} {pts[0][1]:.6f}\n")  # closing repeat -> loop
    with open(dat + ".meta", "w") as f:
        f.write("HYBMESH_META 3\n")
        f.write(f"COUNT {N}\n")
        f.write("NPIECES 0\n")
        k = len(verts)
        f.write(f"NSEGMENTS {k}\n")
        for j in range(k):
            f.write(f"{j+1} wall polyline {grow[j]}\n")
        f.write(f"POINTS {N}\n")
        for i in range(N):
            f.write(f"{seg[i]} {corner[i]}\n")
    print(f"  wrote {dat} ({N} pts, {k} segs, grow={grow})")

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "examples/geometries/junction_tests"
    os.makedirs(out, exist_ok=True)

    # Case 2 (theta=180 straight split, + theta=270 convex): thin plate, top edge
    # split at midpoint; only the top-front segment grows BL.
    #  verts CCW: bottom-left, bottom-right, top-right, top-mid, top-left
    write_case(out, "jt_case2_plate",
               [(0,0),(4,0),(4,0.3),(2,0.3),(0,0.3)],
               grow=[0,0,0,1,0])   # E3 = top-front (2,0.3)->(0,0.3) is BL

    # Case 3 (theta=300): equilateral wedge, apex 60 deg; upper edge grows BL.
    h = 3*math.tan(math.radians(30))
    write_case(out, "jt_case3_wedge",
               [(0,0),(3,h),(3,-h)],
               grow=[1,0,0])       # E0 = apex->upper is BL

    # Case 4 (theta=340 at apex) + case 3 (theta=280 at base): thin wedge apex 20 deg.
    h2 = 5*math.tan(math.radians(10))
    write_case(out, "jt_case4_sharp",
               [(0,0),(5,h2),(5,-h2)],
               grow=[1,0,0])       # E0 = apex->upper is BL

    # Case 1 (theta=90 concave reflex) + case 2 (theta=270 convex): L-shape, the
    # vertical inner edge grows BL and slides along the horizontal non-BL edge.
    write_case(out, "jt_case1_lshape",
               [(0,0),(3,0),(3,1),(1,1),(1,3),(0,3)],
               grow=[0,0,0,1,0,0]) # E3 = (1,1)->(1,3) is BL

    # Case 1 SHARP concave (theta=60) to show the tilted concave blend: a 60-deg
    # V-notch cut into the top of a rectangle; apex (3,1), walls at +/-30 from
    # vertical. Left notch wall grows BL and slides along the non-BL right wall,
    # blending nearby columns from perpendicular toward the right wall near the apex.
    hw = (3 - 1) * math.tan(math.radians(30))   # half-width at the mouth (y=3)
    write_case(out, "jt_case1_notch60",
               [(0,0),(6,0),(6,3),(3+hw,3),(3,1),(3-hw,3),(0,3)],
               grow=[0,0,0,0,1,0,0]) # E4 = apex(3,1)->left-mouth is BL

if __name__ == "__main__":
    main()
