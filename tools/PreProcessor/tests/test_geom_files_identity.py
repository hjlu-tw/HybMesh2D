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
import ast                                                        # noqa: E402

#: Files allowed to touch geom_files as a plain list, with the reason. The MODEL
#: owns the identity rules, so it is the one place that may; anything else must
#: go through add/remove/has_geom_file, role_of or dedupe_geom_paths. Note this
#: names the MIXIN, not mesh_config.py: the verbs moved there when the model went
#: over the file-size budget, and this check is what noticed — an allow-list keyed
#: to where the code used to live would have exempted nothing and flagged the
#: declaration itself, which is the honest failure and not a false alarm.
_RAW_OK = {
    os.path.normpath(os.path.join(_GUI, "app", "models", "mesh_config_geoms.py")):
        "declares add/remove/has_geom_file itself",
}


def _raw_geom_file_sites(path: str) -> list[tuple[int, str]]:
    """(line, construct) for every raw string mutation/membership over
    ``*.geom_files`` in one file. Reads what the code DOES, so a rename or a
    reflowed line cannot make a violation invisible the way a grep could."""
    tree = ast.parse(open(path).read())
    out = []
    for n in ast.walk(tree):
        # x.geom_files.append(...) / .remove(...)
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in ("append", "remove")
                and isinstance(n.func.value, ast.Attribute)
                and n.func.value.attr == "geom_files"):
            out.append((n.lineno, f"geom_files.{n.func.attr}()"))
        # `p in x.geom_files` / `p not in x.geom_files`
        if isinstance(n, ast.Compare):
            for op, cmp in zip(n.ops, n.comparators):
                if (isinstance(op, (ast.In, ast.NotIn))
                        and isinstance(cmp, ast.Attribute)
                        and cmp.attr == "geom_files"):
                    out.append((n.lineno, "`in` over geom_files"))
    return out


_offenders = []
for _root, _dirs, _files in os.walk(os.path.join(_GUI, "app")):
    _dirs[:] = [d for d in _dirs if d != "__pycache__"]
    for _f in _files:
        if not _f.endswith(".py"):
            continue
        _full = os.path.normpath(os.path.join(_root, _f))
        if _full in _RAW_OK:
            continue
        for _ln, _what in _raw_geom_file_sites(_full):
            _offenders.append(f"{os.path.relpath(_full, _GUI)}:{_ln} {_what}")

check(not _offenders,
      f"7. nothing outside the model mutates or tests geom_files by string "
      f"({_offenders})")

# ...and the check is not vacuous: it must SEE the construct it forbids.
_probe = os.path.join(tmp, "probe_raw.py")
with open(_probe, "w") as fh:
    fh.write("def f(cfg, p):\n"
             "    if p not in cfg.geom_files:\n"
             "        cfg.geom_files.append(p)\n"
             "    cfg.geom_files.remove(p)\n")
_found = {w for _ln, w in _raw_geom_file_sites(_probe)}
check(_found == {"geom_files.append()", "geom_files.remove()", "`in` over geom_files"},
      f"7. INJECTION: the scan really sees all three constructs ({sorted(_found)})")

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
