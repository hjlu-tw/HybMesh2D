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

    def __init__(self, binary: str, work_dir: str, para_path: str, nx: int):
        super().__init__()
        self._binary = binary
        self._work_dir = work_dir
        self._para_path = para_path
        self._nx = max(int(nx), 1)
        self._process: subprocess.Popen | None = None
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        if self._process and self._process.poll() is None:
            self._process.terminate()

    def run(self):
        self._cancelled = False
        self.progress_signal.emit(0)
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
                )
        except OSError as e:
            self.log_signal.emit(f"[STL3d] failed to start: {e}")
            self.finished_signal.emit(-1)
            return

        last_pct = 0
        for line in self._process.stdout:
            if self._cancelled:
                self._process.terminate()
                self.log_signal.emit("STL3d cancelled by user.")
                self.finished_signal.emit(-2)
                return
            stripped = line.rstrip()
            if not stripped:
                continue
            self.log_signal.emit(f"[STL3d] {stripped}")
            m = _TRACE_RE.match(stripped)
            if m:
                # +1 so the final slice reads as ~100%; ray tracing dominates runtime.
                pct = min(99, int(100 * (int(m.group(1)) + 1) / self._nx))
                if pct > last_pct:
                    last_pct = pct
                    self.progress_signal.emit(pct)

        self._process.wait()
        rc = self._process.returncode
        if rc == 0:
            self.progress_signal.emit(100)
        elif not self._cancelled:
            self.log_signal.emit(f"[STL3d] exited with code {rc}")
        self.finished_signal.emit(rc)
