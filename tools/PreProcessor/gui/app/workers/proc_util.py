"""Shared subprocess launch / termination helpers for the worker QThreads.

Two things every worker needs and none of them should re-invent:

* **Launch in its own process group** (``start_new_session=True``). The C++
  stages spawn helpers of their own (gmsh writes temporaries, the solver chain
  forks), and signalling only the direct child leaves those as orphans that keep
  holding the case directory.

* **Escalate SIGTERM -> SIGKILL.** A bare ``proc.terminate()`` is a request, not
  a guarantee: a mesher wedged inside a third-party library can ignore SIGTERM
  indefinitely, and any caller that then joins the worker — notably the app's
  close handler — would block forever with no way out but ``kill -9``.

Cancel is driven from the GUI thread, so the escalation must never block it:
:func:`stop_process_async` signals immediately and hands the timed follow-up to a
short-lived daemon thread. :func:`stop_process` is the blocking variant, for
callers that genuinely want to wait (bounded) for the child to be gone.
"""
from __future__ import annotations

import os
import signal
import subprocess
import threading

# Seconds a SIGTERM'd process (and its group) gets to exit before SIGKILL.
TERMINATE_GRACE_S = 5.0

# Process-group signalling is POSIX-only; on a platform without it we fall back
# to signalling the direct child.
_HAVE_PGID = hasattr(os, "killpg") and hasattr(os, "getpgid")


def popen_kwargs(**extra) -> dict:
    """Base ``Popen`` kwargs shared by the streaming workers.

    Merged text-mode line-buffered pipes (stderr folded into stdout, matching the
    existing log-panel severity colouring) plus ``start_new_session`` so the
    child is killable as a tree. Any keyword given in ``extra`` overrides the
    default of the same name.
    """
    kwargs = dict(
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,               # line-buffered
        start_new_session=True,  # own process group -> signal the whole tree
    )
    kwargs.update(extra)
    return kwargs


def _signal_tree(proc: subprocess.Popen, sig) -> None:
    """Send ``sig`` to the child's process group, falling back to the child.

    The fallback matters when the child was not started with
    ``start_new_session`` (an older call site, or a platform without process
    groups): signalling just the child is still better than nothing.
    """
    if proc is None:
        return
    if _HAVE_PGID:
        try:
            os.killpg(os.getpgid(proc.pid), sig)
            return
        except (ProcessLookupError, PermissionError, OSError):
            pass  # already reaped, or not our group leader — try the child
    try:
        proc.send_signal(sig)
    except (ProcessLookupError, ValueError, OSError):
        pass


def kill_process(proc: subprocess.Popen) -> None:
    """SIGKILL the child's process tree right now, without a grace period."""
    if proc is None or proc.poll() is not None:
        return
    _signal_tree(proc, signal.SIGKILL)


def stop_process(proc: subprocess.Popen,
                 grace: float = TERMINATE_GRACE_S) -> bool:
    """Terminate ``proc``'s process tree, escalating to SIGKILL after ``grace``.

    Blocks for at most ``2 * grace`` seconds. Returns True if the process is
    gone, False if even SIGKILL did not reap it within the second grace window
    (a zombie whose parent bookkeeping is stuck — the caller should log and move
    on rather than wait forever).
    """
    if proc is None or proc.poll() is not None:
        return True
    _signal_tree(proc, signal.SIGTERM)
    try:
        proc.wait(timeout=grace)
        return True
    except subprocess.TimeoutExpired:
        pass
    _signal_tree(proc, signal.SIGKILL)
    try:
        proc.wait(timeout=grace)
        return True
    except subprocess.TimeoutExpired:
        return False


def stop_process_async(proc: subprocess.Popen,
                       grace: float = TERMINATE_GRACE_S) -> None:
    """SIGTERM ``proc``'s tree now; escalate to SIGKILL later, off-thread.

    Safe to call from the GUI thread: it returns as soon as the signal is sent,
    so a Cancel button never freezes the UI for the grace period. The daemon
    thread that performs the escalation cannot outlive the process.
    """
    if proc is None or proc.poll() is not None:
        return
    _signal_tree(proc, signal.SIGTERM)

    def _escalate():
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            _signal_tree(proc, signal.SIGKILL)
        except Exception:
            # Concurrent wait() from the worker thread may have reaped it first;
            # either way there is nothing left to escalate to.
            pass

    threading.Thread(target=_escalate, daemon=True,
                     name="hybmesh-proc-stop").start()
