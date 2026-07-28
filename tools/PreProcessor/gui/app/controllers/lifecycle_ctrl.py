"""Autosave / crash-recovery / clean-shutdown lifecycle for AppController,
extracted from controller.py. Methods run on the composed instance."""
from __future__ import annotations
import os

from PyQt6.QtWidgets import QApplication


class LifecycleControllerMixin:
    def _maybe_recover_autosave(self) -> bool:
        """Offer to restore an autosave left behind by an unclean shutdown."""
        try:
            if not os.path.exists(self._autosave_path):
                return False
            # Headless (tests, CI, batch runs): a modal recovery prompt would
            # block construction forever with no user to answer it. On a headless
            # Qt platform there is no screen to show it on anyway, so skip the
            # prompt and start clean — this is what lets the full AppController be
            # built off-screen for end-to-end testing.
            app = QApplication.instance()
            if app is not None and app.platformName() in ("offscreen", "minimal"):
                return False
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self.main_window,
                "Recover Unsaved Work",
                "Unsaved work from a previous session was found — the application "
                "may have closed unexpectedly.\n\nRecover it now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._read_workspace_file(self._autosave_path)
                self.main_window.log_panel.log("Recovered autosaved workspace.")
                return len(self.sessions) > 0
            # User declined: drop the stale autosave so we don't ask again.
            os.remove(self._autosave_path)
        except Exception as e:
            try:
                self.main_window.log_panel.log(f"Autosave recovery failed: {e}")
            except Exception:
                pass
        return False

    def _autosave(self):
        """Periodically checkpoint modified sessions to the stable autosave path."""
        try:
            if not self.sessions:
                return
            if not any(getattr(s, "is_geometry_modified", False) for s in self.sessions):
                return
            self._write_workspace_file(self._autosave_path)
            # Recovered: note it once so the engineer knows the safety net is
            # working again after a prior failure.
            if getattr(self, "_autosave_failed", False):
                self._autosave_failed = False
                self.main_window.log_panel.log(
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
                    self.main_window.log_panel.log(
                        f"[Autosave] [WARNING] auto-save failed and is paused: {e}. "
                        "Save your workspace manually (File > Save Workspace).")
                except Exception:
                    pass

    def cleanup_temp_dir(self):
        """Clean up the dedicated temp directory and all its contents on app exit."""
        if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
            import shutil
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except Exception:
                pass

    def handle_close_event(self) -> bool:
        """Return True if the app can close, False to cancel closing."""
        modified_sessions = [s for s in self.sessions if s.is_geometry_modified]
        if modified_sessions:
            names = ", ".join([s.display_name for s in modified_sessions])
            from PyQt6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self.main_window,
                "Unsaved Changes",
                f"The following sessions have unsaved changes:\n{names}\n\nDo you want to discard them and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return False
        
        # Auto-save workspace on successful exit (disabled to start clean)

        # Cancel and wait for all running background workers/threads to avoid crash on exit
        if hasattr(self, "_worker") and self._worker is not None:
            if self._worker.isRunning():
                self._worker.cancel()
                self._worker.wait()
                
        if hasattr(self, "_mesh_worker") and self._mesh_worker is not None:
            if self._mesh_worker.isRunning():
                self._mesh_worker.cancel()
                self._mesh_worker.wait()

        # Immersed-solid (STL3d) workers. Stl3dWorker supports cancel(); the fit
        # check and profile extruder have no cancel(), so wait() them out. All
        # three are QThreads on this controller and would abort with "QThread
        # destroyed while running" if the window closed mid-run without a join.
        stl3d_worker = getattr(self, "_stl3d_worker", None)
        if stl3d_worker is not None and stl3d_worker.isRunning():
            stl3d_worker.cancel()
            stl3d_worker.wait()
        for attr in ("_fit_worker", "_extrude_worker"):
            w = getattr(self, attr, None)
            if w is not None and w.isRunning():
                w.wait()
        # Workers delivered but not yet finished() (see _retiring_workers): about
        # to terminate, but join them so none is destroyed mid-run on exit.
        for w in list(getattr(self, "_retiring_workers", ())):
            if w is not None and w.isRunning():
                w.wait()

        mcv = self.main_window.mesh_canvas_view
        loader_threads = list(getattr(mcv, "_geom_loader_threads", []))
        # Seed previews use their own loader threads; join them too so none is
        # destroyed mid-run on exit ("QThread destroyed while running").
        loader_threads += list(getattr(mcv, "_seed_loader_threads", []))
        last = getattr(mcv, "_geom_loader_thread", None)
        if last is not None and last not in loader_threads:
            loader_threads.append(last)
        for t in loader_threads:
            if t is not None and t.isRunning():
                try:
                    t.loaded_signal.disconnect()
                except TypeError:
                    pass
                t.wait()

        # Clean shutdown: stop autosave and remove its file so the next launch
        # does not offer to "recover" an intentionally-closed session.
        try:
            if getattr(self, "_autosave_timer", None) is not None:
                self._autosave_timer.stop()
            ap = getattr(self, "_autosave_path", None)
            if ap and os.path.exists(ap):
                os.remove(ap)
        except Exception:
            pass

        try:
            self.main_window.canvas_view.clear()
            self.main_window.mesh_canvas_view.clear_mesh()
        except Exception:
            pass
        return True
