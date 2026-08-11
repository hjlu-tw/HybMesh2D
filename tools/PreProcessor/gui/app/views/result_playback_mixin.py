"""Frame playback for a transient result (multi-zone Tecplot file).

A transient run appends one zone per dumped step, so the Results view is a movie
that was only ever shown one frame at a time. This mixin adds the transport
controls — Play/Pause, Prev, Next, speed and Loop — over
:class:`~app.models.result_series.ResultSeries`.

**Looping is opt-in.** A run plays through once and stops on the last frame (the
converged solution, and where the view opens anyway); the Loop checkbox turns the
animation into a repeating one. The same switch governs the step buttons, which
clamp at the ends rather than jumping to the far end of the run.

Two things make the animation readable rather than merely possible:

* **The colour scale is locked across the whole run.** Auto-scaling every frame
  to its own min/max repaints the same colours onto a changing range, so a field
  that grows by 10x looks identical from frame to frame. The first use of any
  transport control scans all frames for the current variable (cached per
  variable, see ``ResultSeries.global_range``) and pins that range for the run.
  A range the user set by hand always wins — locking is a fix for auto-scaling,
  not an override of an explicit choice.
* **The mesh is not rebuilt per frame.** ``set_result`` reuses the triangulation
  when the incoming frame has the same nodes, which also keeps probes/lines/
  extrema alive across a step (they are pinned to geometry that did not move).
"""
from __future__ import annotations

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton,
)

from app.models.result_series import ResultSeries
from app.services.logging_setup import get_logger
from app.utils import block_signals

_log = get_logger(__name__)

# Frame rates offered in the speed picker. 4 fps reads as motion while still
# giving each frame long enough to be looked at; a full render is ~0.1-0.2 s on
# a 70k-cell mesh, so the higher rates degrade to "as fast as it can draw".
PLAYBACK_RATES = [1, 2, 4, 8, 15]
DEFAULT_RATE = 4

_FG = "#a0a8c0"
_BTN_QSS = (
    "QPushButton{background:#1d2a3a;color:#dde2ff;border:1px solid #2d3356;"
    "border-radius:4px;padding:3px 10px;font-weight:bold;font-size:11px;}"
    "QPushButton:hover{border-color:#5a9ad4;}")
_COMBO_QSS = (
    "QComboBox{background:#181b30;color:#dde2ff;border:1px solid #2d3356;"
    "border-radius:4px;padding:2px 6px;font-size:11px;min-width:70px;}")


