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

Both rules are about COMPARING two spellings. :func:`stored_geom_path` is the
third question they leave open -- which spelling to write down in the first
place -- and it exists because the callers answered it with the very
``os.path.abspath`` the first rule condemns.
"""
from __future__ import annotations

import os

from app.services.paths import repo_root

__all__ = ["canonical_geom_path", "same_geom_file", "canonical_geom_keys",
           "dedupe_geom_paths", "stored_geom_path"]


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


def _keyed(paths, base: str | None = None):
    """``(canonical key, the spelling it came from)`` for every entry that names
    a file. Falsy entries are dropped here, once.

    The ONE place a list of spellings becomes identities. Every verb that walks
    the list -- dedupe below, and the model's membership and role-prune through
    :func:`canonical_geom_keys` -- reads it through here, because the same loop
    written per verb is how one canonicalisation rule drifts into three that can
    disagree. That is not hypothetical: the string-compare defect this module
    exists for was a rule stated once and applied in several hand-written copies.
    """
    for p in paths or ():
        key = canonical_geom_path(p, base)
        if key:
            yield key, p


def canonical_geom_keys(paths, base: str | None = None) -> set[str]:
    """The set of identities in ``paths`` -- the membership question, answered
    for a whole list at once."""
    return {key for key, _ in _keyed(paths, base)}


def dedupe_geom_paths(paths, base: str | None = None) -> list[str]:
    """``paths`` with duplicate identities removed, order and spelling kept.

    The FIRST spelling of each file survives, because that is the one the user
    (or the workspace they loaded) actually put there -- rewriting every entry
    to its canonical form would churn a saved config on load for no gain.
    """
    seen: set[str] = set()
    out: list[str] = []
    for key, p in _keyed(paths, base):
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def stored_geom_path(path: str, base: str | None = None) -> str:
    """The spelling to STORE for ``path``: repo-relative when the file is inside
    the repo, its canonical absolute path when it is not.

    The counterpart of :func:`canonical_geom_path`, which answers "which file is
    this?"; this one answers "how should the entry be written down?". Callers
    used to answer it with ``os.path.abspath``, which is the cwd-relative call
    this module's first rule condemns -- a rule contradicted by its own callers.
    Nothing was broken by it, because every comparison canonicalises, but a
    stored ``<cwd>/results/...`` is a path that stops naming the same file the
    moment the GUI is launched from somewhere else.

    Repo-relative rather than absolute, because that is what ``mesh_config_io``
    emits into the ``.dat`` it writes and what a saved workspace carries: one
    spelling for the same file in the model, in the config and in the script, so
    a case package stays portable. A geometry OUTSIDE the repo has no
    repo-relative spelling, and gets the canonical absolute one -- which is also
    what the config writer falls back to.
    """
    canon = canonical_geom_path(path, base)
    if not canon:
        return ""
    root = os.path.realpath(base or repo_root())
    if canon == root or canon.startswith(root + os.sep):
        return os.path.relpath(canon, root)
    return canon
