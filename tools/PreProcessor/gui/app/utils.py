from __future__ import annotations
import os
import shutil
from contextlib import contextmanager

from PyQt6.QtCore import QObject, Qt, QPoint, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QPushButton,
    QFormLayout,
    QLabel,
    QHBoxLayout,
    QWidget
)

# BUTTON_QSS_TEMPLATE is used below; the others are re-exported for convenience
# (many panels do `from app.utils import COMBO_STYLE`). The `X as X` form marks
# them as intentional re-exports so they aren't reported as unused imports.
from app.styles import (
    BUTTON_QSS_TEMPLATE,
    COMBO_STYLE as COMBO_STYLE,
    SPIN_STYLE as SPIN_STYLE,
    LINEEDIT_STYLE as LINEEDIT_STYLE,
)

# Boundary Condition Colors mapping
BC_COLORS = {
    "wall": '#ef4444',
    "farfield": '#06b6d4',
    "inlet": '#22c55e',
    "outlet": '#3b82f6',
    "symmetry": '#f97316',
    "symp": '#f97316',       # alias for symmetry
    "isothermal": '#a855f7', # purple — isothermal wall
    "free": '#eab308',       # yellow — free boundary
}
DEFAULT_BC_COLOR = '#9ca3af'

def report_error(parent, title: str, message: str, detail: str | None = None):
    """Show a blocking error dialog for a failed *data* operation (save/export).

    A failed write that only lands in the log panel is easy to miss — the user
    walks away believing their work is on disk. Industrial tools surface these
    modally; keep the log line too (callers still log), but never let a data-loss
    failure be silent. Headless/offscreen platforms skip the modal so batch and
    test runs don't block on a prompt with no one to answer it."""
    _message_box(parent, title, message, detail, "error")


def report_warning(parent, title: str, message: str, detail: str | None = None):
    """Show a blocking warning dialog for a failed *read* (load/import). Less
    severe than report_error — no user data is at risk — but still surfaced so a
    silent load failure isn't mistaken for an empty result."""
    _message_box(parent, title, message, detail, "warning")


def report_info(parent, title: str, message: str, detail: str | None = None):
    """Show a blocking information dialog: a precondition the user must satisfy
    ("draw a closed profile first"), not a failure. Nothing went wrong, so it must
    not carry a warning/error icon — grading everything the same way trains users
    to dismiss real problems."""
    _message_box(parent, title, message, detail, "info")


def confirm(parent, title: str, question: str,
            detail: str | None = None, headless_default: bool = True) -> bool:
    """Ask a Yes/No question; return True for Yes.

    Use this instead of a bare ``QMessageBox.question``/``warning`` prompt: it
    carries the Question icon (a confirmation is not a warning) and, crucially,
    it resolves to ``headless_default`` on a screenless platform instead of
    blocking forever. Every hand-rolled prompt that skipped that check became a
    hang in tests, CI or the headless pipeline.

    ``headless_default`` is True for "proceed anyway?" prompts, which is what a
    batch run wants. Pass False for anything destructive.
    """
    from PyQt6.QtWidgets import QMessageBox
    if is_headless():
        return headless_default
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(question)
    if detail:
        box.setDetailedText(detail)
    box.setStandardButtons(QMessageBox.StandardButton.Yes
                           | QMessageBox.StandardButton.No)
    box.setDefaultButton(QMessageBox.StandardButton.No)
    return box.exec() == QMessageBox.StandardButton.Yes


_ICONS = {"error": "Critical", "warning": "Warning", "info": "Information"}


def _message_box(parent, title, message, detail, severity):
    from PyQt6.QtWidgets import QMessageBox
    if is_headless():
        return
    box = QMessageBox(parent)
    box.setIcon(getattr(QMessageBox.Icon, _ICONS.get(severity, "Warning")))
    box.setWindowTitle(title)
    box.setText(message)
    if detail:
        box.setDetailedText(detail)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()


