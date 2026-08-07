"""Batch queue: run many pipeline scripts unattended, and watch them.

A modeless dialog rather than a new stage page. The stage pages (CAD → Mesh → Solver →
IB → Results) are steps of *one* case; a batch is an operation over many cases and does
not belong in that sequence. Modeless because the point of a batch is to leave it
running — a modal would lock the window for the hours the queue takes.

Three things this shows that the CLI cannot:

* **Name collisions before the run, not during it.** Output paths derive from the case
  name, so two scripts sharing one silently overwrite each other's mesh. ``run_batch``
  warns when it starts; here it is visible as soon as the scripts are added, which is
  when it can still be fixed cheaply.
* **Per-case status as it happens.** A table that stayed blank until the batch ended
  would be indistinguishable from a hang.
* **What Cancel actually does.** It ends the case in flight and stops the queue; the
  button says so, because a Cancel that silently meant "after the current solve, in
  twenty minutes" would be worse than no button.
"""
from __future__ import annotations

import os

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QProgressBar, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app.services import batch_runner
from app.utils import make_button

#: status -> (shown text, colour). Grey for "nothing has happened yet" so a pending
#: queue does not look like a wall of warnings.
_STATUS = {
    "pending": ("queued", "#8a93ad"),
    "running": ("running…", "#e5a13a"),
    "ok": ("ok", "#4ec9a0"),
    "failed": ("FAILED", "#e06c75"),
    "skipped": ("skipped", "#8a93ad"),
}

_COLS = ("Case", "Source", "Status", "Time", "Detail")


