import subprocess
from PyQt6.QtCore import QThread, pyqtSignal


class BackendWorker(QThread):
    """Runs the C++ surface_resampler binary in a background thread."""

    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)

    def __init__(self, executable_path: str, config_path: str):
        super().__init__()
        self.executable_path = executable_path
        self.config_path = config_path

    def run(self):
        try:
            self.log_signal.emit(
                f"Running: {self.executable_path} {self.config_path}")
            process = subprocess.Popen(
                [self.executable_path, self.config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,          # line-buffered
            )
            for line in process.stdout:
                stripped = line.rstrip()
                if stripped:
                    self.log_signal.emit(stripped)
            process.wait()
            self.finished_signal.emit(process.returncode)
        except Exception as e:
            self.log_signal.emit(f"Failed to start backend: {e}")
            self.finished_signal.emit(-1)
