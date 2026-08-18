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


def _points_block_end(lines: list[str]) -> int:
    """Index just past the last POINTS row, or len(lines) if there is no POINTS
    block. Everything after this index is GUI-only trailer (e.g. a GROUP_BC map);
    the C++ mesher stops reading at the end of the POINTS block, so a trailer is
    ignored by it but round-tripped by the writers here."""
    for i, line in enumerate(lines):
        parts = line.split()
        if parts and parts[0] == "POINTS":
            try:
                n = int(parts[1])
            except (IndexError, ValueError):
                n = 0
            return min(len(lines), i + 1 + n)
    return len(lines)


def read_meta_group_bc(dat_path: str) -> dict[str, str]:
    """Return {group_label: bc_type} from the .meta trailer written by
    :func:`write_meta_group_bc`. Empty dict if absent. This is the persisted
    half of the per-segment BC mechanism whose LABELS live in the NSEGMENTS bc
    column; without it the label→physical-type map is lost across a session
    reset / config reload and every boundary falls back to the wall default."""
    meta = meta_path_for(dat_path)
    if not os.path.exists(meta):
        return {}
    try:
        with open(meta, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return {}
    out: dict[str, str] = {}
    for line in lines[_points_block_end(lines):]:
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "GROUP_BC":
            out[parts[1]] = parts[2]
    return out


def write_meta_group_bc(dat_path: str, group_bc: dict[str, str]) -> bool:
    """Persist the group-label→BC-type map as a trailer after the POINTS block,
    preserving the whole meta above it and replacing any prior trailer. Only
    labels with a non-empty type are written. Returns False if no sidecar."""
    meta = meta_path_for(dat_path)
    if not os.path.exists(meta):
        return False
    try:
        with open(meta, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return False
    head = lines[:_points_block_end(lines)]
    trailer = [f"GROUP_BC {k} {v}"
               for k, v in group_bc.items()
               if str(k).strip() and str(v).strip()]
    try:
        with open(meta, "w", encoding="utf-8") as f:
            f.write("\n".join(head + trailer) + "\n")
    except OSError:
        return False
    return True


# snapshot_seg_edits / restore_seg_edits / describe_seg_edit_restore used to sit
# here: a snapshot of the MESH-stage per-segment edits (BC label, No-BL flag)
# taken before the resampler rewrote this sidecar and re-applied after. They are
# gone because the facts they carried are SegmentModel fields now, so the
# resampler receives them in its own config (sj["bc"] / sj["grow_bl"]) and writes
# the sidecar correctly the first time. The restore also had to refuse itself
# whenever the segment id set had changed — it re-applied by id after a
# subprocess had rewritten the file, so an added or removed edge would have moved
# the inlet onto another piece of wall. A field bound to the segment object has
# no such gap, which is why the refusal disappeared as a concept rather than
# being reimplemented here.


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
