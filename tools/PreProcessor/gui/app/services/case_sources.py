"""Stage the CAD/STL a solver case was actually built from into the case itself.

A case directory used to hold only what the SOLVER reads: the STAR-CD triplet,
the binary grid, ``input.in``. That is enough to rerun the case and not nearly
enough to *understand* it — the geometry it was cut from lived somewhere else
entirely (``examples/geometries/``, someone's Desktop), free to be edited,
renamed or deleted while the case sat there looking complete. Six months later
"which body is this?" had no answer inside the case at all.

So the sources are copied in beside the grid, under ``grid/<SOURCE_DIR_NAME>/``.
"Source" means every file the run READ, not only the drawn ones: a ``MESH_MODE 1``
case is shaped by its block topology document as much as by its geometry, and two
of this repo's five shipped topology cases have no geometry at all — see
:func:`mesh_input_paths`.

Four rules keep the copy honest:

* **Copy, never move.** The CAD is a project asset that other cases, the GUI
  session and the mesher all still point at. Relocating it would break every one
  of them to tidy up one case.
* **Sidecars follow their file.** A resampled ``.dat`` carries per-segment BC
  labels and No-BL flags in ``<name>.dat.meta``; the geometry without it is a
  different geometry (see ``meta_io`` / the orphaned-GROUP_BC failure), so the
  sidecar is pulled in automatically rather than being one more thing to
  remember.
* **Collisions are renamed, not overwritten.** Two bodies can legitimately both
  be ``profile.dat`` from different directories. The second becomes
  ``profile_2.dat`` — silently overwriting would leave a case describing a body
  that is not in it.
* **Where each file came from is recorded.** Copying discards the original path,
  and a renamed collision discards the name too, so ``SOURCES.txt`` maps every
  staged name back to the absolute path it was taken from and stamps the case.
  Without it the folder answers "which body?" but not "which revision of it?".
  It is also the only index there is: ``tools/scripts/case_sources_index.py``
  answers "which cases use this geometry?" by reading these files back.

A hard link would cost no disk and was rejected for it: the two names would be
one inode, so editing the CAD afterwards would silently rewrite what the case
holds — which is the exact property the copy exists to deny. (It also cannot
cross filesystems, which a case dir and a Desktop routinely do.)

Qt-free: both ``solver_ctrl`` (via the worker) and the headless
``pipeline_runner`` stage through here, so a GUI case and a scripted one hold
the same thing.
"""
from __future__ import annotations

import os
import shutil

from app.services import mesh_modes

# Under grid/, because that is where the mesh this geometry became already sits.
SOURCE_DIR_NAME = "cad"
SOURCES_INDEX = "SOURCES.txt"

# Origin recorded for a file written from the live configuration rather than
# copied from disk. Read back by tools/scripts/case_sources_index.py, so it is a
# constant rather than a string spelled in two places.
GENERATED = "(generated)"

# Pulled in automatically alongside a staged file. The .meta is not optional
# metadata — it is where the per-segment BC labels and No-BL flags live.
_SIDECARS = (".meta",)


def _noop(_msg: str) -> None:
    pass


def mesh_provenance_paths(*mesh_outputs) -> list:
    """The ``*.provenance.json`` sidecars beside the given mesh output paths.

    The mesher writes one per export format, named after the output stem with
    every known extension stripped (``src/cli.cpp``: ``stripExt`` +
    ``writeProvenance``). Non-existent candidates are returned anyway — the
    staging service drops what is not on disk — so this stays a pure name
    computation rather than a second place that decides what exists.
    """
    out: list = []
    for path in mesh_outputs:
        if not path:
            continue
        stem = os.path.splitext(path)[0]
        for cand in (f"{stem}.provenance.json", f"{path}.provenance.json"):
            if cand not in out:
                out.append(cand)
    return out


