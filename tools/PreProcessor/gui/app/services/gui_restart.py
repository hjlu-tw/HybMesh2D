"""How to start a brand-new GUI process — the decision, with no Qt in it.

The toolbar's "Restart" closes this window and opens a fresh one. Closing is
Qt's business (:meth:`AppController.restart_gui` drives it); *what to launch* is
a plain question about paths and subprocess arguments, so it lives here where a
headless test can ask it without a window.

Three things about the launch are deliberate and each one has already been a
defect somewhere in this repo:

* **The entry point is resolved through :func:`app.services.paths.repo_root`**,
  never by counting ``..`` segments from ``__file__``. That off-by-one has been
  shipped here once already (``find_binary_executable`` walked five levels from
  ``gui/app`` and resolved *outside* the repo) and is gated by
  ``tests/test_qt_free_seam.py``.

* **The pipes are ``DEVNULL``, not pipes.** ``app/workers/proc_util.popen_kwargs``
  exists for the streaming workers and sets ``stdout``/``stderr`` to ``PIPE`` so a
  worker thread can drain them. Reusing that bundle here would hand the child two
  pipes whose only reader — this process — is about to exit, and the child would
  stall the moment the buffer filled. ``start_new_session=True`` is repeated here
  on purpose rather than inherited from a bundle built for a different job.

* **Nothing is passed to the child.** The request is a *brand-new* session, not a
  second view of this case, so no geometry, workspace or script travels.

:func:`preflight` exists because of the ordering the whole feature turns on: the
window is closed *first* and the child spawned only if the close really happened,
so a bad interpreter or a missing script has to be caught while there is still a
window to report it in.
"""
from __future__ import annotations
import os
import subprocess
import sys

from app.services.paths import repo_root

__all__ = ["entry_script", "restart_command", "preflight", "launch"]

# Relative to the repo root, so the one path fact is written once.
ENTRY_REL = os.path.join("tools", "PreProcessor", "gui", "main.py")


def entry_script() -> str:
    """Absolute path to the GUI entry point a new instance would run."""
    return os.path.join(repo_root(), ENTRY_REL)


def restart_command() -> tuple[list[str], dict]:
    """The ``(argv, popen_kwargs)`` a restart would use.

    Split out from :func:`launch` so a test can pin it without spawning a second
    GUI: the argv and the kwargs *are* the behaviour worth checking, and running
    them is not.
    """
    argv = [sys.executable, entry_script()]
    kwargs = dict(
        cwd=repo_root(),
        # The child has to outlive the parent it was launched from, and must not
        # inherit the dying process's signal handling (a Ctrl-C in the terminal
        # that started the old GUI would otherwise reach the new one).
        start_new_session=True,
        # See the module docstring: no reader survives this process, so a pipe is
        # a stall waiting to happen. stdin too — a detached child reading the old
        # terminal would take SIGTTIN.
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return argv, kwargs


def preflight() -> str:
    """``""`` if a restart can be launched, else why it cannot.

    Checked *before* the window closes. Afterwards there is no window to put an
    error in and the user is left with no GUI at all.
    """
    exe = sys.executable
    if not exe or not os.path.isfile(exe):
        return (f"The Python interpreter running this session cannot be found "
                f"again ({exe or 'unknown'}), so a new one cannot be started.")
    entry = entry_script()
    if not os.path.isfile(entry):
        return (f"The GUI entry point is missing:\n{entry}\n\n"
                "A new session cannot be started from this installation.")
    return ""


def launch() -> subprocess.Popen:
    """Start a detached, argument-free GUI process. Raises ``OSError`` on failure."""
    argv, kwargs = restart_command()
    return subprocess.Popen(argv, **kwargs)
