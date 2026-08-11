"""Byte-offset index over a multi-zone Tecplot FEBLOCK result file.

A transient solver run appends one zone per dumped step, so ``xtecp_sol_allz.dat``
grows to hundreds of MB. Loading zone *k* used to ``readlines()`` the WHOLE file
and rescan it for zone headers, which is fine when a result is opened once but
not when the Results view animates through the zones — every frame paid for the
entire file.

This module scans the file ONCE, records the byte offset of each ``zone`` header,
and caches that index keyed by (path, mtime, size). Loading a frame then seeks
straight to its byte range and reads only that zone. The index is what makes
frame-by-frame playback affordable; nothing here parses field data.
"""
from __future__ import annotations
import os
import re
from dataclasses import dataclass, field

_ZONE_RE = re.compile(r"^\s*zone\b", re.IGNORECASE)
_N_RE = re.compile(r"\bN\s*=\s*(\d+)", re.IGNORECASE)
_E_RE = re.compile(r"\bE\s*=\s*(\d+)", re.IGNORECASE)
_ZONETYPE_RE = re.compile(r"ZONETYPE\s*=\s*(\w+)", re.IGNORECASE)
_TITLE_RE = re.compile(r't\s*=\s*"([^"]*)"', re.IGNORECASE)

# Byte-level counterparts used while scanning the file in binary mode (decoding
# 100+ MB just to find the header lines would defeat the point of the index).
_ZONE_RE_B = re.compile(rb"^\s*zone\b", re.IGNORECASE)
_VARIABLES_RE_B = re.compile(rb"^\s*variables\b", re.IGNORECASE)


def parse_variables(line: str) -> list[str]:
    """Extract the quoted variable names from a `variables = "x", "y", ...` line."""
    return re.findall(r'"([^"]*)"', line)


@dataclass
class ZoneInfo:
    """Header metadata for one zone (no field data loaded)."""
    index: int
    title: str
    n_nodes: int
    n_elems: int
    zonetype: str


def parse_zone_header(header: str, index: int) -> ZoneInfo:
    """Read N / E / ZONETYPE / title out of one ``zone ...`` header line."""
    n = _N_RE.search(header)
    e = _E_RE.search(header)
    zt = _ZONETYPE_RE.search(header)
    title = _TITLE_RE.search(header)
    return ZoneInfo(
        index=index,
        title=title.group(1) if title else f"zone {index}",
        n_nodes=int(n.group(1)) if n else 0,
        n_elems=int(e.group(1)) if e else 0,
        zonetype=zt.group(1) if zt else "",
    )


@dataclass
class TecplotIndex:
    """Where each zone lives in the file, and the file's variable names."""

    path: str
    variables: list[str] = field(default_factory=list)
    zones: list[ZoneInfo] = field(default_factory=list)
    offsets: list[int] = field(default_factory=list)   # byte offset per zone header
    size: int = 0                                      # file size (end of last zone)

    def zone_byte_range(self, k: int) -> tuple[int, int]:
        """(start, end) byte offsets of zone ``k``'s header + data region."""
        start = self.offsets[k]
        end = self.offsets[k + 1] if k + 1 < len(self.offsets) else self.size
        return start, end

    def read_zone_lines(self, k: int) -> list[str]:
        """Read ONLY zone ``k``'s byte range and return it as decoded lines.

        Line 0 is the zone header, so callers parse relative to it rather than
        to an absolute line number in the file.
        """
        start, end = self.zone_byte_range(k)
        with open(self.path, "rb") as f:
            f.seek(start)
            blob = f.read(max(0, end - start))
        return blob.decode("utf-8", errors="replace").splitlines(keepends=True)


def build_index(path: str) -> TecplotIndex:
    """Scan ``path`` once, recording the variables line and every zone offset."""
    idx = TecplotIndex(path=path)
    pos = 0
    with open(path, "rb") as f:
        for raw in f:
            if not idx.variables and _VARIABLES_RE_B.match(raw):
                idx.variables = parse_variables(
                    raw.decode("utf-8", errors="replace"))
            if _ZONE_RE_B.match(raw):
                header = raw.decode("utf-8", errors="replace")
                idx.zones.append(parse_zone_header(header, len(idx.zones)))
                idx.offsets.append(pos)
            pos += len(raw)
    idx.size = pos
    return idx


# Indices are cached so repeated frame loads (playback) scan the file once. The
# key carries mtime+size, so a result file the solver is still appending to is
# re-indexed rather than served stale.
_CACHE: dict[str, tuple[tuple, TecplotIndex]] = {}
_CACHE_MAX = 4


def _stamp(path: str) -> tuple:
    st = os.stat(path)
    return (st.st_mtime_ns, st.st_size)


def index_for(path: str) -> TecplotIndex:
    """Return the cached index for ``path``, building it if missing or stale."""
    key = os.path.abspath(path)
    stamp = _stamp(path)
    hit = _CACHE.get(key)
    if hit is not None and hit[0] == stamp:
        return hit[1]
    idx = build_index(path)
    if len(_CACHE) >= _CACHE_MAX:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = (stamp, idx)
    return idx


def clear_index_cache() -> None:
    """Drop every cached index (used by tests and by an explicit reload)."""
    _CACHE.clear()
