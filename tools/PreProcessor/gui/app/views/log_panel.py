from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit

class LogPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self._layout.addWidget(self.text_edit)

    def log(self, message):
        self.text_edit.append(message)
