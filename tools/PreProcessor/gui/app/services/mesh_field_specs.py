"""The mesh panel's field TABLE — every ``MeshConfig`` field its own widgets author.

Together with :data:`~app.services.mesh_bl_field_specs.PANEL_BL_SPECS` (the 21
boundary-layer parameters, shared with the Edit-BL dialog) this is the whole of what
``MeshConfigPanel`` declares. ``group`` says which ``_build_*`` section lays a row out,
and the gate refuses a group no builder walks — a field that is written back to the
model but has no reachable widget is the worst of the two silent failures this table
replaces.

What is deliberately NOT here, because it is not a per-field fact:

* the **geometry list** and its per-item role data (``geom_files`` / ``geom_roles`` /
  ``group_bc``), which one widget holds for many geometries;
* ``bc_configured``, a flag the BC editors set rather than a field with a widget;
* the **domain-source** combo, which selects between two ways of describing a domain
  rather than editing a value;
* the **model unit** row, whose three fields come from one ``UnitSelector``.

Those five are named in :data:`MESH_EXTRA_AUTHORED`, and the gate proves that list
equals what the panel's remaining hand-written ``get_config`` code actually assigns.
"""
from __future__ import annotations

from app.services.field_spec import FieldSpec
from app.services.mesh_modes import (
    MESH_MODE_CHOICES, MESH_MODE_HYBRID, MESH_MODE_MULTIBLOCK,
)

_GROWTH = dict(lo=0.01, hi=10.0, dec=4)
_HINT_STYLE = "color:#6fae7a; font-size:10px;"

#: Gmsh's algorithm numbers are sparse and the item text keeps its "N: " prefix, so the
#: combo reads exactly as it did when the numbers were positional.
_GMSH_ALGOS = [(1, "1: MeshAdapt"), (2, "2: Automatic"), (5, "5: Delaunay"),
               (6, "6: Frontal-Delaunay"), (7, "7: BAMG"),
               (8, "8: Frontal-Delaunay Quads")]

#: The quad-split diagonal rules. The numbers are the mesher's (``MbSplitRule`` in
#: ``include/MultiBlock.hpp``), spelled here the way ``_GMSH_ALGOS`` above spells
#: Gmsh's algorithm numbers — inline, because this combo is the only widget that
#: offers them and a second module would be one more place for the list to drift.
#: An unknown number is refused by ``Config::validate()``, never clamped, so a
#: divergence here is a loud config error rather than a mesh nobody asked for.
_MB_SPLIT_RULES = [(0, "0: Alternating by index parity"),
                   (1, "1: Fixed forward diagonal"),
                   (2, "2: Fixed backward diagonal"),
                   (3, "3: Randomized (hashed, reproducible from the seed)")]

