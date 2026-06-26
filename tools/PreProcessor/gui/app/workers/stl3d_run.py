from __future__ import annotations
import os
import re
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal

# STL3d echoes "<i> tracing" once per x-slice as it ray-traces, so the current
# slice index over the total Nx gives a faithful progress fraction.
_TRACE_RE = re.compile(r"^\s*(\d+)\s+tracing\b")


class Stl3dWorker(QThread):
    """Runs the interactive STL3d preprocessor as ``./stl3d < para.in``.

    The controller stages a work dir (STL copied in, para.in written), then this
    worker feeds para.in on stdin — mirroring the verified console workflow — and
    streams stdout to the log while reporting per-slice progress.
    """

    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)        # 0..100
    finished_signal = pyqtSignal(int)        # return code (0 ok; <0 cancelled/error)

    def __init__(self, binary: str, work_dir: str, para_path: str, nx: int,
                 threads: int = 1):
        super().__init__()
        self._binary = binary
        self._work_dir = work_dir
        self._para_path = para_path
        self._nx = max(int(nx), 1)
        self._threads = max(int(threads), 1)   # OMP_NUM_THREADS (1 = serial)
        self._process: subprocess.Popen | None = None
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        if self._process and self._process.poll() is None:
            self._process.terminate()

    def run(self):
        self._cancelled = False
        self.progress_signal.emit(0)
        # OpenMP thread count (the binary is OpenMP-enabled; OMP_NUM_THREADS=1
        # makes it run single-threaded, which is the default).
        env = os.environ.copy()
        env["OMP_NUM_THREADS"] = str(self._threads)
        try:
            with open(self._para_path, "rb") as stdin_f:
                self._process = subprocess.Popen(
                    [self._binary],
                    stdin=stdin_f,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    cwd=self._work_dir,
                    env=env,
                )
        except OSError as e:
            self.log_signal.emit(f"[STL3d] failed to start: {e}")
            self.finished_signal.emit(-1)
            return

        last_pct = 0
        last_logged_pct = -1
        for line in self._process.stdout:
            if self._cancelled:
                self._process.terminate()
                self.log_signal.emit("STL3d cancelled by user.")
                self.finished_signal.emit(-2)
                return
            stripped = line.rstrip()
            if not stripped:
                continue
            m = _TRACE_RE.match(stripped)
            if m:
                # The per-slice "<n> tracing" lines drive the progress bar but are
                # too noisy for the log. Don't echo them; instead log a throttled
                # percentage every 10% so the user sees it is working, not stuck.
                # +1 so the final slice reads as ~100%; ray tracing dominates runtime.
                pct = min(99, int(100 * (int(m.group(1)) + 1) / self._nx))
                if pct > last_pct:
                    last_pct = pct
                    self.progress_signal.emit(pct)
                bucket = (pct // 10) * 10
                if bucket > last_logged_pct:
                    last_logged_pct = bucket
                    self.log_signal.emit(f"[STL3d] ray tracing… {bucket}%")
                continue
            self.log_signal.emit(f"[STL3d] {stripped}")

        self._process.wait()
        rc = self._process.returncode
        if self._cancelled:
            # cancel() terminate()s the process, which usually closes stdout via
            # EOF before the in-loop cancel branch runs, so wait() returns the
            # SIGTERM code. Report it as the cancel sentinel (-2), not a failure.
            self.finished_signal.emit(-2)
            return
        if rc == 0:
            self.progress_signal.emit(100)
        else:
            self.log_signal.emit(f"[STL3d] exited with code {rc}")
        self.finished_signal.emit(rc)
