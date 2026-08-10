# HybMesh2D

HybMesh2D is a C++ tool for generating 2D hybrid meshes. It generates high-quality boundary layers (quadrilateral meshes) around geometric boundaries and automatically fills the far-field with unstructured (triangular) meshes.

## Core Features

- **Boundary Layer Generation**: Grows quadrilateral boundary layers with specified layers and growth rates from geometric shapes (e.g., NACA0012 airfoil).
- **Multi-Geometry Support**: Supports multiple non-intersecting geometries simultaneously, each with its own boundary layer.
- **Refinement Seeds**: A geometry can be tagged as a *refinement seed* (Pointwise-like source) instead of a body-fitted boundary. A seed only drives a local minimum mesh size to refine the unstructured far-field around it — it **grows no boundary layer and is not a domain boundary**. Two modes are supported: `source` (pure sizing source, mesh does not conform) and `embed` (mesh nodes conform to the seed curve). You can freely designate which geometries are body-fitted boundaries and which are seeds. See "Refinement Seeds" below.
- **Hybrid Mesh Architecture**: Combines structured near-field (boundary layers) with unstructured far-field flexibility (triangles).
- **Fan Elements**: Automatically generates fan meshes at sharp convex corners to maintain mesh quality.
- **Concave Handling & Smoothing**: Provides concave node merging and Laplacian smoothing to prevent mesh self-intersection in complex geometries.
- **Safety Checks**: Automatically detects intersections between geometries and ensures they stay within the computational domain.
- **Gmsh Integration**: Utilizes the Gmsh SDK for robust far-field triangulation.
- **Multi-Format Export**: Supports exporting to `.vtk` (ParaView), STAR-CD (`.vrt`, `.cel`, `.bnd`), and **CGNS** (`.cgns`, unstructured zone + one BC patch per boundary) formats.
- **Geometry Association**: The preprocessor writes a `.meta` sidecar next to each resampled `.dat`, losslessly carrying per-point source segment (`seg_id`), structural corner flags (`is_corner`), per-segment boundary condition (`bc`), and curve kind (`curve_kind`). See "Geometry Metadata Sidecar" below.
- **Analytic BL Normals**: Grows the boundary layer along exact analytic normals on line/circle surfaces (instead of finite differences) for higher accuracy on curved bodies (cylinders, leading edges). Toggled by `BL_USE_ANALYTIC_GEOM` (off by default).
- **Per-Segment Boundary Conditions**: Assign a BC per segment in the GUI CAD inspector; it travels to the mesher via the sidecar. On export, each boundary edge's BC comes from a tag attached to the edge (rectangle side, custom-outline segment, or geometry segment) rather than from position-based inference; same-named boundaries merge into one group (like STAR-CCM+/Fluent named boundaries).
- **Custom Domain Shape**: The outer domain can be the rectangular box (`DOMAIN_X/Y_MIN/MAX`) or a custom closed polyline (`DOMAIN_FILE`). Polygons, circles, and sectors are all represented as resampled polylines that flow through the full BL/collision/export pipeline; each outline segment can carry its own BC via the sidecar.
- **Internal Flow (Interior Meshing)**: Mesh the *interior* of a closed CAD geometry — the boundary layer grows **inward**, triangles fill the core, and no separate far-field box is built (`DOMAIN_FILE <path> bl`). Islands can be placed inside to form an annular domain.
- **Per-Geometry Role**: Each geometry independently either grows a boundary layer (`bl`) or grows none and conforms at far-field size (`nobl`). Growth direction is deterministic: the domain wall grows inward, obstacles grow outward (no area-based heuristic).
- **Full Pipeline**: One JSON script chains CAD resampling → mesh generation → the UNICONES solver → a result contour. The GUI offers a **▶ Run All** button; `run_pipeline.sh` runs the same script headless and writes a contour PNG. Both share one schema and one set of stage logic. See "Full Pipeline" below.
- **Batch Queue**: Queue several pipeline scripts and run them back to back, from the GUI or the CLI, through one runner. The GUI's Cancel stops the **case already running**, not just the queue. See "Batch Queue" below.
- **Length Units**: The model declares one length unit (m/cm/mm/µm/in/ft/custom). This is not cosmetic — the solver is dimensional, so `Linf` is *derived* from the unit rather than typed, and the resulting reference Reynolds number is shown live on the Solver panel. See "Length Units" below.

