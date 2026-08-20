from __future__ import annotations
import os

from app.models.mesh_config_keys import _KEY_MAP


def load_config_from_file(cfg, path: str):
    """Parse configuration parameters from a text file into `cfg`."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config file not found: {path}")

    path = os.path.abspath(path)
    # Clear existing geometry files list
    cfg.geom_files = []
    # Per-geometry roles (seed geometries), rebuilt from SEED_FILE lines
    cfg.geom_roles = {}
    # Per-group BC-type assignments, rebuilt from GROUP_BC lines (#4)
    cfg.group_bc = {}
    # Track GEOM_FILE/SEED_FILE tokens that could not be resolved to a file
    cfg.missing_geom_files = []
    # Track KEY VALUE lines whose value could not be converted (so the user is
    # told their setting was ignored instead of it silently reverting to default)
    cfg.parse_warnings = []

    cfg_dir = os.path.dirname(path)

    def resolve(val_str: str) -> str:
        """Resolve a geometry token to an absolute path, trying several roots.
        Records unresolved tokens in missing_geom_files."""
        if os.path.exists(val_str):
            return os.path.abspath(val_str)
        candidates = [os.path.abspath(os.path.join(cfg_dir, val_str)),
                      os.path.abspath(os.path.join(os.path.dirname(cfg_dir), val_str))]
        from app.services.paths import repo_root
        project_root = repo_root()
        candidates.append(os.path.abspath(os.path.join(project_root, val_str)))
        candidates.append(os.path.abspath(os.path.join(project_root, "examples", val_str)))
        for c in candidates:
            if os.path.exists(c):
                return c
        # Not found anywhere: keep a config-dir-relative absolute path.
        cfg.missing_geom_files.append(val_str)
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
                cfg.geom_files.append(gp)
                role_name, bl_params, bc = None, {}, None
                for tok in tokens[2:]:
                    if tok == "nobl":
                        role_name = "nobl"
                    elif tok == "bl":
                        role_name = "bl"
                    elif tok.startswith("bc="):
                        bc = tok[3:]
                    else:
                        kv = cfg._parse_bl_token(tok)
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
                    cfg.geom_roles[gp] = entry
            elif key == "DOMAIN_FILE":
                # Outer-domain outline: bl -> wall (internal), nobl -> far-field
                # (external, default). Trailing KEY=VALUE tokens are per-domain
                # BL overrides (only meaningful for a BL-growing wall).
                dom_path = resolve(val_str)
                cfg.geom_files.append(dom_path)
                role, bl_params, bc = "farfield", {}, None
                for tok in tokens[2:]:
                    if tok == "bl":
                        role = "wall"
                    elif tok == "nobl":
                        role = "farfield"
                    elif tok.startswith("bc="):
                        bc = tok[3:]
                    else:
                        kv = cfg._parse_bl_token(tok)
                        if kv:
                            bl_params[kv[0]] = kv[1]
                entry = {"role": role}
                if bl_params and role == "wall":
                    entry["bl_params"] = bl_params
                if bc:
                    entry["bc"] = bc
                cfg.geom_roles[dom_path] = entry
            elif key == "GROUP_BC":
                # GROUP_BC <name> <bc_type>; the grouping label maps to a BC
                # type chosen in the Mesh Generator (#4). Names/types are
                # single tokens (no spaces), matching how they are written.
                if len(tokens) >= 3:
                    cfg.group_bc[tokens[1]] = tokens[2]
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
                cfg.geom_files.append(seed_path)
                cfg.geom_roles[seed_path] = {
                    "role": "seed", "size": size, "radius": radius, "mode": mode,
                }
            elif key in _KEY_MAP:
                attr, converter = _KEY_MAP[key]
                try:
                    setattr(cfg, attr, converter(val_str))
                except ValueError:
                    cfg.parse_warnings.append(
                        f"{key}: could not parse value '{val_str}'; kept the default.")


def save_config_to_file(cfg, path: str):
    """Export `cfg` parameters to a Background_para.dat format text file."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(config_to_text(cfg, path))


