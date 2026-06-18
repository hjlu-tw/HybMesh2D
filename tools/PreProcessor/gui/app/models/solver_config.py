from __future__ import annotations
import os
import json
from dataclasses import dataclass, field, asdict


def _repo_root() -> str:
    """Absolute path to the repository root (5 levels up from this file)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../.."))


# Default locations of the prebuilt solver-pipeline binaries (decision D5:
# use the existing binaries under solver/, no compilation step).
_DEFAULT_GETPGRID = "solver/preprocess/getPGrid/work/getPGrid"
_DEFAULT_BDECOMPOSE = "solver/preprocess/bDecompose/work/bDecompose"
_DEFAULT_SOLVER = "solver/execute/unicones.eqn6.mac"


@dataclass
class SolverConfig:
    """Full configuration for the unicones solver pipeline.

    Drives three stages: getPGrid (STAR-CD -> .grid/.bc), the optional
    bDecompose (MPI domain decomposition, bypassed by default per D4), and
    the unicones solver itself. Also knows how to emit every input file the
    binaries expect: para.in (getPGrid/bDecompose stdin), input.in (solver)
    and the boundary-condition .def table.
    """

    # ── Pipeline binary paths (default to the prebuilt binaries under solver/) ──
    getpgrid_binary: str = ""
    bdecompose_binary: str = ""
    solver_binary: str = ""

    # ── getPGrid input (STAR-CD .vrt/.cel/.bnd -> .grid/.bc) ──
    input_vrt_file: str = ""
    input_cel_file: str = ""
    input_bnd_file: str = ""
    is_3d: bool = False
    reorient_mesh: bool = False
    slice_to_simplex: bool = False
    output_grid_file: str = "mesh.grid"
    output_bc_file: str = "mesh.bc"

    # ── bDecompose (optional bypass, D4) ──
    enable_decompose: bool = False
    num_partitions: int = 4

    # ── Solver main parameters (input.in) ──
    domain_type: str = "e2d"            # e2d / e3d
    solve_gcl: bool = False
    grid_type: str = "unstructured"
    grid_data_format: str = "c_binary"
    bc_file_use_table: bool = True

    # Free-stream conditions
    transp_prop_option: str = "CONST_PRANDTL"
    fs_mach: float = 0.2
    fs_tinf: float = 273.0
    fs_unit_re: float = 200.0
    linf: float = 1.0
    prandtl: float = 0.72

    # Numerics
    alpha: float = 1.0
    beta: float = -200000.0
    dissip_ctrl: float = 1.0e-12
    epsilon: float = 2.0
    cfl: float = 0.6
    constant_cfl: bool = True
    unsteady_lstep: bool = False
    use_incenter: bool = True
    dissip_per_cfl: bool = False

    # Iteration control.
    # NOTE (R9): print_convg_per_niter governs how often convergence is echoed
    # to stdout. The smoke test showed the stock value (100000) prints residuals
    # only every 100k iterations, leaving the live monitor blank. Default low so
    # the residual plot updates; users can raise it for long production runs.
    num_half_iter: int = 1000
    print_convg_per_niter: int = 10
    print_sol_per_niter: int = 1000

    # Parallel (pthread; bDecompose/MPI is a separate optional path)
    apply_pthread: bool = True
    max_nthread: int = 32
    num_zones_per_block: int = 28

    # IBM (Immersed Boundary) — only emitted when immersed_solid is True (D7).
    immersed_solid: bool = False
    solid_phase_phi_min: float = 0.001
    solid_phase_alpha: float = 0.001
    solid_phase_epsilon: float = 1.03
    stationary_solid: bool = True
    rigid_moving_body: bool = False
    init_cond_dll: str = ""             # path to .cc source (compiled per-case)
    motion_dll: str = ""                # path to .cc source (compiled per-case)

    # Boundary-condition definitions for the solver .def table:
    # [{"segment_no": 33, "bc_type": 5}, ...]
    bc_definitions: list = field(default_factory=list)

    # Case working directory + name (solver_ctrl builds case/<name>/{work,grid,dll})
    work_dir: str = ""
    case_name: str = "case"

    # ------------------------------------------------------------------ #
    # Defaults / discovery
    # ------------------------------------------------------------------ #
    def ensure_default_binaries(self):
        """Fill in any blank binary path with the prebuilt binary under solver/."""
        root = _repo_root()
        if not self.getpgrid_binary:
            self.getpgrid_binary = os.path.join(root, _DEFAULT_GETPGRID)
        if not self.bdecompose_binary:
            self.bdecompose_binary = os.path.join(root, _DEFAULT_BDECOMPOSE)
        if not self.solver_binary:
            self.solver_binary = os.path.join(root, _DEFAULT_SOLVER)

    # ------------------------------------------------------------------ #
    # Input-file generation
    # ------------------------------------------------------------------ #
    def generate_getpgrid_para(self, path: str):
        """Write the stdin answer file (para.in) for getPGrid.

        The order matches getPGrid's interactive prompts (verified by smoke
        test): use-starcd? / vrt / cel / bnd / 3d? / reorient? / stifcons? /
        mixed_mesh? / slice? / out grid / out bc.
        """
        yn = lambda b: "y" if b else "n"
        lines = [
            "y",                                   # Using starcd vrt and cel files?
            os.path.basename(self.input_vrt_file),
            os.path.basename(self.input_cel_file),
            os.path.basename(self.input_bnd_file),
            yn(self.is_3d),                        # Is this a 3D grid?
            yn(self.reorient_mesh),                # Re-orient the mesh?
            "y",                                   # Write grid+bc in stifcons format?
            "n",                                   # mixed_mesh format?
            yn(self.slice_to_simplex),             # slice quad/hex into tri/tet?
            os.path.basename(self.output_grid_file),
            os.path.basename(self.output_bc_file),
        ]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def generate_bdecompose_para(self, path: str):
        """Write the stdin answer file (para.in) for bDecompose (optional, D4)."""
        lines = [
            os.path.basename(self.output_grid_file),
            os.path.basename(self.output_bc_file),
            "n", "n", "n", "n", "n", "n",
            str(self.num_partitions),
            "mpi",
        ]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def generate_bc_def(self, path: str):
        """Write the solver boundary-condition .def table.

        Format matches the case SQ.def: a header comment line followed by
        `segment_no  bc_string` rows.
        """
        lines = [
            "  segment_no    bc_string(0: reflect_bc, 5: fixed_bc,  1: non_reflect_bc)",
        ]
        for bc in self.bc_definitions:
            seg = bc.get("segment_no")
            bc_type = bc.get("bc_type")
            lines.append(f"   {seg:>10}   {bc_type:>10}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def generate_input_in(self, path: str, grid_rel: str | None = None,
                          bc_rel: str | None = None):
        """Write the solver input.in.

        grid_rel/bc_rel let solver_ctrl inject paths relative to the case work
        dir (e.g. "../grid/<case>.grid"); otherwise output_grid_file/output_bc_file
        are used verbatim.
        """
        bl = lambda b: "true" if b else "false"
        grid_path = grid_rel if grid_rel is not None else self.output_grid_file
        bc_path = bc_rel if bc_rel is not None else self.output_bc_file

        L = []
        a = L.append
        a("")
        a(f"   DomainType      \t{self.domain_type}")
        a(f"   solve_gcl       \t{bl(self.solve_gcl)}")
        a("")
        a(f'   grid_fname  \t\t"{grid_path}"')
        a(f'   bc_fname    \t\t"{bc_path}"')
        a("")
        a(f"   grid_type          \t{self.grid_type}")
        a(f"   grid_data_format    \t{self.grid_data_format}")
        a(f"   bc_file_use_table   \t{bl(self.bc_file_use_table)}")
        a("")
        a(f"   Transp_prop_option   {self.transp_prop_option}")
        a(f"   fs_Mach            \t{self.fs_mach:g}")
        a(f"   fs_Tinf            \t{self.fs_tinf:g}")
        a(f"   fs_UnitRe            {self.fs_unit_re:g}")
        a(f"   Linf        \t\t{self.linf:g}")
        a(f"   Prandtl         \t{self.prandtl:g}")
        a("")
        a(f"   alpha           \t{self.alpha:g}")
        a(f"   beta            \t{self.beta:g}")
        a(f"   dissip_ctrl          {self.dissip_ctrl:g}")
        a(f"   epsilon         \t{self.epsilon:g}")
        a("")
        a(f"   cfl             \t{self.cfl:g}")
        a(f"   constant_cfl      \t{bl(self.constant_cfl)}")
        a(f"   unsteady_lstep \t{bl(self.unsteady_lstep)}")
        a(f"   use_incenter    \t{bl(self.use_incenter)}")
        a(f"   dissip_per_cfl     \t{bl(self.dissip_per_cfl)}")
        a("")
        a(f"   apply_pthread      \t{bl(self.apply_pthread)}")
        a(f"   max_nthread          {self.max_nthread}")
        a(f"   num_zones_per_block  {self.num_zones_per_block}")
        a("")
        a(f"   num_half_iter   \t\t{self.num_half_iter}")
        a(f"   print_convg_per_niter  \t{self.print_convg_per_niter}")
        a(f"   print_sol_per_niter   \t{self.print_sol_per_niter}")
        a("")

        if self.immersed_solid:
            if self.init_cond_dll:
                a(f'   init_cond_use_zdump_fn               "{self.init_cond_dll}"')
                a("   init_cond_use_zdump_fn_usedll        true")
            a("   immersed_solid                       true")
            a(f"   SolidPhasePhiMin                     {self.solid_phase_phi_min:g}")
            a(f"   SolidPhaseAlpha                      {self.solid_phase_alpha:g}")
            a(f"   SolidPhaseEpsilon                    {self.solid_phase_epsilon:g}")
            a(f"   Stationary_Solid                     {bl(self.stationary_solid)}")
            if self.motion_dll:
                a(f'   SolidPhaseMotionDLL                  "{self.motion_dll}"')
            a(f"   rigid_moving_body                    {bl(self.rigid_moving_body)}")
            a("")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(L) + "\n")

    # ------------------------------------------------------------------ #
    # Persistence (JSON)
    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        return asdict(self)

    def load_from_dict(self, d: dict):
        for k, v in d.items():
            if hasattr(self, k):
                setattr(self, k, v)

    def save_to_file(self, path: str):
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    def load_from_file(self, path: str):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Solver config not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            self.load_from_dict(json.load(f))
