#!/usr/bin/env python3
"""A STACK of count-reducing rings on the SHIPPED AEROFOIL, not on a circle.

A RESEARCH HARNESS beside ``docs/research/nesting-blocks-at-a-complicated-leading-edge.md``
section 16. Nothing shipped reads it; nothing in ``config/``, ``examples/``,
``src/`` or ``include/`` is written or changed by it, and it adds no geometry
file: it reads the two the shipped C-grid reads.

WHY A FOURTH GENERATOR, in the shape ``make_rings.py`` already uses for the same
reason. ``make_reducing_annulus.py`` writes one reducing ring and
``make_reducing_stack.py`` stacks them -- both on ``circle_body.dat``.
``make_reducing_cgrid.py`` writes ONE reducing band on the aerofoil. This is the
stack on the aerofoil, which is the case that matters: the circle was never the
subject, it was the geometry whose boundary conditions were easiest to bind.

THE LEVEL MACHINERY IS ``make_reducing_stack.py``'s AND THE ARITHMETIC IS THE
SAME. With two ordinary blocks per unit a reducing band takes ``K(2a + 2m)``
intervals to ``2Km`` and ``4K`` stations to ``2K``; with its radial depth ``a``
equal to its arc count ``m`` both halve, so a stack is K, K/2, K/4 and the
counts are N, N/2, N/4. ``a = m`` is forced, not chosen: the corner block ties
its two radials to the two arcs it carries.

WHAT IS DIFFERENT FROM THE CIRCLE, and it is the whole of the extra work. The
C's ring is OPEN -- it runs from the upper trailing edge, round the nose, to the
lower one -- so the stations are a LINE and not a cycle, and there is a WAKE
COLUMN at the open end: at every level the te-side station carries a line out to
the outlet plane, and the band between two levels has two wake blocks between
those lines. The first band's pair share the wake CUT; every pair above them is
bounded by the two levels' own wake lines.

    python3 docs/research/gridpro-blocking-method/make_cgrid_stack.py
    ./run.sh -conf docs/research/gridpro-blocking-method/cgrid_stack.dat
"""

import argparse
import itertools
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BODY, FAR = "naca0012_cgrid.dat", "cgrid_farfield.dat"
CENTRE = (1.0, 0.0)                      # the chain case's own seam centre


def seg_table(name):
    import numpy as np
    pts = np.loadtxt(os.path.join(ROOT, "examples/geometries", name))
    rows = [l.split() for l in
            open(os.path.join(ROOT, "examples/geometries", name + ".meta"),
                 encoding="utf-8").read().splitlines()]
    i = next(k for k, r in enumerate(rows) if r and r[0] == "POINTS")
    seg = [int(r[0]) for r in rows[i + 1:i + 1 + len(pts)]]
    out, start = [], 0
    for key, grp in itertools.groupby(seg):
        n = len(list(grp))
        if out and key == out[0][0]:
            break
        sl = pts[start:start + n + 1] if start + n < len(pts) else pts[start:]
        d = np.r_[0.0, np.cumsum(np.hypot(*(sl[1:] - sl[:-1]).T))]
        out.append((key, d, sl))
        start += n
    return out


def station_at_fraction(table, segs, frac):
    lens = [table[s][1][-1] for s in segs]
    target = frac * sum(lens)
    for s, L in zip(segs, lens):
        if target <= L or s == segs[-1]:
            return s, min(1.0, max(0.0, target / L))
        target -= L          # walked past this segment; the rest is the next's
    raise AssertionError


def body_frame(table, seg, t):
    """(point, outward unit normal) at normalised arc length `t` of `seg`."""
    import numpy as np
    _, cum, pts = table[seg]
    sdist = t * cum[-1]
    i = int(np.searchsorted(cum, sdist, side="right")) - 1
    i = max(0, min(i, len(pts) - 2))
    f = (sdist - cum[i]) / max(cum[i + 1] - cum[i], 1e-15)
    p = pts[i] + (pts[i + 1] - pts[i]) * f
    d = pts[i + 1] - pts[i]
    L = math.hypot(d[0], d[1]) or 1.0
    # The body is traversed te -> le on segment 0 and le -> te on segment 1,
    # which is CLOCKWISE around it, so the outward normal is the tangent turned
    # a quarter turn the OTHER way from the usual convention.
    n = (d[1] / L, -d[0] / L)
    return (float(p[0]), float(p[1])), n


