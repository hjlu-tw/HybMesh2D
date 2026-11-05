"""PROTOTYPE -- THROWAWAY. Not production, not gated, not imported by anything.

THE QUESTION IT ANSWERS
    A proposal on the table is: run a coarse mesh, solve it, and use the
    DENSITY GRADIENT of the result to decide where the block boundaries go.
    docs/research/solution-driven-block-decomposition.md says a bare |grad rho|
    is the one sensor nobody ships, and that the orthodox ones are a pressure
    switch, a Ducros-style dilatation/vorticity ratio, or a normalised second
    derivative -- each with mandatory scaling. It also records, as an INFERENCE
    [I] rather than a verified fact, that |grad rho| fires inside boundary
    layers, and notes the claim is cheaply measurable on this repo's own output.

    So: draw the candidate sensors on a solve this repo already has, and ask of
    each one -- is the curve it picks out something a person would accept as a
    block boundary, or is it speckle?

HOW TO RUN
    python3 prototypes/sensor_fields/plot_sensors.py [case_dir_or_tecplot_path]

WHAT IT PRINTS
    Per sensor: the fraction of cells above the threshold, how many DISCONNECTED
    pieces the extracted iso-curve breaks into, and its total arc length. A
    usable block boundary is a small number of long pieces. Speckle is a large
    number of short ones -- that count is the whole measurement.
"""
import sys
import pathlib

import numpy as np
import matplotlib
import matplotlib.path
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.tri import Triangulation

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "PreProcessor" / "gui"))
from app.models.result_data import TecplotResult  # noqa: E402

# The percentile a sensor's iso-curve is cut at. One number for every sensor so
# the comparison is of SHAPE, not of threshold-picking.
PCTL = 97.0


def load(path):
    r = TecplotResult.from_file(str(path))
    tri = Triangulation(r.nodes[:, 0], r.nodes[:, 1], r.elements)
    return r, tri


def cell_to_node(tri, cell_vals, areas):
    """Area-weighted average of a cell-centred field onto the nodes."""
    n = tri.x.size
    num = np.zeros(n)
    den = np.zeros(n)
    for k in range(3):
        np.add.at(num, tri.triangles[:, k], cell_vals * areas)
        np.add.at(den, tri.triangles[:, k], areas)
    return num / np.where(den > 0, den, 1.0)


def tri_areas(tri):
    x = tri.x[tri.triangles]
    y = tri.y[tri.triangles]
    return 0.5 * np.abs((x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0])
                        - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0]))


def grad_per_cell(tri, node_vals, areas):
    """Constant gradient on each linear triangle, from its three node values."""
    x = tri.x[tri.triangles]
    y = tri.y[tri.triangles]
    f = node_vals[tri.triangles]
    a2 = 2.0 * np.where(areas > 0, areas, 1e-300)
    gx = (f[:, 0] * (y[:, 1] - y[:, 2])
          + f[:, 1] * (y[:, 2] - y[:, 0])
          + f[:, 2] * (y[:, 0] - y[:, 1])) / a2
    gy = (f[:, 0] * (x[:, 2] - x[:, 1])
          + f[:, 1] * (x[:, 0] - x[:, 2])
          + f[:, 2] * (x[:, 1] - x[:, 0])) / a2
    return gx, gy


def wall_mask(tri, body_dat, dist):
    """Triangles whose centroid is within `dist` of the body polyline.

    The wall is where every sensor is largest, by orders of magnitude, so a
    global percentile puts its whole iso-curve on the aerofoil's nose and the
    wake -- the feature a block boundary would actually be drawn on -- never
    reaches the threshold. Masking lets the question be asked of the field
    OUTSIDE the boundary layer, which is the only place the answer matters.
    """
    pts = np.loadtxt(body_dat)
    cx = tri.x[tri.triangles].mean(axis=1)
    cy = tri.y[tri.triangles].mean(axis=1)
    d = np.full(cx.size, np.inf)
    for i in range(0, pts.shape[0], 1):
        d = np.minimum(d, np.hypot(cx - pts[i, 0], cy - pts[i, 1]))
    return d < dist


