#!/usr/bin/env python3
"""The Surface Definition dialog, end to end on the real Results canvas.

``test_surface_source.py`` pins the geometry; this pins the part a user touches:

 1. **Every source is LISTED, including the unusable ones** — with the reason on
    the row ("no STL3d φ field loaded (run the IB stage)"). A source that is
    merely hidden when unavailable reads as a feature that does not exist, and the
    user has no idea what to go and do.
 2. **Nothing runs until they commit.** Opening the dialog and clicking around
    must not contour a field or chain a point cloud — on a large result those are
    seconds each, and the user is usually mid-decision.
 3. **s = 0 is required, not defaulted** (USER-REQUESTED): Show / Plot stay
    disabled until a start rule is chosen, and the chosen origin is what the
    canvas marks and the plot's axis label states.
 4. **The overlay tells the truth**: the curve that was plotted is drawn, the
    other extracted pieces are drawn too (a missing flap must be visible, not
    implied), and unticking / clearing takes the marker with it.

The result files are synthetic but structurally real: a body-fitted annulus
(FETRIANGLE, BLOCK, one CELLCENTERED variable, exactly like the solver's) and an
immersed-boundary square whose φ marks a disk that touches no mesh boundary — the
case the old mesh-boundary-only surface plot could not describe at all.

Run:  python3 tools/PreProcessor/tests/test_surface_source_gui.py
"""
import os
import sys
import tempfile
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
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.controllers.surface_source_ctrl import SurfaceSourceControllerMixin  # noqa: E402
from app.models.segment import SegmentModel  # noqa: E402
from app.services import surface_source as ss  # noqa: E402
from app.views.result_canvas import ResultCanvasView  # noqa: E402
from app.views.surface_source_dialog import SurfaceSourceDialog  # noqa: E402

TMP = tempfile.mkdtemp(prefix="hyb_surf_")
R_IN, R_OUT = 0.5, 2.0
PHI_R = 0.6


def _write_zone(path, nodes, tris, nodal: dict, cell: dict):
    """One FETRIANGLE BLOCK zone: NODAL vars then CELLCENTERED ones, then conn."""
    names = ["x", "y"] + list(nodal) + list(cell)
    ci = [names.index(k) + 1 for k in cell]
    varloc = ", ".join(f"[{i}] = CELLCENTERED" for i in ci)
    L = ['Title = "test"',
         "variables = " + ", ".join(f'"{n}"' for n in names),
         f'zone t = "time 0" N={len(nodes)} E={len(tris)} ZONETYPE=FETRIANGLE',
         f" DATAPACKING = BLOCK VARLOCATION = ( {varloc} )"]
    for col in (nodes[:, 0], nodes[:, 1], *nodal.values(), *cell.values()):
        L.append(" ".join(f"{v:.10g}" for v in np.asarray(col).ravel()))
    for t in tris:
        L.append(" ".join(str(int(v) + 1) for v in t))
    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")
    return path


def write_annulus(path, nr=9, nt=48):
    """Body-fitted: a disk-shaped hole (r=0.5) inside a circular far field (r=2).
    ``geometry_boundary_loops`` must keep the hole and drop the outer ring."""
    rr = np.linspace(R_IN, R_OUT, nr)
    th = np.linspace(0, 2 * np.pi, nt, endpoint=False)
    R, T = np.meshgrid(rr, th, indexing="ij")
    nodes = np.column_stack([(R * np.cos(T)).ravel(), (R * np.sin(T)).ravel()])
    tris = []
    for i in range(nr - 1):
        for j in range(nt):
            a = i * nt + j
            b = i * nt + (j + 1) % nt
            c = (i + 1) * nt + (j + 1) % nt
            d = (i + 1) * nt + j
            tris += [[a, b, c], [a, c, d]]
    tris = np.asarray(tris)
    cx = nodes[tris][:, :, 0].mean(axis=1)
    return _write_zone(path, nodes, tris, {"p": nodes[:, 0] * 3.0}, {"u": cx})


