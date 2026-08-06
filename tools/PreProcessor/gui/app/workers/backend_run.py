import subprocess
from PyQt6.QtCore import QThread, pyqtSignal

from app.services.env_setup import mesher_env
from app.workers.exit_codes import RC_EXCEPTION, RC_CANCELLED, RC_TIMEOUT
from app.workers.proc_util import popen_kwargs, stop_process_async, kill_process


class BackendWorker(QThread):
    """Runs the C++ surface_resampler binary in a background thread."""

    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)

    def __init__(self, executable_path: str, config_path: str):
        super().__init__()
        self.executable_path = executable_path
        self.config_path = config_path
        self._process: subprocess.Popen | None = None
        self._cancelled = False

    def cancel(self):
        # Non-blocking SIGTERM of the whole process tree, escalating off-thread
        # (see app/workers/proc_util.py).
        self._cancelled = True
        stop_process_async(self._process)

    def run(self):
        try:
            import os
            self.log_signal.emit(
                f"Running: {self.executable_path} {self.config_path}")
            self._cancelled = False
            cwd = os.path.dirname(os.path.dirname(os.path.abspath(self.executable_path)))
            # Same loader-path handover as the mesher: surface_resampler is built
            # from the same tree and must not depend on a shell wrapper's export.
            self._process = subprocess.Popen(
                [self.executable_path, self.config_path],
                env=mesher_env(),
                **popen_kwargs(cwd=cwd),
            )

            for line in self._process.stdout:
                if self._cancelled:
                    stop_process_async(self._process)
                    self.log_signal.emit("Backend cancelled by user.")
                    self.finished_signal.emit(RC_CANCELLED)
                    return
                stripped = line.rstrip()
                if stripped:
                    self.log_signal.emit(stripped)

            if self._cancelled:
                stop_process_async(self._process)
                self.log_signal.emit("Backend cancelled by user.")
                self.finished_signal.emit(RC_CANCELLED)
                return

            self._process.wait(timeout=600)  # 10 min timeout
            self.finished_signal.emit(self._process.returncode)
        except subprocess.TimeoutExpired:
            kill_process(self._process)
            self.log_signal.emit("Backend timed out (10 min).")
            self.finished_signal.emit(RC_TIMEOUT)
        except Exception as e:
            self.log_signal.emit(f"Failed to start backend: {e}")
            self.finished_signal.emit(RC_EXCEPTION)