@contextmanager
def block_signals(*widgets: QObject):
    """Context manager to block signals of multiple Qt widgets temporarily."""
    for w in widgets:
        if w is not None:
            w.blockSignals(True)
    try:
        yield
    finally:
        for w in widgets:
            if w is not None:
                w.blockSignals(False)

# Curve type labels mapping
CURVE_TYPE_LABELS = {
    "custom": lambda seg: f"Curve ({'Param' if seg.curve_mode == 'parametric' else 'Explicit'})",
    "horizontal_line": "H Line",
    "vertical_line": "V Line",
    "line": "Line",
    "circle": "Circle",
    "arc": "Arc",
    "triangle": "Triangle",
    "quadrilateral": "Quad",
    "polygon": "Polygon",
}


def make_button(text: str, color: str = '#26293c', *,
                border: str | None = None, hover_border: str | None = None,
                checked_bg: str | None = None, padding: str | None = None,
                font_size: str | None = None) -> QPushButton:
    """App push button.

    Called as ``make_button(text, color)`` it yields the standard button (the
    shared BUTTON_QSS_TEMPLATE — background-hover, disabled state). Passing any of
    the keyword styling args switches to the compact "bar" variant used by the
    STL3d canvas toolbar: a coloured border that brightens on hover (``border`` /
    ``hover_border``), an optional checked highlight (``checked_bg``), and custom
    ``padding`` / ``font_size`` — one factory instead of a parallel one.
    """
    b = QPushButton(text)
    if (border is None and hover_border is None and checked_bg is None
            and padding is None and font_size is None):
        b.setStyleSheet(BUTTON_QSS_TEMPLATE.format(color=color))
        return b
    bdr = border or "#4a5070"
    hov = hover_border or bdr
    pad = padding or "6px 10px"
    fs = f"font-size:{font_size};" if font_size else ""
    qss = (f"QPushButton{{background:{color};color:#dde6ff;border:1px solid {bdr};"
           f"border-radius:4px;padding:{pad};font-weight:bold;{fs}}}"
           f"QPushButton:hover{{border-color:{hov};}}"
           f"QPushButton:disabled{{background:#171926;color:#555;}}")
    if checked_bg:
        qss += (f"QPushButton:checked{{background:{checked_bg};"
                f"border-color:{hov};color:#fff;}}")
    b.setStyleSheet(qss)
    return b

# Pop-up stacking lives in app/popup_stack.py (this module was over the GUI
# file-size budget); re-exported here because every call site imports it from
# app.utils. The `X as X` form marks these as intentional re-exports.
from app.popup_stack import (                                    # noqa: E402
    KEEP_ON_TOP_PROP as KEEP_ON_TOP_PROP,
    _ClickRaiser as _ClickRaiser,
    _CLICK_RAISER_PROP as _CLICK_RAISER_PROP,
    _PopupRaiser as _PopupRaiser,
    _RAISER_PROP as _RAISER_PROP,
    keep_on_top as keep_on_top,
    offset_popup as offset_popup,
    raise_later as raise_later,
    raise_popups_of as raise_popups_of,
)


def align_form_labels(layout: QFormLayout, width: int = 120):
    layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
    layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    for i in range(layout.rowCount()):
        label_item = layout.itemAt(i, QFormLayout.ItemRole.LabelRole)
        if label_item:
            lbl = label_item.widget()
            if lbl:
                lbl.setFixedWidth(width)
                if isinstance(lbl, QLabel):
                    lbl.setWordWrap(True)


# ---------------------------------------------------------------------------
# Custom floating tooltip popup (bypasses macOS QToolTip rendering issues)
# ---------------------------------------------------------------------------

