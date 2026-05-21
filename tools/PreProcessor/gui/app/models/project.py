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
            new_file_segs.append(seg)

        # Renumber curve segments
        all_segs = new_file_segs + curve_segs
        for i, seg in enumerate(all_segs):
            seg.id = i + 1
        self.segments = all_segs

    def get_segment(self, index: int) -> SegmentModel | None:
        if 0 <= index < len(self.segments):
            return self.segments[index]
        return None

    def add_curve_segment(self) -> SegmentModel:
        new_id = len(self.segments) + 1
        seg = SegmentModel(new_id, -1, -1)
        seg.type = "curve"
        seg.curve_mode = "parametric"
        self.segments.append(seg)
        return seg

    def remove_segment(self, index: int):
        if 0 <= index < len(self.segments):
            self.segments.pop(index)
            for i, s in enumerate(self.segments):
                s.id = i + 1

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
