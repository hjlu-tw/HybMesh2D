from __future__ import annotations
import os
from dataclasses import dataclass, field

_KEY_MAP = {
    "DOMAIN_X_MIN": ("domain_x_min", float),
    "DOMAIN_X_MAX": ("domain_x_max", float),
    "DOMAIN_Y_MIN": ("domain_y_min", float),
    "DOMAIN_Y_MAX": ("domain_y_max", float),
    "SURFACE_MESH_SIZE": ("surface_mesh_size", float),
    "AUTO_SURFACE_SIZE": ("auto_surface_size", lambda s: int(s) != 0),
    "FARFIELD_MESH_SIZE": ("farfield_mesh_size", float),
    "AUTO_FARFIELD_SIZE": ("auto_farfield_size", lambda s: int(s) != 0),
    "FARFIELD_GROWTH_RATE": ("farfield_growth_rate", float),
    "FARFIELD_BIDIRECTIONAL": ("farfield_bidirectional", lambda s: int(s) != 0),
    "FARFIELD_GROWTH_RATE_OUTER": ("farfield_growth_rate_outer", float),
    "BL_INITIAL_THICKNESS": ("bl_initial_thickness", float),
    "BL_GROWTH_RATE": ("bl_growth_rate", float),
    "BL_LAYERS": ("bl_layers", lambda s: int(float(s))),
    "BL_CONVEX_METHOD": ("bl_convex_method", lambda s: int(float(s))),
    "BL_FAN_NODES": ("bl_fan_nodes", lambda s: int(float(s))),
    "BL_AUTO_FAN_NODES": ("bl_auto_fan_nodes", lambda s: int(s) != 0),
    "BL_FAN_ANGLE_THRESHOLD": ("bl_fan_angle_threshold", float),
    "BL_CONVEX_ANGLE_THRESHOLD": ("bl_convex_angle_threshold", float),
    "BL_PARA_FALLBACK_ANGLE": ("bl_para_fallback_angle", float),
    "BL_CONCAVE_METHOD": ("bl_concave_method", lambda s: int(float(s))),
    "BL_CONCAVE_ANGLE_THRESHOLD": ("bl_concave_angle_threshold", float),
    "BL_CONCAVE_INFLUENCE_MULTIPLIER": ("bl_concave_influence_multiplier", float),
    "BL_MERGE_CONCAVE": ("bl_merge_concave", lambda s: int(s) != 0),
    "BL_SMOOTHING_ITERS": ("bl_smoothing_iters", lambda s: int(float(s))),
    "BL_TRANSITION_LAYERS": ("bl_transition_layers", lambda s: int(float(s))),
    "BL_AUTO_TRANSITION_LAYERS": ("bl_auto_transition_layers", lambda s: int(float(s))),
    "BL_TRANSITION_GROWTH_RATE": ("bl_transition_growth_rate", float),
    "BL_TRANSITION_BUFFER": ("bl_transition_buffer", float),
    "GMSH_ALGORITHM": ("gmsh_algorithm", lambda s: int(float(s))),
    "GMSH_OPTIMIZE": ("gmsh_optimize", lambda s: int(float(s))),
    "BL_USE_ANALYTIC_GEOM": ("bl_use_analytic_geom", lambda s: int(s) != 0),
    "BC_XMIN": ("bc_xmin", str),
    "BC_XMAX": ("bc_xmax", str),
    "BC_YMIN": ("bc_ymin", str),
    "BC_YMAX": ("bc_ymax", str),
    "BC_GEOM": ("bc_geom", str),
    "EXPORT_VTK": ("export_vtk", lambda s: int(s) != 0),
    "EXPORT_STARCD": ("export_starcd", lambda s: int(s) != 0),
    "EXPORT_CGNS": ("export_cgns", lambda s: int(s) != 0),
    "ENABLE_COLLISION_DETECTION": ("enable_collision_detection", lambda s: int(s) != 0),
    "OUTPUT_FILENAME": ("output_filename", str),
}

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
    bl_concave_influence_multiplier: float = 10.0
    bl_merge_concave: bool = False
    bl_smoothing_iters: int = 0

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

    def prune_roles(self):
        """Drop geom_roles entries whose path is no longer in geom_files, so a
        stale seed role can't silently re-attach when a path is added again."""
        present = set(self.geom_files) | {os.path.abspath(g) for g in self.geom_files}
        self.geom_roles = {k: v for k, v in self.geom_roles.items() if k in present}

    def load_from_file(self, path: str):
        """Parse configuration parameters from a text file."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")

        path = os.path.abspath(path)
        # Clear existing geometry files list
        self.geom_files = []
        # Per-geometry roles (seed geometries), rebuilt from SEED_FILE lines
        self.geom_roles = {}
        # Per-group BC-type assignments, rebuilt from GROUP_BC lines (#4)
        self.group_bc = {}
        # Track GEOM_FILE/SEED_FILE tokens that could not be resolved to a file
        self.missing_geom_files = []

        cfg_dir = os.path.dirname(path)

        def resolve(val_str: str) -> str:
            """Resolve a geometry token to an absolute path, trying several roots.
            Records unresolved tokens in missing_geom_files."""
            if os.path.exists(val_str):
                return os.path.abspath(val_str)
            candidates = [os.path.abspath(os.path.join(cfg_dir, val_str)),
                          os.path.abspath(os.path.join(os.path.dirname(cfg_dir), val_str))]
            from app.utils import repo_root
            project_root = repo_root()
            candidates.append(os.path.abspath(os.path.join(project_root, val_str)))
            candidates.append(os.path.abspath(os.path.join(project_root, "examples", val_str)))
            for c in candidates:
                if os.path.exists(c):
                    return c
            # Not found anywhere: keep a config-dir-relative absolute path.
            self.missing_geom_files.append(val_str)
            return os.path.abspath(os.path.join(cfg_dir, val_str))

        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("/"):
                    continue

                tokens = line.split()
                if not tokens or len(tokens) < 2:
                    continue

                key = tokens[0].upper()
                val_str = tokens[1]

                # Map text file key to class attribute. GEOM_FILE / DOMAIN_FILE take
                # an optional [bl|nobl] role token (must match the C++ parser in
                # include/Config.hpp).
                if key == "GEOM_FILE":
                    # GEOM_FILE <path> [bl|nobl] [KEY=VALUE ...]; trailing
                    # KEY=VALUE tokens are per-geometry BL overrides (see the C++
                    # parser in include/Config.hpp — keep the two in sync).
                    gp = resolve(val_str)
                    self.geom_files.append(gp)
                    role_name, bl_params, bc = None, {}, None
                    for tok in tokens[2:]:
                        if tok == "nobl":
                            role_name = "nobl"
                        elif tok == "bl":
                            role_name = "bl"
                        elif tok.startswith("bc="):
                            bc = tok[3:]
                        else:
                            kv = self._parse_bl_token(tok)
                            if kv:
                                bl_params[kv[0]] = kv[1]
                    entry = {}
                    if bl_params:
                        entry = {"role": "bl", "bl_params": bl_params}
                    elif role_name == "nobl":
                        entry = {"role": "nobl"}
                    elif bc:
                        # A per-geometry wall BC on a plain boundary still needs a
                        # role dict to carry it ("bl" = boundary that grows a BL).
                        entry = {"role": "bl"}
                    if entry:
                        if bc:
                            entry["bc"] = bc
                        self.geom_roles[gp] = entry
                elif key == "DOMAIN_FILE":
                    # Outer-domain outline: bl -> wall (internal), nobl -> far-field
                    # (external, default). Trailing KEY=VALUE tokens are per-domain
                    # BL overrides (only meaningful for a BL-growing wall).
                    dom_path = resolve(val_str)
                    self.geom_files.append(dom_path)
                    role, bl_params, bc = "farfield", {}, None
                    for tok in tokens[2:]:
                        if tok == "bl":
                            role = "wall"
                        elif tok == "nobl":
                            role = "farfield"
                        elif tok.startswith("bc="):
                            bc = tok[3:]
                        else:
                            kv = self._parse_bl_token(tok)
                            if kv:
                                bl_params[kv[0]] = kv[1]
                    entry = {"role": role}
                    if bl_params and role == "wall":
                        entry["bl_params"] = bl_params
                    if bc:
                        entry["bc"] = bc
                    self.geom_roles[dom_path] = entry
                elif key == "GROUP_BC":
                    # GROUP_BC <name> <bc_type>; the grouping label maps to a BC
                    # type chosen in the Mesh Generator (#4). Names/types are
                    # single tokens (no spaces), matching how they are written.
                    if len(tokens) >= 3:
                        self.group_bc[tokens[1]] = tokens[2]
                elif key == "SEED_FILE":
                    # SEED_FILE <path> [size] [radius] [mode]; order-tolerant:
                    # words source/embed = mode, numbers fill size then radius.
                    # Must stay equivalent to the C++ parser in include/Config.hpp
                    # (loadFromFile, SEED_FILE branch).
                    seed_path = resolve(val_str)
                    size = radius = None
                    mode = "source"
                    numi = 0
                    for tok in tokens[2:]:
                        if tok in ("source", "embed"):
                            mode = tok
                        elif tok == "auto":
                            numi += 1  # skip this numeric slot (stays auto)
                        else:
                            try:
                                v = float(tok)
                                if numi == 0:
                                    size = v
                                elif numi == 1:
                                    radius = v
                                numi += 1
                            except ValueError:
                                pass
                    self.geom_files.append(seed_path)
                    self.geom_roles[seed_path] = {
                        "role": "seed", "size": size, "radius": radius, "mode": mode,
                    }
                elif key in _KEY_MAP:
                    attr, converter = _KEY_MAP[key]
                    try:
                        setattr(self, attr, converter(val_str))
                    except ValueError:
                        pass

    def save_to_file(self, path: str):
        """Export parameters to a Background_para.dat format text file."""
        lines = [
            "# HybMesh2D Background Parameter File (Background_para.dat)",
            "# Automatically generated by Mesh Config Editor",
            "",
            "# ==============================================================================",
            "# 1. Domain Settings",
            "# ==============================================================================",
            f"DOMAIN_X_MIN {self.domain_x_min:.6g}",
            f"DOMAIN_X_MAX {self.domain_x_max:.6g}",
            f"DOMAIN_Y_MIN {self.domain_y_min:.6g}",
            f"DOMAIN_Y_MAX {self.domain_y_max:.6g}",
            "",
            "# ==============================================================================",
            "# 2. General Mesh Settings",
            "# ==============================================================================",
            f"SURFACE_MESH_SIZE {self.surface_mesh_size:.6g}",
            f"AUTO_SURFACE_SIZE {1 if self.auto_surface_size else 0}",
            f"FARFIELD_MESH_SIZE {self.farfield_mesh_size:.6g}",
            f"AUTO_FARFIELD_SIZE {1 if self.auto_farfield_size else 0}",
            f"FARFIELD_GROWTH_RATE {self.farfield_growth_rate:.6g}",
            f"FARFIELD_BIDIRECTIONAL {1 if self.farfield_bidirectional else 0}",
            f"FARFIELD_GROWTH_RATE_OUTER {self.farfield_growth_rate_outer:.6g}",
            "",
            "# ==============================================================================",
            "# 3. Boundary Layer Core Settings",
            "# ==============================================================================",
            f"BL_INITIAL_THICKNESS {self.bl_initial_thickness:.6g}",
            f"BL_GROWTH_RATE {self.bl_growth_rate:.6g}",
            f"BL_LAYERS {self.bl_layers}",
            "",
            "# ==============================================================================",
            "# 4. Fan & Convex Corner Handling",
            "# ==============================================================================",
            f"BL_CONVEX_METHOD {self.bl_convex_method}",
            f"BL_FAN_NODES {self.bl_fan_nodes}",
            f"BL_AUTO_FAN_NODES {1 if self.bl_auto_fan_nodes else 0}",
            f"BL_FAN_ANGLE_THRESHOLD {self.bl_fan_angle_threshold:.6g}",
            f"BL_CONVEX_ANGLE_THRESHOLD {self.bl_convex_angle_threshold:.6g}",
            f"BL_PARA_FALLBACK_ANGLE {self.bl_para_fallback_angle:.6g}",
            "",
            "# ==============================================================================",
            "# 5. Concave Corner Handling",
            "# ==============================================================================",
            f"BL_CONCAVE_METHOD {self.bl_concave_method}",
            f"BL_CONCAVE_ANGLE_THRESHOLD {self.bl_concave_angle_threshold:.6g}",
            f"BL_CONCAVE_INFLUENCE_MULTIPLIER {self.bl_concave_influence_multiplier:.6g}",
            f"BL_MERGE_CONCAVE {1 if self.bl_merge_concave else 0}",
            f"BL_SMOOTHING_ITERS {self.bl_smoothing_iters}",
            "",
            "# ==============================================================================",
            "# 6. Transition to Farfield & Algorithm",
            "# ==============================================================================",
            f"BL_TRANSITION_LAYERS {self.bl_transition_layers}",
            f"BL_AUTO_TRANSITION_LAYERS {self.bl_auto_transition_layers}",
            f"BL_TRANSITION_GROWTH_RATE {self.bl_transition_growth_rate:.6g}",
            f"BL_TRANSITION_BUFFER {self.bl_transition_buffer:.6g}",
            f"GMSH_ALGORITHM {self.gmsh_algorithm}",
            f"GMSH_OPTIMIZE {self.gmsh_optimize}",
            f"BL_USE_ANALYTIC_GEOM {1 if self.bl_use_analytic_geom else 0}",
            "",
            "# ==============================================================================",
            "# 7. Boundary Conditions & I/O",
            "# ==============================================================================",
            f"EXPORT_VTK {1 if self.export_vtk else 0}",
            f"EXPORT_STARCD {1 if self.export_starcd else 0}",
            f"EXPORT_CGNS {1 if self.export_cgns else 0}",
            f"ENABLE_COLLISION_DETECTION {1 if self.enable_collision_detection else 0}",
            f"BC_XMIN {self.bc_xmin}",
            f"BC_XMAX {self.bc_xmax}",
            f"BC_YMIN {self.bc_ymin}",
            f"BC_YMAX {self.bc_ymax}",
            f"BC_GEOM {self.bc_geom}",
        ]

        # #4: per-group BC-type assignments (grouping label -> BC type). Ignored by
        # the mesher (BC still travels via the patch name); kept so the assignment
        # round-trips through a saved .dat and re-seeds the solver table.
        for name, bc in (self.group_bc or {}).items():
            if str(name).strip() and str(bc).strip():
                lines.append(f"GROUP_BC {name} {bc}")

        if self.output_filename:
            lines.append(f"OUTPUT_FILENAME {self.output_filename}")

        from app.utils import repo_root
        project_root = repo_root()
        cfg_dir = os.path.dirname(os.path.abspath(path))
        domain_emitted = False   # at most one DOMAIN_FILE (the backend keeps one)
        for gf in self.geom_files:
            abs_gf = os.path.abspath(gf)

            # Real containment test (avoids matching siblings like HybMesh_old)
            if abs_gf == project_root or abs_gf.startswith(project_root + os.sep):
                rel_path = os.path.relpath(abs_gf, project_root)
            else:
                try:
                    rel_path = os.path.relpath(abs_gf, cfg_dir)
                except ValueError:
                    rel_path = gf

            role = self.role_of(gf)
            role_name = role.get("role") if role else None
            # Per-geometry BL overrides -> trailing "KEY=VALUE" tokens (only for
            # BL-growing roles). Mirrors the C++ parser in include/Config.hpp.
            bl_tokens = ""
            if role and role.get("bl_params"):
                parts = [f"{k}={float(v):g}" for k, v in role["bl_params"].items()]
                if parts:
                    bl_tokens = " " + " ".join(parts)
            # Per-geometry wall BC override -> trailing `bc=<name>` token.
            bc_val = role.get("bc") if role else None
            bc_token = f" bc={bc_val}" if bc_val else ""
            # Outer-domain outline -> DOMAIN_FILE (wall -> bl / internal, far-field ->
            # nobl / external). Only the first domain-role geom is emitted as the
            # domain; any extra falls through to GEOM_FILE.
            if role_name in ("wall", "farfield") and not domain_emitted:
                token = "bl" if role_name == "wall" else "nobl"
                # BL overrides only apply to a BL-growing wall.
                extra = bl_tokens if role_name == "wall" else ""
                lines.append(f"DOMAIN_FILE {rel_path} {token}{extra}{bc_token}")
                domain_emitted = True
            elif role_name == "nobl":
                lines.append(f"GEOM_FILE {rel_path} nobl{bc_token}")
            elif role_name == "bl":
                # Boundary obstacle that grows a BL (may carry BL and/or BC overrides).
                lines.append(f"GEOM_FILE {rel_path} bl{bl_tokens}{bc_token}")
            elif role and role_name == "seed":
                # SEED_FILE <path> [size|auto] [radius] <mode>; mode always
                # explicit so source/embed round-trips. size/radius are
                # independent: an explicit radius with an auto size uses the
                # 'auto' size-slot placeholder so radius still lands correctly.
                parts = [f"SEED_FILE {rel_path}"]
                size = role.get("size")
                radius = role.get("radius")
                has_size = bool(size and size > 0)
                has_radius = bool(radius and radius > 0)
                if has_size:
                    parts.append(f"{size:.6g}")
                    if has_radius:
                        parts.append(f"{radius:.6g}")
                elif has_radius:
                    parts.append("auto")            # auto size, explicit radius
                    parts.append(f"{radius:.6g}")
                parts.append(role.get("mode") or "source")
                lines.append(" ".join(parts))
            else:
                lines.append(f"GEOM_FILE {rel_path}")

        # Ensure parent directories exist
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