def curve_stats(tri, node_sensor, level):
    """Extract the iso-curve and measure whether it is a CURVE or speckle."""
    fig = plt.figure()
    ax = fig.add_subplot(111)
    cs = ax.tricontour(tri, node_sensor, levels=[level])
    pieces, total_len = [], 0.0
    for path in cs.get_paths():
        # A contour comes back as ONE COMPOUND Path whose disconnected pieces
        # are separated by MOVETO codes. Counting get_paths() instead gives 1
        # for every sensor -- a check that cannot fail -- and measuring length
        # with a plain diff also bridges the gaps, inflating the total.
        v = path.vertices
        codes = path.codes
        if codes is None:
            runs = [v]
        else:
            starts = np.flatnonzero(codes == matplotlib.path.Path.MOVETO)
            bounds = list(starts) + [len(v)]
            runs = [v[a:b] for a, b in zip(bounds[:-1], bounds[1:])]
        for run in runs:
            if len(run) < 2:
                continue
            seg = np.hypot(np.diff(run[:, 0]), np.diff(run[:, 1])).sum()
            pieces.append(seg)
            total_len += seg
    plt.close(fig)
    pieces.sort(reverse=True)
    return pieces, total_len


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "multiblock_cgrid_demo"
    p = pathlib.Path(arg)
    if not p.is_file():
        hits = sorted((REPO / "results" / "solver" / arg / "work").glob("xtecp_sol_allz*"))
        if not hits:
            sys.exit(f"no tecplot solution for {arg!r}")
        p = hits[0]
    print(f"solution : {p.relative_to(REPO)}")

    r, tri = load(p)
    areas = tri_areas(tri)
    h = np.sqrt(areas)
    cd = r.cell_data
    print(f"variables: {r.variables}")
    print(f"cells    : {areas.size}   nodes: {tri.x.size}")

    rho = cd["`r"]
    pres = cd["p"]
    vort = cd["vort"]
    mach = cd["M"]
    print(f"rho range: {rho.min():.6f} .. {rho.max():.6f} "
          f"(spread {100 * (rho.max() - rho.min()) / rho.mean():.2f}% of mean)")
    print(f"M   range: {mach.min():.4f} .. {mach.max():.4f}")

    n_rho = cell_to_node(tri, rho, areas)
    n_p = cell_to_node(tri, pres, areas)
    gx, gy = grad_per_cell(tri, n_rho, areas)
    g_rho = np.hypot(gx, gy)
    px, py = grad_per_cell(tri, n_p, areas)
    g_p = np.hypot(px, py)

    # THE CONTROL. A sensor must be compared against the MESH, because a gradient
    # computed on a linear triangulation fires on a cell-size jump whether or not
    # anything is happening in the flow. If a sensor correlates with this, it is
    # reporting the blocking the coarse mesh already had.
    n_h = cell_to_node(tri, h, areas)
    hx, hy = grad_per_cell(tri, n_h, areas)
    mesh_rough = np.hypot(hx, hy)

    sensors = {
        "|grad rho|  (raw, as proposed)": g_rho,
        "h |grad rho|  (scaled)": h * g_rho,
        "h |grad p| / p  (pressure switch)": h * g_p / np.maximum(pres, 1e-30),
        "|vort|  (solver output, no derivative)": np.abs(vort),
    }

    def spearman(a, b):
        ra = np.argsort(np.argsort(a)).astype(float)
        rb = np.argsort(np.argsort(b)).astype(float)
        ra -= ra.mean(); rb -= rb.mean()
        return float((ra @ rb) / np.sqrt((ra @ ra) * (rb @ rb)))

    import os
    mask_d = float(os.environ.get("MASK_WALL", "0") or 0)
    keep = np.ones(areas.size, dtype=bool)
    if mask_d > 0:
        body = os.environ.get("BODY", "examples/geometries/naca0012.dat")
        m = wall_mask(tri, REPO / body, mask_d)
        tri.set_mask(m)
        keep = ~m
        print(f"wall mask : {mask_d} from {body} -- "
              f"{m.sum()} of {m.size} cells excluded")

    # The CONTROL's own longest piece, computed first, because every sensor is
    # reported RELATIVE to it. The absolute length means nothing across meshes --
    # a wake cut is 19 long and a ring round a cylinder is 0.85 -- but "how much
    # longer a curve than the bare mesh yields" is the same question everywhere.
    ctl_lvl = np.percentile(mesh_rough[keep], PCTL)
    ctl_node = cell_to_node(tri, mesh_rough, areas)
    ctl_pieces, ctl_total = curve_stats(tri, ctl_node, ctl_lvl)
    ctl_longest = ctl_pieces[0] if ctl_pieces else float("nan")
    print(f"\ncontrol  : |grad h| alone -> {len(ctl_pieces)} pieces, "
          f"longest {ctl_longest:.3f}")
    print()
    print(f"{'sensor':38s} {'pieces':>7s} {'longest':>9s} {'vs ctl':>8s} {'rho_mesh':>9s}")
    print("-" * 75)
    results = {}
    for name, sv in sensors.items():
        lvl = np.percentile(sv[keep], PCTL)
        n_s = cell_to_node(tri, sv, areas)
        pieces, total = curve_stats(tri, n_s, lvl)
        longest = pieces[0] if pieces else 0.0
        rm = spearman(sv[keep], mesh_rough[keep])
        results[name] = (sv, n_s, lvl, pieces, total)
        print(f"{name:38s} {len(pieces):7d} {longest:9.3f} "
              f"{longest / ctl_longest:7.2f}x {rm:9.3f}")
    print("\nrho_mesh = Spearman rank correlation with |grad h|, the MESH's own")
    print("roughness. High means the sensor is reporting the grid, not the flow.")

    # ---- the picture -------------------------------------------------------
    # The view. Overridable, because the two-ring case is a circle of radius ~1
    # in a domain of radius 10 and the aerofoil's wake runs to x=19.
    import os
    win = os.environ.get("WINDOW")
    if win:
        xmin, xmax, ymin, ymax = (float(v) for v in win.split(","))
    else:
        xmin, xmax, ymin, ymax = -0.6, 3.2, -0.9, 0.9
    results["|grad h|  (THE MESH -- control, no flow)"] = (
        mesh_rough, cell_to_node(tri, mesh_rough, areas),
        np.percentile(mesh_rough[keep], PCTL),
        *curve_stats(tri, cell_to_node(tri, mesh_rough, areas),
                     np.percentile(mesh_rough[keep], PCTL)))
    fig, axes = plt.subplots(2, 5, figsize=(26, 9), constrained_layout=True)
    for col, (name, (s, n_s, lvl, pieces, total)) in enumerate(results.items()):
        hi = np.percentile(s, 99.5)
        ax = axes[0, col]
        ax.tripcolor(tri, facecolors=np.clip(s, 0, hi), cmap="inferno", shading="flat")
        ax.set_title(name, fontsize=11)
        ax = axes[1, col]
        ax.triplot(tri, color="0.88", lw=0.2)
        ax.tricontour(tri, n_s, levels=[lvl], colors="crimson", linewidths=1.3)
        ax.set_title(f"iso at p{PCTL:g}  --  {len(pieces)} pieces, "
                     f"longest {pieces[0] if pieces else 0:.2f}", fontsize=10)
    for ax in axes.ravel():
        ax.set_xlim(xmin, xmax)
        ax.set_ylim(ymin, ymax)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(f"Candidate block-boundary sensors -- {p.parent.parent.name}   "
                 f"(M={mach.max():.2f} max, rho spread "
                 f"{100 * (rho.max() - rho.min()) / rho.mean():.2f}%)", fontsize=13)
    out = pathlib.Path(__file__).parent / f"sensors_{p.parent.parent.name}.png"
    fig.savefig(out, dpi=110)
    print(f"\nwrote {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
