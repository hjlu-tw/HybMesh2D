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
