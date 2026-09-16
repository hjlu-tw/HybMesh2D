#!/usr/bin/env python3
"""A geometry in the mesh config is identified by its FILE, not by its spelling.

USER-REPORTED (2026-08-20), reopening an exported case package: the Mesh
Generator's geometry list showed every geometry TWICE, and Run All died with

    [ERROR] Requested geometry 'results/resampled/Untitled' could not be opened
    HYBMESH_ERROR 3 GEOMETRY_LOAD results/resampled/Untitled

Three defects behind that, each pinned below:

 1. IDENTITY. ``geom_files`` was keyed by the raw string, and every dedup guard
    in the tree was a ``not in`` string compare, so ``results/x.dat`` and
    ``/repo/results/x.dat`` were two entries for one file. The mesher was handed
    the same geometry twice (measured: two identical GEOM_FILE lines), which is a
    doubled boundary, not just an untidy list.

 2. BASE. A relative entry was resolved with ``os.path.abspath``, i.e. against
    the PROCESS CWD. Measured: the same entry resolved to
    ``<repo>/results/...`` when launched from the repo root and to
    ``/private/tmp/results/...`` from /tmp. ``repo_root()`` was already right
    there in the same function, used for relativising OUTPUT only.

 3. HONESTY. An entry naming a file that does not exist was warned about in the
    diagnostic scan and then written into the mesher config anyway. Dropping it
    silently would be worse (a mesh quietly missing a body looks converged), so
    the run must REFUSE and name the file.

 4. REACH (#99). The check 7 scan that gates the above forbade
    ``append``/``remove``/``in`` and could not see ``cfg.geom_files = [...]`` --
    the wholesale rebind, which is BOTH the pre-fix shape and what
    ``remove_geom_file`` does internally. Five callers outside the mixin were
    still using it, so the defect had an unwatched door back in. The scan now
    watches every list mutation, the rebind, a slice rebind and a ``del``;
    callers replace the list through ``MeshConfig.set_geom_files``; and the
    allow-list is DERIVED from where the verbs are defined rather than naming a
    file.

 5. RESIDUE (#104). One canonicalisation rule, written three times -- the add
    path re-derived the canonical key the membership verb beside it already
    answers, and both restated the dedupe helper's loop. The identity import was
    function-local where no cycle required it. And two callers still STORED what
    ``os.path.abspath`` returned, i.e. the cwd-relative spelling defect 2 is
    about: nothing was broken, because every comparison canonicalises, but a
    rule its own callers contradict is how the first defect got in. Checks 8
    and 9, each shown to fail the BUILD like the doors above.

 6. THE READ SIDE (#111). The write side got ``stored_geom_path`` and the
    sidecar side ``meta_io.meta_path_for``; the side that OPENS the file got
    neither, so five readers across three layers each answered "canonicalise,
    then find out whether there is anything to open" for themselves -- four with
    ``os.path.exists`` on the canonical path, the BC overlay by letting the open
    itself fail -- and the symptom of getting it wrong is a preview that silently
    does not draw. ``readable_geom_path`` is that one question, and check 11 asks
    it from a foreign cwd.

 7. REACH ON THE READ SIDE (#112). A verb with no scan is a rule the sixth
    reader can be written around, which is what happened on the store side
    twice. Check 12 fails the build on both shapes the converted readers used
    to be: canonicalise-then-ask-the-filesystem, and a raw ``geom_files`` entry
    handed to it. The first is banned by the QUESTION rather than by the shape
    -- only when the canonicalised entry is used nowhere but the branch where
    the file turned out to be there -- because three sites in one controller
    need that path precisely WHEN the file is absent, and a gate that
    red-lights three correct sites to find one real one gets worked around.

 8. THE SECOND VERB, AND THE PROBE (#119). Two holes #108 left, neither of them
    visible from the ticket that made it. Check 12 recognised canonicalisation
    by ONE name while the identity module had exported a second canonicalising
    verb since #110, so the banned shape written through
    ``keyed_geom_paths`` passed -- and the tree already held an instance of it.
    The verb set is MEASURED off the module now, and a reader through each is
    injected. And the injection doors were written into ``gui/app/services/``
    and removed in a ``finally``, which a killed run never reaches: they go into
    a sandbox on ``sys.path`` instead, and check 7c kills a run mid-injection
    and shows the package untouched.

Run: python3 tools/PreProcessor/tests/test_geom_files_identity.py
"""
import os
import signal
import sys
import threading
import shutil
import tempfile
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def cfg6_ok(path):
    c = MeshConfig()
    c.add_geom_file(path)
    return c


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


from app.services import geom_path_identity as gpi   # noqa: E402
from app.models.mesh_config import MeshConfig        # noqa: E402
from app.models import mesh_config_io                # noqa: E402

tmp = tempfile.mkdtemp(prefix="geom_ident_")

# ── the injection sandbox: a scanned tree that is NOT the package ────────
# The doors at the foot of this file are opened in a file this gate scans. That
# file used to be written into gui/app/services/ -- the live package -- and
# removed in a `finally`. A run killed between the write and the remove left it
# there, and the next run then measured a module the previous one abandoned.
# This repo has already paid once for exactly that shape: a stale harness backup
# silently reverted a fix that had landed (#113).
#
# So the probe is written HERE instead: a temporary directory put on sys.path
# and added to this gate's own scan roots below. The door is still opened in a
# tree the real scans walk, with the same per-file AST check and the same
# reporting, and there is nothing inside the package to leave behind rather than
# a sweep that only runs when the process survives. A child gate run is handed
# the parent's sandbox through the environment, so the process that CREATED the
# directory is the one that removes it.
_INJ_DIR_ENV = "HYBMESH_GEOM_IDENT_INJ_DIR"
_INJ_DIR = os.environ.get(_INJ_DIR_ENV) or os.path.join(tmp, "inj")
os.makedirs(_INJ_DIR, exist_ok=True)
if _INJ_DIR not in sys.path:
    sys.path.insert(0, _INJ_DIR)

#: (tree to walk, the base its findings are reported relative to). The package
#: first, so a real offender still reports as `app/...`; the sandbox second,
#: empty on every run but an injected one.
_SCAN_ROOTS = [(os.path.join(_GUI, "app"), _GUI), (_INJ_DIR, _INJ_DIR)]

# A geometry inside the repo, so the repo-relative spelling is meaningful.
rel = os.path.join("results", "resampled", "ident_probe.dat")
absolute = os.path.join(_REPO, rel)
os.makedirs(os.path.dirname(absolute), exist_ok=True)
with open(absolute, "w") as f:
    f.write("0 0\n1 0\n1 1\n0 1\n")

# ── 1. the two spellings are ONE identity ────────────────────────────────
check(gpi.canonical_geom_path(rel) == gpi.canonical_geom_path(absolute),
      "1. the repo-relative and absolute spellings canonicalise to one path")
check(gpi.same_geom_file(rel, absolute),
      "1. ...so same_geom_file says they are the same geometry")
check(gpi.canonical_geom_path(absolute) == os.path.realpath(absolute),
      "1. an absolute path canonicalises to its realpath")

# ── 2. the base is the repo, NOT the process cwd ─────────────────────────
# This is the whole of defect 2: run the resolution from another directory and
# the answer must not move.
_cwd = os.getcwd()
try:
    os.chdir(tempfile.gettempdir())
    from_tmp = gpi.canonical_geom_path(rel)
finally:
    os.chdir(_cwd)
from_here = gpi.canonical_geom_path(rel)
check(from_tmp == from_here,
      f"2. a relative entry resolves the same from any cwd ({from_tmp} vs {from_here})")
check(from_tmp == os.path.realpath(absolute),
      "2. ...and that answer is the repo-relative file, not a cwd-relative one")

# ── 3. add_geom_file is the one way in, and it dedupes by identity ───────
cfg = MeshConfig()
cfg.add_geom_file(absolute)
cfg.add_geom_file(rel)
check(len(cfg.geom_files) == 1,
      f"3. adding both spellings leaves ONE entry (got {cfg.geom_files})")
cfg.add_geom_file(absolute + "/../" + os.path.basename(absolute))
check(len(cfg.geom_files) == 1,
      f"3. ...and a non-normalised spelling of it adds nothing (got {cfg.geom_files})")

other = os.path.join(_REPO, "results", "resampled", "ident_other.dat")
with open(other, "w") as f:
    f.write("0 0\n1 1\n")
cfg.add_geom_file(other)
check(len(cfg.geom_files) == 2,
      f"3. a genuinely different geometry still adds (got {cfg.geom_files})")

# ── 4. the per-geometry ROLE follows the identity ────────────────────────
# geom_roles is keyed by the path in geom_files, so canonicalising the list
# without carrying the key would silently detach every role -- a wrong BC / a
# body meshed with a boundary layer it was told not to have.
cfg2 = MeshConfig()
cfg2.geom_roles[rel] = {"role": "seed"}
cfg2.add_geom_file(absolute)
check(cfg2.is_seed(absolute) and cfg2.is_seed(rel),
      "4. a role stored under one spelling is found under the other")
cfg2.prune_roles()
check(cfg2.is_seed(absolute),
      "4. ...and prune_roles does not drop it as stale")

cfg3 = MeshConfig()
cfg3.add_geom_file(absolute)
cfg3.geom_roles[gpi.canonical_geom_path(absolute)] = {"role": "nobl"}
check(cfg3.is_nobl(rel),
      "4. a role keyed canonically answers a relative query")

# ── 5. the mesher config names each geometry ONCE ────────────────────────
cfg4 = MeshConfig()
cfg4.geom_files = [rel, absolute]        # the state a stale workspace restores
text = mesh_config_io.config_to_text(cfg4, os.path.join(tmp, "para.dat"))
geom_lines = [ln.strip() for ln in text.splitlines()
              if ln.strip().startswith("GEOM_FILE")]
check(len(geom_lines) == 1,
      f"5. two spellings of one file emit ONE GEOM_FILE line (got {geom_lines})")

