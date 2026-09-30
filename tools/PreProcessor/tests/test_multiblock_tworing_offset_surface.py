#!/usr/bin/env python3
"""A TWO-RING O-GRID whose middle ring was COMPUTED, end to end (issue #154).

#151 shipped the key (``follows``), #152 shipped the CAD-stage offset and #153
shipped a two-ring O-grid whose middle ring is a hand-drawn concentric circle.
This is the case the batch exists for: the two halves meeting on a body whose
offset nobody could have drawn. From ``examples/topology/tworing_offset.json`` +
``config/multiblock_tworing_offset.dat``, and — like #153 — it needed no C++
change at all.

THE BODY IS A 2:1 ELLIPSE AND THAT IS THE WHOLE POINT. A circle's offset is a
circle, so #153's middle ring could be drawn; an ellipse's offset is not an
ellipse, and the nearest curve this tool can draw — a concentric ellipse through
the same four corners — is measurably the wrong curve (check 3). The shipped
offset is written by ``app/services/geometry_offset.py``, the ONE owner, and this
gate re-derives it rather than trusting the committed file.

What this pins down:

  1. THE SHIPPED FILES ARE WHAT THEIR GENERATORS PRODUCE. The body against the
     ellipse generator, and the middle ring against the REAL offset service run
     on the body's own array — so "computed rather than drawn" is measured here
     and not asserted in prose. Same property check 1 of the O-grid and two-ring
     gates make, and for the same reason: a hand-edited ``.dat`` whose ``.meta``
     still describes the old point set is a mesh with corners on the wrong
     segments and no error at all.
  2. SEGMENT FOR SEGMENT, BY CONSTRUCTION. The offset's sidecar carries the same
     segment ids at the same point indices as the body's, checked as the two
     index lists rather than as a count — which is what makes a stable id on the
     offset mean the same thing as the id it mirrors, with no re-segmenting step
     asked of anybody.
  3. THE RING IS A CONSTANT THICKNESS AND THE HAND-DRAWN ALTERNATIVE IS NOT.
     Every point of the middle ring is 0.25 from the body to within the miter's
     own excess, while the concentric ellipse through the same four corners falls
     to 0.2415 at the nose — 3.39% of the thickness asked for, in the one place a
     boundary layer is thickest. That number is why this curve is computed.
  4. THE SHIPPED CASE MESHES: exit 0, zero inverted cells, eight blocks of
     25 x 25, and the machine-readable ``HYBMESH_MB_QUALITY`` line.
  5. THE RUN NAMES the four seam edges as interfaces FOLLOWING their own segment
     of ``ellipse_offset.dat``, and names the eight radials straight chords.
  6. THE SEAM'S 96 NODES LIE ON THE OFFSET POLYLINE, not on the four chords
     between its corners, measured point-to-SEGMENT against the committed
     polyline itself (this ring is not a circle, so there is no radius to
     recompute it from). The negative control is the same document with its four
     ``follows`` removed.
  7. THE SEAM IS NOT A BOUNDARY. No ``.bnd`` face has both ends on the middle
     ring, and no patch carries its sidecar's label ``seam``.
  8. THE TWO RINGS ARE CONTINUOUS ACROSS THE SEAM: the last cell into it and the
     first cell out of it agree to nine decimals on the unsmoothed mesh, because
     the topology's ``ds_start`` IS the inner ring's own last interval. Negative
     control: the same document with that key removed.
  9. THE GRID IS CONFORMING, on the exported files.
 10. THE COMPARISON #150 ASKED FOR, AND ON THE BODY #153 SAID IT COULD NOT SPEAK
     FOR. #153's blind spot was that a circle is where a single tanh law has the
     least trouble, so its measurement said nothing about a body whose
     wall-normal extent varies around it. This is that body, and the control is
     the SINGLE-ring O-grid on the same ellipse at the same budget — 4704
     vertices, 9216 triangles, 192 boundary edges — built here rather than
     shipped, because a single ring on this body is not a case anybody should
     run. Measured at the default 20 sweeps AND unsmoothed.

Run:  python3 tools/PreProcessor/tests/test_multiblock_tworing_offset_surface.py
      python3 tools/PreProcessor/tests/test_multiblock_tworing_offset_surface.py --write
          rewrites the shipped body and its offset from the generators.
Skips cleanly if ./build/HybMesh2D has not been built.
"""
import json
import math
import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_GEOM = os.path.join(_REPO, "examples", "geometries")
_TOPO = os.path.join(_REPO, "examples", "topology", "tworing_offset.json")
sys.path.insert(0, _HERE)
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

