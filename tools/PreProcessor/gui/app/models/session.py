from __future__ import annotations
import os
import numpy as np
from app.models.project import ProjectModel
from app.commands.base import CommandHistory
from app.models.mesh_config import MeshConfig
from app.models.vtk_mesh import VTKMesh

# Colour palette cycling per session (bright on dark canvas)
SESSION_COLORS = [
    '#64B5F6',  # blue
    '#81C784',  # green
    '#FF8A65',  # orange-red
    '#FFD54F',  # amber
    '#CE93D8',  # purple
    '#4DD0E1',  # cyan
    '#F06292',  # pink
    '#A5D6A7',  # light green
    '#FFF176',  # yellow
    '#80DEEA',  # light cyan
    '#FFCC80',  # light orange
    '#CF94DA',  # light purple
]


class GeometrySession:
    """Holds all mutable state for one opened geometry (= one tab)."""

    _counter: int = 0  # class-level counter for unique IDs

    def __init__(self, file_path: str = ""):
        GeometrySession._counter += 1
        self.session_id: int = GeometrySession._counter

        self.file_path: str = file_path
        self._display_name: str = ""
        self.original_points: np.ndarray | None = None
        self.split_indices: list[int] = []
        self.selected_point_idx: int | None = None
        self.current_segment_idx: int = -1
        self.is_geometry_modified: bool = False
        self.resampled_points: np.ndarray | None = None
        # Exact piece-break indices from the last preview (nan-separated output);
        # used to break the resampled polyline at disconnected pieces.
        self.resampled_gaps: set | None = None

        self.project_model: ProjectModel = ProjectModel()
        self.command_history: CommandHistory = CommandHistory()
        self.is_visible: bool = True
        self.param_snapshot: dict = {}
        self.segment_state_snapshot: dict = {}
        self.mesh_config: MeshConfig = MeshConfig()
        self.vtk_mesh: VTKMesh | None = None
        self.vtk_path: str = ""

        # Colour assigned from palette (set by controller)
        self.color: str = SESSION_COLORS[
            (self.session_id - 1) % len(SESSION_COLORS)]

    # ── Display helpers ───────────────────────────────────────────────────

    @property
    def display_name(self) -> str:
        if self._display_name:
            base = self._display_name
        elif not self.file_path:
            base = "Untitled"
        else:
            base = os.path.basename(self.file_path)
        return f"*{base}" if self.is_geometry_modified else base

    @display_name.setter
    def display_name(self, value: str):
        self._display_name = value.lstrip('*')

    @property
    def default_output_path(self) -> str:
        if not self.file_path:
            return "output_resampled.dat"
        stem, _ = os.path.splitext(self.file_path)
        return f"{stem}_resampled.dat"

    def mark_modified(self):
        self.is_geometry_modified = True