class BatchDialog(QDialog):
    """Queue table + Run/Cancel. The controller owns the worker; this is the view."""

    run_requested = pyqtSignal()
    cancel_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Queue")
        self.setStyleSheet("background:#121422; color:#cdd6f4;")
        self.setMinimumSize(760, 420)
        self.jobs: list = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)

        hint = QLabel(
            "Queue pipeline scripts (.json) or workspaces (.hws) and run them "
            "unattended. Each case runs the same stages as Run All.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8a93ad; font-size:10px;")
        outer.addWidget(hint)

        # ── queue table ──────────────────────────────────────────────────
        self.table = QTableWidget(0, len(_COLS))
        self.table.setHorizontalHeaderLabels(_COLS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet(
            "QTableWidget { background:#0c0d16; gridline-color:#1c1e36; }"
            "QHeaderView::section { background:#1a1c2e; color:#8a93ad; border:0; "
            "padding:3px; }")
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c in (2, 3):
            hdr.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        outer.addWidget(self.table, 1)

        # Collision warning, hidden until there is one. Always-present empty warning
        # space trains people to ignore that row.
        self.collision_label = QLabel("")
        self.collision_label.setWordWrap(True)
        self.collision_label.setStyleSheet("color:#e5a13a; font-size:10px;")
        self.collision_label.setVisible(False)
        outer.addWidget(self.collision_label)

        # ── queue editing ────────────────────────────────────────────────
        row = QHBoxLayout()
        self.add_btn = make_button("Add Scripts…", "#1a2a3a")
        self.add_manifest_btn = make_button("Add Manifest…", "#1a2a3a")
        self.remove_btn = make_button("Remove", "#3a1c1c")
        self.clear_btn = make_button("Clear", "#3a1c1c")
        for b in (self.add_btn, self.add_manifest_btn, self.remove_btn,
                  self.clear_btn):
            row.addWidget(b)
        row.addStretch()
        outer.addLayout(row)

        # ── options ──────────────────────────────────────────────────────
        opts = QHBoxLayout()
        self.run_solver_cb = QCheckBox("Run solver")
        self.run_solver_cb.setChecked(True)
        self.run_solver_cb.setToolTip(
            "Off = stop after meshing (the same as run_batch.sh --no-solver).")
        self.run_ib_cb = QCheckBox("Run immersed solid")
        self.run_ib_cb.setChecked(True)
        self.run_ib_cb.setToolTip(
            "Off = skip the STL→φ stage, e.g. when φ was generated already.")
        opts.addWidget(self.run_solver_cb)
        opts.addWidget(self.run_ib_cb)
        opts.addStretch()
        outer.addLayout(opts)

        # ── progress + actions ───────────────────────────────────────────
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.setFormat("idle")
        self.progress.setStyleSheet(
            "QProgressBar { background:#0c0d16; border:1px solid #2c2e43; "
            "text-align:center; color:#a0a8c0; height:16px; }"
            "QProgressBar::chunk { background:#1e4620; }")
        outer.addWidget(self.progress)

        actions = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color:#8a93ad; font-size:11px;")
        actions.addWidget(self.status_label, 1)
        self.run_btn = make_button("Run Batch", "#1e4620")
        self.cancel_btn = make_button("Cancel", "#4a1c1c")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setToolTip(
            "Stops the case that is running now and skips the rest of the queue.\n"
            "Cases already finished keep their output.")
        self.close_btn = make_button("Close", "#2a2c3e")
        for b in (self.run_btn, self.cancel_btn, self.close_btn):
            actions.addWidget(b)
        outer.addLayout(actions)

        self.add_btn.clicked.connect(self._on_add_scripts)
        self.add_manifest_btn.clicked.connect(self._on_add_manifest)
        self.remove_btn.clicked.connect(self._on_remove_selected)
        self.clear_btn.clicked.connect(self.clear_jobs)
        self.run_btn.clicked.connect(self.run_requested)
        self.cancel_btn.clicked.connect(self.cancel_requested)
        self.close_btn.clicked.connect(self.close)
        self._refresh()

    # ── queue contents ───────────────────────────────────────────────────
    def add_paths(self, paths, log=None) -> int:
        """Queue every script/workspace in ``paths``. Returns how many were added."""
        if not paths:
            return 0
        new = batch_runner.load_jobs(paths, log=log or (lambda _m: None))
        self.jobs.extend(new)
        self._refresh()
        return len(new)

    def clear_jobs(self):
        self.jobs = []
        self._refresh()

    def _on_add_scripts(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Pipeline Scripts / Workspaces", "config/pipeline",
            "Pipeline scripts and workspaces (*.json *.hws);;All files (*)")
        self.add_paths(paths, log=self._emit_log)

    def _on_add_manifest(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Add Batch Manifest", "config",
            "Manifest (*.txt *.lst *.manifest);;All files (*)")
        if not path:
            return
        try:
            paths = batch_runner.read_manifest(path)
        except OSError as e:
            from app.utils import report_warning
            report_warning(self, "Manifest Not Read",
                           "The manifest could not be read.", detail=str(e))
            return
        self.add_paths(paths, log=self._emit_log)

    def _on_remove_selected(self):
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            if 0 <= r < len(self.jobs):
                del self.jobs[r]
        self._refresh()

    def _emit_log(self, msg):
        # The dialog has no log of its own; batch output belongs in the one log the
        # user already watches. The controller connects this.
        if callable(getattr(self, "log_sink", None)):
            self.log_sink(msg)

    # ── display ──────────────────────────────────────────────────────────
    def _refresh(self):
        self.table.setRowCount(len(self.jobs))
        for r, job in enumerate(self.jobs):
            self.update_row(r)
        self._refresh_collisions()
        self._refresh_buttons()

    def update_row(self, index: int):
        """Redraw one row (called per case as the batch progresses)."""
        if not (0 <= index < len(self.jobs)):
            return
        job = self.jobs[index]
        text, colour = _STATUS.get(job.status, (job.status, "#a0a8c0"))
        source = os.path.basename(job.source) if job.source else "(in memory)"
        secs = f"{job.seconds:.1f}s" if job.seconds else ""
        for c, value in enumerate((job.label, source, text, secs, job.error)):
            item = QTableWidgetItem(value)
            if c == 1 and job.source:
                item.setToolTip(job.source)
            if c == 4 and job.error:
                item.setToolTip(job.error)
            if c == 2:
                item.setForeground(QBrush(QColor(colour)))
            self.table.setItem(index, c, item)

    def _refresh_collisions(self):
        runnable = [j for j in self.jobs if j.config is not None]
        collisions = batch_runner.find_collisions(runnable)
        if not collisions:
            self.collision_label.setVisible(False)
            self.collision_label.setText("")
            return
        parts = [f"{name!r} ({', '.join(srcs)})"
                 for name, srcs in sorted(collisions.items())]
        self.collision_label.setText(
            "Case names shared by several jobs — their outputs would overwrite each "
            "other. Give each script its own \"name\": " + "; ".join(parts))
        self.collision_label.setVisible(True)

    def _refresh_buttons(self):
        runnable = any(j.config is not None for j in self.jobs)
        self.run_btn.setEnabled(runnable and not self.cancel_btn.isEnabled())
        self.remove_btn.setEnabled(bool(self.jobs))
        self.clear_btn.setEnabled(bool(self.jobs))
        n = len(self.jobs)
        bad = sum(1 for j in self.jobs if j.config is None)
        if not n:
            self.status_label.setText("Queue empty.")
        else:
            msg = f"{n} case(s) queued"
            if bad:
                msg += f", {bad} unreadable (will be skipped)"
            self.status_label.setText(msg + ".")

    # ── run state ────────────────────────────────────────────────────────
    def set_running(self, running: bool):
        self.cancel_btn.setEnabled(running)
        for b in (self.add_btn, self.add_manifest_btn, self.remove_btn,
                  self.clear_btn):
            b.setEnabled(not running)
        self.run_btn.setEnabled(not running and
                                any(j.config is not None for j in self.jobs))
        if not running:
            self._refresh_buttons()

    def set_progress(self, done: int, total: int, label: str):
        if total <= 0:
            self.progress.setValue(0)
            self.progress.setFormat("idle")
            return
        self.progress.setValue(int(round(100.0 * done / total)))
        self.progress.setFormat(
            f"{done}/{total} — {label}" if label else f"{done}/{total}")

    def show_summary(self, summary: dict):
        ok = len(summary.get("ok", []))
        failed = len(summary.get("failed", []))
        skipped = len(summary.get("skipped", []))
        self.progress.setFormat(
            f"done — {ok} ok, {failed} failed, {skipped} skipped")
        # Redraw the rows FIRST: _refresh rewrites the status label with the queue
        # count, so setting the summary before it would show "N case(s) queued" the
        # instant a batch finished — the one moment the result matters most.
        self._refresh()
        self.status_label.setText(
            f"{ok} ok, {failed} failed, {skipped} skipped "
            f"in {summary.get('seconds', 0.0):.1f}s. Full output is in the log.")
