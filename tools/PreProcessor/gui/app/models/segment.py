class SegmentModel:
    def __init__(self, segment_id, start_index, end_index):
        self.id = segment_id
        self.type = "file"
        self.start_index = start_index
        self.end_index = end_index
        self.strategy = "uniform"
        self.parameters = {"n_points": 50}

    def update_strategy(self, new_strategy):
        self.strategy = new_strategy
        # Assign default parameters based on strategy
        if new_strategy == "uniform":
            self.parameters = {"n_points": 50}
        elif new_strategy == "tanh":
            self.parameters = {"n_points": 50, "intensity": 2.0}
        elif new_strategy == "cosine":
            self.parameters = {"n_points": 50}
        elif new_strategy == "curvature":
            self.parameters = {"n_points": 50, "sensitivity": 1.5, "max_angle": 15.0}
        elif new_strategy == "geometric":
            self.parameters = {"n_points": 50, "ratio": 1.2}

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "start_index": int(self.start_index),
            "end_index": int(self.end_index),
            "strategy": self.strategy,
            "parameters": self.parameters
        }
