"""Does THIS run actually use that file?

Split out of ``services/case_export`` (which was at the GUI file-size budget).
That module decides what a case *contains* from the filesystem layout; this one
answers the question its allow-list cannot, because the allow-list matches on
NAME alone: ``work/phi.dat`` and everything under ``dll/`` are legitimate inputs
for one run and fossils of an earlier one for the next.

The authority is ``work/input.in`` — the file the far machine actually runs. It
declares ``immersed_solid`` and it names every shared object it dlopens by
quoted path, so "is this an input?" is a fact read off the case rather than a
guess. USER-REPORTED (2026-08-12): "I didn't configure IBM, why is there a
phi.dat and a dll/?" — ``prepare_case_dir`` reuses a case directory in place, so
both survive a re-run without an immersed solid.

Qt-free, like the rest of the export services.
"""
from __future__ import annotations

import os
import re

# Quoted values in input.in are ALL file paths (see SolverConfig.generate_input_in).
_QUOTED_RE = re.compile(r'"([^"]*)"')

# The immersed solid is declared in input.in itself, which makes "does this run
# read phi.dat?" a fact. Read off the file, so a hand-edited input.in is obeyed.
_IMMERSED_RE = re.compile(r"^\s*immersed_solid\s+true\b", re.IGNORECASE | re.MULTILINE)


def input_in_text(case_dir: str) -> str:
    """``work/input.in`` as text, or "" when it cannot be read."""
    try:
        with open(os.path.join(case_dir, "work", "input.in"),
                  encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def declares_immersed_solid(input_in: str) -> bool:
    """Whether this run turns the immersed solid on — the phase field's reader."""
    return _IMMERSED_RE.search(input_in) is not None


def loaded_shared_objects(case_dir: str) -> set:
    """Basenames of the ``*.so`` this run actually dlopens.

    Every DLL reference is a quoted path: ``init_cond_use_zdump_fn`` /
    ``SolidPhaseMotionDLL`` in ``input.in``, and a type-11 (user BC) row's
    ``"./name.so"`` in the ``*.def`` staged next to it — so a BC DLL counts as
    loaded even though ``input.in`` alone never mentions it.
    """
    text = input_in_text(case_dir)
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


def unused_reason(sub: str, name: str, loaded_so: set, immersed: bool) -> str:
    """Why an allow-listed file is no part of THIS run — "" when it is part of it.

    ``work/phi.dat`` and everything in ``dll/`` are kept by NAME, and a reused case
    directory (``prepare_case_dir`` writes in place) still holds both long after the
    immersed-solid run that produced them: fossils presented as "input" that the
    exported ``input.in`` never reads. That same ``input.in`` answers it — it
    declares ``immersed_solid`` (the phase field's only reader is the init DLL, so
    with neither a declaration nor a DLL nothing touches ``phi.dat``) and it names
    every DLL it loads. A source travels with its own ``.so``
    (``case_export._add_dll_sources``); a header travels with whatever source
    ships, since it is the rebuild that needs it.
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