def mesh_input_paths(mesh_config, base_dir: str = "") -> list:
    """The mesh stage's input files that are not geometry, for staging.

    Today that is exactly one: the **block topology document** a ``MESH_MODE 1``
    run fills. It belongs here for the same reason the CAD does — in that mode it
    decides the mesh *as much as the geometry does*, and two of this repo's five
    shipped topology cases name no geometry at all — so a case staged without it
    is incomplete in precisely the way ``grid/cad/`` exists to prevent (#56). The
    mesher already agrees: ``src/cli.cpp:417`` puts it in the run's
    ``inputFiles``, beside the geometry, for the provenance sidecar.

    **Whether the run READ a topology is not decided here**:
    ``mesh_modes.topology_file`` owns that, so this and the mesh stage's own
    precondition cannot disagree about it. What is decided here is where the file
    IS — ``base_dir`` resolves a relative declaration, because a pipeline script
    quotes repo-relative paths and ``run_batch`` is launched from wherever the
    user happens to be, so the interpreter's cwd is not the answer. Existence is
    not checked: that is ``stage_case_sources``' single decision, as it already
    is for :func:`mesh_provenance_paths`.
    """
    topo = mesh_modes.topology_file(mesh_config)
    if not topo:
        return []
    if not os.path.isabs(topo) and base_dir:
        topo = os.path.join(base_dir, topo)
    return [os.path.abspath(topo)]


def mesh_config_generated(mesh_config, case_name: str) -> list:
    """``(name, text)`` pairs the case can only RECONSTRUCT, not copy.

    The mesher parameter file, always: the GUI never writes a persistent one — a
    run serialises the live config into a temp directory that is removed on exit —
    so without regenerating it the case would record every input except the one
    that shaped its grid.

    And, when a TEMPLATE drove the run, the block topology DOCUMENT beside it
    (#135). This is the half #134 named as a blind spot and deferred here: the two
    callers that want the config as CONTENT rather than as a run read
    ``cfg.mesh_topology_file``, which is EMPTY for a template case, because that
    path does not exist until ``save_config_to_file`` has projected one. A staged
    config therefore carried no ``MESH_TOPOLOGY_FILE`` line at all, and a case that
    cannot say what topology it was cut from is precisely what ``grid/cad/``
    exists to prevent — the same argument :func:`mesh_input_paths` already makes
    for a hand-written document, which is COPIED IN as a source. A template's
    document has no file to copy, so it is generated, exactly like the parameter
    file it sits beside.

    Named by :func:`~app.services.topology_model.projection_path`, so the pair
    follows ONE naming rule rather than two that can drift; quoted by BARE
    FILENAME, because the two files are siblings in the staged folder and the case
    is meant to survive being copied somewhere else. That is the one place the
    staged line deliberately differs from the line the run itself wrote, which is
    absolute — the mesher resolves it against its own working directory, and the
    staged copy is a record rather than something rerun in place.

    Qt-free and shared, like everything else here: ``controllers/solver_ctrl.py``
    and ``services/pipeline_case_sources.py`` both call this rather than each
    spelling the name and the projection out. Raises whatever the projection
    raises — both callers already downgrade a failure here to a warning, because a
    case that stages its geometry but not its settings is still worth having.
    """
    from app.models.mesh_config_io import config_to_text
    from app.services import topology_model

    stem = f"Background_para_{case_name}"
    model = getattr(mesh_config, "topology", None)
    if model is None or not getattr(model, "family", ""):
        return [(f"{stem}.dat", config_to_text(mesh_config))]
    doc_name = os.path.basename(topology_model.projection_path(f"{stem}.dat"))
    return [
        (f"{stem}.dat", config_to_text(mesh_config, topology_path=doc_name)),
        (doc_name,
         topology_model.document_text(topology_model.build_document(model))),
    ]


def _unique_name(dest_dir: str, name: str, taken: set) -> str:
    """``name``, or ``stem_2.ext`` / ``stem_3.ext`` until it is free."""
    if name not in taken and not os.path.exists(os.path.join(dest_dir, name)):
        return name
    stem, ext = os.path.splitext(name)
    n = 2
    while True:
        cand = f"{stem}_{n}{ext}"
        if cand not in taken and not os.path.exists(os.path.join(dest_dir, cand)):
            return cand
        n += 1