def write_ibm_square(path, n=41):
    """Immersed boundary: a full square whose nodal φ marks a disk r=0.6 — the
    solid never reaches a mesh boundary, so ONLY a φ iso-line can find it."""
    xs = np.linspace(-2, 2, n)
    gx, gy = np.meshgrid(xs, xs, indexing="xy")
    nodes = np.column_stack([gx.ravel(), gy.ravel()])
    tris = ss.grid_triangles(n, n)
    phi = (np.hypot(nodes[:, 0], nodes[:, 1]) <= PHI_R).astype(float)
    return _write_zone(path, nodes, tris,
                       {"phi": phi, "p": nodes[:, 1] * 2.0},
                       {"u": np.zeros(len(tris))})


class FakeCtrl(SurfaceSourceControllerMixin):
    """The real provider mixin over stubbed session state, so availability and
    extraction are tested without standing up the whole application."""

    def __init__(self):
        self._stl3d_phi_pts = None
        self._stl3d_phi_val = None
        self.global_stl3d_config = None
        self.global_solver_config = None
        self._session = None
        self._cad = []

    def active_session(self):
        return self._session

    def cad_overlay_sessions(self):
        return [(1, "square.dat", "#fff", bool(len(self._cad)))]

    def cad_overlay_polylines(self, ids=None):
        return list(self._cad)


class Cfg:                                  # stand-in for Stl3dConfig
    def __init__(self, n):
        self.nx = self.ny = n
        self.nz = 1

    def spacings(self):
        return (4.0 / (self.nx - 1), 4.0 / (self.ny - 1), 0.0)


# --------------------------------------------------------------------------- #
ann = write_annulus(os.path.join(TMP, "annulus.dat"))
ibm = write_ibm_square(os.path.join(TMP, "ibm.dat"))

canvas = ResultCanvasView()
ctrl = FakeCtrl()
canvas.set_controller(ctrl)
canvas.load_result_path(ann)
res = canvas._result
check(res is not None and len(res.nodes) > 0 and len(res.elements) > 0,
      f"the synthetic annulus parses ({len(res.nodes)} nodes, {len(res.elements)} tris)")

# ── 1. The option list: everything shown, reasons on the unusable rows ────── #
opts = canvas.surface_source_options()
kinds = [o["kind"] for o in opts]
check(kinds == list(ss.ALL_KINDS), f"all six sources are offered, in order ({kinds})")
by = {o["kind"]: o for o in opts}
check(by[ss.KIND_MESH]["enabled"], "mesh boundary is available with a result loaded")
check(not by[ss.KIND_GRID_ISO]["enabled"]
      and "IB" in by[ss.KIND_GRID_ISO]["reason"],
      f"STL3d sources are unavailable AND say why: {by[ss.KIND_GRID_ISO]['reason']!r}")
check(not by[ss.KIND_ANALYTIC]["enabled"]
      and "closed CAD shape" in by[ss.KIND_ANALYTIC]["reason"],
      "the analytic source explains that no closed CAD shape exists")
check(not by[ss.KIND_CAD]["enabled"], "the CAD source is unavailable with no geometry")

dlg = SurfaceSourceDialog(canvas)
dlg.reload(opts, canvas._surface_spec)
check(len(dlg._radios) == len(ss.ALL_KINDS)
      and not dlg._radios[ss.KIND_GRID_ISO].isEnabled()
      and dlg._radios[ss.KIND_MESH].isEnabled(),
      "the dialog greys out exactly the unavailable rows")
check(dlg.current_kind() == ss.KIND_MESH,
      "it opens on the first usable source rather than a dead one")

# ── 2. Nothing computed, and nothing plottable, until s = 0 is chosen ────── #
check(dlg.start_combo.currentData() == "",
      "the start rule opens on the placeholder (no silent default)")
check(not dlg.show_btn.isEnabled() and not dlg.plot_btn.isEnabled(),
      "Show / Plot are disabled until the arc-length origin is picked")
