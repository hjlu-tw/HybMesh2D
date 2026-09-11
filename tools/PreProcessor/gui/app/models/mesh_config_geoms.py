"""The geometry LIST half of :class:`MeshConfig`: which files the mesh is built
from, what role each one plays, and the identity rules both questions obey.

Split out of ``mesh_config.py`` (over the GUI file-size budget) as a mixin rather
than as free functions, because these are the model's own verbs: ``add_geom_file``
is documented as the one way in, and a free function would be a second way that
callers could choose not to take.

The identity rule they all share lives one layer down, in Qt-free
``services/geom_path_identity``: a geometry is the FILE it names, not the string
that names it, and a relative entry is resolved against the REPO, never the
process cwd. What this module adds is that the whole list — membership, addition,
removal and every role lookup — asks that one question, so no caller can add by
identity and remove by string. It could, and did: the checkbox in the Mesh
Generator drew Unchecked for a geometry that was in the mesh, and unchecking it
removed nothing. Gated by ``tests/test_geom_files_identity.py`` check 7, which
fails the build on every raw way in over ``geom_files`` anywhere outside THIS
MIXIN: the eight list mutators, ``in`` / ``not in``, a wholesale
``cfg.geom_files = [...]`` rebind, a slice rebind, a ``del``, a literal
``setattr`` and a ``geom_files=`` keyword to the constructor or
``dataclasses.replace``. The rebind is the one that
mattered — the exact pre-fix shape, and invisible to the scan until #99.
:class:`MeshConfig` is NOT exempt: the allow-list is derived from where the verbs
are defined, so when they moved into this module the exemption moved with them and
the config class kept none.
"""
from __future__ import annotations

import os

from app.services.geom_path_identity import (canonical_geom_keys,
                                             canonical_geom_path,
                                             dedupe_geom_paths,
                                             keyed_geom_paths,
                                             same_geom_file)

__all__ = ["GeomListMixin"]


