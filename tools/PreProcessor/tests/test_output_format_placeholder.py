#!/usr/bin/env python3
"""Regression test: the Output field's ``.*`` is a placeholder, not an extension.

The Mesh panel's Output field holds ONE name for however many export formats are
enabled, so it is filled in as ``results/meshes/<case>/mesh_<case>.*`` and each
writer substitutes its own extension. Since the panel->model sync runs on every
edit, that string IS the model value — and travels verbatim into the workspace,
the pipeline script and the mesher's config file.

Only the export dialog ever understood it. Consequences found on disk
(2026-08-13, from a user's `.hws` whose `output_filename` was
`results/meshes/cartesian/mesh_cartesian.*`):

* `src/main.cpp` took it literally. ``extPos()`` finds the dot before the ``*``,
  so ``.vtk`` was never appended and **the VTK was written into a file NAMED
  ``mesh_<case>.*``** — verified with the shipped binary before the fix. Older
  builds (before ``stripExt``, 2026-08-12) did the same to STAR-CD, leaving
  ``mesh_cartesian.*.vrt`` / ``.cel`` / ``.bnd`` / ``.provenance.json`` behind.
* `services/pipeline_runner` handed that name straight to the mesher and then
  checked ``os.path.exists`` on it — which the literal ``mesh_<case>.*`` file
  satisfied, so the pipeline reported success and passed a glob downstream. Note
  that a C++-only fix would have turned this into a *failure* here, which is why
  both halves move together.

What this pins down:
  1. `models/mesh_output_names.output_base` / `output_path_for` (re-exported as
     `MeshConfig.*`) resolve the placeholder, a real extension, and a name with
     neither — and are idempotent.
  2. Nothing else in the GUI carries its own private `endswith(".*")` branch.
  3. The pipeline stage resolves the name to a real absolute `.vtk`.
  4. The mesher, given `-out_name <dir>/probe.*`, writes `probe.vtk` plus the
     STAR-CD trio and leaves NO file with a `*` in its name.

Run:  python3 tools/PreProcessor/tests/test_output_format_placeholder.py
Checks 4 skip cleanly if ./build/HybMesh2D has not been built.
"""
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_BIN = os.path.join(_REPO, "build", "HybMesh2D")
_LIB = os.path.join(_REPO, "build")
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


from app.models.mesh_config import MeshConfig                      # noqa: E402
from app.services.pipeline_runner import _mesh_output_path         # noqa: E402

# ── 1. the resolver ───────────────────────────────────────────────────────
P = MeshConfig.FORMAT_PLACEHOLDER
check(P == ".*", f"1. the placeholder is a named constant ({P})")
check(MeshConfig.output_base("results/meshes/c/mesh_c.*") == "results/meshes/c/mesh_c",
      "1. output_base strips the placeholder")
check(MeshConfig.output_base("results/meshes/c/mesh_c.vtk") == "results/meshes/c/mesh_c",
      "1. output_base strips a real extension too")
check(MeshConfig.output_base("results/meshes/c/mesh_c") == "results/meshes/c/mesh_c",
      "1. output_base leaves an extension-less name alone")
# splitext only looks at the basename, so a dotted DIRECTORY must survive.
check(MeshConfig.output_base("/a/.hidden.dir/mesh_c.*") == "/a/.hidden.dir/mesh_c",
      "1. a dot in a directory component is not mistaken for the extension")
check(MeshConfig.output_base("") == "" and MeshConfig.output_base(None) == "",
      "1. an empty name resolves to empty, not to a bare extension")
check(MeshConfig.output_path_for("m.*", ".vtk") == "m.vtk",
      "1. output_path_for substitutes the wanted extension")
check(MeshConfig.output_path_for("m.vtk", ".vtk") == "m.vtk",
      "1. ...idempotently")
check(MeshConfig.output_path_for("m.*", ".bnd") == "m.bnd",
      "1. ...once per format")
check(MeshConfig.output_path_for("", ".vtk") == "",
      "1. an empty name stays empty (the caller auto-names instead)")