check(canvas._surface_curve is None,
      "opening the dialog extracts NOTHING (deferred until the user commits)")
bad = canvas.build_surface(ss.SurfaceSpec(kind=ss.KIND_MESH, start_rule=""))
check(not bad["ok"] and "s = 0" in bad["error"],
      "building without a start rule is refused with a readable reason")

dlg.start_combo.setCurrentIndex(dlg.start_combo.findData("xmin"))
check(dlg.show_btn.isEnabled() and dlg.plot_btn.isEnabled(),
      "picking the origin enables Show / Plot")

# ── 3. Mesh-boundary source: the hole, not the far field ─────────────────── #
dlg._on_show()
cur = canvas._surface_curve
check(cur is not None and cur.closed, "Show extracts a closed curve")
rad = np.hypot(cur.points[:, 0], cur.points[:, 1])
check(abs(rad.mean() - R_IN) < 1e-9,
      f"it is the r={R_IN} hole, not the r={R_OUT} far field (mean r {rad.mean():.4f})")
check(canvas._surface_on and canvas.surface_cb.isChecked(),
      "Show turns the overlay on and ticks the top-bar box with it")
start = canvas._surface_start
check(abs(start[0] - -R_IN) < 1e-9 and abs(start[1]) < 1e-9,
      f"s=0 landed on the x-min point of the hole (got {start})")
check(cur.node_ids is not None, "the mesh source carries node_ids (exact sampling)")

# The plot: columns, the closing sample, and exact nodal values.
plot = canvas.plot_surface_series(dlg.spec())
check(plot["ok"], f"Plot succeeds: {plot.get('error', '')}")
d = canvas._surf_dialog
labels = list(d._labels)
check(labels[0].startswith("s (arc length)") and "s=0 @" in labels[0]
      and "CCW" in labels[0],
      f"the x-axis names the origin and direction: {labels[0]!r}")
check("x" in labels and "y" in labels and "p" in labels,
      f"x / y stay available as alternative abscissae ({labels})")
s_col = d._data[:, 0]
check(len(s_col) == len(cur.points) + 1,
      "the closed curve is plotted with its closing sample (full perimeter)")
check(abs(s_col[-1] - cur.perimeter) < 1e-9 and np.all(np.diff(s_col) >= 0),
      "arc length is monotone and reaches the perimeter")
p_col = d._data[:, labels.index("p")]
expect = np.asarray(canvas._result.cell_to_node("p"))[cur.node_ids]
check(np.allclose(p_col[:-1], expect) and abs(p_col[-1] - expect[0]) < 1e-12,
      "values along the mesh boundary are the EXACT nodal ones, wrapped at the end")
check("exact nodal" in d.windowTitle(),
      f"the title states how the values were obtained: {d.windowTitle()!r}")

# Direction and origin are honoured, not merely accepted.
cw = dlg.spec(); cw.ccw = False; cw.start_rule = "xmax"
r2 = canvas.apply_surface_spec(cw)
check(r2["ok"] and abs(r2["start"][0] - R_IN) < 1e-9,
      "switching to x max moves s=0 to the other side")
from app.services.surface_sample import signed_area  # noqa: E402
check(signed_area(r2["curve"].points) < 0, "the CW request really reversed the loop")

# ── 4. Overlay hygiene ───────────────────────────────────────────────────── #
canvas.render()
check(True, "rendering with the surface overlay on does not raise")
canvas.surface_cb.setChecked(False)
check(not canvas._surface_on, "unticking the box hides the overlay")
canvas.surface_cb.setChecked(True)
canvas.clear_surface()
check(canvas._surface_curve is None and not canvas.surface_cb.isChecked(),
      "clearing the surface unticks its box too (no ticked box with nothing drawn)")

