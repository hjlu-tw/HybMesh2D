#!/usr/bin/env python3
"""Batch runner (Phase-3 item): several pipeline cases in one queue.

Meshing a parameter sweep or a family of geometries meant launching the pipeline by
hand once per case. Three properties matter more than anything else, because a batch
is what you leave running unattended — and each is asserted here:

* **One bad case must not kill the queue.** Aborting the night's work because job 3
  of 40 had an inverted domain is what makes people stop using batch mode.
* **Jobs must not overwrite each other.** Output paths derive from the case name, so
  a shared name means silent clobbering. Collisions are detected BEFORE anything
  runs and reported by SOURCE FILE — repeating the shared name back at the user
  ("used by case_b, case_b") tells them nothing about which file to edit.
* **Exit code 0 only when every queued case succeeded.** A batch that "finished"
  with 12 failures must not look green to a scheduler.

Checks:
 1. load_jobs turns unreadable/missing paths into `skipped` jobs instead of raising.
 2. read_manifest honours comments/blanks and resolves relative paths against the
    manifest's own directory.
 3. find_collisions reports the source FILES, not the shared name.
 4. A failing job is recorded and the queue continues to the next one.
 5. An unexpected (non-PipelineError) exception also does not kill the queue, and is
    labelled as unexpected rather than passed off as a normal stage failure.
 6. progress() is called per job and ends at total/total.
 7. should_stop() cancels the remaining queue without touching finished jobs.
 8. exit_code() is 0 only when nothing failed and nothing was skipped.
 9. The summary names each outcome.

Run:  python3 tools/PreProcessor/tests/test_batch_runner.py
"""
import os
import sys
import tempfile
import threading

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
    print("FAIL watchdog: blocked >90s", flush=True)
    os._exit(99)


_wd = threading.Timer(90, _watchdog)
_wd.daemon = True
_wd.start()

import json  # noqa: E402

from app.services import batch_runner as br  # noqa: E402
from app.services import pipeline_runner  # noqa: E402

tmp = tempfile.mkdtemp(prefix="hybmesh_batch_")


def write_script(name, case_name):
    path = os.path.join(tmp, name)
    json.dump({"pipeline_version": 2, "name": case_name,
               "cads": [], "mesh": {"geom_files": ["/tmp/x.dat"]},
               "solver": {"skip": True}},
              open(path, "w", encoding="utf-8"), indent=2)
    return path


a = write_script("a.json", "case_a")
b = write_script("b.json", "case_b")
dup = write_script("dup.json", "case_b")          # same name as b -> collision
bad = os.path.join(tmp, "bad.json")
with open(bad, "w") as f:
    f.write("{ this is not json")
missing = os.path.join(tmp, "nope.json")

# ── 1. tolerant loading ───────────────────────────────────────────────────
jobs = br.load_jobs([a, b, bad, missing])
by_label = {j.label: j for j in jobs}
check(len(jobs) == 4, "1. every path becomes a job, readable or not")
check(by_label["case_a"].config is not None, "1. a valid script is parsed")
check(any(j.status == "skipped" and "unreadable" in j.error for j in jobs),
      "1. malformed JSON becomes a skipped job, not an exception")
check(any(j.status == "skipped" and j.error == "file not found" for j in jobs),
      "1. a missing path becomes a skipped job")

# ── 2. manifest ───────────────────────────────────────────────────────────
manifest = os.path.join(tmp, "cases.txt")
with open(manifest, "w") as f:
    f.write("# a comment\n\na.json\n  b.json  \n")
paths = br.read_manifest(manifest)
check(paths == [os.path.join(tmp, "a.json"), os.path.join(tmp, "b.json")],
      f"2. comments/blanks ignored and relative paths resolved next to the "
      f"manifest ({[os.path.basename(p) for p in paths]})")

