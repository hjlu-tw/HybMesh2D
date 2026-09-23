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
