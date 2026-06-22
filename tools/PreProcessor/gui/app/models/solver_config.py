from __future__ import annotations
import os
import json
from dataclasses import dataclass, field, asdict


def _repo_root() -> str:
    """Absolute path to the repository root. Delegates to the shared helper;
    imported lazily so this model module stays free of GUI dependencies."""
    from app.utils import repo_root
    return repo_root()


# Default locations of the prebuilt solver-pipeline binaries (decision D5:
# use the existing binaries under solver/, no compilation step).
_DEFAULT_GETPGRID = "solver/preprocess/getPGrid/work/getPGrid"
_DEFAULT_BDECOMPOSE = "solver/preprocess/bDecompose/work/bDecompose"
_DEFAULT_SOLVER = "solver/execute/unicones.eqn6.mac"


# ── Boundary-condition types (manual Appendix E, enum BCType) ──────────────
# (flag, label, needs_extra). The enum integer values start at 0; the FIXED_BC
# variant 50 means "user supplies explicit dependent variables at this boundary".
# `needs_extra` flags the types whose .bc.def row carries trailing values:
#   3  no-slip isothermal wall -> non-dimensional wall temperature
#   50 fixed (explicit dep-vars) -> rho u v et (2D) / rho u v w et (3D)
#   11 user DLL               -> path to the .so
BC_TYPES: list[tuple[int, str, bool]] = [
    (0,  "reflect (slip / inviscid wall)", False),
    (1,  "non-reflect (far-field)", False),
    (2,  "no-slip wall (adiabatic)", False),
    (3,  "no-slip wall (isothermal)", True),
    (4,  "unsteady", False),
    (5,  "fixed (freestream)", False),
    (50, "fixed (explicit dep-vars)", True),
    (6,  "supersonic 2D (S2D)", False),
    (7,  "periodic", False),
    (8,  "no-slip wall (heat flux)", False),
    (9,  "zonal interface", False),
    (10, "reservoir", False),
    (11, "user DLL", True),
    (12, "non-reflect 0", False),
    (13, "non-reflect 1", False),
    (14, "non-reflect 2", False),
    (15, "non-reflect 3", False),
]

BC_FLAG_TO_LABEL = {flag: label for flag, label, _ in BC_TYPES}
BC_FLAGS_NEEDING_EXTRA = {flag for flag, _, extra in BC_TYPES if extra}


