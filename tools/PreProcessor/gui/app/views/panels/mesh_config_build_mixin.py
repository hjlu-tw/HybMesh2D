from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QFormLayout, QComboBox, QSpinBox, QLabel,
    QCheckBox,
)
from PyQt6.QtCore import Qt
from app.views.collapsible import CollapsibleSection
from app.utils import (
    make_button, COMBO_STYLE, SPIN_STYLE, align_form_labels,
    help_label, help_widget,
)
from app.models.mesh_config import MeshConfig
from app.views.bc_widget import BCWidget
from app.views.clean_double_spin_box import CleanDoubleSpinBox, SciDoubleSpinBox



class MeshConfigBuildMixin:
    """Collapsible-section builders for MeshConfigPanel, extracted from
    __init__. Each appends to self._layout; runs on the composed panel."""

    def _build_sizing_section(self):
        # ── 2. General Sizing ─────────────────────────────────────────────
        # #11: renamed back to "Mesh Sizing" (it covers surface + far-field, not
        # only the far field).
        self.sec_sizing = CollapsibleSection("Mesh Sizing", start_collapsed=True)
        self._layout.addWidget(self.sec_sizing)

        sizing_form = QFormLayout()
        # Scientific-notation field: the old 1e-4 floor made mm-scale geometry
        # unmeshable at its natural size. 0 is allowed here and rejected with a
        # message by MeshConfig.validate() unless Auto is on.
        self.surface_mesh_size = SciDoubleSpinBox()
        self.surface_mesh_size.setRange(0.0, 1e6)
        self.surface_mesh_size.setValue(MeshConfig.surface_mesh_size)
        self.surface_mesh_size.setStyleSheet(SPIN_STYLE)
        self.surface_mesh_size.setToolTip(
            "Target element size along the geometry boundary walls. "
            "Accepts scientific notation (e.g. 5e-5).")

        self.auto_surface_size = QCheckBox("Auto Surface Sizing")
        self.auto_surface_size.setStyleSheet("color:#a0a8c0;")
        self.auto_surface_size.setToolTip("Automatically determine surface mesh size from geometry spacing")

        # #6: when Auto Surface is on, show the size the mesher will derive (the
        # average resampled point spacing of the boundary geometries — the mesher
        # uses the average BL-front edge length, which equals that spacing).
        self.auto_surface_hint = QLabel("")
        self.auto_surface_hint.setWordWrap(True)
        self.auto_surface_hint.setStyleSheet("color:#6fae7a; font-size:10px;")
        self.auto_surface_hint.setVisible(False)

        self.farfield_mesh_size = SciDoubleSpinBox()
        self.farfield_mesh_size.setRange(0.0, 1e6)
        self.farfield_mesh_size.setValue(MeshConfig.farfield_mesh_size)
        self.farfield_mesh_size.setStyleSheet(SPIN_STYLE)
        self.farfield_mesh_size.setToolTip(
            "Target element size in the far-field region away from geometry. "
            "Accepts scientific notation (e.g. 2.5e-3).")

        # #11: far-field size also gets an Auto option (mirrors Auto Surface).
        # When on, the mesher derives the far-field size from the domain extent;
        # the manual value stays visible as the fallback.
        self.auto_farfield_size = QCheckBox("Auto Far-field Sizing")
        self.auto_farfield_size.setStyleSheet("color:#a0a8c0;")
        self.auto_farfield_size.setToolTip(
            "Automatically determine the far-field mesh size from the domain "
            "extent (the manual value stays as a fallback).")

        # #6: when Auto Far-field is on, show the size the mesher will derive so
        # the user can see the computed value (updated as the domain changes).
        self.auto_farfield_hint = QLabel("")
        self.auto_farfield_hint.setWordWrap(True)
        self.auto_farfield_hint.setStyleSheet("color:#6fae7a; font-size:10px;")
        self.auto_farfield_hint.setVisible(False)

        self.farfield_growth_rate = CleanDoubleSpinBox()
        self.farfield_growth_rate.setRange(0.01, 10.0)
        self.farfield_growth_rate.setDecimals(4)
        self.farfield_growth_rate.setStyleSheet(SPIN_STYLE)
        self.farfield_growth_rate.setToolTip("Rate of element size expansion from the body/BL outward to the far-field (0.0~1.0)")

        # #7: bidirectional grading — also grow the size from the OUTER domain
        # boundary inward, with its own rate. Off = single direction (body
        # outward), the original behaviour. When on, the mesh stays fine near both
        # the body and the outer boundary and is coarsest in the middle.
        self.farfield_bidirectional = QCheckBox("Bidirectional (grade from outer boundary too)")
        self.farfield_bidirectional.setStyleSheet("color:#a0a8c0;")
        self.farfield_bidirectional.setToolTip(
            "Grade the far-field size from BOTH sides: the body/BL outward AND the "
            "outer domain boundary inward, each with its own growth rate (finest "
            "near both, coarsest in the middle). Off = grow only from the body.")

        self.farfield_growth_rate_outer = CleanDoubleSpinBox()
        self.farfield_growth_rate_outer.setRange(0.01, 10.0)
        self.farfield_growth_rate_outer.setDecimals(4)
        self.farfield_growth_rate_outer.setStyleSheet(SPIN_STYLE)
        self.farfield_growth_rate_outer.setToolTip("Rate of element size expansion inward from the outer domain boundary (bidirectional only)")

        # #11: Surface Size first, then its Auto toggle right after it; likewise
        # Far-field size then its Auto toggle. Ticking Auto no longer hides the
        # manual field (it stays as a fallback the mesher uses if auto can't
        # derive a value).
        sizing_form.addRow(help_label("Surface Size:", "Target element size along the geometry boundary walls"), self.surface_mesh_size)
        sizing_form.addRow("", help_widget(self.auto_surface_size, "Automatically determine surface mesh size from geometry spacing"))
        sizing_form.addRow("", self.auto_surface_hint)
        sizing_form.addRow(help_label("Far-field Size:", "Target element size in the far-field region away from geometry"), self.farfield_mesh_size)
        sizing_form.addRow("", help_widget(self.auto_farfield_size, "Automatically determine the far-field mesh size from the domain extent"))
        sizing_form.addRow("", self.auto_farfield_hint)
        sizing_form.addRow(help_label("Growth Rate:", "Rate of element size expansion from the body/BL outward (0.0~1.0)"), self.farfield_growth_rate)
        sizing_form.addRow("", help_widget(self.farfield_bidirectional, "Also grade the far-field size inward from the outer domain boundary, with its own rate"))
        sizing_form.addRow(help_label("Outer Growth Rate:", "Rate of element size expansion inward from the outer domain boundary (bidirectional only)"), self.farfield_growth_rate_outer)
        align_form_labels(sizing_form, 130)
        self.sec_sizing.add_layout(sizing_form)
        self._sizing_form = sizing_form

        # #6: refresh the computed-size hints when the relevant Auto toggles or the
        # domain box changes (custom-domain extent refreshes via set_config /
        # domain-source changes).
        self.auto_farfield_size.toggled.connect(self._update_auto_farfield_hint)
        self.auto_surface_size.toggled.connect(self._update_auto_surface_hint)
        for _sb in (self.domain_x_min, self.domain_x_max,
                    self.domain_y_min, self.domain_y_max):
            _sb.valueChanged.connect(self._update_auto_farfield_hint)
        # #7: show/hide the outer growth rate with the bidirectional toggle.
        self.farfield_bidirectional.toggled.connect(self._update_bidirectional_visibility)
        self._update_bidirectional_visibility()


    def _build_bl_param_sections(self):
        # ── Boundary Layer (global default) ───────────────────────────────
        # The BL parameters are edited in a pop-up (same dialog as the
        # per-geometry override), not duplicated as inline panel fields.
        self.sec_bl = CollapsibleSection("Boundary Layer", start_collapsed=True)
        self._layout.addWidget(self.sec_bl)
        self.edit_global_bl_btn = make_button(
            "Edit boundary layer (global default)…", "#243a52")
        self.edit_global_bl_btn.setToolTip(
            "Edit the GLOBAL boundary-layer parameters (used by every geometry "
            "without a per-geometry override). Same fields as the per-geometry "
            "Edit BL dialog.")
        self.sec_bl.add_widget(self.edit_global_bl_btn)
        self.edit_global_bl_btn.clicked.connect(self._open_global_bl_dialog)

        # ── 3. Boundary Layer Core ────────────────────────────────────────
        # Kept alive to back the global-BL store, but hidden — the params live in
        # the Edit-BL dialog now (see #5). Same for Convex/Concave/Transition BL.
        self.sec_bl_core = CollapsibleSection("Boundary Layer Core", start_collapsed=True)
        self._layout.addWidget(self.sec_bl_core)

        bl_form = QFormLayout()
        # Scientific-notation field: a y+~1 first cell on a chord-normalised
        # geometry is routinely 1e-7..1e-8, which the old
        # setRange(1e-6, 1.0)+setDecimals(6) silently clamped to 1e-6. The lower
        # bound is 0 here and "must be > 0" is enforced by MeshConfig.validate(),
        # so an invalid entry gets a message instead of a silent substitution.
        self.bl_initial_thickness = SciDoubleSpinBox()
        self.bl_initial_thickness.setRange(0.0, 1e4)
        # Seed the MeshConfig default explicitly. The old field's 1e-6 *minimum*
        # was doing this implicitly (Qt clamped the un-set 0 up to it); now that
        # 0 is a legal entry, an un-populated panel would otherwise read 0.
        self.bl_initial_thickness.setValue(MeshConfig.bl_initial_thickness)
        self.bl_initial_thickness.setStyleSheet(SPIN_STYLE)
        self.bl_initial_thickness.setToolTip(
            "Height of the first boundary layer cell adjacent to the wall. "
            "Accepts scientific notation (e.g. 2.5e-7).")

        self.bl_growth_rate = CleanDoubleSpinBox()
        self.bl_growth_rate.setRange(1.001, 5.0)
        self.bl_growth_rate.setDecimals(4)
        self.bl_growth_rate.setStyleSheet(SPIN_STYLE)
        self.bl_growth_rate.setToolTip("Multiplicative growth factor between successive BL layers (e.g. 1.2 = 20% increase per layer)")

        self.bl_layers = QSpinBox()
        self.bl_layers.setRange(0, 100)
        self.bl_layers.setStyleSheet(SPIN_STYLE)
        self.bl_layers.setToolTip("Total number of structured boundary layer rows to generate")

        bl_form.addRow(help_label("Initial Thick:", "Height of the first boundary layer cell adjacent to the wall"), self.bl_initial_thickness)
        bl_form.addRow(help_label("Growth Rate:", "Multiplicative growth factor between successive BL layers (e.g. 1.2 = 20% increase per layer)"), self.bl_growth_rate)
        bl_form.addRow(help_label("Layers:", "Total number of structured boundary layer rows to generate"), self.bl_layers)
        align_form_labels(bl_form, 130)
        self.sec_bl_core.add_layout(bl_form)

        # ── 4. Transition & Meshing Algorithm ─────────────────────────────
        self.sec_transition = CollapsibleSection("Transition & Meshing Algorithm", start_collapsed=True)
        self._layout.addWidget(self.sec_transition)

        trans_form = QFormLayout()
        self.bl_transition_layers = QSpinBox()
        self.bl_transition_layers.setRange(0, 100)
        self.bl_transition_layers.setStyleSheet(SPIN_STYLE)
        self.bl_transition_layers.setToolTip("Number of transitional element rows blending BL quads into far-field triangles")

        self.bl_auto_transition_layers = QComboBox()
        self.bl_auto_transition_layers.addItems(["0: OFF", "1: GLOBAL", "2: LOCAL"])
        self.bl_auto_transition_layers.setCurrentIndex(2)  # #4: default LOCAL
        self.bl_auto_transition_layers.setStyleSheet(COMBO_STYLE)
        self.bl_auto_transition_layers.setToolTip("Automatically compute transition layer count (OFF / GLOBAL / LOCAL)")

        self.bl_transition_growth_rate = CleanDoubleSpinBox()
        self.bl_transition_growth_rate.setRange(1.001, 5.0)
        self.bl_transition_growth_rate.setDecimals(4)
        self.bl_transition_growth_rate.setStyleSheet(SPIN_STYLE)
        self.bl_transition_growth_rate.setToolTip("Growth rate applied within the transition zone between BL and far-field")

        self.bl_transition_buffer = CleanDoubleSpinBox()
        self.bl_transition_buffer.setRange(0.0, 100.0)
        self.bl_transition_buffer.setDecimals(4)
        self.bl_transition_buffer.setStyleSheet(SPIN_STYLE)
        self.bl_transition_buffer.setToolTip("Buffer distance multiplier around geometry for transition smoothing")

        self.gmsh_algorithm = QComboBox()
        self.gmsh_algorithm.addItems([
            "1: MeshAdapt",
            "2: Automatic",
            "5: Delaunay",
            "6: Frontal-Delaunay",
            "7: BAMG",
            "8: Frontal-Delaunay Quads"
        ])
        self.gmsh_algorithm.setStyleSheet(COMBO_STYLE)
        self.gmsh_algorithm.setToolTip("Meshing algorithm used by Gmsh for far-field triangulation")

        self.gmsh_optimize = QCheckBox("Optimize Mesh Quality")
        self.gmsh_optimize.setStyleSheet("color:#a0a8c0;")
        self.gmsh_optimize.setToolTip("Enable Gmsh mesh quality optimization pass after generation")

        self.bl_use_analytic_geom = QCheckBox("Analytic BL Normals (line/circle)")
        self.bl_use_analytic_geom.setStyleSheet("color:#a0a8c0;")
        self.bl_use_analytic_geom.setToolTip(
            "Grow the boundary layer along exact analytic normals on line/circle surface "
            "segments (instead of finite differences). No effect on smooth/polyline bodies. "
            "Uses the curve kind carried in the geometry's .meta sidecar.")

        trans_form.addRow(self._mesh_sublabel("BOUNDARY-LAYER TRANSITION"))
        trans_form.addRow(help_label("Auto Transition:", "Automatically compute transition layer count (OFF / GLOBAL / LOCAL)"), self.bl_auto_transition_layers)
        trans_form.addRow(help_label("Transition Layers:", "Number of transitional element rows blending BL quads into far-field triangles"), self.bl_transition_layers)
        trans_form.addRow(help_label("Trans Growth Rate:", "Growth rate applied within the transition zone between BL and far-field"), self.bl_transition_growth_rate)
        trans_form.addRow(help_label("Trans Buffer:", "Buffer distance multiplier around geometry for transition smoothing"), self.bl_transition_buffer)
        trans_form.addRow(self._mesh_sublabel("FAR-FIELD MESHING"))
        trans_form.addRow(help_label("Gmsh Algorithm:", "Meshing algorithm used by Gmsh for far-field triangulation"), self.gmsh_algorithm)
        trans_form.addRow("", help_widget(self.gmsh_optimize, "Enable Gmsh mesh quality optimization pass after generation"))
        trans_form.addRow("", help_widget(self.bl_use_analytic_geom,
            "Grow the boundary layer along exact analytic normals on line/circle surfaces"))
        align_form_labels(trans_form, 130)
        self.sec_transition.add_layout(trans_form)
        self._trans_form = trans_form
        self.bl_auto_transition_layers.currentIndexChanged.connect(self._update_transition_visibility)
        self._update_transition_visibility()

        # ── 5. Fan & Convex Corner Handling ────────────────────────────────
        self.sec_convex = CollapsibleSection("Convex Corner Handling", start_collapsed=True)
        self._layout.addWidget(self.sec_convex)

        self.convex_form = QFormLayout()
        self.bl_convex_method = QComboBox()
        self.bl_convex_method.addItems(["0: Fan", "2: Parallelogram"])
        self.bl_convex_method.setStyleSheet(COMBO_STYLE)
        self.bl_convex_method.setCurrentIndex(1)  # Default: Parallelogram
        self.bl_convex_method.setToolTip("Method for handling convex (outward-pointing) corners in the boundary layer")

        self.bl_fan_nodes = QSpinBox()
        self.bl_fan_nodes.setRange(1, 100)
        self.bl_fan_nodes.setStyleSheet(SPIN_STYLE)
        self.bl_fan_nodes.setToolTip("Number of fan elements inserted at convex corners (Fan method only)")

        self.bl_auto_fan_nodes = QCheckBox("Auto Fan Nodes")
        self.bl_auto_fan_nodes.setStyleSheet("color:#a0a8c0;")
        self.bl_auto_fan_nodes.setToolTip("Automatically determine fan node count based on corner angle")

        self.bl_fan_angle_threshold = CleanDoubleSpinBox()
        self.bl_fan_angle_threshold.setRange(0.0, 360.0)
        self.bl_fan_angle_threshold.setDecimals(2)
        self.bl_fan_angle_threshold.setStyleSheet(SPIN_STYLE)
        self.bl_fan_angle_threshold.setToolTip("Minimum corner angle (degrees) to trigger fan insertion")

        self.bl_convex_angle_threshold = CleanDoubleSpinBox()
        self.bl_convex_angle_threshold.setRange(0.0, 360.0)
        self.bl_convex_angle_threshold.setDecimals(2)
        self.bl_convex_angle_threshold.setStyleSheet(SPIN_STYLE)
        self.bl_convex_angle_threshold.setToolTip("Angle threshold to classify a corner as convex")

        self.bl_para_fallback_angle = CleanDoubleSpinBox()
        self.bl_para_fallback_angle.setRange(0.0, 360.0)
        self.bl_para_fallback_angle.setDecimals(2)
        self.bl_para_fallback_angle.setStyleSheet(SPIN_STYLE)
        self.bl_para_fallback_angle.setToolTip("When corner angle exceeds this, fall back to parallelogram method")

        self.convex_form.addRow(help_label("Convex Method:", "Method for handling convex (outward-pointing) corners in the boundary layer"), self.bl_convex_method)
        self.convex_form.addRow(help_label("Fan Nodes:", "Number of fan elements inserted at convex corners (Fan method only)"), self.bl_fan_nodes)
        self.convex_form.addRow("", help_widget(self.bl_auto_fan_nodes, "Automatically determine fan node count based on corner angle"))
        self.convex_form.addRow(help_label("Fan Threshold (deg):", "Minimum corner angle (degrees) to trigger fan insertion"), self.bl_fan_angle_threshold)
        self.convex_form.addRow(help_label("Convex Threshold (deg):", "Angle threshold to classify a corner as convex"), self.bl_convex_angle_threshold)
        self.convex_form.addRow(help_label("Fallback Angle (deg):", "When corner angle exceeds this, fall back to parallelogram method"), self.bl_para_fallback_angle)
        align_form_labels(self.convex_form, 130)
        self.sec_convex.add_layout(self.convex_form)

        # Wire visibility updates for Fan parameters
        self.bl_convex_method.currentIndexChanged.connect(self._update_convex_widgets_visibility)
        self._update_convex_widgets_visibility()

        # ── 6. Concave Corner Handling ────────────────────────────────────
        self.sec_concave = CollapsibleSection("Concave Corner Handling", start_collapsed=True)
        self._layout.addWidget(self.sec_concave)

        concave_form = QFormLayout()
        self.bl_concave_method = QComboBox()
        self.bl_concave_method.addItems(["5: Thickness Blending"])
        self.bl_concave_method.setStyleSheet(COMBO_STYLE)
        self.bl_concave_method.setToolTip("Method for handling concave (inward-pointing) corners in the boundary layer")

        self.bl_concave_angle_threshold = CleanDoubleSpinBox()
        self.bl_concave_angle_threshold.setRange(0.0, 360.0)
        self.bl_concave_angle_threshold.setDecimals(2)
        self.bl_concave_angle_threshold.setStyleSheet(SPIN_STYLE)
        self.bl_concave_angle_threshold.setToolTip("Angle threshold to classify a corner as concave")

        self.bl_concave_influence_multiplier = CleanDoubleSpinBox()
        self.bl_concave_influence_multiplier.setRange(0.0, 100.0)
        self.bl_concave_influence_multiplier.setDecimals(2)
        self.bl_concave_influence_multiplier.setStyleSheet(SPIN_STYLE)
        self.bl_concave_influence_multiplier.setToolTip("Controls how far the concave corner correction propagates along the wall")

        self.bl_merge_concave = QCheckBox("Merge Concave")
        self.bl_merge_concave.setStyleSheet("color:#a0a8c0;")
        self.bl_merge_concave.setToolTip("Merge nearby concave corners into a single correction zone")

        self.bl_smoothing_iters = QSpinBox()
        self.bl_smoothing_iters.setRange(0, 100)
        self.bl_smoothing_iters.setStyleSheet(SPIN_STYLE)
        self.bl_smoothing_iters.setToolTip("Number of Laplacian smoothing passes applied to BL cells near concave corners")

        # ── BL / no-BL junction (a BL edge meeting a grow=0 neighbour) ─────
        # These are hidden backing widgets; the user edits them in the Edit-BL
        # dialog (mesh_dialogs._BL_FIELD_SPECS). Method 1 = 4-case angle-driven
        # scheme whose case selection is binned by the three θ thresholds.
        _JUNCTION_TIP = ("Flow-facing angle thresholds (deg) that bin the 4-case "
                         "BL/no-BL junction scheme: C1 concave-slide, C2/C3 cap "
                         "boundaries. Only used when Junction Method = 4-case.")
        self.bl_junction_method = QComboBox()
        self.bl_junction_method.addItems(["0: Taper-to-zero", "1: 4-case angle-driven"])
        self.bl_junction_method.setStyleSheet(COMBO_STYLE)
        self.bl_junction_method.setCurrentIndex(1)
        self.bl_junction_method.setToolTip(
            "How a BL edge meeting a no-BL neighbour is capped (1: angle-driven, default)")

        # Seed the spinboxes with the model defaults (θ bins 135/270/315) so a
        # fresh panel — before any config is loaded — reports the real defaults
        # rather than the spinbox floor (0), matching bl_junction_method's index.
        self.bl_junction_angle_c1 = CleanDoubleSpinBox()
        self.bl_junction_angle_c1.setRange(0.0, 360.0)
        self.bl_junction_angle_c1.setDecimals(2)
        self.bl_junction_angle_c1.setValue(135.0)
        self.bl_junction_angle_c1.setStyleSheet(SPIN_STYLE)
        self.bl_junction_angle_c1.setToolTip(_JUNCTION_TIP)

        self.bl_junction_angle_c2 = CleanDoubleSpinBox()
        self.bl_junction_angle_c2.setRange(0.0, 360.0)
        self.bl_junction_angle_c2.setDecimals(2)
        self.bl_junction_angle_c2.setValue(270.0)
        self.bl_junction_angle_c2.setStyleSheet(SPIN_STYLE)
        self.bl_junction_angle_c2.setToolTip(_JUNCTION_TIP)

        self.bl_junction_angle_c3 = CleanDoubleSpinBox()
        self.bl_junction_angle_c3.setRange(0.0, 360.0)
        self.bl_junction_angle_c3.setDecimals(2)
        self.bl_junction_angle_c3.setValue(315.0)
        self.bl_junction_angle_c3.setStyleSheet(SPIN_STYLE)
        self.bl_junction_angle_c3.setToolTip(_JUNCTION_TIP)

        concave_form.addRow(help_label("Concave Method:", "Method for handling concave (inward-pointing) corners in the boundary layer"), self.bl_concave_method)
        concave_form.addRow(help_label("Concave Threshold:", "Angle threshold to classify a corner as concave"), self.bl_concave_angle_threshold)
        concave_form.addRow(help_label("Influence Mult:", "Controls how far the concave corner correction propagates along the wall"), self.bl_concave_influence_multiplier)
        concave_form.addRow("", help_widget(self.bl_merge_concave, "Merge nearby concave corners into a single correction zone"))
        concave_form.addRow(help_label("Smoothing Iters:", "Number of Laplacian smoothing passes applied to BL cells near concave corners"), self.bl_smoothing_iters)
        concave_form.addRow(help_label("Junction Method:", "How a BL edge meeting a no-BL neighbour is capped"), self.bl_junction_method)
        concave_form.addRow(help_label("Junction θ C1:", _JUNCTION_TIP), self.bl_junction_angle_c1)
        concave_form.addRow(help_label("Junction θ C2:", _JUNCTION_TIP), self.bl_junction_angle_c2)
        concave_form.addRow(help_label("Junction θ C3:", _JUNCTION_TIP), self.bl_junction_angle_c3)
        align_form_labels(concave_form, 130)
        self.sec_concave.add_layout(concave_form)


    def _build_meshing_section(self):
        # ── Meshing Algorithm (the global-only params not in the BL dialog) ──
        # gmsh algorithm/optimize + concave merge/smoothing are meshing options
        # (not per-geometry BL), so they stay in the panel while the BL sections
        # (Core/Convex/Concave/Transition) are hidden — their fields are edited
        # in the Edit-BL dialog instead (#5). Re-adding these widgets here moves
        # them out of the now-hidden sections.
        self.sec_meshing = CollapsibleSection("Meshing Algorithm", start_collapsed=True)
        self._layout.addWidget(self.sec_meshing)
        mesh_algo_form = QFormLayout()
        mesh_algo_form.addRow(help_label("Gmsh Algorithm:", "Meshing algorithm used by Gmsh for far-field triangulation"), self.gmsh_algorithm)
        mesh_algo_form.addRow("", help_widget(self.gmsh_optimize, "Enable Gmsh mesh quality optimization pass after generation"))
        mesh_algo_form.addRow("", help_widget(self.bl_merge_concave, "Merge nearby concave corners into a single correction zone"))
        mesh_algo_form.addRow(help_label("Smoothing Iters:", "Laplacian smoothing passes applied to BL cells near concave corners"), self.bl_smoothing_iters)
        align_form_labels(mesh_algo_form, 130)
        self.sec_meshing.add_layout(mesh_algo_form)

        # Hide the BL parameter sections — their fields now live in the Edit-BL
        # dialog (global + per-geometry). The widgets stay alive to back the
        # global-BL store / round-trip.
        for _sec in (self.sec_bl_core, self.sec_convex, self.sec_concave,
                     self.sec_transition):
            _sec.setVisible(False)


    def _build_patches_section(self):
        # ── 7. Domain Boundary Patches (rectangle-box edges only) ─────────
        # Only relevant when Domain Source is "Rectangle box"; names the four box
        # edges. The NAME is a patch/grouping label — the physical BC TYPE is
        # assigned per patch later in the Solver → Boundary Conditions table
        # (auto-detected from the mesh), matching industrial software. #4: these
        # live in a pop-up (built into self._domain_patch_body, shown by
        # _open_domain_patch_dialog via the "Domain boundary patches…" button
        # above) instead of a panel section.
        self._domain_patch_body = QWidget()
        io_form = QFormLayout(self._domain_patch_body)
        io_form.setContentsMargins(0, 0, 0, 0)

        self.bc_xmin = BCWidget()
        self.bc_xmin_indicator = self.bc_xmin.indicator
        self.bc_xmin.setToolTip("Patch name for the left domain-box edge")

        self.bc_xmax = BCWidget()
        self.bc_xmax_indicator = self.bc_xmax.indicator
        self.bc_xmax.setToolTip("Patch name for the right domain-box edge")

        self.bc_ymin = BCWidget()
        self.bc_ymin_indicator = self.bc_ymin.indicator
        self.bc_ymin.setToolTip("Patch name for the bottom domain-box edge")

        self.bc_ymax = BCWidget()
        self.bc_ymax_indicator = self.bc_ymax.indicator
        self.bc_ymax.setToolTip("Patch name for the top domain-box edge")

        # Names the four rectangular-domain edges; the physical BC type is set
        # per patch in the Solver stage (auto-detected from the generated mesh).
        self._bc_intro_hint = QLabel(
            "Names the four rectangular-domain box edges (patch labels). The "
            "physical BC type is assigned per patch in the Solver → Boundary "
            "Conditions table, auto-detected from the generated mesh.")
        self._bc_intro_hint.setWordWrap(True)
        self._bc_intro_hint.setStyleSheet("color:#8a93ad; font-size:10px;")

        io_form.addRow(self._bc_intro_hint)
        io_form.addRow(help_label("XMin patch:", "Patch name for the left domain-box edge"), self.bc_xmin)
        io_form.addRow(help_label("XMax patch:", "Patch name for the right domain-box edge"), self.bc_xmax)
        io_form.addRow(help_label("YMin patch:", "Patch name for the bottom domain-box edge"), self.bc_ymin)
        io_form.addRow(help_label("YMax patch:", "Patch name for the top domain-box edge"), self.bc_ymax)
        # Narrow label column: the labels are short so a wide right-aligned column
        # left a big gap and stole width from the BCWidget fields (overflow).
        align_form_labels(io_form, 90)
        io_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        io_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._io_form = io_form
