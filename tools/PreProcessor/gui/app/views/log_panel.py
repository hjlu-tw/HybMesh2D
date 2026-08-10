import re
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel, QFileDialog
)
from PyQt6.QtCore import QTime, QDateTime
from PyQt6.QtGui import QTextCursor

# Native-crash / linker / interpreter failure signatures that don't contain the
# literal word "error" or "failed". Without these, the line that actually
# explains a crash (segfault, abort, fatal, undefined reference, traceback) is
# classified INFO and rendered in muted grey — indistinguishable from noise.
_CRASH_TOKENS = (
    "fatal", "segmentation", "segfault", "abort trap", "core dumped",
    "terminate called", "undefined reference", "traceback",
    "bad_alloc", "libc++abi", "collect2:",
)

# The C++ side stamps every log line itself as "[<ISO UTC>] [LEVEL] msg"
# (include/Logger.hpp), and proc_util folds stderr into stdout, so all of those
# reach this panel. The panel renders its OWN clock + level label, so an
# unstripped stamp reads "[14:29:06] [INFO] [2026-08-10T06:29:06Z] [INFO] msg".
# The timestamp is optional in this pattern because GUI-side callers pass a bare
# "[ERROR] ..." tag. A matched tag is authoritative: it beats the keyword
# heuristics below, which would otherwise mis-tag e.g. an INFO line that merely
# contains the word "error".
_LEVEL_PREFIX = re.compile(
    r'^\s*(?:\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\]\s*)?'
    r'\[(?P<level>ERROR|WARNING|WARN|INFO)\]\s*',
    re.IGNORECASE,
)


