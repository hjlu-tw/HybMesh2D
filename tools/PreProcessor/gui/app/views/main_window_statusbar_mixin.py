"""Persistent status bar for MainWindow.

The window had no status bar, so three things had nowhere to live: which workflow
stage is active (only the combo said so), how much is currently selected (nothing
said so at all), and what background work is running — the toolbar progress bar
showed a moving bar but never *what* was moving.

Deliberately NOT here: cursor coordinates. All three canvases already carry a
``coord_label`` that floats next to the pointer, which is more useful than a fixed
read-out and was specifically fixed to clear on leave. Repeating it in the status bar
would be duplication, and two coordinate read-outs that can disagree are worse than
one.

Also not here: units. There is no unit system yet, and a field that always says the
same thing teaches people to stop reading the bar.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QStatusBar

_BAR_QSS = """
    QStatusBar { background:#0c0d16; color:#8a93ad; border-top:1px solid #1c1e36; }
    QStatusBar::item { border:0px; }
"""
_FIELD_QSS = "color:#a0a8c0; font-size:11px; padding:0 8px;"
_BUSY_QSS = "color:#e5a13a; font-size:11px; padding:0 8px;"

#: Short stage names. The combo's own labels ("PreProcessor (CAD)") are too long for
#: a status field, and the index-to-stage mapping is the same one mode_combo uses.
_STAGE_NAMES = ("CAD", "Mesh", "Mesh Stats", "Solver", "Results", "Immersed Solid")

#: Human phrase per progress owner, so "what is running" is readable rather than an
#: internal key. Owners come from claim_progress() call sites.
_ACTIVITY_NAMES = {
    "backend": "Resampling geometry",
    "cad": "Resampling geometry",
    "mesh": "Generating mesh",
    "mesh_gen": "Generating mesh",
    "solver": "Running solver",
    "stl3d": "Generating φ field",
    "extrude": "Exporting STL",
    "fit": "Checking STL/φ fit",
    "stats": "Computing mesh statistics",
    "pipeline": "Running full pipeline",
}


class MainWindowStatusBarMixin:
    def _build_status_bar(self):
        """Create the status bar. Call once, after the panels exist."""
        bar = QStatusBar(self)
        bar.setStyleSheet(_BAR_QSS)
        bar.setSizeGripEnabled(False)
        self.setStatusBar(bar)

        self.status_stage = QLabel("")
        self.status_stage.setStyleSheet(_FIELD_QSS)
        self.status_stage.setToolTip("Active workflow stage")

        self.status_selection = QLabel("")
        self.status_selection.setStyleSheet(_FIELD_QSS)
        self.status_selection.setToolTip(
            "What is currently selected in the active stage")

        self.status_activity = QLabel("")
        self.status_activity.setStyleSheet(_FIELD_QSS)
        self.status_activity.setToolTip("Background work in progress")

        # Permanent widgets sit right-aligned and are never overwritten by the
        # transient showMessage() text, which is the point: a passing message must
        # not erase the state read-out.
        for w in (self.status_selection, self.status_stage, self.status_activity):
            bar.addPermanentWidget(w)

        self.update_status_stage(self.mode_combo.currentIndex())
        self.set_status_selection()
        self.set_status_activity(None)

    # ── fields ───────────────────────────────────────────────────────────
    def update_status_stage(self, index: int):
        name = (_STAGE_NAMES[index] if 0 <= index < len(_STAGE_NAMES)
                else self.mode_combo.currentText())
        self.status_stage.setText(f"Stage: {name}")

    def set_status_selection(self, text: str = ""):
        """Show what is selected, or a dash when nothing is."""
        self.status_selection.setText(f"Selection: {text or '—'}")

    def set_status_activity(self, label: str | None, pct: int | None = None):
        """Name the running work (None = idle).

        ``label`` may be a progress-owner key, which is translated to a phrase; an
        unknown key is shown as-is rather than dropped, so a new call site is
        visible instead of silently blank.
        """
        if not label:
            self.status_activity.setText("")
            self.status_activity.setStyleSheet(_FIELD_QSS)
            return
        phrase = _ACTIVITY_NAMES.get(label, label)
        if pct is not None and 0 <= pct <= 100:
            phrase = f"{phrase} {pct}%"
        self.status_activity.setText(f"⟳ {phrase}…")
        self.status_activity.setStyleSheet(_BUSY_QSS)

    def flash_status(self, message: str, msecs: int = 4000):
        """Transient message on the left. Used for things that would otherwise only
        reach the log panel, so feedback does not require opening it."""
        bar = self.statusBar()
        if bar is not None:
            bar.showMessage(message, msecs)
