# app/styles.py

DARK_STYLESHEET = """
    QMainWindow, QDialog {
        background: #0c0d16;
        color: #a0a8c0;
    }
    QLabel {
        color: #a0a8c0;
    }
"""

COMBO_STYLE = """
    QComboBox {
        background: #181b2a;
        color: #a0a8c0;
        border: 1px solid #333852;
        border-radius: 3px;
        padding: 3px 20px 3px 6px;
        min-width: 80px;
    }
    QComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        border-left-width: 1px;
        border-left-color: #333852;
        border-left-style: solid;
    }
    QComboBox::down-arrow {
        image: url("data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxMCIgaGVpZ2h0PSIxMCIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJub25lIiBzdHJva2U9IiNhMGE4YzAiIHN0cm9rZS13aWR0aD0iMyIgc3Ryb2tlLWxpbmVjYXA9InJvdW5kIiBzdHJva2UtbGluZWpvaW49InJvdW5kIj48cG9seWxpbmUgcG9pbnRzPSI2IDkgMTIgMTUgMTggOSI+PC9wb2x5bGluZT48L3N2Zz4=");
    }
"""

SPIN_STYLE = "background:#181b2a; color:#a0a8c0; border:1px solid #333852; padding: 2px; max-width: 110px;"

CHECKBOX_STYLE = "color: #a0b0d0; font-size: 11px;"

BUTTON_QSS_TEMPLATE = """
    QPushButton {{
        background-color: {color};
        color: #dde6ff;
        border: 1px solid #4a5070;
        border-radius: 4px;
        padding: 6px 10px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: #32364e;
    }}
    QPushButton:disabled {{
        background-color: #171926;
        color: #555;
    }}
"""
