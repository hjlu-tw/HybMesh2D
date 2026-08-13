#!/usr/bin/env python3
"""Surface sources for the Results arc-length plot.

"Plot Cp along the surface" used to have exactly one meaning — the inner boundary
loops of the solved triangulation — which is the only honest answer for a
body-fitted mesh and NO answer at all for an immersed-boundary run, where the
solid never touches a mesh boundary. The surface is now a choice, and each choice
has to survive the same two questions:

 1. **Is the curve really the body?** An iso-line is chained by mesh EDGE identity
    (one crossing point per crossed edge, shared exactly by both owning triangles)
    rather than by welding coordinates within a tolerance — on a fine mesh a
    tolerance either splits one contour into fragments or fuses two that merely
    pass close. Pinned here on a field whose iso-line is known analytically.

 2. **Is the arc length comparable?** s = 0 is a stated rule (x min, x max, …) and
    the traversal direction is forced, because the old path inherited both from
    ``next(iter(set))`` inside the loop tracer: reproducible for one file, but
    two runs of the same body could start their arc length in different places,
    which is exactly when you want to overlay the two curves.

Also pinned: the mesh-boundary source still reads EXACT nodal values (the whole
point of carrying node_ids), a closed curve's arc length now reaches the full
perimeter instead of stopping one chord short, the δ offset moves samples OUT of
the body and not into it, and the Fit Δ interface cloud reports when its
nearest-neighbour chaining jumped instead of quietly returning a plausible curve.

Run:  python3 tools/PreProcessor/tests/test_surface_source.py
"""
import os
import sys
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >180s", flush=True)
    os._exit(99)


_wd = threading.Timer(180, _watchdog)
_wd.daemon = True
_wd.start()

import numpy as np  # noqa: E402

from app.services import surface_sample as sm  # noqa: E402
from app.services import surface_source as ss  # noqa: E402
from app.services.phi_quality import interface_points  # noqa: E402


# --------------------------------------------------------------------------- #
# Helpers: a structured square grid, triangulated, plus a radial field.
# --------------------------------------------------------------------------- #
def unit_grid(n=41, lo=-2.0, hi=2.0):
    xs = np.linspace(lo, hi, n)
    ys = np.linspace(lo, hi, n)
    gx, gy = np.meshgrid(xs, ys, indexing="xy")     # x fastest, matching i,j,k
    nodes = np.column_stack([gx.ravel(), gy.ravel()])
    return nodes, ss.grid_triangles(n, n)


# ── 1. Iso-line geometry ─────────────────────────────────────────────────── #
nodes, tris = unit_grid(81)
r = np.hypot(nodes[:, 0], nodes[:, 1])
curves = ss.iso_curves(nodes, tris, r, 1.0)         # the unit circle
check(len(curves) == 1, f"iso-line of |r| gives ONE closed contour (got {len(curves)})")
c = curves[0]
check(c.closed, "the extracted circle is closed (a cycle, not a path)")
rad = np.hypot(c.points[:, 0], c.points[:, 1])
check(abs(rad.mean() - 1.0) < 2e-3 and rad.std() < 5e-3,
      f"every point sits on r=1 (mean {rad.mean():.5f}, std {rad.std():.2e})")
check(abs(c.perimeter - 2 * np.pi) / (2 * np.pi) < 5e-3,
      f"its perimeter is 2π to <0.5% (got {c.perimeter:.5f})")
# Ordered, not just a bag of points: consecutive points must be neighbours, so
# every step is about one crossing apart and never a jump across the circle.
step = np.hypot(*np.diff(np.vstack([c.points, c.points[:1]]), axis=0).T)
check(step.max() < 5.0 * np.median(step),
      f"points are in traversal order (worst step {step.max() / np.median(step):.1f}× median)")

# Two disjoint bodies must stay two curves, not be welded into one.
d1 = np.hypot(nodes[:, 0] + 1.0, nodes[:, 1])
d2 = np.hypot(nodes[:, 0] - 1.0, nodes[:, 1])
two = ss.iso_curves(nodes, tris, np.minimum(d1, d2), 0.4)
check(len(two) == 2 and all(t.closed for t in two),
      f"two separate circles stay two closed curves (got {len(two)})")

# An iso-line that leaves through the mesh boundary is a PATH, not a fake loop.
open_curves = ss.iso_curves(nodes, tris, nodes[:, 0], 0.0)   # the x = 0 line
check(len(open_curves) == 1 and not open_curves[0].closed,
      "an iso-line crossing the domain is reported OPEN, not closed")

