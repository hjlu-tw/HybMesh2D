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

from PyQt6.QtCore import QCoreApplication, QT_TRANSLATE_NOOP
from PyQt6.QtWidgets import QLabel, QStatusBar

_BAR_QSS = """
    QStatusBar { background:#0c0d16; color:#8a93ad; border-top:1px solid #1c1e36; }
    QStatusBar::item { border:0px; }
"""
_FIELD_QSS = "color:#a0a8c0; font-size:11px; padding:0 8px;"
_BUSY_QSS = "color:#e5a13a; font-size:11px; padding:0 8px;"

def _t(text: str) -> str:
    """Translate a module-level string (no QObject to call self.tr on)."""
    return QCoreApplication.translate("StatusBar", text)


#: Short stage names. The combo's own labels ("PreProcessor (CAD)") are too long for
#: a status field, and the index-to-stage mapping is the same one mode_combo uses.
#: Kept as source strings and translated at display time (see _t below), so switching
#: language does not depend on when this module happened to be imported.
#: QT_TRANSLATE_NOOP marks them for extraction without translating here — without it a
#: coverage report sees no literal at the tr() call site and wrongly declares these
#: translations stale, inviting someone to delete real work.
_STAGE_NAMES = (
    QT_TRANSLATE_NOOP("StatusBar", "CAD"),
    QT_TRANSLATE_NOOP("StatusBar", "Mesh"),
    QT_TRANSLATE_NOOP("StatusBar", "Mesh Stats"),
    QT_TRANSLATE_NOOP("StatusBar", "Solver"),
    QT_TRANSLATE_NOOP("StatusBar", "Results"),
    QT_TRANSLATE_NOOP("StatusBar", "Immersed Solid"),
)

#: Human phrase per progress owner, so "what is running" is readable rather than an
#: internal key. Owners come from claim_progress() call sites.
_ACTIVITY_NAMES = {
    "backend": QT_TRANSLATE_NOOP("StatusBar", "Resampling geometry"),
    "cad": QT_TRANSLATE_NOOP("StatusBar", "Resampling geometry"),
    "mesh": QT_TRANSLATE_NOOP("StatusBar", "Generating mesh"),
    "mesh_gen": QT_TRANSLATE_NOOP("StatusBar", "Generating mesh"),
    "solver": QT_TRANSLATE_NOOP("StatusBar", "Running solver"),
    "stl3d": QT_TRANSLATE_NOOP("StatusBar", "Generating φ field"),
    "extrude": QT_TRANSLATE_NOOP("StatusBar", "Exporting STL"),
    "fit": QT_TRANSLATE_NOOP("StatusBar", "Checking STL/φ fit"),
    "stats": QT_TRANSLATE_NOOP("StatusBar", "Computing mesh statistics"),
    "pipeline": QT_TRANSLATE_NOOP("StatusBar", "Running full pipeline"),
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
        self.status_stage.setToolTip(_t("Active workflow stage"))

        self.status_selection = QLabel("")
        self.status_selection.setStyleSheet(_FIELD_QSS)
        self.status_selection.setToolTip(
            _t("What is currently selected in the active stage"))

        self.status_activity = QLabel("")
        self.status_activity.setStyleSheet(_FIELD_QSS)
        self.status_activity.setToolTip(_t("Background work in progress"))

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
        name = (_t(_STAGE_NAMES[index]) if 0 <= index < len(_STAGE_NAMES)
                else self.mode_combo.currentText())
        self.status_stage.setText(_t("Stage: %s") % name)

    def set_status_selection(self, text: str = ""):
        """Show what is selected, or a dash when nothing is."""
        self.status_selection.setText(_t("Selection: %s") % (text or "—"))

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
        # Translate the phrase, not the owner key: an unknown owner is shown
        # as-is (untranslated) rather than hidden.
        phrase = _ACTIVITY_NAMES.get(label)
        phrase = _t(phrase) if phrase else label
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