# ── 6. a missing geometry is refused, by name, by BOTH hosts ────────────
# The question is filesystem state, so it is NOT inside validate() -- that stays
# a pure function of the config (a fictional filename is a legitimate fixture
# there, and test_custom_domain_validation.py uses several). It lives beside the
# config as its own named question, and both pipeline hosts must ask it: the GUI
# pre-flight AND the headless runner, or one of them keeps the bug.
gone = os.path.join(_REPO, "results", "resampled", "ident_gone.dat")
cfg5 = MeshConfig()
cfg5.add_geom_file(absolute)
cfg5.geom_files.append(gone)             # as a reopened package leaves it
miss = cfg5.geom_files_not_on_disk()
check(miss == [gone],
      f"6. geom_files_not_on_disk() names exactly the entry that is not on disk "
      f"(got {miss})")
check(not MeshConfig().geom_files_not_on_disk()
      and not cfg6_ok(absolute).geom_files_not_on_disk(),
      "6. ...and reports nothing when every geometry exists")

msg = MeshConfig.missing_geometry_message(miss)
check("ident_gone.dat" in msg and "exported case package" in msg,
      "6. one wording, naming the file and why a reopened package has one")

errs, _ = cfg5.validate()
check(not [e for e in errs if "ident_gone" in e],
      f"6. validate() stays PURE -- it does not touch the filesystem (got {errs})")

# Both hosts ask, by source. A refusal wired into one host only is the exact
# asymmetry that made the IB hand-off a bug (see services/ib_handoff).
gui_src = open(os.path.join(_GUI, "app", "controllers",
                            "mesh_gen_ctrl.py")).read()
run_src = open(os.path.join(_GUI, "app", "services",
                            "pipeline_runner.py")).read()
check("geom_files_not_on_disk()" in gui_src
      and "missing_geometry_message(" in gui_src,
      "6. the GUI mesh pre-flight asks, and uses the shared wording")
check("geom_files_not_on_disk()" in run_src
      and "missing_geometry_message(" in run_src,
      "6. the headless runner asks too, with the same wording")
# ...and the headless one is DRIVEN, not just read: it is the host whose refusal
# was never exercised by hand, and a source match cannot tell a live check from a
# dead one.
from app.services import pipeline_runner            # noqa: E402
from app.models.pipeline_config import PipelineConfig  # noqa: E402

pcfg = PipelineConfig()
pcfg.name = "ident_probe_case"
try:
    pipeline_runner._run_mesh(pcfg, _REPO, [absolute, gone],
                              need_starcd=False, log=lambda *a, **k: None)
    check(False, "6. the headless _run_mesh REFUSES a missing geometry (it did not)")
except pipeline_runner.PipelineError as e:
    check("ident_gone.dat" in str(e),
          f"6. the headless _run_mesh refuses and names the file ({e})")
except Exception as e:  # a different failure would hide the one under test
    check(False, f"6. headless _run_mesh raised something else: {type(e).__name__}: {e}")

check("Geometry file missing" not in gui_src,
      "6. and the old [WARNING]-then-mesh-anyway line is gone -- a warning "
      "beside a fatal condition reads as 'it went ahead'")

# ── 7. the one way in is the ONLY way in, statically ──────────────────────
# The first round of this work converted the six ADD sites and left the removals
# and the membership tests comparing strings, several of them the very
# os.path.abspath this module's docstring condemns. The result was worse than
# before it started: mesh_layers_ctrl added a layer by identity and un-added it
# by string, so on a config holding the repo-relative spelling (what a loaded
# workspace or exported case package carries) the checkbox cleared while the
# geometry stayed in the mesh. Reviewing found it; nothing in the tree could.
#
# So the rule is gated the way this repo gates its other "no second copy" rules
# (test_output_format_placeholder.py): any NEW raw string mutation or membership
# test over geom_files fails the build. By AST, not substring — the prose above
# names every construct it forbids.
#
# #99 widened it to the constructs listed in defect 4 above. The replace verb
# callers are left with is MeshConfig.set_geom_files; the mixin keeps the rebind,
# which is what the derived allow-list exempts and the negative control proves.
import ast                                                        # noqa: E402
import inspect                                                    # noqa: E402
import subprocess                                                 # noqa: E402

#: Where the model's list verbs LIVE — the allow-list is DERIVED from that, not
#: a filename list. The MODEL owns the identity rules, so the module declaring
#: the verbs is the one place that may touch geom_files as a plain list; anything
#: else must go through add/set/remove/has_geom_file, role_of or
#: dedupe_geom_paths. Deriving it is the whole point: the verbs already moved once
#: (out of mesh_config.py, when the model went over the file-size budget) and a
#: hardcoded name would have exempted the wrong file. Note what it does NOT
#: exempt today — mesh_config.py, the config class itself, whose load_from_dict
#: goes through set_geom_files like every other caller.
_RAW_OK = {
    os.path.normpath(inspect.getsourcefile(_verb)): "declares the list verbs itself"
    for _verb in (MeshConfig.add_geom_file, MeshConfig.set_geom_files,
                  MeshConfig.remove_geom_file, MeshConfig.has_geom_file)
}

#: Every list-mutating method name. Only `append` and `remove` were ever in the
#: tree; the rest are here so that "the scan watches the mutations" is a claim
#: about the operation and not about the two spellings that happened to exist
#: when it was written. Direct dunder calls (`.__setitem__`, `.__iadd__`) are
#: deliberately NOT listed and are a recorded blind spot: nobody writes them, and
#: the subscript FORMS they spell are caught below as syntax.
_LIST_MUTATORS = ("append", "remove", "extend", "insert", "pop", "clear",
                  "sort", "reverse")

#: Callees that can set the dataclass field by keyword. `MeshConfig(...)` and
#: `dataclasses.replace(cfg, ...)` are the two; the first is read off the class
#: so a rename follows, the second is a stdlib name that will not move.
_CONFIG_BUILDERS = frozenset({MeshConfig.__name__, "replace"})


def _callee_name(node: ast.Call):
    """The name being CALLED, whether it is reached through an attribute or
    not: ``os.path.exists(...)``, ``path.exists(...)`` and a bare imported
    ``exists(...)`` are one answer. Shared by all four scans below, which each
    used to spell it inline."""
    f = node.func
    return f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)


def _is_geom(node) -> bool:
    """``<anything>.geom_files`` -- the attribute, not what it is used for."""
    return isinstance(node, ast.Attribute) and node.attr == "geom_files"


