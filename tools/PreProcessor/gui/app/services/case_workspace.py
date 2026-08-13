"""The GUI workspace that travels inside a portable case package.

``services/case_export`` packages the files the SOLVER needs; this adds the one
file the ENGINEER needs — a ``.hws`` sitting in the export folder whose paths
point at *that folder* instead of at the machine it was exported from. Without
it the package is runnable (``./run_case.sh``) but not re-openable: the GUI has
no importer for an exported case, so "load the case I exported" had no answer at
all.

Three rules make it worth shipping:

* **Re-point by file identity, never by string match.** A path is rewritten only
  when it names a file the package actually carries, matched on
  ``(st_dev, st_ino)`` so a differently-spelled path for the same file (``results/``
  vs ``Results/`` on a case-insensitive volume, a symlinked scratch directory) is
  still recognised, and two genuinely different files never collide. A path the
  package does NOT carry is left exactly as it was and REPORTED — silently
  re-pointing it would aim the solver at a file that is not there, which is the
  failure this whole module exists to prevent.
* **Only the paths, and only into the package.** The geometry itself already
  travels inside the ``.hws`` (a session stores ``original_points`` /
  ``resampled_points`` verbatim), so a re-opened workspace draws its CAD even
  though the source ``.dat`` is not in the package. What it cannot do is
  *re-resample* from a source that is not there — hence the report.
* **The stamp survives the folder being moved.** The point of an export is that
  it gets copied somewhere else, which would strand absolute paths a second time.
  So the exported workspace records the root it was written for and
  :func:`rebase_case_workspace` swaps that prefix for wherever the ``.hws`` is
  actually being opened from. Absolute paths rather than relative ones because
  nothing in the loader resolves a workspace path against the workspace's own
  location — see ``session_io_ctrl._read_workspace_file``, which uses every path
  as written.

Qt-free, like the rest of the export services.
"""
from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field

# Recorded in the exported .hws so a moved package can re-point itself. Absent
# from every normally-saved workspace, which is what keeps rebasing a no-op there.
EXPORT_ROOT_KEY = "exported_case_root"

# Point arrays: thousands of floats per session and never a path. Skipped by name
# so the walk stays proportional to the CONFIG, not to the geometry.
_BULK_KEYS = frozenset({"original_points", "resampled_points"})


@dataclass
class WorkspaceRewrite:
    """What :func:`build_case_workspace` did, so the caller can report it."""
    repointed: list = field(default_factory=list)   # (key, old, new)
    outside: list = field(default_factory=list)     # (key, path)

    @property
    def n_repointed(self) -> int:
        return len(self.repointed)


def _walk(node, key: str, fn) -> None:
    """Apply ``fn(key, value)`` to every string in ``node``, replacing it when
    ``fn`` returns one. Depth-first over dicts and lists; bulk point arrays are
    skipped by key."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k in _BULK_KEYS:
                continue
            sub = f"{key}.{k}" if key else str(k)
            if isinstance(v, str):
                new = fn(sub, v)
                if new is not None:
                    node[k] = new
            else:
                _walk(v, sub, fn)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            sub = f"{key}[{i}]"
            if isinstance(v, str):
                new = fn(sub, v)
                if new is not None:
                    node[i] = new
            else:
                _walk(v, sub, fn)


def _ident(path: str):
    """``(st_dev, st_ino)`` for ``path``, or None when it cannot be stat'd.

    The identity key for the rewrite map. String comparison would miss the same
    file reached by a different spelling and — on a case-insensitive volume —
    could equally well fuse two paths that are not the same file at all."""
    try:
        st = os.stat(path)
    except (OSError, ValueError):
        return None
    return (st.st_dev, st.st_ino)


def _looks_like_path(value: str) -> bool:
    """A string worth reporting as a FILE left pointing off the package.

    Deliberately narrow on both counts. It must have a separator and exist, so a
    BC name, a variable name or a units label is never reported as a stranded
    file. And it must be a file, not a directory: ``SolverConfig.work_dir`` is a
    record of where the case last ran, rebuilt from the case name by
    ``prepare_case_dir`` on the next run — reporting it as "left behind" would
    describe a stale breadcrumb as missing data."""
    return bool(value) and (os.sep in value or "/" in value) \
        and os.path.isfile(value)


def build_case_workspace(workspace: dict, plan, dest_dir: str
                         ) -> tuple[dict, WorkspaceRewrite]:
    """Return a copy of ``workspace`` whose paths point into ``dest_dir``.

    ``plan`` is the :class:`~app.services.case_export.ExportPlan` that was
    actually written — it must be the same one, or a file the user declined
    (the restart dump) would be re-pointed at a name the package does not hold.
    """
    ws = copy.deepcopy(workspace)
    dest_dir = os.path.abspath(dest_dir)

    by_ident: dict = {}
    by_abs: dict = {}
    for item in plan.items:
        target = os.path.join(dest_dir, *item.rel.split("/"))
        ident = _ident(item.src)
        if ident is not None:
            by_ident[ident] = target
        by_abs[os.path.normcase(os.path.abspath(item.src))] = target

    report = WorkspaceRewrite()

    def repoint(key: str, value: str):
        if not value:
            return None
        target = by_ident.get(_ident(value))
        if target is None:
            target = by_abs.get(os.path.normcase(os.path.abspath(value)))
        if target is None:
            if _looks_like_path(value):
                report.outside.append((key, value))
            return None
        if target == value:
            return None
        report.repointed.append((key, value, target))
        return target

    _walk(ws, "", repoint)
    ws[EXPORT_ROOT_KEY] = dest_dir
    return ws, report


def rebase_case_workspace(workspace: dict, hws_path: str) -> int:
    """Re-point an exported workspace at the folder it is being opened from.

    A no-op (returns 0) for any workspace that was not written by the case
    export, and for one still sitting where it was written. Returns the number
    of paths swapped otherwise.
    """
    root = (workspace.get(EXPORT_ROOT_KEY) or "").strip()
    if not root:
        return 0
    here = os.path.dirname(os.path.abspath(hws_path))
    old = os.path.normpath(root)
    if os.path.normcase(old) == os.path.normcase(here):
        return 0

    prefix = old.rstrip("/\\") + os.sep
    alt = old.rstrip("/\\") + "/"        # a package written on the other OS
    moved = 0

    def swap(_key: str, value: str):
        nonlocal moved
        for p in (prefix, alt):
            if value.startswith(p):
                moved += 1
                return os.path.join(here, *value[len(p):].replace("\\", "/").split("/"))
        return None

    _walk(workspace, "", swap)
    workspace[EXPORT_ROOT_KEY] = here
    return moved
