from __future__ import annotations
import json
import copy
from app.models.segment import SegmentModel

# Bump when the exported JSON config schema changes in a backward-incompatible
# way. Readers should tolerate a missing field (treated as version 0/legacy)
# and warn — but not crash — when the file version is newer than they support.
CONFIG_FORMAT_VERSION = 1


class ProjectModel:
    """Holds all data for one geometry file's resampling project."""

    def __init__(self):
        self.input_file: str = ""
        self.output_file: str = ""
        self.is_closed: bool = True
        self.segments: list[SegmentModel] = []
        self._next_curve_id: int = 10001

        # Advanced backend settings
        self.global_spline: bool = False
        self.transform: dict | None = None  # scale, rotate, translate

    # ── Segment management ────────────────────────────────────────────────

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

        new_file_segs: list[SegmentModel] = []
        for i in range(len(split_indices) - 1):
            start, end = split_indices[i], split_indices[i + 1]
            key = (start, end)
            if key in existing_map:
                seg = existing_map[key]
                seg.id = i + 1
            else:
                seg = SegmentModel(i + 1, start, end)
                # Try to inherit settings from most-overlapping old segment
                best_overlap = 0
                best_seg = None
                for (old_s, old_e), old_seg in existing_map.items():
                    overlap = max(0, min(end, old_e) - max(start, old_s))
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_seg = old_seg
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
        data["format_version"] = CONFIG_FORMAT_VERSION
        return data

    def load_from_config(self, config: dict):
        config = self.migrate_config(config)
        self.input_file = config.get("input_file", "")
        self.output_file = config.get("output_file", "")
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
