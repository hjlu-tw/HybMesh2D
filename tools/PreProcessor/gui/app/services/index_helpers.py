from __future__ import annotations
import numpy as np
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.session import GeometrySession
from app.models.segment import SegmentModel

def remove_points_and_adjust_indices(session: GeometrySession, seg: SegmentModel):
    """
    Remove points belonging to segment from session.original_points 
    and adjust all segment indices and split indices accordingly.
    """
    if seg.type != "file" or session.original_points is None:
        return

    # Determine shared boundaries
    S = seg.start_index
    E = seg.end_index

    s_shared = False
    e_shared = False
    for other in session.project_model.segments:
        if other is not seg and other.type == "file":
            if other.start_index == S or other.end_index == S:
                s_shared = True
            if other.start_index == E or other.end_index == E:
                e_shared = True

    del_start = S + 1 if s_shared else S
    del_end = E - 1 if e_shared else E

    if del_start <= del_end:
        num_deleted = del_end - del_start + 1

        # Delete points from original_points
        session.original_points = np.delete(
            session.original_points, slice(del_start, del_end + 1), axis=0)

        # Adjust split indices
        new_splits = []
        for idx in session.split_indices:
            if idx < del_start:
                new_splits.append(idx)
            elif idx > del_end:
                new_splits.append(idx - num_deleted)
        session.split_indices = sorted(list(set(new_splits)))

        # Adjust start/end index of other file segments
        for other in session.project_model.segments:
            if other is not seg and other.type == "file":
                if other.start_index > del_end:
                    other.start_index -= num_deleted
                if other.end_index > del_end:
                    other.end_index -= num_deleted
