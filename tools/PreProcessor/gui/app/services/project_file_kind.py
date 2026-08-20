"""What kind of project file is this? (Qt-free.)

A HybMesh JSON file is one of three things — a ``.hws`` **workspace** (local
working state, multi-tab), a runnable **pipeline script**, or neither (a
PreProcessor CAD config, or not a project file at all) — and the callers that
need to know are spread across every layer: the headless CLI, ``main.py``'s
argument handling, the geometry loader, the Pipeline menu, the batch queue.

They classify by CONTENT, never by extension, because the extension is exactly
what a caller holding a path cannot trust: ``main.py`` handed every positional
argument to the geometry loader, so opening the GUI on a workspace ran
``np.loadtxt`` over JSON and reported ``could not convert string '{' to float64``
— a message naming neither the file nor the real problem. One classifier here,
so those callers cannot disagree about what a file is.
"""
from __future__ import annotations
import json

WORKSPACE = "workspace"
PIPELINE = "pipeline"


def looks_like_workspace(d) -> bool:
    """True for a ``.hws`` workspace dict rather than a pipeline script."""
    return bool(isinstance(d, dict) and "sessions" in d
                and "cads" not in d and "cad" not in d)


def looks_like_pipeline(d) -> bool:
    """True for a unified pipeline script dict.

    ``cad`` (singular) is the pre-v2 spelling and ``pipeline_version`` alone
    covers a script whose stages are all empty.
    """
    return bool(isinstance(d, dict)
                and ("cads" in d or "cad" in d or "pipeline_version" in d))


def peek_json_object(path: str) -> dict | None:
    """Parse ``path`` as a JSON object, or None when it plainly isn't one.

    The first non-whitespace byte is checked before the file is read, so
    classifying a 200 MB STL or a point cloud costs one byte rather than loading
    it into memory only to fail the parse.
    """
    try:
        with open(path, encoding="utf-8") as f:
            while True:
                ch = f.read(1)
                if ch == "":
                    return None                 # empty / whitespace only
                if not ch.isspace():
                    break
            if ch != "{":
                return None                     # geometry data, not JSON
            f.seek(0)
            d = json.load(f)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return d if isinstance(d, dict) else None


def classify_project_file(path: str) -> str:
    """``"workspace"``, ``"pipeline"`` or ``""`` for the file at ``path``.

    ``""`` covers everything that is neither — a ``.dat``/``.stl`` geometry, a
    PreProcessor CAD config (``input_file`` + ``segments``), a missing file,
    unreadable or truncated JSON. Never raises: a caller asking "what is this?"
    has no better answer than "not a project file".
    """
    d = peek_json_object(path)
    if d is None:
        return ""
    if looks_like_workspace(d):
        return WORKSPACE
    if looks_like_pipeline(d):
        return PIPELINE
    return ""
