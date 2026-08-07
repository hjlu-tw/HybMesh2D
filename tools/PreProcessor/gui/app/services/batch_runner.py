"""Run several pipeline cases in sequence (Qt-free).

Meshing a parameter sweep or a family of geometries meant launching the pipeline by
hand once per case and watching each one. This runs a queue instead.

Three properties matter more than anything else here, because a batch is what you
leave running:

* **One bad case must not kill the queue.** A failure is recorded and the next job
  starts. Aborting the night's work because job 3 of 40 had an inverted domain is the
  behaviour that makes people stop using batch mode.
* **Jobs must not overwrite each other.** Output paths are derived from the case
  name, so two jobs that resolve to the same name would silently clobber one
  another's mesh. Collisions are detected up front and reported by SOURCE FILE —
  before anything runs, while the user can still fix the scripts.
* **The summary must be readable at a glance.** After 40 jobs nobody reads 40
  interleaved logs; the report says which succeeded, which failed and why.

Qt-free, so the CLI and the GUI's batch worker share exactly this logic.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from app.models.pipeline_config import PipelineConfig
from app.services import pipeline_runner


def _noop(_msg: str) -> None:
    pass


@dataclass
class BatchJob:
    """One queued case: where it came from, and what happened to it."""

    source: str                      # script/workspace path, or "" for in-memory
    config: PipelineConfig | None = None
    name: str = ""
    status: str = "pending"          # pending | running | ok | failed | skipped
    error: str = ""
    artifacts: dict = field(default_factory=dict)
    seconds: float = 0.0

    @property
    def label(self) -> str:
        return self.name or (os.path.basename(self.source) or "case")


def load_jobs(paths, log=_noop) -> list:
    """Build jobs from pipeline-script / workspace paths.

    A path that cannot be parsed becomes a ``skipped`` job rather than raising: the
    other 39 cases in the queue are still worth running, and the summary will say
    which one was unreadable.
    """
    jobs = []
    for path in paths:
        job = BatchJob(source=path)
        if not os.path.exists(path):
            job.status, job.error = "skipped", "file not found"
            log(f"[Batch] [WARNING] {path}: not found — skipping")
        else:
            try:
                job.config = PipelineConfig.load_from_file(path)
                job.name = job.config.name or os.path.splitext(
                    os.path.basename(path))[0]
            except Exception as e:
                job.status, job.error = "skipped", f"unreadable: {e}"
                log(f"[Batch] [WARNING] {path}: {e} — skipping")
        jobs.append(job)
    return jobs


def read_manifest(path: str) -> list:
    """Paths from a manifest file, one per line; ``#`` comments and blanks ignored.

    Relative entries resolve against the manifest's own directory, so a batch list
    can sit next to the scripts it names and still work from any cwd.
    """
    base = os.path.dirname(os.path.abspath(path))
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(line if os.path.isabs(line)
                       else os.path.normpath(os.path.join(base, line)))
    return out


def find_collisions(jobs) -> dict:
    """``{case name: [source files]}`` for names claimed by more than one job.

    Output paths derive from the case name, so a shared name means jobs silently
    overwriting each other's mesh.

    The values are the SOURCE FILES, not the case names: when two scripts share a
    name, repeating that name back ("used by batch_case_b, batch_case_b") tells the
    user nothing — the actionable fact is which files to edit.
    """
    seen: dict = {}
    for job in jobs:
        if job.config is None:
            continue
        key = (job.config.name or "").strip() or job.label
        seen.setdefault(key, []).append(
            os.path.basename(job.source) or job.label)
    return {k: v for k, v in seen.items() if len(v) > 1}


def run_batch(jobs, log=_noop, progress=None, run_solver: bool = True,
              run_ib: bool = True, should_stop=None, on_process=None) -> dict:
    """Run every runnable job in order. Returns a summary dict.

    ``progress(done, total, label)`` is called before each job so a caller can drive
    a progress bar. ``should_stop()`` is polled between jobs, so the queue stops
    cleanly at a case boundary rather than leaving a half-written output directory.

    ``on_process(proc)`` is forwarded to the pipeline runner and fires for each stage
    subprocess, which is what lets a GUI Cancel end the case that is *already running*.
    Both are needed and they are not alternatives: killing the child stops the work,
    and the stop flag stops the queue from starting the next case.
    """
    runnable = [j for j in jobs if j.config is not None and j.status != "skipped"]
    total = len(runnable)

    collisions = find_collisions(runnable)
    if collisions:
        for name, labels in collisions.items():
            log(f"[Batch] [WARNING] case name {name!r} is used by "
                f"{len(labels)} jobs ({', '.join(labels)}); their outputs would "
                "overwrite each other — give each script its own \"name\".")

    log(f"=== Batch: {total} case(s) ===")
    started = time.time()
    for i, job in enumerate(runnable):
        if should_stop is not None and should_stop():
            job.status, job.error = "skipped", "cancelled before start"
            for rest in runnable[i + 1:]:
                rest.status, rest.error = "skipped", "cancelled before start"
            log("[Batch] cancelled — remaining cases skipped.")
            break
        if progress is not None:
            progress(i, total, job.label)
        log(f"--- [{i + 1}/{total}] {job.label} ---")
        job.status = "running"
        t0 = time.time()
        try:
            job.artifacts = pipeline_runner.run_pipeline(
                job.config, log=log, run_solver=run_solver, run_ib=run_ib,
                on_process=on_process)
            job.status = "ok"
        except pipeline_runner.PipelineError as e:
            # Expected failure mode (a stage returned non-zero, a file was
            # missing): record it and keep going.
            job.status, job.error = "failed", str(e)
            log(f"[Batch] [ERROR] {job.label}: {e}")
        except Exception as e:
            # Unexpected: still must not take the queue down, but say plainly that
            # it was not a normal stage failure.
            job.status, job.error = "failed", f"unexpected error: {e}"
            log(f"[Batch] [ERROR] {job.label}: unexpected error: {e}")
        finally:
            job.seconds = time.time() - t0
    if progress is not None:
        progress(total, total, "")

    summary = {
        "total": len(jobs),
        "ok": [j.label for j in jobs if j.status == "ok"],
        "failed": [(j.label, j.error) for j in jobs if j.status == "failed"],
        "skipped": [(j.label, j.error) for j in jobs if j.status == "skipped"],
        "collisions": collisions,
        "seconds": time.time() - started,
    }
    log(format_summary(summary))
    return summary


def format_summary(summary: dict) -> str:
    """The end-of-batch report. After 40 jobs nobody reads 40 interleaved logs."""
    lines = ["=== Batch summary ===",
             f"  ran {len(summary['ok'])} ok, {len(summary['failed'])} failed, "
             f"{len(summary['skipped'])} skipped "
             f"of {summary['total']} queued in {summary['seconds']:.1f}s"]
    for label in summary["ok"]:
        lines.append(f"  [ok]      {label}")
    for label, err in summary["failed"]:
        lines.append(f"  [FAILED]  {label}: {err}")
    for label, err in summary["skipped"]:
        lines.append(f"  [skipped] {label}: {err}")
    if summary["collisions"]:
        lines.append("  [WARNING] case names shared by several jobs: "
                     + ", ".join(summary["collisions"]))
    return "\n".join(lines)


def exit_code(summary: dict) -> int:
    """0 only when every queued job actually succeeded.

    A batch that "finished" with 12 failures must not report success to a scheduler.
    """
    return 0 if not summary["failed"] and not summary["skipped"] else 1
