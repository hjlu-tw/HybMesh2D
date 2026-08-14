import sys
import os
from PyQt6.QtWidgets import QApplication, QSpinBox, QDoubleSpinBox, QComboBox

# Disable scroll-wheel value changes on spin boxes and combo boxes so a stray
# scroll over the control can't silently change a value/selection (mis-touch).
# (Only affects scrolling the closed widget; an open dropdown still scrolls.)
QSpinBox.wheelEvent = lambda self, event: event.ignore()
QDoubleSpinBox.wheelEvent = lambda self, event: event.ignore()
QComboBox.wheelEvent = lambda self, event: event.ignore()

from app.controller import AppController


def _resolve_listed_path(raw: str, list_dir: str) -> str:
    """Resolve a path read from a list file: try as given (cwd-relative or
    absolute) first, then relative to the list file's own directory."""
    if os.path.isabs(raw) or os.path.exists(raw):
        return raw
    candidate = os.path.join(list_dir, raw)
    return candidate if os.path.exists(candidate) else raw


def _read_list_file(path: str) -> list[str]:
    """Read a manifest of geometry paths, one per line. Blank lines and lines
    starting with '#' are ignored."""
    list_dir = os.path.dirname(os.path.abspath(path))
    paths = []
    try:
        with open(path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                paths.append(_resolve_listed_path(line, list_dir))
    except OSError as e:
        print(f"Warning: Could not read list file '{path}': {e}")
    return paths


def split_project_files(paths: list[str]) -> tuple[str, list[str]]:
    """Split existing paths into (project_file, geometry_files).

    A *project* file is a workspace (``.hws``) or a pipeline script — recognised
    by content, so the extension does not have to be right. Only one can be open
    at a time (loading either replaces every tab), so a second one is refused
    rather than quietly cancelling the first.

    Splitting them out is what makes `main.py case.hws` work at all: every
    positional argument used to go to the geometry loader, which read the
    workspace as columns of numbers and reported
    "could not convert string '{' to float64".
    """
    from app.models.pipeline_config import PipelineConfig

    project = ""
    geometry = []
    for fp in paths:
        kind = PipelineConfig.classify_file(fp)
        if not kind:
            geometry.append(fp)
        elif not project:
            project = fp
        else:
            print(f"Warning: ignoring '{fp}' — only one workspace/pipeline "
                  f"script can be open at a time (using '{project}').")
    return project, geometry


def collect_geometry_files(args: list[str]) -> list[str]:
    """Expand command-line args into file paths.

    An argument is treated as a *list file* (a manifest of paths, one per line)
    when it starts with '@' or ends with '.txt' / '.list'; otherwise it is a
    geometry / project file path. This lets several files be opened at once via,
    e.g., `main.py @geoms.txt` instead of listing every path on the command line.
    """
    file_paths = []
    for arg in args:
        is_list = arg.startswith("@") or arg.lower().endswith((".txt", ".list"))
        if is_list:
            list_path = arg[1:] if arg.startswith("@") else arg
            if not os.path.exists(list_path):
                print(f"Warning: List file not found: {list_path}")
                continue
            for fp in _read_list_file(list_path):
                if os.path.exists(fp):
                    file_paths.append(fp)
                else:
                    print(f"Warning: File not found (from {list_path}): {fp}")
        elif os.path.exists(arg):
            file_paths.append(arg)
        else:
            print(f"Warning: File not found: {arg}")
    return file_paths


def main():
    # Ensure default directories exist
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    for sub in [
        "config/preprocessor",
        "config/mesh",
        "results/resampled",
        "results/meshes"
    ]:
        os.makedirs(os.path.join(root_dir, sub), exist_ok=True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Durable diagnostics: rotating log file + uncaught-exception hook, so a
    # crash leaves a traceback in results/logs/gui.log instead of vanishing.
    from app.services.logging_setup import configure_logging
    configure_logging()

    # UI language: installed BEFORE any widget is created, because strings are
    # translated as widgets are constructed. `--lang xx` overrides the saved choice
    # for one run, which is what makes a translation reviewable without changing
    # the user's setting.
    from app.services import i18n
    lang_override = ""
    for i, a in enumerate(sys.argv[1:]):
        if a == "--lang" and i + 2 <= len(sys.argv[1:]):
            lang_override = sys.argv[i + 2]
    i18n.install(app, lang_override)

    # Slightly smaller global font for a denser, industrial-style UI.
    _f = app.font()
    _ps = _f.pointSizeF()
    if _ps > 0:
        _f.setPointSizeF(max(8.0, _ps - 1.5))
    else:
        _f.setPixelSize(max(10, _f.pixelSize() - 2))
    app.setFont(_f)
    
    import pyqtgraph as pg
    pg.setConfigOption('background', '#0c0d16')
    pg.setConfigOption('foreground', '#a0a8c0')
    
    controller = AppController()

    # Split off pipeline flags: `--pipeline <file>` loads a unified pipeline
    # script into the GUI on startup; `--run` then auto-clicks Run All so the
    # whole CAD->mesh->solver->results chain executes and ends on the contour.
    argv = sys.argv[1:]
    pipeline_path = None
    auto_run = False
    rest_args = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--pipeline" and i + 1 < len(argv):
            pipeline_path = argv[i + 1]
            i += 2
            continue
        if a == "--run":
            auto_run = True
            i += 1
            continue
        if a == "--lang" and i + 1 < len(argv):
            i += 2                      # already consumed above
            continue
        rest_args.append(a)
        i += 1

    from PyQt6.QtCore import QTimer

    # Files given as command line arguments. Several may be passed directly, or
    # via a list file (@list.txt / *.txt / *.list) holding one path per line.
    # A workspace / pipeline script is loaded as such; every geometry file opens
    # in its own tab.
    project_path, geometry_paths = split_project_files(
        collect_geometry_files(rest_args))
    if pipeline_path:
        if not os.path.exists(pipeline_path):
            print(f"Warning: --pipeline file not found: {pipeline_path}")
            pipeline_path = None
        elif project_path:
            print(f"Warning: ignoring '{project_path}' — --pipeline "
                  f"'{pipeline_path}' takes precedence.")
    if pipeline_path:
        project_path = pipeline_path

    if project_path or geometry_paths:
        # One deferred load, in one order, so the UI is fully rendered first.
        # The project MUST go first: loading a workspace or a script resets all
        # state and closes every tab, so a geometry loaded before it was silently
        # discarded (the old code loaded geometry at 100 ms and the pipeline at
        # 200 ms).
        def startup_load():
            if project_path:
                controller.open_pipeline_path(os.path.abspath(project_path))
            for fp in geometry_paths:
                controller.load_geometry_from_path(fp)
            if auto_run:
                QTimer.singleShot(500, controller.run_full_pipeline)

        QTimer.singleShot(100, startup_load)
    elif auto_run:
        print("Warning: --run ignored — no workspace, pipeline script or "
              "geometry file was given to run.")

    controller.show_main_window()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
