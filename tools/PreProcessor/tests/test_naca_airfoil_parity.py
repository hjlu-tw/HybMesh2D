#!/usr/bin/env python3
"""The parametric NACA 4-digit aerofoil: one law, two hosts, driven BOTH ways.

#147. The CAD stage gained a `naca4` `curve_type` — an aerofoil drawn from its
designation and a chord instead of sourced as a coordinate file — and the shape
crosses a seam no other analytic shape's defect can hide behind: the canvas
previews it in Python and the resampler regenerates it in C++. A circle drawn one
way and meshed another is visible the moment anyone overlays the two; an aerofoil
is not, because nobody can look at two NACA 0012s and say which one has the wrong
leading-edge radius.

So the law is written twice on purpose -- `app/services/naca_airfoil.py` and
`tools/PreProcessor/include/NacaAirfoil.hpp` -- and this file is what makes the
pair behave as ONE owner. **It drives both**: the preview through the real
`GeometryService.compute_curve_preview_pts`, and the law through the real
`build/surface_resampler` on a config built from a real `SegmentModel.to_dict()`.
A source scan would not do, and #135's finding is why: a claim about a shared
funnel was TRUE in the source while the edit never reached it.

What is checked, and what each check would let through on its own:

  1. The law itself, off the Python owner alone (no build tree needed): the
     thickness digits, the camber digits, the two points that must be EXACT, and
     every refusal with its reason.
  2. The SEGMENTATION. A drawn aerofoil lands as the edges it is split at its
     trailing and leading edges into -- two for a sharp section, three for a
     blunt one -- each an ordinary CAD segment with its own id, so a topology
     template binds by the stable id #137 already resolves and needs no new rule.
  3. PARITY, the criterion this file is named for: preview points vs the
     resampler's own output file, compared numerically over a spread of
     parameters that moves every one of them. The floor is the `.dat`'s own
     10-decimal quantum (5e-11), so the tolerance is 1e-9 and NOT tighter --
     a tolerance below the file's resolution measures the writer, not the law.
  4. The BLUNT trailing edge, PRODUCED: the decision #147 asked for, stated in
     the module docstring and measured here -- its base is a real segment whose
     span is the thickness law's own y(1). The sharp section is the negative
     control: its `te` part is REFUSED, in both hosts, with the reason named.
  5. The round trip: the project file and the pipeline script carry every
     aerofoil parameter, because they go through the one `SegmentModel`
     serialiser -- asserted by driving it, not by reading it.
  6. The OTHER shapes, unchanged. `read_widget_params` / `write_widget_params`
     grew a table where the polygon used to be a hand-written special case, so
     the polygon's exact previous behaviour is pinned, and a circle is driven
     through BOTH hosts the same way the aerofoil is.

NAMED BLIND SPOTS.

  * **This proves the two hosts AGREE, never that either is RIGHT.** Both could
     carry the same wrong coefficient. Check 1 is the only thing standing
     between that and a shipped aerofoil, and it is a handful of published
     figures (0.06 half-thickness at 12%, the x of maximum thickness at 0.3, the
     closed-TE coefficient summing to zero) -- not an independent implementation.
  * **The `full` part under-resolves a BLUNT base, and that is measured rather
     than fixed** (check 4d). The resampler distributes a curve segment's nodes
     uniformly by arc length, so a base 0.25% of chord long gets no interior
     node of its own and the loop cuts that corner. The SEGMENTED form is the
     answer and is what a template binds to; the single-edge `full` shape is a
     convenience, and this says so with a number.
  * **Parity is checked on the points, not on the mesh.** Two hosts agreeing
     about coordinates says nothing about what the mesher then does with them.
  * **No check here drives the Qt canvas.** The preview is exercised through
     `GeometryService`, which is what the canvas calls; that a control-point
     drag reaches it is `test_curve_edit_spec.py`'s and the edit-owner gate's.

Run:  python3 tools/PreProcessor/tests/test_naca_airfoil_parity.py
"""
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []
_RUN = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    _RUN.append(msg)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >180s", flush=True)
    os._exit(99)


_wd = threading.Timer(180, _watchdog)
_wd.daemon = True
_wd.start()

from app.models import shape_spec                                   # noqa: E402
from app.models.project import ProjectModel                         # noqa: E402
from app.models.segment import SegmentModel                         # noqa: E402
from app.services import naca_airfoil as na                         # noqa: E402
from app.services.geometry_service import GeometryService           # noqa: E402