# ── the shipped case, as numbers ───────────────────────────────────────────
#: The body: semi-major, semi-minor, points per quarter, BC label.
BODY = (0.5, 0.25, 120, "wall")
#: The middle ring: the SIGNED distance the offset service is asked for, and the
#: label its sidecar carries. That label reaches nothing — a following edge takes
#: no condition — which check 7 is what proves.
OFFSET_D, OFFSET_BC = 0.25, "seam"
#: Far field: the r = 10 circle the single-ring and two-ring O-grids already use.
FAR_R = 10.0


# The ONE parser for the machine-readable quality line, in the gate that owns it.
from test_multiblock_quality_surface import qlines as _qlines            # noqa: E402
# The ONE set of exported-file readers, in the gate that owns welding.
from test_multiblock_weld_surface import (                               # noqa: E402
    bnd_faces, cel_cells, components, edge_use, vrt_nodes)
# The ONE writer of this repo's closed-polyline `.meta` convention.
from test_multiblock_cgrid_surface import closed_polyline_meta           # noqa: E402
# THE ONE shipped-config retargeter (#126), imported and never re-implemented.
from mb_shipped_config import shipped_config                             # noqa: E402
from mesher_bin import NO_SMOOTH, mesher_env as _mesher_env              # noqa: E402
# THE ONE owner of the offset law (#152). The shipped middle ring is what this
# returns, which is the whole claim of the case and is check 1 here.
from app.services.geometry_offset import offset_points                   # noqa: E402

failures = []


def check(msg, cond):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


# ── The ONE generator for each shipped geometry ────────────────────────────

def _arc(a, b, t, panels=1024):
    """Arc length of ``(a cos, b sin)`` from 0 to ``t``, by composite Simpson.

    Pure Python and a FIXED panel count, so the shipped file is reproducible:
    check 1 compares the committed text, and a generator whose answer moved with
    a library version would make that check a coin toss. 1024 panels over a
    quarter leave a truncation error near 1e-16 of the length, which is below the
    12 decimals the file carries.
    """
    h = t / panels
    total = 0.0
    for k in range(panels):
        for u, w in ((k * h, 1.0), ((k + 0.5) * h, 4.0), ((k + 1) * h, 1.0)):
            total += w * math.hypot(a * math.sin(u), b * math.cos(u))
    return total * h / 6.0


def _t_at_arc(a, b, s, quarter_len):
    """The parameter at arc length ``s``, by Newton on :func:`_arc`.

    The derivative is the integrand itself, so Newton converges in a handful of
    steps from the circular guess; the two ends are returned EXACTLY rather than
    solved for, because a quarter boundary is a block corner and one ulp there
    moves a corner off the axis it is declared on.
    """
    if s <= 0.0:
        return 0.0
    if s >= quarter_len:
        return math.pi / 2.0
    t = (s / quarter_len) * (math.pi / 2.0)
    for _ in range(40):
        d = math.hypot(a * math.sin(t), b * math.cos(t))
        step = (_arc(a, b, t) - s) / d
        t -= step
        if abs(step) < 1e-15:
            break
    return t


