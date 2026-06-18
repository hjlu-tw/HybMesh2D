from __future__ import annotations
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, QElapsedTimer

# Residual component labels for compressible Navier-Stokes conserved variables.
# The solver prints 5 values per region (verified by smoke test); they map to the
# conservation residuals in this order.
_COMP_LABELS = ["continuity", "x-mom", "y-mom", "energy", "aux"]
_COMP_COLORS = ["#22c55e", "#3b82f6", "#06b6d4", "#f59e0b", "#a855f7"]
_RES_FLOOR = 1e-30  # clamp for log plotting (residuals can hit exactly 0)


class SolverMonitorPanel(QWidget):
    """Live solver monitor: pipeline stage, iteration counter, elapsed time, and a
    log-scale residual convergence plot fed by SolverPipelineWorker.residual_signal.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #121422; color: #a0a8c0;")
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QLabel("Solver Monitor")
        title.setStyleSheet("color: #dde2ff; font-size: 14px; font-weight: bold;")
        root.addWidget(title)

        # ── Status grid ───────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)

        def _mk_value(text="—"):
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #dde2ff; font-weight: bold;")
            return lbl

        def _mk_key(text):
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #7a82a0;")
            return lbl

        self.stage_value = _mk_value("idle")
        self.iter_value = _mk_value("—")
        self.cfl_value = _mk_value("—")
        self.elapsed_value = _mk_value("0.0 s")
        grid.addWidget(_mk_key("Stage:"), 0, 0)
        grid.addWidget(self.stage_value, 0, 1)
        grid.addWidget(_mk_key("Iteration:"), 0, 2)
        grid.addWidget(self.iter_value, 0, 3)
        grid.addWidget(_mk_key("CFL:"), 1, 0)
        grid.addWidget(self.cfl_value, 1, 1)
        grid.addWidget(_mk_key("Elapsed:"), 1, 2)
        grid.addWidget(self.elapsed_value, 1, 3)
        root.addLayout(grid)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2c2e43;")
        root.addWidget(sep)

        res_label = QLabel("Residual (eL2, log scale)")
        res_label.setStyleSheet("color: #a0b0d0; font-weight: bold;")
        root.addWidget(res_label)

        # ── Residual plot ──────────────────────────────────────────────────
        pg.setConfigOptions(antialias=True)
        self.plot = pg.PlotWidget()
        self.plot.setBackground("#0c0d16")
        self.plot.setLogMode(x=False, y=True)
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "Iteration", color="#7a82a0")
        self.plot.setLabel("left", "eL2 residual", color="#7a82a0")
        self.plot.addLegend(offset=(-10, 10))
        root.addWidget(self.plot, stretch=1)

        self._curves: list = []
        self._iters: list[int] = []
        self._comps: list[list[float]] = []

        # Elapsed-time ticker
        self._elapsed = QElapsedTimer()
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick_elapsed)

    # ------------------------------------------------------------------ #
    def reset(self):
        """Clear all data and start a fresh monitoring session."""
        self.plot.clear()
        self._curves = []
        self._iters = []
        self._comps = []
        self.stage_value.setText("starting…")
        self.iter_value.setText("—")
        self.cfl_value.setText("—")
        self.elapsed_value.setText("0.0 s")
        self._elapsed.restart()
        self._timer.start()

    def stop(self):
        self._timer.stop()

    # ------------------------------------------------------------------ #
    def on_stage(self, stage: str):
        self.stage_value.setText(stage)

    def on_residual(self, data: dict):
        l2 = data.get("L2") or []
        if not l2:
            return
        # Lazily create one curve per residual component on first data.
        if not self._curves:
            self._comps = [[] for _ in l2]
            for i in range(len(l2)):
                label = _COMP_LABELS[i] if i < len(_COMP_LABELS) else f"comp{i}"
                color = _COMP_COLORS[i % len(_COMP_COLORS)]
                self._curves.append(
                    self.plot.plot(pen=pg.mkPen(color, width=2), name=label))

        self._iters.append(data.get("iter", len(self._iters)))
        for i, c in enumerate(self._curves):
            v = l2[i] if i < len(l2) else _RES_FLOOR
            self._comps[i].append(max(abs(v), _RES_FLOOR))
            c.setData(self._iters, self._comps[i])

        if data.get("iter") is not None:
            self.iter_value.setText(str(data["iter"]))
        if data.get("cfl") is not None:
            self.cfl_value.setText(f"{data['cfl']:g}")

    def on_finished(self, rc: int):
        self._timer.stop()
        if rc == 0:
            self.stage_value.setText("finished")
        elif rc == -2:
            self.stage_value.setText("cancelled")
        else:
            self.stage_value.setText(f"failed ({rc})")

    # ------------------------------------------------------------------ #
    def _tick_elapsed(self):
        secs = self._elapsed.elapsed() / 1000.0
        if secs < 60:
            self.elapsed_value.setText(f"{secs:.1f} s")
        else:
            self.elapsed_value.setText(f"{int(secs // 60)}m {int(secs % 60)}s")
