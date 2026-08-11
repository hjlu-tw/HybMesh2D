"""Package a solver case that ran here into a folder that runs THERE.

A case under ``results/solver/<name>/`` mixes two kinds of file: the handful of
inputs that define the run, and the hundreds of MB of output it produced. Copying
the directory wholesale ships a result set nobody asked for; copying it by hand
loses whichever input was not on the person's mental list. This module makes the
selection explicit.

What ships (an ALLOW-list, so an output can never sneak in by being new):

* ``grid/``  — the mesh the solver reads (``*.grid``/``*.bc``) plus its boundary
  table (``*.def``) and the getPGrid inputs that regenerate them
  (``input.vrt``/``.cel``/``.bnd`` + ``para.in``).
* ``work/``  — ``input.in``, the ``*.def`` table, ``phi.dat`` for an immersed
  solid, and the restart zone dump when one is present.
* ``dll/``   — the compiled ``*.so`` **and** the ``*.cc`` it came from, pulled
  from ``results/solver/dll_src`` by basename. The binary alone is not portable
  (it is this machine's arch and libstdc++); the source is what actually travels.

Anything not on the list is skipped and NAMED in the manifest, split into "known
output" and "not recognised" — a skipped input is then a visible line, not a
silent omission discovered on the far machine.

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
_WORK_KEEP = ({"input.in", "phi.dat"}, (".def", ".in"))
_DLL_KEEP = (set(), (".so", ".cc", ".cpp", ".c", ".h", ".hpp"))

_SUBDIRS = ("grid", "work", "dll")

# Quoted values in input.in are ALL file paths (see SolverConfig.generate_input_in).
_QUOTED_RE = re.compile(r'"([^"]*)"')


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
def plan_export(case_dir: str, *, dll_src_dirs=(), include_restart: bool = True) -> ExportPlan:
    """Decide what a portable copy of ``case_dir`` contains. Touches no files."""
    if not os.path.isdir(case_dir):
        raise CaseExportError(f"Not a case directory: {case_dir}")
    plan = ExportPlan(case_dir=os.path.abspath(case_dir))

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
                # restart run — carried by request, never by the allow-list.
                (plan.items.append(ExportItem(src, rel, "restart zone dump"))
                 if include_restart else
                 plan.skipped_output.append((rel, _size(src))))
                continue
            if _keeps(name, keeps[sub]):
                plan.items.append(ExportItem(src, rel, "input"))
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

    taken = {i.rel for i in plan.items}
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
            if rel not in taken:            # referenced => an input, by definition
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
                include_restart: bool = True, make_tarball: bool = False,
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
    try:
        os.makedirs(dest_dir, exist_ok=True)
        for item in plan.items:
            target = os.path.join(dest_dir, *item.rel.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(item.src, target)
        _write_input_in(plan, dest_dir)
        _write_run_script(plan, dest_dir, solver_tag)
        manifest = _manifest_text(plan, solver_tag)
        with open(os.path.join(dest_dir, "MANIFEST.txt"), "w") as f:
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
    with open(target, "w") as f:
        f.write(text)


_RUN_SCRIPT = """#!/bin/sh
# Run this case on this machine. Written by HybMesh2D's portable-case export.
#
#   ./run_case.sh              run the solver on the grid included here
#   ./run_case.sh --regrid     rebuild <case>.grid/.bc from the STAR-CD inputs
#                              first (needed when the included binary grid was
#                              written by a different architecture)
#
# Binaries are NOT included. Put unicones / getPGrid on PATH, or point these at
# them:  UNICONES=/path/to/unicones GETPGRID=/path/to/getPGrid ./run_case.sh
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
UNICONES=${UNICONES:-unicones}
GETPGRID=${GETPGRID:-getPGrid}
TAG=${TAG:-%(tag)s}

if [ "$1" = "--regrid" ]; then
    echo "[run_case] regenerating the grid with $GETPGRID"
    cd "$HERE/grid" && "$GETPGRID" < para.in
    cd "$HERE"
fi

%(dll_block)scd "$HERE/work"
echo "[run_case] $UNICONES -t $TAG input.in"
exec "$UNICONES" -t "$TAG" input.in
"""

# Substituted INTO _RUN_SCRIPT as a value, so its '%' is not a format spec and
# must stay single (unlike the escapes in _RUN_SCRIPT itself).
_DLL_BLOCK = """# Recompile the user DLL(s): a .so built elsewhere will not load here.
if [ -n "$REBUILD_DLL" ]; then
    for src in "$HERE"/dll/*.cc; do
        [ -e "$src" ] || continue
        echo "[run_case] g++ -shared $src"
        g++ -D_INCLUDE_TEMPLATE_IMPLEMENTATION -fPIC -shared -O3 \\
            -o "${src%.cc}.so" "$src"
    done
fi

"""


def _write_run_script(plan: ExportPlan, dest_dir: str, solver_tag: str) -> None:
    has_dll = any(i.rel.startswith("dll/") for i in plan.items)
    text = _RUN_SCRIPT % {"tag": solver_tag,
                          "dll_block": _DLL_BLOCK if has_dll else ""}
    path = os.path.join(dest_dir, "run_case.sh")
    with open(path, "w") as f:
        f.write(text)
    os.chmod(path, 0o755)


def _manifest_text(plan: ExportPlan, solver_tag: str) -> str:
    L = [f"Portable solver case: {os.path.basename(plan.case_dir)}",
         f"Exported from: {plan.case_dir}",
         "",
         "Run it:  ./run_case.sh          (unicones / getPGrid must be on PATH)",
         "         ./run_case.sh --regrid (rebuild the grid from the STAR-CD inputs)",
         "",
         f"INCLUDED ({len(plan.items)} file(s), {human_size(plan.total_bytes)})",
         "-" * 66]
    for item in sorted(plan.items, key=lambda i: i.rel):
        L.append(f"  {item.rel:<44} {human_size(_size(item.src)):>9}  {item.reason}")
    if plan.rewrites:
        L += ["", "PATHS REWRITTEN IN work/input.in (they pointed off this machine)",
              "-" * 66]
        for raw, new in sorted(plan.rewrites.items()):
            L.append(f"  {raw}  ->  {new}")
    if plan.skipped_output:
        total = sum(s for _, s in plan.skipped_output)
        L += ["", f"SKIPPED — produced by the run ({human_size(total)})", "-" * 66]
        L += [f"  {r:<44} {human_size(s):>9}" for r, s in plan.skipped_output]
    if plan.skipped_other:
        L += ["", "SKIPPED — not recognised as a solver input; check whether the "
              "run needs one", "-" * 66]
        L += [f"  {r:<44} {human_size(s):>9}" for r, s in plan.skipped_other]
    if plan.warnings:
        L += ["", "WARNINGS", "-" * 66] + [f"  ! {w}" for w in plan.warnings]
    L += ["", "NOTES",
          "-" * 66,
          "  * The solver binary is deliberately NOT included.",
          "  * dll/*.so was built on the exporting machine. On a different "
          "architecture,",
          "    rebuild with:  REBUILD_DLL=1 ./run_case.sh",
          "  * grid/*.grid is c_binary. If the solver rejects it, regenerate "
          "with --regrid.",
          f"  * Output is tagged '{solver_tag}' "
          f"(work/xtecp_sol_allz.dat{solver_tag}).",
          ""]
    return "\n".join(L)