class GeomListMixin:
    """The geometry list and per-geometry roles, for :class:`MeshConfig`.

    Holds no fields of its own: ``geom_files`` and ``geom_roles`` stay declared on
    the dataclass, so the config-parity and panel-sync gates still read one class
    body for the model's fields.
    """

    # ── Per-geometry role helpers ─────────────────────────────────────────
    # Roles live in geom_roles (keyed by the path in geom_files). These helpers
    # are the single place that queries a role, and they tolerate a relative vs
    # absolute spelling mismatch so a seed role is not silently lost/misapplied.
    def role_of(self, path: str) -> dict | None:
        r = self.geom_roles.get(path)
        if r is None:
            # By IDENTITY, not by os.path.abspath: that is cwd-relative, so the
            # same stored key answered differently depending on where the GUI
            # was launched from. See services/geom_path_identity.
            want = canonical_geom_path(path)
            if want:
                r = self.geom_roles.get(want)
                if r is None:
                    for k, v in self.geom_roles.items():
                        if canonical_geom_path(k) == want:
                            return v
        return r

    def add_geom_file(self, path: str) -> bool:
        """Add `path` to geom_files unless that FILE is already there.

        The one way in. Every caller used to hand-roll `if p not in
        cfg.geom_files: cfg.geom_files.append(p)`, which compares STRINGS, so a
        relative and an absolute spelling of one file both went in -- the
        geometry was listed twice and meshed twice. Returns True if it was added.
        """
        if not path:
            return False
        # Through has_geom_file, not a second canonical-key loop: "is that FILE
        # already here?" is exactly the membership verb below, and a rule stated
        # twice is a rule that can come to disagree with itself.
        if self.has_geom_file(path):
            return False
        self.geom_files.append(path)
        return True

    def set_geom_files(self, paths: list[str] | None) -> None:
        """Replace the whole list, keeping one entry per FILE.

        The wholesale-replace half of the one way in, and the reason it exists is
        that a bare ``cfg.geom_files = [...]`` is BOTH the pre-fix shape (five
        callers outside here rebuilt the list) and the one construct the identity
        gate could not see. Dedupes by identity, so a rebuilt list cannot put back
        the two-spellings-one-file state ``add_geom_file`` removed; the spelling
        the caller gave is kept and a falsy entry is dropped, both per
        ``dedupe_geom_paths`` — which is already what the mesher-config WRITER
        does to this list, so the two cannot disagree about what is in the mesh.
        ``None`` is an empty replacement, since a restored workspace may hold a
        JSON null where the list should be.
        """
        self.geom_files = dedupe_geom_paths(paths)

    def has_geom_file(self, path: str) -> bool:
        """Is that FILE already in geom_files? The read half of the one way in.

        Membership had to move with the mutation: a caller that adds by identity
        and then asks ``path in cfg.geom_files`` gets False for the file it just
        confirmed was there under another spelling. Measured on the reported case
        (a workspace holding the repo-relative spelling, a panel holding the
        absolute one): the Mesh Generator drew the layer's checkbox UNCHECKED for
        a geometry that was in the mesh, and unchecking it removed nothing.
        """
        want = canonical_geom_path(path)
        return bool(want) and want in canonical_geom_keys(self.geom_files)

    def remove_geom_file(self, path: str) -> bool:
        """Drop whichever entry names the same FILE as `path`.

        Through ``same_geom_file``, not a second canonical-key loop: this verb
        asks about ONE file, and the module's comparison verb is that question.
        NOT through ``keyed_geom_paths``, which the list-wide verbs read --
        stated here because the omission is a decision: that helper drops a
        falsy entry, which is right for a dedupe (such an entry names no file)
        and would make a removal silently delete the empty entries beside the
        one it was asked about. Its docstring records the same split.

        Returns True if an entry went. A falsy `path` names no file, so it
        removes nothing and says so, rather than matching the falsy entries.
        """
        if not path:
            return False
        keep = [g for g in self.geom_files if not same_geom_file(g, path)]
        removed = len(keep) != len(self.geom_files)
        self.geom_files = keep
        return removed

    @staticmethod
    def missing_geometry_message(paths: list[str]) -> str:
        """What to tell the user about geometry files that are not on disk.

        One wording for both hosts (GUI pre-flight and the headless runner), so
        the same condition cannot be reported two different ways.
        """
        names = "\n".join(f"  • {p}" for p in paths)
        return (
            "Geometry file(s) not found:\n" + names + "\n"
            "Remove them from Geometry Files, or re-export the geometry they "
            "name. An exported case package carries no CAD source, so a "
            "reopened case leaves these entries pointing at nothing.")

    def geom_files_not_on_disk(self) -> list[str]:
        """geom_files entries naming a file that is not on disk.

        NOT ``missing_geom_files``, the field one word away on this same class:
        that one holds GEOM_FILE tokens a ``.dat`` read could not resolve at all.
        Two facts, two names.

        A reopened exported case package is the case that matters: it carries no
        CAD by design, so the entry its workspace restored is dead. It used to be
        WARNED about in the diagnostic scan and then written into the mesher
        config regardless, and the mesher exited 3 on it.

        Through ``keyed_geom_paths``: "drop the entries that name no file, then
        canonicalise the rest" is that helper's whole job, and the third
        hand-written copy of it here is what #104 removed from the two verbs
        beside it.
        """
        return [p for key, p in keyed_geom_paths(self.geom_files)
                if not os.path.exists(key)]

    def _role_name(self, path: str) -> str | None:
        r = self.role_of(path)
        return r.get("role") if r else None

    @staticmethod
    def _parse_bl_token(tok: str):
        """Parse a 'KEY=VALUE' BL-override token; returns (KEY, float) or None."""
        if "=" not in tok:
            return None
        k, _, v = tok.partition("=")
        if not k:
            return None
        try:
            return (k, float(v))
        except ValueError:
            return None

    def bl_params_of(self, path: str) -> dict:
        """Per-geometry BL parameter overrides for `path` ({} if none)."""
        r = self.role_of(path)
        return dict(r.get("bl_params") or {}) if r else {}

    def bc_of(self, path: str) -> str:
        """Per-geometry wall BC override for `path` ("" if none)."""
        r = self.role_of(path)
        return (r.get("bc") or "") if r else ""

    def is_seed(self, path: str) -> bool:
        return self._role_name(path) == "seed"

    def is_nobl(self, path: str) -> bool:
        """No-BL obstacle: conforms at far-field size, grows no boundary layer."""
        return self._role_name(path) == "nobl"

    def is_farfield(self, path: str) -> bool:
        """Custom outer-domain outline with NO boundary layer (external flow)."""
        return self._role_name(path) == "farfield"

    def is_wall(self, path: str) -> bool:
        """Domain wall whose boundary layer grows inward (internal flow)."""
        return self._role_name(path) == "wall"

    def is_domain(self, path: str) -> bool:
        """This geometry is the outer computational-domain outline (far-field or wall)."""
        return self._role_name(path) in ("farfield", "wall")

    @property
    def domain_file(self) -> str | None:
        """The single custom outer-domain outline, if one is defined."""
        for g in self.geom_files:
            if self.is_domain(g):
                return g
        return None

    @property
    def boundary_files(self) -> list:
        """geom_files used for output naming: obstacle/no-BL bodies, excluding
        refinement seeds and the outer-domain outline."""
        return [g for g in self.geom_files if not self.is_seed(g) and not self.is_domain(g)]

    @property
    def seed_files(self) -> list:
        """geom_files that are refinement seeds."""
        return [g for g in self.geom_files if self.is_seed(g)]

    def prune_roles(self):
        """Drop geom_roles entries whose path is no longer in geom_files, so a
        stale seed role can't silently re-attach when a path is added again."""
        present = canonical_geom_keys(self.geom_files)
        self.geom_roles = {k: v for k, v in self.geom_roles.items()
                           if canonical_geom_path(k) in present}
