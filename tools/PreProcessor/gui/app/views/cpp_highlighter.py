"""Minimal C++ syntax highlighter for the IBM DLL code editor (dark theme)."""
from __future__ import annotations
import re

from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont


def _fmt(color: str, bold: bool = False, italic: bool = False) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor(color))
    if bold:
        f.setFontWeight(QFont.Weight.Bold)
    if italic:
        f.setFontItalic(True)
    return f


_KEYWORDS = (
    "alignas alignof and asm auto bool break case catch char class const "
    "constexpr continue default delete do double else enum explicit extern "
    "false float for friend goto if inline int long mutable namespace new "
    "noexcept nullptr operator private protected public register return short "
    "signed sizeof static struct switch template this throw true try typedef "
    "typename union unsigned using virtual void volatile while"
).split()


class CppHighlighter(QSyntaxHighlighter):
    """Highlights keywords, preprocessor, strings, numbers, and comments."""

    def __init__(self, document):
        super().__init__(document)
        kw = _fmt("#7cb8f0", bold=True)
        self._rules: list[tuple[re.Pattern, QTextCharFormat]] = []
        self._rules += [(re.compile(rf"\b{k}\b"), kw) for k in _KEYWORDS]
        self._rules.append((re.compile(r"^\s*#.*$"), _fmt("#c586c0")))            # preprocessor
        self._rules.append((re.compile(r"\b[A-Za-z_]\w*(?=\s*\()"), _fmt("#dcdcaa")))  # calls
        self._rules.append((re.compile(r"\b\d+\.?\d*([eE][-+]?\d+)?\b"), _fmt("#b5cea8")))  # numbers
        self._rules.append((re.compile(r'"[^"\\]*(\\.[^"\\]*)*"'), _fmt("#ce9178")))   # strings
        self._rules.append((re.compile(r"//[^\n]*"), _fmt("#6a9955", italic=True)))    # line comment
        self._comment = _fmt("#6a9955", italic=True)
        self._c_open = re.compile(r"/\*")
        self._c_close = re.compile(r"\*/")

    def highlightBlock(self, text: str):
        for pattern, fmt in self._rules:
            for m in pattern.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)

        # Multi-line /* ... */ comments via block state.
        self.setCurrentBlockState(0)
        start = 0
        if self.previousBlockState() != 1:
            mo = self._c_open.search(text)
            start = mo.start() if mo else -1
        while start >= 0:
            mc = self._c_close.search(text, start)
            if mc:
                length = mc.end() - start
            else:
                length = len(text) - start
                self.setCurrentBlockState(1)
            self.setFormat(start, length, self._comment)
            nxt = self._c_open.search(text, start + length)
            start = nxt.start() if nxt else -1
