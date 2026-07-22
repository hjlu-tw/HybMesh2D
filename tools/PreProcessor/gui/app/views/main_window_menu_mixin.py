from __future__ import annotations
import os
from PyQt6.QtGui import QKeySequence


class MainWindowMenuMixin:
    """
    Menu bar, global shortcuts and recent-files handling for :class:`MainWindow`.

    Mixed into ``MainWindow`` (after ``QMainWindow``); every method references
    ``self.*`` attributes/widgets that ``MainWindow.__init__`` creates, resolved
    at call time via the MRO.

    The menu bar mirrors the workflow pages the user already navigates through
    ``mode_combo``: a page-agnostic ``File``/``Edit`` pair, then one menu per
    stage (``CAD`` → ``Mesh`` → ``Solver`` → ``Results`` → ``IBM``),
    then the cross-stage ``Pipeline`` menu and ``Help``. Every stage action first
    switches ``mode_combo`` to that stage's page, so a menu click always lands the
    user on the matching page. Keyboard shortcuts live on the menu actions
    themselves (no separate ``QShortcut`` objects, which would otherwise collide
    with the menu shortcuts as an "ambiguous shortcut overload").
    """

    # Mode indices, matching MainWindow.mode_combo item order
    # ("PreProcessor (CAD)", "Mesh Generator", "Mesh Statistics", "Solver",
    #  "Results", "Immersed Boundary (φ)").
    _MODE_CAD = 0
    _MODE_MESH = 1
    _MODE_SOLVER = 3
    _MODE_RESULTS = 4
    _MODE_IB = 5

    _MENU_QSS = """
        QMenuBar {
            background-color: #090a12;
            color: #a0a8c0;
            border-bottom: 1px solid #1c1e36;
        }
        QMenuBar::item {
            background-color: transparent;
            padding: 4px 10px;
        }
        QMenuBar::item:selected {
            background-color: #1e2235;
            color: #ffffff;
        }
        QMenu {
            background-color: #121422;
            color: #a0a8c0;
            border: 1px solid #1c1e36;
        }
        QMenu::item {
            padding: 6px 20px;
        }
        QMenu::item:selected {
            background-color: #3b82f6;
            color: #ffffff;
        }
        QMenu::separator {
            height: 1px;
            background: #1c1e36;
            margin: 4px 8px;
        }
    """

    # ── Menu bar ──────────────────────────────────────────────────────────

    def setup_shortcuts(self, controller):
        menubar = self.menuBar()
        menubar.setStyleSheet(self._MENU_QSS)

        def go(mode_idx, slot):
            """Switch to a stage's page, then run its action."""
            self.mode_combo.setCurrentIndex(mode_idx)
            slot()

        def add(menu, label, slot, *, mode=None, shortcut=None, tip=None):
            act = menu.addAction(label)
            if shortcut is not None:
                if isinstance(shortcut, (list, tuple)):
                    act.setShortcuts([QKeySequence(s) for s in shortcut])
                else:
                    act.setShortcut(QKeySequence(shortcut))
            if tip:
                act.setToolTip(tip)
            if mode is None:
                act.triggered.connect(lambda _checked=False, s=slot: s())
            else:
                act.triggered.connect(
                    lambda _checked=False, m=mode, s=slot: go(m, s))
            return act

        # ── File (project / workspace level — page-agnostic) ───────────────
        file_menu = menubar.addMenu("File")
        add(file_menu, "New Session", controller.new_blank_tab,
            shortcut=["Ctrl+N", "Ctrl+T"],
            tip="Create a new empty geometry workspace tab")
        self.recent_menu = file_menu.addMenu("Open Recent")
        controller.init_recent_files()
        file_menu.addSeparator()
        add(file_menu, "Save Workspace...", controller.save_workspace)
        add(file_menu, "Load Workspace...", controller.load_workspace)
        file_menu.addSeparator()
        add(file_menu, "Close Tab",
            lambda: controller.close_tab(controller.active_idx),
            shortcut="Ctrl+W")
        add(file_menu, "Exit", self.close)

        # ── Edit ────────────────────────────────────────────────────────────
        edit_menu = menubar.addMenu("Edit")
        add(edit_menu, "Undo", controller.undo, shortcut="Ctrl+Z")
        add(edit_menu, "Redo", controller.redo,
            shortcut=["Ctrl+Shift+Z", "Ctrl+Y"])

        # ── CAD (PreProcessor) ────────────────────────────────────────────
        cad_menu = menubar.addMenu("CAD")
        add(cad_menu, "Import Geometry (.dat)...", controller.load_geometry,
            mode=self._MODE_CAD, shortcut="Ctrl+O",
            tip="Open a .dat geometry file from disk")
        add(cad_menu, "Import STL Surface (z=0)...", controller.load_stl_geometry,
            mode=self._MODE_CAD,
            tip="Load a planar (z=0) STL surface as boundary points")
        add(cad_menu, "Load Configuration (.json)...", controller.load_json_config,
            mode=self._MODE_CAD,
            tip="Open a .json config with geometry and resampling settings")
        cad_menu.addSeparator()
        add(cad_menu, "Export Resampled Geometry (.dat)...", controller.save_output,
            mode=self._MODE_CAD, shortcut="Ctrl+S",
            tip="Run the resampler and save the resampled boundary geometry (.dat)")
        add(cad_menu, "Save Configuration (.json)...", controller.generate_json,
            mode=self._MODE_CAD)
        add(cad_menu, "Extrude to STL...", controller.extrude_active_to_stl,
            mode=self._MODE_CAD)
        cad_menu.addSeparator()
        add(cad_menu, "Join Edges into Polygon", controller.join_selected_edges_to_polygon,
            mode=self._MODE_CAD,
            tip="Merge selected end-to-end curve edges into one closed polygon "
                "(clears the 'boundary not closed' warning)")
        cad_menu.addSeparator()
        add(cad_menu, "Preview", controller.preview_backend,
            mode=self._MODE_CAD, shortcut="F5",
            tip="Run the PreProcessor and preview geometry / boundary conditions")

        # ── Mesh Generator ─────────────────────────────────────────────────
        mesh_menu = menubar.addMenu("Mesh")
        add(mesh_menu, "Load Mesh Config...", controller.load_mesh_config,
            mode=self._MODE_MESH)
        add(mesh_menu, "Save Mesh Config...", controller.save_mesh_config,
            mode=self._MODE_MESH)
        mesh_menu.addSeparator()
        add(mesh_menu, "Add All Sessions", controller.add_all_sessions_to_mesh,
            mode=self._MODE_MESH,
            tip="Add all exported PreProcessor sessions to this mesh config")
        mesh_menu.addSeparator()
        add(mesh_menu, "BC Preview", controller.preview_mesh_generator,
            mode=self._MODE_MESH)
        add(mesh_menu, "Generate Mesh", controller.run_mesh_generator,
            mode=self._MODE_MESH)
        add(mesh_menu, "Cancel", controller.cancel_mesh_generator,
            mode=self._MODE_MESH)
        add(mesh_menu, "Export Mesh...", controller.export_mesh_files,
            mode=self._MODE_MESH,
            tip="Export the generated mesh (VTK / STAR-CD)")

        # ── Solver ──────────────────────────────────────────────────────────
        solver_menu = menubar.addMenu("Solver")
        add(solver_menu, "Load Solver Config...", controller.load_solver_config,
            mode=self._MODE_SOLVER)
        add(solver_menu, "Save Solver Config...", controller.save_solver_config,
            mode=self._MODE_SOLVER)
        solver_menu.addSeparator()
        add(solver_menu, "Detect BC from Mesh", controller.detect_bc_from_mesh,
            mode=self._MODE_SOLVER)
        dll_menu = solver_menu.addMenu("Build DLL")
        add(dll_menu, "Initial Condition...",
            lambda: controller.open_dll_builder("init_cond"),
            mode=self._MODE_SOLVER)
        add(dll_menu, "Motion...",
            lambda: controller.open_dll_builder("motion"),
            mode=self._MODE_SOLVER)
        add(dll_menu, "Boundary Condition...", controller.open_bc_dll_builder,
            mode=self._MODE_SOLVER)
        solver_menu.addSeparator()
        add(solver_menu, "Run Solver", controller.run_solver_pipeline,
            mode=self._MODE_SOLVER)
        add(solver_menu, "Cancel", controller.cancel_solver,
            mode=self._MODE_SOLVER)

        # ── Results ──────────────────────────────────────────────────────────
        results_menu = menubar.addMenu("Results")
        add(results_menu, "Load Result...", controller.open_result_dialog,
            mode=self._MODE_RESULTS)
        add(results_menu, "Save PNG...", controller.export_result_screenshot,
            mode=self._MODE_RESULTS)

        # ── IBM (Immersed Boundary, φ) — sits to the right of Results ────────
        ib_menu = menubar.addMenu("IBM")
        add(ib_menu, "Import STL...", controller.browse_stl3d, mode=self._MODE_IB)
        add(ib_menu, "Fit Domain to STL", controller.fit_stl3d_domain,
            mode=self._MODE_IB)
        ib_menu.addSeparator()
        add(ib_menu, "Generate φ Grid", controller.run_stl3d, mode=self._MODE_IB)
        add(ib_menu, "Cancel", controller.cancel_stl3d, mode=self._MODE_IB)
        ib_menu.addSeparator()
        add(ib_menu, "Send Grid to Solver", controller.send_stl3d_to_solver,
            mode=self._MODE_IB)

        # ── Pipeline (cross-stage; the orchestrator drives the page itself) ──
        pipeline_menu = menubar.addMenu("Pipeline")
        add(pipeline_menu, "Run Full Pipeline", controller.run_full_pipeline,
            shortcut="Ctrl+R",
            tip="CAD resample → mesh → solver → results contour")
        pipeline_menu.addSeparator()
        add(pipeline_menu, "Load Pipeline Script...", controller.load_pipeline_file)
        add(pipeline_menu, "Save Pipeline Script...", controller.save_pipeline_file)

        # ── Help ───────────────────────────────────────────────────────────
        from PyQt6.QtWidgets import QMessageBox
        help_menu = menubar.addMenu("Help")
        add(help_menu, "About HybMesh2D", lambda: QMessageBox.about(
            self, "About HybMesh2D",
            "<b>HybMesh2D</b><br>"
            "2D hybrid mesh generator (boundary-layer quads + far-field "
            "triangles) for CFD, with a PyQt6 pre-processor.<br><br>"
            "Menus follow the workflow: "
            "CAD → Mesh → Solver → Results."))
        add(help_menu, "Keyboard Shortcuts", lambda: QMessageBox.information(
            self, "Keyboard Shortcuts", self._shortcuts_help_text()))

    @staticmethod
    def _shortcuts_help_text() -> str:
        return (
            "Ctrl+O\t\tImport geometry (.dat)\n"
            "Ctrl+S\t\tExport resampled geometry (.dat)\n"
            "Ctrl+N / Ctrl+T\tNew session\n"
            "Ctrl+W\t\tClose tab\n"
            "Ctrl+Z\t\tUndo\n"
            "Ctrl+Shift+Z / Ctrl+Y\tRedo\n"
            "F5\t\tCAD preview\n"
            "Ctrl+R\t\tRun full pipeline"
        )

    # ── Recent files ─────────────────────────────────────────────────────

    def refresh_recent_files_menu(self, files: list[str], controller):
        self.recent_menu.clear()
        if not files:
            empty_action = self.recent_menu.addAction("No Recent Files")
            empty_action.setEnabled(False)
            return
        for f in files:
            action = self.recent_menu.addAction(os.path.basename(f))
            action.setToolTip(f)
            # Use default argument in lambda to bind loop variable f properly
            action.triggered.connect(lambda checked, path=f: controller.load_recent_file(path))
