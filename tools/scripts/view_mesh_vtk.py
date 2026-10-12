#!/usr/bin/env python3
"""Quick legacy-VTK unstructured mesh viewer -> PNG (matplotlib Agg).

Draws cell edges; optionally a zoom box. Usage:
  view_mesh_vtk.py <mesh.vtk> <out.png> [xmin xmax ymin ymax] [--no-blocks]

A MESH_MODE 1 file carries a per-cell ``SCALARS block int 1`` section (#106).
When it is there, every cell is filled by the block it came from and the edges
BETWEEN two blocks are drawn heavy, so "which block is this cell in" is answered
by looking rather than by loading the file into ParaView. The field is the index
into the topology's declaration, which is what the exporter promises; the block's
declared id string is a different thing and is not in the file.

A hybrid-path file has no such section (deliberately -- a .vtk claiming every
cell is in block 0 would be a worse answer than no field), so it renders the way
it always has. ``--no-blocks`` forces that rendering on a file that does have one.
"""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

# Qualitative fills. The first is the colour every mesh in this repo was drawn
# in before blocks were shown, so a one-block topology looks unchanged.
BLOCK_COLORS = [
    "#f4a742", "#7fb2d9", "#8fc98f", "#d99797",
    "#b9a0d4", "#e3c766", "#8fc9c3", "#c9a98f",
]


def read_vtk(path):
    """Points, cells, and the per-cell block index (None when absent)."""
    pts, cells, blocks = [], [], None
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
        if t == "SCALARS" and i + 2 < n and toks[i+1] == "block":
            # SCALARS block int 1 / LOOKUP_TABLE default / <ncells> values
            j = i + 4
            if j < n and toks[j] == "LOOKUP_TABLE":
                j += 2
            want = len(cells)
            vals = []
            while j < n and len(vals) < want:
                try:
                    vals.append(int(toks[j]))
                except ValueError:
                    break
                j += 1
            if len(vals) == want:
                blocks = vals
            i = j
            continue
        i += 1
    return pts, cells, blocks


def block_edges(cells, blocks):
    """Edges on a block's rim: shared by two different blocks, or by one cell."""
    seen = {}
    for c, b in zip(cells, blocks):
        m = len(c)
        if m < 2:
            continue
        for j in range(m):
            a, d = c[j], c[(j+1) % m]
            key = (a, d) if a < d else (d, a)
            seen.setdefault(key, []).append(b)
    return [k for k, bs in seen.items() if len(bs) == 1 or len(set(bs)) > 1]


def main():
    argv = [a for a in sys.argv if not a.startswith("--")]
    flags = {a for a in sys.argv if a.startswith("--")}
    mesh, out = argv[1], argv[2]
    box = [float(v) for v in argv[3:7]] if len(argv) >= 7 else None
    # optional 7th positional: number of trailing far-field triangles (blue);
    # earlier area cells are BL (orange). Far-field cells are appended last.
    n_far = int(argv[7]) if len(argv) >= 8 else 0
    pts, cells, blocks = read_vtk(mesh)
    if "--no-blocks" in flags:
        blocks = None

    from matplotlib.patches import Polygon as MplPoly
    from matplotlib.collections import PatchCollection

    tri_cells = [(idx, c) for idx, c in enumerate(cells) if len(c) >= 3]
    n_tri = len(tri_cells)
    fig, ax = plt.subplots(figsize=(11, 9), dpi=140)

    if blocks is not None:
        by_block = {}
        for idx, c in tri_cells:
            by_block.setdefault(blocks[idx], []).append(MplPoly([pts[v] for v in c],
                                                                closed=True))
        handles = []
        for b in sorted(by_block):
            col = BLOCK_COLORS[b % len(BLOCK_COLORS)]
            ax.add_collection(PatchCollection(by_block[b], facecolor=col,
                                              edgecolor="none", alpha=0.85))
            handles.append(plt.Line2D([], [], marker="s", linestyle="none",
                                      markersize=9, markerfacecolor=col,
                                      markeredgecolor="#33393f",
                                      label=f"block {b}  ({len(by_block[b])} cells)"))
        ax.legend(handles=handles, loc="upper right", fontsize=8,
                  framealpha=0.9, title="declaration index", title_fontsize=8)
    else:
        bl_patches, ff_patches = [], []
        for k, (idx, c) in enumerate(tri_cells):
            poly = [pts[v] for v in c]
            if n_far and k >= n_tri - n_far:
                ff_patches.append(MplPoly(poly, closed=True))
            else:
                bl_patches.append(MplPoly(poly, closed=True))
        if bl_patches:
            ax.add_collection(PatchCollection(bl_patches, facecolor="#f4a742",
                                              edgecolor="none", alpha=0.85))
        if ff_patches:
            ax.add_collection(PatchCollection(ff_patches, facecolor="#bcd6f0",
                                              edgecolor="none", alpha=0.7))

    segs = []
    for c in cells:
        m = len(c)
        if m < 2:
            continue
        for j in range(m):
            segs.append([pts[c[j]], pts[c[(j+1) % m]]])
    ax.add_collection(LineCollection(segs, colors="#33393f", linewidths=0.4))

    if blocks is not None:
        rim = [[pts[a], pts[b]] for a, b in block_edges(cells, blocks)]
        ax.add_collection(LineCollection(rim, colors="#121619", linewidths=1.9))

    ax.set_aspect("equal")
    if box:
        ax.set_xlim(box[0], box[1]); ax.set_ylim(box[2], box[3])
    else:
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        ax.set_xlim(min(xs), max(xs)); ax.set_ylim(min(ys), max(ys))
    nb = f", {len(set(blocks))} blocks" if blocks is not None else ""
    ax.set_title(f"{mesh}  ({len(pts)} pts, {len(cells)} cells{nb})")
    fig.tight_layout(); fig.savefig(out); print("wrote", out)


if __name__ == "__main__":
    main()
