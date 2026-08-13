"""Package a solver case that ran here into a folder that runs THERE.

A case under ``results/solver/<name>/`` mixes two kinds of file: the handful of
inputs that define the run, and the hundreds of MB of output it produced. Copying
the directory wholesale ships a result set nobody asked for; copying it by hand
loses whichever input was not on the person's mental list. This module makes the
selection explicit.

What ships (an ALLOW-list, so an output can never sneak in by being new):

* ``grid/``  — the mesh the solver reads (``*.grid``/``*.bc``) plus its boundary
  table (``*.def``) and the getPGrid inputs that regenerate them
  (``input.vrt``/``.cel``/``.bnd`` + ``para.in``, which is written out under the
  self-explaining name ``getPGrid.in`` — see ``_RENAMES``).
* ``work/``  — ``input.in``, the ``*.def`` table, ``phi.dat`` when the run has an
  immersed solid, and the restart zone dump **only when ``input.in`` actually
  restarts from it** (``include_restart="auto"``, the default). It is the largest
  file in a case and an OUTPUT that a restart run happens to read back, so
  shipping it unasked is how a 100 MB package appears with nothing to say why.
* ``dll/``   — the compiled ``*.so`` **and** the ``*.cc`` it came from, pulled
  from ``results/solver/dll_src`` by basename. The binary alone is not portable
  (it is this machine's arch and libstdc++); the source is what actually travels.

Anything not on the list is skipped and NAMED in the manifest, split into "known
output", "not used by this run" and "not recognised" — a skipped input is then a
visible line, not an omission discovered on the far machine.

**The allow-list decides by NAME, so two of its entries also have to ask whether
the run uses them** — ``work/phi.dat`` and ``dll/*``, see :func:`_unused_reason`.
USER-REPORTED: "I didn't configure IBM, why is there a phi.dat and a dll/?".

**Absolute paths are the other half of portability.** Every quoted value in
``input.in`` is a file path, and the GUI happily writes an absolute one for a
probe-point or CFL-schedule file the user picked from anywhere on disk. Those
resolve to nothing on another machine, so each is copied into ``work/`` and the
reference rewritten to ``./<name>``.

Qt-free: the GUI layer asks the questions, this does the work (and the tests can
drive it without a display).
"""
from __future__ import annotations

import os
import re
import shutil
import tarfile
from dataclasses import dataclass, field

# run_case.sh + MANIFEST.txt are generated next door (this module was over the
# GUI file-size budget). They are imported under their old private names so
# every call site here reads as it did.
from app.services.case_export_docs import (
    GETPGRID_INPUT,
    manifest_text as _manifest_text,
    write_run_script as _write_run_script,
)

# Files a run PRODUCES. Only used to explain a skip in the manifest — the
# copy decision is made by the allow-lists below, never by this list.
_OUTPUT_PATTERNS = (
    re.compile(r"^xtecp"), re.compile(r"^tWall"), re.compile(r"^unicones\."),
    re.compile(r"^vsurface"), re.compile(r"^probe_data"),
    re.compile(r"^xxprocess"), re.compile(r"^mesh_tecplot"),
    re.compile(r"\.plt$"), re.compile(r"^fort\.\d+$"),
)

_RESTART_RE = re.compile(r"^binDump", re.IGNORECASE)

# Per-subdirectory allow-lists: (exact names, suffixes).
_GRID_KEEP = ({"para.in", "input.vrt", "input.cel", "input.bnd"},
              (".grid", ".bc", ".def"))
# No ".in" suffix here: it would subsume the exact "input.in" entry and, worse, turn
# this allow-list into a glob — a future solver writing work/restart.in or work/monitor.in
# would be copied as an input with no skip line to notice it, which is exactly the
# guarantee the allow-list exists to make. An input.in that references some other *.in
# (a CFL schedule, say) still travels: _resolve_input_in ships it BY REFERENCE.
_WORK_KEEP = ({"input.in", "phi.dat"}, (".def",))
_DLL_KEEP = (set(), (".so", ".cc", ".cpp", ".c", ".h", ".hpp"))

_SUBDIRS = ("grid", "work", "dll")