class ResultPlaybackMixin:
    """Play / step through the zones of a transient result."""

    # ------------------------------------------------------------------ #
    # Setup (called from ResultCanvasView.__init__)
    # ------------------------------------------------------------------ #
    def _build_playback_bar(self, bar_v):
        """Create the transport row and insert it under the data selectors.

        Every widget is registered in ``_playback_widgets`` so one call hides the
        whole group for a single-frame (steady) result.
        """
        row = QHBoxLayout()
        row.setSpacing(6)

        self.prev_btn = QPushButton("◀ Prev")
        self.prev_btn.setToolTip(
            "Show the previous frame (stops at the first unless Loop is on)")
        self.play_btn = QPushButton("▶ Play")
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.setToolTip(
            "Show the next frame (stops at the last unless Loop is on)")
        for b in (self.prev_btn, self.play_btn, self.next_btn):
            b.setStyleSheet(_BTN_QSS)

        self.frame_label = QLabel("")
        self.frame_label.setStyleSheet(
            f"color:{_FG};font-size:11px;font-weight:bold;")
        self.frame_label.setMinimumWidth(150)

        speed_label = QLabel("Speed:")
        speed_label.setStyleSheet(f"color:{_FG};font-size:11px;")
        self.speed_combo = QComboBox()
        self.speed_combo.setStyleSheet(_COMBO_QSS)
        for r in PLAYBACK_RATES:
            self.speed_combo.addItem(f"{r} fps", r)
        self.speed_combo.setCurrentIndex(PLAYBACK_RATES.index(DEFAULT_RATE))
        self.speed_combo.setToolTip(
            "Target frames per second. A frame that takes longer to draw than "
            "the interval simply plays at the rate the mesh allows.")

        # Off by default: a run plays through once and stops on the last frame,
        # which is the converged solution and the thing worth being left looking
        # at. Looping is a deliberate choice, not the thing that happens to you.
        self.loop_cb = QCheckBox("Loop")
        self.loop_cb.setChecked(False)
        self.loop_cb.setStyleSheet(f"color:{_FG};font-size:11px;")
        self.loop_cb.setToolTip(
            "Repeat the run continuously. Off: Play stops at the last frame, "
            "and Prev/Next stop at the ends instead of wrapping round.")

        for w in (self.prev_btn, self.play_btn, self.next_btn,
                  self.frame_label, speed_label, self.speed_combo, self.loop_cb):
            row.addWidget(w)
        row.addStretch()
        # Directly under row 1 (the data selectors it belongs with), not appended
        # after the display toggles.
        bar_v.insertLayout(1, row)

        self._playback_widgets = [self.prev_btn, self.play_btn, self.next_btn,
                                  self.frame_label, speed_label,
                                  self.speed_combo, self.loop_cb]
        for w in self._playback_widgets:
            w.setVisible(False)

        self.prev_btn.clicked.connect(lambda: self.step_frame(-1))
        self.next_btn.clicked.connect(lambda: self.step_frame(1))
        self.play_btn.clicked.connect(self.toggle_playback)
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        # Ticking Loop at an end must re-enable the step button parked there.
        self.loop_cb.toggled.connect(lambda _=None: self._update_playback_ui())

    def _init_playback(self):
        self._series: ResultSeries | None = None
        self._frame = 0
        self._playing = False
        self._range_lock = None      # (vmin, vmax) pinned across the animation
        self._range_lock_var = ""    # which variable _range_lock belongs to
        self._scanning = False       # a range scan is running (blocks re-entry)
        self._play_timer = QTimer(self)
        self._play_timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._play_timer.timeout.connect(self._advance_frame)

    def _attach_series(self, path: str):
        """Point the transport at ``path`` and show/hide it by zone count."""
        self.stop_playback()
        self._range_lock = None
        self._range_lock_var = ""
        try:
            self._series = ResultSeries(path)
        except (OSError, ValueError) as e:
            self._series = None
            _log.warning("could not index %s for playback: %s", path, e)
        self._frame = max(0, (self._series.n_frames - 1) if self._series else 0)
        self._update_playback_ui()

    def _detach_series(self):
        self.stop_playback()
        self._series = None
        self._frame = 0
        self._range_lock = None
        self._range_lock_var = ""
        self._update_playback_ui()

    # ------------------------------------------------------------------ #
    # Transport
    # ------------------------------------------------------------------ #
    def _frame_count(self) -> int:
        return self._series.n_frames if self._series else 0

    def _looping(self) -> bool:
        cb = getattr(self, "loop_cb", None)
        return bool(cb.isChecked()) if cb is not None else False

    def toggle_playback(self):
        self.stop_playback() if self._playing else self.start_playback()

    def start_playback(self):
        """Begin animating. No-op unless the file actually has several frames."""
        n = self._frame_count()
        if n < 2 or self._playing:
            return
        self._lock_color_range()
        # Play at the end of a finished, non-looping run means "play it again":
        # rewind, rather than starting a run with nowhere to go and stopping on
        # the first tick.
        if not self._looping() and self._frame >= n - 1:
            self.show_frame(0)
        self._playing = True
        self._play_timer.start(max(1, int(1000 / self._playback_rate())))
        self._update_playback_ui()

    def stop_playback(self):
        self._play_timer.stop()
        if not self._playing:
            return
        self._playing = False
        self._update_playback_ui()

    def step_frame(self, delta: int):
        """Step by ``delta`` frames, pausing an animation first.

        Wraps round the ends only when Loop is on; otherwise it clamps, so the
        button parked at an end does nothing rather than jumping to the far end
        of the run.
        """
        n = self._frame_count()
        if n < 2:
            return
        self.stop_playback()
        target = self._frame + delta
        if self._looping():
            target %= n
        else:
            target = max(0, min(n - 1, target))
            if target == self._frame:
                return
        self._lock_color_range()
        self.show_frame(target)

    def _advance_frame(self):
        n = self._frame_count()
        if n < 2:
            self.stop_playback()
            return
        nxt = self._frame + 1
        if nxt >= n:
            if not self._looping():
                # End of the run: stop ON the last frame (the converged
                # solution), which is where the view opens on anyway.
                self.stop_playback()
                return
            nxt = 0
        self.show_frame(nxt)

    def show_frame(self, k: int):
        """Display frame ``k`` (0-based), keeping the zone selector in step."""
        n = self._frame_count()
        if not (0 <= k < n):
            return
        self._frame = k
        try:
            result = self._series.frame(k)
        except (OSError, ValueError) as e:
            self.stop_playback()
            _log.warning("frame %d could not be loaded: %s", k, e)
            self._empty_message(f"Frame {k + 1} could not be loaded: {e}")
            return
        with block_signals(self.zone_combo):
            if self.zone_combo.count() > k:
                self.zone_combo.setCurrentIndex(k)
        self.set_result(result)
        self._update_playback_ui()

    def hideEvent(self, event):
        """Stop animating when the Results page is left.

        Without this the timer keeps loading and drawing frames for a canvas
        nobody is looking at, which competes with the mesher or solver run the
        user switched away to watch. (Mixin sits before QWidget in the MRO, so
        this override reaches Qt's implementation through super().)
        """
        self.stop_playback()
        super().hideEvent(event)

    def _playback_rate(self) -> int:
        combo = getattr(self, "speed_combo", None)
        if combo is None:
            return DEFAULT_RATE
        data = combo.currentData()
        return int(data) if data else DEFAULT_RATE

    def _on_speed_changed(self, _idx=None):
        if self._playing:
            self._play_timer.start(max(1, int(1000 / self._playback_rate())))

    # ------------------------------------------------------------------ #
    # Colour-scale lock
    # ------------------------------------------------------------------ #
    def _lock_color_range(self):
        """Pin the colour scale to the current variable's range over ALL frames.

        Skipped when the user set the range by hand (their choice stands) or when
        the file has a single frame (nothing to keep steady). The scan is paid
        once per variable — afterwards the answer is cached on the series.
        """
        if self._series is None or self._frame_count() < 2 or not self._clim_auto:
            return
        var = self._current_var()
        if not var:
            return
        if self._range_lock is not None and self._range_lock_var == var:
            return
        if self._scanning:
            return
        known = self._series.has_global_range(var)
        self._scanning = True
        try:
            if not known:
                self._log(f"[Results] scanning {self._frame_count()} frames for "
                          f"the '{var}' range (once per variable)…")
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                # Paint the message and the cursor BEFORE the scan blocks: a long
                # run means seconds of frozen UI, and an unexplained freeze reads
                # as a hang. Re-entry is what _scanning guards.
                QApplication.processEvents()
            try:
                rng = self._series.global_range(var)
            except (OSError, ValueError) as e:
                _log.warning("global range scan failed for %s: %s", var, e)
                rng = None
        finally:
            self._scanning = False
            if not known:
                QApplication.restoreOverrideCursor()
        self._range_lock = rng
        self._range_lock_var = var
        if rng and not known:
            self._log(f"[Results] '{var}' locked to [{rng[0]:.6g}, {rng[1]:.6g}] "
                      "for playback (all frames share one colour scale).")

    def _invalidate_range_lock(self):
        """Called when the displayed variable changes — the lock is per-variable."""
        if self._range_lock is not None and self._range_lock_var != self._current_var():
            self._range_lock = None
            self._range_lock_var = ""

    def playback_clim(self):
        """The pinned (vmin, vmax) if it applies to what is on screen, else None.

        ``render`` consults this ONLY in auto mode, so a manual colour range is
        never silently replaced by the animation's.
        """
        if self._range_lock is None or not self._clim_auto:
            return None
        if self._range_lock_var != self._current_var():
            return None
        return self._range_lock

    # ------------------------------------------------------------------ #
    def _update_playback_ui(self):
        """Reflect frame position / playing state; hide the bar for 1-frame files."""
        n = self._frame_count()
        multi = n > 1
        for w in getattr(self, "_playback_widgets", []):
            w.setVisible(multi)
        if not hasattr(self, "play_btn"):
            return
        self.play_btn.setText("❚❚ Pause" if self._playing else "▶ Play")
        self.play_btn.setToolTip(
            "Pause the animation" if self._playing else
            "Play through every frame of this transient result")
        # Without Loop, an end of the run is a real boundary: grey the step
        # button out there rather than leaving a click that does nothing.
        loop = self._looping()
        self.prev_btn.setEnabled(multi and (loop or self._frame > 0))
        self.next_btn.setEnabled(multi and (loop or self._frame < n - 1))
        self.frame_label.setText(
            self._series.frame_label(self._frame) if multi else "")

    def _log(self, msg: str):
        """Log to the main window's console when there is one (tests have none)."""
        win = self.window()
        panel = getattr(win, "log_panel", None)
        if panel is not None:
            panel.log(msg)
        else:
            _log.info("%s", msg)
