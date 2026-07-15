from __future__ import annotations
import os
from PyQt6.QtGui import QKeySequence, QShortcut


class MainWindowMenuMixin:
    """
    Menu bar, global shortcuts and recent-files handling for :class:`MainWindow`.

    Mixed into ``MainWindow`` (after ``QMainWindow``); every method references
    ``self.*`` attributes/widgets that ``MainWindow.__init__`` creates, resolved
    at call time via the MRO. Extracted verbatim — no behaviour change.
    """

    # ── Shortcuts ─────────────────────────────────────────────────────────

    def setup_shortcuts(self, controller):
        # 1. Initialize QShortcuts (Global hotkeys)
        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(controller.undo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self).activated.connect(controller.redo)
        QShortcut(QKeySequence("Ctrl+Y"), self).activated.connect(controller.redo)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(controller.load_geometry)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(controller.save_output)
        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(controller.new_blank_tab)
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(controller.new_blank_tab)
        QShortcut(QKeySequence("Ctrl+W"), self).activated.connect(lambda: controller.close_tab(controller.active_idx))
        QShortcut(QKeySequence("F5"), self).activated.connect(controller.preview_backend)

        # 2. Setup standard Menu Bar
        menubar = self.menuBar()
        menubar.setStyleSheet("""
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
        """)

        file_menu = menubar.addMenu("File")

        load_action = file_menu.addAction("Load Geometry...")
        load_action.setShortcut("Ctrl+O")
        load_action.triggered.connect(controller.load_geometry)

        load_json_action = file_menu.addAction("Load JSON Config...")
        load_json_action.triggered.connect(controller.load_json_config)

        file_menu.addSeparator()

        self.recent_menu = file_menu.addMenu("Open Recent")
        controller.init_recent_files()

        file_menu.addSeparator()

        new_tab_action = file_menu.addAction("New Tab")
        new_tab_action.setShortcut("Ctrl+T")
        new_tab_action.triggered.connect(controller.new_blank_tab)

        close_tab_action = file_menu.addAction("Close Tab")
        close_tab_action.setShortcut("Ctrl+W")
        close_tab_action.triggered.connect(lambda: controller.close_tab(controller.active_idx))

        file_menu.addSeparator()

        save_action = file_menu.addAction("Export Mesh (.dat)...")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(controller.save_output)

        save_json_action = file_menu.addAction("Save Configuration (.json)...")
        save_json_action.triggered.connect(controller.generate_json)

        file_menu.addSeparator()

        save_ws_action = file_menu.addAction("Save Workspace...")
        save_ws_action.triggered.connect(controller.save_workspace)

        load_ws_action = file_menu.addAction("Load Workspace...")
        load_ws_action.triggered.connect(controller.load_workspace)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

        # ── Pipeline menu (full CAD -> mesh -> solver -> results) ──────────
        pipeline_menu = menubar.addMenu("Pipeline")

        run_all_action = pipeline_menu.addAction("Run Full Pipeline")
        run_all_action.setShortcut("Ctrl+R")
        run_all_action.triggered.connect(controller.run_full_pipeline)

        pipeline_menu.addSeparator()

        load_pipe_action = pipeline_menu.addAction("Load Pipeline Script...")
        load_pipe_action.triggered.connect(controller.load_pipeline_file)

        save_pipe_action = pipeline_menu.addAction("Save Pipeline Script...")
        save_pipe_action.triggered.connect(controller.save_pipeline_file)

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
