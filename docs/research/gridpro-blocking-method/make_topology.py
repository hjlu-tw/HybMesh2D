#!/usr/bin/env python3
"""Write the GridPro-style blocking of ``docs/research/gridpro-blocking-method.md``
section 6 as a runnable ``MESH_MODE 1`` case.

A RESEARCH HARNESS, like ``docs/research/hermite-wall-normal-fill/``'s. Nothing
shipped reads it, nothing in ``config/`` or ``examples/`` is written by it, and
no gate covers the case it emits -- that is the point: it is a reproduction
attempt, not a shipped case.

WHAT IS GRIDPRO'S AND WHAT IS OURS, since the whole value of the file is that
the line is visible:

  * GridPro's, measured out of its own 2-D aerofoil tutorial (section 3 of the
    note): the far field is a CIRCLE OF RADIUS 3 CENTRED ON THE TRAILING EDGE;
    the sharp trailing edge is resolved by THREE straight "internal surfaces"
    radiating from it; and those three BISECT THE EXTERIOR ANGLE EQUALLY, so
    four blocks meet at the trailing edge each with a corner near 90 degrees.
    On its S830 they come out at +78.09 / -18.10 / -101.63 degrees and the four
    sectors at 84.3 / 96.2 / 83.5 / 92.3.
  * GridPro's, and the reason this reproduction can grow: its answer to a badly
    shaped region is MORE BLOCKS, and its tutorial ends with four corners on the
    aerofoil and about nine on the circle. ``--split K`` is that: K block sides
    per surface, so K = 1 gives 4 blocks and 2 body corners, K = 2 gives 6 and
    4, which is the tutorial's own count on the body.
  * OURS: the body. GridPro's S830 lives in a zip that is now behind a sign-in
    wall (section 7), so the rule is executed on the aerofoil this repo already
    ships. The three ray directions are therefore NOT GridPro's numbers -- they
    are GridPro's RULE run on this body, DERIVED here from the polyline's own
    two trailing-edge tangents rather than written down, so a change of body
    moves them.
  * OURS: the node counts, and the four-block floor. GridPro reports 14 blocks;
    the ones this cannot reach are its wrap ring, which needs an offset of a
    sharp trailing edge (section 6c).

The far field needs NO GEOMETRY FILE: every outer side is an analytic arc
(``curve``, #175) whose span comes from its own two corners. That is the part of
GridPro's built-in-surface model this repo does have.

Usage, from the repo root:

    python3 docs/research/gridpro-blocking-method/make_topology.py [--split K]
    ./run.sh -conf docs/research/gridpro-blocking-method/gridpro_airfoil.dat
"""

import argparse
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BODY = "examples/geometries/naca0012_cgrid.dat"
BODY_NAME = "naca0012_cgrid.dat"

FAR_R = 3.0          # GridPro's: "a circle of radius 3 units with center 1 0"
DS_SURF = 0.005      # the shipped C-grid's surface clustering, reused unchanged
N_RADIAL = 41        # the wall-normal class, the shipped C-grid's number
N_SURF = 48          # INTERVALS along one whole surface, the C-grid's number
N_WAKE = 25          # the aft class, the shipped C-grid's number


# -- The body, read once ---------------------------------------------------

def read_body(path):
    """``(points, seg0, seg1)`` -- the stored polyline and its two segments.

    The file is the closed two-segment aerofoil the C-grid case ships: it starts
    AND ends at the trailing edge, and the leading edge is its minimum-x point,
    which is where the sidecar splits it. Each returned segment is the full
    polyline of that side, both endpoints included.
    """
    pts = [tuple(map(float, ln.split()))
           for ln in open(path, encoding="utf-8") if ln.strip()]
    le_i = min(range(len(pts)), key=lambda i: pts[i][0])
    return pts, pts[:le_i + 1], pts[le_i:]


