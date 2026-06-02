# HybMesh PreProcessor GUI — 完整審查與改善計劃

> 審查涵蓋：20+ 個 Python 檔案，包含 models、controllers、commands、services、workers、views 全層。  
> 優先等級：🔴 **P0 Bug** → 🟠 **P1 UX** → 🔵 **P2 Code Quality** → 🟢 **P3 Enhancement**

---

## 🔴 P0 — 確認 Bug（立即修正）

### B1 — `mesh_canvas.py`：BC item 被雙重加入場景
**問題**：`_rebuild_boundary_coloring` 中先呼叫 `self.plot_widget.plot(...)` 建立 `bc_item`（此操作已自動 addItem），之後又多呼叫一次 `self.plot_widget.addItem(bc_item)`，導致每條 BC 邊被渲染兩次、儲存在 `self.bc_items` 兩次，後續移除時也嘗試移除兩次。  
**位置**：[`mesh_canvas.py`](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/views/mesh_canvas.py) L427–434  
**修正**：移除多餘的 `addItem(bc_item)` 呼叫，只保留 `plot()` 回傳的 item。

---

### B2 — `canvas.py`：點擊選取頂點的邏輯錯誤
**問題**：`_on_mouse_clicked` 中有 `if not self.split_scatter.isVisible(): return` 的 guard，導致只要沒有分割點顯示在畫布上，所有頂點點擊都被靜默忽略。正確的判斷應是「目前是否有 active 幾何資料」，而非 scatter 是否可見。  
**位置**：[`canvas.py`](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/views/canvas.py) L476  
**修正**：改成 `if self._active_session_id is None or self._active_points is None: return`。

---

### B3 — `mesh_canvas.py`：`_rebuild_mesh_items` 在 mesh 為空時不清空舊資料
**問題**：`if not self.mesh or len(self.mesh.points) == 0: return` 直接 return，跳過了前面的 clear 邏輯（L204–215），導致切換 session 後舊的 wireframe/填色資料殘留在畫布上。  
**位置**：[`mesh_canvas.py`](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/views/mesh_canvas.py) L201  
**修正**：先執行 clear，再判斷 mesh 是否為空後 return。

---

### B4 — `bc_widget.py`：設定 custom 值時 `textChanged` 雙重觸發
**問題**：`setText()` 中：先 `blockSignals(True)` 設值，再 `blockSignals(False)`，然後呼叫 `textChanged.emit()`。但若是 custom 模式，`custom.setText(val_clean)` 會觸發 `_on_custom_changed`，後者也會 `emit textChanged`，造成雙重發射。  
**位置**：[`bc_widget.py`](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/views/bc_widget.py) L63–82  
**修正**：在 `setText` 整個過程中包裹 `blockSignals(True)`，結束後手動 emit 一次。

---

### B5 — `collapsible.py`：`toggle_btn` 連接 `clicked` 而非 `toggled`
**問題**：`toggle_btn.clicked.connect(self._on_toggle)` — `clicked` 信號只在使用者點擊時觸發，`setChecked()` 不會觸發。若外部程式碼呼叫 `toggle_btn.setChecked(True)` 而不透過 `expand()`，內容框不會展開。  
**位置**：[`collapsible.py`](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/views/collapsible.py) L35  
**修正**：改為 `toggle_btn.toggled.connect(self._on_toggle)`。

---

### B6 — `segment.py`：`from_dict` curve_mode 判斷與 `to_dict` 不一致
**問題**：`from_dict` 以 `"x_formula" in d` 判斷 parametric mode，但若 JSON 同時含有三個 key（老版本資料），會誤判。`to_dict` 在 explicit mode 不寫 `x_formula`/`y_formula`，但若有第三方手寫 JSON 包含這些 key，就會出問題。  
**位置**：[`segment.py`](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/models/segment.py) L61–72  
**修正**：優先以 `d.get("curve_mode")` 明確欄位判斷；x/y formula 的存在僅作為 fallback。

---

### B7 — `session_ctrl.py`：`_load_geometry_file` 中 `n_seg` 可能為負數
**問題**：`n_seg = len(session.split_indices) - 1`，當 `split_indices` 為空（未偵測到分割點）時算出 -1，顯示 `-1 auto-detected edges`。  
**位置**：[`session_ctrl.py`](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/controllers/session_ctrl.py) L253  
**修正**：`n_seg = max(0, len(session.split_indices) - 1)`。

---