def stage_case_sources(sources, grid_dir: str, log=_noop, generated=()) -> list:
    """Copy ``sources`` (and their sidecars) into ``grid_dir/cad/``.

    ``generated`` is an iterable of ``(name, text)`` written straight into the
    folder — the mesh parameter file, which the GUI only ever materialises as a
    temp file deleted on exit, so there is no path to copy and the alternative
    is that a case records every input except the one that shaped its grid.

    Returns a list of ``(origin, dest_abs)``, where ``origin`` is the source path
    or ``"(generated)"``. Missing and duplicate entries are dropped — callers
    assemble the list from whatever the case happens to have, so blanks are
    normal input, not an error. Creates nothing when there is nothing to stage.
    """
    wanted: list = []
    seen: set = set()
    for src in sources or ():
        if not src:
            continue
        src = os.path.abspath(src)
        if not os.path.isfile(src):
            continue
        key = os.path.realpath(src)
        if key in seen:
            continue
        seen.add(key)
        wanted.append(src)
        # A sidecar rides with its file, under whatever name that file ends up
        # with — resolved below, so a renamed collision keeps the pair together.
        for suf in _SIDECARS:
            side = src + suf
            if os.path.isfile(side) and os.path.realpath(side) not in seen:
                seen.add(os.path.realpath(side))
                wanted.append(side)

    made = [(n, t) for n, t in (generated or ()) if n and t]
    if not wanted and not made:
        return []

    dest_dir = os.path.join(grid_dir, SOURCE_DIR_NAME)
    os.makedirs(dest_dir, exist_ok=True)

    staged: list = []
    names: dict = {}          # src_abs -> staged basename
    taken: set = set()
    for src in wanted:
        base = os.path.basename(src)
        # Keep a sidecar attached to the name its owner actually got.
        owner = next((s for s in (src[:-len(suf)] for suf in _SIDECARS
                                  if src.endswith(suf)) if s in names), None)
        if owner is not None:
            base = names[owner] + src[len(owner):]
        name = _unique_name(dest_dir, base, taken)
        taken.add(name)
        names[src] = name
        dst = os.path.join(dest_dir, name)
        shutil.copy2(src, dst)
        staged.append((src, dst))
        note = f" (renamed from {os.path.basename(src)})" \
            if name != os.path.basename(src) else ""
        log(f"[case] source -> grid/{SOURCE_DIR_NAME}/{name}{note}")

    # Generated last, so a real file of the same name keeps its own name and the
    # generated one steps aside — a copied input is evidence, a regenerated one
    # is only a reconstruction.
    for gname, text in made:
        name = _unique_name(dest_dir, os.path.basename(gname), taken)
        taken.add(name)
        dst = os.path.join(dest_dir, name)
        with open(dst, "w", encoding="utf-8") as f:
            f.write(text)
        staged.append((GENERATED, dst))
        log(f"[case] source -> grid/{SOURCE_DIR_NAME}/{name} (written from the "
            "live configuration)")

    _write_index(dest_dir, staged, log)
    return staged


def _write_index(dest_dir: str, staged: list, log=_noop) -> None:
    """Record where every staged file came from.

    Rewritten in full on each run rather than appended to: the folder describes
    the case as it stands now, and a stale line for a body that is no longer part
    of it is exactly the kind of confident-but-wrong record this file exists to
    prevent."""
    lines = ["# CAD / STL sources this solver case was built from.",
             "# Copied here by HybMesh2D; the originals are untouched.",
             "# Columns: staged name  <-  original absolute path",
             ""]
    width = max((len(os.path.basename(d)) for _s, d in staged), default=0)
    for src, dst in sorted(staged, key=lambda p: os.path.basename(p[1])):
        lines.append(f"{os.path.basename(dst):<{width}}  <-  {src}")
    lines.append("")
    path = os.path.join(dest_dir, SOURCES_INDEX)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except OSError as e:
        # The copies are the deliverable; the index is the explanation. Losing
        # the explanation must not fail the run, but it must not be silent.
        log(f"[case] [WARNING] could not write grid/{SOURCE_DIR_NAME}/"
            f"{SOURCES_INDEX}: {e}")