def config_to_text(cfg, path: str = "") -> str:
    """`cfg` as Background_para.dat text, as it would be written at `path`.

    Split from :func:`save_config_to_file` so a caller that needs the config as
    CONTENT rather than as a file on disk — the solver case staging its own
    runnable mesh parameters into grid/cad/ — does not have to write a temp file
    and read it back. One builder, so the staged config is byte-identical to the
    one Save Mesh Config writes.
    """
    lines = [
        "# HybMesh2D Background Parameter File (Background_para.dat)",
        "# Automatically generated by Mesh Config Editor",
        "",
        "# ==============================================================================",
        "# 0. Units",
        "#    The unit every length below is written in. The mesher does not convert",
        "#    them (it only compares lengths with each other) but it does record the",
        "#    unit, so a mesh handed to the solver carries what its coordinates mean:",
        "#    Linf is metres-per-grid-unit and Re = fs_UnitRe x Linf.",
        "# ==============================================================================",
        f"LENGTH_UNIT {getattr(cfg, 'length_unit', 'm') or 'm'}",
    ]
    # Only written for a custom unit: for m/mm/in the factor is a definition, and a
    # stale number in the file could contradict the code it sits next to.
    if getattr(cfg, "length_unit", "m") == "custom":
        lines.append(f"LENGTH_UNIT_METRES {float(getattr(cfg, 'length_unit_metres', 1.0)):.10g}")
        cu_name = str(getattr(cfg, "length_unit_name", "") or "").strip()
        if cu_name and " " not in cu_name:
            lines.append(f"LENGTH_UNIT_NAME {cu_name}")
    lines += [
        "",
        "# ==============================================================================",
        "# 1. Domain Settings",
        "# ==============================================================================",
        f"DOMAIN_X_MIN {cfg.domain_x_min:.6g}",
        f"DOMAIN_X_MAX {cfg.domain_x_max:.6g}",
        f"DOMAIN_Y_MIN {cfg.domain_y_min:.6g}",
        f"DOMAIN_Y_MAX {cfg.domain_y_max:.6g}",
        "",
        "# ==============================================================================",
        "# 2. General Mesh Settings",
        "# ==============================================================================",
        f"SURFACE_MESH_SIZE {cfg.surface_mesh_size:.6g}",
        f"AUTO_SURFACE_SIZE {1 if cfg.auto_surface_size else 0}",
        f"FARFIELD_MESH_SIZE {cfg.farfield_mesh_size:.6g}",
        f"AUTO_FARFIELD_SIZE {1 if cfg.auto_farfield_size else 0}",
        f"FARFIELD_GROWTH_RATE {cfg.farfield_growth_rate:.6g}",
        f"FARFIELD_BIDIRECTIONAL {1 if cfg.farfield_bidirectional else 0}",
        f"FARFIELD_GROWTH_RATE_OUTER {cfg.farfield_growth_rate_outer:.6g}",
        "",
        "# ==============================================================================",
        "# 3. Boundary Layer Core Settings",
        "# ==============================================================================",
        f"BL_INITIAL_THICKNESS {cfg.bl_initial_thickness:.6g}",
        f"BL_GROWTH_RATE {cfg.bl_growth_rate:.6g}",
        f"BL_LAYERS {cfg.bl_layers}",
        "",
        "# ==============================================================================",
        "# 4. Fan & Convex Corner Handling",
        "# ==============================================================================",
        f"BL_CONVEX_METHOD {cfg.bl_convex_method}",
        f"BL_FAN_NODES {cfg.bl_fan_nodes}",
        # int() rather than the bare field, unlike its ~20 integer siblings: this
        # was a bool field until 2026-08-19 and a workspace written before then
        # can still put True here if it reaches the model without going through
        # load_from_dict, which would write "True" into the .dat.
        f"BL_AUTO_FAN_NODES {int(cfg.bl_auto_fan_nodes)}",
        f"BL_FAN_ANGLE_THRESHOLD {cfg.bl_fan_angle_threshold:.6g}",
        f"BL_CONVEX_ANGLE_THRESHOLD {cfg.bl_convex_angle_threshold:.6g}",
        f"BL_PARA_FALLBACK_ANGLE {cfg.bl_para_fallback_angle:.6g}",
        "",
        "# ==============================================================================",
        "# 5. Concave Corner Handling",
        "# ==============================================================================",
        f"BL_CONCAVE_METHOD {cfg.bl_concave_method}",
        f"BL_CONCAVE_ANGLE_THRESHOLD {cfg.bl_concave_angle_threshold:.6g}",
        f"BL_CONCAVE_INFLUENCE_MULTIPLIER {cfg.bl_concave_influence_multiplier:.6g}",
        f"BL_JUNCTION_METHOD {cfg.bl_junction_method}",
        f"BL_JUNCTION_ANGLE_C1 {cfg.bl_junction_angle_c1:.6g}",
        f"BL_JUNCTION_ANGLE_C2 {cfg.bl_junction_angle_c2:.6g}",
        f"BL_JUNCTION_ANGLE_C3 {cfg.bl_junction_angle_c3:.6g}",
        f"BL_MERGE_CONCAVE {1 if cfg.bl_merge_concave else 0}",
        f"BL_SMOOTHING_ITERS {cfg.bl_smoothing_iters}",
        "",
        "# ==============================================================================",
        "# 6. Transition to Farfield & Algorithm",
        "# ==============================================================================",
        f"BL_TRANSITION_LAYERS {cfg.bl_transition_layers}",
        f"BL_AUTO_TRANSITION_LAYERS {cfg.bl_auto_transition_layers}",
        f"BL_TRANSITION_GROWTH_RATE {cfg.bl_transition_growth_rate:.6g}",
        f"BL_TRANSITION_BUFFER {cfg.bl_transition_buffer:.6g}",
        f"GMSH_ALGORITHM {cfg.gmsh_algorithm}",
        f"GMSH_OPTIMIZE {cfg.gmsh_optimize}",
        f"BL_USE_ANALYTIC_GEOM {1 if cfg.bl_use_analytic_geom else 0}",
        "",
        "# ==============================================================================",
        "# 7. Boundary Conditions & I/O",
        "# ==============================================================================",
        f"EXPORT_VTK {1 if cfg.export_vtk else 0}",
        f"EXPORT_STARCD {1 if cfg.export_starcd else 0}",
        f"EXPORT_CGNS {1 if cfg.export_cgns else 0}",
        f"ENABLE_COLLISION_DETECTION {1 if cfg.enable_collision_detection else 0}",
        f"BC_XMIN {cfg.bc_xmin}",
        f"BC_XMAX {cfg.bc_xmax}",
        f"BC_YMIN {cfg.bc_ymin}",
        f"BC_YMAX {cfg.bc_ymax}",
        f"BC_GEOM {cfg.bc_geom}",
    ]

    # #4: per-group BC-type assignments (grouping label -> BC type). Ignored by
    # the mesher (BC still travels via the patch name); kept so the assignment
    # round-trips through a saved .dat and re-seeds the solver table.
    for name, bc in (cfg.group_bc or {}).items():
        if str(name).strip() and str(bc).strip():
            lines.append(f"GROUP_BC {name} {bc}")

    if cfg.output_filename:
        lines.append(f"OUTPUT_FILENAME {cfg.output_filename}")

    from app.services.paths import repo_root
    project_root = repo_root()
    cfg_dir = os.path.dirname(os.path.abspath(path)) if path else project_root
    domain_emitted = False   # at most one DOMAIN_FILE (the backend keeps one)
    # By IDENTITY: two spellings of one file used to emit two GEOM_FILE lines,
    # i.e. hand the mesher a doubled boundary. And the resolution base is the
    # repo, never the process cwd -- os.path.abspath made the same entry name a
    # different file depending on where the GUI was launched from.
    from app.services.geom_path_identity import (canonical_geom_path,
                                                 dedupe_geom_paths)
    for gf in dedupe_geom_paths(cfg.geom_files):
        abs_gf = canonical_geom_path(gf)

        # Real containment test (avoids matching siblings like HybMesh_old)
        if abs_gf == project_root or abs_gf.startswith(project_root + os.sep):
            rel_path = os.path.relpath(abs_gf, project_root)
        else:
            try:
                rel_path = os.path.relpath(abs_gf, cfg_dir)
            except ValueError:
                rel_path = gf

        role = cfg.role_of(gf)
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

    return "\n".join(lines) + "\n"