class _FloatingTooltip(QWidget):
    """A frameless, always-on-top popup label used as a custom tooltip."""

    def __init__(self):
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setMaximumWidth(260)
        self._label.setStyleSheet(
            "color: #e2e8f0;"
            "background: transparent;"
            "padding: 0px;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.addWidget(self._label)
        self.setStyleSheet(
            "background-color: #1e2235;"
            "border: 1px solid #3b82f6;"
            "border-radius: 5px;"
        )
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_near(self, global_pos: QPoint, text: str):
        self._hide_timer.stop()
        self._label.setText(text)
        self._label.adjustSize()
        self.adjustSize()
        # Position slightly below-right of cursor
        x = global_pos.x() + 14
        y = global_pos.y() + 14
        # Keep on screen
        screen = QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            if x + self.width() > geom.right():
                x = global_pos.x() - self.width() - 4
            if y + self.height() > geom.bottom():
                y = global_pos.y() - self.height() - 4
        self.move(x, y)
        self.show()
        self.raise_()

    def schedule_hide(self, delay_ms: int = 200):
        self._hide_timer.start(delay_ms)


# Singleton tooltip popup (one per application)
_tooltip_popup: _FloatingTooltip | None = None

def _get_tooltip_popup() -> _FloatingTooltip:
    global _tooltip_popup
    if _tooltip_popup is None:
        _tooltip_popup = _FloatingTooltip()
    return _tooltip_popup


class HelpButton(QPushButton):
    """A small '?' button that shows a custom floating tooltip on hover."""

    def __init__(self, tooltip_text: str):
        super().__init__("?")
        self._tooltip_text = tooltip_text
        self.setFixedSize(16, 16)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.setMouseTracking(True)
        self.setStyleSheet("""
            QPushButton {
                background-color: #2a2d45;
                color: #8892b0;
                border: 1px solid #3a4060;
                border-radius: 8px;
                font-size: 10px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #3b82f6;
                color: #ffffff;
                border-color: #60a5fa;
            }
        """)

    def enterEvent(self, event):
        popup = _get_tooltip_popup()
        cursor_pos = self.mapToGlobal(QPoint(self.width(), 0))
        popup.show_near(cursor_pos, self._tooltip_text)
        super().enterEvent(event)

    def leaveEvent(self, event):
        _get_tooltip_popup().schedule_hide(150)
        super().leaveEvent(event)


def make_help_label(tooltip: str) -> HelpButton:
    """Create a small '?' button with a custom floating tooltip."""
    return HelpButton(tooltip)


def help_label(label_text: str, tooltip: str) -> QWidget:
    """Create a composite label widget with text + '?' help icon for use as a QFormLayout label."""
    container = QWidget()
    hl = QHBoxLayout(container)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(3)
    text_lbl = QLabel(label_text)
    text_lbl.setStyleSheet("color: #a0a8c0;")
    text_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    hl.addWidget(text_lbl, 1)
    hl.addWidget(make_help_label(tooltip))
    return container


def help_widget(widget, tooltip: str) -> QWidget:
    """Wrap any widget (like a button, checkbox, or list) with a '?' help icon to its right."""
    container = QWidget()
    hl = QHBoxLayout(container)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(6)
    hl.addWidget(widget)
    hl.addWidget(make_help_label(tooltip))
    return container


def help_row(label_text: str, widget, tooltip: str) -> QWidget:
    """Backward compatibility helper mapping to help_label."""
    return help_label(label_text, tooltip)


def repo_root() -> str:
    """Absolute path to the repository root (the HybMesh project directory).

    Single source of truth for the project root. Callers in ``app/`` previously
    derived it ad-hoc as ``os.path.join(dirname(__file__), "../...")`` with the
    number of ``..`` segments depending on the file's depth — an easy off-by-one
    to get wrong. ``utils.py`` lives at ``gui/app/utils.py``, four levels below
    the repo root."""
    return os.path.abspath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../.."))


def is_headless() -> bool:
    """True on a Qt platform with no screen (offscreen / minimal).

    A modal there would block forever: there is nothing to show it on and nobody
    to answer it. Every confirmation prompt on a path that batch runs, the
    headless pipeline or the test suite can reach must check this first.
    """
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    return app is not None and app.platformName() in ("offscreen", "minimal")


def find_binary_executable(bin_name: str) -> str | None:
    """Locate binary executable in PATH environment or local build candidates."""
    path_run = shutil.which(bin_name)
    if path_run:
        return path_run

    base_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.abspath(os.path.join(base_dir, "../../../../../build")),
        os.path.abspath("../../../build"),
        os.path.abspath("./build"),
        os.path.abspath("."),
    ]
    for folder in candidates:
        full_path = os.path.join(folder, bin_name)
        if os.path.exists(full_path) and os.access(full_path, os.X_OK) and not os.path.isdir(full_path):
            return full_path
    return None


