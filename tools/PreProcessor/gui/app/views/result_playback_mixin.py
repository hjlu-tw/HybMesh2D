"""Frame playback for a transient result (multi-zone Tecplot file).

A transient run appends one zone per dumped step, so the Results view is a movie
that was only ever shown one frame at a time. This mixin adds the transport
controls — First, Prev, Play/Pause, Next, Last, speed, Loop and the colour-scale
lock — over :class:`~app.models.result_series.ResultSeries`.

**Looping is opt-in.** A run plays through once and stops on the last frame (the
converged solution, and where the view opens anyway); the Loop checkbox turns the
animation into a repeating one. The same switch governs the step buttons, which
clamp at the ends rather than jumping to the far end of the run. First/Last are
the deliberate jumps to an end and ignore Loop entirely.

**A restarted solve plays as one animation, and is not asked about.** Opening
any leg of it opens the whole solve (#32 asked a modal on every load; #43 removed
it, along with the permission flag that let a caller suppress it — interactive
and unattended loads now take one path). **"This leg only"** is the escape, and
it follows the same rules as "Lock scale": shown only when there IS more than one
leg, never persisted, unticked on every load. Toggling it rebuilds the series.

Two things make the animation readable rather than merely possible:

* **The colour scale is its own concern**, in ``result_scale_lock_mixin`` — the
  lock, the seed and the precedence between them. Split out when this file passed
  the GUI length budget; the two only ever shared a toolbar row.
* **The mesh is not rebuilt per frame.** ``set_result`` reuses the triangulation
  when the incoming frame has the same nodes, which also keeps probes/lines/
  extrema alive across a step (they are pinned to geometry that did not move).
"""
from __future__ import annotations

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton,
)