def ray_point(P, n, F, sigma, Rref):
    """A point on the station's own ray: normal at the body, F at sigma = 1.

    `Rref` is one length for the whole stack, so a level is a constant distance
    out along every station's ray and reads as a smooth offset of the body.

    THIS IS THE FIX FOR THE ONE DEFECT SECTION 16g NAMED AND NOBODY HAD TRIED.
    Placing a level's stations by arc length along an ellipse puts a mid-chord
    body point against an ellipse point that is nowhere near its normal, and the
    radial then runs almost ALONG the aerofoil: measured as a mean
    non-orthogonality of 26 degrees on the first draft of this file, against the
    10.5 of a four-block mesh at the same body count. Here each station keeps its
    OWN ray -- it leaves the body along the normal and bends to arrive at its own
    far-field station -- so every level's correspondence with the body is the
    body's own normal direction, by construction and not by a mapping.
    """
    u = (F[0] - P[0], F[1] - P[1])
    Lu = math.hypot(u[0], u[1]) or 1.0
    ux, uy = u[0] / Lu, u[1] / Lu
    # THE BEND IS LINEAR IN SIGMA, and an exponent on it was tried and REMOVED.
    # A fold near the trailing edge looked like the bend starting too early, so
    # a `--bend` knob went in at 2.0 (nearly a pure normal offset). The fold was
    # the TE STATION'S NORMAL instead -- see where P and N are built -- and once
    # that was right, 1.0 beat every exponent tried on BOTH the worst cell
    # (75.2 against 85.7 degrees) and the mean (9.43 against 9.91). A knob whose
    # best value is "off" is a knob that should not exist.
    w = sigma
    dx = (1.0 - w) * n[0] + w * ux
    dy = (1.0 - w) * n[1] + w * uy
    Ld = math.hypot(dx, dy) or 1.0
    # ONE reference length for the whole level, not each ray's own. Scaling by
    # |F - P| makes the te-side rays 10 and 8.8 long, so a level stands 0.24
    # further out at one station than its neighbour and the block between them
    # winds BACKWARDS -- the mesher refused it outright, which is the good case.
    r = sigma * Rref
    return [round(P[0] + r * dx / Ld, 12), round(P[1] + r * dy / Ld, 12)]


def ell(a, b, t):
    return [round(CENTRE[0] + a * math.cos(t), 12),
            round(CENTRE[1] + b * math.sin(t), 12)]


def ell_even(a, b, n, t0=0.5 * math.pi, t1=1.5 * math.pi, samples=12001):
    """`n`+1 parameters from t0 to t1, evenly spaced in ARC LENGTH."""
    ts = [t0 + (t1 - t0) * k / (samples - 1) for k in range(samples)]
    cum, acc = [0.0], 0.0
    for k in range(1, samples):
        p, q = ell(a, b, ts[k - 1]), ell(a, b, ts[k])
        acc += math.hypot(q[0] - p[0], q[1] - p[1])
        cum.append(acc)
    out, j = [t0], 0
    for k in range(1, n + 1):
        target = acc * k / n
        while j + 1 < samples and cum[j + 1] < target:
            j += 1
        out.append(ts[min(j, samples - 1)])
    out[-1] = t1
    return out