def _raw_geom_file_sites(path: str) -> list[tuple[int, str]]:
    """(line, construct) for every raw list mutation/membership/rebind over
    ``*.geom_files`` in one file. Reads what the code DOES, so a rename or a
    reflowed line cannot make a violation invisible the way a grep could."""
    tree = ast.parse(open(path).read())
    out = []

    def _leaf_targets(t):
        """Unpack `a, cfg.geom_files = ...` so a tuple target cannot hide one."""
        if isinstance(t, (ast.Tuple, ast.List)):
            for e in t.elts:
                yield from _leaf_targets(e)
        else:
            yield t

    for n in ast.walk(tree):
        # x.geom_files.append(...) / .remove(...) / .extend(...) / ...
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in _LIST_MUTATORS
                and _is_geom(n.func.value)):
            out.append((n.lineno, f"geom_files.{n.func.attr}()"))
        # `p in x.geom_files` / `p not in x.geom_files`
        if isinstance(n, ast.Compare):
            for op, cmp in zip(n.ops, n.comparators):
                if isinstance(op, (ast.In, ast.NotIn)) and _is_geom(cmp):
                    out.append((n.lineno, "`in` over geom_files"))
        # x.geom_files = [...] / += / x.geom_files[:] = [...]  (#99)
        if isinstance(n, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            _targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            for _t in _targets:
                for t in _leaf_targets(_t):
                    if _is_geom(t):
                        out.append((n.lineno, "geom_files = ... (rebind)"))
                    elif isinstance(t, ast.Subscript) and _is_geom(t.value):
                        out.append((n.lineno, "geom_files[...] = ... (slice rebind)"))
        # del x.geom_files[...]
        if isinstance(n, ast.Delete):
            for t in n.targets:
                if isinstance(t, ast.Subscript) and _is_geom(t.value):
                    out.append((n.lineno, "del geom_files[...]"))
        # Two doors the FIRST widening still walked past, both found by review
        # rather than by the scan -- which is the whole lesson of this check.
        if isinstance(n, ast.Call):
            # MeshConfig(geom_files=[...]) / dataclasses.replace(cfg,
            # geom_files=[...]): geom_files is a real dataclass field, so the
            # CONSTRUCTOR is a way in that no assignment and no method call
            # appears at. Scoped to the callees that can actually REACH that
            # field, because nine functions in this tree take a parameter of the
            # same name for an ordinary file list -- a gate that fails on
            # `audit_mesh_bc(bnd, geom_files=...)` gets worked around, not
            # obeyed. The class name is taken from the class, so a rename of the
            # model follows without an edit here.
            _callee = _callee_name(n)
            if _callee in _CONFIG_BUILDERS:
                for kw in n.keywords:
                    if kw.arg == "geom_files":
                        out.append((n.lineno,
                                    f"geom_files= keyword to {_callee}()"))
            # setattr(cfg, "geom_files", [...]) -- a LITERAL name is a plain
            # rebind spelled sideways. A computed name stays a blind spot; this
            # is the same line config_ownership._targets already draws.
            if (isinstance(n.func, ast.Name) and n.func.id == "setattr"
                    and len(n.args) >= 2
                    and isinstance(n.args[1], ast.Constant)
                    and n.args[1].value == "geom_files"):
                out.append((n.lineno, 'setattr(..., "geom_files", ...)'))
    return out


def _scanned_files() -> list[tuple[str, str]]:
    """``(file, the base its findings are reported relative to)`` for every file
    these scans read. Separate from the scan below so that "the package really is
    the tree this gate walks" can be CHECKED: the injection doors used to prove
    it as a side effect, and since #119 they are opened in the sandbox instead."""
    out = []
    for tree, base in _SCAN_ROOTS:
        for root, dirs, files in os.walk(tree):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            out += [(os.path.normpath(os.path.join(root, f)), base)
                    for f in sorted(files) if f.endswith(".py")]
    return out


def _scan_app_tree(sites=None, skip=None) -> list[str]:
    """Every offending site under gui/app, one run reporting all of them.

    ``sites`` is the per-file check (default: the raw-construct scan of check 7);
    ``skip`` the allow-list it exempts. Checks 8 and 9 walk the SAME tree with
    their own per-file check, so the walk itself is written once -- three copies
    of "which files does this gate look at?" is how two of them come to disagree
    about a directory."""
    sites = sites or _raw_geom_file_sites
    skip = _RAW_OK if skip is None else skip
    bad = []
    for full, base in _scanned_files():
        if full in skip:
            continue
        for ln, what in sites(full):
            bad.append(f"{os.path.relpath(full, base)}:{ln} {what}")
    return bad


_offenders = _scan_app_tree()
check(not _offenders,
      f"7. nothing outside the model mutates, tests or rebinds geom_files by "
      f"string ({_offenders})")

# The exemption is LOAD BEARING, not decoration: the allow-listed module really
# does contain a construct this scan sees, so "the real tree passes" below is a
# statement about an exemption that is doing work.
check(len(_RAW_OK) == 1
      and all(_raw_geom_file_sites(p) for p in _RAW_OK),
      f"7. the derived allow-list is one module, and it really uses the raw "
      f"constructs ({ {os.path.basename(k): _raw_geom_file_sites(k) for k in _RAW_OK} })")
check(os.path.normpath(os.path.join(_GUI, "app", "models", "mesh_config.py"))
      not in _RAW_OK,
      "7. ...and MeshConfig's own module is NOT exempt -- the reach the mixin's "
      "docstring states is the reach the allow-list has")

# ...and the check is not vacuous: it must SEE every construct it forbids.
_probe = os.path.join(tmp, "probe_raw.py")
with open(_probe, "w") as fh:
    fh.write("def f(cfg, p, q):\n"
             "    if p not in cfg.geom_files:\n"
             "        cfg.geom_files.append(p)\n"
             "    cfg.geom_files.remove(p)\n"
             "    cfg.geom_files.extend([p])\n"
             "    cfg.geom_files.insert(0, p)\n"
             "    cfg.geom_files.pop()\n"
             "    cfg.geom_files.clear()\n"
             "    cfg.geom_files.sort()\n"
             "    cfg.geom_files.reverse()\n"
             "    cfg.geom_files = [p]\n"
             "    cfg.geom_files += [p]\n"
             "    q, cfg.geom_files = 1, [p]\n"
             "    cfg.geom_files[:] = [p]\n"
             "    del cfg.geom_files[0]\n"
             "    setattr(cfg, 'geom_files', [p])\n"
             "    q = replace(cfg, geom_files=[p])\n"
             "    return MeshConfig(geom_files=[p]), q\n")
_found = {w for _ln, w in _raw_geom_file_sites(_probe)}
check(_found == {f"geom_files.{m}()" for m in _LIST_MUTATORS} | {
          "`in` over geom_files",
          "geom_files = ... (rebind)",
          "geom_files[...] = ... (slice rebind)",
          "del geom_files[...]",
          "geom_files= keyword to MeshConfig()",
          "geom_files= keyword to replace()",
          'setattr(..., "geom_files", ...)'},
      f"7. INJECTION: the scan sees every construct it forbids ({sorted(_found)})")

# The reported failure itself, end to end on the model: a config holding one
# spelling must answer, add and remove consistently for the other.
_rel = os.path.relpath(absolute, _REPO)
_cfg7 = MeshConfig()
_cfg7.geom_files = [_rel]
check(_cfg7.has_geom_file(absolute),
      "7. a geometry stored relative is FOUND by its absolute spelling "
      "(the checkbox that drew Unchecked for a geometry in the mesh)")
check(not _cfg7.add_geom_file(absolute) and _cfg7.geom_files == [_rel],
      "7. ...adding it again is a no-op that keeps the stored spelling")
check(_cfg7.remove_geom_file(absolute) and _cfg7.geom_files == [],
      "7. ...and removing by the other spelling really removes it "
      "(unchecking the box used to clear the box and keep the geometry)")
check(not MeshConfig().remove_geom_file(absolute),
      "7. ...removing from a list that does not hold the file reports that "
      "nothing went (an empty list)")
_cfg7b = MeshConfig()
_cfg7b.add_geom_file(absolute)
check(not _cfg7b.remove_geom_file(other) and _cfg7b.geom_files == [absolute],
      f"7. ...and so does removing a DIFFERENT geometry, which stays listed "
      f"(got {_cfg7b.geom_files})")

# Why remove_geom_file compares through same_geom_file instead of reading the
# shared keyer like the list-wide verbs: that keyer drops a falsy entry, which
# is right for a dedupe and would make a removal delete the empty entries
# BESIDE the one it was asked about. No writer in this tree can produce that
# state -- add_geom_file refuses a falsy path, set_geom_files drops one, and
# the mixin's own two rebinds are built from those -- so the check below is
# NOT non-vacuous against a reachable regression: it discriminates against the
# DESIGN ALTERNATIVE the two docstrings reject, which is what the line after it
# measures. It is here because that rejection is otherwise a claim no gate
# holds.
_cfg7c = MeshConfig()
_cfg7c.geom_files = [_rel, ""]
check(_cfg7c.remove_geom_file(absolute) and _cfg7c.geom_files == [""],
      f"7. removing one geometry leaves a falsy entry beside it alone -- a "
      f"removal is not a dedupe (got {_cfg7c.geom_files})")
_via_keyer = [p for key, p in gpi.keyed_geom_paths([_rel, ""])
              if key != gpi.canonical_geom_path(absolute)]
check(_via_keyer == [],
      f"7. INJECTION: the same removal written through the keyer deletes that "
      f"falsy entry as a side effect, which is the alternative the verb's "
      f"docstring rejects (got {_via_keyer})")
check(not _cfg7c.remove_geom_file("") and _cfg7c.geom_files == [""],
      f"7. ...and removing '' names no file, so it removes nothing and says so "
      f"(got {_cfg7c.geom_files})")

# set_geom_files is the REPLACE verb the widened scan leaves callers, so it must
# do the identity job a rebind did not: a rebuilt list carrying both spellings of
# one file collapses to one entry, keeping the spelling the caller gave.
_cfg8 = MeshConfig()
_cfg8.set_geom_files([_rel, absolute, other])
check(_cfg8.geom_files == [_rel, other],
      f"7. set_geom_files() dedupes a rebuilt list by identity and keeps the "
      f"caller's spelling (got {_cfg8.geom_files})")
_cfg8.set_geom_files(None)
check(_cfg8.geom_files == [],
      f"7. ...and a None/empty replacement clears it (got {_cfg8.geom_files})")

# ── 8. the identity import is at MODULE level, and no cycle requires else ─
# A deferred import hides a real dependency, which is the seam gate's own
# lesson: with `test_qt_free_seam`'s import-time sweep green, `run_pipeline.sh`
# still died on a PyQt6-less machine because three call sites imported inside a
# function body. Nothing here imports the model, so there was no cycle to defer
# around -- and "there is no cycle" is VERIFIED below rather than asserted, by
# importing the module that carried the deferred form as the FIRST thing a fresh
# interpreter does.
def _deferred_identity_imports(path: str) -> list[tuple[int, str]]:
    """(line, statement) for every ``geom_path_identity`` import nested inside a
    function or class body in one file. By AST at ANY depth, like the Qt-free
    seam's own scan -- a name is deferred whether it sits one level in or four."""
    tree = ast.parse(open(path).read())
    out = []

    def _names(node) -> bool:
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            return (mod.endswith("geom_path_identity")
                    or any(a.name == "geom_path_identity" for a in node.names))
        if isinstance(node, ast.Import):
            return any(a.name.endswith("geom_path_identity") for a in node.names)
        return False

    def _walk(node, inside: bool):
        for child in ast.iter_child_nodes(node):
            deeper = inside or isinstance(
                child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            if inside and _names(child):
                out.append((child.lineno, "deferred geom_path_identity import"))
            _walk(child, deeper)

    _walk(tree, False)
    return out


_deferred = _scan_app_tree(_deferred_identity_imports, skip=())
check(not _deferred,
      f"8. every geom_path_identity import under gui/app is at module level "
      f"({_deferred})")

_probe8 = os.path.join(tmp, "probe_deferred.py")
with open(_probe8, "w") as fh:
    fh.write("def f():\n"
             "    from app.services.geom_path_identity import canonical_geom_path\n"
             "    return canonical_geom_path\n"
             "\n"
             "class C:\n"
             "    def g(self):\n"
             "        if True:\n"
             "            from app.services import geom_path_identity\n"
             "        return geom_path_identity\n")
check(len(_deferred_identity_imports(_probe8)) == 2,
      f"8. INJECTION: the scan sees a deferred import at any depth "
      f"({_deferred_identity_imports(_probe8)})")
# ...and it is not firing on the module-level ones it must ignore, or the check
# above would be green for the wrong reason.
_probe8b = os.path.join(tmp, "probe_toplevel.py")
with open(_probe8b, "w") as fh:
    fh.write("from app.services.geom_path_identity import canonical_geom_path\n"
             "\n"
             "def f():\n"
             "    return canonical_geom_path\n")
check(not _deferred_identity_imports(_probe8b),
      "8. ...and a module-level import is NOT reported")

# The cycle: MEASURED, not assumed. mesh_config_io is the module whose import
# was deferred, and it is on the HEADLESS path (run_pipeline.sh / run_batch.sh),
# so the same run says it still drags in no Qt.
_cyc = subprocess.run(
    [sys.executable, "-c",
     "import sys; sys.path.insert(0, %r);"
     "import app.models.mesh_config_io as m;"
     "print('QT' if 'PyQt6' in sys.modules else 'NOQT')" % _GUI],
    capture_output=True, text=True)
check(_cyc.returncode == 0,
      f"8. mesh_config_io imports FIRST in a fresh interpreter -- no cycle "
      f"requires the deferred form (exit {_cyc.returncode}: "
      f"{_cyc.stderr.strip()[:200]})")
check("NOQT" in _cyc.stdout,
      f"8. ...and hoisting it drags no Qt onto the headless path ({_cyc.stdout.strip()})")

# ── 9. what is STORED is never a cwd-relative spelling ────────────────────
# The rule the module states -- "the base is the repo, never the process cwd" --
# was contradicted by its own callers: they resolved with os.path.abspath and
# stored THAT as the entry. Nothing was broken, because every comparison
# canonicalises, but a stored `<cwd>/results/...` stops naming the same file the
# moment the GUI is launched from somewhere else. stored_geom_path is the answer
# to "how is the entry written down?", and it is repo-relative -- the spelling
# the config writer emits.
_cwd = os.getcwd()
try:
    os.chdir(tempfile.gettempdir())
    _stored_from_tmp = gpi.stored_geom_path(rel)
    _outside_from_tmp = gpi.stored_geom_path(os.path.join(tmp, "elsewhere.dat"))
finally:
    os.chdir(_cwd)
check(_stored_from_tmp == rel and gpi.stored_geom_path(absolute) == rel,
      f"9. a geometry inside the repo is STORED repo-relative, from any cwd and "
      f"from either spelling (got {_stored_from_tmp!r} / "
      f"{gpi.stored_geom_path(absolute)!r}, want {rel!r})")
check(os.path.isabs(_outside_from_tmp)
      and _outside_from_tmp == gpi.canonical_geom_path(os.path.join(tmp, "elsewhere.dat")),
      f"9. a geometry OUTSIDE the repo is stored absolute, not cwd-relative "
      f"({_outside_from_tmp})")
check(gpi.same_geom_file(gpi.stored_geom_path(absolute), absolute)
      and gpi.stored_geom_path("") == "",
      "9. ...and re-spelling an entry never changes which FILE it names")

# The callers, statically: no geometry reaches the list through the cwd-relative
# call. Scoped to the model's two ADD/REPLACE verbs, so an os.path.abspath used
# for anything else (the recent-files list is one) is not swept up.
_STORE_VERBS = ("add_geom_file", "set_geom_files")


def _cwd_relative_stores(path: str) -> list[tuple[int, str]]:
    """(line, construct) for every ``add_geom_file(os.path.abspath(...))`` -- the
    cwd-relative call feeding the model's own store verb, directly or inside a
    list literal."""
    tree = ast.parse(open(path).read())
    out = []

    def _is_abspath(node) -> bool:
        return isinstance(node, ast.Call) and _callee_name(node) == "abspath"

    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in _STORE_VERBS):
            continue
        args = list(n.args)
        for a in list(args):
            if isinstance(a, (ast.List, ast.Tuple)):
                args.extend(a.elts)
        if any(_is_abspath(a) for a in args):
            out.append((n.lineno, f"{n.func.attr}(os.path.abspath(...))"))
    return out


_stores = _scan_app_tree(_cwd_relative_stores, skip=())
check(not _stores,
      f"9. no caller stores the cwd-relative spelling into geom_files ({_stores})")

# The READ side of the same rule, where it has a seam rather than a scan: a
# `.meta` sidecar belongs to the FILE. Nine call sites across the panels, the
# layer controller and the .bnd audit reach a sidecar, and every one goes
# through meta_io.meta_path_for -- so this is driven end to end from a FOREIGN
# cwd, which is the condition under which the raw string is wrong. The write is
# the half that matters most: it used to be able to leave a stray tree beside
# wherever the GUI was launched from, with the real sidecar still holding the
# old BCs.
from app.services import meta_io                       # noqa: E402

# The sidecar the C++ resampler would have left beside the geometry.
with open(absolute + ".meta", "w") as fh:
    fh.write("HYBMESH_META 2\nCOUNT 4\nNSEGMENTS 1\n1 inflow line\n"
             "POINTS 4\n1 0\n1 0\n1 0\n1 0\n")

_cwd = os.getcwd()
_stray = os.path.join(tmp, "stray_cwd")
os.makedirs(_stray, exist_ok=True)
try:
    os.chdir(_stray)
    _wrote = meta_io.write_meta_group_bc(rel, {"inflow": "inlet"})
    _read_back = meta_io.read_meta_group_bc(rel)
finally:
    os.chdir(_cwd)
check(_wrote and _read_back == {"inflow": "inlet"},
      f"9. a .meta sidecar round-trips through the REPO-relative spelling from a "
      f"foreign cwd (wrote={_wrote}, read={_read_back})")
check(meta_io.read_meta_group_bc(absolute) == {"inflow": "inlet"},
      "9. ...and the other spelling of the same file reads the same sidecar")
check(not os.path.exists(os.path.join(_stray, "results")),
      f"9. ...and nothing was written under the process cwd "
      f"({os.listdir(_stray)})")
try:
    os.remove(absolute + ".meta")
except OSError:
    pass

_probe9 = os.path.join(tmp, "probe_store.py")
with open(_probe9, "w") as fh:
    fh.write("import os\n"
             "\n"
             "def f(cfg, p):\n"
             "    cfg.add_geom_file(os.path.abspath(p))\n"
             "    cfg.set_geom_files([os.path.abspath(p)])\n"
             "    cfg.add_geom_file(stored_geom_path(p))\n"
             "    return os.path.abspath(p)\n")
check(len(_cwd_relative_stores(_probe9)) == 2,
      f"9. INJECTION: the scan sees the cwd-relative call at BOTH store verbs, "
      f"and leaves an unrelated abspath alone ({_cwd_relative_stores(_probe9)})")

# ── 10. what routing the RESTORE through the verb actually changed ───────
# load_from_dict used to rebind: `self.geom_files = d.get("geom_files") or []`.
# Routing it through set_geom_files (#99) changed three things no test asserted
# (a fourth, the JSON null, the rebind already handled and is asserted last)
# -- they arrived as a consequence of the routing and were described in a
# comment, which is the shape this repo keeps having to close. All three are
# right for a STALE WORKSPACE, which is exactly the dict that carries one file
# under two spellings (the panel computed the absolute one, the saved file kept
# the relative one). Asserted through the model's public restore API, and each
# one shown non-vacuous by the bypass below.
def _bypass_restore(d: dict) -> MeshConfig:
    """The pre-#99 restore: the raw rebind, on the real model.

    Not a stub -- a MeshConfig carrying the one line the routing replaced, so
    "the verb is what makes these three true" is measured rather than claimed.
    """
    c = MeshConfig()
    c.geom_files = d.get("geom_files") or []
    return c


_dup_ws = {"geom_files": [_rel, absolute]}
_c10 = MeshConfig()
_c10.load_from_dict(_dup_ws)
check(_c10.geom_files == [_rel],
      f"10. restoring a workspace that lists one file under two spellings "
      f"yields ONE entry, the saved spelling (got {_c10.geom_files})")
check(_bypass_restore(_dup_ws).geom_files == [_rel, absolute],
      "10. INJECTION: the rebind it replaced restores BOTH, so the check above "
      "is about the verb and not about the fixture")

_stale_ws = {"geom_files": [_rel, None, "", other]}
_c10b = MeshConfig()
_c10b.load_from_dict(_stale_ws)
check(_c10b.geom_files == [_rel, other],
      f"10. a null or empty entry in a saved workspace is DROPPED, not restored "
      f"as a nameless geometry (got {_c10b.geom_files})")
check(_bypass_restore(_stale_ws).geom_files == [_rel, None, "", other],
      "10. INJECTION: the rebind restores them, so that check is the verb's too")

_alias_ws = {"geom_files": [_rel]}
_c10c = MeshConfig()
_c10c.load_from_dict(_alias_ws)
_c10c.add_geom_file(other)
_alias_ws["geom_files"].append(gone)
check(_alias_ws["geom_files"] == [_rel, gone] and _c10c.geom_files == [_rel, other],
      f"10. the restored list is a COPY: mutating either side leaves the other "
      f"alone (dict={_alias_ws['geom_files']}, cfg={_c10c.geom_files})")
_aliased = {"geom_files": [_rel]}
_c10d = _bypass_restore(_aliased)
_c10d.add_geom_file(other)
check(_aliased["geom_files"] == [_rel, other],
      f"10. INJECTION: the rebind ALIASED the dict's own list -- adding to the "
      f"config appended to the caller's list (got {_aliased['geom_files']})")

# The fourth consequence the comment beside the call names. NO injection is
# claimed for this one: the rebind's own `or []` got it right too, so the
# bypass agrees -- and saying so is the point, since three of the four are the
# verb's and one is not.
_null_ws = {"geom_files": None}
_c10e = MeshConfig()
_c10e.load_from_dict(_null_ws)
check(_c10e.geom_files == [] == _bypass_restore(_null_ws).geom_files,
      f"10. a JSON null for the whole list restores as [] -- the one of the "
      f"four the rebind also got right (got {_c10e.geom_files})")

# ── 11. the READ side is one verb too ────────────────────────────────────
# The FIVE readers that OPEN a geometry (the mesh bbox scan, the preview loader
# thread, the BC overlay, the selection highlight and the mesh panel's
# auto-sizing hint reader) each answered "canonicalise the entry, then find out
# whether there is anything to open" for themselves -- three with os.path.exists
# on the canonical path, the BC overlay and the hint scans by letting np.loadtxt
# fail into their skip. The Run-All readiness check and
# mesh_layers_ctrl.add_all_sessions_to_mesh ask the same question and open
# nothing, which is what makes SEVEN callers and not five (#117: this comment was
# the fourth home of a "five ... that OPEN" count that included the readiness
# check; #118 converted the fifth reader and moved both numbers again).
# readable_geom_path is that question, asked once. Driven from a FOREIGN cwd,
# because that is the only condition under which the two spellings disagree.
#
# The raw form is measured beside it as a FIXTURE CONTROL, not an injection: it
# shows this fixture is one where the two answers differ, so the assertion above
# it could fail. What makes the check non-vacuous about the VERB is the
# mutation, run separately (#111): rewriting the body to os.path.abspath exits 1
# with the first assertion below the first FAIL.
_cwd = os.getcwd()
try:
    os.chdir(tempfile.gettempdir())
    _readable_from_tmp = gpi.readable_geom_path(_rel)
    _raw_from_tmp = os.path.exists(_rel)
    _missing_from_tmp = gpi.readable_geom_path(
        os.path.relpath(gone, _REPO))
finally:
    os.chdir(_cwd)
check(_readable_from_tmp == gpi.canonical_geom_path(absolute),
      f"11. a repo-relative entry reads back as the file it names, from any cwd "
      f"(got {_readable_from_tmp!r})")
check(not _raw_from_tmp,
      f"11. FIXTURE CONTROL: the raw form the readers used to carry answers "
      f"FALSE for that same entry from that same cwd, so the check above is one "
      f"the fixture could fail (os.path.exists({_rel!r}) -> {_raw_from_tmp})")
check(_missing_from_tmp == "" and gpi.readable_geom_path(gone) == "",
      f"11. an entry naming a file that is not on disk reads back as \"\", the "
      f"same answer a falsy entry gets (got {_missing_from_tmp!r})")
check(gpi.readable_geom_path("") == "",
      "11. ...and a falsy entry is answered without a separate emptiness test, "
      "as the shared derivation answers it")

# ── 12. the READ side has a SCAN as well as a verb ───────────────────────
# Check 11 holds what readable_geom_path ANSWERS. It says nothing about who
# ASKS: the sixth reader can still be written the way the first five were, and
# the symptom is silent -- a repo-relative entry resolved against the process
# cwd, and a preview that simply does not draw. Both previous sweeps on this
# rule (#99, #104) had a review find sites they had missed, so the reach is
# known rather than assumed.
#
# TWO shapes, both of them exactly what the converted readers used to be:
#
#  (a) canonicalise, then ask the filesystem -- os.path.exists(
#      canonical_geom_path(p)), or the same over a local bound from it. That is
#      readable_geom_path written out by hand.
#  (b) a RAW geom_files entry handed to the filesystem -- `for gf in
#      cfg.geom_files: np.loadtxt(gf)`, the reader the rule file's blind spot
#      named. A stored entry is a repo-relative SPELLING, so this one resolves
#      it against the process cwd.
#
# Shape (a) cannot be banned outright, and the measurement that says so was
# taken against the tree BEFORE this check was written (#112, an AST walk at
# #111): mesh_layers_ctrl.py carried FIVE canonicalise-then-exists sites and
# only ONE was this defect. THREE of the other four need the canonical path
# precisely WHEN the file is absent -- it goes into the refusal message
# (add_active_preprocessor_geometry), onto the "(not exported)" label with the
# membership test and the item data, and onto the "missing file" tag by basename
# (both in sync_mesh_layers_panel) -- and "" is the one answer that destroys what
# they need. The fifth re-tests a path taken from the widget's item data
# (handle_mesh_layer_toggled), with no canonicalising call feeding it at all, so
# the scan below never reaches it: the ticket counted it among the four a shape
# ban would red-light because it was measured FILE-scoped, and the scan that
# shipped is function-scoped, which is why the number here is THREE. Either way
# a gate that red-lights correct sites to find one real one gets worked around
# rather than obeyed, and the escape hatch it would need -- "these files are
# fine" -- is the growing filename list the derived allow-lists exist to avoid.
#
# So the ban is on the QUESTION, not on the shape: an existence call on a
# canonicalised entry is a violation only when that entry is used NOWHERE but
# the branch where the file turned out to be there. That is "use it only if it
# is there", which is readable_geom_path's question and nothing else's. Uses
# inside the guard's own test do not count -- `canon and os.path.exists(canon)`
# is one question, not two -- which is why the verb's own body is a violation
# and its exemption is load bearing. A call that READS (open, loadtxt, ...)
# needs no such discrimination: it presupposes the answer.
#
# And "canonicalise" is more than ONE verb (#119). This check shipped
# recognising the single name it was written for -- #110 had already made
# keyed_geom_paths the module's second public canonicalising verb -- so
# the banned shape written through the second one was invisible, with an
# instance of it already sitting in the tree. The set is MEASURED off the module
# now, so a third verb needs no edit here. The list-wide verbs answer with a
# SEQUENCE rather than a path, which is why a loop target binds as well as an
# assignment and why a comprehension's `if` is read as a guard; and the tree's
# own instance -- the model's geom_files_not_on_disk -- stays green through the
# discrimination above rather than through a pin, because it asks which entries
# are NOT there.

#: The filesystem calls this tree asks about a geometry path, split by the
#: question they answer. The existence half is what readable_geom_path absorbs
#: (four of #111's five readers spelled it os.path.exists); the read half is how
#: the fifth asked it -- np.loadtxt, letting the failure be the answer. Matched
#: by attribute name, so `os.path.exists`, `path.exists` and a bare imported
#: `exists` are one entry, and `np.loadtxt` needs no import to be recognised.
_EXISTENCE_CALLS = ("exists", "isfile", "lexists", "access")
_READ_CALLS = ("open", "loadtxt", "genfromtxt", "stat", "getsize", "getmtime")

#: Derived from the verb, like _RAW_OK: the module that DEFINES the read side is
#: the one place that may canonicalise and then ask the filesystem, because that
#: is the question it exists to answer. Read off the FUNCTION, so moving it moves
#: the exemption with it. ONE verb is named, not both halves of the module:
#: canonical_geom_path sits beside it today, and a module holding only that one
#: would contain none of the calls below anyway -- os.path.realpath is not one of
#: them -- so naming it too would exempt a module with nothing to exempt, which
#: is exactly what the load-bearing check underneath refuses.
_READ_OK = {
    os.path.normpath(inspect.getsourcefile(gpi.readable_geom_path)):
        "defines the read-side verb",
}


def _canonicalising_verbs() -> dict:
    """The identity module's public verbs that hand a CANONICAL path back, each
    mapped to WHERE in its answer the path sits: ``None`` when the verb answers
    with paths directly, or ``(how many values it yields at a time, the
    POSITIONS holding a canonical path)`` when it answers with tuples.

    MEASURED off the module, never listed here, and that is the whole point of
    this derivation. Check 12 was written when there was one such verb and
    recognised canonicalisation by that one name; #110 had already promoted
    ``_keyed`` to a second public one, so the banned shape
    written through it was invisible -- with an instance of that shape already
    sitting in the tree behind it. A third verb is covered with no edit here.

    The measurement: call each exported verb with one relative spelling whose
    canonical form is known, and keep the verbs whose answer CONTAINS it. That
    discriminates on behaviour rather than on a name, which matters because the
    module's public surface is not all one family -- one verb answers a bool and
    two answer SPELLINGS, and none of those three is a way to get an identity
    out of the module. Arity is discovered the same way, by trying the shapes
    the module actually takes and skipping a ``TypeError``.

    The POSITIONS are measured rather than assumed for the same reason the verb
    set is: ``keyed_geom_paths`` answers ``(key, the spelling it came from)``,
    and the two halves are not the same question -- the key is an identity and
    the spelling is a stored entry, which the scan below must treat as the raw
    entry it is. Hard-coding "the key is first" would put that contract in this
    file instead of in the module.

    KNOWN LIMIT: this CALLS every exported verb. It is safe because the module
    is pure-string by construction (its own docstring: it "never touches the
    filesystem for its answer"), and only a ``TypeError`` -- the arity probe's
    own signal -- is swallowed, so a verb that raised anything else would fail
    this gate loudly rather than be silently dropped from the set.
    """
    want = gpi.canonical_geom_path(rel)
    found = {}
    for name in gpi.__all__:
        verb = getattr(gpi, name)
        for args in ((rel,), (rel, rel), ([rel],)):
            try:
                answer = verb(*args)
            except TypeError:
                continue             # a different arity, not a different answer
            if isinstance(answer, str):
                if answer == want:
                    found[name] = None
                    break
                continue
            try:
                items = list(answer)
            except TypeError:
                continue             # a bool: not a path by any route
            if want in items:
                found[name] = None
                break
            tuples = [item for item in items if isinstance(item, (tuple, list))]
            spots = {i for item in tuples
                     for i, value in enumerate(item) if value == want}
            if spots:
                found[name] = (max(len(item) for item in tuples),
                               frozenset(spots))
                break
    return found


#: The read-side verb MEASURES as canonicalising -- it answers with the canonical
#: path when the file is there -- and is removed again, because it is the
#: sanctioned route TO the filesystem rather than a way around it: five of its
#: seven callers open the file it hands back, and banning a read on its result
#: would red-light every one of them. Read off the same function object _READ_OK
#: is derived from, so the two cannot come to name different verbs.
_READ_SIDE_VERB = gpi.readable_geom_path.__name__
_MEASURED_VERBS = _canonicalising_verbs()
#: verb -> None (it answers with paths) or (arity, the positions holding one).
_CANON_SPOTS = {k: v for k, v in _MEASURED_VERBS.items() if k != _READ_SIDE_VERB}
_CANON_VERBS = frozenset(_CANON_SPOTS)

check(gpi.canonical_geom_path.__name__ in _CANON_VERBS and len(_CANON_VERBS) > 1,
      f"12. the canonicalising verbs are DERIVED from the identity module, and "
      f"there is more than ONE of them -- which is the defect this closes "
      f"({sorted(_CANON_VERBS)})")
check(_READ_SIDE_VERB in _MEASURED_VERBS and _READ_SIDE_VERB not in _CANON_VERBS,
      f"12. ...the read-side verb measures as one and is removed again, because "
      f"it is the sanctioned route rather than a way around it "
      f"({_READ_SIDE_VERB})")
check(_CANON_VERBS < (set(gpi.__all__) - {_READ_SIDE_VERB}),
      f"12. ...and the measurement DISCRIMINATES rather than handing back the "
      f"whole public surface (exported and not canonicalising: "
      f"{sorted(set(gpi.__all__) - set(_MEASURED_VERBS))})")
check(any(v is None for v in _CANON_SPOTS.values())
      and any(v is not None for v in _CANON_SPOTS.values()),
      f"12. ...and it measures WHERE the path sits, so the spelling half of a "
      f"pair is not mistaken for an identity ({_CANON_SPOTS})")


def _is_geom_list(node) -> bool:
    """``cfg.geom_files`` as something to iterate, `or []` tail included."""
    while isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        node = node.values[0]
    return _is_geom(node)


def _name_scopes(tree) -> list[list]:
    """Every set of nodes whose NAMES belong together: the module and each
    function, each WITHOUT the bodies of the functions nested inside it.

    Function-scoped rather than file-scoped because a file-scoped read
    over-reaches: mesh_layers_ctrl binds ``abs_out_file`` from the canonicalising
    call in one method and unpacks a same-named local from the widget's item
    data in another, and a file-wide scan reports the second as if the first fed
    it."""
    out = []

    def walk(node):
        own = []

        def collect(n):
            for c in ast.iter_child_nodes(n):
                if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef, ast.Lambda)):
                    walk(c)
                    continue
                own.append(c)
                collect(c)
        collect(node)
        out.append(own)

    walk(tree)
    return out


