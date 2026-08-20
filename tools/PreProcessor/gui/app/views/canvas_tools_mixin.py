"""Measure tool + view history for the CAD canvas.

The canvas could draw and drag but not *measure*: checking a slat gap, a chord, or the
clearance a boundary layer has to fit into meant exporting the geometry and computing
it elsewhere. It also had no way back to a previous zoom — a mis-scrolled wheel meant
re-framing by hand.

The arithmetic and the history stack live in the Qt-free
:mod:`app.services.canvas_tools`; this mixin is only the canvas state and the drawn
overlay.
"""
from __future__ import annotations

import pyqtgraph as pg
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFontDatabase

from app.services.canvas_tools import ViewHistory, format_measure_lines, measure

#: Idle time before a view is recorded. Long enough that a wheel-zoom or a drag-pan is
#: one history entry, short enough that Back is available as soon as you stop moving.
VIEW_PUSH_IDLE_MS = 350
from app.services.logging_setup import get_logger

_log = get_logger(__name__)

#: Measurement is an ANNOTATION, not data, and telling it apart cannot rest on hue
#: alone: this canvas already carries ~20 colours (six palette constants plus twelve
#: session colours), so no hue is truly free. The old amber #f5c542 sat on top of three
#: of them — #FFD700 (auto-closing edge), #FFB347 (active segment) and the #FFD54F /
#: #FFF176 session colours — and plain white is worse still, because white rings are the
#: endpoint markers, i.e. exactly what you are looking at while measuring.
#:
#: The hue is chosen by measurement, not by eye: a search over legible saturated colours
#: maximising the minimum CIELAB ΔE to all 25 colours in play lands on this violet-magenta
#: at ΔE 64. For comparison the old amber scored **6.1** — below ~10, which is "the same
#: colour at a glance", i.e. the reported duplication, quantified — and plain white scores
#: **0.0** because it IS the endpoint-marker colour.
#:
#: The read-out additionally gets a filled dark plate, which no other item has, so it reads
#: as a label rather than as geometry even before the colour registers. Belt and braces,
#: because on a canvas this crowded no hue stays unique for ever.
_MEASURE_COLOR = "#DD11FF"
#: Background for the read-out, matching the canvas so the label sits on its own plate.
_MEASURE_LABEL_BG = (12, 13, 22, 210)
#: Anchor for that plate: centred horizontally, sitting just above the span's midpoint.
#: The gap is ``(y - 1)`` of the plate's OWN height, so a four-row plate needs a much
#: smaller fraction than the single line did (1.4 there meant 0.4 of one line; here 1.1
#: means 0.1 of four rows) — otherwise stacking the values would float the label a full
#: line-and-a-half clear of the thing it labels.
_MEASURE_LABEL_ANCHOR = (0.5, 1.1)

#: Every mutually-exclusive canvas tool — the ones that take over the click and the
#: cursor: ``(name, "flag attribute", "the call that leaves it")``.
#:
#: Exclusion used to be written pairwise inside each ``start_*``, so with three tools
#: there were six directions and only three were implemented: Measure stopped the other
#: two, but starting a draw tool (Polygon, Line, …) or the weld tool did NOT stop
#: Measure. The reported symptom is the cursor, but the real one is worse — the measure
#: tool intercepts clicks *before* drawing (``canvas_events_mixin``), so a Polygon
#: started while Measure was on collected measurement spans and never placed a point.
#:
#: One table, applied by ``activate_exclusive_tool``, makes it symmetric by construction:
#: a tool added here is excluded in both directions without touching any other tool.
EXCLUSIVE_TOOLS = (
    ("measure", "_measure_tool", "stop_measure_tool"),
    ("draw", "_draw_tool", "cancel_draw_mode"),
    ("weld", "_endpoint_tool", "stop_endpoint_tool"),
)


