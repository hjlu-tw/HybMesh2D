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

Run: python3 tools/PreProcessor/tests/test_geom_files_identity.py
"""
import os
import sys
import shutil
import tempfile

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


def _raw_geom_file_sites(path: str) -> list[tuple[int, str]]:
    """(line, construct) for every raw list mutation/membership/rebind over
    ``*.geom_files`` in one file. Reads what the code DOES, so a rename or a
    reflowed line cannot make a violation invisible the way a grep could."""
    tree = ast.parse(open(path).read())
    out = []

    def _is_geom(node) -> bool:
        return isinstance(node, ast.Attribute) and node.attr == "geom_files"

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
            _callee = (n.func.attr if isinstance(n.func, ast.Attribute)
                       else getattr(n.func, "id", None))
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


def _scan_app_tree() -> list[str]:
    """Every offending site under gui/app, one run reporting all of them."""
    bad = []
    for root, dirs, files in os.walk(os.path.join(_GUI, "app")):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in sorted(files):
            if not f.endswith(".py"):
                continue
            full = os.path.normpath(os.path.join(root, f))
            if full in _RAW_OK:
                continue
            for ln, what in _raw_geom_file_sites(full):
                bad.append(f"{os.path.relpath(full, _GUI)}:{ln} {what}")
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

# ── 7b. the gate is non-vacuous AS A BUILD STEP, read from the exit code ──
# The scan-level probe above proves the AST walk sees the constructs; it cannot
# prove this FILE goes red when one appears in the real tree. So run this whole
# module as a subprocess: a negative control on the untouched tree, then one run
# per NEW door injected into a real GUI package. The verdict is the EXIT CODE --
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
if not os.environ.get(_NO_SUB):
    _child_env = dict(os.environ, **{_NO_SUB: "1"})

    def _run_gate():
        return subprocess.run([sys.executable, os.path.abspath(__file__)],
                              env=_child_env, capture_output=True, text=True)

    _neg = _run_gate()
    check(_neg.returncode == 0,
          f"7b. NEGATIVE CONTROL: the real tree passes this gate "
          f"(exit {_neg.returncode})")

    # A file that did not exist before, so no restore can be silently ignored by
    # a stale .pyc keyed on (mtime, size) -- the trap that made a same-size
    # injection restore inert on this platform.
    _inj = os.path.join(_GUI, "app", "services", "_geom_ident_inj_probe.py")
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
    )
    for _what, _src, _want in _DOORS:
        try:
            with open(_inj, "w") as fh:
                fh.write(_src)
            _pos = _run_gate()
            check(_pos.returncode != 0,
                  f"7b. INJECTION: {_what} in a real GUI package fails the gate "
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
