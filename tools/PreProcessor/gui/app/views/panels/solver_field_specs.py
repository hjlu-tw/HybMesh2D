"""The solver panel's field TABLE — all 74 ``SolverConfig`` fields its widgets author.

This is the panel the candidate was measured on: 88 widget attributes across two build
mixins, read back by 75 hand-written ``cfg.<field> = self.<widget>.<getter>()`` lines
and written by 77 more. Nothing declared the set, so the three halves agreed only
because all three spelled the same name.

``group`` names the ``_build_*`` section that lays a row out. A few groups exist only
because the section adds a bare widget instead of a form row (``*_enable``: the feature
toggles that gate a sub-form) — that is a layout fact, so it lives here rather than
being smoothed over in the builder.

Only two fields are not plain: ``beta`` / ``dissip_ctrl`` and the three shock parameters
are ``gfloat`` (a float in a QLineEdit) because a spin box cannot display ``1.0e-12``,
and their read keeps the model's current value when the text does not parse — the same
``_parse_float(text, cfg.x)`` fallback the hand-written half had.
"""
from __future__ import annotations

from app.services.field_spec import FieldSpec

_BIG_INT = dict(lo=1, hi=100_000_000)
_SYM = dict(lo=-1e6, hi=1e6, dec=4)

SOLVER_SPECS: tuple[FieldSpec, ...] = (
    # ── Case & Preset (built in the panel's __init__) ─────────────────────────
    FieldSpec("domain_type", "choice", "Domain Type",
              "Solver domain dimensionality (e2d = 2D, e3d = 3D)",
              group="case", opts=dict(choices=[("e2d", "e2d"), ("e3d", "e3d")])),
    FieldSpec("case_name", "text", "Case Name",
              "Case name; solver_ctrl builds case/<name>/{work,grid,dll}",
              group="case", opts=dict(fallback="case")),

    # ── Pipeline Binaries ────────────────────────────────────────────────────
    FieldSpec("getpgrid_binary", "path", "getPGrid",
              "Path to the getPGrid binary",
              group="pipeline", opts=dict(caption="Select getPGrid binary")),
    FieldSpec("bdecompose_binary", "path", "bDecompose",
              "Path to the bDecompose binary (optional)",
              group="pipeline", opts=dict(caption="Select bDecompose binary")),
    FieldSpec("solver_binary", "path", "Solver",
              "Path to the unicones solver binary",
              group="pipeline", opts=dict(caption="Select solver binary")),

    # ── Grid Conversion (getPGrid) ───────────────────────────────────────────
    FieldSpec("input_vrt_file", "path", ".vrt", "STAR-CD vertex file (.vrt)",
              group="grid", opts=dict(caption="Select .vrt",
                                      filter="Vertex (*.vrt);;All Files (*)")),
    FieldSpec("input_cel_file", "path", ".cel", "STAR-CD cell file (.cel)",
              group="grid", opts=dict(caption="Select .cel",
                                      filter="Cell (*.cel);;All Files (*)")),
    FieldSpec("input_bnd_file", "path", ".bnd", "STAR-CD boundary file (.bnd)",
              group="grid", opts=dict(caption="Select .bnd",
                                      filter="Boundary (*.bnd);;All Files (*)")),
    FieldSpec("is_3d", "bool", "3D grid", "Treat the input as a 3D grid",
              group="grid", opts=dict(text="3D grid")),
    FieldSpec("mixed_mesh", "bool", "Mixed mesh (keep quads+tris)",
              "Preserve the hybrid quad+tri mesh instead of slicing to triangles. "
              "Forces use_incenter off (undefined for quad cells).",
              group="grid", opts=dict(text="Mixed mesh (keep quads+tris)")),
    FieldSpec("output_grid_file", "text", "Out grid", "Output grid filename (.grid)",
              group="grid", opts=dict(fallback="mesh.grid")),
    FieldSpec("output_bc_file", "text", "Out bc", "Output bc filename (.bc)",
              group="grid", opts=dict(fallback="mesh.bc")),

    # ── Flow Conditions ──────────────────────────────────────────────────────
    # Axisymmetric is a property of the solved domain (nozzles, cones), not of the
    # getPGrid file conversion — it belongs with the flow/domain settings.
    FieldSpec("axisymmetric_2d", "bool", "Axisymmetric 2D",
              "Treat the 2D domain as axisymmetric (nozzles, cones)",
              group="flow", opts=dict(text="Axisymmetric 2D")),
    FieldSpec("flow_solu_type", "choice", "Solver type",
              "Solution type: ns_sol = viscous Navier-Stokes, euler_sol = inviscid.\n"
              "Also drives the default geometry wall BC (no-slip vs slip).",
              group="flow",
              opts=dict(choices=[("ns_sol", "ns_sol"), ("euler_sol", "euler_sol")])),
    FieldSpec("transp_prop_option", "choice", "Transport",
              "Transport-property model under the perfect-gas assumption.",
              group="flow",
              opts=dict(choices=[("CONST_PRANDTL", "CONST_PRANDTL"),
                                 ("CONST_PROP", "CONST_PROP"),
                                 ("VAR_PRANDTL", "VAR_PRANDTL")])),
    FieldSpec("fs_mach", "float", "Mach", "Free-stream Mach number",
              group="flow", opts=dict(lo=0.0, hi=100.0, dec=4)),
    FieldSpec("fs_flow_angle", "float", "AoA (deg)",
              "Free-stream flow angle / angle of attack (degrees)",
              group="flow", opts=dict(lo=-180.0, hi=180.0, dec=3)),
    FieldSpec("fs_tinf", "float", "T_inf (K)", "Free-stream temperature (K)",
              group="flow", opts=dict(lo=0.0, hi=1e5, dec=2)),
    FieldSpec("fs_unit_re", "float", "Unit Re",
              "Free-stream unit Reynolds number per meter",
              group="flow", opts=dict(lo=0.0, hi=1e9, dec=2)),
    # Linf is a PHYSICAL LENGTH in metres, so it follows the sci rule: a fixed-notation
    # box with a 1e-6 floor cannot express a custom unit like 2.54e-7 m and would
    # silently clamp it.
    FieldSpec("linf", "sci", "L_inf (m)",
              "Metres per grid unit — NOT a free normalisation length.\n"
              "The manual: \"Length scale used to normalize grid coordinates (in "
              "meter), input 1 if dimensional in meters\"; an inch grid uses 0.0254.\n\n"
              "Since fs_UnitRe is per metre, Re = fs_UnitRe x Linf. Derived from the "
              "Mesh panel's model unit while 'from model unit' is ticked.",
              group="flow", opts=dict(lo=0.0, hi=1e6, suffix=" m")),
    FieldSpec("linf_from_unit", "bool", "from model unit",
              "Keep Linf equal to the Mesh panel's model unit (metres per unit).\n"
              "Untick only to hold a hand-set Linf — which is how a config written "
              "before units existed is loaded, so its Reynolds number is preserved.",
              group="flow", opts=dict(text="from model unit")),
    # The derived quantity, shown because it is the one an engineer recognises. A unit
    # error hides inside Linf; it is obvious in Re. Authors nothing.
    FieldSpec("ref_reynolds", "label", "→ Re",
              "Reference Reynolds number the solver will run at: fs_UnitRe x Linf.\n"
              "This is the number to sanity-check — a wrong model unit is invisible in "
              "Linf but unmistakable here.",
              model=None, group="flow",
              opts=dict(text="—", style="color:#8a93ad; font-size:11px;")),
    FieldSpec("gamma", "float", "gamma",
              "Ratio of specific heats Cp/Cv (1.4 for air)",
              group="flow", opts=dict(lo=1.0, hi=2.0, dec=4)),
    FieldSpec("rgas", "float", "Rgas", "Perfect-gas constant R (≈287 for air, SI)",
              group="flow", opts=dict(lo=0.0, hi=1e4, dec=3)),
    FieldSpec("stokes", "float", "Stokes",
              "Stokes coefficient for the second viscosity",
              group="flow", opts=dict(lo=-10.0, hi=10.0, dec=4)),
    FieldSpec("prandtl", "float", "Prandtl", "Prandtl number",
              group="flow", opts=dict(lo=0.0, hi=10.0, dec=4)),

    # ── Turbulence ───────────────────────────────────────────────────────────
    FieldSpec("turb_model_option", "choice", "Model",
              "Turbulence model. laminar = none. RANS models need near-wall y+~1 "
              "mesh;\nLES (smagorinsky/dsm) is only meaningful for time-accurate runs.",
              group="turbulence",
              opts=dict(choices=[(n, n) for n in (
                  "laminar", "sa_model", "komega_wilcox", "komega_sst",
                  "k-epsilon", "smagorinsky", "dsm_model")])),
    FieldSpec("construct_wall_dist_db", "bool", "Construct wall-distance DB",
              "Generate Wall_dist_db.dat (RANS pre-processing step; run once with "
              "num_half_iter = 0, then switch to 'Read in').",
              group="turbulence", opts=dict(text="Construct wall-distance DB")),
    FieldSpec("read_in_wall_dist_db", "bool", "Read in wall-distance DB",
              "Read the previously generated Wall_dist_db.dat instead of rebuilding it.",
              group="turbulence", opts=dict(text="Read in wall-distance DB")),

    # ── Numerics ─────────────────────────────────────────────────────────────
    FieldSpec("cfl", "float", "CFL", "CFL number",
              group="numerics", opts=dict(lo=0.0, hi=1e4, dec=4)),
    FieldSpec("constant_cfl", "bool", "Constant CFL",
              "Hold CFL constant across iterations",
              group="numerics", opts=dict(text="Constant CFL")),
    FieldSpec("dt_const", "text", "dt_const",
              "Constant time step (used when 'Constant CFL' is off). Leave blank to "
              "use CFL.", group="numerics"),
    FieldSpec("cfl_schedule_fn", "text", "CFL schedule",
              "Optional iteration→(cfl,dt,dissip) schedule table filename",
              group="numerics"),
    FieldSpec("alpha", "float", "alpha", "Numerical parameter alpha",
              group="numerics", opts=dict(_SYM)),
    # gfloat: scientific-notation values a spin box cannot show.
    FieldSpec("beta", "gfloat", "beta", "Numerical parameter beta (e.g. -200000)",
              group="numerics"),
    FieldSpec("dissip_ctrl", "gfloat", "dissip_ctrl",
              "Dissipation control (e.g. 1.0e-12)", group="numerics"),
    FieldSpec("epsilon", "float", "epsilon",
              "Numerical parameter epsilon (sigma bound)",
              group="numerics", opts=dict(_SYM)),
    FieldSpec("convg_norm_type", "choice", "Norm",
              "Error-norm type used for the convergence residual.",
              group="numerics",
              opts=dict(choices=[("L2NORM", "L2NORM"), ("L1NORM", "L1NORM")])),
    FieldSpec("use_incenter", "bool", "Use incenter",
              "Use triangle incenter for reconstruction",
              group="numerics", opts=dict(text="Use incenter")),
    FieldSpec("dissip_per_cfl", "bool", "Dissipation per CFL",
              "Scale the artificial dissipation by the local CFL number so the "
              "dissipation stays consistent when the CFL / time-step varies "
              "(local time stepping, ramped CFL). It is a stabilisation toggle "
              "only — the dissipation magnitude is still set by alpha / beta / "
              "dissip_ctrl, so no extra input is required.",
              group="numerics", opts=dict(text="Dissipation per CFL")),
    FieldSpec("unsteady_lstep", "bool", "Unsteady local stepping",
              "Enable unsteady local time stepping",
              group="numerics", opts=dict(text="Unsteady local stepping")),

    # ── Shock capturing (a toggle gating its own sub-form) ────────────────────
    FieldSpec("enable_shock", "bool", "Enable shock capturing",
              "Pressure-gradient based shock capturing for supersonic flows.\n"
              "Tip: run once and plot the 'vort' variable (2nd pressure derivative) "
              "to pick shock_gradp_value.",
              model="enable_shock_capturing", group="shock_enable",
              opts=dict(text="Enable shock capturing")),
    FieldSpec("shock_gradp_value", "gfloat", "gradp value",
              "Shock detection cut-off (e.g. -2000)", group="shock"),
    FieldSpec("shockf_gradp_beta", "gfloat", "gradp beta", "Shock beta (e.g. -2000)",
              group="shock"),
    FieldSpec("shockf_gradp_eps", "float", "gradp eps", "Shock epsilon (e.g. 3)",
              group="shock", opts=dict(_SYM)),
    FieldSpec("shockf_gradp_dissip_ctrl", "gfloat", "gradp dissip",
              "Shock dissipation control (e.g. 1.0e-14)", group="shock"),

    # ── Iteration Control ────────────────────────────────────────────────────
    FieldSpec("num_half_iter", "int", "Half iters",
              "Total number of half-iterations to run",
              group="iteration", opts=dict(_BIG_INT)),
    # R9: keep print intervals small enough that the live residual monitor actually
    # receives data (the stock 100000 leaves it blank for a long time).
    FieldSpec("print_convg_per_niter", "int", "Print convg /n",
              "Iterations between convergence prints. Keep small (e.g. 100) so the "
              "live residual monitor updates (R9).",
              group="iteration", opts=dict(_BIG_INT)),
    FieldSpec("print_sol_per_niter", "int", "Print sol /n",
              "Iterations between Tecplot solution dumps. Controls when Results has "
              "a file.", group="iteration", opts=dict(_BIG_INT)),
    FieldSpec("dump_zone_per_niter", "int", "Dump zone /n",
              "Iterations between zone-dump (restart) writes.",
              group="iteration", opts=dict(_BIG_INT)),
    FieldSpec("write_wall_force", "bool", "Write wall force",
              "Compute viscous wall force and write WallForce.dat (lift/drag history).",
              group="iteration", opts=dict(text="Write wall force")),

    # ── Output & Probes ──────────────────────────────────────────────────────
    FieldSpec("tecplot_write_vtx_output", "bool", "Write nodal Tecplot output",
              "Write solutions on cell vertices instead of cell centers. "
              "Cell-centered is more reliable for the CESE scheme (esp. MPI).",
              group="output_flags", opts=dict(text="Write nodal Tecplot output")),
    FieldSpec("calc_time_mean_values", "bool", "Compute time-mean values",
              "Accumulate and write time averages (MeanValue_tec.dat).",
              group="output_flags", opts=dict(text="Compute time-mean values")),
    FieldSpec("probe_points_def_fn", "path", "Probe file",
              "Probe-point coordinate file (one 'x y' per line for 2D); "
              "blank = no probes",
              group="output", opts=dict(caption="Select probe-point file")),
    FieldSpec("probe_output_skip_niter", "int", "Probe /n",
              "Iterations between probe outputs",
              group="output", opts=dict(_BIG_INT)),

    # ── Restart / Initial Condition ──────────────────────────────────────────
    FieldSpec("restart", "bool", "Restart from previous run",
              "Continue from a previous run's zone-dump and convergence files.",
              group="restart_enable", opts=dict(text="Restart from previous run")),
    FieldSpec("convg_fn_restart", "path", "Convg file",
              "Previous-run convergence file — the solver writes it into the case "
              "work dir as unicones.enorm.gui (GUI) / .cli (headless)",
              group="restart", opts=dict(caption="Select convergence file")),
    FieldSpec("zdump_fn_restart", "path", "Zone dump",
              "Previous-run zone-dump file — the solver writes it into the case "
              "work dir as binDumpZ.dat.gui (GUI) / .cli (headless)",
              group="restart", opts=dict(caption="Select zone-dump file")),
    FieldSpec("init_cond_depQ", "text", "init Q",
              "Explicit initial dep-var array, e.g. '1 1 0 0 0.524' (rho u v [w] et). "
              "Leave blank for freestream init. Ignored on restart, or when an init "
              "DLL is set.",
              group="ic",
              opts=dict(placeholder="rho u v [w] et   e.g. 1 1 0 0 0.524")),
    # Works with OR without IBM (#4): a getQ-style source the solver dlopens to set
    # the initial field. Its row carries a 'Build…' button, so the section wraps it.
    FieldSpec("init_cond_dll", "text", "init DLL",
              "Path to an initial-condition DLL source (.cc; compiled per-case). "
              "Set it to drive the initial field from code instead of the explicit "
              "'init Q' array. Works with or without IBM.",
              group="ic"),

    # ── Parallel (pthread) ───────────────────────────────────────────────────
    FieldSpec("apply_pthread", "bool", "Apply pthread", "Enable pthread parallelism",
              group="parallel", opts=dict(text="Apply pthread")),
    FieldSpec("max_nthread", "int", "Max threads", "Maximum number of threads",
              group="parallel", opts=dict(lo=1, hi=1024)),
    FieldSpec("num_zones_per_block", "int", "Zones/block",
              "Number of zones per block", group="parallel", opts=dict(lo=1, hi=100000)),

    # ── Domain Decomposition (bDecompose) ────────────────────────────────────
    FieldSpec("enable_decompose", "bool", "Enable domain decomposition (MPI)",
              "Run bDecompose to partition the grid and launch the solver under "
              "mpirun. Off by default (D4): the bundled unicones is a pthread build, "
              "not MPI. Requires mpirun on PATH and an MPI-capable solver binary.",
              group="decompose_enable",
              opts=dict(text="Enable domain decomposition (MPI)")),
    FieldSpec("num_partitions", "int", "Partitions",
              "Number of MPI partitions (mpirun -np)",
              group="decompose", opts=dict(lo=1, hi=4096)),
    FieldSpec("readin_iface_info", "bool", "Read in interface info",
              "Off for the first MPI run (the code generates interface info and "
              "writes it to file); on for later runs reusing it.",
              group="decompose", opts=dict(text="Read in interface info")),
    FieldSpec("mpi_comm_map_fn", "path", "Comm map",
              "Communication-map file produced by bDecompose (optional)",
              group="decompose", opts=dict(caption="Select comm-map file")),

    # ── Immersed Boundary (IBM) ──────────────────────────────────────────────
    FieldSpec("immersed_solid", "bool", "Immersed solid",
              "Enable the immersed-boundary solid phase (D7)",
              group="ibm_enable", opts=dict(text="Immersed solid")),
    FieldSpec("solid_phase_phi_min", "float", "phi_min", "Minimum solid-phase phi",
              group="ibm", opts=dict(lo=0.0, hi=1.0, dec=6)),
    FieldSpec("solid_phase_alpha", "float", "solid alpha", "Solid-phase alpha",
              group="ibm", opts=dict(lo=0.0, hi=100.0, dec=6)),
    FieldSpec("solid_phase_epsilon", "float", "solid eps", "Solid-phase epsilon",
              group="ibm", opts=dict(lo=0.0, hi=100.0, dec=6)),
    FieldSpec("stationary_solid", "bool", "Stationary solid", "Solid does not move",
              group="ibm", opts=dict(text="Stationary solid")),
    FieldSpec("rigid_moving_body", "bool", "Rigid moving body",
              "Solid is a rigid moving body",
              group="ibm", opts=dict(text="Rigid moving body")),
    # The initial-condition DLL lives in the Restart section now (#4 — it works
    # without IBM too); only the motion DLL is IBM-specific and stays here.
    FieldSpec("motion_dll", "text", "motion DLL",
              "Path to motion DLL source (.cc; compiled per-case)", group="ibm"),
    FieldSpec("ibm_phi_file", "path", "phi field",
              "phi field data (STL3d output), staged into the work dir as phi.dat",
              group="ibm", opts=dict(caption="Select phi field data",
                                     filter="phi data (*.dat);;All Files (*)")),
)

#: SolverConfig fields the panel authors OUTSIDE the table. One entry, and it is a
#: TABLE of rows rather than a field: each row is a mesh segment with its patch name
#: and BC type, and the extra value is dropped for types that do not take one.
SOLVER_EXTRA_AUTHORED = frozenset({"bc_definitions"})