## Mesh Architecture & Transition

HybMesh2D divides the computational domain into three main regions with smooth size transitions:

1. **Geometry Boundary**
   - User-input geometry. In external flow simulations, the interior is treated as a "hole," and the mesh starts from this boundary.

2. **Boundary Layer Region**
   - A structured region composed of **quadrilaterals** growing outward from the geometry.
   - Controlled via parameters for initial thickness, growth rate, total layers, and fan segment count.

3. **Far-field & Transition Region**
   - The space between the boundary layer's outer edge and the domain boundary, composed of **triangles** generated by Gmsh.
   - **Transition Mechanism**: The tool captures the thickness of the outermost boundary layer and passes it to Gmsh as the starting mesh size, which then expands towards `FARFIELD_MESH_SIZE` based on `FARFIELD_GROWTH_RATE`.

## System Requirements

- **Compiler**: C++17 compatible compiler (e.g., GCC, Clang, MSVC).
- **Build Tool**: CMake 3.10+.
- **Dependencies**: [Gmsh SDK](https://gmsh.info/).
- **Optional**: [CGNS](https://cgns.github.io/) (with HDF5). CMake auto-detects it; CGNS export is compiled in only when found, otherwise `exportCGNS` degrades to a no-op and the default build is unaffected. On macOS: `brew install cgns`.

> ⚠️ **CGNS / Gmsh link order**: `libgmsh` statically bundles its own CGNS (built with 32-bit `cgsize_t`) and exports the `cg_*` symbols. CMakeLists links `libcgns` *before* `libgmsh` so our `cg_*` calls bind to the correct 64-bit homebrew libcgns — do not swap this order.

## Building the Project

Run the provided build script:

```bash
./build.sh
```

The executable will be located at `build/HybMesh2D`.

## Usage

```bash
./HybMesh2D [options]
```

### Common Command-Line Arguments

- `-conf <path>`: Path to the background parameter config file (Default: `config/Background_para.dat`).
- `-geom <path1> [path2]...`: Specify one or more geometry data files (body-fitted boundaries / obstacles that grow a boundary layer).
- `-geom_nobl <path1> [path2]...`: Specify geometries that grow no boundary layer (conform at far-field size, as holes).
- `-domain <path>`: Use a custom domain-outline geometry (a closed polyline) instead of the rectangular box.
- `-domain_bl`: Treat the `-domain` geometry as a domain wall with the boundary layer growing inward (= internal flow); omit for a far-field outline (external flow).
- `-seed <path1> [path2]...`: Specify one or more *refinement seed* geometries (drive a local minimum size only; no boundary layer).
- `-seed_size <v>` / `-seed_radius <v>` / `-seed_mode <source|embed>`: Global default seed size / influence radius / mode.
- `-out_vtk <0|1>`: Enable/Disable VTK output (1: ON, 0: OFF).
- `-out_starcd <0|1>`: Enable/Disable STAR-CD output.
- `-out_cgns <0|1>`: Enable/Disable CGNS output (requires the CGNS library detected at build time).

### Execution Example (Using Example Files)

```bash
./HybMesh2D -conf examples/config/test_box.dat -geom examples/geometries/naca0012.dat
```

## Configuration Parameters (`Background_para.dat`)

### 1. Domain & Size Settings

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `DOMAIN_X_MIN` / `MAX` | X-axis range of the rectangular domain (used when `DOMAIN_FILE` is unset) | -10.0 / 10.0 |
| `DOMAIN_Y_MIN` / `MAX` | Y-axis range of the rectangular domain | -10.0 / 10.0 |
| `DOMAIN_FILE <path> [bl\|nobl]` | Custom domain outline (closed polyline). `nobl` (default) = far-field outline (no BL, external flow); `bl` = domain wall (BL grows inward, internal flow). | (none; uses box) |
| `GEOM_FILE <path> [bl\|nobl]` | Geometry / obstacle. `bl` (default) = grows a boundary layer; `nobl` = no BL, conforms at far-field size. | — |
| `SURFACE_MESH_SIZE` | Initial mesh size on the geometry surface | 0.02 |
| `AUTO_SURFACE_SIZE` | Auto-calculate starting surface size (0: OFF, 1: ON) | 1 |
| `FARFIELD_MESH_SIZE` | Maximum mesh size in the far-field | 1.0 |
| `FARFIELD_GROWTH_RATE` | Size growth rate from BL to far-field | 0.1 |

### 2. Boundary Layer (BL) Core Settings

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `BL_INITIAL_THICKNESS` | Height of the first boundary layer | 0.0002 |
| `BL_GROWTH_RATE` | Growth rate of boundary layers | 1.1 |
| `BL_LAYERS` | Total number of boundary layers | 5 |

### 3. Fan & Convex Corner Handling

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `BL_CONVEX_METHOD` | Convex handling method (0: Fan, 2: Parallelogram) | 0 |
| `BL_FAN_NODES` | Number of segments in fan elements | 5 |
| `BL_AUTO_FAN_NODES` | Auto-calculate fan nodes (0: OFF, 1: Global, 2: Local) | 1 |
| `BL_FAN_ANGLE_THRESHOLD`| Angle threshold to trigger fan elements (deg) | 60.0 |
| `BL_CONVEX_ANGLE_THRESHOLD`| External angle threshold for convex corners (deg) | 220.0 |
| `BL_PARA_FALLBACK_ANGLE`| Threshold for dual-parallelogram strategy (deg) | 300.0 |

### 4. Concave Corner Handling

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `BL_CONCAVE_METHOD` | Concave handling method (0: Merge, 5: Thickness-based Blending) | 5 |
| `BL_CONCAVE_ANGLE_THRESHOLD`| External angle threshold for concave corners (deg) | 120.0 |
| `BL_CONCAVE_INFLUENCE_MULTIPLIER`| Influence radius multiplier for concave smoothing (Method 5) | 5.0 |
| `BL_MERGE_CONCAVE` | Force merge concave nodes (0: OFF, 1: ON) | 0 |
| `BL_SMOOTHING_ITERS` | Number of Laplacian smoothing iterations | 0 |

### 5. Transition to Farfield & Gmsh

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `BL_TRANSITION_LAYERS` | Number of transition layers to far-field | 3 |
| `BL_AUTO_TRANSITION_LAYERS`| Auto-calculate transition layers (0: OFF, 1: Global) | 0 |
| `BL_TRANSITION_GROWTH_RATE`| Size growth rate during transition layers | 1.15 |
| `BL_TRANSITION_BUFFER` | Buffer multiplier for the transition region | 2.0 |
| `GMSH_ALGORITHM` | Gmsh triangulation algorithm (Default 6: Frontal-Delaunay) | 6 |
| `GMSH_OPTIMIZE` | Enable mesh optimization in Gmsh | 1 |
| `BL_USE_ANALYTIC_GEOM` | Grow BL along analytic normals on line/circle surfaces (needs `.meta` sidecar; no effect on smooth/polyline) | 0 |

### 6. I/O & Advanced Features

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `EXPORT_VTK` | Default toggle for VTK export (0/1) | 1 |
| `EXPORT_STARCD` | Default toggle for STAR-CD export (0/1) | 0 |
| `EXPORT_CGNS` | Default toggle for CGNS export (0/1; requires the CGNS library at build time) | 0 |
| `ENABLE_COLLISION_DETECTION`| Enable multi-geometry collision detection (0/1) | 1 |
| `BC_XMIN` / `XMAX` | STAR-CD boundary name strings | inlet / outlet |
| `BC_YMIN` / `YMAX` | STAR-CD boundary name strings | inlet / outlet |
| `BC_GEOM` | STAR-CD surface boundary name string | wall |
| `OUTPUT_FILENAME` | Base name for output files | (empty) |
| `LENGTH_UNIT` | Length unit of the model coordinates (`m`/`cm`/`mm`/`um`/`in`/`ft`/`custom`). The mesher **records it but never converts** (it only compares lengths with each other); it prints it in the banner, so it also lands in the provenance sidecar | m |
| `LENGTH_UNIT_METRES` | Metres per model unit, when `LENGTH_UNIT custom` | 1.0 |
| `LENGTH_UNIT_NAME` | Display name of the custom unit | (empty) |

### 7. Refinement Seeds

Tag a geometry as a *refinement seed* rather than a body-fitted boundary: a seed only drives a local minimum mesh size around itself (a Gmsh Distance + Threshold size field). It **grows no boundary layer and is not a domain boundary** — ideal for locally refining wakes, shear layers, etc. (like a Pointwise source).

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `SEED_FILE <path> [size\|auto] [radius] [mode]` | Add one seed geometry. Optional: `size` (min size at the seed), `radius` (influence radius), `mode` (`source`/`embed`). `size` and `radius` are independent; for an auto size with an explicit radius, put `auto` in the size slot (e.g. `SEED_FILE f auto 1.0 source`). Omitted fields fall back to the globals below | — |
| `SEED_SIZE` | Global default seed size (omitted/<0: auto — **follows the seed's own resampled point spacing**, matching its surface-point distribution) | auto |
| `SEED_RADIUS` | Global default influence radius (omitted: **~100×size**; beyond it the size blends back to the far field). May be set independently of size | auto |
| `SEED_MODE` | Global default mode. `source`: pure sizing source, mesh does **not** conform; `embed`: mesh nodes **conform** to the seed curve (still no boundary layer) | source |

`SEED_FILE` tokens are order-tolerant (`source`/`embed` may appear anywhere). Example:

```
GEOM_FILE examples/geometries/naca0012.dat             # body-fitted boundary
SEED_FILE examples/geometries/wake.dat 0.02 1.0 source  # wake refinement seed
```

Command line:

```bash
./HybMesh2D -geom naca0012.dat -seed wake.dat -seed_size 0.02 -seed_radius 1.0 -seed_mode source
```

In the PreProcessor GUI, use **Mesh Generator → Domain & Geometry**: select any geometry file, switch its role (Boundary / Seed) and set the seed size, influence radius, and mode. Seeds are drawn as dashed orange lines on the canvas.

### 8. BL/no-BL Junction

A *junction* is a BL-growing node whose neighbouring segment grows **no** boundary layer (`grow=0` in the `.meta` sidecar — the per-segment **No-BL** setting in the GUI's mesh stage). Using the ordinary corner bisector there tilts the growth ray toward the no-BL edge and skews, or even inverts, that cell.

| Parameter | Description | Default |
| :--- | :--- | :--- |
| `BL_JUNCTION_METHOD` | 0: taper to zero (legacy); 1: angle-driven cap | 1 |
| `BL_JUNCTION_ANGLE_C1` | (deg) retained for method 0 and config round-trip only — see the note below | 135.0 |
| `BL_JUNCTION_ANGLE_C2` | (deg) θ ≤ C2 → cap perpendicular, along the BL normal | 270.0 |
| `BL_JUNCTION_ANGLE_C3` | (deg) C2 < θ ≤ C3 → cap along the reversed neighbour edge; θ > C3 → cap perpendicular | 315.0 |

**Definition of θ**: the included angle swept from the BL edge to the no-BL edge **through the flow side**. 180° is collinear, < 180° concave, > 180° convex. Because it is defined on the flow side, internal and external flow use the same bins — nothing has to be reconfigured per case.

**Method 1 (default, angle-driven cap)**

| θ range | Growth direction |
| :--- | :--- |
| θ ≤ C2 | **Perpendicular cap** along that BL edge's own outward normal |
| C2 < θ ≤ C3 | Cap along the **reversed no-BL neighbour edge** (extension cap) |
| θ > C3 | Perpendicular cap |
| Both neighbours no-BL (isolated BL node) | Perpendicular cap |

This scheme applies **no height taper**. What stays fixed across every case is the BL's *perpendicular* total height `D_total`: a tilted cap grown to a fixed *edge length* would only reach `D_total × cos(tilt)`, dipping below the neighbouring perpendicular columns and skewing the corner — so the step is scaled by `1 / cos(tilt)` (the cosine is floored, so a very sharp concave cannot blow the column length up). A cap leaves a free **full-height lateral column** whose exposed side edges are emitted as far-field constraints, so the wedge is filled with triangles rather than covered by quads.

> **Why is C1 still here?** A concave junction (θ ≤ C1) used to be "case 1": the BL column slid *along* the no-BL neighbour edge and absorbed that segment's surface nodes. On internal-flow concave corners — a closed fluid domain growing its BL inward, i.e. the common case — this collapsed the layer onto the very wall the user had explicitly marked no-BL, and did not preserve the layer height. Concave junctions are therefore capped perpendicular too; `C1` survives only for `BL_JUNCTION_METHOD=0` and config round-trip, and changing it does not affect the default scheme.

**Method 0 (legacy, taper to zero)**: the junction node grows along its own BL edge's normal (never the bisector), and every node's layer height is scaled by a taper factor — a small floor (~12%) at the junction, ramping smoothly back to 1 over an arc-length distance into the BL interior. The outer front descends toward the surface with no cliff and the far-field mesher fills the shrinking wedge.

All four parameters are editable in the GUI under **Mesh panel → Concave section**, or in the **Edit BL** dialog.

## Visualization & Output

1. **VTK Format**: Generates `results/meshes/<case>/mesh_<case>.vtk`. View with [ParaView](https://www.paraview.org/).
2. **STAR-CD Format**: Generates a triad of files:
   - `.vrt`: Vertex coordinates.
   - `.cel`: Cell definitions (Triangles and Quads).
   - `.bnd`: Boundary condition definitions with assigned BC names (geometry edges prefer the per-segment `bc` from the sidecar, falling back to `BC_GEOM`).
3. **CGNS Format** (optional): Generates `*.cgns` (single unstructured zone with triangle/quad element sections plus one BAR_2 edge section + `BC_t` patch per boundary; BCType mapped to wall/inlet/outlet, etc.). Suitable for lossless handoff to CGNS-aware solvers. Validate with `cgnscheck`.

## Output Directory Layout & Cleanup (`results/`)

All artifacts are written under `results/` (the whole directory is `.gitignore`d) and split into subdirectories by purpose. Mesh output uses a **per-case** layout: each case gets its own folder, so the top level no longer accumulates loose files.

| Subdirectory | Contents | Regenerable |
|--------------|----------|-------------|
| `results/meshes/<case>/` | Mesh output `mesh_<case>.{vtk,vrt,cel,bnd,cgns}` and `.provenance.json` | ✅ re-run to regenerate |
| `results/solver/<case>/` | Solver case dir (`work/`, `grid/`, `dll/`); `work/binDumpZ.dat.*` is the restart zone dump | ✅ re-run (deleting `binDumpZ` loses restart) |
| `results/resampled/` | Surface-resampler output `.dat` + `.meta` | ✅ regenerate from CAD sources |
| `results/inputs/` | CAD source geometry `.dat` | ⚠️ source files, keep |
| `results/logs/`, `results/pipeline/` | Run logs, pipeline scripts | — |

`<case>` is derived from the boundary geometry filenames (single → its stem, several → stems joined, none → `cartesian`); the rule is shared by `MeshConfig.auto_output_name()` (GUI) and the `src/main.cpp` default (CLI).

**Periodic cleanup**: `results/` only grows as different cases are run (re-running the same case overwrites, it does not accumulate). To free space, use the cleanup script (dry-run by default; `--force` actually deletes; `inputs/` is always kept):

```bash
./tools/scripts/clean_results.sh            # list what would be deleted (no delete)
./tools/scripts/clean_results.sh --force    # actually delete regenerable artifacts
```

## Geometry Metadata Sidecar (Geometry Association)

On a real export the preprocessor (`surface_resampler`) writes a `.meta` sidecar next to the resampled `.dat` (plain text, parseable with `ifstream` — the mesher needs no JSON dependency). It losslessly carries what a bare-coordinate `.dat` cannot:

- `seg_id` (source segment per point), `is_corner` (structural corners the BL can trust), `piece_breaks` (disconnected pieces).
- per-segment `bc` (boundary condition, assignable per segment in the GUI) and `curve_kind` (`line`/`circle`/`smooth`/`polyline`).

The mesher then assigns geometry BCs from `bc` (instead of position inference), uses the corner flags for fan/merge decisions, and — when `BL_USE_ANALYTIC_GEOM` is on — rebuilds an analytic curve (`include/Curve.hpp`) from the actual surface points per `curve_kind` to query exact normals/curvature.

Backward compatible: a missing sidecar, field, or older format falls back to the legacy behavior. Preview runs still use `nan` separator rows and write no sidecar.

## Mesh Generator GUI Workflow

The Mesh Generator tab manages inputs through a **single geometry list**: add with `Add All` (all exported PreProcessor sessions), `Add Active`, or `Browse`; drop with `Remove`. Select a geometry and set its **Role** (mirrors the CLI/config `bl|nobl` / `DOMAIN_FILE` tokens):

| Role | Meaning |
| :--- | :--- |
| Boundary (grows BL) | A body/obstacle that grows a boundary layer (external obstacle, or internal-flow island) |
| No-BL (far-field size) | A boundary with no BL, conforming at far-field size |
| Seed (refinement source) | Refinement seed (drives local size only) |
| Domain: far-field (no BL) | This closed geometry is the outer domain (external flow, no BL) |
| Domain: wall (internal, BL in) | This closed geometry is the domain wall; the BL grows inward (internal flow) |

The **Domain Source** selector chooses `Rectangle box` (shows the X/Y Min/Max box) or `Custom geometry` (hides the box; the domain then comes from whichever geometry has a Domain role).

**Multiple bodies / annular domains:** draw each shape as its own PreProcessor session, Save & Export each, then in the Mesh Generator click `Add All` to include them all and assign a Role to each. An annular domain = the outer shape as `Domain: wall` + the inner island as `Boundary`.

## Full Pipeline (CAD → Mesh → Solver → Results)

A **single JSON script** chains the whole workflow (CAD resampling → mesh generation → the UNICONES solver → a result contour) into one action. The GUI and the headless CLI **share that script and the stage logic**, so they cannot drift apart.

**GUI:** the **▶ Run All** button at the top right (visible in every mode) runs CAD → mesh → solver for the active geometry and switches to the Results tab with the contour loaded. The **Pipeline** menu additionally offers Run / Load / Save Pipeline Script.

**Headless (no window, writes a PNG):**

```bash
./run_pipeline.sh config/pipeline/template.json              # → results/pipeline/<name>_M.png
./run_pipeline.sh config/pipeline/template.json --no-solver  # stop after meshing
```

The GUI can also load and immediately run a script at start-up:

```bash
python3 tools/PreProcessor/gui/main.py --pipeline config/pipeline/my_case.json --run
```

**Script format**: one JSON with `cads` / `mesh` / `solver` / `stl3d` / `results` sections, each mapping 1:1 onto an existing config model (`ProjectModel` / `MeshConfig` / `SolverConfig` / `Stl3dConfig`). `cads` is a *list*, so a multi-body case round-trips. Copy `config/pipeline/template.json` and change a few numbers (Mach, angle of attack, Reynolds number, iterations, BCs…). Field-by-field notes: [config/pipeline/README.md](config/pipeline/README.md).

```json
{
  "cads":   [ { "input_file": "examples/geometries/naca0012.dat", "skip": true } ],
  "mesh":   { "domain_x_min": -4, "domain_x_max": 8, "bl_layers": 15, "bc_geom": "wall" },
  "solver": { "preset": "Laminar NS (subsonic, steady)", "fs_mach": 0.3,
              "fs_flow_angle": 4.0, "fs_unit_re": 1000, "num_half_iter": 2000 },
  "results":{ "variable": "M", "save_png": "results/pipeline/case_M.png" }
}
```

> `run_pipeline.sh` sets Gmsh's `DYLD_LIBRARY_PATH` first (like `run.sh`). Solver results go to `results/solver/<case_name>/work/`, contour PNGs to `results/pipeline/`. Note that `print_sol_per_niter` must be ≤ `num_half_iter`, or the solver writes no result file.

## Batch Queue

One runner executes several pipeline scripts in sequence (`.json` scripts or `.hws` workspaces).

**Headless:**

```bash
./run_batch.sh case_a.json case_b.hws --no-solver
./run_batch.sh @manifest.txt            # manifest file, one path per line
```

**GUI: Pipeline ▸ Batch Queue…** — a modeless dialog (a queue you assembled survives closing the window) with a per-case status table:

- **Cancel stops the case already running**, not just the queue. `should_stop()` is polled only *between* cases — right for not leaving a half-written output directory, but on its own Cancel would do nothing visible for minutes or hours. So `pipeline_runner` hands the live child process of every stage up to its caller (`on_process`), and the worker kills it with SIGTERM → grace → SIGKILL over the **process group** (a stage is a process tree — mpirun ranks, gmsh helpers — and killing only the direct child orphans the rest). Both mechanisms are needed: one stops the work in flight, the other stops the queue starting the next case.
- **Case-name collisions are reported when scripts are queued**, not when the run starts. Output paths derive from the case name, so a shared name means one case silently destroying another's mesh.
- An unreadable script becomes a visible skipped row **with the reason** — a batch that quietly runs 9 of your 10 cases is worse than one that fails.

## Length Units

The model declares **one** length unit (top row of the Mesh panel, or `LENGTH_UNIT` in the config): `m` / `cm` / `mm` / `µm` / `in` / `ft` / custom.

This is not a display label — **the solver is dimensional**. Per the UNICONES manual, `fs_UnitRe` is a *per metre* unit Reynolds number and `Linf` is *metres per grid unit* (its own sample uses `Linf 0.0254` for an inch grid), so

```
Re = fs_UnitRe × Linf
```

A mesh authored in mm but left at `Linf = 1` runs at **1000×** the intended Reynolds number, on a mesh that looks perfect.

Rules:

- **`Linf` is derived from the declared unit, not typed.** A pre-existing config with a hand-set `linf` and no `length_unit` keeps derivation off on load, so its Reynolds number is preserved; `unit_check()` then reports which unit that `linf` actually implies.
- **Changing the unit relabels; it never rescales.** Only two things convert numbers: `Linf`, and coordinates at *import* (the import-unit dialog, asked once per import action, defaulting to no conversion, silent and no-op when headless).
- **Units appear as the spin box's own suffix**, never baked into label text — the suffix rides on the widget owning the number and cannot be forgotten. Only physical lengths get one; growth rates, angles and counts do not.
- The visible defence against a *plausible* wrong unit is the live **reference Reynolds number** read-out on the Solver panel, plus the `[INFO] reference Reynolds number` line from `run_pipeline.py`. The size-plausibility check only catches gross errors, and says so.
- The mesher **records but never converts** `LENGTH_UNIT` (it only compares lengths with each other); it prints it in the banner, so it also lands in the provenance sidecar.

## PreProcessor GUI Usability

- **Canvas tools (CAD toolbar)**
  - **Measure**: two clicks span a distance, reading out `d / dx / dy / angle` (four rows, fixed-width font, on a dark plate sitting on the span it measures).
  - **Snap**: grid snapping with an adjustable step.
  - **◀ / ▶**: canvas view back/forward — zoom and pan history, like a browser. One wheel-zoom or drag-pan is **one** history entry.
  - These tools are mutually exclusive: starting one leaves the other two (including the weld tool), and the toolbar toggles follow the canvas.
- **Status bar**: a persistent line showing the current stage, the selection, and any activity.
- **Geometry Statistics** (CAD sidebar, collapsed by default): point count, open/closed, bounding box, perimeter, spacing min/mean/max, and **uniformity** — the largest expansion ratio between neighbouring intervals, how many exceed the threshold, and **where**. A geometry whose neighbouring intervals jump by more than ~1.2× grows a poor boundary layer, which used to be discoverable only by generating a mesh and looking at the failure.
- **Source-file change detection**: a workspace stores each session's geometry points next to a fingerprint of the source file (size + mtime + SHA-256). If the `.dat`/`.stl` was re-exported from CAD, regenerated by a script, or hand-edited after the workspace was saved, reopening it says so — otherwise the canvas shows the saved points while the mesh stage re-reads from disk, i.e. it meshes geometry the user never saw.
- **By End Spacing**: the `tanh` and `geometric` strategies can be given the end spacing (first cell size) directly, instead of approximating it through an abstract intensity or growth ratio. (`tanh`'s spacing is now solved by bisection in `solveTanhDelta()`; the previous heuristic mapping missed the requested spacing by ~40× and required *both* ends to be set.)
- **Interface language**: **Help ▸ Language** (English / 繁體中文), applied at the next launch. Fully translated today: the always-visible chrome (menu bar + status bar). Panel field labels, dialog bodies and log messages are still English.

## License

MIT License

