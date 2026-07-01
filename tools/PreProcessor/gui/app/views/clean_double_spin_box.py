from __future__ import annotations

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
