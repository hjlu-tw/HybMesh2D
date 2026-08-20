from __future__ import annotations

import math
import re

from PyQt6.QtGui import QValidator
from PyQt6.QtWidgets import QDoubleSpinBox


class CleanDoubleSpinBox(QDoubleSpinBox):
    """
    A custom QDoubleSpinBox that formats values to omit trailing zeros.
    """
    def textFromValue(self, value: float) -> str:
        decimals = self.decimals()
        locale = self.locale()
        decimal_point = locale.decimalPoint()

        # Get standard formatted string from locale
        s = locale.toString(value, 'f', decimals)

        if decimal_point in s:
            parts = s.split(decimal_point)
            if len(parts) == 2:
                frac = parts[1].rstrip('0')
                if frac:
                    return parts[0] + decimal_point + frac
                else:
                    return parts[0] + decimal_point + '0'
        return s


class NarrowDoubleSpinBox(CleanDoubleSpinBox):
    """CleanDoubleSpinBox that won't reserve width for its full ±range.

    A wide range (e.g. ±1e9) with several decimals makes Qt report a large
    ``minimumSizeHint`` (room for the longest possible value), so two-per-row
    fields overflow a narrow sidebar even with ``setMaximumWidth``. Calling
    ``setWidthCap(px)`` clamps the hint: typical (small) domain values still show
    in full, and a rare long value simply scrolls within the field.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._width_cap: int | None = None

    def setWidthCap(self, px: int | None) -> None:
        self._width_cap = int(px) if px else None
        self.updateGeometry()

    def minimumSizeHint(self):
        h = super().minimumSizeHint()
        if self._width_cap:
            h.setWidth(min(h.width(), self._width_cap))
        return h

    def sizeHint(self):
        h = super().sizeHint()
        if self._width_cap:
            h.setWidth(min(h.width(), self._width_cap))
        return h


# A complete number, with optional exponent: "1", "-2.5", ".5", "1.2e-7", "3E+4".
_SCI_COMPLETE = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")
# A prefix of one, so the field accepts every keystroke on the way there:
# "", "-", "1.", "1e", "1e-" are all still-being-typed, not invalid.
_SCI_PARTIAL = re.compile(r"^[+-]?(?:\d*\.?\d*)(?:[eE][+-]?\d*)?$")


class SciDoubleSpinBox(NarrowDoubleSpinBox):
    """A spin box that accepts and displays scientific notation.

    ``QDoubleSpinBox`` is fixed-notation only: its validator rejects the ``e`` in
    ``1.2e-7``, and ``decimals`` both truncates the display and pins how small a
    value can be represented at all. For CFD that is not cosmetic — a y+~1 first
    boundary-layer cell on a chord-normalised geometry is routinely 1e-7..1e-8,
    and a field built as ``setRange(1e-6, 1.0)`` + ``setDecimals(6)`` silently
    clamps such an input to 1e-6, changing the mesh the engineer asked for
    without saying so. Millimetre-scale geometry hits the same wall on mesh
    sizes and coordinates.

    Behaviour:

    * **Input** accepts ``1.2e-7`` / ``3E+4`` / plain decimals, and tolerates the
      locale decimal comma as well as ``.`` so a de/fr locale can type either.
    * **Display** is ``%.<sig>g`` — no trailing-zero noise, and an exponent only
      when the magnitude needs one. Always emitted with ``.`` so the text matches
      what the ``.dat``/JSON config files carry (they are written C-locale
      ``%.6g`` and read back by ``std::stod`` / ``float()``).
    * **Stepping** is decade-relative and recomputed per press, so the arrows
      nudge 1e-6 by 1e-7 instead of by Qt's blunt 1.0. (``apply_smart_spin_steps``
      computes a *fixed* step once at startup and therefore skips this class.)
    * **Keyboard tracking is off.** Every prefix of ``1e-7`` — ``1``, ``1e`` — is
      itself a valid number, so per-keystroke ``valueChanged`` would briefly apply
      ``1`` as a mesh size and fire a preview/dirty cascade for a value the user
      never meant. The value is committed on Enter / focus-out instead.
    """

    #: Significant digits used for display.
    SIG_DIGITS = 6
    #: ``decimals()`` only has to be large enough not to round away a small
    #: value; the visible precision comes from ``SIG_DIGITS``.
    STORAGE_DECIMALS = 12
    #: Default width cap — with a wide range and 12 decimals, Qt's own hint would
    #: reserve room for "-1000000.000000000000" and overflow the sidebar.
    DEFAULT_WIDTH_CAP = 120

    def __init__(self, *args, sig_digits: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._sig = int(sig_digits or self.SIG_DIGITS)
        self.setDecimals(self.STORAGE_DECIMALS)
        self.setKeyboardTracking(False)
        self.setWidthCap(self.DEFAULT_WIDTH_CAP)

    # ── display ──────────────────────────────────────────────────────────
    def textFromValue(self, value: float) -> str:
        return f"{value:.{self._sig}g}"

    # ── input ────────────────────────────────────────────────────────────
    def _normalize(self, text: str) -> str:
        """Strip the suffix/prefix and accept the locale decimal separator."""
        s = text.strip()
        for affix in (self.prefix(), self.suffix()):
            if affix and s.startswith(affix):
                s = s[len(affix):]
            if affix and s.endswith(affix):
                s = s[:len(s) - len(affix)]
        point = self.locale().decimalPoint()
        if point and point != ".":
            s = s.replace(point, ".")
        return s.strip()

    def _is_special(self, text: str) -> bool:
        """True if ``text`` is this field's specialValueText (e.g. "auto").

        Qt normally handles specialValueText inside its own validate/interpret
        pair, which our overrides replace — without this the word could be
        displayed but never typed back in.
        """
        svt = self.specialValueText()
        return bool(svt) and text.strip() == svt

    def valueFromText(self, text: str) -> float:
        if self._is_special(text):
            return self.minimum()
        s = self._normalize(text)
        try:
            return float(s)
        except ValueError:
            # Reached only for a partial entry Qt asks us to interpret (e.g. the
            # user leaves the field on "1e"); keep the current value rather than
            # jumping to 0.
            return self.value()

    def validate(self, text: str, pos: int):
        if self._is_special(text):
            return (QValidator.State.Acceptable, text, pos)
        svt = self.specialValueText()
        if svt and svt.startswith(text.strip()) and text.strip():
            # Still typing "au" on the way to "auto".
            return (QValidator.State.Intermediate, text, pos)
        s = self._normalize(text)
        if s in ("", "+", "-", ".", "+.", "-."):
            return (QValidator.State.Intermediate, text, pos)
        if _SCI_COMPLETE.match(s):
            try:
                v = float(s)
            except (ValueError, OverflowError):
                return (QValidator.State.Invalid, text, pos)
            if self.minimum() <= v <= self.maximum():
                return (QValidator.State.Acceptable, text, pos)
            # Out of range is Intermediate, not Invalid: "12345" may be on its way
            # to "1.2345e-7". fixup() clamps whatever is left at focus-out.
            return (QValidator.State.Intermediate, text, pos)
        if _SCI_PARTIAL.match(s):
            return (QValidator.State.Intermediate, text, pos)
        return (QValidator.State.Invalid, text, pos)

    def fixup(self, text: str) -> str:
        """Turn a still-Intermediate entry into the nearest legal value."""
        if self._is_special(text):
            return text
        s = self._normalize(text)
        try:
            v = float(s)
        except ValueError:
            return self.textFromValue(self.value())
        return self.textFromValue(min(max(v, self.minimum()), self.maximum()))

    # ── stepping ─────────────────────────────────────────────────────────
    def stepBy(self, steps: int):
        v = self.value()
        mag = abs(v)
        if mag < 1e-300:
            # Stepping up from exactly zero: start one decade above the smallest
            # value the field can hold, so the first press does something visible.
            step = 10.0 ** -min(self.decimals(), self._sig)
        else:
            step = 10.0 ** (math.floor(math.log10(mag)) - 1)
        self.setValue(v + steps * step)