def build(folds=8, stages=2, notch=0.12, total_iv=40, wake=25, control=False,
          sigmas=None, ord_iv=None):
    far_t = seg_table(FAR)
    body_t = seg_table(BODY)
    S = stages
    Ks = [folds // (2 ** s) for s in range(S)]
    if Ks[-1] < 2:
        raise SystemExit("the outermost band needs K >= 2; lower --stages")
    n_levels = 2 + 2 * S
    arc = 192 // (4 * Ks[0])
    if arc * 4 * Ks[0] != 192:
        raise SystemExit("--folds must divide 192/4")
    red_iv = arc                      # forced: a = m
    if ord_iv is None:
        rest = total_iv - S * red_iv
        ord_iv = [max(2, rest - 2 * S)] + [2] * S
    # THE RADIAL BUDGET PER BAND, built once and used by BOTH modes, so the
    # control is radially identical to the reducing document and the only thing
    # that differs between them is the corner block. An earlier draft gave the
    # control only the ORDINARY entries and the mesher refused it outright: two
    # of its five bands had no count at all.
    band_iv, oi = [], 0
    for L in range(n_levels - 1):
        if (not control) and (L % 2 == 1):
            band_iv.append(red_iv)
        else:
            band_iv.append(ord_iv[oi] if oi < len(ord_iv) else 2)
            oi += 1
    if control:
        band_iv, oi = [], 0
        for L in range(n_levels - 1):
            if L % 2 == 1:
                band_iv.append(red_iv)
            else:
                band_iv.append(ord_iv[oi] if oi < len(ord_iv) else 2)
                oi += 1
    if sigmas is None:
        # Each interior level's fraction of the way along its stations' own
        # rays. Geometric, so the bands grow the way a boundary layer does.
        sigmas = [0.05, 0.10, 0.22, 0.40, 0.65, 0.85][:n_levels - 2]

    # Station counts per level: the body and the first band's inner level carry
    # 4K0; each reducing band halves; the ordinary band above it passes through.
    counts = [0] * n_levels
    counts[0] = 4 * Ks[0]                      # the body
    for s in range(S):
        counts[1 + 2 * s] = 4 * Ks[s]          # a reducing band's inner level
        counts[2 + 2 * s] = 2 * Ks[s]          # ... and its outer one
    counts[n_levels - 1] = 2 * Ks[-1]          # the far field
    if control:                       # no corner block anywhere: nothing halves
        counts = [4 * Ks[0]] * n_levels
    # THE FOLD SITS IN THE MIDDLE OF ITS UNIT, at 4j+2, and that is forced by
    # the aerofoil rather than chosen. At 4j+1 the first unit's fold is the
    # station NEXT TO THE TRAILING EDGE, where the body stations are 0.064 chord
    # apart while the notch pulls the fold ~0.1 out of line: the quad between
    # them is a twisted sliver and the mesher refuses the block outright. 4j+2
    # is also MIRROR-SYMMETRIC by construction, so the upper and lower surfaces
    # get folds at matching chordwise positions without a special case — which
    # an earlier 4j+1-upper / 4j+3-lower pair had to fake, and which still left
    # 11 inverted cells at negative y.
    fold_at = {}
    if not control:
        for s_i in range(S):
            fold_at[1 + 2 * s_i] = {4 * j + 2 for j in range(Ks[s_i])}

    corners, edges, blocks = [], [], []
    seen = set()

    def add(c):
        if c["id"] not in seen:
            seen.add(c["id"])
            corners.append(c)
        return c["id"]

    # ---- level 0, the body: te .. le .. te, 4K0 arcs ------------------------
    ids = []
    n0 = counts[0]
    row = []
    for k in range(n0 + 1):
        if k in (0, n0):
            cid = add({"id": "te", "kind": "on_geometry", "geom": BODY,
                       "seg": 0, "t": 0.0})
        elif k == n0 // 2:
            cid = add({"id": "le", "kind": "on_geometry", "geom": BODY,
                       "seg": 1, "t": 0.0})
        else:
            seg = 0 if k < n0 // 2 else 1
            loc = (k if seg == 0 else k - n0 // 2) / (n0 / 2.0)
            cid = add({"id": "b%d" % k, "kind": "on_geometry", "geom": BODY,
                       "seg": seg, "t": round(loc, 12)})
        row.append(cid)
    ids.append(row)

    # ---- every station's own RAY: body point, outward normal, far target ----
    # THE TRAILING-EDGE STATIONS TAKE THE SURFACE'S OWN NORMAL THERE, not a
    # vertical one. On a NACA 0012 the upper surface at the te has a normal
    # about (0.1, 0.995), so a station one arc in is pushed to x > 1 while a
    # vertical te ray stays at x = 1: the level's first arc then steps BACKWARDS
    # and the quad across it is twisted. The mesher refused the block, which is
    # the good case — it is the kind of fold a picture hides.
    P, N, F = [], [], []
    for k in range(n0 + 1):
        if k == 0:
            p, n = (1.0, 0.0), body_frame(body_t, 0, 1.0 / (n0 / 2.0))[1]
        elif k == n0:
            p, n = (1.0, 0.0), body_frame(body_t, 1,
                                          1.0 - 1.0 / (n0 / 2.0))[1]
        else:
            seg = 0 if k < n0 // 2 else 1
            loc = (k if seg == 0 else k - n0 // 2) / (n0 / 2.0)
            p, n = body_frame(body_t, seg, loc)
        P.append(p); N.append(n)
        fs, ft = station_at_fraction(far_t, [2, 3], k / float(n0))
        _, fcum, fpts = far_t[fs]
        import numpy as _np
        sd = ft * fcum[-1]
        i = int(_np.searchsorted(fcum, sd, side="right")) - 1
        i = max(0, min(i, len(fpts) - 2))
        g = (sd - fcum[i]) / max(fcum[i + 1] - fcum[i], 1e-15)
        q = fpts[i] + (fpts[i + 1] - fpts[i]) * g
        F.append((float(q[0]), float(q[1])))

    import statistics as _st
    Rref = _st.median([math.hypot(F[k][0] - P[k][0], F[k][1] - P[k][1])
                       for k in range(n0 + 1)])

    # ---- interior levels, on those rays -------------------------------------
    for L in range(1, n_levels - 1):
        step = n0 // counts[L]
        sig = sigmas[L - 1]
        below = sigmas[L - 2] if L >= 2 else 0.0
        row = []
        for m in range(counts[L] + 1):
            k = m * step
            # THE NOTCH IS A FRACTION OF THE BAND BELOW, NOT OF THE RAY. A first
            # draft scaled sigma itself, so the dip grew with the ray's own
            # length -- which varies tenfold round an aerofoil, so at the nose it
            # pulled the fold 0.6 chords in, deeper than the band it sat on, and
            # folded the corner blocks there. Measured: 12 inverted cells, all in
            # the first reducing band's corner blocks near the nose.
            sg = sig - notch * (sig - below) if m in fold_at.get(L, ()) else sig
            row.append(add({"id": "L%d_%d" % (L, m), "kind": "free",
                            "xy": ray_point(P[k], N[k], F[k], sg, Rref)}))
        ids.append(row)

    # ---- the far field ------------------------------------------------------
    for cid, seg, t in (("wk", 0, 0.0), ("fu", 1, 0.0), ("f1", 2, 0.0),
                        ("f2", 3, 0.0), ("f3", 4, 0.0), ("fl", 5, 0.0)):
        add({"id": cid, "kind": "on_geometry", "geom": FAR, "seg": seg, "t": t})
    nF = counts[-1]
    row = []
    for k in range(nF + 1):
        if k == 0:
            row.append("f1")
        elif k == nF:
            row.append("f3")
        elif k == nF // 2:
            row.append("f2")
        else:
            sg, t = station_at_fraction(far_t, [2, 3], k / float(nF))
            row.append(add({"id": "x%d" % k, "kind": "on_geometry",
                            "geom": FAR, "seg": sg, "t": round(t, 12)}))
    ids.append(row)

    def edge(eid, a, b, kind, count=None, curve=None, bind=None, spacing=None):
        e = {"id": eid, "corners": [a, b], "kind": kind}
        if count:
            e["count"] = count
        if curve:
            e["curve"] = dict(curve)
        if bind is not None:
            e["binding"] = {"geom": bind[0], "seg": bind[1]}
        if spacing:
            e["spacing"] = spacing
        edges.append(e)
        return eid

    # ---- circumferential edges, level by level ------------------------------
    for L in range(n_levels):
        for k in range(counts[L]):
            eid = "c%d_%d" % (L, k)
            if L == 0:
                edge(eid, ids[0][k], ids[0][k + 1], "wall", arc + 1,
                     bind=(BODY, 0 if k < counts[0] // 2 else 1))
            elif L == n_levels - 1:
                edge(eid, ids[L][k], ids[L][k + 1], "wall",
                     bind=(FAR, 2 if k < counts[L] // 2 else 3))
            else:
                # NO declared curve: the stations are on their own rays and
                # adjacent ones are close, so the chord between them IS the
                # level. An ellipse here is what put the radials along the
                # aerofoil -- see ray_point().
                edge(eid, ids[L][k], ids[L][k + 1], "interface")

    # ---- bands ---------------------------------------------------------------
    red_in = {1 + 2 * s: s for s in range(S)} if not control else {}
    band = 0
    for L in range(n_levels - 1):
        if L in red_in:
            s = red_in[L]
            for j in range(Ks[s]):
                # O1 | CORNER (fold at 4j+2) | O2, with the apex at 2j+1.
                rS = "rS%d_%d" % (L, j)
                if j == 0:
                    edge(rS, ids[L][0], ids[L + 1][0], "interface")
                rM1 = edge("rM%d_%d_a" % (L, j), ids[L][4 * j + 1],
                           ids[L + 1][2 * j + 1], "interface")
                rM2 = edge("rM%d_%d_b" % (L, j), ids[L][4 * j + 3],
                           ids[L + 1][2 * j + 1], "interface")
                rE = edge("rS%d_%d" % (L, j + 1), ids[L][4 * j + 4],
                          ids[L + 1][2 * j + 2], "interface")
                blocks.append({"id": "Q%d_%d_0" % (L, j),
                               "edges": [rS, "c%d_%d" % (L + 1, 2 * j), rM1,
                                         "c%d_%d" % (L, 4 * j)]})
                blocks.append({"id": "C%d_%d" % (L, j),
                               "edges": [rM1, rM2,
                                         "c%d_%d" % (L, 4 * j + 2),
                                         "c%d_%d" % (L, 4 * j + 1)]})
                blocks.append({"id": "Q%d_%d_1" % (L, j),
                               "edges": [rM2, "c%d_%d" % (L + 1, 2 * j + 1),
                                         rE, "c%d_%d" % (L, 4 * j + 3)]})
        else:
            seed = band_iv[L] + 1
            for k in range(counts[L] + 1):
                edge("r%d_%d" % (L, k), ids[L][k], ids[L + 1][k], "interface",
                     seed if k == 0 else None,
                     spacing={"wall_ends": "start"} if L == 0 else None)
            for k in range(counts[L]):
                blocks.append({"id": "B%d_%d" % (L, k),
                               "edges": ["r%d_%d" % (L, k),
                                         "c%d_%d" % (L + 1, k),
                                         "r%d_%d" % (L, k + 1),
                                         "c%d_%d" % (L, k)]})
            band += 1

    # ---- the wake column ----------------------------------------------------
    edge("wake", "te", "wk", "cut", wake, spacing={"ds_start": 0.005})
    out_up, out_lo = ["wk"], ["wk"]
    for L in range(1, n_levels - 1):
        y = abs(float(next(c for c in corners
                           if c["id"] == ids[L][0])["xy"][1]))
        t = min(0.95, max(0.02, y / 10.0))
        out_up.append(add({"id": "ou%d" % L, "kind": "on_geometry",
                           "geom": FAR, "seg": 0, "t": round(t, 12)}))
        out_lo.append(add({"id": "ol%d" % L, "kind": "on_geometry",
                           "geom": FAR, "seg": 5, "t": round(1.0 - t, 12)}))
        edge("wu%d" % L, ids[L][0], out_up[-1], "interface",
             spacing={"ds_start": 0.005})
        edge("wl%d" % L, ids[L][counts[L]], out_lo[-1], "interface",
             spacing={"ds_start": 0.005})
    out_up.append("fu")
    out_lo.append("fl")
    for i in range(len(out_up) - 1):
        edge("ou_e%d" % i, out_up[i], out_up[i + 1], "wall", bind=(FAR, 0),
             spacing={"wall_ends": "start"} if i == 0 else None)
        edge("ol_e%d" % i, out_lo[i], out_lo[i + 1], "wall", bind=(FAR, 5),
             spacing={"wall_ends": "start"} if i == 0 else None)
    edge("e_ff_up", "fu", "f1", "wall", bind=(FAR, 1))
    edge("e_ff_lo", "f3", "fl", "wall", bind=(FAR, 4))

    def wake_side(L):
        """(upper radial, lower radial) bounding the wake blocks of band L."""
        if L in red_in:
            return "rS%d_0" % L, "rS%d_%d" % (L, Ks[red_in[L]])
        return "r%d_0" % L, "r%d_%d" % (L, counts[L])

    for L in range(n_levels - 1):
        up, lo = wake_side(L)
        low_up = "wake" if L == 0 else "wu%d" % L
        low_lo = "wake" if L == 0 else "wl%d" % L
        hi_up = "wu%d" % (L + 1) if L + 1 < n_levels - 1 else "e_ff_up"
        hi_lo = "wl%d" % (L + 1) if L + 1 < n_levels - 1 else "e_ff_lo"
        blocks.append({"id": "WU%d" % L,
                       "edges": ["ou_e%d" % L, hi_up, up, low_up]})
        blocks.append({"id": "WL%d" % L,
                       "edges": [lo, hi_lo, "ol_e%d" % L, low_lo]})

    return {"format_version": 1, "corners": corners, "edges": edges,
            "blocks": blocks}, counts, arc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=8)
    ap.add_argument("--stages", type=int, default=2)
    ap.add_argument("--notch", type=float, default=0.12)
    ap.add_argument("--total-iv", type=int, default=40)
    ap.add_argument("--sigmas", type=float, nargs="*", default=None,
                    help="each interior level's fraction along the rays")
    ap.add_argument("--ord-iv", type=int, nargs="*", default=None)
    ap.add_argument("--control", action="store_true",
                    help="the same levels with NO corner block, so nothing halves")
    ap.add_argument("--smooth", type=int, default=0)
    ap.add_argument("--stem", default="cgrid_stack")
    a = ap.parse_args()
    doc, counts, arc = build(folds=a.folds, stages=a.stages, notch=a.notch,
                             total_iv=a.total_iv, control=a.control,
                             sigmas=a.sigmas, ord_iv=a.ord_iv)
    header = ("// A STACK OF COUNT-REDUCING RINGS ON THE SHIPPED AEROFOIL "
              "(#192 follow-up)\n"
              "// — GENERATED by make_cgrid_stack.py %s\n"
              "// beside this file. Do not hand-edit; re-run that command.\n"
              "//\n"
              "// %d blocks. Stations per level: %s. Body %d intervals, far "
              "field %d.\n"
              % (" ".join(sys.argv[1:]), len(doc["blocks"]),
                 " -> ".join(str(c) for c in counts), counts[0] * arc,
                 counts[-1] * arc))
    with open(os.path.join(HERE, a.stem + ".json"), "w", encoding="utf-8") as f:
        f.write(header + json.dumps(doc, indent=2) + "\n")
    cfg = ("# GENERATED by make_cgrid_stack.py " + " ".join(sys.argv[1:])
           + " — #192 follow-up.\n"
             "MESH_MODE 1\n"
             "MESH_TOPOLOGY_FILE docs/research/gridpro-blocking-method/%s.json\n"
             "GEOM_FILE examples/geometries/%s\n"
             "DOMAIN_FILE examples/geometries/%s nobl\n"
             "BL_INITIAL_THICKNESS 0.001\n"
             "MB_SPLIT_QUADS 0\n"
             "MB_SMOOTH_ITERS %d\n"
             "BC_GEOM wall\n"
             "EXPORT_VTK 1\n"
             "EXPORT_STARCD 0\n" % (a.stem, BODY, FAR, a.smooth))
    with open(os.path.join(HERE, a.stem + ".dat"), "w", encoding="utf-8") as f:
        f.write(cfg)
    print("wrote %s.json / %s.dat: %d blocks, stations %s, body %d -> far %d"
          % (a.stem, a.stem, len(doc["blocks"]),
             "->".join(str(c) for c in counts), counts[0] * arc,
             counts[-1] * arc))


if __name__ == "__main__":
    main()
