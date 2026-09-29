"""What a geometry REMEMBERS about the geometry it was derived from. Qt-free.

#152. An offset curve is an ordinary discrete geometry to everything downstream —
that is the whole point of it — which leaves one thing an ordinary geometry cannot
say: where it came from. Without that record the offset is a point array somebody
will reopen in three months next to the body it mirrors, with no way to tell which
is which or how far apart they were meant to be, and no way to bring it back into
step after editing the source.

THE RECORD IS DATA, AND REGENERATION IS AN EXPLICIT ACTION. It is deliberately NOT
a live link. A recomputation on every source edit would put an implicit write into
every geometry edit path, and it would have to be reconciled with global undo and
with the outline re-fit before it could be trusted; a snapshot with no record at
all would leave a ring silently wrong after a source edit, which is the
stage-to-stage staleness class this repo gates in four other places. So the record
is carried, the user asks for the regeneration, and a regeneration whose source is
gone is a named refusal rather than a skip or a nearest match.

THE SOURCE IS NAMED THE WAY THE USER NAMES IT. ``source_name`` is the source
geometry's display name — what the tab and the model tree show — because that is
the only identity a drawn, never-saved geometry has, and it is what a refusal has
to print to be actionable. ``source_file`` is its path when it has one, kept as the
second way to find it after a rename. Neither is a live object reference: the
record outlives the process it was made in, which is what "carried through save and
reopen" means.
"""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["DerivedOffset"]


@dataclass
class DerivedOffset:
    """One geometry's record of the offset that produced it."""

    #: Display name of the source geometry, as the user sees it.
    source_name: str = ""
    #: The source's file path, when it has one ("" for a drawn geometry).
    source_file: str = ""
    #: SIGNED distance, in this geometry's own length unit. Positive is outward
    #: for a closed source outline and the right of travel for an open one —
    #: `app/services/geometry_offset.py` owns that meaning, not this record.
    distance: float = 0.0

    def to_dict(self) -> dict:
        d: dict = {"kind": "offset",
                   "source_name": self.source_name,
                   "distance": float(self.distance)}
        if self.source_file:
            d["source_file"] = self.source_file
        return d

    @classmethod
    def from_dict(cls, d) -> "DerivedOffset | None":
        """Read a record back, or ``None`` when there is not one.

        A dict of another ``kind`` is not this record and is not guessed at: a
        later derivation type must be read by its own reader, never mistaken for
        an offset because the two happen to share a field name.
        """
        if not isinstance(d, dict) or d.get("kind", "offset") != "offset":
            return None
        try:
            dist = float(d.get("distance", 0.0))
        except (TypeError, ValueError):
            return None
        name = str(d.get("source_name", "") or "")
        if not name:
            return None
        return cls(source_name=name,
                   source_file=str(d.get("source_file", "") or ""),
                   distance=dist)

    def describe(self) -> str:
        """The one-line summary shown to the user (log, tab, tooltip)."""
        return "offset %+g from '%s'" % (self.distance, self.source_name)
