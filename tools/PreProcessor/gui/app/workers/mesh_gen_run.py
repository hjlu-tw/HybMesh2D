from __future__ import annotations
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal

class MeshGenWorker(QThread):
    """Runs the C++ HybMesh2D binary in a background thread."""

    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)

    def __init__(self, executable_path: str, config_path: str):
        super().__init__()
        self.executable_path = executable_path
        self.config_path = config_path
        self._process: subprocess.Popen | None = None
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        if self._process and self._process.poll() is None:
            self._process.terminate()

    def run(self):
        try:
            import os
            self.log_signal.emit(
                f"Running: {self.executable_path} -conf {self.config_path}"
            )
            self._cancelled = False
            cwd = os.path.dirname(os.path.dirname(os.path.abspath(self.executable_path)))
            self._process = subprocess.Popen(
                [self.executable_path, "-conf", self.config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,  # line-buffered
                cwd=cwd,
            )

            
            for line in self._process.stdout:
                if self._cancelled:
                    self._process.terminate()
                    self.log_signal.emit("Mesh generation cancelled by user.")
                    self.finished_signal.emit(-2)
                    return
                stripped = line.rstrip()
                if stripped:
                    self.log_signal.emit(stripped)

            if self._cancelled:
                self._process.terminate()
                self.log_signal.emit("Mesh generation cancelled by user.")
                self.finished_signal.emit(-2)
                return

            self._process.wait(timeout=600)  # 10 min timeout
            self.finished_signal.emit(self._process.returncode)
        except subprocess.TimeoutExpired:
            if self._process:
                self._process.kill()
            self.log_signal.emit("Mesh generation timed out (10 min).")
            self.finished_signal.emit(-3)
        except Exception as e:
            self.log_signal.emit(f"Failed to start mesh generator: {e}")
            self.finished_signal.emit(-1)