def _subtree_ids(nodes) -> set:
    return {id(x) for n in nodes for x in ast.walk(n)}


def _target_names(target) -> set:
    """Every name a binding target binds: `q`, `key, p` and `head, *rest` alike."""
    return {t.id for t in ast.walk(target) if isinstance(t, ast.Name)}


#: What makes the statements AFTER a refusal part of the file-is-there branch.
_TERMINATORS = (ast.Return, ast.Raise, ast.Continue, ast.Break)


def _siblings_after(stmt, parent) -> list:
    """The statements following ``stmt`` in the block that holds it."""
    p = parent.get(id(stmt))
    for field in ("body", "orelse", "finalbody"):
        block = getattr(p, field, None)
        if isinstance(block, list) and any(x is stmt for x in block):
            i = next(k for k, x in enumerate(block) if x is stmt)
            return block[i + 1:]
    return []


def _existence_guard(call, parent):
    """``(the TEST this existence call is part of, the branch taken when the
    file IS there, whether the test was NEGATED)``, or ``(None, None, False)``
    when the call is not a guard.

    Polarity is counted through ``not``, so the early-refusal spelling ``if not
    os.path.exists(p):`` has the same two branches as ``if os.path.exists(p):``
    with them swapped -- and when that refusal ENDS the branch (return, raise,
    continue, break), the rest of the enclosing block is the file-is-there branch
    too. Without that, the guard-clause spelling of the reach-around would be
    invisible while the indented one fails.

    A COMPREHENSION's ``if`` is a guard as well, and reading it is what the
    second canonicalising verb made necessary (#119): the list-wide verbs are
    consumed by a ``for``, so the shape written through them is a filter rather
    than a statement. Its file-is-there branch is the element expression -- and
    NOTHING when the test is negated, because then the element is produced
    precisely where the file is ABSENT.

    The third value is the POLARITY, reported rather than acted on here: what the
    caller does with an empty file-is-there branch under a negated test is its
    rule, and it applies that rule to the ``if`` statement and the comprehension
    filter alike."""
    negated = False
    node, p = call, parent.get(id(call))
    while p is not None:
        if isinstance(p, ast.UnaryOp) and isinstance(p.op, ast.Not):
            negated = not negated
        if isinstance(p, ast.comprehension):
            if not any(x is node for x in p.ifs):
                return None, None, False   # the ITERABLE, not a filter
            comp = parent.get(id(p))
            if isinstance(comp, ast.DictComp):
                elts = [comp.key, comp.value]
            else:
                elts = [comp.elt] if hasattr(comp, "elt") else []
            return node, ([] if negated else elts), negated
        if isinstance(p, (ast.If, ast.IfExp)):
            if p.test is not node:
                return None, None, False   # climbed out of the test, not a guard
            body = p.body if isinstance(p.body, list) else [p.body]
            orelse = p.orelse if isinstance(p.orelse, list) else [p.orelse]
            present = list(orelse if negated else body)
            absent = body if negated else orelse
            if (isinstance(p, ast.If) and absent
                    and isinstance(absent[-1], _TERMINATORS)):
                present += _siblings_after(p, parent)
            return node, present, negated
        node, p = p, parent.get(id(p))
    return None, None, False