class CanvasToolsMixin:
    def _init_canvas_tools(self):
        """Set up measure state and start recording view ranges."""
        self._measure_tool = False
        self._measure_first = None          # first clicked point, or None
        self._measure_result = {}
        #: Called with no arguments whenever the measure tool leaves, however it left —
        #: the toolbar's toggle has to follow the canvas, not the other way round, or
        #: a tool stopped by another tool leaves the button stuck looking pressed.
        self.measure_ended_cb = None

        # Dashed rubber band + a text read-out, both created once and hidden.
        self._measure_line = pg.PlotDataItem(
            pen=pg.mkPen(_MEASURE_COLOR, width=1.4,
                         style=Qt.PenStyle.DashLine))
        self._measure_line.setZValue(95)
        self.plot_widget.addItem(self._measure_line)
        self._measure_text = pg.TextItem("", color=_MEASURE_COLOR,
                                         anchor=_MEASURE_LABEL_ANCHOR,
                                         fill=pg.mkBrush(*_MEASURE_LABEL_BG),
                                         border=pg.mkPen(_MEASURE_COLOR, width=1))
        # Fixed-width, so the four rows' "=" line up into a column instead of
        # ragging with the digit widths of whatever was measured.
        self._measure_text.textItem.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self._measure_text.setZValue(96)
        self.plot_widget.addItem(self._measure_text, ignoreBounds=True)
        self._measure_line.setVisible(False)
        self._measure_text.setVisible(False)

        self.view_history = ViewHistory()
        vb = self.plot_widget.getViewBox()
        # Recorded only once the view stops moving. pyqtgraph emits a range change per
        # axis and per wheel notch, so pushing on the signal itself made "back" mean
        # "back one notch" — and, because x and y arrive separately, one press of Back
        # often landed on a view a hair from where you already were and looked broken.
        # A browser records one entry per gesture; so does this.
        self._view_push_timer = QTimer(self)
        self._view_push_timer.setSingleShot(True)
        self._view_push_timer.setInterval(VIEW_PUSH_IDLE_MS)
        self._view_push_timer.timeout.connect(self._push_current_view)
        vb.sigRangeChanged.connect(self._on_view_range_changed)
        # Seed with the current view so the first "back" has somewhere to go.
        self.view_history.push(vb.viewRange())

    # ── view history ─────────────────────────────────────────────────────
    def _on_view_range_changed(self, *_args):
        """Restart the idle timer; the view is recorded when it settles."""
        if self.view_history.restoring:
            return
        self._view_push_timer.start()

    def _push_current_view(self):
        vb = self.plot_widget.getViewBox()
        if self.view_history.push(vb.viewRange()):
            self._notify_view_history()

    def _apply_view(self, view):
        """Set the view without recording it as a new navigation step."""
        if view is None:
            return False
        # A pending push would otherwise fire just after the restore and record the
        # view we just navigated to as a NEW step, truncating the forward branch.
        self._view_push_timer.stop()
        self.view_history.restoring = True
        try:
            vb = self.plot_widget.getViewBox()
            vb.setRange(xRange=view[0], yRange=view[1], padding=0)
        finally:
            self.view_history.restoring = False
        self._notify_view_history()
        return True

    def view_back(self) -> bool:
        return self._apply_view(self.view_history.back())

    def view_forward(self) -> bool:
        return self._apply_view(self.view_history.forward())

    def _notify_view_history(self):
        """Let the window enable/disable its back/forward buttons."""
        cb = getattr(self, "view_history_changed_cb", None)
        if cb is not None:
            cb(self.view_history.can_back, self.view_history.can_forward)

    # ── tool exclusion ───────────────────────────────────────────────────
    def activate_exclusive_tool(self, name: str):
        """Leave every canvas tool except ``name``. Call it at the top of a ``start_*``.

        Passing a name that is not in :data:`EXCLUSIVE_TOOLS` is a programming error and
        raises, rather than silently leaving that tool non-exclusive — which is exactly
        the failure this table replaced.

        Every other tool's stop is called UNCONDITIONALLY, not only when its flag is set:
        a tool's leftovers can outlive its flag. ``_commit_draw`` clears ``_draw_tool``
        while deliberately leaving the control-point handles and the rubber band on
        screen ("stop collecting; artifacts stay visible") until the shape dialog is
        resolved — and that dialog is modeless, so the user can pick another tool first.
        Gating on the flag skipped ``cancel_draw_mode``, and the finished shape's handles
        stayed painted over the new tool's. The stops are idempotent, and the one thing
        the gate was protecting against — ``stop_measure_tool`` un-checking the toolbar
        toggle, whose signal comes back in here — is guarded inside that method by its
        own real-transition check, which is where it belongs.
        """
        known = [t[0] for t in EXCLUSIVE_TOOLS]
        if name not in known:
            raise ValueError(f"unknown canvas tool {name!r}; expected one of {known}")
        for tool, _flag, stop in EXCLUSIVE_TOOLS:
            if tool == name:
                continue
            fn = getattr(self, stop, None)
            if callable(fn):
                fn()

    # ── measure tool ─────────────────────────────────────────────────────
    def start_measure_tool(self):
        """Enter measure mode: two clicks define the span."""
        self.activate_exclusive_tool("measure")
        self._measure_tool = True
        self._measure_first = None
        self._measure_result = {}
        self._measure_line.setVisible(False)
        self._measure_text.setVisible(False)
        try:
            self.plot_widget.setCursor(Qt.CursorShape.CrossCursor)
        except Exception:
            _log.debug("could not set the measure cursor", exc_info=True)

    def stop_measure_tool(self, keep_result: bool = True):
        """Leave measure mode. The last span stays drawn unless told otherwise, so
        the number is still readable after the tool is switched off."""
        was_on = bool(self._measure_tool)
        self._measure_tool = False
        self._measure_first = None
        if not keep_result:
            self._measure_result = {}
            self._measure_line.setVisible(False)
            self._measure_text.setVisible(False)
        try:
            self.plot_widget.unsetCursor()
        except Exception:
            _log.debug("could not restore the cursor after measuring",
                       exc_info=True)
        # Only on a real transition: the callback un-checks the toolbar toggle, whose
        # own signal calls back in here, and this is what stops that bouncing.
        if was_on and callable(self.measure_ended_cb):
            self.measure_ended_cb()

    @property
    def measuring(self) -> bool:
        return bool(self._measure_tool)

    def handle_measure_click(self, x: float, y: float) -> dict:
        """Feed a click to the measure tool. Returns the completed result, or {}.

        The first click anchors; the second completes the span and the NEXT click
        starts a fresh one — chaining spans is what you do when stepping along a
        multi-element gap, and forcing a tool re-activation between them would be
        friction for no gain.
        """
        if self._measure_first is None:
            self._measure_first = (float(x), float(y))
            self._measure_line.setData([x, x], [y, y])
            self._measure_line.setVisible(True)
            self._measure_text.setVisible(False)
            return {}
        m = measure(self._measure_first, (x, y))
        self._measure_first = None
        self._measure_result = m
        if m:
            self._draw_measure(m)
        return m

    def update_measure_preview(self, x: float, y: float):
        """Rubber-band the span while the second point is still being chosen."""
        if not self._measure_tool or self._measure_first is None:
            return
        m = measure(self._measure_first, (x, y))
        if m:
            self._draw_measure(m)

    def _draw_measure(self, m: dict):
        (x0, y0), (x1, y1) = m["p0"], m["p1"]
        self._measure_line.setData([x0, x1], [y0, y1])
        self._measure_line.setVisible(True)
        self._measure_text.setText(format_measure_lines(m))
        self._measure_text.setPos(0.5 * (x0 + x1), 0.5 * (y0 + y1))
        self._measure_text.setVisible(True)

    def clear_measure(self):
        self._measure_result = {}
        self._measure_first = None
        self._measure_line.setVisible(False)
        self._measure_text.setVisible(False)