def ellipse_segments(a, b, per_quarter):
    """The ellipse as four quarter segments, each cut into equal ARC LENGTHS.

    The quarters are EXACT REFLECTIONS of the first, not four separate solves, so
    the four are congruent to the last bit and the body's own four-fold symmetry
    is not something the sampler could break.

    Each segment includes both endpoints, which is what
    ``closed_polyline_meta`` expects; consecutive segments overlap by one point
    and that shared joint — on an axis, where a block corner is declared — belongs
    to the later of the two.
    """
    ql = _arc(a, b, math.pi / 2.0)
    ts = [_t_at_arc(a, b, ql * k / per_quarter, ql) for k in range(per_quarter + 1)]
    q0 = [(a * math.cos(t), b * math.sin(t)) for t in ts]
    q0[0] = (a, 0.0)
    q0[-1] = (0.0, b)
    q1 = [(-x, y) for x, y in reversed(q0)]
    q2 = [(-x, -y) for x, y in q0]
    q3 = [(x, -y) for x, y in reversed(q0)]
    return [q0, q1, q2, q3]


def closed_array(segs):
    """The point array a file built from ``segs`` actually holds.

    ``closed_polyline_meta`` drops each segment's last point and appends the
    first point again, so this is the array the offset must be taken OF — not the
    concatenation, which would repeat every joint.
    """
    pts = [p for s in segs for p in s[:-1]]
    return pts + [pts[0]]


def write_ellipse(a, b, per_quarter, bc):
    """``(dat_text, meta_text)`` for the body: a closed ellipse in four quarters."""
    return closed_polyline_meta(ellipse_segments(a, b, per_quarter), [bc] * 4)


def write_offset(a, b, per_quarter, distance, bc):
    """``(dat_text, meta_text)`` for the middle ring, FROM THE OFFSET SERVICE.

    Not a formula: ``offset_points`` is the one owner of the offset law, and the
    whole claim of this case is that the shipped curve is what a user gets from
    CAD ▸ Offset Geometry… on the shipped body. It returns one point per source
    point in the same order, so the four quarters are cut at the SAME indices the
    body's are and the two sidecars carry the same segment ids at the same rows —
    which is check 2, and which is what "segment for segment, by construction"
    means.
    """
    segs = ellipse_segments(a, b, per_quarter)
    out = offset_points(closed_array(segs), distance, True)
    n = per_quarter
    off = [[(float(out[k][0]), float(out[k][1]))
            for k in range(s * n, (s + 1) * n + 1)] for s in range(4)]
    return closed_polyline_meta(off, [bc] * 4)


SHIPPED = (
    ("ellipse_body", lambda: write_ellipse(*BODY)),
    ("ellipse_offset", lambda: write_offset(BODY[0], BODY[1], BODY[2],
                                            OFFSET_D, OFFSET_BC)),
)


def _write_shipped():
    for name, gen in SHIPPED:
        dat, meta = gen()
        with open(os.path.join(_GEOM, name + ".dat"), "w", encoding="utf-8") as f:
            f.write(dat)
        with open(os.path.join(_GEOM, name + ".dat.meta"), "w", encoding="utf-8") as f:
            f.write(meta)
        print("wrote " + name)


# ── driving the shipped case ───────────────────────────────────────────────

def base_config(topo=None, geom_dir=None):
    """The shipped config, retargeted at a temp output stem.

    Read from disk rather than rebuilt, for the reason `mb_shipped_config` gives:
    ``config/multiblock_tworing_offset.dat`` is documentation a user runs, and a
    test that composed an equivalent one would leave an edit to the shipped file
    invisible from the gate that is supposed to be covering it.

    The name is ``base_config`` because ``tools/scripts/golden_mesh.py`` reaches
    every shipped multi-block case through ``mod.base_config()``. BOTH arguments
    default to nothing rather than to this file's ``_TOPO`` and ``_GEOM``: a
    default that names the shipped value asks for it BY NAME, so the gate would
    go on driving the same topology after the shipped config was repointed.
    """
    return shipped_config(
        "multiblock_tworing_offset",
        paths=({"MESH_TOPOLOGY_FILE": topo} if topo is not None else None),
        dirs=({"GEOM_FILE": geom_dir} if geom_dir is not None else None))


