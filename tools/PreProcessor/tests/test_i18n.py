#!/usr/bin/env python3
"""Translation mechanism (finding N9).

``tr()`` appeared ZERO times in the GUI, so a Traditional-Chinese UI was not merely
untranslated but unreachable.

Two design points this test pins down:

* **Call sites are standard Qt** (``self.tr`` / ``QCoreApplication.translate``), so a
  later switch to compiled ``.qm`` catalogues would touch no call site. Only the
  backend is custom, because ``lrelease`` is not in the PyQt6 wheel.
* **A missing string must fall back to the English source, never to "".** Qt's
  documented "no translation" signal is a *null* QString, but a Python override
  returning ``""`` hands Qt an *empty* one, which it accepts as the translation — every
  untranslated label would render BLANK. That was hit for real during development and
  is the single most important assertion here.

Checks:
 1. available_languages() finds the catalogues and always offers the source language.
 2. JsonTranslator translates by context, falls back to the "" context, and returns
    the SOURCE (not "") for anything missing.
 3. A malformed / missing / non-object catalogue degrades to no translation instead of
    raising.
 4. install() puts a real translator in place and current_language() reports it.
 5. The live menu bar and status bar actually render Chinese.
 6. Reverting to English restores the source strings.
 7. The catalogue covers every wrapped string (the extraction report is clean), and
    its keys match the CONCATENATED runtime strings — a catalogue key that only
    matches the first chunk of an implicitly-joined literal can never hit at run time.
 8. Deferred strings (table entries translated at display time) are marked with
    QT_TRANSLATE_NOOP so extraction sees them and does not report real translations as
    stale.

Run:  python3 tools/PreProcessor/tests/test_i18n.py
"""
import json
import os
import subprocess
import sys
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_GUI = os.path.abspath(os.path.join(_HERE, "..", "gui"))
if _GUI not in sys.path:
    sys.path.insert(0, _GUI)

_FAILS = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg, flush=True)
    if not cond:
        _FAILS.append(msg)


def _watchdog():
    print("FAIL watchdog: blocked >120s", flush=True)
    os._exit(99)


_wd = threading.Timer(120, _watchdog)
_wd.daemon = True
_wd.start()

from PyQt6.QtCore import QCoreApplication  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or QApplication(sys.argv)

from app.services import i18n  # noqa: E402

# ── 1. discovery ──────────────────────────────────────────────────────────
langs = i18n.available_languages()
check(i18n.SOURCE_LANGUAGE in langs,
      f"1. the source language is always offered ({langs})")
check("zh_TW" in langs, f"1. the zh_TW catalogue is found ({langs})")

# ── 2. lookup semantics ───────────────────────────────────────────────────
t = i18n.JsonTranslator({"Ctx": {"Hello": "哈囉"}, "": {"Shared": "共用"}}, "test")
check(t.translate("Ctx", "Hello") == "哈囉", "2. translates by context")
check(t.translate("Other", "Shared") == "共用",
      "2. falls back to the \"\" context for a shared word")
check(t.translate("Ctx", "Missing") == "Missing",
      "2. a MISSING string returns the English source — returning \"\" would render "
      "the label blank, because Qt accepts an empty string as the translation")
check(t.count() == 2, f"2. count() reports the catalogue size ({t.count()})")
check(not t.isEmpty() and i18n.JsonTranslator({}).isEmpty(),
      "2. isEmpty reflects the catalogue")

# ── 3. bad catalogues degrade ─────────────────────────────────────────────
check(i18n.JsonTranslator.load("no_such_language") is None,
      "3. a missing catalogue yields None, not an exception")
check(i18n.JsonTranslator.load(i18n.SOURCE_LANGUAGE) is None,
      "3. the source language needs no catalogue")

tdir = i18n.translations_dir()
bad = os.path.join(tdir, "xx_BAD.json")
notobj = os.path.join(tdir, "xx_LIST.json")
try:
    with open(bad, "w", encoding="utf-8") as f:
        f.write("{ not json")
    with open(notobj, "w", encoding="utf-8") as f:
        f.write('["not", "an", "object"]')
    check(i18n.JsonTranslator.load("xx_BAD") is None,
          "3. malformed JSON yields None rather than raising")
    check(i18n.JsonTranslator.load("xx_LIST") is None,
          "3. a non-object catalogue is rejected")