def _reach_around_read_sites(path: str) -> list[tuple[int, str]]:
    """(line, construct) for every site in one file that reaches around
    ``readable_geom_path`` -- shape (a) or shape (b) above."""
    tree = ast.parse(open(path).read())
    parent = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            parent[id(c)] = n

    out = set()
    for scope in _name_scopes(tree):
        canon, raw = {}, set()
        for n in scope:
            if (isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
                    and _callee_name(n.value) in _CANON_VERBS):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        canon[t.id] = n
            it = tgt = None
            if isinstance(n, (ast.For, ast.AsyncFor)):
                it, tgt = n.iter, n.target
            elif isinstance(n, ast.comprehension):
                it, tgt = n.iter, n.target
            if it is None:
                continue
            if _is_geom_list(it):
                raw |= _target_names(tgt)
            elif isinstance(it, ast.Call) and _callee_name(it) in _CANON_VERBS:
                # The list-wide verbs answer with a SEQUENCE, so the binding they
                # reach the code through is a loop target rather than an
                # assignment. WHICH half is which comes from the measurement
                # above, not from an assumption here: `keyed_geom_paths` yields
                # (key, the spelling it came from), and the spelling is a stored
                # entry -- so it goes into `raw`, where handing it to the
                # filesystem is shape (b), exactly as it is when the same entry
                # comes off the list directly.
                shape = _CANON_SPOTS[_callee_name(it)]
                if shape is None or not isinstance(tgt, (ast.Tuple, ast.List)):
                    canon.update({name: n for name in _target_names(tgt)})
                else:
                    _, _spots = shape
                    for _i, _elt in enumerate(tgt.elts):
                        if _i in _spots:
                            canon.update({nm: n for nm in _target_names(_elt)})
                        else:
                            raw |= _target_names(_elt)

        for n in scope:
            if not (isinstance(n, ast.Call) and n.args):
                continue
            fn = _callee_name(n)
            if fn not in _EXISTENCE_CALLS + _READ_CALLS:
                continue
            arg = n.args[0]
            if isinstance(arg, ast.Call) and _callee_name(arg) in _CANON_VERBS:
                out.add((n.lineno, f"{fn}({_callee_name(arg)}(...))"))
                continue
            # cfg.geom_files[0] handed straight to the call: the same raw entry
            # the loop yields, reached by index instead.
            if isinstance(arg, ast.Subscript) and _is_geom(arg.value):
                out.add((n.lineno, f"{fn}() on a raw geom_files entry"))
                continue
            if not isinstance(arg, ast.Name):
                continue
            if arg.id in raw:
                out.add((n.lineno, f"{fn}() on a raw geom_files entry"))
                continue
            if arg.id not in canon:
                continue
            if fn in _READ_CALLS:
                out.add((n.lineno, f"{fn}() on a canonicalised entry"))
                continue
            test, present, negated = _existence_guard(n, parent)
            # Uses inside the guard's own test are part of the question, not a
            # second use of the answer. With no guard at all, the existence call
            # itself is the only thing standing in for one.
            asked = _subtree_ids([test] if test is not None else [n])
            found_here = _subtree_ids(present) if test is not None else set()
            # A NEGATED guard with an EMPTY file-is-there branch is the absent
            # question and nothing else: the value drives the selection of the
            # entries that are GONE -- `[p for k, p in keyed(...) if not
            # exists(k)]`, which is the model's own geom_files_not_on_disk.
            # That is the deliberate limit this check has always carried, and it
            # is the only thing #119 subtracted; every other shape is judged the
            # way it was before, by whether the entry is used anywhere but the
            # branch where the file turned out to be there.
            if test is not None and negated and not present:
                continue
            elsewhere = [u for u in scope
                         if isinstance(u, ast.Name) and u.id == arg.id
                         and isinstance(u.ctx, ast.Load)
                         and id(u) not in asked and id(u) not in found_here]
            if not elsewhere:
                out.add((n.lineno,
                         f"{fn}() on a canonicalised entry used only where it "
                         f"exists"))
    return sorted(out)