_EXE = os.path.join(_ROOT, "build", "surface_resampler")
tmp = tempfile.mkdtemp(prefix="hybmesh_naca_")


# ── helpers ───────────────────────────────────────────────────────────────── #

def make_seg(params, n, seg_id=1):
    """The SegmentModel the GUI would hold for one aerofoil edge."""
    seg = SegmentModel(seg_id, -1, -1)
    seg.type = "curve"
    seg.curve_type = "naca4"
    seg.strategy = "uniform"
    seg.parameters = dict(params)
    seg.parameters["n_points"] = n
    return seg


def preview(seg, n):
    """What the CANVAS draws."""
    return GeometryService.compute_curve_preview_pts(seg, n, None)


def resample(segs, closed=True, name="af"):
    """What the RESAMPLER writes, through the real binary.

    The config is built from `SegmentModel.to_dict()` and not hand-authored: the
    serialiser IS half of the round trip under test, so a literal dict here
    would prove something the GUI does not do.
    """
    out = os.path.join(tmp, name + ".dat")
    cfg = {"elements": [{"name": name, "input_file": "", "output_file": out,
                         "is_closed": closed,
                         "segments": [s.to_dict() for s in segs]}]}
    cfg_path = os.path.join(tmp, name + ".json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f)
    p = subprocess.run([_EXE, cfg_path], cwd=_ROOT, capture_output=True,
                       text=True, timeout=120)
    pts = []
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            for ln in f:
                if ln.strip():
                    a, b = ln.split()[:2]
                    pts.append((float(a), float(b)))
    return p, pts


def worst_dev(a, b):
    """Largest point-to-point distance between two equal-length point lists."""
    if len(a) != len(b) or not a:
        return float("inf")
    return max(math.hypot(p[0] - q[0], p[1] - q[1]) for p, q in zip(a, b))


# ── 1. the law itself (no build tree needed) ──────────────────────────────── #

m, p_, t = na.parse_designation("2412")
check(abs(m - 0.02) < 1e-15 and abs(p_ - 0.4) < 1e-15 and abs(t - 0.12) < 1e-15,
      "1a. '2412' reads as 2%% camber at 40%% chord, 12%% thick (%g, %g, %g)"
      % (m, p_, t))
check(na.parse_designation("NACA 0012") == (0.0, 0.0, 0.12),
      "1a. ...and a 'NACA ' prefix is accepted")

up = na.airfoil_points("0012", 401, "upper")
ymax = max(y for _x, y in up)
xmax = [x for x, y in up if y == ymax][0]
check(abs(ymax - 0.06) < 5e-5,
      "1b. a 12%% section is 6%% of chord in HALF-thickness (%.6f)" % ymax)
check(abs(xmax - 0.3) < 0.01,
      "1b. ...and its thickest point is at x = 0.3 (%.4f)" % xmax)

check(up[0] == (1.0, 0.0) and up[-1] == (0.0, 0.0),
      "1c. the sharp trailing edge and the leading edge are EXACT, not nearly "
      "(%r, %r)" % (up[0], up[-1]))
lo = na.airfoil_points("0012", 401, "lower")
check(lo[0] == (0.0, 0.0) and lo[-1] == (1.0, 0.0),
      "1c. ...from the lower surface too, so the two really meet (%r, %r)"
      % (lo[0], lo[-1]))
check(all(abs(a[1] + b[1]) < 1e-15 and abs(a[0] - b[0]) < 1e-15
          for a, b in zip(up, list(reversed(lo)))),
      "1c. a symmetric section's two surfaces are exact mirrors")

cam = na.airfoil_points("2412", 401, "upper")
low = na.airfoil_points("2412", 401, "lower")
mid = [((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5)
       for a, b in zip(cam, list(reversed(low)))]
check(abs(max(y for _x, y in mid) - 0.02) < 5e-4,
      "1d. a 2%%-camber section's mean line peaks at 2%% of chord (%.5f)"
      % max(y for _x, y in mid))

check(abs(na.half_thickness(1.0, 0.12, True)) < 1e-15,
      "1e. the closed-TE coefficient really closes it (y(1) = %g)"
      % na.half_thickness(1.0, 0.12, True))
check(abs(na.half_thickness(1.0, 0.12, False) - 0.00126) < 1e-9,
      "1e. the open-TE coefficient leaves 0.0021*t of chord (%g)"
      % na.half_thickness(1.0, 0.12, False))

for bad, why in (("12", "too short"), ("abcd", "not digits"),
                 ("0000", "zero thickness"), ("2012", "camber at x = 0")):
    try:
        na.airfoil_points(bad, 20, "full")
        ok, msg = False, "(no refusal)"
    except na.NacaError as e:
        ok, msg = True, str(e)
    check(ok and bad in msg,
          "1f. '%s' (%s) is refused, and the message names it: %s"
          % (bad, why, msg[:70]))

try:
    na.airfoil_points("0012", 5, "te", sharp_te=True)
    sharp_te_refused, why = False, "(no refusal)"
except na.NacaError as e:
    sharp_te_refused, why = True, str(e)
check(sharp_te_refused and "SHARP" in why,
      "1g. a `te` part on a SHARP section is refused by the law: %s" % why[:80])

rot = na.airfoil_points("0012", 3, "upper", chord=2.0, x_le=1.0, y_le=-1.0,
                        alpha_deg=90.0)
check(abs(rot[-1][0] - 1.0) < 1e-12 and abs(rot[-1][1] + 1.0) < 1e-12,
      "1h. the leading edge lands where it was placed (%r)" % (rot[-1],))
check(abs(rot[0][0] - 1.0) < 1e-12 and abs(rot[0][1] + 3.0) < 1e-12,
      "1h. ...and alpha = 90 deg points the chord along -y, nose up (%r)"
      % (rot[0],))


# ── 2. the segmentation ───────────────────────────────────────────────────── #

check(na.segment_parts(True) == ("upper", "lower"),
      "2a. a SHARP section is split at the TE and the LE: two edges")
check(na.segment_parts(False) == ("upper", "lower", "te"),
      "2b. a BLUNT one adds its trailing-edge base as a third edge")

pm = ProjectModel()
tpl = make_seg({"designation": "2412", "chord": 1.5, "x_le": 0.25,
                "y_le": -0.5, "alpha_deg": 4.0, "sharp_te": True}, 120)
made = pm.add_airfoil_parts(tpl)
check([s.parameters["part"] for s in made] == ["upper", "lower"],
      "2c. drawing one aerofoil adds exactly its parts (%r)"
      % [s.parameters["part"] for s in made])
check(len({s.id for s in made}) == len(made) and all(s.id > 0 for s in made),
      "2c. ...each an ordinary CAD segment with its own id (%r)"
      % [s.id for s in made])
check(all(s.curve_type == "naca4" and s.type == "curve" for s in made),
      "2c. ...and an ordinary analytic edge, not a new kind of object")
shared = {k: v for k, v in made[0].parameters.items() if k != "part"
          and k != "n_points"}
check(all({k: v for k, v in s.parameters.items()
           if k != "part" and k != "n_points"} == shared for s in made),
      "2c. ...all describing ONE aerofoil (same designation, chord, LE, alpha)")

pm2 = ProjectModel()
tpl2 = make_seg({"designation": "0012", "sharp_te": False}, 120)
made2 = pm2.add_airfoil_parts(tpl2)
check([s.parameters["part"] for s in made2] == ["upper", "lower", "te"],
      "2d. a blunt section arrives as THREE edges (%r)"
      % [s.parameters["part"] for s in made2])
check(made2[2].parameters["n_points"] == na.TE_PART_POINTS,
      "2d. ...and the base gets its own node count, not a share of the "
      "surfaces' (%d)" % made2[2].parameters["n_points"])
check(sum(s.parameters["n_points"] for s in made2[:2]) >= 118,
      "2d. ...while the two surfaces split the drawn budget (%d + %d of 120)"
      % (made2[0].parameters["n_points"], made2[1].parameters["n_points"]))

# The parts really are the loop: walking them end to end closes it.
ends = []
for s in made2:
    xs, ys = preview(s, s.parameters["n_points"])
    ends.append(((xs[0], ys[0]), (xs[-1], ys[-1])))
gaps = [math.hypot(ends[i][1][0] - ends[(i + 1) % 3][0][0],
                   ends[i][1][1] - ends[(i + 1) % 3][0][1]) for i in range(3)]
check(max(gaps) < 1e-12,
      "2e. the three parts chain end to end into one closed loop (worst gap "
      "%.3e)" % max(gaps))


# ── 3-6 need the binary ───────────────────────────────────────────────────── #

if not os.path.exists(_EXE):
    print("SKIP build/surface_resampler not found — run ./build.sh "
          "(checks 3-6 are the parity half)", flush=True)
    _wd.cancel()
    shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(1 if _FAILS else 0)

# The `.dat` is written with `std::setprecision(10)` fixed, so half its own
# quantum is 5e-11 and nothing read back out of it can agree more closely than
# that. A tighter tolerance here would be measuring the writer.
TOL = 1e-9

CASES = [
    ("symmetric, the default section", {"designation": "0012", "part": "full"}, 120, True),
    ("cambered upper surface, scaled and pitched",
     {"designation": "2412", "part": "upper", "chord": 2.0, "alpha_deg": 5.0}, 61, False),
    ("cambered lower surface, moved and pitched the other way",
     {"designation": "4415", "part": "lower", "chord": 0.3, "x_le": 1.5,
      "y_le": -2.0, "alpha_deg": -8.0}, 45, False),
    ("a BLUNT section's whole loop",
     {"designation": "0012", "part": "full", "sharp_te": False}, 150, True),
    ("a blunt section's trailing-edge base",
     {"designation": "0021", "part": "te", "sharp_te": False}, 5, False),
    ("thin and thick, at a large angle",
     {"designation": "6409", "part": "full", "chord": 12.5, "x_le": -3.0,
      "alpha_deg": 12.0}, 200, True),
]

worst_overall = 0.0
for i, (label, params, n, closed) in enumerate(CASES):
    seg = make_seg(params, n)
    xs, ys = preview(seg, n)
    gui = list(zip(xs, ys))
    proc, cpp = resample([seg], closed=closed, name="case%d" % i)
    check(proc.returncode == 0,
          "3%s. the resampler accepts %s (rc=%d)" % ("abcdef"[i], label,
                                                     proc.returncode))
    check(len(gui) == len(cpp) == n,
          "3%s. ...and both hosts produce %d points (gui %d, cpp %d)"
          % ("abcdef"[i], n, len(gui), len(cpp)))
    dev = worst_dev(gui, cpp)
    worst_overall = max(worst_overall, dev if dev != float("inf") else 0.0)
    check(dev <= TOL,
          "3%s. ...agreeing to %.3e, under the %.0e tolerance" % ("abcdef"[i],
                                                                 dev, TOL))

check(worst_overall > 0.0,
      "3g. the comparison is really comparing (worst deviation over all six "
      "cases %.3e, which is the .dat's own 10-decimal quantum and not zero)"
      % worst_overall)

# A parameter the gate does not MOVE is a parameter the gate does not check.
moved = set()
for _lbl, params, _n, _c in CASES:
    moved.update(k for k, v in params.items()
                 if v != na.DEFAULTS.get(k, object()))
declared = set(na.DEFAULTS) | {"part"}
check(moved >= declared,
      "3h. every declared aerofoil parameter is moved off its default by at "
      "least one case (missing: %r)" % sorted(declared - moved))


# ── 4. the blunt trailing edge is PRODUCED, the sharp one REFUSES a base ──── #

blunt = make_seg({"designation": "0012", "part": "te", "sharp_te": False}, 5)
_proc, base = resample([blunt], closed=False, name="blunt_te")
span = math.hypot(base[-1][0] - base[0][0], base[-1][1] - base[0][1])
want = 2.0 * na.half_thickness(1.0, 0.12, False)
check(abs(span - want) < 1e-9,
      "4a. the blunt base spans the thickness law's own y(1), doubled "
      "(%.8f vs %.8f)" % (span, want))
check(all(abs(x - 1.0) < 1e-12 for x, _y in base),
      "4a. ...standing at the chord's own trailing edge, x = 1")

sharp_base = make_seg({"designation": "0012", "part": "te", "sharp_te": True}, 5)
proc, pts = resample([sharp_base], closed=False, name="sharp_te")
check(proc.returncode != 0 and not pts,
      "4b. the NEGATIVE CONTROL: a `te` part on a sharp section produces "
      "nothing (rc=%d, %d points)" % (proc.returncode, len(pts)))
first_line = (proc.stderr.strip().splitlines() or [""])[0]
check("SHARP trailing edge" in proc.stderr,
      "4b. ...and the resampler NAMES the reason: %r" % first_line[:90])

bad = make_seg({"designation": "banana", "part": "full"}, 20)
proc, pts = resample([bad], name="bad_desig")
check(proc.returncode != 0 and "four digits" in proc.stderr,
      "4c. a designation the law refuses is refused by the BINARY too, with "
      "its reason (rc=%d)" % proc.returncode)

# The measured limit of the single-edge `full` form on a blunt section, stated
# as a number rather than left for someone to discover: uniform arc-length
# distribution gives a base 0.25% of chord long no interior node of its own.
loop = make_seg({"designation": "0012", "part": "full", "sharp_te": False}, 150)
_proc, lp = resample([loop], name="blunt_loop")
on_base = [q for q in lp if abs(q[0] - 1.0) < 1e-9]
check(len(on_base) < 3,
      "4d. MEASURED, not fixed: the single-edge `full` form leaves the blunt "
      "base with %d node(s) of its own — the SEGMENTED form is what a template "
      "binds to" % len(on_base))


# ── 5. the round trip ─────────────────────────────────────────────────────── #

pm3 = ProjectModel()
pm3.add_airfoil_parts(make_seg({"designation": "4412", "chord": 0.75,
                                "x_le": 2.0, "y_le": 0.125,
                                "alpha_deg": -3.5, "sharp_te": False}, 90))
proj = os.path.join(tmp, "case.json")
pm3.export_config(proj)
pm4 = ProjectModel()
with open(proj, encoding="utf-8") as f:
    pm4.load_from_config(json.load(f))
before = [s.to_dict() for s in pm3.segments]
after = [s.to_dict() for s in pm4.segments]
check(before == after,
      "5a. every aerofoil parameter survives the project file unchanged")

from app.models.pipeline_config import PipelineConfig               # noqa: E402
ws = {"sessions": [{"display_name": "af", "file_path": "",
                    "project_config": {"segments": before}}],
      "project": {}}
pc = PipelineConfig.from_dict(PipelineConfig.from_workspace_dict(ws).to_dict())
check(pc.cads and pc.cads[0]["segments"] == before,
      "5b. ...and the pipeline script, through the same one serialiser")

# The strongest form of the round trip: re-mesh from the RELOADED model and get
# the same points. A key silently dropped anywhere above moves a coordinate.
_proc, a = resample(pm3.segments, name="rt_a")
_proc, b = resample(pm4.segments, name="rt_b")
check(a and worst_dev(a, b) == 0.0,
      "5c. the reloaded case resamples to the SAME %d points" % len(a))


# ── 6. the other shapes are unchanged ─────────────────────────────────────── #

class _PolyOwner:
    class _Edit:
        def __init__(self, t=""):
            self._t = t

        def text(self):
            return self._t

        def setText(self, v):
            self._t = v

    def __init__(self):
        self.poly_vertices = self._Edit("0,0; 2,0; 2,2")


owner = _PolyOwner()
check(shape_spec.read_widget_params(owner, "polygon")
      == {"vertices_str": "0,0; 2,0; 2,2"},
      "6a. a polygon still reads back exactly its vertices string, and nothing "
      "else (the widget tables replaced a hand-written special case)")
shape_spec.write_widget_params(owner, "polygon", {})
check(owner.poly_vertices.text() == shape_spec.POLYGON_DEFAULT,
      "6a. ...and still falls back to the polygon default when the key is "
      "missing (%r)" % owner.poly_vertices.text())

circ = SegmentModel(1, -1, -1)
circ.type = "curve"
circ.curve_type = "circle"
circ.parameters = {"n_points": 37, "cx": 0.3, "cy": -0.2, "r": 2.5}
cxs, cys = preview(circ, 37)
_proc, ccpp = resample([circ], name="circle")
check(worst_dev(list(zip(cxs, cys)), ccpp) <= TOL,
      "6b. the circle's own GUI/resampler agreement is untouched by the new "
      "dispatch entry (%.3e)" % worst_dev(list(zip(cxs, cys)), ccpp))

check(set(shape_spec.DEFAULTS["naca4"]) == set(na.DEFAULTS),
      "6c. shape_spec's aerofoil defaults name exactly the generator's "
      "parameters (%r vs %r)" % (sorted(shape_spec.DEFAULTS["naca4"]),
                                 sorted(na.DEFAULTS)))
check(shape_spec.DEFAULTS["naca4"] == na.DEFAULTS,
      "6c. ...with the same values, so a type switch and a headless call agree")


# ── done ──────────────────────────────────────────────────────────────────── #

print("\n%d checks, %d failed" % (len(_RUN), len(_FAILS)), flush=True)
if _FAILS:
    print("FAILED:", flush=True)
    for f in _FAILS:
        print("  - " + f, flush=True)
_wd.cancel()
shutil.rmtree(tmp, ignore_errors=True)
os._exit(1 if _FAILS else 0)
