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
_handler_attached = False


def get_logger(name: str | None = None) -> logging.Logger:
    """Logger for a GUI module: ``get_logger(__name__)``.

    Always a child of ``hybmesh.gui``, so everything lands in the same rotating
    file with the module name attached. Safe before :func:`configure_logging`
    (the records are simply dropped until a handler exists), which is what lets
    module-level use work in tests and headless runs.

    Use this instead of swallowing an exception with ``pass``. A best-effort
    step that is *allowed* to fail belongs at ``debug(..., exc_info=True)``;
    something that should not have failed belongs at ``warning``. Either way the
    traceback survives in results/logs/gui.log, where a silent ``pass`` left
    nothing at all to diagnose a field problem with.
    """
    if not name or name == LOGGER_NAME:
        return logging.getLogger(LOGGER_NAME)
    short = name[4:] if name.startswith("app.") else name
    return logging.getLogger(f"{LOGGER_NAME}.{short}")


def _log_dir() -> str:
    try:
        from app.utils import repo_root
        base = repo_root()
    except Exception:
        base = os.getcwd()
    d = os.path.join(base, "results", "logs")
    os.makedirs(d, exist_ok=True)
    return d


def _env_level(default: int) -> int:
    """Log level from ``HYBMESH_LOG_LEVEL``, else ``default``.

    Best-effort diagnostics are logged at DEBUG, which INFO (the default) drops.
    An env var is what makes them reachable when a user is actually chasing a
    problem — ``HYBMESH_LOG_LEVEL=DEBUG python3 tools/PreProcessor/gui/main.py``
    — without leaving verbose logging on for everyone.
    """
    raw = (os.environ.get("HYBMESH_LOG_LEVEL") or "").strip().upper()
    if not raw:
        return default
    named = getattr(logging, raw, None)
    if isinstance(named, int):
        return named
    try:
        return int(raw)
    except ValueError:
        return default


def ensure_file_logging(level: int = logging.INFO) -> logging.Logger:
    """Attach the rotating file handler if nothing has attached one yet.

    Idempotent, and deliberately does NOT install the excepthook: this is called
    lazily from library code (:func:`app.services.user_log.log`) so that a
    process which never runs the GUI's ``main()`` still leaves its user-facing
    log on disk, and a library call must not quietly take over ``sys.excepthook``
    on the way. :func:`configure_logging` is the entry point that does both.

    Without this, a record emitted before anything configured the logger was
    simply dropped — measured: a headless ``user_log.log()`` left
    ``results/logs/gui.log`` byte-for-byte unchanged, so the durable log that the
    seam exists to guarantee did not actually exist outside the GUI process.
    """
    global _handler_attached
    logger = logging.getLogger(LOGGER_NAME)
    if _handler_attached:
        return logger
    _handler_attached = True          # set first: a failure must not retry per call
    logger.setLevel(_env_level(level))
    logger.propagate = False

    try:
        path = os.path.join(_log_dir(), "gui.log")
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
        # %(name)s carries the module (get_logger(__name__)), so a logged
        # best-effort failure can be traced back to its call site.
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
            "%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
    except Exception:
        # Never let logging setup take the app down; the console still works.
        pass
    return logger


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    """Set up the ``hybmesh.gui`` logger with a rotating file handler and an
    uncaught-exception hook. Idempotent.

    ``HYBMESH_LOG_LEVEL`` overrides ``level`` (e.g. ``DEBUG`` to include the
    best-effort/teardown diagnostics)."""
    global _configured
    logger = ensure_file_logging(level)
    if _configured:
        return logger
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
        # Deliberately silent: we are already inside the uncaught-exception hook,
        # and the traceback that matters has just been written to the log file by
        # the caller. Raising (or logging) from here would only mask it.
        pass