def arc_table(poly):
    """``(cumulative arc length, total)`` along ``poly``."""
    s = [0.0]
    for a, b in zip(poly, poly[1:]):
        s.append(s[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return s, s[-1]


def at_fraction(poly, t):
    """``(point, outward_unit_normal)`` at normalized arc length ``t``.

    The normal is the tangent turned by -90 degrees, which points AWAY from the
    body on both segments because each is walked with the fluid on its left.
    """
    s, total = arc_table(poly)
    target = t * total
    i = max(k for k in range(len(s) - 1) if s[k] <= target)
    a, b = poly[i], poly[i + 1]
    seg = s[i + 1] - s[i]
    u = 0.0 if seg == 0.0 else (target - s[i]) / seg
    p = (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
    tx, ty = b[0] - a[0], b[1] - a[1]
    n = math.hypot(tx, ty)
    return p, (ty / n, -tx / n)


def te_rays(pts):
    """The THREE internal-surface directions, by GridPro's own rule.

    Takes the two tangents leaving the trailing edge and divides the exterior
    fluid angle into four equal sectors. The tangents are CHORDS to the
    neighbouring stored points, not an analytic derivative, because the chord is
    what the mesher's bound edges actually follow.
    """
    te = pts[0]
    up = math.degrees(math.atan2(pts[1][1] - te[1], pts[1][0] - te[0]))
    lo = math.degrees(math.atan2(pts[-2][1] - te[1], pts[-2][0] - te[0]))
    ext = (up - lo) % 360.0
    q = ext / 4.0
    return te, [up - q, up - 2 * q, up - 3 * q], q


# -- Where a radial lands --------------------------------------------------

def cast_to_circle(p, n, c, r):
    """Where the ray ``p + t n`` meets the circle, as an ANGLE about ``c``.

    This is what makes a radial normal to the body at the end it leaves: its
    far-field corner is not chosen, it is where the body's own normal arrives.
    """
    dx, dy = p[0] - c[0], p[1] - c[1]
    b = n[0] * dx + n[1] * dy
    t = -b + math.sqrt(b * b - (dx * dx + dy * dy) + r * r)
    q = (p[0] + t * n[0], p[1] + t * n[1])
    return math.degrees(math.atan2(q[1] - c[1], q[0] - c[0]))


def on_circle(c, r, deg):
    return [c[0] + r * math.cos(math.radians(deg)),
            c[1] + r * math.sin(math.radians(deg))]


def ccw_len(r, deg_a, deg_b):
    """Arc length from ``deg_a`` counter-clockwise to ``deg_b``."""
    return r * math.radians((deg_b - deg_a) % 360.0)


# -- The document ----------------------------------------------------------

def build(split):
    pts, seg_up, seg_lo = read_body(os.path.join(ROOT, BODY))
    te, (a_up, a_wake, a_lo), sector = te_rays(pts)
    c = te                               # the circle is centred ON the trailing edge
    l_up = arc_table(seg_up)[1]
    l_lo = arc_table(seg_lo)[1]

    # The body corners. t = 0 of each segment is a joint the sidecar already
    # carries; the interior ones are fractions of arc length along it.
    # seg 0 runs te -> le, seg 1 runs le -> te.
    fr = [k / split for k in range(1, split)]

    corners = [
        {"id": "te", "kind": "on_geometry", "geom": BODY_NAME, "seg": 0, "t": 0.0},
        {"id": "le", "kind": "on_geometry", "geom": BODY_NAME, "seg": 1, "t": 0.0},
    ]
    corners += [{"id": "u%d" % k, "kind": "on_geometry", "geom": BODY_NAME,
                 "seg": 0, "t": t} for k, t in enumerate(fr)]
    corners += [{"id": "l%d" % k, "kind": "on_geometry", "geom": BODY_NAME,
                 "seg": 1, "t": t} for k, t in enumerate(fr)]

    # Where every radial lands on the circle. The three at the trailing edge are
    # GridPro's bisection; every other is the body's own normal, cast out.
    ang = {"fa": a_up, "fw": a_wake, "fc": a_lo, "fl": 180.0}
    for k, t in enumerate(fr):
        p, n = at_fraction(seg_up, t)
        ang["Fu%d" % k] = cast_to_circle(p, n, c, FAR_R)
        p, n = at_fraction(seg_lo, t)
        ang["Fl%d" % k] = cast_to_circle(p, n, c, FAR_R)
    # The two corners that give each aft block its fourth side. Without them the
    # region between two consecutive rays has three corners and is not a block
    # at all -- the structural finding of section 6c.
    ang["m2"] = 0.5 * (a_wake + a_up)
    ang["m3"] = 0.5 * (a_lo + a_wake)
    corners += [{"id": k, "kind": "free", "xy": on_circle(c, FAR_R, v)}
                for k, v in ang.items()]

    arc = {"kind": "arc", "centre": [c[0], c[1]], "r": FAR_R, "sweep": "ccw"}

    # The chain of corners along each surface, body side and far-field side, in
    # the order the surface is walked.
    up_body = ["te"] + ["u%d" % k for k in range(split - 1)] + ["le"]
    up_far = ["fa"] + ["Fu%d" % k for k in range(split - 1)] + ["fl"]
    lo_body = ["le"] + ["l%d" % k for k in range(split - 1)] + ["te"]
    lo_far = ["fl"] + ["Fl%d" % k for k in range(split - 1)] + ["fc"]

    edges = [
        # GridPro's three internal surfaces. The middle one is the wake and is
        # declared a `cut`; the other two are ordinary interior lines. All three
        # are RADII of the far-field circle, because its centre is the trailing
        # edge -- which is why they reach the outer boundary unaided.
        {"id": "ray_up", "corners": ["te", "fa"], "kind": "interface",
         "count": N_RADIAL, "spacing": {"wall_ends": "start"}},
        {"id": "wake", "corners": ["te", "fw"], "kind": "cut",
         "count": N_WAKE, "spacing": {"ds_start": DS_SURF}},
        {"id": "ray_lo", "corners": ["te", "fc"], "kind": "interface",
         "spacing": {"wall_ends": "start"}},
    ]
    # One radial per remaining body corner, each along the body's own normal.
    for b in ["le"] + ["u%d" % k for k in range(split - 1)] \
            + ["l%d" % k for k in range(split - 1)]:
        f = "fl" if b == "le" else ("F" + b)
        edges.append({"id": "r_%s" % b, "corners": [b, f], "kind": "interface",
                      "spacing": {"wall_ends": "start"}})

    # The body, one block side per stretch, and the far-field arc facing it.
    # THE FAR-FIELD ARC'S CLUSTERING IS THE BODY'S, SCALED BY THE TWO ARC
    # LENGTHS, so the pair carry the SAME NORMALIZED distribution and the grid
    # line between them stays near the body's own normal. DERIVED, not tuned:
    # change the body spacing or the radius and this follows.
    def pair(i, body, far, seg, side, total):
        nb = N_SURF // split + (1 if i < N_SURF % split else 0)
        ab, bb = body[i], body[i + 1]
        af, bf = far[i], far[i + 1]
        # BOTH surfaces are walked in the circle's own counter-clockwise sense
        # -- the upper from the trailing edge forward, the lower from the nose
        # aft -- so the facing arc is always the forward one. Taking it the
        # other way makes the far-field edge sweep 266 deg of the circle and
        # the mesh folds; it is the same mistake in both directions.
        flen = ccw_len(FAR_R, ang[af], ang[bf])
        ratio = flen / (total / split)
        sp, spf = {}, {}
        if i == 0:
            sp["ds_start"] = spf["ds_start"] = DS_SURF
            spf["ds_start"] *= ratio
        if i == split - 1:
            sp["ds_end"] = spf["ds_end"] = DS_SURF
            spf["ds_end"] *= ratio
        eb = {"id": "af_%s_%d" % (side, i), "corners": [ab, bb], "kind": "wall",
              "count": nb + 1, "binding": {"geom": BODY_NAME, "seg": seg},
              "spacing": sp}
        ef = {"id": "ff_%s_%d" % (side, i),
              "corners": [af, bf],
              "kind": "wall", "curve": arc, "spacing": spf}
        return eb, ef

    for i in range(split):
        edges += list(pair(i, up_body, up_far, 0, "up", l_up))
    for i in range(split):
        edges += list(pair(i, lo_body, lo_far, 1, "lo", l_lo))

    # The four aft arcs, closing the circle between the three rays' landings.
    edges += [
        {"id": "ff_aft_up_i", "corners": ["fw", "m2"], "kind": "wall", "curve": arc},
        {"id": "ff_aft_up_o", "corners": ["m2", "fa"], "kind": "wall", "curve": arc,
         "spacing": {"ds_end": DS_SURF * ccw_len(FAR_R, ang["m2"], ang["fa"])
                     / (l_up / split)}},
        {"id": "ff_aft_lo_o", "corners": ["fc", "m3"], "kind": "wall", "curve": arc,
         "spacing": {"ds_start": DS_SURF * ccw_len(FAR_R, ang["fc"], ang["m3"])
                     / (l_lo / split)}},
        {"id": "ff_aft_lo_i", "corners": ["m3", "fw"], "kind": "wall", "curve": arc},
    ]

    # [south, east, north, west], every ring counter-clockwise -- and the SOUTH
    # edge is taken AS DECLARED, which is what decides which of the four an edge
    # may be. On the upper side the aft radial is the south; on the lower side
    # the ring winds the other way, so there the FORWARD radial is.
    blocks = []
    for i in range(split):
        s = "ray_up" if i == 0 else "r_%s" % up_body[i]
        n = "r_le" if i == split - 1 else "r_%s" % up_body[i + 1]
        blocks.append({"id": "b_up_%d" % i,
                       "edges": [s, "ff_up_%d" % i, n, "af_up_%d" % i]})
    for i in range(split):
        s = "r_le" if i == 0 else "r_%s" % lo_body[i]
        n = "ray_lo" if i == split - 1 else "r_%s" % lo_body[i + 1]
        blocks.append({"id": "b_lo_%d" % i,
                       "edges": [s, "ff_lo_%d" % i, n, "af_lo_%d" % i]})
    blocks += [
        {"id": "b_wake_up", "edges": ["wake", "ff_aft_up_i", "ff_aft_up_o", "ray_up"]},
        {"id": "b_wake_lo", "edges": ["ray_lo", "ff_aft_lo_o", "ff_aft_lo_i", "wake"]},
    ]

    for e in edges:                      # an empty spacing object is not a key
        if not e.get("spacing"):
            e.pop("spacing", None)

    return te, [a_up, a_wake, a_lo], sector, ang, \
        {"format_version": 1, "corners": corners, "edges": edges, "blocks": blocks}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", type=int, default=2,
                    help="block sides per surface: 1 -> 4 blocks, 2 -> 6 (default)")
    ap.add_argument("--out", default="gridpro_airfoil.json")
    args = ap.parse_args()

    te, rays, sector, ang, topo = build(args.split)
    nb = len(topo["blocks"])
    hdr = [
        "// GridPro's aerofoil blocking, reproduced -- see",
        "// docs/research/gridpro-blocking-method.md section 6.",
        "//",
        "// GENERATED by make_topology.py --split %d beside this file." % args.split,
        "// Edit that, not this.",
        "//",
        "// GRIDPRO'S, measured out of its own 2-D aerofoil tutorial: a far-field",
        "// CIRCLE of radius %g centred ON THE TRAILING EDGE, and THREE straight" % FAR_R,
        "// internal surfaces radiating from the trailing edge that BISECT THE",
        "// EXTERIOR ANGLE EQUALLY. Because the circle is centred on the trailing",
        "// edge, those three are RADII -- which is why they reach the outer",
        "// boundary with no construction at all. Also GridPro's: the answer to a",
        "// badly shaped region is MORE BLOCKS, and its tutorial ends with four",
        "// corners on the aerofoil. --split %d puts %d there." % (args.split, 2 * args.split),
        "//",
        "// OURS: the body. GridPro's S830 is behind a sign-in wall, so the rule is",
        "// executed on this repo's own aerofoil. DERIVED, not written down:",
        "//   trailing-edge wedge  %.4f deg   exterior %.4f deg" % (360 - 4 * sector, 4 * sector),
        "//   four sectors of      %.4f deg each" % sector,
        "//   the three rays at    %.4f / %.4f / %.4f deg" % tuple(rays),
        "// On GridPro's own S830 the same rule gives +78.09 / -18.10 / -101.63 and",
        "// sectors of 84.3 / 96.2 / 83.5 / 92.3. Here the body is symmetric, so the",
        "// middle ray is the x axis exactly and the wake is straight BY DERIVATION.",
        "//",
        "// OURS: %d blocks. GridPro's tutorial reports 14; the ones this cannot" % nb,
        "// reach are its wrap ring, which needs an offset of a sharp trailing edge.",
        "//",
        "// Every other radial leaves along the BODY'S OWN OUTWARD NORMAL and its",
        "// far-field corner is where that normal ARRIVES, not a chosen angle; and",
        "// each far-field arc carries its body edge's clustering scaled by the two",
        "// arc lengths, so the facing pair share one normalized distribution.",
    ]
    out = os.path.join(HERE, args.out)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(hdr) + "\n" + json.dumps(topo, indent=2) + "\n")
    print("wrote %s  (%d blocks, %d corners, %d edges)"
          % (os.path.relpath(out, ROOT), nb, len(topo["corners"]), len(topo["edges"])))
    print("  trailing edge at %s" % (te,))
    print("  rays at %.6f / %.6f / %.6f deg, four sectors of %.6f deg"
          % (rays[0], rays[1], rays[2], sector))
    print("  circle corners, counter-clockwise from the wake:")
    for k, v in sorted(ang.items(), key=lambda kv: kv[1] % 360.0):
        print("    %-5s %9.4f deg" % (k, v))


if __name__ == "__main__":
    main()
