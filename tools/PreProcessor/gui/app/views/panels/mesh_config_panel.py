from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from app.utils import (
    make_button,
)

from app.views.panels.mesh_bl_mixin import MeshConfigBLMixin
from app.views.panels.mesh_sizing_mixin import MeshConfigSizingMixin
from app.views.panels.mesh_config_config_mixin import MeshConfigConfigMixin
from app.views.panels.mesh_domain_mixin import MeshConfigDomainMixin
from app.views.panels.mesh_output_mixin import MeshConfigOutputMixin
from app.views.panels.mesh_config_build_mixin import MeshConfigBuildMixin
from app.views.panels.mesh_units_mixin import MeshConfigUnitsMixin


class MeshConfigPanel(QScrollArea, MeshConfigBLMixin, MeshConfigSizingMixin,
                      MeshConfigConfigMixin, MeshConfigDomainMixin,
                      MeshConfigOutputMixin, MeshConfigBuildMixin,
                      MeshConfigUnitsMixin):
    """Scrollable panel containing editor widgets for all Background_para.dat options."""
    geom_files_changed = pyqtSignal(list)
    mesh_config_changed = pyqtSignal(object)
    # Emitted when Domain Source flips (True = custom geometry outline) so the
    # canvas can hide the rectangular domain box + its per-edge BC colours.
    domain_source_changed = pyqtSignal(bool)
    # Emitted with the file path of the geometry selected in the list ("" when
    # none) so the canvas can highlight the matching geometry.
    geom_selection_changed = pyqtSignal(str)
    # Emitted with an Nx2 coords array (or None) to highlight one segment on the
    # canvas while the per-segment BC dialog is open.
    # A Mesh-stage per-segment edit: the No-BL toggle and the BC label. Emitted
    # rather than written straight to the .meta sidecar, because that file is not
    # where either fact should live — the resampler rewrites it from the CAD
    # config on every save. The controller puts them on the SegmentModel (where
    # undo, the workspace and the pipeline script can see them) and writes the
    # sidecar from there.
    seg_grow_bl_changed = pyqtSignal(str, dict)
    seg_bc_labels_changed = pyqtSignal(str, dict)

    segment_highlight_requested = pyqtSignal(object)
    # #5: emitted by the Output "Export mesh…" button to save the generated mesh.
    export_mesh_requested = pyqtSignal()

    # Per-item data role storing the geometry's mesh role (seed dict or None)
    _ROLE_DATA = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        # Show a horizontal scrollbar (the bottom left-right slider) when content
        # is wider than the panel, so labels/values that overflow the narrow
        # sidebar can be scrolled into view instead of being clipped.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background: #0c0d16;")

        # Custom scrollbar styling
        self.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical {
                border: none;
                background: #0c0d16;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #2c2e43;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3e415e;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        # Match the horizontal slider (shown when content overflows the width).
        self.horizontalScrollBar().setStyleSheet("""
            QScrollBar:horizontal {
                border: none;
                background: #0c0d16;
                height: 10px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background: #2c2e43;
                min-width: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #3e415e;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

        content = QWidget()
        content.setStyleSheet("background: #121422; color: #a0a8c0;")
        content.setMaximumWidth(430)  # Prevent content from expanding beyond sidebar
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(6, 6, 6, 6)
        self._layout.setSpacing(6)
        self.setWidget(content)

        # ── Control Buttons ───────────────────────────────────────────────
        # Load/Save Config live in the Mesh menu (menu bar). The buttons are
        # kept as attributes so controller.py keeps its clicked wiring, but they
        # are no longer shown in the side panel.
        self.load_config_btn = make_button("Load Config File")
        self.save_config_btn = make_button("Save Config File", "#301540")

        # Row 2: Preview / Run / Cancel (Redundant, not added to layout to keep sidebar clean since they are in the top toolbar)
        self.preview_btn = make_button("BC Preview", "#1e2a38")
        self.run_mesh_btn = make_button("Mesh Generate", "#1e4620")
        self.cancel_mesh_btn = make_button("Cancel", "#4a1c1c")
        self.cancel_mesh_btn.setEnabled(False)

        # The former separate "Geometry Layers" (session checklist) and
        # "Geometry Input Files" (file list) overlapped, so they are merged into
        # the single geometry list in the "Domain & Geometry" section below. The
        # "Add All Sessions" button is created here and placed in that list's
        # button row.
        self.add_all_sessions_btn = make_button("Add All", "#1a2a3a")
        self.add_all_sessions_btn.setToolTip("Add all exported PreProcessor sessions to this mesh configuration")

        # ── 0. Model unit ─────────────────────────────────────────────────
        # First, and not collapsible: it is what every number below means.
        self._build_units_section()

        # ── 1. Domain & Geometry Files ────────────────────────────────────
        # Section builder (combo + bounding box + geometry list + role editor)
        # relocated to MeshConfigDomainMixin.
        self._build_domain_section()

        self._build_sizing_section()
        self._build_bl_param_sections()
        self._build_meshing_section()
        self._build_patches_section()
        # ── 8. Output ─────────────────────────────────────────────────────
        # Section builder (output name + write-format buttons + Export mesh…)
        # relocated to MeshConfigOutputMixin.
        self._build_output_section()

        # Spacer at the end
        self._layout.addStretch()

        # Connect internal Browse button
        self.add_file_geom_btn.clicked.connect(self._on_browse_geom)
        self.remove_geom_btn.clicked.connect(self._on_remove_geom)
        self.export_mesh_btn.clicked.connect(self.export_mesh_requested)  # #5

        # Connect BC textChanged signals
        self.bc_xmin.textChanged.connect(self._update_bc_indicators)
        self.bc_xmax.textChanged.connect(self._update_bc_indicators)
        self.bc_ymin.textChanged.connect(self._update_bc_indicators)
        self.bc_ymax.textChanged.connect(self._update_bc_indicators)
        # #3: mark the domain BCs as user-configured on any edit, so the BC
        # Preview switches from the neutral (grey) untouched state to real
        # colours only once the user has actually chosen a BC.
        self._bc_configured = False
        for w in (self.bc_xmin, self.bc_xmax, self.bc_ymin, self.bc_ymax):
            w.textChanged.connect(self._mark_bc_configured)

        # Route every BL-section edit through one handler so it lands in either
        # the global defaults or the selected geometry's override.
        self._wire_bl_widgets()
        self._global_bl = self._read_bl_widgets()

        # Now that every section's fields exist, stamp the unit on the length ones
        # (the call inside _build_units_section ran before they were created).
        self._apply_unit_suffixes()

        self._update_domain_source_visibility()
    # Geometry-list / role handlers + get_config/set_config: MeshConfigConfigMixin.
