"""A derived geometry MATERIALISED for a run that holds only the record. Qt-free.

#154, parent #150. #152 made the offset an ordinary geometry: it is drawn on the
canvas, resampled, given boundary conditions, saved with the project and staged
into a case, and NOTHING downstream learned a new kind of object. That decision
is what kept binding resolution, the repair panel, the resampler, case staging
and the stable-id scheme untouched, and composing it with #151's ``follows`` on a
real case confirmed every one of those.

IT LEFT ONE GAP, AND IT IS THE STAGE THAT DESCRIBES THE RUN. A pipeline script
identifies a CAD input BY ITS FILE PATH — ``cads[i].input_file`` — and a geometry
that was derived rather than loaded has no path. So a script saved from a
workspace holding an offset carried the RECORD (source, distance) and no
geometry, and both hosts then did the only thing they could with an entry that
names no file: the headless runner's ``cad_skip`` skipped it, and the GUI's
script loader warned that a tab was missing. The mesh that ran was one geometry
short, and on a two-ring case that geometry is the seam.

THE ANSWER IS TO PRODUCE IT, FROM THE RECORD, AT THE START OF THE RUN. That is
not the live recomputation #150 rules out — which was a recomputation on every
geometry EDIT, an implicit write into every edit path that would have had to be
reconciled with global undo and the outline re-fit. This is the explicit
Regenerate action, performed once, at the one moment the whole chain is being
executed on purpose. A script becomes self-contained: it carries the body and the
instruction, and the curve between them is derived rather than shipped, so it can
never be the offset of a body the script no longer names.

ONE OWNER, AND NOW REALLY TWO CALLERS. ``app/services/geometry_offset.py`` is the
law; #152 could only state that a second caller WOULD go through it, because the
CAD-stage creation path was the only one there was. This module is that second
caller, and both hosts reach the law through it: ``services/pipeline_runner``
before its resample stage, and ``controllers/pipeline_io_ctrl`` when a script is
loaded into the GUI. That is what makes "the same script produces the same mesh
in both hosts" a property of the code rather than a hope — the two do not each
offset; they call one function with the same three arguments.

THE POINTS ARE WRITTEN AT ``%.10f``, WHICH IS NOT A ROUND NUMBER. It is the
precision ``controllers/backend_ctrl`` writes when it hands a session's points to
the resampler. The GUI reads this file into a session and then writes that temp
file, so any finer precision here would be rounded away on one host and not the
other, and the two hosts' meshes would differ in the eleventh digit for no reason
a reader could find.

A RECORD WHOSE SOURCE THE SCRIPT DOES NOT CARRY IS REFUSED BY NAME, never skipped
and never resolved to whatever is nearest — the same rule, and for the same
reason, as the GUI's Regenerate refusal: a ring silently derived from the wrong
body is a mesh that runs, exports and looks right.

Rules: ``.claude/rules/pipeline-case.md``; why: ``docs/design_notes/pipeline.md``.
"""
from __future__ import annotations

import os

import numpy as np

from app.models.derived_geometry import DerivedOffset
from app.services.geom_path_identity import canonical_geom_path
from app.services.geometry_offset import OffsetRefused, offset_points
from app.services.geometry_service import load_points_dat
from app.services.logging_setup import get_logger

_log = get_logger(__name__)

__all__ = ["DerivedGeometryError", "DERIVED_DIR", "record_for", "needs_derivation",
           "source_index", "source_points", "output_path", "materialise",
           "materialise_all"]

#: Where a materialised curve lands, under the repo's generated-artifact tree.
#: NOT beside the source geometry: the source is a project asset a user owns and
#: several cases point at, and writing a run's intermediate next to it is how a
#: geometry directory fills with files nobody can attribute.
DERIVED_DIR = os.path.join("results", "derived")

#: The precision the resampler is handed points at elsewhere. See the module
#: docstring — this is a parity constant, not a taste.
_FMT = "%.10f"


class DerivedGeometryError(ValueError):
    """A derived geometry this run cannot produce, named.

    Carries ``index`` — the ``cads`` entry it is about — so a caller can say which
    entry of the script it read, rather than re-parsing prose.
    """

    def __init__(self, message: str, index: int = -1):
        super().__init__(message)
        self.index = int(index)


def record_for(cad: dict) -> DerivedOffset | None:
    """The offset record a ``cads`` entry carries, or ``None``."""
    return DerivedOffset.from_dict((cad or {}).get("derived_from"))


def needs_derivation(cad: dict) -> bool:
    """Does this entry describe a geometry that has to be produced?

    A record AND no source file. An entry that carries BOTH — an offset the user
    exported, then listed by path — is an ordinary geometry and is left alone:
    re-deriving it would overrule a file the script names, and #152's rule is that
    regeneration is something a user asks for.
    """
    return record_for(cad) is not None and not (cad or {}).get("input_file")