# ── Workload presets (grounded in manual Appendix A + dissipation guidance) ──
# Each preset is a dict of SolverConfig field overrides applied on top of the
# current config. They cover the common starting points so users tune rather
# than build from scratch.
PRESETS: dict[str, dict] = {
    "Laminar NS (subsonic, steady)": dict(
        flow_solu_type="ns_sol", turb_model_option="laminar",
        alpha=1.0, beta=-2000.0, dissip_ctrl=1.0e-12, epsilon=5.0,
        cfl=0.6, constant_cfl=True, unsteady_lstep=False,
        use_incenter=True, dissip_per_cfl=False,
        enable_shock_capturing=False,
    ),
    "Euler (inviscid)": dict(
        flow_solu_type="euler_sol", turb_model_option="laminar",
        alpha=1.0, beta=-2000.0, dissip_ctrl=1.0e-12, epsilon=5.0,
        cfl=0.6, constant_cfl=True, unsteady_lstep=False,
        use_incenter=True, dissip_per_cfl=False,
        enable_shock_capturing=False,
    ),
    "RANS k-omega SST (steady)": dict(
        flow_solu_type="ns_sol", turb_model_option="komega_sst",
        alpha=1.0, beta=-5000.0, dissip_ctrl=1.0e-12, epsilon=10.0,
        cfl=0.3, constant_cfl=True, unsteady_lstep=False,
        use_incenter=True, dissip_per_cfl=False,
        enable_shock_capturing=False,
    ),
    "Supersonic + shock capturing": dict(
        flow_solu_type="ns_sol", turb_model_option="laminar",
        alpha=2.0, beta=-5000.0, dissip_ctrl=1.0e-12, epsilon=10.0,
        cfl=0.1, constant_cfl=False, unsteady_lstep=True,
        use_incenter=True, dissip_per_cfl=False,
        enable_shock_capturing=True, shock_gradp_value=-2000.0,
        shockf_gradp_beta=-2000.0, shockf_gradp_eps=3.0,
        shockf_gradp_dissip_ctrl=1.0e-14,
    ),
    "Time-accurate (TALTS)": dict(
        flow_solu_type="ns_sol", turb_model_option="laminar",
        alpha=0.1, beta=-1.2, dissip_ctrl=1.0e-12, epsilon=2.0,
        cfl=0.6, constant_cfl=False, unsteady_lstep=True,
        use_incenter=True, dissip_per_cfl=False,
        enable_shock_capturing=False,
    ),
}


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
    mpi_comm_map_fn: str = ""            # comm-map file from bDecompose (MPI runs)
    readin_iface_info: bool = False      # false on the first MPI run (generates iface info)

    # ── Solver main parameters (input.in) ──
    domain_type: str = "e2d"            # e2d / e3d
    solve_gcl: bool = False
    grid_type: str = "unstructured"
    grid_data_format: str = "c_binary"
    bc_file_use_table: bool = True
    mixed_mesh: bool = False             # preserve hybrid quad+tri (no slicing to simplex)
    axisymmetric_2d: bool = False

    # Solution type / transport / turbulence
    flow_solu_type: str = "ns_sol"      # ns_sol / euler_sol
    transp_prop_option: str = "CONST_PRANDTL"   # CONST_PROP / CONST_PRANDTL / VAR_PRANDTL
    turb_model_option: str = "laminar"  # laminar / sa_model / komega_wilcox /
                                        # komega_sst / k-epsilon / smagorinsky / dsm_model
    construct_wall_dist_db: bool = False
    read_in_wall_dist_db: bool = False

    # Free-stream conditions
    fs_mach: float = 0.2
    fs_tinf: float = 273.0
    fs_unit_re: float = 200.0
    fs_flow_angle: float = 0.0          # angle of attack (deg), manual fs_flow_angle
    linf: float = 1.0
    gamma: float = 1.4
    rgas: float = 287.0
    stokes: float = 0.0
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
    dt_const: str = ""                  # constant time step (used if constant_cfl=false)
    cfl_schedule_fn: str = ""           # iteration-vs-(cfl,dt,dissip) schedule table
    convg_norm_type: str = "L2NORM"     # L1NORM / L2NORM

    # Shock capturing (pressure-gradient based; off by default).
    enable_shock_capturing: bool = False
    shock_gradp_value: float = -50.0
    shockf_gradp_beta: float = -2.0
    shockf_gradp_eps: float = 5.0
    shockf_gradp_dissip_ctrl: float = 1.0e-12

    # Iteration control.
    # NOTE: the solver build reads `num_half_iter` (verified against the working
    # case input.in); manual V0.6 lists the older name `num_iter` for the same
    # parameter (total physical time = dt * num_iter / 2 for the dual-level CESE
    # scheme). Keep `num_half_iter`.
    # R9: print_convg_per_niter governs how often convergence is echoed to stdout.
    # The smoke test showed the stock value (100000) prints residuals only every
    # 100k iterations, leaving the live monitor blank. Default low so the residual
    # plot updates; users can raise it for long production runs.
    num_half_iter: int = 1000
    print_convg_per_niter: int = 10
    print_sol_per_niter: int = 1000
    dump_zone_per_niter: int = 1000
    write_wall_force: bool = False

    # ── Output / probes ──
    tecplot_write_vtx_output: bool = False   # write nodal (vertex) Tecplot, not cell-centered
    calc_time_mean_values: bool = False      # accumulate time-mean values to file
    probe_points_def_fn: str = ""            # probe-point coordinate file
    probe_output_skip_niter: int = 1         # iterations between probe outputs

    # ── Restart / initial conditions ──
    restart: bool = False
    convg_fn_restart: str = ""          # previous-run convergence file
    zdump_fn_restart: str = ""          # previous-run zone-dump file
    init_cond_depQ: str = ""            # explicit initial dep-var array, e.g. "1 1 0 0 0.524"

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
    # [{"segment_no": 33, "bc_type": 5, "values": ""}, ...]
    # `values` holds the trailing tokens for types that need them (isothermal
    # wall temperature, fixed explicit dep-vars, user-DLL path).
    bc_definitions: list = field(default_factory=list)

    # Case working directory + name (solver_ctrl builds case/<name>/{work,grid,dll})
    work_dir: str = ""
    case_name: str = "case"

    # ------------------------------------------------------------------ #
    # Presets / defaults / discovery
    # ------------------------------------------------------------------ #
    def apply_preset(self, name: str):
        """Apply a named workload preset (PRESETS) onto this config in place."""
        for k, v in PRESETS.get(name, {}).items():
            if hasattr(self, k):
                setattr(self, k, v)

    def default_wall_bc_flag(self) -> int:
        """The sensible geometry-wall BC flag for the current solution type:
        no-slip adiabatic (2) for viscous NS, slip/reflect (0) for inviscid Euler."""
        return 0 if self.flow_solu_type == "euler_sol" else 2

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
            yn(self.mixed_mesh),                   # mixed_mesh format?
            # Don't slice to simplex when keeping a mixed mesh.
            "n" if self.mixed_mesh else yn(self.slice_to_simplex),
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

        Format matches getPGrid's companion: a `segm_no   bc_flag` header line
        followed by `segment_no  bc_flag [extra values]` rows. Types 3, 50 and 11
        carry trailing values (wall temperature / explicit dep-vars / DLL path);
        see manual Appendix E and §3.2.
        """
        lines = ["segm_no   bc_flag"]
        for bc in self.bc_definitions:
            seg = bc.get("segment_no")
            bc_type = bc.get("bc_type")
            extra = str(bc.get("values", "") or "").strip()
            row = f"   {seg:>6}   {bc_type:>6}"
            if extra:
                row += f"   {extra}"
            lines.append(row)
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
        if self.axisymmetric_2d:
            a(f"   axisymmetric_2D \t{bl(self.axisymmetric_2d)}")
        a("")
        a(f'   grid_fname  \t\t"{grid_path}"')
        a(f'   bc_fname    \t\t"{bc_path}"')
        a("")
        a(f"   grid_type          \t{self.grid_type}")
        a(f"   grid_data_format    \t{self.grid_data_format}")
        a(f"   bc_file_use_table   \t{bl(self.bc_file_use_table)}")
        if self.mixed_mesh:
            a(f"   mixed_mesh          \t{bl(self.mixed_mesh)}")
        # MPI multi-block options (only meaningful with domain decomposition).
        if self.enable_decompose:
            a(f"   readin_iface_info   \t{bl(self.readin_iface_info)}")
            if self.mpi_comm_map_fn.strip():
                a(f'   mpi_comm_map_fn     \t"{self.mpi_comm_map_fn.strip()}"')
        a("")
        # ── Flow conditions ──
        a(f"   flow_solu_type      \t{self.flow_solu_type}")
        a(f"   Transp_prop_option   {self.transp_prop_option}")
        a(f"   fs_Mach            \t{self.fs_mach:g}")
        a(f"   fs_Tinf            \t{self.fs_tinf:g}")
        a(f"   fs_UnitRe            {self.fs_unit_re:g}")
        a(f"   fs_flow_angle       \t{self.fs_flow_angle:g}")
        a(f"   Linf        \t\t{self.linf:g}")
        a(f"   gamma           \t{self.gamma:g}")
        a(f"   Rgas            \t{self.rgas:g}")
        if self.stokes:
            a(f"   stokes          \t{self.stokes:g}")
        a(f"   Prandtl         \t{self.prandtl:g}")
        # Turbulence (only when not laminar).
        if self.turb_model_option and self.turb_model_option != "laminar":
            a("")
            a(f"   turb_model_option   \t{self.turb_model_option}")
            if self.construct_wall_dist_db:
                a(f"   construct_wall_dist_db  {bl(self.construct_wall_dist_db)}")
            if self.read_in_wall_dist_db:
                a(f"   read_in_wall_dist_db    {bl(self.read_in_wall_dist_db)}")
        a("")
        # ── Numerics / dissipation ──
        a(f"   alpha           \t{self.alpha:g}")
        a(f"   beta            \t{self.beta:g}")
        a(f"   dissip_ctrl          {self.dissip_ctrl:g}")
        a(f"   epsilon         \t{self.epsilon:g}")
        if self.enable_shock_capturing:
            a(f"   shock_gradp_value      {self.shock_gradp_value:g}")
            a(f"   shockf_gradp_beta      {self.shockf_gradp_beta:g}")
            a(f"   shockf_gradp_eps       {self.shockf_gradp_eps:g}")
            a(f"   shockf_gradp_dissip_ctrl  {self.shockf_gradp_dissip_ctrl:g}")
        if self.convg_norm_type and self.convg_norm_type != "L2NORM":
            a(f"   Convg_norm_type     \t{self.convg_norm_type}")
        a("")
        a(f"   cfl             \t{self.cfl:g}")
        a(f"   constant_cfl      \t{bl(self.constant_cfl)}")
        if (not self.constant_cfl) and self.dt_const.strip():
            a(f"   dt_const          \t{self.dt_const.strip()}")
        if self.cfl_schedule_fn.strip():
            a(f'   cfl_schedule_fn     \t"{self.cfl_schedule_fn.strip()}"')
        a(f"   unsteady_lstep \t{bl(self.unsteady_lstep)}")
        # Incenter reconstruction is undefined for quad/hex cells, so it is forced
        # off for mixed meshes regardless of the UI setting (manual guidance).
        a(f"   use_incenter    \t{bl(self.use_incenter and not self.mixed_mesh)}")
        a(f"   dissip_per_cfl     \t{bl(self.dissip_per_cfl)}")
        a("")
        a(f"   apply_pthread      \t{bl(self.apply_pthread)}")
        a(f"   max_nthread          {self.max_nthread}")
        a(f"   num_zones_per_block  {self.num_zones_per_block}")
        a("")
        a(f"   num_half_iter   \t\t{self.num_half_iter}")
        a(f"   print_convg_per_niter  \t{self.print_convg_per_niter}")
        a(f"   print_sol_per_niter   \t{self.print_sol_per_niter}")
        a(f"   dump_zone_per_niter   \t{self.dump_zone_per_niter}")
        if self.write_wall_force:
            a(f"   write_wall_force     \t{bl(self.write_wall_force)}")
        if self.tecplot_write_vtx_output:
            a(f"   tecplot_write_vtx_output  {bl(self.tecplot_write_vtx_output)}")
        if self.calc_time_mean_values:
            a(f"   calc_time_mean_values  \t{bl(self.calc_time_mean_values)}")
        if self.probe_points_def_fn.strip():
            a(f'   probe_points_def_fn   \t"{self.probe_points_def_fn.strip()}"')
            a(f"   probe_output_skip_niter  {self.probe_output_skip_niter}")
        a("")

        # ── Restart / initial conditions ──
        # IBM DLL initial condition takes precedence (existing behaviour); else
        # honour restart zone dump, else an explicit init_cond_depQ array.
        if self.restart:
            a(f"   restart              \t{bl(self.restart)}")
            if self.convg_fn_restart.strip():
                a(f'   convg_fn_restart     \t"{self.convg_fn_restart.strip()}"')
            if self.zdump_fn_restart.strip():
                a(f'   zdump_fn_restart     \t"{self.zdump_fn_restart.strip()}"')
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
        elif (not self.restart) and self.init_cond_depQ.strip():
            a(f"   init_cond_depQ       \t{self.init_cond_depQ.strip()}")
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
