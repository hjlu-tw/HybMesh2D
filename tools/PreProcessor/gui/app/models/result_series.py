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

**A series is one or MORE files** (#32). A restarted solve is one physical run
split across ``work/xtecp_sol_allz.dat.gui`` plus one file per ``work/prev_<NNN>/``
archive, so playing it as one animation means a flat frame index ABOVE the
per-file byte-offset indices: global frame *k* resolves to ``(file, zone)``. The
per-file ``tecplot_index`` is kept exactly as it was — its ``(path, mtime, size)``
cache is right, and a merged temp file would throw away the byte-offset seek that
makes a frame cost 0.07 s instead of 0.35 s. Three things are therefore GLOBAL
rather than per file: the frame numbering, the LRU byte budget, and every value
range :meth:`global_range` reports. Which files make up a series, and in what
order, is ``services/result_legs``'s question, not this module's.

Qt-free on purpose: the playback UI owns the timer, this owns the data.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.models.result_data import TecplotResult
from app.models.tecplot_index import build_index, index_for, stamp
from app.services.logging_setup import get_logger

_log = get_logger(__name__)

# One frame of a 35k-node / 69k-cell mesh with 8 cell variables is ~7 MB. The
# byte cap (not a frame count) is what keeps a big transient run from filling
# memory: 512 MB holds ~70 such frames and only a handful of very large ones.
_DEFAULT_MAX_BYTES = 512 * 1024 * 1024

#: What separates a leg's name from the frame position in a label.
_LEG_SEP = " · "


@dataclass
class _File:
    """One file of the series and everything the series knows about it.

    A record rather than four lists indexed by the same ``fi`` — the repo's own
    reasoning for ``JunctionNode`` ("AoS, not six parallel arrays"), and here the
    alignment is a real invariant rather than a tidiness point: an unreadable leg
    is dropped at construction, and dropping it from three lists and forgetting
    the fourth would silently pair one file's label with another's index.

    ``stamp`` and ``index`` are re-assigned when the file changes on disk, so
    this is mutable on purpose.
    """
    path: str
    label: str
    stamp: tuple
    index: object


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
    """Frame access + global value ranges over one or more result files.

    ``paths`` is a single path or an ordered sequence of them (the legs of a
    restarted solve, oldest solution first). ``labels`` names each file for
    :meth:`frame_label`; an empty label means "do not prefix", which is what a
    single-file series uses so its labels are unchanged.
    """

    def __init__(self, paths, max_bytes: int = _DEFAULT_MAX_BYTES,
                 labels=None):
        if isinstance(paths, str):
            paths = [paths]
        paths = [str(p) for p in paths]
        labels = list(labels) if labels is not None else [""] * len(paths)
        if len(labels) != len(paths):
            raise ValueError(
                f"{len(paths)} path(s) but {len(labels)} label(s)")
        self._max_bytes = int(max_bytes)
        self._frames: dict = {}          # global frame index -> TecplotResult (LRU)
        self._bytes = 0
        self._ranges: dict = {}          # var -> (vmin, vmax) over ALL frames
        self._files: list = []
        for path, label in zip(paths, labels):
            try:
                # Stamp FIRST, then index: if the file is written in between, the
                # recorded stamp is older than the content we hold, so the next access
                # notices and re-indexes. The other order would record "up to date"
                # over a stale index, permanently.
                st = stamp(path)
                idx = index_for(path)
            except OSError:
                # One unreadable leg must not cost the whole animation: a case is
                # free to have had a leg deleted. Dropped here, before anything is
                # numbered, so no index can point at a file that is not in the list.
                _log.warning("dropping %s from the series: it cannot be read",
                             path, exc_info=True)
                continue
            self._files.append(_File(path=path, label=label, stamp=st, index=idx))
        if not self._files:
            raise ValueError(f"no readable result file among {len(paths)}")
        self._map = self._build_map()

    # ------------------------------------------------------------------ #
    @property
    def paths(self) -> list:
        return [f.path for f in self._files]

    @property
    def labels(self) -> list:
        return [f.label for f in self._files]

    def _build_map(self) -> list:
        """``[(file index, zone index), …]`` — the flat frame numbering.

        Rebuilt whenever any file's index is, since a leg that gained a zone
        renumbers every frame after it.
        """
        return [(fi, zi)
                for fi, f in enumerate(self._files)
                for zi in range(len(f.index.zones))]

    def _live_indices(self) -> list:
        """The indices for the files AS THEY ARE NOW, dropping caches on a change.

        Everything public reads through this instead of the snapshot taken in
        ``__init__``, because the frame COUNT/labels and the frame DATA used to come from
        two different snapshots: ``from_file`` re-resolved the index itself. A run
        rewritten under an open Results tab therefore reported the old zone count while
        serving frames from the new file — and replayed already-cached frames from the
        OLD one, interleaving two solutions under a colour scale pinned to the first,
        which reads as physics. One index per file, refreshed on a real content change.

        A change in ANY file drops EVERY cached frame and range, not just that
        file's: the flat numbering shifts, so a cache keyed by global frame would
        serve one leg's zone under another's number, and a range that spans the
        series is no longer a range of this series.
        """
        changed = []
        for f in self._files:
            try:
                st = stamp(f.path)
            except OSError:
                # The file went away (a case directory cleaned up mid-session). Keep
                # answering from the last good index rather than raising out of a paint
                # path; the next frame read reports the real error.
                _log.debug("could not stat %s; keeping the last index", f.path,
                           exc_info=True)
                continue
            if st != f.stamp:
                f.stamp = st
                f.index = index_for(f.path)
                changed.append(f.path)
        if changed:
            _log.info("%s changed on disk — re-indexing, dropping %d cached "
                      "frame(s)", ", ".join(changed), len(self._frames))
            self._drop_caches()
            self._map = self._build_map()
        return [f.index for f in self._files]

    def _drop_caches(self) -> None:
        """Forget every materialised frame and every scanned range."""
        self._frames.clear()
        self._bytes = 0
        self._ranges.clear()

    def _live_map(self) -> list:
        """The flat frame map, refreshed against the files on disk."""
        self._live_indices()
        return self._map

    # ------------------------------------------------------------------ #
    @property
    def zones(self) -> list:
        """Every file's zones, concatenated in series order.

        ``ZoneInfo.index`` is a position WITHIN its file, so it is not a frame
        number here; ask :meth:`frame_label` or index this list.
        """
        return [z for idx in self._live_indices() for z in idx.zones]

    @property
    def n_frames(self) -> int:
        return len(self._live_map())

    @property
    def n_files(self) -> int:
        return len(self._files)

    def locate(self, k: int) -> tuple:
        """``(file index, zone index)`` for global frame ``k``."""
        return self._live_map()[k]

    def path_of(self, k: int) -> str:
        """Which file global frame ``k`` comes from."""
        return self._files[self.locate(k)[0]].path

    def frame_label(self, k: int) -> str:
        """Human label for frame ``k`` — its 1-based position, named by leg.

        The solver writes the same zone title ("time 0") for every dumped step,
        so the position is the only honest identifier; the title is appended only
        when the file actually distinguishes its zones.

        Across a restarted solve the position alone stops being meaningful — two
        legs both have a "Frame 3" — so the leg's name leads (#32):
        ``prev_002 · Frame 3 / 10``. The position stays WITHIN the leg, which is
        the pair the label is identifying; a single-file series has no leg name
        and its labels are byte-identical to what they were.
        """
        m = self._live_map()
        n = len(m)
        if not (0 <= k < n):
            # A label must never raise: the caller's frame index can outlive a file
            # that shrank under it (a re-run with fewer dumped steps), and this is
            # called from the UI refresh, not from a load path that can report it.
            return f"Frame {k + 1} / {n}"
        fi, zi = m[k]
        zones = self._files[fi].index.zones
        label = f"Frame {zi + 1} / {len(zones)}"
        if len({z.title for z in zones}) > 1:
            label += f" — {zones[zi].title}"
        leg = self._files[fi].label
        # Only a MULTI-file series prefixes. A case that was never restarted has
        # exactly one leg and its read-out must not grow a name that distinguishes
        # it from nothing — and a caller that declines the whole solve gets the
        # single file it asked for, labelled the way it always was.
        return (f"{leg}{_LEG_SEP}{label}"
                if leg and len(self._files) > 1 else label)

    # ------------------------------------------------------------------ #
    @property
    def variables(self) -> list:
        """The variables EVERY file in the series carries, in the first's order.

        The intersection, not the union (#32): a variable only some legs hold
        would render as a blank frame — or worse, as a differently-meaning column
        — at every boundary that lacks it. Which legs are short of what is
        :meth:`variable_gaps`, so the caller can say so instead of the animation
        silently changing subject.
        """
        indices = self._live_indices()
        common = set(indices[0].variables)
        for idx in indices[1:]:
            common &= set(idx.variables)
        return [v for v in indices[0].variables if v in common]

    def variable_gaps(self) -> list:
        """``[(label, (missing, …)), …]`` for the files short of a variable some
        other file in the series has. Empty when they all agree."""
        indices = self._live_indices()
        union = []
        for idx in indices:
            union += [v for v in idx.variables if v not in union]
        out = []
        for f, idx in zip(self._files, indices):
            missing = tuple(v for v in union if v not in set(idx.variables))
            if missing:
                out.append((f.label or f.path, missing))
        return out

    # ------------------------------------------------------------------ #
    def frame(self, k: int) -> TecplotResult:
        """Materialise global frame ``k``, serving it from the cache when possible."""
        # Ask for the map BEFORE the cache lookup: on a changed file it is what drops
        # the now-foreign frames, and it holds the index the read below goes through.
        m = self._live_map()
        if k in self._frames:
            r = self._frames.pop(k)      # re-insert: most-recently-used last
            self._frames[k] = r
            return r
        fi, zi = m[k]
        f = self._files[fi]
        r = TecplotResult.from_file(f.path, zone=zi, index=f.index)
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
        """(vmin, vmax) of ``var`` across EVERY frame of EVERY file, cached per
        variable.

        ``progress(done, total)`` is called after each frame so a long scan can
        report itself. Returns None when the variable has no finite values
        anywhere (the caller then falls back to per-frame auto-scaling).
        """
        if var in self._ranges:
            return self._ranges[var]
        lo, hi = np.inf, -np.inf
        # The scan must describe ONE generation of these files: if any is rewritten
        # while we are part-way through (a re-run into the same case dir), the frames
        # already read belong to the previous one, so the result is not cached as this
        # series' range.
        started_on = [f.stamp for f in self._files]
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
        if [f.stamp for f in self._files] == started_on:
            self._ranges[var] = rng
        return rng

    def has_global_range(self, var: str) -> bool:
        """Whether ``var``'s range is already known (i.e. asking is free)."""
        return var in self._ranges

    def invalidate(self) -> None:
        """Force a rebuild: drop every cache and re-scan every file from scratch.

        Ordinary staleness needs no call — every access re-checks (mtime, size). This is
        for the case that check cannot see: a rewrite landing inside one mtime tick at
        exactly the same size. It therefore calls ``build_index`` rather than
        ``index_for``, which would hand back the very index it was told to discard.
        """
        self._drop_caches()
        for f in self._files:
            f.stamp = stamp(f.path)            # before the scan; see __init__
            f.index = build_index(f.path)
        self._map = self._build_map()
