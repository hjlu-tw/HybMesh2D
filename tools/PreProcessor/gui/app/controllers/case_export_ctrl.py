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

    # ------------------------------------------------------------------ #
    def export_portable_case(self):
        """Ask for a case + destination, then write a self-contained copy."""
        win = self.main_window
        log = win.log_panel.log

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

        also_tar = confirm(
            win, "Export Case",
            "Also write a .tar.gz archive next to the folder?\n\n"
            "The folder is always written; the archive is the convenient thing "
            "to scp to the other machine.",
            headless_default=False)

        try:
            summary = case_export.export_case(
                case_dir, target, dll_src_dirs=(dll_src,),
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
        detail = "\n".join(
            [f"{summary['n_files']} file(s), "
             f"{case_export.human_size(summary['bytes'])}",
             f"Folder: {summary['dest']}"]
            + ([f"Archive: {summary['tarball']}"] if summary["tarball"] else [])
            + ([""] + [f"! {w}" for w in plan.warnings] if plan.warnings else []))
        report_info(
            win, "Export Case",
            f"Exported '{name}'. Run it on the other machine with "
            "./run_case.sh (see MANIFEST.txt).",
            detail=detail)
