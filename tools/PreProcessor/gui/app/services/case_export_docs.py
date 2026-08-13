"""The two documents a portable case carries: ``run_case.sh`` and ``MANIFEST.txt``.

Split out of ``services/case_export`` (which was over the file-size budget). The
selection logic lives there; this module only turns a finished
:class:`~app.services.case_export.ExportPlan` into text a person on the far
machine reads. Qt-free, like its parent.

Both documents describe the SAME package, so they are written from the same plan
and share the constants that name things — ``GETPGRID_INPUT`` in particular: a
rename that the run script does not know about would break ``--regrid`` while
the manifest cheerfully claimed it worked.
"""
from __future__ import annotations

import os

# The exported name of getPGrid's stdin input (the case's own ``para.in``).
# Defined here because both documents mention it; ``case_export`` imports it for
# its rename table so there is exactly one place it is spelled.
GETPGRID_INPUT = "getPGrid.in"

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
    cd "$HERE/grid" && "$GETPGRID" < %(getpgrid_in)s
    cd "$HERE"
fi

%(dll_block)scd "$HERE/work"
echo "[run_case] $UNICONES -t $TAG input.in"
exec "$UNICONES" -t "$TAG" input.in
"""

# Substituted INTO _RUN_SCRIPT as a value, so its '%' is not a format spec and
# must stay single (unlike the escapes in _RUN_SCRIPT itself).
#
# The compiler is a SUGGESTION, not a decision: this package is meant for
# someone else's machine, and plenty of HPC sites build with icpc/icpx/nvc++ and
# their own flags. CXX/CXXFLAGS are the names such a person already expects, so
# the default is g++ and overriding it needs no edit to this file.
_DLL_BLOCK = """# Recompile the user DLL(s): a .so built elsewhere will not load here.
#   REBUILD_DLL=1 ./run_case.sh                 (uses g++)
#   REBUILD_DLL=1 CXX=icpc ./run_case.sh        (any C++ compiler)
#   REBUILD_DLL=1 CXX=icpc CXXFLAGS='-O2 -xHost' ./run_case.sh
# The flags below are only what the DLL API needs; add optimisation to taste.
CXX=${CXX:-g++}
CXXFLAGS=${CXXFLAGS:--O3}
if [ -n "$REBUILD_DLL" ]; then
    for src in "$HERE"/dll/*.cc; do
        [ -e "$src" ] || continue
        echo "[run_case] $CXX -shared $CXXFLAGS $src"
        "$CXX" -D_INCLUDE_TEMPLATE_IMPLEMENTATION -fPIC -shared $CXXFLAGS \\
            -o "${src%.cc}.so" "$src"
    done
fi

"""


def write_run_script(plan, dest_dir: str, solver_tag: str) -> None:
    """Write an executable ``run_case.sh`` next to the staged folders."""
    has_dll = any(i.rel.startswith("dll/") for i in plan.items)
    text = _RUN_SCRIPT % {"tag": solver_tag,
                          "getpgrid_in": GETPGRID_INPUT,
                          "dll_block": _DLL_BLOCK if has_dll else ""}
    path = os.path.join(dest_dir, "run_case.sh")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(path, 0o755)


def manifest_text(plan, solver_tag: str) -> str:
    """The package's own record: everything included, everything skipped (and
    why), every rewritten path, and the handful of facts the person running it
    on another machine has to know."""
    from app.services.case_export import _size, human_size

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
    if plan.skipped_unused:
        total = sum(s for _r, s, _w in plan.skipped_unused)
        L += ["", f"SKIPPED — in the case directory but not used by this run "
              f"({human_size(total)})", "-" * 66]
        for r, s, why in plan.skipped_unused:
            L.append(f"  {r:<44} {human_size(s):>9}")
            L.append(f"      {why}")
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
          "    Another compiler / other flags:  "
          "REBUILD_DLL=1 CXX=icpc CXXFLAGS='-O2 -xHost' ./run_case.sh",
          "    (run_case.sh defaults to g++ and hard-codes nothing else.)",
          f"  * grid/{GETPGRID_INPUT} is getPGrid's stdin input — it is the "
          "case's own para.in,",
          "    renamed here so the file says what reads it.",
          "  * grid/*.grid is c_binary. If the solver rejects it, regenerate "
          "with --regrid.",
          "  * work/binDump* is the solver's zone snapshot: an OUTPUT that a "
          "restart run reads",
          "    back. It travels only when work/input.in restarts from it "
          "(otherwise it is",
          "    listed under SKIPPED); the target does not need it to start the "
          "run from scratch.",
          f"  * Output is tagged '{solver_tag}' "
          f"(work/xtecp_sol_allz.dat{solver_tag}).",
          ""]
    return "\n".join(L)
