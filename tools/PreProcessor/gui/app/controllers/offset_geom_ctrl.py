"""Derive a geometry by offsetting one the user already drew, and regenerate it.

#152, parent #150. The CAD-stage half of the offset feature: the LAW is
`app/services/geometry_offset.py`, which is Qt-free and is the ONE owner, and
nothing here re-derives any part of it. What lives here is which points a session
hands that law, what the new session inherits from its source, and the two
refusals a user can meet.

WHAT THE OFFSET INHERITS, AND WHY IT IS A COPY RATHER THAN A DERIVATION. The new
geometry takes the source's split indices and a deep copy of its FILE segments
verbatim, so its segment ids, boundaries, strategies and per-segment facts are the
source's. That is what "segmented exactly as its source" means, and it is what
makes a stable segment id on the offset mean the same thing as the id it mirrors —
the property a topology that pairs two outlines segment-for-segment relies on. It
is a copy and not a re-segmentation because re-segmenting is a second answer to a
question the source has already answered, and two answers drift.

ONLY THE DISCRETE GEOMETRY IS OFFSET. The source's analytic (curve) edges are not
carried: the result is an ordinary discrete geometry, one point array, which is
what keeps the resampler's shape-parity surface from growing a new curve type. A
source with no discrete points at all is REFUSED by name and pointed at Convert to
Discrete, rather than silently offsetting nothing.

REGENERATION IS EXPLICIT, AND ITS SOURCE IS FOUND BY NAME. The record carries the
source's display name and its path (`app/models/derived_geometry.py`); the source
is the OPEN session matching one of them, because the thing being offset is the
geometry as it is now — a source edited but not yet exported lives only in its
session. A record whose source is not open is refused NAMING it, never skipped and
never resolved to whatever is nearest: a ring silently re-derived from the wrong
body is the failure this refusal exists for.
"""
from __future__ import annotations

import copy
import os

import numpy as np
from PyQt6.QtWidgets import QDialog

from app.models.derived_geometry import DerivedOffset
from app.services.geometry_offset import OffsetRefused, offset_points
from app.services.logging_setup import get_logger
from app.utils import report_info, report_warning
from app.views.offset_dialog import OffsetGeometryDialog

_log = get_logger(__name__)


