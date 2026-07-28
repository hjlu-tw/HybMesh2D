from __future__ import annotations
import os
from dataclasses import dataclass, field

# Re-exported so existing `from app.models.mesh_config import _KEY_MAP` imports
# and the to_dict/load_from_dict references below keep working; the canonical
# definition lives in mesh_config_keys.py (shared with mesh_config_io.py).
from app.models.mesh_config_keys import _KEY_MAP

@dataclass
class MeshConfig:
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
    bl_auto_fan_nodes: bool = False
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
    # method 0 = legacy taper-to-zero. See CLAUDE.md "BL/no-BL Junction".
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

    def to_dict(self) -> dict:
        """Serialize configuration parameters to a dictionary."""
        d = {}
        for attr, _ in _KEY_MAP.values():
            d[attr] = getattr(self, attr)
        d["geom_files"] = self.geom_files
        d["geom_roles"] = self.geom_roles
        d["group_bc"] = self.group_bc
        d["bc_configured"] = self.bc_configured
        return d

    def load_from_dict(self, d: dict):
        """Restore configuration parameters from a dictionary.

        Values are coerced through the same converters used when parsing a .dat
        file, so a hand-written pipeline JSON that quotes a number
        (e.g. ``"bl_layers": "8"``) still lands as the right type instead of a
        str that later crashes save_to_file's numeric formatting. A value that
        can't be converted is kept as-is (no worse than a raw assignment)."""
        for attr, converter in _KEY_MAP.values():
            if attr in d:
                v = d[attr]
                try:
                    v = converter(v)
                except (TypeError, ValueError):
                    pass
                setattr(self, attr, v)
        # `or []`/`or {}` (not the .get default) so an explicit JSON null still
        # lands as an empty container instead of None, which would crash
        # save_to_file's `for gf in self.geom_files` iteration.
        self.geom_files = d.get("geom_files") or []
        self.geom_roles = d.get("geom_roles", {}) or {}
        self.group_bc = d.get("group_bc", {}) or {}
        # #3: a session predating this key already carries real BCs, so default
        # True (show their colours); a new session that saved it uses the value.
        self.bc_configured = bool(d.get("bc_configured", True))

    # ── Per-geometry role helpers ─────────────────────────────────────────
    # Roles live in geom_roles (keyed by the path in geom_files). These helpers
    # are the single place that queries a role, and they tolerate a relative vs
    # absolute spelling mismatch so a seed role is not silently lost/misapplied.
    def role_of(self, path: str) -> dict | None:
        r = self.geom_roles.get(path)
        if r is None:
            r = self.geom_roles.get(os.path.abspath(path))
        return r

    def _role_name(self, path: str) -> str | None:
        r = self.role_of(path)
        return r.get("role") if r else None

    @staticmethod
    def _parse_bl_token(tok: str):
        """Parse a 'KEY=VALUE' BL-override token; returns (KEY, float) or None."""
        if "=" not in tok:
            return None
        k, _, v = tok.partition("=")
        if not k:
            return None
        try:
            return (k, float(v))
        except ValueError:
            return None

    def bl_params_of(self, path: str) -> dict:
        """Per-geometry BL parameter overrides for `path` ({} if none)."""
        r = self.role_of(path)
        return dict(r.get("bl_params") or {}) if r else {}

    def bc_of(self, path: str) -> str:
        """Per-geometry wall BC override for `path` ("" if none)."""
        r = self.role_of(path)
        return (r.get("bc") or "") if r else ""

    def is_seed(self, path: str) -> bool:
        return self._role_name(path) == "seed"

    def is_nobl(self, path: str) -> bool:
        """No-BL obstacle: conforms at far-field size, grows no boundary layer."""
        return self._role_name(path) == "nobl"

    def is_farfield(self, path: str) -> bool:
        """Custom outer-domain outline with NO boundary layer (external flow)."""
        return self._role_name(path) == "farfield"

    def is_wall(self, path: str) -> bool:
        """Domain wall whose boundary layer grows inward (internal flow)."""
        return self._role_name(path) == "wall"

    def is_domain(self, path: str) -> bool:
        """This geometry is the outer computational-domain outline (far-field or wall)."""
        return self._role_name(path) in ("farfield", "wall")

    @property
    def domain_file(self) -> str | None:
        """The single custom outer-domain outline, if one is defined."""
        for g in self.geom_files:
            if self.is_domain(g):
                return g
        return None

    @property
    def boundary_files(self) -> list:
        """geom_files used for output naming: obstacle/no-BL bodies, excluding
        refinement seeds and the outer-domain outline."""
        return [g for g in self.geom_files if not self.is_seed(g) and not self.is_domain(g)]

    @property
    def seed_files(self) -> list:
        """geom_files that are refinement seeds."""
        return [g for g in self.geom_files if self.is_seed(g)]

    @staticmethod
    def auto_case_name(boundaries: list) -> str:
        """The <case> label used for auto-generated mesh output paths.

        Derived from the boundary geometry stems: single body -> its stem,
        several -> their stems joined, none -> "cartesian"."""
        if not boundaries:
            return "cartesian"
        if len(boundaries) == 1:
            return os.path.splitext(os.path.basename(boundaries[0]))[0]
        return "_".join(os.path.splitext(os.path.basename(b))[0] for b in boundaries)

    @staticmethod
    def auto_output_name(boundaries: list, ext: str = ".vtk") -> str:
        """Auto mesh output path: results/meshes/<case>/mesh_<case><ext>.

        Each case gets its own subdirectory so results/meshes/ stays tidy
        instead of accumulating loose files at its top level."""
        case = MeshConfig.auto_case_name(boundaries)
        return f"results/meshes/{case}/mesh_{case}{ext}"

    @staticmethod
    def is_auto_output_name(name: str) -> bool:
        """True if `name` is empty or matches an auto-generated mesh path (the
        flat legacy `results/meshes/mesh_*` or the per-case
        `results/meshes/<case>/mesh_*`). Auto names are refreshed when geometry
        changes; a name the user typed is preserved."""
        if not name:
            return True
        n = name.replace("\\", "/")
        return n.startswith("results/meshes/") and os.path.basename(n).startswith("mesh_")

    def prune_roles(self):
        """Drop geom_roles entries whose path is no longer in geom_files, so a
        stale seed role can't silently re-attach when a path is added again."""
        present = set(self.geom_files) | {os.path.abspath(g) for g in self.geom_files}
        self.geom_roles = {k: v for k, v in self.geom_roles.items() if k in present}

    def load_from_file(self, path: str):
        """Parse configuration parameters from a text file."""
        from app.models.mesh_config_io import load_config_from_file
        return load_config_from_file(self, path)

    def save_to_file(self, path: str):
        """Export parameters to a Background_para.dat format text file."""
        from app.models.mesh_config_io import save_config_to_file
        return save_config_to_file(self, path)