def fixture():
    """The checked-in topology as data, so a variant differs from it by one key.

    The shipped documents carry ``//`` comments, which the mesher's parser accepts
    and Python's does not."""
    text = "\n".join(ln for ln in open(_TOPO, encoding="utf-8").read().splitlines()
                     if not ln.lstrip().startswith("//"))
    return json.loads(text)


def edge(doc, eid):
    for e in doc["edges"]:
        if e["id"] == eid:
            return e
    raise AssertionError("no edge %r in the shipped topology" % eid)


def run(tmp, name, conf_text, extra=""):
    stem = os.path.join(tmp, name)
    conf = os.path.join(tmp, name + ".dat")
    with open(conf, "w", encoding="utf-8") as f:
        f.write(conf_text.replace("@STEM@", stem) + extra)
    p = subprocess.run([_BIN, "-conf", conf], cwd=tmp, env=_mesher_env(),
                       capture_output=True, text=True, timeout=600)
    return p, stem, (p.stdout or "") + (p.stderr or "")


def write_doc(tmp, name, doc):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    return path


def quality(out):
    """The quality line for the mesh AS EXPORTED, or ``{}`` when there is none."""
    q = _qlines(out)
    return q[0] if q else {}


def ray_nodes(stem):
    """The exported nodes on the +x axis, in order — one whole radial line.

    The body, its offset and the far field all have a vertex at angle 0 and all
    three corner rings are declared at the t = 0 of their segment 0, so this ray
    carries a node of every radial station and both seam ends."""
    return sorted(x for (x, y) in vrt_nodes(stem) if abs(y) < 1e-12 and x > 0.0)


def intervals(xs):
    return [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]


def ratios(iv):
    return [iv[i + 1] / iv[i] for i in range(len(iv) - 1)]


# ── measuring against the middle ring itself ───────────────────────────────