# Prebuilt solver-pipeline binaries shipped under solver/ (decision D5: use the
# existing binaries, no compilation step). Paths are relative to the repo root.
_SOLVER_BIN_REL = {
    "getpgrid": "solver/preprocess/getPGrid/work/getPGrid",
    "bdecompose": "solver/preprocess/bDecompose/work/bDecompose",
    "solver": "solver/execute/unicones.eqn6.mac",
}


def find_solver_executables() -> dict:
    """Locate the prebuilt getPGrid / bDecompose / unicones binaries.

    Returns a dict {name: abs_path | None}. Existence (not executability) is
    reported, since bDecompose ships without the +x bit and the solver worker
    chmods it on demand when domain decomposition is enabled.
    """
    repo = repo_root()
    found: dict[str, str | None] = {}
    for name, rel in _SOLVER_BIN_REL.items():
        full = os.path.join(repo, rel)
        found[name] = full if os.path.exists(full) else None
    return found


def find_stl3d_binary() -> str | None:
    """Locate the prebuilt STL3d immersed-solid preprocessor binary.

    Mirrors find_solver_executables (decision D5: use the existing binaries). The
    binary ships in both the work and src dirs; prefer the work-dir copy.
    """
    repo = repo_root()
    for rel in ("solver/preprocess/STL3d/work/stl3d",
                "solver/preprocess/STL3d/src/stl3d"):
        full = os.path.join(repo, rel)
        if os.path.exists(full):
            return full
    return None


def find_mpi_launcher() -> str | None:
    """Return the path to mpirun/mpiexec on PATH, or None if neither is present."""
    return shutil.which("mpirun") or shutil.which("mpiexec")


def is_mpi_binary(path: str) -> bool:
    """Heuristic: does this executable actually link MPI?

    Scans the binary for the `MPI_Init` symbol name. A pthread/serial build (like
    the bundled unicones) has no MPI symbols, so domain decomposition + mpirun
    would be meaningless against it.
    """
    if not path or not os.path.exists(path):
        return False
    try:
        with open(path, "rb") as f:
            blob = f.read()
    except OSError:
        return False
    return b"MPI_Init" in blob


def apply_smart_spin_steps(root) -> int:
    """Give every default-stepped QDoubleSpinBox under ``root`` a value-scaled
    ``singleStep`` so the up/down arrows nudge by ~one order of magnitude below
    the field's own scale, instead of Qt's blunt 1.0 default (#7).

    Only boxes still on the 1.0 default are touched — any field that set an
    explicit step at construction (growth rate 0.05, spacing 0.01, …) is left
    alone — and integer QSpinBoxes (node counts) keep their natural step of 1.
    Returns the number of boxes adjusted.
    """
    import math
    from PyQt6.QtWidgets import QDoubleSpinBox
    from app.views.clean_double_spin_box import SciDoubleSpinBox
    changed = 0
    for sp in root.findChildren(QDoubleSpinBox):
        if isinstance(sp, SciDoubleSpinBox):
            # Scientific fields recompute a decade-relative step on every press
            # (stepBy), which a single fixed step chosen at startup cannot match:
            # their value can move several orders of magnitude in one session.
            continue
        if abs(sp.singleStep() - 1.0) > 1e-9:
            continue   # respect an explicit per-field step
        dec = sp.decimals()
        v = abs(sp.value())
        if v > 1e-12:
            step = 10.0 ** (math.floor(math.log10(v)) - 1)
        else:
            step = 0.1   # neutral default when the field starts at zero
        if dec > 0:
            step = max(step, 10.0 ** (-dec))   # keep it representable
        step = min(max(step, 1e-9), 100.0)
        sp.setSingleStep(step)
        changed += 1
    return changed

