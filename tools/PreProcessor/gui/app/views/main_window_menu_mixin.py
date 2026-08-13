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
        file_menu = menubar.addMenu(self.tr("File"))
        add(file_menu, self.tr("New Session"), controller.new_blank_tab,
            shortcut=["Ctrl+N", "Ctrl+T"],
            tip=self.tr("Create a new empty geometry workspace tab"))
        self.recent_menu = file_menu.addMenu(self.tr("Open Recent"))
        controller.init_recent_files()
        file_menu.addSeparator()
        add(file_menu, self.tr("Save Workspace..."), controller.save_workspace)
        add(file_menu, self.tr("Load Workspace..."), controller.load_workspace)
        file_menu.addSeparator()
        add(file_menu, self.tr("Close Tab"),
            lambda: controller.close_tab(controller.active_idx),
            shortcut="Ctrl+W")
        add(file_menu, self.tr("Exit"), self.close)

        # ── Edit ────────────────────────────────────────────────────────────
        edit_menu = menubar.addMenu(self.tr("Edit"))
        add(edit_menu, self.tr("Undo"), controller.undo, shortcut="Ctrl+Z")
        add(edit_menu, self.tr("Redo"), controller.redo,
            shortcut=["Ctrl+Shift+Z", "Ctrl+Y"])

        # ── View (dock visibility) ─────────────────────────────────────────
        # The Log Console dock has a close button but nothing re-opened it, and
        # ui_state persists its hidden state, so closing it once lost every run
        # log for good (there is no QToolBar either, so Qt's own dock context
        # menu has nothing to pop up from). toggleViewAction() is Qt's own
        # action for the dock, so the check state follows the close button too.
        log_dock = getattr(self, "log_dock", None)
        if log_dock is not None:
            view_menu = menubar.addMenu(self.tr("View"))
            log_act = log_dock.toggleViewAction()
            log_act.setText(self.tr("Log Console"))
            log_act.setShortcut(QKeySequence("Ctrl+L"))
            log_act.setToolTip(self.tr("Show or hide the log console at the bottom"))
            view_menu.addAction(log_act)

        # ── CAD (PreProcessor) ────────────────────────────────────────────
        cad_menu = menubar.addMenu(self.tr("CAD"))
        add(cad_menu, self.tr("Import Geometry (.dat)..."), controller.load_geometry,
            mode=self._MODE_CAD, shortcut="Ctrl+O",
            tip=self.tr("Open a .dat geometry file from disk"))
        add(cad_menu, self.tr("Import STL Surface (z=0)..."), controller.load_stl_geometry,
            mode=self._MODE_CAD,
            tip=self.tr("Load a planar (z=0) STL surface as boundary points"))
        add(cad_menu, self.tr("Load Configuration (.json)..."), controller.load_json_config,
            mode=self._MODE_CAD,
            tip=self.tr("Open a .json config with geometry and resampling settings"))
        cad_menu.addSeparator()
        add(cad_menu, self.tr("Export Resampled Geometry (.dat)..."), controller.save_output,
            mode=self._MODE_CAD, shortcut="Ctrl+S",
            tip=self.tr("Run the resampler and save the resampled boundary geometry (.dat)"))
        add(cad_menu, self.tr("Save Configuration (.json)..."), controller.generate_json,
            mode=self._MODE_CAD)
        add(cad_menu, self.tr("Extrude to STL..."), controller.extrude_active_to_stl,
            mode=self._MODE_CAD)
        cad_menu.addSeparator()
        add(cad_menu, self.tr("Join Edges into Polygon"), controller.join_selected_edges_to_polygon,
            mode=self._MODE_CAD,
            tip=self.tr("Merge selected end-to-end curve edges into one closed polygon "
                    "(clears the 'boundary not closed' warning)"))
        cad_menu.addSeparator()
        add(cad_menu, self.tr("Preview"), controller.preview_backend,
            mode=self._MODE_CAD, shortcut="F5",
            tip=self.tr("Run the PreProcessor and preview geometry / boundary conditions"))

        # ── Mesh Generator ─────────────────────────────────────────────────
        mesh_menu = menubar.addMenu(self.tr("Mesh"))
        add(mesh_menu, self.tr("Load Mesh Config..."), controller.load_mesh_config,
            mode=self._MODE_MESH)
        add(mesh_menu, self.tr("Save Mesh Config..."), controller.save_mesh_config,
            mode=self._MODE_MESH)
        mesh_menu.addSeparator()
        add(mesh_menu, self.tr("Add All Sessions"), controller.add_all_sessions_to_mesh,
            mode=self._MODE_MESH,
            tip=self.tr("Add all exported PreProcessor sessions to this mesh config"))
        mesh_menu.addSeparator()
        add(mesh_menu, self.tr("BC Preview"), controller.preview_mesh_generator,
            mode=self._MODE_MESH)
        add(mesh_menu, self.tr("Generate Mesh"), controller.run_mesh_generator,
            mode=self._MODE_MESH)
        add(mesh_menu, self.tr("Cancel"), controller.cancel_mesh_generator,
            mode=self._MODE_MESH)
        add(mesh_menu, self.tr("Export Mesh..."), controller.export_mesh_files,
            mode=self._MODE_MESH,
            tip=self.tr("Export the generated mesh (VTK / STAR-CD)"))

        # ── Solver ──────────────────────────────────────────────────────────
        solver_menu = menubar.addMenu(self.tr("Solver"))
        add(solver_menu, self.tr("Load Solver Config..."), controller.load_solver_config,
            mode=self._MODE_SOLVER)
        add(solver_menu, self.tr("Save Solver Config..."), controller.save_solver_config,
            mode=self._MODE_SOLVER)
        solver_menu.addSeparator()
        add(solver_menu, self.tr("Detect BC from Mesh"), controller.detect_bc_from_mesh,
            mode=self._MODE_SOLVER)
        dll_menu = solver_menu.addMenu(self.tr("Build DLL"))
        add(dll_menu, self.tr("Initial Condition..."),
            lambda: controller.open_dll_builder("init_cond"),
            mode=self._MODE_SOLVER)
        add(dll_menu, self.tr("Motion..."),
            lambda: controller.open_dll_builder("motion"),
            mode=self._MODE_SOLVER)
        add(dll_menu, self.tr("Boundary Condition..."), controller.open_bc_dll_builder,
            mode=self._MODE_SOLVER)
        solver_menu.addSeparator()
        add(solver_menu, self.tr("Run Solver"), controller.run_solver_pipeline,
            mode=self._MODE_SOLVER)
        add(solver_menu, self.tr("Cancel"), controller.cancel_solver,
            mode=self._MODE_SOLVER)
        solver_menu.addSeparator()
        add(solver_menu, self.tr("Export Portable Case..."),
            controller.export_portable_case, mode=self._MODE_SOLVER,
            tip=self.tr("Copy this case's INPUTS (grid / dll / work) into a "
                        "self-contained folder that reruns on another machine"))

        # ── Results ──────────────────────────────────────────────────────────
        results_menu = menubar.addMenu(self.tr("Results"))
        add(results_menu, self.tr("Load Result..."), controller.open_result_dialog,
            mode=self._MODE_RESULTS)
        add(results_menu, self.tr("Define Surface..."),
            controller.open_surface_definition, mode=self._MODE_RESULTS,
            tip=self.tr("Choose which curve is 'the surface' (mesh boundary, φ "
                        "iso-line, Fit Δ interface, analytic φ or CAD) and where "
                        "arc length starts"))
        add(results_menu, self.tr("Save PNG..."), controller.export_result_screenshot,
            mode=self._MODE_RESULTS)

        # ── IBM (Immersed Boundary, φ) — sits to the right of Results ────────
        ib_menu = menubar.addMenu(self.tr("IBM"))
        add(ib_menu, self.tr("Import STL..."), controller.browse_stl3d, mode=self._MODE_IB)
        add(ib_menu, self.tr("Fit Domain to STL"), controller.fit_stl3d_domain,
            mode=self._MODE_IB)
        ib_menu.addSeparator()
        add(ib_menu, self.tr("Generate φ Grid"), controller.run_stl3d, mode=self._MODE_IB)
        add(ib_menu, self.tr("Cancel"), controller.cancel_stl3d, mode=self._MODE_IB)
        ib_menu.addSeparator()
        add(ib_menu, self.tr("Send Grid to Solver"), controller.send_stl3d_to_solver,
            mode=self._MODE_IB)

        # ── Pipeline (cross-stage; the orchestrator drives the page itself) ──
        pipeline_menu = menubar.addMenu(self.tr("Pipeline"))
        add(pipeline_menu, self.tr("Run Full Pipeline"), controller.run_full_pipeline,
            shortcut="Ctrl+R",
            tip=self.tr("CAD resample → mesh → solver → results contour"))
        add(pipeline_menu, self.tr("Batch Queue..."), controller.open_batch_dialog,
            tip=self.tr("Queue several pipeline scripts and run them unattended"))
        pipeline_menu.addSeparator()
        add(pipeline_menu, self.tr("Load Pipeline Script..."), controller.load_pipeline_file)
        add(pipeline_menu, self.tr("Save Pipeline Script..."), controller.save_pipeline_file)

        # ── Help ───────────────────────────────────────────────────────────
        from PyQt6.QtWidgets import QMessageBox
        help_menu = menubar.addMenu(self.tr("Help"))
        self._build_language_menu(help_menu)
        help_menu.addSeparator()
        add(help_menu, self.tr("About HybMesh2D"), lambda: QMessageBox.about(
            self, "About HybMesh2D",
            "<b>HybMesh2D</b><br>"
            "2D hybrid mesh generator (boundary-layer quads + far-field "
            "triangles) for CFD, with a PyQt6 pre-processor.<br><br>"
            "Menus follow the workflow: "
            "CAD → Mesh → Solver → Results."))
        add(help_menu, self.tr("Keyboard Shortcuts"), lambda: QMessageBox.information(
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

    # ── Language ──────────────────────────────────────────────────────────
    def _build_language_menu(self, parent_menu):
        """A checkable language submenu.

        The choice applies at the NEXT launch. Re-translating a live window means
        walking every widget and re-setting every string, which the panels are not
        built for; promising a live switch and half delivering it would be worse than
        saying plainly that a restart is needed.
        """
        from PyQt6.QtGui import QActionGroup

        from app.services import i18n

        menu = parent_menu.addMenu(self.tr("Language"))
        group = QActionGroup(self)
        group.setExclusive(True)
        current = i18n.current_language()
        #: Endonyms — a language is listed the way its own speakers write it, which is
        #: the point of a language menu: it must be readable to someone who cannot
        #: read the current UI language.
        names = {"en": "English", "zh_TW": "繁體中文"}
        for code in i18n.available_languages():
            act = menu.addAction(names.get(code, code))
            act.setCheckable(True)
            act.setChecked(code == current)
            group.addAction(act)
            act.triggered.connect(
                lambda _checked=False, c=code: self._choose_language(c))
        return menu

    def _choose_language(self, code: str):
        from app.services import i18n
        if code == i18n.current_language():
            return
        i18n.save_language(code)
        self.log_panel.log(
            f"[UI] language set to {code} — restart to apply "
            "(open panels keep their current strings until then).")
        from app.utils import report_info
        report_info(self, self.tr("Language"),
                    self.tr("The interface language will change the next time "
                            "HybMesh2D starts."))
