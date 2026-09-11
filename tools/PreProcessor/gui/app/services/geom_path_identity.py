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
``os.path.abspath`` the first rule condemns. :func:`readable_geom_path` is the
fourth -- which path to OPEN -- and it exists for the same reason: five readers
across three layers each answered it for themselves, and the two full-tree
sweeps that paid for the other sides each had a review find sites they had
missed.
"""
from __future__ import annotations

import os

from app.services.paths import repo_root

__all__ = ["canonical_geom_path", "same_geom_file", "keyed_geom_paths",
           "canonical_geom_keys", "dedupe_geom_paths", "stored_geom_path",
           "readable_geom_path"]


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


def keyed_geom_paths(paths, base: str | None = None):
    """``(canonical key, the spelling it came from)`` for every entry that names
    a file. Falsy entries are dropped here, once.

    The ONE place a list of spellings becomes identities, and its readers are
    named here rather than left to be grepped for, because the same loop written
    per verb is how one canonicalisation rule drifts into three that can
    disagree. That is not hypothetical: the string-compare defect this module
    exists for was a rule stated once and applied in several hand-written copies.

    THREE readers, and the list stays three long however many verbs are added
    above it: :func:`dedupe_geom_paths` and :func:`canonical_geom_keys` below,
    and the model's ``geom_files_not_on_disk``, which asks the filesystem about
    each key. Everything else reaches this loop through those two -- the model's
    ``has_geom_file`` (hence ``add_geom_file``) and ``prune_roles`` through the
    keys; its ``set_geom_files`` (hence the workspace restore) and
    ``mesh_config_io``'s GEOM_FILE writer through the dedupe.

    THREE verbs that ask an IDENTITY question do NOT read it, and all three
    omissions are decisions rather than oversights. ``remove_geom_file`` asks
    about ONE file, so it compares through :func:`same_geom_file`: dropping a
    falsy entry is right for a dedupe, since such an entry names no file, and
    would make a removal silently delete the empty entries beside the one it was
    asked about. :func:`readable_geom_path` asks about ONE entry for the same
    reason, and reaches :func:`canonical_geom_path` directly: a caller holding a
    list still calls it per entry, because each of its callers needs the stored
    spelling beside the path.
    ``role_of`` walks ``geom_roles`` -- a different container, whose keys are
    spellings of the same files -- against the one key it has already derived.
    (The model's ``domain_file`` / ``boundary_files`` / ``seed_files`` walk the
    list too, but ask no identity question: they filter it by ROLE and hand back
    the stored spellings verbatim.)
    """
    for p in paths or ():
        key = canonical_geom_path(p, base)
        if key:
            yield key, p


def canonical_geom_keys(paths, base: str | None = None) -> set[str]:
    """The set of identities in ``paths`` -- the membership question, answered
    for a whole list at once."""
    return {key for key, _ in keyed_geom_paths(paths, base)}


def dedupe_geom_paths(paths, base: str | None = None) -> list[str]:
    """``paths`` with duplicate identities removed, order and spelling kept.

    The FIRST spelling of each file survives, because that is the one the user
    (or the workspace they loaded) actually put there -- rewriting every entry
    to its canonical form would churn a saved config on load for no gain.
    """
    seen: set[str] = set()
    out: list[str] = []
    for key, p in keyed_geom_paths(paths, base):
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


def readable_geom_path(path: str, base: str | None = None) -> str:
    """The path to OPEN for ``path``: its canonical spelling when a file is
    there, "" when there is nothing to open.

    "Canonicalise the entry, then find out whether there is anything to open"
    is ONE question, and this is where it is asked. It used to be answered at
    five call sites across three layers -- the mesh bbox scan, the Run-All
    readiness check, the preview loader thread, the BC overlay and the selection
    highlight -- which is the shape :func:`meta_path_for` was extracted from on
    the sidecar side, for the same reason: converting readers one by one is the
    shotgun-surgery version of one rule, and the symptom of getting it wrong is
    SILENT -- a repo-relative entry resolved against the process cwd, and a
    preview that simply does not draw.

    FOUR of the five spelled it ``os.path.exists`` on the canonical path; the
    BC overlay asked by attempting the open and treating the failure as a skip,
    which is the same question with no separate call to name. Existence here is
    therefore ``os.path.exists`` -- not ``isfile``, not ``os.access``. A path
    that exists and still cannot be read is the OPEN's failure, and every caller
    already has a handler that names the file; answering it here would move a
    diagnostic out of the layer that has the filename and the exception.

    The verb stays at the PATH layer. It does not load, and it does not absorb
    the preview loader's NaN / ``(N,2)`` validation, which is a separate concern
    with a home of its own (``geometry_service.load_points_dat``).

    A falsy entry canonicalises to "" and so reads back as "" -- the same answer
    the shared derivation gives, so a caller filtering on the empty string is
    filtering both cases at once.
    """
    canon = canonical_geom_path(path, base)
    return canon if canon and os.path.exists(canon) else ""
