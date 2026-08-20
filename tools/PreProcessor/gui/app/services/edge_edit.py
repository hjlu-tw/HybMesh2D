"""Owner of the edge currently being edited — the state a modeless edit holds.

There are TWO edit kinds and this module owns both, because they are
alternatives: at most one may be live, and something has to be able to say so.

* **Analytic** — drawing a new arc/line/circle/polygon, or double-clicking an
  existing one. A numeric dialog and draggable canvas handles are both bound
  live to one segment, committed by **Create Edge** / **Apply** and reverted by
  **Cancel**.
* **Shape** — double-clicking an *imported* (discrete) edge opens the whole
  connected outline for editing by its corner vertices; every edge re-fits
  between its own two corners, so a corner two edges share redistributes both.
  Its arithmetic is :mod:`app.services.shape_refit`, kept separate because it is
  geometry rather than lifecycle, and pure.
* **Drag** — a control-point handle of an already-COMMITTED edge dragged on the
  canvas, with no dialog open. It is a third modality rather than a mode of the
  first two, which deliberately route handle drags away from it. Its whole job
  is to make one gesture — many move events — one undo step.

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
* **No canvas, no command history, no logging.** The ``commit``/``cancel`` verbs
  end the session and return an outcome describing what the caller must now do;
  deciding whether that becomes an ``AddCurveSegmentCmd``, a recorded
  ``UpdateSegmentStateCmd`` or a ``ReplaceGeometryPointsCmd`` stays with the
  controller, which is the layer that owns the undo stack.

The revert itself DOES live here, because it is the other half of the snapshot
this module took: a cancelled analytic edit restores the parameters and — for a
polygon — the ``closed`` flag the dialog may have toggled, and a cancelled shape
edit hands back the pristine points.

**An edit BELONGS to the CAD session it began in**, and that is not a detail.
The commit path used to resolve its target through ``active_session()`` — the
tab in front *now*, not the tab the edit began in — while nothing cancelled a
live edit when a tab was switched or closed. Both consequences were silent:
committing an edit looked the segment up in the wrong session, failed, and fell
back to matching by segment **id**, which is per-session (every
``ProjectModel._next_curve_id`` starts at 10001), so both tabs' first analytic
edge is 10001 and the edit landed on ANOTHER TAB'S edge — recording an undo
entry whose before-state came from one geometry and whose after-state came from
another; and committing a NEW edge added it to whichever tab was in front. So
every outcome carries its session, and the caller acts on THAT one.

**At most one edit is live, and the owner enforces it.** It used to be
convention: six call sites guard on ``_edit_in_progress()``, and a ``begin``
that slipped past them would overwrite the live edit's snapshots — after which a
Cancel restores the wrong shape. ``begin``/``begin_shape`` now REFUSE while
another edit is live, so the caller has to end the first one deliberately (the
Qt side asks the user first). Refusing is the backstop, not the interaction: a
module with no Qt cannot put up a prompt, and should not decide to.

The shape session also holds the CORNER POSITIONS rather than a live point
array: every re-fit recomputes from the pristine snapshot, so dragging never
accumulates transform onto transform and Cancel is exact rather than
approximate.

And the drag snapshot is a TRANSITION, not a nullable field cleared by
convention. It used to be ``AppController._drag_orig_state``: filled by the drag
handler on the first move event, and retired by the *selection/refresh
chokepoint* as a side effect, because a snapshot left over from a drag that
ended abnormally — its finished-event guard tripped, or the selection changed
mid-gesture — would otherwise be recorded against whichever segment happened to
be selected next, and undoing that would put the WRONG shape onto that edge. The
rule is now a property of the owner instead of a clearing call in an unrelated
method: a drag belongs to the segment it began on, and cannot be finished
against another.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from app.services.shape_refit import build_edge_specs, refit_shape

#: Prefix of a corner handle's id on the canvas. Emitted by ``handle_points``
#: and parsed by ``move_corner``, so the format lives in exactly one place.
_CORNER_PREFIX = "c"


@dataclass(frozen=True)
class EditOutcome:
    """What a finished edit session leaves for the caller to act on.

    ``seg`` is the segment that was being edited, ``is_new`` says whether it was
    being created (commit → add it) or edited in place (commit → record the
    change against ``orig_state``, the ``to_dict()`` taken before the edit).
    ``reverted`` is True when :meth:`EdgeEditSession.cancel` actually put the
    shape back — cancelling a *creation* has nothing to revert.

    ``session`` is the CAD session the edit BEGAN in, and is the one the caller
    must act on — never whichever tab happens to be in front when the dialog's
    signal arrives.
    """

    seg: Any
    is_new: bool
    orig_state: Optional[dict] = None
    reverted: bool = False
    session: Any = None


@dataclass(frozen=True)
class ShapeOutcome:
    """What a finished shape (imported-outline) edit leaves for the caller.

    ``orig`` is the pristine point array the session snapshotted, which the
    caller needs for BOTH endings: to restore on cancel, and — on commit — as
    the "before" half of the undoable geometry replacement. ``session`` is the
    CAD session the edit began in, for the same reason as on
    :class:`EditOutcome`.
    """

    seg: Any
    orig: Any
    session: Any = None


class EdgeEditSession:
    """The edge being edited: an analytic one, or an imported outline."""

    def __init__(self):
        self._seg = None
        self._dialog = None
        self._is_new = True
        self._orig_params = None
        self._orig_state = None
        self._session = None          # the CAD session this edit belongs to
        # Shape (imported-outline) edit.
        self._shape_seg = None
        self._shape_dialog = None
        self._shape_orig = None       # pristine points (revert + refit basis)
        self._shape_specs = None      # per-edge corner + interior index spans
        self._shape_corners = None    # sorted corner indices = handle order
        self._shape_pos = None        # {corner index: [x, y]} live positions
        self._shape_edge = None       # the double-clicked edge's two corners
        self._shape_session = None
        # Drag of a committed edge's handle: the segment it began on, and that
        # segment's state before the gesture started.
        self._drag_seg = None
        self._drag_state = None
        self._drag_session = None

    # ── Questions ────────────────────────────────────────────────────────
    def is_active(self) -> bool:
        """True while a modeless edit SESSION is live — the one question
        ``_edit_in_progress()`` asks, for either kind.

        A committed-edge drag is deliberately NOT one of them. It opens no
        dialog and holds nothing the user must confirm or cancel, and the
        callers that guard on this predicate — double-click to open an editor,
        canvas selection, the handle-drag router — must keep working *during* a
        drag. Folding the drag in here would make an ordinary reshape look like
        an open dialog and lock those out.
        """
        return self._seg is not None or self._shape_seg is not None

    @property
    def owning_session(self):
        """The CAD session the live EDIT belongs to (either kind), or None.

        A committed-edge drag is deliberately excluded: it is not a modal edit,
        and leaving its session drops it silently rather than asking.
        """
        if self._seg is not None:
            return self._session
        if self._shape_seg is not None:
            return self._shape_session
        return None

    def belongs_to(self, session) -> bool:
        """True when a live edit — of either kind — began in ``session``."""
        return session is not None and self.owning_session is session

    @property
    def active_segment(self):
        """The edge being edited, of whichever kind. Callers exclude it from the
        snap targets so a dragged control point cannot target its own points."""
        return self._seg if self._seg is not None else self._shape_seg

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
    def begin(self, seg, is_new: bool = True, session=None) -> bool:
        """Start editing ``seg`` in ``session``. False if REFUSED.

        Refused when another edit is already live: overwriting its snapshots is
        how a later Cancel comes to restore the wrong shape. Ending the live one
        is the caller's decision, not this module's — it has no way to ask.

        The parameters are deep-copied so cancelling an edit reverts nested
        values (a polygon's vertex list) rather than the outer dict alone; the
        full ``to_dict()`` is kept separately because committing an edit has to
        be undoable, and undo needs the state, not just the parameters.
        """
        if seg is None or self.is_active():
            return False
        self._seg = seg
        self._is_new = bool(is_new)
        self._orig_params = None if is_new else copy.deepcopy(seg.parameters)
        self._orig_state = None if is_new else seg.to_dict()
        self._dialog = None
        self._session = session
        return True

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
        outcome = EditOutcome(self._seg, self._is_new, self._orig_state,
                              session=self._session)
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
        session = self._session
        self._reset()
        if seg is None:
            return None
        reverted = False
        if (not is_new) and orig_params is not None:
            seg.parameters = orig_params
            if orig_state is not None and hasattr(seg, "closed"):
                seg.closed = bool(orig_state.get("closed", True))
            reverted = True
        return EditOutcome(seg, is_new, orig_state, reverted=reverted,
                           session=session)

    def _reset(self):
        self._seg = None
        self._dialog = None
        self._is_new = True
        self._orig_params = None
        self._orig_state = None
        self._session = None

    # ══ The committed-edge drag ══════════════════════════════════════════
    def is_dragging(self) -> bool:
        return self._drag_seg is not None

    @property
    def drag_segment(self):
        """The segment the drag in progress began on, or None."""
        return self._drag_seg

    def begin_drag(self, seg, session=None) -> bool:
        """Start a drag on ``seg``, or continue the one already on it.

        Called on EVERY move event, and snapshots only the first time — that is
        what collapses a gesture into one undo step. A call naming a *different*
        segment starts a new drag and discards the old snapshot, which is the
        stale-snapshot rule from the other side: a leftover from a gesture that
        never finished cannot be adopted by the next one. Returns True when this
        call actually took a snapshot.
        """
        if seg is None or self._drag_seg is seg:
            return False
        self._drag_seg = seg
        self._drag_state = seg.to_dict()
        self._drag_session = session
        return True

    def finish_drag(self, seg):
        """End the drag and return the pre-gesture snapshot — but ONLY if the
        drag began on ``seg``. None otherwise, and in that case nothing should
        be recorded: the gesture that took the snapshot is not the one ending.

        The drag ends either way. Returning the snapshot for a segment it does
        not describe is the failure this replaces — undo would then write one
        edge's shape onto another.
        """
        began_on, state = self._drag_seg, self._drag_state
        self._drag_seg = None
        self._drag_state = None
        self._drag_session = None
        return state if (began_on is not None and began_on is seg) else None

    # ══ The shape (imported outline) edit ════════════════════════════════
    def is_shape_active(self) -> bool:
        return self._shape_seg is not None

    @property
    def shape_dialog(self):
        """The modeless endpoint dialog, held opaquely; None if not attached."""
        return self._shape_dialog

    @property
    def edge_corners(self):
        """``(i0, i1)`` — the double-clicked edge's corners, the two the numeric
        dialog shows. None when no shape edit is live."""
        return self._shape_edge

    def begin_shape(self, seg, points, segments, session=None) -> bool:
        """Open ``seg``'s whole outline for corner editing. False if it has none.

        A geometry whose file segments describe no usable edge cannot be edited
        this way — the caller says so; refusing here rather than opening an empty
        handle set is what keeps "a session is live" meaningful. Also refused
        while ANOTHER edit is live, for the reason :meth:`begin` gives; ask
        :meth:`is_active` first when the two need distinguishing, since "no
        usable edge" and "an edit is already open" are different sentences.
        """
        pts = np.asarray(points, dtype=float) if points is not None else None
        if pts is None or len(pts) == 0 or self.is_active():
            return False
        n = len(pts)
        specs, corners = build_edge_specs(segments, n)
        if not specs or not corners:
            return False
        self._shape_seg = seg
        self._shape_dialog = None
        self._shape_orig = pts.copy()
        self._shape_specs = specs
        self._shape_corners = corners
        self._shape_pos = {k: list(pts[k]) for k in corners}
        # end_index may be one past the end (the closing edge wrapping to 0).
        self._shape_edge = (seg.start_index,
                            seg.end_index if seg.end_index < n else 0)
        self._shape_session = session
        return True

    def attach_shape_dialog(self, dlg):
        self._shape_dialog = dlg

    def handle_points(self):
        """``[(handle id, (x, y)), …]`` — one draggable handle per corner, in
        the stable sorted order ``build_edge_specs`` returns."""
        if self._shape_seg is None:
            return []
        return [(f"{_CORNER_PREFIX}{k}", tuple(self._shape_pos[k]))
                for k in self._shape_corners]

    def edge_corner_points(self):
        """The current positions of the two corners the dialog shows, or None."""
        if self._shape_edge is None:
            return None
        i0, i1 = self._shape_edge
        return tuple(self._shape_pos[i0]), tuple(self._shape_pos[i1])

    def move_corner(self, handle_id, x, y):
        """Move one corner and return the re-fitted outline; None if unusable.

        Returns None — rather than raising — for an unparseable or unknown
        handle id, because handle ids arrive from the canvas and a stray one
        must not take the edit down with it.
        """
        if self._shape_seg is None:
            return None
        key = self.corner_key(handle_id)
        if key is None or key not in self._shape_pos:
            return None
        self._shape_pos[key] = [x, y]
        return self._refit()

    def set_edge_corners(self, p0, p1):
        """Set both of the dialog's corners at once; returns the re-fitted
        outline, or None if no shape edit is live."""
        if self._shape_seg is None or self._shape_edge is None:
            return None
        i0, i1 = self._shape_edge
        self._shape_pos[i0] = list(p0)
        self._shape_pos[i1] = list(p1)
        return self._refit()

    @staticmethod
    def corner_key(handle_id):
        """Parse a corner handle id back to its point index, else None."""
        try:
            text = str(handle_id)
            if not text.startswith(_CORNER_PREFIX):
                return None
            return int(text[len(_CORNER_PREFIX):])
        except (TypeError, ValueError):
            return None

    def end_shape(self) -> Optional[ShapeOutcome]:
        """End the shape session, returning the pristine points. None if none
        was live.

        ONE verb, not a commit/cancel pair, because both endings need the same
        thing from this module — the snapshot — and differ only in what the
        caller does with it: Cancel puts it back, Commit makes it the "before"
        half of an undoable replacement. Two identical verbs would only pretend
        the owner had an opinion about which ending it was.
        """
        if self._shape_seg is None:
            self._reset_shape()
            return None
        outcome = ShapeOutcome(self._shape_seg, self._shape_orig,
                               session=self._shape_session)
        self._reset_shape()
        return outcome

    def _refit(self):
        return refit_shape(self._shape_orig, self._shape_specs, self._shape_pos)

    def release_drag_for(self, session) -> bool:
        """Drop a drag belonging to ``session``. True if one was dropped.

        Leaving a CAD session ends any gesture that began in it. No prompt and
        nothing to revert: a drag holds only the snapshot that would have made
        the gesture undoable, so dropping it means the gesture records nothing —
        which is the right answer for a gesture the user walked away from.
        """
        if self._drag_seg is None or self._drag_session is not session:
            return False
        self._drag_seg = None
        self._drag_state = None
        self._drag_session = None
        return True

    def _reset_shape(self):
        self._shape_seg = None
        self._shape_dialog = None
        self._shape_orig = None
        self._shape_specs = None
        self._shape_corners = None
        self._shape_pos = None
        self._shape_edge = None
        self._shape_session = None
