"""Owner of the edge currently being edited — the state a modeless edit holds.

Drawing a new analytic edge, or double-clicking an existing one, opens a
*modeless* session: a numeric dialog and a set of draggable canvas handles both
bound live to one segment, which is only committed when the user presses
**Create Edge** / **Apply** and reverted when they press **Cancel**.

That session used to be five attributes on ``AppController`` — the segment, the
dialog, the create/edit flag and two snapshots — declared in one file, begun in a
second and committed or cancelled in a third, with "live or absent" enforced only
by every reader remembering to test the segment for ``None``. This module holds
them instead, behind verbs, so the lifecycle can be driven (and therefore tested)
without a canvas, a dialog or a running Qt event loop.

Two rules make that possible and are the reason this file sits under
``services/``:

* **No Qt.** The dialog is held as an OPAQUE reference — this module stores it
  and hands it back, and never calls a method on it. Whatever has to be *asked*
  of the dialog (a polygon's open/closed toggle) is read by the caller and passed
  in as a value, so nothing here depends on the widget's interface.
* **No canvas, no command history, no logging.** ``commit()`` and ``cancel()``
  end the session and return an :class:`EditOutcome` describing what the caller
  must now do; deciding whether that becomes an ``AddCurveSegmentCmd`` or an
  ``UpdateSegmentStateCmd`` stays with the controller, which is the layer that
  owns the undo stack.

The revert itself DOES live here, because it is the other half of the snapshot
this module took: a cancelled edit restores the parameters and — for a polygon —
the ``closed`` flag the dialog may have toggled.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class EditOutcome:
    """What a finished edit session leaves for the caller to act on.

    ``seg`` is the segment that was being edited, ``is_new`` says whether it was
    being created (commit → add it) or edited in place (commit → record the
    change against ``orig_state``, the ``to_dict()`` taken before the edit).
    ``reverted`` is True when :meth:`EdgeEditSession.cancel` actually put the
    shape back — cancelling a *creation* has nothing to revert.
    """

    seg: Any
    is_new: bool
    orig_state: Optional[dict] = None
    reverted: bool = False


class EdgeEditSession:
    """The analytic edge being created or edited, and its two snapshots."""

    def __init__(self):
        self._seg = None
        self._dialog = None
        self._is_new = True
        self._orig_params = None
        self._orig_state = None

    # ── Questions ────────────────────────────────────────────────────────
    def is_active(self) -> bool:
        """True while an edit session is live (a segment is being edited)."""
        return self._seg is not None

    @property
    def segment(self):
        """The edge being edited, or None. Callers exclude it from snap targets
        so a dragged control point does not target its own endpoints."""
        return self._seg

    @property
    def dialog(self):
        """The modeless numeric dialog, held opaquely; None if not attached."""
        return self._dialog

    @property
    def is_new(self) -> bool:
        return self._is_new

    # ── Lifecycle ────────────────────────────────────────────────────────
    def begin(self, seg, is_new: bool = True):
        """Start editing ``seg``. Returns the segment, for use at the call site.

        The parameters are deep-copied so cancelling an edit reverts nested
        values (a polygon's vertex list) rather than the outer dict alone; the
        full ``to_dict()`` is kept separately because committing an edit has to
        be undoable, and undo needs the state, not just the parameters.
        """
        self._seg = seg
        self._is_new = bool(is_new)
        self._orig_params = None if is_new else copy.deepcopy(seg.parameters)
        self._orig_state = None if is_new else seg.to_dict()
        self._dialog = None
        return seg

    def attach_dialog(self, dlg):
        """Hold the modeless dialog for the duration of the session."""
        self._dialog = dlg

    def update(self, params: dict, n_points, closed=None) -> bool:
        """Apply a dialog edit to the live segment. False if none is live.

        Two rules the numeric form leaves to whoever applies its values:

        * a polygon switched back to *By Node Count* stops sending ``spacing``,
          so a stale key must be dropped or the backend keeps resampling by
          distance (mirrors the sidebar's own apply path);
        * the open/closed toggle is not part of ``params``, so it is passed in
          separately and mirrored onto the segment — and only for a polygon,
          which is the only shape that reads the flag.
        """
        seg = self._seg
        if seg is None:
            return False
        seg.parameters.update(params)
        seg.parameters["n_points"] = n_points
        is_polygon = getattr(seg, "curve_type", "") == "polygon"
        if is_polygon and "spacing" not in params:
            seg.parameters.pop("spacing", None)
        if is_polygon and closed is not None:
            seg.closed = bool(closed)
        return True

    def commit(self) -> Optional[EditOutcome]:
        """End the session, keeping the edit. None if none was live."""
        if self._seg is None:
            self._reset()
            return None
        outcome = EditOutcome(self._seg, self._is_new, self._orig_state)
        self._reset()
        return outcome

    def cancel(self) -> Optional[EditOutcome]:
        """End the session, restoring an edited shape. None if none was live.

        Cancelling a *creation* reverts nothing — the edge was never added — so
        the outcome comes back with ``reverted=False`` and the caller simply
        drops the pending segment.
        """
        seg, is_new = self._seg, self._is_new
        orig_params, orig_state = self._orig_params, self._orig_state
        self._reset()
        if seg is None:
            return None
        reverted = False
        if (not is_new) and orig_params is not None:
            seg.parameters = orig_params
            if orig_state is not None and hasattr(seg, "closed"):
                seg.closed = bool(orig_state.get("closed", True))
            reverted = True
        return EditOutcome(seg, is_new, orig_state, reverted=reverted)

    def _reset(self):
        self._seg = None
        self._dialog = None
        self._is_new = True
        self._orig_params = None
        self._orig_state = None