# ── 5. Immersed boundary: only a φ iso-line finds the solid ──────────────── #
canvas.load_result_path(ibm)
opts = canvas.surface_source_options()
by = {o["kind"]: o for o in opts}
check(by[ss.KIND_FIELD_ISO]["enabled"]
      and by[ss.KIND_FIELD_ISO]["default_var"] == "phi",
      "the field-iso source defaults to φ when the result carries it")
spec = ss.SurfaceSpec(kind=ss.KIND_FIELD_ISO, var="phi", level=0.5,
                      start_rule="xmin")
out = canvas.apply_surface_spec(spec)
check(out["ok"], f"the φ iso-line extracts: {out.get('error', '')}")
ir = np.hypot(out["curve"].points[:, 0], out["curve"].points[:, 1])
h = 4.0 / 40
check(out["curve"].closed and abs(ir.mean() - PHI_R) < h,
      f"φ=0.5 reconstructs the r={PHI_R} solid to within a cell (mean {ir.mean():.4f})")
mesh_try = canvas.build_surface(ss.SurfaceSpec(kind=ss.KIND_MESH,
                                               start_rule="xmin"))
mr = np.hypot(*mesh_try["curve"].points.T) if mesh_try["ok"] else np.array([9.0])
check(not mesh_try["ok"] or mr.min() > 1.5,
      "the mesh-boundary source cannot see an immersed solid (only the far field) "
      "— which is why the other sources exist")

# Sampling an iso-line is interpolated, and δ moves the samples outward.
pl = canvas.plot_surface_series(spec)
check(pl["ok"] and "interpolated" in canvas._surf_dialog.windowTitle(),
      "an iso-line surface is reported as interpolated, not exact")
spec_off = ss.SurfaceSpec(kind=ss.KIND_FIELD_ISO, var="phi", level=0.5,
                          start_rule="xmin", offset=0.15)
pl2 = canvas.plot_surface_series(spec_off)
d = canvas._surf_dialog
xs = d._data[:, list(d._labels).index("x")]
ys = d._data[:, list(d._labels).index("y")]
# "Outside" has to be tested against the CURVE, not against a radius: a φ
# iso-line on a coarse grid is a staircase, so at a corner the outward normal
# runs along an axis and the sample's distance from the centre barely changes
# even though it has properly left the body.
from matplotlib.path import Path as _Path  # noqa: E402
inside = _Path(out["curve"].points).contains_points(np.column_stack([xs, ys]))
check(pl2["ok"] and not inside.any(),
      f"δ > 0 puts every sample OUTSIDE the solid ({int(inside.sum())} inside)")
check(np.hypot(xs, ys).min() > PHI_R * 0.99,
      "and none of them ends up deeper inside than the interface itself")
check("δ=" in canvas._surf_dialog.windowTitle(),
      f"the offset is stated in the title: {canvas._surf_dialog.windowTitle()!r}")

# ── 6. STL3d φ sources light up once the IB stage has a field ────────────── #
n = 41
xs1 = np.linspace(-2, 2, n)
gx, gy = np.meshgrid(xs1, xs1, indexing="xy")
ctrl._stl3d_phi_pts = np.column_stack([gx.ravel(), gy.ravel(), np.zeros(n * n)])
ctrl._stl3d_phi_val = (np.hypot(gx, gy) <= 0.9).astype(float).ravel()
ctrl.global_stl3d_config = Cfg(n)
by = {o["kind"]: o for o in canvas.surface_source_options()}
check(by[ss.KIND_GRID_ISO]["enabled"] and by[ss.KIND_INTERFACE_CELLS]["enabled"],
      "both STL3d sources become available once a φ field is loaded")
g = canvas.apply_surface_spec(ss.SurfaceSpec(kind=ss.KIND_GRID_ISO, level=0.5,
                                             start_rule="xmin"))
gr = np.hypot(*g["curve"].points.T)
check(g["ok"] and abs(gr.mean() - 0.9) < 0.1,
      f"the STL3d grid iso-line finds r=0.9 (mean {gr.mean():.3f})")
