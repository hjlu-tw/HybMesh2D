#!/usr/bin/env python3
"""Quick legacy-VTK unstructured mesh viewer -> PNG (matplotlib Agg).
Draws cell edges; optionally a zoom box. Usage:
  view_mesh_vtk.py <mesh.vtk> <out.png> [xmin xmax ymin ymax]
"""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

def read_vtk(path):
    pts, cells = [], []
    with open(path) as f:
        toks = f.read().split()
    i = 0
    n = len(toks)
    while i < n:
        t = toks[i]
        if t == "POINTS":
            npts = int(toks[i+1]); i += 3  # skip dtype
            for _ in range(npts):
                x, y, z = float(toks[i]), float(toks[i+1]), float(toks[i+2])
                pts.append((x, y)); i += 3
            continue
        if t == "CELLS":
            ncells = int(toks[i+1]); total = int(toks[i+2]); i += 3
            end = i + total
            while i < end:
                cnt = int(toks[i]); i += 1
                cells.append([int(toks[i+j]) for j in range(cnt)]); i += cnt
            continue
        i += 1
    return pts, cells

def main():
    mesh, out = sys.argv[1], sys.argv[2]
    box = [float(v) for v in sys.argv[3:7]] if len(sys.argv) >= 7 else None
    # optional 7th arg: number of trailing far-field triangles (colored blue);
    # earlier area cells are BL (orange). Far-field cells are appended last.
    n_far = int(sys.argv[7]) if len(sys.argv) >= 8 else 0
    pts, cells = read_vtk(mesh)
    from matplotlib.patches import Polygon as MplPoly
    from matplotlib.collections import PatchCollection
    tri_cells = [(idx, c) for idx, c in enumerate(cells) if len(c) >= 3]
    n_tri = len(tri_cells)
    bl_patches, ff_patches = [], []
    for k, (idx, c) in enumerate(tri_cells):
        poly = [pts[v] for v in c]
        if n_far and k >= n_tri - n_far:
            ff_patches.append(MplPoly(poly, closed=True))
        else:
            bl_patches.append(MplPoly(poly, closed=True))
    segs = []
    for c in cells:
        m = len(c)
        if m < 2: continue
        for j in range(m):
            a = pts[c[j]]; b = pts[c[(j+1) % m]]
            segs.append([a, b])
    fig, ax = plt.subplots(figsize=(11, 9), dpi=140)
    if bl_patches:
        ax.add_collection(PatchCollection(bl_patches, facecolor="#f4a742", edgecolor="none", alpha=0.85))
    if ff_patches:
        ax.add_collection(PatchCollection(ff_patches, facecolor="#bcd6f0", edgecolor="none", alpha=0.7))
    ax.add_collection(LineCollection(segs, colors="#33393f", linewidths=0.4))
    ax.set_aspect("equal")
    if box:
        ax.set_xlim(box[0], box[1]); ax.set_ylim(box[2], box[3])
    else:
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        ax.set_xlim(min(xs), max(xs)); ax.set_ylim(min(ys), max(ys))
    ax.set_title(f"{mesh}  ({len(pts)} pts, {len(cells)} cells)")
    fig.tight_layout(); fig.savefig(out); print("wrote", out)

if __name__ == "__main__":
    main()
