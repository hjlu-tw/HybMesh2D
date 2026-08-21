"""Autosave / crash-recovery / clean-shutdown lifecycle for AppController,
extracted from controller.py. Methods run on the composed instance."""
from __future__ import annotations
import os

from PyQt6.QtWidgets import QApplication

from app.workers.proc_util import kill_process

from app.services.logging_setup import get_logger

_log = get_logger(__name__)

# Shutdown join budget, per worker. An unbounded ``QThread.wait()`` on the GUI
# thread is how a hung backend turns "close the window" into "kill -9 the app":
# the event loop stops, nothing repaints, and there is no cancel path left. We
# instead give each worker a bounded window, escalate to SIGKILL on its child
# process, then give up and let process exit reap it.
_JOIN_MS = 4000          # after cancel() (SIGTERM already sent)
_JOIN_AFTER_KILL_MS = 2000   # after SIGKILL on the child process

# Workers that outlived their join budget. Module-level so the reference (and
# therefore the QThread) survives until the interpreter exits: dropping the last
# reference to a *running* QThread aborts with "QThread: Destroyed while thread
# is still running", turning a slow shutdown into a crash report.
_abandoned_workers: list = []


class LifecycleControllerMixin:
    def _maybe_recover_autosave(self) -> bool:
        """Offer to restore an autosave left behind by an unclean shutdown."""
        try:
            if not os.path.exists(self._autosave_path):
                return False
            # Headless (tests, CI, batch runs): recovery must NOT happen
            # silently, so the default is False — an offscreen run starts clean
            # rather than inheriting a stranger's autosave. This is also what lets
            # the full AppController be built off-screen for end-to-end testing.
            from app.utils import confirm, is_headless
            if is_headless():
                return False
            if confirm(
                    self.main_window, "Recover Unsaved Work",
                    "Unsaved work from a previous session was found — the "
                    "application may have closed unexpectedly.\n\nRecover it now?",
                    headless_default=False):
                self._read_workspace_file(self._autosave_path)
                self.log("Recovered autosaved workspace.")
                return len(self.sessions) > 0
            # User declined: drop the stale autosave so we don't ask again.
            os.remove(self._autosave_path)
        except Exception as e:
            try:
                self.log(f"Autosave recovery failed: {e}")
            except Exception:
                _log.debug(
                    "could not report the autosave-recovery failure to the log "
                    "panel", exc_info=True)
        return False

    def _autosave(self):
        """Periodically checkpoint modified sessions to the stable autosave path."""
        try:
            if not self.sessions:
                return
            # Checkpoint when EITHER the CAD geometry or the project-level
            # configuration (Mesh / Solver / IB panels) has changed. Keying only
            # off geometry meant a session spent tuning the domain, BL and BCs was
            # never checkpointed at all — the crash-recovery net had a hole exactly
            # where the un-reproducible work was.
            if (not any(getattr(s, "is_geometry_modified", False) for s in self.sessions)
                    and not self.project_is_dirty()):
                return
            self._write_workspace_file(self._autosave_path)
            # Recovered: note it once so the engineer knows the safety net is
            # working again after a prior failure.
            if getattr(self, "_autosave_failed", False):
                self._autosave_failed = False
                self.log(
                    "[Autosave] resumed — workspace checkpoint saved again.")
        except Exception as e:
            # A background autosave must never interrupt the user (e.g. a
            # transient NaN while editing a live curve), but it must not die
            # silently either: warn ONCE so the engineer knows the crash-recovery
            # net has stopped and they should save manually. Subsequent identical
            # failures are suppressed until a save succeeds again.
            if not getattr(self, "_autosave_failed", False):
                self._autosave_failed = True
                try:
                    self.log(
                        f"[Autosave] [WARNING] auto-save failed and is paused: {e}. "
                        "Save your workspace manually (File > Save Workspace).")
                except Exception:
                    _log.debug(
                        "could not report the autosave failure to the log "
                        "panel", exc_info=True)

    # ── Bounded worker shutdown ──────────────────────────────────────────
    def _log_quiet(self, msg: str):
        """Log during shutdown without letting a torn-down panel raise."""
        try:
            self.log(msg)
        except Exception:
            _log.debug("log panel unavailable during shutdown", exc_info=True)

    def _join_worker(self, worker, label: str) -> bool:
        """Cancel + join one worker within the shutdown budget.

        Escalates in three steps — ``cancel()`` (SIGTERM to the child's process
        group), then SIGKILL on the child, then give up — and returns True only
        if the thread actually finished. A worker that survives all of it is
        parked in ``_abandoned_workers`` so its QThread is not destroyed while
        still running; the OS reaps it at process exit.
        """
        if worker is None or not worker.isRunning():
            return True

        cancel = getattr(worker, "cancel", None)
        if callable(cancel):
            try:
                cancel()          # non-blocking; SIGTERMs the child's tree
            except Exception:
                _log.warning(
                    "worker cancel() raised; falling back to a bounded "
                    "join", exc_info=True)
        if worker.wait(_JOIN_MS):
            return True

        # Still running. The pure-Python workers (fit check, profile extruder)
        # have no child to kill and no cancel path — nothing more to escalate to.
        proc = getattr(worker, "_process", None)
        if proc is not None:
            self._log_quiet(f"[Shutdown] {label} did not stop; killing it.")
            kill_process(proc)
            if worker.wait(_JOIN_AFTER_KILL_MS):
                return True

        self._log_quiet(
            f"[Shutdown] [WARNING] {label} is still running; leaving it to be "
            "reaped on exit rather than blocking the shutdown.")
        _abandoned_workers.append(worker)
        return False

    def _shutdown_workers(self):
        """Stop every background worker/loader thread within a bounded budget."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QCursor

        app = QApplication.instance()
        headless = app is not None and app.platformName() in ("offscreen", "minimal")
        if app is not None and not headless:
            # The joins below block the event loop, so give the user the one bit
            # of feedback still possible: a wait cursor.
            app.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            named = [
                # Batch first: it is the only worker that can be minutes or hours
                # from finishing, and it owns a child process tree of its own. Joining
                # a shorter worker ahead of it just spends the shutdown budget waiting.
                (getattr(self, "_batch_worker", None), "batch queue"),
                (getattr(self, "_worker", None), "CAD resample"),
                (getattr(self, "_mesh_worker", None), "mesh generator"),
                (getattr(self, "_solver_worker", None), "solver"),
                (getattr(self, "_stl3d_worker", None), "immersed-solid (STL3d)"),
                (getattr(self, "_fit_worker", None), "STL/phi fit check"),
                (getattr(self, "_extrude_worker", None), "profile extruder"),
            ]
            # Workers already delivered but not yet finished() (see
            # _retiring_workers) are about to end; join them so none is destroyed
            # mid-run on exit.
            named += [(w, "retiring worker")
                      for w in list(getattr(self, "_retiring_workers", ()))]
            for worker, label in named:
                self._join_worker(worker, label)

            # Geometry/seed preview loaders: pure-Python QThreads with no child
            # process, so a bounded wait is the only escalation available.
            mcv = self.main_window.mesh_canvas_view
            loaders = list(getattr(mcv, "_geom_loader_threads", []))
            loaders += list(getattr(mcv, "_seed_loader_threads", []))
            last = getattr(mcv, "_geom_loader_thread", None)
            if last is not None and last not in loaders:
                loaders.append(last)
            for t in loaders:
                if t is None or not t.isRunning():
                    continue
                try:
                    t.loaded_signal.disconnect()
                except TypeError:
                    pass
                if not t.wait(_JOIN_MS):
                    _abandoned_workers.append(t)
        finally:
            if app is not None and not headless:
                app.restoreOverrideCursor()

    def cleanup_temp_dir(self):
        """Clean up the dedicated temp directory and all its contents on app exit."""
        if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
            import shutil
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except Exception:
                _log.debug("could not remove the session temp directory", exc_info=True)

    def restart_gui(self) -> bool:
        """Close this window the normal way and, only if it closed, open a fresh GUI.

        The order is the whole feature. Spawning first and *then* asking "discard
        unsaved changes?" leaves two GUIs running when the answer is No — the exact
        opposite of what the button is for. So the close goes first, through
        :meth:`MainWindow.closeEvent` → :meth:`handle_close_event`, which is also
        why there is no second copy of the unsaved-work question here: that method
        already covers both modified geometry sessions and a dirty Mesh/Solver/IB
        configuration, saves the layout, joins the workers within their budget and
        removes the autosave file so the new instance does not offer to recover the
        session the user just chose to leave.

        **The outcome is read from ``close()``'s return value, not from
        ``isVisible()``.** Measured under the offscreen platform: a cancelled close
        on a window that was never shown reports ``isVisible() == False`` and
        ``isHidden() == True`` — indistinguishable from a successful one — while
        ``close()`` returns False exactly when the close event was ignored, shown
        or not.
        """
        from app.services import gui_restart

        # Validate while there is still a window to report an error in: after the
        # close there is no GUI left to tell.
        reason = gui_restart.preflight()
        if reason:
            from app.utils import report_error
            report_error(self.main_window, "Cannot Start a New Session", reason)
            self.log(f"[ERROR] Restart not possible: {reason.splitlines()[0]}")
            return False

        self.log("Restarting: closing this window, then opening a new empty session...")
        if not self.main_window.close():
            self.log("Restart cancelled - this window stays open and nothing was launched.")
            return False

        try:
            gui_restart.launch()
        except OSError as e:
            # The window is gone, so the log PANEL is gone with it and there is no
            # parent left to put a modal on; user_log's own file mirror is the only
            # place this can still be said. That residue is the accepted cost of
            # closing first — :func:`gui_restart.preflight` is what keeps the
            # foreseeable failures (bad interpreter, missing script) on the side of
            # the close where a dialog still works.
            self.log(f"[ERROR] Could not start the new session: {e}")
            _log.warning("restart: launching a new GUI failed", exc_info=True)
            return False
        return True

    def handle_close_event(self) -> bool:
        """Return True if the app can close, False to cancel closing."""
        # Unsaved work is not only CAD geometry: an unsaved Mesh / Solver / IB
        # configuration is just as expensive to recreate, and used to be discarded
        # without a word.
        modified_sessions = [s for s in self.sessions if s.is_geometry_modified]
        project_dirty = self.project_is_dirty()
        if modified_sessions or project_dirty:
            what = []
            if modified_sessions:
                names = ", ".join([s.display_name for s in modified_sessions])
                what.append(f"Geometry sessions: {names}")
            if project_dirty:
                what.append("Mesh / Solver / Immersed-Solid configuration")
            from app.utils import confirm
            # headless_default True: a batch run has to be able to exit. There is
            # nobody to answer, and refusing to close would hang the process.
            if not confirm(
                    self.main_window, "Unsaved Changes",
                    "The following have unsaved changes:\n"
                    + "\n".join(f"  • {w}" for w in what)
                    + "\n\nDo you want to discard them and exit?"):
                return False
        
        # Auto-save workspace on successful exit (disabled to start clean)

        # Remember the layout BEFORE tearing anything down, while the window and
        # its panels still describe what the user was looking at.
        from app.services.ui_state import save_ui_state
        save_ui_state(self.main_window)

        # Cancel and join every background worker/thread, each within a bounded
        # budget so a wedged backend cannot make the app unclosable.
        self._shutdown_workers()

        # Clean shutdown: stop autosave and remove its file so the next launch
        # does not offer to "recover" an intentionally-closed session.
        try:
            if getattr(self, "_autosave_timer", None) is not None:
                self._autosave_timer.stop()
            ap = getattr(self, "_autosave_path", None)
            if ap and os.path.exists(ap):
                os.remove(ap)
        except Exception:
            _log.debug(
                "could not stop the autosave timer / remove its "
                "file", exc_info=True)

        try:
            self.main_window.canvas_view.clear()
            self.main_window.mesh_canvas_view.clear_mesh()
        except Exception:
            _log.debug("could not clear the canvases on shutdown", exc_info=True)
        return True
