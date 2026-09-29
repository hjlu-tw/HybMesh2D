#!/usr/bin/env python3
"""A closed outline with segment ids OF OUR CHOOSING, and the CAD edit that breaks
a binding to one.

Two gates build the same fixture and must not be able to build it differently:
`test_topology_ogrid.py` (which this was extracted from, unchanged) needs outlines
whose segment ids are deliberately not positions, and `test_topology_repair.py`
(#138) needs the same outlines PLUS the edit that makes a stored binding stop
resolving. A second copy of the writer is a second `.meta` format, and the format is
what the whole binding rule rests on.

This module holds no checks and prints nothing, so importing it has no side effects.
Needs no Qt, no build tree and no network.
"""
import math
import os


def write_outline(stem, r, seg_ids, per_seg, bc, cw=False, square=False):
    """A closed outline as a ``.dat`` plus its ``.meta`` sidecar.

    ``seg_ids`` are written into BOTH the sidecar's ``NSEGMENTS`` rows and its
    per-point ``POINTS`` column, which is where the PreProcessor puts a
    ``SegmentModel.id`` and where the mesher reads one. They are deliberately free to
    be anything, because a binding that is an id must not care what they are.

    ``square=True`` walks the perimeter of a square rather than a circle, so a
    segment's arc length is EXACT under resampling — which is what lets
    ``test_topology_ogrid.py`` check 10 compare byte for byte rather than within a
    tolerance.
    """
    n_seg = len(seg_ids)
    pts, ids = [], []
    for i in range(n_seg):
        for j in range(per_seg):
            f = (i * per_seg + j) / float(n_seg * per_seg)
            if square:
                u = ((4.0 - f * 4.0) if cw else (f * 4.0)) % 4.0
                side, t = int(u), u - int(u)
                x, y = [(r, -r + 2 * r * t), (r - 2 * r * t, r),
                        (-r, r - 2 * r * t), (-r + 2 * r * t, -r)][side]
            else:
                a = 2.0 * math.pi * (-f if cw else f)
                x, y = r * math.cos(a), r * math.sin(a)
            pts.append((x, y))
            ids.append(seg_ids[i])
    pts.append(pts[0])           # the trailing duplicate a closed loop carries
    ids.append(seg_ids[0])
    with open(stem + ".dat", "w", encoding="utf-8") as f:
        for x, y in pts:
            f.write(f"{x:.12f} {y:.12f}\n")
    with open(stem + ".dat.meta", "w", encoding="utf-8") as f:
        f.write("HYBMESH_META 2\n")
        f.write(f"COUNT {len(pts)}\n")
        f.write("NPIECES 0\n")
        f.write(f"NSEGMENTS {n_seg}\n")
        for s in seg_ids:
            f.write(f"{s} {bc} line\n")
        f.write(f"POINTS {len(pts)}\n")
        for k, s in enumerate(ids):
            f.write(f"{s} {1 if k % per_seg == 0 else 0}\n")
    return stem + ".dat"


