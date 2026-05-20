import json
from app.models.segment import SegmentModel

class ProjectModel:
    def __init__(self):
        self.input_file = ""
        self.output_file = "resampled_output.dat"
        self.is_closed = True
        self.segments = []

    def update_segments_from_indices(self, split_indices):
        self.segments = []
        # split_indices is expected to be sorted, e.g., [0, 15, 30]
        for i in range(len(split_indices) - 1):
            start = split_indices[i]
            end = split_indices[i+1]
            seg = SegmentModel(i + 1, start, end)
            self.segments.append(seg)

    def get_segment(self, index):
        if 0 <= index < len(self.segments):
            return self.segments[index]
        return None

    def export_config(self, filepath):
        config = {
            "input_file": self.input_file,
            "output_file": self.output_file,
            "is_closed": self.is_closed,
            "segments": [seg.to_dict() for seg in self.segments]
        }
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)
