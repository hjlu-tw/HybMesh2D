"""Read/write the per-geometry ``.meta`` sidecar that carries per-segment
metadata (boundary-condition tag + curve kind) alongside a resampled ``.dat``.

Format (written by the C++ resampler, tools/PreProcessor/src/main.cpp
saveMetadata — keep in sync):

    HYBMESH_META 2
    COUNT <n>
    NPIECES <k> [b1 b2 ...]
    NSEGMENTS <m>
    <segId> <bc|-> <kind>      x m
    POINTS <n>
    <segId> <isCorner>         x n

Only the NSEGMENTS block's BC column is edited here; everything else is copied
through verbatim so points / pieces / kinds are preserved.
"""
from __future__ import annotations
import os


def meta_path_for(dat_path: str) -> str:
    return dat_path + ".meta"


def read_meta_segments(dat_path: str) -> list[tuple[int, str, str]]:
    """Return [(seg_id, bc, kind), ...] from the geometry's .meta sidecar, or []
    if there is no sidecar / no segment block. bc is "" when unset."""
    meta = meta_path_for(dat_path)
    if not os.path.exists(meta):
        return []
    try:
        with open(meta, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    segs: list[tuple[int, str, str]] = []
    for i, line in enumerate(lines):
        parts = line.split()
        if parts and parts[0] == "NSEGMENTS":
            try:
                m = int(parts[1])
            except (IndexError, ValueError):
                return []
            for j in range(m):
                if i + 1 + j >= len(lines):
                    break
                sp = lines[i + 1 + j].split()
                if not sp:
                    continue
                try:
                    sid = int(sp[0])
                except ValueError:
                    continue
                bc = sp[1] if len(sp) >= 2 else "-"
                kind = sp[2] if len(sp) >= 3 else "polyline"
                segs.append((sid, "" if bc == "-" else bc, kind))
            break
    return segs


def read_meta_seg_growbl(dat_path: str) -> dict[int, bool]:
    """Return {seg_id: grow_bl} from the NSEGMENTS block's v3 grow-BL column (the
    4th column, ``segId bc kind growBL``). Segments without the column default to
    True (grow a boundary layer). Empty dict if there is no sidecar/segment block."""
    meta = meta_path_for(dat_path)
    if not os.path.exists(meta):
        return {}
    try:
        with open(meta, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return {}
    out: dict[int, bool] = {}
    for i, line in enumerate(lines):
        parts = line.split()
        if parts and parts[0] == "NSEGMENTS":
            try:
                m = int(parts[1])
            except (IndexError, ValueError):
                return {}
            for j in range(m):
                if i + 1 + j >= len(lines):
                    break
                sp = lines[i + 1 + j].split()
                if not sp:
                    continue
                try:
                    sid = int(sp[0])
                except ValueError:
                    continue
                out[sid] = len(sp) < 4 or sp[3] != "0"
            break
    return out


def write_meta_seg_growbl(dat_path: str, seg_grow: dict[int, bool]) -> bool:
    """Rewrite the .meta sidecar, setting each listed segment's grow-BL flag (the
    v3 4th column) while preserving bc, kind, points and pieces. Bumps the format
    header to at least version 3 and ensures every NSEGMENTS line carries the 4th
    column (segments not in ``seg_grow`` keep their current flag, default grow=1).
    Returns False if there is no sidecar to update."""
    meta = meta_path_for(dat_path)
    if not os.path.exists(meta):
        return False
    try:
        with open(meta, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return False

    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        parts = line.split()
        # The grow-BL column is a v3 feature: bump the header so the mesher's
        # version-gated reader expects the 4th column.
        if i == 0 and parts and parts[0] == "HYBMESH_META":
            try:
                ver = max(3, int(parts[1]))
            except (IndexError, ValueError):
                ver = 3
            out.append(f"HYBMESH_META {ver}")
            i += 1
            continue
        out.append(line)
        if parts and parts[0] == "NSEGMENTS":
            try:
                m = int(parts[1])
            except (IndexError, ValueError):
                m = 0
            for j in range(m):
                if i + 1 + j >= len(lines):
                    break
                sp = lines[i + 1 + j].split()
                if not sp:
                    out.append(lines[i + 1 + j])
                    continue
                try:
                    sid = int(sp[0])
                except ValueError:
                    # Format drift / bad NSEGMENTS count: preserve the line
                    # verbatim instead of crashing the save (matches the read path).
                    out.append(lines[i + 1 + j])
                    continue
                bc = sp[1] if len(sp) >= 2 else "-"
                kind = sp[2] if len(sp) >= 3 else "polyline"
                if sid in seg_grow:
                    grow = 1 if seg_grow[sid] else 0
                else:
                    grow = 0 if (len(sp) >= 4 and sp[3] == "0") else 1
                out.append(f"{sid} {bc} {kind} {grow}")
            i += 1 + m
            continue
        i += 1
    try:
        with open(meta, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
    except OSError:
        return False
    return True


def read_meta_point_segids(dat_path: str) -> list[int]:
    """Return the segment id of each point (the POINTS block's first column), so
    a segment can be mapped back to the geometry points that belong to it."""
    meta = meta_path_for(dat_path)
    if not os.path.exists(meta):
        return []
    try:
        with open(meta, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    for i, line in enumerate(lines):
        parts = line.split()
        if parts and parts[0] == "POINTS":
            try:
                n = int(parts[1])
            except (IndexError, ValueError):
                n = len(lines) - i - 1
            out: list[int] = []
            for j in range(n):
                if i + 1 + j >= len(lines):
                    break
                sp = lines[i + 1 + j].split()
                try:
                    out.append(int(sp[0]))
                except (IndexError, ValueError):
                    out.append(-1)
            return out
    return []


def write_meta_segbc(dat_path: str, seg_bc: dict[int, str]) -> bool:
    """Rewrite the .meta sidecar, replacing each listed segment's BC tag (by
    seg_id) while preserving kinds, points and piece breaks. Returns False if
    there is no sidecar to update."""
    meta = meta_path_for(dat_path)
    if not os.path.exists(meta):
        return False
    try:
        with open(meta, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return False

    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        parts = line.split()
        out.append(line)
        if parts and parts[0] == "NSEGMENTS":
            try:
                m = int(parts[1])
            except (IndexError, ValueError):
                m = 0
            for j in range(m):
                if i + 1 + j >= len(lines):
                    break
                sp = lines[i + 1 + j].split()
                if not sp:
                    out.append(lines[i + 1 + j])
                    continue
                try:
                    sid = int(sp[0])
                except ValueError:
                    # Format drift / bad NSEGMENTS count: preserve the line
                    # verbatim instead of crashing the save (matches the read path).
                    out.append(lines[i + 1 + j])
                    continue
                kind = sp[2] if len(sp) >= 3 else "polyline"
                grow = sp[3] if len(sp) >= 4 else None   # preserve v3 grow-BL column
                if sid in seg_bc:
                    bc = (seg_bc[sid] or "").strip() or "-"
                else:
                    bc = sp[1] if len(sp) >= 2 else "-"
                out.append(f"{sid} {bc} {kind}" + (f" {grow}" if grow is not None else ""))
            i += 1 + m
            continue
        i += 1
    try:
        with open(meta, "w", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
    except OSError:
        return False
    return True