_readers = _scan_app_tree(_reach_around_read_sites, skip=_READ_OK)
check(not _readers,
      f"12. no reader canonicalises and then asks the filesystem itself, and "
      f"none hands a raw geom_files entry to it ({_readers})")

# The exemption is LOAD BEARING, like check 7's: readable_geom_path's own body
# IS shape (a) -- canonicalise, then os.path.exists on the result, used only
# where it exists -- so exempting the module it lives in is doing work, and the
# scan is reaching the one construct it must not ban.
check(len(_READ_OK) == 1 and all(_reach_around_read_sites(p) for p in _READ_OK),
      f"12. the derived allow-list is the one module that DEFINES the verb, and "
      f"it really contains the construct "
      f"({ {os.path.basename(k): _reach_around_read_sites(k) for k in _READ_OK} })")
check(os.path.normpath(os.path.join(_GUI, "app", "controllers",
                                    "mesh_layers_ctrl.py")) not in _READ_OK,
      "12. ...and the controller carrying the three sites that need the "
      "canonical path WHEN IT IS ABSENT is not exempt -- they are distinguished "
      "by the question they ask, not by their filename")

# The scan sees every shape it forbids.
_probe12 = os.path.join(tmp, "probe_read.py")
with open(_probe12, "w") as fh:
    fh.write("import os\n"
             "import numpy as np\n"
             "\n"
             "def direct(p):\n"
             "    return os.path.exists(canonical_geom_path(p))\n"
             "\n"
             "def guarded(p):\n"
             "    q = canonical_geom_path(p)\n"
             "    if os.path.exists(q):\n"
             "        return q\n"
             "    return ''\n"
             "\n"
             "def refused(p):\n"
             "    q = canonical_geom_path(p)\n"
             "    if not os.path.isfile(q):\n"
             "        return ''\n"
             "    return q\n"
             "\n"
             "def flagged(p):\n"
             "    q = canonical_geom_path(p)\n"
             "    return os.path.lexists(q)\n"
             "\n"
             "def opened(p):\n"
             "    q = canonical_geom_path(p)\n"
             "    return np.loadtxt(q)\n"
             "\n"
             "def raw_loop(cfg):\n"
             "    for gf in cfg.geom_files:\n"
             "        if os.path.exists(gf):\n"
             "            yield open(gf)\n"
             "\n"
             "def raw_comp(cfg):\n"
             "    return [np.loadtxt(g) for g in (cfg.geom_files or [])]\n"
             "\n"
             "def raw_index(cfg):\n"
             "    return os.stat(cfg.geom_files[0])\n")
_seen12 = {w for _ln, w in _reach_around_read_sites(_probe12)}
check(_seen12 == {
          "exists(canonical_geom_path(...))",
          "exists() on a canonicalised entry used only where it exists",
          "isfile() on a canonicalised entry used only where it exists",
          "lexists() on a canonicalised entry used only where it exists",
          "loadtxt() on a canonicalised entry",
          "exists() on a raw geom_files entry",
          "open() on a raw geom_files entry",
          "loadtxt() on a raw geom_files entry",
          "stat() on a raw geom_files entry"},
      f"12. INJECTION: the scan sees both shapes -- the direct call, the local "
      f"bound from it in either polarity, with no guard at all, a read that "
      f"presupposes the answer, and a raw entry from a loop, a comprehension or "
      f"a subscript ({sorted(_seen12)})")

