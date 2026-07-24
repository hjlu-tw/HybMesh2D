from __future__ import annotations
import json
import copy
from app.models.segment import SegmentModel

# Bump when the exported JSON config schema changes in a backward-incompatible
# way. Readers should tolerate a missing field (treated as version 0/legacy)
# and warn — but not crash — when the file version is newer than they support.
CONFIG_FORMAT_VERSION = 2


def _legacy_closed_mode(config: dict) -> str:
    """Map a legacy config's ``is_closed`` bool to a ``closed_mode`` string.

    Older files (and hand-written dicts) carry only the boolean. We treat that
    saved value as a *manual* choice (not auto-detect), so an existing project
    keeps behaving exactly as it did before this feature."""
    return "closed" if config.get("is_closed", True) else "open"


class ProjectModel:
    """Holds all data for one geometry file's resampling project."""

    def __init__(self):
        self.input_file: str = ""
        self.output_file: str = ""
        # closed_mode is the user intent: "auto" derives closure from the
        # geometry, "closed"/"open" force it. is_closed is the RESOLVED effective
        # value every meshing/resample/export call site reads — kept in sync by
        # resolve_closure(). Fresh raw .dat/.stl loads start "auto"; loading a
        # saved config maps its legacy bool to a manual mode (see _legacy_closed_mode).
        self.closed_mode: str = "auto"
        self.is_closed: bool = True
        self.segments: list[SegmentModel] = []
        self._next_curve_id: int = 10001

        # Advanced backend settings
        self.global_spline: bool = False
        self.transform: dict | None = None  # scale, rotate, translate

    # ── Segment management ────────────────────────────────────────────────

    @staticmethod
    def prune_degenerate_splits(split_indices, points):
        """Return `split_indices` with any boundary that would create a zero-length
        (coincident-endpoint) file segment removed.

        A split pair whose points collapse to one location produces a phantom
        ~zero-length edge (e.g. "Idx 100 → 101") that the user can neither select
        nor remove — its two endpoints are shared with both neighbours, so the
        remove path deletes nothing (services.index_helpers) and every rebuild
        (load / remove / convert-to-discrete / join) resurrects it. It also
        corrupts the per-segment .meta/BC numbering (an empty segment id). Merging
        it into its neighbour here is the single choke-point that kills it on every
        path. The first/last indices (the geometry endpoints) are always kept."""
        idx = sorted({int(i) for i in split_indices})
        if points is None or len(idx) < 3:
            return idx
        import numpy as np
        pts = np.asarray(points, dtype=float)
        n = len(pts)
        if n < 2:
            return idx
        mn = pts.min(axis=0)
        mx = pts.max(axis=0)
        diag = float(np.hypot(mx[0] - mn[0], mx[1] - mn[1]))
        eps = max(1e-12, 1e-7 * diag)

        def _degenerate(a: int, b: int) -> bool:
            if not (0 <= a < b < n):
                return False
            seg = pts[a:b + 1]
            d = np.diff(seg, axis=0)
            return float(np.sqrt((d * d).sum(axis=1)).sum()) <= eps

        last = idx[-1]
        kept = [idx[0]]
        for j in idx[1:]:
            # Keep the true endpoint; drop an interior boundary coincident with the
            # previous kept one (it only bounds a collapsed segment).
            if j != last and _degenerate(kept[-1], j):
                continue
            kept.append(j)
        # If the final interval itself collapsed, drop the second-to-last boundary
        # so the endpoint is preserved but the phantom tail segment is not created.
        while len(kept) >= 3 and _degenerate(kept[-2], kept[-1]):
            kept.pop(-2)
        return kept

    def update_file_segments_from_indices(self, split_indices: list[int],
                                          points=None):
        """Rebuild file-type segments from split indices, preserving curve segments.

        When an existing BY-NODE segment is split, its node count is redistributed
        across the resulting sub-segments in proportion to arc length so the point
        DENSITY is preserved — instead of every sub-segment inheriting the full
        count, which over-densified short pieces (#1). Distance-based ('spacing')
        segments need no redistribution: the same spacing already yields uniform
        density. ``points`` is the geometry's (N, 2) coordinates; when omitted,
        index span is used as a length proxy."""
        # Drop any degenerate (coincident-endpoint) boundary first so no rebuild
        # path can create/resurrect a phantom zero-length edge (see docstring).
        split_indices = self.prune_degenerate_splits(split_indices, points)
        curve_segs = [s for s in self.segments if s.type == "curve"]

        # Build a map of (start, end) → existing file segment so we preserve settings
        existing_map: dict[tuple, SegmentModel] = {}
        for s in self.segments:
            if s.type == "file":
                existing_map[(s.start_index, s.end_index)] = s

        def _arc_len(a: int, b: int) -> float:
            """Arc length of the point range [a, b], or index span as a fallback."""
            if a >= b:
                return 0.0
            if points is not None and 0 <= a < b < len(points):
                import numpy as np
                seg = np.asarray(points[a:b + 1], dtype=float)
                d = np.diff(seg, axis=0)
                return float(np.sqrt((d * d).sum(axis=1)).sum())
            return float(b - a)

        # Phantom-bridge guard (item: Remove Edge / arc Convert-to-Discrete): after
        # removing a MIDDLE file segment the two survivors become index-adjacent
        # (S, S+1) across the hole they used to fill, and appending a disjoint piece
        # (a converted free-standing arc) leaves the base end index-adjacent to the
        # new range's start. Either way `split_indices` gains a consecutive pair that
        # bridges a discontinuity — a 1-edge segment that no Remove can delete and
        # every rebuild resurrects. It is NOT coincident (prune_degenerate_splits
        # can't see it), but it is distinguishable: a genuine split's sub-pairs
        # always lie WITHIN their parent's span, whereas a bridge matches no existing
        # segment and overlaps none. Drop such adjacent, no-overlap pairs — but only
        # on a real REBUILD of the current segmentation (some pair still lands on an
        # existing segment); on a fresh build / geometry swap `existing_map` is empty
        # or irrelevant, so keep every pair.
        def _overlaps_existing(a: int, b: int) -> bool:
            for (old_s, old_e) in existing_map:
                if max(0, min(b, old_e) - max(a, old_s)) > 0:
                    return True
            return False

        pairs = [(split_indices[i], split_indices[i + 1])
                 for i in range(len(split_indices) - 1)]
        is_rebuild = bool(existing_map) and any(
            (a, b) in existing_map or _overlaps_existing(a, b) for a, b in pairs)

        new_file_segs: list[SegmentModel] = []
        for i in range(len(split_indices) - 1):
            start, end = split_indices[i], split_indices[i + 1]
            key = (start, end)
            if key in existing_map:
                seg = existing_map[key]
                seg.id = i + 1
            else:
                # Try to inherit settings from most-overlapping old segment
                best_overlap = 0
                best_seg = None
                for (old_s, old_e), old_seg in existing_map.items():
                    overlap = max(0, min(end, old_e) - max(start, old_s))
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_seg = old_seg
                # A bridge across a removed segment / disjoint-append boundary.
                if is_rebuild and best_overlap == 0 and (end - start) == 1:
                    continue
                seg = SegmentModel(i + 1, start, end)
                if best_seg:
                    seg.strategy = best_seg.strategy
                    seg.parameters = copy.deepcopy(best_seg.parameters)
                    seg.match_previous = best_seg.match_previous
                    # By-node count → scale to this piece's share of the parent
                    # segment's arc length, keeping the original point density.
                    if "spacing" not in seg.parameters and "n_points" in seg.parameters:
                        n_old = best_seg.parameters.get("n_points", 50)
                        L_old = _arc_len(best_seg.start_index, best_seg.end_index)
                        if L_old > 0:
                            share = _arc_len(start, end) / L_old
                            seg.parameters["n_points"] = max(2, int(round(n_old * share)))
            new_file_segs.append(seg)

        # Contiguous ids (a dropped phantom bridge would otherwise gap them).
        for k, s in enumerate(new_file_segs):
            s.id = k + 1
        self.segments = new_file_segs + curve_segs

    def renumber_segments(self):
        """Assign contiguous 1..N ids to every segment in list order.

        Discrete (file) and analytic (curve) edges share one running sequence,
        so the edge list / ids never gap or jump (e.g. to the old 10001 range)
        after add / delete / transform."""
        for i, seg in enumerate(self.segments):
            seg.id = i + 1
        self._next_curve_id = len(self.segments) + 1

    def get_segment(self, index: int) -> SegmentModel | None:
        if 0 <= index < len(self.segments):
            return self.segments[index]
        return None

    def add_curve_segment(self) -> SegmentModel:
        new_id = self._next_curve_id
        self._next_curve_id += 1
        seg = SegmentModel(new_id, -1, -1)
        seg.type = "curve"
        seg.curve_type = "line"
        seg.curve_mode = "parametric"
        self.segments.append(seg)
        return seg

    def remove_segment(self, index: int):
        if 0 <= index < len(self.segments):
            self.segments.pop(index)
            file_idx = 1
            for s in self.segments:
                if s.type == "file":
                    s.id = file_idx
                    file_idx += 1

    def get_split_indices_from_file_segments(self) -> list[int]:
        """Reconstruct split_indices from file-type segments."""
        indices: set[int] = set()
        for seg in self.segments:
            if seg.type == "file":
                indices.add(seg.start_index)
                indices.add(seg.end_index)
        return sorted(indices)

    # ── Closure ───────────────────────────────────────────────────────────

    def resolve_closure(self, points) -> bool:
        """Refresh the effective ``is_closed`` from ``closed_mode`` + geometry.

        "auto" derives closure from the points (GeometryService.detect_closed);
        "closed"/"open" force it. Returns the resolved value. Call whenever the
        mode or the geometry changes (the render funnel does this)."""
        if self.closed_mode == "closed":
            self.is_closed = True
        elif self.closed_mode == "open":
            self.is_closed = False
        else:  # "auto"
            from app.services.geometry_service import GeometryService
            self.is_closed = GeometryService.detect_closed(points)
        return self.is_closed

    # ── JSON I/O ──────────────────────────────────────────────────────────

    @staticmethod
    def migrate_config(config: dict) -> dict:
        """Upgrade an older config dict to the current CONFIG_FORMAT_VERSION.

        Extension point for backward-compatible schema migration. Version is
        read explicitly (a *missing* ``format_version`` means a legacy v0 file,
        NOT "current"), then each older version is upgraded field-by-field
        through this dispatch. Only v0->v1 exists today; add an ``if v < N``
        block here when the schema changes.

        A file NEWER than this build is left as-is (callers should surface a
        read-only warning that some settings may be ignored)."""
        v = int(config.get("format_version", 0))
        if v >= CONFIG_FORMAT_VERSION:
            return config
        data = copy.deepcopy(config)
        # v0 -> v1: v0 files predate an explicit version field; nothing about the
        # field layout changed, so the upgrade is just to stamp the version.
        if v < 1:
            v = 1
        # v1 -> v2: added closed_mode (auto/closed/open). Older files carry only
        # the is_closed bool; map it to a manual mode so they behave unchanged.
        if v < 2:
            data.setdefault("closed_mode", _legacy_closed_mode(data))
            v = 2
        data["format_version"] = CONFIG_FORMAT_VERSION
        return data

    def load_from_config(self, config: dict):
        config = self.migrate_config(config)
        self.input_file = config.get("input_file", "")
        self.output_file = config.get("output_file", "")
        # A saved config expresses explicit intent → manual mode. Missing
        # closed_mode (legacy) maps from the is_closed bool.
        self.closed_mode = config.get("closed_mode", _legacy_closed_mode(config))
        self.is_closed = config.get("is_closed", True)
        self.global_spline = config.get("global_spline", False)
        self.transform = copy.deepcopy(config.get("transform", None))

        self.segments = []
        for i, sj in enumerate(config.get("segments", [])):
            seg = SegmentModel.from_dict(i + 1, sj)
            self.segments.append(seg)

        # All edges share one contiguous 1..N numbering (in list order).
        self.renumber_segments()

    def export_config(self, filepath: str, extra: dict | None = None):
        # Keep exported ids consistent with the (contiguous) edge numbering.
        self.renumber_segments()
        config: dict = {
            "format_version": CONFIG_FORMAT_VERSION,
            "input_file": self.input_file,
            "output_file": self.output_file,
            "closed_mode": self.closed_mode,
            # Resolved value kept for forward-compat (older builds read this).
            "is_closed": self.is_closed,
            "segments": [seg.to_dict() for seg in self.segments],
        }
        if self.global_spline:
            config["global_spline"] = True
        if self.transform:
            config["transform"] = copy.deepcopy(self.transform)
        # Transient, run-specific keys (e.g. preview_markers) that should not be
        # persisted to user-saved configs.
        if extra:
            config.update(extra)

        with open(filepath, "w") as f:
            json.dump(config, f, indent=2)