from app.models.result_series import ResultSeries
from app.services import user_log
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

        self.first_btn = QPushButton("⏮ First")
        self.first_btn.setToolTip("Jump to the first frame of the run")
        self.prev_btn = QPushButton("◀ Prev")
        self.prev_btn.setToolTip(
            "Show the previous frame (stops at the first unless Loop is on)")
        self.play_btn = QPushButton("▶ Play")
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.setToolTip(
            "Show the next frame (stops at the last unless Loop is on)")
        self.last_btn = QPushButton("Last ⏭")
        self.last_btn.setToolTip(
            "Jump to the last frame — the converged solution of the run")
        for b in (self.first_btn, self.prev_btn, self.play_btn,
                  self.next_btn, self.last_btn):
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

        # Off by default so "Auto (fit to data)" fits the frame on screen. On,
        # every frame is drawn on the whole run's range, which is what makes a
        # decaying field visibly decay instead of looking identical throughout.
        self.lock_scale_cb = QCheckBox("Lock scale")
        self.lock_scale_cb.setChecked(False)
        self.lock_scale_cb.setStyleSheet(f"color:{_FG};font-size:11px;")
        self.lock_scale_cb.setToolTip(
            "Pin the colour scale to this variable's range over ALL frames, so "
            "colours mean the same thing throughout the run.\n"
            "Off (default): 'Auto (fit to data)' fits each frame on its own.\n"
            "A range typed into Min/Max wins over both.")

        # Only for a restarted solve, and unticked every time: opening any leg
        # plays the whole solve, and inspecting one on its own is the exception
        # the user asks for rather than a preference the view carries over.
        self.one_leg_cb = QCheckBox("This leg only")
        self.one_leg_cb.setChecked(False)
        self.one_leg_cb.setStyleSheet(f"color:{_FG};font-size:11px;")
        self.one_leg_cb.setToolTip(
            "Play only the file you opened, instead of every leg of this "
            "restarted solve.\n"
            "Shown only when the solve HAS more than one leg, and always off "
            "when a result is opened.")

        # "Which legs?" as a reopenable control, so the load-time question is an
        # answer the user can revise rather than one they are stuck with
        # (USER-REQUESTED 2026-08-27). Shown on the same condition as the
        # checkbox beside it: does this SOLVE have more than one leg.
        self.pick_legs_btn = QPushButton("Legs…")
        self.pick_legs_btn.setFixedWidth(52)
        self.pick_legs_btn.setStyleSheet(f"color:{_FG};font-size:11px;")
        self.pick_legs_btn.setToolTip(
            "Choose which legs of this restarted solve play as one animation.\n"
            "All of them unless you say otherwise; 'This leg only' overrides "
            "this while it is ticked.")
        self.pick_legs_btn.clicked.connect(self._on_pick_legs)

        for w in (self.first_btn, self.prev_btn, self.play_btn, self.next_btn,
                  self.last_btn, self.frame_label, speed_label,
                  self.speed_combo, self.loop_cb, self.lock_scale_cb,
                  self.one_leg_cb, self.pick_legs_btn):
            row.addWidget(w)
        row.addStretch()
        # Directly under row 1 (the data selectors it belongs with), not appended
        # after the display toggles.
        bar_v.insertLayout(1, row)

        self._playback_widgets = [self.first_btn, self.prev_btn, self.play_btn,
                                  self.next_btn, self.last_btn,
                                  self.frame_label, speed_label,
                                  self.speed_combo, self.loop_cb,
                                  self.lock_scale_cb]
        for w in self._playback_widgets:
            w.setVisible(False)
        # Deliberately NOT in _playback_widgets: that group answers "does this
        # result have several FRAMES?", and this box answers "does this SOLVE have
        # several LEGS?" — two different questions, so it gets its own line in
        # _update_playback_ui rather than riding along with the transport.
        self.one_leg_cb.setVisible(False)

        self.first_btn.clicked.connect(lambda: self.go_to_end(-1))
        self.prev_btn.clicked.connect(lambda: self.step_frame(-1))
        self.next_btn.clicked.connect(lambda: self.step_frame(1))
        self.last_btn.clicked.connect(lambda: self.go_to_end(1))
        self.play_btn.clicked.connect(self.toggle_playback)
        self.speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        # Ticking Loop at an end must re-enable the step button parked there.
        self.loop_cb.toggled.connect(lambda _=None: self._update_playback_ui())
        self.lock_scale_cb.toggled.connect(self._on_lock_scale_toggled)
        self.one_leg_cb.toggled.connect(self._on_one_leg_toggled)

    def _init_playback(self):
        self._series: ResultSeries | None = None
        self._frame = 0
        self._playing = False
        self._legs = None            # the whole solve, whether or not it is loaded
        self._range_lock = None      # (vmin, vmax) pinned across the animation
        self._range_lock_var = ""    # which variable _range_lock belongs to
        self._scanning = False       # a range scan is running (blocks re-entry)
        # Variables whose range came from a SUCCESSFUL whole-series scan. Not
        # "variables that have a range": a failed scan must be retryable, and a
        # range the user typed must not be scanned away. See the scale mixin.
        self._series_seeded: set = set()
        self._play_timer = QTimer(self)
        self._play_timer.setTimerType(Qt.TimerType.CoarseTimer)
        self._play_timer.timeout.connect(self._advance_frame)

    def _attach_series(self, paths, labels=None):
        """Point the transport at ``paths`` and show/hide it by frame count.

        ``paths`` is one path or the legs of a restarted solve in playback order
        (#32); ``labels`` names them for the frame read-out. The transport does
        not care how many files there are — the series flattens them into one
        frame numbering — so everything below this line is unchanged by #32.
        """
        self.stop_playback()
        self._range_lock = None
        self._range_lock_var = ""
        self._series_seeded.clear()
        try:
            self._series = ResultSeries(paths, labels=labels)
        except (OSError, ValueError) as e:
            self._series = None
            _log.warning("could not index %s for playback: %s", paths, e)
        if self._series is not None:
            self._report_variable_gaps(self._series)
        self._frame = max(0, (self._series.n_frames - 1) if self._series else 0)
        self._update_playback_ui()

    def _report_variable_gaps(self, series):
        """Say which leg is short of which variable, when the legs disagree.

        The selector offers the INTERSECTION (``ResultSeries.variables``), which
        is the only set every frame can render. That is a real subtraction, so it
        is said out loud rather than left as a variable that quietly stopped being
        on the list.
        """
        for label, missing in series.variable_gaps():
            self._log(f"[Results] leg '{label}' does not carry "
                      f"{', '.join(missing)} — the variable list shows only what "
                      "every leg has, so the animation never changes subject "
                      "part-way through. Tick 'This leg only' on a leg that has "
                      "it to see it.")

    def _detach_series(self):
        self.stop_playback()
        self._series = None
        self._frame = 0
        self._legs = None
        self._range_lock = None
        self._range_lock_var = ""
        self._series_seeded.clear()
        self._update_playback_ui()

    # ------------------------------------------------------------------ #
    # Transport
    # ------------------------------------------------------------------ #
    def _frame_count(self) -> int:
        return self._series.n_frames if self._series else 0

    def _looping(self) -> bool:
        cb = getattr(self, "loop_cb", None)
        return bool(cb.isChecked()) if cb is not None else False

    def _scale_locked(self) -> bool:
        """Whether the colour scale is pinned to the whole run (opt-in)."""
        cb = getattr(self, "lock_scale_cb", None)
        return bool(cb.isChecked()) if cb is not None else False

    def toggle_playback(self):
        self.stop_playback() if self._playing else self.start_playback()

    def start_playback(self):
        """Begin animating. No-op unless the file actually has several frames."""
        n = self._frame_count()
        if n < 2 or self._playing:
            return
        # Also here, not only in show_frame: pressing Play mid-run does not change frame,
        # so without this the frame already on screen would keep its per-frame scale
        # until the first tick — a visible jump one frame in.
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
        self.show_frame(target)

    def go_to_end(self, direction: int):
        """Jump to the first (``direction < 0``) or last frame of the run.

        Deliberately NOT governed by Loop: "take me to the end" has one meaning
        whether or not the animation wraps, and unlike Prev/Next there is no
        far end to be surprised by.
        """
        n = self._frame_count()
        if n < 2:
            return
        self.stop_playback()
        target = 0 if direction < 0 else n - 1
        if target != self._frame:
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
        """Display frame ``k`` (0-based), keeping the zone selector in step.

        Every route to another frame goes through here — Prev/Next, the timer, the
        rewind, AND the zone combo box — so this is where the colour scale is pinned.
        It used to be pinned by the two transport callers instead, which left the most
        obvious way to compare frames (picking them from the combo) auto-scaling each
        frame to its own min/max: the very effect the lock exists to remove.
        """
        n = self._frame_count()
        if not (0 <= k < n):
            return
        self._lock_color_range()
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
    def _update_playback_ui(self):
        """Reflect frame position / playing state; hide the bar for 1-frame files."""
        n = self._frame_count()
        multi = n > 1
        for w in getattr(self, "_playback_widgets", []):
            w.setVisible(multi)
        if not hasattr(self, "play_btn"):
            return
        # Visibility follows how many legs the SOLVE has, and NOTHING else — not
        # `multi`, which is a fact about frames. Ticking the box can leave a
        # single-frame series (one zone per leg is an ordinary restarted solve),
        # and `multi` then hid the whole transport row INCLUDING the box that had
        # just been ticked, with no way back. Measured in review of #43: 3 legs x
        # 1 zone, tick -> frames=1, hidden=True.
        multi_leg = len(self._legs or ()) > 1
        self.one_leg_cb.setVisible(multi_leg)
        # Not keyed on the frame-count flag: a solve of three one-frame legs is
        # an ordinary restarted run, and hiding this with the transport would
        # close the escape behind the user (the bug #43 found for 'This leg
        # only', measured at 3 legs x 1 zone).
        self.pick_legs_btn.setVisible(multi_leg)
        self.play_btn.setText("❚❚ Pause" if self._playing else "▶ Play")
        self.play_btn.setToolTip(
            "Pause the animation" if self._playing else
            "Play through every frame of this transient result")
        # Without Loop, an end of the run is a real boundary: grey the step
        # button out there rather than leaving a click that does nothing.
        loop = self._looping()
        at_first, at_last = self._frame <= 0, self._frame >= n - 1
        self.prev_btn.setEnabled(multi and (loop or not at_first))
        self.next_btn.setEnabled(multi and (loop or not at_last))
        # First/Last are jumps, not steps: Loop does not make "go to the first
        # frame" mean anything different, and standing ON that frame is the one
        # case where the button has nothing to do.
        self.first_btn.setEnabled(multi and not at_first)
        self.last_btn.setEnabled(multi and not at_last)
        self.frame_label.setText(self._read_out())
        tip = self._legs_tip()
        self.frame_label.setToolTip(tip)
        self.zone_combo.setToolTip(tip)

    def _read_out(self) -> str:
        """What the transport says about where it is.

        The series label names the leg and the position WITHIN it
        (``prev_002 · Frame 3 / 10``), which is the pair that identifies a frame
        — but every button here moves through the whole series, so across legs
        the read-out also carries the overall position. It is appended HERE
        rather than inside ``frame_label`` because the zone selector uses that
        label as a list entry, where a second pair of numbers on every row is
        noise; this is the one place describing the transport itself.
        """
        n = self._frame_count()
        if n < 2 or self._series is None:
            return ""
        label = self._series.frame_label(self._frame)
        if self._series.n_files > 1:
            label += f" ({self._frame + 1} / {n})"
        return label

    def _log(self, msg: str):
        """Say something to the user about playback.

        This used to hand-roll the "is there a console to write to?" fallback by
        walking up to the window and poking at ``log_panel``; the sink registry
        answers that now, so a test (or a headless run) with no window keeps the
        message instead of it depending on who happens to be on screen.
        """
        user_log.log(msg)
