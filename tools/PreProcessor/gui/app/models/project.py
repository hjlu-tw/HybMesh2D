from __future__ import annotations
import json
import copy
from app.models.segment import SegmentModel


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

    def update_file_segments_from_indices(self, split_indices: list[int]):
        """Rebuild file-type segments from split indices, preserving curve segments."""
        curve_segs = [s for s in self.segments if s.type == "curve"]

        # Build a map of (start, end) → existing file segment so we preserve settings
        existing_map: dict[tuple, SegmentModel] = {}
        for s in self.segments:
            if s.type == "file":
                existing_map[(s.start_index, s.end_index)] = s

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
            new_file_segs.append(seg)

        self.segments = new_file_segs + curve_segs

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

    def load_from_config(self, config: dict):
        self.input_file = config.get("input_file", "")
        self.output_file = config.get("output_file", "")
        self.is_closed = config.get("is_closed", True)
        self.global_spline = config.get("global_spline", False)
        self.transform = copy.deepcopy(config.get("transform", None))

        self.segments = []
        for i, sj in enumerate(config.get("segments", [])):
            seg = SegmentModel.from_dict(i + 1, sj)
            self.segments.append(seg)

        # Fix curve segment IDs if they are < 10000 (old format) to avoid conflicts
        next_curve_id = 10001
        used_curve_ids = set()
        for seg in self.segments:
            if seg.type == "curve":
                if seg.id < 10000:
                    seg.id = next_curve_id
                    next_curve_id += 1
                else:
                    used_curve_ids.add(seg.id)

        if used_curve_ids:
            self._next_curve_id = max(used_curve_ids) + 1
        else:
            self._next_curve_id = next_curve_id

        # Renumber only file segments to ensure they are 1..N contiguous
        file_idx = 1
        for seg in self.segments:
            if seg.type == "file":
                seg.id = file_idx
                file_idx += 1

    def export_config(self, filepath: str):
        config: dict = {
            "input_file": self.input_file,
            "output_file": self.output_file,
            "is_closed": self.is_closed,
            "segments": [seg.to_dict() for seg in self.segments],
        }
        if self.global_spline:
            config["global_spline"] = True
        if self.transform:
            config["transform"] = copy.deepcopy(self.transform)

        with open(filepath, "w") as f:
            json.dump(config, f, indent=2)
