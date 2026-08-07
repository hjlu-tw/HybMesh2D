#!/usr/bin/env python3
"""The batch queue GUI: the parts a headless test can actually prove.

``services/batch_runner`` was already covered by tests/test_batch_runner.py; what was
missing was any way to drive it from the GUI, watch it, or stop it.

What this pins down:
 1. The dialog is created once and re-shown — a queue someone assembled must survive
    closing the window, and a running batch must survive it too.
 2. An unreadable script becomes a visible `skipped` row WITH the reason, rather than
    being dropped: a batch that quietly runs 9 of your 10 cases is worse than one that
    fails.
 3. Name collisions are shown as soon as the scripts are added — before the run, while
    it is still cheap to fix — and name the SOURCE FILES, which is the actionable fact.
 4. A real two-case batch runs end to end through the GUI path with the real binaries,
    and each row reaches `ok`.
 5. **Cancel stops the case already running**, not just the queue. `should_stop()` alone
    would mean Cancel does nothing visible until the current mesh or solve finishes.
    Verified by signalling a real child process, including the race where the cancel
    arrives while the process is still starting.
 6. The end-of-batch summary is not clobbered by the row refresh (a real bug: the label
    showed "N case(s) queued" the instant a batch finished).
 7. `on_process` is threaded all the way through pipeline_runner, which is what makes
    (5) possible at all.
 8. The batch worker is in the shutdown join list, so quitting cannot orphan a mesher.

Run:  python3 tools/PreProcessor/tests/test_batch_queue_gui.py
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >600s", flush=True)
    os._exit(99)


_wd = threading.Timer(600, _watchdog)
_wd.daemon = True
_wd.start()

from PyQt6.QtCore import QEventLoop, QTimer  # noqa: E402
from PyQt6.QtWidgets import QApplication, QDialog  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

# ── 7. the cancel plumbing exists in the runner ───────────────────────────
runner_src = open(os.path.join(_GUI, "app", "services", "pipeline_runner.py"),
                  encoding="utf-8").read()
check("on_process=None) -> int:" in runner_src
      and "if on_process is not None:" in runner_src,
      "7. _stream hands the live child to its caller")
check(runner_src.count("on_process=on_process") >= 6,
      f"7. every stage forwards on_process, so no stage is silently uncancellable "
      f"({runner_src.count('on_process=on_process')} forwards)")
batch_src = open(os.path.join(_GUI, "app", "services", "batch_runner.py"),
                 encoding="utf-8").read()
check("on_process=on_process" in batch_src,
      "7. run_batch forwards it to the pipeline runner")

# ── 8. shutdown ───────────────────────────────────────────────────────────
life = open(os.path.join(_GUI, "app", "controllers", "lifecycle_ctrl.py"),
            encoding="utf-8").read()
check('_batch_worker' in life,
      "8. the batch worker is joined on shutdown — its children are in their own "
      "process groups precisely so they survive a crash, which is the wrong behaviour "
      "for a deliberate quit")

# ── 5. cancel signals a live child ────────────────────────────────────────
from app.workers.batch_run import BatchRunWorker  # noqa: E402
from app.workers.proc_util import popen_kwargs  # noqa: E402


def _wait_dead(proc, timeout=8.0):
    end = time.time() + timeout
    while time.time() < end:
        if proc.poll() is not None:
            return True
        time.sleep(0.05)
    return False


w = BatchRunWorker([])
child = subprocess.Popen(["sleep", "60"], **popen_kwargs())
w._note_process(child)
check(child.poll() is None, "5. (setup) the child is running")
w.cancel()
check(_wait_dead(child),
      "5. Cancel terminates the stage already running — not only the queue, which "
      "would leave Cancel doing nothing visible for the length of a solve")
check(w.is_cancelled(), "5. ...and the queue is marked to stop as well")

w2 = BatchRunWorker([])
w2.cancel()                                   # cancel BEFORE any child exists
late = subprocess.Popen(["sleep", "60"], **popen_kwargs())
w2._note_process(late)
check(_wait_dead(late),
      "5. a cancel arriving while the process was still starting is not lost")

# ── 1/2/3. the dialog ─────────────────────────────────────────────────────
from app.controller import AppController  # noqa: E402

ctl = AppController()
dlg = ctl.open_batch_dialog()
check(isinstance(dlg, QDialog) and not dlg.isModal(),
      "1. the queue is a MODELESS dialog — the point of a batch is to leave it running")
check(dlg.parent() is ctl.main_window,
      "1. it is parented to the main window (the project's rule for every dialog)")

tmp = tempfile.mkdtemp(prefix="hybmesh_batch_test_")
base = json.load(open(os.path.join(_REPO, "config", "pipeline", "naca_demo.json"),
                      encoding="utf-8"))


def _script(name: str, case: str) -> str:
    d = json.loads(json.dumps(base))
    d["name"] = case
    d.setdefault("solver", {})["skip"] = True      # mesh only: keeps the test honest
    path = os.path.join(tmp, name)                 # and finishes in seconds
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f)
    return path


ok_a = _script("a.json", "batch_test_a")
ok_b = _script("b.json", "batch_test_b")
dup_a = _script("dup.json", "batch_test_a")       # collides with ok_a
broken = os.path.join(tmp, "broken.json")
with open(broken, "w", encoding="utf-8") as f:
    f.write("{ not json")

logged = []
dlg.log_sink = logged.append
dlg.add_paths([ok_a, ok_b, broken], log=logged.append)
check(dlg.table.rowCount() == 3, f"2. every path is queued ({dlg.table.rowCount()})")
statuses = [dlg.table.item(r, 2).text() for r in range(3)]
check(statuses.count("skipped") == 1,
      f"2. the unreadable script is a visible skipped row, not silently dropped "
      f"({statuses})")
detail = [dlg.table.item(r, 4).text() for r in range(3)]
check(any("unreadable" in d for d in detail),
      f"2. ...and says why ({[d[:40] for d in detail]})")

check(not dlg.collision_label.isVisible(),
      "3. no collision warning when the names are distinct")
dlg.add_paths([dup_a], log=logged.append)
check(dlg.collision_label.isVisible(),
      "3. a shared case name is flagged as soon as the script is added — before the "
      "run, when it is still cheap to fix")
text = dlg.collision_label.text()
check("a.json" in text and "dup.json" in text,
      f"3. the warning names the SOURCE FILES (what to edit), not the case name twice "
      f"({text[-70:]})")

# The dialog is not rebuilt, so the queue survives closing it.
dlg.close()
again = ctl.open_batch_dialog()
check(again is dlg and again.table.rowCount() == 4,
      "1. re-opening returns the same dialog with the queue intact")

# ── 4/6. a real run ───────────────────────────────────────────────────────
dlg.clear_jobs()
dlg.add_paths([ok_a, ok_b], log=logged.append)
dlg.run_solver_cb.setChecked(False)
dlg.run_ib_cb.setChecked(False)
dlg.jobs[0].status = "failed"          # stale state from a previous run
dlg.jobs[0].error = "old error"

ctl.run_batch_queue()
check(ctl._batch_worker is not None, "4. the run starts a worker")
check(not dlg.run_btn.isEnabled() and dlg.cancel_btn.isEnabled(),
      "4. Run is disabled and Cancel enabled while running")
check(not dlg.add_btn.isEnabled(),
      "4. the queue cannot be edited mid-run")

summary = {}
loop = QEventLoop()
ctl._batch_worker.finished_signal.connect(lambda s: (summary.update(s), loop.quit()))
QTimer.singleShot(540000, loop.quit)
loop.exec()

check(summary.get("ok") == ["batch_test_a", "batch_test_b"],
      f"4. both cases ran through the GUI path with the real binaries "
      f"({summary.get('ok')}, failed={summary.get('failed')})")
row_status = [dlg.table.item(r, 2).text() for r in range(dlg.table.rowCount())]
check(row_status == ["ok", "ok"],
      f"4. each row reached ok as the batch progressed ({row_status})")
check(all(dlg.table.item(r, 3).text().endswith("s")
          for r in range(dlg.table.rowCount())),
      "4. and carries its elapsed time")
check(not dlg.jobs[0].error,
      "4. a re-run clears the previous attempt's status instead of showing stale "
      "failures next to fresh results")
check(dlg.jobs[0].artifacts.get("vtk", "").endswith(".vtk")
      and os.path.exists(dlg.jobs[0].artifacts["vtk"]),
      f"4. the mesh really was produced ({dlg.jobs[0].artifacts.get('vtk')})")

check("ok" in dlg.status_label.text() and "queued" not in dlg.status_label.text(),
      f"6. the summary survives the row refresh — it used to be overwritten with the "
      f"queue count at the exact moment the result mattered "
      f"({dlg.status_label.text()!r})")
check("done" in dlg.progress.format(),
      f"6. the progress bar reports completion ({dlg.progress.format()!r})")
check(dlg.run_btn.isEnabled() and not dlg.cancel_btn.isEnabled(),
      "6. and the buttons are restored")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
