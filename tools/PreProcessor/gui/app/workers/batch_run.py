"""QThread wrapper around :func:`services.batch_runner.run_batch`.

A batch is the one operation in this GUI that can plausibly run for hours, which changes
what Cancel has to mean. ``run_batch`` polls ``should_stop()`` between cases — enough to
stop the *queue* at a clean boundary, and deliberately so, because aborting between cases
never leaves a half-written output directory. On its own, though, it would make Cancel
take effect only after the current mesh or solve finished: a button that claims to stop
and then does nothing visible for twenty minutes.

So this worker does both. It also receives every stage subprocess through ``on_process``
and terminates the live one, which is what actually stops the work in flight. The
escalation goes through ``proc_util.stop_process_async`` (SIGTERM → grace → SIGKILL over
the child's process group), never a bare ``terminate()``: a stage is typically a process
tree (mpirun ranks, gmsh helpers) and killing only the direct child orphans the rest.
"""
from __future__ import annotations

import threading

from PyQt6.QtCore import QThread, pyqtSignal

from app.services import batch_runner
from app.services.logging_setup import get_logger
from app.workers.proc_util import stop_process_async

_log = get_logger(__name__)


class BatchRunWorker(QThread):
    """Runs a list of :class:`BatchJob` off the GUI thread.

    ``job_finished`` fires per case so the queue table updates as it goes rather than
    only at the end — for a long batch, a table that stays blank until completion is
    indistinguishable from a hang.
    """

    log_line = pyqtSignal(str)
    progress = pyqtSignal(int, int, str)          # done, total, label
    job_finished = pyqtSignal(int)                # index into `jobs`
    finished_signal = pyqtSignal(dict)            # the summary dict

    def __init__(self, jobs, run_solver: bool = True, run_ib: bool = True,
                 parent=None):
        super().__init__(parent)
        self.jobs = jobs
        self._run_solver = run_solver
        self._run_ib = run_ib
        # Set from the GUI thread, read from the worker: an Event rather than a bool so
        # the cross-thread hand-off is explicit rather than relying on the GIL.
        self._stop = threading.Event()
        self._proc = None
        self._proc_lock = threading.Lock()
        self.summary: dict = {}

    # ── control ──────────────────────────────────────────────────────────
    def cancel(self) -> None:
        """Stop the queue AND the case currently running. Returns immediately."""
        self._stop.set()
        with self._proc_lock:
            proc = self._proc
        if proc is not None:
            # Async: this is called on the GUI thread, and SIGTERM→grace→SIGKILL takes
            # seconds. Blocking here would freeze the window while it escalated.
            stop_process_async(proc)

    def is_cancelled(self) -> bool:
        return self._stop.is_set()

    # ── worker ───────────────────────────────────────────────────────────
    def _note_process(self, proc) -> None:
        with self._proc_lock:
            self._proc = proc
        # A cancel that arrived while the process was starting would otherwise be
        # missed: the flag was already set, but there was no child to signal yet.
        if self._stop.is_set():
            stop_process_async(proc)

    def run(self):
        done = {"n": 0}

        def _log(msg):
            self.log_line.emit(str(msg))

        def _progress(i, total, label):
            # Emitted BEFORE each case starts, so the table can mark it running.
            self.progress.emit(i, total, label)
            # Anything already finished has its final status; tell the view which.
            while done["n"] < i:
                self.job_finished.emit(done["n"])
                done["n"] += 1

        try:
            self.summary = batch_runner.run_batch(
                self.jobs, log=_log, progress=_progress,
                run_solver=self._run_solver, run_ib=self._run_ib,
                should_stop=self._stop.is_set, on_process=self._note_process)
        except Exception as e:
            # run_batch already contains each case's failure; reaching here means the
            # batch machinery itself broke. Report it as the batch result rather than
            # letting the thread die silently with the dialog stuck on "running".
            _log.warning("batch run failed outside a case", exc_info=True)
            self.log_line.emit(f"[Batch] [ERROR] batch aborted: {e}")
            self.summary = {"total": len(self.jobs), "ok": [], "failed": [],
                            "skipped": [], "collisions": {}, "seconds": 0.0,
                            "aborted": str(e)}
        finally:
            with self._proc_lock:
                self._proc = None
            # Flush the status of every case the progress callback did not cover
            # (the last one, and all of them if the batch was cancelled early).
            for i in range(done["n"], len(self.jobs)):
                self.job_finished.emit(i)
            self.finished_signal.emit(self.summary)