# Files that travel under a different name. ``para.in`` says nothing about what
# reads it, and there is a second para.in in this project (the STL3d stage), so
# the copy is named after the program whose stdin it is. The rename lives here,
# in the plan, so the manifest and run_case.sh cannot disagree about it.
_RENAMES = {"grid/para.in": f"grid/{GETPGRID_INPUT}"}

# Quoted values in input.in are ALL file paths (see SolverConfig.generate_input_in).
_QUOTED_RE = re.compile(r'"([^"]*)"')

# The immersed solid is declared in input.in itself, which makes "does this run
# read phi.dat?" a fact. Read off the file, so a hand-edited input.in is obeyed.
_IMMERSED_RE = re.compile(r"^\s*immersed_solid\s+true\b", re.IGNORECASE | re.MULTILINE)


class CaseExportError(Exception):
    """The case cannot be packaged (missing directory, unwritable target, …)."""


def _noop(_msg: str) -> None:
    pass


@dataclass
class ExportItem:
    """One file to copy: where it came from, where it lands, why."""
    src: str
    rel: str             # destination path relative to the export root
    reason: str = ""


@dataclass
class ExportPlan:
    case_dir: str
    items: list = field(default_factory=list)         # ExportItem
    skipped_output: list = field(default_factory=list)   # (rel, size) produced files
    skipped_unused: list = field(default_factory=list)   # (rel, size, why) not this run's
    skipped_other: list = field(default_factory=list)    # (rel, size) unrecognised
    rewrites: dict = field(default_factory=dict)      # input.in: raw -> portable
    warnings: list = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(_size(i.src) for i in self.items)

    def has(self, rel: str) -> bool:
        return any(i.rel == rel for i in self.items)


def _size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} GB"


def _is_output(name: str) -> bool:
    return any(p.search(name) for p in _OUTPUT_PATTERNS)


def _is_inside(child: str, parent: str) -> bool:
    """Whether ``child`` lives under ``parent`` (False across volumes, where
    commonpath refuses to answer rather than returning something misleading)."""
    try:
        return os.path.commonpath([os.path.abspath(child),
                                   os.path.abspath(parent)]) == os.path.abspath(parent)
    except ValueError:
        return False


def _keeps(name: str, keep) -> bool:
    exact, suffixes = keep
    return name in exact or name.endswith(suffixes)


