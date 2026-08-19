from __future__ import annotations
import os
from dataclasses import dataclass, field

from app.models import mesh_output_names


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
class MeshConfig:
    # Section 0: Units
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
        for attr, _ in _key_map().values():
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
        for attr, converter in _key_map().values():
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

    def prune_roles(self):
        """Drop geom_roles entries whose path is no longer in geom_files, so a
        stale seed role can't silently re-attach when a path is added again."""
        present = set(self.geom_files) | {os.path.abspath(g) for g in self.geom_files}
        self.geom_roles = {k: v for k, v in self.geom_roles.items() if k in present}

    def validate(self, geom_bbox: tuple | None = None,
                 domain_bbox: tuple | None = None) -> tuple[list[str], list[str]]:
        """Pre-flight parameter sanity check, returning (errors, warnings).

        Errors are conditions that would make the backend crash or produce
        garbage (invalid domain, non-positive sizes, shrinking BL); the caller
        must block the run on any error. Warnings are advisory (no BL grown,
        BL stack likely to overrun the domain, geometry outside the domain box)
        and let the run proceed. Catching these here — rather than after a
        cryptic C++ crash — is what an industrial pre-processor does.

        ``geom_bbox`` is an optional (xmin, ymin, xmax, ymax) of the boundary
        geometry; when supplied, containment against the domain is checked.
        ``domain_bbox`` is the same for the custom outer-domain outline, and is
        what containment is checked against when one is defined.

        **Every domain check here is about the domain the run will actually
        use.** With a custom outline (`domain_file`) the rectangular box is
        hidden in the panel and overwritten from the geometry by the mesher, so
        validating it would block a perfectly valid run on numbers nobody set
        or can see. Config.hpp::validate() gates its own domain-span check on
        `domainFile.empty()` for exactly this reason — the two must agree.
        """
        errors: list[str] = []
        warnings: list[str] = []
        custom_domain = self.domain_file is not None

        # ── Domain ────────────────────────────────────────────────────────
        errors += self.domain_box_errors()
        if custom_domain and domain_bbox is None:
            warnings.append(
                "Custom domain outline could not be read; its extent-based "
                "checks (BL overrun, geometry containment) were skipped.")

        # What the advisory checks measure against: the outline's bounds, else the box.
        if custom_domain:
            dom = domain_bbox
        elif self.domain_x_min < self.domain_x_max and self.domain_y_min < self.domain_y_max:
            dom = (self.domain_x_min, self.domain_y_min,
                   self.domain_x_max, self.domain_y_max)
        else:
            dom = None

        # ── Mesh sizes ────────────────────────────────────────────────────
        if not self.auto_surface_size and self.surface_mesh_size <= 0:
            errors.append("Surface mesh size must be > 0 (or enable Auto).")
        if not self.auto_farfield_size and self.farfield_mesh_size <= 0:
            errors.append("Far-field mesh size must be > 0 (or enable Auto).")

        # ── Boundary layer (only meaningful when layers are grown) ────────
        # Checked PER FRONT: "the BL parameters" is not one set of numbers. Validating
        # the global ones whenever ANY front grows rejects a run over a parameter no
        # front reads; validating them only when the global count is positive lets a
        # geometry inherit a zero thickness unchecked. See bl_fronts().
        fronts = self.bl_fronts()
        if self.bl_layers < 0:
            errors.append("BL layer count cannot be negative.")
        elif not fronts:
            warnings.append("BL layers = 0: no boundary layer will be grown.")
        else:
            for labels, t0, growth in fronts:
                where = f" (used by {', '.join(labels)})" if labels else ""
                if t0 <= 0:
                    errors.append(f"BL initial thickness must be > 0{where}.")
                if growth < 1.0:
                    errors.append(
                        "BL growth rate must be >= 1.0 (a rate < 1 shrinks each "
                        f"layer){where}.")
            # Total BL stack thickness vs domain size (advisory).
            if (self.bl_layers > 0 and self.bl_initial_thickness > 0
                    and self.bl_growth_rate >= 1.0 and dom):
                g, n, t0 = self.bl_growth_rate, self.bl_layers, self.bl_initial_thickness
                total = (t0 * n if abs(g - 1.0) < 1e-9
                         else t0 * (g ** n - 1.0) / (g - 1.0))
                half = 0.5 * min(dom[2] - dom[0], dom[3] - dom[1])
                if half > 0 and total > half:
                    warnings.append(
                        f"Estimated BL stack thickness (~{total:.4g}) exceeds half "
                        f"the smaller domain extent (~{half:.4g}); the boundary "
                        "layer may overrun the domain.")

        # ── Transition ────────────────────────────────────────────────────
        if self.bl_transition_layers < 0:
            errors.append("Transition layer count cannot be negative.")
        if self.bl_transition_layers > 0 and self.bl_transition_growth_rate < 1.0:
            warnings.append(
                "Transition growth rate < 1.0 shrinks each transition layer.")

        # ── Geometry containment (advisory; needs both bboxes) ────────────
        if geom_bbox is not None and dom:
            gx0, gy0, gx1, gy1 = geom_bbox
            if (gx0 < dom[0] or gx1 > dom[2] or gy0 < dom[1] or gy1 > dom[3]):
                where = ("the custom domain outline's bounds "
                         f"([{dom[0]:.4g}, {dom[2]:.4g}] x [{dom[1]:.4g}, {dom[3]:.4g}])"
                         if custom_domain else "the domain box")
                warnings.append(
                    f"Geometry bounds ([{gx0:.4g}, {gx1:.4g}] x [{gy0:.4g}, "
                    f"{gy1:.4g}]) extend outside {where}; the mesh may be "
                    "clipped or the run may fail.")

        return errors, warnings

    def domain_box_errors(self) -> list[str]:
        """Errors in the rectangular domain box — empty when a custom outline is in use.

        The one definition, shared by :meth:`validate` and the Mesh-Generator preview.
        With a custom outline the box is hidden in the panel and overwritten from the
        geometry by the mesher, so checking it would block a valid run on numbers nobody
        set or can see; ``Config.hpp::validate()`` gates its own span check on
        ``domainFile.empty()`` for the same reason, and the three must agree.
        """
        if self.domain_file is not None:
            return []
        out = []
        if self.domain_x_min >= self.domain_x_max:
            out.append("Domain X Min must be strictly less than X Max.")
        if self.domain_y_min >= self.domain_y_max:
            out.append("Domain Y Min must be strictly less than Y Max.")
        return out

    @staticmethod
    def _as_float(value, fallback: float) -> float:
        """``value`` as a float, else ``fallback``. Override dicts come from a workspace
        or a hand-written config, so a value can be a string or junk; an unreadable
        override falls back to the global rather than failing the whole pre-flight."""
        if value is None:
            return fallback
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    def bl_fronts(self) -> list[tuple]:
        """``(labels, initial_thickness, growth_rate)`` per DISTINCT set of values grown.

        Empty when nothing grows a boundary layer at all. ``labels`` is the geometry
        names using those values, and is EMPTY when the global front uses them — so a
        message built from it points at the global BL fields exactly when those are the
        fields to fix, and names the geometries otherwise.

        A geometry's override is merged ON TOP of the global BLParams by the mesher
        (``Config.hpp::applyBLOverride``), so a geometry overriding only the layer count
        is still grown with the GLOBAL thickness and growth rate: hence resolving the
        effective values per front, and grouping by the values rather than the front.
        """
        global_key = ((self.bl_initial_thickness, self.bl_growth_rate)
                      if self.bl_layers > 0 else None)
        by_values: dict = {}          # (t0, growth) -> [geometry label, ...]
        if global_key is not None:
            by_values[global_key] = []
        for g in self.geom_files:
            p = self.bl_params_of(g)
            if not p:
                continue
            if self._as_float(p.get("BL_LAYERS"), float(self.bl_layers)) <= 0:
                continue
            key = (self._as_float(p.get("BL_INITIAL_THICKNESS"), self.bl_initial_thickness),
                   self._as_float(p.get("BL_GROWTH_RATE"), self.bl_growth_rate))
            labels = by_values.setdefault(key, [])
            # Sharing the global front's numbers => unlabelled: the global fields own them.
            if key != global_key:
                labels.append(os.path.basename(g))
        return [(tuple(labels), t0, growth)
                for (t0, growth), labels in by_values.items()]

    def load_from_file(self, path: str):
        """Parse configuration parameters from a text file."""
        from app.models.mesh_config_io import load_config_from_file
        return load_config_from_file(self, path)

    def save_to_file(self, path: str):
        """Export parameters to a Background_para.dat format text file."""
        from app.models.mesh_config_io import save_config_to_file
        return save_config_to_file(self, path)