# ...and it is silent on the sites that are not this question, or the tree
# passing above says nothing. These are the real ones, rewritten to the
# fixture's names: the THREE that need the canonical path where the file is
# absent -- the refusal message, the "(not exported)" label, the "missing file"
# tag -- plus the near-shape, a re-test of a path that no canonicalising call
# fed, which is silent for a different reason and is here so the two reasons are
# not confused for one.
_probe12b = os.path.join(tmp, "probe_read_ok.py")
with open(_probe12b, "w") as fh:
    fh.write("import os\n"
             "\n"
             "def refusal(self, p):\n"
             "    q = canonical_geom_path(p)\n"
             "    if not os.path.exists(q):\n"
             "        self.log(f\"does not exist at '{q}'\")\n"
             "        return\n"
             "    self.use(q)\n"
             "\n"
             "def label(self, p):\n"
             "    q = canonical_geom_path(p)\n"
             "    text = 'name'\n"
             "    if not os.path.exists(q):\n"
             "        text += ' (not exported)'\n"
             "    self.item(text, q)\n"
             "\n"
             "def tag(self, cfg):\n"
             "    for gf in cfg.geom_files:\n"
             "        q = canonical_geom_path(gf)\n"
             "        t = 'external file' if os.path.exists(q) else 'missing file'\n"
             "        self.item(f'{os.path.basename(q)} ({t})')\n"
             "\n"
             "def retest(self, data):\n"
             "    _sid, q = data\n"
             "    if not q or not os.path.exists(q):\n"
             "        self.refuse()\n"
             "\n"
             "def converted(self, p):\n"
             "    q = readable_geom_path(p)\n"
             "    if q:\n"
             "        self.use(q)\n")
check(not _reach_around_read_sites(_probe12b),
      f"12. ...and silent on the three sites that need the canonical path where "
      f"the file is ABSENT, on the near-shape no canonicalising call feeds, and "
      f"on a converted reader ({_reach_around_read_sites(_probe12b)})")

# ...and it sees the shape written through EVERY canonicalising verb, not only
# the one it was written for. Generated FROM the derived set, so a verb added to
# the identity module is proved here with no edit. Each fixture carries the
# reader BESIDE the model's own absent-question spelling of the same loop, so one
# probe holds both halves of the discrimination: the list-wide verbs answer with
# a SEQUENCE, so both are reached through a loop target rather than an
# assignment. (Syntactic fixtures, like the probes above: the scan reads names
# and shapes, and these files are never imported.)
_WHERE_IT_EXISTS = "exists() on a canonicalised entry used only where it exists"
_RAW_ENTRY = "exists() on a raw geom_files entry"


def _verb_loop_names(verb):
    """``(the loop target to write for this verb, the name bound to a canonical
    key, the name bound to a stored spelling or None)``.

    Built from the MEASURED shape rather than written key-first, because a
    fixture that hard-codes ``for key, _spelling in ...`` makes the derivation
    above only half true: a third verb answering ``(spelling, key)`` would turn
    these probes RED instead of being covered by them. This generates the
    fixture the other way round for such a verb, with no edit."""
    shape = _CANON_SPOTS[verb]
    if shape is None:
        return "key", "key", None
    arity, spots = shape
    names, key, spelling = [], None, None
    for i in range(arity):
        if i in spots:
            key = key or "key"
            names.append(key if names.count("key") == 0 else f"_c{i}")
        else:
            spelling = spelling or "spelling"
            names.append(spelling if names.count("spelling") == 0
                         else f"_sp{i}")
    return ", ".join(names), key, spelling


for _verb in sorted(_CANON_VERBS):
    _target, _key, _spelling = _verb_loop_names(_verb)
    _pv = os.path.join(tmp, f"probe_verb_{_verb}.py")
    with open(_pv, "w") as fh:
        fh.write("import os\n"
                 "\n"
                 "\n"
                 "def reader(cfg):\n"
                 f"    for {_target} in {_verb}(cfg.geom_files):\n"
                 f"        if os.path.exists({_key}):\n"
                 f"            yield {_key}\n"
                 "\n"
                 "\n"
                 "def absent(cfg):\n"
                 f"    return [{_key} for {_target} in {_verb}(cfg.geom_files)\n"
                 f"            if not os.path.exists({_key})]\n")
    _seen = _reach_around_read_sites(_pv)
    check(_seen == [(6, _WHERE_IT_EXISTS)],
          f"12. INJECTION: a reader that canonicalises through {_verb}() and "
          f"then asks the filesystem is seen -- and the ABSENT question written "
          f"through the same verb beside it is not, which is why the model's own "
          f"geom_files_not_on_disk stays green unpinned ({_seen})")

# The two halves of a PAIR are two different questions, and the measured
# POSITION is what tells them apart. Both shapes here regressed in #119's own
# first cut and were caught by review: the key half went silent when the branch
# uses the ANSWER rather than the path, and the spelling half was given the
# canonical half's discrimination instead of being the raw stored entry it is --
# so `exists(spelling)` was silent where the identical entry taken off the list
# directly fails.
for _verb in sorted(_CANON_VERBS):
    _target, _key, _spelling = _verb_loop_names(_verb)
    if _spelling is None:
        continue                     # this verb answers with paths, not pairs
    _pp = os.path.join(tmp, f"probe_pair_{_verb}.py")
    with open(_pp, "w") as fh:
        fh.write("import os\n"
                 "\n"
                 "\n"
                 "def answered(cfg):\n"
                 f"    for {_target} in {_verb}(cfg.geom_files):\n"
                 f"        if os.path.exists({_key}):\n"
                 "            return True\n"
                 "    return False\n"
                 "\n"
                 "\n"
                 "def spelled(cfg):\n"
                 f"    return [{_spelling} for {_target} in "
                 f"{_verb}(cfg.geom_files)\n"
                 f"            if not os.path.exists({_spelling})]\n")
    _seen = _reach_around_read_sites(_pp)
    check(_seen == [(6, _WHERE_IT_EXISTS), (13, _RAW_ENTRY)],
          f"12. INJECTION: through {_verb}(), the KEY half is a canonicalised "
          f"entry even where the branch uses only the ANSWER, and the SPELLING "
          f"half is the raw entry it is -- told apart by the measured position, "
          f"not by which name comes first in the target ({_seen})")

# ...and the discrimination is load bearing in the SCAN, not just in the set:
# the same reader through a verb that answers with SPELLINGS or a bool is silent.
for _verb in sorted(set(gpi.__all__) - set(_MEASURED_VERBS)):
    _pv = os.path.join(tmp, f"probe_notverb_{_verb}.py")
    with open(_pv, "w") as fh:
        fh.write("import os\n"
                 "\n"
                 "\n"
                 "def reader(cfg):\n"
                 f"    for key, _spelling in {_verb}(cfg.geom_files):\n"
                 "        if os.path.exists(key):\n"
                 "            yield key\n")
    check(not _reach_around_read_sites(_pv),
          f"12. ...and the same reader through {_verb}(), which the measurement "
          f"says is not a canonicalising verb, is silent "
          f"({_reach_around_read_sites(_pv)})")

# ── 7b. the gate is non-vacuous AS A BUILD STEP, read from the exit code ──
# The scan-level probe above proves the AST walk sees the constructs; it cannot
# prove this FILE goes red when one appears in the real tree. So run this whole
# module as a subprocess: a negative control on the untouched tree, then one run
# per NEW door injected into a tree this gate scans. The verdict is the EXIT CODE --
# a FAIL-line count reports a crash as zero failures, which reads as an inert
# injection (see docs/design_notes/gui.md).
#
# Both doors are here because the first widening only closed the first, and the
# constructor kwarg was found by REVIEW rather than by the scan -- a coverage
# claim proved on one construct says nothing about the other.
#
# The negative control is what proves the mixin's own `self.geom_files = keep` is
# still PERMITTED: the tree containing it passes, and the allow-list check above
# has already shown the exemption is what lets it.
_NO_SUB = "HYBMESH_GEOM_IDENT_NO_SUBPROCESS"
#: Set on a child run by check 7c only: it stops the doors loop with a probe
#: written and nothing removed, which is the state a crash leaves behind.
_PAUSE = "HYBMESH_GEOM_IDENT_PAUSE_AT_INJECTION"
#: What that child prints before it stops: the probe it just wrote, then its own
#: temp directory. The second is there because the child is about to be SIGKILLed
#: and its own `shutil.rmtree` at the foot of this file will never run -- so the
#: KILLER removes it. Without this the gate leaked one ~48K directory per run:
#: outside the package, so check 7c held either way, but "leave nothing rather
#: than sweep afterwards" has to be true of the whole run, not of one tree.
_PAUSE_MARK = "INJECTION-PROBE-ON-DISK "


#: How long check 7c's paused child waits to be killed. It must outlast the
#: watchdog below, so that a child which is somehow NOT killed still dies on its
#: own rather than holding the suite; the watchdog is the one that normally
#: fires. POSIX only (process groups, SIGKILL), like the rest of this repo's
#: harness -- CI is ubuntu and development is macOS.
_PAUSE_SECONDS = 600
_WATCHDOG_SECONDS = 120


def _package_snapshot():
    """Every file under gui/app with its size -- what an interrupted run of this
    gate must leave exactly as it found it.

    A separate walk from :func:`_scanned_files`, which answers a different
    question: that one is the SCAN's reach (``.py`` only, both roots), this one
    is the PACKAGE's contents (every file, sizes included, the package alone) --
    a stray ``.json`` or a rewritten module has to show up here."""
    out = []
    for _root, _dirs, _files in os.walk(os.path.join(_GUI, "app")):
        _dirs[:] = [d for d in _dirs if d != "__pycache__"]
        for _f in _files:
            _full = os.path.join(_root, _f)
            out.append((os.path.relpath(_full, _GUI), os.path.getsize(_full)))
    return sorted(out)


