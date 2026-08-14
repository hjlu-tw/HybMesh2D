"""How a mesh output is NAMED (Qt-free).

One topic, split out of ``mesh_config.py`` for its file-size budget: the `<case>`
label, the auto-generated `results/meshes/<case>/mesh_<case><ext>` path, the test
for "is this name still auto?", and the resolution of the Output field's
all-formats placeholder.

Two of these are contracts with code outside this file and must not drift:

* ``clamp_case_name`` / ``auto_case_name`` / ``auto_output_name`` are mirrored in
  ``src/cli.cpp`` — the GUI looks for the mesh at the path the mesher writes, so
  a divergence means the mesh "vanishes" after a successful run.
* ``FORMAT_PLACEHOLDER`` is understood by ``src/cli.cpp`` too, which strips it
  before it can be mistaken for a real extension.

:class:`MeshConfig` re-exports every function here as a staticmethod, so
``MeshConfig.auto_output_name(...)`` and friends keep working unchanged.
"""
from __future__ import annotations
import os

# <case> length cap, in characters. results/meshes/<case>/mesh_<case><ext> puts
# <case> in a single path component, which must stay inside the 255-byte NAME_MAX;
# 60 chars is safe even for 4-byte UTF-8 stems.
CASE_NAME_MAX_LEN = 60

# Extension the Output field wears when it stands for every enabled format at
# once (see output_base).
FORMAT_PLACEHOLDER = ".*"


def clamp_case_name(name: str) -> str:
    """Clamp a <case> label to CASE_NAME_MAX_LEN characters.

    A many-body case joins every boundary stem, which easily runs past NAME_MAX
    and makes the mesh write fail. Keep a readable prefix and disambiguate it
    with an FNV-1a digest of the full name so two long cases never collide.
    src/cli.cpp mirrors this exactly.
    """
    if len(name) <= CASE_NAME_MAX_LEN:
        return name
    h = 0x811C9DC5
    for b in name.encode("utf-8"):
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return f"{name[:CASE_NAME_MAX_LEN - 9]}_{h:08x}"


def auto_case_name(boundaries: list) -> str:
    """The <case> label used for auto-generated mesh output paths.

    Derived from the boundary geometry stems: single body -> its stem, several ->
    their stems joined, none -> "cartesian". Always clamped (see clamp_case_name)
    so the resulting path component is writable.
    """
    if not boundaries:
        return "cartesian"
    if len(boundaries) == 1:
        name = os.path.splitext(os.path.basename(boundaries[0]))[0]
    else:
        name = "_".join(os.path.splitext(os.path.basename(b))[0] for b in boundaries)
    return clamp_case_name(name)


def auto_output_name(boundaries: list, ext: str = ".vtk") -> str:
    """Auto mesh output path: results/meshes/<case>/mesh_<case><ext>.

    Each case gets its own subdirectory so results/meshes/ stays tidy instead of
    accumulating loose files at its top level.
    """
    case = auto_case_name(boundaries)
    return f"results/meshes/{case}/mesh_{case}{ext}"


def output_base(name: str) -> str:
    """`name` with its extension — or the `.*` format placeholder — removed.

    The Output field holds ONE name for however many formats are enabled, so the
    panel fills it in as `mesh_<case>.*` (`FORMAT_PLACEHOLDER`) and each writer
    substitutes its own extension. That placeholder is a WILDCARD, not an
    extension, and it reaches everything downstream verbatim — the model, the
    workspace, the pipeline script, the mesher's config file. Resolving it in one
    place is the point: the mesher used to take it literally and write the VTK
    into a file NAMED `mesh_<case>.*`, while the export dialog had its own
    private `endswith(".*")` branch and the headless runner had none.
    """
    name = (name or "").strip()
    if not name:
        return ""
    if name.endswith(FORMAT_PLACEHOLDER):
        return name[:-len(FORMAT_PLACEHOLDER)]
    return os.path.splitext(name)[0]


def output_path_for(name: str, ext: str) -> str:
    """`name` re-extensioned to `ext` (`""` for an empty name).

    `ext` includes its dot. Idempotent, so a name that already carries `ext`
    comes back unchanged.
    """
    base = output_base(name)
    return base + ext if base else ""


def is_auto_output_name(name: str) -> bool:
    """True if `name` is empty or is exactly a name this module would generate:
    the flat legacy `results/meshes/mesh_<case><ext>` or the per-case
    `results/meshes/<case>/mesh_<case><ext>`.

    Auto names are refreshed when geometry changes, so this must stay a narrow
    match: anything else — including a user's own file inside a results/meshes/
    subfolder — is a typed name and must be preserved.
    """
    if not name:
        return True
    n = name.replace("\\", "/")
    prefix = "results/meshes/"
    if not n.startswith(prefix):
        return False
    parts = n[len(prefix):].split("/")
    if len(parts) == 1:
        # Legacy flat layout: results/meshes/mesh_<case><ext>
        return parts[0].startswith("mesh_")
    if len(parts) != 2:
        return False
    # Per-case layout: the file must be that case's own mesh_<case><ext>, not
    # merely some mesh_*.vtk the user parked in the case folder.
    case, base = parts
    return os.path.splitext(base)[0] == f"mesh_{case}"
