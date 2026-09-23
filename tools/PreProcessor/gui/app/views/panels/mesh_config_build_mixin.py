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
from app.views.panels.field_widgets import SpecRowsMixin, edit_signal
from app.views.panels.mesh_bl_field_specs import PANEL_BL_SPECS
from app.views.panels.mesh_field_specs import MESH_SPECS
from app.services.geom_path_identity import canonical_geom_path
from app.services.topology_field_specs import BINDING_ROWS, TOPOLOGY_SPECS
from app.services.topology_model import TopologyModel


class MeshConfigBuildMixin(SpecRowsMixin):
    """Collapsible-section builders for MeshConfigPanel, extracted from
    __init__. Each appends to self._layout; runs on the composed panel.

    ``_spec_rows`` / ``_spec_widgets`` come from SpecRowsMixin; the BL sections pass
    PANEL_BL_SPECS explicitly because this panel has two tables.
    """

    _SPEC_TABLE = MESH_SPECS
    _SPEC_MODEL = MeshConfig

    def _build_mode_section(self):
        # ── 0b. Which generation path runs ────────────────────────────────
        # NOT collapsible and first after the unit row, for the unit row's own
        # reason: it decides which of the fields below take effect at all. The
        # topology-file row is declared `modes=(MULTIBLOCK,)` and so is hidden by
        # _apply_mode_visibility in the default mode — one declaration drives both
        # this panel and the mesher's inert-parameter warnings.
        mode_form = QFormLayout()
        mode_form.setContentsMargins(6, 0, 6, 0)
        self._spec_rows(mode_form, "mode")
        align_form_labels(mode_form, 130)
        self._layout.addLayout(mode_form)
        self.mesh_mode.currentIndexChanged.connect(self._apply_mode_visibility)

    def _build_topology_section(self):
        # ── 0c. Block Topology ────────────────────────────────────────────
        # Only the multi-block path fills a topology, so every row here declares
        # `modes=(MULTIBLOCK,)` and _apply_mode_visibility hides the whole section
        # in the hybrid mode — one declaration, the same one the mesher's
        # inert-parameter warnings read.
        #
        # SEEDED FROM TopologyModel, not from MeshConfig: `_spec_rows` seeds each
        # widget from `_SPEC_MODEL()`, and this table's rows author fields of the
        # topology model. A panel is otherwise built with whatever Qt leaves in an
        # un-set widget, and since the panel->model sync reads every panel back at
        # startup, that value would BECOME the session's default (SpecRowsMixin's
        # own reason, applied to the panel's third table).
        self.sec_topology = CollapsibleSection("Block Topology (template)",
                                               start_collapsed=True)
        self._layout.addWidget(self.sec_topology)
        topo_form = QFormLayout()
        self._spec_rows(topo_form, "topology", table=TOPOLOGY_SPECS,
                        model=TopologyModel)
        align_form_labels(topo_form, 130)
        self.sec_topology.add_layout(topo_form)

        # THE CAPTURE IS WIRED FIRST, and the order is the rule rather than an
        # accident: Qt calls slots in connection order, so with the read-out wired
        # first, naming a geometry emitted once carrying the binding it was about to
        # replace — a `topology_changed` describing a configuration that existed for
        # no one. Wired here, the first emit already carries the captured binding.
        _by_attr = {sp.attr: sp for sp in TOPOLOGY_SPECS}
        for geom_attr, segs_attr in BINDING_ROWS:
            w = getattr(self, geom_attr, None)
            if w is None or getattr(self, segs_attr, None) is None:
                continue
            sig = edit_signal(w, _by_attr[geom_attr])
            if sig is not None:
                sig.connect(lambda *_a, g=geom_attr, t=segs_attr:
                            self._capture_topology_binding(g, t))

        # The derived counts are a READ-OUT of the family's own derivation, so it
        # refreshes whenever any parameter that feeds it changes — including the
        # family itself, which decides whether there is a derivation at all.
        for spec in TOPOLOGY_SPECS:
            w = getattr(self, spec.attr, None)
            if w is None:
                continue
            sig = edit_signal(w, spec)
            if sig is not None:
                sig.connect(self._on_topology_edited)
        # The MODE is the other half of "is there a skeleton to draw"
        # (`topology_skeleton.skeleton_for_config` asks both), and it is not a row
        # of this table — so without this line the canvas would keep drawing a
        # topology while this very section is hidden by `_apply_mode_visibility`.
        # Wired here rather than in `_build_mode_section` because it is the
        # TEMPLATE that cares; the mode row itself is unchanged.
        self.mesh_mode.currentIndexChanged.connect(self._on_topology_edited)
        self._refresh_topology_counts()

    def _capture_topology_binding(self, geom_attr: str, segs_attr: str):
        """Write the named geometry's CURRENT segment ids into its binding row.

        WHAT MAKES A LATER DELETION A REFUSAL RATHER THAN A SHORTER RING. With the
        row blank the family adopts whatever the geometry has at projection time, so
        removing a bound segment would quietly produce a different mesh; once these
        ids are stored, the same removal is refused with the edge named (#137).
        Capturing HERE — the moment the user names the geometry — is the one moment
        they have said which shape they mean.

        KEYED BY THE FILE THE BINDING WAS CAPTURED FOR, not by whether the held ids
        still happen to resolve. Review found the difference: both shipped circles
        carry segments 0-3, so a user switching the body from one to the other kept a
        binding chosen for the OTHER shape — the walls then bind segments never
        picked for the geometry they lie on, which is this ticket's own failure class
        reached by another route. A held binding therefore survives only a re-naming
        of the SAME file (which is what #138's repair will write), and a different
        file is always a fresh capture.

        The row itself is READ-ONLY (`topology_field_specs.BINDING_ROWS`), because
        #133 decides that which edges bind is the template's decision and not the
        user's. Parsing what is held still goes through the family's own
        `parse_binding`, so "is the held binding good?" and "what does the projection
        bind?" cannot answer about different readings of one string — they did, and
        disagreed on a malformed token.
        """
        if getattr(self, "_loading", False):
            return
        from app.services import topology_binding, topology_ogrid
        w, sw = getattr(self, geom_attr, None), getattr(self, segs_attr, None)
        if w is None or sw is None:
            return
        name = w.text().strip()
        if not name:
            return
        g = topology_binding.geometry_binding(name)
        if not g.seg_ids:
            return
        captured_for = getattr(self, "_topo_captured_for", None)
        if captured_for is None:
            captured_for = self._topo_captured_for = {}
        canon = canonical_geom_path(name) or name
        held, why = topology_ogrid.parse_binding(sw.text(), (), "binding")
        if (not why and held and captured_for.get(segs_attr) == canon
                and all(s in g.spans for s in held)):
            return
        captured_for[segs_attr] = canon
        sw.setText(", ".join(str(s) for s in g.seg_ids))

    def _on_topology_edited(self, *_args):
        """A template parameter changed: refresh the read-out AND tell the canvas.

        The emit is what makes the canvas skeleton follow the parameters as they
        are typed (#136). It is needed because ``mesh_config_changed`` fires for
        STRUCTURAL actions — the geometry list, a role, a BC — and not for a plain
        spin box, which is the same gap ``undo_ctrl._wire_widget_edits`` exists to
        cover for the undo recorder; the canvas has no such generic traversal, and
        the overlay is the first thing on it that has to track a typed number.

        ``topology_changed`` and NOT ``mesh_config_changed``, which is the review
        finding both axes reported. This fires per KEYSTROKE, and that signal's
        listener reloads every geometry preview and re-reads every `.meta` —
        measured at 12 preview reloads for five characters typed — and worse,
        `update_geometry_previews` opens by clearing the selection highlight, so
        typing here dropped the outline of the geometry selected in the config list
        and nothing put it back. The narrow signal reaches the same
        `update_mesh_config`, with `reload_geometry=False`.

        Suppressed while ``set_config`` populates — the `text` rows report
        ``textChanged``, which Qt also emits for a programmatic write — because an
        emit from inside a population re-enters the panel->model sync with the
        widgets half-written. ``set_config`` ends with its own
        ``mesh_config_changed``, so the canvas still learns about a programmatic
        push; it simply learns once, through the wide route that a push deserves.
        """
        if getattr(self, "_loading", False):
            # No `get_config()` from inside a population: the widgets are half
            # written, and the read-out that needs a config is the one that would
            # then describe a configuration that never existed. `set_config` calls
            # the read-out itself, with the config it is writing.
            self._refresh_topology_counts()
            return
        cfg = self.get_config()
        self._refresh_topology_counts(cfg)
        self.topology_changed.emit(cfg)

    def _refresh_topology_counts(self, cfg=None):
        """Show what the family functions derive from the parameters as typed.

        Reads the ONE owner of each derivation rather than repeating it
        (``topology_hgrid.hgrid_counts`` and ``topology_ogrid.plan``, which are also
        what the documents seed), so the panel cannot display a figure the generated
        mesh does not use.

        ``cfg`` is the mesh configuration the O-grid's derivation resolves its
        geometries against; ``None`` means "not available here", which is the state
        during a population and at construction. The H-grid half needs none — it
        binds to nothing.
        """
        from app.services import topology_hgrid, topology_ogrid
        from app.views.panels.field_widgets import read_specs
        model = TopologyModel()
        read_specs(self, TOPOLOGY_SPECS, model)
        lbl = getattr(self, "topo_hgrid_counts_derived", None)
        if lbl is not None:
            if model.family != topology_hgrid.FAMILY:
                # No family, or a family this read-out is not about. Said rather
                # than left blank: a blank cell in a row of numbers reads as a zero.
                lbl.setText("—  (no template selected)")
            else:
                xc, yc = topology_hgrid.hgrid_counts(model)
                lbl.setText(f"X: {', '.join(str(v) for v in xc)}    "
                            f"Y: {', '.join(str(v) for v in yc)}"
                            f"    ({len(xc)}x{len(yc)} blocks)")
        lbl = getattr(self, "topo_ogrid_derived", None)
        if lbl is None:
            return
        if model.family != topology_ogrid.FAMILY:
            lbl.setText("—  (no template selected)")
            return
        from app.services import topology_binding
        ctx = None if cfg is None else topology_binding.context_for_config(cfg)
        lbl.setText("\n".join(topology_ogrid.plan(model, ctx).lines()))

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
