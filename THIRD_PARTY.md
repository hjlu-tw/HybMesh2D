# Third-Party Dependencies (SBOM-lite)

This file records the third-party components HybMesh2D depends on, how they are
obtained, and the versions this project targets. It is a lightweight
software bill of materials (SBOM) for auditing and reproducibility.

Last reviewed: 2026-07-14.

## Bundled (vendored in-tree)

| Component | Version | Location | Upstream | License |
|-----------|---------|----------|----------|---------|
| nlohmann/json (single-header) | 3.12.0 | `tools/PreProcessor/include/json.hpp` | https://github.com/nlohmann/json | MIT |

The `json.hpp` header is committed directly into the repository (no submodule /
package manager). To update, replace the file with a new single-header release
and bump the version above; the header self-reports its version via the
`NLOHMANN_JSON_VERSION_MAJOR/MINOR/PATCH` macros.

## C/C++ external libraries (system / SDK)

| Component | Version target | How obtained | Discovery |
|-----------|----------------|--------------|-----------|
| Gmsh SDK (gmsh.h + libgmsh) | 4.15.x | pip `gmsh` wheel, or a manual Gmsh SDK download | CMake `find_path`/`find_library` (override with `-DGMSH_ROOT=`) |
| CGNS | 4.x (dev machine: 4.5.2) | system package (e.g. Homebrew `cgns`) | CMake `find_path`/`find_library`; **optional** — build degrades to a no-op `exportCGNS` stub if absent |

Notes:
- **Gmsh** is a hard dependency of the `HybMesh2D` binary. The pip `gmsh` wheel
  installs both the Python bindings and the native library (`libgmsh.*`); the
  C++ side links against `libgmsh` and the shell run scripts add its directory
  to `DYLD_LIBRARY_PATH`/`LD_LIBRARY_PATH` at runtime. The version pinned for
  the Python side (`gmsh>=4.15,<4.16`) matches the library the C++ code links.
- **CGNS** is optional. `libcgns` must be linked *before* `libgmsh` because
  Gmsh statically bundles a 32-bit-`cgsize_t` copy of CGNS and exports the
  `cg_*` symbols; the CMake link order enforces this (see `CMakeLists.txt`).

## Python runtime dependencies

Declared in `tools/PreProcessor/gui/requirements.txt`. Requires **Python >= 3.9**.

| Package | Pin | Used by |
|---------|-----|---------|
| PyQt6 | `>=6.5.0,<7.0.0` | GUI toolkit |
| pyqtgraph | `>=0.13.0,<0.14.0` | interactive geometry/mesh canvas |
| numpy | `>=1.20.0,<2.0.0` | numerics throughout |
| scipy | `>=1.7.0,<2.0.0` | `phi_quality` mesh-quality metrics |
| matplotlib | `>=3.5.0,<4.0.0` | `contour_render`, `result_canvas`, `visualize_dat`, `wall_qty_view`, `stl3d_canvas` |
| gmsh | `>=4.15,<4.16` | native meshing SDK + Python bindings (provides `libgmsh`) |

For reproducible installs, generate a pinned lockfile from a known-good
environment (`pip freeze > requirements.lock.txt`) and install from that in CI.

## Build-time provenance

`CMakeLists.txt` reads the git short SHA at configure time (read-only,
optional — falls back to `unknown` if git is unavailable) and passes it plus the
project version into the `HybMesh2D` binary as `HYBMESH_GIT_SHA` /
`HYBMESH_VERSION` compile definitions, so produced meshes can be traced back to
the exact source revision.
