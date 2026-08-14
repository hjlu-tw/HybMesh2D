"""Auto-detect / feature-split logic for AppController, split out of
segment_ctrl as a sibling mixin (behaviour unchanged): sharp-angle corner
detection that creates segment splits. Composed into AppController alongside
SegmentControllerMixin and resolves through the same flat self (active_session,
main_window, _apply_geometry_update, per-session command_history)."""
from __future__ import annotations
import numpy as np
from app.commands.split_cmds import AutoDetectSplitCmd
from app.commands.segment_cmds import CreateSegmentsFromIndicesCmd
from app.services.geometry_service import GeometryService


class SegmentAutoDetectControllerMixin:
    """Auto-detect segment boundaries from sharp angles (moved from SegmentControllerMixin)."""

    def auto_detect_segments(self, angle_threshold_deg: float = 30.0):
        """Auto-detect segment boundaries based on sharp angles."""
        session = self.active_session()
        if not session or session.original_points is None:
            self.log("No geometry loaded.")
            return

        points = session.original_points.copy()
        pm = session.project_model
        if pm.is_closed and len(points) > 0:
            if not np.allclose(points[0], points[-1]):
                points = np.vstack((points, points[0]))

        new_indices = self._auto_detect_features(points, angle_threshold_deg)
        cmd = AutoDetectSplitCmd(
            session, new_indices,
            refresh_cb=lambda: self._apply_geometry_update(session))
        session.command_history.execute(cmd)
        self.log(
            f"Auto-detected {len(new_indices) - 1} edges based on sharp angles (threshold: {angle_threshold_deg}°).")

    def auto_detect_segments_from_button(self):
        """Slot for the Auto Detect Segments button."""
        session = self.active_session()
        if not session:
            return

        seg_idx = session.current_segment_idx
        seg = None
        if 0 <= seg_idx < len(session.project_model.segments):
            seg = session.project_model.get_segment(seg_idx)

        sb = self.main_window.sidebar_view
        angle_threshold = sb.auto_split_angle_sb.value()

        if seg:
            if seg.type == "file" and session.original_points is None:
                self.log("No geometry loaded for file segment.")
                return

            new_indices = self._auto_detect_features_for_segment(seg_idx, angle_threshold)
            if len(new_indices) >= 2:
                cmd = CreateSegmentsFromIndicesCmd(
                    session, seg_idx, new_indices,
                    refresh_cb=lambda: self._apply_geometry_update(session))
                session.command_history.execute(cmd)
                self.log(
                    f"Auto-detected {len(new_indices) - 1} sub-edges for edge {seg.id} (threshold: {angle_threshold}°).")
            else:
                self.log("No sharp corners detected for selected edge.")
            return

        if session.original_points is None:
            self.log("No geometry loaded.")
            return
        self.auto_detect_segments(angle_threshold_deg=angle_threshold)

    def _auto_detect_features(self, points: np.ndarray,
                              angle_threshold_deg: float = 30.0) -> list[int]:
        return GeometryService.auto_detect_features(points, angle_threshold_deg)

    def _auto_detect_features_for_segment(self, segment_idx: int, angle_threshold_deg: float = 30.0) -> list[int]:
        session = self.active_session()
        if not session:
            return []

        seg = session.project_model.get_segment(segment_idx)
        if not seg:
            return []

        if seg.type == "file":
            if session.original_points is None:
                return []
            pts = session.original_points[seg.start_index:seg.end_index + 1]
            local_splits = self._auto_detect_features(pts, angle_threshold_deg)
            return [seg.start_index + i for i in local_splits]
        else:
            n = seg.parameters.get("n_points", 100)
            xs, ys = GeometryService.compute_curve_preview_pts(seg, n, session.original_points)
            if xs is None or len(xs) < 2:
                return []
            pts = np.column_stack([xs, ys])
            return self._auto_detect_features(pts, angle_threshold_deg)
