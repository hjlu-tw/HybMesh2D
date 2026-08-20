"""Batch queue controller: owns the dialog and the worker.

The dialog is created once and re-shown, not rebuilt: a queue the user spent time
assembling must survive closing the window, and a batch left running must keep running
while they work on something else.
"""
from __future__ import annotations

from app.services.logging_setup import get_logger
from app.utils import confirm, report_info

_log = get_logger(__name__)


class BatchControllerMixin:
    def open_batch_dialog(self):
        """Show the batch queue (creating it on first use)."""
        dlg = getattr(self, "_batch_dialog", None)
        if dlg is None:
            from app.views.batch_dialog import BatchDialog
            # Parented to the main window so it inherits the app icon and is
            # destroyed with it. Deliberately NOT keep_on_top()'d, unlike the
            # editing pop-ups: a batch runs for minutes and the user is meant to
            # keep working, so this window must be free to go behind the main
            # one instead of jumping back on top at every activation.
            dlg = BatchDialog(self.main_window)
            dlg.log_sink = self._batch_log
            dlg.run_requested.connect(self.run_batch_queue)
            dlg.cancel_requested.connect(self.cancel_batch_queue)
            self._batch_dialog = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        return dlg

    def _batch_log(self, msg: str):
        """Batch output goes to the log panel the user already watches."""
        self.log(str(msg))

    # ── running ──────────────────────────────────────────────────────────
    def run_batch_queue(self):
        dlg = getattr(self, "_batch_dialog", None)
        if dlg is None:
            return
        if getattr(self, "_batch_worker", None) is not None:
            report_info(dlg, "Batch Already Running",
                        "A batch is already running. Cancel it first.")
            return
        runnable = [j for j in dlg.jobs if j.config is not None]
        if not runnable:
            report_info(dlg, "Nothing to Run",
                        "Queue at least one readable pipeline script or workspace.")
            return

        # Ask before overwriting: output paths derive from the case name, so a shared
        # name means one case silently destroying another's mesh. The dialog already
        # shows the warning; this is the last point at which it is still cheap to stop.
        from app.services import batch_runner
        collisions = batch_runner.find_collisions(runnable)
        if collisions:
            names = ", ".join(sorted(collisions))
            if not confirm(dlg, "Case Names Collide",
                           f"These case names are used by more than one job: {names}. "
                           f"Their outputs would overwrite each other.\n\n"
                           f"Run anyway?",
                           headless_default=True):
                return

        # Reset previous results so a re-run does not show last time's statuses.
        for job in dlg.jobs:
            if job.config is not None:
                job.status, job.error, job.seconds = "pending", "", 0.0
                job.artifacts = {}

        from app.workers.batch_run import BatchRunWorker
        worker = BatchRunWorker(dlg.jobs,
                                run_solver=dlg.run_solver_cb.isChecked(),
                                run_ib=dlg.run_ib_cb.isChecked())
        worker.log_line.connect(self._batch_log)
        worker.progress.connect(dlg.set_progress)
        worker.job_finished.connect(dlg.update_row)
        worker.finished_signal.connect(self._on_batch_finished)
        worker.finished.connect(lambda: self._retire_batch_worker(worker))
        self._batch_worker = worker

        dlg.set_running(True)
        # The batch drives the mesher/solver itself; claiming the main progress bar
        # would fight the per-stage owners. The dialog has its own.
        self._batch_log(f"[Batch] starting {len(runnable)} case(s)…")
        worker.start()

    def cancel_batch_queue(self):
        worker = getattr(self, "_batch_worker", None)
        if worker is None:
            return
        self._batch_log("[Batch] cancelling — stopping the running case and skipping "
                        "the rest of the queue.")
        worker.cancel()

    def _on_batch_finished(self, summary: dict):
        dlg = getattr(self, "_batch_dialog", None)
        if dlg is not None:
            dlg.set_running(False)
            dlg.show_summary(summary)
        failed = len(summary.get("failed", []))
        aborted = summary.get("aborted")
        if aborted:
            _log.warning("batch aborted: %s", aborted)
        elif failed:
            _log.info("batch finished with %d failed case(s)", failed)

    def _retire_batch_worker(self, worker):
        """Drop the reference once the QThread has actually unwound.

        Held until ``finished`` (not ``finished_signal``) so a still-unwinding thread
        keeps its last reference and Qt cannot report "destroyed while running".
        """
        if getattr(self, "_batch_worker", None) is worker:
            self._batch_worker = None
        self._retiring_workers.add(worker)
        worker.deleteLater()
        self._retiring_workers.discard(worker)