def source_index(pcfg, repo: str, index: int) -> int:
    """Which ``cads`` entry the entry at ``index`` was derived FROM.

    By FILE first and by the source's display name second — the same order
    ``controllers/offset_geom_ctrl.find_offset_source`` uses, because it is
    answering the same question about the same record. Raises
    :class:`DerivedGeometryError` naming the source when the script does not carry
    it, rather than falling back to a neighbour.
    """
    rec = record_for(pcfg.cad_at(index))
    if rec is None:
        raise DerivedGeometryError(
            "cads[%d] carries no offset record, so there is nothing to derive."
            % index, index)
    want = canonical_geom_path(rec.source_file) if rec.source_file else ""
    if want:
        for i in pcfg.cad_indices():
            if i == index:
                continue
            got = pcfg.resolve_input_file(repo, i)
            if got and canonical_geom_path(got) == want:
                return i
    name = (rec.source_name or "").strip()
    if name:
        for i in pcfg.cad_indices():
            if i == index:
                continue
            got = pcfg.resolve_input_file(repo, i)
            if got and os.path.basename(got) == os.path.basename(name):
                return i
    raise DerivedGeometryError(
        "cads[%d] is an offset of '%s', which this script does not carry. Add "
        "that geometry as a CAD entry — a derived geometry is never re-derived "
        "from a different source." % (index, rec.source_name or "(unnamed)"),
        index)


def output_path(pcfg, repo: str, index: int) -> str:
    """Where the entry at ``index`` is materialised.

    The stem comes from the entry's own ``output_file`` when it names one, so the
    derived curve and the resampled curve share a basename and a reader of the
    case can see they are two revisions of one geometry. Both hosts compute this
    the same way, which is what lets the staging service name the file without
    having run the derivation.
    """
    out = (pcfg.cad_at(index) or {}).get("output_file", "")
    stem = os.path.splitext(os.path.basename(out))[0] if out else ""
    if not stem:
        stem = "%s_derived_%d" % (pcfg.name or "pipeline", index)
    return os.path.join(repo, DERIVED_DIR, pcfg.name or "pipeline", stem + ".dat")


def source_points(path: str, index: int, rec: DerivedOffset):
    """The source's point array, or a refusal naming the geometry.

    A guard of its own rather than four lines inside :func:`materialise`, because
    "the body this offset is of is not there" is a distinct answer from "the
    script does not carry it" and each has its own sentence — and because a gate
    can then take this one away and watch the refusal disappear.
    """
    if not path or not os.path.exists(path):
        raise DerivedGeometryError(
            "cads[%d] is an offset of '%s', whose geometry file is not on disk "
            "(%s). Nothing was derived." % (index, rec.source_name, path or "unset"),
            index)
    try:
        return np.asarray(load_points_dat(path), dtype=float)[:, :2]
    except Exception as e:
        raise DerivedGeometryError(
            "cads[%d] is an offset of '%s', which could not be read: %s"
            % (index, rec.source_name, e), index) from e


def materialise(pcfg, repo: str, index: int) -> str:
    """Derive the entry at ``index`` onto disk and return the path written.

    The closure flag is the SOURCE's, resolved through the source's own
    :class:`~app.models.project.ProjectModel` rather than guessed here: the
    offset law's two ends depend on it, and a second answer to "is this outline
    closed" is a second curve.
    """
    src = source_index(pcfg, repo, index)
    rec = record_for(pcfg.cad_at(index))
    path = pcfg.resolve_input_file(repo, src)
    pts = source_points(path, index, rec)
    closed = pcfg.build_project_model(repo, "", src).resolve_closure(pts)
    try:
        out = offset_points(pts, rec.distance, closed)
    except (OffsetRefused, ValueError) as e:
        # NOT trimmed and NOT clamped, for #152's reason: a trimmed offset is a
        # different curve and no longer carries its source's segmentation. When
        # the law named a distance that would have worked, that number is the
        # whole point of the message and is carried through verbatim.
        raise DerivedGeometryError(
            "cads[%d] is an offset of '%s' by %g, which cannot be produced: %s"
            % (index, rec.source_name, rec.distance, e), index) from e
    dest = output_path(pcfg, repo, index)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    np.savetxt(dest, out, fmt=_FMT)
    return dest


def materialise_all(pcfg, repo: str, log=None) -> list:
    """Produce every derived geometry this run needs, in ``cads`` order.

    Sets each entry's ``input_file`` to the file written, so everything that
    follows — the resample stage, the mesh stage's geometry wiring, and the case's
    own record of what it was built from — treats the curve as the ordinary
    geometry #150 decided it should be, with no second code path anywhere.

    Returns ``[(index, path), ...]``. Raises :class:`DerivedGeometryError`: a run
    that quietly drops a geometry meshes something the user did not ask for, and
    on a two-ring case the geometry it drops is the seam.
    """
    made = []
    for i in pcfg.cad_indices():
        if not needs_derivation(pcfg.cad_at(i)):
            continue
        dest = materialise(pcfg, repo, i)
        pcfg.cads[i]["input_file"] = dest
        made.append((i, dest))
        rec = record_for(pcfg.cad_at(i))
        _log.debug("derived cads[%d] -> %s", i, dest)
        if log is not None:
            log("[CAD] derived geometry %d/%d: %s -> %s"
                % (i + 1, len(pcfg.cads), rec.describe(), dest))
    return made
