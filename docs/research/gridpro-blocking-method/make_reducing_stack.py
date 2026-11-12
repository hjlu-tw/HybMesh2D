#!/usr/bin/env python3
"""A STACK of count-reducing rings, so the count comes down ALL THE WAY OUT.

A RESEARCH HARNESS beside ``docs/research/nesting-blocks-at-a-complicated-leading-edge.md``
section 16. Nothing shipped reads it; nothing in ``config/``, ``examples/``,
``src/`` or ``include/`` is written or changed by it.

WHY A THIRD GENERATOR, in the shape ``make_rings.py`` beside it already uses for
the same reason. ``make_reducing_annulus.py`` writes ONE reducing ring: the
count falls once, near the body, and everything outside it is a single ordinary
band running to the far field. On the shipped circle that is 8 blocks spanning
r = 1.8 out to r = 10 — the block structure stops changing a chord and a half
off the body and the figure shows it. **That is one step, not a staircase.**
This file stacks S reducing rings at increasing radius with an ordinary band
between each pair, so N(r) and the node count come down in stages from the wall
to the far field.

THE ARITHMETIC IS WHY THE STACK CLOSES. With two ordinary blocks per unit a
reducing ring takes ``K(2a + 2m)`` inner intervals to ``2Km`` outer ones, and
``4K`` inner stations to ``2K`` outer ones. Setting the ring's radial depth
``a`` equal to its arc count ``m`` makes both of those exactly HALVE, and the
next ring up then needs ``K/2`` folds to meet them. So a stack is K, K/2, K/4 …
and the count is N, N/2, N/4 … — and ``a = m`` is not a choice: the corner
block forces its radials equal to the two inner arcs it carries, so the depth a
halving ring must have is the one it gets.

    python3 docs/research/gridpro-blocking-method/make_reducing_stack.py
    ./run.sh -conf docs/research/gridpro-blocking-method/reducing_stack.dat
    python3 docs/research/gridpro-blocking-method/measure_block_partition.py \
        /tmp/rs.vtk --centre 0 0
"""

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

BODY_GEOM, R_BODY = "circle_body.dat", 0.5
FAR_GEOM, R_FAR = "circle_farfield.dat", 10.0


def polar(r, deg):
    t = math.radians(deg)
    return [round(r * math.cos(t), 12), round(r * math.sin(t), 12)]