class LogPanel(QWidget):
    """An enhanced console panel for displaying logs, featuring color coding, timestamps, and log rotation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        
        # ── Header bar ───────────────────────────────────────────────────
        self.header = QWidget()
        self.header.setStyleSheet("background: #090a12; border-bottom: 1px solid #1c1e36;")
        self.header.setFixedHeight(26)
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(8, 0, 8, 0)
        
        title = QLabel("OUTPUT CONSOLE")
        title.setStyleSheet("font-size: 10px; font-weight: bold; color: #8892b0; border: none;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        _btn_qss = """
            QPushButton {
                background: #1b1e36;
                color: #a5b0cf;
                border: 1px solid #363a60;
                border-radius: 3px;
                font-size: 9px;
                font-weight: bold;
                padding: 1px 6px;
            }
            QPushButton:hover {
                background: #2e3155;
                color: #ffffff;
                border-color: #5a9ad4;
            }
            QPushButton:pressed {
                background: #121422;
            }
        """

        # Save the console contents to a .log file.
        self.save_btn = QPushButton("Save Log")
        self.save_btn.setStyleSheet(_btn_qss)
        self.save_btn.setToolTip("Save the console output to a .log file")
        self.save_btn.clicked.connect(self.save_log)
        header_layout.addWidget(self.save_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet(_btn_qss)
        self.clear_btn.clicked.connect(self.clear_log)
        header_layout.addWidget(self.clear_btn)

        self._layout.addWidget(self.header)
        
        # ── Plain text log area ──────────────────────────────────────────
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.document().setMaximumBlockCount(1000)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background: #06070d;
                color: #dde6ff;
                font-family: 'Courier New', Courier, monospace;
                font-size: 11px;
                border: none;
            }
        """)
        self._layout.addWidget(self.text_edit)

    def log(self, message, level=None):
        """Append log message with timestamp and level color coding."""
        if not message:
            return
            
        # Colour-coded output is tagged by ANSI escapes, which the strip below
        # removes — so read them off the raw message first.
        if level is None:
            if "\x1b[1;31m" in message or "\x1b[31m" in message:
                level = "ERROR"
            elif "\x1b[1;33m" in message or "\x1b[33m" in message:
                level = "WARNING"

        # Strip ANSI escape codes to clean up garbled control characters
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        clean_message = ansi_escape.sub('', message)

        # Drop the emitter's own "[<ISO>] [LEVEL]" stamp (see _LEVEL_PREFIX) so it
        # doesn't double up with the panel's, and adopt the level it declared.
        # Component tags like [Pipeline] are not level tags and are kept.
        m = _LEVEL_PREFIX.match(clean_message)
        if m:
            clean_message = clean_message[m.end():]
            if level is None:
                tag = m.group("level").upper()
                level = "WARNING" if tag == "WARN" else tag

        # Only guess when nothing authoritative said otherwise.
        if level is None:
            lower_msg = clean_message.lower()
            # "eL2 error norm ..." is the solver's per-iteration residual
            # metric echoed on stdout, not a failure — don't let the "error"
            # substring in "error norm" mis-tag these convergence lines as
            # ERROR. Match the solver's own "eL2 error norm" token (not a bare
            # "error norm"), so a genuine error that happens to contain the
            # words "error norm" is still surfaced as ERROR.
            if "el2 error norm" in lower_msg:
                level = "INFO"
            elif ("error" in lower_msg or "failed" in lower_msg
                  # Native-crash / linker signatures that don't contain the
                  # word "error" would otherwise render as muted INFO — the one
                  # line that explains a crash must stand out as ERROR.
                  or any(tok in lower_msg for tok in _CRASH_TOKENS)):
                level = "ERROR"
            elif "warning" in lower_msg or "warn" in lower_msg:
                level = "WARNING"
            else:
                level = "INFO"

        timestamp = QTime.currentTime().toString("hh:mm:ss")
        
        # Choose text color based on level
        if level == "ERROR":
            color = "#f44336"  # Red
            lvl_lbl = "[ERROR]"
        elif level == "WARNING":
            color = "#ffb74d"  # Orange/Yellow
            lvl_lbl = "[WARN]"
        else:
            color = "#8892b0"  # Muted Blue-grey
            lvl_lbl = "[INFO]"
            
        # Mirror to the durable rotating log file so the console output survives
        # the session (the on-screen console is bounded and cleared on exit).
        try:
            import logging
            _lg = logging.getLogger("hybmesh.gui")
            _lvl = (logging.ERROR if level == "ERROR"
                    else logging.WARNING if level == "WARNING" else logging.INFO)
            _lg.log(_lvl, clean_message)
        except Exception:
            # Deliberately silent, and the only place in the GUI that should be:
            # this IS the write-to-log-file path, so logging the failure would
            # re-enter it. The on-screen console below still shows the message.
            pass

        # Escape potential HTML characters in message to prevent formatting injection
        safe_message = clean_message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        # pre-wrap, not the HTML default: append() parses this as rich text, which
        # folds every run of spaces into one. The mesher's column-aligned blocks
        # (the parameter banner, "[ Mesh Size Field ]") are built from padding, so
        # without this they arrive in the console as ragged one-space soup.
        # pre-wrap rather than pre so a long advisory line still wraps.
        html = (
            f'<span style="color:#6b738c;">[{timestamp}]</span> '
            f'<span style="color:{color}; font-weight:bold;">{lvl_lbl}</span> '
            f'<span style="color:#dde6ff; white-space:pre-wrap;">{safe_message}</span>'
        )
        self.text_edit.append(html)
        self.text_edit.moveCursor(QTextCursor.MoveOperation.End)

    def clear_log(self):
        """Clear all messages from the log."""
        self.text_edit.clear()

    def get_log_text(self) -> str:
        """Return the plain text content of the log (strips HTML formatting)."""
        return self.text_edit.toPlainText()

    def save_log(self):
        """Prompt for a path and write the console contents to a .log file."""
        try:
            from app.utils import repo_root
            start_dir = os.path.join(repo_root(), "results")
        except Exception:
            start_dir = ""
        # Stamp the default filename with the date + time so successive saves
        # don't silently overwrite one another (console_YYYYMMDD_HHMMSS.log).
        stamp = QDateTime.currentDateTime().toString("yyyyMMdd_HHmmss")
        fname = f"console_{stamp}.log"
        default = os.path.join(start_dir, fname) if start_dir else fname
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Log", default, "Log files (*.log);;Text files (*.txt);;All Files (*)")
        if not path:
            return
        if not os.path.splitext(path)[1]:
            path += ".log"
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.get_log_text())
            self.log(f"Console log saved to {path}")
        except OSError as e:
            self.log(f"[ERROR] Failed to save log: {e}")
