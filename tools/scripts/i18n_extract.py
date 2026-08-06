#!/usr/bin/env python3
"""Report translation coverage, and optionally run Qt's string extractor.

Two jobs:

* **Coverage** (default): scan the GUI for wrapped strings — ``self.tr("...")`` and
  ``QCoreApplication.translate("Ctx", "...")`` — and diff them against a catalogue,
  listing what is missing and what has gone stale. Needs no Qt tooling, so it works
  on any developer machine and in CI.

* ``--ts``: also invoke ``pylupdate6`` to produce a standard ``.ts`` file for a
  translator using Qt Linguist. That tool IS in the PyQt6 wheel; ``lrelease`` (which
  compiles ``.ts`` -> ``.qm``) is not, which is why the runtime reads JSON instead —
  see app/services/i18n.py.

Usage:
    python3 tools/scripts/i18n_extract.py                 # coverage for every catalogue
    python3 tools/scripts/i18n_extract.py zh_TW           # one language
    python3 tools/scripts/i18n_extract.py zh_TW --ts      # also write a .ts
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", ".."))
_GUI = os.path.join(_REPO, "tools", "PreProcessor", "gui")
_TRANSLATIONS = os.path.join(_GUI, "translations")

# A run of ADJACENT string literals: Python concatenates them, so the runtime source
# string is the whole run. Capturing only the first chunk silently produced catalogue
# keys that could never match at run time.
_RUN = r'((?:"(?:[^"\\]|\\.)*"\s*)+)'

# self.tr("...")  /  QCoreApplication.translate("Ctx", "...")  /  _t("...")
_TR = re.compile(r'self\.tr\(\s*' + _RUN)
_TRANSLATE = re.compile(
    r'(?:QCoreApplication\.)?translate\(\s*"([^"]+)"\s*,\s*' + _RUN)
_LOCAL_T = re.compile(r'(?<![\w.])_t\(\s*' + _RUN)


def _join_literals(run: str) -> str:
    """Concatenate a run of adjacent quoted literals into the real source string."""
    return "".join(re.findall(r'"((?:[^"\\]|\\.)*)"', run))
# Qt's standard marker for a string translated LATER (a table entry translated at
# display time). Without recognising it, such strings look untranslated at the call
# site and their catalogue entries look stale.
_NOOP = re.compile(
    r'QT_TRANSLATE_NOOP\(\s*"([^"]+)"\s*,\s*' + _RUN)

#: app/services/i18n.py documents the API in its docstring, so its example strings
#: are not real UI text.
_SKIP_FILES = {os.path.join("app", "services", "i18n.py")}


def _translatable(text: str) -> bool:
    """False for strings with no letters ('...', '%s', '—'): nothing to translate."""
    return any(ch.isalpha() for ch in text)


def wrapped_strings() -> dict:
    """``{context: {source, ...}}`` for every wrapped string under app/.

    ``self.tr`` and a module-level ``_t`` helper carry no explicit context, so they are
    filed under the module's own name — matching how Qt derives a context from the
    class. The catalogue's "" fallback context is what makes that forgiving.
    """
    found: dict = {}
    for root, _dirs, files in os.walk(os.path.join(_GUI, "app")):
        for fn in sorted(files):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            if os.path.relpath(path, _GUI) in _SKIP_FILES:
                continue
            src = open(path, encoding="utf-8").read()
            for pattern in (_TRANSLATE, _NOOP):
                for ctx, run in pattern.findall(src):
                    text = _join_literals(run)
                    if _translatable(text):
                        found.setdefault(ctx, set()).add(text)
            implicit = [t for t in (_join_literals(r) for r in
                                    _TR.findall(src) + _LOCAL_T.findall(src))
                        if _translatable(t)]
            if implicit:
                found.setdefault(os.path.splitext(fn)[0], set()).update(implicit)
    return found


def catalogue(lang: str) -> dict:
    path = os.path.join(_TRANSLATIONS, f"{lang}.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items()
            if isinstance(v, dict) and not k.startswith("_")}


def report(lang: str) -> int:
    """Print coverage for one language. Returns the number of missing strings."""
    try:
        cat = catalogue(lang)
    except FileNotFoundError:
        print(f"[{lang}] no catalogue at translations/{lang}.json")
        return -1
    # A string counts as translated if it appears under ANY context, because the
    # runtime falls back to the "" context and the implicit contexts derived here are
    # a best-effort guess at Qt's.
    translated = {s for ctx in cat.values() for s in ctx}
    wrapped = wrapped_strings()
    all_wrapped = {s for texts in wrapped.values() for s in texts}

    missing = sorted(all_wrapped - translated)
    stale = sorted(translated - all_wrapped)

    print(f"[{lang}] {len(all_wrapped) - len(missing)}/{len(all_wrapped)} wrapped "
          f"strings translated")
    if missing:
        print(f"  missing ({len(missing)}):")
        for s in missing[:40]:
            print(f"    {s}")
        if len(missing) > 40:
            print(f"    ... and {len(missing) - 40} more")
    if stale:
        print(f"  no longer wrapped in the code ({len(stale)}) — safe to delete:")
        for s in stale[:20]:
            print(f"    {s}")
    return len(missing)


def write_ts(lang: str) -> int:
    """Run pylupdate6 to produce translations/<lang>.ts for Qt Linguist."""
    sources = []
    for root, _dirs, files in os.walk(os.path.join(_GUI, "app")):
        sources += [os.path.join(root, f) for f in sorted(files) if f.endswith(".py")]
    out = os.path.join(_TRANSLATIONS, f"{lang}.ts")
    cmd = ["pylupdate6", *sources, "-ts", out]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        print("pylupdate6 not found — install PyQt6 tooling to produce a .ts")
        return 1
    if r.returncode != 0:
        print(f"pylupdate6 failed:\n{r.stderr.strip()}")
        return r.returncode
    print(f"wrote {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Translation coverage report.")
    ap.add_argument("language", nargs="?", help="language code (default: all)")
    ap.add_argument("--ts", action="store_true",
                    help="also write a .ts via pylupdate6 for Qt Linguist")
    args = ap.parse_args()

    if args.language:
        langs = [args.language]
    else:
        langs = sorted(os.path.splitext(f)[0]
                       for f in os.listdir(_TRANSLATIONS) if f.endswith(".json"))
    if not langs:
        print("no catalogues found")
        return 1

    rc = 0
    for lang in langs:
        if report(lang) < 0:
            rc = 1
        if args.ts:
            rc = write_ts(lang) or rc
    return rc


if __name__ == "__main__":
    sys.exit(main())
