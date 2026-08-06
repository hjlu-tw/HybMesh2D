# Pipeline scripts (CAD → mesh → solver → contour)

One JSON file drives the whole chain. Run it two ways:

```bash
# Headless — no window, writes a contour PNG at the end
./run_pipeline.sh config/pipeline/template.json          # -> results/pipeline/<name>_M.png
./run_pipeline.sh config/pipeline/template.json --no-solver   # stop after meshing

# GUI — open, auto-load the script, auto-run, ends on the Results contour
python3 tools/PreProcessor/gui/main.py --pipeline config/pipeline/template.json --run
```

(No `DYLD_LIBRARY_PATH` needed: the GUI resolves the libgmsh directory itself and
hands it to the mesher. Override with `HYBMESH_GMSH_LIB_DIR` for a non-standard
gmsh install.)

In the GUI you can also use **Pipeline ▸ Load Pipeline Script**, then click **▶ Run All** (top-right).
**Pipeline ▸ Save Pipeline Script** writes your current CAD + mesh + solver settings back out to a file like these.

`template.json` is a ready-to-copy starting point. Copy it, rename `name` / `case_name`, and change the numbers below.

> JSON has no comments — keep this file valid JSON. This README is the field reference.

---

## The knobs you'll usually change

### Flow conditions — `solver`
| Field | Meaning | Typical |
|---|---|---|
| `fs_mach` | Free-stream Mach number | 0.1–0.8 subsonic, >1 supersonic |
| `fs_flow_angle` | **Angle of attack (deg)** | 0, 2, 4, … |
| `fs_unit_re` | Unit Reynolds number (per `linf`). Re ≈ `fs_unit_re × linf` | 1e3 laminar … 1e6 turbulent |
| `fs_tinf` | Free-stream temperature (K) | 288 |
| `linf` | Reference length (chord) | 1.0 |
| `gamma`, `prandtl` | Gas ratio / Prandtl no. | 1.4 / 0.72 |
| `num_half_iter` | CESE half-iterations — raise for more convergence | 2000–20000 |
| `print_sol_per_niter` | Write a Tecplot solution every N iters (**must be ≤ `num_half_iter`** or no result is written) | 500 |
| `print_convg_per_niter` | Echo residuals every N iters (drives the live monitor) | 50 |
| `cfl`, `constant_cfl` | Time-step control | 0.6 / true |
| `case_name` | Output folder `results/solver/<case_name>/` | — |

### Physics model — `solver`
- `preset` (applied first, then your explicit fields override it). Available:
  `"Laminar NS (subsonic, steady)"`, `"Euler (inviscid)"`, `"RANS k-omega SST (steady)"`,
  `"Supersonic + shock capturing"`, `"Time-accurate (TALTS)"`.
  Presets set the stability-critical numerics (`alpha`/`beta`/`dissip_ctrl`/`epsilon`), so keep one.
- `flow_solu_type`: `ns_sol` (viscous) or `euler_sol` (inviscid).
- `turb_model_option`: `laminar`, `sa_model`, `komega_wilcox`, `komega_sst`, `k-epsilon`, `smagorinsky`, `dsm_model`.
  For a turbulent RANS first run also add `"construct_wall_dist_db": true`.

### Mesh — `mesh`
| Field | Meaning |
|---|---|
| `domain_x_min/max`, `domain_y_min/max` | Outer domain box (external flow) |
| `surface_mesh_size`, `auto_surface_size` | Body surface spacing (auto = derive from last BL layer) |
| `farfield_mesh_size`, `farfield_growth_rate` | Far-field triangle size / growth |
| `bl_initial_thickness`, `bl_growth_rate`, `bl_layers` | Boundary-layer first cell / growth / count |
| `bl_transition_layers` | Extra transition quads to the far field |
| `bc_geom` | Body BC: `wall` (external) |
| `bc_xmin/xmax/ymin/ymax` | Domain-edge BCs: `inlet`, `outlet`, `farfield`, `symmetry`, `wall` |

### Geometry — `cads` (a list, one entry per geometry)
```json
"cads": [
  { "input_file": "examples/geometries/slat.dat", "is_closed": true, "skip": true },
  { "input_file": "examples/geometries/flap.dat", "is_closed": true, "skip": true }
]
```
- `input_file`: a `.dat` (space-separated `x y` per line), path relative to the repo root.
- `skip: true` — use the `.dat` directly as the mesh boundary (recommended when it is already well resolved).
- To **resample** as part of the pipeline: open the geometry in the GUI (it auto-detects edges and lets you pick per-edge spacing), then **Save Pipeline Script** — it writes a `segments` block and sets `skip: false`. With segments present, resampling runs in both GUI and headless. (GUI **Run All** always resamples and auto-detects edges even without a `segments` block; headless resamples only when `segments` are present.)
- **Multi-body cases** (multi-element wing, body + ground plane) list several entries. Each is resampled independently and **all** outputs become mesh boundaries, in list order — the mesher keys per-geometry roles and BL overrides by path and names the mesh after the first entry, so the order is part of the case. See `multi_element_demo.json`.
- **Singular `cad`** (one object instead of `cads`) is still accepted, so pre-v2 scripts and hand-written single-geometry scripts keep working. Saving rewrites it as `cads`.

### Immersed solid — `stl3d` (optional)
A subset of the Immersed Solid panel's fields (STL path, domain box, resolution, case name). Loading a script applies it to that panel. The headless runner does **not** execute this stage — it says so and continues — so generate the phi field from the GUI's **Immersed Solid** stage, or beforehand.

### Running a saved workspace instead of a script
`run_pipeline.sh` also accepts a `.hws` workspace saved by the GUI (recognised by its contents, not its extension):
```bash
./run_pipeline.sh my_case.hws --no-solver
```
Every CAD session in the workspace becomes one resample stage, and its Mesh / Solver / Immersed-Solid configuration is used as-is. Machine-specific solver paths are stripped so the run re-links to the mesh it just produced. View-only state (cached resampled points, selection, active tab) is ignored — it is derived, not input.

### Results — `results`
| Field | Meaning |
|---|---|
| `variable` | Field to contour: `M` (Mach), `p`, `T`, `` `r `` (density), `u`, `v`, `vort` |
| `cmap` | Any matplotlib colormap (`jet`, `viridis`, `coolwarm`, …) |
| `save_png` | Headless output PNG path (GUI shows it in the Results tab instead) |
| `mesh_overlay` | Draw the mesh wireframe over the contour |

---

## Advanced: solver boundary conditions (`solver.bc_definitions`)
Leave `[]` to use the defaults getPGrid derives from the mesh `.bnd` (what the template does).
To override, list `{ "segment_no": <int>, "bc_type": <flag>, "values": "<extra>" }` per boundary segment.
Common `bc_type` flags: `0` slip/inviscid wall, `2` no-slip adiabatic wall, `3` no-slip isothermal
(`values` = wall T), `1` far-field, `5` fixed freestream, `7` periodic, `11` user DLL (`values` = .so path).
Segment numbers come from the generated mesh, so set these after inspecting the mesh in the GUI.
