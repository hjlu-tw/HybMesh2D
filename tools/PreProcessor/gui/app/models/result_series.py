"""A multi-zone Tecplot result seen as a TIME SERIES of frames.

The Results view animates through the zones of a transient run, which needs two
things the single-zone :class:`TecplotResult` cannot provide on its own:

* **Cheap repeat access.** Playback revisits the same frames every loop, so
  materialised frames are kept in a bounded LRU cache (bounded by BYTES, since
  one frame of a large mesh is tens of MB and a long run has hundreds of them).
* **A stable colour scale.** Auto-scaling each frame to its own min/max makes the
  colours jump every step, which hides exactly the physical change the animation
  is meant to show. :meth:`global_range` scans every frame ONCE per variable and
  caches the result, so the whole animation shares one scale.

Qt-free on purpose: the playback UI owns the timer, this owns the data.
"""
from __future__ import annotations

import numpy as np

from app.models.result_data import TecplotResult
from app.models.tecplot_index import index_for

# One frame of a 35k-node / 69k-cell mesh with 8 cell variables is ~7 MB. The
# byte cap (not a frame count) is what keeps a big transient run from filling
# memory: 512 MB holds ~70 such frames and only a handful of very large ones.
_DEFAULT_MAX_BYTES = 512 * 1024 * 1024


def _frame_nbytes(r: TecplotResult) -> int:
    """Rough resident size of one materialised frame."""
    total = r.nodes.nbytes + r.elements.nbytes
    for d in (r.cell_data, r.node_data):
        for a in d.values():
            total += getattr(a, "nbytes", 0)
    return int(total)


class ResultSeries:
    """Frame access + global value ranges for one multi-zone result file."""

    def __init__(self, path: str, max_bytes: int = _DEFAULT_MAX_BYTES):
        self.path = path
        self._max_bytes = int(max_bytes)
        self._index = index_for(path)
        self._frames: dict = {}          # zone index -> TecplotResult (LRU by order)
        self._bytes = 0
        self._ranges: dict = {}          # var -> (vmin, vmax) over ALL frames

    # ------------------------------------------------------------------ #
    @property
    def zones(self) -> list:
        return list(self._index.zones)

    @property
    def n_frames(self) -> int:
        return len(self._index.zones)

    def frame_label(self, k: int) -> str:
        """Human label for frame ``k`` — 1-based position in the file.

        The solver writes the same zone title ("time 0") for every dumped step,
        so the position is the only honest identifier; the title is appended only
        when the file actually distinguishes its zones.
        """
        n = self.n_frames
        label = f"Frame {k + 1} / {n}"
        titles = {z.title for z in self._index.zones}
        if len(titles) > 1:
            label += f" — {self._index.zones[k].title}"
        return label

    # ------------------------------------------------------------------ #
    def frame(self, k: int) -> TecplotResult:
        """Materialise zone ``k``, serving it from the cache when possible."""
        if k in self._frames:
            r = self._frames.pop(k)      # re-insert: most-recently-used last
            self._frames[k] = r
            return r
        r = TecplotResult.from_file(self.path, zone=k)
        self._frames[k] = r
        self._bytes += _frame_nbytes(r)
        self._evict()
        return r

    def _evict(self) -> None:
        """Drop least-recently-used frames until the cache is under its cap.

        The most recent frame is never evicted (it is the one on screen), so a
        single frame larger than the cap still works — it just isn't cached
        alongside anything else.
        """
        while self._bytes > self._max_bytes and len(self._frames) > 1:
            k, r = next(iter(self._frames.items()))
            del self._frames[k]
            self._bytes -= _frame_nbytes(r)

    def cached_frames(self) -> int:
        return len(self._frames)

    # ------------------------------------------------------------------ #
    def global_range(self, var: str, progress=None):
        """(vmin, vmax) of ``var`` across EVERY frame, cached per variable.

        ``progress(done, total)`` is called after each frame so a long scan can
        report itself. Returns None when the variable has no finite values
        anywhere (the caller then falls back to per-frame auto-scaling).
        """
        if var in self._ranges:
            return self._ranges[var]
        lo, hi = np.inf, -np.inf
        n = self.n_frames
        for k in range(n):
            vals = np.asarray(self.frame(k).get_cell_field(var), dtype=float)
            finite = vals[np.isfinite(vals)]
            if finite.size:
                lo = min(lo, float(finite.min()))
                hi = max(hi, float(finite.max()))
            if progress is not None:
                progress(k + 1, n)
        rng = None if lo > hi else (lo, hi)
        self._ranges[var] = rng
        return rng

    def has_global_range(self, var: str) -> bool:
        """Whether ``var``'s range is already known (i.e. asking is free)."""
        return var in self._ranges

    def invalidate(self) -> None:
        """Drop cached frames and ranges (the file changed on disk)."""
        self._frames.clear()
        self._bytes = 0
        self._ranges.clear()
        self._index = index_for(self.path)