def split_segment_in_meta(dat_path, old_id, new_ids):
    """Cut segment ``old_id`` into ``new_ids``, in the SIDECAR only (#138).

    THE ``.dat`` IS NOT TOUCHED, because a CAD split does not move a point: it
    re-partitions the points that are already there and stamps the halves with new
    :class:`SegmentModel` ids. That is the edit #138's demo is built on — "go back to
    the CAD stage and cut one more segment into a geometry a topology is bound to" —
    and it is what makes the stored id stop resolving while every coordinate the
    binding was chosen against is still exactly where it was.

    Returns the sidecar's previous text, so a caller can put it back and watch the
    flag clear the way undoing the CAD edit would.
    """
    meta = dat_path + ".meta"
    with open(meta, encoding="utf-8") as fh:
        before = fh.read()
    lines = before.splitlines()
    out, i = [], 0
    while i < len(lines):
        parts = lines[i].split()
        if parts and parts[0] == "NSEGMENTS":
            m = int(parts[1])
            rows = lines[i + 1:i + 1 + m]
            grown = []
            for row in rows:
                sp = row.split()
                if sp and int(sp[0]) == int(old_id):
                    grown += [" ".join([str(n)] + sp[1:]) for n in new_ids]
                else:
                    grown.append(row)
            out.append(f"NSEGMENTS {len(grown)}")
            out += grown
            i += 1 + m
            continue
        if parts and parts[0] == "POINTS":
            n = int(parts[1])
            rows = lines[i + 1:i + 1 + n]
            mine = [k for k, row in enumerate(rows)
                    if row.split() and int(row.split()[0]) == int(old_id)]
            # Cut the run into len(new_ids) contiguous pieces, in order, so each
            # half is still ONE contiguous run of points — the shape
            # `topology_binding._spans` requires and the mesher refuses without.
            per = max(1, len(mine) // max(1, len(new_ids)))
            for j, k in enumerate(mine):
                which = min(len(new_ids) - 1, j // per)
                sp = rows[k].split()
                rows[k] = " ".join([str(new_ids[which])] + sp[1:])
            out.append(f"POINTS {n}")
            out += rows
            i += 1 + n
            continue
        out.append(lines[i])
        i += 1
    with open(meta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    return before


def restore_meta(dat_path, text):
    """Put a sidecar back, as undoing the CAD edit would."""
    with open(dat_path + ".meta", "w", encoding="utf-8") as fh:
        fh.write(text)


def meta_stamp(dat_path):
    """``(mtime_ns, size)`` of the sidecar — the half of the binding cache's key
    that a sidecar-only edit moves. Read by the gate so the claim "the context is
    re-read" rests on a measurement rather than on the cache's docstring."""
    st = os.stat(dat_path + ".meta")
    return (st.st_mtime_ns, st.st_size)


def write_airfoil(stem, seg_ids, bcs, n=195, designation="0012", chord=1.0,
                  x_le=0.0, y_le=0.0, alpha_deg=0.0, sharp_te=True,
                  mirror_y=False):
    """A DRAWN aerofoil as a ``.dat`` plus its ``.meta`` sidecar (#148).

    Built through the CAD stage's OWN law and the CAD stage's own segmentation —
    ``naca_airfoil.segment_parts`` decides how many segments there are and
    ``airfoil_points`` decides where the points go — so a blunt section arrives here
    with THREE segments because that is what the CAD produces, not because this
    writer was told to make three. A fixture that hand-wrote the split would be
    testing the C-grid against this file's idea of an aerofoil.

    The point layout mirrors the shipped ``naca0012_cgrid.dat``: each part
    contributes every point but its last (the joint belongs to the part that STARTS
    there), and the loop closes on a trailing duplicate stamped with the first
    segment's id — which is what ``topology_binding._close_loop`` drops and what the
    mesher's loader pops.

    ``mirror_y`` negates y, which leaves the section's SHAPE alone for a symmetric
    designation and reverses the loop's WINDING: the segment that leaves the trailing
    edge is then the -y surface. That is the one thing the C-grid family has to
    measure rather than assume, so it is a fixture flag rather than a second file.
    """
    from app.services.naca_airfoil import (
        airfoil_points, part_node_counts, segment_parts,
    )
    parts = segment_parts(bool(sharp_te))
    if len(seg_ids) != len(parts) or len(bcs) != len(parts):
        raise ValueError(f"this section has {len(parts)} part(s) "
                         f"({', '.join(parts)}); give one id and one bc for each.")
    counts = part_node_counts(n, parts)
    runs = [airfoil_points(designation=designation, n=counts[q], part=q, chord=chord,
                           x_le=x_le, y_le=y_le, alpha_deg=alpha_deg,
                           sharp_te=sharp_te) for q in parts]
    pts, ids = [], []
    for sid, run in zip(seg_ids, runs):
        pts += run[:-1]
        ids += [sid] * (len(run) - 1)
    pts.append(runs[0][0])
    ids.append(seg_ids[0])
    if mirror_y:
        pts = [(x, -y) for x, y in pts]
    with open(stem + ".dat", "w", encoding="utf-8") as f:
        for x, y in pts:
            f.write(f"{x:.12f} {y:.12f}\n")
    with open(stem + ".dat.meta", "w", encoding="utf-8") as f:
        f.write("HYBMESH_META 2\n")
        f.write(f"COUNT {len(pts)}\n")
        f.write("NPIECES 0\n")
        f.write(f"NSEGMENTS {len(parts)}\n")
        for sid, bc in zip(seg_ids, bcs):
            f.write(f"{sid} {bc} line\n")
        f.write(f"POINTS {len(pts)}\n")
        prev = None
        for s in ids:
            f.write(f"{s} {1 if s != prev else 0}\n")
            prev = s
    return stem + ".dat"


def write_cgrid_farfield(stem, seg_ids, bcs, te_xy=(1.0, 0.0), x_le=0.0,
                         wake_len=19.0, radius=10.0, arc=40, cw=False, rotate=0):
    """A DRAWN C-grid far field: the shipped ``cgrid_farfield.dat``'s own shape (#149).

    Six corners at exactly where ``topology_cgrid_section.far_corners`` generates
    them, so the drawn path and the generated path can be compared on the same
    geometry rather than on two shapes that merely look alike — and the sides
    between them are the shipped document's: straight from the outlet to the
    trailing-edge station, then a SEMICIRCULAR nose, which is the half where a
    generated hexagon and a drawn D differ.

    ``seg_ids`` decides how many segments the outline is cut into as well as what
    they are called. SIX is the shape a C-grid binds, one per block side, and every
    other count is the refusal the family owes the user: for those the whole closed
    polyline is split into equal contiguous chunks instead, which is what a far
    field segmented by hand rather than for this template looks like.

    ``cw`` reverses the winding and ``rotate`` starts the outline at a later joint —
    the two things a binding cannot see (every id still resolves, every side still
    lies on its own segment) and the mesher would answer with a folded grid rather
    than a refusal.
    """
    x_te, y0 = te_xy
    x_out = x_te + wake_len
    corners = [(x_out, y0), (x_out, y0 + radius), (x_te, y0 + radius),
               (x_le - radius, y0), (x_te, y0 - radius), (x_out, y0 - radius)]

    def line(a, b, n):
        return [(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n)
                for k in range(n)]

    def nose(a0, a1, n):
        """Quarter arc of the nose semicircle, centred at the leading-edge station."""
        return [(x_le + radius * math.cos(a0 + (a1 - a0) * k / n),
                 y0 + radius * math.sin(a0 + (a1 - a0) * k / n))
                for k in range(n)]

    runs = [
        line(corners[0], corners[1], 20),
        line(corners[1], corners[2], 40),
        line(corners[2], (x_le, y0 + radius), 5) + nose(math.pi / 2, math.pi, arc),
        nose(math.pi, 3 * math.pi / 2, arc) + line((x_le, y0 - radius),
                                                   corners[4], 5),
        line(corners[4], corners[5], 40),
        line(corners[5], corners[0], 20),
    ]
    if cw:
        # The same loop walked the other way from the same first point, so every
        # joint is still a joint and only the ORDER reverses: wk, fl, f3, f2, f1, fu.
        flat = [p for run in runs for p in run]
        runs = _regroup([flat[0]] + flat[:0:-1],
                        [len(r) for r in reversed(runs)])
    if rotate:
        # The same loop STARTED at a later joint. Every id still resolves and every
        # side still lies on its own segment; what moves is which joint is `wk`.
        flat = [p for run in runs for p in run]
        cut = sum(len(r) for r in runs[:rotate % len(runs)])
        runs = _regroup(flat[cut:] + flat[:cut],
                        [len(r) for r in _shift(runs, rotate)])
    if len(seg_ids) != len(runs):
        runs = _equal_chunks([p for run in runs for p in run], len(seg_ids))

    pts, ids = [], []
    for sid, run in zip(seg_ids, runs):
        pts += run
        ids += [sid] * len(run)
    pts.append(pts[0])
    ids.append(seg_ids[0])
    with open(stem + ".dat", "w", encoding="utf-8") as f:
        for x, y in pts:
            f.write(f"{x:.12f} {y:.12f}\n")
    with open(stem + ".dat.meta", "w", encoding="utf-8") as f:
        f.write("HYBMESH_META 2\n")
        f.write(f"COUNT {len(pts)}\n")
        f.write("NPIECES 0\n")
        f.write(f"NSEGMENTS {len(seg_ids)}\n")
        for sid, bc in zip(seg_ids, bcs):
            f.write(f"{sid} {bc} line\n")
        f.write(f"POINTS {len(pts)}\n")
        prev = object()
        for s in ids:
            f.write(f"{s} {1 if s != prev else 0}\n")
            prev = s
    return stem + ".dat"


def _shift(runs, k):
    return runs[k % len(runs):] + runs[:k % len(runs)]


def _regroup(flat, sizes):
    out, at = [], 0
    for n in sizes:
        out.append(flat[at:at + n])
        at += n
    return out


def _equal_chunks(flat, n):
    step = len(flat) / float(n)
    return [flat[int(round(k * step)):int(round((k + 1) * step))]
            for k in range(n)]