### B8 — `mesh_gen_ctrl.py`：Export filename `.*` 置換邏輯重複
**問題**：`export_generated_vtk` 和 `export_star_cd` 各自實作相同的 `.*` → `.vtk` / `.*` → `.vrt` 置換邏輯，兩處各自處理 `isabs` 判斷，高度重複且容易不同步。  
**位置**：[`mesh_gen_ctrl.py`](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/controllers/mesh_gen_ctrl.py) L259–270, L322–332  
**修正**：提取 `_resolve_export_path(user_fn, ext, root_dir, default_dir)` 工具函式統一呼叫。

---

### B9 — `mesh_gen_run.py`：Worker 的重複 cancel 路徑有 race condition
**問題**：stdout 讀取結束後，第 44 行和第 53 行各有一個 `if self._cancelled` 判斷，且兩次都呼叫 `terminate()`，但第二次呼叫前沒有先確認 process 是否仍在執行（`poll() is None`），可能在已結束的 process 上呼叫 `terminate()`。  
**位置**：[`mesh_gen_run.py`](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/workers/mesh_gen_run.py) L44–57  
**修正**：合併兩個 cancel 判斷，`terminate()` 前加 `if self._process.poll() is None` 保護。

---

### B10 — `mesh_config_panel.py`：直接呼叫 `self.window().mesh_canvas_view`（View-to-View 耦合）
**問題**：`_on_browse_geom` 和 `_on_remove_geom` 直接透過 `self.window()` 取得 `mesh_canvas_view` 並呼叫其方法，繞過 controller。若 window 層次結構變更，這段程式碼靜默失敗。  
**位置**：[`mesh_config_panel.py`](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/views/panels/mesh_config_panel.py) L474–503  
**修正**：改用 `pyqtSignal` 通知 controller 處理，不直接引用其他 view。

---

### B11 — `geometry_service.py`：`eval()` 沙盒不完整（安全性）
**問題**：`eval(expr, {"__builtins__": {}}, safe)` 無法完全防止 Python 物件模型逃逸（如 `().__class__.__bases__[0].__subclasses__()`）。惡意的 `.json` 設定檔可以執行任意程式碼。  
**位置**：[`geometry_service.py`](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/services/geometry_service.py) L17  
**修正**：改用 `sympy.sympify` 解析，或在 `safe` dict 中加 `"__builtins__": None`，並加強例外處理。

---

### B12 — `log_panel.py`：`appendHtml` 在 `QPlainTextEdit` 上非官方支援
**問題**：`QPlainTextEdit` 的官方方法是 `appendPlainText()`，`appendHtml()` 是透過 Qt 內部機制繼承，非官方 API，未來版本可能移除或行為改變。  
**位置**：[`log_panel.py`](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/views/log_panel.py) L111  
**修正**：改用 `QTextEdit`（支援 rich text），並加入 auto-scroll。

---

