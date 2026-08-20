"""Collapsible-section builders for MeshConfigPanel.

Every widget here comes from a field-spec table — ``MESH_SPECS`` for the panel's own
fields, ``PANEL_BL_SPECS`` for the 21 boundary-layer parameters it shares with the
Edit-BL dialog — so a section builder says which GROUP of rows it lays out and nothing
about the individual widgets. Each ``self.<attr> = <widget>(…)`` that used to sit here
(56 of them) was a second description of a field the read/write half named again;
``add_spec_rows`` is the one traversal that creates them, and it seeds each from
``MeshConfig``'s own default rather than from a literal repeated in build code.

The four BL parameter sections (Core / Convex / Concave / Transition) are built and
then HIDDEN: their fields are edited in the Edit-BL dialog (global + per-geometry) and
the widgets stay alive only to back the global-BL store and the config round-trip.
"""
from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QFormLayout, QLabel

from PyQt6.QtCore import Qt
from app.views.collapsible import CollapsibleSection
from app.utils import make_button, align_form_labels
from app.models.mesh_config import MeshConfig
from app.views.panels.field_widgets import SpecRowsMixin
from app.views.panels.mesh_bl_field_specs import PANEL_BL_SPECS
from app.views.panels.mesh_field_specs import MESH_SPECS


class MeshConfigBuildMixin(SpecRowsMixin):
    """Collapsible-section builders for MeshConfigPanel, extracted from
    __init__. Each appends to self._layout; runs on the composed panel.

    ``_spec_rows`` / ``_spec_widgets`` come from SpecRowsMixin; the BL sections pass
    PANEL_BL_SPECS explicitly because this panel has two tables.
    """

    _SPEC_TABLE = MESH_SPECS
    _SPEC_MODEL = MeshConfig

    def _build_sizing_section(self):
        # ── 2. General Sizing ─────────────────────────────────────────────
        # #11: renamed back to "Mesh Sizing" (it covers surface + far-field, not
        # only the far field).
        self.sec_sizing = CollapsibleSection("Mesh Sizing", start_collapsed=True)
        self._layout.addWidget(self.sec_sizing)

        sizing_form = QFormLayout()
        # Surface Size then its Auto toggle then the computed-size hint, and the same
        # three for the far field: ticking Auto does not hide the manual field (it
        # stays as the fallback the mesher uses if auto cannot derive a value).
        self._spec_rows(sizing_form, "sizing")
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

        # ── The four BL parameter sections ────────────────────────────────
        # Built so the widgets exist (they back the global-BL store and the config
        # round-trip) and hidden by _build_meshing_section: the user edits these
        # parameters in the Edit-BL dialog, from the same table.
        self.sec_bl_core = CollapsibleSection("Boundary Layer Core",
                                             start_collapsed=True)
        self._layout.addWidget(self.sec_bl_core)
        bl_form = QFormLayout()
        self._spec_rows(bl_form, "bl_core", PANEL_BL_SPECS)
        align_form_labels(bl_form, 130)
        self.sec_bl_core.add_layout(bl_form)

        self.sec_transition = CollapsibleSection("Transition & Meshing Algorithm",
                                                start_collapsed=True)
        self._layout.addWidget(self.sec_transition)
        trans_form = QFormLayout()
        trans_form.addRow(self._mesh_sublabel("BOUNDARY-LAYER TRANSITION"))
        self._spec_rows(trans_form, "transition", PANEL_BL_SPECS)
        align_form_labels(trans_form, 130)
        self.sec_transition.add_layout(trans_form)
        self._trans_form = trans_form
        self.bl_auto_transition_layers.currentIndexChanged.connect(
            self._update_transition_visibility)
        self._update_transition_visibility()

        self.sec_convex = CollapsibleSection("Convex Corner Handling",
                                            start_collapsed=True)
        self._layout.addWidget(self.sec_convex)
        self.convex_form = QFormLayout()
        self._spec_rows(self.convex_form, "convex", PANEL_BL_SPECS)
        align_form_labels(self.convex_form, 130)
        self.sec_convex.add_layout(self.convex_form)
        self.bl_convex_method.currentIndexChanged.connect(
            self._update_convex_widgets_visibility)
        self._update_convex_widgets_visibility()

        self.sec_concave = CollapsibleSection("Concave Corner Handling",
                                             start_collapsed=True)
        self._layout.addWidget(self.sec_concave)
        concave_form = QFormLayout()
        self._spec_rows(concave_form, "concave", PANEL_BL_SPECS)
        align_form_labels(concave_form, 130)
        self.sec_concave.add_layout(concave_form)

    def _build_meshing_section(self):
        # ── Meshing Algorithm (the global-only params not in the BL dialog) ──
        # gmsh algorithm/optimize + concave merge/smoothing are meshing options, not
        # per-geometry BL, so they live in the panel while the BL sections
        # (Core/Convex/Concave/Transition) are hidden (#5).
        self.sec_meshing = CollapsibleSection("Meshing Algorithm", start_collapsed=True)
        self._layout.addWidget(self.sec_meshing)
        mesh_algo_form = QFormLayout()
        self._spec_rows(mesh_algo_form, "meshing")
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
        # live in a pop-up (self._domain_patch_body, shown by
        # _open_domain_patch_dialog via the "Domain boundary patches…" button)
        # instead of a panel section.
        self._domain_patch_body = QWidget()
        io_form = QFormLayout(self._domain_patch_body)
        io_form.setContentsMargins(0, 0, 0, 0)

        # Prose, not a field: a spanning row, which is why it is not in the table.
        self._bc_intro_hint = QLabel(
            "Names the four rectangular-domain box edges (patch labels). The "
            "physical BC type is assigned per patch in the Solver → Boundary "
            "Conditions table, auto-detected from the generated mesh.")
        self._bc_intro_hint.setWordWrap(True)
        self._bc_intro_hint.setStyleSheet("color:#8a93ad; font-size:10px;")
        io_form.addRow(self._bc_intro_hint)

        self._spec_rows(io_form, "patches")
        # Each BCWidget owns its colour square; _update_bc_indicators repaints them.
        self.bc_xmin_indicator = self.bc_xmin.indicator
        self.bc_xmax_indicator = self.bc_xmax.indicator
        self.bc_ymin_indicator = self.bc_ymin.indicator
        self.bc_ymax_indicator = self.bc_ymax.indicator

        # Narrow label column: the labels are short so a wide right-aligned column
        # left a big gap and stole width from the BCWidget fields (overflow).
        align_form_labels(io_form, 90)
        io_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        io_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._io_form = io_form
