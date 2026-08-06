"""Durable, file-based diagnostics for the GUI (Qt-free setup).

The on-screen OUTPUT CONSOLE is ephemeral (bounded to 1000 lines and gone when
the app closes). Industrial tools always leave a log file behind so a user can
attach it to a bug report after a crash. This module:

  * configures a rotating file handler under results/logs/gui.log, and
  * installs a sys.excepthook so an *uncaught* exception (e.g. raised inside a
    Qt slot) is recorded with a full traceback instead of vanishing to stderr.

Call configure_logging() once, as early as possible in main().
"""
from __future__ import annotations
import logging
import logging.handlers
import os
import sys

LOGGER_NAME = "hybmesh.gui"
_configured = False


def _log_dir() -> str:
    try:
        from app.utils import repo_root
        base = repo_root()
    except Exception:
        base = os.getcwd()
    d = os.path.join(base, "results", "logs")
    os.makedirs(d, exist_ok=True)
    return d


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Set up the ``hybmesh.gui`` logger with a rotating file handler and an
    uncaught-exception hook. Idempotent."""
    global _configured
    logger = logging.getLogger(LOGGER_NAME)
    if _configured:
        return logger
    logger.setLevel(level)
    logger.propagate = False

    try:
        path = os.path.join(_log_dir(), "gui.log")
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(message)s", "%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
    except Exception:
        # Never let logging setup take the app down; the console still works.
        pass

    _install_excepthook(logger)
    _configured = True
    logger.info("=== GUI session started (pid %s) ===", os.getpid())
    return logger


def _install_excepthook(logger: logging.Logger):
    prev = sys.excepthook

    def hook(exc_type, exc, tb):
        # KeyboardInterrupt should still exit quietly.
        if not issubclass(exc_type, KeyboardInterrupt):
            logger.critical("Uncaught exception",
                            exc_info=(exc_type, exc, tb))
            _maybe_show_dialog(exc_type, exc)
        prev(exc_type, exc, tb)

    sys.excepthook = hook


def _maybe_show_dialog(exc_type, exc):
    """Show a non-fatal error dialog for an uncaught exception when a GUI is up
    (skipped on headless/offscreen so tests and batch runs don't block)."""
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance()
        if app is None or app.platformName() in ("offscreen", "minimal"):
            return
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("Unexpected Error")
        box.setText("An unexpected error occurred. The application may be "
                    "unstable — consider saving your work to a new file.")
        box.setInformativeText(f"{exc_type.__name__}: {exc}")
        box.setDetailedText("A full traceback was written to results/logs/gui.log.")
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()
    except Exception:
        pass
