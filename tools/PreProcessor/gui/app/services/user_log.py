"""The USER-FACING log, as a module instead of a widget (Qt-free).

There are two logs in this GUI and they answer different questions.
:mod:`app.services.logging_setup` is the DEVELOPER log — a rotating file under
``results/logs/gui.log`` that exists so a crash can be diagnosed after the fact.
This module is the log the user is *shown*: the OUTPUT CONSOLE lines that say
which grid was picked, which BC was restored, why a stage refused to run.

It used to have no seam at all. Business logic reached through the view tree —
``self.main_window.log_panel.log(...)``, 255 call sites, by a wide margin the
most-touched thing in the codebase — so:

  * the level-classification below, which is pure string work with several
    hard-won edge cases (the mesher's own stamp, the solver's "eL2 error norm"
    false positive, native-crash tokens carrying none of the words it looks
    for), was only reachable by constructing a QWidget,
  * a test could only observe the log by monkey-patching a Qt widget's method,
  * a Qt-free service that takes a ``log=`` callback (``prepare_case_dir``) was
    being handed a *widget bound method*, and a worker's ``log_signal`` was
    wired straight to one — so the seam existed in fact while being denied in
    the design,
  * and every one of those call sites hard-required a ``main_window`` to exist,
    which is why the headless entry points each grew their own private answer
    instead (``run_pipeline.py`` defines ``log = print``;
    ``result_playback_mixin`` hand-rolled a "is there a console?" fallback).

So: the classification is :func:`classify` (Qt-free, unit-testable), the file
mirror always happens here, and anything that wants to DISPLAY the log registers
as a sink. ``LogPanel`` is one such adapter and a test recorder is another —
which is what makes this a real seam rather than a hypothetical one. With no
sink at all the message still reaches the durable log rather than vanishing,
so a controller path driven without a window degrades instead of failing.

Sinks are handed the RAW message (one positional argument), not the classified
pair, so every adapter classifies for itself and stays self-contained.
"""
from __future__ import annotations

import logging
import re
from typing import Callable, Iterable

#: A sink displays one user-facing message. It receives the raw text, exactly as
#: the caller wrote it (ANSI escapes and emitter stamps included).
Sink = Callable[[str], None]

LEVELS = ("INFO", "WARNING", "ERROR")

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
# reach this module. A display sink renders its OWN clock + level label, so an
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

_ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

_sinks: list[Sink] = []


def classify(message: str, level: str | None = None) -> tuple[str, str]:
    """Resolve ``(level, clean_message)`` for one user-facing line.

    ``clean_message`` has ANSI escapes and the emitter's own ``[<ISO>] [LEVEL]``
    stamp removed; component tags like ``[Pipeline]`` are NOT level tags and are
    kept. An explicit *level* is taken as given and only the cleaning is done, so
    re-classifying an already-classified line is stable.

    Priority: an explicit argument, then ANSI colour, then the emitter's own
    level tag, then keyword heuristics — most authoritative first.
    """
    if not message:
        return (level or "INFO", "")

    # Colour-coded output is tagged by ANSI escapes, which the strip below
    # removes — so read them off the raw message first.
    if level is None:
        if "\x1b[1;31m" in message or "\x1b[31m" in message:
            level = "ERROR"
        elif "\x1b[1;33m" in message or "\x1b[33m" in message:
            level = "WARNING"

    clean = _ANSI_ESCAPE.sub('', message)

    m = _LEVEL_PREFIX.match(clean)
    if m:
        clean = clean[m.end():]
        if level is None:
            tag = m.group("level").upper()
            level = "WARNING" if tag == "WARN" else tag

    # Only guess when nothing authoritative said otherwise.
    if level is None:
        lower = clean.lower()
        # "eL2 error norm ..." is the solver's per-iteration residual metric
        # echoed on stdout, not a failure — don't let the "error" substring in
        # "error norm" mis-tag these convergence lines as ERROR. Match the
        # solver's own "eL2 error norm" token (not a bare "error norm"), so a
        # genuine error that happens to contain the words "error norm" is still
        # surfaced as ERROR.
        if "el2 error norm" in lower:
            level = "INFO"
        elif ("error" in lower or "failed" in lower
              # Native-crash / linker signatures that don't contain the word
              # "error" would otherwise render as muted INFO — the one line that
              # explains a crash must stand out as ERROR.
              or any(tok in lower for tok in _CRASH_TOKENS)):
            level = "ERROR"
        elif "warning" in lower or "warn" in lower:
            level = "WARNING"
        else:
            level = "INFO"

    return level, clean


def add_sink(sink: Sink) -> None:
    """Register a display adapter. Re-registering the same sink is a no-op."""
    if sink not in _sinks:
        _sinks.append(sink)


def remove_sink(sink: Sink) -> None:
    """Unregister a display adapter; unknown sinks are ignored."""
    if sink in _sinks:
        _sinks.remove(sink)


def sinks() -> tuple[Sink, ...]:
    """The registered adapters, for tests and for shutdown ordering."""
    return tuple(_sinks)


def log(message, level: str | None = None) -> None:
    """Emit one user-facing line: mirror it to the log file, then show it.

    Safe with no sinks registered, which is the headless case — the message
    still reaches ``results/logs/gui.log`` instead of vanishing.

    A sink that raises must not take down the caller (this is called from
    subprocess-output slots), so a failing sink is reported to the developer log
    and the remaining sinks still run.
    """
    if not message:
        return
    message = str(message)
    resolved, clean = classify(message, level)

    _lvl = (logging.ERROR if resolved == "ERROR"
            else logging.WARNING if resolved == "WARNING" else logging.INFO)
    try:
        logging.getLogger("hybmesh.gui").log(_lvl, clean)
    except Exception:
        # Deliberately silent, and one of the few places that should be: this IS
        # the write-to-log-file path, so logging the failure would re-enter it.
        # The sinks below still show the message.
        pass

    for sink in tuple(_sinks):
        try:
            sink(message)
        except Exception:
            from app.services.logging_setup import get_logger
            get_logger(__name__).warning(
                "user-log sink %r failed; message not displayed", sink,
                exc_info=True)


def log_all(messages: Iterable[str], level: str | None = None) -> None:
    """Emit several lines in order. Convenience for multi-line reports."""
    for m in messages:
        log(m, level)
