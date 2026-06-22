from __future__ import annotations
import os
import re
import shutil
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal

from app.models.solver_config import SolverConfig
from app.utils import find_mpi_launcher

# Convergence markers echoed by unicones on stdout (verified by smoke test, R1):
#   Global Iteration count <N> :
#    cfl = <val>
#    physical time = <val>
#    eL2 error norm for int.  region =   r1 r2 r3 r4 r5   (one row per zone)
#    eL2 error norm of bound. region =   b1 b2 b3 b4 b5
_ITER_RE = re.compile(r"Global Iteration count\s+(\d+)")
_CFL_RE = re.compile(r"\bcfl\s*=\s*([-\d.eE+]+)")
_PTIME_RE = re.compile(r"physical time\s*=\s*([-\d.eE+]+)")
_INT_RE = re.compile(r"eL2 error norm for int\.\s*region\s*=\s*(.+)")
_BND_RE = re.compile(r"eL2 error norm of bound\.\s*region\s*=\s*(.+)")
_FLOAT_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


class SolverPipelineWorker(QThread):
    """Runs getPGrid -> (optional bDecompose) -> unicones in a background thread.

    Directory layout (prepared by solver_ctrl, D6):
      - getpgrid_dir: holds the STAR-CD .vrt/.cel/.bnd inputs; getPGrid writes
        .grid/.bc here.
      - solver_work_dir: the case work dir; unicones runs with this as cwd so
        the relative grid/bc/DLL paths inside input.in resolve.
    The worker generates the stdin answer files (para.in) for the interactive
    preprocessors and streams/parses solver stdout for live residuals.
    """

    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)       # 0..100
    stage_signal = pyqtSignal(str)          # "getPGrid" / "bDecompose" / "Solver"
    residual_signal = pyqtSignal(dict)      # {"iter":int, "cfl":float, "time":float, "L2":[...], "bound":[...]}
    finished_signal = pyqtSignal(int)       # return code (0 ok; <0 cancelled/error)

    def __init__(self, config: SolverConfig, getpgrid_dir: str,
                 solver_work_dir: str, input_in_path: str, tag: str = ".gui"):
        super().__init__()
        self._config = config
        self._getpgrid_dir = getpgrid_dir
        self._solver_work_dir = solver_work_dir
        self._input_in_path = input_in_path
        self._tag = tag
        self._process: subprocess.Popen | None = None
        self._cancelled = False

        # Residual accumulation state. A convergence print is delimited by the
        # "eL2 ... bound. region" line (present in both the IBM and non-IBM stdout
        # formats); the iteration number comes from an explicit "Global Iteration
        # count" header when present, otherwise a synthetic counter.
        self._explicit_iter: int | None = None
        self._synthetic_iter: int = 0
        self._cfl: float | None = None
        self._ptime: float | None = None
        self._int_rows: list[list[float]] = []
        self._bound_row: list[float] | None = None

    # ------------------------------------------------------------------ #
    def cancel(self):
        self._cancelled = True
        if self._process and self._process.poll() is None:
            self._process.terminate()

    def run(self):
        try:
            self._cancelled = False
            self.progress_signal.emit(0)

            if not self._run_getpgrid():
                return
            if self._config.enable_decompose:
                if not self._run_bdecompose():
                    return
            if not self._run_solver():
                return

            self.finished_signal.emit(0)
        except Exception as e:  # pragma: no cover - defensive
            self.log_signal.emit(f"Solver pipeline failed: {e}")
            self.finished_signal.emit(-1)

    # ------------------------------------------------------------------ #
    # Stage 1: getPGrid (STAR-CD -> .grid/.bc), interactive via stdin
    # ------------------------------------------------------------------ #
    def _run_getpgrid(self) -> bool:
        self.stage_signal.emit("getPGrid")
        self.progress_signal.emit(2)
        para_path = os.path.join(self._getpgrid_dir, "para.in")
        self._config.generate_getpgrid_para(para_path)
        self.log_signal.emit(f"[getPGrid] running in {self._getpgrid_dir}")
        rc = self._run_stdin_stage(self._config.getpgrid_binary, para_path,
                                   self._getpgrid_dir, label="getPGrid")
        if rc != 0:
            if not self._cancelled:
                self.log_signal.emit(f"[getPGrid] exited with code {rc}")
                self.finished_signal.emit(rc if rc else -1)
            return False

        # The solver reads its segment table "<bc>.def" from its own cwd (work
        # dir). Use getPGrid's companion verbatim: copy grid/<bc>.def -> work/.
        # Skip only when the user supplied an explicit BC override (solver_ctrl
        # already wrote it into the work dir).
        def_name = os.path.basename(self._config.output_bc_file) + ".def"
        companion = os.path.join(self._getpgrid_dir, def_name)
        target = os.path.join(self._solver_work_dir, def_name)
        if (not self._config.bc_definitions
                and os.path.exists(companion)
                and os.path.abspath(companion) != os.path.abspath(target)):
            shutil.copy2(companion, target)
            self.log_signal.emit(f"[getPGrid] segment table -> {def_name}")

        self.progress_signal.emit(15)
        return True

    # ------------------------------------------------------------------ #
    # Stage 2: bDecompose (optional MPI partitioning, D4)
    # ------------------------------------------------------------------ #
    def _run_bdecompose(self) -> bool:
        self.stage_signal.emit("bDecompose")
        # bDecompose ships without the +x bit; make it executable on demand.
        try:
            os.chmod(self._config.bdecompose_binary, 0o755)
        except OSError:
            pass
        bd_dir = os.path.dirname(self._config.bdecompose_binary)
        para_path = os.path.join(bd_dir, "para.in")
        self._config.generate_bdecompose_para(para_path)
        self.log_signal.emit(f"[bDecompose] running in {bd_dir}")
        rc = self._run_stdin_stage(self._config.bdecompose_binary, para_path,
                                   bd_dir, label="bDecompose")
        if rc != 0:
            if not self._cancelled:
                self.log_signal.emit(f"[bDecompose] exited with code {rc}")
                self.finished_signal.emit(rc if rc else -1)
            return False
        self.progress_signal.emit(25)
        return True

    # ------------------------------------------------------------------ #
    # Stage 3: unicones solver, streaming residuals
    # ------------------------------------------------------------------ #
    def _run_solver(self) -> bool:
        self.stage_signal.emit("Solver")
        cmd = [self._config.solver_binary, "-t", self._tag, self._input_in_path]
        # Domain decomposition => real MPI launch. The controller's pre-run guard
        # has already verified mpirun + an MPI-capable binary; prepend the launcher.
        if self._config.enable_decompose:
            launcher = find_mpi_launcher()
            if launcher:
                cmd = [launcher, "-np", str(self._config.num_partitions)] + cmd
        self.log_signal.emit(
            f"[Solver] {' '.join(cmd)}  (cwd={self._solver_work_dir})")
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                cwd=self._solver_work_dir,
            )
        except OSError as e:
            self.log_signal.emit(f"[Solver] failed to start: {e}")
            self.finished_signal.emit(-1)
            return False

        for line in self._process.stdout:
            if self._cancelled:
                self._process.terminate()
                self.log_signal.emit("Solver cancelled by user.")
                self.finished_signal.emit(-2)
                return False
            stripped = line.rstrip()
            if stripped:
                self.log_signal.emit(stripped)
                self._parse_solver_output(stripped)

        self._flush_residual()  # emit the final accumulated iteration
        self._process.wait()
        rc = self._process.returncode
        if rc != 0 and not self._cancelled:
            self.log_signal.emit(f"[Solver] exited with code {rc}")
            self.finished_signal.emit(rc)
            return False
        self.progress_signal.emit(100)
        return True

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _run_stdin_stage(self, binary: str, para_path: str, cwd: str,
                         label: str) -> int:
        """Run an interactive preprocessor, feeding para.in on stdin (mirrors
        the verified `./binary < para.in`)."""
        try:
            with open(para_path, "rb") as stdin_f:
                self._process = subprocess.Popen(
                    [binary],
                    stdin=stdin_f,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    cwd=cwd,
                )
        except OSError as e:
            self.log_signal.emit(f"[{label}] failed to start: {e}")
            return -1

        for line in self._process.stdout:
            if self._cancelled:
                self._process.terminate()
                self.log_signal.emit(f"{label} cancelled by user.")
                return -2
            stripped = line.rstrip()
            if stripped:
                self.log_signal.emit(f"[{label}] {stripped}")
        self._process.wait()
        return self._process.returncode

    def _parse_solver_output(self, line: str):
        """Accumulate a convergence print; emit it when the bound-region line
        (its terminator) arrives. Works for both stdout formats."""
        m = _ITER_RE.search(line)
        if m:
            self._explicit_iter = int(m.group(1))
            self._int_rows = []
            self._bound_row = None
            return

        m = _CFL_RE.search(line)
        if m:
            self._cfl = float(m.group(1))
            return
        m = _PTIME_RE.search(line)
        if m:
            self._ptime = float(m.group(1))
            return
        m = _INT_RE.search(line)
        if m:
            vals = [float(x) for x in _FLOAT_RE.findall(m.group(1))]
            if vals:
                self._int_rows.append(vals)
            return
        m = _BND_RE.search(line)
        if m:
            vals = [float(x) for x in _FLOAT_RE.findall(m.group(1))]
            self._bound_row = vals or None
            self._flush_residual()  # bound line terminates a convergence print

    def _flush_residual(self):
        """Emit the accumulated convergence print (max residual across regions)."""
        if not self._int_rows:
            return
        it = self._explicit_iter if self._explicit_iter is not None else self._synthetic_iter
        ncomp = max(len(r) for r in self._int_rows)
        l2 = [max(r[c] for r in self._int_rows if len(r) > c) for c in range(ncomp)]
        self.residual_signal.emit({
            "iter": it,
            "cfl": self._cfl,
            "time": self._ptime,
            "L2": l2,
            "bound": self._bound_row,
        })
        self._emit_progress(it)
        # Prepare for the next print.
        self._synthetic_iter = it + max(1, self._config.print_convg_per_niter)
        self._explicit_iter = None
        self._int_rows = []
        self._bound_row = None

    def _emit_progress(self, it: int):
        total = max(1, self._config.num_half_iter)
        self.progress_signal.emit(25 + int(75 * min(it / total, 1.0)))
