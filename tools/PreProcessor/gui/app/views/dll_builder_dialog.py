from __future__ import annotations
import os
import tempfile

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QComboBox, QLabel,
    QPlainTextEdit, QListWidget, QListWidgetItem, QPushButton, QLineEdit,
    QWidget, QFileDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QTextCursor, QColor

from app.services.dll_templates import (
    templates_for, default_basename, INIT_COND,
)
from app.workers.dll_compile_run import DllCompileWorker, compiler_available
from app.views.cpp_highlighter import CppHighlighter
from app.views.clean_double_spin_box import CleanDoubleSpinBox
from app.utils import make_button, COMBO_STYLE, SPIN_STYLE, LINEEDIT_STYLE, repo_root


_FN_LABEL = {
    INIT_COND: "Initial Condition  —  initQ_at_p()",
    "motion": "Solid Motion  —  get_6dof_vel()",
}
_DIAG_COLOR = {"error": "#ef4444", "warning": "#eab308", "note": "#8892b0"}


class DllBuilderDialog(QDialog):
    """Generate, edit, and compile a unicones IBM DLL source.

    Tier 1 (parameter templates) generates C++ into the editor; Tier 2 lets the
    user edit it freely. ``Compile`` test-builds with the solver's exact flags and
    shows inline diagnostics. ``Save & Use`` writes the ``.cc`` and exposes its
    path via ``result_path`` for the caller to drop into the solver config.
    """

    def __init__(self, parent, dll_type: str, initial_path: str = ""):
        super().__init__(parent)
        self._dll_type = dll_type
        self.result_path: str = ""
        self._param_spins: dict = {}
        self._worker: DllCompileWorker | None = None
        self._tmp = tempfile.mkdtemp(prefix="hybmesh_dll_")
        self._compiled_ok = False

        self.setWindowTitle("IBM DLL Builder")
        self.setMinimumSize(820, 680)
        self.setStyleSheet("background:#121422; color:#a0a8c0;")

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(6)

        title = QLabel(_FN_LABEL.get(dll_type, dll_type))
        title.setStyleSheet("color:#dde2ff; font-weight:bold; font-size:13px;")
        root.addWidget(title)

        # ── Tier 1: template + parameters ────────────────────────────────
        tpl_row = QHBoxLayout()
        tpl_row.setSpacing(6)
        tlbl = QLabel("Template:")
        tlbl.setStyleSheet("color:#7a82a0;")
        self.template_combo = QComboBox()
        self.template_combo.setStyleSheet(COMBO_STYLE)
        self._specs = templates_for(dll_type)
        for s in self._specs:
            self.template_combo.addItem(s.label)
        self.generate_btn = make_button("Generate Code", "#1d2a3a")
        tpl_row.addWidget(tlbl)
        tpl_row.addWidget(self.template_combo, 1)
        tpl_row.addWidget(self.generate_btn)
        root.addLayout(tpl_row)

        self.desc_lbl = QLabel("")
        self.desc_lbl.setWordWrap(True)
        self.desc_lbl.setStyleSheet("color:#8892b0; font-size:11px;")
        root.addWidget(self.desc_lbl)

        self._params_host = QWidget()
        self._params_layout = QVBoxLayout(self._params_host)
        self._params_layout.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._params_host)

        # ── Tier 2: editor ───────────────────────────────────────────────
        ed_lbl = QLabel("Source (editable):")
        ed_lbl.setStyleSheet("color:#7a82a0;")
        root.addWidget(ed_lbl)
        self.editor = QPlainTextEdit()
        self.editor.setFont(QFont("Menlo", 11))
        self.editor.setStyleSheet(
            "QPlainTextEdit{background:#0c0d16; color:#d6dcf0; border:1px solid #2d3356;"
            "border-radius:4px;} ")
        self.editor.setTabStopDistance(28)
        self._highlighter = CppHighlighter(self.editor.document())
        root.addWidget(self.editor, 1)

        # ── Diagnostics ──────────────────────────────────────────────────
        self.diag_list = QListWidget()
        self.diag_list.setMaximumHeight(120)
        self.diag_list.setStyleSheet(
            "QListWidget{background:#0c0d16; border:1px solid #2d3356; border-radius:4px;"
            "font-family:monospace; font-size:11px;}")
        self.diag_list.itemDoubleClicked.connect(self._goto_diag)
        root.addWidget(self.diag_list)

        # ── Output + actions ─────────────────────────────────────────────
        out_row = QHBoxLayout()
        out_row.setSpacing(6)
        self.status_lbl = QLabel("Not compiled.")
        self.status_lbl.setStyleSheet("color:#8892b0; font-size:11px;")
        self.compile_btn = make_button("Compile", "#1d2a3a")
        self.save_btn = make_button("Save && Use", "#1e4620")
        self.close_btn = make_button("Close", "#26293c")
        out_row.addWidget(self.status_lbl, 1)
        out_row.addWidget(self.compile_btn)
        out_row.addWidget(self.save_btn)
        out_row.addWidget(self.close_btn)
        root.addLayout(out_row)

        # ── Wiring ────────────────────────────────────────────────────────
        self.template_combo.currentIndexChanged.connect(self._on_template_changed)
        self.generate_btn.clicked.connect(self._generate)
        self.compile_btn.clicked.connect(self._compile)
        self.save_btn.clicked.connect(self._save_and_use)
        self.close_btn.clicked.connect(self.reject)

        self._compiler = compiler_available()
        if not self._compiler:
            self.compile_btn.setEnabled(False)
            self.status_lbl.setText("No C++ compiler (g++/clang++) found on PATH — "
                                    "Compile disabled. The solver will compile the .cc itself.")

        # If a previously-saved source was passed in, load it; else generate.
        self._on_template_changed(0)
        if initial_path and initial_path.endswith((".cc", ".cpp")) and os.path.exists(initial_path):
            try:
                with open(initial_path) as f:
                    self.editor.setPlainText(f.read())
                self.status_lbl.setText(f"Loaded {os.path.basename(initial_path)} for editing.")
            except OSError:
                pass

    # ------------------------------------------------------------------ #
    def _current_spec(self):
        return self._specs[self.template_combo.currentIndex()]

    def _on_template_changed(self, _idx: int):
        spec = self._current_spec()
        self.desc_lbl.setText(spec.description)
        self._rebuild_params(spec)
        self._generate()

    def _rebuild_params(self, spec):
        # Clear the old params widget(s).
        while self._params_layout.count():
            item = self._params_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._param_spins = {}
        if not spec.params:
            return
        form_w = QWidget()
        form = QFormLayout(form_w)
        form.setContentsMargins(0, 0, 0, 0)
        for p in spec.params:
            spin = CleanDoubleSpinBox()
            spin.setRange(-1e9, 1e9)
            spin.setDecimals(p.decimals)
            spin.setValue(p.default)
            spin.setStyleSheet(SPIN_STYLE)
            spin.setToolTip(p.tip)
            spin.setMaximumWidth(140)
            lbl = QLabel(p.label + ":")
            lbl.setStyleSheet("color:#a0a8c0;")
            form.addRow(lbl, spin)
            self._param_spins[p.key] = spin
        self._params_layout.addWidget(form_w)

    def _params(self) -> dict:
        return {k: s.value() for k, s in self._param_spins.items()}

    def _generate(self):
        spec = self._current_spec()
        self.editor.setPlainText(spec.render(self._params()))
        self._compiled_ok = False
        self.diag_list.clear()
        self.status_lbl.setText("Generated. Edit if needed, then Compile or Save.")

    # ------------------------------------------------------------------ #
    def _compile(self):
        if self._worker is not None and self._worker.isRunning():
            return
        src = os.path.join(self._tmp, "dll_src.cc")
        out = os.path.join(self._tmp, "dll_src.so")
        try:
            with open(src, "w") as f:
                f.write(self.editor.toPlainText())
        except OSError as e:
            self.status_lbl.setText(f"Could not write temp source: {e}")
            return
        self.diag_list.clear()
        self.compile_btn.setEnabled(False)
        self.status_lbl.setText("Compiling…")
        self._worker = DllCompileWorker(src, out, self._compiler or "g++")
        self._worker.finished_signal.connect(self._on_compiled)
        self._worker.start()

    def _on_compiled(self, rc: int, _output: str, diags: list):
        self.compile_btn.setEnabled(self._compiler is not None)
        for d in diags:
            loc = f"{d['file']}:{d['line']}" + (f":{d['col']}" if d['col'] else "")
            it = QListWidgetItem(f"{d['level']:>7}  {loc}  {d['msg']}")
            it.setForeground(QColor(_DIAG_COLOR.get(d["level"], "#a0a8c0")))
            it.setData(Qt.ItemDataRole.UserRole, d["line"])
            self.diag_list.addItem(it)
        n_err = sum(1 for d in diags if d["level"] == "error")
        n_warn = sum(1 for d in diags if d["level"] == "warning")
        self._compiled_ok = (rc == 0)
        if rc == 0:
            self.status_lbl.setText(
                f"✓ Compiled OK" + (f"  ({n_warn} warning(s))" if n_warn else ""))
        else:
            self.status_lbl.setText(f"✗ Compile failed — {n_err} error(s).")

    def _goto_diag(self, item: QListWidgetItem):
        line = item.data(Qt.ItemDataRole.UserRole)
        if not line:
            return
        cur = self.editor.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.Start)
        cur.movePosition(QTextCursor.MoveOperation.Down,
                         QTextCursor.MoveMode.MoveAnchor, int(line) - 1)
        self.editor.setTextCursor(cur)
        self.editor.setFocus()

    # ------------------------------------------------------------------ #
    def _save_and_use(self):
        spec = self._current_spec()
        default_dir = os.path.join(repo_root(), "results", "solver", "dll_src")
        os.makedirs(default_dir, exist_ok=True)
        default = os.path.join(default_dir, default_basename(self._dll_type, spec.key) + ".cc")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save DLL source", default, "C++ Source (*.cc *.cpp);;All Files (*)")
        if not path:
            return
        if not path.endswith((".cc", ".cpp")):
            path += ".cc"
        try:
            with open(path, "w") as f:
                f.write(self.editor.toPlainText())
        except OSError as e:
            self.status_lbl.setText(f"Save failed: {e}")
            return
        self.result_path = path
        self.accept()

    def done(self, r: int):
        # Best-effort cleanup of the temp compile dir.
        try:
            import shutil
            shutil.rmtree(self._tmp, ignore_errors=True)
        except Exception:
            pass
        super().done(r)
