"""GUI front end for the portable-case export (``services/case_export``).

The service decides *what* travels; this asks the three questions only a person
can answer — which case, where to put it, and whether to also produce a
``.tar.gz`` to scp across — then reports what was written.
"""
from __future__ import annotations
import os

from PyQt6.QtWidgets import QFileDialog

from app.services import case_export
from app.services.solver_case import sanitize_case_name
from app.utils import repo_root, report_error, report_info, confirm
from app.services.logging_setup import get_logger

_log = get_logger(__name__)


class CaseExportControllerMixin:
    """Package the current solver case so another machine can reproduce it."""

    def _default_case_dir(self) -> str:
        """The case the Solver stage is pointed at, if it exists on disk.

        ``work_dir`` is set by ``solver_case.prepare_case_dir`` at run time and
        already reflects any auto-versioned ``<case>_002`` name, so it is a truer
        answer than rebuilding the path from the case name.
        """
        cfg = getattr(self, "global_solver_config", None)
        work = getattr(cfg, "work_dir", "") if cfg else ""
        if work and os.path.isdir(work):
            return os.path.dirname(os.path.abspath(work))
        name = sanitize_case_name(getattr(cfg, "case_name", "") or "")
        guess = os.path.join(repo_root(), "results", "solver", name)
        return guess if name and os.path.isdir(guess) else ""

    def _build_case_workspace_text(self, plan, dest_dir: str):
        """The .hws to drop into the package, as ``(json_text, report)``.

        Returns None — with the reason logged and shown — when the workspace
        cannot be serialised (non-finite coordinates being the one real case).
        Failing the WORKSPACE must not fail the export: the solver package is
        the part someone is waiting on.
        """
        import json
        from app.services import case_workspace
        try:
            ws, report = case_workspace.build_case_workspace(
                self.workspace_dict(), plan, dest_dir)
            return json.dumps(ws, indent=2, allow_nan=False), report
        except (ValueError, TypeError) as e:
            _log.warning("could not build the exported workspace", exc_info=True)
            self.log(
                f"[export] [WARNING] no .hws written: {e}")
            return None

    @staticmethod
    def _log_workspace_report(report, log) -> None:
        """Name what the exported workspace still points at OFF the package.

        The export's allow-list only carries solver inputs, so a CAD .dat, a
        mesh .vtk or a solver binary keeps its original path — correct on this
        machine, absent on any other. Naming them here is the same promise the
        manifest makes about skipped files: nothing goes missing silently.
        """
        if report is None:
            return
        log(f"[export]   workspace: {report.n_repointed} path(s) now point "
            "into the exported folder")
        seen = []
        for _key, path in report.outside:
            if path not in seen:
                seen.append(path)
        for path in seen:
            log(f"[export]   workspace: (outside the package) {path}")
        if seen:
            log("[export]   workspace: those are not solver-case files, so they "
                "do not travel — the geometry itself is stored inside the .hws, "
                "but re-resampling / re-meshing on another machine needs them.")

    # ------------------------------------------------------------------ #
    def export_portable_case(self):
        """Ask for a case + destination, then write a self-contained copy."""
        win = self.main_window
        log = self.log

        case_dir = self._default_case_dir()
        if not case_dir:
            start = os.path.join(repo_root(), "results", "solver")
            case_dir = QFileDialog.getExistingDirectory(
                win, "Choose the solver case to export",
                start if os.path.isdir(start) else repo_root())
            if not case_dir:
                return

        # Plan first: nothing is written, but it can already report that the
        # chosen directory is not a case at all.
        dll_src = os.path.join(repo_root(), "results", "solver", "dll_src")
        try:
            plan = case_export.plan_export(case_dir, dll_src_dirs=(dll_src,))
        except case_export.CaseExportError as e:
            report_error(win, "Export Case", str(e))
            return

        name = os.path.basename(os.path.abspath(case_dir))
        target, _ = QFileDialog.getSaveFileName(
            win, "Export portable case to…",
            os.path.join(os.path.dirname(os.path.abspath(case_dir)),
                         f"{name}_portable"),
            "Folder (*)")
        if not target:
            return
        target = target[:-7] if target.endswith(".tar.gz") else target

        # The zone dump is by far the largest file in a case and it is an OUTPUT
        # that only a RESTART run reads back, so the plan leaves it out unless
        # input.in names it ("auto"). When it is being carried, say so with its
        # size rather than letting a 100 MB package turn up unexplained.
        include_restart = "auto"
        dump = next((i for i in plan.items if i.reason.startswith("restart")), None)
        if dump is not None:
            include_restart = confirm(
                win, "Export Case",
                f"Include the restart snapshot {dump.rel} "
                f"({case_export.human_size(os.path.getsize(dump.src))})?\n\n"
                "work/input.in restarts from it, so the target needs it to "
                "continue this run. Answer No to export the inputs only — the "
                "case then starts from scratch there.",
                headless_default=True)

        # Asked before the archive question, because it decides what is IN the
        # folder and the archive is taken of the finished folder.
        want_hws = confirm(
            win, "Export Case",
            f"Also write a GUI workspace ({os.path.basename(target)}.hws) into "
            "the folder?\n\n"
            "run_case.sh reruns the SOLVER; the workspace is what reopens the "
            "case in this GUI. Its solver paths point into the exported folder, "
            "and they follow the folder if you move it.",
            headless_default=True)

        also_tar = confirm(
            win, "Export Case",
            "Also write a .tar.gz archive next to the folder?\n\n"
            "The folder is always written; the archive is the convenient thing "
            "to scp to the other machine.",
            headless_default=False)

        # Re-plan with the answers actually given: the plan above was built to
        # DETECT the restart dump, before the user said whether to carry it. The
        # workspace is derived from the plan, so it has to be derived from the
        # plan that is written — not from one that merely resembles it.
        try:
            plan = case_export.plan_export(case_dir, dll_src_dirs=(dll_src,),
                                           include_restart=include_restart)
        except case_export.CaseExportError as e:
            report_error(win, "Export Case", str(e))
            return

        extra_files = []
        ws_report = None
        if want_hws:
            hws_rel = os.path.basename(os.path.abspath(target)) + ".hws"
            built = self._build_case_workspace_text(plan, target)
            if built is not None:
                text, ws_report = built
                extra_files.append(
                    (hws_rel, text,
                     "GUI workspace — File > Load Workspace"))

        try:
            summary = case_export.export_case(
                case_dir, target, dll_src_dirs=(dll_src,),
                include_restart=include_restart, plan=plan,
                extra_files=extra_files,
                make_tarball=bool(also_tar), log=log)
        except case_export.CaseExportError as e:
            report_error(win, "Export Case", "Could not export the case.",
                         detail=str(e))
            return
        except OSError as e:
            _log.warning("portable case export failed", exc_info=True)
            report_error(win, "Export Case", "Could not export the case.",
                         detail=str(e))
            return

        plan = summary["plan"]
        log(f"[export] portable case '{name}' -> {summary['dest']}")
        for item in sorted(plan.items, key=lambda i: i.rel):
            log(f"[export]   {item.rel}")
        # A file the case holds but this run does not use (a phi field / DLL left
        # by an earlier immersed-solid run in the same case dir) is named here as
        # well as in the manifest — that it is absent from the package should be
        # visible where the user is already looking, not only on the far machine.
        for rel, _size, why in plan.skipped_unused:
            log(f"[export]   (not used by this run) {rel} — {why}")
        for rel, _size, note in plan.extras:
            log(f"[export]   {rel} — {note}")
        self._log_workspace_report(ws_report, log)
        hws = next((r for r, _s, _n in plan.extras if r.endswith(".hws")), "")
        detail = "\n".join(
            [f"{summary['n_files']} file(s), "
             f"{case_export.human_size(summary['bytes'])}",
             f"Folder: {summary['dest']}"]
            + ([f"Archive: {summary['tarball']}"] if summary["tarball"] else [])
            + ([f"Workspace: {hws} "
                f"({ws_report.n_repointed if ws_report else 0} path(s) "
                f"re-pointed into the folder)"] if hws else [])
            + ([""] + [f"! {w}" for w in plan.warnings] if plan.warnings else []))
        report_info(
            win, "Export Case",
            f"Exported '{name}'. Run it on the other machine with "
            "./run_case.sh (see MANIFEST.txt).",
            detail=detail)