f = canvas.apply_surface_spec(ss.SurfaceSpec(kind=ss.KIND_INTERFACE_CELLS,
                                             level=0.5, start_rule="xmin"))
check(f["ok"] and any("interface cells" in n_ for n_ in f["notes"]),
      f"the Fit Δ source reports how many interface cells it used: {f['notes']}")
fr = np.hypot(*f["curve"].points.T)
check(fr.max() < 0.95, "the Fit Δ ring is the solid-side staircase (inside r=0.9)")

# A grid that no longer matches the field must refuse, not contour garbage.
ctrl.global_stl3d_config = Cfg(n + 4)
by = {o["kind"]: o for o in canvas.surface_source_options()}
check(not by[ss.KIND_GRID_ISO]["enabled"]
      and "no longer matches" in by[ss.KIND_GRID_ISO]["reason"],
      "an edited Nx/Ny disables the STL3d sources with an explicit reason")
ctrl.global_stl3d_config = Cfg(n)

# ── 7. Analytic φ shape and CAD outline ──────────────────────────────────── #
class FakeSession:
    def __init__(self, segs):
        self.project_model = type("PM", (), {"segments": segs})()


seg = SegmentModel(7, 0, 1)
seg.type = "curve"
seg.curve_type = "circle"
seg.parameters = {"cx": 0.0, "cy": 0.0, "r": 0.75}
ctrl._session = FakeSession([seg])
ctrl.global_solver_config = type("SC", (), {
    "init_cond_dll": "/x/results/solver/dll_src/ibm_phi_shape_edge7.cc",
    "ibm_phi_file": ""})()
shapes = ctrl.surface_analytic_shapes()
check(len(shapes) == 1 and shapes[0]["in_use"] and "disk" in shapes[0]["label"],
      f"the analytic shape is found and flagged as the one in use: {shapes}")
a = canvas.apply_surface_spec(ss.SurfaceSpec(kind=ss.KIND_ANALYTIC,
                                             shape=shapes[0], start_rule="xmax"))
ar = np.hypot(*a["curve"].points.T)
check(a["ok"] and np.allclose(ar, 0.75) and abs(a["start"][0] - 0.75) < 1e-9,
      "the analytic surface is exact and honours the start rule")

ctrl._cad = [np.array([[-1.0, -1.0], [1.0, -1.0], [1.0, 1.0], [-1.0, 1.0],
                       [-1.0, -1.0]])]
by = {o["kind"]: o for o in canvas.surface_source_options()}
check(by[ss.KIND_CAD]["enabled"], "the CAD source lights up when a session has geometry")
c = canvas.apply_surface_spec(ss.SurfaceSpec(kind=ss.KIND_CAD, session_ids=(1,),
                                             start_rule="ymin"))
check(c["ok"] and c["curve"].closed and len(c["curve"].points) == 4
      and abs(c["start"][1] + 1.0) < 1e-9,
      "the CAD outline round-trips as a closed 4-point square starting at y min")

# ── 8. A reload rebuilds the shown surface from the spec ─────────────────── #
canvas.apply_surface_spec(ss.SurfaceSpec(kind=ss.KIND_FIELD_ISO, var="phi",
                                         level=0.5, start_rule="xmin"))
check(canvas._surface_curve is not None, "a φ surface is shown before the reload")
canvas.load_result_path(ibm)
check(canvas._surface_curve is not None
      and abs(np.hypot(*canvas._surface_curve.points.T).mean() - PHI_R) < h,
      "reloading the result re-extracts the same surface from the kept spec")
canvas.load_result_path(ann)
check(canvas._surface_curve is None and "dropped" in canvas._surface_info,
      "a result that cannot produce it drops the surface and SAYS so "
      f"({canvas._surface_info!r})")

print("-" * 60)
if _FAILS:
    print(f"{len(_FAILS)} FAILED:")
    for f_ in _FAILS:
        print("  - " + f_)
    sys.exit(1)
print("ALL PASS")
