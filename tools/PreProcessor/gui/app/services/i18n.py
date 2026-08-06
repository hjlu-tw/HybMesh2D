"""Translation support (finding N9).

Every user-visible string was hardcoded English — ``tr()`` appeared zero times — so a
Traditional-Chinese UI was not merely untranslated but unreachable.

**Call sites are standard Qt.** Widgets use ``self.tr("...")`` and non-QObject code
uses ``QCoreApplication.translate("Context", "...")``. That is deliberate: if this
project later gains Qt's ``lrelease`` it can switch to compiled ``.qm`` catalogues
without touching a single call site.

**The catalogue backend is not.** ``lrelease`` (the tool that compiles ``.ts`` ->
``.qm``) is not part of the PyQt6 wheel, so requiring it would make translations
un-buildable on a plain developer machine. Instead :class:`JsonTranslator` overrides
``QTranslator.translate`` and reads a plain JSON file:

    {"MainWindow": {"File": "檔案"}, "": {"Cancel": "取消"}}

which is diffable, reviewable in a pull request, and needs no build step. The ``""``
context is the fallback, tried when a string is not found under its own context —
otherwise the same word would have to be repeated for every widget class that uses it.

Extraction for translators still uses the standard tool, which IS available::

    pylupdate6 $(find app -name '*.py') -ts translations/zh_TW.ts

``tools/scripts/i18n_extract.py`` wraps that and reports untranslated strings.
"""
from __future__ import annotations

import json
import os

from PyQt6.QtCore import QCoreApplication, QLocale, QSettings, QTranslator

from app.services.logging_setup import get_logger

_log = get_logger(__name__)

#: Language code used when nothing is configured. English is the source language,
#: so it needs no catalogue.
SOURCE_LANGUAGE = "en"

#: QSettings key (same org/app as the recent-files list and the window layout).
_SETTINGS_KEY = "ui/language"

#: Fallback context: a string not found under its own context is looked up here.
FALLBACK_CONTEXT = ""


def translations_dir() -> str:
    """Directory holding ``<lang>.json`` catalogues."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # app/
    return os.path.join(os.path.dirname(here), "translations")


def available_languages() -> list:
    """Language codes with a catalogue, plus the source language, sorted.

    The source language is always offered even though it has no file — it is what
    the code itself is written in.
    """
    langs = {SOURCE_LANGUAGE}
    try:
        for name in os.listdir(translations_dir()):
            if name.endswith(".json"):
                langs.add(os.path.splitext(name)[0])
    except OSError:
        pass
    return sorted(langs)


class JsonTranslator(QTranslator):
    """A QTranslator backed by a JSON catalogue.

    A missing string returns the English ``sourceText``, NOT ``""``. Qt's documented
    "no translation" signal is a *null* QString, but a Python override returning ``""``
    hands Qt an *empty* one, which it accepts as the translation — every untranslated
    label would then render BLANK. Verified the hard way; returning the source keeps a
    partial catalogue perfectly usable, which matters because a translation lands
    string by string, not all at once.
    """

    def __init__(self, catalogue: dict | None = None, language: str = ""):
        super().__init__()
        self._catalogue = catalogue or {}
        self.language = language

    @classmethod
    def load(cls, language: str):
        """Load ``<language>.json``, or None when there is nothing to load."""
        if not language or language == SOURCE_LANGUAGE:
            return None
        path = os.path.join(translations_dir(), f"{language}.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            _log.warning("no translation catalogue for %r (%s)", language, path)
            return None
        except (OSError, ValueError) as e:
            _log.warning("could not read the %r catalogue: %s", language, e)
            return None
        if not isinstance(data, dict):
            _log.warning("the %r catalogue is not a JSON object; ignoring", language)
            return None
        return cls(data, language)

    # Qt calls this for every tr() / translate().
    def translate(self, context, sourceText, disambiguation=None, n=-1):  # noqa: N802
        by_context = self._catalogue.get(context)
        if isinstance(by_context, dict):
            hit = by_context.get(sourceText)
            if hit:
                return hit
        shared = self._catalogue.get(FALLBACK_CONTEXT)
        if isinstance(shared, dict):
            hit = shared.get(sourceText)
            if hit:
                return hit
        # The English source, never "" — see the class docstring.
        return sourceText

    def isEmpty(self) -> bool:  # noqa: N802
        return not self._catalogue

    def count(self) -> int:
        """Number of translated strings, for reporting coverage."""
        return sum(len(v) for v in self._catalogue.values() if isinstance(v, dict))


def saved_language() -> str:
    """The configured language: the saved setting, else the system locale if a
    catalogue exists for it, else the source language."""
    try:
        value = QSettings("HybMesh", "PreProcessor").value(_SETTINGS_KEY)
        if value:
            return str(value)
    except Exception:
        _log.debug("could not read the saved language", exc_info=True)

    langs = available_languages()
    system = QLocale.system().name()                 # e.g. "zh_TW"
    if system in langs:
        return system
    short = system.split("_")[0]                     # e.g. "zh"
    for lang in langs:
        if lang == short or lang.startswith(short + "_"):
            return lang
    return SOURCE_LANGUAGE


def save_language(language: str) -> None:
    """Persist the choice. Applies at the next launch.

    Re-translating a live window means walking every widget and re-setting every
    string, which the panels are not built for; promising a live switch and half
    delivering it would be worse than being explicit about the restart.
    """
    try:
        QSettings("HybMesh", "PreProcessor").setValue(_SETTINGS_KEY, language)
    except Exception:
        _log.warning("could not save the language choice", exc_info=True)


_installed: JsonTranslator | None = None


def install(app: QCoreApplication | None = None, language: str = "") -> str:
    """Install the catalogue for ``language`` (default: the configured one).

    Returns the language actually in effect. Call once, early in ``main()``, BEFORE
    the windows are built: strings are translated as widgets are constructed.
    """
    global _installed
    app = app or QCoreApplication.instance()
    if app is None:
        return SOURCE_LANGUAGE
    lang = language or saved_language()

    if _installed is not None:
        app.removeTranslator(_installed)
        _installed = None
    if lang == SOURCE_LANGUAGE:
        return SOURCE_LANGUAGE

    translator = JsonTranslator.load(lang)
    if translator is None:
        return SOURCE_LANGUAGE
    app.installTranslator(translator)
    _installed = translator
    _log.info("UI language %s (%d strings)", lang, translator.count())
    return lang


def current_language() -> str:
    """The language in effect right now."""
    return _installed.language if _installed is not None else SOURCE_LANGUAGE
