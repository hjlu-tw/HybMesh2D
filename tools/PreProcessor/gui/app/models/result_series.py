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
from app.models.tecplot_index import build_index, index_for, stamp
from app.services.logging_setup import get_logger

_log = get_logger(__name__)

# One frame of a 35k-node / 69k-cell mesh with 8 cell variables is ~7 MB. The
# byte cap (not a frame count) is what keeps a big transient run from filling
# memory: 512 MB holds ~70 such frames and only a handful of very large ones.
_DEFAULT_MAX_BYTES = 512 * 1024 * 1024


def _frame_nbytes(r: TecplotResult) -> int:
    """Resident size of one frame, INCLUDING the buffer its field arrays are views into.

    ``from_file`` parses the zone into one token buffer and hands out slices of it, so a
    single cached slice keeps the whole buffer alive — connectivity region included, which
    no field array covers. Counting only the slices under-reported a frame by that region
    (~2.4 MB on a 100k-element mesh, ~25% of the frame), so a 512 MB cap really held
    ~630 MB: a machine sized to the declared bound swapped or was OOM-killed part-way
    through a playback instead of evicting, which is the one thing a BYTE cap (rather than
    a frame count) was chosen to prevent.
    """
    total = int(getattr(r, "raw_nbytes", 0)) + r.nodes.nbytes + r.elements.nbytes
    for d in (r.cell_data, r.node_data):
        for a in d.values():
            # A view is already inside raw_nbytes; only real copies add to the total (a
            # quad zone's cell values are tiled onto both triangles, i.e. copied).
            if getattr(a, "base", None) is None:
                total += getattr(a, "nbytes", 0)
    return int(total)


class ResultSeries:
    """Frame access + global value ranges for one multi-zone result file."""

    def __init__(self, path: str, max_bytes: int = _DEFAULT_MAX_BYTES):
        self.path = path
        self._max_bytes = int(max_bytes)
        self._frames: dict = {}          # zone index -> TecplotResult (LRU by order)
        self._bytes = 0
        self._ranges: dict = {}          # var -> (vmin, vmax) over ALL frames
        # Stamp FIRST, then index: if the file is written in between, the recorded stamp
        # is older than the content we hold, so the next access notices and re-indexes.
        # The other order would record "up to date" over a stale index, permanently.
        self._stamp = stamp(path)
        self._index = index_for(path)

    # ------------------------------------------------------------------ #
    def _live_index(self):
        """The index for the file AS IT IS NOW, dropping cached frames if it changed.

        Everything public reads through this instead of the snapshot taken in
        ``__init__``, because the frame COUNT/labels and the frame DATA used to come from
        two different snapshots: ``from_file`` re-resolved the index itself. A run
        rewritten under an open Results tab therefore reported the old zone count while
        serving frames from the new file — and replayed already-cached frames from the
        OLD one, interleaving two solutions under a colour scale pinned to the first,
        which reads as physics. One index per series, refreshed on a real content change.
        """
        try:
            st = stamp(self.path)
        except OSError:
            # The file went away (a case directory cleaned up mid-session). Keep
            # answering from the last good index rather than raising out of a paint
            # path; the next frame read reports the real error.
            _log.debug("could not stat %s; keeping the last index", self.path,
                       exc_info=True)
            return self._index
        if st != self._stamp:
            _log.info("%s changed on disk — re-indexing, dropping %d cached frame(s)",
                      self.path, len(self._frames))
            self._stamp = st
            self._index = index_for(self.path)
            self._drop_caches()
        return self._index

    def _drop_caches(self) -> None:
        """Forget every materialised frame and every scanned range."""
        self._frames.clear()
        self._bytes = 0
        self._ranges.clear()

    # ------------------------------------------------------------------ #
    @property
    def zones(self) -> list:
        return list(self._live_index().zones)

    @property
    def n_frames(self) -> int:
        return len(self._live_index().zones)

    def frame_label(self, k: int) -> str:
        """Human label for frame ``k`` — 1-based position in the file.

        The solver writes the same zone title ("time 0") for every dumped step,
        so the position is the only honest identifier; the title is appended only
        when the file actually distinguishes its zones.
        """
        zones = self._live_index().zones
        n = len(zones)
        label = f"Frame {k + 1} / {n}"
        titles = {z.title for z in zones}
        # A label must never raise: the caller's frame index can outlive a file that
        # shrank under it (a re-run with fewer dumped steps), and this is called from the
        # UI refresh, not from a load path that can report the error.
        if len(titles) > 1 and 0 <= k < n:
            label += f" — {zones[k].title}"
        return label

    # ------------------------------------------------------------------ #
    def frame(self, k: int) -> TecplotResult:
        """Materialise zone ``k``, serving it from the cache when possible."""
        # Ask for the index BEFORE the cache lookup: on a changed file it is what drops
        # the now-foreign frames, and it is the index the read below must go through.
        idx = self._live_index()
        if k in self._frames:
            r = self._frames.pop(k)      # re-insert: most-recently-used last
            self._frames[k] = r
            return r
        r = TecplotResult.from_file(self.path, zone=k, index=idx)
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
        # The scan must describe ONE file: if it is rewritten while we are part-way
        # through (a re-run into the same case dir), the frames already read belong to
        # the previous one, so the result is not cached as this file's range.
        started_on = self._stamp
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
        if self._stamp == started_on:
            self._ranges[var] = rng
        return rng

    def has_global_range(self, var: str) -> bool:
        """Whether ``var``'s range is already known (i.e. asking is free)."""
        return var in self._ranges

    def invalidate(self) -> None:
        """Force a rebuild: drop every cache and re-scan the file from scratch.

        Ordinary staleness needs no call — every access re-checks (mtime, size). This is
        for the case that check cannot see: a rewrite landing inside one mtime tick at
        exactly the same size. It therefore calls ``build_index`` rather than
        ``index_for``, which would hand back the very index it was told to discard.
        """
        self._drop_caches()
        self._stamp = stamp(self.path)      # before the scan; see __init__
        self._index = build_index(self.path)
