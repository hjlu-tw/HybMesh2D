"""Command for the interactive endpoint weld tool (canvas red open-endpoint →
pick → snap onto another endpoint/vertex). Moving the picked endpoint's
underlying datum onto the target coincides the two ends so the boundary reads as
joined. Undo restores a full state snapshot (same pattern as the bake command).

The "connect a line" variant is NOT a command here: it reuses the normal
add-line create-edit flow (controller.on_shape_drawn), which is undoable on its
own commit."""
from __future__ import annotations
import numpy as np

from app.commands.segment_cmds import _snapshot_full_state, _restore_full_state
from app.models import shape_spec


class EndpointWeldCmd:
    """Move one open endpoint onto ``target`` (x, y).

    ``ref`` is the ``(kind, seg_idx, which)`` tuple produced by
    ``OpenEndpointControllerMixin._collect_open_endpoints`` — ``kind`` ∈
    {'file','polygon','other'}, ``which`` ∈ {'start','end'}.
    """

    def __init__(self, session, ref, target, refresh_cb):
        self.session = session
        self.ref = ref
        self.target = (float(target[0]), float(target[1]))
        self.refresh_cb = refresh_cb
        self._snap = _snapshot_full_state(session)

    def description(self) -> str:
        return "Weld open endpoint"

    def execute(self):
        kind, seg_idx, which = self.ref
        tx, ty = self.target
        if kind == "file":
            pts = self.session.original_points
            if pts is not None and len(pts) > 0:
                arr = np.array(pts, dtype=float, copy=True)
                arr[0 if which == "start" else -1] = [tx, ty]
                self.session.original_points = arr
                self.session.is_geometry_modified = True
        else:
            segs = self.session.project_model.segments
            if seg_idx is not None and 0 <= seg_idx < len(segs):
                seg = segs[seg_idx]
                if seg.type == "curve":
                    ct = seg.curve_type
                    bes = shape_spec.boundary_endpoints(ct, seg.parameters)
                    if bes:
                        hid = bes[0][0] if which == "start" else bes[-1][0]
                        shape_spec.apply_drag(ct, seg.parameters, hid, tx, ty)
                        self.session.is_geometry_modified = True
        self.refresh_cb()

    def undo(self):
        _restore_full_state(self.session, self._snap)
        self.refresh_cb()