finally:
    for p in (bad, notobj):
        if os.path.exists(p):
            os.remove(p)

# ── 4/5. install and render ───────────────────────────────────────────────
lang = i18n.install(app, "zh_TW")
check(lang == "zh_TW" and i18n.current_language() == "zh_TW",
      f"4. install() puts zh_TW in effect (got {lang})")
check(QCoreApplication.translate("MainWindow", "Never Translated Anywhere")
      == "Never Translated Anywhere",
      "4. an unknown string still renders as English through the real Qt path")

from app.controller import AppController  # noqa: E402

ctl = AppController()
mw = ctl.main_window
titles = [a.text() for a in mw.menuBar().actions() if a.text()]
check("檔案" in titles, f"5. the menu bar renders Chinese ({titles[:4]})")
check(mw.status_stage.text().startswith("階段"),
      f"5. the status bar renders Chinese ({mw.status_stage.text()!r})")
mw.claim_progress("mesh", determinate=True)
mw.set_progress("mesh", 40)
check("正在產生網格" in mw.status_activity.text(),
      f"5. a deferred (table) string is translated at display time "
      f"({mw.status_activity.text()!r})")
mw.release_progress("mesh")

file_menu = [a for a in mw.menuBar().actions() if a.text() == "檔案"][0].menu()
items = [a.text() for a in file_menu.actions() if a.text()]
check("新增工作階段" in items, f"5. menu items are translated ({items[:3]})")

lang_menu = None
help_menu = [a for a in mw.menuBar().actions() if a.text() == "說明"][0].menu()
for a in help_menu.actions():
    if a.menu() is not None:
        lang_menu = a.menu()
check(lang_menu is not None, "5. Help carries a Language submenu")
if lang_menu is not None:
    entries = {a.text(): a.isChecked() for a in lang_menu.actions()}
    check(entries.get("繁體中文") is True,
          f"5. the active language is checked ({entries})")
    check("English" in entries,
          "5. languages are listed as endonyms — a language menu must be readable "
          "to someone who cannot read the current UI language")

# ── 6. back to English ────────────────────────────────────────────────────
check(i18n.install(app, "en") == "en", "6. reverting to the source language")
ctl2 = AppController()
titles2 = [a.text() for a in ctl2.main_window.menuBar().actions() if a.text()]
check("File" in titles2, f"6. the menu bar is English again ({titles2[:4]})")

# ── 7/8. catalogue coverage + key correctness ─────────────────────────────
script = os.path.join(_REPO, "tools", "scripts", "i18n_extract.py")
if not os.path.exists(script):
    print("SKIP i18n_extract.py missing", flush=True)
else:
    r = subprocess.run([sys.executable, script, "zh_TW"],
                       capture_output=True, text=True, cwd=_REPO, timeout=90)
    out = r.stdout
    check("missing (" not in out,
          f"7. every wrapped string is translated\n{out.strip()}")
    check("no longer wrapped" not in out,
          f"8. no catalogue entry is reported stale — QT_TRANSLATE_NOOP marks the "
          f"deferred ones so real translations are not flagged for deletion\n"
          f"{out.strip()}")

cat = json.load(open(os.path.join(i18n.translations_dir(), "zh_TW.json"),
                     encoding="utf-8"))
joined = [k for ctx, entries in cat.items() if isinstance(entries, dict)
          for k in entries if k.endswith(" ")]
check(not joined,
      f"7. no catalogue key ends mid-sentence — such a key comes from capturing "
      f"only the first chunk of an implicitly-concatenated literal and can never "
      f"match at run time ({joined})")

_wd.cancel()
if _FAILS:
    print(f"\nRESULT: {len(_FAILS)} FAILED", flush=True)
    os._exit(1)
print("\nRESULT: ALL PASS", flush=True)
os._exit(0)
