"""The colour scale a run is drawn on — pinned, seeded, or per frame.

Split out of ``result_playback_mixin`` when that file passed the GUI length
budget; the transport and the colour scale are two concerns that happened to
share a toolbar row. What lives here is every answer to "which numbers is this
frame coloured on?", and the precedence between them is unchanged (#24): a range
the user TYPED wins over the run-wide LOCK, which wins over the frame's own data
range.

* **The lock** ("Lock scale") pins the current variable's range over ALL frames.
  Auto-scaling every frame to its own min/max repaints the same colours onto a
  changing range, so a field that decays by 5x looks identical from frame to
  frame. USER-REQUESTED (2026-08-12) that it be **off by default**, because
  "Auto (fit to data)" has to mean what it says — the frame on screen.

* **The seed** is what a variable's manual range starts at when Auto is unticked
  (#24: nothing should jump at that moment). For a restarted solve the frame on
  screen is the wrong basis — one leg's band saturates every other leg, which is
  #24's own symptom one level up — so a MULTI-leg series seeds from the whole
  series and a single file keeps #24 exactly.

  **The scan for that seed does NOT run inside a paint** (#43). It used to be
  called from ``render``, which meant switching variables in Custom mode blocked
  a repaint for as long as reading every frame takes, with no way to say so: the
  event loop cannot be pumped from inside the paint it would re-enter. It now
  runs in :meth:`seed_range_from_series`, called by the handler that unticks
  Auto, where a "this will take a moment" line can be painted first — and
  switching variables afterwards seeds from the frame on screen instead, with the
  whole-series range explained in the Min/Max tooltip rather than repeated in the
  log on every change.

  **A failed scan is not remembered.** ``_series_seeded`` records the variables
  whose range really did come from a successful whole-series scan, so a transient
  read error does not pin a variable to one frame's numbers for the session: the
  next untick retries. It is keyed on the SCAN rather than on "is a range
  remembered", because a range the user typed must not be re-scanned away.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from app.services.logging_setup import get_logger

_log = get_logger(__name__)


class ResultScaleLockMixin:
    """Pin / seed the colour range of a transient result."""

    def _lock_color_range(self):
        """Pin the colour scale to the current variable's range over ALL frames.

        Skipped unless the user ticked "Lock scale" — auto means the frame on
        screen — and also when the range was set by hand (their choice stands)
        or the file has a single frame (nothing to keep steady). The scan is paid
        once per variable; afterwards the answer is cached on the series.
        """
        if (self._series is None or self._frame_count() < 2
                or not self._clim_auto or not self._scale_locked()):
            return
        var = self._current_var()
        if not var:
            return
        if self._range_lock is not None and self._range_lock_var == var:
            return
        known = self._series.has_global_range(var)
        rng = self.scan_series_range(var)
        if rng is None and not self._series.has_global_range(var):
            return                      # a re-entrant call, or the scan failed
        self._range_lock = rng
        self._range_lock_var = var
        if rng and not known:
            self._log(f"[Results] '{var}' locked to [{rng[0]:.6g}, {rng[1]:.6g}] "
                      "for playback (all frames share one colour scale).")

    def scan_series_range(self, var: str):
        """``var``'s range over EVERY frame of the series, or None.

        The one place that pays for a full scan, so a variable is scanned once
        whichever of its two callers asked — the "Lock scale" box and the
        per-variable seed. Returns None on a re-entrant call or a failed read;
        the answer itself is cached on the series, so asking again is free.

        Both callers are now a CLICK (ticking Lock scale, unticking Auto), so the
        event loop is pumped to paint the "this is going to take a moment" message
        before the scan blocks — an unexplained freeze reads as a hang. It used to
        take a ``pump`` flag because the seed ran inside ``render``, where pumping
        would have re-entered the paint in progress; #43 moved that caller out, so
        the flag had one value left and is gone.
        """
        if self._series is None or not var or self._scanning:
            return None
        known = self._series.has_global_range(var)
        self._scanning = True
        try:
            if not known:
                self._log(f"[Results] scanning {self._frame_count()} frames for "
                          f"the '{var}' range (once per variable)…")
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                QApplication.processEvents()
            try:
                return self._series.global_range(var)
            except (OSError, ValueError) as e:
                _log.warning("global range scan failed for %s: %s", var, e)
                return None
        finally:
            self._scanning = False
            if not known:
                QApplication.restoreOverrideCursor()

    def seed_range_from_series(self):
        """Pin the displayed variable to the WHOLE SERIES' range, once.

        Called by the handler that leaves Auto — never from ``render``. #24 seeds
        an untouched variable from the frame being shown so nothing jumps at that
        moment; across the legs of a restarted solve that is the wrong basis (#32:
        one leg's band saturates every other leg, and the Min/Max boxes then
        describe a range that is not on screen), so a MULTI-leg series seeds from
        the series and a single file keeps #24's rule untouched.

        What #43 changes is WHERE the scan happens. Inside ``render`` it blocked a
        repaint with no way to explain itself — the event loop cannot be pumped
        from inside the paint it would re-enter — so switching variables in Custom
        mode froze the application for as long as reading every frame takes. Here
        the "this will take a moment" line is painted first.

        Four guards, each for its own reason. A variable already scanned is not
        re-scanned. A range the user TYPED is never scanned away — #24's
        manual-over-lock-over-auto precedence is out of scope for #43, and
        "already scanned" does NOT imply it: the first version of this guarded on
        the scan set alone, and typing a range for a variable that had never been
        scanned, then toggling Auto off and on, replaced the user's numbers with
        the series band (measured in review, -999..999 -> 1.0..134.33). A FAILED
        scan is not recorded, so the next untick retries instead of pinning the
        variable to one frame's numbers for the session. And a single-file series
        is left to #24.
        """
        series = getattr(self, "_series", None)
        var = self._current_var()
        if (series is None or not var or series.n_files < 2
                or var in self._series_seeded or var in self._clim_typed):
            return
        rng = self.scan_series_range(var)
        if rng is None:
            return          # not remembered — a transient failure must not pin
        self._series_seeded.add(var)
        self.remember_clim(var, *rng)

    def _on_lock_scale_toggled(self, on: bool):
        """Tick = scan the run and pin its range; untick = back to per-frame auto."""
        if on:
            self._lock_color_range()
        else:
            self._range_lock = None
            self._range_lock_var = ""
            self._log("[Results] colour scale follows each frame again "
                      "(Auto fits the frame on screen).")
        self.render()

    def series_range_hint(self) -> str:
        """One sentence for the Min/Max tooltip about where these numbers came
        from — or "" for an ordinary single-file result.

        The whole-series range is now offered at ONE moment (unticking Auto)
        rather than recomputed whenever the variable changes, so where it is
        available has to be stated somewhere the user is already looking. A log
        line on every variable change was the alternative and is noise.
        """
        series = getattr(self, "_series", None)
        if series is None or series.n_files < 2:
            return ""
        return ("This solve has several legs. Unticking 'Auto (fit to data)' "
                "seeds the range from the WHOLE series (scanned once per "
                "variable); switching variables afterwards seeds from the frame "
                "on screen, so untick again to scan the new one.")

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
        if (self._range_lock is None or not self._clim_auto
                or not self._scale_locked()):
            return None
        if self._range_lock_var != self._current_var():
            return None
        return self._range_lock
