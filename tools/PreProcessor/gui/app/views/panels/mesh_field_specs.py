"""The mesh panel's field TABLE — every ``MeshConfig`` field its own widgets author.

Together with :data:`~app.views.panels.mesh_bl_field_specs.PANEL_BL_SPECS` (the 21
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

_GROWTH = dict(lo=0.01, hi=10.0, dec=4)
_HINT_STYLE = "color:#6fae7a; font-size:10px;"

#: Gmsh's algorithm numbers are sparse and the item text keeps its "N: " prefix, so the
#: combo reads exactly as it did when the numbers were positional.
_GMSH_ALGOS = [(1, "1: MeshAdapt"), (2, "2: Automatic"), (5, "5: Delaunay"),
               (6, "6: Frontal-Delaunay"), (7, "7: BAMG"),
               (8, "8: Frontal-Delaunay Quads")]

MESH_SPECS: tuple[FieldSpec, ...] = (
    # ── Domain & Geometry: the rectangular bounding box ──────────────────────
    FieldSpec("domain_x_min", "sci", "Domain X Min",
              "Left boundary of the rectangular computational domain",
              group="domain", opts=dict(lo=-1e9, hi=1e9)),
    FieldSpec("domain_x_max", "sci", "Domain X Max",
              "Right boundary of the rectangular computational domain",
              group="domain", opts=dict(lo=-1e9, hi=1e9)),
    FieldSpec("domain_y_min", "sci", "Domain Y Min",
              "Bottom boundary of the rectangular computational domain",
              group="domain", opts=dict(lo=-1e9, hi=1e9)),
    FieldSpec("domain_y_max", "sci", "Domain Y Max",
              "Top boundary of the rectangular computational domain",
              group="domain", opts=dict(lo=-1e9, hi=1e9)),

    # ── the selected geometry's refinement-seed parameters ───────────────────
    # model=None: these write per-geometry ROLE data on the list item, not a
    # MeshConfig field. They are in the table anyway because they are physical
    # lengths, and the unit-suffix list is derived from the table — leaving them out
    # is exactly how a field silently loses its unit.
    FieldSpec("seed_size", "sci", "Seed Size",
              "Target minimum element size at the seed "
              "(0 = auto: follows the seed's own resampled point spacing).",
              model=None, group="seed", opts=dict(lo=0.0, hi=1e4, special="auto")),
    FieldSpec("seed_radius", "sci", "Seed Radius",
              "Influence radius: beyond it the size returns to far-field "
              "(0 = auto: 100x the seed size). Can be set independently of size.",
              model=None, group="seed", opts=dict(lo=0.0, hi=1e6, special="auto")),

    # ── Mesh Sizing ─────────────────────────────────────────────────────────
    FieldSpec("surface_mesh_size", "sci", "Surface Size",
              "Target element size along the geometry boundary walls. "
              "Accepts scientific notation (e.g. 5e-5).",
              group="sizing", opts=dict(lo=0.0, hi=1e6)),
    FieldSpec("auto_surface_size", "bool", "Auto Surface Sizing",
              "Automatically determine surface mesh size from geometry spacing",
              group="sizing", opts=dict(text="Auto Surface Sizing")),
    # A derived read-out: the size the mesher will pick, shown only while Auto is on.
    FieldSpec("auto_surface_hint", "label", "", "",
              model=None, group="sizing",
              opts=dict(bare=True, hidden=True, style=_HINT_STYLE)),
    FieldSpec("farfield_mesh_size", "sci", "Far-field Size",
              "Target element size in the far-field region away from geometry. "
              "Accepts scientific notation (e.g. 2.5e-3).",
              group="sizing", opts=dict(lo=0.0, hi=1e6)),
    FieldSpec("auto_farfield_size", "bool", "Auto Far-field Sizing",
              "Automatically determine the far-field mesh size from the domain "
              "extent (the manual value stays as a fallback).",
              group="sizing", opts=dict(text="Auto Far-field Sizing")),
    FieldSpec("auto_farfield_hint", "label", "", "",
              model=None, group="sizing",
              opts=dict(bare=True, hidden=True, style=_HINT_STYLE)),
    FieldSpec("farfield_growth_rate", "float", "Growth Rate",
              "Rate of element size expansion from the body/BL outward to the "
              "far-field (0.0~1.0)",
              group="sizing", opts=dict(_GROWTH)),
    FieldSpec("farfield_bidirectional", "bool",
              "Bidirectional (grade from outer boundary too)",
              "Grade the far-field size from BOTH sides: the body/BL outward AND the "
              "outer domain boundary inward, each with its own growth rate (finest "
              "near both, coarsest in the middle). Off = grow only from the body.",
              group="sizing",
              opts=dict(text="Bidirectional (grade from outer boundary too)")),
    FieldSpec("farfield_growth_rate_outer", "float", "Outer Growth Rate",
              "Rate of element size expansion inward from the outer domain boundary "
              "(bidirectional only)",
              group="sizing", opts=dict(_GROWTH)),

    # ── Meshing Algorithm (global-only; not per-geometry BL) ─────────────────
    FieldSpec("gmsh_algorithm", "choice", "Gmsh Algorithm",
              "Meshing algorithm used by Gmsh for far-field triangulation",
              key="GMSH_ALGORITHM", group="meshing",
              opts=dict(choices=list(_GMSH_ALGOS), fallback=6)),
    # as_int: GMSH_OPTIMIZE is an int flag in MeshConfig and in Config.hpp, so the
    # checkbox must report 0/1 rather than a bool the .dat writer would spell "True".
    FieldSpec("gmsh_optimize", "bool", "Optimize Mesh Quality",
              "Enable Gmsh mesh quality optimization pass after generation",
              key="GMSH_OPTIMIZE", group="meshing",
              opts=dict(text="Optimize Mesh Quality", as_int=True)),
    FieldSpec("bl_merge_concave", "bool", "Merge Concave",
              "Merge nearby concave corners into a single correction zone",
              key="BL_MERGE_CONCAVE", group="meshing",
              opts=dict(text="Merge Concave")),
    FieldSpec("bl_smoothing_iters", "int", "Smoothing Iters",
              "Number of Laplacian smoothing passes applied to BL cells near "
              "concave corners",
              key="BL_SMOOTHING_ITERS", group="meshing", opts=dict(lo=0, hi=100)),

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