MESH_SPECS: tuple[FieldSpec, ...] = (
    # ── Which generation path runs ───────────────────────────────────────────
    FieldSpec("mesh_mode", "choice", "Mesh Mode",
              "Which generation path runs. Hybrid grows boundary-layer quads from "
              "every geometry and fills the far field with Gmsh triangles (the "
              "default, and what every existing case uses). Multi-block fills a "
              "DECLARED block topology with structured quads and uses Gmsh "
              "nowhere. Switching the mode hides the fields the other path reads.",
              key="MESH_MODE", group="mode",
              opts=dict(choices=list(MESH_MODE_CHOICES),
                        fallback=MESH_MODE_HYBRID)),
    FieldSpec("mesh_topology_file", "path", "Topology File",
              "The block topology document (JSON) the multi-block path fills. "
              "Named explicitly rather than guessed from a filename beside the "
              "geometry: this file decides the whole mesh, and a wrong guess "
              "would be silent.",
              key="MESH_TOPOLOGY_FILE", group="mode",
              modes=(MESH_MODE_MULTIBLOCK,),
              opts=dict(caption="Select block topology file",
                        filter="Topology (*.json);;All Files (*)",
                        placeholder="(required by the multi-block mode)")),
    FieldSpec("mb_split_quads", "bool", "Split Quads to Triangles",
              "Split every quad the multi-block path fills into two triangles "
              "before export, on alternating diagonals by index parity. ON is the "
              "working setting: the solver's incenter reconstruction is UNDEFINED "
              "on quad cells and the grid converter refuses a mixed mesh, so an "
              "all-triangle mesh is what a fully blocked domain buys. Turn it off "
              "only to inspect the quads a topology actually declared — that mesh "
              "is for looking at, not for solving.",
              key="MB_SPLIT_QUADS", group="mode",
              modes=(MESH_MODE_MULTIBLOCK,)),
    FieldSpec("mb_split_rule", "choice", "Split Rule",
              "WHICH diagonal each quad is cut on. Alternating flips with (i + j) "
              "parity and is the default: a single fixed diagonal imprints its own "
              "direction on a uniform region, and this needs no seed. The two fixed "
              "rules are for a region whose flow direction is known. Randomized "
              "breaks the same directional bias without laying down parity's regular "
              "checkerboard — it is hashed from each cell's own identity (block, i, "
              "j, seed), so adding a block elsewhere leaves every other block's "
              "diagonals alone, and the seed below reproduces the mesh exactly.",
              key="MB_SPLIT_RULE", group="mode",
              modes=(MESH_MODE_MULTIBLOCK,),
              opts=dict(choices=list(_MB_SPLIT_RULES), fallback=0)),
    FieldSpec("mb_split_seed", "int", "Split Seed",
              "The seed the randomized rule hashes. The same topology and the same "
              "seed give byte-identical connectivity, so a randomized mesh can be "
              "reproduced later — it is written into the run's configuration record "
              "for that reason. Read by the randomized rule only; set beside any "
              "other rule the mesher says so rather than letting it imply a "
              "reproducibility it had no part in.",
              key="MB_SPLIT_SEED", group="mode",
              modes=(MESH_MODE_MULTIBLOCK,),
              opts=dict(lo=0, hi=2147483647)),
    FieldSpec("mb_smooth_iters", "int", "Smoothing Sweeps",
              "The MOST elliptic (Winslow) sweeps that may relax each block's "
              "INTERIOR nodes after the fill — a cap, not a count: the solve stops "
              "as soon as it has converged, and a run that reaches this number "
              "still moving says so rather than handing back a half-solved grid "
              "that looks finished. Nodes on an INTERFACE or a CUT move and are "
              "solved from both sides at once; nodes on a declared WALL and every "
              "declared CORNER are frozen, so the blocking and the geometry a "
              "corner is attached to cannot move. It improves the worst cell angle "
              "AND holds the wall first-cell height the declaration asks for — the "
              "run reports the mesh quality before and after, so both are numbers "
              "you can read rather than claims. 20 is the default: a cap with an "
              "order of magnitude of room before this solve can fold a cell, not "
              "the best value measured. Raise it on a topology you have checked; "
              "0 turns it off.",
              key="MB_SMOOTH_ITERS", group="mode",
              modes=(MESH_MODE_MULTIBLOCK,),
              opts=dict(lo=0, hi=100000)),

    # ── Domain & Geometry: the rectangular bounding box ──────────────────────
    # modes: the multi-block domain is bounded by the topology's own outer edges,
    # so the box has nothing to bound. Same declaration the mesher warns from.
    FieldSpec("domain_x_min", "sci", "Domain X Min",
              "Left boundary of the rectangular computational domain",
              key="DOMAIN_X_MIN", group="domain", modes=(MESH_MODE_HYBRID,),
              opts=dict(lo=-1e9, hi=1e9)),
    FieldSpec("domain_x_max", "sci", "Domain X Max",
              "Right boundary of the rectangular computational domain",
              key="DOMAIN_X_MAX", group="domain", modes=(MESH_MODE_HYBRID,),
              opts=dict(lo=-1e9, hi=1e9)),
    FieldSpec("domain_y_min", "sci", "Domain Y Min",
              "Bottom boundary of the rectangular computational domain",
              key="DOMAIN_Y_MIN", group="domain", modes=(MESH_MODE_HYBRID,),
              opts=dict(lo=-1e9, hi=1e9)),
    FieldSpec("domain_y_max", "sci", "Domain Y Max",
              "Top boundary of the rectangular computational domain",
              key="DOMAIN_Y_MAX", group="domain", modes=(MESH_MODE_HYBRID,),
              opts=dict(lo=-1e9, hi=1e9)),

    # ── the selected geometry's refinement-seed parameters ───────────────────
    # model=None: these write per-geometry ROLE data on the list item, not a
    # MeshConfig field. They are in the table anyway because they are physical
    # lengths, and the unit-suffix list is derived from the table — leaving them out
    # is exactly how a field silently loses its unit.
    FieldSpec("seed_size", "sci", "Seed Size",
              "Target minimum element size at the seed "
              "(0 = auto: follows the seed's own resampled point spacing).",
              model=None, group="seed", modes=(MESH_MODE_HYBRID,),
              opts=dict(lo=0.0, hi=1e4, special="auto")),
    FieldSpec("seed_radius", "sci", "Seed Radius",
              "Influence radius: beyond it the size returns to far-field "
              "(0 = auto: 100x the seed size). Can be set independently of size.",
              model=None, group="seed", modes=(MESH_MODE_HYBRID,),
              opts=dict(lo=0.0, hi=1e6, special="auto")),

    # ── Mesh Sizing ─────────────────────────────────────────────────────────
    FieldSpec("surface_mesh_size", "sci", "Surface Size",
              "Target element size along the geometry boundary walls. "
              "Accepts scientific notation (e.g. 5e-5).",
              key="SURFACE_MESH_SIZE", group="sizing", opts=dict(lo=0.0, hi=1e6)),
    FieldSpec("auto_surface_size", "bool", "Auto Surface Sizing",
              "Automatically determine surface mesh size from geometry spacing",
              key="AUTO_SURFACE_SIZE", group="sizing", opts=dict(text="Auto Surface Sizing")),
    # A derived read-out: the size the mesher will pick, shown only while Auto is on.
    FieldSpec("auto_surface_hint", "label", "", "",
              model=None, group="sizing",
              opts=dict(bare=True, hidden=True, style=_HINT_STYLE)),
    FieldSpec("farfield_mesh_size", "sci", "Far-field Size",
              "Target element size in the far-field region away from geometry. "
              "Accepts scientific notation (e.g. 2.5e-3).",
              key="FARFIELD_MESH_SIZE", group="sizing", modes=(MESH_MODE_HYBRID,),
              opts=dict(lo=0.0, hi=1e6)),
    FieldSpec("auto_farfield_size", "bool", "Auto Far-field Sizing",
              "Automatically determine the far-field mesh size from the domain "
              "extent (the manual value stays as a fallback).",
              key="AUTO_FARFIELD_SIZE", group="sizing", modes=(MESH_MODE_HYBRID,),
              opts=dict(text="Auto Far-field Sizing")),
    FieldSpec("auto_farfield_hint", "label", "", "",
              model=None, group="sizing", modes=(MESH_MODE_HYBRID,),
              opts=dict(bare=True, hidden=True, style=_HINT_STYLE)),
    FieldSpec("farfield_growth_rate", "float", "Growth Rate",
              "Rate of element size expansion from the body/BL outward to the "
              "far-field (0.0~1.0)",
              key="FARFIELD_GROWTH_RATE", group="sizing", modes=(MESH_MODE_HYBRID,),
              opts=dict(_GROWTH)),
    FieldSpec("farfield_bidirectional", "bool",
              "Bidirectional (grade from outer boundary too)",
              "Grade the far-field size from BOTH sides: the body/BL outward AND the "
              "outer domain boundary inward, each with its own growth rate (finest "
              "near both, coarsest in the middle). Off = grow only from the body.",
              key="FARFIELD_BIDIRECTIONAL", group="sizing", modes=(MESH_MODE_HYBRID,),
              opts=dict(text="Bidirectional (grade from outer boundary too)")),
    FieldSpec("farfield_growth_rate_outer", "float", "Outer Growth Rate",
              "Rate of element size expansion inward from the outer domain boundary "
              "(bidirectional only)",
              key="FARFIELD_GROWTH_RATE_OUTER", group="sizing", modes=(MESH_MODE_HYBRID,),
              opts=dict(_GROWTH)),

    # ── Meshing Algorithm (global-only; not per-geometry BL) ─────────────────
    FieldSpec("gmsh_algorithm", "choice", "Gmsh Algorithm",
              "Meshing algorithm used by Gmsh for far-field triangulation",
              key="GMSH_ALGORITHM", group="meshing", modes=(MESH_MODE_HYBRID,),
              opts=dict(choices=list(_GMSH_ALGOS), fallback=6)),
    # as_int: GMSH_OPTIMIZE is an int flag in MeshConfig and in Config.hpp, so the
    # checkbox must report 0/1 rather than a bool the .dat writer would spell "True".
    FieldSpec("gmsh_optimize", "bool", "Optimize Mesh Quality",
              "Enable Gmsh mesh quality optimization pass after generation",
              key="GMSH_OPTIMIZE", group="meshing", modes=(MESH_MODE_HYBRID,),
              opts=dict(text="Optimize Mesh Quality", as_int=True)),
    FieldSpec("bl_merge_concave", "bool", "Merge Concave",
              "Merge nearby concave corners into a single correction zone",
              key="BL_MERGE_CONCAVE", group="meshing", modes=(MESH_MODE_HYBRID,),
              opts=dict(text="Merge Concave")),
    FieldSpec("bl_smoothing_iters", "int", "Smoothing Iters",
              "Number of Laplacian smoothing passes applied to BL cells near "
              "concave corners",
              key="BL_SMOOTHING_ITERS", group="meshing", modes=(MESH_MODE_HYBRID,),
              opts=dict(lo=0, hi=100)),

    # ── Domain boundary patches (rectangle-box edges only) ───────────────────
    FieldSpec("bc_xmin", "bcname", "XMin patch",
              "Patch name for the left domain-box edge",
              key="BC_XMIN", group="patches"),
    FieldSpec("bc_xmax", "bcname", "XMax patch",
              "Patch name for the right domain-box edge",
              key="BC_XMAX", group="patches"),
    FieldSpec("bc_ymin", "bcname", "YMin patch",
              "Patch name for the bottom domain-box edge",
              key="BC_YMIN", group="patches"),
    FieldSpec("bc_ymax", "bcname", "YMax patch",
              "Patch name for the top domain-box edge",
              key="BC_YMAX", group="patches"),

    # ── Output ──────────────────────────────────────────────────────────────
    # host_writes: population is a heuristic, not a copy — an auto-generated name is
    # refreshed from the current geometry while a name the user typed is kept, and the
    # rule reads the widget's own text, so writing it here first would destroy the
    # state it branches on. FORMAT_PLACEHOLDER (".*") enters the model through this
    # field and is a wildcard, not an extension (see models/mesh_output_names.py).
    FieldSpec("output_filename", "text", "Output File",
              "Base filename for mesh output files (extension .* means all formats)",
              key="OUTPUT_FILENAME", group="output", opts=dict(host_writes=True)),
    FieldSpec("enable_collision_detection", "bool", "Collision Detection",
              "Enable self-intersection detection during boundary layer generation",
              key="ENABLE_COLLISION_DETECTION", group="output",
              opts=dict(text="Collision Detection")),
    # The three write formats are checkable BUTTONS stacked under one "Formats:"
    # label, so the output builder assembles their row itself; the widgets, their
    # ranges and their model fields still come from here.
    FieldSpec("export_vtk", "toggle", "VTK",
              "Write a .vtk file when the mesh is generated/saved.",
              key="EXPORT_VTK", group="formats", opts=dict(text="VTK")),
    FieldSpec("export_starcd", "toggle", "STAR-CD",
              "Write STAR-CD files (.vrt/.cel/.bnd) when the mesh is generated/saved "
              "(required for the solver).",
              key="EXPORT_STARCD", group="formats", opts=dict(text="STAR-CD")),
    FieldSpec("export_cgns", "toggle", "CGNS",
              "Write a CGNS file (.cgns; unstructured zone + per-BC patches) when the "
              "mesh is generated. Ignored if HybMesh2D was built without the CGNS "
              "library.",
              key="EXPORT_CGNS", group="formats", opts=dict(text="CGNS")),
)

#: MeshConfig fields the panel authors OUTSIDE the table. Each is a fact one widget
#: holds for many things, or a flag with no widget at all — see the module docstring.
#: Gated by tests/test_field_spec_tables.py against what get_config really assigns.
MESH_EXTRA_AUTHORED = frozenset({
    # One UnitSelector row declares all three.
    "length_unit", "length_unit_metres", "length_unit_name",
    # The geometry list: one QListWidget, one entry per geometry, roles in item data.
    "geom_files", "geom_roles",
    # Label -> BC-type map, keyed by LABEL rather than by segment, self-healed from
    # each geometry's .meta trailer.
    "group_bc",
    # Set by the BC editors when the user first chooses a domain BC, so the preview
    # can tell "untouched" from "deliberately wall".
    "bc_configured",
})