def read_dat(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.split()
            if len(s) >= 2:
                out.append((float(s[0]), float(s[1])))
    return out


def seg_ids(meta_path):
    """The per-point segment id column of a ``.meta`` sidecar, in file order."""
    rows, take = [], 0
    with open(meta_path, encoding="utf-8") as f:
        for line in f:
            s = line.split()
            if not s:
                continue
            if s[0] == "POINTS":
                take = int(s[1])
                continue
            if take and len(s) == 2 and len(rows) < take:
                rows.append(int(s[0]))
    return rows


def dist_to_polyline(p, poly):
    """Point-to-SEGMENT distance to a polyline.

    The middle ring is not a circle, so — unlike #153's gate — there is no radius
    to recompute it from and the committed polyline itself is the ruler."""
    best = float("inf")
    for k in range(len(poly) - 1):
        (ax, ay), (bx, by) = poly[k], poly[k + 1]
        vx, vy = bx - ax, by - ay
        d2 = vx * vx + vy * vy
        t = 0.0 if d2 <= 0.0 else ((p[0] - ax) * vx + (p[1] - ay) * vy) / d2
        t = min(1.0, max(0.0, t))
        best = min(best, math.hypot(p[0] - (ax + t * vx), p[1] - (ay + t * vy)))
    return best


def chord_poly(poly, per_quarter):
    """The four CHORDS between the middle ring's corners, as a polyline.

    What the seam would be with ``follows`` gone, and therefore the negative
    control's own ruler."""
    idx = [0, per_quarter, 2 * per_quarter, 3 * per_quarter, 4 * per_quarter]
    return [poly[i] for i in idx]


def shared_edges(out):
    """``{edge id: path-source phrase}`` from the shared-edge report."""
    got = {}
    for m in re.finditer(r"- Interface '(\w+)'\s*:.*?, (a straight chord|following "
                         r"segment \d+ of '[^']+')", out):
        got[m.group(1)] = m.group(2)
    return got


def single_ring_doc(doc):
    """The SAME ellipse and far field as ONE ring, at the SAME budget.

    Built here rather than shipped, because a single ring on this body is not a
    case anybody should run — it is the control that makes check 10 a
    measurement. 49 radial nodes against the two rings' 25 + 25 - 1, so the two
    meshes have the same 4704 vertices and the same 9216 cells.

    Derived from the shipped document rather than written out again: its body
    edges, its far-field edges and its corners are taken verbatim, so an edit to
    the shipped case moves the control with it instead of leaving the comparison
    measuring two different bodies.
    """
    keep = {c["id"] for c in doc["corners"] if not c["id"].startswith("m")}
    out = {"format_version": 1,
           "corners": [c for c in doc["corners"] if c["id"] in keep],
           "edges": [], "blocks": []}
    for k in range(4):
        e = {"id": "r%d" % k, "corners": ["b%d" % k, "f%d" % k],
             "kind": "interface", "spacing": {"wall_ends": "start"}}
        if k == 0:
            e["count"] = 49
        out["edges"].append(e)
    out["edges"] += [dict(edge(doc, "w%d" % k)) for k in range(4)]
    out["edges"] += [dict(edge(doc, "o%d" % k)) for k in range(4)]
    out["blocks"] = [{"id": "c%d" % k,
                      "edges": ["r%d" % k, "o%d" % k, "r%d" % ((k + 1) % 4),
                                "w%d" % k]} for k in range(4)]
    return out


def main() -> int:
    if "--write" in sys.argv:
        _write_shipped()
        return 0
    if not os.path.exists(_BIN):
        print("SKIP: build/HybMesh2D not found (run ./build.sh first)")
        return 0

    a, b, per_q, _bc = BODY

    # ── 1. the shipped geometries ARE what the generators produce ──────────
    for name, gen in SHIPPED:
        dat, meta = gen()
        for ext, want in ((".dat", dat), (".dat.meta", meta)):
            path = os.path.join(_GEOM, name + ext)
            got = open(path, encoding="utf-8").read() if os.path.exists(path) else None
            check("1. %s%s is exactly what its generator produces" % (name, ext),
                  got == want)

    body_pts = read_dat(os.path.join(_GEOM, "ellipse_body.dat"))
    ring_pts = read_dat(os.path.join(_GEOM, "ellipse_offset.dat"))

    # ── 2. segment for segment, by construction ────────────────────────────
    b_ids = seg_ids(os.path.join(_GEOM, "ellipse_body.dat.meta"))
    r_ids = seg_ids(os.path.join(_GEOM, "ellipse_offset.dat.meta"))
    check("2a. the offset holds one point per source point, in the same order",
          len(ring_pts) == len(body_pts) == 4 * per_q + 1)
    check("2b. the two sidecars carry the SAME segment id at every row — the "
          "pairing holds with nothing re-segmented", b_ids == r_ids and len(b_ids) > 0)
    check("2c. and there are four of them, the body's own",
          sorted(set(b_ids)) == [0, 1, 2, 3])

    # ── 3. a constant-thickness ring; the drawable alternative is not ──────
    thick = [dist_to_polyline(p, body_pts) for p in ring_pts]
    drawn = [dist_to_polyline((math.cos(2 * math.pi * k / 4000) * (a + OFFSET_D),
                               math.sin(2 * math.pi * k / 4000) * (b + OFFSET_D)),
                              body_pts) for k in range(4001)]
    short = (OFFSET_D - min(drawn)) / OFFSET_D
    print("   ring thickness %.6f..%.6f; concentric ellipse %.6f..%.6f "
          "(%.2f%% short)" % (min(thick), max(thick), min(drawn), max(drawn),
                              100.0 * short))
    check("3a. every middle-ring point is 0.25 from the body to within the "
          "miter's own excess",
          min(thick) >= OFFSET_D - 1e-9 and max(thick) <= OFFSET_D * (1.0 + 1e-3))
    check("3b. the concentric ellipse through the same four corners is short at "
          "the nose by more than 3% of the thickness asked for",
          short > 0.03)
    check("3c. and it is short, never long — so it cannot be read as the same "
          "curve sampled differently", max(drawn) <= OFFSET_D * (1.0 + 1e-3))

    tmp = tempfile.mkdtemp(prefix="tworing_offset_")
    doc = fixture()

    # ── 4. the shipped case meshes ─────────────────────────────────────────
    p, stem, out = run(tmp, "ship", base_config())
    check("4a. the shipped case exits 0", p.returncode == 0)
    q = quality(out)
    check("4b. zero inverted cells", q.get("inverted") == 0)
    check("4c. 9216 cells, the shipped O-grids' budget", q.get("cells") == 9216)
    nodes = vrt_nodes(stem)
    cells = cel_cells(stem)
    faces = bnd_faces(stem)
    check("4d. 4704 vertices / 9216 cells / 192 boundary edges",
          (len(nodes), len(cells), len(faces)) == (4704, 9216, 192))

    # ── 5. the run says which interior lines follow a curve ────────────────
    se = shared_edges(out)
    check("5a. all four seam edges are reported FOLLOWING their own segment of "
          "the offset geometry",
          all(se.get("s%d" % k) == "following segment %d of 'ellipse_offset.dat'" % k
              for k in range(4)))
    check("5b. the eight radials are reported as straight chords",
          all(se.get(e) == "a straight chord"
              for e in [p_ + str(k) for p_ in ("ri", "ro") for k in range(4)]))

    # ── 6. the seam lies on the COMPUTED ring, not on its chords ───────────
    # Measured on the UNSMOOTHED mesh, because the negative control's seam is an
    # ordinary interface and the smoother MOVES it — which is the difference
    # check 6d is about and would otherwise silently decide 6c.
    _, ustem, _u = run(tmp, "unsm", base_config(), extra=NO_SMOOTH)
    unodes = vrt_nodes(ustem)
    chords = chord_poly(ring_pts, per_q)
    band = max(dist_to_polyline(p_, chords) for p_ in ring_pts)
    tol = band / 1.0e4
    on_ring = [p_ for p_ in unodes if dist_to_polyline(p_, ring_pts) <= tol]
    worst = max(dist_to_polyline(p_, ring_pts) for p_ in on_ring) if on_ring else -1
    print("   seam nodes off the ring by at most %.3e; the quarter chords depart "
          "from it by %.4f (band %.3e)" % (worst, band, tol))
    check("6a. the seam's 96 nodes lie on the middle ring's own polyline",
          len(on_ring) == 96)
    check("6b. and the chord sagitta is orders larger, so 6a cannot pass by the "
          "two being close", band > 1.0e4 * max(worst, 1e-15))
    nof = fixture()
    for k in range(4):
        edge(nof, "s%d" % k).pop("follows")
    _, cstem, _o = run(tmp, "nofollow", base_config(
        topo=write_doc(tmp, "nofollow.json", nof)), extra=NO_SMOOTH)
    ctrl = [p_ for p_ in vrt_nodes(cstem)
            if dist_to_polyline(p_, chords) <= tol]
    check("6c. NEGATIVE CONTROL: with the four `follows` removed the same 96 "
          "nodes lie on the chords instead", len(ctrl) == 96)
    check("6d. and the seam SURVIVES the shipped default of 20 sweeps: the same "
          "96 nodes are still on the ring in the exported file",
          len([p_ for p_ in nodes
               if dist_to_polyline(p_, ring_pts) <= tol]) == 96)

    # ── 7. the seam is not a boundary ──────────────────────────────────────
    idx = {}
    for i, p_ in enumerate(nodes):
        idx[i + 1] = p_
    onring = {i for i, p_ in idx.items() if dist_to_polyline(p_, ring_pts) <= 1e-9}
    check("7a. no .bnd face has both ends on the middle ring",
          not any(len(f & onring) == 2 for f, _n in faces))
    check("7b. no patch carries the middle ring's sidecar label 'seam'",
          OFFSET_BC not in {n for _f, n in faces})
    check("7c. the .bnd is the body and the far field and nothing else",
          {n for _f, n in faces} == {"wall", "farfield"})

    # ── 8. the two rings are continuous across the seam ────────────────────
    iv = intervals(ray_nodes(ustem))
    check("8a. the first cell out of the seam IS the last cell into it, to nine "
          "decimals", round(iv[24] / iv[23], 9) == 1.0)
    nods = fixture()
    for k in range(4):
        edge(nods, "ro%d" % k)["spacing"] = {}
    _, dstem, _d = run(tmp, "nods", base_config(
        topo=write_doc(tmp, "nods.json", nods)), extra=NO_SMOOTH)
    div = intervals(ray_nodes(dstem))
    print("   seam ratio: shipped %.9f, with ds_start removed %.3f"
          % (iv[24] / iv[23], div[24] / div[23]))
    check("8b. NEGATIVE CONTROL: with `ds_start` removed the outer ring goes "
          "uniform and the seam is a jump", div[24] / div[23] > 5.0)

    # ── 9. the grid is conforming ──────────────────────────────────────────
    use = edge_use(cells)
    check("9a. every interior edge belongs to exactly two cells",
          sorted({v for v in use.values()}) == [1, 2])
    check("9b. the boundary edge set is exactly the .bnd",
          {e for e, v in use.items() if v == 1} == {f for f, _n in faces})
    check("9c. one connected component", components(cells, len(nodes)) == 1)

    # ── 10. the comparison, against a SINGLE ring on the same body ─────────
    one = write_doc(tmp, "single.json", single_ring_doc(doc))
    rows = {}
    for label, extra in (("default", ""), ("unsmoothed", NO_SMOOTH)):
        _, s2, o2 = run(tmp, "single_" + label.strip(), base_config(topo=one),
                        extra=extra)
        _, s1, o1 = run(tmp, "two_" + label.strip(), base_config(), extra=extra)
        q1, q2 = quality(o1), quality(o2)
        rows[label] = (q1, q2, ray_nodes(s1), ray_nodes(s2))
        check("10a-%s. the control is the SAME budget, read off both runs"
              % label,
              q1.get("cells") == q2.get("cells") == 9216
              and len(vrt_nodes(s1)) == len(vrt_nodes(s2)) == 4704)
        print("   %-10s two-ring: nonortho %.4f/%.4f wall %.6f | single: "
              "%.4f/%.4f wall %.6f" % (
                  label, q1.get("nonortho_max_deg", -1), q1.get("nonortho_mean_deg", -1),
                  q1.get("wall_first_cell_worst_rel", -1),
                  q2.get("nonortho_max_deg", -1), q2.get("nonortho_mean_deg", -1),
                  q2.get("wall_first_cell_worst_rel", -1)))
        r1 = max(ratios(intervals(rows[label][2])))
        r2 = max(ratios(intervals(rows[label][3])))
        print("   %-10s worst wall-normal expansion on the +x ray: two-ring "
              "%.4f, single %.4f" % (label, r1, r2))
    d1, d2 = rows["default"][0], rows["default"][1]
    check("10b. at the DEFAULT 20 sweeps the two rings hold the wall spacing "
          "better than one",
          d1["wall_first_cell_worst_rel"] < d2["wall_first_cell_worst_rel"])
    check("10c. and are better on worst non-orthogonality",
          d1["nonortho_max_deg"] < d2["nonortho_max_deg"])
    check("10d. and WORSE on mean non-orthogonality — stated because the case "
          "is not allowed to publish only the half that flatters it",
          d1["nonortho_mean_deg"] > d2["nonortho_mean_deg"])
    check("10e. and WORSE on the worst wall-normal expansion ratio, as #153's "
          "circle also was",
          max(ratios(intervals(rows["default"][2])))
          > max(ratios(intervals(rows["default"][3]))))
    u1, u2 = rows["unsmoothed"][0], rows["unsmoothed"][1]
    check("10f. UNSMOOTHED the wall reading REVERSES: the arc-length rule that "
          "places a following edge's nodes does not put them normal-opposite the "
          "body's on a body of varying curvature, and 20 sweeps are what repair it",
          u1["wall_first_cell_worst_rel"] > 10.0 * u2["wall_first_cell_worst_rel"])

    print("\n%d checks failed" % len(failures))
    for f in failures:
        print("  - " + f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
