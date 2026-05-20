import subprocess
from PyQt6.QtCore import QThread, pyqtSignal

class BackendWorker(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)

    def __init__(self, executable_path, config_path):
        super().__init__()
        self.executable_path = executable_path
        self.config_path = config_path

    def run(self):
        try:
            self.log_signal.emit(f"Running: {self.executable_path} {self.config_path}")
            # Use subprocess.Popen to capture output line by line
            process = subprocess.Popen(
                [self.executable_path, self.config_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1 # Line buffered
            )
            
            for line in process.stdout:
                self.log_signal.emit(line.strip())
                
            process.wait()
            self.finished_signal.emit(process.returncode)
        except Exception as e:
            self.log_signal.emit(f"Failed to start backend: {str(e)}")
            self.finished_signal.emit(-1)
