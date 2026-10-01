from __future__ import annotations
from dataclasses import dataclass, field

from app.models import mesh_output_names
from app.models.mesh_config_geoms import GeomListMixin
from app.models.mesh_config_validate import ConfigValidationMixin
from app.services.topology_model import TopologyModel


def _key_map() -> dict:
    """The .dat KEY map, imported at CALL time rather than at module scope.

    It is now DERIVED from the field-spec tables plus this dataclass's own field
    types (see mesh_config_keys), so it depends on MeshConfig — and MeshConfig is
    here. A module-level import would therefore be a cycle, which is the same
    hazard the separate mesh_config_keys module was split out to avoid in the first
    place; the dependency simply runs the other way now. Deferring it is safe rather
    than a smell: both use sites are methods, so by the time either runs this module
    is fully initialised, and nothing in the chain touches Qt (the tables live in
    app/services/ precisely so that stays true).

    The stale `from app.models.mesh_config import _KEY_MAP` re-export this replaced
    had no importers left — checked across app/ and tests/.
    """
    from app.models.mesh_config_keys import _KEY_MAP
    return _KEY_MAP

@dataclass
class MeshConfig(ConfigValidationMixin, GeomListMixin):
    """Every mesh parameter, declared once.

    Two mixins, each a half this file ran out of room for and each still
    reached as a method ON THIS CLASS: ``GeomListMixin`` owns the geometry
    list's identity verbs, ``ConfigValidationMixin`` the pre-flight checks
    (#159). What stays here is the DECLARATION of the parameters and their
    serialisation, which is what makes this file the one place a new mesh
    field is added.
    """

    # Section 0: Which generation PATH runs.
    # 0 = the existing hybrid path (BL quads + Gmsh far-field triangles) and the
    # default, so every case that exists today meshes exactly as it did. 1 = the
    # topology-driven multi-block path. The numbers are the mesher's
    # (include/MeshMode.hpp); app/services/mesh_modes.py is the GUI's one spelling
    # of them. Which fields each mode reads is declared per field, on its spec.
    mesh_mode: int = 0
    # The block topology document the multi-block path reads. Explicit, never
    # guessed from a name beside the geometry.
    #
    # WHEN `topology` BELOW NAMES A FAMILY, THIS FIELD IS AN OUTPUT, NOT AN INPUT:
    # the document is a PROJECTION of that model, written beside the mesher config
    # by `mesh_config_io.save_config_to_file`, and the line this field spells is the
    # path that projection went to. With no family named it is what it always was —
    # a document the user maintains by hand — and every case that predates the
    # template library meshes exactly as it did (#134).
    mesh_topology_file: str = ""
    # The topology TEMPLATE: which family, and every family's parameters. The model
    # is the truth and the JSON above is its projection; two homes for one fact is
    # the shape a per-segment BC was once bitten by, where a label and a map drifted
    # apart and exported an all-wall mesh. Default `family=""` means "no template",
    # which is the state every existing project is in.
    topology: TopologyModel = field(default_factory=TopologyModel)
    # Split every quad the multi-block path fills into two triangles before
    # export. ON by default, and not as a preference: the solver's incenter
    # reconstruction is undefined on quad cells and the grid converter's slicer
    # refuses a mixed mesh, so an all-triangle mesh is what a fully blocked
    # domain buys. Off is a diagnostic, for inspecting the quads a topology
    # actually declared.
    mb_split_quads: bool = True
    # WHICH diagonal each of those quads is cut on. The four rules and their
    # numbers are the mesher's (`MbSplitRule` in include/MultiBlock.hpp):
    # 0 = alternating by index parity, 1 = fixed forward, 2 = fixed backward,
    # 3 = randomized from a hash of (block id, i, j, seed). 0 is the default
    # because it shipped first, so a case saved before this field existed meshes
    # exactly as it did.
    mb_split_rule: int = 0
    # The seed the RANDOMIZED rule hashes, and the whole of what makes that rule
    # reproducible: the same topology and seed give byte-identical connectivity,
    # which is what keeps a randomized mesh inside the regression comparator.
    #
    # `mb_split_*` and not `seed_*`: the seed_ fields below are REFINEMENT seeds,
    # a local far-field sizing source with nothing to do with a random number.
    # Two unrelated concepts under one prefix is how a user sets the wrong one.
    mb_split_seed: int = 0
    # THE CAP on the multi-block path's elliptic (Winslow) smoother, between the
    # fill and the split. 0 runs none. `mb_smooth_iters` and not a
    # `bl_smoothing_iters` lookalike: that key is the OTHER path's collision
    # remedy, and the two share a verb and nothing else.
    #
    # 20 AND NOT 0 SINCE #85, and it MUST equal `Config::mbSmoothIters` — the
    # parity gate compares the two defaults in both directions, and a default that
    # disagrees is a mesher and a GUI producing different meshes from one document.
    # The derivation is at that C++ declaration; it is the SAFE cap rather than the
    # best one measured.
    mb_smooth_iters: int = 20

    # Section 0b: Units
    # The unit EVERY length in this config is expressed in — domain bounds, mesh
    # sizes, BL thickness, seed radii. The mesher never converts them (it only
    # compares lengths against each other), so this is a label as far as meshing is
    # concerned. It is not a label to the solver: Linf is metres-per-grid-unit and
    # Re = fs_UnitRe × Linf, so this is where a mm geometry meshed as metres turns
    # into a Reynolds number that is wrong by 1000×. See services/units.py.
    length_unit: str = "m"
    # Only meaningful when length_unit == "custom" — e.g. a unit-chord aerofoil grid
    # whose coordinates run 0…1 and whose chord is 25.4 mm.
    length_unit_metres: float = 1.0
    length_unit_name: str = ""

    # Section 1: Domain
    domain_x_min: float = -10.0
    domain_x_max: float = 10.0
    domain_y_min: float = -10.0
    domain_y_max: float = 10.0

    # Section 2: Mesh Size
    surface_mesh_size: float = 0.1
    auto_surface_size: bool = True
    farfield_mesh_size: float = 1.0
    auto_farfield_size: bool = False
    farfield_growth_rate: float = 0.1
    # #7: bidirectional far-field grading — also grow the far-field size from the
    # outer domain boundary inward, with its own rate (mesh stays fine near both
    # the body and the outer boundary, coarsest in the middle). Off = single
    # direction (body outward), the original behaviour.
    farfield_bidirectional: bool = False
    farfield_growth_rate_outer: float = 0.1

    # Section 3: Boundary Layer
    bl_initial_thickness: float = 0.01
    bl_growth_rate: float = 1.2
    bl_layers: int = 5

    # Section 4: Corner Handling (Convex & Fan)
    bl_convex_method: int = 2  # 0: Fan, 2: Parallelogram
    bl_fan_nodes: int = 5
    # 0 OFF / 1 Global Avg / 2 Local Avg — an int, matching Config.hpp and the
    # three-item combo that has always edited it. It was a `bool` until
    # 2026-08-19, so the combo's LOCAL item collapsed to 1 on the way out and
    # Local Avg was reachable only from a hand-written .dat, even though
    # BoundaryLayer.cpp has always branched on 2.
    bl_auto_fan_nodes: int = 0
    bl_fan_angle_threshold: float = 60.0
    bl_convex_angle_threshold: float = 260.0
    bl_para_fallback_angle: float = 300.0

    # Section 5: Concave Corner Handling
    bl_concave_method: int = 0  # 0: Default (Merge), 5: Thickness-based Blending
    bl_concave_angle_threshold: float = 100.0
    bl_concave_influence_multiplier: float = 2.5  # 10 over-blended: each edge's BL→far-field band came out curved; 2.5 keeps a straight uniform-height outer edge with only a short transition at the corner.
    bl_merge_concave: bool = False
    bl_smoothing_iters: int = 0

    # BL / no-BL junction: how a BL edge meeting a grow=0 neighbour is capped.
    # method 1 (default) = 4-case angle-driven scheme; the flow-facing angle θ is
    # binned by the three thresholds C1 < C2 < C3 (degrees) to pick the case.
    # method 0 = legacy taper-to-zero. See the "BL/no-BL Junction" group in
    # .claude/rules/mesher.md (moved out of CLAUDE.md by #62).
    bl_junction_method: int = 1
    bl_junction_angle_c1: float = 135.0
    bl_junction_angle_c2: float = 270.0
    bl_junction_angle_c3: float = 315.0

    # Section 6: Transition & Meshing Algorithm
    bl_transition_layers: int = 3
    bl_auto_transition_layers: int = 2  # 0: OFF, 1: GLOBAL, 2: LOCAL (#4: default LOCAL)
    bl_transition_growth_rate: float = 1.2
    bl_transition_buffer: float = 2.0
    gmsh_algorithm: int = 6  # 6: Frontal-Delaunay
    gmsh_optimize: int = 1   # 1: Enable, 0: Disable
    bl_use_analytic_geom: bool = False  # Phase 3: analytic normals on line/circle surfaces

    # Section 7: Boundary Conditions & I/O
    # Default external-flow setup: inflow on the left, geometry is a wall, the
    # remaining domain boundaries are outflow.
    bc_xmin: str = "inlet"
    bc_xmax: str = "outlet"
    bc_ymin: str = "outlet"
    bc_ymax: str = "outlet"
    bc_geom: str = "wall"
    export_vtk: bool = False
    export_starcd: bool = True
    export_cgns: bool = False
    enable_collision_detection: bool = True
    output_filename: str = ""

    # Geometry files list (corresponds to multiple GEOM_FILE parameters).
    # A geometry file stays in this list whether it is a body-fitted boundary
    # or a refinement seed; its role is recorded separately in geom_roles.
    geom_files: list[str] = field(default_factory=list)

    # Per-geometry role, keyed by the exact path stored in geom_files. Absent =
    # obstacle that grows a boundary layer (default, written as GEOM_FILE). Present
    # role dicts:
    #   {"role": "seed", "size": float|None, "radius": float|None, "mode": "source"|"embed"}
    #       -> refinement seed, written as SEED_FILE.
    #   {"role": "nobl"}
    #       -> obstacle with NO boundary layer, conform at far-field size
    #          (written as GEOM_FILE <path> nobl).
    #   {"role": "farfield"}
    #       -> outer-domain outline, no BL, external flow (DOMAIN_FILE <path> nobl).
    #   {"role": "wall"}
    #       -> outer-domain wall, BL grows inward, internal flow (DOMAIN_FILE <path> bl).
    # At most one geometry may be a domain (farfield or wall). size/radius None
    # (or <=0) => let the backend auto-resolve.
    geom_roles: dict = field(default_factory=dict)

    # #4: physical BC type assigned per CAD group/patch NAME in the Mesh Generator
    # ("Edit segment BCs…"). Keyed by the grouping label so the label itself is
    # never overwritten; the solver BC table is pre-seeded from this map. Values
    # are BC-type strings (e.g. "inlet"/"wall"/… or a free-form Custom name).
    group_bc: dict = field(default_factory=dict)

    # #3: has the user actually configured the domain boundary conditions? A
    # fresh config starts False, so the BC-Preview draws the four domain-box
    # edges NEUTRAL (grey) instead of painting the pristine inlet/outlet model
    # defaults as if the user had chosen them (which read as "weird" arbitrary
    # colours on a box they never touched). Flipped True once any domain BC is
    # edited. Loaded sessions predating this key default to True (they already
    # carry real BCs). Round-trips through to_dict/load_from_dict.
    bc_configured: bool = False

    # GEOM_FILE tokens from the last load_from_file that could not be resolved
    # to an existing file (not serialized; populated by load_from_file)
    missing_geom_files: list[str] = field(default_factory=list)

    # Output naming lives in models/mesh_output_names.py (one topic, and this
    # file's size budget); re-exported here so MeshConfig.auto_output_name(...)
    # and friends stay the API every caller already uses.
    CASE_NAME_MAX_LEN = mesh_output_names.CASE_NAME_MAX_LEN
    FORMAT_PLACEHOLDER = mesh_output_names.FORMAT_PLACEHOLDER
    clamp_case_name = staticmethod(mesh_output_names.clamp_case_name)
    auto_case_name = staticmethod(mesh_output_names.auto_case_name)
    auto_output_name = staticmethod(mesh_output_names.auto_output_name)
    output_base = staticmethod(mesh_output_names.output_base)
    output_path_for = staticmethod(mesh_output_names.output_path_for)
    is_auto_output_name = staticmethod(mesh_output_names.is_auto_output_name)

    def to_dict(self) -> dict:
        """Serialize configuration parameters to a dictionary."""
        d = {}
        for attr, _ in _key_map().values():
            d[attr] = getattr(self, attr)
        d["geom_files"] = self.geom_files
        d["geom_roles"] = self.geom_roles
        d["group_bc"] = self.group_bc
        d["bc_configured"] = self.bc_configured
        # The topology template, named here like the four above because it has no
        # `.dat` KEY for `_key_map()` to find it by — the mesher never sees a
        # parameter, it sees the document one produced (#134). Without this line the
        # project-undo snapshot (`project_state_ctrl._collect_project_state`, which
        # is `to_dict()`) could not see a template edit at all, so Ctrl+Z would be
        # the one thing that did nothing in this section.
        #
        # OPTIONAL, like `stl3d` one file over (#135): a project with no template
        # configured writes no section, so a file predating templates and a file
        # saved today by a user who never opened the section are the same file.
        # `is_configured()` owns "configured" and asks about EVERY parameter, not
        # about the family, so a number typed before the combo was touched is not
        # dropped. Its inverse is `load_from_dict` below: absent means the DEFAULT
        # model, which is what keeps the first template edit undoable.
        if self.topology.is_configured():
            d["topology"] = self.topology.to_dict()
        return d

    def load_from_dict(self, d: dict):
        """Restore configuration parameters from a dictionary.

        Values are coerced through the same converters used when parsing a .dat
        file, so a hand-written pipeline JSON that quotes a number
        (e.g. ``"bl_layers": "8"``) still lands as the right type instead of a
        str that later crashes save_to_file's numeric formatting. A value that
        can't be converted is kept as-is (no worse than a raw assignment)."""
        for attr, converter in _key_map().values():
            if attr in d:
                v = d[attr]
                try:
                    v = converter(v)
                except (TypeError, ValueError):
                    pass
                setattr(self, attr, v)
        # Through set_geom_files, not a rebind: a stale workspace is exactly the
        # dict that carries one file under two spellings, so the restore is the
        # last place that should be allowed to put that state back. Four
        # consequences, and all four are held by test_geom_files_identity.py
        # check 10 rather than by this comment: the two spellings collapse to
        # ONE entry, a falsy entry is DROPPED rather than kept, the list is a
        # copy -- `d`'s own list is no longer aliased into the config, so
        # mutating one no longer mutates the other -- and an explicit JSON null
        # lands as [] , which is the one of the four the old line also got
        # right, with `or []`.
        self.set_geom_files(d.get("geom_files"))
        # `or {}` (not the .get default) so an explicit JSON null still lands as
        # an empty container instead of None, which would crash save_to_file.
        self.geom_roles = d.get("geom_roles", {}) or {}
        self.group_bc = d.get("group_bc", {}) or {}
        # #3: a session predating this key already carries real BCs, so default
        # True (show their colours); a new session that saved it uses the value.
        self.bc_configured = bool(d.get("bc_configured", True))
        # ABSENT MEANS THE DEFAULT MODEL, in both directions (#135). A project
        # file written before templates existed has no section and must load
        # exactly as it did, which a fresh default satisfies; and because
        # `to_dict()` now OMITS the section when nothing is configured, an absent
        # section is also what the project-undo snapshot taken before the first
        # template edit looks like. Were this a no-op, undoing back to that
        # snapshot would leave the edit in place — every other field is restored by
        # being present, this one has to be restored by being absent.
        #
        # A rebind rather than an in-place reset: `to_dict`/`load_from_dict` are
        # value semantics for this section, and nothing holds the model across a
        # load (the panel reads `cfg.topology` at each `set_config`, and
        # `get_config` builds and ASSIGNS a fresh one — #134's finding).
        topo = d.get("topology")
        self.topology = TopologyModel()
        if isinstance(topo, dict):
            self.topology.load_from_dict(topo)

    def load_from_file(self, path: str):
        """Parse configuration parameters from a text file."""
        from app.models.mesh_config_io import load_config_from_file
        return load_config_from_file(self, path)

    def save_to_file(self, path: str):
        """Export parameters to a Background_para.dat format text file."""
        from app.models.mesh_config_io import save_config_to_file
        return save_config_to_file(self, path)