# ── 2. Structured φ field (STL3d) through the same code path ─────────────── #
n = 61
xs = np.linspace(-2, 2, n)
gx, gy = np.meshgrid(xs, xs, indexing="xy")
pts3 = np.column_stack([gx.ravel(), gy.ravel(), np.zeros(n * n)])
phi = (np.hypot(gx, gy) <= 1.0).astype(float).ravel()        # binary marker
gc = ss.grid_iso_curves(pts3, phi, n, n, 1, level=0.5)
gcc = ss.pick_curve(gc)
gr = np.hypot(gcc.points[:, 0], gcc.points[:, 1])
check(gcc.closed and abs(gr.mean() - 1.0) < 0.05,
      f"a binary φ disk contours to r≈1 (mean {gr.mean():.4f}, closed={gcc.closed})")

# A degenerate/mismatched grid must say so rather than contour garbage.
try:
    ss.grid_iso_curves(pts3, phi[:-1], n, n, 1, level=0.5)
    check(False, "a φ array that doesn't match nx*ny*nz is rejected")
except ValueError:
    check(True, "a φ array that doesn't match nx*ny*nz is rejected")

# ── 3. Fit Δ interface cells: same points as the fit report, chained ──────── #
ipts = interface_points(phi > 0.5, n, n, 1, pts3)
check(len(ipts) > 20, f"interface_points is importable and finds cells ({len(ipts)})")
chain = ss.chain_points_nn(ipts)
check(len(chain) == len(ipts), "chaining keeps every interface point")
cr = np.hypot(chain.points[:, 0], chain.points[:, 1])
check(cr.max() < 1.05 and cr.min() > 0.85,
      f"the staircase ring stays near r=1 ({cr.min():.3f}..{cr.max():.3f})")
check(chain.closed, "the interface ring is detected as closed")
# The honesty requirement: a cloud that cannot be chained sensibly must SAY so.
split = np.vstack([ipts[np.hypot(ipts[:, 0], ipts[:, 1]) > 0][:5],
                   ipts[:5] + np.array([50.0, 0.0, 0.0])])
check(bool(ss.chain_points_nn(split[:, :2]).note),
      "a cloud with a huge gap reports its unreliable ordering in `note`")

# ── 4. s = 0 is a rule, and the direction is forced ──────────────────────── #
th = np.linspace(0, 2 * np.pi, 60, endpoint=False)
circle = ss.SurfaceCurve(points=np.column_stack([np.cos(th), np.sin(th)]),
                         closed=True)          # CCW by construction
check(sm.signed_area(circle.points) > 0, "signed_area is positive for a CCW loop")
cw = sm.orient_curve(circle, ccw=False)
check(sm.signed_area(cw.points) < 0, "orient_curve(ccw=False) reverses the loop")
check(sm.orient_curve(circle, ccw=True) is circle,
      "an already-CCW loop is returned untouched (no needless copy)")
for rule, expect in (("xmin", (-1.0, 0.0)), ("xmax", (1.0, 0.0)),
                     ("ymin", (0.0, -1.0)), ("ymax", (0.0, 1.0))):
    rot, start = sm.rotate_to_start(circle, rule)
    ok = (abs(start[0] - expect[0]) < 0.06 and abs(start[1] - expect[1]) < 0.06
          and np.allclose(rot.points[0], start))
    check(ok, f"start rule {rule!r} puts s=0 at {expect} (got "
              f"({start[0]:.3f}, {start[1]:.3f}))")
check(abs(sm.arc_length(circle.points, closed=True, wrap=True)[-1]
          - circle.perimeter) < 1e-12,
      "arc length of a closed curve reaches the FULL perimeter (the closing chord "
      "is included, which the old perimeter_series sliced off)")
check(len(sm.arc_length(circle.points, closed=True, wrap=True))
      == len(circle.points) + 1,
      "the wrapped series has one extra sample so the plot closes the loop")
try:
    sm.start_index(circle.points, "")
    check(False, "an unset start rule is refused (no silent default)")
except ValueError:
    check(True, "an unset start rule is refused (no silent default)")

