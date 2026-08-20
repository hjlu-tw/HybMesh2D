import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel, QFileDialog
)
from PyQt6.QtCore import QTime, QDateTime
from PyQt6.QtGui import QTextCursor

from app.services import user_log


class LogPanel(QWidget):
    """The on-screen adapter of :mod:`app.services.user_log`.

    This panel RENDERS; it does not decide. Which level a line is, and whether it
    reaches the durable log file, both belong to the service — so a headless run
    (which has no panel at all) keeps its user-facing log, and the classification
    edge cases can be tested without a QApplication.

    ``MainWindow`` registers :meth:`log` as a sink, so calling it directly is
    equivalent to a display-only ``user_log.log()``; prefer the service (or
    ``AppController.log``) unless you specifically mean "show this here".
    """

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
        """Render one line with a timestamp and level colour coding.

        The durable file mirror is NOT done here — ``user_log.log()`` has already
        done it before fanning out to this sink, and doing it again would write
        every line twice.
        """
        if not message:
            return

        level, clean_message = user_log.classify(str(message), level)

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
            user_log.log(f"Console log saved to {path}")
        except OSError as e:
            user_log.log(f"[ERROR] Failed to save log: {e}")