class OffsetGeomControllerMixin:
    """CAD ▸ Offset Geometry… and CAD ▸ Regenerate Offset."""

    # ── what a session offers the law ─────────────────────────────────────

    @staticmethod
    def _offset_source_points(session):
        """The discrete point array to offset, or ``None`` when there is none."""
        pts = getattr(session, "original_points", None)
        if pts is None:
            return None
        arr = np.asarray(pts, dtype=float)
        if arr.ndim != 2 or len(arr) < 2:
            return None
        return arr

    @staticmethod
    def _offset_segmentation(source):
        """The split indices and FILE segments an offset inherits from ``source``."""
        splits = list(source.split_indices)
        segs = [copy.deepcopy(s) for s in source.project_model.segments
                if s.type == "file"]
        return splits, segs

    def _derive_offset_points(self, source, distance: float, what: str):
        """Run the law for ``source``; log + report a refusal and return ``None``."""
        pts = self._offset_source_points(source)
        if pts is None:
            self.log("[Offset] [ERROR] '%s' has no discrete geometry to offset; "
                     "use Convert to Discrete on its analytic edges first."
                     % source.display_name.lstrip("*"))
            report_info(
                self.main_window, "Offset Geometry",
                "'%s' has no discrete geometry to offset."
                % source.display_name.lstrip("*"),
                detail="An offset mirrors a point array. Select the edge and use "
                       "Convert to Discrete, then offset the geometry.")
            return None
        closed = source.project_model.resolve_closure(pts)
        try:
            return offset_points(pts, distance, closed)
        except (OffsetRefused, ValueError) as e:
            # NOT trimmed and NOT clamped: a trimmed offset is a different curve
            # and would no longer carry its source's segmentation. The number the
            # refusal names is the whole point of showing it.
            _log.debug("offset refused for %s", what, exc_info=True)
            self.log("[Offset] [ERROR] %s: %s" % (what, e))
            report_warning(self.main_window, "Offset Refused", str(e),
                           detail="Nothing was changed. The distance named above "
                                  "is the largest that works on that side.")
            return None

    # ── create ────────────────────────────────────────────────────────────

    def offset_active_geometry(self):
        """Derive a new geometry from the active one, at a distance and a side."""
        source = self.active_session()
        if source is None:
            self.log("[Offset] No active geometry to offset.")
            return
        pts = self._offset_source_points(source)
        if pts is None:
            self._derive_offset_points(source, 0.0, "offset")   # says it, once
            return
        name = source.display_name.lstrip("*")
        closed = source.project_model.resolve_closure(pts)
        span = float(np.hypot(*(pts.max(axis=0) - pts.min(axis=0))))
        dlg = OffsetGeometryDialog(
            name, closed, unit=source.project_model.length_unit,
            suggested=0.05 * span, parent=self.main_window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        distance = dlg.signed_distance()
        if distance == 0.0:
            self.log("[Offset] A zero distance would duplicate '%s'; nothing done."
                     % name)
            return
        self.create_offset_geometry(source, distance)

    def create_offset_geometry(self, source, distance: float):
        """Build the derived session. Returns it, or ``None`` when refused."""
        name = source.display_name.lstrip("*")
        out = self._derive_offset_points(
            source, distance, "offsetting '%s' by %g" % (name, distance))
        if out is None:
            return None
        splits, segs = self._offset_segmentation(source)
        new = self._new_session("")
        new.original_points = out
        new.split_indices = splits
        pm, src_pm = new.project_model, source.project_model
        pm.segments = segs
        pm.renumber_segments()
        pm.closed_mode = src_pm.closed_mode
        pm.is_closed = src_pm.is_closed
        pm.length_unit = src_pm.length_unit
        pm.length_unit_metres = src_pm.length_unit_metres
        pm.length_unit_name = src_pm.length_unit_name
        pm.derived_from = DerivedOffset(
            source_name=name, source_file=source.file_path, distance=distance)
        # The name is where a user meets the record first, months later, without
        # opening anything: the tab says what this geometry is. The decimal point
        # is written `p` because a display name is `os.path.splitext`-ed wherever
        # one becomes a file stem (`controllers/pipeline_io_ctrl.py`), and
        # "body_offset+0.2" would come back as "body_offset+0".
        stem = os.path.splitext(name)[0] or "geometry"
        new.display_name = "%s_offset%s" % (
            stem, ("%+g" % distance).replace(".", "p"))
        new.mark_modified()
        self._refresh_segment_list()
        self._sync_geometry_list()
        self.redraw_canvas(announce=False)
        self.log("[Offset] Created '%s': %s, %d points, %d segments."
                 % (new.display_name.lstrip("*"), pm.derived_from.describe(),
                    len(out), len(pm.segments)))
        return new

    # ── regenerate ────────────────────────────────────────────────────────

    def find_offset_source(self, record: DerivedOffset, exclude=None):
        """The OPEN session a record points at, or ``None``.

        By display name first — that is what the user named and what a refusal
        prints — then by file path, which survives a rename.
        """
        if record is None:
            return None
        for s in self.sessions:
            if s is exclude:
                continue
            if s.display_name.lstrip("*") == record.source_name:
                return s
        if record.source_file:
            want = os.path.abspath(record.source_file)
            for s in self.sessions:
                if s is exclude:
                    continue
                if s.file_path and os.path.abspath(s.file_path) == want:
                    return s
        return None

    def regenerate_offset_geometry(self):
        """Re-derive the active geometry from its recorded source, undoably."""
        session = self.active_session()
        if session is None:
            self.log("[Offset] No active geometry.")
            return
        name = session.display_name.lstrip("*")
        record = session.project_model.derived_from
        if record is None:
            self.log("[Offset] '%s' is not a derived geometry; there is nothing "
                     "to regenerate." % name)
            report_info(self.main_window, "Regenerate Offset",
                        "'%s' was not derived from another geometry." % name,
                        detail="Use CAD ▸ Offset Geometry… to create one.")
            return
        source = self.find_offset_source(record, exclude=session)
        if source is None:
            # Named, never skipped and never filled in from whatever is nearest.
            msg = ("cannot regenerate '%s': its source geometry '%s' is not open. "
                   "Open it and try again." % (name, record.source_name))
            self.log("[Offset] [ERROR] %s" % msg)
            report_warning(self.main_window, "Regenerate Offset",
                           msg[0].upper() + msg[1:],
                           detail="Nothing was changed. A derived geometry is "
                                  "never re-derived from a different source.")
            return
        out = self._derive_offset_points(
            source, record.distance,
            "regenerating '%s' from '%s'" % (name, record.source_name))
        if out is None:
            return
        splits, segs = self._offset_segmentation(source)
        from app.commands.derived_cmds import RegenerateOffsetCmd

        def _refresh():
            self._refresh_segment_list()
            self._sync_geometry_list()
            self.redraw_canvas(announce=False)

        cmd = RegenerateOffsetCmd(session, out, splits, segs, _refresh)
        session.command_history.execute(cmd)
        self._update_undo_redo_buttons(session)
        self.log("[Offset] Regenerated '%s' from '%s': %s, %d points, %d segments."
                 % (name, record.source_name, record.describe(), len(out),
                    len(session.project_model.segments)))