# Rotation must carry node_ids with the points, or the exact nodal lookup after a
# rotation reads the wrong node.
ids = np.arange(len(circle.points))
with_ids = ss.SurfaceCurve(points=circle.points, closed=True, node_ids=ids)
rot, _ = sm.rotate_to_start(with_ids, "xmax")
i0 = int(np.lexsort((circle.points[:, 1], -circle.points[:, 0]))[0])
check(rot.node_ids is not None and int(rot.node_ids[0]) == i0
      and np.allclose(rot.points[0], circle.points[i0]),
      "node_ids are rotated with the points (values stay bound to their node)")

# ── 5. δ offset goes OUTWARD, for either handedness ──────────────────────── #
for ccw in (True, False):
    cur = sm.orient_curve(circle, ccw)
    nrm = sm.outward_normals(cur.points, closed=True)
    moved = cur.points + 0.1 * nrm
    check(np.all(np.hypot(moved[:, 0], moved[:, 1]) > 1.05),
          f"outward normals point away from the body ({'CCW' if ccw else 'CW'})")
flipped = sm.outward_normals(circle.points, closed=True, flip=True)
check(np.all(np.hypot(*(circle.points + 0.1 * flipped).T) < 0.95),
      "'offset the other way' samples INSIDE the body")

# ── 6. Sampling: exact on mesh nodes, interpolated otherwise ─────────────── #
vals = np.arange(len(circle.points), dtype=float) * 3.0
out = sm.sample_on_curve(with_ids, nodal_values=vals, interp=None, offset=0.0)
check(out["exact"] and np.allclose(out["values"], vals),
      "a mesh-boundary curve reads EXACT nodal values (no interpolation)")


def fake_interp(xs, ys):
    return np.asarray(xs) * 0.0 + 7.0


out = sm.sample_on_curve(with_ids, nodal_values=vals, interp=fake_interp, offset=0.05)
check(not out["exact"] and np.allclose(out["values"], 7.0)
      and out["offset"] == 0.05,
      "asking for δ != 0 switches to interpolation at the OFFSET points")
check(np.all(np.hypot(*out["points"].T) > 1.0),
      "the reported sample points are the offset ones, not the curve points")


def masked_interp(xs, ys):
    return np.ma.masked_invalid(np.where(np.asarray(xs) > 0, 1.0, np.nan))


out = sm.sample_on_curve(ss.SurfaceCurve(points=circle.points, closed=True),
                         interp=masked_interp)
check(np.isnan(out["values"]).any() and not np.isnan(out["values"]).all(),
      "samples outside the mesh come back NaN (a gap), never a fabricated value")

# ── 7. Analytic / CAD sources ────────────────────────────────────────────── #
disk = ss.analytic_curve({"type": "circle", "cx": 2.0, "cy": -1.0, "r": 0.5})
dr = np.hypot(disk.points[:, 0] - 2.0, disk.points[:, 1] + 1.0)
check(disk.closed and np.allclose(dr, 0.5) and len(disk.points) > 100,
      "an analytic disk is exact (every point at r, closed, well sampled)")
poly = ss.analytic_curve({"type": "polygon",
                          "verts": [(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]})
check(poly.closed and len(poly.points) == 4,
      "an analytic polygon drops the repeated closing vertex (4 unique points)")
cad = ss.cad_curves([np.array([[0, 0], [1, 0], [1, 1], [0, 0]]),
                     np.array([[5, 5], [6, 6]]),
                     np.array([[9, 9]])])
check(len(cad) == 2 and cad[0].closed and not cad[1].closed,
      "CAD pieces: closure is read from the points; a 1-point piece is dropped")
check(ss.analytic_curve({"type": "circle", "r": 0.0}).note,
      "a degenerate analytic shape reports why it produced nothing")

# ── 8. pick_curve chooses by PERIMETER, not point count ──────────────────── #
big = ss.SurfaceCurve(points=np.column_stack([10 * np.cos(th), 10 * np.sin(th)]),
                      closed=True)                      # 60 pts, perimeter ~63
dense = np.linspace(0, 2 * np.pi, 400, endpoint=False)
small = ss.SurfaceCurve(points=np.column_stack([np.cos(dense), np.sin(dense)]),
                        closed=True)                    # 400 pts, perimeter ~6
check(ss.pick_curve([small, big]) is big,
      "the plotted piece is the longest by perimeter, not the one with most points")
check(ss.pick_curve([small, big], loop=0) is small, "an explicit piece index wins")

print("-" * 60)
if _FAILS:
    print(f"{len(_FAILS)} FAILED:")
    for f in _FAILS:
        print("  - " + f)
    sys.exit(1)
print("ALL PASS")
