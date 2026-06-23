from __future__ import annotations
import os
import re
import shutil
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal

# Matches g++ diagnostics: "file.cc:12:5: error: ...".
_DIAG_RE = re.compile(r"^(?P<file>[^:\n]+):(?P<line>\d+):(?:(?P<col>\d+):)?\s*"
                      r"(?P<level>error|warning|note):\s*(?P<msg>.*)$")

# The exact flags solver_ctrl._stage_dll / solver/run.sh use, so a DLL that
# compiles here is ABI-compatible with how the solver pipeline rebuilds it.
COMPILE_FLAGS = ["-D_INCLUDE_TEMPLATE_IMPLEMENTATION", "-fPIC", "-shared", "-O3"]


def compiler_available() -> str | None:
    """Return the C++ compiler on PATH (g++ preferred, then c++/clang++)."""
    for name in ("g++", "c++", "clang++"):
        path = shutil.which(name)
        if path:
            return path
    return None


def parse_diagnostics(text: str) -> list[dict]:
    """Parse g++ stderr into [{file,line,col,level,msg}] entries."""
    diags: list[dict] = []
    for raw in text.splitlines():
        m = _DIAG_RE.match(raw.strip())
        if not m:
            continue
        diags.append({
            "file": os.path.basename(m.group("file")),
            "line": int(m.group("line")),
            "col": int(m.group("col")) if m.group("col") else 0,
            "level": m.group("level"),
            "msg": m.group("msg"),
        })
    return diags


class DllCompileWorker(QThread):
    """Compiles a single .cc source into a .so with the solver's exact flags."""

    log_signal = pyqtSignal(str)
    # returncode, raw compiler output, parsed diagnostics
    finished_signal = pyqtSignal(int, str, list)

    def __init__(self, src_path: str, out_path: str, compiler: str = "g++"):
        super().__init__()
        self._src = src_path
        self._out = out_path
        self._compiler = compiler

    def run(self):
        cmd = [self._compiler] + COMPILE_FLAGS + ["-o", self._out, self._src]
        self.log_signal.emit("$ " + " ".join(cmd))
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
        except OSError as e:
            self.log_signal.emit(f"[compile] failed to launch compiler: {e}")
            self.finished_signal.emit(-1, str(e), [])
            return
        output = (r.stdout or "") + (r.stderr or "")
        if output.strip():
            self.log_signal.emit(output.strip())
        self.finished_signal.emit(r.returncode, output, parse_diagnostics(output))
