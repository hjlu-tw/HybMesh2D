from __future__ import annotations
import re
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal

from app.services.env_setup import mesher_env, gmsh_missing_hint
from app.workers.exit_codes import RC_EXCEPTION, RC_CANCELLED, RC_TIMEOUT
from app.workers.proc_util import popen_kwargs, stop_process_async, kill_process

# Ordered stage markers emitted by HybMesh2D on stdout, mapped to a coarse
# completion percentage. Matched as substrings, in order, so progress is
# monotonic even if some lines are missing. The boundary-layer stage (5–55%)
# is refined further from the "Boundary Layer progress: a / b" line.
_STAGE_PCT = [
    ("Step: Generating", 5),
    ("Validating final boundary layer", 55),
    ("Global Transverse Balancing", 58),
    ("Setting up Gmsh", 62),
    ("Generating far-field", 70),
    ("Gmsh generation finished", 85),
    ("Syncing elements", 90),
    ("Finalizing Gmsh", 95),
    ("completed successfully", 100),
]
_BL_RE = re.compile(r"Boundary Layer progress:\s*(\d+)\s*/\s*(\d+)")


class MeshGenWorker(QThread):
    """Runs the C++ HybMesh2D binary in a background thread."""

    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)
    progress_signal = pyqtSignal(int)  # 0..100, best-effort from stdout markers

    def __init__(self, executable_path: str, config_path: str):
        super().__init__()
        self.executable_path = executable_path
        self.config_path = config_path
        self._process: subprocess.Popen | None = None
        self._cancelled = False
        self._progress = 0

    def _emit_progress(self, text: str):
        """Parse a stdout chunk for stage/BL markers and emit monotonic progress."""
        pct = None
        for marker, value in _STAGE_PCT:
            if marker in text:
                pct = value
        # The carriage-return-updated BL line may arrive as one blob; take the
        # last "a / b" it contains for the most recent fraction.
        bl = None
        for bl in _BL_RE.finditer(text):
            pass
        if bl is not None:
            a, b = int(bl.group(1)), int(bl.group(2))
            if b > 0:
                bl_pct = 5 + int(50 * min(a, b) / b)
                pct = bl_pct if pct is None else max(pct, bl_pct)
        if pct is not None and pct > self._progress:
            self._progress = pct
            self.progress_signal.emit(pct)

    def cancel(self):
        # Non-blocking: SIGTERM the whole process tree now and let the escalation
        # to SIGKILL happen off-thread, so the Cancel button never freezes the UI
        # (and a mesher that ignores SIGTERM still dies).
        self._cancelled = True
        stop_process_async(self._process)

    def run(self):
        try:
            import os
            self.log_signal.emit(
                f"Running: {self.executable_path} -conf {self.config_path}"
            )
            self._cancelled = False
            cwd = os.path.dirname(os.path.dirname(os.path.abspath(self.executable_path)))
            # HybMesh2D loads libgmsh through @rpath; the loader search path has
            # to be handed over explicitly here (a shell wrapper's export cannot
            # survive into this process — see app/services/env_setup.py).
            hint = gmsh_missing_hint()
            if hint:
                self.log_signal.emit(hint)
            self._process = subprocess.Popen(
                [self.executable_path, "-conf", self.config_path],
                env=mesher_env(),
                **popen_kwargs(cwd=cwd),
            )


            self._progress = 0
            for line in self._process.stdout:
                if self._cancelled:
                    break
                stripped = line.rstrip()
                if stripped:
                    self.log_signal.emit(stripped)
                    self._emit_progress(stripped)

            if self._cancelled:
                stop_process_async(self._process)
                self.log_signal.emit("Mesh generation cancelled by user.")
                self.finished_signal.emit(RC_CANCELLED)
                return

            # stdout is at EOF, so the process is finishing; this only bounds a
            # child that closed its pipe but will not exit.
            self._process.wait(timeout=600)  # 10 min timeout
            self.finished_signal.emit(self._process.returncode)
        except subprocess.TimeoutExpired:
            kill_process(self._process)
            self.log_signal.emit("Mesh generation timed out (10 min).")
            self.finished_signal.emit(RC_TIMEOUT)
        except Exception as e:
            self.log_signal.emit(f"Failed to start mesh generator: {e}")
            self.finished_signal.emit(RC_EXCEPTION)