def on_geometry(cid, geom, deg):
    phi = deg % 360.0
    seg = int(phi // 90.0) % 4
    return {"id": cid, "kind": "on_geometry", "geom": geom, "seg": seg,
            "t": round((phi - 90.0 * seg) / 90.0, 12)}


def quarter_of(deg):
    return int((deg % 360.0) // 90.0) % 4


def build(folds=8, stages=3, arc=6, notch=0.18, radii=None, smooth=20,
          ord_depth=None):
    """`folds` is K at the INNERMOST reducing ring; it halves at each stage."""
    S = stages
    Ks = [folds // (2 ** s) for s in range(S)]
    if Ks[-1] < 2:
        raise SystemExit("the outermost ring needs K >= 2, or its far-field "
                         "arcs are half turns; lower --stages or raise --folds")
    # Levels, from the body outward: body, then per stage (ring in, ring out),
    # then the far field. An ordinary band sits between every consecutive pair
    # that is not a reducing ring's own two levels.
    n_levels = 2 + 2 * S
    if radii is None:
        radii = [R_BODY, 0.9, 1.4, 2.3, 3.3, 5.3, 7.0, R_FAR][:n_levels]
    if len(radii) != n_levels:
        raise SystemExit("--radii needs %d values for %d stages" % (n_levels, S))
    if ord_depth is None:                       # one per ORDINARY band
        ord_depth = [25, 9, 7, 5][:S + 1]

    # Station angles per level, and why they line up without being made to.
    # A reducing ring's inner stations sit every unit/4 and its outer every
    # unit/2; the next ring up has twice the unit, so ITS inner step is the one
    # below's outer step. Each ring is therefore offset half a unit from the
    # one below and everything coincides by construction.
    units = [360.0 / k for k in Ks]
    offs, acc = [], 0.0
    for s_i in range(S):
        offs.append(acc)
        acc += 0.5 * units[s_i]
    spec = [(offs[0] - 0.25 * units[0], 0.25 * units[0], 4 * Ks[0])] * 2
    for s_i in range(S):
        spec[1 + 2 * s_i] = (offs[s_i] - 0.25 * units[s_i],
                             0.25 * units[s_i], 4 * Ks[s_i])
        spec.append((offs[s_i], 0.5 * units[s_i], 2 * Ks[s_i]))
        if s_i + 1 < S:
            spec.append((offs[s_i + 1] - 0.25 * units[s_i + 1],
                         0.25 * units[s_i + 1], 4 * Ks[s_i + 1]))
    spec = spec[:n_levels - 1] + [spec[n_levels - 2]]
    counts = [c for _, _, c in spec]
    # Rotate the whole stack so the FAR-FIELD stations land on 0/90/180/270,
    # which is what keeps every bound arc inside one quarter segment of the two
    # shipped circles. Every other level's step divides that one's, so the
    # body's arcs stay inside their quarters too -- asserted below.
    rot = -spec[-1][0]
    angles = [[rot + st + k * dt for k in range(ct)] for st, dt, ct in spec]
    for L in (0, n_levels - 1):
        for k in range(counts[L]):
            a0 = angles[L][k] % 360.0
            a1 = (angles[L][k] + 360.0 / counts[L]) % 360.0
            if quarter_of(a0) != quarter_of(a1 - 1e-9):
                raise SystemExit("a bound arc at level %d crosses a quarter "
                                 "join: %.4f -> %.4f" % (L, a0, a1))

    # Which levels are a reducing ring's INNER level, and where its folds are.
    red_in = {1 + 2 * s: s for s in range(S)}
    fold_at = {}
    for L, s in red_in.items():
        fold_at[L] = {4 * j + 1 for j in range(Ks[s])}

    corners, edges, blocks = [], [], []
    ids = []
    for L in range(n_levels):
        row = []
        for k in range(counts[L]):
            cid = "n%d_%d" % (L, k)
            if L == 0:
                corners.append(on_geometry(cid, BODY_GEOM, angles[L][k]))
            elif L == n_levels - 1:
                corners.append(on_geometry(cid, FAR_GEOM, angles[L][k]))
            else:
                r = radii[L] * (1.0 - notch) if k in fold_at.get(L, ()) \
                    else radii[L]
                corners.append({"id": cid, "kind": "free",
                                "xy": polar(r, angles[L][k])})
            row.append(cid)
        ids.append(row)

    def circ(L, k, count=None):
        """The circumferential edge from station k to k+1 at level L."""
        eid = "c%d_%d" % (L, k)
        nxt = (k + 1) % counts[L]
        e = {"id": eid, "corners": [ids[L][k], ids[L][nxt]],
             "kind": "wall" if L in (0, n_levels - 1) else "interface"}
        if count:
            e["count"] = count
        if L == 0:
            e["binding"] = {"geom": BODY_GEOM, "seg": quarter_of(
                0.5 * (angles[L][k] + angles[L][k] + 360.0 / counts[L]))}
        elif L == n_levels - 1:
            e["binding"] = {"geom": FAR_GEOM, "seg": quarter_of(
                0.5 * (angles[L][k] + angles[L][k] + 360.0 / counts[L]))}
        else:
            # A notched station breaks the circle, so the two arcs that reach it
            # are declared as the chords they are.
            if k not in fold_at.get(L, ()) and nxt not in fold_at.get(L, ()):
                e["curve"] = {"kind": "ellipse", "centre": [0.0, 0.0],
                              "a": radii[L], "b": radii[L], "sweep": "ccw"}
        edges.append(e)
        return eid

    for L in range(n_levels):
        for k in range(counts[L]):
            circ(L, k, (arc + 1) if L == 0 else None)

    def radial(eid, L, k, L2, k2, count=None, wall=False):
        e = {"id": eid, "corners": [ids[L][k], ids[L2][k2]], "kind": "interface"}
        if count:
            e["count"] = count
        if wall:
            e["spacing"] = {"wall_ends": "start"}
        edges.append(e)
        return eid

    band = 0
    for L in range(n_levels - 1):
        if L in red_in:                                   # a REDUCING band
            s = red_in[L]
            for j in range(Ks[s]):
                i0, i1, i2, i3 = 4 * j, 4 * j + 1, 4 * j + 2, 4 * j + 3
                o0, o1 = 2 * j, 2 * j + 1
                rA = radial("rA%d_%d" % (L, j), L, i0, L + 1, o0)
                rB = radial("rB%d_%d" % (L, j), L, i2, L + 1, o0)
                rD = radial("rD%d_%d" % (L, j), L, i3, L + 1, o1)
                nxt = "rA%d_%d" % (L, (j + 1) % Ks[s])
                blocks.append({"id": "Q%d_%d_0" % (L, j),
                               "edges": [rB, "c%d_%d" % (L + 1, o0), rD,
                                         "c%d_%d" % (L, i2)]})
                blocks.append({"id": "Q%d_%d_1" % (L, j),
                               "edges": [rD, "c%d_%d" % (L + 1, o1), nxt,
                                         "c%d_%d" % (L, i3)]})
                # THE CORNER BLOCK: both radials end at the apex o0.
                blocks.append({"id": "C%d_%d" % (L, j),
                               "edges": [rA, rB, "c%d_%d" % (L, i1),
                                         "c%d_%d" % (L, i0)]})
        else:                                              # an ORDINARY band
            seed = ord_depth[band] if band < len(ord_depth) else None
            for k in range(counts[L]):
                radial("r%d_%d" % (L, k), L, k, L + 1, k,
                       seed if k == 0 else None, wall=(L == 0))
            for k in range(counts[L]):
                nxt = (k + 1) % counts[L]
                blocks.append({"id": "B%d_%d" % (L, k),
                               "edges": ["r%d_%d" % (L, k),
                                         "c%d_%d" % (L + 1, k),
                                         "r%d_%d" % (L, nxt),
                                         "c%d_%d" % (L, k)]})
            band += 1

    doc = {"format_version": 1, "corners": corners, "edges": edges,
           "blocks": blocks}
    n_in = counts[0] * arc
    n_out = counts[-1] * arc
    header = (
        "// A STACK OF COUNT-REDUCING RINGS (issue #192, follow-up) — GENERATED\n"
        "// by make_reducing_stack.py %s\n"
        "// beside this file. Do not hand-edit; re-run that command.\n"
        "//\n"
        "// %d stages, folds %s, %d blocks. The body carries %d intervals and\n"
        "// the far field %d, halving at each stage.\n"
        % (" ".join(sys.argv[1:]), S, "/".join(str(k) for k in Ks),
           len(blocks), n_in, n_out))
    cfg = ("# GENERATED by make_reducing_stack.py " + " ".join(sys.argv[1:])
           + " — #192 follow-up.\n"
             "MESH_MODE 1\n"
             "GEOM_FILE examples/geometries/%s\n"
             "DOMAIN_FILE examples/geometries/%s nobl\n"
             "BL_INITIAL_THICKNESS 0.001\n"
             "MESH_TOPOLOGY_FILE docs/research/gridpro-blocking-method/STEM.json\n"
             "MB_SPLIT_QUADS 0\n"
             "MB_SMOOTH_ITERS %d\n"
             "EXPORT_VTK 1\n"
             "EXPORT_STARCD 0\n" % (BODY_GEOM, FAR_GEOM, smooth))
    return header, doc, cfg, n_in, n_out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=8,
                    help="K at the innermost reducing ring; halves per stage")
    ap.add_argument("--stages", type=int, default=3)
    ap.add_argument("--arc", type=int, default=6,
                    help="intervals on each body arc; also every ring's depth")
    ap.add_argument("--notch", type=float, default=0.18)
    ap.add_argument("--radii", type=float, nargs="*", default=None)
    ap.add_argument("--smooth", type=int, default=20)
    ap.add_argument("--stem", default="reducing_stack")
    a = ap.parse_args()
    header, doc, cfg, n_in, n_out = build(
        folds=a.folds, stages=a.stages, arc=a.arc, notch=a.notch,
        radii=a.radii, smooth=a.smooth)
    with open(os.path.join(HERE, a.stem + ".json"), "w", encoding="utf-8") as f:
        f.write(header + json.dumps(doc, indent=2) + "\n")
    with open(os.path.join(HERE, a.stem + ".dat"), "w", encoding="utf-8") as f:
        f.write(cfg.replace("STEM", a.stem))
    print("wrote %s.json / %s.dat: %d blocks, body %d intervals -> far %d"
          % (a.stem, a.stem, len(doc["blocks"]), n_in, n_out))


if __name__ == "__main__":
    main()
