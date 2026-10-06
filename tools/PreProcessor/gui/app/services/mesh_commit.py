"""Trial and Generate: ONE generation, two dispositions. Qt-free.

Issue #166, parent #158. The operator presses **Trial** as often as they like —
it costs about a second — looks at the mesh and its verdict, adjusts, and
presses it again. **Generate** is the other disposition of the SAME generation:
it writes that mesh into the case, embeds the whole case type that judged it,
freezes the verdict beside it and leaves a runnable pipeline script.

GENERATE DOES NOT RECOMPUTE, AND THAT IS THE WHOLE POINT. If Trial showed mesh A
and Generate shipped mesh B the operator approved one thing and the solver reads
another, and the verdict's traceability is gone — and folds and wall-spacing
error are exactly the defects that move with density, so "it would come out the
same" is the claim least worth trusting. :class:`TrialMesh` is therefore the
unit this module deals in: a generation that has already happened, carrying
where its files are, what judged it and what it was generated FROM. Generate
copies; it never launches a mesher.

TRIAL WRITES NOTHING THE CASE CONSUMES. The GUI already meshes into its session
temp dir (`<temp>/global_mesh.vtk`, wiped on exit — `.claude/rules/gui-handoff.md`),
so Trial is that run with no disposition at all, and nothing here is reached. The
rule that matters is the one in the other direction: `commit` is the ONLY writer
of a case's mesh on this path, so a Trial after a Generate cannot touch what
Generate approved.

THE REFUSAL IS NOT SPELLED HERE. `case_type_verdict.commit_refusal` decides
whether a verdict blocks the write and says why; this module raises what it
returns. Hosts and dispositions do not spell verdict states
(`.claude/rules/gui-handoff.md`), and a disposition is a host.

WHAT A COMMITTED CASE CARRIES, and why each file is separate rather than one:

* ``<stem>.vtk`` + ``.vrt`` / ``.cel`` / ``.bnd`` / ``.provenance.json`` — the
  mesh itself, every format the run produced, under the case's own name.
* ``<stem>.casetype.json`` — **the whole case type document**, not its name and
  not a hash (user story 42). A name points at a file that moves; a hash proves
  only that it moved. The copy is a loadable case type: `case_type.load` reads
  it, and `HYBMESH_CASE_TYPE` can name it, which is what makes "explain this
  verdict six months later" an action rather than an archaeology project.
* ``<stem>.verdict.json`` — the verdict as TEXT already rendered, plus its
  state, its deviations and the exit code. Frozen, so that editing the case
  type the operator borrowed cannot rewrite the judgement of a finished case
  (user story 43). It holds no threshold numbers of its own: the bounds are in
  the embedded document beside it, and two copies of one number is how they
  come to disagree.
* ``<stem>.pipeline.json`` — a runnable script that regenerates the mesh
  (user story 44), written by the host's own `PipelineConfig`. Taken as an
  object with a `save_to_file` method rather than imported, so this module
  stays a stranger to the GUI's model layer and a test can hand it a stub.

THE FINGERPRINT ANSWERS ONE QUESTION: is the mesh in hand still the mesh this
configuration would produce? It is taken over the mesher's own config text —
the bytes the binary read, not a reconstruction of them — plus the content of
every input file that text names. A Generate that finds a matching fingerprint
commits what Trial produced; one that does not generates first and commits that.
It is deliberately a CONSERVATIVE answer: anything it cannot read hashes as
missing, so an unreadable input makes the trial stale rather than silently fresh.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import shutil

from app.services import case_sources, case_type, case_type_verdict
from app.services.logging_setup import get_logger

logger = get_logger(__name__)

#: The mesh files a run can leave beside its ``.vtk``, in the order a committed
#: case lists them. The sidecar is named by `case_sources.mesh_provenance_paths`
#: rather than spelled here, so the one name computation the case export already
#: stages a run's provenance with stays the only one.
MESH_EXTS = (".vtk", ".vrt", ".cel", ".bnd")

#: What a committed case's own three files are called, keyed by what they hold.
#: `<stem>` is the mesh's, so a directory holding two meshes carries two sets
#: rather than one that the second Generate overwrites.
SIDECAR_EXTS = {"case_type": ".casetype.json",
                "verdict": ".verdict.json",
                "pipeline": ".pipeline.json"}

VERDICT_SCHEMA = "hybmesh-case-verdict"
VERDICT_SCHEMA_VERSION = 1


class CommitRefused(Exception):
    """Generate will not write this mesh into the case, and the message says why.

    Carries `case_type_verdict.commit_refusal`'s own sentence verbatim: the
    refusal is one body of knowledge and this is not a second place that
    re-words it.
    """


class TrialMesh:
    """One generation that has already happened, and what judged it.

    `mesh_path` is where the run actually wrote — the session temp dir on the
    GUI path — and is the file `commit` copies FROM. `fingerprint` is what it
    was generated from (see the module docstring); an empty one means nobody
    computed it, and :meth:`matches` then answers False rather than guessing,
    because "we did not check" must not read as "it is current".
    """

    __slots__ = ("mesh_path", "exit_code", "fingerprint", "verdict", "report",
                 "level")

    def __init__(self, mesh_path: str, exit_code: int, fingerprint: str = "",
                 verdict=None, report: str = "", level: str = "INFO"):
        self.mesh_path = mesh_path
        self.exit_code = exit_code
        self.fingerprint = fingerprint
        #: `case_type_verdict.Verdict`, or ``None`` when no case type is in
        #: play. ``None`` is an ordinary state, not an error: most of this
        #: repo's cases have no case type and still have to be committable.
        self.verdict = verdict
        #: The verdict already rendered, and the grade to log it at. Rendered
        #: ONCE, where it was judged, so the window and the frozen record quote
        #: the same words.
        self.report = report
        self.level = level

    @property
    def usable(self) -> bool:
        """True when the run left a mesh file on disk to dispose of at all."""
        return bool(self.mesh_path) and os.path.isfile(self.mesh_path)

    def matches(self, fingerprint: str) -> bool:
        """True when this trial was generated from exactly `fingerprint`."""
        return bool(self.fingerprint) and self.fingerprint == fingerprint

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return ("TrialMesh(mesh_path=%r, exit_code=%r, verdict=%r)"
                % (self.mesh_path, self.exit_code, self.verdict))


def inputs_fingerprint(config_text: str, input_paths) -> str:
    """What a generation was made FROM, as one hex digest.

    `config_text` is the mesher config as the binary read it; `input_paths` the
    files that config names (geometry, and the block topology document in
    `MESH_MODE 1`). A path that cannot be read contributes a MISSING marker
    rather than being skipped, so a vanished geometry changes the answer instead
    of leaving it looking unchanged.
    """
    digest = hashlib.sha256()
    digest.update(config_text.encode("utf-8", "replace"))
    for path in sorted(set(input_paths)):
        digest.update(b"\0" + os.path.abspath(path).encode("utf-8", "replace"))
        try:
            with open(path, "rb") as fh:
                digest.update(hashlib.sha256(fh.read()).digest())
        except OSError as exc:
            logger.debug("fingerprint: %s is unreadable (%s); the trial it "
                         "belongs to will read as stale", path, exc,
                         exc_info=True)
            digest.update(b"<missing>")
    return digest.hexdigest()


def judge_run(mesh_path: str, exit_code: int, config=None,
              fingerprint: str = "") -> TrialMesh:
    """Judge one finished generation ONCE and carry the answer.

    The single call the GUI's mesh controller makes after a run. It reaches
    `case_type_verdict.run_verdict` rather than `run_report` because the
    disposition that follows needs the judgement itself — the case type to
    embed, the state to refuse on — and judging twice to get it would be two
    answers about one mesh.
    """
    verdict, report, level = case_type_verdict.run_verdict(
        mesh_path, exit_code, config=config)
    return TrialMesh(mesh_path, exit_code, fingerprint=fingerprint,
                     verdict=verdict, report=report, level=level)


def sidecar_paths(dest_mesh: str) -> dict:
    """The three files a committed case carries beside `dest_mesh`, by role."""
    stem = os.path.splitext(dest_mesh)[0]
    return {role: stem + ext for role, ext in SIDECAR_EXTS.items()}


def verdict_record(trial: TrialMesh, dest_mesh: str, when: str) -> dict:
    """The frozen judgement, as the committed case holds it.

    TEXT, not a recipe for recomputing one. The report is already rendered and
    the state is already decided, so nothing here has to be re-derived later
    against a case type that has since moved on — which is exactly what user
    story 43 asks for. The embedded document beside it is what explains the
    numbers; this file does not restate them.
    """
    verdict = trial.verdict
    record = {
        "schema": VERDICT_SCHEMA,
        "version": VERDICT_SCHEMA_VERSION,
        "recorded": when,
        "mesh": os.path.basename(dest_mesh),
        "exit_code": trial.exit_code,
        "state": verdict.state,
        "report": trial.report,
        "case_type": {
            "name": verdict.case_type.name,
            # WHERE IT CAME FROM, kept beside the copy rather than instead of
            # it: the embedded document is the authority, and this says which
            # file on the author's machine it was taken from.
            "source": verdict.case_type.source,
            "embedded": os.path.basename(sidecar_paths(dest_mesh)["case_type"]),
        },
        "deviations": [d.describe() for d in verdict.deviations],
    }
    return record


def commit(trial: TrialMesh, dest_mesh: str, pipeline=None,
           when: str | None = None) -> list:
    """Write `trial` into the case at `dest_mesh`. Returns the files written.

    Raises :class:`CommitRefused` when the verdict refuses it, BEFORE anything
    is written — a case half-committed to a mesh nobody approved is worse than
    one not committed at all — and :class:`OSError` if the copy itself fails.

    `pipeline` is the host's `PipelineConfig` (anything with `save_to_file`), or
    ``None`` when the host has no script to leave; `when` is the timestamp
    recorded, defaulting to now in UTC.
    """
    refusal = case_type_verdict.commit_refusal(trial.verdict)
    if refusal:
        raise CommitRefused(refusal)
    if not trial.usable:
        raise CommitRefused(
            "There is no mesh to write into the case: the generation left "
            "nothing at %s." % (trial.mesh_path or "<no path>"))

    when = when or datetime.datetime.now(
        datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    dest_mesh = os.path.abspath(dest_mesh)
    os.makedirs(os.path.dirname(dest_mesh) or ".", exist_ok=True)

    written = _copy_mesh_files(trial.mesh_path, dest_mesh)
    sidecars = sidecar_paths(dest_mesh)

    if trial.verdict is not None:
        # The WHOLE document (user story 42). `case_type.save` is the one
        # writer, so the embedded copy is a case type `case_type.load` reads
        # back — not a report about one.
        case_type.save(trial.verdict.case_type, sidecars["case_type"])
        written.append(sidecars["case_type"])
        _write_json(sidecars["verdict"],
                    verdict_record(trial, dest_mesh, when))
        written.append(sidecars["verdict"])
    else:
        # SAID by its absence being explicit: a case with no verdict file was
        # judged by nobody, which a reader must be able to tell apart from one
        # whose judgement went missing. The host logs it; stale files from an
        # earlier Generate must not be left behind to answer for this one.
        _remove_stale(sidecars["case_type"], sidecars["verdict"])

    if pipeline is not None:
        pipeline.save_to_file(sidecars["pipeline"])
        written.append(sidecars["pipeline"])
    return written


def _copy_mesh_files(src_mesh: str, dest_mesh: str) -> list:
    """Copy every format the run produced, under the case's own stem.

    The trial's stem is the session temp dir's (`global_mesh`) and the case's is
    `mesh_<case>`, so this RENAMES as it copies rather than copying a directory:
    a committed case must be named after the case, not after the scratch file it
    came from.
    """
    src_stem = os.path.splitext(src_mesh)[0]
    dest_stem = os.path.splitext(dest_mesh)[0]
    written = []
    for ext in MESH_EXTS:
        src = src_stem + ext
        if os.path.isfile(src):
            shutil.copy2(src, dest_stem + ext)
            written.append(dest_stem + ext)
    for src in case_sources.mesh_provenance_paths(src_mesh):
        if os.path.isfile(src):
            dest = case_sources.mesh_provenance_paths(dest_mesh)[0]
            shutil.copy2(src, dest)
            written.append(dest)
            break
    return written


def _write_json(path: str, doc: dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _remove_stale(*paths: str) -> None:
    for path in paths:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError as exc:
            logger.warning("could not remove the stale %s left by an earlier "
                           "Generate: %s", path, exc, exc_info=True)
