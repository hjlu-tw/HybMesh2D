"""The 3D view's OpenGL imports, in one place, with a failure you can act on.

`pyqtgraph.opengl` imports PyOpenGL at module load, and `views/main_window.py`
imports the 3D view unconditionally — so a missing PyOpenGL does not disable the
3D tab, it stops `from app.controller import AppController` outright and the GUI
cannot start. That is the correct behaviour for a required dependency and is
deliberately NOT softened here: a fallback would model a first-class feature as
optional and leave the user with a quietly crippled app.

What was wrong was the diagnosis, not the failure. The raw error points at
`pyqtgraph/opengl/shaders.py` and says `No module named 'OpenGL'`, naming neither
the package to install nor the command — and it took a CI run failing 33 of 69
tests, every one with that same traceback, before anyone noticed the dependency
had never been declared.

Both import sites go through this module so the message cannot drift into two
versions of itself.
"""
from __future__ import annotations

try:
    import pyqtgraph.opengl as gl
    from OpenGL.GL import (GL_ALPHA_TEST, GL_BLEND, GL_CULL_FACE, GL_DEPTH_TEST,
                           GL_ONE_MINUS_SRC_ALPHA, GL_SRC_ALPHA)
except ImportError as exc:                      # pragma: no cover - env-dependent
    raise ImportError(
        f"The 3D view needs PyOpenGL and it is not importable ({exc}).\n"
        "  Install it:  pip install -r tools/PreProcessor/gui/requirements.txt\n"
        "  (or just:    pip install PyOpenGL)\n"
        "On Linux the system OpenGL runtime is needed as well:\n"
        "  sudo apt-get install libgl1 libglu1-mesa\n"
        "This is a required dependency, not an optional extra: main_window.py "
        "imports the 3D view, so the whole GUI stops here without it."
    ) from exc

__all__ = ["gl", "GL_ALPHA_TEST", "GL_BLEND", "GL_CULL_FACE", "GL_DEPTH_TEST",
           "GL_ONE_MINUS_SRC_ALPHA", "GL_SRC_ALPHA"]
