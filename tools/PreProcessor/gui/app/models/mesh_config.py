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
    "FARFIELD_GROWTH_RATE": ("farfield_growth_rate", float),
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
    "BC_XMIN": ("bc_xmin", str),
    "BC_XMAX": ("bc_xmax", str),
    "BC_YMIN": ("bc_ymin", str),
    "BC_YMAX": ("bc_ymax", str),
    "BC_GEOM": ("bc_geom", str),
    "EXPORT_VTK": ("export_vtk", lambda s: int(s) != 0),
    "EXPORT_STARCD": ("export_starcd", lambda s: int(s) != 0),
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
    farfield_growth_rate: float = 0.1

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
    bl_auto_transition_layers: int = 0  # 0: OFF, 1: GLOBAL, 2: LOCAL
    bl_transition_growth_rate: float = 1.2
    bl_transition_buffer: float = 2.0
    gmsh_algorithm: int = 6  # 6: Frontal-Delaunay
    gmsh_optimize: int = 1   # 1: Enable, 0: Disable

    # Section 7: Boundary Conditions & I/O
    bc_xmin: str = "wall"
    bc_xmax: str = "wall"
    bc_ymin: str = "wall"
    bc_ymax: str = "wall"
    bc_geom: str = "wall"
    export_vtk: bool = True
    export_starcd: bool = False
    enable_collision_detection: bool = True
    output_filename: str = ""

    # Geometry files list (corresponds to multiple GEOM_FILE parameters)
    geom_files: list[str] = field(default_factory=list)

    def load_from_file(self, path: str):
        """Parse configuration parameters from a text file."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")

        # Clear existing geometry files list
        self.geom_files = []

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("/"):
                    continue

                tokens = line.split()
                if not tokens or len(tokens) < 2:
                    continue

                key = tokens[0].upper()
                val_str = tokens[1]

                # Map text file key to class attribute
                if key == "GEOM_FILE":
                    self.geom_files.append(val_str)
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
            f"FARFIELD_GROWTH_RATE {self.farfield_growth_rate:.6g}",
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
            "",
            "# ==============================================================================",
            "# 7. Boundary Conditions & I/O",
            "# ==============================================================================",
            f"EXPORT_VTK {1 if self.export_vtk else 0}",
            f"EXPORT_STARCD {1 if self.export_starcd else 0}",
            f"ENABLE_COLLISION_DETECTION {1 if self.enable_collision_detection else 0}",
            f"BC_XMIN {self.bc_xmin}",
            f"BC_XMAX {self.bc_xmax}",
            f"BC_YMIN {self.bc_ymin}",
            f"BC_YMAX {self.bc_ymax}",
            f"BC_GEOM {self.bc_geom}",
        ]

        if self.output_filename:
            lines.append(f"OUTPUT_FILENAME {self.output_filename}")

        for gf in self.geom_files:
            lines.append(f"GEOM_FILE {gf}")

        # Ensure parent directories exist
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
