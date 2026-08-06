"""Sentinel return codes shared by the worker QThreads.

A child process killed by a POSIX signal reports ``Popen.returncode`` as the
*negated* signal number (e.g. SIGINT(2) -> -2, SIGQUIT(3) -> -3). The workers
also emit their own out-of-band "reason" codes on ``finished_signal``; if those
reused the small negative range they would collide with ``-signal`` and a real
backend *crash* would be misreported as a user cancel / timeout (and, in the
mesh path, would even suppress the self-intersection diagnostic).

These sentinels are therefore chosen far below any realistic ``-signal`` value
so a crash can never masquerade as a benign cancel/timeout. Keep them in sync
with every ``finished_signal.emit(...)`` reason path and every controller that
interprets the code (mesh_gen_ctrl, solver_ctrl, backend_ctrl, stl3d_ctrl).
"""
from __future__ import annotations

RC_EXCEPTION = -1001   # worker raised, or the subprocess failed to launch
RC_CANCELLED = -1002   # user cancelled the run
RC_TIMEOUT = -1003     # watchdog timeout expired

_LABELS = {
    RC_EXCEPTION: "error",
    RC_CANCELLED: "cancelled by user",
    RC_TIMEOUT: "timed out",
}


def is_reason(rc: int) -> bool:
    """True if ``rc`` is one of our out-of-band reason sentinels (not a real
    process exit / -signal code)."""
    return rc in _LABELS


def describe(rc: int) -> str | None:
    """Human phrase for a reason sentinel, or None for a real process code."""
    return _LABELS.get(rc)
