"""The mesh config a FILE holds, for the case-type hosts. Qt-free.

Cut out of `services/case_type_fields.py` by #169, under that seam's own stated
rule: "ONE SEAM, AND EVERY CUT IS THE ~500-LINE STANDARD rather than a second
home for the knowledge" (`services/case_type.py`'s docstring). It is the
smallest module of the case-type seam, and it is a cut rather than a new idea —
`read_config` is RE-EXPORTED from `case_type_fields`, so no caller learns a new
name, exactly as `case_type.py` re-exports `FIGURE_KEYS` and `apply`. No count
of the seam's files is stated here: `ls services/case_type*` answers it, and a
number restated in eleven docstrings is the staleness this repo gates for.

WHY IT IS ITS OWN QUESTION. Everything left in `case_type_fields` is about what
a case type may have an OPINION about — which fields are ownable, what an
overlay holds, what deviates from it. This function answers something else
entirely: given a path the maintainer typed, what mesh configuration is in it.
That is a question about FILE KINDS, and its one rule comes from
`services/project_file_kind.py` rather than from the overlay vocabulary.
"""
from __future__ import annotations

from app.models.mesh_config import MeshConfig
from app.services import project_file_kind
from app.services.case_type_reference import CaseTypeError


def read_config(path: str) -> MeshConfig:
    """The mesh config a file holds — a `.dat`, a `.hws` workspace or a script.

    A PATH IS NOT A KIND, which this repo has a user-reported defect for: the
    classification goes through `services/project_file_kind`, the one owner, so
    this host cannot disagree with `main.py` about what a file is. A `.dat` is
    what is left when the file is not a JSON object at all.

    It exists in the seam rather than in a host because ALL THREE headless hosts
    need it — the authoring step captures an overlay from a working case, the
    correcting step reads one, and the inspecting step compares a case type
    against one — and two readers would be free to disagree about where a
    workspace keeps its mesh section.
    """
    config = MeshConfig()
    doc = project_file_kind.peek_json_object(path)
    if doc is None:
        config.load_from_file(path)
        return config
    if project_file_kind.looks_like_workspace(doc):
        section = (doc.get("project") or {}).get("mesh_config")
    elif project_file_kind.looks_like_pipeline(doc):
        section = doc.get("mesh")
    else:
        raise CaseTypeError(
            "'%s' is a JSON document but neither a workspace nor a pipeline "
            "script, so there is no mesh configuration in it to read" % path)
    if not isinstance(section, dict):
        raise CaseTypeError("'%s' carries no mesh configuration" % path)
    config.load_from_dict(section)
    return config