if not os.environ.get(_NO_SUB):
    _child_env = dict(os.environ, **{_NO_SUB: "1", _INJ_DIR_ENV: _INJ_DIR})

    def _run_gate():
        return subprocess.run([sys.executable, os.path.abspath(__file__)],
                              env=_child_env, capture_output=True, text=True)

    _neg = _run_gate()
    check(_neg.returncode == 0,
          f"7b. NEGATIVE CONTROL: the real tree passes this gate "
          f"(exit {_neg.returncode})")

    # A file that did not exist before, so no restore can be silently ignored by
    # a stale .pyc keyed on (mtime, size) -- the trap that made a same-size
    # injection restore inert on this platform. It is written into the SANDBOX
    # declared at the top of this file rather than into gui/app/services/, so a
    # killed run has nothing in the package to leave behind; check 7c kills one
    # and shows the tree clean.
    _inj = os.path.join(_INJ_DIR, "_geom_ident_inj_probe.py")
    check(not os.listdir(_INJ_DIR),
          f"7b. NEGATIVE CONTROL: the injection sandbox is empty before any door "
          f"is opened, so the run above passed on the real tree alone "
          f"({os.listdir(_INJ_DIR)})")
    check(not os.path.abspath(_INJ_DIR).startswith(
              os.path.join(os.path.abspath(_GUI), "app") + os.sep),
          f"7b. ...and it is outside the package tree ({_INJ_DIR})")
    # What the doors used to prove as a side effect of being written INTO
    # gui/app: that the package is the tree these scans read. They are opened in
    # the sandbox now, so it is asserted here instead, against the one walk both
    # roots go through.
    _walked = [f for f, _b in _scanned_files()]
    _must_walk = [os.path.normpath(os.path.join(_GUI, "app", *_p)) for _p in
                  (("models", "mesh_config_geoms.py"),
                   ("services", "geom_path_identity.py"),
                   ("controllers", "mesh_layers_ctrl.py"))]
    check(len(_walked) > 100 and all(_m in _walked for _m in _must_walk),
          f"7b. ...and the PACKAGE is really the tree these scans walk -- "
          f"{len(_walked)} files, the model's geometry verbs, the identity "
          f"module and the controller carrying the correct sites among them "
          f"({[os.path.basename(_m) for _m in _must_walk if _m not in _walked]})")
    _DOORS = (
        ("the wholesale rebind",
         "def reintroduce_the_defect(cfg, paths):\n"
         "    cfg.geom_files = list(paths)\n",
         "_geom_ident_inj_probe.py:2 geom_files = ... (rebind)"),
        ("the constructor keyword",
         "from app.models.mesh_config import MeshConfig\n"
         "\n"
         "def reintroduce_the_defect(paths):\n"
         "    return MeshConfig(geom_files=list(paths))\n",
         "_geom_ident_inj_probe.py:4 geom_files= keyword to MeshConfig()"),
        # Checks 8 and 9 are scans over the same real tree, so they are held to
        # the same bar: a door opened in a tree this gate scans, and the verdict
        # read from the child's exit code.
        ("the deferred identity import",
         "def reintroduce_the_defect():\n"
         "    from app.services.geom_path_identity import canonical_geom_path\n"
         "    return canonical_geom_path\n",
         "_geom_ident_inj_probe.py:2 deferred geom_path_identity import"),
        ("the cwd-relative store",
         "import os\n"
         "\n"
         "def reintroduce_the_defect(cfg, p):\n"
         "    cfg.add_geom_file(os.path.abspath(p))\n",
         "_geom_ident_inj_probe.py:4 add_geom_file(os.path.abspath(...))"),
        # Check 12's two shapes, held to the same bar for the same reason:
        # its scan-level probe proves the AST walk sees them, and only a run of
        # this FILE against a door opened in a tree this gate scans proves the
        # gate goes red. The first is the discriminated shape -- the canonical path
        # used only on the branch where the file turned out to be there -- so
        # this door is also what keeps the discriminator from being a way to
        # never fire at all.
        ("the canonicalise-then-ask reach-around",
         "import os\n"
         "\n"
         "from app.services.geom_path_identity import canonical_geom_path\n"
         "\n"
         "\n"
         "def reintroduce_the_defect(p):\n"
         "    q = canonical_geom_path(p)\n"
         "    if os.path.exists(q):\n"
         "        return q\n"
         "    return ''\n",
         "_geom_ident_inj_probe.py:8 exists() on a canonicalised entry used "
         "only where it exists"),
        ("the raw geom_files entry handed to the filesystem",
         "import os\n"
         "\n"
         "\n"
         "def reintroduce_the_defect(cfg):\n"
         "    for gf in cfg.geom_files:\n"
         "        if os.path.exists(gf):\n"
         "            yield open(gf)\n",
         "_geom_ident_inj_probe.py:6 exists() on a raw geom_files entry"),
    )
    # One door per canonicalising verb BEYOND the one check 12 was written for,
    # generated from the DERIVED set so that a third verb is proved at the build
    # level too with no edit here. canonical_geom_path is the door above, in the
    # shape a single-path verb is actually written in; these are the list-wide
    # verbs, whose answer reaches the code through a loop target.
    _DOORS += tuple(
        (f"the reach-around through {_v}()",
         "import os\n"
         "\n"
         f"from app.services.geom_path_identity import {_v}\n"
         "\n"
         "\n"
         "def reintroduce_the_defect(cfg):\n"
         f"    for {_verb_loop_names(_v)[0]} in {_v}(cfg.geom_files):\n"
         f"        if os.path.exists({_verb_loop_names(_v)[1]}):\n"
         f"            yield {_verb_loop_names(_v)[1]}\n",
         f"_geom_ident_inj_probe.py:8 {_WHERE_IT_EXISTS}")
        for _v in sorted(_CANON_VERBS - {gpi.canonical_geom_path.__name__}))

    for _what, _src, _want in _DOORS:
        try:
            with open(_inj, "w") as fh:
                fh.write(_src)
            if os.environ.get(_PAUSE):
                # Check 7c's child stops HERE: a probe written, nothing removed.
                print(_PAUSE_MARK + _inj + "\t" + tmp, flush=True)
                time.sleep(_PAUSE_SECONDS)
            _pos = _run_gate()
            check(_pos.returncode != 0,
                  f"7b. INJECTION: {_what} in a scanned tree fails the gate "
                  f"(exit {_pos.returncode})")
            check(_want in _pos.stdout.replace(os.sep, "/"),
                  f"7b. ...and the failure names the file, the line and the "
                  f"construct ({_what})")
            # Exit 1 by FAILING, not by crashing: an unhandled exception exits
            # non-zero too, which would make a broken gate look like a biting one.
            check(not _pos.stderr.strip(),
                  f"7b. ...and it failed rather than crashed -- stderr is empty "
                  f"({_what}: {_pos.stderr.strip()[:200]!r})")
            check("RESULT: 1 FAILED" in _pos.stdout,
                  f"7b. ...and it moved exactly ONE verdict, so the injection "
                  f"measures that one check and not collateral damage ({_what})")
        finally:
            try:
                os.remove(_inj)
            except OSError:
                pass

    # ── 7c. an INTERRUPTED run leaves nothing inside the package ─────────
    # The doors above used to be written into gui/app/services/ and removed in
    # the `finally` right there. A `finally` does not run when the process is
    # killed, so a crashed or cancelled run left a module inside the live package
    # and the NEXT run measured it -- the shape that already cost this repo once,
    # when a stale harness backup silently reverted a fix that had landed (#113).
    #
    # Demonstrated rather than argued: snapshot the package, start this file
    # again with the pause set so it stops with a probe on disk, SIGKILL the
    # process group, and compare. The first two checks are what stop the third
    # from being clean for the wrong reason -- a run that died before writing
    # anything would pass it trivially.
    _before = _package_snapshot()
    _paused = subprocess.Popen(
        [sys.executable, os.path.abspath(__file__)],
        env=dict(os.environ, **{_PAUSE: "1", _INJ_DIR_ENV: _INJ_DIR}),
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        start_new_session=True)

    def _kill_paused():
        try:
            os.killpg(os.getpgid(_paused.pid), signal.SIGKILL)
        except OSError:
            pass                       # already gone

    _watchdog = threading.Timer(_WATCHDOG_SECONDS, _kill_paused)
    _watchdog.start()
    _left, _child_tmp = "", ""
    try:
        for _line in _paused.stdout:
            if _line.startswith(_PAUSE_MARK):
                _left, _, _child_tmp = _line.strip()[len(_PAUSE_MARK):].partition(
                    "\t")
                break
    finally:
        _kill_paused()
        _watchdog.cancel()
        _paused.stdout.close()
        _paused.wait()

    check(bool(_left) and os.path.exists(_left),
          f"7c. the killed run really had an injection probe ON DISK when it "
          f"died, so the tree below is not clean for the wrong reason ({_left!r})")
    check(bool(_left) and not os.path.abspath(_left).startswith(
              os.path.join(os.path.abspath(_GUI), "app") + os.sep),
          f"7c. ...and it wrote that probe into the sandbox, outside the package "
          f"({_left!r})")
    # Wider than the two above, which only say where THIS probe went: this one
    # fails on anything the killed run left in the package, a second file or a
    # rewritten module included.
    check(_package_snapshot() == _before,
          "7c. INTERRUPTED RUN: killing this gate mid-injection leaves gui/app "
          "exactly as it was, file for file and byte for byte -- nothing is "
          "swept up afterwards because nothing was put there")
    check(bool(_child_tmp) and os.path.isdir(_child_tmp),
          f"7c. ...and the killed run's OWN temp directory is still there, which "
          f"its `finally` never reached -- so this process removes it rather "
          f"than leaving one behind per run ({_child_tmp!r})")
    try:
        os.remove(_left)
    except OSError:
        pass
    shutil.rmtree(_child_tmp, ignore_errors=True)
    check(bool(_child_tmp) and not os.path.exists(_child_tmp),
          f"7c. ...and it is gone ({_child_tmp!r})")

for p in (absolute, other):
    try:
        os.remove(p)
    except OSError:
        pass
shutil.rmtree(tmp, ignore_errors=True)

if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED")
    for m in _FAILS:
        print("  - " + m)
    sys.exit(1)
print("\nRESULT: ALL PASS")
