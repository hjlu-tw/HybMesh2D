"""The identity of a geometry path. Qt-free.

A geometry in the mesh config is identified by the FILE it names, not by the
string that names it. Before this module every dedup guard in the tree was a
``not in`` string compare over ``MeshConfig.geom_files``, so the repo-relative
and absolute spellings of one file were two entries: the Mesh Generator listed
the geometry twice and the mesher was handed it twice -- a doubled boundary.
USER-REPORTED 2026-08-20, reopening an exported case package.

Two rules, and the second is the one that was wrong:

* **The base is the repo, never the process cwd.** A relative entry used to be
  resolved with ``os.path.abspath``, which is cwd-relative, so the same entry
  named a different file depending on where the GUI was launched from
  (measured: ``<repo>/results/...`` from the repo root,
  ``/private/tmp/results/...`` from /tmp). Every relative path this app stores
  is repo-relative -- that is what ``mesh_config_io`` writes -- so
  ``repo_root()`` is the only correct base. It was already imported in that
  same function, used for relativising output only.

* **Canonical means realpath.** Symlinked scratch dirs and a case-insensitive
  volume otherwise reintroduce the same two-strings-one-file problem that
  ``case_workspace`` solves with ``(st_dev, st_ino)``. Identity by inode is the
  stronger test but needs the file to EXIST, and the whole point here is to
  reason about entries that may not (a reopened package carries no CAD), so
  this is a pure-string canonicalisation that never touches the filesystem for
  its answer.
"""
from __future__ import annotations

import os

from app.services.paths import repo_root

__all__ = ["canonical_geom_path", "same_geom_file", "dedupe_geom_paths"]


def canonical_geom_path(path: str, base: str | None = None) -> str:
    """One spelling per file: absolute, normalised, symlinks resolved.

    A relative ``path`` is taken as relative to ``base`` (the repo root by
    default) rather than to the process cwd. Returns "" for a falsy path so
    callers can filter without a separate emptiness test.
    """
    if not path:
        return ""
    p = os.path.expanduser(str(path))
    if not os.path.isabs(p):
        p = os.path.join(base or repo_root(), p)
    return os.path.realpath(os.path.normpath(p))


def same_geom_file(a: str, b: str, base: str | None = None) -> bool:
    """Do these two spellings name the same geometry file?"""
    return bool(a) and bool(b) and (
        canonical_geom_path(a, base) == canonical_geom_path(b, base))


def dedupe_geom_paths(paths, base: str | None = None) -> list[str]:
    """``paths`` with duplicate identities removed, order and spelling kept.

    The FIRST spelling of each file survives, because that is the one the user
    (or the workspace they loaded) actually put there -- rewriting every entry
    to its canonical form would churn a saved config on load for no gain.
    """
    seen: set[str] = set()
    out: list[str] = []
    for p in paths or ():
        key = canonical_geom_path(p, base)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out
