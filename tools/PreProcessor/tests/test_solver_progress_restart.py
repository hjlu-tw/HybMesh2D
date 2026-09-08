#!/usr/bin/env python3
"""The solver progress bar measures THIS run, not an absolute iteration count.

USER-REPORTED (2026-08-20): "在跑restart的時候進度條會直接顯示100%".

The solver prints an ABSOLUTE "Global Iteration count" -- on a restart it
continues from the dump it resumed (20000, say) -- while ``num_half_iter`` is
what this run was asked to do (5000). ``_emit_progress`` divided one by the
other, so ``min(it/total, 1.0)`` was 1.0 at the very first convergence print
and the bar sat at 100% for the whole run.

The GUI cannot look the dump's iteration up: SolverConfig carries ``restart``
plus two filenames and no step number. So the anchor is the run's OWN first
print, which is also the more robust choice -- it holds whether the solver
numbers absolutely or from zero, and whichever dump was resumed.

A fresh run's numbers must not move: its first print lands at
``print_convg_per_niter``, so that step is what the anchor subtracts.

Run: python3 tools/PreProcessor/tests/test_solver_progress_restart.py
"""
import os
import sys
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >60s", flush=True)
    os._exit(99)


_wd = threading.Timer(60, _watchdog)
_wd.daemon = True
_wd.start()

from PyQt6.QtWidgets import QApplication                  # noqa: E402
app = QApplication.instance() or QApplication(sys.argv)
from app.workers.solver_run import SolverPipelineWorker   # noqa: E402
from app.models.solver_config import SolverConfig         # noqa: E402


def run_prints(first_iter, n_prints=5, per=1000, n_half_iter=5000,
               explicit=True):
    """Feed a worker `n_prints` convergence prints; return the progress values.

    `first_iter` is the absolute iteration of the FIRST print -- `per` for a
    fresh run, dump + `per` for a restart.
    """
    cfg = SolverConfig()
    cfg.num_half_iter = n_half_iter
    cfg.print_convg_per_niter = per
    w = SolverPipelineWorker(cfg)
    seen = []
    w.progress_signal.connect(seen.append)
    for k in range(n_prints):
        it = first_iter + k * per
        lines = []
        if explicit:
            lines.append(f"  Global Iteration count  {it}")
        lines += ["  cfl = 0.5",
                  "  eL2 error norm for int. region =  1.0e-3  2.0e-3",
                  "  eL2 error norm of bound. region =  1.0e-4"]
        for ln in lines:
            w._parse_solver_output(ln)
    return seen


# ── 1. a fresh run is unchanged ──────────────────────────────────────────
fresh = run_prints(1000)
check(fresh == [40, 55, 70, 85, 100],
      f"1. a fresh run still ramps 40..100 exactly as before (got {fresh})")

# ── 2. a restart run ramps too, instead of pinning at 100 ────────────────
rest = run_prints(20000 + 1000)
check(rest == fresh,
      f"2. a restart resumed at 20000 reports the SAME ramp as the fresh run "
      f"doing the same work (got {rest})")
check(rest[0] < 100,
      f"2. ...so the first convergence print is not already 100% (got {rest[0]})")

# ── 3. the anchor is the run's own first print, at any resume point ──────
# What this establishes and what it does NOT. `run_prints(dump + per)` builds the
# first print at resume + per, which is the anchor's own formula, so this cannot
# fail however the anchor is written -- it pins that the ramp is independent of the
# resume MAGNITUDE (a real property: an absolute counter must not leak into the
# fraction), not that the anchor is the right one.
for dump in (0, 1, 7, 999_999):
    got = run_prints(dump + 1000)
    check(got == fresh,
          f"3. the ramp is independent of the resume magnitude, at {dump} "
          f"(got {got})")

# ── 3b. so pin the ASSUMPTION the anchor rests on, and its sensitivity ────
# The anchor subtracts one print interval from the run's first print, which is
# right exactly when the solver prints at multiples of print_convg_per_niter PAST
# the resume point -- the convention a fresh run demonstrably follows (its first
# print is at `per`, which is why check 1 starts at 40 and not at 25).
#
# Nothing here can observe a real restart, so the alternative is MEASURED rather
# than assumed away: if a build's first print after a restart were the resumed
# step ITSELF, that print represents no work done, and the bar would open at 40%
# and reach 100% one print early. Recorded so that a reader seeing that on a real
# run knows both that it is this line to change and what the symptom looks like.
first_print_is_resume = run_prints(20_000, n_prints=6)
check(first_print_is_resume[0] == fresh[0] and first_print_is_resume[4] == 100,
      f"3b. ASSUMPTION: the anchor reads the first print as one interval PAST the "
      f"resume. Were it the resume itself, the ramp would open at {fresh[0]}% for "
      f"zero work and hit 100% a print early (measured: "
      f"{first_print_is_resume})")
check(fresh[0] == 40 and run_prints(1000, n_prints=1)[0] == 40,
      "3b. ...and the convention it copies is the fresh run's own: the first "
      "print lands at print_convg_per_niter, one interval in, not at zero")

# ── 4. overshoot is still clamped ────────────────────────────────────────
long_run = run_prints(1000, n_prints=8)     # 8 prints, only 5000 asked for
check(max(long_run) == 100 and long_run[-1] == 100,
      f"4. running past num_half_iter clamps at 100 rather than exceeding it "
      f"(got {long_run})")
check(all(a <= b for a, b in zip(long_run, long_run[1:])),
      f"4. ...and progress never goes backwards (got {long_run})")

# ── 5. the synthetic counter (no explicit header) still works ───────────
# Some solver builds print no "Global Iteration count"; the worker then counts
# prints itself, starting at 0. That path must not be knocked off by the anchor.
syn = run_prints(0, explicit=False)
check(syn == sorted(syn) and syn[0] < syn[-1],
      f"5. with no iteration header the synthetic counter still ramps (got {syn})")
check(syn[0] == 25,
      f"5. ...starting at the stage floor, not above it (got {syn[0]})")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED")
    for m in _FAILS:
        print("  - " + m)
    sys.stdout.flush()
    os._exit(1)
print("\nRESULT: ALL PASS")
sys.stdout.flush()
os._exit(0)