# ── 2. one owner for the convention ───────────────────────────────────────
# The export dialog used to hold the only endswith(".*") branch; a second private
# copy is how the mesher and the headless runner came to disagree with it.
_OWNER = "mesh_output_names.py"          # the module that defines output_base
strays = []
for base in (os.path.join(_GUI, "app"), _GUI):
    for root, _dirs, files in os.walk(base):
        if os.path.basename(root) == "__pycache__":
            continue
        for fn in files:
            if not fn.endswith(".py") or fn == _OWNER:
                continue
            path = os.path.join(root, fn)
            with open(path, encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    code = line.split("#", 1)[0]
                    if 'endswith(".*")' in code or "endswith('.*')" in code:
                        strays.append(f"{os.path.relpath(path, _REPO)}:{i}")
        if base == _GUI:
            break                      # top level only; app/ walked separately
check(not strays,
      f"2. only {_OWNER} resolves the placeholder ({strays or 'no strays'})")

# ── 3. the headless mesh stage resolves it to a real .vtk ─────────────────
cfg = MeshConfig()
cfg.geom_files = ["/tmp/body.dat"]
cfg.output_filename = "results/meshes/cartesian/mesh_cartesian.*"
out = _mesh_output_path(cfg, "script", _REPO)
check(out == os.path.join(_REPO, "results/meshes/cartesian/mesh_cartesian.vtk"),
      f"3. the pipeline resolves the placeholder to an absolute .vtk ({out})")
cfg.output_filename = ""
out = _mesh_output_path(cfg, "script", _REPO)
check(out.endswith(os.path.join("results", "meshes", "mesh_body.vtk")),
      f"3. an empty name still auto-names after the primary geometry ({out})")
cfg.output_filename = "/elsewhere/mine.vtk"
check(_mesh_output_path(cfg, "script", _REPO) == "/elsewhere/mine.vtk",
      "3. an explicit absolute name is left exactly as typed")

# ── 4. end to end: the mesher never writes a file called "<name>.*" ───────
if not os.path.exists(_BIN):
    print("SKIP 4: build/HybMesh2D not found (run ./build.sh first)", flush=True)
else:
    geom = os.path.join(_REPO, "examples", "geometries", "naca0012.dat")
    if not os.path.exists(geom):
        print(f"SKIP 4: {geom} not present", flush=True)
    else:
        with tempfile.TemporaryDirectory() as td:
            conf = os.path.join(td, "para.dat")
            with open(conf, "w") as f:
                f.write(
                    "DOMAIN_X_MIN -1.5\nDOMAIN_X_MAX 2.5\n"
                    "DOMAIN_Y_MIN -1.5\nDOMAIN_Y_MAX 1.5\n"
                    "AUTO_SURFACE_SIZE 1\nSURFACE_MESH_SIZE 0.02\n"
                    "FARFIELD_MESH_SIZE 0.4\nFARFIELD_GROWTH_RATE 0.2\n"
                    "BL_INITIAL_THICKNESS 0.001\nBL_GROWTH_RATE 1.2\nBL_LAYERS 5\n"
                    "GMSH_ALGORITHM 6\nGMSH_OPTIMIZE 1\n"
                    "EXPORT_VTK 1\nEXPORT_STARCD 1\n"
                )
            env = dict(os.environ, DYLD_LIBRARY_PATH=_LIB, LD_LIBRARY_PATH=_LIB)
            # -out_name, so the CLI override is covered as well as the config key.
            star = os.path.join(td, "probe.*")
            try:
                p = subprocess.run(
                    [_BIN, "-conf", conf, "-geom", geom, "-out_name", star],
                    cwd=td, env=env, capture_output=True, text=True, timeout=600)
                rc, log = p.returncode, p.stdout + p.stderr
            except subprocess.TimeoutExpired:
                rc, log = None, "<timed out>"
            check(rc == 0, f"4. the mesher runs with a '.*' output name (rc={rc})")
            if rc != 0:
                print(log[-1500:], flush=True)
            written = sorted(os.listdir(td))
            check("probe.vtk" in written,
                  f"4. the VTK is written as probe.vtk ({written})")
            check(all(f"probe{e}" in written for e in (".vrt", ".cel", ".bnd")),
                  f"4. the STAR-CD trio keeps the same stem ({written})")
            globs = [f for f in written if "*" in f]
            check(not globs,
                  f"4. no file is named with a literal '*' ({globs or 'none'})")
            # The banner feeds the provenance sidecar, so it must not advertise a
            # name nothing was written under.
            banner = [ln.split(":", 1)[1].strip() for ln in log.splitlines()
                      if "Output Filename" in ln]
            check(banner and banner[0].endswith("probe"),
                  f"4. the config banner reports the resolved basename ({banner})")

if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    sys.exit(1)
print("\nRESULT: ALL PASS", flush=True)
sys.exit(0)
