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
# --far-geom swaps the far field for another FILE with the same points and
# different boundary conditions. It exists for one experiment, #194's candidate
# (2): the aerofoil's shipped far field carries `outlet` on two of its six
# segments and the circle documents that PASS gate 2 are `farfield` throughout,
# and nothing had put an outlet beside a corner block. A topology names a
# geometry by BASENAME (findGeometry in src/MultiBlock.cpp), so the swap is a
# basename in the document and a path in the config, and nothing else moves.
FAR_DIR = "examples/geometries"
CENTRE = (1.0, 0.0)                      # the chain case's own seam centre


def seg_table(name, where="examples/geometries"):
    import numpy as np
    pts = np.loadtxt(os.path.join(ROOT, where, name))
    rows = [l.split() for l in
            open(os.path.join(ROOT, where, name + ".meta"),
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
          sigmas=None, ord_iv=None, layers=None, fold_units=None):
    far_t = seg_table(FAR, FAR_DIR)
    body_t = seg_table(BODY)
    S = stages
    Ks = [folds // (2 ** s) for s in range(S)]
    if Ks[-1] < 2:
        raise SystemExit("the outermost band needs K >= 2; lower --stages")
    arc = 192 // (4 * Ks[0])
    if arc * 4 * Ks[0] != 192:
        raise SystemExit("--folds must divide 192/4")
    red_iv = arc                      # forced: a = m

    # THE BAND PLAN IS EXPLICIT, not derived from a level index's parity. It was
    # parity until --layers: an ORDINARY band may now be cut into several RADIAL
    # layers of blocks, which is how GridPro's own aerofoil figure wraps a body
    # (16j) and which a parity rule cannot express, because it inserts levels.
    #   ('ord', n)  an ordinary band as n layers of blocks, count unchanged
    #   ('red', s)  a reducing band, 4Ks stations in and 2Ks out
    if layers is None:
        layers = [1] * (S + 1)
    if len(layers) < S + 1:
        layers = list(layers) + [1] * (S + 1 - len(layers))
    plan = [("ord", layers[0])]
    for s_i in range(S):
        plan.append(("red", s_i))
        plan.append(("ord", layers[s_i + 1]))

    # A UNIT MAY DECLINE ITS FOLD. `fold_units` names the units of each
    # reducing band that carry a corner block; the rest map their four inner
    # stations to FOUR outer ones as ordinary blocks instead of to two. That
    # makes the outer station count a MIX, so a level can no longer derive its
    # stations from a uniform stride and each one carries `src`: the level-0
    # station whose ray it sits on. This exists for one experiment — #194's
    # discriminator, which needs corner blocks over the NOSE and none near the
    # wake cut — and the all-folded default is behaviour-preserving.
    lv_count, lv_src = [4 * Ks[0]], [list(range(4 * Ks[0] + 1))]
    bands, fold_of = [], {}
    for kind, payload in plan:
        if kind == "ord":
            for _ in range(payload):
                bands.append(("ord", len(lv_count) - 1, None))
                lv_count.append(lv_count[-1])
                lv_src.append(list(lv_src[-1]))
        else:
            L = len(lv_count) - 1
            # K COMES FROM THE STATIONS THAT ARE ACTUALLY THERE, not from
            # folds // 2**s. That derivation assumes every unit folds and so
            # every band halves; with --fold-units it does not, and the next
            # band's unit walk then leaves arcs belonging to one block only —
            # which the mesher refuses by name, as `c3_16` an interface with one
            # side.
            if lv_count[-1] % 4:
                raise SystemExit("level %d has %d stations, not a multiple of 4"
                                 % (L, lv_count[-1]))
            K = lv_count[-1] // 4
            want = fold_units if fold_units is not None else list(range(K))
            folded = sorted(j for j in want if 0 <= j < K)
            src_in = lv_src[L]
            src_out, plan_j = [src_in[0]], []
            for j in range(K):
                i0 = 4 * j
                if j in folded:
                    plan_j.append(("red", j))
                    src_out.append(src_in[i0 + 2])
                    src_out.append(src_in[i0 + 4])
                else:
                    plan_j.append(("flat", j))
                    for t in (1, 2, 3, 4):
                        src_out.append(src_in[i0 + t])
            bands.append(("red", L, (payload, plan_j)))
            fold_of[L] = {4 * j + 2 for j in folded}
            lv_count.append(len(src_out) - 1)
            lv_src.append(src_out)
    n_levels = len(lv_count)

    if ord_iv is None:
        rest = total_iv - S * red_iv
        ord_iv = [max(2, rest - 2 * S)] + [2] * S
    # Per BAND, so the control is radially identical to the reducing document.
    # An ordinary band split into n layers shares its budget between them.
    # Share each ORDINARY band's budget across its own layers of blocks.
    i, oi = 0, 0
    band_iv = [0] * len(bands)
    for kind, payload in plan:
        if kind == "ord":
            want = ord_iv[oi] if oi < len(ord_iv) else 2
            oi += 1
            per = max(2, want // payload)
            for k in range(payload):
                band_iv[i] = per
                i += 1
        else:
            band_iv[i] = red_iv
            i += 1

    # THE FOLD SITS IN THE MIDDLE OF ITS UNIT, at 4j+2, and that is forced by
    # the aerofoil rather than chosen. At 4j+1 the first unit's fold is the
    # station NEXT TO THE TRAILING EDGE, where the body stations are 0.064 chord
    # apart while the notch pulls the fold ~0.1 out of line: the quad between
    # them is a twisted sliver and the mesher refuses the block outright. 4j+2
    # is also MIRROR-SYMMETRIC by construction, so the upper and lower surfaces
    # get folds at matching chordwise positions without a special case.
    fold_at = {} if control else dict(fold_of)
    if control:
        lv_count = [4 * Ks[0]] * n_levels
        lv_src = [list(range(4 * Ks[0] + 1))] * n_levels

    # SIGMA IS GIVEN PER BAND OF THE PLAN, NOT PER LEVEL, and that distinction
    # is a bug this file shipped for one run. --layers is meant to SUBDIVIDE an
    # ordinary band; spreading one sigma per level over the whole range instead
    # pushed the body band's outer boundary from 0.05 to 0.16 -- three times
    # thicker -- and moved every level above it. The plan's own boundaries are
    # fixed first and each ordinary band's layers are then packed INSIDE its own
    # span, so --layers cannot move anything.
    n_plan = len(plan)
    if sigmas is None:
        sigmas = [0.05 * (0.40 / 0.05) ** (k / max(1, n_plan - 2))
                  for k in range(n_plan - 1)]
    if len(sigmas) != n_plan - 1:
        raise SystemExit("--sigmas needs %d values for this plan (one per "
                         "interior band boundary), got %d"
                         % (n_plan - 1, len(sigmas)))
    lv_sigma, bi0 = [0.0], 0.0
    for pi, (kind, payload) in enumerate(plan):
        bi1 = sigmas[pi] if pi < len(sigmas) else 1.0
        if kind == "ord":
            for k in range(1, payload + 1):
                f = k / float(payload)
                lv_sigma.append(bi0 * (bi1 / bi0) ** f if bi0 > 0.0
                                else bi1 * f)
        else:
            lv_sigma.append(bi1)
        bi0 = bi1
    counts = lv_count
    assert len(lv_sigma) == n_levels, (len(lv_sigma), n_levels)

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
        sig = lv_sigma[L]
        below = lv_sigma[L - 1]
        row = []
        for m in range(counts[L] + 1):
            k = lv_src[L][m]
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
    red_in = {L: payload for kind, L, payload in bands if kind == "red"} \
        if not control else {}
    for bi, (kind, L, payload) in enumerate(bands):
        if kind == "red" and not control:
            _, plan_j = payload
            o = 0
            for kind_j, j in plan_j:
                i0 = 4 * j
                if kind_j == "red":
                    rS = "rS%d_%d" % (L, o)
                    if o == 0:
                        edge(rS, ids[L][i0], ids[L + 1][0], "interface")
                    rM1 = edge("rM%d_%d_a" % (L, j), ids[L][i0 + 1],
                               ids[L + 1][o + 1], "interface")
                    rM2 = edge("rM%d_%d_b" % (L, j), ids[L][i0 + 3],
                               ids[L + 1][o + 1], "interface")
                    rE = edge("rS%d_%d" % (L, o + 2), ids[L][i0 + 4],
                              ids[L + 1][o + 2], "interface")
                    blocks.append({"id": "Q%d_%d_0" % (L, j),
                                   "edges": [rS, "c%d_%d" % (L + 1, o), rM1,
                                             "c%d_%d" % (L, i0)]})
                    blocks.append({"id": "C%d_%d" % (L, j),
                                   "edges": [rM1, rM2, "c%d_%d" % (L, i0 + 2),
                                             "c%d_%d" % (L, i0 + 1)]})
                    blocks.append({"id": "Q%d_%d_1" % (L, j),
                                   "edges": [rM2, "c%d_%d" % (L + 1, o + 1),
                                             rE, "c%d_%d" % (L, i0 + 3)]})
                    del rE
                    o += 2
                else:
                    # A unit that declined its fold: four ordinary blocks.
                    if o == 0:
                        edge("rS%d_0" % L, ids[L][i0], ids[L + 1][0],
                             "interface")
                    for t in range(4):
                        edge("rS%d_%d" % (L, o + t + 1), ids[L][i0 + t + 1],
                             ids[L + 1][o + t + 1], "interface")
                        blocks.append({"id": "F%d_%d_%d" % (L, j, t),
                                       "edges": ["rS%d_%d" % (L, o + t),
                                                 "c%d_%d" % (L + 1, o + t),
                                                 "rS%d_%d" % (L, o + t + 1),
                                                 "c%d_%d" % (L, i0 + t)]})
                    o += 4
        else:
            seed = band_iv[bi] + 1
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

    # ---- the wake column ----------------------------------------------------
    edge("wake", "te", "wk", "cut", wake, spacing={"ds_start": 0.005})
    out_up, out_lo = ["wk"], ["wk"]
    for L in range(1, n_levels - 1):
        y = abs(float(next(c for c in corners
                           if c["id"] == ids[L][0])["xy"][1]))
        # NO LOWER FLOOR. The levels' sigma is strictly increasing, so the
        # te-side station's y is too, and t = y/10 is therefore strictly
        # increasing on its own. An arbitrary 0.02 floor flattened the inner
        # layers onto one another and the mesher refused `ou_e1` for having no
        # length -- at six body layers, which is the first depth that reaches it.
        t = min(0.95, y / 10.0)
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
            return "rS%d_0" % L, "rS%d_%d" % (L, counts[L + 1])
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
    ap.add_argument("--layers", type=int, nargs="*", default=None,
                    help="radial layers of BLOCKS per ordinary band, innermost "
                         "first; 4 on the body band makes its blocks square-ish "
                         "the way GridPro's own aerofoil wrap is (16j)")
    ap.add_argument("--far-geom", default=None,
                    help="a path to another far-field geometry with the same "
                         "points; see FAR_DIR. #194 candidate (2)")
    ap.add_argument("--fold-units", type=int, nargs="*", default=None,
                    help="which units of each reducing band carry a corner "
                         "block; the rest map four stations to four. Default: "
                         "all. #194's discriminator needs the nose ones only")
    ap.add_argument("--control", action="store_true",
                    help="the same levels with NO corner block, so nothing halves")
    ap.add_argument("--smooth", type=int, default=0)
    ap.add_argument("--stem", default="cgrid_stack")
    a = ap.parse_args()
    if a.far_geom:
        global FAR, FAR_DIR
        FAR_DIR, FAR = os.path.split(a.far_geom)
    doc, counts, arc = build(folds=a.folds, stages=a.stages, notch=a.notch,
                             total_iv=a.total_iv, control=a.control,
                             sigmas=a.sigmas, ord_iv=a.ord_iv,
                             layers=a.layers, fold_units=a.fold_units)
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
             "DOMAIN_FILE %s/%s nobl\n"
             "BL_INITIAL_THICKNESS 0.001\n"
             "MB_SPLIT_QUADS 0\n"
             "MB_SMOOTH_ITERS %d\n"
             "BC_GEOM wall\n"
             "EXPORT_VTK 1\n"
             "EXPORT_STARCD 0\n" % (a.stem, BODY, FAR_DIR, FAR, a.smooth))
    with open(os.path.join(HERE, a.stem + ".dat"), "w", encoding="utf-8") as f:
        f.write(cfg)
    print("wrote %s.json / %s.dat: %d blocks, stations %s, body %d -> far %d"
          % (a.stem, a.stem, len(doc["blocks"]),
             "->".join(str(c) for c in counts), counts[0] * arc,
             counts[-1] * arc))


if __name__ == "__main__":
    main()