# --------------------------------------------------------------------------- #
# Planning
# --------------------------------------------------------------------------- #
def _input_in_text(case_dir: str) -> str:
    """``work/input.in`` as text, or "" when it cannot be read."""
    try:
        with open(os.path.join(case_dir, "work", "input.in"),
                  encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def _loaded_shared_objects(case_dir: str) -> set:
    """Basenames of the ``*.so`` this run actually dlopens.

    Every DLL reference is a quoted path: ``init_cond_use_zdump_fn`` /
    ``SolidPhaseMotionDLL`` in ``input.in``, and a type-11 (user BC) row's
    ``"./name.so"`` in the ``*.def`` staged next to it — so a BC DLL counts as
    loaded even though ``input.in`` alone never mentions it.
    """
    text = _input_in_text(case_dir)
    work = os.path.join(case_dir, "work")
    try:
        names = sorted(os.listdir(work))
    except OSError:
        names = []
    for name in names:
        if not name.endswith(".def"):
            continue
        try:
            with open(os.path.join(work, name), encoding="utf-8",
                      errors="replace") as f:
                text += "\n" + f.read()
        except OSError:
            continue
    return {os.path.basename(r.strip()) for r in _QUOTED_RE.findall(text)
            if r.strip().endswith(".so")}


def _unused_reason(sub: str, name: str, loaded_so: set, immersed: bool) -> str:
    """Why an allow-listed file is no part of THIS run — "" when it is part of it.

    ``work/phi.dat`` and everything in ``dll/`` are kept by NAME, and a reused case
    directory (``prepare_case_dir`` writes in place) still holds both long after the
    immersed-solid run that produced them: fossils presented as "input" that the
    exported ``input.in`` never reads. That same ``input.in`` answers it — it
    declares ``immersed_solid`` (the phase field's only reader is the init DLL, so
    with neither a declaration nor a DLL nothing touches ``phi.dat``) and it names
    every DLL it loads. A source travels with its own ``.so``
    (``_add_dll_sources``); a header travels with whatever source ships, since it
    is the rebuild that needs it.
    """
    if sub == "dll":
        if name.endswith((".h", ".hpp")):
            return ""
        if f"{os.path.splitext(name)[0]}.so" not in loaded_so:
            return ("nothing in work/input.in or the BC .def loads it — left "
                    "over from an earlier run in this case directory")
    elif sub == "work" and name == "phi.dat":
        if not (immersed or loaded_so):
            return ("immersed-solid phase field, but this run declares no "
                    "immersed_solid and loads no DLL to read it — left over "
                    "from an earlier run in this case directory")
    return ""


def plan_export(case_dir: str, *, dll_src_dirs=(),
                include_restart: bool | str = "auto") -> ExportPlan:
    """Decide what a portable copy of ``case_dir`` contains. Touches no files.

    ``include_restart`` — True/False force the zone dump in or out; "auto" (the
    default) ships it only when ``work/input.in`` names it, i.e. when the run
    really is a restart. ``SolverConfig.generate_input_in`` writes
    ``zdump_fn_restart`` only under ``restart``, so the reference is an exact
    signal rather than a guess.
    """
    if not os.path.isdir(case_dir):
        raise CaseExportError(f"Not a case directory: {case_dir}")
    plan = ExportPlan(case_dir=os.path.abspath(case_dir))

    input_in = _input_in_text(case_dir)
    referenced = {os.path.basename(r.strip())
                  for r in _QUOTED_RE.findall(input_in)
                  if r.strip()}
    loaded_so = _loaded_shared_objects(case_dir)
    immersed = _IMMERSED_RE.search(input_in) is not None
    keeps = {"grid": _GRID_KEEP, "work": _WORK_KEEP, "dll": _DLL_KEEP}
    found_any = False
    for sub in _SUBDIRS:
        d = os.path.join(case_dir, sub)
        if not os.path.isdir(d):
            continue
        found_any = True
        for name in sorted(os.listdir(d)):
            src = os.path.join(d, name)
            if not os.path.isfile(src):
                continue
            rel = f"{sub}/{name}"
            restart = _RESTART_RE.match(name) is not None
            if restart:
                # The zone dump is an output that doubles as the input of a
                # restart run — carried by request or by input.in, never by the
                # allow-list.
                by_ref = name in referenced
                reason = ("restart zone dump — input.in restarts from it"
                          if by_ref else "restart zone dump (asked for)")
                wanted = include_restart is True or (
                    include_restart == "auto" and by_ref)
                (plan.items.append(ExportItem(src, rel, reason)) if wanted else
                 plan.skipped_output.append((rel, _size(src))))
                continue
            if _keeps(name, keeps[sub]):
                why = _unused_reason(sub, name, loaded_so, immersed)
                if why:
                    plan.skipped_unused.append((rel, _size(src), why))
                    continue
                dest = _RENAMES.get(rel, rel)
                plan.items.append(ExportItem(
                    src, dest,
                    f"input (renamed from {os.path.basename(rel)})"
                    if dest != rel else "input"))
            elif _is_output(name):
                plan.skipped_output.append((rel, _size(src)))
            else:
                plan.skipped_other.append((rel, _size(src)))
    if not found_any:
        raise CaseExportError(
            f"{case_dir} has no grid/ work/ dll/ subdirectory — is it a solver "
            "case directory?")

    _add_dll_sources(plan, dll_src_dirs)
    _resolve_input_in(plan)
    _check_completeness(plan)
    return plan


def _add_dll_sources(plan: ExportPlan, dll_src_dirs) -> None:
    """Pair every staged ``dll/*.so`` with the ``.cc`` it was compiled from.

    ``solver_case.stage_dll`` compiles ``results/solver/dll_src/foo.cc`` into
    ``<case>/dll/foo.so``, so the source lives OUTSIDE the case. Without it the
    package carries a binary that only this machine's arch can load.
    """
    sos = [i for i in plan.items if i.rel.startswith("dll/") and i.rel.endswith(".so")]
    for item in sos:
        stem = os.path.splitext(os.path.basename(item.rel))[0]
        if any(p.rel.startswith(f"dll/{stem}.") and not p.rel.endswith(".so")
               for p in plan.items):
            continue                      # source already sitting in dll/
        for d in dll_src_dirs:
            hit = next((os.path.join(d, f"{stem}{ext}")
                        for ext in (".cc", ".cpp", ".c")
                        if os.path.isfile(os.path.join(d, f"{stem}{ext}"))), None)
            if hit:
                plan.items.append(ExportItem(
                    hit, f"dll/{os.path.basename(hit)}", "DLL source"))
                break
        else:
            plan.warnings.append(
                f"dll/{stem}.so has no matching source in dll_src — it will only "
                "load on a machine matching this one's architecture and libstdc++.")


def _resolve_input_in(plan: ExportPlan) -> None:
    """Make every path inside ``work/input.in`` resolve on the target machine.

    A reference that already points inside the case stays as written (and the
    file it names is force-included, even if the allow-list did not pick it up).
    One pointing anywhere else is staged into ``work/`` and rewritten to
    ``./<name>``, because an absolute path from this machine is exactly what
    breaks on the next one.
    """
    work = os.path.join(plan.case_dir, "work")
    input_in = os.path.join(work, "input.in")
    if not os.path.isfile(input_in):
        plan.warnings.append(
            "work/input.in is missing — the exported case has no solver input "
            "file and cannot be run as-is.")
        return
    try:
        with open(input_in, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError as e:
        plan.warnings.append(f"could not read work/input.in: {e}")
        return

    # Destination names, plus the source names of anything that travels renamed:
    # a reference to grid/para.in must not re-add the file the plan already
    # carries as grid/getPGrid.in.
    taken = {i.rel for i in plan.items} | set(_RENAMES)
    # Files the caller DELIBERATELY excluded (include_restart=False). "Referenced by
    # input.in" must not quietly overrule that: the restart dump is the largest file in
    # work/, and re-adding it also listed the same path under INCLUDED *and* under
    # "SKIPPED — produced by the run" in the manifest, a contradiction the named-skip
    # design exists to make impossible.
    declined = {rel for rel, _size in plan.skipped_output}
    for raw in _QUOTED_RE.findall(text):
        ref = raw.strip()
        if not ref:
            continue
        resolved = os.path.normpath(
            ref if os.path.isabs(ref) else os.path.join(work, ref))
        inside = _is_inside(resolved, plan.case_dir)
        if not os.path.isfile(resolved):
            plan.warnings.append(
                f"input.in references '{ref}', which does not exist here — the "
                "exported case will fail the same way this one would.")
            continue
        if inside:
            rel = os.path.relpath(resolved, plan.case_dir).replace(os.sep, "/")
            if rel in declined:
                # Still rewrite the path below, so the exported input.in points at a
                # local name rather than at this machine's filesystem.
                plan.warnings.append(
                    f"input.in references '{ref}', which was deliberately NOT exported "
                    f"({rel} — see the skipped list). Turn the restart off on the target, "
                    "or export again with the restart dump included.")
            elif rel not in taken:          # referenced => an input, by definition
                plan.items.append(ExportItem(resolved, rel, "referenced by input.in"))
                taken.add(rel)
            if os.path.isabs(ref):          # absolute, but inside: make it relative
                plan.rewrites[raw] = os.path.relpath(resolved, work).replace(os.sep, "/")
            continue
        # Outside the case: stage a copy next to input.in under a free name.
        base = os.path.basename(resolved)
        rel = f"work/{base}"
        n = 2
        while rel in taken and not _same_file(plan, rel, resolved):
            base = f"{os.path.splitext(os.path.basename(resolved))[0]}_{n}" \
                   f"{os.path.splitext(resolved)[1]}"
            rel = f"work/{base}"
            n += 1
        if rel not in taken:
            plan.items.append(ExportItem(resolved, rel, "referenced by input.in"))
            taken.add(rel)
        plan.rewrites[raw] = f"./{base}"


def _same_file(plan: ExportPlan, rel: str, src: str) -> bool:
    return any(i.rel == rel and os.path.abspath(i.src) == os.path.abspath(src)
               for i in plan.items)


def _check_completeness(plan: ExportPlan) -> None:
    """Warn about what a runnable case needs and this one does not have."""
    rels = {i.rel for i in plan.items}
    if not any(r.endswith(".grid") for r in rels):
        plan.warnings.append(
            "no *.grid in grid/ — the target must regenerate it with "
            "'./run_case.sh --regrid' (getPGrid inputs are included).")
    if not any(r.endswith(".bc") for r in rels):
        plan.warnings.append("no *.bc in grid/ — same as above.")
    if not any(r.startswith("grid/input.") for r in rels):
        plan.warnings.append(
            "getPGrid inputs (input.vrt/.cel/.bnd) are missing, so the grid "
            "cannot be rebuilt on the target — the binary *.grid must load as-is.")


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #
def export_case(case_dir: str, dest_dir: str, *, dll_src_dirs=(),
                include_restart: bool | str = "auto", make_tarball: bool = False,
                solver_tag: str = ".run", log=_noop) -> dict:
    """Write a portable copy of ``case_dir`` into ``dest_dir``.

    Returns a summary dict: ``dest``, ``tarball``, ``plan``, ``n_files``,
    ``bytes``. Raises :class:`CaseExportError` if nothing can be written.
    """
    plan = plan_export(case_dir, dll_src_dirs=dll_src_dirs,
                       include_restart=include_restart)
    if not plan.items:
        raise CaseExportError(
            f"{case_dir} holds no input files to export (only outputs?)")

    dest_dir = os.path.abspath(dest_dir)
    if _is_inside(dest_dir, plan.case_dir):
        raise CaseExportError(
            "the export folder cannot sit inside the case it is exporting")
    # ...nor CONTAIN it. Naming results/solver as the target while exporting
    # results/solver/naca_run passed the check above and wrote grid/, work/, run_case.sh
    # and MANIFEST.txt straight into the shared cases directory — and with the tarball
    # option, archived every other case's output along with them. That is the "ship a
    # result set nobody asked for" outcome this module exists to prevent, arrived at from
    # the other direction.
    if _is_inside(plan.case_dir, dest_dir):
        raise CaseExportError(
            "the export folder cannot contain the case it is exporting "
            f"({plan.case_dir} is inside {dest_dir}) — pick a folder beside it or "
            "somewhere else entirely")
    try:
        os.makedirs(dest_dir, exist_ok=True)
        for item in plan.items:
            target = os.path.join(dest_dir, *item.rel.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(item.src, target)
        _write_input_in(plan, dest_dir)
        _write_run_script(plan, dest_dir, solver_tag)
        manifest = _manifest_text(plan, solver_tag)
        with open(os.path.join(dest_dir, "MANIFEST.txt"), "w", encoding="utf-8") as f:
            f.write(manifest)
    except OSError as e:
        raise CaseExportError(f"could not write the export: {e}") from e

    log(f"[export] {len(plan.items)} file(s), {human_size(plan.total_bytes)} "
        f"-> {dest_dir}")
    for w in plan.warnings:
        log(f"[export] WARNING: {w}")

    tarball = ""
    if make_tarball:
        tarball = dest_dir.rstrip(os.sep) + ".tar.gz"
        try:
            with tarfile.open(tarball, "w:gz") as tf:
                tf.add(dest_dir, arcname=os.path.basename(dest_dir))
        except OSError as e:
            raise CaseExportError(f"could not write {tarball}: {e}") from e
        log(f"[export] archive -> {tarball} ({human_size(_size(tarball))})")

    return {"dest": dest_dir, "tarball": tarball, "plan": plan,
            "n_files": len(plan.items), "bytes": plan.total_bytes}


def _write_input_in(plan: ExportPlan, dest_dir: str) -> None:
    """Copy input.in with its off-machine paths rewritten to local ones."""
    if not plan.rewrites:
        return
    target = os.path.join(dest_dir, "work", "input.in")
    if not os.path.isfile(target):
        return
    with open(target, encoding="utf-8", errors="replace") as f:
        text = f.read()
    for raw, new in plan.rewrites.items():
        text = text.replace(f'"{raw}"', f'"{new}"')
    with open(target, "w", encoding="utf-8") as f:
        f.write(text)
