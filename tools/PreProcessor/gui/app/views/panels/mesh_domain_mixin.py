"""Domain & Geometry section builder for MeshConfigPanel, split out as a mixin
(behaviour unchanged): the domain-source combo, the rectangular bounding-box
spinners + domain-patch button, the merged geometry-file list and the selected-
geometry role editor (boundary / no-BL / seed / domain roles, per-geometry BL /
segment-BC / segment-BL pop-up buttons).

The section-building code was relocated verbatim from MeshConfigPanel.__init__;
the geometry-list handlers, role handlers and get_config/set_config stay in
MeshConfigConfigMixin, and the visibility/pop-up helpers referenced by the wired
signals stay in MeshConfigSizingMixin / MeshConfigConfigMixin — they resolve on
self via the shared MRO."""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QFormLayout, QComboBox, QLabel, QListWidget,
)
from app.views.collapsible import CollapsibleSection
from app.utils import (
    make_button, COMBO_STYLE, align_form_labels,
    help_label, help_widget,
)


class MeshConfigDomainMixin:
    """Builds the "Domain & Geometry" panel section (widgets + wiring)."""

    def _build_domain_section(self):
        # ── 1. Domain & Geometry Files ────────────────────────────────────
        self.sec_domain = CollapsibleSection("Domain & Geometry", start_collapsed=True)
        self._layout.addWidget(self.sec_domain)

        # Domain source: the rectangular box, or a geometry acting as the outer
        # domain outline. When "Custom geometry" is chosen the box X/Y Min/Max are
        # hidden (the domain comes from whichever geometry has a Domain role in the
        # list below); "Rectangle box" shows them.
        dsrc_form = QFormLayout()
        self.domain_source_combo = QComboBox()
        self.domain_source_combo.addItems(["Rectangle box", "Custom geometry"])
        # #1: default to Custom geometry on first entry (set before the signal is
        # connected so the visibility handler isn't called before its widgets exist).
        self.domain_source_combo.setCurrentIndex(1)
        self.domain_source_combo.setStyleSheet(COMBO_STYLE)
        self.domain_source_combo.setToolTip(
            "Rectangle box: the domain is the X/Y Min/Max box below.\n"
            "Custom geometry: a geometry in the list is the outer domain — set its "
            "role to 'Domain: far-field' (external) or 'Domain: wall' (internal).")
        dsrc_form.addRow(help_label("Domain Source:",
            "Use the rectangular box, or a geometry as the outer domain outline"),
            self.domain_source_combo)
        align_form_labels(dsrc_form, 130)
        self.sec_domain.add_layout(dsrc_form)

        # Bounding box (shown only for the "Rectangle box" source). Seeded from
        # the model's own defaults by the spec builder: a spin box left at Qt's 0
        # makes an untouched panel report a degenerate 0..0 domain, which then fails
        # validation on numbers the user never set and — with the fields hidden
        # under a custom domain — cannot even see.
        self._domain_box_widget = QWidget()
        dom_form = QFormLayout(self._domain_box_widget)
        dom_form.setContentsMargins(0, 0, 0, 0)
        self._spec_rows(dom_form, "domain")
        align_form_labels(dom_form, 130)
        self.sec_domain.add_widget(self._domain_box_widget)

        # #4: the four rectangle-box edge patch names are edited in a POP-UP opened
        # from this button (right under the box), instead of a separate panel
        # section. Only meaningful for the rectangle box, so the button is hidden
        # for a custom domain (whose outer patches come from the outline's per-edge
        # CAD names). The dialog + its widgets are built lazily on first open.
        self.domain_patch_btn = make_button("Domain boundary patches…", "#243a52")
        self.domain_patch_btn.setToolTip(
            "Name the four rectangular-domain box edges (XMin/XMax/YMin/YMax) in a "
            "pop-up. The physical BC type is assigned per patch in the Solver → "
            "Boundary Conditions table (auto-detected from the generated mesh).")
        self.sec_domain.add_widget(self.domain_patch_btn)
        self.domain_patch_btn.clicked.connect(self._open_domain_patch_dialog)
        self._domain_patch_dialog = None

        self.domain_source_combo.currentIndexChanged.connect(self._update_domain_source_visibility)

        # Geometry file list (the single merged geometry list)
        geom_label = QLabel("Geometry files (add / assign role / remove):")
        geom_label.setStyleSheet("color: #a0b0d0; margin-top: 6px; font-weight: bold;")
        self.sec_domain.add_widget(help_widget(geom_label, "Geometry files to load for meshing"))

        self.geom_list_widget = QListWidget()
        self.geom_list_widget.setFixedHeight(80)
        self.geom_list_widget.setStyleSheet(
            "background: #181b2a; color: #a0a8c0; border: 1px solid #333852; border-radius: 3px;"
        )
        self.sec_domain.add_widget(help_widget(self.geom_list_widget, "List of geometry boundary files to include in the computational domain"))

        # Geometry list control buttons — two rows so four buttons don't force the
        # sidebar wider than its fixed width.
        self.add_active_geom_btn = make_button("Add Active", "#1a2525")
        self.add_active_geom_btn.setToolTip("Add the active PreProcessor resampled file")
        self.add_file_geom_btn = make_button("Browse", "#1d2a3a")
        self.remove_geom_btn = make_button("Remove", "#301a1a")

        geom_btn_row1 = QHBoxLayout(); geom_btn_row1.setSpacing(4)
        geom_btn_row1.addWidget(help_widget(self.add_all_sessions_btn, "Add all exported PreProcessor sessions"))
        geom_btn_row1.addWidget(help_widget(self.add_active_geom_btn, "Add the active PreProcessor resampled geometry"))
        geom_btn_row2 = QHBoxLayout(); geom_btn_row2.setSpacing(4)
        geom_btn_row2.addWidget(help_widget(self.add_file_geom_btn, "Browse for geometry files on disk"))
        geom_btn_row2.addWidget(help_widget(self.remove_geom_btn, "Remove selected geometry file from list"))
        self.sec_domain.add_layout(geom_btn_row1)
        self.sec_domain.add_layout(geom_btn_row2)

        # ── Geometry Role (Boundary vs Refinement Seed) ───────────────────
        # Set the role of the geometry SELECTED in the list above: a body-fitted
        # boundary (grows boundary layers) or a refinement seed (Pointwise-like
        # source that only drives a local minimum mesh size).
        role_label = QLabel("Selected Geometry Role:")
        role_label.setStyleSheet("color: #a0b0d0; margin-top: 6px; font-weight: bold;")
        self.sec_domain.add_widget(help_widget(role_label,
            "Set the role of the geometry selected in the list above."))

        role_form = QFormLayout()
        self.geom_role_combo = QComboBox()
        # Index order is relied on by _on_geom_selection_changed / _on_role_edited /
        # _update_role_visibility below — keep them in sync.
        self.geom_role_combo.addItems([
            "Boundary (grows BL)",              # 0 -> None (obstacle, BL outward)
            "No-BL (far-field size)",           # 1 -> {"role":"nobl"}
            "Seed (refinement source)",         # 2 -> {"role":"seed",...}
            "Domain: far-field (no BL)",        # 3 -> {"role":"farfield"}  (external)
            "Domain: wall (internal, BL in)",   # 4 -> {"role":"wall"}      (internal flow)
        ])
        self.geom_role_combo.setStyleSheet(COMBO_STYLE)
        self.geom_role_combo.setEnabled(False)
        self.geom_role_combo.setToolTip(
            "Boundary: grows a boundary layer (external-flow obstacle / wall) — default.\n"
            "No-BL: no boundary layer; the mesh conforms to it at far-field size.\n"
            "Seed: only drives a local minimum mesh size (no BL, not a boundary).\n"
            "Domain far-field: this closed outline is the outer domain (no BL, external flow).\n"
            "Domain wall: this closed outline is the outer domain and grows its BL inward "
            "(internal flow — mesh the interior).\n"
            "The rectangular box (Domain X/Y Min/Max) is used unless one geometry has a "
            "Domain role. At most one Domain geometry.")

        self.seed_mode = QComboBox()
        self.seed_mode.addItems(["source (sizing only)", "embed (conform)"])
        self.seed_mode.setStyleSheet(COMBO_STYLE)
        self.seed_mode.setToolTip(
            "source: mesh does NOT conform to the seed (pure sizing source).\n"
            "embed: mesh nodes conform to the seed curve (still no boundary layer).")

        # Per-geometry wall BC / patch name. #2: the inline "Wall BC" field was
        # REMOVED from the role editor — a geometry's wall patch is grouped in CAD
        # (Assign patch / group…) and its BC chosen in Edit segment BCs, so a
        # separate per-geometry field only re-appeared inconsistently (it showed
        # for geometries without segment BCs) and duplicated that flow. The widget
        # is kept alive (not placed in any layout, always hidden) so existing
        # per-geometry `bc` values still round-trip through the role data, and the
        # handlers/signal wiring referencing it stay valid.
        self.geom_bc_combo = QComboBox()
        self.geom_bc_combo.setEditable(True)
        self.geom_bc_combo.setStyleSheet(COMBO_STYLE)
        self.geom_bc_combo.setVisible(False)

        role_form.addRow(help_label("Role:", "Body-fitted boundary or refinement seed"), self.geom_role_combo)
        # Seed Size / Seed Radius: physical lengths, so they are declared in the
        # panel's table (that is what puts a unit suffix on them) even though they
        # write per-geometry ROLE data rather than a MeshConfig field.
        self._spec_rows(role_form, "seed")
        role_form.addRow(help_label("Seed Mode:", "source (sizing only) or embed (conform)"), self.seed_mode)

        # Per-geometry boundary layer is edited in a pop-up dialog; the panel's
        # BL sections below always edit the GLOBAL default. The button is enabled
        # only for BL-growing geometries (Boundary / Domain: wall). The pop-up
        # also carries the per-segment 'grow BL?' toggles when the geometry has a
        # segmented .meta sidecar.
        self.edit_bl_btn = make_button("Edit boundary layer…", "#243a52")
        self.edit_bl_btn.setToolTip(
            "Open a pop-up to give THIS geometry its own boundary layer "
            "(thickness, growth, layers, corners, transition). When the geometry "
            "has segments, the same pop-up also lets you choose which segments "
            "grow a boundary layer. The BL sections in the panel below always "
            "edit the GLOBAL default.")
        self.edit_bl_btn.setEnabled(False)
        role_form.addRow(self.edit_bl_btn)

        # Per-segment BC: open a pop-up listing every segment of the selected
        # geometry (from its .meta sidecar) to assign a patch name / BC to each.
        # Enabled only when the geometry has a segmented .meta.
        self.edit_seg_bc_btn = make_button("Edit segment BCs…", "#243a52")
        self.edit_seg_bc_btn.setToolTip(
            "Open a pop-up listing every segment of THIS geometry and assign a "
            "patch name / BC to each (saved to the .meta sidecar). Available for "
            "geometries exported with segments from CAD.")
        self.edit_seg_bc_btn.setEnabled(False)
        role_form.addRow(self.edit_seg_bc_btn)

        align_form_labels(role_form, 130)
        self.sec_domain.add_layout(role_form)
        self._role_form = role_form
        self._role_updating = False

        # BL editing scope: None = global defaults, else the geom list item whose
        # per-geometry override the BL sections currently edit. _global_bl holds
        # the authoritative global values regardless of which scope is shown.
        self._bl_target_item = None
        self._global_bl: dict = {}
        self._bl_updating = False

        self.geom_list_widget.currentItemChanged.connect(self._on_geom_selection_changed)
        self.geom_role_combo.currentIndexChanged.connect(self._on_role_edited)
        self.seed_size.valueChanged.connect(self._on_role_edited)
        self.seed_radius.valueChanged.connect(self._on_role_edited)
        self.seed_mode.currentIndexChanged.connect(self._on_role_edited)
        self.geom_bc_combo.currentTextChanged.connect(self._on_geom_bc_edited)
        self.edit_bl_btn.clicked.connect(self._open_bl_override_dialog)
        self.edit_seg_bc_btn.clicked.connect(self._open_segment_bc_dialog)
        # #4: per-group BC-type assignments (grouping name -> BC type), edited via
        # the segment-BC dialog and round-tripped through MeshConfig.group_bc.
        self._group_bc: dict = {}
        self._update_role_visibility()