### B13 — `session_ctrl.py`：JSON config 無 `input_file` 時靜默失敗
**問題**：`_apply_json_config` 若 `input_file` 為空，`original_points` 維持 `None`，`split_indices` 被設為空 list，後續呼叫 `_apply_geometry_update` 因 `original_points is None` 而靜默 return，不報錯。  
**位置**：[`session_ctrl.py`](file:///Users/hjlu_nchc/home/NCHC/CESE/HybMesh/tools/PreProcessor/gui/app/controllers/session_ctrl.py) L325–333  
**修正**：在 `input_file` 為空時，明確 log 提示並跳過後續步驟，避免部分初始化的 session。

---

## 🟠 P1 — UX 問題

### U1 — Undo/Redo 按鈕不隨堆疊狀態更新 enable/disable
`CommandHistory` 已有 `can_undo`/`can_redo` 屬性，但按鈕始終啟用。  
**修正**：每次執行命令、undo、redo 後呼叫 `_update_undo_redo_buttons(session)` 更新按鈕狀態。

---

### U2 — Domain 範圍輸入無即時驗證（XMin ≥ XMax）
使用者可設定反轉域邊界，後端收到無效參數。  
**修正**：在 `run_mesh_generator` 前加入驗證，XMin ≥ XMax 時 log 錯誤並 return。

---

### U3 — Log Panel 無自動捲動
新增 log 後不自動捲到底部。  
**修正**：在 `log()` 末尾加入 `self.moveCursor(QTextCursor.MoveOperation.End)`。

---

### U4 — 無進度條顯示 Mesh Generation 進度
**修正**：在 toolbar 加入 `QProgressBar`（indeterminate），生成期間顯示，完成後隱藏。

---

### U5 — 幾何列表無顏色標示，無法辨識 session
**修正**：在 `_sync_geometry_list` 中為每個 item 設 `setForeground(QColor(session.color))`。

---

### U6 — `advanced_panel.py`：hint 文字幾乎不可見（`color:#556`）
**修正**：改為 `color:#6a7aaa`（可讀的深灰藍色）。

---

### U7 — `vertex_panel.py`：雙層 CollapsibleSection 需兩次點擊
**修正**：移除內部的 sub-collapsible，直接展開，或預設 `start_collapsed=False`。

---

### U8 — `transform_panel.py`：Base Point 對所有操作都顯示
**修正**：根據 `dup_type_combo` 值決定是否顯示 Base Point 區域（Translate/Mirror H/V 時隱藏）。

---

### U9 — `mesh_canvas.py`：幾何預覽在主執行緒讀取大型檔案（UI 凍結）
**修正**：移至背景 `QThread` 或 `QRunnable`。

---

### U10 — `edge_list_panel.py`：`curve_bake_btn` 始終啟用，狀態管理缺失
**修正**：`handle_file_segment_selected` 時 disable；`handle_curve_segment_selected` 時 enable。

---

### U11 — Mesh Generator 空狀態無引導
**修正**：加入空狀態 overlay，顯示「請先在 CAD 分頁載入幾何資料」。

---

### U12 — `canvas.py`：座標標籤每像素更新，無節流
**修正**：加入 16ms timer debounce（每幀最多更新一次）。

---

## 🔵 P2 — 程式碼品質

| # | 問題 | 位置 | 修正方向 |
|---|------|------|----------|
| Q1 | `bc_colors` dict 三個地方重複定義 | `bc_widget.py`, `mesh_canvas.py`, `mesh_config_panel.py` | 移至 `app/utils.py` 或 `app/constants.py` |
| Q2 | `LINEEDIT_STYLE` 重複定義 | `bc_widget.py` L6, `mesh_config_panel.py` L19 | 移至 `app/styles.py` |
| Q3 | `list_style` 重複定義 | `edge_list_panel.py`, `geometry_panel.py` | 移至 `app/styles.py` |
| Q4 | `QDoubleSpinBox` vs `CleanDoubleSpinBox` 不一致 | `vertex_panel.py`, `transform_panel.py` | 統一改為 `CleanDoubleSpinBox` |
| Q5 | `utils.py` import 順序混亂、重複 import | `utils.py` L17,L49 | 整理至頂部，移除重複 |
| Q6 | `controller.py` sync 函式三重複 | `controller.py` L160–217 | 重構為 `_make_sync_fn()` factory |
| Q7 | `mesh_config.py` 30+ elif 分支 | `mesh_config.py` | 改用 `KEY_MAP` dict + `setattr` |
| Q8 | `main_window.py` checkbox stylesheet 重複貼上 4 次 | `main_window.py` | 提取為 `TOOLBAR_CHECKBOX_STYLE` 常數 |
| Q9 | Dead widgets（廢棄按鈕） | `main_window.py`, `mesh_config_panel.py`, `actions_panel.py` | 移除或加明確文件說明 |
| Q10 | `sidebar.py` ~60 個屬性別名維護負擔 | `sidebar.py` | 考慮移除，讓 controller 直接存取 `sb.file_panel.load_btn` |
| Q11 | `log_panel.py` 的 `import re` 在函式內 | `log_panel.py` L86 | 移至模組頂部 |

---

## 🟢 P3 — 功能加強建議

| # | 功能 | 工作量 |
|---|------|--------|
| E1 | Keyboard Shortcuts 擴充（Ctrl+O/S/T/W、F5） | 中 |
| E2 | Recent Files（QSettings） | 中 |
| E3 | Color mode 切換快取 wireframe（效能） | 中 |
| E4 | Mesh Quality Histogram（pyqtgraph） | 大 |
| E5 | Session 狀態持久化 | 大 |
| E6 | CollapsibleSection 展開動畫 | 小 |
| E7 | Geometry 列表右鍵選單（重命名、刪除、聚焦） | 中 |

---

## 執行優先順序總表

| 批次 | 項目 | 預估工作量 |
|------|------|-----------|
| **批次 1（P0 Bugs）** | B1–B9 | 各 30 min 以內 |
| **批次 2（P1 UX）** | U1, U3, U5, U6, U10 | 各 20–30 min |
| **批次 3（P1 UX）** | U2, U4, U7, U8, U11, U12 | 各 30–60 min |
| **批次 4（P2 Quality）** | Q1–Q5, Q8–Q11 | 各 20 min |
| **批次 5（P2 Quality）** | Q6, Q7 重構 | 各 1–2 hr |
| **批次 6（P3 Enhancement）** | E1, E2, E6, E7 | 各 1–2 hr |
| **批次 7（P3 大功能）** | E3, E4, E5 | 各 4+ hr |