# ── 3. collisions name the files ──────────────────────────────────────────
col = br.find_collisions(br.load_jobs([a, b, dup]))
check(list(col) == ["case_b"], f"3. the shared name is identified ({list(col)})")
check(sorted(col.get("case_b", [])) == ["b.json", "dup.json"],
      f"3. ...and reported by SOURCE FILE, which is the actionable fact "
      f"({col.get('case_b')})")
check(not br.find_collisions(br.load_jobs([a, b])),
      "3. distinct names produce no collision")

# ── 4/5/6/9. the queue continues past failures ────────────────────────────
calls = []
real_run = pipeline_runner.run_pipeline


def fake_run(cfg, log=print, **kw):
    calls.append(cfg.name)
    if cfg.name == "case_a":
        raise pipeline_runner.PipelineError("HybMesh2D failed (code 2)")
    if cfg.name == "case_b":
        raise ValueError("something nobody planned for")
    return {"vtk": f"/tmp/{cfg.name}.vtk"}


ok = write_script("ok.json", "case_ok")
pipeline_runner.run_pipeline = fake_run
try:
    prog = []
    jobs = br.load_jobs([a, b, ok])
    summary = br.run_batch(jobs, progress=lambda d, t, lbl: prog.append((d, t)))
finally:
    pipeline_runner.run_pipeline = real_run

check(calls == ["case_a", "case_b", "case_ok"],
      f"4. every job ran despite the first two failing ({calls})")
check(len(summary["failed"]) == 2 and summary["ok"] == ["case_ok"],
      f"4. failures are recorded and the good one still succeeded ({summary['ok']})")
errs = dict(summary["failed"])
check("HybMesh2D failed" in errs["case_a"],
      "4. a PipelineError is reported verbatim")
check("unexpected error" in errs["case_b"],
      f"5. an unexpected exception is labelled as such, not passed off as a "
      f"normal stage failure ({errs['case_b']})")
check(prog and prog[0] == (0, 3) and prog[-1] == (3, 3),
      f"6. progress runs from 0/total to total/total ({prog})")

report = br.format_summary(summary)
check("[ok]" in report and "[FAILED]" in report and "case_ok" in report,
      "9. the summary names each outcome")

# ── 7. cancellation ───────────────────────────────────────────────────────
calls.clear()
pipeline_runner.run_pipeline = lambda cfg, log=print, **kw: (
    calls.append(cfg.name), {"vtk": ""})[1]
try:
    jobs = br.load_jobs([ok, a, b])
    # Stop once the first job has been dispatched.
    summary = br.run_batch(jobs, should_stop=lambda: len(calls) >= 1)
finally:
    pipeline_runner.run_pipeline = real_run
check(calls == ["case_ok"], f"7. cancellation stops further dispatch ({calls})")
check(len(summary["ok"]) == 1 and len(summary["skipped"]) == 2,
      f"7. the finished job keeps its result; the rest are skipped "
      f"({summary['ok']}, {len(summary['skipped'])} skipped)")
check(all("cancelled" in e for _lbl, e in summary["skipped"]),
      "7. ...and say they were cancelled, not that they failed")

# ── 8. exit code ──────────────────────────────────────────────────────────
check(br.exit_code({"failed": [], "skipped": []}) == 0,
      "8. a clean batch exits 0")
check(br.exit_code({"failed": [("x", "e")], "skipped": []}) == 1,
      "8. any failure exits 1 — a batch with 12 failures must not look green")
check(br.exit_code({"failed": [], "skipped": [("x", "e")]}) == 1,
      "8. a skipped (unrunnable) case also exits 1")

# ── the CLI wrapper exists and is executable ──────────────────────────────
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
for rel in ("run_batch.sh", "tools/PreProcessor/run_batch.py"):
    p = os.path.join(_REPO, rel)
    check(os.path.exists(p), f"0. {rel} exists")
check(os.access(os.path.join(_REPO, "run_batch.sh"), os.X_OK),
      "0. run_batch.sh is executable")

import shutil  # noqa: E402

shutil.rmtree(tmp, ignore_errors=True)

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    sys.exit(1)
print("\nRESULT: ALL PASS", flush=True)
sys.exit(0)
