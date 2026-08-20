"""Stage the CAD/STL a solver case was actually built from into the case itself.

A case directory used to hold only what the SOLVER reads: the STAR-CD triplet,
the binary grid, ``input.in``. That is enough to rerun the case and not nearly
enough to *understand* it — the geometry it was cut from lived somewhere else
entirely (``examples/geometries/``, someone's Desktop), free to be edited,
renamed or deleted while the case sat there looking complete. Six months later
"which body is this?" had no answer inside the case at all.

So the sources are copied in beside the grid, under ``grid/<SOURCE_DIR_NAME>/``.
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
